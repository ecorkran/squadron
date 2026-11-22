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
reviewedSha: ce420b84bf669073152217ee30b1092ef108c57c
reviewedBlob: 09b713cd9fcdc3d26ce52f53fa18db1ae6cb8d27
reviewedBlobCurrent: false
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 82
injected:
  - key: input
    path: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md"
    chars: 39534
    sha256: 90d95936ad03c6890a98131ae9c3e43004ed3c43ddb0a293c6c343a22dec9b8d
    whole: true
  - key: against
    path: "project-documents/user/architecture/420-arch.model-benchmark.md"
    chars: 30840
    sha256: 3b909db8ad85dd24d2d2195772f10ecf022a254653af1faaa958b1f54dc13b07
    whole: true
filesRead:
  - "project-documents/user/slices/430-slice.real-bug-review-recall.md"
  - "src/squadron/metrology/recall_case_models.py"
  - "src/squadron/benchmark/recall/kinds.py"
  - "src/squadron/metrology/recall_run_models.py"
  - "src/squadron/metrology/recall_label_models.py"
  - "src/squadron/benchmark/recall/hit_rule.py"
  - "src/squadron/benchmark/recall/stage_identity.py"
  - "src/squadron/benchmark/recall/label_precedence.py"
  - "src/squadron/benchmark/recall/review_sandbox.py"
  - "src/squadron/replay/history_free_sandbox.py"
  - "src/squadron/review/task_gate.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/cases.tsv"
  - "project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-320-arch-fable-medium-1.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-197-tasks-fable-medium-1.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/map.json"
  - "src/squadron/benchmark/recall/hand_run_import.py"
  - "src/squadron/benchmark/recall/import_plan.py"
  - "src/squadron/benchmark/recall/hand_run_reviews.py"
  - "src/squadron/benchmark/recall/review_output.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/r01.json"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/flaws.json"
  - "tests/benchmark/recall/test_decisions.py"
  - "tests/benchmark/recall/test_report_json_schema.py"
  - "src/squadron/benchmark/recall/scoring.py"
  - "src/squadron/data/templates/comb.yaml"
  - "src/squadron/review/review_client.py"
  - "src/squadron/cli/commands/benchmark_recall_stage.py"
  - "src/squadron/benchmark/recall/real_work.py"
  - "src/squadron/benchmark/recall/live_services.py"
  - "project-documents/user/reference/review-recall-results/RESULTS.md"
  - "src/squadron/benchmark/recall/leak_check.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/prepare.py"
  - "project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-400-arch/hits.json"
