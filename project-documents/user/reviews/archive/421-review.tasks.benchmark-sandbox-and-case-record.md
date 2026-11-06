---
docType: review
layer: project
reviewType: tasks
slice: benchmark-sandbox-and-case-record
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: a7d3c82649affe728281b78181078f4c11b8500d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
effort: xhigh
turns: 13
promptTokens: 559118
cachedTokens: 399789
cacheWriteTokens: 159319
completionTokens: 53120
durationSeconds: 231.4
costUsd: 0.299897
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered and the workflow rules hold"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md"
  - id: F002
    severity: concern
    category: consistency
    summary: "Task 3 edits a replay test file that Tasks 11 and 29 require unchanged"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:57"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 9 may record a `no` from a `sq` that lacks the probe command"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:111"
  - id: F004
    severity: concern
    category: sequencing
    summary: "The benchmark orphan sweep has no call site"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:245"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Task 1's clean-tree check fails on the current state"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:45"
  - id: F006
    severity: concern
    category: traceability
    summary: "The parent design still says `env=` applies the scrub, which the code refutes"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md:64"
  - id: F007
    severity: concern
    category: sequencing
    summary: "A sleeping node in the shared fixture will stall non-timeout suite runs"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:191"
  - id: F008
    severity: note
    category: clarity
    summary: "The auth check's behavior for a missing granted variable is unspecified"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:93"
  - id: F009
    severity: note
    category: clarity
    summary: "Several steps leave inputs to the implementer"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:74"
  - id: F010
    severity: note
    category: traceability
    summary: "The task file adds modules and an error the design doesn't list"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md:81"
  - id: F011
    severity: note
    category: coverage
    summary: "The load-test tier may apply to the sandbox"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md"
  - id: F012
    severity: note
    category: proportionality
    summary: "Some tests and a commit exceed what the success criteria need"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:47"
---

# Review: tasks — slice 421

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria are covered and the workflow rules hold

FR1 and FR2 map to Tasks 12, 14 and 15. FR3 and walkthrough step 2 map to Tasks 18, 27 and 28. FR4 maps to Task 18. FR5 maps to Task 26. FR6 maps to Tasks 7–9. FR7 and TR4 map to Tasks 19 and 21–23. TR1 maps to Tasks 11 and 29. TR2 maps to Tasks 18 and 22. TR3 maps to Tasks 5 and 26. IR2 maps to Tasks 10, 11 and 28. Walkthrough steps 1–7 each have a task. The design restates no NFR, so no load test is missing on that basis. No merge or push appears as a task. Commit markers are plain lines, and every checklist item has a checkbox.

### [CONCERN] Task 3 edits a replay test file that Tasks 11 and 29 require unchanged

Task 3 requires updating every fake `ProcessRunner` in `tests/`. Its own grep pattern matches `tests/replay/sandbox_support.py:30`, so Task 3 edits `tests/replay/`. Task 11 says the replay tests pass "with no test edits" (line 129), and Task 29 says `tests/replay/` is "unchanged" (line 280). Those can't all hold. Fix: say the Task 3 fake edit is allowed, take the Task 10 baseline after Task 3, and limit the no-edit rule to the Task 11 extraction.

### [CONCERN] Task 9 may record a `no` from a `sq` that lacks the probe command

The probe runs whatever `sq` `shutil.which` finds on the harness PATH (Task 7, design D8). Task 9 doesn't check that this is the branch's build. A released or stale `sq` has no `benchmark _auth-probe`, so the probe exits non-zero and reports `no`, and that `no` is recorded as the PM's answer. Add a step: confirm the printed probed path is this checkout's install, and that `sq benchmark _auth-probe --help` runs, before the auth check.

### [CONCERN] The benchmark orphan sweep has no call site

