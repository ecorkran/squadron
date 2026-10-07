---
docType: tasks
slice: run-liveness-stall-bounds-pruning-and-readable-listings
project: squadron
lld: user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md
dependencies: [150, 156, 199, 932]
projectState: >
  Slice design complete (review rounds applied), not yet implemented. 199 (listings, wait) and
  932 (SDK session idle timer) are complete. Integration branch is unset, so the target is `main`.
dateCreated: 20261007
dateUpdated: 20261007
status: complete
---

## Context Summary

- Working on **174 run-liveness-stall-bounds-pruning-and-readable-listings**: fixes #190
  (a dead run stays `running`) and #165 (a stalled foreground turn waits forever); adds
  `sq runs prune` and `sq pipelines show`; reworks the 199 listings onto a terminal-fitting
  renderer.
- Order: spike, then the no-behaviour-change `RunObserver` refactor, then schema v5 and
  liveness, foreground stall, wait and listing, renderer, show and prune, docs.
- Tasks reference the slice design by section (D1–D13, "API Contracts", "UI Specifications");
  the design is the contract.
- Out of scope: resuming orphaned runs (an issue is opened in the last part), #169, liveness
  for prompt-only runs, the automatic keep-10 `StateManager.prune()`, `--json`, typing
  `RunState.status`.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors) and its tests
  before its commit. Tests are hermetic (`tests/_hermetic.py`): `tmp_path` runs dir, real
  `StateManager`, dead PIDs from a subprocess that has already exited.
- Traceability (design → tasks): spike/D5 → 2; D12 → 4–7; D2/D13 → 8–13; D3 → 9–10; D6 →
  11–12; D1 → 8; D7 → 15–18; D8 → 19–20; D10 → 21–22; listing-time NFR → 22 (I/O counts) and 42 (walkthrough step 8, timed by hand; the design puts no time assertion in tests); D11 → 23–26; pipelines list →
  27–28; show → 29–31; D9 prune → 32–39; docs → 40; issues → 41; walkthrough → 42.
- Effort: 3/5. Next planned slice: per `cf next` after 174 closes.

---

## Task 1 — Create the slice branch

- [x] Confirm `cf config get git.integration_branch` is empty (target = `main`) and
      `git status` is clean
- [x] If the branch does not exist:
      `git checkout -b 174-slice.run-liveness-stall-bounds-pruning-and-readable-listings main`;
      if it exists, `git checkout` it
  - [x] Success: `git branch --show-current` prints the branch name

## Task 2 — Spike: SDK interrupt and state-write threading (design Dev Approach step 1)

- [x] Write a throwaway script (outside `src/`, not committed) that starts a
      `ClaudeSDKClient` turn asking for a long Bash `sleep`, calls `client.interrupt()`, and
      prints every message that follows, in order
  - [x] Record: does a `ResultMessage` for the interrupted turn arrive, is `is_error` set,
        and does a following `query()` on the same client succeed
  - [x] Success: findings recorded under the design's "Interrupting a live turn" risk; if no
        `ResultMessage` arrives, apply the design's fallback (D7 narrows to "always mark
        unusable"), update D7 to say so, and carry it into Task 16
- [x] Confirm no `StateManager` write runs off the event-loop thread (D5): grep
      `to_thread` and `run_in_executor` in `src/squadron/pipeline` and `cli/commands/run.py`
  - [x] Success: each hit is listed with whether it touches the state file; if any does, add
        D5's per-run `threading.Lock` around load, modify and write in Task 11

## Task 3 — Baseline the existing tests

- [x] Run `pytest tests -q` and record pass/fail counts
  - [x] Success: failures (if any) are noted as pre-existing before any edit

---

## Part A — `RunObserver` refactor, no behaviour change (D12)

## Task 4 — Add `run_observer.py` with `RunObserver` and `RunStateRecorder`

- [x] Create `src/squadron/pipeline/run_observer.py` with the `RunObserver` protocol
      (`step_started`, `item_started`, `step_completed`) per D12
  - [x] `item_started` takes an `ActiveItem`; define `ActiveItem` (D2) in `state.py` now so
        the module imports it
- [x] Add `RunStateRecorder(state_mgr, run_id)` implementing the protocol; `step_completed`
      does exactly what `StateManager.make_step_callback`'s closure does today
      (`state.py:267`); `step_started` and `item_started` are no-ops for now