searches:
  - "list_files src/squadron/benchmark/**/*.py in ."
  - "list_files project-documents/user/slices/430* in ."
  - "list_files project-documents/user/reference/review-recall-results/* in ."
  - "list_files project-documents/user/reference/review-recall-recipes/* in ."
  - "list_files **/templates/**/*.yaml in ."
  - "list_files tests/benchmark/recall/**/* in ."
  - "list_files src/squadron/benchmark/recall/**/*.py in ."
  - "list_files src/squadron/metrology/recall*.py in ."
  - "grep ^#+ |^### D1[0-9]|^### D[0-9] in project-documents/user/slices/430-slice.real-bug-review-recall.md"
  - "grep STAGE_TEMPLATES|live_stage_config|LiveStageResolver|\\.resolve\\( in /Users/manta/source/repos/manta/squadron/src"
  - "grep def builtin_template_hash|COMB_TEMPLATE_NAME\\s*=|def stage_config|def stage_config\\( in /Users/manta/source/repos/manta/squadron/src/squadron/recipes"
  - "grep @.*command|add_parser|\\\"--against\\\"|'--against'|\\\"--no-save\\\"|\\\"--output-path\\\"|\\\"--cwd\\\"|\\\"--model\\\"|\\\"--output\\\" in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "list_files src/squadron/cli/commands/review*.py in ."
  - "grep TASK_GATE_MODEL|class TemplateOutput|DECISIONS\\b|def run_review_with_profile in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep template|task_gate|TASK_GATE in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "grep \\\"arch\\\"|\\\"slice\\\"|\\\"tasks\\\"|BuiltinReviewTemplate\\.(ARCH|SLICE|TASKS) in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands/review.py"
  - "list_files * in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined"
  - "list_files project-documents/user/reference/review-recall-results/20261116-mined/grade*/* in ."
  - "grep ^  \"(model|profile|template_name|effort|tools_given|max_output_tokens|squadron_version|tool_calls_made|input_files|verdict_source|cost_usd|template_hash|effort_sent)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-320-arch-fable-medium-1.json"
  - "grep ^  \"(model|profile|template_name|effort|tools_given|max_output_tokens|squadron_version|tool_calls_made|input_files|verdict_source|cost_usd|template_hash|effort_sent)\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-197-tasks-fable-medium-1.json"
  - "list_files * in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade"
  - "list_files * in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade5"
  - "grep ^#+ .*16|12\\.7|14\\.0|19\\.7 in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/RESULTS.md"
  - "list_files **/hits.json in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined"
  - "grep SCORED_SEVERITIES|DECIDED_MISS|GateResult|locations=\\(\\)|locations=\\[\\]|\"locations\": \\[\\]|base=None|ValidationError|recall_fetch_timeout_s|review_timeout_s|auth_probe_timeout_s in /Users/manta/source/repos/manta/squadron"
  - "grep keys|== \\{|set\\(|sorted\\(|schema|top_level|assert .*\\.keys\\(\\) in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/test_report_json_schema.py"
  - "grep glob|rglob|user/reference|review-recall-cases in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep gate\\(|locations|CANDIDATE|DECIDED|base=|base\\\"|RecallCaseKind|StageKind|LabelerKind|register_kind|registered_kind|get_kind|SCORED|STAGE_TEMPLATES|Cannot|ValidationError in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall"
  - "grep SCORED_SEVERITIES\\s*=|^def run_bound|^def run_plan|^def run_loop|^def stage_runner|class ReviewBudget|class StageIdentityResolver|def parse_decisions|class LeakVerdict|def build_leak_rules|def run_auth_check|def _stage|\"_stage\"|_auth-probe|_auth_probe in /Users/manta/source/repos/manta/squadron/src"
  - "grep GIT_AUTHOR_DATE|GIT_COMMITTER_DATE|case_file|write_text|def build|commit in /Users/manta/source/repos/manta/squadron/tests/benchmark/recall/fixtures/bug_repo/build.py"
  - "grep SCORED_SEVERITIES|resolve\\(|StageIdentityResolver in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep def finding_id_at|return f\"F|F\\{|ConfigFor\\s*=|class ConfigFor|def run_comb_stage|def _sandbox|SandboxError in /Users/manta/source/repos/manta/squadron/src/squadron/recipes/comb_call.py"
  - "grep SandboxError|ConfigFor|harness_failure|HARNESS_FAILURE in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "list_files *-arch-*.json in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out"
  - "grep version|def |unchanged|no change|identical in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall/case_intake.py"
  - "grep version|RecallCaseSet\\(|def _write|def add|def cases_add|no new version|already in /Users/manta/source/repos/manta/squadron/src/squadron/cli/commands"
  - "grep \\b(hy4|mimo|luna-r|fable-medium|opus-high|fable-haiku)\\b in /Users/manta/source/repos/manta/squadron/src/squadron"
  - "grep LeakInputs\\(|repo_root=|distribution_name=|host_owner= in /Users/manta/source/repos/manta/squadron/src/squadron/benchmark/recall"
  - "grep ^\\[?(hy4|mimo|luna-r|fable-medium|opus-high|haiku-xhigh|fable|luna|sol)\\]?|^(hy4|mimo|luna-r|fable-medium|opus-high)\\s*=|\\[aliases\\.(hy4|mimo|luna-r|fable-medium|opus-high)\\] in /Users/manta/source/repos/manta/squadron/src/squadron/data/models.toml"
  - "list_files .gitattributes in /Users/manta/source/repos/manta/squadron"
  - "list_files .gitattributes in /Users/manta/source/repos/manta/context-forge"
  - "list_files .gitattributes in /Users/manta/source/repos/manta/migratory"
  - "grep \"severity\": \"PASS\" in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out"
  - "grep \"i\": (\\d+) in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade/squadron-320-arch/hits.json"
  - "grep \"severity\": \"PASS\"|\"title\":  in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-400-arch-fable-medium-1.json"
  - "grep squadron-400-arch/ in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade/map.json"
  - "grep \"severity\": \"PASS\"|\"title\":  in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/out/squadron-360-arch-fable-medium-2.json"
  - "grep squadron-360-arch/ in /Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined/grade2/map.json"
