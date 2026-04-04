---
docType: slice-design
slice: sdk-pipeline-executor
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [154-prompt-only-loops]
interfaces: [152-pipeline-documentation]
dateCreated: 20260404
dateUpdated: 20260404
status: draft
---

# Slice Design: SDK Pipeline Executor

## Overview

Add a fully automated pipeline execution mode that uses `ClaudeSDKClient` to dispatch work, switch models per step via `set_model()`, and manage context compaction via the server-side `context_management` API. This runs from straight CLI only (`sq run slice 154`) — outside any Claude Code session.

The prompt-only mode (slices 153-154) is the interactive bridge for IDE and Claude Code CLI sessions where a human-in-the-loop executes instructions. This slice builds the autonomous path where the SDK client is the runtime — no human needed except at checkpoints.

## Value

- **Full automation**: `sq run slice 154` executes the entire pipeline without human intervention — design, review, checkpoint gates, compaction, commit, devlog.
- **Per-step model switching**: Expensive models (opus) for design, cheap models (haiku/sonnet) for task breakdown. `set_model()` changes the model mid-session without spawning a new process.
- **Managed compaction**: Server-side compaction via `context_management` API with pipeline-defined instructions from compact templates. No slash commands, no context loss.
- **Review integration**: Reviews already work via SDK subprocess dispatch. This executor runs outside Claude Code, so the "no nested sessions" restriction doesn't apply.

## Technical Scope

### In Scope

1. **SDK dispatch action mode** — Extend the existing dispatch action to support a persistent `ClaudeSDKClient` session across multiple dispatch actions within a pipeline run. The client is created once and reused.
2. **Per-step model switching** — Call `client.set_model(model_alias)` before each dispatch action based on the resolved model from the cascade chain.
3. **Server-side compaction** — Replace the compact action's CF-based compaction with the `context_management` API (`compact_20260112` beta). Use `pause_after_compaction: true` to inject pipeline state after compaction. Pass `instructions` from the compact template's `resolved_instructions`.
4. **SDK executor entry point** — The default execution mode for `sq run` when not using `--prompt-only`. Detects that it's running outside Claude Code (no `CLAUDECODE` env var) and uses the SDK client path.
5. **Checkpoint behavior** — When a checkpoint triggers, the executor pauses, persists state, and exits with a specific exit code. The user resumes with `sq run --resume`.

### Out of Scope

- Running inside Claude Code sessions (blocked by nested session restriction).
- Model pools or pool selection strategies (160 scope).
- Convergence loop strategies beyond basic max-iteration (160 scope).
- Multi-agent coordination or parallel dispatch.
- Custom tool registration for SDK agents.

## Architecture

### SDK Client Lifecycle

The key architectural decision is client lifecycle management. Today, the dispatch action creates a one-shot agent per dispatch, sends one message, and shuts it down. For SDK execution, we need a persistent client that survives across steps.

```
Pipeline start
  |
  v
Create ClaudeSDKClient(options)
  |
  v
client.connect()
  |
  +---> Step 1 (design): client.set_model("opus") -> client.query(prompt)
  |
  +---> Step 2 (tasks):  client.set_model("sonnet") -> client.query(prompt)
  |
  +---> Step 3 (compact): [compaction via context_management on next query]
  |
  +---> Step 4 (implement): client.set_model("sonnet") -> client.query(prompt)
  |
  v
client.disconnect()
```

The client is owned by a new `SDKExecutionSession` that wraps the pipeline executor. It is NOT owned by individual actions — actions receive a reference to the active session.

### SDKExecutionSession

```python
@dataclass
class SDKExecutionSession:
    """Manages a persistent ClaudeSDKClient across pipeline steps."""

    client: ClaudeSDKClient
    current_model: str | None = None

    async def set_model(self, model_alias: str) -> None:
        """Switch model if different from current."""
        if model_alias != self.current_model:
            await self.client.set_model(model_alias)
            self.current_model = model_alias

    async def dispatch(self, prompt: str) -> str:
        """Send a prompt and collect the response."""
        await self.client.query(prompt)
        response_parts = []
        async for msg in self.client.receive_response():
            response_parts.append(extract_text(msg))
        return "".join(response_parts)
```

### Dispatch Action Changes

The dispatch action gains a conditional path. When an `SDKExecutionSession` is present in the `ActionContext`, it uses the session's client instead of spawning a new agent:

```python
async def _dispatch(self, context: ActionContext) -> ActionResult:
    session = context.sdk_session  # None in prompt-only or non-SDK mode
    if session is not None:
        return await self._dispatch_via_session(context, session)
    return await self._dispatch_via_agent(context)  # existing path
```

The existing one-shot agent path remains unchanged for reviews and non-SDK providers.

### Compact Action Changes

The compact action currently calls CF for compaction. In SDK mode, compaction happens at the API level via `context_management`. The compact action's role changes:

