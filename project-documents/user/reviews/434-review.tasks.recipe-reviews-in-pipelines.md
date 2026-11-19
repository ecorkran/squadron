---
docType: review
layer: project
reviewType: tasks
slice: recipe-reviews-in-pipelines
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261119
dateUpdated: 20261119
reviewedSha: 583335a23e1b7de34bf23110cf97fb75b103e3f4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
effort: xhigh
turns: 29
promptTokens: 1239458
cachedTokens: 1112782
cacheWriteTokens: 126652
completionTokens: 77804
durationSeconds: 327.8
costUsd: 0.228558
costBasis: provider
runId: run-20261119-p5-f4e1d1e9
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Task 5 names one `resolve_recipe` call in `test_recipe.py`; four more break under the new signature"
    location: "tests/benchmark/recall/test_recipe.py:92"
  - id: F002
    severity: concern
    category: completeness
    summary: "Task 7 misses `test_reproduce_results.py`, which loads the moved `haiku-sol-opus` from the old directory"
    location: "tests/benchmark/recall/test_reproduce_results.py:94"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Recipe names in slash commands take an exception-logging path that no task covers"
    location: "src/squadron/pipeline/prompt_renderer.py:262-277"
  - id: F004
    severity: concern
    category: design-consistency
    summary: "D2's signature and `RecipeRef` fields contradict Task 9, and Task 1 does not list D2 for correction"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:146"
  - id: F005
    severity: concern
    category: design-consistency
    summary: "D7's reader audit misses two stats readers that will show the recipe name as a model"
    location: "src/squadron/stats/reviews_report.py:104"
  - id: F006
    severity: concern
    category: completability
    summary: "Task 10's central step names no function"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:136"
  - id: F007
    severity: concern
    category: size
    summary: "Tasks 12 and 13 both grow `recipes/recipe_runner.py` past the size rule"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:152-177"
  - id: F008
    severity: concern
    category: granularity
    summary: "Task 21 bundles five surfaces and six test groups"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:240-251"
  - id: F009
    severity: note
    category: commit-cadence
    summary: "Task 8 has no commit marker, and Task 1's commit message is wrong"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:119-121"
  - id: F010
    severity: note
    category: granularity
    summary: "Task 11 is a fixture-only task that precedes its consumers, and several tasks are very small"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:145-150"
  - id: F011
    severity: note
    category: coverage
    summary: "No task checks that every 430 command resolves a recipe by name"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:114"
  - id: F012
    severity: note
    category: coverage
    summary: "D3's \"rules and inputs validated once before the first stage\" has no test"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:166"
  - id: F013
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks with no functional or failure-mode gaps"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:366-395"
  - id: F014
    severity: pass
    category: scope
    summary: "No scope creep, and excluded items stay out"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:56-275"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing and dependencies hold"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:58-275"
  - id: F016
    severity: pass
    category: accuracy
    summary: "Code references in the tasks exist where the tasks say"
    location: "src/squadron/review/parsers.py:146"
  - id: F017
    severity: pass
    category: nfr
    summary: "No load-test task is needed"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:286"
  - id: F018
    severity: pass
    category: proportionality
    summary: "One task file is the right size"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:56"
---

# Review: tasks — slice 434

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 5 names one `resolve_recipe` call in `test_recipe.py`; four more break under the new signature

Task 5 (task file line 90) says the three `benchmark_recall_*` commands and `test_recipe.py:91` move to the search-directory signature. `test_recipe.py` also calls `resolve_recipe` at lines 92, 99, 100 and 105, and imports it at line 9. Add those lines to Task 5's list. The three commands call `load_recipes` (`benchmark_recall_report.py:33`, `benchmark_recall_label.py:75`, `benchmark_recall_run.py:70`), and Task 5 covers them.

### [CONCERN] Task 7 misses `test_reproduce_results.py`, which loads the moved `haiku-sol-opus` from the old directory

Line 94 calls `_committed("haiku-sol-opus", ...)`. Line 36 loads each name from `RECIPES_DIR / f"{name}.yaml"`, and `RECIPES_DIR` is defined at `tests/benchmark/recall/committed.py:30` as the old directory. After Task 7 moves the file, this test fails. Task 7 (task file line 111) lists only `test_recipe.py:82`/`:91`, `test_run_plan.py:129` and `test_benchmark_recall_run.py:129`. Add this file and the `committed.py` helper to the path edits. The design's Migration Plan (line 304) also omits them.

### [CONCERN] Recipe names in slash commands take an exception-logging path that no task covers

