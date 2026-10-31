---
docType: slice-design
slice: adoption-baseline-command
project: squadron
parent: project-documents/user/architecture/400-slices.code-quality-measurement.md
dependencies:
- 400
- 323
interfaces:
- 440
dateCreated: 20261022
dateUpdated: 20261030
status: complete
turns: 28
promptTokens: 1524671
cachedTokens: 1431691
cacheWriteTokens: 92938
completionTokens: 22445
durationSeconds: 236.4
costUsd: 1.479256
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Adoption Baseline Command

## Overview

`sq metrology baseline [PATH]` gives an existing project a measured starting point in one step. It takes a code snapshot of the clean HEAD (400), then runs 323's audit variance series at that same commit and writes its noise floor. Before any LLM call it prints what it's about to spend: the file and byte count after exclusions, the number of audit runs, and the profile and model they'll use.

The command composes code that already exists. It adds no record type, metric, config key or store change. The new code is the command, the up-front preflight, the scope report, and the audit series loop, which moves out of `sq metrology audit variance` so both commands share it.

## Value

- **User value.** A project gets a full baseline (deterministic snapshot, audit run and audit noise floor) from one command, without editing its config files or code. Every later slice on that project can then be measured against it with 403's reports.
- **Spend is predictable.** The scope report and the up-front preflight mean a run that would fail on config (no pinned model, no project identity, a dirty tree) fails before any token is spent, and the operator sees the size of the job before the first audit starts.

## Technical Scope

**Included**
- `sq metrology baseline [PATH] [--profile P] [--model M]`, in a new CLI module mounted onto `metrology_app`.
- A preflight that runs every check from both halves before anything is measured or spent (D2).
- The scope report (D5).
- Extracting the per-project variance-series loop from `audit_variance` into a shared library function that both commands call (D4). `sq metrology audit variance` behaves exactly as it does today.
- Moving the audit progress and outcome printers out of `metrology.py` into a small shared CLI module, so the new command doesn't import private names.
- Docs: a `metrology baseline` section in `docs/COMMANDS.md` and a CHANGELOG bullet.

**Excluded**
- Measuring a commit other than a clean HEAD. That's 403's commit export.
- Any change to the snapshot's clean-tree rule, the audit skill, the noise-floor reduction or `baseline_report`.
- New config keys. Runs, cooldown, profile, model and snapshot settings are all existing keys.
- A `--json` mode. The command writes records; the records are read with `sq metrology report baseline --json` and `sq metrology snapshot --json`'s record format.
- Installing dependencies. Type counts stay absent unless the project's environment is already resolved (400).

## Dependencies

### Prerequisites
- **400 (complete):** `take_snapshot`, `default_registry`, `SubprocessToolRunner`, snapshot `preflight`, `effective_exclusions`, `resolve_files`, `render_summary`, `MetrologyStore.write_snapshot`.
- **323 (complete):** `run_audit`, `preflight_project`, `resolve_audit_skill`, `resolve_audit_profile`, `resolve_audit_model`, `reduce_noise_floor`, `MIN_USABLE_RUNS`, `store.write_noise_floor`, and the config keys `metrology.audit_variance_runs`, `metrology.audit_run_cooldown_s`, `metrology.audit_profile`, `metrology.audit_model`.

### Interfaces Required
- `derive_project_id(cwd=...)`: snapshot and audit both call it with the project path, so they key on the same `ProjectId`.
- `run_audit(..., independent_run=True, require_clean=True, expected_sha=...)`: the variance-run settings, used as `audit variance` uses them.
- `baseline_report` groups runs by `(project, commit, audit_prompt_hash)` and reports the newest run with that group's floor (323). D3 relies on this.

## Architecture

### Component Structure

