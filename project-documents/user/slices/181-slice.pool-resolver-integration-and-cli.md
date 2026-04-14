---
docType: slice-design
slice: pool-resolver-integration-and-cli
project: squadron
parent: 180-slices.pipeline-intelligence.md
dependencies: [180-model-pool-infrastructure-and-strategies]
interfaces: [ModelResolver, StateManager, PoolBackend]
dateCreated: 20260411
dateUpdated: 20260411
status: not-started
---

# Slice Design: Pool Resolver Integration and CLI

## Overview

Extends the existing `ModelResolver` cascade in
`src/squadron/pipeline/resolver.py` to handle the `pool:` prefix that
slice 180 introduced as a schema concept. Resolution is recursive and
transparent: `pool:<name>` resolves to an alias name via the pool
backend, and that alias resolves to `(model_id, profile)` through the
existing alias registry — exactly as if the alias had been specified
directly. No action handler changes are needed for pool-backed models.

Every pool selection is logged as a structured entry in run state, giving
operators a per-run audit trail for debugging strategy behavior. The CLI
gains a `sq pools` command for pool inspection and round-robin state
management.

---

## Motivation

Slice 180 defines pool data models and strategies but deliberately stops
short of wiring them into the resolver — that is this slice. Until 181
lands, any `pool:` reference in a pipeline definition or `--model` flag
raises `ModelPoolNotImplemented`. After 181, `pool:` is a first-class
resolution candidate at every level of the cascade.

---

## Dependencies

| Dependency | What 181 Needs |
|---|---|
| 180 — Model Pool Infrastructure | `ModelPool`, `PoolStrategy` protocol, `SelectionContext`, `PoolNotFoundError`, module-level functions: `select_from_pool`, `get_pool`, `get_all_pools`, `clear_pool_state` |
| 142 — Pipeline Core Models / Action Protocol | `ActionContext` for executor integration |
| 150 — Pipeline State | `RunState`, `StateManager` for pool selection logging |
| 141 — Configuration Externalization | Config path conventions for `pool-state.toml` |

---

## Design

### Module Layout

```
src/squadron/pipeline/intelligence/pools/   ← created by slice 180
  __init__.py
  models.py      ← ModelPool, SelectionContext, PoolState, PoolNotFoundError (180)
  protocol.py    ← PoolStrategy protocol (180)
  strategies.py  ← built-in strategy implementations (180)
  loader.py      ← select_from_pool(), get_pool(), get_all_pools(),
                   load/save/clear_pool_state() (180)
  backend.py     ← PoolBackend protocol + DefaultPoolBackend + PoolSelection (181)
```

Slice 181 adds `backend.py` to `src/squadron/pipeline/intelligence/pools/`. It also modifies:
- `src/squadron/pipeline/resolver.py` — integrate `PoolBackend`
- `src/squadron/pipeline/state.py` — add pool selection log to `RunState`
- `src/squadron/cli/commands/run.py` — wire pool backend at resolver construction sites
- `src/squadron/cli/commands/pools.py` — new `sq pools` command
- `src/squadron/cli/app.py` — register `pools_app`

### 1. `PoolBackend` Protocol (defined in slice 181, consumed by resolver)

Slice 181 defines these in `src/squadron/pipeline/intelligence/pools/backend.py`.
Slice 180 shipped module-level functions in `loader.py`; `PoolBackend` and
`DefaultPoolBackend` are new in this slice. `DefaultPoolBackend` delegates to
the existing `loader.py` functions — no logic is duplicated.

```python
class PoolSelection:
    """Record of a single pool resolution event."""
    pool_name: str
    selected_alias: str
    strategy: str
    step_name: str       # pipeline step that triggered the resolution
    action_type: str     # e.g. "dispatch", "review"
    timestamp: datetime

class PoolBackend(Protocol):
    def select(self, pool_name: str, context: SelectionContext) -> str:
        """Resolve pool_name to an alias. Raises PoolNotFoundError if absent."""
        ...
    def get_pool(self, pool_name: str) -> ModelPool: ...
    def list_pools(self) -> dict[str, ModelPool]: ...
    def reset_pool_state(self, pool_name: str) -> None: ...

class DefaultPoolBackend:
    """Implements PoolBackend by delegating to loader.py functions."""
    def select(self, pool_name: str, context: SelectionContext) -> str:
        return select_from_pool(get_pool(pool_name))
    def get_pool(self, pool_name: str) -> ModelPool:
        return get_pool(pool_name)
    def list_pools(self) -> dict[str, ModelPool]:
        return get_all_pools()
    def reset_pool_state(self, pool_name: str) -> None:
        clear_pool_state(pool_name)
```

`PoolNotFoundError` (from 180) is raised when the named pool does
not exist in the loaded configuration.

### 2. `ModelResolver` Integration

**File:** `src/squadron/pipeline/resolver.py`

Changes:
1. Accept `pool_backend: PoolBackend | None = None` in `__init__`.
2. Accept `on_pool_selection: Callable[[PoolSelection], None] | None = None` in `__init__`.
3. In `resolve()`, when a candidate starts with `pool:`, delegate to `_resolve_pool()`.