sectionsInDocument: 41
sectionsCovered: 30
sectionsNotCovered:
  - "D1 \u2014 A document case is the reviewed document, its commit and its verified flaws"
  - "D2 \u2014 Three kinds, one implementation, and the kind carries its traits"
  - "D3 \u2014 The sandbox is the reviewed tree with saved reviews removed and no history"
  - "D4 \u2014 A bug with no locations is not gated"
  - "D5 \u2014 Document kinds score NOTE findings"
  - "D6 \u2014 One kind per case set"
  - "D7 \u2014 Import of the mined review outputs"
  - "D8 \u2014 Import of the grading passes: the first pass to grade a review wins"
  - "D9 \u2014 `match`: an agent matches findings to flaws, blind, for document kinds"
  - "D10 \u2014 Failure modes and how each is observed"
  - "D11 \u2014 More architecture cases are mined by hand and added as files (#373)"
effort: xhigh
turns: 83
promptTokens: 6018624
cachedTokens: 5736145
cacheWriteTokens: 282411
completionTokens: 162087
durationSeconds: 733.7
costUsd: 0.838514
costBasis: provider
runId: run-20261121-p4-9ad65e46
squadronVersion: 0.24.37
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "`--recheck` cannot \"change no score\" under the precedence rule the design states"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:257-260"
  - id: F002
    severity: fail
    category: architecture-alignment
    summary: "Document flaws with no later commit contradict the architecture's ground-truth rule"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:148"
  - id: F003
    severity: concern
    category: correctness
    summary: "The matcher prompt uses one `F` namespace for both findings and flaws"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:250-253"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "The document sandbox departs from 430 D7 and the 420 amendment without saying so"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:196-199"
  - id: F005
    severity: concern
    category: integration
    summary: "`report --json` gains fields in a schema test that is pinned for slice 433"
    location: "tests/benchmark/recall/test_report_json_schema.py:7-17"
  - id: F006
    severity: concern
    category: under-specification
    summary: "The changed-module table omits the call sites that carry the stage kind"
    location: "src/squadron/benchmark/recall/run_plan.py:33"
  - id: F007
    severity: concern
    category: consistency
    summary: "Scored severities are defined twice, and one consumer is missing from the change list"
    location: "src/squadron/benchmark/recall/real_work.py:18"
  - id: F008
    severity: concern
    category: integration
    summary: "Integration calls the 430 changes \"additive\"; several are signature or type changes"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:346"
  - id: F009
    severity: concern
    category: duplication
    summary: "A second lenient line parser duplicates `parse_decisions`"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:253"
  - id: F010
    severity: concern
    category: testing
    summary: "Matcher fixtures placed in the existing decisions folder would break a comb test"
    location: "tests/benchmark/recall/test_decisions.py:77-83"
  - id: F011
    severity: concern
    category: error-handling
    summary: "Resume re-spends on every partial or failed matcher call"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:250-255"
  - id: F012
    severity: concern
    category: state
    summary: "Labels and the match entry are written separately, so a crash between them loses the call"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:254-258"
  - id: F013
    severity: concern
    category: architecture-alignment
    summary: "The matcher's identity is its alias, and mixed matchers are not flagged"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:254"
  - id: F014
    severity: concern
    category: architecture-alignment
    summary: "Absent grader keys are recorded as MISS, which the \"Absent is not zero\" principle rules out"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:239"
  - id: F015
    severity: concern
    category: architecture-alignment
    summary: "Agent-matched hits enter the primary recall with no separate reporting or threshold"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:262"
  - id: F016
    severity: concern
    category: scope
    summary: "Arch mining is open-ended human work inside an implementation task, and 430 D13 does not cover it"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:289"
  - id: F017
    severity: concern
    category: operability
    summary: "Walkthrough step 4 asks to inspect a sandbox that is removed on exit"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:429"
  - id: F018
    severity: concern
    category: operability
    summary: "The fixture's commit shas are unstable, so the committed case folder cannot match a fresh build"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:422-423"
  - id: F019
    severity: concern
    category: error-handling
    summary: "`exclude` paths are not checked when cases are added, and the design gives two handlings"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:200"
  - id: F020
    severity: concern
    category: error-handling
    summary: "Two new I/O paths have no failure rows"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:270-282"
  - id: F021
    severity: concern
    category: proportionality
    summary: "A new hidden matcher command duplicates the existing stage command"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:309"
  - id: F022
    severity: concern
    category: testing
    summary: "No walkthrough step produces matcher fixtures from two providers"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:253"
  - id: F023
    severity: note
    category: accuracy
    summary: "Gate-only outputs do not \"record no model\""
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:228"
  - id: F024
    severity: note
    category: consistency
    summary: "Flaw text carries curator annotations that the matcher will read"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:145"
  - id: F025
    severity: note
    category: testing
    summary: "The `i` mapping assumes grader indices equal the output's finding indices"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:238"
  - id: F026
    severity: pass
    category: dependencies
    summary: "Interfaces the design relies on exist as described"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:74-82"
  - id: F027
    severity: pass
    category: correctness
    summary: "The hit-rule claim holds, and the case-level change is needed"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:204-207"
  - id: F028
    severity: pass
    category: correctness
    summary: "The sandbox comparability claim holds"
    location: "project-documents/user/slices/432-slice.document-review-recall-from-real-corrections.md:195"
