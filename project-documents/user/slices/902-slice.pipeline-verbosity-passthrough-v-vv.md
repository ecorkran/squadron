---
docType: slice-design
slice: pipeline-verbosity-passthrough-v-vv
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260426
dateUpdated: 20260426
status: not_started
relatedIssues: [9]
---

# Slice Design: Pipeline Verbosity Passthrough (`-v`/`-vv`)

## Overview

Fixes [issue #9](https://github.com/ecorkran/squadron/issues/9). The pipeline
runner currently hard-codes `-v` on every review sub-command it emits, and the
`/sq:run` slash command swallows trailing flags (like `-v`/`-vv`) into the
target string. Two coordinated changes let the user control verbosity for
pipeline-driven reviews end-to-end.

1. **Thread verbosity from `sq run` into `PromptRenderer` and replace the
   hard-coded `-v` in `_render_review`.** Default becomes 0 (no flag);
   `-v` and `-vv` opt in explicitly. This is a deliberate behavior change.
2. **Update `/sq:run` slash command to peel trailing `-v`/`-vv`/`--verbose`
   tokens from `$ARGUMENTS`** before splitting pipeline/target, and pass them
   through to the `sq run` CLI invocation.

## Value

- **User controls review verbosity per-run.** Today every pipeline review
  emits `-v` unconditionally — the user cannot quiet them or raise to `-vv`.
  After this slice, `sq run slice 152 -vv` produces `-vv` on every review
  command, and `sq run slice 152` (no flag) produces silent reviews.
- **Slash command parity.** `/sq:run slice 152 -v` currently breaks because
  `-v` is swallowed into the target argument. After this slice, the flag is
  peeled off and forwarded correctly.
- **Cleaner default output.** Removing the unconditional `-v` reduces noise
  on routine pipeline runs where the user didn't ask for detail.

## Technical Scope

### Included

- **`render_step_instructions` and `_render_review`** gain a `verbosity: int`
  parameter. The hard-coded `cmd_parts.append("-v")` at
  [`prompt_renderer.py:174`](../../../src/squadron/pipeline/prompt_renderer.py#L174)
  becomes conditional: emit nothing at 0, `-v` at 1, `-vv` at 2+.
- **`sq run` CLI** threads its existing `verbose` count into
  `render_step_instructions` calls in the prompt-only path.
- **`/sq:run` slash command** (`commands/sq/run.md`) updated to peel
  `-v`/`-vv`/`--verbose` from `$ARGUMENTS` and include them in the
  `sq run ... --prompt-only` invocation.
- **Tests** updated: existing `test_prompt_renderer.py` assertion for
  hard-coded `-v` updated; new parametrized cases for verbosity 0/1/2.

### Excluded

- **Executor-path (non-prompt-only) verbosity threading.** The full executor
  in `executor.py` builds review commands differently (via `ActionContext` and
  `ReviewAction`). Threading verbosity into `ActionContext` and
  `run_review_with_profile` is valuable but orthogonal — it only matters when
  `sq run` executes reviews in-process (SDK mode), not prompt-only mode. This
  can be a follow-up if needed.
- **`--step-done` / `--next` / `--resume` paths.** These don't render review
  commands; they operate on already-rendered runs.
- **Verbosity for non-review actions** (dispatch, commit, cf-op). These
  don't emit sub-commands affected by verbosity level.
- **Config-file verbosity default.** The review CLI has
  `_resolve_verbosity()` that reads `get_config("verbosity")`. The pipeline
  runner does not consult config — it uses the CLI flag only. Adding config
  fallback is a separate concern.

## Technical Decisions

### Verbosity flows through `render_step_instructions`, not `ActionContext`

The prompt-only path never constructs an `ActionContext` — it goes from
`StepConfig` → `render_step_instructions` → JSON. The natural injection
point is a `verbosity` keyword argument on `render_step_instructions`, which
passes it through to `_build_action_instruction` → `_render_review`.

This is simpler and more contained than modifying `ActionContext` (which
would ripple into the full executor and every action type).

### Default verbosity changes from 1 to 0

Today `_render_review` unconditionally appends `-v`. After this slice, no
flag is emitted when verbosity is 0. This means existing pipelines that
relied on the implicit `-v` will run quieter by default.

This is intentional: the hard-coded `-v` was never a deliberate feature — it
was a placeholder from initial development. Users who want verbose review
output should pass `-v` explicitly. The issue description confirms this:
"Default 0 (no flag); `-v` and `-vv` opt in."

### Slash command uses simple suffix matching, not full argparse

The `/sq:run` command is a markdown file interpreted by Claude Code, not a
Python CLI. Complex argument parsing is inappropriate. The implementation
peels recognized flag tokens (`-v`, `-vv`, `--verbose`) from the tail of
`$ARGUMENTS` before splitting pipeline/target. This is sufficient because:

- `-v`/`-vv`/`--verbose` are unambiguous — no pipeline name or target would
  legitimately be these strings.
- The tokens are always at the end of the argument string (natural CLI
  usage).
- Only these three tokens need recognition; this is not a general-purpose
  flag parser.

## Implementation Details

### Change 1: `prompt_renderer.py` — conditional verbosity emission

**File:** `src/squadron/pipeline/prompt_renderer.py`

**`_render_review` signature change:**

```python
def _render_review(
    config: dict[str, object],
    params: dict[str, object],
    resolver: ModelResolver,
    *,
    verbosity: int = 0,   # <-- new
) -> ActionInstruction:
```

**Command-building change** (replacing the hard-coded line 174):

```python
# Emit verbosity flag only when requested
if verbosity == 1:
    cmd_parts.append("-v")
elif verbosity >= 2:
    cmd_parts.append("-vv")
```

**`_build_action_instruction` change:** Accept and forward `verbosity` kwarg
when calling `_render_review`.

**`render_step_instructions` signature change:**

```python
def render_step_instructions(
    step: StepConfig,
    *,
    step_index: int,
    total_steps: int,
    params: dict[str, object],
    resolver: ModelResolver,
    run_id: str,
    verbosity: int = 0,   # <-- new
) -> StepInstructions:
```

Passes `verbosity` through to `_build_action_instruction`.

### Change 2: `run.py` — thread verbose into prompt-only rendering

**File:** `src/squadron/cli/commands/run.py`

At the call sites where `render_step_instructions` is invoked (in the
prompt-only code path), pass `verbosity=verbose`:

```python
instructions = render_step_instructions(
    step,
    step_index=...,
    total_steps=...,
    params=params,
    resolver=resolver,
    run_id=run_id,
    verbosity=verbose,  # <-- new
)
```

There are two call sites to update:
1. Initial prompt-only render (first step).
2. `--next --resume` render (subsequent steps).

### Change 3: `/sq:run` slash command — peel verbosity flags

**File:** `commands/sq/run.md`

Update the "Input parsing" section to instruct the LLM to:

1. Scan `$ARGUMENTS` for trailing `-v`, `-vv`, or `--verbose` tokens.
2. Remove them from the argument string.
3. Append them to the `sq run ... --prompt-only` command.

Updated usage line:

```
/sq:run <pipeline> [target] [-v|-vv]  — run a pipeline (e.g., /sq:run slice 152 -v)
```

Updated Step 0 command template:

```bash
sq run <pipeline> <target> <verbose_flags> --prompt-only
```

### Change 4: Tests

**File:** `tests/pipeline/test_prompt_renderer.py`

- Update the existing test that asserts `"-v"` in the review command to
  expect no flag at default verbosity (0).
- Add parametrized tests for verbosity 0, 1, and 2:
  - `verbosity=0` → command does not contain `-v` or `-vv`
  - `verbosity=1` → command ends with `-v`
  - `verbosity=2` → command ends with `-vv`

## Component Interactions

```
User invokes: sq run slice 152 -vv
                         │
        ┌────────────────┴─────────────────┐
        │  run.py captures verbose=2       │
        │  (typer --verbose/-v count=True) │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │  render_step_instructions(       │
        │      ..., verbosity=2)           │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │  _render_review(...,             │
        │      verbosity=2)                │
        │  → cmd_parts.append("-vv")       │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │  JSON output:                    │
        │  "command": "sq review slice     │
        │             152 --model glm5     │
        │             -vv"                 │
        └──────────────────────────────────┘
```

For the slash command path:

```
User invokes: /sq:run slice 152 -vv
                         │
        ┌────────────────┴─────────────────┐
        │  run.md peels -vv from args      │
        │  pipeline="slice", target="152"  │
        │  verbose_flags="-vv"             │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │  sq run slice 152 -vv            │
        │      --prompt-only               │
        └────────────────┬─────────────────┘
                         │
              (same flow as above)
```

## Success Criteria

1. `sq run slice 152 --prompt-only` (no verbose flag) produces review
   commands without `-v` or `-vv` in the `command` field.
2. `sq run slice 152 -v --prompt-only` produces review commands with `-v`.
3. `sq run slice 152 -vv --prompt-only` produces review commands with `-vv`.
4. The hard-coded `cmd_parts.append("-v")` in `_render_review` is replaced
   with conditional emission based on the `verbosity` parameter.
5. `render_step_instructions` accepts a `verbosity` keyword argument
   (default 0) and forwards it to review rendering.
6. `/sq:run slice 152 -v` correctly peels the flag and runs
   `sq run slice 152 -v --prompt-only`.
7. `/sq:run slice 152` (no flag) runs `sq run slice 152 --prompt-only`
   without verbosity flags.
8. Existing tests pass after updating the hard-coded `-v` expectation.
9. New parametrized tests cover verbosity levels 0, 1, and 2.

## Verification Walkthrough

**Step 1 — Default (silent) review commands.**

```bash
uv run sq run slice 152 --prompt-only 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for a in data.get('actions', []):
    cmd = a.get('command', '')
    if cmd:
        assert '-v' not in cmd.split(), f'Unexpected -v in: {cmd}'
        print(f'OK: {cmd}')
"
```

Expected: review commands contain no `-v` or `-vv`.

**Step 2 — Explicit `-v`.**

```bash
uv run sq run slice 152 -v --prompt-only 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for a in data.get('actions', []):
    cmd = a.get('command', '')
    if 'review' in cmd:
        assert cmd.endswith('-v'), f'Expected -v at end: {cmd}'
        print(f'OK: {cmd}')
"
```

Expected: review commands end with `-v`.

**Step 3 — Explicit `-vv`.**

```bash
uv run sq run slice 152 -vv --prompt-only 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for a in data.get('actions', []):
    cmd = a.get('command', '')
    if 'review' in cmd:
        assert cmd.endswith('-vv'), f'Expected -vv at end: {cmd}'
        print(f'OK: {cmd}')
"
```

Expected: review commands end with `-vv`.

**Step 4 — Test suite.**

```bash
uv run pytest tests/pipeline/test_prompt_renderer.py -v
```

Expected: all tests pass, including the updated and new verbosity tests.

**Step 5 — Full gate.**

```bash
uv run pytest -q && uv run ruff check && uv run pyright
```

Expected: all pass.

## Implementation Notes

### Development Approach

Suggested implementation order:

1. `_render_review` and `_build_action_instruction` — add `verbosity`
   parameter, replace hard-coded `-v` with conditional.
2. `render_step_instructions` — add `verbosity` parameter, forward it.
3. `run.py` — pass `verbose` to `render_step_instructions` at both call
   sites.
4. Tests — update existing assertion, add parametrized verbosity tests.
5. `commands/sq/run.md` — update input parsing and Step 0 command template.
6. Manual verification with the walkthrough above.

### Effort

1/5. Four files touched (prompt_renderer, run.py, run.md, test_prompt_renderer).
All changes are mechanical: add a parameter, forward it, conditionally emit.
