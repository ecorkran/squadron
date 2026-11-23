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
reviewedSha: f7538da5e47e654e78900a8b635a9a14b0dd073c
reviewedBlob: 9d48aacf3a11d3270ae2fbe2ab3d478de48c7da2
reviewedBlobCurrent: true
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 67
injected: []
filesRead:
  - "src/squadron/data/recipes/haiku-line-pass.yaml"
  - "src/squadron/data/pipelines/P6.yaml"
  - "src/squadron/data/pipelines/review.yaml"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/pipeline/steps/phase.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/models/aliases.py"
  - "src/squadron/data/pipelines/implement-plan.yaml"
searches:
  - "grep haiku-line-pass in /Users/manta/source/repos/manta/squadron"
  - "grep RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src"
  - "list_files **/recipes/*.yaml in /Users/manta/source/repos/manta/squadron/src"
  - "grep review-model|model:|template:|diff|files|code in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep has_diff|validate_recipe_review|diff in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep \"diff\"|\\bdiff\\b.*params|params\\[.diff.\\]|\"diff\": in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep \\bdiff\\b in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep diff|inputs|required|default in /Users/manta/source/repos/manta/squadron/src/squadron/data/templates/code.yaml"
  - "grep ReviewAction|\"review\"|review_action|\\.execute\\(|action_type=ActionType\\.REVIEW in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep target in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/steps/phase.py"
  - "grep def _resolve_slice_inputs|def _resolve_inputs|\"diff\"|diff\\b.*=|template_name == \"code\"|== \"code\" in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def resolve_template_input_parts|def _code|\"code\"|diff in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep def resolve_template_input_parts in /Users/manta/source/repos/manta/squadron/src"
  - "grep TEMPLATE_INPUTS|InputSpec\\(|\"code\"|diff in /Users/manta/source/repos/manta/squadron/src/squadron/review/template_inputs.py"
  - "grep no_tools|allowed_tools in /Users/manta/source/repos/manta/squadron/src/squadron/review/review_client.py"
  - "grep no_tools|allowed_tools|options|review_call in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review_recipe.py"
  - "grep Findings|### \\\\\\[|_FINDING|def parse_review_output|def _findings|whole in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep _classify_or_exit|has_diff|no_tools= in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep has_diff|resolve_review_model_ref in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/classification.py"
  - "grep line-length|\\[tool\\.ruff|extend-select|select =|ignore =|E501 in /Users/manta/source/repos/manta/squadron"
  - "grep .{101,} in /Users/manta/source/repos/manta/squadron/src/squadron/recipes"
  - "list_files **/line-pass.rules.md in /Users/manta/source/repos/manta/squadron"
  - "grep package-data|include|artifacts|force-include|build-backend|\\[tool\\.(hatch|setuptools|poetry)|package_data|data/ in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep . in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def recall_findings|category in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/recipe_outcome.py"
  - "grep class RecallFinding|category:|category = in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "grep def require_known_model|profile_source|raise .*Error|def resolve_model_alias in /Users/manta/source/repos/manta/squadron/src/squadron/models/aliases.py"
  - "grep StageConfigError in /Users/manta/source/repos/manta/squadron/src"
  - "grep def recipe_isolation_failure|stage_model\\(reviewer\\)|return ref$|refusal = recipe_isolation_failure|except ReviewModelError|    recipe = _classify_or_exit|^def _review_command|^def review_code|def _resolve_model\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "list_files **/hand_run/expected.json in /Users/manta/source/repos/manta/squadron/tests"
  - "list_files **/20261122-martian/rules-line-pass.md in /Users/manta/source/repos/manta/squadron/project-documents"
  - "grep rules_content|\"no_tools\"|verbosity|options in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review_recipe.py"
  - "grep review-model|haiku-xhigh|haiku-line-pass|review-model.*default|default.*review in /Users/manta/source/repos/manta/squadron/docs/PIPELINES.md"
  - "grep haiku-xhigh|haiku-line-pass in /Users/manta/source/repos/manta/squadron/README.md"
  - "grep plan_recipe\\(|planned_stages\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def _not_gating_findings_section|if recipe.reviewer_options:|def recipe_hash|pre-run|passes_the_pre_run_check_with_the_line_pass|def test_code_step_with_files_and_a_filter|rules_content=kwargs in /Users/manta/source/repos/manta/squadron"
  - "grep def _not_gating_findings_section|if recipe\\.reviewer_options:|def recipe_hash in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def test_code_step_with_files_and_a_filter_recipe_passes_the_pre_run_check in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_classification.py"
  - "grep slice|params|\\*\\* in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/steps/review.py"
  - "grep params=|pipeline_params|\\.params\\b.*=|merged|step_params in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/executor.py"
