---
docType: slice-design
slice: reviewer-recall
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [421, 425, 300, 400, 402]
interfaces: [425]
dateCreated: 20261104
dateUpdated: 20261105
status: not_started
---

# Slice Design: Reviewer Recall

## Overview

This slice measures how many known defects each code-review config finds. It adds three layers:

1. **Planted-defect cases** (`sq benchmark recall build`). A candidate is a real commit from the project's history. Defects are planted by mutation operators applied to source lines that commit added. A defect is kept only if a test that passes on the clean commit fails with that defect alone, in every verification run. Each defect records its location, its operator, a category from 402's `ReviewCategory`, the test or tests that prove it, and the enclosing symbols. A case holds up to N defects, spaced so that a one-line finding cannot be near two of them.
2. **Recall runs** (`sq benchmark recall run`). Each reviewer config reviews each case's defected diff K times. The review is 425's grading review call, imported: the `code` template, no tools, the diff injected, and rules from the case tree. Records hold the normalized findings, not match results.
3. **Matching and the report** (`sq benchmark recall report`). A deterministic matcher pairs findings with defects by file and line window, or by an anchor on an enclosing symbol. The report shows recall per config with a case-bootstrap interval, paired comparisons between configs, recall per category and per operator, category agreement, and findings that matched no defect, all with n.

When recall data exists for 425's grading reviewer, 425's report shows that recall in place of its unmeasured-reviewer flag.

## Value

Developer value. Code-review model choice is set by habit today, and code review is one of the two places most of the money goes. This slice gives each reviewer config a measured recall on defects shown by a test to be real, on the project's own code, under the same conditions the benchmark grader reviews in. It also tells the PM whether the grader's review-finding columns in 425 come from a reviewer that finds anything.

No model is involved in planting or matching. A defect written by one model family could be easier for that family's reviewers to see, and an LLM matcher would be one more unmeasured instrument. Building cases costs no LLM spend.

## Technical Scope

**Included**

- `RecallAdapter` protocol and `PythonRecallAdapter`: mutation sites on added source lines, textual application of an operator, enclosing symbols, and test selection by static import closure.
- The mutation operator table (D3).
- Candidate discovery from commits, defect planting, verification, and `RecallCase` records with a `RecallBuild` record listing every rejection with its reason.
- Case sets of recall cases, through 421's `CaseSet`.
- The recall runner: plan, dollar bound, run-level cap, lock and resume.
- The matcher (D6), as a pure function, versioned.
- Recall statistics and the report.
- `latest_recall_for(reviewer_key)` and the change to 425's `review_flag`.
- CLI `sq benchmark recall build | run | report | show`, with matching `/sq:benchmark recall` subcommands.
- Config keys for the build limits.

**Excluded**

- Hand-written or LLM-written defects (D2).
- Defects no test can show: documentation drift, consistency, architecture and most performance defects. Recall is measured only for the categories the operator table covers, and the report says so.
- Reviews with tools. Recall is measured under the no-tools condition 425 grades with. A reviewer used with tools in `sq review code` runs under different conditions, and this recall does not describe it.
- A clean-diff control review (the same diff reviewed without defects).
- Languages other than Python (Future Work 1).

## Dependencies

### Prerequisites

- **421:** `HistoryFreeSandbox`, `BenchmarkSandbox`, `EnvironmentIdentity`, `ScrubbedEnvironment` with `CredentialGrant.none()`, `run_suite` with `SuiteSelection.nodes(...)`, `NodeResult`, `FailureKind`, the adapter registry keyed by `SourceLanguage`, 421 D11's project-source rule, `CaseSet` and `BenchmarkRecordStore`, and `benchmark.suite_timeout_s`.
- **425:** `ReviewerRef` with `reviewer_key`, `review_tree_diff`, `bootstrap_mean_interval`, `MIN_PAIRED_CASES` and `review_flag` (D9, D11).
- **402:** `normalize_result_categories`, `ReviewCategory` and `CodeReviewFinding`.
- **917 / review parsers:** `location_path` and `location_span` (`review/parsers.py`), so a finding's location is read the same way the rest of squadron reads it.
- **300:** the `code` review template and `run_review_with_profile`, whose `ReviewResult.effort` is the effort actually sent (931 D4).
- **420:** effort sent on the review path. The reviewer key uses it (D8).
- **External:** `git` and `uv`, as for 421.