---

# Review: slice — slice 432

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] `--recheck` cannot "change no score" under the precedence rule the design states

Line 257 says the newest agent label wins and imports stay in force. Line 260 stores `--recheck` labels under the agent labeler "so they do not change any score". Neither holds:

- For a finding with no import label, an agent label is the only label and is in force. A recheck that labels it turns an undecided candidate into a decided one, which moves the row's recall.
- `labels_record_id` (`src/squadron/metrology/recall_label_models.py:68-72`) keys one record per (case, labeler). Writing recheck labels under the existing agent labeler replaces the record that scores.
- If they go under a new labeler, newest-wins (`src/squadron/benchmark/recall/label_precedence.py:53-58`) makes them win.

The acceptance criterion at line 371 cannot be met as written. Give recheck output its own record that is never in force, or drop the claim and print only the disagreement.

### [FAIL] Document flaws with no later commit contradict the architecture's ground-truth rule

D1 lets `proof` be empty, citing "all of migratory's" flaws, and substitutes a mining-file `source`. The 420 architecture says "A bug counts only when a later commit or issue shows it was real" (`420-arch.model-benchmark.md:142`). Migratory is 13 of the 43 cases (`cases.tsv` rows 31–43). The 430 code-case schema requires a proof. The design does not name this as a deviation and does not amend 420.

Either the PM amends 420 with the reason documents cannot meet the rule, or the proof-less flaws are excluded and the flaw totals (19/32/31) and the section 16 reproduction are recomputed. The decision is needed before the case files are written. D11's 40-flaw target depends on it.

