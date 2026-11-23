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
reviewedSha: 9e083186a1cb062039a35334c20f082f76915dc9
reviewedBlob: 12a01973ab8548d95ea91fa92ef1b8f49b1eaeea
reviewedBlobCurrent: true
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 83
injected: []
filesRead:
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/reviewer_options.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/data/recipes/haiku-line-pass.yaml"
  - "src/squadron/data/pipelines/review.yaml"
  - "src/squadron/data/templates/code.yaml"
  - "src/squadron/data/pipelines/implement.yaml"
  - "src/squadron/data/pipelines/P6.yaml"
  - "src/squadron/review/parsers.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "src/squadron/pipeline/isolation_validation.py"
  - "src/squadron/benchmark/recall/report_json.py"
searches:
  - "grep no_tools|allowed_tools|model_allows_tools in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def run_review_with_profile|def run_review\\b|no_tools: bool|allowed_tools: list|ReviewCall\\b.*=|class ReviewCall|ReviewCall =  in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep validate_recipe_review|resolve_review_model_ref|has_diff= in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def recipe_review_request|review_call=|def run_recipe_review|class RecipeReviewRequest|RecipeReviewCall\\( in /Users/manta/source/repos/manta/squadron/src/squadron/recipes"
  - "grep _classify_recipe\\(|no_tools=|allowed_tools.*\\[\\]|has_diff = |has_diff= in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep haiku-line-pass|haiku-xhigh|review-model|files:|diff: in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "list_files **/haiku-line-pass.yaml in /Users/manta/source/repos/manta/squadron"
  - "list_files **/line-pass.rules.md in /Users/manta/source/repos/manta/squadron"
  - "grep def _base_inputs|\"diff\"|'diff'|\"files\" in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def _resolve_slice_inputs|\"diff\"\\]|\\[\"diff\"\\]|inputs\\[\"diff\"\\]|diff= in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def resolve_template_input_parts|\"code\"|diff in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions"
  - "list_files src/squadron/review/templates/code.yaml in /Users/manta/source/repos/manta/squadron"
  - "grep def resolve_template_input_parts in /Users/manta/source/repos/manta/squadron/src"
  - "list_files **/templates/code* in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep \"code\"|diff|required in /Users/manta/source/repos/manta/squadron/src/squadron/review/template_inputs.py"
  - "grep \"diff\"|diff=|\"slice\"|template.*code in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions"
  - "grep review.*template.*code|\\\"template\\\": \\\"code\\\"|template=\\\"code\\\"|ReviewAction\\(\\)|review_step|_review_params|build_review in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep review in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/implement.py"
  - "grep \"diff\"|\"slice\"|slice=|diff= in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep review in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/steps/phase.py"
  - "grep lru_cache|functools\\.cache|@cache\\b|set\\[Recipe\\]|dict\\[Recipe|frozenset\\(.*recipe|hash\\(recipe|\\{recipe\\b|: Recipe\\] in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "list_files tests/recipes/fixtures/hand_run/* in /Users/manta/source/repos/manta/squadron"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/**/* in /Users/manta/source/repos/manta/squadron"
  - "list_files project-documents/user/reference/review-recall-recipes/*.yaml in /Users/manta/source/repos/manta/squadron"
  - "grep Findings|_FINDING|\\\\\\[|\\\\#|def _findings_section|def parse_review_output|whole|fallback in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep degraded\\s*=|fallback_used=|fallback_used\\b.*=|def merge_recipe|verdict_source=|UNKNOWN in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/recipe_merge.py"
  - "grep degraded\\s*=|degraded = in /Users/manta/source/repos/manta/squadron/src/squadron/review/persistence.py"
  - "grep line-length|line_length|\\[tool\\.ruff|extend-select|select = |E501|ignore =  in /Users/manta/source/repos/manta/squadron"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep ^.{105,}$ in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def recall_findings|category|normalize in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/recipe_outcome.py"
  - "grep class RecallFinding|category:|SCORED_SEVERITIES\\s*=|class ReviewCategory|def normalize|OTHER in /Users/manta/source/repos/manta/squadron/src"
  - "grep class RecallFinding|class ReviewCategory|SCORED_SEVERITIES|def map_historical_category in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def identity_of|config_key|class StageIdentity|rules_hash|template_hash in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/scoring_select.py"
  - "grep config_key in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep _findings_block|feedback.*review|def _review_feedback|read_text in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/dispatch.py"
  - "grep def resolve_effective_tools|suppressed in /Users/manta/source/repos/manta/squadron/src/squadron/review/tool_support.py"
  - "grep def resolve_effective_tools in /Users/manta/source/repos/manta/squadron/src"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/rules-line-pass.md in /Users/manta/source/repos/manta/squadron"
  - "grep def tool_isolation_failure|def should_inject_file_bodies in /Users/manta/source/repos/manta/squadron/src"
  - "grep def tool_isolation_error in /Users/manta/source/repos/manta/squadron/src"
  - "grep tool_isolation|honors_empty_tools|TOOL_ISOLATION in /Users/manta/source/repos/manta/squadron/src"
  - "grep \\\"haiku\\\"|haiku:|haiku-xhigh in /Users/manta/source/repos/manta/squadron/src/squadron/data"
  - "grep can_read_files=True|can_read_files= in /Users/manta/source/repos/manta/squadron/src/squadron/providers"
  - "grep \\[aliases\\.(haiku|sol|sol-r)\\] in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep openai-oauth in /Users/manta/source/repos/manta/squadron/src/squadron/providers"
  - "grep ^from squadron|^import squadron in /Users/manta/source/repos/manta/squadron/src/squadron/project_rules/render.py"
  - "grep ^from squadron|^import squadron in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/refusal.py"
  - "grep ^from squadron|^import squadron in /Users/manta/source/repos/manta/squadron/src/squadron/core/finding_categories.py"
  - "grep squadron\\.(recipes|pipeline|review|benchmark) in /Users/manta/source/repos/manta/squadron/src/squadron/project_rules"
  - "grep def shipped_recipes_dir|def production_recipe_dirs|def benchmark_recipe_dirs|def defect_repo|def review_result|def run_scripted|def provider_error|def _record\\b|def _review_files|class FakeRecipeSink|def _recipe_metadata|def _warnings|def _code\\b in /Users/manta/source/repos/manta/squadron"
  - "grep recipe\\.model_dump|recipe\\.model_dump_json|Recipe\\.model_validate|\\.model_dump\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep not_gating\\` lists|a scored finding not listed|__len__\\(\\)|# type: ignore\\[attr-defined\\]|def _stored|def _result|def _finding in /Users/manta/source/repos/manta/squadron"
  - "grep \\.category\\s*(==|!=|in\\b|not in)|keep_categories\\s*(\\)|\\]|and|or|\\bis\\b) in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def undecided_candidates|class ImportOnlyResolver in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
