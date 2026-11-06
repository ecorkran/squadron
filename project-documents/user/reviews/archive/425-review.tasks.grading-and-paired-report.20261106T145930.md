---
docType: review
layer: project
reviewType: tasks
slice: grading-and-paired-report
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/425-tasks.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 7754fedc16290c1dade207c0685a5ed433b27344
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: xhigh
turns: 11
promptTokens: 880484
cachedTokens: 702033
cacheWriteTokens: 178437
completionTokens: 64716
durationSeconds: 283.8
costUsd: 0.36303
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "Functional criteria trace to tasks"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:50-348"
  - id: F002
    severity: pass
    category: design-gap
    summary: "Context Summary design gaps match the code"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:38-41"
  - id: F003
    severity: pass
    category: process
    summary: "Test-with pattern and commit cadence"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:56-348"
  - id: F004
    severity: note
    category: nfr
    summary: "No NFR restated, so no load-test or CI task is required"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:491-497"
  - id: F005
    severity: concern
    category: test-infrastructure
    summary: "Fixture trees will be collected by pytest and linted with the suite"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:121-127"
  - id: F006
    severity: concern
    category: commit-hygiene
    summary: "Commit markers sit on the wrong work"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:127"
  - id: F007
    severity: concern
    category: sequencing
    summary: "The Task 4 gate blocks work that does not depend on 421–424"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:72-75"
  - id: F008
    severity: concern
    category: design-consistency
    summary: "The report row key contradicts the design's own identity rule"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:263"
  - id: F009
    severity: concern
    category: interface-gap
    summary: "Nothing carries cap accounting or review cost out of `grade_one`"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:194-197"
  - id: F010
    severity: concern
    category: test-gap
    summary: "An empty hidden set is untested and could select every test"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:211-216"
  - id: F011
    severity: concern
    category: test-gap
    summary: "\"Both sides run\" is asserted only as existence"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:158-161"
  - id: F012
    severity: concern
    category: test-gap
    summary: "The 16 KB record bound has an uncapped path"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:96-101"
  - id: F013
    severity: concern
    category: test-gap
    summary: "Four stated rules have no test"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:131"
  - id: F014
    severity: concern
    category: commit-hygiene
    summary: "Task 47 edits the architecture and another slice's design inside the `feat:` commit"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:344"
  - id: F015
    severity: note
    category: proportionality
    summary: "Overlapping and optional tests"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:227-231"
  - id: F016
    severity: note
    category: sizing
    summary: "Sizing: one task is heavy, three are single functions"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:121-127"
  - id: F017
    severity: note
    category: clarity
    summary: "Wording and reference issues"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:85"
---

# Review: tasks — slice 425

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Functional criteria trace to tasks

All ten functional requirements (design lines 480–489) and the technical and integration requirements have a named task and test. FR1 maps to Tasks 29 and 35. FR2 maps to Tasks 13, 15, 16 and 28. FR3 maps to Tasks 14 and 25. FR4 and FR5 map to Tasks 17, 18 and 27. FR6 and FR7 map to Tasks 32 and 38. FR8 maps to Task 38's reflection test. FR9 maps to Tasks 36, 40 and 44. FR10 maps to Tasks 34, 35, 36 and 42. All eleven D16 absences are produced by a task (Tasks 24–26, 29, 30). I found no task that traces to nothing.

### [PASS] Context Summary design gaps match the code

Verified in the tree: `is_within_floor(delta: int, ...)` (`src/squadron/metrology/audit_delta.py:41`); private `_stat` (`src/squadron/metrology/audit_variance.py:58`), which no test imports, so the rename is safe; `take_snapshot_at` (`src/squadron/metrology/snapshot/take.py:160`); `resolve_files(repo_root, exclusions)` (`src/squadron/metrology/snapshot/files.py:40`); and `tests/metrology/snapshot/test_take_at.py`, where Task 3's tests belong. `review/run_cost.py` and `tomli-w` (`pyproject.toml:34`) also exist.

### [PASS] Test-with pattern and commit cadence

Every implementation task has a test item directly after it. Task 45 has no test, which is right for a markdown file. There are 18 commit markers, all at points that should pass tests. Task 11 and Task 23 are the exceptions (see the commit-marker finding).

### [NOTE] No NFR restated, so no load-test or CI task is required

