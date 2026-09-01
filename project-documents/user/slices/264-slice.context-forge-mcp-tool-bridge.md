---
docType: slice-design
project: squadron
slice: 264-slice.context-forge-mcp-tool-bridge
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261, 262, 263]
interfaces: [265]
dateCreated: 20260831
dateUpdated: 20260901
status: complete
---

# Slice Design: Context-Forge MCP Tool Bridge

## Parent Documents

- Architecture: `260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
- Slice Plan: `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`, entry 4

## Overview

Slices 261–263 gave non-SDK models file and shell tools. What they still cannot do is drive
the workflow itself: set the phase, advance the slice, build their own context prompt, pull a
prompt template. Those operations live in context-forge, reachable today only by squadron's
own code (via the `cf` CLI wrapper in `integrations/context_forge.py`) or by Claude Code (via
the CF MCP server). This slice bridges the gap: a curated set of CF MCP operations exposed as
squadron tools through the slice-261 descriptor protocol, so a pipeline can declare
`allowed_tools: [read_file, write_file, cf_set_phase, cf_build_context]` and a capable
non-SDK model runs the full workflow loop — any phase, without a Claude model in the path.

The bridge speaks real MCP: each executor spawns the published `@context-forge/mcp` stdio
server (verified published, v0.13.0; squadron already depends on the python `mcp` SDK, and
the installed 1.26.0 supports `StdioServerParameters.cwd`). This also proves the adapter
pattern the 260 architecture designed for — the async-first execute interface means MCP
composition is an adapter, not a re-architecture — leaving a clean seam for bridging other
MCP servers later.

Everything in this slice is additive inside `squadron/tools/`. No agent, executor, dispatch,
or pipeline-schema changes: slice 263's `allowed_tools` validation is registry-driven, so the
new names become valid pipeline YAML the moment they register.

## Value

- A non-SDK model can advance CF state (phase, slice), rebuild its own context, and fetch
  prompt templates mid-dispatch — closing the last gap between "can edit files" and "can run
  the workflow."
- Proves the MCP-bridge composition claim from the 260 architecture with a real server.
- The generic single-call MCP transport helper is the extension seam for future MCP-backed
  tools (other servers), at zero additional protocol cost.

## Technical Scope

### In scope

1. Generic MCP transport helper: `tools/mcp_bridge.py` — one async function that spawns a
   stdio MCP server, initializes a session, calls one tool, maps the result to `ToolResult`,
   and tears down. Timeout-guarded; errors are values.
2. CF tool descriptors: `tools/cf_tools.py` — five curated tools (`cf_set_phase`,
   `cf_set_slice`, `cf_build_context`, `cf_prompt_get`, `cf_workflow_status`) registered at
   import time alongside the builtins.
3. Config keys for the server launch command and per-call timeout.
4. Tests: argument-mapping units (mocked transport), a real stdio round-trip against a
   python fake MCP server, failure-mode coverage (spawn failure, timeout, server error), and
   an availability-gated live contract test against the real CF server.

### Out of scope

- Dynamic discovery of CF MCP tools (curated subset only, per slice plan).
- Bridging any other MCP server (the transport helper is the seam; no second consumer yet).
- Session pooling / persistent MCP connections (see D3).
- Changes to `integrations/context_forge.py` (the CLI client keeps serving squadron's own
  code paths; see D6).
- Review-path tool activation (slice 265).

## Architecture

### Component layout

```
squadron/tools/
  models.py       (261, unchanged)  ToolDescriptor / ToolResult / ToolExecutor
  registry.py     (261, unchanged)  register / lookup / materialize
  builtin.py      (261, unchanged)  read_file, write_file, bash
  mcp_bridge.py   (new)             call_mcp_tool(server, tool, args, timeout) -> ToolResult
  cf_tools.py     (new)             five CF descriptors; register() at import
  __init__.py     (edited)          also imports cf_tools for its registration side effect
