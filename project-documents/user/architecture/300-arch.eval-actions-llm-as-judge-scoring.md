---
docType: architecture
archIndex: 300
component: eval-actions-llm-as-judge-scoring
initiative: eval-actions-llm-as-judge-scoring
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [100, 140]
dateCreated: 20260530
dateUpdated: 20260531
status: reviewed
---

# Architecture: Intrinsic LLM Judging & Scoring

## Overview

Squadron is an excellent **deterministic workflow engine** running a **non-deterministic process**. It dispatches agents, runs reviews, persists verdicts, and gates progress — with high accuracy. But the automation breaks exactly where determinism does: at the **decision points**. A pipeline can produce a slice-design, but deciding "is this design good enough to proceed, or does a human need to look?" is a judgment call, and today that judgment is always a human's. The result is a system that works very well but requires a human in the loop at too many gates — tolerable for complex work, but heavy enough that the overhead isn't worth it for simple projects.

This component adds the missing piece: **non-human intelligence at the decision points.** It lets an LLM render a *scored judgment* on an artifact against its in-repo ground truth — does this slice-design satisfy its arch doc, do these tasks reflect their slice — so the deterministic engine can gate on that judgment instead of stopping for a human every time. Done well, the judge handles the routine calls and bubbles the genuinely hard ones up to the human.

Two concrete capabilities, both reusing machinery that already exists:

1. **A numeric score on results.** Reviews and judgments produce a `PASS | CONCERNS | FAIL` verdict today. This component adds an optional **0–100 numeric score** to the result model, so quality is *measurable* and *thresholdable*, not just categorical. This is the keystone change.
2. **An intrinsic LLM judge.** A "judge" is a **review with a judge-flavored system prompt** that emits a score. It runs on the **existing `review` action** through the existing provider-agnostic engine (`run_review_with_profile`), and composes with the **existing** `each` / `loop` / `commit` steps to drive the review→fix→re-review cycle without a human at each turn.

**What this deliberately is not.** It does *not* introduce a new `eval:judge` action, a reference-dataset facility, a per-case dataset loop, or any agentic/turn-loop inside the engine. A judge is a one-shot call — read inputs, emit a scored verdict — exactly like a review. Those other concerns were considered and removed: they are either a separate initiative (calibration/metrology, [320]) or a different product entirely (reference datasets — see Non-Goals).

**A judge's score is not assumed reliable.** LLMs are known to produce poorly-calibrated numeric scores — clustering on round numbers, anchoring on the prompt, varying run-to-run for identical input. This component does **not** assume calibrated scores; it treats early scores as *advisory* and gates conservatively until the calibration initiative ([320]) measures how much a given judge can be trusted at a given artifact level. Score *reliability* is explicitly 320's problem; 300's job is to produce, parse, persist, and conservatively gate on the score, with the cheap in-engine mitigations noted in Technical Considerations. This division is the reason 300 and 320 are separate initiatives, not one.

**Scope.** A numeric `score` field added additively to the review/action result models, parser, and persistence; one or more **judge templates** for the existing `review` action; and the conventions for using judges to gate design-phase decisions via existing pipeline steps.

**Motivation.** Squadron's automation is limited not by its workflow engine but by the absence of intelligence at its gates. A judge that can score an artifact against its parent documents and the guide's success criteria removes the human from the routine gates (advancing simple projects automatically) while preserving escalation of the hard ones (accelerating experiments on complex projects). A numeric score makes "is the quality improving?" answerable — the instrumentation a workflow engine needs to be measurably, not just anecdotally, good.

## Design Goals

- **Intelligence at the decision points.** Make a scored LLM judgment a gateable signal, so the deterministic engine can advance past routine decision points without a human and escalate only the hard ones.

- **Quality becomes measurable.** Add a numeric score alongside the verdict so artifact quality is a tracked, thresholdable quantity, not just a three-state opinion.

