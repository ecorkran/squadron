---
docType: review
layer: project
reviewType: slice
slice: adoption-baseline-command
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/404-slice.adoption-baseline-command.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 2359ffcec3b89f20fe7152be71c5f10400710ba1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 94301
cachedTokens: 11266
cacheWriteTokens: 83031
completionTokens: 4193
durationSeconds: 37.8
costUsd: 0.375917
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the adoption-baseline capability and architectural principles"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#Overview"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#Component-Structure"
  - id: F003
    severity: note
    category: scope
    summary: "Deliberate deviation: no separate \"baseline run\""
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D3"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes of the audit series are only partly enumerated"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D6"
  - id: F005
    severity: concern
    category: integration
    summary: "A successful baseline leaves the tree dirty and blocks the next snapshot"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D6"
  - id: F006
    severity: concern
    category: dependencies
    summary: "Undeclared dependency on slice 403"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#Consumes-from-Other-Slices"
  - id: F007
    severity: note
    category: scope
    summary: "Scope report states a number that is not what the audit reads"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D5"
  - id: F008
    severity: note
    category: integration
    summary: "Probe contract meaning line carries an unresolved placeholder"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D7"
---

# Review: slice — slice 404

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the adoption-baseline capability and architectural principles

The command takes a snapshot of a clean HEAD, then runs 323's variance series and writes the noise floor. It prints the file and byte count after exclusions and the run count before any spend, as a report with no gate. This matches the architecture's "Adoption baseline" capability and "Baseline scope report" consideration. It adds no record type, store change or config key, which fits "Extend the 320 store, don't fork it". It reuses 320's audit profile and model config. It measures only and gates nothing. The snapshot's clean-tree rule is left untouched.

### [PASS] Layering and dependency direction

`metrology/baseline.py` and `metrology/audit_series.py` are library code with no Typer or Rich imports. The CLI shell depends on them, and output goes through an observer, so dependencies run CLI → library. Both `audit variance` and `baseline` call the single extracted series loop, which avoids duplicating it. Moving the printers into a shared module removes imports of private names. For an effort-2/5 slice this refactor is justified by DRY, so I would not cut it.

### [NOTE] Deliberate deviation: no separate "baseline run"

The architecture's cost note counts "three audit runs plus the baseline run". D3 drops the fourth run. It argues that the floor group already reports the newest run and that a fourth audit adds cost without information. The reasoning is sound and lowers spend. The slice records the deviation explicitly, so the architecture's cost note can be corrected to match.

### [CONCERN] Failure modes of the audit series are only partly enumerated

The series is the new long-running, spend-bearing I/O path. The design covers a failed run, a rate-limit stop, too few runs, a moved HEAD and snapshot failure. It does not say what happens in these cases:
- **Hung or timed-out run.** The design never says whether `run_audit`'s timeout (if it has one) is counted as a failed run, or where that timeout comes from.
- **Interrupt mid-series.** A Ctrl-C or killed process after the snapshot and some runs leaves records behind. D6's "keeps what was measured" covers failure, but not an interrupt, and no recovery message is printed.
- **Floor write failure.** `store.write_noise_floor` can fail after the runs are spent. D6 lists store failure only for the snapshot.

The project's failure-mode rule needs each of these answered explicitly and made observable. Add a short table that maps each mode to its handling (counted failed run, exit code, message), and add a test asserting the observable signal for the timeout and floor-write cases.

### [CONCERN] A successful baseline leaves the tree dirty and blocks the next snapshot

D6 and the "State Management" section accept that the audit's untracked analysis file stays in the repository. Because the snapshot refuses a dirty tree, every later `sq metrology snapshot`, and 403's on-demand boundary snapshots, will be refused until the user removes or commits that file. That works against the architecture's goal that every later slice is measured against the baseline. The only mitigation is a line in the docs. The `Next:` line in the output shape names only the report command. The summary should name the analysis file and say it must be removed or committed before the next measurement. The design should also state which of 323's behaviors lets runs 2..N pass `require_clean=True` once run 1 has written the file, since the series depends on that.

### [CONCERN] Undeclared dependency on slice 403

The frontmatter lists dependencies 400 and 323, and "Prerequisites" lists 400, 323 and 366. "Consumes" relies on 401's metric output and on 403's `read_snapshot_config` split leaving `take_snapshot`'s signature unchanged. 403's design is also still under review, per recent commits. The design calls `take_snapshot` and the snapshot preflight "exactly as `sq metrology snapshot` calls them". It should state whether it needs 403 landed first or only needs the signature to stay stable. If it is the latter, name that as an interface contract, not an implicit dependency.

### [NOTE] Scope report states a number that is not what the audit reads

The file and byte count follows the snapshot's exclusions, but the audit agent reads the whole repository. D5 says so in the printed report, which handles the mismatch honestly. The architecture's stated purpose for the count is to inform spend, so the caveat is the right treatment.

### [NOTE] Probe contract meaning line carries an unresolved placeholder

The release version is "added to that line when the release is cut". That leaves a known follow-up outside the slice's tasks. Either drop the version from the line or add a release-time step so the contract does not stay incomplete.

### Run Digest

- Response length: 5949 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 94301 / 11266 / 83031 / 4193 / not computed
- Duration: 37.8 s
- Cost: $0.38 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