The design has no non-functional section. Its only size bound (records under 16 KB, design line 458) is a unit-level invariant that Task 8 covers. Nothing here requires a `tests/load/` task or CI gating.

### [CONCERN] Fixture trees will be collected by pytest and linted with the suite

`pyproject.toml:89` sets `testpaths = ["tests"]`, with no `norecursedirs` or `python_files` override. Task 12 puts `start/` and `reference/` copies of the same test file, plus `producer_*/` variants, under `tests/benchmark/fixtures/grading/`. Those copies match `test_*.py`, so the touched-area run (`pytest tests/benchmark`) and the Task 46/47 full-suite gates will collect them. Two same-named test modules in sibling directories without `__init__.py` typically fail collection with an import-file mismatch. The variants also contain deliberately non-conforming code (edited assertions, `# noqa`, `# type: ignore`), which `ruff check` would flag unless excluded. Task 12 should state how the fixtures are kept out of collection and lint: for example, store them with a non-`.py` suffix that the builder copies into a tmp dir, or add explicit pytest and ruff excludes. Task 17's pytest runs should use the tmp copies.

### [CONCERN] Commit markers sit on the wrong work

The commit at line 127 is `test: add real-commit fixture trees for grading`, but it also contains Task 11's production code (`GradingAdapter` protocol, registry, `GitTreeReader`), which has no marker of its own. Task 23 (`review_flag`) has no marker either, so it lands in the `feat: add the grade sandbox…` commit at line 204. Add a `feat:` marker after Task 11, and move Task 23 before the commit at line 187 or give it its own marker. As written, `git log` misdescribes what several commits contain.

### [CONCERN] The Task 4 gate blocks work that does not depend on 421–424

Task 4 stops with `BLOCKED:` and the task text says Tasks 5 onward wait. The process rule is to finish whatever does not depend on the blocked part. Task 32's core (`case_pass_fraction`, `paired_differences`, `bootstrap_mean_interval`, `compare_pair`) has no upstream dependency; the design says `paired_stats` is pure, with no I/O, store or model. Move Task 32's core ahead of the gate, or state that the gate covers only the sandbox-dependent tasks. Task 33 needs 422's z constants, so it stays behind the gate.

### [CONCERN] The report row key contradicts the design's own identity rule

The design's Dependencies section (line 58) says rows group by 420's identity: model, profile, effort sent, `tool_use` and `max_output_tokens`. The 420 architecture (`project-documents/user/architecture/420-arch.model-benchmark.md:40`) and the 420 review (F004) agree. D13 (line 263) keys rows on `(alias, model, profile, effort_sent)`, and Task 38 (line 276) copies that. Two configs that differ only in `tool_use` or `max_output_tokens` would then share a row, which violates "rows are never silently merged." Settle the five-field key before Task 38 and write it into Task 38. The 420 review also notes that pre-slice records have `tool_use = None`, so old and new records would split across rows. Decide how to handle that.

### [CONCERN] Nothing carries cap accounting or review cost out of `grade_one`

Task 35 says the runner checks the cap before each review and counts unpriced reviews at the per-review figure. But reviews run inside `grade_one`: in Task 25 for replays, and in Task 29 for each of the reference's floor runs. `GradeDeps` (Task 24, line 195) lists the sandbox factory, registry, reviewer, measurer, store, runner and clock. It gives the runner no pre-review check and no way to receive each review's `cost_usd`. The floor runs are the case that matters: D8 says a cap hit between floor runs writes no reference record, and no test covers that (Task 29, line 224). Add a budget port to `GradeDeps` (a check-before-review callable and a cost sink), and add a Task 29 test for a cap stop between floor runs.

### [CONCERN] An empty hidden set is untested and could select every test

Integration requirement (design line 501): 426 must be able to grade a slice case with an empty hidden set through `grade_one`. No task tests that. Task 27 runs `nodes(injected ids)`. If an empty selection is passed through to pytest as no node arguments, pytest runs the whole rootdir. Add a Task 27 test that an empty hidden set issues no hidden run and that the pass reduces to "no regressions" (the zero-hidden row Task 8 already tests). Also state in the `run_suite` contract that an empty selection runs nothing.

### [CONCERN] "Both sides run" is asserted only as existence

