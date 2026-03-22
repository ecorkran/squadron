---
slice: model-alias-registry
project: squadron
lld: user/slices/120-slice.model-alias-registry.md
dependencies: [review-provider-model-selection]
projectState: Slices 100-119 complete. Review commands work via SDK and non-SDK providers (--profile flag). Model inference uses hardcoded _infer_profile_from_model(). Non-SDK reviews fail because prompts contain file paths but models can't read files. review arch command exists but name is misleading.
dateCreated: 20260321
dateUpdated: 20260321
status: not_started
---

## Context Summary

- Working on `model-alias-registry` slice — three goals: model alias registry, content injection for non-SDK reviews, rename `review arch` → `review slice`
- Currently `_infer_profile_from_model()` in `review.py` uses hardcoded pattern-matching — not user-extensible
- Non-SDK reviews receive file paths in prompts but can't read them — need content injection in `review_client.py`
- `review arch` is misleading — it reviews a slice design, not an architecture doc
- Key files: `src/squadron/cli/commands/review.py`, `src/squadron/review/review_client.py`, `src/squadron/review/templates/builtin/arch.yaml`, `commands/sq/review-arch.md`
- New files: `src/squadron/models/__init__.py`, `src/squadron/models/aliases.py`
- Alias resolution happens once in `_run_review_command()` as pre-processing, then threads through existing `_resolve_model()`/`_resolve_profile()`

---

## Tasks

### T1: Rename `review arch` → `review slice` in template YAML

- [ ] Rename `src/squadron/review/templates/builtin/arch.yaml` → `src/squadron/review/templates/builtin/slice.yaml`
  - [ ] Update `name: arch` → `name: slice` inside the file
  - [ ] Update `description` to say "Slice design review" instead of "Architectural review"
  - [ ] All other fields (system_prompt, inputs, prompt_template) remain unchanged
- [ ] `pyright` and `ruff check` pass

### T2: Rename `review arch` → `review slice` in CLI

- [ ] In `src/squadron/cli/commands/review.py`:
  - [ ] Rename `review_arch` function to `review_slice`
  - [ ] Change `@review_app.command("arch")` → `@review_app.command("slice")`
  - [ ] Update `_run_review_command("arch", ...)` → `_run_review_command("slice", ...)`
  - [ ] Update `_save_review_file(result, "arch", ...)` → `_save_review_file(result, "slice", ...)`
- [ ] Add backward-compatible `review arch` alias command
  - [ ] New function `review_arch` decorated with `@review_app.command("arch", hidden=True)`
  - [ ] Prints deprecation notice: `"Warning: 'review arch' is deprecated, use 'review slice' instead"`
  - [ ] Delegates to `review_slice()` with all same parameters
- [ ] `pyright` and `ruff check` pass

### T3: Rename slash command and update references

- [ ] Rename `commands/sq/review-arch.md` → `commands/sq/review-slice.md`
  - [ ] Update content to reference `sq review slice` instead of `sq review arch`
- [ ] Update `commands/sq/run-slice.md` references from `review arch` → `review slice`
- [ ] Update `tests/cli/test_install_commands.py`
  - [ ] Replace `"review-arch.md"` → `"review-slice.md"` in `EXPECTED_FILES`
  - [ ] Update any `EXPECTED_COMMANDS` dict entries referencing `review-arch`

### T4: Tests for rename

- [ ] Add/update tests in `tests/cli/test_review_resolve.py` or appropriate file
  - [ ] Test `review slice` command works (mock review, verify template name is `"slice"`)
  - [ ] Test `review arch` hidden alias delegates to `review_slice` and prints deprecation warning
  - [ ] `uv run pytest tests/cli/` — all tests pass
- [ ] `uv run pytest` — full suite passes (regression)

### T5: Commit — rename review arch → review slice

- [ ] Commit T1-T4 work
  - [ ] Message: `refactor: rename review arch to review slice for clarity`

### T6: Create `models/` package with alias registry

