---
docType: tasks
slice: configuration-externalization
sliceIndex: 141
project: squadron
lldReference: project-documents/user/slices/141-slice.configuration-externalization.md
dependencies:
  - 100-band complete
status: not_started
dateCreated: 20260329
dateUpdated: 20260329
---

# Tasks: Configuration Externalization (141)

## Context Summary

Move all shipped defaults into `src/squadron/data/`:
- `BUILT_IN_ALIASES` Python dict → `src/squadron/data/models.toml` (TOML, same format as user `models.toml`)
- `review/templates/builtin/*.yaml` → `src/squadron/data/templates/*.yaml`
- Reserve `src/squadron/data/pipelines/` for slice 148

Add a `DataLoader` utility (`src/squadron/data/__init__.py`) with `data_dir() -> Path` — same two-path fallback pattern as `install.py`'s `_get_commands_source()`.

Update both loaders (`aliases.py`, `review/templates/__init__.py`) to read from `data/`. Public APIs unchanged. No behavior changes.

---

## Tasks

### T1: Create `src/squadron/data/` package skeleton

- [x] T1.1 — Create `src/squadron/data/` directory
- [x] T1.2 — Create `src/squadron/data/__init__.py` with `data_dir() -> Path` function:
  - Step 1: try `importlib.resources.files("squadron") / "data"` — cast result to `Path`; if it `is_dir()`, return it
  - Step 2: fallback — `Path(__file__).parent` (works in editable install because `__init__.py` lives inside the dir)
  - No other public symbols in this module
- [x] T1.3 — Create `src/squadron/data/templates/` directory (empty placeholder; populated in T2)
- [x] T1.4 — Create `src/squadron/data/pipelines/` directory with `.gitkeep` (placeholder for slice 148)

**Success criteria:** `from squadron.data import data_dir; data_dir().is_dir()` returns `True` under `uv run python`.

---

### T2: Copy review template YAMLs into `data/templates/`

- [x] T2.1 — Copy `src/squadron/review/templates/builtin/code.yaml` → `src/squadron/data/templates/code.yaml`
- [x] T2.2 — Copy `src/squadron/review/templates/builtin/slice.yaml` → `src/squadron/data/templates/slice.yaml`
- [x] T2.3 — Copy `src/squadron/review/templates/builtin/tasks.yaml` → `src/squadron/data/templates/tasks.yaml`
- [x] T2.4 — Copy `src/squadron/review/templates/builtin/arch.yaml` → `src/squadron/data/templates/arch.yaml`

**Success criteria:** All four YAML files exist under `src/squadron/data/templates/`; file contents are identical to the originals.

---

### T3: Create `src/squadron/data/models.toml`

Transcribe all entries from `BUILT_IN_ALIASES` in `src/squadron/models/aliases.py` to TOML format.

Format per entry:
```toml
[aliases.<name>]
profile = "..."
model = "..."
private = true          # if present
cost_tier = "..."       # if present
notes = "..."           # if present

[aliases.<name>.pricing]
input = 0.00            # if present
output = 0.00
cache_read = 0.00
cache_write = 0.00
```

- [x] T3.1 — Transcribe all Claude SDK aliases: `opus`, `sonnet`, `haiku`
- [x] T3.2 — Transcribe all OpenAI GPT-5.4 aliases: `gpt54`, `gpt54-mini`, `gpt54-nano`, `codex`, `codex-agent`, `codex-spark`
- [x] T3.3 — Transcribe all Google Gemini aliases: `gemini`, `flash3`, `flash3-lite`
- [x] T3.4 — Transcribe all OpenRouter aliases: `kimi25`, `minimax`, `glm5`, `glm5-turbo`, `mimo-omni`, `grok-fast`
- [x] T3.5 — Verify alias count: `grep -c '^\[aliases\.' src/squadron/data/models.toml` matches `len(BUILT_IN_ALIASES)` in `aliases.py` (currently 16 entries)

**Success criteria:** `models.toml` has the same number of alias entries as `BUILT_IN_ALIASES`; spot-check 3 entries for field accuracy.

---

### T4: Refactor `aliases.py` to load from `data/models.toml`

