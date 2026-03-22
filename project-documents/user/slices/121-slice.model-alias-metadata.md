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

Extend the `ModelAlias` type with optional metadata fields so users and built-in aliases can carry information about privacy, cost, and notes. Update `sq models` to display metadata columns. Ship curated metadata for all built-in aliases.

## Value

- **Informed model selection.** `sq models` shows at a glance which providers train on prompts, relative cost, and useful notes (context window, speed characteristics).
- **Privacy awareness.** The `private` field lets users quickly identify which models/providers may train on their input — important when reviewing proprietary code.
- **Low friction.** Metadata is optional on every alias. Existing user `models.toml` files continue to work unchanged.

## Technical Scope

### Included

- Extend `ModelAlias` TypedDict with optional `private`, `cost_tier`, and `notes` fields
- Update `BUILT_IN_ALIASES` with curated metadata for all 12 defaults
- Update `models.toml` parsing to read metadata from both inline table and full table TOML syntax
- Update `sq models` table to show metadata columns
- Tests for new fields, parsing, and display

### Excluded

- Provider API metadata hydration (auto-fetching pricing/context from APIs) — tracked as a future enhancement in slice plan
- Validation or enforcement based on metadata (e.g., blocking reviews on non-private models)
- Metadata filtering in `sq models` (e.g., `--private-only`) — future if needed

## Dependencies

### Prerequisites

- **Model Alias Registry (120)** — complete. Provides `ModelAlias`, `BUILT_IN_ALIASES`, `load_user_aliases()`, `get_all_aliases()`, `sq models` CLI command.

### External Packages

- None new. `tomllib` (stdlib) already used.

## Technical Decisions

### Extended ModelAlias Type

```python
class ModelAlias(TypedDict, total=False):
    """A model alias mapping a short name to a profile and full model ID."""
    profile: str       # Required
    model: str         # Required
    private: bool      # Whether the provider may train on prompts
    cost_tier: str     # "free" | "cheap" | "moderate" | "expensive"
    notes: str         # Free-text (context window, speed, etc.)
```

Using `total=False` with `TypedDict` makes all fields optional by default. Since `profile` and `model` are always required in practice, validation stays in `load_user_aliases()` where it already checks for their presence. The type change is backward-compatible — existing code that only accesses `["profile"]` and `["model"]` continues to work.

**Alternative considered:** A separate `ModelAliasMetadata` TypedDict composed into `ModelAlias`. Rejected — adds a nesting level in both code and TOML format for three simple fields. YAGNI.

### cost_tier Values

Plain strings rather than an enum. The four values (`free`, `cheap`, `moderate`, `expensive`) are display labels, not routing logic. No code branches on them. An enum would add import overhead for zero safety benefit.

### TOML Format Support

Current inline syntax continues to work for aliases without metadata:

```toml
[aliases]
opus = { profile = "sdk", model = "claude-opus-4-6" }
```

Metadata requires either extended inline tables or full table sections:

```toml
# Inline table with metadata
[aliases]
kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2.5", private = true, cost_tier = "cheap", notes = "1M context" }

# Full table section (equivalent, more readable for many fields)
[aliases.deepseek]
profile = "openrouter"
model = "deepseek/deepseek-r2"
private = false
cost_tier = "cheap"
notes = "trains on all input"
```

Both are standard TOML and already parse correctly via `tomllib`. The only change is in `load_user_aliases()`: after extracting `profile` and `model`, also extract `private`, `cost_tier`, and `notes` if present.

### Built-in Metadata

Curated metadata for all 12 default aliases:

| Alias | private | cost_tier | notes |
|-------|---------|-----------|-------|
| opus | true | subscription | Max sub, highest capability |
| sonnet | true | subscription | Max sub, balanced |
| haiku | true | subscription | Max sub, fastest |
| gpt54 | true | expensive | Frontier model |
| gpt54-mini | true | moderate | Good cost/quality balance |
| gpt54-nano | true | cheap | Lightweight tasks |
| codex | true | expensive | Code-specialized |
| gemini | true | free | Free tier available |
| flash3 | true | free | Fast, free tier |
| kimi25 | true | cheap | 1M context |
| minimax | true | cheap | |
| glm5 | true | cheap | |

**`private` semantics:** `true` means the provider states they do not train on API input. `false` means the provider may train on input or their policy is unclear. All current built-in providers are `true` — their API terms prohibit training on API traffic. Users adding community or self-hosted models may set `false`.

**`cost_tier` = `"subscription"`:** Claude models via SDK use the Max subscription, not per-token billing. This is a meaningful distinction from "free" or "expensive" and warrants its own tier value.

### Display in `sq models`

Add three columns to the table: `Private`, `Cost`, `Notes`.

```
$ sq models
┏━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Alias     ┃ Profile     ┃ Model ID                      ┃ Private┃ Cost   ┃ Notes        ┃ Source ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━┩
│ opus      │ sdk         │ claude-opus-4-6               │ yes    │ sub    │ Max, highest │        │
│ sonnet    │ sdk         │ claude-sonnet-4-6             │ yes    │ sub    │ Max, balanced│        │
│ gpt54     │ openai      │ gpt-5.4                       │ yes    │ $$$    │ Frontier     │        │
│ kimi25    │ openrouter  │ moonshotai/kimi-k2.5          │ yes    │ $      │ 1M context   │        │
│ deepseek  │ openrouter  │ deepseek/deepseek-r2          │ no     │ $      │              │ (user) │
└───────────┴─────────────┴───────────────────────────────┴────────┴────────┴──────────────┴────────┘
```

