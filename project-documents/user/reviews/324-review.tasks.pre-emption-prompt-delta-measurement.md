---
docType: review
layer: project
reviewType: tasks
slice: pre-emption-prompt-delta-measurement
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/324-tasks.pre-emption-prompt-delta-measurement.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260728
dateUpdated: 20260728
findings:
  - id: F001
    severity: concern
    category: test-organization
    summary: "Test-with pattern broken for T11 — CLI tests deferred to T12"
    location: project-documents/user/tasks/324-tasks.pre-emption-prompt-delta-measurement.md
  - id: F002
    severity: note
    category: code-organization
    summary: "`read_fragment_body` added in T8 instead of T3 — file I/O cohesion gap"
    location: src/squadron/metrology/preemption.py
  - id: F003
    severity: note
    category: test-coverage
    summary: "SC3 verification is structural, not explicitly tested"
    location: src/squadron/pipeline/actions/dispatch.py
  - id: F004
    severity: note
    category: task-sizing
    summary: "T12 is relatively large — combines delta CLI implementation with all CLI tests"
    location: project-documents/user/tasks/324-tasks.pre-emption-prompt-delta-measurement.md
  - id: F005
    severity: pass
    category: completeness
    summary: "All nine success criteria from the slice design are covered by tasks"
    location: project-documents/user/tasks/324-tasks.pre-emption-prompt-delta-measurement.md
  - id: F006
    severity: pass
    category: sequencing
    summary: "Task sequencing respects dependencies with no circular dependencies"
    location: project-documents/user/tasks/324-tasks.pre-emption-prompt-delta-measurement.md
  - id: F007
    severity: pass
    category: commit-strategy
    summary: "Commit checkpoints distributed throughout, not batched at end"
    location: project-documents/user/tasks/324-tasks.pre-emption-prompt-delta-measurement.md
---

# Review: tasks — slice 324

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] Test-with pattern broken for T11 — CLI tests deferred to T12

T11 implements `sq metrology preempt generate` (including `--check`) but contains no tests of its own. Its tests are bundled into T12, which first implements `sq metrology audit delta` and then adds `tests/metrology/test_preemption_cli.py` alongside extensions to `tests/metrology/test_audit_cli.py`. This means T11 is committed (`feat(cli): add sq metrology preempt generate with --check`) without any test coverage, and the tests for T11's implementation arrive only after T12's own implementation is complete. The evaluation criteria require that test tasks immediately follow their implementation tasks. The fix is straightforward: either move the `preempt generate` CLI test cases into T11 (with its own commit like `test(cli): cover preempt generate`), or split T12 so that T12 implements `audit delta` and a T12b adds all CLI tests. As written, a junior AI completing T11 would commit a CLI command with no verification that it works.

### [NOTE] `read_fragment_body` added in T8 instead of T3 — file I/O cohesion gap

T3 defines `write_fragment`, `read_fragment_header`, and `check_freshness` — all the file I/O functions for `preemption.py`. T8 then adds `read_fragment_body(path: Path) -> str | None` as a conditional afterthought ("add ... to `preemption.py` in this task if T3 did not already cover a full-text read"). This function logically belongs with T3's other I/O functions and should be tested in T4 alongside the header-read failure modes. As written, T4's tests don't cover `read_fragment_body` in isolation; its behavior is only exercised through T10's dispatch-level tests. Not blocking since T10 does test all three failure modes through the dispatch path, but the function would be better placed and tested in T3/T4.

### [NOTE] SC3 verification is structural, not explicitly tested

Success criterion 3 states: "Dispatch never queries the metrology store at runtime — asserted by inspection/test that no code path from `DispatchAction` reaches `MetrologyStore`." The design verifies this by inspection (Ground-truth fact 2, Decision 1), and the task implementation structurally guarantees it (T8 reads a file path, not the store). However, no task explicitly adds a test asserting that `dispatch.py` does not import or reach `MetrologyStore`, nor a test that dispatch succeeds when the store is absent. T10's "absent param → prompt unchanged" test and T13's "unmodified pipeline → byte-identical prompt" implicitly cover this, but the criterion's "asserted by inspection/test" language suggests a more deliberate verification step. A junior AI could add a simple import-level assertion or a comment in T8 noting the structural guarantee.

### [NOTE] T12 is relatively large — combines delta CLI implementation with all CLI tests

T12 implements `sq metrology audit delta` (including error handling, output rendering, and `run_audit` integration) AND adds `tests/metrology/test_preemption_cli.py` AND extends `tests/metrology/test_audit_cli.py` with six test cases covering both CLI commands. This is a substantial task for a junior AI. If the test-with pattern concern above is addressed by moving `preempt generate` tests into T11, T12 becomes more reasonably sized (delta CLI + delta CLI tests only). As written, it combines implementation and testing for two separate CLI commands in one task.

### [PASS] All nine success criteria from the slice design are covered by tasks

Every success criterion traces to at least one task: SC1 (fragment generation) → T2/T3/T11; SC2 (dispatch threading + byte-identical) → T8/T9/T10; SC3 (no store at runtime) → T8/T10/T13 (implicitly); SC4 (delta command) → T5/T12; SC5 (floor-relative delta) → T5/T6/T12; SC6 (disclaimer) → T1/T5/T6; SC7 (freshness check) → T3/T4/T11/T12; SC8 (failure mode degradation) → T8/T10; SC9 (existing tests pass) → T9/T10/T13. No gaps identified.

### [PASS] Task sequencing respects dependencies with no circular dependencies

The suggested order (T1→T2→T3→T4→T5→T6→T7→T8→T9→T10→T11→T12→T13) is correct: models (T1) before generators (T2/T3), tests (T4) after I/O, delta computation (T5/T6) before CLI (T12), config key (T7) before CLI (T11), dispatch injection (T8) before step threading (T9) before tests (T10). No task depends on a later task. The only minor ordering question is T8→T9 (T8 adds the dispatch method, T9 threads the param through steps), but these are independent changes that T10 tests together.

### [PASS] Commit checkpoints distributed throughout, not batched at end

Each of the 13 tasks has its own commit message with a conventional-commit prefix (`feat`, `test`), and commits are interleaved with implementation throughout the sequence rather than batched at the end. T13's final commit covers end-to-end verification, which is appropriate as a closing checkpoint.
