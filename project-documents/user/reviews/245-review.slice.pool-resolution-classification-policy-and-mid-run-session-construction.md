---
docType: review
layer: project
reviewType: slice
slice: pool-resolution-classification-policy-and-mid-run-session-construction
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md
aiModel: deepseek/deepseek-v4-pro
status: complete
dateCreated: 20260504
dateUpdated: 20260504
findings:
  - id: F001
    severity: fail
    category: architecture-alignment
    summary: "Default policy contradicts architecture’s conservative‑on‑uncertainty principle"
    location: 245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md#Overview; Technical Decisions (first paragraph)
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Mid‑run session construction mechanism matches arch §5a"
    location: 245‑slice…/Mid-Run Session Construction (entire section)
---

# Review: slice — slice 245

**Verdict:** FAIL
**Model:** deepseek/deepseek-v4-pro

## Findings

### [FAIL] Default policy contradicts architecture’s conservative‑on‑uncertainty principle

The architecture document (240‑arch) states:
- “Conservative on uncertainty. When pool resolution makes the classification uncertain, the **default behavior is to treat the pipeline as Claude‑required** … A user can **opt into lazy connection** only with explicit acknowledgment of the trade‑off.”
- The “Envisioned State” describes `needs_persistent_session` as true for pool‑uncertain steps “under conservative default.”

Slice 245 explicitly reverses this:
- “This slice changes the default: **lazy is the default policy** … Users who want the old conservative … opt in explicitly via `--strict` or `auth_policy: strict`.”

This violation breaks the architectural contract for the boundary between classification and execution. The slice must align with the conservation‑first principle, making eager connection the default and lazy an opt‑in (e.g., `--lazy` flag or `auth_policy: lazy`). Changing this fundamental rule without updating the architecture document is unacceptable at this stage.

### [PASS] Mid‑run session construction mechanism matches arch §5a

The slice’s approach to holding a mutable `sdk_session` reference in the executor, checking before each action‑context build, and constructing/connecting on the first statically‑confirmed SDK step aligns precisely with the architecture’s described mechanism. The boundary for pool‑uncertain steps (dispatch action guard returns `FAILED` when the session is still `None`) is correct. Auth‑failure error messages, run‑state persistence, and resume behaviour are specified as required.