```

`cf_tools.py` depends on `mcp_bridge.py`, never the reverse. The transport helper knows
nothing about context-forge; a future bridge to another server reuses it unchanged.

### Curated tool set

Squadron-semantic names and narrow schemas; the executor maps them to the CF MCP call. The
model never sees or supplies `projectId`/`projectPath` — project identity always resolves
from the working directory the factory bound (see Security).

| Squadron tool | Parameters (JSON Schema) | CF MCP call | Arguments sent |
|---|---|---|---|
| `cf_set_phase` | `phase: string` (required) | `project_update` | `{developmentPhase: phase}` |
| `cf_set_slice` | `slice: string` (required) | `project_update` | `{fileSlice: slice}` |
| `cf_build_context` | `phase?: string`, `slice?: string`, `instruction?: string` (all optional, ephemeral overrides) | `context_build` | `{developmentPhase?, fileSlice?, instruction?}` |
| `cf_prompt_get` | `template_name: string` (required) | `prompt_get` | `{templateName: template_name}` |
| `cf_workflow_status` | none | `workflow_status` | `{}` |

Why these five: the slice plan names the first four (the write/read pair a model needs to
advance and re-contextualize itself). `cf_workflow_status` is added because state-mutating
tools without a state-reading tool force the model to mutate blind; status is the read that
makes the writes safe, and it is trivially cheap.

`cf_build_context` overrides are ephemeral by design (CF's `context_build` applies them
without writing the store), so a model can preview another phase's context without mutating
project state.

### Data flow (one tool call)

```
model emits tool_call cf_set_phase {"phase": "Phase 5: Task Breakdown"}
  → agentic loop (262) dispatches to the materialized executor
    → executor validates required args        (missing → ToolResult(is_error=True), no spawn)
    → call_mcp_tool(server_params, "project_update", {"developmentPhase": ...}, timeout)
        spawn: stdio_client(StdioServerParameters(command, args, cwd=bound_cwd))
        ClientSession.initialize()
        session.call_tool(name, arguments)    (whole call wrapped in asyncio.timeout)
        map CallToolResult → ToolResult       (text blocks joined; isError → is_error)
        teardown (async context exit)
  → ToolResult content returned to the model as the role:"tool" message (262 mechanics)