**Display formatting:**
- `private`: `"yes"` / `"no"` / blank (if unset)
- `cost_tier`: Short display labels: `"free"` → `"free"`, `"cheap"` → `"$"`, `"moderate"` → `"$$"`, `"expensive"` → `"$$$"`, `"subscription"` → `"sub"`, unset → blank
- `notes`: Displayed as-is, truncated to ~30 chars if needed to keep table manageable

### Compact Mode

When no aliases have metadata (e.g., user has only basic aliases and no built-ins would show metadata), the metadata columns are hidden automatically. This keeps the display clean for users who don't care about metadata.

Implementation: check if any alias in the merged set has at least one metadata field set. If none do, render the table without Private/Cost/Notes columns. This applies to the entire table, not per-row.

## Data Flow

### Alias Loading with Metadata

```
load_user_aliases()
  → read models.toml
  → for each [aliases.X] or inline table:
    → extract profile, model (required — skip with warning if missing)
    → extract private, cost_tier, notes (optional — omit if absent)
    → build ModelAlias dict
  → return dict
```

### Display

```
sq models
  → get_all_aliases()  (merges built-in + user)
  → check if any alias has metadata fields
  → if yes: render 7-column table (Alias, Profile, Model ID, Private, Cost, Notes, Source)
  → if no: render 4-column table (Alias, Profile, Model ID, Source)
```

## Integration Points

### Provides to Other Slices

- Extended `ModelAlias` type available for future filtering/routing (e.g., Ensemble Review could select only `private=true` models)
- Metadata accessible via `get_all_aliases()` — no new API needed

### Consumes from Other Slices

- `ModelAlias`, `BUILT_IN_ALIASES`, `load_user_aliases()`, `get_all_aliases()` from slice 120

## Success Criteria

### Functional Requirements

- `sq models` shows Private, Cost, and Notes columns for built-in aliases
- All 12 built-in aliases have curated metadata
- User can add metadata to aliases in `models.toml` (inline or full table syntax)
- User aliases without metadata display with blank metadata columns
- Existing `models.toml` files without metadata fields continue to work
- `resolve_model_alias()` behavior unchanged — metadata is display-only, does not affect resolution

### Technical Requirements

- `ModelAlias` TypedDict extended with optional `private`, `cost_tier`, `notes` fields
- `load_user_aliases()` extracts metadata fields when present
- `_show_aliases()` renders metadata columns (or hides them if no metadata present)
- Existing tests pass without modification
- New tests for: metadata in built-in aliases, metadata parsing from TOML, display with/without metadata
- `pyright`, `ruff check`, `ruff format` pass

### Verification Walkthrough

1. **Built-in metadata display:**
   ```bash
   sq models
   # Expect: 7-column table with Private, Cost, Notes populated for all built-ins
   ```

2. **User alias with metadata:**
   ```bash
   # Add to ~/.config/squadron/models.toml:
   # [aliases.deepseek]
   # profile = "openrouter"
   # model = "deepseek/deepseek-r2"
   # private = false
   # cost_tier = "cheap"
   # notes = "trains on all input"

   sq models
   # Expect: deepseek row shows private=no, cost=$, notes="trains on all input", source=(user)
   ```

3. **User alias without metadata:**
   ```bash
   # In models.toml:
   # [aliases]
   # mymodel = { profile = "local", model = "llama3" }

   sq models
   # Expect: mymodel row has blank Private/Cost/Notes columns
   ```

4. **Backward compatibility:**
   ```bash
   sq review slice 120 --model opus
   # Expect: works exactly as before — metadata does not affect review behavior
   ```

5. **Tests:**
   ```bash
   uv run pytest tests/test_model_aliases.py tests/cli/test_model_list.py -v
   ```

## Implementation Notes

### Suggested Implementation Order

1. **Extend `ModelAlias` TypedDict** — add optional fields, update `BUILT_IN_ALIASES` with metadata (effort: 1/5)
2. **Update `load_user_aliases()`** — extract metadata fields from TOML entries (effort: 0.5/5)
3. **Update `_show_aliases()`** — add metadata columns, compact mode logic (effort: 1/5)
4. **Tests** — alias metadata, TOML parsing, display formatting (effort: 1/5)

### Testing Strategy

- **Unit tests in `tests/test_model_aliases.py`:** Verify `BUILT_IN_ALIASES` entries have expected metadata. Test `load_user_aliases()` with metadata in both inline and full table TOML syntax. Test that missing metadata fields result in absent keys (not None or defaults).
- **CLI tests in `tests/cli/test_model_list.py`:** Verify metadata columns appear. Verify compact mode (no metadata → no metadata columns). Verify user aliases with and without metadata display correctly.
- **Regression:** Existing `resolve_model_alias()` tests should pass unchanged since metadata is additive and display-only.
