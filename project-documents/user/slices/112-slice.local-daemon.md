---
docType: slice-design
slice: local-daemon
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [foundation, agent-registry, cli-foundation, openai-provider-core]
interfaces: [message-bus-core, mcp-server, rest-websocket-api]
status: not started
dateCreated: 20260228
dateUpdated: 20260228
---

# Slice Design: Local Server & CLI Client

## Overview

Introduce a persistent daemon process (`orchestration serve`) that holds the agent registry, agent instances, and conversation state in memory. CLI commands become thin clients communicating with the daemon via Unix socket (primary) or localhost HTTP (secondary). This enables spawn-then-message workflows that are impossible with the current per-command process model, where each CLI invocation creates a fresh process and registry.

GitHub issue #4.

## Value

**Unblocks multi-turn interaction:** All non-SDK providers (OpenAI, OpenRouter, local models from slice 111) are currently unusable for multi-turn conversation. The agent disappears when the spawning process exits. This slice makes `spawn` → `message` → `message` → `shutdown` workflows work across separate CLI invocations.

**Architectural enablement:** The daemon becomes the single host process for every future interface. The message bus (slice 6), MCP server (slice 13), and REST+WebSocket API (slice 14) all become additional frontends into the same running daemon rather than separate infrastructure. This is the foundation that every post-M1 slice builds on.

**Developer experience:** A developer can open multiple terminal windows, spawn agents from one, send messages from another, and observe state from a third — matching the natural experimentation workflow described in issue #4.

## Technical Scope

### Included

- `OrchestrationEngine` — central object owning the agent registry (and future message bus)
- FastAPI application with REST endpoints for all agent lifecycle operations
- Dual transport: Unix domain socket (CLI) + localhost HTTP (external consumers)
- `orchestration serve` command — starts the daemon in foreground
- `orchestration serve --stop` — sends shutdown signal to running daemon
- `orchestration serve --status` — checks if daemon is running
- CLI client refactor — all agent commands (`spawn`, `list`, `task`, `shutdown`) communicate with daemon via HTTP
- `orchestration message <agent> "prompt"` — new command for multi-turn conversation
- `orchestration history <agent>` — retrieve conversation history
- PID file management for daemon lifecycle detection
- Health check endpoint
- Graceful shutdown via signal handling (SIGTERM, SIGINT)
- Agent lifecycle: ephemeral (task) and session (spawn + message)

### Excluded

- Message bus (slice 6)
- MCP server interface (slice 13)
- REST API beyond what the daemon needs (slice 14 extends this)
- WebSocket streaming (slice 14)
- Persistent/scheduled agents (future)
- Agent identity files (agent.md, soul.md — future)
- Authentication/authorization on daemon endpoints (localhost-only, trusted)
- Daemonization (backgrounding via systemd, launchd, etc.) — user runs `serve` in a terminal or uses `&`

## Dependencies

### Prerequisites

- **Foundation** (complete): Models, Protocols, provider registry, error hierarchy
- **Agent Registry** (complete): Agent lifecycle management — becomes an internal component of the engine
- **CLI Foundation** (complete): Typer app structure — commands are refactored from direct execution to daemon client calls
- **OpenAI-Compatible Provider Core** (slice 111, complete): Concrete provider that needs persistence to be useful

### External Dependencies

- `fastapi>=0.115.0` — already in `pyproject.toml`
- `uvicorn[standard]>=0.30.0` — already in `pyproject.toml`
- `httpx` — HTTP client for CLI→daemon communication. Already a transitive dependency (via `openai`), but should be declared explicitly.

## Architecture

### Component Structure

```
src/orchestration/
├── server/
│   ├── __init__.py          # Currently a stub — becomes the server package
│   ├── engine.py            # OrchestrationEngine
│   ├── app.py               # FastAPI application factory
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── agents.py        # Agent CRUD + messaging endpoints
│   │   └── health.py        # Health check + status
│   ├── daemon.py            # PID file, signal handling, uvicorn launch
│   └── models.py            # Request/response Pydantic models (API layer)
├── client/
│   ├── __init__.py
│   └── http.py              # DaemonClient — HTTP client for CLI commands
├── cli/
│   └── commands/
│       ├── serve.py          # New: orchestration serve
│       ├── message.py        # New: orchestration message
│       ├── history.py        # New: orchestration history
│       ├── spawn.py          # Refactored: delegates to daemon
│       ├── list.py           # Refactored: delegates to daemon
│       ├── task.py           # Refactored: delegates to daemon
│       └── shutdown.py       # Refactored: delegates to daemon
```

