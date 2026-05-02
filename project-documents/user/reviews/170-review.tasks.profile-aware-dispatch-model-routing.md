---
docType: review
layer: project
reviewType: tasks
slice: profile-aware-dispatch-model-routing
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/170-tasks.profile-aware-dispatch-model-routing.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260501
dateUpdated: 20260501
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Renderer signature and `_BUILDERS` dispatch update not explicitly tasked"
    location: src/squadron/pipeline/prompt_renderer.py:123-150
  - id: F002
    severity: concern
    category: commit-strategy
    summary: "Single commit checkpoint batches all implementation"
    location: project-documents/user/tasks/170-tasks.profile-aware-dispatch-model-routing.md
  - id: F003
    severity: concern
    category: task-clarity
    summary: "T10 has open-ended decision branching unsuitable for junior AI"
    location: src/squadron/pipeline/actions/dispatch.py:90-125
  - id: F004
    severity: note
    category: test-coverage
    summary: "SC5 lacks explicit test task"
    location: unverified
  - id: F005
    severity: note
    category: test-organization
    summary: "Minor test file location discrepancy with slice test plan"
    location: unverified
  - id: F006
    severity: pass
    category: completeness
    summary: "All six success criteria have corresponding task coverage"
    location: unverified
  - id: F007
    severity: pass
    category: test-sequencing
    summary: "Test-with pattern is correctly followed"
    location: unverified
  - id: F008
    severity: pass
    category: sequencing
    summary: "Task sequencing respects dependencies with no circular dependencies"
    location: unverified
---

# Review: tasks — slice 170

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Renderer signature and `_BUILDERS` dispatch update not explicitly tasked

The slice design (Section 1) explicitly calls out that `_render_dispatch`'s signature must change from `(config, params)` to `(config, params, resolver)`, and that `_BUILDERS` dispatch in `_build_action_instruction` must be updated to pass the resolver to the `DISPATCH` entry. T4 describes changing `model_id, _ = resolver.resolve(...)` to capture the profile, which implies the resolver is already available — and T1's reconnaissance step expects to confirm this. However, if the resolver is NOT already a parameter, a junior AI following T4 literally would produce code that doesn't compile. The task should include an explicit step: "If resolver is not already a parameter of `_render_dispatch`, add it and update the `_BUILDERS` dispatch for `ActionType.DISPATCH` to pass `resolver` (mirroring how `SUMMARY` already does)." This eliminates the risk of a silent gap between T1's read-only confirmation and T4's implementation.

### [CONCERN] Single commit checkpoint batches all implementation

T14 creates one monolithic commit for all changes across five distinct logical units: (1) the `_one_shot_dispatch` extraction refactor (T2–T3), (2) the renderer fix (T4–T5), (3) the new hidden subcommand (T6–T8), (4) the slash handler update (T9), and (5) the SDK error fix (T10–T11). If any later task introduces a defect, there is no granular rollback point. Best practice is to commit after each test-with pair (T3, T5, T8) and after T9 and T11, yielding ~5 focused commits rather than one. The task file should specify intermediate commit points with descriptive messages.

### [CONCERN] T10 has open-ended decision branching unsuitable for junior AI

T10 instructs the implementer to "Determine where to add the `is_error` check" with multiple options (in `SDKExecutionSession.dispatch` vs. in `_dispatch_via_session`), a "preferred" choice, and a fallback that says "document what is missing and add a `# TODO(240)` comment — do not silently skip the fix." While the escape hatch is good, the branching logic means a junior AI must evaluate `translate_sdk_message` output, decide whether to modify `sdk_session.py` or `dispatch.py`, and potentially leave a TODO instead of completing the work. This should be restructured: first a dedicated read-and-decide sub-step (like T1), then a concrete implementation step with the preferred path fully specified, and a separate conditional step for the TODO fallback only if the preferred path is infeasible.

### [NOTE] SC5 lacks explicit test task

Success criterion 5 ("From a real terminal, `sq run P4 183` with default model continues to use the SDK session path") has no dedicated test task. It is covered implicitly by T3's regression check on the `_one_shot_dispatch` extraction and T12's full-suite run, but no test explicitly asserts that the default-model path selects `_dispatch_via_session`. If existing tests already cover this, no action is needed; if not, a brief unit test asserting the routing decision would close the gap.

### [NOTE] Minor test file location discrepancy with slice test plan

The slice design's test plan specifies integration tests in `tests/pipeline/test_dispatch_synthetic_error.py`, but T11 places them in `tests/pipeline/actions/test_dispatch_session.py`. This is a cosmetic difference and the tasks' choice may be more consistent with the existing file structure, but it should be confirmed that the test discoverability is not affected.

### [PASS] All six success criteria have corresponding task coverage

SC1 → T4+T5+T6+T7+T8; SC2 → T9+T13; SC3 → T6+T8+T13; SC4 → T4+T5; SC5 → T3+T12 (implicit); SC6 → T10+T11. No success criterion is entirely unaddressed.

### [PASS] Test-with pattern is correctly followed

Every implementation task is immediately followed by its corresponding test task: T2→T3, T4→T5, T6+T7→T8, T10→T11. No test task is separated from its implementation by unrelated work.

### [PASS] Task sequencing respects dependencies with no circular dependencies

T1 (read) → T2 (extract helper) → T3 (test extraction) → T4 (fix renderer) → T5 (test renderer) → T6 (implement subcommand, depends on T2's helper) → T7 (register) → T8 (test subcommand) → T9 (slash handler) → T10 (SDK error fix) → T11 (test error fix) → T12 (full suite) → T13 (verification) → T14 (commit) → T15 (docs). All dependencies are satisfied by ordering; no circular dependencies exist.
