---
docType: slice-design
slice: auth-strategy-credential-management
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [openai-provider-core, provider-variants]
interfaces: [codex-agent-integration]
status: complete
dateCreated: 20260301
dateUpdated: 20260301
---

# Slice Design: Auth Strategy & Credential Management

## Overview

Extract credential resolution from `OpenAICompatibleProvider.create_agent()` into a formal `AuthStrategy` protocol, introduce an API key strategy as the concrete implementation, and add CLI commands for credential validation and status reporting. This formalizes the ad-hoc credential resolution pattern that emerged across slices 111-113 into an extensible abstraction that future auth methods (OAuth token flows, service account rotation) can implement without modifying provider logic.

## User-Provided Concept

Research during slice design revealed that OpenAI's API does not offer a general-purpose OAuth2 flow — authentication is purely API key-based (project-scoped keys, service account keys). OAuth exists only for Codex subscription access (browser-based, ChatGPT Plus/Pro/Teams). This finding reshapes the slice from "implement OAuth" to "formalize auth strategy abstraction with API key as the concrete implementation, and create documented extension points for future OAuth consumers (slice 116: Codex Agent Integration)."

## Value

**Separation of concerns**: Credential resolution is currently embedded in `OpenAICompatibleProvider.create_agent()` (lines 29-50). This logic will grow as providers multiply. Extracting it into a strategy pattern keeps providers focused on agent creation, not auth plumbing.

**Extensibility without complexity**: The `AuthStrategy` protocol costs almost nothing — it's a three-method interface with one concrete implementation. But it gives slice 116 (Codex) and future providers a clean seam to plug into, rather than adding more conditional branches to `create_agent()`.

**Credential visibility**: `orchestration auth status` gives users a single command to see which providers have working credentials, replacing the current workflow of "try to spawn, see if it errors."

## Technical Scope

### Included

- `AuthStrategy` protocol with `get_credentials()`, `refresh_if_needed()`, `is_valid()` methods
- `ApiKeyStrategy` implementation (env var lookup chain, matching current behavior)
- `auth_type` field on `ProviderProfile` (default: `"api_key"`)
- Strategy resolution: profile's `auth_type` → instantiate the correct `AuthStrategy`
- Refactor `OpenAICompatibleProvider.create_agent()` to delegate credential resolution to the strategy
- CLI `auth` command group: `auth login <provider>`, `auth status`
- `auth login`: validate API key exists for the specified provider/profile, report success or error
- `auth status`: show credential state for all configured profiles (valid/missing/invalid)
- Unit tests for strategy protocol, API key strategy, CLI commands

### Excluded

- OAuth2 flows, browser-based login, token exchange (slice 116)
- Encrypted credential storage / OS keyring (future hardening slice)
- Credential rotation or expiry management
- Changes to `SpawnRequest` or daemon protocol
- New provider implementations

## Dependencies

### Prerequisites

- **Slice 111 (OpenAI-Compatible Provider Core)** — complete. Provides `OpenAICompatibleProvider` with the credential resolution logic to refactor.
- **Slice 113 (Provider Variants & Registry)** — complete. Provides `ProviderProfile` model and profile loading infrastructure that this slice extends with `auth_type`.

### External Dependencies

- No new Python packages required

## Architecture

### Component Structure

```
src/orchestration/providers/
├── auth.py              # AuthStrategy protocol + ApiKeyStrategy
├── profiles.py          # Add auth_type field to ProviderProfile
├── openai/
│   └── provider.py      # Refactor: delegate to AuthStrategy

src/orchestration/cli/commands/
├── auth.py              # New: auth login, auth status commands

tests/providers/
├── test_auth.py         # AuthStrategy + ApiKeyStrategy tests

tests/cli/
├── test_auth.py         # CLI auth command tests
```

### AuthStrategy Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class AuthStrategy(Protocol):
    """Credential resolution strategy for a provider."""

    async def get_credentials(self) -> dict[str, str]:
        """Return credentials dict (e.g. {"api_key": "sk-..."}).

        Raises ProviderAuthError if credentials cannot be resolved.
        """
        ...

    async def refresh_if_needed(self) -> None:
        """Refresh credentials if they are expired or near expiry.

        No-op for strategies that don't support refresh (e.g. API keys).
        """
        ...

    def is_valid(self) -> bool:
        """Return True if credentials are currently available and usable."""
        ...
```

Using `Protocol` (not ABC) — consistent with existing `AgentProvider` protocol pattern. `runtime_checkable` enables `isinstance()` checks if needed, but the primary dispatch mechanism is the profile's `auth_type` field.

### ApiKeyStrategy

```python
class ApiKeyStrategy:
    """Resolve an API key from explicit value, env var chain, or localhost bypass."""

    def __init__(
        self,
        *,
        explicit_key: str | None = None,
        env_var: str | None = None,
        fallback_env_var: str = "OPENAI_API_KEY",
        base_url: str | None = None,
    ) -> None: ...

    async def get_credentials(self) -> dict[str, str]:
        """Return {"api_key": "<resolved_key>"}.

        Resolution order:
        1. explicit_key (from AgentConfig.api_key)
        2. os.environ[env_var] (profile-specified, e.g. OPENROUTER_API_KEY)
        3. os.environ[fallback_env_var] (default OPENAI_API_KEY)
        4. "not-needed" if base_url is localhost
        5. Raise ProviderAuthError
        """
        ...

    async def refresh_if_needed(self) -> None:
        """No-op — API keys don't expire."""
        pass

    def is_valid(self) -> bool:
        """Return True if any key source resolves to a non-empty value."""
        ...
