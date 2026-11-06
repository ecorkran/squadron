---
docType: review
layer: project
reviewType: tasks
slice: fix-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/423-tasks.fix-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 895202055aadde1b0908bbf34aebf314952d70e5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 698211
cachedTokens: 537754
cacheWriteTokens: 160445
completionTokens: 60018
durationSeconds: 254.7
costUsd: 0.190339
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: process
    summary: "Task 1 would commit the planning document onto the slice branch"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:48"
  - id: F002
    severity: concern
    category: sequencing
    summary: "The default fetch path ships in the Task 10 commit with no defined behaviour"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:143"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 11's BLOCKED instruction says \"stop\", and its precondition check is too weak"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:146"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 12 is one task spanning about ten files and four test files"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:154"
  - id: F005
    severity: concern
    category: coverage
    summary: "No live run exercises the target-mode commit the design requires"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:181"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Unreadable git state is unspecified in Tasks 5 and 8"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:84"
  - id: F007
    severity: concern
    category: maintainability
    summary: "The detached-HEAD sentinel is private, so tasks would scatter a literal"
    location: "src/squadron/pipeline/git_ops.py:25"
  - id: F008
    severity: concern
    category: error-handling
    summary: "Logging of caught file errors does not match the exception-handling rule"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:62"
  - id: F009
    severity: concern
    category: maintainability
    summary: "The 40-line budget for `commit.py` pushes it past the 300-line limit"
    location: "src/squadron/pipeline/actions/commit.py"
  - id: F010
    severity: concern
    category: design
    summary: "A `current` commit does not check the branch that fix-context recorded"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:83"
  - id: F011
    severity: concern
    category: coverage
    summary: "No load test for the new network path"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:43"
  - id: F012
    severity: concern
    category: coverage
    summary: "The \"nothing staged\" requirement has no test"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:87"
  - id: F013
    severity: note
    category: design
    summary: "Design and tasks disagree on several points"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:139"
  - id: F014
    severity: note
    category: coverage
    summary: "Task 14 step 4 does not confirm `gh` and `cf` are unreachable"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:179"
  - id: F015
    severity: pass
    category: coverage
    summary: "Criteria coverage, sequencing and test placement"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:46"
  - id: F016
    severity: pass
    category: design
    summary: "Design correction on dispatch fallback is accurate"
    location: "src/squadron/pipeline/actions/dispatch.py:841-845"
  - id: F017
    severity: pass
    category: coverage
    summary: "Cited modules, functions, tests and registration block exist"
    location: "src/squadron/pipeline/executor.py:529"
---

# Review: tasks — slice 423

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 1 would commit the planning document onto the slice branch

Task 1 creates the branch from the target and says "uncommitted planning files carry over". The task file is untracked today, so its commit would land on `423-slice.fix-pipeline`. The branch rules put planning commits directly on the target, before any work branch exists. Add a step to commit the task file to the target first, then create the branch.

### [CONCERN] The default fetch path ships in the Task 10 commit with no defined behaviour

`fix.yaml` defaults `issue-file` to `""` (fetch mode). Task 3 defines only the file branch of `IssueTextLoader`, and Task 11 (fetch) comes after the Task 10 commit. The commit therefore ships a default pipeline path with no implementation, and a junior AI could fill the gap with a silent empty result. Have the non-file branch raise an explicit `IssueTextError` ("fetched issue source not yet available") that Task 11 replaces, or move Task 11 ahead of the Task 10 commit.

### [CONCERN] Task 11's BLOCKED instruction says "stop", and its precondition check is too weak

A block should stop that task, not the run. Tasks 12 and 13 use file mode and do not need 422. As written, "stop" halts them. Also: Task 13 documents the fetched source, and Task 14 step 3 needs Task 11, so both need an explicit rule for when 422 is absent. The check greps only for the names; the design (D3, and the Consumes section at design line 239) also needs `render_issue` to accept a `None` cutoff. Grep for `def get_issue` and `def render_issue` under `src/` currently finds nothing, so this path is live.

### [CONCERN] Task 12 is one task spanning about ten files and four test files

The task covers the new hidden command, `commit_run.py` flags, renderer entries, the `cwd` plumbing in `run.py`, `commands/sq/run.md`, and four test files, with a parity test that has four sub-cases. Split it: 12a renderer entries, `run.md`, and renderer tests (string assertions only); 12b the two hidden commands and their CLI tests; 12c the parity test. Keep the commit marker at the end of 12c.

### [CONCERN] No live run exercises the target-mode commit the design requires

Design criterion F1 (design line 247) requires one new commit on the target from a real issue. Walkthrough step 3 was changed to `-p commit-to=current` in a scratch clone. Tasks 5, 6 and 10 cover target mode only at unit or file-mode level, so the target path never runs end to end. Keep the scratch run, and add one live `commit-to=target` run in a cf-registered checkout with the same test-fails-at-parent check.

### [CONCERN] Unreadable git state is unspecified in Tasks 5 and 8

