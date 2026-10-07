---
docType: review
layer: project
reviewType: slice
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: a0e745be023c248ecb8a51b3d0dc4a5d7bb26c87
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 29.7
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Slice matches the architecture's stated role for 199"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Overview"
  - id: F002
    severity: concern
    category: scope-creep
    summary: "Scope beyond the architecture: `sq runs wait` and `sq agents list`"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:32"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`sq runs wait` has no timeout default and cannot detect crashed runs"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:179"
  - id: F004
    severity: concern
    category: nfr
    summary: "The 1 s listing target is not an architecture NFR and is not enforced"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Special Considerations"
  - id: F005
    severity: concern
    category: boundaries
    summary: "Heavy refactor of 140/197-owned modules inside a listing slice"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Development Approach"
  - id: F006
    severity: note
    category: compatibility
    summary: "Removing `sq run --list` and the `sq list` rename are clean breaks"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:163"
  - id: F007
    severity: note
    category: integration
    summary: "Parent field and `--json` deferral"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:43"
---

# Review: slice — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Slice matches the architecture's stated role for 199

The architecture (180-arch lines 49–50) says 199 makes batch runs findable through `sq runs list`, built on `pipeline/run_listing.py`. It also says `sq pipelines list` replaces `sq run --list`. The slice delivers both with the same module name. It consumes 197's `BatchReport`, `ItemOutcome` and `FlagKind`, as the architecture describes. Squadron still only reports state and applies no decisions, so the listing stays read-only.

### [CONCERN] Scope beyond the architecture: `sq runs wait` and `sq agents list`

The architecture describes 199 as two listings. The slice also adds `sq runs wait` with a seven-value `WaitOutcome` exit-code contract (D13). It also renames `sq list` to `sq agents list` (D14), which changes three error messages and the slash command and skill bodies, with no alias.
- Neither is covered by the architecture's 199 paragraph or its Scope Boundaries.
- D14 breaks a user-facing command for a reason unrelated to pipeline intelligence.
- `wait` is a new blocking-poll I/O path and a new public exit-code interface.

The listing slice stays coherent, but the architecture should either record both additions or the slice should justify them as 199 scope. Update the architecture's 199 description (the 180-arch bullet at line 49) to name them. That would also settle whether Amoeba or other consumers rely on the `wait` exit codes.

### [CONCERN] `sq runs wait` has no timeout default and cannot detect crashed runs

Failure modes are enumerated well: timeout, not found, unreadable and unknown status each have an exit code and a WARNING log. Two cases are accepted rather than handled:
- A crashed process leaves the run at `running`, so an unbounded `wait` blocks forever. The only mitigation is help text.
- A caller such as an agent or script that omits `--timeout` hangs indefinitely.

For a command aimed at agents, "wait indefinitely" is a hang-by-default risk. The slice should state explicitly why this is acceptable. It could also add a cheap orphan signal, such as the run lock being free while the status is `running`, or a configured default bound. The unreadable retry policy (one retry, then `UNREADABLE`) is also unmotivated beyond the atomic-write argument.

### [CONCERN] The 1 s listing target is not an architecture NFR and is not enforced

The architecture states no NFR for this path, so nothing here needs restating. The slice sets its own target (under 1 s for a few hundred runs) but verifies it only by a manual walkthrough measurement. The call-count bounds test (D12) is a reasonable proxy. The slice should say plainly that the target is advisory. It should also note that `list_runs` still parses every state file with no cache, so cost grows linearly with run history.

### [CONCERN] Heavy refactor of 140/197-owned modules inside a listing slice

Step 1 modifies `state`, `batch_report`, `item_resume` and `loader`, owned by 140 and 197. The changes include a new `item_eligibility` module, a public `RESUMABLE_STATUSES`, a `PipelineSource` enum and a `first_unfinished_step_of` extraction. The motivation (no duplicated eligibility logic between the listing and resume) is sound and aligns with the DRY and single-source principles. The dependency direction is correct (`cli` → `run_views` → `run_listing` → pipeline modules, and `item_resume` → `item_eligibility`).
- The refactor is bundled with the new surface and rated effort 2/5, which looks low for four modules plus a command removal and rename.
- The slice does mitigate it by committing the refactor on its own and adding a parity test.

Consider whether the refactor should be split into its own slice or sub-task so the listing's risk does not depend on it.

### [NOTE] Removing `sq run --list` and the `sq list` rename are clean breaks

D8 and D14 justify skipping deprecation by pointing to the absence of known callers. This is consistent with the project's no-complexity principle, and the CHANGELOG entries record the change. Confirm that Amoeba and other out-of-process consumers do not call `sq list`. The slice states "no known users" for the agent lifecycle but cites no verification.

### [NOTE] Parent field and `--json` deferral

The architecture names Amoeba as the consumer of the resume interface (arch line 48). The slice defers `--json` for it and tracks the follow-up as a GitHub issue. That is acceptable, but the architecture's statement that `sq runs list` makes runs findable is satisfied for human and in-process callers only. An out-of-process Amoeba would have to scrape the table. The deferral is explicit and has a tracking step, so no action is needed beyond keeping that issue open.

### Run Digest

- Response length: 5740 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 29.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response

- **F002 (scope):** accepted. The 180 architecture's 199 bullet now names `sq runs wait` and the `sq <noun> list` grammar that motivates `sq agents list`.
- **F003 (`wait`):** partly accepted.
  - The retry was unmotivated, so it is dropped: atomic writes rule out torn reads, and the first unreadable poll now ends with `UNREADABLE`.
  - No default timeout: any value would be a guessed magic number, and agent callers are bounded by their own tool timeout. D13 now states this.
  - The run-lock orphan signal is unsound because the lock is per checkout and only mutating runs take it. Orphan detection needs a PID in run state, so it gets a follow-up issue.
- **F004 (perf target):** accepted. The target is marked advisory, and the linear growth in cost is stated.
- **F005 (refactor):** not split. The refactor is already its own behaviour-neutral commit, guarded by existing tests and the parity test. Effort is raised to 3/5.
- **F006:** verified. The Amoeba repo has no `sq list` or `sq run --list` calls, and D14 now cites this.
- **F007:** no action. The `--json` issue stays tracked.