### OrchestrationEngine

The engine is the central object that owns all mutable state. It wraps the existing `AgentRegistry` and exposes high-level operations. Future slices add capabilities (message bus, topology) to this same object.

```python
class OrchestrationEngine:
    """Central orchestration coordinator. Owns registry and agent instances."""

    def __init__(self) -> None:
        self._registry = AgentRegistry()

    async def spawn_agent(self, config: AgentConfig) -> AgentInfo: ...
    async def list_agents(self, ...) -> list[AgentInfo]: ...
    async def send_message(self, agent_name: str, content: str) -> list[Message]: ...
    async def get_history(self, agent_name: str) -> list[Message]: ...
    async def shutdown_agent(self, name: str) -> None: ...
    async def shutdown_all(self) -> ShutdownReport: ...
```

Key design point: the engine does **not** subclass or replace `AgentRegistry`. It composes it. The registry continues to manage the agent lifecycle; the engine adds conversation history tracking and higher-level coordination on top.

#### Conversation History

The engine maintains a per-agent conversation history:

```python
self._histories: dict[str, list[Message]] = {}
```

When `send_message` is called:
1. Create a `Message` from the human input
2. Record it in `_histories[agent_name]`
3. Call `agent.handle_message(message)`, collect response messages
4. Record response messages in `_histories[agent_name]`
5. Return response messages

This is distinct from the agent's internal history (which tracks the raw API conversation for context). The engine history is the orchestration-level record of what was said, visible via `get_history`.

#### History Lifecycle After Agent Shutdown

History is **retained after agent shutdown** until the daemon exits. `orchestration history gpt` works even after `orchestration shutdown gpt`. This supports post-mortem inspection of agent conversations — a developer can shut down an agent and still review what it said.

The `list` command only shows live agents, so a shutdown agent won't appear in `list` but its history is still retrievable. This is analogous to shell history surviving after a process exits. History for all agents is cleared when the daemon stops.

No explicit `history --clear` command in this slice — not worth the complexity. If memory pressure from accumulated histories becomes a concern, it can be addressed when persistent agents (future) introduce proper storage.

### FastAPI Application

The FastAPI app is created by a factory function that takes an `OrchestrationEngine` instance:

```python
def create_app(engine: OrchestrationEngine) -> FastAPI:
    app = FastAPI(title="Orchestration Daemon")
    app.state.engine = engine

    app.include_router(agents_router, prefix="/agents")
    app.include_router(health_router)

    return app
```

### API Endpoints

#### Agent Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents` | Spawn a new agent |
| GET | `/agents` | List agents (optional `?state=` and `?provider=` filters) |
| GET | `/agents/{name}` | Get single agent info |
| DELETE | `/agents/{name}` | Shutdown a single agent |
| DELETE | `/agents` | Shutdown all agents |

#### Agent Interaction

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/{name}/message` | Send a message, get response messages |
| POST | `/agents/{name}/task` | One-shot task (spawn ephemeral, message, shutdown) |
| GET | `/agents/{name}/history` | Get conversation history |

#### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (returns `{"status": "ok"}`) |
| POST | `/shutdown` | Graceful daemon shutdown |

#### Request/Response Models

```python
# server/models.py — API-layer Pydantic models

class SpawnRequest(BaseModel):
    name: str
    agent_type: str = "api"
    provider: str = "sdk"
    model: str | None = None
    instructions: str | None = None
    base_url: str | None = None
    cwd: str | None = None
    # ... mirrors AgentConfig fields needed for spawning

class MessageRequest(BaseModel):
    content: str

class MessageResponse(BaseModel):
    messages: list[MessageOut]

