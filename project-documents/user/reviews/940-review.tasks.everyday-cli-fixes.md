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
reviewedSha: aea4e817e386e9a1fea35a35c04c2e15351bf7c0
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 29.9
runId: run-20261010-p5-4e5bc315
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit cadence"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 20 lists the baseline marker after the step it must precede"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:261-266"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 17 changes the built-in `models.toml` and departs from the D2 design"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:223"
  - id: F005
    severity: note
    category: task-sizing
    summary: "Task 17 is on the large side"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:220-237"
  - id: F006
    severity: note
    category: clarity
    summary: "Allowlist removal instructions assume every swept file is in `_UNSWEPT`"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:64"
  - id: F007
    severity: note
    category: task-sizing
    summary: "Task 7 covers many files in one commit"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:91-97"
---

# Review: tasks — slice 940

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

Every functional and technical requirement in the slice design maps to at least one task.
- **Copy and list:** the copy criteria are covered by Tasks 13-16, and the list-marking criterion by Task 16.
- **Models init:** the `models init` criteria are covered by Tasks 13 and 17, with the doctor pointer in Task 18.
- **Path runs:** the path-run criteria are covered by Tasks 8-10.
- **Rich escaping:** the `[codex]` criterion is covered by Task 4, and the guard test by Tasks 2-7.
- **Review profile:** the `-v` profile and `aiProfile` criteria are covered by Tasks 11-12.
- **D7:** the list-color decision is covered by Task 19.
- **D8 failure modes:** every row of the failure-mode table has a matching test bullet in Tasks 10, 15 and 17.
- **Technical requirements:** the lint, pyright, full-suite, pre-slice-state and temp-home requirements are covered by Tasks 8, 10 and 20.

No tasks trace to nothing, apart from the Task 17 point below.

### [PASS] Sequencing, test-with pattern and commit cadence

Dependencies run in one direction, with no cycles.
- Task 13 (the helper) comes before its users, Tasks 15 and 17.
- Task 14 (the loader) comes before Task 15.
- Task 16 (shadow marking) comes before Task 19 (coloring the marker).
- Task 11 comes before Task 12, which threads its profile through.

Each implementation task carries its own tests and its own semantic commit, so commits are spread across the work and not batched at the end. The Task 2-7 allowlist shrinks as each module is swept, which keeps the guard test green throughout. No merge task exists, which matches the git rules. No performance NFR is restated in the slice, so no load test or CI-gating task is required.

### [CONCERN] Task 20 lists the baseline marker after the step it must precede

The first bullet runs the full test suite. The second bullet says "Before running the full suite, create a marker" and records the `~/.config/squadron` baseline. A junior agent working top to bottom will run the suite first, so the baseline is taken after any writes and the check that the real config was untouched becomes meaningless. Move the marker and baseline bullet above the suite run. The marker must also exist before the walkthrough, which is also meant to be covered by the final check.

### [CONCERN] Task 17 changes the built-in `models.toml` and departs from the D2 design

D2 says the field reference is "the leading comment block of the built-in `data/models.toml`" and that `init` reads it at write time. Task 17 instead edits the built-in file. It adds `BEGIN`/`END` marker comments and moves the "Deprecated" and "Renamed" notes below the END marker. It also adds marker constants and a marker-validation error path. This is a reasonable hardening, since it avoids fragile header parsing, and it adds tests for the missing, reversed and empty-block cases. However, the slice design neither mentions nor authorizes it. Either update D2 to describe the marker approach, or confirm with the PM that the built-in file edit is intended. Moving the notes could also affect anything that reads the file, so the task should say to check for other consumers of those comments.

### [NOTE] Task 17 is on the large side

Task 17 bundles the built-in file edit, the extraction function with marker validation, the `init` command, and seven test groups. It could be split into "extract reference block" (with its tests) and "`sq models init` command" (with its tests). That would give two commits and a smaller unit per junior agent. This is optional, since the task is still completable as written.

### [NOTE] Allowlist removal instructions assume every swept file is in `_UNSWEPT`

Tasks 3-6 say "Remove the swept files from `_UNSWEPT`". `_UNSWEPT` only holds files that had flagged sites when Task 2 built it. A listed file with no flagged sites will not be in the set, so there is nothing to remove. Add "if present" to those steps. Task 7 should also say that its file list is whatever the grep returns, which it already does.

### [NOTE] Task 7 covers many files in one commit

Task 7 sweeps roughly eleven modules and retires the allowlist in a single commit. It is mechanical and low risk, and the guard test bounds the work. If the actual flagged set is large, split it by module group so a revert stays small.

### Run Digest

- Response length: 5028 chars
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
- Duration: 29.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