- [ ] Create `src/squadron/models/__init__.py` (empty or minimal)
- [ ] Create `src/squadron/models/aliases.py`
  - [ ] Define `ModelAlias` as a `TypedDict` with keys `profile: str` and `model: str`
  - [ ] Define `BUILT_IN_ALIASES: dict[str, ModelAlias]` with defaults:
    - [ ] `opus` → `{ profile: "sdk", model: "claude-opus-4-6" }`
    - [ ] `sonnet` → `{ profile: "sdk", model: "claude-sonnet-4-6" }`
    - [ ] `haiku` → `{ profile: "sdk", model: "claude-haiku-4-5-20251001" }`
    - [ ] `gpt4o` → `{ profile: "openai", model: "gpt-4o" }`
    - [ ] `o3` → `{ profile: "openai", model: "o3-mini" }`
    - [ ] `o1` → `{ profile: "openai", model: "o1-preview" }`
  - [ ] Add `models_toml_path() -> Path` returning `Path.home() / ".config" / "squadron" / "models.toml"`
  - [ ] Add `load_user_aliases() -> dict[str, ModelAlias]` — loads `[aliases]` section from TOML, returns empty dict if file missing
  - [ ] Add `get_all_aliases() -> dict[str, ModelAlias]` — merges built-in + user (user overrides)
  - [ ] Add `resolve_model_alias(name: str) -> tuple[str, str | None]` — returns `(model_id, profile)` if alias found, `(name, None)` if not
- [ ] `pyright` and `ruff check` pass

### T7: Tests for alias registry

- [ ] Add tests in `tests/models/test_aliases.py`
  - [ ] Test `resolve_model_alias("opus")` → `("claude-opus-4-6", "sdk")`
  - [ ] Test `resolve_model_alias("gpt4o")` → `("gpt-4o", "openai")`
  - [ ] Test `resolve_model_alias("unknown-model")` → `("unknown-model", None)` (passthrough)
  - [ ] Test user alias overrides built-in (create tmp_path `models.toml`, monkeypatch `models_toml_path`)
  - [ ] Test user alias adds new entry
  - [ ] Test missing `models.toml` returns empty (no error)
  - [ ] Test `get_all_aliases()` returns merged dict
  - [ ] `uv run pytest tests/models/test_aliases.py` — all tests pass

### T8: Wire alias resolution into `_run_review_command()`

- [ ] In `src/squadron/cli/commands/review.py`:
  - [ ] Import `resolve_model_alias` from `squadron.models.aliases`
  - [ ] In `_run_review_command()`, before `_resolve_model`/`_resolve_profile` calls:
    - [ ] `alias_model, alias_profile = resolve_model_alias(model_flag) if model_flag else (None, None)`
    - [ ] Pass `alias_model or model_flag` to `_resolve_model()`
    - [ ] Pass `profile_flag or alias_profile` to `_resolve_profile()`
  - [ ] Remove `_infer_profile_from_model()` function entirely
  - [ ] Remove `_infer_profile_from_model` from any imports in test files
  - [ ] Update `_resolve_profile()`: remove the model-inference block that called `_infer_profile_from_model()`
- [ ] `pyright` and `ruff check` pass

### T9: Tests for alias wiring

- [ ] Update tests in `tests/cli/test_review_profile.py`
  - [ ] Remove `TestInferProfileFromModel` class (function deleted)
  - [ ] Update `TestResolveProfile` tests — model inference now handled by alias pre-processing, not by `_resolve_profile()` directly
  - [ ] Add test: `_run_review_command` with `model_flag="gpt4o"` resolves to model `"gpt-4o"` and profile `"openai"` (mock `_execute_review`, verify args)
  - [ ] Add test: `_run_review_command` with unknown model passes through unchanged
  - [ ] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T10: Commit — model alias registry and wiring

- [ ] Commit T6-T9 work
  - [ ] Message: `feat: add model alias registry with built-in defaults and user overrides`

### T11: Add `_inject_file_contents()` to `review_client.py`

- [ ] Add `_inject_file_contents(prompt: str, inputs: dict[str, str]) -> str` in `src/squadron/review/review_client.py`
  - [ ] Define constants: `_MAX_FILE_SIZE = 100_000` (100KB), `_MAX_TOTAL_INJECTION = 500_000` (500KB)
  - [ ] Define `_SKIP_KEYS = {"cwd"}` — input keys to skip during file detection
  - [ ] Iterate `inputs` items, skip keys in `_SKIP_KEYS`
  - [ ] For each value, check `Path(value).is_file()`
  - [ ] If file exists: read content, enforce per-file limit (truncate with message), add to injection buffer
  - [ ] Enforce total injection limit across all files
  - [ ] Append `\n\n## File Contents\n\n` section to prompt with fenced code blocks: `` ```\n{content}\n``` `` keyed by input name
  - [ ] Return enriched prompt
- [ ] Wire into `_run_non_sdk_review()`: call `_inject_file_contents(prompt, inputs)` after `template.build_prompt(inputs)`
- [ ] `pyright` and `ruff check` pass

### T12: Tests for file content injection

