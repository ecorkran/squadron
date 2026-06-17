---
docType: slice-plan
parent: 300-arch.eval-actions-llm-as-judge-scoring.md
project: squadron
dateCreated: 20260604
dateUpdated: 20260604
status: not_started
---

# Slice Plan: Intrinsic LLM Judging & Scoring

## Parent Document
`300-arch.eval-actions-llm-as-judge-scoring.md` — High-Level Design: Intrinsic LLM Judging & Scoring

## Planning Context
Architecture-level. The parent architecture document settles the design across three review rounds; this plan breaks it into vertical slices. The keystone numeric-scoring slice is ordered first and done alone, per the architecture's explicit instruction. Every slice is additive — existing verdict-gating pipelines keep working unchanged at each step.

The architecture's "Anticipated Slices" section sketches four slices. This plan refines that into five: the judge **enforcement layer** (validation, score→verdict thresholding, provenance) is separated from the judge **templates**, because the two-layer parser/action split is an explicit architectural commitment, the enforcement logic is independently testable, and templates cannot be gated until it exists.

---

## Foundation Work

1. [x] **(300) Numeric Scoring Foundation** — Add an optional `score` field (0–100) and a reserved optional `criteria` map (criterion name → sub-score) to the result models (`ReviewResult`, `ActionResult`) additively. Extend the response parser to extract a top-level numeric `score` and the `criteria` map **when present**, ignoring them when absent so existing score-less review responses parse exactly as before. Persist the score as a first-class, queryable field of the result record (not buried in an opaque JSON blob). No judging logic, no validation, no thresholding — the parser stays lenient and never knows it is in a judging context. This de-risks the cross-cutting model/parser/persistence change in isolation.
   - **Value:** Architectural enablement — quality becomes a representable, persistable, queryable quantity; every later slice builds on this settled foundation.
   - **Success Criteria:**
     - `score` and `criteria` are optional on `ReviewResult` / `ActionResult`; constructing a result without them succeeds unchanged.
     - The parser extracts `score` and `criteria` when present and returns the prior shape when absent (covered by a test using a real score-less review response and a real score-bearing response).
     - The score persists as a queryable field; a stored result can be retrieved and its score compared without deserializing an opaque payload.
     - All existing verdict-gating pipelines and the full existing test suite pass unchanged.
   - **Dependencies:** [100, 140] (result models, parser, persistence from existing initiatives).
   - **Interfaces:** Provides the `score` / `criteria` fields on the result contract and the parser's optional-score extraction; consumed by every subsequent slice.
   - **Risk Level:** Medium (touches models every pipeline depends on; mitigated by additive-only, backward-compatible design and isolation).
   - **Relative Effort:** 3/5

---

## Feature Slices (in implementation order)

2. [ ] **(301) Judge Enforcement Layer** — The second half of the two-layer split. At the judge **use** (not the parser): require the score, range-validate it to 0–100, and derive the verdict by thresholding the score (at/above a pass floor → `PASS`, middle band → `CONCERNS`, below a floor → `FAIL`). Thresholds live at **template-level config with step-level override**, defaults deliberately conservative (gate toward escalation when uncertain). Add the **provenance** field to the result (judge-derived vs. review-produced) so a result carrying both score and verdict is self-describing. Map the enumerated failure modes to non-passing verdicts: absent/out-of-range score, unparseable response, missing/unreadable ground-truth file, provider unavailable, ground truth over the injection cap → `UNKNOWN` (cannot judge); a substantive negative judgment → `FAIL`; each logged at WARNING or above. No templates yet — this slice provides the enforcement the templates plug into.
   - **Value:** Architectural enablement — turns a parsed score into a gateable, self-describing verdict with conservative, observable failure handling; the contract every judge template depends on.
   - **Success Criteria:**
     - A score is required and 0–100-validated at the judge use; absent or out-of-range produces `UNKNOWN`, not a pass.
     - The verdict is computed by thresholding the score, one-directionally; no independent model verdict is consulted.
     - Thresholds resolve from template config, overridable per step; defaults are conservative.
     - The result carries a provenance discriminator distinguishing judge-derived from review-produced verdicts.
     - Each enumerated failure mode yields a non-passing verdict and an observable WARNING+ log line, asserted by at least one test per mode.
   - **Dependencies:** [300].
   - **Interfaces:** Provides verdict-derivation, score validation, threshold resolution (template + step override), and the provenance field; consumes the `score` field from 300; produces verdicts the existing `--step-done --verdict` checkpoint machinery already consumes.
   - **Risk Level:** Medium (threshold locus and provenance are architectural commitments with config surface).
   - **Relative Effort:** 3/5