- **Reuse, don't rebuild.** A judge is a review template plus a score — it runs on the existing `review` action, the existing engine, and the existing `each`/`loop`/`commit` steps. No new action type, no new execution model.

- **Ground truth is what's already in the repo.** Judges adjudicate an artifact against its parent documents, the project rules, the codebase, and the phase success-criteria — all present in the project. No external answer key is manufactured or required.

- **Bubble up the hard calls.** A judge's value is as much in knowing when *not* to decide as in deciding. Where in-repo ground truth is strong (tasks vs. slice), the judge can be trusted to gate; where it is weak (arch concept vs. initiative blurb), the judgment is advisory and the decision escalates to the human. (How trust is *calibrated* per artifact level is initiative [320], not this one.)

## Architectural Principles

- **Additive over migratory.** The numeric-scoring foundation extends existing result models (`ReviewResult`, `ActionResult`) by adding fields, never by removing or repurposing the verdict. Existing verdict-gating pipelines keep working unchanged — the verdict remains the operational gating signal they consume. Any eventual migration of non-summary levels from verdict to score is staged behind existing behavior, never a breaking change.

- **The score is the source of truth; the verdict is its projection.** For a judge result, the numeric score is authoritative and the verdict is *derived from it* by a configurable threshold (at or above a pass floor → `PASS`, a middle band → `CONCERNS`, below a floor → `FAIL`). The verdict exists so the existing checkpoint machinery — which consumes verdicts, not scores — can gate on a judge result without new plumbing; it is a deterministic projection of the score, not a second opinion that could diverge from it. The threshold values are a slice-design and configuration concern; that the verdict derives from the score, one-directionally, is the architectural commitment.

- **The judge emits score + findings, not a verdict.** Because the verdict derives from the score, the judge template instructs the model to emit a score and findings and **not** an independent verdict — the action computes the verdict by thresholding the parsed score. A template thus carries its own expected output shape (the judge template expects score+findings; the standard review template expects verdict+findings); the shared parser surfaces whichever fields are present, and each use enforces what it requires. No model-emitted verdict is discarded or left to contradict the derived one, because the judge prompt does not ask for one.

- **A result declares its own provenance.** A `ReviewResult` carrying both `score` and `verdict` is ambiguous on its face: for a judge, the verdict is *derived from* the score; for a standard review, the verdict is *independently model-produced* and any score is incidental. A consumer — the checkpoint machinery, a future composition layer, a human reading a devlog — must not have to know which template ran to interpret the result correctly. The result model therefore carries a **provenance field** (the kind of result: judge-derived vs. review-produced) so the result is self-describing. This is the architectural commitment; the exact field name/enum is slice-design detail. (It also gives the calibration initiative [320] the discriminator it needs to compare judge results against review results and against human samples.)

- **A judge is one-shot, like a review.** A judge reads its inputs and emits a scored verdict in a single call. It does not request files mid-judgment, loop, or use tools. Ground truth is supplied the way reviews already supply it — natively for file-reading providers (SDK, Codex), by front-loaded injection for the rest. Any review→fix→re-review *cycle* is the existing `each`/`loop`/`commit` machinery driving repeated one-shot judges, not a loop inside the judge.

- **Scalar now; a criterion breakdown is anticipated, not finalized.** The headline, consumed output is a single 0–100 scalar — required and authoritative. A future per-criterion breakdown is anticipated, and the foundation reserves an **optional `criteria` map** (criterion name → sub-score) so adding one later *populates an existing field* rather than re-threading the parser, result models, and persistence a second time. The honest scope of that guarantee: it spares the *plumbing* migration, not necessarily a *schema* one — if criterion scoring later needs weights, per-criterion metadata, or a different key structure, the reserved shape may still evolve. The map is therefore reserved as a cheap, optional, latent field, not committed as a final schema. If even that proves wrong, the cost is one unused optional field.

## Current State

