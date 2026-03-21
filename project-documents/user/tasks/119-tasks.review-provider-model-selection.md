---
slice: review-provider-model-selection
project: squadron
lld: user/slices/119-slice.review-provider-model-selection.md
dependencies: [review-workflow-templates, provider-variants-registry, auth-strategy, composed-workflows]
projectState: Slices 100-118 complete. Review commands work via SDK only. Provider infrastructure (profiles, auth, OpenAI-compatible) exists from slices 111-114. Review auto-save and number shorthand from slice 118. No user-customizable templates yet.
dateCreated: 20260321
dateUpdated: 20260321
status: not_started
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

- [ ] Add `profile: str | None = None` field to `ReviewTemplate` dataclass in `src/squadron/review/templates/__init__.py`
  - [ ] Field added after existing `model` field
  - [ ] Default is `None` (falls back to config or `"sdk"`)
- [ ] Update `load_template()` to parse `profile` field from YAML
  - [ ] `profile=str(data["profile"]) if "profile" in data else None`
  - [ ] Existing templates without `profile` field load without error
- [ ] `pyright` and `ruff check` pass on modified file

### T2: Tests for `profile` field on `ReviewTemplate`

- [ ] Add tests in `tests/review/test_templates.py` (or new file if needed)
  - [ ] Test loading a template YAML with `profile: openrouter` — field is populated
  - [ ] Test loading a template YAML without `profile` field — defaults to `None`
  - [ ] Test `ReviewTemplate` dataclass has `profile` attribute
  - [ ] `uv run pytest tests/review/` — all tests pass

### T3: Add `default_review_profile` config key

- [ ] Add config key to `src/squadron/config/keys.py`
  - [ ] Key name: `default_review_profile`
  - [ ] Type: `str`
  - [ ] Default: `None`
  - [ ] Description: `"Default provider profile for review commands (e.g. openrouter, sdk)"`
- [ ] `pyright` and `ruff check` pass

### T4: Add `_resolve_profile()` helper to `review.py`

- [ ] Add `_resolve_profile()` function in `src/squadron/cli/commands/review.py`
  - [ ] Resolution chain: CLI flag → template `profile` → config `default_review_profile` → `"sdk"`
  - [ ] Signature: `_resolve_profile(flag: str | None, template: ReviewTemplate | None = None) -> str`
  - [ ] Uses `get_config("default_review_profile")` for config lookup
  - [ ] Returns `"sdk"` as final fallback
- [ ] `pyright` and `ruff check` pass

### T5: Tests for `_resolve_profile()`

- [ ] Add tests in `tests/cli/test_review_profile.py`
  - [ ] Test CLI flag takes precedence over template and config
  - [ ] Test template `profile` takes precedence over config
  - [ ] Test config `default_review_profile` is used when no flag or template profile
  - [ ] Test fallback to `"sdk"` when nothing is configured
  - [ ] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T6: Add model-to-profile inference

- [ ] Add `_infer_profile_from_model(model: str) -> str | None` in `review.py`
  - [ ] `opus`, `sonnet`, `haiku`, or starts with `claude-` → `"sdk"`
  - [ ] Starts with `gpt-`, `o1-`, `o3-` → `"openai"`
  - [ ] Contains `/` (e.g., `anthropic/claude-3.5-sonnet`) → `"openrouter"`
  - [ ] Otherwise returns `None` (no inference, fall through to resolution chain)
- [ ] Integrate into `_resolve_profile()`: if CLI flag is `None` and model is provided, try inference before template/config fallback

### T7: Tests for model-to-profile inference

- [ ] Add tests in `tests/cli/test_review_profile.py`
  - [ ] Test `opus` → `"sdk"`
  - [ ] Test `claude-opus-4-6` → `"sdk"`
  - [ ] Test `gpt-4o` → `"openai"`
  - [ ] Test `o3-mini` → `"openai"`
  - [ ] Test `anthropic/claude-3.5-sonnet` → `"openrouter"`
  - [ ] Test `llama3` → `None` (no inference)
  - [ ] Test inference is bypassed when explicit `--profile` flag is provided
  - [ ] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T8: Commit — template profile field, config key, profile resolution

- [ ] Commit T1-T7 work
  - [ ] Message: `feat: add profile field to ReviewTemplate and profile resolution chain`

### T9: Create `review_client.py` with `run_review_with_profile()`

- [ ] Create `src/squadron/review/review_client.py`
  - [ ] Function signature: `async def run_review_with_profile(template, inputs, *, profile, rules_content, model) -> ReviewResult`
  - [ ] If `profile == "sdk"`: delegate to existing `run_review()` from `runner.py` — pass all args through
  - [ ] If `profile != "sdk"`:
    - [ ] Call `get_profile(profile)` to get `ProviderProfile`
    - [ ] Resolve auth via `resolve_auth_strategy()` or direct env var lookup from profile
    - [ ] Build prompt from template: `template.build_prompt(inputs)`
    - [ ] Build system prompt (same logic as SDK path: template system_prompt + optional rules)
    - [ ] Create `AsyncOpenAI(base_url=profile.base_url, api_key=api_key, default_headers=profile.default_headers)`
    - [ ] Call `client.chat.completions.create(model=model, messages=[system, user])`
    - [ ] Extract text content from response
    - [ ] Pass through `parse_review_output()` with template name, inputs, model
    - [ ] Return `ReviewResult`
  - [ ] Fail explicitly if profile not found (`get_profile` raises `KeyError`)
  - [ ] Fail explicitly if API key not resolved for non-local profiles

