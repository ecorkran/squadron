---
docType: review
layer: project
reviewType: arch
slice: eval-actions-llm-as-judge-scoring
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/300-arch.eval-actions-llm-as-judge-scoring.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260531
dateUpdated: 20260531
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Score-to-verdict threshold configuration is architecturally unspecified"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Architectural Principles
  - id: F002
    severity: concern
    category: feasibility
    summary: "LLM score reliability is assumed without validation"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Overview
  - id: F003
    severity: concern
    category: abstraction
    summary: "Semantic split between judge-derived and review-derived verdicts is invisible to consumers"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Architectural Principles
  - id: F004
    severity: concern
    category: completeness
    summary: "UNKNOWN verdict behavior in checkpoint machinery is asserted but not verified"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Technical Considerations
  - id: F005
    severity: concern
    category: completeness
    summary: "Step-level configuration for judge template selection is not specified"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Envisioned State
  - id: F006
    severity: note
    category: antipattern
    summary: "Criteria map reservation is speculative schema with no consumer"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Architectural Principles
  - id: F007
    severity: note
    category: completeness
    summary: "Score persistence and queryability for time-series tracking is unspecified"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Envisioned State
  - id: F008
    severity: note
    category: extension-points
    summary: "Gate composition with single-verdict checkpoint machinery is an acknowledged constraint with no resolution path"
    location: 300-arch.eval-actions-llm-as-judge-scoring-scoring.md#Technical Considerations
---

# Review: arch — slice 300

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Score-to-verdict threshold configuration is architecturally unspecified

The principle "the verdict is its projection" commits to the derivation direction (score → verdict), but the threshold values themselves — where they live, how they're specified, whether they're per-template/per-artifact-type/per-pipeline-step, and what sensible defaults are — are entirely deferred to "slice-design and configuration." This is the load-bearing decision that makes the score operationally useful. Without it, the first consuming slice has no basis for gating. The document also acknowledges that trust varies by artifact level ("where in-repo ground truth is strong … the judge can be trusted to gate; where it is weak … the judgment is advisory"), which implies per-artifact-type thresholds are needed, yet no configuration mechanism is sketched. An architectural commitment to the direction without any anchoring of the values or their locus leaves the keystone change incomplete at the architecture level.

### [CONCERN] LLM score reliability is assumed without validation

The entire design premises gating decisions on LLM-emitted 0–100 numeric scores. LLMs are notoriously unreliable at producing calibrated numeric scores: they cluster around round numbers (70, 80, 90), exhibit anchoring bias from the prompt, and produce inconsistent scores across runs for the same input. The document treats score extraction as a parsing problem ("the parser is extended to extract an optional top-level numeric score") but the real difficulty is that the scores may not be meaningful enough to gate on. No mitigation is discussed — not structured-output constraints, not multi-sample voting, not score-calibration prompts, not even acknowledgment that this is a known LLM weakness. The failure-mode section covers "score absent or outside 0–100" but not "score present but poorly calibrated," which is the far more likely failure mode in practice.

### [CONCERN] Semantic split between judge-derived and review-derived verdicts is invisible to consumers

The principle "The score is the source of truth; the verdict is its projection" applies only to judge results. For standard reviews, the verdict is independently model-produced. This means a `ReviewResult` carrying both `score` and `verdict` has two possible semantic interpretations: verdict-derived-from-score (judge) or verdict-independent-of-score (review). A downstream consumer — the checkpoint machinery, a composition layer, a human reading a devlog — cannot determine which semantics apply without knowing which template produced the result. The result model carries no provenance field to disambiguate. This is a leaky abstraction: the consumer needs template-level knowledge to correctly interpret a model-level field, or it must assume one interpretation and be wrong for the other case.

### [CONCERN] UNKNOWN verdict behavior in checkpoint machinery is asserted but not verified

The failure-modes section states "a parse or input failure produces `UNKNOWN` (cannot judge)" and "no failure mode silently yields a passing result." But whether the existing checkpoint machinery (from initiative 140) treats `UNKNOWN` as non-passing — i.e., blocks step advancement — is not confirmed. The document links to 140-arch.pipeline-foundation.md but does not cite or verify UNKNOWN's treatment there. If the checkpoint machinery treats UNKNOWN as neither PASS nor FAIL (e.g., skips it, logs it, or requires manual resolution differently), the guarantee that "a gating step never advances on an unobserved failure" may not hold. This is a cross-dependency assertion that needs verification, not assumption.

### [CONCERN] Step-level configuration for judge template selection is not specified

The document says "a pipeline step runs [a judge] via the `review` action, points it at an artifact and its in-repo ground truth." But the review action is template-parameterized — how does a pipeline step specify "use the judge template, not the standard review template"? The existing step configuration schema isn't shown, and the document doesn't describe whether a step declares a template name, a template category, or some other selector. Without this, the "judge is a review template" abstraction can't actually be invoked from a pipeline definition. This is a connective gap between the template abstraction and the pipeline execution model.

### [NOTE] Criteria map reservation is speculative schema with no consumer

