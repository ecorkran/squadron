---
docType: review
layer: project
reviewType: tasks
slice: line-pass-pair-as-the-code-gate
conventionsSource: none
projectRules: [general.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: e9aba4de155e681e91e2bac0ca01e7fcb83612da
reviewedBlob: c67c737e32f09d1a00ee53c32ea84e68fb01c06b
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 127
injected:
  - key: input
    path: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md"
    chars: 34896
    sha256: eb7a2f803bf7dae51b14fa7631edf29660ec398069cd7d72aef38e8fb8c9f782
    whole: true
  - key: against
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 41159
    sha256: 1eacb261d32272dd619f3754ea5197461f4b8b9cf6f58ca3243eba9852ce2135
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/recipe_record.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/metrology/review_category_map.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/review/models.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke37429-haiku-line-1.json"
  - "src/squadron/data/pipelines/P6.yaml"
  - "src/squadron/data/pipelines/review.yaml"
  - "src/squadron/cli/commands/review.py"
  - "tests/review/test_review_template_defaults.py"
  - "tests/cli/commands/test_run.py"
  - "tests/benchmark/recall/test_recipe.py"
  - "tests/recipes/test_import_boundary.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "src/squadron/benchmark/recall/refusal.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "src/squadron/benchmark/recall/label_candidates.py"
  - "tests/recipes/test_stage_config.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/metrology/recipe_review_models.py"
  - "tests/recipes/test_model_ref.py"
  - "src/squadron/cli/commands/review_revise.py"
  - "docs/PIPELINES.md"
  - "README.md"
  - "src/squadron/data/models.toml"
searches:
  - "list_files src/squadron/recipes/*.py in ."
  - "list_files src/squadron/data/recipes/* in ."
  - "list_files src/squadron/data/pipelines/* in ."
  - "list_files project-documents/user/reference/review-recall-recipes/* in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/**/* in ."
  - "list_files tests/recipes/**/*.py in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{convert.py,rules-line-pass.md,RESULTS.md} in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/out/*-haiku-line-1.json in ."
  - "list_files src/squadron/{core/finding_categories.py,project_rules/render.py,metrology/recall_run_models.py,metrology/recipe_review_models.py,metrology/review_category_map.py,review/models.py,review/persistence.py,review/review_client.py,review/rules.py} in ."
  - "list_files src/squadron/benchmark/recall/*.py in ."
  - "list_files tests/benchmark/recall/*.py in ."
  - "list_files tests/{cli/test_review_recipe.py,cli/test_benchmark_recall_run.py,cli/test_review*.py,pipeline/actions/test_review_recipe.py,pipeline/actions/test_dispatch.py,pipeline/test_builtin_pipelines.py,pipeline/test_classification.py,pipeline/test_loader.py,review/test_review_template_defaults.py,review/tes\u2026 in ."
  - "grep class RecallFinding|class StageConfig|def config_key|rules_hash|tool_use|class StageKind|class RecallRefusal in /Users/manta/source/repos/manta/squadron/src"
  - "grep no_tools|rules_content|RULES_SEPARATOR|options=|call_options|review_call=|def run_review_with_profile in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def (_pair_variants|entry_matches|expand_pending|reviewer_output|comb_input_findings|recipe_outputs|chain_counts|_reviewer_counts|_row_cells|BoundsJson|class BoundsJson|class RowJson|class ReviewerOutput|class RecipeReview\\b|class RecipeReviewInfo|def recipe_merge|def live_stage_config|class ConfigF\u2026 in /Users/manta/source/repos/manta/squadron/src"
  - "grep RowJson|BoundsJson|ReviewerOutput\\b|RecipeReviewInfo|live_stage_config|ConfigFor|StageIdentityResolver|PendingStage\\b|review_argv|_findings_block|No specific findings|NO_TOOLS_NOTICE|recipe_merge\\(|_NO_VALUE|split_by_category|reviewer_call_options|rules_sha256|\\bkeep_categories\\b in /Users/manta/source/repos/manta/squadron"
  - "grep Findings|_FINDING|re\\.compile|whole|fallback in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep class ReviewFinding|raw_category|SCORED_SEVERITIES =|def verdict_from_findings|class ReviewResult|    findings: |    category:  in /Users/manta/source/repos/manta/squadron/src/squadron/review/models.py"
  - "grep \"(category|severity|verdict|raw_category)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke37429-haiku-line-1.json"
  - "grep class Severity|_missing_|upper\\(\\)|def _severity|SEVERITY_MAP|_SEVERITY_MAP = in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep \"category\": (null|\"(security|error-handling|observability|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|documentation|style|code-quality|concurrency|uncategorized|other|test-debt|architectural-decay|performance-resource|documentation-\u2026 in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(other|test-debt|architectural-decay|performance-resource|documentation-drift|dependency-config-debt)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"severity\": \"(?i:concern|fail)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": (null|\"(security|error-handling|observability|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|documentation|style|code-quality|concurrency|uncategorized)\") in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"other\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"other\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"verdict\": \"UNKNOWN\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep review-model|model:|template:|^\\s+- name:|^\\s+name:|params:|review_model|haiku in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep default_model_code|DEFAULT_MODEL_CODE|default_model\\b|review-model|REVIEW_MODEL|PIPELINE_REVIEW_MODEL in /Users/manta/source/repos/manta/squadron"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \\.glob\\(|iterdir\\(|rglob\\(|RECIPE_SUFFIX|listdir|\\*\\.yaml|\\*\\.md in /Users/manta/source/repos/manta/squadron"
  - "grep shipped_recipes_dir|def production_recipe_dirs|def benchmark_recipe_dirs|test_shipped_recipes|Known recipes|no_longer_shipped in /Users/manta/source/repos/manta/squadron"
  - "grep class CallRecord|class ScriptedReviewCall|def __call__|no_tools|rules_content|kwargs|def scripted|class |FORBIDDEN|forbid|must not import|_BANNED|allowed in /Users/manta/source/repos/manta/squadron/tests/recipes/support.py"
  - "grep \"max_output_tokens\"|max_output_tokens=None|model_dump\\(\\)\\s*==|\\\"tool_use\\\": |'tool_use':  in /Users/manta/source/repos/manta/squadron/tests"
  - "grep max_output_tokens|tool_use|config_key|model_dump in /Users/manta/source/repos/manta/squadron/tests/metrology/test_recipe_review_models.py"
  - "grep def test_|config_key|rules|tool_use in /Users/manta/source/repos/manta/squadron/tests/recipes/test_stage_config.py"
  - "grep EXPECTED_ROW|findings_per_run|recall_|not_gating|rows\\[|def test_ in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_report_json_schema.py"
  - "grep expand_pending|RecallRefusal|build_bound|run_bound|print|echo|rprint|bound in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall_run.py"
  - "grep def test_review_model_recipe_passes_the_pre_run_check|def test_review_pipeline_defaults_to_the_p6_code_reviewer|def test_implement_plan_params_and_shape|def test_shipped_recipes_are_the_two_with_no_opus_high_comb|haiku-solr-luna|haiku-sol-luna|def test_.*recipe.* in /Users/manta/source/repos/manta/squadron/tests"
  - "grep Verification Walkthrough|Draft; refined|^## |^### Recipe|Recipe reviews|luna-r|refused before any model call|haiku-sol-luna|Each runs two reviewers|defaults to `haiku-xhigh` in /Users/manta/source/repos/manta/squadron"
  - "grep haiku-xhigh|luna-r|refused before any model call|defaults to `haiku-xhigh`|Each runs two reviewers|Recipe reviews|## Built-in|implement-plan in /Users/manta/source/repos/manta/squadron"
  - "grep ^\\| .*(18|437)|437 in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep line-pass|haiku-line|^\\s*(-|\\d+\\.|\\|)\\s*\\[?.{0,3}\\]?\\s*18\\b|\\b18\\.|Entry 18|entry 18 in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep ^#|^\\d+\\.|^- \\[|^\\| ?\\d+ ?\\| in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep validate_recipe_review|resolve_review_model_ref|plan_recipe\\(|recipe_review_request\\(|run_recipe_review\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep resolve_review_model_ref\\(|has_diff=|template=|no_tools=|explicit_profile= in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/classification.py"
  - "grep \"--no-save\"|\"--cwd\"|\"--diff\"|\"--real-work\"|\"--max\"|\"--dry-run\"|\"--project\"|\"--files\"|\"-v\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep exit\\(?.{0,10}(2|FAIL)|Exit\\(code=2\\)|code=2|EXIT_FAIL|exit_code_for in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep \"--no-save\"|\"--cwd\"|\"--diff\"|\"--real-work\"|\"--max\"|\"--dry-run\"|\"--project\"|\"--files\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep ^(reviewers|combs|pool|name): in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-recipes"
  - "grep ^\\[(models\\.|[a-zA-Z0-9_.-]+\\])|^\\[[^\\]]+\\] in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep def load_user_aliases|load_user_aliases\\b in /Users/manta/source/repos/manta/squadron"
  - "grep _classify_recipe\\(|has_diff =|has_diff=|has_diff: in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep _classify_recipe|has_diff|template_takes_diff in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions"
  - "grep \\\"diff\\\"|'diff'|diff_ref|\\[\\\"diff\\\"\\]|inputs\\[.diff.\\]|def _resolve_slice_inputs|def _resolve_inputs|def _resolve_code in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def resolve_template_input_parts|\"diff\"|diff=|\\bdiff\\b.*slice|code.*diff in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep recipeComplete|aiRecipe|aiModel|RECORD_NOT_WRITTEN =|recipe record: not written in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep package|include|force-include|artifacts|data|\\.md in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep \"file_ref\": [^\\n]*,\\n\\s*\"location\"|\"severity\": \"(CONCERN|FAIL)\",\\n\\s*\"title\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep line|rules|no-tools|tools in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/run.sh"
  - "grep \"file_ref\": [^\\n]*,\\n\\s*\"location\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep lru_cache|functools\\.cache\\b|@cache\\b|set\\[Recipe\\]|frozenset\\(.*recipe|\\{recipe\\b|recipe\\.model_dump|Recipe\\.model_validate|Recipe\\(\\*\\*|model_validate\\(.*recipe in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep haiku-s|haiku-sol|haiku-solr|run_recipe_part|RECIPE_ALIASES =  in /Users/manta/source/repos/manta/squadron/tests"
  - "grep findings|read_text|review_file|feedback|_findings_block|parse_review|ReviewResult in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review_revise.py"
  - "grep feedback|findings_block|_findings|prompt|build_feedback|revise_prompt in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep def run_review_revise|def _revise|feedback=|feedback_prompt|findings_block|_resolve_prompt_from_prior_review|review_file_path|read_text\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep def entry_key|def identity_of|def slot|model_dump_json\\(\\)|model_dump\\(\\)|\\.model_dump\\(mode in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep \"max_output_tokens\": |'max_output_tokens': |\\\"tool_use\\\": (true|false|null) in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def entry_key|def review_key_for|entry_key\\b.*import|import.*entry_key in /Users/manta/source/repos/manta/squadron/src"
  - "grep max_output_tokens|tool_use in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_run_models.py"
  - "grep recipe = |recipe: RecipeReviewInfo|degraded =|resolved_verdict =|def render_review|def _body|def to_markdown|def review_markdown in /Users/manta/source/repos/manta/squadron/src/squadron/review/persistence.py"
  - "grep haiku-sol-luna|haiku-solr-luna|luna-r\\b in /Users/manta/source/repos/manta/squadron/src"
  - "grep resolve_template_input|resolve_slice_diff_range|resolve_template_input_parts|inputs\\[.diff.\\]|inputs\\[.input.\\] =|_run_review_command\\(|def review_code|def _review_code|def _build_code_inputs|changed_files = in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep recipe_names|recipes:|all_recipes|benchmark_recipe_dirs\\(|known_recipe_names|list_recipes|for .* in .*recipe in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall_report.py"
  - "grep def load_recipes in /Users/manta/source/repos/manta/squadron/src/squadron"
sectionsInDocument: 27
sectionsCovered: 27
effort: xhigh
turns: 128
promptTokens: 18393178
cachedTokens: 18036313
cacheWriteTokens: 356701
completionTokens: 170154
durationSeconds: 702.7
costUsd: 1.542772
costBasis: provider
runId: run-20261123-p5-55b85c9e
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Task 9 says \"a line pass that raises\" without naming the exception type"
    location: "src/squadron/recipes/recipe_runner.py:205"
  - id: F002
    severity: concern
    category: testing
    summary: "Task 21 places the existing `haiku-solr-luna` / `haiku-sol-luna` tests in the wrong file"
    location: "tests/cli/test_review_recipe.py"
  - id: F003
    severity: note
    category: testing
    summary: "Packaging of the rules file is checked once by hand, not by a test"
    location: "pyproject.toml:72"
  - id: F004
    severity: note
    category: documentation
    summary: "The `P56` and `P456` comments point to a P6 note whose content is about to change"
    location: "src/squadron/data/pipelines/P56.yaml:9"
  - id: F005
    severity: note
    category: testing
    summary: "A test name becomes wrong after Task 20"
    location: "tests/review/test_review_template_defaults.py:32"
  - id: F006
    severity: note
    category: testing
    summary: "The pre-run check test is placed in the wrong test module"
    location: "src/squadron/pipeline/classification.py:465-473"
  - id: F007
    severity: note
    category: consistency
    summary: "`review/rules.py` still hard-codes the rules separator in one place"
    location: "src/squadron/review/rules.py:246"
  - id: F008
    severity: note
    category: documentation
    summary: "Task 23 does not say where in the README the new default goes"
    location: "README.md:239"
  - id: F009
    severity: note
    category: scope
    summary: "Task count is proportionate, with two obvious merges"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md"
  - id: F010
    severity: pass
    category: testing
    summary: "The D6 escaping defeats the parser's finding patterns"
    location: "src/squadron/review/parsers.py:91-110"
  - id: F011
    severity: pass
    category: sequencing
    summary: "`pipeline.review-model` feeds only code reviews in the four pipelines"
    location: "src/squadron/data/pipelines/P6.yaml:28"
  - id: F012
    severity: pass
    category: testing
    summary: "Task 18's fixture selection is feasible from the stored outputs"
    location: "project-documents/user/reference/review-recall-results/20261122-martian/out"
---

# Review: tasks — slice 437

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 9 says "a line pass that raises" without naming the exception type

Task 9 (task file line 144) says "A line pass that raises: one WARNING logged naming the reviewer, its outcome is a harness failure". The runner converts only `ProviderError` into a harness-failure stage (`recipe_runner.py:205-209`). Any other exception propagates out of `run_recipe` (module docstring, lines 5–6). A test that scripts the line pass to raise `RuntimeError` would see the exception escape, not a harness-failure stage. Task 22's two failed-line-pass tests (lines 263–265) have the same gap. Both should say "raises `ProviderError`", and note that other exceptions still propagate as 434 defines them.

### [CONCERN] Task 21 places the existing `haiku-solr-luna` / `haiku-sol-luna` tests in the wrong file

Task 21 (task file line 256) says "The existing `haiku-solr-luna` and `haiku-sol-luna` tests pass unchanged" under the `tests/cli/test_review_recipe.py` item. That file names neither recipe. The tests live in `tests/benchmark/recall/test_recipe.py:110-115`, `tests/pipeline/test_classification.py:1229-1247`, `tests/pipeline/test_loader.py:559`, `tests/cli/test_benchmark_recall_run.py:131` and `tests/benchmark/recall/test_run_plan.py:130`. An implementer who looks in the CLI file will either add duplicates or miss the regression check. Name the real files.

### [NOTE] Packaging of the rules file is checked once by hand, not by a test

Design D9 (line 262) says "a test loads the recipe from the installed package data directory". Task 17 (line 218) uses a one-time `uv build` and `unzip -l` check instead, and its `shipped_recipes_dir()` test runs against the checkout. Hatch packages all of `src/squadron` (`pyproject.toml:72`), so the risk is low. Still, a later change to the packaging config would not be caught in CI. Either add a test that builds the wheel, or record the one-time check as the chosen mitigation.

### [NOTE] The `P56` and `P456` comments point to a P6 note whose content is about to change

`P56.yaml:9` and `P456.yaml:10` say "review-model: see the note in P6.yaml." Task 20 rewrites that note to describe the recipe default for P6 and says P56 and P456 stay unchanged (task file line 240). Those two pipelines keep `haiku-xhigh`, so the pointer now leads to a description of a different default. Reword the two comments to say they keep `haiku-xhigh` (see #390).

### [NOTE] A test name becomes wrong after Task 20

`test_standalone_review_default_matches_the_pipeline` asserts the `code` template's model matches the pipelines. After Task 20 it does not. Task 20 (task file line 243) rewords only the module docstring and the `PIPELINE_REVIEW_MODEL` comment. Rename the test too, or the name will contradict its own `code` row.

### [NOTE] The pre-run check test is placed in the wrong test module

Task 12 (task file line 174) puts "the pre-run check passes a `code` step with `files` and no diff" in `tests/recipes/test_model_ref.py`. The pre-run check is `classify_pipeline`, which calls `resolve_review_model_ref` with `has_diff=template_takes_diff(template)`. That expression is true for `code` whatever `files` says. Test it in `tests/pipeline/test_classification.py`, beside the Task 20 test at line 1178, using a `code` step with `files` and no diff.

### [NOTE] `review/rules.py` still hard-codes the rules separator in one place

Design D3 (line 178) says `review/rules.py` "already joins rules with" `RULES_SEPARATOR`. Lines 129, 143, 267 and 272 do, but line 246 writes `"\n\n---\n\n"` literally. That breaks the "defined once, never compared as literals" rule (task file line 40). The task file does not require a fix, so either add one line to Task 8 to replace the literal, or record it as a known exception.

### [NOTE] Task 23 does not say where in the README the new default goes

Task 23 (task file line 274) says "`README.md` names the new default code gate", with no location. The README has no sentence about the P6 default. The nearest passage is the recipe paragraph at `README.md:239`, which names only `haiku-sol-luna`. Say which paragraph gets the sentence.

### [NOTE] Task count is proportionate, with two obvious merges

The file has 25 tasks for about 20 modules and 11 decisions, which is in proportion. Tasks 21 and 22 are both end-to-end recipe-review tests through the two entry points, with the same scripted outputs (task file lines 250–267), so they can be one task. Tasks 18 and 19 (lines 223–235) share a fixture and a test and could also merge. Neither merge is needed.

### [PASS] The D6 escaping defeats the parser's finding patterns

`_FINDING_RE` needs a literal `###` heading or a literal `- [SEV]` bullet. A `\#` or `\[` in a table cell breaks both. When a `## Findings` heading exists, the scan is limited to that section (`parsers.py:797-824`). So the Not gating table (task file lines 150, 156) and the Task 11 parser test (line 162) hold.

### [PASS] `pipeline.review-model` feeds only code reviews in the four pipelines

In `P6.yaml:28,45`, `implement.yaml:19,36`, `implement-plan.yaml:31,48` and `review.yaml:11-12`, every consumer of the default is `template: code`. D10's "in all four the parameter feeds only code reviews" holds, so changing the default cannot refuse a slice or tasks review.

### [PASS] Task 18's fixture selection is feasible from the stored outputs

The `-haiku-line-1.json` and `-haiku-xhigh-1.json` files exist for many PRs. Several run-1 files contain `"category": "other"`. No run-1 file has verdict `UNKNOWN`. No haiku finding lacks a `category` key, and none has a null or historical category string. Severities in `findings` are uppercase. The lowercase severities sit only in `structured_findings`, which the fixtures exclude.

### Run Digest

- Response length: 24550 chars
- Response is newline-free: no
- Tool calls made: 127
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 128
- Tokens — prompt / cached / cache write / completion / reasoning: 18393178 / 18036313 / 356701 / 170154 / not computed
- Duration: 702.7 s
- Cost: $1.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12

## Resolution

- **Task 9 says "a line pass that raises" without naming the exception type** — Applied. Task 9's test and Task 22's failed-line-pass tests now raise `ProviderError`; Task 22 notes other exceptions propagate (434 D5).
- **Task 21 places the existing `haiku-solr-luna` / `haiku-sol-luna` tests in the wrong file** — Applied by removal. The line is dropped; Task 25's full `uv run pytest -q` covers those tests where they live.
- **Packaging of the rules file is checked once by hand, not by a test** — Applied. Task 17 records the one-time wheel check as the chosen mitigation; design D9's Technical Requirements line now says the same.
- **The `P56` and `P456` comments point to a P6 note whose content is about to change** — Applied. Task 20 rewords their comment to say they keep `haiku-xhigh` (#390); their value is unchanged.
- **A test name becomes wrong after Task 20** — Applied. Task 20 renames it to `test_review_template_default_model`.
- **The pre-run check test is placed in the wrong test module** — Applied. Task 12 moves it to `tests/pipeline/test_classification.py`, beside `test_review_model_recipe_passes_the_pre_run_check`.
- **`review/rules.py` still hard-codes the rules separator in one place** — Applied. Task 8 replaces the literal with `RULES_SEPARATOR`.
- **Task 23 does not say where in the README the new default goes** — Applied. Task 23 names the recipe paragraph after the pipeline example.
- **Task count is proportionate, with two obvious merges** — Rejected. The finding says neither merge is needed; Tasks 21–22 already share one commit, as do 18–19.
- **The D6 escaping defeats the parser's finding patterns** — Pass; no change.
- **`pipeline.review-model` feeds only code reviews in the four pipelines** — Pass; no change.
- **Task 18's fixture selection is feasible from the stored outputs** — Pass; no change.
