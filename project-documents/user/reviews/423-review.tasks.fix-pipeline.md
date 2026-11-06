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
reviewedSha: fd3afac8601f315bcfc0cbff8ff294048ff66aa0
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
effort: xhigh
turns: 32
promptTokens: 1428771
cachedTokens: 1249638
cacheWriteTokens: 179111
completionTokens: 62970
durationSeconds: 277.3
costUsd: 0.268089
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 14 is held behind 422 although it does not depend on it"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:191"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 14 documents fetch mode before Task 15 builds it"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:183"
  - id: F003
    severity: concern
    category: scope
    summary: "The \"amend the design\" step contradicts the Context Summary and is out of scope"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:185"
  - id: F004
    severity: concern
    category: verification
    summary: "CI gating of the load test is assumed, not verified"
    location: ".github/workflows/ci.yml:38"
  - id: F005
    severity: concern
    category: sequencing
    summary: "The only load test waits on 422, but the concurrency it guards lands in Task 9"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:199"
  - id: F006
    severity: concern
    category: completeness
    summary: "The scrubbed-environment integration criterion has no verifying task"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:154"
  - id: F007
    severity: concern
    category: verification
    summary: "Walkthrough step 3 proves a scratch target, not squadron's target"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:218"
  - id: F008
    severity: note
    category: verification
    summary: "Walkthrough step 6 is waived, so the live `/sq:run` path is untested"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:220"
  - id: F009
    severity: note
    category: complexity
    summary: "The `--io-dir` branch in the renderer cannot be reached from `sq run --prompt-only`"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:169"
  - id: F010
    severity: note
    category: clarity
    summary: "Task 1's commit instruction does not fit the current state of the task file"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:51"
  - id: F011
    severity: note
    category: clarity
    summary: "Task 9's registration path is incomplete"
    location: "src/squadron/pipeline/executor.py:529"
  - id: F012
    severity: note
    category: clarity
    summary: "Task 13 names a test file that does not exist, without saying to create it"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:171"
  - id: F013
    severity: note
    category: error-handling
    summary: "Task 4 leaves an empty or non-string `blocked` undefined"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:78"
  - id: F014
    severity: note
    category: error-handling
    summary: "Task 10's placeholder exemption is broader than it needs to be"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:140"
  - id: F015
    severity: note
    category: proportionality
    summary: "Task count and some duplicated tests are heavier than the slice needs"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md"
  - id: F016
    severity: pass
    category: verification
    summary: "The design corrections and the coverage map check out"
    location: "src/squadron/pipeline/actions/dispatch.py:842"
---

# Review: tasks — slice 423

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 14 is held behind 422 although it does not depend on it

The BLOCKED note in Task 15 says "(Tasks 14–15 wait for it)". Task 14 (docs and CHANGELOG) has no dependency on 422: the fetched source is deferred to Task 15, and the Context Summary (line 33) says Tasks 1–14 are complete without 422. The process rule is that independent work continues when one part is blocked, so Task 14 should not wait. Narrow the note to Task 15 only.

### [CONCERN] Task 14 documents fetch mode before Task 15 builds it

The CHANGELOG bullet in Task 14 says "`sq run fix <issue>` makes a fix…". Until Task 15, default (fetch) mode fails explicitly (Task 3, and the not-built-yet case in Task 11). So at Task 14's commit, the success line "the docs describe only behavior that exists" (line 184) is false. Task 14 should document `issue-file` mode only, and Task 15 should add the fetched mode, which lines 181 and 201 already partly do.

### [CONCERN] The "amend the design" step contradicts the Context Summary and is out of scope

Line 34 says "the design is not edited; these tasks follow the corrections". Line 185 then has Task 14 amend `423-slice.fix-pipeline.md` and set its `dateUpdated`. The design's Technical Scope (lines 28–43) limits docs to `docs/PIPELINES.md` and the CHANGELOG, and no success criterion requires the amendment. Either drop line 185 and keep the corrections in the task file, or change line 34 and make the amendment its own step. My recommendation is to drop it.

### [CONCERN] CI gating of the load test is assumed, not verified

