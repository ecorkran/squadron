---
docType: tasks
slice: adoption-baseline-command
project: squadron
lld: user/slices/404-slice.adoption-baseline-command.md
dependencies:
- 400
- 323
projectState: 0.24.10 released; slices 400, 401, 402 and 403 complete; 440 removed
  sq probe; slice 404 design complete, all decisions decided
dateCreated: 20261030
dateUpdated: 20261030
status: in_progress
turns: 45
promptTokens: 3825664
cachedTokens: 3703628
cacheWriteTokens: 121952
completionTokens: 36567
durationSeconds: 448.4
costUsd: 2.448319
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 2.4483190000000006
    completionTokens: 36567
revision_number: 2
---

# Tasks: Adoption Baseline Command

## Context Summary
- Slice 404 adds `sq metrology baseline [PATH] [--profile P] [--model M]`: one command that runs every config check up front, prints a scope report, takes a code snapshot of the clean HEAD, then runs 323's audit variance series at that commit and writes its noise floor. No new record type, metric, config key or store change.
- All decisions are in the slice design (the `lld` above), D1–D6. Each task cites its decision; read it before starting. The module table is under Architecture → Component Structure, the failure-mode table is in D6, the output shape and library contracts are under Implementation Details.
- Prerequisites on `main` (all complete): 400's snapshot package (`metrology/snapshot/`: `preflight`, `effective_exclusions`, `resolve_files`, `take_snapshot`, `default_registry`, `SubprocessToolRunner`, `render_summary`), 323's audit harness (`metrology/audit.py`: `run_audit`, `preflight_project`, `resolve_audit_skill`, `resolve_audit_profile`, `resolve_audit_model`, `find_audit_file`; `metrology/audit_variance.py`: `reduce_noise_floor`, `MIN_USABLE_RUNS`, `AuditVarianceError`), `derive_project_id` (`metrology/identity.py`).
- **Decisions recorded at task breakdown.**
  - **D7 is withdrawn.** Slice 440 deleted `sq probe` and its `baseline.available` field; the slice design now records D7 as withdrawn and lists no probe work.
  - **Library contracts.** `prepare_baseline` takes the adapter registry, and the series observer has a `progress_callback`. The slice design's Library contracts and D4 state both.
  - **Snapshot exclusions after 403.** 403 moved config reading into `read_snapshot_config`, but snapshot `preflight(repo_root)` still returns `head_sha` and `project_exclusions`, and `take_snapshot` still reads them from it. `prepare_baseline` uses `preflight` exactly as `take_snapshot` does.
