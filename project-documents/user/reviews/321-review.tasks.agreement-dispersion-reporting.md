---
docType: review
layer: project
reviewType: tasks
slice: agreement-dispersion-reporting
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260723
dateUpdated: 20260723
findings:
  - id: F001
    severity: pass
    category: completeness
    summary: "Report models capture the 322 consumption interface"
    location: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
  - id: F002
    severity: pass
    category: completeness
    summary: "Core-CLI parity and read-only invariance are explicitly tested"
    location: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
  - id: F003
    severity: pass
    category: nfr/load-test
    summary: "No NFR restated, so no load-test or CI-gating task is required"
    location: project-documents/user/slices/321-slice.agreement-dispersion-reporting.md
  - id: F004
    severity: concern
    category: sequencing
    summary: "Config-key task is sequenced after report tasks that need its keys"
    location: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Malformed/unparseable review frontmatter is missing from enrichment tests"
    location: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Empty-store honest render lacks an explicit test task"
    location: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
  - id: F007
    severity: note
    category: test-coverage
    summary: "Corrupt-sibling store-read tolerance is inherited but not explicitly re-tested"
    location: project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md
  - id: F008
    severity: note
    category: consistency
    summary: "Slice design mentions `--judge-config` convention but API contracts omit it"
    location: project-documents/user/slices/321-slice.agreement-dispersion-reporting.md
---

# Review: tasks — slice 321

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [PASS] Report models capture the 322 consumption interface

T3 defines all required Pydantic models (`GroupKey`, `AgreementCell`, `ArtifactKey`, `DispersionCell`, `ExclusionSummary`, `AgreementReport`, `DispersionReport`, `TrendReport`) matching the slice design's Report Models section and the integration requirement that 322 consume `AgreementReport` with `below_floor` and `ExclusionSummary`.

### [PASS] Core-CLI parity and read-only invariance are explicitly tested

T16 directly tests that `squadron.metrology.report` / `levels` / `report_models` import no Typer, that the CLI is a thin shell, and that store/review file bytes are unchanged after report commands, covering the technical requirements for surface-agnostic core and read-only discipline.

### [PASS] No NFR restated, so no load-test or CI-gating task is required

The slice design discusses a performance trip-wire for flat-file vs. SQLite but does not restate a quantified NFR (target latency, throughput, or memory). Therefore the absence of a `tests/load/` task and CI wiring is correct and not a gap.

### [CONCERN] Config-key task is sequenced after report tasks that need its keys

T7's `agreement_report` computes `below_floor` using `metrology.min_evidence_n` and T11's `trend_report` relies on `metrology.trend_bucket`, but those `CONFIG_KEYS` entries are only added and wired in T13. A junior AI implementing T7/T11 first must hard-code a temporary default or leave a stub that T13 later refactors. Reorder T13 before T7/T11, or defer `below_floor`/bucket wiring out of T7/T11 until the keys exist.

### [CONCERN] Malformed/unparseable review frontmatter is missing from enrichment tests

The slice design's Failure Modes table requires a test for "review file present but frontmatter unparseable / no verdict" → `stale_judge_result`. T5 implements this handling, but T6 only tests missing file, overwritten file, missing `sourceDocument`, and unversioned records. Add a malformed-frontmatter fixture case to T6 to cover that row.

### [CONCERN] Empty-store honest render lacks an explicit test task

The Failure Modes table's "empty evidence" row requires a test that a store with no samples renders an honest "no evidence" report and exits 0. T10 mentions a "no-op/empty report" but in the context of missing `source_document`, and no task asserts behavior for a zero-sample store across agreement/dispersion/trend. Add explicit empty-store test cases.

### [NOTE] Corrupt-sibling store-read tolerance is inherited but not explicitly re-tested

The Failure Modes table's "store read" row (corrupt sibling skipped) is inherited from 320 and likely covered by 320's tests plus T17's full-suite run, but no 321-specific task explicitly asserts it. Consider adding a regression test in T16 or T17 if 320's coverage is not deemed sufficient for the report path.

### [NOTE] Slice design mentions `--judge-config` convention but API contracts omit it

The slice design text says the report commands reuse "`--cwd` / `--project` / `--judge-config` conventions", but the CLI API contracts and T15 list only `--project`, `--level`, `--json`, `--cwd` (plus `--bucket` for trend). The task breakdown correctly follows the explicit API contracts, so this is a slice-design inconsistency rather than a task gap. Ensure the final CLI surface matches whichever form is intended.
