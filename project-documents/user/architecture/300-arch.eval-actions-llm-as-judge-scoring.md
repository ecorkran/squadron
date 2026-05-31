---
docType: architecture
archIndex: 300
component: eval-actions-llm-as-judge-scoring
initiative: eval-actions-llm-as-judge-scoring
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [100, 140]
dateCreated: 20260530
dateUpdated: 20260530
status: reviewed
---

# Architecture: Eval Actions (LLM-as-Judge & Scoring)

## Overview

Squadron is a deterministic executor. Its pipelines dispatch agents, run reviews, persist verdicts, and gate progress on those verdicts — but nothing in the system *judges* the quality of an artifact against ground truth. The review subsystem comes closest: it produces structured findings and a `PASS | CONCERNS | FAIL` verdict. Yet a verdict is a categorical opinion about a diff against a ruleset; it is not a measured score against a known-correct answer, and it cannot answer "how good is this, on a scale, against what we expected?"

This component introduces an **`eval` action family** that adds a judgment-and-measurement layer to the pipeline. Its first and primary variant, **`eval:judge`**, is LLM-as-judge: an intelligent agent adjudicates an artifact against ground truth and emits a **numeric score plus a verdict**. The action reuses squadron's existing provider-agnostic review engine — the same intelligent-agent-with-file-access-and-structured-output machinery that powers `sq review`. That engine is already parameterized by a template (system prompt, prompt builder, required inputs, allowed tools, model), so a judge is expressed as *a template with a judge system-prompt and reference-dataset inputs*; multi-provider model support, file injection, and the verdict contract are inherited without engine changes. The **one identified non-free modification** is output parsing: the engine's parser today extracts verdict + findings from a fixed structure, and eval must extend it to also extract the numeric score (see Technical Considerations).

A **single** eval result carries a verdict in the established `PASS | CONCERNS | FAIL` vocabulary, so on its own it gates a pipeline step through the existing `sq run --step-done --verdict` machinery with no new plumbing. *Composing* an eval result with a review result into one gate is a separate, open question (see Technical Considerations) — the zero-plumbing claim applies to a single eval verdict gating a step, not to multi-source gate composition.

**Core problem.** Squadron produces excellent *evaluable* artifacts but has no adjudication layer. There is no way to score a pipeline's output against a reference dataset, no numeric quality signal to track over time or threshold a gate on, and no way to compose a measured judgment alongside a rule-based review.

**Scope.** This component encompasses: the `eval` action type and its `eval:judge` variant; a numeric-scoring foundation that extends the existing review/action result models additively; the resolution and loading of reference datasets that an eval adjudicates against; and a canonical read-file-on-request capability that lets non-SDK provider models serve as file-reading judges. It does **not** encompass the authoring of eval datasets or materials (those are produced out-of-band), the wholesale replacement of verdicts with scores, or the general agentic tool loop of initiative 260.

**Motivation.** Squadron becomes orders of magnitude more useful when its pipelines can not only *produce* artifacts and *review* them, but *measure* them against ground truth and gate on that measurement. A numeric score is a richer, trackable, thresholdable signal than a three-state verdict — and once eval exists, the same scoring foundation can progressively enrich the review subsystem itself.

## Design Goals

- **Judgment as a first-class action.** Make adjudication a native pipeline action (`eval:judge`) that composes with dispatch, review, and checkpoint actions exactly as any other action does — so a measured judgment can gate a pipeline step.

- **Score alongside verdict, not instead of it.** Introduce a numeric score as an additive signal that coexists with the established verdict. Existing pipelines that gate on verdicts continue to work unchanged; the score is a new, richer dimension layered on top, available to migrate to over time.

- **Reuse the judge engine, don't rebuild it.** The intelligent-agent-with-file-access-and-structured-output path already exists in the review subsystem and is provider-agnostic. Eval rides that path with a judge system-prompt and reference inputs rather than introducing a parallel execution engine.

