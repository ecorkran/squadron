---
docType: architecture
layer: project
project: squadron
archIndex: 100
component: orchestration
dateCreated: 20251019
dateUpdated: 20260322
status: in_progress
---

# High-Level Design: Orchestration (Python Reboot)

## Overview

Orchestration is a Python-based multi-agent communication and coordination system. It enables developers to spawn AI agent instances, manage their lifecycle, and experiment with different communication topologies — particularly peer-based patterns where agents self-select whether to engage rather than being directed by a rigid controller.

The system prioritizes experimentation with orchestration patterns and agent communication over UI polish. It exposes functionality through CLI, MCP server, and REST+WebSocket API, making it accessible to humans, AI agents, and other tools.

### Relationship to Prior Work

This document supersedes the original Electron-based HLD. The conceptual wins from the Node.js version carry forward: the peer-based communication model, the message bus architecture, per-agent conversation filtering, and the separation between transport layer and business logic (validated by the backend extraction in slice 132). What is dropped: the Electron shell, the IPC complexity, the TypeScript toolchain, and the custom ADK wrapper/fork work (slices 128, 129) now unnecessary due to ADK native Claude support.

---

## System Architecture

Four major subsystems, layered from core outward:

### 1. Core Engine

The orchestration logic itself. Agent registry (lifecycle management), message bus (pub/sub with configurable routing and per-agent filtering), and communication topology definitions. Pure Python with no framework dependencies. The portable, testable heart of the system.

The core engine includes a supervision layer responsible for detecting agent failures and applying configurable recovery strategies. This is a separate concern from agent communication and topology — agents do not supervise each other. An orthogonal Supervisor component monitors agent health and manages restarts independently of conversation flow.

The supervision layer adopts OTP/BEAM patterns as follows:
* Let it crash, then recover: implement happy path, detect failures, recover
* Configurable restart strategies: 1-1, 1-All, Rest-1
* Circuit breaker
* Recovery policies (clean slate, resume — configurable per agent)
* Health detection
* Agent states (idle, processing, restarting, failed, terminated)

### 2. Agent Provider Layer

Abstracts how agents are created and how they execute. All providers produce agents that satisfy the same `Agent` Protocol, making the core engine and message bus provider-agnostic. Two provider categories exist:

**SDK Agent Provider** (primary, via `claude-agent-sdk`)
- Wraps the official Claude Agent SDK for Python
- Agents are autonomous: they can read/write files, run commands, search the web, and use MCP tools
- Uses Max subscription credentials (no per-token API cost)
- Best for: task execution, code review, file manipulation, any work with side effects
- Supports Claude Code's CLAUDE.md project context, subagent definitions, and hook system
- Session management: multi-turn conversations with context continuity
- Constraint: each `ClaudeSDKClient` instance spawns a CLI subprocess with 20-30s initialization time; design for warm pool / instance reuse rather than per-message creation

**API Agent Provider** (via `anthropic`, `openai`, and other LLM SDKs)
- Wraps raw LLM APIs (Messages API, Chat Completions API, etc.)
- Agents are conversational: send messages, get completions
- Uses API keys with per-token billing
- Best for: multi-agent discussion, reasoning chains, topology experiments, lightweight conversational agents
- Multi-provider by design: the `APIAgentProvider` Protocol is satisfied by any provider that can send messages and return completions
- Initial implementation: Anthropic. Extensible to OpenAI, Google (Gemini), OpenRouter, and local models with compatible API patterns

Both provider types produce agents that implement the unified `Agent` Protocol. The message bus routes messages to agents without knowing or caring which provider created them. This is the key architectural invariant: **the core engine never depends on provider internals**.

#### Agent Protocol

```python
class Agent(Protocol):
    """A participant that can receive and produce messages."""
    @property
    def name(self) -> str: ...
    @property
    def agent_type(self) -> str: ...       # "sdk" | "api"
    @property
    def state(self) -> AgentState: ...

    async def handle_message(self, message: Message) -> AsyncIterator[Message]: ...
    async def shutdown(self) -> None: ...
```

For an SDK agent, `handle_message` translates the incoming message into a `query()` or `client.query()` call, streams back the SDK's response messages as orchestration `Message` objects. For an API agent, `handle_message` appends the message to conversation history, calls the LLM API, and yields the response.

#### Agent Provider Protocol

