---
docType: review
layer: project
reviewType: slice
slice: is-sdk-profile-predicate-re-homing
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/241-slice.is-sdk-profile-predicate-re-homing.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260502
dateUpdated: 20260502
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Predicate contract matches architecture specification exactly"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#contract-matches-arch-§is_sdk_profile-predicate-iteration-3
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Dependency direction correct — pipeline imports from providers, not reverse"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#canonical-home-providersprofiles.py
  - id: F003
    severity: pass
    category: scope
    summary: "Scope tightly bounded — no behavior change, no new callers, no scope creep"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#scope
  - id: F004
    severity: pass
    category: error-handling
    summary: "Pure function — no I/O paths, no failure mode enumeration required"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#canonical-home-providersprofiles.py
  - id: F005
    severity: note
    category: sequencing
    summary: "Architecture suggested re-homing might land in pre-scan slice; dedicated slice is cleaner"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md
---

# Review: slice — slice 241

**Verdict:** PASS
**Model:** z-ai/glm-5.1

## Findings

### [PASS] Predicate contract matches architecture specification exactly

The slice's contract table (None→True, "sdk"→True, all other registered profiles→False, unknown strings→False) is a verbatim restatement of the architecture document's §`is_sdk_profile()` predicate — ownership and contract (iteration 3). The classification-layer note about `None`→`True` semantics serving only renderer/summary call sites (not pre-scan) is also carried forward correctly. No drift.

### [PASS] Dependency direction correct — pipeline imports from providers, not reverse

Before the slice, the predicate lives in `pipeline/summary_oneshot.py` with same-layer imports from other `pipeline` modules. After the slice, `pipeline/prompt_renderer.py` and `pipeline/actions/summary.py` import from `providers.profiles` — a lower layer. This is the correct dependency direction per the architecture, which explicitly states the canonical home is `providers/profiles.py` alongside `get_profile()`. No circular or upward dependency introduced.

### [PASS] Scope tightly bounded — no behavior change, no new callers, no scope creep

The slice explicitly marks behavior change, new callers, changes to `capture_summary_via_profile()`, and changes to existing branch logic as out of scope. The migration plan is mechanical across 6 files with atomic single-PR delivery. The "no re-export shim" decision is deliberate and justified (all 3 existing callers update in one PR; a shim would only delay cleanup). This aligns with the architecture's characterization of re-homing as "mechanical."

### [PASS] Pure function — no I/O paths, no failure mode enumeration required

The predicate is explicitly side-effect free: no logging, no config reads, no CLI probes, no I/O. The architecture mandates this ("The predicate does not probe the Claude CLI, does not check auth, does not read config. It is a pure function of the profiles registry.") and the slice faithfully preserves it. Since there are no I/O paths, failure-mode enumeration for hangs/timeouts/peer-disconnect is not applicable. The only risk (stale import paths) is documented in the Risks section.

### [NOTE] Architecture suggested re-homing might land in pre-scan slice; dedicated slice is cleaner

The architecture states re-homing "lands in the first slice that needs it (likely the pre-scan slice; slice 170 can also adopt the new home if it ships afterward)." This slice instead creates a dedicated slice (241) for the re-homing, which is arguably better than bundling it into slice 243 or 170 — it keeps the mechanical refactor isolated and makes the 6 downstream slices' dependency on 241 explicit. This is a minor sequencing deviation from the architecture's suggestion but is an improvement in clarity, not a violation.
