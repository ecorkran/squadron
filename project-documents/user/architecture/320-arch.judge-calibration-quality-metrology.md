---
docType: architecture
archIndex: 320
component: judge-calibration-quality-metrology
initiative: judge-calibration-quality-metrology
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [100, 140, 300, 340]
dateCreated: 20260717
dateUpdated: 20260717
status: not_started
---

# Architecture: Judge Calibration & Quality Metrology

## Overview

Initiative 300 put LLM judges at squadron's pipeline decision points: an artifact is scored against its in-repo ground truth, the score is thresholded into a verdict, and the engine gates on it. What 300 deliberately did **not** do is measure whether those judgments are any good. Its scores are treated as advisory, its thresholds are set conservatively by human judgment rather than by evidence, and 300-arch names this gap explicitly: *"Measuring whether a judge actually is reliable is explicitly out of scope here and is the reason [320] exists."*

This component is that measurement layer. It answers two questions the engine currently cannot: **"how much can I trust these judges?"** and **"is model X an overreacher while model Y rubber-stamps?"** It does so with no curated dataset — the ground truth for judge quality is **the human, sampled**. The operator spot-checks a sample of judge verdicts; the system records those human calls and reports judge-vs-human agreement and judge-vs-judge dispersion. Because trust is not uniform — it scales with the strength of the in-repo ground truth (high for tasks-vs-slice, weak for arch-vs-concept) — calibration is computed **per artifact level**, and its output feeds 300's escalate-vs-auto-gate threshold configuration.

The same metrology shape is applied to a second oracle: a **code-quality baseline**. The tech-debt-audit analysis skill (forked MIT Claude skill, adapted for squadron, shipped in the 340 analysis pack) is run across projects to capture a measurable baseline of code-quality findings. A dispatch-side **prompt-chaining pre-emption prompt** — front-loading avoidance of the issue classes the audit actually finds — is the first measurable customer of that baseline: if it works, audit-findings-per-project drops.

