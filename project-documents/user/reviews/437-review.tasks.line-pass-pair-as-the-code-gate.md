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
reviewedSha: 92cce870f3b078e7bd540d76911a3c4df784b8a5
reviewedBlob: 56cf19e67fcde8f635f15b3a1c3b6069f6ccaff5
reviewedBlobCurrent: false
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 79
injected:
  - key: input
    path: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md"
    chars: 27064
    sha256: e1a5334bddf13e0592a096534c4a3dc1e80c3104bb91fad3bbd59022564d0c1e
    whole: true
  - key: against
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 40210
    sha256: de62be0097a6a1ffdd45c968ced27cc11789592cc1b6c2c6ef0376b70b27fe51
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/recipe_record.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/metrology/recipe_review_models.py"
  - "src/squadron/review/persistence.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "tests/recipes/support.py"
  - "tests/recipes/conftest.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "docs/PIPELINES.md"
  - "tests/cli/commands/test_run.py"
  - "tests/review/test_review_template_defaults.py"
  - "src/squadron/cli/commands/review.py"
searches:
  - "grep class StageConfig|def config_key|class RecallFinding|class StageKind|tool_use|rules_hash|category in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "grep no_tools|rules_content|model_allows_tools|def run_review_with_profile in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep RULES_SEPARATOR in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep No specific findings|## Findings|recipe\\b|RecipeReviewInfo|stage_section in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep recipe|classify_review_model|resolve_review_model_ref|has_diff in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/classification.py"
  - "grep Known recipes|haiku-solr-luna|haiku-sol-luna|SHIPPED|the_two in /Users/manta/source/repos/manta/squadron/tests"
  - "grep _FINDING_RE\\s*=|_HEADING_RE\\s*=|_CATEGORY_RE\\s*=|_LOCATION_RE\\s*=|def _count_finding_matches|def _mask_fences|_SEVERITY_MAP\\s*= in /Users/manta/source/repos/manta/squadron/src/squadron/review/parsers.py"
  - "grep degraded\\s*=|fallback_used\\s*=|fallback_used:|findings_section_located in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "list_files src/squadron/data/recipes/* in /Users/manta/source/repos/manta/squadron"
  - "list_files project-documents/user/reference/review-recall-recipes/* in /Users/manta/source/repos/manta/squadron"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/**/* in /Users/manta/source/repos/manta/squadron"
  - "list_files tests/recipes/**/*.py in /Users/manta/source/repos/manta/squadron"
  - "list_files tests/benchmark/recall/**/*.py in /Users/manta/source/repos/manta/squadron"
  - "list_files src/squadron/data/pipelines/*.yaml in /Users/manta/source/repos/manta/squadron"
  - "grep review-model|^\\s*model:|template: code|template: slice|template: tasks in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep def reviewer_output|def expand_pending|def _reviewer_counts|Kept/review|Raw findings/review|def stage_outputs|ConfigFor|def live_stage_config|class StageIdentityResolver|def resolve\\(|def candidates|def label_candidates|not_gating in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark"
  - "grep load_user_aliases in /Users/manta/source/repos/manta/squadron"
  - "grep ^\\s*(\\[aliases\\.|\\[)?\"?(haiku|haiku-xhigh|sol|luna|sol-r|solr|sonnet|sonnet-high|opus|opus-high|haiku-opus|mimo|sol-opus)\"?\\]?\\s*(=|$) in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep reviewers:|combs:|pool:|^\\s+- |^\\s+\\w+: \\[ in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-recipes"
  - "grep luna-r|opus-high\\]|^\\[aliases\\.opus-high in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep COLUMNS|Kept/review|Raw findings/review|Incomplete \\(aborted\\)|\\| Recipe \\| in /Users/manta/source/repos/manta/squadron/tests"
  - "grep class \\w*(Error|Refus)\\w*\\(|refus|expand_pending\\(|bound in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep expand_pending|bound|RunRefused|Refused|class .*Error in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep def matching_reviews|def matching_chains|def identity_of|resolver\\.resolve in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep feedback in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/dispatch.py"
  - "grep def entry_key|def run_record_id|model_dump|_sha256_json\\( in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/recall_run_models.py"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{*.md,*.py,out/*haiku-line*} in /Users/manta/source/repos/manta/squadron"
  - "grep Exit\\(code=2\\)|exit_code=2|code=2|Exit\\(2\\) in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep def _findings_block|def _latest_review in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/dispatch.py"
  - "grep ^  \"[a-zA-Z_]+\":|\"verdict\"|\"severity\"|\"category\"|/Users/|/tmp/|sandbox in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke36882-haiku-xhigh-1.json"
  - "grep CONCERN|FAIL|category|other|def |import in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "grep def test_standalone_review_default_matches_the_pipeline|def test_implement_plan_params_and_shape|def test_recipe_no_longer_shipped_is_refused_at_the_pre_run_check|standalone code review|runs P6|P6's reviewer in /Users/manta/source/repos/manta/squadron/tests"
  - "grep review-model|matching `P6`|defaults to `haiku-xhigh`|haiku-xhigh in /Users/manta/source/repos/manta/squadron/docs/PIPELINES.md"
  - "grep ^#+ .*[Rr]ecipe|^## \\[Unreleased\\]|haiku-xhigh in /Users/manta/source/repos/manta/squadron"
  - "grep \\b437\\b|\\b18\\b.*(slice|line) in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep template: code in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep haiku-xhigh|review-model in /Users/manta/source/repos/manta/squadron/tests"
  - "grep Param \\| Default|^#+ .*P6|`P6` in /Users/manta/source/repos/manta/squadron/docs/PIPELINES.md"
  - "grep line-pass|line pass|haiku-xhigh|\\| *18 *\\||^1[5-9]\\.|18\\. in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep in step|P456|P56|\"P6\"|implement-plan in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_builtin_pipelines.py"
  - "grep \"template_hash\"|\"recipe_hash\"|\"tool_use\"|model_dump\\(\\)\\s*==|config_key\\\"?\\s*:|\"max_output_tokens\" in /Users/manta/source/repos/manta/squadron/tests"
  - "grep split\\(|cells|\\[\\d\\]|== \\[|header|Recipe \\| in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_real_work.py"
  - "grep json|schema|keys|SCHEMA in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_report_json_schema.py"
  - "grep RecipePart\\(|rules_content= in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep package-data|package_data|include|artifacts|\\[tool\\.hatch|\\[tool\\.setuptools|\\[build-system\\]|force-include|\\*\\*/\\*|data/ in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep shipped_recipes_dir\\(\\)|def shipped_recipes_dir|iterdir|glob\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep \"--dry-run\"|\"--no-save\"|\"--cwd\"|\"--real-work\"|\"--max\"|\"--diff\"|\"--files\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep def review_argv|def live_stage_config|alias_stage_config\\( in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md in /Users/manta/source/repos/manta/squadron"
  - "grep \"category\": \"other\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"real-work\"|\"--real-work\"|\"--dry-run\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep real-work|real_work in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep model_dump|model_fields|recipe_hash\\(|_reviewer_counts|chain_counts in /Users/manta/source/repos/manta/squadron/tests"
sectionsInDocument: 26
sectionsCovered: 26
effort: xhigh
turns: 80
promptTokens: 4463314
cachedTokens: 4197751
cacheWriteTokens: 265511
completionTokens: 138157
durationSeconds: 565.0
costUsd: 0.705506
costBasis: provider
runId: run-20261123-p5-55b85c9e
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Task 10's empty-Findings rule does not keep the Not-gating table out of the parser"
    location: "src/squadron/review/parsers.py:775-778"
  - id: F002
    severity: fail
    category: correctness
    summary: "Task 5 misdescribes `recipe_hash`; the literal change alters every recipe's hash"
    location: "src/squadron/recipes/recipe_record.py:102-105"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 2's pin test iterates the shipped directory, so Task 17 breaks it"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:52"
  - id: F004
    severity: concern
    category: correctness
    summary: "The degraded branch overrides the new rule for an UNKNOWN recipe with only not-gating findings"
    location: "src/squadron/review/persistence.py:789-800"
  - id: F005
    severity: concern
    category: correctness
    summary: "\"Matches no stored entry\" needs a named skip, because the resolver must not change"
    location: "src/squadron/benchmark/recall/scoring_select.py:49-55"
  - id: F006
    severity: concern
    category: test-infrastructure
    summary: "Task 9's scripted call cannot record `no_tools` or `rules_content`"
    location: "tests/recipes/support.py:84-111"
  - id: F007
    severity: concern
    category: scope
    summary: "Task 15 changes a pinned JSON schema and leaves the change open"
    location: "tests/benchmark/recall/test_report_json_schema.py:21-25"
  - id: F008
    severity: concern
    category: error-handling
    summary: "Task 3's unknown-category refusal cannot name the value through the existing error path"
    location: "src/squadron/recipes/recipe.py:69-73"
  - id: F009
    severity: concern
    category: scope
    summary: "Task 3 is too large for one task"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:60"
  - id: F010
    severity: concern
    category: scope
    summary: "Task 10 bundles separable work, including the part the first FAIL blocks"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:133"
  - id: F011
    severity: concern
    category: coverage
    summary: "No test runs the pipeline action path and checks the review shape"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:229"
  - id: F012
    severity: concern
    category: docs-accuracy
    summary: "Task 22 names a row that does not exist and points at one that must stay"
    location: "docs/PIPELINES.md:1026-1033"
  - id: F013
    severity: note
    category: clarity
    summary: "Task 13 does not name the existing refusal type"
    location: "src/squadron/benchmark/recall/refusal.py:6"
  - id: F014
    severity: note
    category: clarity
    summary: "Task 16 must thread the categories into `_reviewer_counts`"
    location: "src/squadron/benchmark/recall/real_work.py:48"
  - id: F015
    severity: note
    category: duplication
    summary: "Two places compute the same rules hash"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:84"
  - id: F016
    severity: note
    category: coverage
    summary: "Task 12 names no test for the arch refusal"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:157"
  - id: F017
    severity: note
    category: sequencing
    summary: "Task 1 requires a clean tree that the snapshot does not have"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:47"
  - id: F018
    severity: note
    category: docs-accuracy
    summary: "The P6 comment rewrite must also remove the existing figures"
    location: "src/squadron/data/pipelines/P6.yaml:8-16"
  - id: F019
    severity: note
    category: clarity
    summary: "Four tasks name no test file"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:146"
  - id: F020
    severity: note
    category: clarity
    summary: "Task 23 says to remove the Draft text from a heading, but it is a paragraph"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:256"
  - id: F021
    severity: note
    category: verification
    summary: "Task 24's grep check is not a mechanical test"
    location: "project-documents/user/tasks/437-tasks.line-pass-pair-as-the-code-gate.md:262"
  - id: F022
    severity: pass
    category: verification
    summary: "Code claims that check out"
    location: "src/squadron/pipeline/actions/review_recipe.py:124-128"
---

# Review: tasks — slice 437

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 10's empty-Findings rule does not keep the Not-gating table out of the parser

Task 10 (lines 137, 141) and Task 21 (line 233) rely on design D6 (lines 213–214): with no gating finding, write `## Findings` and the "No gating findings" line so the parser does not scan the table. The heading does not do that. `_locate_section` returns `None` when the Findings span holds no finding-shaped text but the document does (parsers.py:775–778), which is this case. `_extract_findings` then scans the whole response (parsers.py:816–817). The bullet alternative of `_FINDING_RE` is not line-anchored (parsers.py:100), so the `- [CONCERN] ` inside a table title matches. Its body runs to the next `## ` heading or end of text (parsers.py:102–107). The D6 parser test at line 141 therefore parses a finding, and the ingest assertion at line 233 fails the same way. The plan needs a decision: escape finding-shaped text in table cells and test that, or change the guard, which also changes real-review ingest and needs its own tests.

### [FAIL] Task 5 misdescribes `recipe_hash`; the literal change alters every recipe's hash

Task 5 (line 84) says `recipe_hash` "dumps `name`, `reviewers`, `pool`, `combs` as today". It does not. It dumps `recipe.model_dump(mode="json")` (recipe_record.py:104), which is every field of `Recipe`. Once Task 3 adds `reviewer_options` and `keep_categories` as fields, every recipe's dump gains `"keep_categories": null` and `"reviewer_options": {}`, which changes every pin in Task 2. A recipe with options would also dump `rules_path` and `rules_content` from the nested `ReviewerOptions`, which Task 5 says must never appear. Task 5 should say to build the four-key canonical dict explicitly, adding the two optional keys only when set. Task 2's pins would catch a literal implementation, but the instruction points the implementer the wrong way.

### [CONCERN] Task 2's pin test iterates the shipped directory, so Task 17 breaks it

Task 2 (line 52) asks for "every recipe in the shipped directory (`shipped_recipes_dir()`, 2 files)". Task 17 (line 199) says the pins still pass because the new recipe "is not pinned". Read literally, the directory loop finds `haiku-line-pass` with no recorded value and fails at the Task 17 commit. Task 24 (line 261) requires the file to stay unmodified after Task 2, so the fix cannot wait. Task 2 should name the 13 files explicitly: 2 shipped and 11 reference.

### [CONCERN] The degraded branch overrides the new rule for an UNKNOWN recipe with only not-gating findings

persistence.py checks `result.findings` (line 765), then `fallback_used` (776), then `degraded` (789), and only then writes "No specific findings." (800). Task 10 (line 137) places the new rule where that last line is, so it is never reached in this case. Task 21's case "only not-gating findings from haiku-xhigh → verdict UNKNOWN" (line 237) makes `degraded` true (persistence.py:613). The file then gets "## Findings Not Parsed" and "No verdict and no findings could be extracted", which is false for a recipe whose findings were extracted. With no `## Findings` heading, the parser problem above also applies. The new rule must come before the degraded branch, and Task 21 should assert the saved section.

### [CONCERN] "Matches no stored entry" needs a named skip, because the resolver must not change

`entry_matches` compares `identity_of(entry)` with `resolver.resolve(alias, kind)`. `live_stage_config` (src/squadron/benchmark/recall/stage_identity.py:35) passes no options, so the line-pass reviewer's identity equals plain `haiku`'s, and a stored tool-enabled `haiku` entry would match. D8 (design line 234) forbids changing `resolve`. Task 14 (line 168) should name where the skip goes. `_pair_variants` (scoring.py:141–159) has `recipe` and can return no variants for a reviewer with options.

### [CONCERN] Task 9's scripted call cannot record `no_tools` or `rules_content`

`CallRecord` holds alias, template, `allowed_tools`, cwd and inputs. `__call__` keeps no other keyword. Task 9 (line 126) and Task 21 (line 232) assert `no_tools=True` and the rules text on the scripted call, but no task names this file as one to change.

### [CONCERN] Task 15 changes a pinned JSON schema and leaves the change open

The test's docstring says "The report --json schema is fixed for slice 433", and it asserts the top-level keys and `$defs`. Task 15 (line 175) says to update the test "if the schema is pinned". It is pinned. The per-finding gating mark is a schema change. The task must decide where the mark lives and update the pinned sets.

### [CONCERN] Task 3's unknown-category refusal cannot name the value through the existing error path

`load_recipe` builds the `RecipeError` from `error["msg"]` only (recipe.py:72). A pydantic enum error's message lists the valid values but, as I read it, does not echo the bad input. Task 3 (line 68) requires the message to name the value. The task should require an explicit check in the validator, or carry the error's input through, and Task 4's test should assert the value appears.

### [CONCERN] Task 3 is too large for one task

Task 3 covers the model, seven refusals, the rules-file read with its four failures, the recipe-file UTF-8 handling, and possibly a helper module. Split it: 3a for the model fields, `keep_categories` and the combs refusal; 3b for the rules-file read and its refusals. Each part can then be tested on its own.

### [CONCERN] Task 10 bundles separable work, including the part the first FAIL blocks

Task 10 covers the table, the docstring fix, the `RecipeReviewInfo` field, the persistence rule and four test groups, including the parser test. Split it: 10a for the table, field, docstring and merge tests; 10b for the persistence rule and the parser test.

### [CONCERN] No test runs the pipeline action path and checks the review shape

Design line 351 requires `sq review code --model haiku-line-pass` and a P6 run to produce the same shape: one review file with the Recipe section and one `recipe_review` record. Task 21 asserts the CLI path (lines 230–233) and the reviser's feedback. Task 23 step 5 is the CLI with `--max`. The action path (`run_recipe_part` in `pipeline/actions/review_recipe.py`) is never asserted to write the file and the record. Add that assertion to the existing `tests/pipeline/actions/test_review_recipe.py`.

### [CONCERN] Task 22 names a row that does not exist and points at one that must stay

There is no "P6 parameter table" with a `review-model` default. The one default row (line 1030) sits in the plan-batch parameter table, which describes slices-plan and tasks-plan. Those keep `haiku-xhigh`, since their templates are not code reviews. The sentence to change is at line 1059, in the implement-plan section ("same params as the plan batches above"). Task 22 should name that row and say the slices-plan and tasks-plan defaults stay.

### [NOTE] Task 13 does not name the existing refusal type

The run's refusals are `RecallRefusal`. `expand_pending` (run_plan.py:87) runs before the bound is built and printed (benchmark_recall_run.py:77–80, 119–121), so the ordering in Task 13 holds. The task should name the class.

### [NOTE] Task 16 must thread the categories into `_reviewer_counts`

`_reviewer_counts(review, combs)` takes only stages. `chain_counts(record)` has the record, so Task 16 (line 183) should say to pass `keep_categories` through `chain_counts` and `_row_cells`. The new column also appears in every real-work table, so "a record without the field gives today's row" is not literally true.

### [NOTE] Two places compute the same rules hash

Task 5 (line 84) and Task 6 (lines 93–94) both compute sha256 of `rules_content`. One helper in the recipes package should serve both, since the general rules forbid duplicated logic.

### [NOTE] Task 12 names no test for the arch refusal

Design D7 (line 226) refuses the recipe on `arch` reviews as well. Task 12 tests `slice`, `tasks` and `code`. Add `arch`, or record why it is left out.

### [NOTE] Task 1 requires a clean tree that the snapshot does not have

The start-of-conversation git status lists the task file as modified and uncommitted, so `git status --short` is not clean. The planning commit should come before Task 1.

### [NOTE] The P6 comment rewrite must also remove the existing figures

The comment above `review-model` contains "64.7%" and "52 of the 66", plus recipe names. Task 20 (line 219) says "no numbers" but does not say to delete the old comment.

### [NOTE] Four tasks name no test file

Tasks 11 (lines 146–152), 15 (173–180), 17 (195–197) and 20 (225) list tests without a file path, so a junior would have to choose one. Name the files.

### [NOTE] Task 23 says to remove the Draft text from a heading, but it is a paragraph

"Draft; refined after implementation." is the first body paragraph of the Verification Walkthrough (design line 356). The heading itself is "Verification Walkthrough".

### [NOTE] Task 24's grep check is not a mechanical test

`grep -rn keep_categories src/squadron` lists call sites, not comparisons. Checking that a category is compared only inside `split_by_category` needs a search for membership tests on the category. I did not locate "entry 18" in the 420 architecture file, so that check is unverified.

### [PASS] Code claims that check out

Verified: the CLI options dict (cli/commands/review_recipe.py:80–84) carries `no_tools` and the action's (review_recipe.py:124–128) does not, as Task 8 says. `run_review_with_profile` takes `no_tools` and `rules_content` (review/review_client.py:147–157), and `RULES_SEPARATOR` is at project_rules/render.py:29. Both entry points pass the assembled rules. The 2 shipped and 11 reference recipes exist. The reference aliases (`luna-r`, `sol-r`, `opus-high`, `mimo`) are built-in (data/models.toml). The martian artifacts exist: rules-line-pass.md, convert.py, RESULTS.md, and haiku-line-1 outputs, some with `"category": "other"`. Review exits 2 on FAIL (cli/commands/review.py:471–472). `--real-work`, `--no-save`, `--max`, `--diff`, `--cwd` and `run --dry-run` exist. The reviser reads `review.findings` (dispatch.py:897–951), so Task 10's docstring fix is accurate. The wheel packages `src/squadron` (pyproject.toml:72), and recipe discovery globs `*.yaml` (recipe_search.py:50), so the `.md` rules file ships without being read as a recipe. The test names that Tasks 17 and 20 cite exist.

### Run Digest

- Response length: 23133 chars
- Response is newline-free: no
- Tool calls made: 79
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 80
- Tokens — prompt / cached / cache write / completion / reasoning: 4463314 / 4197751 / 265511 / 138157 / not computed
- Duration: 565.0 s
- Cost: $0.71 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 22
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 22
- Finding-shaped matches — surviving validation: 22
