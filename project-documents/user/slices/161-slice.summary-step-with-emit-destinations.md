---
docType: slice-design
slice: summary-step-with-emit-destinations
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [158-sdk-session-management-and-compaction]
interfaces: [152-pipeline-documentation]
dateCreated: 20260408
dateUpdated: 20260408
status: not_started
---

# Slice Design: Summary Step with Emit Destinations

## Overview

Add a `summary` pipeline step type that captures a summary of the current
SDK session's conversation-so-far and emits it to one or more named
destinations. Factor the *summary-generation* axis out of the existing
`compact` step so that "make a summary" and "what to do with the summary"
become orthogonal concerns.

The new step uses the same session-rotate summarizer mechanism that
slice 158 built (cheap-model switch, compact-template dispatch, summary
capture) but decouples it from the act of rotating the session. The
pipeline author chooses one or more destinations from a registry:
`stdout`, `file`, `clipboard`, and `rotate` (the slice 158 session
rotate behavior). `compact` is retained as a thin alias step that
expands to a summary action with `emit: [rotate]` hardcoded — existing
pipelines using `- compact: { template: ..., model: ... }` continue to
work unchanged.

The motivating use case: a pipeline author wants to pause at a
checkpoint after a design step, discuss the design with a model in
interactive Claude Code, then resume the pipeline. Today there is no
clean way to get the pipeline's context into a Claude Code conversation.
With this slice the pipeline can write
`- summary: { template: minimal-sdk, emit: [clipboard, file], checkpoint: always }`
and the user gets the summary on their clipboard and on disk at the
moment the pipeline pauses.

## Value

- **Bridges the pipeline ↔ interactive Claude Code gap**: pipeline state
  becomes copy-pasteable in one step. Solves the "I want to discuss my
  paused slice design with a model before resuming" workflow that
  currently requires manual digging through state files.
- **Composable summary destinations**: the same summary text can be
  rotated into a fresh SDK session AND written to a file in the same
  step, or any other combination. No more "compact does session
  rotation but I also wanted a copy."
- **Backward compatible**: `compact` keeps working exactly as it does
  today. Pipeline authors who don't want to think about emit destinations
  never have to.
- **Foundation for follow-ups**: a `clear` alias (rotate without seed)
  becomes a small follow-up; new emit destinations can be registered
  without changing the step type.

## Technical Scope

### In Scope

1. **New `summary` step type and `summary` action**, registered alongside
   the existing compact step/action. The step expands to a single
   summary action.

2. **Emit destination registry** in a new module
   `src/squadron/pipeline/emit.py`. Built-in destinations:
   - `stdout` — print summary to the pipeline's stdout (currently the
     same channel as logger info; uses `print()` so it survives even
     when logging is silenced).
   - `file: <path>` — write summary text (no framing prefix) to the
     given path. Path is resolved relative to the pipeline's `cwd` if
     not absolute. Parent directory is created if missing.
   - `clipboard` — copy summary text to the OS clipboard via `pyperclip`.
   - `rotate` — invoke `SDKExecutionSession.compact()` exactly as the
     current compact action does, with the same `summary_model` /
     `restore_model` semantics. The summary used for the rotated
     session's seed is the same one captured before any other emit
     destinations run.

3. **Two-phase emit**: every summary action first captures the summary
   text once (single dispatch), then iterates over emit destinations.
   Destinations are independent and run sequentially in declared order.
   A failing emit produces a warning but does not fail the action
   unless the destination is `rotate` (rotation failure must propagate).

4. **`compact` alias preserved**: the existing `compact` step/action
   remains, but its `execute()` body becomes a thin call into the new
   shared summary helper with `emit=[rotate]` baked in. The compact
   action keeps its current outputs shape (`summary`, `instructions`,
   `source_step_index`, `source_step_name`, `summary_model`) so
   `StateManager._maybe_record_compact_summaries()` continues to fire
   and the run state's `compact_summaries` field still gets populated.
   See "Compact alias compatibility" below for the exact contract.

5. **Checkpoint shorthand on summary step**: a `checkpoint: always`
   field on the summary step expands the step into a two-action
   sequence `[summary, checkpoint]`. The shorthand is purely sugar;
   internally it produces the same structure as writing a separate
   `- checkpoint: { trigger: always }` step right after the summary.
   Triggers other than `always` (`on-fail`, `on-concerns`, `never`)
   are also accepted and pass through unchanged.

