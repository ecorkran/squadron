---
docType: notes
project: squadron
dateCreated: 20260228
dateUpdated: 20260301
status: deprecated
---

# Slice Design Brief: 112 — Local Server & CLI Client

## Assignment

Design slice 112 following the ai-project-guide slice design format. Use existing slice designs (105, 106, 111) as style references. The slice design doc should be saved as `112-slice.local-server-cli-client.md`.

## Context

The orchestration CLI currently uses `asyncio.run()` per command invocation — each command is a separate process. `spawn` creates an agent, the process exits, the agent is gone. There's no persistent process holding agent instances or conversation state between commands.

This makes non-SDK providers (OpenAI, OpenRouter, Gemini, local models added in slice 111) unusable for multi-turn interaction. SDK agents work for one-shot `task` because that's a complete lifecycle, but any agent you want to `spawn` then later `message` needs something alive to hold it.

GitHub issue #4.

## Architectural Decisions (already made)

### Transport: Unix socket + HTTP (both)
- Single async server core (daemon holding registry + agents)
- Unix socket for CLI communication (fast, no port conflicts)
- HTTP listener on localhost for external consumers
- FastAPI can serve both simultaneously — same routes, two listeners
- The HTTP path means this daemon is already halfway to being the REST API (future slice 14)

### Daemon lifecycle: Explicit `orchestration serve`
- User explicitly starts the daemon with `orchestration serve`
- CLI commands detect whether daemon is running and give clear error if not
- Consider `orchestration serve --status` or `orchestration status` for checking
- No auto-start magic — keep it predictable

### CLI refactor: All commands through daemon
- Every command goes through the daemon — one execution path, simpler to maintain
- This means `review` and `task` also go through the daemon, which enables interactive follow-ups on reviews for free
- Stateless commands (`config`, `review list`) still work through the daemon but don't need persistence

### Message bus awareness without implementation
- Design the daemon's internal structure so the message bus can be added later (slice 6)
- Concretely: the daemon holds an `OrchestrationEngine` (or similar) that owns the registry now and gains a message bus in slice 6
- CLI, MCP server, and REST API are all just interfaces into that engine
- Don't build the bus — just don't make decisions that prevent it

### Agent lifecycle categories (implement first two only)
Three categories exist. Slice 112 implements the first two:

1. **Ephemeral** — spin up, do a thing, done. Current `task` and `review` behavior. No identity persistence beyond the single exchange.
2. **Session** — spawned, stays alive, user interacts with it, eventually shut down. Has a name, conversation history, role/personality via system prompt. This is the primary new capability.
3. **Persistent** (future, acknowledge only) — long-lived agents with identity, scheduled behaviors, ability to be "woken up" on triggers or intervals. Do not implement, but do not preclude.

## Dependencies

- **Foundation** (complete): Models, Protocols, provider registry, errors, Settings
- **Agent Registry** (complete): Agent lifecycle management — becomes an internal component of the daemon's engine
- **CLI Foundation** (complete): Typer app structure — commands are refactored from direct execution to daemon client calls
- **OpenAI-Compatible Provider Core** (slice 111, complete): Concrete provider that needs persistence to be useful

## Key Interfaces

This daemon becomes the host process for future slices:
- **Slice 6 (Message Bus Core):** Bus lives inside the daemon's engine
- **Slice 13 (MCP Server):** Additional interface into the daemon
- **Slice 14 (REST + WebSocket API):** The HTTP listener from 112 evolves into this

## Scope Guidance

### In scope
- Daemon process with `orchestration serve` command
- Unix socket + HTTP dual transport
- `OrchestrationEngine` (or similar) as the central object owning registry and agent instances
- CLI client refactor — all commands communicate with daemon
- Agent spawn with persistence across commands
- Multi-turn conversation with session agents (`orchestration message AGENT_NAME "prompt"`)
- Conversation history retrieval (`orchestration history AGENT_NAME`)
- Graceful shutdown of daemon (`orchestration serve --stop` or signal handling)
- PID file management for daemon lifecycle detection
- Health check endpoint

### Out of scope
- Message bus (slice 6)
- MCP server interface (slice 13)
- REST API beyond what the daemon needs for its own HTTP listener (slice 14)
- Persistent/scheduled agents (future)
- Agent identity files (agent.md, soul.md — future)
- WebSocket streaming (slice 14)

## Technical Notes

- Python, consistent with existing orchestration codebase
- FastAPI + uvicorn is already a project dependency
- Existing tests should be updated or extended, not broken
- Follow test-with pattern per project conventions
