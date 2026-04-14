---
docType: tasks
slice: model-pool-infrastructure-and-strategies
project: squadron
lld: user/slices/180-slice.model-pool-infrastructure-and-strategies.md
dependencies: [141-configuration-externalization, 142-model-resolver]
projectState: Pipeline intelligence layer underway; slice 191 complete, slice 180 is next implementation target.
dateCreated: 20260413
dateUpdated: 20260413
status: not_started
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

- [ ] Create `src/squadron/pipeline/intelligence/__init__.py` (empty, marks package)
- [ ] Create `src/squadron/pipeline/intelligence/pools/__init__.py`
  - [ ] Leave empty for now; public re-exports added in Task 6
- [ ] Verify that `from squadron.pipeline.intelligence import pools` resolves
  without import error
- [ ] **Success criteria:** Both `__init__.py` files exist; `python -c "import squadron.pipeline.intelligence.pools"` exits 0

---

### Task 2: Create test infrastructure (conftest and fixtures)

- [ ] Create `tests/pipeline/intelligence/` directory with `__init__.py`
- [ ] Create `tests/pipeline/intelligence/pools/__init__.py`
- [ ] Create `tests/pipeline/intelligence/pools/conftest.py`
  - [ ] Add `sample_aliases` fixture returning a dict of `ModelAlias` objects
    covering: `minimax`, `glm5`, `kimi25`, `grok-fast`, `opus`, `gpt54`,
    `gemini`, `flash3`, `gemma4`, `qwen36-free` — with varying `cost_tier`
    values (`free`, `cheap`, `moderate`, `expensive`)
  - [ ] Add `builtin_pools_toml` fixture returning the text of
    `src/squadron/data/pools.toml` (read from the actual file, not hardcoded)
  - [ ] Add `tmp_state_file` fixture using `tmp_path` to isolate
    `pool-state.toml` writes
- [ ] **Success criteria:** `pytest tests/pipeline/intelligence/pools/ --collect-only`
  collects 0 tests (file exists, no errors)

---

### Task 3: Implement data models (`models.py`)

- [ ] Create `src/squadron/pipeline/intelligence/pools/models.py`
- [ ] Implement `ModelPool` frozen dataclass:
  - [ ] Fields: `name: str`, `description: str`, `models: list[str]`,
    `strategy: str`, `weights: dict[str, float] | None = None`
- [ ] Implement `SelectionContext` dataclass:
  - [ ] Fields: `pool_name: str`, `action_type: str`,
    `run_id: str | None = None`, `aliases: dict[str, ModelAlias] | None = None`,
    `pool_state: PoolState | None = None`,
    `task_description: str | None = None`
- [ ] Implement `PoolState` dataclass:
  - [ ] Field: `last_index: int = 0`
- [ ] Implement custom exception classes: `PoolValidationError`,
  `PoolNotFoundError`, `StrategyNotFoundError`
- [ ] All classes fully type-annotated; import `ModelAlias` from
  `squadron.models.aliases`
- [ ] **Success criteria:** `from squadron.pipeline.intelligence.pools.models import ModelPool, SelectionContext, PoolState` succeeds; all fields accessible

---

### Task 4: Test data models

- [ ] Create `tests/pipeline/intelligence/pools/test_models.py`
- [ ] Test `ModelPool` instantiation with and without `weights`
- [ ] Test `ModelPool` is frozen (assignment raises `FrozenInstanceError`)
- [ ] Test `SelectionContext` with all optional fields defaulting to `None`
- [ ] Test `PoolState` default `last_index` is 0
- [ ] Test each exception class is a subclass of `Exception`
- [ ] **Success criteria:** All model tests pass; `ruff check` clean

**Commit:** `feat: add ModelPool, SelectionContext, PoolState data models`

---

### Task 5: Implement `PoolStrategy` protocol (`protocol.py`)

- [ ] Create `src/squadron/pipeline/intelligence/pools/protocol.py`
- [ ] Define `PoolStrategy` as a `@runtime_checkable` `Protocol`:
  - [ ] Method: `select(self, pool: ModelPool, context: SelectionContext) -> str`
- [ ] Import `ModelPool`, `SelectionContext` from `.models`
- [ ] **Success criteria:** `isinstance(obj, PoolStrategy)` works at runtime for
  any object implementing `select`

---

### Task 6: Implement cost-tier ordering constant

- [ ] In `src/squadron/pipeline/intelligence/pools/strategies.py`, define
  `COST_TIER_RANK: dict[str, int]` mapping `free→0`, `cheap→1`,
  `moderate→2`, `expensive→3`, `subscription→4`
- [ ] This constant is the single source of truth for tier ordering — no
  magic values scattered in conditionals
