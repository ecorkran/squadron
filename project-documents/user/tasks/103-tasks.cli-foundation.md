---
docType: task-breakdown
slice: cli-foundation
project: squadron
lld: user/slices/103-slice.cli-foundation.md
dependencies: [foundation, sdk-agent-provider, agent-registry]
projectState: Foundation complete with migration applied. SDK Agent Provider (slice 2) complete — SDKAgentProvider and SDKAgent implemented, auto-registered as "sdk". Agent Registry (slice 3) complete — AgentRegistry with spawn/get/list_agents/shutdown_agent/shutdown_all, get_registry() singleton, AgentInfo and ShutdownReport models, registry error types. The stub file cli/__init__.py exists. The cli/commands/ directory does not yet exist.
dateCreated: 20260219
dateUpdated: 20260220
---

## Context Summary

- Working on **CLI Foundation & SDK Agent Tasks** — the first interface layer component
- Foundation, SDK Agent Provider, and Agent Registry slices are complete
- The stub file `src/orchestration/cli/__init__.py` exists
- This slice creates `cli/app.py`, `cli/commands/` with four command modules, and corresponding tests
- **Completes Milestone 1**: developer can spawn an SDK agent, send a task, see output, shut down — all from the terminal
- Next planned slice: **SDK Client Warm Pool** (slice 5)
- **Task ordering**: test-with pattern — implementation immediately followed by tests
- **All tests use mocked registry** — no real SDK or agent calls in unit tests

### What Exists

- `src/orchestration/cli/__init__.py` — stub
- `src/orchestration/core/agent_registry.py` — full `AgentRegistry` with `spawn()`, `get()`, `list_agents()`, `shutdown_agent()`, `shutdown_all()`
- `src/orchestration/core/models.py` — `AgentConfig`, `AgentState`, `Message`, `MessageType`, `AgentInfo`, `ShutdownReport`
- `src/orchestration/providers/errors.py` — `ProviderError`, `ProviderAuthError`, `ProviderAPIError`, `ProviderTimeoutError`
- `src/orchestration/core/agent_registry.py` — `AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError`, `get_registry()`, `reset_registry()`

### What This Slice Adds

- `cli/app.py` — Typer app definition with `orchestration` entry point
- `cli/commands/` — `spawn.py`, `list.py`, `task.py`, `shutdown.py`
- `pyproject.toml` script entry point
- Test suite in `tests/cli/`

### Async Bridge Pattern

All commands use the same pattern: sync Typer handler calls `asyncio.run(_async_impl(...))`. See slice design Technical Decisions for details.

---

## Tasks

### Task 1: Typer App Scaffolding & Entry Point
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1/5
**Objective**: Create the Typer app definition and wire the `pyproject.toml` script entry point so `orchestration --help` works.

**Steps**:
- [x] Create `src/orchestration/cli/app.py`:
  - Import `typer`
  - Create `app = typer.Typer(name="orchestration", help="Multi-agent orchestration CLI")`
  - Add a placeholder callback or empty state so the app is importable
- [x] Update `src/orchestration/cli/__init__.py` to export `app`
- [x] Create `src/orchestration/cli/commands/__init__.py` (empty)
- [x] Add script entry point to `pyproject.toml`:
  ```toml
  [project.scripts]
  orchestration = "orchestration.cli.app:app"
  ```
- [x] Run `uv sync` to install the entry point
- [x] Verify `orchestration --help` runs and shows the app help text

**Success Criteria**:
- [x] `orchestration --help` executes without error and shows help text
- [x] `src/orchestration/cli/app.py` exists with a Typer app instance
- [x] `cli/commands/` directory exists with `__init__.py`

---

### Task 2: CLI Test Infrastructure
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 1/5
**Objective**: Set up shared test fixtures for CLI testing with Typer's `CliRunner` and mock registry.

**Steps**:
- [x] Create `tests/cli/__init__.py`
- [x] Create `tests/cli/conftest.py` with fixtures:
  - `cli_runner` — returns a `typer.testing.CliRunner` instance
  - `mock_registry` — returns a `MagicMock` spec'd to `AgentRegistry`, with async methods patched as `AsyncMock`
  - `patch_registry` — patches `get_registry()` to return `mock_registry`. Use `unittest.mock.patch` targeting `orchestration.cli.commands.<module>.get_registry` (each command module imports it). Alternatively, if commands import from a shared location, patch that single import.
- [x] Create a mock `AgentInfo` factory fixture that builds `AgentInfo` instances with configurable fields for use across test files
- [x] Verify fixtures work by writing a trivial test that invokes `orchestration --help` via `CliRunner` and asserts exit code 0

**Success Criteria**:
- [x] `tests/cli/conftest.py` provides `cli_runner`, `mock_registry`, and `patch_registry` fixtures
- [x] Trivial `--help` test passes via `CliRunner`
- [x] `pytest tests/cli/` runs without errors

---

### Task 3: Implement `spawn` Command
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 2/5
**Objective**: Implement the `spawn` command that creates an agent via the registry.

