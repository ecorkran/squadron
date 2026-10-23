---
docType: review
layer: project
reviewType: slice
slice: adoption-baseline-command
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/404-slice.adoption-baseline-command.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 83769c3eb7148498fdbe793f7bea5f89b67687c4
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 174835
cachedTokens: 87406
cacheWriteTokens: 87423
completionTokens: 4403
durationSeconds: 36.5
costUsd: 0.403205
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#Architecture"
  - id: F002
    severity: pass
    category: requirements-coverage
    summary: "Scope report and config handling match the architecture and the slice plan"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D5"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D6"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "D3 runs a series of N and no separate \"baseline run\", which differs from the architecture's cost note"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D3"
  - id: F005
    severity: note
    category: usability
    summary: "Requiring a pinned model and leaving an analysis file behind both reduce the \"one command\" ease"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D2"
  - id: F006
    severity: note
    category: error-handling
    summary: "Interrupt row assumes a snapshot id exists"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#D6"
  - id: F007
    severity: note
    category: dependencies
    summary: "366 is a prerequisite in the body but not in the frontmatter dependencies"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md:7-10"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable; some text restates other documents"
    location: "project-documents/user/slices/404-slice.adoption-baseline-command.md#Consumes from Other Slices"
---

# Review: slice — slice 404

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency direction match the architecture

The slice reuses 400's snapshot code and 323's audit harness unchanged. It adds no record type, no store change and no new config key, which matches "Extend the 320 store, don't fork it". The library modules (`metrology/baseline.py`, `metrology/audit_series.py`) don't import Typer or Rich, and the CLI shell sits in its own module, so dependencies run CLI to library to existing slices. The command only writes measurements and nothing reads them to gate, which fits "Measure, never gate". Each record is keyed on `ProjectId` and commit SHA, and a dirty tree is refused, as the architecture's "A snapshot measures a commit" principle requires.

### [PASS] Scope report and config handling match the architecture and the slice plan

The scope report covers what the architecture and the slice plan require. It prints the file and byte counts after exclusions and the run count before any spend, and it is informational with no prompt. The file set comes from the same `resolve_files` and `effective_exclusions` calls the snapshot uses, so the report can't disagree with the snapshot, and a success criterion tests this. It also states that the audit agent isn't limited by the exclusions, which keeps the spend estimate honest. Profile and model come from 320's existing config keys. A missing model fails explicitly before anything runs, as the slice plan's success criteria require.

### [PASS] Failure modes are enumerated for each new I/O path

D6's table covers snapshot failure, audit timeout, run failure, rate limit, HEAD moving mid-series, interrupt, floor write failure and too few runs. Each row has a handling strategy, an observable signal and an exit code. The Technical Requirements name tests that assert the signals for the timeout, store-error and interrupt cases. Preflight failures are shown to make no LLM call, because the fake audit callable is asserted never to have been called.

### [NOTE] D3 runs a series of N and no separate "baseline run", which differs from the architecture's cost note

The architecture's Baseline scope report paragraph says "three audit runs plus the baseline run". D3 runs only the N independent variance runs, because `baseline_report` already reports the newest run in the group beside its floor. The slice plan's criterion ("an audit run and an audit noise floor") is still met. The reasoning is explicit and saves the cost of a fourth full audit. The architecture's note is exploratory, so nothing needs to change. The architecture could be amended later so the two documents agree.

### [NOTE] Requiring a pinned model and leaving an analysis file behind both reduce the "one command" ease

The architecture goal is "cheap to start measuring" with no edits to the project's config or code. Two decisions add friction, and both are documented and defensible:
- **Pinned model.** A first run with no `metrology.audit_model` set fails once, because an unpinned model would make the floor non-comparable. The fix is a user-level `sq config set`, not a project edit.
- **Analysis file.** The audit leaves an untracked analysis file, which blocks the next snapshot or baseline until it is removed or committed (D6). The summary names the file so this is visible.

No change is needed. If adopters trip on either, 440's offer text should cover it.

### [NOTE] Interrupt row assumes a snapshot id exists

The interrupt row says the output names "the snapshot id, runs completed, and the recovery command". A Ctrl-C during the snapshot step happens before any snapshot id exists. The slice also doesn't say what the output should be in that case. The wording should cover "no snapshot yet; nothing spent" for that window. This is small, and the exit code of 130 is already specified.

### [NOTE] 366 is a prerequisite in the body but not in the frontmatter dependencies

The Prerequisites section lists 366 (the probe and `BaselineReport`), but the frontmatter `dependencies` lists only 400 and 323. The dependency is visible in the body, so this is a metadata inconsistency and not a hidden coupling. Add 366 to the frontmatter.

### [NOTE] Proportionality is acceptable; some text restates other documents

Extracting the series loop, moving the printers into a shared module and adding the observer protocol all serve DRY, and they avoid importing private names. They fit the 2/5 effort. The paragraph in "Consumes from Other Slices" that restates how 401 and 403 may change `take_snapshot` and `read_snapshot_config` is speculative. It could shrink to one line saying the scope set must stay the snapshot's own (D5), which is already the contract. The long Verification Walkthrough is optional trimming and not a defect.

### Run Digest

- Response length: 5672 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 174835 / 87406 / 87423 / 4403 / not computed
- Duration: 36.5 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Applied to the design on 20261023.

- **Interrupt row (NOTE): fixed.** An interrupt before any snapshot exists prints one line saying nothing was recorded or spent.
- **366 in frontmatter (NOTE): fixed.**
- **D3, ease of use, proportionality (NOTEs):** no change.
