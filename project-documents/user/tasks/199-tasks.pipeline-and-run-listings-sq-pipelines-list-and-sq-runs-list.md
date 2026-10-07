---
docType: tasks
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
lld: user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
dependencies: [197]
projectState: >
  Slice design complete (review round 3 applied), not yet implemented. Pipeline discovery
  lives under `sq run --list`; nothing lists runs. 197 (batch reports, item resume) is
  complete. Integration branch is unset, so the target is `main`.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on **199 pipeline-and-run-listings**: adds `sq pipelines list`, `sq runs list`
  and `sq runs wait`; removes `sq run --list`; renames `sq list` to `sq agents list`.
  Fixes #185 and #187.
- Starts with a no-behaviour-change refactor (shared resume/eligibility rules, loader enum),
  then the CLI surfaces, then `run_listing.py`, then `wait`, then docs and issues.
- Tasks reference the slice design by section (D1–D14); the design is the contract.
  Section names below ("D7", "API Contracts") point into it.
- Out of scope: slash commands for the new commands, `--json`, MCP, changing
  `sq run --status`, pruning runs, typing `RunState.status`.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors) and its
  tests before its commit. Tests are hermetic: `tmp_path` runs dir and pipeline dirs, per
  `tests/_hermetic.py`; real `StateManager`, `BatchReport.write` and YAML fixtures.
- Traceability (design → tasks): D1/D2 → 10–15; D3 → 7–9; D4/D11 → 3–4; D5 → 5–6; D6/D10 →
  21; D7 → 22–24; D8 → 16–17; D9 → 25; D12 → 26; D13 → 30–33; D14 → 18–20; docs, CHANGELOG
  and follow-up issues → 34–36; Verification Walkthrough → 37.
- Effort: 3/5. Next planned slice: per `cf next` after 199 closes.

---

## Task 1 — Create the slice branch

- [ ] Confirm `cf config get git.integration_branch` is empty (target = `main`) and
      `git status` is clean
- [ ] If the branch does not exist: `git checkout -b 199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list main`;
      if it exists, `git checkout` it
  - [ ] Success: `git branch --show-current` prints the new branch name

## Task 2 — Baseline the existing tests

- [ ] Run `pytest tests/pipeline tests/cli -q` and record pass/fail counts
  - [ ] Success: failures (if any) are noted as pre-existing before any edit. Known:
        3 schema-drift failures in squadron-pr are cf issue #88, not squadron bugs

---

## Part A — Refactor with no behaviour change (Dev Approach step 1)

## Task 3 — Make `RESUMABLE_STATUSES` public and extract `first_unfinished_step_of` (D4, D11)

- [ ] In `src/squadron/pipeline/state.py`, rename `_RESUMABLE_STATUSES` to
      `RESUMABLE_STATUSES` and make it a `frozenset`; update the in-module use
- [ ] Extract the body of `StateManager.first_unfinished_step` into module function
      `first_unfinished_step_of(state: RunState, definition: PipelineDefinition) -> str | None`
  - [ ] The method loads state, then delegates to the function
  - [ ] Success: signature matches the design's D4; no other logic changes
- [ ] Make the `"running"` literal in `init_run` a named module constant `RUNNING_STATUS`
      (D13) and use it there
  - [ ] Success: `grep -n '"running"' src/squadron/pipeline/state.py` shows only the constant definition

## Task 4 — Tests for the state extraction

- [ ] In the existing state test module, add tests calling `first_unfinished_step_of`
      directly: paused run → step name; failed run → step name; all steps complete → `None`
  - [ ] Success: new tests pass; existing `first_unfinished_step` tests pass unchanged
- [ ] Commit: `refactor: extract first_unfinished_step_of and publish RESUMABLE_STATUSES`

## Task 5 — Add report path helpers to `batch_report.py` (D5)

- [ ] Add module functions `report_json_path(runs_dir, run_id, step_name) -> Path` and
      `report_json_paths(runs_dir, run_id) -> list[Path]` (glob
      `f"{run_id}.*{REPORT_JSON_SUFFIX}"`)
- [ ] Make `BatchReport.json_path` delegate to `report_json_path`
- [ ] Replace the inline `".report.json"` literal in `item_resume._validate` with
      `report_json_path`
  - [ ] Success: `grep -rn '\.report\.json' src/squadron` shows only the suffix constant definition

## Task 6 — Tests for report path helpers

