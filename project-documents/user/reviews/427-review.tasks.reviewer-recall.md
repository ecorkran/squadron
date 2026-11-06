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
reviewedSha: f8780ebb70eb71789fb02ce427e1fe1669bdfa31
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: xhigh
turns: 10
promptTokens: 581151
cachedTokens: 405825
cacheWriteTokens: 175316
completionTokens: 72188
durationSeconds: 308.4
costUsd: 0.363803
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: testability
    summary: "Baseline flaky-node test cannot pass with the flaky fixture as specified"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:174"
  - id: F002
    severity: concern
    category: coverage
    summary: "Enclosing symbols are never recorded on planted defects"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:181"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 26 relies on a read that Task 10 does not perform"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:247"
  - id: F004
    severity: concern
    category: coverage
    summary: "Walkthrough step 2's hand check of a defect is missing"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:310"
  - id: F005
    severity: concern
    category: process
    summary: "Task 21 tells the agent to file a GitHub issue on zero yield"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:219"
  - id: F006
    severity: note
    category: consistency
    summary: "Task 1's grep list omits names whose homes change"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:69"
  - id: F007
    severity: note
    category: scope
    summary: "The `recall_unselected` fixture is beyond the design's list"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:165"
  - id: F008
    severity: note
    category: clarity
    summary: "Task 2's pointer to the existing test is wrong"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:79"
  - id: F009
    severity: note
    category: consistency
    summary: "Two commit titles do not name everything they commit"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:100"
  - id: F010
    severity: note
    category: clarity
    summary: "The DEVLOG path is never named"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:219"
  - id: F011
    severity: note
    category: consistency
    summary: "Task 37's design-name list omits `recall_stats.py`"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:328"
  - id: F012
    severity: note
    category: testability
    summary: "`config_recall` lacks the seed inputs its interval needs"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:235"
  - id: F013
    severity: note
    category: scope
    summary: "Some task pairs could merge"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md"
  - id: F014
    severity: pass
    category: coverage
    summary: "Functional success criteria all trace to tasks"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md"
---

# Review: tasks — slice 427

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Baseline flaky-node test cannot pass with the flaky fixture as specified

Task 13 defines `recall_flaky` to fail only on its third execution, so it "passes both baseline runs". Task 14 then asks for "a baseline with a flaky node excludes that node". With the default `benchmark.recall_verify_runs` of 2, both baseline runs pass and the node stays in the passing set, so the test fails. It can pass only with three baseline runs or a different fixture, and the task names neither. State the run count the test uses (for example `verify_runs=3`, so the third run fails).

### [CONCERN] Enclosing symbols are never recorded on planted defects

Design D6 (`project-documents/user/slices/427-slice.reviewer-recall.md:211`) says enclosing symbols are recorded on each defect when it is planted, and the anchor rule depends on them. Task 8 adds `enclosing_symbols`, but no task calls it when a defect is kept. Task 15 returns `PlantResult(kept, hung, skipped)` without saying what a kept defect contains, and Task 17 (line 193) writes the case without them. Task 22 tests use hand-built defects and Task 18 checks only the proving node, so a build could store `()` for every defect and anchor findings would never match, with no failing test. Tasks 8–9 also do not say whether `enclosing_symbols` and `tests_reaching` are adapter methods, which the protocol requires, or module functions. Name where a kept defect is assembled and add an assertion that a built defect carries its enclosing symbols.

### [CONCERN] Task 26 relies on a read that Task 10 does not perform

Task 26 takes the per-review figure from 425's `ReviewSummary` "(read the real cost field at Task 10)". Task 10's read step (line 133) covers only 421's `SuiteRun`/`FailureKind` and 424's lock helper. No earlier task reads 425's cost field, so the implementer would have to guess its name, which the do-not-guess rule forbids. Add that read to Task 10 or name the field once 425's `ReviewSummary` is confirmed.

### [CONCERN] Walkthrough step 2's hand check of a defect is missing

