---
docType: review
layer: project
reviewType: tasks
slice: pipeline-executor-and-loops
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/149-tasks.pipeline-executor-and-loops.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260403
dateUpdated: 20260403
---

# Review: tasks — slice 149

**Verdict:** CONCERNS
**Model:** z-ai/glm-5

## Findings

### [CONCERN] Task T7 has dependency on T8 but T7 is sequenced first

T7 (Collection Step Type) states it should "import source registry from executor" for validation, but the source registry is not implemented until T8 (Source Registry and `each` Execution). This creates a dependency cycle. The validation step in T7 that checks "Namespace and function must be known in source registry" cannot be completed without T8's `_SOURCE_REGISTRY` existing first.

**Recommendation:** Either:
1. Move T8 before T7, or
2. Modify T7's validation to defer source registry checking to executor-time (the slice design notes that unknown sources raise `ValueError` in `_parse_source()` which is executor-side)

### [CONCERN] Task T5 is too large and should be split

T5 (Core Executor) contains ~15 implementation items and ~9 test cases covering:
- Parameter merging and validation
- Step type lookup and expansion
- Full action execution loop
- `prior_outputs` threading
- Checkpoint pause handling
- Action failure handling
- `start_from` skip logic
- Callback invocation

This is too much for a junior AI to complete in one task. The test-with pattern is followed correctly, but the scope is still too broad.

**Recommendation:** Split T5 into two tasks:
- T5a: Parameter merging, `start_from` skip logic, and basic step/action loop (success path)
- T5b: Error handling (checkpoint pause, action failure, missing params), `prior_outputs` threading

### [PASS] All success criteria have corresponding tasks

Cross-reference mapping:
- **SC1** (simple pipeline end-to-end) → T5
- **SC2** (step types expand, actions sequence) → T5
- **SC3** (parameter placeholders resolve) → T3
- **SC4** (missing required params error) → T5
- **SC5** (checkpoint pause stops executor) → T5
- **SC6** (action failure stops step) → T5
- **SC7** (retry loop max iterations) → T6
- **SC8** (until: review.pass terminates) → T4 + T6
- **SC9** (on_exhaust behavior) → T6
- **SC10** (each iterates over CF query) → T7 + T8
- **SC11** (item binding resolves) → T3 + T8
- **SC12** (on_step_complete callback) → T5
- **SC13** (start_from skips steps) → T5
- **SC14** (loop.strategy warning) → T6
- **Technical reqs** → T2, T5, T8, T10

### [PASS] No scope creep identified

All tasks trace back to slice design requirements. Test infrastructure (T1) is appropriate scaffolding for a complex feature.

### [PASS] Test-with pattern followed correctly

Each implementation task includes corresponding tests immediately after:
- T2 → result type tests
- T3 → `resolve_placeholders` tests
- T4 → `evaluate_condition` tests
- T5 → core executor tests
- T6 → retry loop tests
- T7 → `EachStepType` tests
- T8 → `each` execution tests
- T9 → integration tests

### [PASS] Commit checkpoints appropriately distributed

Commits are placed after major milestones:
- After T5 (core executor)
- After T6 (retry loops)
- After T8 (each/collection)
- After T10 (verification/cleanup)

This is appropriate distribution—not batched at the end.
