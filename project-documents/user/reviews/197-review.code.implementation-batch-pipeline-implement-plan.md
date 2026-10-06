---
docType: review
layer: project
reviewType: code
slice: implementation-batch-pipeline-implement-plan
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: 19d83bf23a6dcc9fea8bf0c539118fbe658ad88d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
diffTruncated: false
turns: 20
promptTokens: 2597933
cachedTokens: 2267248
completionTokens: 3833
reasoningTokens: 0
durationSeconds: 110.9
squadronVersion: 0.19.0
findings:
  - id: F001
    severity: note
    category: design
    summary: "`_take_run_lock` is not called for `--resume --item`"
    location: "src/squadron/cli/commands/run.py:1157"
  - id: F002
    severity: note
    category: correctness
    summary: "Preexisting operator-precedence bug in `resume_model`"
    location: "src/squadron/cli/commands/run.py:1232"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`in_flight` is reset to `None` after writing the per-item report"
    location: "src/squadron/pipeline/executor.py:1592-1598"
  - id: F004
    severity: concern
    category: correctness
    summary: "`_add_record`/`ItemRerun.replace` uses index equality for matching"
    location: "src/squadron/pipeline/batch_report.py:357-364"
  - id: F005
    severity: concern
    category: api-design
    summary: "`_check_record` accepts NOT_RUN items with any decision"
    location: "src/squadron/pipeline/item_resume.py:194"
  - id: F006
    severity: note
    category: design
    summary: "Two-state `_finish_each_report` parameter surface"
    location: "src/squadron/pipeline/executor.py:1466-1472"
  - id: F007
    severity: pass
    category: tests
    summary: "Tests comprehensively cover the slice"
    location: "tests/pipeline/test_item_resume_*.py"
  - id: F008
    severity: pass
    category: failure-modes
    summary: "Atomic report writes preserve prior report on failure"
    location: "src/squadron/pipeline/batch_report.py:343-360"
  - id: F009
    severity: pass
    category: validation
    summary: "Reserved param keys rejected at three boundaries"
    location: "src/squadron/pipeline/control_params.py"
  - id: F010
    severity: pass
    category: design
    summary: "`pipeline_mutates` is recursive and conservative"
    location: "src/squadron/pipeline/run_lock.py:51-72"
  - id: F011
    severity: pass
    category: correctness
    summary: "`ItemRerun.replace` and `_add_record` keep report ordering stable"
    location: "src/squadron/pipeline/batch_report.py:357-364"
---

# Review: code — slice 197

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [NOTE] `_take_run_lock` is not called for `--resume --item`

The `--resume --item` branch calls `handle_item_resume(...)` directly, bypassing `_locked`. That branch opens its own run lock via `resume_item` in `item_resume.py`, so behavior is correct, but the run-lock invariant is not expressed through `_locked` here. A future refactor of item-resume could lose the lock silently. Consider funneling this branch through a single helper, or commenting the deliberate deviation.

### [NOTE] Preexisting operator-precedence bug in `resume_model`

`resume_model = model or str(state.params.get("model")) if state.params.get("model") else model` is parsed as `((model or str(...)) if state.params.get("model") else model)`, so the stored model is never actually used. This is a preexisting bug and not introduced by the diff, but a touched line is a good time to fix it: the intent appears to be `model or state.params.get("model")`.

### [CONCERN] `in_flight` is reset to `None` after writing the per-item report

If the per-item `_write_each_report(report, runs_dir, final=False)` after a successful item raises (e.g. disk full), the exception propagates out of the `try` block. The `finally` then sees `in_flight=None` and only writes the report — but the in-flight item is not the one currently running, it was already complete, so the report already has its record. The exception is then re-raised, and the run halts with no `not_run` records. This is acceptable for disk-full mid-batch, but worth a test.

### [CONCERN] `_add_record`/`ItemRerun.replace` uses index equality for matching

`ItemRerun.replace` matches by `record.index`. If two items in a batch share the same `index` string (unusual but possible if a source returns duplicates), `next` would replace the first. The fresh batch report's records typically have unique indexes, but a resume path that selects the same item twice would silently misbehave. Worth either asserting uniqueness in `BatchItemRecord.from_item` or matching by identity.

