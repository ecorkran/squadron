---
docType: architecture
layer: project
project: squadron
archIndex: 050
component: hld-orchestration
dateCreated: 20260218
dateUpdated: 20260219
status: active
---

# Orchestration — Project Overview

## What Is This?

Orchestration is a Python-based multi-agent communication and coordination system. It enables spawning AI agent instances, managing their lifecycle, and experimenting with different communication topologies — particularly peer-based patterns where agents self-select whether to engage rather than being directed by a rigid controller.

The system exposes functionality through CLI, MCP server, and REST+WebSocket API, making it accessible to humans, AI agents, and other tools.

## Technology Stack

Python 3.12+, claude-agent-sdk, anthropic SDK, FastAPI, Typer, Google ADK, Pydantic, asyncio. Dual agent execution model: SDK agents (autonomous, Max subscription) and API agents (conversational, multi-provider). No Electron, no Node.js.

## Project History

This project reboots an earlier Node.js/TypeScript/Electron implementation. The conceptual wins from that version (peer-based communication, message bus architecture, per-agent conversation filtering, transport/logic separation) carry forward. The code does not. See the initiative HLD for details on what was retained and what was dropped.

## Document Map

### Project Level (050)
- `050-arch.hld-orchestration.md` — This document. Project overview and routing.

### Initiative: Python Reboot (100-band)
- `100-arch.orchestration-v2.md` — Full High-Level Design. Four-layer architecture (Core Engine, Agent Provider Layer, Interface Layer, Frontend), dual provider model (SDK agents + API agents), agent communication topologies, deployment model.
- `100-slices.orchestration-v2.md` — Slice plan. Slices organized around three milestones (SDK agent task execution → multi-agent communication → human + agents).
- `100-slice.*.md` — Individual slice designs (created as work progresses).
- `100-tasks.*.md` / `10n-tasks.*.md` — Task breakdowns per slice.

### Prior Work (reference only)
Old orch-prefixed documents (128, 129, 132, 140) describe Node.js/Electron era work. They are retained as architectural decision records. No code or structure carries forward.

## Key Architectural Decisions

- **SDK agents first**: Claude Agent SDK is the primary agent execution path. Autonomous agents with built-in tools (file I/O, command execution, web search) on Max subscription. Cost-effective and immediately useful for task execution and review workflows.
- **Unified Agent Protocol**: All agent types (SDK, API, future local) implement the same Protocol. The core engine, message bus, and topology layer never depend on provider specifics.
- **Multi-provider as architectural constraint**: The Agent/AgentProvider Protocols are designed for extensibility. Adding a new LLM provider (OpenAI, Gemini, OpenRouter, local models) requires only implementing the Protocol and registering — no core engine changes.
- **CLI-first**: CLI is the primary development and experimentation interface. Other interfaces (MCP, API) consume the same core engine.
- **Supervision orthogonal to topology**: The core engine includes a supervision layer responsible for detecting agent failures and applying configurable recovery strategies. This is a separate concern from agent communication and topology — agents do not supervise each other.
- **ADK as framework, not fork**: Google ADK provides workflow primitives. Custom value-add is the communication topology layer on top.
- **Frontend deferred**: No UI in initial build. REST+WebSocket API enables a future React frontend as a thin client.

## Getting Started

```bash
# Clone and setup
cd orchestration
uv sync

# Configure credentials (Max subscription for SDK agents, API key for API agents)
# See .env.example or docs/

# Spawn an SDK agent and give it a task
orchestration spawn --name reviewer --type sdk --cwd /path/to/project
orchestration task reviewer "Review the recent changes for style compliance"

# Spawn an API agent and chat
orchestration spawn --name assistant --type api --provider anthropic
orchestration chat assistant
```

(CLI commands are illustrative — exact interface defined during slice implementation.)
