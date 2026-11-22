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
reviewedSha: 55a84177a0ca84c3d94f542adacdbdce26bde55d
reviewedBlob: e35da33d44cc69f5090d983a2c64c68af251d6ee
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 104
injected:
  - key: input
    path: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md"
    chars: 61693
    sha256: 3c590fb416fd84bd7a71d0e864f941458c95261bb64db658a1d520b4968df14a
    whole: true
  - key: against
    path: "project-documents/user/architecture/420-arch.model-benchmark.md"
    chars: 30840
    sha256: 3b909db8ad85dd24d2d2195772f10ecf022a254653af1faaa958b1f54dc13b07
    whole: true
filesRead:
  - "src/squadron/benchmark/recall/kinds.py"
  - "src/squadron/benchmark/recall/case_models.py"
  - "src/squadron/benchmark/recall/hit_rule.py"
  - "src/squadron/benchmark/recall/stage_identity.py"
  - "src/squadron/recipes/decisions.py"
  - "src/squadron/benchmark/recall/hand_run_labels.py"
  - "src/squadron/benchmark/recall/label_precedence.py"
  - "src/squadron/benchmark/recall/hand_run_reviews.py"
  - "src/squadron/benchmark/recall/hand_run_import.py"
  - "src/squadron/benchmark/recall/import_plan.py"
  - "src/squadron/metrology/recall_case_models.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/metrology/recall_label_models.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-197-tasks-fable-medium-1.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/cases.tsv"
  - "src/squadron/cli/commands/benchmark_recall_stage.py"
  - "src/squadron/recipes/comb_call.py"
  - "src/squadron/data/templates/comb.yaml"
  - "src/squadron/review/review_client.py"
  - "src/squadron/review/templates/__init__.py"
  - "src/squadron/review/parsers.py"
  - "src/squadron/benchmark/recall/stage_runner.py"
  - "src/squadron/replay/history_free_sandbox.py"
  - "src/squadron/benchmark/recall/stage_ingest.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/benchmark/recall/label_candidates.py"
  - "src/squadron/cli/commands/benchmark_recall_import.py"
  - "src/squadron/benchmark/recall/hand_run_overrides.py"
  - "src/squadron/benchmark/recall/case_intake.py"
  - "src/squadron/benchmark/recall/live_services.py"
  - "src/squadron/benchmark/recall/recall_services.py"
  - "src/squadron/cli/commands/benchmark_recall_run.py"
  - "tests/benchmark/recall/test_case_models.py"
  - "tests/benchmark/recall/test_report_render.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/hits.json"
  - "project-documents/user/reference/review-recall-results/RESULTS.md"
  - "src/squadron/config/keys.py"
  - "src/squadron/benchmark/recall/scoring_select.py"
  - "tests/cli/test_benchmark_recall_import.py"
  - "src/squadron/recipes/stage_config.py"
