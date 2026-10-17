---
docType: review
layer: project
reviewType: tasks
slice: artifact-usage-stamping
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/178-tasks.artifact-usage-stamping.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: d0e4730825175fdcacd1546a300dbf222d66f315
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 209033
cachedTokens: 174721
cacheWriteTokens: 34306
completionTokens: 4238
durationSeconds: 33.4
costUsd: 0.197754
costBasis: provider
runId: run-20261017-p5-a1cd3acb
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Part C commits are batched at the end of Task 13"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:141-188"
  - id: F002
    severity: concern
    category: test-with-pattern
    summary: "Manifest and dispatcher tests sit apart from the registration task they test"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:155-159, 185-187"
  - id: F003
    severity: concern
    category: scope
    summary: "Speculative JSON output sub-item in Task 16"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:224"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 4 contradicts itself on \"verbatim\" versus key-table references"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:73-74"
  - id: F005
    severity: concern
    category: process
    summary: "Task 19 commit prefix and the walkthrough's dependence on live LLM runs"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:251-258"
  - id: F006
    severity: note
    category: testing
    summary: "Task 3 contains a near-tautological test"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:66"
  - id: F007
    severity: note
    category: accuracy
    summary: "Design/code discrepancy already handled"
    location: "src/squadron/cli/stats_effort_views.py:110"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing and sizing"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
---

# Review: tasks — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Part C commits are batched at the end of Task 13

Tasks 10, 11, 12 and 13 produce the stamp action, its registration and all of its tests. They have a single commit, at the end of Task 13. The project rule is to commit at least once per task, and the other parts commit after each implement-plus-test pair. Add a commit after Task 12, since Tasks 10–12 produce a working stamp with its happy-path tests. A second commit after Task 13 would then cover the failure-mode and manifest tests. Tasks 2, 4, 6 and 14 also have no commit of their own, but their paired test tasks commit them straight afterward. Task 14's pair, Task 15, has no commit at all, so the report code and its tests ride along with the Task 17 commit.

### [CONCERN] Manifest and dispatcher tests sit apart from the registration task they test

Task 11 registers the binding. The tests that check its position in `DEFAULT_BINDINGS`, the `disable:` entry and the dispatcher ordering are in Task 13, two tasks later and mixed in with the failure-mode tests. Move the three manifest and dispatcher tests into a test step directly after Task 11, or into Task 12. The dispatcher-order test is the only test of the design's "No path written this run" row. It exercises existing `fire` behavior, so keep it small.

### [CONCERN] Speculative JSON output sub-item in Task 16

Task 16 says to add artifact spend to JSON output "if `sq stats slice` has JSON output". No success criterion or D-section asks for that. The task also leaves the decision to the implementer ("skip if the slice view has no JSON mode"). Either remove the item, or check `stats/json_support.py` now and state in the task whether a JSON mode exists. If the slice view does have one, name the requirement that needs the artifact spend there.

### [CONCERN] Task 4 contradicts itself on "verbatim" versus key-table references

Task 4 says to move the reader code "verbatim". It then says key names must come from the `RunCost` key table "wherever the moved code already names them". The first is a pure move and the second is an edit. The design (D4) only says "verbatim" and "each key name is defined once". Pick one. The simplest option is to move verbatim, then rewire the literals in a separate step, with the unchanged `reviews_report` tests as the guard. As written, a junior implementer could edit parsing behavior while "wiring" the keys.

### [CONCERN] Task 19 commit prefix and the walkthrough's dependence on live LLM runs

Task 19 commits edits to the slice design document, which are documentation and not tests, under `test:`. Use `docs:` or `review:`. The walkthrough runs P4 and P5 on a scratch slice, so it spends real LLM money and depends on the environment. The task already has a prune safeguard. Add a similar note that the PM should confirm it is acceptable to run the P4 and P5 pipelines. Without that, an automated implementer may skip the step or run it unattended.

### [NOTE] Task 3 contains a near-tautological test

The test that `frontmatter_lines()` equals lines rendered from `frontmatter_fields()` checks an implementation against itself. The real regression guard is the unchanged existing persistence and rendering tests on the line above, which assert byte-identical review artifacts. The extra test is cheap, but it can be dropped.

### [NOTE] Design/code discrepancy already handled

The Context Summary correctly redirects the `recorded spend` line from `cli/stats_views.py` (the design's component table) to `cli/stats_effort_views.py`. I confirmed `recorded spend` is printed at line 110 of that file. The test file `tests/cli/test_stats_effort.py` also exists, and `events/builtin/artifact_paths.py` and `revision_stamp.py` exist, as the tasks assume.

### [PASS] Success-criteria coverage

Each design criterion traces to a task:
- Stamp keys, `usageRounds` and `pricedRounds` on slice, task and architecture docs: Tasks 10 and 12.
- Cumulative fold across rounds: Tasks 8, 9 and 12.
- Unpriced rounds: Tasks 9 and 12.
- Keep, failed dispatch, implement, summary and compact stamp nothing: Task 12 eligibility tests.
- Split task breakdown gets a WARNING and no stamp: Task 13.
- No `StateManager` writes: Task 12.
- Every D6 failure has a log-signal test: Task 13.
- Artifact spend line next to `recorded spend` and not summed with it: Tasks 16 and 17.
- Spend survives pruning: Task 17's no-run-state test.
- 179 needs no run state: Task 15.
- `disable:` support: Task 13.
- Byte-identical review artifacts and unchanged `dispatch-artifact` tests: Tasks 3, 5 and 7.
- Lint, type-check and docs: Tasks 18 and 19.

I found no tasks outside the design's scope other than the JSON item above.

### [PASS] Sequencing and sizing

The dependencies run in order: refactors (A), then the usage model (B), then the stamp (C), then the report and slice line (D), then docs (E). There are no cycles. Part C uses the `dispatch_artifact_paths` and `record_from_frontmatter` that Part A creates, and Part D uses the model from Part B. The task list is proportionate for a 3/5 slice. Tasks are a single file and each is of reasonable size. Task 10 is the largest, but its sub-items are specific and it points the implementer at `revision_stamp.py` instead of guessing. The merge is correctly left out of the task list, per the Git rules.

### Run Digest

- Response length: 6447 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 209033 / 174721 / 34306 / 4238 / not computed
- Duration: 33.4 s
- Cost: $0.20 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
