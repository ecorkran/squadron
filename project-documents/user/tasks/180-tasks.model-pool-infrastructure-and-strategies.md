---
docType: tasks
slice: model-pool-infrastructure-and-strategies
project: squadron
lld: user/slices/180-slice.model-pool-infrastructure-and-strategies.md
dependencies: [141-configuration-externalization, 142-model-resolver]
projectState: Pipeline intelligence layer underway; slice 191 complete, slice 180 is next implementation target.
dateCreated: 20260413
dateUpdated: 20260413
status: complete
---

## Context Summary

- Working on `model-pool-infrastructure-and-strategies` (slice 180)
- Delivers the data model, pool TOML schema, built-in pool definitions,
  user override loading, four selection strategies behind a `PoolStrategy`
  protocol, and round-robin persistent state
- Does **not** integrate with the model resolver or expose CLI commands —
  those are slice 181
- Depends on slice 141 (`~/.config/squadron/` convention) and slice 142
  (`get_all_aliases()`, `ModelAlias` with `cost_tier`)
- Next slice: 181 (Pool Resolver Integration and CLI)
- Package location: `src/squadron/pipeline/intelligence/pools/`

---

## Tasks

### Task 1: Create `intelligence` and `pools` sub-package scaffolding

- [x] Create `src/squadron/pipeline/intelligence/__init__.py` (empty, marks package)
- [x] Create `src/squadron/pipeline/intelligence/pools/__init__.py`
  - [x] Leave empty for now; public re-exports added in Task 6
- [x] Verify that `from squadron.pipeline.intelligence import pools` resolves
  without import error
- [x] **Success criteria:** Both `__init__.py` files exist; `python -c "import squadron.pipeline.intelligence.pools"` exits 0

---

### Task 2: Create test infrastructure (conftest and fixtures)

- [x] Create `tests/pipeline/intelligence/` directory with `__init__.py`
- [x] Create `tests/pipeline/intelligence/pools/__init__.py`
- [x] Create `tests/pipeline/intelligence/pools/conftest.py`
  - [x] Add `sample_aliases` fixture returning a dict of `ModelAlias` objects
    covering: `minimax`, `glm5`, `kimi25`, `grok-fast`, `opus`, `gpt54`,
    `gemini`, `flash3`, `gemma4`, `qwen36-free` — with varying `cost_tier`
    values (`free`, `cheap`, `moderate`, `expensive`)
  - [x] Add `builtin_pools_toml` fixture returning the text of
    `src/squadron/data/pools.toml` (read from the actual file, not hardcoded)
  - [x] Add `tmp_state_file` fixture using `tmp_path` to isolate
    `pool-state.toml` writes
- [x] **Success criteria:** `pytest tests/pipeline/intelligence/pools/ --collect-only`
  collects 0 tests (file exists, no errors)

---

### Task 3: Implement data models (`models.py`)

- [x] Create `src/squadron/pipeline/intelligence/pools/models.py`
- [x] Implement `ModelPool` frozen dataclass:
  - [x] Fields: `name: str`, `description: str`, `models: list[str]`,
    `strategy: str`, `weights: dict[str, float] | None = None`
- [x] Implement `SelectionContext` dataclass:
  - [x] Fields: `pool_name: str`, `action_type: str`,
    `run_id: str | None = None`, `aliases: dict[str, ModelAlias] | None = None`,
    `pool_state: PoolState | None = None`,
    `task_description: str | None = None`
- [x] Implement `PoolState` dataclass:
  - [x] Field: `last_index: int = 0`
- [x] Implement custom exception classes: `PoolValidationError`,
  `PoolNotFoundError`, `StrategyNotFoundError`
- [x] All classes fully type-annotated; import `ModelAlias` from
  `squadron.models.aliases`
- [x] **Success criteria:** `from squadron.pipeline.intelligence.pools.models import ModelPool, SelectionContext, PoolState` succeeds; all fields accessible

