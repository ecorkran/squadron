---
docType: review
layer: project
reviewType: tasks
slice: fan-out-fan-in-step-type
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/182-tasks.fan-out-fan-in-step-type.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260415
dateUpdated: 20260415
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "ModelPoolNotImplemented error path untested"
    location: Task 13
  - id: F002
    severity: concern
    category: consistency
    summary: "SDK session guard error message mismatches slice design"
    location: Task 11
  - id: F003
    severity: note
    category: test-coverage
    summary: "Branch exception fast-fail path untested"
    location: Task 13
  - id: F004
    severity: note
    category: test-coverage
    summary: "Default `fan_in` reducer value not explicitly tested"
    location: Task 13
  - id: F005
    severity: note
    category: process
    summary: "Sparse commit checkpoints for 14 tasks"
    location: Tasks 1–14
  - id: F006
    severity: pass
    category: completeness
    summary: "All functional success criteria have implementation tasks"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Task sequencing respects all dependencies with no cycles"
  - id: F008
    severity: pass
    category: scope
    summary: "No scope creep detected"
  - id: F009
    severity: pass
    category: sizing
    summary: "Task sizes are appropriately scoped for a junior AI"
---

# Review: tasks — slice 182

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] ModelPoolNotImplemented error path untested

Success criterion FR3 requires that a pool reference raises `ModelPoolNotImplemented` with a clear error message when slice 181 is not available. Task 13 tests the happy path (mocked resolver returns models successfully for `pool:review` with `n: 2`), but no task tests the error path where `resolver.resolve()` raises `ModelPoolNotImplemented`. An integration test or unit test should verify that the `ModelPoolNotImplemented` exception from the resolver propagates with a clear message, matching the slice's explicit requirement.

### [CONCERN] SDK session guard error message mismatches slice design

Task 11 specifies the SDK session guard error as `"fan_out is not supported inside an SDK session pipeline; use agent-path dispatch"`. The slice design specifies `"fan_out is not supported inside an SDK session step; use profile-based dispatch"`. These differ in two ways: (1) "pipeline" vs "step" and (2) "agent-path dispatch" vs "profile-based dispatch". These should be reconciled — either the task or the slice should be updated so they agree on the exact wording, since the error message is a user-facing contract.

### [NOTE] Branch exception fast-fail path untested

The slice design explicitly describes two failure modes: (a) a branch raising an exception, which propagates immediately via `asyncio.gather(return_exceptions=False)` (true fast-fail), and (b) a branch returning `StepResult(status=FAILED)`, which is gathered normally and checked afterward. Task 13 only tests case (b). Case (a) is handled by `asyncio.gather`'s default behavior and doesn't require new code, so the risk is low. However, an integration test confirming that a branch exception causes the step to fail without calling the reducer would strengthen confidence in the fast-fail semantics.

### [NOTE] Default `fan_in` reducer value not explicitly tested

The slice states that `collect` is the default reducer when `fan_in` is not specified. Task 11 implements this via `resolved_config.get("fan_in", "collect")`. However, no integration test verifies that omitting `fan_in` from the YAML config results in `collect` behavior. All Task 13 integration tests that use `collect` appear to specify it explicitly. A test case with no `fan_in` key confirming default `collect` behavior would close this gap.

### [NOTE] Sparse commit checkpoints for 14 tasks

Only 3 commit checkpoints exist across 14 tasks: after Task 8, after Task 13, and after Task 14. Tasks 1 (enum), 9–10 (step type + validation), and 11–12 (executor + wiring) are all independently functional units that could each warrant a commit. Adding a checkpoint after Task 10 (step type and validation are complete and independently testable) would improve rollback granularity and make incremental progress visible.

### [PASS] All functional success criteria have implementation tasks

Every functional requirement (FR1–FR6) and technical requirement (TR1–TR4) from the slice design traces to at least one implementation task:
- FR1 (registration): Tasks 1, 9, 12
- FR2 (explicit models): Tasks 5, 11, 13
- FR3 (pool models): Tasks 11, 13 (happy path; error path gap noted above)
- FR4 (branch failure): Tasks 11, 13
- FR5 (first_pass reducer): Tasks 7, 8, 13
- FR6 (validation): Tasks 9, 10
- TR2–TR4 (async gather, linting, test coverage): Tasks 11, 14, 4/6/8/10/13

### [PASS] Task sequencing respects all dependencies with no cycles

The dependency chain is linear and logical: enum (T1) → protocol (T3) → reducers (T5, T7) → step type (T9) → executor (T11) → wiring (T12) → integration tests (T13) → validation (T14). Test tasks immediately follow their corresponding implementation tasks (T3→T4, T5→T6, T7→T8, T9→T10). No circular dependencies exist.

### [PASS] No scope creep detected

Every task traces directly to a success criterion or to scaffolding required by test tasks. No tasks implement features excluded from the slice (unanimous convergence, finding merge logic, UI/CLI surface).

### [PASS] Task sizes are appropriately scoped for a junior AI

Each task has clear, specific success criteria and a bounded scope. The largest tasks (T11: executor implementation, T13: integration tests) are on the upper bound of appropriate but remain coherent single-purpose tasks with explicit checklists. They would not benefit from being split further since their sub-parts are tightly coupled.