6. **`pyperclip` dependency**: add `pyperclip` to `pyproject.toml` as a
   runtime dependency. It is a small pure-Python library that wraps
   platform-specific clipboard tools (`pbcopy`, `xclip` / `xsel` /
   `wl-copy`, `clip.exe`). At import time it does nothing; at first
   call it probes the platform.

7. **Validation**:
   - `template` is required (string).
   - `model` optional (string, alias-validatable like other model
     fields).
   - `emit` optional (list of strings or one-key dicts). Default
     `[stdout]` if omitted.
   - Each emit entry must be one of: a known destination name
     (`stdout`, `clipboard`, `rotate`) or a single-key dict whose key
     is `file` and whose value is a non-empty string path.
   - `emit: [rotate]` (or any list containing `rotate`) is rejected at
     pipeline-load time when the pipeline mode is known to be non-SDK,
     and at runtime in `summary.execute()` if `context.sdk_session is
     None`. The runtime check is the authoritative one because
     pipeline-load may not know the future execution mode; the
     load-time check is best-effort and reports a warning, not an
     error. (See "On non-SDK mode and rotate" below.)
   - `checkpoint` optional (string trigger value, validated against
     the existing checkpoint trigger enum).

8. **Outputs**: the summary action returns an `ActionResult` with:
   - `summary` — the captured summary text
   - `instructions` — rendered template instructions
   - `emit_results` — list of per-destination dicts:
     `{"destination": "clipboard", "ok": True, "detail": ""}` or
     `{"destination": "file:/tmp/x.md", "ok": True, "detail": "wrote 1234 bytes"}`
   - `source_step_index`, `source_step_name`, `summary_model` —
     identical to the compact action's keying primitives, so any
     consumer that already inspects compact outputs continues to work

9. **Test pipeline update** (smoke verification only): add a `summary`
   variant of `test-pipeline.yaml` (or a sibling fixture) that
   exercises the new step type with `emit: [stdout, file]` so manual
   smoke runs cover the new path.

### Out of Scope

- **`sq checkpoint-context <run-id>` command** — the standalone
  "render run state to a context blob" subcommand discussed earlier.
  Postponed because users typically don't know run-ids and the command
  would have to reimplement the same paused-run discovery logic that
  `--resume` already has. May land in a follow-up slice if demand
  emerges.
- **`clear` alias** (rotate without summary seeding). Filed as a
  known follow-up. Trivially layerable as either a second alias step
  type or a `seed: false` flag on summary.
- **New emit destinations beyond stdout/file/clipboard/rotate**:
  `slack:`, `webhook:`, `gist:` etc. Registry exists; adding new
  destinations is a small follow-up if and when wanted.
- **Auto-discovery of paused runs for one-shot summary export**.
- **Reformatting the summary based on destination** (e.g. HTML for
  one, markdown for another). Single text payload per dispatch.

## Architecture

### Step → Action Expansion

```
Pipeline YAML:
  - summary:
      template: minimal-sdk
      model: haiku
      emit: [clipboard, file: /tmp/ctx.md]
      checkpoint: always

Step type expansion (with checkpoint shorthand):
  -> [
       ("summary", {template, model, emit}),
       ("checkpoint", {trigger: "always"}),
     ]

Step type expansion (no checkpoint):
  -> [("summary", {template, model, emit})]
```

The `compact` step's expansion is unchanged from today: `[("compact",
{template, model, keep, summarize})]`.

### Summary Action Flow

```
summary.execute(context):
  1. Resolve template and render instructions (existing helpers)
  2. Resolve summary model alias (if provided)
  3. Capture restore_model = context.sdk_session.current_model
  4. Validate destinations vs. execution mode
       (rotate requires sdk_session)
  5. summary_text = await capture_summary(
       session=context.sdk_session,
       instructions=instructions,
       summary_model=resolved,
     )
       -> internally: optionally set_model(summary_model),
          dispatch(instructions), receive response, restore model.
          NOTE: this is *not* the existing compact() session-rotate
          method — it captures the summary without disconnecting.
          A new helper `capture_summary()` is added to
          SDKExecutionSession alongside the existing compact().
  6. emit_results = []
     for dest in destinations:
       result = await emit_registry[dest.kind](summary_text, dest, context)
       emit_results.append(result)
       if dest.kind == "rotate" and not result.ok:
         return ActionResult(success=False, error=result.detail)
  7. Return ActionResult(success=True, outputs={
       summary, instructions, emit_results,
       source_step_index, source_step_name, summary_model
     })
