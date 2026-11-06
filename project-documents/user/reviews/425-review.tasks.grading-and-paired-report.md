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
reviewedSha: cf9744e63f4ffdffaa4aad65104470de0a3934fc
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
effort: xhigh
turns: 23
promptTokens: 1561322
cachedTokens: 1329744
cacheWriteTokens: 231558
completionTokens: 94819
durationSeconds: 406.9
costUsd: 0.522986
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: nfr
    summary: "No load test or CI gate for the network and sandbox paths 425 adds"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:37-59"
  - id: F002
    severity: concern
    category: doc-accuracy
    summary: "Task 1 removes the architecture update on a premise the architecture doesn't support"
    location: "project-documents/user/architecture/420-slices.model-benchmark.md:113-125"
  - id: F003
    severity: concern
    category: coverage
    summary: "Task 1's correction list misses sections the gap list changes"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:66-67"
  - id: F004
    severity: concern
    category: doc-accuracy
    summary: "Task 32 imports z constants that 422 does not define"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:303"
  - id: F005
    severity: concern
    category: coverage
    summary: "`lockfile_sha256` has no value when no reinstall happens"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:411"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "Malformed producer TOML and a hanging reinstall have no defined outcome"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:159-166"
  - id: F007
    severity: concern
    category: coverage
    summary: "Reference grades have no defined lookup path for replays, retry or the report"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:417-431"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 27 bundles four steps and nine test assertions"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:238-240"
  - id: F009
    severity: note
    category: test-quality
    summary: "Exact-equality assertion on a bootstrap interval is brittle"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:265"
  - id: F010
    severity: note
    category: coverage
    summary: "Three inputs are left for the implementer to guess"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:98"
  - id: F011
    severity: note
    category: scope
    summary: "The home for the grade models is left conditional"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:110"
  - id: F012
    severity: note
    category: doc-accuracy
    summary: "Fixture commit need not be a fix commit"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:143"
  - id: F013
    severity: note
    category: sequencing
    summary: "Task 29 changes the order Task 24 sets up"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:221-254"
  - id: F014
    severity: note
    category: proportionality
    summary: "Tasks 44 and 45 run the same gates"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:348"
  - id: F015
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks, and all eleven absences are tested"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:476-502"
  - id: F016
    severity: pass
    category: sequencing
    summary: "Sequencing, upstream gate and commit markers are sound"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:97-101"
---

# Review: tasks — slice 425

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] No load test or CI gate for the network and sandbox paths 425 adds

`python.md:57` requires at least one `tests/load/` test, with CI gating, for code on the network or environment-layer paths. 425 adds a provider call (`review_tree_diff`, Task 21 at L204–207) and runs sandbox, `uv sync` and snapshot code (Tasks 24–26). The breakdown has no load task, no CI task, and no recorded exemption. The design restates no performance NFR, so the NFR trigger doesn't fire, but the python rule applies by its own terms. The 420 and 421 reviews both asked for this to be decided explicitly. Fix: add a load task for the review and sandbox paths with a CI gate, or record in the Context Summary why none is needed. If 421's existing `tests/load/` sandbox coverage applies, cite it; the review-call path still needs its own.

### [CONCERN] Task 1 removes the architecture update on a premise the architecture doesn't support

Task 1 (L66) says "the architecture's cost section and 424 already say grading has its own cap" and removes the design sentence (design L236) that the architecture should say so. The architecture has no cost section, and its 425 entry (L113–125) says nothing about a grading cap. Only 424 says it (424 slice L258: "Grading is bounded by `sq benchmark grade`'s own cap (425 D9)"). After Task 1, the architecture records no grading cap at all. Fix: correct the premise in Task 1, then either add one line to the architecture's 425 entry or state in the design that the architecture is silent and 424 is the only record.

### [CONCERN] Task 1's correction list misses sections the gap list changes

Task 1's success check (L67) covers D7, D8, D10, D12–D15, Database Schema and API Contracts. The gap bullets (L41–53) also change D1 and D2 (empty selections), D9 (one reference per environment digest), the report extension point under Integration Points (design L464), and D11 (the new `reviews` sidecar kind; design L249 and State Management L146 list only `diffs`, `snapshots`, `nodes`). The design's walkthrough step 4 (design L528) names `tests/benchmark/test_grade_one.py`, but Tasks 28 (L246) and 44 (L354) use `test_grade_one_edits.py`. Fix: extend Task 1's check to D1, D2, D9, D11, Integration Points and the walkthrough, and align the test path before any code is written.

### [CONCERN] Task 32 imports z constants that 422 does not define

422 Task 26 defines `SIGNIFICANCE = 0.05` and `POWER = 0.80` in `separability.py` and computes z with `statistics.NormalDist`. It defines no z constants. Task 32 (L271) says "422's z constants (imported, not redefined)", and Task 5 (L98) asks to confirm "the z constants the separability bound uses". Neither names a symbol that exists, so the implementer must redefine z (which Task 32 forbids) or guess. Fix: name the symbols 422 exports, or require 422 to export a z helper, and make Task 5's check use the same names.