- **Reference dataset as primary ground truth.** Design the eval input contract around adjudicating an artifact against a reference dataset (input/expected pairs), while leaving room for the regular review command to contribute structured findings alongside.

- **Broaden judge model coverage deliberately.** Provide a canonical capability for non-SDK provider models to read ground-truth files on request, so judge model choice is governed by capability rather than by which provider happens to read files natively — but stage this as a secondary extension, not the foundation.

## Architectural Principles

- **Additive over migratory.** The numeric-scoring foundation extends existing result models (`ReviewResult`, `ActionResult`) by adding fields, never by removing or repurposing the verdict. Verdict remains authoritative at the summary level. Any eventual migration of non-summary levels from verdict to score is staged behind existing behavior, never a breaking change in the foundation.

- **Score is primary; verdict is derived.** The numeric score is the model's primary output. The verdict is *derived from the score* by a configurable threshold (e.g. a score at or above a pass threshold maps to `PASS`, a middle band to `CONCERNS`, below a floor to `FAIL`), not emitted independently by the model. This guarantees the verdict and score never disagree, and it keeps the verdict — which the checkpoint machinery consumes — a deterministic function of the measured score rather than a second opinion. The threshold values are a slice-design concern; that the verdict derives from the score is the architectural commitment.

- **One judgment per case.** An `eval:judge` action adjudicates **one case** (one artifact against one ground-truth reference) and returns one result (score + verdict + findings). Evaluating a multi-case dataset is a *composition of single judgments* — the pipeline expands one judgment per case and aggregates their scores — not a single action that loops internally over cases. This keeps the action's abstraction boundary, its result model, and its persistence uniform whether it runs once or as part of a dataset sweep.

- **Per-case results are retained, not just the aggregate.** A dataset evaluation produces N per-case results and one aggregated step-level scalar. The per-case results (which cases scored low, which findings applied where) are retained, because the "track quality over time" motivation is meaningless if only the aggregate survives. The exact persistence shape is a slice-design concern; that per-case data is not discarded is the architectural commitment.

- **Scalar summarizes vector.** The headline output is a single 0–100 scalar. That scalar is understood to summarize a latent per-criterion vector; the components are recorded where cheap to do so but are not surfaced or depended upon initially. Pipelines consume the scalar; the vector is latent capability for later.

- **Capability-gated model support.** Which models can serve as judges, and against what ground truth, is determined by provider capability (can it read files?) and prompt-injection limits — not by provider identity. The read-file-on-request capability exists to lift that gate for non-SDK models when needed.

- **Gate composition is a resolved decision, not an accident.** How an eval verdict/score and a review verdict combine into a single checkpoint gate (combined, separate, or per-review-type) is an explicit architectural decision made during this component's slice design, not an emergent property of action ordering.

## Current State

The pipeline action system is **open**: actions register themselves into a module-level registry (`register_action`) and satisfy an `Action` protocol exposing `action_type`, `execute`, and `validate`. The built-in action set is `dispatch | review | summary | compact | checkpoint | cf-op | commit | devlog`. Adding a new action is additive — a new protocol-satisfying class plus a registry entry — with no change to the executor core.

The **review subsystem** already provides a provider-agnostic "intelligent agent + file access + structured output" execution path (`run_review_with_profile`). It resolves a provider profile, builds a system+user prompt, injects file/diff/rules content when the provider cannot read files natively, runs a one-shot agent, and parses the response into a structured result carrying a verdict and findings.

The **result contract** is already shaped for what eval needs: an action result carries `verdict` and `findings` fields, and the verdict enum is `PASS | CONCERNS | FAIL | UNKNOWN`. The `sq run --step-done --verdict` flow consumes exactly these verdict values to advance the checkpoint state machine.

**Provider/model support** is governed by a profile registry: `sdk` (Claude Code session), `openai`, `openrouter` (any gateway model), `gemini`, `local` (Ollama/vLLM/LM Studio), `openai-oauth` (Codex), plus user-defined profiles. Only providers with a file-reading capability (SDK, Codex) read project files directly; all others receive file contents injected into the prompt, subject to a per-file and total injection cap.