```python
class ModelResolver:
    def __init__(
        self,
        cli_override: str | None = None,
        pipeline_model: str | None = None,
        config_default: str | None = None,
        pool_backend: PoolBackend | None = None,
        on_pool_selection: Callable[[PoolSelection], None] | None = None,
    ) -> None:
        self._cli_override = cli_override
        self._pipeline_model = pipeline_model
        self._config_default = config_default
        self._pool_backend = pool_backend
        self._on_pool_selection = on_pool_selection
```

`resolve()` updated logic (replacing the `pool:` branch):

```python
if candidate.startswith("pool:"):
    pool_name = candidate.removeprefix("pool:")
    return self._resolve_pool(pool_name, action_model, step_model)
```

New private method:

```python
def _resolve_pool(
    self,
    pool_name: str,
    action_model: str | None,
    step_model: str | None,
) -> tuple[str, str | None]:
    if self._pool_backend is None:
        raise ModelPoolNotImplemented(
            f"Pool-based model selection is not configured: '{pool_name}'. "
            "Ensure PoolBackend is wired into ModelResolver."
        )
    context = SelectionContext(
        action_model=action_model,
        step_model=step_model,
    )
    alias = self._pool_backend.select(pool_name, context)
    result = resolve_model_alias(alias)
    if self._on_pool_selection is not None:
        selection = PoolSelection(
            pool_name=pool_name,
            selected_alias=alias,
            strategy=self._pool_backend.get_pool(pool_name).strategy,
            step_name=context.step_name or "",
            action_type=context.action_type or "",
            timestamp=datetime.now(UTC),
        )
        self._on_pool_selection(selection)
    return result
```

