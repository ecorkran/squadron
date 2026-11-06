---
docType: tasks
slice: reviewer-recall
project: squadron
lld: user/slices/427-slice.reviewer-recall.md
dependencies:
- 300
- 400
- 402
- 420
- 421
- 424
- 425
- 917
projectState: Slices 420–426 have tasks written, not implemented (src/squadron/benchmark
  does not exist at the time of writing). Slice 427 design written. main is the target
  unless cf config get git.integration_branch says otherwise.
dateCreated: 20261106
dateUpdated: 20261106
status: not_started
turns: 22
promptTokens: 1532607
cachedTokens: 1411717
cacheWriteTokens: 120856
completionTokens: 36491
durationSeconds: 258.1
costUsd: 0.989891
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.9898907
    completionTokens: 36491
---

## Context Summary
- Working on slice 427: `sq benchmark recall build | run | report | show`. Design: `user/slices/427-slice.reviewer-recall.md`; its D-numbers (D1–D11) are cited below instead of repeating them.
- Order: branch and design corrections (Task 1); config keys, operators, adapter seam, edit engine and the Python adapter (Tasks 2–8), which need nothing from 421–425; the precondition gate, source-path check and adapter registration (Task 9); records and store (Tasks 10–11); fixtures and verification (Tasks 12–13); planting, discovery and build (Tasks 14–17); materializer and `build`/`show` commands (Tasks 18–19); a live build (Task 20); matcher and statistics (Tasks 21–23); runner and `run` (Tasks 24–28); report, `latest_recall_for` and `review_flag` (Tasks 29–32); slash commands (Task 33); walkthrough (Task 34); final validation (Task 35).
- **Preconditions (Task 9):** Tasks 2–8 touch only config code, pure modules and the adapter, and are committed before the gate. Tasks 10 onward need names 421–425 create. At the time of writing those names do not exist, so Task 9 stops with `BLOCKED:` and Tasks 10 onward wait. Every 421–425 name below is the name those task files give; read the real module before using one, and if a name differs use the real one and say so in the DEVLOG entry.
- Design gaps found while reading the sibling task files (Task 1 writes each into the design; these tasks follow the corrections):
  - **`ReviewerRef` has no `rules_hash` (D8).** 425 Task 7 drops it (the rules directory differs per case); the outcome carries it. D8 loses `rules_hash` from the tuple. `resolve_reviewer(alias)` (`benchmark/grade_review.py`, 425) builds the ref; 427 does not rebuild it. 425's design still lists `rules_hash`; 425's own Task 1 corrects it, so 427 does not edit 425's design.
  - **`review_tree_diff` raises (D9).** 425 Task 21 raises `ReviewFailed` for a raise, timeout or `UNKNOWN`-empty result. The runner catches it and records the absence `review_failed`.
  - **Source-path predicate (Data Flow, API Contracts).** "Added source lines (421 D11 rule)" is language-specific and `recall_build` may touch Python only through the adapter, so `RecallAdapter` gains `is_source_path(path) -> bool`, delegating to 421's project-source rule, and the Python adapter is registered in 421's adapter registry (Task 9).
  - **Edit coordinates (D4).** `edit_span` columns are ast `col_offset` values, which count UTF-8 bytes. Edits are applied on the encoded line bytes, so a non-ASCII line is not mis-cut. Applying edits and deriving defected-tree lines is language-independent and used by build and run: new `benchmark/recall_edits.py` (Task 5).
  - **Diff size (D1).** "Diff lines" is added plus removed lines from `git diff --numstat P C` (binary files count 0), compared with `benchmark.recall_max_diff_lines`.
  - **Shared materializer (Data Flow).** `run` and `show` both build the defected tree: new `benchmark/recall_materialize.py` (history-free tree at P, apply the `P..C` diff, apply the stored edits, commit as the benchmark identity with a fixed message). `show` uses it so its diff is the one a reviewer sees (Task 18).
  - **Home for models and store (Component Structure).** `benchmark_models.py` and `benchmark_store.py` are shared and near the ~300-line limit, so the recall models go in `metrology/recall_models.py` and the recall record methods in `metrology/recall_store.py` (`RecallRecordStore`); only `write_case_set` is edited in `benchmark_store.py` (Tasks 10–11).
  - **New modules and their homes (Component Structure).** Split up front so none passes ~300 lines. In `benchmark/`: `recall_edits.py`, `recall_materialize.py`, `recall_discovery.py`, `recall_verify.py`, `recall_plant.py`, `recall_plan.py`, `recall_stats.py`, `recall_run_state.py` (lock, interruption), `recall_summary.py` (`RecallSummary`, `latest_recall_for`), `recall_report_render.py`, `python_recall_expr.py`, `python_recall_stmt.py`, `python_recall_closure.py`; `recall_build.py` keeps orchestration, `recall_runner.py` the run loop, `recall_report.py` the report model and `python_recall.py` the adapter class. In `cli/commands/`: `benchmark_recall.py` (build, show) and `benchmark_recall_run.py` (run, report). In `metrology/`: `recall_models.py`, `recall_store.py`. Task 1 rewrites Component Structure to list exactly these.
  - **Spacing (D4, Success Criteria).** Spacing is measured in defected-tree lines, the numbers the matcher uses, not original lines: a line-removing defect shifts every defect below it and is zero width in its own numbering. A site is accepted only if, with it added to the kept set, every adjacent pair of defects in a file is at least `2 × RECALL_LINE_WINDOW + 1` lines apart (next `line_start` minus previous `line_end`). At that gap no one-line finding's window `[line − W, line + W]` reaches both.
  - **Case identity (D5, Database Schema).** Identity covers each defect's `path`, `edit_span` and replacement only. Proving tests, lines and symbols can differ between builds of one commit and must not change the id. `PlantedDefect.mutated` is the replacement text (empty for a deletion).
  - **Anchor parsing (D6).** `review/parsers.py` reads a location's path (`location_path`) and lines (`location_span`) but not a `path#name` anchor's name; Task 21 adds `location_anchor` beside them so the matcher never parses locations itself.
  - **Operator spans (D4).** An operator token is not an ast node, so its span comes from `tokenize` over the text between its operands (Task 6), never from searching the line.
  - **`--limit` default (API Contracts).** The design gives `recall build --limit` no default. It becomes `benchmark.recall_candidate_limit` (positive int, default 40, the value the walkthrough uses), declared with the other recall keys (Task 2); the flag overrides it.
  - **`review_flag` needs a store (D11).** 425 Task 38 gives `review_flag(reviewer)` no store. It becomes `review_flag(reviewer, records)`; the one call site in 425's report passes the store it already holds (Task 31). The literal text stays in one file.
  - **Seeds (D11).** The interval seed for a config is the first 8 bytes of the sha256 of `run_id` and `reviewer_key` (never `hash()`); pairs use 425's `pair_seed` with the recall run id in place of a benchmark id.
