---
docType: slice-design
project: squadron
slice: 261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: []
interfaces: [262, 263, 264, 265]
dateCreated: 20260825
dateUpdated: 20260827
status: complete
---

# Slice Design: Tool Registry, Descriptor Protocol, and Core Tool Implementations

## Parent Documents

- Architecture: `260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
- Slice Plan: `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`, entry 1

## Overview

Foundation slice for initiative 260. Establishes the tool abstraction that every later slice
consumes: a descriptor type describing a tool to an OpenAI-compatible model, a result type,
a process-level registry, and three core tool implementations (`read_file`, `write_file`,
`bash`). Pure data plus pure callables — no `OpenAICompatibleAgent`, `AgentConfig`, executor,
or pipeline change. After this slice lands, tools exist and are fully tested, but nothing in
the running system consumes them yet; observable behavior is unchanged.

The names registered here are the start of the **canonical squadron tool vocabulary**
(`read_file`, `write_file`, `bash`; slice 265 adds `list_files`, `grep`). Templates, pipeline
YAML, and models.toml will declare tools in these names; providers translate at their edges
(decided 20260825, recorded in arch §Allowlist).

## Value

Architectural enablement. Unblocks 262 (agentic loop), 263 (pipeline YAML validation needs
`lookup`), 264 (MCP bridge registers descriptors), and 265 (review tools register here).
Independently testable: every sandbox property (path-escape rejection, timeout, truncation)
is provable in isolation before any model is in the loop.

## Technical Scope

**In:**
- `ToolDescriptor` and `ToolResult` types
- Tool registry: `register`, `lookup`, `materialize`, `list_tools`
- `read_file`, `write_file` (CWD-jailed), `bash` (CWD-anchored, timeout-bounded)
- Registration at package import; unit tests for all of the above

**Out (explicitly):**
- Any agent, provider, executor, or pipeline change (262/263)
- `list_files` / `grep` read-only tools (265, registered through this registry)
- Canonical→Claude name translation for the SDK path (265)
- Bash sandboxing beyond CWD + timeout: network deny, env scrubbing, process isolation
  (arch-documented future work)
- MCP-bridged tools (264)

## Architecture

### Component Structure

New package `src/squadron/tools/`:

```
src/squadron/tools/
  __init__.py       # public API re-exports; imports builtin to trigger registration
  models.py         # ToolDescriptor, ToolResult
  registry.py       # _REGISTRY, register(), lookup(), materialize(), list_tools()
  errors.py         # ToolNotRegisteredError
  builtin.py        # read_file, write_file, bash descriptors + register() calls
  limits.py         # MAX_READ_BYTES, MAX_OUTPUT_BYTES, BASH_TIMEOUT_S (single home)
```

**D1 — location: `squadron/tools/`, not `core/tools/`.** The arch doc says "`core/tools/`
(or analogous)". A sibling top-level package is the analogous choice taken: it mirrors
`squadron/providers/` (the registry pattern it copies — `providers/registry.py`), keeps
`core/` from accreting unrelated responsibilities, and gives 264/265 an obvious home for
additional tool modules. No consumer exists yet, so the location costs nothing to choose now
and would cost real churn to move later.

**D2 — descriptor is a frozen dataclass, not a Protocol.** Descriptors are pure data plus one
factory callable; there is exactly one shape and no polymorphism to dispatch on. A `Protocol`
would add an abstraction with a single implementer (complexity resisted per project rules).

```python
@dataclass(frozen=True)
class ToolDescriptor:
    name: str                      # registry key; canonical vocabulary
    description: str               # surfaced to the model
    parameters: dict[str, object]  # JSON Schema, OpenAI tools[].function.parameters shape
    factory: ToolFactory           # (cwd: Path) -> ToolExecutor

ToolExecutor = Callable[[dict[str, object]], Awaitable[ToolResult]]

