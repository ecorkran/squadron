---
docType: slice-plan
parent: 300-arch.eval-actions-llm-as-judge-scoring.md
project: squadron
dateCreated: 20260604
dateUpdated: 20260802
status: complete
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

2. [x] **(301) Judge Enforcement Layer** — The second half of the two-layer split. At the judge **use** (not the parser): require the score, range-validate it to 0–100, and derive the verdict by thresholding the score (at/above a pass floor → `PASS`, middle band → `CONCERNS`, below a floor → `FAIL`). Thresholds live at **template-level config with step-level override**, defaults deliberately conservative (gate toward escalation when uncertain). Add the **provenance** field to the result (judge-derived vs. review-produced) so a result carrying both score and verdict is self-describing. Map the enumerated failure modes to non-passing verdicts: absent/out-of-range score, unparseable response, missing/unreadable ground-truth file, provider unavailable, ground truth over the injection cap → `UNKNOWN` (cannot judge); a substantive negative judgment → `FAIL`; each logged at WARNING or above. No templates yet — this slice provides the enforcement the templates plug into.
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

3. [x] **(302) Design-Phase Judge Templates** — One or more judge system-prompt templates for the existing `review` action that emit **score + findings and not a verdict** (the action derives the verdict via 301). A step selects a judge by naming its template (e.g. a `review` step with `template: judge.slice-vs-arch`) — no new action, no new step type, no new selector. Prioritize the **design-phase gates** where human-in-loop is heaviest: slice-design vs. arch, tasks vs. slice. Each template uses a structured-output constraint for the score field and a **score-with-rationale** prompt shape (require the model to justify the number) to reduce anchoring. Ground truth is supplied as reviews already supply it — natively for file-reading providers, by front-loaded injection for the rest.
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

4. [x] **(303) Judge-Gated Cycle Conventions** — Define and document how the existing `each` / `loop` / `commit` steps compose with a judge to express the review→fix→re-review cycle as an unattended pipeline: a judge scores an artifact, the score gates automatically where it clears the threshold, the cycle repeats on `CONCERNS`/`FAIL` up to a bound, and it escalates to a human where the score cannot clear (weak ground truth → advisory-only threshold). No new constructs — this slice is the conventions and the worked pipeline that proves the existing machinery drives repeated one-shot judges.
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

