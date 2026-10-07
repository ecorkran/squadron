---
docType: review
layer: project
reviewType: slice
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: 817adb82ae79bec1966109609dad374a6d9660a2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 25.9
runId: run-20261007-p4-08b6c078
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the parent architecture's 199 description"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Overview"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated with observable signals"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#D7. Failure modes"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "`run_listing` pulls the executor's heavy import graph through `ExecutionStatus` and a private constant"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:85"
  - id: F004
    severity: concern
    category: nfr
    summary: "The performance target is verified manually, not by a test"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Special Considerations"
  - id: F005
    severity: note
    category: scope
    summary: "Refactoring of 197-owned code widens the slice's footprint"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#D3"
  - id: F006
    severity: note
    category: integration
    summary: "`--json` deferral and the architecture's Amoeba framing"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Technical Scope"
  - id: F007
    severity: note
    category: documentation
    summary: "Architecture overview was already updated for 199"
    location: "project-documents/user/architecture/180-arch.pipeline-intelligence.md:49"
---

# Review: slice — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the parent architecture's 199 description

The slice implements what 180-arch §Relationship to 140 attributes to it: runs `--resume` can act on, including finished batches with open items, listed via `pipeline/run_listing.py`, and `sq pipelines list` replacing `sq run --list`. It is read-only. It adds no grammar and no review-model changes, so the architecture's "Out of Scope" limits on 140 grammar and review models hold. The slice reads 197's `BatchReport`, `ItemOutcome`, `FlagKind` and `ItemDecision` as the interface for flag handoff.

### [PASS] Failure modes enumerated with observable signals

D7 covers the cases on this slice's I/O paths:
- corrupt run state;
- unloadable definition;
- missing unfinished step;
- unsupported `each` count;
- unreadable report;
- `running` runs;
- concurrent writers, with the atomic-replace argument.

Each case has a row marker or a WARNING log, and unlisted exceptions propagate. Hang and timeout are not discussed. That is reasonable because everything is local-disk reads, but the slice does not say so. A one-line statement would close the gap.

### [CONCERN] `run_listing` pulls the executor's heavy import graph through `ExecutionStatus` and a private constant

The slice justifies `item_eligibility` by saying it keeps the read-only listing from pulling in git machinery. But the listing still depends on `ExecutionStatus` (Interfaces Required, line 58) and `_RESUMABLE_STATUSES`. `state.py` already imports `ExecutionStatus` from `executor.py` (state.py:25), and `executor.py` imports `git_ops`, `branch_ops`, `commit_plan` and `loop_commit` at module level. So `run_listing` reaches git-related modules transitively, and the stated isolation claim does not hold.

D10 also has the listing import a private, underscore-named constant (`_RESUMABLE_STATUSES`) across modules. Two options:
- Expose a public `RESUMABLE_STATUSES` from `state.py`.
- Move the status enum to a lightweight module.

Either one, or an explicit acknowledgement that the import cost is accepted, would remove the inconsistency.

### [CONCERN] The performance target is verified manually, not by a test

The architecture states no NFR for this path, so the slice correctly sets its own: under 1 s for a few hundred runs. The only check is the walkthrough timing in step 7, and a miss is deferred to "a finding for Phase 7". Two parts of the path are not bounded: one glob per completed run, and one report read per completed batch run. A cheap automated check would be a test with a few hundred synthetic runs that asserts the number of definition loads and report reads. The slice already specifies one-definition-load-per-pipeline, but not a bound on globs or reads. Adding one would make the target regress-detectable.

### [NOTE] Refactoring of 197-owned code widens the slice's footprint

The slice moves eligibility rules out of `item_resume`, extracts `first_unfinished_step_of`, adds `report_json_path`, and retypes `PipelineInfo.source`. This touches 197 and 140 code. It is justified by DRY and a no-drift guarantee, and it is protected by the parity test and by "existing tests pass unchanged". The slice is rated effort 2/5 but carries a refactor across four modules. Keep it as the first implementation step, as the development approach already does.

### [NOTE] `--json` deferral and the architecture's Amoeba framing

180-arch names Amoeba as an intended consumer of the item-resume interface. The slice defers `--json`, so an out-of-process consumer cannot enumerate runs programmatically. The slice states this openly and Python callers are served. No change is needed. The slice or the architecture should record the follow-up if Amoeba starts consuming runs.

### [NOTE] Architecture overview was already updated for 199

The architecture already names slice 199, `sq runs list` and `run_listing.py`, so the parent document and the slice agree. No update is required.

### Run Digest

- Response length: 5352 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 25.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
