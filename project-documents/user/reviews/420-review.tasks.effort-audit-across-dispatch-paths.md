---
docType: review
layer: project
reviewType: tasks
slice: effort-audit-across-dispatch-paths
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261105
dateUpdated: 20261105
reviewedSha: 1a4e32cdbddd109c3ae37e62eee34feb5968dc4e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
effort: xhigh
turns: 20
promptTokens: 666343
cachedTokens: 533845
cacheWriteTokens: 132484
completionTokens: 41215
durationSeconds: 204.3
costUsd: 0.150295
costBasis: provider
runId: run-20261105-p5-03049c49
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Dependencies and sequencing hold"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F003
    severity: pass
    category: proportionality
    summary: "Test-with pattern and proportion are sound"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F004
    severity: concern
    category: coverage
    summary: "Task 3 omits the outer `ProviderError` handler"
    location: "src/squadron/pipeline/actions/dispatch.py:439"
  - id: F005
    severity: concern
    category: design-consistency
    summary: "Task 3 resolves a design contradiction by editing the design mid-implementation"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md"
  - id: F006
    severity: concern
    category: clarity
    summary: "Task 13 has no bucket for session-effort callers"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F007
    severity: concern
    category: scope
    summary: "Task 12 adds an unnamed module and a file split the design does not list"
    location: "src/squadron/replay/report.py:51"
  - id: F008
    severity: concern
    category: design-consistency
    summary: "Judge tables are keyed on alias, against D6's identity rule"
    location: "src/squadron/metrology/replay_models.py:73"
  - id: F009
    severity: note
    category: clarity
    summary: "Task 8 does not name the `judge_residue_core` module"
    location: "src/squadron/review/addressed/judge.py:71"
  - id: F010
    severity: note
    category: coverage
    summary: "Path 12 has no named test in Task 13"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F011
    severity: note
    category: testing
    summary: "The load-test exemption is reasoned"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F012
    severity: note
    category: commit-cadence
    summary: "Commit markers and messages do not line up"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
  - id: F013
    severity: note
    category: process
    summary: "Task 1 names the target without a read step"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md"
---

# Review: tasks — slice 420

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion has a task

FR1 maps to Task 13. FR2 maps to Task 6. FR3 maps to Task 7. FR4 maps to Task 8. FR5 maps to Task 9. FR6 maps to Tasks 3–5 (stamp) and 10 (replay and stats reads). FR7 maps to Tasks 11–12. The technical requirements map to per-path tests (Tasks 3–10, 13), the capability gate in both helpers (Task 2), the compaction `effort=None` updates (Task 6), the validation gate (Task 15), and the CHANGELOG (Task 14). Walkthrough steps 1–6 map to Tasks 13 and 15.

### [PASS] Dependencies and sequencing hold

Task 2 (stamp and readers) precedes its consumers in Tasks 3, 4, 5, 6 and 10. Task 11 precedes Task 12, which uses its fields. Task 13 follows the tests it indexes. The prerequisites named in the Context Summary exist: `EFFORT_SENT_KEY`, `note_effort_sent`, `effort_sent_by_profile`, `read_effort_sent` and `effort_for_session` are in `src/squadron/pipeline/usage_capture.py`, and `resolve_full` is in `src/squadron/pipeline/resolver.py:179`.

### [PASS] Test-with pattern and proportion are sound

Each implementation task carries its own tests, and there is no separate test-only task apart from the inventory guard. Fifteen tasks in one file is proportionate for twelve dispatch-path changes. The nine `**Commit**:` markers sit at tested points.

### [CONCERN] Task 3 omits the outer `ProviderError` handler

Task 3 lists the outer `except Exception` as unstamped and asks for a comment there. `DispatchAction.execute` also has `except ProviderError as exc: return self._provider_failure(context, exc, None, None)` at line 439, which carries no telemetry and no effort. Task 3 neither stamps it nor excludes it. Add it to the not-stamped list with the same comment, or state why it cannot run after resolution.

### [CONCERN] Task 3 resolves a design contradiction by editing the design mid-implementation

D5 says the stamp goes on "every action result built after the model is resolved". It then excludes the outer `except Exception`, which runs after resolution if `_dispatch` raises late. FR6 says "a dispatch that fails before any telemetry still carries `effort_sent`". Task 3 keeps FR6 and tells the implementer to rewrite D5's sentence on the slice branch. Fix the design before branching. Narrow D5 and FR6 to "every result built where the effort is known", and name the outer handlers as the exclusion.

### [CONCERN] Task 13 has no bucket for session-effort callers