| Module | Change | Responsibility |
|---|---|---|
| `cli/commands/metrology_baseline.py` | new | `register_baseline_command(metrology_app)`: the Typer shell. Runs preflight, prints the scope report, takes the snapshot, runs the series, prints the summary, sets the exit code |
| `metrology/baseline.py` | new | `prepare_baseline(project_path, registry, *, profile, model) -> BaselinePlan`: the combined preflight and scope computation, with no side effects and no spend |
| `metrology/audit_series.py` | new | `run_audit_series(request, *, store, observer) -> AuditSeriesResult`: the per-project series loop moved out of `audit_variance` (pinning, cooldown, rate-limit stop, reduce and write the floor) |
| `cli/commands/metrology_audit_output.py` | new | `make_progress_reporter`, `report_run_outcome` and `campaign_summary`, moved unchanged from `metrology.py` |
| `cli/commands/metrology.py` | edit | `audit_variance` calls `run_audit_series` per project. `audit_run` and `audit_variance` import the moved printers. Registers the baseline command |

`metrology/baseline.py` and `metrology/audit_series.py` are library code with no Typer or Rich imports, following the snapshot package's split between `take.py` and its CLI shell. The CLI talks to `run_audit_series` through a small observer protocol (run started, cooldown, outcome), so `audit variance` and `baseline` keep their own output wording without duplicating the loop.

### Data Flow

```
sq metrology baseline PATH
  │
  ├─ prepare_baseline(PATH)                     no tool runs, no LLM call
  │    ├─ snapshot preflight(PATH)              clean tree, limits, exclusions, timeout
  │    ├─ derive_project_id(PATH)               same identity for both halves
  │    ├─ preflight_project(PATH, require_clean=True)
  │    ├─ resolve_audit_skill()
  │    ├─ resolve_audit_profile(profile, cwd=PATH)
  │    ├─ resolve_audit_model(model, cwd=PATH)  None → BaselinePreflightError (D2)
  │    ├─ runs = metrology.audit_variance_runs  < MIN_USABLE_RUNS → BaselinePreflightError
  │    └─ effective_exclusions + resolve_files → file count, byte count
  │
  ├─ print scope report                         informational, no prompt (D5)
  │
  ├─ take_snapshot(PATH, default_registry(), SubprocessToolRunner(), store)
  │    └─ one code_snapshot record at HEAD sha S
  │
  ├─ run_audit_series(PATH, runs, expected_sha=S, ...)
  │    ├─ N × run_audit(independent_run=True, require_clean=True, expected_sha=S)
  │    │    └─ one audit_run record per successful run
  │    └─ reduce_noise_floor(series) → one audit_noise_floor record
  │
  └─ print summary: snapshot id, runs ok/failed, floor, next command
```

### State Management

All state goes to 320's metrology store through existing writers: one `code_snapshot`, N `audit_run` records and one `audit_noise_floor`, all keyed on the same project and commit. The command holds no state between invocations. The audit skill writes its analysis file into the project, as every audit does (323). That file is the only thing the command leaves in the repository.

## Technical Decisions

### D1 — Command name, argument and config source
Status: decided
- `sq metrology baseline [PATH]`. `PATH` defaults to the current directory. This is the "take" side of the existing `sq metrology report baseline`, which reads the audit baseline. The two names pair on purpose.
- Every config read uses `cwd=PATH`, so the measured project's `.squadron.toml` (if it has one) and the user config apply to both halves alike. There is no `--cwd`. `audit variance` takes several project paths and reads config from `--cwd`. The baseline measures one project, so a second directory would only let the snapshot and the audit read different config.
- `--profile` and `--model` are overrides with the same precedence `audit run` and `audit variance` use (explicit argument, then config), through the same resolvers.
- Rejected: a top-level `sq baseline`. The command writes metrology records and sits beside the commands that read them.