---

### Task 4: Test data models

- [x] Create `tests/pipeline/intelligence/pools/test_models.py`
- [x] Test `ModelPool` instantiation with and without `weights`
- [x] Test `ModelPool` is frozen (assignment raises `FrozenInstanceError`)
- [x] Test `SelectionContext` with all optional fields defaulting to `None`
- [x] Test `PoolState` default `last_index` is 0
- [x] Test each exception class is a subclass of `Exception`
- [x] **Success criteria:** All model tests pass; `ruff check` clean

**Commit:** `feat: add ModelPool, SelectionContext, PoolState data models`

---

### Task 5: Implement `PoolStrategy` protocol (`protocol.py`)

- [x] Create `src/squadron/pipeline/intelligence/pools/protocol.py`
- [x] Define `PoolStrategy` as a `@runtime_checkable` `Protocol`:
  - [x] Method: `select(self, pool: ModelPool, context: SelectionContext) -> str`
- [x] Import `ModelPool`, `SelectionContext` from `.models`
- [x] **Success criteria:** `isinstance(obj, PoolStrategy)` works at runtime for
  any object implementing `select`

---

### Task 6: Implement cost-tier ordering constant

- [x] In `src/squadron/pipeline/intelligence/pools/strategies.py`, define
  `COST_TIER_RANK: dict[str, int]` mapping `free→0`, `cheap→1`,
  `moderate→2`, `expensive→3`, `subscription→4`
- [x] This constant is the single source of truth for tier ordering — no
  magic values scattered in conditionals
- [x] **Success criteria:** `COST_TIER_RANK["free"] == 0` and
  `COST_TIER_RANK["expensive"] == 3`

---

### Task 7: Implement `random` strategy

- [x] In `strategies.py`, implement `RandomStrategy` class conforming to
  `PoolStrategy`
- [x] `select()` returns a uniformly random member alias name from
  `pool.models`
- [x] Works correctly for a single-member pool
- [x] **Success criteria:** 100 calls on a 3-member pool produce all three
  members; single-member pool always returns same member

---

### Task 8: Test `random` strategy

- [x] Create `tests/pipeline/intelligence/pools/test_strategies.py`
- [x] Test uniform distribution over 200 calls (each member appears > 30 times)
- [x] Test single-member pool: always returns the one member
- [x] **Success criteria:** All random strategy tests pass

---

### Task 9: Implement `round-robin` strategy

- [x] In `strategies.py`, implement `RoundRobinStrategy` conforming to
  `PoolStrategy`
- [x] `select()` reads `context.pool_state.last_index`, advances by 1 mod
  `len(pool.models)`, updates `context.pool_state.last_index`, returns
  `pool.models[next_index]`
- [x] If `context.pool_state` is `None`, treat `last_index` as 0
- [x] Mutates the passed `PoolState` in place (caller is responsible for
  persisting it)
- [x] Works correctly for a single-member pool (always index 0)
- [x] **Success criteria:** Three calls on a 3-member pool return all three
  members in order; fourth call returns first member again

---

### Task 10: Test `round-robin` strategy

- [x] In `test_strategies.py`, test deterministic rotation through all members
- [x] Test wrap-around on the N+1th call returns first member
- [x] Test single-member pool: all calls return the same member
- [x] Test `None` pool_state treated as index 0
- [x] **Success criteria:** All round-robin strategy tests pass

---

### Task 11: Implement `cheapest` strategy

- [x] In `strategies.py`, implement `CheapestStrategy` conforming to
  `PoolStrategy`
- [x] `select()` resolves each member's cost tier from
  `context.aliases[member].cost_tier` using `COST_TIER_RANK`
- [x] Breaks ties within same tier by `context.aliases[member].pricing.input`
  (lowest wins); if pricing unavailable, breaks randomly
