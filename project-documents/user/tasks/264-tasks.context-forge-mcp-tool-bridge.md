---
docType: tasks
project: squadron
slice: 264-slice.context-forge-mcp-tool-bridge
lldReference: project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261, 262, 263]
dateCreated: 20260831
dateUpdated: 20260901
status: complete
---

# Tasks: Context-Forge MCP Tool Bridge

## Context Summary

Slices 261–263 gave non-SDK models file/shell tools, an agentic loop, and the pipeline YAML
surface. This slice adds five curated context-forge tools (`cf_set_phase`, `cf_set_slice`,
`cf_build_context`, `cf_prompt_get`, `cf_workflow_status`) backed by a real MCP stdio client,
so a tool-capable non-SDK model can drive the workflow itself. Everything is additive inside
`src/squadron/tools/`: no agent, executor, dispatch, or schema changes — 263's
`validate_allowed_tools` is registry-driven, so the new names become valid pipeline YAML the
moment they register.

Facts from the design a junior implementer must not lose:

1. **Layering is one-way.** `cf_tools.py` depends on `mcp_bridge.py`, never the reverse. The
   bridge is a generic single-call MCP transport that knows nothing about context-forge.
2. **Errors are values.** Executors never raise to the loop (261 contract). Every failure
   mode in the design's failure-mode table returns `ToolResult(is_error=True)` and logs at
   WARNING — spawn failure, timeout, server `isError`, protocol error. Missing required args
   fail before any spawn (no log needed; result text names the field).
3. **No silent no-ops.** A `CallToolResult` with no text blocks maps to an explicit
   `is_error=True` result naming the condition, never an empty success (slice-909 lesson).
   Non-text blocks are noted by type in the content, not dropped.
4. **CF argument names live in exactly one place.** The mapping table in `cf_tools.py`
   (`developmentPhase`, `fileSlice`, `instruction`, `templateName`) is the only spot CF MCP
   vocabulary appears. The live contract test defends it against CF schema drift.
5. **The model never sees project identity.** No `projectId`/`projectPath` in any schema.
   The factory-bound `cwd` is passed as `StdioServerParameters(cwd=...)`; CF resolves the
   project from CWD.
6. **Teardown is the SDK's job.** mcp 1.26.0 spawns the server with
   `start_new_session=True` and kills the process group (`os.killpg`, SIGKILL escalation) on
   context exit, so `npx` grandchildren are reaped on timeout. Do not add custom
   process-kill code; do assert the behavior in the timeout test.
7. **Registration is unconditional at import** (design D4) so pipeline validation stays
   deterministic regardless of whether node/npx is installed on this machine.

Config access goes through the existing manager (`squadron.config.manager.get_config` /
`get_typed_config`), never raw `os.environ`. Registered tool names before this slice:
`read_file`, `write_file`, `bash` — read via `tools.list_tools()`, never hard-coded.

**Sequencing:** config keys first (leaf dependency), then test scaffolding (fake MCP
server) before the bridge it tests, then bridge → bridge tests → descriptors → descriptor
tests → live contract test → close-out. Each task leaves the suite green.

**Commit protocol — applies to every task below.**

1. `uv run ruff format .` immediately before the commit, never skipped
2. `git add` from the project root; semantic message (`feat:`, `test:`, `chore:`, `docs:`)
3. The task's scoped test command passes first; a task is not done until committed

**Branch.** This is Phase 6 implementation work, so it happens on
`264-slice.context-forge-mcp-tool-bridge`. Before creating it, read
`cf config get git.integration_branch` and fork from that value (or `main` if empty) — do
not assume the value recorded at plan-authoring time is still current.

---

## Task 1: Config keys for the bridge

- [x] **1.1** Add two entries to `CONFIG_KEYS` in `src/squadron/config/keys.py`, following
  the existing `ConfigKey` pattern
  - [x] `cf.mcp_command` — `type_=str`, `default="npx -y @context-forge/mcp"`, description
    stating it is the launch command for the CF MCP stdio server, split with `shlex.split`
  - [x] `cf.mcp_timeout_s` — `type_=int`, `default=60`, description stating it is the
    wall-clock cap per bridge call (spawn + initialize + call)
  - [x] Effort: 1/5

- [x] **Task 1 success criteria**
  - [x] `get_config("cf.mcp_command")` returns the default with no config file present;
    same for `cf.mcp_timeout_s` via `get_typed_config`
  - [x] Existing config tests still green
  - [x] `ruff format` run, then committed: `feat: add cf.mcp_command and cf.mcp_timeout_s config keys`

## Task 2: Test the config keys