3. [ ] **(302) Design-Phase Judge Templates** — One or more judge system-prompt templates for the existing `review` action that emit **score + findings and not a verdict** (the action derives the verdict via 301). A step selects a judge by naming its template (e.g. a `review` step with `template: judge.slice-vs-arch`) — no new action, no new step type, no new selector. Prioritize the **design-phase gates** where human-in-loop is heaviest: slice-design vs. arch, tasks vs. slice. Each template uses a structured-output constraint for the score field and a **score-with-rationale** prompt shape (require the model to justify the number) to reduce anchoring. Ground truth is supplied as reviews already supply it — natively for file-reading providers, by front-loaded injection for the rest.
   - **Value:** User/developer value — the first working judges; a pipeline can score a design artifact against its in-repo ground truth and receive a gateable verdict.
   - **Success Criteria:**
     - At least the slice-vs-arch and tasks-vs-slice judge templates exist and run via the existing `review` action with no engine changes.
     - A judge template emits score + findings and no verdict; the derived verdict comes from 301.
     - Templates carry conservative default thresholds; a step can override them.
     - The score-with-rationale shape is enforced by the template's structured output.
     - A judge run against a real artifact-plus-ground-truth pair produces a score, derived verdict, and findings, persisted like any review output.
   - **Dependencies:** [301].
   - **Interfaces:** Provides named judge templates; consumes the `review` action, `run_review_with_profile`, the enforcement layer (301), and the existing template-selection mechanism.
   - **Risk Level:** Low (templates are data; the connective work is authoring, not engine change).
   - **Relative Effort:** 2/5

4. [ ] **(303) Judge-Gated Cycle Conventions** — Define and document how the existing `each` / `loop` / `commit` steps compose with a judge to express the review→fix→re-review cycle as an unattended pipeline: a judge scores an artifact, the score gates automatically where it clears the threshold, the cycle repeats on `CONCERNS`/`FAIL` up to a bound, and it escalates to a human where the score cannot clear (weak ground truth → advisory-only threshold). No new constructs — this slice is the conventions and the worked pipeline that proves the existing machinery drives repeated one-shot judges.
   - **Value:** User value — the human-driven review→fix→re-review loop becomes a pipeline that runs without a human at each gate; the initiative's headline capability.
   - **Success Criteria:**
     - A documented convention shows `each`/`loop`/`commit` + a judge expressing the review→fix→re-review cycle.
     - A worked pipeline runs the cycle unattended: auto-advancing where the score clears the threshold, escalating where it does not.
     - The cycle is bounded (no unbounded looping) and the escalation path is observable.
     - No new step type or engine change is introduced.
   - **Dependencies:** [302].
   - **Interfaces:** Provides the judge-gated-cycle convention and reference pipeline; consumes `each`/`loop`/`commit`, the judge templates (302), and the enforcement/threshold layer (301).
   - **Risk Level:** Low (composition of existing constructs; risk is in getting bound/escalation conventions right, not new code).
   - **Relative Effort:** 2/5

---

## Integration Work

