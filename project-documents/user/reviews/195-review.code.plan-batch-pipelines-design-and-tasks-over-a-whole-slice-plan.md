---
docType: review
layer: project
reviewType: code
slice: plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: f0cc31a5ba689da4cd7ead7c89dd5ab5a5d2f692
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
diffTruncated: false
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Single-source loop grammar replaces three copies"
    location: "src/squadron/pipeline/loop_config.py:1-139"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Each source returns items consistently with `flag_reason`"
    location: "src/squadron/pipeline/sources.py:1-179"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "BatchReport wired into executor with item-scoped isolation"
    location: "src/squadron/pipeline/batch_report.py:1-161"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Phase ordering: set_arch → set_slice → set_phase → build_context"
    location: "src/squadron/pipeline/steps/phase.py:160-184"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Dispatch `feedback: review` produces well-typed errors"
    location: "src/squadron/pipeline/actions/dispatch.py:184-225"
  - id: F006
    severity: note
    category: uncategorized
    summary: "Synchronous report write and YAML dump run on the event loop"
    location: "src/squadron/pipeline/executor.py:1464-1470"
  - id: F007
    severity: note
    category: uncategorized
    summary: "StateManager re-instantiated to access `runs_dir`"
    location: "src/squadron/pipeline/executor.py:1466"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Review artifact traceability keys are wired end-to-end"
    location: "src/squadron/review/persistence.py:348-426"
  - id: F009
    severity: pass
    category: uncategorized
    summary: "CLI JSON stdout stays parseable; save messages go to stderr"
    location: "src/squadron/cli/commands/review.py:107-113,403-407"
  - id: F010
    severity: pass
    category: uncategorized
    summary: "Validation surfaces inner-step errors and bans nesting"
    location: "src/squadron/pipeline/steps/collection.py:114-135, src/squadron/pipeline/steps/loop.py:206-219"
---

# Review: code — slice 195

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Single-source loop grammar replaces three copies

The `LoopCondition`, `ExhaustBehavior`, `LoopConfig`, `parse_loop_config`, `last_with_verdict`, and `evaluate_condition` all live in `loop_config.py` now; the executor re-exports them for back-compat. `met_by_verdict` is the single definition of verdict sets — `_accept_arg` in `sources.py` and `_loop_exhaust_result` in `executor.py` both reference it. Tests covering this (`test_met_by_verdict`, the `met_by_verdict` parametrization, the `loop-config`'s own `test_accept_if_…` set) confirm the threshold semantics are now load-bearing and not duplicated.

### [PASS] Each source returns items consistently with `flag_reason`

`_cf_unfinished_slices`, `_cf_undesigned_slices`, and `_cf_untasked_slices` all produce the same shape (`{index, name, status, design_file}`), and only `untasked_slices` adds `flag_reason`. `_plan_arg` rejects non-digit plans with a clear message, exercising the documented "garbage reaches cf" guard. Tests cover the digit/non-digit boundary including `"{plan}"` (unresolved placeholder), `900-slices.maintenance-and-refactoring` (slice-plan stem), and `"9a"` (mixed). `_design_review_flag` computes the review path the same way the save path names it — single definition — and the archived-predecessor rule is documented in code.

### [PASS] BatchReport wired into executor with item-scoped isolation

`BatchItemRecord.from_item` collapses to FLAGGED when `failure_reason` is set, to ACCEPTED when any inner step ran an `accepted` loop, otherwise PASSED. Frontmatter ordering (`docType → pipeline → runId → plan → passed/accepted/flagged`) is pinned by the `test_frontmatter_parses_and_counts_match` snapshot. `_run_each_item` clones both `prior_outputs` and `step_outputs` per item so item N+1 never sees item N's review — the regression test `test_items_do_not_see_each_others_outputs` proves it with a concrete finding-vs-finding comparison.

### [PASS] Phase ordering: set_arch → set_slice → set_phase → build_context

`set_arch` is prepended only when `plan:` is set, with `set_slice` and `set_phase` swapped (slice now precedes phase) so cf's switching rule (arch switches initiative and plan, slice must be in that plan, phase follows) holds. Tests `test_expand_with_plan_sets_arch_first` and `test_expand_without_plan_has_no_set_arch` pin both branches.

### [PASS] Dispatch `feedback: review` produces well-typed errors

`DispatchFeedbackError` is caught specifically before the broader exception ladder, so an out-of-scope feedback resolves to a typed `success=False` result with the message intact rather than `success=True` with empty outputs. The findings block precedes the "Revise in place" instruction; the order is tested.

### [NOTE] Synchronous report write and YAML dump run on the event loop

`report.write(StateManager(runs_dir=runs_dir).runs_dir)` is called from inside the async `_execute_each_step`. The project's async rule states that any synchronous call inside `async def` must guarantee sub-millisecond execution in the worst case; `yaml.safe_dump` plus `Path.write_text` of an unbounded batch report does not meet that bar. The sibling path in `review.py::_review` (saving review artifacts) already uses `asyncio.to_thread` for the same reason. Worth applying the same pattern here for consistency, though typical batches will be small enough that the impact is unobservable. A separate autouse fixture in `tests/conftest.py` already isolates `_DEFAULT_RUNS_DIR` so test runs do not pollute the developer's real `~/.config/squadron/runs` — this is the right defensive move and was added in this slice.

### [NOTE] StateManager re-instantiated to access `runs_dir`

`StateManager(runs_dir=runs_dir).runs_dir` constructs a new StateManager just to read its `runs_dir` property back. Cheap but redundant — `runs_dir` is already in scope at the call site (and is the source the new manager immediately re-resolves). Either threading `runs_dir` directly into `report.write(runs_dir)` or moving the `runs_dir` accessor onto a module-level helper would remove the double allocation.

### [PASS] Review artifact traceability keys are wired end-to-end

`run_id` and `squadron_version` (and `providerFailure: true` for failure artifacts) are appended by the shared `_review_frontmatter_lines` and survive byte-identity for the pre-migration fixtures via the pinned `squadron_version="0.0.0-test"` argument the migration tests pass in. `result.run_id = context.run_id` is set before persistence; the `ReviewAction._review` failure path plumbs `run_id` through `_save_failure_artifact` so a provider-failure artifact carries the run id too. Tests verify ordering (`runId` after `dateUpdated`, `squadronVersion` immediately after `runId`) and that a CLI-authored review carries no `runId` key.

### [PASS] CLI JSON stdout stays parseable; save messages go to stderr

The new `_report_console(json_stdout)` helper routes save reports to stderr when `--output json` is active, and the regression tests `test_saved_line_goes_to_stderr_under_json_output` / `test_saved_line_stays_on_stdout_otherwise` pin both branches. `OutputMode` is a `StrEnum` so the match arms are exhaustive by construction.

### [PASS] Validation surfaces inner-step errors and bans nesting

`EachStepType._validate_inner_steps` delegates each inner step's validation through its own step-type impl, so a malformed inner `design:` step is reported at the `each` step's `phase` field rather than failing later. Both nesting bans (`each` inside `each`, `each` inside `loop`) emit messages naming the offending step. Test coverage exercises both.

### Run Digest

- Response length: 6907 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 23363
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