### [CONCERN] The matcher prompt uses one `F` namespace for both findings and flaws

Finding ids are positional `F1…Fn` (`src/squadron/recipes/comb_call.py:29-31`). Flaw ids are `F1…Fk` from `flaws.json` (line 145). The matcher input carries both, and each output line is "the finding id, then the ids of the flaws it matches". A line `F3: F1 — …` is ambiguous. A finding id that falls inside the flaw range parses as a flaw match, and the unknown-flaw-id rule (line 256) cannot catch it. The labels land silently in `RecallLabels`.

Use distinct prefixes for the two namespaces and say so in the prompt rule (line 252). Add a fixture where the namespaces overlap.

### [CONCERN] The document sandbox departs from 430 D7 and the 420 amendment without saying so

D3 rebuilds a one-commit repository. Line 383 says `HistoryFreeSandbox` is unchanged. Neither mentions that reviewer recall's sandbox differs from 430 D7, which holds head and its ancestry back to base (`src/squadron/benchmark/recall/review_sandbox.py:1-6`). The 420 amendment (`420-arch.model-benchmark.md:36`) says "one commit" describes the replay sandbox.

The rebuild is a sound leak fix: ancestry would keep excluded files, such as earlier reviews, reachable by `git show`. But the design must call it a deliberate exception and propose the amendment line, as 430 D7 did. The `--diff` reason in 430 D7 does not apply to `sq review arch`, which needs no merge base. Say so.

### [CONCERN] `report --json` gains fields in a schema test that is pinned for slice 433

The test asserts exact key sets at the top level and per row, and its docstring says "fixed for slice 433". The design adds `kind` and `gate_only_entries` at the top level and `label_sources` per row (line 328), so the test fails unchanged. Line 353 says "430's report reproduction tests pass unmodified", which does not cover this test. Slice 433 consumes `report --json` for its answers (line 342). Name this as a 433 contract change, update the test in the same change, and list 433 under Consumes from Other Slices.

### [CONCERN] The changed-module table omits the call sites that carry the stage kind

Line 188 moves the review template into traits, but several signatures receive no kind:

- `StageIdentityResolver.resolve(alias, stage_kind)` (`scoring_select.py:32-35`)
- `live_stage_config(alias, stage_kind)` (`stage_identity.py:35-41`)
- `ConfigFor` (`run_plan.py:33`)
- `LiveRunServices.config_for` (`live_services.py:63`)

A document run therefore cannot pick `arch`, `slice` or `tasks`. `recall_services.py` and `scoring_select.py` are missing from the changed-module table (lines 101–116). Test doubles pin the two-argument form: `tests/benchmark/recall/scoring_support.py:129`, `test_run_end_to_end.py:72`, and `test_stage_identity.py:48-72`. `RecallKind` gaining required `traits` and `plan_import` also breaks the `StubKind` at `test_run_end_to_end.py:183`. Name the new parameter and list each changed module and double.

### [CONCERN] Scored severities are defined twice, and one consumer is missing from the change list

The trait table (lines 180–184) gives code the set CONCERN, FAIL, which already exists as `SCORED_SEVERITIES` (`src/squadron/review/models.py:39`). The trait should reference that constant. `real_work.py:18,50` imports it too, and D5 (line 213) names only `scoring.py` and `label_candidates.py`. A comparison value must be defined once. Make the code trait reference the constant, and add `real_work.py` to D5 or justify leaving it out.

### [CONCERN] Integration calls the 430 changes "additive"; several are signature or type changes

The changes are not additive:

- `scoring.py` and `label_candidates.py` gain a required severity argument.
- `RecallKind` gains two required members.
- `StageIdentityResolver` and `ConfigFor` change arity.
- `RealBugCase.base` becomes optional.
- `resolve_labels` changes order.
- `split_output_name` (`src/squadron/benchmark/recall/hand_run_reviews.py:44-50`) changes behaviour, since it stops splitting at the first hyphen.