class MessageOut(BaseModel):
    id: str
    sender: str
    content: str
    message_type: str
    timestamp: datetime
    metadata: dict[str, Any]

class HealthResponse(BaseModel):
    status: str  # "ok"
    agents: int  # count of active agents
```

### Dual Transport

FastAPI serves both transports from a single application:

```python
# daemon.py — server startup

async def start_server(engine: OrchestrationEngine, config: DaemonConfig) -> None:
    app = create_app(engine)
    uds_config = uvicorn.Config(app, uds=config.socket_path)
    http_config = uvicorn.Config(app, host="127.0.0.1", port=config.port)

    uds_server = uvicorn.Server(uds_config)
    http_server = uvicorn.Server(http_config)

    # TaskGroup (not asyncio.gather) — if either server fails to bind,
    # the other is cancelled automatically. Python 3.11+ required.
    async with asyncio.TaskGroup() as tg:
        tg.create_task(uds_server.serve())
        tg.create_task(http_server.serve())
```

- **Unix socket** (`~/.orchestration/daemon.sock`): Used by CLI commands. Fast, no port conflicts, no network exposure.
- **HTTP** (`127.0.0.1:7862`): Used by external consumers, future MCP server, development tools. Localhost only — no 0.0.0.0 binding.

The CLI client uses the Unix socket by default, falling back to HTTP if the socket is unavailable.

### DaemonClient (CLI Side)

```python
# client/http.py

class DaemonClient:
    """HTTP client for CLI → daemon communication."""

    def __init__(self, socket_path: str | None = None, base_url: str | None = None):
        # Prefer Unix socket, fall back to HTTP
        ...

    async def spawn(self, config: AgentConfig) -> AgentInfo: ...
    async def list_agents(self, ...) -> list[AgentInfo]: ...
    async def send_message(self, agent_name: str, content: str) -> list[Message]: ...
    async def get_history(self, agent_name: str) -> list[Message]: ...
    async def shutdown_agent(self, name: str) -> None: ...
    async def shutdown_all(self) -> ShutdownReport: ...
    async def health(self) -> HealthResponse: ...
    async def request_shutdown(self) -> None: ...
```

Uses `httpx.AsyncClient` with `transport=httpx.AsyncHTTPTransport(uds=socket_path)` for Unix socket communication. This is a standard httpx feature.

Each CLI command constructs a `DaemonClient`, makes one async call, and displays the result. The client handles connection errors and produces user-friendly messages when the daemon is not running.

### Daemon Lifecycle

#### PID File

Location: `~/.orchestration/daemon.pid`

Written on startup, removed on clean shutdown. Contains the process PID. Used by:
- `serve --status`: read PID, check if process is alive via `os.kill(pid, 0)`
- `serve --stop`: read PID, send SIGTERM
- CLI commands: quick pre-check before attempting connection (optional optimization)

#### Signal Handling

The daemon registers handlers for `SIGTERM` and `SIGINT`:
1. Stop accepting new connections
2. Shutdown all agents via `engine.shutdown_all()`
3. Remove PID file
4. Remove Unix socket file
5. Exit cleanly

#### Runtime Directory

`~/.orchestration/` holds daemon runtime files:
```
~/.orchestration/
├── daemon.pid
└── daemon.sock
```

Created on first `serve` invocation if it doesn't exist.

### Data Flow

#### spawn → message → message → shutdown (session workflow)

```
Terminal 1:                         Daemon Process:
                                    ┌─────────────────────────┐
$ orchestration serve               │ OrchestrationEngine     │
                                    │   AgentRegistry         │
Terminal 2:                         │   _histories: {}        │
                                    └─────────────────────────┘
$ orchestration spawn \
    --name gpt --provider openai \
    --model gpt-4o-mini            ──POST /agents──►  engine.spawn_agent()
                                                      → registry creates agent
                                                      → agent stored in memory
                                    ◄── AgentInfo ──

$ orchestration message gpt \
    "What is 2+2?"                 ──POST /agents/gpt/message──►
                                      engine.send_message("gpt", "What is 2+2?")
                                      → agent.handle_message(msg)
                                      → API call to OpenAI
                                      → response Messages
                                    ◄── [Message] ──

