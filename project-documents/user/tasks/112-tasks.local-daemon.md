---
slice: local-daemon
project: squadron
lld: project-documents/user/slices/112-slice.local-daemon.md
dependencies: [foundation, agent-registry, cli-foundation, openai-provider-core]
projectState: M1 complete and published. OpenAI-compatible provider (slice 111) complete. 342 tests passing. Agent persistence gap identified (GitHub issue #4) — agents don't survive between CLI invocations.
status: complete
dateCreated: 20260228
dateUpdated: 20260228
---

## Context Summary

- Working on **local-daemon** (slice 112)
- Introduces persistent daemon process (`orchestration serve`) holding agent registry, agents, and conversation state in memory
- CLI commands become thin clients communicating with daemon via Unix socket / localhost HTTP
- New `OrchestrationEngine` composes existing `AgentRegistry`, adds conversation history tracking
- FastAPI app serves both transports via two uvicorn instances in a `TaskGroup`
- New commands: `serve`, `message`, `history`. Existing commands refactored to use `DaemonClient`
- Resolves GitHub issue #4 (agent persistence)
- Full design: `project-documents/user/slices/112-slice.local-daemon.md`
- Next slice: 113 (Provider Variants & Registry)

---

## Tasks

- [x] **T1: Add httpx dependency**
  - [x] Add `httpx>=0.27.0` to `pyproject.toml` `[project.dependencies]`
  - [x] Run `uv sync` to install
  - [x] Success: `python -c "import httpx; print(httpx.__version__)"` prints a version; `uv sync` clean

- [x] **T2: Create test infrastructure for server and client**
  - [x] Create `tests/server/__init__.py`
  - [x] Create `tests/server/conftest.py` with:
    - [x] `MockAgent` class satisfying the `Agent` Protocol (reusable mock with controllable `handle_message` responses)
    - [x] `MockProvider` class satisfying `AgentProvider` Protocol (returns `MockAgent` from `create_agent`)
    - [x] `engine` fixture — creates `OrchestrationEngine`, registers mock provider
    - [x] `app` fixture — calls `create_app(engine)` to get a FastAPI test app
    - [x] `async_client` fixture — `httpx.AsyncClient` with `ASGITransport(app)` for route testing
  - [x] Create `tests/client/__init__.py`
  - [x] Success: `pytest tests/server/ tests/client/` runs (0 tests, 0 errors)

- [x] **T3: Implement OrchestrationEngine**
  - [x] Create `src/orchestration/server/engine.py`
  - [x] `OrchestrationEngine.__init__()` — creates own `AgentRegistry` instance; initializes `_histories: dict[str, list[Message]]`
  - [x] `spawn_agent(config)` — calls `_load_provider(config.provider)` (import from shared location or inline), then `self._registry.spawn(config)`; initializes empty history list for the agent; returns `AgentInfo`
  - [x] `list_agents(state, provider)` — delegates to `self._registry.list_agents(...)`
  - [x] `get_agent(name)` — delegates to `self._registry.get(name)`
  - [x] `send_message(agent_name, content)` — creates `Message(sender="human", ...)`, records in history, calls `agent.handle_message(msg)`, collects and records response messages, returns them
  - [x] `get_history(agent_name)` — returns `self._histories.get(agent_name, [])` (works for shutdown agents too)
  - [x] `shutdown_agent(name)` — delegates to `self._registry.shutdown_agent(name)`; does NOT clear history (history retained per design)
  - [x] `shutdown_all()` — delegates to `self._registry.shutdown_all()`; returns `ShutdownReport`
  - [x] Update `src/orchestration/server/__init__.py` — replace stub docstring; export `OrchestrationEngine`
  - [x] Success: module importable; all methods present; pyright clean on this file

- [x] **T4: Test OrchestrationEngine**
  - [x] Create `tests/server/test_engine.py`
  - [x] `test_spawn_agent` — spawn via engine, returns `AgentInfo` with correct name
  - [x] `test_spawn_agent_loads_provider` — verify `_load_provider` is called with provider name before registry spawn
  - [x] `test_list_agents_returns_spawned` — spawn two, list returns both
  - [x] `test_send_message_returns_responses` — spawn, send message, get list of response Messages
  - [x] `test_send_message_records_history` — after send, `get_history` returns both human and agent messages
  - [x] `test_get_history_empty_for_unknown` — returns empty list (not error) for unknown agent name
  - [x] `test_history_retained_after_shutdown` — spawn, message, shutdown, history still returns messages
  - [x] `test_shutdown_agent` — spawn then shutdown; agent no longer in list
  - [x] `test_shutdown_all` — spawn two, shutdown_all returns `ShutdownReport` with both names
  - [x] Success: all tests pass; ruff clean

- [x] **T5: Implement server models and health route**
  - [x] Create `src/orchestration/server/models.py` with Pydantic models:
    - [x] `SpawnRequest` — mirrors `AgentConfig` fields needed for spawning (name, agent_type, provider, model, instructions, base_url, cwd, etc.)
    - [x] `MessageRequest` — `content: str`
    - [x] `MessageOut` — serializable Message (id, sender, content, message_type, timestamp, metadata)
    - [x] `MessageResponse` — `messages: list[MessageOut]`
    - [x] `AgentInfoOut` — mirrors `AgentInfo` (name, agent_type, provider, state)
    - [x] `HealthResponse` — `status: str`, `agents: int`
    - [x] `ShutdownReportOut` — mirrors `ShutdownReport`
  - [x] Create `src/orchestration/server/routes/__init__.py` (empty)
  - [x] Create `src/orchestration/server/routes/health.py` — `health_router` with `GET /health` returning `HealthResponse`
  - [x] Success: models importable; health router importable; pyright clean

- [x] **T6: Implement agent routes**
  - [x] Create `src/orchestration/server/routes/agents.py` — `agents_router` with:
    - [x] `POST /` — spawn agent (accepts `SpawnRequest`, returns `AgentInfoOut`)
    - [x] `GET /` — list agents (optional `state` and `provider` query params, returns `list[AgentInfoOut]`)
    - [x] `GET /{name}` — get single agent info (returns `AgentInfoOut`, 404 if not found)
    - [x] `DELETE /{name}` — shutdown single agent (204 on success, 404 if not found)
    - [x] `DELETE /` — shutdown all agents (returns `ShutdownReportOut`)
    - [x] `POST /{name}/message` — send message (accepts `MessageRequest`, returns `MessageResponse`)
    - [x] `POST /{name}/task` — one-shot task (accepts `SpawnRequest` + prompt in body, returns `MessageResponse`; spawns ephemeral agent, messages, shuts down)
    - [x] `GET /{name}/history` — get conversation history (optional `limit` query param, returns `MessageResponse`)
  - [x] All routes access engine via `request.app.state.engine`
  - [x] Map `AgentNotFoundError` → HTTP 404; `ProviderError` hierarchy → appropriate 4xx/5xx
  - [x] Success: routes importable; pyright clean

- [x] **T7: Test routes**
  - [x] Create `tests/server/test_routes.py`
  - [x] `test_health` — `GET /health` returns 200 with `status: "ok"` and agent count
  - [x] `test_spawn_agent` — `POST /agents` with valid body returns 200 with agent info
  - [x] `test_list_agents` — spawn two, `GET /agents` returns both
  - [x] `test_get_agent` — spawn one, `GET /agents/{name}` returns info
  - [x] `test_get_agent_not_found` — `GET /agents/nonexistent` returns 404
  - [x] `test_send_message` — spawn then `POST /agents/{name}/message` returns response messages
  - [x] `test_get_history` — spawn, message, `GET /agents/{name}/history` returns conversation
  - [x] `test_shutdown_agent` — spawn then `DELETE /agents/{name}` returns 204
  - [x] `test_shutdown_all` — spawn two, `DELETE /agents` returns shutdown report
  - [x] All tests use `async_client` fixture (httpx + ASGITransport, no real server)
  - [x] Success: all tests pass; ruff clean

- [x] **T8: Implement app factory**
  - [x] Create `src/orchestration/server/app.py`
  - [x] `create_app(engine: OrchestrationEngine) -> FastAPI` — stores engine on `app.state.engine`, includes `agents_router` with `/agents` prefix and `health_router`
  - [x] Success: `create_app(engine)` returns a FastAPI instance; routes accessible

- [x] **T9: Implement daemon module**
  - [x] Create `src/orchestration/server/daemon.py`
  - [x] `DaemonConfig` dataclass — `socket_path` (default `~/.orchestration/daemon.sock`), `port` (default `7862`), `pid_path` (default `~/.orchestration/daemon.pid`)
  - [x] `write_pid_file(path)` — write `os.getpid()` to file; create parent directory if needed
  - [x] `remove_pid_file(path)` — remove file if it exists
  - [x] `read_pid_file(path) -> int | None` — read PID from file, return None if file doesn't exist or is invalid
  - [x] `is_daemon_running(pid_path) -> bool` — read PID file, check `os.kill(pid, 0)`; handle stale files (process gone → remove stale PID file, return False)
  - [x] `remove_socket_file(path)` — remove Unix socket file if it exists
  - [x] `start_server(engine, config)` — create app, configure two `uvicorn.Server` instances (UDS + HTTP), run both in `asyncio.TaskGroup`; register signal handlers for SIGTERM/SIGINT that trigger shutdown
  - [x] Signal handler: on signal, call `engine.shutdown_all()`, then set a shutdown event that causes servers to stop
  - [x] Success: module importable; all functions present; pyright clean

- [x] **T10: Test daemon module**
  - [x] Create `tests/server/test_daemon.py`
  - [x] `test_write_and_read_pid_file` — write PID, read back, matches `os.getpid()`
  - [x] `test_read_pid_file_missing` — non-existent file returns None
  - [x] `test_remove_pid_file` — write then remove; file gone
  - [x] `test_is_daemon_running_true` — write current PID, returns True
  - [x] `test_is_daemon_running_stale` — write non-existent PID, returns False, stale PID file removed
  - [x] `test_is_daemon_running_no_file` — no PID file, returns False
  - [x] Use `tmp_path` fixture for all file operations (no real `~/.orchestration/`)
  - [x] Success: all tests pass; ruff clean

- [x] **T11: Commit server core**
  - [x] `pytest tests/server/` — all green
  - [x] `ruff check src/orchestration/server/` — clean
  - [x] `pyright src/orchestration/server/` — zero errors
  - [x] Commit: `feat: add OrchestrationEngine, FastAPI routes, and daemon module`

- [x] **T12: Implement DaemonClient**
  - [x] Create `src/orchestration/client/__init__.py`
  - [x] Create `src/orchestration/client/http.py`
  - [x] `DaemonNotRunningError(Exception)` — raised when connection to daemon fails
  - [x] `DaemonClient.__init__(socket_path, base_url)` — defaults to Unix socket at `~/.orchestration/daemon.sock`; falls back to HTTP at `http://127.0.0.1:7862`
  - [x] Internally creates `httpx.AsyncClient` with `AsyncHTTPTransport(uds=socket_path)` for Unix socket, or plain client for HTTP; timeout set to 300s
  - [x] Methods: `spawn(request_data)`, `list_agents(state, provider)`, `send_message(agent_name, content)`, `get_history(agent_name, limit)`, `shutdown_agent(name)`, `shutdown_all()`, `health()`, `request_shutdown()`
  - [x] Each method makes the appropriate HTTP call, deserializes response, returns domain objects
  - [x] Connection errors (`httpx.ConnectError`) → raise `DaemonNotRunningError` with helpful message
  - [x] HTTP error responses (4xx/5xx) → raise appropriate errors with detail from response body
  - [x] `close()` method to close the underlying httpx client
  - [x] Success: module importable; pyright clean

- [x] **T13: Test DaemonClient**
  - [x] Create `tests/client/test_http.py`
  - [x] `test_spawn_sends_post` — mock httpx response; verify POST to `/agents` with correct body
  - [x] `test_list_agents` — mock response; verify GET to `/agents`
  - [x] `test_send_message` — mock response; verify POST to `/agents/{name}/message`
  - [x] `test_get_history` — mock response; verify GET to `/agents/{name}/history`
  - [x] `test_shutdown_agent` — mock response; verify DELETE to `/agents/{name}`
  - [x] `test_connection_error_raises_daemon_not_running` — mock `httpx.ConnectError`; verify `DaemonNotRunningError` raised
  - [x] `test_health` — mock response; verify GET to `/health`
  - [x] Success: all tests pass; ruff clean

- [x] **T14: Commit client**
  - [x] `pytest tests/client/` — all green
  - [x] `ruff check src/orchestration/client/` — clean
  - [x] `pyright src/orchestration/client/` — zero errors
  - [x] Commit: `feat: add DaemonClient for CLI-to-daemon communication`

- [x] **T15: Implement serve command**
  - [x] Create `src/orchestration/cli/commands/serve.py`
  - [x] `serve()` Typer command with mutually exclusive flags: `--stop`, `--status`, `--port`
  - [x] Default (no flags): create `OrchestrationEngine`, create `DaemonConfig`, check if already running (error if so), call `start_server(engine, config)`
  - [x] `--status`: call `is_daemon_running()`; print status and exit
  - [x] `--stop`: read PID file, send SIGTERM via `os.kill(pid, signal.SIGTERM)`; print confirmation
  - [x] `--port`: override HTTP port in `DaemonConfig`
  - [x] Register in `cli/app.py`: `app.command("serve")(serve)`
  - [x] Success: `orchestration serve --help` shows the command with options

- [x] **T16: Test serve command**
  - [x] Create `tests/cli/test_serve.py`
  - [x] `test_serve_status_not_running` — no PID file → prints "not running"
  - [x] `test_serve_status_running` — PID file with live PID → prints "running"
  - [x] `test_serve_stop_sends_sigterm` — mock `os.kill`; verify SIGTERM sent to PID from file
  - [x] `test_serve_stop_not_running` — no PID file → prints error, exits non-zero
  - [x] `test_serve_already_running` — PID file with live PID → prints error about existing daemon
  - [x] Success: all tests pass; ruff clean

- [x] **T17: Refactor spawn and list commands**
  - [x] Update `src/orchestration/cli/commands/spawn.py`:
    - [x] Replace `get_registry()` + direct `registry.spawn()` with `DaemonClient().spawn()`
    - [x] Add `DaemonNotRunningError` handler with user-friendly error message
    - [x] Remove `_load_provider` call (now handled by engine)
    - [x] Keep display logic (Rich output) unchanged
  - [x] Update `src/orchestration/cli/commands/list.py`:
    - [x] Replace `get_registry()` + `registry.list_agents()` with `DaemonClient().list_agents()`
    - [x] Add `DaemonNotRunningError` handler
    - [x] Keep Rich table display unchanged
  - [x] Success: both commands produce same user-visible output when daemon is running; show clear error when daemon is not running

- [x] **T18: Test spawn and list refactors**
  - [x] Update `tests/cli/test_spawn.py` — mock `DaemonClient` instead of `get_registry`; test happy path and daemon-not-running error
  - [x] Update `tests/cli/test_list.py` — mock `DaemonClient`; test happy path and daemon-not-running error
  - [x] Success: all tests pass; ruff clean

- [x] **T19: Refactor task and shutdown commands**
  - [x] Update `src/orchestration/cli/commands/task.py`:
    - [x] Replace direct registry + `agent.handle_message()` with `DaemonClient().send_message()` (for existing agents) or appropriate task endpoint
    - [x] Add `DaemonNotRunningError` handler
    - [x] Keep response display logic unchanged
  - [x] Update `src/orchestration/cli/commands/shutdown.py`:
    - [x] Replace `get_registry()` calls with `DaemonClient().shutdown_agent()` / `shutdown_all()`
    - [x] Add `DaemonNotRunningError` handler
    - [x] Keep `ShutdownReport` display unchanged
  - [x] Success: both commands produce same user-visible output; show clear error when daemon not running

- [x] **T20: Test task and shutdown refactors**
  - [x] Update `tests/cli/test_task.py` — mock `DaemonClient`; test happy path and daemon-not-running
  - [x] Update `tests/cli/test_shutdown.py` — mock `DaemonClient`; test happy path and daemon-not-running
  - [x] Success: all tests pass; ruff clean

- [x] **T21: Implement message command**
  - [x] Create `src/orchestration/cli/commands/message.py`
  - [x] `message(agent_name: str, prompt: str)` — constructs `DaemonClient`, calls `send_message(agent_name, prompt)`, displays response messages using same styling as `task` output
  - [x] Handle `DaemonNotRunningError` and agent-not-found errors with user-friendly messages
  - [x] Register in `cli/app.py`: `app.command("message")(message)`
  - [x] Success: `orchestration message --help` shows the command

- [x] **T22: Implement history command**
  - [x] Create `src/orchestration/cli/commands/history.py`
  - [x] `history(agent_name: str, limit: int | None)` — calls `DaemonClient().get_history(agent_name, limit)`, displays messages with sender, timestamp, and content
  - [x] Handle `DaemonNotRunningError` with user-friendly message
  - [x] Register in `cli/app.py`: `app.command("history")(history)`
  - [x] Success: `orchestration history --help` shows the command with `--limit` option

- [x] **T23: Test message and history commands**
  - [x] Create `tests/cli/test_message.py`:
    - [x] `test_message_displays_response` — mock `DaemonClient.send_message`; verify output contains response content
    - [x] `test_message_daemon_not_running` — mock `DaemonNotRunningError`; verify error message
  - [x] Create `tests/cli/test_history.py`:
    - [x] `test_history_displays_messages` — mock `DaemonClient.get_history`; verify output shows messages
    - [x] `test_history_daemon_not_running` — mock `DaemonNotRunningError`; verify error message
    - [x] `test_history_with_limit` — verify `--limit` param passed to client
  - [x] Success: all tests pass; ruff clean

- [x] **T24: Full validation pass**
  - [x] `pytest` (full suite) — all green, no regressions
  - [x] `ruff check src/` — clean
  - [x] `ruff format --check src/` — clean
  - [x] `pyright src/` — zero errors
  - [x] Success: all four checks pass

- [x] **T25: Commit CLI changes**
  - [x] `git add` all new and modified CLI command files, test files
  - [x] Commit: `feat: add serve, message, history commands and refactor CLI to use daemon`

- [x] **T26: Integration test**
  - [x] Create `tests/server/test_integration.py`
  - [x] Single test using real `OrchestrationEngine` + `create_app` + `httpx.AsyncClient(ASGITransport)` + mock provider (no real LLM calls):
    1. [x] `POST /agents` — spawn agent, verify 200 with agent info
    2. [x] `GET /agents` — list shows the agent
    3. [x] `POST /agents/{name}/message` — send message, verify response messages returned
    4. [x] `GET /agents/{name}/history` — verify history contains both human and agent messages
    5. [x] `DELETE /agents/{name}` — shutdown, verify 204
    6. [x] `GET /agents/{name}/history` — verify history still accessible after shutdown
    7. [x] `GET /agents` — list no longer shows the agent
    8. [x] `GET /health` — verify status ok, agent count 0
  - [x] Success: integration test passes end-to-end

- [x] **T27: Final commit and validation**
  - [x] `pytest` (full suite) — all green
  - [x] `ruff check src/` — clean
  - [x] `pyright src/` — zero errors
  - [x] Commit: `test: add daemon integration test`
  - [x] Success: `git status` clean; all checks pass

---

## Implementation Notes

- **ASGITransport for route tests**: Use `httpx.AsyncClient(transport=ASGITransport(app=app))` — no real server process needed. This is the standard FastAPI testing approach.
- **MockAgent in tests**: The mock agent's `handle_message` should be an async generator that yields configurable response Messages. Make it simple — a fixture parameter or attribute controls what it returns.
- **Provider auto-loading**: The `_load_provider` function from `spawn.py` moves into the engine (or a shared utility). It uses `importlib.import_module(f"orchestration.providers.{name}")` — same logic, new location.
- **DaemonClient transport**: For Unix socket, use `httpx.AsyncHTTPTransport(uds=socket_path)`. The base URL must still be set (httpx requires it) — use `http://localhost` as a placeholder since routing is by socket, not hostname.
- **Signal handling in daemon**: Use `asyncio.get_event_loop().add_signal_handler()` for SIGTERM/SIGINT. Set an `asyncio.Event` that the main loop checks, triggering graceful shutdown.
- **`review` command**: Left unchanged in this slice. It continues to use SDK agents directly. Convergence planned for slice 15 (Review Findings Pipeline).
- **`config` command**: Left unchanged — stateless file operations, no daemon needed.