**Steps**:
- [x] Create `src/orchestration/cli/commands/spawn.py`:
  - Define a sync Typer command function `spawn()` with parameters:
    - `name: str` (required)
    - `type: str` (default `"sdk"`, option `--type`)
    - `provider: str | None` (optional, option `--provider`, defaults to value of `type`)
    - `cwd: str | None` (optional, option `--cwd`)
    - `system_prompt: str | None` (optional, option `--system-prompt`)
    - `permission_mode: str | None` (optional, option `--permission-mode`)
  - Build `AgentConfig` from the arguments
  - Call `asyncio.run(_spawn(config))` where `_spawn` is an async function that calls `get_registry().spawn(config)`
  - On success: print confirmation with agent name, type, and provider using `rich.print`
  - Error handling: catch `AgentAlreadyExistsError`, `ProviderError`, `ProviderAuthError`, `KeyError` (unknown provider) and display user-friendly messages per the error table in the slice design
  - On error: raise `typer.Exit(code=1)`
- [x] Register the command with the app: in `app.py`, import and add the spawn command via `app.command()` or `app.add_typer()`

**Success Criteria**:
- [x] `orchestration spawn --name test --type sdk` is a valid command (visible in `--help`)
- [x] Command constructs `AgentConfig` correctly from CLI arguments
- [x] `--provider` defaults to value of `--type` when not specified
- [x] Error cases produce styled messages (not stack traces) and exit code 1

---

### Task 4: Write `spawn` Command Tests
**Owner**: Junior AI
**Dependencies**: Tasks 2, 3
**Effort**: 1/5
**Objective**: Test the `spawn` command via `CliRunner` with mocked registry.

**Steps**:
- [x] Create `tests/cli/test_spawn.py` with test cases:
  1. Successful spawn with minimal args (`--name test`) — verify exit code 0, success message displayed, `registry.spawn()` called with correct `AgentConfig`
  2. Spawn with all options (`--name test --type sdk --provider sdk --cwd /tmp --system-prompt "Be helpful" --permission-mode acceptEdits`) — verify all fields passed to `AgentConfig`
  3. `--provider` defaults to `--type` value when omitted
  4. Duplicate name — mock `registry.spawn()` to raise `AgentAlreadyExistsError` — verify error message mentions the name and exit code 1
  5. Provider auth error — mock raises `ProviderAuthError` — verify error message and exit code 1
  6. Unknown provider — mock raises `KeyError` — verify error message and exit code 1

**Success Criteria**:
- [x] All spawn tests pass
- [x] Both success and error paths verified
- [x] `AgentConfig` construction verified via mock assertions

---

### Task 5: Implement `list` Command
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 2/5
**Objective**: Implement the `list` command that displays a rich table of active agents.

