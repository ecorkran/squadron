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
turns: 39
promptTokens: 3810675
cachedTokens: 3595551
cacheWriteTokens: 215074
completionTokens: 51209
durationSeconds: 573.6
costUsd: 6.209406
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-fable-5-2:
    rounds: 1
    costUsd: 6.2094063
    completionTokens: 51209
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
- `sq benchmark recall match`: an agent matcher for hit labels on document kinds, with bound, caps and resume, plus a hidden `_match` command and a built-in `flaw-match` template.
- Kind traits that 430 hard-coded for code: review template, scored severities, whether combs and the matcher apply.
- Report additions: where each row's hit labels came from, and a count of entries decided by the task gate.
- More arch cases mined and added as records (#373), and recipe files for the configs #373 names.

Excluded:
- The 9 first-pass cases of RESULTS.md sections 14-15 (`20261115-design/`). Their reviewed text is mostly not in git and sonnet had reviewed six of them. The plan's criterion is the 43 mined cases.
- Combs on document reviews. PM decision 20261117 (RESULTS.md section 18): no comb on design reviews. The `20261116-mined/comb/` outputs are not imported, and a recipe with combs is refused for a document set.
- Agent matching for code cases. The runbook rule "no model grades hits" stands for code; `match` refuses a code set.
- Grading findings REAL or MINOR (#340). Document rows show real share as ungraded.
- Running the #373 comparison. It is the PM's walkthrough step 6, because it is several hundred serial review calls.
- A case miner command (#326).
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
- `run_loop`, `stage_runner`, `run_plan`, `run_bound` and `ReviewBudget` for the match stage's dispatch, bound and caps.
- `run_review_with_profile` and `TemplateOutput.DECISIONS` for the matcher call.
- `TASK_GATE_MODEL` (`review/task_gate.py`), to recognise a task-gate output.
- `builtin_template_hash` (`recipes/stage_config.py`).

## Architecture

### Component Structure

New modules in `src/squadron/benchmark/recall/`:

| Module | Responsibility |
|---|---|
| `document_case.py` | The document case-file spec and its validation (D1) |
| `document_kind.py` | `DocumentKind`, registered three times, once per kind (D2) |
| `document_sandbox.py` | The reviewed tree with excluded paths removed and no history (D3) |
| `hand_run_documents.py` | Import of `20261116-mined/out/` (D7) |
| `hand_run_document_labels.py` | Import of the five grading passes (D8) |
| `match_plan.py` | Which review entries need a matcher call; bound and refusals (D9) |
| `match_stage.py` | Matcher input rendering and turning parsed lines into labels (D9) |
| `match_lines.py` | Lenient parser for matcher output lines (D9) |

Changed modules:

| Module | Change |
|---|---|
| `kinds.py` | `RecallKind` gains `traits` and `plan_import` (D2); `CodeKind` supplies both |
| `metrology/recall_case_models.py` | `RecallCaseKind` gains `ARCH`, `SLICE`, `TASKS`; `RealBugCase` gains optional `document`, `against`, `exclude`, `source`; `base` becomes optional (D1) |
| `metrology/recall_run_models.py` | `StageKind.MATCH`; `RecallRun.matches`; `StageEntry.gate_only` and `input_ref` (D7, D9) |
| `metrology/recall_label_models.py` | `LabelerKind.AGENT` (D9) |
| `hit_rule.py` | A bug with no locations is not gated (D4) |
| `stage_identity.py` | The review template comes from the kind's traits, not a fixed `code` |
| `scoring.py`, `label_candidates.py` | Scored severities are an argument, supplied from the kind's traits (D5) |
| `label_precedence.py` | Person over import over agent (D9) |
| `hand_run_import.py` | Calls the set's kind's `plan_import` |
| `case_intake.py` | Refuses a set that would hold more than one kind (D6) |
| `report_build.py`, `report_render.py`, `report_json.py` | Label-source counts and the gate-only count |
| `cli/commands/benchmark_recall*.py` | `match` and hidden `_match` |

New data: `data/templates/flaw-match.yaml`.

### Data Flow

```
document case files (YAML, one folder per kind) ──cases add──▶ cases + one set per kind
20261116-mined/out + grade..grade5 ──import──▶ RecallRun reviews + import label records

recipe + set + runs
  └─run─▶ as 430, with the kind's sandbox and review command:
           document_sandbox(commit, exclude) ─▶ <sq> review <kind> <document> [--against <parent>]
           → leak scan ─▶ review StageEntry
  └─match─▶ review entries with an unlabeled scored finding → bound → per entry, one at a time:
           <sq> benchmark recall _match (flaw-match template, no tools, no tree)
           → parsed lines ─▶ agent RecallLabels for the case + match StageEntry
  └─report─▶ 430's scoring with the kind's scored severities → table, label sources, gate-only count
```

### State Management

No new record types. Document cases are `recall_case` records, match calls are entries in `recall_run` records, and agent labels are `recall_labels` records. Matcher input and raw output go in the `REVIEWS` sidecar. Resume works as in 430: a match call's key is deterministic, and a rerun skips review entries whose scored findings all have a label.

## Technical Decisions

### D1 — A document case is the reviewed document, its commit and its verified flaws
Status: decided
- Case files live in `user/reference/document-recall-cases/<kind>/<name>.yaml`. The 43 are written once from `20261116-mined/cases.tsv`, `against.tsv` and `grade/<case>/flaws.json`; the four `design-review-recall-cases-*.md` files stay as the narrative record.
- **Flaw text is `flaws.json` text, unchanged.** That is the text the hand-run graders matched against, so the live matcher sees the same wording. Flaw ids (`F1`…) are the `flaws.json` ids, which the grading passes refer to.
- **`commit` is the full sha of the reviewed text.** The mined files give short shas and `<sha>^` forms; the case file holds the resolved 40 characters. `cases add` checks that `document` (and `against`) exist at that commit with `git cat-file -e`, and refuses the file otherwise.
- **No location derivation.** A document flaw has no fix-commit file list that a finding should cite, so `locations` is empty and the gate does not apply (D4).
- **`proof` may be empty.** Many flaws (all of migratory's) were verified by reading the reviewed text and the code at that commit, with no later commit. `source` is required instead: the mining file and section that records the evidence. Where a correcting or response commit exists it goes in `proof`.
- **Case id.** `RealBugCase` gains `document`, `against`, `exclude` and `source`, and `base` becomes `str | None`. The id payload gains `document`, `against` and `exclude` only when `document` is set, so the 17 stored code case ids do not change (tested). `commit` is stored in `head`.
- A model validator requires `base` for `code` and `document` for the document kinds.
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
- `DocumentKind(review_command, traits)` is registered for `ARCH`, `SLICE` and `TASKS`. `review_argv` is `<sq> review <review_command> <document> [--against <against>] --model <alias> --no-save --output file --output-path <out> --cwd .`.
- `RecallKind` gains two members:
  - `traits: KindTraits`, a frozen dataclass:

    | Trait | code | arch, slice, tasks |
    |---|---|---|
    | `review_template` | `code` | `arch`, `slice`, `tasks` |
    | `scored_severities` | CONCERN, FAIL | CONCERN, FAIL, NOTE (D5) |
    | `comb_template` | `comb` | none |
    | `match_template` | none | `flaw-match` |

  - `plan_import(results_dir, context, plan)`: the kind's hand-run layout (D7, D8). `CodeKind`'s is the existing reviews, combs, labels and overrides plan.
- `stage_identity.STAGE_TEMPLATES` loses its `REVIEW: "code"` entry; the review template hash comes from `traits.review_template`. A live review entry of an arch case therefore carries the arch template's hash.
- `run` refuses a recipe with combs when `comb_template` is none, and `match` refuses a set whose `match_template` is none, both before any call (exit 1).
- 430's integration note said a kind could be added without touching `scoring.py` or `stage_runner`. That does not hold: the data needs kind-specific scored severities (D5) and templates. The changes are the trait lookups above; no module branches on the kind value.
- Rejected: one `document` kind with a `doc_type` field. Three registry entries need no second dispatch inside the kind.

### D3 — The sandbox is the reviewed tree with saved reviews removed and no history
Status: decided
- At the reviewed commit every one of the 43 trees holds saved review files (2 to 527 of them under `project-documents/user/reviews`), and for some cases the document's own review, which names the flaws. The hand-run `prepare.py` exported the tree, deleted that directory, and committed what was left as a new one-commit repo. The sandbox does the same, so live results are comparable with the imported ones.
- `document_sandbox` enters `HistoryFreeSandbox(start_sha=commit)` unchanged (lock, cleanup and orphan sweep come with it), then, through the injected `ProcessRunner`, each under `benchmark.recall_fetch_timeout_s`:
  1. removes `.git` and every `exclude` path;
  2. `git init`, `git add -A`, and one commit with a fixed author and date.
- Removing a path from the working tree alone is not enough: the fetched commit would still hold it, and a reviewer with a shell could `git show` it. Rebuilding the repository leaves no object that holds an excluded file.
- An `exclude` path that does not exist at the commit fails the sandbox (`harness_failure`): the case file is wrong, and a silently skipped exclusion could leave the answer in the tree.
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
- `scoring.py` and `label_candidates.py` take the scored severities as an argument instead of importing `SCORED_SEVERITIES`. `report_build`, `label` and `match` pass the set's kind's trait. Code rows are unchanged.
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
- **Task-gate outputs.** 70 files (squadron-197-tasks and squadron-917-tasks, every config and run) are the task gate's rule-based FAIL: `model` is `TASK_GATE_MODEL`, and no model was called. They record no model, profile or tools.
  - Such a file imports with the config shared by the same alias's model-call outputs in the same set, and `gate_only: true`. The gate's result does not depend on the model, and the alias is what the run was given. If that alias's model-call outputs do not all share one config, the file is skipped and listed.
  - Without this the two cases would form a separate row per alias and drop out of the tasks row, and the row would no longer be "of 31".
  - A live review entry is marked `gate_only` by the same test on its output's `model`.
  - The report footer prints the number of gate-only entries used, with "no model call".
- Expected counts: 259 review entries for arch, 515 for slice, 507 for tasks; 27, 51 and 51 run records.

### D8 — Import of the grading passes: the first pass to grade a review wins
Status: decided
- Passes, in order: `grade`, `grade2`, `grade3`, `grade4`, `grade5`. Labeler `import:mined/<pass>`, one label record per case and pass.
- Each pass has `map.json` (`<case>/<rNN>` to alias and run) and, per case, `flaws.json` and `hits.json`. For a mapped review, every finding the grader was shown (severity not PASS) gets a label for every flaw of the case: `HIT` when `hits.json` lists its index `i` under that flaw and review, `MISS` otherwise. `i` is the finding's index in the output's `findings` list.
- **An absent key means no hit.** The brief asked for every review under every flaw, but the graders left out reviews with no hit (671 flaw-and-review pairs). A case folder with a `hits.json` was graded in full, which is how the hand-run `score_all.py` read it. The summary prints the absent-key count.
- **Regrades.** 172 reviews were graded again in later passes as anchors. A review takes its labels from the first pass that graded it; later gradings of it are not stored. The summary prints how many flaw decisions the regrades compared and how many disagreed (measured on the committed files: 11 of 574). Section 16 was computed from `grade` and `grade2`, so this order reproduces it.
- Refusals, each skipped and listed (exit 1 at the end, as in 430):
  - a pass's `flaws.json` whose flaw ids differ from the case's bug ids;
  - a `map.json` entry with no imported review, or a hit index with no finding;
  - a mapped case with no `hits.json`.
- Two findings of one case with the same content key and different labels: the earlier pass wins, and the conflict is counted and listed.

### D9 — `match`: an agent matches findings to flaws, blind, for document kinds
Status: decided
- **Why a model.** The location gate cannot narrow document findings, so every finding is a candidate for every flaw: about 14 findings by 2 flaws per haiku-xhigh review. The plan entry names agent grading as this slice's matching method, and the hand-run numbers this command must be comparable with came from grading agents.
- **Unit.** One call per stored review entry of the recipes given, when the entry has a scored finding with no hit label from any labeler. The input holds the case's flaws (id and text) and that review's scored findings (id, severity, title, description, location). It holds no alias, model, recipe or run index, so the matcher cannot know who wrote the review.
- **Call.** A scrubbed subprocess, `<sq> benchmark recall _match --input <file> --output <file> --model <alias>`, run in an empty directory with the `flaw-match` template: `output: decisions`, no tools. It is leak-scanned or marked `confined` exactly as a 430 stage call.
- **Prompt rule** (the hand-run brief's): a finding matches a flaw when it names the same underlying defect, in other words or at another location; a finding about the same area that raises a different problem does not.
- **Output.** One line per finding: the finding id, then the ids of the flaws it matches or the word for none, then a reason. `match_lines.py` parses it leniently (separators, case, markdown, flaw ids separated by commas or spaces), mapping the none word through one constant. Its test fixtures are real matcher outputs captured from the fixture run (walkthrough step 4), from at least two providers.
- **Labels.** For each finding with a parsed line: `HIT` for the flaws named, `MISS` for the case's other flaws. Written to the case's `RecallLabels` for labeler `agent:<alias>@<template hash, 8 hex>`, kind `AGENT`.
  - A finding with no line gets no label and stays undecided, so recall prints as a range (430 D3).
  - A line naming a flaw id the case does not have is discarded whole, counted, and logged at WARNING; that finding stays undecided.
- **Precedence.** Person over import over agent. Among agent labelers the newest `updated` wins. Imported labels stay in force when an agent grades the same finding.
- **Record.** `RecallRun.matches["<review entry_key>|<matcher entry_key>"]`, a `StageEntry` of kind `MATCH` with config, usage, outcome, leak verdict, `raw_ref`, and `input_ref` (sha256 of the input file, stored in the sidecar), so each call records what it was given.
- **Matcher model.** `--model` is required and has no default. The hand-run graders were Sonnet agents.
- **Checking the matcher.** `match --recheck` also matches entries that already have labels. Its labels are stored under the agent labeler (so they do not change any score), and the command prints agreement with the labels in force: flaw decisions compared, and how many differ. The hand-run regrade figure (11 of 574) is the yardstick. The command prints both numbers and passes no judgment.
- **Bound, caps, resume.** As 430 D9: `--max-cost` required, per-call figure from stored match entries of the same `config_key` or `--call-cost`, `--max-plan-calls` when plan-billed calls are pending, bound printed before the first call, serial calls, exit 2 at a cap.
- **Report.** Each row prints how many of its hit labels came from import, agent and person labelers, so an agent-matched row is never read as hand-checked.
- Rejected: one call per case covering every review, as the hand-run did. A per-review call is the natural resume unit, needs no shuffling to be blind, and keeps the input small.
- Rejected: `label` by a person as the only route. It works unchanged for document sets, and a person's label overrides the agent's, but it is the load this slice exists to remove.

### D10 — Failure modes and how each is observed
Status: decided
Each mode is logged at the level shown with case, run and stage, written to the entry or the command summary, and covered by a test asserting both. Modes not listed (auth preflight, timeouts, lock, store writes, orphan output files) are 430 D8's, unchanged, and apply to match calls as to comb calls.

| Mode | Level | Outcome |
|---|---|---|
| `cases add`: `document` or `against` missing at `commit`; `against` on an arch case or absent on a slice or tasks case; the set would hold two kinds | ERROR | Whole command refused, exit 1, nothing written |
| Sandbox: an `exclude` path is missing, or the rebuild commands fail or exceed `benchmark.recall_fetch_timeout_s` | WARNING | `harness_failure` + reason; (case, run) dropped from every recipe and counted |
| Sandbox: the commit can no longer be fetched (collected) | WARNING | `harness_failure` naming the commit |
| Review output is a task-gate result | INFO | `ok`, `gate_only: true`; counted in the report footer |
| Matcher call times out, or its output has no parseable line | WARNING | Match entry `config_failure`; no labels written; the findings stay undecided |
| Matcher output covers some findings only | WARNING | `ok`; the rest stay undecided; count printed |
| Matcher line names an unknown flaw id | WARNING | That line discarded and counted |
| Matcher subprocess exits without an output file | WARNING | Match entry `harness_failure`; rerun by `match --retry-harness` |
| `run` with combs, or `match`, on a kind that has none | ERROR | Refused, exit 1, before the lock |
| Import: file name matches no case of the set | — | Counted in one summary line |
| Import: the D8 refusals, or a gate file whose alias has no single config | WARNING | Skipped and listed; exit 1 at the end |

### D11 — More architecture cases are mined by hand and added as files (#373)
Status: decided
- Method: the validity rule and evidence labels of `design-review-recall-cases-migratory.md`, applied to architecture documents with a saved review in squadron, context-forge, migratory, trading-engine and the other local cf projects. Read-only: `git show`, `git diff`, `git log`, `git grep` at the reviewed commit. No model review is run and nothing is checked out.
- Each accepted case is a YAML file in `document-recall-cases/arch/` and a section in a new `user/reference/design-review-recall-cases-arch.md`, which also lists every candidate examined and why the rejected ones were rejected.
- Target: at least 40 arch flaws in `doc-flaws-arch` version 2 (19 exist). Mining stops at the target or when every architecture document with a saved review in those repos has been examined. If it stops short, the count and the reason go in that file and in a comment on #373; the slice is not blocked on the number.
- Reading squadron's own history to write case records is 430 D13's ruling.
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
| `match` | Match findings to flaws for the review entries of the recipes given | `--set NAME[@VERSION]`, `--recipe` (repeatable), `--runs N`, `--model ALIAS` (required), `--max-cost` (required), `--call-cost`, `--max-plan-calls`, `--recheck`, `--retry-harness`, `--case NAME` |
| `_match` (hidden) | One matcher call; launched by `match` | `--input`, `--output`, `--model` |
| `cases add`, `cases list` | Unchanged options; document kinds accepted; `commit=unreferenced` shown | |
| `import` | Unchanged options; the set's kind chooses the layout | |
| `run` | Unchanged options; refuses combs for a document set | |
| `report` | Unchanged options; one more column and footer item | |

`report` for a document set:

```
Case set doc-flaws-arch v1 (arch): 9 cases, 19 known flaws, runs 1..3
Hit rule: labels only (no location gate); scored severities CONCERN, FAIL, NOTE.
Matched nothing includes valid findings outside the known flaws.

| Recipe | Cases | Runs | Bug-hits | Recall | Bugs found | ... | Hit labels (import/agent/person) | Real share | Cost/run (basis) | Leak scan |
| fable-medium | 9 | 3 | 38/57 | 67% | 16/19 | ... | <n>/0/0 | ungraded | ... | 27 not scanned |
...
Gate-only entries (no model call): 0.
```

`report --json` gains `kind`, `label_sources` per row and `gate_only_entries`.

### Database / Storage Schema

No new record type and no migration; `schema_version` stays 1. Every added field is optional with a default, so stored 430 records read unchanged:
- `RealBugCase`: `document`, `against`, `exclude`, `source`; `base` optional.
- `RecallRun`: `matches: dict[str, StageEntry] = {}`.
- `StageEntry`: `gate_only: bool = False`, `input_ref: str | None = None`.
- `RecallLabels`: no change; a new `labeler_kind` value.

## Integration Points

### Provides to Other Slices
- **435, 436:** recipes with repeats, votes, focuses and sequential stages can be run on the document sets once those slices exist; nothing here is specific to single reviewers except the comb refusal.
- **Model answers** (`review-recall-results/SUMMARY.md`, `ANSWERS.yaml`): per-kind document rows from `report --json`.
- **#340:** the match stage (one no-tools decisions call per review entry, agent labeler, precedence) is the shape live grading needs.

### Consumes from Other Slices
- **430:** everything listed under Dependencies. The changes to 430 modules are additive: code sets, their ids, their imported records and their report rows are unchanged, and 430's reproduction tests keep passing.
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
- `run` on a document set reviews with the kind's production command in a sandbox that holds no excluded path in its tree or in any git object, and refuses a recipe with combs.
- `match`:
  - refuses a code set, a missing `--model` and a missing `--max-cost`;
  - prints its bound before the first call, stops at a cap with exit 2, and resumes;
  - sends no alias, model or run index to the matcher;
  - writes agent labels that turn an undecided row into a decided one, and leaves imported and person labels in force;
  - with `--recheck`, prints agreement with the labels in force and changes no score.
- A partial matcher output leaves the uncovered findings undecided, and recall prints as a range.
- The report prints label-source counts per row and the gate-only entry count. The imported tasks rows count squadron-197-tasks and squadron-917-tasks as gate-only.
- `doc-flaws-arch` version 2 holds the new arch cases, with the narrative file listing every candidate examined. The flaw count and, if below 40, the reason are posted on #373.
- Recipe files `opus-high`, `fable-medium`, `hy4`, `mimo`, `fable-haiku` and `luna-r` are committed.

### Technical Requirements
- `ruff format`, `ruff check` and `pyright` (zero errors) pass, and `tests/benchmark/recall/` passes.
- Tests run no model and no git outside fixtures.
- The import is tested against the committed `20261116-mined/` files.
- The matcher-line parser's fixtures are real captured outputs.
- Every D10 mode has a test asserting its outcome and its log record.
- `HistoryFreeSandbox` and `sq review` are unchanged (no diff in their files).
- The runbook gains a "Document reviews" section naming the case folders, sets, `match` and the hand-run folders it replaces.

### Integration Requirements
- A stub kind with its own traits runs a review stage and a match stage in a test, with no change to `run_loop` or `scoring`.
- `report --json` for a document set has a schema test.

### Verification Walkthrough

Run from the squadron checkout as `uv run sq ...` until a release carries the commands. `C=project-documents/user/reference/document-recall-cases`, `P=project-documents/user/reference/review-recall-recipes`. Steps 1-4 are checked during implementation; steps 5 and 6 are the PM's.

1. **Load the cases.**
   ```bash
   for kind in arch slice tasks; do
     uv run sq benchmark recall cases add $C/$kind/ --set doc-flaws-$kind
   done
   uv run sq benchmark recall cases list --set doc-flaws-arch
   ```
   Expect 9, 17 and 17 cases at v1, and `commit=unreferenced` on squadron-403-design, context-forge-260-arch and context-forge-268-tasks.

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
   Expect the bug-hit and bugs-found numbers in the Functional Requirements table, every row `not scanned`, hit labels all from import, and a gate-only count on the tasks report.

4. **Run, match and report on the fixture.**
   ```bash
   uv run python tests/benchmark/recall/fixtures/doc_repo/build.py
   uv run sq benchmark recall cases add tests/benchmark/recall/fixtures/doc_repo/cases/slice/ --set fixture-slice
   uv run sq benchmark recall run --set fixture-slice --recipe luna-r --runs 1 --max-cost 0.10 --call-cost 0.02
   uv run sq benchmark recall report --set fixture-slice --recipe luna-r      # recall as a range
   uv run sq benchmark recall match --set fixture-slice --recipe luna-r --model <matcher alias> --max-cost 0.10 --call-cost 0.02
   uv run sq benchmark recall report --set fixture-slice --recipe luna-r      # decided, agent label count shown
   ```
   The fixture repo holds a slice design with one planted contradiction, its parent, and a saved review naming it under the excluded path. Confirm the sandbox tree has no reviews directory and `git log` in it shows one commit. A second `match` prints `0 calls to make`.

5. **Check the matcher against the hand-run graders (PM).**
   ```bash
   uv run sq benchmark recall match --set doc-flaws-arch@1 --recipe haiku-xhigh --runs 1 \
     --model <matcher alias> --recheck --max-cost <USD> --call-cost <USD per call>
   ```
   9 calls. Compare the printed disagreement with the hand-run regrade figure before trusting agent-matched rows.

6. **Arch comparison for #373 (PM).**
   ```bash
   uv run sq benchmark recall run --set doc-flaws-arch --runs 3 --max-cost <USD> --call-cost <USD per call> \
     --recipe fable-medium --recipe opus-high --recipe haiku-xhigh --recipe hy4 --recipe mimo
   uv run sq benchmark recall match --set doc-flaws-arch --runs 3 --model <matcher alias> --max-cost <USD> \
     --recipe fable-medium --recipe opus-high --recipe haiku-xhigh --recipe hy4 --recipe mimo
   uv run sq benchmark recall report --set doc-flaws-arch --runs 3 \
     --recipe fable-medium --recipe opus-high --recipe haiku-xhigh --recipe hy4 --recipe mimo --recipe fable-haiku
   ```
   Live entries have their own stage identity, so every review runs live: 15 review calls per arch case, one after another (#372). The report is appended to RESULTS.md as a new section and #373 is updated.

## Risk Assessment

### Technical Risks
- **The matcher is a model.** Its hits are less certain than fix-commit ground truth with a person's label, and a loose or strict matcher moves every row.
- **Unreferenced commits.** Three cases depend on commits that `git gc` can remove from the source repos.
- **Mining yield.** There may be fewer than 21 new valid arch flaws in the local repos.

### Mitigation Strategies
- `--recheck` measures the matcher against the imported labels (step 5), the report prints label sources on every row, and a person's label always wins.
- `cases list` flags unreferenced commits, and a collected commit is a counted harness failure, never a wrong score. Pinning them with a ref in the source repos is the PM's call; this slice writes nothing to those repos.
- D11's stop rule records the yield and its reason instead of blocking.

## Implementation Notes

### Development Approach
1. Case model fields and kinds, `document_case.py`, `KindTraits` on both kinds, the one-kind-per-set rule, the ungated-bug rule. The 43 case files and three sets. Test that code case ids are unchanged.
2. Scored severities as an argument; template from traits. 430's tests still pass.
3. `hand_run_documents.py` and `hand_run_document_labels.py`, tested on the committed files, then the section 16 reproduction test. This is the first result for the PM.
4. `document_sandbox.py`, `DocumentKind.review_argv`, the comb refusal, the fixture doc repo, and `run` end to end on it with a scripted model command.
5. `flaw-match` template, `_match`, `match_lines.py`, `match_plan.py`, `match_stage.py`, `match` with bound, caps, resume and `--recheck`; label precedence; report label sources and gate-only count.
6. Arch mining (D11), the new case files, set version 2, recipe files, the #373 comment, and the runbook section.

Testing: unit tests per module; scoring tests add a document set with NOTE-only hits, a gate-only entry, agent labels under an import label, and a partial matcher output.

### Special Considerations
- No task runs a review against squadron's own history. Steps 1-3 read commit metadata and committed files only, step 4 uses the fixture repo, and the live document runs (19 of the 43 cases are squadron's) are the PM's steps 5 and 6.
- The `flaw-match` prompt describes the output line format in words and places no sample flaw or finding id near the slot the model fills.
- Case files hold the PM's local repo paths, as 430's do. Nothing is pushed.
