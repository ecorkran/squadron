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
reviewedSha: 4e11d22d395a184882e77d6bb1267ebdd2a8dd7f
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 18.6
runId: run-20261013-p5-b4b93f69
squadronVersion: 0.21.6
findings:
  - id: F001
    severity: concern
    category: coverage-gap
    summary: "Dirty-tree refusal for `code` has no implementing task"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:70-77"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "`round N commit failed` stderr output is tested but not implemented in any task"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md:53-58"
  - id: F003
    severity: pass
    category: traceability
    summary: "Success criteria 1–9 trace to tasks"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md"
  - id: F004
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit cadence"
    location: "project-documents/user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md"
---

# Review: tasks — slice 941

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Dirty-tree refusal for `code` has no implementing task

The dirty-tree refusal for `code` comes from D5's last row, which requires a refusal before any model call with an error listing the dirty paths and exit 1. Task 8 says `validate_max_options` implements "D6". D6 covers the branch check but not the dirty-tree check. Only Task 9 (item 3) tests the dirty-tree behavior, and no task builds it. A junior implementer reading Task 8 would write the D6 checks and then hit a failing Task 9 test. Name the dirty-tree check in Task 8, or in Task 6, as an explicit sub-item citing D5.

### [CONCERN] `round N commit failed` stderr output is tested but not implemented in any task

D5 requires `round N commit failed: <error>` on stderr and exit 1, which supports Success Criteria 8 and the technical requirement for a stubbed failed round commit. Task 7 item 5 tests it. Task 6 lists the outcome mapping and the accepted/exhausted ordering but never says the runner emits this line or where the error text comes from. Add a Task 6 sub-item saying who prints it (the runner, from the failed `ActionResult` or run error) and that the exit code is 1.

### [PASS] Success criteria 1–9 trace to tasks

- **SC1:** Tasks 3, 6 and 8.
- **SC2 and SC3:** Task 10.
- **SC4:** Tasks 6 and 7.
- **SC5:** Tasks 4 and 9.
- **SC6 and SC7:** Task 9.
- **SC8:** Task 7.
- **SC9:** Task 12, with an explicit "unverified" fallback.

The technical requirements are also covered: the builder unit tests, the `round_completed` executor test, the `RoundPrinter` tests, the integration test, the lint/pyright gate, and the CHANGELOG bullet. No task falls outside the design, so there is no scope creep.

### [PASS] Sequencing, test-with pattern and commit cadence

Dependencies run in order: observer hook, builder, `RoundPrinter`, runner, CLI wiring, integration test, docs, final gate. There are no cycles. Each implementation task is followed by its tests and a commit (Tasks 1–2, 3–4, 5, 6–7, 8–9). Commits are spread across the run, not batched at the end. Task count and detail fit a 3/5 slice. A single task file is appropriate. No load-test task is needed because the slice states no NFR.

### Run Digest

- Response length: 2689 chars
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
- Duration: 18.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4

## Response (20261012)

- **F001 — fixed.** Task 8 now has an explicit sub-item for the `code` dirty-tree refusal (D5 last row): it lists the dirty paths, and a failed git call is an error, not a clean tree.
- **F002 — fixed.** Task 6 now says the runner prints the failing step's `error` to stderr and returns 1. For a failed round commit that is the executor's own `loop <name> round N commit failed: <error>` message (fix 85a7f7aa), printed as-is.
- **F003, F004 — pass, no action.**

**Open question for the PM (not raised by the review):** `sq run` refuses SDK execution inside a Claude Code session (`_resolve_execution_mode`, `cli/commands/run.py`), but `sq review --max` runs the same executor, and Task 12 / design walkthrough step 6 expect `/sq:review --max` to work inside Claude Code (Success Criterion 9). Neither the design nor the tasks say whether the review-revise runner applies that guard. This needs a decision before Task 6: apply the guard (and drop SC9 parity for `--max`), or confirm the guard's reason doesn't apply to a one-shot revise dispatch.