- [x] **2.1** Extend the existing config test module (locate the tests covering
  `CONFIG_KEYS` defaults; add there rather than creating a parallel file)
  - [x] `test_cf_mcp_command_default` — asserts the exact default string
  - [x] `test_cf_mcp_timeout_default` — asserts `60` and that the typed read returns `int`
  - [x] Effort: 1/5

- [x] **Task 2 success criteria**
  - [x] Scoped config tests green
  - [x] `ruff format` run, then committed: `test: cover cf mcp bridge config key defaults`

## Task 3: Fake MCP server test fixture

Test infrastructure first: tasks 5, 6 both need a real stdio peer.

- [x] **3.1** Create `tests/tools/fake_mcp_server.py` — a minimal stdio MCP server built on
  the python `mcp` SDK (already a dependency), runnable as
  `python tests/tools/fake_mcp_server.py`
  - [x] `echo` tool — returns its `text` argument as a `TextContent` block
  - [x] `fail` tool — returns a result with `isError=True` and explanatory text
  - [x] `sleep` tool — sleeps for its `seconds` argument before responding (drives the
    timeout test)
  - [x] `empty` tool — returns a result with zero content blocks (drives the no-silent-
    no-op mapping rule)
  - [x] `nontext` tool — returns a result whose blocks include a non-text block (e.g. an
    `ImageContent` with a tiny inline payload) alongside optional text (drives the
    non-text-block mapping rule)
  - [x] Accept a `--pid-file <path>` argument: when given, write `os.getpid()` to that
    path at startup (supports Task 5.2's teardown assertion)
  - [x] Keep it under ~80 lines; it is a fixture, not a product
- [x] **3.2** Add a shared helper (in `tests/tools/conftest.py` or the fixture module) that
  builds `StdioServerParameters` pointing at the fake server via `sys.executable`, so tests
  never depend on `python` being on PATH
  - [x] Effort: 2/5

- [x] **Task 3 success criteria**
  - [x] Launching the fake server and calling `echo` by hand (or via a trivial smoke test)
    round-trips text
  - [x] `ruff format` run, then committed: `test: add fake stdio MCP server fixture`

## Task 4: Generic MCP transport helper `mcp_bridge.py`

- [x] **4.1** Create `src/squadron/tools/mcp_bridge.py` with one public coroutine:
  `call_mcp_tool(server: StdioServerParameters, tool: str, arguments: dict[str, object], timeout_s: int) -> ToolResult`
  - [x] Spawn via `mcp.client.stdio.stdio_client`, `ClientSession.initialize()`, then
    `session.call_tool(tool, arguments)`; teardown by async-context exit
  - [x] Wrap the entire spawn → initialize → call span in `asyncio.timeout(timeout_s)`
  - [x] Use the SDK's `get_default_environment()` as the spawned process env (PATH included
    so `npx`/`node` resolve) — callers construct `StdioServerParameters`; the bridge does
    not read config
  - [x] Module knows nothing about context-forge — no CF imports, no CF strings
- [x] **4.2** Implement result mapping per the design's Result mapping rules
  - [x] Join all `TextContent` blocks with `\n` → `ToolResult.content`
  - [x] `CallToolResult.isError` → `is_error=True`, plus `logger.warning`
  - [x] Zero text blocks → `is_error=True` result naming the condition
  - [x] Non-text blocks noted by type in the content
- [x] **4.3** Implement failure handling — every path returns a `ToolResult`, never raises
  - [x] Spawn failure (bad command / missing binary) → `is_error=True` telling the model
    the bridge is unavailable and why; `logger.warning` including the launch command
  - [x] `TimeoutError` from `asyncio.timeout` → `is_error=True`; `logger.warning` with tool
    name and timeout value
  - [x] `McpError` / closed-stream transport errors → `is_error=True`; `logger.warning`
  - [x] Each `except` clause is specific and satisfies the CLAUDE.md exception rules (no
    bare `except`, no silent swallow)
  - [x] Target ~80 lines; hard cap 300 per code-structure rules
  - [x] Effort: 3/5

- [x] **Task 4 success criteria**
  - [x] `pyright` zero errors on the new module; no CF vocabulary anywhere in it
  - [x] Manual smoke against the fake server (`echo`) returns the text
  - [x] `ruff format` run, then committed: `feat: add generic single-call MCP stdio transport helper`

## Task 5: Bridge tests (real stdio round-trip + failure modes)

