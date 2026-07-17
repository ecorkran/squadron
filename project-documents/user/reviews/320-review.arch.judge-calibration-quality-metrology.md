---
docType: review
layer: project
reviewType: arch
slice: judge-calibration-quality-metrology
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md
aiModel: claude-fable-5
status: complete
dateCreated: 20260717
dateUpdated: 20260717
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Judge-configuration identity cannot be satisfied read-side — the persisted record has no template version"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:79
  - id: F002
    severity: concern
    category: completeness
    summary: "The calibration loop destroys its own evidence source at graduation"
    location: unverified
  - id: F003
    severity: concern
    category: completeness
    summary: "Human-verdict anchoring is unaddressed and inflates the number that loosens gates"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md#technical-considerations
  - id: F004
    severity: concern
    category: dependencies
    summary: "`fan_out` is attributed to 140 but belongs to 180, which 320 claims independence from"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:81
  - id: F005
    severity: concern
    category: dependencies
    summary: "Frontmatter dependencies omit 340, on which two of five slices depend"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:8
  - id: F006
    severity: concern
    category: completeness
    summary: "The cross-project metrology store is named keystone yet left architecturally unconstrained"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:87
  - id: F007
    severity: concern
    category: dependencies
    summary: "Pre-emption prompt's data path into dispatch is unspecified and risks an upward dependency"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:97
  - id: F008
    severity: concern
    category: feasibility
    summary: "The pre-emption delta is measured against an oracle whose noise floor is never measured"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:83-85
  - id: F009
    severity: note
    category: extension-points
    summary: "Per-model calibration has no expression point in the threshold config it feeds"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:36
  - id: F010
    severity: note
    category: abstraction
    summary: "\"One metrology shape, reporting built once\" overstates what the two oracles share"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:69
  - id: F011
    severity: note
    category: consistency
    summary: "Skill name drift: \"tech-debt-audit\" vs. the actual `tech-debt-analyze` skill"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:22
---

# Review: arch — slice 320

**Verdict:** CONCERNS
**Model:** claude-fable-5

## Findings

### [CONCERN] Judge-configuration identity cannot be satisfied read-side — the persisted record has no template version

The "Comparability across template and model versions" consideration fixes as architectural that "measurements are keyed by judge configuration (template identity/version, model)." But the "Read-side over 300's write path" principle (line 46) forbids modifying "the result models' write semantics," and the actual persisted record (`ReviewResult` in `src/squadron/review/models.py`) carries `template_name` and `model` but **no template version**. These three facts are jointly unsatisfiable: a template revision under an unchanged name silently blends incompatible calibration data — the exact failure this consideration says must not happen. Version can be hashed read-side at *sample-capture* time for future data, but historical results and opportunistic dispersion data (line 81) cannot be version-keyed retroactively. The doc's escape hatch ("where a latent field exists… 320 populates or reads it") does not apply — no latent version field exists. Either the read-side principle needs an explicit carve-out (a version/hash field is a 300 write-path change, coordinated like the checkpoint multi-verdict case in 300-slices), or the doc must commit to name+model granularity and state the blending risk it accepts.

### [CONCERN] The calibration loop destroys its own evidence source at graduation

Cross-cutting gap, so no single section to pin. The entire loop moves judges from advisory (human sees escalations) toward auto-gate (human never sees the artifact). Once a judge graduates at an artifact level, human spot-checks of that judge's calls stop occurring naturally — the sample source *is* the escalation flow the graduation removes. Consequences the document never addresses: (a) false-PASS on auto-gated artifacts becomes systematically unobservable — the most dangerous error class is exactly the unsampled one; (b) agreement n freezes at graduation, so within-configuration drift or simple regression goes undetected forever. "Sampling ergonomics" (line 75) discusses *which results are offered* but only pre-graduation. The architecture needs a commitment to forced random sampling of auto-gated results (a "trust but verify" tax), or graduation is a one-way door with no ongoing instrument check — ironic for a metrology initiative.

### [CONCERN] Human-verdict anchoring is unaddressed and inflates the number that loosens gates

