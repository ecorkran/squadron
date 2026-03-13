---
docType: slice-design
slice: cli-foundation
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [foundation, sdk-agent-provider, agent-registry]
interfaces: [sdk-client-warm-pool, review-workflow-templates, human-in-the-loop, end-to-end-testing]
status: complete
dateCreated: 20260219
dateUpdated: 20260220
---

# Slice Design: CLI Foundation & SDK Agent Tasks

## Overview

Implement the Typer-based CLI that serves as the primary development and experimentation interface for the orchestration system. The CLI provides four commands — `spawn`, `list`, `task`, and `shutdown` — that wire the full path from user input through the Agent Registry and SDK Agent Provider to Claude agent execution and back.

This is the first interface layer component and the slice that **completes Milestone 1**: a developer can spawn an SDK agent, give it a task, and see structured output — all from the terminal.

## Value

Direct developer value. After this slice:

- A developer can `orchestration spawn --name reviewer --type sdk --cwd ./my-project` and get a live agent ready to accept tasks.
- `orchestration task reviewer "Review recent changes for style compliance"` sends a real task to Claude and streams the response to the terminal.
- `orchestration list` provides visibility into active agents and their states.
- `orchestration shutdown reviewer` cleanly terminates an agent.
- The system is usable end-to-end for the first time — everything prior was infrastructure. This is the payoff.

## Technical Scope

### Included