### [CONCERN] `_check_record` accepts NOT_RUN items with any decision

The validation allows `ACCEPT` against a `NOT_RUN` item (which has `flag_kind=None`), but the test `tests/pipeline/test_item_resume_validation.py:71` asserts that `accept requires flagKind review_unresolved; item 404 is not_run` is rejected. The logic at line 200 catches this: `record.flag_kind is not FlagKind.REVIEW_UNRESOLVED` is true for NOT_RUN, so the `REJECTED` path fires. Working as intended, but the test name is slightly misleading — it tests that accept-on-NOT_RUN is rejected. Worth a clarifying comment.

### [NOTE] Two-state `_finish_each_report` parameter surface

`_finish_each_report` takes `in_flight`, `halt`, and `items` separately. The `halt is not None` branch records `not_run` for every item after the in-flight one; the non-halt branch (legacy fall-through) doesn't. If `in_flight` is set with `halt is None`, the in-flight item is recorded as `STEP_FAILED` with reason `"run halted before this item finished"`, but no `not_run` records are added for unreached items. This path is unreachable in practice (every `try/except` that sets `in_flight` then raises sets `halt` first), but the asymmetry is fragile. A small docstring update or guard at entry would help.

### [PASS] Tests comprehensively cover the slice

The new test files (`item_resume_validation`, `item_resume_params`, `item_resume_git`, `item_resume_source`, `item_resume_body`, `item_resume_plan_batches`) cover validation, parameter merging, git preconditions, source re-selection, body execution, and integration with `slices-plan`/`tasks-plan`. The failure-mode-enumeration rule is honored: timed-out counts, held locks, missing reports, dirty trees, unrelated branches, mid-item halts, and failed report writes each have an explicit assertion and observable signal.

### [PASS] Atomic report writes preserve prior report on failure

`_write_atomic` writes to a sibling temp file then renames; on `OSError` the temp is unlinked and the prior report is intact. The test `test_a_failed_write_keeps_the_previous_report_and_logs_error` confirms the no-temp-leak invariant (the trailing assertion checks for any `.*` temp files left in the dir).

### [PASS] Reserved param keys rejected at three boundaries

`reserved_param_error` is invoked by `_apply_param_overrides` (CLI), `validate_pipeline` (declared `params:`), and `item_params` (resume overrides). A `-p accept_decision=1` cannot reach the executor any other way; tests in `test_control_params.py` confirm each path. The constant is centralized in one module per the project convention.

### [PASS] `pipeline_mutates` is recursive and conservative

The check walks nested `loop:` and `each:` bodies via `unpack_inner_steps`, and a `loop:` with `commit_each_iteration: true` is treated as mutating. Tests confirm the four code pipelines and the planning pipelines resolve correctly.

### [PASS] `ItemRerun.replace` and `_add_record` keep report ordering stable

The resume path replaces by index, preserving the order of other records. Tests in `test_item_resume_body.py` assert that records `"401", "402", "403", "404"` stay in that order after resume and the other items' `decision` fields remain untouched.

## Response (20261006)

The first round's response is in `archive/`. Its fixes are 39dda24d.

- **F001 — no change.** Item resume takes the lock itself in `resume_item`, and the module docstring says so. Wrapping it in `_locked` as well would take the same lock twice in one process.
- **F002 — no change, incorrect.** The expression parses as `(model or str(stored)) if stored else model`, so a stored model is used whenever `--model` is absent. It is hard to read, but it behaves correctly.
- **F003 — no change.** The reviewer itself concludes the disk-full path is acceptable. The halt and the error are both logged.
- **F004 — no change.** Item indexes come from cf slice indexes, which are unique within a plan.
- **F005 — no change.** The reviewer confirms the behavior is correct. The test name states the rejection.
- **F006 — no change.** As the reviewer notes, every path that sets `in_flight` also sets `halt`.
- F007–F011: pass.

### Run Digest

- Response length: 6246 chars
- Response is newline-free: no
- Tool calls made: 33
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 512000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 0
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2597933 / 2267248 / 3833 / 0
- Duration: 110.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
