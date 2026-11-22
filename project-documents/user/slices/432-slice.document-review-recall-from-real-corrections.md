---
docType: slice-design
slice: document-review-recall-from-real-corrections
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies:
- 430
interfaces: []
dateCreated: 20261121
dateUpdated: 20261122
status: not_started
turns: 102
promptTokens: 21816233
cachedTokens: 21482793
cacheWriteTokens: 333268
completionTokens: 115282
durationSeconds: 1231.1
costUsd: 14.241854
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-fable-5-2:
    rounds: 3
    costUsd: 14.241854700000003
    completionTokens: 115282
revision_number: 2
---

# Slice Design: document-review-recall-from-real-corrections

## Overview

`sq benchmark recall` (slice 430) measures code reviewers on real escaped bugs. This slice makes it measure document reviewers: architecture documents, slice designs and task files. A case is a document at the commit that held the reviewed text, plus the flaws that were verified in it. The reviewer is the production `sq review arch|slice|tasks` command.

The hand-run work this replaces (`user/reference/review-recall-results/20261116-mined/`, RESULTS.md sections 16-20) holds:
- 43 cases with 82 flaws: 9 arch cases (19 flaws), 17 slice cases (32), 17 tasks cases (31).
- 1,281 review outputs from 35 config-and-run combinations, none byte-identical.
- Five blind grading passes (`grade/` … `grade5/`) that matched findings to flaws.

It is imported as records, and the report reproduces section 16's per-kind table from them with no new calls. A new command, `match`, does what the hand-run grading agents did: it matches a review's findings to the case's flaws with a model, blind, under a cost cap. After that, measuring a new model on documents is `run`, `match`, `report`.

## Value

