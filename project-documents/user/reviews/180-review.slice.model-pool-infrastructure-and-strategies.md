---
docType: review
layer: project
reviewType: slice
slice: model-pool-infrastructure-and-strategies
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/180-slice.model-pool-infrastructure-and-strategies.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260413
dateUpdated: 20260413
findings:
  - id: F001
    severity: fail
    category: architecture-boundaries
    summary: "Module placed in models layer, not pipeline/intelligence layer"
    location: src/squadron/models/pools.py
  - id: F002
    severity: concern
    category: interface-contract
    summary: "TOML pool field name mismatch: `members` vs `models`"
    location: src/squadron/data/pools.toml
  - id: F003
    severity: concern
    category: interface-contract
    summary: "SelectionContext fields diverge from architecture specification"
    location: src/squadron/models/pools.py
  - id: F004
    severity: note
    category: scope
    summary: "PoolStrategy gains a `name` property not in the architecture protocol"
    location: src/squadron/models/pools.py
  - id: F005
    severity: pass
    category: scope
    summary: "Scope boundaries are correctly observed"
  - id: F006
    severity: pass
    category: state-management
    summary: "Round-robin state location matches architecture's open-question resolution"
    location: ~/.config/squadron/pool-state.toml
  - id: F007
    severity: pass
    category: dependencies
    summary: "Dependency directions are correct"
---

# Review: slice — slice 180

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [FAIL] Module placed in models layer, not pipeline/intelligence layer

The architecture document explicitly defines the package structure for all pool infrastructure:

```
src/squadron/pipeline/intelligence/pools/
├── protocol.py
├── strategies.py
├── models.py
└── loader.py
```

The slice places everything in `src/squadron/models/pools.py`, justifying this as "pools are model infrastructure, not pipeline infrastructure." This rationale contradicts the architecture, which unambiguously places pools inside `pipeline/intelligence/` alongside convergence, escalation, and persistence — framing them as pipeline-layer concerns that happen to use model metadata, not model-layer concerns. Downstream slices 181, 182, and 185 will import from whichever location is established here; a location change after they are written will require coordinated updates. The architecture's placement should be followed unless the parent slice plan explicitly overrides it.

### [CONCERN] TOML pool field name mismatch: `members` vs `models`

The architecture document uses `models` as the list field in pool definitions:

```toml
[pools.review]
strategy = "random"
models = ["minimax2.7", "sonnet", "gemma3", "gpt54-nano"]
```

The slice uses `members` throughout — in the TOML schema, the `ModelPool` dataclass, and all references. This is a schema-level incompatibility: any user who writes `pools.toml` following the architecture doc's examples will have their file silently rejected or produce empty member lists. One of these must be authoritative. If `members` is the chosen name (it is arguably clearer), the architecture doc should be updated and the discrepancy should be noted in the parent slice plan.

### [CONCERN] SelectionContext fields diverge from architecture specification

The architecture describes `SelectionContext` as carrying:
- Action type requesting the model (review, dispatch, etc.)
- Pipeline run ID (for round-robin state)
- Task description (for future capability-match)

The slice defines it as:
```python
@dataclass
class SelectionContext:
    pool_name: str
    aliases: dict[str, ModelAlias]   # full alias metadata for members
    pool_state: PoolState            # round-robin index
```

These are almost entirely different. The architecture's fields support the future `capability-match` strategy (action type, task description) and pass run identity for state tracking. The slice's fields are implementation-internal plumbing (aliases for cheapest, pool_state for round-robin) that arguably belong inside the strategy implementations rather than in the shared context object. The architecture's context design should be followed, with implementation-specific data passed as strategy constructor arguments or loaded lazily inside each strategy. Departing from the architecture's interface here will require changes when `capability-match` or action-type-aware strategies are added in future slices.

### [NOTE] PoolStrategy gains a `name` property not in the architecture protocol

The slice adds a `name: str` property to the `PoolStrategy` protocol that is absent from the architecture's definition. This is a reasonable addition for registry lookups and debug logging, but it is an unacknowledged deviation. If the architecture's protocol is considered the contract for how 140 registers strategies, this addition should be noted in the parent slice plan or architecture addendum so consuming slices know to expect it.

### [PASS] Scope boundaries are correctly observed

The slice correctly excludes model resolver integration (`pool:` prefix handling), CLI commands, fan-out enumeration, and escalation target handling — all deferred to slices 181, 182, and 185 as the architecture intends. The no-nested-pools constraint matches the architecture's rationale for safe single-step resolution.

### [PASS] Round-robin state location matches architecture's open-question resolution

The architecture raises as an open question where round-robin state should live and suggests `~/.config/squadron/pool-state.toml` with global-per-pool scope, reset via `sq pools reset`. The slice implements exactly this, including the correct acknowledgment that the non-atomic read-increment-write is a benign race for a single-user CLI tool.

### [PASS] Dependency directions are correct

The slice correctly depends on slices 141 (config directory convention) and 142 (alias resolver), and correctly provides to slices 181, 182, and 185. The `get_all_aliases()` → member validation dependency chain is architecturally sound and matches the architecture's description of pool validation.
