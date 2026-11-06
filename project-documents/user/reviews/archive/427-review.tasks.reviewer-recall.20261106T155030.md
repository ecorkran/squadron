---
docType: review
layer: project
reviewType: tasks
slice: reviewer-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/427-tasks.reviewer-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: a8852faa12fa768219a8868c159f0051a46cce06
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 918726
cachedTokens: 733853
cacheWriteTokens: 184859
completionTokens: 87562
durationSeconds: 370.7
costUsd: 0.428076
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:391-412"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test pattern hold"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md"
  - id: F003
    severity: pass
    category: consistency
    summary: "The 425 facts that Task 1 relies on check out"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:48"
  - id: F004
    severity: concern
    category: correctness
    summary: "Spacing rule is off by one between the task and its own test"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:163-164"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Task 8 copies 421's project-source rule before the gate that forbids copies"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:113"
  - id: F006
    severity: concern
    category: coverage
    summary: "No task registers the recall adapter"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:98-103"
  - id: F007
    severity: concern
    category: correctness
    summary: "The `--limit` default is never given"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:192"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 40's line-count check conflicts with a 522-line shared file"
    location: "src/squadron/config/keys.py"
  - id: F009
    severity: concern
    category: commit-cadence
    summary: "Task 10's refactor has no commit marker"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:126-130"
  - id: F010
    severity: concern
    category: dependency
    summary: "Task 38 edits a file created by 422, which the design says 427 does not depend on"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:291-296"
  - id: F011
    severity: concern
    category: coverage
    summary: "The normalization step is unnamed"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:242-245"
  - id: F012
    severity: concern
    category: error-handling
    summary: "Store-write failures are untested where the task file says they must be"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:137-143"
  - id: F013
    severity: concern
    category: proportionality
    summary: "Duplicate and thin tasks make the file heavier than the slice needs"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:197-199"
  - id: F014
    severity: note
    category: consistency
    summary: "The design still disagrees with the tasks in places Task 1's bullets do not name"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:80-97"
  - id: F015
    severity: note
    category: convention
    summary: "Severity literals should come from the existing enum"
    location: "src/squadron/metrology/review_models.py:24"
  - id: F016
    severity: note
    category: scope
    summary: "Task 7 adds a constraint to the operator table that D3 does not contain"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:106"
  - id: F017
    severity: note
    category: dependency
    summary: "Task 10's gate omits names that Task 12 reuses"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:127"
  - id: F018
    severity: note
    category: dependency
    summary: "Walkthrough step 5 needs a graded benchmark that no task creates"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:306"
  - id: F019
    severity: note
    category: sequencing
    summary: "Task 16 forward-references the matcher stub"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:163"
  - id: F020
    severity: note
    category: proportionality
    summary: "Task 13 bundles six fixture projects and a repo helper under one criterion"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:145-149"
---

# Review: tasks — slice 427

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria are covered by tasks

Functional (391–399), technical (401–407) and integration (409–412) criteria, and all seven walkthrough steps, map to tasks. Examples: the matcher cases to Tasks 24–25, the line-shift planter test to Tasks 5 and 16, absences and rejections to Tasks 18, 30 and 31, the `review_flag` change to Tasks 35–36, and walkthrough steps 1–7 to Tasks 22, 23, 33 and 39.

### [PASS] Sequencing and test pattern hold

Apart from Task 8 (below), each task depends only on earlier tasks. Task 10 is a dependency gate, which is the right use of BLOCKED for 421–425 names not yet built. Every implementation task has its tests inline or immediately after. No task merges or pushes. Task 1 corrects the design before the slice branch is cut.

### [PASS] The 425 facts that Task 1 relies on check out

425 Task 7 (line 48) drops `rules_hash` from `ReviewerRef`. 425 Task 38 (line 315) gives `review_flag(reviewer)` the text that Task 36 changes. I did not verify `bootstrap_mean_interval`, `pair_seed` or `compare_pair`, because the grep output truncated those lines. Task 10's gate covers them.

### [CONCERN] Spacing rule is off by one between the task and its own test

Task 16 says a kept defect blocks sites "within `2W+1` lines". Its test then says distance `2W` is blocked and `2W+1` is allowed. Under the usual meaning of "within", those cannot both hold. The test is the right one: a one-line finding can fall in both defects' windows only when they are at most `2W` apart. Reword Task 16 and design lines 190 and 395 to "blocks distance ≤ 2W", so the criterion, the step and the test agree.

### [CONCERN] Task 8 copies 421's project-source rule before the gate that forbids copies

Task 8 (committed at the Task 9 marker, line 124) implements `is_source_path` with the test-module patterns and the `.venv` rule written out. Task 10 (lines 129–130) then requires it to call 421's rule, "not a copy". If 421 is absent at that point, the copy ships and the gate blocks. Move the `is_source_path` body to after the Task 10 gate.

### [CONCERN] No task registers the recall adapter

Design line 90 lists `registry.py + recall adapters`, and line 99 says `recall_build` reaches Python only through the registry. Task 6 creates `PythonRecallAdapter`, but no task registers it under `SourceLanguage.PYTHON`. Task 18 injects an "adapter registry", and Task 21's `build_deps()` is not told to register anything. Without this step, the real build in Task 19 has no adapter to plant with. Add a registration step with a test to Task 6 or Task 21.