@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False
```

**D3 — `cwd` is infrastructure context, closure-bound by the factory.** It never appears in
`parameters`, so the model cannot supply or override it. `materialize` resolves `cwd` once
(`Path(cwd).resolve()`) and passes the resolved path to every factory; executors compare
against that pre-resolved jail root.

**D4 — registry mirrors `providers/registry.py`.** Module-level `_REGISTRY: dict[str,
ToolDescriptor]`, functions not a class. Differences from the provider registry, both
deliberate:
- `register()` raises `ValueError` on duplicate name (provider registry silently overwrites;
  for tools a collision means two definitions of a security-relevant surface — fail fast).
- `materialize(names, cwd)` raises `ToolNotRegisteredError` naming the unknown tool and
  listing registered names (mirrors `get_provider`'s KeyError message style). An unknown name
  at materialization is a caller configuration error, not a model error — the model-requests-
  unknown-tool case is 262's concern and is surfaced to the model there, not here.

**D5 — registration at package import.** `builtin.py` calls `register()` at module scope;
`tools/__init__.py` imports `builtin`. Consumers (262+) write `from squadron import tools`
and the registry is populated — same auto-registration idiom the provider loader relies on.
No `ensure_tools_loaded()` indirection: there is one built-in module, not a lazy plugin map;
264 can introduce conditional loading when a genuinely optional tool source exists.

**D6 — async-first executor surface.** `async def execute(args) -> ToolResult` is the
non-negotiable interface (arch §Async-first). `read_file`/`write_file` wrap filesystem work
in `asyncio.to_thread` (files may be large; never block the loop). `bash` uses
`asyncio.create_subprocess_shell` + `asyncio.wait_for`.

### Data Flow

```
262 (later):  config.allowed_tools ──▶ materialize(names, cwd) ──▶ {name: executor}
                                            │ factories bind resolved cwd
