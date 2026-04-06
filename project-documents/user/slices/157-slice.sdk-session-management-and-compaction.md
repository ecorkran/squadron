---
docType: slice-design
slice: sdk-session-management-and-compaction
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [155-sdk-pipeline-executor, 156-pipeline-executor-hardening]
interfaces: [152-pipeline-documentation]
dateCreated: 20260406
dateUpdated: 20260406
status: not_started
---

# Slice Design: SDK Session Management and Compaction

## Overview

Replace the unconnected `configure_compaction()` stub from slice 155 with working context compaction via session rotation. When a compact step executes in SDK mode, the current session's model is switched to a cheap summarizer, the compact template instructions are sent as a query, the summary response is captured, the session is disconnected, and a fresh session continues with the summary as its opening context.

Additionally, wire the Agent SDK `PreCompact` hook so that interactive pipeline sessions (prompt-only mode where the user types `/compact`) automatically receive the pipeline's compact template instructions instead of requiring the user to type them manually.

## Value

- **Deterministic compaction at step boundaries**: Compaction happens exactly where the pipeline author placed the compact step — not at arbitrary token thresholds. This prevents context loss mid-phase (e.g., losing design context during task breakdown).
- **Cost savings via summarization model**: The compact YAML can specify a cheap model (haiku) for summarization, avoiding the cost of using opus/sonnet to compress context.
- **Interactive quality-of-life**: When users type `/compact` during prompt-only pipeline work, they get pipeline-aware compaction instructions automatically via the `PreCompact` hook.

## Technical Scope

### In Scope

1. **Session rotate compaction** — Replace the `configure_compaction()` stub with a working implementation that: switches model, queries with compact instructions, captures summary, disconnects, reconnects fresh with summary context.
2. **Session ID capture** — Extract `session_id` from `ResultMessage` during dispatch so the session can be identified for logging and diagnostics.
3. **Compact YAML `model` field** — Optional model alias for the summarization query. Validated at load time like other model aliases.
4. **`PreCompact` hook wiring** — Register a `PreCompact` hook via `ClaudeAgentOptions.hooks` that returns the current pipeline's compact template instructions when Claude Code's internal compaction fires.
5. **Cleanup of `configure_compaction()` stub** — Remove the unused `_compaction_config` field and `configure_compaction()` method from `SDKExecutionSession`.

### Out of Scope

