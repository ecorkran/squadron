---
docType: slice-design
slice: model-pool-infrastructure-and-strategies
project: squadron
parent: 180-slices.pipeline-intelligence.md
dependencies: [141-configuration-externalization, 142-model-resolver]
interfaces: [181-pool-resolver-integration-and-cli, 182-fan-out-fan-in-step-type, 185-escalation-behavior]
dateCreated: 20260413
dateUpdated: 20260413
status: complete
---

# Slice Design: Model Pool Infrastructure and Strategies

## Overview

Model pools are named groups of model aliases with a selection strategy
that determines which model to use on each invocation. When a pipeline
step, review, or CLI command references `pool:review` instead of a
single alias like `minimax`, the pool resolver picks one member according
to the pool's strategy — random, round-robin, cheapest, or
weighted-random.

This slice delivers the data model, pool definition schema, built-in
pools, user override loading, four selection strategies behind a
`PoolStrategy` protocol, and per-pool persistent state for round-robin
rotation. It does **not** integrate with the model resolver or expose CLI
commands — that is slice 181.

---

## Value

- **Model diversity for reviews.** A review pool rotates across multiple
  models, reducing the chance that a single model's blind spots become
  systematic. This is the primary motivation.
- **Cost management.** A `cheap` pool directs low-stakes work to the
  cheapest available models. A `cheapest` strategy formalizes this.
- **Foundation for fan-out, escalation, and ensemble.** Slices 181, 182,
  185, and 189 all consume pool infrastructure. Nothing downstream works
  without this slice.

---

## Technical Scope

### In Scope

1. **`ModelPool` dataclass** — name, description, models (list of alias
   names), strategy name, strategy-specific config (weights, etc.).
2. **`PoolStrategy` protocol** — `select(pool, context) -> str` returning
   a chosen alias name. Four built-in implementations: `random`,
   `round-robin`, `cheapest`, `weighted-random`.
3. **`SelectionContext` dataclass** — carries action type requesting the
   model (review, dispatch, etc.), pipeline run ID (for state tracking),
   resolved alias metadata (for cheapest), and pool state (for
   round-robin). Designed to accommodate future capability-match strategy
   via optional `task_description` field.
4. **Pool definition files** — `src/squadron/data/pools.toml` (shipped
   defaults) and `~/.config/squadron/pools.toml` (user overrides), using
   the same layering pattern as model aliases.
5. **Pool loader** — reads, validates, and merges pool definitions.
   Validates that every model entry is a known alias (not another pool)
   at load time.
6. **Round-robin persistent state** —
   `~/.config/squadron/pool-state.toml` tracks the last-selected index
   per pool. Shared across runs (not per-run).
7. **Strategy registry** — maps strategy name strings to `PoolStrategy`
   instances. Extensible for future strategies.
8. **Default pools** — `review` (varied mid-tier models), `high`
   (strongest available), `cheap` (lowest-cost models).

### Out of Scope

- **Model resolver integration** (`pool:` prefix handling) — slice 181.
- **CLI commands** (`sq pools`, `sq pools list`, `sq pools reset`) —
  slice 181.
- **Fan-out model lists from pools** — slice 182.
- **Escalation target pools** — slice 185.
- **Pool analytics / performance tracking** — future work.
- **Capability-match strategy** — future work.

---

## Dependencies

### Prerequisites

- **Slice 141 (Configuration Externalization)** — provides the
  `~/.config/squadron/` directory convention and config loading
  utilities.
- **Slice 142 (Model Resolver)** — provides `resolve_model_alias()` and
  the `ModelAlias` type with `cost_tier` metadata. Pool validation calls
  `get_all_aliases()` to verify model entries exist.

### Interfaces Required

- `squadron.models.aliases.get_all_aliases() -> dict[str, ModelAlias]` —
  pool loader validates model entries against this.
- `squadron.models.aliases.ModelAlias` — `cost_tier` field consumed by
  the `cheapest` strategy.
- `squadron.data.data_dir() -> Path` — locates shipped `pools.toml`.

---

## Architecture

### Component Structure

```
src/squadron/pipeline/intelligence/
├── __init__.py           # NEW — intelligence sub-package
└── pools/
    ├── __init__.py       # NEW — public API re-exports
    ├── models.py         # NEW — ModelPool, SelectionContext, PoolState
    ├── protocol.py       # NEW — PoolStrategy protocol
    ├── strategies.py     # NEW — random, round-robin, cheapest, weighted-random
    └── loader.py         # NEW — TOML loading, validation, merge

src/squadron/data/
├── models.toml           # existing
└── pools.toml            # NEW — shipped default pools

~/.config/squadron/
├── models.toml           # existing — user alias overrides
├── pools.toml            # NEW — user pool overrides
└── pool-state.toml       # NEW — round-robin rotation state
```

