---
docType: review
layer: project
reviewType: slice
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: 941703f1b306818e27e2ee8eac032b26bedce5ff
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 30.0
runId: run-20261007-p4-08b6c078
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Scope and layering match the parent architecture"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Architecture"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated, observable and testable"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#D7. Failure modes"
  - id: F003
    severity: note
    category: integration
    summary: "Runs are global to the user, not scoped to a checkout"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Data Flow"
  - id: F004
    severity: note
    category: scope
    summary: "Refactor of 140 and 197 modules is justified but carries risk"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Development Approach"
  - id: F005
    severity: note
    category: integration
    summary: "`--json` exclusion leaves out-of-process consumers without a listing"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Technical Scope"
  - id: F006
    severity: note
    category: nfr
    summary: "No NFR in the parent architecture applies to this path"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Special Considerations"
---

# Review: slice — slice 199

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope and layering match the parent architecture

The architecture describes this slice as making 197's batch runs findable. It lists runs `--resume` can act on, including finished batches with open items, and it replaces `sq run --list` for pipeline discovery. The slice delivers exactly that.
- It adds no grammar and no review-model change, so it stays inside the "Out of Scope" boundary.
- Dependencies run one way: `cli/commands/*` → `cli/run_views` → `pipeline/run_listing` → pipeline modules. No command imports another command.
- The listing is read-only. It cannot violate the architecture's rules for git-mutating steps or its run-lock rule.

### [PASS] Failure modes are enumerated, observable and testable

D7 covers unreadable state, an unloadable definition, no unfinished step, an unsupported `each` count, an unreadable report, `running` runs and concurrent writers. Each case has a row marker and a WARNING log, and the success criteria require tests asserting both. D12 states that all I/O is local and bounded, so there is no timeout or hang path. I checked `BatchReport.load`: it already converts `OSError` and decode errors into `BatchReportLoadError`, so the single exception named for the report row is sufficient.

### [NOTE] Runs are global to the user, not scoped to a checkout

The architecture describes a per-checkout run lock. `RunState` has no project or checkout field, and the runs directory is `~/.config/squadron/runs`. So `sq runs list` shows runs from every repository. Two consequences follow:
- Pipeline definitions load relative to the current project. A run from another repository can therefore show `PIPELINE_UNAVAILABLE` or resolve to a different pipeline of the same name.
- The slice does not say whether this is accepted.

Add one sentence saying the listing is user-global and that a `PIPELINE_UNAVAILABLE` row may mean "run from another project".

### [NOTE] Refactor of 140 and 197 modules is justified but carries risk

Step 1 touches `state`, `batch_report`, `item_resume` and `loader`. These are the interface the architecture designates for Amoeba to apply decisions. The slice mitigates the risk well:
- The refactor lands as its own commit.
- The existing tests must pass unchanged.
- A parity test guards the eligibility rules.

I treat this as necessary scope, because it prevents the listing and `--resume` from disagreeing.

### [NOTE] `--json` exclusion leaves out-of-process consumers without a listing

The architecture frames item resume as the interface Amoeba, or a human, uses. Amoeba therefore needs to discover run-ids. The slice defers `--json` and tracks it with a GitHub issue. That is a reasonable deferral, but it makes the interface incomplete for that consumer until the issue lands. The frontmatter also lists `interfaces: []` even though the slice provides `list_run_summaries`, `item_eligibility` and `PipelineSource`. Consider listing them there.

### [NOTE] No NFR in the parent architecture applies to this path

The architecture states no latency or throughput target for listings. The slice sets its own target (under 1 s for a few hundred runs). It enforces the target through call-count bounds in the tests and verifies wall-clock time once in the walkthrough, which is appropriate.

### Run Digest

- Response length: 4582 chars
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
- Duration: 30.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