The `criteria` map (criterion name → sub-score) is added to the result model and structured-output contract from the foundation slice onward, but "nothing populates or consumes it initially." The argument is that reserving it now avoids a second cross-cutting migration later. This is a YAGNI tradeoff with low cost (one optional field), but the future schema may not match what's reserved — if criterion scoring later needs weights, metadata, or a different key structure, the reserved map is wrong and must be migrated anyway. The cost is low enough not to flag as a concern, but the justifying argument is weaker than presented.

### [NOTE] Score persistence and queryability for time-series tracking is unspecified

The document states that "quality is trackable over time" and that "a numeric score makes 'is the quality improving?' answerable," but does not describe how scores are persisted in a queryable form. Are they a column on a result table? A field in a JSON blob? Is there an index? The motivation depends on scores being retrievable and comparable across runs, but the persistence design is limited to "thread it through the parser and persistence." If scores are stored as an opaque JSON field, time-series queries require full deserialization, which may not be practical. This is a gap between the stated motivation and the technical commitment.

### [NOTE] Gate composition with single-verdict checkpoint machinery is an acknowledged constraint with no resolution path

The document correctly identifies that "the current checkpoint machinery appears built around a single verdict per step" and that this may constrain gate composition options. It advises auditing before choosing a strategy. This is responsible, but the audit outcome could force a checkpoint expansion (initiative 140 scope) that this initiative doesn't budget for. The "gate composition" anticipated slice may discover it needs to modify the checkpoint state machine itself, which would be scope creep beyond the "additive over migratory" principle.

## Disposition (architect, 20260531) — review of the reduced-scope doc

This review is of the rewritten "Intrinsic LLM Judging & Scoring" doc (verdict CONCERNS, no FAIL — the scope reduction cleared the prior parser-contradiction/dataset/read-file findings). All eight findings addressed; two (F004, F005) were verified against source before responding rather than argued.

- **F001 [CONCERN] — threshold config unspecified.** Addressed. Committed the *locus*: thresholds are template-level config with step-level override, defaults conservative (gate toward escalation when uncertain). This is what lets strong-ground-truth judges gate confidently and weak ones stay advisory. Values remain slice/config detail; locus is now fixed.
- **F002 [CONCERN] — LLM score reliability assumed.** Addressed — the most important finding. The doc now states plainly that LLM scores may be poorly calibrated (round-number clustering, anchoring, run-to-run variance), that 300 does **not** assume reliability, and that score *reliability* is initiative [320]'s problem. 300's job is produce/parse/persist/conservatively-gate, with cheap in-engine mitigations (structured-output score field, score-with-rationale prompt, optional multi-sample via existing fan_out). This finding validates the 300/320 split, now made explicit. New Overview paragraph + Technical Consideration.
- **F003 [CONCERN] — judge-derived vs review-derived verdict invisible.** Addressed. New principle "A result declares its own provenance": the result model carries a provenance field (judge-derived vs review-produced) so a result is self-describing without template knowledge. Also gives [320] its discriminator.
- **F004 [CONCERN] — UNKNOWN-blocks-advancement asserted not verified.** Verified against code and addressed. `CheckpointAction._TRIGGER_THRESHOLDS` includes `UNKNOWN` in both `on-concerns` and `on-fail` firing sets (checkpoint.py), so a checkpoint fires on UNKNOWN — the no-silent-pass guarantee holds with existing 140 machinery, no change. Failure-modes consideration now cites the code.
- **F005 [CONCERN] — judge template selection unspecified.** Verified against code and addressed. The `review` step already requires a `template` field (steps/review.py), so a judge is selected by naming its template — no new step type or selector. New consideration states this; the connective work is authoring templates + threshold config, not schema extension.
- **F006 [NOTE] — criteria map speculative.** Addressed by softening. The reservation now claims only that it spares the *plumbing* migration, not necessarily a *schema* one (future criteria may need weights/metadata/different keys); reserved as a cheap optional latent field, not a final schema. Worst case is one unused optional field.
- **F007 [NOTE] — score queryability for time-series.** Addressed. Commitment: persist score as a first-class queryable field (not opaque JSON), so cross-run comparison needs no full deserialization. The time-series/trend analysis layer itself is [320]; 300 only stores the score in a shape 320 can query.
- **F008 [NOTE] — gate composition may force checkpoint expansion (scope creep).** Verified and addressed. `_find_review_verdict` returns the first non-None verdict (single-verdict-per-step), confirming the reviewer. The consideration now names the boundary explicitly: prefer composing upstream of the checkpoint (additive); extending the checkpoint to multiple verdicts is a 140 change, out of 300's additive scope, to be escalated as a 140 dependency — not silently absorbed.

Net: all addressed; F004/F005 confirmed the design is *already* supported by existing code; F002 drove the clearest articulation yet of why 300 and 320 are separate. `status: reviewed`. The reduced scope plus these clarifications should clear an arch gate; a confirming re-review is welcome but the verdict-driving gaps are closed.
