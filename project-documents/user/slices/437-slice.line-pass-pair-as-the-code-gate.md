---
docType: slice-design
slice: line-pass-pair-as-the-code-gate
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies:
- 430
- 434
interfaces:
- 436
dateCreated: 20261123
dateUpdated: 20261123
status: complete
turns: 57
promptTokens: 5771284
cachedTokens: 5535996
cacheWriteTokens: 235216
completionTokens: 71266
durationSeconds: 707.3
costUsd: 7.722225
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-fable-5-2:
    rounds: 3
    costUsd: 7.7222242
    completionTokens: 71266
revision_number: 2
---

# Slice Design: line-pass-pair-as-the-code-gate

## Overview

The code review gate of four shipped pipelines becomes one recipe, `haiku-line-pass`, with two reviewers:

- `haiku-xhigh` with tools, as today.
- A line pass: plain `haiku` with no tools and a rules file that tells it to read the changed lines of the diff for slips.

Their findings merge into one review. A category filter then decides which CONCERN and FAIL findings set the verdict: those filed under `correctness`, `security-hygiene`, `error-handling-observability`, `consistency-rot` or `type-contract-debt`. The rest stay visible in the review file but do not set the verdict and are not sent to the reviser.

A recipe today is a list of reviewer aliases plus combs, so it cannot describe this pair. This slice adds per-reviewer options (`tools`, `rules`), the category filter, the shipped rules file and recipe, and switches the code-review default of four shipped pipelines to the recipe.

**Which code gates change.**

