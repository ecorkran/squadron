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
turns: 66
promptTokens: 5483932
cachedTokens: 5254151
cacheWriteTokens: 229673
completionTokens: 72288
durationSeconds: 663.1
costUsd: 4.334911
usageRounds: 4
pricedRounds: 4
usageByModel:
  claude-opus-5-5:
    rounds: 4
    costUsd: 4.3349104
    completionTokens: 72288
revision_number: 3
---

## Context Summary
- Working on slice 437: the code review gate of `P6`, `implement`, `implement-plan` and the `review` pipeline becomes the recipe `haiku-line-pass`: `haiku-xhigh` with tools plus a no-tools `haiku` line pass with its own rules file, merged into one review, with a category filter deciding which CONCERN and FAIL findings set the verdict. Design: `user/slices/437-slice.line-pass-pair-as-the-code-gate.md`. Its D-numbers (D1–D11) are cited below instead of repeating them; read the cited decision before each task.
- Paths: source modules are relative to `src/squadron/`, tests to the repo root, `user/...` documents to `project-documents/`. The measured run lives in `user/reference/review-recall-results/20261122-martian/` (below: `MARTIAN/`).
- Delivers: `reviewer_options` (`tools`, `rules`) and `keep_categories` on recipes; both options in the stage identity; `split_by_category`; the "Not gating" table and the `keep_categories` record field; the benchmark's filter scoring, report columns and real-work column; the refusals for #393; the shipped recipe and rules file; the four pipeline defaults; docs.
- Excluded (design Technical Scope): cross-reviewer dedupe (435), reviewers that read earlier findings (436), duplicate aliases in one recipe, `keep_categories` with `combs` (#392, refused), benchmark run/scoring of reviewers with options (#393, refused/left out), `P56` and `P456` (#390), the `code` template's own `model`, a stage time bound, the full 50-PR benchmark run (the PM's, after the slice).
- Identity safety (D1, D4): a recipe with neither new key keeps its `recipe_hash` and every stage `config_key`. Task 2 pins today's values before any model change; that test must pass unchanged at the end.
- Parser safety (D6): "Not gating" table cells escape every `|`, `[` and `#` with a backslash, so no cell holds finding-shaped text for the parser's whole-file scan. D6 states the rule and the reason.
- Large files: `recipes/recipe_runner.py` (322 lines) gains only call sites; per-reviewer call options go in new `recipes/reviewer_options.py`. `review/persistence.py` gains only the Findings branch of Task 11.
- Shared names, defined once and never compared as literals: `ReviewCategory` values (`core/finding_categories.py`); `RULES_SEPARATOR` (`project_rules/render.py`); the rules hash as one helper (`rules_sha256`, Task 4) used by `recipe_hash` and `stage_config`. Each task that writes a message or heading names its constant.
- `split_by_category` is the only place a finding's category is compared with the kept list (runner, scoring, real-work all call it).
- Failure modes asserted where they are built: bad keys in Task 3; rules-file read failures in Task 4; a failed line pass in Task 9 (outcome, WARNING) and Task 22 (stage table, record, verdict, saved Findings section); refusals in Tasks 12 and 13.
- Tests run no model: the review call is scripted as in 434's tests (`tests/recipes/support.py`, `tests/recipes/conftest.py`). Alias resolution is isolated by monkeypatching `aliases.load_user_aliases`, as `tests/recipes/test_stage_config.py` does. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), the touched area's tests. Nothing here pushes or merges.
- Effort 3/5. Next open entries in the 420 plan: 431, 432, 435, 436 (435 and 436 build on this slice's reviewer options).

## Tasks

### Task 1: Create the slice branch
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file, commit it by path as `docs: revise slice 437 tasks`; then `git status --short` is clean
- [ ] Create `437-slice.line-pass-pair-as-the-code-gate` from the target and switch to it
  - [ ] `git branch --show-current` prints the slice branch name

### Task 2: Pin today's recipe identities (test infrastructure)
- [ ] Add `tests/recipes/test_identity_pins.py`. With `aliases.load_user_aliases` monkeypatched to return `{}` (built-in aliases only) and one fixed review template hash constant, for these 13 files, named explicitly in the test (no directory glob, so Task 17's new recipe never enters it):
  - shipped (`shipped_recipes_dir()`): `haiku-sol-luna`, `haiku-solr-luna`
  - `user/reference/review-recall-recipes/`: `haiku-mimo-opus`, `haiku-opus`, `haiku-sol-luna-opus`, `haiku-sol-opus`, `haiku-sol-pool`, `haiku-solr-luna-opus`, `haiku-xhigh`, `luna`, `sol`, `sonnet-high`, `sonnet`
  - [ ] Assert `recipe_hash(load_recipe(path))` equals a value recorded in the test now, on the unchanged code
  - [ ] Assert the `config_key` of each `planned_stages(recipe, <fixed hash>)` entry equals a value recorded now
  - [ ] The recorded values are literal strings in the test (generated once by running the current code, then pasted); the test passes on the unchanged code
- [ ] Note in the test module docstring: values recorded before slice 437; they must never be regenerated by this slice (D1, D4)

**Commit**: `test: pin recipe hashes and stage keys before slice 437`

### Task 3: Recipe model: `reviewer_options` and `keep_categories` (D1, D5)
- [ ] In `recipes/recipe.py` add `ReviewerOptions` (pydantic, unknown keys forbidden): `tools: bool = True`, `rules: str | None = None` (the file name as written), and loader-set `rules_path: Path | None = None` and `rules_content: str | None = None`. A `model_validator(mode="before")` refuses `rules_path` and `rules_content` in the input; `load_recipe` (Task 4) sets them with `model_copy(update=...)`, which runs no validator
- [ ] Add `Recipe.reviewer_options: Mapping[str, ReviewerOptions]` (alias to options, empty by default) and `Recipe.keep_categories: tuple[ReviewCategory, ...] | None = None`. `Recipe.reviewers` stays a tuple of alias strings; existing `Recipe(reviewers=(...))` constructions still type-check
- [ ] In the same change, `recipes/recipe_record.py` `recipe_hash` stops dumping `recipe.model_dump(mode="json")`, which would put the two new fields into every recipe's hash. It builds the canonical dict explicitly from `name`, `reviewers`, `pool` and `combs`, with the values `model_dump(mode="json")` gives them today. Task 5 adds the new keys to it. Without this, Task 2's pins fail as soon as the fields exist
- [ ] Validation, each failure a `RecipeError` from `load_recipe` naming the recipe path and the problem:
  - [ ] a `reviewer_options` key not in `reviewers`
  - [ ] an unknown option key inside an entry
  - [ ] `rules_path` or `rules_content` written in the recipe file
  - [ ] a `keep_categories` value that is not a `ReviewCategory` value: `field_validator("keep_categories", mode="before")` checks each raw value and raises `ValueError` naming the bad value and the valid values (the enum's own error runs first otherwise and does not carry the input; `load_recipe` builds the message from `error["msg"]`)
  - [ ] an empty `keep_categories` list
  - [ ] `keep_categories` together with `combs`; the message names #392 from one module constant
- [ ] Tests in `tests/recipes/test_recipe_options.py`, writing recipe files to `tmp_path`:
  - [ ] A recipe with neither new key loads with empty `reviewer_options` and `keep_categories is None`
  - [ ] A recipe with `reviewer_options` (no `rules`) and `keep_categories` loads with the given values
  - [ ] One test per refusal above, each asserting `RecipeError`; the category test asserts the bad value and one valid value appear in the message
- [ ] `uv run pytest tests/recipes tests/benchmark/recall/test_recipe.py -q` passes, Task 2's pins included

### Task 4: Rules file read and the rules hash helper (D3)
- [ ] `load_recipe` resolves each `rules` in the recipe file's own directory, reads it as UTF-8, and sets `rules_path` (absolute) and `rules_content`. Each failure a `RecipeError` naming the recipe path and the rules file name:
  - [ ] a `rules` value with a directory part, an absolute path or `..`
  - [ ] a missing file
  - [ ] `OSError` on read
  - [ ] `UnicodeDecodeError`
  - [ ] an empty file
- [ ] The recipe file's own read: catch `UnicodeDecodeError` beside the existing `OSError` and `yaml.YAMLError`, raising `RecipeError`
- [ ] Add `rules_sha256(options: ReviewerOptions) -> str | None` in `recipes/recipe.py`: sha256 of `rules_content`, `None` with no rules. Tasks 5 and 6 use it; no other place hashes rules content
- [ ] Keep `recipe.py` near the ~300-line guideline; if it goes over, move option parsing to a helper module inside `recipes/`
- [ ] Tests in `tests/recipes/test_recipe_options.py`:
  - [ ] A recipe with `rules` loads; `rules_path` is absolute and in the recipe's directory; `rules_content` equals the file
  - [ ] One test per refusal above (non-UTF-8 uses bytes such as `b"\xff\xfe"`; `OSError` by a monkeypatched read), each asserting `RecipeError` naming the rules file
  - [ ] A recipe file that is not UTF-8 raises `RecipeError`, not `UnicodeDecodeError`
  - [ ] `rules_sha256` gives two values for two contents and `None` with no rules

### Task 5: `recipe_hash` canonical form (D1)
- [ ] In `recipes/recipe_record.py`, extend the explicit canonical dict of `recipe_hash` (four keys since Task 3): add `reviewer_options` only when non-empty (per alias: `tools`, `rules`, `rules_sha256(options)`) and `keep_categories` only when set. `rules_path` and `rules_content` are never in it
- [ ] Tests in `tests/recipes/test_recipe_options.py`:
  - [ ] Task 2's pins pass unchanged
  - [ ] Changing the rules file content changes `recipe_hash`; changing `tools` changes it; adding `keep_categories` changes it
  - [ ] Moving the recipe and its rules file to another directory does not change `recipe_hash` (path not in the dump)

**Commit**: `feat: add reviewer options and category filter to recipe files`

### Task 6: Stage identity (D4)
- [ ] `metrology/recall_run_models.py`: `StageConfig.rules_hash: str | None = None`; `config_key` includes it only when set
- [ ] `recipes/stage_config.py`: `stage_config` and `alias_stage_config` take `options: ReviewerOptions | None = None`. With options: `tool_use` is `False` when `tools` is false (whatever the alias allows), and `rules_hash` is `rules_sha256(options)`. With `None`: today's config
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
- [ ] `review/rules.py`: replace the literal `"\n\n---\n\n"` in the template-rules join with `RULES_SEPARATOR` (same value)
- [ ] Tests in `tests/recipes/test_reviewer_options.py`, each run against both entry points' options dict shapes (the CLI's, which carries `no_tools`, and the action's, which does not; copy the shapes from `cli/commands/review_recipe.py` and `pipeline/actions/review_recipe.py`):
  - [ ] No options: returned dict equals the input, and the input is not mutated
  - [ ] `tools: false`: `no_tools is True`; `tools: true`: `no_tools is False`
  - [ ] Rules with step rules: step rules, then `RULES_SEPARATOR`, then the file; rules with no step rules: the file alone

**Commit**: `feat: add category split and per-reviewer call options for recipes`

### Task 9: Runner applies options and the filter (D2, D5, D6)
- [ ] `recipes/recipe_outcome.py`: `ReviewerOutcome.not_gating` (the findings the filter did not keep; empty by default)
- [ ] `recipes/recipe_runner.py`: each reviewer's call uses `reviewer_call_options(options, recipe.reviewer_options.get(alias))`; no `no_tools` or `rules_content` keyword is passed separately
- [ ] In `_run_chain`, split first: `split_by_category(split.scored, recipe.keep_categories)`. The gating findings replace `split.scored` as the chain input and in `chain_result`, so `kept` holds only gating findings; the not-gating findings go to `ReviewerOutcome.not_gating`. The finding-id map (`source`) still covers every finding returned. `recipe_runner.py` gains only that call and the `not_gating=` argument; any further logic goes in `kept_findings.py`
- [ ] Incomplete recipes follow 434 D5 with "kept" meaning gating (D6)
- [ ] `tests/recipes/support.py`: `CallRecord` gains `no_tools: bool | None = None` and `rules_content: str | None = None` (last, with defaults); `ScriptedReviewCall.__call__` records both from its keyword arguments
- [ ] Tests in `tests/recipes/test_recipe_runner.py` with the scripted review call:
  - [ ] The recorded calls show: the `tools: false` reviewer got `no_tools=True` and the step rules + separator + file; the other reviewer got the step's `no_tools` and `rules_content` unchanged
  - [ ] Kept and `not_gating` partition the reviewer's CONCERN/FAIL findings per `keep_categories`
  - [ ] A line pass that raises `ProviderError`: one WARNING logged naming the reviewer, its outcome is a harness failure, the recipe is incomplete
  - [ ] A recipe with no options and no filter behaves as before (existing tests pass unchanged)

**Commit**: `feat: run recipe reviewers with their own options and the category filter`

### Task 10: "Not gating" table (D6)
- [ ] `recipes/recipe_merge.py`: after the stage table in the Recipe section, a "Not gating" table when any reviewer has `not_gating` findings, under a heading held in one module constant: one row per finding with reviewer, category, original severity, location (`_NO_VALUE` when missing) and title. Every `|`, `[` and `#` in a cell is escaped with a backslash (D6). `ReviewResult.findings` holds gating findings, then NOTE and PASS, as 434 orders them
- [ ] Correct the `recipe_merge.py` docstring: the reviser's feedback is built from the review action's findings, not read from the review file
- [ ] `review/models.py`: `RecipeReviewInfo.not_gating: int = 0`. `recipe_merge` sets it
- [ ] Tests in `tests/recipes/test_recipe_merge.py`:
  - [ ] A listed-category CONCERN is in `findings` and sets the verdict; an unlisted one (including `other`) is absent from `findings` and present in the table; a no-category one is in `findings`; NOTE and PASS merge as before
  - [ ] A review whose only CONCERN findings are not gating has verdict PASS; `recipe.not_gating` equals the table's row count
  - [ ] A title holding `|`, `- [CONCERN] ` and `### FAIL x` renders as one row with every `|`, `[` and `#` escaped
  - [ ] A recipe review with no not-gating findings renders as before (existing tests pass)

### Task 11: Findings section of a review with no gating finding (D6)
- [ ] `review/persistence.py`: a new branch in the body, directly after the body's `if result.findings:` block (the one that writes `## Findings`, not the frontmatter one) and before `elif result.fallback_used`: when `recipe is not None and recipe.not_gating > 0`, write `## Findings`, a blank line, and "No gating findings; N not gating (see the Recipe section).", its text held in one module constant. The branch only extends the body with the lines of a new helper `_not_gating_findings_section(count)` beside `_findings_not_parsed_section`. So an incomplete recipe with only not-gating findings (verdict UNKNOWN) gets this line, not "Findings Not Parsed"
- [ ] Tests in `tests/review/test_persistence.py`:
  - [ ] D6 parser test: save a recipe review with no gating finding and one not-gating finding whose title holds `|` and `- [CONCERN] ` and has no location; parse the saved file; assert the table row is one row, no finding is parsed, and the "No gating findings; 1 not gating" line is under `## Findings`
  - [ ] The same review with verdict UNKNOWN: the saved file has the "No gating findings" line and no "Findings Not Parsed" heading
  - [ ] A non-recipe review with no findings still gets "No specific findings." (existing tests pass)

**Commit**: `feat: show not-gating findings in a table in the recipe review section`

### Task 12: `keep_categories` on the record, and refusals with no diff (D6, D7)
- [ ] `metrology/recipe_review_models.py`: `RecipeReview.keep_categories: tuple[ReviewCategory, ...] | None = None`; `schema_version` stays 1. `recipes/recipe_record.py` writes the recipe's `keep_categories` to the record
- [ ] `recipes/model_ref.py` `validate_recipe_review` refuses, naming the recipe and the template, before any model call: `keep_categories` on a review with no diff input; a `tools: false` reviewer on a review with no diff input. Follow the existing combs refusal's shape; each message's text from one module constant
- [ ] Tests:
  - [ ] `tests/metrology/test_recipe_review_models.py`: a stored record JSON with no `keep_categories` field loads with `None`
  - [ ] `tests/recipes/test_recipe_review.py`: a record built from a recipe with a filter carries its list, one without carries `None`. `split_by_category` over the record's review stages whose outcome is OK, with `keep_categories`, reproduces the runner's gating set for the same scripted outputs, including a reviewer whose UNKNOWN-verdict stage carries findings the runner did not use
  - [ ] `tests/recipes/test_model_ref.py`: each refusal on `slice`, `tasks`, `arch` and a `code` review with `files` and no diff, the message naming the recipe and template; a `code` review with a diff passes
  - [ ] `tests/pipeline/test_classification.py`, beside `test_review_model_recipe_passes_the_pre_run_check`: the pre-run check passes a `code` step with `files` and no diff and a recipe with `keep_categories` (it is refused when the step runs, D7)

**Commit**: `feat: record the category filter and refuse it on reviews without a diff`

### Task 13: Benchmark: refuse and skip reviewers with options (D8)
- [ ] `benchmark/recall/run_plan.py` `expand_pending` raises `RecallRefusal` (`benchmark/recall/refusal.py`) for a recipe where any reviewer has options, naming the recipe, the reviewer and #393 (the message text from one module constant). `expand_pending` runs before the bound is built, so nothing is printed first
- [ ] `benchmark/recall/scoring.py` `_pair_variants`: a reviewer with an entry in `recipe.reviewer_options` has no choices, so the function returns `{}` as for a reviewer with no stored output; a comment names #393. `entry_matches` and the resolver are unchanged (a live `haiku` entry would otherwise match, since `live_stage_config` passes no options; an imported one matches by alias)
- [ ] Tests:
  - [ ] `tests/cli/test_benchmark_recall_run.py`: `sq benchmark recall run` with such a recipe exits non-zero, the output names #393, no bound line is printed and the scripted stage call is never invoked
  - [ ] `tests/benchmark/recall/test_scoring_outputs.py`: store a tool-enabled live `haiku` entry and an imported `haiku` entry; score a recipe whose `haiku` reviewer has `tools: false` and a rules file; assert neither entry serves it and every case run is listed as left out

**Commit**: `feat: refuse and skip recipe reviewers with options in the recall benchmark`

### Task 14: Scoring the filter (D8)
- [ ] `scoring.py`: `ReviewerOutput.not_gating: tuple[RecallFinding, ...] = ()`. `reviewer_output` gains a keyword `keep: tuple[ReviewCategory, ...] | None = None`, applies `split_by_category` to the reviewer's CONCERN and FAIL findings, and sets `not_gating`. `_pair_variants` passes `recipe.keep_categories`; `stage_runner.comb_input_findings` passes none (combs and a filter never meet, #392)
- [ ] Before-filter numbers come from an unfiltered pass: `recipe_outputs(recipe.model_copy(update={"keep_categories": None}), ...)` for a recipe with a filter
- [ ] `label_candidates.py`: for a recipe with a filter, candidates come from the unfiltered pass's `reviewer.upper`, so not-gating findings are candidates
- [ ] Tests:
  - [ ] `tests/benchmark/recall/test_scoring_outputs.py`: a recipe with `keep_categories` over stored reviewer outputs (no options): the filtered pass's `upper` holds only gating findings and `not_gating` the rest; the unfiltered pass holds both; no model call
  - [ ] New `tests/benchmark/recall/test_label_candidates.py`: candidates for a filtered recipe include a not-gating finding

### Task 15: Report columns (D8)
- [ ] JSON report (`report_json.py` `RowJson`) gains three fields, `None` for a recipe with no filter: `findings_per_run_unfiltered: float | None` and `recall_unfiltered: BoundsJson | None` from the unfiltered pass, and `not_gating: list[str] | None`, one `<case>/<run>/<reviewer>/<finding_id>` per finding in `ReviewerOutput.not_gating` (the per-finding mark: a scored finding not listed is gating)
- [ ] `report_build.py` fills them; `report_render.py` prints findings per run and recall before and after the filter for a recipe with a filter, and prints as today for one without
- [ ] Tests:
  - [ ] `tests/benchmark/recall/test_report_json_schema.py`: add the three keys to `EXPECTED_ROW`; the test passes
  - [ ] `tests/benchmark/recall/test_report_render.py`: a filtered recipe's row has before/after values and its JSON `not_gating` lists the not-gating finding; an unfiltered recipe renders as before (existing tests pass)

### Task 16: Real-work table "Not gating/review" (D8)
- [ ] `benchmark/recall/real_work.py`: `chain_counts(record)` passes `record.keep_categories` to `_reviewer_counts`, which applies `split_by_category`. "Raw findings/review" stays every CONCERN and FAIL finding; "Kept/review" counts only gating findings; `_row_cells` adds a "Not gating/review" column, shown in every real-work table. A record with no `keep_categories` counts as before, with 0 not gating
- [ ] Tests in `tests/benchmark/recall/test_real_work.py`: a record with not-gating findings counts them in "Not gating/review" and not in "Kept/review"; a record without the field keeps its other counts and shows 0; existing render assertions updated for the new column

**Commit**: `feat: score the category filter in recall reports and the real-work table`

### Task 17: Shipped recipe and rules file (D9)
- [ ] Add `data/recipes/haiku-line-pass.yaml` exactly as in D9
- [ ] Copy `MARTIAN/rules-line-pass.md` byte for byte to `data/recipes/line-pass.rules.md`
- [ ] Confirm `haiku-line-pass` is not an alias in `data/models.toml`
- [ ] Pinned tests updated in this commit:
  - [ ] `tests/benchmark/recall/test_recipe.py`: `SHIPPED` gains `haiku-line-pass`; rename `test_shipped_recipes_are_the_two_with_no_opus_high_comb` to drop "the two"
  - [ ] `tests/pipeline/test_classification.py` `test_recipe_no_longer_shipped_is_refused_at_the_pre_run_check`: the pinned "Known recipes:" string gains `haiku-line-pass` in its sorted place
- [ ] New tests in `tests/benchmark/recall/test_recipe.py`:
  - [ ] The shipped rules file's bytes equal `MARTIAN/rules-line-pass.md`
  - [ ] The recipe loads from the shipped data directory (`shipped_recipes_dir()`), with `rules_content` set, `haiku` options `tools: false`, and the five categories
- [ ] One-time check, not a unit test (a checkout's pytest run reads `src/squadron/data`, so only this checks packaging): `uv build --wheel --out-dir <temp dir>` and `unzip -l` on the wheel lists `squadron/data/recipes/line-pass.rules.md`. Record the result as a note under this item. This one-time check is the chosen mitigation: Hatch packages all of `src/squadron`, and no test builds the wheel
- [ ] Task 2's pins pass unchanged

**Commit**: `feat: ship the haiku-line-pass recipe and line-pass rules file`

### Task 18: D11 hand-run fixture
- [ ] Choose five PRs from `MARTIAN/out/` (`<case>-haiku-xhigh-1.json`, and `<case>-haiku-line-1.json` for the `haiku` line pass) so that both reviewers have gating and not-gating CONCERN/FAIL findings and at least one PR has a finding whose category is `other`. No chosen output has verdict UNKNOWN (the runner uses no findings from such an output). Every CONCERN/FAIL finding in the five has a category, and every category in the five is a `ReviewCategory` value (Task 19 asserts it)
- [ ] Write `tests/recipes/fixtures/hand_run/<case>-<alias>.json` (alias `haiku-xhigh` or `haiku`): a JSON with only `verdict` and `findings` (no other key, so no sandbox path is committed)
- [ ] Write `tests/recipes/fixtures/hand_run/expected.json` once, with a short throwaway script applying `MARTIAN/convert.py`'s rule (severity CONCERN or FAIL, category in the five): `{"<case>": {"haiku-xhigh": [titles in order], "haiku": [titles in order]}}`. Do not use the code under test. Do not commit the script
- [ ] `grep` the fixture directory for `/Users/`, `/tmp/` and `sandbox`: no hits

### Task 19: D11 test
- [ ] `tests/recipes/test_hand_run_entry.py`: a test helper builds a `ReviewResult` per fixture file, one `ReviewFinding` per entry from `severity`, `title`, `description`, `location`, `category`. Run the recipe runner and merge with the shipped `haiku-line-pass` recipe and a scripted review call returning those results per reviewer
  - [ ] Assert the gating CONCERN/FAIL findings' titles per PR and reviewer equal `expected.json`, in order
  - [ ] Assert every category in the fixtures is a `ReviewCategory` value
- [ ] `uv run pytest tests/recipes/test_hand_run_entry.py -q` passes

**Commit**: `test: reproduce the hand-run line-pass entry from stored outputs`

### Task 20: Pipeline defaults (D10)
- [ ] `review-model: haiku-line-pass` in `data/pipelines/P6.yaml`, `implement.yaml`, `implement-plan.yaml`; `model: haiku-line-pass` in `review.yaml`. Confirm in each that the parameter feeds only `template: code` reviews
- [ ] Replace the whole existing comment block above `review-model` in `P6.yaml` (its figures and recipe list included) with one that says what the recipe is, that `review-model: haiku-xhigh` gives the old gate, and points to `MARTIAN/RESULTS.md`; no numbers
- [ ] `P56.yaml` and `P456.yaml` keep `review-model: haiku-xhigh`; only their comment `# review-model: see the note in P6.yaml.` changes, to say they keep `haiku-xhigh` because their `review-model` also reviews documents (#390). The `code` template's `model` unchanged
- [ ] Pinned tests updated:
  - [ ] `tests/pipeline/test_builtin_pipelines.py` `test_implement_plan_params_and_shape`: `review-model` is `haiku-line-pass`
  - [ ] `tests/review/test_review_template_defaults.py`: no assertion changes. The test reads the templates, not the pipelines, and the `code` template's model stays `haiku-xhigh`, so it passes as it is. Rename `test_standalone_review_default_matches_the_pipeline` to `test_review_template_default_model`, and reword the module docstring and the `PIPELINE_REVIEW_MODEL` comment, which say the templates agree with every pipeline's reviewer: the `code` template keeps `haiku-xhigh` (its model is part of the template hash) while four pipelines now review code with `haiku-line-pass`
  - [ ] `tests/pipeline/test_loader.py` `test_review_pipeline_defaults_to_the_p6_code_reviewer`: no change. It compares `review.yaml`'s `model` with P6's `review-model`; both become `haiku-line-pass`, so the assertion and its docstring stay true
  - [ ] New parametrized test in `tests/pipeline/test_builtin_pipelines.py` pinning each shipped pipeline's code reviewer: `review-model` is `haiku-line-pass` in `P6`, `implement` and `implement-plan`; `model` is `haiku-line-pass` in `review`; `review-model` is `haiku-xhigh` in `P56` and `P456` (#390)
- [ ] New test in `tests/pipeline/test_classification.py`, beside `test_review_model_recipe_passes_the_pre_run_check`: the pre-run check passes for each of the four pipelines with `review-model` (or `model`) resolved to `haiku-line-pass` as a recipe

**Commit**: `feat: make haiku-line-pass the code review default of four pipelines`

### Task 21: CLI recipe review with both reviewers
- [ ] In `tests/cli/test_review_recipe.py`: a temp git repo, `sq review code --diff HEAD~1 --model haiku-line-pass` with scripted outputs for `haiku-xhigh` (one gating CONCERN, one not-gating) and `haiku` (one gating, one in `other`):
  - [ ] One review file with the Recipe section, the stage table with two review rows, and the "Not gating" table with two rows; one `recipe_review` record with `keep_categories`
  - [ ] The scripted `haiku` call recorded `no_tools=True` and the step rules + `RULES_SEPARATOR` + `line-pass.rules.md`'s content
  - [ ] Review ingest of the saved file records no not-gating finding
- [ ] In the same file: `haiku-line-pass` on `sq review slice` and `sq review tasks` exits 1 naming the recipe and template; the scripted call is never invoked

### Task 22: Action path, reviser and a failed line pass
- [ ] In `tests/pipeline/actions/test_review_recipe.py`, the scripted outputs of Task 21 through `run_recipe_part`:
  - [ ] One review file with the Recipe section and "Not gating" table, and one `recipe_review` record (the same shape as the CLI)
  - [ ] The scripted `haiku` call recorded `no_tools=True` and the step rules + `RULES_SEPARATOR` + the rules file content
- [ ] In `tests/pipeline/actions/test_dispatch.py`: the reviser's findings block (`_findings_block`) for that review action's result holds no not-gating finding title
- [ ] Failed line pass, in `tests/pipeline/actions/test_review_recipe.py`, one test each:
  - [ ] The line pass raises `ProviderError` in both (other exceptions propagate, 434 D5)
  - [ ] With a gating finding from `haiku-xhigh`: WARNING logged, `harness_failure` in the stage table and the record, `recipeComplete: false`, verdict FAIL
  - [ ] With only not-gating findings from `haiku-xhigh`: verdict UNKNOWN, the review fails, and the saved file's `## Findings` section holds the "No gating findings; 1 not gating" line

**Commit**: `test: add end-to-end line-pass recipe review tests`

### Task 23: Docs and CHANGELOG
- [ ] `docs/PIPELINES.md` (Recipe reviews): `reviewer_options`, `keep_categories`, the "Not gating" table, the new default of the four pipelines, and that `sq review code` with no `--model`, `P56` and `P456` still run `haiku-xhigh`
- [ ] Same section, the shipped-recipes paragraph: add `haiku-line-pass` (needs neither `OPENROUTER_API_KEY` nor Codex credits; two reviewers, no comb), and correct "Each runs two reviewers and one `luna-r` comb" to cover it
- [ ] Same section, the refusal list: add `keep_categories` and a `tools: false` reviewer on a review with no diff
- [ ] `docs/PIPELINES.md` `implement-plan` section: the sentence "`review-model` defaults to `haiku-xhigh`, matching `P6`" says `haiku-line-pass`. The plan-batch parameter table's `review-model` row (`slices-plan`, `tasks-plan`) stays `haiku-xhigh` (design Technical Requirements)
- [ ] `README.md`: the recipe paragraph after the pipeline example (the one naming `haiku-sol-luna`) names `haiku-line-pass` as the new default code gate of the four pipelines
- [ ] `CHANGELOG.md` `[Unreleased]`: one short user-facing bullet (detail belongs in DEVLOG)
  - [ ] `grep -n "haiku-xhigh\|haiku-sol-luna\|luna-r\|refused before any model call" docs/PIPELINES.md README.md`: every hit is correct after this slice

**Commit**: `docs: document reviewer options, the category filter and the new code gate`

### Task 24: Verification walkthrough (live)
- [ ] Run design walkthrough steps 1–3 (no model call) and record the actual output under each step in the slice design
- [ ] Build the step 4 fixture repo in a temp directory (last commit turns `total -= amount` into `total += amount` and adds an undocumented public function) and run `sq config set metrology.project_id fixture-437 --project` in it, so records can be keyed (as in 434's walkthrough step 4); run step 4 and record the output: findings from both reviewers, two review rows, the `haiku` row with no tool calls, exit 2, and no `recipe record: not written` line
- [ ] Register the fixture with cf as in 434's walkthrough step 5; run step 5 and record: `aiModel: haiku-line-pass`, `aiRecipe: true`, reviser round addresses only gating findings
- [ ] Run step 6 and record: one `haiku-line-pass` row; per review, "Kept/review" plus "Not gating/review" accounts for its table rows and CONCERN/FAIL findings
- [ ] Delete the sentence "Draft; refined after implementation." from the first paragraph under the Verification Walkthrough heading; step 7 stays as the PM's
- If a live step fails, get the actual error output before any change, fix under the task that owns the code, and re-run the step. If it cannot proceed, write a `BLOCKED:` line here with the reason and stop.

### Task 25: Final validation and completion
- [ ] `ruff format`, `ruff check`, `pyright` (zero errors) pass
- [ ] `uv run pytest -q` passes; Task 2's pin test is unmodified since its commit (`git diff <Task 2 commit> -- tests/recipes/test_identity_pins.py` is empty)
- [ ] `grep -rnE "\bin +(keep|[A-Za-z_.]*keep_categories)\b" src/squadron` prints only the comparison inside `split_by_category`; and reading the call sites of Tasks 9, 14 and 16 shows each passes the kept list to `split_by_category` and compares no category itself
- [ ] Every Success Criteria item of the design was checked by the task that built it (Tasks 2–24 checked off)
- [ ] Set the task file and slice design `status: complete`; check off entry 18 (437) in `user/architecture/420-slices.model-benchmark.md`; DEVLOG entry

**Commit**: `docs: record the slice 437 verification walkthrough and complete the slice`
