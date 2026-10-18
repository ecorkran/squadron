---
docType: tasks
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
project: squadron
lld: user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md
dependencies: []
projectState: 0.23.2 released; slice 947 design complete (revision 2, plus D12 for #239)
dateCreated: 20261018
dateUpdated: 20261018
status: not_started
---

# Tasks: Unattended Pipelines — Cost Cap, No Invented Gates, BLOCKED Tasks, Background Shells

## Context Summary
- Slice 947 makes an unattended `sq run` finish, stop on a real error, pause on a real PM hand-off, or stop at a dollar cap. Source issues: #239, #235, #223, #234.
- Delivers, in order: D12 dispatch end on the CLI's `idle` state (#239); the D10 background-shell probe; the D1 review criterion and D2 `CLAUDE.md` rule; the D3–D6 cost cap; the D7–D8 BLOCKED pause; D11 shell reporting and wait; docs.
- All decisions and contracts live in the slice design (the `lld` above). Each task cites its decision by number. Read that decision before starting the task.
- Prerequisites: none. Everything consumed exists on `main` (0.23.2).
- Branch: `947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors project-wide), and the tests for the touched area. Use `.venv/bin/` tools. Don't use `pytest -n`.
- LLM spend, pipeline runs, and live probes in this slice are pre-authorized.
- Deferred: #240 (pre-implement pending-decision check, blocked on context-forge#121).

## Task 1: Dispatch ends on the CLI's `idle` state (D12, #239) — Effort 3
- [x] Add the session-state constants to `src/squadron/pipeline/sdk_turns.py`, each defined once
  - [x] The env var name `CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS`
  - [x] The system-message subtype `session_state_changed`
  - [x] The state values `idle`, `running`, `requires_action`
- [x] Track state in `DispatchTurns`
  - [x] New field for the latest session state, `None` at dispatch start
  - [x] Feed it from `SystemMessage` frames whose subtype is the session-state subtype, reading `data["state"]`
  - [x] An unknown state string logs WARNING once per dispatch and counts as not idle
  - [x] `waiting` is true when our own result is in and either the state has been seen and isn't `idle`, or no state was seen and the ledger is active
- [x] Set the env var to `"1"` in the env passed by `open_pipeline_session` (`src/squadron/pipeline/sdk_session.py`), merged with `settings["env"]` without dropping existing keys
- [x] Change `_collect_turns` so it ends the dispatch per D12
  - [x] State seen: return only when our own result is in and the latest state is `idle`. Either order (idle before or after the result) ends the dispatch.
  - [x] An `idle` frame that arrives after our result, with no further result, ends the dispatch. The read loop has to return on that frame, not only on a `ResultMessage`.
  - [x] No state seen: today's ledger rule, unchanged
  - [x] Waiting on `running` is bounded by `pipeline.background_idle_timeout_s` through the existing `_stop_background` path
- [x] Update the `_collect_turns` docstring and the `DispatchTurns` docstring to state the new end condition
- [x] Success: one-shot `query()` dispatches (`providers/sdk/agent.py`) are untouched

## Task 2: Tests for D12 — Effort 2
- [x] In `tests/pipeline/test_sdk_session.py`, using the existing fake-client pattern there:
  - [x] Replay the #239 order: our result → agent 2's notice → agent 3's notice queued mid-turn → agent 2's follow-up result (ledger empty, state `running`) → agent 3's follow-up turn → `idle`. The dispatch returns agent 3's follow-up text.
  - [x] `idle` arriving before our result ends the dispatch at our result
  - [x] `idle` arriving after our result, with no further result, ends the dispatch
  - [x] No state frames at all: existing ledger tests pass unchanged
  - [x] State stuck at `running` past a low `background_idle_timeout_s` goes through `_stop_background` and logs its WARNING
  - [x] Stream ends while waiting on `running` raises the existing `ProviderError`
  - [x] Unknown state string logs WARNING once and doesn't end the dispatch
  - [x] `open_pipeline_session` options carry the env var and keep the existing env keys
- [x] Success: all `tests/pipeline/test_sdk_session.py` tests pass; ruff and pyright clean
- [x] Commit: `fix: end SDK session dispatches on the CLI idle state (#239)`
- [x] Comment on #239 with the commit hash, run as its own `gh` call with `--repo ecorkran/squadron`

## Task 3: Background-shell probe (D10) — Effort 3
- [x] Write the probe script at `scripts/probes/background_shell.py`. It isn't collected by pytest. It opens a session via `open_pipeline_session` (so the D12 code and the #199 deny hook are active) and logs every SDK message with its type, subtype, `task_type`, status, and timestamp.
- [x] The probe tries to get a shell into the background inside the pipeline session: a direct `run_in_background` request (expected to be denied by the #199 hook), and a long foreground command the agent moves to the background
- [x] Run it live. Record each answer from the logged output, not from reasoning:
  - [x] (1) The `task_type` string the CLI emits for a background shell
  - [x] (2) Whether a shell can be backgrounded despite the deny hook, and the exact path
  - [x] (3) Whether a shell's terminal status makes the CLI inject a continuation turn
  - [x] (4) Whether a running shell emits `TaskProgressMessage` frames
  - [x] (5) Whether the CLI reports session state `running` while a background shell is live (D12)
- [x] If (2) finds no path, record that, and record (1) and (3)–(5) as not reachable with the evidence
- [x] Amend the slice design
  - [x] D10: add a "Probe results" list with answers (1)–(5) and the log excerpts that show them
  - [x] D11: replace "Written after the probe" with the chosen wait mechanism and its evidence. If (5) is yes, the wait is the D12 wait. If (2) found no path, record reporting and the wait as not needed.
  - [x] D11: unless the wait is not needed or is the D12 wait, end the amendment with a numbered implementation step list for the wait: files, functions, the end condition, and the bound
  - [x] Walkthrough step 5 or 6: keep the one that matches the probe result
- [x] Comment on #234 with answers (1)–(5), as its own `gh` call
- [x] Commit: `test: add background-shell probe and record results in slice 947`

## Task 4: No-invented-gates review criterion (D1) — Effort 1
- [ ] Add `NO_INVENTED_GATES_CRITERION` to `src/squadron/review/review_client.py` with the D1 text, in substance
  - [ ] It's a plain prohibition with no example values (project hallucination-trap rule)
- [ ] Append it to the system prompt after `_STRUCTURED_OUTPUT_INSTRUCTIONS`, only when `not template.is_judge`
- [ ] Success: no review YAML template is edited

## Task 5: Tests for D1 — Effort 1
- [ ] In the existing review-client tests under `tests/review/`:
  - [ ] Each built-in non-judge template (`arch`, `slice`, `tasks`, `code`) gets a system prompt containing the criterion
  - [ ] A user (non-built-in) non-judge template gets it
  - [ ] A `judge-*` template's system prompt doesn't contain it
- [ ] Success: review tests pass; ruff and pyright clean
- [ ] Commit: `feat: add no-invented-gates criterion to non-judge reviews`

## Task 6: `CLAUDE.md` gate rule and BLOCKED convention (D2) — Effort 1
- [ ] Add the D2 rule text to squadron `CLAUDE.md` under Core Principles
- [ ] Don't edit anything under `project-documents/ai-project-guide/` (vendored; upstream is ai-project-guide#45)
- [ ] Success: `CLAUDE.md` contains the gate rule and the `BLOCKED:` line convention
- [ ] Commit: `docs: add invented-gate rule and BLOCKED convention to CLAUDE.md`

## Task 7: Cost-cap config key and `run_spend.py` (D3, D4) — Effort 2
- [ ] Add `pipeline.max_cost_usd` to `src/squadron/config/keys.py`: `type_=float`, `default=None`. The description states that unset means no cap, the cap is best-effort (D5 overshoot bound), and it counts per invocation (D6).
- [ ] Create `src/squadron/pipeline/run_spend.py`
  - [ ] Module constant for the key name, the only literal of it in `src/`
  - [ ] `read_cost_cap(cwd) -> float | None`: `None` when unset; raises `ValueError` naming the key when it's set but isn't a positive number
  - [ ] `RunSpend` with `add(raw_usage)` and a `known_usd` property
  - [ ] `add` parses through `UsageRecord.from_dict`. `None` input adds nothing.
  - [ ] `cost_usd is None` adds nothing and logs WARNING once per alias per run, with the D4 message naming step and alias
  - [ ] A malformed record (`ValueError` from `from_dict`) logs at ERROR and adds nothing
  - [ ] `add` contains no `await`
- [ ] Success: the module imports only from `core`, `config`, and logging, not from the executor

## Task 8: Tests for `run_spend.py` — Effort 1
- [ ] New `tests/pipeline/test_run_spend.py`
  - [ ] `read_cost_cap`: unset → `None`; positive → float; zero, negative, and non-numeric → `ValueError` naming the key
  - [ ] `RunSpend.add`: sums known costs; `None` input is a no-op
  - [ ] Unknown cost: adds nothing; one WARNING per alias across repeated adds; a second alias gets its own WARNING
  - [ ] Malformed record: ERROR logged; total unchanged; no raise
  - [ ] `read_cost_cap` through the real config layer: a value written to a temp project config with the `sq config set` code path reads back as a float
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat: add pipeline.max_cost_usd key and per-run spend ledger`

## Task 9: `FailureKind.COST_CAP` and replay mapping — Effort 1
- [ ] Add `COST_CAP = "cost_cap"` to `FailureKind` in `src/squadron/pipeline/failure_kind.py`
- [ ] Add `FailureClass.COST_CAP` in `src/squadron/replay/outcome.py` and map it in `_CLASS_OF_KIND`
- [ ] Test in `tests/replay/test_outcome.py`: a run whose failed action carries kind `cost_cap` classifies as `FailureClass.COST_CAP` with the action's error text
- [ ] Test: every `FailureKind` member has a `_CLASS_OF_KIND` entry, unless such a test already exists
- [ ] Success: replay tests pass; ruff and pyright clean
- [ ] Commit: `feat: add cost_cap failure kind and replay class`

## Task 10: Executor enforces the cap (D4, D5) — Effort 3
- [ ] In `execute_pipeline` (`src/squadron/pipeline/executor.py`), call `read_cost_cap(cwd)` before the first step. A `ValueError` fails the run at start with that error.
- [ ] Create one `RunSpend` next to the per-run `UsageCapture`
- [ ] Thread it as a parameter the same way `usage_capture` is threaded: `_execute_step` → `_execute_step_once`, and through the loop, `each`, and `fan_out` paths. `fan_out`'s `_run_branch` closures receive the same instance.
- [ ] In `_execute_step_once`, after POST_ACTION events: `spend.add(result.metadata.get(USAGE_KEY))`; then if a cap is set and `known_usd > cap`, the action result becomes `success=False` with `metadata[FAILURE_KIND_KEY] = FailureKind.COST_CAP` and the D5 error text, showing spend and cap with two decimals
- [ ] Success: no cap configured → no behavior change (existing executor tests pass unchanged)

## Task 11: Tests for cap enforcement — Effort 2
- [ ] In the executor tests under `tests/pipeline/`, using fake actions that stamp usage under `USAGE_KEY`:
  - [ ] Cap unset: a run spending any amount completes
  - [ ] Cap crossed on the second action: that action fails with kind `cost_cap` and the D5 message; the run is FAILED; no later step runs
  - [ ] Invalid cap config: the run fails at start with the `ValueError` text and runs no step
  - [ ] Unknown-cost actions don't count toward the cap and log the WARNING
  - [ ] `fan_out` step: all branches add to one `RunSpend`; the reported spend is the real total
  - [ ] `each` step: items add to the same `RunSpend`
- [ ] Success: pipeline tests pass; ruff and pyright clean
- [ ] Commit: `feat: enforce pipeline.max_cost_usd in the executor`

## Task 12: Extract `slice_task_paths` (D7) — Effort 1
- [ ] In `src/squadron/pipeline/branch_ops.py`, extract `slice_task_paths(cf_client, slice_index, cwd) -> list[Path]` from `_require_checked_tasks`, using `resolve_slice_info(...)["task_files"]` and `TASKS_DIR`
- [ ] `_require_checked_tasks` calls it; its behavior and error messages are unchanged
- [ ] Unit test for `slice_task_paths`: returns the resolved paths; a cf error propagates
- [ ] Success: existing merge-guard tests pass unchanged; ruff and pyright clean
- [ ] Commit: `refactor: extract slice_task_paths from the merge guard`

## Task 13: `parse_blocked_markers` (D7) — Effort 2
- [ ] Add `parse_blocked_markers(text) -> tuple[str, ...]` to `src/squadron/pr/tasks.py`, next to `parse_task_items`
  - [ ] The marker word `BLOCKED` is a module constant, the only literal of it in `src/`
  - [ ] Lenient per D7: strip leading whitespace, any number of `>` marks, a list bullet (`-*+`) with an optional checkbox, and `*`/`_` emphasis; then match the uppercase word followed by `:`, `—`, `-`, or whitespace
  - [ ] Case-sensitive, so lowercase prose doesn't match
  - [ ] Returns the text after the marker for each matching line, in file order
- [ ] Tests in the existing `pr/tasks` test module:
  - [ ] Fixture with the real line quoted in #223: `> BLOCKED: no judge-template review artifact ... PM asked`
  - [ ] List-item form, checkbox form, bold form (`**BLOCKED:**`), plain form, em-dash and hyphen separators, nested `> >`
  - [ ] Rejects `blocked by`, `Blocked:`, and `UNBLOCKED:`
  - [ ] No markers → empty tuple
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat: parse BLOCKED markers from task files`

## Task 14: Executor copies `awaits_human` from event outcomes (D7) — Effort 1
- [ ] In the executor's event-outcome loop, copy `awaits_human` from the failing outcome along with `success`, `error`, and failure kind
- [ ] Test: a user-style POST_ACTION action that returns `success=False, awaits_human=True` turns the step PAUSED and the run PAUSED, and runs no later step
- [ ] Test: a failing outcome without `awaits_human` still fails the run (unchanged)
- [ ] Success: events and pipeline tests pass; ruff and pyright clean
- [ ] Commit: `feat: let POST_ACTION events pause a run via awaits_human`

## Task 15: `squadron.blocked-tasks` action and binding (D7) — Effort 2
- [ ] Create `src/squadron/events/builtin/blocked_tasks.py`, following `dispatch_branch_work.py` for structure and registration
  - [ ] Guard: applies only when `action_type == dispatch`, `step_type == StepTypeName.IMPLEMENT`, the result succeeded, a `slice` param is present, and the result isn't `SKIPPED_KEY`. Otherwise it passes.
  - [ ] Reads the slice's task files through `slice_task_paths` and collects markers through `parse_blocked_markers`
  - [ ] No markers → pass
  - [ ] Markers → `success=False`, `awaits_human=True`, with the D7 error text including the run id and the marker texts; logged at WARNING
  - [ ] Unreadable task file → plain failure naming the path (not paused)
  - [ ] cf error → plain failure with the cf error text
- [ ] Register it and add it to `DEFAULT_BINDINGS` in `src/squadron/events/manifest.py`, before `squadron.dispatch-branch-work`
- [ ] Success: `events.yaml` `disable: [squadron.blocked-tasks]` removes it, like every built-in

## Task 16: Tests for `squadron.blocked-tasks` — Effort 2
- [ ] New `tests/events/builtin/test_blocked_tasks.py`
  - [ ] Each guard condition that doesn't apply → pass, with no task-file read
  - [ ] Markers present → failing result with `awaits_human=True`, the marker texts, and the resume command; WARNING logged
  - [ ] No markers → pass
  - [ ] Unreadable task file → failure naming the path, `awaits_human` false
  - [ ] cf error → failure with the cf text
- [ ] In `tests/events/test_manifest.py`: the binding exists and comes before `squadron.dispatch-branch-work`; disabling it removes it
- [ ] Executor-level test: an implement dispatch that leaves a marker and made no commits pauses at `implement` (the blocked check wins over branch-work's no-commits failure)
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat: pause pipelines on BLOCKED task markers after implement`

## Task 17: Resume re-runs implement (D8) — Effort 1
- [ ] Test, using the existing resume test pattern: pause on BLOCKED at `implement`, remove the marker from the task file, resume, and assert implement is dispatched again and later steps run
- [ ] Success: no resume code changes; test passes
- [ ] Commit: `test: resume after a BLOCKED pause re-dispatches implement`

## Task 18: Report running background shells (D11) — Effort 2
- [ ] Add `SHELL_TASK_TYPE` to `sdk_turns.py` with the value recorded by Task 3 probe answer (1). If the probe recorded shells as not reachable, mark this task's items and Tasks 19–21 [x] with the note "not reachable per D10 probe" and go to Task 22. Never write a shell type string the probe didn't record.
- [ ] Extend `BackgroundLedger` to track shells separately from waited-for agents: start on `TaskStartedMessage` with the shell type; clear on the same terminal frames agents use
- [ ] When a dispatch returns with shells still running: WARNING `dispatch ended with N background shell(s) running: <descriptions>`, and `background_shells_running: int` in dispatch metadata, set the same way as `background_tasks_waited`
- [ ] Extend the `ProviderError` "stream ended before the dispatch's result" message to name running shells
- [ ] Success: `background_tasks_waited` and `background_tasks_stopped` keep their agent-only meaning

## Task 19: Tests for shell reporting — Effort 1
- [ ] In `tests/pipeline/test_sdk_session.py`:
  - [ ] Shell start then terminal frame → not running, no WARNING
  - [ ] Shell start, dispatch returns → WARNING naming it; `background_shells_running == 1`
  - [ ] Stream ends with a shell running → `ProviderError` names the shell
  - [ ] Shell starts don't change `background_tasks_waited`
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat: report background shells left running at dispatch end`

## Task 20: Wait for background shells (D11) — Effort 3
- [ ] Check that D11 in the slice design records the wait mechanism and its probe evidence (Task 3). If it doesn't, this task doesn't start, and the D11 success criterion stays unchecked.
- [ ] If D11 records the wait as not needed: mark this task's items [x] with the note "not needed per D11" and go to Task 22
- [ ] If D11 records that the D12 wait covers shells: add the test in Task 21 only; no new code
- [ ] Otherwise follow D11's numbered implementation step list, one sub-item per step, bounded by `pipeline.background_idle_timeout_s`. A shell stopped at the bound logs WARNING.
- [ ] Success: a turn that ends with a shell running doesn't end the dispatch until the shell's terminal frame or the bound, and the D11 failure modes behave as D11 states

## Task 21: Tests for the shell wait — Effort 2
- [ ] A turn that ends with a shell running waits, and the dispatch returns the text after the shell completes
- [ ] Shell exits non-zero → cleared by its terminal frame; no special action
- [ ] Shell outlives a low `background_idle_timeout_s` → stopped with WARNING
- [ ] Stream closes mid-wait → `ProviderError` naming the shell
- [ ] An extra turn's cost lands in the dispatch's usage telemetry
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat: wait for background shells in SDK session dispatches`

## Task 22: Docs and CHANGELOG — Effort 1
- [ ] `docs/PIPELINES.md`: `pipeline.max_cost_usd`, how to set it, the D5 overshoot bound, the per-invocation count (D6), the unknown-cost WARNING, `--prompt-only` not capped; the BLOCKED pause and how to resume; the shell wait and its bound
- [ ] `docs/EVENTS.md`: `squadron.blocked-tasks` in the built-in list with its order; the `awaits_human` pause contract for POST_ACTION actions
- [ ] CHANGELOG under Unreleased: short user-facing bullets for the cost cap, the BLOCKED pause, the shell wait, and the #239 fix
- [ ] Success: every doc names the key and action exactly as defined in code
- [ ] Commit: `docs: document cost cap, BLOCKED pause, and background-shell wait`

## Task 23: Full validation — Effort 1
- [ ] `.venv/bin/ruff format --check`, `.venv/bin/ruff check`, `.venv/bin/pyright` with zero errors
- [ ] Full test suite, run in the background, all passing. Record any failure with its output and fix it before continuing.
- [ ] Commit any fixes: `fix: address slice 947 validation failures`

## Task 24: Verification walkthrough — Effort 2
- [ ] Create a scratch slice as slice 178's walkthrough did, so no real slice is touched
- [ ] Run walkthrough steps 1–4 and the probe-matched step 5 or 6 from the slice design, with `--model` on every `sq review`
- [ ] Replace the design's "Draft" walkthrough with the commands as run and their observed output lines
- [ ] Remove the scratch slice and its artifacts; reset `pipeline.max_cost_usd` to unset
- [ ] Success: each walkthrough step's expected output was observed, or the mismatch was fixed and the step re-run
- [ ] Commit: `docs: record slice 947 verification walkthrough`
