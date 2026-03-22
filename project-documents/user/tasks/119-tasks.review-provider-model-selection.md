---
slice: review-provider-model-selection
project: squadron
lld: user/slices/119-slice.review-provider-model-selection.md
dependencies: [review-workflow-templates, provider-variants-registry, auth-strategy, composed-workflows]
projectState: Slices 100-118 complete. Review commands work via SDK only. Provider infrastructure (profiles, auth, OpenAI-compatible) exists from slices 111-114. Review auto-save and number shorthand from slice 118. No user-customizable templates yet.
dateCreated: 20260321
dateUpdated: 20260321
reviewUpdated: 20260321
status: in_progress
---

## Context Summary

- Working on `review-provider-model-selection` slice — decouple reviews from hardcoded Claude SDK
- Currently `runner.py` imports `ClaudeSDKClient` directly — reviews can only run via SDK
- This slice adds `--profile` flag, `profile` field in templates, user templates, config defaults
- SDK path preserved exactly via delegation; non-SDK path uses `AsyncOpenAI` directly
- Provider infrastructure already exists: `ProviderProfile`, `get_profile()`, `resolve_auth_strategy()`
- Key files: `src/squadron/review/runner.py`, `src/squadron/review/templates/__init__.py`, `src/squadron/cli/commands/review.py`, `src/squadron/config/keys.py`
- Next planned slice: implementation of this slice, then potentially slice 122 (Anthropic API Provider)

---

## Tasks

### T1: Add `profile` field to `ReviewTemplate` and YAML loader

- [x] Add `profile: str | None = None` field to `ReviewTemplate` dataclass in `src/squadron/review/templates/__init__.py`
  - [x] Field added after existing `model` field
  - [x] Default is `None` (falls back to config or `"sdk"`)
- [x] Update `load_template()` to parse `profile` field from YAML
  - [x] `profile=str(data["profile"]) if "profile" in data else None`
  - [x] Existing templates without `profile` field load without error
- [x] `pyright` and `ruff check` pass on modified file

### T2: Tests for `profile` field on `ReviewTemplate`

- [x] Add tests in `tests/review/test_templates.py` (or new file if needed)
  - [x] Test loading a template YAML with `profile: openrouter` — field is populated
  - [x] Test loading a template YAML without `profile` field — defaults to `None`
  - [x] Test `ReviewTemplate` dataclass has `profile` attribute
  - [x] `uv run pytest tests/review/` — all tests pass

### T3: Add `default_review_profile` config key

- [x] Add config key to `src/squadron/config/keys.py`
  - [x] Key name: `default_review_profile`
  - [x] Type: `str`
  - [x] Default: `None`
  - [x] Description: `"Default provider profile for review commands (e.g. openrouter, sdk)"`
- [x] `pyright` and `ruff check` pass

### T4: Add `_resolve_profile()` helper to `review.py`

- [x] Add `_resolve_profile()` function in `src/squadron/cli/commands/review.py`
  - [x] Resolution chain: CLI flag → template `profile` → config `default_review_profile` → `"sdk"`
  - [x] Signature: `_resolve_profile(flag: str | None, template: ReviewTemplate | None = None, model: str | None = None) -> str`
  - [x] Accept `model` parameter but do not use it yet (inference added in T6)
  - [x] Uses `get_config("default_review_profile")` for config lookup
  - [x] Returns `"sdk"` as final fallback
- [x] `pyright` and `ruff check` pass

### T5: Tests for `_resolve_profile()`

- [x] Add tests in `tests/cli/test_review_profile.py`
  - [x] Test CLI flag takes precedence over template and config
  - [x] Test template `profile` takes precedence over config
  - [x] Test config `default_review_profile` is used when no flag or template profile
  - [x] Test fallback to `"sdk"` when nothing is configured
  - [x] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T6: Add model-to-profile inference

- [x] Add `_infer_profile_from_model(model: str) -> str | None` in `review.py`
  - [x] `opus`, `sonnet`, `haiku`, or starts with `claude-` → `"sdk"`
  - [x] Starts with `gpt-`, `o1-`, `o3-` → `"openai"`
  - [x] Contains `/` (e.g., `anthropic/claude-3.5-sonnet`) → `"openrouter"`
  - [x] Otherwise returns `None` (no inference, fall through to resolution chain)
- [x] Integrate into `_resolve_profile()`: if CLI flag is `None` and model is provided, try inference before template/config fallback

### T7: Tests for model-to-profile inference

- [x] Add tests in `tests/cli/test_review_profile.py`
  - [x] Test `opus` → `"sdk"`
  - [x] Test `claude-opus-4-6` → `"sdk"`
  - [x] Test `gpt-4o` → `"openai"`
  - [x] Test `o3-mini` → `"openai"`
  - [x] Test `anthropic/claude-3.5-sonnet` → `"openrouter"`
  - [x] Test `llama3` → `None` (no inference)
  - [x] Test inference is bypassed when explicit `--profile` flag is provided
  - [x] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T8: Commit — template profile field, config key, profile resolution

- [x] Commit T1-T7 work
  - [x] Message: `feat: add profile field to ReviewTemplate and profile resolution chain`

### T9: Create `review_client.py` with `run_review_with_profile()`

