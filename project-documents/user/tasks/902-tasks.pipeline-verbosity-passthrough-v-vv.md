---
docType: tasks
slice: pipeline-verbosity-passthrough-v-vv
project: squadron
lld: user/slices/902-slice.pipeline-verbosity-passthrough-v-vv.md
dependencies: []
projectState: Slice 901 complete (diff injection + UNKNOWN-fails-closed). Branch 902-pipeline-verbosity-passthrough.
dateCreated: 20260426
dateUpdated: 20260426
status: complete
---

## Context Summary

- Fixes [issue #9](https://github.com/ecorkran/squadron/issues/9): pipeline review commands hard-code `-v`, and `/sq:run` swallows trailing flags into the target string.
- Two coordinated changes: (1) thread `verbosity` param through `render_step_instructions` → `_render_review`, replacing the hard-coded `-v` at `prompt_renderer.py:174`; (2) update `/sq:run` slash command to peel `-v`/`-vv`/`--verbose` from `$ARGUMENTS`.
- Default review verbosity changes from implicit `-v` to silent (0). This is intentional.
- Scope is prompt-only path only. Executor-path (`ActionContext`) threading is excluded.
- Files touched: `prompt_renderer.py`, `run.py`, `commands/sq/run.md`, `tests/pipeline/test_prompt_renderer.py`.
- No new dependencies. Effort: 1/5.

---

## Tasks

- [x] **T1. Add `verbosity` parameter to `_render_review`**
  - File: `src/squadron/pipeline/prompt_renderer.py`
  - Add `verbosity: int = 0` as a keyword-only argument to `_render_review` (after `resolver`).
  - Replace the hard-coded `cmd_parts.append("-v")` at line 174 with:
    - If `verbosity == 1`: append `"-v"`
    - Elif `verbosity >= 2`: append `"-vv"`
    - Else: append nothing
  - Success: `_render_review({...}, {...}, resolver, verbosity=0)` builds a command with no `-v`/`-vv`; `verbosity=1` appends `-v`; `verbosity=2` appends `-vv`.

- [x] **T2. Update test: existing `_render_review` assertion**
  - File: `tests/pipeline/test_prompt_renderer.py`
  - `TestRenderReview.test_includes_template_and_model` (line 172) currently asserts `result.command == "sq review slice 152 --model glm5 -v"`.
  - Update that assertion to expect no trailing `-v`: `result.command == "sq review slice 152 --model glm5"`.
  - Run `uv run pytest tests/pipeline/test_prompt_renderer.py::TestRenderReview -v` — must pass.

- [x] **T3. Add parametrized verbosity tests for `_render_review`**
  - File: `tests/pipeline/test_prompt_renderer.py`
  - Add a new parametrized test class or method `TestRenderReviewVerbosity` covering three cases:
    1. `verbosity=0` → command does not contain `-v` or `-vv` (check `"-v" not in cmd.split()`)
    2. `verbosity=1` → command ends with `"-v"` (check `cmd.endswith("-v")`)
    3. `verbosity=2` → command ends with `"-vv"` (check `cmd.endswith("-vv")`)
  - Run `uv run pytest tests/pipeline/test_prompt_renderer.py -v` — all 3 new cases plus existing must pass.

- [x] **T4. Forward `verbosity` through `_build_action_instruction`**
  - File: `src/squadron/pipeline/prompt_renderer.py`
  - `_build_action_instruction` dispatches to action-type builders including `_render_review`.
  - Add `verbosity: int = 0` keyword argument to `_build_action_instruction`.
  - At the call site where `_render_review` is invoked inside `_build_action_instruction`, pass `verbosity=verbosity`.
  - Success: calling `_build_action_instruction(ActionType.REVIEW, config, params, resolver, verbosity=2)` produces a command ending with `-vv`.

- [x] **T5. Add `verbosity` parameter to `render_step_instructions`**
  - File: `src/squadron/pipeline/prompt_renderer.py`
  - Add `verbosity: int = 0` as a keyword-only argument to `render_step_instructions` (alongside `run_id`).
  - Pass `verbosity=verbosity` through to each `_build_action_instruction` call in the loop body.
  - Success: `render_step_instructions(..., verbosity=2)` results in review action commands ending with `-vv`.

- [x] **T6. Thread `verbose` into `_handle_prompt_only_init`**
  - File: `src/squadron/cli/commands/run.py`
  - Add `verbosity: int = 0` parameter to `_handle_prompt_only_init` (line 346).
  - At the call site of `render_step_instructions` (line 389), add `verbosity=verbosity`.
  - At the call site of `_handle_prompt_only_init` in the main command handler, pass the `verbose` count from the typer option.
  - Success: when `sq run slice 152 -v --prompt-only` is invoked, the generated JSON contains review commands ending with `-v`.

- [x] **T7. Thread `verbose` into `_handle_prompt_only_next`**
  - File: `src/squadron/cli/commands/run.py`
  - Add `verbosity: int = 0` parameter to `_handle_prompt_only_next` (line 400).
  - At the call site of `render_step_instructions` (line 478), add `verbosity=verbosity`.
  - At the call site of `_handle_prompt_only_next` in the main command handler, pass the `verbose` count.
  - Success: `sq run --prompt-only --next --resume <run-id> -vv` generates review commands ending with `-vv` for subsequent steps.

- [x] **T8. Commit: prompt_renderer + run.py changes**
  - Run `uv run ruff format src/squadron/pipeline/prompt_renderer.py src/squadron/cli/commands/run.py`.
  - Run full gate: `uv run pytest -q && uv run ruff check && uv run pyright`.
  - All must pass before committing.
  - Commit with message: `fix(pipeline): thread verbosity through render_step_instructions`
  - Success: commit exists on branch, all gates green.

- [x] **T9. Update `/sq:run` slash command — input parsing section**
  - File: `commands/sq/run.md`
  - In the "Input parsing" section, add instructions to scan `$ARGUMENTS` for known verbosity tokens (`-v`, `-vv`, `--verbose`) at the end of the argument string, capture them as `<verbose_flags>`, and remove them from the remainder before splitting `pipeline` and `target`.
  - Update the usage line to: `/sq:run <pipeline> [target] [-v|-vv]  — run a pipeline (e.g., /sq:run slice 152 -v)`
  - Success: the section clearly and unambiguously instructs the LLM on the three-step peel: scan → capture → remove.

- [x] **T10. Update `/sq:run` slash command — Step 0 command template**
  - File: `commands/sq/run.md`
  - In "Step 0: Validate and Initialize", update the `sq run` invocation to include `<verbose_flags>` between `<target>` and `--prompt-only`:
    `sq run <pipeline> <target> <verbose_flags> --prompt-only`
  - Success: Step 0 template shows flags placement; a no-flag invocation omits `<verbose_flags>` (empty string / not appended).

- [x] **T11. Commit: slash command update**
  - Commit `commands/sq/run.md` with message: `fix(sq:run): peel -v/-vv flags from arguments, pass to sq run`
  - Success: commit exists, slash command file reflects both input-parsing and Step 0 changes.

- [x] **T12. Final validation**
  - Run full gate: `uv run pytest -q && uv run ruff check && uv run pyright`
  - Manually verify the three walkthrough scenarios from the slice design:
    1. `uv run sq run slice 152 --prompt-only` → no `-v`/`-vv` in review commands
    2. `uv run sq run slice 152 -v --prompt-only` → review commands end with `-v`
    3. `uv run sq run slice 152 -vv --prompt-only` → review commands end with `-vv`
  - Success: all gate checks pass; all three manual scenarios produce expected output.
