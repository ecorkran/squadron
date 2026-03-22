---
docType: review
reviewType: arch
slice: model-alias-registry
project: squadron
verdict: PASS
dateCreated: 20260321
dateUpdated: 20260321
---

# Review: arch — slice 120

**Verdict:** PASS
**Model:** opus

## Findings

### [PASS] — Alignment with Multi-Provider Architecture

The architecture document establishes "multi-provider as architectural constraint" as a key decision and lists planned providers (OpenAI, OpenRouter, local models) alongside the primary SDK path. The alias registry directly serves this goal by making multi-provider model selection ergonomic. The `resolve_model_alias()` function replaces brittle pattern-matching (`_infer_profile_from_model()`) with a data-driven, user-extensible registry — this is a clear improvement in line with the architecture's extensibility principle.

### [PASS] — Correct Layer Placement

The architecture defines four layers: Core Engine, Agent Provider Layer, Interface Layer, and Frontend. The alias registry (`src/squadron/models/aliases.py`) sits as shared infrastructure consumed by the Interface Layer (CLI commands, review routing). It does not leak into or depend on the Core Engine or Agent Provider Layer. The new `sq model list` CLI command follows the CLI-first principle from the architecture.

### [PASS] — Dependency Direction

The slice correctly depends on slice 119 (Review Provider & Model Selection, complete) and is consumed by slice 131 (Ensemble Review). The alias registry feeds into `_resolve_model()` and `_resolve_profile()` — both review-layer functions — without creating reverse dependencies. The architecture's invariant that "the core engine never depends on provider internals" is preserved.

### [PASS] — Agent Protocol Bypass is Consistent

The slice continues the precedent set by slice 119: reviews are one-shot request/response operations that bypass the Agent Protocol and call provider APIs directly. The architecture defines the Agent Protocol for agent lifecycle management (handle_message, shutdown, state tracking). Using it for single API calls would be over-engineering. This is explicitly documented in slice 119's design rationale and the current slice correctly inherits that decision.

### [CONCERN] — Dual Scope May Warrant Separation

The slice bundles two distinct capabilities: (1) model alias resolution and (2) content injection for non-SDK reviews. These are described as sharing a "root cause" (non-SDK review path wasn't designed for usability), which is a reasonable framing. However, they are technically independent — alias resolution works without content injection and vice versa. If either encounters implementation complexity (especially content injection with its size limits, git diff execution, and truncation logic), the combined scope could delay the simpler alias work. The implementation order (section at bottom) does treat them as sequential steps, which mitigates this risk. **Recommendation:** Consider splitting if implementation reveals unexpected complexity in either half.

### [CONCERN] — Double Alias Resolution in Data Flow

The data flow diagram shows `resolve_model_alias()` being called twice per review command — once in `_resolve_model()` and once in `_resolve_profile()`:

```
→ _resolve_model("kimi25") → resolve_model_alias("kimi25") → ("moonshotai/kimi-k2", "openrouter")
→ _resolve_profile(None, template, "kimi25") → resolve_model_alias("kimi25") → profile="openrouter"
```

The raw alias string `"kimi25"` is passed to `_resolve_profile()` rather than the already-resolved `("moonshotai/kimi-k2", "openrouter")` tuple. This means the alias lookup happens redundantly. While functionally correct and cheap (dict lookup + TOML file read, likely cached), it suggests the resolution should happen once at a higher level with the result tuple threaded through. This is a minor design inefficiency, not a violation.

### [PASS] — Configuration File Conventions

The new `~/.config/squadron/models.toml` follows the established pattern of `~/.config/squadron/providers.toml` (slice 113) and `~/.config/squadron/templates/` (slice 119). TOML format is consistent with existing config files. User overrides of built-in defaults by name matches the template override pattern from slice 119.

### [PASS] — Content Injection Respects Provider Boundaries

The architecture clearly distinguishes SDK agents (autonomous, file/code access) from API agents (conversational, no tool access). Content injection works at the review client level (`review_client.py`), enriching the prompt *before* it reaches the API — it does not attempt to give non-SDK providers tool capabilities. This correctly respects the architectural boundary while pragmatically solving the usability gap. The explicit exclusion of "tool use for non-SDK providers" confirms appropriate scope control.

### [PASS] — Size Limits Are Reasonable

The 100KB per-file and 500KB total injection limits provide a safety boundary against token cost explosion. The truncation behavior (clear message, warning log) is well-specified. The known limitations section appropriately notes that content injection makes non-SDK reviews "workable, not equivalent" to SDK reviews.

### [PASS] — Future Slice Compatibility

The slice correctly identifies itself as a prerequisite for Ensemble Review (131) and excludes the Anthropic API provider (123). The `resolve_model_alias()` API is generic enough to be consumed by future `sq spawn --model` commands (explicitly noted in the module location rationale), supporting the architecture's multi-provider agent spawning use case.