- Typer application in `cli/app.py` with `orchestration` as the entry point
- Four commands: `spawn`, `list`, `task`, `shutdown`
- Async support: CLI commands call async registry/agent methods via `asyncio.run()`
- Output formatting: human-readable terminal output with `rich` (Typer's built-in rich support)
- `pyproject.toml` script entry point: `orchestration = "orchestration.cli.app:app"`
- Error handling: user-friendly error messages for common failure modes (agent not found, provider error, no agents running)
- Unit tests for CLI command logic (using Typer's `CliRunner`)

### Excluded

- Multi-turn `chat` command (future — requires message bus, slice 6+)
- `observe` command for watching multi-agent conversations (slice 8)
- `pool` command for warm pool management (slice 5)
- `review` command with templates (slice 15)
- `workflow` commands for ADK (slice 12)
- Streaming output for `task` command — initial implementation collects and displays the full response. Streaming is a natural enhancement once the basic path is proven, but is not required for M1.
- Configuration file support (e.g., `~/.orchestration.yaml`) — future enhancement. CLI flags and env vars are sufficient for M1.
- Shell completion setup — nice-to-have, not part of initial delivery.

## Dependencies

### Prerequisites

- **Foundation** (complete): `AgentConfig`, `AgentState`, `Message` models; `Settings`; logging.
- **SDK Agent Provider** (complete): `SDKAgentProvider` registered as `"sdk"` in the provider registry. The CLI doesn't import the SDK provider directly — it goes through the registry.
- **Agent Registry** (slice 102, complete): `AgentRegistry` with `spawn()`, `get()`, `list_agents()`, `shutdown_agent()`, `shutdown_all()`; `get_registry()` singleton; `AgentInfo` and `ShutdownReport` models; registry error types.

### External Packages

- **typer** (already in pyproject.toml): CLI framework. Provides argument parsing, help generation, and rich output integration.
- **rich** (transitive via typer): Terminal formatting — tables for `list`, styled output for `task` responses.

## Architecture

### Package Structure

```
src/orchestration/cli/
├── __init__.py          # Currently a stub — becomes package init
├── app.py               # Typer app definition, command group
└── commands/
    ├── __init__.py
    ├── spawn.py          # spawn command
    ├── list.py           # list command
    ├── task.py           # task command
    └── shutdown.py       # shutdown command
```

Test structure:
```
tests/cli/
├── __init__.py
├── conftest.py           # Shared CLI test fixtures (CliRunner, mock registry)
├── test_spawn.py
├── test_list.py
├── test_task.py
└── test_shutdown.py
```

### Component Interactions

```
User (terminal)
  → Typer CLI (cli/app.py)
    → command handler (cli/commands/spawn.py, etc.)
      → get_registry() → AgentRegistry
        → AgentProvider Protocol → SDKAgentProvider
          → claude-agent-sdk → Claude
      ← AgentInfo / Message / ShutdownReport
    ← formatted terminal output (rich tables, styled text)
```

The CLI is a thin layer. Each command handler:
1. Parses arguments (Typer handles this)
2. Gets the registry singleton
3. Calls one async method on the registry or agent
4. Formats and displays the result
5. Handles errors with user-friendly messages

### Data Flow

#### Spawn Flow
```
CLI: orchestration spawn --name reviewer --type sdk --cwd ./project
  → build AgentConfig(name="reviewer", agent_type="sdk", provider="sdk", cwd="./project")
  → registry.spawn(config)
  → display: "Agent 'reviewer' spawned (type: sdk, provider: sdk)"
```

#### Task Flow
```
CLI: orchestration task reviewer "Review the code for issues"
  → registry.get("reviewer")  → Agent
  → agent.query("Review the code for issues")  → list[Message]
  → display each Message's content to terminal
```

#### List Flow
```
CLI: orchestration list
  → registry.list_agents()  → list[AgentInfo]
  → display as rich table: Name | Type | Provider | State
```

#### Shutdown Flow
```
CLI: orchestration shutdown reviewer
  → registry.shutdown_agent("reviewer")
  → display: "Agent 'reviewer' shut down"

CLI: orchestration shutdown --all
  → registry.shutdown_all()  → ShutdownReport
  → display: "Shut down 3 agents. 3 succeeded, 0 failed."
```

## Technical Decisions

### Typer as CLI Framework

Typer is already a project dependency and is the HLD's specified choice. It provides:
- Automatic `--help` generation from function signatures and docstrings
- Type-based argument/option parsing
- Rich integration for styled terminal output
- `CliRunner` for testing without subprocess overhead

### Async Bridge Pattern

Typer command handlers are synchronous functions. The registry and agent methods are async. The CLI bridges this with `asyncio.run()`:

```python
@app.command()
def spawn(name: str, type: str = "sdk", provider: str | None = None, cwd: str | None = None):
    """Spawn a new agent."""
    asyncio.run(_spawn(name, type, provider, cwd))

async def _spawn(name: str, type: str, provider: str | None, cwd: str | None):
    registry = get_registry()
    config = AgentConfig(name=name, agent_type=type, provider=provider or type, cwd=cwd)
    await registry.spawn(config)
    # ... display success
```

This is the standard pattern for Typer + asyncio. Each command gets a sync entry point (Typer-decorated) and an async implementation. The `asyncio.run()` creates an event loop per command invocation, which is fine for a CLI tool.

**Alternative considered**: `anyio.from_thread.run` — unnecessary complexity. `asyncio.run()` is clean and sufficient since the CLI doesn't need a persistent event loop across commands.

### Output Formatting Strategy

- **`list`**: Rich `Table` — columns for Name, Type, Provider, State. Color-coded state (idle=green, processing=yellow, terminated=red).
- **`task`**: Plain text output of the agent's response. Message role/type as a subtle prefix if multiple messages are returned. No heavy formatting — the agent's output should be prominent.
- **`spawn` / `shutdown`**: Simple `rich.print()` with styled confirmation messages.
- **Errors**: `rich.print()` with `[red]` styling. No stack traces for expected errors (agent not found, provider error). Stack traces for unexpected errors only in `--verbose` mode (future enhancement).

### Error Handling Approach

The CLI catches known exception types and translates them to user-friendly messages:

| Exception | User Message |
|-----------|-------------|
| `AgentNotFoundError` | `Error: No agent named '{name}'. Use 'orchestration list' to see active agents.` |
| `AgentAlreadyExistsError` | `Error: Agent '{name}' already exists. Choose a different name or shut it down first.` |
| `ProviderError` | `Error: Provider failed — {error detail}` |
| `ProviderAuthError` | `Error: Authentication failed for provider '{provider}'. Check your credentials.` |
| `KeyError` (unknown provider) | `Error: Unknown provider '{provider}'. Available: {list}.` |

Unexpected exceptions propagate as Typer's default behavior (traceback to stderr, exit code 1).

### Command Design Details

#### `spawn`

```
orchestration spawn --name NAME --type TYPE [--provider PROVIDER] [--cwd PATH]
                    [--system-prompt TEXT] [--permission-mode MODE]
```

- `--name` (required): Unique agent name.
- `--type` (default: `"sdk"`): Agent type. Currently only `"sdk"` is available.
- `--provider` (optional): Provider name. Defaults to the value of `--type`. This distinction exists for future providers where type and provider may differ.
- `--cwd` (optional): Working directory for SDK agents. Defaults to current directory.
- `--system-prompt` (optional): System prompt override.
- `--permission-mode` (optional): SDK permission mode (e.g., `"default"`, `"acceptEdits"`).

Maps to `AgentConfig` construction and `registry.spawn()`.

#### `list`

```
orchestration list [--state STATE] [--provider PROVIDER]
```

- `--state` (optional): Filter by agent state (`idle`, `processing`, `terminated`).
- `--provider` (optional): Filter by provider name.
- No arguments: list all agents.

If no agents are registered, display `"No agents running."` instead of an empty table.

#### `task`

```
orchestration task AGENT_NAME PROMPT
```

- `AGENT_NAME` (positional, required): Name of the agent to send the task to.
- `PROMPT` (positional, required): The task prompt.

Calls `agent.query(prompt)` and displays the result. The query returns `list[Message]` — the CLI iterates and prints each message's text content. Tool use blocks are displayed as a compact summary (tool name + truncated input) rather than raw JSON.

If the agent is in a state that doesn't accept queries (e.g., terminated), display an appropriate error.

#### `shutdown`

```
orchestration shutdown AGENT_NAME
orchestration shutdown --all
```

- `AGENT_NAME` (positional, optional): Agent to shut down.
- `--all` (flag): Shut down all agents.
- Must provide exactly one of `AGENT_NAME` or `--all`.

For `--all`, display the `ShutdownReport` summary. For individual shutdown, display a simple confirmation.

### Entry Point Configuration

Add to `pyproject.toml`:

```toml
[project.scripts]
orchestration = "orchestration.cli.app:app"
```

After `uv sync`, the `orchestration` command is available in the virtual environment. This is the standard Typer entry point pattern.

## Integration Points

### Provides to Other Slices

- **SDK Client Warm Pool (slice 5)**: The CLI adds a `pool` subcommand. The warm pool integrates with `spawn` — spawning an SDK agent in client mode checks out a warm instance. The CLI's `spawn` command doesn't change; the optimization is transparent behind the registry.
- **Review Workflow Templates (slice 15)**: The CLI adds a `review` command that uses predefined configurations. The review command composes `spawn` + `task` with template-defined settings (system_prompt, cwd, allowed_tools).
- **Human-in-the-Loop (slice 9)**: The CLI adds a `chat` or interactive mode where the human is a message bus participant. This requires the message bus (slice 6).
- **Multi-Agent Message Routing (slice 8)**: The CLI adds an `observe` command for watching multi-agent conversations.
- **End-to-End Testing (slice 17)**: CLI commands are the primary surface for E2E tests.

### Consumes from Other Slices

- **Agent Registry (slice 102)**: `get_registry()`, `AgentRegistry.spawn()`, `.get()`, `.list_agents()`, `.shutdown_agent()`, `.shutdown_all()`. This is the CLI's only runtime dependency (aside from foundation models).
- **Foundation (slice 100)**: `AgentConfig`, `AgentState`, `Message`, `AgentInfo`, `ShutdownReport` for type construction and result interpretation. `get_logger()` for CLI-level logging.
- **Provider errors (foundation)**: `ProviderError`, `ProviderAuthError` for error message translation.
- **Registry errors (slice 102)**: `AgentNotFoundError`, `AgentAlreadyExistsError` for error message translation.

## Success Criteria

### Functional Requirements

- `orchestration spawn --name test --type sdk` creates an agent and confirms success
- `orchestration list` displays a table of agents with name, type, provider, and state
- `orchestration task test "What is 2+2?"` sends a query and displays the agent's response
- `orchestration shutdown test` terminates the agent and confirms
- `orchestration shutdown --all` terminates all agents and displays a summary
- Error cases produce helpful messages (not stack traces) for: agent not found, duplicate name, provider failure, auth failure
- `orchestration --help` and `orchestration <command> --help` display useful documentation

### Technical Requirements

- All CLI commands tested via Typer's `CliRunner` with mocked registry
- No real SDK/agent calls in unit tests — mock at the registry boundary
- Commands exit with code 0 on success, code 1 on error
- Output is readable both in interactive terminals and when piped (no ANSI codes when not a TTY — rich handles this automatically)

### Integration Requirements

- After this slice, a developer with a Max subscription can run the full M1 flow end-to-end: install → configure → spawn → task → see output → shutdown
- The `pyproject.toml` script entry point works after `uv sync`

## Tracked Enhancements

### Streaming Output for `task` Command (target: slice 9 / M3)

The initial `task` command collects the full response from `agent.query()` and displays it after completion. Streaming output — displaying tokens/messages as they arrive — is deferred to the Human-in-the-Loop slice (9), where real-time output is required for interactive participation. By that point the message bus (slice 6) will have established async iteration patterns that make retrofitting streaming to `task` straightforward. This may also be addressed slightly earlier if it falls naturally out of message bus or multi-agent routing work (slices 6-8).

## Implementation Notes

### Development Approach

Suggested implementation order:

1. **Typer app scaffolding** — `app.py` with the app definition, entry point in `pyproject.toml`, verify `orchestration --help` works.
2. **`spawn` command + tests** — First command because it's needed to set up state for other commands.
3. **`list` command + tests** — Verifies the spawn path by displaying the agent.
4. **`task` command + tests** — The core M1 deliverable. This is where the full path is validated.
5. **`shutdown` command + tests** — Both individual and `--all` variants.
6. **Integration smoke test** — A single test that runs spawn → list → task → shutdown sequentially against the real registry (with mocked provider), verifying the commands compose correctly.

### Testing Strategy

- **Unit tests**: Each command tested in isolation with `CliRunner`. The registry is mocked via `get_registry()` monkeypatching (or by passing a mock registry to an internal function). Tests verify:
  - Correct arguments are parsed and passed to registry methods
  - Success output is formatted correctly
  - Error cases produce expected messages and exit codes
- **Integration test**: One test wires spawn → list → task → shutdown with a real `AgentRegistry` and a mock `AgentProvider` that returns a mock `Agent`. This validates the command composition without needing the SDK.
- **No E2E tests in this slice** — those belong to slice 17. The integration smoke test is the closest we get.
