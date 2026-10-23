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
reviewedSha: 90725f6dc41e477bd72207ca3c3fd3aa5aa73514
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 185762
cachedTokens: 91669
cacheWriteTokens: 94087
completionTokens: 6307
durationSeconds: 53.9
costUsd: 0.449327
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Git failures in range resolution are reported as ordinary \"unresolved\" reasons at INFO"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:164"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Concurrent `slice_ranges` writes can silently lose landings"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:166"
  - id: F003
    severity: concern
    category: dependencies
    summary: "Cross-slice ordering with 401 is conditional and hidden from the dependency graph"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:74"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "Exports use the live checkout's limits and exclusions, so comparability claims are weaker than the architecture and criterion 7 imply"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:214"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The design carries scope that can be cut or deferred"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#Component Structure"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Alignment with architecture principles and layer boundaries"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#Technical Decisions"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Failure-mode enumeration for new I/O paths"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:153-167"
  - id: F008
    severity: note
    category: uncategorized
    summary: "Dependency on unimplemented 402 is stated clearly"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:72"
---

# Review: slice — slice 403

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Git failures in range resolution are reported as ordinary "unresolved" reasons at INFO

The failure table says a `None` from a reflog read or merge search means "this path can't answer". The resolver moves to the next path, and if every path fails the slice gets an unresolved reason logged at INFO. `RangeUnresolvedReason` (data-flow lines 114-119) has no member for "git call failed or timed out". A hung or failing `git log --merges` falls through to the fast-forward path, and the output then says `no_landing` or `reflog_unavailable`.

That is indistinguishable from a slice that never landed. The project's failure-mode rule (`.claude/rules/review-code.md`) requires failures to be observable at WARNING or above. Nothing in this design distinguishes a transient git error from a real absence.

The slice's own risk section says a wrong or missing range is costly, because persistence is permanent. Add an explicit git-error reason, or a WARNING when any path returned `None`. Add a `caplog` assertion for it to the Technical Requirements.

### [CONCERN] Concurrent `slice_ranges` writes can silently lose landings

The failure table lists the concurrent-write case with "Signal: None". The last write wins and a fast-forward landing can be lost for good once its reflog expires. This is the one place where the slice's central goal, durable ranges, can fail without any signal. The doc's reasoning that 400 also does not support concurrency is fair.

The cost to fix is small. `record_slice_ranges` could re-read the record just before it writes and log a WARNING if the stored landings changed since the first read. At minimum, the doc should say plainly that it accepts this unobserved loss. As written, "Every failure mode behaves as stated" (criterion 11) is satisfied without any observable behavior here.

### [CONCERN] Cross-slice ordering with 401 is conditional and hidden from the dependency graph

The frontmatter lists `dependencies: [400, 402]`, and the slice plan matches. The Prerequisites text then says 401 is "not a prerequisite". The `environment_root` rule is a contract change that 401's code must obey, though. The doc says "If 401 is implemented after 403, it inherits the rule. If before, 403 updates whatever of 401's code reads `ctx.repo_root`."

The scope of 403's work therefore depends on an ordering that is not pinned down, and the files that might change are not named. That is a hidden dependency. The plan lists 401 before 403, so the "401 first" case is the likely one.

Resolve it one of two ways:
- State that 401 lands first, and list the 401 adapter modules that move to `environment_root` as in-scope work for 403.
- Add 401 to the dependency list and have the implementation order say so.

### [CONCERN] Exports use the live checkout's limits and exclusions, so comparability claims are weaker than the architecture and criterion 7 imply

The architecture says "Limits come from the project" and that comparability flags catch differences in tool, rule set, environment and exclusions. D5 reads limits, exclusions and the tool timeout from the live checkout for every export. A slice that changes its own limits or exclusions therefore shows no `limits_changed` or `exclusions_changed` break between its two exported boundaries. The Risk section acknowledges this, but it has no mitigation.

Criterion 7 and walkthrough step 6 present these breaks as working. In practice they only fire against a snapshot taken earlier under other settings. Two things would close the gap:
- Say in `report slice` output when either boundary was exported under live settings. The record already states the settings it used, so the report can surface that.
- Narrow criterion 7 to match what the design can deliver.

### [CONCERN] The design carries scope that can be cut or deferred

