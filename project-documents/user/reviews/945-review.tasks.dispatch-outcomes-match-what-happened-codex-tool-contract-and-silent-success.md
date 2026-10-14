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
reviewedSha: 98fe4397109294ea977bb495695ad515117492dd
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 34.5
runId: run-20261014-p5-5722795e
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task count and impl/test split are heavy for effort 3/5"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 2 adds metadata key constants that the design does not call for"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md (Task 2, second sub-item)"
  - id: F005
    severity: concern
    category: task-clarity
    summary: "Task 14 has a vague, conditional step"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md (Task 14, third sub-item)"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Implementation detail dictated beyond what the design requires"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md (Tasks 6, 11)"
  - id: F007
    severity: concern
    category: verifiability
    summary: "Task 26 depends on external state and credentials that the task cannot guarantee"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md (Task 26)"
  - id: F008
    severity: note
    category: scope
    summary: "Tasks 9 and 10 carry an extra WARNING behavior beyond refusal"
    location: "project-documents/user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md (Tasks 9–10)"
---

# Review: tasks — slice 945

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

- Criterion 1 is covered by Tasks 9–10.
- Criterion 2 is covered by Tasks 9–10.
- Criterion 3 is covered by Tasks 9–10.
- Criterion 4 is covered by Tasks 6, 8, 11–14.
- Criterion 5 is covered by Tasks 7–8.
- Criterion 6 is covered by Task 14.
- Criterion 7 is covered by Tasks 16–19.
- Criterion 8 is covered by Tasks 20–23.
- Criterion 9 is covered by Tasks 4–5.
- The integration requirement (the #200 loop path) is covered by Task 15.
- The CHANGELOG, validation and walkthrough requirements are covered by Tasks 24–26.
- No load-test or NFR task is needed.

### [PASS] Sequencing and test-with pattern

- Dependencies run in order. The constants and predicate (Task 2) come first. The SDK count fix (Task 4) and the OpenAI `first_tool_error` (Task 6) precede the outcome rules (Task 11) and their wiring (Task 13). The executor flag (Task 20) precedes the branch failure that sets it (Task 22).
- Each implementation task is followed immediately by its test task.
- Commits fall at seven points between Tasks 3 and 24 rather than at the end.
- The D5 and D6 work is committed separately from D1–D4, as the design requires.
- The `_flag_kind` ordering note in Task 22 is accurate. `_flag_kind` already reads `FAILURE_OUTPUT` and `BranchFailure` (`src/squadron/pipeline/executor.py:1762-1775`), so the executor needs no new coupling.

### [CONCERN] Task count and impl/test split are heavy for effort 3/5

- There are 26 tasks in one file, and many are tiny. Task 1 is branch creation. Tasks 3, 5 and 17 each add a few assertions. Task 15 is a single test that needs no code change.
- Merge Task 15 into Task 14, since both cover the D3 dispatch behavior. Fold Task 17 into Task 19 as one D5 test task. Fold Task 21 into Task 20, so the flag and its test land together.
- Task 25's full validation largely repeats the per-task ruff, pyright and pytest runs. Keep it only as a final gate.

### [CONCERN] Task 2 adds metadata key constants that the design does not call for

- The slice design lists `WRITE_TOOL_NAMES`, `requires_writes` and the predicate. It does not mention new key constants in `providers/base.py`.
- The constants are justified by the "never scatter comparison values" rule. But the task names `providers/base.py` without saying that the existing literals (`tools_given`, `tool_calls_made`) are being replaced.
- Either state that the existing literals in the providers are migrated to the constants, or the change is incomplete and leaves duplicates. Also confirm `providers/base.py` is the right home for them.

### [CONCERN] Task 14 has a vague, conditional step

- "Extend `tests/providers/agent_config_sites.py` captures if they cover this path" leaves the junior agent to decide whether to act.
- Name the assertion: `requires_writes` is true for a phase-step param and for `feedback`, and false for bare dispatch. Name the file that carries it. Drop the conditional.
- Task 14 also bundles four distinct scenarios plus a metadata-shape change. Task 13 should say which existing tests assert the full metadata dict, since Task 14's success line says they are the only ones that change.

### [CONCERN] Implementation detail dictated beyond what the design requires

- Task 6 suggests a constant name (`_FIRST_TOOL_ERROR_MAX_CHARS`). Task 11 specifies a "frozen dataclass" with a signature and "module under ~100 lines". Task 22 adds an extra code-structure instruction about check ordering.
- These are mostly harmless, and the design does name `ToolOutcome` and `assess_tool_outcome`. The "for example" constant name is a minor hallucination-trap risk and can be dropped.
- Drop the line-count target and the constant name. Keep only what a success criterion needs.

### [CONCERN] Task 26 depends on external state and credentials that the task cannot guarantee

- The walkthrough needs a Codex alias, an OpenRouter alias, SDK haiku, a scratch cf clone and a changeable Codex sandbox credential. The task correctly says to stop and ask the Project Manager if any is missing.
- Walkthrough steps 1–4 are the only proof that the refusals fire on real configs, so a skipped step leaves criteria 1–4 verified only at unit level. State in the success line that a skipped step must be reported as unverified, not passed.
- The DEVLOG sub-item cites `prompt.ai-project.system.md` without a path. I did not verify that reference.

### [NOTE] Tasks 9 and 10 carry an extra WARNING behavior beyond refusal

- The bare-dispatch WARNING traces to criterion 3, so it is in scope.
- Task 9 says the agent logs it, while the context summary says "the agents do not log refusals". This is consistent, because the WARNING is not a refusal. Keep the distinction explicit.

### Run Digest

- Response length: 6295 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 34.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
