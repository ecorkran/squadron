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
dateUpdated: 20261118
status: complete
turns: 48
promptTokens: 4792203
cachedTokens: 4617673
cacheWriteTokens: 174448
completionTokens: 77194
durationSeconds: 683.4
costUsd: 3.863646
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.863645600000001
    completionTokens: 77194
revision_number: 2
---

## Context Summary
- Working on slice 430: `sq benchmark recall`, the code-review recall benchmark on real escaped bugs. Design: `user/slices/430-slice.real-bug-review-recall.md`; its D-numbers (D1–D14) are cited below instead of repeating them. Read the cited decision before each task.
- Paths: source modules are relative to `src/squadron/`, tests to the repo root, and `user/...` documents to `project-documents/`.
- Delivers: case files and case sets, recipes, run and label records, the hit rule, scoring with recall bounds and paired intervals, the report, the import of the hand-run results, live `run` (scrubbed subprocess, leak scan, bound, caps, resume), `label`, the `comb` template and the D11 recipe file. The live D11 run is walkthrough step 7, run by the PM after the slice; no task makes a D11 call.
- Excluded (design Technical Scope): live grading (#340), document cases (432), outside tools, concurrency (#146), any change to 421–426 or `sq review code`.
- Design gaps found while reading the code. Task 1 writes each into the design; later tasks follow the corrections:
  - **Payload models live in `metrology/`.** `MetrologyRecord` (`metrology/models.py`) imports every payload from `metrology/*_models.py`; it never imports `benchmark/`. The four recall payloads and their parts go in `metrology/recall_case_models.py`, `metrology/recall_run_models.py` and `metrology/recall_label_models.py`. `benchmark/recall/case_models.py` keeps only the case-file loader and validator.
  - **`combs` key (D4).** A tuple `(entry_key, chain_key)` cannot be a JSON object key, so `RecallRun.combs` is keyed by the string `"<entry_key>|<chain_key>"`.
  - **Scoring modules.** `scoring.py` would pass ~300 lines, so it is three pure modules: `scoring.py` (recipe outputs), `scoring_metrics.py`, `scoring_paired.py`.
  - **Lock name.** There is no `bench_lock` function: the lock is `BenchmarkLock.acquire(root, benchmark_id, runner)` (`benchmark/bench_lock.py`), used with lock id `recall`.
  - **Timeout refusal.** `benchmark_common` has no timeout check. `run` uses `check_review_timeout` (`benchmark/grading_config.py`) as `benchmark_grade.py` does.
  - **Pair seed.** `pair_seed(benchmark_id, key_a, key_b)`: `benchmark_id` is `<set name>@v<version>`, the keys are the two row keys.
  - **How a recipe selects stored entries (D2, D4, D10).** `report` matches a recipe stage to an entry by the stage's identity, (`config_key`, `effort_sent`) per D4, so aliases with the same model and settings that send the same effort are one row. Live identities come from an injected `StageIdentityResolver` (protocol defined in `scoring.py`; the live implementation is Task 22). An entry whose `source` is `import:*` matches when its `alias` equals the recipe's alias. Each distinct stage identity found becomes its own row; a recipe with both live and imported matches gives separate, flagged rows. `entry_key` (which includes configured effort) is used only by `run`, to decide whether a stage is already stored: only live `entry_key` matches count as stored.
  - **Overrides file (D10).** Not named in the design: `user/reference/review-recall-overrides.yaml`, outside the cases folder so `cases add <dir>` never reads it. Schema and precedence in Task 13.
  - **Slash command parity.** `commands/sq/benchmark.md` documents every `sq benchmark` subcommand. It gains the recall subcommands (Task 29).
  - **Stale text.** D11, D13 and walkthrough step 7 still say "PM to confirm" / "pending PM confirmation", and D13 keeps its "If not" fallback sentence; both decisions are made (PM decisions 20261116).
- Shared names (defined once, never compared as literals): `RECORD_TYPE_RECALL_*` in `metrology/models.py`; `StageKind`, `CombVerdict`, `StageOutcome`, `RecallLeakVerdict`, `UNKNOWN_MARKER` in `recall_run_models.py`; `HitVerdict`, `FindingGrade`, `LabelerKind` in `recall_label_models.py`; the decisions word table in `decisions.py`; `MIN_RECALL_PAIRED_CASES = 8` (the runbook floor; `paired_stats.MIN_PAIRED_CASES` is 5 and is not used) in `scoring_paired.py`; `EXIT_CAP_REACHED` reused from `cli/commands/benchmark_grade.py`.
- Failure modes: every D8 row (both tables) is asserted, outcome plus log record, in the task that produces it: `cases add` validation and `git show` (Tasks 5, 7); import files and refs (Tasks 11, 13); auth preflight (Task 24); stage calls (Task 23a) and leak verdicts (Task 23b); sandbox and fetch, caps (Task 25); orphan, retry, `write_record` (Task 26); lock (Task 27); incomplete stages (Task 16).
- Tests live in `tests/benchmark/recall/` (plus `tests/benchmark/test_config_keys.py`, `tests/cli/`). They run no model and no git outside fixtures; process runner, sandbox factory and clock are injected. Pyright covers `src` only. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Nothing here pushes or merges.
- Effort 5/5. Next planned slice: 431 (Implementation Report from Run Records).

## Tasks

### Task 1: Commit the task file, correct the design, create the branch
- [x] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file, commit it by path as `docs: revise slice 430 tasks`
  - [x] Success: `git status --short` does not list the task file
- [x] Edit `user/slices/430-slice.real-bug-review-recall.md` so it states each design-gap bullet in the Context Summary: Component Structure (model homes, the scoring modules, and the modules `stage_identity.py`, `leak_check.py` and `run_loop.py`, which the component table lacks), D2 and D11 (the comb alias is `luna-r`, the OpenRouter alias RESULTS.md section 5 measured; plain `luna` is the Codex alias, which was not measured), D4 (`combs` key), D9 (lock name, timeout check), D10 (overrides path), D12 (seed), D3 (among `person` labelers the newest `updated` wins, PM-approved 20261116; no disagreement listing), the report identity rule (D4: (`config_key`, `effort_sent`); `entry_key` only for `run`'s stored-entry check) and a Non-functional line (recall runs serially under D9 as a PM-run benchmark, so it has no load-test tier). Remove the "PM to confirm" sentences in D11 and D13, D13's "If not, the three squadron cases list their files in `extra_locations`..." sentence, and "pending PM confirmation" in walkthrough step 7
  - [x] Success: `grep -n "PM to confirm\|pending PM\|bench_lock\|squadron history not read" project-documents/user/slices/430-slice.real-bug-review-recall.md` finds nothing; the design names `metrology/recall_*_models.py`, the string `combs` key, the three scoring modules, `BenchmarkLock`, `check_review_timeout`, the overrides path, the entry-selection rule, the person-labeler rule, the no-load-test line, `luna-r` in D2 and D11 and the three missing modules in the component table

**Commit**: `docs: correct slice 430 design for model homes, lock, entry selection`

- [x] `git checkout -b 430-slice.real-bug-review-recall <target>` (or switch to it if it exists)
  - [x] Success: `git branch --show-current` prints the slice branch

### Task 2a: Case models (D1, D3, D10)
- [x] Convention for Tasks 2a–2c: one `*_models.py` per record type, holding that record's payload and its part models, like the existing `metrology/*_models.py` modules (for example `grade_models.py`, `snapshot_models.py`). The one-class-per-file rule applies to services, not payload parts
- [x] `metrology/recall_case_models.py`: `BugLocation` (file, symbol optional, reason optional; `reason` required when it is an extra location), `KnownBug` (id, description, proof list, `original_review` enum `missed|reported`, `locations` frozen list, `extra_locations`), `RealBugCase` (project_id, case_id, name, kind, repo, host_repo, distribution, base, head, status enum `verified|checked`, hand_run_id optional, bugs, notes), `RecallCaseSet` (name, version, case_ids, created). `case_id_for(case)`: `rbcase-<sha12>` of canonical JSON (sorted keys) of exactly: `kind`, the repo path's basename, `base`, `head`, `host_repo`, and the bugs sorted by id, each as (`id`, `description`, `proof`, `original_review`, resolved locations, extra locations with symbol and reason). `case_set_id(name, version)`: `rbset-<name>-v<version>`
- [x] Tests `tests/benchmark/recall/test_case_models.py`: case id stable across field order and repo parent path, changed by any bug or location change; extra location without reason rejected; round-trip JSON
  - [x] Success: tests pass

### Task 2b: Run models (D4, D5, D6, D8)
- [x] `metrology/recall_run_models.py`: enums `StageKind` (`review`, `comb`), `CombVerdict` (`KEEP`, `DROP`, `UNDECIDED`), `StageOutcome` (`ok`, `config_failure`, `harness_failure`), `RecallLeakVerdict` (a StrEnum whose three scan members take their values from `LeakVerdict.LEAKED`, `LeakVerdict.NO_LEAK_DETECTED` and `LeakVerdict.SCAN_UNAVAILABLE` in `metrology/benchmark_replay_enums.py`, plus `confined` and `not_scanned`; the strings are not retyped); constant `UNKNOWN_MARKER = "unknown"`. Models: `StageConfig` (model, profile, template_hash, tool_use, max_output_tokens; each its value, `None` when the alias leaves it unset, or the unknown marker where D10 says so) with `config_key` (sha256 of the five); `StageUsage` (cost_usd, cost_basis, duration_s, turns, tool_calls); `RecallFinding` (finding_id, content_key, severity, category via `map_historical_category`, raw_category, location, title, description); `CombDecision` (verdict, reason); `StageEntry` (fields per D4 including `outcome` + `outcome_reason`, `leak`, `source`, `case_set`, `raw_ref`, `alias`, `created`, `duplicate_decisions`, `unknown_ids`); `RecallRun` (case_id, run_index, `reviews: dict[str, StageEntry]`, `combs` keyed by `"<entry_key>|<chain_key>"`, `superseded`). Helpers: `entry_key(config, effort_configured)`, `chain_key(comb_entry_keys)` joined with `>`, `content_key(location, title, description)` (sha256, whitespace collapsed), `run_record_id(case_id, run_index)` → `rbrun-<sha12>`
  - Note: plan-billed classification (D9) has no source in code yet — CostBasis has only provider/alias_pricing; resolved in Task 24.
- [x] Tests `tests/benchmark/recall/test_run_models.py`: `config_key` ignores alias and configured effort; `entry_key` includes configured effort; content key whitespace-insensitive; a chain's parent key is the chain minus its last element; round-trip JSON
  - [x] Success: tests pass

### Task 2c: Label models (D3, D5, D10)
- [x] `metrology/recall_label_models.py`: `HitVerdict` (`HIT`, `ADJACENT`, `MISS`), `FindingGrade` (the grade words used in the committed graded files; read them, one enum member each), `LabelerKind` (`person`, `import`), `RecallLabels` (case_id, labeler, labeler_kind, `hits: dict[content_key, dict[bug_id, HitVerdict]]`, `grades: dict[content_key, FindingGrade]`, updated, notes); `labels_record_id(case_id, labeler)` → `rblabels-<case_id>-<labeler>` (labeler sanitized to path-safe characters)
- [x] Tests `tests/benchmark/recall/test_label_models.py`: every grade word in the committed graded files maps to a member; label id path-safe for `import:grid3/BRIEF-B2.md`; round-trip JSON
  - [x] Success: tests pass

### Task 3: Record types and `recall_store` (Database Schema, D4)
- [x] `metrology/models.py`: `RECORD_TYPE_RECALL_CASE`, `RECORD_TYPE_RECALL_CASE_SET`, `RECORD_TYPE_RECALL_RUN`, `RECORD_TYPE_RECALL_LABELS`, and four optional sibling payload fields on `MetrologyRecord`. `schema_version` stays 1
- [x] `benchmark/recall/recall_store.py`: `RecallRecordStore`, wrapping a `MetrologyStore` as `BenchmarkRecordStore` does, with write/get/list for cases; `write_case_set(name, case_ids)` that writes a new version only when membership changed (same members → existing version returned); `get_case_set(name, version=None)` (newest when None) and `parse_set_ref("name@N")`; `get_run`/`put_run` (rewrite via `MetrologyStore.write_record`, `metrology/store.py`; not `benchmark/replay_records.write_record`); `list_runs(case_ids)`; labels get/put/list per case
- [x] Tests `test_recall_store.py` on a temp store: round-trip each type; same membership keeps the version; changed membership bumps it; `name@2` resolves; rewriting a run keeps one record; `write_record` raising surfaces as the exception (handled in Task 26)
  - [x] Success: tests pass; pyright zero errors

**Commit**: `feat: add recall case, run and label records and store`

### Task 4: Fixture bug repo (test infrastructure, walkthrough step 5)
- [x] `tests/benchmark/recall/fixtures/bug_repo/build.py` (pattern: `tests/benchmark/slice_repos.py`), callable from tests and as a script: `build(out_dir)` creates `out_dir/repo/`, a small git repo with a base commit, a buggy head commit and a later fix commit, and `out_dir/case.yaml` with that repo path, base/head shas, `host_repo`, `distribution` and one bug B1 whose proof is the fix commit. Run as a script with no argument, `out_dir` is the script's own folder, which gives the design's `tests/benchmark/recall/fixtures/bug_repo/case.yaml`. A `.gitignore` in that folder lists `repo/` and `case.yaml`
- [x] `tests/benchmark/recall/conftest.py`: a `bug_repo` fixture calling `build(tmp_path)`; a fake `ProcessRunner` that records argv and returns scripted results; a fixed clock
  - [x] Success: a smoke test builds the repo and `git rev-list --count base..head` in it is 1; `git status --short` after running the script lists only the new `.py` and `.gitignore` files

**Commit**: `test: add recall fixture repo and fakes`

### Task 5: Fetch timeout key, case-file loader and validator (D1, D7)
- [x] `config/keys.py`: add `BENCHMARK_RECALL_FETCH_TIMEOUT_KEY` (`benchmark.recall_fetch_timeout_s`) and its `ConfigKey` next to the other benchmark keys: `type_=int`, `default=120`, description naming the `git show` and D7 commands it bounds (local-repo git calls; it is independent of the sandbox's own fixed bound). Test in `tests/benchmark/test_config_keys.py`: present, default 120, type int
- [x] `benchmark/recall/case_models.py`: `load_case_file(path) -> CaseFileSpec` with PyYAML; schema check; `~` kept unexpanded in the record, expanded at use. Refuse: missing required field, unknown `status`/`original_review`, issue proof (`#n`) with no `extra_locations`, extra location without reason
- [x] `derive_locations(spec, runner, timeout)`: for each commit proof, `git show --name-only --format= <sha>` in the case repo (timeout `benchmark.recall_fetch_timeout_s`); every changed file becomes a `BugLocation`, unfiltered; then append `extra_locations`. A failing or timed-out `git show` raises a `CaseFileError` naming the commit
- [x] Tests `test_case_loader.py` with the fake runner and the fixture repo: derived list equals the fix commit's files; issue proof without extras refused; `git show` failure and timeout each refused with the commit named
  - [x] Success: tests pass

### Task 6: `RecallKind` seam and `CodeKind` (D14), with the review sandbox (D7)
- [x] `benchmark/recall/review_sandbox.py`: context manager entering `HistoryFreeSandbox(start_sha=head)` unchanged, then via the injected `ProcessRunner` (timeout `benchmark.recall_fetch_timeout_s`): `git rev-list --count base..head` in the source repo, `git -C <tree> fetch --depth <count+1> <repo> <head>`, `git -C <tree> rev-parse --verify base^{commit}`. Any failure raises `SandboxError` with the reason (missing repo, sandbox build failure, timeout, fetch error, base unreachable); no refs created
- [x] `benchmark/recall/kinds.py`: `RecallKind` protocol (`validate`, `open_sandbox`, `review_argv` per D14), a registry keyed by `kind`, `get_kind(kind)` raising on unknown. `CodeKind`: `validate` = Task 5 loader + `derive_locations`; `open_sandbox` = `review_sandbox`; `review_argv` = `[sq, "review", "code", "--diff", base, "--model", alias, "--no-save", "--output", "file", "--output-path", out]`
- [x] Tests `test_review_sandbox.py` (fixture repo, real git): tree has head and base, and not the fix commit; each failure gives `SandboxError` with its reason (Task 25 asserts the outcome and log). `test_kinds.py`: registry lookup; unknown kind raises; a stub kind registers and is returned
  - [x] Success: tests pass; `git diff <target> -- src/squadron/replay/history_free_sandbox.py` is empty

### Task 7: CLI group, `cases add` and `cases list` (D1, D8)
- [x] `cli/commands/benchmark_recall.py`: Typer subgroup `recall` registered in `cli/commands/benchmark.py` via `add_typer`; a services factory (store, runner, sandbox factory, clock, sq path) as in `benchmark_grade.py`/`grade_services.py`; a `recall_lock()` helper around `BenchmarkLock.acquire(<benchmark root>, "recall", runner)` (live holder → ERROR naming the pid, exit 1; dead holder → WARNING, taken over), used by every writing command. Split into `benchmark_recall_*.py` modules once past ~300 lines
- [x] `cases add <path>... --set NAME`: expand dirs to `*.yaml`; validate and derive every file first; on any failure print every failing file and reason, log ERROR, exit 1, write nothing; else write cases and `write_case_set`. Look up the kind via the registry, never branch on it
- [x] `cases list [--set]`: sets with versions; per case name, kind, status, bug count, each bug's locations and extras with reasons, and whether the repo path exists
- [x] Tests `tests/cli/test_benchmark_recall_cases.py`: happy path on the fixture case; two bad files → both listed, exit 1, store empty, ERROR logged; a `git show` failure → refused naming the commit, store empty, ERROR logged; rerun with same files keeps v1
  - [x] Success: tests pass

**Commit**: `feat: add sq benchmark recall cases add and list`

### Task 8: The 17 case files and four set lists (D1, D13)
- [x] Write one YAML file per case under `user/reference/review-recall-cases/` from `user/reference/review-recall-cases.md` (17 cases, 21 bugs; controls and `cf9006d5-N1` are notes, not bugs). Fill `host_repo` from each repo's `origin` remote (`git remote get-url origin`) and `distribution` from the head commit's `pyproject.toml`/`package.json` (`git show <head>:pyproject.toml`). Add `extra_locations` (with reason) only where the case text cites a file the proof commit did not change (`git show --name-only` of the proof). Files cited only by graded hits are found by Task 15's gate test. If a case's repo path, `origin` remote, manifest or proof commit cannot be read, write a line starting with `BLOCKED:` and the reason under this task, leave it unchecked, and stop; do not guess a value
  - Note: batch-2 bases written as the resolved full sha of `<sha>^`; all shas full-length; `real-bugs-nonsquadron` has 18 bugs.
- [x] `tests/benchmark/recall/fixtures/proof_files.json`: proof sha → file list, captured with `git show --name-only --format=` for every commit proof in the 17 case files, so tests can derive locations with a fake runner and no git
- [x] `user/reference/review-recall-sets.md`: one `##` heading per set (the set name), each followed by a fenced block listing one case-file path per line, relative to `user/reference/review-recall-cases/`. The sets: `real-bugs` (17), `real-bugs-original` (first 10, 14 bugs), `real-bugs-original-no-u103` (9, 13), `real-bugs-nonsquadron` (14)
- [x] Test `test_committed_cases.py`: every committed case file passes the schema check (fake runner, no git); counts 17 cases / 21 bugs; each set list, parsed in that exact format, resolves to existing files with the stated counts
  - [x] Success: tests pass. Case locations that Task 15's gate test finds missing are added when that test runs and are committed at the marker after Task 20. The real store is not written here; it is first written in Task 30, so a case-file edit before then needs no record migration

**Commit**: `docs: add the 17 real-bug case files and set lists`

### Task 9: Decisions parser (Patterns: decisions parser)
- [x] `benchmark/recall/decisions.py`: `parse_decisions(raw, finding_ids) -> DecisionParse` (decisions dict, duplicate count, unknown-id count). One word→`CombVerdict` table. Lenient: `F3: KEEP — reason`, `F3 - KEEP: reason`, `**F3**: keep`, hyphen/en/em dash, any case, surrounding markdown. First verdict per id wins. Ids not in `finding_ids` are counted. Missing ids become `UNDECIDED`. No parseable line at all returns an empty parse (caller makes it `config_failure`)
  - Note: also accepts the trailing-verdict form (`### [NOTE] F1: title — DROP`) seen in real outputs; on all 480 hand-run comb outputs the parser matches the hand-run decision for all 2,086 decided findings.
- [x] Fixtures: copy `raw_output` from at least one Claude, one Codex and one OpenRouter comb output in `20261113-comb/out/` into `tests/benchmark/recall/fixtures/decisions/`
- [x] Tests `test_decisions.py`: each format variant; real fixtures parse with no `UNDECIDED` where the output decided every id; duplicate and unknown counts; empty output gives empty parse
  - [x] Success: tests pass

**Commit**: `feat: add lenient comb decisions parser`

### Task 10: Recipes (D2) and recipe files
- [x] `benchmark/recall/recipe.py`: `Recipe` (name, reviewers, pool, combs); loader refuses empty reviewers, `pool: true` with one reviewer. `required_stages(recipe)`: per reviewer one review stage, plus one comb stage per chain prefix (luna-r, then luna-r>opus-high)
  - Note: `pool` defaults to false and `combs` to none, so single-reviewer files are `name` + `reviewers`; duplicate reviewers are also refused.
- [x] Recipe files under `user/reference/review-recall-recipes/`: `haiku-xhigh`, `sol`, `sonnet-high`, `sonnet`, `luna` (single reviewers); `haiku-sol-opus` (fan-out haiku-xhigh + sol, comb `[opus-high]`); `haiku-sol-pool` (pool); `haiku-sol-luna-opus` (D11: fan-out, combs `[luna-r, opus-high]`). Section 5's recipes are built in the reproduction test (Task 20), not committed
- [x] Tests `test_recipe.py`: refusals; stage expansion for fan-out + two-stage comb; every committed recipe file loads
  - [x] Success: tests pass

**Commit**: `feat: add recall recipes and recipe files`

### Task 11: Import review outputs (D10)
- [x] `benchmark/recall/hand_run_import.py`, part 1: read `*.json` directly under `20261112-grid1/`, `20261112-grid2/`, `20261113-grid3/` (`<case>-<config>-<run>.json`); map `<case>` to a case by `hand_run_id` (no case → skip, listed); skip a file whose sha256 matches a file already read, listed as a duplicate (all 27 grid1 files); build `StageConfig` per D10's review table (template marker `unknown:<template_name>@<squadron_version>`, `tool_use` from `tools_given`: non-empty `true`, empty `false`; `effort_sent` null); findings → `RecallFinding` with content keys; raw output into the `REVIEWS` sidecar; `leak: not_scanned`; `source: import:<folder>`. Unreadable/invalid/missing-field file → WARNING, skipped, listed
  - Note: Codex outputs have `tools_given: null`, imported as `tool_use: unknown` (design D10 updated). Read order grid2, grid3, grid1 so the 27 grid1 copies are the duplicates. Review-output reading is shared in `benchmark/recall/review_output.py`; plan types in `import_plan.py`.
  - Note: PM decision 20261118 resolved the `entry_key` collisions (57 of 723 files): duplicates are skipped by content hash and `tool_use` comes from `tools_given`. Checked on the committed files: 696 entries, no collisions. Design D10 updated.
- [x] Return an `ImportPlan` (run records keyed by id, skipped list, unknown-field counts); no store writes here
- [x] Tests `test_import_reviews.py` on the real committed files: 696 review entries across 51 run keys, 27 grid1 files listed as duplicates; an unreadable file, an invalid-JSON file and a missing-field file are each skipped with WARNING; unknown counts present
  - [x] Success: tests pass

### Task 12: Import comb outputs (D10)
- [x] Part 2: `20261113-comb/out/<comb>/<case>-<reviewer>-<run>.json`; attach to the review entry of that case/reviewer/run; `luna-r+opus-high` becomes chain luna-r then opus-high (parent = the luna-r entry). Comb config per D10's comb table (`comb.yaml@9bc108a6#<folder>`). Decisions from the stored `raw_output` via Task 9's parser. F-ids are positional within each comb call (a stage-two call renumbers only the findings stage one kept), so map every F-id to its finding through the file's `refs`, never by number. Ignore the `P*` entries in `decisions`: those stage-one drops are already in stage one's entry. An id with no verdict is `UNDECIDED` (no DROP default)
  - Note: 4 two-stage files where stage one kept nothing import as `ok` with no decisions (no call was made).
- [x] Tests `test_import_combs.py` on the real files: 480 comb entries; the two-stage chain key has two parts; two comb folders that differ only by name have different `config_key`s; on a two-stage file where stage one kept two findings, stage two's decisions land on exactly those two findings and the others keep stage one's DROP
  - [x] Success: tests pass

### Task 13: Import grading passes, hit labels and overrides (D3, D5, D10)
- [x] Part 3: the four passes in D10's table, one labeler `import:<brief>` each, one `RecallLabels` per graded case. Resolve `<config>/<run>/<index>` refs to the imported finding's content key (unresolved → WARNING, skipped, listed). `matched` refs take the named issue's grade and `known`. `known: Bn` → `HIT` for Bn; other issues' members → `MISS` for every bug of the case; cf5e840c partial → `HIT`. Later pass in table order wins on conflicts; conflicts counted and listed
- [x] `user/reference/review-recall-overrides.yaml`: a list of entries `{case: <case name>, issue: <issue id>, grade: <FindingGrade member>, reason: <text>}`, holding the RESULTS.md section 12 adjudications (921-I9 REAL, 197-I14 MINOR). Each entry sets that grade on every content key that is a member of, or matched to, the issue in any pass of that case. They are written as one `RecallLabels` per case with labeler `person:results-section-12` and `labeler_kind` `person`. An entry whose case or issue is not found → WARNING, listed as skipped
- [x] Precedence when reading labels (used by Tasks 15 and 17): for hits and for grades, a `person` labeler beats every `import:` labeler; among `import:` labelers the merge rule above already left one value; among `person` labelers the record with the newest `updated` wins
- [x] Tests `test_import_labels.py` on the real files: four import labelers present; a conflict is listed; the two overrides land under `person:results-section-12` and win over the pass grades; an unknown override issue and a bad ref are each skipped with WARNING; two person labelers disagreeing → newest wins
  - Note: the committed passes have no conflicts; the conflict test uses a synthetic later pass. Precedence lives in `label_precedence.py`; overrides in `hand_run_overrides.py`.
  - [x] Success: tests pass

### Task 14: `import` command (D10, D8)
- [x] `import <results-dir> --set NAME [--dry-run]`: take the recall lock (Task 7 helper), build the plan, print counts (review/comb entries, run records, label records, unknown-field counts, grade conflicts, skipped files and refs); without `--dry-run` write records; second import writes nothing and says "no changes"; exit 1 at the end if anything was skipped
- [x] Tests `tests/cli/test_benchmark_recall_import.py`: dry run writes nothing; real run then rerun reports no changes; skipped file → exit 1
  - [x] Success: tests pass; walkthrough step 2 counts match (696, 480, 51) on a temp store

**Commit**: `feat: add sq benchmark recall import for hand-run results`

### Task 15: Hit rule (D3)
- [x] `benchmark/recall/hit_rule.py`: `cited_paths(finding)` (lenient: `path:12-30`, `path#symbol`, `path (text)`, bare basenames with an extension, from location and description); `path_matches(a, b)` (suffix at `/` boundary); `gate(finding, bug) -> GateResult` (`candidate` | `decided_miss`); `resolve(finding, bug, labels) -> HIT|ADJACENT|MISS|UNDECIDED` with Task 13's precedence
  - Note: all 86 imported HIT labels pass the gate, 307 B1 included; no case file needed an `extra_locations` entry. A cited path must end in a listed source extension (`SOURCE_EXTENSIONS`), so dotted code references are not read as files.
- [x] Tests `test_hit_rule.py`: each path form; no path → candidate for every bug; mismatch → decided miss; label precedence; **every imported `HIT` label passes the gate**, on a temp store the test fills by running `cases add` on the committed case files (fake runner answering `git show` from `proof_files.json`) and writing the `ImportPlan` of Tasks 11–13 to it. Expect 307 B1 (`cutover_304_first_purchase.py`) to need checking. If a hit fails, add an `extra_locations` entry with reason to that case file and rerun; do not loosen the gate
  - [x] Success: tests pass

### Task 16: Scoring — recipe outputs per (case, run) (D2, D3, D8)
- [x] `benchmark/recall/scoring.py` (pure, no I/O): entry selection per the Context Summary rule, with live identities from an injected `StageIdentityResolver` protocol (`resolve(alias, stage_kind) -> (config_key, effort_sent)`), so this module imports nothing from Tasks 21–22; per (case, run) build each reviewer's final kept set in lower and upper form (`UNDECIDED` → drop / keep; stage-one `UNDECIDED` not sent to stage two; stage-one `DROP` stays `DROP` and is never sent; a stage-one `KEEP` takes its stage-two verdict through the finding id); failed comb → zero kept; group by stage identity (`config_key`, `effort_sent`); drop (case, run) on any `harness_failure`, `leaked` or `scan_unavailable` entry, counting by reason; incomplete pairs left out and listed; fan-out = union; pool = per-member values kept for the mean
  - Note: only CONCERN/FAIL findings are scored (`SCORED_SEVERITIES`), the set the hand-run comb, grading and tables used (design D3 updated). Entry selection and the `StageIdentityResolver` protocol live in `scoring_select.py`; the resolver is a `RecallServices` field (`ImportOnlyResolver` until Task 22).
- [x] Tests `test_scoring_outputs.py` with hand-built runs: fan-out union, pool, two-stage chain with a stage-one `UNDECIDED`, harness and leak drops, superseded entries ignored, incomplete coverage listed, live+imported → two flagged rows; with a stub resolver, a recipe naming alias B scores a live entry stored under alias A with the same `config_key` and `effort_sent` as one row
  - [x] Success: tests pass

### Task 17: Scoring — metrics, bounds, real share (D3, D5)
- [x] `benchmark/recall/scoring_metrics.py` (pure): per row: cases, runs, bug-hits / (bugs × runs) low and high, bugs found, runs with a hit, adjacent count, undecided count, findings/run (raw sum), matched nothing (lower-bound set, excludes undecided), real share over graded findings with pass names, graded count, person-checked count and agreement, cost/run with basis, leak counts (`not_scanned` per row), entries from another set version. Pool = mean of members' per-case metrics. Split recall by `original_review`
  - Note: per-pair scoring is in `scoring_pair.py`. A pool's cost/run is the mean of its members' costs (the expected pick).
- [x] Tests `test_scoring_metrics.py`: bounds equal when nothing undecided; matched nothing excludes undecided; pool mean; live entries ungraded
  - [x] Success: tests pass

### Task 18: Scoring — paired intervals (D12)
- [x] `benchmark/recall/scoring_paired.py` (pure): per recipe pair, shared complete cases with nothing undecided; per-case recall and findings/run; `compare_pair` with `pair_seed("<set>@v<n>", key_a, key_b)`; "not distinguishable" when the interval spans zero; "too few cases" below `MIN_RECALL_PAIRED_CASES`; count left out for undecided
- [x] Tests `test_scoring_paired.py`: deterministic interval for a fixed set; spanning zero; too few; undecided cases counted
  - [x] Success: tests pass

### Task 19: Report rendering (API Contracts)
- [x] `benchmark/recall/report_render.py`: text table and footer lines exactly as the design's `report` example; `effort_sent` null printed "not recorded"; recall printed as one number or `low–high`. JSON model with set name/version, n cases, n runs, bounds, matched nothing, real share, cost, paired comparisons, newest entry date
  - Note: JSON model in `report_json.py`; report assembly in `report_build.py`. Stage efforts print on a `Stages <row>:` line per row.
- [x] Tests: `test_report_render.py` (text layout, "not recorded", range form); `test_report_json_schema.py` fixes the JSON schema for 433
  - [x] Success: tests pass

### Task 20: `report` command and reproduction tests
- [x] `report --recipe FILE... --set NAME[@V] [--runs N] [--json]` in the CLI, wiring store reads to the scoring modules and the renderer, with a resolver that knows no live aliases (imported entries match by alias; Task 22 swaps in the live resolver)
  - Note: `--runs` defaults to 1.
- [x] Reproduction tests `test_reproduce_results.py` on imported real records (temp store as in Task 15): section 1 bug-hits 16/12/7/4 of 42 and runs with a hit 14/12/7/4 of 30 over `real-bugs-original`, runs 1..3; 13/9/4/1 of 39 over `real-bugs-original-no-u103`. Section 5 known kept: for each comb, build in the test one fan-out recipe of haiku-xhigh, sol, sonnet-high and sonnet with that one comb; its run-1 count of kept findings carrying a `HIT` label, summed over the four reviewers (so a bug two reviewers found counts twice; RESULTS.md section 5's "known kept"), over `real-bugs-original` is opus-high 14, luna-r 14, sol 10, sonnet-high 8, against 14 for the same fan-out uncombed. Distinct bugs found is 8 for the uncombed fan-out, opus-high and luna-r. `haiku-sol-opus` and `haiku-sol-pool` on run 1 report with no "Left out" and pool = mean of the two single rows
  - [x] Success: all tests pass

**Commit**: `feat: add recall hit rule, scoring and report reproducing hand-run tables`

### Task 21: `comb` template and `_stage` command (D6)
- [x] `src/squadron/data/templates/comb.yaml` (the built-in template directory the loader reads): the prompt from `user/reference/review-recall-results/20261113-comb/comb.yaml` unchanged, with `output: decisions`
  - Note: three comment lines added at the top (the template-classification test requires the "Deliberately NO tool_exclude_patterns" reason in the YAML); the rest is byte-identical to the hand-run file, pinned by a test. `comb.yaml` is classified non-excluding in `tests/review/test_tool_exclusions.py`.
- [x] Hidden `_stage --template comb --input FILE --output FILE`: reads the input file Task 23a writes (a JSON list of `RecallFinding`), renders `F1..Fn` by position in the input list, F1 being the first (the `comb.py render` format), calls `run_review_with_profile` with `allowed_tools: [read_file, list_files, grep]`, writes output (raw text, decisions, usage) to `--output` only after the model call returns
  - Note: `_stage` also takes `--model <alias>` and `--diff <base>` (the call needs the alias; changed files are `git diff --name-only <base> HEAD` in the sandbox). Logic in `benchmark/recall/stage_command.py`; design D6 updated.
- [x] Tests `test_stage_command.py` with a stubbed `run_review_with_profile`: rendered input matches `comb.py render` on one real case; output written; no output file when the call raises
  - [x] Success: tests pass

**Commit**: `feat: add comb template and hidden recall _stage command`

### Task 22: Live stage identity and plan expansion (D2, D4, D9)
- [x] `benchmark/recall/stage_identity.py`: `live_stage_config(alias, stage_kind) -> tuple[StageConfig, Effort | None]` from the alias registry (`get_all_aliases()`, `models/aliases.py`) and `resolve_alias_profile(alias)` (`benchmark/auth_check.py`): model, profile, `tool_use` (absent = allowed, per `ModelAlias`), `max_output_tokens` (absent → `None`), configured effort; `template_hash` = `template_content_hash("code")` for reviews and `template_content_hash("comb")` for combs. Unknown alias or a `None` template hash raises, naming it
  - Note: `live_stage_config` loads the template registry before `template_content_hash`. `LiveStageResolver` predicts effort sent with `effort_sent_by_profile`; an alias unknown to the registry resolves to no live identity (WARNING), so only imported entries match it. The production `RecallServices.stage_resolver` is now `LiveStageResolver`.
- [x] `stage_identity.py` also provides `LiveStageResolver`, implementing Task 16's `StageIdentityResolver` with `live_stage_config`; `report` (Task 20) is changed to use it in place of its import-only resolver
- [x] `benchmark/recall/run_plan.py`, part 1: expand recipes over set cases and runs 1..N to live stage keys via `live_stage_config` and `entry_key`; drop stored (live `entry_key` match; with `--retry-harness` keep harness and dropped-leak entries as pending)
  - Note: stages are `PendingStage`s; comb output files use a sha256 of the comb slot as the filename key.
- [x] Tests `test_stage_identity.py` and `test_run_plan_expand.py`: two aliases with the same settings give one `config_key`; `report` scores a live entry stored under alias A for a recipe naming alias B through the live resolver; different configured effort gives different `entry_key`s; unknown alias raises; expansion of fan-out + two-stage comb; stored entries skipped; imported entries never count as stored
  - [x] Success: tests pass

### Task 23a: Stage runner and outcomes (D6, D8)
- [x] `benchmark/recall/stage_runner.py`: `run_stage(...) -> StageEntry`. Build a `ScrubbedEnvironment` with the alias profile's `CredentialGrant` only; cwd = sandbox; argv from the kind's `review_argv` or the `_stage` argv, using the `resolve_sq_path()` path passed in; timeout `benchmark.review_timeout_s`; output under `recall-out/<record id>/<stage key>.json`. For a comb, first write the parent entry's kept findings (review findings, or the previous comb's `KEEP`s; `UNDECIDED` not sent) to `recall-out/<record id>/<stage key>.input.json`
- [x] After the call: parse the output (review findings → `RecallFinding` with content keys; comb → Task 9 parser over the rendered F-ids, then each F-id mapped to its `finding_id` by position in the comb input file), store the raw output in the `REVIEWS` sidecar (`ContentSidecars`) and set `raw_ref`; `config` from Task 22; `effort_sent` from the output's usage record (`read_effort_sent`, `pipeline/usage_capture.py`), null when not recorded
  - Note: `effort_sent` is read from the output's `effort` field, which review_client writes only when the effort was sent (slice 931 D4); neither `sq review code` nor `_stage` writes an `effort_sent` key (design D6 updated). Parsing lives in `stage_ingest.py`, shared with orphan ingest.
- [x] Outcomes: no start / no output file → `harness_failure` + exit code + stderr tail; timeout or unparseable output → `config_failure`; comb partial → `ok` with `UNDECIDED`s; each logged WARNING with case, run, stage
  - Note: a comb whose input is empty (the parent kept nothing) is recorded `ok` with no decisions and makes no call. A missing profile credential is a `harness_failure`. The scrubbed home is kept until the loop stores the entry.
- [x] The entry's `leak` comes from an injected `LeakChecker` (`check(stage_context) -> RecallLeakVerdict`); Task 23b supplies it
- [x] Tests `test_stage_runner.py` (fake runner, stub `LeakChecker`), each asserting outcome and WARNING log: subprocess cannot start; exits without output file; review timeout; review output unparseable; comb timeout; comb output with no decision line; comb partial. Also: comb input file holds only the parent's kept findings; `raw_ref` resolves in the sidecar
  - [x] Success: tests pass

### Task 23b: Leak verdicts (D6, D8)
- [x] `benchmark/recall/leak_check.py`, implementing Task 23a's `LeakChecker`: `transcript_source_for(profile)`; with a source, `leak_scan.scan(source, scrubbed_home, build_leak_rules(...))` with the D6 inputs (tree, home, output_dir, real_home, repo_root, `installed_package_location()`, `uv_cache_dir(runner)`, distribution, host owner/repo); `leaked` and `scan_unavailable` logged WARNING with case, run, stage and verdict; none and jailed builtins → `confined`; neither → raise (plan refuses earlier, Task 24)
  - Note: "jailed builtins" = profiles whose provider type is `openai` (`JAILED_BUILTIN_PROVIDERS`); `leak_judgeable(profile)` is the plan-time check.
- [x] Tests `test_leak_check.py` (fake transcript source), each asserting verdict and WARNING log: `leaked` (a scripted transcript reading the case repo by absolute path); `scan_unavailable`. Also: scan inputs include the case repo and host repo; the `confined` path never calls `scan`; the checker is wired into Task 23a's runner
  - [x] Success: tests pass; `git diff <target> -- src/squadron/benchmark/leak_rules.py` is empty

**Commit**: `feat: add recall stage identity and stage runner with leak scan`

### Task 24: Run plan — bound, refusals, preflight (D6, D9)
- [x] `run_plan.py`, part 2: refuse a profile with no transcript source and no jailed builtins (exit 1); per-call figure = max observed `cost_usd` for the `config_key`, else `--call-cost` (refuse when missing); bound = sum + largest once, labeled "estimate" or "from --call-cost"; plan-billed count, requiring `--max-plan-calls` when any; `render_bound` wording after `grade_plan.render_bound`
  - Note: run plan part 2 is `benchmark/recall/run_bound.py` (run_plan.py holds part 1). Plan-billed = profiles whose provider is `openai-oauth` (Codex; `PLAN_BILLED_PROVIDERS`), resolving the Task 2b note. Per-call figures come from live entries only (imported config keys never match live ones), so walkthrough step 7 also needs `--call-cost`; step 5's `luna` is Codex and needs `--max-plan-calls` (walkthrough corrections in Task 30). `require_review_timeout` wraps `check_review_timeout`.
- [x] Preflight: `run_auth_check` for distinct profiles with `benchmark.auth_probe_timeout_s`; any non-`yes` → ERROR naming the profile, exit 1, nothing recorded
- [x] Tests `test_run_plan.py`: refusals (no `--max-cost`, no timeout via `check_review_timeout`, no `--call-cost`, no `--max-plan-calls`, auth failure with ERROR log and nothing recorded); bound arithmetic and labels; the committed `haiku-sol-luna-opus.yaml` over the 14 committed `real-bugs-nonsquadron` case files loaded into a temp store (fake runner, no calls) gives a bound with the plan-billed count (D11 criterion)
  - [x] Success: tests pass

### Task 25: Run loop — sandboxes, serial dispatch, caps (D7, D8, D9)
- [x] `benchmark/recall/run_loop.py`: `run_pending(plan, deps) -> LoopResult`, with store, sandbox factory, stage runner and budget injected. Per case: one sandbox per invocation, reused for that case's stages and removed after; stages one at a time; `ReviewBudget.before_review()` / `after_review(cost)` around each call; stop before the (N+1)th plan-billed call. `SandboxError` → every pending stage of that case gets a `harness_failure` entry with the reason, WARNING logged. Each entry is stored in its run record as soon as it exists. Result says complete or capped, with what is left
  - Note: `KindSandboxFactory` opens sandboxes through the case kind; `live_loop_deps` wires the real stage runner, orphan ingest and home removal. Plan-billed calls skip `after_review`; `before_review` gates every call.
- [x] Tests `test_run_loop.py`: missing repo, sandbox build failure, fetch error, fetch timeout and base unreachable each give `harness_failure` with reason and WARNING; sandbox removed on success and failure; serial order; dollar cap and plan cap stop with records kept; the first call always runs under a tiny cap (`before_review` raises only once spend reaches the cap)
  - [x] Success: tests pass

### Task 26: Run loop — resume, orphans, retry, write failure (D8)
- [x] In `run_loop.py`: before dispatching a stage, an output file in `recall-out/` with no entry is ingested (leak scan if its scrubbed home is still present), else the call is repeated with a WARNING that the earlier cost was spent without a record. `--retry-harness` stores the new entry and moves the replaced one to `superseded`. A `write_record` failure logs ERROR, stops the loop with an error result, and leaves the output file
  - Note: an output file is treated as an orphan only when the stage is not a `--retry-harness` replacement (a leak-dropped entry's old output is overwritten by the retry).
- [x] Tests `test_run_loop_resume.py`: rerun of a complete plan dispatches nothing; orphan with home present → ingested and scanned; orphan with home gone → repeated with WARNING; retry supersedes and deletes nothing; `write_record` failure → ERROR, output file kept, next run ingests it
  - [x] Success: tests pass

**Commit**: `feat: add recall run plan and run loop`

### Task 27: `run` command and end-to-end test (D6, D9, Integration Requirements)
- [x] `run` in the CLI with the API Contracts options: `recall_lock()`; plan refusals; preflight; print bound; `run_pending`; exit 0 complete, `EXIT_CAP_REACHED` capped (print remaining), 1 refused or error; "0 stages to run" when nothing is pending; `--case NAME` filters
  - Note: `run`'s collaborators are one `RecallServices.live` field (`LiveRunServices` in `live_services.py`: harness env, sq path, auth check, leak checker, sandboxes, alias config). `RecallRefusal` moved to `refusal.py` to avoid an import cycle. `--runs` defaults to 1; `--case` is repeatable.
- [x] Tests `tests/cli/test_benchmark_recall_run.py` (fake services): bound printed before the first call; `run` with the committed `haiku-sol-luna-opus.yaml` on the `real-bugs-nonsquadron` case files (loaded into a temp store) prints its bound and makes no call; exit codes 0/1/2; lock held by a live process → ERROR with pid, exit 1; dead owner → WARNING, taken over
  - Note: the D11 run test gives every case a sandbox failure (the source repos are not on the test machine), so it prints the bound (84 stages, 14 plan-billed) and makes no model call.
- [x] End-to-end test `test_run_end_to_end.py` on the fixture repo with a scripted `sq` subprocess: two review entries with leak verdicts, a leaking call recorded `leaked` and dropped from `report` with the drop counted; a stub kind registered in the registry runs one stage
  - Note: the scripted `sq` writes its transcript into the scrubbed home; a test transcript source reads it, and `TranscriptLeakChecker` scans it with the real 424 rules.
  - [x] Success: tests pass

**Commit**: `feat: add sq benchmark recall run`

### Task 28: `label` command (D3)
- [x] `label --set ... [--recipe ...] [--case ...]`: list each undecided candidate with case, bug id and description, bug files and symbols, content key, severity, location, title, description, affected recipes and runs. `--hit KEY BUG HIT|ADJACENT|MISS --by NAME` writes the person `RecallLabels` for that case (labeler `person:<NAME>`, rewrite in place); refuse unknown key or bug
  - Note: logic in `benchmark/recall/label_candidates.py`. Without `--recipe` the candidates come from every scored finding of the set's stored reviews; with it, from the recipes' upper-bound kept findings (`--runs` sets the run range). A content key found in several cases needs `--case`.
- [x] Tests `tests/cli/test_benchmark_recall_label.py`: listing on hand-built records; recording a label removes it from the list and the report's undecided count drops; unknown key refused
  - [x] Success: tests pass

**Commit**: `feat: add sq benchmark recall label`

### Task 29: Docs — runbook, slash command, CHANGELOG
- [x] `user/reference/review-recall-runbook.md`: "Running a reviewer on a case" and "Scoring" point to `sq benchmark recall` commands; the hand-run method stays as the fallback for outside tools
- [x] `commands/sq/benchmark.md`: a recall paragraph listing `cases add`, `cases list`, `import`, `run`, `label`, `report` with key options and exit codes, matching the existing style (cost warning on `run`)
  - Note: `tests/cli/test_benchmark_slash_command.py` now checks every option of the six recall subcommands against their signatures in benchmark.md.
- [x] `CHANGELOG.md`: one short user-facing bullet for `sq benchmark recall`
  - [x] Success: `grep -n "benchmark recall" commands/sq/benchmark.md project-documents/user/reference/review-recall-runbook.md CHANGELOG.md` finds each file

**Commit**: `docs: point recall runbook and slash command to sq benchmark recall`

### Task 30: Final validation and walkthrough
- [x] `ruff format`, `ruff check`, `pyright` (zero errors), `pytest tests/benchmark/recall tests/benchmark/test_config_keys.py tests/cli -q`; `git diff <target> --stat -- src/squadron/metrology/grade_models.py src/squadron/cli/commands/review.py src/squadron/replay/history_free_sandbox.py src/squadron/benchmark/leak_rules.py`
  - [x] Success: all pass; the diff is empty
- [x] Walkthrough steps 1–6 of the design on the real store. Before step 5, run `python tests/benchmark/recall/fixtures/bug_repo/build.py`. Step 5 uses `luna` with `--max-cost 0.05` (LLM spend is pre-authorized). Step 7 is not run. The design's walkthrough names recipes as `recipes/<name>.yaml`; the files are `project-documents/user/reference/review-recall-recipes/<name>.yaml`, so use those paths
  - Note: corrections recorded in the design walkthrough: run via `uv run sq` until released; `luna` is Codex, so step 5 needs `--max-plan-calls` and its cap stop is the plan cap (overshoot shown with a priced `luna-r` call); step 7 needs `--call-cost`. Step 5 found that the seeded user config `cwd` key sent `sq review code` outside the sandbox; the code kind now passes `--cwd .` and `--retry-harness` reran the two failed calls.
  - [x] Success: each step's expected output observed. A mismatch is recorded as `BLOCKED:` under this item with the command and its output, and work stops there
- [x] DEVLOG entry (Session State Summary format); slice design `status: complete`; slice plan entry 430 checked
  - [x] Success: files updated

**Commit**: `docs: complete slice 430 and record walkthrough results`
