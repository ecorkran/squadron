---
docType: review
layer: project
reviewType: tasks
slice: fix-case-qualification-and-yield-report-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 99814720708321fc8891fe01347f883db1544e72
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 1171412
cachedTokens: 1008500
cacheWriteTokens: 162894
completionTokens: 52830
durationSeconds: 231.7
costUsd: 0.333161
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: fail
    category: spec-contradiction
    summary: "Resolver crash is both a candidate rejection and a harness error"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:227"
  - id: F002
    severity: concern
    category: spec-gap
    summary: "Constructor crossings are indistinguishable from method crossings"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:195"
  - id: F003
    severity: concern
    category: correctness
    summary: "Reference-state test-side list may omit files the diff adds"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:150"
  - id: F004
    severity: concern
    category: interface
    summary: "Plugin output schema is not pinned"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:40"
  - id: F005
    severity: concern
    category: spec-gap
    summary: "Test-first mapping does not order the `collection_error` row"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:164"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Three I/O paths have no failure-mode test"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:108"
  - id: F007
    severity: concern
    category: testing
    summary: "Real-commit pins become silent skips on a shallow checkout"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:279"
  - id: F008
    severity: concern
    category: scope
    summary: "Tasks 10, 11 and 16 are too large for one junior pass"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:191"
  - id: F009
    severity: concern
    category: design-deviation
    summary: "Task 26 rewrites approved success criteria to match the build"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:299"
  - id: F010
    severity: note
    category: scope
    summary: "Two definitions are decided in the task file and not in the design"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:171"
  - id: F011
    severity: note
    category: testing
    summary: "`--keep` has no test"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:273"
  - id: F012
    severity: note
    category: sequencing
    summary: "Prerequisite 421 is unmet"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md"
---

# Review: tasks — slice 422

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Resolver crash is both a candidate rejection and a harness error

Task 16 (line 193) raises `BoundaryUndecidable` for resolver failure or unparsable output. Task 18 (line 219) maps `BoundaryUndecidable` to the `boundary_undecidable` candidate rejection, which blames the case. Task 18's test list (line 227) then requires "a resolver crash" to yield `harness_error`. One input cannot satisfy both. The design repeats the split: D6 (slice design line 185) makes an import failure a rejection, and Technical Requirements (line 389) make a resolver crash a `harness_error`. Decide by cause. A project package that fails to import stays `boundary_undecidable`. The resolver process itself failing (missing interpreter, plugin error, timeout) becomes `harness_error` via `HarnessFailure`. Write the split into Tasks 16 and 18 and into D6.

### [CONCERN] Constructor crossings are indistinguishable from method crossings

Line 195 says a constructor crossing must be in the allowed set and a method crossing is always allowed. Line 178 records a constructor and an instance method both with a class prefix in `co_qualname`. A constructor frame is `Cls.__init__`, which has a class prefix, so the judge as written classifies it as a method and allows it. Design D6 (slice design lines 190–191) has the same conflict. Specify that the plugin records a constructor kind for `__init__` and `__new__` frames, and that Task 16 judges on that kind.

### [CONCERN] Reference-state test-side list may omit files the diff adds

Task 11 builds `test_side_files` from `git ls-files`, and Task 18 calls `collect` again at the reference state. `ReplaySandbox` builds a history-free checkout (`src/squadron/replay/sandbox.py:150`), and I have not confirmed how `BenchmarkSandbox` lays out its index. If the reference's new test files are untracked after `FileStates` writes them, `git ls-files` omits them. Their helpers then count as project code in the trace, which can produce a false `reaches_past_boundary`, and their closures are never digested. Name the source explicitly: the parent list plus the diff's added test-side paths at the reference state, or `git ls-files --cached --others --exclude-standard`.

### [CONCERN] Plugin output schema is not pinned

The Context Summary pins the config JSON but not the output. Output shapes appear only in prose across Tasks 10 and 13–15: closure digests, conftest fixtures reached and defined, references `(kind, module, qualname)`, crossings `(module, co_qualname)`, patches `(api, owner kind, owner module, target)`, `has_co_qualname`, and `unresolved`. Task 11 parses collect output and Task 16 parses trace output, in separate commits, so each may invent different keys. Pin one JSON schema with key names and enum values in Task 10, before Task 11 reads it.