```

This is a direct extraction of the existing logic from `OpenAICompatibleProvider.create_agent()` lines 29-50. No behavior change — same resolution order, same localhost bypass, same error messages.

### ProviderProfile Extension

Add `auth_type` field to `ProviderProfile`:

```python
@dataclass(frozen=True)
class ProviderProfile:
    name: str
    provider: str
    base_url: str | None = None
    api_key_env: str | None = None
    default_headers: dict[str, str] | None = None
    description: str = ""
    auth_type: str = "api_key"     # ← new field
```

Default is `"api_key"` — all existing profiles work unchanged. The `auth_type` value maps to a strategy class via a simple registry:

```python
AUTH_STRATEGIES: dict[str, type] = {
    "api_key": ApiKeyStrategy,
    # Future: "oauth": OAuthStrategy (slice 116)
    # Future: "none": NoAuthStrategy (if needed)
}
```

For `providers.toml`, users can specify:
```toml
[profiles.my-codex]
provider = "codex"
auth_type = "oauth"   # resolved by slice 116's OAuthStrategy
```

### Strategy Resolution

A factory function builds the correct strategy from an `AgentConfig` + `ProviderProfile`:

```python
def resolve_auth_strategy(
    config: AgentConfig,
    profile: ProviderProfile | None = None,
) -> AuthStrategy:
    """Build an AuthStrategy from config and optional profile."""
    auth_type = "api_key"
    if profile is not None:
        auth_type = profile.auth_type

    strategy_cls = AUTH_STRATEGIES.get(auth_type)
    if strategy_cls is None:
        raise ProviderAuthError(
            f"Unknown auth_type {auth_type!r}. "
            f"Available: {', '.join(sorted(AUTH_STRATEGIES))}"
        )

    if auth_type == "api_key":
        return ApiKeyStrategy(
            explicit_key=config.api_key,
            env_var=(
                profile.api_key_env if profile else
                config.credentials.get("api_key_env")
            ),
            fallback_env_var="OPENAI_API_KEY",
            base_url=config.base_url,
        )

    # Future auth types constructed here
    raise ProviderAuthError(f"Auth type {auth_type!r} not yet implemented")
```

### Provider Refactor

`OpenAICompatibleProvider.create_agent()` changes from inline credential resolution to strategy delegation:

```python
async def create_agent(self, config: AgentConfig) -> OpenAICompatibleAgent:
    strategy = resolve_auth_strategy(config, self._resolve_profile(config))
    await strategy.refresh_if_needed()
    credentials = await strategy.get_credentials()

    api_key = credentials["api_key"]
    # ... rest of agent creation unchanged
```

The `_resolve_profile` helper extracts the profile lookup that `spawn.py._resolve_profile` currently does at the CLI level. This ensures the provider can resolve auth even when invoked programmatically (not just via CLI).

### CLI Commands

#### `orchestration auth login <profile>`

Validates that credentials exist for the given profile:

```
$ orchestration auth login openai
✓ OPENAI_API_KEY is set (sk-...7x2f)

$ orchestration auth login openrouter
✗ OPENROUTER_API_KEY is not set
  Set it with: export OPENROUTER_API_KEY=your-key-here

$ orchestration auth login local
✓ No authentication required for local profile
```

This is a **validation** command, not a credential storage command. It checks whether the env var specified by the profile's `api_key_env` is set and non-empty. For localhost profiles, it reports that no auth is needed.

The key value shown is masked (first 3 + last 4 characters) — never displays full keys.

#### `orchestration auth status`

Shows credential state for all configured profiles:

```
$ orchestration auth status
Profile       Auth Type   Status    Source
─────────────────────────────────────────────────
openai        api_key     ✓ valid   OPENAI_API_KEY
openrouter    api_key     ✗ missing OPENROUTER_API_KEY
local         api_key     ✓ valid   (no auth needed)
gemini        api_key     ✗ missing GEMINI_API_KEY
```

Uses `rich` tables for formatting, consistent with existing CLI output patterns.

#### CLI Registration

```python
# cli/commands/auth.py
auth_app = typer.Typer(help="Credential management")