- [ ] Add tests: `report_json_path` equals the path `BatchReport.write` produced;
      `report_json_paths` returns `[]` for a run with no report, one path per written
      report, and does not match another run's reports (including a run-id that is a prefix)
  - [ ] Success: tests pass; 197's batch-report and item-resume tests pass unchanged
- [ ] Commit: `refactor: centralize batch report file naming`

## Task 7 — Create `item_eligibility.py` (D3)

- [ ] Create `src/squadron/pipeline/item_eligibility.py` with `RESUMABLE_OUTCOMES`
      (`FLAGGED`, `NOT_RUN`), `item_decisions(record)`, `single_each_step(definition)` and
      `ItemResumeUnsupportedError`
  - [ ] `item_decisions` returns an empty set outside `RESUMABLE_OUTCOMES`, else `{RETRY}`
        plus `ACCEPT` when `flag_kind is FlagKind.REVIEW_UNRESOLVED`
  - [ ] `single_each_step` is today's `item_resume._single_each_step` rule, moved
  - [ ] Success: module has no I/O imports (no git, lock, executor)
- [ ] Add `tests/pipeline/test_item_eligibility.py`: `item_decisions` over every `ItemOutcome`
      × relevant `FlagKind`; `single_each_step` with zero, one and two `each` steps
  - [ ] Success: tests pass

## Task 8 — Move `item_resume` onto `item_eligibility`

- [ ] In `item_resume._validate`, catch `ItemResumeUnsupportedError` and convert it to
      `_Stop(REJECTED, ...)` with the existing message text
- [ ] In `item_resume._check_record`, reject when `request.decision not in item_decisions(record)`,
      keeping the two existing messages (wrong outcome; accept without `review_unresolved`)
- [ ] Remove the old `_single_each_step` and any now-duplicate outcome constant
  - [ ] Success: existing item-resume tests pass unchanged

## Task 9 — Item-resume parity test

- [ ] Parity test: for every outcome and flag-kind combination and each `ItemDecision`,
      build the real report/record, run `item_resume._check_record`, and assert any decision it
      rejects is absent from `item_decisions(record)`
  - [ ] Success: tests pass
- [ ] Commit: `refactor: share item eligibility rules between item resume and listings`

## Task 10 — `PipelineSource` and `LISTING_ORDER` in the loader (D1)

- [ ] In `src/squadron/pipeline/loader.py` add `PipelineSource(StrEnum)`
      (`BUILT_IN="built-in"`, `PROJECT="project"`, `USER="user"`) and
      `LISTING_ORDER: tuple[PipelineSource, ...] = (BUILT_IN, PROJECT, USER)`
- [ ] Type `PipelineInfo.source` as `PipelineSource`; update `discover_pipelines` to use the
      enum; leave scan order (built-in → user → project) unchanged
- [ ] Update every other producer/consumer of the source strings found by
      `grep -rn '"built-in"\|"project"\|"user"' src/squadron/pipeline src/squadron/cli`
  - [ ] Success: no bare source string literals remain outside the enum

## Task 11 — Loader tests

- [ ] Add tests: `discover_pipelines` tags built-in/user/project with the enum members;
      a project pipeline shadows a built-in of the same name (appears once, as `PROJECT`);
      `LISTING_ORDER` order is as specified
  - [ ] Success: new tests pass; existing loader tests pass unchanged
- [ ] Run `ruff format`, `ruff check`, `pyright`, then `pytest tests/pipeline tests/cli -q`
  - [ ] Success: zero lint/type errors; counts match Task 2 baseline plus new tests
- [ ] Commit: `refactor: type pipeline source as PipelineSource enum`

---

## Part B — `sq pipelines list`, flag removal, `sq agents list` (Dev Approach step 2)

## Task 12 — Create `cli/run_views.py` with `STATUS_COLORS`

- [ ] Create `src/squadron/cli/run_views.py`; move `_STATUS_COLORS` from `cli/commands/run.py`
      here as `STATUS_COLORS` (single definition)
- [ ] Update `run.py` (`_display_run_status` around line 562, result display around line 592)
      to import it
  - [ ] Success: `grep -rn _STATUS_COLORS src` returns nothing; `sq run --status` output unchanged

## Task 13 — `render_pipeline_listing()` (D1, D2, UI Specifications)

