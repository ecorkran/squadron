---
docType: tasks
slice: pool-resolver-integration-and-cli
project: squadron
lld: user/slices/181-slice.pool-resolver-integration-and-cli.md
dependencies: [180-model-pool-infrastructure-and-strategies, 142-model-resolver, 150-pipeline-state, 141-configuration-externalization]
projectState: Slice 180 complete (pool infrastructure at src/squadron/pipeline/intelligence/pools/). Slice 181 wires pools into the resolver, state, executor, and CLI.
dateCreated: 20260414
dateUpdated: 20260414
status: complete
---

## Context Summary

- Working on `pool-resolver-integration-and-cli` (slice 181)
- Integrates the pool infrastructure built in slice 180 into the runtime
  model resolution cascade, run state persistence, pipeline executor, and
  CLI surface
- **Actual package path is `squadron.pipeline.intelligence.pools`** — the
  slice design references `squadron.pools` in module diagrams; use the
  real path. `PoolBackend` protocol described in the design does not yet
  exist as a named class; slice 180 shipped `select_from_pool()` and
  loader functions instead. We will either (a) add a thin `PoolBackend`
  protocol in 181 or (b) wire the resolver to the existing module-level
  functions — Task 2 below decides
- Files to modify: `src/squadron/pipeline/resolver.py`,
  `src/squadron/pipeline/state.py`,
  `src/squadron/cli/commands/run.py` (resolver construction site —
  design says `executor.py` but resolver is actually built in `run.py`)
- New file: `src/squadron/cli/commands/pools.py`
- Register `pools_app` in `src/squadron/cli/app.py`
- Bump `state.py` `_SCHEMA_VERSION` from 3 to 4 and handle schema-3
  back-compat in `_load_raw`

---

## Tasks

### Task 1: Add `PoolSelection` dataclass in pools package

- [x] Add `PoolSelection` frozen dataclass to
  `src/squadron/pipeline/intelligence/pools/models.py` (keep with the
  other pool data models):
  - [x] Fields: `pool_name: str`, `selected_alias: str`, `strategy: str`,
    `step_name: str`, `action_type: str`, `timestamp: datetime`
  - [x] All fields required (no silent fallback values)
- [x] Re-export `PoolSelection` from
  `src/squadron/pipeline/intelligence/pools/__init__.py`
- [x] **Success criteria:** `from squadron.pipeline.intelligence.pools
  import PoolSelection` succeeds; instantiating with all six fields
  produces a frozen instance

---

### Task 2: Decide and define `PoolBackend` protocol

- [x] Add `PoolBackend` `@runtime_checkable Protocol` to a new file
  `src/squadron/pipeline/intelligence/pools/backend.py`:
  - [x] Methods: `select(pool_name, context) -> str`,
    `get_pool(pool_name) -> ModelPool`,
    `list_pools() -> dict[str, ModelPool]`,
    `reset_pool_state(pool_name) -> None`
- [x] Add `DefaultPoolBackend` class implementing the protocol by
  delegating to existing loader functions (`get_pool`, `get_all_pools`,
  `select_from_pool`, `clear_pool_state`) — do NOT duplicate logic
- [x] `DefaultPoolBackend.select()` signature must match protocol; it
  calls `select_from_pool(pool)` under the hood but accepts the
  `SelectionContext` passed from the resolver
- [x] Re-export `PoolBackend` and `DefaultPoolBackend` from the pools
  package `__init__`
- [x] **Success criteria:**
  `isinstance(DefaultPoolBackend(), PoolBackend)` is True at runtime;
  `DefaultPoolBackend().list_pools()` returns the three built-in pools

---

### Task 3: Test `PoolBackend` protocol and default implementation

- [x] Create `tests/pipeline/intelligence/pools/test_backend.py`
- [x] Test `DefaultPoolBackend.select("review", ctx)` returns a member
  of the review pool
- [x] Test `DefaultPoolBackend.get_pool("review")` returns the correct
  `ModelPool`
- [x] Test `DefaultPoolBackend.get_pool("does-not-exist")` raises
  `PoolNotFoundError`