The design's walkthrough step 2 (design lines 428–433) requires a hand check: build a scratch set with `--limit 1 --keep`, apply one defect's edit in the kept tree, confirm the proving node fails with `.venv/bin/python -m pytest`, revert, and confirm it passes. Task 36 step 2 checks only the `show` output but claims to cover steps 2–6. Nothing else checks a stored edit against a real squadron build, since Task 18 uses a fixture. Add the scratch build and the hand check as sub-items with success criteria. Also say what happens if Task 21 keeps no case, since Task 36 needs one.

### [CONCERN] Task 21 tells the agent to file a GitHub issue on zero yield

CLAUDE.md allows an issue only when something is actually broken, or is high severity and reasonably likely. A build that keeps no cases is the yield risk the design already names (design Risk Assessment, line 460). It is a result to record, not a defect, and filing is outward-facing. Record the counts and dominant reason in the DEVLOG and report them to the Project Manager, and file an issue only if the rule's criteria are met.

### [NOTE] Task 1's grep list omits names whose homes change

The list omits `latest_recall_for`, `RecallSummary`, `recall_summary.py`, and the design's `recall_report.py` home for them (design line 255). It also omits `BenchmarkRecordStore` (design line 375, which the Context Summary moves to `RecallRecordStore`) and `recall_models.py`. The section list would catch these on a full read, but a grep-driven pass would not. Add them to the grep.

### [NOTE] The `recall_unselected` fixture is beyond the design's list

The design's Technical Requirements list five verification fixtures. `recall_hang` is needed for the `mutant_timeout` failure mode, but `recall_unselected` is not on the list. Empty selection is already covered by Task 15's scripted test, and Task 14's "unselected gives NotProved" duplicates the passes-under-defect case. It also adds a seventh `uv.lock` project to Task 13, already the largest artifact task. Drop it, or record why it is kept.

### [NOTE] Task 2's pointer to the existing test is wrong

The `judge_timeout_s` tests live in `tests/metrology/test_config.py` and `tests/cli/test_replay_judge.py`, not under `tests/config/`. Name `tests/config/test_keys.py` as the file to extend and point at the existing test to copy from.

### [NOTE] Two commit titles do not name everything they commit

The commit at line 100 covers Tasks 3–5 (operator table, adapter types, matcher constants, edit engine) but is titled only for the edit engine. The commit at line 213 covers Tasks 19–20 but names only the CLI. Retitle them.

### [NOTE] The DEVLOG path is never named

Tasks 21, 36 and 37 refer to "the DEVLOG" without a path. The repo has `DEVLOG.md` at the root and quarterly archives under `project-documents/user/archive/devlog/`. Name the active file and the entry format, or point to the guide that defines them.

### [NOTE] Task 37's design-name list omits `recall_stats.py`

Task 24 creates `benchmark/recall_stats.py`, which neither the design's Component Structure nor Task 37's list names. Add it.

### [NOTE] `config_recall` lacks the seed inputs its interval needs

`config_recall(per_case)` takes no `run_id` or `reviewer_key`, but its interval seed is `recall_seed(run_id, reviewer_key)`. Task 32 requires the summary and the report to print the same interval. Put the seed inputs in the signature so the two call sites cannot derive different seeds.

### [NOTE] Some task pairs could merge

Tasks 8 and 9 each add a small method to one adapter module, and Tasks 24 and 25 share one module and one commit. Merging each pair would remove a task header without losing a test. The 37-task count is high, but each task is small and the scope fits the slice.

### [PASS] Functional success criteria all trace to tasks

Build outcomes and rebuild identity (Tasks 11, 14–18), spacing and the no-overlap rule (Tasks 5, 15), the matcher list (Tasks 22–23, with the line-shift planter test in Task 15), run refusals, bound, cap and resume (Tasks 26–30), the report (Tasks 24–25, 31, 34), and 425's flag (Tasks 32–33) are all covered. The technical requirements are covered too: per-operator tests on real squadron source (Tasks 6–7), real-pytest fixtures (Tasks 13–14), and doubles for every rejection and absence (Tasks 17, 28). No task merges or pushes, and no load test or CI gate is needed because no NFR is restated. Cross-slice names check out: `ReviewCategory`, `SourceLanguage` and `CodeReviewFinding` exist in `src`, and 425's task file carries the `rules_hash` correction (line 48).

