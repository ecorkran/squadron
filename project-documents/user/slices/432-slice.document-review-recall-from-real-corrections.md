---
docType: slice-design
slice: document-review-recall-from-real-corrections
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies:
- 430
interfaces: []
dateCreated: 20261121
dateUpdated: 20261123
status: deprecated
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

`sq benchmark recall` (slice 430) measures code reviewers on real escaped bugs. This slice makes it measure document reviewers: architecture documents, slice designs and task files. A case is a document at the commit that held the reviewed text, plus the flaws a later commit corrected. The reviewer is the production `sq review arch|slice|tasks` command. A new command, `match`, uses one model to match a review's findings to the case's flaws, so no person reads findings to score a run.

This is the command [#383](https://github.com/ecorkran/squadron/issues/383) asks for: defects found out of defects known, per review shape, run before a change to the review path ships.

**Reduced on 20261121 (PM decision).** The first design also imported the 43 hand-run cases, reproduced RESULTS.md section 16, mined more architecture cases and supported two matchers. Its review found the import and those extras responsible for most of its defects, and five places where it departed from the architecture. All of that is now [#387](https://github.com/ecorkran/squadron/issues/387). This design departs from the architecture nowhere.

## Value

- **User-facing.** "Did this change to a review prompt, template, model or recipe make document reviews find more or fewer known defects" is answered by three commands on fixed cases, with a cost figure.
- **Cheap.** A measurement costs its reviews plus one no-tools matcher call per review. Stored reviews of other configs are reused.

## Technical Scope

Included:
- Three case kinds, `arch`, `slice` and `tasks`, behind 430's `RecallKind` seam, with a document case-file format.
- Two cases, in one case set per kind: amoeba slice 260's task file as it entered tasks-review round 3, and one slice design (D7).
- The document sandbox: 430's sandbox (head and its history back to base) with the case's excluded paths removed from the working tree.
- `sq benchmark recall match`: one matcher per case set, with a cost bound from observed costs, caps and resume.
- Kind traits that 430 hard-coded for code: review template, scored severities, and whether combs or the matcher apply.
- Document findings stored by reference in the sidecar.
- Two header lines on the text report for a document set.

Excluded, each in [#387](https://github.com/ecorkran/squadron/issues/387) unless another issue is named:
- Import of the hand-run results and the section 16 reproduction.
- Flaws with no later correcting commit. Whether they count is a PM decision recorded there.
- More architecture cases (#373) and its recipe files. The `arch` kind is built and tested on a fixture; this slice adds no arch case.
- `match --recheck`, a second matcher beside the first, and an unreferenced-commit check in `cases list`.
- Report columns that split bug-hits by label source or proof status.
- Combs on document reviews (PM decision 20261117, RESULTS.md section 18). A recipe with combs is refused for a document set.
- Agent matching for code cases. `match` refuses a code set.
- Grading findings REAL or MINOR (#340). Document rows show real share as ungraded.
- New `report --json` fields (#386).
- Cases from squadron's own history (architecture amendment 20261115).

## Dependencies

### Prerequisites
- **430 (complete):** the `recall` package, its record types, recipes, run loop, hit rule, labels, scoring and report.
- The amoeba and context-forge repos readable at their recorded paths. A missing repo is a harness failure, as in 430 D8.

### Interfaces Required
- `sq review arch <doc>`, `sq review slice <doc> --against <parent>` and `sq review tasks <doc> --against <design>`, each with `--model <alias> --no-save --output file --output-path <file> --cwd .`. Production commands, unchanged.
- `RecallKind`, `register_kind`, `KindContext` (`recall/kinds.py`); `review_sandbox` (`recall/review_sandbox.py`), unchanged.
- `observed_costs`, `require_review_timeout`, `render_bound`, `auth_preflight` (`recall/run_bound.py`).
- `LeakChecker`, `StageContext` (`recall/stage_runner.py`); `recall_leak_rules`, `TranscriptLeakChecker` (`recall/leak_check.py`).
- `stage_config`, `builtin_template_hash`, `COMB_TEMPLATE_NAME` (`recipes/stage_config.py`).
- `run_review_with_profile` for the matcher call.

## Architecture

### Component Structure

New modules in `src/squadron/benchmark/recall/`:

| Module | Responsibility |
|---|---|
| `document_case.py` | `DocumentCaseFileSpec` and `FlawSpec`, validation, and the checks at the commit (D1) |
| `document_recall_kind.py` | `DocumentRecallKind`, registered once per kind (D2). Not `DocumentKind`: that name is the review package's enum |
| `findings_store.py` | Writing a document entry's findings to the sidecar and filling them back in on read (D5) |
| `match_stage.py` | Matcher input, `parse_matches`, the match entry, and labels from a stored entry (D6) |
| `match_loop.py` | Which review entries need a call, the bound, and the serial calls (D6) |

Changed modules:

| Module | Change |
|---|---|
| `kinds.py` | `KindTraits`; `RecallKind` gains `traits`; `CodeKind` supplies its traits and refuses a bug with no locations |
| `metrology/recall_case_models.py` | `RecallCaseKind` gains `ARCH`, `SLICE`, `TASKS`; `RealBugCase` gains optional `document`, `against`, `exclude` |
| `metrology/recall_run_models.py` | `StageKind.MATCH`; `RecallRun.matches`; `StageEntry.findings_ref` and `input_ref` |
| `metrology/recall_label_models.py` | `LabelerKind.AGENT` |
| `case_models.py` | The quoted-sha guard, the YAML read and the validation-error text become public for `document_case.py` |
| `case_intake.py` | Refuses a set that would hold more than one kind |
| `hit_rule.py` | A bug with no locations is not gated (D3) |
| `stage_identity.py` | `live_stage_config` and `LiveStageResolver` take the templates table (D2) |
| `recall_services.py`, `live_services.py` | The factory takes the set's kind's templates (D2) |
| `stage_runner.py` | Its `COMB_TEMPLATE` is replaced by `COMB_TEMPLATE_NAME` |
| `stage_ingest.py` | A document review entry's findings go to the sidecar (D5); a task-gate output is a harness failure (D8) |
| `leak_check.py` | The kind's forbidden paths join the leak rules; an entry point that needs no `PendingStage` (D4, D6) |
| `run_bound.py` | The per-call figure is a function both bounds call (D6) |
| `run_loop.py` | The cap check becomes a function both loops call (D6) |
| `scoring.py`, `label_candidates.py` | The scored severities are a required argument (D2) |
| `label_precedence.py` | Person labels over agent labels |
| `report_build.py`, `report_render.py` | Two header lines for a document set; code reports unchanged |
| `recipes/stage_config.py` | `stage_config` takes the tools actually given (D6) |
| `cli/commands/benchmark_recall_stage.py` | `_stage` picks its call from a table keyed by template name; `--diff` is required only by the comb call |
| `cli/commands/benchmark_recall*.py` | `match`; the comb refusal before the lock in `run` and `report` |

New data: `data/templates/flaw-match.yaml`. Not changed: `recipes/decisions.py`, `comb_call.py`, `review_sandbox.py`, `sq review`.

Existing tests that change:
- `StubKind` in `tests/benchmark/recall/test_kinds.py` and `test_run_end_to_end.py` gains `traits`.
- `test_stage_identity.py`, `test_run_plan.py` and `tests/cli/test_benchmark_recall_run.py` pass the code templates table.
- Tests that call the scoring and candidate functions pass `SCORED_SEVERITIES`.

`tests/benchmark/recall/test_report_render.py` is not edited: a code report keeps its 14 columns.

### Data Flow

```
document case files ──cases add──▶ cases + one set per kind

recipe + set + runs
  └─run─▶ as 430, with the kind's sandbox and review command:
           review_sandbox(base, head) minus exclude paths
           ─▶ <sq> review <kind> <document> [--against <parent>]
           → leak scan ─▶ review StageEntry, findings in the sidecar
  └─match─▶ review entries with an unlabeled scored finding and no match entry → bound
           → one at a time, no sandbox, no tools:
             <sq> benchmark recall _stage --template flaw-match
             → match StageEntry in RecallRun.matches, then agent RecallLabels
  └─report─▶ 430's scoring with the kind's scored severities
```

### State Management

No new record type. Document cases are `recall_case` records, match calls are entries in `recall_run` records, and agent labels are `recall_labels` records, one per case. Findings of document entries, matcher input and raw output are in the `REVIEWS` sidecar.

## Technical Decisions

### D1 — A document case is the reviewed document, its commit and the flaws a later commit corrected
Status: decided
- Case files live in `user/reference/document-recall-cases/<kind>/<name>.yaml`.
- **Ground truth is the architecture's.** Every flaw has a non-empty `proof`: the commit that corrected it. A flaw with no correcting commit is not in the case file. Validation refuses an empty `proof`.
- `head` is the full sha of the commit holding the reviewed text. `base` is an ancestor of `head`, normally the parent of the commit that first added the document; it sets how much history the sandbox holds (D4).
- `cases add` checks, through the injected `ProcessRunner` and under `benchmark.recall_fetch_timeout_s`: `document`, `against` and every `exclude` path exist at `head`; `base` is an ancestor of `head`; each `proof` commit exists and is not an ancestor of `head`. Any failure refuses the whole command.
- **No locations.** A document flaw's correcting commit changes the document, and a finding about it usually cites code. `locations` is empty and the gate does not apply (D3).
- `document_case.py` defines `DocumentCaseFileSpec` and `FlawSpec` (`extra="forbid"`). They do not extend `CaseFileSpec` or `BugSpec`, whose location rules do not apply.
- `RealBugCase` gains `document`, `against` and `exclude`, each `None` or empty for a code case. The id payload gains them only when `document` is set, so the 17 stored code case ids do not change (tested).
- Tests of the committed case files call no git: the checks are answered from a captured file, as the code cases' test reads `proof_files.json`.

```yaml
name: <case name>
kind: tasks                      # arch | slice | tasks
repo: ~/source/repos/manta/<repo>
host_repo: <owner>/<repo>        # for the leak rules (430 D6)
distribution: <package name>     # for the leak rules
base: <40-character sha>
head: <40-character sha>         # the commit holding the reviewed text
document: <path in the tree>
against: <path in the tree>      # slice and tasks only; refused for arch
exclude:                         # removed from the working tree (D4); required, may be []
  - project-documents/user/reviews
status: checked
bugs:
  - id: K01
    description: "..."
    proof: ["<sha of the correcting commit>"]
    original_review: missed      # missed | reported
```

### D2 — Three kinds, one implementation, and the kind carries its traits
Status: decided
- `DocumentRecallKind(review_command, traits)` is registered for `ARCH`, `SLICE` and `TASKS`. `review_argv` is `<sq> review <review_command> <document> [--against <against>] --model <alias> --no-save --output file --output-path <out> --cwd .`.
- `RecallKind` gains `traits: KindTraits`, a frozen dataclass in `kinds.py`:

  | Trait | code | arch, slice, tasks |
  |---|---|---|
  | `templates: Mapping[StageKind, str]` | `REVIEW: code`, `COMB: comb` | `REVIEW: arch`, `slice` or `tasks`; `MATCH: flaw-match` |
  | `scored_severities` | `SCORED_SEVERITIES` | that set plus NOTE |
  | `forbidden_paths(case) -> list[str]` | none | `.git` and the case's `exclude` paths (D4) |
  | `findings_by_reference` | false | true (D5) |

- **How the kind reaches the seams.** Each command reads the set first, then builds its services. `RecallServicesFactory` becomes `Callable[[Path, KindTraits], RecallServices]`, and `build_production_recall_services` and `build_production_live_services` pass `traits.templates` to `LiveStageResolver(templates)` and `live_stage_config(alias, stage_kind, templates)`. The code kind's table is today's `STAGE_TEMPLATES`.
- **Scored severities are a required argument**, with no default, on `recipe_outputs`, `_pair_variants` and `reviewer_output` in `scoring.py` and on the candidate filter in `label_candidates.py`. The report, `label` and `match` pass the trait. A default would silently score a document set with the code severities.
- NOTE is scored for documents because the #383 key includes defects reviewers reported as notes. "Findings/run" for a document row counts CONCERN, FAIL and NOTE, and the header says so.
- **Refusals before the lock**, in the command, exit 1: `run` or `report` with a comb recipe on a kind with no `COMB` template; `match` on a kind with no `MATCH` template. Without the check `STAGE_TEMPLATES[COMB]` raises a `KeyError` nothing catches.
- A set holds one kind. `cases add` refuses a call that would mix kinds, and `run`, `match`, `report` and `label` refuse a stored set that does.
- No module compares a kind value.

### D3 — A bug with no locations is not gated
Status: decided
- `hit_rule.gate` returns `CANDIDATE` when the bug has no locations. Today a finding that cites any path is a decided miss for such a bug.
- `CodeKind.validate` refuses a bug whose resolved locations are empty, so the rule applies only to kinds that mean it.
- Document hits are decided by labels alone: agent (D6) or person.

### D4 — The sandbox keeps history back to base, and the excluded paths are leak-scanned
Status: decided
- `DocumentRecallKind.open_sandbox` enters `review_sandbox(repo, base, head, …)` unchanged, then removes each `exclude` path from the working tree. This is the sandbox the architecture defines for reviewer recall.
- The tree at `head` holds saved reviews, and the document's own earlier review can name its flaws. Removing them from the working tree hides them from file reads. They remain in git objects.
- **Leak rule.** `recall_leak_rules` adds the kind's `forbidden_paths` to the hits: the sandbox's `.git` directory and each excluded path. A transcript that reads or names one makes the entry `leaked`, which drops that case and run from every recipe, as any 430 leak does.
- A profile judged `confined` (squadron's jailed read, list and grep tools) has no shell, so it cannot run git; git objects are compressed and not readable as text through those tools. It stays `confined`.
- The sandbox test asserts that no excluded path is in the working tree and that a transcript reading `.git` is judged `leaked`.

### D5 — Document findings are stored by reference
Status: decided
- The architecture keeps findings inline because they are short. Document findings are not (a median of 47 KB per run record was measured on the hand-run outputs), so they are not stored inline.
- When `traits.findings_by_reference` is true, `stage_ingest` writes the entry's normalized findings as JSON to the `REVIEWS` sidecar and stores the key in `StageEntry.findings_ref`; `StageEntry.findings` is empty on disk.
- `findings_store.fill(run, sidecar) -> RecallRun` returns a copy with each such entry's findings read back. The recall store's run reader calls it once, so scoring, labels and the matcher see filled entries and do not change.
- A `findings_ref` with no sidecar file raises a store error naming the run and entry. It is never read as "no findings".
- Code entries are unchanged: `findings_ref` is `None` and findings stay inline.

### D6 — `match`: one model matches findings to flaws, blind
Status: decided
- **Unit.** One call per stored review entry of the recipes given, when the entry has a scored finding with no label for some flaw of its case, and the run holds no match entry for it.
- **Input** (a JSON object, written to the `_stage --input` file): `flaws` (id and text) and `findings` (id, severity, title, description, location). It holds no alias, model, recipe or run index.
- **Two id namespaces.** Flaws keep their case ids. Findings are rendered as `R1`…`Rn`, so a line cannot name a finding where a flaw is meant. A fixture has overlapping numbers.
- **Call.** `<sq> benchmark recall _stage --template flaw-match --input <file> --output <file> --model <alias>`, in a scrubbed subprocess and an empty directory, under `benchmark.review_timeout_s` (`require_review_timeout`; `match` refuses without it). `_stage` picks its call from a table keyed by `COMB_TEMPLATE_NAME` and `MATCH_TEMPLATE_NAME`. The match call invokes `run_review_with_profile` with an empty tool list.
- **Prompt rule.** A finding matches a flaw when it names the same underlying defect, in other words or at another location. A finding about the same area that raises a different problem does not. The prompt describes the output line in words and places no sample id near the slot.
- **Output.** One line per finding: the finding id, a separator, then the flaw ids it matches or the none word, then optionally a dash and a reason. `parse_matches(raw, finding_ids, flaw_ids)` in `match_stage.py` reads it with its own line recognition. `recipes/decisions.py` is not touched, so the production comb path cannot change.
- **Entry.** `match_stage.match_entry` builds the `StageEntry` (kind `MATCH`, with `raw_ref` and `input_ref`). It does not go through `ingest_output`, which reads every non-review output as comb decisions. It is stored in `RecallRun.matches` under the review entry's key.
- **Labels.** For each finding with a parsed line: `HIT` for the flaws named, `MISS` for the case's other flaws, labeler kind `AGENT`. A finding with no line gets no label and stays undecided, so recall prints as a range: absent is absent, never a miss.
- **Identity.** The matcher's config is built by `stage_config` with the tools actually given (none), not the alias's `tool_use`. The labeler is `agent:<12 hex>` of the config key and the effort sent.
- **One matcher per set.** `match` refuses, exit 1, when the set's cases hold agent labels from another matcher, and names it. `match --replace` removes that matcher's label records and match entries for the set's cases first, and prints the counts. A person's label always wins over an agent's.
- **Bound from observed costs.** The per-call figure is the largest observed `cost_usd` for the matcher's config key among stored match entries, else `--call-cost`. The bound is the sum over pending calls plus the largest figure once. `run_bound.py`'s figure function is shared; `observed_costs` reads match entries too. `--max-cost` and `--call-cost` are required; `--max-plan-calls` when the matcher is plan-billed. Exit 2 at a cap.
- **The loop.** `match_loop.py` is separate from `run_loop.run_pending`, which opens a case sandbox per stage and plans `PendingStage`s; a matcher needs neither, so a missing repo cannot fail a match. What is shared is extracted, not copied: the cap check (`run_loop._check_caps` becomes a public function), the per-call figure, the recall lock, the auth preflight and `render_bound`.
- **Resume, as 430.** The scrubbed home is kept until the entry is stored. A rerun that finds an output file with no entry builds the entry from it and makes no new call. An `ok` entry whose findings have no agent labels gets its labels rebuilt from `input_ref` and `raw_ref`, with no call.
- **Leak check.** `TranscriptLeakChecker` gains an entry point that takes the case, the profile, the call's home and its output folder, and `check(context)` calls it. The match loop uses it with the empty directory as the only tree.
- A failed call is `harness_failure`, never `config_failure`: the matcher's failure says nothing about the reviewed config. `--retry-harness` repeats failed calls.
- `--model` is required and has no default.

### D7 — The two cases
Status: decided
- **`amoeba-260-tasks`**, set `doc-flaws-tasks`. `repo` amoeba, `head` `1be45d3a00c4eedc714216249b1a03600c267f62`, `document` `project-documents/user/tasks/260-tasks.hub-and-door.md`, `against` `project-documents/user/slices/260-slice.hub-and-door.md`, `exclude` `project-documents/user/reviews`. The flaws are the 17 in the #383 comment of 20261121 (K01 to K17). Each goes in the case file with the amoeba commit that corrected it; one with no correcting commit is left out and named in the case's `notes`.
- **One slice-design case**, set `doc-flaws-slice`, from the candidates already mined in `user/reference/design-review-recall-cases-context-forge.md` and `-migratory.md`. Take the first slice-design candidate, in file order, that has at least one flaw corrected by a later commit. If none has one, use amoeba's `260-slice.hub-and-door.md` at the commit its slice review read, with the flaws its response commits corrected. The case's `notes` say which rule chose it.
- No case comes from squadron's own history.

### D8 — Failure modes and how each is observed
Status: decided
Each mode is logged at the level shown with case, run and stage, and covered by a test asserting the outcome and the log record. Modes of `run` not listed are 430 D8's, unchanged.

| Mode | Level | Outcome |
|---|---|---|
| `cases add`: a path missing at `head`, `base` not an ancestor, a `proof` commit missing or not later, an empty `proof`, `against` on an arch case or absent otherwise, a second kind for the set | ERROR | Whole command refused, exit 1, nothing written |
| `cases add`: a git check cannot run or times out | ERROR | Refused, naming the case and the command |
| Sandbox: removing an excluded path fails | WARNING | `harness_failure` + reason; case and run dropped from every recipe |
| Review transcript reads `.git` or an excluded path | WARNING | Entry `leaked`; case and run dropped from every recipe |
| Review output is the task gate's rule-based result (no model ran) | WARNING | `harness_failure`, reason "task gate"; the case cannot measure a model |
| A `findings_ref` has no sidecar file | ERROR | The command stops with a store error naming the run and entry |
| Matcher call times out, exits with no output file, or gives no parseable line | WARNING | Match entry `harness_failure`; no labels; repeated by `--retry-harness` |
| Matcher output covers some findings only | WARNING | `ok`; the rest stay undecided; count printed |
| Matcher line names an unknown flaw id or finding id, or repeats a finding | WARNING | Line discarded and counted; the first line per finding wins |
| Match leak scan `leaked` or `scan_unavailable` | WARNING | Match entry stored with that verdict; no labels |
| A rerun finds a match output with no entry | INFO | Entry built from the output; no call |
| `match` when another matcher's labels exist, without `--replace` | ERROR | Refused, exit 1, naming the matcher |
| `run` or `report` with combs on a document set; `match` on a code set | ERROR | Refused, exit 1, before the lock |

## Implementation Details

### API Contracts

Exit codes as 430: 0 complete, 1 refused or error, 2 cap reached.

| Command | Change |
|---|---|
| `match` | New. `--set NAME[@VERSION]`, `--recipe` (repeatable), `--runs N`, `--model ALIAS`, `--max-cost`, `--call-cost`, `--max-plan-calls`, `--retry-harness`, `--replace`, `--case NAME` |
| `_stage` (hidden) | One comb or matcher call, chosen by `--template` |
| `cases add`, `cases list` | Document kinds accepted |
| `run`, `report`, `label` | Options unchanged; the refusals in D2 |

`report` for a document set prints 430's table and columns, with these header lines:

```
Case set doc-flaws-tasks v1 (tasks): 1 cases, <n> known flaws, runs 1..3
Hit rule: labels only (no location gate); scored severities CONCERN, FAIL, NOTE.
Matcher: <labeler id> (<alias>), or "none (no agent labels)".
```

### Database / Storage Schema

No migration; `schema_version` stays 1. Every added field is optional with a default, so stored 430 records read unchanged:
- `RealBugCase`: `document`, `against`, `exclude`.
- `RecallRun`: `matches: dict[str, StageEntry] = {}`.
- `StageEntry`: `findings_ref: str | None = None`, `input_ref: str | None = None`.
- `RecallLabels`: a new `labeler_kind` value.

## Integration Points

### Provides to Other Slices
- **#387:** the kinds, the sandbox, by-reference findings and the matcher, which the import of the 43 hand-run cases builds on.
- **435, 436:** recipes with repeats, votes and focuses can be run on the document sets.
- **#340:** the match loop is the shape live grading needs.

### Consumes from Other Slices
- **430.** Stored records, code case ids, code report rows and `report --json` are unchanged. Changes that are not purely additive: `RecallKind` gains `traits`; `live_stage_config`, `LiveStageResolver` and the services factory take the kind's templates; the scoring and candidate functions take the scored severities; `stage_config` takes the tools given; `_stage`'s `--diff` becomes optional.
- **434.** The production comb path is untouched: `recipes/decisions.py` and `comb_call.py` have no diff.

## Success Criteria

### Functional Requirements
- `cases add` loads `amoeba-260-tasks` into `doc-flaws-tasks` and the slice-design case into `doc-flaws-slice`. Every flaw has a correcting commit. A file with a missing document, an empty `proof`, a wrong `against` or a second kind refuses the whole command.
- The 17 stored code case ids are unchanged, and 430's report tests pass.
- `run` on a document set reviews with the kind's production command, in a sandbox with history back to `base` and no excluded path in the working tree.
- A document review entry's findings are in the sidecar and its run record holds a reference; scoring reads them through the store.
- `match` refuses a code set, a missing `--model`, `--max-cost`, `--call-cost` or `benchmark.review_timeout_s`, and another matcher's labels without `--replace`. It opens no sandbox, prints a bound from observed costs before the first call, stops at a cap with exit 2, and resumes without paying twice.
- The matcher gets no alias, model or run index and no tools.
- A partial matcher output leaves the uncovered findings undecided and recall prints as a range.
- `report` on each set prints defects found out of defects known per recipe, the cost per run, and the matcher.

### Technical Requirements
- `ruff format`, `ruff check` and `pyright` (zero errors) pass, and `tests/benchmark/recall/` passes.
- Tests run no model and no git outside fixtures.
- `parse_matches` fixtures are real captured outputs from two providers.
- `recipes/decisions.py`, `comb_call.py`, `review_sandbox.py` and `test_report_render.py` have no diff.
- Every D8 mode has a test asserting its outcome and its log record.
- The runbook gains a "Document reviews" section naming the case folders, the sets, `match` and `benchmark.review_timeout_s`.

### Verification Walkthrough

Run from the squadron checkout. `C=project-documents/user/reference/document-recall-cases`. The `haiku-xhigh` recipe is in `project-documents/user/reference/review-recall-recipes/`.

1. **Set the timeout once** (both `run` and `match` refuse without it):
   ```bash
   uv run sq config set benchmark.review_timeout_s 1800
   ```
2. **Load the cases.**
   ```bash
   uv run sq benchmark recall cases add $C/tasks/ --set doc-flaws-tasks
   uv run sq benchmark recall cases add $C/slice/ --set doc-flaws-slice
   uv run sq benchmark recall cases list --set doc-flaws-tasks
   ```
   Expect one case in each set, and the flaw count the case file holds.
3. **Review, match, report on the tasks case.**
   ```bash
   uv run sq benchmark recall run --set doc-flaws-tasks --recipe haiku-xhigh --runs 1 --max-cost 2 --call-cost 1.20
   uv run sq benchmark recall report --set doc-flaws-tasks --recipe haiku-xhigh
   uv run sq benchmark recall match --set doc-flaws-tasks --recipe haiku-xhigh --model <matcher alias> --max-cost 1 --call-cost 0.20
   uv run sq benchmark recall report --set doc-flaws-tasks --recipe haiku-xhigh
   ```
   The first report prints recall as a range and `Matcher: none`. The second prints a decided figure and the matcher. A repeat of `match` prints `0 calls to make`.
4. **Compare with the hand score.** The #383 table gives 3 to 6 key items per `haiku-xhigh` run on this document. A matcher figure far outside that range means the matcher or the key needs a look before the number is used.
5. **Capture the parser fixtures.** Run `match` once more with `--replace` and an alias on another provider, and copy both raw outputs from the `REVIEWS` sidecar into `tests/benchmark/recall/fixtures/match/`.

## Risk Assessment

### Technical Risks
- **The matcher is a model.** A loose or strict matcher moves every row, and one case per set cannot show it.
- **Two cases.** A change tuned to these two documents can look better than it is. #387 adds the 43.
- **Key items with no correcting commit** drop out of the amoeba case, so its flaw count may be below 17.

### Mitigation Strategies
- Walkthrough step 4 compares the matcher with the hand score on the same document, and a person's label always overrides an agent's.
- The report header prints the case and flaw counts, so a figure is never read without its size.
- The case's `notes` name every key item left out and why.

## Implementation Notes

### Development Approach
1. Case model fields and kinds, `document_case.py`, `KindTraits` on both kinds, the one-kind-per-set rule, the ungated-bug rule. Test that code case ids are unchanged.
2. Scored severities as a required argument; templates from traits through the services factory; the comb refusals.
3. The document sandbox, forbidden paths in the leak rules, by-reference findings, the task-gate outcome, and `run` end to end on a fixture document repo with a scripted model command.
4. `flaw-match` template, `_stage`'s template table, `match_stage.py`, `match_loop.py` with the shared cap check and figure, `match` with bound, caps, resume, `--retry-harness` and `--replace`, label precedence, the report header.
5. The two case files, their captured git answers, and the runbook section.

### Special Considerations
- No task runs a review against squadron's own history. The live runs in the walkthrough use amoeba and context-forge documents.
- Case files hold the PM's local repo paths, as 430's do. Nothing is pushed.
