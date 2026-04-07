---
slice: model-alias-metadata
project: squadron
lld: user/slices/121-slice.model-alias-metadata.md
dependencies: [model-alias-registry]
projectState: Slices 100-120 complete. ModelAlias TypedDict with profile/model fields in src/squadron/models/aliases.py. BUILT_IN_ALIASES dict with 12 entries. load_user_aliases() parses models.toml. sq models shows 4-column table (Alias, Profile, Model ID, Source). resolve_model_alias() returns (model, profile) tuple.
dateCreated: 20260322
dateUpdated: 20260323
status: complete
docType: tasks
---

## Context Summary

- Working on `model-alias-metadata` slice — extends model aliases with optional metadata and pricing
- Current `ModelAlias` is a TypedDict with only `profile` and `model` fields
- `BUILT_IN_ALIASES` has 12 entries (opus, sonnet, haiku, gpt54, gpt54-mini, gpt54-nano, codex, gemini, flash3, kimi25, minimax, glm5) — no metadata
- `sq models` displays a 4-column table; needs metadata columns (Private, Cost, In $/1M, Out $/1M, Notes)
- New `ModelPricing` TypedDict and `estimate_cost()` function enable future cost reporting
- Key files: `src/squadron/models/aliases.py`, `src/squadron/cli/commands/models.py`
- Test files: `tests/cli/test_model_list.py`, `tests/review/test_model_resolution.py`

---

## Tasks

### T1: Add `ModelPricing` TypedDict

- [x] In `src/squadron/models/aliases.py`, add `ModelPricing` TypedDict above `ModelAlias`
  - [x] Fields: `input` (float), `output` (float), `cache_read` (float), `cache_write` (float)
  - [x] Use `total=False` — all fields optional
  - [x] Docstring: "Per-token pricing for a model, all values in USD per 1M tokens."
- [x] `uv run pyright` and `uv run ruff check` pass

### T2: Extend `ModelAlias` TypedDict with metadata fields

- [x] Change `ModelAlias` to use `total=False`
  - [x] `profile` and `model` remain required in practice — validation in `load_user_aliases()` already checks for them
- [x] Add optional fields to `ModelAlias`:
  - [x] `private: bool` — whether provider states they don't train on input
  - [x] `cost_tier: str` — one of: free, cheap, moderate, expensive, subscription
  - [x] `notes: str` — free-text
  - [x] `pricing: ModelPricing` — per-token cost data
- [x] Verify existing code accessing `alias["profile"]` and `alias["model"]` still works (backward-compatible change)
- [x] `uv run pyright` and `uv run ruff check` pass
- [x] Existing tests pass: `uv run pytest tests/cli/test_model_list.py tests/review/test_model_resolution.py -v`

### T3: Update `BUILT_IN_ALIASES` with curated metadata and pricing

- [x] Update all 12 entries in `BUILT_IN_ALIASES` with metadata fields per the slice design table:
  - [x] Claude family (opus, sonnet, haiku): `private=True`, `cost_tier="subscription"`, `notes="Max sub"`, no `pricing` key
  - [x] OpenAI family (gpt54, gpt54-mini, gpt54-nano, codex): `private=True`, appropriate `cost_tier`, `pricing` with input/output and cache values where available
  - [x] Google (gemini, flash3): `private=True`, `cost_tier="free"`, `pricing` with all zeros
  - [x] OpenRouter (kimi25, minimax, glm5): `private=True`, `cost_tier="cheap"`, `pricing` with input/output (cache where available)
- [x] Use exact pricing values from the slice design metadata table
- [x] `uv run pyright` and `uv run ruff check` pass

### T4: Tests for `ModelAlias` type extension and built-in metadata

- [x] In `tests/cli/test_model_list.py`, add tests:
  - [x] `test_builtin_aliases_have_metadata`: verify all entries in `BUILT_IN_ALIASES` have `private` and `cost_tier` keys
  - [x] `test_builtin_sdk_aliases_have_no_pricing`: verify opus, sonnet, haiku do NOT have `pricing` key
  - [x] `test_builtin_api_aliases_have_pricing`: verify gpt54, kimi25, gemini etc. have `pricing` key with `input` and `output` fields
