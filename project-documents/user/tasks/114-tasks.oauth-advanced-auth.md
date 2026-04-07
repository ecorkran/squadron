---
slice: auth-strategy-credential-management
project: squadron
lld: project-documents/user/slices/114-slice.oauth-advanced-auth.md
dependencies: [openai-provider-core, provider-variants]
projectState: Slices 111-113 complete. OpenAICompatibleProvider has inline credential resolution (api_key → profile env var → OPENAI_API_KEY → localhost placeholder → error). ProviderProfile dataclass in profiles.py with TOML loading. CLI has spawn, config, review, models commands. 377+ tests passing.
status: complete
dateCreated: 20260301
dateUpdated: 20260301
docType: tasks
---

## Context Summary

- Working on **auth-strategy-credential-management** (slice 114)
- Extracts credential resolution from `OpenAICompatibleProvider.create_agent()` into an `AuthStrategy` protocol
- `ApiKeyStrategy` is the concrete implementation — same behavior as current inline logic
- Adds `auth_type` field to `ProviderProfile` for strategy dispatch
- CLI gains `auth login <profile>` and `auth status` commands
- Extension point for future OAuth/token strategies (slice 116: Codex Agent Integration)
- Depends on slices 111 (provider core) and 113 (provider variants/profiles)
- Full design: `project-documents/user/slices/114-slice.oauth-advanced-auth.md`

---

## Tasks

### Auth Strategy Protocol & API Key Implementation