### [CONCERN] Test-first mapping does not order the `collection_error` row

421 records an id that did not collect as outcome `error` with kind `collection_error` (421 task line 228). Line 164 lists `collection_error` under the kind rule and `error` with any other kind under undecidable, with no precedence. Read in order, `error`/`collection_error` lands in undecidable, but D5 says it is `uses_symbol_added_by_fix`. State that kind rows are checked before outcome rows, and add a test for that exact pair.

### [CONCERN] Three I/O paths have no failure-mode test

The Context Summary says every bounded call has a failure test. These do not: `discover`'s `git log` (Task 7, line 108), Stage 2's `git diff --name-status` (Task 17, line 209; the harness-failure list at line 211 covers only `git show`), and `FileStates`' `git show` during sandbox switches (Task 11, line 151). The review rule requires each new I/O path to have a test asserting its observable signal. Add one test each. Stage 2 failure should be `harness_error` with detail and an ERROR log. For `discover`, decide whether a failure halts the build or records, since no candidates can be trusted if discovery fails, and test that decision.

### [CONCERN] Real-commit pins become silent skips on a shallow checkout

Task 24 calls `pytest.skip` when a pinned commit is absent. On a shallow CI clone every real-commit pin would be skipped and the suite would still report green, leaving the Functional Requirement at slice design lines 376–380 unverified with no visible failure. I could not confirm this repo's CI checkout depth. Fail under CI when a pinned commit is missing, or have Task 25 record that no pin was skipped. Also, the discovery pins read only git history, so the `network` marker on that file is unnecessary. Mark only the fairness pins.

### [CONCERN] Tasks 10, 11 and 16 are too large for one junior pass

Task 16 holds the resolver script, `adapter.boundary`, `adapter.trace`, `judge_trace`, the registry entry and three test files. Task 10 holds a fixture project with a uv lock, `fix_history` and its scenario, the collect-mode plugin, packaging, and three test groups. Task 11 holds collect, overlay, `FileStates`, grader commands and six test bullets. Split Task 16 into boundary (resolver and `adapter.boundary`) and trace verdict with registry. Split Task 10 into the fixture with `fix_history`, and plugin collect mode. Split Task 11 into `FileStates` with overlay, and collect with grader commands.

### [CONCERN] Task 26 rewrites approved success criteria to match the build

Task 26 changes the design's real-commit examples to match what was built. The criteria at slice design lines 376–380 name ebd45f3f and #291 as fairness examples. The build reaches them only by direct calls (Task 24), not through `build`. The deviation is sound, but a criterion rewritten to fit the outcome passes by definition. Keep the criterion text, record the direct-call path as a deviation in the DEVLOG, and raise the change with the PM before editing the design. The protocol changes (`is_test_side` with pyproject text, `trace` with `allowed`, the single `FairnessVerdict`) are supported by the Context Summary and can be recorded in the design.

### [NOTE] Two definitions are decided in the task file and not in the design

Task 13 defines "project" as outside `.venv` and not in `test_side_files`. Design line 188 cites 421 D11's definition, which excludes only name-matched test files. A helper under `tests/` that is not `test_*.py` is therefore project code under one definition and test-side under the other. Task 22 (line 261) also defines the counting unit, the latest record per commit regardless of environment, which the design does not state. Record both in the design when Task 26 corrects it.

### [NOTE] `--keep` has no test

The CLI signature includes `--keep` (slice design line 304; Task 23, line 268), and Task 18 uses it to skip sandbox removal. Task 23's test list (line 273) does not cover it. Add a test that `--keep` reaches the build and that the sandbox is absent without it.

### [NOTE] Prerequisite 421 is unmet

421's task file has unchecked items, and `src/squadron/benchmark/` and `tests/benchmark/` do not exist. Task 1's gate will therefore stop with `BLOCKED: slice 421 is not implemented`. That is the intended behavior, not a defect in 422, but nothing else in 422 can start until 421 lands.

### Run Digest

- Response length: 10953 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 1171412 / 1008500 / 162894 / 52830 / not computed
- Duration: 231.7 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
