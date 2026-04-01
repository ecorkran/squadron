---
docType: slice-design
slice: dispatch-action
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [142]
interfaces: [146, 147, 149]
dateCreated: 20260331
dateUpdated: 20260331
status: complete
---

# Slice Design: Dispatch Action (145)

## Overview

This slice implements the `dispatch` action — the pipeline's interface to language models. Dispatch resolves a model alias through the 5-level cascade (via `ModelResolver`), creates a one-shot agent through the provider registry, sends assembled context via `agent.handle_message()`, and captures the response with metadata (model used, token counts, profile). It is the only action that talks to external LLMs; all other actions are local I/O.

**Slice plan entry:** **(145) Dispatch Action** — Send assembled context to a model via agent registry, capture output (file artifacts or code changes), record metadata (model used, token counts). Integrates with model resolver for alias resolution through the cascade chain. Handles both SDK and API provider dispatch transparently through the AgentProvider protocol. Dependencies: [142, Agent Registry (102)]. Risk: Low. Effort: 2/5

---

## Value

- **Model access for pipelines.** Without dispatch, the pipeline system can only perform local operations (git, file I/O, CF CLI). Dispatch is what makes pipelines capable of generating code, reviews, and design artifacts.
- **Transparent provider routing.** The caller specifies a model alias (e.g. `sonnet`, `opus`, `gpt4o`); dispatch resolves it to a concrete model ID and profile, creates the appropriate agent, and returns the output. The pipeline step has no awareness of which provider is used.
- **Proven pattern.** The review system already dispatches to agents via the same `AgentProvider` → `create_agent()` → `handle_message()` → `shutdown()` path (`review_client.py`). Dispatch action formalizes this into a reusable pipeline action.

---

## Technical Scope

### Included

- `DispatchAction` class in `src/squadron/pipeline/actions/dispatch.py` satisfying the `Action` protocol
- Model resolution via `context.resolver.resolve()` with action-level and step-level overrides from `context.params`
- Agent creation via `AgentRegistry.spawn()` using resolved model and profile
- Message construction and dispatch via `agent.handle_message()`
- Response collection and assembly into `ActionResult.outputs`
- Metadata capture: resolved model ID, profile, token counts (when available from agent response metadata)
- Duplicate response deduplication (SDK providers emit both `AssistantMessage` and `ResultMessage`)
- Agent lifecycle: create → dispatch → shutdown (one-shot, no reuse)
- Auto-registration at module level

### Excluded

- Multi-turn conversations (each dispatch is a single send/receive)
- Streaming output (responses are collected then returned)
- File artifact extraction from agent output (future slice concern — dispatch returns raw text)
- Retry logic on transient failures (future scope)
- Model pool resolution (`pool:` prefix — 160 scope, `ModelResolver` already raises `ModelPoolNotImplemented`)

---

## Dependencies

### Prerequisites

- **Slice 142** (Pipeline Core Models) — `Action` protocol, `ActionType`, `ActionContext`, `ActionResult`, `ValidationError`, `ModelResolver`, action registry
- **Slice 102** (Agent Registry) — `AgentRegistry`, `get_registry()`, `AgentConfig`, `Message`, `MessageType`
- **Provider registry** — `get_provider()`, `get_profile()`, provider loading (`_ensure_provider_loaded`)

### Interfaces Required

- `ActionContext.resolver: ModelResolver` — cascade resolution returns `(model_id, profile_name)`
- `ActionContext.params: dict[str, object]` — carries `model`, `prompt`, `system_prompt`, and optional `profile` override
- `AgentRegistry.spawn(config: AgentConfig) -> Agent` — creates agent from config
- `Agent.handle_message(message: Message) -> AsyncIterator[Message]` — sends prompt, yields responses
- `Agent.shutdown() -> None` — cleans up agent resources

---

## Architecture

### Data Flow

```
context.params["prompt"] ─────────────────────────────────────────┐
                                                                   │
context.params.get("model") ──► ModelResolver.resolve() ──► (model_id, profile)
context.params.get("step_model")─┘                              │
                                                                  │
                              AgentConfig ◄──────────────────────┘
                                  │                               │
                     AgentRegistry.spawn(config) ──► Agent        │
                                                      │           │
                          Message(content=prompt) ─────┘           │
                                  │                                │
                     agent.handle_message(msg) ──► response text   │
                                  │                                │
                     agent.shutdown()                              │
                                  │                                │
                     ActionResult(                                 │
                       success=True,                               │
                       outputs={"response": text},                 │
                       metadata={"model": ..., "profile": ...}     │
                     )                                             │
```

### Key Design Decisions

**1. One-shot agent lifecycle**

Each dispatch creates a fresh agent, sends one message, collects the response, and shuts down. This matches the review system's pattern and avoids state leakage between pipeline steps. Agent reuse across steps is a future optimization.

**2. Model resolution via `context.resolver`**

The `ModelResolver` is already on `ActionContext` (slice 142). Dispatch calls `resolver.resolve(action_model, step_model)` where:
- `action_model` comes from `context.params.get("model")` — the action-level config
- `step_model` comes from `context.params.get("step_model")` — injected by the step type when expanding

