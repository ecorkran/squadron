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
reviewedSha: c87396f8e9a80e517ce128437603f9c550c175ac
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
diffTruncated: false
effort: xhigh
turns: 39
promptTokens: 5487076
cachedTokens: 5221302
cacheWriteTokens: 265726
completionTokens: 86218
durationSeconds: 384.3
costUsd: 0.810924
costBasis: provider
runId: run-20261119-p6-4d95f013
squadronVersion: 0.24.34
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Recipe lookup uses the process cwd at pre-run, but the revise loop executes in `--cwd`"
    location: "src/squadron/pipeline/classification.py:465"
  - id: F002
    severity: concern
    category: correctness
    summary: "A later part's abort drops the spend of the parts that already ran"
    location: "src/squadron/pipeline/actions/review.py:355-366"
  - id: F003
    severity: concern
    category: performance-resource
    summary: "New synchronous disk and config work runs inside async functions"
    location: "src/squadron/pipeline/actions/review.py#ReviewAction._classify_recipe"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "The CLI and pipeline recipe adapters duplicate plumbing"
    location: "src/squadron/cli/commands/review_recipe.py:39"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "`recipe_sink` is threaded through eight more executor signatures"
    location: "src/squadron/pipeline/executor.py#_execute_step_once"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "`stage_table` and `RealWorkRow.key` are dead code"
    location: "src/squadron/cli/commands/review_recipe.py:147"
  - id: F007
    severity: note
    category: performance-resource
    summary: "The recipe `review_code` path runs the git scope check twice"
    location: "src/squadron/cli/commands/review_recipe.py:76"
  - id: F008
    severity: note
    category: correctness
    summary: "`--json` is silently ignored with `--real-work`"
    location: "src/squadron/cli/commands/benchmark_recall_report.py#make_report_command"
  - id: F009
    severity: note
    category: performance-resource
    summary: "Recipe stage calls have no deadline; the slow-stage check only logs"
    location: "src/squadron/recipes/recipe_runner.py#_Run.timed"
  - id: F010
    severity: note
    category: correctness
    summary: "Recipe files whose name differs from the file stem are now refused everywhere"
    location: "src/squadron/recipes/recipe.py#load_recipe"
  - id: F011
    severity: note
    category: consistency-rot
    summary: "In-function imports in the loader have no stated reason"
    location: "src/squadron/pipeline/loader.py#_validate_review_model"
  - id: F012
    severity: note
    category: consistency-rot
    summary: "`POOL_PREFIX` is public now, but two private copies remain"
    location: "src/squadron/pipeline/executor.py:2499"
  - id: F013
    severity: note
    category: test-debt
    summary: "A test undoes all patches to get the real alias registry"
    location: "tests/recipes/test_model_ref.py#test_haiku_xhigh_is_an_alias_in_squadrons_own_checkout"
  - id: F014
    severity: note
    category: type-contract-debt
    summary: "Test code suppresses type errors instead of annotating"
    location: "tests/pipeline/actions/test_review_recipe.py#_stages"
  - id: F015
    severity: pass
    category: consistency-rot
    summary: "Import boundary and renamed symbols are covered"
    location: "tests/recipes/test_import_boundary.py"
---

# Review: code — slice 434

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 37 successful tool call(s) of 38 made; 297136 of 297136 diff characters reached the model

## Findings

### [CONCERN] Recipe lookup uses the process cwd at pre-run, but the revise loop executes in `--cwd`

Pre-run classification and validation resolve recipe names with `Path.cwd()`: `classification.py:465`, `loader.py:493` and `prompt_renderer.py:253`. The executor resolves them from the step's cwd (`pipeline/actions/review.py:408`). The `--max` revise loop shows the mismatch. `run_review_revise` runs `classify_for_run` with no cwd (`review_revise.py:236`), then calls `execute_pipeline(..., cwd=cwd)` with the `--cwd` value (`review_revise.py:259`). With `sq review code N --max K --cwd <other repo> --model <recipe>`, a recipe that exists only in that repo fails the pre-run check with "unknown model alias … Known recipes: …" and the loop exits with `EXIT_RUN_FAILED`. The reverse also happens: a same-named recipe in the process cwd gets classified instead. `test_max_builds_the_loop_with_the_recipe_as_reviewer` patches `run_review_revise`, so no test covers this path. Fix: pass the run's cwd into `classify_pipeline`, `validate_pipeline` and `_is_recipe_name`, and use it at all three sites.

### [CONCERN] A later part's abort drops the spend of the parts that already ran

`_review` collects one `ActionResult` per part and returns them only after the loop. When `_run_part` raises `RecipePartAborted` on part k, the earlier results are discarded. `execute` stamps only the aborted part's record (`review.py:226-231`). The executor charges the run cap only from the returned step result (`executor.py:1234`, `run_spend.py:117`). So the spend of parts 1 through k-1 never reaches the cap. `_PartProviderFailure` already has this gap, but a recipe part runs every stage, so the diff makes it material. Fix: carry the completed parts' usage on the exception, or sum it into the failure result.

### [CONCERN] New synchronous disk and config work runs inside async functions

The project rule requires sync work inside an `async def` to be bounded under 1 ms, and reviewers must verify it. The new code does unbounded work on the event loop:
- `_classify_recipe` (called from `_resolve_model` on every review step, alias or recipe) runs `classify_review_model`, which reads recipe files, parses YAML, and loads the alias registry.
- `run_recipe_part` calls `get_positive_int_config` (`pipeline/actions/review_recipe.py:155`).
- `run_recipe_review` calls `planned_stages` (`recipes/recipe_review.py:133`), which calls `builtin_template_hash`, which parses a YAML template.
- `run_recipe` repeats `planned_stages` (`recipes/recipe_runner.py:128`) and loads `builtin_template(COMB)` (`recipe_runner.py:132`).

