---
docType: review
layer: project
reviewType: slice
slice: pipeline-tasks-review-covers-every-split-task-file
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: f135f30721f9bb8868f40b99c5f045b0266dc996
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-783dab3a
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "In-scope list omits the batch report change"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md:30-35"
  - id: F002
    severity: concern
    category: consistency
    summary: "Data flow uses a function name the Migration Plan removes"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md:97"
  - id: F003
    severity: concern
    category: integration
    summary: "Findings-to-dispatch contract rides on untyped dict keys"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md:111-121, 130-132"
  - id: F004
    severity: note
    category: scope
    summary: "Scope stays within the maintenance initiative's bounds"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Overview"
  - id: F005
    severity: pass
    category: architecture
    summary: "Dependency direction and layering"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Architecture"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated with observable signals"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Failure-Modes"
  - id: F007
    severity: pass
    category: integration
    summary: "Cross-repo boundary handled correctly"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Integration-Points"
---

# Review: slice — slice 930

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] In-scope list omits the batch report change

Component Structure (line 63) lists `pipeline/batch_report.py` as an edit to render `outputs["unsaved_parts"]`. The "In scope" list has no matching bullet. Failure Modes (line 158) and Success Criteria (line 202) both depend on it. The unsaved-part signal is the slice's answer to the silent-save-failure case, so it belongs in the scope list. Otherwise a reader of the scope list would think the batch report is untouched. Add the bullet.

### [CONCERN] Data flow uses a function name the Migration Plan removes

The Data Flow diagram calls `resolve_template_inputs(...)`. Line 85 and the Migration Plan (line 169) say that name is deleted and replaced by `resolve_template_input_parts`. Line 169 also requires `grep -rn resolve_template_inputs src tests` to return nothing. The diagram should use the new name. As written, it contradicts the slice's own guard against the silent-ignore bug.

### [CONCERN] Findings-to-dispatch contract rides on untyped dict keys

`ReviewAction` and `DispatchAction` now share a contract made of `outputs["input_files"]`, `outputs["input_file"]`, `outputs["unsaved_parts"]` and a per-finding `input_file` key. The doc describes it only in prose. The feedback prompt's behavior depends on whether `input_files` has more than one entry, so a rename or typo on either side would silently fall back to the single-file prompt. That is the kind of hidden dependency the "no silent fallback" rule targets. Define these keys once as constants, or a small typed structure, in one shared module. Also add a test asserting the dispatch prompt reads exactly what the review action writes. The parity tests cover file names but not this seam.

### [NOTE] Scope stays within the maintenance initiative's bounds

This is a bug fix (#153) plus a consolidation of duplicated logic. Both fit the architecture's "Bug fixes" and "Refactoring" categories. It adds no new capability. It touches about five files, which is at the upper edge of "small and focused". The doc justifies not extracting the full loop body, which avoids over-engineering.

### [PASS] Dependency direction and layering

`review/parts.py` sits in the review layer, and both the CLI and the pipeline depend on it, not on each other. Fan-out is declared in the input registry instead of by template-name checks in the action. That avoids string dispatch. Deleting the old function name so that stale callers break at import time is a good guard.

### [PASS] Failure modes enumerated with observable signals

The table covers provider error and timeout, hang, save-subprocess hang, and save failure. Each row gives a handling strategy and a WARNING or ERROR log or a named output, and tests are specified with `caplog`. The hang case explicitly declines a per-part timeout and explains why. Validating every part before the first model call is a good way to avoid wasted spend. Sequential runs multiply latency by N, which is acceptable because the architecture states no NFR for this path.

### [PASS] Cross-repo boundary handled correctly

The context-forge gate's last-match selection is recorded as out of scope and tracked in context-forge#106. The slice records what the consequences are, including the `part-10` ordering issue. It also states that a leftover unsuffixed review never wins. This respects the repository boundary and logs the deferred work as an issue, not as Future Work.

### Run Digest

- Response length: 4411 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
