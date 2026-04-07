---
slice: provider-variants
project: squadron
lld: project-documents/user/slices/113-slice.provider-variants.md
dependencies: [openai-provider-core, local-daemon]
projectState: Slices 111 (OpenAI-Compatible Provider Core) and 112 (Local Server & CLI Client) complete. Daemon architecture operational. CLI commands are thin HTTP clients to daemon. Provider auto-loader in engine. 377 tests passing.
status: complete
dateCreated: 20260228
dateUpdated: 20260228
docType: tasks
---

## Context Summary

- Working on **provider-variants** (slice 113)
- Adds named provider profiles bundling provider + base URL + auth into short aliases
- Three built-in variants: OpenRouter, local (Ollama/vLLM/LM Studio), Gemini-via-compatible
- All variants reuse `OpenAICompatibleProvider` — no new provider classes
- Profiles persisted in `~/.config/orchestration/providers.toml`
- CLI gains `--profile` flag on spawn and a new `models` command
- Credential resolution enhanced: profile-specific env vars, localhost auth bypass
- Depends on slices 111 and 112
- Full design: `project-documents/user/slices/113-slice.provider-variants.md`

---

## Tasks

### Profile Infrastructure

- [x] **T1: Create ProviderProfile model and built-in defaults**
  - [x] Create `src/orchestration/providers/profiles.py`
  - [x] `ProviderProfile` frozen dataclass with fields: `name`, `provider`, `base_url` (optional), `api_key_env` (optional), `default_headers` (optional dict), `description` (default `""`)
  - [x] `BUILT_IN_PROFILES: dict[str, ProviderProfile]` with four entries: `openai`, `openrouter`, `local`, `gemini` — values as specified in slice design §Built-in Profiles
  - [x] Success: module importable; `BUILT_IN_PROFILES["openrouter"].base_url == "https://openrouter.ai/api/v1"`; pyright clean

- [x] **T2: Implement profile loading from providers.toml**
  - [x] Add `providers_toml_path() -> Path` — returns `~/.config/orchestration/providers.toml`
  - [x] Add `load_user_profiles() -> dict[str, ProviderProfile]` — reads `[profiles.*]` sections from TOML file; returns empty dict if file missing
  - [x] Add `get_all_profiles() -> dict[str, ProviderProfile]` — merges built-in profiles with user profiles; user profiles override built-in entries with the same name
  - [x] Add `get_profile(name: str) -> ProviderProfile` — looks up from `get_all_profiles()`; raises `KeyError` with descriptive message if not found
  - [x] Success: all four functions present with correct signatures; pyright clean

- [x] **T3: Test profile loading and merging**
  - [x] `test_built_in_profiles_available` — `get_all_profiles()` contains `openai`, `openrouter`, `local`, `gemini`
  - [x] `test_built_in_openrouter_has_correct_base_url`
  - [x] `test_built_in_local_has_no_api_key_env` — `api_key_env is None`
  - [x] `test_load_user_profiles_missing_file` — returns empty dict; no error
  - [x] `test_load_user_profiles_from_toml` — write a temp TOML file with a `[profiles.custom]` section; verify `load_user_profiles()` returns it as a `ProviderProfile`
  - [x] `test_user_profile_overrides_builtin` — user defines `openrouter` in TOML with different `base_url`; `get_all_profiles()["openrouter"]` uses user's value
  - [x] `test_get_profile_known` — returns profile for `"openrouter"`
  - [x] `test_get_profile_unknown_raises` — raises `KeyError` for `"nonexistent"`
  - [x] Success: all tests pass; ruff clean

- [x] **T4: Commit profile infrastructure**
  - [x] `ruff check` and `ruff format` clean on new files
  - [x] `pyright` clean on new files
  - [x] Commit: `feat: add provider profile model and TOML loading`

### Provider Enhancements

- [x] **T5: Enhance credential resolution in OpenAICompatibleProvider**
  - [x] Modify `create_agent()` in `src/orchestration/providers/openai/provider.py`:
    - [x] After checking `config.api_key`, check `config.credentials.get("api_key_env")` — if present, look up that env var name
    - [x] Keep `OPENAI_API_KEY` as final fallback
    - [x] If no API key found and `config.base_url` starts with `http://localhost` or `http://127.0.0.1`, use placeholder `"not-needed"` instead of raising `ProviderAuthError`
  - [x] Success: existing provider tests still pass; new resolution chain works

- [x] **T6: Add default_headers support to OpenAICompatibleProvider**
  - [x] Modify `create_agent()` to pass `default_headers=config.credentials.get("default_headers")` to `AsyncOpenAI` constructor
  - [x] Success: `AsyncOpenAI` constructed with `default_headers` kwarg when present in credentials

- [x] **T7: Test enhanced credential resolution**
  - [x] `test_api_key_from_credentials_env_var` — `credentials={"api_key_env": "MY_CUSTOM_KEY"}`, env var set → uses that key
  - [x] `test_credentials_env_var_takes_precedence_over_default` — both `MY_CUSTOM_KEY` and `OPENAI_API_KEY` set → uses `MY_CUSTOM_KEY`
  - [x] `test_localhost_placeholder_key` — no API key anywhere, `base_url="http://localhost:11434/v1"` → key is `"not-needed"`, no error
  - [x] `test_127_0_0_1_placeholder_key` — no API key, `base_url="http://127.0.0.1:8080/v1"` → placeholder key, no error
  - [x] `test_remote_url_still_raises_without_key` — no API key, `base_url="https://api.example.com"` → `ProviderAuthError`
  - [x] `test_default_headers_passed_to_client` — `credentials={"default_headers": {"X-Custom": "val"}}` → `AsyncOpenAI` constructed with `default_headers`
  - [x] `test_no_default_headers_passes_none` — no `default_headers` in credentials → `AsyncOpenAI` gets `None` for `default_headers`
  - [x] Success: all tests pass; existing provider tests still pass; ruff clean

