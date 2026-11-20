---
docType: tasks
slice: recipe-reviews-in-pipelines
project: squadron
lld: user/slices/434-slice.recipe-reviews-in-pipelines.md
dependencies:
- 430
- 425
- 420
- 947
projectState: Slices 420–426 and 430 complete; 0.24.34 released with `sq benchmark
  recall`. Slice 434 design revised through review round 4 (CONCERNS). Target is main
  (git.integration_branch empty).
dateCreated: 20261119
dateUpdated: 20261119
status: in_progress
turns: 31
promptTokens: 2619319
cachedTokens: 2492805
cacheWriteTokens: 126454
completionTokens: 45308
durationSeconds: 405.5
costUsd: 2.416914
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 2.4169140000000002
    completionTokens: 45308
revision_number: 2
---

## Context Summary
- Working on slice 434: a 430 recipe is accepted by name wherever a review takes one model (pipeline `review-model`, step `review.model`, `sq review --model`). Design: `user/slices/434-slice.recipe-reviews-in-pipelines.md`; its D-numbers (D1–D11) are cited below instead of repeating them. Read the cited decision before each task.
- Paths: source modules are relative to `src/squadron/`, tests to the repo root, `user/...` documents to `project-documents/`.
- Delivers: the `recipes/` package (moved 430 recipe model, comb call, decisions parser; new search, classification, runner, merge, record sink), recipe reviews from `sq review` and the review action, the review file's recipe frontmatter and stage table, the `recipe_review` metrology record, the summed usage record under the pipeline cost cap, and `sq benchmark recall report --real-work`.
- Excluded (design Technical Scope): changing any shipped `review-model` default (D11, #369), concurrent stages (#372), per-stage caps, MCP, `pool: true` recipes in reviews, combs on document reviews, recipes on judge templates, cross-reviewer dedupe, stage reuse across rounds, known-bug recall for real work, anything for 435/436.
- Design gaps found while reading the code. Task 1 writes each into the design; later tasks follow the corrections:
  - **Eight recipe files stay, not six.** `user/reference/review-recall-recipes/` holds 11 files; 3 move (D1), so `haiku-mimo-opus`, `haiku-opus`, `haiku-sol-pool`, `haiku-xhigh`, `luna`, `sol`, `sonnet-high`, `sonnet` stay.
  - **`RECIPES_DIR` home.** It is defined in `benchmark/recall/recipe.py`, which moves. It goes to a new `benchmark/recall/recipe_dirs.py` with `benchmark_recipe_dirs(repo_root)` (`RECIPES_DIR`, then the shipped directory), used by the three benchmark commands.
  - **D2 signatures.** `classify_review_model(name, *, profile_source, search_dirs)` returns `AliasRef(name)` or `RecipeRef(recipe, path)`. The `RecipeRef` refusals are a separate `validate_recipe_review(ref, *, template, has_diff, explicit_profile)`, called right after classification at each site, because the pre-run check and execution know different inputs.
  - **Stage config takes the template.** `live_stage_config` hardcodes `code`/`comb` templates via `STAGE_TEMPLATES` and gets model and profile from benchmark's `resolve_alias_profile`. `recipes/stage_config.py` holds `stage_config(alias, model, profile, template_hash) -> StageConfig` (reads `model_allows_tools` and `model_max_output_tokens` from `models/aliases.py`), `alias_stage_config(alias, template_hash)`, the production entry: model and profile from `resolve_model_alias` (`models/aliases.py`), raising when the alias has no profile, and `planned_stages(recipe, review_template_hash) -> list[StageConfig]`, one per `required_stages` entry. Production runs no auth check; member aliases are already checked by `require_known_model` at classification (D2). `live_stage_config` keeps its signature `(alias, stage_kind)` in `benchmark/recall/stage_identity.py` and calls `stage_config`, so `live_services.py` (`config_for=live_stage_config`) and `tests/cli/test_benchmark_recall_run.py` are unchanged. A recipe review's review stages use the step's own template hash, comb stages the built-in `comb` hash.
  - **Recipe data on `ReviewResult`.** `review/` cannot import `recipes/`, so `review/models.py` gains `RecipeReviewInfo(name, complete, stage_section)` and `ReviewResult.recipe: RecipeReviewInfo | None = None`. `stage_section` is the rendered "Recipe" markdown section built by `recipe_merge`. `ReviewResult.to_dict()` is unchanged (API Contracts: same JSON shape).
  - **Reviewer and "not combed" marks (D5, D6).** `ReviewFinding` gains no field. `recipe_merge` appends one line to each finding's description: `Reviewer: <alias>`, plus `(not combed: <comb alias> failed)` when it passed through a failed comb.
  - **Shared caller flow (D5, D8).** Save-then-record, the aborted record, the synchronous write on cancellation and the record-write catch are the same for the CLI and the action. They live once in `recipes/recipe_review.py` (`run_recipe_review`), which takes the review call, the save callable and the sink as arguments.
  - **Recipe name in usage records (D7, D9).** Both usage records of a recipe review carry the recipe name in `alias` and `model=None`: the stamped action record (D9; `RunSpend` keys its unpriced warning on `alias`) and `record_from_frontmatter`, which sets `alias` from `aiModel` when `aiRecipe` is true. They feed different totals, as for a single-model review today: the stamped record feeds `RunSpend`; the frontmatter record feeds per-file reports (`stats/`, `review/artifact_usage.py`). Neither total reads the other, so no review is counted twice in one total.
  - **Other `aiModel` readers (D7).** `stats/reviews_report.py:104` (`sq stats reviews`) and `stats/review_rounds.py:113` (the effort report) read `aiModel` as the reviewing model. A recipe review is listed there under the recipe name, the only name the whole review has; neither reader changes.
  - **Slash command rendering.** `pipeline/prompt_renderer.py` `_render_review` resolves the review model for display; a recipe name raises `UnknownModelAliasError` there and logs a traceback through `_logger.exception` on every render. It classifies the name first and uses the recipe name as the display model for a `RecipeRef`. The rendered `sq review ... --model <name>` command is unchanged.
  - **`report --set`.** `--set` is a required option today; it becomes optional and is required unless `--real-work` is given.
  - **Migration is not import-only.** Call-site edits beyond imports: `resolve_recipe` now takes search directories (`test_recipe.py` lines 14, 91, 92, 99, 100, 105; the three `benchmark_recall_*` commands' `load_recipes` calls); the three moved recipe files are loaded from the shipped directory in `test_recipe.py:82` and `:91`, `test_run_plan.py:129`, `test_benchmark_recall_run.py:129` and `test_reproduce_results.py` (`_committed`, line 36, used at line 94), with `committed.py:30`'s `RECIPES_DIR` as the old directory; `test_recipe.py`'s `COMMITTED` set drops the three moved names.
  - **Component table.** The Architecture table also lists `recipes/stage_config.py`, `recipes/kept_findings.py`, `recipes/recipe_review.py`, `benchmark/recall/recipe_dirs.py`, `benchmark/recall/real_work.py`, `metrology/recipe_review_models.py`, `pipeline/actions/review_recipe.py` and `cli/commands/review_recipe.py`. The design frontmatter's `dependencies` gains 420 and 947.
- Large files: `pipeline/actions/review.py` (782 lines), `cli/commands/review.py` (1,589) and `review/persistence.py` (1,149) only gain dispatch lines; the recipe paths go in new `pipeline/actions/review_recipe.py` and `cli/commands/review_recipe.py`.
- Shared names (defined once, never compared as literals): `AliasRef`/`RecipeRef` (matched by type), `RECORD_TYPE_RECIPE_REVIEW` in `metrology/models.py`, record id prefix `rrev-`, frontmatter keys `aiRecipe`/`recipeComplete` as constants in `review/persistence.py`, config key `review.recipe_stage_slow_s`, 430's `StageKind`, `StageOutcome`, `CombVerdict`.
- Failure modes: every row of both D5 tables and D8's write failure is asserted in the task that builds it: outcome and log record in Tasks 10–12 (kept rule, runner), verdict in 13, records and write failures in 15 (caller flow); the review file's stage table and the `recipe_review` record for every failed-stage row in 17 (action); exit codes in 19 (CLI).
- Tests run no model: the review call, the comb call and the record sink are injected. Pyright covers `src` only. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), the touched area's tests. Nothing here pushes or merges.
- Effort 5/5. Next planned slice: 431 (Implementation Report from Run Records).

## Tasks

### Task 1: Commit the task file, correct the design, create the branch
- [x] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file, commit it by path as `docs: revise slice 434 tasks`
  Note: target is main (integration_branch unset); the branch forks from main after b324ccdf, which carries the task file. No separate tasks commit was needed.
- [x] Write each Context Summary design gap into the design, as a plain statement, not a change note: D1, D2, D5, D6, D7, D8, D9, D10, API Contracts (slash commands), the Architecture Component Structure table, the Migration Plan (including its "import and path edits only" lines) and the frontmatter `dependencies`. Bump `dateUpdated`
  Note: design content verified in b324ccdf.
  - [x] `cf validate design` passes on the edited file
    Note: verified 20261119: `cf validate design` prints PASS.

**Commit**: `docs: correct slice 434 design for recipe dirs, stage config, result carrier`

- [x] After that commit on the target, create `434-slice.recipe-reviews-in-pipelines` from the target and switch to it

### Task 2: `recipes/` package and its import boundary
- [x] Create `recipes/__init__.py` (docstring: production recipe reviews, slice 434)
- [x] Add `tests/recipes/test_import_boundary.py`: walks the AST of every module under `recipes/` and asserts no import of `squadron.pipeline`, `squadron.cli` or `squadron.benchmark`; walks `review/` and `metrology/` and asserts none imports `squadron.recipes`
  - [x] Test passes on the empty package and fails when a forbidden import is added (check once by hand, then remove it)
    Note: verified 20261119: a temporary recipes module importing squadron.pipeline made test_recipes_imports_nothing_above_it fail; removed, the test passes.

### Task 3: Move `SCORED_SEVERITIES`, publish `verdict_from_findings`, move the recipe model
- [x] Move `SCORED_SEVERITIES` from `benchmark/recall/scoring.py` to `review/models.py`, next to `Severity`. Update `scoring.py` and `label_candidates.py` imports; no re-export
- [x] Rename `review/parsers.py` `_verdict_from_findings` to `verdict_from_findings`; update every caller in `src/` and `tests/`
- [x] Move `Recipe`, `RequiredStage`, `RecipeError`, `load_recipe`, `required_stages`, `RECIPE_SUFFIX` to `recipes/recipe.py`, unchanged. `benchmark/recall/recipe.py` keeps only `RECIPES_DIR`, `resolve_recipe` and `load_recipes` (removed in Task 4). Update the imports of every consumer in the Migration Plan's first row; no shims
  - [x] `tests/benchmark/recall/`, `tests/cli/test_benchmark_recall_*.py`, the review parser tests and the import boundary test pass with import edits only
    Note: also added `haiku-mimo-opus` and `haiku-opus` to `test_recipe.py`'s `COMMITTED`; the test already failed on main because those two files were added to the directory without updating it.

**Commit**: `refactor: add recipes package, move recipe model and scored severities`

### Task 4: Recipe search by name (D1)
- [x] `recipes/recipe.py` `load_recipe` also checks `name` equals the file stem and raises `RecipeError` with the path when it does not
- [x] Add `recipes/recipe_search.py`:
  - [x] `resolve_recipe(ref, search_dirs) -> Path`: a ref with a directory part or a `.yaml`/`.yml` suffix is a path as given; a name is `<name>.yaml` in the first directory that holds it. A later directory holding the same name logs one WARNING naming both files. No match raises `RecipeError` listing the known names across all directories
  - [x] `load_recipes(refs, search_dirs)`; a file found that fails to load raises, and the search never moves on
  - [x] `production_recipe_dirs(cwd)`: `cwd / project-documents/user/recipes`, then `data_dir() / "recipes"`. `find_recipe(name, search_dirs) -> tuple[Recipe, Path] | None` for classification (names only; `None` when no directory holds it)
    Note: the Path feeds RecipeRef(recipe, path) (D2); item text corrected to the shipped signature.
- [x] Replace `benchmark/recall/recipe.py` with `benchmark/recall/recipe_dirs.py` (`RECIPES_DIR`, `benchmark_recipe_dirs(repo_root)`). The three `benchmark_recall_*` commands' `load_recipes` calls and `test_recipe.py` lines 14, 91, 92, 99, 100 and 105 use `benchmark_recipe_dirs`
- [x] Tests in `tests/recipes/test_recipe_search.py`:
  Note: `test_recipe.py`'s `_write` helper now names the file after the recipe (`r.yaml`, `sol.yaml`), since `load_recipe` checks name against stem.
  - [x] first match wins; a shadowed name logs the WARNING naming both files
  - [x] a broken file found by name raises with its path even when a later directory has a good one
  - [x] `name` not matching the stem raises; an unknown name lists known names
  - [x] a path ref is returned as given; `find_recipe` returns `None` for an unknown name
- [x] One test each for `run` (`tests/cli/test_benchmark_recall_run.py`), `label` (`tests/cli/test_benchmark_recall_label.py`) and `report` (`tests/benchmark/recall/test_run_end_to_end.py`) that `--recipe <name>` (no path) reaches the command's recipe loading by name
- [x] `tests/benchmark/recall/` and `tests/cli/test_benchmark_recall_*.py` pass

**Commit**: `feat: find recipes by name across project and shipped directories`

### Task 5: Move the comb call, decisions parser and stage config
- [x] Move `parse_decisions` and its types from `benchmark/recall/decisions.py` to `recipes/decisions.py`, unchanged
- [x] Move `render_findings`, `run_comb_stage`, `COMB_ALLOWED_TOOLS`, `ReviewCall`, `StageModel` from `benchmark/recall/stage_command.py`, and `finding_id_at`, `FINDING_ID_PREFIX` from `benchmark/recall/review_output.py`, to `recipes/comb_call.py`. `stage_command.py` keeps its file I/O helpers. This `ReviewCall` is not `benchmark/grade_review.py`'s alias of the same name; leave that one alone
- [x] Add `recipes/stage_config.py` with `stage_config`, `alias_stage_config` and `planned_stages` (Context Summary, "Stage config takes the template"). `live_stage_config` keeps its signature and calls `stage_config`
  Note: `builtin_template_hash` moved with it (as `recipes/stage_config.py`'s `builtin_template` / `builtin_template_hash`, raising `StageConfigError`), since `planned_stages` needs the comb hash and `recipes/` cannot import `benchmark/`; `live_stage_config` wraps `StageConfigError` in `StageIdentityError`.
- [x] Update the imports in Migration Plan rows 2–5 (`benchmark_recall_stage.py`, `stage_command.py`, `review_output.py`, `hand_run_combs.py`, `stage_ingest.py`, `stage_identity.py`, `test_stage_command.py`, `test_decisions.py`, `test_stage_identity.py`). `live_services.py` needs no edit. No shims
- [x] Tests in `tests/recipes/test_stage_config.py`: the same alias with a review template hash and with the `comb` hash gives different `config_key`s; `tool_use` and `max_output_tokens` come from the alias; `alias_stage_config` raises for an alias with no profile; `planned_stages` for two reviewers and two combs gives six configs in `required_stages` order, review stages with the given hash and comb stages with the `comb` hash
  - [x] `tests/benchmark/recall/`, `tests/cli/test_benchmark_recall_*.py` and the import boundary test pass

### Task 6: Move the three shipped recipe files
- [x] `git mv` `haiku-solr-luna-opus.yaml`, `haiku-sol-luna-opus.yaml`, `haiku-sol-opus.yaml` from `user/reference/review-recall-recipes/` to `src/squadron/data/recipes/`. The other eight stay
- [x] Confirm none of the three names is an alias in `data/models.toml`
- [x] Load the moved files from the shipped directory in `test_recipe.py:82` and `:91`, `test_run_plan.py:129` and `test_benchmark_recall_run.py:129`; `test_reproduce_results.py`'s `_committed` (line 36) loads by name through `load_recipes(names, benchmark_recipe_dirs(REPO_ROOT))`, so `committed.py`'s `RECIPES_DIR` no longer decides where `haiku-sol-opus` is; drop the three names from `test_recipe.py`'s `COMMITTED`
- [x] Confirm the wheel carries them: `uv build --wheel` and list the archive for `squadron/data/recipes/`. Edit `pyproject.toml` only if they are missing
  Note: verified 20261119: the built wheel lists squadron/data/recipes/haiku-sol-luna-opus.yaml, haiku-sol-opus.yaml and haiku-solr-luna-opus.yaml; pyproject.toml unchanged.
- [x] Update recipe paths in `user/reference/review-recall-runbook.md` where it names a moved file
  Note: the runbook named no moved file by path; its recipe sentence now names the shipped directory and the search order.
- [x] Behavior check: `uv run sq benchmark recall report --set real-bugs-original --runs 1 --recipe haiku-sol-opus --recipe haiku-xhigh` prints the same rows as before the move (run it on the target first and keep the output for comparison)
  Note: the baseline was captured on the slice branch after Tasks 2-5 and before the file move, which is the change being checked.
  - [x] `tests/benchmark/recall/` and `tests/cli/test_benchmark_recall_*.py` pass

**Commit**: `refactor: move comb call and decisions to recipes, ship three recipe files`

### Task 7: `review.recipe_stage_slow_s` config key
- [x] Add `review.recipe_stage_slow_s` to `config/keys.py`: int seconds, default 1800, description names the slow-stage WARNING (D3, D5)
- [x] Extend the existing config key tests: default, type, and that `sq config get review.recipe_stage_slow_s` reads it

**Commit**: `feat: add review.recipe_stage_slow_s config key`

### Task 8: Classify a review model name (D2)
- [x] `recipes/model_ref.py`:
  - [x] `AliasRef(name)` and `RecipeRef(recipe, path)` frozen dataclasses; `ReviewModelRef = AliasRef | RecipeRef`
  - [x] `classify_review_model(name, *, profile_source, search_dirs) -> ReviewModelRef`: alias (or literal model id with a profile source, via `require_known_model`'s rule) gives `AliasRef`; `find_recipe` hit gives `RecipeRef`; both raises the collision message from D2; neither raises the existing unknown-alias message with the known recipe names appended. One exception type, `ReviewModelError`
  - [x] `validate_recipe_review(ref, *, template, has_diff, explicit_profile)`: raises `ReviewModelError` naming the recipe and the member for: a reviewer or comb alias failing `require_known_model`; `pool: true`; `template.is_judge`; combs with `has_diff` false; `explicit_profile` set
- [x] Tests in `tests/recipes/test_model_ref.py`, recipe directories in `tmp_path`:
  - [x] alias, literal id with profile source, recipe, both, neither (message lists close aliases and recipe names)
  - [x] each of the five refusals, asserting the recipe and member in the message
  - [x] `haiku-xhigh` classifies as `AliasRef` with the squadron checkout's real production dirs (the benchmark file of that name is outside them)

**Commit**: `feat: classify review model names as alias or recipe`

### Task 9: Pre-run checks and slash command rendering accept recipe names (D2)
- [x] `pipeline/classification.py`, at both review-candidate sites (`classify_pipeline` and `_classify_container_inner`, where `_collect_unknown_alias` runs today): for a review action, call `classify_review_model` first. An `AliasRef` continues to `_collect_unknown_alias` and `resolve_model_alias` as today. A `RecipeRef` is validated with `validate_recipe_review` (template from the step, `has_diff` from whether the template takes a `diff` input, profile from the step), and then classified with `_classify_alias_set(reviewers + combs, ..., f"recipe {name}")`. Every `ReviewModelError` is collected into `alias_errors` (add it to `PreRunNameError`), so one pre-run error lists every bad name
  Note: a review step's own `profile` key is not passed into its review action, so the explicit profile checked is the action config's `profile` or the run's `profile` param, as the review action reads it.
- [x] `pipeline/loader.py` `_validate_model_alias`: literal review-model names go through `classify_review_model`, so a recipe passes and its member aliases are checked
- [x] `pipeline/prompt_renderer.py` `_render_review`: classify the name before `resolver.resolve`; a `RecipeRef` uses the recipe name as the display model and does not call the resolver (Context Summary, "Slash command rendering")
- [x] Tests (existing classification, loader and prompt renderer test files):
  - [x] `review-model: haiku-sol-opus` passes the pre-run check; an unknown name fails before any step starts with the recipe names listed; a recipe with an unknown member fails naming it
  - [x] a recipe on a step with an explicit `profile` and on a judge template are refused
  - [x] a rendered review step with a recipe model emits `--model <recipe>` and logs no ERROR record
  - [x] existing classification, loader and renderer tests pass unchanged

**Commit**: `feat: accept recipe names in the pipeline pre-run check and slash commands`

### Task 10: Kept-findings rule (D5)
- [x] `recipes/kept_findings.py`, pure functions over findings and parsed comb decisions:
  - [x] `comb_input(findings)`: the CONCERN/FAIL findings (`SCORED_SEVERITIES`) a chain starts from; NOTE/PASS are returned separately and never combed
  - [x] `apply_comb(findings, decisions) -> CombStep(kept, dropped, undecided)`: KEEP stays in the chain, DROP is dropped, a finding with no decision is `UNDECIDED`, kept, and not passed to the next comb
  - [x] `chain_result(steps)`: the kept set after the chain is everything still KEEP plus every undecided finding
    Note: signature is `chain_result(initial, steps)` so a recipe with no combs keeps its whole input and the kept set keeps the reviewer's order; also added `decisions_by_finding` (positional `F1..Fn` to finding ids) and `pass_through` (a failed comb).
- [x] Tests in `tests/recipes/test_kept_findings.py`: KEEP/DROP/UNDECIDED over a two-comb chain; first-comb UNDECIDED not in the second comb's input and kept; NOTE/PASS never in a comb input; empty input gives empty steps

### Task 11: Recipe runner and stage loop (D3, D4)
- [x] Fixtures in `tests/recipes/conftest.py` and `tests/recipes/support.py`:
  - [x] `ScriptedReviewCall`: an async callable matching `run_review_with_profile`'s use, returning a scripted `ReviewResult` (or raising `ProviderError`) per (alias, stage index); records every call's alias, template, `allowed_tools`, cwd and prompt input
  - [x] `FakeRecipeSink` collecting `write(record, raw_outputs)` calls, with a switch to raise `MetrologyStoreError` or `OSError`
  - [x] a `tmp_path` git repo with one commit adding a defect, and the two-reviewer, two-comb recipe file used across the tests
  - [x] helpers building `ReviewFinding` lists and comb decision output text in the format `parse_decisions` reads
- [x] `recipes/recipe_runner.py`:
  - [x] `RecipeStageResult` (kind, reviewer, alias, config, `effort_sent`, findings, decisions, duplicate/unknown counts, usage, outcome, reason, raw output, `not_combed` ids) and `RecipeOutcome` (stages, kept findings per reviewer, uncombed NOTE/PASS findings per reviewer, `complete`, `planned`)
  - [x] `RecipeProgress`: a caller-owned list the runner appends each finished stage to
  - [x] `run_recipe(recipe, *, review_call, comb_call, review_inputs, changed_files, cwd, slow_after_s, progress)`: `planned` from `planned_stages` before the first call; walks `required_stages(recipe)`; a review stage calls `review_call` with the step's template and inputs and the reviewer alias; a comb stage calls `comb_call` (`run_comb_stage`) with the `comb` template, `COMB_ALLOWED_TOOLS`, the input from `kept_findings`, and `changed_files`; an empty comb input makes no call and is `ok`. No `git` call of its own
    Note: the review side is one `RecipeReviewCall(template, inputs, options, review_call, comb_call)` argument; `options` carries the caller's rules, allowed tools and pricing set, and per-alias settings come from `stage_config.stage_model`. `run_comb_stage` was split into a typed `call_comb` (returns `CombCallResult`), which the runner uses, and the benchmark's document wrapper. Types live in `recipes/recipe_outcome.py`.
  - [x] INFO log at each stage start and finish with recipe, stage and alias
- [x] Tests in `tests/recipes/test_recipe_runner.py`:
  - [x] stage order and call count for two reviewers and two combs; each comb gets the `changed_files` passed in and `COMB_ALLOWED_TOOLS`; each reviewer gets the step's template and inputs
  - [x] `RecipeOutcome.planned` equals `planned_stages` for the recipe and the step template's hash; kept findings per reviewer match `kept_findings` on the scripted decisions; empty comb input makes no call
  - [x] `effort_sent` is `None` when the stage result has no effort, never the alias's configured effort

### Task 12: Runner failures and the slow-stage warning (D5)
- [x] Failed stages, each logged at WARNING with recipe, stage and reason, `complete` false:
  - [x] reviewer raises `ProviderError` → `harness_failure` with the error text; its combs do not run
  - [x] reviewer verdict UNKNOWN → `config_failure`; its findings are not used
  - [x] comb raises `ProviderError` or returns no parseable decision → `harness_failure`/`config_failure`; its input passes on uncombed and marked `not_combed`; the next comb runs on it
  - [x] partial decisions → `ok`, missing ids `UNDECIDED`, `complete` unaffected
  - [x] repeated or unknown ids → `ok`, WARNING with both counts, first decision wins, counts on the stage
- [x] Any other exception propagates unhandled; finished stages remain in `progress`
- [x] Slow stage: one timer per stage call; past `slow_after_s` it logs one WARNING with recipe, stage, alias and elapsed time; the timer is cancelled when the call returns; the call is never stopped
- [x] Tests (same file), each asserting outcome and log record: every row above; an unexpected `RuntimeError` leaves the finished stages in `progress`; a stage outlasting a small `slow_after_s` logs exactly one WARNING and finishes

**Commit**: `feat: add recipe runner with kept-findings rule and stage failures`

### Task 13: Combine recipe stages into one review result (D5, D6)
- [x] `recipes/recipe_merge.py` `merge_recipe(outcome, recipe_name, template_name, input_files) -> ReviewResult`:
  - [x] findings: reviewer 1's kept, reviewer 2's kept, then NOTE/PASS in reviewer order; reviewer and not-combed line appended per finding (Context Summary); ids renumbered by the existing `F{n:03d}` rule
    Note: ids renumber with no extra code: `structured_findings` numbers `F{n:03d}` by position over the merged list.
  - [x] verdict: `verdict_from_findings` over the merged findings; incomplete and PASS → UNKNOWN; incomplete with any CONCERN/FAIL kept → FAIL
  - [x] `cost_usd`, `duration_seconds`, `turns`, `tool_calls_made` summed over stages
  - [x] `recipe = RecipeReviewInfo(name, complete, stage_section)`: the "Recipe" section with one row per stage (D7 columns) and each failed stage's reason, plus a line saying the FAIL comes from the incomplete recipe when that rule applied; `raw_output` is the rendered summary
  - [x] dropped findings appear nowhere in the result
- [x] Add `RecipeReviewInfo` and `ReviewResult.recipe` to `review/models.py`; `to_dict()` unchanged
- [x] Tests in `tests/recipes/test_recipe_merge.py`: order and renumbering; PASS when every CONCERN was dropped while a reviewer stated CONCERNS; incomplete+PASS → UNKNOWN; incomplete+CONCERN kept → FAIL with the stage-section line; all reviewers failed → UNKNOWN; sums; no dropped finding in findings or `raw_output`; `to_dict()` keys equal a single-model result's

### Task 14: Review file frontmatter and stage section (D7)
- [x] `review/persistence.py`: constants for `aiRecipe` and `recipeComplete`. When `result.recipe` is set: `aiModel` is the recipe name, `aiRecipe: true`, `recipeComplete`, and `aiProfile`/`requestedModel` omitted; `recipe.stage_section` is written before `## Findings`
- [x] `review/frontmatter_usage.py` `record_from_frontmatter`: when `aiRecipe` is true, `alias` is `aiModel` and `model` is `None` (Context Summary, "Recipe name in usage records")
- [x] Confirm `metrology/identity.py` is reached only for judge templates (no code change expected)
- [x] Tests (existing persistence, frontmatter usage and stats test files): a recipe result's file has the three keys, no `aiProfile`/`requestedModel`, the stage section before findings; its usage record has `alias` = recipe name and `model` `None`; `sq stats reviews` and the effort report list a recipe review file under the recipe name; a single-model result's file is byte-identical to before
  Note: single-model byte identity is asserted by the existing fixtures in tests/review/test_persistence_migration.py (unchanged on this branch, passing); a 20261119 render of a single-model result on main and on the branch compared identical with cmp. Recipe usage record asserted in tests/stats/test_reviews_report.py.

**Commit**: `feat: write recipe reviews as one review file with a stage table`

### Task 15: `recipe_review` record, sink and the shared caller flow (D5, D8)
- [x] `metrology/recipe_review_models.py`: `RecipeStage` and `RecipeReview` with the fields in the design's schema tables, reusing 430's `StageKind`, `StageConfig`, `RecallFinding`, `CombDecision`, `StageUsage`, `StageOutcome`; no new enum. `RECORD_TYPE_RECIPE_REVIEW = "recipe_review"` and the sibling payload in `MetrologyRecord` (`metrology/models.py`); id `rrev-<utc timestamp>-<8 hex>` from a `new_recipe_review_id(clock)` helper
- [x] `recipes/recipe_record.py`: `RecipeRecordSink` protocol (`write(record, raw_outputs) -> None`, synchronous); `MetrologyStoreRecipeSink` (writes the record with `write_record`, raw stage outputs to the `REVIEWS` content sidecar, `raw_ref` = sha256); `build_recipe_record(outcome, ...) -> RecipeReview` from a `RecipeOutcome` or a `RecipeProgress`
  Note: `build_recipe_record(facts, context)` takes a `RecipeRecordFacts` (stages from a `RecipeOutcome` or a `RecipeProgress`, plus the plan) and a `RecipeRecordContext` (project id, clock, run linkage); `raw_outputs` maps each `raw_ref` to the JSON document it hashes.
- [x] `recipes/recipe_review.py` `run_recipe_review(...)`, used by both callers; returns the merged `ReviewResult`, the record id or `None`, and the outcome:
  - [x] runs the runner, merges, saves through the injected save callable, then writes the record via `asyncio.to_thread`; a save that raises writes the record with `review_file: null`, then re-raises
  - [x] catches `MetrologyStoreError` and `OSError` from the write only, logs at ERROR with the record id, comment gives D8's reason, record id `None`
  - [x] unexpected exception: `logger.exception`, writes the aborted record (finished stages, `complete: false`, UNKNOWN, `aborted` = error text), no review file, re-raises
  - [x] `asyncio.CancelledError`: WARNING, calls `sink.write` directly (not awaited) with the aborted record; a write error there is logged at ERROR; the cancellation re-raises
- [x] Tests:
  - [x] `tests/metrology/test_recipe_review_models.py`: round-trip through `MetrologyRecord`; null `run_id`/`step_name`/`iteration`/`review_file`; `effort_sent: null` survives; id format
  - [x] `tests/recipes/test_recipe_review.py` with the fakes: order save→record; save raises → record with null file and error propagates; sink raises `MetrologyStoreError`/`OSError` → ERROR log, result returned, record id `None`; unexpected exception → aborted record, no save; cancellation mid-recipe → aborted record written synchronously and `CancelledError` propagates; real `MetrologyStoreRecipeSink` on a `tmp_path` store writes the record and sidecar

**Commit**: `feat: add recipe_review record, sink and shared recipe review flow`

### Task 16: Review action runs recipes: usage and success path (D2, D3, D8, D9)
- [x] `pipeline/actions/review_recipe.py` `recipe_usage_record(recipe_name, stages) -> UsageRecord`: `alias` = recipe name, `model` None, `cost_usd` = sum of known costs (None when none known), turns/duration/tokens summed per field, `cost_basis` the common basis else None; each unpriced stage named in one WARNING
- [x] `pipeline/actions/review.py` `_resolve_model`: classify the winning cascade candidate; validate a `RecipeRef` against the template, the resolved `diff` input and the step profile. `_run_part` sends a `RecipeRef` to `review_recipe.py` after the existing rules, input validation, task merge gate and scope check; an `AliasRef` runs as today
- [x] `review_recipe.py` runs `run_recipe_review` once per split part, with `changed_files` from the existing `assert_reviewable_scope` result, the executor-provided sink, run id, step name and loop iteration; folds parts as today
  Note: a project with no git remote and no recorded `metrology.project_id` cannot key a record; that is treated as a record-write failure (ERROR log, `recipe record: not written`), never a review failure. `allowed_tools: []` isolation refusal applies to single-model steps only.
- [x] `ActionResult`: verdict and findings as today; `metadata["recipe"]` = name, `complete`, record id (or `recipe record: not written`); usage stamped with `stamp` and `recipe_usage_record`
- [x] Pipeline executor passes `MetrologyStoreRecipeSink` into the action context
  Note: `recipe_sink` is threaded through the executor beside `usage_capture` into every `ActionContext`; `execute_pipeline(recipe_sink=...)` defaults to `metrology_recipe_sink(cwd)`, whose store opens on each write so a store problem is a D8 write failure, not a run-start failure.
- [x] Tests in `tests/pipeline/actions/test_review_recipe.py`, scripted review call on the fixture repo:
  - [x] `recipe_usage_record`: all priced; one unpriced (floor, WARNING names it); none priced (`cost_usd` None); mixed bases → None
  - [x] `review-model: <recipe>` and step `model: <recipe>` each run the recipe; metadata and usage record match
  - [x] a failing input validation makes no recipe stage call (D3)
  - [x] revise loop with a recipe reviewer: every stage runs in both rounds (call counts)
  - [x] existing review action tests pass unchanged

### Task 17: Review action failure paths, loop exhaustion and the cost cap (D5, D9)
- [x] UNKNOWN merged verdict → `success=False` with an error naming the failed stages; unexpected exception → failure result with the finished stages' spend stamped; usage stamped on every failure result
- [x] Tests (same file, plus the loop and executor test files), each failed-stage row asserting the review file's stage table and the `recipe_review` record:
  - [x] one reviewer fails, CONCERN kept → success, FAIL, `complete: false`; nothing kept → `success=False`, review file and record exist; every reviewer fails → same
  - [x] a comb fails → kept and marked not combed, next comb ran, `complete: false`
  - [x] a comb decides only some findings → the rest kept as undecided, `complete: true`
  - [x] a comb repeats an id and names an unknown one → first decision wins, both counts in the record and the WARNING
  - [x] unexpected exception → aborted record, spend stamped, no review file; `EmptyScopeError` on a bad range → no model call, no record
  - [x] last round ends incomplete with a CONCERN kept: `accept_if: review.concerns_or_better` does not accept, the exhaust path runs
  - [x] `--max-cost` below the recipe total stops the run after the step with the existing cap error; one unpriced stage: `RunSpend` counts the priced sum

**Commit**: `feat: run recipe reviews from the pipeline review action`

### Task 18: `sq review`: classification, refusals and dispatch (D2)
- [x] `cli/commands/review.py` `_run_review_command`: classify the resolved name; on `ReviewModelError` print it and exit 1 before any call; validate a `RecipeRef` (`--profile` refused, combs without `--diff` refused); a `RecipeRef` goes to `cli/commands/review_recipe.py`
  Note: each subcommand (code, slice, tasks, arch) now hands its save step to `_run_review_command` as a run-once `CliPersist`; the recipe path saves through it before writing the record, a single-model review saves after it returns as before. `sq review pr` hands no save step, so a recipe name there is refused with a message naming the four subcommands.
- [x] `review_recipe.py`: runs `run_recipe_review` with the metrology-store sink, null run linkage and the CLI's save callable
- [x] Tests in `tests/cli/test_review_recipe.py`, scripted review call:
  - [x] unknown name and collision exit 1 with no call; each refusal exits 1 naming the recipe
  - [x] a recipe name runs every stage and saves one review file
  - [x] `sq review ... --max 1` with a recipe builds the loop pipeline with `review-model` set to it

### Task 19: `sq review`: output, exit codes and `--no-save` (D5, API Contracts)
- [x] `review_recipe.py`: prints the stage table at `-v`; UNKNOWN prints the failed stages and exits 1 with the review file and record written; prints `recipe record: not written` when the write failed; `--output json` prints `to_dict()`; `--no-save` skips the file and writes the record with `review_file: null`
- [x] Tests (same file):
  - [x] end-to-end `sq review code --diff HEAD~1 --model <recipe>` on the fixture repo: one review file, stage table, record written, combs got the scope-check file list
  - [x] one reviewer fails and nothing kept → exit 1, file and record exist; sink raises → result printed and `recipe record: not written`
  - [x] `--output json` shape equals a single-model review's keys; `--no-save` writes no file and a record with `review_file: null`
  - [x] existing review CLI tests pass unchanged

**Commit**: `feat: run recipe reviews from sq review`

### Task 20: `report --real-work` (D10)
- [x] `benchmark/recall/real_work.py`: reads `recipe_review` records of the current project via `iter_records`; row key = recipe name, recipe hash, `planned` config keys; columns per D10; "effort differs" when run stages of one alias sent different efforts; "config differs" when rows share a recipe name; `--recipe` filter
    Note: records are read through a new `RecallRecordStore.list_recipe_reviews()` (over `iter_records`) and filtered to the current project. Kept counts undecided findings too (D5's one meaning of kept); Undecided is shown separately as a subset. `--recipe` stays required (with a clear error) unless `--real-work` is given.
- [x] Render the table in `report_render.py` style; `--real-work` on `benchmark_recall_report.py`; `--set` optional and required otherwise (clear error naming the flag)
- [x] Tests in `tests/benchmark/recall/test_real_work.py`: a complete, an empty-input-comb, a skipped-chain and an aborted record of one config land in one row with the right Incomplete and aborted counts; two efforts → one row flagged; changed template hash → new row, "config differs"; unpriced count; no `--set` with `--real-work` works, without either errors
  - [x] existing report tests pass unchanged

**Commit**: `feat: add real-work table to sq benchmark recall report`

### Task 21: Docs, slash command, P6 comment, CHANGELOG
- [x] `docs/PIPELINES.md`, `docs/COMMANDS.md` and `README.md` where they describe `review-model`/`--model`: a recipe name is accepted, searched in `project-documents/user/recipes/` then the shipped recipes, how to add one, and what is refused
- [x] `commands/sq/benchmark.md`: `report --real-work`
- [x] `data/pipelines/P6.yaml` comment above `review-model`: recipe names accepted, the three shipped recipes named; default unchanged (D11)
- [x] CHANGELOG `### Added` bullet, user-facing (recipe names in reviews; real-work report)
- [x] `ruff format`, `ruff check`, `pyright` (zero errors), full `pytest` pass

**Commit**: `docs: document recipe reviews and the real-work report`

### Task 22: Verification walkthrough
- [x] Steps 1–3 and 6 of the design's walkthrough (no model calls); record output summaries under the walkthrough
- [x] Steps 4, 5 and 7 (live). Step 5 needs a fixture project registered with cf; create it in a temp directory. If `OPENROUTER_API_KEY` or Codex credentials are absent, write `BLOCKED:` with the missing credential under this item and leave it unchecked
- [x] Update the design's walkthrough with the actual commands and results; set the design and this file's `status` to `complete` only when every item is checked

**Commit**: `docs: record slice 434 verification walkthrough`
