---
docType: review
layer: project
reviewType: tasks
slice: calibration-to-threshold-feedback
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/322-tasks.calibration-to-threshold-feedback.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260725
dateUpdated: 20260725
findings:
  - id: F001
    severity: concern
    category: logic/sequencing
    summary: "T7 direction-classification precedence contradicts the \"tightening is not floor-gated\" requirement"
    location: project-documents/user/tasks/322-tasks.calibration-to-threshold-feedback.md
  - id: F002
    severity: note
    category: test-coverage
    summary: "T8 omits an explicit malformed judge-block test claimed by the Coverage Check"
    location: project-documents/user/tasks/322-tasks.calibration-to-threshold-feedback.md
  - id: F003
    severity: note
    category: dependency-risk
    summary: "T13 residual-offer selection depends on an unverified 320 result-discovery surface"
    location: project-documents/user/tasks/322-tasks.calibration-to-threshold-feedback.md
  - id: F004
    severity: pass
    category: coverage/sequencing
    summary: "Coverage mapping and test-with sequencing are complete"
    location: project-documents/user/tasks/322-tasks.calibration-to-threshold-feedback.md
---

# Review: tasks — slice 322

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] T7 direction-classification precedence contradicts the "tightening is not floor-gated" requirement

T7 lists `classify_direction` precedence as:
1. `n < floor` → `INSUFFICIENT_EVIDENCE`
2. `not versioned` → `INSUFFICIENT_EVIDENCE`
3. `n >= floor and match_rate >= graduate_rate` → `GRADUATE`
4. `match_rate <= tighten_rate` → `TIGHTEN`
5. otherwise → `HOLD`

The task text then claims case 4 is "reachable even if `n < floor`," but a literal if-elif implementation of that order will always return `INSUFFICIENT_EVIDENCE` at step 1 for any below-floor cell and never reach step 4. This directly conflicts with the slice design's direction-bands table and text stating "tightening is not floor-gated," and with T8's expected test for "a below-floor cell with a low match rate returns `TIGHTEN`, not `INSUFFICIENT_EVIDENCE`." Reorder the precedence so unversioned is checked first, then `TIGHTEN`, then the evidence floor gates only the loosening path (`GRADUATE`/`HOLD`).

### [NOTE] T8 omits an explicit malformed judge-block test claimed by the Coverage Check

The Failure Modes table in the slice design requires a malformed `judge:` block to be flagged (WARNING naming the template) rather than silently defaulted. The Coverage Check at the end of the task file asserts this is "exercised in T8," but T8's bullet list only tests registered vs. unregistered templates and does not include a fixture with a non-numeric `pass_floor`/`concerns_floor`. Add an explicit T8 test that `read_current_thresholds` delegates to `resolve_thresholds` and surfaces the inherited WARNING without fabricating thresholds.

### [NOTE] T13 residual-offer selection depends on an unverified 320 result-discovery surface

T13 instructs the implementer to "reuse 320's existing result-discovery surface" to find unsampled judge results, with a fallback to "store-recorded samples only" if no such surface exists. The slice design's success criterion and T13's own success criterion require a graduated config with unsampled results to yield a non-empty offer set. If 320 only tracks sampled results, the fallback may be unable to identify unsampled judge results at all, making the guarantee untestable. Confirm the existence and shape of the 320 discovery surface before implementing T13/T14, or split the fallback path into an explicit spike/dependency-resolution task.

### [PASS] Coverage mapping and test-with sequencing are complete

The Coverage Check maps every slice-design success criterion and Failure-Modes row to concrete tasks, and no task introduces deferred-by-design scope (automatic threshold mutation, new gating, 300 write-path changes, audit-oracle work). Implementation tasks are immediately followed by their test tasks (T1/T2, T3/T4, T5/T6, T7/T8, T9/T10, T11/T12, T13/T14, T15/T16), config keys are sequenced before consumers (T5 before T7/T9/T15), and the hash-narrowing correction is sequenced first as required. Commit checkpoints are distributed per task, not batched at the end, and no NFR/load-test requirement is stated in the parent slice that would require a `tests/load/` task or CI gating task.