- Controlling Claude Code's internal compaction threshold (no API exposed).
- Server-side `context_management` API integration (Agent SDK doesn't expose it).
- Manual compaction triggering from SDK mode (no `compact()` method on `ClaudeSDKClient`).
- `PostCompact` hook (doesn't exist in the SDK).
- Pipeline artifact summary action (separate future work).

## Architecture

### Session Rotate Flow

```
Compact step executes:
  |
  1. Resolve compact template → render instructions with pipeline params
  2. Resolve summarization model (compact YAML `model` field, or fallback)
  |
  3. session.set_model(summarization_model)   ← cheap model (e.g. haiku)
  4. session.dispatch(compact_instructions)    ← ask current session to summarize
  5. Capture summary text from response
  |
  6. session.disconnect()                      ← done with old conversation
  |
  7. Create new ClaudeSDKClient + SDKExecutionSession
  8. new_session.connect()
  9. new_session.set_model(next_step_model)    ← restore to pipeline model
  10. new_session.dispatch(summary_as_context)  ← seed new conversation
  |
  Continue pipeline with new session
```

Key insight from PM: we summarize in the **current** session (step 3-5) rather than disconnecting first and resuming. The model that did the work has the best understanding of what happened. No need to resume the old conversation in a new process just to read it — we already have it live.

### SDKExecutionSession Changes

The session gains two capabilities:

```python
@dataclass
class SDKExecutionSession:
    client: ClaudeSDKClient
    current_model: str | None = None
    session_id: str | None = None       # captured from ResultMessage

    async def compact(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
    ) -> str:
        """Perform session-rotate compaction.

        1. Switch to summary_model (if specified).
        2. Query with compact instructions.
        3. Capture summary from response.
        4. Disconnect current session.
        5. Create and connect a new session.
        6. Seed new session with summary.
        7. Restore model to restore_model (if specified).

        Returns the summary text for logging/diagnostics.
        """
        ...
```

The `compact()` method owns the full rotate lifecycle. It replaces `configure_compaction()` which is deleted.

The `session_id` field is populated from `ResultMessage.session_id` during `dispatch()`. This is captured for logging and diagnostics — not used for resume (we don't resume the old session, we start fresh).

### Compact Action Changes

The compact action's SDK path changes from configuring a stub to actually performing compaction:

```python
# Current (stub — does nothing):
if context.sdk_session is not None:
    context.sdk_session.configure_compaction(...)
    return ActionResult(success=True, ...)

# New (performs session rotate):
if context.sdk_session is not None:
    summary_model = str(context.params.get("model", "")) or None
    summary = await context.sdk_session.compact(
        instructions=instructions,
        summary_model=summary_model_id,
        restore_model=current_pipeline_model,
    )
    return ActionResult(
        success=True,
        outputs={"summary": summary, "instructions": instructions},
    )
```

The `model` param in compact config is the summarization model. It goes through the same model alias resolution as dispatch and review model params.

### Compact YAML `model` Field

Pipeline authors can specify a model for summarization:

```yaml
steps:
  - compact:
      template: minimal
      model: haiku          # ← new: use haiku for cheaper summarization
```

When omitted, the summarization query uses whatever model the session currently has active (typically the dispatch model from the previous step).

Validation: the `model` field is validated by `_validate_model_alias` in `validate_pipeline`, same as step-level and action-level model aliases. The compact step's `validate()` method checks the field type.

### PreCompact Hook for Interactive Mode

When `_run_pipeline_sdk` creates the `ClaudeAgentOptions`, it registers a `PreCompact` hook that injects the pipeline's compact template instructions:

```python
async def _pre_compact_hook(
    input: PreCompactHookInput,
    result: str | None,
    context: HookContext,
) -> dict:
    """Inject pipeline compact instructions on user /compact."""
    return {"custom_instructions": rendered_instructions}

options = claude_agent_sdk.ClaudeAgentOptions(
    cwd=str(Path.cwd()),
    hooks={
        "PreCompact": [
            claude_agent_sdk.HookMatcher(
                matcher=None,  # match all compact events
                hooks=[_pre_compact_hook],
            )
        ]
    },
)
```

This fires when the user types `/compact` in interactive sessions. In SDK mode, auto-compaction may fire during very long individual steps — the hook provides best-effort instruction injection there too.

The hook needs access to the rendered compact instructions. These are resolved from the pipeline's compact step configuration at pipeline load time and stored on the session or passed via closure.

### Data Flow

```
Pipeline YAML compact step:
  template: "minimal"
  model: "haiku"
       |
       v
CompactAction.execute()
  → load_compaction_template("minimal")
  → render_instructions(template, pipeline_params)
  → resolve_model_alias("haiku") → model_id
       |
       v
SDKExecutionSession.compact(instructions, summary_model=model_id)
  → set_model(model_id)              # switch to haiku
  → dispatch(instructions)           # haiku summarizes the conversation
  → capture summary text
  → disconnect()                     # end old conversation
  → create new ClaudeSDKClient       # fresh conversation
  → connect()
  → dispatch(summary)                # seed new conversation with summary
  → set_model(restore_model)         # restore for next dispatch step
       |
       v
ActionResult(success=True, outputs={"summary": ..., "instructions": ...})
```

### State Management

The session rotate creates a new `ClaudeSDKClient` internally. The executor's reference to `sdk_session` must remain valid. Two approaches:

**Option A — Session replaces its own client**: `SDKExecutionSession.compact()` creates a new client, replaces `self.client`, and updates `self.session_id`. The executor's reference to the session object is unchanged. This is the simpler path.

**Option B — Executor provides a session factory**: The `compact()` method receives a factory callable to create new clients. More flexible but more complex.

**Decision**: Option A. The session owns its client lifecycle. The executor doesn't need to know that the underlying client changed. `compact()` is the only method that replaces the client, and it handles the full connect/disconnect/reconnect cycle internally.

The `ClaudeAgentOptions` used to create the replacement client must match the original (same `cwd`, `hooks`, etc.). The session stores the options at construction time for reuse.

## Technical Decisions

### Summarize in Current Session, Not via Resume

Resuming the old conversation in a new process would load the entire context just to summarize it — defeating the purpose. Instead, we query the current live session with the compact instructions. The model has full context and produces the best summary. Then we disconnect and start clean.

### Session Owns Client Replacement

The `SDKExecutionSession` replaces its own `ClaudeSDKClient` during compact. This keeps the executor unaware of the rotation — it just sees the same session object. The alternative (executor managing sessions) would spread lifecycle logic across two layers.

### Compact Model Is Optional

If no `model` is specified in the compact YAML, the session uses whatever model is currently active. This is fine for pipelines where the dispatch model is already cheap. For expensive models (opus dispatching design work), authors should specify `model: haiku` on the compact step to save tokens.

### PreCompact Hook Is Best-Effort

The `PreCompact` hook fires on Claude Code's internal compaction schedule, which we don't control. The hook provides pipeline-aware instructions but can't guarantee optimal timing. For SDK mode, session rotate at step boundaries is the primary compaction mechanism. The hook is a safety net for long individual steps and a quality-of-life feature for interactive `/compact` usage.

## Implementation Details

### Changes to `src/squadron/pipeline/sdk_session.py`

- Remove `_compaction_config` field and `configure_compaction()` method.
- Add `session_id: str | None` field, populated from `ResultMessage` during `dispatch()`.
- Add `_options: ClaudeAgentOptions` field, stored at construction for reuse during rotation.
- Add `compact()` method implementing the full session rotate flow.
- Update `dispatch()` to capture `session_id` from `ResultMessage`.
- ~80 lines changed/added.

### Changes to `src/squadron/pipeline/actions/compact.py`

- Replace the `configure_compaction()` stub call with `await context.sdk_session.compact(...)`.
- Add model resolution for the compact step's `model` param.
- Add `model` to `validate()` checks.
- ~20 lines changed.

### Changes to `src/squadron/pipeline/steps/compact.py`

- Pass through the `model` config field when expanding to the compact action.
- ~5 lines changed.

### Changes to `src/squadron/cli/commands/run.py`

- Pass `ClaudeAgentOptions` to `SDKExecutionSession` constructor (needed for client recreation during rotate).
- Register `PreCompact` hook in `ClaudeAgentOptions.hooks` with rendered compact instructions.
- Resolve compact instructions at pipeline load time for hook use.
- ~30 lines changed.

### Changes to `src/squadron/providers/sdk/translation.py`

- Capture `session_id` from `ResultMessage` in the translated message metadata.
- ~3 lines changed.

## Success Criteria

1. `sq run test-pipeline 154 -vv` with a compact step shows: model switch to summarization model, compact query, summary captured, session disconnected, new session connected, summary injected, model restored.
2. The summary text is visible in `-vv` output and stored in the step's `ActionResult.outputs`.
3. Compact step with `model: haiku` uses haiku for summarization, not the dispatch model.
4. Compact step without `model` uses the current session model.
5. Pipeline execution continues normally after compact — subsequent dispatch steps work with the new session.
6. Resume after checkpoint following a compact step works correctly (new session, not the old one).
7. `--validate` catches invalid model aliases in compact step `model` field.
8. `configure_compaction()` stub and `_compaction_config` field are removed.
9. All existing tests pass; new tests cover compact flow with mock SDK client.

## Verification Walkthrough

### 1. Session rotate compaction

```bash
sq run test-pipeline 154 -vv
```

**Expected output** at compact step:
```
action 5/7: compact template=minimal
  SDKExecutionSession: switched model to claude-haiku-4-5-20251001
  SDKExecutionSession: compact query sent (instructions: 42 chars)
  SDKExecutionSession: summary captured (387 chars)
  SDKExecutionSession: old session disconnected
  SDKExecutionSession: new session connected
  SDKExecutionSession: summary injected as context
    -> ok
    outputs={'summary': '...', 'instructions': '...'}
```

### 2. Compact with explicit model

```yaml
# test-pipeline.yaml
steps:
  - compact:
      template: minimal
      model: haiku
```

```bash
sq run test-pipeline 154 -vv
```

**Expected**: Compact step uses haiku for summarization regardless of what the previous dispatch used.

### 3. Pipeline continues after compact

```bash
sq run test-pipeline 154 -v
```

**Expected**: Steps after compact execute normally. The dispatch action uses the new session. The model is restored to whatever the next step specifies.

### 4. Validation

```bash
sq run test-pipeline --validate
```

**Expected**: Invalid model alias in compact `model` field is caught:
```
Validation errors for 'test-pipeline':
  steps[compact-4].model: Model alias 'bogus' did not resolve to a known alias
```

## Risk Assessment

### Technical Risks

- **New session context quality**: The summary injected into the fresh session may not preserve enough context for subsequent steps. Mitigation: compact templates are pipeline-author-controlled and can be tuned per pipeline. The `default` and `minimal` templates already exist with sensible defaults.
- **Client recreation in `compact()`**: Creating a new `ClaudeSDKClient` mid-pipeline means re-establishing the subprocess connection. If connect fails, the pipeline fails mid-run. Mitigation: the same connect/disconnect pattern is used at pipeline start — if it works there, it works here. Error handling in `compact()` should fail the step explicitly.

## Implementation Notes

### Development Approach

1. **Capture session_id in dispatch** — Update `dispatch()` to extract from `ResultMessage`. Small, testable change.
2. **Implement `compact()` method** — Core session rotate logic with mock tests. Store `_options` for client recreation.
3. **Wire compact action** — Replace stub with `compact()` call. Add model resolution.
4. **Add compact `model` field** — Step expansion, validation, YAML support.
5. **PreCompact hook** — Wire into `ClaudeAgentOptions` in `_run_pipeline_sdk`.
6. **Remove `configure_compaction()` stub** — Cleanup.
7. **End-to-end test** — Run `test-pipeline` with compact step and verify session rotation.
