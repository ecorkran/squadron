---
docType: review
layer: project
reviewType: tasks
slice: snapshot-record-and-first-adapters-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 230feb6304365e785fc1d228895491fea6a55093
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 105690
cachedTokens: 8843
cacheWriteTokens: 96843
completionTokens: 5417
durationSeconds: 47.0
costUsd: 0.443169
costBasis: provider
runId: run-20261022-p5-31b932ac
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md"
  - id: F002
    severity: concern
    category: coverage
    summary: "Success Criterion 5's \"files over the limit\" has no home in the record shape"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:161"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Version-parsing tests run before the real tool-output fixtures exist"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:172-181"
  - id: F004
    severity: concern
    category: process
    summary: "Commit checkpoints are batched across long stretches"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:207"
  - id: F005
    severity: note
    category: sequencing
    summary: "Python adapter declares all four metrics before ruff and pyright exist"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:219"
  - id: F006
    severity: note
    category: dependencies
    summary: "Task 20 assumes ESLint is installed in `../context-forge`"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:214"
  - id: F007
    severity: note
    category: scope
    summary: "Proportionality"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:165"
---

# Review: tasks — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

- **Functional 1–10:** each has an implementing task and a test task, apart from criterion 5, whose file-length half has a gap (see the first CONCERN below).
  - SC1: Tasks 6/7, 18/19.
  - SC2, SC8: Tasks 9/10.
  - SC3: Tasks 4/5.
  - SC4: Task 19 and walkthrough step 4.
  - SC6: Tasks 19, 24, 26, 30.
  - SC7: Tasks 12/13, 29/30.
  - SC9: Tasks 10 and 7.
  - SC10: Tasks 7 and 32.
- **Technical requirements:** the failure-mode tests are all present.
  - Tool and version probe: Tasks 17, 24, 26, 30.
  - Parse failures: Tasks 22 and 28.
  - Git `None` or non-zero: Tasks 10 and 13.
- **Integration:** the every-metric-for-every-language guard is in Task 19, and docs and CHANGELOG are in Task 33.
- **NFR / load tests:** the slice restates no NFR, so no load test or CI-gating task is needed.
- **Ordering:** dependencies run forward and nothing is circular.

### [CONCERN] Success Criterion 5's "files over the limit" has no home in the record shape

- Task 14 asks the file-length builder for "the over-limit file list per D1 and Success Criterion 5".
- Neither the slice's `Measurement` schema (Database / Storage Schema) nor Task 4 has a field for it. `over_limit` is `list[FunctionOverLimit]`, which is function-shaped, and `limit` is only the number.
- Task 15 tests `over_limit` only for functions. No task asserts that file length reports files over the limit.
- The implementer has to invent a field in the keystone record shape, which 401, 403 and 404 inherit.
- **Fix:** have the slice or Task 4 choose one of two options.
  - Add an explicit field, such as `files_over_limit: list[str]`.
  - State that over-limit files are derived from `per_file` and `limit`, and reword Task 14.
- Add a Task 15 assertion either way.

### [CONCERN] Version-parsing tests run before the real tool-output fixtures exist

- Task 16 implements `probe_version`, which parses `--version` text for ruff, pyright, uv and ESLint. Task 17 tests it.
- The real `--version` captures are only created in Task 20 (line 215), which comes after Tasks 16–19.
- That breaks the project's parsing rule that the fixture must be the real production format, and the slice's own requirement for real-output fixtures.
- Task 17 would either use invented strings or have to be reworked later.
- **Fix:** move Task 20 (or at least the version-output capture) ahead of Task 16.
- Task 20 has no code dependency on Tasks 11–19, so it can go earlier.

### [CONCERN] Commit checkpoints are batched across long stretches

- The project rule is to commit at least once per task. These stretches have a single commit:
  - Tasks 3–7 share one commit.
  - Tasks 11–19 share one commit at line 207. That covers the contract, file resolution, lengths, runner and orchestrator, with seven implementation and test tasks.
  - Task 20 (fixtures) has no commit and rides in Task 24's commit.
  - Tasks 21–22 have no commit and ride in Task 24's.
- **Fix:** add commit items at natural boundaries. Suggested points:
  - After Task 5.
  - After Task 13.
  - After Task 15 (or 17).
  - After Task 20.
  - After Task 22.

  Each is a small `feat:`/`test:`/`chore:` commit.

### [NOTE] Python adapter declares all four metrics before ruff and pyright exist

- Task 21 sets `metrics` to all four. The adapter contract requires exactly one `Measurement` per declared metric, but lint and type arrive in Tasks 23 and 25.
- Nothing breaks, because the orchestrator tests use fakes and the registry is only wired in Task 31.
- A one-line note in Task 21 would stop an implementer from stubbing placeholder measurements. For example: "declare `metrics` incrementally, or leave `measure` incomplete until Task 25".

### [NOTE] Task 20 assumes ESLint is installed in `../context-forge`

- The capture needs `../context-forge/node_modules/.bin/eslint`, and the task has no step for the case where it's absent. I haven't checked that sibling repo.
- The same applies to the `ignores` entry and the tracked `vitest.config.ts` it cites as an example.
- A pre-check line would fail fast. Installing dependencies there is a write to `../context-forge`, and the slice does not authorize it.

### [NOTE] Proportionality

- 35 tasks is heavy but defensible for a keystone slice with two adapters. Nothing traces to nothing, and I found no scope creep.
- Task 15 is an effort-1 test task for Task 14. It could be folded into Task 14 as test-with, which would cut a task header without losing coverage.
- Task 35 repeats checks already run at each commit. It is worth keeping only for its mapping of success criteria to tests.

### Run Digest

- Response length: 5696 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 105690 / 8843 / 96843 / 5417 / not computed
- Duration: 47.0 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
