---
docType: review
layer: project
reviewType: tasks
slice: everyday-cli-fixes
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/940-tasks.everyday-cli-fixes.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261009
dateUpdated: 20261009
reviewedSha: 15c2f41dd211333901a44b5b6fc88c02962faaca
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 30.1
runId: run-20261010-p5-4e5bc315
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Sequencing and commit distribution"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 3 is too large for one task"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md (Task 3)"
  - id: F004
    severity: concern
    category: ambiguity
    summary: "Task 8 is ambiguous about callers that have no profile"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md (Task 8)"
  - id: F005
    severity: concern
    category: parsing
    summary: "Task 13 extracts the reference block with a fragile rule"
    location: "src/squadron/data/models.toml:1-37"
  - id: F006
    severity: concern
    category: process
    summary: "Task 2 leaves a failing test until Task 3 ends"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md (Task 2)"
  - id: F007
    severity: note
    category: test-coverage
    summary: "D4 behavior for old lowercased-path runs has no test"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md (Task 6)"
  - id: F008
    severity: note
    category: verification
    summary: "Task 16's check on `~/.config/squadron` has no method"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md (Task 16)"
  - id: F009
    severity: note
    category: scope
    summary: "Task 17 adds docs and changelog work outside the slice criteria"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md (Task 17)"
---

# Review: tasks — slice 940

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are covered by tasks

Every functional and technical criterion in the slice design traces to a task:
- **Copy and list:** copy to user and `--project` scope, refusal without `--force`, and list marking are in Tasks 10-12.
- **`models init`:** `sq models init` is in Task 13.
- **Path runs:** the path run recorded as `foo` plus its absolute path, and `--resume` reloading the same file, are in Tasks 4-6.
- **Output escaping:** the `[codex]` test is in Task 3.
- **Review profile:** `-v` printing the profile and `aiProfile` in artifacts are in Tasks 7-8.
- **Quality gates:** the pre-slice state-file test is in Task 4. The ruff, pyright and full-suite gates are in Task 16.

Each D8 failure-mode row has a named test in Tasks 6, 11 and 13. The slice states no NFR, so no `tests/load/` task or CI gating task is required.

### [PASS] Sequencing and commit distribution

The order follows the design's Implementation Notes. Dependencies hold: Task 9 comes before Tasks 11 and 13, Task 10 before Task 11, and Task 12 before Task 15. There are no cycles. Tests sit with their implementation in each task, and commits are spread across the file, one per task. Task 1 creates the branch, and no task performs a merge, which matches the git rules.

### [CONCERN] Task 3 is too large for one task

Task 3 sweeps about 77 print sites across the whole `src/squadron/cli` tree and ends in a single commit. It is the biggest unit of work in the file, and a junior AI is likely to lose track of it. Split it into per-module or per-group tasks, each with its own check and commit. Alternatively, have it list the files first and commit per batch. The guard test can stay red across the batches and go green on the last one.

### [CONCERN] Task 8 is ambiguous about callers that have no profile

For callers without a profile, the task says "fail explicitly or pass what the caller already resolved". This leaves the choice open and could break non-pipeline review paths such as `sq review`. The slice design only says `aiProfile` is written next to `aiModel` and that readers tolerate a missing key. Task 8 should decide which behavior applies. It should also say how many callers `grep` is expected to find, and how each one gets its profile. If some paths legitimately have no profile, the key should probably be omitted rather than raising an error.

### [CONCERN] Task 13 extracts the reference block with a fragile rule

Task 13 takes "lines up to the first blank line" as the reference block. In the real file that rule covers lines 1-36. It includes the "Deprecated" and "Renamed" notes (lines 29-36), which are changelog text and not field reference. The starter would copy them verbatim. The rule also breaks if anyone adds a blank line inside the field list. The project's parsing guidance prefers semantic rules over layout rules. Define the block explicitly, for example by ending it at a marker line or at the `# Fields:` section. Add a test that runs the extraction against the real built-in file and asserts the starter excludes the deprecation notes.

### [CONCERN] Task 2 leaves a failing test until Task 3 ends

Task 2 ends with "Do not commit yet" and a red real-tree test. This is deliberate but fragile. If Task 3 is split as suggested above, the red state spans several commits. Either mark the real-tree test with a temporary xfail, or commit the guard together with the first batch of fixes.

### [NOTE] D4 behavior for old lowercased-path runs has no test

D4 says runs already recorded under a lowercased path "keep that name" and still resume through the path itself. Task 6's "pre-slice state resumes by name" case is close to this, but it doesn't use a path-shaped name. Add a case that uses one, or state that the pre-slice case covers it.

### [NOTE] Task 16's check on `~/.config/squadron` has no method

"Confirm the real `~/.config/squadron` was not modified" gives no way to check it. Suggest taking a mtime or listing snapshot before the suite and the walkthrough, then comparing afterwards.

### [NOTE] Task 17 adds docs and changelog work outside the slice criteria

The docs, CHANGELOG and DEVLOG items are not slice success criteria. They are standard close-out work and no change is needed. They are listed here only for traceability.

### Run Digest

- Response length: 5126 chars
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
- Duration: 30.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