**Constraints the current system imposes.** There is no numeric quality signal anywhere — only the categorical verdict. There is no notion of ground truth beyond a diff/ruleset/parent-doc. There is no reference-dataset concept in the action or persistence layers. And non-SDK provider models cannot request a file mid-judgment; they can only judge what was injected up front, which is bounded by the injection cap.

## Envisioned State

At completion, an `eval:judge` action is a first-class pipeline citizen. A pipeline step can name it, point it at a reference dataset (and optionally at an artifact and supporting ground-truth files), and receive back a numeric score, a verdict, and structured findings — persisted like any review output. Because the result carries a verdict in the established vocabulary, a downstream checkpoint gates on it through the existing `--step-done --verdict` machinery; because it also carries a score, gates and trackers can threshold on the numeric signal.

The result models throughout the review-and-action layer carry a numeric score field alongside the verdict. Reviews may optionally populate it; eval always does. Summary-level reporting still leads with the verdict, but the score is present wherever a result is, available for thresholding, trend tracking, and eventual promotion to the primary gate signal at non-summary levels.

Judge model selection is governed by capability: SDK and Codex judges read ground-truth files natively; other provider models either receive injected content or, once the read-file capability lands, request files on demand — making the full profile registry viable for file-grounded judging.

From a system perspective, eval closes squadron's loop: the executor produces artifacts (dispatch), critiques them against rules (review), and now *measures* them against ground truth (eval) — all through the same action protocol, the same provider machinery, and the same checkpoint gates.

## Technical Considerations

- **Numeric-scoring model migration.** Adding a score to `ReviewResult` / `ActionResult` touches models that every existing pipeline depends on, plus the response parser and the persistence layer. This must be additive and backward-compatible: verdict stays authoritative, score is optional on existing producers and required only on eval. This is the riskiest change in the component and is deliberately isolated as the keystone slice, done first and alone, so eval builds on a settled foundation.

- **Output parsing is the one non-free engine change.** The review engine is parameterized by template for prompt, model, inputs, and tools, so eval reuses it for those. But the response parser extracts verdict + findings from a fixed structured-output contract and does not currently read a score. Eval requires extending the parser — shared infrastructure used by every provider profile — to extract a numeric score. At minimum the architecture constrains: the score is a single required top-level numeric field in the structured output, validated to the 0–100 range; an out-of-range or absent score is a parse failure, not a silently coerced value. The full output schema (field names, finding shape) is a slice-design concern, but the score being a required, range-validated field of the shared parser contract is the architectural commitment.

- **Score-to-verdict mapping.** Because the verdict is derived from the score (see Architectural Principles), the action computes the verdict by thresholding the parsed score, rather than asking the model for an independent verdict. This makes verdict derivation deterministic and keeps it consistent with the score the checkpoint machinery's gating ultimately reflects. The threshold band values (pass floor, concerns band) are a slice-design and configuration concern; the derivation direction (score → verdict, never the reverse) is fixed here.

- **Failure modes and their verdict mapping.** Eval:judge is an LLM call against ground-truth inputs; its failure modes must map to observable, non-passing outcomes. Enumerated: unparseable model response; score absent or outside 0–100; missing/unreadable ground-truth file or dataset case; provider unavailable; injected content exceeding the cap. The architectural commitment is that no failure mode silently yields a passing result — a parse or input failure produces `UNKNOWN` (cannot judge) and a substantive negative judgment produces `FAIL`, with the distinction logged at WARNING or above so a gating step never advances on an unobserved failure. Eval inherits the review subsystem's established parse-failure behavior where it applies; the score field adds new parse-failure cases (absent/out-of-range) that this component must handle, not inherit. Per-failure-mode detail is slice-level; the no-silent-pass mapping is architectural.