The pipeline action system is **open**: actions register into a module-level registry (`register_action`) and satisfy an `Action` protocol. The built-in set is `dispatch | review | summary | compact | checkpoint | cf-op | commit | devlog`.

The **review subsystem** already provides a provider-agnostic "intelligent agent + file access + structured output" path (`run_review_with_profile`), and it is **parameterized by a template** — system prompt, prompt builder, required inputs, allowed tools, model are all template data, not hardcoded. A judge is therefore expressible as a template; prompt, model, file injection, and the verdict contract are inherited without engine changes.

The **result contract** already carries `verdict` and `findings`, with the verdict enum `PASS | CONCERNS | FAIL | UNKNOWN` — exactly what `sq run --step-done --verdict` consumes to advance the checkpoint state machine. The **iteration constructs** already exist: `each` iterates a collection running inner steps per item, `loop` repeats steps, `commit` persists between iterations — the review→fix→re-review cycle is already expressible.

**The one gap.** There is no numeric quality signal anywhere — only the categorical verdict. The response parser extracts verdict + findings from a fixed structure and does not read a score. Closing that gap is the substance of this component.

## Envisioned State

At completion, a result anywhere in the review-and-judge layer can carry a numeric score alongside its verdict. Standard reviews may leave it unset; judges always set it. A judge is a review template with a judge system prompt: a pipeline step runs it via the `review` action, points it at an artifact and its in-repo ground truth (parent doc, rules, criteria), and receives a score, a derived verdict, and findings — persisted like any review output and gated through the existing `--step-done --verdict` machinery.

Because the score is present wherever a result is, quality is trackable over time and gates can threshold on the number. Because judging reuses the `review` action and the `each`/`loop`/`commit` steps, the human-driven review→fix→re-review cycle becomes a pipeline that runs without a human at each gate — advancing past decision points where the score clears the threshold, and escalating where it does not.

From a system perspective, this is the instrumentation the workflow engine was missing: the executor produces artifacts (dispatch), critiques them (review), and now *scores* them so the engine itself can decide whether to proceed — closing the loop the human currently closes by hand.

## Technical Considerations

- **Numeric-scoring model migration (the keystone).** Adding a score to `ReviewResult` / `ActionResult` touches models every pipeline depends on, plus the parser and persistence. It must be additive and backward-compatible: the score is optional everywhere at the model/parser layer, required only where a judge produces one. This is the riskiest change and is isolated as the first slice, done alone, so judging builds on a settled foundation.

- **Output parsing — optional at the parser, required at the judge.** The parser is extended to extract an *optional* top-level numeric `score` (and the optional `criteria` map) **when present**, ignoring it when absent — so existing score-less review responses parse exactly as before; the parser never needs to know it is in a judging context. Required-ness and 0–100 range-validation live at the **judge** use: if a judge's score is absent or out of range, the judge result is a failure (verdict `UNKNOWN`), enforced by the action, not the parser. This two-layer split is the architectural commitment; exact field names and finding shape are slice-design detail.

- **Score-to-verdict thresholds — where they live.** The verdict is computed by thresholding the parsed score (see Principles); the model is not asked for an independent verdict. The threshold *values* are configuration, but their *locus* is an architectural commitment: thresholds are **template-level config with step-level override**. A judge template carries default bands (pass floor, concerns band); a pipeline step invoking that judge may override them. Because trust varies by artifact level (see *Bubble up the hard calls*), this is what lets a strong-ground-truth judge (tasks-vs-slice) gate at a confident floor while a weak-ground-truth judge (arch-vs-concept) is configured advisory-only (a floor it effectively cannot clear, forcing escalation). Defaults are deliberately conservative — when uncertain, gate toward escalation, not auto-pass. The band values and the precise config keys are slice-design detail; that thresholds live at template-with-step-override, default conservative, is fixed here.