Task 15 (line 200) says CI gates `tests/load/test_fix_context_fetch.py` because the `uv run pytest` step has no deselect. That is true today: ci.yml:38 runs a bare `uv run pytest`, and pyproject.toml (lines 90–93) deselects only the `network` and `host_cf` markers. But no task checks it, and the Python rules require CI to gate load tests on network and concurrency paths. Add a success line that reads the workflow and confirms no step excludes `tests/load`. Also note that the workflow triggers only on pushes and PRs to `main` (ci.yml lines 3–8). If `git.integration_branch` is set, slice merges into it are not gated.

### [CONCERN] The only load test waits on 422, but the concurrency it guards lands in Task 9

Task 9 (line 125) runs git and file work in `asyncio.to_thread`. That is a concurrency path in file mode, and the Python rules require a load test for it. The only load test is in Task 15, which is blocked on 422 and needs the fetch path. Until 422 lands, the path ships untested under load. Fix this by having `FixContextAction` take the issue loader as a constructor dependency. A fake loader that blocks can then drive the load test in Task 9 with no 422 dependency. The fetch-specific case stays in Task 15.

### [CONCERN] The scrubbed-environment integration criterion has no verifying task

Design line 270 requires that 424 can run the pipeline in a 421 sandbox under `ScrubbedEnvironment` with no extra flags. Task 11 defers "the full scrubbed-environment sandbox run" to 424. The frontmatter (lines 6–7) lists only 422, and 421 is not implemented (line 8). So this criterion cannot be verified in this slice. Either add 421 as a dependency and a test under `ScrubbedEnvironment.variables()` (421 design, line 89), or write the deferral into the design's success criteria. The current `PATH` tripwire covers only the "no `gh` or `cf`" part.

### [CONCERN] Walkthrough step 3 proves a scratch target, not squadron's target

Functional requirement 1 (design line 247) requires one commit on "the target" of squadron. Development Approach step 6 (line 342) says steps 1–5 run on squadron. Task 16 step 3 instead runs in a `cf init`-registered scratch clone with `integration_branch` set to `fix-target-check`. That isolation is sensible, but the criterion as written is not demonstrated. Either state the substitution in the task and record it in the design, or run on squadron with a throwaway integration branch.

### [NOTE] Walkthrough step 6 is waived, so the live `/sq:run` path is untested

The waiver is reasonable. Task 13 covers CLI parity, and the `run.md` check covers the section structure. But no run exercises an agent following `run.md`. Mark this as a manual check for the Project Manager in the walkthrough.

### [NOTE] The `--io-dir` branch in the renderer cannot be reached from `sq run --prompt-only`

`run.py:1214` refuses `--io-dir` with `--prompt-only`, so `RUN_IO_DIR` never reaches the renderer from prompt-only runs. The branch "add `--io-dir` only when `RUN_IO_DIR` is in params" is dead from the CLI. Task 12 already tests the hidden command's flag directly. Either drop the renderer branch or document it as a contract for a future caller.

### [NOTE] Task 1's commit instruction does not fit the current state of the task file

The task file is tracked (`fd3afac8`) and has uncommitted edits, so "if this task file is uncommitted" is ambiguous. The suggested message `docs: add slice 423 tasks` is already used by `89520205`. Say to commit the current edits as `docs: revise slice 423 tasks`.

### [NOTE] Task 9's registration path is incomplete

Task 9 (line 133) says "Register in `executor.py`". The actual file is `src/squadron/pipeline/executor.py`, and the "Import modules to trigger registration" block is at line 529. Give the full path.

### [NOTE] Task 13 names a test file that does not exist, without saying to create it

`tests/cli/test_run_md_actions.py` does not exist. Say "new file" so the implementer does not look for it.

### [NOTE] Task 4 leaves an empty or non-string `blocked` undefined

The task covers a `blocked` key with a non-empty reason. It does not say what to do when `blocked` is present but empty, null or not a string. Specify that it is a defect naming `blocked`, so the implementer does not have to decide.

### [NOTE] Task 10's placeholder exemption is broader than it needs to be

Any value containing `{` skips validation. A malformed literal such as `"{301"` would pass `validate` and fail only at runtime. Exempt only a whole `{name}` token, so malformed literals are still rejected at validate time.

### [NOTE] Task count and some duplicated tests are heavier than the slice needs

Sixteen tasks and about 110 checkboxes for a 3/5 slice is at the upper end, but not overweight overall. Heaviest are Task 11 (about 11 scenarios in one commit) and Task 13 (five deliverables in one commit). Cut candidates: the separate no-change test bullet in Task 5 (line 95) repeats the Task 5 test list and Task 6 (line 102). Task 11's default-fetch failure case (line 153) is deleted in Task 15 anyway. Keep the `run.md` mutation check (line 172), since it is the only automated parity check on `/sq:run`.