- [x] Add `StateManager.observer(run_id) -> RunObserver` returning the recorder
  - [x] Success: `pyright` clean; the module has no import of `executor`

## Task 5 — Move `execute_pipeline` onto the observer

- [x] In `executor.py`, replace the `on_step_complete` parameter and its docstring entry
      (`:390`, `:427`) with `observer: RunObserver | None`; the call at `:576` becomes
      `observer.step_completed(step_result)`
- [x] Call `observer.step_started(step.name)` at each top-level step start, and
      `observer.item_started(each_name, ActiveItem(...))` at each `each` item start
      (`executor.py` each loop, design cites `:1553-1597`)
  - [x] `ActiveItem.index` is the item's own `index` field when present, else `None`
  - [x] Success: with the recorder's no-op start methods, behaviour is unchanged
- [x] In `cli/commands/run.py:251` pass `observer=state_mgr.observer(run_id)`; delete
      `make_step_callback`
  - [x] Success: `grep -rn "on_step_complete\|make_step_callback" src tests` is empty after
        Task 6

## Task 6 — Move the existing callback tests onto the observer

- [x] Update every test that passed `on_step_complete` or `make_step_callback` to pass an
      observer (a small recording fake, or `state_mgr.observer`), same assertions
  - [x] Success: those tests pass with unchanged intent

## Task 7 — Observer call-order tests; commit

- [x] In `tests/pipeline/test_executor.py` add: a plain step yields `step_started` then
      `step_completed`; in `tests/pipeline/test_executor_each.py` an `each` step with three
      items yields `step_started`, three `item_started` (positions 0–2, total 3, index from
      the item), `step_completed`
  - [x] Success: tests pass; `pytest tests -q` matches the Task 3 baseline
- [x] Commit: `refactor: replace on_step_complete with RunObserver`

---

## Part B — Schema v5 and liveness core (D2, D3, D5, D6, D13)

## Task 8 — Config keys (D1) and `RunOwner` / schema v5 fields (D2)

- [x] Add `pipeline.foreground_idle_timeout_s` (default 1800) and
      `pipeline.run_heartbeat_interval_s` (default 30) to `CONFIG_KEYS`, typed `int`
  - [x] Add a typed reader for each that raises `ValueError` naming the key when the value is
        `<= 0`
- [x] In `state.py` (`ActiveItem` already exists from Task 4; do not redefine it) add
      `RunOwner` with a `RunOwner.current(heartbeat_interval_s)` factory
      (pid, hostname, `claimed_at = now`); add the five `RunState` fields from D2, all
      default `None`; set `_SCHEMA_VERSION = 5` and `_SUPPORTED_SCHEMA_VERSIONS = {3, 4, 5}`
  - [x] Success: a v4 fixture file loads with all new fields `None`; a v6 file still raises
        `SchemaVersionError`
- [x] Tests in `tests/test_config.py` and `tests/pipeline/test_state.py`: both keys resolve
      with defaults; `0` and negative values raise naming the key; v3/v4/v5 load; v6 rejected
      - Tests live in tests/config/test_keys.py
  - [x] Success: tests pass

## Task 9 — `run_liveness.py`

- [x] Create `src/squadron/pipeline/run_liveness.py` with `RunLiveness` (`LIVE`, `STALE`,
      `ORPHANED`, `UNOWNED`), `LivenessAssessment(liveness, elapsed, progress_age,
      heartbeat_age)`, `STALE_HEARTBEAT_INTERVALS = 10`, `process_alive(pid) -> bool | None`
      and `assess_liveness(state, *, now, hostname, process_alive)`
  - [x] `process_alive` uses `os.kill(pid, 0)`: `ProcessLookupError` → `False`,
        `PermissionError` → `True`; non-positive PID or any other `OSError` → `None` with a
        WARNING naming the PID (the run-id is logged by the caller that has it)
  - [x] `assess_liveness` applies the D3 table top to bottom, only for `RUNNING_STATUS`; a
        `None` from `process_alive` falls through to the heartbeat row
  - [x] `elapsed` is `now - owner.claimed_at`; `progress_age` is `now - progress_at`
  - [x] Success: module performs no I/O except the injected `process_alive` default

## Task 10 — `run_liveness` tests

