---
docType: slice-design
slice: sdk-agent-provider
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [foundation]
interfaces: [agent-registry, cli-foundation, review-workflow-templates]
status: complete
dateCreated: 20260219
dateUpdated: 20260220
---

# Slice Design: SDK Agent Provider

## Overview

Implement the `SDKAgentProvider` and `SDKAgent` classes that wrap the `claude-agent-sdk` Python package, enabling the orchestration system to spawn autonomous Claude agents backed by a Max subscription. This is the primary agent execution path — SDK agents can read/write files, run commands, search the web, and use MCP tools without per-token API cost.

The SDK Agent Provider is the first concrete provider implementation and validates the `Agent` / `AgentProvider` Protocols defined in the foundation slice.

## Value

Direct developer value and architectural enablement. After this slice:

- A developer can programmatically spawn a Claude agent, give it a task, and get structured results — the core primitive for all subsequent orchestration work.
- The `AgentProvider` and `Agent` Protocol contracts are validated with a real implementation. Any design issues surface now, before additional providers are built.
- The review workflow use cases (code review, task verification, plan review) become possible once combined with the CLI (slice 4).

## Technical Scope

### Included

- `SDKAgentProvider` class satisfying the `AgentProvider` Protocol
- `SDKAgent` class satisfying the `Agent` Protocol
- Two execution modes: one-shot (`query()`) and multi-turn (`ClaudeSDKClient`)
- `ClaudeAgentOptions` construction from `AgentConfig`
- SDK message type translation: SDK `Message` types → orchestration `Message` model
- Provider auto-registration with the provider registry as `"sdk"`
- Error mapping: SDK exceptions → orchestration `ProviderError` hierarchy
- Credential validation via SDK availability check (Claude CLI reachable)
- Unit tests with SDK mocked at the boundary

### Excluded