Pool logic lives in `src/squadron/pipeline/intelligence/pools/`,
following the architecture's package structure for all 180-band
intelligence capabilities. The `intelligence/` package is the shared
home for pools, convergence, escalation, triage, and persistence —
all pipeline-layer concerns that consume model metadata but are
orchestrated by the pipeline executor. The `pools/` sub-package
imports from `squadron.models.aliases` for alias resolution and
metadata but is not itself part of the models layer.

### Data Flow

```
pools.toml (built-in) ──┐
                         ├── pool loader ──> dict[str, ModelPool]
pools.toml (user) ──────┘        │
                                 │  validates models against
                                 │  get_all_aliases()
                                 ▼
                          ModelPool instances
                                 │
                          PoolStrategy.select()
                                 │
                                 ▼
                          selected alias name (str)
                                 │
                          (slice 181 resolves alias → model_id, profile)
```

### State Management

**Round-robin state** is the only persistent state in this slice.

- File: `~/.config/squadron/pool-state.toml`
- Format: `[pools.<name>]` with `last_index = <int>`
- Global scope: shared across all pipeline runs, all sessions
- Reset: clearing a pool's entry or deleting the file (slice 181 adds
  `sq pools reset`)
- Concurrency: TOML read → increment → write is not atomic. Acceptable
  for a single-user CLI tool. If concurrent runs rotate the same pool,
  they may occasionally pick the same model — this is a benign race, not
  a correctness bug.

---

## Technical Decisions

### Pool Models Are Alias Names, Not Raw Model IDs

Pool `models` entries reference alias names (`minimax`, `glm5`), not raw
model IDs (`minimax/minimax-m2.7`). This means:
- Pools automatically pick up alias changes (profile, model ID, pricing)
- Validation is a simple check against `get_all_aliases()`
- Resolution is recursive: pool → alias name → (model_id, profile)

Pools cannot reference other pools. This prevents circular references
and keeps resolution a single step. If a use case for nested pools
emerges, it can be added later with cycle detection.

### Strategy Is Per-Pool, Not Global

Each pool declares its own strategy. A `review` pool might use
`round-robin` while a `cheap` pool uses `cheapest`. There is no global
default strategy — each pool must declare one. This avoids implicit
behavior and keeps pool definitions self-contained.

### Cost Tier Ordering for `cheapest` Strategy

The `cheapest` strategy uses the `cost_tier` field from alias metadata.
Ordering:

| cost_tier      | rank (lower = cheaper) |
|----------------|----------------------|
| `free`         | 0                    |
| `cheap`        | 1                    |
| `moderate`     | 2                    |
| `expensive`    | 3                    |
| `subscription` | 4                    |

Ties within the same tier are broken by `pricing.input` (lowest wins).
If pricing data is unavailable, ties are broken randomly. The tier
ordering is defined as a constant (enum or dict), not scattered across
conditionals.

### Weighted-Random Weights Are Per-Member

The `weighted-random` strategy accepts per-member weights in the pool
definition. Members without explicit weights default to 1.0. Weights are
normalized to probabilities at selection time.

```toml
[pools.review]
strategy = "weighted-random"
models = ["minimax", "glm5", "kimi25"]

[pools.review.weights]
minimax = 2.0
glm5 = 1.0
kimi25 = 1.0
```

### Patterns and Conventions

- **Module location:** `src/squadron/pipeline/intelligence/pools/` —
  per the architecture's package structure for 180-band capabilities.
- **Loader pattern:** Follows `aliases.py` exactly — `load_builtin_pools()`,
  `load_user_pools()`, `get_all_pools()` with user-wins-on-name-collision
  merge.
- **Validation pattern:** Fail loudly at load time. If a pool references
  a non-existent alias, raise `PoolValidationError` with the pool name,
  bad member, and available aliases.
- **Strategy registration:** Module-level dict mapping strategy names to
  `PoolStrategy` instances, populated at import time. Same pattern as
  action/step registries.

---

## Implementation Details

### Data Model

