---
docType: review
layer: project
reviewType: tasks
slice: line-pass-pair-as-the-code-gate
conventionsSource: none
projectRules: [general.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: 44da99ec0f8ded991df09e9cf74ba55eb920d6cd
reviewedBlob: bd3d012b5c6ecd15e633347a178b7bcdab631c85
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 108
injected:
  - key: input
    path: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md"
    chars: 33537
    sha256: e4fc17198744e4f2e887110816ae6f5b4cb6ead323689a845d274d6ea546bf9c
    whole: true
  - key: against
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 40810
    sha256: 83b35f69f5ddae897ca278fdf7a90562e71b58e40576f0fa95aa1341cc7bcf82
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/recipe_record.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/tools/effective.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/metrology/review_category_map.py"
  - "src/squadron/review/models.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke37429-haiku-line-1.json"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "src/squadron/benchmark/recall/label_candidates.py"
  - "src/squadron/benchmark/recall/report_json.py"
  - "src/squadron/cli/commands/benchmark_recall_run.py"
  - "src/squadron/data/pipelines/P6.yaml"
  - "tests/review/test_review_template_defaults.py"
  - "src/squadron/data/pipelines/review.yaml"
  - "tests/pipeline/test_loader.py"
  - "tests/pipeline/test_builtin_pipelines.py"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/config/__init__.py"
  - "src/squadron/config/keys.py"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "docs/PIPELINES.md"
  - "README.md"
  - "pyproject.toml"
  - "project-documents/user/architecture/420-slices.model-benchmark.md"
  - "src/squadron/pipeline/classification.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/benchmark/recall/import_plan.py"
  - "tests/pipeline/test_code_pipelines_branching.py"
searches:
  - "list_files src/squadron/recipes/*.py in ."
  - "grep no_tools|rules_content|model_allows_tools|RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep No specific findings|Findings Not Parsed|fallback_used|recipe is not None|recipe\\.|def |## Findings in /Users/manta/source/repos/manta/squadron/src/squadron/review/persistence.py"
  - "grep class RecipeReviewInfo|class ReviewFinding|class ReviewResult|SCORED_SEVERITIES|category|raw_category|stage_section|class Verdict|def verdict_from_findings in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "list_files project-documents/user/reference/review-recall-recipes/* in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/**/* in ."
  - "list_files src/squadron/data/{recipes,pipelines}/* in ."
  - "list_files tests/recipes/**/* in ."
  - "grep integration_branch|project_id|recipe record: not written|RECORD_NOT_WRITTEN = in /Users/manta/source/repos/manta/squadron/src"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{rules-line-pass.md,convert.py,RESULTS.md,out/*haiku-line*,out/*haiku*} in ."
  - "grep haiku-line|haiku-r|line-1|line-pass in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/out/*-haiku-{line,r,1}*.json in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/out/*line* in ."
  - "grep line in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md"
  - "grep \"category\": (null|\"\") in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(error-handling|security|testing|performance|design|dry|typing|documentation|concurrency|observability|structure|consistency|project-conventions|test-coverage|style|code-quality|architecture|maintainability|bug|logic)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"other\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep def expand_pending|class RecallRefusal|RecallRefusal\\(|def _pair_variants|def reviewer_output|class ReviewerOutput|def recipe_outputs|def comb_input_findings|def chain_counts|def _reviewer_counts|def _row_cells|class RowJson|class BoundsJson|def entry_matches|def live_stage_config|class StageIdentit\u2026 in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark"
  - "grep expand_pending\\(|bound|def run|print|echo|ConfigFor|live_stage_config|_run_bound|build_bound in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall_run.py"
  - "grep EXPECTED_ROW|findings_per_run|recall_unfiltered|not_gating in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep SHIPPED|shipped_recipes_are_the_two|def test_shipped|haiku-sol-luna|haiku-solr-luna in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_recipe.py"
  - "grep Known recipes|haiku-sol-luna, haiku-solr-luna in /Users/manta/source/repos/manta/squadron/tests"
  - "grep review-model|^\\s*model:|haiku-xhigh|default_model|template: code in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep test_implement_plan_params_and_shape|review-model|haiku-xhigh|def test_standalone_review_default_matches_the_pipeline|def test_review_model_recipe_passes_the_pre_run_check in /Users/manta/source/repos/manta/squadron/tests"
  - "grep default_model_code|DEFAULT_MODEL_CODE|default_model\\b in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def get_config\\b|def get_config\\( in /Users/manta/source/repos/manta/squadron/src/squadron/config"
  - "grep class CallRecord|class ScriptedReviewCall|def __call__|no_tools|rules_content|load_user_aliases|def scripted|kwargs in /Users/manta/source/repos/manta/squadron/tests/recipes"
  - "list_files tests/{cli/test_benchmark_recall_run.py,cli/test_review_recipe.py,benchmark/recall/test_scoring_outputs.py,benchmark/recall/test_report_render.py,benchmark/recall/test_real_work.py,benchmark/recall/test_report_json_schema.py,benchmark/recall/test_label_candidates.py,pipeline/actions/test_review_reci\u2026 in ."
  - "grep _findings_block|def run_recipe_part|def _findings_block in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep luna-r|haiku-xhigh|refused before any model call|haiku-sol-luna|haiku-solr-luna|Each runs two reviewers|review-model. defaults|Recipe reviews|## Recipe|Built-in Pipelines|implement-plan in /Users/manta/source/repos/manta/squadron/docs/PIPELINES.md"
  - "grep haiku-xhigh|haiku-sol-luna|luna-r|refused before any model call in /Users/manta/source/repos/manta/squadron/README.md"
  - "grep ^## \\[Unreleased\\]|^## \\[ in /Users/manta/source/repos/manta/squadron/CHANGELOG.md"
  - "grep \"--no-save\"|\"--dry-run\"|\"--real-work\"|\"--diff\"|\"--files\"|\"--cwd\"|\"-v\"|Exit\\(code=2\\)|exit_code=2|code=2 in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "list_files project-documents/user/{slices,architecture,devlog,recipes}/*{434,420}* in ."
  - "grep Walkthrough|^[0-9]\\. \\*\\*|metrology.project_id|register|cf |fixture repo in /Users/manta/source/repos/manta/squadron/project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md"
  - "grep 437|line-pass in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep \"--files\"|\"--diff\"|\"--no-save\"|Exit\\(code=2\\)|Verdict\\.FAIL|exit\\(2\\)|code=2 in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep real.work in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep ^\\s*(- \\[[ x]\\]|[0-9]+\\.|- )?\\s*\\*{0,2}1[78]\\b|^\\s*\\d+\\.\\s|^\\| 1[78] |^1[78][\\.\\)] in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep P56|P456|in step|CODE_PIPELINES|code pipelines|_CODE_PIPELINES|\"P6\", \"implement\" in /Users/manta/source/repos/manta/squadron/tests"
  - "grep params|review-model|\"model\" in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_code_pipelines_branching.py"
  - "grep \"verdict\": \"UNKNOWN\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep ## Findings|_FINDING|_SECTION|findings_section|in_section|whole|fallback in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep lru_cache|cache\\(|set\\[Recipe|dict\\[Recipe|frozenset\\(.*recipe|\\{recipe\\b|hash\\(recipe|Recipe\\]\\s*=|key=.*recipe in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep model_dump\\(|model_validate\\(.*[Rr]ecipe|RecipeReview\\(|RecipeRef\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep RecallRefusal|except .*Refusal|typer.Exit|exit_code in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall_run.py"
  - "grep ^(reviewers|combs): in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-recipes"
  - "grep ^\\[(haiku|haiku-xhigh|sol|sol-r|luna|luna-r|sonnet|sonnet-high|opus-high|opus|mimo|sol-pool|sonnet-high)\\]|^\\s*profile\\s*=\\s*\"sdk\"|^\\[.*\\]$ in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep review_call|run_review_with_profile|def recipe_review_request|options in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/recipe_review.py"
  - "grep haiku-solr-luna|haiku-sol-luna\\b|data/recipes|\"recipes\"\\)|shipped_recipes_dir|SHIPPED_DIR|== 2\\b.*recipe|recipes\\)\\s*== in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def review_argv|def resolve\\(|--project|def set_config|\"--project\" in /Users/manta/source/repos/manta/squadron/src"
  - "list_files src/squadron/benchmark/recall/{report_build.py,report_render.py,scoring_select.py,stage_identity.py,label_candidates.py,refusal.py} in ."
  - "grep \"max_output_tokens\"|\"tool_use\"|model_fields|\"schema_version\"|\"raw_ref\" in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def _locate_section in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron"
  - "grep recipe_outputs\\(|reviewer_output\\(|chain_counts\\(|stage_config\\(|alias_stage_config\\(|planned_stages\\(|build_recipe_record\\(|undecided_candidates\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep glob\\(|iterdir|RECIPE_SUFFIX|\\.yaml in /Users/manta/source/repos/manta/squadron/src/squadron"
sectionsInDocument: 27
sectionsCovered: 27
effort: xhigh
turns: 109
promptTokens: 9966482
cachedTokens: 9616969
cacheWriteTokens: 349423
completionTokens: 173375
durationSeconds: 717.8
costUsd: 1.138029
costBasis: provider
runId: run-20261123-p5-55b85c9e
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 3's gate cannot pass until Task 5"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:78"
  - id: F002
    severity: concern
    category: existing-code
    summary: "Task 20 changes a test on a false premise"
    location: "tests/review/test_review_template_defaults.py:32"
  - id: F003
    severity: note
    category: existing-code
    summary: "The test_loader docstring stays true"
    location: "tests/pipeline/test_loader.py:51"
  - id: F004
    severity: note
    category: verification
    summary: "The Task 25 grep does not enforce the single-comparison rule"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:289"
  - id: F005
    severity: note
    category: test-design
    summary: "Task 18 has no verdict criterion"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:223"
  - id: F006
    severity: note
    category: verification
    summary: "The \"installed package\" test cannot check the wheel"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:216"
  - id: F007
    severity: note
    category: code-structure
    summary: "Tasks 9 and 11 add code to files already over the size guideline"
    location: "src/squadron/recipes/recipe_runner.py:1"
---

# Review: tasks — slice 437

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 3's gate cannot pass until Task 5

Task 3 adds `reviewer_options` and `keep_categories` to `Recipe` (lines 65–66). `recipe_hash` still dumps the whole model (`src/squadron/recipes/recipe_record.py:104`), so every recipe's hash changes as soon as the fields exist, and Task 2's pins (lines 57–59) fail. Task 3's gate at line 78 requires "Task 2's pins included", but the change that restores them is the canonical form in Task 5 (line 97), which comes later. Move the canonical `recipe_hash` into Task 3, or drop the pins from Task 3's gate and run them at Task 5.

### [CONCERN] Task 20 changes a test on a false premise

Task 20 (lines 240–242) and D10 say the `code` row "no longer equals the pipelines' code reviewer" and must be split out. The test reads no pipeline. It loads each template and asserts `loaded.model == expected` against the constant `PIPELINE_REVIEW_MODEL` (line 18). The `code` template's model stays `haiku-xhigh`, so the test passes unchanged and the split is unnecessary. Its name and docstring ("agree with the pipelines' reviewers") describe a check it does not make. If the intent is a pipeline check, the task should state what it asserts for each pipeline: the new default for P6, implement, implement-plan and review, and `haiku-xhigh` for P56 and P456.

### [NOTE] The test_loader docstring stays true

Task 20 says to correct the docstring that the standalone code review runs P6's reviewer. After the change `review.yaml` and P6 both use `haiku-line-pass`, and the assertion at line 55 compares them, so the docstring stays true. Drop the correction. `sq review code` with no `--model` still runs `haiku-xhigh` (D10), which this docstring does not describe.

### [NOTE] The Task 25 grep does not enforce the single-comparison rule

`grep -rnE "in [A-Za-z_.]*keep_categories"` only matches a literal `in ...keep_categories`. A comparison through a local (`keep = recipe.keep_categories`, then `if f.category in keep`) or a parameter passes. The design's rule, that `split_by_category` is the only place a category is compared with the kept list, needs a check that also finds `in keep` in the runner, scoring and real-work modules, or a review of those call sites.

### [NOTE] Task 18 has no verdict criterion

The runner drops every finding of a reviewer whose verdict is UNKNOWN (`src/squadron/recipes/recipe_runner.py:211-223`). `convert.py` does not check the verdict, so `expected.json` would include findings the test never gates. No stored `haiku-xhigh-1` or `haiku-line-1` output in the pool has an UNKNOWN verdict, so this is latent. Task 18 should exclude UNKNOWN-verdict outputs when it chooses the five PRs.

### [NOTE] The "installed package" test cannot check the wheel

A pytest run from a checkout loads `src/squadron/data`, not an installed wheel, so the test at line 216 says nothing about packaging. The `unzip -l` check at line 217 is the only evidence that the `.md` file ships, and it is not repeatable in CI. Rename the test as a data-directory test and keep the wheel check as a one-time step. Hatch builds `packages = ["src/squadron"]` (pyproject.toml), so the file should ship.

### [NOTE] Tasks 9 and 11 add code to files already over the size guideline

`recipe_runner.py` is 322 lines. Task 9 keeps `split_by_category` in `kept_findings.py`, as planned, but the `_run_chain` changes and the `ReviewerOutcome.not_gating` plumbing have no named helper. Task 11 adds a branch to `format_review_markdown` (`src/squadron/review/persistence.py:547`), which runs to about line 848. Put the Not gating line in a helper beside `_findings_not_parsed_section`.

### Run Digest

- Response length: 22570 chars
- Response is newline-free: no
- Tool calls made: 108
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 109
- Tokens — prompt / cached / cache write / completion / reasoning: 9966482 / 9616969 / 349423 / 173375 / not computed
- Duration: 717.8 s
- Cost: $1.14 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