- [ ] In `run_views.py` add `render_pipeline_listing(pipelines)`: group by
      `PipelineSource` in `LISTING_ORDER`, keep alphabetical name order within groups, one
      Rich table per non-empty group headed `Built-in (N)` / `Project (N)` / `User (N)`; with
      no pipelines print `No pipelines found.`
  - [ ] Success: output shape matches the design's `sq pipelines list` mock

## Task 14 — `pipelines.py` command and registration

- [ ] Create `src/squadron/cli/commands/pipelines.py` with `pipelines_app`
      (`no_args_is_help=True`) and a `list` subcommand calling `discover_pipelines()` and
      `render_pipeline_listing()`
- [ ] Register with `app.add_typer(pipelines_app, name="pipelines")` in `cli/app.py`
  - [ ] Success: `sq pipelines list` runs; `sq pipelines` prints help; no command module
        imports another command module

## Task 15 — Pipeline listing tests

- [ ] Unit test for grouping/ordering/empty-group omission/`No pipelines found.` using
      `project_dir` and `user_dir` overrides with real YAML in `tmp_path`, covering all three
      sources plus a shadowed built-in
- [ ] `CliRunner` test for `sq pipelines list` (hermetic, via the same overrides or monkeypatched
      directories per `tests/_hermetic.py`), exit code 0 incl. empty result
  - [ ] Success: tests pass
- [ ] Commit: `feat: add sq pipelines list`

## Task 16 — Remove `sq run --list` (D8)

- [ ] In `cli/commands/run.py` delete the `--list`/`-l` option (line ~971), its
      mutual-exclusion check, its handler and any helper used only by it
- [ ] Delete the `--list` tests in `tests/cli/commands/test_run.py`
  - [ ] Success: `sq run --list` fails with Typer "No such option"; remaining `test_run.py`
        tests pass; no dead imports (`ruff check` clean)

## Task 17 — Test the removed flag

- [ ] Add a `CliRunner` test asserting `sq run --list` and `sq run -l` exit non-zero
- [ ] Confirm `sq run --status`, `--resume` and `--item` tests still pass unchanged
  - [ ] Success: tests pass
- [ ] Commit: `refactor: remove sq run --list in favor of sq pipelines list`

## Task 18 — `sq agents list` (D14)

- [ ] In `cli/commands/list.py` expose `agents_app` (`no_args_is_help=True`) with
      `list_agents` as its `list` subcommand; flags `--state`, `--provider` unchanged
- [ ] In `cli/app.py` register `add_typer(agents_app, name="agents")` and remove
      `app.command("list")`
  - [ ] Success: no command module imports another; `agents` name does not collide with an
        existing group (check `app.py`)

## Task 19 — Update `sq list` references (D14)

- [ ] Change the three "Use 'sq list' to see active agents" messages in `task.py`,
      `shutdown.py`, `message.py` to name `sq agents list`; update any tests asserting that text
- [ ] Change `commands/sq/list.md` and `commands/agents/sq-list/SKILL.md` to run
      `sq agents list $ARGUMENTS`, keeping their file names
  - [ ] Success: `grep -rn "sq list" src commands tests` returns only intentional historical mentions (none expected)

## Task 20 — Tests for `sq agents list`

- [ ] Move/adapt existing `sq list` CLI tests to `sq agents list`; add a test that `sq list`
      exits non-zero (no such command) and that the error messages in Task 19 name
      `sq agents list`; `--state` and `--provider` still work
- [ ] Test that `commands/sq/list.md` and `commands/agents/sq-list/SKILL.md` contain
      `sq agents list $ARGUMENTS` and no bare `sq list`
  - [ ] Success: tests pass
- [ ] Run `ruff format`, `ruff check`, `pyright`, `pytest tests/cli -q`
- [ ] Commit: `refactor: move sq list to sq agents list`

---

## Part C — `run_listing.py` (Dev Approach step 3)

## Task 21 — Row types and their tests (D6, D10)

- [ ] Create `src/squadron/pipeline/run_listing.py` with `ResumeKind(StrEnum)`
      (`STEP`, `ITEMS`), `ResumeProblem(StrEnum)` (`PIPELINE_UNAVAILABLE`,
      `NO_UNFINISHED_STEP`, `ITEM_RESUME_UNSUPPORTED`, `REPORT_UNREADABLE`), frozen
      dataclass `ResumePoint` (`kind`, `step_name`, `open_items`, `acceptable_items`) and
      frozen dataclass `RunSummary` per API Contracts (`status` stays `str`)
  - [ ] Success: signatures match the design; module has no rendering code