### [CONCERN] `lockfile_sha256` has no value when no reinstall happens

`GradeResult.lockfile_sha256: str` is required (design L411). Task 25 records the lockfile hash only in the reinstall branch (L227). For every grade without a dependency change the field is undefined, so an implementer will leave it empty or write a placeholder. AGENTS.md ("Never use silent fallback values") rules out both. Fix: state that the producer's lock hash is always recorded (with a defined value when there is no lock), or make the field optional with `None` meaning no lock, and say which in Tasks 8 and 25.

### [CONCERN] Malformed producer TOML and a hanging reinstall have no defined outcome

Task 14 parses the producer's `pyproject.toml` with `tomllib`, and Task 25 runs `uv sync --locked` (L227). No task says what happens when the TOML doesn't parse (`TOMLDecodeError`) or when the reinstall hangs. D16 (design L293–312) names no absence for either, and no timeout is named for the reinstall (only `suite_timeout_s` and `review_timeout_s`). The review rule (`.claude/rules/review-code.md`, Failure-Mode Enumeration) asks "What if this hangs? What if it times out?" and requires an observable signal with a test. Fix: map a parse failure and a reinstall timeout to named absences, name the timeout key, and add a test for each asserting the ERROR log and the recorded absence.

### [CONCERN] Reference grades have no defined lookup path for replays, retry or the report

`ReferenceGrade` has `case_id`, grader and environment digest, but no `benchmark_id`, and its id has no benchmark part (Task 10, L127). Three things need to find these records, and no task says how:
- Design D8 (L216) says replay grades read the baseline from the reference grade. Task 26 (L234) only says "baseline nodes sidecar".
- Task 10 defines `grades_for(benchmark_id)` as returning implementation grades only, yet Task 35 (L290) says `--retry-harness` deletes "those grade records", which may include a harness-absent reference.
- The report's reference line and case drops (Tasks 36–39) need the same lookup.

