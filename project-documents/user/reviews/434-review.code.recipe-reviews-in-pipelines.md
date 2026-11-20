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
reviewedSha: 0ca18024ea692adbc4a120342818397883bd5f82
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 37
diffTruncated: false
effort: xhigh
turns: 38
promptTokens: 4201225
cachedTokens: 3932454
cacheWriteTokens: 268737
completionTokens: 60309
durationSeconds: 274.4
costUsd: 0.702569
costBasis: provider
runId: run-20261119-p6-4d95f013
squadronVersion: 0.24.34
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Pool selection's state write moved off the event loop and can race other writers"
    location: "src/squadron/pipeline/actions/review.py:308"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "Cancellation during the review-file save leaves no aborted record"
    location: "src/squadron/recipes/recipe_review.py:211"
  - id: F003
    severity: concern
    category: performance-resource
    summary: "The CLI save step runs synchronous file and git work inside an `async def`"
    location: "src/squadron/cli/commands/review_recipe.py:95"
  - id: F004
    severity: concern
    category: type-contract-debt
    summary: "Stage fields and review-call options are untyped, so pyright strict cannot catch mismatches"
    location: "src/squadron/recipes/recipe_runner.py:145"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "Recipe classification re-derives the model cascade outside the resolver"
    location: "src/squadron/pipeline/actions/review.py:395"
  - id: F006
    severity: note
    category: security-hygiene
    summary: "Recipe names are joined into file paths without validation"
    location: "src/squadron/recipes/recipe_search.py:43"
  - id: F007
    severity: pass
    category: correctness
    summary: "New required `cwd` arguments are passed at every call site"
    location: "src/squadron/cli/commands/run.py:380"
  - id: F008
    severity: pass
    category: correctness
    summary: "Duplicate recipe reviewers are rejected at load"
    location: "src/squadron/recipes/recipe.py:45"
---

# Review: code — slice 434

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 35 successful tool call(s) of 37 made; 380620 of 380620 diff characters reached the model

## Findings

### [CONCERN] Pool selection's state write moved off the event loop and can race other writers

`_review` now resolves the model inside `asyncio.to_thread` (line 308). For a `pool:` review model, that call reaches `_resolve_alias` (line 420), then `resolver.resolve_full`, then `_on_pool_selection`. The CLI wires that callback to `state_mgr.log_pool_selection` (run.py:422). `log_pool_selection` is a load, append, save cycle on the run's state file (state.py:653-672). `heartbeat` (state.py:495-501) writes the same run file through `_write_progress` from the loop.

Before this change, both writers ran on the loop thread and could not interleave. Now the step awaits a worker thread, so a heartbeat can load the file between the pool write's load and save, and one of the two updates can be lost. The project's concurrency rule requires reviewing any state an executor touches. The comment at line 306 mentions only recipe and alias file reads. No test covers this interleaving.

Fix: keep `resolve_full` on the loop and move only the file-reading classification into the thread, or put the state write under a lock.

### [CONCERN] Cancellation during the review-file save leaves no aborted record

The `try` at lines 192–210 covers the run and the merge only. `_save_then_record` (line 211; body at 221–231) runs outside that `try`. Its `except Exception` (line 227) does not catch `asyncio.CancelledError`. A cancel during the save therefore propagates with no record, even though the module docstring promises an aborted record on cancellation. The final `writer.write` at lines 212–215 has the same gap.

The cancellation tests (`test_cancellation_*`, `test_a_real_cancellation_writes_the_aborted_record`) cancel only during a stage call.

Fix: extend the cancellation handling to the save and the final write, and add a test that cancels during the save.

### [CONCERN] The CLI save step runs synchronous file and git work inside an `async def`

`save` is declared `async def` but calls `review.persist.run(result)` synchronously, which reaches `save_review_result`. The pipeline path runs the same save via `asyncio.to_thread`, with a comment that it can run a git subprocess and that no blocking call belongs on the loop inside an `async def` (pipeline/actions/review.py:743-751). The CLI loop has no concurrent coroutine, so practical starvation is limited, but the project rule still applies.

Fix: `await asyncio.to_thread(review.persist.run, result)`.

### [CONCERN] Stage fields and review-call options are untyped, so pyright strict cannot catch mismatches

`_stage` takes `**fields: Any` and forwards them to `RecipeStageResult(**defaults)`. A misspelled or mistyped field such as `not_combd=` passes strict type checking and fails only at runtime. The review call is typed `ReviewCall = Callable[..., Awaitable[ReviewResult]]` in `recipes/comb_call.py`, and `RecipeReviewCall.options` is a `Mapping[str, Any]` splatted into it.

The CLI and pipeline pass different option sets (`no_tools` and `verbosity` versus `allowed_tools` and `pricing_warned`). Both match `run_review_with_profile` today (review_client.py:140-157), but nothing checks that. The test fake accepts `**kwargs`, so a mismatch would not fail any test.

Fix: give `_stage` explicit keyword parameters, and type the review call with a Protocol that mirrors `run_review_with_profile`'s keyword-only signature.

### [CONCERN] Recipe classification re-derives the model cascade outside the resolver

`_classify_recipe` picks the winning candidate itself: `next((c for c in candidates if c is not None), template.model)` at line 405. `_resolve_alias` (lines 420–444) then asks `resolve_full`, which applies its own cascade. The docstring of `ModelResolver.cascade_candidates` (resolver.py:124-138) says the cascade ordering should be a single source of truth in the resolver.

The two copies agree today: both fall back to `template.model` only when the cascade is empty. A new tier or a changed fallback in the resolver would not reach the classifier. A name could then be classified as a recipe on one path and resolved as an alias on the other.

Fix: add a resolver method that returns the winning candidate, and call it from both places.

### [NOTE] Recipe names are joined into file paths without validation

`_matches` builds `d / f"{name}.yaml"` for any name. `find_recipe` (line 85) receives every review model string and does not apply `is_path_ref`. A name containing `..` or a separator can therefore load a YAML file outside the search directories, provided it validates and its `name` equals its stem. The names come from repo-owned pipeline YAML or the CLI, so the impact is small. Rejecting names that contain a separator or `..` before the lookup would close it.

### [PASS] New required `cwd` arguments are passed at every call site

I checked every call to `validate_pipeline`, `classify_pipeline`, `classify_for_run` and `render_step_instructions` under `src/`. Each passes `cwd`: run.py, review_revise.py, run_session.py and prompt_renderer.py. `assert_reviewable_scope` returns `list[str]` (git_utils.py:547-551), which matches the new `changed_files` assignments in both review paths. The executor's `services` threading has no leftover `usage_capture=` or `spend=` keyword arguments.

### [PASS] Duplicate recipe reviewers are rejected at load

`Recipe._checks` rejects duplicate reviewers, so the reviewer-keyed `dict(zip(required_stages(...)))` in `run_recipe` cannot silently collapse stages.

### Run Digest

- Response length: 11095 chars
- Response is newline-free: no
- Tool calls made: 37
- Tool calls failed: 2
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 38
- Tokens — prompt / cached / cache write / completion / reasoning: 4201225 / 3932454 / 268737 / 60309 / not computed
- Duration: 274.4 s
- Cost: $0.70 (provider)
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
