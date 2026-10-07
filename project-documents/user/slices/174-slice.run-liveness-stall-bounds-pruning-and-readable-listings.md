---
docType: slice-design
slice: run-liveness-stall-bounds-pruning-and-readable-listings
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [150, 156, 199, 932]
interfaces: []
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

# Slice Design: run-liveness-stall-bounds-pruning-and-readable-listings

## Overview

Pipelines now run unattended for long stretches, and three gaps show up there:

- A run whose process died stays `running` forever.
- A stalled foreground turn waits forever.
- The runs directory fills with rows nobody can act on.

This slice fixes [#190](https://github.com/ecorkran/squadron/issues/190) (liveness) and [#165](https://github.com/ecorkran/squadron/issues/165) (foreground stall bound). It adds `sq runs prune` and `sq pipelines show`, and it reworks the 199 listings so they read well in a terminal and stay complete when piped.

## Value

- **Unattended runs:**
  - A crashed run shows as `orphaned` instead of `running`.
  - `sq runs wait` returns for an orphaned run instead of blocking forever.
  - A stalled turn fails its step with a named reason instead of hanging the batch.
- **Users:**
  - `sq runs list` shows where a live run is: its step, its item, how long it has run and when it last moved.
  - Dead rows can be removed with a preview first.
  - Both listings fit the terminal.
  - Built-in pipeline YAML can be found and read without digging through the installed package.
- **Agents:** an agent that started a run in the background can tell "still working" from "dead" with one command and an exit code.

## Technical Scope

**Included**
- **(a) Liveness (#190).**
  - `RunState` schema v5 gains an owner record (PID, host, claim time, heartbeat interval), a heartbeat timestamp, the active step, the active `each` item and a progress timestamp.
  - A heartbeat task runs for the life of every SDK run.
  - A pure liveness assessment classifies a `running` run as live, orphaned or unowned.
  - `sq runs list` shows running and orphaned runs. `sq runs wait` gains an `ORPHANED` outcome.
  - Resuming a run marks it `running` again, under the new owner.
- **(b) Foreground stall bound (#165).**
  - A new config key, `pipeline.foreground_idle_timeout_s`, bounds silence on a foreground turn.
  - When the bound fires, the turn is interrupted, the step fails with a named reason, and a WARNING is logged. The session stays usable if the interrupt completes cleanly, and is marked unusable if not.
- **(c) `sq runs prune`.**
  - Select runs by category (`failed`, `orphaned`, `unavailable`, `unreadable`, `completed`, `paused`), `--pipeline`, `--older-than` and explicit run-ids.
  - Preview by default. `--yes` deletes.
  - Paused runs are protected unless selected by name or by `--status paused`. A live run is never deleted.
- **(d) `sq runs list` output.**
  - One stderr summary line replaces the per-run "pipeline unavailable" warnings. `-v` prints the details, once per pipeline.
  - A shared column-fitting renderer replaces the rich table.
- **(e) `sq pipelines list` output.**
  - A plain aligned list, with a label and count for each group and column widths shared across groups.
  - `-v` adds up to three params with their defaults.
- **(f) `sq pipelines show <name> [--path]`.**

**Excluded**
- Resuming an orphaned run. `RESUMABLE_STATUSES` stays `{paused, failed}`. An orphaned run is visible and prunable but not resumable. That needs a rule for the step that was in flight, which is beyond this slice. A GitHub issue records it (Implementation Notes, step 7).
- Fixing #169 (`sq run <path>` records the path as the pipeline name). Prune removes the rows it produces, but the cause stays.
- Liveness for prompt-only runs. No squadron process owns a prompt-only run between `--next` and `--step-done` calls, so these runs are `UNOWNED` (D3).
- Changing the automatic keep-10 `StateManager.prune()` that `init_run` calls.
- `--json` output for either listing (#192 is unchanged).
- Typing `RunState.status` as an enum (#191). `orphaned` is a derived display state and is never persisted (D4).

## Dependencies

### Prerequisites
- **150 (complete):** `RunState`, `StateManager`, the schema-version gate and `--resume`.
- **156 (complete):** executor hardening. This slice adds a progress callback beside `on_step_complete`.
- **199 (complete):**
  - `sq runs list` and `sq runs wait`
  - `run_listing.py`, `run_wait.py`, `run_views.py`
  - `PipelineSource` and `LISTING_ORDER`
- **932 (complete):** `SDKExecutionSession._read_turn` with its per-read `asyncio.timeout` idle timer, and `pipeline.background_idle_timeout_s`.

### Interfaces Required
- `state.py`:
  - `RunState`, `_SCHEMA_VERSION`, `_SUPPORTED_SCHEMA_VERSIONS`
  - `STATE_READ_ERRORS`, `RUNNING_STATUS`, `RESUMABLE_STATUSES`
  - `StateManager.list_runs`, `_write_atomic`, `_append_step`, `finalize`
- `cli/commands/run.py` `_run_pipeline_sdk`: the single `execute_pipeline` call site for new, resumed and item-resumed SDK runs.
- `executor.py` `execute_pipeline(on_step_complete=...)` and the `each` loop (`executor.py:1553-1597`).
- `sdk_session.py`:
  - `_collect_turns`, `_read_turn`, `_IdleTimer`
  - `unusable_reason` and `_require_usable`
- `actions/dispatch.py` `execute()`, including its exception mapping.
- `config/keys.py` `CONFIG_KEYS` and `config/manager.py` `get_typed_config`.
- `loader.py`:
  - `discover_pipelines`, `load_pipeline`, `_search_dirs`, `_find_by_identity`
  - `PipelineInfo`, `PipelineSource`
- `batch_report.py` `report_json_paths`. Prune also needs the `.report.md` sibling (D9).
- `claude_agent_sdk.ClaudeSDKClient.interrupt()`, which sends an `interrupt` control request. The SDK bounds the request with its own 60 s timeout (`_internal/query.py:_send_control_request`).

## Architecture

### Component Structure

```
pipeline/state.py          RunState v5 fields; RunOwner, ActiveItem models;
                           StateManager.claim(), heartbeat(), record_progress(), scan_runs()
pipeline/run_liveness.py   (new) RunLiveness, OrphanReason, LivenessAssessment,
                           assess_liveness(), process_alive(); STALE_HEARTBEAT_INTERVALS
pipeline/run_heartbeat.py  (new) RunHeartbeat async context manager (claim + periodic heartbeat)
pipeline/executor.py       on_progress callback: step start, each-item start
pipeline/sdk_session.py    foreground idle bound; interrupt + drain; DispatchStalledError
pipeline/actions/dispatch.py  maps DispatchStalledError to a failed ActionResult (WARNING)
pipeline/run_listing.py    RunSummary gains liveness + progress; running runs in default view;
                           unavailable-pipeline reasons returned, not logged per run
pipeline/run_wait.py       WaitOutcome.ORPHANED (exit 8)
pipeline/run_prune.py      (new) PruneCategory, PruneCandidate, plan_prune(), apply_prune()
pipeline/loader.py         resolve_pipeline() (shared by load_pipeline and show);
                           PipelineInfo.params
config/keys.py             pipeline.foreground_idle_timeout_s, pipeline.run_heartbeat_interval_s
cli/columns.py             (new) fit_widths(), Column, render_rows(): terminal-fitting renderer
cli/run_views.py           runs/pipelines/prune renderers on cli/columns; summary line
cli/commands/runs.py       list -v; prune
cli/commands/pipelines.py  list -v; show
cli/commands/run.py        _run_pipeline_sdk wraps execute_pipeline in RunHeartbeat
```

Dependency direction is unchanged from 199: `cli/commands/*` → `cli/run_views` → `cli/columns` and `pipeline/*`. `run_liveness` is pure, with no I/O except the injected `process_alive`. `run_listing`, `run_wait` and `run_prune` all assess liveness through it, so "orphaned" has one definition.

### Data Flow

**Run lifecycle (SDK mode).** `_run_pipeline_sdk` enters `RunHeartbeat(state_mgr, run_id, interval)` around `execute_pipeline`.
1. **Enter:** `StateManager.claim(run_id)` writes:
   - `owner = RunOwner(pid, hostname, claimed_at, heartbeat_interval_s)`
   - `heartbeat_at = now`
   - `status = RUNNING_STATUS`
   - `progress_at = now`

   It does this for new and resumed runs alike. On resume this replaces today's behaviour, where a resumed run keeps its `paused` or `failed` status while it runs.
2. **Heartbeat:** an `asyncio` task calls `StateManager.heartbeat(run_id)` every `interval` seconds. That call rewrites `heartbeat_at` only.
3. **Progress:** `execute_pipeline(on_progress=state_mgr.make_progress_callback(run_id))`.
   - At each top-level step start, the executor reports `RunProgress(step=name, item=None)`.
   - At each `each` item start, it reports `RunProgress(step=each_name, item=ActiveItem(position, total, index))`.
   - `record_progress` writes `active_step`, `active_item` and `progress_at`.
   - `_append_step` (step complete) clears `active_item` and sets `progress_at`.
4. **Exit:** the heartbeat task is cancelled, then `finalize` writes the terminal status as today and clears `active_step` and `active_item`. The owner record stays as history. Liveness is assessed only while status is `running`.

**Liveness assessment.** `assess_liveness(state, *, now, hostname, process_alive) -> LivenessAssessment` follows D3. Its readers are listing, wait and prune.

**Foreground stall.** `_collect_turns` reads foreground turns with `idle_s = foreground_idle_timeout_s`. Today the read has no bound. Background-wait reads keep 932's key. When the foreground timer expires:
1. Call `client.interrupt()`.
2. Drain the stream until the dispatch's own `ResultMessage`, with each read bounded by `INTERRUPT_DRAIN_TIMEOUT_S`.
3. Raise `DispatchStalledError`.

`dispatch.execute()` catches that error, logs a WARNING and returns `ActionResult(success=False, error=...)`. The step then fails through the existing path (D7).

**Prune.**
1. `StateManager.scan_runs()` returns the readable `RunState`s and the unreadable files.
2. `plan_prune(scan, selection, now, definitions, liveness)` returns `PruneCandidate`s with their matched categories, plus refusals.
3. The CLI renders the preview.
4. With `--yes`, `apply_prune(candidates, runs_dir)` deletes each state file and its report siblings, and reports a count.

**`sq runs list`.** `list_run_summaries` now returns `RunListing(rows, unavailable: dict[pipeline, reason])`. The CLI does three things:
- renders the rows with `cli/columns`;
- prints one stderr summary line when `unavailable` is non-empty;
- under `-v`, prints one line per unavailable pipeline.

### State Management

`RunState` schema v5 (D2). Every new field has a default of `None`, so v3 and v4 files still load and read as `UNOWNED`. `_SUPPORTED_SCHEMA_VERSIONS = {3, 4, 5}`. Every write in this slice goes through the existing load, modify and `_write_atomic` path, on the event-loop thread (D5).

## Technical Decisions

### Technology Choices
- **Liveness signal: PID plus heartbeat.** The PID alone is fooled by PID reuse, and it cannot be checked from another host when the runs directory is synced or shared. A heartbeat alone cannot tell a crash from a slow write for up to the stale window. Either signal can convict on its own (D3).
- **`os.kill(pid, 0)`** for the process check (`ProcessLookupError` means gone, `PermissionError` means alive). No new dependency such as psutil.
- **Heartbeat as an `asyncio` task**, not a thread. State writes then stay on one thread, with no lock (D5).
- **Interrupt through `ClaudeSDKClient.interrupt()`**, the SDK's supported way to end a turn. A stalled session is not torn down: a reconnect would lose the session's context for the steps after it.
- **Own column fitter in place of rich `Table` (D11).**
  - Rich wraps or folds to the console width, which on a non-TTY is 80 columns (or `COLUMNS`), so piped output is cut.
  - Rich tables also cannot share column widths across the separate tables of each group.
  - The fitter uses `rich.text.Text` for styling, measurement (`cell_len`) and ellipsis truncation, and `rich.console.Console` for output, so colour is still dropped on non-TTY and under `NO_COLOR`.
  - The width algorithm is cf's `output/tables.ts` `fitColumnWidths`.

### Patterns and Conventions

**D1. Config keys.** Both keys live in `config/keys.py` `CONFIG_KEYS`, typed `int`. Each is validated `> 0` where it is read, and a non-positive value raises `ValueError` naming the key.

| Key | Default | Meaning |
|---|---|---|
| `pipeline.foreground_idle_timeout_s` | 1800 | Longest silence allowed on a foreground turn before it is interrupted. Same value and semantics as 932's `background_idle_timeout_s`: silence, not total time. |
| `pipeline.run_heartbeat_interval_s` | 30 | Seconds between heartbeat writes. |

There is no "disabled" value. A user who wants no practical bound sets a large number.

`INTERRUPT_DRAIN_TIMEOUT_S = 60` (in `sdk_session.py`) and `STALE_HEARTBEAT_INTERVALS = 10` (in `run_liveness.py`) are protocol constants, not user tuning. Each is defined once. The drain bound matches the SDK's own 60 s control-request bound.

**D2. Schema v5 fields.**

```python
class RunOwner(BaseModel):
    pid: int
    hostname: str
    claimed_at: datetime
    heartbeat_interval_s: int   # the writer's interval; readers judge staleness by it

class ActiveItem(BaseModel):
    position: int               # 0-based position in the each step's item list
    total: int
    index: str | None           # the item's own "index" field when present (plan slice index)

# RunState additions (all default None)
owner: RunOwner | None
heartbeat_at: datetime | None
active_step: str | None         # the step running now; current_step keeps its meaning
progress_at: datetime | None    # last step start, item start or step completion
active_item: ActiveItem | None
```

`current_step` already means "last step completed" (`state.py:351`), and resume logic reads it. It is not renamed, so the running step gets a field of its own, `active_step`. Recording the interval in the owner means a reader whose config differs from the writer's still judges staleness correctly.

**D3. Liveness rule** (`run_liveness.py`). This applies only to `status == RUNNING_STATUS`.

| Condition | Result |
|---|---|
| `owner is None` (v3/v4 file, prompt-only run) | `UNOWNED` |
| `owner.hostname == hostname` and `not process_alive(owner.pid)` | `ORPHANED`, reason `PROCESS_GONE` |
| `now - heartbeat_at > STALE_HEARTBEAT_INTERVALS × owner.heartbeat_interval_s` | `ORPHANED`, reason `HEARTBEAT_STALE` |
| otherwise | `LIVE` |

- On another host, only the heartbeat test applies.
- `LivenessAssessment(liveness, reason, elapsed, progress_age)` carries both durations:
  - `elapsed` is `now - owner.claimed_at`, so a resumed run counts from its resume.
  - `progress_age` is `now - progress_at`.
- `UNOWNED` runs keep today's behaviour everywhere: listed as `running`, waited on, never pruned as orphaned.

**D4. `orphaned` is derived, never persisted.** A read never writes. The listing, wait and prune each assess the run themselves, and the state file keeps `running`. Persisting it would put a second writer on a file the owner may still be writing, if the verdict was wrong. It would also need the status enum (#191). The display status lives in `run_views` as `RUN_DISPLAY_ORPHANED`, keyed by `RunLiveness.ORPHANED`.

**D5. One writer thread.**
- All `StateManager` writes for a run happen on the event-loop thread of the owning process: the step callback, the progress callback, pool selection, the heartbeat and finalize.
- Load, modify and write is synchronous, so two writes cannot interleave.
- The one `to_thread` near state writes, `executor.py:1459`, writes the batch report, not the state file.
- Task 1 confirms no state write runs off the loop thread. If one does, `StateManager` gains a per-run `threading.Lock` around load, modify and write.

**D6. Heartbeat failure.** An `OSError` from a heartbeat write is logged at WARNING with the run-id, and the run continues. A run is not killed because its bookkeeping failed. If writes keep failing, the run turns `ORPHANED (HEARTBEAT_STALE)` after the stale window. That is the observable signal, and the WARNINGs explain it. `claim` failing at start is fatal: it raises, the way `init_run` does today.

**D7. Foreground stall.**
- `_read_turn` already applies `idle_s` to each read with its own `_IdleTimer`. Today `_collect_turns` passes `idle_s=None` for foreground reads (`:217`) and will pass `foreground_idle_timeout_s` instead.
- A private `_ForegroundIdleTimeout` marks expiry, as `_BackgroundIdleTimeout` does. `_collect_turns` handles it:
  1. Log WARNING `dispatch: foreground turn silent for %ds; interrupting`.
  2. `await client.interrupt()`.
  3. Drain with `_read_turn(idle_s=INTERRUPT_DRAIN_TIMEOUT_S)` until the dispatch's own result arrives. A `ResultMessage` with `is_error` is expected here and is not re-raised as `ProviderAPIError`.
  4. **Session stays usable** when the interrupt and the drain both complete. The next step, or the next `each` item, dispatches as usual.
  5. **Session becomes unusable** when the interrupt raises, the drain times out or the stream ends. `unusable_reason` is set to `foreground stall: interrupt did not complete (<detail>)`, logged at ERROR. Every later call fails fast through the existing `_require_usable`.
  6. Raise `DispatchStalledError(idle_s, session_usable)`. It is a public subclass of `ProviderError` in `sdk_session.py`.
- `dispatch.execute()` catches `DispatchStalledError` ahead of its generic `Exception` handler. It logs a WARNING without a traceback and returns `ActionResult(success=False, error="dispatch stalled: no output for <N>s; turn interrupted", metadata={"stalled": True, "session_usable": ...})`.
- Background tracking is not affected. If the stall fires while 932's ledger is active, the turn is a background wait and is governed by 932's key.

**D8. `sq runs wait`.** On each poll that sees `running`, `wait_for_run` assesses liveness. `ORPHANED` ends the wait with `WaitOutcome.ORPHANED`, exit **8**. This is the next free code: 0–7 are taken (199 D13). The result is logged at WARNING with the reason, and stderr reads `sq runs wait: run <id> orphaned (<reason>)`. `wait_for_run` gains injected `now: Callable[[], datetime]`, `hostname` and `process_alive`, beside the existing `clock` and `sleep`.

**D9. Prune selection.**

`PruneCategory(StrEnum)`:

| Category | Matches |
|---|---|
| `FAILED` | status `failed` |
| `ORPHANED` | assessed `ORPHANED` (D3) |
| `UNAVAILABLE` | pipeline cannot be loaded (199's `ResumeProblem.PIPELINE_UNAVAILABLE` rule) |
| `UNREADABLE` | the file is in `STATE_READ_ERRORS`, schema-obsolete included |
| `COMPLETED` | status `completed` |
| `PAUSED` | status `paused` |

**Selection rules:**
- **Default** (no `--status`): `failed`, `orphaned`, `unavailable`, `unreadable`. In the default set, `orphaned` matches only `PROCESS_GONE` orphans. A `HEARTBEAT_STALE` orphan is selected only by an explicit `--status orphaned` or by run-id (see Risk Assessment).
- **`--status`** is repeatable and replaces the default set.
- **Run-ids**, given as positional arguments, select exactly those runs whatever their category. Run-ids combined with `--status` is a usage error (exit 2).
- **Matching:** a run is a candidate if any selected category matches it.
- **Filters:** `--pipeline` and `--older-than` narrow the candidates further.
  - `--pipeline` is lowercased (199 D9) and excludes unreadable files, which have no pipeline.
  - Age is `now - updated_at`, or the file mtime for an unreadable file.

**Protection rules,** applied after selection:
- **Paused:** a paused run is dropped unless it was named by run-id or `PAUSED` is in `--status`. This holds even when it also matches `unavailable`.
- **Live:** a `LIVE` run is never a candidate. Naming one is refused: a stderr line, and exit 1 after the rest of the preview or deletion. An `UNOWNED` `running` run is protected the same way, because liveness cannot be judged.

**`--older-than`** takes `<int><unit>`, with unit `s`, `m`, `h`, `d` or `w`. The parse is lenient about surrounding whitespace and case. An invalid value is a usage error naming the accepted form.

**Deletion** removes `{run_id}.json` and every `{run_id}.*.report.json` and `{run_id}.*.report.md`. The report pattern is defined once, in `batch_report.py`, next to `report_json_paths`. A `FileNotFoundError` on delete counts as already gone. Any other `OSError` is logged at ERROR with the path, and pruning continues. The command exits 1 if any deletion failed.

**D10. Unavailable-pipeline reporting.**
- `_Definitions` keeps caching load failures per pipeline but stops logging per run.
- `list_run_summaries` returns `RunListing.unavailable`, mapping each pipeline name to the loader's message.
- The CLI prints one stderr line: `<R> runs reference <P> unavailable pipelines (-v for details; sq runs prune --status unavailable removes them).`
- With `-v`, it then prints `  <pipeline>: <message>` once per pipeline. The loader's message names the searched directories.
- The summary line is the observable signal, and a CLI test asserts it.
- `run_listing` also logs one DEBUG record per unavailable pipeline. The existing per-file WARNING for unreadable state files is unchanged.

**D11. `cli/columns.py`.**
```python
@dataclass(frozen=True)
class Column:
    header: str | None       # None: headerless list (pipelines)
    shrinkable: bool         # Run ID / Status / Name are not

def fit_widths(natural: list[int], shrinkable: list[bool], available: int | None) -> list[int]
def render_rows(columns, rows: list[list[Text]], *, available: int | None) -> list[Text]
def available_width(console: Console) -> int | None   # None when not a terminal
```
- `fit_widths` is the `fitColumnWidths` loop from cf:
  - It shrinks the widest shrinkable column one cell at a time.
  - It never shrinks below `MIN_TRUNCATED_COLUMN_WIDTH = 8`, or below a narrower natural width.
  - It stops when nothing can shrink, which leaves the line to wrap.
- Unlike cf, a column can be marked non-shrinkable. Otherwise a run-id, which is needed for copying, would be cut once params reached the minimum.
- `available=None` means no truncation. Truncation uses `Text.truncate(width, overflow="ellipsis")`.
- The column gap is 2 and the indent is 2, both as in cf.

### Error handling summary

| Failure | Observable signal | Outcome |
|---|---|---|
| Heartbeat write `OSError` | WARNING per failure | run continues; turns `ORPHANED` after stale window |
| `claim` fails | exception | run does not start (as `init_run` today) |
| Process dies | `ORPHANED (PROCESS_GONE)` in list; wait exit 8 | — |
| Event loop blocked > stale window | `ORPHANED (HEARTBEAT_STALE)` while blocked | clears on next heartbeat |
| Foreground silence | WARNING; step error `dispatch stalled: …` | step fails; session usable |
| Interrupt or drain fails | ERROR; `unusable_reason` set | step fails; later dispatches fail fast |
| Prune delete `OSError` | ERROR with path | continues; exit 1 |
| Prune names a live/unowned running run | stderr refusal | not deleted; exit 1 |
| Pipeline unavailable in listing | stderr summary line; `-v` detail | row marker as in 199 |

## Implementation Details

### API Contracts

```
sq runs list [--all] [--pipeline NAME] [-v]
sq runs wait <run-id> [--timeout SECONDS]                 # + exit 8 orphaned
sq runs prune [RUN_ID ...] [--status CATEGORY ...] [--pipeline NAME]
              [--older-than DURATION] [--yes]
sq pipelines list [-v]
sq pipelines show <name> [--path]
```

- **`sq runs list`:** the default view now also includes `running` runs, live and orphaned, as well as 199's resumable and problem rows. A running run is the thing a user most wants to check on, and an orphan is something they need to act on. `--all` still adds completed runs that have nothing to resume.
- **`sq runs prune`:** without `--yes` it prints the preview and `N run(s) would be removed. Re-run with --yes to delete.`, then exits 0. With `--yes` it prints `Removed N run(s).`
- **`sq pipelines show`:** resolves `<name>` through `loader.resolve_pipeline(name) -> PipelineInfo`, the same search `load_pipeline` uses. `load_pipeline` is refactored to call it, so resolution has one definition.
  - **Output:** a `# source: <source>` line and a `# path: <path>` line, then the file text byte for byte. The output is still valid YAML, so `> copy.yaml` works.
  - **`--path`:** prints only the path.
  - **Not found:** exits 1 with the loader's message. Paths are not names, so a path argument is reported as not found.

```python
# pipeline/run_listing.py
@dataclass(frozen=True)
class RunSummary:              # 199 fields, plus:
    liveness: LivenessAssessment | None   # set only when status is running
    active_step: str | None
    active_item: ActiveItem | None

@dataclass(frozen=True)
class RunListing:
    rows: list[RunSummary]
    unavailable: dict[str, str]           # pipeline -> loader message

# pipeline/run_prune.py
@dataclass(frozen=True)
class PruneCandidate:
    run_id: str
    pipeline: str | None                  # None for unreadable
    status: str | None
    categories: frozenset[PruneCategory]
    age: timedelta

def plan_prune(scan, *, statuses, run_ids, pipeline, older_than, now,
               load_definition, assess) -> PrunePlan        # candidates + refusals
def apply_prune(plan: PrunePlan, runs_dir: Path) -> PruneResult
```

### UI Specifications

`sq runs list` (TTY 120 columns, params column shrunk):
```
  Run ID                             Pipeline        Target                Status    At                         Started           Activity
  ─────────────────────────────────  ──────────────  ────────────────────  ────────  ─────────────────────────  ────────────────  ──────────────
  run-20261007-implement-plan-4b07a1c2  implement-plan  plan=180 model=opu…   running   slices [item 3/12 · 182]   2026-10-07 09:12  1h04m · 40s ago
  run-20261007-p6-8bc5e634           p6              slice=173 model=s…    orphaned  implement-1                2026-10-07 08:01  2h11m · 1h50m ago
  run-20261006-p4-1a2b3c4d           p4              slice=199             paused    review-design              2026-10-06 14:02
2 runs reference 2 unavailable pipelines (-v for details; sq runs prune --status unavailable removes them).
```
- **Status:** `running` is cyan. `orphaned` is red, with its reason in the `-v` detail. `UNOWNED` running runs show `running` with an empty Activity cell.
- **At:** for a resumable run, 199's "Resume at" text. For a running or orphaned run, `active_step`, plus `[item P/T · index]` when an item is active.
- **Activity:** `elapsed · progress-age ago`, for running and orphaned runs only.
- **Run ID** and **Status** never shrink.

`sq pipelines list`:
```
Built-in (15)
  design-batch     Slice designs for every unstarted slice in a plan
  p4               Slice design with review loop
User (1)
  my-loop          Personal review loop
```
- **Groups:** shown in `LISTING_ORDER`, empty groups omitted, and the Name width is shared across all groups.
- **Colour:** group labels are bold and counts are dim. No other colour, because the list is read and copied rather than scanned for state.
- **`-v`:** adds a third column holding up to the first three params in declaration order, as `slice=required model=sonnet max-revisions=2`. When a pipeline has more, ` +N` is appended, so no param is dropped silently.

`sq runs prune` preview:
```
  Run ID                          Pipeline   Status     Reason                 Age
  run-20261002-test-p4-…          test-p4    completed  unavailable            5d
  run-20261004-p6-77aa…           p6         running    orphaned (process gone) 3d
  run-20261001-x.json             —          —          unreadable             6d
3 run(s) would be removed. Re-run with --yes to delete.
```

### Database / Storage Schema

`~/.config/squadron/runs/{run_id}.json`, schema v5 (D2). The migration is passive: v3 and v4 files load with the new fields at `None` and are rewritten as v5 the next time a run writes them (claim on resume). Older squadron builds reject v5 files with `SchemaVersionError`. That is the existing behaviour for a newer schema, and 199's listing skips such files with a WARNING.

## Integration Points

### Provides to Other Slices
- `assess_liveness` and `RunLiveness`: the single definition of orphaned, for any future orchestrator or `--json` surface (#192).
- `RunState.active_step`, `active_item` and `progress_at`: live progress for in-process callers.
- `DispatchStalledError` and the `stalled` metadata: a named stall signal for review loops and metrology (320).
- `loader.resolve_pipeline`: resolution without loading.
- `cli/columns`: the terminal-fitting renderer for any later listing.

### Consumes from Other Slices
- **932:** the per-read idle timer in `_read_turn`, and the "only the dispatch's own result ends it" rule (932 D6), which the interrupt drain relies on.
- **199:** `RunSummary`, `ResumeProblem`, `_Definitions`, `WaitOutcome` and the run views.
  - The default view of `sq runs list` changes on purpose: running runs are now shown. 199's tests that assert running runs are hidden are updated.

## Success Criteria

### Functional Requirements
- A new SDK run, a resumed run and an item-resumed run each record `owner` and set `status: running` at start. `heartbeat_at` advances every `run_heartbeat_interval_s` while the run lives.
- `active_step` names the running step, and during an `each` step `active_item` names the running item. Both clear at finalize.
- A running run whose process is killed (`kill -9`) lists as `orphaned` within one listing call. `sq runs wait` on it exits 8.
- A v4 `running` file lists as `running` (`UNOWNED`), and `wait` keeps waiting on it, as in 0.21.
- A foreground turn silent longer than `pipeline.foreground_idle_timeout_s` is interrupted:
  - The step fails with an error starting `dispatch stalled:`.
  - A WARNING is logged.
  - The next dispatch in the same session succeeds when the interrupt completed.
- `sq runs prune`:
  - Without `--yes`, it deletes nothing.
  - With `--yes`, it deletes exactly the previewed runs and their report files.
  - It never deletes a live or unowned running run.
  - It deletes a paused run only when the run is named or `--status paused` is given.
- `sq runs list` prints no per-run warnings. It prints at most one unavailable-pipeline summary line, and `-v` prints one detail line per pipeline.
- On a TTY, `sq runs list` fits within the terminal width, shrinking the widest shrinkable column with `…` and never below 8. When piped, it never truncates.
- `sq pipelines list` prints aligned groups with counts and shared widths, and no box drawing. `-v` adds the params column.
- `sq pipelines show p4` prints the source, the path and the YAML exactly as written. `--path` prints only the path.

### Technical Requirements
- `run_liveness` unit tests cover every D3 row with injected `now`, `hostname` and `process_alive`:
  - same host, process gone;
  - stale heartbeat with the process alive (PID reuse);
  - another host, fresh heartbeat and stale heartbeat;
  - unowned.
- `RunHeartbeat` test, with a short interval and a real `StateManager` in `tmp_path`:
  - the claim is written;
  - at least two heartbeats are written;
  - the task is cancelled on exit;
  - an `OSError` on write logs a WARNING and does not raise.
- Executor tests assert the `on_progress` call order for a plain step and for an `each` step (one call per item).
- `sdk_session` tests use a fake client whose stream goes silent:
  - the interrupt is sent;
  - the drain reaches the result;
  - the session stays usable;
  - `DispatchStalledError` is raised.

  A second fake, whose interrupt raises, leaves the session unusable with an ERROR record. Background-wait behaviour (932 tests) is unchanged.
- The dispatch action test asserts a `DispatchStalledError` gives a failed `ActionResult` and a WARNING, with no traceback logged.
- `plan_prune` tests cover each category, each protection rule, filter combinations, run-id selection and the run-id/`--status` usage error. `apply_prune` tests use real files, including reports, a missing file and an unwritable directory.
- `fit_widths` tests: fits already; one column shrinks; several shrink; the minimum floor; a non-shrinkable column; `available=None`.
- `wait_for_run` gains an `ORPHANED` test. The CLI exit-code mapping test covers exit 8.
- Fixtures are real: run states are written through `StateManager`, and a dead PID comes from a subprocess that has already exited.
- Tests never read the real runs directory or the user pipelines (`tests/_hermetic.py`).
- `ruff format`, `ruff check` and `pyright` pass with zero errors.

### Integration Requirements
- `sq run`, `--resume`, `--item`, `--status`, prompt-only `--next` and `--step-done` behave as before, except that a resumed run now reads `running` while it runs.
- Existing 932 background-wait tests and the 199 listing tests pass. The 199 tests that assert running runs are hidden from the default view are updated, as noted above.

### Verification Walkthrough

Draft, to be refined in Phase 6. Steps 1–5 use a scratch `HOME` and project. Steps 6 and 7 need model credentials and read nothing from real runs.

**Scratch setup.** Seed runs with the 199 support helpers (`tests/pipeline/run_listing_support.py`). Add a running v5 run owned by a dead PID, and copy a v4-shaped running file:

```bash
S=$(mktemp -d); mkdir -p $S/home $S/proj
# seed.py (Phase 6 adds a helper): writes paused/failed/completed runs as in 199, plus
#  - "orphan": claim() with pid of an already-exited `python -c pass`
#  - "unowned": a running state with no owner (v4 shape)
#  - "gone": a completed run of a pipeline that no longer exists
#  - "junk": a run file with invalid JSON
HOME=$S/home PYTHONPATH=. python $S/seed.py $S/proj
cd $S/proj && export HOME=$S/home
```

1. **Liveness in the listing.**
   ```bash
   sq runs list
   ```
   - The orphan row shows `orphaned` with an Activity cell.
   - The unowned row shows `running`.
   - One stderr line reads `1 runs reference 1 unavailable pipelines (-v for details; …)`, with no per-run warnings.
   - `sq runs list -v` adds the `gone` pipeline's loader message once.
2. **Wait on an orphan.**
   ```bash
   sq runs wait <orphan-id>; echo "exit $?"          # "… orphaned (process gone)"; exit 8
   sq runs wait <unowned-id> --timeout 3; echo $?    # exit 4 (still treated as running)
   ```
3. **Width.**
   ```bash
   COLUMNS=90 sq runs list            # Target shrinks with "…"; Run ID intact
   sq runs list | cat                 # no "…" anywhere; full params
   ```
4. **Prune.**
   ```bash
   sq runs prune                      # preview: orphan, failed, gone, junk; paused absent
   ls $HOME/.config/squadron/runs | wc -l     # unchanged
   sq runs prune --yes                # "Removed 4 run(s)."
   sq runs prune <paused-id>          # preview shows the paused run (named)
   sq runs prune --status running     # usage error: not a category
   ```
5. **Pipelines.**
   ```bash
   sq pipelines list                  # Built-in (N), aligned, no boxes
   sq pipelines list -v               # params column, e.g. "slice=required model=…"
   sq pipelines show p4 | head -3     # "# source: built-in", "# path: …/data/pipelines/P4.yaml", YAML
   $EDITOR "$(sq pipelines show p4 --path)"
   sq pipelines show nope; echo $?    # loader message; exit 1
   ```
6. **Live run** (credentials).
   ```bash
   sq run p4 <slice> --model <alias> &   # any multi-step pipeline
   sq runs list                          # running; At = current step; Activity advancing
   kill -9 %1; sq runs list              # orphaned (process gone)
   ```
7. **Foreground stall** (credentials). Set `pipeline.foreground_idle_timeout_s = 20` in the scratch project's `.squadron.toml`. Run a one-step pipeline whose dispatch prompt asks the model to run `sleep 120` in Bash.
   - The run log shows `dispatch: foreground turn silent for 20s; interrupting`.
   - The step fails with `dispatch stalled: no output for 20s; turn interrupted`.
   - The run ends `failed` within a few seconds of the bound.

## Risk Assessment

### Technical Risks
- **Interrupting a live turn.** The SDK's state after `interrupt()` is not documented. The drain assumes the CLI emits the turn's own `ResultMessage` after an interrupt.
- **False orphan from a blocked event loop.** A synchronous call that blocks the loop for longer than 10 heartbeat intervals (300 s by default) makes a live run read as orphaned. `sq runs prune` could then delete a live run's file, and that run's next state write fails.
- **Silent tool calls.** A legitimate foreground tool call (a long test suite run through Bash) that emits nothing for the idle bound gets interrupted.

### Mitigation Strategies
- **Interrupt:** Phase 6 task 1 is a spike against the installed SDK. It interrupts a real turn and records the messages that follow. If no result arrives, D7's fallback applies (session unusable, step fails). The decision then narrows to "always mark unusable" and the design is updated.
- **Blocked loop:** prune deletes `ORPHANED (HEARTBEAT_STALE)` runs only when `--status orphaned` is given explicitly, or the run is named. The default prune set includes only `PROCESS_GONE` orphans on the same host. The preview shows the reason.
- **Silent tool calls:** the default bound equals 932's 30 minutes, and it is configurable. The walkthrough records whether the CLI emits progress during a long Bash call.

## Implementation Notes

### Development Approach
1. **Spike:** run `interrupt()` against the installed SDK to confirm the post-interrupt stream (risk above). Confirm no `StateManager` write runs off the loop thread (D5).
2. **Schema v5 and the liveness core:** the `RunState` fields, `claim`, `heartbeat`, `record_progress`, `run_liveness.py` and `RunHeartbeat`. Wire them into `_run_pipeline_sdk` and add `on_progress` to the executor. Tests.
3. **Foreground stall:** the config key, the `_collect_turns` change, the interrupt and drain, `DispatchStalledError`, and the dispatch mapping. Tests.
4. **Wait and listing:** `WaitOutcome.ORPHANED`; `RunSummary` liveness, `RunListing` and the unavailable summary; running runs in the default view.
5. **Renderer and listings:** `cli/columns.py`, then move the runs and pipelines renderers onto it (`PipelineInfo.params`, `-v`).
6. **`resolve_pipeline`, show and prune:** `resolve_pipeline` (refactor `load_pipeline` onto it) and `sq pipelines show`. `scan_runs`, `run_prune.py` and `sq runs prune`.
7. **Docs and issues:** update README, docs/PIPELINES.md and docs/COMMANDS.md, add the CHANGELOG lines, and close #190 and #165. Open an issue for resuming orphaned runs (Technical Scope, Excluded).

Effort: 3/5. The parts are independent apart from the shared liveness definition. Steps 2–4 carry the risk; 5 and 6 are mechanical.

### Special Considerations
- **Write volume:** one extra state write per heartbeat (30 s) and one per `each` item start. Both are small atomic rewrites of a single JSON file.
- **Prune is destructive,** and it touches only `~/.config/squadron/runs`. The preview is the default, and `--yes` is never implied by any other flag.
- **Prompt-only runs** stay `UNOWNED` by design (Technical Scope). The listing's empty Activity cell is the visible signal that liveness is unknown for them.
