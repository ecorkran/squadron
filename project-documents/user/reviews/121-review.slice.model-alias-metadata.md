---
docType: review
reviewType: slice
slice: model-alias-metadata
project: squadron
verdict: CONCERNS
dateCreated: 20260322
dateUpdated: 20260322
status: not_started
---

# Review: slice — slice 121

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Project Naming Inconsistency

The architecture document defines the project as **"orchestration"** with project structure `orchestration/src/orchestration/`. The slice document references **"squadron"** as the project name, with paths like `squadron.models.aliases` and commands like `sq models`. This inconsistency raises questions:

- Is "squadron" a separate project, a rebrand, or a documentation error?
- The slice's `parent` field references `100-slices.orchestration-v2.md`, indicating intent to integrate with the orchestration architecture
- The architecture document contains no mention of "squadron" or CLI command structure like `sq models`

**Recommendation:** Confirm whether this slice is intended to be part of the `orchestration` project or is a separate effort. If part of orchestration, update the slice to reference the correct project structure and namespace.

### [CONCERN] Architectural Scope Ambiguity

The architecture document focuses on:
- Multi-agent communication and coordination
- Agent lifecycle management (registry, providers)
- Message bus and topology management
- Multiple interface modes (CLI, MCP, REST+WebSocket)

The slice extends **model alias metadata** (privacy flags, cost tiers, per-token pricing) and adds cost estimation. While the architecture does reference `AgentConfig` with provider credentials, **model alias management is not formally defined in the architecture**. This slice is building on slice 120 (model-alias-registry) rather than documented architectural foundations.

This is not a violation—slice 120 may have established this scope—but the architecture document does not provide explicit boundaries for what model management features are in-scope vs. future work.

### [PASS] Dependency Alignment

The slice correctly depends on **slice 120 (model-alias-registry)** as its prerequisite:
> *"Provides `ModelAlias`, `BUILT_IN_ALIASES`, `load_user_aliases()`, `get_all_aliases()`, `sq models` CLI command."*

No other architectural dependencies are introduced. The slice consumes existing interfaces and does not create unexpected coupling to core orchestration components (agent registry, message bus, provider layer).

### [PASS] Backward Compatibility

The design is explicitly backward-compatible:
- All new fields are **optional** (`TypedDict` with `total=False`)
- `resolve_model_alias()` behavior is explicitly unchanged
- Existing `models.toml` files without metadata continue to work
- `estimate_cost()` returns `None` (not 0) when pricing is unavailable, preventing silent failures

### [PASS] Layer Responsibilities

The slice scope respects layer boundaries:

| Responsibility | Layer | Status |
|----------------|-------|--------|
| `ModelAlias`/`ModelPricing` TypedDict | Data model | Appropriate |
| `load_user_aliases()` update | Data access | Appropriate |
| `estimate_cost()` utility | Utility/service | Appropriate |
| `sq models` display update | CLI interface | Appropriate |

The CLI update aligns with the architecture's "CLI-first" principle, though `sq models` itself is not documented in the architecture.

### [PASS] Scope Containment

The "Excluded" section is comprehensive and appropriately bounded:
- Live cost tracking during reviews (future slice)
- Provider API metadata hydration (tracked enhancement)
- Metadata enforcement/validation
- Context window fields

The `estimate_cost()` function is scoped as a pure utility with no side effects, suitable for future integration without architectural risk.

### [PASS] Technical Design Quality

The design decisions are well-justified:
- **`ModelPricing` as separate TypedDict:** Groups related pricing fields, maps cleanly to TOML sub-tables
- **`total=False` for optional fields:** Maintains type safety while allowing backward compatibility
- **`estimate_cost()` returns `None`:** Explicitly handles missing data rather than silently computing 0
- **Compact mode for metadata columns:** Avoids polluting display for users who don't need metadata

### [PASS] Integration Points

The slice provides interfaces for future slices:
> *"Extended `ModelAlias` type with pricing data available for future cost tracking, model comparison, ensemble review cost budgeting"*
> *"estimate_cost() function usable by any future feature that knows token counts (review post-mortem, session summary, cost budget enforcement)"*

This approach is consistent with the architecture's extensibility goals via Agent/AgentProvider Protocols.

### MINOR Missing Architecture References
The slice references `BUILT_IN_ALIASES`, `load_user_aliases()`, and `sq models` CLI command as provided by slice 120, but these components are not documented in the parent architecture (100-arch.orchestration-v2.md). If model alias management is intended to be part of the orchestration architecture, it should be formally defined there. This is a documentation gap rather than an architectural violation by the slice.
