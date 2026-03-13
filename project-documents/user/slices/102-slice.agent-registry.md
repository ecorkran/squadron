---
docType: slice-design
slice: agent-registry
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [sdk-agent-provider]
interfaces: [cli-foundation, message-bus, mcp-server, rest-websocket-api, subprocess-agent-support]
status: complete
dateCreated: 20260219
dateUpdated: 20260219
---

# Slice Design: Agent Registry & Lifecycle

## Overview

Implement `AgentRegistry` — the central coordination point for agent lifecycle management. The registry spawns agents by name and provider configuration, tracks their state, provides lookup/enumeration, and manages graceful shutdown. It bridges the interface layer (CLI, MCP, REST) and the provider layer, keeping both sides provider-agnostic.

The registry is a pure core-engine component with no dependencies on any specific provider, interface, or communication layer. It operates entirely through the `AgentProvider` and `Agent` Protocols.

## Value

Direct developer value and architectural enablement. After this slice:

- Any interface (CLI, MCP, API) can spawn, query, and shut down agents through a single coordinated entry point — the prerequisite for the CLI slice (4).
- Agent name uniqueness, state tracking, and bulk shutdown are centralized rather than reimplemented per-interface.
- The message bus (slice 6) has a registry to query for routing targets.
- The supervision layer (future) has a registry to monitor.

## Technical Scope

### Included

- `AgentRegistry` class in `core/agent_registry.py`
- Spawn agent: resolve provider → `create_agent(config)` → track by name
- Agent name uniqueness enforcement
- Agent lookup by name and enumeration (list all, filter by state/provider)
- Individual agent shutdown via `agent.shutdown()`
- Bulk shutdown (all agents, with error collection)
- State observation: registry reads `agent.state` — agents own their state
- Module-level convenience: `get_registry()` for shared instance access
- Unit tests with mock providers and agents

### Excluded

- Supervision / health monitoring / restart strategies (future slice — the registry tracks state but does not act on failures)
- Message bus integration (slice 6 — the bus will query the registry, not the other way around)
- Warm pool / client instance reuse (slice 5)
- Agent-to-agent communication (slice 8)
- CLI commands (slice 4 — consumes this registry)
- Subprocess/OS-process agents (slice 16 — extends the registry pattern)

## Dependencies

### Prerequisites

- **Foundation slice** (complete): `AgentConfig`, `AgentState`, `Message` models; `Agent` and `AgentProvider` Protocols; provider registry (`get_provider`, `register_provider`); `ProviderError` hierarchy; `Settings`; logging.
- **SDK Agent Provider** (complete): At least one concrete provider registered, validating that the `AgentProvider → Agent` creation path works. The registry is provider-agnostic but needs a real provider for integration smoke tests.

### What This Slice Provides

- `AgentRegistry` class satisfying the agent lifecycle contract described in the architecture's Core Engine section.
- A `get_registry()` accessor for shared instance access across interface layers.

## Technical Decisions

### Class design: `AgentRegistry`

The registry is a stateful class, not a module-level dict (unlike the simpler provider registry). Reasons:

1. **Async lifecycle operations** — `spawn` and `shutdown` are async. A class with async methods is the natural container.
2. **Testability** — Tests instantiate fresh registries with mock providers. No module-level state to clean up between tests.
3. **Future extensibility** — The supervision layer will likely wrap or extend the registry. A class gives a clean extension point.

However, the interface layer needs a shared instance. Provide a module-level `get_registry()` function that lazily creates a singleton. Tests bypass this and create their own instances.

```python
class AgentRegistry:
    def __init__(self) -> None: ...

    async def spawn(self, config: AgentConfig) -> Agent: ...
    async def shutdown_agent(self, name: str) -> None: ...
    async def shutdown_all(self) -> ShutdownReport: ...

    def get(self, name: str) -> Agent: ...
    def list_agents(self, ...) -> list[AgentInfo]: ...
    def has(self, name: str) -> bool: ...

# Module-level shared instance
_registry: AgentRegistry | None = None

def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
```

### Agent name uniqueness

Agent names are the primary identifier throughout the system — the message bus routes by name, the CLI references agents by name, the REST API uses name in URLs. Names must be unique within a registry instance.