```python
@dataclass(frozen=True)
class ModelPool:
    """A named group of model aliases with a selection strategy."""
    name: str
    description: str
    models: list[str]         # alias names, validated at load time
    strategy: str             # strategy name (key in strategy registry)
    weights: dict[str, float] | None = None  # for weighted-random

@dataclass
class SelectionContext:
    """Metadata passed to PoolStrategy.select()."""
    pool_name: str
    action_type: str              # "review", "dispatch", etc.
    run_id: str | None = None     # pipeline run ID for state tracking
    aliases: dict[str, ModelAlias] | None = None  # resolved alias metadata
    pool_state: PoolState | None = None           # round-robin state
    task_description: str | None = None           # future: capability-match

@dataclass
class PoolState:
    """Persistent state for a single pool."""
    last_index: int = 0
```

### PoolStrategy Protocol

```python
@runtime_checkable
class PoolStrategy(Protocol):
    """Selects one model from a pool."""

    def select(self, pool: ModelPool, context: SelectionContext) -> str:
        """Return the alias name of the selected model."""
        ...
```

The protocol matches the architecture's definition. Strategy
registration uses the strategy name string as the registry key —
strategies do not need a `name` property.

### Built-In Strategies

| Strategy | Behavior | State |
|----------|----------|-------|
| `random` | Uniform random selection from members | Stateless |
| `round-robin` | Deterministic rotation through members in order | Persistent index in `pool-state.toml` |
| `cheapest` | Select member with lowest cost tier (ties broken by `pricing.input`, then random) | Stateless |
| `weighted-random` | Random selection weighted by per-member weights (default 1.0) | Stateless |

### Pool Definition Schema (TOML)

```toml
# src/squadron/data/pools.toml

[pools.review]
description = "Varied mid-tier models for review diversity"
strategy = "round-robin"
models = ["minimax", "glm5", "kimi25", "grok-fast"]

[pools.high]
description = "Strongest available models"
strategy = "random"
models = ["opus", "gpt54", "gemini"]

[pools.cheap]
description = "Lowest-cost models for bulk or low-stakes work"
strategy = "cheapest"
models = ["minimax", "glm5", "grok-fast", "flash3", "gemma4", "qwen36-free"]
```

User file at `~/.config/squadron/pools.toml` uses the identical format.
User pools override built-in pools by name.

### Pool Loader Validation

At load time, the pool loader:

1. Parses TOML and extracts `[pools.*]` tables
2. Validates required fields: `models` (non-empty list of strings),
   `strategy` (string matching a registered strategy)
3. Validates every model entry is a known alias via `get_all_aliases()`
4. Validates `weights` keys (if present) are a subset of `models`
5. Raises `PoolValidationError` with specific diagnostics on failure

Validation runs eagerly — all pools are validated on load, not on first
use. This matches the pipeline loader's eager validation pattern.

### Round-Robin State File

```toml
# ~/.config/squadron/pool-state.toml

[pools.review]
last_index = 2
```

- Read on selection, write after selection
- Missing file or missing pool entry → start at index 0
- Index wraps via modulo: `next_index = (last_index + 1) % len(pool.models)`
- Written with `tomli_w` (already a project dependency for config
  writing)

### Public API Surface

```python
# Module: squadron.pipeline.intelligence.pools

# Data model
class ModelPool: ...
class SelectionContext: ...
class PoolState: ...
class PoolStrategy(Protocol): ...

# Errors
class PoolValidationError(Exception): ...
class PoolNotFoundError(Exception): ...
class StrategyNotFoundError(Exception): ...

# Loader
def load_builtin_pools() -> dict[str, ModelPool]: ...
def load_user_pools() -> dict[str, ModelPool]: ...
def get_all_pools() -> dict[str, ModelPool]: ...
def get_pool(name: str) -> ModelPool: ...  # raises PoolNotFoundError

# Selection
def select_from_pool(pool: ModelPool) -> str: ...  # convenience wrapper

# Strategy registry
def register_strategy(strategy: PoolStrategy) -> None: ...
def get_strategy(name: str) -> PoolStrategy: ...  # raises StrategyNotFoundError

# State management
def load_pool_state(pool_name: str) -> PoolState: ...
def save_pool_state(pool_name: str, state: PoolState) -> None: ...
def clear_pool_state(pool_name: str) -> None: ...
```

---

## Integration Points

### Provides to Other Slices

- **Slice 181 (Pool Resolver):** `get_pool()`, `select_from_pool()`,
  `get_all_pools()`, `clear_pool_state()`. The resolver calls
  `select_from_pool()` when it encounters a `pool:` prefix, then
  resolves the returned alias name through the existing alias system.
- **Slice 182 (Fan-Out):** `ModelPool.models` list for enumerating
  models to fan out across. Fan-out doesn't use the selection strategy —
  it uses all models in the pool.
