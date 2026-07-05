---
docType: review
layer: project
reviewType: slice
slice: design-phase-judge-templates
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/302-slice.design-phase-judge-templates.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260705
dateUpdated: 20260705
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Failure modes not explicitly enumerated for judge template paths"
    location: 302-slice.design-phase-judge-templates.md#risk-assessment
  - id: F002
    severity: note
    category: nfr
    summary: "NFR for no-silent-pass not restated with specific application"
    location: 302-slice.design-phase-judge-templates.md#technical-decisions
  - id: F003
    severity: pass
    category: alignment
    summary: "Architectural principles correctly implemented"
    location: 302-slice.design-phase-judge-templates.md#technical-decisions
  - id: F004
    severity: pass
    category: alignment
    summary: "Conservative threshold differentiation well-justified"
    location: 302-slice.design-phase-judge-templates.md#technical-decisions
---

# Review: slice — slice 302

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Failure modes not explicitly enumerated for judge template paths

The architecture document enumerates specific failure modes — "unparseable response; score absent or outside 0–100; missing/unreadable ground-truth file; provider unavailable; injected ground truth exceeding the cap" — and mandates they map to observable, non-passing outcomes with explicit handling. This slice introduces concrete I/O paths (judge template → LLM call with score-with-rationale prompt → parser → enforce_judge) and a new message shape (score + criteria + findings, no verdict), yet its Risk Assessment section addresses only prompt quality, not these operational failure modes.

While slice 301's `enforce_judge` and slice 300's parser handle these at the infrastructure level, the slice design should explicitly enumerate each failure mode for its specific paths and state the handling strategy — e.g., what happens when: (1) the LLM call times out or hangs during a judge template invocation; (2) the model returns a response where `score:` is absent or outside 0–100 for the score-with-rationale prompt shape; (3) the model emits a verdict summary despite the prompt forbidding it; (4) `TEMPLATE_INPUTS` resolution fails for a judge template name (missing `arch_file` in SliceInfo); (5) the model's `## Rationale` section or `criteria:` block deviates from the expected shape. The architecture requires explicit handling strategies, not implicit delegation to another slice's infrastructure.

### [NOTE] NFR for no-silent-pass not restated with specific application

The architecture establishes the NFR "no failure mode silently yields a passing result" and explicitly cross-references the checkpoint machinery to verify it. The slice document references `enforce_judge` and threshold-derived verdicts but does not restate this NFR for the judge template paths it creates. A brief restatement — confirming that every failure mode on the judge template path (unparseable output, absent score, provider timeout) maps to a non-PASS outcome via the existing enforcement layer — would close the loop between the architecture's commitment and this slice's specific paths.

### [PASS] Architectural principles correctly implemented

The slice design demonstrates strong alignment with the architecture's core principles: (1) **Additive over migratory** — two new YAML files and two registry entries, no modifications to existing templates or engine code; (2) **Score as source of truth** — the system prompt forbids emitting a verdict, and the data flow shows `verdict=UNKNOWN` being ignored in favor of threshold-derived verdict; (3) **Bubble up the hard calls** — differentiated thresholds (slice-vs-arch at 82/60 vs. tasks-vs-slice at 78/55) reflect ground-truth strength; (4) **Reuse, don't rebuild** — consumes slices 300 and 301 as-is with no change requests back; (5) **Provenance declaration** — data flow shows `provenance="judge"`; (6) **Template naming is human-readable, not dispatch** — explicitly documented and motivated; (7) No scope creep — cycle conventions (303) and gate composition (304) are explicitly out of scope.

### [PASS] Conservative threshold differentiation well-justified

The decision to set `pass_floor=82` for `judge.slice-vs-arch` (higher, harder to auto-pass) versus `pass_floor=78` for `judge.tasks-vs-slice` directly implements the architecture's "bubble up the hard calls" principle and its observation that "architecture intent is more interpretive" (weaker ground truth) versus "slice design is concrete, cross-referenceable" (stronger ground truth). The thresholds are template-level defaults overridable via step-level `resolve_thresholds`, consistent with the architecture's "template-level config with step-level override" commitment.