Task 25 extends the directory sweep, and Task 28 step 7 expects a rerun to sweep an orphan with a WARNING. The `__enter__` order on line 243 never calls the sweep. In the existing code the sweep is called from `src/squadron/replay/runner.py:179`, not from the sandbox. Name the benchmark call site (sandbox enter or the CLI) so step 7 can pass. Also say which `sweep_orphans` is extended: `replay/sandbox.py:235` already takes an optional `root`, and a second function with the same name exists at `codehost/worktree.py:138`. That affects Task 11's "takes `root` and a flag" wording too.

### [CONCERN] Task 1's clean-tree check fails on the current state

The session's starting git status shows the task file modified and uncommitted on `main`. Task 1 requires `git status` to be clean after branching. The planning artifacts must be committed to the target first, per the planning cadence, so the slice branch forks from a clean tree. Add that as a prerequisite of Task 1.

### [CONCERN] The parent design still says `env=` applies the scrub, which the code refutes

Line 64 and D7 (line 174) say `ProcessRunner.run(env=...)` gives every child the scrubbed environment. `SubprocessRunner.run` merges `env` over `os.environ` (`src/squadron/core/process_runner.py:118`), so `GH_TOKEN` and the other credentials would survive. Task 3 fixes this by adding `replace_env`, but the correction lives only in the task file's context summary. The design, which the task file cites as its parent, should record the correction and the new keyword so 422–427 don't build on the wrong claim.

### [CONCERN] A sleeping node in the shared fixture will stall non-timeout suite runs

Task 19 puts a node that "sleeps well past the suite timeout used in Task 23" in the shared `classify_project`. Task 20 runs that project with no timeout and no deselect, so it waits out the full sleep. Any all-tests run in Tasks 22–23 does the same unless the node is deselected. Task 19 also doesn't give the timeout value, so the link between the two tasks is unclear. Fix: put the sleeping node in its own fixture, and name the small `suite_timeout_s` in Task 23.

### [NOTE] The auth check's behavior for a missing granted variable is unspecified

Task 5 raises a named error when a granted variable is absent from `harness_env`. Task 7 builds each probe's grant without saying what happens when an API-key alias has no key set. The row could become `no`, or the command could abort. Task 8 specifies exit behavior only for an unknown alias and a missing `sq`. Pick one and add a test.

### [NOTE] Several steps leave inputs to the implementer

- Task 5 doesn't give the fixed benchmark `user.name` and `user.email`.
- Task 28 uses `$REV` without defining it. The design's example `v0.20.0` is unverified to contain a `uv.lock`. Name a REV and check `git cat-file -e REV:uv.lock`.
- Task 19 doesn't say where `pkg` lives. `pythonpath = ["src"]` implies `src/pkg/`.

### [NOTE] The task file adds modules and an error the design doesn't list

`benchmark/alias_profile.py` (Task 6), `pytest_reporter/reporter_format.py` (Task 20) and `UnresolvedProfileError` (Tasks 6–7) are not in the design's component structure or error list. Each is justified: the probe needs alias-to-profile resolution, and the plugin can't import the harness. Add them to the design so the design stays the source of truth.

### [NOTE] The load-test tier may apply to the sandbox

`python.md` requires a `tests/load/` test, with CI gating, for code on "environment-layer" paths. The repo doesn't define that term; the concept guide uses it only as an example component. The sandbox's lock, sweep and process-group timeout paths resemble worktree concurrency, which already has `tests/load/test_worktree_concurrency.py`. Ask the PM whether this slice counts. If it does, add a load task and a CI gate. The breakdown has neither.

### [NOTE] Some tests and a commit exceed what the success criteria need

Config-key tests appear in Tasks 2, 18 and 22, and no success criterion mentions config keys. Task 16's test that `FailureKind` has five values repeats the enum's own definition. Task 2's one-key commit could fold into Task 3's. These are cheap, but merging them would trim the 29-task list without losing coverage. The file is otherwise proportionate to a 3/5-effort slice.

### Run Digest

- Response length: 8732 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 559118 / 399789 / 159319 / 53120 / not computed
- Duration: 231.4 s
- Cost: $0.30 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