427 does not depend on 422, 424 or 426.

### Interfaces Required

- `ProcessRunner`, for `git log`, `git show` and `git diff` in the user's checkout, and `git apply` and `git commit` in the sandbox.
- `resolve_rules_dir` and `load_rules_content` (`review/rules.py`), pointed at the sandbox tree.
- Model alias resolution (`models.toml`).
- `derive_project_id`, to key cases and check `--repo`.

## Architecture

### Component Structure

```
src/squadron/
  benchmark/
    recall_adapter.py        RecallAdapter protocol, MutationSite, PlantedEdit
    python_recall.py         PythonRecallAdapter: ast sites, textual apply, symbols, import closure
    mutation_operators.py    MutationOperator table: id, category, description
    recall_build.py          discovery, planting, verification, RecallCase / RecallBuild
    recall_runner.py         plan, bound, cap, lock, resume
    recall_match.py          match(findings, defects) -> MatchResult; MATCHER_VERSION, RECALL_LINE_WINDOW
    recall_report.py         RecallReport model assembled from records
    registry.py              + recall adapters
  metrology/
    benchmark_models.py      + RecallCase, PlantedDefect, RecallBuild, RecallRun, RecallReview
    benchmark_store.py       + recall record methods; write_case_set accepts recall case ids
  cli/commands/
    benchmark_recall.py      `sq benchmark recall …` (registered on the benchmark group)
commands/sq/benchmark.md     + recall subcommands
```

`recall_build` reaches Python only through the `RecallAdapter` registry. `recall_match` and the statistics are pure, with no I/O, store or model. `recall_runner` reaches the reviewer only through `review_tree_diff`. Each module stays under 300 lines.

### Data Flow

**Building cases** (`sq benchmark recall build --set recall`):

```
git log --no-merges HEAD (newest first), up to --limit candidates
for commit C with parent P:
   added source lines (421 D11 rule)  → none: reject no_source_change
   diff lines > max                   → reject diff_too_large
   added source lines < min           → reject too_few_added_lines
   BenchmarkSandbox(C)                → EnvironmentIdentity | reject environment_failed (reason)
   adapter.mutation_sites(added lines)→ none: reject no_mutation_sites
   baseline: run_suite(all_tests()) × verify_runs → passing set S (a node passing in every run)
       timed out | SuiteRunError      → reject baseline_failed
   sites in seeded order (seed from C), spaced (D4):
       mutated source → ast.parse fails: skip site
       select = nodes in S whose test file's import closure reaches the mutated module
       select empty → skip site (no_selected_tests)
       run_suite(nodes(select)) with the mutation, × verify_runs
       timed out | SuiteRunError → skip site, end this commit's attempts (D4)
       proving = nodes failing with assertion_failure | project_exception in every run
       proving empty → skip site; else keep defect; restore file
       stop at defects_per_case kept, or max attempts
   kept 0 → reject no_verified_defect; else write RecallCase
write case set (421 D2) and one RecallBuild record (candidates, kept, rejections by reason)
```

**Running** (`sq benchmark recall run --set recall --review-model A --review-model B --samples 3 --max-cost 8`):

```
load set, cases; resolve reviewers → ReviewerRef each
refuse: missing --max-cost | fewer than 2 samples | no per-review cost figure | case project without --repo
plan: (case, reviewer, sample) with no RecallReview record
print bound ─── nothing dispatched before this line
take run lock
for case: HistoryFreeSandbox(P); git apply (P..C diff + planted edits); commit as the benchmark identity
   any of the three fails → absence case_setup_failed for each planned review of the case
   for sample, then reviewer:  spent ≥ cap → stop, exit 2
       review_tree_diff(tree, P, reviewer) → findings | absence review_failed
       write RecallReview
```

