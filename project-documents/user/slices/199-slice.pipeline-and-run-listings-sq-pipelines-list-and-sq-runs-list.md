---
docType: slice-design
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
parent: project-documents/user/architecture/180-slices.pipeline-intelligence.md
dependencies: [197]
interfaces: []
dateCreated: 20261006
dateUpdated: 20261006
status: not_started
---

# Slice Design: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list

## Overview

Two listing commands as noun groups: `sq pipelines list` (what can I run?) and `sq runs list` (what can I resume?). Fixes [#185](https://github.com/ecorkran/squadron/issues/185) and [#187](https://github.com/ecorkran/squadron/issues/187).

Today pipeline discovery hides under `sq run --list` and mixes sources in one name-sorted table. Nothing lists runs: `sq run --status latest` shows one run, so resuming an older paused run, or an item of a finished batch (slice 197), means already knowing its run-id.

## Value

- **Users:** see their own pipelines apart from the built-ins, and find any resumable run with the exact `sq run --resume` invocation it needs.
- **Batch workflows (197):** a finished batch run with flagged items shows up as resumable, with its open-item count. Without this, the only way to find it is the run output or the runs directory.
- **Agents:** the slash command and skill can list run-ids instead of guessing or scraping `~/.config/squadron/runs`.

## Technical Scope

**Included**
- `sq pipelines list`: effective pipelines grouped by source (built-in, project, user), alphabetical within each group.
- `sq runs list`: one row per run, newest first. Shows resumable runs by default. `--all` includes every run and `--pipeline NAME` filters by pipeline.
- A pure run-listing layer (`squadron/pipeline/run_listing.py`) that builds row data from `StateManager` and batch reports. Rendering stays in the CLI.
- `sq run --list` stays as a deprecated alias for `sq pipelines list` and prints a deprecation notice on stderr.
- Slash commands `/sq:pipelines` and `/sq:runs`, agent skills `sq-pipelines` and `sq-runs`, and drift-test entries for both.
- Doc references to `sq run --list` updated (README, docs/PIPELINES.md, docs/QUICKSTART.md, `commands/sq/run.md`, `commands/agents/sq-run/SKILL.md`).

**Excluded**
- Removing `sq run --list`. That is tracked by a GitHub issue opened during this slice.
- Changes to `sq run --status`, which keeps its current behaviour.
- Deleting or pruning runs, and `--json` output. No consumer needs JSON yet.
- An MCP surface. Squadron has no MCP server (`src/squadron/server` is the agent daemon, with `agents` and `health` routes only), so parity means CLI, slash command and agent skill.

## Dependencies

### Prerequisites
- **197 (complete):** batch reports (`BatchReport`, `ItemOutcome`, `<run_id>.<step>.report.json` beside the run state) and item resume (`sq run --resume <id> --item N --decision ...`).

### Interfaces Required
- `discover_pipelines()` and `PipelineInfo` in `squadron/pipeline/loader.py`.
- `StateManager.list_runs(pipeline=, status=)`, `StateManager.runs_dir` and `RunState` in `squadron/pipeline/state.py`.
- `StateManager.first_unfinished_step` logic, which decides where `--resume` restarts.
- `BatchReport.load`, `BatchReport.json_path`, `ItemOutcome` in `squadron/pipeline/batch_report.py`.
- `ExecutionStatus` in `squadron/pipeline/executor.py`.

## Architecture

### Component Structure

```
cli/app.py
 ├─ add_typer(pipelines_app, "pipelines")   cli/commands/pipelines.py  (new)
 ├─ add_typer(runs_app, "runs")             cli/commands/runs.py       (new)
 └─ command("run")                          cli/commands/run.py
       --list → warn on stderr → pipelines.render_pipeline_listing()

pipeline/loader.py        PipelineSource enum, LISTING_ORDER; PipelineInfo.source typed
pipeline/run_listing.py   (new) RunSummary, ResumePoint, list_run_summaries()
pipeline/state.py         first_unfinished_step logic extracted to a pure function
pipeline/batch_report.py  RESUMABLE_OUTCOMES, report_json_paths()
pipeline/item_resume.py   uses RESUMABLE_OUTCOMES and the shared path helper
```

### Data Flow

**`sq pipelines list`:** `discover_pipelines()` returns the effective set, where a later source shadows an earlier one by name, so a pipeline is listed once, under the source `sq run <name>` would load. The CLI groups the set by `PipelineSource` in `LISTING_ORDER`, keeps the name sort within each group, and renders one table per non-empty group.

**`sq runs list`:**
1. `list_run_summaries(state_mgr, pipeline=..., include_all=...)` calls `state_mgr.list_runs(pipeline=)`, which is already sorted newest first.
2. It builds the resume point for each run:
   - status `paused` or `failed`: load the pipeline definition and take the first unfinished step (the same function `--resume` uses) → `ResumePoint.step(name)`.
   - status `completed`: load each batch report for the run (`report_json_paths(runs_dir, run_id)`) and count records whose outcome is in `RESUMABLE_OUTCOMES` → `ResumePoint.items(count, step_name)` when the count is above 0, else none.
3. It keeps a run when the run has a resume point, or when `include_all` is set.
4. The CLI renders the `RunSummary` rows as one table and prints a hint line with the resume command shape.

### State Management
Read-only. The slice adds no new state and does not write run state or reports.

## Technical Decisions

### Technology Choices
- **Typer noun groups** (`pipelines_app`, `runs_app`, `no_args_is_help=True`), following `pools_app` and `models_app`. `sq list` already lists agents. A `list` subcommand under `sq run` would collide with the pipeline-name positional.
- **Rich tables**, as in the current `--list` and `sq pools`.

### Patterns and Conventions

**D1. `PipelineSource(StrEnum)`** with `BUILT_IN = "built-in"`, `PROJECT = "project"` and `USER = "user"` in `loader.py`. `discover_pipelines` and `PipelineInfo.source` use it, so the values are no longer bare strings. `LISTING_ORDER: tuple[PipelineSource, ...] = (BUILT_IN, PROJECT, USER)` is the single display-order definition. It is separate from the scan order (built-in → user → project), which decides shadowing.

**D2. Effective pipelines only.** A built-in shadowed by a project copy appears under `project` and not under `built-in`. The listing answers "what does `sq run <name>` load". README already documents shadowing.

**D3. Resumable means `--resume` would do something.** That is either a run-level resume (status in `_RESUMABLE_STATUSES`: paused, failed) or an item resume (completed run with batch-report records in `RESUMABLE_OUTCOMES`). `RESUMABLE_OUTCOMES = frozenset({ItemOutcome.FLAGGED, ItemOutcome.NOT_RUN})` moves into `batch_report.py`, and `item_resume._check_record` uses it, so the listing and the resume path cannot disagree.

**D4. One source for the resume step.** The body of `StateManager.first_unfinished_step` becomes a pure function `first_unfinished_step_of(state: RunState, definition: PipelineDefinition) -> str | None`. The method loads state and delegates. The listing calls the pure function on the `RunState` it already holds, so it does not load each run twice.

**D5. One owner for report file names.** `report_json_paths(runs_dir, run_id) -> list[Path]` sits beside `BatchReport.json_path` in `batch_report.py`. It globs `f"{run_id}.*{REPORT_JSON_SUFFIX}"` and returns the paths sorted. `item_resume._validate` builds its path through `BatchReport.json_path` (or a shared static form of it) instead of the inline `".report.json"` literal.

**D6. `ResumePoint` is a small frozen dataclass:** `kind: ResumeKind` (`STEP` | `ITEMS`), `step_name: str`, `open_items: int` (0 for `STEP`). A run without a resume point holds `None`. Rendering dispatches on `ResumeKind`, not on strings.

**D7. Failure modes are visible in the row.** No fallback value is invented. Every case logs a WARNING and puts an explicit marker in the "Resume at" column:

| Failure | Cause | Row shows | Log |
|---|---|---|---|
| Unreadable or invalid run-state file | corrupt or old schema | (row skipped, as `list_runs` already does) | WARNING (existing) |
| Pipeline definition not found or invalid for a paused or failed run | pipeline renamed or deleted | `<pipeline unavailable>` | WARNING with run-id and pipeline |
| Batch report unreadable (`BatchReportLoadError`) | corrupt or wrong schema | `<report unreadable>` | WARNING with path |

A row with a marker counts as resumable for a paused or failed run, because its status says so. For a completed run it is shown only under `--all`.

**D8. Deprecated alias.** `sq run --list` calls the same `render_pipeline_listing()` used by `sq pipelines list`, after printing `Deprecated: use 'sq pipelines list'.` to stderr. The existing mutual-exclusion check for `--list` stays.

**D9. Pipeline filter normalisation.** `--pipeline` is lowercased, matching `pipeline_identity` and run-state names (#147).

## Implementation Details

### API Contracts

```
sq pipelines list
sq runs list [--all] [--pipeline NAME]
sq run --list            # deprecated alias of `sq pipelines list`
```

Exit codes: 0 for success, including empty results. Usage errors use Typer's standard non-zero code.

```python
# squadron/pipeline/run_listing.py
@dataclass(frozen=True)
class RunSummary:
    run_id: str
    pipeline: str
    params: dict[str, object]
    status: str                 # ExecutionStatus value
    resume: ResumePoint | None
    resume_problem: str | None  # D7 marker text, else None
    started_at: datetime

def list_run_summaries(
    state_manager: StateManager, *, pipeline: str | None, include_all: bool,
) -> list[RunSummary]: ...
```

`list_run_summaries` receives its `StateManager` as a parameter, so tests pass one with a `tmp_path` runs dir.

### UI Specifications

`sq pipelines list`:
```
Built-in (14)
 Name          Description
 p4            Slice design with review loop
 ...
Project (2)
 Name          Description
 my-loop       ...
```
Empty groups are omitted. If there are no pipelines at all, the command prints `No pipelines found.`

`sq runs list`:
```
 Run ID              Pipeline     Target            Status     Resume at                Started
 run-20261006-...    p4           slice=199         paused     review-design            2026-10-06 14:02
 run-20261005-...    implement-plan plan=180        completed  3 items (implement-each) 2026-10-05 09:40
 run-20261004-...    p5           slice=196         failed     <pipeline unavailable>   2026-10-04 17:11

Resume: sq run --resume <run-id>   Item: sq run --resume <run-id> --item N --decision retry|accept
```
- **Target:** params as `key=value` pairs joined by spaces.
- **Started:** `started_at` formatted as `%Y-%m-%d %H:%M`.
- **Status:** coloured with the existing `_STATUS_COLORS` map, moved from `run.py` to a shared location the new module imports.
- **Empty result:** `No resumable runs.`, plus ` Use --all to include completed runs.` when `--all` was not given.

### Slash command and skill surfaces
- `commands/sq/pipelines.md` and `commands/sq/runs.md` follow the `list.md` pattern: run `sq pipelines list $ARGUMENTS` or `sq runs list $ARGUMENTS`, show the results, and document the flags under a `## Subcommand: list` section.
- `commands/agents/sq-pipelines/SKILL.md` and `commands/agents/sq-runs/SKILL.md` use the same content in skill form.
- Both installers enumerate these directories by glob (`skills/targets.py`), so no registry edit is needed.
- `tests/cli/test_command_surface.py` gains entries `(("pipelines", "list"), "pipelines.md", "## Subcommand: list")` and `(("runs", "list"), "runs.md", "## Subcommand: list")`.

## Integration Points

### Provides to Other Slices
- `list_run_summaries` / `RunSummary`, which an orchestrator such as Amoeba can use to find runs needing a decision without parsing CLI output.
- `PipelineSource` and `LISTING_ORDER` for any later pipeline-catalogue surface.
- `RESUMABLE_OUTCOMES` and `report_json_paths`, which remove duplication between the listing and item resume.

### Consumes from Other Slices
- From 197: the report file layout and `ItemOutcome`. A schema change there surfaces as `BatchReportLoadError`, which D7 makes visible. It is never silently treated as "no open items".

## Success Criteria

### Functional Requirements
- `sq pipelines list` prints groups in the order built-in, project, user. Names are alphabetical within each group, empty groups are omitted, and a project pipeline that shadows a built-in appears only under project.
- `sq runs list` shows paused and failed runs, plus completed runs with flagged or not-run batch items, newest first. Completed runs with no open items are hidden.
- `sq runs list --all` also shows completed runs with nothing to resume, with an empty "Resume at" cell.
- `sq runs list --pipeline P4` matches runs of `p4`.
- For a paused run, "Resume at" equals the step `sq run --resume <id>` actually resumes at, because both use the same function.
- A completed batch run shows `N items (<each-step>)`, where N counts the `flagged` plus `not_run` records in its report.
- Every D7 failure case shows its marker and logs a WARNING. None crashes the listing.
- `sq run --list` prints the deprecation notice on stderr and the same output as `sq pipelines list` on stdout.

### Technical Requirements
- `PipelineSource` replaces the bare source strings. `RESUMABLE_OUTCOMES`, `first_unfinished_step_of` and `report_json_paths` each have a single definition and are used by both the listing and resume paths.
- Unit tests for `list_run_summaries` cover: a paused run (step), a failed run (step), a completed batch run with flagged items, a completed batch run with all items passed, a completed non-batch run, a missing pipeline definition, an unreadable report, `--pipeline` filtering, and ordering.
- The unit test for pipeline grouping covers all three sources plus shadowing, using the `project_dir` and `user_dir` overrides.
- CLI tests use `CliRunner` for both commands and the deprecated alias, including the stderr notice.
- The run-state fixtures in the tests are real `RunState` JSON written by `StateManager.init_run` and its update methods. The report fixtures are written by `BatchReport.write`, not hand-built JSON.
- The drift test covers both new command files. `ruff format`, `ruff check` and `pyright` pass with zero errors.

### Integration Requirements
- After `sq install-commands`, `/sq:pipelines` and `/sq:runs` are installed, and the `sq-pipelines` and `sq-runs` skills are installed for skill-runtime targets.
- Existing `sq run --status`, `--resume` and `--item` behaviour is unchanged, and the existing tests pass.

### Verification Walkthrough

These commands do not exist yet. The walkthrough is the draft demo for Phase 6.

1. **Pipeline listing**
   ```bash
   sq pipelines list
   ```
   Expect a "Built-in (N)" table with names in alphabetical order. Then add a project pipeline and list again:
   ```bash
   mkdir -p project-documents/user/pipelines
   cp src/squadron/data/pipelines/P4.yaml project-documents/user/pipelines/P4.yaml
   sq pipelines list
   ```
   Expect a "Project (1)" group containing `p4`, and no `p4` under Built-in. Remove the copy afterwards.

2. **Deprecated alias**
   ```bash
   sq run --list 2>/dev/null   # same tables as step 1
   sq run --list >/dev/null    # stderr: Deprecated: use 'sq pipelines list'.
   ```

3. **Resumable runs.** Use the existing runs in `~/.config/squadron/runs`, or create one by starting a pipeline that hits a checkpoint and lets it pause.
   ```bash
   sq runs list
   ```
   Expect paused and failed runs, newest first, each with a "Resume at" step. Copy a paused run-id, then run:
   ```bash
   sq run --status <run-id>
   sq run --resume <run-id>
   ```
   Confirm that the step it resumes at matches the "Resume at" column.

4. **Batch items (197).** If a completed `implement-plan` batch run with flagged items exists, `sq runs list` shows it as `N items (<each-step>)`. Then run:
   ```bash
   sq run --resume <run-id> --item <index> --decision accept
   sq runs list
   ```
   The count drops by one, and the run disappears from the list when the count reaches zero.

5. **Filters**
   ```bash
   sq runs list --all             # completed runs appear, Resume at empty
   sq runs list --pipeline P4     # only p4 runs
   ```

6. **Failure visibility.** Rename the pipeline YAML of a paused project-pipeline run, then run `sq runs list`. Expect `<pipeline unavailable>` in its row and a WARNING on stderr. Restore the file afterwards.

7. **Slash surfaces.** After `sq install-commands`, run `/sq:runs` in Claude Code. The table should match `sq runs list`.

## Implementation Notes

### Development Approach
1. `PipelineSource` and `LISTING_ORDER` in the loader; update `discover_pipelines` and its existing tests.
2. `pipelines.py` with `render_pipeline_listing()`; register it in `app.py`; point `sq run --list` at it with the deprecation notice.
3. Extract `first_unfinished_step_of`, `RESUMABLE_OUTCOMES` and `report_json_paths`; move `item_resume` onto them. Existing resume tests must pass unchanged.
4. Write `run_listing.py` with its unit tests.
5. Add `runs.py` and register it; move `_STATUS_COLORS` to the shared location.
6. Add the slash commands, skills and drift-test entries.
7. Update the docs, and open the GitHub issue for removing `sq run --list`.

Effort: 2/5.

### Special Considerations
- `list_runs` reads every state file in the runs directory, and this slice adds one pipeline load per paused or failed run plus one report read per completed run. That is acceptable at current run counts. The slice adds no cache.
- Tests must not read the developer's real runs directory or `~/.config/squadron/pipelines`. Pass `runs_dir`, `user_dir` and `project_dir` explicitly, in line with the hermetic-test conventions in `tests/_hermetic.py`.
