---
docType: review
layer: project
reviewType: tasks
slice: sq-onboard
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/440-tasks.sq-onboard.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261026
dateUpdated: 20261026
reviewedSha: 10441c6d47a2027cc46c9c9fcd9349b824809c3e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 195023
cachedTokens: 95131
cacheWriteTokens: 99886
completionTokens: 4647
durationSeconds: 45.1
costUsd: 0.456269
costBasis: provider
runId: run-20261026-p5-9ba2586e
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:48-293"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit checkpoints are sound"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:59-278"
  - id: F003
    severity: concern
    category: testability
    summary: "The CLI tests have no specified seam for the adoption client"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:226-233"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Fixture and test volume goes beyond what the success criteria need"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:51-54"
  - id: F005
    severity: concern
    category: granularity
    summary: "Several tiny implementation/test pairs could be merged"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:92-101"
  - id: F006
    severity: concern
    category: proportionality
    summary: "T30 duplicates checks already in each task's success criteria"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:288-293"
  - id: F007
    severity: note
    category: clarity
    summary: "T26's success criterion is vague, and T29 relies on a line number"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:264"
  - id: F008
    severity: note
    category: nfr
    summary: "Load testing and CI wiring do not apply"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md"
---

# Review: tasks — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

Each Functional, Technical and Integration criterion in the slice maps to a task:
- **No-writes check:** T23 item 3.
- **D1 rows, including the resumed run:** T19.
- **D7 report-version, outcome and envelope errors:** T11, T5 and T23.
- **D7 timeout:** T3 and T23.
- **D8 `register`/`decline`/`prompt` cases, including the second `register` after `ok: false`:** T25.
- **D4 monorepo root:** T23 item 4.
- **D11:** T7 and T9.
- **`sq probe` removed:** T15.
- **Single definitions, file size and lint/type gates:** T30.

The live-run Integration criterion cannot be produced by this list. Context Summary line 40 states it as a precondition, so it is handled explicitly.

### [PASS] Sequencing and commit checkpoints are sound

I found no circular dependencies:
- **Order:** the cf client (T2–T9) comes first, then the adoption client (T10–T13), the probe move (T14–T15), the onboard core (T16–T21), the CLI (T22–T25) and the agent files (T26–T28).
- **Probe move:** T14 leaves the old probe in place so `sq probe` still builds, and T15 deletes it. I checked that `tests/probe/fixtures/installed_plugins.json` is used only by `test_surfaces.py`, which moves in T14, so nothing is left broken between those two commits.
- **Commits:** each implementation and test pair ends in a commit, spread through the list rather than batched at the end.

### [CONCERN] The CLI tests have no specified seam for the adoption client

T22 creates the Typer sub-app, but it doesn't say how the command obtains its `CfAdoptionClient`. T23 then assumes a fake can be injected: "adoption client replaced by a fake (or a fake `cf` on `PATH`)".

Without a named factory or dependency seam in T22, the implementer must guess. The likely result is monkeypatching internals, which the project's DIP rule flags. Add one line to T22 naming a client factory that the report command and the three subcommands share. T24's "share `--path` validation and error handling" can use the same seam.

### [CONCERN] Fixture and test volume goes beyond what the success criteria need

The slice requires "the error envelope from each command". T1 records five separate `detect-error-{code}.json` files, one per D5 code, and T11 item 2 parametrizes over all of them. The parser is generic (`_checked_report` in T10), so extra codes exercise the same path.

Cut this to one envelope fixture for detect (`path-not-found`) and one for init (`init-error-worktree`). Both are already needed. The fixtures can be regenerated from real cf output anyway, as the slice's Risk section says.

### [CONCERN] Several tiny implementation/test pairs could be merged

The slice is rated Effort 3/5 but has 30 tasks. Three pairs are small enough to merge into one task with one commit each:
- **T6 + T7:** `SliceEntry.retroactive` and its test, both Effort 1.
- **T16 + T17:** `newest_comprehension` and its test, Effort 2 and 1.
- **T4 + T5:** `run_report` and its tests.

Merging keeps the test-with pattern and removes three separate task entries and commit gates. T2/T3 could also merge into T4/T5, since all of them change the same two files.

### [CONCERN] T30 duplicates checks already in each task's success criteria

Every earlier task already requires `ruff format`, `ruff check`, `pyright` and the touched tests, and T14 and T15 require the full suite. T30's lint, type and size checks repeat them.

The single-definition and no-artifact-name greps are worth keeping because no earlier task owns them. Reduce T30 to those two greps, which are the slice's Technical Requirements. Alternatively, attach them to T24 or T29 and drop T30.

### [NOTE] T26's success criterion is vague, and T29 relies on a line number

T26's SC, "the file reads `next.step` values that exist in `OnboardStep`", has no check of its own; T28 is the only place it is tested. Point the SC at T28, or state it as "each `OnboardStep` value appears". T29 also cites "README.md line 404", and a line number goes stale. Locate the sentence by its `sq probe --json` text instead.

### [NOTE] Load testing and CI wiring do not apply

The slice states no NFR, so no `tests/load/` task or CI gating task is needed.

### Run Digest

- Response length: 5205 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 195023 / 95131 / 99886 / 4647 / not computed
- Duration: 45.1 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