- [x] Add `tests/pipeline/test_run_liveness.py` covering every D3 row with injected `now`,
      `hostname`, `process_alive`: same host process gone (also with overdue heartbeat) →
      `ORPHANED`; process alive + overdue → `STALE`; other host fresh → `LIVE`; other host
      overdue → `STALE`; no owner → `UNOWNED`; `process_alive` returns `None` → heartbeat rule
  - [x] Add `process_alive` tests with a real exited subprocess PID (`False`), the test's own
        PID (`True`), PID `0` and `-1` (`None` plus WARNING)
  - [x] Success: tests pass
- [x] Commit: `feat: add RunState v5 owner fields and run_liveness`

## Task 11 — `init_run(owner=)`, `claim`, `heartbeat`, progress writes (D13, D6)

- [x] `init_run(..., owner: RunOwner | None)`: when given, the same `_write_atomic` that
      creates the file with `status: running` also writes `owner`, `heartbeat_at` and
      `progress_at`
- [x] `StateManager.claim(run_id, owner)`: one write setting owner fields and
      `status = RUNNING_STATUS`; raises if the file is already `running` with a `LIVE`
      owner (assessed via `assess_liveness`)
- [x] `StateManager.heartbeat(run_id)`: rewrites `heartbeat_at` only
- [x] `RunStateRecorder`: `step_started` writes `active_step`, clears `active_item`, sets
      `progress_at`; `item_started` writes `active_item` and `progress_at`; `step_completed`
      also clears `active_item` and sets `progress_at`; `finalize` clears `active_step` and
      `active_item`
  - [x] `heartbeat` and the two start writes catch `OSError` and `STATE_READ_ERRORS` by name,
        log WARNING with run-id and exception, and continue; any other exception propagates
        (D6)
  - [x] Success: no new try/except swallows without a comment saying why

## Task 12 — Tests for state writes

- [x] In `test_state.py`: first `init_run(owner=...)` file already holds the owner (read the
      file immediately; no ownerless `running` state); `claim` flips `paused` and `failed` to
      `running` with owner; `claim` on a `LIVE` running run raises; `heartbeat` changes only
      `heartbeat_at`; recorder start/complete writes set and clear `active_step`,
      `active_item`, `progress_at`; `finalize` clears the active fields and keeps `owner`
  - [x] Failure modes: an `OSError` on heartbeat and on `step_started` logs a WARNING and
        does not raise (`caplog`); a non-I/O exception from `step_started` propagates
  - [x] Success: tests pass
- [x] Commit: `feat: record owner, heartbeat and progress in run state`

## Task 13 — `RunHeartbeat` and wiring into `_run_pipeline_sdk`

- [x] Create `src/squadron/pipeline/run_heartbeat.py`: async context manager
      `RunHeartbeat(state_mgr, run_id, interval, *, claim: bool)`
  - [x] Enter: when `claim`, call `StateManager.claim` with a `RunOwner.current(interval)`;
        start the heartbeat task (first write after one interval)
  - [x] The task catches `OSError` / `STATE_READ_ERRORS` per D6; a done-callback logs any
        other exception except `CancelledError` with `logger.exception` and the heartbeat
        stops
  - [x] Exit: cancel the task and await it
- [x] In `cli/commands/run.py` `_run_pipeline_sdk`: new runs build
      `RunOwner.current(...)` before `init_run(owner=...)` and enter `RunHeartbeat(...,
      claim=False)`; resume and item-resume paths enter `RunHeartbeat(..., claim=True)`;
      prompt-only paths pass `owner=None` and no heartbeat
  - [x] Success: the executor call sits inside the context manager on all three SDK paths

## Task 14 — `RunHeartbeat` and wiring tests; commit

- [x] `tests/pipeline/test_run_heartbeat.py`, real `StateManager` in `tmp_path`, interval
      0.05 s: claim written; at least two heartbeats written; task cancelled on exit; write
      `OSError` logs WARNING and does not raise; an unexpected exception in the task is
      logged at ERROR by the done-callback and the heartbeat stops
  - [x] Success: tests pass
- [x] Add a CLI-level test (existing `tests/pipeline/test_cli_integration.py` style),
      parametrized over the three SDK paths (new run, `--resume`, `--item` item-resume), that
      the run is `running` with an owner while the executor runs, and `failed` or `completed`
      after; the new-run case also asserts the owner was present from the creating write
  - [x] Success: tests pass; existing `sq run` / `--resume` / `--item` tests unchanged