- Shared names (defined once): `RecallRejection`, `RecallAbsence`, `DefectOutcome`, `FindingOutcome` StrEnums only in `recall_models.py` (Task 10); `MATCHER_VERSION`, `RECALL_LINE_WINDOW` only in `recall_match.py`; `MUTATION_TABLE_VERSION` and the operator ids only in `mutation_operators.py`; `DEFAULT_RECALL_SET` only in `recall_build.py`; config key names only in `config/keys.py`. Never compare against a literal.
- Failure modes (review rule): each new I/O path has a test that asserts an observable signal (a log at WARNING or above plus a recorded outcome): a failing `git` call in discovery; a sandbox or baseline failure (rejection); a mutant hang (rejection `mutant_timeout`); a failing `git apply` or commit in the materializer (`case_setup_failed`); a review that raises, times out or returns `UNKNOWN` (`review_failed`); a store write failure; the run lock held; a run stopped by the cap (exit 2, records kept).
- Load test: none added. Build and run are sequential, one sandbox at a time, and reuse 421's sandbox, which 421's concurrency test covers; every external call is bounded by 421's suite timeout or 425's review timeout.
- Pyright covers `src` only (`[tool.pyright] include`), so tests are held to `ruff` and a passing run, and every source module to zero pyright errors.
- Tests live in `tests/benchmark/`, `tests/metrology/`, `tests/config/` and `tests/cli/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Nothing here pushes or merges.
- Effort 3/5. Next planned slice: none after 427 in the 420 plan.

## Tasks

### Task 1: Create the slice branch and correct the design
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file as modified or untracked, commit it there by path as `docs: add slice 427 tasks`; planning work commits to the target. Stage every later commit by path
  - [ ] Success: `git status --short` does not list the task file
- [ ] Edit `user/slices/427-slice.reviewer-recall.md` so it states each design-gap bullet in the Context Summary (those bullets are the spec). Then grep the design for every name a bullet changes (`rules_hash`, `review_flag(reviewer`, `2 × RECALL_LINE_WINDOW + 1`, `benchmark_models.py`, `benchmark_store.py`, `--limit`, `recall_build.py`, `recall_runner.py`, `edit_span`, `replacement`, `is_source_path`, `latest_recall_for`, `RecallSummary`, `BenchmarkRecordStore`, `RecallRecordStore`, `recall_models.py`, `recall_store.py`, `recall_summary.py`, `recall_stats.py`) and fix every remaining statement, in whichever section it is (Technical Scope, Component Structure, Data Flow, State Management, D4, D5, D6, D8, D9, D11, API Contracts, Database Schema, Success Criteria, Implementation Notes)
  - [ ] Success: each grep hit agrees with the gap bullets

**Commit**: `docs: correct slice 427 design for reviewer ref, edit coordinates, module split and review_flag store`

- [ ] `git checkout -b 427-slice.reviewer-recall <target>` (or switch to it if it exists)
  - [ ] Success: `git branch --show-current` prints the slice branch

### Task 2: Config keys (D1, D4)
- [ ] `config/keys.py`: add a recall group with a constant, a `CONFIG_KEYS` entry and a description per key (other slices add benchmark keys in the same file; keep this group together and do not depend on theirs): `benchmark.recall_max_diff_lines` (400), `benchmark.recall_min_added_source_lines` (10), `benchmark.recall_verify_runs` (2), `benchmark.recall_defects_per_case` (3), `benchmark.recall_max_attempts_per_commit` (20), `benchmark.recall_candidate_limit` (40), all positive ints read with `get_positive_int_config`
- [ ] Tests in `tests/config/test_keys.py`, in the style of its `TestCodexTimeoutConfigKeys`: each default; 0 and a negative value rejected with the error type `get_positive_int_config` raises; a set value is returned
  - [ ] Success: tests pass

**Commit**: `feat: add recall build config keys`

### Task 3: Operator table (D3)
- [ ] `benchmark/mutation_operators.py`: frozen `MutationOperator(operator_id, category: ReviewCategory, description)`, the nine operators of D3 in one `MUTATION_TABLE` tuple (categories `ReviewCategory.CORRECTNESS` and `ReviewCategory.ERROR_HANDLING_OBSERVABILITY`), `MUTATION_TABLE_VERSION = 1` with a comment that any change bumps it, one id constant per operator, and `operator_for(operator_id)` raising a named error (logged at ERROR) for an unknown id
- [ ] Tests `tests/benchmark/test_mutation_operators.py`: ids unique; every category is a `ReviewCategory`; the table has exactly the nine D3 ids; `operator_for` of an unknown id raises
  - [ ] Success: tests pass; pyright is clean

### Task 4: Adapter seam types and matcher constants (API Contracts, Patterns, D4, D6)
- [ ] `benchmark/recall_adapter.py`: frozen `MutationSite(path, operator_id, start_line, start_col, end_line, end_col)`, frozen `PlantedEdit(new_source, edit_span, replacement, original, mutated)` where `edit_span` is the 4-tuple of D4, and the `RecallAdapter` Protocol exactly as D4's API Contracts block lists it plus `is_source_path(path: str) -> bool` and `language: SourceLanguage`, declared `@runtime_checkable`
- [ ] Tests `tests/benchmark/test_recall_adapter_types.py`: the models are frozen; a stub class with every member passes `isinstance(stub, RecallAdapter)` and one missing a member does not
- [ ] `benchmark/recall_match.py`: create it with only `MATCHER_VERSION = 1` (comment: bumped on any change to `W`, the anchor or claim rule, or the counted severities) and `RECALL_LINE_WINDOW = 3`; the planter imports the window from here and Task 21 completes the module. First test in `tests/benchmark/test_recall_match.py`: both constants exist, and the window is a positive int
  - [ ] Success: tests pass; pyright is clean

### Task 5: Edit engine (D4)
- [ ] `benchmark/recall_edits.py` (pure): `apply_edits(source: str, edits: Sequence[StoredEdit]) -> str` applying edits last position to first on the UTF-8 bytes of the lines (columns are byte offsets, deletion spans run from column 0 of the first line to column 0 of the line after the last); `derive_line_ranges(edits_by_file)` returning each edit's defected-tree `(line_start, line_end)`: original start line plus the net line change of every edit above it in the same file, a deletion zero width at its start line; `StoredEdit(path, edit_span, replacement)`. Overlapping spans raise `EditOverlapError`; a result that does not `ast.parse` is the caller's concern, not this module's
- [ ] Tests `tests/benchmark/test_recall_edits.py`: a one-token replacement changes only that segment; a second `<` on the same line is untouched; a line-removing edit above another shifts the lower defect's lines by exactly the removed count and applying the stored edits to the original gives the file those lines describe; a deletion's range is zero width; a non-ASCII line before the edit column cuts at the right character; two edits in one file apply regardless of input order; overlapping edits raise
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add recall operator table, adapter seam, matcher constants and edit engine`

### Task 6: `PythonRecallAdapter` expression operators (D3, D4)
- [ ] `benchmark/python_recall.py`: `PythonRecallAdapter` with `language = SourceLanguage.PYTHON` and `mutation_sites(path, source, added_lines)`, calling the finders in `benchmark/python_recall_expr.py` (one function per operator), each yielding sites only for nodes whose lines are all in `added_lines`: `compare-boundary` (`<` `<=` `>` `>=`), `compare-negate` (`==` `!=` `in` `not in` `is` `is not`), `bool-swap` (`and` `or`), `offset-drop` (`x + 1` / `x - 1` → `x`). The site of an operator token is found by `tokenize` over the text between the end of the left operand and the start of the next operand (comments and parentheses skipped; `not in` and `is not` span both tokens). `offset-drop` replaces the whole BinOp segment with the left operand's source segment. `apply(source, site)` replaces exactly the site's segment through the Task 5 byte rules and returns a `PlantedEdit`; it never calls `ast.unparse`
- [ ] Tests `tests/benchmark/test_python_recall_expr.py`, one test per operator on a fixture source: sites only on added lines; the result differs from the input only inside the site's segment (compare the text outside the span); the result parses; a chained comparison `a < b < c` mutates one operator only; a `<` inside a comment or string between or beside the operands is never touched; a parenthesized left operand under `offset-drop`; a multi-line boolean expression keeps its line breaks
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add Python recall adapter with expression operators`

### Task 7: `PythonRecallAdapter` statement operators (D3, D4)
- [ ] In `benchmark/python_recall_stmt.py` (one function per operator, called from `PythonRecallAdapter`) add the statement finders: `condition-negate` (the `if`/`while` test's segment replaced by `not (<segment>)`, `elif` included), `return-none` (`return <expr>` where expr is not `None`), `call-drop` (a statement that is only a call; whole lines deleted), `guard-drop` (an `if` whose body is only `raise` or `return`; whole lines deleted), `reraise-swallow` (a `raise` inside an `except` body becomes `pass`). A site is never offered where the change leaves an empty body (the only statement of a block for `call-drop` and `guard-drop`), and deletions use the whole-line spans of D4
- [ ] Tests `tests/benchmark/test_python_recall_stmt.py`, one test per operator: sites only on added lines; the edit result parses; a deletion's stored span runs column 0 to column 0 of the next line with empty replacement; an operator is not offered when it would empty a body; `elif` and a `while` under `condition-negate`; a bare `raise` and `raise X from e` under `reraise-swallow`
  - [ ] Success: tests pass; pyright is clean
- [ ] Real-source coverage (Technical Requirements, Tasks 6 and 7): copy three real squadron source files with branches, comparisons, returns, `try/except` and guard clauses (for example `src/squadron/review/parsers.py`) into `tests/benchmark/fixtures/recall_sources/` and add a test that every operator of the table yields at least one site over their lines and every `apply` result parses
  - [ ] Success: the test reads those files only (never the live checkout) and passes

**Commit**: `feat: add Python recall adapter statement operators`

### Task 8: Enclosing symbols and import-closure selection (D4, D6)
- [ ] As `PythonRecallAdapter` methods in `python_recall.py`, add `enclosing_symbols(source, line) -> tuple[str, ...]`: the bare and dotted qualified names of the innermost enclosing function or class, then each outer one (a method gives `method`, `Class.method`, `Class`); an empty tuple at module level
- [ ] Tests `tests/benchmark/test_python_recall_symbols.py`: a function, a method, a nested function, a class body line and a module-level line
- [ ] Add the adapter method `tests_reaching(...)`, delegating to `benchmark/python_recall_closure.py`, with `tests_reaching(tree, module_path, candidates) -> tuple[str, ...]`: the candidate node ids whose test file's static import closure (ast `import` and `from` statements followed through project modules under the tree, including relative imports and package `__init__` files) reaches `module_path`. Unparseable files are skipped with a WARNING naming the file; a cycle terminates
- [ ] Tests `tests/benchmark/test_python_recall_closure.py` on a small tree built in `tmp_path`: a direct import, a transitive import, a relative import, a package `__init__` re-export, an import cycle, a test that imports nothing from the module (not selected), a file with a syntax error (WARNING, skipped)
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add recall enclosing symbols and import-closure selection`

### Task 9: Preconditions
- [ ] Confirm by grep in `src/squadron` that these exist. 421: `class BenchmarkSandbox` (with `tree`, `identity`, `run_suite`, `keep`), `class HistoryFreeSandbox`, `class EnvironmentIdentity`, `class SuiteSelection` (`all_tests`, `nodes`), `class SuiteRun` (`results`, `timed_out`), `class NodeResult`, `class FailureKind`, `class SuiteRunError`, `class EnvironmentResolutionError`, `class BenchmarkRecordStore` with `write_case_set`, `class CaseSet`, `class ProcessRunner`, `benchmark.suite_timeout_s`, the adapter registry in `benchmark/registry.py`, `benchmark_root()`, `tests/benchmark/conftest.py` with `collect_ignore_glob`, the project-source rule in `python_failure.py`, `MetrologyStore.write_record` and `iter_records`, `MetrologyStoreError` and `MetrologyRecord`. 424: `BenchmarkStatus`, the lock and interruption helper in `bench_runner.py`, and `commands/sq/benchmark.md`. 425: `ReviewerRef` with `reviewer_key` (`metrology/grade_models.py`), `ReviewOutcome`, `ReviewFailed`, `resolve_reviewer`, `review_tree_diff` (`benchmark/grade_review.py`), `bootstrap_mean_interval`, `pair_seed`, `compare_pair`, `PairVerdict`, `MIN_PAIRED_CASES` (`benchmark/paired_stats.py`), `GradeRecordStore` and `ReviewSummary` (`metrology/grade_models.py`, `grade_store.py`), and `review_flag` in `bench_report.py`. 300, 400, 402 and 917: `run_review_with_profile`, `CodeReviewFinding`, `ReviewCategory`, `normalize_result_categories`, `location_path`, `location_span`, `derive_project_id`, `SourceLanguage`. If any is missing write `BLOCKED: <name> is not implemented (slice <n>)` under this task, leave it unchecked, and stop (Tasks 2–8 are already committed)
  - [ ] Success: all names found; no `BLOCKED:` line
- [ ] Read 421's project-source rule and `SuiteRun`/`FailureKind`, 424's lock helper and the field of 425's `ReviewSummary` that holds a review's cost, once. If the project-source rule is private, make it public in a `refactor:` change with 421's tests unchanged and call it from `is_source_path`. If 424's lock helper is tied to `BenchmarkRun`, extract the lock part into a shared function with 424's tests unchanged
  - [ ] Success: the project-source rule is public and the lock helper is reusable for a recall run; 421 and 424 tests unchanged

**Commit**: `refactor: make the project-source rule and the process lock helper reusable` (skipped when neither needed a change)

- [ ] In `python_recall.py` add `is_source_path(path)`: `.py` files only, deciding project source by calling 421's rule (never a copy). In `benchmark/registry.py` register `PythonRecallAdapter` by `SourceLanguage.PYTHON` with `recall_adapter_for(language)`, raising a named error (logged at ERROR) for a language with none; the registry stays the only importer of concrete adapters
- [ ] Tests `tests/benchmark/test_python_recall_source_path.py`: `is_source_path` for a source file, a test file, `conftest.py`, a `.venv` path and a non-Python file; `recall_adapter_for(PYTHON)` returns a `PythonRecallAdapter`; an unregistered language raises and logs ERROR
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: register the recall adapter and add its source-path check on 421's rule`

### Task 10: Recall models (D5, D6, Database Schema, Patterns)
- [ ] `metrology/recall_models.py`: `StrEnum`s `RecallRejection` (the eight of Patterns), `RecallAbsence` (`case_setup_failed`, `review_failed`), `DefectOutcome` (`found`, `missed`), `FindingOutcome` (`matched`, `duplicate`, `unlocated`, `unmatched`); frozen `PlantedDefect`, `RecallProvenance` (environment digest, build id, `created_at`), `RecallCase`, `RecallBuild`, `RecallRun`, `RecallReview` exactly per Database Schema. `RecallCase.case_id` is derived and validated on read: `rcase-` plus the first 16 hex digits of the sha256 of the canonical JSON of `project_id`, `parent_sha`, `commit_sha`, `mutation_table_version` and each defect's `(path, edit_span, mutated)` (everything else, including provenance, is excluded); defects must be sorted by path and line, `defect_id` `d1`, `d2` … in that order; `RecallRun.state` is a `BenchmarkStatus`
- [ ] Tests `tests/benchmark/test_recall_models.py`: id stable across field order and unaffected by provenance, a defect's `proving_tests`, lines and `enclosing_symbols`; any identity field (including one defect's `mutated` text) changes it; a tampered id fails validation; unsorted defects or wrong `defect_id`s fail validation; every enum value serializes; models are frozen
  - [ ] Success: tests pass; pyright is clean

