---
docType: slice-design
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261017
dateUpdated: 20261019
status: complete
turns: 82
promptTokens: 7049132
cachedTokens: 6885803
cacheWriteTokens: 163185
completionTokens: 59391
durationSeconds: 733.9
costUsd: 3.873626
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

# Slice Design: Unattended Pipelines — Cost Cap, No Invented Gates, BLOCKED Tasks, Background Shells

## Overview

A pipeline started unattended should run to completion, or stop only on a real error or an enforced cost cap. Three failures break that today:

- **[#235](https://github.com/ecorkran/squadron/issues/235):** reviewers invent confirmation gates ("the PM should confirm…"). The revise loop writes them into artifacts and implementers obey them. Nothing in code bounds spend, so prose gates are standing in for a cost control that doesn't exist.
- **[#223](https://github.com/ecorkran/squadron/issues/223):** an implement agent marks a task `BLOCKED` on a PM hand-off, and the pipeline keeps going: review, commit, close-out and devlog all run on an incomplete slice, and the merge guard only catches it by counting unchecked items.
- **[#234](https://github.com/ecorkran/squadron/issues/234):** the agent ends its turn waiting on a background shell (a test run). The dispatch counts the turn as finished, and the post-condition fails, wasting the dispatch.

This slice adds a review criterion and a CLAUDE.md rule against invented gates, a real per-run `max_cost_usd` cap enforced by the executor, a POST_ACTION check that pauses after an implement dispatch leaves a `BLOCKED` task, and a dispatch wait for background shells with end-of-turn reporting.

## Value

- **PM:** `sq run P56 <slice>` can be left alone. It finishes, stops on a real error, pauses on a real PM hand-off and prints the blocker, or stops at a dollar cap the PM set. Wasted dispatches from invented gates and abandoned shells go away.
- **Reviews:** findings that only add caution or approval steps are excluded by instruction, so the revise loop stops adding weight that nobody asked for (same family as slice 943).
- **Cost:** each run's spend is summed and checked against a cap; before this slice spend was only captured per dispatch. The cap is best-effort with a stated overshoot bound (D5).

## Technical Scope

**Included**

1. A "no invented gates" criterion added to the system prompt of every non-judge review template (D1).
2. A rule in squadron's `CLAUDE.md` saying confirmation steps without a named rule are invalid, plus the `BLOCKED:` marker convention (D2). The upstream `rules/general.md` change is filed as [ai-project-guide#45](https://github.com/ecorkran/ai-project-guide/issues/45).
3. A `pipeline.max_cost_usd` config key. The executor sums each invocation's spend and checks it after every action (D3–D6). This is in scope because slice plan entry 41 assigns it to this slice, and #235 replaces the prose cost gates with it. It adds no new commands or files, only one config key over the existing executor.
4. A built-in POST_ACTION action `squadron.blocked-tasks`. When an implement dispatch leaves a `BLOCKED:` marker in the slice's task files, it pauses the run and prints the marker text. Resuming re-runs the implement step (D7, D8).
5. Background shells in the SDK dispatch: an evidence probe first, then end-of-turn reporting of running shells, and a wait for shells bounded by the existing background idle timeout. The wait mechanism is written into D11 from the probe's results (D10, D11).
6. [#239](https://github.com/ecorkran/squadron/issues/239): an SDK session dispatch ends on the CLI's `idle` session state, not on an empty agent ledger, so a background agent's follow-up turn is never cut off (D12). It lands first because D11's wait and the D10 probe both run over `_collect_turns`.

**Excluded**

- The task-breakdown guide change from #235 item 2. It already shipped with [ai-project-guide#44](https://github.com/ecorkran/ai-project-guide/issues/44) (`guide.ai-project.005-task-breakdown.md` line 155: "No task may wait on a Project Manager decision…").
- The pre-implement pending-decision check from the #223 comment. It is blocked on [context-forge#121](https://github.com/ecorkran/context-forge/issues/121) and filed as [#240](https://github.com/ecorkran/squadron/issues/240) (D9).
- The misleading code-review PASS on a slice with open items (#223, second bullet). The pause now stops the run before that review happens; review-content changes stay out of scope.
- `--prompt-only` runs. The outer agent does the dispatching there, so squadron sees no spend and enforces no cap.
- A pipeline YAML `max_cost_usd` field. The plan allows "pipeline YAML or project config", and config alone covers per-project caps.
- Persisting spend across resume. A resumed run counts spend from $0 (D6).
- A `--max-cost` CLI flag. The config key covers per-project caps, and it applies the same way to CLI, MCP and slash-command runs because the executor enforces them.
- Monitor tasks and teammate/remote agent task types. They are not waited for, same as today.

## Dependencies

### Prerequisites

None. Everything consumed below already exists on `main` (0.23.2).

### Interfaces Required

- `UsageRecord` stamped under `USAGE_KEY` in `ActionResult.metadata` by every LLM action (slice 175), and `UsageRecord.from_dict`.
- `ActionResult.awaits_human` → `ExecutionStatus.PAUSED` mapping in `_execute_step_once` (already used by the branch merge's unfinished-tasks refusal).
- POST_ACTION event bindings (`events/manifest.py` `DEFAULT_BINDINGS`); the first failing outcome wins.
- `resolve_slice_info(cf_client, slice_index)["task_files"]` and `TASKS_DIR` (used by the merge guard in `branch_ops.py`).
- `BackgroundLedger`, `DispatchTurns`, `_collect_turns`, `_stop_background` in `sdk_turns.py` / `sdk_session.py` (slice 932 D5/D6), and `pipeline.background_idle_timeout_s`.
- The `run_in_background` deny hook (`background_shell_guard.py`, #199, shipped 0.21.5). It stays in place (D11).

## Architecture

### Component Structure

| Component | Location | Change |
|---|---|---|
| Review prompt assembly | `review/review_client.py` | Append `NO_INVENTED_GATES_CRITERION` to non-judge system prompts |
| Project rules | `CLAUDE.md` | Gate rule + `BLOCKED:` convention |
| Run spend ledger | new `pipeline/run_spend.py` | `RunSpend`, `read_cost_cap()` |
| Cap config | `config/keys.py` | `pipeline.max_cost_usd` key |
| Cap enforcement | `pipeline/executor.py` | Create `RunSpend`, thread it to `_execute_step_once`, post-action check |
| Failure classification | `replay/outcome.py` | Map `FailureKind.COST_CAP` → new `FailureClass.COST_CAP` |
| BLOCKED check | new `events/builtin/blocked_tasks.py` | `squadron.blocked-tasks` POST_ACTION action |
| Task-file reading | `pipeline/branch_ops.py` | Extract `slice_task_paths()` shared by merge guard and BLOCKED check |
| Event outcome copy | `pipeline/executor.py` | Copy `awaits_human` from a failing event outcome |
| Shell tracking | `pipeline/sdk_turns.py`, `sdk_session.py` | Report running shells; wait per D11 |
| Dispatch end (#239) | `pipeline/sdk_turns.py`, `sdk_session.py` | Session-state env, `DispatchTurns` state, `_collect_turns` ends on `idle` (D12) |

### Data Flow

**Cost cap**

```
execute_pipeline start
  cap = read_cost_cap(cwd)                             # float | None
  spend = RunSpend()                                   # per invocation; a resume starts at $0
  for each action in _execute_step_once:
      result = action.execute(ctx); POST_ACTION events run (usage already stamped)
      spend.add(result.metadata.get(USAGE_KEY))         # unknown cost → WARNING, counted
      if cap and spend.known_usd > cap: fail action (FailureKind.COST_CAP) → step FAILED → run FAILED
```

**BLOCKED pause**

```
implement dispatch returns → POST_ACTION
  squadron.blocked-tasks (bound before dispatch-branch-work)
    not implement dispatch / skipped / no slice → pass
    read slice task files → find BLOCKED markers
    none → pass
    any  → ActionResult(success=False, awaits_human=True, error="<n> blocked task(s): …")
  executor copies awaits_human → step PAUSED → run PAUSED at "implement"
sq run --resume <run-id> → resume starts at the paused step → implement re-dispatched
```

**Background shells (SDK dispatch)**

```
TaskStartedMessage(task_type == SHELL_TASK_TYPE) → ledger records shell start; terminal frame clears it
dispatch returns with a shell still running → WARNING naming it; background_shells_running in metadata
wait for shells (bounded by pipeline.background_idle_timeout_s) → mechanism per D11, from probe evidence
```

### State Management

- `RunSpend` is in-memory, one per `execute_pipeline` call, created next to the existing per-run `UsageCapture`. It is passed down as a parameter the same way `usage_capture` is: `_execute_step` → `_execute_step_once`, and through the loop, `each` and `fan_out` paths. `fan_out`'s `_run_branch` closures receive the same instance. `RunSpend.add` contains no `await`, so concurrent branches on the one event loop can't interleave inside an addition.
- Nothing is persisted. A resumed run counts from $0 (D6).
- The BLOCKED check is stateless. The marker lives in the task file, and the PM (or the agent, once the task is done) removes it. A marker left in place pauses the run again on the next implement, which is correct.
- Shell tracking is per dispatch, like the agent ledger.

## Technical Decisions

### D1 — No-invented-gates criterion is one shared constant, non-judge templates only
Status: decided
- A constant `NO_INVENTED_GATES_CRITERION` in `review_client.py` is appended to the system prompt after `_STRUCTURED_OUTPUT_INSTRUCTIONS` when `not template.is_judge`. Text, in substance: "Approval steps, confirmation gates, and added caution are never valid findings. LLM spend, pipeline runs, and live tests are pre-authorized; spend is bounded by the run's enforced cost cap. Do not ask for a step that waits on Project Manager confirmation unless a rule you were given names it as required."
- Every non-judge review (built-in `arch`, `slice`, `tasks`, `code`, plus user templates) goes through this one assembly point, so the rule is stated once and can't drift between YAML files.
- Judges are excluded, meaning templates with a `judge:` block (`judge-slice-vs-arch`, `judge-tasks-vs-slice`); the test is `template.is_judge`. `judge-findings-addressed` has no `judge:` block, is not score-calibrated, and so gets the criterion like any non-judge template. Their prompts are calibrated by initiative 320, and a prompt change shifts scores against existing baselines. Judges score fit against criteria and don't propose process steps.
- Rejected: copying the bullet into the five non-judge YAMLs (duplicates the rule, and user templates miss it).

### D2 — CLAUDE.md rule and BLOCKED convention; upstream via issue
Status: decided
- Add to squadron `CLAUDE.md` Core Principles: "A step in any artifact that waits on Project Manager confirmation, approval, or added caution is invalid unless a named rule requires it; ignore it. LLM spend, pipeline runs, and live tests are pre-authorized. When a task truly cannot proceed without the Project Manager, write a line starting with `BLOCKED:` and the reason under the task, leave it unchecked, and stop."
- `CLAUDE.md` is derived from ai-project-guide `rules/general.md`, so the durable fix is upstream ([ai-project-guide#45](https://github.com/ecorkran/ai-project-guide/issues/45)). This slice changes only squadron's copy and does not edit the vendored guide.
- The BLOCKED convention formalizes what agents already write (`> BLOCKED: …` in amoeba slice 107), so D7 matches real output.

### D3 — One cap source: project config
Status: decided
- Config: `pipeline.max_cost_usd`, `type_=float`, `default=None` (no cap). `read_cost_cap(cwd) -> float | None` in `run_spend.py` returns `None` when it's unset, and raises `ValueError` when it's set but isn't a positive number. The run fails at start with that error.
- Unset means no cap. That's explicit, documented in the key description, and not a fallback value.
- Rejected: also accepting a pipeline YAML field. A second source needs precedence rules, and nothing needs it yet.

### D4 — Spend is summed from stamped usage records in the executor
Status: decided
- `RunSpend.add(raw_usage)` parses `ActionResult.metadata[USAGE_KEY]` itself through `UsageRecord.from_dict`, so there is no separate helper. It runs after POST_ACTION events, at the single action site `_execute_step_once`. Every LLM action (dispatch, review, summary, compact, loop rounds, each/fan-out items) passes through it.
- Rejected: accumulating inside `UsageCapture`. Review records are built by `record_from_review` outside `_build`, so two paths would need hooking, and live spend would come from a different source than resume spend.
- A record with `cost_usd is None` adds nothing and logs WARNING once per alias per run: "step X (alias Y) reported no cost; the run's spend is a lower bound". The cap compares known spend. Failing on unknown cost would stop every run on an unpriced alias, which contradicts the slice goal; the WARNING keeps it observable.
- A malformed usage record raises `ValueError` from `from_dict`. It's logged at ERROR and adds nothing, so it doesn't crash the run (the same posture `usage-stamp` takes).

### D5 — Cap exceeded fails the run; checked before the run and after each action
Status: decided
- After each action: if `known_usd > cap`, the action result becomes `success=False`, with `metadata[FAILURE_KIND_KEY] = FailureKind.COST_CAP` (new member). The error is `"run spent $X.XX this invocation, over pipeline.max_cost_usd $Y.YY; raise the cap and resume to continue"`. The step fails and the run fails. This is an error, not a pause (#235: "stops the run with an explicit error").
- The cap is best-effort, with these bounds stated in `docs/PIPELINES.md` and the config key description:
  - **Overshoot:** at most the cost of the actions in flight when the cap is crossed. `each` runs items serially, so outside `fan_out` that's one action. A `fan_out` step runs its branches concurrently (`asyncio.gather`), so it adds at most one action per branch, up to the step's branch count. Each branch stops at its own next check. The error's "spent $X" reports the real total.
  - **Per invocation:** a resumed run's count starts at $0, so a run and its resumes can together spend up to the cap once per invocation (D6).
  - **Unknown cost:** actions with no reported cost aren't counted (D4 WARNING).
- **`each` batches:** a `cost_cap` failure fails the `each` step under either `on_item_failure` policy. Under `continue` the item would otherwise be flagged and the batch would keep spending, so `_item_outcome` treats the cap as fatal.
- **`fan_out` error text:** a failed branch's step error is its failed action's error (`_item_failure_reason`), not the bare "branch failed", so the cap message (spent, cap, remedy) reaches the step error and the run summary.
- `RunSpend` takes the cap in its constructor (`RunSpend(cap_usd)`) and owns the check (`cap_error()`), so the executor threads one object, not a spend and a cap.

### D6 — Spend counts per invocation; not persisted
Status: decided
- Each `sq run` or `sq run --resume` starts its count at $0. The PM resumes a capped run deliberately, so each resume is a new spend decision. The limit is stated in the config key description and `docs/PIPELINES.md`.
- Rejected: persisting spend on `RunState`. It needs a state field, observer changes, a pre-run check and a pre-slice-file warning, and the plan doesn't require it.

### D7 — `squadron.blocked-tasks` POST_ACTION action, bound before branch-work
Status: decided
- New `events/builtin/blocked_tasks.py`, registered and added to `DEFAULT_BINDINGS` **before** `squadron.dispatch-branch-work`. A blocked agent often commits nothing, and the PM hand-off has to win over the "no commits" failure (the first failing outcome wins).
- It applies when `action_type == dispatch`, `step_type == StepTypeName.IMPLEMENT`, the result succeeded, a `slice` param is present, and the result isn't `SKIPPED_KEY`. That's the same guard shape as `dispatch-branch-work`.
- Task files: extract `slice_task_paths(cf_client, slice_index, cwd) -> list[Path]` from the merge guard in `branch_ops.py`. Both the guard and this check call it.
- Marker parsing is a new `parse_blocked_markers(text) -> tuple[str, ...]` in `pr/tasks.py`, next to `parse_task_items`. It's lenient: strip leading whitespace, any number of `>` blockquote marks, a list bullet (`-*+`) with an optional checkbox, and `*`/`_` emphasis. The line then matches if it starts with the uppercase word `BLOCKED`, followed by `:`, `—`, `-`, or whitespace. Matching is case-sensitive so prose like "blocked by" doesn't match. The returned text is the line after the marker.
- On markers: `ActionResult(success=False, awaits_human=True, error=f"{n} blocked task(s) need the Project Manager: {first markers}. Resolve them, remove the BLOCKED lines, then resume: sq run --resume {run_id}")`, logged at WARNING. The executor's event-outcome loop now copies `awaits_human` along with `success`/`error`/failure kind. That turns the step into `PAUSED`. This changes the POST_ACTION contract for every binding, including user-defined ones: a failing outcome with `awaits_human=True` now pauses the run instead of failing it. No existing built-in event action sets `awaits_human` (today only the branch action does, and it isn't an event), so built-in behavior is unchanged.
- Unreadable task file: fails closed as a plain failure (not paused), naming the path. That matches the merge guard's `OTHER`.

### D8 — Resume re-runs the implement step through existing resume logic
Status: decided
- A paused run resumes at its paused step (`first_unfinished_step_of`), and the paused step is the phase-6 `implement` step, so the dispatch runs again.
- **Amended after the live walkthrough.** "No new resume code" was wrong. P6's implement step is `existing: keep`, which skips the dispatch when the slice branch has any commits ahead of the target. A blocked agent often commits its partial work, and a PM who commits the resolution adds a commit too, so the resume found "existing work", skipped implement, and went on to review (the live run failed with `code review resolved diff … to no changed files`, or, with partial commits, would have reviewed unfinished work). Fix: `execute_pipeline` checks the run state when it resumes; if the restarted step's latest record is `PAUSED` and one of its actions has `awaits_human`, it sets the reserved param `resumed_from_handoff` for that step only, and the implement keep check (`_kept_branch_work`) then dispatches. A checkpoint pause is not a hand-off (its step finished), so it keeps skipping. Tests: `tests/pipeline/test_blocked_pause.py` (param set for the resumed step only; a plain failure does not set it) and `tests/pipeline/test_existing_keep.py`.

### D9 — Pre-implement pending-decision check is deferred
Status: decided
- The check belongs to cf ([context-forge#121](https://github.com/ecorkran/context-forge/issues/121), open), and squadron doesn't parse decision status itself, because gating lives in cf. Filed as [#240](https://github.com/ecorkran/squadron/issues/240). #223 closes with this slice. #240 tracks the remainder.

### D10 — Background shells: evidence probe first
Status: decided
- The #234 run happened after the #199 deny hook shipped, and the issue notes that backgrounding wasn't confirmed from logs. Following the project's debugging rule, Task 3 (after D12 lands) is a probe against the real SDK/CLI, at `scripts/probes/background_shell.py` (live runs are pre-authorized). It records, in the slice design and the issue:
  1. the `task_type` string the CLI emits for a backgrounded shell. This becomes the constant `SHELL_TASK_TYPE` in `sdk_turns.py`; the SDK doesn't name it.
  2. whether a shell can be backgrounded in a pipeline session despite the deny hook (for example, a long foreground command moved to the background), and how.
  3. whether a shell's terminal status leads the CLI to inject a continuation turn. The SDK's `DEFERRING_TASK_TYPES` comment says only agent/workflow completion runs a follow-up turn.
  4. whether a running shell emits `TaskProgressMessage` frames.
- If (2) finds no path to a background shell, there is no shell to see and no `task_type` string to identify one by. Neither D11 reporting nor the wait ships; both are recorded as not needed, with the probe output as evidence. No shell type is ever written without probe evidence (hallucination-trap rule).

**Probe results** (`scripts/probes/background_shell.py`, run live on claude-haiku-4-5-20251001, CLI 2.1.302, through `open_pipeline_session` so the #199 hook and the D12 state frames were active). Five experiments; frames quoted from the logs.
1. **`task_type` is `local_bash`** for every backgrounded shell, from both paths in (2): `TaskStartedMessage task_type="local_bash"`.
2. **A shell can be backgrounded despite the deny hook, by two paths the hook does not see.**
   - `run_in_background: true` directly: denied by the hook (`PreToolUse:Bash hook error: Background shells are not allowed...`). No task starts.
   - A Bash command that runs past its own `timeout` parameter: the CLI moves it to the background itself (`Command did not complete within its 5s timeout and was moved to the background (ID: b66lefm88)`), after a `TaskStartedMessage local_bash`. No `run_in_background` input is involved, so the hook never fires. A long `sleep` as the command is refused by the CLI before it runs (`Blocked: sleep 40 followed by...`), which is why the probe uses `python3 -c "import time; time.sleep(40)"` for this path.
   - The Monitor tool (`ToolSearch select:Monitor`, then `Monitor`): `TaskStartedMessage local_bash` and `background_tasks_changed`. The hook matches only `Bash`, so Monitor is not covered either.
   - `(cmd) &` inside a foreground command: no task frame at all. It is an untracked OS process, not a tracked shell.
3. **A shell's end makes the CLI inject a continuation turn**, after the dispatch has already returned. Both paths: `task_updated status=completed`, `task_notification status=completed`, `session_state_changed running`, an assistant turn, then a `ResultMessage` with `origin={"kind": "task-notification"}`, then `idle`. The SDK's `DEFERRING_TASK_TYPES` comment (only agents and workflows run a follow-up turn) does not hold for the CLI 2.1.302 behavior. This is #234's mechanism.
4. **No progress frames.** Zero `TaskProgressMessage` / `task_progress` frames across all five logs, with shells running 22–30 s. The idle timer sees only silence for a shell's whole run.
5. **The CLI reports `idle` while a shell is live.** Monitor log: `idle` at t=8.0 s, shell still running, `running` only at t=30.8 s when the shell ended. Same in the timeout path (`idle` t=10.8 s, `running` t=43.2 s). The D12 state does not cover shells; the wait needs its own mechanism (D11).

### D11 — Report running shells now; write the wait mechanism from the probe
Status: decided
- Committed once probe (1) yields the shell `task_type`: `BackgroundLedger` records shell starts and terminal frames (`SHELL_TASK_TYPE` from probe 1). When a dispatch returns with a shell still running, it logs WARNING ("dispatch ended with N background shell(s) running: <descriptions>") and sets `background_shells_running: int` in dispatch metadata, the way `background_tasks_waited` reaches it today.
- Committed now: the dispatch waits for shells, bounded by `pipeline.background_idle_timeout_s` (the slice plan's requirement). A shell stopped at that bound logs WARNING.
- **Wait mechanism (from the D10 probe).** Shells are reachable (probe 2), `SHELL_TASK_TYPE = "local_bash"` (probe 1). The CLI injects the continuation turn itself when a shell ends (probe 3), so squadron sends nothing: it only has to keep reading. The state is `idle` while a shell lives (probe 5), so the D12 end rule alone returns too early, and there are no progress frames (probe 4), so the idle timer is silence for the shell's whole run.
  - **End rule.** A dispatch is waiting when our own result is in and either the ledger holds a running agent or shell, or a state frame has been seen and the state isn't `idle`. It settles when neither holds. The ledger term keeps the pre-D12 agent behavior when the CLI says `idle` while an agent lives, and adds shells. The shell's terminal frames clear the ledger, the CLI's `running` that follows keeps the wait open through the continuation turn, and its `idle` ends it (#239's ordering, now for shells).
  - **Bound.** `pipeline.background_idle_timeout_s` (default 1800 s) of silence. Because shells emit no progress, a shell that runs longer than the bound is stopped. The docs say so.
  - **Implementation steps** (Tasks 18 and 20 follow these):
    1. `sdk_turns.py`: add `SHELL_TASK_TYPE = "local_bash"`, citing this probe. `BackgroundLedger` tracks shells in a separate set from agents: `shells_active`, `shell_ids()`, `shell_descriptions()`. `active`, `active_ids()`, `seen_count` and `descriptions()` stay agents-only. Add `holding` (agents or shells running).
    2. `sdk_turns.py`: `DispatchTurns.waiting` becomes `own_result_seen and (ledger.holding or state_seen_and_not_idle)`. `settled` is unchanged.
    3. `sdk_session.py` `_collect_turns`: the stream-ended error and the wait log use `ledger.holding`; the message names running shells beside agents.
    4. `sdk_session.py` `_stop_background`: stop agent ids and shell ids through `client.stop_task`; `background_tasks_stopped` counts agents only; the shell ids stopped set `background_shells_running`, and the WARNING names them. Whether `stop_task` ends a `local_bash` task is verified live in walkthrough step 5, not assumed.
    5. `DispatchTurns.telemetry` already folds the injected turn's result, so its cost reaches the dispatch's usage record and the cap with no further change.
- Failure modes on this path, each with an observable signal and a test:
  - **Shell exits non-zero:** a normal terminal frame clears it. The agent reads the result itself; squadron takes no special action.
  - **Shell outlives the bound:** it's stopped and WARNING is logged.
  - **CLI process dies, or the SDK stream closes mid-wait:** the existing `ProviderError` "stream ended before the dispatch's result" path, with its message extended to name the shells still running.
  - **Extra turn to resume the agent:** `DispatchTurns.telemetry` already folds every `ResultMessage` the dispatch reads, including injected turns. Its cost lands in the dispatch's usage record and counts against the cap with no extra work.
- Gating: the probe task's last item amends this D11. The wait task's first item checks that D11 records the mechanism and its probe evidence, and the wait task doesn't start without it. If the amendment never happens, the slice isn't complete: the wait criterion below stays unchecked.
- The #199 deny hook stays. It keeps explicit backgrounding in the foreground, where the foreground stall bound applies.

### D12 — End a session dispatch on the CLI's `idle` state (#239)
Status: decided
- Cause (from CLI transcript 8eb3453f, recorded on #239): `BackgroundLedger` clears an agent when its `TaskNotificationMessage` arrives, which is before the turn that consumes it. A notice queued mid-turn leaves the ledger empty at that turn's result, so `_collect_turns` returns while the CLI still owes a follow-up turn. The SDK documents the gap (`_track_task_lifecycle`, SDK #1190): only the CLI's session state closes it.
- The SDK (0.2.162) already sets `CLAUDE_CODE_SDK_READS_SESSION_STATE`, but it drops those frames from the caller's stream (`sdk_host_only`). `open_pipeline_session` adds `CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS=1` to the session env, so `session_state_changed` reaches us as a `SystemMessage` with `data["state"]` in `idle` / `running` / `requires_action`. The env name and the state values are constants defined once in `sdk_turns.py`.
- `DispatchTurns` records the latest state, starting at `None` for each dispatch. Once a state frame has been seen, the dispatch ends when our own result is in **and** the state is `idle`. The idle frame may arrive before or after the result, and either order ends the dispatch. While the state is `running` after our result, the dispatch is waiting, bounded by `pipeline.background_idle_timeout_s` (the existing `_stop_background` path).
- No state frame seen in the dispatch (older CLI): today's ledger rule applies, unchanged.
- Only the persistent `SDKExecutionSession` path changes. One-shot `query()` dispatches and `--prompt-only` runs already let the CLI decide when the run ends.
- Failure modes: a stream that closes mid-wait goes through the existing `ProviderError` path. Waiting on `running` past the bound goes through `_stop_background` with its WARNING. An unknown state string logs WARNING once and counts as not idle.
- D10 runs its probe after D12 lands, and adds a fifth question: does the CLI report `running` while a background shell is live? If it does, D11's wait is the D12 wait and needs no separate mechanism. It does not (D10 result 5): D11 adds the ledger term to the end rule.

## Implementation Details

### API Contracts

**Config**

```
sq config set pipeline.max_cost_usd 20
sq config get pipeline.max_cost_usd     # None when unset = no cap
```

**Dispatch metadata (SDK dispatch)**: new key `background_shells_running: int`. Existing `background_tasks_waited`/`_stopped` keep their meaning (agents).

**FailureKind**: new member `COST_CAP = "cost_cap"`. `replay/outcome.py` maps it in `_CLASS_OF_KIND` to a new `FailureClass.COST_CAP`. That mapping is required: the reader indexes the dict, so an unmapped kind raises `KeyError`. The BLOCKED pause sets no kind, because it pauses rather than fails.

## Integration Points

### Provides to Other Slices

- `RunSpend` gives any later spend reporting (run status, `sq stats`) a per-run total without re-summing.
- `slice_task_paths()` and `parse_blocked_markers()` let any step read task-file state.
- The `BLOCKED:` convention gives agents and pipelines a machine-readable PM hand-off.
- POST_ACTION contract change: an event action may return a failing result with `awaits_human=True` to pause the run (D7).

### Consumes from Other Slices

- Slice 175 usage records. If an action stamps no usage, it adds nothing and the cap can't see it. Every LLM action is required to stamp (`require_capture`), so the only gap is a provider that reports no cost, and that is surfaced by the D4 WARNING.
- cf `resolve_slice_info`. A cf error in the BLOCKED check fails the step closed with the cf error text, the same as the merge guard.
- context-forge#121 for #240 (deferred, not consumed here).

## Success Criteria

### Functional Requirements

- Every non-judge review's system prompt contains the no-invented-gates criterion. Judge prompts are unchanged.
- `CLAUDE.md` contains the gate rule and the `BLOCKED:` convention.
- With `pipeline.max_cost_usd` set, a run whose summed known spend exceeds the cap fails at the action that crossed it. The error states spend and cap, with failure kind `cost_cap`. The replay reader classifies the failure as `cost_cap`. Overshoot stays within the D5 bound, and the docs state the bound and the per-invocation count.
- An action with no reported cost logs one WARNING per alias per run and doesn't stop the run.
- No cap configured: run behavior is unchanged.
- An implement dispatch that leaves a `BLOCKED:` marker in the slice's task files pauses the run at `implement`, prints each marker's text, and runs no later step. This includes when the agent made no commits.
- Resuming the paused run re-dispatches implement.
- Marker parsing accepts the real amoeba format (`> BLOCKED: no judge-template review artifact ... PM asked`), list-item, bold, and plain forms, and rejects lowercase prose "blocked".
- Probe results for D10 (1)–(5) are recorded in this design and on #234, and D11 is amended with the wait mechanism before the wait task starts.
- A dispatch that returns with a background shell running logs WARNING and sets `background_shells_running`. A dispatch whose turn ends while a shell runs waits for it, bounded by `pipeline.background_idle_timeout_s`, by the mechanism D11 records from the probe (unless the probe records shells as unreachable, in which case neither ships).
- An SDK session dispatch whose background agent's notice arrives mid-turn waits for that agent's follow-up turn and returns its text (#239). With no session-state frames, dispatch behavior is unchanged.

### Technical Requirements

- `ruff format`, `ruff check`, `pyright` zero errors. The pipeline, events, review and config test suites pass.
- Unit tests: `read_cost_cap` validation; `RunSpend` add/unknown handling; the post-action cap failure in the executor (fake actions with stamped usage), including a `fan_out` step sharing one `RunSpend`; the replay reader on a `cost_cap` failure; a user-style POST_ACTION action returning `awaits_human=True` pauses the run; `parse_blocked_markers` against a fixture copied from the real amoeba task file text; the `blocked-tasks` guard conditions, ordering before `dispatch-branch-work`, and `awaits_human` propagation to `PAUSED`; ledger shell tracking and the WARNING on running shells; wait tests covering the D11 failure modes.
- The failure modes each have an observable signal and a test: cap exceeded (error + kind), unknown cost (WARNING), malformed usage (ERROR), invalid cap config (error at start), BLOCKED (WARNING + pause), unreadable task file (failure), shell timeout (WARNING), shell left running (WARNING).
- The config key description and `docs/PIPELINES.md` cover `pipeline.max_cost_usd`; `docs/EVENTS.md` lists `squadron.blocked-tasks` and the `awaits_human` pause. CHANGELOG gets user-facing bullets for the cap, the BLOCKED pause, and the shell wait.

### Integration Requirements

- `P56` and `P6` runs need no YAML change. The BLOCKED check and shell wait apply by default, and the cap applies when configured.
- `events.yaml` `disable: [squadron.blocked-tasks]` turns the check off, the same as every built-in.

### Verification Walkthrough

Run live on 20261018 in a scratch project (`~/source/repos/manta/temp/scratch-947`: `cf init --lite`, slice 108 copied from the slice 945 scratch, the AI project guide copied in), with `haiku` for every model. `sq run` works from inside a Claude Code session. Findings that changed the code are listed after the steps.

1. **No-invented-gates criterion.** `sq review tasks 108 --model haiku -vvv` (the system prompt prints at `-vvv`; `-vv` does not show it). The prompt contains `## Process Steps Are Not Findings` and `Approval steps, confirmation gates, and added caution are never valid findings.` There is no CLI entry for a judge template, so the absent half was checked on the assembly point itself: `assemble_system_prompt` gives `tasks: is_judge=False contains_criterion=True` and `judge-tasks-vs-slice: is_judge=True contains_criterion=False`.
2. **Cost cap, config.** `sq config set pipeline.max_cost_usd 0.01 --project`, then `sq run P5 108 -m haiku -p review-model=haiku -p summary-model=haiku -v`: the first dispatch ran, then `Error: run spent $0.16 this invocation, over pipeline.max_cost_usd $0.01; raise the cap and resume to continue`, exit 1. `sq run --status latest` shows `Status: failed`, and the run state holds `"failure_kind": "cost_cap"`.
3. **Resume.** `sq config set pipeline.max_cost_usd 20 --project`, then `sq run --resume run-20261018-p5-53c9e928 -v`: `Pipeline 'p5' — completed` (`tasks-0: completed (CONCERNS)`, `loop-1`, `summary-2`), exit 0, counting from $0.
4. **BLOCKED pause.** Task 0 of the scratch tasks file tells the agent to write a `BLOCKED:` line and stop. In two live runs where the agent chose, it wrote `**BLOCKED:** …` itself once and asked in prose once (`dispatch-branch-work` caught that, as before), so the run recorded below seeds the line in the file (the check reads files, not the agent). `sq run P6 108 -m haiku …` printed `squadron.blocked-tasks: failed … 1 blocked task(s) need the Project Manager: <text>. Resolve them, remove the BLOCKED lines, then resume: sq run --resume run-20261018-p6-1b71dfb0` and `Pipeline 'p6' — paused`, `Steps: 2` (`branch-0: completed`, `implement-1: paused`); no close-out, review or devlog ran. The task's own instruction line, which mentions `BLOCKED:` mid-sentence, did not match. The PM deleted the line, checked the task, and committed on the slice branch; `sq run --resume run-20261018-p6-1b71dfb0 -v` logged `implement: step implement-1 is resuming a hand-off pause; dispatching again` and ran the dispatch (action 4/7). The review after it failed with `code review resolved diff … to no changed files`, because the scratch repo has no code scaffold and the haiku agent wrote nothing; that is the scratch project, not the pause.
5. **Background shell.** A one-step pipeline asks the agent for `python3 -c "import time; time.sleep(40)"` with the Bash `timeout` at 5000. Log: `dispatch: turn ended with session state 'running', 0 background agent(s) and 1 background shell(s) running; waiting: python3 -c "import time; time.sleep(40); …"`; the run took 51 s, `completed`. With `time.sleep(100000)` and `pipeline.background_idle_timeout_s 15`: `dispatch ended with 1 background shell(s) running: python3 -c "import time; time.sleep(100000); …" (no activity for 15s; stopped)`, 26 s, `completed`, and `ps` finds no process. Because the session also closes at the end of the run, `stop_task` was checked on its own against a connected session: `task_updated killed`, `task_notification stopped`, and the sleeper processes went from 2 to 0 before disconnect.

Found by the walkthrough and fixed:

- Resume after a BLOCKED pause skipped `implement` under `existing: keep` once the branch had any commit (D8, amended above).
- A normal dispatch logged `waiting:` with nothing listed at INFO, because `running` briefly follows every result; it is now DEBUG unless an agent or shell is held.
- This design's step 1 named `-vv`; the prompt prints at `-vvv`.

## Risk Assessment

### Technical Risks

- #234's real cause isn't confirmed. The SDK's own comment says shell completion doesn't run a follow-up turn, which conflicts with #199's docstring.

### Mitigation Strategies

- D10 makes the probe the first task, and D11 commits only to reporting and the bounded wait until the probe's results are recorded. Squadron only acts on recorded evidence; if no shell can be backgrounded, nothing shell-specific ships.

## Implementation Notes

### Development Approach

Suggested order (Effort 3/5):

0. D12 dispatch end on `idle` (#239).
1. D10 probe (evidence only; record results), run over the D12 code.
2. D1 criterion + D2 `CLAUDE.md` (small, independent).
3. D3–D6 cost cap: config key → `run_spend.py` → executor threading and check → replay mapping.
4. D7–D8 BLOCKED: `slice_task_paths` extraction (merge guard unchanged in behavior; existing tests pass) → `parse_blocked_markers` → action + binding → `awaits_human` copy → resume test.
5. D11 shell reporting, then the wait as amended from the probe.
6. Docs, CHANGELOG, walkthrough.

Each part is independently committable. Parts 2–4 don't depend on the probe.

### Special Considerations

- The criterion text in D1 and the `CLAUDE.md` rule must not contain example values near a fill-in slot (project hallucination-trap rule). Both are plain prohibitions.
- The cap key name and the BLOCKED marker word are each defined once (`run_spend.py`, `pr/tasks.py`) and referenced everywhere. No scattered literals.
