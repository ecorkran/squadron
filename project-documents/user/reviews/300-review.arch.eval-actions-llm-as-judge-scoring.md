---
docType: review
layer: project
reviewType: arch
slice: eval-actions-llm-as-judge-scoring
project: squadron
verdict: UNKNOWN
sourceDocument: project-documents/user/architecture/300-arch.eval-actions-llm-as-judge-scoring.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260530
dateUpdated: 20260530
findings:
  - id: F001
    severity: fail
    category: completeness
    summary: "Score-to-verdict mapping is unspecified"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Technical-Considerations
  - id: F002
    severity: concern
    category: consistency
    summary: "Contradiction: \"drops straight into existing checkpoint machinery\" vs. \"gate composition is undecided\""
    location: 300-arch.eval-actions-llm-as-judge-scoring.md
  - id: F003
    severity: concern
    category: abstraction
    summary: "\"One action, one judgment\" principle conflicts with dataset loop design"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Architectural-Principles
  - id: F004
    severity: concern
    category: completeness
    summary: "Critical architectural decisions deferred wholesale to slice design"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Technical-Considerations
  - id: F005
    severity: concern
    category: feasibility
    summary: "Review engine reuse claim lacks validation of required modifications"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Overview
  - id: F006
    severity: concern
    category: dependencies
    summary: "Read-file-on-request capability overlaps with Initiative 260 without clear boundary"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Related-Work
  - id: F007
    severity: concern
    category: completeness
    summary: "Per-case result persistence and aggregation model not addressed"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Envisioned-State
  - id: F008
    severity: concern
    category: completeness
    summary: "Error handling and failure modes for eval:judge are unaddressed"
    location: unverified
  - id: F009
    severity: concern
    category: feasibility
    summary: "Injection cap constraint may restrict eval:judge to SDK/Codex providers for non-trivial datasets"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Technical-Considerations
  - id: F010
    severity: note
    category: completeness
    summary: "LLM structured output schema for scored results not specified"
    location: 300-arch.eval-actions-llm-as-judge-scoring.md#Envisioned-State
---

# Review: arch — slice 300

**Verdict:** UNKNOWN
**Model:** z-ai/glm-5.1

## Findings

### [FAIL] Score-to-verdict mapping is unspecified

The document states eval produces both a numeric score (0–100) and a verdict, and that the verdict flows through the existing `--step-done --verdict` checkpoint machinery. Yet it never specifies how the verdict is derived from the score. Is the LLM prompted to emit both independently? Is the verdict threshold-derived from the score (e.g., ≥80 → PASS)? This is a load-bearing decision: the checkpoint state machine consumes the verdict, so the mapping determines whether an eval result can actually gate a pipeline step. Leaving it completely unspecified means the architecture cannot validate that eval results integrate with the checkpoint machinery at all.

### [CONCERN] Contradiction: "drops straight into existing checkpoint machinery" vs. "gate composition is undecided"

The overview claims "the score it produces drops straight into the existing `sq run --step-done --verdict` checkpoint machinery, meaning an eval result can gate pipeline progress with no new plumbing." But the Technical Considerations section states that eval/review gate composition is "undecided and must be resolved during slice design" and that it "affects the checkpoint expansion and the `--step-done` contract." These two statements are directly contradictory. Either eval composes with existing checkpoint machinery as-is (no new plumbing), or the checkpoint contract needs expansion to handle the composition — it cannot be both. The overview's claim of zero-plumbing integration is premature and misleading given the acknowledged open decision.

### [CONCERN] "One action, one judgment" principle conflicts with dataset loop design

The principle states "an `eval:judge` action adjudicates one artifact against ground truth and returns one result." But the dataset loop slice describes "iteration over cases, aggregation of per-case scores into a step-level scalar." The document never resolves whether the pipeline expands one `eval:judge` action per dataset case (clean, but creates N action results) or one `eval:judge` action internally loops over all cases (breaks the stated principle, single result with internal aggregation). This is an abstraction boundary decision, not an implementation detail, and it affects the result model, persistence, and checkpoint interaction. Deferring it to slice design leaves the architecture's core principle unvalidated against its own envisioned state.

### [CONCERN] Critical architectural decisions deferred wholesale to slice design

The Technical Considerations section lists at least four load-bearing decisions as open: where datasets live, how a pipeline step references one, how cases iterate, how per-case scores aggregate. Additionally, score-to-verdict mapping, eval/review gate composition, and the LLM output schema for scored results are all unresolved. These are not implementation details resolvable at slice time — they are architectural decisions that determine whether the component's abstractions are viable. The document is closer to a problem statement with design goals than an architecture; it describes what the system should do without committing to how the hardest parts actually work.

### [CONCERN] Review engine reuse claim lacks validation of required modifications

The overview states eval "reuses squadron's existing provider-agnostic review engine" and "inherits multi-provider model support, file injection, and the verdict contract for free." But eval:judge requires a different system prompt (judging vs. rule-based review), different input sources (reference datasets + ground-truth files vs. diffs + rulesets), and a different structured output schema (score + verdict + findings vs. verdict + findings). The document never describes what changes to `run_review_with_profile` are needed — can it be parameterized with a custom system prompt and output schema today, or does it hardcode the review prompt/format? If the review engine isn't actually generalizable without significant modification, the "reuse for free" claim is misleading and the real engineering effort is underestimated.

### [CONCERN] Read-file-on-request capability overlaps with Initiative 260 without clear boundary

