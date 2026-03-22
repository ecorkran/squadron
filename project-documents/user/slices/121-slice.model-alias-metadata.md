---
docType: slice-design
slice: model-alias-metadata
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [model-alias-registry]
interfaces: []
dateCreated: 20260322
dateUpdated: 20260322
status: not_started
---

# Slice Design: Model Alias Metadata

## Overview

Extend the `ModelAlias` type with optional metadata fields so users and built-in aliases can carry information about privacy, pricing, and notes. Update `sq models` to display metadata columns. Ship curated metadata — including per-token pricing — for all built-in aliases. The pricing data enables future cost estimation ("how much did that kimi25 review just cost me?").

## Value

- **Informed model selection.** `sq models` shows at a glance which providers train on prompts, relative cost tier, and useful notes.
- **Cost estimation foundation.** Per-token pricing data (input, output, cache read, cache write) enables future features like post-review cost reporting and model cost/quality trade-off analysis.
- **Privacy awareness.** The `private` field lets users quickly identify which models/providers may train on their input — important when reviewing proprietary code.
- **Low friction.** All metadata fields are optional. Existing user `models.toml` files continue to work unchanged. Nothing fails if pricing is null.

## Technical Scope

### Included

- Extend `ModelAlias` TypedDict with optional `private`, `cost_tier`, `notes`, and `pricing` fields
- `pricing` is a nested structure with per-token costs: `input`, `output`, `cache_read`, `cache_write` (all per 1M tokens, USD)
- Update `BUILT_IN_ALIASES` with curated metadata and pricing for all 12 defaults
- Update `models.toml` parsing to read metadata from both inline table and full table TOML syntax
- Update `sq models` table to show metadata columns
- `estimate_cost()` utility function: given token counts and a model alias, returns estimated cost in USD
- Tests for new fields, parsing, display, and cost estimation

### Excluded

- Live cost tracking during reviews (needs token counting integration — future slice)
- Provider API metadata hydration (auto-fetching pricing from APIs) — tracked as future enhancement in slice plan
- Validation or enforcement based on metadata (e.g., blocking reviews on non-private models)
- Metadata filtering in `sq models` (e.g., `--private-only`) — future if needed
- Context window / max output fields (useful but not needed for cost estimation — can be added later)

## Dependencies

### Prerequisites

- **Model Alias Registry (120)** — complete. Provides `ModelAlias`, `BUILT_IN_ALIASES`, `load_user_aliases()`, `get_all_aliases()`, `sq models` CLI command.

### External Packages

- None new. `tomllib` (stdlib) already used.

## Technical Decisions

### Extended ModelAlias Type

```python
class ModelPricing(TypedDict, total=False):
    """Per-token pricing for a model, all values in USD per 1M tokens."""
    input: float        # Input token price per 1M tokens
    output: float       # Output token price per 1M tokens
    cache_read: float   # Cached input read price per 1M tokens
    cache_write: float  # Cache write price per 1M tokens

class ModelAlias(TypedDict, total=False):
    """A model alias mapping a short name to a profile and full model ID."""
    profile: str          # Required (validated at load time)
    model: str            # Required (validated at load time)
    private: bool         # Whether the provider states they don't train on input
    cost_tier: str        # "free" | "cheap" | "moderate" | "expensive" | "subscription"
    notes: str            # Free-text (context window, speed, etc.)
    pricing: ModelPricing # Per-token cost data for cost estimation
```

Using `total=False` with `TypedDict` makes all fields optional by default. Since `profile` and `model` are always required in practice, validation stays in `load_user_aliases()` where it already checks for their presence. The type change is backward-compatible — existing code that only accesses `["profile"]` and `["model"]` continues to work.

`ModelPricing` is a separate TypedDict rather than flattened into `ModelAlias` because:
- It maps naturally to a TOML sub-table: `[aliases.kimi25.pricing]`
- It groups related values that are always used together (cost estimation)
- It avoids polluting the top-level alias namespace with four similarly-named fields

All pricing fields are optional within the dict. A model can have `input` and `output` but no cache pricing. `estimate_cost()` handles missing fields gracefully — returns `None` for components it can't calculate.

### cost_tier Values