### [CONCERN] The `--limit` default is never given

Task 21's test checks "`--limit` default", but neither this task nor design line 283 gives a value or says where one lives. AGENTS.md requires defaults to be centralized, so an implementer would invent a magic number. Name the value and its constant or config key.

### [CONCERN] Task 40's line-count check conflicts with a 522-line shared file

Task 40 (line 319) fails any source file the slice changed that exceeds ~300 lines, and asks for a split. `config/keys.py` is 522 lines, and Task 2 (line 75) adds to it. The check would force an unplanned split of a file other slices share. Limit the check to files this slice creates, or name the split as a task. `metrology/models.py` is 263 lines and grows in Task 12, so watch it when that task runs.

### [CONCERN] Task 10's refactor has no commit marker

Task 10 (line 129) asks for the 421 rule and the 424 lock helper to be made reusable "in a `refactor:` change". It has no **Commit** marker, so the refactor lands in Task 12's `feat:` commit (line 143). That mixes a refactor of 421 and 424 code into a feature commit. Add a marker after the refactor step, and say to skip it when no refactor is needed.

### [CONCERN] Task 38 edits a file created by 422, which the design says 427 does not depend on

Task 38 adds recall subcommands to `commands/sq/benchmark.md`. That file does not exist in the repo yet. Task 422 creates it (422 task line 322), and 424, 425 and 426 also edit it. The design says 427 does not depend on 422 or 426 (design lines 6 and 67), so this ordering is undeclared. Declare 422 as a prerequisite for Task 38, or say that Task 38 creates the file in 422's form if it is absent.

### [CONCERN] The normalization step is unnamed

Design line 366 says `RecallReview.findings` holds normalized findings, and line 386 says normalization is consumed from 402. Task 30 writes "findings, `unnormalized_count`", but no step says which code normalizes them. `normalize_result_categories` appears only in Task 10's existence list. Name the call in Task 30, or state that 425's `review_tree_diff` already returns normalized findings and test for it.

### [CONCERN] Store-write failures are untested where the task file says they must be

The Context Summary (line 55) requires each new I/O path to have a test for its observable failure signal, and names "a store write failure". Only Task 31 tests one, for the runner. Task 12 (store writes, which log ERROR and raise, line 138) and Task 18 (build writes, which stop and log ERROR, line 175) have no failure test. Add one test to each.

### [CONCERN] Duplicate and thin tasks make the file heavier than the slice needs

- Task 22 (lines 197–199) repeats Task 19's assertion (the proving node fails with the edit and passes without it) and Task 39 step 2 (line 300). It has no commit. Drop it.
- Task 33 (lines 261–263) is the same live command as Task 39 step 3 (line 302), with one alias. Keep one of the two live runs.
- Merge Task 3 into Task 4. Both are small, and Task 4's test is a pyright check that pytest cannot assert.
- Merge Task 15 into Task 14. It extends Task 14's test file.
- Cut Task 27's grep-style test (line 227). It checks a code-review rule rather than a success criterion.

Net: 40 tasks drop to about 36.

### [NOTE] The design still disagrees with the tasks in places Task 1's bullets do not name

Component Structure has no `recall_stats.py` (Task 26) or `recall_report_render.py` (Task 37). D11 (line 255) names the first parameter `store`, but Task 35 (line 271) uses `records`. The integration criterion (line 411) says "no other change to 425's report code", but Task 36 (line 278) changes the call site. Add these to Task 1's list.

### [NOTE] Severity literals should come from the existing enum

Task 24 (line 209) hardcodes "NOTE, CONCERN, FAIL". `CodeReviewFinding.severity` is typed `Severity`. Reference the enum members so the scale is defined once.

### [NOTE] Task 7 adds a constraint to the operator table that D3 does not contain

Task 7 narrows `guard-drop` to "has no `else`". D3 (design line 179) says only "an `if` whose body is only `raise` or `return`". Either move the narrowing into D3 and note the effect on the table version, or remove it.

### [NOTE] Task 10's gate omits names that Task 12 reuses

Task 12 (line 138) reuses 421's `write_record` and `iter_records`, and Task 10's list does not check them. Add them to the gate. They are absent from `src/squadron` today, which is expected before 421 lands.

### [NOTE] Walkthrough step 5 needs a graded benchmark that no task creates

Step 5 runs `sq benchmark report <bench-id>` on a graded 425 benchmark, and no task here produces one. The general BLOCKED clause (line 299) covers it, but name where that benchmark comes from so the step does not stall silently.

### [NOTE] Task 16 forward-references the matcher stub

Task 16 creates `recall_match.py` with two constants and says Task 24 completes it. There is no cycle, but the planter then depends on a half-written module. Put the constants in Task 16 and let Task 24 add to them, and say so in both tasks.

### [NOTE] Task 13 bundles six fixture projects and a repo helper under one criterion

Six uv projects, six behaviours and a git-repo builder form one task. Consider splitting it into two (proof fixtures; hang, unselected and flaky fixtures) if a junior run is likely to stall partway.

### Run Digest

- Response length: 11913 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 918726 / 733853 / 184859 / 87562 / not computed
- Duration: 370.7 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20