- [x] All tests pass: `uv run pytest tests/cli/test_model_list.py -v`
- [x] Commit: `feat: add ModelPricing type, extend ModelAlias with metadata and pricing`

### T5: Update `load_user_aliases()` to extract metadata fields

- [x] In `src/squadron/models/aliases.py`, update the loop in `load_user_aliases()`:
  - [x] After extracting `profile` and `model`, also extract optional fields:
    - [x] `private`: if present and `isinstance(val, bool)`, include in alias dict
    - [x] `cost_tier`: if present and `isinstance(val, str)`, include in alias dict
    - [x] `notes`: if present and `isinstance(val, str)`, include in alias dict
  - [x] Extract `pricing` sub-table: if present and `isinstance(val, dict)`, build `ModelPricing` dict from its float fields (`input`, `output`, `cache_read`, `cache_write`)
  - [x] Skip individual pricing fields that aren't floats/ints with a warning
  - [x] If no valid pricing fields found in the sub-table, omit `pricing` from alias
- [x] `uv run pyright` and `uv run ruff check` pass

### T6: Tests for metadata and pricing TOML parsing

- [x] In `tests/cli/test_model_list.py`, add tests:
  - [x] `test_user_alias_with_metadata`: write a `models.toml` with full table syntax including `private`, `cost_tier`, `notes`; verify all fields loaded
  - [x] `test_user_alias_with_pricing_full_table`: write `[aliases.mymodel.pricing]` section with `input`, `output`, `cache_read`, `cache_write`; verify `pricing` dict loaded with all four fields
  - [x] `test_user_alias_with_pricing_inline`: write inline `pricing = { input = 1.0, output = 2.0 }`; verify loaded
  - [x] `test_user_alias_with_partial_pricing`: write `pricing` with only `input` and `output`; verify `cache_read` and `cache_write` absent (not defaulted)
  - [x] `test_user_alias_without_metadata`: write minimal `{ profile, model }` alias; verify no metadata keys present
  - [x] `test_existing_toml_backward_compat`: write old-format `models.toml` with no metadata; verify `load_user_aliases()` returns aliases with only `profile` and `model`
- [x] All tests pass: `uv run pytest tests/cli/test_model_list.py -v`
- [x] Commit: `feat: parse metadata and pricing from user models.toml`

### T7: Add `estimate_cost()` utility function

- [x] In `src/squadron/models/aliases.py`, add `estimate_cost()` function:
  - [x] Signature: `estimate_cost(alias_name: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float | None`
  - [x] Look up alias via `get_all_aliases()`
  - [x] If alias not found or has no `pricing` key, return `None`
  - [x] If `pricing` exists but lacks `input` or `output`, return `None`
  - [x] Calculate: `(input_tokens / 1_000_000 * pricing["input"]) + (output_tokens / 1_000_000 * pricing["output"])`
  - [x] If `cached_tokens > 0` and `cache_read` present, add: `cached_tokens / 1_000_000 * pricing["cache_read"]`
  - [x] Return the total as a float
- [x] `uv run pyright` and `uv run ruff check` pass

### T8: Tests for `estimate_cost()`

- [x] In `tests/cli/test_model_list.py` (or a new `tests/test_estimate_cost.py` if cleaner), add tests:
  - [x] `test_estimate_cost_full_pricing`: call with a known built-in alias that has pricing (e.g., `kimi25`), verify correct USD result
  - [x] `test_estimate_cost_with_cache`: call with `cached_tokens > 0` on an alias with `cache_read`, verify cache cost included
  - [x] `test_estimate_cost_no_pricing`: call with `opus` (subscription, no pricing), verify returns `None`
  - [x] `test_estimate_cost_unknown_alias`: call with nonexistent alias name, verify returns `None`
  - [x] `test_estimate_cost_zero_tokens`: call with `input_tokens=0, output_tokens=0`, verify returns `0.0` (not None — pricing exists, cost is legitimately zero)
  - [x] `test_estimate_cost_free_model`: call with `gemini` (pricing all zeros), verify returns `0.0`
