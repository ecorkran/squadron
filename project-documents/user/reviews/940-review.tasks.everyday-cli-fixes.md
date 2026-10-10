---
docType: review
layer: project
reviewType: tasks
slice: everyday-cli-fixes
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/940-tasks.everyday-cli-fixes.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261009
dateUpdated: 20261009
reviewedSha: 5d9adb9b3bcfc8bd809fa6b28f747c26128389ec
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 14.8
runId: run-20261010-p5-4e5bc315
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Functional success criteria are all covered"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Every D8 failure-mode row has a test"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:206-216"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern are sound"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:35-290"
  - id: F004
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating obligation"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md:122-138"
  - id: F005
    severity: note
    category: scope
    summary: "Guard test cannot catch user text that never passed through an exception"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:63"
  - id: F006
    severity: note
    category: testing
    summary: "Task 8 hand-check of the guard"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:103"
  - id: F007
    severity: note
    category: task-size
    summary: "Task 13 is large but cohesive"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:158-168"
  - id: F008
    severity: note
    category: scope
    summary: "Tasks 22 and 23 are verification and close-out, not design criteria"
    location: "project-documents/user/tasks/940-tasks.everyday-cli-fixes.md:273-290"
---

# Review: tasks — slice 940

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Functional success criteria are all covered

Every functional criterion maps to a task:
- `pipelines copy` byte-identical output, shadow notice, `load_pipeline` loading the copy, and `--project` scope: Tasks 15-16.
- Second copy refused without `--force`: Task 16.
- `list` marks a shadowing copy: Task 17.
- `models init` parses as TOML, defines no aliases, and a second run is refused: Tasks 18-19.
- Path runs record `foo` plus the absolute path, and `--resume` reloads the same file: Tasks 9-11.
- `[codex]` prints intact: Tasks 2-8, with the behavior test in Task 4.
- `-v` shows the profile and `aiProfile` appears in the artifact: Tasks 12-13.

The technical requirements (guard test, pre-slice state loads, temp-home tests, lint/type/test cleanliness) are covered by Tasks 2/8, 9/11, the Context Summary, and Task 22.

### [PASS] Every D8 failure-mode row has a test

Each D8 row has a test asserting both the exit code and the message or log record:
- Target exists: Tasks 16 and 19.
- Write `OSError`: Tasks 14, 16 and 19.
- Unknown name: Task 16.
- Source unreadable or gone between resolve and read: Task 16.
- Partial file removed after a failed write: Tasks 14, 16 and 19.
- Unreadable built-in `models.toml`: Task 19.
- Empty reference block: Task 18.
- Recorded `pipeline_path` missing, or present but invalid: Task 11.

### [PASS] Sequencing and test-with pattern are sound

Order follows the design's Implementation Notes (D5, D4, D6, then D3, D1, D2, D7).
- Dependencies run forward only. Task 14 (helper) comes before Tasks 16 and 19. Task 15 (loader dirs) comes before Task 16. Task 17 (shadow field) comes before Task 21 (color). Task 18 comes before Task 19. Task 12 comes before Task 13.
- Each implementation task carries its own tests, and there is a commit after each task, not batched at the end.
- Task 2's shrinking `_UNSWEPT` allowlist keeps the tree green while the sweep proceeds across Tasks 3-8.
- No merge task appears, which is consistent with the project's Git rules.

### [PASS] No load-test or CI-gating obligation

The slice design restates no NFR (no performance, throughput or latency targets), so no `tests/load/` task or CI wiring task is required.

### [NOTE] Guard test cannot catch user text that never passed through an exception

This is a known limit, acknowledged in the slice's D5. Task 3's "inspect every site" instruction plus Task 21's manual-escape note cover it for now. No change is needed.

### [NOTE] Task 8 hand-check of the guard

The "add an unescaped print, see it fail, revert" step is manual. Task 2's self-test already proves the checker flags unescaped sites, so the manual step is a harmless extra check and not a gap.

### [NOTE] Task 13 is large but cohesive

This task threads the profile through two writers and an unspecified number of callers, then validates frontmatter. A junior AI can complete it because the steps are explicit (grep for callers, list them in the commit body). If the caller count turns out to be large, split it into the writer change and a caller-wiring task.

### [NOTE] Tasks 22 and 23 are verification and close-out, not design criteria

These do not trace to a specific success criterion, but they implement the Technical Requirements (clean lint/type/test, no writes to the real config) and the Verification Walkthrough. They are not scope creep. Task 22's baseline-before-tests step is a good safeguard for the temp-home requirement.

### Run Digest

- Response length: 4234 chars
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
- Duration: 14.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