- `spawn()` raises `AgentRegistryError` if the name is already taken.
- Names are case-sensitive strings with no format restrictions at the registry level. The CLI or API layer may impose conventions (e.g., slug-like names) but the registry doesn't enforce them.

### State observation model

The `Agent` Protocol exposes `state: AgentState` as a property. The registry reads this — it does not maintain a parallel state map. This avoids synchronization issues: the agent is the source of truth for its own state.

The registry does need to know about one lifecycle transition it controls: removal. When `shutdown_agent()` is called, the registry calls `agent.shutdown()` and then removes the agent from its internal dict. After removal, the agent is no longer queryable.

### The `AgentInfo` summary model

`list_agents()` should not return `Agent` instances directly to external callers (interfaces shouldn't need to interact with the Protocol object to display a list). Define a lightweight `AgentInfo` Pydantic model:

```python
class AgentInfo(BaseModel):
    name: str
    agent_type: str      # "sdk" | "api"
    provider: str        # "sdk" | "anthropic" | ...
    state: AgentState
```

This is the read model for agent enumeration. `list_agents()` builds it from the registered agents. The `provider` field comes from the `AgentConfig` stored at spawn time.

Where to define it: in `core/models.py` alongside the other core models. It's a core read model, not registry-internal.

### Provider resolution

`spawn()` uses the existing provider registry (`providers/registry.py`) to look up the provider:

```
spawn(config) →
  provider = get_provider(config.provider)  # KeyError if unknown
  agent = await provider.create_agent(config)
  self._agents[config.name] = agent
  self._configs[config.name] = config  # retain for AgentInfo
```

The registry does **not** import any specific provider. It depends only on `get_provider()` and the `AgentProvider` Protocol. This means new providers (Anthropic API, OpenAI, etc.) work automatically once registered — zero registry changes.

### Error handling

Define a small registry-specific error hierarchy in `core/agent_registry.py` (or a new `core/errors.py` if we prefer — but this is only 2-3 classes, so co-location is fine for now):

```python
class AgentRegistryError(Exception):
    """Base for registry-specific errors."""

class AgentNotFoundError(AgentRegistryError):
    """Raised when referencing a non-existent agent name."""

class AgentAlreadyExistsError(AgentRegistryError):
    """Raised when spawning with a duplicate name."""
```

Provider errors (`ProviderError` and subtypes) propagate through `spawn()` without wrapping — the caller can distinguish "provider failed to create the agent" from "name already exists" by exception type.

### Shutdown semantics

**Individual shutdown** (`shutdown_agent(name)`):
1. Look up agent by name (raise `AgentNotFoundError` if missing)
2. Call `await agent.shutdown()`
3. Remove from registry
4. Log the shutdown

If `agent.shutdown()` raises, the agent is still removed from the registry (it's in an indeterminate state and should not remain tracked). The exception propagates to the caller after removal.

**Bulk shutdown** (`shutdown_all()`):
1. Iterate all registered agents
2. Call `await agent.shutdown()` for each, collecting errors
3. Clear the registry
4. Return a `ShutdownReport` summarizing successes and failures

`ShutdownReport` is a simple dataclass or Pydantic model:

```python
class ShutdownReport(BaseModel):
    succeeded: list[str]     # agent names
    failed: dict[str, str]   # agent name → error message
```

Bulk shutdown does not abort on first failure — it's a best-effort operation. This is important for clean teardown (e.g., CLI exit, server shutdown).

### Concurrency considerations

The registry operations (`spawn`, `shutdown_agent`, `shutdown_all`, `get`, `list_agents`) will be called from async contexts (CLI commands, API handlers, MCP tool handlers). Within a single asyncio event loop, dict operations are atomic (no preemption between `await` points), so we don't need a lock for the common case.

However, `spawn()` has a TOCTOU window: check name doesn't exist → `await provider.create_agent()` → store agent. Two concurrent spawns with the same name could both pass the check. For the initial implementation, this is acceptable — the CLI is single-user and concurrent same-name spawns are a pathological case. Document this as a known limitation.

If this becomes a real concern (e.g., REST API with concurrent requests), add an `asyncio.Lock` per registry instance. But don't add it now — YAGNI until there's a concurrent interface.

> **Note for slices 13 (MCP Server) and 14 (REST + WebSocket API):** When designing those slices, evaluate whether concurrent access to the registry warrants adding an `asyncio.Lock` to `spawn()` and `shutdown_agent()`. The lock is trivial to add — the question is whether the interface introduces real concurrent callers.

### Logging

Use the existing structured logging setup. Key log events:

- `agent.spawned` (INFO): name, agent_type, provider
- `agent.shutdown` (INFO): name
- `agent.shutdown_failed` (WARNING): name, error
- `registry.shutdown_all` (INFO): count, succeeded, failed

## Data Flow

### Spawn Flow

```
Interface (CLI/MCP/API)
  → AgentRegistry.spawn(config: AgentConfig)
    → providers.registry.get_provider(config.provider)
      → AgentProvider (e.g., SDKAgentProvider)
    → await provider.create_agent(config)
      → Agent instance (e.g., SDKAgent)
    → store in self._agents[config.name]
    → store config in self._configs[config.name]
    → log agent.spawned
    → return Agent
```

### Shutdown Flow

```
Interface
  → AgentRegistry.shutdown_agent(name)
    → agent = self._agents[name]   # or raise AgentNotFoundError
    → await agent.shutdown()
    → del self._agents[name]
    → del self._configs[name]
    → log agent.shutdown
```

### Query Flow

```
Interface
  → AgentRegistry.list_agents(state=None, provider=None)
    → iterate self._agents
    → apply filters
    → build AgentInfo from agent properties + stored config
    → return list[AgentInfo]
```

## Integration Points

### Provides to Other Slices

- **CLI Foundation (slice 4):** CLI commands (`spawn`, `list`, `task`, `shutdown`) are thin wrappers around `AgentRegistry` methods. The CLI imports `get_registry()` and calls its async methods.
- **Message Bus (slice 6):** The message bus will query the registry to resolve agent names to `Agent` instances for message delivery. The registry's `get(name)` method is the lookup path.
- **MCP Server (slice 13):** MCP tools like `create_agent`, `list_agents`, `shutdown_agent` map directly to registry methods.
- **REST + WebSocket API (slice 14):** REST endpoints for agent lifecycle consume the registry.
- **Subprocess Agent Support (slice 16):** Extends the registry pattern — subprocess agents are registered the same way as SDK/API agents (they satisfy the `Agent` Protocol).

### Consumes from Other Slices

- **Foundation (slice 1):** Models, Protocols, provider registry, errors, logging.
- **SDK Agent Provider (slice 2):** Registered as `"sdk"` in the provider registry. The agent registry resolves it by calling `get_provider("sdk")`.

## File Structure

```
src/orchestration/
  core/
    agent_registry.py    # AgentRegistry class, get_registry(), registry errors
    models.py            # Add AgentInfo, ShutdownReport models

tests/
  core/
    test_agent_registry.py
```

## Success Criteria

1. **Spawn and retrieve:** `registry.spawn(config)` creates an agent via the correct provider and `registry.get(name)` returns it. Verified with a mock `AgentProvider`.
2. **Name uniqueness:** Spawning with a duplicate name raises `AgentAlreadyExistsError`.
3. **Lookup miss:** `registry.get(unknown_name)` raises `AgentNotFoundError`.
4. **List and filter:** `registry.list_agents()` returns `AgentInfo` objects. Filtering by state and provider works correctly.
5. **Individual shutdown:** `shutdown_agent(name)` calls `agent.shutdown()` and removes the agent from the registry.
6. **Bulk shutdown:** `shutdown_all()` shuts down all agents, collects errors for any that fail, clears the registry, and returns a `ShutdownReport`.
7. **Provider error propagation:** If `provider.create_agent()` raises `ProviderError`, it propagates without wrapping.
8. **Shared instance:** `get_registry()` returns the same instance on repeated calls.
9. **All tests pass** with mock providers — no real SDK or API calls.

## Effort

2/5 — Well-scoped, builds directly on established Protocols, no external dependencies or complex async patterns.