| Code review run by | After this slice | Why |
|---|---|---|
| `P6`, `implement`, `implement-plan`, the `review` pipeline | `haiku-line-pass` | D10 |
| `P56`, `P456` | `haiku-xhigh` | Their one `review-model` also reviews documents, where the recipe is refused (D7). A literal model on their code step would fix the default but stop `-p review-model` from reaching it. A separate parameter is [#390](https://github.com/ecorkran/squadron/issues/390) |
| `sq review code` with no `--model`, with or without `--max` | `haiku-xhigh` | It takes its model from `default_model_code`, then `default_model`, then the `code` template, whose model is part of the template hash (Technical Scope) |

`sq review code --model haiku-line-pass` and `-p review-model=haiku-line-pass` run the recipe on any code review that has a diff. `sq review code --files <glob>` with no diff is refused with the recipe (D7).

**What was measured.** 50 public PRs, 139 known bugs, one judge model (`user/reference/review-recall-results/20261122-martian/RESULTS.md`, strict profile):

| Entry | Recall | Precision | $/review |
|---|---|---|---|
| haiku-xhigh, all findings (today's gate), runs 1 and 2 | 64.7%, 59.7% | 25.7%, 23.8% | $0.12 |
| haiku-xhigh with the same category filter, run 1 | 60.4% | 37.0% | $0.12 |
| The pair with the filter, runs 1 and 2 | 69.1%, 66.9% | 33.4%, 34.8% | $0.13 |

- These are two runs a side with no paired intervals, which is less than 420's comparison rule asks for. RESULTS.md gives a run-to-run spread of about five points of recall. The pair's recall gain over its own haiku-xhigh run (4.4 and 7.2 points) is about the size of that spread. The precision gain (about 8 and 11 points) is the clearer effect.
- Against the filter alone on run 1, the pair buys 8.7 points of recall for 3.6 points of precision. The filter alone is this slice's recipe mechanism with one reviewer, so the PM can ship either by editing the recipe.
- The production line pass is not sent exactly what the measured one was. The measured line pass got its rules file through `--rules` in a benchmark sandbox. In production it also gets the step's rules for the project under review (D3).

**Against the architecture.**
- *Public benchmark.* 420 excludes a public benchmark as a source of cases. These numbers, the shipped rules file and D11's fixtures come from one. The PM added this slice to the plan on 20261123 from those runs (plan entry 18, commit d2b16aee), and 420's amendment of 20261123 records it: public-benchmark results may inform configuration; cases still come from project history. The pair has not been measured on 430's case sets, and `sq benchmark recall run` cannot run it until [#393](https://github.com/ecorkran/squadron/issues/393) (D8).
- *Cost.* The line pass is one more call in a production review. It counts toward the step's usage record and so toward `pipeline.max_cost_usd`.
- *Production changes.* 420's amendment of 20261118 limits this component's production changes to the review path. This slice changes the review file's body (the "Not gating" table, D6) and the default review model of four pipelines (D10). Both are on the review path.

## Value

User-facing. On the public benchmark the pair raised fewer findings that matched no known bug than today's gate, and found as many known bugs or more (Overview). The reviser is sent only findings in the behavior categories. Effort: 3/5.

## Technical Scope

Included:
- A recipe may give a reviewer options: `tools: false` and a `rules` file (D1, D2, D3).
- Both options in the stage identity (D4).
- A category filter, `keep_categories`, with no model call (D5), and what happens to findings it does not keep (D6).
- The filter scored in `sq benchmark recall report` and counted in its real-work table (D8).
- The shipped rules file `line-pass.rules.md` and recipe `haiku-line-pass` (D9).
- The shipped defaults in `P6`, `implement`, `implement-plan` and `review.yaml` (D10).
- A test that reproduces the hand-run entry from stored reviewer outputs (D11).

Excluded:
- Merging duplicate findings between the two reviewers (435). A defect both reviewers raise appears twice in the review.
- Reviewers that read earlier findings (436).
- Two reviewers with the same alias in one recipe. Reviewers stay unique by alias, as today; 436's focused reviewers need a reviewer name separate from the alias and add it there.
- A recipe with both `keep_categories` and `combs` ([#392](https://github.com/ecorkran/squadron/issues/392)). It is refused when it loads (D5).
- Running a reviewer that has options in `sq benchmark recall run`, and scoring one from stored outputs in the report (#393). Both refuse or leave it out, by name (D8).
- `P56` and `P456` (Overview, #390).
- The `code` template's own default model (`model: haiku-xhigh`). `template.model` is part of the template hash, so changing it would give every stored code-review stage a new identity.
- A time bound on a stage call (D2).
- The full benchmark run of the built recipe (50 reviews, about $6.50 on the plan, and about $3.60 of judging on OpenRouter). It is the PM's to start after the slice, through the 20261122 harness, which calls `sq review code --model <name>` and so needs nothing from #393. No task runs it.

## Dependencies

### Prerequisites
- **430 (complete):** the recipe model, stage identities, scoring and report.
- **434 (complete):** the recipe runner, merge, review file section, `recipe_review` record and `validate_recipe_review`.
- The `haiku` and `haiku-xhigh` aliases (`data/models.toml`), both on the `sdk` profile. The recipe needs no OpenRouter key and no Codex credits, so it runs wherever today's default runs.

### Interfaces Required
- `run_review_with_profile` (`review/review_client.py`): its existing `no_tools` and `rules_content` parameters. No change to it.
- `ReviewCategory` (`core/finding_categories.py`), the one definition of category values.
- `map_historical_category` (`metrology/review_category_map.py`), already applied when a stage's findings become `RecallFinding`s.
- `StageConfig` (`metrology/recall_run_models.py`) and `stage_config` (`recipes/stage_config.py`).
- `RecipeReviewInfo.stage_section` (`review/models.py`), the rendered "Recipe" section of the review file.

## Architecture

### Component Structure

| Module | Change |
|---|---|
| `recipes/recipe.py` | `ReviewerOptions` (`tools`, `rules`, and the loaded `rules_path` and `rules_content`); `Recipe.reviewer_options` (alias to options) and `Recipe.keep_categories`; `load_recipe` reads each rules file. `Recipe.reviewers` stays a tuple of alias strings (D1, D3, D5) |
| `recipes/reviewer_options.py` (new) | `reviewer_call_options(call_options, options)`: the per-reviewer call options (D2, D3). Kept out of `recipe_runner.py`, which is already over the file-size guideline |
| `recipes/kept_findings.py` | `split_by_category(findings, keep)`, beside `comb_input`: pure, no I/O. Used by the runner, 430's scoring and the real-work table (D5) |
| `recipes/stage_config.py` | `stage_config`, `alias_stage_config` and `planned_stages` take the reviewer's options: `tool_use` and the rules hash (D4) |
| `recipes/recipe_runner.py` | Per-reviewer call options; the filter on the reviewer's CONCERN and FAIL findings (D5) |
| `recipes/recipe_outcome.py` | `ReviewerOutcome.not_gating`: the findings the filter did not keep |
| `recipes/recipe_merge.py` | The "Not gating" table in the Recipe section (D6). Its docstring says the reviser reads the review file; the reviser's feedback is built from the review action's findings, and the docstring is corrected |
| `review/models.py`, `review/persistence.py` | `RecipeReviewInfo.not_gating` (a count); the Findings heading and line for a review with no gating finding (D6) |
| `recipes/recipe_record.py` | `recipe_hash`'s canonical form (D1); `keep_categories` written to the record (D6) |
| `recipes/model_ref.py` | `validate_recipe_review` refuses `keep_categories` and a `tools: false` reviewer on a review with no diff (D7) |
| `metrology/recall_run_models.py` | `StageConfig.rules_hash` (D4) |
| `metrology/recipe_review_models.py` | `RecipeReview.keep_categories` (D6) |
| `benchmark/recall/scoring.py` | A reviewer that has options matches no stored entry; the filter in `reviewer_output` (D8) |
| `benchmark/recall/run_plan.py` | `expand_pending` refuses a recipe whose reviewers have options (D8) |
| `benchmark/recall/label_candidates.py`, report modules | Label candidates; the report columns (D8) |
| `benchmark/recall/real_work.py` | Not-gating findings counted apart from kept ones (D8) |
| `data/recipes/` | `haiku-line-pass.yaml`, `line-pass.rules.md` (D9) |
| `data/pipelines/` | `P6`, `implement`, `implement-plan`, `review` (D10) |

Not changed: `pipeline/classification.py`, the member check in `model_ref.py`, and the two entry points' options dicts (`cli/commands/review_recipe.py`, `pipeline/actions/review_recipe.py`), because `Recipe.reviewers` stays strings and the runner derives each reviewer's options from what the entry point already passes.

### Data Flow

```
recipe haiku-line-pass
  reviewer haiku-xhigh ──▶ review (step's rules, tools) ─┐
  reviewer haiku       ──▶ review (step's rules + line-pass rules, no tools) ─┤
                                                         ▼
        per reviewer: CONCERN/FAIL findings ──split_by_category──▶ gating
                                                         └──▶ not gating
  merge ──▶ ReviewResult.findings = gating findings + NOTE/PASS findings   → verdict, reviser, review ingest
        └─▶ Recipe section: stage table + "Not gating" table               → review file, response output
```

### State Management

None added. The review file and the `recipe_review` record are the durable outputs, as in 434.

## Technical Decisions

### D1 — Reviewer options are a mapping beside the reviewer list
Status: decided
- `reviewers` stays a list of alias strings. A new optional key `reviewer_options` maps a reviewer alias to `tools` (default `true`) and `rules` (default none). A key that is not in `reviewers`, or an unknown option, fails `load_recipe`.
- Every consumer and test that reads `recipe.reviewers` as strings, or builds `Recipe(reviewers=("a",))`, is untouched. Recipes written before this slice load unchanged.
- **`recipe_hash` canonical form.** Today it is sha256 of the JSON dump of `name`, `reviewers`, `pool` and `combs`. After this slice the dump is the same four keys, plus `reviewer_options` only when it is not empty (each entry: `tools`, the `rules` file name, and the sha256 of the rules content) and `keep_categories` only when it is set. The loader-set `rules_path` and `rules_content` are never in the dump. So a recipe with neither new key hashes as it does today.
- The first task, before the model changes, records the current `recipe_hash` of every shipped and reference recipe in a test; the test must still pass at the end.
- Rejected: a reviewer entry that is a string or a mapping. It turns `reviewers` into a tuple of objects, which touches about eight source consumers, about sixty test constructions and the hash.

### D2 — `tools: false` is the existing no-tools review
Status: decided
- A reviewer with `tools: false` is called with `no_tools=True`: the path `sq review --no-tools` takes, which removes the tools, appends the "No Tools In This Session" notice to the system prompt, and records `tools_suppressed_reason`. The measured line pass ran this way.
- **Call options.** Both entry points already put `rules_content` in the call's options, and the CLI also puts `no_tools`. `reviewer_call_options` returns a copy of those options with `no_tools` and `rules_content` replaced for a reviewer that has options, and the options unchanged for one that has none. The runner passes neither as a separate keyword, so no argument is given twice.
- `tools: true` on an alias whose model cannot use tools changes nothing: the alias's capability still decides, as for any review.
- A step-level tool-less review (`--no-tools`, `allowed_tools: []`) with a recipe stays refused, as in 434.
- **A call that never returns.** The line pass is one more stage call under 434 D5's rule: a stage still running after `review.recipe_stage_slow_s` logs one WARNING and is not stopped, so a hung provider call holds the recipe until it returns or the run is cancelled. `pipeline.max_cost_usd` bounds spend, not time. This slice adds no time bound, for 434's reason: a recipe-only bound would make the two review paths differ.

### D3 — `rules` names a file beside the recipe, appended to the step's rules
Status: decided
- `rules: line-pass.rules.md` is a file name resolved in the recipe file's own directory. A name with a directory part, an absolute path or `..` is refused. A project recipe in `project-documents/user/recipes/` therefore carries its rules files there, and a shipped recipe in `data/recipes/`.
- `load_recipe` reads the file as UTF-8 and sets the option's `rules_path` (absolute) and `rules_content`. A file that is missing, cannot be read (`OSError`), is not UTF-8 (`UnicodeDecodeError`) or is empty raises `RecipeError` with the recipe path and the rules file name, so the pre-run check stops a pipeline before its first step. A test covers each of the four, the non-UTF-8 file included.
- The recipe file's own read gets the same treatment: `load_recipe` today catches `OSError` and `yaml.YAMLError`, so a recipe file that is not UTF-8 escapes as a traceback. It now raises `RecipeError`, with a test.
- `reviewer_call_options` sets the stage's `rules_content` to the step's assembled rules content (`options["rules_content"]`: template rules, the step's own `--rules`, always-on and language rules), then the existing `RULES_SEPARATOR` (`project_rules/render.py`, which `review/rules.py` already joins rules with), then the reviewer's rules; when the step has none, to the reviewer's rules alone. Both land under "Additional Review Rules" in the system prompt. The other reviewers of the recipe do not get it.
- **Not the same order as `sq review --rules`.** That command puts its file after the template rules and before the always-on and language rules; here the reviewer's rules come last. The plan entry asked for the `--rules` order and is amended (20261123) to this one: the runner is handed rules that are already assembled, and matching the order would mean assembling rules once per reviewer in both entry points. The measured run used `--rules`, so it and production send the same rule texts in a different order. `rules_hash` (D4) identifies the reviewer's rules file, not the assembled rules: the project's own rules already differ between any sandbox and a production review and are in no stage key.
- Rejected: a rules search path separate from the recipe's directory. One place per recipe is enough, and it keeps a project recipe and its rules together.

### D4 — Both options are in the stage identity
Status: decided
- `StageConfig` gains `rules_hash: str | None = None`: sha256 of the reviewer's rules file content, `None` when the reviewer has no rules.
- `config_key` includes `rules_hash` only when it is set. A stage with no reviewer rules keeps the key it has today, so every stored stage output and `recipe_review` record still matches. A test asserts the key of a stored entry is unchanged, and that two rules contents give two keys.
- `tool_use` is already in the key. For a `tools: false` reviewer it is `false`, whatever the alias allows.
- **The options parameter is optional where it is added**, default `None`: `stage_config` and `alias_stage_config`. A call with no options gives today's config and key, so existing callers (`tests/recipes/test_stage_config.py`, and `live_stage_config`, which passes none) are unchanged. The benchmark's `ConfigFor`, `live_stage_config` and `StageIdentityResolver.resolve` keep their signatures (D8).
- Editing the rules file changes `recipe_hash` (D1), which starts a new real-work row (434 D10).
- Hand-run outputs imported before this slice have no rules hash. The 20261122 line-pass outputs are not imported as stage entries; D11 reads them as files.

### D5 — The category filter is a recipe key, applied per reviewer, with no model call
Status: decided
- `keep_categories: [correctness, ...]` at the recipe's top level. Each value must be a `ReviewCategory` value; any other fails `load_recipe`, naming the value and the valid ones. Absent means no filter. An empty list is refused.
- **A recipe with both `keep_categories` and `combs` fails `load_recipe`** (#392). The benchmark builds a live comb's input in `stage_runner.comb_input_findings`, which has no recipe in scope, so a comb would be sent not-gating findings. No shipped recipe has both.
- `split_by_category(findings, keep)` returns the gating and the not-gating findings. It reads each finding's normalized category (`RecallFinding.category`), the value the reviewer's own category maps to.
- It applies to CONCERN and FAIL findings. NOTE and PASS findings are untouched, as with combs.
- In the runner the gating list becomes the reviewer's kept findings. The map from finding id to the reviewer's own finding (`source` in `_run_chain`) still covers every finding the reviewer returned, since the "Not gating" table reads it too.
- **A finding with no category is gating.** A reviewer that leaves the category out has said nothing about which kind of defect it is, and the gate must not lose a defect to an omission. A test covers it. The measurement's rule excluded such a finding; in the stored benchmark outputs no CONCERN or FAIL finding lacks a category, so the two rules give the same result on that data.
- A category the reviewer invented normalizes to `other`, which is not in the shipped list, so it is not gating. This is what the measurement did.
- **It is not a stage kind.** The plan entry called it a stage and is amended (20261123). It has no call, cost, outcome or failure, which are what a stage record holds, so it is a pure function over the reviewer's findings: no `StageKind`, no pending stage in `sq benchmark recall run`, no planned `StageConfig`. The recipe hash covers `keep_categories`.

### D6 — Not-gating findings stay in the review file, out of the findings list
Status: decided

This settles the plan's open question. The measurement dropped them; here they are kept where a person can read them and nothing acts on them. The PM decided on 20261122 not to drop real findings to raise precision, and on the benchmark these categories held 5 of haiku-xhigh's 90 hits.

- `ReviewResult.findings` holds the gating findings, then the NOTE and PASS findings, as 434 orders them. These read that list and so never see a not-gating finding:
  - the verdict (`verdict_from_findings`);
  - the reviser, whose feedback is built from the review action's findings;
  - review ingest into the metrology store.
- The review file's Recipe section gains a "Not gating" table after the stage table: one row per finding with reviewer, category, original severity, location and title. It is a table, not finding headings, so the review parser does not read its rows as findings.
  - Every `|`, `[` and `#` in a cell is written with a backslash before it (`\|`, `\[`, `\#`), and a missing location is the existing `_NO_VALUE` placeholder. When the Findings section holds no finding-shaped text but the file does, the parser scans the whole file, and its `###` and bullet patterns match anywhere in a line; escaping every `[` and `#` leaves no finding-shaped text in a cell.
  - **A review with no gating finding.** Today a review with no findings is saved with no `## Findings` heading and the line "No specific findings.", and with no heading the parser scans the whole file, where a title such as `- [CONCERN] x` in a table row reads as a finding. So when the Recipe section has a "Not gating" table and the findings list is empty, the file still gets the `## Findings` heading, followed by "No gating findings; N not gating (see the Recipe section)." `RecipeReviewInfo.not_gating` carries N, since `review/` cannot import `recipes/`.
  - A test saves a review with no gating finding whose not-gating finding has `|` and `- [CONCERN] ` in its title and no location, parses the file, and asserts the row is one row, no finding is parsed, and the line above is present.
- Two readers do see the table, and neither acts on findings:
  - The Recipe section is part of `ReviewResult.raw_output`, so the table is in the review action's response output (`outputs[RESPONSE]`). A split review joins its parts' responses, so a split recipe review shows each part's table.
  - On the SDK path the pipeline summarizer is given every file the run produced, the saved review file included.
- **The record.** `RecipeReview` gains `keep_categories` (the list the review ran with, `None` for a recipe with no filter). Its review stages already hold every finding with its category, so which findings were gating is derived from the two with `split_by_category`, over the review stages whose outcome is OK (the runner uses no finding of a failed stage, as `real_work.chain_counts` already assumes); no per-finding mark is stored. This is the part of [#391](https://github.com/ecorkran/squadron/issues/391) the real-work table needs (D8).
- `sq review --output json` is unchanged: `to_dict()` carries `findings`, which holds no not-gating finding.
- Incomplete recipes follow 434 D5 with "kept" meaning gating. A recipe whose line pass failed and whose other reviewer raised only not-gating findings has nothing kept: verdict UNKNOWN, the review fails.
- Rejected: writing them as NOTE findings. The reviser is sent NOTE findings, and the stored severity would no longer be the reviewer's.

### D7 — The filter and a no-tools reviewer need a diff
Status: decided
- `validate_recipe_review` refuses, before any model call and naming the recipe: `keep_categories` on a review with no diff input, and a `tools: false` reviewer on a review with no diff input. The category values are the code review's vocabulary, and a no-tools reviewer of a document would get only what the prompt carries. The same refusal already applies to combs.
- So `haiku-line-pass` is refused on `slice`, `tasks` and `arch` reviews, with a message that names the template.
- The pipeline pre-run check knows only the template, and the `code` template can take a diff. A `code` step given `files` and no diff therefore passes `sq run --dry-run` and is refused when the step runs, still before any model call. Refusing it at pre-run is [#396](https://github.com/ecorkran/squadron/issues/396).

### D8 — The benchmark scores the filter like a comb; reviewers with options wait for #393
Status: decided
- **Reviewers with options are not run or scored by the benchmark in this slice** (#393). The plan's criteria ask for the options in the stage identity and the filter in the report, not for the benchmark to run a no-tools reviewer, and the PM's run after the slice goes through `sq review code` (Technical Scope). Until #393:
  - `sq benchmark recall run` refuses a recipe whose reviewers have options, before its bound is printed, naming the recipe, the reviewer and #393. Without the refusal it would run the reviewer with tools and no rules file.
  - `sq benchmark recall report` matches a reviewer that has options to no stored entry, live or imported, so a tool-enabled or imported `haiku` output is never scored as the line pass. The row lists every case run as left out, as it does today for a reviewer with no stored output. A report test stores a tool-enabled `haiku` entry and an imported one and asserts neither serves the `haiku-line-pass` reviewer.
  - `ConfigFor`, `live_stage_config`, `StageIdentityResolver.resolve`, `PendingStage` and `review_argv` are unchanged, and so are their test doubles.
- **Scoring.** `reviewer_output` (`benchmark/recall/scoring.py`) applies `split_by_category` to the reviewer's CONCERN and FAIL findings. No stored stage is needed, so a recipe that adds `keep_categories` to reviewers whose outputs are already stored is scored with no new call.
- **Report.** A recipe with a filter gets, per row: findings per run before and after the filter, the per-finding gating or not-gating mark in the JSON report, and known-bug recall before and after it. A recipe with no filter prints as today.
- **Real-work table.** `real_work._reviewer_counts` applies `split_by_category` with the record's `keep_categories`. "Raw findings/review" stays every CONCERN and FAIL finding; a new "Not gating/review" column counts the ones the filter did not keep; "Kept/review" counts only gating findings. A record with no `keep_categories` counts as today. A test covers a record with not-gating findings.
- `sq benchmark recall label` candidates (`label_candidates.py`) include not-gating findings, so recall before the filter can be scored.

### D9 — The shipped recipe and rules file
Status: decided

`src/squadron/data/recipes/haiku-line-pass.yaml`:

```yaml
name: haiku-line-pass
reviewers: [haiku-xhigh, haiku]
reviewer_options:
  haiku:
    tools: false
    rules: line-pass.rules.md
keep_categories:
  - correctness
  - security-hygiene
  - error-handling-observability
  - consistency-rot
  - type-contract-debt
```

- `line-pass.rules.md` is the measured file, `review-recall-results/20261122-martian/rules-line-pass.md`, copied byte for byte. A test compares the two files, so an edit to the shipped one is a deliberate act that also changes its identity.
- The name is not an alias in `models.toml`.
- The wheel must carry the `.md` file. A test loads the recipe from the shipped data directory; a one-time `uv build` and `unzip -l` check confirms the wheel carries the file (Hatch packages all of `src/squadron`; no test builds the wheel).
- `tests/benchmark/recall/test_recipe.py`: the `SHIPPED` set gains the third recipe and `test_shipped_recipes_are_the_two_with_no_opus_high_comb` is renamed to drop "the two", in the commit that adds the file. `tests/pipeline/test_classification.py`, `test_recipe_no_longer_shipped_is_refused_at_the_pre_run_check`, pins the string `Known recipes: haiku-sol-luna, haiku-solr-luna.`; it gains `haiku-line-pass` in the same commit.
- A project file `project-documents/user/recipes/haiku-line-pass.yaml` replaces the shipped recipe for that project, P6's default included. This is 434's behavior, with its existing WARNING naming both files; nothing is built for it here.

### D10 — Four shipped pipelines default to the recipe
Status: decided
- `review-model: haiku-line-pass` in `P6.yaml`, `implement.yaml` and `implement-plan.yaml`; `model: haiku-line-pass` in `review.yaml`. In all four the parameter feeds only `template: code` reviews.
- The comment above `review-model` in `P6.yaml` says what the recipe is, that `review-model: haiku-xhigh` gives the old gate, and points to RESULTS.md. It repeats no numbers.
- `sq review code` with no `--model`, and its `--max` loop, keep the template's `haiku-xhigh` (Overview). `--max` passes the model it resolved as `review-model`, which overrides the pipeline's default.
- `P56` and `P456` keep `haiku-xhigh` (Overview).
- Pinned tests that change with the defaults:
  - `tests/pipeline/test_builtin_pipelines.py`, `test_implement_plan_params_and_shape`: the params dict's `review-model`.
  - A new test pins each shipped pipeline's code reviewer: `haiku-line-pass` in `P6`, `implement`, `implement-plan` and `review`; `haiku-xhigh` in `P56` and `P456`.
- Tests that stay as they are (corrected 20261123 after the tasks review):
  - `tests/review/test_review_template_defaults.py` reads the templates, not the pipelines, and the `code` template keeps `haiku-xhigh`, so its assertions pass unchanged. Only its docstring and the `PIPELINE_REVIEW_MODEL` comment are reworded, since the `code` template no longer agrees with four pipelines' code reviewer.
  - `tests/pipeline/test_loader.py` compares `review.yaml` with P6. Both change together, so the test and its docstring stay true.

### D11 — The hand-run entry is reproduced from stored outputs
Status: decided
- Fixture, in `tests/recipes/fixtures/`: for five benchmark PRs, the verdict and the `findings` list of the stored `haiku-xhigh-1` and `haiku-line-1` outputs from `20261122-martian/out/` (no other key, so no sandbox path is committed), and an expected file listing, per PR and reviewer, the titles the hand-run entry sent. The expected file is produced once by the rule in `20261122-martian/convert.py` (severity CONCERN or FAIL, category in the five), not by the code under test.
- The test, `tests/recipes/test_hand_run_entry.py`, builds a `ReviewResult` from each fixture with a helper in the test: one `ReviewFinding` per entry from its `severity`, `title`, `description`, `location` and `category`. It runs the recipe runner and merge with a scripted review call that returns them, and asserts the gating findings' titles equal the expected file, in order.
- `convert.py` compares the stored category string; production compares the normalized category. The test asserts that every category in the fixtures is a `ReviewCategory` value, so the two rules agree on this data by a checked fact.
- The five PRs are chosen so that both reviewers have gating and not-gating findings and at least one PR has a finding in `other`.

## Implementation Details

### API Contracts

Recipe file, after this slice:

| Key | Type | Notes |
|---|---|---|
| `name` | string | Unchanged |
| `reviewers` | list of aliases | Unchanged |
| `reviewer_options` | mapping of reviewer alias to `{tools?, rules?}` | D1; optional |
| `pool` | bool | Unchanged |
| `combs` | list of aliases | Unchanged; not with `keep_categories` |
| `keep_categories` | list of `ReviewCategory` values | D5; optional |

No new command or flag. `sq review code --model haiku-line-pass` and a pipeline `review-model: haiku-line-pass` run the same recipe through the same runner.

### Database / Storage Schema

`schema_version` stays 1; each field has a default, so stored records load.

| Model | Field | Content |
|---|---|---|
| `StageConfig` | `rules_hash: str \| None = None` | D4 |
| `RecipeReview` | `keep_categories: tuple[ReviewCategory, ...] \| None = None` | D6 |

## Integration Points

### Provides to Other Slices
- **436:** the per-reviewer `rules` and `tools` options and their place in the stage identity. Focused reviewers add a reviewer name so one alias can appear more than once.
- **431:** `keep_categories` on `recipe_review` records.
- **435:** nothing new. Its dedupe would run on the merged findings this slice leaves duplicated.

### Consumes from Other Slices
- 430's recipe file, stage identities, scoring and report; 434's runner, merge, review section and record. A line pass that fails is a failed reviewer stage under 434 D5: logged at WARNING, shown in the stage table and the record, and the recipe is incomplete.

## Success Criteria

### Functional Requirements
- A recipe with neither `reviewer_options` nor `keep_categories` loads as before, with the same `recipe_hash` and stage `config_key`s as before this slice (asserted for every shipped and reference recipe against values recorded before the model changed).
- A reviewer with `tools: false` makes its stage call with `no_tools=True`; one with `rules` makes it with the step's rules followed by the file's content; the recipe's other reviewers get the step's options unchanged (asserted on the scripted call's arguments, from both entry points' options dicts).
- `load_recipe` fails, naming the problem, on: an option for an alias not in `reviewers`, an unknown option, a rules file that is missing, unreadable, not UTF-8 or empty, or has a directory part, an unknown category, an empty `keep_categories`, `keep_categories` with `combs`, a recipe file that is not UTF-8.
- Changing the rules file content or the `tools` setting changes the stage `config_key` and the `recipe_hash`.
- With `keep_categories` set, for scripted reviewer outputs:
  - a CONCERN or FAIL finding in a listed category is in the merged findings and sets the verdict;
  - one in an unlisted category, including `other`, is absent from the merged findings and present in the "Not gating" table;
  - one with no category is in the merged findings;
  - NOTE and PASS findings are merged as before;
  - a review whose only CONCERN findings are not gating has verdict PASS.
- The reviser's feedback for a recipe review holds no not-gating finding, and review ingest of the saved file records none. The "Not gating" table test of D6 passes.
- `haiku-line-pass` on a `slice` or `tasks` review is refused before any model call.
- A failed line pass: WARNING logged, `harness_failure` in the stage table and the record, `recipeComplete: false`; with a gating finding from haiku-xhigh the verdict is FAIL, with none it is UNKNOWN and the review fails.
- `sq benchmark recall report`:
  - for a recipe with `keep_categories` over stored reviewer outputs, prints findings and recall before and after the filter with no model call;
  - the report test of D8 passes: a reviewer that has options is never scored from a tool-enabled or imported output of the same alias;
  - `--real-work` counts a record's not-gating findings in "Not gating/review" and not in "Kept/review".
- `sq benchmark recall run` with a recipe whose reviewers have options exits non-zero before printing a bound or making a call, naming #393.
- The D11 test passes.
- `P6`, `implement`, `implement-plan` and `review` default to `haiku-line-pass` and pass the pipeline pre-run check.

### Technical Requirements
- `ruff format`, `ruff check` and `pyright` (zero errors) pass. Tests for `recipes/`, `tests/benchmark/recall/`, `tests/cli/test_benchmark_recall_run.py`, the review action, the review CLI, the pipeline loader and pipeline classification pass, with the pinned tests of D9 and D10 updated.
- Tests run no model.
- `split_by_category` is the only place a finding's category is compared with the kept list.
- `docs/PIPELINES.md` (Recipe reviews) describes `reviewer_options`, `keep_categories`, the "Not gating" table, the new pipeline default, and that `sq review code` with no `--model`, `P56` and `P456` still run `haiku-xhigh`. The `implement-plan` sentence that says `review-model` "defaults to `haiku-xhigh`, matching `P6`" is corrected; the plan-batch parameter table's `review-model` row stays `haiku-xhigh`, since `slices-plan` and `tasks-plan` review documents. The Built-in Pipelines table lists no defaults, so it has no row to correct. `README.md` names the new default. CHANGELOG has a user-facing bullet.

### Integration Requirements
- `sq review code <slice> --model haiku-line-pass` and a P6 run give the same review shape: one review file with the Recipe section, one `recipe_review` record.
- The existing recipes `haiku-solr-luna` and `haiku-sol-luna` run unchanged.

### Verification Walkthrough

Verified 20261123 on the slice branch. Run from the squadron checkout with `uv run sq` (steps 5 and 6 run from the fixture directory with `uv run --project <squadron checkout> sq`). Steps 1 to 3 make no model call. Steps 4 and 5 are live; the stage table's cost column reported $0.0053 for the `haiku-xhigh` review and $0.0012 for the line pass in step 4, a few cents with the reviser in step 5.

1. **The recipe loads and old recipes are unchanged.**
   ```bash
   ls src/squadron/data/recipes/
   uv run pytest tests/recipes tests/benchmark/recall/test_recipe.py -q
   ```
   The directory holds `haiku-line-pass.yaml` and `line-pass.rules.md` beside the two existing recipes. The tests include the hash and key checks for the existing recipes.

   Actual: `ls` printed `haiku-line-pass.yaml  haiku-sol-luna.yaml  haiku-solr-luna.yaml  line-pass.rules.md`; the tests printed `174 passed`.

2. **The hand-run entry is reproduced.**
   ```bash
   uv run pytest tests/recipes/test_hand_run_entry.py -q
   ```
   Passes: for the five fixture PRs the gating findings equal the hand-run entry's.

   Actual: `7 passed` (five PRs, plus the two fixture checks: every category is a `ReviewCategory` value, and every CONCERN/FAIL finding has a category).

3. **Refused where it does not apply.**
   ```bash
   uv run sq review slice 437 --model haiku-line-pass --no-save
   uv run sq run P6 437 --dry-run
   ```
   The first exits 1 with an error naming the recipe and the `slice` template, and makes no model call. The second passes the pre-run check with `review-model` resolved to `haiku-line-pass`.

   Actual: the first printed `Error: recipe 'haiku-line-pass': keep_categories is the code review's category filter and needs a diff; template 'slice' has no diff input here` and exited 1. The second printed `Params: {'summary-model': 'sonnet', 'model': 'sonnet', 'review-model': 'haiku-line-pass', ...}` and the step list (`review-1 (review)` inside `revise-code (loop)`), with no classification error.

4. **A live review from the CLI.** In a fixture repo whose last commit turns `total -= amount` into `total += amount` and also adds an undocumented public function:
   ```bash
   uv run sq review code --diff HEAD~1 --model haiku-line-pass -v --cwd <fixture>
   ```
   The output shows findings marked `Reviewer: haiku-xhigh` and `Reviewer: haiku`, the stage table with two review rows, and a "Not gating" table if either reviewer raised a finding outside the five categories. The `haiku` row shows no tool calls. Exit 2 (FAIL) on the sign defect.

   Fixture: `ledger.py` with an `apply_entry` whose debit branch the last commit changed from `total -= amount` to `total += amount`, plus an undocumented `monthly_summary`; `sq config set metrology.project_id fixture-437 --project --cwd <fixture>` run first.

   Actual (exit 2): the log shows `Review tools suppressed (model=claude-haiku-5-5, reason=run-suppressed)` for the second call only. The result is `Review: code  Verdict: FAIL  Model: haiku-line-pass`, with five findings marked `Reviewer: haiku-xhigh` (a FAIL and a CONCERN in `correctness`, CONCERNs in `consistency-rot` and `type-contract-debt`, a NOTE) and one FAIL marked `Reviewer: haiku`, both on the debit sign. The Recipe section:

   ```
   | review haiku-xhigh | review | haiku-xhigh | claude-haiku-5-5 | ok | 6 findings | $0.0053 |
   | review haiku | review | haiku | claude-haiku-5-5 | ok | 1 findings | $0.0012 |

   ### Not gating
   | haiku-xhigh | test-debt | CONCERN | ledger.py | No tests cover the ledger, including the changed debit path and the new function |
   ```

   No `recipe record: not written` line was printed. Caveats: the stage table has no tool-call column, so "no tool calls" is read from the `Review tools suppressed` log line; the review is not saved (no slice number), as for any slice-less code review.

5. **The same review in a revise loop.** With the fixture registered with cf as in 434's walkthrough step 5:
   ```bash
   uv run sq review code 100 --model haiku-line-pass --max 1
   ```
   `--model` is needed: without it `--max` runs `haiku-xhigh` (D10). The review file has `aiModel: haiku-line-pass` and `aiRecipe: true`, and the reviser's round addresses only gating findings.

   Fixture registration: the fixture repo got `project-documents/user/{architecture,slices,tasks}` files for slice 100 (`100-arch.ledger.md`, `100-slices.ledger.md`, `100-slice.ledger-fix.md`, `100-tasks.ledger-fix.md`), branch `100-slice.ledger-fix` holding the defect commit and the documents commit on top of `main` (set back to the base commit), `cf init --lite --name fixture-437`, then `cf set slice 100-slice.ledger-fix` and `cf set arch 100-arch.ledger.md`.

   Actual (exit 2): `review-revise code 100  reviewer=haiku-line-pass  reviser=sonnet  max=1`, `review    FAIL (6)      project-documents/user/reviews/100-review.code.ledger-fix.md`, then `round 1   FAIL (6)      committed 877f82d` and `final: FAIL after 1 round`. The review file has `aiModel: haiku-line-pass`, `aiRecipe: true`, `recipeComplete: true`, one Recipe section and a "Not gating" table of two rows (`test-debt`, `architectural-decay`). The reviser's commit changed `ledger.py` only: the debit sign, an explicit `credit` check with `raise ValueError`, and `monthly_summary`'s annotations (the findings in gating categories), and added no tests (the not-gating `test-debt` finding).

   Caveat: the round did not end PASS. The reviser's fix is uncommitted when the round's review runs (`commit_each_iteration` commits after it), and the diff both reviewers get is the committed one. `haiku-xhigh` read the working tree and wrote "The working tree's `ledger.py:7` reads `return total - amount`, so committing that change resolves this finding", yet still filed the committed defect as FAIL; the no-tools `haiku` line pass cannot see the working tree at all and filed the same FAIL from the diff. With `--max 1` the loop ends there. The loop's later rounds were not run.

6. **The record.**
   ```bash
   cd <fixture> && uv run sq benchmark recall report --real-work
   ```
   One `haiku-line-pass` row counting the reviews of steps 4 and 5. For each review, "Kept/review" plus "Not gating/review" accounts for the rows of its "Not gating" table and its CONCERN and FAIL findings in the review file.

   Actual: `Real work: 3 recipe reviews in 1 rows.` and `| haiku-line-pass [689e3cf8] | 3 | 0 (0) | 5.7 | 1.7 | 4.0 | 0.0 | 0.0 | PASS 0 CONCERNS 0 FAIL 3 UNKNOWN 0 | $0.01 (0) |` (the step 4 review and the two reviews of step 5's round 0 and round 1; the columns are Reviews, Incomplete, Raw, Not gating, Kept, Dropped, Undecided, Verdicts, Cost). Raw 17, not gating 5 and kept 12 over three reviews equal the sum of: step 4 (5 gating findings, 1 table row; no review file), the archived round-0 file (4 gating headings, 2 table rows) and the final file (3 gating headings, 2 table rows). The command also printed three `Skipping unreadable metrology record` warnings for `code_snapshot` files dated 22 October in the user's metrology directory; they are unrelated to recipe records.

7. **The full benchmark run** is the PM's to start (Technical Scope). The numbers to compare with are the pair's rows in RESULTS.md.

## Risk Assessment

### Technical Risks
- **The filter trusts the reviewer's own category.** A real defect filed under `test-debt` or `other` does not set the verdict. On the benchmark that was 5 of haiku-xhigh's 90 hits.
- **Stored identities.** A change to `config_key` or `recipe_hash` for existing recipes would orphan every stored stage output and split real-work rows.

### Mitigation Strategies
- Not-gating findings are in the review file with category and title (D6), and the real-work table counts them (D8).
- D1 and D4 keep both values unchanged when no option is set, each with a test against values recorded before the change.

## Implementation Notes

### Development Approach
1. Record the current `recipe_hash` and stage keys of the existing recipes in a test. Then `ReviewerOptions`, `reviewer_options`, `keep_categories`, the loader's rules file read and refusals, and `recipe_hash`'s canonical form.
2. Stage identity: `rules_hash`, `tool_use` from the options, the optional parameter.
3. `split_by_category`; `reviewer_call_options`; the runner's use of both; `ReviewerOutcome.not_gating`.
4. Merge: the "Not gating" table; `keep_categories` on the record; `validate_recipe_review` refusals.
5. Benchmark: the refusal in `run` and the no-match rule in the report for reviewers with options; filter scoring, the report columns and the real-work table.
6. The shipped recipe and rules file with the `SHIPPED` test; the D11 fixture and test.
7. Pipeline defaults with their pinned tests, the P6 comment, docs, CHANGELOG; live walkthrough steps 4 to 6.

Testing: unit tests per module with the scripted review call 434's tests use; one end-to-end `sq review code` test on a temp git repo with scripted outputs for both reviewers.

### Special Considerations
- The line pass is sent the diff, the step's assembled rules and its own rules file (D3), with the no-tools notice. It has no tools, so it reads nothing else, and a provider-side tool-control gap cannot give it any.
- The no-tools notice tells the reviewer that the request holds "the diff and the file contents you will get". On the `sdk` profile no file bodies are injected, so the line pass holds the diff only. The notice is left as it is: it is the prompt the measured line pass ran with, and it is shared by every no-tools review.
- Both reviewers run one after the other (#372). The line pass took about 20 seconds in the measurement against 4 minutes for haiku-xhigh.