- **Score reliability is 320's problem; 300's mitigations are cheap and in-engine.** The hard truth (see Overview) is that an LLM's 0–100 score may be poorly calibrated — round-number clustering, prompt anchoring, run-to-run variance. 300 does not attempt to *solve* this (that is the calibration initiative [320]); it must only avoid *depending* on reliability it doesn't have. Architectural commitments: (a) scores gate conservatively (see thresholds above) and are treated as advisory until 320 calibrates a judge at an artifact level; (b) the judge template uses a structured-output constraint for the score field and a *score-with-rationale* prompt shape (require the model to justify the number), which empirically reduces anchoring; (c) the engine permits but does not require **multi-sample** judging — running a judge N times and reducing (median) via the existing `fan_out`/fan-in machinery — as a config option, not a default. None of these claims the score is reliable; they bound the damage if it isn't. Measuring whether a judge actually is reliable is explicitly out of scope here and is the reason [320] exists.

- **Failure modes and their verdict mapping.** A judge is an LLM call against in-repo ground truth; its failure modes must map to observable, non-passing outcomes. Enumerated: unparseable response; score absent or outside 0–100; missing/unreadable ground-truth file; provider unavailable; injected ground truth exceeding the cap. The commitment: no failure mode silently yields a passing result — a parse or input failure produces `UNKNOWN` (cannot judge), a substantive negative judgment produces `FAIL`, with the distinction logged at WARNING or above so a gating step never advances on an unobserved failure. **This is verified against the checkpoint machinery, not assumed:** `CheckpointAction`'s trigger thresholds include `UNKNOWN` in both the `on-concerns` and `on-fail` firing sets ([checkpoint.py](../../../src/squadron/pipeline/actions/checkpoint.py)), so a checkpoint with either trigger *does* fire on an `UNKNOWN` judge result — the no-silent-pass guarantee holds with the existing 140 machinery, no change required. The judge inherits the review subsystem's parse-failure behavior; the score field adds new absent/out-of-range cases this component handles. (Note: "score present but poorly calibrated" is a *different* failure mode — not a parse failure — and is handled by conservative gating + [320] calibration, not by this enumeration.)

- **How a step selects a judge.** "A judge is a review template" is invokable today with no new selector: the `review` step schema already requires a `template` field ([steps/review.py](../../../src/squadron/pipeline/steps/review.py)), so a pipeline step runs a judge by naming the judge template (e.g. a `review` step with `template: judge.slice-vs-arch`) exactly as it names any review template. No new step type, no new template-selection mechanism. The connective work is therefore just *authoring* the judge templates and the threshold/escalation config (above), not extending the pipeline schema.

- **Ground-truth size vs. the injection cap.** Non-file-reading providers receive ground truth by injection under a bounded cap. For single-artifact intrinsic judging this is rarely a problem — a judge reads one artifact plus its parent doc/criteria, comparable in size to what reviews inject today. Front-loading by injection is the design; there is deliberately no read-file/turn-loop in this component. If a future case (e.g. a large code review) genuinely needs on-demand file fetching, that is a separately scoped problem, not a foundation this component must lay.

- **Score persistence must stay queryable; time-series is 320's.** The motivation ("is quality improving over time?") depends on scores being retrievable and comparable across runs, not buried in an opaque blob. Architectural commitment for the foundation slice: persist the score as a **first-class, queryable field** of the result record (not only inside a serialized JSON payload), so cross-run comparison does not require deserializing every record. The foundation does not build the time-series/trend machinery itself — that analysis layer is the calibration/metrology initiative [320]; 300 only ensures the score is stored in a shape 320 can query. Exact storage representation (column vs. indexed field) is slice-design detail; queryable-not-opaque is the commitment.

