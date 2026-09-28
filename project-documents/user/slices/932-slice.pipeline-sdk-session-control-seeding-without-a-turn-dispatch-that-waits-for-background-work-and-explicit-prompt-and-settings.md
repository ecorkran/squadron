---
docType: slice-design
slice: pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
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

**Out of scope**

- The summary-capture turn in the old session (`capture_summary`). It answers an explicit "summarize" instruction, so it is a real task, not a free turn. It stays as is.
- One-shot dispatch in `query` mode (`ClaudeSDKAgent._handle_query_mode`). The SDK's own `query()` already keeps stdin open while background agents run (`wait_for_result_and_end_input`, `DEFERRING_TASK_TYPES` in `claude_agent_sdk/_internal/query.py`). #163 applies to the persistent session path only.
- Background *shells* (`Bash(run_in_background=true)`) and monitors. They can run forever by design, and the SDK also refuses to wait on them. Dispatch does not wait for them either (D5).
- `sq serve` agent spawning (`server/routes/agents.py`) and the auth probe (`providers/auth.py`). The API caller supplies the config for the first, and the second does no prompt work. Neither is an automated pipeline or review path.
- A `system_prompt_mode: replace` escape hatch. No shipped or user pipeline sets a dispatch `system_prompt` (checked under `src/squadron/data/pipelines/` and `~/.config/squadron/pipelines/`), so nothing needs one.

## Dependencies

### Prerequisites

- None. Slice 931 (designed, not implemented) also adds Run Digest lines and `AgentConfig` fields. The two slices touch neighboring lines but share no logic. Whichever slice merges second rebases.

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
| `config/keys.py` | New key `pipeline.auto_memory` (bool, default `true`). |
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
        origin is None or kind == "human" → own_result_seen = True
        own_result_seen and ledger empty  → return joined text
        else                              → log once, read the next turn
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

No new wait ceiling is added. A background agent that hangs holds dispatch just as a hanging foreground turn does today. The wait is visible, though: the first time a result arrives with the ledger non-empty, dispatch logs at INFO: `dispatch: turn ended with N background agent(s) running; waiting: <descriptions>`.

The rejected alternative is to disallow background agents. The CLI has no per-parameter switch for `run_in_background`, and blocking the `Agent` tool would also remove foreground subagents.

### D6 — Only the dispatch's own result can end it