model tool_call ──▶ executor(parsed_args) ──▶ ToolResult(content, is_error)
```

In this slice the flow is exercised only by tests: `materialize([...], tmp_path)` →
executors → assertions on `ToolResult`.

## Implementation Details

### Tool Specifications

All limits live in `limits.py` as named constants — one definition, referenced everywhere
(project rule: no scattered magic values). Starting values: `MAX_READ_BYTES = 256_000`,
`MAX_OUTPUT_BYTES = 64_000`, `BASH_TIMEOUT_S = 120.0`. Tunability beyond editing the constant
is not this slice's concern (266 owns configuration surface).

**`read_file`** — parameters: `path` (string, required).
- Jail check: `(cwd / path).resolve(strict=False).is_relative_to(cwd)` (cwd pre-resolved).
  Applies equally to relative and absolute inputs; symlinks resolved before the check, so a
  symlink pointing outside the jail is rejected.
- Reads text (UTF-8, `errors="replace"`). Content beyond `MAX_READ_BYTES` is truncated with a
  trailing marker line stating truncation and the full size — a truncated read must be
  visible to the model, never silent.
- Failure modes → `is_error=True` with a specific message: path escape, missing file,
  directory path, permission denied.

**`write_file`** — parameters: `path` (string, required), `content` (string, required).
- Same jail check. Parent directories created (`mkdir(parents=True)`) — design steps write
  into nested locations; the parent-dir path is jail-checked before creation. Existing files
  are overwritten; result content states created vs. overwritten and byte count, so the model
  (and DEBUG logs) can see exactly what happened.
- Failure modes → `is_error=True`: path escape, permission denied, path is an existing
  directory.

**`bash`** — parameters: `command` (string, required).
- Runs via `create_subprocess_shell(command, cwd=cwd, stdout=PIPE, stderr=PIPE)`. CWD is the
  only boundary at this stage (arch-documented scope; per-template allowlist is the opt-out).
- **Timeout (`BASH_TIMEOUT_S`):** on expiry, kill the process group (`start_new_session=True`
  at spawn, then `os.killpg`) and return `is_error=True` naming the timeout. Answering the
  failure-mode question "what if this hangs?" — a hung command must not hang 262's loop.
- Result content: stdout and stderr, labeled, each truncated to `MAX_OUTPUT_BYTES` with
  visible markers. Non-zero exit → `is_error=True` with exit code and captured output
  (the model needs the output to react).

### Error Handling

Executors catch the specific expected exceptions per tool (`FileNotFoundError`,
`PermissionError`, `IsADirectoryError`, `NotADirectoryError`, `UnicodeDecodeError`,
`TimeoutError`) and convert to `ToolResult(is_error=True, ...)`. A final
`except Exception` in the shared executor-wrapper logs with `logger.exception` at ERROR and
returns `is_error=True` — justified as a process-boundary handler: from 262 onward the caller
is a model loop, and an unexpected tool bug must become an observable error result, not a
crashed review. This is (a)+(c) under the project exception rules: logged loudly, never
swallowed silently.

**Observability of expected failures (review F003).** Error results returned to the model are
not by themselves operator-visible, so this slice — not 262 — sets the logging contract:

- **WARNING:** jail violations (tool name + rejected path — CWD is the trust boundary, and an
  escape attempt must be visible without `-vv`) and bash timeouts (command + limit). One test
  per case asserts the log record via `caplog`.
- **INFO:** every other `is_error=True` result (missing file, permission denied, non-zero
  exit, truncation), with tool name and reason. These are routine model-probing outcomes that
  the model itself reacts to; elevating them to WARNING would teach operators to ignore
  warnings. INFO keeps them observable in normal logs without crying wolf.

## Integration Points

### Provides to Other Slices
- **262:** `materialize(config.allowed_tools, cwd)`; `descriptor.parameters` → the API
  `tools` array; `ToolResult` → `role:"tool"` message content.
- **263:** `lookup`/`list_tools` for load-time YAML validation of `allowed_tools`.
- **264/265:** `register()` — new tools are additional descriptors; no registry change.

### Consumes from Other Slices
Nothing. Stdlib only (`asyncio`, `pathlib`, `dataclasses`, `os`); no new dependencies.

Frontmatter `dependencies: []` vs. the slice plan's "Dependencies: [100, 140]" (review F004):
the plan lists *initiative* context — the registry idiom copied from 100's provider registry
and the pipeline machinery whose consumers arrive in 262/263. At the artifact level this
slice imports nothing from either, so the design's `[]` is the accurate sequencing input;
the plan entry is initiative-scoped and stands as written.

## Success Criteria

1. `ToolDescriptor` / `ToolResult` / `ToolExecutor` types exist as specified in D2.
2. Registry: `register` stores by name and raises `ValueError` on duplicates; `lookup`
   returns `None` for unknown names; `list_tools` returns registered names; `materialize`
   returns `{name: executor}` for known names and raises `ToolNotRegisteredError` (naming the
   offender and the available set) for unknown ones.
3. `from squadron import tools` yields a registry containing exactly `read_file`,
   `write_file`, `bash`; importing has no other side effects.
4. Path jail: `../escape`, absolute paths outside `cwd`, and symlinks resolving outside `cwd`
   all return `is_error=True` with a message naming the rejected path — for both file tools.
   Absolute and relative paths *inside* `cwd` work.
5. `read_file` happy path returns file content; oversized files are truncated with a visible
   marker; missing file / directory-as-path return specific errors.
6. `write_file` creates the file (nested dirs included), overwrites existing files, and
   reports created/overwritten + byte count.
7. `bash` returns labeled stdout/stderr; non-zero exit → `is_error=True` with exit code;
   a command exceeding `BASH_TIMEOUT_S` is killed (process group) and reports timeout;
   oversized output is truncated with a visible marker.
8. All limits are named constants in `limits.py`; no limit literal appears anywhere else.
9. Every failure mode above is asserted by at least one test (Failure-Mode Enumeration
   rule), including `caplog` assertions that jail violations and bash timeouts log at
   WARNING and that other error results log at INFO.
10. No change to `providers/`, `pipeline/`, `review/`, or `core/models.py`; full existing
    test suite still passes.

## Verification Walkthrough

Verified at Phase 6 completion (20260827) on branch
`261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations`. Every command
below was run from the repo root and produced the output shown. `ruff`, `pyright`, and
`pytest` are not on PATH directly — invoke them from `.venv/bin/`.

**1. New suite passes.**

```
$ .venv/bin/pytest tests/tools/ -q
54 passed in 0.55s
```

**2. No regression anywhere else.**

```
$ .venv/bin/pytest -q
3075 passed, 2 skipped, 5 warnings in 485.85s (0:08:05)
```

The full suite takes about 8 minutes. The pre-existing `RuntimeWarning: coroutine
'_run_pipeline' was never awaited` from `tests/documents/test_schema_drift.py` is unrelated to
this slice and also present on `main`.

**3. Lint and type gate.**

```
$ .venv/bin/ruff format . && .venv/bin/ruff check .
460 files left unchanged
All checks passed!

