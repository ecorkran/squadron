---
docType: slice-design
slice: context-forge-integration-layer
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [cli-foundation]
interfaces: []
dateCreated: 20260324
dateUpdated: 20260324
status: not_started
---

# Slice Design: Context Forge Integration Layer

## Overview

Centralize all Context Forge CLI interactions behind a `ContextForgeClient` class in `src/squadron/integrations/context_forge.py`. Today, squadron calls `cf` via `subprocess.run()` directly in `review.py` with hardcoded command strings. When CF's command surface changes (as it just did — `cf slice list` → `cf list slices`), every callsite breaks.

This slice extracts a typed abstraction that:
- Encapsulates all CF CLI calls in one place
- Adapts to CF's current command surface
- Provides typed return values instead of raw JSON parsing at each callsite
- Makes future transport changes (MCP client, library import) a single-file swap

Scope is intentionally limited to the abstraction and migration. Command aliasing (`sq` surfacing CF commands) and transport backends beyond subprocess are deferred — they depend on what CF provides and how the relationship evolves.

---

## Technical Decisions

### 1. Client Class Design

A single `ContextForgeClient` class with methods mapping to the CF operations squadron actually uses. No speculative methods for CF commands squadron doesn't call.

**Current CF operations used by squadron** (found via grep):

| Operation | Current callsite | CF command (old) | CF command (new) |
|-----------|-----------------|------------------|------------------|
| List slices | `review.py:278` | `cf slice list --json` | `cf list slices --json` |
| List tasks | `review.py:298` | `cf tasks list --json` | `cf list tasks --json` |
| Get project | `review.py:308` | `cf get --json` | `cf get --json` (unchanged) |
| Set phase | `run-slice.md` | `cf set phase N` | `cf set phase N` (unchanged) |
| Set slice | `run-slice.md` | `cf set slice X` | `cf set slice X` (unchanged) |
| Build context | `run-slice.md` | `cf build` | `cf build` (unchanged) |
| Get prompt | `run-slice.md` | `cf prompt get X` | `cf prompt get X` (unchanged) |

The client exposes typed methods for the operations used in Python code. The markdown command files (`commands/sq/*.md`) reference CF commands by name — they'll be updated to use the new command names directly (they're instructions for Claude Code, not executable code).

```python
class ContextForgeClient:
    """Typed interface to Context Forge CLI operations."""

    def list_slices(self) -> list[SliceEntry]: ...
    def list_tasks(self) -> list[TaskEntry]: ...
    def get_project(self) -> ProjectInfo: ...
    def is_available(self) -> bool: ...
```

### 2. Return Types

Typed dataclasses for each CF response, replacing raw `dict` access scattered across `review.py`:

```python
@dataclass
class SliceEntry:
    index: int
    name: str
    design_file: str | None
    status: str

@dataclass
class TaskEntry:
    index: int
    files: list[str]

@dataclass
class ProjectInfo:
    arch_file: str
    slice_plan: str
    phase: str
    slice: str
```

Only fields squadron actually reads are included. CF may return more — we ignore what we don't use.

### 3. Subprocess Wrapper

The existing `_run_cf()` in `review.py` is a good starting point but is private to that module. The client class absorbs this pattern:

- `subprocess.run(["cf", *args])` with capture, timeout, and error handling
- `FileNotFoundError` → `ContextForgeNotAvailable` exception (new, replaces `typer.Exit`)
- `CalledProcessError` → `ContextForgeError` with stderr context
- JSON parsing of `--json` output with validation

Separating the exceptions from `typer.Exit` is important — the client shouldn't know about Typer. CLI code catches client exceptions and translates to `typer.Exit`.

### 4. Availability Check

`ContextForgeClient.is_available()` — checks if `cf` is on PATH and responsive (runs `cf --version` or similar). Used by:
- CLI code to show helpful errors ("Install Context Forge: ...")
- Future: guard for optional CF integration (don't crash if CF isn't installed)

### 5. Migration Plan

**Source:** `_run_cf()` and `_resolve_slice_number()` in `src/squadron/cli/commands/review.py`

**Destination:** `src/squadron/integrations/context_forge.py`

**Consumer updates:**
- `review.py` — replace `_run_cf()` calls and inline JSON parsing with `ContextForgeClient` method calls
- `commands/sq/run-slice.md` — update CF command names to new surface (`cf list slices`, etc.)
- `commands/sq/review-slice.md` — update command references
- `commands/sq/review-tasks.md` — update command references
- `commands/sq/review-code.md` — update command references

**Steps:**
1. Create `src/squadron/integrations/__init__.py` and `context_forge.py`
2. Define dataclasses and `ContextForgeClient`
3. Move `_run_cf()` logic into client, adapt to new CF commands
4. Replace `_resolve_slice_number()` in `review.py` to use client
5. Remove `_run_cf()` from `review.py`
6. Update markdown command files with new CF command names
7. Tests for client methods (mocked subprocess)