**Scope.** The metrology data layer (recording human sample verdicts and audit findings alongside 300's persisted judge results), the agreement/dispersion/trend reporting over that data, the calibration-to-threshold feedback into 300's gate configuration, the cross-project tech-debt-audit baseline harness, and the pre-emption prompt with its delta measurement.

**Motivation.** 300's gates are only as good as the trust placed in them, and today that trust is guessed, not measured. Without calibration, thresholds stay pinned conservative forever and the human stays in loops a trustworthy judge could close. Without a quality baseline, "squadron produces good code" remains anecdote. Two oracles on a shared metrology spine (queryable persistence + trend reporting), with distinct headline analyses: human-sampled agreement for design quality, audit-findings delta for code quality.

## Design Goals

- **Measured trust per artifact level.** Replace guessed judge reliability with reported judge-vs-human agreement, computed per artifact level (tasks-vs-slice, slice-design-vs-arch, arch-vs-concept), so the trust gradient 300 asserts becomes a measured quantity.

- **Cross-judge comparability.** Report judge-vs-judge dispersion on the same artifacts, so systematic bias between models ("X overreaches, Y rubber-stamps") is visible and model selection for a gate is an informed choice.

- **Cheap human sampling.** The human oracle only works if sampling is low-friction: the operator reviews a small sample of judge calls in the normal course of work, not a dedicated labeling session. Sampling ergonomics are a first-class design constraint, not an afterthought.

- **Calibration feeds the gates.** Measurement closes the loop: agreement results inform 300's template-level/step-override threshold config, moving a trustworthy judge from advisory toward auto-gate and keeping a weak one escalating. Calibration output is configuration, not a new gating mechanism. Note the feedback's resolution: calibration is keyed by (template, model) but 300's threshold config has a template/step dimension and no model dimension, so per-model calibration is *actionable* only at config time — the operator picks a model and its threshold together for a gate. A step whose model is drawn at runtime (e.g. a 180 pool) cannot vary its threshold with the model actually selected; that limit is inherent to the stated feedback path, and the calibration-to-threshold slice inherits it rather than solving it.

- **A code-quality baseline with a first customer.** Capture tech-debt-audit findings across projects as a queryable baseline, then measure whether the dispatch-side pre-emption prompt reduces findings — proving the metrology can detect an intervention's effect, not just accumulate numbers.

## Architectural Principles

- **The human is sampled, not resident.** 300 removed the human from routine gates; 320 must not reinstall them as a labeling workforce. Human verdicts are collected on a sample, opportunistically, with recording cheap enough to happen inline. Any design that requires exhaustive human review of judge output has failed.

- **No curated dataset.** Judge quality is measured against sampled human judgment on the project's own artifacts, never against manufactured input/expected-output pairs. This is the same rejection 300 made of reference-dataset eval, carried forward: squadron's ground truth is intrinsic.

- **Read-side over 300's write path.** 300 persisted scores as first-class queryable fields and results as self-describing (provenance) precisely so 320 could consume them. This component reads and annotates that record; it does not modify the judging path, the parser, or the result models' write semantics. Where a latent field exists (e.g. the reserved `criteria` map), 320 populates or reads it — it does not re-thread plumbing.

- **Calibration is per artifact level.** Trust varies with ground-truth strength, so agreement and dispersion are always computed and reported at the artifact-level grain, never as one global "judge accuracy" number. A single blended number would erase exactly the distinction that makes calibration useful to the gates.

- **Variance, then baseline, then intervention.** The metrology captures the oracle's own run-to-run noise floor *before* it captures a baseline, and the baseline *before* any customer acts on it. Because the tech-debt audit is non-deterministic run-to-run, a findings-count delta smaller than the audit's own variance is indistinguishable from noise; measuring that variance first (repeated audits on unchanged code) is what lets the pre-emption prompt's effect be reported as a *credible directional signal* rather than an artifact of noise. The pre-emption prompt therefore ships only after both the variance and the baseline exist. This ordering discipline applies to any future intervention the metrology enables.

- **Graduation is not a one-way door.** Moving a judge toward auto-gate removes the artifact from the escalation flow — which is precisely where human spot-checks were coming from. If graduation silently ends sampling, false-PASS on auto-gated artifacts becomes systematically unobservable (the most dangerous error class is exactly the unsampled one) and the agreement sample freezes, so within-configuration drift goes undetected forever. The architecture therefore commits to **continued forced random sampling of auto-gated results** — a residual "trust but verify" rate that survives graduation — so the instrument keeps being checked after the human stops seeing every call. The rate is slice-design detail; that graduation does not end sampling is fixed here.

- **Blind capture, not anchored.** The human oracle only measures agreement if the human's judgment is formed independently of the judge's. If the operator reads the judge's score, verdict, and findings *before* recording their own verdict, their call is anchored toward agreement — the same anchoring failure 300-arch cites for LLM scores, applied to the human. That inflates the agreement number, which is the exact input that loosens gates. The capture surface therefore presents the artifact and its ground truth for an **independent human verdict, with the judge's output withheld until after** the human commits (or reveals it only for optional post-hoc annotation). Whether capture is blind is an architectural constraint on the capture surface, not slice-level ergonomics.

- **Honest statistics at small n.** Samples will be small — a handful of human spot-checks per artifact level, a handful of projects in the audit baseline. Reports must carry their sample sizes and refuse to imply precision they don't have. A calibration report that overstates confidence is worse than none: it would move thresholds on noise.

## Current State

Initiative 300 is complete: judges run as review-action templates, emit 0–100 scores with findings, verdicts derive from scores by conservative thresholds, results carry provenance (judge-derived vs. review-produced vs. composed), and scores persist as first-class queryable fields. Judge-gated cycles (303) and gate composition (304) let pipelines run review→fix→re-review unattended and compose judge+review legs at one gate.

But the system is flying on uncalibrated instruments:

- **No record of whether a judge was right.** A judge verdict is persisted; whether the operator agreed with it is not. Spot-checks happen informally and leave no trace, so there is no agreement data to learn from.
- **Thresholds are guesses.** 300's bands are deliberately conservative defaults set by judgment. Nothing measures whether tasks-vs-slice judges have earned a lower escalation rate, so every gate pays the conservative tax indefinitely.
- **No cross-judge visibility.** Multi-sample judging (300 Future Work 1) can reduce variance at execution time, but nothing measures dispersion across judges or models, so systematic bias is invisible.
- **No code-quality measurement.** The tech-debt-audit skill exists in the 340 analysis pack and runs ad hoc; its findings are read once and discarded. There is no baseline, no cross-project comparison, and no way to tell whether dispatch-prompt changes improve the code squadron's pipelines produce.

## Envisioned State

The persisted judge record gains a thin metrology layer around it. When the operator spot-checks a judge call, their verdict is recorded against the judge's result in one cheap step. From that accumulating sample, the system reports — per artifact level and per judge/model — agreement with the human, dispersion across judges, and trend over time, each report carrying its sample size. Those reports inform threshold configuration: a judge with demonstrated agreement at an artifact level is configured toward auto-gate at that level; a judge that disagrees with the human, or judges that disagree with each other, stay advisory and escalate. The escalate-vs-auto-gate decision 300 made configurable becomes evidence-driven.

In parallel, the tech-debt-audit harness runs across squadron-managed projects and persists normalized findings as a code-quality baseline. The dispatch-side pre-emption prompt front-loads avoidance of the issue classes the baseline actually contains, and subsequent audit runs measure the delta. The two oracles share a metrology *spine* — persist oracle verdicts queryably, carry sample sizes, report trend over time — and reuse that spine rather than re-inventing storage and trend reporting twice. What they do **not** share is the headline analysis: the human oracle produces inter-rater agreement at the artifact-level/judge-configuration grain; the audit oracle has no agreement dimension (nothing compares to a human), reports at the project/issue-class grain, and its headline is a before/after count delta against a noise floor. The shared surface is honestly the persistence conventions and trend reporting, not one report path — expect two analysis paths behind a common spine, not a single forced abstraction.

At completion, squadron can answer: "How trustworthy is this judge at this artifact level?", "Do my judges agree with each other?", and "Is the code my pipelines produce getting better?" — with numbers, sample sizes, and trend, not anecdote.

## Technical Considerations

- **Sampling capture ergonomics.** Where and how the operator's spot-check verdict enters the system is the make-or-break design problem. The capture point must sit in an existing workflow surface (CLI at minimum, honoring interface parity if other surfaces are added), take seconds, and attach unambiguously to the specific persisted judge result being checked. Which results are *offered* for sampling (random sample, disagreement-triggered, escalation-triggered) is a slice-level decision with statistical consequences — a biased sample yields a biased agreement number.

- **Agreement and dispersion at small n.** With a handful of samples per artifact level, naive percent-agreement is fragile and chance-corrected metrics behave badly. The metric choices are slice-design detail; the architectural constraint is that every reported number carries its n, and the calibration-to-threshold feedback must define a minimum-evidence floor below which it refuses to recommend loosening a threshold.

- **Comparability across template and model versions — and the write-path tension it forces.** A judge template revision or model change can shift score distributions, silently invalidating accumulated calibration. Metrology records must therefore identify the judge configuration they measured, and reports must not blend measurements across incompatible configurations. **But the persisted record cannot fully satisfy this read-side today:** `ReviewResult` ([review/models.py](../../../src/squadron/review/models.py)) carries `template_name` and `model` but **no template version**, so a template edited under an unchanged name blends incompatible data — the exact failure this consideration forbids. These three facts (version-keying required, read-side-only principle, no version field) are jointly unsatisfiable, so the architecture resolves the tension explicitly rather than leaving it latent:
  - **Preferred:** add a template version/content-hash to the judge result at its write site — a small **300 write-path change, coordinated as a dependency** exactly like the checkpoint multi-verdict case 300 flagged, not silently absorbed under "read-side." This makes future data reliably version-keyed.
  - **Fallback (no write-path change):** the metrology hashes the template *content* at sample-capture time and keys new samples by that hash — reliable going forward but not retroactive. Historical results and opportunistic dispersion data captured before this cannot be version-keyed, and reports must exclude or flag them, not silently pool them.
  - Either way, the granularity that ships is a slice-design decision; that version identity requires a coordinated write-path change or an explicit accept-the-blending fallback — and is *not* free read-side — is fixed here. This is the one place the "read-side over 300's write path" principle has a real edge, named so it is not discovered mid-slice.

- **Dispersion needs repeated measurements — via 300's multi-sample, not 180's fan-out.** Judge-vs-judge dispersion requires multiple judges (or multiple runs) on the same artifact. The execution mechanism this initiative relies on is **300's multi-sample judging option** (300 Future Work 1) — deliberately *not* 180's `fan_out` step type, which is owned by initiative 180 (180-slices slice 182, "Relocated from 140 future work item 10", Risk: High) and which the initiative plan explicitly disclaims as a 320 dependency ("Independent of 180"). Scoping dispersion to 300's multi-sample keeps that independence intact. Running repeated judges costs tokens, so dispersion measurement is a deliberate, sampled activity rather than a per-gate default; the metrology must accept dispersion data opportunistically (when multi-sample ran anyway) as well as from dedicated calibration runs. If a future need genuinely requires general parallel fan-out, that introduces a 180 dependency to be surfaced and coordinated then — it is not assumed here.

- **Normalizing an LLM-authored audit, and measuring its noise floor.** tech-debt-audit is a markdown skill whose output is prose-shaped and non-deterministic run-to-run. Using it as an oracle requires normalizing findings into a persistable, comparable form (category, location, severity) without pretending more precision than the underlying analysis has. The audit's own variance is not a footnote — it is a measurement the metrology must *take*: repeated audits on unchanged code bound the run-to-run noise, and no reported delta is credible below that floor (see *Variance, then baseline, then intervention*). The code-quality oracle has the same reliability questions as the judges; the metrology treats the audit's variance as a first-class measured quantity, not an acknowledged-then-ignored caveat.

- **Attribution of the pre-emption delta.** Audit-findings-per-project will move for many reasons (different projects, models, slice difficulty), and the audit's own run-to-run noise (above) sets a floor below which no delta is meaningful. The pre-emption measurement is an observational before/after, not a controlled experiment; the reporting must present it as such and must report the delta against the measured noise floor, not in isolation. The goal is a credible directional signal, not causal proof — overclaiming here, especially at a "handful of projects," would undermine the initiative's core value of honest measurement.

- **Pre-emption data flows down as configuration, never up at runtime.** The pre-emption prompt must front-load the issue classes the audit actually finds — so metrology-derived content must reach a dispatch prompt. The direction of that data flow is an architectural commitment, not a mechanism detail: the pre-emption content is a **generated static prompt fragment** (the operator/tooling regenerates it from the baseline; it flows *down* into dispatch config like any other prompt material). Dispatch does **not** query the metrology layer at pipeline runtime — that would invert the dependency (140's dispatch path depending upward on a 320 store) and add a new runtime failure mode to every dispatch when the store is absent. This initiative touches a *dispatch-facing* surface (the Non-Goals bound the *judging* path, not the dispatch path), so the direction is stated here to keep it one-way. The regeneration cadence and fragment format are slice-design detail; that the flow is down-only is fixed.

- **Where metrology data lives — a keystone that needs real constraints, not deferral.** Judge results live in squadron's existing persistence; human samples, audit findings, and derived calibration reports need a durable home that can join against those results and aggregate **across projects** — a new requirement, since 300's persistence is per-run/per-project. Because *every other slice consumes this store*, deferring its whole shape would make the keystone slice an architecture phase in disguise. The architecture therefore fixes three load-bearing commitments and leaves only representation to slice design:
  - **Stable project identity.** Cross-project reports key on a project identifier that must be stable across runs and machines. It is a deliberate, explicit key (repo-derived, e.g. remote URL or a recorded project id — *not* a mutable filesystem path); the exact derivation is slice-design detail, that it is stable and explicit is fixed.
  - **Store locality.** The store lives **user-level / central** (one store aggregating across the projects a user runs), not per-repo — per-repo storage cannot aggregate across projects, which is the initiative's entire point. Joining per-project judge results into it is an ingest step, not a live cross-repo query.
  - **No hard dependency on 280.** The shared artifact store (280) is `status: not_started`; the metrology store therefore stands on its own and does **not** block on or speculatively design for 280. If 280 later ships, consolidation is a future refactor, not a prerequisite — named as a possible convergence, explicitly not a dependency.
  The commitment beyond these is queryable and joinable, not opaque; the storage representation (schema, backend) is slice-design detail.

## Anticipated Slices

Exploratory, not a commitment. The data layer is the keystone and comes first.

- **Metrology data layer & sample capture (keystone).** The durable home for human sample verdicts keyed to persisted judge results (with judge-configuration identity), plus the low-friction capture surface. No reporting yet — de-risks the storage/join/ergonomics decisions in isolation.
- **Agreement & dispersion reporting.** Judge-vs-human agreement and judge-vs-judge dispersion, per artifact level and judge configuration, with sample sizes and trend.
- **Calibration-to-threshold feedback.** The documented, evidence-floored path from calibration reports to 300's template/step threshold config — how a judge graduates from advisory to auto-gate at an artifact level.
- **Tech-debt-audit baseline harness.** Run the audit across squadron-managed projects, normalize and persist findings, report the cross-project baseline.
- **Pre-emption prompt & delta measurement.** The dispatch-side prompt-chaining prompt front-loading avoidance of baseline issue classes, plus before/after reporting against the baseline.

## Non-Goals

- **No curated reference dataset.** Carried forward from 300: manufactured input/expected-output pairs grade models in the abstract and are a different product. The oracles here are the sampled human and the audit, on real project artifacts.
- **No change to the judging path.** Judges, scoring, parsing, threshold mechanics, and gate composition are 300's, and they are done. 320 measures and configures; it does not re-architect the write path.
- **No automatic threshold mutation.** Calibration *informs* threshold config; it does not silently rewrite it. Loosening a gate is an operator decision made on reported evidence — an autonomous self-tuning loop is explicitly out of scope.
- **No general observability platform.** The metrology serves two oracles and the gates they calibrate. Dashboards, generic metrics pipelines, or telemetry beyond that purpose are not this initiative.

## Related Work

- **Initiative 300 (Intrinsic LLM Judging & Scoring)** — the measured subject: judges, scores, provenance, queryable score persistence, conservative thresholds awaiting calibration. 300-arch explicitly delegates score reliability, time-series/trend analysis, and inter-judge agreement to this initiative. See [300-arch.eval-actions-llm-as-judge-scoring.md](300-arch.eval-actions-llm-as-judge-scoring.md).
- **300 Future Work 1 (Multi-Sample Judging)** — the execution-time mechanism dispersion measurement can piggyback on. See [300-slices.eval-actions-llm-as-judge-scoring.md](300-slices.eval-actions-llm-as-judge-scoring.md).
- **Initiative 140 (Pipeline Foundation)** — the executor and checkpoint machinery calibration-informed thresholds ultimately gate through. (Parallel fan-out is 180's `fan_out`, not 140's; this initiative relies on 300's multi-sample option, not fan-out — see Technical Considerations.) See [140-arch.pipeline-foundation.md](140-arch.pipeline-foundation.md).
- **Initiative 340 (Skill Pack Infrastructure)** — ships the analysis pack containing the `tech-debt-audit` skill this component's code-quality oracle runs. See [340-arch.skill-pack-infrastructure.md](340-arch.skill-pack-infrastructure.md). (The skill's canonical name is `tech-debt-audit` — matching its frontmatter `name:`, file `commands/analysis/tech-debt-audit.md`, and dispatch `/analysis:tech-debt-audit`. An earlier `tech-debt-analyze` spelling in the 340-band docs was reconciled to this name.)
- **Initiative 280 (Shared Agent Artifact Store)** — not started; a candidate relationship for the metrology store decision (see Technical Considerations), to be evaluated at slice design, not assumed.
- **Initiative plan** — [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md), entry 10.