searches:
  - "list_files src/squadron/benchmark/**/*.py in ."
  - "list_files tests/benchmark/recall/**/* in ."
  - "list_files project-documents/user/reference/review-recall-*/** in ."
  - "list_files src/squadron/recipes/**/*.py in ."
  - "list_files data/templates/* in ."
  - "list_files src/squadron/benchmark/recall/*.py in ."
  - "list_files **/templates/**/*.yaml in /Users/manta/source/repos/manta/squadron"
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/* in ."
  - "list_files project-documents/user/reference/review-recall-recipes/* in ."
  - "grep live_stage_config|LiveStageResolver\\(|STAGE_TEMPLATES|config_for|ConfigFor\\b in /Users/manta/source/repos/manta/squadron"
  - "grep parse_decisions|SCORED_SEVERITIES|split_output_name|read_findings|plan_overrides in /Users/manta/source/repos/manta/squadron"
  - "grep \\.base\\b|require_base|\\bbase= in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep parse_decisions\\(|SCORED_SEVERITIES|plan_overrides\\(|split_output_name in /Users/manta/source/repos/manta/squadron/src"
  - "grep SCORED_SEVERITIES|parse_decisions|split_output_name in /Users/manta/source/repos/manta/squadron/tests"
  - "grep def |SEVERITIES in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/scoring.py"
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/out/*.json in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/out/*-squadron-197-tasks-*.json in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade*/*/map.json in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/{grade,grade2,grade3,grade4,grade5}/* in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade*/**/flaws.json in ."
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade*/**/hits.json in ."
  - "grep ^\\s*\"(model|profile|tools_given|effort|effort_configured|max_output_tokens|template_name|squadron_version|verdict|usage|cost_usd|tools)\"\\s*:.*$ in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-197-tasks-fable-medium-1.json"
  - "grep ^\\s*\"(model|profile|tools_given|effort|effort_configured|max_output_tokens|template_name|squadron_version|verdict|usage|cost_usd|tools)\"\\s*:.*$ in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-174-tasks-fable-medium-1.json"
  - "grep TASK_GATE_MODEL|class DocumentKind|COMB_TEMPLATE_NAME\\s*=|def builtin_template_hash|def stage_config|class StageConfigError|def builtin_template\\b|class HistoryFreeSandbox|def __init__|start_sha in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep --diff|--template|--input|--output|COMB_TEMPLATE|def |call_comb|run_review_with_profile in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/benchmark_recall_stage.py"
  - "grep def run_review_with_profile|allowed_tools|class TemplateOutput|DECISIONS|def call_comb|read_tools|READ_TOOLS in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep def run_review_with_profile|allowed_tools|model_allows_tools|cwd in /Users/manta/source/repos/manta/squadron/src/squadron/review/review_client.py"
  - "grep class TemplateOutput|DECISIONS|def load_all_templates|def get_template|_BUILTIN|class ReviewTemplate|output:|output_kind|impose_diff_coverage\\( in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep load_all_templates|list_templates|builtin|TEMPLATE_NAMES|\"comb\"|\"arch\" in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \"comb\"|COMB|decisions|TemplateOutput|def parse_review_output|def _collect_review in /Users/manta/source/repos/manta/squadron/src/squadron/review"
  - "grep typer\\.Option\\(|@.*command\\(|def .*command|add_typer|register|\"--[a-z-]+\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep ^\\s*-?\\s*case:\\s*\\S+ in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-overrides.yaml"
  - "grep report_render|render_report|build_report|Bugs found|Cost/run|Leak scan|_set_hit|_set_value|reviewer_output\\(|recipe_outputs\\( in /Users/manta/source/repos/manta/squadron/tests"
  - "grep --diff|diff|changed in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_stage_command.py"
  - "grep locations|CANDIDATE|DECIDED_MISS|gate\\( in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep Recipe \\||header|Hit rule|Case set|Recall|Bug-hits|bug-hit|assert .*== \\(|\\.splitlines\\(\\)|column|footer in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep def test_|assert .*(in|==) .*(\\||Recipe|Cases|Runs|runs|header|Bug) in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_report_render.py"
  - "grep def test_|RESULTS|section|golden|expected|reproduc in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_reproduce_results.py"
  - "grep Case set|Recipe|Hit rule|\\| Recipe|Bugs found|Leak scan|Cost/run|Real share|def  in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/report_render.py"
  - "grep def check_review_timeout|def require_review_timeout|class LeakChecker|class ScrubbedEnvironment|def resolve_sq_path|def entry_matches|def matching_reviews|def matching_chains|class ImportOnlyResolver|def render_bound|def run_auth_check|class ReviewBudget in /Users/manta/source/repos/manta/squadron/src"
  - "grep SCORED|recipe_outputs|reviewer_output|resolved_labels|scoring|def |report_build in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/report_json.py"
  - "grep def check|context\\.stage|context\\.sandbox|context\\.profile|context\\.home|context\\.output_dir|class TranscriptLeakChecker|def leak_judgeable|stage\\. in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/leak_check.py"
  - "grep class PendingStage|record_id|file_key|slot|review_key|def for_profiles in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/run_plan.py"
  - "grep severity|def read_findings|def read_effort|def read_usage|PASS|NOTE in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/review_output.py"
  - "list_files project-documents/user/architecture/420-*.md in ."
  - "grep ^\\s*\\[(models\\.)?(fable|opus|luna|hy4|mimo|sol|haiku)[-a-z0-9.]*\\]|^\\s*\\[.*(neon|fable-medium|opus-high|mimo|hy4|luna-r|fable-haiku).*\\] in /Users/manta/source/repos/manta/squadron/src"
  - "grep 432|document|arch|amend|20261119|tasks in /Users/manta/source/repos/manta/squadron/project-documents/user/architecture/420-slices.model-benchmark.md"
  - "grep ^#+ .*16|section 16|\\b1,?074\\b|\\b161\\b|\\b172\\b|\\b574\\b|regrade|absent in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/RESULTS.md"
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/* in ."
  - "grep squadron-320-arch in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade/map.json"
  - "grep hits|absent|get\\(|\\.get\\( in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/score_all.py"
  - "grep BENCHMARK_REVIEW_TIMEOUT_KEY|BENCHMARK_RECALL_FETCH_TIMEOUT_KEY|review_timeout_s|recall_fetch_timeout_s in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep locations=\\(\\)|locations=\\[\\]|\"locations\": \\[\\] in /Users/manta/source/repos/manta/squadron/tests"
  - "grep class StubKind|StubKind\\(|traits|plan_import|register_kind|registered_kind in /Users/manta/source/repos/manta/squadron/tests"
  - "grep Label conflicts|No changes\\.|Review entries:|later pass wins|Run records:|model_dump\\(\\)|model_json_schema|sorted\\(.*keys\\(\\)|StageKind\\)|LABELER_PREFIX|for kind in in /Users/manta/source/repos/manta/squadron/tests"
  - "grep \"--against\"|\"--no-save\"|\"--output-path\"|\"--cwd\"|\"--output\"|def review_(arch|slice|tasks)|review_(arch|slice|tasks)|command\\(\\s*\"(arch|slice|tasks)\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli"
  - "grep \"proof\"|\"original_review\"|\"source\"|\"exclude\"|\"commit\"|\"reviews\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/flaws.json"
  - "grep reviews|rmtree|rm -rf|exclude|rmdir|shutil|os\\.remove|unlink in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/prepare.py"
  - "list_files project-documents/user/reference/design-review-recall-cases*.md in ."
  - "list_files project-documents/user/reference/document-recall-cases/** in ."
  - "grep ^dateCreated:|^dateUpdated: in /Users/manta/source/repos/manta/squadron/project-documents/user/slices"
  - "grep (?i)no later commit|later commit|proves|verified by reading|unproven in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/design-review-recall-cases-migratory.md"
sectionsInDocument: 41
sectionsCovered: 41
effort: xhigh
turns: 105
promptTokens: 10413183
cachedTokens: 10084838
cacheWriteTokens: 328243
completionTokens: 175215
durationSeconds: 790.5
costUsd: 1.144508
costBasis: provider
runId: run-20261121-p4-9ad65e46
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: alignment
    summary: "Flaws with no later correcting commit are counted, against the architecture's ground-truth rule"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:168-172"
  - id: F002
    severity: concern
    category: alignment
    summary: "The sandbox rebuild deviates from the reviewer-recall sandbox the architecture defines"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:224-226"
  - id: F003
    severity: concern
    category: alignment
    summary: "Absent grader keys are read as decided misses, against \"absent is not zero\""
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:268-272"
  - id: F004
    severity: concern
    category: alignment
    summary: "The matcher bound uses a flat per-call figure; the architecture asks for bounds from observed costs"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:325"
  - id: F005
    severity: concern
    category: under-specification
    summary: "The three named inputs for the 43 case files cannot supply the required fields"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:163"
  - id: F006
    severity: concern
    category: integration
    summary: "Walkthrough step 2 exits 1 if the document import applies the code overrides file"
    location: "src/squadron/benchmark/recall/hand_run_overrides.py:65-67"
  - id: F007
    severity: concern
    category: under-specification
    summary: "The import changes are incomplete, and one is under-specified"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:104-125"
  - id: F008
    severity: concern
    category: integration
    summary: "The service factory is built before the case set is known, so per-kind templates cannot reach it"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:213"
  - id: F009
    severity: concern
    category: error-handling
    summary: "The comb refusal sits inside the lock, after the code path that would crash on it"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:351"
  - id: F010
    severity: concern
    category: error-handling
    summary: "The score-severity keyword defaults to the code constant, a silent fallback"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:239-240"
  - id: F011
    severity: concern
    category: testing
    summary: "The text-report change breaks an existing test the design says is unchanged"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:384"
  - id: F012
    severity: concern
    category: under-specification
    summary: "Bug-hits split by label source cannot be computed from the current label resolver"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:326"
  - id: F013
    severity: concern
    category: integration
    summary: "The matcher's leak check has no context type, and the design cites the wrong module"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:82"
  - id: F014
    severity: concern
    category: integration
    summary: "The match contract does not say what `_stage` receives, and a MATCH stage would be parsed as a comb"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:291"
  - id: F015
    severity: concern
    category: identity
    summary: "The matcher identity records the alias's `tool_use`, but the matcher runs with no tools"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:307"
  - id: F016
    severity: concern
    category: state
    summary: "A crash after a paid matcher call pays again, although 430 already avoids this"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:318"
  - id: F017
    severity: concern
    category: operator-walk
    summary: "A clean-start operator cannot run steps 4–6 as written"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:520-552"
  - id: F018
    severity: concern
    category: proportionality
    summary: "Proportionality: several parts exceed what the plan entry asks for"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:308-325"
  - id: F019
    severity: concern
    category: duplication
    summary: "`match_loop` duplicates `run_loop`'s serial, cap, resume and record logic"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:293"
  - id: F020
    severity: note
    category: under-specification
    summary: "Gate-only entries take their config from other files, and the presence check passes null fields"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:258"
  - id: F021
    severity: note
    category: alignment
    summary: "The architecture's record-size premise (\"they are short\") does not hold for documents"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:417"
  - id: F022
    severity: note
    category: existing-code
    summary: "The design names `check_review_timeout` as the reuse point; the recall path uses `require_review_timeout`"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:82"
  - id: F023
    severity: note
    category: state
    summary: "Answer-key isolation rests on commit dates, not on a check"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:221-227"
  - id: F024
    severity: note
    category: patterns
    summary: "`COMB_TEMPLATE` is defined twice"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:368"
  - id: F025
    severity: note
    category: verification
    summary: "Several of the design's numbers could not be checked from this environment"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:228"
  - id: F026
    severity: pass
    category: functional-requirements
    summary: "Section 16's bug-hit totals reproduce from RESULTS.md"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:449-453"
  - id: F027
    severity: pass
    category: scope
    summary: "The scope matches the plan entry, and the counts add up"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:31-40"
  - id: F028
    severity: pass
    category: existing-code
    summary: "The gate change is correct and needed"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:231-235"
---

# Review: slice — slice 432

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Flaws with no later correcting commit are counted, against the architecture's ground-truth rule

The architecture says "A bug counts only when a later commit or issue shows it was real" (`420-arch.model-benchmark.md:142`), and it lists curated expected-output datasets as a non-goal (`:161`). D1 keeps flaws with `proof: []`, meaning "verified at the reviewed commit, no later commit." The migratory narrative states "no later commit proves a flaw" (`design-review-recall-cases-migratory.md:15`). Its 31 flaws (the migratory rows of `cases.tsv`) are 38% of the 82. D1 itself says "many of the 82 flaws do not meet that." The fix is the PM's amendment (line 172), and the success criteria (section 16 reproduction, the 43 cases, the arch target of 40) all count these flaws. D11 extends reading-based verification to new arch cases, which conflicts with `420-arch.model-benchmark.md:163` (no per-case human review) and is not reconciled. Do not write the 43 files or the import on this rule until the amendment exists. Otherwise, report verified-only recall as a separate measure.

### [CONCERN] The sandbox rebuild deviates from the reviewer-recall sandbox the architecture defines

`420-arch.model-benchmark.md:36` says reviewer recall's sandbox "holds the diff's head and its ancestry back to base, and nothing later." D3 rebuilds the repository as one commit with no ancestry. The design flags this and proposes an amendment (line 226), but the sandbox design and its leak reasoning are built on it. The rebuild is defensible because it keeps earlier saved reviews unreachable, so the fix is to record the amendment before D3 is built.

### [CONCERN] Absent grader keys are read as decided misses, against "absent is not zero"

`420-arch.model-benchmark.md:82` says a run with no grade is recorded as such, and "Absent is not zero." D8 reads every absent `hits` key as a graded MISS, for 671 flaw-and-review pairs, and argues in-line (line 271) that the principle does not apply. I checked the evidence: `grade/squadron-320-arch/hits.json` has `hits: {}` for F1 with a note naming r02, r03 and r05, and `score_all.py:26-31` reads absence the same way, so section 16 used this rule. The inference is disclosed and counted, which is good. But it decides every document row's recall and is an exception to an explicit principle. Add it to the amendment list instead of reasoning around the principle.

### [CONCERN] The matcher bound uses a flat per-call figure; the architecture asks for bounds from observed costs

Line 325 sets the bound to pending calls × `--call-cost` plus one overshoot, and says "observed costs are not used, so `run_bound` is not touched." `420-arch.model-benchmark.md:134` says grading and judging, run as separate commands, have "a bound estimated from observed costs of those calls in the store." A matcher is a judging step, and a flat figure can understate the bound on long documents. Use observed matcher costs with `--call-cost` as the fallback, as `run` does, or amend `:134` and say so.

### [CONCERN] The three named inputs for the 43 case files cannot supply the required fields

D1 says the 43 files are written from `cases.tsv`, `against.tsv` and `grade/<case>/flaws.json`. Those do not carry the required fields. `flaws.json` has only `id`, `text` and `hits` per flaw, with no `proof`, `original_review` or `source`. `cases.tsv` has id, repo, sha, kind, document path and a count, with no `host_repo`, `distribution`, `proof` or `source`. `exclude` comes from `prepare.py:22` (`project-documents/user/reviews`), which D1 does not name. `proof` and `source` exist only in the narrative files, which D1 keeps as "narrative record." Name the source of every field and the procedure for the 43 files. Otherwise the writer will invent `original_review` and `proof` values.

### [CONCERN] Walkthrough step 2 exits 1 if the document import applies the code overrides file

D2 (line 212) says `ImportContext` gains `overrides_path` and the code plan "still passes its pass labels into `plan_overrides`." It does not say whether the document plan does too. If it does, every entry is skipped. The committed overrides file names `squadron-197` and `trading-data-921` (`project-documents/user/reference/review-recall-overrides.yaml:5,12`). Neither is a `doc-flaws-*` case, so `plan_overrides` lists each as "no case named." `run_import` still writes the records and then exits 1 (`benchmark_recall_import.py:71-73`). Walkthrough step 2 (lines 503-509) therefore fails as written and reports skipped entries for each kind. State that the document plan does not read overrides. The code overrides are keyed to code passes through `PassLabels` and cannot be reused as they are.

### [CONCERN] The import changes are incomplete, and one is under-specified

- `render_import_summary` hard-codes "Label conflicts (later pass wins)" (`benchmark_recall_import.py:39`). The new summary lines (absent-key count, regrade count, largest record size, gate-only count) need `cli/commands/benchmark_recall_import.py`, which is not in the change table.
- D8's EARLIER policy reverses what `_set_hit` does. Today it removes the earlier value and writes the later one (`hand_run_labels.py:229-245`). State that EARLIER skips the write and keeps the first value, and where the conflict is recorded.
- Import labels need an `updated` date. `folder_date` takes a `YYYYMMDD` prefix (`import_plan.py:85-91`), but the grading folders are `grade`, `grade2`, and so on (line 266). Say `folder_date("20261116-mined")`, or a second import will not be byte-identical.
- D2 says `overrides_path` is filled "as it does today." Today it is an argument to `build_import_plan` (`hand_run_import.py:24`), not a context field.

### [CONCERN] The service factory is built before the case set is known, so per-kind templates cannot reach it

D2 says templates "come from the set's kind, once per command." The change table says `live_services.py` and `recall_services.py` build `config_for` and the resolver from the kind's templates. But `build_production_recall_services(repo_root)` constructs `stage_resolver=LiveStageResolver()` (`recall_services.py:87`), and `build_production_live_services` sets `config_for=live_stage_config` (`live_services.py:63`), before any command reads the set. The set is first read inside each command (`benchmark_recall_import.py:52`, `benchmark_recall_run.py:59`), and `RecallServicesFactory` is `Callable[[Path], RecallServices]`. Say how the kind reaches the seam: a factory that takes the kind, or resolvers built per call.

### [CONCERN] The comb refusal sits inside the lock, after the code path that would crash on it

D10 says `run` with combs on a document kind is "refused, exit 1, before the lock." The change table puts the refusal in `run_plan.py` (line 116), which runs inside `_plan` after `recall_lock` (`benchmark_recall_run.py:118-119`). Without a check, `live_stage_config` indexes `STAGE_TEMPLATES[COMB]` (`stage_identity.py:41`). That `KeyError` is caught by neither the `except` at `stage_identity.py:42` nor `RUN_ERRORS` (`benchmark_recall_run.py:43`), so the user sees a traceback. Put the check in the command before the lock. `report` with a comb recipe on a document set should refuse too, because otherwise every case is silently "left out."

### [CONCERN] The score-severity keyword defaults to the code constant, a silent fallback

D5 adds `scored: frozenset[str] = SCORED_SEVERITIES`, and line 436 says existing callers are unchanged. Any document caller that forgets the keyword silently scores with code severities, dropping NOTE. Only the section 16 test would catch it, and the general rules forbid silent fallbacks. Make the argument required and pass the trait at each call. The design also has to name the functions that carry it: `recipe_outputs` (`scoring.py:95-101`) and `_pair_variants` (`scoring.py:141`) sit between the report and `reviewer_output` (`scoring.py:164`). `label_candidates.py:75` is the other filter.

### [CONCERN] The text-report change breaks an existing test the design says is unchanged

Line 384 says `report` "prints two more columns," while line 240 says "code rows are unchanged." `tests/benchmark/recall/test_report_render.py:50-51` pins the header and a separator of `"|" + "---|" * 14`, plus an exact row. Adding columns breaks it, and it is not listed at lines 132-134 ("Existing tests that change, and no others"). Decide whether code reports get the columns. If they do, update the test and list it. If not, the renderer needs a per-kind column set.

### [CONCERN] Bug-hits split by label source cannot be computed from the current label resolver

Line 326 splits each row's bug-hits "by the labeler kind of the deciding HIT label," and line 470 requires that in the text report. `ResolvedLabels` (`label_precedence.py:16-32`) keeps only the winning verdict per key and bug, not who gave it. `resolve_labels` applies records in a fixed order (`label_precedence.py:53`). Add a per-(key, bug) labeler kind to `ResolvedLabels` and name it in the change table.

### [CONCERN] The matcher's leak check has no context type, and the design cites the wrong module

Line 82 places `LeakChecker` in `recall/leak_check.py`. It is defined at `stage_runner.py:64`. Its `check` takes a `StageContext` whose `stage` is a `PendingStage` (`stage_runner.py:57`). The checker reads `context.stage.case` (`leak_check.py:64`) and logs with `stage_label(context.stage)`. A matcher call has neither a `PendingStage` nor a sandbox, so D9's "leak-scanned or marked confined as a 430 stage call is" (line 294) cannot run as written. Define the matcher's context, or an entry point that takes the case and the home, and fix the citation.

### [CONCERN] The match contract does not say what `_stage` receives, and a MATCH stage would be parsed as a comb

`_stage --input` is documented as "JSON list of findings to comb" (`benchmark_recall_stage.py:49`) and read by `read_stage_input` (line 61). The matcher needs flaws and findings, and D9 never gives the input format. Also, `ingest_output` sends every non-REVIEW kind to `_comb_parts` (`stage_ingest.py:108-111`). Adding `StageKind.MATCH` without a branch would read a match output as comb decisions. State the matcher's input shape, and say that the match entry is built by its own function.

### [CONCERN] The matcher identity records the alias's `tool_use`, but the matcher runs with no tools

The matcher identity comes from the stage config. `stage_config` sets `tool_use=model_allows_tools(alias)` (`recipes/stage_config.py:55`), and D9 says the matcher runs with `allowed_tools=[]` (line 296). The stored identity therefore names a tool configuration the matcher never had. `420-arch.model-benchmark.md:55` requires the config to name the alias's `tool_use`. Either record the tools actually given for matchers or state the choice. As written, two aliases that differ only in `tool_use` become two matchers that behave identically.

### [CONCERN] A crash after a paid matcher call pays again, although 430 already avoids this

The resume table says a call that ran but stored no match entry "is made again." 430's stage path does not re-call: `ingest_orphan` (`stage_runner.py:167-183`) rebuilds the entry from the leftover output and the scrubbed home, and makes no new call. The design gives no reason for the difference. A leftover-output rebuild would need the home kept until the entry is stored, as 430 does (`stage_runner.py:6-7`). Either reuse the orphan path or state the cost of the re-call.

### [CONCERN] A clean-start operator cannot run steps 4–6 as written

`benchmark.review_timeout_s` has no default (`src/squadron/config/keys.py:656-664`), and `run` refuses without it (`run_bound.py:43-47`). `match` is specified to refuse without it too (line 459). None of walkthrough steps 4–6 sets it, and the runbook section (line 485) does not name it. Name the key and the command that sets it, in both the walkthrough and the runbook section.

### [CONCERN] Proportionality: several parts exceed what the plan entry asks for

The plan entry for 432 (`420-slices.model-benchmark.md:183-191`) asks for the 43 cases scored per kind by 430's report, a section 16 reproduction for three recipes, and #373's arch cases. It does not ask for the following, which add a large share of the design:
- `match --recheck` (lines 323-324). The design calls its output "informational," with no pass mark. It writes nothing, cannot be resumed, costs nine calls, and changes no score. Cut it, or move it after step 6.
- Two-matcher coexistence (lines 308-311), `--matcher` on `report` and `label`, the refusal, and the header lines. The plan needs one matcher. Refuse a second matcher per set now and add coexistence when a second one is needed.
- The `cases list` reference check and its WARNING row (lines 228, 338). The three unreferenced commits are a known risk; a note in the case file covers it.
Name these as deferrals. Several D10 rows disappear with them.

### [CONCERN] `match_loop` duplicates `run_loop`'s serial, cap, resume and record logic

D9 gives the matcher its own loop, justified by `PendingStage` and sandbox coupling. The responsibilities are the same as `run_loop`'s: serial calls, bound and cap checks, resume from stored entries, harness-failure mapping, and store writes. The general rules forbid duplicated logic. Extract the shared parts (cap, resume key, outcome mapping), or state which parts the match loop does not share and why.

### [NOTE] Gate-only entries take their config from other files, and the presence check passes null fields

D7 is explicit that a gate file's model, profile, tools, effort and token limit are not read, and that the entry takes its alias's model-call config. That is a disclosed inference. The implementation must bypass the presence check in `_load_document` (`hand_run_reviews.py:103-105`) and `_review_config` (`:109-117`) for these files, because a gate file has `null` for `profile` and `tools_given`. Say so in the design.

### [NOTE] The architecture's record-size premise ("they are short") does not hold for documents

`420-arch.model-benchmark.md:144` justifies inline findings with "they are short." The design measures document findings at a median of 47 KB per run record and keeps them inline. The 1 MB target is restated, which is good, but the premise is not amended. Add it to the amendment list.

### [NOTE] The design names `check_review_timeout` as the reuse point; the recall path uses `require_review_timeout`

`check_review_timeout` is defined in `src/squadron/benchmark/grading_config.py:27`. The recall entry point is `require_review_timeout` (`run_bound.py:43`), which calls it. Name the recall function that the match loop reuses.

### [NOTE] Answer-key isolation rests on commit dates, not on a check

The sandbox excludes saved reviews only. The hand-run answer key (`20261116-mined/grade*/…/flaws.json` and RESULTS.md) is committed in this repo. A case whose reviewed commit is later than that commit would contain the flaw text. The cases I checked come from slices created in late September 2026 (927 on 20260926, 928 on 20260927), so the risk is probably not live. `cases add` should assert that no answer artifact exists at each commit, not assume it.

### [NOTE] `COMB_TEMPLATE` is defined twice

The general rules want one definition per value. `stage_runner.py:50` (`COMB_TEMPLATE = "comb"`) duplicates `stage_config.py:27` (`COMB_TEMPLATE_NAME`). The design's "one constant" line covers the none word, the gate-only test and the agent prefix, but not this value, and `_stage` will use it.

### [NOTE] Several of the design's numbers could not be checked from this environment

I could not run git, measure record sizes or recount grade files from a shell. These are unverified: the three unreferenced commits and their fetchability; the 2–527 saved reviews per tree; 161 NOTE-only hits of 1,074; 11 of 574 regrade disagreements; 172 anchors; 671 absent pairs; the "flaws found in any run" columns of the section 16 table; and the 129-record size figures. The PM's walkthrough run checks them.

### [PASS] Section 16's bug-hit totals reproduce from RESULTS.md

The per-run means in RESULTS.md section 16 (`RESULTS.md:321-323`) multiplied by 3 give the bug-hit totals in the table. fable-medium: 12.7×3=38, 14.0×3=42, 19.7×3=59. haiku-xhigh: 9.7×3=29, 16.0×3=48, 18.0×3=54. opus-high: 11.7×3=35, 13.7×3=41, 17.3×3=52. The "any run" columns are unverified (above).

### [PASS] The scope matches the plan entry, and the counts add up

The 43 cases, three-kind scoring, import of the hand-run results and #373's arch cases are all present (`420-slices.model-benchmark.md:183-191`). `cases.tsv` has 9 arch, 17 slice and 17 tasks rows. The out folder has 1,281 files, and 259 + 515 + 507 = 1,281.

### [PASS] The gate change is correct and needed

`hit_rule.gate` (`src/squadron/benchmark/recall/hit_rule.py:74-81`) returns DECIDED_MISS for any finding that cites a path when the bug has no locations. D4 says so, and the fix is needed. The only existing test that builds empty locations (`tests/benchmark/recall/test_case_models.py:69`) tests `KnownBug` validation, so it is unaffected.

### Run Digest

- Response length: 39350 chars
- Response is newline-free: no
- Tool calls made: 104
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 105
- Tokens — prompt / cached / cache write / completion / reasoning: 10413183 / 10084838 / 328243 / 175215 / not computed
- Duration: 790.5 s
- Cost: $1.14 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 28
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 28
- Finding-shaped matches — surviving validation: 28