5. [ ] **(304) Gate Composition** — Resolve and implement how a judge result and a standard review result compose into a single checkpoint gate. **Prefer (a): compose upstream of the checkpoint** — reduce judge + review into one verdict before the checkpoint sees it (additive, within 300's scope). The checkpoint machinery is single-verdict-per-step today (`_find_review_verdict` returns the first non-`None` verdict), so any composition needing *two* verdicts considered together would require **(b): extending the checkpoint to accept multiple verdicts — a 140 change, explicitly out of 300's additive scope**. This slice must pick (a) where possible and escalate (b) as a coordinated 140 dependency if (a) proves insufficient, rather than silently absorbing the change.
   - **Value:** Architectural enablement — closes the cross-cutting question of combining judge and review judgments at a gate; completes the initiative's gating story.
   - **Success Criteria:**
     - A judge result and a review result compose into one checkpoint gate via an upstream reduction (option a), with the reduction rule documented.
     - The existing single-verdict-per-step checkpoint behavior is unchanged for non-composed steps.
     - If option (a) is found insufficient for a required case, the need for option (b) is raised as an explicit, coordinated 140 dependency — not implemented silently inside 300.
     - Composition behavior is covered by tests including the escalation-to-140 boundary case.
   - **Dependencies:** [302] (judges exist); coordinates with [140] only if option (b) is required.
   - **Interfaces:** Provides the upstream judge+review reduction; consumes the checkpoint machinery (`_find_review_verdict`) and judge/review results.
   - **Risk Level:** Medium (the one place the additive principle has a real edge; carries a conditional 140 dependency).
   - **Relative Effort:** 3/5

---

## Notes

**Key decisions made during planning:**
- The keystone (300) is ordered first and done alone, per the architecture. It is the only Medium-risk cross-cutting model change and everything composes on it.
- The judge **enforcement layer** (301) is split out from the judge **templates** (302). The architecture's two-layer parser/action split (parser lenient/optional; required-ness, validation, thresholding at the judge use) makes the enforcement independently testable and a prerequisite for any gateable template. Combining them would bury the architectural commitment inside template authoring.
- Implementation order follows the dependency chain and the risk/enablement guidance: foundation first, then the enforcement contract, then templates, then the cycle that consumes them, with gate composition last as cross-cutting integration.

**Alternative approaches considered:**
- *Four slices as the architecture sketches them* (templates and enforcement merged): rejected to keep the two-layer split visible and independently verifiable.
- *Building a judge template before the enforcement layer:* rejected — a template that emits a score is not gateable until validation/thresholding/provenance exist; ordering enforcement first keeps every slice in a working, demonstrable state.

**Open questions for later phases:**
- Exact field names/enum for the provenance discriminator (301, slice-design detail).
- Precise threshold band values and config keys (301/302, slice-design + config).
- Storage representation for the queryable score — column vs. indexed field (300, slice-design detail).
- Which design-phase judge templates beyond slice-vs-arch and tasks-vs-slice to author first (302).

---

## Future Work
Items out of scope for the current plan but worth tracking. Add entries here as they arise during slice design, task breakdown, or implementation.

1. [ ] **(1) Multi-Sample Judging** — Permit (not require) running a judge N times and reducing via median through the existing `fan_out`/fan-in machinery, as a config option to bound the damage of run-to-run score variance. The architecture names this as a cheap in-engine mitigation, not a default; deferred so the core judging path lands first. Dependencies: [301, 302]. Effort: 2/5.
2. [ ] **(2) On-Demand Ground-Truth Fetching** — If a future case (e.g. a large code review) genuinely exceeds the injection cap and needs on-demand file fetching, scope it separately. Explicitly **not** a turn-loop inside the judge (judges stay one-shot); a different mechanism entirely. Dependencies: [302]. Effort: 3/5.
3. [ ] **(3) Checkpoint Multi-Verdict Support (140)** — If gate composition (304) finds upstream reduction insufficient, extend the checkpoint machinery to accept multiple verdicts. This is a **140 change**, surfaced here so it is tracked as a coordinated dependency rather than discovered mid-slice. Dependencies: [140, 304]. Effort: 3/5.