- [ ] **Success criteria:** `COST_TIER_RANK["free"] == 0` and
  `COST_TIER_RANK["expensive"] == 3`

---

### Task 7: Implement `random` strategy

- [ ] In `strategies.py`, implement `RandomStrategy` class conforming to
  `PoolStrategy`
- [ ] `select()` returns a uniformly random member alias name from
  `pool.models`
- [ ] Works correctly for a single-member pool
- [ ] **Success criteria:** 100 calls on a 3-member pool produce all three
  members; single-member pool always returns same member

---

### Task 8: Test `random` strategy

- [ ] Create `tests/pipeline/intelligence/pools/test_strategies.py`
- [ ] Test uniform distribution over 200 calls (each member appears > 30 times)
- [ ] Test single-member pool: always returns the one member
- [ ] **Success criteria:** All random strategy tests pass

---

### Task 9: Implement `round-robin` strategy

- [ ] In `strategies.py`, implement `RoundRobinStrategy` conforming to
  `PoolStrategy`
- [ ] `select()` reads `context.pool_state.last_index`, advances by 1 mod
  `len(pool.models)`, updates `context.pool_state.last_index`, returns
  `pool.models[next_index]`
- [ ] If `context.pool_state` is `None`, treat `last_index` as 0
- [ ] Mutates the passed `PoolState` in place (caller is responsible for
  persisting it)
- [ ] Works correctly for a single-member pool (always index 0)
- [ ] **Success criteria:** Three calls on a 3-member pool return all three
  members in order; fourth call returns first member again

---

### Task 10: Test `round-robin` strategy

- [ ] In `test_strategies.py`, test deterministic rotation through all members
- [ ] Test wrap-around on the N+1th call returns first member
- [ ] Test single-member pool: all calls return the same member
- [ ] Test `None` pool_state treated as index 0
- [ ] **Success criteria:** All round-robin strategy tests pass

---

### Task 11: Implement `cheapest` strategy

- [ ] In `strategies.py`, implement `CheapestStrategy` conforming to
  `PoolStrategy`
- [ ] `select()` resolves each member's cost tier from
  `context.aliases[member].cost_tier` using `COST_TIER_RANK`
- [ ] Breaks ties within same tier by `context.aliases[member].pricing.input`
  (lowest wins); if pricing unavailable, breaks randomly
- [ ] If `context.aliases` is `None` or a member is missing, treats that
  member's tier rank as `len(COST_TIER_RANK)` (worst rank)
- [ ] Returns the alias name of the cheapest member
- [ ] **Success criteria:** Given aliases with known tiers, returns the
  cheapest; ties broken correctly

---

### Task 12: Test `cheapest` strategy

- [ ] In `test_strategies.py`, use `sample_aliases` fixture
- [ ] Test: pool with members of distinct tiers returns `free`-tier member
- [ ] Test: same-tier members broken by `pricing.input`
- [ ] Test: member with unknown cost tier ranked worst
- [ ] Test: single-member pool returns that member regardless of tier
- [ ] **Success criteria:** All cheapest strategy tests pass

---

### Task 13: Implement `weighted-random` strategy

- [ ] In `strategies.py`, implement `WeightedRandomStrategy` conforming to
  `PoolStrategy`
- [ ] `select()` uses `pool.weights` for per-member weights; absent members
  default to `1.0`
- [ ] Normalizes weights to probabilities at selection time
- [ ] Returns alias name of selected member
- [ ] Empty `pool.weights` (all defaulting to 1.0) behaves identically to
  uniform random
- [ ] **Success criteria:** Over 1000 calls, a member with weight 2.0 appears
  approximately twice as often as one with weight 1.0 (within 20% tolerance)

---

### Task 14: Test `weighted-random` strategy

- [ ] In `test_strategies.py`, test relative frequency matches weight ratio
  (2:1 weight → ~2:1 frequency, within tolerance)
- [ ] Test: all members absent from `weights` → uniform distribution
- [ ] Test: single-member pool always returns that member
- [ ] **Success criteria:** All weighted-random strategy tests pass

**Commit:** `feat: add PoolStrategy protocol and four built-in strategies`

---

### Task 15: Implement strategy registry

- [ ] In `strategies.py`, create module-level `_STRATEGY_REGISTRY: dict[str, PoolStrategy]`
  populated at import time with keys `"random"`, `"round-robin"`,
  `"cheapest"`, `"weighted-random"` mapping to singleton instances
- [ ] Implement `register_strategy(name: str, strategy: PoolStrategy) -> None`
  for extensibility
- [ ] Implement `get_strategy(name: str) -> PoolStrategy` raising
  `StrategyNotFoundError` for unknown names
- [ ] **Success criteria:** `get_strategy("random")` returns `RandomStrategy`
  instance; `get_strategy("nope")` raises `StrategyNotFoundError`