The slice plan assigns durable ranges, export, comparability, three reports, noise-floor display and project-level attribution of unresolved slices. All of those are needed. The design also adds mechanisms the plan's criteria do not require:
- **`limits_changed` partial marking (D7).** It marks only the over-limit figures and still diffs the distributions. Marking the whole snapshot level, as `exclusions_changed` does, would meet "flag the rest" with one rule instead of two.
- **`boundaries.py` as its own module.** It holds one function, `ensure_snapshot`. It could live in `take.py` or `slice_report.py`.
- **`report history` extras.** Review findings are placed per landing on the row of the landing's `after_sha`. A closing count of off-line snapshots is also shown. A plain per-commit table with a project-level review line would satisfy "trends become visible".
- **Mapping of write-time versus read-side-mapped counts as separate columns, plus the `other` share.** The plan does not require this. It is cheap, but 402 already labels the records, so reports could carry the label through without extra aggregation code.
- **Seven-plus report-package modules and a test list of about 12 export and resolver cases.** This is a large design. Fold the report models and `compare.py` where they are tightly coupled, and keep the test list to cases that exercise distinct behavior.

None of these block progress. Pick which to cut or defer to keep the effort inside the planned 4/5.

### [PASS] Alignment with architecture principles and layer boundaries

- **Measure, never gate.** No gate or pipeline hook is added, and there is no composite score. A test asserts no serialized key contains `score` (D8).
- **Store principles.** `slice_ranges` is an optional sibling payload on `MetrologyRecord`, with `schema_version` unchanged and one coarse record per project.
- **Absent is not zero.** Absence reasons are carried for type counts and coverage at an export (D6).
- **Closed enums.** `LandingMethod`, `RangeUnresolvedReason` and `ComparabilityBreak` are enums.
- **Severity scales.** Review and audit severities stay on their own scales.
- **Architecture refinements.** D3's before/after refinement is already anticipated by the architecture, and D2's refusal of the `main` fallback is justified.
- **Scope of writes.** Reports write only snapshots and ranges, and say so in the help text.

### [PASS] Failure-mode enumeration for new I/O paths

The table covers these I/O paths:
- `git archive` and `rev-parse` failing.
- `git archive` timeout.
- Extraction `OSError`.
- Symlink creation failure.
- An unknown revision.
- A refused archive member.
- A tool hang.
- A boundary snapshot failure.
- A stored commit that no longer exists.
- A store write failure.

Each has an explicit handling strategy and a stated signal, and the Technical Requirements assert them with `caplog`. The two exceptions are the quiet git-error and concurrent-write paths raised above.

### [NOTE] Dependency on unimplemented 402 is stated clearly

The doc states that 403 cannot be implemented before 402 lands. That matches the slice plan's ordering, and no change is needed. The report layer takes the store and `ensure_snapshot` as arguments, so tests can use fakes against 402's contract in the meantime.

### Run Digest

- Response length: 8513 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 185762 / 91669 / 94087 / 6307 / not computed
- Duration: 53.9 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Applied to the design on 20261023.

- **Git failures reported as unresolved at INFO (CONCERN): fixed.** A `None` from the merge search or reflog read now gives a `GIT_ERROR` reason, logged at WARNING, with nothing persisted. `NO_LANDING` and the other reasons mean git answered, and stay at INFO. A `caplog` test with a faked `run_git` is required.
- **Concurrent `slice_ranges` writes (CONCERN): fixed.** The command re-reads the record just before writing and merges into that copy, so both runs' landings survive. A WARNING fires when the stored record changed since the start read. The remaining window is the gap between the re-read and the atomic write. A test is required.
- **Hidden dependency on 401 (CONCERN): fixed.** 401 is in the frontmatter dependencies and Prerequisites. The 401 modules are named, and none of them moves to `environment_root`.
- **Export settings (CONCERN): fixed.** D7 says `settings_changed` can fire only against a snapshot taken under other settings. `report slice` prints each boundary's limits and exclusions. Criterion 7 and the Risk Assessment are narrowed to match.
- **Scope to cut (CONCERN): applied.**
  - Partial `limits_changed`: replaced by one `settings_changed` break for limits or exclusions.
  - `boundaries.py`: folded into `slice_report.py`.
  - `report history`: snapshots only, with break markers and the off-line count. Audits and reviews stay in `report slice` and `report project`.
  - Write-time and read-side columns: the header line carries both totals and category rows show one count. The `other` share stays, because it is the architecture's vocabulary-fit evidence.
  - Module count and the export and resolver test list: left. Each module and test covers distinct behavior.