The design says slash commands get recipe reviews "with no change of their own" (design line 329). But `_render_review` calls `resolver.resolve(alias_str)` at line 261. A recipe name is not an alias, so the call should raise one of the caught types. The handler at line 273 then calls `_logger.exception`, which writes a full traceback on every render. The command still renders correctly because the fallback is display-only. I did not trace the resolver's exact raise type, so confirm that first. Add a task item that classifies the name before resolving it, or skips resolution for recipe names, and a test asserting that a rendered recipe review logs no exception.

### [CONCERN] D2's signature and `RecipeRef` fields contradict Task 9, and Task 1 does not list D2 for correction

D2 says `classify_review_model(name, profile_source)` returns `RecipeRef(recipe)` (line 148). Task 9 (task file lines 125-126) uses `classify_review_model(name, *, profile_source, search_dirs)` and `RecipeRef(recipe, path)`. The task file tells the implementer to read the cited decision before each task, so the contradiction surfaces at Task 9. Add D2 to Task 1's list of design corrections (task file line 60).

### [CONCERN] D7's reader audit misses two stats readers that will show the recipe name as a model

D7 (design lines 231-234) lists the readers of `aiModel` as identity (judge only) and `frontmatter_usage`. Two more exist: `stats/reviews_report.py:104` and `stats/review_rounds.py:113`. Both read `aiModel` as a model, so `sq stats` will list a recipe review under the recipe name. That may be the right result, but neither the design nor the tasks decide it. Add both readers to D7 with the decision, and extend Task 15's confirm item (task file line 192) with a check that `sq stats reviews` handles a recipe file.

### [CONCERN] Task 10's central step names no function

"Session classification treats the recipe as its member aliases" does not say which function changes or what a recipe contributes to it. The relevant code is `pipeline/classification.py:421`, where `require_known_model(candidate, profile_source=...)` runs per candidate. Name the function, state what a `RecipeRef` contributes to it, and state whether validation runs before that. Without this, the implementer has to guess.

### [CONCERN] Tasks 12 and 13 both grow `recipes/recipe_runner.py` past the size rule

One module is asked to hold the stage walk, `planned`, the kept-findings rule, the failure table, the slow-stage timer, the outcome and progress types, and a `run_recipe` with nine keyword arguments. The project's guidelines cap source files near 300 lines and functions near 50. Split the kept-findings rule (a pure function with its own tests) and the planned-config builder into separate modules, and name them in Tasks 12 and 13.

### [CONCERN] Task 21 bundles five surfaces and six test groups

Task 21 covers classification and refusals, recipe dispatch, stage-table printing, exit codes for UNKNOWN and sink failure, `--output json`, `--no-save`, and `--max 1` loop wiring. Split it into 21a (classification, refusals and dispatch, with the refusal tests) and 21b (output, exit codes, `--no-save`, and the end-to-end test). Give each a commit marker or fold them into one, as the group's size warrants.

### [NOTE] Task 8 has no commit marker, and Task 1's commit message is wrong

Task 8 (the config key) has tests and no marker, so it lands in Task 9's `feat: classify review model names` commit under an unrelated message. Give it its own marker, or move it before Task 9. Task 1 (line 59) says to commit the task file as `docs: add slice 434 tasks`, but the file is already in history (`583335a2`, `699ca73f`), so the subject should be `docs: revise slice 434 tasks`.

### [NOTE] Task 11 is a fixture-only task that precedes its consumers, and several tasks are very small

Task 11 has no code or tests of its own and comes before its only consumers (Tasks 12 and 13), which breaks the test-with pattern. Fold it into Task 12. Tasks 3, 8, 16 and 18 are each a few lines or one function. Merging 3 into 4, 16 into 17 and 18 into 19 would cut commits without losing any test.

### [NOTE] No task checks that every 430 command resolves a recipe by name

Design line 398 says every 430 command works by recipe name. Task 7's behavior check runs `report` only. `run`, `label` and the stage commands rely on existing test suites, and no task asserts name resolution through each command's parser. Add a parser-level name test per command to Task 5.

### [NOTE] D3's "rules and inputs validated once before the first stage" has no test

D3 says rule checks, input validation, the tasks merge gate and the scope check run once before the first stage. No task asserts that a validation failure makes no recipe call. Placing dispatch after the existing validation probably satisfies this already, so one test in Task 19 would pin it.

### [PASS] Success criteria map to tasks with no functional or failure-mode gaps

Each functional bullet has a task: classification and refusals (9, 10, 21), the two-reviewer, two-comb merge and verdict (12, 14, 19), the revise loop (19), each failed-stage row (13, 14, 17, 20, 21), record writes and failed writes (17, 21), the cost cap and unpriced stage (18, 20), and the real-work table (22). Each D5 failure row has a runner test and an action or CLI test.

### [PASS] No scope creep, and excluded items stay out

Every task traces to a design decision. No task changes a shipped default, adds concurrency, adds per-stage caps, builds MCP, or reuses stage output across rounds. Task 23's P6 change is comment-only, as D11 requires.

