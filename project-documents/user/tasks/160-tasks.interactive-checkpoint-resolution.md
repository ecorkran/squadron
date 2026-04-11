---
docType: tasks
slice: interactive-checkpoint-resolution
project: squadron
parent: 160-slice.interactive-checkpoint-resolution.md
dependencies: [156-pipeline-executor-hardening]
projectState: All 140-band slices complete except 160. SDK pipeline executor, session management, and compaction are operational. RunState is schema v3. Checkpoint action fires correctly and returns outputs["checkpoint"] = "paused"; executor detects this at _execute_step_once line ~670 and returns StepResult(status=PAUSED). _last_with_verdict() helper exists in executor.py. Review action populates ActionResult.verdict and ActionResult.findings.
dateCreated: 20260411
dateUpdated: 20260411
status: not_started
---

# Tasks: Interactive Checkpoint Resolution

## Context Summary

- Working on slice 160 (Interactive Checkpoint Resolution)
- Replaces pause-and-exit checkpoint behavior with an in-terminal interactive menu
- Three choices: Accept (use review findings as override instructions), Override (enter custom text), Exit (current behavior)
- Accept and Override keep the SDK session live and inject `override_instructions` into `merged_params`
- Non-interactive environments (piped stdin, `SQUADRON_NO_INTERACTIVE`) default silently to Exit
- Prompt-only mode: no runtime change — only the checkpoint `ActionInstruction` text is enhanced
- No `RunState` schema change — `override_instructions` is in-memory only

**Files to change:**
- `src/squadron/pipeline/executor.py` — add `CheckpointResolution`, `CheckpointDecision`, `_is_interactive()`, `_prompt_checkpoint_interactive()`; modify checkpoint detection block in `_execute_step_once`
- `src/squadron/pipeline/actions/dispatch.py` — read `override_instructions` from `context.params`; prepend delimited block to assembled context when present
- `src/squadron/pipeline/prompt_renderer.py` — enhance `_render_checkpoint` to describe all three options

---

## Tasks

### 1. New types and helpers in `executor.py`

- [ ] **1.1** Add `CheckpointResolution(StrEnum)` with values `ACCEPT`, `OVERRIDE`, `EXIT` in `executor.py`. Place after existing enums near the top of the file.
  - Success: `from squadron.pipeline.executor import CheckpointResolution` works; enum members accessible as `CheckpointResolution.ACCEPT` etc.

- [ ] **1.2** Add `CheckpointDecision` dataclass in `executor.py`:
  ```python
  @dataclass
  class CheckpointDecision:
      resolution: CheckpointResolution
      override_instructions: str | None  # None when resolution is EXIT
  ```
  - Success: constructible; `CheckpointDecision(CheckpointResolution.EXIT, None)` works.

- [ ] **1.3** Add `_is_interactive() -> bool` function:
  ```python
  def _is_interactive() -> bool:
      return sys.stdin.isatty() and not os.environ.get("SQUADRON_NO_INTERACTIVE")
  ```
  Add `import os` if not already present.
  - Success: returns `False` when `SQUADRON_NO_INTERACTIVE` is set; returns `True` in a normal terminal.

- [ ] **1.4** Test `_is_interactive()`:
  - `SQUADRON_NO_INTERACTIVE=1` → returns `False`
  - `sys.stdin` monkeypatched to non-tty → returns `False`
  - Both absent → returns `True` (requires tty mock)

### 2. `_prompt_checkpoint_interactive` function

- [ ] **2.1** Implement `_prompt_checkpoint_interactive(verdict, findings, run_id, step_name) -> CheckpointDecision`:
  - If not `_is_interactive()`: log warning `"checkpoint: non-interactive environment; defaulting to exit"` and return `CheckpointDecision(CheckpointResolution.EXIT, None)`.
  - Print the display block to stdout:
    ```
    ──────────────────────────────────────────────────────────
    Checkpoint — step '{step_name}' │ Review: {verdict or 'N/A'}
    ──────────────────────────────────────────────────────────
    Findings:
      [severity] summary
                 location        (omit location line if absent)
    ... and N more (see review file)   (if > 10 findings)

    Options:
      [a] Accept   — continue; findings above become override instructions
      [o] Override — enter custom instructions, then continue
      [e] Exit     — save state; resume: sq run --resume {run_id}
    ──────────────────────────────────────────────────────────
    Choice [a/o/e]:
    ```
  - If `findings` is empty: replace the Findings block with `"No structured findings. Choose Override to provide explicit instructions."`
  - Read one character from stdin. Loop on invalid input.
  - On `a`: format findings as override_instructions string (one line per finding: `[severity] summary — location`), return `CheckpointDecision(ACCEPT, override_instructions)`.
  - On `o`: print `"Instructions: "`, read a line from stdin, return `CheckpointDecision(OVERRIDE, user_text.strip())`.
  - On `e`: return `CheckpointDecision(EXIT, None)`.
  - Truncate findings display to 10 items; include "… and N more" line if truncated.

- [ ] **2.2** Test `_prompt_checkpoint_interactive` — non-interactive path:
  - With `SQUADRON_NO_INTERACTIVE=1`: returns `CheckpointDecision(EXIT, None)` without printing.

- [ ] **2.3** Test `_prompt_checkpoint_interactive` — Accept path:
  - Monkeypatch stdin to yield `"a\n"`, tty=True.
  - Pass two findings dicts. Confirm returned `override_instructions` contains both formatted findings.

- [ ] **2.4** Test `_prompt_checkpoint_interactive` — Override path:
  - Monkeypatch stdin to yield `"o\n"` then `"keep it under 50 lines\n"`.
  - Confirm returned `override_instructions == "keep it under 50 lines"`.

