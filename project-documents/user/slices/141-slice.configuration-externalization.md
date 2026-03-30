---
docType: slice-design
parent: 140-arch.pipeline-foundation.md
slicePlan: 140-slices.pipeline-foundation.md
project: squadron
sliceIndex: 141
sliceName: configuration-externalization
dateCreated: 20260328
dateUpdated: 20260329
status: complete
---

# Slice Design: Configuration Externalization (141)

## Overview

This slice consolidates all shipped data files into a single canonical location: `src/squadron/data/`. Currently, shipped defaults live in multiple places — model aliases as a Python `dict` in `models/aliases.py`, and review templates as YAML files in `review/templates/builtin/`. Pipeline definitions (YAML, introduced in later slices) will join them. After this slice, `src/squadron/data/` is the single answer to "where do shipped defaults live?"

The slice also establishes a clean loading pattern shared by all three data categories: package data first, then user overrides from `~/.config/squadron/`. The formats are identical across shipped and user config — users can copy blocks directly between the two without transformation.

**Slice plan entry:** **(141) Configuration Externalization** — Consolidate all shipped data files into `src/squadron/data/`: model aliases (TOML, moved from Python dict in `aliases.py`), review templates (YAML, moved from `review/templates/builtin/`), and pipeline definitions (YAML, new in later slices). Built-in and user override files use identical formats — users can copy blocks between shipped defaults and their `~/.config/squadron/` overrides. Runtime loads from `data/` first, then layers user config on top (existing merge behavior preserved). "All defaults live in `squadron/data/`" becomes the single answer for where to find shipped configuration. Dependencies: [100-band complete]. Risk: Low. Effort: 2/5

---

## Scope

### In scope

- Move `BUILT_IN_ALIASES` dict (in `src/squadron/models/aliases.py`) to `src/squadron/data/models.toml`
- Move review template YAML files from `src/squadron/review/templates/builtin/` to `src/squadron/data/templates/`
- Add `src/squadron/data/` to `pyproject.toml` hatch `force-include`
- Create a `DataLoader` utility that locates `src/squadron/data/` at runtime (wheel and dev install)
- Update `aliases.py` loader to read `data/models.toml` as the built-in source
- Update `review/templates/__init__.py` loader to read from `data/templates/`
- Reserve `src/squadron/data/pipelines/` directory for slice 148 (empty placeholder with `.gitkeep`)
- Verify `sq model list` and `sq review` still work end-to-end

### Out of scope

- Pipeline definition YAML (implemented in slice 148)
- Adding new config keys
- Changing the `~/.config/squadron/` user override paths (they stay the same)
- Any behavior changes to how aliases or templates function

---

## Current State

### Model Aliases

`src/squadron/models/aliases.py` defines `BUILT_IN_ALIASES: dict[str, ModelAlias]` as a Python literal (~200 lines). The `load_user_aliases()` function reads `~/.config/squadron/models.toml`. The `get_all_aliases()` function merges: built-in dict first, user overrides on top.

**Problem:** Built-in aliases are not in the same format as user aliases. A user wanting to reference or copy a built-in alias must read Python source. The architecture says these should share identical TOML format.

### Review Templates

`src/squadron/review/templates/builtin/` contains four YAML files (`code.yaml`, `slice.yaml`, `tasks.yaml`, `arch.yaml`). The `load_all_templates()` function in `review/templates/__init__.py` resolves the builtin dir as `Path(__file__).parent / "builtin"` — i.e., relative to the `__init__.py` file itself.

**Problem:** Templates are colocated with their Python loader, not with other shipped data. The architecture wants a single `data/` directory for all shipped defaults.

### Package Data

`pyproject.toml` already ships `commands/` via `force-include`:
```toml
[tool.hatch.build.targets.wheel.force-include]
"commands" = "squadron/commands"
```

The same mechanism will be used to ship `src/squadron/data/` (it maps to `squadron/data/` in the wheel).

---

## Target State

### Directory layout

```
src/squadron/
  data/
    models.toml          ← built-in aliases (was BUILT_IN_ALIASES in aliases.py)
    templates/
      code.yaml          ← moved from review/templates/builtin/
      slice.yaml
      tasks.yaml
      arch.yaml
    pipelines/           ← reserved for slice 148; empty with .gitkeep
  models/
    aliases.py           ← loads from data/models.toml; BUILT_IN_ALIASES removed
  review/
    templates/
      __init__.py        ← loads from data/templates/; builtin/ subdir removed
      builtin/           ← DELETED
```