- [ ] Add `tests/pipeline/test_run_listing.py` (hermetic fixtures reused by Tasks 22–26) with
      tests that both dataclasses reject attribute assignment and the enums have exactly the
      members above
  - [ ] Success: tests pass

## Task 22 — Cached definition loading and its tests (D7, D12)

- [ ] In `run_listing.py` add a private per-call loader around the injected `load_definition`:
      one attempt per pipeline name; a failed load is remembered so it is not retried; catches
      exactly `FileNotFoundError`, `OSError`, `yaml.YAMLError` and pydantic `ValidationError`;
      any other exception propagates
- [ ] Tests, with a call-counting `load_definition` and real YAML in `tmp_path`: two runs of
      one pipeline load once; a missing file, a malformed-YAML file and a schema-invalid file
      each yield "unavailable" and are attempted once; a `RuntimeError` from the loader
      propagates
  - [ ] Success: tests pass; no module-level cache (the dict is local to one call)

## Task 23 — Paused/failed resume resolution and its tests (Data Flow)

- [ ] Add a private helper (≤ ~50 lines) resolving a `paused`/`failed` run: load definition
      (failure → `PIPELINE_UNAVAILABLE`), `first_unfinished_step_of` (`None` →
      `NO_UNFINISHED_STEP`), else `ResumePoint(STEP, step_name)`
- [ ] Log each problem at WARNING on logger `squadron.pipeline.run_listing` with the D7 context
      (run-id, pipeline, exception / run-id)
- [ ] Tests: paused run and failed run each resolve to the step `first_unfinished_step` returns;
      `PIPELINE_UNAVAILABLE` and `NO_UNFINISHED_STEP` each assert the enum value and the WARNING
      record via `caplog`
  - [ ] Success: tests pass; status comparisons use only `RESUMABLE_STATUSES`

## Task 24 — Completed-run resume resolution and its tests (Data Flow)

- [ ] Add private helpers (each ≤ ~50 lines) for a `completed` run: `report_json_paths` empty →
      no resume point, definition never loaded; else `single_each_step`
      (`ItemResumeUnsupportedError` → `ITEM_RESUME_UNSUPPORTED`, logging the `each` count);
      `load_report(report_json_path(...))` (`BatchReportLoadError` → `REPORT_UNREADABLE`,
      logging the path); count `open_items` / `acceptable_items` from `item_decisions`;
      `open_items > 0` → `ResumePoint(ITEMS, each.name, open, acceptable)`, else none
- [ ] Add the dispatch for any other status (`running`) → no resume point, no problem; compare
      only via `ExecutionStatus.COMPLETED.value` and `RUNNING_STATUS`; no new status literals
- [ ] Tests (real `BatchReport.write` reports): mixed flag kinds (`review_unresolved` and
      others) check both counts; all items passed → no resume point; completed non-batch run →
      no resume point and `load_definition` never called; `running` run → none;
      `ITEM_RESUME_UNSUPPORTED` (pipeline edited to two `each` steps); `REPORT_UNREADABLE` for
      a corrupt report and for a renamed `each` step (file not found); `PIPELINE_UNAVAILABLE` for
      a completed run with reports. Each problem case asserts enum value and WARNING record
  - [ ] Success: tests pass
- [ ] Commit: `feat: resolve resume points for runs`

## Task 25 — `list_run_summaries()` and its tests

- [ ] Implement `list_run_summaries(state_manager, *, pipeline, include_all, load_definition=load_pipeline, load_report=BatchReport.load)`:
      lowercase the `pipeline` filter (D9), call `state_manager.list_runs(pipeline=)`, build one
      `RunSummary` per run via Tasks 22–24, and unless `include_all` keep only rows with a
      resume point or a problem
- [ ] Tests: `--pipeline P4` matches runs of `p4`; newest-first order preserved; default view
      hides completed-no-open-items and `running` runs and keeps problem rows; `include_all`
      returns every readable run with an empty resume cell for nothing-to-resume rows
  - [ ] Success: tests pass

## Task 26 — I/O-bounds and listing/resume parity tests (D12)

- [ ] I/O-bounds test: 300 runs (200 completed non-batch, 50 completed batch across two
      pipelines, 30 paused and 20 failed across two other pipelines) with call-counting
      wrappers: `load_definition` called 4 times, `load_report` 50 times