Line 190 also reverses 430 D14's stated contract ("432 adds DocumentKind … without changing them"). List that reversal in Consumes from Other Slices, with its consequences for 430's seam.

### [CONCERN] A second lenient line parser duplicates `parse_decisions`

`src/squadron/recipes/decisions.py:55` already parses lenient `<id>: VERDICT — reason` lines, with markdown, separators, prose rejection, and duplicate and unknown-id counting (`tests/benchmark/recall/test_decisions.py:17-61`). The matcher line needs the same tolerances with a different verdict vocabulary: a flaw-id list or a none word. Generalise the existing parser by vocabulary and keep one implementation. `match_lines.py` then becomes a thin mapping. The general rules require that logic not be duplicated.

### [CONCERN] Matcher fixtures placed in the existing decisions folder would break a comb test

`test_real_comb_outputs_parse_fully` globs every `*.json` under `fixtures/decisions/` and reads `raw_output`, `finding_ids` and `expected`. Matcher captures placed there fail with a KeyError. Line 253 does not say where the captures go. Name a separate folder (for example `fixtures/match/`).

### [CONCERN] Resume re-spends on every partial or failed matcher call

The unit at line 250 is "when the entry has a scored finding with no hit label from any labeler". A partial output (lines 255 and 277) or a timed-out call (line 276) leaves findings unlabelled, so the entry qualifies again on every rerun and each rerun makes paid calls. Walkthrough step 4's "a second `match` prints `0 calls to make`" (line 429) therefore holds only after a complete output.

430 D8 (`430-slice.real-bug-review-recall.md:343`) treats config failures as results that are not retried, but this rule retries them. "No hit label" is also ambiguous. An imported MISS is not a hit label, so read literally, every import-labelled finding is re-matched. Define the unit explicitly, keep config failures as recorded results, and state whether MISS counts as labelled.

### [CONCERN] Labels and the match entry are written separately, so a crash between them loses the call

Labels go to `RecallLabels` and the call goes to `RecallRun.matches`, with no stated order or atomicity. If labels are written and the process dies before the match entry, the next run sees labelled findings and skips the review (line 250). No entry then records the call's cost, `raw_ref` or `input_ref`, so the per-call cost used for the bound comes from fewer entries. The orphan rule in 430 D8 (line 328) covers an output file with no entry, not labels with no entry.

State the order (entry first, then labels, or re-derive labels from the stored output on resume) and the resume behaviour for each interrupted state.

### [CONCERN] The matcher's identity is its alias, and mixed matchers are not flagged

The labeler is `agent:<alias>@<hash8>`. The 420 design goals say the alias is for display only, and results must name the config (`420-arch.model-benchmark.md:55`). Alias identity also makes two aliases that resolve to one model into two graders.

The unit is per finding, so a run cut by a cap and resumed with a different `--model` gives one report row labels from two matchers, and nothing flags it. 430 D4 splits and flags a row only when stage identities differ. Key the labeler on `config_key`, and make matcher identity part of the row, or refuse a different matcher on a set that already has agent labels.

### [CONCERN] Absent grader keys are recorded as MISS, which the "Absent is not zero" principle rules out

Line 239 turns every (review, flaw) pair missing from `hits.json` into a stored MISS, in any case that has a `hits.json`. The 420 principle "Absent is not zero" (`420-arch.model-benchmark.md:82`) requires recording why. Here the reason is an inference about the graders' habit. The summary counts the absences, but no row shows which MISS labels are inferred. Step 3's reproduction cannot catch a dropped hit, because the same rule produced the 38/57 figure. Record inferred MISS as a distinct value, or state the inference as a decision with its evidence.

### [CONCERN] Agent-matched hits enter the primary recall with no separate reporting or threshold

