---
docType: slice-design
slice: openai-provider-core
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [foundation]
interfaces: [provider-variants-registry, oauth-advanced-auth, anthropic-api-provider]
status: complete
dateCreated: 20260226
dateUpdated: 20260226
---

# Slice Design: OpenAI-Compatible Provider Core

## Overview

Implement `OpenAICompatibleProvider` and `OpenAICompatibleAgent` satisfying the `AgentProvider` and `Agent` Protocols against the OpenAI Chat Completions API. The provider uses the `openai` Python SDK's `AsyncOpenAI` client, which accepts a configurable `base_url` — making this a single implementation that works for OpenAI, OpenRouter, local models (Ollama, vLLM, LM Studio), and Gemini's OpenAI-compatible endpoint.

This slice validates that the `AgentProvider` Protocol generalizes beyond Anthropic. It is the prerequisite for slice 112 (Provider Variants & Registry) and slice 113 (OAuth & Advanced Auth).

## Value

**Architectural validation:** Proves that a second provider can implement the Protocol and integrate with the existing registry, CLI, and agent registry without modifying core engine code. The Protocol either holds or reveals gaps that must be fixed here before more providers are added.

**Developer capability:** After this slice, a developer can spawn a GPT-4o, a local Ollama model, or an OpenRouter model from the same CLI and send tasks to it — interchangeable with SDK agents from the user's perspective.

**Foundation for multi-provider:** Slices 112 (variants) and 113 (OAuth) build directly on this. Slice 7 (Anthropic API Provider) can model itself on the patterns established here.

## Technical Scope

### Included

- `OpenAICompatibleProvider` satisfying `AgentProvider` Protocol
- `OpenAICompatibleAgent` satisfying `Agent` Protocol
- Conversation history management (internal per-agent `list[dict]`)
- Streaming response support via `AsyncStream[ChatCompletionChunk]`
- Tool call surfacing: OpenAI `tool_calls` in responses → orchestration `Message` objects with metadata
- API key credential resolution: `AgentConfig.api_key` → `OPENAI_API_KEY` env var → `ProviderAuthError`
- `base_url` pass-through for non-OpenAI compatible endpoints
- Provider auto-registration as `"openai"` at import time
- Error mapping: `openai` exceptions → orchestration `ProviderError` hierarchy
- `pyproject.toml`: add `openai>=1.0.0` dependency
- Unit tests with `openai` SDK mocked at the boundary
- CLI smoke test: `spawn --type api --provider openai --model gpt-4o-mini` + `task`

### Excluded

- Tool *execution* (surfacing tool calls only — no round-trip tool result handling)
- OpenRouter-specific headers and model mapping (slice 112)
- Local model discovery via `/v1/models` (slice 112)
- Gemini-via-compatible endpoint configuration (slice 112)
- OAuth flows (slice 113)
- Message Bus integration (slice 6)
- Anthropic API provider (slice 7 — separate slice, but shares patterns from here)

## Dependencies

### Prerequisites

- **Foundation slice** (complete): `Agent` Protocol, `AgentProvider` Protocol, `AgentConfig` model, `Message` model, `AgentState` enum, provider registry, `ProviderError` hierarchy, logging.
- No other slices required — this depends only on Foundation.

### External Dependencies

- `openai>=1.0.0` Python SDK (not yet in `pyproject.toml` — must be added)
- `OPENAI_API_KEY` environment variable (or `api_key` in `AgentConfig`)

## Architecture

### Component Structure

```
src/orchestration/providers/openai/
├── __init__.py       # Instantiate provider, register as "openai"
├── provider.py       # OpenAICompatibleProvider
├── agent.py          # OpenAICompatibleAgent
└── translation.py   # OpenAI response chunks → orchestration Messages
```

Mirrors the `providers/sdk/` layout exactly. The naming `openai/` reflects the primary target; the class names `OpenAICompatible*` signal the broader scope.

```
tests/providers/openai/
├── __init__.py
├── test_provider.py
├── test_agent.py
└── test_translation.py
```

### OpenAICompatibleProvider

```python
class OpenAICompatibleProvider:
    """Creates API agents backed by the OpenAI Chat Completions API (or compatible)."""

    @property
    def provider_type(self) -> str:
        return "openai"

    async def create_agent(self, config: AgentConfig) -> OpenAICompatibleAgent:
        """Resolve credentials, build AsyncOpenAI client, return agent."""
        ...

    async def validate_credentials(self) -> bool:
        """Return True if openai package is importable and OPENAI_API_KEY is set."""
        ...
```

`create_agent` resolves the API key: first from `config.api_key`, then from `os.environ["OPENAI_API_KEY"]`. If neither is present, raise `ProviderAuthError` immediately (fail explicitly — no silent fallback).