### `models.toml` format

Matches the existing `~/.config/squadron/models.toml` user format exactly:

```toml
[aliases.opus]
profile = "sdk"
model = "claude-opus-4-6"
private = true
cost_tier = "subscription"
notes = "Max sub"

[aliases.sonnet]
profile = "sdk"
model = "claude-sonnet-4-6"
private = true
cost_tier = "subscription"
notes = "Max sub"

# ... all other entries from BUILT_IN_ALIASES
```

This is the same TOML structure that `load_user_aliases()` already parses. No format changes needed.

### `DataLoader` utility

A small module `src/squadron/data/__init__.py` provides a single public function:

```python
def data_dir() -> Path:
    """Return the path to the squadron/data package directory.

    Works in both wheel installs (importlib.resources) and editable installs
    (falls back to the source tree via __file__).
    """
```

This follows the same fallback pattern used by `install.py`'s `_get_commands_source()`:
1. Try `importlib.resources.files("squadron") / "data"` — works in wheel installs
2. Fall back to `Path(__file__).parent` — works in editable installs because `data/__init__.py` is in `src/squadron/data/`

Both callers (`aliases.py` and `review/templates/__init__.py`) import `data_dir()` from `squadron.data`.

### `aliases.py` changes

Remove `BUILT_IN_ALIASES` dict. Replace with a loader that reads `data/models.toml`:

```python
def _load_builtin_aliases() -> dict[str, ModelAlias]:
    """Load built-in aliases from the shipped data/models.toml."""
    from squadron.data import data_dir
    path = data_dir() / "models.toml"
    # same parsing logic as load_user_aliases(), reused via shared helper
    return _load_aliases_from_file(path)
```

The `get_all_aliases()` function becomes:
```python
def get_all_aliases() -> dict[str, ModelAlias]:
    merged = _load_builtin_aliases()
    merged.update(load_user_aliases())
    return merged
```

No public API changes. `estimate_cost()`, `resolve_model_alias()`, `get_all_aliases()`, `load_user_aliases()` — all unchanged in signature.

**Shared parsing helper:** The existing `load_user_aliases()` contains TOML-parsing logic that `_load_builtin_aliases()` will also need. Extract a shared internal helper `_load_aliases_from_file(path: Path) -> dict[str, ModelAlias]` that both callers use. `load_user_aliases()` becomes a thin wrapper around it.

### `review/templates/__init__.py` changes

Replace the hardcoded `Path(__file__).parent / "builtin"` with `data_dir() / "templates"`. Remove the `builtin/` subdirectory.

```python
def load_all_templates(user_dir: Path | None = None) -> None:
    from squadron.data import data_dir
    builtin_dir = data_dir() / "templates"
    # rest unchanged
```

The `load_builtin_templates` backward-compatible alias is preserved.

### `pyproject.toml` addition

```toml
[tool.hatch.build.targets.wheel.force-include]
"commands" = "squadron/commands"
"src/squadron/data" = "squadron/data"
```

---

## Migration Plan

### Phase 1: Create `src/squadron/data/`

1. Create `src/squadron/data/__init__.py` with `data_dir()` function
2. Create `src/squadron/data/models.toml` by transcribing `BUILT_IN_ALIASES` to TOML
3. Create `src/squadron/data/templates/` directory; copy (not move yet) the 4 YAML files from `review/templates/builtin/`
4. Create `src/squadron/data/pipelines/.gitkeep`
5. Update `pyproject.toml` force-include

### Phase 2: Update loaders

6. Refactor `aliases.py`: extract `_load_aliases_from_file()`, add `_load_builtin_aliases()`, update `get_all_aliases()`, remove `BUILT_IN_ALIASES`
7. Update `review/templates/__init__.py`: replace builtin dir resolution with `data_dir() / "templates"`

### Phase 3: Cleanup

8. Delete `src/squadron/review/templates/builtin/` directory

### Phase 4: Verify

9. `sq model list` — shows all aliases including built-ins
10. `sq review code --diff main --no-save --dry-run` (or equivalent) — templates load correctly
11. Run test suite