### T10: Tests for `run_review_with_profile()`

- [ ] Add tests in `tests/review/test_review_client.py`
  - [ ] Test SDK delegation: `profile="sdk"` calls `run_review()` (mock `run_review`, verify called)
  - [ ] Test non-SDK path: `profile="openrouter"` creates AsyncOpenAI client (mock `AsyncOpenAI`, verify `base_url` and `api_key`)
  - [ ] Test non-SDK path returns valid `ReviewResult` (mock API response with summary/findings format)
  - [ ] Test unknown profile raises error
  - [ ] Test missing API key raises error (mock env to not have key)
  - [ ] `uv run pytest tests/review/test_review_client.py` — all tests pass

### T11: Commit — review client

- [ ] Commit T9-T10 work
  - [ ] Message: `feat: add run_review_with_profile() for provider-agnostic review execution`

### T12: Wire `--profile` into CLI review commands

- [ ] Update `review_arch` in `review.py`
  - [ ] Add `--profile` option: `typer.Option(None, "--profile", help="Provider profile (e.g. openrouter, openai, local, sdk)")`
  - [ ] Call `_resolve_profile(profile_flag, template, model)` to get resolved profile
  - [ ] Replace `_run_review_command()` call with `run_review_with_profile()` (or wire profile through `_run_review_command`)
  - [ ] Pass resolved profile to the review execution
- [ ] Update `review_tasks` — same pattern
- [ ] Update `review_code` — same pattern
- [ ] Existing behavior unchanged when `--profile` not specified (SDK fallback)
- [ ] `--profile` and `--model` work together correctly
- [ ] `pyright` and `ruff check` pass

### T13: Tests for CLI `--profile` flag

- [ ] Add tests in `tests/cli/test_review_profile.py`
  - [ ] Test `review arch 118 --profile openrouter` passes profile through (mock resolver + review client)
  - [ ] Test `review arch 118` without `--profile` defaults to SDK
  - [ ] Test `review arch 118 --profile openai --model gpt-4o` passes both through
  - [ ] `uv run pytest tests/cli/test_review_profile.py` — all tests pass

### T14: Commit — CLI profile flag

- [ ] Commit T12-T13 work
  - [ ] Message: `feat: add --profile flag to sq review CLI commands`

### T15: User template loading

- [ ] Update `load_builtin_templates()` → `load_all_templates()` in `src/squadron/review/templates/__init__.py`
  - [ ] Rename function to `load_all_templates()`
  - [ ] Add backward-compatible alias: `load_builtin_templates = load_all_templates`
  - [ ] After loading built-in templates, scan `~/.config/squadron/templates/` for `.yaml` files
  - [ ] User templates with same `name` override built-in (register overwrites)
  - [ ] Handle missing user directory gracefully (no error if dir doesn't exist)
  - [ ] User template directory path: `Path.home() / ".config" / "squadron" / "templates"`
- [ ] Update all call sites that reference `load_builtin_templates` (should work via alias)

### T16: Tests for user template loading

- [ ] Add tests in `tests/review/test_user_templates.py`
  - [ ] Test user template overrides built-in by name (create tmp_path with yaml, verify override)
  - [ ] Test user template adds new review type (name not in built-in)
  - [ ] Test missing user directory doesn't error
  - [ ] Test `sq review list` shows both built-in and user templates
  - [ ] `uv run pytest tests/review/test_user_templates.py` — all tests pass

### T17: Commit — user templates

- [ ] Commit T15-T16 work
  - [ ] Message: `feat: load user-customizable review templates from ~/.config/squadron/templates/`

### T18: Update slash commands for `--profile`

- [ ] Update `commands/sq/review-arch.md` — document `--profile` flag
- [ ] Update `commands/sq/review-tasks.md` — document `--profile` flag
- [ ] Update `commands/sq/review-code.md` — document `--profile` flag
- [ ] Update `commands/sq/run-slice.md` — note that reviews can use `--profile` if desired

### T19: Validation pass

- [ ] Full project validation
  - [ ] `uv run ruff check` — clean
  - [ ] `uv run ruff format --check` — clean
  - [ ] `uv run pyright` — zero errors
  - [ ] `uv run pytest` — all tests pass
  - [ ] Existing SDK review path works: `sq review arch 118 -v` (regression check)

### T20: Commit — slash commands and validation

- [ ] Commit T18-T19 work
  - [ ] Message: `docs: update slash commands with --profile flag documentation`

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [ ] **Live test**: Run `sq review arch 118 --profile openrouter --model anthropic/claude-3.5-sonnet -v` to verify OpenRouter routing
- [ ] **Live test**: Run `sq review arch 118 --model gpt-4o -v` to verify model-to-profile inference
- [ ] **Live test**: Create a user template in `~/.config/squadron/templates/` and verify it overrides built-in
- [ ] **Live test**: Run `sq config set default_review_profile openrouter` then `sq review arch 118 -v` to verify config default
- [ ] **Iterate**: Adjust inference patterns if needed based on real-world model names