The classification table allows only `SENDS_ALIAS_EFFORT` and `NO_ALIAS`. The task also says the `open_pipeline_session` callers (`run_session.py`, `executor.py`) "send the session effort". That fits neither bucket, so the implementer must either mislabel them or see the test fail on its first run. Add a third value, such as `SENDS_SESSION_EFFORT`, and say which test proves it.

### [CONCERN] Task 12 adds an unnamed module and a file split the design does not list

`report.py` is 311 lines, and `config_label` starts at line 51. Task 12 says to move `config_label` "(and any further cohesive block needed)" to "a new sibling module". It names neither the module nor the other block. The design's Components list has no new module, and no success criterion sets a file length. The 300-line goal is a CLAUDE.md "where practical" guideline. Decide the module and the exact move in the design, then list it in Components changed.

### [CONCERN] Judge tables are keyed on alias, against D6's identity rule

`JudgeRef` carries `alias: str`, and D3 builds one judge table per `JudgeRef`. D6 and the Integration Points say a config's identity is what went on the wire, not the alias name, and they state the rule generally. So two judge aliases that send the same model, effort and prompt still yield two tables. Task 7 does not address this, and Task 12 covers producers only. Decide in the design whether D6 covers judges. If it does, add a step; if not, say so in D6.

### [NOTE] Task 8 does not name the `judge_residue_core` module

Task 8 says "grep for its module". The function is at `src/squadron/review/addressed/judge.py:71`. Name the file so the implementer does not have to search for it.

### [NOTE] Path 12 has no named test in Task 13

Task 13 names tests for paths 9 and 10 and asks for a map of paths 1–12. Path 12, the replay producer read, is covered only by Task 10's tests, which Task 13 does not name. The map is also a comment, so nothing fails if it goes stale. That is acceptable, but say so.

### [NOTE] The load-test exemption is reasoned

The Context Summary says the load tier does not apply. The design restates no NFR, so the criteria do not require a `tests/load/` task. `python.md` does require a load test for code on network paths, and `dispatch.py` sits on the request path. The exemption holds because the changes add no I/O. The PM may want to confirm it.

### [NOTE] Commit markers and messages do not line up

Task 14 (CHANGELOG and issue) has no marker. Its work lands in the commit marked after Task 15 (full validation), whose message "docs: add effort audit changelog entry" describes only the CHANGELOG. Move the marker to Task 14, or rewrite the message. Task 2 is `feat:` while the other markers are `fix:`. Pick one rule for the slice's commit types.

### [NOTE] Task 1 names the target without a read step

Task 1 says "Create the slice branch from the target" without an explicit `cf config get git.integration_branch` read. The Context Summary states the rule. Add the read to Task 1 so it is an executable step.

### Run Digest

- Response length: 8125 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 666343 / 533845 / 132484 / 41215 / not computed
- Duration: 204.3 s
- Cost: $0.15 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Resolution

- [pass] Every success criterion has a task: no change.
- [pass] Dependencies and sequencing hold: no change.
- [pass] Test-with pattern and proportion are sound: no change.
- [concern] Task 3 omits the outer `ProviderError` handler: fixed. Task 3's "Not stamped" item now names the outer `except ProviderError` beside `except Exception`, and says to comment both.
- [concern] Task 3 edits the design mid-implementation: fixed. The design's D5 was already edited during planning; Task 3 now says D5 states the limit and has no design-edit step.
- [concern] Task 13 has no bucket for session-effort callers: fixed. The table has a third class, `SENDS_SESSION_EFFORT`, used for the `open_pipeline_session` callers.
- [concern] Task 12 adds an unnamed module and an unlisted split: fixed. The module is named `replay/config_label.py` and added to the design's Components changed list.
- [concern] Judge tables are keyed on alias, against D6: rejected. D6 governs producer configs. Judge tables follow D3, one table per distinct `JudgeRef` (alias, model, prompt hash, and now effort sent), which is the intended judge identity.
- [note] Task 8 does not name the `judge_residue_core` module: fixed. Task 8 names `review/addressed/judge.py`.
- [note] Path 12 has no named test in Task 13: fixed. Task 13 names the Task 10 tests in `test_outcome.py` and `test_producer_units.py`.
- [note] The load-test exemption is reasoned: no change.
- [note] Commit markers and messages do not line up: fixed. The Task 11–12 marker message now names the config fields and the grouping. Validation is now Task 14 with no marker; the CHANGELOG and issue task is Task 15 and carries the final marker, whose message matches it.
- [note] Task 1 names the target without a read step: fixed. Task 1 reads `cf config get git.integration_branch` (or `main` if empty) before creating the branch.
