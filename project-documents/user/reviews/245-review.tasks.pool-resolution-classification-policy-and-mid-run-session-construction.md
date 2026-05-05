---
docType: review
layer: project
reviewType: tasks
slice: pool-resolution-classification-policy-and-mid-run-session-construction
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/tasks/245-tasks.pool-resolution-classification-policy-and-mid-run-session-construction.md
aiModel: deepseek/deepseek-v4-pro
status: complete
dateCreated: 20260504
dateUpdated: 20260504
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "No task implements the dispatch‑action guard for pool‑uncertain‑SDK‑at‑runtime with no session"
    location: unverified
  - id: F002
    severity: concern
    category: testing
    summary: "Task T15 does not cover `test_sdk_wiring.py` despite success criterion 9"
    location: unverified
  - id: F003
    severity: note
    category: testing
    summary: "No explicit integration‑level test that startup session construction is skipped under lazy default"
    location: unverified
  - id: F004
    severity: note
    category: scope
    summary: "Task T9 is large but cohesive; consider splitting"
    location: src/squadron/pipeline/executor.py
  - id: F005
    severity: pass
    category: process
    summary: "Task sequencing follows test‑with pattern and respects dependencies"
    location: 245-tasks.pool-resolution-classification-policy-and-mid-run-session-construction.md
  - id: F006
    severity: pass
    category: non-functional-requirements
    summary: "No load‑test requirement is present or missing"
    location: 245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md
---

# Review: tasks — slice 245

**Verdict:** FAIL
**Model:** deepseek/deepseek-v4-pro

## Findings

### [FAIL] No task implements the dispatch‑action guard for pool‑uncertain‑SDK‑at‑runtime with no session

Success criterion 4 requires that when a pool‑uncertain step selects an SDK alias at runtime and no persistent session exists, the step returns `FAILED` with a message that identifies the step and the `--strict` remediation. The slice design explicitly describes this guard in the dispatch action and lists the test `test_lazy_pool_selects_sdk_no_session_fails_with_clear_error` in its test‑coverage table. Neither the guard implementation nor this test appear in any task. This leaves a documented failure mode unhandled.

### [CONCERN] Task T15 does not cover `test_sdk_wiring.py` despite success criterion 9

Success criterion 9 states “All existing tests in `test_run_pipeline_sdk.py` **and `test_sdk_wiring.py`** pass (updated where needed…).” T15 only directs attention to `test_classification.py` and `test_run_pipeline_sdk.py`. If `test_sdk_wiring.py` exists and contains pool‑uncertain‑dependent tests, they may break silently under the new default.

### [NOTE] No explicit integration‑level test that startup session construction is skipped under lazy default

Criterion 1 (no persistent session constructed at startup for POOL_UNCERTAIN‑only pipelines) relies on the classification change producing `needs_persistent_session=False` and the existing startup code honouring that return value. T4 tests the classification logic, and T10 tests the mid‑run hook, but no task verifies the end‑to‑end startup path (e.g., mocking the session constructor and asserting it is never called). The risk is low given existing tests are updated in T15, but a dedicated integration test would strengthen coverage.

### [NOTE] Task T9 is large but cohesive; consider splitting

T9 bundles four changes into one task: adding the `pool_policy` parameter, the mid‑run session‑construction hook, `_connect_lazy_session`, and `_step_needs_sdk`. All are tightly related to the executor, but the private helpers (`_connect_lazy_session` and `_step_needs_sdk`) could each be their own task + test pair to reduce the risk of junior‑AI mistakes. The current grouping is acceptable if the implementor is comfortable with multi‑step tasks.

### [PASS] Task sequencing follows test‑with pattern and respects dependencies

Every implementation task (T1, T3, T5, T7, T9, T11, T13) is immediately followed by a corresponding test task (T2, T4, T6, T8, T10, T12, T14). Dependencies flow naturally from the enum (T1) through classification updates (T3, T5) to the executor (T9) and CLI wiring (T13). The YAML‑schema tasks (T7/T8) are independent and correctly placed in parallel. Commit checkpoints (T16–T18) are distributed at the end, which is appropriate for a focused slice.

### [PASS] No load‑test requirement is present or missing

The slice design does not restate any non‑functional requirement (performance, throughput, etc.), so no load‑test task in `tests/load/` is needed, and no CI‑wiring task is omitted.