- [x] Test `DefaultPoolBackend.list_pools()` contains `review`, `high`,
  `cheap`
- [x] Test `DefaultPoolBackend.reset_pool_state("review")` clears
  round-robin state (set state to non-zero, reset, reload returns
  `last_index=0`)
- [x] Test a stub implementing the four methods satisfies
  `isinstance(stub, PoolBackend)`
- [x] **Success criteria:** All backend tests pass

**Commit:** `feat: add PoolBackend protocol and PoolSelection dataclass for slice 181`

---

### Task 4: Extend `ModelResolver` with pool support

- [x] Edit `src/squadron/pipeline/resolver.py`:
  - [x] Update module docstring: remove "reserved for slice 160" note;
    describe pool support
  - [x] Add two `__init__` params: `pool_backend: PoolBackend | None = None`,
    `on_pool_selection: Callable[[PoolSelection], None] | None = None`
  - [x] Store as `self._pool_backend`, `self._on_pool_selection`
  - [x] In `resolve()`, when candidate starts with `pool:`, call new
    private `_resolve_pool(pool_name, action_model, step_model)`
    instead of raising
  - [x] Implement `_resolve_pool`: builds `SelectionContext`, calls
    `self._pool_backend.select(pool_name, context)`, then
    `resolve_model_alias(alias)`, then fires the
    `on_pool_selection` callback with a fully-populated `PoolSelection`
  - [x] If `self._pool_backend is None`, raise `ModelPoolNotImplemented`
    with a clear message (preserves existing behavior for tests)
- [x] Imports: `from collections.abc import Callable`,
  `from datetime import UTC, datetime`, pool symbols from
  `squadron.pipeline.intelligence.pools`
- [x] **Success criteria:** All existing resolver tests still pass; a
  `pool:` prefix with no backend still raises `ModelPoolNotImplemented`

---

### Task 5: Test resolver pool integration

- [x] In the existing resolver test file (or add
  `tests/pipeline/test_resolver_pools.py`), add tests using a stub
  `PoolBackend`:
  - [x] CLI override `pool:review` → resolves through backend to alias,
    then to `(model_id, profile)`
  - [x] Pipeline-level `pool:cheap` with no action override resolves
    via backend
  - [x] Action-level alias override beats pipeline-level `pool:` (cascade
    precedence unchanged)
  - [x] `on_pool_selection` callback fires exactly once per pool
    resolution with correct fields populated (pool_name, selected_alias,
    strategy, timestamp non-None)
  - [x] `pool:` candidate with `pool_backend=None` raises
    `ModelPoolNotImplemented`
  - [x] Error case: `pool_backend.select()` raises `PoolNotFoundError`
    propagates out of `resolve()` unchanged
- [x] **Success criteria:** New and existing resolver tests pass

**Commit:** `feat: integrate PoolBackend into ModelResolver cascade`

---

### Task 6: Extend `RunState` with pool selection log

- [x] Edit `src/squadron/pipeline/state.py`:
  - [x] Bump `_SCHEMA_VERSION` from `3` to `4`
  - [x] Add to `RunState`: `pool_selections: list[dict[str, object]] = []`
  - [x] In `_load_raw`, allow `schema_version in {3, 4}`: on version 3,
    accept the file and default `pool_selections` to `[]` (Pydantic
    default handles this); only raise `SchemaVersionError` for versions
    outside `{3, 4}`
  - [x] Add `StateManager.log_pool_selection(run_id, selection:
    PoolSelection) -> None`: loads state, appends serialized entry,
    writes atomically via existing `_write_atomic`
  - [x] Serialization: `timestamp` → isoformat string; all other fields
    copied directly
- [x] Do not import from the pools package at module top level if it
  creates a circular import — use a local import inside the method or a
  `TYPE_CHECKING` import for typing only
- [x] **Success criteria:** `StateManager.log_pool_selection()` appends
  a single dict entry; the state file round-trips correctly; old schema-3
  files load without error with `pool_selections=[]`

---

### Task 7: Test state pool-selection logging and schema migration

