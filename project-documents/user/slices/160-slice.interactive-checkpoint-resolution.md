---
docType: slice-design
slice: interactive-checkpoint-resolution
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [156-pipeline-executor-hardening]
interfaces: []
dateCreated: 20260411
dateUpdated: 20260411
dateReviewed: 20260411
status: in_progress
---

# Slice Design: Interactive Checkpoint Resolution

## Overview

Checkpoints currently have one behavior when triggered: pause the pipeline,
persist state, and exit. The user must then run `sq run --resume <run-id>` from
a fresh terminal session. This full disconnect/persist/exit/resume cycle is
expensive — the SDK session is lost, context must be re-assembled, and the user
context-switches back to the terminal to restart.

Slice 160 replaces that single exit path with an in-terminal interactive menu
offering three choices:

1. **Accept** — extract the prior review findings as instructions and continue
   the pipeline in-process.
2. **Override** — enter custom instructions at the prompt and continue in-process.
3. **Exit** — persist state and exit (current behavior, unchanged).

Accept and Override both keep the SDK session live and inject instructions into
the pipeline params so the next dispatch action picks them up. The prompt-only
checkpoint instruction is also enhanced to describe all three options clearly.

## Value

- **Reduces friction.** The common case — "review found a few concerns, let me
  continue with them in mind" — no longer requires exit + resume. The user stays
  in the running pipeline.
- **Preserves SDK session context.** The live session has the full conversation
  history from all prior steps. Exiting throws that away. Staying live means the
  next dispatch inherits that context automatically.
- **Enables guided forward progress.** Override lets the user inject domain
  knowledge ("keep the design under 100 lines") without reformulating a full
  resume invocation.
- **No architecture change.** The action protocol, state model, and executor loop
  are unchanged. This is a narrow addition to the executor's checkpoint handling
  path.

## Technical Scope

**In scope:**
- Interactive menu in SDK execution mode (terminal I/O via stdin/stdout)
- Enhanced checkpoint instruction text in prompt-only mode
- `override_instructions` key injected into `merged_params` on Accept/Override
- Dispatch action picks up `override_instructions` from params
- Exit path unchanged

**Out of scope:**
- Re-running the current step's dispatch within the same checkpoint invocation
  (that is what the loop mechanism is for)
- GUI or notification-based checkpoint UI
- Checkpoint history or audit log

## Dependencies

### Prerequisites

- **Slice 156 (Pipeline Executor Hardening)** — the checkpoint interactive handler
  reads the run_id from the executor context to display the correct resume command.
  `ExecutionMode` itself is not directly referenced; interactive gating is handled
  by `_is_interactive()` (stdin.isatty + `SQUADRON_NO_INTERACTIVE`).
- All prior pipeline slices (executor, state, SDK session) are operational.

### Interfaces Required

- `ActionResult.findings` — list of finding dicts (set by review action, slice 143).
  Each dict: `{"id": ..., "severity": ..., "category": ..., "summary": ..., "location": ...}`.
- `ActionResult.verdict` — string verdict from review action.
- `merged_params` dict in `execute_pipeline` — carries pipeline-scoped params
  across all steps and actions.

## Architecture

### Component Structure

The change is confined to three files:

| File | Change |
|------|--------|
| `executor.py` | Add `CheckpointResolution`, `CheckpointDecision`, `_prompt_checkpoint_interactive()`. Modify `_execute_step_once` to call the handler when checkpoint fires. |
| `actions/dispatch.py` | Prepend `override_instructions` to assembled context if present in params. |
| `prompt_renderer.py` | Enhance `_render_checkpoint` to describe the three options. |

### Data Flow

**SDK mode — Accept or Override:**

```
_execute_step_once iterates actions:
  ...
  [review] → ActionResult(verdict=CONCERNS, findings=[...])
  [checkpoint] → ActionResult(outputs={"checkpoint": "paused"})
      executor detects "paused" →
          _prompt_checkpoint_interactive(verdict, findings, run_id) →
              prints menu to stdout, reads stdin →
              returns CheckpointDecision(ACCEPT, override_instructions="...")
      merged_params["override_instructions"] = "..."
      continue loop (checkpoint does NOT return PAUSED to caller)
  [commit] → runs normally
next step:
  [dispatch] → reads override_instructions from params,
               prepends as "Instructions from checkpoint" block
               in assembled context
```

