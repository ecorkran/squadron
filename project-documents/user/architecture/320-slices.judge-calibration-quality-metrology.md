---
docType: slice-plan
parent: 320-arch.judge-calibration-quality-metrology.md
project: squadron
dateCreated: 20260718
dateUpdated: 20260726
status: complete
---

# Slice Plan: Judge Calibration & Quality Metrology

## Parent Document
`320-arch.judge-calibration-quality-metrology.md` — High-Level Design: Judge Calibration & Quality Metrology

**Picking this up cold?** See [`320-reference.judge-calibration-quality-metrology.md`](320-reference.judge-calibration-quality-metrology.md) for a current-state index and glossary before reading further.

## Planning Context
Architecture-level. The parent architecture settles the design across one review round (CONCERNS, all findings addressed). This plan breaks it into vertical slices.

The architecture describes **two oracles on a shared metrology spine** (queryable persistence + trend reporting): a human-sampled oracle for judge quality, and a tech-debt-audit oracle for code quality. The spine is the keystone — *every other slice consumes the store* — so the data layer plus its capture surface is ordered first and done alone, exactly as the architecture instructs ("The data layer is the keystone and comes first").

The architecture's "Anticipated Slices" section sketches five slices. This plan keeps that count and boundary set — the five map cleanly onto the two headline analyses plus the calibration feedback loop, and the architecture already resolved the load-bearing decisions (store locality, project identity, version-keying tension, down-only pre-emption flow, variance-before-baseline ordering) so no slice needs to reopen them. Every slice is additive: it reads and annotates 300's persisted record and never modifies the judging path.

Two ordering constraints from the architecture are honored explicitly:
- **Variance before baseline before intervention** (*Variance, then baseline, then intervention*): the audit's own run-to-run noise floor is measured inside the baseline harness slice, and the pre-emption prompt ships only after both variance and baseline exist. This forces the audit oracle into two slices, not one, with the pre-emption slice last.
- **The keystone is done alone.** No reporting rides along with the data layer; reporting is a separate slice so the storage/join/ergonomics decisions are de-risked in isolation.

---

## Foundation Work