The document describes building a "minimal, canonical" read-file-on-request capability for non-SDK judges, while Initiative 260 builds a "full agentic tool loop for non-SDK providers." The claimed relationship is that 260 "may consume this component's read-file capability if it ships." But this creates an implicit dependency: if 300's read-file tool is designed narrowly for judging (e.g., only serves files from a predetermined ground-truth directory), it may not be general enough for 260's needs, forcing 260 to build its own mechanism or work around 300's constraints. Conversely, if 300's tool is designed broadly enough for 260, it's no longer "minimal." The document doesn't define the boundary — what exactly does "read-file-on-request" entail? A single tool function? A tool-use loop? The answer determines whether this is genuinely independent of 260 or a premature partial implementation of 260's scope.

### [CONCERN] Per-case result persistence and aggregation model not addressed

The envisioned state says eval results are "persisted like any review output." But a dataset evaluation produces N per-case results plus one aggregated step-level result. The existing persistence model stores one result per action execution. Where do per-case scores go? Are they persisted individually, or only as part of the aggregated result? If individually, what's the persistence model — a new `EvalCaseResult` type? If only aggregated, the per-case data (which findings applied to which cases, which cases scored low) is lost, undermining the "track over time" motivation. This is a state ownership and model decision that should be specified at the architecture level.

### [CONCERN] Error handling and failure modes for eval:judge are unaddressed

The document describes eval:judge as an LLM call producing structured output. What happens when: the LLM returns an unparseable response? The score is outside 0–100? The provider is unavailable? The ground-truth file doesn't exist? The injection cap is exceeded? For each of these, what verdict does the action produce — UNKNOWN? FAIL? Does the action retry? The existing review subsystem has established behavior for parse failures, but the document doesn't say whether eval inherits it or needs different handling (e.g., a parse failure on a score field is different from a parse failure on a verdict field). Checkpoint gating depends on the verdict value, so the failure-mode verdict mapping is architecturally significant.

### [CONCERN] Injection cap constraint may restrict eval:judge to SDK/Codex providers for non-trivial datasets

The document acknowledges that providers without file-reading capability receive injected content under a bounded cap, and that reference datasets can exceed that cap. The resolution options listed are: use a file-reading provider, per-case chunking, or read-file-on-request (a later slice). This means for the first two slices, eval:judge with any non-trivial dataset only works on SDK/Codex providers. Per-case chunking is mentioned but not analyzed — if a single case's ground-truth + artifact exceeds the cap, chunking doesn't help. This constraint should be surfaced as a binding limitation on the initial slice scope, not treated as a future resolution.

### [NOTE] LLM structured output schema for scored results not specified

The review engine's response parser currently extracts verdict + findings from LLM output. Eval:judge requires the parser to also extract a numeric score. The prompt format and expected output schema (JSON structure, field names, validation rules for the 0–100 scalar) are not specified. While this could be deferred to implementation, the response parser is shared infrastructure — changes to it affect all provider profiles. The schema design should at least be constrained at the architecture level (e.g., "score is a required top-level numeric field in the structured output JSON").

## Disposition (architect, 20260530)

Reviewed against the source. Findings resolved by edits to `300-arch.eval-actions-llm-as-judge-scoring.md`; slice-level detail deliberately left for slice design per the arch-phase guidance (keep high-level, do not pre-decide what emerges in slice design).

- **F001 [FAIL] — score→verdict mapping.** Addressed. New principle "Score is primary; verdict is derived" plus a "Score-to-verdict mapping" technical consideration: verdict is a deterministic threshold function of the score (score → verdict, never the reverse). Threshold values left to slice design; derivation direction fixed.
- **F002 [CONCERN] — contradiction.** Addressed. Overview now disambiguates: a *single* eval verdict gates via existing machinery with no new plumbing; *composing* eval+review into one gate is the separate open question. Not contradictory once split.
- **F003 [CONCERN] — one-action-one-judgment vs. dataset loop.** Addressed. Principle reworded to "One judgment per case"; a multi-case dataset is an explicit composition of single judgments (one judgment expanded per case), not an action that loops internally. Reconciled with Anticipated Slices wording.
- **F004 [CONCERN] — wholesale deferral.** Largely resolved by F001/F002/F003 + the new failure-mode and persistence commitments. Remaining deferrals (dataset format/location, threshold values, output field names) are legitimately slice-level and are stated as such.
- **F005 [CONCERN] — review-engine reuse unvalidated.** Verified against code: `run_review_with_profile` is parameterized by `ReviewTemplate` (system prompt, prompt builder, inputs, tools, model), so prompt/model/file-injection/verdict reuse is genuinely free. The parser is NOT template-parameterized — extracting a score is a real, named modification. Overview corrected to claim reuse only where true and to call out the parser change as the one non-free modification.
- **F006 [CONCERN] — read-file boundary vs. 260.** Addressed. Boundary defined: a single read-file tool (model requests a path, squadron serves contents within scoped roots) inside the one-shot judge call — explicitly NOT a multi-tool agentic loop (that is 260). No dependency on 260; not a partial 260.
- **F007 [CONCERN] — per-case persistence/aggregation.** Addressed at principle level: "Per-case results are retained, not just the aggregate." Storage shape left to slice design.
- **F008 [CONCERN] — failure modes.** Addressed. New "Failure modes and their verdict mapping" consideration enumerates the failure modes and commits to no-silent-pass: input/parse failures → UNKNOWN, substantive negative → FAIL, logged at WARNING+. Aligns with the project's Failure-Mode Enumeration rule.
- **F009 [CONCERN] — injection cap restricts providers.** Addressed by reframing: now stated as a binding limitation on initial slice scope — file-grounded eval:judge is SDK/Codex-only until the read-file slice lands — not as a future resolution.
- **F010 [NOTE] — output schema.** Addressed minimally: score constrained as a required, range-validated top-level numeric field of the shared parser contract; full schema left to slice design.