**SDK mode — Exit:**

```
  [checkpoint] → ActionResult(outputs={"checkpoint": "paused"})
      executor detects "paused" →
          _prompt_checkpoint_interactive(...) →
              returns CheckpointDecision(EXIT, override_instructions=None)
      return StepResult(status=PAUSED)  ← current behavior
pipeline exits, state is saved
```

**Prompt-only mode:**

No runtime change. The checkpoint `ActionInstruction` is enhanced to describe
all three options in its `instruction` field so the human operator knows what
to do at a checkpoint.

### Override Instructions Propagation

`override_instructions` is set in `merged_params` at the point of checkpoint
resolution. It persists across all subsequent actions and steps for the lifetime
of the run:

- If the user Accept/Overrides at the design checkpoint, those instructions
  flow into the implement step's dispatch (desirable — the instructions remain
  relevant context).
- If a second checkpoint fires and the user again chooses Accept/Override, the
  new instructions replace the old ones in `merged_params`.
- Exit never modifies `override_instructions`.
- The value is not persisted to `RunState`; on resume from Exit the instructions
  are absent (the user provides fresh context at the next interaction point).

## Technical Decisions

### Interaction at the Executor Layer, Not the Action Layer

The checkpoint action returns `outputs["checkpoint"] = "paused"` — a data signal.
The executor already detects this at `_execute_step_once:670`. Adding interaction
here is a clean, minimal hook: the executor has the run context (run_id for the
resume command), the step_prior dict (for extracting review findings), and
control over whether to return PAUSED or continue. Moving the I/O into the action
would require passing stdin/stdout through `ActionContext`, violating the action's
stateless nature.

### Continue In-Place, Don't Re-Run the Current Step

Accept/Override allows actions **after** the checkpoint in the current step
(typically just `commit`) to run normally and then advances to the next step
with `override_instructions` in params. The next dispatch picks up the
instructions.

Re-running the current step's dispatch from within the checkpoint handler would
require a "restart action sequence from index N" mechanism, higher complexity,
and risks infinite loops without an explicit max. The loop mechanism (`loop.max`,
`loop.until`) is the designed vehicle for iteration. This slice is about reducing
the cost of a one-time human decision, not replacing loops.

### Suggestion Text Extracted from `ActionResult.findings`

When the user chooses Accept, the suggestion text is assembled from the most
recent `ActionResult` in `action_results` (the results collected so far in the
current step's action sequence) that has a non-None `verdict`, retrieved via the
existing `_last_with_verdict(action_results)` helper. Finding
dicts are formatted as:

```
[severity] summary
           location
```

If `findings` is empty (the review action produced a prose-only verdict), a
fallback message indicates the verdict without structured detail and the user
is encouraged to choose Override with explicit text.

### Override Instructions Key in `merged_params`

The dispatch action reads `params.get("override_instructions")` and, if present,
prepends a clearly delimited block to the assembled context before dispatch:

```
--- Instructions from checkpoint resolution ---
{override_instructions}
--- End instructions ---
```

This is an explicit, visible injection — not hidden in CF context. The delimiters
ensure the model treats it as a directive, not as part of the artifact content.

### No Change to `RunState` Schema

`override_instructions` lives in in-memory `merged_params` only. On Exit, the
state file captures the paused position but not the instructions (they were
never applied). On resume, merged_params is re-initialized from the pipeline
definition defaults and the caller's params — the user provides fresh instructions
at the next checkpoint.

This avoids a schema version bump and keeps the state file as a structural
position record, not a full execution snapshot.

## Implementation Details

### New Types in `executor.py`

```python
class CheckpointResolution(StrEnum):
    ACCEPT = "accept"
    OVERRIDE = "override"
    EXIT = "exit"

@dataclass
class CheckpointDecision:
    resolution: CheckpointResolution
    override_instructions: str | None  # None when resolution is EXIT
```

### `_prompt_checkpoint_interactive` Signature

```python
def _prompt_checkpoint_interactive(
    verdict: str | None,
    findings: list[dict[str, object]],
    run_id: str,
    step_name: str,
) -> CheckpointDecision:
    ...
```

Reads from `sys.stdin`, writes to `sys.stdout`. Non-interactive environments
(piped stdin, `SQUADRON_NO_INTERACTIVE` env var set) default to EXIT and log a
warning. This prevents hangs in CI or non-terminal contexts.

### Display Format (SDK terminal)

```
──────────────────────────────────────────────────────────
Checkpoint — step 'design' │ Review: CONCERNS
──────────────────────────────────────────────────────────
Findings:
  [concern] Missing error handling in parse_config
            src/squadron/pipeline/executor.py:45
  [note]    Variable name 'x' is unclear
            src/squadron/pipeline/actions/dispatch.py:12

Options:
  [a] Accept   — continue; findings above become override instructions
  [o] Override — enter custom instructions, then continue
  [e] Exit     — save state; resume: sq run --resume abc123
──────────────────────────────────────────────────────────
Choice [a/o/e]:
```

On choice `o`, a follow-up prompt reads the user's instructions (single-line
entry, terminated by Enter):