### Task 11: Records and store (D5, State Management, Database Schema)
- [ ] `metrology/models.py`: `RECORD_TYPE_RECALL_CASE`, `_RECALL_BUILD`, `_RECALL_RUN`, `_RECALL_REVIEW` constants and optional sibling fields on `MetrologyRecord`; `schema_version` unchanged. `metrology/recall_store.py`: `RecallRecordStore(records: BenchmarkRecordStore)` with `write_recall_case` (idempotent), `get_recall_case` (a record of another kind raises `MetrologyStoreError` naming the kind; absent gives `None`), `list_recall_cases(project_id)`, `write_recall_build`, `write_recall_run` (overwrites the run's one record), `get_recall_run`, `latest_recall_run`, `write_recall_review` (id `rreview-<run_id[7:]>-<case_id[6:18]>-<reviewer_key[:8]>-s<sample>`), `reviews_for(run_id)`, `delete_recall_reviews(ids) -> int`. A failed write or tampered file logs ERROR and raises `MetrologyStoreError`, as 421's store does. Reuse 421's `write_record` and `iter_records`
- [ ] `benchmark_store.py` `write_case_set`: accept ids of `benchmark_case` or `recall_case` records; a list holding both kinds raises `MetrologyStoreError` naming both kinds; the existing missing-id check is unchanged
- [ ] Tests `tests/metrology/test_recall_store.py` and additions to `tests/metrology/test_benchmark_store.py`: round trips; idempotent case write; wrong-kind `get_recall_case`; tampered file raises; `list_recall_cases` filters by project; review id format; `delete_recall_reviews` removes only the named ids; a recall-only set, a benchmark-only set, and a mixed list (raises naming both); a failing write (a store double that raises) logs ERROR and raises `MetrologyStoreError` for each record kind; an old `MetrologyRecord` JSON still loads
  - [ ] Success: tests pass; 421, 424 and 425 store tests unchanged

**Commit**: `feat: add recall models, records and store`

### Task 12: Verification fixture projects (Technical Requirements)
- [ ] Helper `tests/benchmark/recall_repos.py`: builds a git repository from a fixture directory in `tmp_path` with a parent commit P and a commit C that adds the package lines under test
  - [ ] Success: for a stub fixture the repo has P and C and `git diff P C` shows exactly the added lines
- [ ] Under `tests/benchmark/fixtures/` create small uv projects in the style of 421's `env_ok` (own `uv.lock`, pytest dev dependency, `pythonpath = ["src"]`), one bullet each:
  - [ ] `recall_proved_assert`: a defect a plain assertion proves. Success: `uv sync --locked` works; one test fails under the defect by assertion
  - [ ] `recall_proved_exception`: a defect whose test sees a project exception. Success: `uv sync --locked` works; the test fails with a project exception
  - [ ] `recall_import_only`: a mutation whose only failures are collection or missing-symbol errors. Success: `uv sync --locked` works; the mutated run reports only those kinds
  - [ ] `recall_passes_under_defect`: a function whose tests reach it and still pass with a `<` ↔ `<=` applied (a boundary no test exercises). Success: `uv sync --locked` works; the tests pass clean and with the edit applied
  - [ ] `recall_flaky`: a test that increments a counter file and fails only on its third execution; each test starts from a fresh copy. Success: `uv sync --locked` works; four runs give pass, pass, fail, pass
  - [ ] `recall_hang`: a `while` loop whose `condition-negate` never ends, with a test that calls it. Success: `uv sync --locked` works; the clean run passes
  - [ ] Success: `uv run pytest tests/benchmark --collect-only -q` lists no node under `fixtures/`

**Commit**: `test: add recall verification fixture projects`

### Task 13: Baseline and proof (D4)
- [ ] `benchmark/recall_verify.py`: `baseline_passing(run_suite, verify_runs) -> frozenset[str]` (nodes passing in every `all_tests()` run; a timeout or `SuiteRunError` raises `BaselineFailed`, logged at ERROR); `prove_site(...)` taking the sandbox tree, a `PlantedEdit`, the selected nodes and the run count and returning `Proved(proving_nodes)`, `NotProved(reason)` or `Hung`. Proving nodes are those failing with `FailureKind.ASSERTION_FAILURE` or `PROJECT_EXCEPTION` in every run; nodes whose failures are only `collection_error` or `missing_symbol` do not prove. The mutated file is written before and restored after every run on every exit path; a timeout or `SuiteRunError` returns `Hung` after the first occurrence with no further runs
- [ ] Tests `tests/benchmark/test_recall_verify.py` with real pytest on the Task 12 fixtures: assertion-proved and exception-proved give proving nodes; import-only gives `NotProved`; the flaky fixture with a baseline of two runs passes it, then a first mutant run fails it and a second passes it, so the site is `NotProved` (fails in one of two runs); the passes-under-defect fixture gives `NotProved`; the hang fixture (with a short `benchmark.suite_timeout_s`) gives `Hung`, logs a WARNING and leaves the file restored; `baseline_passing` over the flaky fixture with `verify_runs=3` excludes its node (the third run fails) and with `verify_runs=2` includes it
- [ ] Doubles for `SuiteRunError` (same file, scripted `run_suite`): `SuiteRunError` during a mutant run gives `Hung` with an ERROR log and one run only; during the baseline raises `BaselineFailed`; a timed-out baseline raises `BaselineFailed`
  - [ ] Success: tests pass; the mutated source file has the same sha256 after each call (other files, the flaky counter file and caches are not compared); pyright is clean

**Commit**: `feat: add recall baseline and proof verification`

### Task 14: Planting (D4)
- [ ] `benchmark/recall_plant.py`: `plant_defects(sites_by_file, sandbox, adapter, seed_sha, limits) -> PlantResult(kept, hung, skipped)`. Sites are visited in an order shuffled by `random.Random` seeded from the commit sha (sha256, never `hash()`); a mutated source that does not parse is skipped; an empty selection (`tests_reaching` over the baseline-passing set) skips as `no_selected_tests`; a site is accepted only if, with it added to the kept set, `derive_line_ranges` (Task 5) puts every adjacent pair of defects in a file at least `2 × RECALL_LINE_WINDOW + 1` lines apart in the defected tree (spacing gap, Context Summary); stop at `defects_per_case` kept or `max_attempts` visited; a `Hung` ends the attempts. `combine(kept, files, adapter)` applies the kept edits per file with Task 5, derives the lines, builds the final `PlantedDefect`s (`defect_id` in path and line order, the operator's category from `operator_for`, original and mutated text, proving nodes, and `enclosing_symbols` from `adapter.enclosing_symbols(original source, site start line)`), and `ast.parse`s every combined file: a failure raises `PlanterError` (logged at ERROR), it is never a rejection. `RECALL_LINE_WINDOW` is imported from `recall_match.py` (Task 4)
- [ ] Tests `tests/benchmark/test_recall_plant.py` with a scripted verifier: the same sha gives the same order and defects; a neighbor at defected distance `2W` is skipped and at `2W+1` kept; a site `2W+1` lines (original) below a kept line-removing defect is skipped because its defected distance is `2W`, and kept at `2W+2`; stops at the defect limit and at the attempt limit; a hang ends the attempts and is reported; a non-parsing mutant is skipped; an empty selection is skipped; a line-removing defect above another in one file stores shifted lines for the lower one, and applying the stored edits to the original tree gives the tree those lines describe; a combined file that does not parse raises `PlanterError`; a built defect carries the enclosing symbols a scripted adapter returns for its line, and an empty tuple only when the adapter returns none
  - [ ] Success: tests pass; pyright is clean

### Task 15: Discovery and pre-checks (D1)
- [ ] `benchmark/recall_discovery.py`: `Candidate(commit_sha, parent_sha, added_lines_by_file, diff_lines)`; `discover(runner, repo_root, adapter, limit, limits) -> DiscoveryResult(candidates, rejections)` using `git log --no-merges --min-parents=1 --format=%H` on `HEAD` newest first up to `limit` (a root commit has no parent and is never a candidate), `git diff --numstat` for diff size, and the unified diff of `P..C` for added line numbers of files where `adapter.is_source_path` is true. Rejections, in this order: `no_source_change`, `diff_too_large` (added plus removed lines over `benchmark.recall_max_diff_lines`), `too_few_added_lines` (added source lines under `benchmark.recall_min_added_source_lines`). A failing `git` call raises `DiscoveryError`, logged at ERROR with the command and stderr
- [ ] Tests `tests/benchmark/test_recall_discovery.py` on a `tmp_path` git repo: a merge commit and the root commit never appear; each of the three rejections; a kept candidate's added line numbers match the diff (including a pure-deletion hunk and a rename); limit honored; newest first; a failing git (a nonexistent repo path) raises with an ERROR log
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add recall planting and candidate discovery`

### Task 16: Build orchestration (Data Flow, D5)
- [ ] `benchmark/recall_build.py`: `DEFAULT_RECALL_SET = "recall"` and `build_recall_cases(deps, set_name, limit, keep) -> RecallBuild`. `deps` injects the repo path, runner, adapter registry, sandbox factory, store, clock and limits. Per candidate: sandbox at C (`EnvironmentResolutionError` → `environment_failed` with the reason), baseline (`BaselineFailed` → `baseline_failed`), sites (none → `no_mutation_sites`), plant, then `kept 0` → `mutant_timeout` when a hang ended the attempts else `no_verified_defect`; else write the `RecallCase` with provenance. One line per candidate goes to a printer callable. After all candidates write the case set as the union of the set's latest version and the kept ids (deduplicated), and one `RecallBuild`. A write failure stops the build and logs ERROR. Sandboxes are removed unless `keep`
- [ ] Tests `tests/benchmark/test_recall_build.py` with doubles (no model, no real pytest): each `RecallRejection` is produced by its own double (`no_source_change`, `diff_too_large`, `too_few_added_lines`, `environment_failed` carrying the reason, `baseline_failed`, `no_mutation_sites`, `mutant_timeout`, `no_verified_defect`); a kept case is written with provenance and the build record lists every rejection once; a rebuild of the same candidates leaves the set version alone; a second build with another project's case pools both into one new version; the printer receives `kept N defects` / `rejected <reason>` lines; `keep` leaves the sandbox; a failing store write stops the build, logs ERROR and writes no case-set version
  - [ ] Success: tests pass; pyright is clean

### Task 17: Build on a real fixture
- [ ] Add an end-to-end test `tests/benchmark/test_recall_build_real.py` marked `network`, as 421's real-process test is: build over the Task 12 `recall_proved_assert` repo with real sandbox and pytest; assert one case with at least one defect whose proving node fails with the stored edit applied and passes without it and whose `enclosing_symbols` names the function holding the edit, and that a second run gives the same case id
  - [ ] Success: the test passes; the build record shows no rejection for that commit

**Commit**: `feat: add recall build orchestration`

### Task 18: Case materializer (Data Flow, Special Considerations)
- [ ] `benchmark/recall_materialize.py`: `materialize_case(sandbox_tree, repo_root, case, runner) -> None`: with the history-free tree at P, `git diff P C` from `repo_root` applied with `git apply`, then the stored edits applied per file with Task 5 (`apply_edits`), then committed as the benchmark identity with a fixed message that names no defect. A failed `git diff`, `git apply`, edit application or commit raises `MaterializeError` (logged at ERROR with the step and stderr)
- [ ] Tests `tests/benchmark/test_recall_materialize.py` on `tmp_path` repos: the diff from P to the new HEAD differs from `P..C` only on the planted lines; the commit message contains none of the operator ids or defect text; a patch that does not apply raises naming the step; an edit whose span no longer matches the file raises; a failing commit raises
  - [ ] Success: tests pass; pyright is clean

### Task 19: `sq benchmark recall build` and `show` (API Contracts)
- [ ] New `cli/commands/benchmark_recall.py`: a `recall_app` Typer registered under `sq benchmark`. `build [--set NAME] [--limit N] [--keep]` (`--limit` defaults to `benchmark.recall_candidate_limit`) runs in the current repository (`derive_project_id` of the cwd), prints the Task 16 lines, then counts by reason and `case set <name> v<n>`. `show CASE_ID` prints a header stating it prints the answers, then commit, each defect (path, lines, operator, category, original and mutated text, proving nodes) and the defected diff from a `HistoryFreeSandbox` at P through `materialize_case`; an unknown id exits 1 naming it. A `build_deps()` function constructs the real collaborators (store, `ProcessRunner`, adapter registry)
- [ ] Tests `tests/cli/test_benchmark_recall_build.py`: output for doubles; `--limit` omitted uses the config value and the flag overrides it; `show` for a stored fixture case (header present, every field printed); unknown id exits 1; `build_deps()` returns real store and runner types without running anything; `--help` lists every option
  - [ ] Success: tests pass

**Commit**: `feat: add the recall case materializer and sq benchmark recall build and show`

### Task 20: Build on squadron (Walkthrough step 1)
Scratch work goes in new directories under `/tmp`; nothing is pushed. Needs 421 implemented and `uv` and `git` on the PATH.
- [ ] Run `sq benchmark recall build --limit 40` in this repository, then run it again
  - [ ] Success: one line per candidate, counts by reason, `case set recall v1`; the second run prints the same case ids and leaves the set at v1
- [ ] Record the counts by rejection reason and the dominant reason in `DEVLOG.md` (repo root: under today's `## YYYYMMDD` heading, a `### Slice 427: Recall yield` entry, newest first, as the file's other entries). A build that keeps no case is the yield risk the design names, a result and not a defect: report the counts to the Project Manager in the final message, and file an issue only if CLAUDE.md's criteria hold (actually broken, or high severity and reasonably likely). It does not block Tasks 21–23, which are pure
  - [ ] Success: `DEVLOG.md` holds the counts

### Task 21: Matcher, path and window rules (D6)
- [ ] `benchmark/recall_match.py` (pure: no I/O, store or model): complete the module Task 4 started with `normalize_match_path(path, tree_root)`: strip a leading `./`, `a/` or `b/`; an absolute path under `tree_root` becomes relative. `finding_reaches(finding, defect, tree_root) -> bool`: paths equal and either `location_span` overlaps `[line_start − W, line_end + W]` or `location_anchor(location)` equals the defect's enclosing bare or dotted name. Add `location_anchor(location) -> str | None` to `review/parsers.py` beside `location_span`: the stripped text after the first `#`, `None` when there is none or for `UNVERIFIED_LOCATION`. Only findings whose severity is `Severity.NOTE`, `Severity.CONCERN` or `Severity.FAIL` (`squadron.review.models.Severity`) are counted; `Severity.PASS` is ignored
- [ ] Tests `location_anchor` in the existing parser tests (grep `location_span` under `tests/`): `path#sym`, `path:42#sym`, a bare path, a line citation, the sentinel. Tests `tests/benchmark/test_recall_match.py` (path and window part), hand-computed: a span inside the window; a span just outside it (one line past `line_end + W`); a `path#function` anchor by bare name and by dotted name; a bare path (unlocated); `a/` and `./` prefixes; an absolute path under the tree; a `PASS` finding is not counted; a deletion defect's zero-width span reached at its start line
  - [ ] Success: tests pass; pyright is clean

### Task 22: Matcher, claim rule and outcomes (D6)
- [ ] In `recall_match.py` add `match(findings, defects, tree_root) -> MatchResult(defect_outcomes, finding_outcomes)`: findings are taken in order; a finding claims at most one defect not yet found: a line span claims the nearest (smallest line gap, ties to the lower `defect_id`), an anchor the first in `defect_id` order. Outcomes per counted finding: `matched`, `duplicate` (reaches only already-found defects), `unlocated` (no path, or a path with neither line nor anchor), `unmatched`. Category is not part of matching; `category_matches` per matched finding is recorded for the agreement column
- [ ] Tests (same file): a duplicate; a category mismatch that still matches and is flagged; a multi-line span reaching two defects claims the nearest and the other stays missed; a tie goes to the lower `defect_id`; an anchor shared by two defects: one finding claims one, a second claims the other; a third finding on the same anchor is a duplicate; unlocated versus unmatched; an empty findings tuple gives all defects missed
  - [ ] Success: tests pass; every matcher criterion of the design's Functional Requirements has a test

**Commit**: `feat: add the deterministic recall matcher and location_anchor`

### Task 23: Recall statistics (D7)
- [ ] `benchmark/recall_stats.py` (pure): `review_fraction(result, n_defects)`; `case_recall(samples)` (mean over K samples); `config_recall(per_case, run_id, reviewer_key) -> RecallStat(mean, low, high, found, total, n_cases)` with the interval from 425's `bootstrap_mean_interval(values, seed)`, the seed derived inside by `recall_seed(run_id, reviewer_key)` (first 8 bytes of the sha256, never `hash()`) so the report and `latest_recall_for` call one function; `compare_configs(a, b, seed)` calling 425's `compare_pair` on `d(c) = r_A(c) − r_B(c)` (cases sorted by id) and `pair_seed(run_id, key_a, key_b)`
- [ ] Tests `tests/benchmark/test_recall_stats.py`, hand-computed values in comments: a two-case, K = 3 example for fractions and means; pooled found/total beside the mean; the seed is stable across processes (fixed expected integer) and differs per key; fewer than `MIN_PAIRED_CASES` gives `too_few_cases`; an interval spanning zero is `not_distinguishable`
- [ ] In `recall_stats.py` add `by_category` and `by_operator` (pooled found over defects × samples, with n defects), `category_agreement` (matched findings with equal category over matched findings), and `finding_counts_per_review` (mean unmatched, duplicate, unlocated). No composite is computed
- [ ] Tests (same file): hand-computed breakdowns for two operators and two categories; agreement with a mismatch; zero matched findings gives no agreement value (`None`, not 0); counts per review
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add recall statistics`

### Task 24: Run plan and refusals (D8, D10)
- [ ] `benchmark/recall_plan.py`: `recall_run_id(set_name, set_version, reviewer_keys, samples)` (`recall-` plus the first 12 hex digits of the sha256 of the set name, version, sorted keys and K); `plan_run(...)` resolving each alias with `resolve_reviewer`, loading the set, checking its kind, and building the list of (case, reviewer, sample) with no `RecallReview` record. Refusals, each naming what is missing, with exit code 1: no `--max-cost`; fewer than 2 samples; no per-review figure (the largest observed `cost_usd` for the same `reviewer_key` among recall reviews and 425's grade `ReviewSummary` records (the cost field Task 9 read), or `--review-cost`); a case's project with no `--repo` whose `derive_project_id` matches; a set holding `benchmark_case` ids (`set <name> holds benchmark cases, not recall cases`). `bound_text(...)`: reviews planned × figure capped at the run cap, plus one review of overshoot, stating the figure is an estimate with no per-review cap
- [ ] Tests `tests/benchmark/test_recall_plan.py`: the run id is order-independent over keys and changes with set version and K; each refusal and its message; the figure comes from the store's largest cost for the key and `--review-cost` overrides; the plan skips reviews that have records; the bound text arithmetic for three cases of planned reviews
  - [ ] Success: tests pass; pyright is clean

### Task 25: Run lock and interruption (D10)
- [ ] In `benchmark/recall_run_state.py`: `begin_recall_run(deps, plan, printer)`: take `<benchmark root>/<recall_run_id>.lock` through the shared lock function (Task 9; a held lock refuses naming the run id and logs WARNING); a stored `running` run whose lock was free is set `interrupted` and reported before planning; the bound is printed; only then write `RecallRun(state=running)` with the new cap. `RecallRun.spent_usd` accumulates across invocations and the cap check starts at zero per invocation
- [ ] Tests `tests/benchmark/test_recall_runner_begin.py`: a second invocation with the lock held refuses and logs WARNING; a `running` record with a free lock becomes `interrupted`, is reported, then `running` after the bound; a `running` record with a held lock is untouched; an ordered event log proves the bound prints before `write_recall_run(running)` and before any review
  - [ ] Success: tests pass; pyright is clean

### Task 26: Case loop and absences (Data Flow, D9, D10)
- [ ] `recall_runner.py` `run_recall(deps, plan, printer)`: per case a `HistoryFreeSandbox` at P and `materialize_case`; a `MaterializeError`, a sandbox failure or any of the three steps failing records `RecallAbsence.CASE_SETUP_FAILED` for each planned review of that case. Per sample, then reviewer: `review_tree_diff(tree, parent_sha, reviewer)`; `ReviewFailed` records `RecallAbsence.REVIEW_FAILED` with `detail`; success writes a `RecallReview` with the findings, `unnormalized_count` and cost of the `ReviewOutcome` as `review_tree_diff` returns them (it already ran `normalize_result_categories`; the runner never normalizes again), and the wall time. One printed line per review (`rcase-… alias sN found a/b · unmatched n`, computed with `match` for display only). Sandboxes are removed unless `keep`
- [ ] Tests `tests/benchmark/test_recall_runner.py` with doubles: each `RecallAbsence` produced by its condition (a failing materializer, a reviewer that raises `ReviewFailed`) with an ERROR log and an absence record; a successful review writes findings and cost; order is sample then reviewer; the printed line counts match; no sandbox remains after a failure
  - [ ] Success: tests pass; pyright is clean

### Task 27: Cap, unpriced reviews, resume and retry (D10)
- [ ] In `recall_runner.py`: before each review, spent at or above the cap stops the run, keeps every record, marks the run `partial` and returns exit 2; a review with `cost_usd` `None` counts at the per-review figure toward the cap and increments `unpriced_reviews`; planned reviews that already have a record are skipped; `--retry-harness` deletes absent reviews (both absences are harness absences) through `delete_recall_reviews` first and reports the count; a completed run is `complete`; a store write failure stops the run with ERROR
- [ ] Tests (same file): the cap stops after the review that crosses it, exit 2, records kept, state `partial`; an unpriced review counts at the figure and is tallied; a rerun skips completed reviews and finishes with `spent_usd` accumulated across invocations; `--retry-harness` removes only absent reviews and reports the count; a failing store write stops the run and logs ERROR
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add the recall run plan and runner with caps, resume and interruption handling`

### Task 28: `sq benchmark recall run` (API Contracts)
- [ ] In `cli/commands/benchmark_recall_run.py`, registered on `recall_app`, add `run --set NAME --review-model ALIAS … --samples K --max-cost USD [--review-cost USD] [--repo PATH …] [--retry-harness] [--keep]`: prints the bound, one line per review, then a summary (reviews, absences by kind, unpriced, spend). Exit 0 complete, 2 cap reached, 1 refusal. A `run_deps()` function constructs the real collaborators
- [ ] Tests `tests/cli/test_benchmark_recall_run.py`: output for doubles; exit 2 on the cap; exit 1 naming the item for each Task 24 refusal; `run_deps()` returns real types without dispatching; `--help` lists every option
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark recall run`

### Task 29: Report model (D7, D10)
- [ ] `benchmark/recall_report.py`: frozen `RecallReport` assembled from records: load the run, its cases and reviews; `match` each review; reduce per case; drop a case from every config's comparison when any of its samples has an absence (counted per config per absence); for a `partial` run use only cases with all K samples recorded for every config. Fields: run id, set and version, matcher version and window, n cases, compared, dropped with reasons, defects, K, measured categories (from the operators actually present), the chance-match line text ("not measured"), per-config `RecallStat`, per-pair verdicts, per-operator and per-category tables, per-review finding counts
- [ ] Tests `tests/benchmark/test_recall_report.py`: a hand-built store of two cases × two configs × K = 2 gives hand-computed recall and counts; an absence on one sample drops that case from both configs and is counted; a partial run excludes incomplete cases; measured categories list only what the cases contain; a run with no data raises a named error
  - [ ] Success: tests pass; pyright is clean

### Task 30: `latest_recall_for` (D11)
- [ ] In `benchmark/recall_summary.py`: frozen `RecallSummary(recall, low, high, n_cases, k, set_name, set_version, matcher_version)` and `latest_recall_for(records, reviewer_key) -> RecallSummary | None`: the most recent recall run that includes the key, via `latest_recall_run`, `reviews_for` and `get_recall_case`; runs whose compared cases are fewer than `MIN_PAIRED_CASES` are skipped; it calls `config_recall` (Task 23) with the run id and key, so the report and 425's line print identical numbers
- [ ] Tests `tests/benchmark/test_recall_summary.py`: the summary equals the report's row for that config (same interval); the newest run wins; a run with too few compared cases is skipped and an older qualifying run is used; no run gives `None`; a key not in any run gives `None`
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add the recall report model and latest_recall_for`

### Task 31: `review_flag` reads recall (D11)
- [ ] In 425's `bench_report.py` change `review_flag(reviewer)` to `review_flag(reviewer, records)`: a summary gives `reviewer recall 0.62 [0.48, 0.75] (n=12, k=3, set recall v1, no tools)` formatted from the summary; none gives the text 425 wrote. Update the single call site to pass the store the report already holds. No other change to report code; the literal text of both forms stays in `bench_report.py`
- [ ] Tests: update `tests/benchmark/test_report_tables.py` for the new parameter; add tests for a store with a recall run (formatted text, two decimals, `set recall v1`) and without (the 425 text); 425's report tests pass unchanged otherwise
  - [ ] Success: tests pass; `grep -rn "unmeasured reviewer" src/squadron/benchmark` still finds one file

**Commit**: `feat: show reviewer recall in the benchmark report`

### Task 32: Report rendering and `recall report` (API Contracts)
- [ ] Text rendering in `benchmark/recall_report_render.py` per the design's layout: header (run, set and version, matcher version and window, "no tools"), the cases and defects line, measured categories, the chance-match line, the config table (recall, interval, found/total, category agreement), paired lines with verdicts, by-operator and by-category tables, findings per review. `--json` emits the `RecallReport` model. In `benchmark_recall_run.py` add `report [RUN_ID] [--json]` (latest run when omitted; an unknown id exits 1 naming it)
- [ ] Tests `tests/benchmark/test_recall_report_render.py` and `tests/cli/test_benchmark_recall_report.py`: output matches the design's layout for a stored fixture; the header contains the matcher version, the window and "chance-match rate: not measured"; JSON parses back into `RecallReport`; latest run chosen when omitted; unknown id exits 1
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add sq benchmark recall report`

### Task 33: Slash-command mirrors (API Contracts)
- [ ] `commands/sq/benchmark.md` (Task 9's gate checks it exists): add `recall build`, `recall run`, `recall report` and `recall show` with the same arguments and no interpretation, so output is identical to the CLI (the form 424 gave `run`)
- [ ] Tests: the existing slash-command sync test (grep `benchmark.md` under `tests/`) covers the new subcommands; add one if none exists
  - [ ] Success: the file lists all four subcommands with the options of the Typer commands (read against each `--help`) and holds no behavior text beyond running `sq benchmark $ARGUMENTS`

**Commit**: `feat: add recall slash commands`

### Task 34: Verification walkthrough (design Verification Walkthrough steps 2–6; step 7 is Task 22's test run)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized. Needs two review aliases that answered yes in `sq benchmark auth-check`; a missing prerequisite no task here can produce is written as `BLOCKED:` with the evidence.
- [ ] Step 2: `sq benchmark recall show <rcase-id>` for a case from Task 20. If Task 20 kept no case, write `BLOCKED: no recall case kept (Task 20 counts)` under this task and stop
  - [ ] Success: each defect shows operator, category, original and mutated text and proving nodes
- [ ] Step 2, hand check: `sq benchmark recall build --set scratch --limit 1 --keep` (if the newest commit keeps no case, repeat with a larger `--limit` until one is kept); in the kept tree apply one defect's stored edit and run its proving node with `.venv/bin/python -m pytest`, then revert the edit and run it again
  - [ ] Success: the node fails with the edit and passes without it; the scratch set is separate from the `recall` set
- [ ] Step 3: `sq benchmark recall run --set recall --review-model <A> --review-model <B> --samples 3 --max-cost 8 --review-cost 0.20 --repo .`
  - [ ] Success: the bound prints first; each line shows found/defects and unmatched
- [ ] Step 4: `sq benchmark recall report`
  - [ ] Success: recall with an interval per reviewer, the paired verdict, recall by operator, finding counts, n and K; the header names the measured categories and the matcher version
- [ ] Step 5: set `benchmark.grading_review_model` to one of the aliases from step 3 and run `sq benchmark report <bench-id>` on a graded benchmark (if the store holds none, create one with the commands of 425 Task 45); then set an alias with no recall run
  - [ ] Success: the review-findings heading shows the recall line for the first alias and the unmeasured flag for the second; both keys are unset afterwards
- [ ] Step 6: `sq benchmark recall run --set recall --review-model <A> --review-model <B> --samples 2 --max-cost 0.01 --review-cost 0.20 --repo .` (K = 2 is a new run id, so step 3's finished reviews do not count), then the same command with `--max-cost 8`
  - [ ] Success: the first stops after the review that crosses the cap and exits 2 with its records kept; the second skips those reviews and finishes with exit 0
- [ ] Any defect found in this slice's code is fixed here with a test and recorded in `DEVLOG.md`; run Task 35's first bullet before the commit below. If no file changed there is nothing to commit and the marker below is skipped

**Commit**: `feat: correct recall build and run after the walkthrough`

### Task 35: Final validation, design names and DEVLOG
- [ ] Run the gates on the whole branch: `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite once; fix any failure at its cause
  - [ ] Success: all clean, or failures recorded as already failing on the target with the test names; 421–425 tests pass unchanged except where D11 changed `review_flag`
- [ ] Check `wc -l` on every file this slice created: each is under ~300 lines (the splits are planned in the Context Summary). `config/keys.py` was 522 lines before this slice and is not split here
- [ ] Update the slice design with the names the implementation added (`recall_edits.py`, `recall_materialize.py`, `recall_plan.py`, `recall_stats.py`, `recall_discovery.py`, `recall_verify.py`, `recall_plant.py`, `recall_run_state.py`, `recall_summary.py`, `recall_report_render.py`, `python_recall_expr.py`, `python_recall_stmt.py`, `python_recall_closure.py`, `benchmark_recall_run.py`, `recall_models.py`, `recall_store.py`, `location_anchor`, `build_deps`, `run_deps`)
- [ ] DEVLOG: implementation entry per the Session State Summary guidance (what was done, Task 20's yield counts, walkthrough results) in `DEVLOG.md` at the repo root, under today's `## YYYYMMDD` heading, newest first; mark the slice design `status: complete` and tick its slice-plan entry when every task above is checked, dropped items `[x]` with a note
  - [ ] Success: slice design and slice plan reflect completion; every task above is checked

**Commit**: `feat: complete reviewer recall slice`
