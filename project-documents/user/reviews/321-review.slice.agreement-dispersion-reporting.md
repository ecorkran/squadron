---
docType: review
layer: project
reviewType: slice
slice: agreement-dispersion-reporting
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/321-slice.agreement-dispersion-reporting.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260722
dateUpdated: 20260722
findings:
  - id: F001
    severity: fail
    category: data-model
    summary: "Dispersion groups by review-file identity, so cross-config dispersion on the same artifact cannot match"
    location: 321-slice.agreement-dispersion-reporting.md#component-structure
  - id: F002
    severity: note
    category: interfaces
    summary: "Interfaces with slices 323 and 324 are listed but not defined"
    location: 321-slice.agreement-dispersion-reporting.md#integration-points
---

# Review: slice — slice 321

**Verdict:** FAIL
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [FAIL] Dispersion groups by review-file identity, so cross-config dispersion on the same artifact cannot match

The slice defines dispersion as judge-vs-judge disagreement on the *same* artifact across distinct judge configurations, and groups by `(ArtifactLevel, result_ref)` (see `dispersion_report` in `report.py`). It also defines `result_ref` as a pointer to the persisted **300 review file** (`project_id`, `relative_review_path`, `content_hash`) used for the judge-side agreement join. Two different judge configurations grading the same artifact produce two different review files with two different `content_hash`es, so they have **two different `result_ref`s**. A group keyed by `result_ref` can therefore never contain ≥2 distinct `JudgeConfigId`s for the same artifact, so cross-configuration dispersion cannot be produced. This directly contradicts the verification walkthrough step 4, which expects two models' review files for the same slice to appear together under `sq metrology report dispersion`, and undermines 320-arch's "Cross-judge comparability" design goal. The group key must identify the underlying artifact being reviewed, not the review-file instance, and then collect the distinct judge configurations/verdicts captured against that artifact.

### [NOTE] Interfaces with slices 323 and 324 are listed but not defined

The slice frontmatter lists `interfaces: [322, 323, 324]`, and the document explicitly defers audit-oracle reporting to slice 323, but the *Integration Points* section only describes what **322** consumes (`AgreementReport`, `ArtifactLevel`, `min_evidence_n`). It is unclear whether 321 provides to or expects anything from 323/324. Since 320-arch states that the two oracles share the metrology *spine*, not a single report path, those interface expectations should be documented or removed from the interface list.
