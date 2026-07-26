---
docType: review
layer: project
reviewType: tasks
slice: tech-debt-audit-baseline-harness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/323-tasks.tech-debt-audit-baseline-harness.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260726
dateUpdated: 20260726
resolutionDate: 20260726
findings:
  - id: F001
    severity: fail
    category: task-sequencing
    summary: "Config key registration (T19) is sequenced after T13 which reads `metrology.audit_timeout_s`"
    location: project-documents/user/tasks/323-tasks.tech-debt-audit-baseline-harness.md
    resolution: fixed
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Success criterion 9 (\"repeat-run clause does not apply\") lacks a corresponding test assertion"
    location: project-documents/user/tasks/323-tasks.tech-debt-audit-baseline-harness.md
    resolution: fixed
  - id: F003
    severity: note
    category: task-sizing
    summary: "T13 implements a large cohesive unit — agent execution, timeout, failure handling, parsing, and persistence in one task"
    location: project-documents/user/tasks/323-tasks.tech-debt-audit-baseline-harness.md
    resolution: acknowledged-no-change
  - id: F004
    severity: note
    category: process-gap
    summary: "No explicit push-to-remote step for canonical fork edits"
    location: project-documents/user/tasks/323-tasks.tech-debt-audit-baseline-harness.md
    resolution: fixed
---

# Review: tasks — slice 323

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Resolution (20260726)

Three findings fixed, one acknowledged without change. Verdict left as CONCERNS — this section records disposition only, not a re-review.

- **F001 (config ordering)** — Correct, and a genuine defect rather than a style preference: the task file's own T19 text said "this must precede any code that reads them" while being sequenced 86 lines *after* the task that reads `metrology.audit_timeout_s`. A self-contradiction that would have failed at implementation time, since `get_config` raises `KeyError` for an unregistered key. Config keys moved to **T11**, ahead of all `audit.py` work; tasks renumbered (old T11-T18 → T12-T19) and all six internal cross-references updated. An explicit ordering note now states the dependency so a future edit cannot silently re-break it.
- **F002 (missing assertion)** — Correct. T4 asserted the independent-run *marker* was present but never that T2's rewording of the repeat-run clause actually landed — so the design's success criterion ("the repeat-run clause does not apply") was unverified. Added an assertion to T4 that the repeat-run section references the marker as an explicit exception. This matters more than a normal coverage gap: an unconditional repeat-run clause would silently correlate variance runs and bias the measured noise floor toward zero.
- **F003 (T14 sizing)** — Acknowledged, no change. The reviewer's own analysis is the reason: splitting would create an artificial seam, because the design's Decision 9 makes failure handling *part of* the execution contract ("one run persists a complete `AuditRun` or nothing at all"), not a wrapper around it. A basic-execution task that persisted before the failure-handling task landed would be a partial-record path — precisely what the design forbids. The task remains substantial and the note stands as a heads-up to the implementer.
- **F004 (push step)** — Correct and worth making explicit. Added to T3: T1/T2 must be pushed to the fork remote before vendoring, since the criterion is presence in `github:ecorkran/tech-debt-audit`, not a local commit. Vendoring from an unpushed fork would satisfy squadron while leaving every other consumer on the pre-contract instrument — the exact silent divergence Decision 1a exists to prevent.

## Findings

### [FAIL] Config key registration (T19) is sequenced after T13 which reads `metrology.audit_timeout_s`

T19's own description explicitly states: "a key absent here raises `KeyError` on read, so this must precede any code that reads them." Despite this, T19 is positioned after T17/T18 and before T20, while T13 — which implements `run_audit(...)` — reads `metrology.audit_timeout_s` to wrap the agent stream in `asyncio.wait_for`. T14 (harness tests) tests T13 including the timeout failure path, which also requires the key to exist. Since `get_typed_config` raises `KeyError` for unregistered keys, both T13's implementation and T14's tests will fail unless the key is registered first. T19 should be moved before T13 (or at minimum before T14). The config keys `metrology.audit_variance_runs` and `metrology.audit_profile` are only read by T20, so those are fine in the current position, but `metrology.audit_timeout_s` is needed by T13.

### [CONCERN] Success criterion 9 ("repeat-run clause does not apply") lacks a corresponding test assertion

The slice design's Success Criteria state: "Repeated runs in a variance series are independent — asserted by a test that the independent-run preamble is present **and the repeat-run clause does not apply**." T4 (fork-sync guard test) verifies that the independent-run marker string appears in the vendored skill file, and T11 verifies that `build_audit_prompt(independent_run=True)` includes the marker. However, no test asserts that the repeat-run clause in the skill file has been made conditional (i.e., that it explicitly defers when the independent-run marker is present). T2 edits the skill to make the clause conditional, and T2's own success criteria mention this, but T4 does not verify it. A test assertion checking that the conditional wording exists in the skill file (e.g., that the repeat-run section contains text referencing the independent-run marker as an exception) would close this gap.

### [NOTE] T13 implements a large cohesive unit — agent execution, timeout, failure handling, parsing, and persistence in one task

T13 (`run_audit`) is the largest single implementation task, encompassing agent stream management, `asyncio.wait_for` timeout wrapping, exception handling with agent shutdown, parsing delegation, and persistence. While this could theoretically be split (e.g., a basic execution path vs. the failure-handling wrapper), the design treats `run_audit` as one cohesive function where the failure handling is integral to the execution contract ("one run persists a complete AuditRun or nothing at all"). Splitting would likely create an artificial seam. The current scope is defensible but an implementer should be aware it is a substantial task.

### [NOTE] No explicit push-to-remote step for canonical fork edits

T1 and T2 include commits in the fork repo (`github:ecorkran/tech-debt-audit`) but neither task explicitly instructs pushing to the remote. Success criterion 8 requires that "the contract edits are present in the canonical fork (`github:ecorkran/tech-debt-audit`)" — the GitHub remote, not just a local commit. T3 vendors from the fork into squadron, but if the fork changes were committed locally and never pushed, the remote fork would not have them. This is likely implicit in the developer workflow, but making the push step explicit would ensure the criterion is verifiable.