(a) `read_head` returns `str | None` (`src/squadron/pipeline/head_stamp.py:26`) and yields `None` when git cannot say. Task 8 stores `start_head` from it, and Task 5 compares it, without saying what `None` means. Require an explicit refusal naming "cannot read HEAD". (b) `current_branch` raises `GitEnvironmentError` (`src/squadron/pipeline/git_ops.py:94`). Task 8 catches that error only for `read_integration_target`. (c) The `GitEnvironmentError` docstring (`git_ops.py:35-37`) says it ends the run, but Task 8 turns it into an item failure. State whether that is intended, since 424 may run this step repeatedly.

### [CONCERN] The detached-HEAD sentinel is private, so tasks would scatter a literal

`_DETACHED_HEAD = "(detached HEAD)"` is private. Tasks 5 (line 83) and 8 (line 116) say "detached HEAD" without naming how to detect it. A junior AI would either import a private name or repeat the string, which the project's comparison-value rule forbids. Add a step to Task 2 that exposes a public constant (or an `is_detached` helper) in `git_ops.py`, and use it in both places.

### [CONCERN] Logging of caught file errors does not match the exception-handling rule

Task 3 converts a missing, unreadable or non-UTF-8 file into `IssueTextError` and logs it at WARNING. Catching `OSError` or `UnicodeDecodeError` and re-raising under a new type falls under rule (a): `logger.exception` at ERROR. WARNING fits only a pre-check that does not catch anything. Specify which branch each handler uses.

### [CONCERN] The 40-line budget for `commit.py` pushes it past the 300-line limit

The file is 286 lines (verified). Task 6 (line 94) allows about 40 more, which gives about 326, over the ~300-line guideline. Cap the FIX branch in `commit.py` at about 14 lines, delegating the rest to `fix_commit.py`.

### [CONCERN] A `current` commit does not check the branch that fix-context recorded

Design D5 (line 163) says the `current` destination is "the branch checked out when `fix-context` runs". No output records that branch. Under `current`, Task 5 checks only that HEAD is not detached. A dispatch that switches to another branch at the same SHA would go undetected, and the commit would land there. Add `start_branch` to the `fix-context` outputs and to `FixCommitRequest`, and compare it under `current` as well.

### [CONCERN] No load test for the new network path

The task says "Load test: none ... nothing here is concurrent or latency-bounded". The project rule in `python.md` keys on path type, not latency: code on network paths needs at least one load test in `tests/load/`, and CI must gate it. Task 11 adds a GitHub fetch through a host subprocess. Either add a load-test step and CI wiring (exercising the 30-second timeout and a realistic issue size), or record why the rule does not apply.

### [CONCERN] The "nothing staged" requirement has no test

Design line 262 lists "nothing staged" as a required unit test for `fix_commit_plan`. Task 5 says the function stages nothing, but no listed test asserts it. Add an assertion in `test_fix_commit.py` that `git diff --cached --quiet` passes after the plan is built.

### [NOTE] Design and tasks disagree on several points

The design says `DispatchAction` does not change (line 139). Task 7 changes it, and the task file also corrects D6 (attribution), D8 (`importlib.resources` versus `data_dir`) and the enum name clash. The task file's correction list is the only record of these. Amend the design, or add a corrections note to it, so 424, 425 and reviewers read one spec.

### [NOTE] Task 14 step 4 does not confirm `gh` and `cf` are unreachable

The design's claim that neither tool is on `PATH` depends on the restricted `PATH`. Using `dirname(command -v sq)` can keep other tools that share that directory. Add a check that `command -v gh cf` returns nothing under the restricted environment before the run.

### [PASS] Criteria coverage, sequencing and test placement

Every functional, technical and integration criterion (design lines 247–271) maps to at least one task. Tests sit inside their implementation tasks. The order runs pure modules, then the commit, the action, the step, the executor, prompt-only, docs and verification, with no cycles. Task 8 runs git and file work through `asyncio.to_thread`, as the async rule requires. I found no scope creep.

### [PASS] Design correction on dispatch fallback is accurate

The fallback loop gates on `ActionType.CF_OP` and `operation == build_context`, so Task 7 is needed. No attribution or "Co-Authored" lines appear anywhere in `src/`, so the message format in Tasks 5 and 6 is correct.

### [PASS] Cited modules, functions, tests and registration block exist

Verified: `read_integration_target` (`git_ops.py:64`), `results_for_step` (`models.py:58`), `extract_json_object` (`dispatch_io.py:56`), `path_error` (`dispatch_keys.py:41`), `run_test_git` (`tests/conftest.py:175`), the executor registration block (`executor.py:529`), `commands/sq/run.md`, `docs/PIPELINES.md`, `tests/docs/`, and the existing test files Task 10 and Task 12 name. The one gap is 422 (see the BLOCKED finding).

### Run Digest

- Response length: 11069 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 698211 / 537754 / 160445 / 60018 / not computed
- Duration: 254.7 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