Plain strings rather than an enum. The five values (`free`, `cheap`, `moderate`, `expensive`, `subscription`) are display labels, not routing logic. No code branches on them.

`cost_tier` is a human-friendly summary. `pricing` is the machine-readable data. They coexist intentionally — `cost_tier` is for quick visual scanning in `sq models`, `pricing` is for computation. Neither requires the other.

### Cost Estimation Utility

```python
def estimate_cost(
    alias_name: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float | None:
    """Estimate USD cost for a model given token counts.

    Returns None if the alias has no pricing data or insufficient
    pricing fields for the calculation.
    """
```

This is a pure function that looks up the alias, reads its pricing, and multiplies. No side effects, no API calls. It returns `None` (not 0.0) when pricing data is missing — the caller can decide whether to show "unknown" or skip cost display.

For subscription-based models (SDK agents on Max), `estimate_cost()` returns `None` — there is no per-token cost to estimate.

This function is the foundation. Future slices can use it to:
- Print cost after a review: "Estimated cost: $0.03 (12K input, 2K output @ kimi25 rates)"
- Compare models: "opus: subscription, kimi25: ~$0.04, gpt54-nano: ~$0.01"
- Track cumulative cost across a session

### TOML Format Support

Current inline syntax continues to work for aliases without metadata:

```toml
[aliases]
opus = { profile = "sdk", model = "claude-opus-4-6" }
```

Metadata with pricing uses full table sections (recommended for readability):

```toml
[aliases.kimi25]
profile = "openrouter"
model = "moonshotai/kimi-k2.5"
private = true
cost_tier = "cheap"
notes = "1M context"

[aliases.kimi25.pricing]
input = 5.0
output = 25.0
cache_read = 0.50
cache_write = 6.25
```

Or inline (compact, less readable with pricing):

```toml
[aliases]
kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2.5", private = true, cost_tier = "cheap", pricing = { input = 5.0, output = 25.0 } }
```

Both are standard TOML and parse correctly via `tomllib`. The `pricing` sub-table maps directly to the `ModelPricing` TypedDict.

### Built-in Metadata

Curated metadata for all 12 default aliases. Pricing sourced from provider pricing pages as of 2026-03-22.

| Alias | private | cost_tier | input $/1M | output $/1M | cache_read | cache_write | notes |
|-------|---------|-----------|-----------|------------|------------|-------------|-------|
| opus | true | subscription | — | — | — | — | Max sub |
| sonnet | true | subscription | — | — | — | — | Max sub |
| haiku | true | subscription | — | — | — | — | Max sub |
| gpt54 | true | expensive | 2.50 | 10.00 | 0.63 | 2.50 | Frontier |
| gpt54-mini | true | moderate | 0.40 | 1.60 | 0.10 | 0.40 | Balanced |
| gpt54-nano | true | cheap | 0.10 | 0.40 | 0.03 | 0.10 | Lightweight |
| codex | true | expensive | 2.50 | 10.00 | — | — | Code-specialized |
| gemini | true | free | 0.00 | 0.00 | 0.00 | 0.00 | Free tier |
| flash3 | true | free | 0.00 | 0.00 | 0.00 | 0.00 | Fast, free |
| kimi25 | true | cheap | 5.00 | 25.00 | 0.50 | 6.25 | 1M context |
| minimax | true | cheap | 1.10 | 4.40 | — | — | |
| glm5 | true | cheap | 0.50 | 2.00 | — | — | |

**Pricing notes:**
- SDK models (opus, sonnet, haiku) have no pricing — they use Max subscription. `pricing` is omitted entirely (not zeroed).
- `—` means the field is absent, not zero. Zero means "free" (gemini, flash3).
- Values are USD per 1M tokens, matching the convention used by OpenRouter, OpenAI, and Anthropic pricing pages.
- These are point-in-time snapshots. Future slice (Provider API metadata hydration) could auto-update from APIs.

**`private` semantics:** `true` means the provider states they do not train on API input. `false` means the provider may train on input or their policy is unclear. All current built-in providers are `true` — their API terms prohibit training on API traffic.

**`cost_tier` = `"subscription"`:** Claude models via SDK use the Max subscription, not per-token billing. This is a meaningful distinction from "free" or "expensive" and warrants its own tier value.