---

### Task 16: Test strategy registry

- [ ] In `test_strategies.py`, test all four built-in strategies retrievable
  by name
- [ ] Test `get_strategy` with unknown name raises `StrategyNotFoundError`
- [ ] Test `register_strategy` adds a new entry retrievable by `get_strategy`
- [ ] **Success criteria:** All registry tests pass

---

### Task 17: Implement round-robin state persistence (`loader.py` state section)

- [ ] Create `src/squadron/pipeline/intelligence/pools/loader.py`
- [ ] Implement `load_pool_state(pool_name: str) -> PoolState`:
  - [ ] Reads `~/.config/squadron/pool-state.toml`
  - [ ] Missing file or missing pool entry → returns `PoolState(last_index=0)`
  - [ ] Parses `[pools.<pool_name>] last_index` into `PoolState`
- [ ] Implement `save_pool_state(pool_name: str, state: PoolState) -> None`:
  - [ ] Reads current file (or starts empty), updates the pool's entry,
    writes back with `tomli_w`
  - [ ] Creates file and directories if absent
- [ ] Implement `clear_pool_state(pool_name: str) -> None`:
  - [ ] Removes the pool's entry from the file; no-op if absent
- [ ] **Success criteria:** Roundtrip: `save_pool_state("review", PoolState(3))`
  then `load_pool_state("review")` returns `PoolState(last_index=3)`

---

### Task 18: Test round-robin state persistence

- [ ] Create `tests/pipeline/intelligence/pools/test_state.py`
- [ ] Use `tmp_state_file` fixture (monkeypatch config dir to `tmp_path`)
- [ ] Test: `load_pool_state` with missing file returns `PoolState(0)`
- [ ] Test: `load_pool_state` with missing pool entry returns `PoolState(0)`
- [ ] Test: save then load roundtrip preserves `last_index`
- [ ] Test: save updates existing entry without destroying other pools
- [ ] Test: wrap-around: index increments from N-1 to 0 across calls
- [ ] Test: `clear_pool_state` removes entry; subsequent load returns 0
- [ ] Test: `clear_pool_state` on absent entry is a no-op (no exception)
- [ ] **Success criteria:** All state persistence tests pass

**Commit:** `feat: add round-robin state persistence (load/save/clear)`

---

### Task 19: Create built-in `pools.toml`

- [ ] Create `src/squadron/data/pools.toml` with three default pools:
  - [ ] `review`: `strategy = "round-robin"`, models `["minimax", "glm5", "kimi25", "grok-fast"]`
  - [ ] `high`: `strategy = "random"`, models `["opus", "gpt54", "gemini"]`
  - [ ] `cheap`: `strategy = "cheapest"`, models `["minimax", "glm5", "grok-fast", "flash3", "gemma4", "qwen36-free"]`
  - [ ] Each pool has a `description` field
- [ ] File uses `[pools.<name>]` table structure matching the schema in the
  slice design
- [ ] **Success criteria:** File parses without error via
  `python -c "import tomllib; tomllib.load(open('src/squadron/data/pools.toml','rb'))"`

---

### Task 20: Implement pool loader (`loader.py` loading section)

- [ ] In `loader.py`, implement `load_builtin_pools() -> dict[str, ModelPool]`:
  - [ ] Reads `src/squadron/data/pools.toml` via `squadron.data.data_dir()`
  - [ ] Parses each `[pools.*]` table into a `ModelPool`
  - [ ] Validates required fields: `models` (non-empty list), `strategy`
    (registered name)
  - [ ] Validates `weights` keys (if present) are a subset of `models`
  - [ ] Raises `PoolValidationError` with pool name, bad field, and
    diagnostics on failure
- [ ] Implement `load_user_pools() -> dict[str, ModelPool]`:
  - [ ] Reads `~/.config/squadron/pools.toml`; returns `{}` if absent
  - [ ] Same parsing and validation as built-in
- [ ] Implement `get_all_pools() -> dict[str, ModelPool]`:
  - [ ] Merges built-in and user pools; user wins on name collision
- [ ] Implement `get_pool(name: str) -> ModelPool`:
  - [ ] Returns pool from `get_all_pools()`; raises `PoolNotFoundError` if absent

---

### Task 21: Test pool loader

- [ ] Create `tests/pipeline/intelligence/pools/test_loader.py`
- [ ] Test `load_builtin_pools()` against the actual `pools.toml` file
  (use `builtin_pools_toml` fixture) — confirms parser handles production format
- [ ] Test all three default pools load with correct strategy and model counts
- [ ] Test user pool file overrides built-in pool by name
- [ ] Test user pool file absent → `load_user_pools()` returns `{}`
- [ ] Test `PoolValidationError` raised for: unknown strategy, empty models
  list, unknown alias in models (patch `get_all_aliases()` to known set)