```

### Capture vs. Rotate

Slice 158's `SDKExecutionSession.compact()` does *both* in one method:
generate the summary AND rotate the session. Slice 161 splits these
into two operations on `SDKExecutionSession`:

- `capture_summary(instructions, summary_model)` — switch model if
  needed, dispatch instructions, capture response, restore the prior
  model. Does NOT disconnect, does NOT create a new client. Returns
  the summary string.
- `compact(instructions, summary_model, restore_model)` — unchanged
  from slice 158. Internally now refactored to call
  `capture_summary()` first, then disconnect, then create the new
  client and seed it. The seed step keeps using
  `frame_summary_for_seed()` from slice 158.

The refactor of `compact()` is small (it already does the steps in
sequence; we just extract the first half). The compact action's
contract with the executor and state manager is preserved.

### Emit Registry

```python
# src/squadron/pipeline/emit.py

@dataclass(frozen=True)
class EmitDestination:
    kind: Literal["stdout", "file", "clipboard", "rotate"]
    arg: str | None = None  # path for file; unused otherwise

@dataclass(frozen=True)
class EmitResult:
    destination: str  # human-readable form, e.g. "file:/tmp/x.md"
    ok: bool
    detail: str

EmitFn = Callable[
    [str, EmitDestination, "ActionContext"],
    Awaitable[EmitResult],
]

_REGISTRY: dict[str, EmitFn] = {}

def register_emit(kind: str, fn: EmitFn) -> None: ...
def get_emit(kind: str) -> EmitFn: ...

# Built-ins registered on module import:
async def _emit_stdout(text, dest, ctx) -> EmitResult: ...
async def _emit_file(text, dest, ctx) -> EmitResult: ...
async def _emit_clipboard(text, dest, ctx) -> EmitResult: ...
async def _emit_rotate(text, dest, ctx) -> EmitResult: ...
```

`_emit_rotate` is the only destination that touches the SDK session.
It calls `context.sdk_session.compact()` with the *already-captured*
summary text. This requires either (a) the rotate emit also passes
the captured summary in to `compact()` so the model isn't queried
again, or (b) a new `compact()` overload that accepts a pre-rendered
summary instead of generating one.

We choose **(b)**: extend `SDKExecutionSession.compact()` with an
optional `summary` parameter that, if provided, skips the
capture-summary phase and goes straight to disconnect → reconnect →
seed. The slice 158 path (no `summary` arg) keeps working unchanged.
This avoids running the summarizer twice for `emit: [..., rotate]`
combinations.

### Compact Alias Compatibility

The existing `compact` step type and action are preserved verbatim
*at the YAML grammar boundary*. Internally, `CompactAction.execute()`
becomes a thin wrapper:

```python
async def execute(self, context: ActionContext) -> ActionResult:
    # ... existing template loading and instructions rendering ...
    if context.sdk_session is None:
        # Non-SDK path unchanged: ContextForge compaction.
        return await self._cf_compact(context, instructions)
    # SDK path: delegate to shared summary helper with emit=[rotate].
    return await _execute_summary(
        context=context,
        instructions=instructions,
        summary_model_alias=context.params.get("model"),
        emit_destinations=[EmitDestination(kind="rotate")],
        action_type=self.action_type,  # so outputs are still tagged "compact"
    )