```

### Result mapping

- All `TextContent` blocks of the `CallToolResult` joined with `\n` → `ToolResult.content`.
- `CallToolResult.isError` → `ToolResult.is_error` (CF-reported failures flow to the model
  as error results, exactly like builtin tool errors).
- No text blocks → explicit `is_error=True` result naming the condition (never an empty
  success — silent no-ops are the slice-909 lesson).
- Non-text blocks are noted by type in the content, not dropped silently.

### Failure modes (enumerated per review-code rules)

| Failure | Behavior | Observable signal |
|---|---|---|
| Spawn fails (npx absent, package fetch fails, command misconfigured) | `is_error=True` result telling the model the CF bridge is unavailable and why | `logger.warning` with the launch command |
| Call exceeds timeout (hang) | `asyncio.timeout` cancels; session teardown kills the server process tree; `is_error=True` | `logger.warning` with tool name and timeout value |
| Server returns `isError` | passed through as `is_error=True` | `logger.warning` (CF-reported failure; meets the WARNING+ observability floor uniformly) |
| Protocol/transport error mid-call (`McpError`, closed stream) | `is_error=True` | `logger.warning` |
| Model omits a required argument | `is_error=True` before any spawn | no log needed; result text names the missing field |

Executors never raise to the loop (261 contract: errors are values). Each row above has a
test asserting the observable signal.

**Exception grouping (learned in implementation, 20260901).** The SDK runs its transport
inside anyio task groups, so a failure raised in-band — a protocol error, a broken pipe —
reaches the caller wrapped in a `BaseExceptionGroup`, not as itself. A plain `except McpError`
therefore never matches a real protocol error: it falls through to the catch-all and reports
the group's own message, "unhandled errors in a TaskGroup", which names nothing a model or an
operator can act on. `call_mcp_tool` consequently uses one classifying handler that flattens
the group to its leaves and classifies on those, checking spawn failure before protocol error
(a server that never started also yields a closed-stream protocol error downstream, and the
launch problem is the one to report). Spawn failure alone escapes ungrouped, which is why an
early test of that path passed while the protocol-error row was in fact unimplemented — found
by the slice-264 code review (F001).

Teardown reaches npx grandchildren (verified against the installed SDK, mcp 1.26.0): the
stdio client spawns the server with `start_new_session=True` and terminates via
`os.killpg` on the process group, escalating to SIGKILL after 2s (Windows: process-tree
kill). So the node process `npx` forks is in the same group and is reaped on timeout — no
orphaned servers. The implementation relies on this SDK behavior; the fake-server timeout
test asserts the child process is gone after cancellation.

### Configuration

Two keys in `config/keys.py`, following the existing pattern:

- `cf.mcp_command` (str, default `"npx -y @context-forge/mcp"`) — launch command for the CF
  MCP stdio server, split with `shlex.split`. Local-dev override example:
  `node /path/to/context-forge/packages/mcp-server/dist/index.js`.
- `cf.mcp_timeout_s` (int, default `60`) — wall-clock cap per bridge call (spawn +
  initialize + call).

The default env for the spawned process is the mcp SDK's `get_default_environment()` (PATH
included, so `npx`/`node` resolve).

### Security

- Bound working directory only: the factory receives the resolved `cwd` (same value the file
  tools jail to) and spawns the server with `StdioServerParameters(cwd=...)`. CF resolves
  the active project from CWD; the tool schemas expose no `projectId`/`projectPath`, so the
  model cannot target another project.
- Curated subset means no destructive CF surface is reachable (no project delete, no config
  writes, no worktree mutation).

## Integration Points

- **261 registry:** `cf_tools.py` registers via the same `register()` path; duplicate-name
  fail-fast applies. `tools/__init__.py` gains one import line.
- **262 loop:** no changes; executors are ordinary async `ToolExecutor`s.
- **263 validation:** no changes; `validate_allowed_tools` is registry-driven, so `cf_*`
  names become valid step YAML automatically.
- **Config manager:** two new keys, read at factory/execute time through the existing
  manager (no raw `os.environ`).
- **265 (future):** reviews get the read-only subset; `cf_workflow_status` is a candidate
  addition to review tool sets there — no coupling created here.

## Implementation Details

### Files changed

| File | Change |
|---|---|
| `src/squadron/tools/mcp_bridge.py` | new — generic single-call MCP transport (~80 lines) |
| `src/squadron/tools/cf_tools.py` | new — name constants, five descriptors, arg mapping, registration (~150 lines) |
| `src/squadron/tools/__init__.py` | import `cf_tools` for registration side effect |
| `src/squadron/config/keys.py` | add `cf.mcp_command`, `cf.mcp_timeout_s` |
| `tests/tools/test_cf_tools.py` | new — registration, arg mapping, result mapping, failure modes |
| `tests/tools/test_mcp_bridge.py` | new — real stdio round-trip vs fake python MCP server; timeout; spawn failure |
| `tests/tools/fake_mcp_server.py` | new — minimal stdio MCP server (python `mcp` SDK) with echo/error/sleep tools |
| `tests/tools/test_cf_contract_live.py` | new — availability-gated contract test vs real CF server |

### Schema-drift defense

The five argument names sent to CF (`developmentPhase`, `fileSlice`, `instruction`,
`templateName`) are hand-authored against CF MCP v0.13.0 and can drift with CF releases. The
live contract test spawns the real server, lists its tools, and asserts (a) the four curated
MCP tool names exist and (b) each argument name squadron sends appears in that tool's input
schema. Gated with a skip marker when the server cannot be launched, so CI without node
stays green while any environment with CF present verifies the contract.

## Success Criteria

1. `list_tools()` includes the five `cf_*` names after importing `squadron.tools`; a
   pipeline step declaring them passes load-time validation with no schema changes.
2. Each executor sends exactly the mapped MCP call and arguments (asserted with a mocked
   transport), and maps results per the Result mapping rules.
3. A real stdio round-trip works: against the fake python MCP server, an executor returns
   the server's text; server `isError` and timeout paths produce `is_error=True` with the
   WARNING signals from the failure-mode table.
4. Spawn failure (bad command) yields an `is_error=True` result and a WARNING — never an
   exception out of the executor.
5. Live contract test passes in an environment with CF available.
6. Live demo: in the squadron repo, a materialized `cf_workflow_status` executor returns the
   actual project status; a dispatch with a tool-capable non-SDK model can call
   `cf_build_context` and receive assembled context (walkthrough §4).
7. Full suite green; strict pyright zero errors; ruff clean.

## Design Decisions

**D1 — Real MCP client, not a wrapper over the `cf` CLI.** The existing
`ContextForgeClient` could back these tools with subprocess calls and no new transport. The
MCP client is chosen because (a) the slice's architectural purpose is proving the MCP-bridge
composition the 260 arch designed the async-first interface for; (b) it yields a generic
transport seam for other MCP servers, which a CLI wrapper cannot; (c) CF maintains CLI/MCP
parity, so behavior is equivalent either way.

**D2 — Narrow squadron-semantic schemas, not mirrored CF schemas.** `cf_set_phase(phase)`
instead of exposing `project_update`'s full field surface. Smaller blast radius (the model
cannot rewrite `projectPath` or arbitrary fields), clearer tool descriptions for the model,
and the mapping table is the single place CF argument names appear.

**D3 — Per-call session (spawn → call → teardown).** The descriptor protocol has no
teardown hook, and adding lifecycle management to `ToolDescriptor` for one consumer is
unjustified complexity. CF operations are low-frequency (a handful per dispatch), so node
startup cost per call is acceptable. If profiling ever says otherwise, session pooling can
live entirely inside `mcp_bridge.py` without touching the protocol.

**D4 — Unconditional registration at import.** CF tools register whether or not the server
is launchable, keeping load-time pipeline validation deterministic (a pipeline's validity
cannot depend on what's installed on this machine). Unavailability surfaces at execution as
an explicit `is_error` result the model can react to — fail explicit, not silent.

**D5 — Launch command as config with a real default.** `npx -y @context-forge/mcp` works
anywhere node is present (package verified published); the config key exists for local-dev
builds and pinning. Centralized in `config/keys.py` per the no-scattered-defaults rule.

**D6 — `integrations/context_forge.py` untouched.** It serves squadron's own code
(review/pipeline internals) over the CLI; this slice serves model-facing tools over MCP.
The operation sets barely overlap today. Consolidating transports is a refactor for the day
a real duplication appears, not now.

## Risks

- **CF MCP schema drift** — argument names change under a CF release. Mitigated by the live
  contract test (Schema-drift defense) and by D2 keeping all CF argument names in one
  mapping table.
- **`npx -y` cold-start fetch** — first call in a clean environment downloads the package
  (seconds, needs network). Acceptable for a default; documented; pin via config for
  offline/deterministic setups.

## Verification Walkthrough

Verified during Phase 6 implementation (20260901). Steps 1–3 and 5 were run and their real
output is recorded below. Step 4 needs a standard terminal (the `sq run` CLAUDECODE guard
refuses to execute inside a Claude Code session) and remains **open**.

All commands run from the squadron repo root. `uv run` is required — the package is not on
the ambient interpreter's path.

### 1. Tools registered and valid in pipeline YAML

- [x] Verified.

```bash
uv run python -c "import squadron.tools as t; print([n for n in t.list_tools() if n.startswith('cf_')])"
```

Actual output:

```
['cf_set_phase', 'cf_set_slice', 'cf_build_context', 'cf_prompt_get', 'cf_workflow_status']
```

For the pipeline-YAML half, write a scratch pipeline with a dispatch step carrying
`allowed_tools: [read_file, cf_workflow_status]`, then load and validate it — and repeat with
one name changed to `cf_bogus`:

```bash
uv run python -c "
from squadron.pipeline.loader import load_pipeline, validate_pipeline
d = load_pipeline('<path-to-scratch>.yaml')
print([e.message for e in validate_pipeline(d)] or 'VALID')
"
```

Actual output — the good pipeline prints `VALID`; the `cf_bogus` variant prints one error
naming the unknown tool and listing all eight registered names:

```
["Tool 'cf_bogus' is not registered. Available tools: ['read_file', 'write_file', 'bash', 'cf_set_phase', 'cf_set_slice', 'cf_build_context', 'cf_prompt_get', 'cf_workflow_status']"]
```

No pipeline-schema change was needed: 263's `validate_allowed_tools` is registry-driven.

### 2. Live single-call smoke (no model, no pipeline)

- [x] Verified.

```bash
uv run python -c "
import asyncio, squadron.tools as t
ex = t.materialize(['cf_workflow_status'], '.')
r = asyncio.run(ex['cf_workflow_status']({}))
print('is_error:', r.is_error)
print(r.content[:300])
"
```

Actual output — real CF state for project squadron, `is_error: False`, JSON beginning:

```
[context-forge-mcp] Server started
is_error: False
{
  "project": "squadron",
  "phase": "Phase 6: Implementation",
  "activeSlice": {
    "name": "context-forge-mcp-tool-bridge",
    "index": 264,
    ...
```

Caveats discovered:

- The CF MCP server writes `[context-forge-mcp] Server started` to stderr. It is not part of
  the tool result and is not an error.
- Warm round-trip is ~1.3s wall-clock (package already fetched). A cold `npx -y` first run
  also downloads the package, which is why `cf.mcp_timeout_s` defaults to 60 and the live
  contract test allows 180s for its availability probe.

### 2b. `cf_build_context` overrides really are ephemeral

- [x] Verified.

The design claims CF's `context_build` applies overrides without writing the store. Confirmed
against the real server — read the phase, build context with a *different* phase override, then
read the phase again:

```bash
uv run python -c "
import asyncio, json, squadron.tools as t
ex = t.materialize(['cf_workflow_status', 'cf_build_context'], '.')
before = asyncio.run(ex['cf_workflow_status']({})).content
r = asyncio.run(ex['cf_build_context']({'phase': 'Phase 3: Architecture'}))
after = asyncio.run(ex['cf_workflow_status']({})).content
print('build is_error:', r.is_error, '| len', len(r.content))
print('phase before:', json.loads(before)['phase'])
print('phase after :', json.loads(after)['phase'])
"
```

Actual output — real context came back, and the stored phase did not move:

```
build is_error: False | len 5741
phase before: Phase 6: Implementation
phase after : Phase 6: Implementation
```

### 3. Failure modes are observable

- [x] Verified.

```bash
uv run sq config set cf.mcp_command "definitely-not-a-command"
# repeat step 2
uv run sq config unset cf.mcp_command
```

Actual output of the repeated step 2 — a WARNING plus an error result the model can read:

```
WARNING:squadron.tools.mcp_bridge:mcp_bridge: could not launch MCP server 'definitely-not-a-command': [Errno 2] No such file or directory: 'definitely-not-a-command'
is_error: True
Error: could not launch the MCP server 'definitely-not-a-command': [Errno 2] No such file or directory: 'definitely-not-a-command'. The bridge is unavailable.
```

`uv run sq config unset cf.mcp_command` then prints `Removed cf.mcp_command from user config`,
and `sq config get cf.mcp_command` reports the default again. **Do not skip the unset** — a
lingering override breaks every later CF tool call, including the live contract test (which
would skip, not fail, and so hide the breakage).

The remaining failure-mode rows (timeout with process-group teardown, server `isError`, empty
result, protocol error) are covered by `tests/tools/test_mcp_bridge.py` against the fake
stdio server, each asserting its WARNING via `caplog`.

### 4. End-to-end with a real non-SDK model (standard terminal) — OPEN

- [ ] **Open — requires a standard terminal.** Not run at close-out: `sq run` refuses to
  execute inside a Claude Code session (CLAUDECODE guard), so this is the one success-criteria
  item (SC6's dispatch half) carried past slice close. SC6's executor half is evidenced by
  step 2 above and by `tests/tools/test_cf_contract_live.py`.

Scratch pipeline step with `model: kimi25` and
`allowed_tools: [cf_workflow_status, cf_build_context]`, prompt instructing the model to
report current workflow state and build context for the active slice. Run `sq run <pipeline>
<slice> -v` from a plain terminal; confirm the transcript shows the tool calls and the final
response contains real CF-derived state (not hallucinated). Tool-call visibility at `-v`
beyond DEBUG logs arrives with slice 265's observability work.


### 5. Quality gates

- [x] Verified at close-out.

```bash
uv run pytest -q          # full suite green
uv run pyright            # zero errors
uv run ruff check .
```

Actual results:

```
3189 passed, 2 skipped, 4 warnings in 439.68s (0:07:19)
0 errors, 0 warnings, 0 informations      # pyright
All checks passed!                        # ruff check
```

Caveats:

- The full suite takes ~7.5 minutes. Run it in the background rather than under a short
  foreground timeout, and do not start a second run alongside the first — two concurrent runs
  roughly double the wall-clock for both.
- `ruff format` does **not** sort imports. Run `uv run ruff check .` (or `--fix`) before
  committing: a format-only pass leaves `I001` import-order findings unreported.

## Effort

2/5 — two small new modules, config keys, and tests; no changes to agent, executor, or
schema surfaces.