FR5 (design line 484) requires that a clashing producer test or fixture and its hidden counterpart both run. Task 18's tests check that both tests exist and that the clash is recorded. Nothing runs the clash variant under pytest, so the shadowing behavior D3 depends on is never exercised. Add one pytest-run assertion on variant (d) that collects both sides and checks each outcome.

### [CONCERN] The 16 KB record bound has an uncapped path

Design line 458 says a grade record stays under 16 KB because node lists are sidecars and failures are capped at 50. But `GradeResult.hidden` and `hidden_id_map` (design lines 399–400) are per-hidden-test tuples that are neither sidecars nor capped. Task 8's size test covers only 50 failing ids, so a case with a large hidden set can exceed the bound without the test catching it. Either move `hidden` to a sidecar or cap it, or narrow the stated bound to failures and test a large hidden set. Also, line 97 says the 50-id cap is "capped … by a validator that raises on more." A validator cannot cap. State that the caller truncates to 50 and the validator guards that.

### [CONCERN] Four stated rules have no test

- Task 13 (line 130) says a `[tool.*]` table absent at start is removed. The tests on line 131 cover restoration, unchanged tables and `ruff.toml` deletion, but not a producer-added table.
- Task 26 (line 207): replay grades read the baseline from the reference grade (D8). The task says "baseline nodes sidecar" without saying where a replay gets the reference's sidecar reference, and no test checks it.
- Task 29 (line 223): a cap hit between floor runs writes no reference record. No test covers it (line 224).
- Task 32 (line 239): `case_pass_fraction` counts config absences as fails. The test list (line 240) has no absence case.

Each is a one-line test. Add them to the tasks named above.

### [CONCERN] Task 47 edits the architecture and another slice's design inside the `feat:` commit

Task 47 changes 424's design sentence and the architecture's cost section (line 344), then commits everything as `feat: complete grading and paired report slice` (line 348). The architecture change alters a project-level cost decision (design D9, line 236). Under the repo rules, planning documents are committed on their own, and policy changes go to the Project Manager before they are written. Move the architecture and 424 edits out of the feat commit, and get the Project Manager's decision on the cost wording first. The slice design and DEVLOG updates can stay in the feat commit.

### [NOTE] Overlapping and optional tests

- Task 30 re-tests the eleven absences that Tasks 24–26 and 29 already produce. Its parametrized check is the useful part, since it catches a new enum value with no case. The per-task absence tests can then check behavior only.
- Task 37 (a real SIGKILL on a subprocess, lines 269–273) is platform-specific and timing-sensitive. The double-based test in Task 36 already proves the invariant (no record, and a rerun grades the subject). Consider dropping Task 37.
- Tasks 46 and 47 both run the full gates. Task 47 says "once", so keep one full run.

### [NOTE] Sizing: one task is heavy, three are single functions

Task 12 covers commit discovery, a tree builder and five variants, each with its own test list. Split it at the variants (a–c and d–e) so each has a reviewable commit. Tasks 27 (regression, hidden, suppressions, record) and 38 (inclusion rules) are the next largest. In the other direction, Task 9 (record ids), Task 23 (`review_flag`) and Task 45 (a markdown file) are each one function. Merge them into Tasks 10, 22 and 42–43.

### [NOTE] Wording and reference issues

- Task 6 (line 85) says the floor-runs key has a minimum of 2 and that "a value below 2 raises the way `get_positive_int_config` raises." That helper (`src/squadron/config/manager.py:145`) enforces positivity, not a minimum of 2, so the task has to add a separate bound check. Say so.
- Task 17 (line 155) says the subprocess uses "the tmp repo's start venv-free interpreter" without naming the interpreter. Name it, for example `sys.executable -m pytest`.
- Task 4 (lines 74–75) omits names that Tasks 2, 3 and 10 use: `write_record`, `iter_records`, `derive_project_id`, `take_snapshot_at`, `resolve_files` and `FloorStat`. All exist today, so this is list completeness only.
- The design's walkthrough step 4 (design line 528) names `tests/benchmark/test_grade_one.py`. Task 28 and Task 46 use `test_grade_one_edits.py`. Task 47's list of design updates (line 344) doesn't record the rename.

### Run Digest

- Response length: 13140 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 880484 / 702033 / 178437 / 64716 / not computed
- Duration: 283.8 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
