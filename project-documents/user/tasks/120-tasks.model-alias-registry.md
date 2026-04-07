---
slice: model-alias-registry
project: squadron
lld: user/slices/120-slice.model-alias-registry.md
dependencies: [review-provider-model-selection]
projectState: Slices 100-119 complete. Review commands work via SDK and non-SDK providers (--profile flag). Model inference uses hardcoded _infer_profile_from_model(). Non-SDK reviews fail because prompts contain file paths but models can't read files. review arch command exists but name is misleading.
dateCreated: 20260321
dateUpdated: 20260321
status: complete
docType: tasks
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

- [x] Rename `src/squadron/review/templates/builtin/arch.yaml` → `src/squadron/review/templates/builtin/slice.yaml`
  - [x] Update `name: arch` → `name: slice` inside the file
  - [x] Update `description` to say "Slice design review" instead of "Architectural review"
  - [x] All other fields (system_prompt, inputs, prompt_template) remain unchanged
- [x] `pyright` and `ruff check` pass

### T2: Rename `review arch` → `review slice` in CLI

- [x] In `src/squadron/cli/commands/review.py`:
  - [x] Rename `review_arch` function to `review_slice`
  - [x] Change `@review_app.command("arch")` → `@review_app.command("slice")`
  - [x] Update `_run_review_command("arch", ...)` → `_run_review_command("slice", ...)`
  - [x] Update `_save_review_file(result, "arch", ...)` → `_save_review_file(result, "slice", ...)`
- [x] Add backward-compatible `review arch` alias command
  - [x] New function `review_arch` decorated with `@review_app.command("arch", hidden=True)`
  - [x] Prints deprecation notice: `"Warning: 'review arch' is deprecated, use 'review slice' instead"`
  - [x] Delegates to `review_slice()` with all same parameters
- [x] `pyright` and `ruff check` pass

### T3: Rename slash command and update references

- [x] Rename `commands/sq/review-arch.md` → `commands/sq/review-slice.md`
  - [x] Update content to reference `sq review slice` instead of `sq review arch`
- [x] Update `commands/sq/run-slice.md` references from `review arch` → `review slice`
- [x] Update `tests/cli/test_install_commands.py`
  - [x] Replace `"review-arch.md"` → `"review-slice.md"` in `EXPECTED_FILES`
  - [x] Update any `EXPECTED_COMMANDS` dict entries referencing `review-arch`

### T4: Tests for rename

- [x] Add/update tests in `tests/cli/test_review_resolve.py` or appropriate file
  - [x] Test `review slice` command works (mock review, verify template name is `"slice"`)
  - [x] Test `review arch` hidden alias delegates to `review_slice` and prints deprecation warning
  - [x] `uv run pytest tests/cli/` — all tests pass
- [x] `uv run pytest` — full suite passes (regression)

### T5: Commit — rename review arch → review slice

- [x] Commit T1-T4 work
  - [x] Message: `refactor: rename review arch to review slice for clarity`

### T6: Create `models/` package with alias registry

- [x] Create `src/squadron/models/__init__.py` (empty or minimal)
- [x] Create `src/squadron/models/aliases.py`
  - [x] Define `ModelAlias` as a `TypedDict` with keys `profile: str` and `model: str`
  - [x] Define `BUILT_IN_ALIASES: dict[str, ModelAlias]` with defaults:
    - [x] `opus` → `{ profile: "sdk", model: "claude-opus-4-6" }`
    - [x] `sonnet` → `{ profile: "sdk", model: "claude-sonnet-4-6" }`
    - [x] `haiku` → `{ profile: "sdk", model: "claude-haiku-4-5-20251001" }`
    - [x] `gpt4o` → `{ profile: "openai", model: "gpt-4o" }`
    - [x] `o3` → `{ profile: "openai", model: "o3-mini" }`
    - [x] `o1` → `{ profile: "openai", model: "o1-preview" }`
  - [x] Add `models_toml_path() -> Path` returning `Path.home() / ".config" / "squadron" / "models.toml"`
  - [x] Add `load_user_aliases() -> dict[str, ModelAlias]` — loads `[aliases]` section from TOML, returns empty dict if file missing
  - [x] Add `get_all_aliases() -> dict[str, ModelAlias]` — merges built-in + user (user overrides)
  - [x] Add `resolve_model_alias(name: str) -> tuple[str, str | None]` — returns `(model_id, profile)` if alias found, `(name, None)` if not
