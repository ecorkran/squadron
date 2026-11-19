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
reviewedSha: 699ca73f89d7308a139efb9cba6f858e5688bf32
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
effort: xhigh
turns: 20
promptTokens: 1072110
cachedTokens: 954781
cacheWriteTokens: 117305
completionTokens: 68656
durationSeconds: 300.6
costUsd: 0.167139
costBasis: provider
runId: run-20261119-p5-f4e1d1e9
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 6 leaves three test files loading moved recipes by path"
    location: "tests/benchmark/recall/test_recipe.py:82"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`live_services.py` is a consumer missing from the Migration Plan and Task 5"
    location: "src/squadron/benchmark/recall/live_services.py:23"
  - id: F003
    severity: concern
    category: consistency
    summary: "\"Import edits only\" is not true for Tasks 4 and 5"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:99"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "The new stage-config function has no test, and no test asserts `planned`"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:97"
  - id: F005
    severity: concern
    category: completeness
    summary: "The production source of alias settings for `planned` is not named"
    location: "src/squadron/benchmark/recall/stage_identity.py:51"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Failed-stage tests do not assert the file and record the success criterion requires"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:49"
  - id: F007
    severity: concern
    category: consistency
    summary: "Two usage-record conventions for the recipe name"
    location: "src/squadron/review/frontmatter_usage.py:43"
  - id: F008
    severity: concern
    category: size
    summary: "Task 4 is too large"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:77"
  - id: F009
    severity: concern
    category: size
    summary: "Task 18 is too large, and Task 19 is a test-only task after it"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:214"
  - id: F010
    severity: concern
    category: commit-cadence
    summary: "Commit markers sit after almost every task"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:61"
  - id: F011
    severity: concern
    category: process
    summary: "Task 1 commits the design edit onto the slice branch"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:59"
  - id: F012
    severity: concern
    category: completeness
    summary: "Task 1's list of design edits is incomplete, and its check command is hedged"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:57"
  - id: F013
    severity: pass
    category: traceability
    summary: "Success-criteria traceability"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:368"
  - id: F014
    severity: pass
    category: sequencing
    summary: "Sequencing and dependencies"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:63"
  - id: F015
    severity: note
    category: test-coverage
    summary: "Split review per part has no test"
    location: "project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md:216"
  - id: F016
    severity: note
    category: nfr
    summary: "No load-test task, which the design declares"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:286"
  - id: F017
    severity: note
    category: hazard
    summary: "Name collision with `ReviewCall`"
    location: "src/squadron/benchmark/grade_review.py:118"
---

# Review: tasks — slice 434

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 6 leaves three test files loading moved recipes by path

Task 6 moves `haiku-solr-luna-opus.yaml`, `haiku-sol-luna-opus.yaml` and `haiku-sol-opus.yaml` out of `review-recall-recipes/`. These tests still load them from that directory: `test_recipe.py:82` and `:91`, `tests/benchmark/recall/test_run_plan.py:129`, and `tests/cli/test_benchmark_recall_run.py:129` (through `committed.py:30`). Task 6's checks (task file lines 102–106) cover `uv build`, runbook paths and one report run. They do not update these paths or run `tests/benchmark/recall/`, so the commit at line 108 can leave the suite red. The design's Migration Plan (line 310) names only runbook paths. Fix: add these path updates to Task 6 and make its gate run `tests/benchmark/recall/` and `tests/cli/test_benchmark_recall_*.py`.

### [CONCERN] `live_services.py` is a consumer missing from the Migration Plan and Task 5

`live_services.py` imports `live_stage_config` (line 23) and passes it as `config_for` (line 63). `tests/cli/test_benchmark_recall_run.py` uses it at lines 16, 125 and 142. Task 5 (lines 97–98) says `stage_identity.py` keeps `resolve_alias_profile`, `builtin_template_hash` and `LiveStageResolver`, so `live_stage_config` is either removed or its signature changes. Either way this breaks `live_services.py`. Neither file is in Migration Plan row 4 (design line 307) or Task 5's consumer list. Fix: add both files to Task 5 and state what `config_for` becomes.

### [CONCERN] "Import edits only" is not true for Tasks 4 and 5

Task 5 (line 99) says the tests pass "with import edits only". Task 4 changes `resolve_recipe` from `(ref, repo_root)` (`src/squadron/benchmark/recall/recipe.py:77`) to `(ref, search_dirs)`, and `test_recipe.py:91` calls it with `REPO_ROOT`, so that test needs a call-site edit. Task 5 changes `live_stage_config`, which hardcodes its templates (`stage_identity.py:30`, `:54`). The design repeats the "import and path edits only" claim (lines 314 and 398). Fix: list the tests that need call-site changes, or correct the criterion.

### [CONCERN] The new stage-config function has no test, and no test asserts `planned`

Task 5 adds `recipes/stage_config.py` with new logic (the template hash becomes a parameter) but no test task covers it. Task 11's tests (lines 156–158) check call order, arguments and effort, not `planned`. Nothing asserts that a review stage's `StageConfig` carries the step's template hash and a comb stage's carries the built-in `comb` hash. D10's row key (design line 262) and the criterion "one row per recipe and stage identity" (design line 388) both depend on that. Fix: add a `planned` test to Task 11 or 5.

### [CONCERN] The production source of alias settings for `planned` is not named

