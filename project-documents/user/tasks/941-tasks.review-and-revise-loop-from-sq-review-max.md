---
docType: tasks
slice: review-and-revise-loop-from-sq-review-max
project: squadron
lld: user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md
dependencies: []
projectState: >
  Slice design 941 complete after two review rounds plus the D7 observer hook (20261012).
  Prerequisite fix 85a7f7aa (a failed round commit ends the loop) is on main. No code written.
dateCreated: 20261012
dateUpdated: 20261012
status: not_started
---

## Context Summary

- Working on **941 review-and-revise-loop-from-sq-review-max**. `sq review slice|tasks|code <index> --max N` runs one review, then up to N revise-and-review rounds using the loop from P4/P5/P6. Nothing is regenerated.
- The design is the reference for every decision (D1–D7). Tasks cite decisions by number and do not restate them.
- New files: `src/squadron/pipeline/review_revise.py` (table + builder), `src/squadron/cli/commands/review_revise.py` (validation, params, `RoundPrinter`, exit codes). Edited: `pipeline/run_observer.py`, `pipeline/executor.py`, `tests/pipeline/observer_support.py`, `cli/commands/review.py` (option declarations and one early branch only), `commands/sq/review.md`, `CHANGELOG.md`.
- No MCP surface, no run state, no pipeline YAML changes (design "Excluded").
- Every implementation-and-test pair ends with `ruff format`, `ruff check`, `pyright` (zero errors), the touched tests, and a commit on the slice branch.
- Effort: 3/5. Next: no dependent slice.

## Tasks

- [x] **Task 1: Branch and observer hook (D7)**
  - [x] Read the target (`cf config get git.integration_branch`, empty means `main`) and create `941-slice.review-and-revise-loop-from-sq-review-max` from it
  - [x] Add `round_completed(step_name, iteration, results)` to `RunObserver`; no-op on `RunStateRecorder`; recording implementation on `RecordingObserver` (`tests/pipeline/observer_support.py`)
  - [x] Pass `observer` into `_execute_loop_body` as `_execute_each_step` receives it, and call `round_completed` after each round's commit, before the `until` check, including a round whose commit failed
  - **Success:** pyright passes with every `RunObserver` implementation

- [x] **Task 2: Test the observer hook**
  - [x] In `tests/pipeline/test_executor_loop_body.py` / `test_loop_round_commits.py`, with `RecordingObserver`: one call per round with that round's iteration and results; the failed-commit round is reported; a loop meeting `until` on round 1 reports exactly one round
  - [x] Commit: `feat: report each loop round through RunObserver.round_completed`
  - **Success:** `pytest tests/pipeline -q` passes

- [x] **Task 3: `pipeline/review_revise.py` (D1, D2, D4)**
  - [x] `REVISE_PIPELINE_BY_KIND` and `build_review_revise_definition(kind)` as specified in the design ("Technical Scope" items 3–4, Data Flow, D2's three checks, D4's `on_exhaust: fail`)
  - [x] Copy the loaded pipeline's steps before overriding; do not mutate them
  - **Success:** builds `[review, loop]` for all three kinds against the shipped pipelines

- [x] **Task 4: Test the builder**
  - [x] New `tests/pipeline/test_review_revise.py` covering the design's builder requirements: each kind's shape and `on_exhaust=fail`; errors for zero/two loops, zero/two review steps, missing `until`, missing `skip_if_met`; a project override of P4 is picked up; an unmapped kind raises; the loaded pipeline is unchanged after building
  - [x] Commit: `feat: compose a review-revise pipeline from P4/P5/P6 loops`
  - **Success:** tests pass

- [x] **Task 5: `RoundPrinter` and its tests (D7)**
  - [x] In new `cli/commands/review_revise.py`, implement `RoundPrinter` producing the design's "API Contracts" output: header, review line on `step_completed` for the review step, one line per `round_completed` (`committed <sha>`, `commit failed`, or `no changes`); a missing review result raises
  - [x] Tests in new `tests/cli/test_review_revise.py` with constructed `ActionResult`s for each line form and the raise
  - [x] Commit: `feat: print review-revise rounds through RoundPrinter`
  - **Success:** tests pass