The report counts label sources per row (line 262), but a document row's recall mixes imported, agent and person hits in one figure. The 420 principles say LLM signals are "reported beside [objective signals] with their own noise floors, never folded into them" (`420-arch.model-benchmark.md:51`) and call for "Breakdown, not a score" (line 84). The agent-only share of recall should therefore be shown separately, with the matcher's disagreement stated against a noise floor.

The recheck prints two numbers and "passes no judgment" (line 260). Line 436 names the yardstick "11 of 574" (line 240). That figure is grader-versus-regrader disagreement across 172 reviews. Step 5 compares the matcher against first-pass labels on nine reviews, a different population. Set the yardstick and threshold in the design, or present the number as informational only.

### [CONCERN] Arch mining is open-ended human work inside an implementation task, and 430 D13 does not cover it

Line 289 cites 430 D13 for reading squadron's history. That ruling covers four commits for three cases and "takes seconds" (`430-slice.real-bug-review-recall.md:427-430`). D11 instead reads every architecture document with a saved review across five or more repos, until 40 flaws are found or none remain. Development Approach step 6 (line 469) runs it as an implementation task. The 420 amendment says no task "needs hours" (`420-arch.model-benchmark.md:34`). Line 454 expects fewer than 21 new valid flaws, so the stop rule may run to exhaustion.

Move the mining out of the implementation task, as 430 D11 did for the live run, or bound it by time and candidate count. State that the 430 D13 ruling is being extended.

### [CONCERN] Walkthrough step 4 asks to inspect a sandbox that is removed on exit

Line 429 says "Confirm the sandbox tree has no reviews directory and `git log` in it shows one commit." Sandboxes are removed on exit (`src/squadron/replay/history_free_sandbox.py:116-123`, unless `keep()` is called). Nothing in the design keeps them, and the existing test asserts they are gone (`tests/benchmark/recall/test_run_end_to_end.py:139`). The step cannot run as written. Add a keep option for the fixture run, or assert the tree shape in a test.

### [CONCERN] The fixture's commit shas are unstable, so the committed case folder cannot match a fresh build

Step 4 builds `doc_repo`, then runs `cases add` on the committed `cases/slice/` folder. `cases add` refuses a commit that `git cat-file -e` cannot find (line 146). The existing `tests/benchmark/recall/fixtures/bug_repo/build.py` writes its case file into `out_dir` at build time (lines 101-102) and sets no commit dates, so every build produces new shas. Either `doc_repo/build.py` rewrites the committed case file, which makes the folder a build output, or it pins author and committer dates. Say which.

### [CONCERN] `exclude` paths are not checked when cases are added, and the design gives two handlings

Line 200 says an absent `exclude` path "fails the sandbox (`harness_failure`): the case file is wrong". D10 (line 273) says WARNING, with the case dropped from every recipe and counted. `cases add` (line 146) checks `document` and `against` only, and the refusal table (line 272) omits `exclude`. A wrong exclude path is a case-file error. Refuse it at `cases add`, as line 272 does for a wrong `document`, instead of counting it at run time.

### [CONCERN] Two new I/O paths have no failure rows

- **Case checks.** `cases add` now runs git checks on each document case (`git cat-file -e`, line 146), and `cases list` determines the unreferenced status (line 201). The D10 table has a row for "document missing at commit" but none for git failing, a repo path missing, or a timeout. 430 D8 has such a row only for `git show`.
- **Matcher lines.** A line that names a finding id absent from the input, and a finding with two lines, have no row. Line 278 covers only unknown flaw ids.

Add rows for each, with level and outcome.

### [CONCERN] A new hidden matcher command duplicates the existing stage command

`src/squadron/cli/commands/benchmark_recall_stage.py:47-53` already takes `--template`, `--input`, `--output` and `--model`. It runs in a scrubbed home with cwd set to the sandbox, and writes the output file the runner reads. `_match` (line 309) takes the same four options and would repeat that plumbing. Generalise `_stage`: make `--diff` optional for templates that do not need changed files, and dispatch by template. Otherwise justify a second entry point.