```python
class AgentProvider(Protocol):
    """Creates and manages agents of a specific type."""
    @property
    def provider_type(self) -> str: ...    # "sdk" | "anthropic" | "openai" | ...

    async def create_agent(self, config: AgentConfig) -> Agent: ...
    async def validate_credentials(self) -> bool: ...
```

The provider registry maps provider type names to `AgentProvider` instances. `get_provider("sdk")` returns the SDK provider, `get_provider("anthropic")` returns the Anthropic API provider, etc.

### 3. Interface Layer

Three exposure modes, all consuming the core engine:

- **CLI** (primary development interface) — typer-based commands for spawning agents, sending messages, observing conversations, running workflows. Fastest path to experimentation.
- **MCP Server** — Exposes orchestration as MCP tools so Claude Code, Cursor, and other MCP clients can create agents, send messages, and query state programmatically.
- **REST + WebSocket API** — FastAPI server for any external client. REST for lifecycle operations, WebSocket for real-time message streaming. Enables future web UI or integration with other systems.

### 4. Frontend (deferred)

A simple React UI may be added later, connecting to the FastAPI backend via HTTP + WebSocket. Not part of the initial build. When it arrives it is a thin client — all logic lives in the core engine.

### Architecture Diagram

```
+---------------------------------------------------+
|                 Interface Layer                    |
|  +-----------+  +-----------+  +---------------+  |
|  |    CLI    |  | MCP Server|  | FastAPI + WS  |  |
|  |  (typer)  |  |  (stdio)  |  |  (port 8000)  |  |
|  +-----+-----+  +-----+-----+  +-------+-------+  |
|        |              |                |            |
|        +--------------+----------------+            |
|                       |                             |
+---------------------------------------------------+
|              Agent Provider Layer                   |
|  +---------------------+  +-----------------------+ |
|  | SDK Agent Provider   |  | API Agent Providers  | |
|  | (claude-agent-sdk)   |  | (anthropic, openai,  | |
|  |                      |  |  gemini, openrouter, | |
|  | • Autonomous agents  |  |  local models, ...)  | |
|  | • File/code access   |  |                      | |
|  | • Max subscription   |  | • Conversational     | |
|  | • Hooks & MCP tools  |  | • Per-token billing  | |
|  +----------+-----------+  +----------+-----------+ |
|             |                         |              |
|             +------------+------------+              |
|                          |                           |
+---------------------------------------------------+
|                  Core Engine                         |
|  +--------------+ +----------+ +---------------+    |
|  | Agent        | | Message  | | Topology      |    |
|  | Registry     | | Bus      | | Manager       |    |
|  | (lifecycle)  | | (pub/sub)| | (routing)     |    |
|  +--------------+ +----------+ +---------------+    |
|  +------------------------------------------------+ |
|  | Supervisor (health monitoring, restart          | |
|  |  strategies, circuit breaker, state recovery)   | |
|  +------------------------------------------------+ |
+---------------------------------------------------+
```

---

## Technology Stack Rationale

**Python 3.12+** — Primary language. Developer strongest language, ADK most mature SDK, largest AI/ML ecosystem.

**claude-agent-sdk** — Official Python SDK for programmatic Claude Code interaction. Provides autonomous agents with built-in tools (Read, Write, Bash, Edit, Grep, Glob, WebSearch), custom MCP tool support, hook system, session management, and subagent definitions. Uses Max subscription credentials. This is the primary agent execution layer.

**anthropic** — Official Anthropic Python SDK for the Messages API. Used for API-based agents that participate in multi-agent conversations. API key and auth token authentication.

**google-adk** — Agent orchestration framework. Provides ParallelAgent, SequentialAgent, Loop, LLM-driven routing, native Claude model support, MCP tool integration, and A2A protocol. Avoids reinventing workflow primitives.

**FastAPI** — Web framework for REST + WebSocket. Async-native, automatic OpenAPI docs, trivial WebSocket support, easy deployment.

**Typer** — CLI framework. Click-based but with type hints, auto-generated help, clean API. Gets a usable CLI with minimal code.

**MCP SDK** (`mcp` Python package) — For exposing orchestration as MCP tools. Stdio transport for Claude Code integration.

**asyncio** — Core concurrency model. Message bus, agent execution, WebSocket streaming all async. Agent SDK and ADK are async-native.

**Pydantic** — Data validation and serialization. Shared models across CLI, API, and MCP. FastAPI uses it natively.

**No Electron, no Node.js, no TypeScript.** The previous stack existed because the project grew out of a desktop app. This reboot starts from the functionality.