"Sampling capture ergonomics" (line 75) covers *selection* bias (random vs. disagreement-triggered) but not *judgment* bias: the operator "spot-checks a judge call," i.e. reads the judge's score, verdict, and findings, *then* records their own verdict. A human verdict formed after seeing the judge's output is anchored toward agreement — 300-arch itself cites prompt anchoring as a known LLM failure; humans have the same one. The inflated agreement number is precisely the input to calibration-to-threshold feedback, so the bias pushes thresholds looser. Whether capture is blind (human sees artifact + ground truth, not the judge's call) or anchored is an architectural constraint on the capture surface, not slice-level ergonomics — it belongs beside the sampling-bias sentence and is absent.

### [CONCERN] `fan_out` is attributed to 140 but belongs to 180, which 320 claims independence from

Lines 81 and 110 both call it "140's `fan_out`." It is not: 140-arch contains no mention of `fan_out`; 180-slices slice 182 ("Fan-Out / Fan-In Step Type") says explicitly "**Relocated from 140 future work item 10**," with dependencies on 180's pool resolver (181). Meanwhile the initiative plan (line 44) declares 320 "Independent of 180." So dispersion measurement — a stated capability of this initiative — piggybacks on machinery owned by an initiative the dependency analysis disclaims. Also verify slice-182 status before relying on it: it is marked Risk: High in 180-slices. Fix the attribution and either add 180 to the dependency story or scope dispersion to 300's multi-sample option only.

### [CONCERN] Frontmatter dependencies omit 340, on which two of five slices depend

`dependencies: [100, 140, 300]` — but the tech-debt-audit baseline harness and the pre-emption prompt (slices 4 and 5, lines 96–97) cannot exist without the audit skill "shipped in the 340 analysis pack" (line 22). 340-arch line 81 names 320 the "primary consumer of the analysis pack," and the initiative plan (line 45) says the same. 340 is complete, so this is not a sequencing risk today, but the frontmatter is the machine-readable dependency record and it contradicts the document body and both sibling documents. Add 340.

### [CONCERN] The cross-project metrology store is named keystone yet left architecturally unconstrained

"Where metrology data lives" correctly identifies that cross-project aggregation is a *new* requirement (300's persistence is per-run/per-project) and then defers essentially everything to slice design: store location, relation to 280, join mechanism. "Queryable and joinable" is the only commitment. But load-bearing questions with document-wide consequences go unaddressed at the level that should settle them: (a) what is a project's stable identity across the store (path? name? repo URL?) — every cross-project report keys on it; (b) does the store live user-level, repo-level, or centrally — this determines whether joins against per-project judge results are file reads or a sync problem; (c) 280 is `status: not_started`, so "candidate relationship" risks the keystone slice blocking on, or speculatively designing for, an initiative that doesn't exist. Every other slice consumes this store; deferring its shape entirely makes the keystone slice an architecture phase in disguise.

### [CONCERN] Pre-emption prompt's data path into dispatch is unspecified and risks an upward dependency

The "dispatch-side prompt-chaining pre-emption prompt" must front-load "the issue classes the audit actually finds" — i.e., content derived from the cross-project metrology store must reach a dispatch prompt at pipeline runtime. Mechanism is nowhere specified: is it a generated static prompt fragment the operator regenerates (safe — data flows down as configuration), or does dispatch query the metrology layer at run time (140's dispatch path depending upward on a 320 store — a dependency inversion, and a new runtime failure mode for every dispatch when the store is absent)? The Non-Goals rule out changes to the *judging* path but say nothing about the *dispatch* path, so this initiative does modify pipeline-facing surfaces while its dependency section is silent about the direction. Commit to the generated-artifact model (or equivalent) at architecture level.

### [CONCERN] The pre-emption delta is measured against an oracle whose noise floor is never measured

"Normalizing an LLM-authored audit" concedes the audit is "non-deterministic run-to-run" and that "the audit's own variance is itself a calibration concern… the metrology should be honest about it" — and then commits to nothing. "Attribution of the pre-emption delta" (line 85) accepts an observational before/after but never requires establishing the oracle's run-to-run variance first (e.g., N repeated audits on unchanged code to bound noise). Without a measured noise floor, even the promised "credible directional signal" is unfounded: at a "handful of projects" (line 52), a findings-count delta smaller than the audit's own variance is indistinguishable from noise, and the initiative's flagship customer demo becomes exactly the overclaiming line 85 warns against. "Baseline before intervention" (line 50) should be "variance, then baseline, then intervention" — that ordering is architectural, not slice detail.

### [NOTE] Per-model calibration has no expression point in the threshold config it feeds

Calibration is keyed by (template, model), but 300's threshold locus — the config surface line 36 says calibration feeds — is template-level with step-level override, with no model dimension. This works only while a judge step pins one model; with 180's model pools/fan-out drawing models at runtime, a step's threshold cannot vary with the model actually selected, so "model X overreaches, Y rubber-stamps" is measurable but not actionable through the stated feedback path except by manually pinning models. Worth one sentence acknowledging the feedback resolves to "operator picks model + threshold at config time," or the calibration-to-threshold slice will rediscover it.

### [NOTE] "One metrology shape, reporting built once" overstates what the two oracles share

The claimed shared shape — "capture oracle verdicts, persist them queryably, report agreement/trend" — only half-applies to the audit oracle: it has no agreement dimension (nothing is compared against a human), its grain is project/issue-class rather than artifact-level/judge-configuration, and its headline report is a before/after count delta, not inter-rater agreement. "Trend with sample sizes" is genuinely shared; the rest is not. If the reporting layer is literally built once, expect either a forced abstraction or two report paths behind one name. State the shared surface honestly (persistence conventions + trend reporting) rather than "built once."

### [NOTE] Skill name drift: "tech-debt-audit" vs. the actual `tech-debt-analyze` skill

This document consistently says "tech-debt-audit," but 340-arch names the forked skill `tech-debt-analyze` (lines 43, 62, 75) and only its Related Work line echoes "tech-debt-audit." Per project convention (one definition, referenced everywhere), pick the real skill identifier before slice design bakes the wrong name into harness code and pack manifests.

---

## Response (20260717)

All 11 findings addressed in [320-arch.judge-calibration-quality-metrology.md](../architecture/320-arch.judge-calibration-quality-metrology.md). Every factual claim in the review was verified against source before acting.

- **F001** (write-path tension) — verified: `ReviewResult` carries `template_name` + `model`, no version field. The "Comparability" consideration now names the three-way unsatisfiability explicitly and resolves it: preferred path is a coordinated 300 write-path version/hash field (dependency-flagged like the checkpoint multi-verdict case), fallback is content-hashing at capture time with historical/opportunistic data flagged, not silently pooled.
- **F002** (graduation destroys evidence) — accepted. New principle *Graduation is not a one-way door*: forced residual random sampling of auto-gated results survives graduation.
- **F003** (human anchoring) — accepted. New principle *Blind capture, not anchored*: judge output withheld until the human commits their independent verdict.
- **F004** (fan_out mis-attributed) — verified: `fan_out` is 180's (slice 182, relocated from 140 FW10), and the initiative plan declares 320 "Independent of 180." Fixed by scoping dispersion to **300's multi-sample option only**; attribution corrected in the consideration and in Related Work (140 + 180). No 180 dependency added, honoring the plan.
- **F005** (missing 340 dep) — verified: the audit skill ships in 340's pack; initiative plan says "340 does not depend on 320" but 320 consumes it. Added `340` to frontmatter `dependencies`.
- **F006** (metrology store unconstrained) — accepted. The "Where metrology data lives" consideration now fixes three load-bearing commitments: stable explicit project identity (not a path), user-level/central store locality, and no hard dependency on the not-started 280.
- **F007** (pre-emption data path) — accepted. New consideration *Pre-emption data flows down as configuration, never up at runtime*: generated static prompt fragment, dispatch never queries the metrology store at runtime.
- **F008** (unmeasured oracle noise floor) — accepted. Principle rewritten to *Variance, then baseline, then intervention*; the audit-normalization and attribution considerations now require measuring run-to-run variance (repeated audits on unchanged code) and reporting the delta against that floor.
- **F009** (note — per-model calibration has no threshold expression point) — accepted. *Calibration feeds the gates* now states the feedback resolves to operator picking model+threshold at config time; a runtime-drawn model (180 pool) cannot vary its threshold.
- **F010** (note — "built once" overstates shared shape) — accepted. Overview and Envisioned State now describe a shared metrology **spine** (persistence + trend reporting) with two distinct headline analyses, not one report path.
- **F011** (note — skill name) — **verified the review's premise is inverted.** The shipped artifact's frontmatter `name:`, its file (`commands/analysis/tech-debt-audit.md`), and the live dispatch surface (`/analysis:tech-debt-audit`) all use `tech-debt-audit`. `tech-debt-analyze` is 340-arch's stale name that never matched the shipped skill. This doc keeps the correct `tech-debt-audit` and adds a Related Work note; the drift is 340-arch's to reconcile (a 340/900 housekeeping item, not a 320 change).
