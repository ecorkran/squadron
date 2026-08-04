---
docType: review
layer: project
reviewType: tasks
slice: sq-validate-docs-mechanical-frontmatter-enforcement
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260804
dateUpdated: 20260804
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "SC 6 refactoring has no implementation task"
    location: unverified
  - id: F002
    severity: concern
    category: uncategorized
    summary: "Function-name inconsistency between design SC 8 and task T5"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md#D8
  - id: F003
    severity: pass
    category: uncategorized
    summary: "All 20 success criteria trace to at least one task"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Load-bearing ordering is enforced by Part structure"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Test-with pattern is followed for every implementation task"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Commit checkpoints distributed across the slice"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md
  - id: F007
    severity: pass
    category: uncategorized
    summary: "CI gating is explicit, not implicit"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md#T20
  - id: F008
    severity: note
    category: uncategorized
    summary: "T4 is the largest single task but is appropriately scoped"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md#T4
  - id: F009
    severity: note
    category: uncategorized
    summary: "T19 mixes automated tests with manual walkthrough"
    location: project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md#T19
  - id: F010
    severity: pass
    category: uncategorized
    summary: "No load-test NFR restated; no load-test task required"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md
---

# Review: tasks — slice 172

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Findings

### [CONCERN] SC 6 refactoring has no implementation task

Success criterion 6 requires "no status or `docType` string literal appears elsewhere in `src/`." T1's success criterion echoes this ("no other module in `src/` contains a status or docType string literal after Part 3 lands") and T21's verification greps for it, but no task in Parts 1–3 actually performs the refactoring of existing literals. The Part 1–3 tasks touch only `documents/frontmatter.py` (imports only), `config/keys.py` (new key), new CLI files, and `cli/app.py` (one wiring line). If any module currently carries a status/`docType` literal — even one — it will be found by T21's grep with nothing to fix it. Recommend an explicit task (likely a small grep-driven sweep) inserted into Part 1 or Part 2, with its own test asserting the absence.

### [CONCERN] Function-name inconsistency between design SC 8 and task T5

SC 8 in the design specifies that "an actual `render_gate_evidence` and `render_resolution` output passes the validator in a test." T5 instead instructs the implementer to "render actual frontmatter via `gate_evidence_frontmatter` and `resolution_frontmatter`." The design itself is inconsistent — D9 of the same slice says "`gate_evidence_frontmatter` and `resolution_frontmatter` already do" — so SC 8 likely has the wrong names. T5 follows the D9 convention, which matches the codebase references (`pipeline/actions/findings_addressed/evidence.py:26` exports `GATE_EVIDENCE_DOC_TYPE`; `review/resolution_artifact.py:25` exports `RESOLUTION_DOC_TYPE`). Recommend correcting SC 8 in the slice design to match the function names T5 actually uses, so the criterion and the task agree.

### [PASS] All 20 success criteria trace to at least one task

Mapping check: SC1→T9/T10, SC2→T8/T9, SC3→T6/T7, SC4→T3/T4/T5, SC5→T4/T5, SC6→T1/T21 (gap noted above), SC7→T2, SC8→T5, SC9→T4/T9, SC10→T9/T10, SC11→T9/T10, SC12→T17/T19, SC13→T18/T19, SC14→T15/T16, SC15→T21, SC16→T20, SC17→T13, SC18→T13/T14, SC19→T11/T12, SC20→T15. No orphan tasks that fail to trace to a success criterion, beyond the routine close-out work in T22.

### [PASS] Load-bearing ordering is enforced by Part structure

The context summary calls out two ordering constraints: writer fix (Part 4) before cleanup (Part 6), and cleanup (Part 6) before CI (Part 8). Both are reflected — T11/T12 are Part 4, T15/T16 are Part 6, T20 is Part 8. T16 also explicitly says "Commit the cleanup separately from the feature work," matching the design's "CI must not gate on the validator until the cleanup commit has landed" requirement.

### [PASS] Test-with pattern is followed for every implementation task

T2 follows T1, T5 follows T4, T7 follows T6, T10 follows T9, T12 follows T11, T14 follows T13, T19 follows T17/T18. No implementation task is left without an immediately-following test task.

### [PASS] Commit checkpoints distributed across the slice

The Part structure provides natural commit boundaries (8 feature parts + Part 9 close-out), T16 mandates its own cleanup commit separate from feature work, and T21 closes with the verification commit. No batching at the end.

### [PASS] CI gating is explicit, not implicit

T20 wires `uv run sq validate docs` into `.github/workflows/ci.yml` as an explicit CI step in the `test` job, with `submodules: true` on the checkout. This is the CI gating for SC 16 and is not left implicit.

### [NOTE] T4 is the largest single task but is appropriately scoped

T4 implements `validate_document` covering all eight FM001–FM008 codes, line-number resolution, and classification into two document classes. It is large in line count but cohesive: one function, one success criterion, clear acceptance ("one document yields all applicable violations, not just the first"). A junior AI can complete it against the T5 fixture list.

### [NOTE] T19 mixes automated tests with manual walkthrough

T19 combines unit tests for `check_git_hooks`, a documentation update, and a manual walkthrough of verification steps 5 and 6 "by hand." The manual component is unusual for a test task but is explicitly scoped and bounded to two specific steps from the design's walkthrough. Acceptable; flagging only because it deviates from the test-with pattern elsewhere in the slice.

### [PASS] No load-test NFR restated; no load-test task required

The design does not restate any non-functional requirement. The 1/5 effort estimate and the slice's character (a deterministic, I/O-bound validator plus a git hook) do not warrant a load test. No `tests/load/` task is needed.