1. Resolve the compaction template and render instructions (existing logic, unchanged).
2. Configure `context_management` on the SDK session for the next query.
3. The next `client.query()` call triggers server-side compaction automatically.

```python
# In compact action, SDK mode:
session.configure_compaction(
    instructions=resolved_instructions,
    trigger_tokens=50_000,  # low threshold to force immediate compaction
    pause_after=True,
)
# Next dispatch query will compact and pause, allowing state injection
```

The `pause_after_compaction: true` flag is critical — it returns `stop_reason: "compaction"` after summarizing, letting us inject pipeline state (current step, params, etc.) before the model continues.

### Context Management API Integration

The compaction API uses the beta `compact_20260112` strategy:

```python
context_management = {
    "edits": [{
        "type": "compact_20260112",
        "trigger": {"type": "input_tokens", "value": trigger_tokens},
        "instructions": resolved_instructions,
        "pause_after_compaction": True,
    }]
}
```

Key behaviors:
- **`instructions`** completely replaces the default summary prompt. We pass the compact template's rendered text (e.g., "Keep slice design, task breakdown for slice 154").
- **`pause_after_compaction`** returns a compaction block, stopping the response. We can then inject additional context before continuing.
- **`trigger`** threshold: for explicit compact steps, set low (e.g., 50,000) to force immediate compaction. For background compaction during long dispatch steps, use higher thresholds.

**Integration with ClaudeSDKClient**: The SDK client manages messages internally. We need to determine whether `context_management` can be passed through `ClaudeAgentOptions` or needs to be set per-query. This is the primary integration risk — the SDK may not expose this parameter yet.

**Fallback**: If `context_management` is not available through the SDK client, fall back to ending the session and starting a new one with a compacted system prompt. This is less elegant but functionally equivalent.

### ActionContext Extension

`ActionContext` gains one optional field:

```python
@dataclass
class ActionContext:
    # ... existing fields ...
    sdk_session: SDKExecutionSession | None = None
```

This is `None` for prompt-only mode and non-SDK execution. Actions check for it and fall back to their existing behavior.

### Execution Flow

```
User runs: sq run slice 154

  1. Load pipeline definition
  2. Validate pipeline
  3. Check environment: CLAUDECODE not set → use SDK executor
  4. Init run via StateManager
  5. Create SDKExecutionSession(ClaudeSDKClient)
  6. client.connect()

  For each step:
    7. Expand step type → action sequence
    8. For dispatch actions:
       - Resolve model via cascade chain
       - session.set_model(resolved_alias)
       - session.dispatch(prompt from cf build)
    9. For review actions:
       - Run via existing review system (spawns subprocess)
    10. For compact actions:
       - Configure context_management on session
       - Next dispatch triggers compaction
    11. For checkpoint actions:
       - Evaluate trigger condition
       - If triggered: persist state, disconnect, exit
    12. For commit actions:
       - Run git commands (no SDK involvement)
    13. Record step result in state

  14. client.disconnect()
  15. Finalize run state
```

### Environment Detection

The executor determines the execution mode:

```python
def _resolve_execution_mode(prompt_only: bool) -> str:
    if prompt_only:
        return "prompt-only"
    if os.environ.get("CLAUDECODE"):
        raise EnvironmentError(
            "SDK pipeline execution cannot run inside a Claude Code session. "
            "Use --prompt-only mode or run from a standard terminal."
        )
    return "sdk"
```

This provides a clear error instead of the cryptic "cannot be launched inside another Claude Code session" message.

### Prompt Assembly for Dispatch

Each dispatch action needs a prompt. In prompt-only mode, the human reads the `cf build` output and acts on it. In SDK mode, the executor:

1. Runs `cf build` to get the context prompt.
2. Wraps it with step-specific instructions (e.g., "Create the slice design document").
3. Sends it to the SDK client via `session.dispatch(prompt)`.

The step-specific instructions come from the step type expansion — each phase step type already knows what the dispatch should do (design, tasks, implement). This text is currently only in the prompt-only `ActionInstruction.instruction` field. We reuse it as the dispatch prompt suffix.

## Technical Decisions

### Client Per Pipeline, Not Per Step

A single `ClaudeSDKClient` session spans the pipeline run. This is a **runtime optimization** — the model benefits from retaining context from earlier steps, but no step semantically depends on prior conversation state. If the session is interrupted (checkpoint, crash), resume rebuilds context from CF + pipeline state, as the architecture prescribes.

This is distinct from conversation persistence (160 scope), which would make steps *depend* on specific prior conversation state for correctness (e.g., retry loops that need the model to remember what it tried). Here, each step could function with a fresh session; the persistent session simply avoids redundant context rebuilding and enables `set_model()`.

See architecture update: "Interaction with Conversations" section in `140-arch.pipeline-foundation.md`.

### SDK Client Owns Compaction

Compact steps don't call CF for compaction. They configure `context_management` on the SDK session. This is cleaner — the API handles summarization natively, using the same model that's doing the work. CF compaction templates provide the `instructions` text but the execution is API-level.

