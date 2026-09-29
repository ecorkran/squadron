---
docType: slice-design
slice: pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260928
dateUpdated: 20260928
status: complete
---

# Slice Design: Pipeline SDK Session Control — Seeding Without a Turn, Dispatch That Waits for Background Work, and Explicit Prompt and Settings

## Overview

Squadron does not fully control what a pipeline SDK session receives, or decide when that session is done. Four issues come from that one gap:

1. **Seeding hands the model a free turn** ([#162](https://github.com/ecorkran/squadron/issues/162)). `SDKExecutionSession.compact()` and `seed_context()` ([sdk_session.py:298](../../../src/squadron/pipeline/sdk_session.py#L298), [:313](../../../src/squadron/pipeline/sdk_session.py#L313)) send the framed summary as an ordinary prompt. That is a full turn with every tool enabled under `bypassPermissions`. In amoeba's `sq run slices-plan 100` (run `run-20260928-slices-plan-a04bdb07`), the `item-reset` summary contained no task. Opus invented one ("Commit the slice 106 task breakdown… then push to origin") and ran `git push origin main`, publishing 12 unreviewed commits. The "do NOT take action" framing is only advice to the model; nothing enforces it.
2. **Dispatch stops while background work is still running** ([#163](https://github.com/ecorkran/squadron/issues/163)). In the same run, slice 107's design dispatch started a background `Explore` agent, then ended its turn with "once it reports back I'll write the 107 design". `dispatch()` stops at the first `ResultMessage`, so the work was lost. The flag said only "no design artifact path registered", and the agent's explanation was recorded nowhere.
3. **A step's `system_prompt` replaces the Claude Code prompt** ([#155](https://github.com/ecorkran/squadron/issues/155)). [dispatch.py:133](../../../src/squadron/pipeline/actions/dispatch.py#L133) turns off the preset whenever a step gives a prompt. This is the bug #85 fixed for reviews, on a different path.
4. **Settings sources are left to the CLI, and nothing records them** ([#156](https://github.com/ecorkran/squadron/issues/156)). Pipeline sessions, dispatch, and the `slice`/`tasks`/`judge-*` review templates leave `setting_sources` unset. No path records which system prompt and settings it ran with.

## Value

- A pipeline cannot act on seed text. Rotation and resume put the seed into the new session's system prompt, and the model gets no turn until the next real step.
- A dispatch that starts background agents returns only after those agents report back and the model finishes its follow-up turn. When a dispatch still leaves no artifact, the flag includes the agent's last words, so the reason is on record.
- A step's `system_prompt` adds to the Claude Code prompt instead of replacing it, the same as reviews.
- Every automated SDK path loads a declared set of settings. Personal settings (user CLAUDE.md, user settings, output style) no longer reach reviews or pipeline runs, and which template or path is running no longer changes that. Auto-memory becomes a deliberate choice: a config switch for pipeline work, and always off for reviews. Each review artifact and dispatch step records the prompt mode and settings it ran with.

## Technical Scope

**In scope**

- **A — Seeding without a turn (#162).** A single session builder. Rotation, resume, and `summary restore` connect a fresh client whose system prompt is the preset with the framed seed appended. No seeding `query()` is sent. The lazy-connect path also receives the resume seed, which it misses today. The restore path's double framing is fixed.
- **B — Dispatch waits for background agents (#163).** `SDKExecutionSession.dispatch()` tracks background agent tasks from the task lifecycle messages. It keeps reading past a turn's result until none are still running and the final result answers its own prompt. The dispatch-artifact post-condition appends the tail of the agent's final text to its failure message, and the batch report shows it too.
- **C — Explicit system prompt (#155).** SDK one-shot dispatch always uses the preset, and a step `system_prompt` is appended to it. On the session path, a step `system_prompt` fails with an explicit error, as `allowed_tools` already does.
- **D — Explicit settings, recorded (#156).** The CLI's default is verified and written down (D9). One declared `setting_sources` value per automated path. Auto-memory is set explicitly per path: the config key `pipeline.auto_memory` (default on) controls pipeline sessions and dispatch, and every review, judge, PR, summary, and audit path has it off. Each review's Run Digest and JSON output records the system-prompt mode and settings sources, as does each dispatch and summary step's metadata.

**Why one slice.** The slice plan entry bundles all four issues, and that was a Project Manager decision. They share one theme: squadron decides what an SDK session receives and when it is done. They also share two surfaces, the session builder and the prompt/settings recording. The parts are still delivered separately, in the order A → B → D → C (see Development Approach). Each part is its own commit or commits, passes the suite on its own, and can be reverted without touching the others. Part A, the safety fix, goes first and does not wait on the others. If the slice needs splitting, the agreed fallback is to split between A/B and D/C.

**Out of scope**

- The summary-capture turn in the old session (`capture_summary`). It answers an explicit "summarize" instruction, so it is a real task, not a free turn. It stays as is.
- One-shot dispatch in `query` mode (`ClaudeSDKAgent._handle_query_mode`). The SDK's own `query()` already keeps stdin open while background agents run (`wait_for_result_and_end_input`, `DEFERRING_TASK_TYPES` in `claude_agent_sdk/_internal/query.py`). #163 applies to the persistent session path only.
- Background *shells* (`Bash(run_in_background=true)`) and monitors. They can run forever by design, and the SDK also refuses to wait on them. Dispatch does not wait for them either (D5).
- `sq serve` agent spawning (`server/routes/agents.py`) and the auth probe (`providers/auth.py`). The API caller supplies the config for the first, and the second does no prompt work. Neither is an automated pipeline or review path.
- A `system_prompt_mode: replace` escape hatch. No shipped or user pipeline sets a dispatch `system_prompt` (checked under `src/squadron/data/pipelines/` and `~/.config/squadron/pipelines/`), so nothing needs one.

## Dependencies

### Prerequisites

- No hard prerequisite.
- **Soft ordering with slice 931** (designed, not implemented). Both slices add Run Digest lines, `ReviewResult` fields, `AgentConfig` fields, and review JSON keys. The overlap is in `review/models.py`, `review/persistence.py`, and `core/models.py`. The two share no logic. If 931 merges first, Part C of this slice rebases onto it, along with Part D's one `AgentConfig.auto_memory` line in `core/models.py`. Parts A and B don't touch those files.

### Interfaces Required

- `claude-agent-sdk` 0.2.160 (pinned), public exports: `TaskStartedMessage`, `TaskNotificationMessage`, `TaskUpdatedMessage`, `TERMINAL_TASK_STATUSES`, and `ResultMessage.origin`. `ClaudeAgentOptions` is a dataclass, so `dataclasses.replace` works on it. A preset `append` is sent as `--append-system-prompt` (`subprocess_cli.py`).
- Claude Code CLI 2.1.284 behavior under each `--setting-sources` value, verified in D9.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `pipeline/sdk_session.py` | `open_pipeline_session(seed=None)` builder (replaces the duplicated option literals in `run.py:357` and `executor.py:648`). `SDKExecutionSession` keeps `base_options`, and one private `_reconnect(seed)` serves `compact()` and `seed_context()`. `dispatch()` gains the background-task ledger and origin-aware completion. |
| `pipeline/executor.py` | The resume seed is computed once and passed either to `seed_context()` (session already connected) or to `_connect_lazy_session(seed=…)`. |
| `pipeline/actions/summary.py` | Restore passes the raw summary. `seed_context` does the framing, which removes the double frame. |
| `pipeline/actions/dispatch.py` | SDK one-shot always uses the preset, with the step prompt appended. The session path rejects a step `system_prompt`. Step metadata gets `system_prompt_mode`, `setting_sources`, and (session path) `background_tasks_waited`. |
| `events/builtin/dispatch_artifact.py` | The failure message gets the tail of `result.outputs["response"]`. |
| `providers/sdk/settings.py` (new, small) | `PIPELINE_SETTING_SOURCES` and `REVIEW_SETTING_SOURCES` policy constants, plus `sdk_settings_options(setting_sources, *, auto_memory) -> dict`, which returns `setting_sources` and the auto-memory env. Used by both the provider and the session builder. |
| `providers/sdk/provider.py` | Uses `sdk_settings_options` and reads `AgentConfig.auto_memory` instead of inferring it from `setting_sources == []` (D11). |
| `config/keys.py` | New keys `pipeline.auto_memory` (bool, default `true`) and `pipeline.background_idle_timeout_s` (int, default `1800`). |
| `core/models.py` | `SystemPromptMode` StrEnum and `describe_system_prompt(config)`, next to the existing prompt table. |
| `review/templates/__init__.py`, `data/templates/*.yaml` | Built-in templates set `setting_sources: [project]`. The loader resolves an absent or `null` key to `REVIEW_SETTING_SOURCES`. |
| `review/models.py`, `review/review_client.py`, `review/persistence.py` | `ReviewResult` carries `system_prompt_mode` (replacing the `default_system_prompt_preset_used` bool) and `setting_sources`. The Run Digest and JSON output render both, always. |
| `pipeline/summary_oneshot.py` | Records mode and settings in metadata. Its values (`instructions=""`, `[]`) do not change. |

### Data Flow

**Rotation today (#162):**

```
compact(summary) → disconnect → new client(options) → connect
                 → dispatch(frame(summary))   ← full turn, all tools, bypassPermissions
```

**Rotation after:**

```
compact(summary) → disconnect → new client(base_options + append=frame(summary)) → connect
                 → (no query; the next step's dispatch is the session's first turn)
```

Resume follows the same path. If the run starts with a session already connected, `executor` calls `seed_context(text)`, which is `_reconnect(text)`. With a lazy session, `executor` holds the seed and `_connect_lazy_session(seed=text)` builds the first client with it. `summary restore` also calls `seed_context`.

**Dispatch completion after (#163):**

```
query(prompt)
loop receive_response():
    TaskStartedMessage(task_type ∈ WAITED_TASK_TYPES)       → ledger.add(task_id)
    TaskNotificationMessage | TaskUpdatedMessage(terminal)   → ledger.discard(task_id)
    ResultMessage:
        injected and not own_result_seen  → drop text read so far (leftover, WARNING)
        origin is None or kind == "human" → own_result_seen = True
        own_result_seen and ledger empty  → return joined text
        else                              → log once, read the next turn
    (waiting, no message for idle timeout) → stop_task each, clear ledger, WARNING, return
    (stream ends, no own result)           → ProviderError
```

Text from the follow-up turn (the one the CLI injects when a background agent reports back) is joined into the response. The response therefore contains the agent's real final words.

### State Management

- `SDKExecutionSession.base_options` is the unseeded option set. A seed is applied per connect and never stored back, so a second rotation replaces the first seed instead of adding to it.
- The background ledger is a local `set[str]` inside a single `dispatch()` call. Each dispatch starts empty.
- Nothing new is persisted. Recording goes into existing carriers: `ActionResult.metadata` (run state JSON), the review artifact body, and review JSON output.

## Technical Decisions

### D1 — The seed rides the system prompt, never a turn

On connect, the fresh client gets `system_prompt={"type": "preset", "preset": "claude_code", "append": frame_summary_for_seed(text)}`. The model sees the seed as standing context and has nothing to answer until the next step's prompt. This is the fix #162 proposes. No turn happens, so there is no turn to run tool-less.

The framing text changes to match its new place. It no longer says "wait for the next user instruction". It says: this is a summary of earlier work in this pipeline run, it is reference material and not a task, and it is not an instruction to do anything.

If the base options already carry an `append` (none do today), the seed goes after it, separated by a blank line.

### D2 — One session builder

`open_pipeline_session(*, seed: str | None = None) -> SDKExecutionSession` builds the options (cwd, `bypassPermissions`, preset, and the settings from D10), constructs the client, and connects. `run.py` and `_connect_lazy_session` both call it, which removes today's duplicated literals. `_reconnect` uses the same option-building function with `base_options`.

### D3 — `summary restore` replaces the session

`seed_context(text)` is now "rotate to a fresh session seeded with `text`". Any history since the last rotation is dropped. Every shipped `restore: true` (`slice.yaml`, `tasks.yaml`, `app.yaml`) comes right after a `compact:` step, so nothing is lost there. The example.yaml comment is updated to say "replaces the session". `summary.py:154` stops calling `frame_summary_for_seed` itself, since today the summary is framed twice.

### D4 — Resume seeds the lazy session too

Today `executor.py:488` seeds only `if sdk_session is not None`. Under the lazy default with no statically-SDK step, the session does not exist yet at that point, so the resume summary is silently dropped. After this slice, the executor keeps the seed and hands it to whichever connect happens first.

### D5 — Wait for background agents, not shells

The ledger tracks `task_started` only for `task_type ∈ WAITED_TASK_TYPES = {"local_agent", "local_workflow"}`. This mirrors the SDK's `DEFERRING_TASK_TYPES`, redeclared locally because the SDK's constant is `_internal`. The comment cites the source. A task is cleared by a `TaskNotificationMessage` or by a `TaskUpdatedMessage` with a status in `TERMINAL_TASK_STATUSES`, since the SDK documents that either can be the only terminal signal. Shells and monitors are ignored, because they may never finish.

The wait is visible. The first time a result arrives with the ledger non-empty, dispatch logs at INFO: `dispatch: turn ended with N background agent(s) running; waiting: <descriptions>`.

**The wait is bounded by idle time.** Background-wait mode is the state where the dispatch's own result has been seen and the ledger is still non-empty. In that mode, each read of the stream is bounded by `pipeline.background_idle_timeout_s`, a new config key (int, default `1800`). If no message of any kind arrives within that time, dispatch does the following:

1. It calls `client.stop_task(task_id)` for each tracked id. The SDK already bounds each call: it waits 60s for the control response and then raises a bare `Exception`. It raises the same type when the CLI returns an error, so no narrower type can be caught. The catch is therefore `except Exception` around the single call, marked `noqa: BLE001` with a comment naming this SDK behavior, and it logs through `logger.exception`. Stopping is best-effort cleanup: the dispatch goes on to the next id and then returns. An agent that failed to stop may still trigger a follow-up turn later, and D6 handles that.
2. It clears the ledger locally, because a lost terminal signal is exactly the case being handled here.
3. It logs a WARNING: `dispatch: no activity for <N>s with background agent(s) still running; stopped: <descriptions>`.
4. It records `background_tasks_stopped` in the step metadata and returns the text it has.

The timer is idle-based, not total, so a long agent that keeps emitting progress messages is never cut off. If the CLI turns out to send no progress messages between turns, the timer becomes a total cap on the wait. That is still a bound. Walkthrough step 3 shows which of the two applies. Foreground turns keep today's behavior, with no timer. This slice bounds only the new wait it adds, and the foreground case is tracked in [#165](https://github.com/ecorkran/squadron/issues/165).

A stopped agent can still trigger a follow-up turn from the CLI. That turn's messages arrive at the start of the next dispatch and are handled by D6.

The rejected alternative is to disallow background agents. The CLI has no per-parameter switch for `run_in_background`, and blocking the `Agent` tool would also remove foreground subagents.

### D6 — Only the dispatch's own result can end it

`ResultMessage.origin` tells a result for our prompt (`None` or `{"kind": "human"}`) apart from the result of an injected turn (`{"kind": "task-notification"}`). There is a race the SDK documents (#1190): a background agent can finish just before our result, leaving the ledger empty while a follow-up turn is still owed. That follow-up then arrives at the start of the *next* dispatch's stream. Because injected results never end a dispatch, the next dispatch reads past it to its own result.

**Leftover text is dropped from the response.** An injected result can arrive before the dispatch's own result. When it does, every message read up to and including that injected result belongs to the previous step. Dispatch drops that text from its response and logs it at WARNING: `dispatch: discarded a background follow-up turn left over from the previous dispatch; its final text: "…<tail>"`. The current step's response, D7 tail, and post-condition therefore see only the current step's words, and the previous step's late words are still on record in the log.

**The previous step's flag can be misleading, and this is accepted.** If that leftover turn wrote the previous step's artifact, it did so after that step's post-condition ran. The step is flagged even though its artifact now exists on disk, and the WARNING above is the evidence. A resume or re-run finds the artifact. This is the rare race the SDK documents, and closing it would need the CLI's session-state frames, which the SDK hides from callers (`sdk_host_only`).

### D7 — The flag carries the agent's last words

`DispatchArtifactAction` appends `; agent's final text: "…<tail>"` to every post-condition failure message. The tail is the last `FINAL_TEXT_TAIL_CHARS = 400` characters of `context.result.outputs["response"]`, with whitespace collapsed. An empty response renders as `(empty response)`. This message is the action error, which `_item_failure_reason` already uses as the item's flag reason, so the batch report and the FLAGGED warning both show it with no new plumbing.

### D8 — SDK dispatch: preset plus append, always

`use_default_system_prompt = is_sdk`, and `instructions = system_prompt or None`. From the existing provider table: an SDK dispatch with a prompt sends preset + append, one without sends the preset only, and non-SDK is unchanged. `sq dispatch --system-prompt` goes through the same function, so it gets the same fix.

A live session's system prompt is fixed at connect. On the session path, a step `system_prompt` is therefore an error with the same wording pattern as the existing `allowed_tools` guard. Today it is silently ignored.

### D9 — What the CLI loads with no `--setting-sources` (verified)

Probed during design with Claude Code 2.1.284 (`claude -p`, haiku). The probe asked the model about a codeword placed in a throwaway project `CLAUDE.md`, and about a heading that exists only in the user's `~/.claude/CLAUDE.md`:

| Flag | Project CLAUDE.md | User CLAUDE.md | Auto-memory (`MEMORY.md`) |
|---|---|---|---|
| none | loaded | **loaded** | — |
| `project` | loaded | not loaded | **loaded** |
| `user,project` | loaded | loaded | — |
| `project` + `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` | loaded | not loaded | not loaded |

With `setting_sources=None` and no `skills`, SDK 0.2.160 passes no flag (`subprocess_cli.py:729`). So today, `slice`/`tasks`/`judge-*` reviews, every pipeline session, and SDK dispatch load the operator's user CLAUDE.md and user settings, including output style. `code`/`arch` reviews do not. Auto-memory loads even under `project`, so `code`/`arch` reviews and the audit also read the operator's per-project memory.

### D10 — Settings policy per path

Each automated path uses a declared value. None of them inherits `None`.

| Path | `setting_sources` | Auto-memory | Change |
|---|---|---|---|
| Reviews and judges (all built-in templates) | `REVIEW_SETTING_SOURCES = ["project"]` | off | `slice`, `tasks`, `judge-*`: `null` → `[project]` |
| PR review | `[]` | off | none |
| Pipeline SDK session | `PIPELINE_SETTING_SOURCES = ["project"]` | `pipeline.auto_memory` (default on) | unset → `[project]` |
| One-shot SDK dispatch | `PIPELINE_SETTING_SOURCES` | `pipeline.auto_memory` (default on) | unset → `[project]` |
| Summary one-shot | `[]` | off | none |
| Tech-debt audit | `["project"]` | off | auto-memory now off |
| PR composer | `[]` | off | none |

Pipelines and reviews run on the project's conventions, not on the operator's personal setup. A run should produce the same artifacts whoever starts it, and personal settings such as the output style should not shape pipeline output. The rejected alternative was `user,project` for pipeline sessions, which would keep the operator's global CLAUDE.md in every dispatch.

**Why this is maintenance, not a feature.** Nobody chose today's behavior. Squadron leaves `setting_sources` unset, and the SDK's handling of `None` changed underneath it: slice 101 records "None → no project context loaded", but 0.2.160 passes no flag, and the CLI then loads user settings too (D9). Part D closes that unintended default and makes it explicit. Part D's only new config key is `pipeline.auto_memory`, which the PM asked for (D11). Settings sources get no config key; they are code constants.

**PM-ratified 20260928.** The policy was presented to the Project Manager, who kept `[project]` and changed only the auto-memory part (D11). This changes behavior operators can see: user CLAUDE.md and user settings stop loading on these paths. The CHANGELOG entry for the release says so in one line (see Implementation Notes).

**Added after implementation (PM request):** `pipeline.user_settings` (bool, default `false`). When on, pipeline sessions and one-shot SDK dispatch use `pipeline_setting_sources(include_user=True)` = `["user", "project"]`. Reviews, judges, PR, summary, and audit stay on their declared values whatever it says, so a review's verdict never depends on who runs it (PM-confirmed).

Custom review templates that omit `setting_sources` or set it to `null` resolve to `REVIEW_SETTING_SOURCES` in the loader. The artifact records the value used, so the default is visible rather than silent.

### D11 — Auto-memory: a config key for pipeline work, off for judging paths

`sdk_settings_options(setting_sources, *, auto_memory: bool)` sets `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` whenever `auto_memory` is false. It uses the same env-merge pattern as today ([provider.py:88](../../../src/squadron/providers/sdk/provider.py#L88)), and `open_pipeline_session` passes the same `env` into `ClaudeAgentOptions`.

- **Pipeline sessions and one-shot dispatch** read a new config key, `pipeline.auto_memory` (bool, default `true`, declared in `config/keys.py`). The per-project memory holds project lessons that help an agent doing project work. Because the key follows the existing user/project config levels, one project can turn it off without touching the others. With it on, the agent can also *write* to the memory directory. That is the reason the switch exists.
- **Reviews, judges, PR review, PR composer, summary one-shot, and audit** always pass `auto_memory=False`, with no switch. A reviewer judges against the project's conventions, not the operator's accumulated preferences. The PR paths work on untrusted input (slice 382 D8).

`AgentConfig` gets an `auto_memory: bool = False` field, and the provider reads it instead of inferring the setting from `setting_sources == []`. The default is `False`, so every path that doesn't opt in gets memory off. Only the two pipeline paths set it, from the config key.

### D12 — Recording

`SystemPromptMode` (StrEnum): `preset`, `preset+append`, `custom`, `empty`. `describe_system_prompt(config: AgentConfig)` derives the mode from the same two fields the provider table uses, so the recorded mode and the prompt actually sent come from one rule. Settings render as the joined list (`project`), `none` for `[]`, or `n/a (non-SDK)`.

- **Review Run Digest**, always on: `- System prompt: preset+append` and `- Settings sources: project`. The same two keys go in `--output json`. The `-vv` "sent with the preset" note reads the mode instead of the old bool.
- **Dispatch step metadata**: `system_prompt_mode`, `setting_sources`, and `auto_memory` on both paths. The session path uses `preset`, or `preset+append` when seeded. The session path also records `background_tasks_waited` (count).
- **Summary one-shot metadata**: `system_prompt_mode: empty`, `setting_sources: none`.
- **Seeding**: INFO log `seeded fresh session via system prompt (N chars, source: compact|resume|restore)`.

### D13 — Failure modes

| Failure | Signal |
|---|---|
| Reconnect with seed fails (CLI spawn, E2BIG on a huge seed) | The old client is already gone, so `_reconnect` records `self.unusable_reason` and re-raises. Compact, emit, and restore report a failed step with the error and log via `logger.exception`. Any later `dispatch()`, `compact()`, or `seed_context()` on that session raises `ProviderError("SDK session unusable: reconnect failed: …")` at once. The check is the first statement of each method, before any query or stream read, so it can never meet the background-wait or idle-timeout logic. Inside an `each` batch with a continue policy, the remaining items are therefore flagged with that reason, not sent into a dead client. There is no automatic retry. |
| Stream ends before the dispatch's own result (CLI died, or the iterator ended) | A CLI crash surfaces as `ProcessError`/`CLIConnectionError` and maps to `ProviderError`, as today. If `receive_response()` ends without the dispatch's own result, dispatch raises `ProviderError("stream ended before the dispatch's result; N background agent(s) still running: …")`. It never returns partial text as success. |
| Background agent never finishes, or its terminal signal is lost | After `pipeline.background_idle_timeout_s` of silence: stop the tracked tasks, clear the ledger, log a WARNING naming them, and record `background_tasks_stopped` (D5). |
| `stop_task` raises or times out during the idle-timeout path (the SDK bounds it at 60s) | `logger.exception` naming the task id, then continue with the next id, and return as in D5. The agent may later trigger a follow-up turn, which D6 handles. |
| Stalled foreground turn: no own result yet and no tracked agents | **Accepted and unchanged**: no timer, same as today. This slice bounds only the new wait it adds. Tracked in [#165](https://github.com/ecorkran/squadron/issues/165). |
| Background agent fails or is killed | A terminal status clears it. The follow-up turn's text is in the response, and the D7 tail shows it if no artifact was written. |
| Injected turn consumed at the start of a dispatch | Its text is dropped from the response and logged at WARNING with its tail (D6). |
| Step `system_prompt` on the session path | Step fails with an explicit error. |
| Custom template with no `setting_sources` | Resolves to `REVIEW_SETTING_SOURCES`, and the Run Digest shows it. |

## Implementation Details

### API Contracts

As built:

```python
# pipeline/sdk_session.py
class SeedSource(StrEnum):
    COMPACT = "compact"; RESUME = "resume"; RESTORE = "restore"   # named in the seeding log

async def open_pipeline_session(*, seed: str | None = None) -> SDKExecutionSession: ...

class SDKExecutionSession:
    client: ClaudeSDKClient
    base_options: ClaudeAgentOptions        # renamed from `options`; unseeded, settings included
    async def compact(self, instructions: str, summary_model: str | None = None,
                      restore_model: str | None = None, summary: str | None = None) -> str: ...
    async def seed_context(self, text: str, source: SeedSource) -> None:  # rotate; raw text
    async def dispatch(self, prompt: str) -> str:       # waits per D5/D6
    background_tasks_waited: int                        # set by the last dispatch()
    background_tasks_stopped: int                       # set by the last dispatch() (idle timeout)
    unusable_reason: str | None                         # set when _reconnect fails; later calls raise
    seeded: bool                                        # live client carries a seed (prompt-mode metadata)
    setting_sources: list[str] | None                   # property, derived from base_options
    auto_memory: bool                                   # property, derived from base_options.env

# pipeline/sdk_turns.py (pure turn bookkeeping, split out of sdk_session.py for size)
WAITED_TASK_TYPES: Final = frozenset({"local_agent", "local_workflow"})
class BackgroundLedger: ...                             # observe(msg), active, seen_count, ...
def is_own_result(msg: ResultMessage) -> bool: ...
class DispatchTurns: ...                                # response parts + ledger for one dispatch

# pipeline/text_tail.py — the one definition of the tail, shared by D6 and D7
FINAL_TEXT_TAIL_CHARS: Final = 400
def tail_text(text: str) -> str: ...                    # "…" when truncated; "(empty response)"

# providers/sdk/settings.py
PIPELINE_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)
REVIEW_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)
AUTO_MEMORY_DISABLE_ENV: Final = "CLAUDE_CODE_DISABLE_AUTO_MEMORY"
USER_SETTING_SOURCE: Final = "user"
def pipeline_setting_sources(*, include_user: bool) -> tuple[str, ...]: ...  # pipeline.user_settings
class SdkSettings(TypedDict): setting_sources: list[str]; env: dict[str, str]
def sdk_settings_options(setting_sources: Sequence[str], *, auto_memory: bool,
                         base_env: Mapping[str, str] | None = None) -> SdkSettings: ...

# core/models.py — AgentConfig
auto_memory: bool = False   # SDK agents: True only on pipeline paths, from pipeline.auto_memory

# core/models.py
class SystemPromptMode(StrEnum):
    PRESET = "preset"; PRESET_APPEND = "preset+append"; CUSTOM = "custom"; EMPTY = "empty"
def describe_system_prompt(config: AgentConfig) -> SystemPromptMode: ...
def describe_setting_sources(setting_sources: Sequence[str] | None, *, is_sdk: bool) -> str: ...
def describe_run_settings(config: AgentConfig, *, is_sdk: bool) -> dict[str, object]: ...

# config/manager.py — bool config values (lenient: true/yes/on/1, false/no/off/0)
def get_typed_config(key: str, type_: type[bool], cwd: str = ".") -> bool: ...   # overload
```

The two policy constants have the same value today, but they are separate on purpose. They answer different questions and can diverge.

Differences from the draft contracts: `seed_context` takes a `SeedSource`; `sdk_settings_options` takes `base_env` and returns a TypedDict; the ledger and own-result helper live in `pipeline/sdk_turns.py` rather than `sdk_session.py`; the D7 tail lives in `pipeline/text_tail.py` rather than `dispatch_artifact.py`. An unreported digest value renders through the existing `_render_optional` sentinel, `not computed`, not `not reported` as drafted in C5.

## Integration Points

### Provides to Other Slices

- `open_pipeline_session` as the only way to build a pipeline session.
- `SystemPromptMode` / `describe_system_prompt` for any future path that needs to record its prompt.
- Declared settings constants for any new SDK path.

### Consumes from Other Slices

- The existing provider prompt table (#85, #40) and the PR-review `[]` override (slice 382 D8). Both stay as they are.
- The `each` batch report's flag-reason derivation (`_item_failure_reason`). It is used unchanged.

## Success Criteria

### Functional Requirements

- Rotation (`compact`, `emit: [rotate]`), resume seeding (connected and lazy), and `summary restore` send no `query()` to the fresh session. The fresh client's options carry the framed seed as preset `append`.
- Restore frames the summary once.
- A session dispatch whose turn ends with a `local_agent` task still running returns only after that task reaches a terminal status and the next result arrives. Its text includes the follow-up turn. A running `local_bash` task does not hold dispatch.
- A dispatch never returns on an injected turn's result. An injected turn consumed before its own result is dropped from the response and logged at WARNING with its tail.
- When no message arrives for `pipeline.background_idle_timeout_s` while background agents are tracked, dispatch stops them, logs a WARNING naming them, records `background_tasks_stopped`, and returns.
- A stream that ends before the dispatch's own result raises `ProviderError`. It never returns partial text as success.
- After a failed reconnect, every later call on the session raises `ProviderError` naming the reconnect failure.
- A dispatch-artifact post-condition failure message ends with the agent's final-text tail, and the batch report's flag reason shows it.
- An SDK one-shot dispatch with `system_prompt` builds `AgentConfig(use_default_system_prompt=True, instructions=<prompt>)`. The session path fails a step that sets `system_prompt`.
- Every path in the D10 table passes its declared `setting_sources` (never `None`).
- Auto-memory is on for pipeline sessions and dispatch when `pipeline.auto_memory` is true (the default) and off when it is false. It is off on every other path whatever the key says.
- Review artifacts always show the two new Run Digest lines, and JSON output has both keys. Dispatch and summary step metadata carry the mode and settings.

### Technical Requirements

- Unit tests with a fake `ClaudeSDKClient`. For rotation and seeding, assert on the options the new client was built with, and that the new client received no `query`. For dispatch waiting, feed scripted message sequences across two `receive_response()` calls: agent started, then result, then notification, then the follow-up result. Cover `TaskUpdatedMessage(killed)` as the only terminal signal, a `local_bash` start, and an injected result arriving first (its text absent from the response, WARNING asserted).
- Failure-mode tests, each asserting its observable signal:
  - the idle timeout, using a small timeout value and a fake client that goes silent. Assert `stop_task` was called per id, the WARNING, and `background_tasks_stopped`.
  - `stop_task` raising on the first of two tracked ids. Assert `logger.exception` for that id, `stop_task` still called for the second, and dispatch returning normally.
  - a stream that ends early, with a tracked agent and no own result. Assert `ProviderError` and the message naming the agent.
  - a reconnect failure. Assert `logger.exception` on the failing call, then `ProviderError("SDK session unusable…")` from the next `dispatch()`.
- The rate-limit retry behavior in `dispatch()` is unchanged. Existing tests pass as they are.
- Parametrized tests for `describe_system_prompt` over all four rows, and for D10 (one case per path, asserting `setting_sources` and the env).
- Digest rendering tests for each mode, plus `n/a (non-SDK)`.
- `ruff format`, `ruff check`, and `pyright` (strict), all clean.

### Integration Requirements

- `slices-plan` / `tasks-plan` batch runs rotate between items with no turn in between. A background-agent design step completes within its own dispatch.
- The `summary → compact → restore` pattern in `slice.yaml`/`tasks.yaml` still carries the summary into the next phase.

### Verification Walkthrough

Verified 20260928 against the implementation (Claude Code CLI bundled with claude-agent-sdk 0.2.160).

**Running a pipeline live from inside a Claude Code session.** `sq run` picks prompt-only mode when `CLAUDECODE` is set (`run.py:149`), so the SDK session path under test never runs. From an ordinary terminal no prefix is needed. From inside Claude Code, strip the session variables:

```bash
SQ_ENV="env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_CHILD_SESSION \
  -u CLAUDE_CODE_SESSION_ATTENDED -u CLAUDE_CODE_MESSAGING_SOCKET -u CLAUDE_CODE_MESSAGING_TOKEN \
  -u CLAUDE_PID -u CLAUDE_CODE_EXECPATH"
```

**Scratch repo.** The pipeline pre-flight needs a Context Forge project, so register a throwaway repo (a lite project):

```bash
mkdir -p /tmp/sq932-scratch && cd /tmp/sq932-scratch && git init -q
echo "# scratch" > README.md && git add . && git commit -qm init
cf init --lite --name sq932-scratch && git add -A && git commit -qm "cf init"
```

**1. Settings default (D9, done at design time).** In a scratch directory whose `CLAUDE.md` says `The project codeword is PELICAN-SEVEN.`:

```bash
Q='From your system context only, no tools: 1) project codeword? 2) is there a section titled "Tool Use Discipline"? Reply: codeword=<x> tud=<YES|NO>'
claude -p "$Q" --model haiku                          # codeword=PELICAN-SEVEN tud=YES
claude -p "$Q" --model haiku --setting-sources project # codeword=PELICAN-SEVEN tud=NO
```

**2. Seeding without a turn (#162).** `/tmp/seed-check.yaml`:

```yaml
name: seed-check
description: slice 932 — rotation seeds without a turn
steps:
  - dispatch: { prompt: "Reply with the single word READY.", model: haiku }
  - summary: { template: item-reset, model: haiku, emit: [rotate] }
  - dispatch:
      prompt: "Quote, in one line, any text in your context about a previous batch item. Use no tools."
      model: haiku
```

```bash
cd /tmp/sq932-scratch && $SQ_ENV sq run /tmp/seed-check.yaml -v
```

Observed:
- The log shows `seeded fresh session via system prompt (101 chars, source: compact)`, and all three steps complete.
- The newest transcript under `~/.claude/projects/-private-tmp-sq932-scratch/` has these entries in order:
  - `user`: the third step's prompt, with no assistant turn before it.
  - `assistant`: `"The previous batch item is complete. Nothing from it carries forward; work only from the next prompt."` That is the `item-reset` line, so the seed was visible.
- `git log --oneline` shows only the two setup commits.

**3. Dispatch waits for a background agent (#163).** Add `src/a.py`, `src/b.py`, `src/c.py` to the scratch repo and commit them. Then `/tmp/bg-check.yaml`:

```yaml
name: bg-check
description: slice 932 — dispatch waits for a background agent
steps:
  - dispatch:
      model: opus
      prompt: >
        Launch an Explore agent with run_in_background set to true to count the
        .py files under src/. End your turn immediately, saying you are waiting.
        When it reports back, write the count to bg-check.txt.
```

```bash
cd /tmp/sq932-scratch && $SQ_ENV sq run /tmp/bg-check.yaml -v
```

Observed:
- The log shows `dispatch: turn ended with 1 background agent(s) running; waiting: Count .py files in src`.
- The step completes, and `bg-check.txt` contains `3`.
- The step metadata is in the run state file, not in `sq run --status latest`, which doesn't render metadata: `~/.config/squadron/runs/<run-id>.json` → `completed_steps[0].action_results[0].metadata` = `{'background_tasks_waited': 1, 'background_tasks_stopped': 0, 'system_prompt_mode': 'preset', 'setting_sources': 'project', 'auto_memory': True, ...}`.

Caveat: the step uses `opus` because the `sonnet` alias (`claude-sonnet-5-5`) failed `set_model` with "isn't described by this version's model catalog" on the bundled CLI. That is unrelated to this slice.

**Messages between turns (D5 timer question).** A direct `ClaudeSDKClient` probe prints every message across the two `receive_response()` calls. After the dispatch's own result, the stream carries the following, roughly every 2s:
- `TaskProgressMessage`
- the subagent's own `AssistantMessage`s (`parent_tool_use_id` set)
- `UserMessage`s (tool results)

Then come `TaskUpdatedMessage`, `TaskNotificationMessage`, the follow-up assistant text, and the injected `ResultMessage` (`origin={'kind': 'task-notification'}`). The idle timer therefore resets on subagent activity and bounds idle periods; it is not a total cap.

The probe also found that the subagent's final report text streams as an `AssistantMessage` with `parent_tool_use_id` set, and dispatch was joining it into the response. It is now excluded (`sdk_turns.DispatchTurns.collect`): only the main agent's prose is the response.

**4. Flag tail.** No cheap live command makes a phase dispatch skip its artifact on purpose. Proof by tests:

```bash
uv run pytest tests/pipeline/test_executor.py tests/pipeline/test_executor_each.py -k final_text -q   # 2 passed
```

**5. Prompt and settings recording (#155, #156).** A saved run overwrites the committed review artifact, so either restore it afterwards (`git checkout -- project-documents/user/reviews/` and delete the new archive copy) or use `--no-save` for the JSON check. The recording does not depend on the model.

```bash
sq review slice 932 --model haiku -v            # saved artifact's Run Digest:
                                                #   - Output budget: backend default
                                                #   - System prompt: preset+append
                                                #   - Settings sources: project
sq review slice 932 --model haiku --no-save --output json | python3 -c \
  'import json,sys; t=sys.stdin.read(); d=json.loads(t[t.index("{"):]); print(d["system_prompt_mode"], d["setting_sources"])'
                                                # preset+append project
```

`--output file` writes JSON, not the markdown artifact, so the digest check needs a saved run.

## Implementation Notes

### Development Approach

Order by damage prevented. Each part is one or more commits that pass the full suite on their own.

1. **A — Seeding** (#162): session builder, `_reconnect`, resume and lazy seed, restore framing. Effort 3.
2. **B — Background wait and flag tail** (#163). Effort 3.
3. **D — Settings policy** (#156, settings half): `providers/sdk/settings.py`, templates, provider auto-memory rule, and the builder picking up the settings. Effort 2.
4. **C + recording** (#155, #156 recording): dispatch preset+append, session guard, `SystemPromptMode`, digest and JSON, metadata. Effort 2.

Existing tests that assert seeding goes through `dispatch()` (compact, emit rotate, restore, resume) are rewritten to assert on client options instead. That change is the point of this slice, so it does not count as a regression.

At release, the CHANGELOG gets one user-facing line for Part D: pipeline runs and all reviews load project settings only, so user CLAUDE.md and user settings no longer apply, and `pipeline.auto_memory` controls memory for pipeline work.

### Special Considerations

- **Security.** Part A is a safety fix. Before it, any seed text, including an empty-task seed like `item-reset`, gave a `bypassPermissions` session a free turn with push rights. After it, the seed cannot start any action.
- A seed is passed on the command line (`--append-system-prompt`). Linux caps a single argument at 128 KiB. Summaries are a few KB, and a seed over that limit fails the spawn with a visible error (D13). It is not silently truncated.
