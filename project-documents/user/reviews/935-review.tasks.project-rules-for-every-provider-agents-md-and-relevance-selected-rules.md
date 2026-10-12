---
docType: review
layer: project
reviewType: tasks
slice: project-rules-for-every-provider-agents-md-and-relevance-selected-rules
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/935-tasks.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261012
dateUpdated: 20261012
reviewedSha: 79bd463b5a6cf850ae9177d39ae8b05dac88a892
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
durationSeconds: 55.2
squadronVersion: 0.21.5
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "The git-failure test fakes a failure `run_git` never produces"
    location: "src/squadron/review/git_utils.py:28-59"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Review rule loading still skips unreadable rule files silently"
    location: "src/squadron/review/rules.py:235-243"
  - id: F003
    severity: concern
    category: concurrency
    summary: "Blocking file and git I/O runs inside async dispatch"
    location: "src/squadron/pipeline/actions/dispatch.py:97-186"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 12 requires the rendered length to equal a count made before rendering"
    location: "unverified"
  - id: F005
    severity: note
    category: testing
    summary: "The real-files test leaves out the review kind"
    location: "unverified"
  - id: F006
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/tasks/935-tasks.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing, commits and size"
    location: "project-documents/user/tasks/935-tasks.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md"
---

# Review: tasks — slice 935

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] The git-failure test fakes a failure `run_git` never produces

Task 15 says "A `run_git` failure propagates (monkeypatch `run_git` to raise)". But `run_git` never raises. It returns `None` when git can't run or times out, and a process with a non-zero `returncode` when git refuses. Its docstring says "Callers must distinguish the two". A test that makes it raise passes even if `build_rule_context` treats `None` as "no tracked files", which is exactly the silent zero-rules case the design forbids (Special Considerations, and the failure-mode row "`git ls-files` fails or times out"). Change Task 14 to say both `None` and a non-zero `returncode` must raise, naming the git error. Change Task 15 to test both returns instead of an exception.

### [CONCERN] Review rule loading still skips unreadable rule files silently

Under Patterns and Conventions, the design says that today `load_rules_content` skips an unreadable rule file silently and "that `continue` is replaced". The failure-mode table also requires a WARNING and a `dropped` entry for this case. Task 11 covers this only for the new `select_project_rules`. Task 2 leaves `load_rules_content` in `review/rules.py` as it is, and Task 19 changes `load_review_rules` without touching it. Review language rules still go through the `except OSError: continue` at lines 241-242, and the template-rule path does the same at 257-258. Add a step to Task 19 that replaces the silent skip with a WARNING and records the file as dropped, plus a test in Task 20.

### [CONCERN] Blocking file and git I/O runs inside async dispatch

Task 17 calls `build_rule_context` → `select_project_rules` → `render_project_rules` inside the async `one_shot_dispatch_with_telemetry`. That means a `git ls-files` subprocess (up to 30 seconds), reading every rule file and the conventions file, and a config read, all synchronous. The project's Python rules require sync code in an async function to finish in under 1 ms, or else run off the event loop. This codebase already does that consistently, for example `asyncio.to_thread(_kept_outputs, ...)` at dispatch.py:395 and the `to_thread` calls in `actions/review.py`. Task 17 should say to run the context build and selection through `asyncio.to_thread`. Review's `_inject_file_contents` path should be checked the same way.

### [CONCERN] Task 12 requires the rendered length to equal a count made before rendering

Task 12's success line and a step in Task 13 both require `len(render_project_rules(...)) == ProjectRules.chars`. But Task 11 computes `chars` during selection, and render then adds the `## Project Rules` heading, rule separators and heading demotion, which itself adds `#` characters. To make the two match, the implementer would have to render inside selection or fudge the count. The design only needs `chars` recorded and the budget enforced on whole files. Drop the equality check, or state exactly what `chars` measures (for example, raw file content only) and test that instead.

### [NOTE] The real-files test leaves out the review kind

The technical requirements ask for the per-kind result in D3. Task 13 asserts implement, design and tasks only. For review, D3 only says it gets "what `load_review_rules` gives it today", which is a different code path, and Task 20 covers that. This is acceptable as written. If you want a direct check, add one assertion that review's selection with squadron's real rules is unchanged.

### [PASS] Every success criterion has a task

- Non-SDK injection plus the state record: Tasks 17 and 18.
- The D2 cases: Tasks 5 and 6.
- `steps: [implement]` reaches only implement: Tasks 13 and 20.
- Path-scoped rules: Task 13.
- Reviews of an AGENTS.md-only project, and the review frontmatter keys: Tasks 7, 8, 9, 19 and 20.
- SDK one-shot and SDK session record `sdk-native`: Tasks 17 and 18.
- Budget behavior: Tasks 13 and 18.
- The no-conventions, no-rules WARNING: Task 18.
- Parser tests and the real-format fixture: Task 4.
- Integration tests: Tasks 18, 9 and 20.
- Docs: Task 21.
- Walkthrough: Task 22.

Apart from the git-failure row above, each row of the failure-mode table has a test asserting its signal.

### [PASS] Sequencing, commits and size

The order follows the design's Development Approach. Every dependency points backward (frontmatter → conventions → selection → glue → wiring → review filtering), and there are no cycles. Each implementation task is followed by its test task, and there are nine commit points spread through the file. Twenty-three tasks in one file is reasonable for effort 3/5. The design states no NFR, so no load test or CI-gating task is needed.

### Run Digest

- Response length: 5854 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 55.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response (20261012)

- **F001 — accepted.** `run_git` returns `None` or a non-zero `returncode`; it never raises. Task 14 now raises on both, and Task 15 tests both returns.
- **F002 — accepted.** Task 19 replaces the silent skips in `load_rules_content` and `get_template_rules` with a WARNING and leaves unreadable language rules out of the returned filenames. Task 20 tests it.
- **F003 — accepted for dispatch.** Task 17 runs build-and-select through `asyncio.to_thread`. The review side is unchanged: `_inject_file_contents` already reads files synchronously today, and Task 7 only swaps which conventions file it probes.
- **F004 — accepted.** The equality check is dropped. `chars` is the raw content length the budget is checked against; Tasks 12 and 13 now say so.
- **F005 — no change.** Review selection is covered by Task 20, as the finding says.