- [x] In `tests/pipeline/test_state.py` (or matching existing file),
  add tests:
  - [x] `log_pool_selection` appends a correctly-keyed dict (all six
    fields present, timestamp ISO-formatted)
  - [x] Multiple calls append multiple entries (no overwrite)
  - [x] Loading a manually-crafted `schema_version=3` state file
    succeeds and yields `pool_selections=[]`
  - [x] Loading a `schema_version=4` file round-trips through save+load
  - [x] Unsupported schema versions (e.g. `2`, `5`) still raise
    `SchemaVersionError`
- [x] **Success criteria:** All state tests pass; no regressions

**Commit:** `feat: add pool_selections to RunState (schema v4)`

---

### Task 8: Wire pool backend into resolver construction

- [x] Edit `src/squadron/cli/commands/run.py` — at each `ModelResolver(`
  call site (three instances: lines near 182, 367, 460):
  - [x] Instantiate `DefaultPoolBackend()` once and pass as
    `pool_backend=` parameter
  - [x] Pass `on_pool_selection=lambda sel:
    state_mgr.log_pool_selection(run_id, sel)` — ensure `run_id` and
    `state_mgr` are in scope at each call site (may require minor
    reordering if `run_id` is not yet known)
  - [x] If a call site does not have `run_id` at resolver build time
    (e.g. before `init_run`), pass a lazy callback that reads `run_id`
    from a closure cell set after init
- [x] Note: `squadron.pipeline.executor.execute_pipeline` accepts
  `resolver: ModelResolver` as a parameter; it does not construct a resolver
  internally. No changes to `executor.py` are required.
- [x] **Success criteria:** Full pipeline run with
  `sq run <name> --model pool:review` resolves to a member of the
  review pool; state file shows one `pool_selections` entry per
  resolved action

---

### Task 9: Integration test for pool resolution end-to-end

- [x] Create `tests/pipeline/test_pool_integration.py` (or extend the
  existing pipeline integration test file if one exists):
  - [x] Using a real pipeline definition fixture and a
    `DefaultPoolBackend`, run `execute_pipeline` with a `pool:` CLI
    override; assert the resolver selects a valid alias and the run
    state file contains at least one `pool_selections` entry with
    matching `pool_name` and `selected_alias`
  - [x] Test that pipeline-level `pool:` in pipeline YAML works (create
    a minimal in-memory `PipelineDefinition` with `model="pool:review"`)
  - [x] Test that action-level model override bypasses pipeline-level
    pool (cascade precedence)
- [x] Use `tmp_path` to isolate state files and pool-state.toml
- [x] **Success criteria:** Integration test passes; round-robin state
  advances across two runs of the same pool

**Commit:** `feat: wire DefaultPoolBackend into pipeline runner`

---

### Task 10: Implement `sq pools list` (with optional pool name)

- [ ] Create `src/squadron/cli/commands/pools.py` following the
  structure of `models.py`:
  - [ ] `pools_app = typer.Typer(name="pools", help="Inspect and manage model pools.", invoke_without_command=True)`
  - [ ] `@pools_app.callback()` invokes `list` when no subcommand
  - [ ] `@pools_app.command("list")` function `_list_pools(name: str | None = None)`:
    - [ ] **No name:** Calls `get_all_pools()` to fetch all pools; renders
      a Rich table with columns Name, Strategy, Members (count), Source
      ("(user)" if from user config, empty if builtin)
    - [ ] **With name:** Calls `get_pool(name)` — raises `PoolNotFoundError`
      if not found; CLI catches, prints clean error, exits non-zero
      - [ ] Prints pool metadata: name, description, strategy
      - [ ] Renders a Rich table of members with columns Alias, Model ID,
        Cost Tier (fetch metadata via `get_all_aliases()`)
      - [ ] Scans most recent 20 run state files in `~/.config/squadron/runs/`
        for `pool_selections` entries where `pool_name == name`; renders a
        second table with last 10 selections (Timestamp, Step, Selected Alias)
      - [ ] If no recent selections, prints `(no recent selections)`
