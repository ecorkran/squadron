---
docType: tasks
slice: plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan
project: squadron
lld: user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md
dependencies: [194, 181, 909, 927]
projectState: >
  194 (`loop:` step with a `steps:` body), 181 (pool resolver), 909 (dispatch
  artifact post-condition) and 927 (review artifact diffTruncated / answering
  model) are complete. `each` exists with one source, `cf.unfinished_slices`,
  which ignores its plan argument. A `loop:` inside `each` is a silent no-op.
  `design-batch.yaml` exists and is superseded by this slice. The 195 design
  passed review at CONCERNS with all findings dispositioned.
dateCreated: 20260926
dateUpdated: 20260926
status: in_progress
---

## Context Summary

- Working on slice 195: two unattended batch pipelines, `design-plan` and `tasks-plan`, that walk a whole slice plan, flag failures instead of stopping, and end with one report for the PM. Also fixes issue #139 (review traceability).
- The design is the reference for every decision (D1–D12). Tasks cite decisions by number instead of repeating them.
- Engine changes are general: a single step router, plan-aware cf sources, a `set_arch` cf-op, per-item isolation and a failure policy in `each`, `accept_if` / `skip_if_met` on `loop:`, `feedback: review` on dispatch, and a batch report.
- **Every commit task:** run `ruff format`, `ruff check`, and `pyright` first. Zero pyright errors is a merge blocker. Use semantic commit prefixes per `CLAUDE.md`.
- Executor behavior is tested with the existing fake action registry (`_action_registry` in `tests/pipeline/`), so no model calls are needed.
- The live walkthrough needs `sq run`, which refuses inside a Claude Code session (#144). The PM runs it from a terminal (Task 30).
- Next planned slice: 928 (Codex parity for skill packs and provider access), per the 900 plan.

---

## Task 1 — Branch setup (Effort: 1)

- [x] Read the target: `cf config get git.integration_branch` (empty means `main`)
- [x] Create `195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan` from the target, or switch to it if it exists
  - [x] **Success:** `git branch --show-current` prints the slice branch; `git status` is clean

---

## Part 1 — Router extraction (D3)

### Task 2 — Extract `_execute_step` (Effort: 3)

- [x] In `src/squadron/pipeline/executor.py`, extract the step-type branch of `execute_pipeline` (`each` / `fan_out` / `loop:` step / loop sub-field / once) into `_execute_step(step, resolved_config, …) -> StepResult`
  - [x] `execute_pipeline` calls `_execute_step` for every step
  - [x] `_execute_each_step` calls `_execute_step` for each inner step (replacing its direct `_execute_step_once` call)
  - [x] `_execute_loop_body` calls `_execute_step` for each inner step
  - [x] No other behavior change: result keying, checkpoint handling, and state persistence stay identical
  - [x] **Success:** the full existing suite passes unchanged

### Task 3 — Test: `loop:` inside `each` runs (Effort: 2)

- [x] In `tests/pipeline/test_executor.py`, add a test: an `each` over two stub items whose body is a `loop:` step with `max: 2` and a fake review action
  - [x] Assert the loop body's actions ran for each item (the fake registry records calls)
  - [x] Add a comment naming the pre-195 behavior this pins as fixed: zero actions, status COMPLETED
  - [x] **Success:** the test passes; it would fail with a direct `_execute_step_once` call
- [x] Commit: `refactor: extract single step router in pipeline executor`

---

## Part 2 — Sources (D1, D7)

### Task 4 — Move the source registry to `sources.py` (Effort: 2)

- [x] Create `src/squadron/pipeline/sources.py` and move `SourceFn`, `_SOURCE_REGISTRY`, `_SOURCE_RE`, `_cf_unfinished_slices`, and `_parse_source` into it unchanged
- [x] Update `executor.py` to import from `sources.py`
- [x] Update test imports (e.g. `tests/pipeline/test_executor.py:1687` imports `_cf_unfinished_slices` from the executor)
  - [x] **Success:** full suite passes; `grep -n "_SOURCE_REGISTRY\[" src/squadron/pipeline/executor.py` shows only lookups, no registrations
  Note: `_SOURCE_REGISTRY` / `_parse_source` became public `SOURCE_REGISTRY` / `parse_source` — pyright strict rejects private names across modules.
- [x] Commit: `refactor: move pipeline source registry to sources module`

### Task 5 — `ContextForgeClient.list_slices(plan)` / `list_tasks(plan)` (Effort: 1)

- [x] In `src/squadron/integrations/context_forge.py`, add an optional `plan: str | None = None` to `list_slices()` and `list_tasks()`
  - [x] When set, pass it as the positional `archIndex`: `cf list slices {plan} --json`, `cf list tasks {plan} --json`
  - [x] When unset, the command is unchanged
- [x] Tests in `tests/integrations/test_context_forge.py`: the argument list passed to the cf runner with and without `plan`
  - [x] **Success:** tests pass; existing callers unchanged
- [x] Commit: `feat: add plan argument to cf slice and task listing`

### Task 6 — `LoopCondition.met_by_verdict` (Effort: 2)

- [x] In `executor.py`, add `LoopCondition.met_by_verdict(verdict: str) -> bool` as the single definition of the verdict sets (D7)
  - [x] `REVIEW_PASS` → PASS only; `REVIEW_CONCERNS_OR_BETTER` → PASS or CONCERNS
  - [x] `ACTION_SUCCESS` raises `ValueError` (no verdict meaning)
- [x] Rewrite `evaluate_condition` to call `met_by_verdict` for the two review conditions
- [x] Tests: each condition against PASS, CONCERNS, FAIL; `ACTION_SUCCESS` raises
  - [x] **Success:** new tests and existing `evaluate_condition` / loop tests pass
- [x] Commit: `refactor: define review verdict thresholds once in met_by_verdict`

### Task 7 — `CfSliceStatus`, plan argument check, and the `unfinished_slices` fix (Effort: 2)

- [x] In `sources.py`, add `CfSliceStatus` StrEnum (`COMPLETE`, `DEFERRED`) and one helper that turns a source's `plan` argument into an arch index
  - [x] A value that isn't all digits raises `ValueError("plan must be an architecture index, got …")`
- [x] Fix `_cf_unfinished_slices` to pass `plan` to `list_slices(plan)` and compare against `CfSliceStatus.COMPLETE`
- [x] Tests (stub client returning real `cf list slices --json` shapes, including `designFile: null` and `status: deferred`):
  - [x] `unfinished_slices("900")` calls `list_slices("900")`
  - [x] A non-digit plan raises the stated error
  - [x] Existing `each` tests using `cf.unfinished_slices(...)` still pass
  - [x] **Success:** all pass
- [x] Commit: `fix: make unfinished_slices honor its plan argument`

### Task 8 — `cf.undesigned_slices(plan)` (Effort: 1)

- [x] Add and register `_cf_undesigned_slices`: status not in `{COMPLETE, DEFERRED}` and `design_file` is empty
  - [x] Item shape matches the API Contracts section of the design
- [x] Tests with a fixture mirroring today's 900 plan: selects 923, 924, 928, 929; excludes 907 (deferred) and 914 (designed)
  - [x] **Success:** tests pass
- [x] Commit: `feat: add undesigned_slices source`

### Task 9 — `cf.untasked_slices(plan, accept)` (Effort: 3)

- [x] Add and register `_cf_untasked_slices`: status not in `{COMPLETE, DEFERRED}`, `design_file` set, and index absent from `list_tasks(plan)`
- [x] Validate `accept` as a `LoopCondition`, and reject `ACTION_SUCCESS` as a threshold
- [x] For each selected slice, compute the design review path (D1): `reviews_dir / f"{SliceTarget.filename_stem('slice')}.md"`, built from the same slice info the save path uses. No prefix search. Never read archived predecessors.
- [x] Read the verdict from frontmatter via `split_document` + `yaml.safe_load`, validated against `Verdict`
- [x] Set `flag_reason` using exactly these strings:
  - [x] File missing → `"no design review found"`
  - [x] No parseable verdict → `"design review verdict unreadable"`
  - [x] `met_by_verdict` false → `"design review below threshold ({verdict} < {threshold verdict})"`, e.g. CONCERNS < PASS
- [x] Tests, with a design-review fixture copied from a real review artifact's frontmatter:
  - [x] 900-plan fixture: returns only 914, flagged `"no design review found"`
  - [x] A PASS review → no flag; a FAIL review under `concerns_or_better` → below-threshold flag; malformed frontmatter → unreadable flag
  - [x] A slice with a task file is not selected
  - [x] **Success:** tests pass
  Note: the review filename now comes from shared `slice_name_for` / `slice_review_stem` helpers in `review/persistence.py`, which `SliceTarget.filename_stem` and `save_review_result` also use.
- [x] Commit: `feat: add untasked_slices source gated on design review`

---

## Part 3 — cf switching (D2)

### Task 10 — `CfOperation.SET_ARCH` (Effort: 2)

- [x] In `src/squadron/pipeline/actions/cf_op.py`, add `SET_ARCH = "set_arch"` with a required `plan` param (validated like `SET_SLICE`)
  - [x] Resolve the plan file from the top-level `slicePlan` field of `cf list slices {plan} --json` (e.g. `900-slices.maintenance-and-refactoring`). `list_slices()` discards that field today, so add a `ContextForgeClient` method that returns it, with a test in `tests/integrations/test_context_forge.py`
  - [x] Read that plan file's frontmatter `parent:`; run `cf set arch {parent stem}`
  - [x] No `parent:` → action fails with an error naming the plan file
  - [x] Do not call `cf set plan`
- [x] Tests in `tests/pipeline/actions/test_cf_op.py`: the `cf set arch` call and argument; the no-parent failure message; missing `plan` param rejected
  - [x] **Success:** tests pass
- [x] Commit: `feat: add set_arch cf-op`

### Task 11 — Phase step `plan:` key and the arch → slice → phase order (Effort: 2)

- [x] In `src/squadron/pipeline/steps/phase.py`:
  - [x] Accept an optional `plan:` key
  - [x] `expand()` emits, in order: `cf-op set_arch` (only when `plan:` is set) → `set_slice` → `set_phase` → `build_context` → dispatch → …
  - [x] This flips today's `set_phase` → `set_slice` order for every phase step
- [x] Update the exact-equality `expand()` tests in `tests/pipeline/steps/test_phase.py` to the new order; add cases with and without `plan:`
  - [x] **Success:** tests pass; P4, P5, `app.yaml`, `judge-cycle`, `findings-addressed-cycle`, and `test-loop` still load and validate
  Note: the `--prompt-only` renderer also gained a `set_arch` instruction (it would otherwise emit `cf set_arch`); three other order-pinning tests (test_run.py, test_prompt_only_integration.py, test_prompt_renderer.py) were updated to the new order.
- [x] Commit: `fix: switch phase step cf order to arch, slice, phase`

---

## Part 4 — `each` changes (D3, D4, D5)

### Task 12 — `each` inner-step validation and nesting bans (Effort: 2)

- [x] In `src/squadron/pipeline/steps/collection.py`, validate each inner step with its own step type's `validate()`
  - [x] Reject an inner `each` (nested `each` ban)
  - [x] Accept `on_item_failure` values from a new `ItemFailurePolicy` StrEnum (`STOP` default, `CONTINUE`); reject anything else
- [x] In `steps/loop.py` `_validate_inner_steps`, reject an inner `each`
- [x] Tests (new `tests/pipeline/steps/test_collection.py`, plus `tests/pipeline/steps/test_loop.py`): nested `each` rejected; `each` in `loop:` rejected; invalid inner step config surfaces its own error; bad `on_item_failure` rejected
  - [x] **Success:** tests pass; existing pipelines validate
- [x] Commit: `feat: validate each inner steps and ban nested each`

### Task 13 — Per-item isolation (Effort: 2)

- [x] In `_execute_each_step`, per item build `item_prior = dict(prior_outputs)` and `item_step_outputs = dict(step_outputs)`, accumulate the item's results into both using `_execute_loop_body`'s keying, and discard them when the item ends (D4)
  - [x] Run-wide `prior_outputs` / `step_outputs` never receive item results
- [x] Test: two items whose fake reviews carry distinct findings; the second item's fake dispatch sees only its own item's review
  - [x] **Success:** test passes
- [x] Commit: `fix: isolate each item outputs from other items`

### Task 14 — `on_item_failure` and pre-flagged items (Effort: 3)

- [x] Implement D5 in `_execute_each_step`:
  - [x] `CONTINUE`: a FAILED inner step ends the item and records it FLAGGED with the step's `error`, else the first failed action's `error`, else `"step {name} failed"`; the next item runs; the `each` step completes COMPLETED
  - [x] `STOP` (default): today's behavior
  - [x] PAUSED stops the run under both policies
  - [x] An item with `flag_reason` is recorded FLAGGED with that reason and its body is not run, under both policies
  - [x] Each flagged item logs at WARNING with its reason
- [x] Tests: each bullet above, including that `STOP` behavior is unchanged
  - [x] **Success:** tests pass
  Note: tests live in the new `tests/pipeline/test_executor_each.py`.
- [x] Commit: `feat: add on_item_failure policy and pre-flagged items to each`

---

## Part 5 — Loop options (D6)

### Task 15 — `accept_if`, `skip_if_met`, param-sourced values (Effort: 3)

- [x] `StepResult` gains `accepted: bool = False`
- [x] `_parse_loop_config`: parse `accept_if` (a `LoopCondition`) and `skip_if_met` (bool); accept `max` as an int or a decimal digit string; its `ValueError` names the bad field
- [x] `LoopStepType.validate`: reject `accept_if` or `skip_if_met` without `until`; skip load-time checks for `max` / `until` / `accept_if` values containing `{` (same convention as `_validate_model_alias`)
- [x] `_execute_loop_body`:
  - [x] `skip_if_met`: before round 1, evaluate `until` against `prior_outputs` in insertion order; if met, complete with `iteration=0` and no rounds
  - [x] On exhaust: if `accept_if` is met by the final round's results → COMPLETED with `accepted=True`; otherwise `on_exhaust` applies as today
- [x] Tests (`tests/pipeline/test_executor_loop_body.py`, `tests/pipeline/test_loop_validation.py`):
  - [x] Passing pre-loop review + `skip_if_met` → 0 rounds
  - [x] `accept_if` met on exhaust → COMPLETED, `accepted`; not met → `on_exhaust` applies
  - [x] `max: "3"` resolves; `max: "three"` fails naming `max`
  - [x] Placeholder values pass load-time validation
  - [x] **Success:** tests pass
  Note: `accept_if` and `skip_if_met` are applied through shared helpers (`_loop_exhaust_result`, `_loop_skip_result`), so they also work on a step's `loop:` sub-field, not only the `loop:` step type.
- [x] Commit: `feat: add accept_if and skip_if_met loop options`

---

## Part 6 — Revise dispatch (D8)

### Task 16 — Review action `input_file` output (Effort: 1)

- [x] In `src/squadron/pipeline/actions/review.py`, add `outputs["input_file"]`: the path of the file that was reviewed
- [x] Test in `tests/pipeline/actions/test_review_action.py`: a slice review's `input_file` is the slice design path
  - [x] **Success:** test passes
- [x] Commit: `feat: add input_file to review action outputs`

### Task 17 — `dispatch: { feedback: review }` (Effort: 2)

- [x] Add a `DispatchFeedback` StrEnum (`REVIEW`) and accept `feedback` in dispatch config and validation
- [x] In `src/squadron/pipeline/actions/dispatch.py`, when `feedback: review` is set, the prompt is the step's `prompt` (if any) followed by the findings block from the most recent in-scope review result
  - [x] Reuse the body of `_resolve_prompt_from_prior_review`; don't duplicate it
  - [x] Append `"Revise `{input_file}` in place; do not create a new file."`
  - [x] No in-scope review → fail with `"feedback: review but no prior review in scope"`
- [x] Tests in `tests/pipeline/actions/test_dispatch.py`: prompt contains findings and `input_file`; the no-review failure; `build_context` output in scope is not used when `feedback: review` is set
  - [x] **Success:** tests pass
  Note: the dispatch step type validates `feedback` and passes it to the action; a missing review raises `DispatchFeedbackError`, reported as the action's error.
- [x] Commit: `feat: add review feedback mode to dispatch`

---

## Part 7 — Batch report (D9)

### Task 18 — `batch_report.py` (Effort: 3)

- [x] Create `src/squadron/pipeline/batch_report.py` with `ItemOutcome` (`PASSED`, `ACCEPTED`, `FLAGGED`), `BatchItemRecord`, and `BatchReport`
  - [x] Build a record from an item and its results, per D9 (labels, final verdict, review file, outcome rules)
  - [x] Render Markdown: frontmatter (`docType: batch-report`, `pipeline`, `runId`, `plan` when present, counts), then Flagged / Accepted / Passed sections, flagged first with reason and review file
  - [x] Write to `{runs_dir}/{run_id}.{step_name}.report.md`
- [x] Tests (new `tests/pipeline/test_batch_report.py`): outcome rules for each case; item without `index`/`name` labeled by position; rendered frontmatter parses and counts match; flagged section first
  - [x] **Success:** tests pass; module stays near ~300 lines
- [x] Commit: `feat: add batch report model and renderer`

### Task 19 — Wire the report into `each` (Effort: 2)

- [x] `StepResult` gains `batch_report: BatchReport | None`
- [x] `_execute_each_step` builds a record per item, writes the report file at the end, and sets `batch_report`. Every `each` step does this, with no opt-in flag.
  - [x] Report is written even when every item is FLAGGED
- [x] Tests: report file exists next to `{run_id}.json` with correct counts after a mixed run
  - [x] **Success:** tests pass
- [x] Commit: `feat: write batch report for each steps`
- Note: the report is written on every exit (completed, stopped, paused). An autouse fixture in tests/conftest.py (`isolate_default_runs_dir`) keeps test reports out of ~/.config/squadron/runs.

### Task 20 — `sq run` summary (Effort: 1)

- [x] In `src/squadron/cli/commands/run.py`, after the run, for each step result with a `batch_report`: print one line of counts, the flagged items, and the report path
- [x] Test in `tests/cli/commands/test_run.py`
  - [x] **Success:** test passes
- [x] Commit: `feat: summarize batch reports in sq run`

---

## Part 8 — Pipelines (D11)

### Task 21 — `design-plan.yaml` and `tasks-plan.yaml` (Effort: 2)

- [x] Create `src/squadron/data/pipelines/design-plan.yaml` exactly as in D11
- [x] Create `tasks-plan.yaml`: the same file, with source `cf.untasked_slices("{plan}", "{accept-threshold}")`, `tasks:` with `phase: 5`, and both review templates `tasks`
- [x] Tests in `tests/pipeline/test_loader_integration.py`: both load and validate
  - [x] **Success:** tests pass
- [x] Commit: `feat: add design-plan and tasks-plan batch pipelines`
- Note: `max-revisions` is quoted ("3") — the pipeline params schema accepts only strings.

### Task 22 — Remove `design-batch.yaml` (Effort: 1)

- [x] Delete `src/squadron/data/pipelines/design-batch.yaml`
- [x] Update every reference (the design lists three; five exist):
  - [x] `tests/pipeline/test_loader.py:108`
  - [x] `tests/pipeline/test_loader_integration.py:16,77`
  - [x] `tests/pipeline/test_executor_integration.py:189,242` → use `design-plan`
  - [x] `src/squadron/data/pipelines/example.yaml:172` → point at `design-plan.yaml`
  - [x] `docs/PIPELINES.md:662` (the table row; rewritten in Task 29)
  - [x] **Success:** `grep -rn design-batch src tests docs` returns nothing; full suite passes
- [x] Commit: `refactor: remove design-batch pipeline superseded by design-plan`
- Note: `tests/pipeline/test_executor_integration.py` now runs design-plan end to end with fakes (PASSED / ACCEPTED / FLAGGED slices).

---

## Part 9 — Issue #139 (D12)

### Task 23 — `run_id` on reviews (Effort: 2)

- [x] `ReviewResult.run_id: str | None = None`; the review action sets it from `ActionContext.run_id`; the CLI leaves it `None`
- [x] Frontmatter `runId` only when set; JSON `run_id` always present (`null` on the CLI)
- [x] Tests: `tests/review/test_models.py`, `tests/review/test_persistence.py`, `tests/pipeline/actions/test_review_action.py`
  - [x] **Success:** tests pass
- [x] Commit: `feat: record pipeline run id on review artifacts`
- Note: pipeline provider-failure artifacts also carry `runId`.

### Task 24 — `squadronVersion` on reviews (Effort: 2)

- [x] `_review_frontmatter_lines` takes the version as a parameter; call sites pass `squadron.__version__`
- [x] Frontmatter `squadronVersion` on every artifact, including provider-failure artifacts; JSON `squadron_version` always present
- [x] Key placement: `runId` then `squadronVersion` at the end of the block, after `diffTruncated`
- [x] Snapshot tests pass a fixed version; regenerate `tests/review/fixtures/clean_pass_artifact.md` once for the new key
- [x] Tests: persistence, models, provider-failure artifact
  - [x] **Success:** tests pass; the fixture diff is only the new key
- [x] Commit: `feat: record squadron version on review artifacts`
- Note: the six 383 migration fixtures (pre and post) and clean_pass_artifact.md each gained only the `squadronVersion: 0.0.0-test` line; tests pin that version.

### Task 25 — `providerFailure` frontmatter (Effort: 1)

- [x] `format_provider_failure_markdown` adds `providerFailure: true` directly after `verdict`; other artifacts omit it
- [x] Tests in `tests/review/test_persistence.py`
  - [x] **Success:** tests pass
- [x] Commit: `feat: mark provider failure review artifacts in frontmatter`

### Task 26 — Pure JSON stdout (Effort: 1)

- [x] In `_save_and_report` (`src/squadron/cli/commands/review.py`), print "Saved review to {path}" to stderr when `--output json`, and to stdout otherwise
- [x] Test in `tests/cli/test_review_save.py`: stdout under `--output json` parses as JSON
  - [x] **Success:** test passes
- [x] Commit: `fix: send saved-review line to stderr under json output`
- Note: a `--output` `OutputMode` StrEnum replaced the string literals in review.py; `_save_and_report` takes `json_stdout`.

### Task 27 — `to_dict()` gaps (Effort: 1)

- [x] `structured_findings[].location_verified` added; `finding_scan` added as an object of `FindingScanCounts` fields, `null` when absent
- [x] Tests in `tests/review/test_models.py`
  - [x] **Success:** tests pass; CLI and pipeline paths write identical frontmatter apart from `runId`
- [x] Commit: `fix: add location_verified and finding_scan to review to_dict`
- Note: `StructuredFinding` now carries `location_verified`.

---

## Part 10 — Docs and validation

### Task 28 — Full validation (Effort: 1)

- [x] `ruff format`, `ruff check`, `pyright` (zero errors), full test suite
- [x] `executor.py` has not grown on net versus the branch point (`git diff --stat`); `sources.py` and `batch_report.py` near ~300 lines
  - [x] **Success:** all clean; record pass/skip counts for the DEVLOG
  Note: full suite 4669 passed, 4 skipped; executor.py 1704 → 1636 after moving the loop grammar to `pipeline/loop_config.py` (commit f0cc31a5).

### Task 29 — `docs/PIPELINES.md` (Effort: 2)

- [x] Document the sources (`undesigned_slices`, `untasked_slices`, `unfinished_slices` with the arch-index argument), `each` options (`on_item_failure`, pre-flagged items, isolation), loop options (`accept_if`, `skip_if_met`, param values), `feedback: review`, the batch report, and the two pipelines, including that `max-revisions` counts revise rounds after the first design
- [x] Note that batches change cf state and that no other cf-consuming command should run in the project during a batch
- [x] Replace the `design-batch` table row
  - [x] **Success:** every item in design Included §11 is covered
- [x] Commit: `docs: document plan batch pipelines and engine options`

### Task 30 — Walkthrough handoff (Effort: 1)

- [x] Run walkthrough step 2 (`cf list slices 900 --json | jq …`) and record the actual output in the design's Verification Walkthrough
- [x] Try walkthrough step 1 (`uv run sq run design-plan --validate`); record the actual output, or the refusal text if `sq run` refuses in this session
- [x] Run walkthrough step 8's `sq review slice … --output json` checks if they run in this session; record actual output
- [x] Mark the remaining steps (3–7, 9) in the design as PM-run from a terminal (#144)
  - [x] **Success:** each step in the walkthrough carries either recorded actual output or the PM-run marker

---

## Close-out

### Task 31 — Slice close-out (Effort: 1)

- [x] CHANGELOG: short user-facing bullets under Unreleased (the two pipelines, the batch report, review traceability)
- [x] DEVLOG entry: Phase 6 complete, test counts, commits
- [x] Set `status: complete` in the slice design and this task file; check off entry 15 (195) in `project-documents/user/architecture/180-slices.pipeline-intelligence.md`
- [x] Commit: `docs: complete slice 195`
- [ ] Merge: re-read the target (`cf config get git.integration_branch`), `git checkout {target}`, `git merge` the slice branch; if either fails, stop and ask the PM
  - [ ] **Success:** the target contains the slice commits; the slice branch is left in place