1. [x] **(320) Metrology Data Layer & Sample Capture (keystone)** — The durable, user-level/central home for oracle verdicts, plus the low-friction human-sample capture surface. Two things land together because the capture surface is meaningless without the store and the store cannot be verified without a writer: (a) a queryable, joinable store that keys on a **stable, explicit project identity** (repo-derived — remote URL or recorded project id, never a mutable filesystem path), lives **user-level/central** (one store aggregating across the projects a user runs), and does **not** depend on 280; (b) a **blind, inline** capture surface (CLI at minimum, honoring interface parity) that presents an artifact and its ground truth for an independent human verdict **with the judge's output withheld until after** the human commits, then records that verdict against the specific persisted judge result being checked, carrying the judge-configuration identity. The capture surface is **pull-based, budgeted, and never blocking**: designated samples queue for the operator to drain when convenient, no pipeline/gate/dispatch waits on a sample verdict, skipping an offered sample is free, and the offered-sample volume is governed by a **configured budget** (rate or ceiling), not by pipeline volume. Blindness attaches **only to designated calibration samples** — the normal escalated-gate review flow stays judge-assisted and is never converted into a blind labeling task. No reporting, no agreement math, no threshold feedback — this slice de-risks storage, join, and capture ergonomics in isolation.
   - **Value:** Architectural enablement — the metrology spine every other slice consumes; human agreement data begins accumulating with a verifiable, unambiguous link to the judge result it grades.
   - **Success Criteria:**
     - A human sample verdict persists keyed to (a) the specific 300 judge result it grades and (b) the judge configuration identity, and can be queried and joined back to that result.
     - The store keys on a stable, explicit project identifier that is invariant across runs and machines (not a filesystem path); a cross-project query returns samples from more than one project.
     - The store is user-level/central and stands alone — it neither reads from nor writes to 280, and its absence for a fresh user yields an empty store, not an error in the judging path.
     - The capture surface is blind: the judge's score/verdict/findings are not shown before the human commits their verdict (asserted by a test on the capture flow), and reveal (if offered) is post-commit only.
     - Blindness is scoped to designated calibration samples: the escalated-gate review flow is unchanged (judge output remains visible there), and an escalated-gate verdict is never recorded as blind agreement data.
     - Capture never blocks execution: no pipeline, gate, or dispatch waits on a human sample verdict; skipping an offered sample succeeds cleanly and records nothing. Offered-sample volume respects a configured budget.
     - Capture attaches unambiguously to one persisted judge result; a mis-target or absent target fails explicitly rather than recording against the wrong result or a placeholder.
     - The judging path (300) is unmodified: the full existing test suite passes, and a judge run with no metrology store present behaves exactly as before.
   - **Dependencies:** [100, 140, 300] (persistence, executor, the persisted judge result being graded).
   - **Interfaces:** Provides the metrology store (write + queryable/joinable read, cross-project) and the human-sample capture command; consumes 300's persisted `ReviewResult` (its `template_name` / `model`, and the reserved `criteria` map where read-side population applies). Provides the project-identity derivation every later slice keys on.
   - **Risk Level:** High (the keystone: store locality, stable identity, blind-capture ergonomics, and the join to 300's per-run results are all first-decided here; every downstream slice inherits these choices).
   - **Relative Effort:** 4/5

---

## Feature Slices (in implementation order)

2. [x] **(321) Agreement & Dispersion Reporting** — The human oracle's headline analysis over the accumulated sample: **judge-vs-human agreement** and **judge-vs-judge dispersion**, always computed **per artifact level** (tasks-vs-slice, slice-design-vs-arch, arch-vs-concept) and per judge configuration, never as one blended global number. Every reported figure **carries its sample size** and refuses to imply precision it lacks (honest statistics at small n). Trend over time is reported on the same grain. Dispersion draws its repeated measurements from **300's multi-sample judging option** (300 Future Work 1) and accepts dispersion data **opportunistically** (when multi-sample ran anyway) as well as from dedicated calibration runs — it does **not** introduce a 180 `fan_out` dependency. Dispersion and trend are the **human-free continuous monitors** in the division of labor the architecture fixes: they maintain a graduated judge's standing between scarce human samples, and rising dispersion flags where the human sample budget should be spent. Version comparability is enforced here: reports must not blend measurements across incompatible judge configurations (see the version-keying decision in slice 322's write-path coordination / this slice's content-hash fallback).
   - **Value:** Developer/operator value — the trust gradient 300 asserts becomes a measured, per-level quantity, and systematic cross-model bias ("X overreaches, Y rubber-stamps") becomes visible.
   - **Success Criteria:**
     - Agreement and dispersion are reported per artifact level and per judge configuration; no report path emits a single blended "judge accuracy" number.
     - Every reported figure carries its sample size (n); a report at small n does not overstate confidence, and a minimum-evidence floor is representable (consumed by slice 323).
     - Dispersion is computed from repeated judgments sourced via 300's multi-sample option; opportunistic multi-sample data is ingested without a dedicated run, and no 180 dependency is introduced.
     - Reports refuse to pool measurements across incompatible judge configurations (version/hash-keyed), excluding or flagging un-version-keyable historical data rather than silently blending it.
     - Trend over time is reported on the same per-level/per-configuration grain.
   - **Dependencies:** [320]; consumes 300's multi-sample judging option for dispersion inputs.
   - **Interfaces:** Provides agreement/dispersion/trend reports (per artifact level, per judge configuration, sample-size-carrying); consumes the metrology store (320) and the judge-configuration identity persisted there.
   - **Store-backend revisit (decision point inherited from 320):** The keystone (320) deliberately ships the store as flat per-record JSON with glob-and-filter querying (the `StateManager` precedent), *not* a database — the keystone must not introduce squadron's first DB for a write-one/read-filtered workload that doesn't need one. **321 is the first slice whose workload is aggregation** — group-by artifact level, group-by judge configuration, trend over time, sample counts — which is exactly what a query engine is good at. So the SQLite-vs-flat-file decision is **reconsidered here**: if reporting queries strain glob-and-filter over a growing cross-project sample, adopt stdlib `sqlite3` (zero new dependency) in this slice. The migration is contained, not a rewrite: 320's records are versioned Pydantic (`schema_version` + `record_type` discriminator), so flat-JSON → SQLite is a schema-versioned data move. Default remains flat-file unless the aggregation workload demonstrably needs otherwise — resist the DB until the query surface actually strains.
   - **Risk Level:** Medium (small-n statistics and the version-comparability boundary are the substance; no engine change).
   - **Relative Effort:** 3/5

3. [x] **(322) Calibration-to-Threshold Feedback** *(complete — see `user/slices/322-slice.calibration-to-threshold-feedback.md`)* — The documented, **evidence-floored** path from agreement/dispersion reports to 300's template-level / step-override threshold config: how a judge **graduates** from advisory toward auto-gate at an artifact level. Calibration **informs** config; it never silently rewrites it (no automatic threshold mutation) — loosening a gate is an operator decision made on reported evidence, below a **minimum-evidence floor** that refuses to recommend loosening. Two architectural constraints ship as first-class behavior, not caveats: (a) **graduation is not a one-way door** — moving a judge to auto-gate installs a **continued forced random-sampling rate** on auto-gated results so false-PASS stays observable and within-configuration drift keeps being detected; (b) the **calibration is keyed by (template, model)** but 300's threshold config has a template/step dimension and no model dimension, so the recommendation resolves to the operator picking model+threshold **together at config time**, and a step whose model is drawn at runtime cannot vary its threshold — this slice inherits that limit rather than solving it. This slice also **resolves the version-keying tension**: it either coordinates the **preferred 300 write-path change** (add a template version/content-hash to the judge result at its write site — a dependency-flagged 300 change, like the checkpoint multi-verdict case) or ships the **content-hash-at-capture fallback**; whichever ships, historical/un-keyable data is flagged, not pooled.
   - **Value:** Operator value — closes the loop: the escalate-vs-auto-gate decision 300 made configurable becomes evidence-driven, with graduation kept honest by residual sampling.
   - **Success Criteria:**
     - A documented path takes an agreement report at an artifact level and yields a threshold-config recommendation for 300's template/step config; the recommendation is advisory output, and nothing mutates the threshold config automatically.
     - The recommendation refuses to suggest loosening below a defined minimum-evidence floor (sample size / agreement strength), and states the floor it applied.
     - Graduating a judge to auto-gate installs a continued forced random-sampling rate on auto-gated results; a graduated judge still produces sampled human-verdict data (asserted by a test), so agreement does not freeze.
     - The (template, model)-keyed calibration is surfaced as a config-time model+threshold pairing; the runtime-drawn-model limitation is documented where the recommendation is produced, not silently ignored.
     - Version identity ships one of the two named ways: the coordinated 300 write-path version/hash field (raised as an explicit 300 dependency) **or** the content-hash-at-capture fallback; either way, un-version-keyable historical data is excluded or flagged in any recommendation input.
   - **Dependencies:** [321]; coordinates with [300] if the preferred write-path version field is chosen (surface as an explicit dependency, not a silent absorption).
   - **Interfaces:** Provides the calibration→threshold recommendation path, the residual-sampling policy on graduated judges, and the version-identity key; consumes agreement reports (321), the metrology store (320), and 300's template/step threshold config surface (read for recommendation targets; never written automatically).
   - **Risk Level:** Medium (the (template,model)↔(template,step) mismatch, the graduation-sampling guarantee, and the conditional 300 write-path coordination are the substance).
   - **Relative Effort:** 3/5

4. [x] **(323) Tech-Debt-Audit Baseline Harness** *(complete — see `user/slices/323-slice.tech-debt-audit-baseline-harness.md`)* — The code-quality oracle's data slice: run the **tech-debt-audit** skill (340 analysis pack) across squadron-managed projects, **normalize** its prose-shaped, non-deterministic output into a persistable, comparable form (category, location, severity) without overstating precision, and persist findings to the metrology spine as a **cross-project baseline** keyed on the stable project identity. Critically, this slice **measures the audit's own run-to-run noise floor first** (repeated audits on unchanged code) and persists it alongside the baseline, because *Variance, then baseline, then intervention* requires the floor to exist before any delta is credible. Reports the cross-project baseline at the **project/issue-class grain** (the audit oracle has no agreement dimension — nothing compares to a human) with the noise floor attached.
   - **Value:** Developer/operator value — "squadron produces good code" gains a measured, cross-project baseline; the noise floor makes any later delta interpretable rather than anecdotal.
   - **Success Criteria:**
     - The tech-debt-audit skill runs across more than one squadron-managed project and its findings normalize into persisted records (category, location, severity) keyed on the stable project identity from slice 320.
     - The audit's run-to-run variance is measured (repeated audits on unchanged code) and persisted as an explicit noise floor alongside the baseline; the baseline report presents the floor.
     - The baseline report is at the project/issue-class grain and carries no agreement dimension (it does not fabricate a human-comparison figure).
     - Normalization does not overclaim precision the prose analysis lacks; findings that cannot be normalized are represented honestly (flagged/retained), not dropped silently.
     - The harness reuses the metrology spine (persistence + trend) rather than re-inventing storage.
   - **Dependencies:** [320], [340] (the tech-debt-audit skill / analysis pack).
   - **Interfaces:** Provides the audit-run harness, the finding-normalization, the persisted cross-project baseline, and the measured noise floor; consumes the tech-debt-audit skill (340) and the metrology spine (320).
   - **Risk Level:** Medium (normalizing non-deterministic prose and measuring its variance honestly is the substance; running the skill is orchestration, not new engine).
   - **Relative Effort:** 3/5

---

## Integration Work

5. [x] **(324) Pre-Emption Prompt & Delta Measurement** *(complete — see `user/slices/324-slice.pre-emption-prompt-delta-measurement.md`)* — The code-quality oracle's first measurable customer: a dispatch-side **prompt-chaining pre-emption prompt** that front-loads avoidance of the **issue classes the baseline actually contains**, plus **before/after reporting** of audit-findings-per-project against the baseline **and its measured noise floor**. The pre-emption content is a **generated static prompt fragment** regenerated from the baseline and flowing **down** into dispatch config — dispatch **never** queries the metrology store at runtime (that would invert the 140→320 dependency and add a runtime failure mode). The delta is reported as an **observational before/after against the noise floor**, presented as a **credible directional signal, not causal proof** — a delta smaller than the floor is reported as indistinguishable from noise, and overclaiming at "a handful of projects" is explicitly avoided. This slice ships **only after** both the variance and the baseline exist (slice 323), per *Variance, then baseline, then intervention*.
   - **Value:** Operator value — proves the metrology can detect an intervention's effect, not just accumulate numbers; the initiative's proof-of-value that measurement closes a loop on code quality.
   - **Success Criteria:**
     - A pre-emption prompt fragment is generated from the persisted baseline's actual issue classes and reaches dispatch config as static prompt material; dispatch does not query the metrology store at runtime (the down-only flow is verified — the store's absence does not add a dispatch failure mode).
     - A before/after report compares audit-findings-per-project against the baseline and reports the delta **relative to the measured noise floor**, not in isolation.
     - A delta below the noise floor is reported as indistinguishable from noise; the report frames the result as an observational directional signal, not causal proof.
     - Regeneration of the fragment from an updated baseline is a defined step (cadence/format is slice-design detail); a stale fragment does not silently diverge from the baseline without the report showing it.
   - **Dependencies:** [323] (baseline + noise floor must exist first); [140] (the dispatch-facing config surface the fragment flows into).
   - **Interfaces:** Provides the generated pre-emption fragment (down-only into dispatch config) and the before/after-vs-floor delta report; consumes the persisted baseline and noise floor (323) and the dispatch prompt-config surface (140, write-target for the static fragment — not a runtime query).
   - **Risk Level:** Medium (honest attribution against a noise floor at small project-n is the substance; the down-only data-flow discipline is a firm constraint, not a mechanism choice).
   - **Relative Effort:** 3/5