- [ ] **2.5** Test `_prompt_checkpoint_interactive` — Exit path:
  - Monkeypatch stdin to yield `"e\n"`. Confirm `resolution == EXIT`.

- [ ] **2.6** Test `_prompt_checkpoint_interactive` — invalid input recovery:
  - Monkeypatch stdin to yield `"x\n"` then `"a\n"`. Confirm function retries and returns Accept.

- [ ] **2.7** Test `_prompt_checkpoint_interactive` — finding truncation:
  - Pass 12 findings. Confirm only 10 displayed and "… and 2 more" appears in output.

### 3. Modify checkpoint detection in `_execute_step_once`

- [ ] **3.1** In `_execute_step_once`, replace the checkpoint detection block (at the point where `result.outputs.get("checkpoint") == "paused"` is detected) with:
  ```python
  if result.outputs.get("checkpoint") == "paused":
      prior_review = _last_with_verdict(action_results)
      verdict = prior_review.verdict if prior_review else None
      findings = [f for f in (prior_review.findings or []) if isinstance(f, dict)] if prior_review else []
      decision = _prompt_checkpoint_interactive(verdict, findings, run_id, step.name)
      if decision.resolution == CheckpointResolution.EXIT:
          return StepResult(
              step_name=step.name,
              step_type=step.step_type,
              status=ExecutionStatus.PAUSED,
              action_results=action_results,
              iteration=iteration,
          )
      if decision.override_instructions:
          merged_params["override_instructions"] = decision.override_instructions
      # Accept/Override: loop continues to next action
  ```
  Confirm `run_id` and `merged_params` are in scope at the call site.

- [ ] **3.2** Test executor checkpoint detection — Exit path:
  - Mock `_prompt_checkpoint_interactive` to return `CheckpointDecision(EXIT, None)`.
  - Confirm `_execute_step_once` returns `StepResult(status=PAUSED)` — identical to pre-160 behavior.

- [ ] **3.3** Test executor checkpoint detection — Accept path:
  - Mock `_prompt_checkpoint_interactive` to return `CheckpointDecision(ACCEPT, "fix error handling")`.
  - Confirm `merged_params["override_instructions"] == "fix error handling"`.
  - Confirm execution does NOT return `PAUSED` — continues to next action.

- [ ] **3.4** Test executor checkpoint detection — Override path:
  - Mock returns `CheckpointDecision(OVERRIDE, "keep under 50 lines")`.
  - Confirm `merged_params["override_instructions"] == "keep under 50 lines"` and execution continues.

- [ ] **3.5** Test `override_instructions` replacement on second checkpoint:
  - First checkpoint: Accept with `"fix A"` → `merged_params["override_instructions"] == "fix A"`.
  - Second checkpoint: Override with `"fix B"` → `merged_params["override_instructions"] == "fix B"` (old value replaced).

### 4. `override_instructions` injection in `actions/dispatch.py`

- [ ] **4.1** In the dispatch action's `execute` method, before assembling the context message, read and prepend `override_instructions`:
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
  ```
  Prepend `prefix` to the assembled context string sent to the model.

- [ ] **4.2** Test dispatch override injection — present:
  - `context.params["override_instructions"] = "do X"`. Confirm assembled context starts with the delimited block.

- [ ] **4.3** Test dispatch override injection — absent:
  - `context.params` has no `override_instructions` key. Confirm assembled context is unchanged (no prefix, no empty block).

- [ ] **4.4** Test dispatch override injection — empty string:
  - `context.params["override_instructions"] = ""`. Confirm no prefix is added (`.strip()` guard).

### 5. Enhance `_render_checkpoint` in `prompt_renderer.py`

- [ ] **5.1** In `prompt_renderer.py`, update `_render_checkpoint` so `ActionInstruction.instruction` describes all three options. For trigger `on-concerns`:
  ```
  If review verdict is CONCERNS or FAIL:
    [a] Accept   — proceed; review findings become instructions for next dispatch
    [o] Override — enter custom instructions; proceed with those
    [e] Exit     — stop pipeline; resume with: sq run --resume {run_id}
  Note: in prompt-only mode, you are the executor. Choose an option and act accordingly.
  ```
  For `on-fail`, change the condition line to `"If review verdict is FAIL:"`. For `always`, remove the condition line. For `never`, keep existing "skip" text.

- [ ] **5.2** Test `_render_checkpoint` — `on-concerns`:
  - Confirm instruction contains `"CONCERNS or FAIL"` and all three option labels.

- [ ] **5.3** Test `_render_checkpoint` — `on-fail`:
  - Confirm instruction contains `"FAIL"` but not `"CONCERNS"`.

- [ ] **5.4** Test `_render_checkpoint` — `always`:
  - Confirm no conditional clause; all three options present.

- [ ] **5.5** Test `_render_checkpoint` — `never`:
  - Confirm instruction indicates skip/no-pause (existing behavior unchanged).

### 6. Export and final validation

- [ ] **6.1** Export `CheckpointResolution` and `CheckpointDecision` from `executor.py`'s public surface (add to `__all__` if it exists, or confirm they are importable from the module).

- [ ] **6.2** Run full test suite: `pytest tests/ -x -q`. All tests must pass. The Exit path must behave identically to pre-160 in integration tests that exercise checkpoints.

- [ ] **6.3** Run `ruff format src/ tests/` and `pyright src/`. No errors.

- [ ] **6.4** Verify `override_instructions` does not appear in any committed `RunState` JSON files (state schema version unchanged at 3).

- [ ] **6.5** Update slice status to `in_progress` in [160-slice.interactive-checkpoint-resolution.md](../slices/160-slice.interactive-checkpoint-resolution.md) at implementation start; to `complete` when all tasks pass.