```

The shared `_execute_summary()` helper lives in `actions/summary.py`
and returns an `ActionResult` whose `action_type` is whatever the
caller specifies. State manager's
`_maybe_record_compact_summaries()` keys on
`ar.action_type == "compact"`, so compact-via-alias still records
into `compact_summaries`. The new `summary` action does NOT record
into `compact_summaries` (its outputs go to its emit destinations
instead) — there is a separate question of whether `summary`
output should also persist for resume seeding, addressed in "Open
questions".

### On Non-SDK Mode and `rotate`

`emit: [rotate]` requires an SDK session. There are three modes
where it could appear:

- **SDK mode** (`sq run` from a real terminal) — works as designed.
- **Prompt-only mode** (`sq run --prompt-only`) — `context.sdk_session`
  is `None`. Validation at the action level returns
  `ActionResult(success=False, error="emit: rotate requires SDK execution mode")`.
- **Pipeline-load validation** (`sq run --validate <pipeline>`) — the
  load-time validator does not know which mode the pipeline will
  eventually run in, so it cannot definitively reject rotate. It
  emits a warning at load time if `emit` contains `rotate`,
  documenting that the pipeline will fail if run in prompt-only
  mode. The error stops execution at runtime, not at load.

The warning is best-effort. If the validation surface doesn't
naturally support warnings (today it's errors only), we either add a
warning channel or skip the load-time hint entirely and rely on the
runtime error. **Decision deferred to implementation**: easiest
acceptable answer at coding time wins.

### Clipboard Mechanics

`pyperclip.copy(text)` is synchronous and platform-aware. Wrapping it
in `asyncio.to_thread()` keeps the emit registry's async signature
honest without blocking the event loop on a fast operation. On a
machine without a clipboard backend (e.g., headless Linux without
xclip/xsel/wl-copy installed), `pyperclip` raises
`pyperclip.PyperclipException`. The clipboard emit catches this and
returns `EmitResult(ok=False, detail="...")` so the rest of the
emit chain still runs. The summary action does not fail on clipboard
errors (a clipboard miss is not fatal); the user sees a warning and
the file/stdout fallback (if configured) still works.

### File Emit Mechanics

`_emit_file` resolves the path:
1. If absolute, use as-is.
2. Otherwise, resolve relative to `context.cwd`.
3. Create parent directories if missing (`mkdir(parents=True,
   exist_ok=True)`).
4. Write `text` (no framing prefix) using `Path.write_text(encoding="utf-8")`.

Errors (permission denied, disk full, etc.) produce
`EmitResult(ok=False)` and a logger warning; the action does not
fail.

## Data Models

### Pipeline Grammar Additions

```yaml
# New step form:
- summary:
    template: minimal-sdk        # required, string
    model: haiku                 # optional, model alias
    emit:                        # optional, default: [stdout]
      - stdout
      - clipboard
      - file: ./checkpoint.md
      - rotate
    checkpoint: always           # optional, expands step into [summary, checkpoint]

# Existing compact step (unchanged grammar):
- compact:
    template: minimal-sdk
    model: haiku