- **Judge/review gate composition — and an honest scope boundary.** A judge and a standard review can both gate a step. Whether their results combine into one gate, stay separate, or are chosen per review type is an open slice-design decision. **Verified constraint:** the checkpoint machinery is single-verdict-per-step today — `_find_review_verdict` returns the *first* non-`None` verdict among prior outputs ([checkpoint.py](../../../src/squadron/pipeline/actions/checkpoint.py)), so it picks one verdict, it does not combine several. Therefore any composition that needs *two* verdicts (judge AND review) considered together would require changing the checkpoint machinery — which is **initiative 140 territory, not additive to 300**. This is the one place the *Additive over migratory* principle has a real edge: the gate-composition slice may discover it must either (a) compose upstream of the checkpoint (reduce judge+review into one verdict before the checkpoint sees it — additive, preferred) or (b) extend the checkpoint to accept multiple verdicts (a 140 change, explicitly out of 300's additive scope and to be coordinated as such, not silently absorbed). The slice must pick (a) where possible and escalate (b) as a 140 dependency if not. Naming this here so the boundary is not a surprise discovered mid-slice.

## Anticipated Slices

Exploratory, not a commitment. The keystone is ordered first deliberately.

- **Numeric scoring foundation (keystone — first).** Add the optional `score` (and reserved optional `criteria` map) to the result models, thread it through the parser and persistence, keep the verdict authoritative for existing pipelines. No judging logic yet — this de-risks the cross-cutting model change in isolation.

- **Judge template(s) for the review action.** One or more judge system-prompt templates that emit score + findings, run via the existing `review` action, producing a score and derived verdict for a single artifact against its in-repo ground truth. Prioritize the **design-phase gates** (slice-design vs. arch, tasks vs. slice) where human-in-loop is heaviest today.

- **Judge-gated cycle conventions.** Document/define how `each`/`loop`/`commit` + a judge express the review→fix→re-review cycle as an unattended pipeline, including where the score gates automatically vs. escalates.

- **Gate composition.** Resolve and implement how a judge result and a standard review result compose into a single checkpoint gate.

## Non-Goals

- **No new `eval:judge` action.** Judging is the existing `review` action with a judge template. A distinct action type was considered and rejected as duplicative.

- **No agentic / turn loop inside the engine.** Judges are one-shot. Tool-using, file-on-request, multi-turn execution belongs to the orchestrator vision (a far-future rung; see Related Work), explicitly *above* the engine, not inside an action.

- **Reference-dataset eval is a separate concern, not deferred scope here.** A reference dataset (curated input/expected-output pairs scored against a known-correct answer) is a *different product*: it manufactures external ground truth to grade a model/prompt in the abstract. Squadron's judging needs none — its ground truth is the project's own documents. Reference datasets are also a poor fit here (artifact outputs are non-deterministic; valid solutions vary; and at the top of the artifact hierarchy the ground truth is weak). The related-but-distinct question "how good are the judges themselves?" (inter-judge agreement, human-sampled calibration) is initiative [320], not a dataset.

## Related Work

- **Initiative 100 (Orchestration v2)** — supplies the agent registry, provider profiles, and the review engine (`run_review_with_profile`) a judge reuses. See [100-arch.orchestration-v2.md](100-arch.orchestration-v2.md).
- **Initiative 140 (Pipeline Foundation)** — supplies the action protocol/registry, the executor, `each`/`loop`/`commit` steps, the model resolver, and the `--step-done --verdict` checkpoint machinery judge results gate through. See [140-arch.pipeline-foundation.md](140-arch.pipeline-foundation.md).
- **Initiative [320] (Judge Calibration & Quality Metrology)** — the sibling concern: how much to trust a judge at a given artifact level, inter-judge agreement ("does model X overreach while Y rubber-stamps?"), human-sampled calibration, and a code-quality baseline (tech-debt-audit). Depends on this component's judges existing first.
- **Orchestrator / "organism" (far-future, Future Work)** — an agent that drives Context Forge + squadron and acts on their outputs, consulting the human only on hard calls. This is the only place a true agentic loop belongs, and it sits *above* the engine consuming its CLI/JSON — not inside a pipeline action. Naming it here keeps its loop from being smuggled back into this component.
- **Initiative plan** — [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md).