```
Instructions: _
```

### Modification to `_execute_step_once` in `executor.py`

The existing checkpoint detection at line 670:

```python
if result.outputs.get("checkpoint") == "paused":
    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=ExecutionStatus.PAUSED,
        action_results=action_results,
        iteration=iteration,
    )
```

Becomes:

```python
if result.outputs.get("checkpoint") == "paused":
    # Findings come from the review action, not the checkpoint action.
    # The checkpoint action only sets outputs["checkpoint"] = "paused";
    # its verdict and findings fields are None/[]. Use _last_with_verdict
    # to pull the review result from earlier in this step's action_results.
    prior_review = _last_with_verdict(action_results)
    verdict = prior_review.verdict if prior_review else None
    findings = [f for f in (prior_review.findings or []) if isinstance(f, dict)] if prior_review else []
    decision = _prompt_checkpoint_interactive(
        verdict, findings, run_id, step.name
    )
    if decision.resolution == CheckpointResolution.EXIT:
        return StepResult(
            step_name=step.name,
            step_type=step.step_type,
            status=ExecutionStatus.PAUSED,
            action_results=action_results,
            iteration=iteration,
        )
    # Accept or Override: inject instructions and continue
    if decision.override_instructions:
        merged_params["override_instructions"] = decision.override_instructions
    # Loop continues to next action (typically commit)
```

### Modification to `actions/dispatch.py`

In the dispatch action's `execute` method, before assembling the context message:

```python
override = str(context.params.get("override_instructions", "")).strip()
if override:
    prefix = (
        f"--- Instructions from checkpoint resolution ---\n"
        f"{override}\n"
        f"--- End instructions ---\n\n"
    )
else:
    prefix = ""
# prepend `prefix` to the assembled context string
```

### `_render_checkpoint` in `prompt_renderer.py`

The current instruction text (`"Pause if review verdict is CONCERNS or worse"`)
is replaced with a structured description of the three options. Example for
`on-concerns`:

```
If review verdict is CONCERNS or FAIL:
  [a] Accept   — proceed; review findings become instructions for next dispatch
  [o] Override — enter custom instructions; proceed with those
  [e] Exit     — stop pipeline; resume with: sq run --resume {run_id}
Note: in prompt-only mode, you are the executor. Choose an option and act accordingly.
```

`ActionInstruction.instruction` carries this text. The `trigger` field remains
for machine consumers.

### Non-Interactive Guard

```python
import os, sys

def _is_interactive() -> bool:
    return sys.stdin.isatty() and not os.environ.get("SQUADRON_NO_INTERACTIVE")
```

If not interactive, `_prompt_checkpoint_interactive` returns
`CheckpointDecision(CheckpointResolution.EXIT, None)` and logs:
```
checkpoint: non-interactive environment; defaulting to exit (set SQUADRON_NO_INTERACTIVE=0 to suppress)
```

## Integration Points

### Provides to Other Slices

- `CheckpointResolution` and `CheckpointDecision` are exported from `executor.py`
  for use by any future checkpoint-adjacent features (e.g. notification hooks,
  convergence loops in 180).
- `SQUADRON_NO_INTERACTIVE` env var establishes the non-interactive override
  pattern for CI use.

### Consumes from Other Slices

