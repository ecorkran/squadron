---
docType: review
layer: project
reviewType: code
slice: implementation-batch-pipeline-implement-plan
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: 90a40dbf40289fd46b99e999c957a6e9295545be
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
durationSeconds: 23.6
squadronVersion: 0.19.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Item-resume HALTED path can mask a lost lock and leaves `raise AssertionError` as dead code"
    location: "src/squadron/pipeline/item_resume.py:118-135"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`typer.Exit` from the pipeline runner is swallowed and reclassified without logging"
    location: "src/squadron/cli/commands/run_item.py:88-93"
  - id: F003
    severity: concern
    category: design
    summary: "Function-local imports and private-symbol imports used to dodge a circular import"
    location: "src/squadron/cli/commands/run_item.py:44-50"
  - id: F004
    severity: concern
    category: structure
    summary: "`run()` entry point and `run.py` keep growing; `assert` used for control flow"
    location: "src/squadron/cli/commands/run.py:1199-1202"
  - id: F005
    severity: concern
    category: correctness
    summary: "Lock is not taken for implicit-resume and resume paths using a possibly different `definition`"
    location: "src/squadron/cli/commands/run.py:1231-1315"
  - id: F006
    severity: concern
    category: conventions
    summary: "Duplicated magic strings and keys scattered across modules"
    location: "src/squadron/pipeline/executor.py:1593"
  - id: F007
    severity: concern
    category: error-handling
    summary: "Exception-handling rule: `except GitEnvironmentError: raise` and unlogged swallows"
    location: "src/squadron/pipeline/actions/dispatch.py:320"
  - id: F008
    severity: concern
    category: concurrency
    summary: "Item resume has a read-modify-write race on `report.json` outside the lock for plain runs"
    location: "src/squadron/pipeline/run_lock.py:60-80"
  - id: F009
    severity: note
    category: correctness
    summary: "`_find_cycle` and `order_by_dependencies` rely on subtle invariants"
    location: "src/squadron/pipeline/sources.py:315-330"
  - id: F010
    severity: note
    category: testing
    summary: "Overall test coverage is strong"
    location: "tests/pipeline"
---

# Review: code — slice 197

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Item-resume HALTED path can mask a lost lock and leaves `raise AssertionError` as dead code

`resume_item` catches `OSError` broadly around the whole locked body (`_resume_locked`) and reports it as "cannot write the batch report". `_resume_locked` also runs git, cf and the model body. Any unrelated `OSError` (for example a `subprocess` or file error in `evaluate_each_source` or `load_pipeline`) will be mislabelled as a report-write failure. The handler also logs nothing itself. It relies on `batch_report` having logged, which is not true for other `OSError` sources. Narrow the catch to the report write, or log with `logger.exception` and use a neutral message. The trailing `raise AssertionError("unreachable")` after the `with` block is also dead code. Restructure so no unreachable statement is needed.

### [CONCERN] `typer.Exit` from the pipeline runner is swallowed and reclassified without logging

`except typer.Exit` converts any exit from `_run_pipeline_sdk` (classification error, lost session) into `ResumeExit.HALTED`. The original exit code is only printed, never logged, so automation reading logs gets no ERROR record. A `GitEnvironmentError` raised from `_run_pipeline_sdk` when `item_rerun` is set is re-raised (run.py:398) and handled in `resume_item`. Other exit paths do not go through that handler. Log at ERROR here for observability, per the failure-mode rule.

### [CONCERN] Function-local imports and private-symbol imports used to dodge a circular import

`handle_item_resume` imports the private `_apply_param_overrides` and `_run_pipeline_sdk` from `run.py`, and `run.py` imports this module. This is a circular dependency papered over with pyright suppressions. Test helpers do the same with `_kept_outputs` and `_flag_kind`. Move the shared pipeline-running functions and param parsing into a neutral module, or inject `_run_pipeline_sdk` and the override parser into `handle_item_resume`. This also fixes the DIP problem: `run_item` depends on the concrete `run` module.

### [CONCERN] `run()` entry point and `run.py` keep growing; `assert` used for control flow

`assert decision is not None  # check_item_flags` is stripped under `python -O` and relies on a call made elsewhere. `check_item_flags` should return the validated decision, or the check should be explicit. `run()` already carries many branches, and `_locked(definition, ...)` is repeated across four call sites, so a variation is easy to miss. Consider a single helper that picks SDK or prompt-only and takes the lock.

### [CONCERN] Lock is not taken for implicit-resume and resume paths using a possibly different `definition`

`_locked(definition, ...)` uses `definition` from the earlier scope. On `--resume` and the implicit-resume branches, the pipeline actually run is `state.pipeline` or `match.pipeline`. If `definition` was loaded from the CLI `pipeline` argument (or is `None` or stale), the mutating check is made against the wrong pipeline. A run could then execute without the lock, or a non-mutating one could take it. I did not see where `definition` is bound for those branches. Verify it is loaded from `state.pipeline` and `match.pipeline`, and add a test for it. `test_a_plain_resume_of_a_paused_run_with_the_lock_held_exits_2` mocks `StateManager`, which does not prove this.