**Resolution is one level deep.** Pool entries must be alias references
(validated by slice 180's loader at load time). There is no pool-of-pools
recursive case; `_resolve_pool()` always terminates after one pool lookup
and one alias lookup.

The existing `ModelPoolNotImplemented` exception class is preserved for
backward compatibility (tests that expect it when no backend is set still
pass). The docstring in `resolver.py` is updated to remove the "reserved
for slice 160" note.

**No action handler changes are required.** Callers (`dispatch.py`,
`review.py`, `summary.py`) call `resolver.resolve(action_model,
step_model)` and receive `(model_id, profile)` — pool resolution is
transparent.

### 3. Run State: Pool Selection Log

**File:** `src/squadron/pipeline/state.py`

`RunState` gains a new field:

```python
class RunState(BaseModel):
    ...
    pool_selections: list[dict[str, object]] = []
```

`PoolSelection` is serialized to a plain dict before appending (keeps the
state model dependency-free from the pools module):

```python
{
    "pool_name": "review",
    "selected_alias": "glm5",
    "strategy": "round-robin",
    "step_name": "design-0",
    "action_type": "dispatch",
    "timestamp": "2026-04-11T12:34:56.789Z"
}
```

`_SCHEMA_VERSION` is bumped from 3 to 4.

`StateManager` gets a new method:

```python
def log_pool_selection(self, run_id: str, selection: PoolSelection) -> None:
    """Append a pool selection record to the run's state file."""
    state = self.load(run_id)
    entry = {
        "pool_name": selection.pool_name,
        "selected_alias": selection.selected_alias,
        "strategy": selection.strategy,
        "step_name": selection.step_name,
        "action_type": selection.action_type,
        "timestamp": selection.timestamp.isoformat(),
    }
    state.pool_selections.append(entry)
    self.save(state)
```

**Schema version migration:** `StateManager.load()` must already handle
forward-only migration; older state files (schema version < 4) load
successfully with `pool_selections` defaulting to `[]`. No migration
logic is needed — Pydantic's default value handles it.

### 4. Executor Integration

**File:** `src/squadron/cli/commands/run.py`

`execute_pipeline()` in `executor.py` accepts `resolver: ModelResolver` as a
parameter — it does not construct one. All three `ModelResolver(` construction
sites are in `src/squadron/cli/commands/run.py` (around lines 182, 367, 460).
Slice 181 modifies those three sites to pass `pool_backend` and
`on_pool_selection`:

```python
pool_backend = DefaultPoolBackend()
resolver = ModelResolver(
    cli_override=cli_model,
    pipeline_model=definition.model,
    config_default=config_default,
    pool_backend=pool_backend,
    on_pool_selection=lambda sel: state_mgr.log_pool_selection(run_id, sel),
)
```

`DefaultPoolBackend` is defined in slice 181 (see §1). If pools configuration
is absent or empty, `get_all_pools()` returns only built-in pools; unknown pool
names raise `PoolNotFoundError` (no silent empty pool). The `on_pool_selection`
callback writes to the live state file on each selection event; it is safe to
call from within action handlers because `StateManager.save()` uses an atomic
write-then-rename.

The `ActionContext` dataclass does not change. The resolver already flows
through to every action via `ActionContext.resolver`.

### 5. CLI: `sq pools`

**New file:** `src/squadron/cli/commands/pools.py`

Follows the same structure as `src/squadron/cli/commands/models.py`.

```
sq pools                     → list all pools (alias for sq pools list)
sq pools list                → tabular list: Name | Strategy | Members | Source
sq pools show <name>         → pool members + recent selections from run state files
sq pools reset <name>        → clear round-robin state for a named pool
```

**`sq pools list`:** Calls `PoolLoader.load().list_pools()`, renders a
Rich table. Columns: Alias (pool name), Strategy, Members (count), Source
("(user)" if from `~/.config/squadron/pools.toml`, empty if built-in).

**`sq pools show <name>`:** Calls `PoolLoader.load().get_pool(name)`,
displays full member list with alias metadata (model_id, cost_tier).
Then scans the most recent 20 run state files in
`~/.config/squadron/runs/` for `pool_selections` entries matching the
pool name, shows last 10 with timestamp, step_name, and selected alias.
If no recent selections exist, prints "(no recent selections)".

**`sq pools reset <name>`:** Calls `pool_backend.reset_pool_state(name)`,
confirms with a message. Errors if the pool does not exist.

**Registration in `app.py`:**

```python
from squadron.cli.commands.pools import pools_app
app.add_typer(pools_app, name="pools")
```

---

## Cross-Slice Interfaces

### Provided to downstream slices (182+)

- `ModelResolver` with pool support — fan-out (182) will use the same
  resolver cascade; pool-specified model lists in fan-out configs resolve
  transparently through `pool_backend.select()`.

### Consumed from slice 180

- `ModelPool` and `ModelPool.strategy` field (for logging)
- `SelectionContext` dataclass
- `PoolNotFoundError` exception
- Module-level functions: `select_from_pool`, `get_pool`, `get_all_pools`,
  `clear_pool_state` (all in `squadron.pipeline.intelligence.pools.loader`)

`PoolBackend`, `DefaultPoolBackend`, and `PoolSelection` are defined in
slice 181 (`backend.py`).

---

## Success Criteria

1. `sq run <pipeline> --model pool:<name>` executes the pipeline using a
   model selected from the named pool; the selection is logged in the run
   state file under `pool_selections`.

2. A pipeline YAML with `model: pool:<name>` at the pipeline level causes
   every action without an explicit model override to resolve through the
   pool. Each resolution is independently logged.

3. A pipeline YAML with `model: pool:<name>` at the action level overrides
   step and pipeline level, and resolves through the pool for that action
   only. This is the same cascade precedence as alias-based models.

4. When no pool backend is configured (unit test context), `pool:` prefixed
   model references raise `ModelPoolNotImplemented`, unchanged from prior
   behavior.

5. `sq pools list` prints a table of all available pools without error.

6. `sq pools show <name>` prints pool members and recent selections (or
   "(no recent selections)" when the run history is empty).

7. `sq pools reset <name>` clears round-robin state and confirms; raises a
   clear error if the pool name is unknown.

8. All existing resolver tests continue to pass without modification.

9. Run state files produced under schema version 4 load correctly in
   `StateManager.load()`; older schema version 3 files also load (with
   `pool_selections` defaulting to `[]`).

---

## Verification Walkthrough

After implementation:

```bash
# 1. Confirm pool listing works
sq pools list

# 2. Confirm pool detail works
sq pools show review

# 3. Run a pipeline with a pool override (assumes 'review' pool exists)
sq run slice 182 --model pool:review

# 4. Inspect run state for pool selection log
cat ~/.config/squadron/runs/run-$(date +%Y%m%d)-*.json | python3 -c \
  "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('pool_selections', []), indent=2))"

# 5. Verify at least one entry with pool_name, selected_alias, strategy, step_name

# 6. Reset round-robin state
sq pools reset review

# 7. Confirm sq pools reset <nonexistent> errors clearly
sq pools reset does-not-exist  # expect non-zero exit + readable error
```

To verify cascade precedence:
- Pipeline YAML with `model: pool:cheap` at pipeline level, action with
  explicit `model: opus` — action should use `opus`, pipeline-level steps
  use pool selection.

---

## Implementation Notes

### Development Approach

Suggested order within the slice:
1. Add `pool_backend` and `on_pool_selection` params to `ModelResolver`;
   add `_resolve_pool()`. Run existing resolver tests — all pass.
2. Add `pool_selections` to `RunState`, bump schema version, add
   `StateManager.log_pool_selection()`. Run state tests.
3. Wire `PoolLoader.load()` and callback into `executor.py`.
4. Implement `src/squadron/cli/commands/pools.py` and register in `app.py`.

### Testing Strategy

- Unit tests for `ModelResolver._resolve_pool()` using a stub `PoolBackend`.
- Unit test: `on_pool_selection` callback fires with correct `PoolSelection` fields.
- Unit test: `StateManager.log_pool_selection()` appends correctly and
  round-trips through JSON serialization.
- Unit test: `StateManager.load()` on a schema_version=3 state file
  succeeds with `pool_selections=[]`.
- Integration test: `sq pools list` / `show` / `reset` via subprocess or
  Typer test client (following the pattern in existing CLI tests).

---

## DEVLOG Entry

See DEVLOG.md under `## 20260411`.
