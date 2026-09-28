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
reviewedSha: 10cf828b00bb6c9a81035ee9b9ac64b95d8b4c49
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-783dab3a
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Fits the maintenance initiative scope"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Overview"
  - id: F002
    severity: pass
    category: architecture
    summary: "Dependency direction and layering"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Component-Structure"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for hang and timeout are not enumerated for the new per-part I/O path"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Patterns-and-Conventions"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Silent gap in verdict semantics when a part's save fails"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Patterns-and-Conventions"
  - id: F005
    severity: concern
    category: integration
    summary: "Known downstream gate defect is recorded but not tracked"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Integration-Points"
  - id: F006
    severity: note
    category: specification
    summary: "Verdict fold and score/criteria tie-breaking are under-specified at the edges"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Data-Flow"
  - id: F007
    severity: note
    category: specification
    summary: "Behavior change to `resolve_template_inputs` signature"
    location: "project-documents/user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md#Migration-Plan"
  - id: F008
    severity: note
    category: nfr
    summary: "NFR restatement not applicable"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
---

# Review: slice — slice 930

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Fits the maintenance initiative scope

This is a non-trivial bug fix (issue #153) that also removes a latent `KeyError` and moves the part naming and verdict folding into one module. Arch 900 lists "Bug fixes" and "Refactoring: consolidating duplicated logic" as in scope. Effort is 2/5 and the slice can be delivered on its own. Out-of-scope items are explicit: no task splitting, no cleanup of old artifacts, and no context-forge change.

### [PASS] Dependency direction and layering

`review/parts.py` is a leaf module. Both `cli/commands/review.py` and `pipeline/actions/review.py` depend on it, and it depends on neither. The `fans_out` fan-out is declared in the input registry, so `ReviewAction` needs no template-name string dispatch. That fits the project rule against string dispatch. Sharing naming and verdict folding instead of the loop body is justified in the doc, and it avoids a sync/async adapter layer.

### [CONCERN] Failure modes for hang and timeout are not enumerated for the new per-part I/O path

The failure-behavior paragraph covers a provider failure on part k and a failed save. It says nothing about a part that hangs or times out, or about a peer that disconnects mid-call. A run of N sequential calls multiplies exposure to those cases. The doc should say whether the existing per-call timeout applies to each part, or whether one timeout covers the whole step. It should also say what observable signal (WARNING+ log or metric) marks a timed-out part and which failure artifact slot it lands in. The test list has one failure test, for a provider failure on part 2. It has none that asserts the observable signal for a timeout or a non-fatal save failure. The review-code rule requires an observable signal and a test for each failure mode.

### [CONCERN] Silent gap in verdict semantics when a part's save fails

A save failure is logged and the step continues. In the multi-part case that leaves a verdict for a part with no artifact on disk. The context-forge gate and the parity claim ("identical filenames") both rely on those artifacts, so the step can report success while artifacts are missing. The doc should say whether that case is surfaced in `ActionResult` (for example in `metadata` or `outputs`), or state why a log line alone is enough.

### [CONCERN] Known downstream gate defect is recorded but not tracked

The doc finds that context-forge's gate reads only the lexicographically last tasks review. That means the gate can PASS a slice whose worst part failed. The slice's stated Value is that "a PASS on part 1 no longer clears a slice whose part 3 is broken", but this defect leaves the gate open to the same failure. The doc defers the fix and leaves the issue link as a to-do (implementation step 7). Project convention is to log deferred work as a GitHub issue and link its number from the deferring decision. File the issue before implementation starts, or state that the Value claim covers pipeline gating only.

### [NOTE] Verdict fold and score/criteria tie-breaking are under-specified at the edges

The fold takes `score` and `criteria` from the lowest-scoring part, and `review_file` from the worst verdict part, first on ties. Those two can point at different parts. That is acceptable, but the doc should state it. It should also say how a part with no score is treated when other parts have one. This is minor and can be settled in the task breakdown.

### [NOTE] Behavior change to `resolve_template_inputs` signature

`resolve_template_inputs` now returns a list and stops mutating its argument. The doc names the single production caller and the affected tests. That covers the integration surface adequately. No action is needed beyond the planned updates.

### [NOTE] NFR restatement not applicable

Arch 900 states no NFRs (latency, throughput), so the slice has none to restate. Sequential per-part calls do raise wall-clock time roughly N-fold for split slices. The doc accepts that as a deliberate choice ("Sequential parts").

### Run Digest

- Response length: 5149 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