$ orchestration message gpt \
    "Now multiply by 10"           ──POST /agents/gpt/message──►
                                      (agent has conversation history)
                                      → continues multi-turn
                                    ◄── [Message] ──

$ orchestration shutdown gpt       ──DELETE /agents/gpt──►
                                      engine.shutdown_agent("gpt")
                                      → agent.shutdown()
                                      → removed from registry
```

#### task (ephemeral workflow — unchanged user experience)

```
$ orchestration task reviewer \
    "Review this code"             ──POST /agents/reviewer/task──►
                                      engine: spawn → message → shutdown
                                    ◄── [Message] ──
```

The `task` command still works as a one-shot operation. Under the hood, the daemon creates an ephemeral agent, sends the message, collects responses, shuts down the agent, and returns the messages. For SDK agents, this preserves current behavior.

### CLI Command Refactoring

Each existing command is refactored from direct `asyncio.run()` + registry calls to `DaemonClient` calls.

**Before (current):**
```python
def spawn(...) -> None:
    asyncio.run(_spawn(...))

async def _spawn(...) -> None:
    registry = get_registry()
    agent_info = await registry.spawn(config)
    rprint(f"Spawned {agent_info.name}")
```

**After:**
```python
def spawn(...) -> None:
    asyncio.run(_spawn(...))

async def _spawn(...) -> None:
    client = DaemonClient()
    try:
        agent_info = await client.spawn(config)
    except DaemonNotRunningError:
        rprint("[red]Daemon not running. Start with: orchestration serve[/red]")
        raise typer.Exit(code=1)
    rprint(f"Spawned {agent_info.name}")