- [x] If `context.aliases` is `None` or a member is missing, treats that
  member's tier rank as `len(COST_TIER_RANK)` (worst rank)
- [x] Returns the alias name of the cheapest member
- [x] **Success criteria:** Given aliases with known tiers, returns the
  cheapest; ties broken correctly

---

### Task 12: Test `cheapest` strategy

- [x] In `test_strategies.py`, use `sample_aliases` fixture
- [x] Test: pool with members of distinct tiers returns `free`-tier member
- [x] Test: same-tier members broken by `pricing.input`
- [x] Test: member with unknown cost tier ranked worst
- [x] Test: single-member pool returns that member regardless of tier
- [x] **Success criteria:** All cheapest strategy tests pass

---

### Task 13: Implement `weighted-random` strategy

- [x] In `strategies.py`, implement `WeightedRandomStrategy` conforming to
  `PoolStrategy`
- [x] `select()` uses `pool.weights` for per-member weights; absent members
  default to `1.0`
- [x] Normalizes weights to probabilities at selection time
- [x] Returns alias name of selected member
- [x] Empty `pool.weights` (all defaulting to 1.0) behaves identically to
  uniform random
- [x] **Success criteria:** Over 1000 calls, a member with weight 2.0 appears
  approximately twice as often as one with weight 1.0 (within 20% tolerance)

---

### Task 14: Test `weighted-random` strategy

- [x] In `test_strategies.py`, test relative frequency matches weight ratio
  (2:1 weight → ~2:1 frequency, within tolerance)
- [x] Test: all members absent from `weights` → uniform distribution
- [x] Test: single-member pool always returns that member
- [x] **Success criteria:** All weighted-random strategy tests pass

**Commit:** `feat: add PoolStrategy protocol and four built-in strategies`

---

### Task 15: Implement strategy registry

- [x] In `strategies.py`, create module-level `_STRATEGY_REGISTRY: dict[str, PoolStrategy]`
  populated at import time with keys `"random"`, `"round-robin"`,
  `"cheapest"`, `"weighted-random"` mapping to singleton instances
- [x] Implement `register_strategy(name: str, strategy: PoolStrategy) -> None`
  for extensibility
- [x] Implement `get_strategy(name: str) -> PoolStrategy` raising
  `StrategyNotFoundError` for unknown names
- [x] **Success criteria:** `get_strategy("random")` returns `RandomStrategy`
  instance; `get_strategy("nope")` raises `StrategyNotFoundError`

---

### Task 16: Test strategy registry

- [x] In `test_strategies.py`, test all four built-in strategies retrievable
  by name
- [x] Test `get_strategy` with unknown name raises `StrategyNotFoundError`
- [x] Test `register_strategy` adds a new entry retrievable by `get_strategy`
- [x] **Success criteria:** All registry tests pass

---

### Task 17: Implement round-robin state persistence (`loader.py` state section)

- [x] Create `src/squadron/pipeline/intelligence/pools/loader.py`
- [x] Implement `load_pool_state(pool_name: str) -> PoolState`:
  - [x] Reads `~/.config/squadron/pool-state.toml`
  - [x] Missing file or missing pool entry → returns `PoolState(last_index=0)`
  - [x] Parses `[pools.<pool_name>] last_index` into `PoolState`
- [x] Implement `save_pool_state(pool_name: str, state: PoolState) -> None`:
  - [x] Reads current file (or starts empty), updates the pool's entry,
    writes back with `tomli_w`
  - [x] Creates file and directories if absent
- [x] Implement `clear_pool_state(pool_name: str) -> None`:
  - [x] Removes the pool's entry from the file; no-op if absent
- [x] **Success criteria:** Roundtrip: `save_pool_state("review", PoolState(3))`
  then `load_pool_state("review")` returns `PoolState(last_index=3)`

---

### Task 18: Test round-robin state persistence