```

### `EmitDestination` Parsing

YAML `emit:` entries are parsed as follows:

| YAML form | Parsed to |
| --- | --- |
| `stdout` | `EmitDestination(kind="stdout")` |
| `clipboard` | `EmitDestination(kind="clipboard")` |
| `rotate` | `EmitDestination(kind="rotate")` |
| `{file: path}` | `EmitDestination(kind="file", arg="path")` |
| `file: path` (one-key) | same as above |
| anything else | `ValidationError` |

### Action Outputs

`summary` action `ActionResult.outputs`:

```python
{
    "summary": "<captured text>",
    "instructions": "<rendered template>",
    "emit_results": [
        {"destination": "stdout", "ok": True, "detail": ""},
        {"destination": "file:/tmp/ctx.md", "ok": True, "detail": "wrote 4271 bytes"},
        {"destination": "clipboard", "ok": False, "detail": "no clipboard backend"},
        {"destination": "rotate", "ok": True, "detail": "session rotated"},
    ],
    "source_step_index": 3,
    "source_step_name": "summary-mid",
    "summary_model": "claude-haiku-4-5-20251001",
}
```

`compact` action outputs unchanged from slice 158.

## Implementation Outline

### New Files

- `src/squadron/pipeline/emit.py` — `EmitDestination`, `EmitResult`,
  registry, and the four built-in destination functions.
- `src/squadron/pipeline/actions/summary.py` — `SummaryAction` class
  and the shared `_execute_summary()` helper that both the new
  summary action and the refactored compact action call.
- `src/squadron/pipeline/steps/summary.py` — `SummaryStepType` with
  `validate()` and `expand()`. Expand respects the `checkpoint:`
  shorthand by emitting a follow-on checkpoint action.

### Modified Files

- `src/squadron/pipeline/sdk_session.py` —
  - Add `capture_summary(instructions, summary_model)` method that
    generates a summary without rotating.
  - Extend `compact()` with optional `summary: str | None = None`
    parameter; when provided, skip the capture phase and go straight
    to disconnect/reconnect/seed.
- `src/squadron/pipeline/actions/compact.py` — refactor SDK path to
  call `_execute_summary()` with `emit=[rotate]`. Non-SDK path
  unchanged.
- `src/squadron/pipeline/actions/__init__.py` — add
  `ActionType.SUMMARY = "summary"`.
- `src/squadron/pipeline/steps/__init__.py` — add
  `StepTypeName.SUMMARY = "summary"`.
- `src/squadron/pipeline/executor.py` — register the new action and
  step modules in the import-side-effect block at the top of
  `execute_pipeline()`.
- `pyproject.toml` — add `pyperclip` dependency.
- `src/squadron/data/pipelines/test-pipeline.yaml` — add a
  `summary` step (or create a sibling fixture) for smoke testing.

### Test Files

- `tests/pipeline/test_emit.py` — registry, each built-in
  destination, error handling, async wrapping for clipboard.
- `tests/pipeline/steps/test_summary.py` — validate/expand for the
  step type, including checkpoint shorthand expansion.
- `tests/pipeline/actions/test_summary.py` — execute() coverage:
  capture phase, emit dispatch, multi-destination ordering, rotate
  vs. non-rotate, error propagation rules.
- `tests/pipeline/actions/test_compact_alias_compat.py` — ensures
  the refactored compact action still produces the slice-158
  outputs shape and `compact_summaries` still gets recorded.
- `tests/pipeline/test_sdk_session.py` — extend for the new
  `capture_summary()` method and the `summary=` overload of
  `compact()`.

## Integration Points

### Provides

- `SummaryAction` and `SummaryStepType` for pipeline authors.
- `emit` registry for follow-up slices that want new destinations.
- `SDKExecutionSession.capture_summary()` for any future slice that
  wants to summarize without rotating.

### Consumes

- Slice 158: session rotation, compact template loading, framed seed
  helper, `SDKExecutionSession.compact()`.
- Slice 156: state callback, checkpoint action.
- Slice 142: action protocol, step protocol, action context.

### Cross-Slice Effects

- `compact_summaries` in `RunState` is unchanged. Only the compact
  action populates it. The summary action's outputs are not
  persisted to that field by default — they live in the action's
  step result. If a future need arises to also seed from summary
  steps on resume, it's a small change to
  `_maybe_record_compact_summaries()` to also key on
  `action_type == "summary"`.

## Success Criteria

### Functional

1. `- summary: { template: minimal-sdk, model: haiku, emit: [stdout] }`
   produces the summary in stdout when the pipeline runs in SDK mode.
2. `emit: [file: ./out.md]` writes the summary to `./out.md` (resolved
   relative to pipeline cwd) and creates parent directories.
3. `emit: [clipboard]` puts the summary on the OS clipboard via
   `pyperclip`. On a clipboardless environment, the action succeeds
   and the emit_result records `ok: False` with a clear detail.
4. `emit: [rotate]` produces the same observable behavior as today's
   `compact` step: session is rotated, the new session is seeded with
   the framed summary, the prior model is restored.
5. `emit: [stdout, file: ./x.md, clipboard, rotate]` runs all four in
   declared order; the rotate uses the same captured summary as the
   other three (no duplicate summarizer call).
6. A failing non-rotate emit (e.g., file path with no write
   permission) produces a warning, records `ok: False`, and lets the
   remaining emits run. The action returns success.
7. A failing `rotate` emit (e.g., session disconnect error) returns
   `ActionResult(success=False)` and the pipeline halts at that step.
8. `checkpoint: always` on the summary step pauses the pipeline after
   the emit destinations have run.
9. The existing `- compact: { template: ..., model: ... }` step
   continues to work unchanged: same outputs, same
   `compact_summaries` persistence, same session rotation behavior.
10. `emit: [rotate]` in prompt-only mode produces a clear error at
    runtime; the rest of the pipeline does not silently skip the
    rotate.

### Technical

1. `pyperclip` is added as a runtime dependency in `pyproject.toml`
   and is import-clean on macOS, Linux (with xclip/xsel/wl-copy
   present), and Linux without a clipboard backend (the import
   succeeds, the runtime call fails gracefully).
2. The `emit` registry is extensible: a third-party can call
   `register_emit("slack", _emit_slack)` and use it from YAML
   without modifying squadron core. (Demonstrated by a test that
   registers a fake emit destination and exercises it through the
   summary action.)
3. The `_execute_summary()` helper has a single source of truth for
   the capture-then-emit flow; both `SummaryAction.execute()` and
   `CompactAction.execute()` SDK path call it.
4. `SDKExecutionSession.compact(summary=...)` skips the
   capture-summary phase when the parameter is provided. Verified by
   asserting that `client.query` is called once in the rotate
   sequence (only for the seed dispatch), not twice.
5. Pipeline validator (`validate_pipeline`) accepts the new
   `summary` step grammar and rejects malformed `emit` entries with
   a `ValidationError` whose `field` is `"emit"`.

### Integration

1. `sq run test-pipeline 154 -vv` with an updated test-pipeline that
   uses `summary` instead of `compact` for the rotation step
   produces the same end-to-end behavior as the current test
   (rotated session, seeded with summary, post-compact dispatch
   responds with awareness of pre-rotation context).
2. `sq run test-pipeline 154 -vv` with a `summary` step using
   `emit: [stdout, clipboard]` plus `checkpoint: always` pauses the
   pipeline after writing summary to stdout and clipboard. Resuming
   with `sq run --resume <run-id>` continues correctly. (Resume does
   NOT re-emit; the summary already happened.)
3. Existing `compact`-based pipelines (including the current
   test-pipeline shape) continue to work without modification. All
   slice 158 tests still pass.

## Verification Walkthrough

### Demo 1: stdout + file emit, no rotation

```bash
# Edit test-pipeline.yaml to add a summary step:
#   - summary:
#       template: minimal-sdk
#       model: haiku
#       emit:
#         - stdout
#         - file: ./summary-out.md