`live_stage_config` gets the model and profile from benchmark's `resolve_alias_profile` (line 51), plus `model_allows_tools`, `model_max_output_tokens` and `model_effort`. The import-boundary test (Task 2) forbids `recipes/` from importing `benchmark`, and the design keeps `resolve_alias_profile` in `benchmark/`. Task 11 says "planned: every stage's StageConfig resolved before the first call" but does not say where the production runner gets model, profile, tool_use, max_output_tokens and effort. A junior would have to guess. Fix: name the production source (for example the `models/aliases.py` readers) and where the auth check runs.

### [CONCERN] Failed-stage tests do not assert the file and record the success criterion requires

The Context Summary (line 49) says every D5 row is asserted by outcome, log record, review file and record. Task 12 asserts only outcome and log (lines 167–169). The comb-failure row has no file or record assertion at the action level (Task 18, line 223). The partial-decision and repeated/unknown-id rows have no file or record assertion at any task level. The design requires all four for each row (lines 378–384). Fix: add those assertions to Tasks 18 and 20, or correct the Context Summary claim.

### [CONCERN] Two usage-record conventions for the recipe name

Task 14 (line 185) keeps the recipe name in `model`, which matches `record_from_frontmatter`: it sets `model=aiModel` and sets `alias` only for known aliases, so a recipe review gives `model=<recipe>, alias=None`. Task 17 (line 209) stamps `alias=<recipe>, model=None`. The design agrees with each side in a different place (D7 line 233, D9 line 253). Both records describe the same review's spend, and the task file does not rule out counting it twice through `artifact_usage.py:101–122`. Fix: pick one field, and say whether the stamped record and the frontmatter-derived record can both count the same review.

### [CONCERN] Task 4 is too large

Task 4 mixes a pure move with new behaviour. The move updates about 20 consumer files (lines 84 and 90) and deletes `recipe.py`. The new behaviour is a search with three functions, shadow WARNINGs, a stem check, and a new `recipe_dirs.py`. Split it: 4a is the move with import edits and green tests; 4b is the search and `benchmark_recipe_dirs`.

### [CONCERN] Task 18 is too large, and Task 19 is a test-only task after it

Task 18 covers classification, dispatch, the new `review_recipe.py`, metadata, usage stamping, the UNKNOWN verdict path, the exception path and executor sink plumbing, with five test bullets. Task 19 adds no code. Split Task 18 into the success path (dispatch, metadata, usage) and the failure paths (UNKNOWN, unexpected exception, `EmptyScopeError`), each with its own tests, and fold Task 19's bullets into the failure-path group.

### [CONCERN] Commit markers sit after almost every task

19 of 23 tasks carry a marker (lines 61, 68, 75, 92, 108, 114, 126, 136, 145, 171, 188, 195, 206, 212, 234, 247, 255, 264, 271). Task 10 (line 145) commits fixtures that no test uses until Task 11. Task 7 (line 114) is a two-bullet config key. Suggested groupings, each ending green: 2–4 as one refactor, 7 with 8, 10 with 11–12, 15 with 16, 17 with 18–19. That gives about 13 commits.

### [CONCERN] Task 1 commits the design edit onto the slice branch

Task 1 creates `434-slice…` and commits the design edit there (lines 59–61). The Git Rules say planning work, including slice design revisions, commits directly to the target and does not get a branch. Fix: commit the design edit to the target, then branch from it.

### [CONCERN] Task 1's list of design edits is incomplete, and its check command is hedged

The list (D1, D6, D7, D8, D10, Migration Plan) omits D5, which holds the not-combed and failure semantics that Context Summary gap 5 cites (line 44). It also omits the Architecture Component Structure table (design lines 92–102), which does not list `recipe_review.py`, `stage_config.py`, `recipe_dirs.py`, `review_recipe.py`, `real_work.py` or `metrology/recipe_review_models.py`. The design's frontmatter (lines 6–8) lists 430 and 425 but not 420 or 947, which the task file lists. The check on line 58 says "`cf validate design` (or the project's design check)". The guides name `cf validate design` (`guide.ai-project.004-slice-design.md:93`), so use that command alone.

### [PASS] Success-criteria traceability

Each functional criterion has a task: the three entry points and the `haiku-xhigh` unchanged check (Tasks 8, 9, 18, 20); unknown and colliding names (8, 9, 20); the five refusals (8, 9, 20); the two-by-two merge (11, 13, 14, 18, 20); the revise loop (19); the failed-stage rows (12, 13, 18–20, subject to the assertion finding above); the other failures (16, 18, 12); records (15, 16, 20); usage and cap (17, 19); and the real-work report (21). I found no scope creep: every task traces to a criterion, a decision or the Migration Plan.

### [PASS] Sequencing and dependencies

The dependency order is valid and has no cycles. Tests follow their implementation, except the noted gaps in Tasks 5, 6 and 10.

### [NOTE] Split review per part has no test

D3 (design line 167) says a split review runs the whole recipe per part and folds the parts. Task 18 describes this but no test names it. Not a success criterion, so this is optional.

### [NOTE] No load-test task, which the design declares

The design says no load tier is needed because no two model calls run at once. The runner is sequential and the path is not a simulation, network or concurrency path, so no `tests/load/` task or CI gate is required.

### [NOTE] Name collision with `ReviewCall`

`grade_review.py` defines its own `ReviewCall` alias. The `ReviewCall` moved by Task 5 is a different type. A junior could mistake one for the other when updating imports.

### Run Digest

- Response length: 13446 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 1072110 / 954781 / 117305 / 68656 / not computed
- Duration: 300.6 s
- Cost: $0.17 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