- **User-facing.** "Which model reviews architecture documents, slice designs and task breakdowns" is answered by a repeatable command on the same cases each time. Today it takes a job list, a shell loop, a grading-input script, a batch of grading agents and a scoring script per batch.
- **Cheap re-measurement.** A new model costs its reviews plus one no-tools matcher call per review. Stored reviews of other configs are reused.
- **Architecture reviews get enough cases** (#373). 19 arch flaws cannot separate the top configs; this slice adds arch cases as records.

## Technical Scope

Included:
- Three case kinds, `arch`, `slice` and `tasks`, behind 430's `RecallKind` seam, with a document case-file format.
- The 43 mined cases written as case files, in one folder and one case set per kind.
- A document sandbox: the tree at the reviewed commit with saved reviews removed and no history.
- Import of the `20261116-mined/` review outputs and its five grading passes.
- `sq benchmark recall match`: an agent matcher for hit labels on document kinds, with bound, caps and resume, run through the existing hidden `_stage` command with a built-in `flaw-match` template.
- Kind traits that 430 hard-coded for code: review template, scored severities, whether combs and the matcher apply.
- Text report additions: each row's bug-hits split by label source and by proof status, the matcher in use, and a count of entries decided by the task gate.
- More arch cases mined and added as records (#373), and recipe files for the configs #373 names.

Excluded:
- The 9 first-pass cases of RESULTS.md sections 14-15 (`20261115-design/`). Their reviewed text is mostly not in git and sonnet had reviewed six of them. The plan's criterion is the 43 mined cases.
- Combs on document reviews. PM decision 20261117 (RESULTS.md section 18): no comb on design reviews. The `20261116-mined/comb/` outputs are not imported, and a recipe with combs is refused for a document set.
- Agent matching for code cases. The runbook rule "no model grades hits" stands for code; `match` refuses a code set.
- Grading findings REAL or MINOR (#340). Document rows show real share as ungraded.
- Running the #373 comparison. It is the PM's walkthrough step 6, because it is several hundred serial review calls.
- A case miner command (#326).
- New `report --json` fields for document sets (#386). The JSON document is unchanged; its reader, slice 433, was dropped on 20261119.
- Arch cases mined from squadron's own history (D11).
- Mixed-kind case sets and an all-kinds table. Each kind has its own set and its own report.

## Dependencies

### Prerequisites
- **430 (complete):** the `recall` package, its four record types, recipes, run loop, hit rule, labels, scoring, report and import plan.
- The source repos named by the case files (squadron, context-forge, migratory, and whatever the new arch cases add) readable at their recorded paths. A missing repo is a harness failure, as in 430 D8.

### Interfaces Required
- `sq review arch <doc>`, `sq review slice <doc> --against <parent>` and `sq review tasks <doc> --against <design>`, each with `--model <alias> --no-save --output file --output-path <file> --cwd .`. Production commands, unchanged.
- `RecallKind`, `register_kind`, `KindContext` (`recall/kinds.py`).
- `HistoryFreeSandbox` (`replay/history_free_sandbox.py`), unchanged.
- `ImportPlan`, `ImportContext`, `folder_date` (`recall/import_plan.py`); `read_findings`, `read_usage`, `read_effort` (`recall/review_output.py`).
- For the match loop (D9): `ReviewBudget`, `recall_lock`, `run_auth_check`, `ScrubbedEnvironment`, `resolve_sq_path()`, `LeakChecker` (`recall/leak_check.py`), `check_review_timeout` and the `render_bound` wording. The match loop does not use `run_loop`, `stage_runner`, `stage_ingest`, `run_plan` or `run_bound`.
- `run_review_with_profile` and `TemplateOutput.DECISIONS` for the matcher call.
- `TASK_GATE_MODEL` (`review/task_gate.py`), to recognise a task-gate output.
- `builtin_template_hash` (`recipes/stage_config.py`).

## Architecture

### Component Structure

New modules in `src/squadron/benchmark/recall/`:

| Module | Responsibility |
|---|---|
| `document_case.py` | `DocumentCaseFileSpec` and `FlawSpec`, their validation, and the existence checks at the commit (D1) |
| `document_recall_kind.py` | `DocumentRecallKind`, registered three times, once per kind (D2). Not `DocumentKind`: that name is the review package's enum (`review/document_target.py`) |
| `document_sandbox.py` | The reviewed tree with excluded paths removed and no history (D3) |
| `hand_run_documents.py` | Import of `20261116-mined/out/` (D7) |
| `hand_run_document_labels.py` | Import of the five grading passes (D8) |
| `match_plan.py` | Which review entries need a matcher call; bound and refusals (D9) |
| `match_loop.py` | Serial matcher calls: scrubbed subprocess, leak check, caps, the match entry, then the labels (D9) |
| `match_stage.py` | Matcher input rendering, `parse_matches`, and turning parsed lines into labels (D9) |

Changed modules:

| Module | Change |
|---|---|
| `kinds.py` | `KindTraits` and `DOCUMENT_SCORED_SEVERITIES`; `RecallKind` gains `traits` and `plan_import` (D2); `CodeKind` supplies both and reads `base` through `require_base` |
| `metrology/recall_case_models.py` | `RecallCaseKind` gains `ARCH`, `SLICE`, `TASKS`; `RealBugCase` gains optional `document`, `against`, `exclude`, `source`; `base` becomes optional, with `require_base` (D1) |
| `metrology/recall_run_models.py` | `StageKind.MATCH`; `RecallRun.matches`; `StageEntry.gate_only` and `input_ref` (D7, D9) |
| `metrology/recall_label_models.py` | `LabelerKind.AGENT` (D9) |
| `case_models.py` | `_require_text`, the YAML read and `_validation_reason` become public so `document_case.py` uses them. `CaseFileSpec` and `BugSpec` are unchanged |
| `hit_rule.py` | A bug with no locations is not gated (D4) |
| `stage_identity.py` | `STAGE_TEMPLATES` becomes the code kind's `templates` trait; `live_stage_config` takes the templates table and `LiveStageResolver` is constructed with it (D2) |
| `live_services.py`, `recall_services.py` | Build `config_for` and the resolver from the set's kind's templates. The `ConfigFor` type and `StageIdentityResolver.resolve` keep their two arguments |
| `run_plan.py` | Refuses a recipe with combs when the kind has no comb template |
| `stage_runner.py` | The comb argv reads `base` through `require_base` |
| `stage_ingest.py` | Marks a live review entry `gate_only` (D7) |
| `scoring.py`, `label_candidates.py` | A `scored` keyword for the scored severities (D5) |
| `recipes/decisions.py` | Line recognition extracted as `parse_id_lines`; `parse_decisions` keeps its signature and behaviour (D9) |
| `label_precedence.py` | Person over import over the chosen matcher's agent labels (D9) |
| `import_plan.py` | `ImportContext` gains `overrides_path` (D2) |
| `hand_run_import.py` | Calls the set's kind's `plan_import` |
| `hand_run_labels.py` | `_set_hit` and `_set_value` take the conflict policy (D8) |
| `case_intake.py` | Refuses a set that would hold more than one kind (D6) |
| `report_build.py`, `report_render.py` | Bug-hits by label source and by proof status, the matcher, the gate-only count |
| `cli/commands/benchmark_recall_stage.py` | `_stage` picks its call from a table keyed by template name; `--diff` becomes optional and the comb call requires it (D9) |
| `cli/commands/benchmark_recall*.py` | `match`; `--matcher` on `report` and `label` |

Not changed: `run_loop.py`, `run_bound.py`, `scoring_select.py`, `report_json.py`, and the callers of `parse_decisions` (`recipes/comb_call.py`, `hand_run_combs.py`, `stage_ingest.py`).

Existing tests that change, and no others:
- `StubKind` in `tests/benchmark/recall/test_kinds.py` and `test_run_end_to_end.py` gains `traits` and `plan_import`.
- `test_stage_identity.py`, `test_run_plan.py` and `tests/cli/test_benchmark_recall_run.py` pass the code templates table to `live_stage_config` and `LiveStageResolver`.

New data: `data/templates/flaw-match.yaml`.

### Data Flow

```
document case files (YAML, one folder per kind) ──cases add──▶ cases + one set per kind
20261116-mined/out + grade..grade5 ──import──▶ RecallRun reviews + import label records

recipe + set + runs
  └─run─▶ as 430, with the kind's sandbox and review command:
           document_sandbox(commit, exclude) ─▶ <sq> review <kind> <document> [--against <parent>]
           → leak scan ─▶ review StageEntry
  └─match─▶ match_plan: review entries with an unlabeled scored finding and no match entry → bound
           → match_loop, per entry, one at a time, no sandbox:
             <sq> benchmark recall _stage --template flaw-match (no tools, empty directory)
             → match StageEntry in RecallRun.matches, then agent RecallLabels for the case
  └─report─▶ 430's scoring with the kind's scored severities → table, bug-hit splits, matcher, gate-only count
```

### State Management

No new record types. Document cases are `recall_case` records, match calls are entries in `recall_run` records, and agent labels are `recall_labels` records, one per case and matcher. Matcher input and raw output go in the `REVIEWS` sidecar. A match call's key is deterministic, and a rerun skips review entries that already have a match entry from this matcher (D9).

## Technical Decisions

### D1 — A document case is the reviewed document, its commit and its verified flaws
Status: decided
- Case files live in `user/reference/document-recall-cases/<kind>/<name>.yaml`. The 43 are written once from `20261116-mined/cases.tsv`, `against.tsv` and `grade/<case>/flaws.json`; the four `design-review-recall-cases-*.md` files stay as the narrative record.
- **Flaw text is `flaws.json` text, unchanged.** That is the text the hand-run graders matched against, so the live matcher sees the same wording. It includes the curator's notes (`**VALID**`, "Raised by the original review (F004)", line numbers in sibling documents), and the matcher gets them as the graders did. They say nothing about the review being matched.
- Flaw ids (`F1`…) are the `flaws.json` ids, which the grading passes refer to.
- **`commit` is the full sha of the reviewed text.** The mined files give short shas and `<sha>^` forms; the case file holds the resolved 40 characters. `cases add` checks with `git cat-file -e` that `document`, `against` and every `exclude` path exist at that commit, and refuses the file otherwise.
- **No location derivation.** A document flaw has no fix-commit file list that a finding should cite, so `locations` is empty and the gate does not apply (D4).
- **`proof` may be empty, which needs an architecture amendment.** The architecture says "A bug counts only when a later commit or issue shows it was real", and its non-goals name a fix commit or issue as 432's ground truth. Many of the 82 flaws do not meet that: the migratory mining file says no later commit proves any of its 31, and each was verified by reading the reviewed text and the repo at that commit.
  - The slice plan entry (PM, amended 20261119) counts all 82 flaws in 43 cases and requires section 16 to be reproduced from them, so they stay.
  - `source` is required in every document case file: the mining file and section that records the evidence. Code case files have no `source`, and the 17 committed ones do not change. A correcting or response commit goes in `proof` where one exists; an empty `proof` means "verified at the reviewed commit, no later commit".
  - The report shows the difference: its header counts the set's flaws by proof status, and each row splits its bug-hits the same way (API Contracts), so a reader sees how much recall rests on flaws no later commit corrected.
  - **Proposed amendment** (a line under the architecture's amendments, for the PM): "A document flaw (432) counts when a later commit corrected it, or when its mining record shows it verified against the reviewed text and the repository at the reviewed commit. Each flaw records which."
- **The file spec is new.** `document_case.py` defines `DocumentCaseFileSpec` and `FlawSpec` (both `extra="forbid"`). They do not extend `CaseFileSpec` or `BugSpec`, whose rules (required `base` and `head`, non-empty proof, `extra_locations` for issue proofs) are the ones that do not apply. The shared parts are reused from `case_models.py`: the quoted-sha guard, the YAML read and the validation-error text. `build_document_case` maps `commit` to `RealBugCase.head` and leaves `base` as `None`.
- **Case id.** `RealBugCase` gains `document`, `against`, `exclude` and `source`, each `None` or empty for a code case, and `base` becomes `str | None`. The id payload gains `document`, `against` and `exclude` only when `document` is set, so the 17 stored code case ids do not change (tested).
- A model validator requires `base` for `code` and `document` for the document kinds.
- **Typing.** `require_base(case) -> str` in `recall_case_models.py` returns `base` or raises `ValueError`. The three places that need a base call it: `CodeKind.open_sandbox`, `CodeKind.review_argv` and the comb argv in `stage_runner.py`. `compute_recall_case_id` takes `base: str | None`.
- **Tests of the 43 committed files call no git.** The existence checks run through the injected `ProcessRunner`; the committed-case test answers them from a captured file, `tests/benchmark/recall/fixtures/document_paths.json`, as the code cases' test reads `proof_files.json`.
- Rejected: a separate payload type for document cases. Labels, runs, sets, scoring and the report all take `RealBugCase`; a second type would need a protocol over both for four optional fields.

```yaml
name: <case name>                # the hand-run id for the 43
kind: arch                       # arch | slice | tasks
repo: ~/source/repos/manta/<repo>
host_repo: <owner>/<repo>        # for the leak rules (430 D6)
distribution: <package name>     # for the leak rules
commit: <40-character sha>       # the commit holding the reviewed text
document: <path in the tree>
against: <path in the tree>      # slice and tasks only; refused for arch
exclude:                         # paths removed from the tree (D3); required, may be []
  - project-documents/user/reviews
status: checked
hand_run_id: <id used in 20261116-mined>   # import only
source: <mining file>#<section>
bugs:
  - id: F1
    description: "..."
    proof: []                    # correcting or response commits, when there are any
    original_review: missed      # missed | reported
```

### D2 — Three kinds, one implementation, and the kind carries its traits
Status: decided
- `DocumentRecallKind(review_command, traits)` is registered for `ARCH`, `SLICE` and `TASKS`. `review_argv` is `<sq> review <review_command> <document> [--against <against>] --model <alias> --no-save --output file --output-path <out> --cwd .`.
- `RecallKind` gains two members:
  - `traits: KindTraits`, a frozen dataclass in `kinds.py`:

    | Trait | code | arch, slice, tasks |
    |---|---|---|
    | `templates: Mapping[StageKind, str]` | `REVIEW: code`, `COMB: comb` | `REVIEW: arch`, `slice` or `tasks`; `MATCH: flaw-match` |
    | `scored_severities` | `SCORED_SEVERITIES` (`review/models.py`) | `DOCUMENT_SCORED_SEVERITIES` (`kinds.py`): that set plus NOTE (D5) |

  - `plan_import(results_dir, context, plan)`: the kind's hand-run layout (D7, D8). `CodeKind`'s is the existing reviews, combs, labels and overrides plan. `ImportContext` gains `overrides_path: Path | None`, which the import command fills as it does today, so the code plan still passes its pass labels into `plan_overrides` and loses nothing.
- **Templates come from the set's kind, once per command.** A set holds one kind (D6), so `run`, `match` and `report` read that kind's `templates` once. `live_stage_config(alias, stage_kind, templates)` gains the table as a third parameter, and `LiveStageResolver(templates)` is constructed with it. `LiveRunServices.config_for` is that function bound to the table. The `ConfigFor` type, `StageIdentityResolver.resolve(alias, stage_kind)` and the `scoring_select` helpers that call it (`entry_matches`, `matching_reviews`, `matching_chains`) keep their signatures. The code kind's table is today's `STAGE_TEMPLATES`. A live review entry of an arch case therefore carries the arch template's hash.
- `run` refuses a recipe with combs when the kind's `templates` has no `COMB` entry, and `match` refuses a set whose kind has no `MATCH` entry, both before any call (exit 1).
- 430's integration note said a kind could be added without touching `scoring.py` or `stage_runner`. That does not hold: the data needs kind-specific scored severities (D5) and templates. The changes are the trait lookups above; no module branches on the kind value.
- Rejected: one `document` kind with a `doc_type` field. Three registry entries need no second dispatch inside the kind.

### D3 — The sandbox is the reviewed tree with saved reviews removed and no history
Status: decided
- At the reviewed commit every one of the 43 trees holds saved review files (2 to 527 of them under `project-documents/user/reviews`), and for some cases the document's own review, which names the flaws. The hand-run `prepare.py` exported the tree, deleted that directory, and committed what was left as a new one-commit repo. The sandbox does the same, so live results are comparable with the imported ones.
- `document_sandbox` enters `HistoryFreeSandbox(start_sha=commit)` unchanged (lock, cleanup and orphan sweep come with it), then, through the injected `ProcessRunner`, each under `benchmark.recall_fetch_timeout_s`:
  1. removes `.git` and every `exclude` path;
  2. `git init`, `git add -A`, and one commit with a fixed author and date.
- Removing a path from the working tree alone is not enough: the fetched commit would still hold it, and a reviewer with a shell could `git show` it. Rebuilding the repository leaves no object that holds an excluded file.
- **This is a deliberate exception to 430 D7 and needs an architecture amendment.** 430's recall sandbox holds head and its ancestry back to base, because `sq review code --diff <base>` needs a merge base. `sq review arch|slice|tasks` take no diff, so they need no ancestry, and ancestry would keep earlier saved reviews reachable.
  - **Proposed amendment** (a line under the architecture's 20261115 amendment): "Document recall's sandbox (432) is one rebuilt commit: the reviewed tree without the case's excluded paths, and no ancestry."
- `exclude` paths are checked when the case is added (D1), so a stored case's paths exist at its commit.
- Three of the 43 commits are on no ref (squadron-403-design, context-forge-260-arch, context-forge-268-tasks). A local fetch by sha still works for them (checked 20261121), but `git gc` can remove them. `cases add` and `cases list` print `commit=unreferenced` for such a case. See Risk Assessment.
- Submodules stay unfilled, as in the hand-run export and in `HistoryFreeSandbox`.

### D4 — A bug with no locations is not gated
Status: decided
- `hit_rule.gate` returns `CANDIDATE` when the bug has no locations. Today a finding that cites any path would be a decided miss for such a bug, which would decide every document hit away.
- Code cases always have locations: commit proofs give files and issue proofs require `extra_locations`. `CodeKind.validate` now refuses a bug whose resolved locations are empty, so the rule can only apply to kinds that mean it.
- Document hits are therefore decided by labels alone: imported (D8), agent (D9) or person.

### D5 — Document kinds score NOTE findings
Status: decided
- The hand-run graders were given every finding except PASS, and 161 of the 1,074 flaw hits rest only on NOTE findings. Scoring CONCERN and FAIL alone would not reproduce section 16 and would undercount recall.
- The functions in `scoring.py` and `label_candidates.py` that filter on `SCORED_SEVERITIES` gain a keyword, `scored: frozenset[str] = SCORED_SEVERITIES`. `report_build`, `label` and `match` pass the set's kind's trait. Existing callers, including `stage_runner.comb_input_findings` (combs are code-only), and existing tests are untouched, and code rows are unchanged. The default is the one existing constant, not a new value; the section 16 reproduction test fails if a document caller leaves the keyword out.
- Each set is defined once. The code trait is the existing `SCORED_SEVERITIES`. `DOCUMENT_SCORED_SEVERITIES` is defined in `kinds.py` as that set plus NOTE: it is a benchmark value and stays out of the production `review/models.py`.
- `real_work.py` and `recipes/kept_findings.py` keep importing `SCORED_SEVERITIES`. They score and merge production recipe reviews (434), which have no recall case and so no kind.
- "Findings/run" for a document row counts CONCERN, FAIL and NOTE, and the report header says so.

### D6 — One kind per case set
Status: decided
- `cases add` refuses a call whose files, together with the named set's current version, would hold more than one kind (exit 1, naming the kinds). `run`, `match`, `report`, `label` and `import` read the kind from the set's cases and refuse a stored set with more than one.
- A stage identity includes the template hash, and the scored severities differ by kind, so a mixed set has no single row per recipe. One set per kind gives the per-kind table directly: three reports.
- Sets: `doc-flaws-arch`, `doc-flaws-slice`, `doc-flaws-tasks`. Version 1 of each is its share of the 43 cases. New arch cases (D11) make `doc-flaws-arch` version 2; `--set doc-flaws-arch@1` keeps reproducing section 16.
- Rejected: grouping one report by kind. It adds a dimension to scoring for a table that three invocations already give.

### D7 — Import of the mined review outputs
Status: decided
- `import <results-dir> --set doc-flaws-<kind>` reads `20261116-mined/out/*.json`. A file belongs to the set's case whose `hand_run_id` is the longest prefix of its name followed by `-`; the rest must be `<config>-<run>.json`. Case ids contain hyphens, so 430's split at the first hyphen does not apply.
- A file that matches no case of the set is counted in one summary line ("files for other sets' cases"), not listed as skipped: the same folder serves all three sets. A test asserts that the three imports together hold all 1,281 files.
- Config fields follow 430 D10's review table without change (alias from the file name, `unknown:<template_name>@<squadron_version>` template marker, `tool_use` from `tools_given`, `effort_sent` null). Every entry has `leak: not_scanned` and `source: import:20261116-mined`.
- **Task-gate outputs.** 70 files (squadron-197-tasks and squadron-917-tasks, every config and run) are the task gate's rule-based FAIL: no model was called. Their fields are `model: squadron-task-gate` (`TASK_GATE_MODEL`), `template_name: tasks`, and null `profile`, `tools_given`, `effort` and `max_output_tokens`.
  - Such a file imports with `gate_only: true`. Its `model`, `profile`, `tools_given`, `effort` and `max_output_tokens` are not read: the entry takes the config and configured effort shared by the same alias's model-call outputs in the same set. The gate's result does not depend on the model, and the alias is what the run was given. If that alias's model-call outputs do not all share one config, the file is skipped and listed.
  - Without this the two cases would form a separate row per alias and drop out of the tasks row, and the row would no longer be "of 31".
  - A live review entry is marked `gate_only` by the same test on its output's `model`.
  - The report footer prints the number of gate-only entries used, with "no model call".
- Expected counts: 259 review entries for arch, 515 for slice, 507 for tasks; 27, 51 and 51 run records.

### D8 — Import of the grading passes: the first pass to grade a review wins
Status: decided
- Passes, in order: `grade`, `grade2`, `grade3`, `grade4`, `grade5`. Labeler `import:mined/<pass>`, one label record per case and pass.
- Each pass has `map.json` (`<case>/<rNN>` to alias and run) and, per case, `flaws.json` and `hits.json`. For a mapped review, every finding the grader was shown (severity not PASS) gets a label for every flaw of the case: `HIT` when `hits.json` lists its index `i` under that flaw and review, `MISS` otherwise. `i` is the finding's index in the output's `findings` list.
- **An absent key is read as a graded miss. This is an inference, recorded as one.** The brief asked for every review under every flaw, but the graders left out reviews with no hit (671 flaw-and-review pairs).
  - Evidence: `grade/squadron-320-arch/hits.json` has an empty `hits` for F1, and its `note` says reviews r02, r03 and r05 were read against F1 and judged no hit. The hand-run `score_all.py` reads absence the same way, and section 16 was published from it.
  - Each pass label record's `notes` gives how many of its MISS labels come from absent keys, and the summary prints the total.
  - **Why "absent is not zero" does not apply.** That principle is about a run with no grade. These reviews were graded: the pass's `map.json` lists the review and the case has a `hits.json`. The absent key is how the grader wrote "no hit". A review that was not graded (not in `map.json`, or its case has no `hits.json`) gets no labels and stays undecided, which is the principle at work.
  - The consequence is accepted: these pairs are decided misses, so imported rows print one recall figure, as section 16 did, not a range.
- **Regrades.** 172 reviews were graded again in later passes as anchors. A review takes its labels from the first pass that graded it; later gradings of it are not stored. The summary prints how many flaw decisions the regrades compared and how many disagreed (measured on the committed files: 11 of 574). Section 16 was computed from `grade` and `grade2`, so this order reproduces it.
- Refusals, each skipped and listed (exit 1 at the end, as in 430):
  - a pass's `flaws.json` whose flaw ids differ from the case's bug ids;
  - a `map.json` entry with no imported review, or a hit index with no finding;
  - a review whose grader file (`<pass>/<case>/<rNN>.json`) gives, for any `i`, a title different from the title of the output's finding at index `i`: the grader's indices would not be the output's;
  - a mapped case with no `hits.json`.
- Two findings of one case with the same content key and different labels: the earlier pass wins, and the conflict is counted and listed.
- **This reverses 430's rule on purpose.** 430's code import keeps the later pass (`hand_run_labels.py`), because its later passes were corrections. Here the later passes are anchor regrades and section 16 was published from the first. The merge is not written twice: `_set_hit` and `_set_value` in `hand_run_labels.py` take a `ConflictPolicy` (`LATER` for the code passes, `EARLIER` here and for matcher labels, D9) and record the same `LabelConflict`. A test covers each policy.

### D9 — `match`: an agent matches findings to flaws, blind, for document kinds
Status: decided
- **Why a model.** The location gate cannot narrow document findings, so every finding is a candidate for every flaw: about 14 findings by 2 flaws per haiku-xhigh review. The plan entry names agent grading as this slice's matching method, and the hand-run numbers this command must be comparable with came from grading agents.
- **Unit.** One call per stored review entry of the recipes given, when both hold:
  - the entry has a scored finding that, for some flaw of its case, has no label of any verdict (HIT, ADJACENT or MISS) from a person, an import or this matcher. An imported entry has a HIT or MISS for every finding and flaw, so it is never matched;
  - the run record holds no match entry for this review entry and this matcher.

  A stored `ok` match entry is a result: a partial output is not called again, and its uncovered findings stay undecided for `label`. A failed matcher call is stored as `harness_failure`, never `config_failure`: the matcher is the judge, and its failure says nothing about the reviewed config. `--retry-harness` repeats failed calls and moves the old entry to `superseded`, as in 430 D8.
- **Gate-only review entries are matched like any other.** The gate's findings are scored findings, and a flaw list can include what the gate reports. "No model call" in the footer is about the review, not the match. The gate's findings are the same text for every config, so after the first call their labels exist and no further entry of that case needs one.
- **Input.** The case's flaws (id and text) and that review's scored findings (id, severity, title, description, location). It holds no alias, model, recipe or run index, so the matcher cannot know who wrote the review.
- **Two id namespaces.** Flaws keep their `F1`…`Fk` ids. Findings are rendered as `R1`…`Rn` in the matcher input, not with the comb's positional `F` ids, so a line can never name a finding where a flaw is meant. The prompt states both prefixes. A fixture has `n` and `k` overlapping.
- **A separate loop.** `match_loop.py` runs the calls. It does not go through `run_loop`, `stage_runner` or `stage_ingest`, which open the case sandbox before every stage, store every non-review entry among the combs, and parse every non-review output as comb decisions. A matcher needs no tree, so a missing repo or a collected commit cannot fail a match. The loop reuses the recall lock, the auth preflight, `ScrubbedEnvironment`, `resolve_sq_path()`, `LeakChecker` and `ReviewBudget`, and writes `RecallRun.matches` itself.
- **Call.** A scrubbed subprocess through the existing hidden command: `<sq> benchmark recall _stage --template flaw-match --input <file> --output <file> --model <alias>`, run in an empty directory under `benchmark.review_timeout_s` (`match` refuses without it, as `run` does). It is leak-scanned or marked `confined` as a 430 stage call is.
  - `_stage` picks its call from a table keyed by the template-name constants (`COMB_TEMPLATE_NAME`, `MATCH_TEMPLATE_NAME`), so there is one selector. `--diff` becomes optional: the comb call requires it and reads the changed files as today; the match call refuses it. Existing `_stage` invocations and `test_stage_command.py` are unchanged.
  - The match call invokes `run_review_with_profile` directly with an empty `allowed_tools` list. It does not go through `call_comb`, which always passes the read tools.
- **Prompt rule** (the hand-run brief's): a finding matches a flaw when it names the same underlying defect, in other words or at another location; a finding about the same area that raises a different problem does not.
- **Output.** One line per finding: the finding id, a separator, then the flaw ids it matches or the none word, then optionally a dash and a reason.
  - **Shared line recognition.** `recipes/decisions.py` gains `parse_id_lines(raw, ids) -> IdLineParse`: for each line that starts with a known or unknown id (after markdown and list markers), the id and the rest of the line, with the unknown-id and duplicate counts, first line per id winning. `parse_decisions(raw, finding_ids)` keeps its signature and result and is rebuilt on it with the comb's word table. Its three callers do not change, so the production comb path (434) behaves as before; `tests/benchmark/recall/test_decisions.py`, `tests/recipes/test_recipe_review.py`, `tests/recipes/test_recipe_runner.py` and `tests/pipeline/actions/test_review_recipe.py` pass unchanged and are the proof.
  - **Matcher grammar.** `parse_matches(raw, finding_ids, flaw_ids) -> MatchParse` in `match_stage.py` reads each line's rest. The verdict part runs to the first dash (hyphen, en dash or em dash) with a space on each side, or to the end of the line. It is either the none word (one constant, any case) or flaw ids separated by commas, spaces or both. What follows the dash is the reason.
  - `MatchParse` holds `matches: dict[finding id, frozenset[flaw id]]` (empty set for none), and the counts `unknown_flaw_lines`, `unknown_ids` and `duplicates`. A verdict part with any token that is neither the none word nor one of the case's flaw ids discards the line and adds one to `unknown_flaw_lines`. No `CombDecision` or `CombVerdict` is involved.
  - Fixtures are real matcher outputs from two providers, captured in walkthrough step 4 and stored in `tests/benchmark/recall/fixtures/match/`, apart from `fixtures/decisions/`, whose test reads every file as a comb output.
- **Labels.** For each finding with a parsed line: `HIT` for the flaws named, `MISS` for the case's other flaws. Written to the case's `RecallLabels`, kind `AGENT`.
  - A finding with no line gets no label and stays undecided, so recall prints as a range (430 D3).
  - A line naming a flaw id the case does not have is discarded whole, counted, and logged at WARNING; that finding stays undecided.
  - **Same finding text in two reviews.** Labels are keyed by content key, so two reviews of one case that share a finding share its label. Within one matcher's record the first verdict written stays; a later call that disagrees does not overwrite it, and the conflict is counted, logged at WARNING and printed in the `match` summary (`ConflictPolicy.EARLIER`, D8).
- **Matcher identity.** The labeler is `agent:<12 hex>` of sha256 of the matcher's `config_key` and the effort it sent, the stage identity 430 D4 uses. The alias is display only and goes in the record's `notes`. Two aliases that resolve to one config are one matcher.
- **Several matchers can coexist; a report uses one.** Each matcher has its own label record per case and its own match entries, so running a second matcher changes nothing the first wrote, and nothing ever has to be deleted to change matcher.
  - `report` and `label` take `--matcher ALIAS`. With it, only that matcher's agent labels are in force.
  - Without it, a set whose cases hold agent labels from one matcher uses that one, and a set with labels from more than one is refused (exit 1) with the matchers listed.
  - A row's agent labels therefore always come from one matcher, and the report header prints its id and alias. Running the wrong matcher is undone by running the right one and naming it.
- **Precedence.** Person over import over the chosen matcher's agent labels. Imported labels stay in force when an agent grades the same finding.
- **Record.** `RecallRun.matches["<review entry_key>|<matcher entry_key>"]`, a `StageEntry` of kind `MATCH` with config, usage, outcome, leak verdict, `raw_ref`, and `input_ref` (sha256 of the input file, stored in the sidecar), so each call records what it was given.
- **Write order and resume.** The match entry is written first, then the labels. Labels are derived only from the entry's stored input and raw output, so they can be rebuilt. On a rerun:

  | State found | Action |
  |---|---|
  | The call ran but no match entry was stored | The call is made again; a leftover output file is logged at WARNING as cost spent without a record |
  | An `ok` match entry whose findings have no labels under this matcher | Labels rebuilt from `input_ref` and `raw_ref`; no call |
  | Entry and labels both present | Skipped |

- **Matcher model.** `--model` is required and has no default. The hand-run graders were Sonnet agents.
- **Checking the matcher.** `match --recheck` matches the recipes' entries whether or not they have labels, and compares the matcher's flaw decisions with the labels in force. It writes no labels and no match entry, so no score can change. It prints the number of flaw decisions compared, how many differ, and the cost. A recheck is not resumed; an interrupted one is run again.
  - The number is informational. This design sets no threshold on it. The hand-run regrade figure (11 of 574) is grader against regrader on 172 reviews, a different comparison, and is printed nowhere as a yardstick.
- **Bound and caps.** `--max-cost` and `--call-cost` are both required: the bound is the number of pending calls times `--call-cost`, plus one call of overshoot, printed before the first call in `render_bound`'s wording. Observed costs are not used, so `run_bound` is not touched. `--max-plan-calls` is required when the matcher is plan-billed. Calls are serial, and the command exits 2 at a cap.
- **Report.** Recall is not one blended figure. Each row prints its bug-hits split by the labeler kind of the deciding HIT label (import, agent, person), so the share of recall that rests on the matcher is read directly from the row.
- Rejected: one call per case covering every review, as the hand-run did. A per-review call is the natural resume unit, needs no shuffling to be blind, and keeps the input small.
- Rejected: `label` by a person as the only route. It works unchanged for document sets, and a person's label overrides the agent's, but it is the load this slice exists to remove.

### D10 — Failure modes and how each is observed
Status: decided
Each mode is logged at the level shown with case, run and stage, written to the entry or the command summary, and covered by a test asserting both. For `run` on a document set, modes not listed (auth preflight, timeouts, lock, store writes, orphan output files) are 430 D8's, unchanged. The match loop is separate (D9), so its modes are all in the table; its auth preflight, lock and store-write failures refuse or stop the command as 430 D8's do.

| Mode | Level | Outcome |
|---|---|---|
| `cases add`: `document`, `against` or an `exclude` path missing at `commit`; `against` on an arch case or absent on a slice or tasks case; the set would hold two kinds | ERROR | Whole command refused, exit 1, nothing written |
| `cases add`: a `git cat-file -e` check cannot run (repo path missing, git fails) or exceeds `benchmark.recall_fetch_timeout_s` | ERROR | Refused as above, naming the case and the command |
| `cases add`, `cases list`: the check for refs containing the commit fails or times out | WARNING | The case is shown as `commit=unknown`; nothing else changes |
| Sandbox: the rebuild commands fail or exceed `benchmark.recall_fetch_timeout_s` | WARNING | `harness_failure` + reason; (case, run) dropped from every recipe and counted |
| Sandbox: the commit can no longer be fetched (collected) | WARNING | `harness_failure` naming the commit |
| Review output is a task-gate result | INFO | `ok`, `gate_only: true`; counted in the report footer |
| Matcher call exceeds `benchmark.review_timeout_s`, its output has no parseable line, or the subprocess exits without an output file | WARNING | Match entry `harness_failure` + reason; no labels written; the findings stay undecided; repeated by `match --retry-harness` |
| Matcher output covers some findings only | WARNING | `ok`; the rest stay undecided; count printed; not called again |
| Matcher line names an unknown flaw id | WARNING | That line discarded and counted (`unknown_flaw_lines`) |
| Matcher line names a finding id that was not in the input | WARNING | That line discarded and counted (`unknown_ids`) |
| Matcher gives two lines for one finding | WARNING | The first line wins; the repeat is counted (`duplicates`) |
| Matcher verdict differs from the one this matcher already stored for the same content key | WARNING | The stored verdict stays; conflict counted and printed |
| Match leak scan `leaked` or `scan_unavailable` | WARNING | Match entry stored with that verdict; no labels written; repeated by `--retry-harness` |
| A rerun finds a match output file with no entry | WARNING | The call is made again; the log says the earlier cost has no record |
| `report` or `label` without `--matcher` on a set with agent labels from more than one matcher | ERROR | Refused, exit 1, listing the matchers |
| `run` with combs, or `match`, on a kind that has none | ERROR | Refused, exit 1, before the lock |
| Import: file name matches no case of the set | — | Counted in one summary line |
| Import: the D8 refusals, or a gate file whose alias has no single config | WARNING | Skipped and listed; exit 1 at the end |

### D11 — More architecture cases are mined by hand and added as files (#373)
Status: decided
- Method: the validity rule and evidence labels of `design-review-recall-cases-migratory.md`, applied to architecture documents with a saved review in context-forge, migratory and trading-engine. Read-only: `git show`, `git diff`, `git log`, `git grep` at the reviewed commit. No model review is run and nothing is checked out.
- Each accepted case is a YAML file in `document-recall-cases/arch/` and a section in a new `user/reference/design-review-recall-cases-arch.md`, which also lists every candidate examined and why the rejected ones were rejected.
- **Bounded by candidate count.** At most 15 candidates per repo, the limit each earlier mining pass used, so at most 45 in all. Target: at least 40 arch flaws in `doc-flaws-arch` version 2 (19 exist). Mining stops at the target or at the candidate limit, whichever comes first. If it stops short, the count and the reason go in that file and in a comment on #373; the slice is not blocked on the number.
- **Squadron's own history is not mined.** #373 lists squadron among the sources, but the architecture's 20261115 amendment says no task runs against squadron's own history, and 430 D13's exception covered only the file lists of four commits. Mining squadron's arch documents needs a recorded PM decision; the #373 comment says they were left out and why.
- Recipe files added to `review-recall-recipes/`: `opus-high`, `fable-medium`, `hy4`, `mimo`, `fable-haiku` (fan-out of fable-medium and haiku-xhigh, the union #373 asks for), and `luna-r` (a cheap priced reviewer for the fixture run). `haiku-xhigh` exists.

### Technology Choices
- No new dependencies. PyYAML and Pydantic as in 430.
- No load-test tier: calls are serial and PM-run, as in 430.

### Patterns and Conventions
- The none word, the gate-only test and the agent labeler prefix are each one constant. `LabelerKind.AGENT` gets its prefix in `LABELER_PREFIX`.
- No module compares a kind value. Kind-specific behavior is a trait or a `RecallKind` method.

## Implementation Details

### API Contracts

New and changed `sq benchmark recall` commands. Exit codes as 430: 0 complete, 1 refused or error, 2 cap reached.

| Command | Purpose | Key options |
|---|---|---|
| `match` | Match findings to flaws for the review entries of the recipes given | `--set NAME[@VERSION]`, `--recipe` (repeatable), `--runs N`, `--model ALIAS` (required), `--max-cost` (required), `--call-cost` (required), `--max-plan-calls`, `--recheck`, `--retry-harness`, `--case NAME` |
| `_stage` (hidden) | One comb or matcher call, chosen by `--template`; launched by `run` and `match` | `--diff` optional, required by the comb call |
| `cases add`, `cases list` | Unchanged options; document kinds accepted; `commit=unreferenced` shown | |
| `import` | Unchanged options; the set's kind chooses the layout | |
| `run` | Unchanged options; refuses combs for a document set | |
| `report`, `label` | Add `--matcher ALIAS` (D9); `report` prints two more columns and the header and footer items below | |

`report` for a document set:

```
Case set doc-flaws-arch v1 (arch): 9 cases, 19 known flaws (<n> corrected by a later commit, <m> verified only), runs 1..3
Hit rule: labels only (no location gate); scored severities CONCERN, FAIL, NOTE.
Matched nothing includes valid findings outside the known flaws.
Matcher: none (no agent labels).

| Recipe | Cases | Runs | Bug-hits | By label (import/agent/person) | By proof (corrected/verified only) | Recall | Bugs found | ... | Real share | Cost/run (basis) | Leak scan |
| fable-medium | 9 | 3 | 38/57 | 38/0/0 | <a>/<b> | 67% | 16/19 | ... | ungraded | ... | 27 not scanned |
...
Gate-only entries (no model call): 0.
```

`report --json` is unchanged for now. Its schema is pinned by `tests/benchmark/recall/test_report_json_schema.py` for slice 433, which was dropped on 20261119, and `SUMMARY.md` and `ANSWERS.yaml` are updated by hand from the text report. Adding the new fields to the JSON document is deferred to [#386](https://github.com/ecorkran/squadron/issues/386).

### Database / Storage Schema

No new record type and no migration; `schema_version` stays 1. Every added field is optional with a default, so stored 430 records read unchanged:
- `RealBugCase`: `document`, `against`, `exclude`, `source`; `base` optional.
- `RecallRun`: `matches: dict[str, StageEntry] = {}`.
- `StageEntry`: `gate_only: bool = False`, `input_ref: str | None = None`.
- `RecallLabels`: no change; a new `labeler_kind` value.

**Record size.** The architecture keeps findings inline because they are short, and the store reads every file on every query. Document findings are longer, so this was measured on the committed files (20261121):

| | Run records | Finding text, total | Largest record | Median |
|---|---|---|---|---|
| Code records in the store today | 54 | 7.2 MB (whole files) | 309 KB | — |
| Document import (finding text only) | 129 | 10.9 MB | 377 KB | 47 KB |

- Findings stay inline, as 430 D4 stores them: scoring, labels and the matcher all read the full text, and the largest document record is the same order as the largest code record.
- Target: no run record above 1 MB. The import summary prints the largest and total run-record size, and a test on the committed files asserts the target. A record over it fails the import with that reason; moving finding text to the sidecar would then be a design change, not a silent one.

## Integration Points

### Provides to Other Slices
- **435, 436:** recipes with repeats, votes, focuses and sequential stages can be run on the document sets once those slices exist; nothing here is specific to single reviewers except the comb refusal.
- **Model answers** (`review-recall-results/SUMMARY.md`, `ANSWERS.yaml`): per-kind document rows, copied by hand from the text report.
- **#340:** the match loop (one no-tools call per review entry, agent labeler, precedence) is the shape live grading needs.

### Consumes from Other Slices
- **430:** everything listed under Dependencies. Stored records, code case ids, code report rows and the `report --json` schema are unchanged, and 430's reproduction tests keep passing. The code changes that are not purely additive:
  - `RecallKind` gains two required members, `traits` and `plan_import`.
  - `live_stage_config` gains a required `templates` parameter, and `LiveStageResolver` a required constructor argument.
  - `RealBugCase.base` becomes optional, read through `require_base`.
  - `resolve_labels` gains a third precedence tier and the matcher choice.
  - `_set_hit` and `_set_value` in `hand_run_labels.py` gain a required conflict policy.
  - `_stage`'s `--diff` becomes optional.
  - `ImportContext` gains `overrides_path`.
  - Unchanged in signature and behaviour: `parse_decisions`, `ConfigFor`, `StageIdentityResolver.resolve`, the scoring functions (new keyword with the existing constant as default), and `split_output_name` (the document importer has its own name matching, D7).
  - **This reverses 430 D14**, which said 432 would add a kind without changing `scoring`, the recipe model or `stage_runner`. The seam now also carries traits, so a later kind supplies its traits and import plan and still changes no caller.
- **434 (production recipe reviews):** shares `recipes/decisions.py`. `parse_decisions` is behaviour-neutral (D9), so the architecture's 20261118 rule that production behaviour changes only on the review path holds: this slice changes none.
- `sq review arch|slice|tasks`: a change in their output shape shows as `config_failure` entries (no parseable result), which are counted.

## Success Criteria

### Functional Requirements
- The 43 cases exist as case files under `document-recall-cases/{arch,slice,tasks}/` and load as sets `doc-flaws-arch` (9 cases, 19 flaws), `doc-flaws-slice` (17, 32) and `doc-flaws-tasks` (17, 31). A file with a missing document, a wrong `against`, or a second kind for its set refuses the whole command.
- The 17 stored code case ids are unchanged, and 430's report reproduction tests pass unmodified.
- `import` over the three sets loads all 1,281 review outputs and the five grading passes with no new calls, prints the absent-key and regrade counts, and changes nothing on a second run.
- On the imported records, `report --runs 3` reproduces RESULTS.md section 16 (bug-hits, then flaws found in any run):

  | Recipe | arch (57; 19) | slice (96; 32) | tasks (93; 31) |
  |---|---|---|---|
  | fable-medium | 38; 16 | 42; 16 | 59; 23 |
  | haiku-xhigh | 29; 14 | 48; 21 | 54; 23 |
  | opus-high | 35; 14 | 41; 19 | 52; 20 |

  (Computed from the committed grade files while writing this design; they give section 16's 12.7, 14.0, 19.7 and so on per run.)
- The `fable-haiku` fan-out recipe is scored on each set from stored entries with no new calls.
- `run` on a document set reviews with the kind's production command and refuses a recipe with combs. A test builds the document sandbox and asserts that it has one commit and that no excluded path is in its tree or in any git object.
- `match`:
  - refuses a code set and a missing `--model`, `--max-cost`, `--call-cost` or `benchmark.review_timeout_s`;
  - opens no sandbox, so it runs when a case's repo is missing;
  - prints its bound before the first call, stops at a cap with exit 2, and resumes;
  - sends no alias, model or run index to the matcher, offers it no tools, and renders findings as `R` ids and flaws as `F` ids;
  - writes the match entry to `RecallRun.matches` before the labels, and a rerun rebuilds missing labels from a stored entry with no call;
  - writes agent labels that turn an undecided row into a decided one, and leaves imported and person labels in force;
  - stores a failed call as `harness_failure` and repeats it with `--retry-harness`;
  - keeps the first verdict when two reviews share a finding text, and counts the conflict;
  - with `--recheck`, prints its comparison with the labels in force and writes no label and no match entry.
- A partial matcher output leaves the uncovered findings undecided, recall prints as a range, and a second `match` makes no call for that entry.
- Two matchers' labels coexist: `report --matcher` scores with the one named, and `report` without it on a set holding both is refused.
- The text report prints bug-hits by label source and by proof status per row, the flaw counts by proof status and the matcher in its header, and the gate-only entry count. The imported tasks rows count squadron-197-tasks and squadron-917-tasks as gate-only.
- `doc-flaws-arch` version 2 holds the new arch cases, with the narrative file listing every candidate examined. The flaw count, the reason if it is below 40, and the fact that squadron was not mined are posted on #373.
- Recipe files `opus-high`, `fable-medium`, `hy4`, `mimo`, `fable-haiku` and `luna-r` are committed.

### Technical Requirements
- `ruff format`, `ruff check` and `pyright` (zero errors) pass, and `tests/benchmark/recall/` passes.
- Tests run no model and no git outside fixtures.
- The import is tested against the committed `20261116-mined/` files.
- `parse_matches` fixtures are real captured outputs from two providers, in `tests/benchmark/recall/fixtures/match/`.
- The production comb path is unchanged: `test_decisions.py`, `tests/recipes/test_recipe_review.py`, `tests/recipes/test_recipe_runner.py`, `tests/pipeline/actions/test_review_recipe.py`, `test_stage_command.py` and `test_report_json_schema.py` pass with no edit. The only existing tests edited are the five named under Component Structure.
- The committed document cases are tested with captured existence answers, not git.
- No imported run record exceeds 1 MB (tested on the committed files).
- Each `ConflictPolicy` has a test.
- Every D10 mode has a test asserting its outcome and its log record.
- `HistoryFreeSandbox`, `sq review`, `run_loop.py`, `run_bound.py` and `comb_call.py` are unchanged (no diff in their files).
- The runbook gains a "Document reviews" section naming the case folders, sets, `match` and the hand-run folders it replaces.

### Integration Requirements
- A stub kind with its own traits runs a review stage through `run_loop` and a match call through `match_loop` in a test.

### Verification Walkthrough

Run from the squadron checkout as `uv run sq ...` until a release carries the commands. `C=project-documents/user/reference/document-recall-cases`, `P=project-documents/user/reference/review-recall-recipes`. Steps 1-4 are checked during implementation; steps 5 and 6 are the PM's.

1. **Load the cases.**
   ```bash
   for kind in arch slice tasks; do
     uv run sq benchmark recall cases add $C/$kind/ --set doc-flaws-$kind
     uv run sq benchmark recall cases list --set doc-flaws-$kind
   done
   ```
   Expect 9, 17 and 17 cases at v1, and `commit=unreferenced` on context-forge-260-arch in the arch list, squadron-403-design in the slice list and context-forge-268-tasks in the tasks list.

2. **Import the hand-run results.**
   ```bash
   for kind in arch slice tasks; do
     uv run sq benchmark recall import project-documents/user/reference/review-recall-results/ --set doc-flaws-$kind
   done
   ```
   Expect review entries 259, 515 and 507, the regrade line, and `No changes.` on a second run.

3. **Reproduce section 16.**
   ```bash
   for kind in arch slice tasks; do
     uv run sq benchmark recall report --set doc-flaws-$kind@1 --runs 3 \
       --recipe fable-medium --recipe haiku-xhigh --recipe opus-high --recipe fable-haiku
   done
   ```
   Expect the bug-hit and bugs-found numbers in the Functional Requirements table, every row `not scanned`, bug-hits by label all under import, and a gate-only count on the tasks report.

4. **Run, match and report on the fixture.**
   ```bash
   uv run python tests/benchmark/recall/fixtures/doc_repo/build.py
   uv run sq benchmark recall cases add tests/benchmark/recall/fixtures/doc_repo/cases/slice/ --set fixture-slice
   uv run sq benchmark recall run --set fixture-slice --recipe luna-r --runs 1 --max-cost 0.10 --call-cost 0.02
   uv run sq benchmark recall report --set fixture-slice --recipe luna-r      # recall as a range
   uv run sq benchmark recall match --set fixture-slice --recipe luna-r --model <matcher alias> --max-cost 0.10 --call-cost 0.02
   uv run sq benchmark recall report --set fixture-slice --recipe luna-r      # decided, bug-hits by label shows the agent
   uv run sq benchmark recall match --set fixture-slice --recipe luna-r --model <alias on another provider> --max-cost 0.10 --call-cost 0.02
   uv run sq benchmark recall report --set fixture-slice --recipe luna-r      # refused: two matchers, names both
   uv run sq benchmark recall report --set fixture-slice --recipe luna-r --matcher <matcher alias>
   ```
   The fixture repo holds a slice design with one planted contradiction, its parent, and a saved review naming it under the excluded path. `build.py` creates the repo and writes `cases/slice/<case>.yaml` with the commit it just made, as `bug_repo/build.py` writes its `case.yaml`; the case file is a build output and is git-ignored. A repeat of either `match` prints `0 calls to make`. The sandbox is removed when `run` exits, so its shape is checked by the sandbox test, not here.

   Each `match` stores its raw matcher output in the `REVIEWS` sidecar under its match entry's `raw_ref`. Copy the two into `tests/benchmark/recall/fixtures/match/` as the two-provider parser fixtures.

5. **Check the matcher against the hand-run graders (PM).**
   ```bash
   uv run sq benchmark recall match --set doc-flaws-arch@1 --recipe haiku-xhigh --runs 1 \
     --model <matcher alias> --recheck --max-cost <USD> --call-cost <USD per call>
   ```
   9 calls. It prints how many flaw decisions differ from the imported labels. The number is informational; the design sets no pass mark.

6. **Arch comparison for #373 (PM).**
   ```bash
   uv run sq benchmark recall run --set doc-flaws-arch --runs 3 --max-cost <USD> --call-cost <USD per call> \
     --recipe fable-medium --recipe opus-high --recipe haiku-xhigh --recipe hy4 --recipe mimo
   uv run sq benchmark recall match --set doc-flaws-arch --runs 3 --model <matcher alias> --max-cost <USD> --call-cost <USD per call> \
     --recipe fable-medium --recipe opus-high --recipe haiku-xhigh --recipe hy4 --recipe mimo
   uv run sq benchmark recall report --set doc-flaws-arch --runs 3 \
     --recipe fable-medium --recipe opus-high --recipe haiku-xhigh --recipe hy4 --recipe mimo --recipe fable-haiku
   ```
   Live entries have their own stage identity, so every review runs live: 15 review calls per arch case, one after another (#372). The report is appended to RESULTS.md as a new section and #373 is updated.

## Risk Assessment

### Technical Risks
- **The matcher is a model.** Its hits are less certain than fix-commit ground truth with a person's label, and a loose or strict matcher moves every row.
- **Unreferenced commits.** Three cases depend on commits that `git gc` can remove from the source repos.
- **Mining yield.** There may be fewer than 21 new valid arch flaws in the three repos mined.
- **Flaws with no later commit.** Part of the ground truth, and possibly all of a new arch case, rests on the miner's verification, not on a correcting commit. A wrongly accepted flaw lowers every config's recall alike.

### Mitigation Strategies
- The report counts flaws and splits bug-hits by proof status, so recall on corrected flaws alone can be read from any row. The amendment that admits verified-only flaws is the PM's (D1).
- `--recheck` compares the matcher with the imported labels (step 5), the report splits every row's bug-hits by label source, and a person's label always wins.
- `cases list` flags unreferenced commits, and a collected commit is a counted harness failure, never a wrong score. Pinning them with a ref in the source repos is the PM's call; this slice writes nothing to those repos.
- D11's stop rule records the yield and its reason instead of blocking.

## Implementation Notes

### Development Approach
1. Case model fields and kinds, `document_case.py`, `KindTraits` on both kinds, the one-kind-per-set rule, the ungated-bug rule. The 43 case files and three sets. Test that code case ids are unchanged.
2. The `scored` keyword; templates from traits. 430's tests pass, with the five edits named under Component Structure.
3. `hand_run_documents.py` and `hand_run_document_labels.py` with the conflict policy, tested on the committed files, the record-size test, then the section 16 reproduction test. This is the first result for the PM.
4. `document_sandbox.py`, `DocumentRecallKind.review_argv`, the comb refusal, the fixture doc repo, and `run` end to end on it with a scripted model command.
5. `parse_id_lines` under an unchanged `parse_decisions`; `flaw-match` template; `_stage`'s template table; `parse_matches`, `match_plan.py`, `match_loop.py`, `match_stage.py`; `match` with bound, caps, resume, `--retry-harness` and `--recheck`; label precedence and `--matcher`; the report's bug-hit splits, matcher and gate-only count.
6. Arch mining (D11), the new case files, set version 2, recipe files, the #373 comment, and the runbook section.

Testing: unit tests per module; scoring tests add a document set with NOTE-only hits, a gate-only entry, agent labels under an import label, and a partial matcher output.

### Special Considerations
- No task runs a review against squadron's own history. Steps 1-3 read commit metadata and committed files only, step 4 uses the fixture repo, and the live document runs (19 of the 43 cases are squadron's) are the PM's steps 5 and 6.
- The `flaw-match` prompt describes the output line format in words and places no sample flaw or finding id near the slot the model fills.
- Case files hold the PM's local repo paths, as 430's do. Nothing is pushed.