- [ ] Listing/resume parity test (Success Criteria): for a completed batch run, every item
      counted open passes `item_resume._check_record` with `retry`, and every item counted
      acceptable passes with `accept`
  - [ ] Success: tests pass
- [ ] Run `ruff format`, `ruff check`, `pyright`, `pytest tests/pipeline -q`
- [ ] Commit: `feat: add run_listing layer for resumable runs`

---

## Part D — `sq runs list` (Dev Approach step 4)

## Task 27 — Marker text and `render_run_listing()`

- [ ] In `run_views.py` add a dict of marker text keyed by `ResumeProblem` (the only place
      marker text is defined) with exactly these values: `PIPELINE_UNAVAILABLE` →
      `<pipeline unavailable>`, `NO_UNFINISHED_STEP` → `<no unfinished step>`,
      `ITEM_RESUME_UNSUPPORTED` → `<item resume unsupported>`, `REPORT_UNREADABLE` →
      `<report unreadable>`
- [ ] Add `render_run_listing(summaries, *, include_all)` per UI Specifications: columns Run ID,
      Pipeline, Target (`key=value` joined by spaces), Status (coloured via `STATUS_COLORS`,
      unknown status `dim`), Resume at, Started (`%Y-%m-%d %H:%M`)
  - [ ] `STEP` → step name; `ITEMS` → `N items in <each-step>` plus ` (K accept)` when K > 0;
        problem → marker text; none → empty cell
  - [ ] Footer prints the two resume hints; empty result prints `No resumable runs.` plus
        ` Use --all to include completed runs.` when `--all` was not given
  - [ ] Success: dispatch is on the enums, no string comparison of marker text

## Task 28 — `runs.py` command and registration

- [ ] Create `src/squadron/cli/commands/runs.py` with `runs_app` (`no_args_is_help=True`) and
      `list` subcommand: `--all`, `--pipeline NAME`; builds a `StateManager` the same way
      `run.py --status` does, calls `list_run_summaries`, then `render_run_listing`
- [ ] Register with `add_typer(runs_app, name="runs")` in `cli/app.py`
  - [ ] Success: exits 0 including on empty results

## Task 29 — Tests: run rendering and command

- [ ] Test every `ResumeProblem` member has marker text in `run_views`
- [ ] Rendering tests: each Resume-at form, Target formatting, empty-result messages with and
      without `--all`
- [ ] `CliRunner` tests for `sq runs list`, `--all`, `--pipeline`, hermetic runs dir
  - [ ] Success: tests pass
- [ ] Run `ruff format`, `ruff check`, `pyright`, `pytest tests/cli tests/pipeline -q`
- [ ] Commit: `feat: add sq runs list`

---

## Part E — `sq runs wait` (Dev Approach step 5)

## Task 30 — `WaitOutcome` and `wait_for_run` (D13)

- [ ] In `run_listing.py` add `WAIT_POLL_INTERVAL_SECONDS`, `WaitOutcome(StrEnum)`
      (`COMPLETED`, `FAILED`, `PAUSED`, `TIMED_OUT`, `NOT_FOUND`, `UNREADABLE`,
      `UNKNOWN_STATUS`) and the single definition of outcome → exit code (0, 1, 3, 4, 5, 6, 7)
- [ ] Implement `wait_for_run(state_manager, run_id, *, timeout, poll_interval, clock, sleep) -> WaitOutcome`:
      re-read state each poll; return when status is not `RUNNING_STATUS`; `timeout=None` waits
      indefinitely; first unreadable poll → `UNREADABLE` with no retry; log every non-`COMPLETED`
      outcome at WARNING
  - [ ] Success: exit code 2 is not used; no default timeout is set

## Task 31 — Tests for `wait_for_run`

- [ ] With injected fake `clock`/`sleep` and real state files, one test per `WaitOutcome`:
      run moves `running` → each terminal status mid-wait; timeout while `running`; missing
      run-id; unreadable state file on the first poll; unknown status value
  - [ ] Success: each non-`COMPLETED` case asserts its WARNING record; no real sleeping
- [ ] Commit: `feat: add wait_for_run helper`

## Task 32 — `sq runs wait` command

- [ ] In `runs.py` add `wait` subcommand: `<run-id>` argument, `--timeout SECONDS`; help text
      states that a crashed run stays `running` and `--timeout` is the bound