- [x] **5.1** Create `tests/tools/test_mcp_bridge.py` using the Task 3 fixture — these are
  real subprocess round-trips, no mocks
  - [x] `test_echo_round_trip` — content matches sent text, `is_error is False`
  - [x] `test_server_is_error_maps_to_error_result` — `fail` tool → `is_error is True`
  - [x] `test_empty_result_is_explicit_error` — `empty` tool → `is_error is True`, content
    names the condition (guards the no-silent-no-op rule)
  - [x] `test_nontext_block_noted_by_type` — `nontext` tool → content mentions the block's
    type (guards the not-dropped-silently mapping rule)
  - [x] `test_unknown_tool_name` — calling a tool the fake server lacks → error result,
    not an exception; asserts the WARNING via `caplog` (this is the failure-mode table's
    protocol-error row — its observable signal is asserted here, explicitly)
- [x] **5.2** Timeout test
  - [x] Call `sleep` with a duration well past a short `timeout_s` (e.g. sleep 10, timeout
    1) → `is_error is True` within ~timeout wall-clock
  - [x] Assert the server child process is gone after the call returns — launch the fake
    server with `--pid-file` (Task 3.1), read the PID, and check the process no longer
    exists. This pins the SDK process-group teardown fact from the design
- [x] **5.3** Spawn-failure test
  - [x] `StdioServerParameters(command="definitely-not-a-command")` → `is_error is True`,
    no exception escapes
- [x] **5.4** Observability assertions
  - [x] Each failure-mode test above also asserts its WARNING via `caplog` (per the
    failure-mode table: timeout, server isError, spawn failure, and protocol error each
    have an observable signal — protocol error's assertion lives in
    `test_unknown_tool_name`, 5.1)
  - [x] Effort: 3/5

- [x] **Task 5 success criteria**
  - [x] `uv run pytest tests/tools/test_mcp_bridge.py -q` green
  - [x] No test sleeps longer than a few seconds; timeout test bounded
  - [x] `ruff format` run, then committed: `test: cover mcp_bridge round-trip and failure modes`

## Task 6: CF tool descriptors `cf_tools.py`

- [x] **6.1** Create `src/squadron/tools/cf_tools.py` with name constants and the single
  mapping table from the design (§ Curated tool set) — squadron name → (CF MCP tool,
  argument mapping). CF argument names (`developmentPhase`, `fileSlice`, `instruction`,
  `templateName`) appear here and nowhere else