- [ ] Test `PoolValidationError` raised for weights keys not in models
- [ ] Test `get_pool` raises `PoolNotFoundError` for unknown pool name
- [ ] **Success criteria:** All loader tests pass

**Commit:** `feat: add pool loader with validation and merge logic`

---

### Task 22: Implement pool member validation against alias registry

- [ ] In `loader.py` validation logic, call `get_all_aliases()` and verify
  each model entry exists as an alias key
- [ ] On failure, raise `PoolValidationError` with: pool name, unknown member
  name, and the list of valid aliases (truncated to first 20 for readability)
- [ ] Validation runs at load time for all pools, not lazily on first use
- [ ] **Success criteria:** Loading a pool with `models = ["nonexistent-alias"]`
  raises `PoolValidationError` naming the bad member

---

### Task 23: Test alias validation

- [ ] In `test_loader.py`, monkeypatch `get_all_aliases()` to a known
  fixture set
- [ ] Test: pool referencing a valid alias → loads without error
- [ ] Test: pool referencing unknown alias → `PoolValidationError` names the
  bad member
- [ ] **Success criteria:** Alias validation tests pass; ruff clean

---

### Task 24: Implement `select_from_pool` convenience wrapper

- [ ] In `loader.py` (or a new `selector.py` if file length warrants), implement:
  ```python
  def select_from_pool(pool: ModelPool) -> str
  ```
  - [ ] Builds `SelectionContext` with `aliases=get_all_aliases()` and
    `pool_state=load_pool_state(pool.name)` for round-robin
  - [ ] Calls `get_strategy(pool.strategy).select(pool, context)`
  - [ ] If strategy is `round-robin`, calls `save_pool_state(pool.name, context.pool_state)` after selection
  - [ ] Returns selected alias name
- [ ] **Success criteria:** `select_from_pool(get_pool("review"))` returns a
  string that is a member of `pools["review"].models`

---

### Task 25: Test `select_from_pool`

- [ ] In `test_loader.py` (or `test_selector.py`), monkeypatch
  `get_all_aliases()` and state file dir
- [ ] Test: round-robin pool — two consecutive calls return different members
  and state file is updated
- [ ] Test: random pool — call returns a member in `pool.models`
- [ ] Test: cheapest pool — call returns cheapest alias per fixture aliases
- [ ] **Success criteria:** All `select_from_pool` tests pass

**Commit:** `feat: add select_from_pool convenience wrapper`

---

### Task 26: Wire up public API in `pools/__init__.py`

- [ ] Edit `src/squadron/pipeline/intelligence/pools/__init__.py` to re-export:
  - [ ] `ModelPool`, `SelectionContext`, `PoolState` from `.models`
  - [ ] `PoolStrategy` from `.protocol`
  - [ ] `PoolValidationError`, `PoolNotFoundError`, `StrategyNotFoundError`
    from `.models`
  - [ ] `load_builtin_pools`, `load_user_pools`, `get_all_pools`, `get_pool`
    from `.loader`
  - [ ] `select_from_pool` from loader/selector
  - [ ] `register_strategy`, `get_strategy` from `.strategies`
  - [ ] `load_pool_state`, `save_pool_state`, `clear_pool_state` from `.loader`
- [ ] **Success criteria:** All symbols in the slice design's Public API Surface
  importable directly from `squadron.pipeline.intelligence.pools`

---

### Task 27: Integration smoke test

- [ ] Run the following in a Python shell or a `tests/pipeline/intelligence/pools/test_integration.py`:
  - [ ] `get_all_pools()` returns dict containing `"review"`, `"high"`, `"cheap"`
  - [ ] `len(get_all_pools()["review"].models) >= 3`
  - [ ] `select_from_pool(get_pool("review"))` returns a string in `["minimax", "glm5", "kimi25", "grok-fast"]`
  - [ ] `select_from_pool(get_pool("cheap"))` returns a string in the cheap pool's models
- [ ] **Success criteria:** Integration test passes with real alias registry

---

### Task 28: Final validation pass

- [ ] Run `pytest tests/pipeline/intelligence/` — all new tests pass
- [ ] Run `pytest` (full suite) — no regressions in existing 623+ tests
- [ ] Run `ruff check src/squadron/pipeline/intelligence/` — clean
- [ ] Run `ruff format src/squadron/pipeline/intelligence/` — no changes
- [ ] Verify all public API symbols importable from
  `squadron.pipeline.intelligence.pools`
- [ ] **Success criteria:** Full suite green; ruff clean; no type errors from `mypy` or `pyright` on new files (if type checking is configured)

**Commit:** `feat: slice 180 — model pool infrastructure and strategies`
