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
reviewedSha: 5c4400c145b68d39323cc67e5c23c995994d5b4b
reviewedBlob: 1152ae6bbb89ea9d11500dd30da04443ee956976
reviewedBlobCurrent: false
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 100
injected:
  - key: input
    path: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md"
    chars: 34525
    sha256: 48cda220f2849ecb10ba7314cbe49a5bd02d1151c83a8a87c887dd622e0e9ae4
    whole: true
  - key: against
    path: "project-documents/user/architecture/420-arch.model-benchmark.md"
    chars: 30840
    sha256: 3b909db8ad85dd24d2d2195772f10ecf022a254653af1faaa958b1f54dc13b07
    whole: true
filesRead:
  - "src/squadron/recipes/recipe.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/recipes/recipe_runner.py"
  - "src/squadron/recipes/kept_findings.py"
  - "src/squadron/recipes/recipe_outcome.py"
  - "src/squadron/recipes/recipe_merge.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/cli/commands/review_recipe.py"
  - "src/squadron/pipeline/actions/review_recipe.py"
  - "src/squadron/recipes/recipe_review.py"
  - "src/squadron/recipes/model_ref.py"
  - "src/squadron/metrology/review_category_map.py"
  - "src/squadron/core/finding_categories.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/review/review_client.py"
  - "src/squadron/review/rules.py"
  - "src/squadron/pipeline/prompt_renderer.py"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/pipeline/actions/review.py"
  - "src/squadron/pipeline/loader.py"
  - "src/squadron/recipes/recipe_search.py"
  - "src/squadron/benchmark/recall/stage_identity.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/benchmark/recall/kinds.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/scoring_select.py"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "src/squadron/benchmark/recall/live_services.py"
  - "tests/review/test_review_template_defaults.py"
  - "tests/pipeline/test_builtin_pipelines.py"
  - "src/squadron/data/pipelines/implement.yaml"
  - "src/squadron/pipeline/actions/dispatch.py"
  - "src/squadron/pipeline/actions/review_outputs.py"
  - "src/squadron/recipes/recipe_record.py"
  - "tests/benchmark/recall/test_recipe.py"
  - "project-documents/user/architecture/420-slices.model-benchmark.md"
  - "project-documents/user/reference/review-recall-results/20261122-martian/out/keycloak-ke36882-haiku-line-1.json"
  - "src/squadron/review/models.py"
  - "src/squadron/pipeline/steps/phase.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/pipeline/summary_artifacts.py"