---

## Notes

**Key decisions made during planning:**
- **The keystone (320) is ordered first and done alone**, per the architecture. It is the only High-risk slice and every other slice joins against its store, keys on its project identity, and depends on its blind-capture guarantee. Bundling any reporting into it would defeat the isolation the architecture asks for.
- **Two oracles, one spine, two analysis paths.** The five slices split as: spine + human capture (320) → human-oracle analysis (321) → human-oracle feedback loop (322); then audit-oracle data + variance (323) → audit-oracle intervention (324). The shared surface is persistence + trend (in 320, reused by 323), *not* one report path — the human oracle reports agreement at the artifact-level/judge-configuration grain, the audit oracle reports count-delta at the project/issue-class grain, exactly as the architecture's Envisioned State fixes.
- **Variance forces the audit oracle into two slices.** *Variance, then baseline, then intervention* means the noise floor is measured inside the baseline harness (323) and the pre-emption prompt (324) ships only after. Collapsing them into one slice would let a delta be reported before its floor exists — the exact failure the principle forbids.
- **Blind capture is scoped; sampling is budgeted and non-blocking.** The reviewer at an escalated gate and the calibration sampler are different roles: escalated review stays judge-assisted (findings visible), blindness applies only to designated calibration samples, capture is a pull-based queue no execution path waits on, and human load is a configured budget. This keeps the human oracle compatible with increasingly autonomous operation (Amoeba direction) — slow evidence means slower graduation and an honest floor refusal, never more interruptions.
- **The version-keying tension is resolved in the slice that needs it (322), not the keystone.** The store (320) persists judge-configuration identity; *which* identity (coordinated 300 write-path field vs. content-hash fallback) is decided in 322 where the calibration recommendation actually depends on not blending incompatible configurations. 321 already enforces non-blending on whatever key is present.