# cli/app.py
app.add_typer(auth_app, name="auth")
```

Follows the existing pattern used by `config_app` and `review_app`.

## Technical Decisions

### Why a Protocol instead of a base class

Consistent with the existing `AgentProvider` pattern. Protocols enable structural typing — any class with the right methods satisfies the interface without inheritance. This matters for slice 116 (Codex), which may need an `OAuthStrategy` that inherits from nothing in this package.

### Why `auth_type` on ProviderProfile rather than AgentConfig

Auth strategy is a property of the **provider configuration**, not of an individual agent. All agents using the OpenRouter profile use the same auth method. Putting it on the profile keeps the `AgentConfig` focused on per-agent runtime configuration.

### Why `auth login` validates rather than stores

The slice plan calls for env-var-based storage as acceptable for now. Adding a credential store would mean managing two sources of truth (env vars vs stored keys). Validation-only keeps things simple: the user sets env vars however they prefer (shell profile, .env file, secrets manager), and `auth login` confirms the credential is reachable.

### Why not `auth_token` on AgentConfig for this slice

`AgentConfig.auth_token` already exists (line 49 of `models.py`). It was added for Anthropic API provider (slice 7, not yet implemented). This slice doesn't use it — API key auth goes through `api_key` and `credentials`. When slice 7 arrives, the Anthropic provider's `AuthStrategy` implementation will use `auth_token`. No changes needed to `AgentConfig` for this slice.

### No-auth strategy considered and deferred

A `NoAuthStrategy` for the `local` profile would be cleaner than the localhost bypass in `ApiKeyStrategy`. However, the current "not-needed" placeholder pattern works with the OpenAI SDK's requirement for a non-empty `api_key`. A `NoAuthStrategy` would need to return a synthetic key anyway, so the abstraction doesn't buy anything. Revisit if a provider truly needs no auth header at all.

## Data Flow

```
CLI spawn --profile openrouter --model anthropic/claude-3.5-sonnet
  │
  ▼
spawn.py: _resolve_profile("openrouter")
  │  → ProviderProfile(auth_type="api_key", api_key_env="OPENROUTER_API_KEY", ...)
  │  → credentials dict includes api_key_env, default_headers
  ▼
Engine → OpenAICompatibleProvider.create_agent(config)
  │
  ▼
resolve_auth_strategy(config, profile)
  │  → auth_type="api_key" → ApiKeyStrategy(env_var="OPENROUTER_API_KEY", ...)
  ▼
strategy.refresh_if_needed()  → no-op for API keys
strategy.get_credentials()    → {"api_key": "sk-or-..."}
  │
  ▼
AsyncOpenAI(api_key=..., base_url=..., default_headers=...)
  │
  ▼
OpenAICompatibleAgent created
```

## Integration Points

### Provides to Other Slices

- **Slice 116 (Codex Agent Integration)**: `AuthStrategy` protocol is the extension point. Codex implements `OAuthStrategy` with browser login, token caching, and refresh. Registers as `AUTH_STRATEGIES["oauth"]`.
- **Slice 7 (Anthropic API Provider)**: Can implement its own `AuthStrategy` for `auth_token` resolution, or use `ApiKeyStrategy` with `ANTHROPIC_API_KEY`.
- **Any future provider**: Auth is decoupled from provider logic — new auth patterns don't require touching existing providers.

### Consumes from Previous Slices

- **Slice 111**: `OpenAICompatibleProvider` — the provider being refactored
- **Slice 113**: `ProviderProfile`, profile loading, `providers.toml` format — extended with `auth_type`
- **Foundation**: `AgentConfig`, `ProviderAuthError`, CLI app structure

## Success Criteria

### Functional Requirements

- `orchestration auth login openai` reports whether `OPENAI_API_KEY` is set (masked display)
- `orchestration auth login local` reports no auth needed
- `orchestration auth login <unknown>` reports error with available profiles
- `orchestration auth status` shows table of all profiles with credential state
- Spawning agents works identically to before (no behavioral regression)
- `ProviderProfile` accepts `auth_type` field from `providers.toml`
- Unknown `auth_type` values produce a clear error message

### Technical Requirements

- All existing tests pass unchanged (refactor doesn't change behavior)
- New unit tests for `ApiKeyStrategy` covering: explicit key, profile env var, default env var, localhost placeholder, missing key error
- New unit tests for `resolve_auth_strategy` covering: api_key type, unknown type error
- CLI tests for `auth login` and `auth status` commands
- `pyright` passes with zero errors
- `ruff check` and `ruff format` pass

## Implementation Notes

### Suggested Order

1. `AuthStrategy` protocol + `ApiKeyStrategy` implementation (`providers/auth.py`)
2. Unit tests for `ApiKeyStrategy` (extraction is behavior-preserving — test current behavior)
3. Add `auth_type` field to `ProviderProfile`, update TOML loading
4. `resolve_auth_strategy` factory function
5. Refactor `OpenAICompatibleProvider.create_agent()` to use strategy
6. Verify all existing tests still pass (no regression)
7. CLI `auth` command group (`auth login`, `auth status`)
8. CLI tests
9. Validation pass (full test suite, ruff, pyright)

### Testing Strategy

- **Strategy tests**: Mock `os.environ` with `monkeypatch.setenv`/`delenv`, test each resolution path
- **Provider tests**: Existing provider tests should pass unchanged — the refactor is internal
- **CLI tests**: Use `typer.testing.CliRunner`, mock profile loading and env vars
- **No integration tests**: All external dependencies are mocked, consistent with existing test patterns
