---
docType: review
layer: project
reviewType: slice
slice: line-pass-pair-as-the-code-gate
conventionsSource: none
projectRules: [general.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: 350aa1efaef661a2f448c275407247c70a32e438
reviewedBlob: 3a54eb97bf6296cc2e5ebb810a4ecf4a482fc239
reviewedBlobCurrent: false
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 114
injected:
  - key: input
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 26867
    sha256: a28cd838c194b864d4b80bd9fdb51f5fec525b208f21bc99bfcf5ad75e600abe
    whole: true
  - key: against
    path: "project-documents/user/architecture/420-arch.model-benchmark.md"
    chars: 30840
    sha256: 3b909db8ad85dd24d2d2195772f10ecf022a254653af1faaa958b1f54dc13b07
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/recipes/recipe_review.py"
  - "src/squadron/recipes/recipe_record.py"
  - "src/squadron/metrology/review_category_map.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "tests/recipes/test_import_boundary.py"
  - "src/squadron/review/models.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "src/squadron/pipeline/actions/review_outputs.py"
  - "src/squadron/pipeline/summary_context.py"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/cli/commands/review_revise.py"
  - "src/squadron/pipeline/review_revise.py"
  - "src/squadron/data/pipelines/P6.yaml"
  - "src/squadron/data/pipelines/review.yaml"
  - "tests/review/test_review_template_defaults.py"
  - "tests/pipeline/test_loader.py"
  - "tests/pipeline/test_branch_when.py"
  - "tests/pipeline/test_code_pipelines_branching.py"
  - "tests/pipeline/test_builtin_pipelines.py"
  - "tests/benchmark/recall/test_recipe.py"
  - "src/squadron/recipes/recipe_search.py"
  - "src/squadron/benchmark/recall/recipe_dirs.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke36882-haiku-line-1.json"
  - "src/squadron/review/review_client.py"
  - "src/squadron/benchmark/recall/kinds.py"
  - "src/squadron/benchmark/recall/stage_identity.py"
  - "src/squadron/benchmark/recall/scoring_select.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/pipeline/classification.py"
searches:
  - "list_files src/squadron/recipes/**/*.py in ."
  - "list_files src/squadron/data/recipes/** in ."
  - "list_files src/squadron/benchmark/recall/**/*.py in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/** in ."
  - "list_files tests/recipes/** in ."
  - "list_files src/squadron/core/finding_categories.py in ."
  - "grep RecipeReviewCall\\(|RecipeReviewInfo\\(|validate_recipe_review|resolve_review_model_ref|plan_recipe\\(|run_recipe\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep class |def config_key|def content_key|tool_use|template_hash|rules in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "grep ^from |^import |class RecallFinding|class CombDecision in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "grep import squadron|from squadron in /Users/manta/source/repos/manta/squadron/tests/recipes/test_import_boundary.py"
  - "grep class |SCORED_SEVERITIES|def to_dict|stage_section|tools_suppressed|raw_category|findings:|def verdict_from_findings in /Users/manta/source/repos/manta/squadron/src/squadron/review/models.py"
  - "grep def run_review_with_profile|no_tools|rules_content|tools_suppressed|No Tools In This Session|Additional Review Rules|def _ in /Users/manta/source/repos/manta/squadron/src/squadron/review/review_client.py"
  - "grep def verdict_from_findings|def parse_review|### |\\^###|Findings|table|\\| in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep stage_section|\\.recipe\\b|\\.findings\\b|verdict_from_findings|aiRecipe|reviser|feedback in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep structured_findings|\\.findings\\b|feedback in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def structured_findings|def successful_tool_calls|def to_dict|def has_fail|def concern_count|for i, f in enumerate in /Users/manta/source/repos/manta/squadron/src/squadron/review/models.py"
  - "grep def .*ingest|review_ingest|ingest_review in /Users/manta/source/repos/manta/squadron/src"
  - "grep ReviewOutputKey\\.RESPONSE|ReviewOutputKey\\.REVIEW_FILE|INPUT_FILE|feedback.*review|\"review\" in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep def |findings|RESPONSE|review_file|read_text|Findings in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/review_revise.py"
  - "grep def _findings_block|def _latest_review|def _review_findings|findings in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/dispatch.py"
  - "grep review_outputs import|from squadron.pipeline.actions.review_outputs|review_response|def review_response|RESPONSE\\b in /Users/manta/source/repos/manta/squadron/src"
  - "grep ReviewOutputKey|review_response|raw_output|response in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review_revise.py"
  - "grep review_response\\(|ReviewOutputKey\\.RESPONSE|prior_outputs.*response|\\.outputs\\[.response.\\]|outputs\\.get\\(.response. in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def _format_review in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/summary_context.py"
  - "grep def _resolve_model\\b|def _resolve_model_and_profile|def run_review_revise|default_model|template\\.model in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep review-model|review_model|^\\s*model:|default_model|template: (code|slice|tasks|arch)|template: \\w+ in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep REVISE_PIPELINE_BY_KIND|REVISE_PIPELINE_BY_KIND\\s*[:=] in /Users/manta/source/repos/manta/squadron/src"
  - "grep review-model|review_model|P56|P456|shared bod|bodies in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \\\"P6\\\"|'P6'|implement\\.yaml|implement-plan|P56|step with|in step|identical|drift in /Users/manta/source/repos/manta/squadron/tests"
  - "grep shared|in step|same body|bodies|compare.*(P6|implement)|P6.*implement|implement.*P6 in /Users/manta/source/repos/manta/squadron/tests/pipeline"
  - "grep params|review-model|def test_|_SINGLE_SLICE_CODE_PIPELINES|== .*body|steps == in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_builtin_pipelines.py"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \\.reviewers\\b|reviewers=|\\\"reviewers\\\" in /Users/manta/source/repos/manta/squadron"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{rules-line-pass.md,convert.py,RESULTS.md,SUMMARY.md,ANSWERS.md,out/*haiku-line*} in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/**/*haiku-line* in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/* in ."
  - "grep 69\\.1|66\\.9|33\\.4|34\\.8|\\$0\\.13|64\\.7|59\\.7|25\\.7|23\\.8|seconds|minute|hits|not drop|drop|categor|line pass|haiku-line|other in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md"
  - "grep \"category\": null|\"category\": \"None\"|\"category\": \"\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"severity\": \"(CONCERN|FAIL)\"(?:(?!\"category\")[\\s\\S]){0,400}?\\} in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \\\"severity\\\": \\\"(CONCERN|FAIL)\\\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep 4 min|240 s|minutes|wall in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md"
  - "grep \"severity\": \"(CONCERN|FAIL)\",\\n\\s*\"title\": [^\\n]*\\n\\s*\"description\": [^\\n]*\\n\\s*\"file_ref\": [^\\n]*\\n\\s*\"location\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(other|test-debt|architectural-decay|performance-resource|documentation-drift|dependency-config-debt)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"severity\": \"(NOTE|PASS)\",\\n\\s*\"title\": [^\\n]*\\n\\s*\"description\": [^\\n]*\\n\\s*\"file_ref\": [^\\n]*\\n\\s*\"category\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke36882-haiku-line-1.json"
  - "grep recipe_review_request\\(|options=|rules_content=|no_tools=|allowed_tools in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def run_recipe_cli|class CliRecipeReview|recipe_review_request|options|no_tools|rules_content|allowed_tools in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep \"rules_content\"|\"no_tools\"|\"allowed_tools\"|options=|def run_recipe_part|recipe_review_request in /Users/manta/source/repos/manta/squadron/src"
  - "grep def reviewer_output|def live_stage_config|def review_argv|def stage_config|def pending_for|def build_run_bound|def label_candidates|def recipe_outputs|def row_metrics|class CodeKind|def _stage|review_argv|live_stage_config|stage_config\\( in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark"
  - "grep entry_matches|matching_reviews|resolve\\(|StageIdentityResolver|LiveStageResolver|resolver in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark"
  - "grep ConfigFor|config_for in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep name: diff|- name: diff|name: input|name: against|name: files|^\\s*-\\s*name:|allowed_tools|model: in /Users/manta/source/repos/manta/squadron/src/squadron/data/templates"
  - "grep def template_behavior_hash|model|def _behavior in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/identity.py"
  - "grep \"--no-tools\"|\"--rules\"|\"--cwd\"|\"--no-save\"|\"--max\"|\"--dry-run\"|\"--real-work\"|\"--diff\"|\"--producer-only\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep \"--no-tools\"|\"--rules\"|\"--max\"|\"--no-save\"|\"--diff\"|\"--cwd\"|\"-v\"|\"--verbose\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep --dry-run|dry_run in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/run.py"
  - "grep package-data|package_data|force-include|\\[tool\\.hatch|include\\s*=|artifacts|\\[tool\\.setuptools|data/|\\*\\.yaml|\\.md in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep Recipe reviews|review-model|haiku-solr-luna|haiku-sol-luna in /Users/manta/source/repos/manta/squadron"
  - "list_files src/squadron/metrology/recipe_review_models.py in ."
  - "grep Exit\\(code=2\\)|code=2|FAIL.*exit|exit.*FAIL|def _exit_code|exit_code in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep def _exit_on|_exit_on\\(|Verdict\\.FAIL: 2|code=2|Exit\\(code= in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep stage_config\\(|live_stage_config\\(|review_argv\\(|\\.config_key\\b|StageConfig\\(|alias_stage_config\\(|planned_stages\\( in /Users/manta/source/repos/manta/squadron"
  - "grep recipe_hash|config_key ==|== \"[0-9a-f]{64}\"|model_dump in /Users/manta/source/repos/manta/squadron/tests"
  - "grep ^\\[(haiku|haiku-xhigh|sol|sol-r)\\]|^\\[aliases\\.(haiku|haiku-xhigh)\\]|profile\\s*=\\s*\"sdk\"|tool_use|effort in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "list_files project-documents/user/**/420-slices*.md in ."
  - "grep 437 in /Users/manta/source/repos/manta/squadron/project-documents/user"
  - "grep 437|line.pass|line-pass|keep_categories|category filter|pair in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep \"verdict\": \"UNKNOWN\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \\*\\*431|431 |not_gating|keep_categories|record.*gating|gating count|reviewer name|focused in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
sectionsInDocument: 40
sectionsCovered: 39
sectionsNotCovered:
  - "Technical Decisions"
effort: xhigh
turns: 115
promptTokens: 10086651
cachedTokens: 9782068
cacheWriteTokens: 304469
completionTokens: 162845
durationSeconds: 685.3
costUsd: 1.062392
costBasis: provider
runId: run-20261123-p4-deb2dadb
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: verification
    summary: "Walkthrough step 5 cannot produce the stated result"
    location: "src/squadron/cli/commands/review_revise.py:220-224"
  - id: F002
    severity: concern
    category: architecture
    summary: "The plain `sq review code` and `--max` defaults stay on haiku-xhigh, against the Overview claim"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:41"
  - id: F003
    severity: fail
    category: correctness
    summary: "The report scores a no-tools reviewer with tool-enabled outputs of the same alias"
    location: "src/squadron/benchmark/recall/scoring_select.py:49-55"
  - id: F004
    severity: concern
    category: integration
    summary: "Changing `Recipe.reviewers` to specs breaks consumers and tests the design does not list, and no coercion is specified"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:124-125"
  - id: F005
    severity: concern
    category: under-specification
    summary: "The `recipe_hash` canonical form is unspecified, and existing hashes would move"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:124"
  - id: F006
    severity: concern
    category: integration
    summary: "The reviewer call collides with the options it inherits"
    location: "src/squadron/recipes/recipe_runner.py:192-202"
  - id: F007
    severity: concern
    category: architecture
    summary: "The component table omits modules that D1–D8 must change"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:86-99"
  - id: F008
    severity: concern
    category: under-specification
    summary: "`review_argv` cannot receive the reviewer's rules path, and the benchmark's `--rules` call differs from the production composition"
    location: "src/squadron/benchmark/recall/kinds.py:79-97"
  - id: F009
    severity: concern
    category: error-handling
    summary: "The new no-tools call has no hang or timeout strategy"
    location: "src/squadron/recipes/recipe_runner.py:80-91"
  - id: F010
    severity: concern
    category: error-handling
    summary: "Rules-file loading does not cover every unreadable case"
    location: "src/squadron/recipes/recipe.py:65"
  - id: F011
    severity: concern
    category: testing
    summary: "Pinned test: the implement-plan params dict breaks with D10"
    location: "tests/pipeline/test_builtin_pipelines.py:44-55"
  - id: F012
    severity: concern
    category: testing
    summary: "Pinned test: the template-defaults test encodes the old agreement, and its premise is now false"
    location: "tests/review/test_review_template_defaults.py:17-35"
  - id: F013
    severity: concern
    category: testing
    summary: "Pinned test: the shipped-recipe count breaks when the new recipe ships"
    location: "tests/benchmark/recall/test_recipe.py:89-94"
  - id: F014
    severity: concern
    category: correctness
    summary: "The report's not-gating table breaks on titles that contain pipes"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:168"
  - id: F015
    severity: concern
    category: scope
    summary: "Proportionality: the design is heavier than it needs to be"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:125"
  - id: F016
    severity: concern
    category: correctness
    summary: "The value comparison omits the filter-only baseline"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:43"
  - id: F017
    severity: concern
    category: architecture
    summary: "Category gating in production is not reconciled with the architecture"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:172"
  - id: F018
    severity: concern
    category: architecture
    summary: "The public benchmark behind the default change conflicts with a 420 non-goal"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:160"
  - id: F019
    severity: concern
    category: nfr
    summary: "The cost rules are not restated for the paths this slice changes"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:43"
  - id: F020
    severity: pass
    category: architecture
    summary: "The import direction holds"
    location: "tests/recipes/test_import_boundary.py:15-16"
  - id: F021
    severity: pass
    category: verification
    summary: "The measured numbers and the reference artifacts exist as stated"
    location: "project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md:105-106"
  - id: F022
    severity: pass
    category: correctness
    summary: "The D11 \"no category is gating\" rule matches the measured rule on the stored data"
    location: "project-documents/user/reference/review-recall-results/20261122-martian/convert.py:28"
  - id: F023
    severity: pass
    category: verification
    summary: "D2 and D7 hold against the code"
    location: "src/squadron/recipes/model_ref.py:126-139"
  - id: F024
    severity: pass
    category: integration
    summary: "Every reviser, verdict, ingest and summary reader sees only gating findings"
    location: "src/squadron/pipeline/actions/dispatch.py:897-925"
  - id: F025
    severity: note
    category: integration
    summary: "`outputs[RESPONSE]` now carries the Not-gating table, which the design's list of readers omits"
    location: "src/squadron/pipeline/actions/review.py:834"
  - id: F026
    severity: note
    category: scope
    summary: "The design departs from the plan's wording: the filter is a field, not a stage"
    location: "project-documents/user/architecture/420-slices.model-benchmark.md:238"
  - id: F027
    severity: note
    category: documentation
    summary: "The P56 and P456 rationale slightly misstates what they review"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:64"
  - id: F028
    severity: note
    category: structure
    summary: "`recipe_runner.py` is already over the file-size guideline"
    location: "src/squadron/recipes/recipe_runner.py:1"
  - id: F029
    severity: note
    category: hygiene
    summary: "The D11 fixtures carry sandbox paths"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:220"
  - id: F030
    severity: note
    category: verification
    summary: "The walkthrough names a test that D11 never specifies"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:306-310"
  - id: F031
    severity: note
    category: architecture
    summary: "A project recipe with the same name silently shadows the shipped default"
    location: "src/squadron/recipes/recipe_search.py:43-64"
---

# Review: slice — slice 437

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Walkthrough step 5 cannot produce the stated result

`sq review code 100 --max 1` (slice line 327) with no `--model` is expected to give `aiModel: haiku-line-pass` and `aiRecipe: true` (line 329). The `--max` path resolves its reviewer with `_resolve_model(None, template, "code")` (`src/squadron/cli/commands/review.py:706`), which returns `default_model_code`, then `default_model`, then the `code` template's `haiku-xhigh` (`review.py:683-684`). `run_review_revise` then sets `"review-model": reviewer`, which overrides P6's `review-model: haiku-line-pass` from D10. The run uses haiku-xhigh, so the step fails as written. Either pass `--model haiku-line-pass` in the step, or decide that `--max` takes the pipeline's review-model and say so in D10.

### [CONCERN] The plain `sq review code` and `--max` defaults stay on haiku-xhigh, against the Overview claim

The Overview says the shipped code-review defaults switch to the recipe. `sq review code <slice>` with no flag still resolves to the `code` template's `haiku-xhigh` (`src/squadron/data/templates/code.yaml:79`), and `--max` runs with haiku-xhigh (see the previous finding). Excluded (line 65) explains why the template model stays, and that reasoning holds, since `template.model` is in `template_behavior_hash` (`src/squadron/metrology/identity.py:322`). The divergence is still not stated: a user gets two code-review defaults for the same pipeline. Name it in the Overview and in `docs/PIPELINES.md`, or choose to route the CLI default through the pipeline's review-model.

### [FAIL] The report scores a no-tools reviewer with tool-enabled outputs of the same alias

`entry_matches` compares a stored live entry's identity with `resolver.resolve(alias, kind)`. `LiveStageResolver` caches on `(alias, stage_kind)` and calls `live_stage_config(alias, …)` (`src/squadron/benchmark/recall/stage_identity.py:57-61`, `35-44`), which takes `tool_use` from the alias alone. Imported entries match on `entry.alias == alias` alone (`scoring_select.py:52-53`). `_pair_variants` walks `recipe.reviewers` as aliases (`src/squadron/benchmark/recall/scoring.py:146-149`). D8 (lines 180-185) changes `live_stage_config` to take the reviewer spec. That covers `run`, which keys pending stages by slot (`run_plan.py:125-134`). It does not cover the report, which is where the design's numbers come from. For `haiku-line-pass`, stored no-tools entries (tool_use false, rules hash) never match, while any stored tool-enabled or imported `haiku` output is scored as the line pass. The claim at line 184 ("a stored output of haiku with tools is never reused for the line pass") and the report criterion at line 281 are therefore false. Pass the reviewer spec through `StageIdentityResolver.resolve` and its cache key, and add a report test with both a tool-enabled and a no-tools stored `haiku` entry.

### [CONCERN] Changing `Recipe.reviewers` to specs breaks consumers and tests the design does not list, and no coercion is specified

D1 makes `reviewers` a `tuple[ReviewerSpec]`. Consumers that treat entries as strings include `src/squadron/pipeline/classification.py:480` (the pre-run member check, which is not in the component table), `src/squadron/recipes/model_ref.py:97`, `src/squadron/recipes/stage_config.py:113`, `src/squadron/recipes/recipe.py:45-46` and `82`, `src/squadron/recipes/recipe_runner.py:136`, `src/squadron/benchmark/recall/scoring.py:146`, and `run_plan.py:124`. Tests that compare `reviewers` to string tuples include `tests/benchmark/recall/test_recipe.py:99-103` and `111-115` and `tests/recipes/test_model_ref.py:74`. About 60 test constructions of `Recipe(reviewers=("a",))` in `tests/benchmark/recall/`, plus `tests/recipes/test_recipe_runner.py:235` and `test_stage_config.py:57`, break unless a `mode="before"` validator coerces strings to `ReviewerSpec`. Line 123 says a string "is the same as a mapping" but never says Python constructors accept strings. Specify the coercion and list the consumers.

### [CONCERN] The `recipe_hash` canonical form is unspecified, and existing hashes would move

`recipe_hash` is sha256 of `recipe.model_dump(mode="json")` (`src/squadron/recipes/recipe_record.py:102-105`). Changing `reviewers` to specs and adding `keep_categories` changes the dump of every existing recipe, including `reviewers: [haiku-xhigh, sol]`. "Unset options left out" needs a defined form: strings stay strings, and `keep_categories` and reviewer options are omitted when unset. `model_dump(exclude_unset=True)` would also drop the defaulted `pool` and `combs` and change existing hashes. The hash values the design asserts (lines 124, 268) must be recorded before the model change in step 1 (line 352).

### [CONCERN] The reviewer call collides with the options it inherits

`_run_reviewer` calls `review_call(..., **call.options, ...)`. Both entry points already put `rules_content` into `options` (`src/squadron/cli/commands/review_recipe.py:80-84`, `src/squadron/pipeline/actions/review_recipe.py:124-128`), and the CLI also puts `no_tools`. Passing `no_tools=` as a keyword on top of that raises `TypeError: got multiple values for keyword argument`. Even with an override, D3's composition (step rules, then `---`, then reviewer rules, lines 138) must read and join `options["rules_content"]`, which the design does not say. Specify that each reviewer builds its own options dict from `call.options` with `no_tools` and `rules_content` replaced.

### [CONCERN] The component table omits modules that D1–D8 must change

Missing rows: `pipeline/classification.py` (line 480); `recipes/recipe_record.py` (`recipe_hash`, `RecipeRecordFacts`, where `keep_categories` and `not_gating` get written); `recipes/recipe_review.py` (`RecipeReviewRequest`); `cli/commands/review_recipe.py` and `pipeline/actions/review_recipe.py` (the options dicts); `benchmark/recall/scoring_select.py` and `stage_identity.py` (the resolver, see above); `benchmark/recall/run_plan.py` (`ConfigFor`, `_recipe_stages`); and `benchmark/recall/kinds.py` (`RecallKind.review_argv`, with fakes at `tests/benchmark/recall/test_kinds.py:30` and `test_run_end_to_end.py:170`). D6 also needs gating counts on `RecipeStageResult`. `_counts` uses `len(stage.findings)` (`recipe_merge.py:75-77`), and nothing in the design adds the gating count to the stage.

### [CONCERN] `review_argv` cannot receive the reviewer's rules path, and the benchmark's `--rules` call differs from the production composition

`CodeKind.review_argv(case, alias, sq_path, out_path)` builds the `sq review code --diff base --model alias …` argv. D8 adds `--no-tools` and `--rules <path>` (line 184). But `ReviewerSpec` holds loaded content (line 88), not a path, and the sandbox cwd (`--cwd .`) does not hold `line-pass.rules.md`. Say how the path reaches the argv (a protocol change, with `PendingStage` carrying the spec) and which path is passed. Also, `sq review --rules` assembles content differently (`src/squadron/cli/commands/review.py:1369`, `:1515-1518`) from D3's composition. The `rules_hash` identity may then not match what production sends for the same key.

### [CONCERN] The new no-tools call has no hang or timeout strategy

The design adds a second model call per review. `_Run.timed` only logs a WARNING after `slow_after_s` and never cancels the call. The failure cases the design lists (lines 137, 280) are errors, not a provider that never returns. Say that a hung stage blocks the recipe until the provider returns, and note that `pipeline.max_cost_usd` does not bound time. Or add a per-stage timeout as a named config key with a default that is explicit.

### [CONCERN] Rules-file loading does not cover every unreadable case

D3 requires `RecipeError` for a missing, unreadable or empty rules file. `load_recipe` catches only `(OSError, yaml.YAMLError)` (`recipe.py:65`). A rules file that is not UTF-8 raises `UnicodeDecodeError`, which is not caught, and it would escape `classify_review_model` (`src/squadron/recipes/model_ref.py:69-71`) as a traceback. Name the decode error in D3, and add a test with a non-UTF-8 rules file.

### [CONCERN] Pinned test: the implement-plan params dict breaks with D10

`test_implement_plan_params_and_shape` asserts the whole params dict is equal, including `"review-model": "haiku-xhigh"` (line 50). D10 changes that default, so the test fails. The design's only note on pinned tests (line 215) covers the body-drift test, which compares steps and is unaffected. Add this test to D10 and to Technical Requirements (line 286).

### [CONCERN] Pinned test: the template-defaults test encodes the old agreement, and its premise is now false

The test (#378) asserts that every standalone review default equals `PIPELINE_REVIEW_MODEL`, including `code`. D10 leaves the `code` template at haiku-xhigh and moves P6 to the recipe, so the test still passes but says something false. `tests/pipeline/test_loader.py:50-55` has the same problem in its docstring ("the standalone code review runs the reviewer P6's code review runs"). Split the `code` row out with the reason from Excluded (line 65), or update the constant and the docstring.

### [CONCERN] Pinned test: the shipped-recipe count breaks when the new recipe ships

`test_shipped_recipes_are_the_two_with_no_opus_high_comb` asserts `set(shipped) == {"haiku-sol-luna", "haiku-solr-luna"}`. Adding `haiku-line-pass.yaml` to `data/recipes/` fails it. Verification step 1 (line 304) already expects three files, so the test and its `SHIPPED` set must change in the same commit. The `reviewers` assertions at `test_recipe.py:111-115` are covered by the type-change finding above.

### [CONCERN] The report's not-gating table breaks on titles that contain pipes

The "Not gating" table holds model-written titles and locations. A `|` in a title, which is common in code titles, splits the cell. `None` locations render as the literal text `None`. The existing stage table writes raw cells (`src/squadron/recipes/recipe_merge.py:123`). Specify escaping (`\|`) and the empty-value placeholder (`_NO_VALUE`, `recipe_merge.py:44`), and include a pipe-containing title in the parser test at line 168.

### [CONCERN] Proportionality: the design is heavier than it needs to be

(a) D1's tuple of `ReviewerSpec` touches about eight source consumers, about 60 test constructions and the hash (findings above). A parallel `reviewer_options` mapping keyed by alias, empty by default and left out of the hash when empty, meets the same requirement and leaves `reviewers` as strings. Cut the spec tuple. (b) The record fields `RecipeStage.not_gating` (line 253) and `RecipeReview.keep_categories` (line 252) have no consumer in this slice. `not_gating` can be derived from stored findings and `keep_categories`. Defer both to 431 unless 431's plan entry requires them. (c) The measured numbers are repeated in the Overview, Value, the P6 comment (`src/squadron/data/pipelines/P6.yaml:8-13`) and the walkthrough (line 337). Keep them in RESULTS.md and link to it.

### [CONCERN] The value comparison omits the filter-only baseline

The design says the pair "sends the reviser fewer findings that match nothing" and costs "about a cent more a review". Both compare the pair with unfiltered haiku-xhigh (64.7% recall, 25.7% precision). RESULTS.md:40 measures haiku-xhigh with the same five-category filter: 60.4% recall and 37.0% precision. The pair's precision (33.4%, 34.8%, lines 105-106) is below that. Against the filter-only single, the pair buys about 8.7 points of recall (run 1) at a precision cost of about 3.6 points. Name that baseline in the Overview and Value so the PM can choose between the pair and the filter alone.

### [CONCERN] Category gating in production is not reconciled with the architecture

The filter decides which findings set the verdict on every P6 run (slice lines 39, 149-157). The architecture says "Measure, never gate" (420 line 86) and that gating stays in 300's review (420 line 172). The design is within the letter, because the category list is data the PM configures and no pipeline reads benchmark output at run time. The design should say that. It should also say that single-model reviews keep 300's `verdict_from_findings` unchanged.

### [CONCERN] The public benchmark behind the default change conflicts with a 420 non-goal

420 line 160 lists "No public or general-purpose benchmark. Cases come from the project's own history." The shipped default (D10, Overview line 43, Value) rests on 50 public PRs from an external benchmark (`20261122-martian`). The design neither cites the PM decision that accepts this nor says that the squadron-history measurement (430) is still outstanding.

### [CONCERN] The cost rules are not restated for the paths this slice changes

420 sets the cost rules: a production recipe review prints no bound and is bounded by `pipeline.max_cost_usd` (line 43), and a measured run prints its bound and stops at its cap (line 57). This slice changes P6 runs and `sq benchmark recall run`. The design restates only the pending-stage bound (line 281). Restate the production bound for the line pass (it counts against `max_cost_usd`, and a standalone review is uncapped) and the benchmark's stop-at-cap for the new stages.

### [PASS] The import direction holds

`recipes/` imports only `review/`, `metrology/` and `core/`. The new `category_filter.py` needs nothing above `recipes/`. `review/` still does not import `recipes/` (`src/squadron/review/models.py:190-192`). The design's boundary claims match the code.

### [PASS] The measured numbers and the reference artifacts exist as stated

Checked: 69.1% and 66.9% recall, 33.4% and 34.8% precision, $0.13 (lines 105-106). haiku-xhigh's 64.7%/25.7% and 59.7%/23.8% (lines 39, 76). 5 of 90 hits outside the five categories (line 55). 20 seconds for the line pass (line 112) and 4 minutes for haiku-xhigh (line 25). `rules-line-pass.md`, `convert.py`, and the `out/*-haiku-line-1.json` and `*-haiku-xhigh-1.json` files exist.

### [PASS] The D11 "no category is gating" rule matches the measured rule on the stored data

`convert.py` keeps a finding only when `str(f.get("category"))` is one of the five values, so a missing category is excluded there. The design gates it instead (slice line 154). A multi-line search over `out/` found no CONCERN or FAIL finding without a `category` key. No `haiku-xhigh-1` or `haiku-line-1` output has verdict UNKNOWN, so the runner's UNKNOWN drop (`recipe_runner.py:211-223`) never fires on the fixtures. The test would pass on this data, but only because of the data.

### [PASS] D2 and D7 hold against the code

The `no_tools` path exists (`src/squadron/review/review_client.py:133-143`, `236-245`), and the stored line-pass JSON records `tools_suppressed_reason: run-suppressed`. The step-level tool-less refusal and the comb-without-diff refusal exist (`model_ref.py:126-139`). The `slice`, `tasks` and `arch` templates declare no `diff` input (`src/squadron/data/templates/slice.yaml:89-94`, `tasks.yaml:88-93`, `arch.yaml:140-143`), so the pre-run check (`classification.py:470`) agrees with the runtime check.

### [PASS] Every reviser, verdict, ingest and summary reader sees only gating findings

The reviser's `_findings_block` reads `review.findings`, which comes from `structured_findings` (`pipeline/actions/review.py:847`, `review/models.py:509-512`). Review ingest reads the frontmatter, which is built from `structured_findings` (`review/persistence.py:699-704`). The summary reads `result.findings` (`pipeline/summary_context.py:113-116`). D6's claim holds for these readers. A failed line pass also follows 434: `ProviderError` becomes `HARNESS_FAILURE` (`recipe_runner.py:205-209`), and an incomplete recipe with nothing kept is UNKNOWN (`recipe_merge.py:67-72`).

### [NOTE] `outputs[RESPONSE]` now carries the Not-gating table, which the design's list of readers omits

`ReviewResult.raw_output` includes the Recipe section, so the table is in `outputs[RESPONSE]`. Nothing feeds that output to a model, except `review_fold.py:68-69`, which joins it for split reviews. Add `RESPONSE` to D6's list of readers and state that split recipe reviews show the table.

### [NOTE] The design departs from the plan's wording: the filter is a field, not a stage

The plan says "a stage that makes no model call". The design (line 157) makes it a field on the review stage, for stated reasons, and that reasoning holds. The PM should update the plan line so the two documents agree.

### [NOTE] The P56 and P456 rationale slightly misstates what they review

P56 reviews tasks and code (`src/squadron/data/pipelines/P56.yaml:20`, `49`). P456 reviews slices, tasks and code (`P456.yaml:21`, `39`, `68`). The line says "tasks and slice documents" for both. The decision to keep them on haiku-xhigh is sound.

### [NOTE] `recipe_runner.py` is already over the file-size guideline

The file has 323 lines, above the ~300-line guideline. D2, D3 and D5 add to it. When implementing, move the per-reviewer options and the filter call into a helper module.

### [NOTE] The D11 fixtures carry sandbox paths

The stored outputs include the sandbox `input_files.cwd` (for example `out/keycloak-ke36882-haiku-line-1.json:45`, `/private/tmp/claude-501/...`). Copy only the findings, or strip `input_files`, before committing the fixtures.

### [NOTE] The walkthrough names a test that D11 never specifies

Step 2 runs `-k hand_run_entry`, but D11 (line 218) does not name the test. Name it in D11.

### [NOTE] A project recipe with the same name silently shadows the shipped default

`find_recipe` returns the first match, and the shadowing WARNING fires only when two directories hold the name. A project's `project-documents/user/recipes/haiku-line-pass.yaml` would replace the shipped default for P6 with no warning in the pipeline. Mention this in D9 or D3.

### Run Digest

- Response length: 38366 chars
- Response is newline-free: no
- Tool calls made: 114
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 115
- Tokens — prompt / cached / cache write / completion / reasoning: 10086651 / 9782068 / 304469 / 162845 / not computed
- Duration: 685.3 s
- Cost: $1.06 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 31
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 31
- Finding-shaped matches — surviving validation: 31