- [x] **T8: Commit provider enhancements**
  - [x] Full test suite passes
  - [x] `ruff check` and `pyright` clean
  - [x] Commit: `feat: enhance credential resolution and default headers support`

### CLI Integration

- [x] **T9: Add --profile flag to spawn command**
  - [x] Add `profile: str | None = typer.Option(None, "--profile", help="Provider profile (e.g. openrouter, local, gemini)")` to `spawn()` in `src/orchestration/cli/commands/spawn.py`
  - [x] Add `_resolve_profile(profile_name, cli_provider, cli_base_url)` helper that:
    - [x] Calls `get_profile(profile_name)` to load the profile
    - [x] Returns a dict with `provider`, `base_url`, and `credentials` (containing `api_key_env` and `default_headers` from profile)
    - [x] CLI flags (`--provider`, `--base-url`) override profile fields when explicitly set
  - [x] In `spawn()`, when `--profile` is given, merge resolved profile fields into `request_data`
  - [x] When `--profile` is given, default `agent_type` to `"api"` (profiles are always API providers)
  - [x] Success: `orchestration spawn --help` shows `--profile`; existing spawn behavior unchanged when `--profile` not used

- [x] **T10: Test --profile flag on spawn**
  - [x] `test_profile_sets_provider_and_base_url` — `--profile openrouter --model x` → `request_data` has `provider="openai"`, `base_url="https://openrouter.ai/api/v1"`
  - [x] `test_profile_includes_credentials` — openrouter profile → `credentials` contains `api_key_env` and `default_headers`
  - [x] `test_profile_cli_base_url_overrides` — `--profile local --base-url http://other:11434/v1` → `base_url` is the CLI value
  - [x] `test_profile_unknown_exits_with_error` — `--profile nonexistent` → exit code 1, error message
  - [x] `test_no_profile_unchanged` — spawn without `--profile` works exactly as before (regression check)
  - [x] Success: all tests pass; ruff clean

- [x] **T11: Implement models command**
  - [x] Create `src/orchestration/cli/commands/models.py`
  - [x] `models` command with options: `--profile <name>` and `--base-url <url>` (at least one required)
  - [x] Resolves base URL: from `--base-url` if given, otherwise from profile's `base_url`
  - [x] Sends `GET {base_url}/models` via `httpx.AsyncClient` (direct HTTP, no daemon)
  - [x] Parses OpenAI-compatible response: `{"data": [{"id": "model-name", ...}, ...]}`
  - [x] Displays model IDs in a formatted list
  - [x] Handles connection errors gracefully (prints message, exits 1)
  - [x] Success: `orchestration models --help` shows options

- [x] **T12: Register models command in app.py**
  - [x] Import `models` from `orchestration.cli.commands.models`
  - [x] Register as `app.command("models")(models)`
  - [x] Success: `orchestration --help` shows `models` command

- [x] **T13: Test models command**
  - [x] `test_models_displays_model_list` — mock `httpx.AsyncClient.get` returning `{"data": [{"id": "llama3"}, {"id": "mistral"}]}` → output contains both model names
  - [x] `test_models_with_profile` — `--profile local` → resolves base URL from profile, sends GET to correct URL
  - [x] `test_models_connection_error` — mock raises `httpx.ConnectError` → exit code 1, error message
  - [x] `test_models_requires_profile_or_base_url` — no flags → exit code ≠ 0, error message
  - [x] Success: all tests pass; ruff clean

- [x] **T14: Commit CLI integration**
  - [x] Full test suite passes
  - [x] `ruff check` and `pyright` clean
  - [x] Commit: `feat: add --profile flag to spawn and models command`

### Validation

- [x] **T15: Full validation pass**
  - [x] `pytest` (full suite) — all green
  - [x] `ruff check src/` — clean
  - [x] `ruff format --check src/` — clean
  - [x] `pyright src/` — zero errors
  - [x] Verify: spawn without `--profile` still works (regression)
  - [x] Success: all four checks pass; no regressions

---

## Implementation Notes

- **TOML parsing**: Use `tomllib.load()` (stdlib) for reading. The `[profiles.X]` TOML section maps to nested dict `{"profiles": {"X": {...}}}`. Parse each sub-dict into a `ProviderProfile`.
- **Profile merge precedence**: CLI flags > profile fields > existing defaults. When `--profile` and `--provider` are both given, `--provider` wins over the profile's `provider` field.
- **Localhost detection**: Check `base_url.startswith("http://localhost")` or `base_url.startswith("http://127.0.0.1")`. Do not use URL parsing — simple prefix match is sufficient and avoids overcomplicating.
- **OpenRouter headers**: The `default_headers` parameter on `AsyncOpenAI` is the canonical way to add extra headers. It applies to every request made by that client instance.
- **Models command response format**: OpenAI `/v1/models` returns `{"object": "list", "data": [{"id": "model-id", "object": "model", ...}]}`. Only the `id` field is needed for display.
