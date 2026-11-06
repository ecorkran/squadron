---
docType: review
layer: project
reviewType: tasks
slice: fix-case-qualification-and-yield-report-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 400f5d6958c38eec251c5d61b2c93b0b5c8d414e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
effort: xhigh
turns: 12
promptTokens: 569904
cachedTokens: 411110
cacheWriteTokens: 158784
completionTokens: 72858
durationSeconds: 310.9
costUsd: 0.349376
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 12 pins a pyright check the Python adapter cannot pass until Task 17"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:152"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 19 collects at the wrong state and leaves timeouts and reference-side collection failures unmapped"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:216"
  - id: F003
    severity: concern
    category: consistency
    summary: "`gh` missing is specified two ways"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:211"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Fixture scenarios are used before any task creates them"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:134"
  - id: F005
    severity: concern
    category: completeness
    summary: "The \"records equal closing commits\" criterion is tested only on discovery output"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:111"
  - id: F006
    severity: concern
    category: completeness
    summary: "Real-commit examples cover only some of the fairness checks"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:275"
  - id: F007
    severity: concern
    category: consistency
    summary: "Verification step 4 expects every line to read `reused`, which the plan cannot produce"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:284"
  - id: F008
    severity: concern
    category: sequencing
    summary: "`is_test_side` needs the parent's `pyproject.toml` before any sandbox exists"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:35"
  - id: F009
    severity: concern
    category: scope
    summary: "Task 12 edits slice 421's module, which the design forbids"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:149"
  - id: F010
    severity: concern
    category: completeness
    summary: "The dependency-invoked callback test has no dependency to invoke it"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:176"
  - id: F011
    severity: concern
    category: completeness
    summary: "The yield counting unit is undefined"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:255"
  - id: F012
    severity: concern
    category: granularity
    summary: "The task file is overweight"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:116"
  - id: F013
    severity: note
    category: traceability
    summary: "Frontmatter lists a dependency the design does not"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:6"
  - id: F014
    severity: note
    category: completeness
    summary: "Some names and selections are left to the implementer"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:91"
  - id: F015
    severity: note
    category: verifiability
    summary: "Three pinned commit SHAs could not be checked from this review"
    location: "unverified"
  - id: F016
    severity: pass
    category: consistency
    summary: "421 names and existing helpers match the plan"
    location: "src/squadron/config/manager.py:145"
  - id: F017
    severity: pass
    category: completeness
    summary: "Separability values check out"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:249"
  - id: F018
    severity: pass
    category: granularity
    summary: "Test-with pattern and commit markers"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:55"
---

# Review: tasks — slice 422

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 12 pins a pyright check the Python adapter cannot pass until Task 17

Task 8 defines `FixCaseAdapter` with `boundary` and `trace` (design API Contracts). Task 12 gives `PythonFixCaseAdapter` only `language`, `is_test_side`, `is_test_source`, `lockfile_names`, `collect`, `overlay` and `grader_commands`. `boundary` and `trace` arrive in Task 17 (lines 190–191). Task 12's registry test requires pyright to accept the Python adapter as a `FixCaseAdapter`, and the commit gate requires zero pyright errors, so Task 12 cannot commit. Move `fix_case_adapter_for` and its pyright test to Task 17. Do not stub `boundary` and `trace` with `NotImplementedError`, which breaks LSP.

### [CONCERN] Task 19 collects at the wrong state and leaves timeouts and reference-side collection failures unmapped

Stage 5 reads "overlay the reference, `collect`, `sort_tests`". In Task 12, `overlay` writes test-side files only, so the literal order collects at parent-plus-overlay. Design D4 and Data Flow step 6 (design line 109) require collection at the reference state. At parent-plus-overlay, a reference test that imports a symbol the fix added fails collection. Stage 4's mapping then turns it into `collection_failed`, but the design says it must surface as `uses_symbol_added_by_fix` (design line 459). Also, the harness-failure bullet in Task 18 is scoped to pre-sandbox stages, and Task 19 names only "resolver or suite `HarnessFailure`". Collect and trace timeouts, and a reference-side `CollectionFailed`, have no stated mapping. Fix the wording to "switch to the reference state, collect, sort_tests" and map every collect, boundary and trace failure, with a test for each.

### [CONCERN] `gh` missing is specified two ways

Task 18 (line 211) requires a missing `gh` to yield a per-candidate `harness_error` with no rejection. Task 22 (lines 246 and 250) requires it to raise `BuildHalted` and exit 1, and the design's CLI section (design line 304) agrees with Task 22. The two tests cannot both pass. Decide one behaviour and state the rule that separates "halts the build" from "one candidate's `harness_error`".

### [CONCERN] Fixture scenarios are used before any task creates them

Task 10 (line 134) tests "the fixture fix from the success criteria" (one added test, one changed, one deleted, one added conftest fixture). Task 10 comes before Task 11, which creates `fix_history` and `fixfair_changes/`. Task 12 (line 154) refers to "the success-criteria scenario", and Task 13 (line 165) to "the fixture overlay scenario". Neither names a directory, and no task lists the scenarios. Task 21 (line 238) first enumerates them, after both. Have Task 11 create the success-criteria scenario under a named directory, and move Task 10's end-to-end assertion there.

### [CONCERN] The "records equal closing commits" criterion is tested only on discovery output

The design criterion (design line 373) is that the number of records equals the number of closing commits, checked against a fixture repository. Task 7 checks discovery candidates plus rejections, not stored `FixQualification` records. Task 22's count uses fakes, and Task 21 uses single-commit scenarios. Add a multi-commit fixture repository covering several rejection reasons, and assert the store holds one record per closing commit.

### [CONCERN] Real-commit examples cover only some of the fairness checks

