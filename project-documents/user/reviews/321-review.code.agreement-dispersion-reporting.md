---
docType: review
layer: project
reviewType: code
slice: agreement-dispersion-reporting
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/321-slice.agreement-dispersion-reporting.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260725
dateUpdated: 20260725
findings:
  - id: F001
    severity: pass
    category: design-principles/dry
    summary: "Artifact-level vocabulary is centralized with an explicit `UNCLASSIFIED` fallback"
    location: src/squadron/metrology/levels.py#ArtifactLevel
  - id: F002
    severity: pass
    category: failure-mode-enumeration/error-handling
    summary: "Enrichment content-verifies referenced reviews and emits observable warnings for stale results"
    location: src/squadron/metrology/report.py#_enrich_one
  - id: F003
    severity: pass
    category: testing
    summary: "Tests are added alongside implementation and cover empty-store, stale-join, and unversioned-segregation cases"
    location: tests/metrology/test_report_agreement.py
  - id: F004
    severity: pass
    category: design/typing
    summary: "Report models provide a stable JSON contract that always carries exclusion metadata"
    location: src/squadron/metrology/report_models.py#ExclusionSummary
  - id: F005
    severity: concern
    category: ui/ux
    summary: "`metrology report trend` human output only renders agreement rows"
    location: src/squadron/cli/commands/metrology.py#report_trend
  - id: F006
    severity: concern
    category: error-handling/reporting
    summary: "Samples excluded from dispersion for missing `sourceDocument` are not reflected in `ExclusionSummary`"
    location: src/squadron/metrology/report.py#dispersion_report
  - id: F007
    severity: concern
    category: error-handling
    summary: "Agreement/dispersion CLI commands do not catch `MetrologyTargetError`"
    location: src/squadron/cli/commands/metrology.py#report_agreement
  - id: F008
    severity: note
    category: typing
    summary: "`EnrichedSample.admissible` could use `Literal[...]` typing"
    location: src/squadron/metrology/report.py#EnrichedSample
---

# Review: code — slice 321

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [PASS] Artifact-level vocabulary is centralized with an explicit `UNCLASSIFIED` fallback

The `ArtifactLevel` `StrEnum` and `_REVIEW_TYPE_TO_LEVEL` map are the single source of truth for review-type-to-level mapping, and `derive_artifact_level` returns `UNCLASSIFIED` instead of silently dropping unknown values. This follows the project rule that comparison values must be defined once and referenced everywhere.

### [PASS] Enrichment content-verifies referenced reviews and emits observable warnings for stale results

`_enrich_one` catches unreadable review files, hash mismatches, and unparseable verdicts as `MetrologyTargetError`/`ValueError`, logs each at `WARNING`, and returns `admissible="stale-judge-result"`. This satisfies the failure-mode-enumeration requirement that exclusion paths must be observable, not silent.

### [PASS] Tests are added alongside implementation and cover empty-store, stale-join, and unversioned-segregation cases

The new test files are committed with the implementation, exercise edge cases (empty store, content-hash mismatch, missing review file, unversioned record segregation), and use pytest fixtures/parametrize patterns.

### [PASS] Report models provide a stable JSON contract that always carries exclusion metadata

`AgreementReport`, `DispersionReport`, and `TrendReport` all include `ExclusionSummary`, ensuring `--json` consumers can see what was left out rather than inferring from an empty `cells` list.

### [CONCERN] `metrology report trend` human output only renders agreement rows

The command help says it reports “Agreement/dispersion figures bucketed over time,” and the `TrendReport` model carries both `agreement` and `dispersion`. The rendering loop in `report_trend` only iterates over `entry.agreement.cells`, so human-mode users never see the dispersion figures. Add a dispersion rendering section or update the help text to match actual behavior.

### [CONCERN] Samples excluded from dispersion for missing `sourceDocument` are not reflected in `ExclusionSummary`

The loop skips items where `source_document is None`, which is correct, but those samples are not counted in `ExclusionSummary` (only `stale_judge_result` and `unversioned` are). Because `ExclusionSummary` is meant to make exclusions visible, missing-source-document samples are effectively silently dropped from the dispersion report. Add a dedicated counter or category so the summary matches the actual exclusions.

### [CONCERN] Agreement/dispersion CLI commands do not catch `MetrologyTargetError`

`report_agreement` and `report_dispersion` only catch `MetrologyStoreError`, while `agreement_report`/`dispersion_report` can raise `MetrologyTargetError` (e.g., an invalid `metrology.min_evidence_n` value). This is inconsistent with `report_trend`, which catches both. Wrap the core call in a `MetrologyTargetError` handler as well.

### [NOTE] `EnrichedSample.admissible` could use `Literal[...]` typing

The dataclass field is typed as `str` with a comment documenting the two allowed values. Prefer `typing.Literal["admissible", "stale-judge-result"]` so static analysis and readers can see the restricted domain directly.
