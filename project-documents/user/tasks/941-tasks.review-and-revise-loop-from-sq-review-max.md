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
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors), the touched tests, and a commit on the slice branch.
- Effort: 3/5. Next: no dependent slice.

## Tasks

- [ ] **Task 1: Branch**
  - [ ] Read the target: `cf config get git.integration_branch` (empty means `main`)
  - [ ] Create `941-slice.review-and-revise-loop-from-sq-review-max` from the target
  - **Success:** on the slice branch, working tree clean

### Observer hook (D7)

- [ ] **Task 2: Add `round_completed` to `RunObserver`**
  - [ ] Add `round_completed(self, step_name: str, iteration: int, results: list[ActionResult]) -> None` to the `RunObserver` protocol in `pipeline/run_observer.py`
  - [ ] Implement it as a no-op on `RunStateRecorder`
  - [ ] Implement it on `RecordingObserver` in `tests/pipeline/observer_support.py`, recording `(step_name, iteration, results)` so tests can assert calls
  - **Success:** pyright reports zero errors; every existing `RunObserver` implementation satisfies the protocol

- [ ] **Task 3: Call `round_completed` from the loop body**
  - [ ] Pass `observer` into `_execute_loop_body` (`pipeline/executor.py`) the same way `_execute_each_step` receives it
  - [ ] After each round's commit and before the `until` check, call `observer.round_completed(step.name, iteration, round_results)` when an observer is present
  - [ ] The call also happens for a round whose commit failed (fix 85a7f7aa path), before the loop ends
  - **Success:** a round that ends the loop (until met, commit failed, or max reached) is still reported

- [ ] **Task 4: Test the loop observer call**
  - [ ] In `tests/pipeline/test_executor_loop_body.py` (or `test_loop_round_commits.py` for the commit-failure case), use `RecordingObserver` to assert:
    1. `round_completed` is called once per round with the correct iteration and that round's results
    2. the round whose commit failed is reported, with the failed commit result in `results`
    3. a loop that meets `until` on round 1 reports exactly one round
  - [ ] Run `pytest tests/pipeline -q`, then ruff and pyright
  - [ ] Commit: `feat: report each loop round through RunObserver.round_completed`
  - **Success:** tests pass, zero pyright errors

### Pipeline builder (D1, D2, D4)

- [ ] **Task 5: `pipeline/review_revise.py`**
  - [ ] Define `REVISE_PIPELINE_BY_KIND: dict[BuiltinReviewTemplate, str]` with `SLICE → "P4"`, `TASKS → "P5"`, `CODE → "P6"`
  - [ ] Implement `build_review_revise_definition(kind) -> PipelineDefinition`:
    1. kind missing from the table → explicit error naming the kind
    2. `load_pipeline(name)` (honors project/user overrides)
    3. find the single step with `step_type == StepTypeName.LOOP`; zero or more than one → error naming the pipeline
    4. validate the loop with `parse_loop_config`: exactly one `review` step in its body, `until` set, `skip_if_met: true`; each failure → error naming the pipeline and the failed check
    5. review step = copy of the loop body's review action config
    6. loop step = the pipeline's loop with `on_exhaust` set to `ExhaustBehavior.FAIL`; all other loop config unchanged
    7. return `PipelineDefinition(name=f"review-revise-{kind.value}", params=<pipeline params>, steps=[review, loop])`
  - [ ] Do not mutate the loaded pipeline's objects; copy before overriding
  - **Success:** builds for all three kinds against the shipped pipelines; file stays well under 300 lines