- Warm pool / client instance reuse (slice 5 — SDK Client Warm Pool)
- Hook system integration (future slice or part of review workflow templates)
- Custom MCP tool definitions (future — SDK agents use built-in tools only for now)
- Subagent spawning (the SDK supports it natively; we don't orchestrate it yet)
- Agent registry integration (slice 3 — this slice produces agents, registry manages them)
- CLI commands (slice 4)

## Dependencies

### Prerequisites

- **Foundation slice** (complete, with migration applied): `Agent` Protocol, `AgentProvider` Protocol, `AgentConfig` model, `Message` model, `AgentState` enum, provider registry, `ProviderError` hierarchy, `Settings`, logging.

### External Dependencies

- `claude-agent-sdk` Python package (added in foundation migration)
- Claude Code CLI (bundled with `claude-agent-sdk` package, or installed separately)
- Active Claude Max subscription (SDK uses Max credentials for authentication)

## Architecture

### Component Structure

```
src/orchestration/providers/sdk/
├── __init__.py       # Re-exports SDKAgentProvider, SDKAgent
├── provider.py       # SDKAgentProvider implementation
├── agent.py          # SDKAgent implementation
└── translation.py    # SDK message ↔ orchestration Message conversion
```

All three modules are new files replacing the stubs created in the foundation slice.

### SDKAgentProvider

Satisfies the `AgentProvider` Protocol. Responsible for creating `SDKAgent` instances from `AgentConfig` and validating that the Claude CLI is available.

```python
class SDKAgentProvider:
    """Creates and manages SDK-based agents using claude-agent-sdk."""

    @property
    def provider_type(self) -> str:
        return "sdk"

    async def create_agent(self, config: AgentConfig) -> SDKAgent:
        """Build ClaudeAgentOptions from config, create SDKAgent."""
        ...

    async def validate_credentials(self) -> bool:
        """Check that Claude CLI is reachable."""
        ...
```

`create_agent` constructs `ClaudeAgentOptions` from the `AgentConfig` fields:

| AgentConfig field | ClaudeAgentOptions field | Notes |
|---|---|---|
| `instructions` | `system_prompt` | Optional system prompt |
| `model` | `model` | None → SDK default |
| `allowed_tools` | `allowed_tools` | None → all tools available |
| `permission_mode` | `permission_mode` | None → SDK default (ask) |
| `cwd` | `cwd` | None → current directory |
| `setting_sources` | `setting_sources` | None → no project context loaded |

Fields like `api_key`, `auth_token`, `base_url` are not used by SDK agents (auth is handled by the Claude CLI's own credential system). They are silently ignored if present in the config.

### SDKAgent

Satisfies the `Agent` Protocol. Wraps SDK interaction for both one-shot and multi-turn modes.

```python
class SDKAgent:
    """An autonomous agent backed by claude-agent-sdk."""

    def __init__(self, name: str, options: ClaudeAgentOptions, mode: str = "query"):
        self._name = name
        self._options = options
        self._mode = mode  # "query" or "client"
        self._state = AgentState.idle
        self._client: ClaudeSDKClient | None = None

    @property
    def name(self) -> str: ...
    @property
    def agent_type(self) -> str: return "sdk"
    @property
    def state(self) -> AgentState: ...

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        """Execute a task based on the incoming message content."""
        ...

    async def shutdown(self) -> None:
        """Disconnect client if in multi-turn mode."""
        ...
```

#### One-shot mode (`mode="query"`)

`handle_message` calls `query(prompt=message.content, options=self._options)`, iterates the async response, translates each SDK message to an orchestration `Message`, and yields it. Each call is independent — no session state.

```python
# Pseudocode for one-shot mode
async def handle_message(self, message: Message) -> AsyncIterator[Message]:
    self._state = AgentState.processing
    try:
        async for sdk_msg in query(prompt=message.content, options=self._options):
            orch_msg = translate_sdk_message(sdk_msg, sender=self._name)
            if orch_msg is not None:
                yield orch_msg
    except ClaudeSDKError as e:
        raise ProviderError(str(e)) from e
    finally:
        self._state = AgentState.idle
```

#### Multi-turn mode (`mode="client"`)

`handle_message` uses a `ClaudeSDKClient` for session continuity. On first call, the client is created and connected. Subsequent calls reuse the same client, preserving conversation context.

```python
# Pseudocode for multi-turn mode
async def handle_message(self, message: Message) -> AsyncIterator[Message]:
    self._state = AgentState.processing
    try:
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._options)
            await self._client.connect()
        await self._client.query(prompt=message.content)
        async for sdk_msg in self._client.receive_response():
            orch_msg = translate_sdk_message(sdk_msg, sender=self._name)
            if orch_msg is not None:
                yield orch_msg
    except ClaudeSDKError as e:
        raise ProviderError(str(e)) from e
    finally:
        self._state = AgentState.idle
```

#### Mode selection

The `AgentConfig.credentials` dict can include `"mode": "client"` to select multi-turn mode. Default is `"query"` (one-shot). The provider reads this during `create_agent` and passes it to the `SDKAgent` constructor.

### Message Translation

SDK messages use specific types (`AssistantMessage`, `ToolUseBlock`, `ToolResultBlock`, `TextBlock`, `ResultMessage`). The translation layer converts these to orchestration `Message` objects.

```
src/orchestration/providers/sdk/translation.py
```

The translation function examines each SDK message and extracts meaningful content:

| SDK Message Type | Orchestration Message | content | message_type | metadata |
|---|---|---|---|---|
| `AssistantMessage` with `TextBlock` | Yes | The text content | `chat` | `{"sdk_type": "assistant_text"}` |
| `AssistantMessage` with `ToolUseBlock` | Yes | `"Using tool: {name}"` | `system` | `{"sdk_type": "tool_use", "tool_name": name, "tool_input": input}` |
| `ToolResultBlock` | Yes | The result text (truncated if very long) | `system` | `{"sdk_type": "tool_result"}` |
| `ResultMessage` with `subtype="success"` | Yes | The result text | `chat` | `{"sdk_type": "result", "subtype": "success"}` |
| `ResultMessage` with `subtype="error"` | Yes | The error message | `system` | `{"sdk_type": "result", "subtype": "error"}` |
| Other / unknown | No (skipped) | — | — | — |

The `translate_sdk_message` function returns `Message | None`. `None` means the SDK message has no meaningful content to surface (e.g., internal protocol messages).

All translated messages have:
- `sender`: the agent's name
- `recipients`: `["all"]` (broadcast — routing is the message bus's job, not the agent's)
- `timestamp`: current UTC time
- `id`: auto-generated UUID

### Data Flow

```
Caller (registry, CLI, bus)
  │
  │  orchestration Message (content = task description)
  ▼
SDKAgent.handle_message()
  │
  │  Extracts message.content as prompt
  ▼
claude_agent_sdk.query() or ClaudeSDKClient.query()
  │
  │  AsyncIterator[SDK Message]  (AssistantMessage, ToolUseBlock, etc.)
  ▼
translate_sdk_message()
  │
  │  orchestration Message | None
  ▼
Yields back to caller as AsyncIterator[Message]
```

### Error Mapping

SDK exceptions are caught and mapped to the orchestration error hierarchy:

| SDK Exception | Orchestration Exception | Notes |
|---|---|---|
| `CLINotFoundError` | `ProviderAuthError` | Claude CLI not installed/not in PATH |
| `CLIConnectionError` | `ProviderError` | Connection to CLI process failed |
| `ProcessError` | `ProviderAPIError` | CLI process exited with error (use `exit_code` as `status_code`) |
| `CLIJSONDecodeError` | `ProviderError` | Malformed response from CLI |
| `ClaudeSDKError` (base) | `ProviderError` | Catch-all for unknown SDK errors |

The `validate_credentials` method on `SDKAgentProvider` performs a lightweight check — it attempts to import `claude_agent_sdk` and verify the CLI is accessible (e.g., by checking the bundled CLI path or running a minimal version check). It does **not** spawn a full agent session, as that's expensive (~20-30s).

## Technical Decisions

### Why `translation.py` as a separate module

The SDK message types are complex (nested content blocks, multiple block types per message) and the translation logic will grow as we support more message details (tool use streaming, subagent messages, etc.). Isolating it makes the translation independently testable and keeps `agent.py` focused on lifecycle.

### Why mode selection via `credentials` dict

The `AgentConfig` model is generic across provider types. Rather than adding SDK-specific fields to the shared model, we use the `credentials: dict[str, Any]` field for provider-specific configuration. The SDK provider documents which keys it recognizes:

- `"mode"`: `"query"` (default) or `"client"`

Future SDK-specific options (hook definitions, subagent configs) can be added to credentials without touching the shared model.

### Why not wrap `ClaudeSDKClient` as an async context manager internally

The SDK client's `connect()` is expensive (~20-30s subprocess startup). If we create and destroy a client per `handle_message` call in multi-turn mode, we lose session continuity and pay the startup cost repeatedly. Instead, the client is created on first use and held until `shutdown()`. This means the `SDKAgent` is itself a stateful resource that must be explicitly shut down — which aligns with the agent registry's lifecycle management (slice 3).

### Permission mode defaults

The SDK's default `permission_mode` is interactive (prompts for approval on each tool use). For programmatic orchestration, this is unusable — the agent would hang waiting for stdin input. The `SDKAgentProvider.create_agent` should set a sensible default when `permission_mode` is not specified in the config:

- If `allowed_tools` is explicitly set (whitelist): default to `"acceptEdits"` (auto-accept within the whitelist)
- If `allowed_tools` is not set (all tools): default to `"acceptEdits"` (still auto-accept — the orchestrator trusts its own agent configurations)

This can be overridden by explicitly setting `permission_mode` in the `AgentConfig`.

## Integration Points

### Provides to Other Slices

- **Agent Registry (slice 3):** `SDKAgentProvider` registers as `"sdk"` in the provider registry. The registry calls `create_agent(config)` to spawn SDK agents.
- **CLI Foundation (slice 4):** CLI `spawn` and `task` commands ultimately create SDK agents through the registry → provider chain.
- **Review Workflow Templates (slice 15):** Review templates configure `AgentConfig` with specific `cwd`, `setting_sources`, `allowed_tools`, and `instructions` for review tasks. The SDK provider creates agents matching those configs.
- **SDK Client Warm Pool (slice 5):** Warm pool manages `ClaudeSDKClient` instances created by this provider. The pool wraps the client lifecycle that `SDKAgent` establishes in client mode.
- **Message Bus (slice 6, 8):** SDK agents satisfy the `Agent` Protocol, so the message bus can route messages to them via `handle_message` without knowing they're SDK-backed.

### Consumes from Foundation

- `Agent` Protocol (from `providers/base.py`) — SDKAgent must satisfy this
- `AgentProvider` Protocol (from `providers/base.py`) — SDKAgentProvider must satisfy this
- `AgentConfig` model (from `core/models.py`) — input to `create_agent`
- `Message` model (from `core/models.py`) — input/output of `handle_message`
- `AgentState` enum (from `core/models.py`) — state tracking
- `ProviderError`, `ProviderAuthError`, `ProviderAPIError` (from `providers/errors.py`) — error hierarchy
- `register_provider`, `get_provider` (from `providers/registry.py`) — auto-registration
- `get_logger` (from `logging.py`) — structured logging
- `Settings` (from `config.py`) — default configuration fallbacks

## Success Criteria

### Functional Requirements

- `SDKAgentProvider` satisfies `AgentProvider` Protocol (verified by type checker)
- `SDKAgent` satisfies `Agent` Protocol (verified by type checker)
- `SDKAgentProvider` auto-registers as `"sdk"` in the provider registry at import time
- `get_provider("sdk")` returns the registered `SDKAgentProvider` instance
- `create_agent` builds correct `ClaudeAgentOptions` from `AgentConfig` fields
- `handle_message` in query mode: sends prompt to `query()`, translates response, yields orchestration Messages
- `handle_message` in client mode: creates/reuses `ClaudeSDKClient`, sends prompt, translates response
- `shutdown` in client mode: disconnects the client gracefully
- Agent `state` transitions: idle → processing → idle (on success), idle → processing → failed (on error)
- SDK exceptions are caught and mapped to orchestration `ProviderError` hierarchy
- `validate_credentials` returns `True` when Claude CLI is available, `False` otherwise (does not throw)
- All message translations produce valid orchestration `Message` objects

### Technical Requirements

- All tests pass with SDK mocked (no real Claude CLI needed for unit tests)
- Type checker passes with zero errors (Protocols are structurally satisfied)
- `ruff check` and `ruff format` pass
- Translation module has independent test coverage
- Provider registration has test coverage
- Error mapping has test coverage for each SDK exception type

## Risk Assessment

### Technical Risks

**SDK message type evolution**: The SDK is relatively new and message types may change across versions. The translation layer isolates this risk — only `translation.py` needs updating if SDK types change.

**CLI startup time**: `ClaudeSDKClient` takes ~20-30s to initialize. This slice does not implement warm pooling. Multi-turn mode mitigates by reusing a single client, but first-message latency is inherent. This is a known limitation, not a blocker.

**Permission mode in CI/testing**: The SDK may behave differently when Claude CLI credentials are not present (e.g., in CI environments). Unit tests must mock the SDK boundary completely. Integration tests (if any) require a real Max subscription.

### Mitigation

- Translation module is independently versioned and tested — SDK changes are contained
- Mode selection allows choosing one-shot (`query()`) for simple tasks where startup cost matters less
- All tests mock the SDK; no tests depend on Claude CLI availability
- `validate_credentials` is a soft check (returns bool, doesn't throw) so provider registration never fails at import time

## Implementation Notes

### Development Approach

Suggested implementation order:

1. `translation.py` + tests — purely functional, no SDK interaction needed, testable with hand-crafted SDK message objects
2. `provider.py` (SDKAgentProvider) + tests — options construction, registration, credential validation
3. `agent.py` (SDKAgent query mode) + tests — one-shot execution with mocked `query()`
4. `agent.py` (SDKAgent client mode) + tests — multi-turn with mocked `ClaudeSDKClient`
5. `__init__.py` re-exports, integration test, full validation pass

### Testing Strategy

All unit tests mock the SDK at the import boundary. The mock targets are:

- `claude_agent_sdk.query` — async generator returning mock SDK message objects
- `claude_agent_sdk.ClaudeSDKClient` — mock class with `connect`, `query`, `receive_response`, `disconnect`
- `claude_agent_sdk.ClaudeAgentOptions` — real class (it's just a config dataclass, safe to construct)

SDK message types (`AssistantMessage`, `TextBlock`, `ToolUseBlock`, etc.) should be constructed as real objects if possible (they're simple dataclasses), or as mocks with matching attributes if construction requires CLI interaction.

Test categories:
- **Translation tests**: Given specific SDK message objects, verify correct orchestration Message output. Cover all message type rows from the translation table. Verify `None` return for unknown types.
- **Provider tests**: Verify `ClaudeAgentOptions` construction from various `AgentConfig` inputs. Verify registration. Verify credential validation.
- **Agent tests (query mode)**: Verify `handle_message` calls `query()` with correct prompt and options, yields translated messages, transitions state correctly, maps errors.
- **Agent tests (client mode)**: Verify client lifecycle (create on first call, reuse on subsequent), verify `shutdown` disconnects, verify error mapping.

### Special Considerations

**Import-time registration**: The `SDKAgentProvider` should register itself when `orchestration.providers.sdk` is imported. This means the `providers/sdk/__init__.py` should instantiate the provider and call `register_provider("sdk", instance)`. This happens lazily — the sdk subpackage is not auto-imported by `orchestration.providers.__init__`. The agent registry or CLI will explicitly import it when an SDK agent is requested.

**Async iteration safety**: The SDK documentation warns against using `break` to exit `receive_response()` early, as it can cause asyncio cleanup issues. The `SDKAgent` implementation should always iterate the full response, using flags to track completion rather than breaking out of the loop.

**`anyio` vs `asyncio`**: The SDK uses `anyio` internally. Our project uses `asyncio`. These are compatible — `anyio` works on top of `asyncio` by default. No special handling needed, but worth noting for debugging if async issues arise.