- `ActionResult.findings` from the review action (slice 143).
- `RunState` run_id from the state manager (slice 150/156) — used to construct
  the resume command displayed in the Exit option.
- `SDKExecutionSession` in `ActionContext` — not modified, but its liveness is
  the motivation for Accept/Override.

## Success Criteria

### Functional Requirements

- When a checkpoint fires in SDK mode, the interactive menu is displayed with
  verdict, findings (if any), and resume command.
- Choosing Accept extracts the finding summaries as `override_instructions` in
  params and continues the pipeline (commit runs, next step begins).
- Choosing Override reads user text and sets it as `override_instructions`; pipeline
  continues identically to Accept.
- Choosing Exit returns `PAUSED` status — identical behavior to pre-slice 160.
- The next dispatch action in the pipeline prepends `override_instructions` to
  its assembled context when the key is present in params.
- In a non-interactive environment (`sys.stdin.isatty() == False` or
  `SQUADRON_NO_INTERACTIVE` set), the handler defaults to Exit with a warning log.
- Prompt-only checkpoint instruction describes all three options explicitly.

### Technical Requirements

- `_prompt_checkpoint_interactive` is unit-testable with mocked stdin/stdout.
- `CheckpointResolution` and `CheckpointDecision` are exported from `executor.py`.
- No change to `RunState` schema version.
- `override_instructions` key does not appear in committed state files.
- `ruff format` passes before commit.

### Verification Walkthrough

**Setup:** A pipeline with a review step and `checkpoint: on-concerns` on a step
known to produce a CONCERNS verdict (use `review-only` on a file with mild issues).

**Step 1 — Trigger a checkpoint in SDK mode:**
```bash
sq run review-only --slice 160 --model sonnet
```
Expect: the pipeline pauses, the interactive menu appears with the review verdict
and any extracted findings.

**Step 2 — Test the Accept path:**
At the prompt, enter `a`. Expect:
- Pipeline continues past the checkpoint.
- Commit action runs.
- Next step (if any) runs; its dispatch prepends the findings block.
- Pipeline completes (or reaches the next natural checkpoint).
- No state file with `status: paused` remains (unless a second checkpoint exits).

**Step 3 — Test the Override path:**
Re-run. At the prompt, enter `o`. Expect the follow-up prompt. Enter some text.
Expect the same continuation behavior as Accept.

**Step 4 — Test the Exit path:**
Re-run. At the prompt, enter `e`. Expect:
- `StepResult(status=PAUSED)` returned.
- `sq run --status` shows the paused run.
- `sq run --resume <run-id>` resumes from the correct step.

**Step 5 — Verify non-interactive guard:**
```bash
echo "" | sq run review-only --slice 160   # piped stdin
# OR
SQUADRON_NO_INTERACTIVE=1 sq run review-only --slice 160
```
Expect: pipeline exits (same as choosing e) with a logged warning, no hang.

**Step 6 — Verify prompt-only output:**
```bash
sq run review-only --slice 160 --prompt-only --next
```
Expect: checkpoint `ActionInstruction.instruction` includes description of
the three options.

## Implementation Notes

### Development Approach

1. Add `CheckpointResolution`, `CheckpointDecision`, and `_prompt_checkpoint_interactive`
   to `executor.py`. Write unit tests with `monkeypatch` on stdin/stdout.
2. Modify `_execute_step_once` checkpoint detection block.
3. Add override instructions prepend to `actions/dispatch.py`. Unit test that
   the prefix appears in the assembled context when the param is set.
4. Update `_render_checkpoint` in `prompt_renderer.py`. Update existing
   prompt-renderer tests.
5. Run the full integration test suite (`pytest tests/`) — the Exit path must
   remain identical to pre-160 behavior.

### Special Considerations

- **Multi-line override input:** The initial implementation accepts a single line
  (terminated by Enter). Multi-line entry (e.g. via a `$EDITOR` subprocess) is a
  future enhancement — the single-line case covers the common "fix this one thing"
  directive and keeps the UX simple.
- **Windows compatibility:** `sys.stdin.isatty()` behaves correctly on Windows
  with ConPTY. No special handling required.
- **Finding truncation:** If there are more than 10 findings, display the first 10
  and add `"... and N more (see review file)"` to keep the display readable.