`AsyncOpenAI` is instantiated with `api_key` and optionally `base_url` (from `config.base_url`). The client is passed to the `OpenAICompatibleAgent` constructor.

The model is taken from `config.model`. If `config.model` is `None`, raise `ProviderError("model is required for OpenAI-compatible agents")` — no silent default model.

`validate_credentials` checks `openai` importability and `OPENAI_API_KEY` env var presence. It does not make a network call. Returns `bool`, never raises.

### OpenAICompatibleAgent

```python
class OpenAICompatibleAgent:
    """Conversational agent backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        name: str,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str | None,
    ) -> None:
        self._name = name
        self._client = client
        self._model = model
        self._history: list[dict[str, str]] = []
        self._state = AgentState.idle

        if system_prompt is not None:
            self._history.append({"role": "system", "content": system_prompt})

    @property
    def name(self) -> str: ...
    @property
    def agent_type(self) -> str: return "api"
    @property
    def state(self) -> AgentState: ...

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        """Append message to history, call API, yield response messages."""
        ...

    async def shutdown(self) -> None:
        """Close the AsyncOpenAI client."""
        ...
```

#### handle_message flow

1. Set state → `processing`
2. Append incoming message to history: `{"role": "user", "content": message.content}`
3. Call `client.chat.completions.create(model=model, messages=history, stream=True)`
4. Iterate `AsyncStream[ChatCompletionChunk]`, accumulating:
   - `delta.content` fragments into a text buffer
   - `delta.tool_calls` fragments into a tool calls buffer
5. After stream completes, build and yield orchestration Messages:
   - If text buffer is non-empty: yield a `chat` Message with accumulated content; append `{"role": "assistant", "content": text}` to history
   - For each complete tool call: yield a `system` Message (see translation section); append tool call to history as `{"role": "assistant", "tool_calls": [...]}` (OpenAI format)
6. Set state → `idle` (in `finally`)
7. Map `openai` exceptions → orchestration errors (see error mapping)

Conversation history grows with each `handle_message` call. The agent is stateful — it remembers prior messages within its lifetime. `shutdown` closes the `AsyncOpenAI` client and sets state → `terminated`.

### Translation Module

`translation.py` contains pure functions operating on OpenAI response types. No side effects, independently testable.

#### Text content

Accumulated `delta.content` strings are joined and returned as a single `chat` Message:

```
content: <accumulated text>
message_type: chat
sender: <agent name>
recipients: ["all"]
metadata: {"provider": "openai", "model": "<model name>"}
```

#### Tool calls

Each entry in `delta.tool_calls` (accumulated and reconstructed from streaming chunks) becomes a `system` Message:

```
content: "Tool call: <function name>"
message_type: system
sender: <agent name>
recipients: ["all"]
metadata: {
    "provider": "openai",
    "type": "tool_call",
    "tool_call_id": "<id>",
    "tool_name": "<function.name>",
    "tool_arguments": "<function.arguments string>"
}
```

Tool call streaming reconstruction: OpenAI streams tool calls as incremental chunks with an index. The translation module accumulates by index into a dict, then iterates the assembled calls after stream end.

### Data Flow

```
Caller (registry / CLI)
  │
  │  orchestration Message (content = user prompt)
  ▼
OpenAICompatibleAgent.handle_message()
  │
  │  Appends to history; calls client.chat.completions.create(stream=True)
  ▼
AsyncStream[ChatCompletionChunk]
  │
  │  Accumulate text + tool_calls from delta fields
  ▼
translation.build_messages(text_buffer, tool_calls_buffer, agent_name, model)
  │
  │  orchestration Message(s)
  ▼
Yields back to caller
```

### Error Mapping

| `openai` exception | Orchestration exception | Notes |
|---|---|---|
| `openai.AuthenticationError` | `ProviderAuthError` | Invalid API key |
| `openai.PermissionDeniedError` | `ProviderAuthError` | Insufficient permissions |
| `openai.RateLimitError` | `ProviderAPIError(status_code=429)` | |
| `openai.APIStatusError` | `ProviderAPIError(status_code=e.status_code)` | Catch-all for 4xx/5xx |
| `openai.APIConnectionError` | `ProviderError` | Network failure |
| `openai.APITimeoutError` | `ProviderTimeoutError` | |

All mapped in `agent.py`'s `handle_message`. The provider never leaks `openai` exceptions to callers.

## Technical Decisions

### Why `openai` SDK instead of direct HTTP

The `openai` Python SDK handles streaming chunked responses, retry logic, and connection management. It also works unchanged against any OpenAI-compatible endpoint via `base_url` override. Direct `httpx` would replicate this work for no benefit.

### Why `AsyncOpenAI` client per agent, not per provider

The `base_url` and `api_key` are per-agent (in `AgentConfig`). A provider-level singleton client would force all agents to share credentials and endpoint. Per-agent client construction is the correct granularity — it's inexpensive (no connection until first call) and keeps each agent's credentials isolated.

