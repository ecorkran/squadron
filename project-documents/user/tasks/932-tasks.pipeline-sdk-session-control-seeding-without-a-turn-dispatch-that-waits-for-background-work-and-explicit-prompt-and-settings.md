---
docType: tasks
slice: pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings
project: squadron
lld: user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Design complete and reviewed twice (CONCERNS addressed). No code changes yet.
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Tasks: Pipeline SDK Session Control

## Context Summary

This file covers five parts, in delivery order. Each part ends with its own commit.

- **Setup**
- **Part A**: seeding without a turn (#162)
- **Part B**: dispatch waits for background agents, plus the flag tail (#163)
- **Part D**: explicit settings (#156, settings half)
- **Part C**: explicit system prompt (#155) and recording (#156, recording half)
- **Close-out**

The design is [932-slice…md](../slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md). Read D1–D13 before starting. These are the key points:

- **D1**: a seed never becomes a turn. The fresh client gets `system_prompt={"type": "preset", "preset": "claude_code", "append": <framed seed>}`, and no `query()` is sent to it.
- **D3**: `seed_context(text)` rotates to a fresh session, and the caller passes raw text.
- **D5 / D6**: dispatch waits for `local_agent`/`local_workflow` tasks, and only its own result can end it. An injected turn that arrives first is leftover text from the previous step and is dropped. The wait has an idle bound, `pipeline.background_idle_timeout_s`.
- **D9 / D10**: with no `--setting-sources` flag, the CLI loads the user and project CLAUDE.md. Policy: `[project]` for reviews, judges, pipeline sessions, and dispatch. PR review, PR composer, and summary one-shot keep `[]`. None of these may ever be `None`.
- **D11**: `AgentConfig.auto_memory: bool = False`. Only the pipeline session and one-shot dispatch set it, from `pipeline.auto_memory` (default true). This also turns auto-memory off for `sq serve` agents and the auth probe, which is intended: any path that doesn't opt in gets memory off.
- **D12**: `SystemPromptMode` and `describe_system_prompt(config)` sit next to the prompt table in `core/models.py`. The Run Digest gets two always-on lines, and JSON output gets the same keys.
- **D13**: every failure mode has an observable signal. Each test asserts that signal, not only the return value.

**Found during breakdown:** `config/manager.py::_coerce_value` supports only `int` and `str`. `pipeline.auto_memory` needs bool support first (task D1).

**Names added by this task list** (not in the design):
- `SeedSource` StrEnum, used in the seeding log line.
- `pipeline/text_tail.py::tail_text`, the one definition of the 400-character tail, shared by the leftover-turn warning and the flag.
- `session.seeded`, used for the prompt-mode metadata.
- The `source: SeedSource` parameter on `seed_context`.
- The `base_env` parameter on `sdk_settings_options`.

E2 folds all of these back into the design's API Contracts.

**Commit cadence:** one commit after each implementation+test pair (the `Commit:` line in each `-T` task). Each part ends with a checkpoint task that runs format, lint, pyright, and the full suite.

SDK facts, checked against claude-agent-sdk 0.2.160:

- `TaskStartedMessage`, `TaskNotificationMessage`, `TaskUpdatedMessage`, and `TERMINAL_TASK_STATUSES` are importable from `claude_agent_sdk`.
- `ResultMessage.origin` is `None` or `{"kind": "human"}` for our own prompt, and `{"kind": "task-notification"}` for an injected turn.
- `ClaudeAgentOptions` is a dataclass.
- `client.stop_task(id)` is bounded at 60s and raises a bare `Exception`.

**Current project state:** design only. Effort for the whole slice is 3/5.

---

## Setup

- [ ] **T0.1 — Create the slice branch**
  - [ ] Run `cf config get git.integration_branch`. It is empty, so the target is `main`.
  - [ ] `git checkout -b 932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings main`
  - [ ] SC: `git branch --show-current` prints that name.

- [ ] **T0.2 — Baseline suite**
  - [ ] Run `uv run pytest -q` and record the pass/fail counts here.
  - [ ] SC: any failure that already exists is noted by test id. This slice's tasks do not fix them.

---

## Part A — Seeding without a turn (#162)

- [ ] **A1 — Seed framing and seeded-options helper** (`pipeline/sdk_session.py`) — Effort 1
  - [ ] Rewrite `_SEED_FRAMING_PREFIX` for its new place in the system prompt (D1). It must say three things: this is a summary of earlier work in this pipeline run, it is reference material and not a task, and it is not an instruction to act. Remove "wait for the next user instruction" and "do NOT acknowledge", which only made sense for a turn.
  - [ ] Add `_seeded_options(base: ClaudeAgentOptions, seed: str | None) -> ClaudeAgentOptions`.
    - `None` → return `base` unchanged.
    - Otherwise → `dataclasses.replace(base, system_prompt=<preset dict>)`, with `append` set to `frame_summary_for_seed(seed)`.
    - If `base.system_prompt` already has an `append`, the result is `existing + "\n\n" + framed seed`.
    - `base` is never mutated.
  - [ ] SC: the function is ≤ 20 lines, and pyright strict is clean.

- [ ] **A1-T — Tests for A1** (`tests/pipeline/test_sdk_session.py`)
  - [ ] `None` seed returns an options object equal to `base`.
  - [ ] A seed produces a preset with `append` starting with the new framing prefix and ending with the seed text.
  - [ ] An existing `append` is kept first, with the seed after a blank line.
  - [ ] `base.system_prompt` is unchanged after the call (not mutated).
  - [ ] SC: `uv run pytest tests/pipeline/test_sdk_session.py -q` passes.
  - [ ] Commit: `feat: add system-prompt seed framing and seeded-options helper`

- [ ] **A2 — `open_pipeline_session` builder** — Effort 2
  - [ ] In `sdk_session.py`, rename the dataclass field `options` → `base_options` and update every reference (`grep -rn "\.options\b" src/squadron/pipeline`).
  - [ ] Add `async def open_pipeline_session(*, seed: str | None = None) -> SDKExecutionSession`. It builds the base options (`cwd=str(Path.cwd())`, `permission_mode="bypassPermissions"`, preset system prompt), builds the client from `_seeded_options(base, seed)`, connects, and returns the session. Settings arrive in task D4. Do not add them here.
  - [ ] Replace the literal options in `cli/commands/run.py:357` and `pipeline/executor.py:648` (`_connect_lazy_session`) with calls to the builder. Keep `_connect_lazy_session`'s `logger.exception` + re-raise on failure.
  - [ ] SC: `grep -rn "ClaudeAgentOptions(" src/squadron/cli/commands/run.py src/squadron/pipeline/executor.py` returns nothing.

- [ ] **A2-T — Tests for A2**
  - [ ] Update `tests/pipeline/test_sdk_wiring.py`, `tests/cli/commands/test_run_pipeline_sdk.py`, and `tests/cli/commands/test_run_pipeline_lazy.py` wherever they patch `ClaudeAgentOptions`/`ClaudeSDKClient` construction in run.py/executor.py, so they patch the builder's module instead.
  - [ ] Update every test that reads `session.options` to use `session.base_options` (`grep -rn "\.options\b" tests/pipeline tests/cli`).
  - [ ] New test: `open_pipeline_session(seed="S")` constructs the client with options whose `system_prompt["append"]` contains `S`, and it calls `connect` once.
  - [ ] SC: the wiring and run-pipeline test files pass.
  - [ ] Commit: `refactor: build pipeline sessions through open_pipeline_session`

- [ ] **A3 — Rotation via `_reconnect`** (`sdk_session.py`) — Effort 2
  - [ ] Add `SeedSource(StrEnum)`: `COMPACT="compact"`, `RESUME="resume"`, `RESTORE="restore"`.
  - [ ] Add `async def _reconnect(self, seed: str | None, source: SeedSource) -> None`. It disconnects the current client, builds `ClaudeSDKClient(options=_seeded_options(self.base_options, seed))`, resets `current_model`/`session_id`, and connects. On success it logs at INFO: `seeded fresh session via system prompt (%d chars, source: %s)`. Connect failure handling comes in A3b; let the exception propagate here.
  - [ ] `compact()`: capture the summary as today, then call `await self._reconnect(summary, SeedSource.COMPACT)` in place of disconnect + new client + `dispatch(frame…)`. Keep the `restore_model` handling.
  - [ ] `seed_context(text, source: SeedSource)`: `await self._reconnect(text, source)`. The docstring states D3: it replaces the session.
  - [ ] SC: `compact()` and `seed_context()` contain no call to `dispatch`/`query` on the new client.

- [ ] **A3-T — Tests for A3, plus the rewrites A3 breaks**
  - [ ] `tests/pipeline/test_sdk_session.py` (fake client factory):
    - [ ] `compact(summary="X")`: the old client is disconnected, and the new client is built with `append` containing `X`. **The new client's `query` is never called.** The return value is `"X"`.
    - [ ] `compact(instructions="I")` with no summary: the capture goes through the *old* client, and the new client gets the captured text as its seed.
    - [ ] `seed_context("Y", SeedSource.RESTORE)`: rotates, the new client's options carry `Y`, there is no `query`, and an INFO record names `restore`.
  - [ ] Rewrite the existing tests that asserted seeding went through `dispatch()`/`query`, so they assert on the new client's options and on the absence of `query`. This is the intended behavior change, not a regression. Files:
    - `tests/pipeline/test_compact_integration.py`
    - `tests/pipeline/test_compact_compose_integration.py`
    - `tests/pipeline/test_sdk_session.py`
    - `tests/pipeline/actions/test_dispatch_session.py`
    - any emit-rotate test found with `grep -rln "rotate" tests/pipeline`
  - [ ] SC: `uv run pytest tests/pipeline -q` passes, which confirms nothing in the pipeline tests is left red.
  - [ ] Commit: `fix: seed rotated sessions via system prompt, never a turn`

- [ ] **A3b — `unusable_reason` and the usable-session guard** (`sdk_session.py`) — Effort 1
  - [ ] Add a field `unusable_reason: str | None = None`.
  - [ ] In `_reconnect`, wrap the new client's `connect()`. On failure, set `unusable_reason = f"reconnect failed: {exc}"`, call `logger.exception`, and re-raise.
  - [ ] Add `_require_usable()`, which raises `ProviderError(f"SDK session unusable: {self.unusable_reason}")`. It is the **first statement** of `dispatch()`, `compact()`, and `seed_context()`.
  - [ ] SC: no stream read or query happens before the guard in any of the three methods.

- [ ] **A3b-T — Tests for A3b, including the action-level and batch signals (D13)**
  - [ ] `tests/pipeline/test_sdk_session.py`: `connect` raises on the new client. The first call re-raises, `caplog` has an ERROR record with the exception, and `unusable_reason` is set. The next `dispatch("p")` raises `ProviderError` containing `SDK session unusable`, **without** calling `query`.
  - [ ] Action level (`tests/pipeline/actions/test_compact.py`, `tests/pipeline/actions/test_summary.py`): each of `compact`, `emit: [rotate]`, and `summary restore`, with a session whose reconnect fails, returns `ActionResult(success=False)` whose `error` holds the exception text or `EmitResult(ok=False)`.
  - [ ] Batch level (`tests/pipeline/test_executor_each.py`): an `each` batch with a continue policy and three items. Item 1's rotate fails the reconnect. Items 2 and 3 are FLAGGED with a reason containing `SDK session unusable`, and their dispatch never reaches `query`.
  - [ ] SC: these tests pass.
  - [ ] Commit: `fix: mark a session unusable after a failed reconnect`

- [ ] **A4 — Resume seeding, including the lazy session** (`pipeline/executor.py`) — Effort 2
  - [ ] Around `executor.py:488`, compute `resume_seed: str | None` from `active_compact_summary_for_resume` **regardless of** whether `sdk_session` exists. Keep the `FileNotFoundError` debug path.
  - [ ] If `sdk_session` is connected, call `await sdk_session.seed_context(resume_seed, SeedSource.RESUME)`.
  - [ ] Otherwise keep `resume_seed` and pass it to `_connect_lazy_session(run_id=…, seed=resume_seed)` at the lazy-connect hook. Clear it after use so a later connect never re-seeds.
  - [ ] SC: the lazy hook forwards the seed, and the connected path calls `seed_context`.

- [ ] **A4-T — Tests for A4**
  - [ ] Resume with a connected session: `seed_context` is called once with the summary text.
  - [ ] Resume under a lazy session: `open_pipeline_session` (or `_connect_lazy_session`) receives `seed=<summary>`. **This case fails against today's code.** Confirm that by running it before A4 if convenient.
  - [ ] Resume with no applicable summary: no seed is passed on either path.
  - [ ] Rewrite the existing resume-seeding assertions in `tests/cli/commands/test_run_pipeline.py` and `tests/pipeline/test_sdk_integration.py` that expected `seed_context(text)` with one argument or a seeding `dispatch`.
  - [ ] SC: `uv run pytest tests/cli/commands tests/pipeline -q` passes.
  - [ ] Commit: `fix: seed resumed runs, including lazily connected sessions`

- [ ] **A5 — `summary restore` framing and docs** — Effort 1
  - [ ] `pipeline/actions/summary.py:151-154`: remove the `frame_summary_for_seed` import and call. Pass the raw `summary` and `SeedSource.RESTORE` to `seed_context`.
  - [ ] `pipeline/actions/compact.py` / `pipeline/emit.py`: no change is needed, since they go through `compact()`. Confirm by reading them.
  - [ ] `data/pipelines/example.yaml` (restore comment, around line 119): change "re-inject … into the current session" to say restore **replaces** the session with a fresh one seeded with the summary.
  - [ ] SC: `grep -rn frame_summary_for_seed src/` shows only `sdk_session.py`.

- [ ] **A5-T — Tests for A5** (`tests/pipeline/actions/test_summary.py`, `tests/pipeline/test_summary_integration.py`)
  - [ ] Restore passes the raw summary. The framing prefix appears **exactly once** in the resulting seeded options.
  - [ ] SC: the files pass.
  - [ ] Commit: `fix: frame restored summaries once; restore replaces the session`

- [ ] **A6 — Part A checkpoint**
  - [ ] Run `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest -q`.
  - [ ] SC: all green apart from any baseline failures recorded in T0.2. If anything outside the tasks above is red, fix it here and name it in the commit body.
  - [ ] Commit any formatting fixes: `style: format Part A`. Skip this if there are no changes.

---

## Part B — Dispatch waits for background agents (#163)

- [ ] **B1 — Config key `pipeline.background_idle_timeout_s`** (`config/keys.py`) — Effort 1
  - [ ] `ConfigKey(name="pipeline.background_idle_timeout_s", type_=int, default=1800, description=…)`. The description names what it bounds: silence while a dispatch waits for background agents.
  - [ ] SC: `sq config get pipeline.background_idle_timeout_s` prints `1800 (default)`.

- [ ] **B1-T — Test** (`tests/config/test_keys.py`)
  - [ ] The key exists with type `int` and default `1800`. `set_config` with `"60"` coerces to `60`.
  - [ ] SC: the file passes.
  - [ ] Commit: `feat: add pipeline.background_idle_timeout_s config key`

- [ ] **B2a — Background ledger and own-result helper** (`sdk_session.py`) — Effort 1
  - [ ] Module constant `WAITED_TASK_TYPES: Final = frozenset({"local_agent", "local_workflow"})`, with a one-line comment citing the SDK's `_internal/query.py` `DEFERRING_TASK_TYPES`, which is private and redeclared on purpose.
  - [ ] Add a `_BackgroundLedger` class with:
    - `observe(msg)`: add on `TaskStartedMessage` whose `task_type ∈ WAITED_TASK_TYPES`. Discard on `TaskNotificationMessage`, or on a `TaskUpdatedMessage` whose status is in `TERMINAL_TASK_STATUSES`.
    - `active` (bool), `seen_count` (distinct ids ever tracked), `active_ids()`, and `descriptions()`.
  - [ ] Add `_is_own_result(msg: ResultMessage) -> bool`: `origin is None or origin.get("kind") == "human"`.
  - [ ] SC: both are pure and have no client dependency.

- [ ] **B2a-T — Tests for B2a** (`tests/pipeline/test_sdk_session.py`)
  - [ ] Ledger parametrized cases:
    - `local_agent` start → active.
    - `local_bash` start → not active.
    - Notification clears.
    - `TaskUpdated(killed)` clears.
    - `TaskUpdated(running)` does not clear.
    - A duplicate terminal is idempotent.
  - [ ] `_is_own_result`: `None` → True, `{"kind": "human"}` → True, `{"kind": "task-notification"}` → False.
  - [ ] Commit: `feat: add background-agent ledger for session dispatch`

- [ ] **B2b — Origin-aware completion in `dispatch()`** (`sdk_session.py`) — Effort 3
  - [ ] Restructure the read loop in `dispatch()`. Keep the existing rate-limit retry semantics exactly as they are.
    - After each `ResultMessage`: if it is our own result, set `own_result_seen`.
    - Return when `own_result_seen` and the ledger is empty.
    - Otherwise call `receive_response()` again to read the next turn.
    - On the first result seen with the ledger non-empty, log at INFO once: `dispatch: turn ended with %d background agent(s) running; waiting: %s`.
  - [ ] Set `self.background_tasks_waited = ledger.seen_count`, using a fresh ledger per dispatch.
  - [ ] If `receive_response()` finishes a pass with no `ResultMessage` at all (the iterator ended), raise `ProviderError(f"stream ended before the dispatch's result; {n} background agent(s) still running: {descriptions}")`.
  - [ ] SC: text from the follow-up turn is joined into the returned response. `dispatch()` itself stays readable: extract helpers to keep each function ≈ 50 lines.

- [ ] **B2b-T — Tests for B2b** (`tests/pipeline/test_sdk_session.py`, scripted fake client whose `receive_response()` yields one scripted list per call)
  - [ ] `local_agent` started → own result → (next call) notification + assistant text + injected result → returns with **both** turns' text. `background_tasks_waited == 1`, and there is an INFO record `waiting`.
  - [ ] The terminal signal is only `TaskUpdatedMessage(status="killed")`: the dispatch still completes.
  - [ ] A `local_bash` task started, then own result: returns immediately with `background_tasks_waited == 0`.
  - [ ] No tasks: behavior is identical to today, with one `receive_response()` call.
  - [ ] The stream ends with no result while an agent is tracked: raises `ProviderError` naming the agent's description.
  - [ ] The existing rate-limit retry tests still pass unchanged.
  - [ ] SC: the file passes.
  - [ ] Commit: `fix: wait for background agents before a session dispatch returns`

- [ ] **B3 — Drop leftover injected turns** (`sdk_session.py`) — Effort 2
  - [ ] While `own_result_seen` is false, an injected (non-own) `ResultMessage` means everything read so far in this dispatch belongs to the previous step (D6).
  - [ ] Clear the collected response parts. Log at WARNING: `dispatch: discarded a background follow-up turn left over from the previous dispatch; its final text: "%s"`, filled with `tail_text(discarded)`. `tail_text` adds the leading `…` itself, so do not add another.
  - [ ] `FINAL_TEXT_TAIL_CHARS = 400` and the tail formatter are defined **once**. Put both in a shared module so B6 and this task use the same definition, e.g. `squadron/pipeline/text_tail.py` with `tail_text(text: str) -> str`. `tail_text` collapses whitespace, keeps the last 400 characters, prefixes `…` when it truncated, and returns `(empty response)` for empty input.
  - [ ] SC: the leftover text is absent from the return value.

- [ ] **B3-T — Tests for B3**
  - [ ] Injected assistant text + injected result, then our own assistant text + own result: the return value holds only our text, and a WARNING carries the leftover tail.
  - [ ] Unit tests for `tail_text`: empty input, short input (no `…`), long input (truncated with `…`), and whitespace collapse.
  - [ ] SC: passes.
  - [ ] Commit: `fix: drop leftover background follow-up turns from the next dispatch`

- [ ] **B4 — Idle timeout while waiting** (`sdk_session.py`) — Effort 3
  - [ ] Read `pipeline.background_idle_timeout_s` through `get_typed_config(…, int)` **once per dispatch, only when entering the waiting state**. Take `cwd` from `self.base_options.cwd`.
  - [ ] While waiting (own result seen, ledger non-empty), bound each wait for the next message with `asyncio.timeout(idle_s)`. The timer resets on every message.
  - [ ] On timeout:
    1. For each tracked id, call `await self.client.stop_task(id)` inside `try/except Exception` (`# noqa: BLE001`), with a comment that the SDK raises a bare `Exception` on both a control-request timeout and an error response. Call `logger.exception` naming the id, then continue.
    2. Clear the ledger.
    3. Log a WARNING: `dispatch: no activity for %ds with background agent(s) still running; stopped: %s`.
    4. Set `self.background_tasks_stopped` and return the collected text.
  - [ ] Foreground turns (own result not yet seen) get **no** timer (#165).
  - [ ] SC: `background_tasks_stopped` is 0 on every path except the timeout.

- [ ] **B4-T — Tests for B4**
  - [ ] Patch the config to return `idle_s=0.05`. The fake client goes silent after our own result while one agent is tracked. Assert: `stop_task` is called with the id, there is a WARNING naming it, `background_tasks_stopped == 1`, and the return value holds the text collected so far.
  - [ ] `stop_task` raises for the first of two ids: an ERROR record for id 1, `stop_task` is still called for id 2, and the dispatch returns normally.
  - [ ] A slow foreground turn (a delay before our own result) longer than `idle_s` still completes. No timer applies.
  - [ ] SC: passes. No real sleeps longer than 0.2s.
  - [ ] Commit: `fix: bound the background-agent wait by idle time`

- [ ] **B5 — Session-path metadata** (`pipeline/actions/dispatch.py::_dispatch_via_session`) — Effort 1
  - [ ] Add `background_tasks_waited` and `background_tasks_stopped` from the session to the returned `ActionResult.metadata`.
  - [ ] SC: the keys are always present on the session path (zero when nothing ran).

- [ ] **B5-T — Test** (`tests/pipeline/actions/test_dispatch_session.py`)
  - [ ] A fake session with `background_tasks_waited=2`, `background_tasks_stopped=0` produces metadata with both values.
  - [ ] Commit: `feat: record background task counts in session dispatch metadata`

- [ ] **B6 — Flag tail on the post-condition** (`events/builtin/dispatch_artifact.py`) — Effort 1
  - [ ] In `DispatchArtifactAction.execute`, when `error` is not None, append `f'; agent\'s final text: "{tail_text(response)}"'`, where `response = str(context.result.outputs.get("response", ""))`.
  - [ ] Do not change the helpers' log lines. The `dispatch post-condition` prefix is asserted by existing tests.
  - [ ] SC: every failure branch gets the tail, because it is appended in one place.

- [ ] **B6-T — Tests** (names contain `final_text`)
  - [ ] `tests/pipeline/test_executor.py`: a phase dispatch with no artifact and response `"…the research agent is still running."`. The failed result's error ends with that tail.
  - [ ] `tests/pipeline/test_executor_each.py`: the same inside an `each` batch. The batch report record's failure reason and the FLAGGED warning both contain `agent's final text:`.
  - [ ] SC: `uv run pytest tests/pipeline/test_executor.py tests/pipeline/test_executor_each.py -k final_text -q` passes.
  - [ ] Commit: `fix: include the agent's final text in dispatch post-condition flags`

- [ ] **B7 — Part B checkpoint**
  - [ ] `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest -q`: all green (apart from baseline).
  - [ ] Commit any formatting fixes: `style: format Part B`. Skip this if there are no changes.


## Part D — Explicit settings (#156)

- [ ] **D1 — Bool config values and `pipeline.auto_memory`** — Effort 2
  - [ ] `config/manager.py::_coerce_value`: add `bool`. Parse leniently and case-insensitively: `true/yes/on/1` → `True`, `false/no/off/0` → `False`, whitespace stripped. Anything else raises `ValueError` naming the key and the accepted spellings.
  - [ ] `get_typed_config`: accept `type_=bool`. A non-bool value raises `ValueError`. **Check `bool` before `int`**, because `bool` is a subclass of `int`.
  - [ ] `config/keys.py`: `ConfigKey(name="pipeline.auto_memory", type_=bool, default=True, description=…)`. The description says it applies to pipeline sessions and dispatch only, and that reviews always run with memory off.
  - [ ] Check that `sq config list` renders the bool (`true` / `false`) and that `sq config set pipeline.auto_memory false` round-trips through the TOML file as a native bool.
  - [ ] SC: `sq config get pipeline.auto_memory` prints `true (default)`.

- [ ] **D1-T — Tests** (`tests/config/test_manager.py`, `tests/config/test_keys.py`, `tests/config/test_cli_config.py`)
  - [ ] Parametrized coercion over every accepted spelling, including mixed case and padded whitespace. An invalid value (`"maybe"`) raises `ValueError`.
  - [ ] `get_typed_config(key, bool)` returns a bool, and a non-bool raises.
  - [ ] The CLI set/get round-trip for `pipeline.auto_memory`.
  - [ ] SC: `uv run pytest tests/config -q` passes.
  - [ ] Commit: `feat: support bool config values and add pipeline.auto_memory`

- [ ] **D2 — `providers/sdk/settings.py`** (new) — Effort 1
  - [ ] Add `PIPELINE_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)` and `REVIEW_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)`, each with a one-line comment saying which paths it governs. They are separate on purpose.
  - [ ] Add `AUTO_MEMORY_DISABLE_ENV: Final = "CLAUDE_CODE_DISABLE_AUTO_MEMORY"`, the one definition of that name.
  - [ ] Add `sdk_settings_options(setting_sources: Sequence[str], *, auto_memory: bool, base_env: Mapping[str, str] | None = None) -> dict[str, object]`. It returns `{"setting_sources": list(setting_sources), "env": {...}}`, where `env` is `base_env` merged with `{AUTO_MEMORY_DISABLE_ENV: "1"}` when `auto_memory` is false. `base_env` is never mutated.
  - [ ] SC: the module has no imports from `pipeline/` or `review/`, so it stays a leaf.

- [ ] **D2-T — Tests** (`tests/providers/sdk/test_settings.py`, new)
  - [ ] `auto_memory=False` → env contains the disable var. `True` → env lacks it.
  - [ ] Existing `base_env` keys survive the merge, and the input mapping is unchanged.
  - [ ] `setting_sources` is returned as a new list.
  - [ ] Commit: `feat: add SDK settings policy module`

- [ ] **D3 — `AgentConfig.auto_memory` and the provider** — Effort 2
  - [ ] `core/models.py`: add `auto_memory: bool = False` to `AgentConfig`, with a one-line comment: "SDK agents: True only on pipeline paths (pipeline.auto_memory)".
  - [ ] `providers/sdk/provider.py:80-92`: replace the `setting_sources == []` inference with `sdk_settings_options(...)`.
    - Apply `setting_sources` only when it is not `None`, as today, because `sq serve` callers may still pass `None`.
    - **Always** apply the env from `auto_memory`.
    - Keep the existing env-merge behavior.
    - Delete the old comment, and replace it with one line pointing at D11.
  - [ ] SC: `grep -n "DISABLE_AUTO_MEMORY" src/squadron` shows only `providers/sdk/settings.py`.

- [ ] **D3-T — Tests** (`tests/providers/sdk/test_provider.py`, `tests/review/test_pr_settings_isolation.py`)
  - [ ] `AgentConfig(auto_memory=False, setting_sources=["project"])` → options env has the disable var. `auto_memory=True` → it does not.
  - [ ] The PR isolation tests still pass unchanged: `[]` plus the disable var.
  - [ ] SC: both files pass.
  - [ ] Commit: `refactor: drive SDK auto-memory from AgentConfig.auto_memory`

- [ ] **D4 — Pipeline session settings** (`pipeline/sdk_session.py::open_pipeline_session`) — Effort 1
  - [ ] Merge `sdk_settings_options(PIPELINE_SETTING_SOURCES, auto_memory=<pipeline.auto_memory read via get_typed_config(..., bool, cwd)>)` into the base options.
  - [ ] Expose the resolved values on the session (`setting_sources: tuple[str, ...]`, `auto_memory: bool`) for task C6's metadata.
  - [ ] SC: the base options carry `setting_sources=["project"]`, and both values survive `_reconnect`, because the seed only changes `system_prompt`.

- [ ] **D4-T — Tests** (`tests/pipeline/test_sdk_session.py`)
  - [ ] With the config patched to `True`: `setting_sources == ["project"]` and the env lacks the disable var. With `False`: the env has it.
  - [ ] After `compact()`, the new client's options still carry the same `setting_sources` and env.
  - [ ] Commit: `fix: set explicit settings sources on pipeline sessions`

- [ ] **D5 — One-shot dispatch settings** (`pipeline/actions/dispatch.py::one_shot_dispatch_with_telemetry`) — Effort 1
  - [ ] SDK path: `setting_sources=list(PIPELINE_SETTING_SOURCES)`, and `auto_memory` from `pipeline.auto_memory` (use the `cwd` argument when given, else `"."`).
  - [ ] Non-SDK path: leave both at their defaults (not applicable).
  - [ ] SC: the SDK `AgentConfig` never has `setting_sources=None`.

- [ ] **D5-T — Tests** (`tests/pipeline/actions/test_dispatch.py`)
  - [ ] SDK dispatch → `AgentConfig.setting_sources == ["project"]`, and `auto_memory` follows the patched config (both values).
  - [ ] Non-SDK dispatch → `setting_sources is None`, `auto_memory is False`.
  - [ ] Commit: `fix: set explicit settings sources on one-shot SDK dispatch`

- [ ] **D6 — Review templates and loader** — Effort 2
  - [ ] Change `setting_sources: null` → `setting_sources: [project]` in each of:
    - [ ] `data/templates/slice.yaml`
    - [ ] `data/templates/tasks.yaml`
    - [ ] `data/templates/judge-findings-addressed.yaml`
    - [ ] `data/templates/judge-slice-vs-arch.yaml`
    - [ ] `data/templates/judge-tasks-vs-slice.yaml`
  - [ ] `review/templates/__init__.py:130-140`: fix the loader.
    - A missing or `null` key → `list(REVIEW_SETTING_SOURCES)`.
    - An explicit `[]` **stays `[]`**. Today `if setting_src else None` turns `[]` into `None`, which is a latent bug; fix it with an `is None` check.
    - The field type becomes `list[str]` (never `None`). Update every reader that handled `None`.
  - [ ] `review/review_client.py`: `setting_sources_override` keeps precedence. Delete the "None preserves template-only behavior" comment, which is now wrong.
  - [ ] SC: `grep -rn "setting_sources: null" src/squadron/data/templates` returns nothing.

- [ ] **D6-T — Tests** (`tests/review/test_templates.py`, `tests/review/test_template_sdk_regression.py`, `tests/review/test_builtin_*.py`)
  - [ ] Every built-in template loads with `setting_sources == ["project"]` (parametrize over the template directory).
  - [ ] A custom template with the key missing → `["project"]`. With `null` → `["project"]`. With `[]` → `[]`.
  - [ ] Update any existing assertion that expected `None` for slice/tasks/judge templates.
  - [ ] SC: `uv run pytest tests/review -q` passes.
  - [ ] Commit: `fix: load review templates with project settings sources`

- [ ] **D7 — Per-path policy test** (`tests/providers/sdk/test_settings_policy.py`, new) — Effort 2
  - [ ] One parametrized test over the D10 table. Each case builds that path's `AgentConfig` or options through its real builder (with collaborators faked) and asserts `setting_sources` and `auto_memory`:
    - [ ] review (a built-in template) → `["project"]`, `False`
    - [ ] PR review → `[]`, `False`
    - [ ] pipeline session → `["project"]`, config value
    - [ ] one-shot SDK dispatch → `["project"]`, config value
    - [ ] summary one-shot → `[]`, `False`
    - [ ] audit (`metrology/audit.py`) → `["project"]`, `False`
    - [ ] PR composer (`pr/composer.py`) → `[]`, `False`
  - [ ] SC: the test passes, and no case asserts `None`.
  - [ ] Commit: `test: assert settings policy per SDK path`

- [ ] **D8 — Part D checkpoint**
  - [ ] `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest -q`: all green (apart from baseline).
  - [ ] Commit any formatting fixes: `style: format Part D`. Skip this if there are no changes.

---

## Part C — Explicit system prompt and recording (#155, #156)

- [ ] **C1 — SDK dispatch: preset plus append** (`pipeline/actions/dispatch.py:127-134`) — Effort 1
  - [ ] Set `use_default_system_prompt = is_sdk` and `instructions = system_prompt or None`. Update the #40 comment to also cite #155.
  - [ ] SC: the provider table rows used are "True / None → preset" and "True / str → preset + append".

- [ ] **C1-T — Tests** (`tests/pipeline/actions/test_dispatch.py`, `tests/cli/commands/test_dispatch_run.py`)
  - [ ] SDK with `system_prompt="X"` → `AgentConfig(use_default_system_prompt=True, instructions="X")`.
  - [ ] SDK without → `(True, None)`.
  - [ ] Non-SDK with `"X"` → `(False, "X")`, unchanged.
  - [ ] `sq dispatch --system-prompt X` on an SDK model → `(True, "X")`.
  - [ ] Commit: `fix: append dispatch system_prompt to the Claude Code preset`

- [ ] **C2 — Session path rejects a step `system_prompt`** (`dispatch.py::_dispatch_via_session`) — Effort 1
  - [ ] Next to the existing `allowed_tools` guard, add: if `context.params.get("system_prompt")` is truthy, return `ActionResult(success=False, …)` with an error stating that a persistent session's system prompt is fixed at connect and suggesting a non-SDK model or removing `system_prompt`. Match the `allowed_tools` wording pattern.
  - [ ] SC: the guard runs before `set_model`/`dispatch`.

- [ ] **C2-T — Test** (`tests/pipeline/actions/test_dispatch_session.py`)
  - [ ] A step with `system_prompt` on the session path fails with that message, and the session's `dispatch` is never called.
  - [ ] Commit: `fix: reject a step system_prompt on the SDK session path`

- [ ] **C3 — `SystemPromptMode` and describers** (`core/models.py`) — Effort 2
  - [ ] Add the `SystemPromptMode(StrEnum)`: `PRESET="preset"`, `PRESET_APPEND="preset+append"`, `CUSTOM="custom"`, `EMPTY="empty"`.
  - [ ] Add `describe_system_prompt(config: AgentConfig) -> SystemPromptMode`, derived from `use_default_system_prompt` and `instructions` per the existing table:
    - `True` + non-empty instructions → `PRESET_APPEND`
    - `True` otherwise → `PRESET`
    - `False` + non-empty → `CUSTOM`
    - `False` otherwise → `EMPTY`
  - [ ] Add `describe_setting_sources(setting_sources: Sequence[str] | None, *, is_sdk: bool) -> str`:
    - not SDK → `"n/a (non-SDK)"`
    - `[]` → `"none"`
    - otherwise → `", ".join(...)`
    - `None` on SDK → `"cli default"`. This case only appears for `sq serve` agents and is recorded honestly.
  - [ ] SC: both functions are pure, and their rendered strings are defined once (constants or enum values).

- [ ] **C3-T — Tests** (`tests/test_models.py`)
  - [ ] Parametrize `describe_system_prompt` over the four rows plus `instructions=""`.
  - [ ] Parametrize `describe_setting_sources` over non-SDK, `[]`, `["project"]`, `["user", "project"]`, and SDK `None`.
  - [ ] Commit: `feat: add SystemPromptMode and settings describers`

- [ ] **C4 — `ReviewResult` carries the mode and settings** — Effort 2
  - [ ] `review/models.py`: replace `default_system_prompt_preset_used: bool` with `system_prompt_mode: SystemPromptMode | None = None`. Add `setting_sources: str | None = None`, holding the rendered string from `describe_setting_sources`.
  - [ ] `review/review_client.py:329`: set both from the built `AgentConfig`, using `describe_system_prompt(config)` and `describe_setting_sources(config.setting_sources, is_sdk=…)`.
  - [ ] `review/persistence.py:663` (the `-vv` note): show the preset note when the mode is `PRESET` or `PRESET_APPEND`.
  - [ ] Update every other reader: `grep -rn default_system_prompt_preset_used src tests`.
  - [ ] SC: that grep returns nothing.

- [ ] **C4-T — Tests** (`tests/review/test_review_client.py`)
  - [ ] An SDK review → `system_prompt_mode == PRESET_APPEND` and `setting_sources == "project"`.
  - [ ] A non-SDK review → `CUSTOM` and `"n/a (non-SDK)"`.
  - [ ] A PR review (override `[]`) → `setting_sources == "none"`.
  - [ ] Commit: `feat: record prompt mode and settings on review results`

- [ ] **C5 — Run Digest and JSON output** (`review/persistence.py::_run_digest_lines`, `review/models.py::to_dict`) — Effort 2
  - [ ] Add two always-on digest lines after `Output budget`:
    - `- System prompt: <mode or "not reported">`
    - `- Settings sources: <value or "not reported">`
    - Use the existing `_render_optional` for `None`.
  - [ ] `to_dict`: add the `system_prompt_mode` and `setting_sources` keys, following the existing `stop_reason` convention for `None`.
  - [ ] SC: a PASS artifact and a degraded artifact both show the two lines.

- [ ] **C5-T — Tests** (`tests/review/test_persistence.py`, `tests/cli/test_review_format.py`, fixtures)
  - [ ] The digest renders each mode and the `not reported` case.
  - [ ] The JSON output contains both keys.
  - [ ] Regenerate or update the golden fixtures that contain a full `### Run Digest` block (`tests/review/fixtures/clean_pass_artifact.md` and any others the suite flags). Diff them, and confirm that the only change is the two new lines.
  - [ ] SC: `uv run pytest tests/review tests/cli -q` passes.
  - [ ] Commit: `feat: show prompt mode and settings in the Run Digest and JSON`

- [ ] **C6 — Dispatch and summary step metadata** — Effort 1
  - [ ] One-shot dispatch (`dispatch.py::_dispatch_via_agent` / `one_shot_dispatch_with_telemetry`): add `system_prompt_mode`, `setting_sources` (the rendered string), and `auto_memory` to `ActionResult.metadata`, derived from the built `AgentConfig`. Return them alongside the telemetry. Do not recompute them.
  - [ ] Session path (`_dispatch_via_session`): the same three keys, from the session. Mode is `preset`, or `preset+append` when the session was seeded, so expose `seeded: bool` on the session, set by `_reconnect`/`open_pipeline_session`.
  - [ ] `pipeline/summary_oneshot.py`: its metadata or return gets `system_prompt_mode="empty"` and `setting_sources="none"`, derived from its config through the same describers.
  - [ ] SC: the keys are present on every dispatch result, on both paths.

- [ ] **C6-T — Tests**
  - [ ] `test_dispatch.py`: SDK one-shot with `system_prompt` → `preset+append`, `project`, and `auto_memory` equal to the config value.
  - [ ] `test_dispatch_session.py`: an unseeded session → `preset`. A seeded session → `preset+append`.
  - [ ] A summary one-shot test asserts `empty` and `none`.
  - [ ] Commit: `feat: record prompt mode and settings in dispatch and summary metadata`

- [ ] **C7 — Part C checkpoint**
  - [ ] `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest -q`: all green (apart from baseline).
  - [ ] Commit any formatting fixes: `style: format Part C`. Skip this if there are no changes.

---

## Close-out

- [ ] **E1 — Live verification** (design § Verification Walkthrough) — Effort 2 — **PM-assisted**: it needs live model calls and a scratch repo. The agent runs the steps and the PM confirms the observations. It is not an autonomous checklist item.
  - [ ] Step 2 (seeding): run `/tmp/seed-check.yaml` from a scratch git repo. The second session's transcript has the third step's prompt as its first `user` entry, the reply quotes the `item-reset` line, and there are no new commits.
  - [ ] Step 3 (background wait): the INFO `waiting` line appears, `bg-check.txt` exists after the step, and `background_tasks_waited: 1` appears in `sq run --status latest`. Also record **whether `task_progress` messages arrived between turns** (D5: this decides whether the idle timer acts per idle period or as a total cap).
  - [ ] Step 5 (recording): `sq review slice 932 --model sonnet -v`. The digest shows `System prompt: preset+append` and `Settings sources: project`, and `--output json` has both keys.
  - [ ] Update the design's Verification Walkthrough with what was actually observed. Fix any command that turned out wrong.
  - [ ] SC: every step either passes or has an open issue linked in the walkthrough.

- [ ] **E2 — Docs and status**
  - [ ] CHANGELOG `[Unreleased]`, short user-facing bullets (no internals):
    - [ ] Pipeline session rotation no longer gives the model a turn (#162).
    - [ ] Dispatch waits for background agents, and flagged items show the agent's last words (#163).
    - [ ] Dispatch `system_prompt` is appended to the Claude Code prompt (#155).
    - [ ] Pipeline runs and all reviews load project settings only: user CLAUDE.md and user settings no longer apply. New settings `pipeline.auto_memory` and `pipeline.background_idle_timeout_s` (#156).
  - [ ] Design § API Contracts: bring it in line with what was built. At minimum:
    - `seed_context(text, source: SeedSource)`
    - `sdk_settings_options(..., base_env=...)`
    - `SeedSource`, `seeded`, `unusable_reason`, `background_tasks_stopped`
    - `pipeline/text_tail.py::tail_text` (which replaces the design's `FINAL_TEXT_TAIL_CHARS` in `dispatch_artifact.py`)
  - [ ] DEVLOG: an implementation entry, with details and any deviations from the design.
  - [ ] Design `status: complete`, task file `status: complete`, and `projectState` updated.
  - [ ] Check off slice plan entry 30 in `900-slices.maintenance-and-refactoring.md`.
  - [ ] Commit: `docs: close out slice 932`

- [ ] **E3 — Code review gate and merge** — **PM-gated**: the PM runs the review. The agent then addresses the findings and merges.
  - [ ] The Project Manager runs the code review (`sq review code 932 --model <model>`). Do not run it without an explicit `--model`.
  - [ ] Address the findings in the review file's `## Response` section, fix them, and commit.
  - [ ] Re-read `cf config get git.integration_branch` (empty → `main`). Then `git checkout main && git merge 932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings`.
  - [ ] SC: main contains the slice, and the suite is green on main.