### Display in `sq models`

Add metadata columns to the table: `Private`, `Cost`, `In $/1M`, `Out $/1M`, `Notes`.

```
$ sq models
┏━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Alias     ┃ Profile     ┃ Model ID                      ┃ Private ┃ Cost ┃ In $/1M ┃ Out $/1M┃ Notes        ┃ Source ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━┩
│ opus      │ sdk         │ claude-opus-4-6               │ yes     │ sub  │         │         │ Max sub      │        │
│ sonnet    │ sdk         │ claude-sonnet-4-6             │ yes     │ sub  │         │         │ Max sub      │        │
│ gpt54     │ openai      │ gpt-5.4                       │ yes     │ $$$  │ $2.50   │ $10.00  │ Frontier     │        │
│ gpt54-nano│ openai      │ gpt-5.4-nano                  │ yes     │ $    │ $0.10   │ $0.40   │ Lightweight  │        │
│ kimi25    │ openrouter  │ moonshotai/kimi-k2.5          │ yes     │ $    │ $5.00   │ $25.00  │ 1M context   │        │
│ gemini    │ gemini      │ gemini-3.1-pro-preview-...    │ yes     │ free │ $0.00   │ $0.00   │ Free tier    │        │
│ deepseek  │ openrouter  │ deepseek/deepseek-r2          │ no      │ $    │ $0.14   │ $2.18   │              │ (user) │
└───────────┴─────────────┴───────────────────────────────┴─────────┴──────┴─────────┴─────────┴──────────────┴────────┘
```

**Display formatting:**
- `private`: `"yes"` / `"no"` / blank (if unset)
- `cost_tier`: Short display labels: `"free"` → `"free"`, `"cheap"` → `"$"`, `"moderate"` → `"$$"`, `"expensive"` → `"$$$"`, `"subscription"` → `"sub"`, unset → blank
- `In $/1M`, `Out $/1M`: formatted as `$X.XX` from `pricing.input` / `pricing.output`. Blank if pricing absent.
- `notes`: Displayed as-is, truncated to ~30 chars if needed
- Cache pricing (cache_read, cache_write) not shown in table — available for `estimate_cost()` and future detailed views like `sq models --detail kimi25`

### Compact Mode

When no aliases have metadata (e.g., user has only basic aliases and no built-ins would show metadata), the metadata columns are hidden automatically. This keeps the display clean for users who don't care about metadata.

Implementation: check if any alias in the merged set has at least one metadata field set. If none do, render the table without metadata columns. This applies to the entire table, not per-row.

## Data Flow

### Alias Loading with Metadata

```
load_user_aliases()
  → read models.toml
  → for each [aliases.X] or inline table:
    → extract profile, model (required — skip with warning if missing)
    → extract private, cost_tier, notes (optional — omit if absent)
    → extract pricing sub-table (optional — omit if absent)
      → if pricing present, extract input, output, cache_read, cache_write (all optional floats)
    → build ModelAlias dict
  → return dict
```

### Display

```
sq models
  → get_all_aliases()  (merges built-in + user)
  → check if any alias has metadata fields
  → if yes: render full table (Alias, Profile, Model ID, Private, Cost, In $/1M, Out $/1M, Notes, Source)
  → if no: render compact table (Alias, Profile, Model ID, Source)
```

### Cost Estimation

```
estimate_cost("kimi25", input_tokens=15000, output_tokens=3000)
  → resolve alias → get pricing → { input: 5.0, output: 25.0, ... }
  → cost = (15000 / 1_000_000 * 5.0) + (3000 / 1_000_000 * 25.0)
  → return 0.15
```

## Integration Points

### Provides to Other Slices

- Extended `ModelAlias` type with pricing data available for future cost tracking, model comparison, ensemble review cost budgeting
- `estimate_cost()` function usable by any future feature that knows token counts (review post-mortem, session summary, cost budget enforcement)
- Metadata accessible via `get_all_aliases()` — no new API needed

### Consumes from Other Slices

- `ModelAlias`, `BUILT_IN_ALIASES`, `load_user_aliases()`, `get_all_aliases()` from slice 120

## Success Criteria

### Functional Requirements