uv run sq run test-pipeline 154 -vv
```

Expected:
- Logger output shows the summary action firing, the captured
  summary text in stdout, and `wrote N bytes` for the file emit.
- `./summary-out.md` exists and contains the same text that was
  printed to stdout (no framing prefix).
- Pipeline continues to subsequent steps (no rotation, session is
  intact).

### Demo 2: clipboard emit with checkpoint

```bash
# Edit test-pipeline.yaml:
#   - design: { phase: 4, model: haiku, ... }
#   - summary:
#       template: minimal-sdk
#       model: haiku
#       emit: [clipboard, file: ./design-checkpoint.md]
#       checkpoint: always
#   - tasks: { phase: 5, ... }

uv run sq run test-pipeline 154 -vv
# Pipeline runs design, then runs summary action, emits to clipboard
# and file, then checkpoint pauses the run.

pbpaste                                          # macOS
# (or xclip -o on Linux, or check the file)
# -> shows the captured summary text

# Open Claude Code in another window, paste the summary,
# discuss the design, iterate on slice 154 design file.

uv run sq run --resume <run-id>
# Pipeline resumes at the tasks step. The summary action does NOT
# re-fire (it already completed). The tasks step proceeds with the
# original session context intact.
```

### Demo 3: full rotate via summary alias

```bash
# Edit test-pipeline.yaml to use summary with rotate (functionally
# equivalent to compact):
#   - summary:
#       template: minimal-sdk
#       model: haiku
#       emit: [rotate]

uv run sq run test-pipeline 154 -vv
```

Expected: identical behavior to the current `compact` test from
slice 158 — session rotated, framed seed sent to new session,
post-compact dispatch responds with awareness of pre-rotation
context. Outputs are slightly different shape (`emit_results` list
instead of compact's flat fields), but the functional result is
identical.

### Demo 4: existing compact step still works

```bash
# Revert test-pipeline.yaml to current shape with the compact alias:
#   - compact:
#       template: minimal-sdk
#       model: haiku

