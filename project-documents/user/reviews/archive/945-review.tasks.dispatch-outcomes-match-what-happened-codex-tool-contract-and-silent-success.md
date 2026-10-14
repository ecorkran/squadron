---
docType: review
layer: project
reviewType: tasks
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 4ca6c6e5032b4b397de0b3af47964fb13f67c629
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 32.1
runId: run-20261014-p5-5722795e
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Metadata key constants are decided after the first task that needs them"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:101"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "A failed D3 write-tool check on SDK one-shot has no direct test"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:131"
  - id: F003
    severity: concern
    category: task-structure
    summary: "Several implementation tasks run back-to-back before their tests"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:127-176"
  - id: F004
    severity: note
    category: consistency
    summary: "Predicate location differs between the design and the tasks"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:81"
  - id: F005
    severity: note
    category: process
    summary: "Commit checkpoints are well distributed"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:44"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria traceability"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md"
---

# Review: tasks — slice 945

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Metadata key constants are decided after the first task that needs them

Task 6 stamps `first_tool_error` in the OpenAI agent. Task 11 then says "if the providers do not already share key constants, define them once in this module and use them in Task 13". `dispatch_outcome.py` is in `pipeline/`, so a provider can't import its constants without inverting the layering. The conditional is also vague for a junior AI. As written, the literal `"first_tool_error"` could end up in three modules (`providers/openai/agent.py`, `dispatch_outcome.py`, `dispatch.py`). That breaks the project rule against scattering comparison values. Decide the constants' home (for example `core/` or next to `WRITE_TOOL_NAMES` in Task 2) and say whether `tools_given`, `tool_calls_made` and `failed_tool_calls` already have constants. Task 6 should then use that home.

### [CONCERN] A failed D3 write-tool check on SDK one-shot has no direct test

D3 says the rules apply to "SDK one-shot dispatches that declare `allowed_tools`". Criterion 9 covers only the failed-call count (Task 5). Task 14 mocks the registry generically and never says which provider's metadata shape it feeds. Add one case to Task 14 using SDK-shaped metadata (a non-zero `failed_tool_calls` with no `first_tool_error` key). That confirms row 2 and its "when present" handling work when the SDK doesn't supply the error text.

### [CONCERN] Several implementation tasks run back-to-back before their tests

The test-with pattern is loose in two places:
- Tasks 15 and 16 are both implemented before Task 17 tests them.
- Tasks 20 and 21 follow Task 18 and are tested together in Task 22.

Task 21 is a one-function change with an ordering trap (the `PAUSED` check runs first today). It would fit better as a sub-item of Task 20 so the ordering warning sits next to the code that triggers it. Task 14 is the heaviest task: three test files, provider capture sites, an executor loop-body case and a commit. Consider splitting the executor loop-body case into its own task.

### [NOTE] Predicate location differs between the design and the tasks

The design's component table places `dispatch_requires_writes` in `pipeline/actions/dispatch.py`. Task 2 puts it in `pipeline/actions/dispatch_rules.py`. The task's choice is better, because `dispatch.py` is already 786 lines and the predicate sits next to `rule_step_from_params`. Update the design table to match so the implementer isn't confused.

### [NOTE] Commit checkpoints are well distributed

Commits land after Tasks 3, 5, 8, 10, 14, 17, 19, 22 and 23. D5 and D6 are separate commits from D1–D4, as the design asks. Merge is correctly left to Phase 7. CHANGELOG, full validation and the walkthrough are in the right order. No NFR load tests are implied, so no CI-gating task is needed.

### [PASS] Success-criteria traceability

- Criteria 1–3 map to Tasks 9–10.
- Criterion 4 maps to Tasks 6, 11, 13 and 14.
- Criterion 5 maps to Tasks 7–8.
- Criterion 6 maps to Task 14.
- Criterion 7 maps to Tasks 15–17.
- Criterion 8 maps to Tasks 18–22.
- Criterion 9 maps to Tasks 4–5.

Walkthrough steps 1–7 are covered by Task 25.

### Run Digest

- Response length: 4389 chars
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
- Duration: 32.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