### D2 — Everything that can fail on config fails before anything runs
Status: decided
- `prepare_baseline` runs the snapshot preflight, identity, the audit preflight, skill resolution, profile and model resolution, and the run-count check, all before the snapshot. So a missing model can't leave a snapshot with no audit behind it.
- **A model must be pinned.** `resolve_audit_model` returns `None` when neither `--model` nor `metrology.audit_model` is set, which `audit run` accepts and lets the CLI choose. For a baseline that's a failure: the config key's own description says an unpinned model isn't a fixed instrument, so a floor measured under it can't be compared later. The error names `sq config set metrology.audit_model <model>` and `--model`.
- **Profile** uses `resolve_audit_profile` unchanged: `metrology.audit_profile`, then `default_review_profile`, then an explicit `AuditSkillError`. That chain is 323's config, and it already fails explicitly.
- **Runs** come from `metrology.audit_variance_runs`. A value below `MIN_USABLE_RUNS` can never produce a floor, so it fails here rather than after the runs are spent.
- **Identity.** A repository with no git remote and no `metrology.project_id` fails with `derive_project_id`'s existing message. That's the one project-level setting the command can need, and only when there's no remote.
- Errors are one new `BaselinePreflightError` (in `metrology/errors.py`) for the model and run-count checks, plus the existing `SnapshotPreflightError`, `AuditPreflightError`, `AuditSkillError` and `MetrologyIdentityError`. The CLI prints each and exits 1.

### D3 — The variance series is the audit run
Status: decided
- The command runs the variance series only: N independent runs (default 3) at the snapshot's commit. Every run in the series is a persisted `audit_run`, and `baseline_report` reports the newest run in the group with the floor beside it. That satisfies "an audit run and an audit noise floor" without a separate non-independent run.
- The architecture's cost note counted "three audit runs plus the baseline run". A fourth run adds a full audit's cost and no information: the floor already describes the spread of runs at that commit, and the report already picks one run from the group.
- `independent_run=True` for every run, so the analysis file run 1 writes doesn't turn later runs into revisions of it (323's repeat-run clause).