- `sq models` shows Private, Cost, In $/1M, Out $/1M, and Notes columns for built-in aliases
- All 12 built-in aliases have curated metadata including pricing where applicable
- User can add metadata and pricing to aliases in `models.toml`
- User aliases without metadata display with blank metadata columns
- Existing `models.toml` files without metadata fields continue to work
- `resolve_model_alias()` behavior unchanged — metadata does not affect resolution
- `estimate_cost()` returns correct USD estimate given token counts and an alias with pricing
- `estimate_cost()` returns `None` for aliases without pricing data (subscription models, unknown)

### Technical Requirements

- `ModelPricing` TypedDict with optional `input`, `output`, `cache_read`, `cache_write` (all float, USD per 1M tokens)
- `ModelAlias` TypedDict extended with optional `private`, `cost_tier`, `notes`, `pricing` fields
- `load_user_aliases()` extracts metadata and pricing sub-table when present
- `_show_aliases()` renders metadata columns (or hides them if no metadata present)
- `estimate_cost()` in `aliases.py` — pure function, no side effects
- Existing tests pass without modification
- New tests for: metadata in built-in aliases, pricing parsing from TOML, display with/without metadata, cost estimation
- `pyright`, `ruff check`, `ruff format` pass

### Verification Walkthrough

1. **Built-in metadata display:**
   ```bash
   sq models
   # Expect: table with Private, Cost, In $/1M, Out $/1M, Notes columns
   # SDK models show "sub" cost, blank pricing; API models show $ amounts
   ```

2. **User alias with pricing:**
   ```bash
   # Add to ~/.config/squadron/models.toml:
   # [aliases.deepseek]
   # profile = "openrouter"
   # model = "deepseek/deepseek-r2"
   # private = false
   # cost_tier = "cheap"
   #
   # [aliases.deepseek.pricing]
   # input = 0.14
   # output = 2.18

   sq models
   # Expect: deepseek row shows private=no, cost=$, In=$0.14, Out=$2.18, source=(user)
   ```

3. **User alias without metadata:**
   ```bash
   # In models.toml:
   # [aliases]
   # mymodel = { profile = "local", model = "llama3" }

   sq models
   # Expect: mymodel row has blank metadata columns
   ```

4. **Cost estimation (Python):**
   ```python
   from squadron.models.aliases import estimate_cost
   cost = estimate_cost("kimi25", input_tokens=15000, output_tokens=3000)
   # Expect: 0.15 (15K * $5/1M + 3K * $25/1M)

   cost = estimate_cost("opus", input_tokens=15000, output_tokens=3000)
   # Expect: None (subscription model, no per-token pricing)
   ```

5. **Backward compatibility:**
   ```bash
   sq review slice 120 --model opus
   # Expect: works exactly as before
   ```

6. **Tests:**
   ```bash
   uv run pytest tests/test_model_aliases.py tests/cli/test_model_list.py -v
   ```

## Implementation Notes

### Suggested Implementation Order

1. **Add `ModelPricing` TypedDict and extend `ModelAlias`** — new types, update `BUILT_IN_ALIASES` with metadata and pricing (effort: 1.5/5)
2. **Update `load_user_aliases()`** — extract metadata and pricing sub-table from TOML entries (effort: 1/5)
3. **Add `estimate_cost()` utility** — pure function for cost calculation (effort: 0.5/5)
4. **Update `_show_aliases()`** — add metadata columns, compact mode logic, price formatting (effort: 1/5)
5. **Tests** — alias metadata, pricing parsing, cost estimation, display formatting (effort: 1.5/5)

### Testing Strategy

- **Unit tests in `tests/test_model_aliases.py`:** Verify `BUILT_IN_ALIASES` entries have expected metadata. Test `load_user_aliases()` with pricing in both inline and full table TOML syntax. Test that missing metadata/pricing fields result in absent keys (not None or defaults). Test `estimate_cost()` with full pricing, partial pricing, and no pricing.
- **CLI tests in `tests/cli/test_model_list.py`:** Verify metadata columns appear. Verify compact mode (no metadata → no metadata columns). Verify pricing display formatting ($X.XX). Verify user aliases with and without metadata display correctly.
- **Regression:** Existing `resolve_model_alias()` tests should pass unchanged since metadata is additive and display-only.
