---
docType: tasks
slice: real-bug-review-recall
project: squadron
lld: user/slices/430-slice.real-bug-review-recall.md
dependencies:
- 420
- 421
- 424
- 425
- 402
projectState: Slices 420–426 complete (replay stack built and frozen). Slice 430 design
  approved with D7, D11, D13 decided by the PM on 20261116; architecture and slice
  plan amended. The hand-run recall data is committed under user/reference/review-recall-results/.
  Target is main (git.integration_branch empty).
dateCreated: 20261116
dateUpdated: 20261116
status: not_started
turns: 29
promptTokens: 1824515
cachedTokens: 1718353
cacheWriteTokens: 106120
completionTokens: 31862
durationSeconds: 310.7
costUsd: 1.830358
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.8303576000000001
    completionTokens: 31862
---

## Context Summary
- Working on slice 430: `sq benchmark recall`, the code-review recall benchmark on real escaped bugs. Design: `user/slices/430-slice.real-bug-review-recall.md`; its D-numbers (D1–D14) are cited below instead of repeating them. Read the cited decision before each task.
- Delivers: case files and case sets, recipes, run and label records, the hit rule, scoring with recall bounds and paired intervals, the report, the import of the hand-run results, live `run` (scrubbed subprocess, leak scan, bound, caps, resume), `label`, the `comb` template and the D11 recipe file. The live D11 run is walkthrough step 7, run by the PM after the slice; no task runs it.
- Excluded (design Technical Scope): live grading (#340), document cases (432), outside tools, concurrency (#146), any change to 421–426 or `sq review code`.
- Design gaps found while reading the code. Task 1 writes each into the design; later tasks follow the corrections:
  - **Payload models live in `metrology/`.** `MetrologyRecord` (`metrology/models.py`) imports every payload from `metrology/*_models.py`; it never imports `benchmark/`. The four recall payloads and their parts go in `metrology/recall_case_models.py`, `metrology/recall_run_models.py` and `metrology/recall_label_models.py`. `benchmark/recall/case_models.py` keeps only the case-file loader and validator.
  - **Lock name.** There is no `bench_lock` function: the lock is `BenchmarkLock.acquire(root, benchmark_id, runner)` (`benchmark/bench_lock.py`), used with lock id `recall`.
  - **Timeout refusal.** `benchmark_common` has no timeout check. `run` uses `check_review_timeout` (`benchmark/grading_config.py`) as `benchmark_grade.py` does.
  - **Pair seed.** `pair_seed(benchmark_id, key_a, key_b)`: `benchmark_id` is `<set name>@v<version>`, the keys are the two row keys.
  - **How a recipe selects stored entries (D2, D4, D10).** A recipe stage matches an entry when the entry's `entry_key` equals the alias's live `entry_key` (resolved from config, no call), or the entry's `source` is `import:*` and its `alias` equals the recipe's alias. Each distinct stage identity found becomes its own row; a recipe with both live and imported matches gives separate, flagged rows. `run` treats only live `entry_key` matches as stored.
  - **Overrides file (D10).** Not named in the design: `user/reference/review-recall-overrides.yaml`, outside the cases folder so `cases add <dir>` never reads it.
  - **Slash command parity.** `commands/sq/benchmark.md` documents every `sq benchmark` subcommand. It gains the recall subcommands (Task 30).
  - **Stale text.** D11, D13 and walkthrough step 7 still say "PM to confirm" / "pending PM confirmation"; both are decided (DEVLOG 20261115, PM decisions 20261116).
- Shared names (defined once, never compared as literals): `RECORD_TYPE_RECALL_*` in `metrology/models.py`; `StageKind`, `CombVerdict`, `StageOutcome`, `RecallLeakVerdict`, `UNKNOWN_MARKER` in `recall_run_models.py`; `HitVerdict`, `FindingGrade`, `LabelerKind` in `recall_label_models.py`; the decisions word table in `decisions.py`; `MIN_RECALL_PAIRED_CASES = 8` (the runbook floor; `paired_stats.MIN_PAIRED_CASES` is 5 and is not used) in `scoring.py`; `EXIT_CAP_REACHED` reused from `cli/commands/benchmark_grade.py`.
- Failure modes: every D8 row (both tables) is asserted, outcome plus log record, in the task that produces it: Tasks 9, 19, 20 (`cases add`, import), 24, 25 (stage calls, sandbox), 27 (lock, `write_record`, orphan, retry).
- Tests live in `tests/benchmark/recall/` (plus `tests/config/`, `tests/cli/`). They run no model and no git outside fixtures; process runner, sandbox factory and clock are injected. Pyright covers `src` only. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Nothing here pushes or merges.
- Effort 5/5. Next planned slice: 431 (Implementation Report from Run Records).

## Tasks

### Task 1: Commit the task file, correct the design, create the branch
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file, commit it by path as `docs: add slice 430 tasks`
  - [ ] Success: `git status --short` does not list the task file
- [ ] Edit `user/slices/430-slice.real-bug-review-recall.md` so it states each design-gap bullet in the Context Summary: Component Structure (model homes), D1, D2, D4, D9 (lock name, timeout check), D10 (overrides path), D12 (seed), API Contracts. Remove the "PM to confirm" sentences in D11 and D13 and "pending PM confirmation" in walkthrough step 7
  - [ ] Success: `grep -n "PM to confirm\|pending PM\|bench_lock" project-documents/user/slices/430-slice.real-bug-review-recall.md` finds nothing; the design names `metrology/recall_*_models.py`, `BenchmarkLock`, `check_review_timeout`, the overrides path and the entry-selection rule

**Commit**: `docs: correct slice 430 design for model homes, lock, entry selection`

- [ ] `git checkout -b 430-slice.real-bug-review-recall <target>` (or switch to it if it exists)
  - [ ] Success: `git branch --show-current` prints the slice branch

### Task 2: Config key `benchmark.recall_fetch_timeout_s`
- [ ] `config/keys.py`: add `BENCHMARK_RECALL_FETCH_TIMEOUT_KEY` and its `ConfigKey` entry next to the other benchmark keys: `type_=int`, `default=120` (the same per-command bound `HistoryFreeSandbox` uses for its own git commands, D7), description naming the three D7 commands it bounds
- [ ] Test in `tests/benchmark/test_config_keys.py` (existing file): key present, default 120, type int
  - [ ] Success: tests pass; pyright zero errors

**Commit**: `feat: add benchmark.recall_fetch_timeout_s config key`

### Task 3: Case payload models (D1)
- [ ] `metrology/recall_case_models.py`: `BugLocation` (file, symbol optional, reason optional; `reason` required when it is an extra location), `KnownBug` (id, description, proof list, `original_review` enum `missed|reported`, `locations` frozen list, `extra_locations`), `RealBugCase` (project_id, case_id, name, kind, repo, host_repo, distribution, base, head, status enum `verified|checked`, hand_run_id optional, bugs, notes), `RecallCaseSet` (name, version, case_ids, created)
- [ ] `case_id_for(case)`: `rbcase-<sha12>` of canonical JSON (sorted keys) of (kind, repo name, base, head, host_repo, bugs with resolved locations). `case_set_id(name, version)`: `rbset-<name>-v<version>`
- [ ] Tests `tests/benchmark/recall/test_case_models.py`: id stable across field order; any bug or location change gives a new id; extra location without reason rejected
  - [ ] Success: tests pass

### Task 4: Run and stage payload models (D4, D6, D8, D10)
- [ ] `metrology/recall_run_models.py`: enums `StageKind` (`review`, `comb`), `CombVerdict` (`KEEP`, `DROP`, `UNDECIDED`), `StageOutcome` (`ok`, `config_failure`, `harness_failure`), `RecallLeakVerdict` (424's verdicts plus `confined`, `not_scanned`); constant `UNKNOWN_MARKER = "unknown"`
- [ ] Models: `StageConfig` (model, profile, template_hash, tool_use, max_output_tokens; each `str` or the unknown marker where D10 says so) with `config_key` (sha256 of the five); `StageUsage` (cost_usd, cost_basis, duration_s, turns, tool_calls); `RecallFinding` (finding_id, content_key, severity, category via `map_historical_category`, raw_category, location, title, description); `CombDecision` (verdict, reason); `StageEntry` (fields per D4 including `outcome` + `outcome_reason`, `leak`, `source`, `case_set`, `raw_ref`, `alias`, `created`, `duplicate_decisions`, `unknown_ids`); `RecallRun` (case_id, run_index, `reviews: dict[str, StageEntry]`, `combs` keyed by `"<entry_key>|<chain_key>"` string, `superseded`)
- [ ] Helpers: `entry_key(config, effort_configured)`, `chain_key(comb_entry_keys)` joined with `>`, `content_key(location, title, description)` (sha256, whitespace collapsed), `run_record_id(case_id, run_index)` → `rbrun-<sha12>`
- [ ] Tests `test_run_models.py`: `config_key` ignores alias and configured effort; `entry_key` includes configured effort; content key is whitespace-insensitive; a chain's parent key is the chain minus its last element; round-trip JSON
  - [ ] Success: tests pass

### Task 5: Label payload model (D3, D5)
- [ ] `metrology/recall_label_models.py`: `HitVerdict` (`HIT`, `ADJACENT`, `MISS`), `FindingGrade` (the grade words used in the committed graded files; read them, one enum member each), `LabelerKind` (`person`, `import`), `RecallLabels` (case_id, labeler, labeler_kind, `hits: dict[content_key, dict[bug_id, HitVerdict]]`, `grades: dict[content_key, FindingGrade]`, updated, notes); `labels_record_id(case_id, labeler)` → `rblabels-<case_id>-<labeler>` (labeler sanitized to path-safe characters)
- [ ] Tests `test_label_models.py`: every grade word in the committed graded files maps to a member (read the files in the test); id is path-safe for `import:grid3/BRIEF-B2.md`
  - [ ] Success: tests pass

### Task 6: Record types and `recall_store` (Database Schema, D4)
- [ ] `metrology/models.py`: `RECORD_TYPE_RECALL_CASE`, `RECORD_TYPE_RECALL_CASE_SET`, `RECORD_TYPE_RECALL_RUN`, `RECORD_TYPE_RECALL_LABELS`, and four optional sibling payload fields on `MetrologyRecord`. `schema_version` stays 1
- [ ] `benchmark/recall/recall_store.py`: `RecallRecordStore(MetrologyStore)` with write/get/list for cases; `write_case_set(name, case_ids)` that writes a new version only when membership changed (same members → existing version returned); `get_case_set(name, version=None)` (newest when None) and `parse_set_ref("name@N")`; `get_run`/`put_run` (rewrite via `write_record`); `list_runs(case_ids)`; labels get/put/list per case
- [ ] Tests `test_recall_store.py` on a temp store: round-trip each type; same membership keeps the version; changed membership bumps it; `name@2` resolves; rewriting a run keeps one record; `write_record` raising surfaces as the exception (CLI handling in Task 27)
  - [ ] Success: tests pass; pyright zero errors

**Commit**: `feat: add recall case, run and label records and store`

### Task 7: Fixture bug repo (test infrastructure, walkthrough step 5)
- [ ] `tests/benchmark/recall/fixtures/bug_repo/build.py` (pattern: `tests/benchmark/slice_repos.py`): builds a small git repo in a temp dir with a base commit, a buggy head commit and a later fix commit; writes `case.yaml` beside it with base/head shas, one bug B1 whose proof is the fix commit
- [ ] `tests/benchmark/recall/conftest.py`: a `bug_repo` fixture calling the builder; a fake `ProcessRunner` that records argv and returns scripted results; a fixed clock
  - [ ] Success: a smoke test builds the repo and `git rev-list --count base..head` in it is 1

**Commit**: `test: add recall fixture repo and fakes`

### Task 8: Case-file loader and validator (D1)
- [ ] `benchmark/recall/case_models.py`: `load_case_file(path) -> CaseFileSpec` with PyYAML; schema check; `~` kept unexpanded in the record, expanded at use. Refuse: missing required field, unknown `status`/`original_review`, issue proof (`#n`) with no `extra_locations`, extra location without reason
- [ ] `derive_locations(spec, runner, timeout)`: for each commit proof, `git show --name-only --format= <sha>` in the case repo (timeout `benchmark.recall_fetch_timeout_s`); every changed file becomes a `BugLocation`, unfiltered; then append `extra_locations`. A failing or timed-out `git show` raises a `CaseFileError` naming the commit
- [ ] Tests `test_case_loader.py` with the fake runner and the fixture repo: derived list equals the fix commit's files; issue proof without extras refused; timeout refused with commit named
  - [ ] Success: tests pass

### Task 9: `RecallKind` seam and `CodeKind` (D14), with the review sandbox (D7)
- [ ] `benchmark/recall/review_sandbox.py`: context manager entering `HistoryFreeSandbox(start_sha=head)` unchanged, then via the injected `ProcessRunner` (timeout `benchmark.recall_fetch_timeout_s`): `git rev-list --count base..head` in the source repo, `git -C <tree> fetch --depth <count+1> <repo> <head>`, `git -C <tree> rev-parse --verify base^{commit}`. Any failure raises `SandboxError` with the reason (missing repo, timeout, fetch error, base unreachable); no refs created
- [ ] `benchmark/recall/kinds.py`: `RecallKind` protocol (`validate`, `open_sandbox`, `review_argv` per D14), a registry keyed by `kind`, `get_kind(kind)` raising on unknown. `CodeKind`: `validate` = Task 8 loader + `derive_locations`; `open_sandbox` = `review_sandbox`; `review_argv` = `[sq, "review", "code", "--diff", base, "--model", alias, "--no-save", "--output", "file", "--output-path", out]`
- [ ] Tests `test_review_sandbox.py` (fixture repo, real git): tree has head and base, and not the fix commit; each failure gives `SandboxError` and a WARNING log at the caller (Task 25 asserts the outcome). `test_kinds.py`: registry lookup; unknown kind raises; a stub kind registers and is returned
  - [ ] Success: tests pass; `git diff <target> -- src/squadron/replay/history_free_sandbox.py` is empty

### Task 10: CLI group, `cases add` and `cases list` (D1, D8)
- [ ] `cli/commands/benchmark_recall.py`: Typer subgroup `recall` registered in `cli/commands/benchmark.py` via `add_typer`; a services factory (store, runner, sandbox factory, clock, sq path) as in `benchmark_grade.py`/`grade_services.py`; a `recall_lock()` helper around `BenchmarkLock.acquire(<benchmark root>, "recall", runner)` (live holder → ERROR naming the pid, exit 1; dead holder → WARNING, taken over), used by every writing command. Split into `benchmark_recall_*.py` modules once past ~300 lines
- [ ] `cases add <path>... --set NAME`: expand dirs to `*.yaml`; validate and derive every file first; on any failure print every failing file and reason, log ERROR, exit 1, write nothing; else write cases and `write_case_set`. Look up the kind via the registry, never branch on it
- [ ] `cases list [--set]`: sets with versions; per case name, kind, status, bug count, each bug's locations and extras with reasons, and whether the repo path exists
- [ ] Tests `tests/cli/test_benchmark_recall_cases.py`: happy path on the fixture case; two bad files → both listed, exit 1, store empty; rerun with same files keeps v1; ERROR log asserted
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark recall cases add and list`

### Task 11: The 17 case files and four set lists (D1, D13)
- [ ] Write one YAML file per case under `user/reference/review-recall-cases/` from `user/reference/review-recall-cases.md` (17 cases, 21 bugs; controls and `cf9006d5-N1` are notes, not bugs). Fill `host_repo` from each repo's `origin` remote (`git remote get-url origin`) and `distribution` from the head commit's `pyproject.toml`/`package.json` (`git show <head>:pyproject.toml`). Add `extra_locations` (with reason) only where the case text or graded hits cite a file the proof commit did not change — check 307 B1 (`cutover_304_first_purchase.py`) against `git show --name-only` of its proof
- [ ] `user/reference/review-recall-sets.md`: the file list for each set: `real-bugs` (17), `real-bugs-original` (first 10, 14 bugs), `real-bugs-original-no-u103` (9, 13), `real-bugs-nonsquadron` (14)
- [ ] Test `test_committed_cases.py`: every committed case file passes the schema check (fake runner, no git); counts 17 cases / 21 bugs; each set list resolves to existing files with the stated counts
  - [ ] Success: tests pass; `sq benchmark recall cases add project-documents/user/reference/review-recall-cases/ --set real-bugs` on the real store exits 0 with 17 cases (walkthrough step 1)

**Commit**: `docs: add the 17 real-bug case files and set lists`

### Task 12: Decisions parser (Patterns: decisions parser)
- [ ] `benchmark/recall/decisions.py`: `parse_decisions(raw, finding_ids) -> DecisionParse` (decisions dict, duplicate count, unknown-id count). One word→`CombVerdict` table. Lenient: `F3: KEEP — reason`, `F3 - KEEP: reason`, `**F3**: keep`, hyphen/en/em dash, any case, surrounding markdown. First verdict per id wins. Ids not in `finding_ids` are counted. Missing ids become `UNDECIDED`. No parseable line at all returns an empty parse (caller makes it `config_failure`)
- [ ] Fixtures: copy `raw_output` from at least one Claude, one Codex and one OpenRouter comb output in `20261113-comb/out/` into `tests/benchmark/recall/fixtures/decisions/`
- [ ] Tests `test_decisions.py`: each format variant; real fixtures parse with no `UNDECIDED` where the output decided every id; duplicate and unknown counts; empty output gives empty parse
  - [ ] Success: tests pass

**Commit**: `feat: add lenient comb decisions parser`

### Task 13: Recipes (D2) and recipe files
- [ ] `benchmark/recall/recipe.py`: `Recipe` (name, reviewers, pool, combs); loader refuses empty reviewers, `pool: true` with one reviewer, duplicate reviewers. `required_stages(recipe)`: per reviewer one review stage, plus one comb stage per chain prefix (luna, then luna>opus-high)
- [ ] Recipe files under `user/reference/review-recall-recipes/`: `haiku-xhigh`, `sol`, `sonnet-high`, `sonnet`, `luna` (single reviewers); `haiku-sol-opus` (fan-out haiku-xhigh + sol, comb `[opus-high]`); `haiku-sol-pool` (pool); `haiku-sol-luna-opus` (D11: fan-out, combs `[luna, opus-high]`). Section 5's reviewer+comb recipes are built in the reproduction test (Task 22), not committed
- [ ] Tests `test_recipe.py`: refusals; stage expansion for fan-out + two-stage comb; every committed recipe file loads
  - [ ] Success: tests pass

**Commit**: `feat: add recall recipes and recipe files`

### Task 14: Import review outputs (D10)
- [ ] `benchmark/recall/hand_run_import.py`, part 1: read `*.json` directly under `20261112-grid1/`, `20261112-grid2/`, `20261113-grid3/` (`<case>-<config>-<run>.json`); map `<case>` to a case by `hand_run_id` (no case → skip, listed); build `StageConfig` per D10's review table (template marker `unknown:<template_name>@<squadron_version>`, `tool_use` unknown, `effort_sent` null); findings → `RecallFinding` with content keys; raw output into the `REVIEWS` sidecar; `leak: not_scanned`; `source: import:<folder>`. Unreadable/invalid/missing-field file → WARNING, skipped, listed
- [ ] Return an `ImportPlan` (run records keyed by id, skipped list, unknown-field counts); no store writes here
- [ ] Tests `test_import_reviews.py` on the real committed files: 723 review entries across 51 run keys; a corrupt temp file is skipped with WARNING; unknown counts present
  - [ ] Success: tests pass

### Task 15: Import comb outputs (D10)
- [ ] Part 2: `20261113-comb/out/<comb>/<case>-<reviewer>-<run>.json`; attach to the review entry of that case/reviewer/run; `luna-r+opus-high` becomes chain luna-r then opus-high (parent = the luna-r entry). Comb config per D10's comb table (`comb.yaml@9bc108a6#<folder>`). Decisions from the stored output via Task 12's parser; missing ids `UNDECIDED` (no DROP default)
- [ ] Tests `test_import_combs.py` on the real files: 480 comb entries; the two-stage chain key has two parts; two comb folders that differ only by name have different `config_key`s
  - [ ] Success: tests pass

### Task 16: Import grading passes, hit labels and overrides (D10)
- [ ] Part 3: the four passes in D10's table, one labeler `import:<brief>` each, one `RecallLabels` per graded case. Resolve `<config>/<run>/<index>` refs to the imported finding's content key (unresolved → WARNING, skipped, listed). `matched` refs take the named issue's grade and `known`. `known: Bn` → `HIT` for Bn; other issues' members → `MISS` for every bug of the case; cf5e840c partial → `HIT`. Later pass in table order wins on conflicts; conflicts counted and listed
- [ ] `user/reference/review-recall-overrides.yaml`: the RESULTS.md section 12 adjudications (921-I9 REAL, 197-I14 MINOR) as person labels; the import writes them under labeler kind `person`
- [ ] Tests `test_import_labels.py` on the real files: four labelers present; a conflict is listed; overrides applied; a bad ref is skipped with WARNING
  - [ ] Success: tests pass

### Task 17: `import` command (D10, D8)
- [ ] `import <results-dir> --set NAME [--dry-run]`: take the recall lock (Task 10 helper), build the plan, print counts (review/comb entries, run records, label records, unknown-field counts, grade conflicts, skipped files and refs); without `--dry-run` write records; second import writes nothing and says "no changes"; exit 1 at the end if anything was skipped
- [ ] Tests `tests/cli/test_benchmark_recall_import.py`: dry run writes nothing; real run then rerun reports no changes; skipped file → exit 1
  - [ ] Success: tests pass; walkthrough step 2 counts match (723, 480, 51)

**Commit**: `feat: add sq benchmark recall import for hand-run results`

### Task 18: Hit rule (D3)
- [ ] `benchmark/recall/hit_rule.py`: `cited_paths(finding)` (lenient: `path:12-30`, `path#symbol`, `path (text)`, bare basenames with an extension, from location and description); `path_matches(a, b)` (suffix at `/` boundary); `gate(finding, bug) -> GateResult` (`candidate` | `decided_miss`); `resolve(finding, bug, labels) -> HIT|ADJACENT|MISS|UNDECIDED` with person over import precedence
- [ ] Tests `test_hit_rule.py`: each path form; no path → candidate for every bug; mismatch → decided miss; label precedence; **every imported `HIT` label passes the gate** (real records from Tasks 14–16). If one fails, add an `extra_locations` entry with reason to that case file; do not loosen the gate
  - [ ] Success: tests pass

### Task 19: Scoring — recipe outputs per (case, run) (D2, D3, D8)
- [ ] `benchmark/recall/scoring.py` (pure, no I/O), part 1: entry selection per the Context Summary rule; per (case, run) build each reviewer's final kept set in lower and upper form (`UNDECIDED` → drop / keep; stage-one `UNDECIDED` not sent to stage two); failed comb → zero kept; group by stage identity (`config_key`, `effort_sent`); drop (case, run) on any `harness_failure`, `leaked` or `scan_unavailable` entry, counting by reason; incomplete pairs left out and listed; fan-out = union; pool = per-member values kept for the mean
- [ ] Tests `test_scoring_outputs.py` with hand-built runs: fan-out union, pool, two-stage chain with a stage-one `UNDECIDED`, harness and leak drops, superseded entries ignored, incomplete coverage listed, live+imported → two flagged rows
  - [ ] Success: tests pass

### Task 20: Scoring — metrics, bounds, real share (D3, D5)
- [ ] Part 2: per row: cases, runs, bug-hits / (bugs × runs) low and high, bugs found, runs with a hit, adjacent count, undecided count, findings/run (raw sum), matched nothing (lower-bound set, excludes undecided), real share over graded findings with pass names, graded count, person-checked count and agreement, cost/run with basis, leak counts (`not_scanned` per row), entries from another set version. Pool = mean of members' per-case metrics. Split recall by `original_review`
- [ ] Tests `test_scoring_metrics.py`: bounds equal when nothing undecided; matched nothing excludes undecided; pool mean; live entries ungraded
  - [ ] Success: tests pass

### Task 21: Scoring — paired intervals (D12)
- [ ] Part 3: per recipe pair, shared complete cases with nothing undecided; per-case recall and findings/run; `compare_pair` with `pair_seed("<set>@v<n>", key_a, key_b)`; "not distinguishable" when the interval spans zero; "too few cases" below `MIN_RECALL_PAIRED_CASES`; count left out for undecided
- [ ] Tests `test_scoring_paired.py`: deterministic interval for a fixed set; spanning zero; too few; undecided cases counted
  - [ ] Success: tests pass

### Task 22: Report rendering and `report` command (API Contracts)
- [ ] `benchmark/recall/report_render.py`: text table and footer lines exactly as the design's `report` example; `effort_sent` null printed "not recorded"; recall printed as one number or `low–high`. JSON model with set name/version, n cases, n runs, bounds, matched nothing, real share, cost, paired comparisons, newest entry date
- [ ] `report --recipe FILE... --set NAME[@V] [--runs N] [--json]` in the CLI
- [ ] Tests: `test_report_render.py` (text layout, "not recorded", range form); `test_report_json_schema.py` fixes the JSON schema for 433
- [ ] Reproduction tests `test_reproduce_results.py` on imported real records: section 1 bug-hits 16/12/7/4 of 42 and runs with a hit 14/12/7/4 of 30 over `real-bugs-original`, runs 1..3; 13/9/4/1 of 39 over `real-bugs-original-no-u103`; section 5 known kept: for each comb, build in the test the four recipes (haiku-xhigh, sol, sonnet-high, sonnet, each with that one comb), sum their run-1 bug-hits over `real-bugs-original`, and expect opus-high 14, luna-r 14, sol 10, sonnet-high 8, against 14 for the same four reviewers uncombed; `haiku-sol-opus` and `haiku-sol-pool` on run 1 report with no "Left out" and pool = mean of the two single rows
  - [ ] Success: all tests pass; walkthrough steps 3 and 4 print the same numbers

**Commit**: `feat: add recall hit rule, scoring and report reproducing hand-run tables`

### Task 23: `comb` template and `_stage` command (D6)
- [ ] `data/templates/comb.yaml`: the prompt from `20261113-comb/comb.yaml` unchanged, with `output: decisions`
- [ ] Hidden `_stage --template comb --input FILE --output FILE`: reads upstream findings, renders `F1..Fn` (the `comb.py render` format), calls `run_review_with_profile` with `allowed_tools: [read_file, list_files, grep]`, writes output (raw text, decisions, usage) to `--output` only after the model call returns
- [ ] Tests `test_stage_command.py` with a stubbed `run_review_with_profile`: rendered input matches `comb.py render` on one real case; output written; no output file when the call raises
  - [ ] Success: tests pass

**Commit**: `feat: add comb template and hidden recall _stage command`

### Task 24: Stage runner and leak verdicts (D6, D8)
- [ ] `benchmark/recall/stage_runner.py`: `run_stage(...) -> StageEntry`. Build a `ScrubbedEnvironment` with the alias profile's `CredentialGrant` only; cwd = sandbox; argv from the kind's `review_argv` or the `_stage` argv, using the `resolve_sq_path()` path passed in; timeout `benchmark.review_timeout_s`; output under `recall-out/<record id>/<stage key>.json`
- [ ] Outcomes: no start / no output file → `harness_failure` + exit code + stderr tail; timeout or unparseable output → `config_failure`; comb partial → `ok` with `UNDECIDED`s; each logged WARNING with case, run, stage
- [ ] Leak: `transcript_source_for(profile)`; with a source, `leak_scan.scan(source, scrubbed_home, build_leak_rules(...))` with the D6 inputs (tree, home, output_dir, real_home, repo_root, `installed_package_location()`, `uv_cache_dir(runner)`, distribution, host owner/repo); none and jailed builtins → `confined`; neither → raise (plan refuses earlier, Task 26)
- [ ] Tests `test_stage_runner.py` (fake runner, fake transcript source): each outcome row with log asserted; scan inputs include the case repo and host repo; a scripted transcript reading the case repo by absolute path → `leaked`; `confined` path never calls `scan`
  - [ ] Success: tests pass; `git diff <target> -- src/squadron/benchmark/leak_rules.py` is empty

**Commit**: `feat: add recall stage runner with scrubbed subprocess and leak scan`

### Task 25: Sandbox failures as harness outcomes (D8)
- [ ] In the run loop helper: one sandbox per case per invocation, reused for its stages and removed after; `SandboxError` → every pending stage of that (case, run) gets a `harness_failure` entry with the reason, WARNING logged
- [ ] Tests `test_sandbox_failures.py`: missing repo, fetch timeout, base unreachable each give `harness_failure` with reason and log; sandbox removed on success and failure
  - [ ] Success: tests pass

### Task 26: Run plan, preflight and bound (D6, D9)
- [ ] `benchmark/recall/run_plan.py`: expand recipes over set cases and runs 1..N to live stage keys; drop stored (live `entry_key` match; with `--retry-harness` keep harness and dropped-leak entries as pending); refuse a profile with no transcript source and no jailed builtins (exit 1); per-call figure = max observed `cost_usd` for the `config_key`, else `--call-cost` (refuse when missing); bound = sum + largest once, labeled "estimate" or "from --call-cost"; plan-billed count, requiring `--max-plan-calls` when any; `render_bound` wording after `grade_plan.render_bound`
- [ ] Preflight: `run_auth_check` for distinct profiles with `benchmark.auth_probe_timeout_s`; any non-`yes` → ERROR naming the profile, exit 1, nothing recorded
- [ ] Tests `test_run_plan.py`: expansion; stored skipped; refusals (no `--max-cost`, no timeout via `check_review_timeout`, no `--call-cost`, no `--max-plan-calls`, auth failure); bound arithmetic and labels
  - [ ] Success: tests pass

### Task 27: `run` command — loop, caps, resume, orphans, retry, lock (D8, D9)
- [ ] `run` in the CLI: `recall_lock()`; preflight; print bound; serial loop with `ReviewBudget.before_review()` / `after_review(cost)`; `GradeCapReached` or plan-call cap → print remaining, exit `EXIT_CAP_REACHED`. Before dispatch, an output file in `recall-out/` with no entry is ingested (leak scan if its home remains), else repeated with a WARNING that the earlier cost was spent without a record. `--retry-harness` moves the replaced entry to `superseded`. `write_record` failure → ERROR, exit 1, output file left. `--case NAME` filters
- [ ] Tests `tests/cli/test_benchmark_recall_run.py` (fake runner, scripted subprocess results): bound printed before first call; serial order; dollar cap and plan cap → exit 2 with records kept; rerun → "0 stages to run"; orphan ingested; retry supersedes, nothing deleted; lock live/dead; `write_record` failure; each with log asserted. `ReviewBudget.before_review` raises only once spend reaches the cap, so the first call always runs (the overshoot term); assert that. The committed `haiku-sol-luna-opus.yaml` over a fake 14-case set prints its bound with the plan-billed count (D11 criterion)
- [ ] End-to-end test `test_run_end_to_end.py` on the fixture repo with a scripted `sq` subprocess: two review entries with leak verdicts, a leaking call recorded `leaked` and dropped from `report` with the drop counted; a stub kind registered in the registry runs one stage (Integration Requirements)
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark recall run with bound, caps and resume`

### Task 28: `label` command (D3)
- [ ] `label --set ... [--recipe ...] [--case ...]`: list each undecided candidate with case, bug id and description, bug files and symbols, content key, severity, location, title, description, affected recipes and runs. `--hit KEY BUG HIT|ADJACENT|MISS --by NAME` writes the person `RecallLabels` for that case (rewrite in place); refuse unknown key or bug
- [ ] Tests `tests/cli/test_benchmark_recall_label.py`: listing on hand-built records; recording a label removes it from the list and the report's undecided count drops; unknown key refused
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark recall label`

### Task 29: Unchanged-file check (Technical Requirements)
- [ ] `git diff <target> --stat -- src/squadron/replay/history_free_sandbox.py src/squadron/metrology/grade_models.py src/squadron/benchmark/leak_rules.py` and the `sq review code` command module(s) (find with `grep -rln "def review_code\|\"code\"" src/squadron/cli/commands/`)
  - [ ] Success: no diff in any of them

### Task 30: Docs — runbook, slash command, CHANGELOG
- [ ] `user/reference/review-recall-runbook.md`: "Running a reviewer on a case" and "Scoring" point to `sq benchmark recall` commands; the hand-run method stays as the fallback for outside tools
- [ ] `commands/sq/benchmark.md`: a recall paragraph listing `cases add`, `cases list`, `import`, `run`, `label`, `report` with key options and exit codes, matching the existing style (cost warning on `run`)
- [ ] `CHANGELOG.md`: one short user-facing bullet for `sq benchmark recall`
  - [ ] Success: `grep -n "benchmark recall" commands/sq/benchmark.md project-documents/user/reference/review-recall-runbook.md CHANGELOG.md` finds each file

**Commit**: `docs: point recall runbook and slash command to sq benchmark recall`

### Task 31: Final validation and walkthrough
- [ ] `ruff format`, `ruff check`, `pyright` (zero errors), `pytest tests/benchmark/recall tests/cli tests/config -q`
  - [ ] Success: all pass
- [ ] Walkthrough steps 1–6 of the design on the real store (step 5 uses `luna` with `--max-cost 0.05`; LLM spend is pre-authorized). Step 7 is not run
  - [ ] Success: each step's expected output observed; any mismatch fixed or recorded as `BLOCKED:` under this item
- [ ] DEVLOG entry (Session State Summary format); slice design `status: complete`; slice plan entry 430 checked
  - [ ] Success: files updated

**Commit**: `docs: complete slice 430 and record walkthrough results`
