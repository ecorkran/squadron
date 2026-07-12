---
docType: slice-design
slice: optional-dependency-split-serve-and-codex-extras
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260514
dateUpdated: 20260712
status: deferred
reviewFindings: [F002-resolved, F003-resolved]
---

# Slice Design: Optional Dependency Split — `serve` and `codex` Extras

## Overview

Move `fastapi` and `uvicorn` out of mandatory dependencies into a `[serve]` optional extra; add a `[codex]` note extra documenting the manual GitHub install. Both commands get fast-fail guards with actionable error messages when their extras are absent. No behavior change for users who have the full install.

## Value

- Users who only run `sq run` / `sq review` / `sq doctor` don't pull in a web framework they'll never use.
- `pip install squadron-ai` stays lightweight; `pip install squadron-ai[serve]` opts in to the daemon.
- Codex install errors go from a raw `ImportError` traceback to a clear install instruction at the right moment.

## Technical Scope

### 1 — `pyproject.toml` restructure

**Remove** `fastapi>=0.115.0` and `uvicorn[standard]>=0.30.0` from `[project.dependencies]`.

**Add** a `[serve]` entry to `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
serve = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
]
codex = []   # manual install — see note below
dev = [...]
```

The `codex` extra is intentionally empty. PyPI rejects direct URL references, so we cannot declare the GitHub dependency. The extra exists to give users a meaningful `pip install squadron-ai[codex]` target that documents intent and can be populated if the package ever reaches PyPI. A comment block in `pyproject.toml` carries the actual install command.

### 2 — `serve` runtime guard

**File:** `src/squadron/cli/commands/serve.py`

At the top of `_start_daemon()` (called only when neither `--stop` nor `--status` is passed), add an import check before touching any `squadron.server.*` module:

```python
def _start_daemon(config: DaemonConfig) -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        rprint(
            "[red]Error:[/red] 'sq serve' requires the [serve] extra.\n"
            "  pip install 'squadron-ai[serve]'"
        )
        raise typer.Exit(code=1)
    ...
```

The guard sits inside `_start_daemon`, not at module import time, so `serve.py` itself remains importable. `--stop` and `--status` never call `_start_daemon` and therefore work without the extra (they only read the PID file).

The import of `squadron.server.daemon` (which pulls in `fastapi`/`uvicorn` at module level) currently happens at the top of `serve.py`. That top-level import must be deferred: move it inside `_start_daemon` after the guard.

**Current top-level imports in `serve.py` to defer:**
```python
from squadron.server.daemon import (
    DaemonConfig,
    is_daemon_running,
    read_pid_file,
    start_server,
)
from squadron.server.engine import SquadronEngine
```

`DaemonConfig`, `is_daemon_running`, and `read_pid_file` are also used by `_show_status` and `_stop_daemon`. Those three have no fastapi/uvicorn dependencies in their own bodies — but `daemon.py` imports `uvicorn` and `squadron.server.app` (fastapi) unconditionally at module level. Any top-level `from squadron.server.daemon import ...` in `serve.py` therefore pulls in fastapi/uvicorn regardless of which names are imported. The extraction is required scope for this slice.

**Extract `src/squadron/server/pid.py`** — new module containing only:
- `DaemonConfig` dataclass
- `read_pid_file()`
- `write_pid_file()`
- `remove_pid_file()`
- `is_daemon_running()`

These functions use only stdlib (`os`, `errno`, `pathlib`, `dataclasses`). `daemon.py` imports them from `pid.py` (no circular dependency — `daemon.py` adds `start_server` which depends on `uvicorn`/`app`). `serve.py` imports `DaemonConfig`, `is_daemon_running`, `read_pid_file` from `pid.py` at module level; `start_server` and `SquadronEngine` are deferred into `_start_daemon` after the guard.

### 3 — `codex` runtime guard

**File:** `src/squadron/providers/codex/provider.py`

`validate_credentials()` already handles `ImportError` from `__import__("codex_app_server")` by returning `False`. That's correct for capability-checking.

The gap is in `CodexAgent._run_prompt()` (`agent.py:91`), which already has an `ImportError` guard that raises `ProviderError` with an install message. That message is correct and complete — no change needed there.