- [ ] On a terminal status print the status line through the shared `run_views` renderer
      (same as `sq run --status <run-id>`); for every non-zero outcome print one stderr line
      naming the run-id and outcome; exit with the D13 code
  - [ ] Success: status-line rendering is shared with `run.py`, not duplicated

## Task 33 — CLI tests for `sq runs wait`

- [ ] `CliRunner` test asserting every `WaitOutcome` maps to its exit code and prints the
      stderr line (inject poll/clock via the helper's parameters or a monkeypatched
      `wait_for_run` returning each outcome)
- [ ] One end-to-end test: pre-completed run prints the status line and exits 0
  - [ ] Success: tests pass
- [ ] Run `ruff format`, `ruff check`, `pyright`, `pytest tests -q -x`
- [ ] Commit: `feat: add sq runs wait`

---

## Part F — Docs, CHANGELOG, issues (Dev Approach step 6)

## Task 34 — Update docs

- [ ] Replace `sq run --list` references with `sq pipelines list` in `README.md`,
      `docs/PIPELINES.md`, `docs/QUICKSTART.md` (find via `grep -rn "run --list\|sq run -l" .`
      excluding `project-documents/archive`)
- [ ] Document `sq pipelines list`, `sq runs list`, `sq runs wait` (with exit codes) in the
      appropriate docs; update `docs/COMMANDS.md` and the README agent-lifecycle paragraph for
      `sq agents list`
  - [ ] Success: grep finds no remaining `sq run --list` or bare `sq list` in user-facing docs

## Task 35 — CHANGELOG

- [ ] Add short user-facing bullets under the unreleased section: new `sq pipelines list`,
      `sq runs list`, `sq runs wait`; removed `sq run --list` (use `sq pipelines list`);
      renamed `sq list` to `sq agents list`; mention #185 and #187
  - [ ] Success: bullets are user-facing only; technical detail goes to DEVLOG
- [ ] Commit: `docs: document run and pipeline listings; update changelog`

## Task 36 — Open follow-up GitHub issues (feedback: issues over Future Work)

- [ ] Open three issues with `gh issue create`: (1) type `RunState.status` as a `RunStatus`
      enum including `RUNNING` (D10); (2) record the run's PID in run state so `sq runs list`
      and `sq runs wait` can detect crashed runs (D13); (3) `sq runs list --json` for
      out-of-process consumers such as Amoeba
- [ ] Link the issue numbers from the slice design where each is deferred (D10, D13, the
      `--json` exclusion in Technical Scope)
  - [ ] Success: three issue numbers recorded in the slice design

---

## Task 37 — Verification walkthrough and final validation

- [ ] Walkthrough steps 1, 2, 5 and 6 (listing, removed flags, filters, failure marker): run
      against a scratch project directory and a scratch runs dir seeded with real
      `StateManager` / `BatchReport.write` fixtures (reuse the Task 21 fixtures)
- [ ] Walkthrough steps 3 and 4 are read-only: run `sq runs list` and `sq run --status <run-id>`
      against `~/.config/squadron/runs` and compare "Resume at" to the status output. Do NOT run
      `sq run --resume` or `--item` there: both mutate real runs. Resume-step and item
      equivalence is asserted by the Task 23, 24 and 26 tests
- [ ] Walkthrough step 7: record the run count (`ls ~/.config/squadron/runs/*.json | wc -l`)
      and the elapsed time of `sq runs list --all` against the real runs dir (read-only)
- [ ] Walkthrough step 8: the `wait` timeout (4) and not-found (5) cases run against the scratch
      runs dir with a hand-seeded `running` run. The live-pipeline case (exit 0/3) needs model
      credentials; if unavailable, record it as skipped with the reason
  - [ ] Success: each executed step behaves as the design states; deviations are logged as
        issues, not silently accepted
- [ ] Hermeticity check: run `HOME=$(mktemp -d) pytest tests -q`; no test may touch the real
      `~/.config/squadron`
  - [ ] Success: suite passes with an empty HOME
- [ ] Full gate: `ruff format`, `ruff check`, `pyright` (zero errors), `pytest tests -q`
  - [ ] Success: zero lint/type errors; existing item-resume and `--resume` tests pass unchanged
- [ ] Mark any dropped/skipped items above `[x]` with a note before closing (visualizer reads checkbox state)
- [ ] Commit any remaining changes: `chore: finalize slice 199 verification`
  - [ ] Success: working tree clean on the slice branch; code review (Phase 6 gate) and merge
        happen later in Phase 7, not here
