---
docType: review
layer: project
reviewType: code
slice: configuration-externalization
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/141-slice.configuration-externalization.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260329
dateUpdated: 20260329
---

# Review: code — slice 141

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] `data_dir()` fallback pattern is correct and consistent

`src/squadron/data/__init__.py` correctly implements the two-path fallback pattern that mirrors `install.py`'s `_get_commands_source()`. The `importlib.resources.files()` approach works for wheel installs; `Path(__file__).parent` correctly resolves to `squadron/data/` in editable installs since `__init__.py` lives inside the data directory itself. The fallback is intentional and documented.

### [PASS] `aliases.py` refactoring is clean and correct

The extraction of `_load_aliases_from_file(path: Path)` as a shared helper is good design — it eliminates duplication between the user and built-in loaders. `_load_builtin_aliases()` is a proper thin wrapper. `get_all_aliases()` correctly merges built-ins first, then user overrides. The `BUILT_IN_ALIASES` dict removal is complete.

### [PASS] `models.toml` format is correct and consistent

The TOML transcription correctly uses dotted key syntax (`[aliases.opus]`, `[aliases.opus.pricing]`) matching the existing user config format. All 16 aliases are transcribed with all required fields (`profile`, `model`) and optional fields (`private`, `cost_tier`, `notes`, `pricing` sub-table).

### [PASS] Template loader migration is correct

`src/squadron/review/templates/__init__.py` correctly replaces `Path(__file__).parent / "builtin"` with `data_dir() / "templates"`. The `builtin/` subdirectory is deleted. All four template files are correctly renamed and relocated.

### [PASS] `models.py` import update is correct

`src/squadron/cli/commands/models.py` correctly updates from `BUILT_IN_ALIASES` to `_load_builtin_aliases()` for the source attribution logic in `sq model list`.

### [PASS] `pyproject.toml` wheel force-include is correct

The addition `"src/squadron/data" = "squadron/data"` correctly maps the source directory to the wheel package location.

### [PASS] Test updates are comprehensive

- `tests/models/test_aliases.py` adds new tests for `_load_builtin_aliases()` and updates existing tests to use it
- `tests/cli/test_model_list.py` correctly updates all references to `_load_builtin_aliases()`
- `tests/review/conftest.py`, `test_builtin_arch.py`, `test_builtin_code.py`, `test_builtin_tasks.py` all correctly use `data_dir() / "templates"` via the fixture
- `tests/review/test_templates.py` adds test for all four templates being registered

### [PASS] No API surface changes

All public functions (`get_all_aliases`, `load_user_aliases`, `resolve_model_alias`, `estimate_cost`, `load_template`, `load_all_templates`, `get_template`) maintain their signatures. Downstream consumers see no change.

### [PASS] Documentation is well-maintained

CHANGELOG and DEVLOG correctly describe the reorganization. Architecture documentation is updated to reflect the new `data/` canonical location and the correct slice index for "Structured Review Findings" (143, not 141).