- [x] All tests pass: `uv run pytest tests/cli/test_model_list.py -v` (or new test file)
- [x] Commit: `feat: add estimate_cost() utility for per-token cost estimation`

### T9: Add `--verbose` flag and update `_show_aliases()` with metadata columns

- [x] In `src/squadron/cli/commands/models.py`, update `_show_aliases()` to accept a `verbose: bool` parameter
  - [x] Default table (compact): 4 columns — Alias, Profile, Model ID, Source (unchanged from current)
  - [x] When `verbose=True`, add metadata columns to the Rich table:
    - [x] `Private` (style: dim) — display `"yes"` / `"no"` / `""` based on `alias.get("private")`
    - [x] `Cost` — map `cost_tier` to display label: `free`→`"free"`, `cheap`→`"$"`, `moderate`→`"$$"`, `expensive`→`"$$$"`, `subscription`→`"sub"`, absent→`""`
    - [x] `In $/1M` — format `pricing["input"]` as `$X.XX` if present, blank if absent
    - [x] `Out $/1M` — format `pricing["output"]` as `$X.XX` if present, blank if absent
    - [x] `Notes` (style: dim) — display `alias.get("notes", "")`, truncate to 30 chars
  - [x] `Source` column remains last in both modes
- [x] Add `-v` / `--verbose` flag to `models_default()` callback
  - [x] Pass `verbose` through to `_show_aliases(verbose=verbose)`
- [x] Update `models_list()` subcommand to also accept `-v` / `--verbose` and pass through
- [x] `uv run pyright` and `uv run ruff check` pass

### T10: Tests for verbose display and compact default

- [x] In `tests/cli/test_model_list.py`, add/update tests:
  - [x] `test_models_default_compact`: run `sq models` (no flags), verify output does NOT contain `Private`, `Cost`, `In $/1M` column headers
  - [x] `test_models_verbose_shows_metadata_columns`: run `sq models -v`, verify output contains `Private`, `Cost`, `In $/1M`, `Out $/1M`, `Notes` column headers
  - [x] `test_models_verbose_shows_pricing_values`: run `sq models -v`, verify output contains formatted pricing like `$2.50` or `$5.00` for a known alias
  - [x] `test_models_verbose_shows_subscription_cost_tier`: run `sq models -v`, verify `sub` appears in output (for SDK aliases)
  - [x] `test_models_verbose_private_yes`: run `sq models -v`, verify `yes` appears for built-in aliases (all are private=True)
  - [x] `test_models_list_verbose`: run `sq models list -v`, verify metadata columns appear (parity with bare command)
- [x] All tests pass: `uv run pytest tests/cli/test_model_list.py -v`
- [x] Commit: `feat: add -v flag to sq models for metadata and pricing display`

### T11: Full validation pass

- [x] Run full test suite: `uv run pytest`
  - [x] All tests pass (including existing tests in `test_model_resolution.py`, `test_review_resolve.py`)
- [x] `uv run pyright` — 0 errors
- [x] `uv run ruff check` — clean
- [x] `uv run ruff format --check` — clean
- [x] Manual verification: `sq models` displays the expected table with metadata columns
- [x] Commit any remaining changes
- [x] Final commit: `feat: complete slice 121 — model alias metadata`

### T12: Post-implementation — update slice status

- [x] Mark slice 121 as complete in `project-documents/user/slices/121-slice.model-alias-metadata.md` (status: complete)
- [x] Mark slice 121 as checked in `project-documents/user/architecture/100-slices.orchestration-v2.md`
  - [x] Change `18. [ ] **(121) Model Alias Metadata**` → `18. [x] **(121) Model Alias Metadata**`
- [x] Update DEVLOG with completion entry
- [x] Commit: `docs: mark slice 121 (Model Alias Metadata) complete`