- [x] Commit: `feat: heartbeat and claim SDK runs`

---

## Part C — Foreground stall bound (D7, #165)

## Task 15 — `DispatchStalledError` and the foreground timer in `sdk_session.py`

- [x] Add `INTERRUPT_DRAIN_TIMEOUT_S = 60` and public `DispatchStalledError(ProviderError)`
      carrying `idle_s` and `session_usable`
- [x] Add private `_ForegroundIdleTimeout`; in `_collect_turns` pass
      `idle_s=foreground_idle_timeout_s` for foreground reads (today `idle_s=None`, `:218`),
      leaving background reads on 932's key
  - [x] Success: background-wait behaviour untouched

## Task 16 — Interrupt and drain

- [x] On `_ForegroundIdleTimeout`: log WARNING `dispatch: foreground turn silent for %ds;
      interrupting`; `await client.interrupt()` inside `asyncio.timeout(INTERRUPT_DRAIN_TIMEOUT_S)`;
      drain with `_read_turn(idle_s=INTERRUPT_DRAIN_TIMEOUT_S)` until the dispatch's own
      `ResultMessage`; an `is_error` result is not re-raised as `ProviderAPIError`
  - [x] Interrupt and drain both complete → session stays usable
  - [x] Interrupt raises, drain times out, or the stream ends → set `unusable_reason` to
        `foreground stall: interrupt did not complete (<detail>)`, log ERROR; later calls
        fail fast through `_require_usable`
  - [x] Raise `DispatchStalledError(idle_s, session_usable)` in both cases
  - [x] Success: adjust to the Task 2 spike findings if they differ from the design

## Task 17 — `sdk_session` stall tests

- [x] In `tests/pipeline/test_sdk_session.py` add a fake client whose stream goes silent:
      interrupt sent; drain reaches the result; session stays usable; the next dispatch
      succeeds; `DispatchStalledError` raised
  - [x] Second fake whose `interrupt()` raises: session unusable, ERROR record, next call
        fails fast; a third whose drain never ends: same, via the drain bound (patch the
        constant small)
  - [x] Success: tests pass; 932 background-wait tests unchanged

## Task 18 — Dispatch action mapping; commit

- [x] In `actions/dispatch.py` `execute()`, catch `DispatchStalledError` ahead of the generic
      `Exception` handler: WARNING without traceback; return `ActionResult(success=False,
      error="dispatch stalled: no output for <N>s; turn interrupted",
      metadata={"stalled": True, "session_usable": ...})`
- [x] Test in `tests/pipeline/actions/test_dispatch_session.py`: failed result, error text
      prefix `dispatch stalled:`, metadata, one WARNING, no `exc_info` on the record
  - [x] Success: tests pass
- [x] Commit: `feat: bound foreground dispatch silence with interrupt`

---

## Part D — Wait and run listing (D3, D8, D10)

## Task 19 — `WaitOutcome.ORPHANED` and the STALE policy in `run_wait.py`

- [x] Add `WaitOutcome.ORPHANED` and exit code 8 to `WAIT_EXIT_CODES`; `wait_for_run` gains
      injected `now`, `hostname`, `process_alive` beside `clock` and `sleep`
- [x] On each poll that sees `running`, assess liveness: `ORPHANED` ends the wait with a
      WARNING and stderr `sq runs wait: run <id> orphaned (process <pid> gone)`; the first
      `STALE` logs one WARNING `run <id> heartbeat overdue by <age>; still waiting`; a later
      `LIVE` after `STALE` logs one INFO; `UNOWNED` and `LIVE` behave as today
  - [x] Success: the exit-code mapping is defined once

## Task 20 — Wait tests; commit

- [x] In `tests/pipeline/test_run_wait.py`: `ORPHANED` ends the wait (exit 8, WARNING); `STALE`
      logs one WARNING, continues, and ends on terminal status or `--timeout`; stale→live logs
      one INFO; unowned keeps waiting; CLI exit-code mapping covers 8 in `test_runs_command.py`
  - [x] Success: tests pass; existing wait tests unchanged
- [x] Commit: `feat: sq runs wait exits 8 for orphaned runs`

## Task 21 — `run_listing`: liveness, `RunListing`, unavailable reasons (D10)