This preserves the 5-level cascade: CLI → action → step → pipeline → config default.

**3. Profile resolution**

`resolve_model_alias()` returns `(model_id, profile_or_none)`. If a profile is returned, use it. If `context.params` contains an explicit `profile` override, use that instead. If neither provides a profile, default to `ProfileName.SDK`.

**4. System prompt from params**

The `system_prompt` for the agent comes from `context.params.get("system_prompt")`. This is assembled by the step type (slice 147) from CF context, pipeline instructions, etc. Dispatch does not assemble prompts — it sends what it receives.

**5. Deduplication of SDK responses**

SDK providers yield both an `AssistantMessage` and a `ResultMessage` with identical content. Dispatch skips messages where `metadata.get("sdk_type") == "result"`, matching the review system's existing behavior.

**6. Token metadata passthrough**

Agent response messages may carry token usage in `metadata` (e.g. `prompt_tokens`, `completion_tokens`). Dispatch extracts these into `ActionResult.metadata` when present, without requiring them.

---

## Implementation Details

### `DispatchAction` Class

```python
# src/squadron/pipeline/actions/dispatch.py

class DispatchAction:
    @property
    def action_type(self) -> str:
        return ActionType.DISPATCH

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        # "prompt" is required in config
        # "model" is optional (cascade handles defaults)
        # "system_prompt" is optional

    async def execute(self, context: ActionContext) -> ActionResult:
        # 1. Resolve model via context.resolver.resolve()
        # 2. Resolve profile from alias result or params override
        # 3. Build AgentConfig
        # 4. Spawn agent via get_registry().spawn()
        # 5. Send message, collect response (skip sdk_type="result" dupes)
        # 6. Shutdown agent
        # 7. Return ActionResult with response text and metadata

register_action(ActionType.DISPATCH, DispatchAction())
```

### Validate Behavior

- `"prompt"` key must be present in config — return `ValidationError(field="prompt", message="...", action_type="dispatch")` if missing
- No other required fields (model comes from cascade, system_prompt is optional)

### Execute Behavior

**Model resolution:**
```python
action_model = str(context.params["model"]) if "model" in context.params else None
step_model = str(context.params["step_model"]) if "step_model" in context.params else None
model_id, alias_profile = context.resolver.resolve(action_model, step_model)
```

**Profile resolution:**
```python
profile_name = (
    str(context.params["profile"])
    if "profile" in context.params
    else alias_profile or ProfileName.SDK
)
```

**Agent config construction:**
```python
profile = get_profile(profile_name)
_ensure_provider_loaded(profile.provider)

config = AgentConfig(
    name=f"dispatch-{context.step_name}-{context.run_id[:8]}",
    agent_type=profile.provider,
    provider=profile.provider,
    model=model_id,
    instructions=str(context.params.get("system_prompt", "")),
    base_url=profile.base_url,
    cwd=context.cwd,
    credentials={
        "api_key_env": profile.api_key_env,
        "default_headers": profile.default_headers,
    },
)
```

**Dispatch and response collection:**
```python
registry = get_registry()
agent = await registry.spawn(config)
try:
    message = Message(
        sender="pipeline",
        recipients=[config.name],
        content=str(context.params["prompt"]),
        message_type=MessageType.chat,
    )
    response_parts: list[str] = []
    token_metadata: dict[str, object] = {}
    async for response in agent.handle_message(message):
        if response.metadata.get("sdk_type") == "result":
            continue
        response_parts.append(response.content)
        # Capture token metadata from last response
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key in response.metadata:
                token_metadata[key] = response.metadata[key]
finally:
    await registry.shutdown_agent(config.name)
```

**Result construction:**
```python
response_text = "".join(response_parts)
return ActionResult(
    success=True,
    action_type=self.action_type,
    outputs={"response": response_text},
    metadata={
        "model": model_id,
        "profile": profile_name,
        **token_metadata,
    },
)
```

### Error Handling

| Error | Source | Handling |
|-------|--------|----------|
| `ModelResolutionError` | `resolver.resolve()` | Return `ActionResult(success=False, error=str(exc))` |
| `ModelPoolNotImplemented` | `resolver.resolve()` | Return `ActionResult(success=False, error=str(exc))` |
| `KeyError` from `get_profile()` | Unknown profile | Return `ActionResult(success=False, error=str(exc))` |
| `KeyError` from `get_provider()` | Provider not loaded | Return `ActionResult(success=False, error=str(exc))` |
| Any exception from `agent.handle_message()` | Provider/API failure | Return `ActionResult(success=False, error=str(exc))` |

All errors are caught and returned as `ActionResult(success=False)` — dispatch never raises. The `finally` block ensures agent shutdown even on failure.

### Provider Loading

The review system uses `_ensure_provider_loaded()` from `review_client.py` to lazily import and register providers. Dispatch needs the same capability. Two options:

