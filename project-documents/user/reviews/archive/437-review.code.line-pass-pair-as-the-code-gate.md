---
docType: review
layer: project
reviewType: code
slice: line-pass-pair-as-the-code-gate
conventionsSource: none
projectRules: [general.md, python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: a6e476ed461c66fd9397ad43987c3340318af1a7
reviewedBlob: 12a01973ab8548d95ea91fa92ef1b8f49b1eaeea
reviewedBlobCurrent: true
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 60
injected: []
filesRead:
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/recipes/recipe_review.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/reviewer_options.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/data/pipelines/P6.yaml"
  - "src/squadron/data/pipelines/implement.yaml"
  - "src/squadron/pipeline/steps/phase.py"
  - "src/squadron/data/pipelines/review.yaml"
  - "src/squadron/data/recipes/haiku-line-pass.yaml"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/review/persistence.py"
  - "pyproject.toml"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/pipeline/steps/review.py"
searches:
  - "grep RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src"
  - "grep no_tools in /Users/manta/source/repos/manta/squadron/src"
  - "grep def resolve_effective_tools in /Users/manta/source/repos/manta/squadron/src"
  - "grep def _findings_block|## Findings|class Severity|severity: Severity|SCORED_SEVERITIES = in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep Recipe\\.model_validate|model_validate\\(.*recipe|Recipe\\(|load_recipe\\(|yaml\\.safe_load in /Users/manta/source/repos/manta/squadron/src"
  - "grep tool_isolation|recipe_isolation_failure|isolation in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep haiku-line-pass|review-model|keep_categories|reviewer_options in /Users/manta/source/repos/manta/squadron/src/squadron/data"
  - "list_files **/*line-pass* in /Users/manta/source/repos/manta/squadron"
  - "grep diff in /Users/manta/source/repos/manta/squadron/src/squadron/review/template_inputs.py"
  - "grep review:|review-model|template: code|diff in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep \"review\"|'review'|slice in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/implement.py"
  - "grep \\\"review\\\" in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep remove 'allowed_tools|declares 'allowed_tools|line-length|line_length|E501 in /Users/manta/source/repos/manta/squadron"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/tests"
  - "grep ^(?!.*(# type:|# pyright:|# noqa|pytest\\.mark)).{105,}$ in /Users/manta/source/repos/manta/squadron/tests/recipes"
  - "grep ^(?!.*(# type:|# pyright:|# noqa|pytest\\.mark)).{105,}$ in /Users/manta/source/repos/manta/squadron/src/squadron/recipes"
  - "grep ^(?!.*(# type:|# pyright:|# noqa|pytest\\.mark)).{105,}$ in /Users/manta/source/repos/manta/squadron/tests/pipeline/actions"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/tests/recipes"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/src/squadron/recipes"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/tests/pipeline/actions"
  - "grep validate_recipe_review|resolve_review_model_ref|has_diff in /Users/manta/source/repos/manta/squadron/src"
  - "grep \\\"diff\\\"|resolve_slice_diff_range|def review_code|def _code|_run_review_command\\( in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep honors_empty_tools|tool_isolation_failure|tool_isolation_error in /Users/manta/source/repos/manta/squadron/src"
  - "grep can run without tools|cannot be isolated|or remove in /Users/manta/source/repos/manta/squadron/tests"
  - "grep _resolve_prompt_from_prior_review|REVIEW_FILE|read_text|_findings_block\\(|stage_section in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep ReviewOutputKey\\.RESPONSE|def review_response|review_response\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep def recall_findings|def _category|ReviewCategory\\(|ReviewCategory\\.OTHER|normalize_category in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/recipe_outcome.py"
  - "grep def map_historical_category in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def stage_model|def load_user_aliases|def get_all_aliases|def load_builtin_aliases|lru_cache|functools.cache|@cache in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def resolve_model_alias|def _load_aliases_from_file|def models_toml_path|def model_allows_tools in /Users/manta/source/repos/manta/squadron/src/squadron/models/aliases.py"
  - "grep set\\[Recipe|set\\[RecipeRef|dict\\[Recipe|dict\\[RecipeRef|frozenset\\(.*recipe|hash\\(.*(recipe|ref)|lru_cache.*\\n?def .*recipe|@cache in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep set\\[Recipe|set\\[RecipeRef|dict\\[Recipe|dict\\[RecipeRef|hash\\(.*(recipe|ref) in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep required|optional|name: diff|key: diff in /Users/manta/source/repos/manta/squadron/src/squadron/data/templates/code.yaml"
  - "grep setdefault\\(|params\\.items\\(\\)|pipeline params|inherit|propagat in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep ActionContext\\(|params= in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/executor.py"
  - "grep merged_action_params in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/executor.py"
diffTruncated: false
effort: xhigh
turns: 61
promptTokens: 8302975
cachedTokens: 7984790
cacheWriteTokens: 318109
completionTokens: 99482
durationSeconds: 426.1
costUsd: 0.89304
costBasis: provider
runId: run-20261123-p6-a0dd6cdd
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: performance-resource
    summary: "Recipe isolation check does alias-file I/O on the event loop"
    location: "src/squadron/pipeline/actions/review.py:342-347"
  - id: F002
    severity: concern
    category: correctness
    summary: "`tools: false` is not enforced on the `sq review` recipe path"
    location: "src/squadron/cli/commands/review_recipe.py:91-109"
  - id: F003
    severity: note
    category: correctness
    summary: "`_cell` does not escape backslashes"
    location: "src/squadron/recipes/recipe_merge.py:112-117"
  - id: F004
    severity: note
    category: other
    summary: "Benchmark refuses `reviewer_options` even when they change nothing"
    location: "src/squadron/benchmark/recall/scoring.py:156-160"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "Reviewer rules are dropped silently when `rules_content` is unset"
    location: "src/squadron/recipes/reviewer_options.py:34-40"
  - id: F006
    severity: note
    category: type-contract-debt
    summary: "`Recipe` is no longer hashable"
    location: "src/squadron/recipes/recipe.py:89-90"
  - id: F007
    severity: note
    category: correctness
    summary: "`keep_categories` order changes the recipe hash"
    location: "src/squadron/recipes/recipe_record.py#recipe_hash"
  - id: F008
    severity: note
    category: other
    summary: "A `files:`-only code step with a filter recipe fails only when it runs"
    location: "src/squadron/pipeline/classification.py:470"
  - id: F009
    severity: note
    category: documentation-drift
    summary: "`recipe_runner.py` module docstring is out of date"
    location: "src/squadron/recipes/recipe_runner.py:3-4"
  - id: F010
    severity: note
    category: test-debt
    summary: "Action-path tests cannot catch a signature mismatch"
    location: "tests/recipes/support.py#ScriptedReviewCall"
  - id: F011
    severity: pass
    category: correctness
    summary: "Live and benchmark paths share one gating rule"
    location: "src/squadron/recipes/kept_findings.py:46-66"
  - id: F012
    severity: pass
    category: correctness
    summary: "`tools: false` reaches provider tool suppression on the action path"
    location: "src/squadron/review/review_client.py:236-240"
  - id: F013
    severity: pass
    category: correctness
    summary: "Shipped code-review defaults resolve a diff before classification"
    location: "src/squadron/pipeline/executor.py:1147"
---

# Review: code — slice 437

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 55 successful tool call(s) of 60 made; 147497 of 147497 diff characters reached the model

## Findings

### [CONCERN] Recipe isolation check does alias-file I/O on the event loop

`ReviewAction._review` is `async def`, and the new recipe branch calls `recipe_isolation_failure` synchronously. For each `tools: false` reviewer that function calls `stage_model` (`recipes/stage_config.py`), which calls `resolve_model_alias` → `get_all_aliases()` (`models/aliases.py:217-238`). That re-reads and TOML-parses `models.toml` on every call, with no cache (`models/aliases.py:157-167`). The project async rule requires sync work on the loop to be under 1 ms in the worst case, and this is not.

The same method already moves `_classify_recipe` off the loop for this reason (review.py:317-323: "Classification reads recipe and alias files, so it runs off the loop"). The alias path already reads aliases on the loop (`_alias_model`, review.py:392-403), so this extends an existing pattern rather than creating one. Still, the new call sits next to the off-loop classification. Fix: run the isolation check inside `_classify_recipe`, or wrap it in `asyncio.to_thread` the way that call is wrapped.

### [CONCERN] `tools: false` is not enforced on the `sq review` recipe path

`run_recipe_cli` calls `run_recipe_review` directly. The only isolation check for `tools: false` is `recipe_isolation_failure`, which the pipeline action calls (review.py:342). Nothing under `src/squadron/cli` calls `tool_isolation_error` or `tool_isolation_failure`.

`tool_support.py:66` refuses a no-tools declaration when a provider reads files itself and does not honor an empty tool list (the comment there names Codex). On the CLI, `reviewer_call_options` still sets `no_tools=True`, and `resolve_effective_tools` returns an empty list. The provider ignores that, so the reviewer runs with tools. The stage config is built with `tool_use=False` (`recipes/stage_config.py#stage_config`), so the stored record says the reviewer had no tools when it did. The pipeline refuses the same recipe before any call.

The existing `sq review --no-tools` path has the same gap, so this is inherited rather than new. The shipped `haiku-line-pass` is not affected today: its tests run it through `ReviewAction` unpatched, and it passes the action-path check. Fix: run the same check before the first call in the CLI path and exit 1, as the other refusals do.

### [NOTE] `_cell` does not escape backslashes

A title with a backslash before a pipe (`x\|y`) becomes `x\\|y`, which GFM can read as an unescaped pipe and split the row. Escaping `\` first would close this. The rare case is a rendering problem only; the review parser is not affected.

### [NOTE] Benchmark refuses `reviewer_options` even when they change nothing

`_pair_variants` returns no rows for any reviewer with an options entry, and `expand_pending` in `benchmark/recall/run_plan.py` refuses any non-empty `reviewer_options`. A `tools: true` entry with no rules changes neither the call nor the config key, so refusing it is over-broad. Limiting the refusal to options that change the call (`not options.tools or options.rules`) would match the stated reason (#393).

### [NOTE] Reviewer rules are dropped silently when `rules_content` is unset

If `rules` is set and `rules_content` is `None`, the reviewer's rules are skipped with no log, and `rules_sha256` returns `None`, so the config key does not change either. `load_recipe` always fills `rules_content`, so this only happens with a `Recipe` built in code. Raising here would match the no-silent-fallback rule.

### [NOTE] `Recipe` is no longer hashable

The `Mapping` field makes `Recipe` unhashable, and `RecipeRef` (a frozen dataclass holding a `Recipe`) inherits that. Nothing under `src` hashes either today (I checked). The comment on line 89 records the trade-off, so this is a trap for later rather than a bug now.

### [NOTE] `keep_categories` order changes the recipe hash

The filter is a set, but `recipe_hash` writes it in the order the recipe lists it. `[correctness, security-hygiene]` and the reverse therefore get different recipe identities. Sorting the values before hashing would make the identity depend only on the set.

### [NOTE] A `files:`-only code step with a filter recipe fails only when it runs

The pre-run check passes `has_diff=template_takes_diff(template)`, which is always true for `code` (its `diff` input is optional). So a code step with `files:` and no `slice` or `diff` passes the check and is refused at run time, after earlier steps may have spent money. `tests/pipeline/test_classification.py` documents this as the D7 trade-off. The shipped defaults are unaffected, because their code steps all carry `slice`. A cheap improvement would be to let the classifier see the step's `slice` and `diff` keys.

### [NOTE] `recipe_runner.py` module docstring is out of date

It says the review stage uses "the step's own template, inputs and rules." With `reviewer_options`, a reviewer's rules file is appended and `no_tools` may be set. The `reviewer_call_options` docstring describes this correctly.

### [NOTE] Action-path tests cannot catch a signature mismatch

`ScriptedReviewCall` accepts any keyword arguments, so the action-path tests that check `no_tools` and `rules_content` never exercise the real `run_review_with_profile` signature (`review/review_client.py:147-164`). I confirmed the signature accepts both today. A rename would pass these tests and fail in production. One test that calls the real function with the reviewer-option dict, with the provider stubbed, would close the gap.

### [PASS] Live and benchmark paths share one gating rule

`split_by_category` is the only place a finding's category is compared with the filter. The runner (`recipe_runner.py:234`), benchmark scoring (`scoring.py:191`), and real-work counts (`real_work.py`) all call it, so they agree on what gates. The tests cover the no-category case (gating) and the normalized `other` case.

### [PASS] `tools: false` reaches provider tool suppression on the action path

`no_tools` from `reviewer_call_options` flows into `resolve_effective_tools(suppressed=no_tools)`, which empties the offered tool set. The provider-level gap on the CLI path is covered in the finding above.

### [PASS] Shipped code-review defaults resolve a diff before classification

Pipeline params, including `slice`, reach every action through `merged_action_params`. So `_review` resolves the diff from the slice (review.py:296-298) before `_classify_recipe` runs (review.py:317-323). The no-diff refusal therefore does not fire for P6, implement, implement-plan, or `review.yaml`.

### Run Digest

- Response length: 16321 chars
- Response is newline-free: no
- Tool calls made: 60
- Tool calls failed: 5
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 61
- Tokens — prompt / cached / cache write / completion / reasoning: 8302975 / 7984790 / 318109 / 99482 / not computed
- Duration: 426.1 s
- Cost: $0.89 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