`ResultMessage.origin` tells a result for our prompt (`None` or `{"kind": "human"}`) apart from the result of an injected turn (`{"kind": "task-notification"}`). There is a race the SDK documents (#1190): a background agent can finish just before our result, leaving the ledger empty while a follow-up turn is still owed. That follow-up then arrives at the start of the *next* dispatch's stream. Because injected results never end a dispatch, the next dispatch reads past it to its own result. Dispatch logs a WARNING when it consumes an injected turn before its own result, since that text belongs to the previous step.

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

Pipelines and reviews run on the project's conventions, not on the operator's personal setup. A run should produce the same artifacts whoever starts it, and personal settings such as the output style should not shape pipeline output. The rejected alternative is `user,project` for pipeline sessions. It would keep the operator's global CLAUDE.md in every dispatch, and it is a single constant change if the PM prefers it.

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
| Reconnect with seed fails (CLI spawn, E2BIG on a huge seed) | Exception propagates as today. Compact/emit/restore report a failed step with the error and log via `logger.exception`. |
| Background agent never finishes | Dispatch waits. The INFO line names the agent(s) being waited on. |
| Background agent fails or is killed | A terminal status clears it. The follow-up turn's text is in the response, and the D7 tail shows it if no artifact was written. |
| Injected turn consumed at the start of a dispatch | WARNING naming the step. |
| Step `system_prompt` on the session path | Step fails with an explicit error. |
| Custom template with no `setting_sources` | Resolves to `REVIEW_SETTING_SOURCES`, and the Run Digest shows it. |

## Implementation Details

### API Contracts

```python
# pipeline/sdk_session.py
async def open_pipeline_session(*, seed: str | None = None) -> SDKExecutionSession: ...

class SDKExecutionSession:
    client: ClaudeSDKClient
    base_options: ClaudeAgentOptions        # renamed from `options`
    async def compact(self, instructions: str, summary_model: str | None = None,
                      restore_model: str | None = None, summary: str | None = None) -> str: ...
    async def seed_context(self, text: str) -> None:   # rotate; caller passes raw text
    async def dispatch(self, prompt: str) -> str:       # waits per D5/D6
    background_tasks_waited: int                        # set by the last dispatch()

# providers/sdk/settings.py
PIPELINE_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)
REVIEW_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)
def sdk_settings_options(setting_sources: Sequence[str], *, auto_memory: bool) -> dict[str, object]: ...

# core/models.py — AgentConfig
auto_memory: bool = False   # SDK agents: True only on pipeline paths, from pipeline.auto_memory

# core/models.py
class SystemPromptMode(StrEnum):
    PRESET = "preset"; PRESET_APPEND = "preset+append"; CUSTOM = "custom"; EMPTY = "empty"
def describe_system_prompt(config: AgentConfig) -> SystemPromptMode: ...
```

The two policy constants have the same value today, but they are separate on purpose. They answer different questions and can diverge.

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
- A dispatch never returns on an injected turn's result. Consuming one before its own result logs a WARNING.
- A dispatch-artifact post-condition failure message ends with the agent's final-text tail, and the batch report's flag reason shows it.
- An SDK one-shot dispatch with `system_prompt` builds `AgentConfig(use_default_system_prompt=True, instructions=<prompt>)`. The session path fails a step that sets `system_prompt`.
- Every path in the D10 table passes its declared `setting_sources` (never `None`).
- Auto-memory is on for pipeline sessions and dispatch when `pipeline.auto_memory` is true (the default) and off when it is false. It is off on every other path whatever the key says.
- Review artifacts always show the two new Run Digest lines, and JSON output has both keys. Dispatch and summary step metadata carry the mode and settings.

### Technical Requirements

- Unit tests with a fake `ClaudeSDKClient`. For rotation and seeding, assert on the options the new client was built with, and that the new client received no `query`. For dispatch waiting, feed scripted message sequences across two `receive_response()` calls: agent started, then result, then notification, then the follow-up result. Cover `TaskUpdatedMessage(killed)` as the only terminal signal, a `local_bash` start, and an injected result arriving first.
- The rate-limit retry behavior in `dispatch()` is unchanged. Existing tests pass as they are.
- Parametrized tests for `describe_system_prompt` over all four rows, and for D10 (one case per path, asserting `setting_sources` and the env).
- Digest rendering tests for each mode, plus `n/a (non-SDK)`.
- `ruff format`, `ruff check`, and `pyright` (strict), all clean.

### Integration Requirements

- `slices-plan` / `tasks-plan` batch runs rotate between items with no turn in between. A background-agent design step completes within its own dispatch.
- The `summary → compact → restore` pattern in `slice.yaml`/`tasks.yaml` still carries the summary into the next phase.

### Verification Walkthrough

Draft, to be refined after implementation.

**1. Settings default (D9, already done at design time).** Reproduce in a scratch directory that contains a `CLAUDE.md` with `The project codeword is PELICAN-SEVEN.`:

```bash
Q='From your system context only, no tools: 1) project codeword? 2) is there a section titled "Tool Use Discipline"? Reply: codeword=<x> tud=<YES|NO>'
claude -p "$Q" --model haiku                          # codeword=PELICAN-SEVEN tud=YES
claude -p "$Q" --model haiku --setting-sources project # codeword=PELICAN-SEVEN tud=NO
```

**2. Seeding without a turn (#162).** Save this as `/tmp/seed-check.yaml`:

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

Run `sq run /tmp/seed-check.yaml -v` from a scratch git repo. Then open the newest session transcript under `~/.claude/projects/<cwd-slug>/` (the second session of the run). Its first `user` entry is the third step's prompt, with no assistant turn before it. The step's reply quotes the `item-reset` line, which proves the seed was visible. `git log` in the scratch repo shows no new commits.

**3. Dispatch waits for a background agent (#163).** Add one step:

```yaml
  - dispatch:
      model: sonnet
      prompt: >
        Launch an Explore agent with run_in_background set to true to count the
        .py files under src/. End your turn immediately, saying you are waiting.
        When it reports back, write the count to bg-check.txt.
```

Expected: the log shows `dispatch: turn ended with 1 background agent(s) running; waiting: …`, and `bg-check.txt` exists when the step completes. The step metadata in `sq run --status latest` shows `background_tasks_waited: 1`.

**4. Flag tail.** No cheap command makes a phase dispatch skip its artifact on purpose. The proof is `uv run pytest tests/pipeline/test_executor.py tests/pipeline/test_executor_each.py -k final_text` (post-condition message and batch-report reason). On the next real batch run, any FLAGGED line and its batch-report reason end with `agent's final text: "…"`.

**5. Prompt and settings recording (#155, #156).**

```bash
sq review slice 932 --model sonnet -v
```

The artifact's Run Digest shows `System prompt: preset+append` and `Settings sources: project`. `sq review slice 932 --model sonnet --output json | jq '.system_prompt_mode, .setting_sources'` prints the same values.

## Implementation Notes

### Development Approach

Order by damage prevented. Each part is one or more commits that pass the full suite on their own.

1. **A — Seeding** (#162): session builder, `_reconnect`, resume and lazy seed, restore framing. Effort 3.
2. **B — Background wait and flag tail** (#163). Effort 3.
3. **D — Settings policy** (#156, settings half): `providers/sdk/settings.py`, templates, provider auto-memory rule, and the builder picking up the settings. Effort 2.
4. **C + recording** (#155, #156 recording): dispatch preset+append, session guard, `SystemPromptMode`, digest and JSON, metadata. Effort 2.

Existing tests that assert seeding goes through `dispatch()` (compact, emit rotate, restore, resume) are rewritten to assert on client options instead. That change is the point of this slice, so it does not count as a regression.

### Special Considerations

- **Security.** Part A is a safety fix. Before it, any seed text, including an empty-task seed like `item-reset`, gave a `bypassPermissions` session a free turn with push rights. After it, the seed cannot start any action.
- A seed is passed on the command line (`--append-system-prompt`). Linux caps a single argument at 128 KiB. Summaries are a few KB, and a seed over that limit fails the spawn with a visible error (D13). It is not silently truncated.
