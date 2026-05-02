---
docType: review
layer: project
reviewType: slice
slice: is-sdk-profile-predicate-re-homing
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/241-slice.is-sdk-profile-predicate-re-homing.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260501
dateUpdated: 20260501
findings:
  - id: F001
    severity: fail
    category: contract-violation
    summary: "`None` contract contradicts architecture specification"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#Design
  - id: F002
    severity: concern
    category: scope-accuracy
    summary: "\"No behavior change\" scope claim is inconsistent with architecture contract"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#Scope
  - id: F003
    severity: note
    category: architectural-boundary
    summary: "Dependency direction is correct"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#Canonical-Home:-providers/profiles.py
  - id: F004
    severity: note
    category: quality
    summary: "Migration plan and verification are thorough"
    location: 241-slice.is-sdk-profile-predicate-re-homing.md#Migration-Plan
---

# Review: slice — slice 241

**Verdict:** FAIL
**Model:** z-ai/glm-5.1

## Findings

### [FAIL] `None` contract contradicts architecture specification

The slice defines `is_sdk_profile(None)` → `True`, but the architecture document explicitly specifies the opposite. From the architecture (§`is_sdk_profile()` predicate — ownership and contract):

> Returns `False` for any other registered provider (`openai-compatible`, `openrouter`, etc.) and for `None` (which means "no profile resolved yet — treat as non-SDK for routing decisions").

The slice's contract table and implementation both say `None` → `True`, with rationale "defaults to SDK for routing decisions, matching today's behavior." The architecture's rationale is also clear: treating `None` as non-SDK is essential to the initiative's core design goal that **Claude-free pipelines run Claude-free**. If an unresolved profile defaults to SDK, any step whose profile hasn't been resolved yet would trigger Claude auth — directly undermining the per-step classification model the architecture mandates. The "matching today's behavior" argument is insufficient; the 240 initiative exists precisely to change the problematic current behavior. The slice must implement the architecture's contract, or the architecture must be amended via a separate design change — the slice cannot silently contradict it.

---

### [CONCERN] "No behavior change" scope claim is inconsistent with architecture contract

The scope section states: "No behavior change. The predicate's return value for any given input is identical before and after." If the architecture's `None` → `False` contract is followed, then the predicate's return value for `None` *does* change, which means existing callers that currently rely on `is_sdk_profile(None) == True` would receive different behavior. This would expand the slice's scope beyond a mechanical refactor: caller impact analysis would be required for every site that passes `None` or an unresolved profile. The scope statement should be updated to accurately reflect whether behavior is preserved or corrected, and if corrected, the caller-impact analysis should be included.

---

### [NOTE] Dependency direction is correct

Moving `is_sdk_profile()` from `pipeline/summary_oneshot.py` to `providers/profiles.py` is consistent with the architecture's direction: `providers` is a foundational layer that defines profile semantics (`get_profile`, `get_all_profiles`), and `pipeline` is a consumer. Having `pipeline` import from `providers` is the correct dependency direction. The component interaction diagram correctly shows this reorientation.

---

### [NOTE] Migration plan and verification are thorough

The migration plan is well-structured with an explicit step ordering, a `grep`-based verification checklist, and a verification walkthrough. The decision not to leave a re-export shim is justified and aligned with the atomic-PR approach. No issues here.
