---
docType: review
layer: project
reviewType: tasks
slice: slice-cases
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/426-tasks.slice-cases.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 948f2ee9b42f733505f0fd8533fa41f2f68a2cb7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: xhigh
turns: 10
promptTokens: 572898
cachedTokens: 413654
cacheWriteTokens: 159234
completionTokens: 72064
durationSeconds: 306.5
costUsd: 0.347953
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "Harness-error stop conflicts with the every-index success criterion"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:181"
  - id: F002
    severity: concern
    category: design-consistency
    summary: "`CfRegistration` `branch` value is undefined for slice runs"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:206"
  - id: F003
    severity: concern
    category: design-consistency
    summary: "`--keep` option has no defined behavior"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:186"
  - id: F004
    severity: concern
    category: testability
    summary: "Over-size records are never cleared once the case becomes judgeable"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:257-260"
  - id: F005
    severity: concern
    category: coverage
    summary: "Production wiring for `build` and `judge` is not assigned"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:262-267"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 12's real fixture needs a `slice_ranges` record that is created later"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:140"
  - id: F007
    severity: concern
    category: coverage
    summary: "No test fixture comes from real landings, as the design requires"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:130-134"
  - id: F008
    severity: concern
    category: completability
    summary: "Leak-scan check in the cf spike has no executable method"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:114"
  - id: F009
    severity: concern
    category: size
    summary: "Three tasks are too large for one pass"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:168-178"
  - id: F010
    severity: concern
    category: size
    summary: "File is overweight for a 3/5 slice: 40 tasks and about 25 test modules"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md"
  - id: F011
    severity: concern
    category: design-consistency
    summary: "Task 1's design correction misses two mismatches"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:57-60"
  - id: F012
    severity: note
    category: coverage
    summary: "Task 6 gate omits names that later tasks use"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:99"
  - id: F013
    severity: note
    category: conventions
    summary: "Pointer to `judge_prompt` is wrong"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:236"
  - id: F014
    severity: note
    category: testability
    summary: "Lock-held test does not assert the failure-mode signal"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:259"
  - id: F015
    severity: note
    category: process
    summary: "`fix:` commit type on defects in the slice's own code"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:203"
  - id: F016
    severity: pass
    category: coverage
    summary: "Functional, integration and walkthrough criteria all map to tasks"
    location: "project-documents/user/slices/426-slice.slice-cases.md:430-457"
  - id: F017
    severity: pass
    category: process
    summary: "Test-with, checkboxes and commit markers"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md"
  - id: F018
    severity: pass
    category: sequencing
    summary: "Sequencing and pre-gate references hold"
    location: "src/squadron/replay/start_point.py:23"
---

# Review: tasks — slice 426

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Harness-error stop conflicts with the every-index success criterion

Task 19 says a harness error on one candidate "stops the build and returns it", and Task 20 exits 1 on it. Design Functional Requirement 1 (`project-documents/user/slices/426-slice.slice-cases.md:434`) says the build writes a `SliceQualification` for every slice index in the record. D6 (line 209) says harness failures are logged and recorded. With a stop, later indices get no record. Decide the rule in Task 1's design correction. Recording and continuing, then exiting 1 at the end, meets the criterion as written.

### [CONCERN] `CfRegistration` `branch` value is undefined for slice runs

Task 23 calls `register(tree, name=<sandbox id>, branch, slice index)`, and Task 4 writes `branch` into `cf config set git.integration_branch`. Neither the task nor D9 (design line 231) says what a fork sandbox passes. Name the value, or the rule that produces it, in Task 23 and D9.

### [CONCERN] `--keep` option has no defined behavior

Task 20 (and design line 336) lists `slice-cases build --set NAME [--repo PATH] [--keep]`. Neither the design nor any task says what `--keep` does, and Task 20's test only checks that `--help` lists it. Define it or remove it.

### [CONCERN] Over-size records are never cleared once the case becomes judgeable

Task 32 says an over-size record is "removed from the pairs when it no longer applies". Task 10 gives the store no delete method, and D14 (design line 285) says only that the record is replaced when the limit changes. After the limit is raised and the case is judged, the report would count it as both judged and over size. Add a delete or clear step, and a test that the count drops after judging.

### [CONCERN] Production wiring for `build` and `judge` is not assigned

Tasks 20 and 33 test only with doubles. No task says which real collaborators the CLI passes in: the judge dispatcher (`one_shot_judge_dispatcher(alias)`, `src/squadron/replay/judge_dispatch.py:34`, used the same way at `src/squadron/cli/commands/replay_judge.py:71`), `ProcessRunner`, the sandbox factory, the adapter registry, the store and the clock. The first live run is Task 39 step 5, so the gap would surface there. Name the composition step in Tasks 20 and 33.

### [CONCERN] Task 12's real fixture needs a `slice_ranges` record that is created later

Task 12 picks a slice "from a landing in `get_slice_ranges`", but the first `sq metrology slice-ranges` run is in Task 22 (lines 197–199), after Task 12. Unless the record already exists, Task 12 cannot run. Add the `slice-ranges` run to Task 12, or take the shas from git and say so.

### [CONCERN] No test fixture comes from real landings, as the design requires