- [x] `pyright` and `ruff check` pass

### T7: Tests for alias registry

- [x] Add tests in `tests/models/test_aliases.py`
  - [x] Test `resolve_model_alias("opus")` → `("claude-opus-4-6", "sdk")`
  - [x] Test `resolve_model_alias("gpt4o")` → `("gpt-4o", "openai")`
  - [x] Test `resolve_model_alias("unknown-model")` → `("unknown-model", None)` (passthrough)
  - [x] Test user alias overrides built-in (create tmp_path `models.toml`, monkeypatch `models_toml_path`)
  - [x] Test user alias adds new entry
  - [x] Test missing `models.toml` returns empty (no error)
  - [x] Test `get_all_aliases()` returns merged dict
  - [x] `uv run pytest tests/models/test_aliases.py` — all tests pass

### T8: Wire alias resolution into `_run_review_command()`

- [x] In `src/squadron/cli/commands/review.py`:
  - [x] Import `resolve_model_alias` from `squadron.models.aliases`
  - [x] In `_run_review_command()`, before `_resolve_model`/`_resolve_profile` calls:
    - [x] `alias_model, alias_profile = resolve_model_alias(model_flag) if model_flag else (None, None)`
    - [x] Pass `alias_model or model_flag` to `_resolve_model()`
    - [x] Pass `profile_flag or alias_profile` to `_resolve_profile()`
  - [x] Remove `_infer_profile_from_model()` function entirely
  - [x] Remove `_infer_profile_from_model` from any imports in test files
  - [x] Update `_resolve_profile()`: remove the model-inference block that called `_infer_profile_from_model()`
- [x] `pyright` and `ruff check` pass

### T9: Tests for alias wiring

- [x] Update tests in `tests/cli/test_review_profile.py`
  - [x] Remove `TestInferProfileFromModel` class (function deleted)
  - [x] Update `TestResolveProfile` tests — model inference now handled by alias pre-processing, not by `_resolve_profile()` directly
  - [x] Add test: `_run_review_command` with `model_flag="gpt4o"` resolves to model `"gpt-4o"` and profile `"openai"` (mock `_execute_review`, verify args)
  - [x] Add test: `_run_review_command` with unknown model passes through unchanged
  - [x] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T10: Commit — model alias registry and wiring

- [x] Commit T6-T9 work
  - [x] Message: `feat: add model alias registry with built-in defaults and user overrides`

### T11: Add `_inject_file_contents()` to `review_client.py`

- [x] Add `_inject_file_contents(prompt: str, inputs: dict[str, str]) -> str` in `src/squadron/review/review_client.py`
  - [x] Define constants: `_MAX_FILE_SIZE = 100_000` (100KB), `_MAX_TOTAL_INJECTION = 500_000` (500KB)
  - [x] Define `_SKIP_KEYS = {"cwd"}` — input keys to skip during file detection
  - [x] Iterate `inputs` items, skip keys in `_SKIP_KEYS`
  - [x] For each value, check `Path(value).is_file()`
  - [x] If file exists: read content, enforce per-file limit (truncate with message), add to injection buffer
  - [x] Enforce total injection limit across all files
  - [x] Append `\n\n## File Contents\n\n` section to prompt with fenced code blocks: `` ```\n{content}\n``` `` keyed by input name
  - [x] Return enriched prompt
- [x] Wire into `_run_non_sdk_review()`: call `_inject_file_contents(prompt, inputs)` after `template.build_prompt(inputs)`
- [x] `pyright` and `ruff check` pass

### T12: Tests for file content injection

- [x] Add tests in `tests/review/test_content_injection.py`
  - [x] Test file contents appear in enriched prompt (create tmp_path files, pass as inputs)
  - [x] Test `cwd` key is skipped (even if value is a valid file path)
  - [x] Test non-existent file path is skipped (no error)
  - [x] Test file exceeding 100KB is truncated with message
  - [x] Test total injection capped at 500KB
  - [x] Test non-file values (e.g., `"."`, `"main"`) are skipped
  - [x] `uv run pytest tests/review/test_content_injection.py` — all tests pass

### T13: Commit — file content injection

- [x] Commit T11-T12 work
  - [x] Message: `feat: inject file contents into prompts for non-SDK reviews`