Existing `_review` code already does sync work (`load_all_templates`, the `assert_reviewable_scope` git call), so this extends a pattern rather than introducing it. Fix: resolve the plan and config once in `asyncio.to_thread`, or move the resolution out of the async path.

### [CONCERN] The CLI and pipeline recipe adapters duplicate plumbing

Two adapters repeat the same logic:
- Constants: `RECORD_NOT_WRITTEN` and `_INPUT_FILE_KEYS` appear at `cli/commands/review_recipe.py:39-40` and `pipeline/actions/review_recipe.py:37-38`.
- Request construction: `_request` (`review_recipe.py:85`) and `run_recipe_part` (`pipeline/actions/review_recipe.py:138-160`) both build `RecipeReviewCall` with `run_review_with_profile` and `call_comb`, then `RecipeReviewRequest` with `input_files` and `slow_after_s`.
- Record context: `RecipeRecordContext(project_id=lambda: derive_project_id(cwd), clock=lambda: datetime.now(UTC))` appears at `review_recipe.py:117` and in `_record_context` (`pipeline/actions/review_recipe.py:111`).
- "Made a call" predicate: `_made_a_call` (`pipeline/actions/review_recipe.py:69`) and `real_work._called` (`benchmark/recall/real_work.py:86`) apply the same rule to two stage types.
- Usage summing: the loop in `recipe_usage_record` (`pipeline/actions/review_recipe.py:73`) repeats the one in `recipes/recipe_merge.merge_recipe`.

The project rule against duplicated logic applies. Fix: one request builder in `recipes/recipe_review.py`, and one `made_call` property on the stage types.

### [CONCERN] `recipe_sink` is threaded through eight more executor signatures

`recipe_sink` is passed beside `usage_capture` and `spend` through `_execute_step`, `_execute_step_once`, `_execute_loop_step`, `_execute_loop_body`, `_resolve_final_notes`, `_run_loop_rounds`, `_execute_each_step` and `_execute_fan_out_step`, and it is added to `ActionContext`. The review-rules file names parameter accumulation as an OCP violation. Fix: bundle the run-scoped services (`usage_capture`, `recipe_sink`, `spend`) into one object and pass that once.

### [NOTE] `stage_table` and `RealWorkRow.key` are dead code

`stage_table` has no callers in `src` or `tests`. The `-v` path reads `result.recipe.stage_section` directly (`cli/commands/review.py:859-860`). `RealWorkRow.key` (`benchmark/recall/real_work.py:48`) is also unused. Remove both.

### [NOTE] The recipe `review_code` path runs the git scope check twice

`review_code` runs `assert_reviewable_scope` at `review.py:1474` and discards the file list. `_changed_files` (`review_recipe.py:76-82`) runs the same git diff again for the recipe path. Pass the list through from the pre-flight call.

### [NOTE] `--json` is silently ignored with `--real-work`

The `real_work` branch calls `run_real_work_report` and never reads `as_json`, so `--json --real-work` prints text with no warning. Either honor the flag or reject the combination.

### [NOTE] Recipe stage calls have no deadline; the slow-stage check only logs

`timed` schedules one WARNING after `slow_after_s` (default 1800 s) and never cancels the call. A hung provider call stalls the step, and the run, until the provider's own timeout fires. The design chose warn-only (D3), so this is a choice to confirm, not a defect. Confirm that the provider path has a timeout, or state the bound in the docs.

### [NOTE] Recipe files whose name differs from the file stem are now refused everywhere

`load_recipe` now rejects `name != path.stem` for every entry point, including explicit `--recipe path/to/file.yaml` in `sq benchmark recall`, which accepted those before. `test_recipe.py` changed its fixture to match. Confirm this is intended and that the slice design records it.

### [NOTE] In-function imports in the loader have no stated reason

`_validate_review_model` imports `squadron.recipes.model_ref` and `recipe_search` inside the function. The module already imports `squadron.pipeline.actions.gate` at top level, and nothing in the diff explains the deferral. If a cycle requires it, name the cycle in a comment. Otherwise move the imports to the top.

### [NOTE] `POOL_PREFIX` is public now, but two private copies remain

The diff makes `POOL_PREFIX` public in `resolver.py` and uses it in classification and the review action. `executor.py:2499` and `pipeline/steps/fan_out.py:12` still define `_POOL_PREFIX`. Consolidate them while this constant is being touched.

### [NOTE] A test undoes all patches to get the real alias registry

`monkeypatch.undo()` removes the autouse fixture's alias patch as well, so the test depends on fixture order. Load the real registry through a fixture that restores it, rather than undoing everything.

### [NOTE] Test code suppresses type errors instead of annotating

`_stages` has no return annotation and is suppressed with `# type: ignore[no-untyped-def]`. Several assertions use `# type: ignore[index]` on `result.metadata[...]`. The project requires strict pyright over tests and type-hinted signatures. Annotate the return type and narrow the metadata values.

### [PASS] Import boundary and renamed symbols are covered

The new test enforces that `recipes/` imports nothing from `pipeline`, `cli` or `benchmark`, and that `review/` and `metrology/` never import `recipes/`. I also grepped the tree: no code still imports the moved names (`benchmark.recall.recipe`, `benchmark.recall.decisions`, `stage_command`'s moved symbols, `_POOL_PREFIX` from the resolver, `_verdict_from_findings`).

### Run Digest

- Response length: 13468 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 39
- Tokens — prompt / cached / cache write / completion / reasoning: 5487076 / 5221302 / 265726 / 86218 / not computed
- Duration: 384.3 s
- Cost: $0.81 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
