---
docType: review
layer: project
reviewType: code
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: c85beb2d702dc43fc194085d0dae47286cb805c2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 79339
cachedTokens: 3232
cacheWriteTokens: 76105
completionTokens: 3555
durationSeconds: 34.9
costUsd: 0.346213
costBasis: provider
squadronVersion: 0.23.2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Cost cap fails open on an unreadable usage record"
    location: "src/squadron/pipeline/run_spend.py#RunSpend.add"
  - id: F002
    severity: concern
    category: testing
    summary: "No load or concurrency test for the shared `RunSpend` tally"
    location: "tests/pipeline/test_executor_cost_cap.py"
  - id: F003
    severity: concern
    category: design
    summary: "Tests patch private methods to isolate behaviour"
    location: "tests/conftest.py:138-150"
  - id: F004
    severity: note
    category: style
    summary: "Redundant and loosely typed checks in turn handling"
    location: "src/squadron/pipeline/sdk_turns.py#DispatchTurns.collect"
  - id: F005
    severity: note
    category: style
    summary: "`assert isinstance` used for type narrowing in an event action"
    location: "src/squadron/events/builtin/blocked_tasks.py#BlockedTasksAction.execute"
  - id: F006
    severity: note
    category: design
    summary: "Resume flag lifecycle relies on mutate-and-pop of the shared params dict"
    location: "src/squadron/pipeline/executor.py:625-657"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Parser, config validation and failure-kind plumbing"
    location: "src/squadron/pr/tasks.py#parse_blocked_markers"
---

# Review: code — slice 947

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Cost cap fails open on an unreadable usage record

`add()` catches `ValueError` from a malformed usage record, logs it with `logger.exception`, and adds $0. The cap is a spend-safety control. A persistently malformed record, for example after a schema change, silently disables it, and the only signal is an ERROR log line. The posture matches `usage-stamp` and the docstring explains it, so this is defensible. It still conflicts with the project's "fail explicitly" principle. Consider failing the action with a distinct `FailureKind`, or at least surfacing the undercount in the run summary, when a cap is configured. A cap of `None` can keep the current behaviour.

### [CONCERN] No load or concurrency test for the shared `RunSpend` tally

`RunSpend` is shared by concurrent `fan_out` branches, which are on the concurrency path. The Python rules call for at least one load-tier test (`tests/load/`) on these paths. The existing fan_out test covers correctness for 3 branches. It does not cover a realistic configuration or the overshoot bound, which the config docs state as "one action per branch". The "pure bookkeeping, no awaiting" safety argument in the module docstring holds only while `add` stays synchronous. A test asserting that would guard it.

### [CONCERN] Tests patch private methods to isolate behaviour

The autouse fixture patches `BlockedTasksAction._read_markers`, and `test_blocked_pause.py` patches `DispatchBranchWorkAction._count_work`. The project's DIP rule treats the need to monkeypatch internals as a symptom of an inverted dependency graph. Injecting a marker reader or task-path provider, or using the existing `cf_client` fake, would remove the global autouse stub. The stub currently applies to every test in the suite, so a regression in real task-file reading could be masked in unrelated tests.

### [NOTE] Redundant and loosely typed checks in turn handling

`isinstance(msg, SystemMessage) and is_session_state_frame(msg)` repeats the `isinstance` check already inside `is_session_state_frame`. It is only needed for type narrowing, so a `TypeGuard` return type on the helper would remove both it and the `# type: ignore[attr-defined]` in `scripts/probes/background_shell.py:67`. `SDKExecutionSession._collect_turns` keeps growing and is now well past the ~50-line guideline, so it is worth extracting a helper.

### [NOTE] `assert isinstance` used for type narrowing in an event action

A bare `assert` is stripped under `python -O`. If this matches the sibling event actions' idiom it is fine. Otherwise, raise `TypeError` explicitly.

### [NOTE] Resume flag lifecycle relies on mutate-and-pop of the shared params dict

`RESUMED_FROM_HANDOFF` is inserted into `merged_params` and popped after the step. It is protected as a reserved param and has test coverage. An exception thrown between the insert and the pop would leave the flag set for later steps, although the exception also ends the run. Passing it only into that step's params copy would be more robust.

### [PASS] Parser, config validation and failure-kind plumbing

The BLOCKED regex is lenient about indent, quote marks, bullets, emphasis and dash style. It rejects look-alike prose, and the tests include the real amoeba line. The cap config is validated at run start with a key-naming error, covering `0`, `inf`, `nan` and `bool`. `FailureKind.COST_CAP` is mapped in replay, and a test enforces that every kind has a replay class. Blocking I/O in `blocked_tasks` runs off the event loop via `asyncio.to_thread`, and each failure path logs at WARNING or above and has a test.

### Run Digest

- Response length: 4422 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 79339 / 3232 / 76105 / 3555 / not computed
- Duration: 34.9 s
- Cost: $0.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response

- **F001** fixed: with a cap configured, an unreadable usage record now makes `RunSpend.cap_error` fail the run ("cannot enforce pipeline.max_cost_usd: unreadable usage record from step(s) ..."), so a capped run never continues on an undercount. Uncapped runs keep the ERROR log and carry on. Tests cover both.
- **F002** partly accepted: a test now asserts `RunSpend.add` stays synchronous, which is the property the concurrency argument rests on. No load test: `add` has no await point, the shared tally is plain arithmetic, and `tests/load/` covers I/O timing paths, which this isn't. The overshoot bound is covered by the `fan_out` test.
- **F003** declined: the autouse stub follows the existing `_count_work` pattern in the same conftest; the real task-file reading has its own unpatched tests in `tests/events/builtin/test_blocked_tasks.py`. Reworking both stubs into injected dependencies is a separate refactor.
- **F004** declined: `_collect_turns` length and the `TypeGuard` cleanup are style notes outside this slice's behavior.
- **F005** declined: `assert isinstance(context, PostActionContext)` is the idiom in every sibling event action (`dispatch_branch_work`, `usage_stamp`, `revision_stamp`, `dispatch_artifact`).
- **F006** declined: an exception between insert and pop ends the run, so the stale flag has no later step to affect.
- **F007** pass, no change.