Design Technical Requirement (line 450) says qualification fixtures come from squadron's real `slice_ranges` landings, including at least one merge and one fast-forward landing. Task 11 builds synthetic repositories only, and Tasks 13–14 test on them. The live build (Task 22) uses real landings, but its success criteria (lines 199–200) do not require the merge and fast-forward landings to each produce a case or a named rejection. Record a real-landing fixture, or add that check to Task 22 and name the requirement it meets.

### [CONCERN] Leak-scan check in the cf spike has no executable method

"Compare `strace`-free evidence: `cf` stderr, or run again with a read-only copy of the real home absent" does not say what to run or what passes. Name the commands and the pass condition. For example: run the three cf steps with `HOME` set to the scrubbed home and the real home made unreadable, then record any failure and the path it names.

### [CONCERN] Three tasks are too large for one pass

Task 17 puts all of `qualify_slice_candidate` in one task: checks, both sandboxes, collect, test sets, superseded, and the record. Task 18 adds the repeat loop, exclusions, regression selection, harness-error mapping and case write to the same function. CLAUDE.md caps functions near 50 lines, so the task should name the helpers to split it into. Task 30 (lines 245–248) puts a whole per-case loop in one task, and Task 32 (lines 257–260) combines the bound, cap, lock, over-size writes and resume. Split Tasks 30 and 32 along those seams.

### [CONCERN] File is overweight for a 3/5 slice: 40 tasks and about 25 test modules

Cut or merge:
- (a) Task 15 into Task 13. Both are in `slice_discovery.py` and already share a commit.
- (b) Task 16 into Task 17.
- (c) Task 38 into Task 33.
- (d) Tasks 27 and 29 into Task 26. All are pure functions in `diff_judge.py`.
- (e) One test module per source module: merge the three `test_slice_qualify_*` files and the five `test_diff_judge_*` files.

That gives about 35 tasks and about 19 test modules, with the same success criteria covered.

### [CONCERN] Task 1's design correction misses two mismatches

Task 1 corrects D3, D9, D12 and the API Contracts block, but not these:
- (a) Development Approach step 1 (design line 512) and the mitigation (line 505) say the cf spike runs first. The task file puts it at Task 8, after Tasks 2–7. That order is justified, since the spike needs Task 4's `CfRegistration` and Task 7's `with_tools`, but the design should say so.
- (b) Data Flow line 134 calls `CfRegistration(env)`, while D9 and the API block use `(runner, env)`.

The Task 1 commit message `docs: add slice 426 tasks` should be `docs: update slice 426 tasks`, because the file is already in history (948f2ee9).

### [NOTE] Task 6 gate omits names that later tasks use

The gate confirms 421–425 names but not `ProcessRunner` (Task 13; exists at `src/squadron/core/process_runner.py`), `one_shot_judge_dispatcher` (Tasks 30 and 33), the `sq benchmark` group that Task 20 registers under, or `sq benchmark yield` (Tasks 21–22). Add them.

### [NOTE] Pointer to `judge_prompt` is wrong

Task 28 says to read `judge_prompt()` in `replay/judging.py`. It is defined in `src/squadron/replay/judge.py:25` and imported into `judging.py` at line 31. Point the task at `replay/judge.py`.

### [NOTE] Lock-held test does not assert the failure-mode signal

The Context Summary (line 46) requires each failure mode to assert an ERROR log plus a recorded outcome. Task 32's test only asserts that a held lock refuses. Add an ERROR-log assertion, as its store-failure test already does.

### [NOTE] `fix:` commit type on defects in the slice's own code

Tasks 22, 25 and 39 commit slice defects as `fix:` (lines 203, 223, 311). The bug-fixes rule says a bug in the slice's own code is part of the slice, and `fix:` routes work through the fix path. Use the slice's commit type, or confirm the type with the PM.

### [PASS] Functional, integration and walkthrough criteria all map to tasks

Each Functional, Technical and Integration criterion, and walkthrough steps 1–8, maps to at least one task. The gaps are the ones listed above. The design restates no performance NFR, so no `tests/load/` task is required. No task falls outside the design's scope; the only excess is the test-module count.

### [PASS] Test-with, checkboxes and commit markers

Every implementation task carries its own tests, and Task 37 is an integration test after Tasks 34–36. All items and subitems use `[ ]`. There are 21 plain `**Commit**:` lines, each at a tested point and none as a checkbox. Tasks 2–5 each commit separately, which is acceptable because each is a tested change.

### [PASS] Sequencing and pre-gate references hold

The symbols that Tasks 2–4 rename or extract exist as described: `_ArtifactKind`, `_KINDS` and `_suffix_order` (`start_point.py`), `_register_with_cf` and `_initiative` (`replay/sandbox.py:168,181`), `_call` and `_judge_pair` (`replay/judging.py:169,183`), and `plan_file_for` (`stats/planning_docs.py:255`). `get_positive_int_config` (`config/manager.py:145`) and `metrology.judge_timeout_s` (`config/keys.py:350`) also exist. Tasks 2–5 can run as written, and the dependency order has no cycles.

### Run Digest

- Response length: 10794 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 572898 / 413654 / 159234 / 72064 / not computed
- Duration: 306.5 s
- Cost: $0.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