- [x] `RunSummary` gains `liveness`, `active_step`, `active_item` (set only for `running`);
      add `RunListing(rows, unavailable)`; `list_run_summaries` returns it
- [x] `_Definitions` keeps the per-pipeline load cache but stops logging per run; it collects
      pipeline → loader message; one DEBUG record per unavailable pipeline
- [x] Running runs enter the default view (loading no definition or report); `--all` still
      adds completed runs with nothing to resume; the unreadable-file WARNING is unchanged
  - [x] Success: no per-run WARNING for an unavailable pipeline remains

## Task 22 — Listing tests; commit

- [x] In `tests/pipeline/test_run_listing.py` (seed via `run_listing_support.py`): live,
      stale, orphaned and unowned rows; `unavailable` maps pipeline → message with one entry
      per pipeline; no WARNING per run; update 199 tests that assert running runs are hidden
  - [x] Extend the I/O-bounds test with 20 running runs (10 live PID, 10 dead): definition and
        report load counts unchanged, `process_alive` called exactly 20 times
  - [x] Success: tests pass
- [x] Commit: `feat: show running runs and liveness in run listings`

---

## Part E — Renderer and listings (D11, UI Specifications)

## Task 23 — `cli/columns.py`

- [x] Create `src/squadron/cli/columns.py` with `Column(header, shrinkable)`,
      `fit_widths(natural, shrinkable, available)`, `render_rows(columns, rows, *, available)`
      and `available_width(console)` per D11
  - [x] `fit_widths`: shrink the widest shrinkable column one cell at a time; never below
        `MIN_TRUNCATED_COLUMN_WIDTH = 8` or a narrower natural width; stop when nothing can
        shrink; `available=None` means no truncation
  - [x] Cells are `rich.text.Text`; measure with `cell_len`, truncate with
        `Text.truncate(width, overflow="ellipsis")`; gap 2, indent 2
  - [x] Success: module imports no pipeline code

## Task 24 — `columns` tests

- [x] `tests/cli/test_columns.py`: already fits; one column shrinks; several shrink; the
      floor of 8; a non-shrinkable column is never cut; `available=None`; wide characters
      measured by cell width; `render_rows` on a non-TTY console emits no ANSI and no `…`
  - [x] Success: tests pass
- [x] Commit: `feat: add terminal-fitting column renderer`

## Task 25 — Move the runs listing onto `columns`; summary line; `-v`

- [x] In `cli/run_views.py` replace the rich table with `render_rows`: columns Run ID, Status
      (never shrink), Pipeline, Target, At, Started, Activity per the UI spec; a single dict
      keyed by `RunLiveness` maps to display statuses `orphaned` (red) and `stale` (yellow);
      `running` is cyan; unowned running runs show an empty Activity cell
  - [x] At = 199 "Resume at" text for resumable runs, else `active_step` plus
        `[item P/T · index]`; Activity = `elapsed · progress-age ago`, with
        ` · heartbeat <age> ago` for stale
- [x] In `cli/commands/runs.py` add `list -v`; print the stderr summary line
      `<R> runs reference <P> unavailable pipelines (-v for details; sq runs prune --status
      unavailable removes them).` when `unavailable` is non-empty, and under `-v` one
      `  <pipeline>: <message>` line per pipeline
  - [x] Success: no per-run warnings print; the summary line text is defined once

## Task 26 — Runs listing view and CLI tests; commit

- [x] `tests/cli/test_run_views.py` / `test_runs_command.py`: each status and colour; At and
      Activity text for running, stale, orphaned; width-limited console truncates Target with
      `…` and keeps Run ID intact; piped output has no `…`; the summary line and `-v` detail
      lines (once per pipeline) are asserted; update 199 view tests that expect the old table
  - [x] Success: tests pass
- [x] Commit: `feat: render sq runs list with column fitting and liveness`

## Task 27 — `PipelineInfo.params` and the plain `sq pipelines list`

- [x] Add `PipelineInfo.params` (name, default or `required`, declaration order) populated by
      `discover_pipelines`
- [x] Replace the pipelines table in `run_views.py` with a plain list on `columns`: group
      label bold with dim count, groups in `LISTING_ORDER`, empty groups omitted, Name width
      shared across groups, no box drawing; `-v` adds up to three params as
      `slice=required model=sonnet`, with ` +N` when more
  - [x] Success: no colour other than the label and count styles