- [x] **T1: Create AuthStrategy protocol and ApiKeyStrategy**
  - [x] Create `src/orchestration/providers/auth.py`
  - [x] `AuthStrategy` as `typing.Protocol` with `runtime_checkable` decorator
  - [x] Three methods: `async get_credentials() -> dict[str, str]`, `async refresh_if_needed() -> None`, `is_valid() -> bool`
  - [x] `ApiKeyStrategy` class implementing the protocol with `__init__` parameters: `explicit_key: str | None`, `env_var: str | None`, `fallback_env_var: str` (default `"OPENAI_API_KEY"`), `base_url: str | None`
  - [x] `get_credentials()` resolution order: explicit_key → `os.environ[env_var]` → `os.environ[fallback_env_var]` → localhost placeholder `"not-needed"` → raise `ProviderAuthError`. Returns `{"api_key": "<value>"}`
  - [x] `refresh_if_needed()` is a no-op (API keys don't expire)
  - [x] `is_valid()` returns `True` if any key source resolves to a non-empty value
  - [x] Success: module importable; `ApiKeyStrategy` satisfies `isinstance(strategy, AuthStrategy)`; pyright clean

- [x] **T2: Test ApiKeyStrategy**
  - [x] Create `tests/providers/test_auth.py`
  - [x] `test_explicit_key_wins` — explicit_key set → returns that key, ignores env vars
  - [x] `test_env_var_from_profile` — no explicit_key, `env_var="CUSTOM_KEY"` set in env → returns env var value
  - [x] `test_env_var_precedence_over_fallback` — both `env_var` and `fallback_env_var` set → uses `env_var`
  - [x] `test_fallback_env_var` — only `OPENAI_API_KEY` set → uses it
  - [x] `test_localhost_placeholder` — no keys set, `base_url="http://localhost:11434/v1"` → returns `"not-needed"`
  - [x] `test_127_0_0_1_placeholder` — no keys, `base_url="http://127.0.0.1:8080/v1"` → returns `"not-needed"`
  - [x] `test_no_key_remote_raises` — no keys, `base_url="https://api.example.com"` → raises `ProviderAuthError`
  - [x] `test_no_key_no_url_raises` — no keys, no base_url → raises `ProviderAuthError`
  - [x] `test_is_valid_with_key` — env var set → `is_valid()` returns `True`
  - [x] `test_is_valid_without_key` — nothing set, remote URL → `is_valid()` returns `False`
  - [x] `test_is_valid_localhost` — nothing set, localhost URL → `is_valid()` returns `True`
  - [x] `test_refresh_is_noop` — `refresh_if_needed()` completes without error
  - [x] Success: all tests pass; ruff clean

- [x] **T3: Commit auth strategy infrastructure**
  - [x] `ruff check` and `ruff format` clean
  - [x] `pyright` clean on new files
  - [x] Commit: `feat: add AuthStrategy protocol and ApiKeyStrategy`

### Strategy Resolution & Registry

- [x] **T4: Create strategy resolution factory and registry**
  - [x] Add to `src/orchestration/providers/auth.py`:
  - [x] `AUTH_STRATEGIES: dict[str, type]` mapping `"api_key"` → `ApiKeyStrategy`
  - [x] `resolve_auth_strategy(config: AgentConfig, profile: ProviderProfile | None = None) -> AuthStrategy` factory function
  - [x] Reads `auth_type` from profile (default `"api_key"` if no profile)
  - [x] Looks up strategy class in `AUTH_STRATEGIES`; raises `ProviderAuthError` for unknown `auth_type`
  - [x] Constructs `ApiKeyStrategy` with correct parameters extracted from config and profile
  - [x] Success: `resolve_auth_strategy` returns correct strategy for `api_key` type; raises for unknown type

- [x] **T5: Test strategy resolution**
  - [x] `test_resolve_api_key_strategy_default` — no profile → returns `ApiKeyStrategy`
  - [x] `test_resolve_api_key_strategy_with_profile` — profile with `auth_type="api_key"` → returns `ApiKeyStrategy` with profile's `api_key_env`
  - [x] `test_resolve_unknown_auth_type_raises` — profile with `auth_type="unknown"` → raises `ProviderAuthError` with descriptive message
  - [x] `test_resolve_no_profile_uses_credentials` — config with `credentials={"api_key_env": "MY_KEY"}` and no profile → strategy uses `MY_KEY` env var
  - [x] Success: all tests pass; ruff clean

- [x] **T6: Commit strategy resolution**
  - [x] Commit: `feat: add auth strategy resolution factory`

### ProviderProfile Extension

- [x] **T7: Add auth_type field to ProviderProfile**
  - [x] Add `auth_type: str = "api_key"` field to `ProviderProfile` dataclass in `profiles.py`
  - [x] Update `load_user_profiles()` to read `auth_type` from TOML (with default `"api_key"` if absent)
  - [x] All built-in profiles retain implicit default `"api_key"` — no changes to `BUILT_IN_PROFILES`
  - [x] Success: `ProviderProfile` has `auth_type` field; existing profile tests still pass; `get_profile("openai").auth_type == "api_key"`

- [x] **T8: Test auth_type on ProviderProfile**
  - [x] `test_builtin_profiles_have_api_key_auth_type` — all built-in profiles have `auth_type == "api_key"`
  - [x] `test_user_profile_with_custom_auth_type` — TOML profile with `auth_type = "oauth"` → loaded profile has `auth_type == "oauth"`
  - [x] `test_user_profile_without_auth_type_defaults` — TOML profile without `auth_type` → defaults to `"api_key"`
  - [x] Success: all profile tests pass (old and new); ruff clean

- [x] **T9: Commit profile extension**
  - [x] Commit: `feat: add auth_type field to ProviderProfile`

### Provider Refactor

- [x] **T10: Refactor OpenAICompatibleProvider to use AuthStrategy**
  - [x] Modify `create_agent()` in `src/orchestration/providers/openai/provider.py`
  - [x] Replace inline credential resolution (lines 29-50) with:
    1. Build profile from `config.credentials` if available (or `None`)
    2. Call `resolve_auth_strategy(config, profile)`
    3. Call `await strategy.refresh_if_needed()`
    4. Call `await strategy.get_credentials()` → extract `api_key`
  - [x] Keep `default_headers` handling from `config.credentials` unchanged
  - [x] Import `resolve_auth_strategy` from `orchestration.providers.auth`
  - [x] Import `ProviderProfile` from `orchestration.providers.profiles` if needed for profile construction
  - [x] Success: `create_agent()` no longer contains inline env var lookups; delegates to strategy

- [x] **T11: Verify provider refactor — regression tests**
  - [x] Run full existing test suite: `pytest tests/`
  - [x] All existing provider tests pass without modification (behavior is identical)
  - [x] All existing CLI spawn/profile tests pass without modification
  - [x] Run `pyright` — zero errors
  - [x] Success: zero test failures; zero pyright errors; no behavior change

- [x] **T12: Commit provider refactor**
  - [x] Commit: `refactor: delegate credential resolution to AuthStrategy`

### CLI Auth Commands

- [x] **T13: Create auth command group with login command**
  - [x] Create `src/orchestration/cli/commands/auth.py`
  - [x] `auth_app = typer.Typer(help="Credential management")`
  - [x] `login` command taking `profile: str` argument
  - [x] Loads profile via `get_profile(profile_name)` — catches `KeyError`, prints error with available profiles
  - [x] For `api_key` auth type: checks if the profile's `api_key_env` is set in env
  - [x] Output on success: `✓ {ENV_VAR} is set ({masked_key})` where masked key shows first 3 + last 4 chars
  - [x] Output on missing: `✗ {ENV_VAR} is not set` with hint `Set it with: export {ENV_VAR}=your-key-here`
  - [x] For profiles with no `api_key_env` (e.g. local): `✓ No authentication required for {profile} profile`
  - [x] Register in `app.py`: `app.add_typer(auth_app, name="auth")`
  - [x] Success: `orchestration auth login openai` runs without error; output matches expected format

- [x] **T14: Create auth status command**
  - [x] Add `status` command to `auth_app`
  - [x] Loads all profiles via `get_all_profiles()`
  - [x] Displays rich table with columns: Profile, Auth Type, Status, Source
  - [x] Status column: `✓ valid` if credential is available, `✗ missing` if not
  - [x] Source column: env var name, or `(no auth needed)` for profiles with no `api_key_env`
  - [x] Table uses `rich.table.Table` consistent with existing CLI output
  - [x] Success: `orchestration auth status` displays formatted table with all profiles

- [x] **T15: Test CLI auth commands**
  - [x] Create `tests/cli/test_auth.py`
  - [x] `test_auth_login_valid_key` — env var set → output contains `✓` and masked key
  - [x] `test_auth_login_missing_key` — env var not set → output contains `✗` and hint
  - [x] `test_auth_login_local_no_auth` — `local` profile → output contains `No authentication required`
  - [x] `test_auth_login_unknown_profile` — nonexistent profile → error message with available profiles, exit code 1
  - [x] `test_auth_status_shows_all_profiles` — output contains all built-in profile names
  - [x] `test_auth_status_valid_and_missing` — one env var set, another not → table shows both states correctly
  - [x] Use `typer.testing.CliRunner` and `monkeypatch` for env vars
  - [x] Success: all tests pass; ruff clean

- [x] **T16: Commit CLI auth commands**
  - [x] `ruff check` and `ruff format` clean
  - [x] `pyright` clean
  - [x] Commit: `feat: add CLI auth login and auth status commands`

### Final Validation

- [x] **T17: Full validation pass**
  - [x] Run complete test suite: `pytest tests/` — all pass
  - [x] Run `pyright` — zero errors
  - [x] Run `ruff check` and `ruff format` — clean
  - [x] Verify `orchestration auth login openai` works (manual or via CLI test runner)
  - [x] Verify `orchestration auth status` works
  - [x] Verify `orchestration spawn --profile openrouter --model <model>` still works (regression)
  - [x] Success: all checks pass; no regressions

- [x] **T18: Final commit and slice completion**
  - [x] Any remaining cleanup committed
  - [x] Update slice design status to `complete` in `114-slice.oauth-advanced-auth.md`
  - [x] Update slice plan: mark slice 114 as `[x]` in `100-slices.orchestration-v2.md`
  - [x] Commit: `docs: mark slice 114 complete`
  - [x] Write DEVLOG entry for slice 114 completion
