---
docType: review
layer: project
reviewType: code
slice: recipe-reviews-in-pipelines
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261119
dateUpdated: 20261119
reviewedSha: 63a58668880fee67312a1c58b97117075a89256b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
diffTruncated: false
effort: xhigh
turns: 25
promptTokens: 1730484
cachedTokens: 1505564
cacheWriteTokens: 224904
completionTokens: 67464
durationSeconds: 287.7
costUsd: 0.541362
costBasis: provider
runId: run-20261119-p6-4d95f013
squadronVersion: 0.24.34
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Tool-less settings are not applied to every recipe stage"
    location: "src/squadron/pipeline/actions/review.py:320-334"
  - id: F002
    severity: concern
    category: correctness
    summary: "Failed stages discard the spend the provider reported"
    location: "src/squadron/recipes/recipe_runner.py:194-197"
  - id: F003
    severity: concern
    category: performance-resource
    summary: "Alias-registry file reads run on the event loop inside async recipe code"
    location: "src/squadron/recipes/recipe_runner.py:179"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "Recipe-name classification is repeated at five sites with different inputs"
    location: "src/squadron/pipeline/classification.py#_review_recipe_row"
  - id: F005
    severity: concern
    category: test-debt
    summary: "Failure-mode tests miss the cases where the new code can go wrong"
    location: "tests/recipes/test_recipe_runner.py"
  - id: F006
    severity: note
    category: correctness
    summary: "`cwd` defaults to \".\" on the pipeline validation entry points"
    location: "src/squadron/pipeline/loader.py:354"
  - id: F007
    severity: note
    category: other
    summary: "Checked and sound"
    location: "src/squadron/review/git_utils.py:547"
---

# Review: code — slice 434

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 23 successful tool call(s) of 24 made; 316897 of 316897 diff characters reached the model

## Findings

### [CONCERN] Tool-less settings are not applied to every recipe stage

The `allowed_tools == []` refusal from #306 only runs for single-model steps: the guard at line 323 is `isinstance(model, _AliasModel)`. A recipe step with `allowed_tools: []` skips `tool_isolation_failure` entirely. A reviewer alias whose provider brings its own tools will run, with no refusal and no log.

The comb stages never see the step's tool setting either. `call_comb` hard-codes `allowed_tools=list(COMB_ALLOWED_TOOLS)` (src/squadron/recipes/comb_call.py:80), and `_run_comb` (src/squadron/recipes/recipe_runner.py:247) passes no caller options. The CLI's `--no-tools` reaches reviewer stages through `recipe_review_request` options, but not comb stages. A recipe run with `--no-tools` therefore still gives combs `read_file`, `list_files` and `grep`. No test covers either case.

Fix: run `tool_isolation_failure` for each member alias, and thread `no_tools` and `allowed_tools` into `call_comb`, or refuse the combination explicitly.

### [CONCERN] Failed stages discard the spend the provider reported

`ProviderError` carries what a failed call cost: `telemetry`, `duration_seconds`, and the resolved `cost_usd` and `cost_basis` (src/squadron/providers/errors.py, class docstring). The single-model path records that through `capture.record_from_error` in `_run_part`. The recipe path catches the error at line 194 (reviewers) and line 258 (combs) and records `HARNESS_FAILURE` with no result, so `usage` stays `StageUsage()`.

Consequences:
- The failed call's tokens and cost are missing from the step's usage record, from the run's cost cap (`services.spend.add`), and from the `recipe_review` record.
- `made_call` is true for every `HARNESS_FAILURE`, so `recipe_usage_record` counts a failed stage with no cost as "unpriced". That logs a WARNING and labels the step's cost a floor, even when nothing was spent. The single-model path treats a failure without telemetry as no spend, not as unpriced.
- `provider_error()` in tests/recipes/support.py builds a bare `ProviderError`, so no test covers a failed stage that carries telemetry.

Fix: derive `StageUsage` from the exception in the recipe stage builder, and keep "no telemetry" distinct from "unpriced".

### [CONCERN] Alias-registry file reads run on the event loop inside async recipe code