## Task 28 — Pipelines listing tests; commit

- [x] In `tests/cli/test_pipelines_command.py` and `tests/pipeline/test_loader.py`: params
      order and defaults; counts per group; shared Name width across groups; `-v` ` +N`
      suffix; no box-drawing characters
  - [x] Success: tests pass
- [x] Commit: `feat: plain aligned sq pipelines list with params`

---

## Part F — `pipelines show` and `runs prune`

## Task 29 — `loader.resolve_pipeline`

- [x] Add `resolve_pipeline(name) -> PipelineInfo` using the same search as `load_pipeline`
      (`_search_dirs`, `_find_by_identity`); refactor `load_pipeline` to call it
  - [x] A path argument is reported as not found, with the loader's message
    Returns `PipelineLocation(name, source, path)`, not `PipelineInfo`: resolution must not need a valid parse (recorded in the slice design, API Contracts).
  - [x] Success: `load_pipeline` behaviour and error text unchanged

## Task 30 — `sq pipelines show <name> [--path]`

- [x] In `cli/commands/pipelines.py` add `show`: read the whole file with `Path.read_bytes()`
      first; print `# source: <source>` and `# path: <path>` then the bytes to
      `sys.stdout.buffer`; `--path` prints only the path and does not read the file
  - [x] Not found → stderr loader message, exit 1
  - [x] `OSError` on read → ERROR log with path, stderr `Error: cannot read <path>:
        <reason>`, exit 1, empty stdout

## Task 31 — `show` tests; commit