The remaining gap: `CodexProvider.create_agent()` unconditionally imports `CodexAgent` at module level (`from squadron.providers.codex.agent import CodexAgent`). When `codex_app_server` is absent, `create_agent` succeeds (because `CodexAgent.__init__` doesn't import the SDK), but the first `handle_message` call explodes with `ProviderError`. This is acceptable — the error message in `_run_prompt` is already clear. No additional guard is needed in `create_agent`.

**What this slice does add** for codex: a guard in `CodexProvider.create_agent()` that catches the absent-binary case early, before the agent is even returned:

```python
async def create_agent(self, config: AgentConfig) -> CodexAgent:
    strategy = OAuthFileStrategy()
    if not strategy.is_valid():
        raise ProviderAuthError(f"No Codex credentials found. {strategy.setup_hint}.")

    from squadron.providers.codex.agent import resolve_codex_binary
    if resolve_codex_binary() is None:
        raise ProviderError(
            "Codex CLI binary not found on PATH.\n"
            "  npm i -g @openai/codex"
        )

    _log.debug("Creating Codex agent %r (model=%s)", config.name, config.model)
    return CodexAgent(name=config.name, config=config)
```

This moves the binary check from `validate_credentials` (which is a passive probe) into `create_agent` (which commits to using the provider), giving a clear error before any work starts.

## Data Flow / Component Interactions

```
pip install squadron-ai          → no fastapi, no uvicorn
pip install squadron-ai[serve]   → + fastapi + uvicorn

sq doctor / sq run / sq review   → never touches server.*  → works without [serve]
sq serve --status / --stop       → reads PID file only     → works without [serve]
sq serve (start)                 → calls _start_daemon     → guard fires if [serve] absent
```

```
codex provider create_agent → binary check → ProviderError if codex binary not on PATH
                            → CodexAgent instance returned
codex agent handle_message  → _run_prompt → SDK import guard → ProviderError if SDK absent
```

## Migration Plan

### Consumer updates

No external consumers to update. The `[serve]` extra is new; existing installs that already have `fastapi`/`uvicorn` in their environment are unaffected. CI / dev installs should add `[serve]` to their install command or use `[dev,serve]`.

### Verification steps

1. Fresh venv, `pip install -e .` (no extras) — `sq doctor`, `sq run`, `sq review` all work.
2. `sq serve` without extras → clear error message, exit code 1.
3. `sq serve --status` without extras → no error (PID check only).
4. `pip install -e .[serve]` → `sq serve` starts normally.
5. `sq serve --stop` without extras, daemon not running → `"Daemon is not running."` error, no ImportError.

## Cross-Slice Dependencies

- No upstream dependencies.
- Slice 908 (`sq setup`) should document `pip install squadron-ai[serve]` as the install step for users who want the daemon. The quickstart (slice 906) should be reviewed after this slice to ensure install instructions reflect the new extras.

## Success Criteria

1. `fastapi` and `uvicorn` are absent from `[project.dependencies]` in `pyproject.toml`.
2. A `[serve]` extra in `[project.optional-dependencies]` lists `fastapi>=0.115.0` and `uvicorn[standard]>=0.30.0`.
3. A `[codex]` extra (empty, with comment) exists in `[project.optional-dependencies]`.
4. `pip install squadron-ai` in a clean venv does not install `fastapi` or `uvicorn`.
5. `sq serve` (start mode) without `[serve]` installed prints an actionable error and exits 1.
6. `sq serve --status` and `sq serve --stop` without `[serve]` installed work correctly.
7. `sq doctor` / `sq run` / `sq review` work without `[serve]` installed.
8. `CodexProvider.create_agent()` raises `ProviderError` (not `ProviderAuthError`) with a `npm i -g @openai/codex` hint when the binary is absent.
9. All 1904 existing tests pass; pyright and ruff clean.
10. CI install command updated to include `[serve]` (and `[dev]`).

## Verification Walkthrough

```bash
# 1. Confirm current full-install baseline passes
uv pip install -e ".[dev,serve]"
pytest
sq doctor

# 2. Create a clean venv and install without extras
python -m venv /tmp/sq-test-venv
/tmp/sq-test-venv/bin/pip install -e .
/tmp/sq-test-venv/bin/pip show fastapi    # should show "not found"
/tmp/sq-test-venv/bin/pip show uvicorn    # should show "not found"

# 3. Core commands work without [serve]
/tmp/sq-test-venv/bin/sq doctor
/tmp/sq-test-venv/bin/sq --help

# 4. sq serve start is gated
/tmp/sq-test-venv/bin/sq serve
# Expected: "Error: 'sq serve' requires the [serve] extra."
# Expected: exit code 1

# 5. sq serve status/stop are NOT gated
/tmp/sq-test-venv/bin/sq serve --status
# Expected: "Daemon is not running." (no ImportError)

# 6. Install with [serve] and confirm daemon starts
/tmp/sq-test-venv/bin/pip install -e ".[serve]"
/tmp/sq-test-venv/bin/sq serve --status   # not running
/tmp/sq-test-venv/bin/sq serve &
sleep 1
/tmp/sq-test-venv/bin/sq serve --status   # running
/tmp/sq-test-venv/bin/sq serve --stop
```
