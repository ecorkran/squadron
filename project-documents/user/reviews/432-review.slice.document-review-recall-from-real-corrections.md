---
docType: review
layer: project
reviewType: slice
slice: document-review-recall-from-real-corrections
conventionsSource: none
projectRules: [general.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: 325c5e7be2330ed92777d2b08e1befd6842bb66f
reviewedBlob: c3812acb117e898f47ac4f7db01ca0b9531e72ec
reviewedBlobCurrent: false
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 94
injected:
  - key: input
    path: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md"
    chars: 49626
    sha256: 6ad59eec56c54410975d7e834e02e3a0913cff60f2c027b4c51efaa514d0e9ba
    whole: true
  - key: against
    path: "project-documents/user/architecture/420-arch.model-benchmark.md"
    chars: 30840
    sha256: 3b909db8ad85dd24d2d2195772f10ecf022a254653af1faaa958b1f54dc13b07
    whole: true
filesRead:
  - "src/squadron/benchmark/recall/kinds.py"
  - "src/squadron/benchmark/recall/stage_identity.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/hit_rule.py"
  - "src/squadron/benchmark/recall/label_candidates.py"
  - "src/squadron/metrology/recall_case_models.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/metrology/recall_label_models.py"
  - "src/squadron/benchmark/recall/label_precedence.py"
  - "src/squadron/benchmark/recall/case_models.py"
  - "src/squadron/recipes/decisions.py"
  - "src/squadron/recipes/stage_config.py"
  - "src/squadron/replay/history_free_sandbox.py"
  - "src/squadron/review/task_gate.py"
  - "src/squadron/benchmark/recall/review_sandbox.py"
  - "src/squadron/cli/commands/review.py"
  - "src/squadron/cli/commands/benchmark_recall_stage.py"
  - "src/squadron/benchmark/recall/stage_command.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/benchmark/recall/import_plan.py"
  - "src/squadron/benchmark/recall/hand_run_import.py"
  - "src/squadron/benchmark/recall/review_output.py"
  - "src/squadron/benchmark/recall/hand_run_reviews.py"
  - "src/squadron/benchmark/recall/hand_run_labels.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/cases.tsv"
  - "project-documents/user/reference/review-recall-results/20261116-mined/against.tsv"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/hits.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/flaws.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/r01.json"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "src/squadron/benchmark/recall/run_plan.py"
  - "src/squadron/benchmark/recall/stage_ingest.py"
  - "src/squadron/benchmark/recall/case_intake.py"
  - "tests/benchmark/recall/test_report_json_schema.py"
  - "project-documents/user/reference/review-recall-recipes/haiku-opus.yaml"
  - "project-documents/user/reference/review-recall-recipes/luna.yaml"
  - "src/squadron/data/templates/comb.yaml"
  - "src/squadron/benchmark/recall/live_services.py"
  - "src/squadron/benchmark/recall/run_loop.py"
  - "tests/benchmark/recall/test_kinds.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-197-tasks-fable-medium-1.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-320-arch-fable-medium-1.json"
  - "src/squadron/benchmark/recall/run_bound.py"
  - "src/squadron/benchmark/recall/scoring_select.py"
  - "project-documents/user/reference/review-recall-results/RESULTS.md"
searches:
  - "list_files src/squadron/benchmark/recall/**/*.py in ."
  - "list_files tests/benchmark/recall/**/* in ."
  - "list_files src/squadron/recipes/**/*.py in ."
  - "list_files src/squadron/replay/history_free_sandbox.py in ."
  - "list_files src/squadron/review/task_gate.py in ."
  - "grep SCORED_SEVERITIES|class Severity|NOTE\\s*=|TASK_GATE_MODEL in /Users/manta/source/repos/manta/squadron/src"
  - "grep \"(arch|slice|tasks|code)\"|--against|--no-save|--output-path|--cwd|def review_(arch|slice|tasks|code)|@review_app|review_app\\.command in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "list_files src/squadron/data/templates/*.yaml in ."
  - "grep DECISIONS|def run_review_with_profile|class TemplateOutput|class BuiltinReviewTemplate|ARCH\\s*=|SLICE\\s*=|TASKS\\s*=|CODE\\s*= in /Users/manta/source/repos/manta/squadron/src"
  - "grep recall_fetch_timeout_s|recall_timeout|max_cost|call_cost in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep class DocumentKind|DocumentKind\\b in /Users/manta/source/repos/manta/squadron/src"
  - "grep parse_decisions\\(|call_comb\\(|run_comb_stage\\(|live_stage_config\\(|STAGE_TEMPLATES|config_for\\(|ConfigFor|\\.resolve\\( in /Users/manta/source/repos/manta/squadron"
  - "grep BENCHMARK_RECALL_FETCH_TIMEOUT_KEY\\s*=|recall_fetch_timeout_s in /Users/manta/source/repos/manta/squadron/src"
  - "grep parse_decisions\\(|call_comb\\(|run_comb_stage\\(|live_stage_config\\(|STAGE_TEMPLATES|config_for\\b|ConfigFor\\b in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep parse_decisions|live_stage_config|STAGE_TEMPLATES|config_for|ConfigFor|StageIdentityResolver|ImportOnlyResolver|StubKind|register_kind|scoring_support in /Users/manta/source/repos/manta/squadron/tests"
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/**/*.{json,tsv,md,yaml} in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade*/**/map.json in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/* in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/* in ."
  - "grep . in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade/map.json"
  - "grep \"hits\":\\{\"r in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined"
  - "grep .{0,200}\"hits\":\\{\"r in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade"
  - "grep \\.base\\b|\\.head\\b|case\\.base|case\\.head in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "list_files project-documents/user/reference/review-recall-recipes/* in ."
  - "grep ^\\[?(opus-high|fable-medium|fable-haiku|hy4|mimo|luna-r|haiku-xhigh|sonnet-medium|sol)\\]?\\s*$|^(opus-high|fable-medium|fable-haiku|hy4|mimo|luna-r|haiku-xhigh)\\s*= in /Users/manta/source/repos/manta/squadron"
  - "grep luna-r|fable-medium|opus-high|\\bhy4\\b|\\bmimo\\b|fable-haiku in /Users/manta/source/repos/manta/squadron/src"
  - "grep ^\\s*\\[?\\s*(luna-r|fable-medium|opus-high|hy4|mimo|fable-haiku|haiku-xhigh|sol|luna|neon-medium|neon)\\s*\\]?\\s*(=|$)|^\\[(models|aliases)\\.(luna-r|fable-medium|opus-high|hy4|mimo|haiku-xhigh|neon-medium)\\] in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep ^\\[[^\\]]+\\] in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "grep allowed_tools|model_allows_tools|tools in /Users/manta/source/repos/manta/squadron/src/squadron/review/review_client.py"
  - "grep class TemplateOutput|output:|DECISIONS|def get_template|def load_all_templates|class ReviewTemplate|tools: in /Users/manta/source/repos/manta/squadron/src/squadron/review/templates/__init__.py"
  - "list_files src/squadron/cli/commands/benchmark_recall*.py in ."
  - "grep class ReviewBudget|def run_bound|def plan_bound|call_cost|max_plan_calls|def .*bound in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/run_bound.py"
  - "grep ReviewBudget|class .*Budget in /Users/manta/source/repos/manta/squadron/src"
  - "grep def run_loop|def run_plan|class .*Sandbox|def .*sandbox|KindSandboxFactory|SandboxFactory in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/run_loop.py"
  - "grep recipe_outputs\\(|undecided_candidates\\(|reviewer_output\\(|label_candidates|scored_severities|SCORED_SEVERITIES in /Users/manta/source/repos/manta/squadron/tests"
  - "grep has no proof|no locations|locations=\\(\\)|locations=\\[\\]|gate\\(|CANDIDATE|DECIDED_MISS|def test_.*(bug|location) in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep \"(squadron_version|model|template_name|profile|max_output_tokens|tools_given|effort)\": in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-197-tasks-fable-medium-1.json"
  - "grep \"squadron_version\": \"[^\"]*\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out"
  - "grep \"squadron_version\": \"0\\.24\\.(2[0-9]|30|3[2-9])\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out"
  - "grep \"squadron_version\": \"0\\.24\\.31\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out"
  - "grep version|No changes|def cases_add|def add_cases|next_version|case_set_version in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall.py"
  - "grep version|No changes|def |identical|unchanged in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/import_writer.py"
  - "grep ^#+ .*16|fable-medium \\||haiku-xhigh \\||opus-high \\| in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/RESULTS.md"
  - "grep recipe_outputs\\(|undecided_candidates\\(|reviewer_output\\(|matching_reviews\\(|matching_chains\\(|entry_matches\\(|resolved_labels\\( in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep \"model\": \"squadron-task-gate\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out"
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/out/*-tasks-{fable-high,luna-r-high,terra,terra-r,sol,deepseek4-flash}-*.json in ."
  - "grep run_comb_stage|call_comb|parse_decisions|comb_call|recipes\\.decisions|reviewer_output in /Users/manta/source/repos/manta/squadron/tests"
  - "grep --diff|--template|--model|invoke\\(|def test_|_stage in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_stage_command.py"
  - "grep def leak_judgeable|def is_plan_billed|CONFINED|confined|jailed in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
sectionsInDocument: 41
sectionsCovered: 40
sectionsNotCovered:
  - "D9 \u2014 `match`: an agent matches findings to flaws, blind, for document kinds"
effort: xhigh
turns: 95
promptTokens: 7564882
cachedTokens: 7272801
cacheWriteTokens: 291999
completionTokens: 182802
durationSeconds: 808.8
costUsd: 1.000682
costBasis: provider
runId: run-20261121-p4-9ad65e46
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: architecture
    summary: "The match stage cannot run on the loop, stage runner and ingest the design says it reuses"
    location: "src/squadron/benchmark/recall/run_loop.py:211"
  - id: F002
    severity: fail
    category: state-management
    summary: "Agent labels have no exit, and two agent verdicts for one finding have no rule"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:285"
  - id: F003
    severity: concern
    category: integration
    summary: "The case-file loader refuses the design's YAML, and D1 does not say which spec loads it"
    location: "src/squadron/benchmark/recall/case_models.py:95"
  - id: F004
    severity: concern
    category: data-model
    summary: "`source` and `base` are specified inconsistently, and an optional `base` breaks pyright at its call sites"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:157"
  - id: F005
    severity: concern
    category: integration
    summary: "The design changes the parser that production recipes use without listing the production comb path"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:114"
  - id: F006
    severity: concern
    category: architecture
    summary: "The generalised parser cannot express the matcher's output as designed"
    location: "src/squadron/recipes/decisions.py:31"
  - id: F007
    severity: concern
    category: architecture
    summary: "The matcher would get read tools through the comb path"
    location: "src/squadron/recipes/comb_call.py:80"
  - id: F008
    severity: concern
    category: integration
    summary: "The template and scored severities are not threaded through the matching helpers"
    location: "src/squadron/benchmark/recall/scoring_select.py:49"
  - id: F009
    severity: concern
    category: testing
    summary: "The test changes named in the design are incomplete, and existing tests it says keep passing will fail"
    location: "tests/benchmark/recall/test_stage_command.py:61"
  - id: F010
    severity: concern
    category: integration
    summary: "`plan_import(results_dir, context, plan)` cannot express the code plan's overrides step"
    location: "src/squadron/benchmark/recall/hand_run_import.py:24"
  - id: F011
    severity: concern
    category: consistency
    summary: "D8's first-pass rule reverses 430's grading import and duplicates its conflict code"
    location: "src/squadron/benchmark/recall/hand_run_labels.py:7"
  - id: F012
    severity: concern
    category: architecture
    summary: "Live gate-only entries would be sent to the matcher"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:268"
  - id: F013
    severity: concern
    category: operator-walkthrough
    summary: "Walkthrough step 6 cannot run as written"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:502"
  - id: F014
    severity: concern
    category: operator-walkthrough
    summary: "Walkthrough step 1 cannot show what its expectation promises"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:458"
  - id: F015
    severity: concern
    category: architecture
    summary: "Proofless flaws weaken the ground-truth rule the architecture names, and the report does not show them"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:155"
  - id: F016
    severity: concern
    category: architecture
    summary: "Counting absent keys as misses runs against \"absent is not zero\" and narrows recall ranges"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:253"
  - id: F017
    severity: concern
    category: nfr
    summary: "Record size is not restated, and document findings are not short"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:375"
  - id: F018
    severity: concern
    category: scope
    summary: "Three mechanisms have no consumer and can be cut"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:297"
  - id: F019
    severity: concern
    category: consistency
    summary: "`DocumentKind` already names an enum in the review package"
    location: "src/squadron/review/document_target.py:18"
  - id: F020
    severity: concern
    category: error-handling
    summary: "Matcher failures are final, which leaves recall ranges open with no retry"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:316"
  - id: F021
    severity: concern
    category: scope
    summary: "Mining arch cases from squadron's history conflicts with the 20261115 amendment, and the decision is not on record"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:332"
  - id: F022
    severity: note
    category: architecture
    summary: "`DOCUMENT_SCORED_SEVERITIES` is a benchmark constant placed in a production module"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:226"
  - id: F023
    severity: pass
    category: traceability
    summary: "The mined counts and section 16 figures check out"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:412"
  - id: F024
    severity: pass
    category: traceability
    summary: "The existing contracts the design relies on are present"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:76"
---

# Review: slice — slice 432

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The match stage cannot run on the loop, stage runner and ingest the design says it reuses

Design lines 80, 275–276 and 287 say the match stage dispatches through `run_loop`, `stage_runner`, `run_plan` and `run_bound` and writes `RecallRun.matches`. The code does not support that, and none of these modules is in the changed-modules table (design 101–120):
- `run_loop._run_case` opens the case's sandbox before every stage (`run_loop.py:134`). A matcher needs no tree (design 275), but a missing repo or unreachable commit (design 313–314) fails every match as a harness failure.
- `_store` writes REVIEW entries to `run.reviews` and every other stage to `run.combs` (`run_loop.py:211`). A MATCH entry lands among comb slots, and the comb supersede path (`:218–220`) runs on it. Nothing writes `matches`.
- `_run_one` skips only empty COMB input (`run_loop.py:165`). Match needs its own nothing-to-match rule.
- `stage_ingest.ingest_output` parses every non-REVIEW output as comb decisions (`stage_ingest.py:108–111`, `:146`).
- `stage_runner.run_stage` builds input only for COMB (`stage_runner.py:122–126`), and `ingest_orphan` re-reads input only for COMB (`:178`). The orphan rule (design 292) cannot re-read a match input.
- `stage_runner._argv` hard-codes `--template comb` and `--diff stage.case.base` (`stage_runner.py:191–198`).
- `stage_command` requires `--diff` and calls `changed_files` before the model call (`benchmark_recall_stage.py:52`, `:63`). The design's match call (design 275–276) has no `--diff`, so it fails at option parsing.
- `run_bound.observed_costs` reads only reviews, combs and superseded entries (`run_bound.py:103`). The match cost figure in design 299 has no source.

Fix: list each module with the MATCH branch it needs, or specify a separate match loop and state which of these it does not reuse.

### [FAIL] Agent labels have no exit, and two agent verdicts for one finding have no rule

Line 285 refuses `match` when a case holds agent labels from a different matcher. Nothing in the design removes or replaces agent labels. `label` writes person labels (`label_candidates.record_person_hit`), and precedence (line 286) only lets persons override them. An operator who ran the wrong matcher on `doc-flaws-arch` can proceed only by editing the store. That is a state only a person editing files can end.

There is also no same-key rule for agent labels. D8 has one for imports (line 263). A content key covers location, title and description, so two reviews of one case can share a finding text and be matched in separate calls. `RecallLabels.hits` is keyed by content key, so the second call's verdict silently overwrites the first.

Fix: name a supported exit (for example, a reset that deletes one matcher's labels and match entries) and a same-key rule.

### [CONCERN] The case-file loader refuses the design's YAML, and D1 does not say which spec loads it

D1's YAML (design 163–182) uses `commit`, `document`, `against`, `exclude`, `source` and `proof: []`, and has no `base` or `head`. The existing spec refuses each file:
- `CaseFileSpec` is `extra="forbid"` (`case_models.py:95`) and requires `base` and `head` (`:102–103`).
- `BugSpec` refuses an empty proof (`:78–79`).
- No mapping turns `commit` into `head`, though design 159 says `commit` is stored in `head`.

Design 93 gives `document_case.py` "the document case-file spec and its validation", but the changed-modules table does not touch `case_models.py`. The design must say whether the document spec is new or an extension, and whether it reuses `BugSpec`. Reusing it refuses every document file; copying its validators duplicates them. Tests of the 43 committed files must not call git (design 435). The existing committed-case test reads captured proofs (`tests/benchmark/recall/fixtures/proof_files.json`), and the design should say the document equivalent does too.

### [CONCERN] `source` and `base` are specified inconsistently, and an optional `base` breaks pyright at its call sites

Line 157 says `source` is required on every case. Line 106 makes it optional on `RealBugCase`. If it is required on code cases, the 17 committed code YAMLs fail, since `CaseFileSpec` forbids extra keys (design 434 says the code case ids stay unchanged, not that the files do). Pick one and say which files change.

Making `base` optional (design 106, 160) also breaks typing at these call sites, which pass `str`: `kinds.py:71` and `:85` (`review_sandbox(base: str)`, and the argv), `stage_runner.py:197`, and `recall_case_models.py:156` (`compute_recall_case_id(base: str)`). Design 434 requires pyright with zero errors. The design does not say how these are narrowed.

### [CONCERN] The design changes the parser that production recipes use without listing the production comb path

Line 114 changes `recipes/decisions.py` so `parse_decisions` takes a required vocabulary (also line 397). Its production caller is `recipes/comb_call.py:87`, used by the 434 recipe reviews. `hand_run_combs.py:148` and `stage_ingest.py:146` also call it. `comb_call.py` is not in the changed-modules table.

The 20261118 architecture amendment says the one production behaviour change is limited to the review path (arch lines 38–44). The design must state that the production comb path is behaviour-neutral, list `comb_call.py`, and name the production tests that pin it: `tests/recipes/test_recipe_review.py`, `tests/recipes/test_recipe_runner.py` and `tests/pipeline/actions/test_review_recipe.py`.

### [CONCERN] The generalised parser cannot express the matcher's output as designed

Lines 278–279 and 318 describe a verdict that is a flaw-id list or the none word, read by one parser through "a function from the text after the id".
- Both regexes capture the verdict as a single letter run (`[A-Za-z]+\b`, `decisions.py:31` and `:36`). `F1, F3` never matches. Only the none word would.
- `CombDecision.verdict` is the closed `CombVerdict` enum (`recall_run_models.py:120`). A set of flaw ids does not fit it.
- Line 318 requires an unknown flaw id to discard the line and be counted. `DecisionParse` counts only unknown finding ids (`decisions.py:45–47`), and a vocabulary function can only return a value.

Fix: give the list line grammar (separator and reason delimiter), the vocabulary function's return type, and how an unknown flaw id is signalled and counted.

### [CONCERN] The matcher would get read tools through the comb path

Line 275 says the flaw-match template has "no tools". `call_comb` always passes `allowed_tools=list(COMB_ALLOWED_TOOLS)` (`comb_call.py:80`), and `run_review_with_profile` uses an explicit list over the template's own (`review_client.py:183`). `_stage` reaches the model through `run_comb_stage` (`benchmark_recall_stage.py:65–73`), so a matcher routed that way gets read_file, list_files and grep. The design should say the match path passes an empty tool list and does not go through `call_comb`.

### [CONCERN] The template and scored severities are not threaded through the matching helpers

Lines 110–113 give the resolver a template argument and say `scoring.py` takes the severities. They do not cover the helpers that call the resolver: `entry_matches` (`scoring_select.py:49–55`), `matching_reviews` (`:58–66`) and `matching_chains` (`:69–82`). Each calls `resolver.resolve(alias, kind)` and needs the case's template. They are called from `scoring._pair_variants` (`scoring.py:148–150`). `stage_runner.comb_input_findings` calls `scoring.reviewer_output` (`stage_runner.py:114`), which needs the severities argument, so `stage_runner.py` changes too.

### [CONCERN] The test changes named in the design are incomplete, and existing tests it says keep passing will fail

Design 122 names five test doubles, and 438 says "no other 430 test changes its expectations". The signature changes break more than that:
- Two-argument `ConfigFor` doubles: `stage_support.py:30` and `:127`, `test_run_plan_expand.py:23`, and `support.py:85`. `test_run_plan.py:131` and `tests/cli/test_benchmark_recall_run.py:127` pass `live_stage_config` directly.
- `StubKind` in `test_kinds.py:21` lacks `traits` and `plan_import`, which design 393 makes required. Passing it to `registered_kind` (`:45`) fails pyright.
- `test_stage_command.py:61–63` invokes `_stage` without `--stage-kind`, which design 398 makes required. Every invocation fails at option parsing.
- `test_decisions.py` calls `parse_decisions` with two arguments at lines 33–80. Design 437 says it "still passes" with a required vocabulary argument.
- Calls to `recipe_outputs` and the resolvers in `test_scoring_outputs.py` (ten call sites), `test_scoring_metrics.py`, `test_scoring_paired.py`, `test_report_render.py`, `test_reproduce_results.py` and `test_stage_runner.py` use the changed signatures.

### [CONCERN] `plan_import(results_dir, context, plan)` cannot express the code plan's overrides step

Line 197 says `CodeKind.plan_import` is "the existing reviews, combs, labels and overrides plan", with the signature `(results_dir, context, plan)`. The current builder takes `overrides_path` (`hand_run_import.py:24`) and passes `plan_labels`' output into `plan_overrides` (`:35–37`). `ImportContext` holds only `cases_by_hand_id` and `case_set` (`import_plan.py:44–49`). As written, the code import would silently lose person overrides. Widen the context or the signature.

### [CONCERN] D8's first-pass rule reverses 430's grading import and duplicates its conflict code

430's grading import already reads the grading passes for the code set. Its docstring says the later pass wins (`hand_run_labels.py:7–8`), implemented in `_set_value` and `_set_hit` (`:219–226`, `:238–245`) and reported with the same `LabelConflict` type (`import_plan.py:30–41`). D8 says the first pass wins (design 249, 257, 263). Two importers with opposite rules and one conflict type is an easy source of error. The design does not mention `hand_run_labels.py` (design 390–402).

The formats differ (flaws.json and hits.json against issues and members), so a separate parser is justified. The merge and conflict logic should be shared, or the reversal stated and tested.

### [CONCERN] Live gate-only entries would be sent to the matcher

The match unit (lines 268–270) has no exclusion for gate-only entries. Line 245 says a live tasks run on squadron-197 or -917 can produce a gate-only output, whose findings are rule-based and whose footer says "no model call" (line 246). Under the unit as written, such an entry has unlabelled FAIL findings and goes to a model. Exclude gate-only entries from the unit, or say why they are matched.

### [CONCERN] Walkthrough step 6 cannot run as written

Step 6 runs `match --set doc-flaws-arch --runs 3 --model <matcher alias> --max-cost <USD>` with no `--call-cost`. The bound needs a figure for each pending matcher config, either observed or `--call-cost` (`run_bound.py:143–148`). Observed costs come from reviews, combs and superseded entries only (`run_bound.py:103`), and `--recheck` writes no match entry (design 297). For a matcher not yet called on that set, the step refuses with "no observed cost". Add `--call-cost` to step 6, or make match entries a cost source (which needs the `observed_costs` change in the first finding).

### [CONCERN] Walkthrough step 1 cannot show what its expectation promises

Step 1 lists only `doc-flaws-arch` (line 456), then expects "9, 17 and 17 cases at v1, and commit=unreferenced on squadron-403-design, context-forge-260-arch and context-forge-268-tasks" (line 458). The arch list cannot show slice or tasks cases, so only context-forge-260-arch can appear, and the 9/17/17 counts need three lists. Correct the command or the expectation.

### [CONCERN] Proofless flaws weaken the ground-truth rule the architecture names, and the report does not show them

The architecture says "A bug counts only when a later commit or issue shows it was real" (arch line 142) and names a fix commit or issue as 432's ground truth (arch line 161). D1 relaxes this for the 82 flaws (lines 155–158), and D11 adds arch flaws under the same relaxed rule, so new arch cases can be entirely proofless. The design proposes an amendment and records `proof` per flaw, which is the right move.

But the report splits rows by labeler only (line 300), not by proof status. A reader cannot see how much of a row's recall rests on flaws no later commit corrected. The risk section (511–514) does not list this. Add the split to the row output and the header, and leave the amendment with the PM.

### [CONCERN] Counting absent keys as misses runs against "absent is not zero" and narrows recall ranges

The architecture's "Absent is not zero" principle (arch line 82) says absence must not be counted as a value. D8 reads 671 absent flaw-and-review pairs as graded misses (lines 253–255). Bug-hit counts depend only on HITs, so the section 16 reproduction holds. But each inferred MISS decides a pair that would otherwise be UNDECIDED, which narrows the recall range (430 D3). The inference is recorded in notes and the summary, but the report does not separate inferred MISS labels from graded ones. Show them separately, or say why the principle does not apply.

### [CONCERN] Record size is not restated, and document findings are not short

The architecture says "Normalized review findings stay inline; they are short" (arch line 144) and that the store "reads every file on every query" (arch line 80). This slice does not restate either NFR, and its inputs break the first assumption. `20261116-mined/out/squadron-320-arch-fable-medium-1.json` has findings whose descriptions run to several paragraphs. The design imports 1,281 review outputs inline (design line 37). Give a record-size target for a run record, then either move finding text to sidecars or measure the import before accepting inline text.

### [CONCERN] Three mechanisms have no consumer and can be cut

- `--recheck` prints the hashes of its stored input and raw output (line 297). Nothing in the design reads them. Print the comparison only.
- `report --json` gains `kind`, `matcher`, `gate_only_entries` and per-row `bug_hits_by_label`, and a pinned schema test changes (line 373, `test_report_json_schema.py:1`). Its named consumer, 433, was dropped on 20261119, and the model answers are updated by hand. Keep the text report and defer the JSON keys.
- `_stage --stage-kind` (line 276) duplicates `--template`, which already names the call. Derive the kind from the template so the two selectors cannot disagree.

### [CONCERN] `DocumentKind` already names an enum in the review package

Line 94 adds `DocumentKind` in `benchmark/recall/document_kind.py`. `src/squadron/review/document_target.py:18` already defines `DocumentKind` (SLICE, TASKS and so on), and `review.py:57` imports it. Two classes with one name in adjacent packages, one used by the review command, will be confused in review and imports. Rename the new class.

### [CONCERN] Matcher failures are final, which leaves recall ranges open with no retry

D10 makes a matcher timeout or unparseable output a `config_failure` that is "not called again" (line 316). D9 retries only harness failures (line 272). In 430, `config_failure` means the reviewed config failed (`stage_runner.py:5–6`). For the matcher, the failure is the judge's, and the reviewed config is blameless. Every review the matcher times out on stays undecided, and its range never narrows without a person's label. Make matcher config failures retryable. The design also names no timeout for the matcher call.

### [CONCERN] Mining arch cases from squadron's history conflicts with the 20261115 amendment, and the decision is not on record

The 20261115 amendment says "No task runs against squadron's own history or needs hours" (arch line 34). D11 reads squadron's documents and history for new arch cases, citing #373 as its authority (line 332). Nineteen of the 43 cases are squadron's, and step 6 is several hundred serial calls. The design acknowledges both, but the override is not recorded as a PM decision. Record it in the amendment, or scope D11 to the other repos.

### [NOTE] `DOCUMENT_SCORED_SEVERITIES` is a benchmark constant placed in a production module

Line 226 defines `DOCUMENT_SCORED_SEVERITIES` beside `SCORED_SEVERITIES` in `review/models.py` (line 39), a production module. The set is used only by the benchmark. It can live with the kind traits in `kinds.py`, importing `SCORED_SEVERITIES` from `review/models.py`.

### [PASS] The mined counts and section 16 figures check out

The 43 cases split 9/17/17 (`20261116-mined/cases.tsv`). The flaws split 19/32/31 (RESULTS.md section 16, line 317). Seventy outputs are gate-only, all in squadron-197-tasks and squadron-917-tasks, with `"model": "squadron-task-gate"` (`20261116-mined/out/`). Section 16's per-run figures (12.7, 14.0, 19.7; 9.7, 16.0, 18.0; 11.7, 13.7, 17.3) match the table at lines 414–416, and the "any of 3 runs" totals (55, 58, 53) equal the per-kind sums. The absent-key evidence holds: `grade/squadron-320-arch/hits.json` has an empty `hits` and a note naming the reviews judged no-hit. Each gate-only alias has sibling model-call outputs in the tasks set.

### [PASS] The existing contracts the design relies on are present

Verified present with the signatures used: `sq review arch` (no `--against`), and `review slice` and `review tasks` with `--against`, each with `--model`, `--output`, `--output-path`, `--no-save` and `--cwd` (`src/squadron/cli/commands/review.py:978–1233`). Also present: `TemplateOutput.DECISIONS` and `run_review_with_profile` (`review/templates/__init__.py:32`, `review/review_client.py:147`); `TASK_GATE_MODEL` and the gate result (`review/task_gate.py:24`, `:161–174`); `HistoryFreeSandbox(start_sha=…)` (`replay/history_free_sandbox.py:71–82`); `ReviewBudget` (`benchmark/grade_budget.py:25`); `benchmark.recall_fetch_timeout_s` (`config/keys.py:48`); all six new aliases and the recipe format (`data/models.toml`, `review-recall-recipes/haiku-opus.yaml`). The sandbox exception (design 209–211) is flagged with amendment text, as it should be.

### Run Digest

- Response length: 36302 chars
- Response is newline-free: no
- Tool calls made: 94
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 95
- Tokens — prompt / cached / cache write / completion / reasoning: 7564882 / 7272801 / 291999 / 182802 / not computed
- Duration: 808.8 s
- Cost: $1.00 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 24
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 24
- Finding-shaped matches — surviving validation: 24
