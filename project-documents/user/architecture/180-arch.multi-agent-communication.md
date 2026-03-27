---
docType: architecture
layer: project
project: squadron
archIndex: 180
component: multi-agent-communication
dateCreated: 20260322
dateUpdated: 20260327
status: not_started
---

# High-Level Design: Multi-Agent Communication

## Overview

Multi-agent communication extends squadron's single-agent CLI and review platform into a coordination system where multiple AI agents communicate through a shared message bus with configurable routing topologies. Agents from different providers (SDK, Anthropic API, OpenAI, local models) participate as peers in conversations, supervised for health and recovery.

This initiative builds on the foundation established in the 100-series (agent registry, provider protocols, CLI, daemon) and adds the communication layer that enables agents to interact with each other and with humans.

### Relationship to 100-Series

The 100-series delivers the single-agent platform: CLI, reviews, provider infrastructure, model aliases, and the local daemon. This 160-series adds:
- Message bus for agent-to-agent communication
- Supervision and health monitoring
- Communication topologies (broadcast, filtered, hierarchical, custom)
- Human-in-the-loop participation
- Interface exposure via MCP and REST+WebSocket
- Workflow orchestration via ADK

The Agent and AgentProvider Protocols defined in the 100-series architecture are the integration contract. All multi-agent work operates through these protocols without modifying core provider logic.

---

## System Architecture

### Core Engine Extensions

The 100-series core engine (agent registry, lifecycle management) gains three new subsystems:

**Message Bus** — Async pub/sub message system. Agents and other participants (human, system) publish and subscribe. Message schema: sender, recipients, content, timestamp, message_type, metadata. Message history (in-memory, upgradeable to persistent store via 135) with per-agent filtering view.

**Supervisor** — Health monitoring and recovery. Watches asyncio task state, detects failures (crashed tasks, unhandled exceptions) and response timeouts. Configurable restart strategies adopting OTP/BEAM patterns:
- one_for_one: restart only the failed agent
- one_for_all: restart all agents in a group
- rest_for_one: restart failed agent and all agents started after it
- Circuit breaker for repeated failures
- Recovery policies: clean slate or resume (configurable per agent)
- Agent states extended: idle, processing, restarting, failed, terminated

**Topology Manager** — Configurable message routing strategies:
- **Broadcast** (default) — All agents see all messages
- **Filtered** — Agents see addressed messages + broadcasts only
- **Hierarchical** — Orchestrator sees all, workers see assigned scope
- **Custom** — User-provided routing functions

Topology affects message bus routing, not agent logic — agents remain unaware of topology details.

### Interface Layer Extensions

Three new exposure modes consuming the core engine:

**MCP Server** — Exposes squadron as MCP tools via Python MCP SDK. Tools: create_agent, list_agents, send_task, send_message, get_conversation, shutdown_agent, set_topology. Stdio transport for Claude Code / Cursor integration.

**REST + WebSocket API** — FastAPI server. REST endpoints for agent lifecycle and conversation management. WebSocket endpoint for real-time message streaming. Automatic OpenAPI docs. CORS configuration for future frontend consumption.

**ADK Integration** — Bridge between ADK workflow patterns (ParallelAgent, SequentialAgent, Loop) and the message bus. ADK manages execution order; each agent step routes through the message bus.

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

## Data Flow

### Message Flow

Human or agent sends message → Message Bus receives → applies routing topology → filters per-agent view of conversation history → delivers to eligible agents via agent.handle_message() → agents produce response messages → responses flow back through Message Bus → broadcast to all subscribers (CLI output, WebSocket clients, other agents)

### API Agent Conversation Flow

Squadron sends message → API agent appends to conversation history → API agent calls LLM API (Messages API, Chat Completions, etc.) → response streamed back → API agent converts to squadron Message → message flows through Message Bus

### ADK Workflow Flow

User defines workflow (parallel, sequential, custom) → ADK orchestrates agent execution order → each agent step goes through Message Bus → results aggregate per ADK pattern → final output returned

---

## Communication Topologies

This is the project differentiator. The Message Bus supports configurable routing strategies:

**Broadcast (default)** — All agents see all messages. Simple, good for small groups.

**Filtered** — Agents see messages addressed to them, messages to all, and their own messages. Can be extended with rules (e.g. agents see all human messages regardless of addressing).

**Hierarchical** — Orchestrator agent sees everything, worker agents see only their assigned scope. Traditional boss/worker pattern, available as one option among many.

**Custom** — User-defined routing functions. Enables experimentation with novel coordination patterns.

---

## Multi-Provider Architecture

Multi-provider support is an architectural requirement inherited from the 100-series. The `AgentProvider` and `Agent` Protocols are designed so that any LLM service with a Python SDK can be integrated without modifying the core engine.

### Provider Implementation Requirements

Any new provider must:
1. Implement `AgentProvider` Protocol (create agents, validate credentials)
2. Produce agents that implement `Agent` Protocol (handle messages, report state)
3. Register with the provider registry at import time
4. Handle its own credential resolution (API keys, tokens, env vars)
5. Map its native response format to squadron `Message` objects

### Providers for Multi-Agent

The Anthropic API Provider (123) is the first API provider built specifically for multi-agent participation. It validates that the Agent Protocol generalizes beyond the SDK provider. Once it exists, additional API providers (OpenAI, Gemini, OpenRouter) follow the same pattern.

---

## Key Architectural Decisions

- **Unified Agent Protocol**: All agent types implement the same Protocol. The core engine, message bus, and topology layer never depend on provider specifics.
- **Supervision orthogonal to topology**: The supervisor monitors agent health independently of conversation flow. Agents do not supervise each other.
- **ADK as framework, not fork**: Google ADK provides workflow primitives. Custom value-add is the communication topology layer on top.
- **CLI-first**: CLI remains the primary experimentation interface. MCP and REST+WebSocket are additional frontends to the same engine.
- **Frontend deferred**: No UI in initial build. REST+WebSocket API enables a future React frontend as a thin client.

---

## Infrastructure and Deployment

**Local development** — CLI commands communicating with the daemon process.

**MCP mode** — Configured in Claude Code MCP settings. Runs as stdio process.

**Server mode** — `uvicorn squadron.server:app`. Deployable to Railway, Render, Fly.io, any container host.

---

## Notes

- The 100-series agent registry, provider infrastructure, and daemon are prerequisites. All 160-series slices depend on at least some 100-series work being complete.
- Ensemble Review (170) is included here because its full value requires M2 parallel fan-out, though it can be experimentally run sequentially using the 100-series review system.
- Subprocess Agent Support (171) extends the agent registry to spawn OS processes, piping through the message bus.
