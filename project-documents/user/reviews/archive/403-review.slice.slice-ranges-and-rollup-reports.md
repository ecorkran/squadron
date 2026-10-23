---
docType: review
layer: project
reviewType: slice
slice: slice-ranges-and-rollup-reports
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 2d98e1862d3df7838e7df75bbf1e128aa6712b29
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 266748
cachedTokens: 174589
cacheWriteTokens: 92151
completionTokens: 4722
durationSeconds: 40.7
costUsd: 0.434029
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Review findings dropped from the over-time report, and unresolved-slice reviews contradict the plan"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#Technical Scope"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice needs, and its cuts should be named"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#Technical Scope"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "Export measures under the live checkout's limits and exclusions, not the commit's"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#D5"
  - id: F004
    severity: note
    category: error-handling
    summary: "Export failure row for an unknown revision names no log signal"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:160"
  - id: F005
    severity: note
    category: error-handling
    summary: "Concurrent `slice_ranges` writes can lose a fast-forward landing permanently"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:166"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction and core principles preserved"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#Architecture"
---

# Review: slice — slice 403

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Review findings dropped from the over-time report, and unresolved-slice reviews contradict the plan

The slice plan entry for 403 assigns "over-time breakdowns across snapshots, audit runs and review records". The design excludes "Review findings over time in `report history` (#255)". `report history` therefore covers only two of the three sources. This is a deferral of assigned scope.

The design should either carry review counts per commit in `report history`, or get the plan entry amended to move that scope to #255.

D9 and criterion 10 also have `report slice` show source-document reviews for an unresolved slice. The slice plan says "Slices whose range never resolved appear at project level only, never under a guessed slice." D9 argues that `slice_index` is not a guess, which is reasonable. It is still a conscious departure from a plan success criterion. It should be recorded as such, or the plan criterion should be reworded.

### [CONCERN] Design is heavier than the slice needs, and its cuts should be named

The design adds a lot for a 4/5-effort slice:
- 13 new modules or splits.
- Seven report models and three enums.
- A new `slice-ranges` command.
- A `read_snapshot_config` split.
- A contract change that must propagate to 401.
- A 10-step walkthrough.
- A test matrix that includes a `git archive` timeout test.

Candidates to cut or defer:
- **`slice-ranges` as a separate command (D4):** `report slice` already persists ranges on first resolution, which is the architecture's requirement. The standalone command exists only to record fast-forward slices before the reflog expires. It could be a flag on `report slice`, or deferred until a fast-forward slice actually needs it. Squadron's walkthrough slices are mostly merge-commit landings.
- **Per-landing multi-landing machinery (D1):** it is justified by real data (172, 305, 940), so keep it. However, the `ProjectReport` slice table and the `HistoryReport` break markers add surface that nothing in the plan's success criteria requires.
- **Walkthrough:** steps 7, 9 and 10 repeat what the tests already assert.

Please state which of these is cut, or why each stays.

### [CONCERN] Export measures under the live checkout's limits and exclusions, not the commit's

The architecture says "Limits come from the project" and that exclusions "come from project config". It also says a config change between two commits "shows up as a rule-set change". D5 reads `.squadron.toml` limits, exclusions and timeout from the live checkout for every export. A slice that edits its own limits or exclusions therefore shows no change across its two boundary snapshots, because both are read under today's settings.

The `limits_changed` and `exclusions_changed` breaks (D7) can then fire only between an in-place snapshot taken earlier and an export. They cannot fire between two exports. That undercuts the "comparable over time" goal for the case where settings changed inside the slice.

The design picks live settings so both boundaries are consistent, and it records which settings each record used. It should state this limitation in the Risk Assessment section. Alternatively, it could read the config from the exported tree and record it per snapshot.

### [NOTE] Export failure row for an unknown revision names no log signal

The "unknown revision" row lists only "exit 1". Technical Requirements say every export failure has an ERROR asserted with `caplog`. Add the ERROR signal to that row. Criterion 11 also refers to "the Data Flow table", but the table is titled "Failure modes".

### [NOTE] Concurrent `slice_ranges` writes can lose a fast-forward landing permanently

The design accepts last-write-wins with no signal, as 400 does. A lost merge-commit landing is rediscovered later. A lost fast-forward landing is not, once its reflog has expired. This is documented and consistent with 400's stance, so I'm recording it only.

### [PASS] Boundaries, dependency direction and core principles preserved

- **Measure, never gate:** no pipeline hook is added (D4) and there is no composite score. A serialized-key test enforces the score rule.
- **Extend the 320 store:** `slice_ranges` is an optional sibling payload on `MetrologyRecord`, with `schema_version` unchanged.
- **Coarse records:** the design keeps one record per project.
- **Absent is not zero:** D6 gives absent with a reason for type counts and coverage at an export.
- **Comparability:** D7 and D8 compare only on full identity match, and the audit and review noise-floor states match the architecture. Severity scales are never mixed.
- **Dependency direction and boundaries:** report assembly takes the store, resolver and `ensure_snapshot` as arguments. Adapters are not imported by reports. The `AdapterContext.environment_root` contract change is minimal, and it comes with a conformance test and an export-equals-in-place test.
- **D3's refinement of the fork-to-merge diff:** the architecture already cites it, so it is consistent.

### Run Digest

- Response length: 6152 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 266748 / 174589 / 92151 / 4722 / not computed
- Duration: 40.7 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
