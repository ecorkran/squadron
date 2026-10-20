---
docType: review
layer: project
reviewType: tasks
slice: dispatcher-routing-and-documentation
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: bbd4182dcda0664b794ecee1d8be0cca80f61a77
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 192288
cachedTokens: 92864
cacheWriteTokens: 99418
completionTokens: 14612
durationSeconds: 70.9
costUsd: 0.028851
costBasis: provider
runId: run-20261020-p5-9edaa59e
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Unreadable dispatcher file is not handled in surface detection"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:213-221"
  - id: F002
    severity: concern
    category: testing
    summary: "README and CHANGELOG presence has no verification step"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:317-318"
  - id: F003
    severity: note
    category: sizing
    summary: "Task 3 is smaller than a task and could merge into Task 2"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:133-138"
  - id: F004
    severity: note
    category: proportionality
    summary: "Tasks 11 and 12 run overlapping test commands"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:340-341"
  - id: F005
    severity: note
    category: testing
    summary: "Stdout-purity test should assert on `result.stdout`, not `result.output`"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:288-292"
  - id: F006
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies, and commit checkpoints"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:86-345"
---

# Review: tasks — slice 366

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Unreadable dispatcher file is not handled in surface detection

Task 6 says a dispatcher with no `Valid skills:` line becomes `null` with a WARNING, and Task 7 adds OSError handling only for the plugin file. Nothing says what happens when `sq/analysis.md` or `analysis/understand.md` exists but cannot be read. Under D6 that exception escapes `build_probe`, and the whole probe exits 1. D8 uses `null` for exactly this kind of unknown state, and the review rules require failure modes to be explicit. Add to Task 6: a read `OSError` on a dispatcher or skill file yields `null` with a WARNING naming the file, plus a test case.

### [CONCERN] README and CHANGELOG presence has no verification step

The design's Technical Requirements say the README subsection, the `sq probe` line, and the CHANGELOG bullets "are present." Task 10's success check only runs the install-guidance test, which checks the three install commands and nothing else. The walkthrough (Task 11) also does not cover these. Nothing confirms the requirement is met. Add a grep check to Task 10 or Task 12, for example `docs/COMMANDS.md` containing `## probe`, the README containing `#probe`, and the CHANGELOG `[Unreleased]` section containing both `understand` and `sq probe`.

### [NOTE] Task 3 is smaller than a task and could merge into Task 2

Task 3 is one assertion in an existing test class, at Effort 1/5, with its own commit. Merging it into Task 2's commit, or keeping it as a sub-item there, would reduce commit granularity without losing any check.

### [NOTE] Tasks 11 and 12 run overlapping test commands

Task 12 runs `tests/skills`, `tests/probe`, and `test_probe.py`, and Task 11 step 8 covers the skills and probe tests as well. Keeping both is acceptable, but Task 12 could say to run only the full suite, since it already includes those paths.

### [NOTE] Stdout-purity test should assert on `result.stdout`, not `result.output`

The Task 9 case "a run that logs a WARNING keeps stdout pure JSON" only means something if it reads stdout separately from stderr. Depending on the Click version, `result.output` can combine the two streams. Say in the task to assert on `result.stdout`.

### [PASS] Sequencing, dependencies, and commit checkpoints

Dependencies run in one direction: parser (1) → dispatchers and drift test (2) → install guidance (4) → report types and graph (5) → surfaces (6) → plugin field (7) → `build_probe` (8) → CLI (9) → docs (10) → walkthrough (11) → final validation (12). Task 6 adds the surface spec without the plugin field, and Task 7 adds it afterward, so there is no circularity. Each implementation task has a test in the same task. Commit checkpoints appear after Tasks 1–12, not batched at the end. The task file correctly contains no merge steps.

### Run Digest

- Response length: 4213 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 192288 / 92864 / 99418 / 14612 / not computed
- Duration: 70.9 s
- Cost: $0.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