- [x] Create `tests/pipeline/intelligence/pools/test_state.py`
- [x] Use `tmp_state_file` fixture (monkeypatch config dir to `tmp_path`)
- [x] Test: `load_pool_state` with missing file returns `PoolState(0)`
- [x] Test: `load_pool_state` with missing pool entry returns `PoolState(0)`
- [x] Test: save then load roundtrip preserves `last_index`
- [x] Test: save updates existing entry without destroying other pools
- [x] Test: wrap-around: index increments from N-1 to 0 across calls
- [x] Test: `clear_pool_state` removes entry; subsequent load returns 0
- [x] Test: `clear_pool_state` on absent entry is a no-op (no exception)
- [x] **Success criteria:** All state persistence tests pass

**Commit:** `feat: add round-robin state persistence (load/save/clear)`

---

### Task 19: Create built-in `pools.toml`

- [x] Create `src/squadron/data/pools.toml` with three default pools:
  - [x] `review`: `strategy = "round-robin"`, models `["minimax", "glm5", "kimi25", "grok-fast"]`
  - [x] `high`: `strategy = "random"`, models `["opus", "gpt54", "gemini"]`
  - [x] `cheap`: `strategy = "cheapest"`, models `["minimax", "glm5", "grok-fast", "flash3", "gemma4", "qwen36-free"]`
  - [x] Each pool has a `description` field
- [x] File uses `[pools.<name>]` table structure matching the schema in the
  slice design
- [x] **Success criteria:** File parses without error via
  `python -c "import tomllib; tomllib.load(open('src/squadron/data/pools.toml','rb'))"`

---

### Task 20: Implement pool loader (`loader.py` loading section)

- [x] In `loader.py`, implement `load_builtin_pools() -> dict[str, ModelPool]`:
  - [x] Reads `src/squadron/data/pools.toml` via `squadron.data.data_dir()`
  - [x] Parses each `[pools.*]` table into a `ModelPool`
  - [x] Validates required fields: `models` (non-empty list), `strategy`
    (registered name)
  - [x] Validates `weights` keys (if present) are a subset of `models`
  - [x] Raises `PoolValidationError` with pool name, bad field, and
    diagnostics on failure
- [x] Implement `load_user_pools() -> dict[str, ModelPool]`:
  - [x] Reads `~/.config/squadron/pools.toml`; returns `{}` if absent
  - [x] Same parsing and validation as built-in
- [x] Implement `get_all_pools() -> dict[str, ModelPool]`:
  - [x] Merges built-in and user pools; user wins on name collision
- [x] Implement `get_pool(name: str) -> ModelPool`:
  - [x] Returns pool from `get_all_pools()`; raises `PoolNotFoundError` if absent

---

### Task 21: Test pool loader

- [x] Create `tests/pipeline/intelligence/pools/test_loader.py`
- [x] Test `load_builtin_pools()` against the actual `pools.toml` file
  (use `builtin_pools_toml` fixture) — confirms parser handles production format
- [x] Test all three default pools load with correct strategy and model counts
- [x] Test user pool file overrides built-in pool by name
- [x] Test user pool file absent → `load_user_pools()` returns `{}`
- [x] Test `PoolValidationError` raised for: unknown strategy, empty models
  list, unknown alias in models (patch `get_all_aliases()` to known set)
- [x] Test `PoolValidationError` raised for weights keys not in models
- [x] Test `get_pool` raises `PoolNotFoundError` for unknown pool name
- [x] **Success criteria:** All loader tests pass

**Commit:** `feat: add pool loader with validation and merge logic`

---

### Task 22: Implement pool member validation against alias registry

- [x] In `loader.py` validation logic, call `get_all_aliases()` and verify
  each model entry exists as an alias key
- [x] On failure, raise `PoolValidationError` with: pool name, unknown member
  name, and the list of valid aliases (truncated to first 20 for readability)
- [x] Validation runs at load time for all pools, not lazily on first use
- [x] **Success criteria:** Loading a pool with `models = ["nonexistent-alias"]`
  raises `PoolValidationError` naming the bad member