- **Reference dataset resolution and loading.** A reference dataset (input/expected pairs) is new persistent state with no current home in squadron. Open decisions for slice design: where datasets live (a squadron config tree vs. CF artifact conventions), how a pipeline step references one, how cases are iterated, and how per-case scores aggregate into a step-level scalar. The dataset *materials* are out of scope; the *mechanics of pointing an action at a dataset and looping over its cases* are in scope.

- **Injection cap binds initial provider scope.** Providers that cannot read files receive injected content under a bounded cap. Because the read-file-on-request capability is a deliberately *later* slice, the initial eval slices have a binding limitation, stated here as scope rather than deferred as a future fix: **until the read-file capability lands, file-grounded `eval:judge` is supported on file-reading providers (SDK, Codex) only.** Non-file-reading providers work only when a case's ground truth plus artifact fit within the injection cap; per-case chunking does not rescue a single case whose own ground truth exceeds the cap. This is an explicit constraint on the first two slices, not an open question.

- **Read-file-on-request capability for non-SDK judges.** To make non-SDK provider models viable file-reading judges, this component owns a minimal, canonical capability with a defined boundary: **a single read-file tool** — the model emits a request naming a path, squadron reads the file (scoped to the run's working directory / ground-truth roots) and returns its contents — invoked within the existing one-shot judge call. It is explicitly **not** a general multi-tool agentic loop: it adds one file-serving tool, not a write/bash/tool-dispatch cycle. That general loop is initiative 260's scope; 260 may later consume this single tool, but this component does not depend on 260 and does not attempt to be a partial 260. It is a secondary, later slice: the core eval mechanics land first on providers that already read files.

- **Eval/review gate composition.** Eval and review are both verdict-producing actions. How they compose into a single checkpoint gate — combined into one verdict, kept as separate gates, or chosen per review type — is undecided and must be resolved during slice design. It affects the checkpoint expansion and the `--step-done` contract.

- **Scalar/vector relationship.** The 0–100 scalar is the consumed signal; a per-criterion vector is latent. The scoring schema should not foreclose recording vector components later, but must not surface or require them now — avoid designing a rich criterion-vector API before there is a consumer for it.

## Anticipated Slices

This is exploratory, not a commitment. The keystone slice is ordered first deliberately; the read-file capability is deliberately last.

- **Numeric scoring foundation (keystone — first).** Add an additive `score` to `ReviewResult` / `ActionResult`, thread it through the response parser and persistence, keep verdict authoritative at the summary level. No eval logic yet — this de-risks the cross-cutting model change in isolation.

- **`eval:judge` action, single-case.** A new `eval` action type and `eval:judge` variant reusing the review engine with a judge system-prompt and ground-truth inputs, producing score + verdict + findings for a single artifact. Proves the action wiring against the open registry on file-reading providers.

- **Reference dataset & per-case loop.** Dataset resolution/loading, iteration over cases, aggregation of per-case scores into a step-level scalar. The bulk of the new infrastructure lives here.

- **Eval/review gate composition.** Resolve and implement how an eval result and a review result compose into a single checkpoint gate.

- **Read-file-on-request tool for non-SDK judges (secondary — later).** The canonical minimal capability letting non-SDK provider models request files mid-judgment, lifting the injection-cap constraint for those providers.

## Related Work

- **Initiative 100 (Orchestration v2)** — supplies the agent registry, provider profiles, and the review engine (`run_review_with_profile`) that `eval:judge` reuses. See [100-arch.orchestration-v2.md](100-arch.orchestration-v2.md).
- **Initiative 140 (Pipeline Foundation)** — supplies the action protocol and registry, the executor and step expansion, the model resolver, and the `--step-done --verdict` checkpoint machinery that eval results gate through. See [140-arch.pipeline-foundation.md](140-arch.pipeline-foundation.md).
- **Initiative 260 (Non-SDK Agent Tool Use)** — a related but separate capability. 260 builds a full agentic tool loop for non-SDK providers; this component instead owns a minimal read-file-on-request tool tailored to judging. The two are independent; 260 may consume this component's read-file capability if it ships. See [260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md](260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md).
- **Initiative plan** — [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md), initiative 300 entry.