---

## Data Flow

### Agent Lifecycle

CLI/MCP/API → Core Engine (Agent Registry) → select AgentProvider by type → provider.create_agent(config) → agent registered with Message Bus → agent ready

### Message Flow

Human or agent sends message → Message Bus receives → applies routing topology → filters per-agent view of conversation history → delivers to eligible agents via agent.handle_message() → agents produce response messages → responses flow back through Message Bus → broadcast to all subscribers (CLI output, WebSocket clients, other agents)

### SDK Agent Task Flow

Orchestration sends task message → SDK agent translates to query() call → Claude Agent SDK executes autonomously (reads files, runs commands, etc.) → SDK streams response messages → SDK agent converts to orchestration Messages → messages flow through Message Bus

### API Agent Conversation Flow

Orchestration sends message → API agent appends to conversation history → API agent calls LLM API (Messages API, Chat Completions, etc.) → response streamed back → API agent converts to orchestration Message → message flows through Message Bus

### ADK Workflow Flow

User defines workflow (parallel, sequential, custom) → ADK orchestrates agent execution order → each agent step goes through Message Bus → results aggregate per ADK pattern → final output returned

---

## Communication Topologies

Communication topologies (broadcast, filtered, hierarchical, custom) are covered in detail in `160-arch.multi-agent-communication.md`.

---

## Multi-Provider Architecture

Multi-provider support is an architectural requirement, not a deferred feature. The `AgentProvider` and `Agent` Protocols are designed so that any LLM service with a Python SDK can be integrated without modifying the core engine.

### Provider Implementation Requirements

Any new provider must:
1. Implement `AgentProvider` Protocol (create agents, validate credentials)
2. Produce agents that implement `Agent` Protocol (handle messages, report state)
3. Register with the provider registry at import time
4. Handle its own credential resolution (API keys, tokens, env vars)
5. Map its native response format to orchestration `Message` objects

### Planned Providers (in priority order)

1. **SDK Agent Provider** (`claude-agent-sdk`) — M1. Autonomous Claude agents on Max subscription.
2. **Anthropic API Provider** (`anthropic` SDK) — M2. Conversational Claude agents via API.
3. **OpenAI Provider** (`openai` SDK) — Post-M2. Chat Completions API.
4. **Google/Gemini Provider** (via ADK or direct SDK) — Post-M2.
5. **OpenRouter Provider** — Post-M2. Access to many models through a single API.
6. **Local Model Provider** — Future. Compatible local APIs (Ollama, vLLM, etc.).

Providers 3-6 follow the same pattern as provider 2. Once the Anthropic API provider exists and the Protocol is validated, additional API providers are straightforward.

### Authentication Patterns

Each provider manages its own authentication:

| Provider | Auth Method | Env Vars |
|----------|------------|----------|
| SDK Agent | Max subscription (automatic via Claude CLI) | `CLAUDE_CODE_OAUTH_TOKEN` (if needed) |
| Anthropic API | API key or auth token | `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` |
| OpenAI | API key | `OPENAI_API_KEY` |
| OpenRouter | API key | `OPENROUTER_API_KEY` |
| Local | None or API key | Provider-specific |

The orchestration framework does not attempt to unify authentication. Each provider's credential resolution is self-contained. The `AgentConfig` model includes a generic `credentials: dict[str, Any]` field that providers interpret as they see fit.

---

## Integration Points and System Boundaries

**Claude Agent SDK** — Primary agent execution. SDK agents use the full Claude Code toolset (file I/O, command execution, web search) through the official Python SDK.

**Anthropic Messages API** — Secondary agent execution. API agents communicate with Claude via the SDK for conversational participation.

**ADK** — Workflow orchestration. The core engine provides the communication layer; ADK provides the execution patterns. They compose rather than compete.

**MCP Protocol** — External tool exposure. The orchestration system appears as a set of MCP tools to any MCP-compatible client.

**Context Forge** (future) — Context assembly for agent instructions. When Context Forge MCP server is running, orchestration agents could use it to build their own context. Shared service model.

---

## Infrastructure and Deployment

**Local development** — `python -m orchestration` or CLI commands. No build step, no bundling.

**MCP mode** — Configured in Claude Code MCP settings. Runs as stdio process.

**Server mode** — `uvicorn orchestration.server:app`. Deployable to Railway, Render, Fly.io, any container host.

**No Electron, no desktop packaging.** If a desktop presence is wanted later, a system tray utility or simple launcher can start the server.

