---
docType: review
layer: project
reviewType: slice
slice: line-pass-pair-as-the-code-gate
conventionsSource: none
projectRules: [general.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: f0dfa40798c9124c5d38060ce82aea0f23007bb8
reviewedBlob: 5ff55e64e19b62a05a713da5769ffdf139a98f9b
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 130
injected:
  - key: input
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 38431
    sha256: dd33a004e988b998c57970f12b777599efa062f5f3fc070e5cc4ccfd78d502f0
    whole: true
  - key: against
    path: "project-documents/user/architecture/420-arch.model-benchmark.md"
    chars: 31474
    sha256: 14438c0ae92b1d7b02c021335251b804b3674dbcd002028fddb62ca56d9b3f52
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/recipes/recipe_record.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/recipes/recipe_review.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/pipeline/loader.py"
  - "src/squadron/pipeline/classification.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/data/pipelines/P6.yaml"
  - "src/squadron/data/pipelines/implement.yaml"
  - "src/squadron/data/pipelines/review.yaml"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/cli/commands/review_revise.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "src/squadron/metrology/review_category_map.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/benchmark/recall/stage_identity.py"
  - "src/squadron/benchmark/recall/scoring_select.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/kinds.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke37429-haiku-line-1.json"
  - "tests/cli/commands/test_run.py"
  - "tests/pipeline/test_builtin_pipelines.py"
  - "tests/review/test_review_template_defaults.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/recipes/recipe_search.py"
  - "tests/recipes/test_import_boundary.py"
  - "src/squadron/providers/sdk/provider.py"
  - "src/squadron/metrology/recipe_review_models.py"
  - "project-documents/user/architecture/420-slices.model-benchmark.md"
  - "tests/pipeline/test_classification.py"
  - "tests/metrology/test_recipe_review_models.py"
searches:
  - "list_files src/squadron/recipes/**/*.py in ."
  - "list_files src/squadron/benchmark/recall/**/*.py in ."
  - "list_files src/squadron/data/recipes/** in ."
  - "list_files tests/recipes/**/*.py in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/** in ."
  - "grep class StageConfig|def config_key|rules_hash|tool_use|class StageKind|class CombVerdict|class RecallFinding|category|def content_key|SCORED_SEVERITIES in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "grep no_tools|rules_content|def run_review_with_profile|tools_suppressed_reason|No Tools In This Session in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def resolve_effective_tools|def should_inject_file_bodies in /Users/manta/source/repos/manta/squadron/src"
  - "grep resolve_review_model_ref|validate_recipe_review|classify_review_model|check_recipe_members|no_tools= in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep _classify_recipe\\(|no_tools = |no_tools=|allowed_tools=|recipe_spent|class _PartSettings in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep _classify_recipe|allowed_tools = |allowed_tools:  in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep review-model|haiku-xhigh|model: |model: in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep \"--cwd\"|\"--no-save\"|\"--dry-run\"|\"--real-work\"|\"--max\"|\"--diff\"|default_model_code|default_model\\b in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep def run_review_revise|def _revise_round|recipe|Recipe in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep def run_review_revise in /Users/manta/source/repos/manta/squadron/src"
  - "grep model|recipe|review_recipe|run_review|no_tools|rules in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review_revise.py"
  - "grep aiRecipe|aiModel|recipe in /Users/manta/source/repos/manta/squadron/src/squadron/review/persistence.py"
  - "grep ### \\[|\\^###|_FINDING|def parse_findings|def parse_review|findings_section|## Findings|\\\\\\[|severity_re|re\\.compile in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep feedback in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/dispatch.py"
  - "grep def _findings_block|def _latest_review|def review_input_files in /Users/manta/source/repos/manta/squadron/src"
  - "grep _pair_variants|def reviewer_output|def _reviewer|matching_reviews\\(|\\.resolve\\(|resolver in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep config_for|live_stage_config|ConfigFor|review_argv|def  in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/live_services.py"
  - "grep def check|install_location|output_dir|transcript|glob|rglob|read_text in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/leak_check.py"
  - "grep \"--rules\"|\"--no-tools\"|def review_code|def review_slice|def review_tasks|def review_arch in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{rules-line-pass.md,convert.py,RESULTS.md,SUMMARY.md,ANSWERS.md} in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/out/*haiku-line* in ."
  - "grep RULES_SEPARATOR\\s*=|^RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src/squadron/review/rules.py"
  - "grep \"(verdict|severity|category|location|tool|model|answering_model|findings)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke37429-haiku-line-1.json"
  - "grep 64\\.7|59\\.7|25\\.7|23\\.8|60\\.4|37\\.0|69\\.1|66\\.9|33\\.4|34\\.8|\\$0\\.1|5 of|90 hits|hits|spread|paired|line pass|haiku-line|haiku-xhigh in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md"
  - "grep template: code|template: \"code\"|template: judge|code in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep ^model:|^name:|template_hash|model: haiku in /Users/manta/source/repos/manta/squadron/src/squadron/data/templates/code.yaml"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron/tests"
  - "grep review-model|review_model|P6|implement in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_builtin_pipelines.py"
  - "grep P6|review-model|docstring|reviewer|standalone in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_loader.py"
  - "grep def template_behavior_hash|model in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/identity.py"
  - "grep ReviewerOutcome\\(|RecipeReview\\(|StageConfig\\(|review_argv|config_for|live_config_for|plan_config_for|def resolve\\(|\\.resolve\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep recipe_hash|config_key in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def resolve\\(|def review_argv|def config_for|def live_config_for|def plan_config_for|config_for=|class StubResolver|class .*Resolver|ConfigFor|lambda alias, kind|lambda alias, stage|ImportOnlyResolver\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep COLUMNS|Kept/review|Raw findings/review|len\\(row|split\\(\"\\|\"\\)|\\| Recipe|Dropped/review in /Users/manta/source/repos/manta/squadron/tests"
  - "grep RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep allowed_tools|disallowed|tools=|setting_sources|can_read_files in /Users/manta/source/repos/manta/squadron/src/squadron/providers"
  - "grep Exit\\(code=2\\)|exit_code_for|EXIT_REVIEW_FAILED|def _exit_for_verdict|Verdict.FAIL in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep P6|implement|CODE|\"code\"|ReviewTemplate|BuiltinReviewTemplate\\.CODE|_PIPELINE|pipeline_name in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review_revise.py"
  - "grep diff = |diff=|slice_info\\b.*=|resolve_slice_diff|slice_diff|base_ref|merge.base|_derive_diff|diff_for_slice in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep def entry_key|def run_record_id|def chain_key|def comb_slot|def is_live|is_live in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "grep 437|line-pass|line pass|keep_categories|category filter in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep package-data|package_data|force-include|include|artifacts|\\[tool\\.hatch|\\[tool\\.setuptools|build-backend|\\*\\.yaml|\\*\\.md in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep SHIPPED|test_shipped_recipes|def test_ in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_recipe.py"
  - "grep \\| Stage \\||Recipe `|## Recipe|stage_section|render_stage_section|No specific findings|Findings\\b.*==|RECIPE_SECTION_HEADING in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \"category\": \"(error-handling|observability|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|security|documentation|concurrency|uncategorized|style|code-quality)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": null in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(error-handling|observability|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|security|documentation|concurrency|uncategorized|style|code-quality)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": null in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"correctness\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep lru_cache|functools.cache|@cache\\b|set\\[RecipeRef|frozenset\\(.*recipe|\\{ref\\}|hash\\(recipe|hash\\(ref|dict\\[RecipeRef|dict\\[Recipe|Recipe\\]\\s*=|RecipeRef\\)\\s*: in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep name: diff|diff|required_inputs|optional_inputs|^  - name:|^- name: in /Users/manta/source/repos/manta/squadron/src/squadron/data/templates"
  - "grep \"P6\"|'P6'|\"implement\"|\"review\"\\)|load_pipeline\\(\"review\"|haiku-solr-luna|haiku-sol-luna in /Users/manta/source/repos/manta/squadron/tests"
  - "grep Known recipes|known recipes|known: |shipped_recipes_dir\\(\\)\\)|glob\\(\"\\*\\.yaml\"\\)|set\\(shipped\\)|== \\{\"haiku in /Users/manta/source/repos/manta/squadron/tests"
  - "grep model_dump|model_fields|keys\\(\\) ==|== set\\(|sorted\\(.*fields|json.loads\\(.*\\)\\) ==|to_dict\\(\\) ==|== \\{\"record_type\" in /Users/manta/source/repos/manta/squadron/tests"
  - "grep model_dump|model_fields|StageConfig|rules|tool_use in /Users/manta/source/repos/manta/squadron/tests/metrology/test_recipe_review_models.py"
  - "grep _unused in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/support.py"
  - "grep expand_pending\\(|_recipe_stages\\(|planned_stages\\(|plan_recipe\\(|alias_stage_config\\(|stage_config\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def high\\(|def config_for|def high in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep data_dir\\(\\) / \"recipes\"|\"data\" / \"recipes\"|data/recipes|recipes_dir\\(\\)|\\.md\"\\)\\.glob|rglob\\(\"\\*\"\\)|package data|MANIFEST in /Users/manta/source/repos/manta/squadron/tests"
  - "grep ^\\[(haiku|haiku-xhigh)\\]|^(model|profile|tool_use|effort|max_output_tokens)\\s*=|^\\[haiku in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep review-model|template:|review: in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines/P56.yaml"
  - "grep review-model|template:|review: in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines/P456.yaml"
  - "grep recipe_sink in /Users/manta/source/repos/manta/squadron/src"
  - "grep \"category\": \"other\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep Recipe reviews|recipe|haiku-xhigh in /Users/manta/source/repos/manta/squadron/docs/PIPELINES.md"
  - "grep ReviewOutputKey.RESPONSE|RESPONSE:|\\bRESPONSE\\b.*=|\"response\" in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def to_dict|\"findings\"|payload\\[\"findings\"\\] in /Users/manta/source/repos/manta/squadron/src/squadron/review/models.py"
  - "grep ReviewerOutcome\\( in /Users/manta/source/repos/manta/squadron"
sectionsInDocument: 40
sectionsCovered: 40
effort: xhigh
turns: 131
promptTokens: 19241313
cachedTokens: 18877918
cacheWriteTokens: 363207
completionTokens: 169095
durationSeconds: 724.2
costUsd: 1.606058
costBasis: provider
runId: run-20261123-p4-deb2dadb
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "`ConfigFor`'s optional options argument cannot hold for existing two-argument fakes"
    location: "tests/benchmark/recall/test_stage_runner.py:236"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "A test pins the exact shipped-recipe list and the design does not update it"
    location: "tests/pipeline/test_classification.py:1206"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`load_recipe` leaves the recipe file's own `UnicodeDecodeError` unhandled"
    location: "src/squadron/recipes/recipe.py:63"
  - id: F004
    severity: concern
    category: design-spec
    summary: "A review where every CONCERN is not gating is written with \"No specific findings.\""
    location: "src/squadron/review/persistence.py:765-800"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "The \"table rows are not findings\" test misses the case where the parser scans the whole file"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:210"
  - id: F006
    severity: concern
    category: correctness
    summary: "The benchmark's rules identity can drift from the rules actually read"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:227"
  - id: F007
    severity: concern
    category: scope
    summary: "Scope exceeds the plan's success criteria, and some prose restates other documents"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:214"
  - id: F008
    severity: concern
    category: design-spec
    summary: "The Overview says the recipe runs \"anywhere a code review runs\", but D7 refuses one kind of code review"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:52"
  - id: F009
    severity: note
    category: docs
    summary: "Stale defaults in docs/PIPELINES.md are not in D10's list"
    location: "docs/PIPELINES.md:1030"
  - id: F010
    severity: note
    category: consistency
    summary: "The rules separator is written as a literal"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:175"
  - id: F011
    severity: note
    category: design-spec
    summary: "The no-tools notice promises file contents that an SDK no-tools reviewer does not get"
    location: "src/squadron/review/review_client.py:124"
  - id: F012
    severity: note
    category: docs
    summary: "The recipe merge docstring says the reviser reads the review file"
    location: "src/squadron/recipes/recipe_merge.py:5"
  - id: F013
    severity: note
    category: error-handling
    summary: "The pre-run check does not refuse a code-template step that has no diff"
    location: "src/squadron/pipeline/classification.py:470"
  - id: F014
    severity: note
    category: design-spec
    summary: "420's amendment that limits production changes is not cited"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:66"
  - id: F015
    severity: pass
    category: correctness
    summary: "The measured numbers in the Overview match RESULTS.md"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:58"
  - id: F016
    severity: pass
    category: correctness
    summary: "The no-tools SDK path withholds every tool"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:165"
  - id: F017
    severity: pass
    category: correctness
    summary: "The pre-run check refuses recipes on slice, tasks and arch reviews"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:222"
  - id: F018
    severity: pass
    category: test-coverage
    summary: "The stored haiku outputs use canonical categories for D11's fixture"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:275"
---

# Review: slice — slice 437

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] `ConfigFor`'s optional options argument cannot hold for existing two-argument fakes

D4 (design line 184) says the options parameter is optional everywhere it is added, including `ConfigFor`, so existing two-argument callers are unchanged. `ConfigFor` is a `Callable[[str, StageKind], ...]` alias (`benchmark/recall/run_plan.py:33`), and a callable type has no optional third parameter. If `_recipe_stages` passes the reviewer's options as a third argument (`run_plan.py:125,140`), the local `high(alias, kind)` at `test_stage_runner.py:236`, passed to `expand_pending` at line 239, raises `TypeError`. That fake is not in D8's test-double list (design line 228). Either pass options only when a reviewer has them, or name `high` in D8 and state the call shape.

### [CONCERN] A test pins the exact shipped-recipe list and the design does not update it

`test_recipe_no_longer_shipped_is_refused_at_the_pre_run_check` asserts the exact string `Known recipes: haiku-sol-luna, haiku-solr-luna.`. Adding `haiku-line-pass.yaml` to `data/recipes/` (D9) changes that to `haiku-line-pass, haiku-sol-luna, haiku-solr-luna`, so the test fails. D9 (design line 257) names only `test_recipe.py`'s SHIPPED set, and D10's pinned list (lines 266-269) does not cover this test.

### [CONCERN] `load_recipe` leaves the recipe file's own `UnicodeDecodeError` unhandled

`load_recipe` reads the YAML with `path.read_text(encoding="utf-8")` inside `except (OSError, yaml.YAMLError)`. A non-UTF-8 recipe raises `UnicodeDecodeError`, a `ValueError`. `classify_review_model` catches only `RecipeError` (`recipes/model_ref.py:69-71`), and the pre-run check catches only `ReviewModelError` (`pipeline/loader.py:500`), so the error escapes as a traceback rather than a named `RecipeError`. D3 (design line 174) handles this error for rules files only, but the design changes `load_recipe` and should cover the recipe's own read as well.

### [CONCERN] A review where every CONCERN is not gating is written with "No specific findings."

When `result.findings` is empty, persistence skips the `## Findings` heading and writes `No specific findings.` (line 800) after the Recipe section. Under D6 (design lines 199-216) that is the normal result of a PASS with not-gating CONCERNs. The file then shows a table of CONCERN rows and says there are no findings. The design does not specify this wording. Give the not-gating case its own line, for example "No gating findings; N not gating, see the Recipe section."

### [CONCERN] The "table rows are not findings" test misses the case where the parser scans the whole file

D6 relies on the parser ignoring table rows (design line 208). That holds only while a `## Findings` heading exists, because `_locate_section` limits the scan to it. Without the heading, the whole response is scanned (`review/parsers.py:796-800`). The bullet alternative of `_FINDING_RE` (`parsers.py:100`) is case-insensitive and not anchored to line start, so a not-gating title containing `- [CONCERN] ` or `### CONCERN ` would be read as a finding. Under D6's own rule, a review with no gating finding has no `## Findings` heading (previous finding), so that is the case that matters. The test at line 210 should use a review with no gating finding and such a title.

### [CONCERN] The benchmark's rules identity can drift from the rules actually read

`rules_hash` is taken when the recipe loads at run start (D4, line 181). Each `sq review code` subprocess gets `--rules <rules_path>` (line 227) and reads the file again on every stage call (`cli/commands/review.py:1499`). If the file is edited during a `sq benchmark recall run`, which takes about four minutes per stage, later stages run on the new content but are keyed with the old hash. Stored outputs then no longer match the content that produced them. Write the hashed bytes into each stage's scrubbed home and pass that path, or hash what each stage reads.

### [CONCERN] Scope exceeds the plan's success criteria, and some prose restates other documents

Plan entry 18's criteria (`420-slices.model-benchmark.md:236-251`) ask for the reviewer options and identity, the filter, scoring in 430's report with recall before and after, the fixture test, the four defaults, and the rules file. They do not ask for the following, which can be cut or deferred:
- (a) The real-work "Not gating/review" column and `RecipeReview.keep_categories` (D6 line 214, D8 line 231, walkthrough step 6). The design itself calls this part of #391. Defer it to #391.
- (b) D8's run-side plumbing (line 227-228: `ConfigFor` options, `PendingStage.options`, `review_argv`, `--no-tools` and `--rules` in argv). Identity and the report do not need it. Keep it only if the PM's measurement should start soon, and say so.
- (c) The measured-number table and prose (lines 54-64) and the amendment restatement (lines 66-68). Cut them to a pointer to RESULTS.md and 420.
- (d) "Patterns and Conventions" (lines 278-279) restates D1's field-name point.

### [CONCERN] The Overview says the recipe runs "anywhere a code review runs", but D7 refuses one kind of code review

`sq review code --files <glob>` with no diff is a code review (`cli/commands/review.py:1462` accepts `files` alone). `validate_recipe_review` refuses a recipe with `keep_categories` or a `tools: false` reviewer on any review with no diff (D7, line 221; `recipes/model_ref.py:105-139`). Name which code reviews run the recipe, or say that the `--files` form is refused.

### [NOTE] Stale defaults in docs/PIPELINES.md are not in D10's list

The P6 parameter table gives `review-model | haiku-xhigh` (line 1030), and line 1059 says `review-model` "defaults to `haiku-xhigh`, matching `P6`". The documentation requirement (design line 345) says only that the doc "describes ... the new pipeline default". Name these two lines.

### [NOTE] The rules separator is written as a literal

D3 joins the step's rules and the reviewer's rules with `---`. The codebase already defines `RULES_SEPARATOR = "\n\n---\n\n"` (`src/squadron/project_rules/render.py:29`) and uses it in `review/rules.py:272`. Reuse the constant so the value has one definition.

### [NOTE] The no-tools notice promises file contents that an SDK no-tools reviewer does not get

`NO_TOOLS_NOTICE` says "The request contains the diff and the file contents you will get." `haiku` runs on the SDK profile, where `can_read_files=True` (`providers/sdk/provider.py:64`), so `should_inject_file_bodies` returns False (`review/tool_support.py:42-43`) and no file bodies are sent. The design's Special Considerations (line 419) correctly says the line pass gets the diff, but the notice misdescribes what the model holds. The measured run had the same prompt, so the result is unaffected. The design makes this path load-bearing, so the wording should be fixed or called out.

### [NOTE] The recipe merge docstring says the reviser reads the review file

The docstring says "the reviser reads the review file". The reviser's feedback is built from the review action's findings (`pipeline/actions/dispatch.py:897-919`). D6's guarantee that the reviser never sees a not-gating finding depends on the findings path, so the docstring will mislead the implementer. Correct it in the same change.

### [NOTE] The pre-run check does not refuse a code-template step that has no diff

The pre-run check passes `has_diff=template_takes_diff(template)`, which is true for `code` whatever the step supplies. A step such as `review: {template: code, model: haiku-line-pass, files: ...}` with no diff passes `sq run --dry-run` and is refused only at run time (`pipeline/actions/review.py:312-318`). D7 (line 222) and walkthrough step 3 (line 373) say the refusal happens before any model call, which is true, but not at the pre-run check. Say so, or derive `has_diff` from the step's inputs.

### [NOTE] 420's amendment that limits production changes is not cited

420's Amendment (20261118) limits production behaviour changes to "the review action and its pre-run check, `sq review`, and the review file's frontmatter" (`420-arch.model-benchmark.md:40-41`). This slice also changes the review file's body (the Not-gating table, D6), the default model of four pipelines (D10), and what the summarizer reads. All of that is arguably the review path, but the Architecture section never checks it against the amendment. Cite the amendment and state that the body change is within the review path.

### [PASS] The measured numbers in the Overview match RESULTS.md

I checked RESULTS.md lines 39-41, 75-76, 85-87 and 105-106: recall 64.7% and 59.7%, precision 25.7% and 23.8% for haiku-xhigh; 60.4% and 37.0% with the filter; 69.1% and 66.9% recall and 33.4% and 34.8% precision for the pair; $0.12 and $0.13 a review. The derived deltas (4.4, 7.2, about 8, about 11, 8.7, 3.6 points) are arithmetically correct.

### [PASS] The no-tools SDK path withholds every tool

`resolve_effective_tools` empties the list when `suppressed` is set (`tools/effective.py:63-64`). The SDK provider sets `tools=[]` for an empty allowed list and installs `deny_every_tool` (`providers/sdk/provider.py:99-110, 131-136`). So D2's claim that the line pass has no tools to read anything else holds.

### [PASS] The pre-run check refuses recipes on slice, tasks and arch reviews

`_review_recipe_row` passes `has_diff=template_takes_diff(template)` (`pipeline/classification.py:465-473`). The `slice`, `tasks` and `arch` templates declare no `diff` input, and `code.yaml:94` does. So D7's refusal happens at the pre-run check for those templates.

### [PASS] The stored haiku outputs use canonical categories for D11's fixture

I searched the `haiku-*` outputs for historical category strings (`testing`, `security`, `error-handling`, `dry` and similar) and for `"category": null`. Neither appears, and `other` appears in several PRs, so the fixture can exercise the `other` rule. D5's no-category rule therefore gives the same answer as the measurement on this data.

### Run Digest

- Response length: 38129 chars
- Response is newline-free: no
- Tool calls made: 130
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 131
- Tokens — prompt / cached / cache write / completion / reasoning: 19241313 / 18877918 / 363207 / 169095 / not computed
- Duration: 724.2 s
- Cost: $1.61 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18

## Resolution

Design revised 20261123 after this review. No further review was run.

- **`ConfigFor`'s optional options argument cannot hold for two-argument fakes** — Resolved by removal. The benchmark's run-side support for reviewers with options is deferred to #393, so `ConfigFor`, `live_stage_config`, `StageIdentityResolver.resolve`, `PendingStage` and `review_argv` keep their signatures and no test double changes (D4, D8).
- **A test pins the exact shipped-recipe list** — Applied. D9 names `tests/pipeline/test_classification.py`, `test_recipe_no_longer_shipped_is_refused_at_the_pre_run_check`, and Technical Requirements lists the classification tests.
- **`load_recipe` leaves the recipe file's own `UnicodeDecodeError` unhandled** — Applied. D3 has the recipe file's read raise `RecipeError`, with a test and a success criterion.
- **A review where every CONCERN is not gating is written with "No specific findings."** — Applied. D6: the file gets "No gating findings; N not gating (see the Recipe section)." `RecipeReviewInfo.not_gating` carries the count; `review/models.py` and `review/persistence.py` are in the component table.
- **The "table rows are not findings" test misses the whole-file scan** — Applied. D6: a recipe review with a "Not gating" table always has the `## Findings` heading, so the parser's scan stays in that section. The test now uses a review with no gating finding and a title holding `|` and `- [CONCERN] `.
- **The benchmark's rules identity can drift from the rules actually read** — Deferred with the run-side support to #393, which records the requirement that a stage reads the bytes that were hashed. In this slice `sq benchmark recall run` refuses a recipe whose reviewers have options.
- **Scope exceeds the plan's success criteria, and some prose restates other documents** —
  - (a) Rejected. The real-work column and `RecipeReview.keep_categories` stay: without them the real-work table counts not-gating findings as kept, which was the previous round's FAIL.
  - (b) Applied. Run-side plumbing deferred to #393; `run` refuses and the report matches a reviewer with options to no stored entry (D8). The PM's benchmark run after the slice goes through `sq review code` and does not need it.
  - (c) Rejected. The filter-only baseline, the run count and spread, and the public-benchmark statement were each required by a finding of the two earlier rounds.
  - (d) Applied. "Patterns and Conventions" removed.
- **The Overview says the recipe runs "anywhere a code review runs"** — Applied. The Overview now says any code review that has a diff, and that `sq review code --files` with no diff is refused.
- **Stale defaults in docs/PIPELINES.md** — Applied. Technical Requirements names the P6 parameter table row and the "defaults to `haiku-xhigh`, matching `P6`" sentence.
- **The rules separator is written as a literal** — Applied. D3 uses the existing `RULES_SEPARATOR`.
- **The no-tools notice promises file contents an SDK no-tools reviewer does not get** — Called out in Special Considerations. The notice is not changed: it is the prompt the measured line pass ran with and is shared by every no-tools review.
- **The recipe merge docstring says the reviser reads the review file** — Applied. The component table has the docstring corrected in the same change.
- **The pre-run check does not refuse a code-template step that has no diff** — Applied as a statement in D7: such a step passes the pre-run check and is refused when it runs, before any model call.
- **420's amendment that limits production changes is not cited** — Applied. The Overview cites the 20261118 amendment and says the review file body change and the pipeline defaults are on the review path.
- **The measured numbers in the Overview match RESULTS.md** (pass) — No change.
- **The no-tools SDK path withholds every tool** (pass) — No change.
- **The pre-run check refuses recipes on slice, tasks and arch reviews** (pass) — No change.
- **The stored haiku outputs use canonical categories for D11's fixture** (pass) — No change.
