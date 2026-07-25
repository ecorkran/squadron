---
docType: review
layer: project
reviewType: slice
slice: calibration-to-threshold-feedback
project: squadron
verdict: UNKNOWN
sourceDocument: project-documents/user/slices/322-slice.calibration-to-threshold-feedback.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260725
dateUpdated: 20260725
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Feedback remains advisory and read-only on 300 surfaces"
    location: 322-slice.calibration-to-threshold-feedback.md#technical-scope
  - id: F002
    severity: concern
    category: data-model
    summary: "GraduatedConfig omits judge-configuration identity"
    location: 322-slice.calibration-to-threshold-feedback.md#component-structure
  - id: F003
    severity: note
    category: failure-handling
    summary: "Low-level I/O/transient failure modes are not enumerated"
    location: 322-slice.calibration-to-threshold-feedback.md#failure-modes
---

# Review: slice — slice 322

**Verdict:** UNKNOWN
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [PASS] Feedback remains advisory and read-only on 300 surfaces

The slice restricts itself to producing `ThresholdRecommendation` output and reading current thresholds via `resolve_thresholds` / `ReviewTemplate.judge`. It explicitly excludes automatic threshold mutation and any new gating mechanism, matching the architecture's Non-Goal "No automatic threshold mutation" and the principle that "calibration output is configuration, not a new gating mechanism."

### [CONCERN] GraduatedConfig omits judge-configuration identity

The architecture states that "Metrology records must therefore identify the judge configuration they measured" because version/key identity is required to avoid blending incompatible calibration data. The `GraduatedConfig` shape defined in this slice only contains `template_name`, `model`, `artifact_level`, and an `EvidenceSnapshot` — it does not include the `JudgeConfigId` / `template_content_hash` that 321/320 use to version a calibration cell. Because residual sampling selects results for a graduated config, the missing identity means offers could be drawn from a different template/model version after a prompt or model edit, violating the architecture's version non-blending guarantee and undermining the "continued forced random sampling" commitment. Add `judge_config_id: JudgeConfigId` (and/or `template_content_hash`) to `GraduatedConfig` and use it in `select_residual_offers`.

### [NOTE] Low-level I/O/transient failure modes are not enumerated

The failure-mode table covers semantic cases (empty store, below-floor refusal, unversioned config, missing template, malformed threshold, graduation guard, etc.) but does not enumerate lower-level, per-I/O-path failures such as store lock contention, file-system timeout, or partial read while loading the store or templates. Consider adding a row for "store/template read hangs/times out or returns partial data" with an explicit handling strategy and observable exit code.