### Checkpoint Exits the Process

When a checkpoint triggers in SDK mode, the executor disconnects the client and exits. Resume creates a new session. This is acceptable because:
- Checkpoints are designed for human decision points.
- The compaction API preserves relevant context.
- State is persisted — resume picks up where it left off.
- Keeping an SDK session alive while waiting for human input wastes resources.

### Reviews Stay Subprocess-Based

Reviews use external models (minimax, etc.) via the existing review system. They don't go through the SDK client. This is correct because:
- Reviews need their own model (not the dispatch model).
- The review system already handles provider routing, template rendering, and finding persistence.
- Reviews spawn a subprocess — which works fine from straight CLI.

## Success Criteria

1. `sq run slice 154` from a standard terminal executes the full slice lifecycle pipeline using `ClaudeSDKClient` — no human intervention except at checkpoints.
2. Each step uses the model specified in the pipeline YAML via `set_model()`. Running with `-v` shows model switches in the output.
3. Compact steps trigger server-side compaction with the resolved template instructions. Post-compaction context is smaller but preserves the information specified in the template.
4. Reviews execute via the existing review system with non-Claude models (minimax, etc.).
5. Checkpoints pause execution, persist state, and allow resume with `sq run --resume`.
6. Running `sq run` inside a Claude Code session shows a clear error directing the user to `--prompt-only` mode.
7. The existing one-shot dispatch path is unchanged — non-SDK providers (OpenAI, OpenRouter) still work.

## Verification Walkthrough

### 1. SDK execution from terminal

```bash
sq run test-pipeline 154
```

**Expected**: Pipeline runs autonomously. Design step uses the pipeline's specified model. Review runs via minimax. Compact step triggers API-level compaction. Pipeline completes with all steps recorded in state.

### 2. Model switching verification

```bash
sq run test-pipeline 154 -v
```

**Expected**: Verbose output shows `set_model(haiku)` before design dispatch, `set_model(haiku)` before tasks dispatch (or whatever the pipeline specifies). Model changes are logged.

### 3. Checkpoint and resume

```bash
# Pipeline with always-checkpoint:
sq run test-pipeline 154
# Hits checkpoint after tasks step → exits with state persisted

sq run --resume <run-id>
# Resumes from compact step
```

### 4. Inside Claude Code rejection

```bash
# From within a Claude Code session:
sq run test-pipeline 154
```

**Expected**: Clear error message: "SDK pipeline execution cannot run inside a Claude Code session. Use --prompt-only mode or run from a standard terminal."

### 5. Compaction with custom instructions

```bash
sq run slice 154 -v
```

**Expected**: At compact step, verbose output shows the resolved instructions from the compact template being passed to `context_management.instructions`. Post-compaction, the model retains slice design and task context per the template.

## Implementation Details

### New Module: `src/squadron/pipeline/sdk_session.py`

Contains `SDKExecutionSession` — the persistent client wrapper with `set_model()`, `dispatch()`, `configure_compaction()`, and lifecycle management. ~150-200 lines.

### Changes to `src/squadron/pipeline/actions/dispatch.py`

- Add `_dispatch_via_session()` method that uses `SDKExecutionSession` instead of spawning a one-shot agent.
- Check `context.sdk_session` to determine which path to use.
- ~50 lines added.

### Changes to `src/squadron/pipeline/actions/compact.py`

- Add SDK compaction path that configures `context_management` on the session.
- Existing CF compaction path remains for non-SDK execution.
- ~30 lines added.

### Changes to `src/squadron/pipeline/models.py`

- Add `sdk_session` field to `ActionContext` (optional, default `None`).
- ~5 lines.

### Changes to `src/squadron/cli/commands/run.py`

- Add environment detection logic.
- Create `SDKExecutionSession` when running in SDK mode.
- Wire session into executor's `ActionContext`.
- Add clear error for Claude Code session detection.
- ~40 lines added.

### Implementation Notes

1. Build `sdk_session.py` with unit tests — mock `ClaudeSDKClient` to test lifecycle, model switching, response collection.
2. Extend dispatch action with session path — test with mock session.
3. Extend compact action with `context_management` configuration.
4. Wire into CLI — integration test with real `ClaudeSDKClient` (requires being outside Claude Code).
5. End-to-end test with `test-pipeline`.

### Risks

- **`context_management` not exposed via SDK client**: The `ClaudeSDKClient` may not accept `context_management` parameters. Mitigation: fall back to session restart with compacted system prompt. Investigation needed before implementation.
- **Beta API stability**: `compact_20260112` is a beta feature. API may change. Mitigation: isolate behind `sdk_session.configure_compaction()` so changes are localized.

### Effort

3/5 — The core dispatch path is straightforward (persistent client with `set_model()`). Compaction integration has the most uncertainty due to SDK client API surface. The existing action protocol and executor are fully reusable.