### Run Digest

- Response length: 9390 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 581151 / 405825 / 175316 / 72188 / not computed
- Duration: 308.4 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

Task numbers below are those of the revised task file (Tasks 9 and 25 were merged into 8 and 24, so later tasks shifted down).

- **[CONCERN] Baseline flaky-node test cannot pass with the flaky fixture as specified:** changed. Task 13 now says each flaky test starts from a fresh copy and four runs give pass, pass, fail, pass. Task 13 (verification) tests `baseline_passing` with `verify_runs=3` (excludes the node) and `verify_runs=2` (includes it), and the mutant-run case is described separately.
- **[CONCERN] Enclosing symbols are never recorded on planted defects:** changed. Task 14 `combine(kept, files, adapter)` now builds the final `PlantedDefect`s, including `enclosing_symbols` from `adapter.enclosing_symbols`, and has a test that a built defect carries them. Task 17's real build asserts the symbol names the function holding the edit. Task 8 now states `enclosing_symbols` and `tests_reaching` are `PythonRecallAdapter` methods.
- **[CONCERN] Task 26 relies on a read that Task 10 does not perform:** changed. The gate task (now Task 9) reads the field of 425's `ReviewSummary` that holds a review's cost, and the run-plan task (now Task 24) refers to "the cost field Task 9 read".
- **[CONCERN] Walkthrough step 2's hand check of a defect is missing:** changed. The walkthrough (now Task 34) has a hand-check item: scratch build with `--limit 1 --keep` (larger limit if nothing is kept), apply one stored edit, the proving node fails, revert, it passes. If the live build kept no case, step 2 writes `BLOCKED:` with the counts.
- **[CONCERN] Task 21 tells the agent to file a GitHub issue on zero yield:** changed. The live-build task (now Task 20) records counts and the dominant reason in `DEVLOG.md` and reports them to the Project Manager. It files an issue only if CLAUDE.md's criteria hold.
- **[NOTE] Task 1's grep list omits names whose homes change:** changed. Added `latest_recall_for`, `RecallSummary`, `BenchmarkRecordStore`, `RecallRecordStore`, `recall_models.py`, `recall_store.py`, `recall_summary.py` and `recall_stats.py`.
- **[NOTE] The `recall_unselected` fixture is beyond the design's list:** changed. Dropped from Task 13 (fixtures) and from the verification tests. Empty selection stays covered by the planting task's scripted test.
- **[NOTE] Task 2's pointer to the existing test is wrong:** changed. Task 2 now extends `tests/config/test_keys.py` in the style of `TestCodexTimeoutConfigKeys`.
- **[NOTE] Two commit titles do not name everything they commit:** changed. The Task 5 marker now names the operator table, adapter seam, matcher constants and edit engine. The Task 19 marker names the materializer with the build and show commands. I also retitled the matcher marker (adds `location_anchor`) and the runner marker (adds the run plan), which had the same problem.
- **[NOTE] The DEVLOG path is never named:** changed. The live-build, walkthrough and final tasks name `DEVLOG.md` at the repo root, under today's `## YYYYMMDD` heading, newest first.
- **[NOTE] Task 37's design-name list omits `recall_stats.py`:** changed. Added to the final-validation list and to the Context Summary module list that Task 1 writes into the design.
- **[NOTE] `config_recall` lacks the seed inputs its interval needs:** changed. It now takes `run_id` and `reviewer_key` and derives the seed inside through `recall_seed`. `latest_recall_for` calls the same function, so the two cannot differ.
- **[NOTE] Some task pairs could merge:** changed. Merged the enclosing-symbols and import-closure tasks, and the two statistics tasks. The file went from 37 to 35 tasks and all references were renumbered. References to other slices' task numbers (425 Tasks 7, 21, 38, 45) were left unchanged.
- **[PASS] Functional success criteria all trace to tasks:** no change needed.