### T14: Handle code review content injection (diff + files)

- [x] In `_inject_file_contents()` or a new helper `_inject_diff_content()`:
  - [x] If `"diff"` key is in inputs and its value is not a file path:
    - [x] Run `subprocess.run(["git", "diff", inputs["diff"]], capture_output=True, text=True)` in the `cwd` from inputs
    - [x] Inject diff output as a fenced code block under `## Git Diff`
    - [x] Enforce same size limits (truncate large diffs)
  - [x] If `"files"` key is in inputs:
    - [x] Run glob locally to find matching files
    - [x] Inject each file's content (same limits)
- [x] `pyright` and `ruff check` pass

### T15: Tests for code review content injection + integration test

- [x] Add tests in `tests/review/test_content_injection.py`
  - [x] Test diff input triggers `git diff` subprocess (mock `subprocess.run`, verify called with correct args)
  - [x] Test diff output appears in enriched prompt
  - [x] Test large diff is truncated
  - [x] Test files glob input resolves and injects matching file contents (use tmp_path)
- [x] Add integration test in `tests/review/test_content_injection.py`
  - [x] Test full non-SDK review path: alias resolution → content injection → enriched prompt reaches API (mock `AsyncOpenAI`, create tmp_path input files, call `run_review_with_profile()` with a non-SDK profile, verify the prompt sent to the API contains file contents, not just paths)
  - [x] `uv run pytest tests/review/test_content_injection.py` — all tests pass

### T16: Commit — code review content injection

- [x] Commit T14-T15 work
  - [x] Message: `feat: inject git diff and glob results for non-SDK code reviews`

### T17: Add `sq model list` CLI command

- [x] Create `src/squadron/cli/commands/model.py`
  - [x] Create `model_app = typer.Typer(name="model", help="Model alias management.")`
  - [x] Add `model_list` command: `@model_app.command("list")`
  - [x] Loads all aliases via `get_all_aliases()`
  - [x] Also loads built-in aliases to detect user overrides (source tagging)
  - [x] Formats output: `{alias:<12} {profile:<12} {model_id}` with `(user)` suffix for user-defined
  - [x] Uses `rich` for formatted output
- [x] Register `model_app` in `src/squadron/cli/app.py`
  - [x] `app.add_typer(model_app)` alongside existing `review_app`
- [x] `pyright` and `ruff check` pass

### T18: Tests for `sq model list`

- [x] Add tests in `tests/cli/test_model_list.py`
  - [x] Test output contains built-in aliases (opus, sonnet, gpt4o)
  - [x] Test user alias shows `(user)` tag (monkeypatch `models_toml_path` to tmp_path with user alias)
  - [x] Test output format is tabular
  - [x] `uv run pytest tests/cli/test_model_list.py` — all tests pass

### T19: Commit — model list command

- [x] Commit T17-T18 work
  - [x] Message: `feat: add sq model list command for viewing available aliases`

### T20: Update slash commands

- [x] Update `commands/sq/review-slice.md` — document `--model` with alias examples
- [x] Update `commands/sq/review-tasks.md` — document `--model` with alias examples
- [x] Update `commands/sq/review-code.md` — document `--model` with alias examples, note diff injection
- [x] Update `commands/sq/run-slice.md` — note `--model` alias support

### T21: Validation pass

- [x] Full project validation
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean
  - [x] `uv run pyright` — zero errors
  - [x] `uv run pytest` — all tests pass
  - [x] Existing SDK review path works: `sq review slice 118 -v` (regression check)

### T22: Commit — slash commands and validation

- [x] Commit T20-T21 work
  - [x] Message: `docs: update slash commands with model alias and content injection documentation`

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.  Note: actual tests run may differ slightly but cover the same workflow.

- [x] **Live test**: Run `sq review tasks 118 --model gpt4o -v` to verify content injection produces real findings (not "I can't read files")
- [x] **Live test**: Add custom alias to `~/.config/squadron/models.toml`, verify `sq review tasks 118 --model kimi25 -v` works
- [x] **Live test**: Run `sq review arch 118 -v` to verify deprecation notice and backward compat
- [x] **Live test**: Run `sq review code 118 --model gpt4o --diff main -v` to verify diff injection
- [x] **Live test**: Run `sq model list` to verify output
- [x] **Iterate**: Adjust built-in aliases based on real-world model naming