- [x] CLI tests: a built-in; a project shadow of a built-in (shadow's path and source shown);
      `--path`; not found (exit 1); unreadable file (mode `000`): exit 1, ERROR record, empty
      stdout; non-UTF-8 bytes pass through unchanged; `resolve_pipeline` unit tests
  - [x] Success: tests pass
- [x] Commit: `feat: add sq pipelines show and resolve_pipeline`

## Task 32 — State scan and report-file pattern

- [x] Add `StateManager.scan_runs()` returning readable `RunState`s and unreadable files
      (path, mtime, reason) using `STATE_READ_ERRORS`; `list_runs` keeps its behaviour
- [x] In `batch_report.py` define the report-sibling glob once (`.report.json` and
      `.report.md`) beside `report_json_paths`
  - [x] Success: `grep -rn "report\.md" src` shows one definition of the pattern
- [x] Tests: `scan_runs` returns an unreadable file for invalid JSON and for an obsolete
      schema; the report helper does not match another run's files, including a prefix run-id
  - [x] Success: tests pass

## Task 33 — `run_prune.py`: selection

- [x] Create `src/squadron/pipeline/run_prune.py` with `PruneCategory(StrEnum)` (D9 table),
      `PruneCandidate`, `PrunePlan` (candidates + refusals) and `plan_prune(scan, *,
      statuses, run_ids, pipeline, older_than, now, load_definition, assess)`
  - [x] Default set `failed`, `orphaned`, `unavailable`, `unreadable`; `--status` replaces
        it; run-ids select exactly those runs; run-ids with statuses raises a usage error
        type the CLI maps to exit 2
  - [x] `--pipeline` lowercased, excludes unreadable files; age is `now - updated_at` or file
        mtime for unreadable
  - [x] Success: candidates carry every matched category; no category string literals outside
        the enum

## Task 34 — `run_prune.py`: protection rules

- [x] Apply after selection: drop `PAUSED` runs unless named or `PAUSED` selected (also when
      they match `unavailable`); never include a `LIVE` run, and a named live run becomes a
      refusal; drop `UNOWNED` running runs unless named or `UNOWNED` selected; `STALE` only
      via `--status stale` or run-id
  - [x] Success: each rule has one implementation point

## Task 35 — `plan_prune` tests

- [x] `tests/pipeline/test_run_prune.py`: each category; default set excludes paused, stale,
      unowned and completed; each protection rule (including paused/unowned also matching
      unavailable); named live run refused; `--status` replacement; run-id selection;
      run-id + `--status` usage error; `--pipeline` and `--older-than` filters and their
      combinations; unreadable file age from mtime
  - [x] Success: tests pass
- [x] Commit: `feat: add plan_prune selection and protection`

## Task 36 — `apply_prune`

- [x] Add `apply_prune(plan, runs_dir) -> PruneResult`: delete `{run_id}.json` and its
      report siblings (pattern from Task 32); `FileNotFoundError` counts as already gone;
      any other `OSError` logs ERROR with the path, continues, and is counted as failed
  - [x] Success: only paths under `runs_dir` are touched; the result has removed and failed
        counts

## Task 37 — `apply_prune` tests

- [x] Real files in `tmp_path`: run file + `.report.json` + `.report.md` removed, another
      run's files kept; a missing file is not a failure; an unwritable directory yields an
      ERROR record, a failed count, and continues with the rest
  - [x] Success: tests pass
    The undeletable case uses a directory where the state file should be (unlink raises OSError) rather than an unwritable directory, which would also block the other run's deletes.
- [x] Commit: `feat: add apply_prune`

## Task 38 — `sq runs prune` command

- [x] In `cli/commands/runs.py` add `prune [RUN_ID ...] [--status CATEGORY ...] [--pipeline]
      [--older-than DURATION] [--yes]`; `--status` values validated against `PruneCategory`
      (a non-category is a usage error); `--older-than` parses `<int><unit>` (`s m h d w`)
      leniently on case and whitespace, invalid values are a usage error naming the form
  - [x] Preview (columns renderer, UI spec) then `N run(s) would be removed. Re-run with
        --yes to delete.`, exit 0; with `--yes` delete and print `Removed N run(s).`
  - [x] Exit 1 for any refusal or failed deletion, after finishing the rest; exit 2 for
        usage errors
  - [x] Success: `--yes` is never implied by another flag; prune touches only the runs dir

## Task 39 — Prune CLI tests; commit

- [x] In `tests/cli/test_runs_command.py`: preview deletes nothing; `--yes` deletes exactly
      the previewed runs and their reports; preview labels (`stale`, `unowned`); paused only
      by name or `--status paused`; live run named → refusal, exit 1; usage errors exit 2
      (run-id with `--status`, non-category status, bad `--older-than`); duration parse cases
  - [x] Success: tests pass
- [x] Commit: `feat: add sq runs prune`

---

## Part G — Docs, issues, verification

## Task 40 — Docs and architecture note (design Dev Approach step 8)

- [x] Update `README.md`, `docs/PIPELINES.md` and `docs/COMMANDS.md`: `orphaned`/`stale`,
      `sq runs list -v`, `sq runs wait` exit 8, `sq runs prune`, `sq pipelines show`, both new
      config keys
- [x] Add short user-facing bullets to `CHANGELOG.md` (technical detail goes in DEVLOG)
- [x] Add the D12 paragraph (events vs `RunObserver`) to the Component Architecture section
      of `user/architecture/140-arch.pipeline-foundation.md`
  - [x] Success: every new command and key appears in COMMANDS.md; docs build nothing new
- [x] Commit: `docs: document run liveness, prune, pipelines show`

## Task 41 — Close-out issues

- [x] Open a GitHub issue for resuming orphaned runs (Technical Scope, Excluded; needs a rule
      for the in-flight step); link its number from the slice design's Excluded entry
  - Opened #195 (https://github.com/ecorkran/squadron/issues/195); linked from the slice design's Excluded entry.
  - [x] Success: the new issue number is recorded in the slice design; #190 and #165 are
        closed in Phase 7 after the merge, not here

## Task 42 — Full validation and walkthrough

- [x] Run `ruff format`, `ruff check`, `pyright` and `pytest tests -q`
  - [x] Success: zero pyright errors; results match the Task 3 baseline plus new tests
  Main tree: 6248 passed, 4 skipped, 0 failed; pyright 0 errors (baseline 6081 passed).
- [x] Run Verification Walkthrough steps 1–5 and 8 from the slice design in a scratch HOME
      (add a seed helper under `tests/pipeline/` that writes the orphan, stale, unowned,
      gone and junk runs); steps 6–7 need credentials, so run them if available and
      otherwise record them as not run
  - [x] Success: outputs match the design; any difference is noted in the DEVLOG
  Steps 1–5 and 8 run in a scratch HOME (seed: tests/pipeline/walkthrough_seed.py); steps 6–7 not run: sq run refuses inside a Claude Code session. Corrections recorded in the slice design's Verification Walkthrough.
- [x] Mark the slice design `status: complete` and update the slice plan entry
- [x] Commit: `docs: record slice 174 verification`