diffTruncated: false
effort: xhigh
turns: 68
promptTokens: 7135138
cachedTokens: 6914497
cacheWriteTokens: 220555
completionTokens: 90535
durationSeconds: 387.6
costUsd: 0.712405
costBasis: provider
runId: run-20261123-p6-a0dd6cdd
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Pre-run check passes a code step with no diff; the refusal only comes when the step runs"
    location: "src/squadron/pipeline/classification.py:470"
  - id: F002
    severity: note
    category: error-handling-observability
    summary: "A CLI `StageConfigError` escapes the `ReviewModelError` handler"
    location: "src/squadron/cli/commands/review.py:771"
  - id: F003
    severity: note
    category: documentation-drift
    summary: "The `_not_gating_findings_section` docstring overstates what the heading protects"
    location: "src/squadron/review/persistence.py:240"
  - id: F004
    severity: note
    category: other
    summary: "A loop in `expand_pending` always raises on its first pass"
    location: "src/squadron/benchmark/recall/run_plan.py:108-110"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "`recipe_hash` treats all-default `reviewer_options` as a different recipe"
    location: "src/squadron/recipes/recipe_record.py:108"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "Oversized files grew again"
    location: "src/squadron/review/persistence.py"
  - id: F007
    severity: note
    category: other
    summary: "A `FAIL` finding outside `keep_categories` can leave the verdict at PASS"
    location: "src/squadron/recipes/recipe_merge.py:199"
  - id: F008
    severity: pass
    category: correctness
    summary: "Not-gating rows cannot be read as findings by the review parser"
    location: "src/squadron/recipes/recipe_merge.py:112"
  - id: F009
    severity: pass
    category: correctness
    summary: "The default code pipelines reach the recipe with a diff"
    location: "src/squadron/pipeline/executor.py:1147"
---

# Review: code — slice 437

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 66 successful tool call(s) of 67 made; 155062 of 155062 diff characters reached the model

## Findings

### [CONCERN] Pre-run check passes a code step with no diff; the refusal only comes when the step runs

The pre-run check passes `has_diff=template_takes_diff(template)`, which is True for every `code` step. The action decides `has_diff` from the inputs it resolves at run time: `bool(part_inputs[0].get("diff"))` at `src/squadron/pipeline/actions/review.py:321`. A `code` step with `files:` and no `slice` or `diff` therefore passes classification with a keep-categories or `tools: false` recipe. Then `validate_recipe_review` refuses it when the step runs (`src/squadron/recipes/model_ref.py:114-124`). In a pipeline, that step usually follows dispatch steps that commit, so the run fails after earlier work is done. The test at `tests/pipeline/test_classification.py:1210` pins the pre-run pass as intended. The shipped defaults are not affected, because `executor.py:1147` merges pipeline params into each action and their `slice` resolves a diff (`src/squadron/review/template_inputs.py:69-70`). Suggested fix: in the pre-run check, pass `has_diff=False` when the step has neither a `diff` nor a `slice` param, and change that test to assert the refusal.

### [NOTE] A CLI `StageConfigError` escapes the `ReviewModelError` handler