### Why accumulate then yield, not stream-through

Streaming chunks to the caller requires the caller to handle partial messages. The current `Agent` Protocol signature `-> AsyncIterator[Message]` yields complete `Message` objects. Accumulating the full response and yielding complete Messages preserves this contract without changing the Protocol. If streaming becomes important for UX, it is a separate Protocol evolution.

### Why no silent model default

API providers are billed per token. An unintended model choice (e.g., a caller omitting `--model` and getting `gpt-4o` when `gpt-4o-mini` was intended) has real cost implications. Explicit failure is safer than a silent default.

### Tool call surfacing scope

Tool call *execution* requires a round-trip: send tool result back as `{"role": "tool", ...}` in history. This requires the orchestration system to route tool calls to executors and collect results — a capability that doesn't exist yet (no tool executor, no message bus). This slice surfaces tool calls as observable Messages so callers can see what the LLM wants to do. Execution is a future slice concern.

### Provider registration name `"openai"`

Slice 112 will add `"openrouter"`, `"local"`, and `"gemini"` as aliases or variant registrations. This slice registers `"openai"` as the canonical entry point. CLI usage: `--provider openai`. Future: `--provider openrouter` (slice 112).

## Integration Points

### Provides to Other Slices

- **Slice 112 (Provider Variants):** `OpenAICompatibleProvider` and `OpenAICompatibleAgent` are the shared implementation. Slice 112 adds variant registrations (openrouter, local, gemini) that reuse this provider with different `base_url` and auth defaults — no new provider class needed.
- **Slice 113 (OAuth):** The `create_agent` credential resolution chain is the extension point. OAuth can inject a bearer token as `api_key` in this same flow.
- **Slice 7 (Anthropic API Provider):** Not a direct dependency, but establishes the structural pattern (`provider.py`, `agent.py`, `translation.py`, per-agent client creation) that the Anthropic provider should follow.
- **Slice 8 (Multi-Agent Message Routing):** `OpenAICompatibleAgent` satisfies the `Agent` Protocol, so the message bus can route to it without modification.

### Consumes from Foundation

- `Agent` Protocol (`providers/base.py`)
- `AgentProvider` Protocol (`providers/base.py`)
- `AgentConfig`, `Message`, `AgentState`, `MessageType` (`core/models.py`)
- `ProviderError`, `ProviderAuthError`, `ProviderAPIError`, `ProviderTimeoutError` (`providers/errors.py`)
- `register_provider`, `get_provider` (`providers/registry.py`)
- `get_logger` (`logging.py`)

## Success Criteria

### Functional Requirements

- `OpenAICompatibleProvider` satisfies `AgentProvider` Protocol (verified by type checker)
- `OpenAICompatibleAgent` satisfies `Agent` Protocol (verified by type checker)
- Provider auto-registers as `"openai"` when `orchestration.providers.openai` is imported
- `create_agent` raises `ProviderAuthError` when no API key is available (not in config, not in env)
- `create_agent` raises `ProviderError` when `config.model` is `None`
- `handle_message` appends user message to history, calls Chat Completions API, yields ≥1 orchestration Message
- Subsequent `handle_message` calls reuse accumulated history (multi-turn conversation works)
- `handle_message` yields a `chat` Message for text responses
- `handle_message` yields `system` Messages for each tool call in the response
- `shutdown` closes the client and sets state → `terminated`
- All `openai` exceptions are mapped to the orchestration error hierarchy — no raw `openai` exceptions escape
- `validate_credentials` returns `True` when `openai` is importable and `OPENAI_API_KEY` is set; `False` otherwise; never raises
- `base_url` in `AgentConfig` is passed through to `AsyncOpenAI`, enabling non-OpenAI endpoints

### Technical Requirements

- All unit tests pass with `openai` SDK fully mocked (no real API calls)
- Type checker (`pyright --strict`) passes with zero errors
- `ruff check` and `ruff format` pass
- Translation module has independent test coverage for text and tool call cases
- Provider credential resolution logic has test coverage (key present, key absent from config but in env, key absent everywhere)
- Error mapping has test coverage for each mapped exception type
- Agent state transitions covered: idle → processing → idle (success), idle → processing → failed (error)

### Integration Requirements

- `orchestration spawn --name gpt --type api --provider openai --model gpt-4o-mini` succeeds (with valid `OPENAI_API_KEY`)
- `orchestration task gpt "Say hello"` returns a response
- `orchestration spawn --name local --type api --provider openai --model llama3 --base-url http://localhost:11434/v1` spawns successfully (Ollama smoke test if available)

## Risk Assessment

### Technical Risks