---

## Project Structure

```
orchestration/
├── pyproject.toml
├── README.md
├── src/
│   └── orchestration/
│       ├── __init__.py
│       ├── core/                  # Core Engine
│       │   ├── agent_registry.py
│       │   ├── message_bus.py
│       │   ├── topology.py
│       │   ├── supervisor.py
│       │   └── models.py         # Pydantic models
│       ├── providers/             # Agent Provider Layer
│       │   ├── base.py           # Agent, AgentProvider Protocols
│       │   ├── registry.py       # Provider registry
│       │   ├── errors.py         # Shared error hierarchy
│       │   ├── sdk/              # SDK Agent Provider
│       │   │   ├── provider.py
│       │   │   └── agent.py
│       │   └── anthropic/        # Anthropic API Provider
│       │       ├── provider.py
│       │       └── agent.py
│       ├── adk/                   # ADK Integration
│       │   ├── workflows.py
│       │   └── bridge.py
│       ├── cli/                   # CLI Interface
│       │   ├── app.py            # typer app
│       │   └── commands/
│       ├── server/                # FastAPI Interface
│       │   ├── app.py
│       │   ├── routes/
│       │   └── websocket.py
│       ├── mcp/                   # MCP Server Interface
│       │   └── server.py
│       └── config.py
├── tests/
│   ├── core/
│   ├── providers/
│   │   ├── sdk/
│   │   └── anthropic/
│   ├── cli/
│   └── server/
└── docs/
```

---

## Key Architectural Decisions

- **SDK agents first**: The Claude Agent SDK is the primary agent execution path. It provides autonomous agents with built-in tools on the Max subscription, making it the most capable and cost-effective option.
- **Unified Agent Protocol**: All agent types (SDK, API, future local) implement the same Protocol. The core engine, message bus, and topology layer never depend on provider specifics.
- **Multi-provider as architectural constraint**: The Agent/AgentProvider Protocols are designed for extensibility from day one. Adding a new LLM provider should require only implementing the Protocol and registering the provider — no core engine changes.
- **CLI-first**: CLI is the primary development and experimentation interface. Other interfaces (MCP, API) consume the same core engine.
- **Credential auth flexibility**: Anthropic API supports both API key and auth token. Each provider manages its own credentials independently.
- **Supervision orthogonal to topology**: The core engine includes a supervision layer responsible for detecting agent failures and applying configurable recovery strategies. This is a separate concern from agent communication and topology — agents do not supervise each other.
- **ADK as framework, not fork**: Google ADK provides workflow primitives. Custom value-add is the communication topology layer on top.
- **Frontend deferred**: No UI in initial build. REST+WebSocket API enables a future React frontend as a thin client.

---

## SDK Agent Design Considerations

The Claude Agent SDK has specific characteristics that influence agent design:

**Initialization cost**: Each `ClaudeSDKClient` instance spawns a Claude Code CLI subprocess with ~20-30s startup time. The agent registry should support warm pool patterns — pre-initialize a configurable number of SDK client instances and reuse them across tasks. For one-shot tasks, the simpler `query()` function may be preferable.

**Two interaction modes**:
- `query(prompt, options)` — One-shot async iterator. Good for discrete tasks (review this file, verify this plan). No session state between calls.
- `ClaudeSDKClient` — Multi-turn interactive client with session continuity. Good for complex tasks requiring back-and-forth. Higher initialization cost.

The SDK agent implementation should support both modes, selected by the agent configuration.

**Subagents**: The SDK natively supports subagent definitions via `ClaudeAgentOptions.agents`. An SDK agent can spawn its own subagents for parallel work with isolated context. This is complementary to (not competing with) the orchestration framework's own multi-agent coordination.

**Project context**: `setting_sources=["project"]` loads CLAUDE.md files from the working directory. This is how project-specific review rules, coding standards, and conventions are provided to SDK agents. The orchestration framework can set `cwd` per agent to point at different project directories.

**Hooks**: The SDK's hook system (PreToolUse, PostToolUse) provides programmatic control over agent behavior. Review workflows can use hooks to enforce constraints (e.g., block destructive commands during read-only review).

**Custom MCP tools**: SDK agents can be given custom tools via in-process MCP servers. The orchestration framework could expose its own capabilities (message bus queries, agent listing, etc.) as MCP tools available to SDK agents, enabling agents to be aware of and interact with the orchestration system.