`recipe_isolation_failure` calls `stage_model` (`src/squadron/pipeline/actions/review_recipe.py:54`), which raises `StageConfigError` for a reviewer that resolves to a model id with no profile (`src/squadron/recipes/stage_config.py:91-92`). `_classify_or_exit` catches only `ReviewModelError` (`review.py:765`), so the CLI would print a traceback instead of the `Error:` line its other refusals print. This is not a regression: `plan_recipe` raises the same error for the same members (`stage_config.py:132-136`), and `check_recipe_members` accepts literal ids that have no profile (`src/squadron/models/aliases.py:263-274`). The root fix is to have `check_recipe_members` require a profile for every member.

### [NOTE] The `_not_gating_findings_section` docstring overstates what the heading protects

The docstring says that without the `## Findings` heading the parser scans the whole file, where a "Not gating" row could read as a finding. It says the heading keeps the section to one plain line. The heading adds no protection beyond the escaping. `_locate_section` falls back to a whole-document scan when the Findings span has no finding-shaped text but the document does (`src/squadron/review/parsers.py:765-778`). The real guard is the cell escaping in `recipe_merge._cell` (`src/squadron/recipes/recipe_merge.py:112-117`). The docstring should say that.

### [NOTE] A loop in `expand_pending` always raises on its first pass

The `for recipe` / `for reviewer` loop raises on its first element, so it reads like a loop that was meant to collect something. It works, but a reader will take it for a bug. Use one check that returns the first offending `(recipe, reviewer)` pair, then raise once.

### [NOTE] `recipe_hash` treats all-default `reviewer_options` as a different recipe

`recipe_hash` adds `reviewer_options` whenever the mapping is non-empty (`if recipe.reviewer_options:`). `Recipe.reviewers_with_options()` and `reviewer_call_options` both treat an all-default entry as no change. So `reviewer_options: {haiku: {tools: true}}` runs identically to a recipe without it, but gets a different `recipe_hash`. The real-work table uses that hash as its row label. Include only the options that differ from the default, or key the test on `reviewers_with_options()`.

### [NOTE] Oversized files grew again

`review/persistence.py` (over 1,000 non-blank lines), `cli/commands/review.py` (over 1,400), and `pipeline/actions/review.py` (about 850) were already past the ~300-line guideline before this branch. Each gained lines here. Moving the recipe-section and not-gating rendering out of `persistence.py` would keep that file from growing further.

### [NOTE] A `FAIL` finding outside `keep_categories` can leave the verdict at PASS

This is intended (D5 and D6): the verdict is computed only from gating findings. A review can therefore read PASS while the Recipe section lists FAIL-severity findings in its "Not gating" table. `haiku-line-pass` is the default code reviewer for four pipelines, so this changes what their `pass-threshold` means. `P6.yaml:8-10` documents it. I note it so the trade is visible in review.

### [PASS] Not-gating rows cannot be read as findings by the review parser

The parser matches five shapes (`src/squadron/review/parsers.py:91-100`). Each requires a contiguous `###`, `**[`, or `- [`. `_cell` escapes `\`, `|`, `[`, and `#` and collapses whitespace, so no cell can start a line or form one of those sequences. `tests/review/test_persistence.py` (`TestNotGatingFindingsSection`) covers the hostile-title case.

### [PASS] The default code pipelines reach the recipe with a diff

`merged_action_params = {**merged_params, **resolved_action_config}` gives every action the pipeline's `slice`. `_resolve_slice_inputs` then resolves a diff for the `code` template (`src/squadron/review/template_inputs.py:69-70`). A phase with a `slice` is slice-scoped (`src/squadron/pipeline/steps/phase.py:246-248`). So `haiku-line-pass` is not refused on the `P6`, `implement`, `implement-plan`, or `review` pipelines.

### Run Digest

- Response length: 17828 chars
- Response is newline-free: no
- Tool calls made: 67
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 68
- Tokens — prompt / cached / cache write / completion / reasoning: 7135138 / 6914497 / 220555 / 90535 / not computed
- Duration: 387.6 s
- Cost: $0.71 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
