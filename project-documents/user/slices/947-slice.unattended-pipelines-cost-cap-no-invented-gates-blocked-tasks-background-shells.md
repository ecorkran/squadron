---
docType: slice-design
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261017
dateUpdated: 20261018
status: not_started
turns: 74
promptTokens: 5716339
cachedTokens: 5568743
cacheWriteTokens: 147468
completionTokens: 49072
durationSeconds: 634.4
costUsd: 3.278034
usageRounds: 2
pricedRounds: 2
revision_number: 1
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
3. A `max_cost_usd` run cap: a top-level pipeline YAML field and a `pipeline.max_cost_usd` config key. The executor sums each run's spend, checks it before the run and after every action, and persists it for resume (D3–D6).
4. A built-in POST_ACTION action `squadron.blocked-tasks`. When an implement dispatch leaves a `BLOCKED:` marker in the slice's task files, it pauses the run and prints the marker text. Resuming re-runs the implement step (D7, D8).
5. Background shells in the SDK dispatch: an evidence probe first, then end-of-turn reporting of running shells, and a wait for shells bounded by the existing background idle timeout. The wait mechanism is written into D11 from the probe's results (D10, D11).

**Excluded**

- The task-breakdown guide change from #235 item 2. It already shipped with [ai-project-guide#44](https://github.com/ecorkran/ai-project-guide/issues/44) (`guide.ai-project.005-task-breakdown.md` line 155: "No task may wait on a Project Manager decision…").
- The pre-implement pending-decision check from the #223 comment. It is blocked on [context-forge#121](https://github.com/ecorkran/context-forge/issues/121) and filed as [#240](https://github.com/ecorkran/squadron/issues/240) (D9).
- The misleading code-review PASS on a slice with open items (#223, second bullet). The pause now stops the run before that review happens; review-content changes stay out of scope.
- `--prompt-only` runs. The outer agent does the dispatching there, so squadron sees no spend and enforces no cap.
- A `--max-cost` CLI flag. Config and pipeline YAML cover per-project and per-pipeline caps, and they apply the same way to CLI, MCP and slash-command runs because the executor enforces them.
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
| Run spend ledger | new `pipeline/run_spend.py` | `RunSpend`, `resolve_cost_cap()` |
| Cap resolution | `pipeline/schema.py`, `models.py`, `config/keys.py` | `max_cost_usd` YAML field, `pipeline.max_cost_usd` key |
| Cap enforcement | `pipeline/executor.py` | Pre-run check, post-action check in `_execute_step_once` |
| Spend persistence | `pipeline/state.py` | `RunState.spent_usd` |
| BLOCKED check | new `events/builtin/blocked_tasks.py` | `squadron.blocked-tasks` POST_ACTION action |
| Task-file reading | `pipeline/branch_ops.py` | Extract `slice_task_paths()` shared by merge guard and BLOCKED check |
| Event outcome copy | `pipeline/executor.py` | Copy `awaits_human` from a failing event outcome |
| Shell tracking | `pipeline/sdk_turns.py`, `sdk_session.py` | Report running shells; wait per D11 |

### Data Flow

**Cost cap**

```
execute_pipeline start
  cap = resolve_cost_cap(definition, cwd)              # float | None
  spend = RunSpend(seed=run_state.spent_usd)           # resume; None → 0.0 + WARNING if cap set
  if cap and spend.known_usd >= cap: fail run before any step (COST_CAP)
  for each action in _execute_step_once:
      result = action.execute(ctx); POST_ACTION events run (usage already stamped)
      spend.add(result.metadata.get(USAGE_KEY))         # unknown cost → WARNING, counted
      if cap and spend.known_usd > cap: fail action (FailureKind.COST_CAP) → step FAILED → run FAILED
  observer.step_completed → state records step + spent_usd
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

- `RunSpend` is in-memory, one per `execute_pipeline` call, created next to the existing per-run `UsageCapture`. Parallel `each`/`fan_out` branches share the one event loop, so additions don't race.
- `RunState` gains `spent_usd: float | None = None`. `None` marks a state file written before this slice; older files load unchanged. It's written with every step record, so a resumed run continues from the persisted total. A crash mid-step loses the spend of the step in progress (bound in D5).
- The BLOCKED check is stateless. The marker lives in the task file, and the PM (or the agent, once the task is done) removes it. A marker left in place pauses the run again on the next implement, which is correct.
- Shell tracking is per dispatch, like the agent ledger.

## Technical Decisions

### D1 — No-invented-gates criterion is one shared constant, non-judge templates only
Status: decided
- A constant `NO_INVENTED_GATES_CRITERION` in `review_client.py` is appended to the system prompt after `_STRUCTURED_OUTPUT_INSTRUCTIONS` when `not template.is_judge`. Text, in substance: "Approval steps, confirmation gates, and added caution are never valid findings. LLM spend, pipeline runs, and live tests are pre-authorized; spend is bounded by the run's enforced cost cap. Do not ask for a step that waits on Project Manager confirmation unless a rule you were given names it as required."
- Every non-judge review (built-in `arch`, `slice`, `tasks`, `code`, plus user templates) goes through this one assembly point, so the rule is stated once and can't drift between YAML files.
- Judges (`judge-*`) are excluded. Their prompts are calibrated by initiative 320, and a prompt change shifts scores against existing baselines. Judges score fit against criteria and don't propose process steps.
- Rejected: copying the bullet into the five non-judge YAMLs (duplicates the rule, and user templates miss it).

### D2 — CLAUDE.md rule and BLOCKED convention; upstream via issue
Status: decided
- Add to squadron `CLAUDE.md` Core Principles: "A step in any artifact that waits on Project Manager confirmation, approval, or added caution is invalid unless a named rule requires it; ignore it. LLM spend, pipeline runs, and live tests are pre-authorized. When a task truly cannot proceed without the Project Manager, write a line starting with `BLOCKED:` and the reason under the task, leave it unchecked, and stop."
- `CLAUDE.md` is derived from ai-project-guide `rules/general.md`, so the durable fix is upstream ([ai-project-guide#45](https://github.com/ecorkran/ai-project-guide/issues/45)). This slice changes only squadron's copy and does not edit the vendored guide.
- The BLOCKED convention formalizes what agents already write (`> BLOCKED: …` in amoeba slice 107), so D7 matches real output.

### D3 — Cap sources: pipeline YAML and project config, lowest wins
Status: decided
- Pipeline YAML: optional top-level `max_cost_usd: <number>` on `PipelineSchema` → `PipelineDefinition.max_cost_usd: float | None`. It must be > 0 (pydantic validator), so a bad value fails at load.
- Config: `pipeline.max_cost_usd`, `type_=float`, `default=None` (no cap).
- One plain function, `resolve_cost_cap(definition, cwd) -> float | None` in `run_spend.py`, reads both. It raises `ValueError` when the config value is set but isn't a positive number, and returns the lower of the set values. A cap is a ceiling, and a pipeline file must not loosen a project ceiling. No source-tracking type: the cap error prints both candidate values (D5).
- Neither set means no cap. That's explicit, documented in the key description, and not a fallback value.

### D4 — Spend is summed from stamped usage records in the executor
Status: decided
- `RunSpend.add(raw_usage)` parses `ActionResult.metadata[USAGE_KEY]` itself through `UsageRecord.from_dict`, so there is no separate helper. It runs after POST_ACTION events, at the single action site `_execute_step_once`. Every LLM action (dispatch, review, summary, compact, loop rounds, each/fan-out items) passes through it.
- Rejected: accumulating inside `UsageCapture`. Review records are built by `record_from_review` outside `_build`, so two paths would need hooking, and live spend would come from a different source than resume spend.
- A record with `cost_usd is None` adds nothing and logs WARNING once per alias per run: "step X (alias Y) reported no cost; the run's spend is a lower bound". The cap compares known spend. Failing on unknown cost would stop every run on an unpriced alias, which contradicts the slice goal; the WARNING keeps it observable.
- A malformed usage record raises `ValueError` from `from_dict`. It's logged at ERROR and adds nothing, so it doesn't crash the run (the same posture `usage-stamp` takes).

### D5 — Cap exceeded fails the run; checked before the run and after each action
Status: decided
- After each action: if `known_usd > cap`, the action result becomes `success=False`, with `metadata[FAILURE_KIND_KEY] = FailureKind.COST_CAP` (new member). The error is `"run spent $X.XX, over max_cost_usd $Y.YY (pipeline max_cost_usd: <value or unset>, config pipeline.max_cost_usd: <value or unset>); raise the cap and resume to continue"`. The step fails and the run fails. This is an error, not a pause (#235: "stops the run with an explicit error").
- Before the first step (fresh or resumed): if seeded `known_usd >= cap`, the run fails without dispatching. Without this check, a resume under an unchanged cap would spend one more dispatch before stopping.
- The cap is best-effort, with these bounds stated in `docs/PIPELINES.md` and the config key description:
  - **Overshoot:** at most the cost of the actions in flight when the cap is crossed. `each` runs items serially, so outside `fan_out` that's one action. A `fan_out` step runs its branches concurrently (`asyncio.gather`), so it adds at most one action per branch, up to the step's branch count. Each branch stops at its own next check. The error's "spent $X" reports the real total.
  - **Crash loss:** spend of the step in progress when the process dies isn't persisted. A resume undercounts by at most that one step (one `fan_out` step's branches when it's a `fan_out` step).
  - **Unknown cost:** actions with no reported cost aren't counted (D4 WARNING).

### D6 — Spend persisted on RunState for resume
Status: decided
- `RunState.spent_usd` is written with each step record (`record_step_completed` gains the value from the executor via the observer). On resume, `RunSpend` is seeded from it.
- A resumed state file with `spent_usd is None` (written before this slice) seeds 0.0. When a cap is active, it also logs WARNING: "run <id> has no recorded spend from before this resume; the cost cap counts only spend from here on".
- Rejected: re-summing every persisted action dict on resume. Each-item results aren't all held in `completed_steps`, so the sum would undercount silently.

### D7 — `squadron.blocked-tasks` POST_ACTION action, bound before branch-work
Status: decided
- New `events/builtin/blocked_tasks.py`, registered and added to `DEFAULT_BINDINGS` **before** `squadron.dispatch-branch-work`. A blocked agent often commits nothing, and the PM hand-off has to win over the "no commits" failure (the first failing outcome wins).
- It applies when `action_type == dispatch`, `step_type == StepTypeName.IMPLEMENT`, the result succeeded, a `slice` param is present, and the result isn't `SKIPPED_KEY`. That's the same guard shape as `dispatch-branch-work`.
- Task files: extract `slice_task_paths(cf_client, slice_index, cwd) -> list[Path]` from the merge guard in `branch_ops.py`. Both the guard and this check call it.
- Marker parsing is a new `parse_blocked_markers(text) -> tuple[str, ...]` in `pr/tasks.py`, next to `parse_task_items`. It's lenient: strip leading whitespace, any number of `>` blockquote marks, a list bullet (`-*+`) with an optional checkbox, and `*`/`_` emphasis. The line then matches if it starts with the uppercase word `BLOCKED`, followed by `:`, `—`, `-`, or whitespace. Matching is case-sensitive so prose like "blocked by" doesn't match. The returned text is the line after the marker.
- On markers: `ActionResult(success=False, awaits_human=True, error=f"{n} blocked task(s) need the Project Manager: {first markers}. Resolve them, remove the BLOCKED lines, then resume: sq run --resume {run_id}")`, logged at WARNING. The executor's event-outcome loop now copies `awaits_human` along with `success`/`error`/failure kind (one line). That turns the step into `PAUSED`.
- Unreadable task file: fails closed as a plain failure (not paused), naming the path. That matches the merge guard's `OTHER`.

### D8 — Resume re-runs the implement step through existing resume logic
Status: decided
- A paused run resumes at its paused step (`first_unfinished_step_of`), and the paused step is the phase-6 `implement` step, so the dispatch runs again. No new resume code. A test pins the behavior: pause on BLOCKED, remove the marker, resume, and implement is re-dispatched.

### D9 — Pre-implement pending-decision check is deferred
Status: decided
- The check belongs to cf ([context-forge#121](https://github.com/ecorkran/context-forge/issues/121), open), and squadron doesn't parse decision status itself, because gating lives in cf. Filed as [#240](https://github.com/ecorkran/squadron/issues/240). #223 closes with this slice. #240 tracks the remainder.

### D10 — Background shells: evidence probe first
Status: decided
- The #234 run happened after the #199 deny hook shipped, and the issue notes that backgrounding wasn't confirmed from logs. Following the project's debugging rule, Task 1 is a probe against the real SDK/CLI (live runs are pre-authorized). It records, in the slice design and the issue:
  1. the `task_type` string the CLI emits for a backgrounded shell. This becomes the constant `SHELL_TASK_TYPE` in `sdk_turns.py`; the SDK doesn't name it.
  2. whether a shell can be backgrounded in a pipeline session despite the deny hook (for example, a long foreground command moved to the background), and how.
  3. whether a shell's terminal status leads the CLI to inject a continuation turn. The SDK's `DEFERRING_TASK_TYPES` comment says only agent/workflow completion runs a follow-up turn.
  4. whether a running shell emits `TaskProgressMessage` frames.
- If (2) finds no path to a background shell, the slice delivers only the D11 reporting (cheap observability). The waiting and continuation part is then recorded as not needed, with the probe output as evidence.

### D11 — Report running shells now; write the wait mechanism from the probe
Status: decided
- Committed now: `BackgroundLedger` records shell starts and terminal frames (`SHELL_TASK_TYPE` from probe 1). When a dispatch returns with a shell still running, it logs WARNING ("dispatch ended with N background shell(s) running: <descriptions>") and sets `background_shells_running: int` in dispatch metadata, the way `background_tasks_waited` reaches it today.
- Committed now: the dispatch waits for shells, bounded by `pipeline.background_idle_timeout_s` (the slice plan's requirement). A shell stopped at that bound logs WARNING.
- Written after the probe: how the wait resumes the agent, depending on probe 3 (injected turn, or squadron sends one), and whether shell progress frames count as activity, depending on probe 4. The probe task amends this D11 with the mechanism and its evidence before the wait task starts. If probe 2 finds no path to a background shell, the wait is recorded here as not needed, and only the reporting ships.
- The #199 deny hook stays. It keeps explicit backgrounding in the foreground, where the foreground stall bound applies.

## Implementation Details

### API Contracts

**Pipeline YAML**

```yaml
name: P56
max_cost_usd: 25        # optional; positive number; lower of this and pipeline.max_cost_usd applies
steps: [...]
```

**Config**

```
sq config set pipeline.max_cost_usd 20
sq config get pipeline.max_cost_usd     # None when unset = no cap
```

**Dispatch metadata (SDK dispatch)**: new key `background_shells_running: int`. Existing `background_tasks_waited`/`_stopped` keep their meaning (agents).

**FailureKind**: new members `COST_CAP = "cost_cap"` and `BLOCKED_TASK = "blocked_task"`. Both are read by the replay outcome reader without matching on error text.

### Database / Storage Schema

`RunState` (run state JSON) gains `spent_usd: float | None` (default `None`, meaning written before this slice). Older files load unchanged. No schema-version bump: an additive field with a default, same as `score` in slice 300.

## Integration Points

### Provides to Other Slices

- `RunSpend` gives any later spend reporting (run status, `sq stats`) a per-run total without re-summing.
- `slice_task_paths()` and `parse_blocked_markers()` let any step read task-file state.
- The `BLOCKED:` convention gives agents and pipelines a machine-readable PM hand-off.

### Consumes from Other Slices

- Slice 175 usage records. If an action stamps no usage, it adds nothing and the cap can't see it. Every LLM action is required to stamp (`require_capture`), so the only gap is a provider that reports no cost, and that is surfaced by the D4 WARNING.
- cf `resolve_slice_info`. A cf error in the BLOCKED check fails the step closed with the cf error text, the same as the merge guard.
- context-forge#121 for #240 (deferred, not consumed here).

## Success Criteria

### Functional Requirements

- Every non-judge review's system prompt contains the no-invented-gates criterion. Judge prompts are unchanged.
- `CLAUDE.md` contains the gate rule and the `BLOCKED:` convention.
- With `max_cost_usd` set (YAML, config, or both, lowest applying), a run whose summed known spend exceeds the cap fails at the action that crossed it. The error states spend and both candidate cap values, with failure kind `cost_cap`. Overshoot and crash loss stay within the D5 bounds, and the docs state those bounds.
- A resumed run starts from persisted spend. A resume at or over the cap fails before any dispatch. Resuming a pre-slice run (no `spent_usd`) under an active cap logs the D6 WARNING.
- An action with no reported cost logs one WARNING per alias per run and doesn't stop the run.
- No cap configured: run behavior is unchanged.
- An implement dispatch that leaves a `BLOCKED:` marker in the slice's task files pauses the run at `implement`, prints each marker's text, and runs no later step. This includes when the agent made no commits.
- Resuming the paused run re-dispatches implement.
- Marker parsing accepts the real amoeba format (`> BLOCKED: no judge-template review artifact ... PM asked`), list-item, bold, and plain forms, and rejects lowercase prose "blocked".
- Probe results for D10 (1)–(4) are recorded in this design and on #234.
- A dispatch that returns with a background shell running logs WARNING and sets `background_shells_running`. A dispatch whose turn ends while a shell runs waits for it, bounded by `pipeline.background_idle_timeout_s`, by the mechanism D11 records from the probe (unless the probe records the wait as not needed).

### Technical Requirements

- `ruff format`, `ruff check`, `pyright` zero errors. The pipeline, events, review and config test suites pass.
- Unit tests: `resolve_cost_cap` precedence and validation; `RunSpend` add/seed/unknown handling; cap pre-check and post-action failure in the executor (fake actions with stamped usage); `parse_blocked_markers` against a fixture copied from the real amoeba task file text; the `blocked-tasks` guard conditions, ordering before `dispatch-branch-work`, and `awaits_human` propagation to `PAUSED`; ledger shell tracking and the WARNING on running shells; wait tests as D11 specifies after the probe.
- The failure modes each have an observable signal and a test: cap exceeded (error + kind), unknown cost (WARNING), malformed usage (ERROR), resume without recorded spend under a cap (WARNING), BLOCKED (WARNING + pause), unreadable task file (failure), shell timeout (WARNING), shell left running (WARNING).
- The config key description and `docs/PIPELINES.md` cover `max_cost_usd`; `docs/EVENTS.md` lists `squadron.blocked-tasks`. CHANGELOG gets user-facing bullets for the cap, the BLOCKED pause, and the shell wait.

### Integration Requirements

- `P56` and `P6` runs need no YAML change. The BLOCKED check and shell wait apply by default, and the cap applies when configured.
- `events.yaml` `disable: [squadron.blocked-tasks]` turns the check off, the same as every built-in.

### Verification Walkthrough

Draft. Refined after Phase 6. Use a scratch slice (as in slice 178's walkthrough) so real slices are untouched.

1. **No-invented-gates criterion.** `sq review tasks <scratch-slice> --model <alias> -vv` prints the system prompt, which contains "Approval steps, confirmation gates, and added caution are never valid findings". Running the same command with a `judge-tasks-vs-slice` template shows the criterion absent.
2. **Cost cap, config.** `sq config set pipeline.max_cost_usd 0.01`, then `sq run P5 <scratch-slice> -v`. The run fails after the first LLM action with `run spent $0.0X, over max_cost_usd $0.01 (pipeline max_cost_usd: unset, config pipeline.max_cost_usd: 0.01); raise the cap and resume to continue`. `sq run --status latest` shows failed, and the run state JSON shows `spent_usd`.
3. **Resume pre-check.** `sq run --resume <run-id>` with the cap unchanged fails immediately, with no dispatch logged. `sq config set pipeline.max_cost_usd 20` then `sq run --resume <run-id>`, and the run continues.
4. **Lowest cap wins.** Copy P5 to a user pipeline with `max_cost_usd: 0.01`, keep config at 20, and run it. The run stops at $0.01, and the error shows both values.
5. **BLOCKED pause.** On the scratch slice, add a task "Ask the PM for X; write `BLOCKED:` if you cannot proceed" (a deliberate test of the marker). `sq run P6 <scratch-slice> -v` pauses at `implement`, prints the marker text, and runs no `close-out`, review or devlog. Remove the line, resolve the task, and run `sq run --resume <run-id>`. Implement re-dispatches.
6. **Background shell.** Run the Task 1 probe script (it lands under `tests/probes/` or the existing live-test location; Task 1 decides). It reproduces the backgrounding path the probe found. The dispatch waits for the shell and continues as D11 records. A forever shell (`sleep 100000` via the same path) with `pipeline.background_idle_timeout_s` set low is stopped with a WARNING.
7. If the probe found no backgrounding path (D10), step 6 is replaced by a unit-level check of the end-of-turn WARNING and `background_shells_running`, and the walkthrough records the probe output.

## Risk Assessment

### Technical Risks

- #234's real cause isn't confirmed. The SDK's own comment says shell completion doesn't run a follow-up turn, which conflicts with #199's docstring.

### Mitigation Strategies

- D10 makes the probe the first task, and D11 commits only to reporting and the bounded wait until the probe's results are recorded. Squadron only acts on recorded evidence, and the reporting part is useful whatever the probe finds.

## Implementation Notes

### Development Approach

Suggested order (Effort 3/5):

1. D10 probe (evidence only; record results).
2. D1 criterion + D2 `CLAUDE.md` (small, independent).
3. D3–D6 cost cap: config/schema → `run_spend.py` → executor checks → state persistence.
4. D7–D8 BLOCKED: `slice_task_paths` extraction (merge guard unchanged in behavior; existing tests pass) → `parse_blocked_markers` → action + binding → `awaits_human` copy → resume test.
5. D11 shell reporting, then the wait as amended from the probe.
6. Docs, CHANGELOG, walkthrough.

Each part is independently committable. Parts 2–4 don't depend on the probe.

### Special Considerations

- The criterion text in D1 and the `CLAUDE.md` rule must not contain example values near a fill-in slot (project hallucination-trap rule). Both are plain prohibitions.
- The cap key name and the BLOCKED marker word are each defined once (`run_spend.py`, `pr/tasks.py`) and referenced everywhere. No scattered literals.