- [x] **6.2** Implement one descriptor per tool (five total), each with a narrow JSON
  Schema and a factory producing an async executor
  - [x] `cf_set_phase` — `phase: string` required → `project_update {developmentPhase}`
  - [x] `cf_set_slice` — `slice: string` required → `project_update {fileSlice}`
  - [x] `cf_build_context` — `phase?`, `slice?`, `instruction?` all optional, described in
    the schema as ephemeral overrides → `context_build`, only supplied keys forwarded
  - [x] `cf_prompt_get` — `template_name: string` required → `prompt_get {templateName}`
  - [x] `cf_workflow_status` — no parameters → `workflow_status {}`
  - [x] Descriptions tell the model what each tool does in workflow terms (they are the
    model's only documentation)
  - [x] Prefer one shared executor-builder parameterized by the mapping-table entry over
    five hand-written near-identical closures (DRY)
- [x] **6.3** Executor behavior
  - [x] Validate required args first; missing/blank → `ToolResult(is_error=True)` naming
    the field, **before any spawn**
  - [x] Read `cf.mcp_command` (split with `shlex.split`) and `cf.mcp_timeout_s` through the
    config manager at execute time; build
    `StdioServerParameters(command, args, cwd=str(bound_cwd), env=get_default_environment())`
  - [x] Delegate to `call_mcp_tool`; return its result unchanged
  - [x] No `projectId`/`projectPath` anywhere in schemas or sent arguments
- [x] **6.4** Register all five at module scope via the 261 `register()` path
  (unconditional, D4), and add the side-effect import to `src/squadron/tools/__init__.py`
  mirroring the existing `builtin` import comment style
  - [x] Target ~150 lines
  - [x] Effort: 3/5

- [x] **Task 6 success criteria**
  - [x] `import squadron.tools` then `list_tools()` includes exactly the five `cf_*` names
    plus the three builtins
  - [x] `pyright` zero errors; `cf_tools` imports `mcp_bridge`, never the reverse
  - [x] `ruff format` run, then committed: `feat: add five context-forge MCP bridge tools`

## Task 7: Descriptor tests (registration, arg mapping, gating)

- [x] **7.1** Create `tests/tools/test_cf_tools.py`
  - [x] `test_all_five_registered` — names present in `list_tools()` after package import
  - [x] `test_schemas_expose_no_project_identity` — no schema mentions
    `projectId`/`projectPath`
- [x] **7.2** Argument-mapping tests with `call_mcp_tool` mocked (patch it where
  `cf_tools` looks it up); one test per tool asserting the exact CF tool name and argument
  dict sent
  - [x] `cf_set_phase("Phase 5")` → `("project_update", {"developmentPhase": "Phase 5"})`
  - [x] `cf_set_slice` → `("project_update", {"fileSlice": ...})`
  - [x] `cf_build_context` with no args → `("context_build", {})`; with all three →
    all three CF keys present; with one → only that key (no `None` padding)
  - [x] `cf_prompt_get` → `("prompt_get", {"templateName": ...})`
  - [x] `cf_workflow_status` → `("workflow_status", {})`
- [x] **7.3** Behavior tests
  - [x] Missing required arg (`cf_set_phase({})`) → `is_error is True`, field named,
    mocked transport **not called** (no spawn)
  - [x] Transport result (success and `is_error=True`) passes through unchanged
  - [x] Executor reads command/timeout from config: with `cf.mcp_command` set to a
    multi-word value, the `StdioServerParameters` passed to the mock has the shlex-split
    command/args and `cwd` equal to the factory-bound directory
- [x] **7.4** Pipeline-surface test — `validate_allowed_tools` (263) accepts
  `["cf_workflow_status"]` and still rejects `["cf_bogus"]`, proving the registry-driven
  YAML surface with zero schema changes
  - [x] Effort: 3/5

- [x] **Task 7 success criteria**
  - [x] `uv run pytest tests/tools/test_cf_tools.py -q` green with no network and no node
  - [x] `ruff format` run, then committed: `test: cover cf tool arg mapping, gating, and registration`

## Task 8: Availability-gated live contract test

- [x] **8.1** Create `tests/tools/test_cf_contract_live.py` (schema-drift defense)
  - [x] Module-level availability gate: attempt to launch the configured
    `cf.mcp_command` server (or detect a launchable command); on failure,
    `pytest.skip` the module with a reason naming the command — CI without node stays
    green, any environment with CF verifies the contract
  - [x] Spawn the real server, `list_tools()` over the session, assert the four curated CF
    MCP tool names exist (`project_update`, `context_build`, `prompt_get`,
    `workflow_status`)
  - [x] For each, assert every argument name squadron sends (from the Task 6 mapping
    table — import the constants, do not restate strings) appears in that tool's input
    schema
- [x] **8.2** One live round-trip: materialized `cf_workflow_status` executor from the
  squadron repo root returns non-error content mentioning the project
  - [x] Effort: 2/5

- [x] **Task 8 success criteria**
  - [x] Test passes locally (node present); forcing an unlaunchable command skips rather
    than fails
  - [x] Contract assertions read argument names from `cf_tools` constants (single source)
  - [x] `ruff format` run, then committed: `test: add availability-gated CF MCP contract test`

## Task 9: Verification walkthrough and close-out

- [x] **9.1** Run design walkthrough steps 1–3 (§ Verification Walkthrough) and record
  outcomes in the walkthrough section of the slice design (refine wording where reality
  differed)
  - [x] Step 1: registration + `cf_bogus` pipeline rejection
  - [x] Step 2: live `cf_workflow_status` smoke returns real project status
  - [x] Step 3: bad `cf.mcp_command` → observable failure; **unset the key afterwards**
- [x] **9.2** Quality gates: `uv run pytest -q` full suite green; `uv run pyright` zero
  errors; `uv run ruff check .` clean
- [x] **9.3** Docs and state
  - [x] DEVLOG entry under today's date (per prompt.ai-project.system.md Session State
    Summary); CHANGELOG bullet only if user-facing behavior warrants one
  - [x] Mark this task file and the slice design `status: complete` (delegate checklist
    updates to task-checker)
  - [x] Walkthrough step 4 (SC6 live non-SDK model demo) runs from a standard terminal —
    the `sq run` CLAUDECODE guard refuses inside Claude Code — so it stays open past
    close-out. Track it explicitly, in both places: annotate walkthrough §4 in the slice
    design as "open — requires standard terminal" with the checkbox left unchecked, and
    name it as an open item in the close-out DEVLOG entry. SC6's executor half (8.2) is
    evidenced at close-out; the dispatch half is evidenced by this follow-up.
    **Resolved 20260901:** the follow-up ran — `sq run cf-tools-demo 264 -v` with `kimi27`
    from a plain terminal made two real tool calls whose reported values all matched live CF
    state. SC6 is fully evidenced; walkthrough §4 is checked in the slice design
- [x] **9.4** Merge `264-slice.context-forge-mcp-tool-bridge` into the target read in the
  Branch note (integration branch, or `main` if unset); do not delete the branch
  - [x] Effort: 2/5

- [x] **Task 9 success criteria**
  - [x] All gates green at the merge commit; walkthrough steps 1–3 recorded
  - [x] `ruff format` run, then committed/merged: `docs: complete slice 264` (plus the
    merge commit)