searches:
  - "list_files src/squadron/recipes/**/*.py in ."
  - "list_files src/squadron/benchmark/recall/**/*.py in ."
  - "list_files src/squadron/data/recipes/** in ."
  - "list_files src/squadron/data/pipelines/*.yaml in ."
  - "list_files tests/recipes/**/*.py in ."
  - "grep def run_review_with_profile|no_tools|rules_content|tools_suppressed|No Tools In This Session in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep review-model|review_model|model: haiku|template: code|template: slice|template: tasks|template: arch|review: in /Users/manta/source/repos/manta/squadron/src/squadron/data/pipelines"
  - "grep default_model_code|DEFAULT_MODEL_CODE|default_model_key|def _resolve_model|review-model|review_model|max_loop|--max|\\bmax_revisions\\b in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep default_model|REVIEW_MODEL_PARAM_KEY|resolve_review_model\\(|review-model|\"max\"|max_revisions|--max|run_session|DEFAULT_MODEL in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep validate_recipe_review|resolve_review_model_ref|check_recipe_members|keep_categories|reviewer_options in /Users/manta/source/repos/manta/squadron"
  - "grep _classify_recipe\\(|has_diff=|has_diff =|load_recipe\\(|find_recipe\\(|known_recipe_names\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep _classify_recipe in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep def production_recipe_dirs|def recipe_dirs|RECIPES|recipes in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/recipe_dirs.py"
  - "grep ConfigFor|PendingStage|review_argv|class .*Kind|def review_argv|_pair_variants|entry_matches|live_stage_config|reviewer_output|def walk|comb_chain in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep def recipe_hash|model_dump|sha256|json\\.dumps|recipe_hash in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/recipe_record.py"
  - "grep SHIPPED|test_shipped_recipes|opus|data/recipes|shipped_recipes_dir|glob\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep SHIPPED|test_shipped_recipes_are_the_two|opus-high|def test_implement_plan_params_and_shape|review-model|haiku-xhigh in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def test_|review-model|\\\"model\\\"|\\['model'\\]|params\\[|P6|implement|review.yaml in /Users/manta/source/repos/manta/squadron/tests/pipeline/test_builtin_pipelines.py"
  - "grep feedback in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep ReviewOutputKey\\.RESPONSE|RESPONSE:|\"findings\"|FINDINGS|outputs\\[|def _part_result|def _findings|findings=|raw_output in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/review.py"
  - "grep structured_findings|review_response\\(|ReviewOutputKey\\.RESPONSE|\\[\"response\"\\] in /Users/manta/source/repos/manta/squadron/src"
  - "grep \\.outputs\\b|prior_outputs in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep stage_section|recipe\\.|def format_review_markdown|raw_output|### \\\\\\[|_FINDING|FINDING_RE|findings_section|## Findings in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/** in ."
  - "list_files {docs/PIPELINES.md,README.md,CHANGELOG.md,pyproject.toml} in ."
  - "list_files project-documents/user/reference/review-recall-results/20261122-martian/{out/*haiku-line-1.json,convert.py,rules-line-pass.md,RESULTS.md,SUMMARY.md,ANSWERS.md} in /Users/manta/source/repos/manta/squadron"
  - "grep package-data|package_data|force-include|include|hatch|setuptools|build-backend|\\[tool\\.hatch in /Users/manta/source/repos/manta/squadron/pyproject.toml"
  - "grep 64\\.7|59\\.7|69\\.1|66\\.9|60\\.4|37\\.0|33\\.4|34\\.8|25\\.7|23\\.8|haiku-line|haiku-xhigh|strict|\\$0\\.1[23]|noise|five points|run-to-run in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md"
  - "grep config_for|review_argv|def resolve\\(|stage_config\\(|alias_stage_config\\(|planned_stages\\(|live_stage_config\\(|ReviewerOutcome\\(|StageConfig\\(|ConfigFor|_pair_variants|entry_matches\\(|matching_reviews\\(|expand_pending\\(|recipe_outputs\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \\-\\-rules|\\-\\-no-tools|no_tools: bool = typer|def code\\(|rules_path: str|rules: str \\| None in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep config_for=|config_for\\b.*lambda|def resolve\\(self|def review_argv|ReviewerOutcome\\(|stage_config\\(|live_stage_config\\(|StageIdentity\\(|\\.resolve\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def resolve\\(|def review_argv|config_for|ReviewerOutcome\\(|StageIdentity\\(|lambda alias|lambda a, k|lambda reviewer|def _config in /Users/manta/source/repos/manta/squadron/tests"
  - "grep haiku-xhigh in /Users/manta/source/repos/manta/squadron/tests"
  - "grep ^\\[aliases\\.haiku|^\\[aliases\\.haiku-xhigh|^haiku|haiku-xhigh|haiku-line|tool_use|max_output_tokens|profile = \"sdk\" in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep def template_behavior_hash|def _behavior|model|exclude|_HASH_FIELDS|asdict|model_dump in /Users/manta/source/repos/manta/squadron/src/squadron/metrology/identity.py"
  - "grep 437|line-pass|line pass|keep_categories|category filter|not gating|reviewer options in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep CONCERN|FAIL|category|correctness|other|uncategorized|severity in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/convert.py"
  - "grep \"category\": \"(error-handling|testing|test-coverage|design|design-principles|structure|dry|project-conventions|consistency|typing|performance|security|documentation|concurrency|observability|uncategorized|Correctness|[^\"]*[A-Z ][^\"]*)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": (null|\"\") in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep \"category\": \"(other|test-debt|architectural-decay|performance-resource|documentation-drift|dependency-config-debt)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/out"
  - "grep lru_cache|@cache\\b|frozenset\\(|set\\[Recipe|dict\\[Recipe|hash\\(recipe|\\{recipe\\}|RecipeRef\\}|in seen|seen\\.add\\(recipe in /Users/manta/source/repos/manta/squadron/src"
  - "grep aiRecipe|Recipe reviews|^## .*[Rr]ecipe in /Users/manta/source/repos/manta/squadron"
  - "grep steps:.*review|read the file|read_file|run grep|use the tools|grep the|open the file|read each|verify .* by reading in /Users/manta/source/repos/manta/squadron/.claude/rules"
  - "grep steps: in /Users/manta/source/repos/manta/squadron/.claude/rules"
  - "grep ReviewAction|review_config|embedded|\"review\"\\)|config\\.get\\(\"review\"|expand.*review|review.*expand in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline"
  - "grep \"--dry-run\"|\"--explain\"|\"--real-work\"|\"--cwd\"|code=2|Exit\\(code=2|exit_code_for|def _exit_code|VERDICT_EXIT in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep params\\[.review-model.\\]|params\\.get\\(.review-model.|\"review-model\"|load_pipeline\\(\"(P6|implement|review)\"|load_pipeline\\(.P6|\"P6\"|'P6' in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep SLICE_PIPELINE|\"-p\"|\"--param\"|review|model|--max-cost|argv in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/slice_runner.py"
  - "grep \\.findings\\b|len\\(.*findings|findings_per|finding_count|findings= in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/real_work.py"
  - "grep RecipeStage|recipe_review|\\.findings in /Users/manta/source/repos/manta/squadron/src/squadron/metrology"
  - "grep Exit\\(code=|exit_code = 2|return 2|verdict_exit|FAIL.*2 in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep (?i)line.pass.{0,60}(seconds|\\bs\\b|min)|(seconds|min).{0,40}line.pass|20 s|about 20 in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261122-martian/RESULTS.md"
  - "grep load_pipeline\\(\\\"(P6|implement|review)\\\"|params\\[\\\"model\\\"\\]|params\\[\\\"review-model\\\"\\] in /Users/manta/source/repos/manta/squadron/tests"
  - "grep review_file|findings|read_text|raw_output|prior_outputs|REVIEW in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/summary_oneshot.py"
  - "grep def .*summary.*|review_file|read_text\\(|artifact|findings in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/actions/summary.py"
  - "grep review|findings|artifact|paths|def  in /Users/manta/source/repos/manta/squadron/src/squadron/pipeline/summary_artifacts.py"
sectionsInDocument: 40
sectionsCovered: 27
sectionsNotCovered:
  - "Technical Decisions"
  - "D1 \u2014 Reviewer options are a mapping beside the reviewer list"
  - "D2 \u2014 `tools: false` is the existing no-tools review"
  - "D3 \u2014 `rules` names a file beside the recipe, appended to the step's rules"
  - "D4 \u2014 Both options are in the stage identity"
  - "D5 \u2014 The category filter is a recipe key, applied per reviewer before combs, with no model call"
  - "D6 \u2014 Not-gating findings stay in the review file, out of the findings list"
  - "D7 \u2014 The filter and a no-tools reviewer need a diff"
  - "D8 \u2014 The benchmark scores the filter like a comb and honors reviewer options"
  - "D9 \u2014 The shipped recipe and rules file"
  - "D10 \u2014 Four shipped pipelines default to the recipe"
  - "D11 \u2014 The hand-run entry is reproduced from stored outputs"
  - "Implementation Details"
effort: xhigh
turns: 101
promptTokens: 12156521
cachedTokens: 11783301
cacheWriteTokens: 373104
completionTokens: 165602
durationSeconds: 709.0
costUsd: 1.264838
costBasis: provider
runId: run-20261123-p4-deb2dadb
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: data-integrity
    summary: "The real-work report counts not-gating findings as kept"
    location: "src/squadron/benchmark/recall/real_work.py:48"
  - id: F002
    severity: concern
    category: accuracy
    summary: "Pipeline summary does read the not-gating table"
    location: "src/squadron/pipeline/summary_artifacts.py:60"
  - id: F003
    severity: concern
    category: plan-alignment
    summary: "Rules-file order and the stage-vs-filter wording both deviate from plan entry 18"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:165"
  - id: F004
    severity: concern
    category: accuracy
    summary: "P56 and P456 keep the old code gate, and the Overview leaves that out"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:35-44"
  - id: F005
    severity: concern
    category: accuracy
    summary: "\"The line pass sees the diff and nothing else\" contradicts D3"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:397"
  - id: F006
    severity: concern
    category: architecture
    summary: "The public benchmark is the evidence for a shipped default, against 420's non-goal"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:57"
  - id: F007
    severity: concern
    category: architecture
    summary: "The default switch rests on two runs per side, which 420's comparison rule rejects"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:46-54"
  - id: F008
    severity: concern
    category: integration
    summary: "D8's wiring misses production and benchmark modules, and the comb input path is open"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:104-121"
  - id: F009
    severity: concern
    category: testing
    summary: "Changed signatures break test doubles and call sites the design does not list"
    location: "tests/benchmark/recall/stage_support.py:30"
  - id: F010
    severity: note
    category: scope
    summary: "D9's project-override WARNING already exists; the SHIPPED test name will be wrong"
    location: "src/squadron/recipes/recipe_search.py:58"
  - id: F011
    severity: note
    category: testing
    summary: "D11's fixture conversion is unspecified and uses a different category rule from production"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:257"
  - id: F012
    severity: note
    category: error-handling
    summary: "The source map zips with `strict=True`, so a filter applied to `findings` would raise"
    location: "src/squadron/recipes/recipe_runner.py:242"
  - id: F013
    severity: note
    category: consistency
    summary: "`category_filter.py` splits one rule into a new module"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:108"
  - id: F014
    severity: note
    category: consistency
    summary: "Entry points diverge on the default"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:44"
  - id: F015
    severity: note
    category: proportionality
    summary: "Proportionality: the design is near its slice size, with a few cuts"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:56-59"
  - id: F016
    severity: pass
    category: data-integrity
    summary: "Stage identity is preserved for recipes without the new keys"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:171"
  - id: F017
    severity: pass
    category: integration
    summary: "The `no_tools` and `rules_content` option keys exist on both entry points"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:155"
  - id: F018
    severity: pass
    category: testing
    summary: "The pipeline defaults, pinned tests and replay path check out"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:250"
  - id: F019
    severity: pass
    category: accuracy
    summary: "The Overview numbers match RESULTS.md, and the walkthrough flags exist"
    location: "project-documents/user/slices/437-slice.line-pass-pair-as-the-code-gate.md:46-54"
---

# Review: slice — slice 437

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The real-work report counts not-gating findings as kept

D6 (design line 200) says the `recipe_review` record is unchanged and that "nothing in this slice reads it." The record is read by the real-work report. `_reviewer_counts` marks every CONCERN/FAIL finding in `review.findings` as "kept" unless a comb drops it (`real_work.py:50`). `RecipeStage.findings` holds every review finding (`recipe_record.py:121`). After this slice a `haiku-line-pass` row will count not-gating findings in "Raw findings/review" and "Kept/review", which overstates what reached the reviser. Walkthrough step 6 (lines 365–369) reads this same table, so the acceptance check cannot distinguish correct numbers from wrong ones. Fix before implementing: either mark gating findings in the record (which pulls #391 into this slice), or have `real_work` apply the recipe's `keep_categories`, which means the row key needs the recipe's filter. Either way, add `real_work.py` to the component table.

### [CONCERN] Pipeline summary does read the not-gating table

Design line 195 lists "the pipeline summary" among readers that "never see a not-gating finding." On the SDK path, `summary_sources` passes every file the run produced to the summarizer (`summary_artifacts.py:60-62`), and `_review_files` includes the saved review file. That file contains the Recipe section with the "Not gating" table (`persistence.py:762`). So the summarizer reads the table. Either accept that and correct the list, or keep the table out of the file, which D6 currently rules out.

### [CONCERN] Rules-file order and the stage-vs-filter wording both deviate from plan entry 18

Plan entry 18 (`420-slices.model-benchmark.md:237`) requires "a rules file sent the way `sq review --rules` sends one." D3 (line 165) puts the reviewer's file last, after always-on and language rules. `--rules` comes after the template rules and before them (`review/rules.py:239-275`). The design says so openly, but the plan criterion is not met and the plan is not amended. The plan also calls the filter "a stage" (`:238`, `:243`), and D5 (line 184) makes it a pure function instead. Also disclosed, also unamended. Recommended: amend the plan. The measured run used `--rules`, so benchmark and production will differ in rule order no matter what.

### [CONCERN] P56 and P456 keep the old code gate, and the Overview leaves that out

Line 35 says "The code review gate in the shipped pipelines becomes one recipe." Lines 44 and 46 name two remaining defaults. In fact P56 and P456 run `template: code` reviews on `{review-model}` (`P56.yaml:49,66`; `P456.yaml:68,85`) and keep haiku-xhigh for those code reviews too. The exclusion at line 80 gives only the document reason. `test_builtin_pipelines.py:68` treats P56 and P456 as single-slice code pipelines beside P6 and implement, so they now differ on the default for the same body. State the four code gates that remain and why. A literal `model:` on the code step would bypass `-p review-model`, which is the trade-off to name.

### [CONCERN] "The line pass sees the diff and nothing else" contradicts D3

D3 (line 164) sends the line pass the step's assembled rules (template rules, the step's `--rules`, always-on and language rules), under "Additional Review Rules" with the no-tools notice (`review_client.py:140-143`). The measured line pass received only its rules file through `--rules` in a sandbox (D8, line 213). So the Overview numbers (lines 46–54) come from a prompt that differs from the production prompt, and the design never says so. Correct line 397 to describe what the production line pass receives. In the Overview, note that the measured rule composition differs.

### [CONCERN] The public benchmark is the evidence for a shipped default, against 420's non-goal

420 excludes "a public or general-purpose benchmark" as a source of cases (`420-arch.model-benchmark.md:160`). The design's numbers come from Martian's public benchmark (RESULTS.md), D11 copies its outputs into test fixtures (line 257), and D9 copies its rules file (line 238). Line 57 records this and says the PM added the slice. That is the PM's call, but 420 still says the component does not do this, and its amendments do not cover it. Record a dated amendment to 420 that allows public-benchmark results as configuration evidence, not as case sources. Otherwise the architecture and the slice will keep contradicting each other.

### [CONCERN] The default switch rests on two runs per side, which 420's comparison rule rejects

420 requires configs to be compared "on paired per-case differences" and reported "with n and paired intervals" (420 lines 25, 84). The table (lines 48–52) gives point estimates from two runs per side. The pair beats same-run haiku-xhigh by 4.4 and 7.2 points of recall and by about 8 and 11 points of precision (RESULTS.md 106–108). RESULTS.md line 79 warns that single-run rows carry a spread of about five points of recall. The recall gain is within that spread. The precision gain is the clearer effect. Add n and an interval, or say the recall gain is within noise. The Value line (63) "finds more real defects" should state what was measured.

### [CONCERN] D8's wiring misses production and benchmark modules, and the comb input path is open

The component table omits modules whose signatures or call sites change:
- `benchmark/recall/live_services.py:63` wires `config_for=live_stage_config`, which D8 changes.
- `benchmark/recall/stage_runner.py:191-193`: `_argv` calls `review_argv(stage.case, stage.alias, …)` and must receive `PendingStage.options`.
- `benchmark/recall/real_work.py` (see the FAIL above).
- `benchmark/recall/label_candidates.py` (named in D8 line 216, absent from the table).

The comb input path is also unspecified. `stage_runner.comb_input_findings` (`stage_runner.py:105-114`) takes `reviewer_output(...).lower`. D8 adds the filter to `reviewer_output` (line 214), but this function has no recipe in scope, so a live comb would see not-gating findings. No shipped recipe has both `keep_categories` and combs, so this is latent. State how the filter reaches the comb input, or refuse recipes that have both.

### [CONCERN] Changed signatures break test doubles and call sites the design does not list

D8 changes `ConfigFor`, `live_stage_config`, `stage_config`, `alias_stage_config`, and `StageIdentityResolver.resolve`. The design lists only the `review_argv` fakes (line 118). The existing code this breaks:
- `stage_support.py:30` (`live_config_for`) and `:127` (`plan_config_for`), used by test_run_plan, test_run_loop, test_run_loop_resume, test_run_end_to_end and test_stage_runner.
- `test_run_plan_expand.py:23` (`config_for`).
- `scoring_support.py:129` (`resolve`), used by test_scoring_outputs.py:143.
- `test_run_end_to_end.py:72` (`resolve`).
- `tests/recipes/test_stage_config.py:37-65` (2-argument `alias_stage_config`).
- `tests/benchmark/recall/test_stage_identity.py:48-65` (2-argument `live_stage_config`).
- `tests/cli/test_benchmark_recall_run.py:76,127,145` (`config_for` through services).

Decide whether the options parameter is optional (default `None`) or required. Optional is lower risk: it keeps every existing caller and key, and it keeps D4's "keeps the key it has today" check testable without changing the doubles. Add these to the test list.

### [NOTE] D9's project-override WARNING already exists; the SHIPPED test name will be wrong

`_find_path` already logs a WARNING naming the shadowed and used files (`recipe_search.py:58-63`). D9 (line 242) lists it as new work. Reduce it to a test of existing behavior. Also, `test_shipped_recipes_are_the_two_with_no_opus_high_comb` (`tests/benchmark/recall/test_recipe.py:89`) will need renaming when the third recipe is added (line 241).

### [NOTE] D11's fixture conversion is unspecified and uses a different category rule from production

D11 does not say how stored JSON becomes `ReviewResult` and `ReviewFinding` objects. The files carry `structured_findings`, `file_ref` and `raw_category`. `convert.py:28` compares the raw `category` string, while production normalizes it through `map_historical_category` (D5, line 179). For these five PRs the two agree: I found no historical, capitalized, or null category strings in the haiku-xhigh-1 and haiku-line-1 outputs. The test should assert that, so the expected file does not depend on it silently.

### [NOTE] The source map zips with `strict=True`, so a filter applied to `findings` would raise

`_run_chain` builds `source` with `zip(findings, result.findings, strict=True)` (line 242). D5 applies the filter after `comb_input`. If the implementation passes the gating list into this zip, it raises `ValueError`. Say in the design that `source` covers every finding, and that only `chain_in` (line 232) and `chain_result` (line 245) take the gating list.

### [NOTE] `category_filter.py` splits one rule into a new module

`comb_input` in `kept_findings.py:35-39` already splits findings into the CONCERN/FAIL set that starts a chain and the rest. `split_by_category` is the second half of the same rule. Put it in `kept_findings.py`, which the runner already imports. Keep `reviewer_options.py` as a separate module, since `recipe_runner.py` is already over the size guideline.

### [NOTE] Entry points diverge on the default

`sq run review` and `sq run P6` will run the pair, while `sq review code` on its own runs haiku-xhigh. The design's reason holds: the template model is in `template_behavior_hash` (`metrology/identity.py:322`), so changing it would re-key stored stages. The divergence is still user-visible. Keep the docs line that says so (Technical Requirements, line 323), and consider a line in the `code` command's help.

### [NOTE] Proportionality: the design is near its slice size, with a few cuts

The mechanisms map to the plan's three criteria plus the benchmark plumbing the PM's later run needs. The cuts I would make:
- Lines 56–59 restate 420's rules (measure-never-gate and the cost rule). Keep only the two real deviations: the public benchmark, and the line pass counting toward `pipeline.max_cost_usd`.
- The D9 WARNING requirement (already exists).
- The separate `category_filter.py` module (see above).
- The `Patterns and Conventions` restatement of general rules (lines 262–264). Only the bullet that makes the new keys Pydantic fields is slice-specific.

### [PASS] Stage identity is preserved for recipes without the new keys

`config_key` hashes a fixed list of five fields (`recall_run_models.py:84-89`). Appending `rules_hash` only when it is set keeps every stored key. D1's canonical form (line 148) is also needed. `recipe_hash` dumps the whole model (`recipe_record.py:104`), so new defaulted fields would change every existing recipe hash unless the dump is restricted as D1 says.

### [PASS] The `no_tools` and `rules_content` option keys exist on both entry points

The CLI puts `rules_content` and `no_tools` in its options (`cli/commands/review_recipe.py:80-84`). The pipeline action puts `rules_content` and `allowed_tools` (`pipeline/actions/review_recipe.py:124-127`) and no `no_tools`. `run_review_with_profile` takes both keywords (`review_client.py:152,156`), and `no_tools=True` removes tools and adds the notice (`review_client.py:142-143,239`). `reviewer_call_options` as D2 describes works for both.

### [PASS] The pipeline defaults, pinned tests and replay path check out

The four `review-model`/`model` sites feed only `template: code` (P6.yaml:28,45; implement.yaml:19,36; implement-plan.yaml:31,48; review.yaml:10-12). The pinned tests D10 names are the ones that actually change: `test_builtin_pipelines.py:50`, `test_review_template_defaults.py:26-28`, and the `test_loader.py:55` docstring (its assertion still passes). The body-normalization test compares `{review-model}` placeholders and is unaffected. Replays are unaffected too: `sq run P6 --producer-only` strips the embedded review (`phase.py:59`).

### [PASS] The Overview numbers match RESULTS.md, and the walkthrough flags exist

The Overview table matches RESULTS.md lines 85–106. The 8.7- and 3.6-point comparison is arithmetically right. The 20-second line-pass timing matches RESULTS.md lines 31 and 112. `sq run --dry-run`, `--real-work`, `review code --cwd`, `--max`, and exit 2 on FAIL (`review.py:472`) all exist, so the walkthrough commands are runnable as written.

### Run Digest

- Response length: 35437 chars
- Response is newline-free: no
- Tool calls made: 100
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 101
- Tokens — prompt / cached / cache write / completion / reasoning: 12156521 / 11783301 / 373104 / 165602 / not computed
- Duration: 709.0 s
- Cost: $1.26 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19
