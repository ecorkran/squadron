---
docType: tasks
slice: tool-registry-descriptor-protocol-and-core-tool-implementations
project: squadron
lldReference: project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md
parent: project-documents/user/architecture/260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: []
projectState: Phase 4 design complete; review CONCERNS findings F003/F004/F005 addressed in b05fadc. `src/squadron/tools/` does not exist yet. No consumer of tools exists anywhere in the tree.
dateCreated: 20260827
dateUpdated: 20260827
status: complete
---

# Tasks: Tool Registry, Descriptor Protocol, and Core Tool Implementations

## Context Summary

- Slice **261** is the foundation slice of initiative 260 (Non-SDK Agent Tool Use). It creates a
  new package `src/squadron/tools/` containing pure data types, a process-level registry, and
  three tool implementations (`read_file`, `write_file`, `bash`).
- **Behavior-neutral by construction.** Nothing outside the new package changes. No agent, no
  provider, no pipeline, no executor, no review code is touched. After this slice, tools exist
  and are fully tested but nothing consumes them — that is 262's job.
- Stdlib only. No new dependencies in `pyproject.toml`.
- The names registered here (`read_file`, `write_file`, `bash`) are the start of the **canonical
  squadron tool vocabulary**. Slice 265 adds `list_files` and `grep` through this same registry.
- **Commit per task group, not once at the end** (review F003). Task 0 creates the branch; groups
  1–7 each end with a commit step; group 8 commits the close-out documentation. Every commit
  leaves `pytest tests/tools/ -q` passing.

### Verified anchors (traced 20260827 on `b05fadc`)

