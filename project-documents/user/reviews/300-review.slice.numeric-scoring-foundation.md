---
docType: review
layer: project
reviewType: slice
slice: numeric-scoring-foundation
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/300-slice.numeric-scoring-foundation.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260605
dateUpdated: 20260605
findings:
  - id: F001
    severity: concern
    category: architectural-alignment
    summary: "Provenance field deferred despite architectural commitment on the result model"
    location: 300-slice.numeric-scoring-foundation.md#Explicitly-out-of-scope
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure modes not explicitly enumerated for new parser extraction path"
    location: 300-slice.numeric-scoring-foundation.md#Technical-Decisions
  - id: F003
    severity: note
    category: scope
    summary: "Structured-output parser shape deferred to 302"
    location: 300-slice.numeric-scoring-foundation.md#Technical-Decisions
  - id: F004
    severity: pass
    category: architectural-alignment
    summary: "Additive-only, backward-compatible model changes"
    location: 300-slice.numeric-scoring-foundation.md#What-changes
  - id: F005
    severity: pass
    category: architectural-alignment
    summary: "Score persisted as first-class queryable field"
    location: 300-slice.numeric-scoring-foundation.md#State-Management
  - id: F006
    severity: pass
    category: architectural-alignment
    summary: "Parser leniency and two-layer split correctly implemented"
    location: 300-slice.numeric-scoring-foundation.md#Parser-remains-lenient-and-judging-unaware
  - id: F007
    severity: pass
    category: scope
    summary: "No judging logic — scope discipline"
    location: 300-slice.numeric-scoring-foundation.md#What-does-NOT-change
  - id: F008
    severity: pass
    category: dependency-direction
    summary: "Correct dependency direction and integration point definitions"
    location: 300-slice.numeric-scoring-foundation.md#Integration-Points
---

# Review: slice — slice 300

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Provenance field deferred despite architectural commitment on the result model

The architecture document states unambiguously: *"A `ReviewResult` carrying both `score` and `verdict` is ambiguous on its face… The result model therefore carries a **provenance field** (the kind of result: judge-derived vs. review-produced) so the result is self-describing. This is the architectural commitment; the exact field name/enum is slice-design detail."* The slice document explicitly defers provenance to slice 301 alongside validation and thresholding. This creates two problems: (a) the architecture commits provenance to the **result model**, and this is the keystone model-change slice — deferring it means 301 must re-open the models, undermining the stated reason for ordering this slice first (settling the field shape once); (b) once `score` and `verdict` can coexist on a `ReviewResult` without provenance (which this slice makes possible), the ambiguity the architecture identifies is live but undressed. A minimal additive field (e.g., `provenance: str | None = None`) here — even if no code populates or consumes it yet — would honor the architectural commitment while keeping the same "latent until 301/302" posture the slice already applies to `score` itself.

### [CONCERN] Failure modes not explicitly enumerated for new parser extraction path

The architecture enumerates failure modes with explicit verdict mapping (unparseable response, score absent/out-of-range, missing ground truth, provider unavailable, injection cap exceeded). The slice adds a new I/O path — the parser extracting `score` and `criteria` from agent output — but does not enumerate its failure modes with explicit handling strategies. Specific cases left implicit: (1) a `score:` line present with a non-numeric value (e.g., `score: high`); (2) multiple `score:` lines in one response; (3) a `criteria` map with non-float values or unexpected nesting; (4) numeric edge cases like `score: inf` or `score: NaN`. The slice's "lenient extraction" commitment implies these return `None`, but the handling strategy is implicit rather than explicitly enumerated. Given the architecture's own standard of enumerated failure modes with explicit outcomes, the slice should state these cases and their handling (e.g., "non-numeric score value → `score` remains `None`, no error raised; multiple score lines → first extracted wins; non-float criteria values → criteria remains `None`").

### [NOTE] Structured-output parser shape deferred to 302

The architecture mentions that "the judge template uses a structured-output constraint for the score field" as a reliability mitigation. The slice deliberately commits only to the `score: <number>` line shape and defers the structured-output JSON extraction to 302. The reasoning is sound — pinning the structured shape here would pre-commit 302's design — but it is worth noting that until 302 lands, the architecture's stated reliability mitigation (structured output) has no parser support. This is correctly scoped but should remain on 302's radar.

### [PASS] Additive-only, backward-compatible model changes

All new fields default to `None`, no existing field is removed or repurposed, and existing score-less reviews parse identically. This directly satisfies the architecture's "Additive over migratory" principle and its statement that "existing verdict-gating pipelines keep working unchanged."

### [PASS] Score persisted as first-class queryable field

The slice addresses the architecture's commitment to persist the score as a "first-class, queryable field" in both review-file frontmatter (top-level `score:` YAML key) and run-state JSON (`StepState.score` as a hoisted top-level field). The concrete mapping from architecture commitment to implementation surfaces is explicit and correct.

### [PASS] Parser leniency and two-layer split correctly implemented

The slice faithfully implements the architecture's "optional at the parser, required at the judge use" commitment. The parser extracts when present, is silent when absent, never validates, never range-checks, and never needs to know it is in a judging context. The separation between extraction (this slice) and enforcement (301) is cleanly drawn.

### [PASS] No judging logic — scope discipline

The slice explicitly excludes all judging concerns: no required-ness, no range validation, no thresholding, no verdict derivation, no provenance. This aligns with the architecture's keystone-slice ordering and the principle that the model change is isolated before consumers depend on it.

### [PASS] Correct dependency direction and integration point definitions

Dependencies on initiative 100 (ReviewResult, parser, run_review_with_profile) and 140 (ActionResult, StepState, state manager) are correct and minimal. Provided interfaces to slices 301–304 are clearly specified with concrete field names, matching what those slices will consume.