**Alternative approaches considered:**
- *Merging the two audit slices (323+324) into one "code-quality oracle" slice:* rejected — it would violate variance-before-intervention and hide the noise-floor measurement inside an intervention slice, precisely the caveat-then-ignore failure the architecture calls out.
- *Building reporting (321) on top of the keystone in a single slice:* rejected — the architecture explicitly wants the storage/join/ergonomics decisions de-risked alone before any analysis rides on them.
- *Folding calibration-to-threshold (322) into agreement reporting (321):* rejected — the feedback loop carries distinct architectural commitments (graduation-sampling, the (template,model)↔(template,step) mismatch, the write-path version coordination) that are cleaner to verify against a settled report format than to co-develop with it.

**Open questions for later phases:**
- Storage representation and backend for the metrology store — schema, on-disk vs. embedded DB. **Resolved for 320: flat per-record JSON with glob-and-filter (the `StateManager` precedent), no DB.** Revisited in **321**, the first slice with an aggregation workload — adopt stdlib `sqlite3` there only if reporting queries strain glob-and-filter; migration is contained because 320's records are versioned Pydantic. (Architecture fixes locality + identity + queryable/joinable; representation stays flat-file until the query surface demonstrably needs otherwise.)
- Exact project-identity derivation (remote URL vs. recorded id) and its fallback when a repo has no remote (320, slice-design).
- Which results are *offered* for sampling — random, disagreement-triggered, escalation-triggered — and its statistical consequence on the agreement number (320/321, slice-design). Constraint fixed by the architecture: escalation-triggered offering may enqueue a sample but never blinds the escalation review itself, and the escalated verdict is anchored — inadmissible as blind agreement data.
- Sampling-budget representation (rate vs. ceiling, per-project vs. global) and its default value (320, slice-design + config).
- Whether a minor template revision inherits prior calibration or forces full re-calibration — churn must not perpetually reset n and starve graduation. **Resolved in 322's slice design:** no inherit/similarity policy; instead the comparability hash is narrowed to exclude the `judge:` threshold block, so a threshold edit (the loop's own output) preserves accumulated n while a prompt/model edit correctly re-keys. The dominant churn source was the calibration loop itself.
- Agreement/dispersion metric choice at small n (naive percent vs. chance-corrected) and the minimum-evidence floor values (321/322, slice-design + config).
- Whether the preferred 300 write-path version field or the content-hash fallback ships for version identity (322, resolved at its slice design; the former is a coordinated 300 dependency). **Resolved in 322's slice design: the content-hash-at-capture fallback ships** — 320 already computes it and 321 already enforces non-blending on it, so no 300 change is taken. Future Work #1 (the 300 write-path version field) therefore stays open, as does 321's Future Work #2 (judge-verdict persistence on the sample), which would ride with it.
- The residual forced-sampling rate on graduated judges (322, slice-design). **Resolved in 322's slice design:** a `metrology.residual_sample_rate` config key plus an offer-selection core drained through 320's existing pull-based capture — offers are generated at that rate; nothing blocks.
- Finding-normalization schema for the audit and how many repeated runs bound the noise floor (323, slice-design). **Resolved in 323's slice design:** normalization is a fenced YAML findings block emitted by the skill itself (the fork is edited rather than wrapped, so the harness and `/analysis:tech-debt-audit` consume one artifact), coerced to a closed 10-value `AuditCategory` vocabulary with `raw_category` retained and an `other` bucket so nothing is dropped. The floor is **3 runs** (`metrology.audit_variance_runs`), measured **per project** at a pinned commit — never one global number — across a 4-project contrast set (squadron, migratory, context-forge, migratory-viewer).
- Pre-emption fragment format and regeneration cadence (324, slice-design).

