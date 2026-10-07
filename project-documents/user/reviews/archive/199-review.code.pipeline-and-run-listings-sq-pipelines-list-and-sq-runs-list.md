---
docType: review
layer: project
reviewType: code
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: d30b6f575ba0c25408ee995a7287ff108f0e6e3c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
durationSeconds: 37.3
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Table column header text is used as logic"
    location: "src/squadron/cli/run_views.py:render_run_listing"
  - id: F002
    severity: concern
    category: security
    summary: "Unescaped Rich markup in `render_run_status`"
    location: "src/squadron/cli/run_views.py:render_run_status"
  - id: F003
    severity: concern
    category: design
    summary: "`run_listing.py` mixes listing and waiting"
    location: "src/squadron/pipeline/run_listing.py:213-287"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`wait` warns twice for each non-success outcome"
    location: "src/squadron/pipeline/run_listing.py:wait_for_run"
  - id: F005
    severity: note
    category: error-handling
    summary: "`wait` reloads state after polling"
    location: "src/squadron/cli/commands/runs.py:wait"
  - id: F006
    severity: note
    category: correctness
    summary: "Report glob can match run ids that contain dots"
    location: "src/squadron/pipeline/batch_report.py:report_json_paths"
  - id: F007
    severity: note
    category: design
    summary: "Hard breaking removals are intentional and consistent"
    location: "src/squadron/cli/app.py"
  - id: F008
    severity: pass
    category: testing
    summary: "Eligibility rules are shared, and tests keep listing and resume in step"
    location: "src/squadron/pipeline/item_eligibility.py"
---

# Review: code — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Table column header text is used as logic

`_UNFOLDED_COLUMNS = frozenset({"Run ID", "Status", "Resume at"})` decides whether a column gets `no_wrap`/`min_width`. The decision is made by comparing the user-visible header string. `CLAUDE.md` says "NEVER use user-accessible labels as logical structure." Renaming a header silently changes wrapping, and the headers are written twice (the tuple and the frozenset). Define the columns once, for example as a small tuple of `(header, never_fold)` entries, and drive both `add_column` and the width computation from it.

### [CONCERN] Unescaped Rich markup in `render_run_status`

The panel interpolates `state.params`, `state.pipeline`, `state.checkpoint.step` and `state.checkpoint.reason` straight into markup strings. Bracketed text in a param value or a pause reason, such as `[/x]`, can raise `MarkupError` or restyle the output. `render_run_listing` correctly uses `escape()`. The code was moved unchanged from `run.py`, but it now also serves `sq runs wait`, so the exposure is wider. Escape these values the same way the listing does.

### [CONCERN] `run_listing.py` mixes listing and waiting

The module has two reasons to change. One is resume-point resolution, which reads definitions and reports. The other is polling a state file and mapping outcomes to exit codes. The module docstring describes only the listing, and the wait code shares nothing with it except the logger. A separate `run_wait.py` would follow SRP and keep the file well under the ~300-line guidance. This is not blocking.

### [CONCERN] `wait` warns twice for each non-success outcome

`wait_for_run` logs a WARNING for every outcome other than COMPLETED, including normal PAUSED and FAILED results. The CLI then also echoes `sq runs wait: run … <outcome>` to stderr. Callers see the same signal twice, and a paused run is an expected result, not a warning. The failure modes (timeout, not found, unreadable) do need to be observable, which they are. Consider logging only the genuine faults (TIMED_OUT, NOT_FOUND, UNREADABLE, UNKNOWN_STATUS) at WARNING.

### [NOTE] `wait` reloads state after polling

After `wait_for_run` returns, `render_run_status(state_manager.load(run_id))` reads the file again. If the file is replaced or becomes unreadable between the two reads, the command raises an unhandled exception instead of returning its documented exit code. The window is tiny and the file is written atomically. It would be cleaner for the helper to return the loaded `RunState` along with the outcome.

### [NOTE] Report glob can match run ids that contain dots

The pattern `<run_id>.*report.json` correctly excludes `run-a-2` and `run-ab`, as the tests show. It would also match a run whose id is `run-a.x`. That is harmless if run ids never contain dots. A one-line note on that assumption, or parsing the step name out of the matched file name, would settle it.

### [NOTE] Hard breaking removals are intentional and consistent

`sq list` and `sq run --list/-l` are removed with no alias. The change is documented in the changelog (D8, D14), and the error messages, slash command and skill text, and tests were all updated. A stale-reference grep found nothing in source. The one inconsistency is that `shutdown.py` keeps a single long line where `message.py` and `task.py` were re-wrapped.

### [PASS] Eligibility rules are shared, and tests keep listing and resume in step

`item_decisions` and `single_each_step` are now the only source for both `item_resume` and the run listing. `test_check_record_agrees_with_item_decisions` covers the full outcome × flag-kind × decision product, so a drift between the two would be caught. Exception handling in `_Definitions.get` and `_poll` catches specific types, logs, and returns an explicit marker, so it complies with the project rules.

## Response (20261007)

Checked against the code. F001, F002, F003, F005 and F006 are fixed in `8b50fb19`.

- **F001: accepted.** `run_views._RUN_COLUMNS` defines each column once (header, plain-text cell, `never_fold`, optional colour). `render_run_listing` builds the table from it, so no logic reads a header string.
- **F002: accepted.** `render_run_status` escapes run id, pipeline, params, status, checkpoint step and reason. `render_pipeline_listing` now escapes names and descriptions too (they come from user YAML). New test: `test_status_panel_escapes_markup_in_run_values`.
- **F003: accepted.** The wait code moved to `pipeline/run_wait.py`, with its tests in `tests/pipeline/test_run_wait.py`. `run_listing.py` is listing only.
- **F004: declined.** D13 asks for a WARNING on every outcome except COMPLETED. For `wait`, a paused or failed run is the end of something an unattended caller was waiting on, and the log line is the observable signal the failure-mode rule asks for. The stderr line is the CLI's one-line summary for scripts.
- **F005: accepted.** `wait_for_run` returns `WaitResult(outcome, state)` holding the state it last read. `sq runs wait` renders that state and does not reload the file.
- **F006: accepted.** Generated run ids cannot contain dots (`init_run` slugs every non-alphanumeric to `-`). `report_json_paths` now documents that assumption.
- **F007: no change.** `shutdown.py`'s line fits the 104-column limit, so the formatter left it on one line. The other two were re-wrapped only because they exceeded it.

### Run Digest

- Response length: 4887 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 37.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