- [x] Create `src/squadron/review/review_client.py`
  - [x] Function signature: `async def run_review_with_profile(template, inputs, *, profile, rules_content, model) -> ReviewResult`
  - [x] If `profile == "sdk"`: delegate to existing `run_review()` from `runner.py` — pass all args through
  - [x] If `profile != "sdk"`:
    - [x] Call `get_profile(profile)` to get `ProviderProfile`
    - [x] Resolve auth via `resolve_auth_strategy()` or direct env var lookup from profile
    - [x] Build prompt from template: `template.build_prompt(inputs)`
    - [x] Build system prompt (same logic as SDK path: template system_prompt + optional rules)
    - [x] Create `AsyncOpenAI(base_url=profile.base_url, api_key=api_key, default_headers=profile.default_headers)`
    - [x] Call `client.chat.completions.create(model=model, messages=[system, user])`
    - [x] Extract text content from response
    - [x] Pass through `parse_review_output()` with template name, inputs, model
    - [x] Return `ReviewResult`
  - [x] Fail explicitly if profile not found (`get_profile` raises `KeyError`)
  - [x] Fail explicitly if API key not resolved for non-local profiles

### T10: Tests for `run_review_with_profile()`

- [x] Add tests in `tests/review/test_review_client.py`
  - [x] Test SDK delegation: `profile="sdk"` calls `run_review()` (mock `run_review`, verify called)
  - [x] Test non-SDK path: `profile="openrouter"` creates AsyncOpenAI client (mock `AsyncOpenAI`, verify `base_url` and `api_key`)
  - [x] Test non-SDK path returns valid `ReviewResult` (mock API response with summary/findings format)
  - [x] Test unknown profile raises error
  - [x] Test missing API key raises error (mock env to not have key)
  - [x] Test non-SDK `ReviewResult` has all fields needed for auto-save and `--json` output (verify `summary`, `findings`, `verdict`, `model` are populated — ensures SC9 parity)
  - [x] `uv run pytest tests/review/test_review_client.py` — all tests pass

### T11: Commit — review client

- [x] Commit T9-T10 work
  - [x] Message: `feat: add run_review_with_profile() for provider-agnostic review execution`

### T12: Wire `--profile` into CLI review commands

- [x] Update `review_arch` in `review.py`
  - [x] Add `--profile` option: `typer.Option(None, "--profile", help="Provider profile (e.g. openrouter, openai, local, sdk)")`
  - [x] Call `_resolve_profile(profile_flag, template, model)` to get resolved profile
  - [x] Wire `profile` through `_run_review_command()` — add `profile: str` parameter and have it call `run_review_with_profile()` internally (preserves auto-save, JSON output, error handling in one place)
  - [x] Pass resolved profile from each command handler into `_run_review_command()`
- [x] Update `review_tasks` — same pattern
- [x] Update `review_code` — same pattern
- [x] Existing behavior unchanged when `--profile` not specified (SDK fallback)
- [x] `--profile` and `--model` work together correctly
- [x] `pyright` and `ruff check` pass

### T13: Tests for CLI `--profile` flag

- [x] Add tests in `tests/cli/test_review_profile.py`
  - [x] Test `review arch 118 --profile openrouter` passes profile through (mock resolver + review client)
  - [x] Test `review arch 118` without `--profile` defaults to SDK
  - [x] Test `review arch 118 --profile openai --model gpt-4o` passes both through
  - [x] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T14: Commit — CLI profile flag

- [x] Commit T12-T13 work
  - [x] Message: `feat: add --profile flag to sq review CLI commands`

### T15: User template loading

- [x] Update `load_builtin_templates()` → `load_all_templates()` in `src/squadron/review/templates/__init__.py`
  - [x] Rename function to `load_all_templates()`
  - [x] Add backward-compatible alias: `load_builtin_templates = load_all_templates`
  - [x] After loading built-in templates, scan `~/.config/squadron/templates/` for `.yaml` files
  - [x] User templates with same `name` override built-in (register overwrites)
  - [x] Handle missing user directory gracefully (no error if dir doesn't exist)
  - [x] User template directory path: `Path.home() / ".config" / "squadron" / "templates"`
- [x] Update all call sites that reference `load_builtin_templates` (should work via alias)
  - [x] Explicitly update `review list` command to use `load_all_templates()` so it displays both built-in and user templates

### T16: Tests for user template loading

- [x] Add tests in `tests/review/test_user_templates.py`
  - [x] Test user template overrides built-in by name (create tmp_path with yaml, verify override)
  - [x] Test user template adds new review type (name not in built-in)
  - [x] Test missing user directory doesn't error
  - [x] Test `sq review list` shows both built-in and user templates
  - [x] `uv run pytest tests/review/test_user_templates.py` — all tests pass

### T17: Commit — user templates

- [x] Commit T15-T16 work
  - [x] Message: `feat: load user-customizable review templates from ~/.config/squadron/templates/`

### T18: Update slash commands for `--profile`

- [x] Update `commands/sq/review-arch.md` — document `--profile` flag
- [x] Update `commands/sq/review-tasks.md` — document `--profile` flag
- [x] Update `commands/sq/review-code.md` — document `--profile` flag
- [x] Update `commands/sq/run-slice.md` — note that reviews can use `--profile` if desired

### T19: Validation pass

- [x] Full project validation
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean
  - [x] `uv run pyright` — zero errors
  - [x] `uv run pytest` — all tests pass
  - [x] Existing SDK review path works: `sq review arch 118 -v` (regression check)

### T20: Commit — slash commands and validation

- [x] Commit T18-T19 work
  - [x] Message: `docs: update slash commands with --profile flag documentation`

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [ ] **Live test**: Run `sq review arch 118 --profile openrouter --model anthropic/claude-3.5-sonnet -v` to verify OpenRouter routing
- [ ] **Live test**: Run `sq review arch 118 --model gpt-4o -v` to verify model-to-profile inference
- [ ] **Live test**: Create a user template in `~/.config/squadron/templates/` and verify it overrides built-in
- [ ] **Live test**: Run `sq config set default_review_profile openrouter` then `sq review arch 118 -v` to verify config default