### [CONCERN] Duplicated magic strings and keys scattered across modules

Project rules say to define comparison values once. Several keys are still literals. `"commit_each_iteration"` is defined in `run_lock.py` but is also a loop-config key. `"steps"`, `"dependencies"`, `"model"`, `"existing"` and `"feedback"` appear as raw strings in `run_lock.py`, `item_resume.py` and `item_resume_support`. `_open_dependencies` and `_step_mutates` re-implement step-tree walking, so a new step shape needs edits in several places. Prefer constants shared with the loader or loop config. `_step_mutates` also hand-parses the raw nested step dict format, which will drift from the loader.

### [CONCERN] Exception-handling rule: `except GitEnvironmentError: raise` and unlogged swallows

`except GitEnvironmentError: raise` exists only to stop a later clause from catching it. It is correct, but add a comment saying which clause it protects. `BatchReport.load` and `_write_atomic` are fine. In `_write_atomic`, a failed write can leave an orphan `.name.XXXX` temp file, because `delete=False` and no cleanup runs when `temp.replace` fails. Remove the temp file in the `except OSError` path.

### [CONCERN] Item resume has a read-modify-write race on `report.json` outside the lock for plain runs

The lock is only taken when `pipeline_mutates` is true. A non-mutating pipeline never takes it, so it can write `report.json` and run state beside a mutating run. `pipeline_mutates` classifies by step type but does not cover `each`, `fan_out` or custom steps that nest mutating steps unless `steps` happens to be a list of single-key dicts. Confirm that a mutating `each` body (as in `implement-plan`) is detected. The tests cover only named pipelines, not a synthetic nested `each`. Add a parametrized test for nested shapes.

### [NOTE] `_find_cycle` and `order_by_dependencies` rely on subtle invariants

`order_by_dependencies` is O(n²) per pop, which is fine at plan scale. `_find_cycle` takes `min(needs[path[-1]])` and assumes a non-empty set for every unplaced node. That holds for a Kahn remainder, but a node that is unplaced only because it depends on another unplaced node outside a cycle is still handled by the walk. This is correct, and the tests cover two- and three-node cycles.

### [NOTE] Overall test coverage is strong

New behavior has tests for the flag kinds, atomic report writes, lock contention (including a killed holder), the catch-up merge, item resume validation, and a real-git end-to-end `implement-plan` run. Failure modes assert ERROR or WARNING logs. Line lengths in `executor.py` (`_write_each_report` signature) and `actions/branch.py` appear to exceed 88 characters. Run `ruff` to confirm.

## Response (20261006)

- **F001 — fixed.** `resume_item` takes the lock, then runs the body in `try/finally` so the lock is released without a `with` block. The `raise AssertionError("unreachable")` is gone. The `OSError` handler now logs with `logger.exception` and uses a neutral "item resume halted" message, because the error can come from more than the report write.
- **F002 — fixed.** The swallowed `typer.Exit` in `run_item.handle_item_resume` now logs at ERROR with the runner's exit code.
- **F003 — fixed.** `run.py` parses the `--param` overrides and passes them to `handle_item_resume` along with `_run_pipeline_sdk`. The function-local import, the private-symbol imports and both pyright suppressions are gone. Tests that import private helpers are left as they are.
- **F004 — no change.** `assert decision is not None  # check_item_flags` follows the file's existing `assert pipeline is not None  # guarded above` convention, and `check_item_flags` exits before this line when the flags are invalid. `_locked` is already the single helper. The four call sites differ only in which coroutine they pass.
- **F005 — no change, incorrect.** `--resume` loads `definition` from `state.pipeline` (run.py, `definition = load_pipeline(state.pipeline)`). Implicit resume finds `match` with `find_matching_run(pipeline, ...)`, so `match.pipeline` is the pipeline `definition` was loaded from.
- **F006 — partly fixed.** `run_lock._step_mutates` now walks `StepConfig`s through the shared `unpack_inner_steps`, the same helper `branch_rules` uses, instead of hand-parsing raw step dicts. The `commit_each_iteration` and `steps` literals are used throughout the existing loop and collection step code. Centralizing them is outside this slice.
- **F007 — partly fixed.** `_write_atomic` now removes its temp file when the write or rename fails, and the existing failed-write test checks that no temp file is left. The `except GitEnvironmentError: raise` in `dispatch.py` already carries a comment.
- **F008 — partly fixed.** Nested shapes are detected: `implement-plan` (a mutating `each`) is already covered by `test_code_and_batch_pipelines_mutate`. Added `test_nested_steps_inside_each_decide_mutation`, which covers an `each` holding an implement, a committing loop, a loop holding tasks, and reviews only. No change for non-mutating runs. Each report is `{run_id}.{step}.report.json`, so two runs never write the same file, and running a non-mutating pipeline beside a batch is intended (D11).
- F009, F010: notes, no action. ruff passes.

### Run Digest

- Response length: 6775 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 23.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