5. [x] **(304) Gate Composition** — Resolve and implement how a judge result and a standard review result compose into a single checkpoint gate. **Prefer (a): compose upstream of the checkpoint** — reduce judge + review into one verdict before the checkpoint sees it (additive, within 300's scope). The checkpoint machinery is single-verdict-per-step today (`_find_review_verdict` returns the first non-`None` verdict), so any composition needing *two* verdicts considered together would require **(b): extending the checkpoint to accept multiple verdicts — a 140 change, explicitly out of 300's additive scope**. This slice must pick (a) where possible and escalate (b) as a coordinated 140 dependency if (a) proves insufficient, rather than silently absorbing the change.
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

6. [x] **(305) Findings-Addressed Gate Policy** — First use of the `VALID_GATE_POLICIES` extension seam 304 declared: a second gate policy, `findings-addressed`, that answers "were the prior round's findings actually addressed?" inside a loop. Moved here from the maintenance initiative (was slice 912, entry 10 in `900-slices`) on its own design review's F001 — it is a capability, and this initiative owns the seam. Deterministic screens run first (round 1 → annotated `PASS`; byte-identical round via `committed: False` → `FAIL`, zero tokens; exact-match recurring findings → `unaddressed`); a judge — the LLM-as-a-judge *role*, consulted inside gate execution, never a node type — settles only the residue, emitting per-prior-finding statuses (`addressed`/`unaddressed`/`moved`+successor/`disputed`) from which the addressed-leg verdict is derived by rule (301's derived-not-declared discipline), then reduced with the clean-eyes review leg via 304's `reduce_verdicts`. The clean-eyes review stays structurally blind to prior rounds (anti-anchoring as a typing rule); evidence persists as a `gate-evidence` artifact outside the `*-review.*` namespace so metrology's judge discovery never ingests it. Also refines 910 Part B's loop guard to count *unconsumed* verdicts, making dispatch + review + gate a valid loop body. Consumes 911's per-iteration commits and `revision_number:` as evidence, and 910's accumulated per-iteration `prior_outputs`.
   - **Slice design:** `user/slices/305-slice.findings-addressed-gate.md` (design complete 20260802; slice review resolved same day)
   - **Tasks:** `user/tasks/305-tasks.findings-addressed-gate-1.md` (Parts A–C) and `-2.md` (Parts D–G), breakdown complete 20260802. Breakdown surfaced two pre-existing loop-executor defects that 305 is the first consumer to expose — `step_outputs` is never populated inside a loop body (so *any* gate in a loop, including 304's `most-severe`, resolves nothing and emits `UNKNOWN`), and `prior_outputs` means "prior round" or "current round" depending on a step's position in the body — plus one ordering fact the design had backwards: round N has no commit SHA at gate time. Part A repairs the executor additively; the byte-identical screen diffs the working tree against `HEAD` rather than chasing a round-N SHA.
   - **Implemented:** 20260802, branch `305-slice.findings-addressed-gate` — seven commits, one per part. Both loop-executor defects are fixed (Part A repairs a gate inside a loop for *every* policy, `most-severe` included). The policy ships as a package under `pipeline/actions/findings_addressed/`; bundled template `judge.findings-addressed` (deliberately not an `is_judge` template); bundled pipeline `findings-addressed-cycle`. The byte-identical screen diffs the working tree against `HEAD`; the recordable audit pair is the prior round's SHA + `revision_number` — round N's own SHA is not recordable, since the evidence artifact predates the commit containing it.
   - **Dependencies:** [911, 910, 304] (911/910 are maintenance-initiative slices — cross-initiative dependency, normal)
   - **Risk Level:** Medium (judge status quality on the genuinely unmeasurable residue; mitigated by fail-closed derivation and contradiction checks)
   - **Relative Effort:** 3/5

7. [ ] **(306) Review Resolution — Recording That Findings Were Addressed** — [Issue #51](https://github.com/ecorkran/squadron/issues/51). A FAIL review's findings get addressed, the fix lands, and the artifact still reads `verdict: FAIL` — so downstream gating stays closed on a verdict no longer true of the code, with no mechanism to say so. Belongs here because 305 already built the decision procedure; this slice is about making it reachable and recordable outside a pipeline loop.

   **The constraint that shapes the whole slice.** Agents were barred from editing `verdict:` because they did it too readily and invented status values when they did. That call stands: a verdict is a fact about a review run at a moment, and mutating it makes the artifact unfalsifiable — "reviewed clean" becomes indistinguishable from "reviewed FAIL, then edited." The missing thing is not a writable verdict; it is a *second assertion* — these findings have been addressed — which is a different claim from "this review passed" and has nowhere to live. Any design where one word an agent can write unprompted unblocks a gate has rebuilt the original problem under a new name.

   **What exists.** `status:` is a hardcoded literal (`persistence.py:143` always writes `status: complete`, meaning "the review ran"), not a state machine. Nothing in squadron re-reads a persisted review's verdict — the file's consumers are Context Forge's `workflow_check` and humans, so this is a **cross-tool frontmatter contract change** and must be coordinated, not decided unilaterally. Today's convention is a hand-written `## Resolution (YYYYMMDD)` prose section (910, 305): auditable, invisible to tooling.

   **Verified 20260802 — what 305 actually writes, and why cf cannot see it.** The gate emits exactly one artifact: `project-documents/user/reviews/{index}-gate.{policy}.{name}-r{revision}.md`, `docType: gate-evidence`, carrying `verdict` / `addressedVerdict` / `reviewVerdict` / `decidingScreen` / `priorRoundSha` / `revision_number` / `judgeModel` / `judgeTemplate` and a `findingStatuses:` list of `{id, status, screen, successor?, note?}` — the same record also on `ActionResult.metadata`. It **never touches the review file**, so `verdict: FAIL` stands untouched; it writes nothing Context Forge reads; and it is reachable only from inside a loop (requires `review_from` naming an earlier body step, a per-round commit source, and `slice` in params — no slice index means a WARNING and no file). So the machine-readable resolution record already exists with per-finding dispositions. The two gaps are **reachability** outside a loop and **a consumer** — cf gates purely on the review artifact's frontmatter verdict against `workflow.review_threshold` (default `concerns`, per-type override at `workflow.review_gates.{type}.threshold`, `review_unknown_as: fail`, floor at `review_gate_effective_date`), and its project schema has no resolution or override field at all.

   **Constraint discovered the same day: the review artifact is not a safe place to record resolution.** `save_review_result` (`persistence.py:303`) is a bare `path.write_text` — no revision suffix on the CLI path, no existence check, no warning. Re-running `sq review code <N>` silently overwrites the prior artifact, destroying any hand-written `## Resolution` section in it. That argues strongly for resolution living in a **separate artifact in 305's `gate-evidence` shape** rather than as a field on the review, and it means "just re-review to get a fresh verdict" costs the resolution record today.

   **Open contracts, to resolve in design.** (a) Where resolution lives — a frontmatter field on the review, a separate artifact in the shape of 305's `gate-evidence`, or a verdict transition with an audit trail; the artifact form is the one that composes with 305. (b) Who may write it, and against what evidence — 305's derived-not-declared discipline applies, but the interactive path needs something cheaper than a judge call or it will not be used; 305's Screens 1 and 2 (a byte-identical round addressed nothing; a finding re-found at the same location was not addressed) are free and may be enough. (c) What the gate reads — original verdict, resolution state, or both. (d) Lifecycle — whether a later clean review supersedes an unresolved FAIL, and what happens when a re-review finds the same thing again.

   **Explicitly out of scope:** restoring an agent's ability to edit `verdict:`. The original verdict stays as written, whatever else is added.

   - **Slice design:** `user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md` (Phase 4 complete 20260802). Shape settled there: `reviewedSha` stamped at review authoring; `sq review resolve <index>` derives per-finding dispositions via 305's screens + judge (transport core extracted context-free) and writes a versioned `{index}-resolution.{type}.{name}-r{n}.md` (`docType: review-resolution`, top-level field `resolution:`, deliberately not `verdict:`); review file never touched; `save_review_file` gains an archive-on-overwrite guard; cf consumption offered as a contract, not assumed.
   - **Dependencies:** [305 (the derivation and the evidence-artifact shape), 300 frontmatter contract]. Coordination dependency on Context Forge for anything `workflow_check` reads.
   - **Risk Level:** Medium — the risk is not implementation, it is designing a field that agents will not casually write
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
4. [ ] **(4) Per-Call Provider Timeout (140)** — Bound a single action's provider call by wall-clock and map a `TimeoutError` to a review `UNKNOWN`, so an unattended judge cycle whose provider *hangs* (distinct from "provider down") escalates via the existing iterate/checkpoint flow instead of stalling indefinitely. `loop.max` bounds iteration count, not wall-clock. Surfaced by slice 303 design review; a **140 action/client-layer change** benefiting every action, not judge-specific, so not authored inside 300. Dependencies: [140]. Effort: 2/5.
5. [ ] **(5) Per-Iteration Commit in a Loop Body (140)** — `commit` is a registered *action* but not a registered *step type*, so it cannot appear as a bare loop-body step (`- commit:` fails validation with `Unknown step type`); it is only auto-emitted inside a phase step. A judge cycle that wants to persist each fix individually therefore cannot today. Add either a standalone `commit` step type or a way to reuse the phase-step commit action inside a loop body. Surfaced by slice 303 (the judge cycle's body is `[fix, judge]` only as a result). A **140 step-registry change**, out of 300's scope. Dependencies: [140]. Effort: 2/5.
6. [ ] **(6) Generic Judge-Over-Results Gate** — A gate whose judge reads **author-declared step results** (`results_from: [step-a, step-b, ...]`) and answers an **author-written question** — the inversion of slice 305, where the policy fixes both in code. Known consumers: fan-in adjudication (N `fan_out` attempts, judge picks the winner — the model-backed sibling of item 1's deterministic median), and a did-the-dispatch-do-the-task check reading a dispatch summary plus diff. Three contracts must be designed, each free in 305 precisely because its question is closed: (a) a **serialization contract** for arbitrary `ActionResult.outputs` into judge context (305 formats known shapes — findings lists, diffs); (b) **derived-not-declared under author-supplied rubrics** — a generalization of `enforce_judge` where the author defines the output schema and derivation rule yet the judge still never asserts the conclusion; (c) a **measurability boundary**: a generic node cannot know which parts of an arbitrary question are deterministic, so either authors declare screens or the pay-a-model-for-measurable-things responsibility (slice 305, design principle 2) shifts explicitly to the pipeline author — it must not shift silently. **Promotion criterion:** extract the abstraction from working policy instances, not ahead of them — promote only after at least one more concrete gate policy beyond `findings-addressed` exists to generalize from (per 305's Technical Scope exclusion, where this instrument is contrasted in full). Dependencies: [304, 305]. Effort: 4/5. Risk: Medium-High (open rubric contract is the hard part).
