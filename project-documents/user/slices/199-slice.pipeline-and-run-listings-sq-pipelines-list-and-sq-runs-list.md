---
docType: slice-design
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
parent: project-documents/user/architecture/180-slices.pipeline-intelligence.md
dependencies: [197]
interfaces: []
dateCreated: 20261006
dateUpdated: 20261007
status: complete
---

# Slice Design: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list

## Overview

This slice adds two listing commands as noun groups: `sq pipelines list` ("what can I run?") and `sq runs list` ("what can I resume?"). It fixes [#185](https://github.com/ecorkran/squadron/issues/185) and [#187](https://github.com/ecorkran/squadron/issues/187).

Today pipeline discovery hides under `sq run --list`, which mixes sources in one name-sorted table. Nothing lists runs. `sq run --status latest` shows only one run, so resuming an older paused run, or an item of a finished batch (slice 197), means already knowing its run-id.

## Value

- **Users** see their own pipelines apart from the built-ins, and can find any resumable run along with the `sq run --resume` invocation it needs.
- **Batch workflows (197):** a finished batch run with flagged items shows up as resumable, with its open-item count. Today the only way to find it is the run output or the runs directory.
- **Agents:** can call `sq runs list` to get run-ids instead of guessing them or scraping `~/.config/squadron/runs`.

## Technical Scope

**Included**
- `sq pipelines list`: effective pipelines grouped by source (built-in, project, user), alphabetical within each group.
- `sq runs list`: one row per run, newest first. The default shows resumable runs and runs whose resumability could not be determined. `--all` shows every run. `--pipeline NAME` filters by pipeline.
- `sq runs wait <run-id> [--timeout SECONDS]`: blocks until the run leaves `running`, prints its final status line, and exits with a code per outcome (D13). Lets an agent or script that started a pipeline in the background learn when it is done without polling the runs directory itself.
- A pure run-listing layer (`squadron/pipeline/run_listing.py`) that builds row data from `StateManager` and batch reports. Rendering stays in the CLI.
- One eligibility module (`squadron/pipeline/item_eligibility.py`) shared by the listing and item resume.
- `sq run --list` (and `-l`) is removed (D8). `sq pipelines list` replaces it.
- `sq list` becomes `sq agents list` (D14), so every listing follows `sq <noun> list`.
- Doc references to `sq run --list` are updated: README, docs/PIPELINES.md and docs/QUICKSTART.md.

**Excluded**
- Slash commands and agent skills for the new commands. Adding `/sq:pipelines` and `/sq:runs` widens the slash surface for little gain.
- Changing `sq run --status`. It behaves as today.
- Deleting or pruning runs.
- `--json` output. The listing's Python API serves in-process callers. An out-of-process orchestrator such as Amoeba would need `--json`, which this slice does not build because no such consumer exists yet. [#192](https://github.com/ecorkran/squadron/issues/192) records the follow-up.
- An MCP surface. Squadron has no MCP server: `src/squadron/server` is the agent daemon, with `agents` and `health` routes only.
- Typing `RunState.status`. See D10.

## Dependencies

### Prerequisites
- **197 (complete):** batch reports and item resume.
  - Batch reports: `BatchReport`, `ItemOutcome` and `FlagKind`, with `<run_id>.<step>.report.json` written beside the run state on every exit of an `each` step.
  - Item resume: `sq run --resume <id> --item N --decision ...`.

### Interfaces Required
- `discover_pipelines()`, `load_pipeline()` and `PipelineInfo` in `squadron/pipeline/loader.py`.
- `StateManager.list_runs(pipeline=, status=)`, `StateManager.runs_dir` and `RunState` in `squadron/pipeline/state.py`.
- The `StateManager.first_unfinished_step` logic, which decides where `--resume` restarts.
- `BatchReport.load`, `BatchReportLoadError`, `ItemOutcome`, `FlagKind` and `ItemDecision` in `squadron/pipeline/batch_report.py`.
- `ExecutionStatus` in `squadron/pipeline/executor.py`, reached through `state.py`, which already imports it.

## Architecture

### Component Structure

```
cli/app.py
 ├─ add_typer(pipelines_app, "pipelines")   cli/commands/pipelines.py  (new)
 ├─ add_typer(runs_app, "runs")             cli/commands/runs.py       (new)
 ├─ add_typer(agents_app, "agents")         cli/commands/list.py       (top-level "list" removed)
 └─ command("run")                          cli/commands/run.py   (--list removed)

cli/run_views.py          (new) STATUS_COLORS, render_pipeline_listing(), render_run_listing(),
                          resume-problem marker text. Imported by pipelines.py, runs.py and run.py
                          (STATUS_COLORS, status line); no command module imports another.

pipeline/loader.py           PipelineSource enum, LISTING_ORDER; PipelineInfo.source typed
pipeline/state.py            first_unfinished_step_of() pure function; method delegates
pipeline/batch_report.py     report_json_path(), report_json_paths(); BatchReport.json_path delegates
pipeline/item_eligibility.py (new) RESUMABLE_OUTCOMES, item_decisions(), single_each_step(),
                             ItemResumeUnsupportedError
pipeline/item_resume.py      _validate/_check_record use item_eligibility and report_json_path
pipeline/run_listing.py      (new) RunSummary, ResumePoint, ResumeKind, ResumeProblem,
                             list_run_summaries()
```

Dependency direction: `cli/commands/*` → `cli/run_views` → `pipeline/run_listing` → `pipeline/{item_eligibility, state, batch_report, loader}`. `item_resume` → `item_eligibility`. `item_eligibility` holds pure rules with no I/O, separate from item resume's orchestration (lock, git, executor), so both callers and the parity test exercise the rules without that orchestration.

**Import cost (accepted):** `run_listing` needs `StateManager`, and `state.py` already imports `ExecutionStatus` from `executor.py` at module level, which transitively imports `git_ops`, `branch_ops` and `commit_plan`. The listing therefore loads the executor's import graph. That adds no cost on the CLI path, because `cli/app.py` already imports `run.py`, which imports the executor. Moving `ExecutionStatus` to a lightweight module is a state/executor refactor outside this slice; the listing makes no claim of import isolation.

### Data Flow

**`sq pipelines list`:** `discover_pipelines()` returns the effective set: a later source shadows an earlier one by name, so each pipeline is listed once, under the source `sq run <name>` would load. `render_pipeline_listing()` groups the set by `PipelineSource` in `LISTING_ORDER`, keeps the name sort within each group, and renders one table per non-empty group.

**`sq runs list`:** `list_run_summaries(state_mgr, pipeline=..., include_all=...)` calls `state_mgr.list_runs(pipeline=)`, which already sorts newest first. Pipeline definitions are loaded at most once per pipeline name in one call, through a dict local to the call. For each run:

- **Status `paused` or `failed`**:
  1. Load the definition. If that fails → `ResumeProblem.PIPELINE_UNAVAILABLE`.
  2. Call `first_unfinished_step_of(state, definition)`. `None` → `ResumeProblem.NO_UNFINISHED_STEP`. `--resume` would print "Nothing to resume" for that run.
  3. Otherwise → `ResumePoint(STEP, step_name)`.
- **Status `completed`**:
  1. `report_json_paths(runs_dir, run_id)` is empty → no resume point. The `each` step never ran, so there is nothing to resume, and no definition is loaded.
  2. Otherwise load the definition. If that fails → `PIPELINE_UNAVAILABLE`.
  3. Call `single_each_step(definition)`. `ItemResumeUnsupportedError` → `ResumeProblem.ITEM_RESUME_UNSUPPORTED`. This applies when the pipeline does not have exactly one `each` step, either by design or because it was edited after the run. `--item` would reject this run for the same reason.
  4. Call `BatchReport.load(report_json_path(runs_dir, run_id, each.name))`. `BatchReportLoadError` → `ResumeProblem.REPORT_UNREADABLE`.
  5. Compute `item_decisions(record)` for each record. Records with a non-empty set count toward `open_items`. Records whose set includes `ACCEPT` count toward `acceptable_items`. `open_items > 0` → `ResumePoint(ITEMS, each.name, open_items, acceptable_items)`. Otherwise there is no resume point.
- **Any other status** (`running`): no resume point and no problem.

The default view keeps a run when it has a resume point or a problem. A problem means resumability could not be determined, and that is never hidden. `include_all` keeps every run. The CLI renders the rows with `render_run_listing()`.

### State Management
The listing is read-only. It adds no state and writes neither run state nor reports. It takes no lock: a live run is read as a snapshot (see D7).

## Technical Decisions

### Technology Choices
- **Typer noun groups** (`pipelines_app` and `runs_app`, with `no_args_is_help=True`), following `pools_app` and `models_app`. Actions on a noun (`sq runs wait`) live beside its listing, which a verb-first `sq list <noun>` grammar cannot offer. A `list` subcommand under `sq run` would collide with the pipeline-name positional.
- **Rich tables**, as in the current `--list` and in `sq pools`.

### Patterns and Conventions

**D1. `PipelineSource(StrEnum)`** in `loader.py`, with `BUILT_IN = "built-in"`, `PROJECT = "project"` and `USER = "user"`. `discover_pipelines` and `PipelineInfo.source` use it, so the source is no longer a bare string. `LISTING_ORDER: tuple[PipelineSource, ...] = (BUILT_IN, PROJECT, USER)` is the single definition of display order. It is separate from the scan order (built-in → user → project), which decides shadowing.

**D2. Effective pipelines only.** A built-in shadowed by a project copy appears under `project` and not under `built-in`, because the listing answers "what does `sq run <name>` load". README already documents shadowing.

**D3. The listing and item resume share eligibility.** The listing shows a run as resumable only on the same grounds that `--resume` uses to accept it. `pipeline/item_eligibility.py` owns every rule item resume applies before it touches git:
- `RESUMABLE_OUTCOMES = frozenset({ItemOutcome.FLAGGED, ItemOutcome.NOT_RUN})`.
- `item_decisions(record) -> frozenset[ItemDecision]`. The set is empty when the outcome is not in `RESUMABLE_OUTCOMES`. Otherwise it is `{RETRY}`, plus `ACCEPT` when `record.flag_kind is FlagKind.REVIEW_UNRESOLVED`.
- `single_each_step(definition) -> StepConfig`, which raises `ItemResumeUnsupportedError` unless the definition has exactly one `each` step. This is today's `item_resume._single_each_step` rule, moved.

`item_resume._validate` converts `ItemResumeUnsupportedError` to `_Stop(REJECTED, ...)`. `_check_record` rejects when `request.decision not in item_decisions(record)`, keeping its two existing messages (wrong outcome, accept without `review_unresolved`).

Item resume also checks state the listing cannot see ahead of time: git state, the run lock, and the item index the user types. The claim is therefore limited to this: **every item the listing counts as open passes item resume's eligibility checks for at least one decision, and an item counted as acceptable passes them for `accept`**. Run-level resume shares `first_unfinished_step_of` (D4) and `RESUMABLE_STATUSES` (D11).

**D4. One source for the resume step.** The body of `StateManager.first_unfinished_step` becomes a pure function, `first_unfinished_step_of(state: RunState, definition: PipelineDefinition) -> str | None`. The method loads state and delegates. The listing calls the function on the `RunState` it already holds.

**D5. One owner for report file names.** `batch_report.py` gains two module functions:
- `report_json_path(runs_dir, run_id, step_name) -> Path`. `BatchReport.json_path` and `item_resume._validate` both use it, replacing the inline `".report.json"` literal in `_validate`.
- `report_json_paths(runs_dir, run_id) -> list[Path]`, which globs `f"{run_id}.*{REPORT_JSON_SUFFIX}"`. It only answers "did this run write any report", which lets the listing skip loading definitions for ordinary completed runs.

**D6. Typed row data.** All three types live in `run_listing.py`. The marker text a user sees is defined only in `cli/run_views.py`, as a dict keyed by `ResumeProblem`, and no logic reads it. Rendering and inclusion dispatch on the enums.
- `ResumeKind(StrEnum)`: `STEP`, `ITEMS`.
- `ResumeProblem(StrEnum)`: `PIPELINE_UNAVAILABLE`, `NO_UNFINISHED_STEP`, `ITEM_RESUME_UNSUPPORTED`, `REPORT_UNREADABLE`.
- `ResumePoint`, a frozen dataclass: `kind`, `step_name`, `open_items` (0 for `STEP`), `acceptable_items` (0 for `STEP`).

**D7. Failure modes.** No fallback value is ever invented. Each case below is observable, either as a row marker or in the log.

| Case | Cause | Row | Default view | Log |
|---|---|---|---|---|
| Run-state file unreadable or invalid | corrupt file, old schema | skipped (existing `list_runs` behaviour) | n/a | WARNING (existing) |
| Definition not loadable (`FileNotFoundError`, `OSError`, `yaml.YAMLError`, pydantic `ValidationError`) | pipeline renamed, deleted or broken | `PIPELINE_UNAVAILABLE` marker | shown | WARNING with run-id, pipeline and exception |
| Paused or failed run with no unfinished step | definition edited after the run | `NO_UNFINISHED_STEP` marker | shown | WARNING with run-id |
| Pipeline does not have exactly one `each` step, but reports exist | multi-`each` pipeline, or pipeline edited | `ITEM_RESUME_UNSUPPORTED` marker | shown | WARNING with run-id and `each` count |
| Report unreadable (`BatchReportLoadError`, including not found at the `each` step's path) | corrupt file, wrong schema, `each` step renamed | `REPORT_UNREADABLE` marker | shown | WARNING with path |
| Run in status `running` | live run, or a process that crashed without recording a final status | no resume point | `--all` only | none |
| Concurrent writer | a run updates state or report during the listing | snapshot of the old or new file | as computed | none |

The exceptions named in the definition row are the set that `discover_pipelines` already narrows to for the same loader. Any other exception propagates: the listing fails loudly instead of misreporting.

Concurrent writes cannot be torn. Both `StateManager._write_atomic` and `batch_report._write_atomic` write a temp file and `replace` it over the target, so a reader always sees a whole file.

A `running` run is outside `RESUMABLE_STATUSES`. The listing reports exactly what the status says, and it cannot tell a live run from a crash orphan. Detecting orphans is not in scope.

**D8. `sq run --list` is removed, not deprecated.** No installed slash command or skill invokes it; only docs and its own tests do. A deprecation window would protect no known caller, so the flag, its `-l` short form, its mutual-exclusion check and its tests in `tests/cli/commands/test_run.py` are deleted. Typer rejects the old flag as an unknown option, and a CHANGELOG line names `sq pipelines list` as the replacement.

**D9. Normalising the pipeline filter.** `--pipeline` is lowercased, matching `pipeline_identity` and run-state names (#147).

**D10. `RunSummary.status` stays `str`.** It mirrors `RunState.status`, which the persisted schema stores as a string. `init_run` writes `"running"`, which is not an `ExecutionStatus` member, so narrowing the summary to `ExecutionStatus` would fail on live runs. The listing adds no status literals: it compares only through `RESUMABLE_STATUSES` and `ExecutionStatus.COMPLETED.value`. `STATUS_COLORS` is keyed by `ExecutionStatus` values, and a status not in it renders `dim`, as it does today. [#191](https://github.com/ecorkran/squadron/issues/191) covers typing `RunState.status` (a `RunStatus` enum that includes `RUNNING`), because that is a run-state schema change.

**D11. `RESUMABLE_STATUSES` becomes public.** `state.py`'s `_RESUMABLE_STATUSES` is renamed `RESUMABLE_STATUSES` and becomes a `frozenset`. `first_unfinished_step_of` and `run_listing` import it; no module imports an underscore-named constant across module boundaries.

**D12. I/O is local and bounded.** Every read in the listing is a local-disk file read or glob under the runs directory or a pipeline directory. There is no network call and no subprocess, so there is no timeout path. The I/O per call is bounded:
- one state-file read per run (existing `list_runs`);
- at most one `report_json_paths` glob per completed run;
- at most one report read per completed run that has a report file;
- at most one definition load per distinct pipeline name.

The definition and report loaders are injected (see API Contracts), so a test asserts these bounds by counting calls.

**D13. `sq runs wait`.** A pure helper in `run_listing.py`, `wait_for_run(state_manager, run_id, *, timeout, poll_interval, clock, sleep) -> WaitOutcome`, re-reads the run's state file every `poll_interval` until its status is not `running`, or until `timeout` elapses. `clock` and `sleep` are injected so tests run without real time. `WAIT_POLL_INTERVAL_SECONDS` is a module constant in `run_listing.py`, the single definition. `--timeout` has no default: without it the command waits indefinitely, which is the right behaviour for a long batch, and a caller that needs a bound passes one.

`WaitOutcome(StrEnum)` and its exit codes are defined once, in `run_listing.py`:

| Outcome | When | Exit |
|---|---|---|
| `COMPLETED` | status `completed` | 0 |
| `FAILED` | status `failed` | 1 |
| `PAUSED` | status `paused` (checkpoint or flag) | 3 |
| `TIMED_OUT` | `--timeout` elapsed while still `running` | 4 |
| `NOT_FOUND` | no state file for the run-id | 5 |
| `UNREADABLE` | state file present but unreadable or invalid on a poll | 6 |
| `UNKNOWN_STATUS` | any other status value | 7 |

Exit 2 is left to Typer's usage errors. Every non-zero outcome prints one line on stderr naming the run-id and the outcome, and every outcome except `COMPLETED` is logged at WARNING. On a terminal status the command prints the same status line `sq run --status <run-id>` prints, through the shared `run_views` renderer.

Failure modes: a crashed process leaves its run at `running` forever, and `wait` cannot tell that from a live run (D7). `--timeout` is the bound, and the help text says so. No default timeout is set because no single bound fits both a one-step review and a whole-plan batch, and any default would be a guessed magic number. An agent caller is already bounded by its own tool timeout. The run lock cannot serve as an orphan signal: it is per checkout, not per run, and only git- or cf-mutating runs take it, so a free lock with status `running` does not mean a crash. Real orphan detection needs the run's PID recorded in run state, which is a schema change tracked by [#190](https://github.com/ecorkran/squadron/issues/190). A run-state file is never torn mid-replace (`_write_atomic`), so a failed read is a real fault, not a race: the first unreadable poll ends with `UNREADABLE`, with no retry. `running` and the other status literals are compared through `ExecutionStatus` and the `running` constant that `init_run` writes, which becomes a named module constant in `state.py` (`RUNNING_STATUS`) if it is not one already; the D10 typing issue covers replacing it with an enum member.

**D14. `sq list` becomes `sq agents list`.** Every listing then reads `sq <noun> list`, and a bare `sq list` no longer implies agents. The agent lifecycle commands are moving to Amoeba and have no known users. A search of the Amoeba repo found no call to `sq list` or `sq run --list`. So, like D8, this is a clean break with no alias:
- `cli/commands/list.py` exposes an `agents_app` Typer group (`no_args_is_help=True`) with `list_agents` as its `list` subcommand; `app.py` registers the group and drops `app.command("list")`. Flags (`--state`, `--provider`) are unchanged.
- The three "Use 'sq list' to see active agents" errors in `task.py`, `shutdown.py` and `message.py` name `sq agents list`.
- `commands/sq/list.md` and `commands/agents/sq-list/SKILL.md` keep their names, so `/sq:list` and `$sq-list` still exist, and run `sq agents list $ARGUMENTS`. Renaming them would leave stale copies in installed targets for no gain.
- `docs/COMMANDS.md` and the README's agent-lifecycle paragraph are updated; a CHANGELOG line records the rename.

## Implementation Details

### API Contracts

```
sq pipelines list
sq runs list [--all] [--pipeline NAME]
sq runs wait <run-id> [--timeout SECONDS]
```

Both listing commands exit 0 on success, including empty results. `sq runs wait` exits per D13. Usage errors use Typer's standard non-zero code.

```python
# squadron/pipeline/run_listing.py
@dataclass(frozen=True)
class RunSummary:
    run_id: str
    pipeline: str
    params: dict[str, object]
    status: str                    # RunState.status (D10)
    resume: ResumePoint | None
    problem: ResumeProblem | None  # D7; set only when resume is None
    started_at: datetime

def list_run_summaries(
    state_manager: StateManager,
    *,
    pipeline: str | None,
    include_all: bool,
    load_definition: Callable[[str], PipelineDefinition] = load_pipeline,
    load_report: Callable[[Path], BatchReport] = BatchReport.load,
) -> list[RunSummary]: ...
```

`list_run_summaries` receives its `StateManager` as a parameter, so tests pass one with a `tmp_path` runs dir. Definitions and reports are read through the injected `load_definition` and `load_report`. The defaults are the same loaders `--resume` uses. Tests pass `functools.partial(load_pipeline, project_dir=..., user_dir=...)` with `tmp_path` directories, wrapped in call counters for the bounds test (D12). The D7 exception set is caught around these calls, so a wrapper changes no error handling.

### UI Specifications

`sq pipelines list`:
```
Built-in (15)
 Name          Description
 p4            Slice design with review loop
 ...
Project (2)
 Name          Description
 my-loop       ...
```
Empty groups are omitted. With no pipelines at all, the command prints `No pipelines found.`

`sq runs list`:
```
 Run ID              Pipeline        Target       Status     Resume at                       Started
 run-20261006-...    p4              slice=199    paused     review-design                   2026-10-06 14:02
 run-20261005-...    implement-plan  plan=180     completed  3 items in slices (1 accept)    2026-10-05 09:40
 run-20261004-...    p5              slice=196    failed     <pipeline unavailable>          2026-10-04 17:11

Resume a step:  sq run --resume <run-id>
Resume an item: sq run --resume <run-id> --item N --decision retry   (accept: only items counted as "accept")
```
- **Target:** the run's params as `key=value` pairs, joined by spaces.
- **Started:** `started_at`, formatted `%Y-%m-%d %H:%M`.
- **Status:** coloured with `run_views.STATUS_COLORS`, moved from `run.py`'s `_STATUS_COLORS`. `run.py`'s `_display_run_status` and result display import it from there.
- **Resume at:** `STEP` shows the step name. `ITEMS` shows `N items in <each-step>`, with ` (K accept)` appended when K > 0. A problem shows its marker text from `run_views`.
- **Empty result:** `No resumable runs.`, followed by ` Use --all to include completed runs.` when `--all` was not given.

## Integration Points

### Provides to Other Slices
- **`list_run_summaries` and `RunSummary`** for in-process callers. An out-of-process orchestrator needs `--json`, which is excluded until such a consumer exists.
- **`item_eligibility`**: the single statement of which batch items can be resumed and with which decisions.
- **`PipelineSource` and `LISTING_ORDER`**, for any later pipeline-catalogue surface.

### Consumes from Other Slices
- **From 197:** the report file layout, `ItemOutcome`, `FlagKind` and `ItemDecision`.
  - A schema change surfaces as `BatchReportLoadError`, which shows the `REPORT_UNREADABLE` marker. It is never treated as "no open items".
  - Moving the eligibility rules into `item_eligibility` changes no item-resume behaviour. 197's existing tests guard that.

## Success Criteria

### Functional Requirements
- `sq pipelines list` prints its groups in the order built-in, project, user. Names are alphabetical within each group and empty groups are omitted. A project pipeline that shadows a built-in appears only under project.
- `sq runs list` shows, newest first:
  - paused and failed runs;
  - completed batch runs with at least one open item;
  - every run with a D7 problem.
- `sq runs list` hides completed runs with no open items, and `running` runs.
- `sq runs list --all` shows every readable run. Runs with nothing to resume have an empty "Resume at" cell.
- `sq runs list --pipeline P4` matches runs of `p4`.
- For a paused run, "Resume at" equals the step `sq run --resume <id>` resumes at.
- For a completed batch run, every item counted as open is accepted by `--item <index> --decision retry`, and every item counted toward "accept" is accepted by `--decision accept`. Here "accepted" means the run passes item resume's validation; git preconditions are separate.
- `sq run --list` is no longer accepted; Typer reports it as an unknown option.
- `sq agents list` behaves as `sq list` did, with the same flags. `sq list` is no longer a command, and `/sq:list` runs `sq agents list`.
- `sq runs wait <run-id>` returns when the run leaves `running`, with the D13 exit code for its outcome; with `--timeout` it returns exit 4 if the run is still `running` when the timeout elapses.

### Technical Requirements
- `PipelineSource` replaces the bare source strings.
- `RESUMABLE_OUTCOMES`, `item_decisions`, `single_each_step`, `first_unfinished_step_of` and `report_json_path` each have a single definition, used by both the listing and the resume paths.
- No command module imports another command module.
- Unit tests for `list_run_summaries` cover:
  - a paused run and a failed run, resolved to a step;
  - a completed batch run with flagged items, mixing `review_unresolved` and other flag kinds, to check the counts;
  - a completed batch run whose items all passed;
  - a completed non-batch run (no report, no definition load);
  - a `running` run;
  - `--pipeline` filtering and ordering;
  - each `ResumeProblem` case.
- An I/O-bounds test builds 300 runs with real `StateManager` and `BatchReport.write` fixtures: 200 completed non-batch runs, 50 completed batch runs across two pipelines, 30 paused and 20 failed runs across two other pipelines. It asserts that `load_definition` is called once per distinct pipeline (4) and `load_report` once per completed batch run (50). This catches regressions in the D12 bounds without a wall-clock assertion.
- Each `ResumeProblem` test asserts both the enum value and the WARNING record (`caplog`, logger `squadron.pipeline.run_listing`).
- A parity test feeds the same report to `item_decisions` and to `item_resume._check_record` for every outcome and flag-kind combination. It asserts that a decision `_check_record` rejects never appears in the decision set `item_decisions` reports.
- `run_views` has a test that every `ResumeProblem` member has marker text.
- `wait_for_run` unit tests, with injected `clock` and `sleep` and real `StateManager` state files: a run that moves `running` → each terminal status mid-wait, one test per `WaitOutcome`; timeout while `running`; a missing run-id; an unreadable state file (`UNREADABLE` on the first poll). Each non-`COMPLETED` case asserts its WARNING record. A CLI test asserts every `WaitOutcome` maps to its exit code.
- The pipeline-grouping unit test covers all three sources plus shadowing, through the `project_dir` and `user_dir` overrides.
- CLI tests use `CliRunner` for the new commands. The `--list` tests in `tests/cli/commands/test_run.py` are deleted with the flag.
- Fixtures are real:
  - run states are written by `StateManager.init_run` and its update methods;
  - reports are written by `BatchReport.write`;
  - pipelines are real YAML files in `tmp_path` directories.
- Existing item-resume and `--resume` tests pass unchanged.
- `ruff format`, `ruff check` and `pyright` pass with zero errors.

### Integration Requirements
- Existing `sq run --status`, `--resume` and `--item` behaviour is unchanged.

### Verification Walkthrough

Run during Phase 6 (20261007). Steps 1, 2, 5, 6 and 8 used a scratch project and a scratch `HOME`, so they never touched real runs. Steps 3, 4 and 7 read the real `~/.config/squadron/runs` and changed nothing.

**Scratch setup.** Seed a runs dir with real `StateManager` and `BatchReport.write` fixtures (`tests/pipeline/run_listing_support.py`):

```bash
S=$(mktemp -d); mkdir -p $S/home $S/proj
cat > $S/seed.py <<'PY'
import sys
from pathlib import Path
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.state import StateManager
from tests.pipeline.run_listing_support import (STEP_NAMES, begin, end, pause_at, fail_at,
    completed_batch_run, write_step_pipeline, write_batch_pipeline)
pipelines = Path(sys.argv[1]) / "project-documents/user/pipelines"
write_step_pipeline(pipelines, "my-steps"); write_batch_pipeline(pipelines, "my-batch")
sm = StateManager()
p = begin(sm, "my-steps"); pause_at(sm, p, STEP_NAMES[1], done=[STEP_NAMES[0]])
f = begin(sm, "my-steps"); fail_at(sm, f, STEP_NAMES[2], done=STEP_NAMES[:2])
b = completed_batch_run(sm, "my-batch")          # 3 open items, 1 acceptable
c = begin(sm, "my-steps"); end(sm, c, ExecutionStatus.COMPLETED)
r = begin(sm, "my-steps")                        # left running
for label, run in (("paused", p), ("failed", f), ("batch", b), ("completed", c), ("running", r)):
    print(label, run)
PY
HOME=$S/home PYTHONPATH=. python $S/seed.py $S/proj    # from the squadron repo root
cd $S/proj && export HOME=$S/home
```

1. **Pipeline listing.**
   ```bash
   sq pipelines list
   ```
   Prints `Built-in (15)` with names in alphabetical order. Then:
   ```bash
   cp <squadron>/src/squadron/data/pipelines/P4.yaml project-documents/user/pipelines/P4.yaml
   sq pipelines list
   ```
   Prints `Built-in (14)` and `Project (3)` (the two seeded pipelines plus `p4`). `p4` appears only under Project. Remove the copy afterwards.

2. **Removed flags.**
   ```bash
   sq run --list; echo "exit $?"   # "No such option: --list"; exit 2
   sq run -l; echo "exit $?"       # "No such option: -l"; exit 2
   sq list; echo "exit $?"         # "No such command 'list'."; exit 2
   sq agents list; echo "exit $?"  # agent table with `sq serve` running; without it,
                                   # "Error: Daemon is not running. Start it with: sq serve", exit 1
   ```

3. **Resumable runs** (read-only, real runs dir).
   ```bash
   sq runs list
   sq run --status <paused-run-id>
   ```
   For `run-20261004-p6-8bc5e634`, "Resume at" showed `implement-1`, the status panel showed `Checkpoint: paused at 'implement-1'`, and `StateManager.first_unfinished_step` returned `implement-1`. Do not run `sq run --resume` here: it changes real runs. The Task 23 tests check that resume-step equivalence.

4. **Batch items (197)** (read-only, real runs dir). No completed batch run in the real runs dir had open items. The only batch run with one (`run-20261006-implement-plan-4b07931e`, 1 not_run item) ended `failed`, so it lists as a step resume at `slices`, as the Data Flow says. The completed batch runs with every item passed or accepted show only under `--all`, with an empty "Resume at". The scratch run covers the item case: `run-…-my-batch-…  completed  3 items in slices (1 accept)`. The Task 24 and Task 26 parity tests check that `--item … --decision retry|accept` accepts exactly the counted items. Do not run `--item` against real runs.

5. **Filters** (scratch).
   ```bash
   sq runs list                   # batch (3 items in slices (1 accept)), failed (devlog-2), paused (tasks-1)
   sq runs list --all             # also the running and completed my-steps runs, Resume at empty
   sq runs list --pipeline MY-BATCH   # only the my-batch run (case-insensitive)
   ```

6. **Failure visibility** (scratch).
   ```bash
   mv project-documents/user/pipelines/my-steps.yaml{,.bak}
   sq runs list
   mv project-documents/user/pipelines/my-steps.yaml{.bak,}
   ```
   Both `my-steps` rows show `<pipeline unavailable>`. stderr carries one line per row: `run <run-id>: pipeline my-steps unavailable: Pipeline 'my-steps' not found in any pipeline directory. …`

7. **Listing cost** (read-only, real runs dir).
   ```bash
   ls ~/.config/squadron/runs/*.json | grep -v report.json | wc -l   # 188 run-state files (+4 reports)
   time sq runs list --all                                          # 0.67 s total
   ```
   The result is within the 1 s target. Caveat: the default view showed 68 rows on this machine, 33 of them `<pipeline unavailable>`. These are runs of deleted test pipelines (`test-p4`, `test-fanout`, …) and of pipelines started from a `/tmp/*.yaml` path. Showing them is intended (D7), and pruning them is out of scope.

8. **Waiting on a run** (scratch, using the seeded run-ids).
   ```bash
   sq runs wait <running-id> --timeout 5; echo "exit $?"   # "sq runs wait: run <id> timed_out"; exit 4, after ~5 s
   sq runs wait no-such-run; echo "exit $?"                # "sq runs wait: run no-such-run not_found"; exit 5
   sq runs wait <completed-id>; echo "exit $?"             # Run Status panel; exit 0
   sq runs wait <paused-id>; echo "exit $?"                # panel + "… paused"; exit 3
   sq runs wait <failed-id>; echo "exit $?"                # panel + "… failed"; exit 1
   ```
   Every non-zero exit also logs `wait on run <id> ended: <outcome>` (WARNING) on stderr. A live pipeline started in the background (`sq run review <slice> --model <alias> &`) was not run: it needs model credentials, and the pre-finished runs above exercise the same exit path.

## Implementation Notes

### Development Approach
1. Refactor the existing code first, with no behaviour change, and commit it on its own before any new surface:
   - extract `first_unfinished_step_of`, make `RESUMABLE_STATUSES` public, and add `report_json_path` / `report_json_paths`;
   - create `item_eligibility.py` and move `item_resume` onto it;
   - add `PipelineSource` and `LISTING_ORDER` to the loader, and update `discover_pipelines`.

   The existing resume, item-resume and loader tests must pass unchanged. Add the parity test.
2. Create `cli/run_views.py` with `STATUS_COLORS`, moved from `run.py`, and `render_pipeline_listing()`. Add `pipelines.py` and register it in `app.py`. Remove `sq run --list` and its tests (D8). Move `sq list` to `sq agents list`, with its error messages, slash command and skill (D14).
3. Write `run_listing.py` with its unit tests.
4. Add `render_run_listing()` and the marker text to `run_views`. Add `runs.py` and register it.
5. Add `wait_for_run` and `WaitOutcome` to `run_listing.py` with their tests, then `sq runs wait` in `runs.py` (D13).
6. Update the docs, and add CHANGELOG lines for the `--list` removal and the `sq agents list` rename. Open GitHub issues for:
   - typing `RunState.status` (D10);
   - `sq runs list --json`, for out-of-process consumers such as Amoeba, linked from the `--json` exclusion in Technical Scope.

Effort: 3/5, covering two listings, `wait`, two command-surface breaks and the refactor. The refactor in step 1 touches four existing modules (`state`, `batch_report`, `item_resume`, `loader`) owned by 140 and 197. Existing tests and the parity test guard it.

### Special Considerations
- **Performance target:** under 1 s for `sq runs list --all` with a few hundred run-state files on local disk. The cost has three parts:
  - one JSON read per run (existing `list_runs`);
  - one glob per completed run;
  - one report read per completed batch run.

  D12 bounds the call counts, and the I/O-bounds test enforces them. Wall-clock time is measured once in walkthrough step 7 rather than asserted in a test, because timing assertions are flaky on CI runners. The target is advisory; the architecture sets no NFR for this path. There is no cache across calls, and `list_runs` parses every state file, so cost grows linearly with run history. Pruning runs is out of scope.
- **Hermetic tests:** tests must not read the developer's real runs directory or `~/.config/squadron/pipelines`. Pass `runs_dir` explicitly and inject a `load_definition` bound to `tmp_path` pipeline directories, following the conventions in `tests/_hermetic.py`.