**OpenAI streaming tool call reconstruction**: Tool calls are delivered as incremental chunks indexed by position. Reconstruction from chunks requires careful accumulation. The `openai` SDK's `Stream` class may handle this internally via `stream.get_final_completion()`, but the streaming iterator approach requires manual assembly if using raw chunk iteration.

**`AsyncOpenAI` client lifecycle**: The `AsyncOpenAI` client uses an internal `httpx.AsyncClient`. If `close()` is not called on shutdown, file descriptors may leak in long-running sessions. The `shutdown` method must call `await client.close()`.

### Mitigation

- For tool call reconstruction: use the `openai` SDK's `Stream.get_final_message()` or accumulate via the pattern in the SDK's own streaming examples rather than implementing from scratch.
- For client lifecycle: `shutdown` unconditionally calls `await self._client.close()`. Tests verify this call is made.

## Implementation Notes

### Development Approach

Suggested order:

1. Add `openai>=1.0.0` to `pyproject.toml`; run `uv sync` to verify install
2. `translation.py` + tests — purely functional, test with hand-crafted `ChatCompletionChunk` objects
3. `provider.py` (`OpenAICompatibleProvider`) + tests — credential resolution, client construction, registration
4. `agent.py` (`OpenAICompatibleAgent`) + tests — mocked `AsyncOpenAI` client, history management, error mapping
5. `__init__.py` registration, import verification test
6. CLI smoke test against real OpenAI endpoint (manual, not in test suite)

### Testing Strategy

All unit tests mock `openai.AsyncOpenAI` and its streaming response. The mock targets:

- `openai.AsyncOpenAI` — constructor (verify `api_key`, `base_url` passed correctly)
- `client.chat.completions.create` — async context manager returning a mock stream
- The mock stream yields synthetic `ChatCompletionChunk` objects with controlled `delta` content

`ChatCompletionChunk` can be constructed using `openai`'s own types (they're Pydantic models in openai >= 1.0) or as attribute mocks. Prefer real types if construction is straightforward.

Test categories:
- **Translation tests**: Text-only response, tool-call-only response, mixed text + tool calls, empty response
- **Provider tests**: API key from config, from env var, from neither (error), model=None (error), base_url pass-through
- **Agent tests**: First message initializes history, second message extends history, text response yields chat Message, tool call yields system Message, error during streaming maps to ProviderError, shutdown closes client
- **Registration test**: Import triggers registration; `get_provider("openai")` returns the instance

### CLI Integration: Provider Auto-Loader

The current codebase has no mechanism to auto-load provider modules when `spawn` is invoked. Providers register at import time (via `__init__.py`), but `spawn.py` and `agent_registry.py` only import `providers.registry`. There is no auto-load. The integration test manually registers a mock provider to work around this.

This slice must solve the auto-loader gap — without it, `--provider openai` will always fail with "Unknown provider 'openai'".

**Chosen approach — lazy import in spawn command:**

Add a `_load_provider(name: str) -> None` helper to `spawn.py` that does:

```python
import importlib

def _load_provider(name: str) -> None:
    """Import the provider module to trigger its auto-registration side effect."""
    try:
        importlib.import_module(f"orchestration.providers.{name}")
    except ImportError:
        pass  # Unknown name; let get_provider raise KeyError naturally
```

Call `_load_provider(config.provider)` in `_spawn()` before `registry.spawn(config)`. This:
- Works for any provider whose module is `providers/{name}/`
- Fails silently for unknown names (they hit the existing `KeyError` path in spawn)
- Requires no central registration list
- Benefits SDK and future providers retroactively

This is a minimal change to `spawn.py` that warrants its own unit test.

### `base_url` CLI Exposure

The `spawn` command does not currently expose `--base-url` as a flag. Adding it is a small, self-contained change within this slice (add `--base-url` option, pass it to `AgentConfig.base_url`). Include it so that the local model smoke test is possible from the CLI without config file changes.

### Deferred: Model Alias / Provider Profile Registry

A natural follow-on is the ability to define named profiles that bundle provider + model + base_url + credentials into a short alias. For example:

```
codex_53    → provider: openai, model: codex-5.3
haiku_or    → provider: openrouter, model: anthropic/claude-haiku-4-5
llama_local → provider: openai, base_url: http://localhost:11434/v1, model: llama3.2
```

With this, `orchestration spawn --model codex_53` resolves the full configuration automatically, without requiring `--provider` or `--base-url` flags.

This belongs in **slice 112 (Provider Variants & Registry)**, which already specifies a `providers.toml` config file for persistent endpoint definitions. Slice 112's design should include:
- Profile schema in `providers.toml` (alias → provider, model, base_url, api_key_env_var)
- Profile resolution in the spawn command: `--model <alias>` or `--profile <alias>` lookup before falling back to explicit flags
- Flag design decision: whether to overload `--model` or add a separate `--profile` flag