- [ ] Add tests in `tests/review/test_content_injection.py`
  - [ ] Test file contents appear in enriched prompt (create tmp_path files, pass as inputs)
  - [ ] Test `cwd` key is skipped (even if value is a valid file path)
  - [ ] Test non-existent file path is skipped (no error)
  - [ ] Test file exceeding 100KB is truncated with message
  - [ ] Test total injection capped at 500KB
  - [ ] Test non-file values (e.g., `"."`, `"main"`) are skipped
  - [ ] `uv run pytest tests/review/test_content_injection.py` — all tests pass

### T13: Commit — file content injection

- [ ] Commit T11-T12 work
  - [ ] Message: `feat: inject file contents into prompts for non-SDK reviews`

### T14: Handle code review content injection (diff + files)

- [ ] In `_inject_file_contents()` or a new helper `_inject_diff_content()`:
  - [ ] If `"diff"` key is in inputs and its value is not a file path:
    - [ ] Run `subprocess.run(["git", "diff", inputs["diff"]], capture_output=True, text=True)` in the `cwd` from inputs
    - [ ] Inject diff output as a fenced code block under `## Git Diff`
    - [ ] Enforce same size limits (truncate large diffs)
  - [ ] If `"files"` key is in inputs:
    - [ ] Run glob locally to find matching files
    - [ ] Inject each file's content (same limits)
- [ ] `pyright` and `ruff check` pass

### T15: Tests for code review content injection

- [ ] Add tests in `tests/review/test_content_injection.py`
  - [ ] Test diff input triggers `git diff` subprocess (mock `subprocess.run`, verify called with correct args)
  - [ ] Test diff output appears in enriched prompt
  - [ ] Test large diff is truncated
  - [ ] Test files glob input resolves and injects matching file contents (use tmp_path)
  - [ ] `uv run pytest tests/review/test_content_injection.py` — all tests pass

### T16: Commit — code review content injection

- [ ] Commit T14-T15 work
  - [ ] Message: `feat: inject git diff and glob results for non-SDK code reviews`

### T17: Add `sq model list` CLI command

- [ ] Create `src/squadron/cli/commands/model.py`
  - [ ] Create `model_app = typer.Typer(name="model", help="Model alias management.")`
  - [ ] Add `model_list` command: `@model_app.command("list")`
  - [ ] Loads all aliases via `get_all_aliases()`
  - [ ] Also loads built-in aliases to detect user overrides (source tagging)
  - [ ] Formats output: `{alias:<12} {profile:<12} {model_id}` with `(user)` suffix for user-defined
  - [ ] Uses `rich` for formatted output
- [ ] Register `model_app` in `src/squadron/cli/app.py`
  - [ ] `app.add_typer(model_app)` alongside existing `review_app`
- [ ] `pyright` and `ruff check` pass

### T18: Tests for `sq model list`

- [ ] Add tests in `tests/cli/test_model_list.py`
  - [ ] Test output contains built-in aliases (opus, sonnet, gpt4o)
  - [ ] Test user alias shows `(user)` tag (monkeypatch `models_toml_path` to tmp_path with user alias)
  - [ ] Test output format is tabular
  - [ ] `uv run pytest tests/cli/test_model_list.py` — all tests pass

### T19: Commit — model list command

- [ ] Commit T17-T18 work
  - [ ] Message: `feat: add sq model list command for viewing available aliases`

### T20: Update slash commands

- [ ] Update `commands/sq/review-slice.md` — document `--model` with alias examples
- [ ] Update `commands/sq/review-tasks.md` — document `--model` with alias examples
- [ ] Update `commands/sq/review-code.md` — document `--model` with alias examples, note diff injection
- [ ] Update `commands/sq/run-slice.md` — note `--model` alias support

### T21: Validation pass

- [ ] Full project validation
  - [ ] `uv run ruff check` — clean
  - [ ] `uv run ruff format --check` — clean
  - [ ] `uv run pyright` — zero errors
  - [ ] `uv run pytest` — all tests pass
  - [ ] Existing SDK review path works: `sq review slice 118 -v` (regression check)

### T22: Commit — slash commands and validation

- [ ] Commit T20-T21 work
  - [ ] Message: `docs: update slash commands with model alias and content injection documentation`

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [ ] **Live test**: Run `sq review tasks 118 --model gpt4o -v` to verify content injection produces real findings (not "I can't read files")
- [ ] **Live test**: Add custom alias to `~/.config/squadron/models.toml`, verify `sq review tasks 118 --model kimi25 -v` works
- [ ] **Live test**: Run `sq review arch 118 -v` to verify deprecation notice and backward compat
- [ ] **Live test**: Run `sq review code 118 --model gpt4o --diff main -v` to verify diff injection
- [ ] **Live test**: Run `sq model list` to verify output
- [ ] **Iterate**: Adjust built-in aliases based on real-world model naming