- **Slice 185 (Escalation):** `select_from_pool()` for drawing a fresh
  model on each escalation attempt.

### Consumes from Other Slices

- **Slice 141 (Config):** `~/.config/squadron/` directory convention.
- **Slice 142 (Resolver):** `get_all_aliases()` and `ModelAlias` type
  for member validation and cost-tier resolution.

---

## Success Criteria

### Functional Requirements

- [ ] `ModelPool` dataclass correctly represents pool definitions loaded
  from TOML.
- [ ] Four strategies (`random`, `round-robin`, `cheapest`,
  `weighted-random`) each produce valid alias names from a pool.
- [ ] `round-robin` rotates deterministically through members and
  persists state to `pool-state.toml` across calls.
- [ ] `cheapest` selects based on `cost_tier` ordering, with
  `pricing.input` as tiebreaker.
- [ ] `weighted-random` respects per-member weights and defaults absent
  weights to 1.0.
- [ ] Pool loader validates model entries against known aliases and
  raises `PoolValidationError` for unknown entries.
- [ ] Pool loader validates strategy names against the strategy registry.
- [ ] User pools in `~/.config/squadron/pools.toml` override built-in
  pools by name.
- [ ] Default pools (`review`, `high`, `cheap`) ship in
  `src/squadron/data/pools.toml` and load correctly.

### Technical Requirements

- [ ] All public functions and classes have type annotations.
- [ ] Unit tests for each strategy (including edge cases: single-member
  pool, empty weights, unknown cost tier).
- [ ] Unit tests for pool loading: built-in, user override, merge,
  validation errors.
- [ ] Unit tests for round-robin state persistence: initial state,
  increment, wrap-around, missing file.
- [ ] Tests use real `pools.toml` fixture content (not invented formats)
  to validate the parser against production input.
- [ ] `ruff` clean, no type errors.

---

## Verification Walkthrough

> Note: this walkthrough will be refined after implementation. Some
> commands depend on slice 181 (CLI) and are marked accordingly.

### Scenario 1: Unit Tests Pass

```bash
pytest tests/pipeline/intelligence/test_pools.py -v
```

All pool infrastructure tests pass — strategies, loader, validation,
state persistence.

### Scenario 2: Default Pools Load

```python
from squadron.pipeline.intelligence.pools import get_all_pools

pools = get_all_pools()
assert "review" in pools
assert "high" in pools
assert "cheap" in pools
assert len(pools["review"].models) >= 3
```

### Scenario 3: Round-Robin State Persists

```python
from squadron.pipeline.intelligence.pools import get_pool, select_from_pool

pool = get_pool("review")
first = select_from_pool(pool)
second = select_from_pool(pool)
assert first != second  # rotated to next member
# State file exists at ~/.config/squadron/pool-state.toml
```

### Scenario 4: Validation Rejects Bad Members

```python
from squadron.pipeline.intelligence.pools import ModelPool, PoolValidationError

# A pool referencing a non-existent alias
bad_pool_toml = """
[pools.bad]
strategy = "random"
members = ["nonexistent-alias"]
"""
# Loading this raises PoolValidationError
```

### Scenario 5: Pool Listing (requires slice 181)

```bash
sq pools list
# Shows: review (round-robin, 4 members), high (random, 3 members), cheap (cheapest, 6 members)
```

---

## Implementation Notes

### Development Approach

1. **Data model first** — `ModelPool`, `SelectionContext`, `PoolState`
   dataclasses + `PoolStrategy` protocol.
2. **Strategy implementations** — four strategies with unit tests for
   each.
3. **Pool loader** — TOML parsing, validation, merge. Tests with fixture
   files.
4. **State persistence** — `pool-state.toml` read/write for round-robin.
5. **Default pools file** — `src/squadron/data/pools.toml` with sensible
   defaults.
6. **Integration smoke test** — `get_all_pools()` +
   `select_from_pool()` end-to-end.

### Testing Strategy

- **Strategy tests:** Parametrized across strategies. Each test covers
  normal selection, single-member pool, and strategy-specific edge cases
  (e.g., round-robin wrap, cheapest tie-breaking, weighted distribution).
- **Loader tests:** Real TOML fixtures. Test built-in loading, user
  override merge, and each validation failure mode.
- **State tests:** Use `tmp_path` for state file isolation. Test initial
  state, increment, wrap, missing file, and corrupt file recovery.
- **No mocking of alias loading** in pool validation tests — use a
  fixture that patches `get_all_aliases()` to return a known set, but
  test the actual TOML parsing against the shipped `pools.toml` file.