- [ ] **Task 6: Test the builder**
  - [ ] New `tests/pipeline/test_review_revise.py`:
    1. each mapped kind yields `[review, loop]`, the loop config matches the pipeline's own except `on_exhaust=fail`, and the review step's config equals the loop body's review config
    2. errors for: zero loops, two loops, zero review steps in the body, two review steps, missing `until`, `skip_if_met` unset or false (use small fixture pipelines via the override mechanism or a stubbed `load_pipeline`)
    3. a project override of P4 (in the test's tmp project) is picked up
    4. a kind not in the table raises
    5. the loaded pipeline definition is unchanged after building
  - [ ] Run `pytest tests/pipeline/test_review_revise.py -q`, then ruff and pyright
  - [ ] Commit: `feat: compose a review-revise pipeline from P4/P5/P6 loops`
  - **Success:** tests pass, zero pyright errors

### CLI runner (D3, D5, D6, D7)

- [ ] **Task 7: Option validation in `cli/commands/review_revise.py`**
  - [ ] Define `MAX_SUPPORTED_OPTIONS` (`max`, `model`, `revise_model`, `cwd`, `verbose`) as one constant
  - [ ] Implement a validator taking the Click context, run before any model call:
    1. positional input must be a slice index; otherwise `--max requires a slice index`
    2. any parameter outside `MAX_SUPPORTED_OPTIONS` whose source is `ParameterSource.COMMANDLINE` → error naming it (e.g. `--json is not supported with --max`)
    3. for `code`: current branch must equal `slice_branch_name(...)` from `pipeline/git_ops.py`; otherwise error naming the expected branch
    4. for `code`: a dirty working tree → error listing the dirty paths
  - [ ] The `--revise-model requires --max` check lives here too, callable when `--max` is absent
  - [ ] `review_revise.py` imports nothing from `cli/commands/review.py` (D3)
  - **Success:** every refusal raises before the executor is reached

- [ ] **Task 8: Test option validation**
  - [ ] New `tests/cli/test_review_revise.py`, executor stubbed, asserting the stub is never called on any refusal:
    1. path input with `--max` → `--max requires a slice index`
    2. `--json`, and one other non-supported option, with `--max` → error names the option
    3. `--revise-model` without `--max` → `--revise-model requires --max`
    4. `code` on the wrong branch → error names the expected branch, exit 1
    5. `code` with a dirty tree → error lists the dirty paths, exit 1
  - [ ] Run the new tests, then ruff and pyright
  - **Success:** tests pass

- [ ] **Task 9: `RoundPrinter` observer**
  - [ ] Implement `RoundPrinter` (a `RunObserver`) in `cli/commands/review_revise.py`:
    1. header line: kind, index, reviewer, reviser, max (design "API Contracts")
    2. on `step_completed` for the review step: verdict, finding count, review filename
    3. on `round_completed`: `round N`, verdict, finding count, then `committed <short sha>`, `commit failed`, or `no changes`
    4. a round with no review result raises (D7)
  - [ ] Other observer methods are no-ops
  - **Success:** output matches the design's example layout

- [ ] **Task 10: Test `RoundPrinter`**
  - [ ] In `tests/cli/test_review_revise.py`, feed constructed `ActionResult`s and assert lines for: verdict + SHA, `commit failed`, `no changes`, review step line; and that a missing review result raises
  - [ ] Run the tests, then ruff and pyright
  - **Success:** tests pass

- [ ] **Task 11: `run_review_revise` — params, execution, exit codes**
  - [ ] Implement `run_review_revise(kind, slice_index, reviewer, revise_model, max_rounds, cwd, verbosity) -> int`:
    1. `build_review_revise_definition(kind)`
    2. params: `slice`, `review-model` = reviewer, `max-revisions` = str(max_rounds), `model` = revise_model only when given (pipeline default otherwise)
    3. `execute_pipeline(definition, params, ..., observer=RoundPrinter(...))`, with no run-state recording (D4)
    4. print `final: <VERDICT> after N rounds`
    5. map the outcome to exit codes per D5: 0 for PASS or accepted, 2 for FAIL or exhausted-not-accepted, 1 for a failed run; a failed round commit prints `round N commit failed: <error>` on stderr and returns 1
  - [ ] Reuse the existing verdict→exit semantics; do not duplicate `_exit_on` logic in a second form (extract a shared helper if needed)
  - **Success:** returns the D5 code for every row in the D5 table that the runner owns

- [ ] **Task 12: Test params and exit codes**
  - [ ] In `tests/cli/test_review_revise.py`, executor stubbed:
    1. params contain `slice`, `review-model`, `max-revisions`; `model` present only with `--revise-model`
    2. a pool alias passed as reviewer reaches `review-model` unchanged (D3)
    3. exit 0 for PASS and for accepted CONCERNS; 2 for FAIL; 1 for a failed action
    4. stubbed failed round commit → stderr `round N commit failed: …` and exit 1
  - [ ] Run the tests, then ruff and pyright
  - [ ] Commit: `feat: add review-revise runner with option checks and round output`
  - **Success:** tests pass, zero pyright errors

### Wiring

- [ ] **Task 13: Wire `--max` / `--revise-model` into `review_slice`**
  - [ ] In `cli/commands/review.py`, add `--max` (int, min 1) and `--revise-model` to `review_slice`
  - [ ] Resolve the reviewer with the existing `_resolve_model`, then add the early branch: `if max_rounds is not None: raise typer.Exit(run_review_revise(...))`, with the `--revise-model requires --max` check before it
  - [ ] Convert the literal kind to `BuiltinReviewTemplate` once, here
  - **Success:** `sq review slice --help` lists both options; `--max 3` and `--max=3` both parse

- [ ] **Task 14: Wire into `review_tasks`**
  - [ ] Same as Task 13 for `review_tasks`, kind `TASKS`
  - **Success:** `sq review tasks --help` lists both options

- [ ] **Task 15: Wire into `review_code`**
  - [ ] Same as Task 13 for `review_code`, kind `CODE`
  - [ ] Do not add the options to `review_arch`
  - **Success:** `sq review code --help` lists both options; `sq review arch 941 --max 1` fails with Typer's unknown-option error

- [ ] **Task 16: Test wiring and no-`--max` parity**
  - [ ] Through Typer's `CliRunner`, executor stubbed: each of `slice`, `tasks`, `code` routes to `run_review_revise` with the right kind; `arch --max` is rejected; `--max 0` is rejected
  - [ ] Run `pytest tests/cli -q`: all existing review CLI tests pass unchanged (Success Criterion 6)
  - [ ] Run ruff and pyright
  - [ ] Commit: `feat: add --max and --revise-model to sq review slice, tasks and code`
  - **Success:** tests pass, zero pyright errors, `review.py` diff limited to option declarations and the early branches

### Integration

- [ ] **Task 17: Two-round integration test**
  - [ ] Add an integration test (`tests/pipeline/test_review_revise_integration.py`) running the composed definition through `execute_pipeline` with fake review and dispatch actions: review CONCERNS → round 1 CONCERNS → round 2 PASS
  - [ ] Assert: two `round_completed` calls; each round commits; prior reviews archived under `reviews/archive/`; final verdict PASS
  - [ ] Add a case where the first review is PASS: zero rounds run (Success Criterion 2)
  - [ ] Follow the fake-action and tmp-git-repo patterns already in `test_loop_round_commits.py` / `test_executor_integration.py`
  - [ ] Run the test, then ruff and pyright
  - [ ] Commit: `test: add review-revise integration test`
  - **Success:** tests pass

### Docs and verification

- [ ] **Task 18: Slash command doc**
  - [ ] In `commands/sq/review.md`, document `--max N` and `--revise-model` for `slice`, `tasks` and `code`, and confirm they are passed through to `sq review` unchanged
  - [ ] State the restrictions from D6 (slice index only, supported options only, `code` needs the slice branch and a clean tree)
  - [ ] Run any installed-command sync/parity tests that cover `commands/sq/`
  - **Success:** doc covers both options for all three kinds

- [ ] **Task 19: CHANGELOG**
  - [ ] Add an Unreleased `### Added` bullet: `sq review slice|tasks|code --max N` revises an existing artifact until its review passes, with `--revise-model` for the reviser
  - [ ] Commit: `docs: document sq review --max in slash command and CHANGELOG`

- [ ] **Task 20: Full validation**
  - [ ] Run the full test suite, `ruff format`, `ruff check`, `pyright`
  - **Success:** all pass, zero pyright errors

- [ ] **Task 21: Verification Walkthrough (design steps 1–6)**
  - [ ] Install the branch build of `sq` and confirm `sq --version` runs from this checkout
  - [ ] Run walkthrough steps 1–5 against slice 941 from a standard terminal; for step 4, use the slice branch and then `main`
  - [ ] Step 6 (`/sq:review` parity) runs inside Claude Code; if it cannot be run in this session, record it as pending for the PM
  - [ ] Record results in the design's Verification Walkthrough and the DEVLOG; commit `docs: record slice 941 verification results`
  - **Success:** each step's observed output matches the design, or the mismatch is reported to the PM with the command and output