The lookup is possible from existing fields (`get_reference_grade` with each replay's environment digest). Task 34 (L285) also uses "a failed reference" without defining it. Fix: state the lookup path in Task 10 or 34, say whether `--retry-harness` covers reference records, and define "failed reference" as a reference record with an absence or a non-pass.

### [CONCERN] Task 27 bundles four steps and nine test assertions

Task 27 covers test restoration, the regression run with truncation, the hidden run with its id-map sidecar, suppression counting, the `GradeResult` assembly with every cap, and the `ImplementationGrade` write, all in one commit with Task 26. It is the largest step in the breakdown and the most likely to be left half done. Task 14 (L159–166) and Task 36 (L296–299) have the same shape, though smaller. Fix: split Task 27 into a regression part (restoration, regression run, guards) and a hidden-and-record part (hidden run, id map, suppressions, assembly, write), each with its own test group. Consider splitting Task 14 along the restore/dependency line.

### [NOTE] Exact-equality assertion on a bootstrap interval is brittle

The test expects "mean 0.2 and an interval of exactly (0.2, 0.2)" for six cases with difference 0.2. A plain sum of six 0.2 values is not exactly 1.2, so an exact comparison can fail for reasons unrelated to the code. Use `pytest.approx`.

### [NOTE] Three inputs are left for the implementer to guess

(a) Task 42 edits `commands/sq/benchmark.md` (L333), which doesn't exist yet, and Task 5 doesn't check for it. (b) Task 26 (L234) calls `resolve_files(repo_root, exclusions)` (`src/squadron/metrology/snapshot/files.py:40`) without naming the exclusions. (c) Task 43 (L340) asks for one yield line, but a `SampleSizeEstimate` holds several pairs and k values, and the task doesn't say which the line shows. Fix: name each in the task.

### [NOTE] The home for the grade models is left conditional

Task 7 puts the enums and models in `metrology/benchmark_models.py` (L110). The context (L53) says that file, shared with 421 and 424, will be near the ~300-line limit. Task 9 names no module, and Task 10 says "`benchmark_store.py` (or `grade_store.py`)" (L127). Splitting into `grade_models.py` and `grade_store.py` is left conditional on line count. Decide now and name the file in each task.

### [NOTE] Fixture commit need not be a fix commit

The design requires fixture trees "built from a real squadron fix commit's test file" (design L495). Task 12 says only "pick a commit whose changed test file has a class with a parametrized method". Add a `fix:` commit to the selection criteria.

### [NOTE] Task 29 changes the order Task 24 sets up

Task 24 writes the reference path as apply-then-commit (L222). Task 29 then requires the start-tree baseline before the diff applies (L252). That works, but Task 24 should leave a marked slot before the apply so Task 29 doesn't reorder finished code.

### [NOTE] Tasks 44 and 45 run the same gates

Task 44's first bullet (L348) runs `ruff format --check`, `ruff check`, `pyright` and the full test suite. Task 45's first bullet (L365) runs the same set. Keep Task 45 and reduce Task 44's bullet to a pointer.

### [PASS] Success criteria map to tasks, and all eleven absences are tested

Functional: reference grading (29–30, 44); edit counting (13–16, 28); reinstall (14, 25); regression selection (27); injection and clashes (17–18); config vs harness absences (31, 36, 39); bootstrap (31, 38); no composite (36); estimate (32, 35, 39, 43); refusals, bound, cap and resume (33–35, 41). Technical: lint and type (45); paired tests (31–32); fixture trees (12–13, 17–18); absences (24–26, 29); retained tests (3, 6, 45). Integration: 26/27 and 37. All eleven `GradeAbsence` values have a test with their class (Task 24: 4, Task 25: 2, Task 26: 4, Task 29: 1). Walkthrough steps 1–7 are covered by Task 44. Two small gaps: the `[project].dependencies` reinstall trigger is unit-tested only (Task 14), with no end-to-end case in Task 25, and the fixture criterion is only as strict as Task 12's selection.

### [PASS] Sequencing, upstream gate and commit markers are sound

Dependencies run forward with no cycle. Tasks 2–4 touch only this slice's design, 320, 400 and config code, so they can run before the gate. Task 5 stops with `BLOCKED:` on the unimplemented names; `src/squadron/benchmark` does not exist yet, so that is the right gate. Test steps sit with the code they test. The `**Commit**:` markers close tested groups (Tasks 20–22, 23–25, 26–27) and don't sit after bare checkbox passes. The 300/320/400 names in Task 5 exist in `src/`, and the 421/422/424 task files name the other symbols I searched for, except the z constants (see the 422 finding above).

### Run Digest

- Response length: 14181 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 23
- Tokens — prompt / cached / cache write / completion / reasoning: 1561322 / 1329744 / 231558 / 94819 / not computed
- Duration: 406.9 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16

## Resolution

- F001 (load test or CI gate): resolved by recording the decision in the Context Summary: none added, because grading is sequential and reuses 421's sandbox and install code (covered by 421 Task 26's concurrency load test); the review, reinstall and suite calls each have a timeout and a test of the observable signal (Tasks 21, 25, 26).
- F002 (architecture premise): corrected Task 1. The architecture file `420-arch.model-benchmark.md` does have the cost wording (its Spend bullet and Cost section); the review read the slice plan `420-slices.model-benchmark.md`, whose 425 entry is silent. Task 1 now adds one sentence on the grading cap to that slice-plan entry.
- F003 (Task 1 correction list): extended Task 1's edit and success check to Component Structure, D1, D2, D7–D16, State Management, Database Schema, API Contracts, Integration Points and the walkthrough, and aligned step 4 to `test_grade_one_edits.py`.
- F004 (z constants): Task 33 now computes both z values with `NormalDist().inv_cdf` from `SIGNIFICANCE` and `POWER`, imported from 422's `benchmark/separability.py`; Task 5 checks those names.
- F005 (`lockfile_sha256`): made `str | None`, always recorded (the producer's `uv.lock` hash, `None` with no lock); stated in Tasks 8 and 25, with a test, and in the gap list.
- F006 (malformed TOML, hanging reinstall): a producer `pyproject.toml` that does not parse raises `ProducerConfigError` (Task 14), recorded as `producer_env_unresolvable`. The reinstall uses 421's `resolve_environment` bounded by `benchmark.install_timeout_s`, and its failure reasons map to existing absences (Task 25). No new `GradeAbsence` value, so the eleven-absence coverage still holds; both mappings have tests with the ERROR log.
- F007 (reference lookup): Task 10 states the contract (`get_reference_grade` with the replay's environment digest; references belong to the case) and lets `delete_grades` take reference ids. Task 26 reads the baseline through it and raises `MissingReferenceGrade` without one. Task 35 defines a failed reference. Task 36 makes `--retry-harness` cover references. Task 39 uses the lookup for the report's reference line.
- F008 (Task 27 bundle): split into Task 27 (restoration and regression) and Task 28 (hidden run, suppressions, record), each with its own tests and marker. Later tasks are renumbered (46 tasks). Task 14 was not split: restoration and `deps_changed` share the restored-tables logic, and an earlier review merged them on purpose.
- F009 (exact interval equality): the test now compares mean and interval with `pytest.approx`.
- F010 (three guessed inputs): Task 5 now checks `commands/sq/benchmark.md`; Task 26 names the exclusions (`effective_exclusions` over `read_snapshot_config(tree)`); Task 44 defines the yield line as the pair needing the most cases at the estimate's k, with a test.
- F011 (home for grade models): decided, not conditional: models and records in `metrology/grade_models.py`, record methods in `metrology/grade_store.py` (`GradeRecordStore`); only the sidecar kinds extend `benchmark_store.py`. Tasks 7–10 and the Task 46 size check name them.
- F012 (fixture commit): Task 12's selection now requires a commit whose subject starts with `fix:`.
- F013 (Task 24/29 order): Task 24 leaves a named step before the apply (empty for replays); Task 30 adds the reference baseline there.
- F014 (duplicate gates): Task 45 now points to Task 46's gates, which also take the "already failing on the target" allowance.
- F015 (pass, success criteria map to tasks): no change needed.
- F016 (pass, sequencing and markers): no change needed.
