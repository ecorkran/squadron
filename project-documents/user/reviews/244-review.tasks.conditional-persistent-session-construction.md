---
docType: review
layer: project
reviewType: tasks
slice: conditional-persistent-session-construction
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/244-tasks.conditional-persistent-session-construction.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260504
dateUpdated: 20260504
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "All eight functional success criteria trace to tasks"
    location: unverified
  - id: F002
    severity: concern
    category: uncategorized
    summary: "T4 prescribes assigning to `resolver._on_pool_selection` private attribute from outside the class"
    location: src/squadron/cli/commands/run.py
  - id: F003
    severity: note
    category: uncategorized
    summary: "Test file location differs from slice design suggestion"
    location: tests/cli/test_run_pipeline_sdk.py
  - id: F004
    severity: note
    category: uncategorized
    summary: "Task IDs and design test IDs share the same namespace, creating potential confusion"
    location: unverified
  - id: F005
    severity: note
    category: uncategorized
    summary: "T9 is a conditional audit task that may expand scope"
    location: unverified
---

# Review: tasks — slice 244

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [PASS] All eight functional success criteria trace to tasks

Every functional requirement (FR1–FR8) from the slice design maps to at least one implementation task and at least one test scenario. Specifically: FR1/T6-T1, FR2/T6-T1+T2, FR3/T6-T3, FR4/T6-T4, FR5/T5+T6-T5, FR6/T7, FR7/T6-T8, FR8/T6-T3b. Technical requirements (ruff, pyright, full suite) are covered by T8 and T10. No success criteria are left uncovered.

### [CONCERN] T4 prescribes assigning to `resolver._on_pool_selection` private attribute from outside the class

T4 instructs: "In the `else:` path (pre-built resolver supplied), attach the callback directly: `resolver._on_pool_selection = lambda sel: state_mgr.log_pool_selection(_run_id, sel)`". The task acknowledges this accesses a private attribute and explicitly says "Do not add a new public setter method." While the decision is deliberate, it couples `_run_pipeline` to `ModelResolver`'s internal implementation — any rename or refactor of `_on_pool_selection` in `resolver.py` would silently break this code with no type-checker warning. The slice design's implementation section does not address this callback-attachment detail at all, so there is no design-level justification to reference. A public constructor parameter (e.g., `on_pool_selection` passed to `ModelResolver.__init__`) or a documented setter would be more robust and would still allow the same functional behavior. This is not blocking, but it creates a maintenance hazard that should be reconsidered.

### [NOTE] Test file location differs from slice design suggestion

The slice design suggests `tests/pipeline/test_conditional_session.py`, but tasks place all new tests in `tests/cli/test_run_pipeline_sdk.py`. This is a reasonable judgment call — the code under test (`_run_pipeline_sdk`) lives in `cli/commands/run.py` — but it diverges from the design's explicit suggestion. No action required; just noting the discrepancy.

### [NOTE] Task IDs and design test IDs share the same namespace, creating potential confusion

The task breakdown uses T1–T11 as task IDs. The slice design's test coverage table uses T1–T8 as test scenario IDs. Task T6's sub-items reference design test IDs (e.g., "T1", "T2", "T3") within a task named "T6", producing lines like "**T3b** — `claude_required_one_shot` shape" inside task T6. This is internally consistent once understood, but a reader encountering "T3" must infer from context whether it refers to task T3 or design test scenario T3. Using a different prefix (e.g., "S1"–"S8" for scenarios) would eliminate ambiguity.

### [NOTE] T9 is a conditional audit task that may expand scope

T9 is described as "a targeted audit, not a code change" but includes the conditional: "If any of the three guards are absent or broken, fix them in the respective action file and add a regression test." The slice design explicitly states these guards already exist and are correct. If the audit finds otherwise, the task would expand to code changes in `compact.py` and `summary.py` with no dedicated test task for those fixes. This is acceptable as a belt-and-suspenders check, but the task should be treated as potentially involving unplanned work.