### [PASS] The design corrections and the coverage map check out

- Task 7's correction is right. `dispatch.py:842` gates the fallback on `ActionType.CF_OP`, so design D2's claim that `DispatchAction` does not change is wrong.
- Task 2's rename is contained. `_DETACHED_HEAD` appears only in `git_ops.py` lines 25, 95 and 119.
- The `GitEnvironmentError` propagation claim holds. It is raised at `git_ops.py:74` and `:94`.
- The `--io-dir` correction holds. `run.py:1214` refuses the combination.
- 422 Tasks 5–6 match Task 15's precondition paths.
- `commit.py` is 286 lines, so Task 6's 300-line limit leaves 14 lines. That is tight but feasible.
- Functional criteria 1–7 and the technical requirements each map to a task. The only gap is the scrubbed-environment criterion above.
- Tests sit with their implementation, and commit markers fall at working, tested points. Task 10 has no marker and is committed with Task 11, which is acceptable.

### Run Digest

- Response length: 11756 chars
- Response is newline-free: no
- Tool calls made: 31
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 32
- Tokens — prompt / cached / cache write / completion / reasoning: 1428771 / 1249638 / 179111 / 62970 / not computed
- Duration: 277.3 s
- Cost: $0.27 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16

## Resolution

- F001 (Task 14 held behind 422): fixed. Task 15's BLOCKED note now says only Task 16 waits; Task 14 does not.
- F002 (Task 14 documents fetch mode): fixed. The Task 14 CHANGELOG bullet now describes `-p issue-file=PATH` and says nothing about fetching; Task 15 adds the fetched source to the docs and the bullet.
- F003 (amend-the-design step): fixed by removal. The step is gone from Task 14; the corrections stay in the Context Summary and the design is not edited.
- F004 (CI gating assumed): fixed. Task 9 now has a step that reads `ci.yml` and `pyproject.toml` to confirm nothing excludes `tests/load`, and notes the workflow runs only for `main`, so integration-branch merges are gated when that branch reaches `main`.
- F005 (load test waits on 422): fixed. `FixContextAction` takes an `IssueLoader` (Protocol, Task 3); Task 9 adds `tests/load/test_fix_context_blocking.py` with a blocking fake loader, no 422 needed. Task 15 adds only the real-loader case to that file.
- F006 (scrubbed-environment criterion): deferred to issue #296, named in Task 11. It needs slice 421, which is not a dependency and not implemented; the tripwire test stays as the part this slice can prove.
- F007 (walkthrough step 3 uses a scratch target): fixed in the task, not the design. Task 16 states that step 3 runs in a cf-registered scratch clone and so shows target mode, not a commit on squadron's own `main`, which a walkthrough must not make. Recording it in the design is rejected as out of scope (F003).
- F008 (step 6 waived): fixed. Task 16 now has the DEVLOG entry list `/sq:run fix <n>` as a manual check for the Project Manager; no task waits on it.
- F009 (`--io-dir` branch unreachable): fixed by removal. The renderer no longer passes `--io-dir`; `sq _fix-prompt --io-dir` stays as the design's contract and is tested directly (Task 12).
- F010 (Task 1 commit instruction): fixed. Task 1 now commits the task file by path as `docs: revise slice 423 tasks` when it is modified or untracked.
- F011 (registration path): fixed. Task 9 gives `src/squadron/pipeline/executor.py` and the block near line 529.
- F012 (test file does not exist): fixed. Task 13 marks `tests/cli/test_run_md_actions.py` as a new file.
- F013 (`blocked` empty or non-string): fixed. Task 4 makes a present but null, empty, whitespace-only or non-string `blocked` a defect naming `blocked`, with test cases.
- F014 (placeholder exemption too broad): fixed. Task 10 exempts only a value that is exactly one `{name}` token; `{301` is checked and rejected, with a test.
- F015 (task count, duplicated tests): partly accepted. Removed the no-change case from Task 6's tests (kept in Task 5 and Task 11) and Task 11's default-fetch case. Task count kept: each task is a commit unit and the `run.md` mutation check is kept, as the review recommends.
- F016 (pass): no change needed.