diffTruncated: false
effort: xhigh
turns: 84
promptTokens: 8984963
cachedTokens: 8742038
cacheWriteTokens: 242821
completionTokens: 95390
durationSeconds: 401.3
costUsd: 0.814406
costBasis: provider
runId: run-20261123-p6-a0dd6cdd
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Per-reviewer `tools: false` skips the provider-isolation guard"
    location: "src/squadron/pipeline/actions/review.py:323-327"
  - id: F002
    severity: concern
    category: correctness
    summary: "A step-level `no_tools` is silently overwritten for reviewers with `tools: true`"
    location: "src/squadron/recipes/reviewer_options.py:31"
  - id: F003
    severity: concern
    category: correctness
    summary: "`rules: \"\"` is silently ignored when it is the only rules key"
    location: "src/squadron/recipes/recipe.py:181"
  - id: F004
    severity: note
    category: documentation-drift
    summary: "`stage_config.py` module docstring omits `rules_hash`"
    location: "src/squadron/recipes/stage_config.py:3-4"
  - id: F005
    severity: note
    category: documentation-drift
    summary: "The `not_gating` field doc overstates what is listed"
    location: "src/squadron/benchmark/recall/report_json.py:56-59"
  - id: F006
    severity: note
    category: type-contract-debt
    summary: "`Recipe` is `frozen` but holds a dict, so it cannot be hashed"
    location: "src/squadron/recipes/recipe.py:89"
  - id: F007
    severity: note
    category: type-contract-debt
    summary: "Fixture parsing is untyped and the type checker is silenced"
    location: "tests/recipes/test_hand_run_entry.py:38-54"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "`.__len__()` call in a test"
    location: "tests/cli/test_review_recipe.py:288"
  - id: F009
    severity: pass
    category: consistency-rot
    summary: "The `RULES_SEPARATOR` refactor preserves behavior"
    location: "src/squadron/review/rules.py:246"
  - id: F010
    severity: pass
    category: correctness
    summary: "The not-gating table cannot be read as findings"
    location: "src/squadron/review/persistence.py:790-791"
  - id: F011
    severity: pass
    category: architectural-decay
    summary: "The category filter is compared in one place"
    location: "src/squadron/recipes/kept_findings.py:63"
---

# Review: code — slice 437

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 80 successful tool call(s) of 83 made; 138237 of 138237 diff characters reached the model

## Findings

### [CONCERN] Per-reviewer `tools: false` skips the provider-isolation guard

The #306 guard refuses a no-tools step when the provider brings its own tools and cannot honor an empty list (`src/squadron/pipeline/actions/tool_support.py:58-63`). The review action runs it only for a step-level `allowed_tools == []` and only when the model is an `_AliasModel`. A recipe reviewer's `tools: false` never reaches it. `reviewer_call_options` sets `no_tools` (`src/squadron/recipes/reviewer_options.py:31`), and `resolve_effective_tools` empties the declared list, but nothing checks that the provider honors that.