---

## Future Work
Items out of scope for the current plan but worth tracking. Add entries here as they arise during slice design, task breakdown, or implementation.

1. [ ] **(1) 300 Judge-Result Version/Hash Field** — If slice 322 selects the *preferred* resolution of the version-keying tension, add a template version or content-hash to the judge result at its 300 write site so future calibration data is reliably version-keyed (not only content-hashed at capture). A **300 write-path change**, surfaced here so it is tracked as a coordinated dependency rather than discovered mid-slice. Dependencies: [300, 322]. Effort: 2/5.
2. [ ] **(2) Metrology / Shared Artifact Store (280) Convergence** — If initiative 280 (Shared Agent Artifact Store) ships, evaluate consolidating the metrology store into it. Named by the architecture as a possible future convergence, explicitly **not** a dependency of this initiative. Dependencies: [280]. Effort: 3/5.
3. [ ] **(3) General Parallel Fan-Out for Dispersion (180)** — If a future need genuinely requires general parallel fan-out for dispersion beyond what 300's multi-sample option provides, that introduces a **180 `fan_out` dependency** to be surfaced and coordinated then. This initiative deliberately relies on 300's multi-sample and remains independent of 180; noted so the boundary is explicit, not assumed. Dependencies: [180, 321]. Effort: 3/5.
4. [ ] **(4) 300 Multi-Sample Judging (FW#1) — activates 321 same-config dispersion** — As of 321's slice design, **300 Future Work #1 (multi-sample judging) has not shipped**: there is one `ReviewResult` per review file, so no repeated *same-configuration* judgments exist. 321 therefore builds and unit-tests the same-config dispersion path but ships it **inert**, reporting cross-configuration dispersion only (distinct model/template on the same artifact — data the store already holds). **When 300 FW#1 ships** (a judge config run N times, reduced/persisted as repeated measurements), 321's same-config dispersion path becomes live with **no 321 code change** — only the data source appears. This is a **300-side** change (a 300-band slice implementing FW#1), surfaced here as a coordination point; it is explicitly **not** a 321 dependency and **not** a 180 `fan_out` dependency (that boundary stays closed). Trigger to build it: rising cross-config dispersion in 321 reports making same-config noise measurement a felt need. Dependencies: [300, 321]. Effort: 2/5.