- **Patch targets.** Existing `audit variance` tests patch `squadron.cli.commands.metrology.run_audit`. `audit_variance` must pass `audit=run_audit` from its own module namespace at call time so those patches still apply unedited. The baseline command does the same from `metrology_baseline.py`.
- Branch: `404-slice.adoption-baseline-command`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors project-wide), and the tests for the touched area. Don't use `pytest -n`. No test uses the user store or the real audit agent. Tests that run a series use a cooldown of 0.
- New modules stay at ~300 lines or less. Live runs (the walkthrough) are pre-authorized.
- Next slice: 420 (consumes 403's `take_snapshot_at` and `get_slice_ranges`).

## Task 1: Branch and move the audit printers (Development Approach 1) — Effort 1
- [x] Create `404-slice.adoption-baseline-command` from the target
- [x] Create `src/squadron/cli/commands/metrology_audit_output.py` and move `_make_progress_reporter`, `_report_run_outcome` and `_campaign_summary` from `cli/commands/metrology.py` into it, without the leading underscore. Bodies unchanged; `audit_run` and `audit_variance` import them
- [x] Success: `tests/metrology/test_audit_cli.py` passes with no edits; pyright clean
- [x] Commit: `refactor(metrology): move audit output printers into their own module`

## Task 2: `run_audit_series` with tests (D4, D6) — Effort 3
- [x] Create `src/squadron/metrology/audit_series.py` (no Typer or Rich imports) with `AuditSeriesRequest`, `AuditSeriesResult`, the `AuditSeriesObserver` Protocol (`on_run_start`, `on_cooldown`, `on_outcome`, `progress_callback`), `AuditCallable`, and `run_audit_series` per the design's Library contracts and D4. `AuditSeriesResult` also carries `stop_error: str | None` (the preflight, skill or identity error that ended the series) and a `NoFloorReason` StrEnum (`too_few_runs`, `unreducible`) for why there is no floor
- [x] Behavior is `audit_variance`'s per-project loop, unchanged: cooldown between runs, every run `independent_run=True, require_clean=True`, SHA pinned from `request.expected_sha` or run 1, an `AuditPreflightError` / `AuditSkillError` / `MetrologyIdentityError` counts the remaining runs failed and stops, rate limit stops, then reduce and `store.write_noise_floor`. `MetrologyStoreError` and `KeyboardInterrupt` propagate. Never prints
- [x] Create `tests/metrology/test_audit_series.py` with a fake `audit` callable and a recording observer: success writes a floor; a failed run in the middle is counted and the floor comes from the rest; rate limit stops the series; too few runs gives no floor and keeps the runs; moved HEAD (fake raises `AuditPreflightError` on run 2) sets `stop_error` and never calls run 3
- [x] Success: tests pass; pyright clean
- [x] Commit: `feat(metrology): add shared audit series loop`

## Task 3: `audit variance` calls the series (D4) — Effort 2
- [x] Replace `audit_variance`'s per-project body with one `run_audit_series` call per path. A private observer in `metrology.py` prints today's cooldown, run and progress lines; the result drives today's error, rate-limit, no-floor and floor lines in today's order, the campaign summary and the exit code
- [x] Success: `tests/metrology/test_audit_cli.py` passes with no edits; `sq metrology audit variance --help` matches the target's
- [x] Commit: `refactor(metrology): run audit variance through the shared series loop`

## Task 4: `prepare_baseline` with tests (D1, D2, D5) — Effort 3
- [x] Add `BaselinePreflightError(MetrologyError)` to `metrology/errors.py`
- [x] Create `src/squadron/metrology/baseline.py` (no Typer or Rich imports) with `BaselinePlan` and `prepare_baseline` per the Library contracts. It runs the D2 checks in Data Flow order with `cwd = str(project_path)` for every config read: snapshot `preflight`, `derive_project_id`, `preflight_project(require_clean=True)`, skill, profile, model (`None` → `BaselinePreflightError` naming `metrology.audit_model` and `--model`), runs (below `MIN_USABLE_RUNS` → `BaselinePreflightError`), cooldown, then the D5 file set and counts from the same calls `take_snapshot` makes. No tool runs, store writes or LLM calls
- [x] Create `tests/metrology/test_baseline.py` on `audited_repo` with user config: the success plan matches HEAD, identity, file and byte counts and config; with a fake registry and a project exclusion, `plan.file_count` equals `len(resolve_files(repo, snapshot.exclusions))` for the snapshot `take_snapshot` then writes, and the snapshot's per-language `file_count` values sum to no more than it
- [x] Success: tests pass; pyright clean
- [x] Commit: `feat(metrology): add baseline preflight and scope plan`

## Task 5: `sq metrology baseline` command with tests (D1, D5, D6, API Contracts) — Effort 3
- [x] Create `src/squadron/cli/commands/metrology_baseline.py` with `register_baseline_command(metrology_app)` following `metrology_snapshot.py`, registered in `metrology.py`. `PATH` (default the current directory), `--profile`, `--model`; the help repeats 400's security warning
- [x] Flow per the design's Data Flow and Output shape: one `default_registry()` passed to `prepare_baseline` and `take_snapshot`; scope report; snapshot summary; `run_audit_series` with `expected_sha=snapshot.commit_sha` and `audit=run_audit` from this module; summary. Exit 0 with a floor; any no-floor result prints its line plus `sq metrology audit variance <PATH>` and exits 1. Preflight and snapshot errors print `Error: …` and exit 1
- [x] Create `tests/metrology/test_baseline_cli.py` (patch `resolve_store_dir`, `default_registry` and `run_audit` in `metrology_baseline`; user config with model, profile and cooldown 0):
  1. [x] Success on a repo with a remote and no `.squadron.toml` or `project-documents/`: exit 0; one snapshot, three runs, one floor, same `ProjectId` and commit; the `Scope:` line precedes a marker the fake audit echoes on its first call
  2. [x] Each preflight failure (no model, no profile, `audit_variance_runs = 1`, dirty tree, no remote), parametrized: exit 1, cause named, store empty, fake audit never called
  3. [x] Each D6 row this task handles: snapshot failure, a `TIMEOUT` run (printed with its detail, floor still written), rate limit, moved HEAD, too few runs, each with its signal and exit
- [x] Success: tests pass; pyright clean; module under ~300 lines
- [x] Commit: `feat(metrology): add sq metrology baseline command`

## Task 6: Interrupt, store error and analysis file with tests (D6) — Effort 2
- [ ] `MetrologyStoreError`: `_logger.exception`, a `Store error:` line naming the store dir and persisted run count, the recovery command, exit 1
- [ ] `KeyboardInterrupt` caught once around the snapshot and series (process boundary, commented), exit 130: before a snapshot, one line saying nothing was recorded or spent; after, the snapshot id, runs completed and the recovery command
- [ ] On every exit after the first run started, name the file `find_audit_file(path, newer_than=<command start>)` returns and say to remove or commit it before the next snapshot
- [ ] Tests in `test_baseline_cli.py`: interrupt on run 2; interrupt from a patched `take_snapshot` (store empty, fake audit never called); `write_noise_floor` raising (ERROR in `caplog`); the analysis-file line on success and on interrupt
- [ ] Success: tests pass; pyright clean
- [ ] Commit: `feat(metrology): handle baseline interrupts and store errors`

## Task 7: Docs, CHANGELOG and full validation — Effort 1
- [ ] `## metrology baseline` in `docs/COMMANDS.md` after `metrology snapshot`: usage, what it writes, preflight checks, scope report, exits 0/1/130, config keys read, the analysis-file note, the security warning
- [ ] One user-facing bullet under `## [Unreleased]` → `### Added` in `CHANGELOG.md`
- [ ] Full suite, ruff and pyright pass; `git diff <target> -- tests/metrology/test_audit_cli.py` is empty
- [ ] Commit: `docs: add metrology baseline command reference`

## Task 8: Verification walkthrough (design → Verification Walkthrough) — Effort 2
- [ ] Run each walkthrough step on a small repository with a remote, cloned to `/tmp/baseline-demo`:
  1. Scratch clone with no `.squadron.toml` or `project-documents/`
  2. Missing model: exit 1 naming `metrology.audit_model` and `--model`, no report entry; restore the model value noted first
  3. Dirty tree: exit 1 naming `scratch.txt`; remove it
  4. Full run: scope report first, no prompt, snapshot summary, three runs, floor, exit 0, `Next:` line
  5. Records: `report baseline --project <id>` shows a floor; the store has one snapshot, three runs and one floor for the commit
  6. Re-run: exit 1 naming the untracked analysis file
  7. Regression: `sq metrology audit variance --help` matches the target's
- [ ] Record each step's outcome in a `## Verification` section at the end of this file; a failing step is fixed (with its test) before it is checked
- [ ] Commit: `docs: record slice 404 verification walkthrough`