---

### Task 23: Test alias validation

- [x] In `test_loader.py`, monkeypatch `get_all_aliases()` to a known
  fixture set
- [x] Test: pool referencing a valid alias → loads without error
- [x] Test: pool referencing unknown alias → `PoolValidationError` names the
  bad member
- [x] **Success criteria:** Alias validation tests pass; ruff clean

---

### Task 24: Implement `select_from_pool` convenience wrapper

- [x] In `loader.py` (or a new `selector.py` if file length warrants), implement:
  ```python
  def select_from_pool(pool: ModelPool) -> str
  ```
  - [x] Builds `SelectionContext` with `aliases=get_all_aliases()` and
    `pool_state=load_pool_state(pool.name)` for round-robin
  - [x] Calls `get_strategy(pool.strategy).select(pool, context)`
  - [x] If strategy is `round-robin`, calls `save_pool_state(pool.name, context.pool_state)` after selection
  - [x] Returns selected alias name
- [x] **Success criteria:** `select_from_pool(get_pool("review"))` returns a
  string that is a member of `pools["review"].models`

---

### Task 25: Test `select_from_pool`

- [x] In `test_loader.py` (or `test_selector.py`), monkeypatch
  `get_all_aliases()` and state file dir
- [x] Test: round-robin pool — two consecutive calls return different members
  and state file is updated
- [x] Test: random pool — call returns a member in `pool.models`
- [x] Test: cheapest pool — call returns cheapest alias per fixture aliases
- [x] **Success criteria:** All `select_from_pool` tests pass

**Commit:** `feat: add select_from_pool convenience wrapper`

---

### Task 26: Wire up public API in `pools/__init__.py`

- [x] Edit `src/squadron/pipeline/intelligence/pools/__init__.py` to re-export:
  - [x] `ModelPool`, `SelectionContext`, `PoolState` from `.models`
  - [x] `PoolStrategy` from `.protocol`
  - [x] `PoolValidationError`, `PoolNotFoundError`, `StrategyNotFoundError`
    from `.models`
  - [x] `load_builtin_pools`, `load_user_pools`, `get_all_pools`, `get_pool`
    from `.loader`
  - [x] `select_from_pool` from loader/selector
  - [x] `register_strategy`, `get_strategy` from `.strategies`
  - [x] `load_pool_state`, `save_pool_state`, `clear_pool_state` from `.loader`
- [x] **Success criteria:** All symbols in the slice design's Public API Surface
  importable directly from `squadron.pipeline.intelligence.pools`

---

### Task 27: Integration smoke test

- [x] Run the following in a Python shell or a `tests/pipeline/intelligence/pools/test_integration.py`:
  - [x] `get_all_pools()` returns dict containing `"review"`, `"high"`, `"cheap"`
  - [x] `len(get_all_pools()["review"].models) >= 3`
  - [x] `select_from_pool(get_pool("review"))` returns a string in `["minimax", "glm5", "kimi25", "grok-fast"]`
  - [x] `select_from_pool(get_pool("cheap"))` returns a string in the cheap pool's models
- [x] **Success criteria:** Integration test passes with real alias registry

---

### Task 28: Final validation pass

- [x] Run `pytest tests/pipeline/intelligence/` — all new tests pass
- [x] Run `pytest` (full suite) — no regressions in existing 623+ tests
- [x] Run `ruff check src/squadron/pipeline/intelligence/` — clean
- [x] Run `ruff format src/squadron/pipeline/intelligence/` — no changes
- [x] Verify all public API symbols importable from
  `squadron.pipeline.intelligence.pools`
- [x] **Success criteria:** Full suite green; ruff clean; no type errors from `mypy` or `pyright` on new files (if type checking is configured)

**Commit:** `feat: slice 180 — model pool infrastructure and strategies`
