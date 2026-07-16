---
docType: review
layer: project
reviewType: slice
slice: gate-composition
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/304-slice.gate-composition.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260716
dateUpdated: 20260716
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Missing failure mode for source result with None verdict"
    location: 304-slice.gate-composition.md#the-reduction-rule-conservative-most-severe-wins
    resolution: addressed
  - id: F002
    severity: concern
    category: architectural-boundaries
    summary: "Executor per-step read surface boundary ambiguity"
    location: 304-slice.gate-composition.md#where-the-two-source-results-come-from
    resolution: addressed
  - id: F003
    severity: pass
    category: architectural-alignment
    summary: "Architectural approach and principles are correctly followed"
    location: 304-slice.gate-composition.md
    resolution: acknowledged
---

# Review: slice — slice 304

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] Missing failure mode for source result with None verdict

The reduction rule's severity table is `UNKNOWN > FAIL > CONCERNS > PASS`. The architecture's checkpoint machinery explicitly handles `None` verdicts by skipping them (`_find_review_verdict` walks prior outputs and returns the first non-`None` verdict). The gate's failure-mode table enumerates a misspelled/missing source step name but does not enumerate the case where a named source step exists, ran successfully, and produced an `ActionResult` with `verdict=None` — e.g., a non-review action result, or a review that failed to produce a verdict. The reduction function's behavior on a `None` input is undefined in the design. This is a new I/O path (reading named prior results by step name) and the failure mode should be explicitly enumerated with a handling strategy: either treat `None` as `UNKNOWN` (most severe, conservative) or as a validation error (fail fast). The current table leaves it implicit.

### [CONCERN] Executor per-step read surface boundary ambiguity

The slice discovers that the existing `prior_outputs` is lossy across same-typed steps (key collision on `review-0`), which means option (a) as the architecture envisioned it — "compose upstream of the checkpoint" — cannot be implemented using the existing executor result accumulation alone. The slice's resolution is to add a step-keyed read view to the executor (140 code). The architecture defines 300's additive scope as "not changing the checkpoint machinery," and option (a) is called "additive, preferred." It is ambiguous whether an additive *executor* change (as opposed to an additive *action/model* change) falls within 300's additive scope or is itself a 140 coordination. The slice acknowledges this ambiguity with a conditional assessment ("within 300's scope *if* it is a pure read-surface addition") and provides an escalation boundary, which mitigates the risk. However, the default path proceeds on an assumption about scope boundaries that the architecture does not explicitly confirm. If the executor change cannot be done as a pure addition, the escalation boundary fires correctly; but the slice could be clearer that this executor touch is itself a candidate 140 dependency, not just the escalation conditions downstream of it.

### [PASS] Architectural approach and principles are correctly followed

The slice faithfully implements the architecture's prescribed approach to gate composition. It commits to option (a) (upstream reduction) as preferred, defines a precise escalation boundary to option (b) (140 change) with three checkable conditions, and does not silently absorb 140 work. The `gate` action registers additively into the open action registry, the checkpoint's `_find_review_verdict` and single-verdict contract are explicitly preserved, and non-composed pipelines are guaranteed byte-for-byte unchanged. The `composed` provenance value is an additive extension of the architecture's provenance principle. The reduction rule (most-severe-wins, `UNKNOWN` most severe) correctly implements the no-silent-pass NFR the architecture requires: a broken judge leg (`UNKNOWN`) dominates a passing review leg, and the checkpoint fires. Scope is tightly bounded to exactly two named sources, with N-way composition and per-criterion composition explicitly excluded. Dependencies on slices 300–302 and 140 are correctly identified and directional.

## Resolution (20260716)

Both concerns addressed in the slice design; re-verify at Phase 6 implementation.

**F001 — `None`-verdict source (addressed).** The reduction rule now explicitly normalizes a `None` source verdict to `UNKNOWN` *before* ranking — the fail-closed choice, deliberately diverging from `_find_review_verdict`'s skip-`None` behavior because a gate must not let a verdict-less source vanish and silently allow the other leg to advance. Added: the normalization rule in "The reduction rule," a dedicated row in the failure-mode table, a required unit test (WARNING+ log asserted), and prose distinguishing it from the *authoring-time* missing-source-name case (which stays fail-fast validation). The design also documents *why* `None → UNKNOWN` and not fail-fast: a verdict-less source at runtime is an observable cannot-judge outcome to gate on, not a load-time authoring mistake.

**F002 — executor read-surface boundary (addressed).** The design no longer treats the per-step read-surface executor touch as in-scope-unless-downstream-escalation-fires. It is now framed as **140-adjacent, requiring up-front 140 sign-off regardless**, because `prior_outputs` is 140-owned executor code. Two explicit outcomes: (a) confirmed pure read-surface addition → proceed with recorded 140 sign-off (expected default); (b) cannot stay pure → escalate to (b) as the full 140 dependency (escalation-boundary condition 1). Updated: "Where the two source results come from," the "Coordinated dependencies with 140" section (now two touch-points at different confidence levels — expected vs. conditional), escalation condition (1), and the technical-risk bullet. The slice explicitly disclaims unilateral authority to modify executor result accumulation under 300's additive banner.

**F003 — no change needed** (acknowledged; the architectural-alignment PASS stands).

Verdict remains `CONCERNS` as the record of the original review; the concerns are dispositioned above. A Phase-6 re-review against the implemented gate should confirm the design commitments hold in code.