### 6. What This Does NOT Include

- **MCP client transport** — deferred until we determine the right integration pattern with CF
- **Library import transport** — requires CF to expose a stable Python API
- **Command aliasing** (`sq list slices` → CF) — deferred pending design philosophy discussion
- **New CF operations** — only wrapping what squadron already uses
- **CF daemon/API integration** — depends on CF providing this

---

## Data Flow

### Current (scattered)

```
review.py → subprocess.run(["cf", "slice", "list", "--json"]) → raw JSON → inline dict parsing → SliceInfo TypedDict
review.py → subprocess.run(["cf", "tasks", "list", "--json"]) → raw JSON → inline dict parsing → task_files list
review.py → subprocess.run(["cf", "get", "--json"]) → raw JSON → inline dict parsing → arch_file string
```

### After (centralized)

```
review.py → ContextForgeClient().list_slices() → list[SliceEntry]
review.py → ContextForgeClient().list_tasks() → list[TaskEntry]
review.py → ContextForgeClient().get_project() → ProjectInfo

ContextForgeClient internally:
  → subprocess.run(["cf", "list", "slices", "--json"]) → JSON → SliceEntry dataclass
```

---

## Component Interactions

**New files:**
- `src/squadron/integrations/__init__.py` — package init
- `src/squadron/integrations/context_forge.py` — `ContextForgeClient`, dataclasses, exceptions

**Modified files:**
- `src/squadron/cli/commands/review.py` — replace `_run_cf()`, `_resolve_slice_number()` with client calls
- `commands/sq/run-slice.md` — update CF command names
- `commands/sq/review-slice.md` — update CF command names
- `commands/sq/review-tasks.md` — update CF command names
- `commands/sq/review-code.md` — update CF command names

**Unchanged:**
- All other squadron code — no other files reference CF

---

## Success Criteria

1. `src/squadron/integrations/context_forge.py` exists with `ContextForgeClient` class
2. All CF subprocess calls go through `ContextForgeClient` — no direct `subprocess.run(["cf", ...])` in `review.py`
3. `_run_cf()` and inline JSON parsing removed from `review.py`
4. CF's new command surface (`cf list slices --json`, `cf list tasks --json`) used correctly
5. `sq review slice 122` works end-to-end (resolves slice via CF, runs review)
6. `sq review tasks 122` works end-to-end
7. Markdown command files reference correct CF command names
8. `ContextForgeClient.is_available()` returns `False` gracefully when `cf` not installed
9. `uv run pytest` — all tests pass; `uv run pyright` — 0 errors

---

### Verification Walkthrough

1. **Slice resolution via client:**
   ```bash
   sq review slice 122 --model minimax -v
   # Expect: resolves slice 122 design file, architecture doc via ContextForgeClient
   # Review executes successfully
   ```

2. **Task resolution via client:**
   ```bash
   sq review tasks 121 --model minimax -v
   # Expect: resolves task files and parent design via ContextForgeClient
   ```

3. **CF not installed:**
   ```bash
   # With cf not on PATH
   sq review slice 122
   # Expect: clear error message about CF not being available, not a stack trace
   ```

4. **Run-slice command:**
   ```bash
   # In Claude Code
   /sq:run-slice 126
   # Expect: uses updated CF commands (cf list slices, not cf slice list)
   ```

5. **No direct CF calls in review.py:**
   ```bash
   grep -n "subprocess.*cf\|\"cf\"" src/squadron/cli/commands/review.py
   # Expect: no matches
   ```

6. **Tests:**
   ```bash
   uv run pytest tests/ -v
   uv run pyright
   ```

---

## Implementation Notes

### Client Instantiation

The client is stateless — no persistent connection, no caching. Instantiate per-use: `client = ContextForgeClient()`. If caching becomes valuable (e.g., multiple calls in one command), that's a future optimization, not a design requirement.

### Error Handling Pattern

```python
# In context_forge.py
class ContextForgeNotAvailable(Exception): ...
class ContextForgeError(Exception): ...

# In review.py (CLI layer)
try:
    client = ContextForgeClient()
    slices = client.list_slices()
except ContextForgeNotAvailable:
    rprint("[red]Error: 'cf' not found. Install Context Forge.[/red]")
    raise typer.Exit(code=1)
except ContextForgeError as exc:
    rprint(f"[red]Error: {exc}[/red]")
    raise typer.Exit(code=1)
```

### Testing Strategy

- **Unit tests for `ContextForgeClient`:** Mock `subprocess.run`, verify command construction, JSON parsing, dataclass mapping
- **Unit tests for error paths:** CF not installed, CF returns error, malformed JSON
- **Integration regression:** Existing review CLI tests must pass (they already mock CF or skip when unavailable)