- [ ] Handle empty case: if no pools loaded, print a single informative
  line and exit 0
- [ ] Use `StateManager.list_runs()` to enumerate runs; tolerate
  schema errors on individual files (skip and continue)
- [ ] **Success criteria:** `sq pools list` prints the three built-in
  pools as a table; `sq pools list review` prints pool detail with members
  and recent selections; `sq pools` (no subcommand) behaves like `list`

---

### Task 11: Implement `sq pools reset <name>`

- [ ] In `pools.py`, `@pools_app.command("reset")` takes required
  `name: str`:
  - [ ] Calls `DefaultPoolBackend().reset_pool_state(name)` (which
    delegates to `clear_pool_state`)
  - [ ] First verify pool exists via `get_pool(name)` — if not, error
    and exit non-zero before touching state
  - [ ] On success, print `Reset round-robin state for pool '{name}'.`
- [ ] **Success criteria:** After a round-robin advance, `sq pools reset
  review` clears state; `sq pools reset nope` exits non-zero

---

### Task 12: Register `pools_app` in the CLI

- [ ] Edit `src/squadron/cli/app.py`:
  - [ ] `from squadron.cli.commands.pools import pools_app`
  - [ ] `app.add_typer(pools_app, name="pools")`
- [ ] **Success criteria:** `sq pools --help` prints usage; `sq pools
  list` runs

---

### Task 13: Test `sq pools` commands

- [ ] Create `tests/cli/test_pools_command.py` following the pattern
  used for `tests/cli/test_models_command.py`:
  - [ ] Use Typer's `CliRunner` (or the existing project helper)
  - [ ] Test `sq pools list` exits 0 and output contains `review`,
    `high`, `cheap`
  - [ ] Test `sq pools list review` exits 0 and output contains
    `round-robin`, members table, and recent selections section
  - [ ] Test `sq pools list nonexistent` exits non-zero with a
    readable error
  - [ ] Test `sq pools reset review` exits 0; subsequent
    `load_pool_state("review").last_index == 0`
  - [ ] Test `sq pools reset nonexistent` exits non-zero
  - [ ] Test `sq pools` (no subcommand) behaves like `list`
  - [ ] Use `tmp_path` + monkeypatched `_config_dir` for state
    isolation
- [ ] **Success criteria:** All CLI tests pass; no pollution of real
  `~/.config/squadron/pool-state.toml`

**Commit:** `feat: add sq pools list and reset CLI commands`

---

### Task 14: Update docstring on `ModelPoolNotImplemented`

- [ ] Edit `src/squadron/pipeline/resolver.py`:
  - [ ] Change `ModelPoolNotImplemented` docstring from "reserved for
    slice 160" to "Raised when a `pool:` candidate is encountered and
    no `PoolBackend` is configured — typically a test context or a
    misconfigured runner."
  - [ ] Update module-level docstring: replace the "reserved for slice
    160" line with a short description of pool support
- [ ] **Success criteria:** Docstrings reflect real current behavior;
  no references to slice 160 remain in `resolver.py`

---

### Task 15: Final validation pass

- [ ] Run `pytest tests/pipeline/intelligence/pools/` — all 180+181
  tests pass
- [ ] Run `pytest tests/pipeline/ tests/cli/` — no regressions
- [ ] Run full `pytest` — entire suite green (expect 1478 + new tests
  from this slice)
- [ ] Run `ruff check src/squadron/pipeline/ src/squadron/cli/commands/pools.py`
  — clean
- [ ] Run `ruff format` before committing (per project feedback)
- [ ] Manual smoke check:
  - [ ] `sq pools list` prints table
  - [ ] `sq pools list review` prints members and recent selections
  - [ ] `sq pools reset review` confirms reset
  - [ ] `sq run <some-pipeline> --model pool:review --prompt-only`
    produces a run state file with a populated `pool_selections` list
- [ ] **Success criteria:** Full suite green; all verification-walkthrough
  steps in the slice design file complete without error

**Commit:** `feat: slice 181 — pool resolver integration and CLI`
