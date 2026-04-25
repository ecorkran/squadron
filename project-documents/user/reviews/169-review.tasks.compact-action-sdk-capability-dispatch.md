---
docType: review
layer: project
reviewType: tasks
slice: compact-action-sdk-capability-dispatch
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/169-tasks.compact-action-sdk-capability-dispatch.md
aiModel: moonshotai/kimi-k2.6
status: complete
dateCreated: 20260422
dateUpdated: 20260422
findings:
  - id: F001
    severity: concern
    category: capability-discovery
    summary: "Prompt-only capability probe omitted"
    location: T3 — Capability probe in the SDK executor
  - id: F002
    severity: concern
    category: testing
    summary: "True CLI compose-pattern integration test missing"
    location: T10 — Integration test: compose pattern
  - id: F003
    severity: note
    category: documentation
    summary: "Slice number inconsistency (193 vs 169)"
    location: T11 commit message; slice design branch name
  - id: F004
    severity: note
    category: logging
    summary: "Compact boundary metadata logging to run state not explicit"
    location: T6 — CompactAction: prompt-only branch
  - id: F005
    severity: note
    category: testing
    summary: "Timeout path for compact_boundary await untested"
    location: T6 — Tests for prompt-only branch
---

# Review: tasks — slice 169

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.6

## Findings

### [CONCERN] Prompt-only capability probe omitted

The slice design's Architecture section states the capability probe fires for both environments: "called once per session in the executor (true CLI on `ClaudeSDKClient` start; **prompt-only on first init-message receipt**)". The Data Flow for prompt-only also references `context.session.capabilities` as "probed from SystemMessage init".

However, T3 explicitly states: "For prompt-only executor (no persistent session), capabilities remain None; `CompactAction` will handle the None case explicitly". If prompt-only capabilities are always `None`, `CompactAction`'s prompt-only branch will always fall through to the "compact not available" informational path and will never dispatch `/compact` via `query()`. This directly undermines functional success criterion #1 ("`compact:` action works in all three execution environments") and technical criterion #7. The task breakdown should either implement the prompt-once probe on first init-message receipt or reconcile the contradiction with the slice design.

---

### [CONCERN] True CLI compose-pattern integration test missing

Functional success criterion #6 requires: "A test pipeline exercising `summarize` → `compact` → `summarize restore:true` runs to completion in at least one prompt-only environment **and in true CLI**."

T10 authors the `test-compact-compose.yaml` pipeline and tasks a prompt-only integration test for it, but does not task a corresponding true CLI integration test for the same compose pattern. T12's true CLI verification ("Run an existing compact-using pipeline end-to-end via `sq run`") is a regression test for legacy compact behavior, not a verification that the new `summarize → compact → summarize restore:true` composition works end-to-end in true CLI. Add an integration test that runs `test-compact-compose.yaml` through the true CLI executor (or a mocked SDK session rotate flow) to satisfy the success criterion.

---

### [NOTE] Slice number inconsistency (193 vs 169)

Multiple references to slice **193** remain in documents that have been renumbered to **169**:
- T11 commit message: `docs: update compact/summarize authoring guide for slice 193 behavior`
- Slice design branch name: `193-slice.rotation-strategy-control-compact-vs-summarize-new-session`
- Slice design body contains multiple "post-193" and "slice 193" references

Update these to **169** to avoid confusion during implementation and code archaeology.

---

### [NOTE] Compact boundary metadata logging to run state not explicit

Success criterion #4 states: "`pre_tokens` and `trigger` from the compact boundary are **logged into pipeline run state**." T6 tasks returning these values in `ActionResult.outputs`, but does not explicitly task writing them to pipeline run state alongside other per-step metadata as described in the slice design's State Management section. Ensure the task explicitly covers persisting `pre_tokens`, `trigger`, and timestamp to run state, not just returning them in the action result.

---

### [NOTE] Timeout path for compact_boundary await untested

T6's implementation specifies: "if it never arrives, raise `TimeoutError` after a reasonable bound (configurable; default 120s)". The test subtasks cover the happy path (boundary arrives), blocking behavior, and missing capabilities, but do not include a test for the timeout/never-arrives error path. Consider adding a test that mocks a `query()` response which never emits the boundary message and asserts that `TimeoutError` is raised within the bounded window.
