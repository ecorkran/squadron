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
reviewedSha: 0515650c49a02e1e53ed6e02d14fd3fad8f92867
reviewedBlob: 2200a7d5ccc8bc734f0e1b3ab7eb09f33fa21ab3
reviewedBlobCurrent: false
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 103
injected:
  - key: input
    path: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md"
    chars: 31837
    sha256: f3722a1dbaba19931da7e772e4f12c82263dccc3fcbad4d7871a0f96b3452ddd
    whole: true
  - key: against
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 40210
    sha256: de62be0097a6a1ffdd45c968ced27cc11789592cc1b6c2c6ef0376b70b27fe51
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/recipes/recipe_record.py"
  - "tests/recipes/support.py"
  - "src/squadron/metrology/recipe_review_models.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/benchmark/recall/label_candidates.py"
  - "src/squadron/benchmark/recall/report_json.py"
  - "tests/review/test_review_template_defaults.py"
  - "tests/benchmark/recall/test_recipe.py"
  - "src/squadron/data/pipelines/P6.yaml"
  - "tests/recipes/test_import_boundary.py"
  - "tests/recipes/test_stage_config.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/data/models.toml"
  - "project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/metrology/review_category_map.py"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "tests/cli/commands/test_run.py"
  - "docs/PIPELINES.md"
  - "README.md"
  - "src/squadron/pipeline/loader.py"
  - "src/squadron/pipeline/classification.py"
  - "src/squadron/pipeline/prompt_renderer.py"
  - "src/squadron/pipeline/actions/review.py"
  - "tests/pipeline/test_classification.py"
