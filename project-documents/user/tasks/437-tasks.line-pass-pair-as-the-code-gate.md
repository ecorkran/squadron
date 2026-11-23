---
docType: tasks
slice: line-pass-pair-as-the-code-gate
project: squadron
lld: user/slices/437-slice.line-pass-pair-as-the-code-gate.md
dependencies:
- 430
- 434
projectState: Slices 430 and 434 complete. Slice 437 design revised after its review
  (CONCERNS, resolution recorded in the review file); every decision D1–D11 is decided.
  Target is main (git.integration_branch empty).
dateCreated: 20261123
dateUpdated: 20261123
status: not_started
turns: 24
promptTokens: 1429695
cachedTokens: 1348904
cacheWriteTokens: 80751
completionTokens: 20196
durationSeconds: 196.8
costUsd: 1.320188
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.3201878
    completionTokens: 20196
---

## Context Summary
- Working on slice 437: the code review gate of `P6`, `implement`, `implement-plan` and the `review` pipeline becomes the recipe `haiku-line-pass`: `haiku-xhigh` with tools plus a no-tools `haiku` line pass with its own rules file, merged into one review, with a category filter deciding which CONCERN and FAIL findings set the verdict. Design: `user/slices/437-slice.line-pass-pair-as-the-code-gate.md`. Its D-numbers (D1–D11) are cited below instead of repeating them; read the cited decision before each task.
- Paths: source modules are relative to `src/squadron/`, tests to the repo root, `user/...` documents to `project-documents/`. The measured run lives in `user/reference/review-recall-results/20261122-martian/` (below: `MARTIAN/`).
- Delivers: `reviewer_options` (`tools`, `rules`) and `keep_categories` on recipes; both options in the stage identity; `split_by_category`; the "Not gating" table and the `keep_categories` record field; the benchmark's filter scoring, report columns and real-work column; the refusals for #393; the shipped recipe and rules file; the four pipeline defaults; docs.
- Excluded (design Technical Scope): cross-reviewer dedupe (435), reviewers that read earlier findings (436), duplicate aliases in one recipe, `keep_categories` with `combs` (#392, refused), benchmark run/scoring of reviewers with options (#393, refused/left out), `P56` and `P456` (#390), the `code` template's own `model`, a stage time bound, the full 50-PR benchmark run (the PM's, after the slice).
- Identity safety (D1, D4): a recipe with neither new key keeps its `recipe_hash` and every stage `config_key`. Task 2 pins today's values before any model change; that test must pass unchanged at the end.
- Large files: `recipes/recipe_runner.py` (322 lines) gains only call sites; per-reviewer call options go in new `recipes/reviewer_options.py`. `review/persistence.py` gains only the Findings heading rule.
- Shared names, defined once and never compared as literals: `ReviewCategory` values (`core/finding_categories.py`); `RULES_SEPARATOR` (`project_rules/render.py`); the "Not gating" heading and the "No gating findings; N not gating (see the Recipe section)." line, each a constant in the module that writes it; issue numbers in refusal messages (#393) as one constant per message site.
- `split_by_category` is the only place a finding's category is compared with the kept list (runner, scoring, real-work all call it).
- Failure modes asserted where they are built: rules-file read failures and bad keys in Task 4; a failed line pass in Task 9 (outcome, WARNING) and Task 21 (stage table, record, verdict); refusals in Tasks 13, 15, 16.
- Tests run no model: the review call is scripted as in 434's tests (`tests/recipes/support.py`, `tests/recipes/conftest.py`). Alias resolution is isolated by monkeypatching `aliases.load_user_aliases`, as `tests/recipes/test_stage_config.py` does. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), the touched area's tests. Nothing here pushes or merges.
- Effort 3/5. Next open entries in the 420 plan: 431, 432, 435, 436 (435 and 436 build on this slice's reviewer options).

## Tasks

### Task 1: Create the slice branch
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target; `git status --short` is clean
- [ ] Create `437-slice.line-pass-pair-as-the-code-gate` from the target and switch to it
  - [ ] `git branch --show-current` prints the slice branch name

### Task 2: Pin today's recipe identities (test infrastructure)
- [ ] Add `tests/recipes/test_identity_pins.py`. With `aliases.load_user_aliases` monkeypatched to return `{}` (built-in aliases only) and one fixed review template hash constant, for every recipe in the shipped directory (`shipped_recipes_dir()`, 2 files) and `user/reference/review-recall-recipes/` (11 files):
  - [ ] Assert `recipe_hash(load_recipe(path))` equals a value recorded in the test now, on the unchanged code
  - [ ] Assert the `config_key` of each `planned_stages(recipe, <fixed hash>)` entry equals a value recorded now
  - [ ] The recorded values are literal strings in the test (generated once by running the current code, then pasted); the test passes on the unchanged code
- [ ] Note in the test module docstring: values recorded before slice 437; they must never be regenerated by this slice (D1, D4)

**Commit**: `test: pin recipe hashes and stage keys before slice 437`

### Task 3: Recipe model: `reviewer_options`, `keep_categories`, rules file read (D1, D3, D5)
- [ ] In `recipes/recipe.py` add `ReviewerOptions`: `tools: bool = True`, `rules: str | None = None` (the file name as written), and loader-set `rules_path: Path | None` and `rules_content: str | None`
- [ ] Add `Recipe.reviewer_options: Mapping[str, ReviewerOptions]` (alias to options, empty by default) and `Recipe.keep_categories: tuple[ReviewCategory, ...] | None = None`. `Recipe.reviewers` stays a tuple of alias strings; existing `Recipe(reviewers=(...))` constructions still type-check
- [ ] `load_recipe` validation, each failure a `RecipeError` naming the recipe path and the problem:
  1. a `reviewer_options` key not in `reviewers`
  2. an unknown option key inside an entry
  3. a `rules` value with a directory part, an absolute path or `..`
  4. a rules file that is missing, raises `OSError` on read, raises `UnicodeDecodeError`, or is empty; the message names the rules file name
  5. a `keep_categories` value that is not a `ReviewCategory` value (message names the value and lists the valid ones)
  6. an empty `keep_categories` list
  7. `keep_categories` together with `combs` (message names #392)
- [ ] `load_recipe` resolves `rules` in the recipe file's own directory, reads it as UTF-8, and sets `rules_path` (absolute) and `rules_content`
- [ ] The recipe file's own read: catch `UnicodeDecodeError` beside the existing `OSError` and `yaml.YAMLError`, raising `RecipeError`
- [ ] Keep `recipe.py` near the ~300-line guideline; if validation pushes it over, move option parsing to a helper module inside `recipes/`

### Task 4: Recipe model tests
- [ ] Add tests in `tests/recipes/test_recipe_options.py`, writing recipe and rules files to `tmp_path`:
  - [ ] A recipe with neither new key loads with empty `reviewer_options` and `keep_categories is None`
  - [ ] A recipe with `reviewer_options` and `keep_categories` loads; `rules_path` is absolute and in the recipe's directory; `rules_content` equals the file
  - [ ] One test per refusal 1–7 of Task 3, each asserting `RecipeError` and that the message names the stated item (the four rules-file failures are four tests; non-UTF-8 uses bytes such as `b"\xff\xfe"`)
  - [ ] A recipe file that is not UTF-8 raises `RecipeError`, not `UnicodeDecodeError`
- [ ] `uv run pytest tests/recipes tests/benchmark/recall/test_recipe.py -q` passes, Task 2's pins included

### Task 5: `recipe_hash` canonical form (D1)
- [ ] In `recipes/recipe_record.py`, `recipe_hash` dumps `name`, `reviewers`, `pool`, `combs` as today, plus `reviewer_options` only when non-empty (per entry: `tools`, the `rules` file name, sha256 of `rules_content`, or `None` for each rules field when there is no rules file) and `keep_categories` only when set. `rules_path` and `rules_content` are never in the dump
- [ ] Tests in `tests/recipes/test_recipe_options.py`:
  - [ ] Task 2's pins pass unchanged
  - [ ] Changing the rules file content changes `recipe_hash`; changing `tools` changes it; adding `keep_categories` changes it
  - [ ] Moving the recipe and its rules file to another directory does not change `recipe_hash` (path not in the dump)

**Commit**: `feat: add reviewer options and category filter to recipe files`

### Task 6: Stage identity (D4)
- [ ] `metrology/recall_run_models.py`: `StageConfig.rules_hash: str | None = None`; `config_key` includes it only when set
- [ ] `recipes/stage_config.py`: `stage_config` and `alias_stage_config` take `options: ReviewerOptions | None = None`. With options: `tool_use` is `False` when `tools` is false (whatever the alias allows), and `rules_hash` is sha256 of `rules_content` when set. With `None`: today's config
- [ ] `planned_stages` passes each review stage's `recipe.reviewer_options.get(alias)`; comb stages pass none
- [ ] `ConfigFor`, `live_stage_config`, `StageIdentityResolver.resolve`, `PendingStage`, `review_argv` and their test doubles are unchanged (D8)
- [ ] Tests in `tests/recipes/test_stage_config.py`:
  - [ ] Calls with no options give the same `config_key` as before (existing tests pass unchanged; Task 2 pins pass)
  - [ ] A stored `StageConfig` JSON with no `rules_hash` loads and keeps its key
  - [ ] Two rules contents give two keys; `tools: false` gives `tool_use is False` and a different key from the same alias with tools
  - [ ] `planned_stages` on a recipe with options gives the line-pass stage `tool_use False` and a `rules_hash`, the other reviewer's stage unchanged

**Commit**: `feat: include reviewer tools and rules in the stage identity`

### Task 7: `split_by_category` (D5)
- [ ] In `recipes/kept_findings.py` add `split_by_category(findings, keep) -> (gating, not_gating)`, pure, beside `comb_input`. Reads each finding's normalized category (`RecallFinding.category`). Only CONCERN and FAIL findings can be not gating; NOTE and PASS findings are returned in `gating`, unchanged. A CONCERN/FAIL finding with no category is gating. `keep is None` returns every finding as gating
- [ ] Tests in `tests/recipes/test_kept_findings.py`:
  - [ ] Listed category: gating; unlisted category: not gating; a category mapped to `other` (an invented string): not gating
  - [ ] No category: gating; NOTE and PASS in unlisted categories: gating, order preserved
  - [ ] `keep=None`: all gating

### Task 8: `reviewer_call_options` (D2, D3)
- [ ] New `recipes/reviewer_options.py` with `reviewer_call_options(call_options, options) -> dict`: returns a copy. For `options is None`, unchanged. Otherwise sets `no_tools` to `not options.tools`, and `rules_content` to the step's `call_options["rules_content"]` + `RULES_SEPARATOR` + `options.rules_content` when the step has rules, or `options.rules_content` alone when it has none; when the reviewer has no rules file, `rules_content` stays the step's
- [ ] Tests in `tests/recipes/test_reviewer_options.py`, each run against both entry points' options dict shapes (the CLI's, which carries `no_tools`, and the action's, which does not; copy the shapes from `cli/commands/review_recipe.py` and `pipeline/actions/review_recipe.py`):
  - [ ] No options: returned dict equals the input, and the input is not mutated
  - [ ] `tools: false`: `no_tools is True`; `tools: true`: `no_tools is False`
  - [ ] Rules with step rules: step rules, then `RULES_SEPARATOR`, then the file; rules with no step rules: the file alone

**Commit**: `feat: add category split and per-reviewer call options for recipes`

### Task 9: Runner applies options and the filter (D2, D5, D6)
- [ ] `recipes/recipe_outcome.py`: `ReviewerOutcome.not_gating` (the findings the filter did not keep; empty by default)
- [ ] `recipes/recipe_runner.py`: each reviewer's call uses `reviewer_call_options(options, recipe.reviewer_options.get(alias))`; no `no_tools` or `rules_content` keyword is passed separately. After a reviewer returns, `split_by_category(findings, recipe.keep_categories)` sets the kept findings and `not_gating`. The finding-id map (`source` in `_run_chain`) still covers every finding returned
- [ ] Incomplete recipes follow 434 D5 with "kept" meaning gating (D6)
- [ ] Tests in `tests/recipes/test_recipe_runner.py` with the scripted review call:
  - [ ] The scripted call records its arguments: the `tools: false` reviewer got `no_tools=True` and the step rules + separator + file; the other reviewer got the step's options unchanged
  - [ ] Kept and `not_gating` partition the reviewer's CONCERN/FAIL findings per `keep_categories`
  - [ ] A line pass that raises: one WARNING logged naming the reviewer, its outcome is a harness failure, the recipe is incomplete
  - [ ] A recipe with no options and no filter behaves as before (existing tests pass unchanged)

**Commit**: `feat: run recipe reviewers with their own options and the category filter`

### Task 10: "Not gating" table and the Findings section (D6)
- [ ] `recipes/recipe_merge.py`: after the stage table in the Recipe section, a "Not gating" table when any reviewer has `not_gating` findings: one row per finding with reviewer, category, original severity, location (`_NO_VALUE` when missing) and title. `|` in a cell is written `\|`. `ReviewResult.findings` holds gating findings, then NOTE and PASS, as 434 orders them
- [ ] Correct the `recipe_merge.py` docstring: the reviser's feedback is built from the review action's findings, not read from the review file
- [ ] `review/models.py`: `RecipeReviewInfo.not_gating: int = 0`. `recipe_merge` sets it
- [ ] `review/persistence.py`: when `recipe.not_gating > 0` and the findings list is empty, write the `## Findings` heading followed by "No gating findings; N not gating (see the Recipe section)." instead of "No specific findings."
- [ ] Tests in `tests/recipes/test_recipe_merge.py` and the persistence tests:
  - [ ] A listed-category CONCERN is in `findings` and sets the verdict; an unlisted one (including `other`) is absent from `findings` and present in the table; a no-category one is in `findings`; NOTE and PASS merge as before
  - [ ] A review whose only CONCERN findings are not gating has verdict PASS
  - [ ] D6 parser test: save a review with no gating finding and one not-gating finding whose title holds `|` and `- [CONCERN] ` and has no location; parse the saved file; assert the table row is one row, no finding is parsed, and the "No gating findings; 1 not gating" line is present
  - [ ] A recipe review with no not-gating findings renders as before (existing tests pass)

**Commit**: `feat: show not-gating findings in a table in the recipe review section`

### Task 11: `keep_categories` on the record (D6)
- [ ] `metrology/recipe_review_models.py`: `RecipeReview.keep_categories: tuple[ReviewCategory, ...] | None = None`; `schema_version` stays 1
- [ ] `recipes/recipe_record.py` writes the recipe's `keep_categories` to the record
- [ ] Tests:
  - [ ] A record built from a recipe with a filter carries its list; one without carries `None`
  - [ ] A stored record JSON with no `keep_categories` field loads
  - [ ] `split_by_category` over the record's review stages and `keep_categories` reproduces the gating set the runner produced for the same scripted outputs

### Task 12: Refusals with no diff (D7)
- [ ] `recipes/model_ref.py` `validate_recipe_review` refuses, naming the recipe and the template, before any model call: `keep_categories` on a review with no diff input; a `tools: false` reviewer on a review with no diff input. Follow the existing combs refusal's shape
- [ ] Tests in `tests/recipes/test_model_ref.py`:
  - [ ] Each refusal on `slice`, `tasks` and a `code` review with `files` and no diff; the message names the recipe and template
  - [ ] A `code` review with a diff passes
  - [ ] The pre-run check passes a `code` step with `files` and no diff (it is refused when the step runs, D7)

**Commit**: `feat: record the category filter and refuse it on reviews without a diff`

### Task 13: Benchmark `run` refuses reviewers with options (D8)
- [ ] `benchmark/recall/run_plan.py` `expand_pending` raises the run's existing refusal error for a recipe where any reviewer has options, naming the recipe, the reviewer and #393, before the bound is printed
- [ ] Test in `tests/cli/test_benchmark_recall_run.py`: `sq benchmark recall run` with such a recipe exits non-zero, the output names #393, no bound line is printed and the scripted stage call is never invoked

### Task 14: Report: reviewers with options match no stored entry (D8)
- [ ] `benchmark/recall/scoring.py`: a reviewer that has options matches no stored stage entry, live or imported. The row lists every case run as left out, as for a reviewer with no stored output
- [ ] Test in `tests/benchmark/recall/`: store a tool-enabled `haiku` entry and an imported `haiku` entry; score a recipe whose `haiku` reviewer has `tools: false` and a rules file; assert neither entry serves it and every case is listed as left out

**Commit**: `feat: refuse and skip recipe reviewers with options in the recall benchmark`

### Task 15: Report: filter scoring and columns (D8)
- [ ] `scoring.py` `reviewer_output` applies `split_by_category` with the recipe's `keep_categories` to the reviewer's CONCERN and FAIL findings (pass the categories in; `reviewer_output` takes no recipe today)
- [ ] Report modules (`report_build.py`, `report_render.py`, `report_json.py`): for a recipe with a filter, per row: findings per run before and after the filter, and known-bug recall before and after; the JSON report marks each finding gating or not gating. A recipe with no filter prints as today. Update the JSON schema test if the schema is pinned (`test_report_json_schema.py`)
- [ ] `label_candidates.py`: candidates include not-gating findings
- [ ] Tests:
  - [ ] A recipe with `keep_categories` over stored reviewer outputs (no options) prints before/after counts and recall, with no model call
  - [ ] JSON report carries the per-finding mark; a recipe with no filter renders identically to before (existing render tests pass)
  - [ ] Label candidates include a not-gating finding

### Task 16: Real-work table "Not gating/review" (D8)
- [ ] `benchmark/recall/real_work.py` `_reviewer_counts` applies `split_by_category` with the record's `keep_categories`. "Raw findings/review" stays every CONCERN and FAIL finding; new "Not gating/review" column; "Kept/review" counts only gating findings. A record with no `keep_categories` counts as today
- [ ] Test in `tests/benchmark/recall/test_real_work.py`: a record with not-gating findings counts them in "Not gating/review" and not in "Kept/review"; a record without the field gives today's row

**Commit**: `feat: score the category filter in recall reports and the real-work table`

### Task 17: Shipped recipe and rules file (D9)
- [ ] Add `data/recipes/haiku-line-pass.yaml` exactly as in D9
- [ ] Copy `MARTIAN/rules-line-pass.md` byte for byte to `data/recipes/line-pass.rules.md`
- [ ] Confirm `haiku-line-pass` is not an alias in `data/models.toml`
- [ ] Pinned tests updated in this commit:
  - [ ] `tests/benchmark/recall/test_recipe.py`: `SHIPPED` gains `haiku-line-pass`; rename `test_shipped_recipes_are_the_two_with_no_opus_high_comb` to drop "the two"
  - [ ] `tests/pipeline/test_classification.py` `test_recipe_no_longer_shipped_is_refused_at_the_pre_run_check`: the pinned "Known recipes:" string gains `haiku-line-pass` in its sorted place
- [ ] New tests:
  - [ ] The shipped rules file's bytes equal `MARTIAN/rules-line-pass.md`
  - [ ] The recipe loads from the installed package data directory (`importlib.resources`), with `rules_content` set, `haiku` options `tools: false`, and the five categories
- [ ] One-time check, not a unit test: `uv build --wheel --out-dir <temp dir>` and `unzip -l` on the wheel lists `squadron/data/recipes/line-pass.rules.md`. Record the result as a note under this item
- [ ] Task 2's pins still pass (the new recipe is not pinned; existing ones are unchanged)

**Commit**: `feat: ship the haiku-line-pass recipe and line-pass rules file`

### Task 18: D11 hand-run fixture
- [ ] Choose five PRs from `MARTIAN/out/` (`<case>-haiku-xhigh-1.json`, `<case>-haiku-line-1.json`) so that both reviewers have gating and not-gating CONCERN/FAIL findings and at least one PR has a finding whose category is `other`. Every CONCERN/FAIL finding in the five has a category (no-category findings would make `convert.py`'s rule and production differ)
- [ ] Write `tests/recipes/fixtures/hand_run/`: per PR and reviewer, a JSON with only `verdict` and `findings` (no other key, so no sandbox path is committed)
- [ ] Write the expected file once with a short throwaway script applying `MARTIAN/convert.py`'s rule (severity CONCERN or FAIL, category in the five), per PR and reviewer, the titles in order. Do not use the code under test. Do not commit the script
- [ ] `grep` the fixture directory for `/Users/`, `/tmp/` and `sandbox`: no hits

### Task 19: D11 test
- [ ] `tests/recipes/test_hand_run_entry.py`: a test helper builds a `ReviewResult` per fixture file, one `ReviewFinding` per entry from `severity`, `title`, `description`, `location`, `category`. Run the recipe runner and merge with the shipped `haiku-line-pass` recipe and a scripted review call returning those results per reviewer
  - [ ] Assert the gating CONCERN/FAIL findings' titles per PR and reviewer equal the expected file, in order
  - [ ] Assert every category in the fixtures is a `ReviewCategory` value
- [ ] `uv run pytest tests/recipes/test_hand_run_entry.py -q` passes

**Commit**: `test: reproduce the hand-run line-pass entry from stored outputs`

### Task 20: Pipeline defaults (D10)
- [ ] `review-model: haiku-line-pass` in `data/pipelines/P6.yaml`, `implement.yaml`, `implement-plan.yaml`; `model: haiku-line-pass` in `review.yaml`. Confirm in each that the parameter feeds only `template: code` reviews
- [ ] The comment above `review-model` in `P6.yaml`: what the recipe is, that `review-model: haiku-xhigh` gives the old gate, and a pointer to `MARTIAN/RESULTS.md`; no numbers
- [ ] `P56.yaml` and `P456.yaml` unchanged; the `code` template's `model` unchanged
- [ ] Pinned tests updated:
  - [ ] `tests/pipeline/test_builtin_pipelines.py` `test_implement_plan_params_and_shape`: `review-model` is `haiku-line-pass`
  - [ ] `tests/review/test_review_template_defaults.py`: the `code` row is split out of `test_standalone_review_default_matches_the_pipeline` into its own test asserting `haiku-xhigh`, with a comment giving the template-hash reason; `slice` and `tasks` still match their pipelines
  - [ ] `tests/pipeline/test_loader.py`: correct the docstring that says the standalone code review runs P6's reviewer
- [ ] New test: the pipeline pre-run check passes for each of the four pipelines with `review-model` (or `model`) resolved to `haiku-line-pass` as a recipe

**Commit**: `feat: make haiku-line-pass the code review default of four pipelines`

### Task 21: End-to-end recipe review with both reviewers
- [ ] One end-to-end test in the review CLI tests: a temp git repo, `sq review code --diff HEAD~1 --model haiku-line-pass` with scripted outputs for `haiku-xhigh` (one gating CONCERN, one not-gating) and `haiku` (one gating, one in `other`):
  - [ ] One review file with the Recipe section, the stage table with two review rows, and the "Not gating" table with two rows; one `recipe_review` record with `keep_categories`
  - [ ] The scripted `haiku` call received `no_tools=True`
  - [ ] Review ingest of the saved file records no not-gating finding
- [ ] Reviser test (review action / revise loop tests): the reviser's feedback for the same scripted recipe review holds no not-gating finding title
- [ ] Failed line pass, one test each:
  - [ ] With a gating finding from `haiku-xhigh`: WARNING logged, `harness_failure` in the stage table and the record, `recipeComplete: false`, verdict FAIL
  - [ ] With only not-gating findings from `haiku-xhigh`: verdict UNKNOWN and the review fails
- [ ] `haiku-line-pass` on `sq review slice` and `sq review tasks` exits 1 naming the recipe and template; the scripted call is never invoked
- [ ] The existing `haiku-solr-luna` and `haiku-sol-luna` tests pass unchanged

**Commit**: `test: add end-to-end line-pass recipe review tests`

### Task 22: Docs and CHANGELOG
- [ ] `docs/PIPELINES.md` (Recipe reviews): `reviewer_options`, `keep_categories`, the "Not gating" table, the new default of the four pipelines, and that `sq review code` with no `--model`, `P56` and `P456` still run `haiku-xhigh`. Correct the P6 parameter table row for `review-model` and the sentence saying `review-model` "defaults to `haiku-xhigh`, matching `P6`"
- [ ] `README.md` names the new default code gate
- [ ] `CHANGELOG.md` `[Unreleased]`: one short user-facing bullet (detail belongs in DEVLOG)
  - [ ] `grep -n "haiku-xhigh" docs/PIPELINES.md README.md`: every remaining hit is correct after this slice

**Commit**: `docs: document reviewer options, the category filter and the new code gate`

### Task 23: Verification walkthrough (live)
- [ ] Run design walkthrough steps 1–3 (no model call) and record the actual output under each step in the slice design
- [ ] Build the step 4 fixture repo in a temp directory (last commit turns `total -= amount` into `total += amount` and adds an undocumented public function); run step 4 and record the output: findings from both reviewers, two review rows, the `haiku` row with no tool calls, exit 2
- [ ] Register the fixture with cf as in 434's walkthrough step 5; run step 5 and record: `aiModel: haiku-line-pass`, `aiRecipe: true`, reviser round addresses only gating findings
- [ ] Run step 6 and record: one `haiku-line-pass` row; per review, "Kept/review" plus "Not gating/review" accounts for its table rows and CONCERN/FAIL findings
- [ ] Remove "Draft; refined after implementation" from the walkthrough heading text; step 7 stays as the PM's
- If a live step fails, get the actual error output before any change, fix under the task that owns the code, and re-run the step. If it cannot proceed, write a `BLOCKED:` line here with the reason and stop.

### Task 24: Final validation and completion
- [ ] `ruff format`, `ruff check`, `pyright` (zero errors) pass
- [ ] `uv run pytest -q` passes; Task 2's pin test is unmodified since its commit (`git diff <Task 2 commit> -- tests/recipes/test_identity_pins.py` is empty)
- [ ] `grep -rn "keep_categories" src/squadron` shows category comparison only inside `split_by_category`
- [ ] Every Success Criteria item of the design was checked by the task that built it (Tasks 2–23 checked off)
- [ ] Set the task file and slice design `status: complete`; check off entry 18 (437) in `user/architecture/420-slices.model-benchmark.md`; DEVLOG entry

**Commit**: `docs: record the slice 437 verification walkthrough and complete the slice`
