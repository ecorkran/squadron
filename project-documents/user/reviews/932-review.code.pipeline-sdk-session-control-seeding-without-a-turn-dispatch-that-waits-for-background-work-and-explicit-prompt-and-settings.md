---
docType: review
layer: project
reviewType: code
slice: pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: d89cc060d2fe3033ed479d7e4eb69aadc779bd97
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: false
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: note
    category: behavior-change
    summary: "sq serve agents now default to auto-memory disabled"
    location: "src/squadron/providers/sdk/provider.py:81-88"
  - id: F002
    severity: note
    category: error-handling
    summary: "Idle timeout can also catch an unrelated TimeoutError"
    location: "src/squadron/pipeline/sdk_session.py:_collect_turns"
  - id: F003
    severity: note
    category: error-handling
    summary: "A failed disconnect in _reconnect does not mark the session unusable"
    location: "src/squadron/pipeline/sdk_session.py:_reconnect"
  - id: F004
    severity: note
    category: style
    summary: "Minor style items"
    location: "src/squadron/pipeline/persistence.py"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Exception handling and failure observability"
    location: "src/squadron/pipeline/sdk_session.py:_stop_background"
  - id: F006
    severity: pass
    category: design
    summary: "Design and DRY"
    location: "src/squadron/pipeline/sdk_session.py#open_pipeline_session"
  - id: F007
    severity: pass
    category: testing
    summary: "Test coverage"
    location: "tests/providers/sdk/test_settings_policy.py"
---

# Review: code — slice 932

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [NOTE] sq serve agents now default to auto-memory disabled

`create_agent` now always writes `env` through `sdk_settings_options(..., auto_memory=config.auto_memory)`. `AgentConfig.auto_memory` defaults to `False`, so any SDK agent built outside the pipeline, such as `sq serve` agents, gets `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. Before this change that variable was set only when `setting_sources == []`. The comment calls this an explicit per-path choice, and the `False` default is the safe direction. Confirm it is intended for the non-pipeline agents that pass `setting_sources=None`.

### [NOTE] Idle timeout can also catch an unrelated TimeoutError

While waiting on background agents, `except TimeoutError` wraps the whole `_read_turn_with_retry` call. A `TimeoutError` raised by the SDK or transport, rather than by `asyncio.timeout(idle_s)`, would also be read as an idle timeout. That would stop the agents and return partial text without saying which one fired. This is unlikely because the SDK wraps its own errors as `ClaudeSDKError`. If you want it airtight, catch the timeout only around the `anext` call in `_read_turn`.

### [NOTE] A failed disconnect in _reconnect does not mark the session unusable

`unusable_reason` is set only when `connect()` fails. If `self.disconnect()` raises at the top of `_reconnect`, the old client state is unknown and the session stays "usable". This matters only if `disconnect` can raise here. Decide whether it should be covered by the same guard.

### [NOTE] Minor style items

- `_PRESET_MODES` in `review/persistence.py` sits between `_NOT_COMPUTED` and `_NOT_OFFERED`, which belong together. Move it below them.
- `describe_system_prompt`'s docstring refers to "the four rows of the table above". That table is not in the diff, so the reference may be stale.

### [PASS] Exception handling and failure observability

- `_stop_background` catches `Exception` with a `BLE001` waiver, a comment explaining why, and `logger.exception`. That meets rule (b).
- A stream that ends while an agent is still tracked raises `ProviderError`.
- A leftover injected turn is discarded with a WARNING that includes the text.
- A failed reconnect is logged with `logger.exception`, recorded in `unusable_reason` and re-raised.
- Tests assert each of these paths, including the ones in batch flows.

### [PASS] Design and DRY

- Session construction was duplicated in `run.py` and the executor. It is now one `open_pipeline_session`.
- The settings policy lives in `providers/sdk/settings.py` and is recorded from the config actually spawned.
- `sdk_turns.py` is pure bookkeeping with no I/O. The tail logic is shared through `text_tail.py`.
- The old `options` field and the old single-argument `seed_context` have no remaining callers in `src`.
- The removed `default_system_prompt_preset_used` field has none either.
- `uses_preset` in `review_client.py` is still used.
- Line lengths fit the project's limit of 104.

### [PASS] Test coverage

- The per-path settings policy matrix covers every automated SDK path.
- The scripted-client fixtures use real SDK message types.
- Bool coercion, the CLI round trip, seed framing (applied exactly once) and lazy-session resume seeding are each covered.
- Tests do not touch the production database.

### Run Digest

- Response length: 4282 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response (20260928)

- **F001 — no change, intended.** D11 makes auto-memory an explicit per-path choice with `AgentConfig.auto_memory = False` as the default, so every path that doesn't opt in, `sq serve` agents and the auth probe included, runs with memory off. Only the pipeline session and one-shot SDK dispatch opt in, from `pipeline.auto_memory`.
- **F002 — fixed.** `_read_turn` now builds the `asyncio.timeout` before the `with` block and raises a private `_BackgroundIdleTimeout` only when that timer's `expired()` is true. Any other `TimeoutError` propagates. `_collect_turns` catches only `_BackgroundIdleTimeout`. Test: `test_unrelated_timeout_while_waiting_is_not_treated_as_idle`, which fails on the old code.
- **F003 — no change.** `SDKExecutionSession.disconnect()` is best-effort by design: it catches and logs every error and never raises. So `_reconnect` always reaches the new client, and only a failed `connect()` can leave the session without a live client. That is the case `unusable_reason` covers.
- **F004 — partly fixed.** `_PRESET_MODES` now sits below `_NOT_COMPUTED`/`_NOT_OFFERED`. The `describe_system_prompt` docstring is accurate as written: "the table above" is the four-row prompt table in the `AgentConfig` comment directly above it in `core/models.py`.
- F005–F007: pass, no action.