### [CONCERN] No walkthrough step produces matcher fixtures from two providers

Line 253 requires parser fixtures "captured from the fixture run (walkthrough step 4), from at least two providers". Step 4 passes one `--model <matcher alias>` (line 426) and runs one recipe at `--runs 1`. Add a step that runs `match` with a second matcher from a different provider, and say where the captures are stored.

### [NOTE] Gate-only outputs do not "record no model"

The gate result records `model: squadron-task-gate`, `profile: null`, `tools_given: null` and `template_name: tasks` (`src/squadron/review/task_gate.py:161-174`; see `out/squadron-197-tasks-fable-medium-1.json`). `_review_config` (`src/squadron/benchmark/recall/hand_run_reviews.py:109-117`) reads `model` and `profile` unchanged, so the special case must not use them. Also `effort` is null in these files, not the alias's effort. State the field values so the special case is explicit.

### [NOTE] Flaw text carries curator annotations that the matcher will read

`grade/squadron-320-arch/flaws.json` F1 reads "**VALID** … Raised by the original review (F004)" and cites line numbers in sibling documents. The design passes flaw text through unchanged so the matcher sees what the graders saw. That supports reproduction, but it puts provenance into the matcher input while the design calls the matcher blind. Decide whether the matcher gets the text as-is or stripped, and say which.

### [NOTE] The `i` mapping assumes grader indices equal the output's finding indices

Eight arch outputs contain PASS findings. In the two I checked (`squadron-400-arch-fable-medium-1` and `squadron-360-arch-fable-medium-2`), the PASS finding is last, so the mapping is undisturbed there. A PASS in the middle would shift indices if the grader numbered the filtered list. Each grader file (`rNN.json`) carries a `title` per `i`. The importer should check that the title matches the output's finding at `i` and refuse on mismatch. The refusal list at lines 241–244 has no such check.

### [PASS] Interfaces the design relies on exist as described

Confirmed: the three `sq review` commands and their options (`src/squadron/cli/commands/review.py`); `RecallKind`, `register_kind` and `KindContext`; `HistoryFreeSandbox`; `ImportPlan`, `ImportContext` and `folder_date`; `read_findings`, `read_usage` and `read_effort`; `TASK_GATE_MODEL`; `TemplateOutput.DECISIONS`; `run_review_with_profile`; `builtin_template_hash`; and `benchmark.recall_fetch_timeout_s`. The shipped templates `arch.yaml`, `slice.yaml` and `tasks.yaml` exist. `flaw-match.yaml` does not yet, as expected. The recipe aliases `opus-high`, `fable-medium`, `luna-r`, `mimo` and `hy4` are in `models.toml`.

### [PASS] The hit-rule claim holds, and the case-level change is needed

`hit_rule.gate` returns DECIDED_MISS for any path-citing finding when a bug has no locations (`src/squadron/benchmark/recall/hit_rule.py:78-81`), so D4's change is required. Committed code cases already assert that every bug has locations (`tests/benchmark/recall/test_committed_cases.py:37`), so the `CodeKind` refusal in D4 should not break them.

### [PASS] The sandbox comparability claim holds

`prepare.py` exports each commit with `git archive`, removes `project-documents/user/reviews`, and commits the rest as a one-commit repository (`20261116-mined/prepare.py:18-36`). The rebuild in D3 produces the same tree shape, plus the exclusions for each case. The root `.gitattributes` check found no `export-ignore` in squadron or migratory, so `git archive` and the fetch path yield the same files there.

### Run Digest

- Response length: 34332 chars
- Response is newline-free: no
- Tool calls made: 82
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 83
- Tokens — prompt / cached / cache write / completion / reasoning: 6018624 / 5736145 / 282411 / 162087 / not computed
- Duration: 733.7 s
- Cost: $0.84 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 28
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 28
- Finding-shaped matches — surviving validation: 28