### D4 — One series loop, shared with `audit variance`
Status: decided
- The per-project body of `audit_variance` (pin the SHA, cool down between runs, stop on rate limit, require `MIN_USABLE_RUNS`, reduce, write the floor) moves to `run_audit_series` in `metrology/audit_series.py`. `audit_variance` loops over its paths and calls it. The baseline calls it once.
- Input: an `AuditSeriesRequest` dataclass (project path, runs, cooldown, profile, model, `expected_sha`, config cwd). Output: an `AuditSeriesResult` dataclass (successful runs, failed count, the floor or the reason there's none, and whether the series stopped on a rate limit).
- The caller supplies an observer (`on_run_start`, `on_cooldown`, `on_outcome`, and `progress_callback` for the live progress line) for output, so the library function never prints.
- The baseline passes `expected_sha` = the snapshot's commit from the first run on, so a HEAD that moves after the snapshot fails the series instead of measuring a different commit. `audit variance` keeps passing `None` for the first run, as now.
- `audit variance`'s output and exit codes stay as they are. Its existing tests are the check.

### D5 — Scope report: snapshot exclusions, stated plainly
Status: decided
- The file set is the one the snapshot measures: `resolve_files(PATH, effective_exclusions(project_exclusions, default_registry().values()))`, the same calls `take_snapshot` makes, so the report and the snapshot can't disagree. Bytes are the sizes of those files on disk, which equal HEAD because the tree is clean.
- The report also prints the commit, the audit run count, profile, model, and the cooldown between runs. It says that the audit agent reads the repository itself and isn't limited to the excluded set. That's true of 323's audit, and an operator estimating spend needs to know.
- No confirmation prompt. The report prints and the command continues, as the slice plan requires.
- No wall-clock estimate. Audit duration varies too much to print one honestly.

### D6 — Failure after the snapshot keeps what was measured
Status: decided
Each run persists independently or not at all (323's `run_audit` rule), so whatever ends the command, the snapshot and every completed run stay in the store. Earlier runs aren't reused by a later series: today no command reduces a floor from stored runs. So the recovery for every row below that has no floor is `sq metrology audit variance PATH`, a fresh full series at the same commit.

| Failure mode | Handling | Observable signal | Exit |
|---|---|---|---|
| Snapshot fails (integrity, adapter contract, store) | Stops before any audit | Error line naming the cause | 1 |
| A run exceeds `metrology.audit_timeout_s` (323 key, default 3600) | `run_audit` cancels it and returns `AuditRunFailure.TIMEOUT`. Counted as a failed run; the series continues | `run_audit`'s WARNING log; the run line prints `failed … timeout: exceeded metrology.audit_timeout_s (Ns)` | per the last two rows |
| A run fails (stream error, missing or malformed findings block) | Counted as a failed run; the series continues | `run_audit`'s WARNING/ERROR log and the run's `failed` line | per the last two rows |
| Rate limit after retries | The series stops | Stop message plus the recovery command | 1 if no floor |
| HEAD moves after the snapshot | `AuditPreflightError` from `expected_sha` pinning; the remaining runs count as failed | Error line naming both SHAs | 1 if no floor |
| Interrupt (Ctrl-C) | `KeyboardInterrupt` is caught once, in the CLI command (process boundary). The interrupted run persists nothing | Lines naming the snapshot id, runs completed, and the recovery command. If no snapshot exists yet (the interrupt came during the snapshot step), one line says so: nothing was recorded or spent | 130 |
| Floor write fails (`MetrologyStoreError` from `write_noise_floor`) | Propagates out of `run_audit_series`; the CLI logs it at ERROR | `Store error:` line naming the store dir and the persisted runs, plus the recovery command | 1 |
| Fewer than `MIN_USABLE_RUNS` successful runs | No floor | Line saying how many runs succeeded, plus the recovery command | 1 |

**The analysis file.** The audit skill writes an untracked analysis file into the project (`find_audit_file`'s globs: `analysis/` or `project-documents/user/analysis/`). Runs 2..N still pass `require_clean=True` because 323's `preflight_project` ignores paths matching `_AUDIT_ARTIFACT_PATTERN`. The snapshot has no such exemption (400's clean-tree rule, unchanged here), so after a baseline, `sq metrology snapshot`, 403's in-place snapshots and a re-run of the baseline are refused until the file is removed or committed. The final summary therefore names the file (`find_audit_file(PATH, newer_than=<command start>)`) and says to remove or commit it before the next measurement. The same lines print on every exit after the first run.

### D7 — Withdrawn
Status: withdrawn
- Slice 440 deleted `sq probe` and its `baseline.available` field, so there is nothing to flip. 404 makes no probe change.

### Technology Choices
- No new dependencies. Typer and Rich as in the sibling commands. Bytes come from `Path.stat().st_size`.

### Patterns and Conventions
- CLI shell in its own module, mounted by a `register_*_command` function, as `metrology_snapshot.py` does.
- Library functions take the store, registry and runner as arguments, so tests pass fakes (400's `take_snapshot` pattern). `run_audit` is injected into `run_audit_series` as a callable for the same reason.
- Every failure path either raises a typed error that the CLI prints, or is a counted failed run that's printed and drives exit 1. No silent path.

## Implementation Details

### API Contracts

```
sq metrology baseline [PATH] [--profile PROFILE] [--model MODEL]
```

Exit 0: snapshot written, and a floor written from at least `MIN_USABLE_RUNS` runs (some runs may have failed; the summary says so).
Exit 1: any preflight failure (nothing written, nothing spent), a snapshot failure (nothing spent), or a series without a floor (snapshot and successful runs kept).
Exit 130: interrupted (snapshot and completed runs kept; D6).

Output shape (values illustrative):

```
Baseline for github.com/acme/widgets @3f2a91c0
  Scope: 412 files, 1,904,233 bytes after exclusions (31 excluded patterns)
         The audit agent reads the repository itself; exclusions don't limit it.
  Audit: 3 runs, profile <profile>, model <model>, 60s between runs
Snapshot
  <render_summary lines, unchanged from sq metrology snapshot>
Audit
  run 1/3  ok github.com/acme/widgets @3f2a91c0  27 findings
  ...
  floor github.com/acme/widgets @3f2a91c0  total 24-29 (mean 26.3, sd 2.05, n=3)
Campaign: 3 succeeded, 0 failed, 1 floor(s) written.
The audit wrote analysis/<file>.md. Remove or commit it before the next snapshot.
Next: sq metrology report baseline --project github.com/acme/widgets
```

Library contracts:

```python
@dataclass(frozen=True)
class BaselinePlan:
    project_path: Path
    project_id: ProjectId
    head_sha: str
    file_count: int
    byte_count: int
    exclusions: list[str]
    runs: int
    cooldown_s: int
    profile: str
    model: str

def prepare_baseline(project_path: Path, registry: AdapterRegistry, *,
                     profile: str | None, model: str | None) -> BaselinePlan: ...
def run_audit_series(request: AuditSeriesRequest, *, store: MetrologyStore,
                     observer: AuditSeriesObserver, audit: AuditCallable = run_audit) -> AuditSeriesResult: ...
```

## Integration Points

### Provides to Other Slices
- **403:** a snapshot, audit runs and a floor at the adoption commit, which its project and history reports read like any others.
- **Squadron itself:** `run_audit_series` as the one series loop.

### Consumes from Other Slices
- **400:** snapshot preflight, file resolution and `take_snapshot`, called exactly as `sq metrology snapshot` calls them. 404 needs neither 401 nor 403 to land first, and works in either order with them. What it relies on is this interface contract, all present in 400 today:
  - `take_snapshot(repo_root, registry, runner, store) -> CodeSnapshot`
  - `preflight(repo_root)` raising `SnapshotPreflightError` on a dirty tree, and returning `head_sha` and the project exclusions
  - `effective_exclusions(project_patterns, adapters)` and `resolve_files(repo_root, exclusions)`
  
  401 adds metrics behind `take_snapshot` (401 design: "404: no change"). 403 moves config reading into `read_snapshot_config` and keeps `take_snapshot`'s signature (403 design: "404: nothing new"). If 403 lands first and the project exclusions move from `preflight`'s result to `read_snapshot_config`, `prepare_baseline` reads them from wherever `take_snapshot` does. The scope set has to stay the snapshot's own (D5).
- **323:** the audit harness and floor reduction, unchanged. If the audit skill changes, `audit_prompt_hash` changes and the baseline's runs group separately, as 323 already handles.

## Success Criteria

### Functional Requirements
- One `sq metrology baseline PATH` on a clean repository writes one `code_snapshot`, N `audit_run` and one `audit_noise_floor` record, all with the same `ProjectId` and commit SHA. N is `metrology.audit_variance_runs`.
- The scope report (commit, files and bytes after exclusions, run count, profile, model, cooldown) prints before the first LLM call. The command doesn't wait for input.
- The scope report's file set is the snapshot's own: a test asserts the scope count equals `len(resolve_files(...))` with the exclusion list the snapshot records, and that the snapshot's per-language `file_count` values sum to no more than it.
- With neither `--model` nor `metrology.audit_model` set, the command exits 1 naming both, writes no record and makes no LLM call. Same for no resolvable profile, `audit_variance_runs` below `MIN_USABLE_RUNS`, a dirty tree, and an underivable project identity.
- A HEAD that moves after the snapshot fails the remaining runs (`expected_sha` pinning) instead of auditing a different commit.
- A series without a floor exits 1, keeps the snapshot and successful runs, and prints the `audit variance` command that completes it. An interrupt exits 130 with the same information. Each failure mode in D6's table produces its listed signal.
- Every exit after the first audit run names the analysis file the audit wrote, and says to remove or commit it before the next snapshot.
- The command succeeds on a git repository with a remote and no `.squadron.toml`, no `project-documents/`, and no cf project, given user-level audit profile and model config.

### Technical Requirements
- `sq metrology audit variance` output and exit codes are unchanged, and its existing tests pass without edits other than imports.
- `run_audit_series` and `prepare_baseline` have unit tests with a fake `audit` callable and a temporary git repository: success, a failed run in the middle, rate-limit stop, too few runs, moved HEAD, and each preflight failure asserting that the fake was never called. Further tests assert the observable signal for three cases: a run returning `AuditRunFailure.TIMEOUT` is counted failed and printed with its timeout detail; a `write_noise_floor` that raises `MetrologyStoreError` gives exit 1, an ERROR log and the recovery command; and `KeyboardInterrupt` from the fake gives exit 130 and the recovery command.
- A CLI test asserts the scope report line comes before the first audit callable invocation.
- `ruff format`, `ruff check`, `pyright` zero errors. New modules within the ~300-line guideline.
- `docs/COMMANDS.md` gets a `metrology baseline` section. CHANGELOG gets one user-facing bullet.

### Integration Requirements
- `sq metrology report baseline --project <id>` shows the baseline's project with a measured floor (not `no floor measured`) after a successful run.

### Verification Walkthrough

Uses a small scratch repository so the three audits stay cheap; run once on 20261030 (results in the tasks file's `## Verification`). The audit settings below are the ones squadron's own repository uses. Substitute your own profile and model.

1. Set up a scratch repository with a remote and no squadron or cf files:
   ```bash
   mkdir /tmp/baseline-demo && cd /tmp/baseline-demo && git init -q -b main
   printf 'def add(a: int, b: int) -> int:\n    return a + b\n' > calc.py && printf '# demo\n' > README.md
   git add -A && git commit -q -m init
   git remote add origin https://github.com/manta/baseline-demo.git
   ls .squadron.toml project-documents 2>&1   # both: No such file or directory
   ```
2. Missing-model failure, nothing spent. Pass `--profile` so the profile check, which runs first, doesn't answer instead:
   ```bash
   sq config get metrology.audit_model          # (not set) in user config; if set, note it and unset it
   sq metrology baseline . --profile demo-profile
   # exit 1: "Error: No audit model is pinned. … 'sq config set metrology.audit_model <model>' or pass --model."
   sq metrology report baseline --json          # no entry for github.com/manta/baseline-demo
   ```
3. Dirty-tree failure: `touch scratch.txt && sq metrology baseline . --profile demo-profile --model demo-model` exits 1 with `Error: The working tree is not clean: scratch.txt. …`, then `rm scratch.txt`.
4. Full run:
   ```bash
   sq metrology baseline . --profile sdk --model claude-sonnet-5
   ```
   Output order: `Baseline for github.com/manta/baseline-demo @…`, `Scope: …`, `Audit: 3 runs, profile sdk, model claude-sonnet-5, 60s between runs` (no prompt follows), `Snapshot` and its summary, `Audit`, `run 1/3  ok …`, `run 2/3  ok …`, `run 3/3  ok …` (with `cooling down 60s` lines between), `floor … total A-B (mean …, sd …, n=3)`, `Campaign: 3 succeeded, 0 failed, 1 floor(s) written.`, `The audit wrote analysis/NNN-analysis.baseline-demo.md. …`, `Next: sq metrology report baseline --project github.com/manta/baseline-demo`. Exit 0. Takes about eight minutes.
5. Check the records:
   ```bash
   sq metrology report baseline --project github.com/manta/baseline-demo   # "floor A-B (sd …, n=3)", not "no floor measured"
   ls ~/.config/squadron/metrology/ | grep -E 'snapshot-.*-<first 12 chars of the commit>|^audit-|^floor-'
   ```
   For this project and commit the store holds one `snapshot-*`, three `audit-*` and one `floor-*` file.
6. Re-run refusal: `sq metrology baseline . --profile sdk --model claude-sonnet-5` exits 1 with `Error: The working tree is not clean:` and every untracked analysis file. Each audit run writes its own file, so after a three-run baseline there are three. The end-of-run line names only the newest.
7. Regression: `sq metrology audit variance --help` prints the same text on `main` and on this branch, and `git diff main -- tests/metrology/test_audit_cli.py` is empty.

## Implementation Notes

### Development Approach
1. Move the three audit printers to `metrology_audit_output.py`. Tests pass unchanged.
2. Extract `run_audit_series` from `audit_variance`, with its tests. `audit variance` tests pass.
3. `prepare_baseline` and `BaselinePreflightError`, with tests for each preflight failure.
4. The CLI command and its tests.
5. Docs and CHANGELOG, then the walkthrough.

Effort: 2/5.

### Special Considerations
- **Security.** The snapshot runs the project's own `.venv` and `node_modules` tools (400's warning), and the audit agent reads the whole repository. The command's help repeats 400's warning: only baseline repositories you trust.
- **Cost.** N full audits on the project. The scope report exists so this is visible before the first one; nothing else limits it.