The design criterion (design lines 376–380) says each check's examples are taken from squadron's real fix commits. Task 25 pins three rejected commits and one qualifying crash fix. The test-first pair (Task 13, line 165) and the qualifying CLI-driving boundary case (Task 17, line 198) are fixture-only. Pin one real commit for each, chosen from the Task 25 build, or narrow the criterion in the design.

### [CONCERN] Verification step 4 expects every line to read `reused`, which the plan cannot produce

Task 26 step 4 requires every line to say `reused` on a rebuild. Design D10 (line 241) reuses only by environment digest. Pre-sandbox outcomes carry `environment=None` and a `pre` key, and Task 18 has no reuse for them. A rejected candidate such as `issue_not_found` is therefore re-evaluated and prints its rejection (Task 22, line 246). The design's own walkthrough (design line 417) has the same error. Change the expectation to "every candidate that reached the sandbox prints `reused`".

### [CONCERN] `is_test_side` needs the parent's `pyproject.toml` before any sandbox exists

The Context Summary's gap list adds `lockfile_names` and `is_test_source` because diff classification runs before a sandbox exists. It omits `is_test_side(tree, path)`, which must read `testpaths` from the parent's `pyproject.toml` (Task 12, line 149; design line 146). Task 9 (line 122) calls `classify_diff(changes, adapter, parent_tree, read_parent, read_reference)` without saying what `parent_tree` is before a sandbox exists, or how `is_test_side` reads `testpaths` through `read_parent`. Add `is_test_side` to the gap list and state how the parent's config is read. Task 9's test should cover a `testpaths` setting.

### [CONCERN] Task 12 edits slice 421's module, which the design forbids

Task 12 says to extract 421's plugin-copy code from `python_adapter.py` into a shared function. The design's Integration Requirements (design line 395) say 421's sandbox, records and suite runner are used unchanged, and any needed change is a 421 defect fixed in 421. Move the extraction into slice 421's task list and make Task 12 depend on it. Do not duplicate the copy logic.

### [CONCERN] The dependency-invoked callback test has no dependency to invoke it

Task 15 requires a test that a Typer-style callback invoked by a library is not a crossing. The design's success criterion (design line 388) requires the same. Task 11 (line 137) gives the fixture project only pytest as a dependency, so no task adds a library that calls back into project code. Name that dependency in Task 11's fixture spec, along with the `uv.lock` change it causes.

### [CONCERN] The yield counting unit is undefined

Task 23 says "per-`TestRejection` counts under `no_qualifying_hidden_test`" without saying whether the unit is the candidate or the test verdict. The design example (design line 317) reads "no_qualifying_hidden_test 31 (patches_project_code 18, reaches_past_boundary 9, …)", which only works if each candidate counts once under one reason. Per-verdict counting would not. Pick the unit and write it into Task 23 so its hand-count test is well defined.

### [CONCERN] The task file is overweight

The file has 27 tasks. Two concrete changes would help. Fold Task 8 into Task 9: it is types only, its test checks frozenness and an int constant, and Task 9's commit already covers it. Split Task 12, which bundles five concerns plus the 421 refactor, into (a) file states and overlay and (b) collect, grader commands and registry, with the registry step moved to Task 17 (see the FAIL above). Keep Tasks 14–16 as separate steps: each has its own failure surface and commit.

### [NOTE] Frontmatter lists a dependency the design does not

The task frontmatter lists `320`; the design frontmatter lists only `[421, 420]`. Either the design is missing it or the task file is stale. Also, the design's gap corrections are deferred to Task 27 (line 292). Correct the design in the planning commit instead, since later readers trust it. Task 27 should name the slice-plan file it ticks: `project-documents/user/architecture/420-slices.model-benchmark.md` exists.

### [NOTE] Some names and selections are left to the implementer

`FrozenIssue` (Task 6, line 91) is returned by `freeze_issue` and used as the `task_text` carrier in Task 18, but it is never defined. Task 24 (line 264) does not say which project `show` reads (it has no `--repo`) or which record to print when a commit has several environment records; the design says the latest. Task 14 says trace mode runs "each requested test", but the pinned config (Context Summary line 36) has no node-id key. State that node ids are passed as pytest arguments.

### [NOTE] Three pinned commit SHAs could not be checked from this review

Task 25 pins `ebd45f3f`, `9fc4fc1c` and `d6535d62` as closing commits for `--commit`. This review had no git-log access, and the SHAs appear only in the design and task file. Task 22 raises on an unknown prefix, so a SHA that is not a candidate stops Task 25. Confirm each one closes an issue before Task 25 starts.

### [PASS] 421 names and existing helpers match the plan

Task 13's `NodeOutcome` and `FailureKind` values match slice 421's design (`project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md:213-221`). `get_positive_int_config` (manager.py:145) and the float overload of `get_typed_config` (manager.py:119) exist, as do `serves_host` (codehost/protocol.py:45), `list_remotes` (codehost/remotes.py:63) and `ProcessRunner` (core/process_runner.py:73). Task 1's gate is correct: `src/squadron/benchmark/` does not exist yet.

### [PASS] Separability values check out

I recomputed (z₀.₉₇₅ + z₀.₈₀)² × 0.5/3 ÷ 0.04 ≈ 32.70, so 33 cases. MDD is 0.199 at n=33 and 0.202 at n=32. Task 22's hand values are correct.

### [PASS] Test-with pattern and commit markers

Each implementation task carries its own tests. Commit markers sit at tested points, and Tasks 8, 10, 14 and 18 are covered by the next marker. No merge or push appears as a task.

### Run Digest

- Response length: 12540 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 12
- Tokens — prompt / cached / cache write / completion / reasoning: 569904 / 411110 / 158784 / 72858 / not computed
- Duration: 310.9 s
- Cost: $0.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