| Anchor | Fact |
|---|---|
| Package location | `src/squadron/tools/` **does not exist**. `src/squadron/mcp/` exists but contains only an empty `__init__.py`. |
| Registry pattern to mirror | [registry.py](src/squadron/providers/registry.py) — module-level `_REGISTRY: dict[...]`, free functions, `KeyError` message lists available names |
| Async subprocess idiom | [frontmatter_gate.py:46](src/squadron/events/builtin/frontmatter_gate.py#L46) — `await asyncio.create_subprocess_exec(..., cwd=..., stdout=PIPE, stderr=PIPE)` then `await proc.communicate()`, decode with `errors="replace"` |
| `asyncio.to_thread` idiom | [http.py:44](src/squadron/client/http.py#L44) and [emit.py:137](src/squadron/pipeline/emit.py#L137) |
| pytest config | `pyproject.toml:81` — `asyncio_mode = "auto"`. **`async def` tests need no decorator.** |
| Ruff lint set | `pyproject.toml` — `select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`. `BLE` is on: a bare `except Exception` requires `# noqa: BLE001` (established idiom at [emit.py:157](src/squadron/pipeline/emit.py#L157), [sdk_session.py:108](src/squadron/pipeline/sdk_session.py#L108)) |
| Pyright | `typeCheckingMode = "strict"`, `include = ["src"]`. New source under `src/squadron/tools/` **must pass strict** — fully annotated, no implicit `Any`. |
| Python floor | `requires-python = ">=3.12"` — `Path.is_relative_to` and `datetime.UTC` are available |
| Line length | 104 |

### Constraints the design implies but does not spell out

1. **`# noqa: BLE001` is required** on the catch-all handler in the shared executor wrapper.
   Without it, `ruff check` fails. The design justifies the handler; ruff still needs the marker.
2. **Pyright strict applies.** `parameters: dict[str, object]` and `args: dict[str, object]` must
   be narrowed before use (e.g. `isinstance(raw, str)`), not indexed and passed blind.
3. **Logging assertions need a level.** `caplog` defaults to WARNING propagation; tests asserting
   INFO records must set `caplog.set_level(logging.INFO)`.

---

## Task 0: Branch

- [x] **0.1 Create the slice branch** — Effort: 1/5
  - [x] Confirm the integration target: `cf config get git.integration_branch`. An empty value
        means the target is `main`.
  - [x] From the target, create and switch to
        `261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations`:
        `git checkout -b 261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations <target>`.
  - [x] If the branch already exists, `git checkout` it instead. Never start from another unit's
        branch.
  - [x] Success: `git branch --show-current` prints the slice branch and `git status` is clean.

### Commit cadence for this slice

Every task group below ends with a commit step. Commit from the project root, on the slice
branch, and run `.venv/bin/ruff format .` immediately before each one. Each commit must leave the
tree in a state where `.venv/bin/pytest tests/tools/ -q` passes — the groups are ordered so this
is always achievable. Do not merge, push, or delete the branch at any point without explicit
instruction from the Project Manager.

---

## Task 1: Package skeleton and pure types

- [x] **1.1 Create the package and limits module** — Effort: 1/5
  - [x] Create directory `src/squadron/tools/`.
  - [x] Create `src/squadron/tools/limits.py` with exactly three module-level constants and a
        docstring stating this is the single home for tool limits:
        `MAX_READ_BYTES = 256_000`, `MAX_OUTPUT_BYTES = 64_000`, `BASH_TIMEOUT_S = 120.0`.
  - [x] Do not add any other value to this module. Do not add configuration plumbing —
        slice 266 owns the configuration surface.
  - [x] Success: `python -c "from squadron.tools import limits; print(limits.MAX_READ_BYTES)"`
        prints `256000`.

- [x] **1.2 Create `errors.py`** — Effort: 1/5
  - [x] Define `ToolNotRegisteredError(Exception)` with a docstring stating it signals a *caller
        configuration* error (an unknown name passed to `materialize`), not a model error.
  - [x] No other exception types. Executors return `ToolResult(is_error=True)`; they do not raise
        to the caller.
  - [x] Success: importable; `issubclass(ToolNotRegisteredError, Exception)` is true.

- [x] **1.3 Create `models.py` with the descriptor and result types** — Effort: 2/5
  - [x] Define the two type aliases first, in this order (the factory alias references the
        executor alias):
        - `ToolExecutor = Callable[[dict[str, object]], Awaitable[ToolResult]]`
        - `ToolFactory = Callable[[Path], ToolExecutor]`
  - [x] Define `@dataclass(frozen=True) class ToolResult` with fields `content: str` and
        `is_error: bool = False`.
  - [x] Define `@dataclass(frozen=True) class ToolDescriptor` with fields `name: str`,
        `description: str`, `parameters: dict[str, object]`, `factory: ToolFactory`.
  - [x] Docstring on `parameters` states it is a JSON Schema object matching OpenAI's
        `tools[].function.parameters` shape.
  - [x] Docstring on `factory` states it receives an **already-resolved** `cwd` and returns a
        closure-bound executor. `cwd` never appears in `parameters` — the model cannot supply it.
  - [x] Do **not** define a `Protocol`. Design decision D2: one shape, no polymorphism, a Protocol
        with a single implementer is unjustified complexity.
  - [x] Use `from __future__ import annotations` and put `Callable`/`Awaitable` imports under
        `collections.abc` (matching the rest of the codebase).
  - [x] Success: `ruff check src/squadron/tools/` and `pyright` both clean for these files;
        `ToolResult("x").is_error is False`; the dataclass is frozen (assignment raises).

- [x] **1.4 Test the pure types** — Effort: 1/5
  - [x] Create `tests/tools/__init__.py` and `tests/tools/test_models.py`.
  - [x] Assert `ToolResult` defaults `is_error` to `False` and is frozen
        (`pytest.raises(dataclasses.FrozenInstanceError)` on attribute assignment).
  - [x] Assert `ToolDescriptor` is frozen and stores all four fields verbatim.
  - [x] Assert a descriptor's `factory` invoked with a `Path` returns a callable
        (use a trivial inline factory; no real tool needed here).
  - [x] Success: `pytest tests/tools/test_models.py -q` passes.

- [x] **1.5 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit:
        `chore: add squadron.tools package skeleton and pure types`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 2: Registry

- [x] **2.1 Implement `registry.py`** — Effort: 2/5
  - [x] Module-level `_REGISTRY: dict[str, ToolDescriptor] = {}`. Free functions, not a class —
        mirroring [providers/registry.py](src/squadron/providers/registry.py).
  - [x] `register(descriptor: ToolDescriptor) -> None` — stores under `descriptor.name`. If the
        name is already present, **raise `ValueError`** naming the colliding tool. This is a
        deliberate difference from the provider registry (which silently overwrites): a tool-name
        collision means two definitions of a security-relevant surface, so it fails fast.
  - [x] `lookup(name: str) -> ToolDescriptor | None` — returns `None` for unknown names. Does not
        raise.
  - [x] `list_tools() -> list[str]` — returns registered names.
  - [x] `materialize(names: Sequence[str], cwd: str | Path) -> dict[str, ToolExecutor]`:
        - Resolve `cwd` **once**: `resolved = Path(cwd).resolve()`.
        - For each name, `lookup` it; if `None`, raise `ToolNotRegisteredError` naming the unknown
          tool **and listing the registered names** (message style mirrors `get_provider`'s
          `KeyError`).
        - Call each descriptor's `factory(resolved)` and collect `{name: executor}`.
  - [x] Do not add an `ensure_tools_loaded()` indirection (design D5) — there is one built-in
        module, and registration happens at package import.
  - [x] Success: `ruff check` and `pyright` clean; functions annotated and documented.

- [x] **2.2 Test the registry** — Effort: 2/5
  - [x] Create `tests/tools/test_registry.py`.
  - [x] **Isolate registry state.** The registry is module-level and the built-ins register at
        import. Add a fixture that snapshots `registry._REGISTRY` (`dict(...)`) before each test
        and restores it after, so registering test doubles cannot leak between tests or corrupt
        the built-in set for other test modules.
  - [x] Assert `register` then `lookup` returns the same descriptor object.
  - [x] Assert `register` with an already-registered name raises `ValueError` and the message
        names the tool.
  - [x] Assert `lookup("nope")` returns `None` (does not raise).
  - [x] Assert `list_tools()` includes a freshly registered name.
  - [x] Assert `materialize` returns a dict keyed by the requested names, whose values are
        callables.
  - [x] Assert `materialize` with an unknown name raises `ToolNotRegisteredError`, and the message
        contains both the unknown name and at least one registered name.
  - [x] Assert `cwd` is resolved once and passed resolved: register a probe descriptor whose
        factory records the `Path` it received; call `materialize` with a relative path or a path
        containing `..`, and assert the recorded path equals `Path(that).resolve()`.
  - [x] Success: `pytest tests/tools/test_registry.py -q` passes.

- [x] **2.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit: `feat: add tool registry`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 3: Shared executor plumbing

- [x] **3.1 Implement the path jail helper** — Effort: 2/5
  - [x] In `builtin.py`, add a module-private helper that takes the resolved `cwd` and the
        model-supplied `path` string and returns the resolved target `Path`, or signals rejection.
  - [x] Rule: `candidate = (cwd / path).resolve(strict=False)`; accept only if
        `candidate.is_relative_to(cwd)`. Because `Path.__truediv__` with an absolute right-hand
        operand yields the absolute path, this expression covers relative inputs, absolute inputs,
        and `..` traversal with one check. `resolve()` resolves symlinks first, so a symlink whose
        target lies outside the jail is rejected.
  - [x] The rejection path must produce a `ToolResult(is_error=True)` whose content names the
        rejected path, and must log at **WARNING** with the tool name and the rejected path
        (CWD is the trust boundary; an escape attempt must be visible without `-vv`).
  - [x] Do not use string prefix comparison (`str(candidate).startswith(str(cwd))`) — it is
        wrong across path-component boundaries.
  - [x] Success: helper is annotated, passes pyright strict, and is referenced by both file tools.

- [x] **3.1a Test the jail helper directly** — Effort: 2/5
  - [x] Create `tests/tools/test_jail.py` testing the helper in isolation, not through a tool.
        Tasks 4.2/5.2 exercise it end-to-end; this task pins the rule itself, so a jail regression
        names the jail rather than surfacing as two confusing tool-test failures.
  - [x] With `tmp_path` as the resolved jail root, assert **accepted**: a plain relative path; a
        nested relative path; an absolute path inside the root; a path containing `..` that stays
        inside the root (e.g. `sub/../file.txt`).
  - [x] Assert **rejected**: `../escape`; a deep `../../..` traversal; an absolute path outside the
        root; a symlink inside the root whose target is outside it; a path whose *parent* resolves
        outside the root (this is the case `write_file` relies on before creating directories).
  - [x] Assert the root itself and the sibling-prefix case behave correctly: a sibling directory
        whose name shares a string prefix with the root (e.g. root `…/jail`, target `…/jail_evil`)
        is **rejected**. This is the case string-prefix comparison gets wrong and
        `is_relative_to` gets right — it is the direct regression test for the "do not use
        `startswith`" instruction in 3.1.
  - [x] Success: `pytest tests/tools/test_jail.py -q` passes.

- [x] **3.2 Implement the shared executor wrapper and logging contract** — Effort: 2/5
  - [x] Add a module-private wrapper used by every executor that:
        - catches the tool-specific expected exceptions listed in the design
          (`FileNotFoundError`, `PermissionError`, `IsADirectoryError`, `NotADirectoryError`,
          `UnicodeDecodeError`, `TimeoutError`) and converts each to a specific-message
          `ToolResult(is_error=True)`;
        - ends with `except Exception as exc:  # noqa: BLE001` that calls `logger.exception(...)`
          at ERROR and returns `ToolResult(is_error=True, ...)`. This is a process-boundary
          handler: from 262 onward the caller is a model loop, and an unexpected tool bug must
          become an observable error result rather than a crashed review.
  - [x] Logging levels (design §Observability, review F003) — this is a **contract**, not a
        suggestion:
        - **WARNING** — jail violations (tool name + rejected path) and bash timeouts
          (command + limit).
        - **INFO** — every other `is_error=True` result (missing file, permission denied,
          non-zero exit, truncation), with tool name and reason.
        - **ERROR** — only the unexpected-exception catch-all, via `logger.exception`.
  - [x] Do not elevate the INFO cases to WARNING. They are routine model-probing outcomes the
        model itself reacts to; elevating them would train operators to ignore warnings.
  - [x] Module logger obtained the same way as elsewhere in the codebase
        (`logging.getLogger(__name__)`).
  - [x] Success: `ruff check src/squadron/tools/` clean (the `noqa` marker is present and
        correctly scoped). The wrapper has no consumer yet — Tasks 4.1, 5.1, and 6.1 each route
        their executor through it, and Task 8.3's full gate is where "used by all three" is
        actually confirmed.

- [x] **3.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit:
        `feat: add tool path jail and shared executor wrapper`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 4: `read_file`

- [x] **4.1 Implement the `read_file` descriptor and executor** — Effort: 2/5
  - [x] Parameters JSON Schema: object with one required property `path` (string), described for
        the model as relative to the working directory. `cwd` must **not** appear.
  - [x] Factory binds the resolved `cwd`; executor runs the jail check, then performs the read.
  - [x] Read text as UTF-8 with `errors="replace"`. Wrap the blocking filesystem work in
        `asyncio.to_thread` — files may be large and must never block the event loop.
  - [x] Truncate content beyond `limits.MAX_READ_BYTES`, appending a **visible trailing marker
        line** stating that truncation occurred and the full size. A truncated read must never be
        silent — the model has to know it did not see everything.
  - [x] Error results with specific messages for: path escape (WARNING), missing file, path is a
        directory, permission denied (INFO each).
  - [x] Register the descriptor at module scope via `register(...)`.
  - [x] Success: descriptor present in `list_tools()`; executor is `async`.

- [x] **4.2 Test `read_file`** — Effort: 2/5
  - [x] Create `tests/tools/test_read_file.py`. Use `tmp_path` as the jail root throughout.
  - [x] Happy path: write a file under `tmp_path`, read it via the materialized executor, assert
        content matches and `is_error is False`.
  - [x] Absolute path *inside* the jail succeeds (proving the jail check does not reject all
        absolute paths).
  - [x] Jail rejections, each asserting `is_error is True` **and** that the message names the
        rejected path:
        - `../escape`-style relative traversal;
        - an absolute path outside `tmp_path` (create a second `tmp_path`-sibling dir or use a
          separately created temp dir — do not read a real system file);
        - a symlink inside the jail whose target is outside it.
  - [x] Truncation: monkeypatch `limits.MAX_READ_BYTES` to a small value (or write a file larger
        than the constant — prefer the monkeypatch to keep the suite fast), assert the returned
        content is shortened and contains the truncation marker.
  - [x] Missing file and directory-as-path each return `is_error=True` with distinct messages.
  - [x] `caplog` assertions: the jail rejection logs at **WARNING**; the missing-file case logs at
        **INFO** (`caplog.set_level(logging.INFO)` is required for the INFO assertion).
  - [x] Success: `pytest tests/tools/test_read_file.py -q` passes.

- [x] **4.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit: `feat: add read_file tool`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 5: `write_file`

- [x] **5.1 Implement the `write_file` descriptor and executor** — Effort: 2/5
  - [x] Parameters JSON Schema: object with required `path` (string) and `content` (string).
  - [x] Same jail check as `read_file`, via the shared helper from Task 3.1.
  - [x] Create parent directories (`mkdir(parents=True, exist_ok=True)`). The **parent directory
        path is jail-checked before creation** — never create directories outside the jail.
  - [x] Existing files are overwritten. The result content states **created vs. overwritten** and
        the byte count, so the model and DEBUG logs can see exactly what happened. Determine
        created-vs-overwritten by checking existence *before* the write.
  - [x] Blocking filesystem work wrapped in `asyncio.to_thread`.
  - [x] Error results: path escape (WARNING), permission denied, path is an existing directory
        (INFO each).
  - [x] Register the descriptor at module scope.
  - [x] Success: descriptor present in `list_tools()`; executor is `async`.

- [x] **5.2 Test `write_file`** — Effort: 2/5
  - [x] Create `tests/tools/test_write_file.py`, `tmp_path` as jail root.
  - [x] Create-new: write to `notes/a.txt` (nested, parent does not exist), assert the file exists
        with the expected content, that the parent dir was created, and that the result content
        says created and reports the correct byte count.
  - [x] Overwrite: write the same path again with different content; assert the result says
        overwritten and the byte count matches the new content.
  - [x] Jail rejections mirroring Task 4.2 (relative traversal, absolute-outside, symlink-outside),
        each `is_error=True` with the path named. **Also assert no file was created outside the
        jail** for at least one case — the rejection must be effective, not merely reported.
  - [x] Path-is-an-existing-directory returns `is_error=True`.
  - [x] `caplog`: jail rejection at **WARNING**; a non-jail error case at **INFO**.
  - [x] Success: `pytest tests/tools/test_write_file.py -q` passes.

- [x] **5.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit: `feat: add write_file tool`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 6: `bash`

- [x] **6.1 Implement the `bash` descriptor and executor** — Effort: 3/5
  - [x] Parameters JSON Schema: object with one required property `command` (string).
  - [x] Spawn with `asyncio.create_subprocess_shell(command, cwd=cwd, stdout=PIPE, stderr=PIPE,
        start_new_session=True)`. `start_new_session=True` is required so the timeout path can
        kill the whole process group.
  - [x] Await `proc.communicate()` inside `asyncio.wait_for(..., timeout=limits.BASH_TIMEOUT_S)`.
  - [x] **Timeout path:** on `TimeoutError`, kill the process group via
        `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)`, then await the process so no zombie is
        left, and return `is_error=True` naming the timeout and the limit. Log at **WARNING** with
        the command and the limit. This answers the failure-mode question "what if it hangs?" —
        a hung command must not hang 262's loop.
    - Guard the `killpg` call for the case where the process already exited between the timeout
      firing and the kill (`ProcessLookupError`) — swallow that one specifically, with a comment.
  - [x] Decode stdout and stderr with `errors="replace"`. Result content labels each stream, and
        truncates each to `limits.MAX_OUTPUT_BYTES` with a visible marker.
  - [x] Non-zero exit → `is_error=True` with the exit code **and the captured output** (the model
        needs the output to react). Log at **INFO**.
  - [x] CWD is the only boundary at this stage. Do **not** add network denial, env scrubbing, or
        process isolation — arch-documented future work, explicitly out of scope.
  - [x] Register the descriptor at module scope.
  - [x] Success: descriptor present in `list_tools()`; executor is `async`.

- [x] **6.2 Test `bash`** — Effort: 3/5
  - [x] Create `tests/tools/test_bash.py`, `tmp_path` as the working directory.
  - [x] Happy path: run a command that writes to stdout; assert the output appears in the result,
        labeled, with `is_error is False`.
  - [x] Stderr capture: run a command writing to stderr; assert the stderr content appears,
        labeled.
  - [x] CWD anchoring: create a file in `tmp_path`, run `ls` (or equivalent), assert the filename
        appears — proving the subprocess runs in the jail root and not the repo root.
  - [x] Non-zero exit: run a command exiting non-zero; assert `is_error is True`, the exit code is
        in the message, and captured output is still present.
  - [x] Truncation: monkeypatch `limits.MAX_OUTPUT_BYTES` to a small value, produce more output
        than that, assert the result is shortened and contains the marker.
  - [x] **Timeout: monkeypatch `limits.BASH_TIMEOUT_S` to a small value** (well under a second is
        fine) and run a sleeping command. Assert `is_error is True`, the message names the
        timeout, and the test completes quickly. Ensure the executor reads the constant at call
        time (module attribute access), not captured at import — otherwise the monkeypatch will
        not take effect and this test will hang. If import-time capture is how the code reads,
        change the code to read the module attribute.
  - [x] `caplog`: the timeout logs at **WARNING**; the non-zero-exit case logs at **INFO**.
  - [x] Success: `pytest tests/tools/test_bash.py -q` passes and the whole file runs in a few
        seconds, not minutes.

- [x] **6.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit: `feat: add bash tool`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 7: Package wiring and import surface

- [x] **7.1 Write `tools/__init__.py`** — Effort: 1/5
  - [x] Import `builtin` so registration happens at package import (design D5), marking it
        `# noqa: F401` with a comment stating the import exists for its registration side effect
        (matching [pipeline/steps/__init__.py](src/squadron/pipeline/steps/__init__.py) idiom;
        add `# pyright: ignore[reportUnusedImport]` if pyright strict flags it).
  - [x] Re-export the public API: `ToolDescriptor`, `ToolResult`, `ToolExecutor`, `ToolFactory`,
        `ToolNotRegisteredError`, `register`, `lookup`, `materialize`, `list_tools`.
  - [x] Define `__all__` listing exactly those names.
  - [x] Importing the package must have **no side effects other than registration** — no logging
        configuration, no filesystem access, no environment reads.
  - [x] Success: `python -c "from squadron import tools; print(tools.list_tools())"` prints
        `['read_file', 'write_file', 'bash']`.

- [x] **7.2 Test the import surface** — Effort: 1/5
  - [x] Create `tests/tools/test_package.py`.
  - [x] Assert `set(tools.list_tools()) == {"read_file", "write_file", "bash"}` — exactly these
        three, no more.
  - [x] Assert every name in `__all__` is accessible on the package.
  - [x] Assert `materialize(tools.list_tools(), tmp_path)` returns three callables.
  - [x] Success: `pytest tests/tools/test_package.py -q` passes.

- [x] **7.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`, then commit: `feat: wire squadron.tools public API`.
  - [x] Success: clean tree; `pytest tests/tools/ -q` passes.

---

## Task 8: Verification and close-out

- [x] **8.1 Confirm limits are not scattered** — Effort: 1/5
  - [x] Run `grep -rn "256_000\|256000\|64_000\|64000\|120\.0" src/squadron/tools/` and confirm
        every hit is inside `limits.py`. Any literal elsewhere is a defect — reference the
        constant instead.
  - [x] Success: the only hits are in `limits.py`.

- [x] **8.2 Confirm nothing consumes tools yet** — Effort: 1/5
  - [x] Run `grep -rn "squadron.tools\|squadron import tools" src/` and confirm the only hits are
        inside `src/squadron/tools/` itself.
  - [x] Run `git status` and confirm no file outside `src/squadron/tools/` and `tests/tools/` is
        modified. If any other file changed, the slice's behavior-neutrality guarantee is broken —
        stop and report to the Project Manager.
  - [x] Success: both checks clean.

- [x] **8.3 Run the full gate** — Effort: 1/5
  - [x] `.venv/bin/ruff format .` then `.venv/bin/ruff check .` — both clean.
  - [x] `.venv/bin/pyright` — no new errors under `src/squadron/tools/` (strict mode applies to
        `src`).
  - [x] `.venv/bin/pytest tests/tools/ -q` — new suite passes.
  - [x] `.venv/bin/pytest -q` — **full suite**, no regression anywhere else.
  - [x] Success: all four clean. Report actual output; do not summarize a failure as a pass.

- [x] **8.4 Manual walkthrough** — Effort: 1/5
  - [x] Registry demo:
        `python -c "from squadron import tools; print(tools.list_tools())"` →
        `['read_file', 'write_file', 'bash']`.
  - [x] Jail demo — run the scratch-tree script from the design document's Verification
        Walkthrough step 4. Expected: write reports created and 5 bytes; read returns `hello`;
        the escape attempt returns an error result naming the path; `bash` lists `a.txt`.
  - [x] Record the actual output in the DEVLOG entry (Task 8.6). If any step deviates from the
        expected result, fix the code — do not adjust the expectation.

- [x] **8.5 Refine the design's Verification Walkthrough** — Effort: 1/5
  - [x] The design marks that section "Draft — refined at Phase 6 completion." Replace the draft
        with the commands actually run in 8.3 and 8.4 and their real output.
  - [x] Set the design document's `status` to `complete` and update `dateUpdated`.
  - [x] Check off slice 261 in
        `project-documents/user/architecture/260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
        (Feature Slices entry 1). Leave the initiative itself `not_started` — 262–266 remain.

- [x] **8.6 DEVLOG and commit** — Effort: 1/5
  - [x] Append a DEVLOG entry to `DEVLOG.md` at the repo root (**not**
        `project-documents/DEVLOG.md`, which is a retired stub) covering: the new package, the
        three registered tools, the jail rule, the logging contract, and the fact that nothing
        consumes tools yet.
  - [x] Set this task file's `status` to `complete` and update `dateUpdated`.
  - [x] `.venv/bin/ruff format .`, then commit the documentation updates from 8.5 and 8.6:
        `docs: close out slice 261 — tool registry and core tools`.
  - [x] Do **not** merge, push, or delete the branch without explicit instruction from the
        Project Manager. The slice branch stays open until the PM says otherwise.
  - [x] Success: clean tree; the frontmatter gate passes; `git log --oneline <target>..HEAD` shows
        the per-task commits from groups 1–7 plus this close-out commit.

---

## Success Criteria (from the design, restated as a checklist)

- [x] 1. `ToolDescriptor` / `ToolResult` / `ToolExecutor` exist as specified (Task 1.3).
- [x] 2. Registry: duplicate `register` → `ValueError`; `lookup` → `None` for unknown;
      `list_tools` returns names; `materialize` returns executors and raises
      `ToolNotRegisteredError` naming offender and available set (Task 2).
- [x] 3. `from squadron import tools` yields exactly `read_file`, `write_file`, `bash`, with no
      other import side effects (Task 7).
- [x] 4. Path jail rejects `../escape`, absolute-outside, and outward symlinks for **both** file
      tools, naming the rejected path; inside-jail absolute and relative paths work
      (Task 3.1a directly, Tasks 4.2 and 5.2 end-to-end).
- [x] 5. `read_file` happy path, visible truncation, and specific missing-file / directory errors
      (Task 4.2).
- [x] 6. `write_file` creates nested dirs, overwrites, and reports created/overwritten + bytes
      (Task 5.2).
- [x] 7. `bash` labels stdout/stderr, non-zero exit → error with code, timeout kills the process
      group and reports, oversized output truncated visibly (Task 6.2).
- [x] 8. All limits are named constants in `limits.py`; no limit literal elsewhere (Task 8.1).
- [x] 9. Every failure mode has at least one test, including `caplog` assertions that jail
      violations and bash timeouts log at WARNING and other error results log at INFO
      (Tasks 4.2, 5.2, 6.2).
- [x] 10. No change to `providers/`, `pipeline/`, `review/`, or `core/models.py`; full existing
      suite passes (Tasks 8.2, 8.3).

---

## Out of Scope (do not implement here)

- Any agent, provider, executor, or pipeline change — that is 262/263.
- `list_files` / `grep` — slice 265 registers those through this same registry.
- Canonical→Claude tool-name translation for the SDK path — slice 265.
- Bash sandboxing beyond CWD + timeout (network deny, env scrubbing, process isolation) —
  arch-documented future work.
- MCP-bridged tools — slice 264.
- Making limits configurable — slice 266 owns the configuration surface.