- [x] **Task 6: `run_review_revise` (D3, D4, D5)**
  - [x] `run_review_revise(kind, slice_index, reviewer, revise_model, max_rounds, cwd, verbosity) -> int`: build the definition, assemble params per D3 (`model` only when `revise_model` is given), run `execute_pipeline` with `RoundPrinter` and no run-state recording, print `final: <VERDICT> after N rounds`, return the D5 exit code
  - [x] Read the outcome from the returned `PipelineResult`: rounds = loop `StepResult.iteration`; final verdict = the review result in the loop's `action_results` when rounds > 0, else the leading review step's; `accepted` / `exhausted` from the loop `StepResult`
  - [x] Check `accepted`, then `exhausted`, before run status: an exhausted, unaccepted loop has failed status but exits 2, not 1
  - [x] Implement the mapping here; do not import or move `_exit_on` (D3, and Task 8's `review.py` diff limit)
  - [x] On a failed run, print the failing step's `error` to stderr and return 1. For a failed round commit that error is the executor's `loop <name> round N commit failed: <error>` (D5), so the runner prints it as-is and does not build its own text
  - [x] Session handling (PM decision 2026-10-13): `classify_for_run` and the `pipeline_session` context manager are extracted from `sq run` into `pipeline/run_session.py` (commit `refactor: extract classify_for_run and pipeline_session from sq run`); the runner uses both so a revise dispatch on an sdk model gets the persistent session the executor's lazy hook would not open for a dispatch inside a loop. The runner takes no `verbosity` parameter; `review.py` sets up logging before calling it (Task 8)
  - [x] Apply no `CLAUDECODE` guard in the runner or the `--max` wiring (D5, "Claude Code sessions"); do not import `_resolve_execution_mode`
  - **Success:** every runner-owned D5 row returns its code

- [x] **Task 7: Test the runner**
  - [x] In `tests/cli/test_review_revise.py`, executor stubbed:
    1. [x] params contain `slice`, `review-model`, `max-revisions`; `model` only with a reviser; a pool alias reaches `review-model` unchanged
    2. [x] exit 0 for PASS and CONCERNS, 2 for FAIL, 1 for a failed action
    3. [x] exhausted loop: accepted → 0, not accepted → 2
    4. [x] zero rounds: `final:` uses the leading review's verdict and reports 0 rounds
    5. [x] failed round commit → stderr `round N commit failed: …`, exit 1
  - [x] Commit: `feat: add review-revise runner with params and exit codes`
  - **Success:** tests pass

- [x] **Task 8: Option validation and wiring into `review.py` (D6)**
  - [x] In `review_revise.py`, define `MAX_SUPPORTED_OPTIONS` and `validate_max_options(ctx, kind, input)` implementing D6. Only `click.Option` parameters are checked, so the positional index is exempt. Each refusal prints its error to stderr and raises `typer.Exit(1)`
  - [x] In the same function, for `CODE` only: refuse a dirty working tree (D5 last row), listing the dirty paths (`git status --porcelain` through `run_git`); a failed git call is an error, not a clean tree
  - [x] In `review.py`, for `review_slice` (`SLICE`), `review_tasks` (`TASKS`) and `review_code` (`CODE`):
    1. [x] add `ctx: typer.Context`, `--max` (int; the range is enforced by the loop's `max` validation, not Typer) and `--revise-model`
    2. [x] refuse `--revise-model` without `--max`
    3. [x] early branch when `--max` is given: `validate_max_options(ctx, kind, input)`, resolve the reviewer with `_resolve_model`, then `raise typer.Exit(run_review_revise(...))`
  - [x] Convert the literal kind to `BuiltinReviewTemplate` once, at this boundary. Do not touch `review_arch`
  - **Success:** `--help` for the three subcommands lists both options; `review.py` diff is limited to these declarations and early branches

- [x] **Task 9: Test validation and wiring through the CLI**
  - [x] Through Typer's `CliRunner` with `execute_pipeline` stubbed:
    1. [x] `slice`, `tasks` and `code` route to the runner with the right kind; `--max 3` and `--max=3` both parse
    2. [x] a valid `<index> --max 2 --model X` reaches the stubbed executor
    3. [x] refusals exit 1 with the stub never called: path input, `--json` and one other unsupported option (error names it), `--revise-model` without `--max`, `code` on the wrong branch (names the expected branch), `code` with a dirty tree (lists the paths)
    4. [x] `arch --max 1` fails with Typer's unknown-option error
  - [x] `pytest tests/cli -q`: all existing review CLI tests pass unchanged (Success Criterion 6)
  - [x] Commit: `feat: add --max and --revise-model to sq review slice, tasks and code`
  - **Success:** tests pass

- [ ] **Task 10: Two-round integration test**
  - [ ] New `tests/pipeline/test_review_revise_integration.py`, using the fake-action and tmp-git-repo patterns in `test_loop_round_commits.py` / `test_executor_integration.py`: review CONCERNS → round 1 CONCERNS → round 2 PASS. Assert two `round_completed` calls, a commit per round, prior reviews in `reviews/archive/`, final PASS
  - [ ] A first-review PASS case runs zero rounds (Success Criterion 2)
  - [ ] Commit: `test: add review-revise integration test`
  - **Success:** tests pass

- [ ] **Task 11: Slash command doc and CHANGELOG**
  - [ ] In `commands/sq/review.md`, document `--max N` and `--revise-model` for `slice`, `tasks` and `code` as passed through to `sq review` unchanged, with the D6 restrictions; run any installed-command sync/parity tests covering `commands/sq/`
  - [ ] Add an Unreleased `### Added` CHANGELOG bullet: `sq review slice|tasks|code --max N` revises an existing artifact until its review passes, with `--revise-model` for the reviser
  - [ ] Commit: `docs: document sq review --max in slash command and CHANGELOG`

- [ ] **Task 12: Final gate and Verification Walkthrough (design steps 1–6)**
  - [ ] Full test suite, `ruff format`, `ruff check`, `pyright` pass
  - [ ] Install the branch build of `sq`, confirm `sq --version` runs from this checkout, and run walkthrough steps 1–5 against slice 941 from a standard terminal (step 4: slice branch, then `main`)
  - [ ] Run step 6 (`/sq:review` parity, Success Criterion 9) inside Claude Code. If it cannot run in this session, the closing report to the PM states that SC9 is unverified and gives the exact command to run
  - [ ] Record results in the design's Verification Walkthrough and the DEVLOG; commit `docs: record slice 941 verification results`
  - **Success:** each step's output matches the design, or the mismatch is reported to the PM with the command and output