1. **Extract** `_ensure_provider_loaded` to a shared location (e.g. `providers/registry.py` or `providers/loader.py`)
2. **Inline** the same pattern in dispatch

Option 1 is cleaner. The function is small (~10 lines) and already has two consumers (review_client, dispatch). Extract to `providers/loader.py` and import from both places.

```python
# src/squadron/providers/loader.py
def ensure_provider_loaded(provider_type: str) -> None:
    """Lazily import and register a provider if not already registered."""
```

This is a minor refactor of an existing private function — not a new feature.

---

## Integration Points

### Provides to Other Slices

- **Slice 146 (Review and Checkpoint)** — Slice 147 (Step Types) composes dispatch and review actions together in step sequences; the review action itself does not depend on dispatch
- **Slice 147 (Step Types)** — Phase step type expands to include a dispatch action in its action sequence
- **Slice 149 (Pipeline Executor)** — Executor invokes dispatch actions as part of step execution

### Consumes from Other Slices

- **Slice 142** — `Action` protocol, `ActionContext`, `ActionResult`, `ModelResolver`, action registry
- **Slice 102** — `AgentRegistry`, `AgentConfig`, `Message`, `MessageType`
- **Provider system** — `get_profile()`, `get_provider()`, provider implementations

---

## Success Criteria

### Functional Requirements

- [x] `DispatchAction` satisfies the `Action` protocol (`isinstance` check passes)
- [x] `action_type` returns `"dispatch"`
- [x] `validate()` returns error when `prompt` is missing from config
- [x] `validate()` returns empty list for valid config
- [x] `execute()` resolves model through `context.resolver.resolve()` with action-level and step-level params
- [x] `execute()` resolves profile from alias result, with explicit `profile` param override
- [x] `execute()` creates agent via registry, sends prompt, collects response
- [x] `execute()` deduplicates SDK `result` messages
- [x] `execute()` captures token metadata when available
- [x] `execute()` always shuts down agent (even on failure)
- [x] `execute()` returns `success=False` with error on any failure (never raises)
- [x] Auto-registers at module import time

### Technical Requirements

- [x] pyright clean (0 errors) on `src/squadron/pipeline/actions/dispatch.py`
- [x] ruff clean on the module
- [x] All existing tests continue to pass
- [x] New tests mock all external boundaries (no real API calls)
- [x] `_ensure_provider_loaded` extracted to shared location

### Verification Walkthrough

*Verified 2026-03-31. All steps pass.*

**1. Protocol compliance:**
```bash
python -c "
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.actions.dispatch import DispatchAction
a = DispatchAction()
print('protocol:', isinstance(a, Action))
print('type:', a.action_type)
"
# Output: protocol: True
# Output: type: dispatch
```

**2. Registration:**
```bash
python -c "
import squadron.pipeline.actions.dispatch
from squadron.pipeline.actions import list_actions
print('dispatch' in list_actions())
"
# Output: True
```

**3. Validation:**
```bash
python -c "
from squadron.pipeline.actions.dispatch import DispatchAction
a = DispatchAction()
print('missing prompt:', a.validate({}))
print('valid:', a.validate({'prompt': 'hello'}))
"
# Output: missing prompt: [ValidationError(field='prompt', message="'prompt' is required for dispatch action", action_type=<ActionType.DISPATCH: 'dispatch'>)]
# Output: valid: []
```

**4. Full test suite:**
```bash
python -m pytest tests/pipeline/actions/test_dispatch.py -v  # 17 passed
python -m pytest --tb=short -q  # 827 passed
pyright src/squadron/pipeline/actions/dispatch.py  # 0 errors
ruff check src/squadron/pipeline/actions/dispatch.py  # All checks passed
```

---

## Implementation Notes

### Development Approach

1. **Extract provider loader** — Move `_ensure_provider_loaded` from `review_client.py` to `providers/loader.py`, update review_client import
2. **Implement `DispatchAction`** — Validate and execute methods following the pattern from `CfOpAction`
3. **Write tests** — Mock `AgentRegistry`, `ModelResolver`, `get_profile`, and agent responses
4. **Integration test** — Verify registration alongside other actions

### Testing Strategy

All tests mock external boundaries:
- `ModelResolver.resolve()` — return known `(model_id, profile)` tuples
- `get_registry()` → mock `AgentRegistry` with mock `Agent`
- `Agent.handle_message()` — yield canned `Message` objects (including SDK dedup scenarios)
- `Agent.shutdown()` — verify called
- `get_profile()` — return a test `ProviderProfile`
- `ensure_provider_loaded()` — no-op mock

Test scenarios:
- Happy path: prompt dispatched, response captured, metadata recorded
- Missing prompt in config: validation error
- Model resolution failure: `success=False` with error
- Profile not found: `success=False` with error
- Agent error during dispatch: `success=False`, agent still shut down
- SDK dedup: `sdk_type="result"` messages filtered out
- Token metadata passthrough: prompt_tokens/completion_tokens extracted from response metadata
- Profile override: explicit `profile` param takes precedence over alias-derived profile
