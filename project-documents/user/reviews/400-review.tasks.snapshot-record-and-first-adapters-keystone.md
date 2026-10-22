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
reviewedSha: 9c7cc816a826531e7ca8d2d5b609439a1520b05a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106423
cachedTokens: 11222
cacheWriteTokens: 95197
completionTokens: 4535
durationSeconds: 40.5
costUsd: 0.428002
costBasis: provider
runId: run-20261022-p5-31b932ac
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage and sequencing"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:39-322"
  - id: F002
    severity: concern
    category: correctness
    summary: "\"Same failure handling as ruff\" misclassifies pyright and ESLint exit codes"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:256"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Pyright and ESLint failure modes are not all tested"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:261"
  - id: F004
    severity: concern
    category: scoping
    summary: "Python and TypeScript adapter modules are likely to exceed ~300 lines, and the split is deferred"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:258"
  - id: F005
    severity: note
    category: task-structure
    summary: "Task 14 mixes implementation, tests and commit in one task"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:161-169"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 15 BLOCKED pre-check gates many downstream tasks"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:172"
---

# Review: tasks — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage and sequencing

- **SC1, SC9, SC10:** covered by tasks 6/7/18/31 (store, orchestrator, CLI).
- **SC2, SC8:** covered by tasks 9/10 and 19 (preflight and integrity).
- **SC3:** covered by tasks 4/5 (model validators).
- **SC4:** covered by task 19 (determinism test) and task 33 (walkthrough).
- **SC5:** covered by task 14 (shared length counting).
- **SC6:** covered by tasks 18 and 22–29 (the five absence reasons).
- **SC7:** covered by tasks 12/13 and 28/29 (exclusions and ESLint ignored files).
- **Docs and CHANGELOG:** task 32.
- **Sequencing:** dependencies run forward with no cycles. Task 15's fixtures are produced before their consumers in tasks 17, 22, 24 and 28. Nothing traces to no criterion. The slice states no NFR, so no load test or CI wiring task is needed.

### [CONCERN] "Same failure handling as ruff" misclassifies pyright and ESLint exit codes

- **The problem:** Task 24 (pyright) and task 28 (line 283, ESLint) both say "same failure handling as ruff". Task 22 maps a non-zero exit to `tool_failed`.
  - Ruff is run with `--exit-zero`, so any non-zero exit means failure.
  - Pyright and ESLint exit 1 when they find errors, which is a normal result. Treating that as `tool_failed` would make type and lint counts absent on every project that has findings.
  - D8 draws the distinction ("non-zero for a reason other than findings"), but the tasks don't carry it down.
- **Fixture gap:** Task 15 doesn't record exit codes for the pyright or ESLint captures. Task 15 also doesn't capture the pyright and ESLint failure exits, such as a config error.
- **Fix:** Have task 15 record the exit code with each capture. Add an explicit rule to tasks 24 and 28 giving which exit codes mean "findings" and which mean "failed". Add tests for exit 1 with findings (counted) versus a fatal exit (`tool_failed`).

### [CONCERN] Pyright and ESLint failure modes are not all tested

- The Technical Requirements require a test per tool failure mode, covering log signal and outcome. The modes are timeout, missing tool, bad JSON, non-zero exit, and version-probe failure.
- Task 23 (ruff) lists them all. Task 25 lists only the uv and environment cases plus the in-sync case, so pyright missing, timeout, bad JSON, bad exit and probe failure have no test.
- Task 29 (ESLint) omits the version-probe failure.
- Add a pyright failure-mode list to task 25 and the probe case to task 29.

### [CONCERN] Python and TypeScript adapter modules are likely to exceed ~300 lines, and the split is deferred

- `python_adapter.py` accumulates ast length, ruff lint, the uv check, environment identity and pyright across tasks 20, 22 and 24. Task 24's success criterion only says to split the file if it ends up too long. The same pattern applies to `typescript_adapter.py` in tasks 26 and 28.
- That would force a refactor after the tests are written.
- Decide the split up front. For example, put the ruff and pyright tool runners and the shared pyproject hashing helper in sibling modules from task 22, and update the slice design's module table then.

### [NOTE] Task 14 mixes implementation, tests and commit in one task

- Every other implementation task is followed by a separate test task. Task 14 bundles both. It is small and the test-with pattern holds, so this is acceptable.
- Task 2's smoke test is similarly thin but harmless.

### [NOTE] Task 15 BLOCKED pre-check gates many downstream tasks

- The BLOCKED rule is valid here, since it depends on `../context-forge` having `node_modules`. Tasks 17, 22–25 and 28–29 depend on its fixtures.
- If the pre-check fails, tasks 26 and 27 (tree-sitter length) don't need the ESLint fixtures and could proceed first. The ordering doesn't need to change, but whoever hits the block should know this.

### Run Digest

- Response length: 4964 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 106423 / 11222 / 95197 / 4535 / not computed
- Duration: 40.5 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