uv run sq run test-pipeline 154 -vv
```

Expected: byte-identical behavior to slice 158 today. State file's
`compact_summaries` field still gets the entry. The post-compact
dispatch step still reads the summary correctly. No regression.

### Demo 5: emit failure isolation

```bash
# emit a file to a path that doesn't exist and can't be created:
#   - summary:
#       template: minimal-sdk
#       model: haiku
#       emit:
#         - stdout
#         - file: /nonexistent/dir/with/no/perms/x.md
#         - clipboard

uv run sq run test-pipeline 154 -vv
```

Expected: stdout emit succeeds, file emit logs a warning and records
`ok: False`, clipboard emit succeeds. The summary action returns
`success=True` overall. Pipeline continues.

## Risks

- **`pyperclip` install footprint**: small pure-Python lib, but adds a
  runtime dependency. Mitigation: the dependency is unconditional but
  lightweight; clipboard runtime errors are caught and reported per
  emit, not raised. Verified at install time on the project's
  supported platforms.

- **Refactoring `compact()` for the `summary=` overload**: the slice
  158 method does both phases in one. Splitting it requires care to
  not break the existing compact action. Mitigation: comprehensive
  test coverage in slice 158 already exists; we add a parameterized
  test that exercises both paths (with and without the `summary`
  arg).

- **Per-destination async serialization**: emits run sequentially.
  If a destination is slow (e.g., a hypothetical webhook destination
  in a follow-up slice), it blocks subsequent emits. For the four
  built-in destinations this is not a concern. Filed as a non-issue
  for now; revisit if/when we add network destinations.

## Open Questions

1. **Should the summary action also persist its summary to
   `compact_summaries` for resume seeding?** Argument for: a paused
   pipeline that resumes after a summary step would benefit from the
   same seed-on-resume behavior compact gets. Argument against: the
   summary step's primary purpose is *export*, not session
   management. If the user also wants resume seeding they can use
   `compact` (or `emit: [..., rotate]` plus their other emits).
   **Recommendation**: do NOT persist in 161. If demand emerges,
   add a `seed_on_resume: true` flag in a follow-up. Documented in
   Out of Scope and as a follow-up finding.

2. **Pipeline-load-time warning for `emit: [rotate]` outside SDK
   mode**: today the validator surface returns
   `list[ValidationError]`. Adding a warning channel is a one-line
   model change but touches every consumer. **Recommendation**:
   skip the load-time warning in 161, rely on the runtime error.
   File a follow-up to add a warnings channel to validators when
   another use case justifies it.

## Effort

2/5. Most of the work is wiring (new step type, new action, new
emit module, registry, dependency, tests). The summary-capture
mechanism already exists in slice 158; we extract a helper rather
than build something new. The compact alias refactor is small
(thin wrapper around the shared helper). The biggest piece of new
code is the emit registry and its four built-in destinations,
which are each ~10–20 lines.

## Risk

Low. Builds on slice 158's mature session-rotate machinery, no
new external SDK surface area, no schema changes, no new state
file format, fully backward-compatible with existing `compact`
pipelines.

## Dependencies

- **158 (SDK Session Management and Compaction)** — required.
  Provides `SDKExecutionSession.compact()`,
  `frame_summary_for_seed()`, the compact template loader, and the
  `compact_summaries` persistence mechanism that the alias must
  preserve.
- **156 (Pipeline Executor Hardening)** — required for the state
  callback path that compact uses for `compact_summaries`
  persistence (preserved by the alias).
- **152 (Pipeline Documentation)** — interface only. The pipeline
  authoring guide will gain a "Summary step" section after this
  slice ships.

## Notes

- `compact` becomes a "syntactic sugar" alias internally, but it
  remains a first-class step type at the YAML grammar level.
  Pipeline authors should not be forced to learn about `summary`
  if they only want session rotation; the documentation should
  present `compact` first ("the simple case") and `summary` as
  the more general form.
- `rotate` is the only emit destination that mutates session
  state. All others are pure I/O. If we later add destinations
  with side effects (e.g., a `state:` destination that writes to
  the run state file), document them carefully.
- The verification walkthrough demos assume haiku for the summary
  model. Pipelines that don't specify `model:` will use the
  pipeline-level model resolution cascade (CLI override → step →
  pipeline → system config), unchanged from slice 158.