searches:
  - "list_files src/squadron/recipes/*.py in ."
  - "list_files src/squadron/data/recipes/* in ."
  - "list_files project-documents/user/reference/review-recall-recipes/* in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/** in ."
  - "list_files tests/recipes/**/* in ."
  - "list_files tests/benchmark/recall/*.py in ."
  - "grep def config_key|class StageConfig|class RecallFinding|class StageKind|def content_key|SCORED_SEVERITIES in /Users/manta/source/repos/manta/squadron/src"
  - "grep no_tools|rules_content|def run_review_with_profile in /Users/manta/source/repos/manta/squadron/src/squadron/review/review_client.py"
  - "grep model_allows_tools|no_tools|rules_content|run_recipe\\(|RecipeReviewCall\\(|options= in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep _locate_section|re\\.compile|_BULLET|_HEADING|def parse_findings|def _scan|Findings Not Parsed|No specific findings|No gating in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep if result\\.findings:|fallback_used|degraded|No specific findings|Findings Not Parsed|stage_section|recipe\\b|## Findings|## Recipe|def  in /Users/manta/source/repos/manta/squadron/src/squadron/review/persistence.py"
  - "grep class RecipeReviewInfo|stage_section|not_gating|class ReviewFinding|category|raw_category in /Users/manta/source/repos/manta/squadron/src/squadron/review/models.py"
  - "grep def |^class |^[A-Z_]+ =  in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/scoring.py"
  - "grep def entry_matches|def matching_reviews|def matching_chains|def identity_of|class StageIdentityResolver|def resolve|def live_stage_config|ConfigFor|class PendingStage|def review_argv|def comb_input_findings|def expand_pending|class RecallRefusal|def planned_stages|def _pair_variants in /Users/manta/source/repos/manta/squadron/src"
  - "grep def entry_matches|def matching_reviews|def matching_chains|def identity_of|class StageIdentityResolver|def live_stage_config|^ConfigFor|class ConfigFor|class PendingStage|def review_argv|def comb_input_findings|def expand_pending|class RecallRefusal|class StageIdentity\\b|def resolve\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep expand_pending\\(|bound|RecallRefusal|def recall_run|def run\\( in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep expand_pending\\(|bound_line|def bound|print_bound|\\.bound\\(|typer\\.echo\\(.*bound in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep class RowJson|class BoundsJson|findings_per_run|recall_|EXPECTED_ROW|not_gating|def |label_candidates|candidates in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep EXPECTED_ROW|BoundsJson|RowJson|def test_ in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_report_json_schema.py"
  - "grep SHIPPED|test_shipped_recipes_are_the_two|Known recipes|haiku-xhigh|review-model|review_model|test_standalone_review_default_matches_the_pipeline|test_implement_plan_params_and_shape|standalone code review|P6's reviewer|test_review_model_recipe_passes_the_pre_run_check|test_recipe_no_longer_shipped in /Users/manta/source/repos/manta/squadron/tests"
  - "grep review-model|implement_plan_params|def test_implement_plan|\\\"model\\\"|P6|implement-plan in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_builtin_pipelines.py"
  - "grep review-model|model:|template:|comment|^#|haiku-xhigh in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep review-model|review_model|template\\.model|default_model_code|def _resolve_code_model|resolve_review_model in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep RULES_SEPARATOR\\s*=|class ReviewCategory|def map_historical_category|def shipped_recipes_dir|def production_recipe_dirs|def known_recipe_names|def find_recipe|def _find_path in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "list_files tests/{cli/test_benchmark_recall_run.py,pipeline/actions/test_review_recipe.py,metrology/test_recipe_review_models.py,review/test_persistence.py,pipeline/test_classification.py,pipeline/test_builtin_pipelines.py,pipeline/test_loader.py,benchmark/recall/test_label_candidates.py,cli/test_review_max_cl\u2026 in ."
  - "grep \"--diff\"|\"--cwd\"|\"--no-save\"|\"--max\"|\"--files\"|exit_code == 1|dry.run|\"--dry-run\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep \"--diff\"|\"--cwd\"|\"--max\"|\"--files\"|\"--verbose|\"-v\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep ^\\s*(reviewers|combs|name): in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-recipes"
  - "grep ^\\[|^name\\s*=|^\\[\\[ in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{rules-line-pass.md,convert.py,RESULTS.md} in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/out/*-haiku-line-1.json in ."
  - "grep \"(category|severity|verdict|findings|raw_category)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out/cal.com-ca7232-haiku-line-1.json"
  - "grep architectural-decay|OTHER|\"other\"|def map_historical_category|_HISTORICAL|_ALIASES|=\\s*\"[a-z-]+\" in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/review_category_map.py"
  - "grep feedback.*review|def _feedback|def build_feedback|feedback_text|review_feedback|findings_feedback|\\.findings\\b in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions"
  - "grep haiku-xhigh|\"P6\"|'P6'|implement\\.yaml|review-model.*default|params\\[.review-model.\\] in /Users/manta/source/repos/manta/squadron/tests"
  - "grep haiku-xhigh|review-model in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \"P6\"|'P6'|implement\\.yaml|\"implement\"|load_pipeline\\(\"P6|classify_pipeline\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep (include|package-data|package_data|artifacts|force-include|\\.yaml|\\.md|\\.toml|data/) in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep real.work|real_work|\"--cwd\"|\"--dry-run\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall.py"
  - "grep \\[aliases\\.|\\[\\[|^- \\[|^\\| 18|437|haiku-xhigh in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "list_files project-documents/user/slices/43*.md in ."
  - "grep real-work|real_work in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep ^\\s*(\\d+\\.|- \\[.\\]|\\*\\*\\d+)\\s.*(43[0-9]|18\\.)|^\\s*(1[5-9]|2[0-9])\\.\\s in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "list_files {DEVLOG.md,CHANGELOG.md,docs/PIPELINES.md,README.md,project-documents/DEVLOG*.md,project-documents/user/DEVLOG*} in ."
  - "grep \\(437\\)|^18\\. |uv run sq|cd <fixture>|--cwd|Walkthrough|step 5|5\\. \\*\\* in /Users/manta/source/repos/manta/squadron/project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md"
  - "grep ^1[6-9]\\. |^2[0-2]\\.  in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep ^[0-9]+\\. \\[.\\] \\*\\*\\((43[0-9]|18)\\)[^*]*\\*\\* in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep review-model|haiku-xhigh|Recipe reviews|##  in /Users/manta/source/repos/manta/squadron/docs/PIPELINES.md"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron/README.md"
  - "grep def _classify_or_exit|ReviewModelError|Exit\\(code=|typer\\.Exit in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "list_files tests/{cli,recipes,pipeline}/**/*recipe*.py in ."
  - "grep exclude|only-include|\\[tool\\.hatch|\\[tool\\.setuptools|package-data|PROJECT_RECIPES_DIR\\s*=|SHIPPED_RECIPES_SUBDIR\\s*= in /Users/manta/source/repos/manta/squadron"
  - "grep ^## |Unreleased in /Users/manta/source/repos/manta/squadron/CHANGELOG.md"
  - "grep \"max_output_tokens\"\\s*:|model_dump\\(\\)\\s*==|\\.model_fields|\"tool_use\"\\s*:|\"template_hash\"\\s*: in /Users/manta/source/repos/manta/squadron/tests"
  - "grep RecipeRef|run_recipe_part|resolve_review_model_ref|classify_review_model|RecipePart\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep review|ReviewAction|REVIEW in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/steps/phase.py"
  - "grep require_known_model|resolve_model_alias|get_all_aliases\\(\\)|BUILTIN|builtin_pipeline_names|for name in .*PIPELINE in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \"category\": \"(error-handling|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|security|documentation|concurrency|observability|style|code-quality|bug|logic)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(?:error-handling|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|security|documentation|concurrency|observability|style|code-quality|bug|logic)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(architectural-decay|correctness|other)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": (null|\"\") in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
sectionsInDocument: 27
sectionsCovered: 27
effort: xhigh
turns: 104
promptTokens: 13395264
cachedTokens: 13037877
cacheWriteTokens: 357267
completionTokens: 181109
durationSeconds: 752.6
costUsd: 1.32549
costBasis: provider
runId: run-20261123-p5-55b85c9e
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: concern
    category: spec-defect
    summary: "Task 3's keep_categories check is unreachable as written"
    location: "src/squadron/recipes/recipe.py:41"
  - id: F002
    severity: concern
    category: safety
    summary: "Loader-set rules fields can be set from YAML"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:65"
  - id: F003
    severity: concern
    category: missing-mechanism
    summary: "Task 16 leaves the \"before the filter\" numbers without a mechanism"
    location: "src/squadron/benchmark/recall/label_candidates.py:77-84"
  - id: F004
    severity: concern
    category: granularity
    summary: "Task 16 is too large for one task"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:192"
  - id: F005
    severity: concern
    category: spec-gap
    summary: "Task 19 does not say where the expected file lives or what it looks like"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:227"
  - id: F006
    severity: concern
    category: granularity
    summary: "Task 22 is one task spanning six scenarios and names no file"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:250"
  - id: F007
    severity: concern
    category: verification
    summary: "Task 24 step 6 cannot produce a row as written"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:274-278"
  - id: F008
    severity: concern
    category: docs
    summary: "Task 23 leaves two stale passages in docs/PIPELINES.md"
    location: "docs/PIPELINES.md:305"
  - id: F009
    severity: concern
    category: process
    summary: "Task 10 changes a design rule inside an implementation task"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:148"
  - id: F010
    severity: concern
    category: format
    summary: "Numbered sub-items in Tasks 3 and 4 have no checkboxes"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:68"
  - id: F011
    severity: note
    category: sequencing
    summary: "Task 9 must split the findings before `_run_chain` runs"
    location: "src/squadron/recipes/recipe_runner.py:228-249"
  - id: F012
    severity: note
    category: spec-precision
    summary: "Task 12 and D6's record derivation must count only OK review stages"
    location: "src/squadron/recipes/recipe_runner.py:211-223"
  - id: F013
    severity: note
    category: traceability
    summary: "A design criterion names a P6 table row that does not exist"
    location: "docs/PIPELINES.md:983"
  - id: F014
    severity: note
    category: spec-precision
    summary: "Task 11 does not say which `if result.findings:` it means"
    location: "src/squadron/review/persistence.py:765"
  - id: F015
    severity: note
    category: traceability
    summary: "Shared-name rules from the Context Summary are not carried into the tasks"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:40"
  - id: F016
    severity: note
    category: granularity
    summary: "Two small tasks could merge into their neighbours"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:166"
  - id: F017
    severity: pass
    category: verified
    summary: "The D6 escaping rule defeats the parser's patterns"
    location: "src/squadron/review/parsers.py:91-110"
  - id: F018
    severity: pass
    category: verified
    summary: "Reviser feedback comes from the action's findings"
    location: "src/squadron/pipeline/actions/dispatch.py:897-958"
  - id: F019
    severity: pass
    category: verified
    summary: "Task 2's pins are feasible"
    location: "src/squadron/recipes/stage_config.py:86-95"
  - id: F020
    severity: pass
    category: verified
    summary: "A tool-less recipe review is already refused"
    location: "src/squadron/recipes/model_ref.py:136-139"
  - id: F021
    severity: pass
    category: verified
    summary: "review-model feeds only code steps; loader and classification refusals line up"
    location: "src/squadron/data/pipelines/P6.yaml:28"
  - id: F022
    severity: pass
    category: verified
    summary: "The check-off target for Task 25 exists"
    location: "project-documents/user/architecture/420-slices.model-benchmark.md:236"
  - id: F023
    severity: pass
    category: verified
    summary: "Stored outputs are clean for Tasks 19 and 20"
    location: "project-documents/user/reference/review-recall-results/20261122-martian/out"
  - id: F024
    severity: pass
    category: verified
    summary: "A finding with no category stays gating"
    location: "src/squadron/metrology/review_category_map.py:48-49"
---

# Review: tasks — slice 437

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 3's keep_categories check is unreachable as written

`keep_categories` is typed `tuple[ReviewCategory, ...] | None`, so pydantic checks each value before any `mode="after"` validator runs. Task 3 puts the explicit check "in a validator" (task file line 70). The only model validator is `_checks` (recipe.py:41-49, mode "after"). For a bad value the enum error fires first and reads "Input should be …" without the input, so the explicit ValueError never runs. Refusal 3's test (task file line 76, which asserts the bad value appears) would fail. Specify `field_validator("keep_categories", mode="before")` that checks raw values against `ReviewCategory` and names both the bad value and the valid ones.

### [CONCERN] Loader-set rules fields can be set from YAML

`rules_path` and `rules_content` are declared fields of `ReviewerOptions`, so `extra="forbid"` does not reject them. A recipe with `reviewer_options: {haiku: {rules_content: "…"}}` and no `rules` passes validation. Refusals 1–5 (lines 68–72) do not cover it, and nothing in Tasks 4–8 does either. Task 8's `reviewer_call_options` and Task 4's `rules_sha256` would then send and hash text that never came from a file. Refuse those keys in YAML with a before-validator, or keep the loader-set values on a separate type.

### [CONCERN] Task 16 leaves the "before the filter" numbers without a mechanism

`findings_per_run_unfiltered`, `recall_unfiltered`, the `not_gating` list and the label candidates all need reviewer output computed without `keep`. Today `_findings` reads `reviewer.upper` (line 83), which a filter shrinks, and `recipe_outputs` builds rows through `_pair_variants`, which Task 16 makes filter. The task does not say how to get the unfiltered set. `ReviewerOutput` (scoring.py:43-51) also has no field for the not-gating findings the JSON list needs. Name the approach: an unfiltered pass with `recipe.model_copy(update={"keep_categories": None})`, and a `not_gating` tuple on `ReviewerOutput` set in `reviewer_output`.

### [CONCERN] Task 16 is too large for one task

It spans scoring, the JSON schema, report build, report render, label candidates and four test modules. Split it into (a) scoring: `reviewer_output` keep, `_pair_variants`, the unfiltered pass, `ReviewerOutput.not_gating`, label candidates; and (b) report: the three JSON keys, `EXPECTED_ROW`, build, render.

### [CONCERN] Task 19 does not say where the expected file lives or what it looks like

Task 19 says "Write the expected file once", and Task 20 asserts against "the expected file" (line 232). Neither gives a path or a structure. Name the path under `tests/recipes/fixtures/hand_run/` and its shape: per PR and reviewer, the ordered list of titles. Also state that the five PRs' categories must be `ReviewCategory` values, since Task 20 asserts it (line 233).

### [CONCERN] Task 22 is one task spanning six scenarios and names no file

Line 251 says "the review CLI tests" without naming a file; `tests/cli/test_review_recipe.py` is the existing module. The task bundles the CLI run, the action path, the reviser check, two failed-line-pass cases and two refusals. The design's criterion that the call arguments hold "from both entry points' options dicts" (design line 324) is checked only for the CLI (`no_tools=True`, line 253). Nothing asserts the action path's call arguments. Name the file, split the task (CLI run and refusals; action path, reviser and failure modes), and assert `no_tools` and rules content on the action path as well.

### [CONCERN] Task 24 step 6 cannot produce a row as written

434's walkthrough step 4 sets `sq config set metrology.project_id <id> --project` (434 slice, Verification Walkthrough step 4, around line 451), and warns that a repo with no git remote and no recorded id gets `recipe record: not written`. Task 24's fixture repo (line 276) has neither, so step 6 (line 278) has no records to count. Copy the config line into step 4 of Task 24.

### [CONCERN] Task 23 leaves two stale passages in docs/PIPELINES.md

Line 305 lists the shipped recipes as `haiku-solr-luna` and `haiku-sol-luna`, and says each "runs two reviewers and one `luna-r` comb". Line 313 lists the refusals and lacks the two new D7 refusals. Task 23 (lines 266–270) names neither passage, and its grep check (line 270) looks only for `haiku-xhigh`, so it will not catch them. Add both edits to Task 23.

### [CONCERN] Task 10 changes a design rule inside an implementation task

Line 148 has Task 10 edit the design's D6 cell rule. The design (line 212) escapes only `|`, and the task widens that to `|`, `[` and `#`. Until Task 10 runs, the task and the design disagree, and the change skips the planning cadence. Put it in its own planning commit before Task 10. Also say that every `#` in a cell is escaped: `_FINDING_RE` matches `###` anywhere (parsers.py:94), so escaping only the first `#` leaves a match.

### [CONCERN] Numbered sub-items in Tasks 3 and 4 have no checkboxes

Task 3's refusals (lines 68–72) and Task 4's refusal cases (lines 81–85) are numbered `1.` to `5.` lines. The convention requires a `[ ]` on every item and subitem, and task-checker cannot tick these. Make each one a `- [ ]` subitem.

### [NOTE] Task 9 must split the findings before `_run_chain` runs

`_run_chain` passes `split.scored` (CONCERN and FAIL) to `chain_result`, which returns all of them when there are no combs (kept_findings.py:81-82). If Task 9 only computes `not_gating` and leaves `kept` alone, the filter does nothing. Task 9's test (line 140) would catch that, but the task should say the split runs first, so `kept` holds only gating findings.

### [NOTE] Task 12 and D6's record derivation must count only OK review stages

An UNKNOWN-verdict stage is recorded as CONFIG_FAILURE with its findings attached, but the runner uses none of them. D6 says the gating set "is derived from the two with split_by_category" (design line 218), and Task 12's test (line 171) says it reproduces the runner's set. Those differ for such a stage. `real_work.chain_counts` already restricts to OK stages (real_work.py:68-70). Say so in Task 12 and in the design sentence.

### [NOTE] A design criterion names a P6 table row that does not exist

The docs criterion (design line 348) asks for "its P6 parameter table row for review-model" to be corrected. The Built-in Pipelines table lists parameter names without defaults (lines 971–993), so there is no such row. Task 23 neither edits nor records this. Record that the criterion is met by the `implement-plan` sentence and the batch-table row.

### [NOTE] Task 11 does not say which `if result.findings:` it means

`persistence.py` has two `if result.findings:` blocks: the frontmatter one (line 699) and the body one (line 765). The new branch belongs after the body one and before `elif result.fallback_used` (line 776). Say "body".

### [NOTE] Shared-name rules from the Context Summary are not carried into the tasks

Line 40 requires the #392 and #393 messages, the "Not gating" heading and the "No gating findings" line to each be one constant per message site. Tasks 3, 10, 11, 13 and 14 do not mention the constants. Add that requirement to each of them.

### [NOTE] Two small tasks could merge into their neighbours

Task 12 is three lines of work and shares a commit with Task 13. Tasks 14 and 15 are small and already share a commit. Merging 12 into 13 and 14 into 15 would give each task its own unit of work without changing the commits.

### [PASS] The D6 escaping rule defeats the parser's patterns

`_FINDING_RE` matches the bullet form `-\s+\[SEV]`, the heading form `###\s+` and the bold form `\*\*\[SEV]\*\*`, none line-anchored. An escaped `[` breaks the bullet and bold forms. An escaped `#` breaks the heading form when every `#` is escaped. With every cell escaped, `_locate_section` (parsers.py:747-780) finds the Findings section empty and the whole-file fallback does not run. Task 11's parse test would pass.

### [PASS] Reviser feedback comes from the action's findings

`feedback: review` builds its block from the prior review action's `findings` (`_findings_block`), not from the file. Task 10's docstring correction is therefore needed: recipe_merge.py:3-5 still says "the reviser reads the review file". Task 22's reviser test checks the right thing.

### [PASS] Task 2's pins are feasible

Every reviewer and comb alias in the 13 pinned files (`haiku-xhigh`, `sol`, `sol-r`, `luna`, `luna-r`, `opus-high`, `mimo`, `sonnet`, `sonnet-high`, `haiku`) is built into models.toml, so `load_user_aliases` returning `{}` does not break them. The `planned_stages(recipe, hash)` signature matches the call Task 2 makes.

### [PASS] A tool-less recipe review is already refused

`validate_recipe_review` refuses `no_tools` on a recipe. A step's no-tools path therefore cannot reach `reviewer_call_options`, and Task 8's `no_tools` override cannot re-enable tools on such a step.

### [PASS] review-model feeds only code steps; loader and classification refusals line up

P6 lines 28 and 45, implement.yaml 19 and 36, implement-plan.yaml 31 and 48, and review.yaml 11–12 use only `template: code`. P56 and P456 keep `haiku-xhigh`, as the design says. Loader validation passes `template=None` (loader.py:491-499), so Task 13's refusals do not run there. Classification passes `has_diff` from the template (classification.py:470), so `code` passes and `slice` and `tasks` are refused.

### [PASS] The check-off target for Task 25 exists

`18. [ ] **(437) Line-Pass Pair as the Code Gate**` is present and unchecked.

### [PASS] Stored outputs are clean for Tasks 19 and 20

A search of the haiku outputs found no historical category strings from the mapping table and no null categories. The five PRs can therefore meet Task 19's rule and Task 20's assertion.

### [PASS] A finding with no category stays gating

`map_historical_category(None)` returns `(None, None)`, so `RecallFinding.category` stays None, and Task 7's "no category is gating" rule needs no special case.

### Run Digest

- Response length: 29666 chars
- Response is newline-free: no
- Tool calls made: 103
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 104
- Tokens — prompt / cached / cache write / completion / reasoning: 13395264 / 13037877 / 357267 / 181109 / not computed
- Duration: 752.6 s
- Cost: $1.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 24
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 24
- Finding-shaped matches — surviving validation: 24

## Resolution

Task file revised 20261123 after this review; the design's D6 and its docs criterion edited in the same planning commit. No further review was run.

- **Task 3's keep_categories check is unreachable** — Applied: `field_validator("keep_categories", mode="before")`.
- **Loader-set rules fields can be set from YAML** — Applied: a before-validator on `ReviewerOptions` refuses them; the loader sets them with `model_copy`. New refusal and test in Task 3.
- **Task 16 leaves the before-filter numbers without a mechanism** — Applied: an unfiltered pass with `model_copy(update={"keep_categories": None})`, and `ReviewerOutput.not_gating` set in `reviewer_output` (Task 14).
- **Task 16 is too large** — Applied: split into Task 14 (scoring, label candidates) and Task 15 (report columns).
- **Task 19 does not say where the expected file lives** — Applied: `tests/recipes/fixtures/hand_run/expected.json` with its shape; the fixture names and the `ReviewCategory` constraint are stated (Task 18).
- **Task 22 spans six scenarios and names no file** — Applied: Task 21 (CLI and refusals, `tests/cli/test_review_recipe.py`) and Task 22 (action path, reviser, failure modes); the action path asserts `no_tools` and rules content.
- **Task 24 step 6 cannot produce a row** — Applied: step 4 sets `metrology.project_id` in the fixture.
- **Task 23 leaves two stale passages** — Applied: the shipped-recipes paragraph and the refusal list are named, and the grep covers them.
- **Task 10 changes a design rule inside an implementation task** — Applied: D6's cell rule now escapes every `|`, `[` and `#`, edited in this planning commit; the task item is removed.
- **Numbered sub-items have no checkboxes** — Applied: each is a `- [ ]` subitem.
- **Task 9 must split before `_run_chain`** — Applied.
- **Record derivation must count only OK review stages** — Applied in Task 12 and in D6's record sentence.
- **A design criterion names a P6 table row that does not exist** — Applied: the design criterion now names the `implement-plan` sentence and the batch-table row, and says the Built-in Pipelines table has no defaults.
- **Task 11 does not say which `if result.findings:`** — Applied: the body's.
- **Shared-name rules not carried into the tasks** — Applied: Tasks 3, 10, 11, 12 and 13 name their constants.
- **Two small tasks could merge** — Applied: old 12+13 are Task 12, old 14+15 are Task 13; commits unchanged.
- PASS findings — No change.