**Steps**:
- [x] Create `src/orchestration/cli/commands/list.py`:
  - Define `list_agents()` command (note: use a name that doesn't shadow the built-in `list`) with optional filters:
    - `state: str | None` (optional, option `--state`)
    - `provider: str | None` (optional, option `--provider`)
  - Call `asyncio.run(_list_agents(...))` where the async function calls `get_registry().list_agents(state=..., provider=...)`
  - If no agents: print `"No agents running."` and return
  - Otherwise: build a `rich.table.Table` with columns: Name, Type, Provider, State
  - Color-code the State column: idle=green, processing=yellow, terminated=red
  - Print the table via `rich.console.Console().print(table)`
- [x] Register the command with the app in `app.py`

**Success Criteria**:
- [x] `orchestration list` displays a formatted table of agents
- [x] `--state` and `--provider` filters are passed through to `list_agents()`
- [x] Empty registry displays `"No agents running."` instead of empty table

---

### Task 6: Write `list` Command Tests
**Owner**: Junior AI
**Dependencies**: Tasks 2, 5
**Effort**: 1/5
**Objective**: Test the `list` command via `CliRunner` with mocked registry.

**Steps**:
- [x] Create `tests/cli/test_list.py` with test cases:
  1. Empty registry — output contains "No agents running", exit code 0
  2. Two agents — output contains both agent names, types, providers, and states
  3. Filter by state — verify `list_agents()` called with `state` parameter
  4. Filter by provider — verify `list_agents()` called with `provider` parameter
  5. State values display correctly (check that "idle", "processing" text appears in output)

**Success Criteria**:
- [x] All list tests pass
- [x] Empty and populated cases verified
- [x] Filter parameters passed through correctly

---

### Task 7: Implement `task` Command
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 2/5
**Objective**: Implement the `task` command that sends a prompt to a named agent and displays the response. This is the core M1 deliverable.

**Steps**:
- [x] Create `src/orchestration/cli/commands/task.py`:
  - Define `task()` command with parameters:
    - `agent_name: str` (positional, required)
    - `prompt: str` (positional, required)
  - Call `asyncio.run(_task(agent_name, prompt))`:
    - `registry.get(agent_name)` → `Agent`
    - `await agent.query(prompt)` → `list[Message]`
    - Iterate messages and display content:
      - For text content: print directly
      - For tool use blocks: print compact summary (tool name + truncated input) — don't dump raw JSON
      - Use a subtle role/type prefix if multiple messages (e.g., `[assistant]`)
  - Error handling: catch `AgentNotFoundError` with user-friendly message suggesting `orchestration list`
- [x] Register the command with the app in `app.py`

**Success Criteria**:
- [x] `orchestration task myagent "do something"` sends the prompt and displays the response
- [x] Text content is displayed cleanly
- [x] Tool use blocks get a compact summary rather than raw JSON
- [x] Agent not found produces a helpful error message and exit code 1

---

### Task 8: Write `task` Command Tests
**Owner**: Junior AI
**Dependencies**: Tasks 2, 7
**Effort**: 1/5
**Objective**: Test the `task` command via `CliRunner` with mocked registry and agent.

**Steps**:
- [x] Create `tests/cli/test_task.py` with test cases:
  1. Successful task — mock agent's `query()` returns a list with one text `Message` — verify the text content appears in output, exit code 0
  2. Multiple messages returned — verify all message contents appear
  3. Agent not found — mock `registry.get()` raises `AgentNotFoundError` — verify error message and exit code 1
  4. Verify `agent.query()` is called with the correct prompt string

**Success Criteria**:
- [x] All task tests pass
- [x] Response content display verified
- [x] Error path verified

---

### Task 9: Implement `shutdown` Command
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 2/5
**Objective**: Implement the `shutdown` command for both individual and bulk agent shutdown.

**Steps**:
- [x] Create `src/orchestration/cli/commands/shutdown.py`:
  - Define `shutdown()` command with parameters:
    - `agent_name: str | None` (positional, optional)
    - `all_agents: bool` (option `--all`, default False)
  - Validate: must provide exactly one of `agent_name` or `--all`. If neither or both, print error and exit.
  - Individual shutdown path:
    - `asyncio.run(registry.shutdown_agent(agent_name))`
    - Print confirmation: `"Agent '{name}' shut down."`
    - Catch `AgentNotFoundError` → user-friendly message
  - Bulk shutdown path:
    - `asyncio.run(registry.shutdown_all())` → `ShutdownReport`
    - Print summary: `"Shut down N agents. X succeeded, Y failed."`
    - If any failed, list failed agent names with error messages
- [x] Register the command with the app in `app.py`

**Success Criteria**:
- [x] `orchestration shutdown myagent` shuts down one agent with confirmation
- [x] `orchestration shutdown --all` shuts down all agents with summary report
- [x] Providing neither name nor `--all` produces an error
- [x] Agent not found produces a helpful error message and exit code 1
- [x] Failed shutdowns in bulk mode display error details

---

### Task 10: Write `shutdown` Command Tests
**Owner**: Junior AI
**Dependencies**: Tasks 2, 9
**Effort**: 1/5
**Objective**: Test the `shutdown` command via `CliRunner` with mocked registry.

**Steps**:
- [x] Create `tests/cli/test_shutdown.py` with test cases:
  1. Individual shutdown success — verify `shutdown_agent()` called, confirmation displayed, exit code 0
  2. Individual shutdown agent not found — verify error message, exit code 1
  3. Bulk shutdown success — mock `shutdown_all()` returns `ShutdownReport(succeeded=["a","b"], failed={})` — verify summary displayed
  4. Bulk shutdown with failures — mock returns `ShutdownReport(succeeded=["a"], failed={"b": "connection lost"})` — verify both succeeded and failed details displayed
  5. Neither name nor `--all` provided — verify error message

**Success Criteria**:
- [x] All shutdown tests pass
- [x] Individual and bulk paths both verified
- [x] Argument validation verified

---

### Task 11: Integration Smoke Test
**Owner**: Junior AI
**Dependencies**: Tasks 3, 5, 7, 9
**Effort**: 1/5
**Objective**: Write a single integration test that exercises spawn → list → task → shutdown sequentially against a real `AgentRegistry` with a mock provider, verifying the commands compose correctly end-to-end.

**Steps**:
- [x] Create `tests/cli/test_integration.py`:
  - Set up a mock `AgentProvider` that returns a mock `Agent` (satisfying the Protocol with `query()` returning test messages, `shutdown()` succeeding, `state` returning `AgentState.idle`)
  - Register the mock provider in the provider registry as `"sdk"`
  - Use a real `AgentRegistry` (via `reset_registry()` + `get_registry()`)
  - Run commands sequentially via `CliRunner`:
    1. `spawn --name test-agent --type sdk` → exit code 0
    2. `list` → output contains "test-agent" and "idle"
    3. `task test-agent "hello"` → output contains the mock response text
    4. `shutdown test-agent` → exit code 0
    5. `list` → output contains "No agents running"
  - Clean up: call `reset_registry()` in teardown

**Success Criteria**:
- [x] All five commands execute successfully in sequence
- [x] Each command's output reflects the state changes from prior commands
- [x] No real SDK or Claude calls — only mock provider and agent
- [x] Registry is cleaned up after the test