The shipped `haiku-line-pass` is not exposed today. `haiku` uses the `sdk` profile, and the SDK sets `honors_empty_tools=True` (`src/squadron/providers/sdk/provider.py:68`). A user recipe that names `sol` is a real gap. `sol` maps to `openai-oauth` and then to the `codex` provider (`src/squadron/providers/loader.py:14`). Codex has `can_read_files=True` (`src/squadron/providers/codex/provider.py:25`) and does not set `honors_empty_tools`. Validation accepts that recipe. At run time Codex keeps its tools, the prompt still says "You have no tools" (`review_client.py:142-143`, `NO_TOOLS_NOTICE`), and the stage records `tool_use: False`. Apply `tool_isolation_error` to each reviewer with `tools: false` before any call, using that reviewer's profile.

### [CONCERN] A step-level `no_tools` is silently overwritten for reviewers with `tools: true`

`merged[NO_TOOLS_KEY] = not options.tools` replaces whatever the step set. A step-level `no_tools=True` is refused before any call (`src/squadron/recipes/model_ref.py:159-162`, and `review.py:317` derives it from `allowed_tools == []`), so this does not happen today. But the helper's contract is that `no_tools` comes only from `tools`, so a future caller that passes a tool-less step gets tools back for any reviewer with the default `tools: true`, with no error. Use `bool(call_options.get(NO_TOOLS_KEY)) or not options.tools`, and add a test where a step-level `no_tools=True` survives a `tools: true` reviewer.

### [CONCERN] `rules: ""` is silently ignored when it is the only rules key

`_with_rules_read` decides whether to read any rules with `any(options.rules for ...)`, which is False for an empty string. The recipe then loads with `rules_content=None`, and the reviewer runs without the rules file its author wrote, with no error. If another reviewer in the same recipe does have a rules file, the same `""` takes a different path: `_read_rules` (line 162) lets `Path("").name == ""` pass the directory check, then fails to read the parent directory and reports "unreadable". The two paths disagree. Test `options.rules is not None` in `_with_rules_read`, refuse an empty name in `_read_rules`, and add a `rules: ""` case to `tests/recipes/test_recipe_options.py`.

### [NOTE] `stage_config.py` module docstring omits `rules_hash`

The docstring lists what `config_key` covers as "model, profile, template hash, ``tool_use`` and ``max_output_tokens``". Slice 437 D4 adds `rules_hash`, which `StageConfig.config_key` now includes when set (`src/squadron/metrology/recall_run_models.py`). Update the docstring.

### [NOTE] The `not_gating` field doc overstates what is listed

The comment says "a scored finding not listed is gating". `_not_gating` walks only `outputs.pairs`, and `recipe_outputs` adds a pair only when it is not dropped (harness or leak) and not left out (`src/squadron/benchmark/recall/scoring.py:127-131`). A scored finding in a dropped or left-out pair is neither listed nor counted as gating. Reword it to cover only the pairs this row scored.

### [NOTE] `Recipe` is `frozen` but holds a dict, so it cannot be hashed

`reviewer_options` is annotated `Mapping` and holds a dict at runtime. `hash(recipe)` would raise `TypeError`. Nothing hashes a `Recipe` today (I searched for `cache`, sets and dict keys), so this is latent. Either store the options as a tuple of pairs or a `MappingProxyType`, or drop `frozen` and say so.

### [NOTE] Fixture parsing is untyped and the type checker is silenced

`_stored` returns `dict[str, object]`, so `stored["findings"]` is typed `object`. The `# type: ignore[attr-defined]` comments at lines 54, 89 and 101 do not match the actual error (iterating `object`), and a bare ignore also hides other errors on those lines. The project rule calls for Pydantic at file-parsing boundaries. Parse each fixture into a small model and remove the ignores.

### [NOTE] `.__len__()` call in a test

`[...].__len__() == 2` should be `len([...]) == 2`. Ruff does not flag it, but the rest of the file uses `len()`.

### [PASS] The `RULES_SEPARATOR` refactor preserves behavior

`review/rules.py` already imports `RULES_SEPARATOR` (line 21), and the constant (`src/squadron/project_rules/render.py:29`) equals the literal it replaces, `"\n\n---\n\n"`. The change removes a duplicated literal without changing output.

### [PASS] The not-gating table cannot be read as findings

Without a `## Findings` heading, the parser scans the whole response (`src/squadron/review/parsers.py:797-800`), and `_FINDING_RE` is not line-anchored (`parsers.py:91-110`). The not-gating-only case writes that heading, so the parser looks only at the one-line section. The `#` escape in `recipe_merge._cell` also stops `###` from matching, so the escape and the heading guard together keep table rows out of the findings.

### [PASS] The category filter is compared in one place

I searched every `.category` comparison and every `keep_categories` use in `src/squadron`. The only comparison of a finding's category against the keep list is `split_by_category`, as the module docstring says (D5). The runner, scoring, the real-work counts and the recipe record all reuse it.

### Run Digest

- Response length: 16534 chars
- Response is newline-free: no
- Tool calls made: 83
- Tool calls failed: 3
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 84
- Tokens — prompt / cached / cache write / completion / reasoning: 8984963 / 8742038 / 242821 / 95390 / not computed
- Duration: 401.3 s
- Cost: $0.81 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