- [x] T4.1 — Extract shared parsing helper: rename the body of `load_user_aliases()` parsing logic into `_load_aliases_from_file(path: Path) -> dict[str, ModelAlias]`. This function opens and parses any aliases TOML file using the existing `_extract_metadata()` and `_extract_pricing()` helpers.
- [x] T4.2 — Rewrite `load_user_aliases()` as a thin wrapper: `return _load_aliases_from_file(models_toml_path())`
- [x] T4.3 — Add `_load_builtin_aliases() -> dict[str, ModelAlias]`: imports `data_dir` from `squadron.data`, calls `_load_aliases_from_file(data_dir() / "models.toml")`
- [x] T4.4 — Update `get_all_aliases()`: replace `dict(BUILT_IN_ALIASES)` with `_load_builtin_aliases()`
- [x] T4.5 — Remove `BUILT_IN_ALIASES` dict from `aliases.py`
- [x] T4.6 — Run `uv run sq model list` — confirm all expected aliases appear

**Success criteria:** `sq model list` shows the same aliases as before; `BUILT_IN_ALIASES` no longer exists in `aliases.py`.

---

### T5: Test alias loading

- [x] T5.1 — Run existing alias tests: `uv run pytest tests/ -k alias -v`
- [x] T5.2 — If any tests reference `BUILT_IN_ALIASES` directly, update them to call `_load_builtin_aliases()` or `get_all_aliases()` instead
- [x] T5.3 — Add a test asserting `_load_builtin_aliases()` returns a non-empty dict and contains `"opus"`, `"sonnet"`, `"haiku"`

**Success criteria:** All alias tests pass.

---

### T6: Update `review/templates/__init__.py` to load from `data/templates/`

- [x] T6.1 — In `load_all_templates()`, replace:
  ```python
  builtin_dir = Path(__file__).parent / "builtin"
  ```
  with:
  ```python
  from squadron.data import data_dir
  builtin_dir = data_dir() / "templates"
  ```
- [x] T6.2 — Run `uv run sq review code --diff main --no-save` — confirm it completes without template errors
- [x] T6.3 — Spot-check the remaining three review types load correctly: run `uv run sq review slice --help`, `sq review tasks --help`, `sq review arch --help` (no template load errors on startup)

**Success criteria:** All four review types load their templates from `data/templates/` without error.

---

### T7: Test review template loading

- [x] T7.1 — Run existing template tests: `uv run pytest tests/ -k template -v`
- [x] T7.2 — If any tests construct `Path(__file__).parent / "builtin"` paths directly, update them to use `data_dir() / "templates"`
- [x] T7.3 — Add a test asserting `load_all_templates()` registers templates named `"code"`, `"slice"`, `"tasks"`, `"arch"`

**Success criteria:** All template tests pass.

---

### T8: Update `pyproject.toml` force-include

- [x] T8.1 — Add to `[tool.hatch.build.targets.wheel.force-include]`:
  ```toml
  "src/squadron/data" = "squadron/data"
  ```
- [x] T8.2 — Build a wheel and confirm `squadron/data/models.toml` and `squadron/data/templates/` are present: `uv build && unzip -l dist/*.whl | grep squadron/data`

**Success criteria:** Wheel contains `squadron/data/models.toml`, all four template YAMLs, and `squadron/data/pipelines/.gitkeep`.

---

### T9: Delete old `builtin/` directory

- [x] T9.1 — Delete `src/squadron/review/templates/builtin/` and all contents
- [x] T9.2 — Run full test suite: `uv run pytest`
- [x] T9.3 — Confirm `src/squadron/review/templates/` contains only `__init__.py` (and `__pycache__/`)

**Success criteria:** Full test suite passes; `builtin/` directory is gone.

---

### T10: Final verification

- [x] T10.1 — `uv run sq model list` — all aliases display correctly
- [x] T10.2 — `uv run sq review code --diff main --no-save` — completes without error
- [x] T10.3 — `ls src/squadron/data/` shows: `__init__.py`, `models.toml`, `templates/`, `pipelines/`
- [x] T10.4 — `grep -rn "BUILT_IN_ALIASES" src/` — no matches
- [x] T10.5 — `ls src/squadron/review/templates/` — only `__init__.py` (no `builtin/`)
- [x] T10.6 — Run `ruff format src/squadron/` before committing

---

### T11: Commit

- [x] T11.1 — Stage and commit all changes with message:
  `refactor: consolidate shipped defaults into src/squadron/data/`
- [x] T11.2 — Mark slice 141 complete in slice plan (`140-slices.pipeline-foundation.md`) and slice design (`141-slice.configuration-externalization.md`)