`_run_reviewer` and `_run_comb` are `async def`, and both call `stage_model(...)` (lines 179 and 252). `stage_model` in src/squadron/recipes/stage_config.py:66 reads the alias registry through `resolve_model_alias` and the `model_*` readers. `get_all_aliases()` (src/squadron/models/aliases.py:217) parses the shipped `models.toml` and the user's `models.toml` on every call, with no cache. That is several file reads and TOML parses per stage, all on the loop.

The same problem is in `_review` at src/squadron/pipeline/actions/review.py:308. It calls `validate_recipe_review` directly, which reaches `require_known_model` and `get_all_aliases()` for each member. The same method moved `_resolve_model` (line 276) to `asyncio.to_thread` for exactly this reason. The project rule for async functions requires sync work to stay under 1 ms.

Fix: `plan_recipe` already resolves the same aliases off the loop. Carry its resolved `StageModel`s into `RecipeReviewCall` and stop re-resolving per stage.

### [CONCERN] Recipe-name classification is repeated at five sites with different inputs

"Is this review model a recipe?" is decided in five places:
- `_review_recipe_row` (pipeline/classification.py)
- `_validate_review_model` (pipeline/loader.py)
- `_is_recipe_name` (pipeline/prompt_renderer.py)
- `_classify_recipe` (pipeline/actions/review.py)
- `_classify_or_exit` (cli/commands/review.py)

Each calls `classify_review_model` with `production_recipe_dirs(...)` and then runs `validate_recipe_review` or `check_recipe_members` with its own inputs. The `profile_source` argument differs by site: classification uses `_action_profile_source(...)`, the action uses `review_profile_source(...)`, the loader passes `False`, and the renderer passes `True`. They agree on the cases the tests cover, but a change to how recipes are found or refused has to be made five times, and the sites can drift.

Fix: one entry point, for example `resolve_review_model(...)` in recipes/model_ref.py, that each site calls with its own inputs.

### [CONCERN] Failure-mode tests miss the cases where the new code can go wrong

The recipe tests raise `ProviderError` as a bare exception. They do not cover:
- a failed stage that carries telemetry or cost (finding 2);
- a recipe step with `allowed_tools: []` or `--no-tools` (finding 1);
- a recipe run that is actually cancelled. The cancellation test in tests/recipes/test_recipe_review.py uses `asyncio.CancelledError` raised from a scripted call, which covers the path but not a real cancellation of a running step.

The project rule also requires a load test for code on network paths. `tests/load/` has no test for the recipe runner, and no test for the review action either. Add regression tests for the first two gaps before fixing findings 1 and 2.

### [NOTE] `cwd` defaults to "." on the pipeline validation entry points

`validate_pipeline(..., cwd: str = ".")` and `classify_pipeline(..., cwd: str = ".")` (src/squadron/pipeline/classification.py:643) silently search the process directory for recipe names when a caller omits `cwd`. The slice's own test `test_recipe_is_found_in_the_run_cwd_not_the_process_cwd` guards against this failure. `render_step_instructions` has the same fallback at src/squadron/pipeline/prompt_renderer.py:667 (`cwd if cwd is not None else "."`).

Current callers are not wrong. `run_session.classify_for_run` passes `cwd`. The five `validate_pipeline` calls in src/squadron/cli/commands/run.py do not pass it, but `sq run` has no `--cwd` and runs in `os.getcwd()`. Per the "never silent fallback" rule, make `cwd` required on all three.

### [NOTE] Checked and sound

These checks came out clean:
- `assert_reviewable_scope` returns `list[str]`, so the `changed_files` plumbing is correct.
- `run_review_with_profile` accepts `verbosity`, `no_tools` and `pricing_warned` (src/squadron/review/review_client.py:140-157), so the recipe options bind.
- Every executor call site passes `services`, or the capture and sink accessors. No stale `usage_capture=` or `spend=` keywords remain.
- `DecisionParse.is_empty` is a property (src/squadron/recipes/decisions.py:49), so `answer.parsed.is_empty` is correct.
- No `_POOL_PREFIX` copies remain in `src/`. The note at project-documents/user/reviews/434-review.code.recipe-reviews-in-pipelines.md:176-178 is stale.

### Run Digest

- Response length: 9777 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 1730484 / 1505564 / 224904 / 67464 / not computed
- Duration: 287.7 s
- Cost: $0.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
