---
docType: review
layer: project
reviewType: tasks
slice: review-and-revise-loop-from-sq-review-max
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261012
dateUpdated: 20261012
reviewedSha: 4006e4c43d5a16649e575316b68b576fb19b5214
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 35.8
runId: run-20261013-p5-b4b93f69
squadronVersion: 0.21.6
findings:
  - id: F001
    severity: concern
    category: scope-conflict
    summary: "Task 11 mandates a shared exit helper that contradicts the `review.py` and D3 constraints"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:124"
  - id: F002
    severity: concern
    category: underspecified
    summary: "Task 11 doesn't say where the final verdict, the round count, or \"accepted\" come from"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:122-123"
  - id: F003
    severity: concern
    category: correctness-risk
    summary: "Option allowlist in Task 7 will reject the positional index unless exempted"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:84-86"
  - id: F004
    severity: concern
    category: granularity
    summary: "Tasks 13–15 are near-identical and should be one task"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:139-152"
  - id: F005
    severity: concern
    category: commit-checkpoints
    summary: "Commits are batched across long task runs"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:82-134"
  - id: F006
    severity: note
    category: proportionality
    summary: "Minor test and option items go beyond the success criteria"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:75,142,155"
  - id: F007
    severity: note
    category: coverage
    summary: "Criteria 1–9 and the technical requirements trace to tasks"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md"
---

# Review: tasks — slice 941

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 11 mandates a shared exit helper that contradicts the `review.py` and D3 constraints

- Task 11 says to "extract a shared helper if needed" so `_exit_on` logic isn't duplicated.
- `_exit_on` lives in `cli/commands/review.py`. D3 forbids `review_revise.py` from importing from `review.py`.
- Task 16 (line 159) requires the `review.py` diff to be "limited to option declarations and the early branches".
- Extracting the helper breaks one of these constraints. The task needs to say where the helper goes, for example a small neutral module that both files import. It should also say that the move is allowed despite the Task 16 criterion. Otherwise an implementer has to choose between duplicating the logic, breaking the import rule, or breaking the diff-limit criterion.

### [CONCERN] Task 11 doesn't say where the final verdict, the round count, or "accepted" come from

- D7 says `execute_pipeline` returns a `StepResult` holding only the last round's action results.
- Task 11 still requires `final: <VERDICT> after N rounds` and the D5 exit mapping, including "accepted by `accept_if`" versus "exhausted-not-accepted".
- The task never says whether the verdict and round count come from `RoundPrinter` state or from the `StepResult`. It also doesn't say how an accepted exhaustion is told apart from a failed one.
- A junior implementer would have to guess. Add a sub-item naming the source for each of the three values. Task 12 should test an exhausted loop in both the accepted and not-accepted cases, because the current list (PASS, accepted CONCERNS, FAIL, failed action) doesn't distinguish them.

### [CONCERN] Option allowlist in Task 7 will reject the positional index unless exempted

- Task 7 refuses any parameter outside `MAX_SUPPORTED_OPTIONS` whose source is `ParameterSource.COMMANDLINE`.
- The positional index argument is itself a Click parameter with source `COMMANDLINE`, and it isn't in the listed set (`max`, `model`, `revise_model`, `cwd`, `verbose`).
- A literal implementation would refuse every valid invocation. The task should state that arguments are excluded from the check, or that the positional's parameter name is in the set.
- Task 8 should also include a positive case. A valid `--max 2 --model X` call must pass validation and reach the stubbed executor. The current cases only assert refusals, so this bug would pass them.

### [CONCERN] Tasks 13–15 are near-identical and should be one task

- Tasks 14 and 15 are literally "Same as Task 13" for a different kind.
- Three tasks and three success lines for one repeated edit add overhead and no independent verification. Task 16 tests all three together anyway.
- Merge them into one wiring task with a per-kind sub-item list, keeping the `review_arch` exclusion.
- Task 19 (CHANGELOG, two lines) can likewise fold into Task 18, since they already share one commit.

### [CONCERN] Commits are batched across long task runs

- Task 17 already says "Every code task ends with … a commit". In practice the first commit after Task 4 is at Task 6, and the next is Task 12. Tasks 7–12 (validation, tests, `RoundPrinter`, its tests, runner, runner tests) all land in one commit.
- Tasks 13–16 are the same, with one commit at Task 16.
- Add a commit at Task 8 (validation plus tests) and at Task 10 (`RoundPrinter` plus tests), so checkpoints follow each implementation-and-test pair.

### [NOTE] Minor test and option items go beyond the success criteria

- Task 6 item 5 tests that the loaded pipeline definition is unchanged. It is cheap and protects the "copy before overriding" rule, but no success criterion asks for it.
- Task 13 adds Typer `min 1` on `--max`, and Task 16 tests `--max 0` rejection. The design says "the loop's own `max` validation enforces this".
- Either is defensible. Pick one enforcement point, because two make it unclear which error message the user sees.

### [NOTE] Criteria 1–9 and the technical requirements trace to tasks

- Criteria 1–3 map to Tasks 5, 11 and 17.
- Criterion 4 maps to Tasks 11–12. Criterion 5 maps to Tasks 5–6 and 15–16.
- Criterion 6 maps to Task 16. Criterion 7 maps to Tasks 7–8.
- Criterion 8 maps to Tasks 11–12. Criterion 9 maps to Tasks 18 and 21.
- The observer-hook tests (Task 4), `RoundPrinter` tests (Task 10) and the dirty-tree test (Task 8) cover the remaining technical requirements.
- Walkthrough step 6 is correctly handled as a possible pending item for the PM. No NFR is restated, so no load test or CI gating task is needed.

### Run Digest

- Response length: 5758 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 35.8 s
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