---

## Consumer Updates

### Internal consumers of `BUILT_IN_ALIASES`

Grep confirms `BUILT_IN_ALIASES` is referenced only within `aliases.py` itself (used only in `get_all_aliases()`). No external consumers need updating.

### Internal consumers of `review/templates/builtin/` path

The builtin path is computed only inside `load_all_templates()`. No external reference to the literal path exists.

### Tests referencing built-in aliases or template paths

Any tests that reference `BUILT_IN_ALIASES` directly or construct `Path(__file__).parent / "builtin"` paths will need updating to use the new loading functions.

---

## Data Format: `models.toml`

The TOML format mirrors what `load_user_aliases()` already parses. Key points:

- Section headers: `[aliases.<name>]`
- Required fields: `profile` (string), `model` (string)
- Optional fields: `private` (bool), `cost_tier` (string), `notes` (string), `pricing` sub-table
- Pricing sub-table: `input`, `output`, `cache_read`, `cache_write` (all floats, USD per 1M tokens)

The existing `_extract_metadata()` and `_extract_pricing()` helpers already handle all these fields. They are reused without modification.

---

## Cross-Slice Interfaces

**Slice 142 (Pipeline Core Models):** Will add Pydantic models for pipeline infrastructure. Does not depend on this slice's data directory structure, but the reserved `data/pipelines/` directory anticipates slice 148's pipeline YAML files.

**Slice 148 (Pipeline Definitions and Loader):** Will add `src/squadron/data/pipelines/*.yaml` built-in pipeline definitions. The `data_dir()` function provides the discovery root. Slice 148 calls `data_dir() / "pipelines"` directly — no API changes to `DataLoader` needed.

**Existing consumers:** `aliases.py` and `review/templates/__init__.py` public APIs are unchanged. Downstream callers (`sq model list`, `sq review`, agent dispatch) see no change.

---

## Success Criteria

1. `src/squadron/data/models.toml` contains all aliases currently in `BUILT_IN_ALIASES`; the Python dict is removed from `aliases.py`
2. `src/squadron/review/templates/builtin/` is deleted; templates load from `src/squadron/data/templates/`
3. `sq model list` shows all expected aliases (built-in and user overrides)
4. All four review types (`code`, `slice`, `tasks`, `arch`) load their templates without error
5. `data_dir()` resolves correctly in both editable install (`uv run sq`) and a wheel install
6. `src/squadron/data/pipelines/` exists (placeholder for slice 148)
7. Test suite passes

---

## Verification Walkthrough

```bash
# 1. Confirm data directory exists with expected files
ls src/squadron/data/
# → models.toml  templates/  pipelines/

ls src/squadron/data/templates/
# → arch.yaml  code.yaml  slice.yaml  tasks.yaml

# 2. Confirm built-in alias dict is gone from aliases.py
grep -n "BUILT_IN_ALIASES" src/squadron/models/aliases.py
# → no results (or only the function reference in get_all_aliases comment)

# 3. Model aliases still load
uv run sq models list
# → shows opus, sonnet, haiku, gpt54, ... (all expected aliases)

# 4. Review templates still load — run a code review
uv run sq review code --diff main --no-save
# → completes without template-not-found error

# 5. Test suite
uv run pytest
# → all tests pass

# 6. Confirm builtin/ dir is gone
ls src/squadron/review/templates/
# → __init__.py  (no builtin/ subdirectory)
```

---

## Notes

- **No behavior changes.** This is a pure reorganization. Public APIs, CLI commands, user config paths, and the merge precedence (built-ins → user overrides) are all unchanged.
- **`models.toml` transcription.** The TOML file is hand-transcribed from the Python dict. After transcription, verify the count of aliases matches (`len(BUILT_IN_ALIASES)`) before deleting the dict.
- **`private: true` in models.toml.** All current built-in aliases have `private: true`. This field is already handled by `_extract_metadata()` in `aliases.py`. No changes needed.
- **Dev vs. wheel install.** The `data_dir()` fallback path (`Path(__file__).parent`) works because `src/squadron/data/__init__.py` is inside the data directory itself — `__file__` is `squadron/data/__init__.py`, so `Path(__file__).parent` is the data dir. No ambiguity.