**Reporting:** read the run, its cases and reviews, call `match` on each review, reduce per case, bootstrap over cases.

### State Management

- **Store records** (persistent, optional sibling payloads on `MetrologyRecord`, no migration): `recall_case` (one per case), `recall_build` (one per build), `recall_run` (one per run), `recall_review` (one per case × reviewer × sample).
- **Match results** are not stored. They are recomputed from findings and defects at report time, so a matcher change needs no new review.
- **Sandboxes** (transient): 421's directories under `~/.config/squadron/benchmark/`, one per candidate during build and one per case during a run, removed unless `--keep` is given.
- **Run lock:** `<benchmark root>/<recall_run_id>.lock`, 421's process lock.

## Technical Decisions

### D1 — Source diffs are single commits from history
Status: decided
- A candidate is a non-merge commit reachable from `HEAD` that adds project source lines (421 D11's rule: under the tree, not `.venv`, not a test module). The reviewed diff is `P..C` with the planted edits on top.
- Bounds, declared in `config/keys.py` with these defaults: `benchmark.recall_max_diff_lines` (400) and `benchmark.recall_min_added_source_lines` (10). The upper bound keeps review cost near a grading review of one fix. The lower bound needs enough added code to hold several spaced defects.
- Rejected: 400's slice ranges. They are too large for one no-tools review. Rejected: 422's fix cases. Using them would make 427 depend on 422 for no gain, since any commit will do.

### D2 — Defects are planted by mutation operators, not written
Status: decided
- Operators are applied mechanically to added source lines. No model takes part, so ground truth carries no planter bias and building cases costs no LLM spend. The architecture's other two options are rejected: hand-written defects make a curated dataset (300's non-goal) and need per-case human work (420's non-goal), and LLM-written defects tie ground truth to one model family.
- The cost is coverage: operators plant correctness and error-handling defects only. The report states the categories it measured (D3).

### D3 — The operator table
Status: decided
- Defined once in `mutation_operators.py`. Each operator has an id, a `ReviewCategory` and a one-line description:

| id | change | category |
|---|---|---|
| `compare-boundary` | `<` ↔ `<=`, `>` ↔ `>=` | correctness |
| `compare-negate` | `==` ↔ `!=`, `in` ↔ `not in`, `is` ↔ `is not` | correctness |
| `bool-swap` | `and` ↔ `or` | correctness |
| `condition-negate` | `if c:` / `while c:` → `if not c:` | correctness |
| `offset-drop` | `x + 1` / `x - 1` → `x` | correctness |
| `return-none` | `return <expr>` → `return None`, where expr is not `None` | correctness |
| `call-drop` | delete a statement that is only a call | correctness |
| `guard-drop` | delete an `if` whose body is only `raise` or `return` | error-handling-observability |
| `reraise-swallow` | a `raise` inside an `except` body → `pass` | error-handling-observability |

- An operator never applies where the change would leave an empty body. `MUTATION_TABLE_VERSION` is an int constant, bumped on any change, and recorded on every case.

### D4 — Planting and verification
Status: decided
- **Textual edits.** A site is an ast node on an added line. Its edit replaces exactly the node's source segment (`lineno`, `col_offset`, `end_lineno`, `end_col_offset`), or deletes whole lines for `call-drop` and `guard-drop`. The file is never re-emitted with `ast.unparse`, which would reformat it and give the defect away. The mutated file must still parse.
- **Deletion span.** A deletion records `line_start = line_end =` the line that now holds the text after the deleted lines, in defected-tree numbering, which is the line where the deleted text began.
- **Order.** Sites are visited in an order shuffled with a seed taken from the commit sha, so a rebuild gives the same case and defects are not always the commit's first lines.
- **Spacing.** A kept defect blocks every site in the same file within `2 × RECALL_LINE_WINDOW + 1` lines of it, so a one-line finding is never in the window of two defects. Wider spans and shared anchors can still reach two, which D6 handles. `RECALL_LINE_WINDOW` comes from `recall_match.py`.
- **Test selection** is for speed only. It is the baseline-passing nodes whose test file's static import closure (ast imports, followed through project modules) reaches the mutated module. A selection that misses a test can only reject a real defect. It never admits a false one, because the proving test is actually run.
- **Proof.** Over `benchmark.recall_verify_runs` runs (default 2): the proving nodes pass on the clean commit in every baseline run and fail with the defect alone in every run, with `FailureKind` `assertion_failure` or `project_exception`. A defect whose only failures are `collection_error` or `missing_symbol` breaks the import, which a reviewer would not need to read code to see, so it is skipped.
- **Hangs.** A mutation can make code loop forever (`condition-negate` on a `while`, `call-drop` of a loop's advancing call). A mutation run that times out or raises `SuiteRunError` skips the site with no further runs and ends the commit's attempts, so each commit spends at most one suite timeout on a hang. If no defect was kept by then, the commit is rejected `mutant_timeout`.
- **Limits.** `benchmark.recall_defects_per_case` (default 3) and `benchmark.recall_max_attempts_per_commit` (default 20), both declared in `config/keys.py`.
- Each defect is verified alone. All of a case's edits together must apply cleanly (spacing makes them disjoint). Defects are not verified in combination, because their tests only prove each defect is real, and matching never runs tests.

### D5 — Case content identity
Status: decided
- `RecallCase` identity fields: `project_id`, `parent_sha`, `commit_sha`, `defects` (sorted by path and line), `mutation_table_version`. `case_id` is `rcase-` followed by the first 16 hex digits of the sha256 of the canonical JSON of those fields, validated on read like 421 D1.
- Provenance (`created_at`, the environment identity digest it was verified under, the build id) is stored but is not identity.
- A recall case set is a 421 `CaseSet`. `write_case_set` accepts ids of either `benchmark_case` or `recall_case` records, and a set must hold one kind only. A mixed list raises `MetrologyStoreError` naming both kinds.

### D6 — The matching rule
Status: decided
- Only findings with severity `NOTE`, `CONCERN` or `FAIL` take part. `PASS` findings are not defect claims and are not counted anywhere.
- **Path:** `location_path(location)`, then normalized: a leading `./`, `a/` or `b/` is stripped, and an absolute path under the tree is made relative to it.
- **A finding matches a defect** when the paths are equal and either:
  - `location_span(location)` overlaps `[line_start − W, line_end + W]` with `W = RECALL_LINE_WINDOW = 3`, in the defected tree's line numbers, or
  - the location is a `path#name` anchor and `name` equals the defect's enclosing function or class name, by bare name or dotted qualified name. Enclosing symbols are recorded on the defect when it is planted.
- **A finding claims at most one defect.** Of the defects it reaches that are not yet found in this review, a line span claims the nearest (smallest line gap, ties to the lower `defect_id`) and an anchor claims the first in `defect_id` order. So one broad finding never credits more than one defect, and several findings on one function can each credit one.
- Category is not part of the match. A reviewer that finds the bug and names it `error-handling-observability` instead of `correctness` has still found it. Category agreement is reported as its own column.
- **Outcomes per review:** findings are taken in finding order. Each defect is `found` or `missed`. Each counted finding is `matched` (it claimed a defect not yet found), `duplicate` (every defect it reaches is already found), `unlocated` (no path, or a path with neither a line nor an anchor) or `unmatched` (located, reaching no defect).
- Unmatched findings are not called false positives. The original commit can hold real issues.
- `MATCHER_VERSION` is an int constant. The report prints it. A change to W, to the anchor or claim rule, or to the counted severities bumps it.
- Rejected: a judge call per finding. It adds an unmeasured LLM to the measurement. Rejected: requiring category agreement for a match. That would measure labelling, not finding.

### D7 — Recall statistics
Status: decided
- Per review: found fraction = found defects / case defects. Per (case, config): `r(c)` is the mean over its K samples. Per config: recall is the mean of `r(c)` over cases, with a 95% percentile bootstrap interval over cases. The case is the unit, as in 425.
- Pairs of configs: `d(c) = r_A(c) − r_B(c)`, the paired bootstrap and the verdicts of 425 D14 (`a_ahead`, `b_ahead`, `not_distinguishable`, `too_few_cases` below `MIN_PAIRED_CASES`).
- Pooled counts (defects found over defects × samples) are shown beside the mean as raw numbers, not as a second recall.
- Breakdowns: recall per category and per operator (pooled, with n defects), category agreement (matched findings whose category equals the defect's, over matched), and duplicate, unlocated and unmatched findings per review.
- No composite of recall and unmatched counts is computed.

### D8 — Reviewer identity
Status: decided
- A reviewer is resolved from an alias to `ReviewerRef(alias, model, profile, effort, template_hash, rules_hash)`, the type 425 defines. `effort` is resolved before dispatch, as 425 does: the alias's effort when the profile's provider applies effort, else `None` (the rule `review_client` uses for the effort it sends). The bound, the run id and resume therefore need no review to have run. A review whose `ReviewResult.effort` differs from the resolved value is the absence `review_failed`, with both values in `detail`.
- `ReviewerRef.reviewer_key` is 425's derived field: the sha256 of `model`, `profile`, `effort` and `template_hash`, with `effort` `None` hashed as JSON `null`. Recall records and the 425 lookup use it. The alias is excluded because aliases are renamed. `rules_hash` is excluded because rules come from each case's tree, so it differs per project and per commit. It describes the case, not the reviewer.

### D9 — Pieces imported from 425
Status: decided
- 425 is a prerequisite. 427 imports three pieces from it and defines no copy, or recall would not describe the grading reviewer:
  1. `ReviewerRef` with `reviewer_key` (425's storage schema).
  2. `review_tree_diff(tree, base_sha, reviewer) -> ReviewOutcome` in `benchmark/grade_review.py` (425 D7).
  3. `bootstrap_mean_interval` and `MIN_PAIRED_CASES` in `benchmark/paired_stats.py` (425 D14).
- Raising, or returning verdict `UNKNOWN` with no findings, is the harness absence `review_failed`, as in 425 D7.

### D10 — Caps, bound and resume
Status: decided
- `run` requires `--max-cost USD` and refuses without it. Build dispatches no model and has no cap.
- The per-review figure is the largest observed review cost for the same `reviewer_key` in the store (recall reviews and 425 grades), or `--review-cost USD`. With neither, `run` refuses and names the flag.
- The bound prints before the first review: reviews planned × figure, capped at the run cap, plus one review of overshoot. The figure is an estimate and no per-review cap exists, as 425 says, and the bound says so. The cap is checked before each review. Hitting it stops, keeps every record and exits 2.
- `recall_run_id` is `recall-` followed by the first 12 hex digits of the sha256 of the set name, set version, sorted reviewer keys and K. Rerunning the same command resumes: planned reviews that already have a record are skipped. `--retry-harness` deletes harness-absent reviews first and reports how many, as 425 D9 does.
- Absences: `case_setup_failed` and `review_failed` are the `RecallAbsence` values. An absence on any sample removes the case from every config's comparison, and the report counts each absence per config, so a reviewer that fails often stays visible.
- A run stopped at its cap is `partial`. Its report uses only cases with all K samples recorded for every config, as the architecture states for partial runs.

### D11 — 425 reads recall
Status: decided
- `BenchmarkRecordStore.latest_recall_for(reviewer_key) -> RecallSummary | None` returns the most recent recall run that includes the key, with recall, its interval, n cases, K, set name and version, and matcher version. Runs with fewer than `MIN_PAIRED_CASES` compared cases are skipped.
- 427 changes 425's `review_flag(reviewer) -> str` alone. When a summary exists it returns `reviewer recall 0.62 [0.48, 0.75] (n=12, k=3, set recall v1, no tools)`, which the review-findings heading shows in place of the flag. Without a summary, it returns the flag as 425 wrote it.

### Technology Choices

- Python's `ast` for sites, segments and import closures. No mutation-testing library: mutmut and cosmic-ray rewrite files and run their own test loops, and neither gives segment-exact edits on chosen lines with 421's per-node classification.
- No new dependencies.

### Patterns and Conventions

- `RecallRejection` (`no_source_change`, `diff_too_large`, `too_few_added_lines`, `environment_failed`, `baseline_failed`, `no_mutation_sites`, `mutant_timeout`, `no_verified_defect`), `RecallAbsence`, `DefectOutcome` and `FindingOutcome` are `StrEnum`s in `benchmark_models.py`. Reports group by enum values.
- Every collaborator of `recall_build` and `recall_runner` is injected (sandbox factory, adapter registry, reviewer, store, clock). Tests run no model.
- `RecallAdapter` is its own protocol, registered by `SourceLanguage`, as 422 and 425 do with theirs.

## Implementation Details

### API Contracts

```python
class RecallAdapter(Protocol):
    language: SourceLanguage
    def mutation_sites(self, path: str, source: str, added_lines: frozenset[int]) -> Sequence[MutationSite]: ...
    def apply(self, source: str, site: MutationSite) -> PlantedEdit: ...   # new source + edit span
    def enclosing_symbols(self, source: str, line: int) -> tuple[str, ...]: ...
    def tests_reaching(self, tree: Path, module_path: str, candidates: Sequence[str]) -> tuple[str, ...]: ...
```

**`sq benchmark recall build [--set NAME] [--limit N] [--keep]`** runs in the current repository. It prints one line per candidate (`a1b2c3d kept 3 defects` or `rejected no_mutation_sites`), then counts by reason and the case set version written. `--set` defaults to `recall`, defined once as `DEFAULT_RECALL_SET` in `recall_build.py`.

**`sq benchmark recall run --set NAME --review-model ALIAS [--review-model ALIAS …] --samples K --max-cost USD [--review-cost USD] [--repo PATH …] [--retry-harness] [--keep]`** prints the bound, one line per review (`rcase-… gpt-review s2 found 2/3 · unmatched 4`), then a summary. Exit 0 complete, 2 cap reached, 1 refusal.

**`sq benchmark recall report [RUN_ID] [--json]`**, latest run when omitted:

```
recall run recall-8d2e…  set recall v1  matcher v1 (window ±3)  no tools
cases 14 · compared 13 · dropped 1 (case_setup_failed) · defects 37 · k 3
measured categories: correctness, error-handling-observability

reviewer                         recall   95% interval    found/total   cat. agree
  gpt-review (openai-oauth, med)  0.61    [0.47, 0.74]     68/111        0.71
  opus-review (sdk, high)         0.74    [0.62, 0.85]     82/111        0.80

paired: opus-review − gpt-review   +0.13  [+0.02, +0.24]  a ahead

by operator           n   gpt-review   opus-review
  compare-boundary    9     0.44          0.63
  …

findings per review   unmatched   duplicate   unlocated
  gpt-review          3.1         0.4         0.3
  …
```

**`sq benchmark recall show CASE_ID`** prints the case's commit, each defect (path, lines, operator, category, original and mutated text, proving nodes) and the defected diff. It prints the answers, and it says so in its header.

`/sq:benchmark recall` mirrors all four subcommands with the same arguments and output. `--json` emits the `RecallReport` model.

### Database / Storage Schema

```python
class PlantedDefect(BaseModel, frozen=True):
    defect_id: str                     # d1, d2 … in path/line order
    path: str
    line_start: int                    # in the defected tree
    line_end: int
    operator: str                      # id from the operator table
    category: ReviewCategory
    original: str
    mutated: str
    enclosing_symbols: tuple[str, ...]
    proving_tests: tuple[str, ...]     # node ids

class RecallCase(BaseModel, frozen=True):
    case_id: str                       # derived, validated (D5)
    project_id: ProjectId
    parent_sha: str
    commit_sha: str
    defects: tuple[PlantedDefect, ...]
    mutation_table_version: int
    provenance: RecallProvenance       # not identity: environment digest, build id, created_at

class RecallBuild(BaseModel, frozen=True):
    build_id: str
    project_id: ProjectId
    case_set: str
    case_set_version: int
    candidates: int
    kept: tuple[str, ...]              # case ids
    rejections: tuple[tuple[str, RecallRejection], ...]   # (commit sha, reason)
    created_at: datetime

class RecallRun(BaseModel, frozen=True):
    run_id: str
    case_set: str
    case_set_version: int
    reviewers: tuple[ReviewerRef, ...]
    samples: int
    max_cost_usd: float
    state: Literal["running", "complete", "partial", "interrupted"]
    created_at: datetime

class RecallReview(BaseModel, frozen=True):
    run_id: str
    case_id: str
    reviewer_key: str
    sample: int
    findings: tuple[CodeReviewFinding, ...]   # normalized, inline (short)
    unnormalized_count: int
    absence: RecallAbsence | None
    detail: str | None
    cost_usd: float | None
    wall_seconds: float
    created_at: datetime
```

Review record id: `rreview-<run_id[7:]>-<case_id[6:18]>-<reviewer_key[:8]>-s<sample>`. `BenchmarkRecordStore` gains `write_recall_case`, `get_recall_case`, `list_recall_cases(project_id)`, `write_recall_build`, `write_recall_run`, `get_recall_run`, `latest_recall_run`, `write_recall_review`, `reviews_for(run_id)`, `delete_recall_reviews(ids)` (for `--retry-harness` only) and `latest_recall_for(reviewer_key)`.

## Integration Points

### Provides to Other Slices

- **425:** `latest_recall_for(reviewer_key)` and `review_flag` reading it (D11).

### Consumes from Other Slices

- **421:** sandboxes, environment identity, suite runner and classification, the project-source rule, `CaseSet`, and the store. `write_case_set` accepts recall case ids (D5). No other 421 decision changes.
- **402 / 917:** normalization and location parsing, read only.
- **300:** the `code` template and review call, unchanged.

## Success Criteria

### Functional Requirements

- `sq benchmark recall build` on squadron writes recall cases and a `RecallBuild` record. Every candidate is either kept or listed with a `RecallRejection`.
- Every planted defect has path, lines, operator, a `ReviewCategory` and at least one proving node that passes on the clean commit and fails with the defect alone in every verification run. A rebuild from the same commits gives the same case ids.
- No two defects in a case are within `2 × RECALL_LINE_WINDOW + 1` lines of each other in one file. The defected diff differs from `P..C` only on the planted lines.
- The matcher has tests for: a span inside the window, a span just outside it, a `path#function` anchor, a bare path (unlocated), `a/` and `./` prefixes, an absolute path under the tree, a `PASS` finding (not counted), a duplicate, a category mismatch that still matches, a multi-line span reaching two defects (claims the nearest), an anchor shared by two defects (one finding claims one; a second claims the other), and a deletion defect's zero-width span.
- `recall run` without `--max-cost`, with K < 2, or with no per-review figure refuses and names what is missing. The bound prints before the first review. Hitting the cap exits 2 and keeps records. A rerun skips completed reviews.
- The report gives recall with an interval, found and total counts, and unmatched, duplicate and unlocated counts per reviewer config, with n cases, n defects and K. It lists the measured categories and the matcher version. A pair of configs gets a paired verdict.
- 425's report shows the grading reviewer's recall when `latest_recall_for` returns a summary, and the unmeasured-reviewer flag when it does not.

### Technical Requirements

- `ruff format`, `ruff check` and `pyright` (zero errors) are clean.
- Each operator has tests that apply it to a fixture source and check that only the node's segment changed and that the result parses. Operator tests include sites from real squadron source files.
- Verification tests run real pytest against fixture projects under `tests/benchmark/fixtures/`: a defect proved by an assertion, one proved by a project exception, one rejected because only the import fails, one rejected because no selected test fails, and one rejected because its test is flaky.
- `recall_match` and the statistics are pure, with tests against hand-computed values.
- Every `RecallAbsence` and `RecallRejection` is produced by a test double for its condition.

### Integration Requirements

- 427 changes 425's `review_flag` to read `latest_recall_for`, with no other change to 425's report code.
- `tests/benchmark/` and `tests/metrology/` pass, with 421's set tests extended for recall ids and mixed-kind rejection.

### Verification Walkthrough

These are draft commands. `sq benchmark recall` does not exist until this slice is implemented. Both review aliases must answer yes in `sq benchmark auth-check`.

1. **Build cases from squadron's history.**
   ```bash
   sq benchmark recall build --limit 40
   ```
   One line per candidate, kept with a defect count or rejected with a reason, then counts by reason and `case set recall v1`. Running it again prints the same case ids and leaves the set at v1.

2. **Inspect a case.**
   ```bash
   sq benchmark recall show <rcase-id>
   ```
   Each defect shows its operator, category, original and mutated text, and proving nodes. Check one by hand in a kept sandbox:
   ```bash
   sq benchmark recall build --limit 1 --keep
   ```
   In the kept tree, apply one defect's edit and run `.venv/bin/python -m pytest <proving node>`. It fails. Revert the edit, and it passes.

3. **Run two reviewers.**
   ```bash
   sq benchmark recall run --set recall --review-model gpt-review --review-model opus-review \
     --samples 3 --max-cost 8 --review-cost 0.20
   ```
   The bound prints first. Each line shows found/defects and unmatched for one review.

4. **The report.**
   ```bash
   sq benchmark recall report
   ```
   Recall with an interval per reviewer, the paired verdict, recall by operator, and the per-review finding counts, with n and K. The header names the measured categories and the matcher version.

5. **425 reads it.** Set `benchmark.grading_review_model` to one of the aliases from step 3 and run `sq benchmark report <bench-id>` on a graded benchmark (425). The review-findings heading shows that reviewer's recall instead of `unmeasured reviewer`. With an alias that has no recall run, the flag is shown.

6. **Cap and resume.** `sq benchmark recall run … --max-cost 0.30` stops after the review that crosses the cap and exits 2. The same command with `--max-cost 8` skips completed reviews and finishes.

7. **Matcher tests.** `uv run pytest tests/benchmark/test_recall_match.py -v` covers every case in the matcher criterion above.

## Risk Assessment

### Technical Risks

- **Operator defects may be easier or harder to see than real ones.** A flipped comparison in a short diff can be easy to spot. A deleted call can be hard to spot. Recall here measures these operators, not defects in general.
- **Yield.** Many squadron source lines are reached only through CLI tests that patch internals, or through no test at all, so many sites will have no proving test.

### Mitigation Strategies

- The per-operator breakdown shows which kinds a reviewer finds, so an operator that every reviewer finds, or that none does, is visible and can be changed with a `MUTATION_TABLE_VERSION` bump.
- The build report counts rejections per reason. If yield is low, `--limit` widens the commit range, and builds can run on other cf projects into the same set name, since each case carries its own `project_id`.

## Implementation Notes

### Development Approach

1. Operator table and `PythonRecallAdapter` sites and textual apply, tested on real squadron source.
2. Records, case identity, store methods and the `write_case_set` extension.
3. Import-closure test selection and verification against fixture projects.
4. `recall_build` and `sq benchmark recall build` and `show`. Build on squadron and check two defects by hand (walkthrough step 2).
5. `recall_match` and the statistics, pure, on 425's bootstrap.
6. `recall_runner`: plan, bound, cap, lock, resume.
8. `recall_report`, the CLI and slash command, then `latest_recall_for` and `review_flag` (D11). Run the walkthrough.

Effort: 3/5.

### Special Considerations

- The reviewer runs with no tools, with the diff and file contents injected, so it cannot read the user's checkout, where the clean commit is. The defected commit is made as the benchmark identity with a fixed message, so the commit message cannot hint at the defects.
- `show` and `--keep` expose the answers. Nothing in the review path reads them.
- Building runs project tests from history in 421's scrubbed environment with no credentials. Installs run in the harness environment (421 D5).