```

The display logic stays in the CLI commands. Only the data-fetching path changes.

#### New Commands

**`orchestration serve`**

```
orchestration serve                 # Start daemon in foreground
orchestration serve --stop          # Stop running daemon
orchestration serve --status        # Check if daemon is running
orchestration serve --port 8080     # Override HTTP port
```

Starts the daemon in the foreground. The user runs it in a dedicated terminal or backgrounds it with `&`. No auto-daemonization — keep it simple and predictable.

**`orchestration message <agent> "prompt"`**

```
orchestration message gpt "What is the capital of France?"
```

Sends a message to a session agent and displays the response. The agent must have been previously spawned. This is the primary new user-facing capability.

**`orchestration history <agent>`**

```
orchestration history gpt
orchestration history gpt --limit 10
```

Displays the conversation history for a named agent. Shows sender, content, and timestamp for each message.

### State Management

All mutable state lives in the `OrchestrationEngine` instance within the daemon process:

- **Agent instances**: In `AgentRegistry._agents` dict (existing)
- **Agent configs**: In `AgentRegistry._configs` dict (existing)
- **Conversation histories**: In `OrchestrationEngine._histories` dict (new)

State is in-memory only. If the daemon exits, all state is lost. This is acceptable for session agents — they are ephemeral by nature. Persistent agents (future) would require a different storage strategy.

The existing module-level `get_registry()` singleton is no longer used by CLI commands. It remains available for direct in-process usage (tests, future MCP server) but the canonical access path is through the engine.

## Technical Decisions

### Why FastAPI for both transports

FastAPI + uvicorn natively supports Unix domain sockets (`--uds` flag). The same ASGI application serves both the Unix socket (fast, local-only) and HTTP (accessible to tools). No code duplication. When slice 14 adds the full REST+WebSocket API, it extends this same FastAPI app rather than building a separate server.

### Why Unix socket as primary CLI transport

- No port conflicts with other services
- No port configuration needed
- Slightly faster than TCP loopback (no TCP overhead)
- Implicit security: only accessible to the local user (filesystem permissions)
- Standard pattern for daemon-CLI communication (Docker, MySQL, PostgreSQL)

### Why `httpx` for the client

`httpx` is the modern Python HTTP client that supports Unix socket transports natively via `httpx.AsyncHTTPTransport(uds=path)`. It's already a transitive dependency. Using it keeps the client simple — just HTTP calls over a different transport.

### Why no auto-start

The brief specifies explicit `orchestration serve`. Reasons:
- Predictable behavior — the user controls when a long-lived process runs
- No surprises with orphaned daemons
- Simple to debug — the daemon logs to stdout
- Consistent with tools like Docker, Redis CLI, etc.

If the daemon is not running, CLI commands print a clear error message with instructions to start it.

### Why conversation history in the engine, not only in agents

Agents maintain their own internal history for API context (the `_history` list in `OpenAICompatibleAgent`). The engine maintains a separate orchestration-level history for:
- Observability: `history` command shows what was said
- Provider-agnostic: works identically for SDK and API agents
- Future message bus: when the bus arrives (slice 6), it inherits this history model
- The agent's internal history is an implementation detail; the engine's history is the system of record

### Why `task` routes through daemon

Keeping all execution paths through the daemon means:
- One execution path to test and maintain
- `task` benefits from daemon-level logging and future observability
- SDK agent `task` also goes through the daemon for consistency
- No conditional logic for "am I talking to a daemon or directly?"

### Agent type categories

**Ephemeral** (existing `task` and `review` behavior):
- Not visible in `list` (or only briefly)
- No conversation history
- Created, used, destroyed in a single request

**Session** (new capability):
- Created via `spawn`, persists in daemon
- Has conversation history
- Visible in `list` with state
- Explicitly `shutdown` or cleaned up when daemon stops

These are behavioral patterns, not formal types in the data model. An `api` type agent spawned via `spawn` is a session agent. The same agent type created for a `task` is ephemeral.

## Integration Points

### Provides to Other Slices

- **Slice 6 (Message Bus Core):** The engine gains a `_bus` field. Bus operations are added to existing engine methods. The daemon process is already running — the bus just lives inside it.
- **Slice 13 (MCP Server):** MCP server connects to the engine, either in-process (if running inside the daemon) or via the HTTP interface. The API endpoints from this slice are the foundation.
- **Slice 14 (REST + WebSocket API):** The FastAPI app from this slice is extended with WebSocket endpoints and broader REST surface. The HTTP listener on `127.0.0.1` becomes configurable for external access.
- **Slice 113 (Provider Variants):** Provider auto-loading already works. Variant registration integrates with the daemon's engine without changes.

### Consumes from Foundation / Prior Slices

- `AgentRegistry` (core/agent_registry.py) — composed inside the engine
- `AgentConfig`, `Message`, `AgentInfo`, `ShutdownReport` (core/models.py)
- `Agent`, `AgentProvider` Protocols (providers/base.py)
- Provider registry and auto-loader (providers/registry.py, cli/commands/spawn.py)
- `ProviderError` hierarchy (providers/errors.py)

## Success Criteria

### Functional Requirements

- `orchestration serve` starts a daemon that persists until stopped
- `orchestration serve --status` reports whether daemon is running
- `orchestration serve --stop` cleanly stops a running daemon
- `orchestration spawn --name gpt --provider openai --model gpt-4o-mini` creates an agent that persists across CLI invocations
- `orchestration message gpt "Hello"` sends a message to a previously spawned agent and displays the response
- A second `orchestration message gpt "Follow up"` continues the conversation with full history
- `orchestration history gpt` displays the conversation history
- `orchestration list` shows spawned agents and their states
- `orchestration shutdown gpt` removes a specific agent
- `orchestration shutdown --all` removes all agents
- `orchestration task <agent> "prompt"` continues to work (routed through daemon)
- CLI commands print a clear error when daemon is not running
- PID file is created on startup and removed on clean shutdown
- Unix socket file is created on startup and removed on clean shutdown
- Daemon handles SIGTERM and SIGINT gracefully (shutdown agents, cleanup files)
- Both Unix socket and HTTP transports serve the same endpoints

### Technical Requirements

- All existing tests continue to pass (test infrastructure may need adaptation for daemon client mocking)
- New unit tests for: engine, API routes, daemon lifecycle, client, CLI commands
- Integration test: start daemon → spawn → message → history → shutdown → stop daemon
- `pyright` passes with zero errors
- `ruff check` and `ruff format` pass
- `httpx` added as explicit dependency in `pyproject.toml`

## Risk Assessment

### Technical Risks

**Dual-transport uvicorn lifecycle:** Running two `uvicorn.Server` instances (Unix socket + HTTP) concurrently in one process requires careful asyncio management. Both must start and stop together. If one fails to bind, both should abort with a clear error.

**PID file race conditions:** If the daemon crashes without cleanup, the PID file and socket file may be stale. The startup sequence must detect and handle stale PID files (check if the recorded PID is still alive, remove stale files if not).

### Mitigation

- For dual transport: wrap both servers in an asyncio task group. If either raises, cancel the other and log the error. Test with the socket path already in use to verify error handling.
- For stale PID files: on startup, read existing PID file, check `os.kill(pid, 0)`, and if the process doesn't exist, remove stale files and proceed. Log a warning when removing stale files.

## Implementation Notes

### Development Approach

Suggested implementation order:

1. **OrchestrationEngine** — wraps existing `AgentRegistry`, adds conversation history
2. **Server models** — request/response Pydantic models
3. **FastAPI routes** — endpoints backed by the engine
4. **App factory + daemon module** — `create_app`, uvicorn startup, PID/socket management, signal handling
5. **DaemonClient** — `httpx`-based client with Unix socket transport
6. **`serve` command** — wires daemon startup into CLI
7. **CLI command refactor** — update `spawn`, `list`, `task`, `shutdown` to use `DaemonClient`
8. **New commands** — `message`, `history`
9. **Integration test** — full lifecycle test

### Testing Strategy

**Unit tests** (mocked dependencies):
- `OrchestrationEngine`: mock `AgentRegistry`, test spawn/message/history/shutdown flows
- FastAPI routes: use `httpx.AsyncClient` with `ASGITransport` (FastAPI test client), mock engine
- `DaemonClient`: mock `httpx.AsyncClient` responses
- CLI commands: mock `DaemonClient`, test display logic and error handling
- Daemon lifecycle: mock `uvicorn.Server`, test PID file creation/removal, signal handling

**Integration test** (real components, no external APIs):
- Start engine with a mock provider
- Create FastAPI app with real engine
- Test full request flow through ASGI transport
- Spawn agent → message → history → shutdown

SDK agent tests may need special handling since SDK agents spawn subprocesses. The primary integration path for this slice is with the OpenAI provider (mocked API).

### Special Considerations

**Review command:** The `review` command currently uses SDK agents directly and does not go through the agent registry. It can continue to work this way in this slice — review has its own runner, its own template system, and refactoring it adds risk without clear value here. The planned convergence point is **slice 15 (Review Findings Pipeline)**, which redesigns review output handling and is a natural place to route review execution through the engine. Until then, `review` remains a separate execution path. This slice must not break the review command.

**Config command:** The `config` command is stateless (reads/writes config files). It does not need to communicate with the daemon. Leave it unchanged.

**Provider auto-loading:** The auto-loader in `spawn.py` (`_load_provider`) imports provider modules to trigger registration. This logic must execute in the daemon process, not the CLI client. It moves into `OrchestrationEngine.spawn_agent()` — the engine calls `_load_provider(config.provider)` before delegating to the registry. This keeps the engine as the single coordination point for agent creation and ensures the provider module is loaded in the process that actually holds the agents. The `_load_provider` function itself can be reused as-is (import from a shared location or inline in engine).

**Long-running requests:** `POST /agents/{name}/message` and `POST /agents/{name}/task` are synchronous request/response — the HTTP connection stays open until the LLM responds. API agents (OpenAI, etc.) typically respond in seconds, but SDK agents performing complex tasks can take 60s+. Uvicorn has no default request timeout, which is correct here. The `DaemonClient` should set a generous `httpx` timeout (e.g., 300s) and the implementation should not add any intermediate timeouts that could kill a legitimate long-running agent response. WebSocket streaming (slice 14) is the proper solution for real-time output of long tasks.

**`AgentRegistry` singleton:** The current `get_registry()` singleton pattern works for the existing per-process model. In the daemon, the engine creates and owns its own registry instance. The singleton remains for backward compatibility (tests, review command) but is no longer the primary access path.
