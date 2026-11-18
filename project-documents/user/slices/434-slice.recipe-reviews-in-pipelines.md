---
docType: slice-design
slice: recipe-reviews-in-pipelines
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies:
- 430
- 425
interfaces:
- 431
- 433
dateCreated: 20261118
dateUpdated: 20261118
status: not_started
turns: 64
promptTokens: 7517862
cachedTokens: 7247104
cacheWriteTokens: 270672
completionTokens: 87804
durationSeconds: 887.4
costUsd: 9.293376
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-fable-5-2:
    rounds: 3
    costUsd: 9.2933754
    completionTokens: 87804
revision_number: 2
---

# Slice Design: recipe-reviews-in-pipelines

## Overview

A review takes a 430 recipe by name wherever it takes one model today: a pipeline's `review-model`, a step's `review.model`, and `sq review --model`. The recipe's reviewers each review the real work, its combs mark each CONCERN/FAIL finding KEEP or DROP, and the kept findings become one review: one verdict, one review file, the same revise loop. Every stage's findings, decisions and cost are written as one record per review, so each real review that uses a recipe leaves a record of what the recipe found, kept and cost.

This is issue [#369](https://github.com/ecorkran/squadron/issues/369) without its last step. Changing the shipped default `review-model` to a recipe is not in this slice (D11).

A recipe review is production work, not a benchmark run. The architecture's 20261118 amendment says so, and names the cost rule that applies (D9).

## Value

User-facing, as the plan entry states. Beyond it, the review file itself shows what each stage found, kept, dropped and cost, so one review can be understood without running a report.

## Technical Scope

Included:
- Recipe files found by name in project and built-in directories (D1). The recipe model and the comb call move out of `benchmark/recall/` (Migration Plan).
- One classification of a review model name as alias or recipe, used by `sq review`, the pipeline pre-run check, and the review action (D2).
- A recipe runner: reviewers, comb chains, merge, verdict (D3–D6).
- One merged review file per review (or per part of a split review), with a stage table (D7).
- A `recipe_review` metrology record per recipe review (D8).
- The step's usage record carries the recipe's total cost, so the run cost cap counts it (D9).
- A "real work" table in `sq benchmark recall report` (D10).

Excluded:
- Changing any shipped pipeline's default `review-model` (D11).
- Concurrent stage calls. Stages run one at a time; concurrency is [#372](https://github.com/ecorkran/squadron/issues/372).
- A printed cost bound or a per-stage cap. Those are the rule for measured benchmark runs; a production review is bounded by the pipeline cost cap (D9).
- MCP. Squadron has no MCP review tool, so there is no MCP surface to give the same result shape. The plan criterion now names the CLI and slash commands.
- `pool: true` recipes in a review. A pool picks one reviewer at random per run, so the same code could get a different verdict on each revise round. They are refused before the run starts (D2) and stay valid for `sq benchmark recall`. The plan criterion now says so.
- Combs on document reviews. A recipe with combs needs a diff (D4).
- Recipes on judge templates (D2).
- Deduplicating findings across reviewers. 430 does no issue clustering, and neither does this.
- Reusing a stage's stored output in a later revise round or on resume. A rerun review reruns the whole recipe (D6).
- Known-bug recall for real work. Real reviews have no known bugs, so the real-work table has counts and cost only.

## Dependencies

### Prerequisites
- **420 (complete):** effort sent on usage records.
- **430 (complete):** the recipe model and loader, the comb call, the decisions parser, the `comb` template, `SCORED_SEVERITIES`, and the stage payload types in `metrology/recall_run_models.py`. The Migration Plan lists what moves.
- **425 (complete):** `ContentSidecars` and its `REVIEWS` kind, for raw stage output.
- **947 (complete):** `pipeline.max_cost_usd`, the cap D9 counts recipe spend against.

### Interfaces Required
- `run_review_with_profile` (`review/review_client.py`), called once per stage, unchanged.
- `require_known_model` and the alias metadata readers (`models/aliases.py`).
- `assert_reviewable_scope` (`review/git_utils.py`), which already runs before a diff review's first call and returns the changed files.
- `save_review_result` (`review/persistence.py`) and the review frontmatter writer.
- `_verdict_from_findings` (`review/parsers.py`), made public as `verdict_from_findings`.
- `UsageCapture` and `stamp` (`pipeline/usage_capture.py`); `RunSpend.add` reads the stamped record.
- `MetrologyStore.write_record` and the `MetrologyRecord` sibling-payload pattern.

## Architecture

### Component Structure

New top-level package `src/squadron/recipes/`. It sits above `review/` and `metrology/` and imports both. `pipeline/`, `cli/` and `benchmark/` import it. `review/` and `metrology/` never import it, so the existing `metrology` → `review` direction gains no cycle.

| Module | Responsibility |
|---|---|
| `recipe.py` | `Recipe`, `RequiredStage`, `load_recipe`, `required_stages` (moved from `benchmark/recall/recipe.py`) |
| `recipe_search.py` | `resolve_recipe(ref, search_dirs)` and the production search directories (D1) |
| `model_ref.py` | `classify_review_model(name, ...)`, returning `AliasRef` or `RecipeRef`; raises on a name that is neither or both (D2) |
| `comb_call.py` | `render_findings`, `run_comb_stage`, `COMB_ALLOWED_TOOLS`, `finding_id_at` (moved, see Migration Plan) |
| `decisions.py` | The decisions parser (moved unchanged) |
| `recipe_runner.py` | Runs the stages in order and returns a `RecipeOutcome`: every stage's result, the kept findings, `complete` (D3–D5) |
| `recipe_merge.py` | Builds the merged `ReviewResult` and its verdict from a `RecipeOutcome` (D5, D6) |
| `recipe_record.py` | `RecipeRecordSink` protocol and the metrology-store implementation (D8) |

`SCORED_SEVERITIES` moves to `review/models.py`, next to `Severity`, and 430's `scoring.py` imports it.

Callers:
- `pipeline/actions/review.py`: `_resolve_model` classifies the winning cascade candidate. A `RecipeRef` sends `_run_part` through the recipe runner; an `AliasRef` runs as today.
- `cli/commands/review.py`: `_run_review_command` classifies the resolved model name the same way.
- `pipeline/classification.py` and `pipeline/loader.py`: the pre-run alias checks call `classify_review_model` for review actions, so a recipe name passes and its member aliases are checked.
- `benchmark/recall/`: imports the moved modules from `recipes/`.

### Data Flow

```
review model name ──classify_review_model──▶ AliasRef  → single-model review, unchanged
                                           └▶ RecipeRef → recipe_runner:
     once: changed files (from the scope check) (D4)
     for each reviewer, in recipe order:
        review stage:  run_review_with_profile(step template, same inputs and rules, reviewer alias)
        for each comb, in order:
           comb stage: run_comb_stage(comb template, the reviewer's findings every earlier comb decided KEEP, changed files)
     → RecipeOutcome(stages, kept findings per reviewer, complete)
        ├─▶ recipe_merge → one ReviewResult (kept findings, verdict) → save_review_result → review file
        ├─▶ RecipeRecordSink → `recipe_review` record + raw stage output in the REVIEWS sidecar
        └─▶ (pipeline) ActionResult: verdict, findings, usage record with the summed cost

sq benchmark recall report ──reads `recipe_review` records──▶ real-work table
```

### State Management

Nothing is held between reviews. The durable outputs are the review file and one `recipe_review` record per review. A pipeline run's state file gets the folded `ActionResult` as for any review, plus the recipe name, `complete` and the record id in its metadata (D8).

## Technical Decisions

### D1 — Production finds recipes by name in the project and built-in directories
Status: decided
- `resolve_recipe(ref, search_dirs)` takes its directories from the caller. First match wins; when a later directory also holds the name (a project recipe overriding a shipped one), a WARNING names both files. A file found by name that fails to load (bad YAML, unknown key, `name` not matching its stem) raises `RecipeError` with its path; the search never moves on to the next directory.
  - **Production** (`sq review`, pipelines) searches `project-documents/user/recipes/` under the working directory, then `src/squadron/data/recipes/` (shipped). It takes names only, looked up as `<name>.yaml`.
  - **`sq benchmark recall`** searches its existing `RECIPES_DIR` (`user/reference/review-recall-recipes/`), then the shipped directory. It keeps accepting a path, as today.
- A recipe file's `name` must equal its file stem, checked at load.
- Shipped recipes: `haiku-solr-luna-opus`, `haiku-sol-luna-opus` and `haiku-sol-opus`. They move from `user/reference/review-recall-recipes/` to `data/recipes/`. None of the three is an alias in `models.toml`.
- The other six benchmark recipes stay where they are. Five of them (`haiku-xhigh`, `sonnet-high`, `sonnet`, `sol`, `luna`) are named after the alias they wrap, so they must stay out of the production search, where D2 makes a name that is both an alias and a recipe an error. `RECIPES_DIR` stays a constant in `benchmark/recall/`.

### D2 — One classification of a review model name, applied before any model call
Status: decided
- `classify_review_model(name, profile_source)` returns:
  - `AliasRef` when the name is a known alias (or a literal model id with a profile source, the existing #175 rule);
  - `RecipeRef(recipe)` when a recipe of that name is found by the production search;
  - an error when it is both ("`<name>` is a model alias and a recipe; rename the recipe"), or neither. The neither message is the existing unknown-alias message with the known recipe names added.
- A `RecipeRef` is validated at the same moment. Each failure names the recipe and the offending member:
  - every reviewer and comb alias must pass `require_known_model`;
  - `pool: true` is refused, because a random pick could change the verdict between revise rounds with no change to the code;
  - a judge template is refused;
  - a recipe with combs on a review that has no diff is refused (D4);
  - an explicit `--profile` or step `profile` is refused, because each stage's alias decides its own profile.
- Where it runs:
  - `sq run`: in the pipeline pre-run check (`classification.py`, and `loader.py`'s `_validate_model_alias` for literal names), so a bad name stops the run before the first step. Session classification treats a recipe as its member aliases.
  - `sq review`: in `_run_review_command`, before the review call.
  - The review action classifies again at execution. That is the only point where a `{review-model}` placeholder is resolved for certain.
- Model cascade: the recipe name is taken from the same cascade as a model (action, step, `-m`, pipeline, config, template default). No new param or flag.

### D3 — Reviewers run the step's own review, one stage at a time
Status: decided
- Each reviewer stage is the review the step would have run with that alias as its model: the same template, inputs, rules and `allowed_tools`. Profile, effort, `tool_use` and `max_output_tokens` come from the reviewer's alias, through the cascade a single-model review uses.
- Stage order is reviewer by reviewer: reviewer 1's review and its comb chain, then reviewer 2's. Calls run one at a time. The recipe runner makes one call at a time, as the review action does today (split parts run in a loop). Concurrency is [#372](https://github.com/ecorkran/squadron/issues/372).
- Rules, input validation, the tasks merge gate and the reviewable-scope check run once, before the first stage, as today.
- A split review (several task files) runs the whole recipe per part, and parts fold as today.
- Each stage's start and finish are logged at INFO with the recipe, stage and alias. A stage still running after `review.recipe_stage_slow_s` logs one WARNING naming it; the call is not stopped (D5).

### D4 — Combs run in process, on the tree the reviewers read, and only with a diff
Status: decided
- A comb stage calls `run_comb_stage` with the built-in `comb` template, the comb alias's settings, `COMB_ALLOWED_TOOLS` (`read_file`, `list_files`, `grep`: no write or shell tool), and cwd set to the review's cwd.
- Its input is the reviewer's CONCERN and FAIL findings (`SCORED_SEVERITIES`) that every earlier comb in the chain decided KEEP. As in 430, combs run per reviewer, never on the union.
- `changed_files` is the list `assert_reviewable_scope` returns for the review's resolved diff spec and exclude patterns. That is the same spec the reviewers' diff is built from, so the comb is told about the files the reviewers saw. Both entry points already call it before the first model call, and it raises `EmptyScopeError` with a WARNING when git cannot compute the range; the runner takes the list as an argument and runs no `git diff` of its own. `extract_diff_paths` (empty list on failure) and 430's `changed_files` (`base HEAD` only) are not used.
- The comb prompt is written for a code change, so a recipe with combs is refused when the review has no `diff` input (D2). A recipe with no combs is a plain fan-out and is allowed on any non-judge template.
- A comb whose input is empty makes no call and is recorded `ok` with no decisions, as 430 records it.
- **Tree state.** Reviewers and combs both read the working tree through tools, in the same cwd. In a pipeline that tree normally holds uncommitted work, since the review runs before the commit. An edit made to the tree while the recipe runs can reach a later comb; this is not detected.
- There is no sandbox and no leak scan: the tree under review is the tree the user is working in. A comb gets the same tool controls a single-model review on its alias's profile gets today: the jailed builtins on OpenAI-compatible profiles, Claude Code's or Codex's own controls on `sdk` and Codex profiles, which do not confine reads to the cwd. That is no wider than the reviewer already has.

### D5 — Kept findings, the verdict, and what a failure does
Status: decided

Kept findings:
- A CONCERN or FAIL finding is **kept** when every comb in the chain decided KEEP, or left it `UNDECIDED`. "Kept" has only this meaning in this design. An undecided finding is never dropped; it is shown as undecided in the stage table and the record. A finding the first comb left undecided is not sent to the second, as in 430, and is still kept.
- NOTE and PASS findings are not combed. They go into the merged review as they are, because a single-model review carries them too and they never affect the verdict.

Verdict:
- `verdict_from_findings` over the merged findings: any FAIL gives FAIL, any CONCERN gives CONCERNS, otherwise PASS. This is the existing rule (#28). The reviewers' own stated verdicts are not used, since a reviewer's CONCERNS may rest on findings the comb dropped.

Failed stages (each is logged at WARNING with the recipe, stage and reason, appears in the review file's stage table, and is in the record):

| Failure | Stage outcome | Effect |
|---|---|---|
| Reviewer call raises `ProviderError` (including a provider timeout or rate limit) | `harness_failure` + the error text | The reviewer contributes no findings. Its combs do not run. The recipe is **incomplete** |
| Reviewer returns verdict UNKNOWN, with or without findings (this includes output the parser reads without raising but cannot place) | `config_failure` | Same as above; any findings it returned are not used, as 430 treats an UNKNOWN review |
| Comb call raises `ProviderError`, or returns no parseable decision line | `harness_failure` / `config_failure` | The comb's input passes through uncombed, marked "not combed" in the review. The next comb in the chain runs on that input. The recipe is **incomplete** |
| Comb decides some findings only | `ok` | Missing ones are `UNDECIDED` and kept |
| Comb repeats a finding id or names an unknown one | `ok`, WARNING with both counts | The first decision per id wins and unknown ids are ignored, as the parser already does. `duplicate_decisions` and `unknown_ids` are in the record |

- **An incomplete recipe cannot pass.** If the recipe is incomplete and the verdict rule would give PASS, the merged verdict is UNKNOWN and the review fails:
  - Pipeline: the action returns `success=False` with an error naming the failed stage, as a single-model provider failure does today. Resuming the run reruns the review.
  - `sq review`: prints the failed stages and exits 1.
  - The review file and the record are still written, so the spend and the reason are on disk.
- If the recipe is incomplete but CONCERN or FAIL findings were kept, the review succeeds with verdict **FAIL**, whatever severities were kept. The revise loop has real findings to act on (the reviser's feedback is built from findings, not the verdict), and the next round reruns the whole recipe, which retries the failed stage. FAIL clears neither `until: review.pass` nor `accept_if: review.concerns_or_better`, so a loop that exhausts its rounds on a partial review takes its exhaust path and is never accepted. The review file says which stage failed and that the FAIL comes from the incomplete recipe; a test covers exhaustion on a partial review.
- All reviewers failing is the first case: nothing kept, UNKNOWN, the review fails.
- Rejected: failing the review on any stage failure. One reviewer hitting a quota would discard the other reviewer's findings and stop a loop that had work to do. Also rejected: a synthetic "reviewer failed" finding, which would send the reviser a finding it cannot fix.

Other failures. The runner appends each finished stage to a `RecipeProgress` the caller owns, so the caller still has the finished stages when the runner does not return:

| Mode | Level | Effect |
|---|---|---|
| Git cannot compute the diff range (bad range, not a repository) | WARNING, from `assert_reviewable_scope` | `EmptyScopeError` fails the review before any model call, through the existing pre-call path. Nothing is recorded |
| A stage raises anything other than `ProviderError` (a parse bug, an error in the merge) | ERROR, `logger.exception` | The runner does not catch it. The caller writes the record with the finished stages, `complete: false`, verdict UNKNOWN and `aborted` set to the error text, then fails the review. The pipeline action stamps the finished stages' spend on its failure result, as a provider failure does. No review file is written |
| The run is cancelled or interrupted mid-recipe (Ctrl-C, pipeline cancel) | WARNING | The caller writes the same aborted record, synchronously, because an awaited write would be cancelled with the task. The cancellation then propagates. As with a cancelled single-model review, the step has no `ActionResult`, so `RunSpend` does not see the finished stages' spend; the record holds it |
| A stage call hangs or runs long | WARNING once, when the stage passes `review.recipe_stage_slow_s`, naming the recipe, stage, alias and elapsed time | The call is not stopped: `run_review_with_profile` has no time bound, and a recipe-only bound would make the two review paths differ. Cancelling the run takes the row above |

### D6 — One merged review, and a revise round reruns the whole recipe
Status: decided
- `recipe_merge` builds one `ReviewResult`:
  - findings: reviewer 1's kept findings, then reviewer 2's, then the NOTE and PASS findings in the same reviewer order. Each finding names its reviewer alias in the review body. Finding ids are renumbered over the merged list by the existing id rule.
  - `raw_output`: a rendered summary (verdict, stage table, findings). Each stage's raw output is in the sidecar, not in the review file.
  - `cost_usd`, `duration_seconds`, `turns`, `tool_calls_made`: sums over stages.
- The revise loop is unchanged. Its review action runs again each round, so every round runs every stage. No stage output is carried between rounds.
- Dropped findings are not in the review file. The reviser reads that file, and a dropped finding there would be acted on.

### D7 — Review file: recipe name in frontmatter, stage table in the body
Status: decided
- Frontmatter:
  - `aiModel` is the recipe name, and `aiRecipe: true` marks it as a recipe, not a model. `aiProfile` and `requestedModel` are omitted.
  - `recipeComplete: true|false`.
- Readers of `aiModel`:
  - `metrology/identity.py` reads it as a model identity, for judge-template reviews only. D2 refuses recipes on judge templates, so it never sees a recipe name.
  - `review/frontmatter_usage.py` reads it into a usage record's `model` field, where the recipe name is the only name the whole review has.
  - Any new reader checks `aiRecipe` first.
- Body: a "Recipe" section before the findings, with one row per stage (`kind`, `alias`, answering model, `outcome`, findings or kept/dropped/undecided counts, cost) and, for a failed stage, its reason.
- **Review ingest is unchanged.** `CodeReviewRecord` has no model field: it holds the review path, commit, slice, verdict and findings. A recipe review's merged findings carry the reviewers' normalized categories, so `sq metrology` ingests it like any code review, and 400's reports see one review with the kept findings. An UNKNOWN recipe review is not recorded, by the existing rule. No review written before this slice has a recipe name in `aiModel`.
- The file name and location follow the existing save rules. A recipe does not change them.

### D8 — One `recipe_review` record per review, written by the runner's caller through a sink
Status: decided
- The record is written for every recipe review, from the pipeline action and from `sq review` alike. Prompt-only pipelines (slash commands) run `sq review` as a shell command and have no `ActionResult`, so the run state file cannot be the record's home. The plan's "stored with the run" is now "stored in the metrology store, keyed by run id" for executor-run pipelines; prompt-only pipelines' records have null run linkage (schema below).
- Payload `RecipeReview` in `metrology/recipe_review_models.py`, record type `recipe_review` (schema in Implementation Details). It reuses 430's stage payload types and adds no new enum.
- Stage identity is 430's: `StageConfig` (`config_key`) plus `effort_sent`. The pure part of `live_stage_config` (resolved alias settings to `StageConfig`) moves to `recipes/stage_config.py`, and both the runner and 430 call it; only the auth-check dependency stays in `benchmark/recall/`. `effort_sent` is the stage result's `effort` (430 D6). That key is absent when the provider applied no effort, and the record then holds `null`, never the alias's configured effort (420 arch, Absent is not zero); a test covers it.
- `RecipeRecordSink.write(record, raw_outputs)` is injected. The pipeline executor and the CLI pass the metrology-store sink; tests pass a fake.
- `write` is synchronous. Normal paths call it through `asyncio.to_thread`. The cancellation path (D5) calls it directly, since an awaited call would be cancelled with the task; if it raises there, the error is logged at ERROR and the cancellation still propagates.
- Order: the review file is saved first, then the record is written. If the save raises, the record is written with `review_file: null` and the save error then propagates as it does today.
- **A failed write does not fail the review.** The caller catches `MetrologyStoreError` (what `write_record` raises) and `OSError` (the sidecar write), logs at ERROR with the record id, and returns the review's result. The comment at the catch gives the reason: the review has already succeeded and its result is the primary output, the same boundary the review-file save has. Any other exception propagates as D5's unexpected-exception row. The pipeline `ActionResult` metadata and the CLI output then say `recipe record: not written`.
- Pipeline `ActionResult.metadata["recipe"]`: the recipe name, `complete` and the record id. Stage detail is in the record.

### D9 — The step's usage record is the recipe's total, under the pipeline cost cap
Status: decided
- A recipe review is a production review. The architecture's rule that a measured run prints a bound and stops at its own cap applies to benchmark commands (`sq benchmark recall run` keeps it). In a pipeline, a review, single-model or recipe, is bounded by `pipeline.max_cost_usd` (947). A standalone `sq review` has no cap today for any model, and this slice adds none; the 20261118 amendment says so.
- The action stamps one `UsageRecord`: `alias` is the recipe name, `model` is `None`, `cost_usd` is the sum of the stages' known costs, `turns` and `duration_seconds` are sums, `tokens` are summed per field.
- **With an unpriced stage, the stamped cost is a floor.** The cap then counts less than the recipe spent. This is kept over stamping `None`, which would make `RunSpend` count nothing for the whole recipe, as it does for an unpriced single-model step; counting the priced stages stops a capped run sooner. Each unpriced stage is named in a WARNING and in the record, and the real-work table counts reviews with one (D10). When no stage has a cost, `cost_usd` is `None`, and `RunSpend` warns once for the recipe name as it does for an unpriced alias.
- `cost_basis` is the stages' common basis when they share one, else `None`. Per-stage bases are in the record.
- A failed review (D5) still stamps what its stages spent, as a single-model provider failure does (slice 175 D5).
- The cost cap is checked after each action, as today. A recipe review is one action (a split review runs the recipe per part inside it), so one review can cross the cap by its own cost, as any action can.

### D10 — 430's report gets a real-work table
Status: decided
- `sq benchmark recall report --real-work` prints rows from `recipe_review` records of the current project.
- **Row key:** recipe name, recipe hash, and the record's `planned` stage configs: every stage the recipe defines, in `required_stages` order, resolved to `StageConfig` before the first call. `config_key` covers model, profile, template hash, `tool_use` and `max_output_tokens`, so a change to an alias in `models.toml`, to the review template or to the comb prompt starts a new row. Because the key comes from the plan, a failed reviewer, a skipped comb chain, an empty-input comb or an aborted review lands in the same row as a complete review of the same configuration, and is counted in Incomplete. `effort_sent` is not in the key, since a stage that never ran sent nothing: when the stages that did run in one row sent different efforts for the same alias, the row is flagged "effort differs". Rows that share a recipe name are flagged "config differs", as 430 flags rows whose stages resolve differently. Report tests cover a complete review, an empty-input comb, a skipped comb chain and an aborted review of one configuration landing in one row.

  | Column | Meaning |
  |---|---|
  | Reviews | Records counted |
  | Incomplete | Records with `complete: false`, with the aborted count |
  | Raw findings/review | CONCERN and FAIL findings before combs, summed over reviewers |
  | Kept/review, Dropped/review, Undecided/review | After the comb chain |
  | Verdicts | Count of PASS, CONCERNS, FAIL, UNKNOWN |
  | Cost/review | Mean of known costs, with the number of reviews that had an unpriced stage |

- `--real-work` needs no `--set` and no `--recipe`; `--recipe` filters by name. It makes no calls.
- 431 and 433 read `recipe_review` records through `MetrologyStore.iter_records`: 431 by `run_id` and `step_name`, 433 by recipe.

### D11 — Shipped defaults do not change
Status: decided
- `P6`, `implement` and the other built-in pipelines keep `review-model: haiku-xhigh`. `haiku-solr-luna-opus` needs an OpenRouter key and `haiku-sol-luna-opus` needs Codex credits, so either as a default would fail the pre-run check for users without them.
- The P6 comment above `review-model` is updated to say a recipe name is accepted and to name the three shipped recipes.
- Making a recipe the default stays with #369, as a PM decision once real-work rows exist.

### Technology Choices
- No new dependencies. PyYAML and Pydantic as in 430.
- New config key `review.recipe_stage_slow_s`, default 1800, in the config defaults table. Of the 1,176 hand-run review and comb calls with a recorded duration, the median is 66 s, the 99th percentile 1,564 s and the longest 2,762 s.
- **Non-functional.**
  - Stage calls are sequential awaits of the existing review call. The slow-stage warning is one timer per stage call, cancelled when the call returns. File and git work in the runner goes through `asyncio.to_thread`, as the review action's saves do. No load-test tier: no two model calls run at once.
  - **Record size.** The architecture's rule holds: findings stay inline, raw output goes to the `REVIEWS` sidecar. A record holds one recipe's stages. 430's run records, which hold every config's findings for a case run, average 107 KB and peak at 253 KB in the dev store (54 records), so a recipe record is well under that.
  - **Record count.** One record per recipe review executed, not per stage: a review step writes one record per round, bounded by the loop's `max-revisions`. The store reads every file on every query, and this count grows with ordinary use at the rate review files already do.
  - **Cost.** Recording adds no model call. A recipe's spend is its stages' spend, counted under the pipeline cap (D9).

### Patterns and Conventions
- `AliasRef` and `RecipeRef` are two dataclasses of one union; callers `match` on the type. No string test decides which path runs.
- Frontmatter key names (`aiRecipe`, `recipeComplete`) are constants in `review/persistence.py`.
- Record id prefix: `rrev-`.

## Implementation Details

### Migration Plan

Consumers are from an import search of `src/` and `tests/`.

| Moved | From | To | Consumers updated |
|---|---|---|---|
| `Recipe`, `RequiredStage`, `load_recipe`, `load_recipes`, `resolve_recipe`, `required_stages`, `RecipeError` | `benchmark/recall/recipe.py` | `recipes/recipe.py`, `recipe_search.py` | `label_candidates.py`, `report_build.py`, `run_plan.py`, `scoring.py`; `benchmark_recall_label.py`, `benchmark_recall_report.py`, `benchmark_recall_run.py` (these three pass the benchmark search directories); in `tests/benchmark/recall/`: `stage_support.py`, `test_leak_check.py`, `test_recipe.py`, `test_report_render.py`, `test_reproduce_results.py`, `test_run_end_to_end.py`, `test_run_loop_resume.py`, `test_run_loop.py`, `test_run_plan_expand.py`, `test_run_plan.py`, `test_scoring_metrics.py`, `test_scoring_outputs.py`, `test_scoring_paired.py`, `test_stage_identity.py`, `test_stage_runner.py` |
| `render_findings`, `run_comb_stage`, `COMB_ALLOWED_TOOLS`, `ReviewCall`, `StageModel` | `benchmark/recall/stage_command.py` | `recipes/comb_call.py` | `benchmark_recall_stage.py`, `stage_command.py` (keeps the file I/O helpers), `test_stage_command.py` |
| `finding_id_at`, `FINDING_ID_PREFIX` | `benchmark/recall/review_output.py` | `recipes/comb_call.py` | `review_output.py`, `hand_run_combs.py`, `stage_command.py`, `stage_ingest.py` |
| Pure part of `live_stage_config` | `benchmark/recall/stage_identity.py` | `recipes/stage_config.py` | `stage_identity.py`, `test_stage_identity.py` |
| `parse_decisions` and its types | `benchmark/recall/decisions.py` | `recipes/decisions.py` | `hand_run_combs.py`, `stage_command.py`, `stage_ingest.py`, `test_decisions.py` |
| `SCORED_SEVERITIES` | `benchmark/recall/scoring.py` | `review/models.py` | `scoring.py`, `label_candidates.py` |
| Three recipe files | `user/reference/review-recall-recipes/` | `src/squadron/data/recipes/` | runbook paths; package data in `pyproject.toml` if data files are listed there |

- `RECIPES_DIR` stays in `benchmark/recall/`, and the six other recipe files do not move.
- Imports are changed at the consumers; no re-export shims are left behind.
- Behavior check: `tests/benchmark/recall/` and `tests/cli/test_benchmark_recall_*.py` pass with only import and path edits, and the 430 walkthrough step 3 report (hand-run table) prints the same rows.

### API Contracts

No new command or flag except `report --real-work`.

| Surface | Accepts | Notes |
|---|---|---|
| Pipeline param `review-model: <name>` | alias or recipe name | Unchanged YAML |
| Step `review: { template: code, model: <name> }` | alias or recipe name | |
| `sq review code\|slice\|tasks\|arch ... --model <name>` (and `-p review-model=<name>`) | alias or recipe name | `--profile` with a recipe is refused |
| `sq review ... --max N` | recipe name as reviewer | The revise loop builds the same pipeline with `review-model` |
| `sq benchmark recall report --real-work [--recipe NAME]` | | D10 |

- `sq review --output json` prints the merged `ReviewResult.to_dict()` for a recipe review, the same shape a single-model review prints.
- Slash commands and prompt-only renderings run `sq review <template> <slice> --model <name>` (`prompt_renderer._render_review`), so they get recipe reviews through the CLI with no change of their own.

### Database / Storage Schema

`RecipeReview`, record type `recipe_review`, id `rrev-<utc timestamp>-<8 hex>` (one per review executed; a revise round is a new record). `schema_version` stays 1.

| Field | Content |
|---|---|
| `project_id` | The project reviewed |
| `recipe`, `recipe_hash` | Name, and sha256 of the recipe's canonical content |
| `template`, `template_hash` | The review template and its content hash |
| `run_id`, `step_name`, `iteration` | The pipeline run, step and loop round; `null` from `sq review`. This includes prompt-only pipelines (slash commands), which run `sq review` as a shell command: their recipe records carry no run linkage, and 431 cannot join them to a run. Passing run context into `sq review` is not built here; only executor-run pipelines get run-keyed records |
| `review_file` | Path of the saved review, `null` when not saved |
| `planned` | `list[StageConfig]`: every stage the recipe defines, resolved before the first call (D10's row key) |
| `stages` | `list[RecipeStage]`, in execution order; stages that did not run are absent |
| `verdict`, `complete`, `aborted` | The merged verdict; whether every stage was `ok`; the reason when the recipe did not finish (D5), else `null` |
| `created` | UTC |

`RecipeStage`: `kind` (`StageKind`), `reviewer` (the alias heading the chain), `alias`, `config` (`StageConfig`), `effort_sent`, `findings` (review stages: every finding, as `RecallFinding`), `decisions` (comb stages: `CombDecision` per reviewer finding id, as 430's comb entries hold them), `duplicate_decisions`, `unknown_ids`, `usage` (`StageUsage`), `outcome` (`StageOutcome`), `outcome_reason`, `raw_ref` (sha256 in the `REVIEWS` sidecar).

`StageEntry` is not reused whole: it requires a case set and a leak verdict, and a real review has neither.

## Integration Points

### Provides to Other Slices
- **431:** `recipe_review` records keyed by `run_id`, `step_name` and `iteration`; the recipe name and record id in each review `ActionResult`'s metadata; `aiRecipe` in review frontmatter.
- **433:** `recipe_review` records, and the real-work table as its named source report.
- **#369:** the default change becomes a one-line pipeline edit.
- **435 and 436:** they add reviewer shapes this slice does not build: a repeat count per reviewer, a dedupe stage over several reviewers' findings, a vote filter, a focus (rules file) per reviewer, and a sequential reviewer that reads earlier stages' findings. The runner walks the stage list the recipe model produces (as 430's `required_stages` does) rather than hard-coding "each reviewer, then its comb chain", and the recipe loader refuses unknown keys, so each new shape is a new stage kind and a new recipe key, not a rewrite of the runner, the merge or the record schema. Nothing for them is built here.

The plan's 431 and 433 entries now list 434 as a dependency with these contracts.

### Consumes from Other Slices
- 430's recipe model, comb template, comb call, decisions parser and stage payloads. They are moved, not copied, so a later change to the comb prompt reaches both the benchmark and pipelines, and its template hash separates the rows.
- 425's content sidecars, for raw stage output.
- Review step dispatch (`ReviewAction`, `run_review_with_profile`). A change to a provider's error types surfaces as `harness_failure` stages, which are counted and reported.

## Success Criteria

### Functional Requirements
- `review-model: haiku-solr-luna-opus` in a pipeline, `model: haiku-solr-luna-opus` on a review step, and `sq review code <n> --model haiku-solr-luna-opus` each run the recipe. The same three with `haiku-xhigh` behave as before this slice, in squadron's own checkout too, where a benchmark recipe file of that name exists outside the production search (existing review tests pass unchanged).
- A name that is neither an alias nor a recipe fails before any model call: `sq run` at the pre-run check with no step started, `sq review` with exit 1. The message lists close alias matches and the known recipe names. A name that is both fails with the collision message.
- Each of these is refused before any model call, naming the recipe: an unknown member alias, `pool: true`, a judge template, combs with no diff, an explicit profile.
- For a two-reviewer, two-comb recipe on a fixture diff with scripted model outputs:
  - the merged findings are exactly the kept findings (D5), plus the uncombed NOTE findings; a finding the first comb left undecided is in the merged set and was not sent to the second comb;
  - the verdict is FAIL, CONCERNS or PASS by `verdict_from_findings` on those findings, including PASS when every CONCERN was dropped while a reviewer stated CONCERNS;
  - each comb is given the file list `assert_reviewable_scope` returned;
  - one review file is written, with the stage table and no dropped finding.
- A revise loop with a recipe reviewer runs every stage in each round (asserted by stage call counts over two rounds).
- Failed stages, each asserting the outcome, the WARNING log record, the review file's stage table and the `recipe_review` record:
  - one reviewer fails and the other keeps a CONCERN: the review succeeds with FAIL and `complete: false`; in a loop whose last round ends this way, `accept_if: review.concerns_or_better` does not accept it and the exhaust path runs;
  - one reviewer fails and nothing is kept: verdict UNKNOWN, the pipeline action fails, `sq review` exits 1, and the review file and record exist;
  - every reviewer fails: the same;
  - a comb fails: its input is kept and marked not combed, the next comb runs, `complete: false`;
  - a comb decides only some findings: the rest are kept as undecided, `complete: true`;
  - a comb repeats an id and names an unknown one: the first decision wins, both counts are in the record and the WARNING.
- Other failures, each asserting its log record and its effect from D5's second table: an uncomputable diff range (no model call, nothing recorded), an unexpected exception in a stage (aborted record, finished stages' spend stamped, no review file), a cancellation mid-recipe (aborted record written, cancellation propagates), and a stage that outlasts `review.recipe_stage_slow_s` (one WARNING, the call finishes).
- A `recipe_review` record is written for a pipeline review and for a `sq review` review, with every stage's findings, decisions, usage and identity. A `MetrologyStoreError` from the write logs at ERROR and the review still returns its result.
- The pipeline step's usage record carries the summed cost, and a run with `--max-cost` below it stops after the step with the existing cap error. With one unpriced stage, the stamped cost is the priced stages' sum and a WARNING names the unpriced stage.
- `sq benchmark recall report --real-work` shows one row per recipe and stage identity from those records. Two records of one recipe whose reviewer alias sent different efforts are one row, flagged "effort differs"; a complete, an incomplete and an aborted review of one configuration are one row.

### Technical Requirements
- `ruff format`, `ruff check` and `pyright` (zero errors) pass. Tests for `recipes/`, the review action, the review CLI, classification, and `tests/benchmark/recall/` pass.
- Tests run no model: the review call and the record sink are injected.
- `recipes/` imports nothing from `pipeline/`, `cli/` or `benchmark/`, and neither `review/` nor `metrology/` imports `recipes/` (an import test asserts both).
- `run_review_with_profile`, the `comb` template, the `Recipe` schema and `metrology/review_ingest.py` have no behavior change.
- README or the pipelines doc that describes `review-model` says a recipe name is accepted, where recipes are searched, and how to add one. CHANGELOG has a user-facing bullet.

### Integration Requirements
- After the move, every 430 command works by recipe name from squadron's checkout, and its tests pass with import and path edits only.

### Verification Walkthrough

Draft; refined after implementation. Run from the squadron checkout with `uv run sq` until a release carries the change. Steps 1–3 and 6 make no model call.

1. **Recipes resolve by name.**
   ```bash
   ls src/squadron/data/recipes/ project-documents/user/reference/review-recall-recipes/
   uv run sq benchmark recall report --set real-bugs-original --runs 1 --recipe haiku-sol-opus --recipe haiku-xhigh
   ```
   The three shipped recipes are in `data/recipes/`, the other six are where they were, and the report prints the same haiku-sol-opus row as 430's walkthrough step 4 (`8/14 | 57%`) and a haiku-xhigh row.

2. **Bad names fail before the run.**
   ```bash
   uv run sq review code --diff HEAD~1 --model no-such-name --no-save
   uv run sq run P6 434 -p review-model=no-such-name
   uv run sq review slice 430 --model haiku-solr-luna-opus --no-save
   ```
   Each prints an error and exits non-zero with no model call: unknown name (with the known recipes listed), the same at the pipeline pre-run check with no step started, combs refused without a diff.

3. **A single alias is unchanged.** `uv run sq review code --diff HEAD~1 --model haiku-xhigh --no-save -v` runs one review with today's output, from squadron's checkout.

4. **A recipe review from the CLI (live, four to six calls).** In a small fixture repo with one commit that adds a defect:
   ```bash
   uv run sq review code --diff HEAD~1 --model haiku-solr-luna-opus -v
   uv run sq review code --diff HEAD~1 --model haiku-solr-luna-opus --no-save --output json > /tmp/recipe-review.json
   ```
   The first prints the stage table (two reviews, up to four combs) with findings, kept, dropped and cost per stage, then the merged verdict. The second writes the merged review's JSON document from stdout.

5. **A recipe review in a revise loop (live).** In the same fixture, registered with cf:
   ```bash
   uv run sq review code 100 --model haiku-solr-luna-opus --max 1
   ```
   One review file is written with `aiModel: haiku-solr-luna-opus`, `aiRecipe: true` and the stage table. If the verdict is not PASS, the reviser runs once and the recipe runs again in full. `sq runs` shows the review step's cost as the recipe total.

6. **The records.**
   ```bash
   uv run sq benchmark recall report --real-work
   ```
   One `haiku-solr-luna-opus` row with the reviews from steps 4 and 5, their raw, kept and dropped counts and cost per review.

7. **A failed stage.** With `OPENROUTER_API_KEY` unset, repeat step 4's first command. Both reviewers' aliases are checked first; the haiku-xhigh stage runs, the sol-r stage and the luna-r combs are recorded as failed with the provider's reason, and the result follows D5: FAIL with `complete: false` when haiku-xhigh's findings are kept, otherwise UNKNOWN and exit 1. The review file names the failed stages either way.

## Risk Assessment

### Technical Risks
- **An incomplete recipe's verdict (D5).** A partial review that passes would clear a gate with half the review. A partial review that always fails would make pipelines stop on any provider hiccup.
- **Review duration.** A two-reviewer, two-comb recipe is six sequential calls where there was one.

### Mitigation Strategies
- D5's rule is two branches (incomplete with findings kept gives FAIL, so it keeps the loop revising but is never accepted; incomplete with nothing kept gives UNKNOWN and fails) with a test per row of its table, and the stage table makes the reason readable in the review file.
- Duration is visible per stage in the record, so the case for #372 is measured, not guessed.

## Implementation Notes

### Development Approach
1. Move the recipe model, search, comb call, `finding_id_at`, decisions parser and `SCORED_SEVERITIES`; move the three shipped recipe files; update 430's imports and tests. Nothing new yet, and all recall tests pass.
2. `classify_review_model` and its refusals, wired into `sq review`, the pre-run check and the loader.
3. `recipe_runner` and `recipe_merge` with scripted review calls: kept findings, verdict, the slow-stage warning, every row of both D5 tables.
4. Review file frontmatter and stage table.
5. `RecipeReview` payload, sink, and the writes from the action and the CLI; usage stamping (D9).
6. `ReviewAction` and `_run_review_command` call the runner; revise-loop test.
7. `report --real-work`.
8. Docs, CHANGELOG, P6 comment, runbook paths; live walkthrough steps 4, 5 and 7.

Testing: unit tests per module with an injected review call and sink. One end-to-end test drives `sq review code` and one drives a review step inside a loop, both on a temp git repo with scripted model outputs.

### Special Considerations
- `sol-r`, `luna-r` and other OpenRouter aliases need their key in the environment, as any `sq review` with those aliases does. Nothing new reads `.env`.
- The comb asks for read tools only (`COMB_ALLOWED_TOOLS`), passed through the same `allowed_tools` path a single-model review uses. How far that is enforced is the profile's, as in D4: this slice claims no tool restriction beyond what a single-model review on the comb's alias already gets.