$ .venv/bin/pyright src/squadron/tools/
0 errors, 0 warnings, 0 informations
```

Caveat: a whole-repo `.venv/bin/pyright` reports **1752 errors**. That count is identical on
`main` and on this branch, and `pyright 2>&1 | grep -c "squadron/tools/"` returns `0` — the
errors are pre-existing in other packages. The new package is strict-clean; verify it with the
scoped invocation above rather than the whole-repo run.

**4. Registry demo.**

```
$ .venv/bin/python -c "from squadron import tools; print(tools.list_tools())"
['read_file', 'write_file', 'bash']
```

**5. Jail demo in a scratch tree.**

```
$ .venv/bin/python - << 'EOF'
import asyncio, tempfile
from squadron import tools
cwd = tempfile.mkdtemp()
ex = tools.materialize(["read_file", "write_file", "bash"], cwd)
async def demo():
    print(await ex["write_file"]({"path": "notes/a.txt", "content": "hello"}))
    print(await ex["read_file"]({"path": "notes/a.txt"}))
    print(await ex["read_file"]({"path": "../../etc/hosts"}))
    print(await ex["bash"]({"command": "ls notes"}))
asyncio.run(demo())
EOF
```

Actual output (the `read_file:` line is the WARNING log record on stderr, interleaved ahead of
stdout — its presence at default verbosity is itself part of the contract):

```
read_file: rejected path outside working directory: ../../etc/hosts
ToolResult(content='Created notes/a.txt (5 bytes).', is_error=False)
ToolResult(content='hello', is_error=False)
ToolResult(content="Error: path '../../etc/hosts' resolves outside the working directory and was rejected.", is_error=True)
ToolResult(content='stdout:\na.txt\n\nstderr:\n', is_error=False)
```

**6. Timeout demo.** `BASH_TIMEOUT_S` is read as a module attribute at call time, so assigning
it (or monkeypatching it in tests) takes effect on the next call — the demo need not wait 120s.

```
$ .venv/bin/python - << 'EOF'
import asyncio, tempfile, time
from squadron import tools
from squadron.tools import limits
limits.BASH_TIMEOUT_S = 2.0
ex = tools.materialize(["bash"], tempfile.mkdtemp())
async def demo():
    t = time.monotonic()
    r = await ex["bash"]({"command": "sleep 300"})
    print(f"elapsed={time.monotonic()-t:.1f}s")
    print(r)
asyncio.run(demo())
EOF

bash: command timed out after 2.0s and was killed: sleep 300
elapsed=2.0s
ToolResult(content='Error: command timed out after 2.0s and was killed: sleep 300', is_error=True)
```

The kill targets the whole process group (`start_new_session=True` at spawn, `os.killpg` on
timeout), so backgrounded children die too. Confirmed separately: running
`{"command": "sleep 987 & sleep 988"}` against a lowered limit leaves no matching process
behind (`pgrep -f "sleep 98"` returns nothing).

**7. Limits are not scattered.**

```
$ grep -rn "256_000\|256000\|64_000\|64000\|120\.0" src/squadron/tools/
src/squadron/tools/limits.py:15:MAX_READ_BYTES = 256_000
src/squadron/tools/limits.py:18:MAX_OUTPUT_BYTES = 64_000
src/squadron/tools/limits.py:21:BASH_TIMEOUT_S = 120.0
```

**8. Nothing consumes tools yet.**

```
$ grep -rn "squadron.tools\|squadron import tools" src/
```

Every hit is inside `src/squadron/tools/` itself. `git diff --stat main..HEAD` touches only
`src/squadron/tools/` (6 files) and `tests/tools/` (8 files), 1088 insertions, 0 deletions —
the behavior-neutrality guarantee holds by construction.


## Implementation Notes

Suggested order: `models.py` + `errors.py` + `limits.py` → `registry.py` (+ tests) →
`builtin.py` file tools (+ jail tests) → `bash` (+ timeout/exit/truncation tests) →
`__init__.py` wiring (+ import-surface test). Tests live in `tests/tools/`, using `tmp_path`
as the jail root throughout; the bash timeout test monkeypatches `BASH_TIMEOUT_S` to keep the
suite fast.

Relative effort: 2/5. Risk: low — stdlib-only, no consumers, behavior-neutral by
construction.