### [PASS] Sequencing and dependencies hold

Each task consumes only earlier outputs: Task 8's config key before Task 13's timer, Task 14's `RecipeReviewInfo` before Task 15, Task 17's sink before Task 19. The import-boundary test (Task 2) comes before the moves. I checked the moved modules: `recipe.py`, `decisions.py` and `review_output.py` import nothing from `benchmark/`, and `stage_command.py`'s benchmark imports (`decisions`, `review_output`) move with it. The boundary test should pass after the moves.

### [PASS] Code references in the tasks exist where the tasks say

Verified: `_verdict_from_findings` (`review/parsers.py:146`), `SCORED_SEVERITIES` (`benchmark/recall/scoring.py:36`), `record_from_frontmatter` (`review/frontmatter_usage.py:38`), `run_comb_stage` (`benchmark/recall/stage_command.py:77`), `parse_decisions` (`benchmark/recall/decisions.py:55`), `live_stage_config` (`benchmark/recall/stage_identity.py:46`), and the alias helpers in `models/aliases.py`. All 11 benchmark recipe files exist, and every `name:` matches its file stem, so Task 5's new stem check will not break the shipped set. The runbook Task 7 edits exists.

### [PASS] No load-test task is needed

The design restates no NFR with a threshold, and it rules out a load tier because no two model calls run at once. The new code adds no concurrency. No `tests/load/` task or CI gate is required, and none is missing.

### [PASS] One task file is the right size

The 24 tasks follow the design's module boundaries and the Migration Plan touches dozens of consumer files. A single file fits, and no split into several task files is needed.

### Run Digest

- Response length: 13941 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 29
- Tokens — prompt / cached / cache write / completion / reasoning: 1239458 / 1112782 / 126652 / 77804 / not computed
- Duration: 327.8 s
- Cost: $0.23 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18

## Resolution

Task numbers below are those of the revised task file (22 tasks; merges and splits renumbered them).

- [concern] `resolve_recipe` calls in `test_recipe.py`: fixed. Task 4 and the "Migration is not import-only" gap list lines 14, 91, 92, 99, 100 and 105.
- [concern] `test_reproduce_results.py` loads `haiku-sol-opus` from the old directory: fixed. Task 6 changes `_committed` (line 36) to load by name through `benchmark_recipe_dirs`, and the migration gap names the file and `committed.py:30`.
- [concern] Slash command rendering logs an exception for recipe names: fixed. Confirmed that `resolver.resolve` raises `UnknownModelAliasError` for a recipe name. Added a "Slash command rendering" gap, a `_render_review` item in Task 9, and a test that a rendered recipe step logs no ERROR record.
- [concern] D2 signature and `RecipeRef` fields contradict the tasks: fixed. Added a "D2 signatures" gap and added D2 to Task 1's list of design corrections.
- [concern] D7 misses two stats readers: fixed. Added an "Other `aiModel` readers" gap (a recipe review is listed under the recipe name; neither reader changes). Task 14 tests `sq stats reviews` and the effort report on a recipe file.
- [concern] Task 10's classification step names no function: fixed. Task 9 now names `classify_pipeline` and `_classify_container_inner`, says validation runs before `_classify_alias_set(reviewers + combs, ...)`, and collects `ReviewModelError` into `alias_errors` through `PreRunNameError`.
- [concern] `recipe_runner.py` too large: fixed. The kept-findings rule is now `recipes/kept_findings.py` (Task 10, with its own tests), and the planned-config builder is `planned_stages` in `recipes/stage_config.py` (Task 5, tested there).
- [concern] Task 21 bundles five surfaces: fixed. Split into Task 18 (classification, refusals, dispatch, refusal tests) and Task 19 (output, exit codes, `--no-save`, end-to-end), sharing one commit marker.
- [note] Task 8 has no commit marker; Task 1's commit message: fixed. The config key (Task 7) has its own marker, and Task 1's subject is now `docs: revise slice 434 tasks`.
- [note] Fixture-only task and very small tasks: fixed. Fixtures are folded into the runner task (Task 11). Old Task 3 is merged into the recipe-model move (Task 3), the record payload into the sink and flow (Task 15), and the usage record into the action success path (Task 16).
- [note] No 430 command checks resolution by name: fixed. Task 4 adds one test each for `run`, `label` and `report` with `--recipe <name>`.
- [note] D3's validation-before-first-stage has no test: fixed. Task 16 adds a test that a failing input validation makes no recipe stage call.
- [pass] Success-criteria traceability: no change.
- [pass] No scope creep: no change.
- [pass] Sequencing and dependencies: no change; it still holds after renumbering.
- [pass] Code references exist: no change.
- [pass] No load-test task needed: no change.
- [pass] One task file is the right size: no change (283 lines).
