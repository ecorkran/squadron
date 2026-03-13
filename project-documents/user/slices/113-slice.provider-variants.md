---
docType: slice-design
slice: provider-variants
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [openai-provider-core, local-daemon]
interfaces: [oauth-advanced-auth]
status: complete
dateCreated: 20260228
dateUpdated: 20260228
---

# Slice Design: Provider Variants & Registry

## Overview

Add named provider profiles that bundle provider + base URL + auth configuration into short aliases, persisted in `~/.config/orchestration/providers.toml`. Ship three built-in variant definitions — OpenRouter, local model (Ollama/vLLM/LM Studio), and Gemini-via-compatible — that reuse the existing `OpenAICompatibleProvider` with pre-configured `base_url` and credential resolution. Extend the CLI spawn command to accept `--profile <alias>` for profile-based spawning.

All three variants are configurations of `OpenAICompatibleProvider`, not new provider classes. The design adds a profile registry layer between the CLI and the provider/engine, resolving a profile alias into a complete `AgentConfig` before spawning.

## Value

**Usability**: Today, spawning an OpenRouter or local model requires knowing the correct `--base-url`, `--provider`, and auth pattern. After this slice, `orchestration spawn --name my-agent --profile openrouter --model anthropic/claude-3.5-sonnet` just works — the user only needs to know the profile name and model.

**Persistence**: Provider configuration (base URLs, API key env var names, default headers) is stored in `providers.toml` and survives across sessions. Users can define custom profiles for their own endpoints.

**Foundation for future providers**: The profile system is provider-agnostic — it works for any provider, not just OpenAI-compatible ones. When the Anthropic API provider arrives (slice 7), it can have its own profiles.

## Technical Scope

### Included

- Provider profile data model (`ProviderProfile`)
- Profile registry: load from built-in defaults + `~/.config/orchestration/providers.toml`
- Three built-in profiles: `openrouter`, `local`, `gemini`
- Profile resolution in engine: `--profile <alias>` → merged `AgentConfig`
- CLI `--profile` flag on spawn command
- Local model discovery: `GET /v1/models` for `local` profile (informational — `list-models` subcommand)
- OpenRouter required headers (`HTTP-Referer`, `X-Title`) via `AgentConfig.credentials`
- Provider-specific env var resolution (e.g., `OPENROUTER_API_KEY` for openrouter profile)
- Unit tests for profile loading, merging, resolution
- CLI tests for `--profile` flag and `list-models` command

### Excluded

- OAuth flows and token refresh (slice 114)
- New provider classes (all variants reuse `OpenAICompatibleProvider`)
- Tool execution or function calling enhancements
- `config set/get` integration for profiles (profiles have their own file and CLI)
- Remote provider discovery or cloud-hosted profile registries

## Dependencies

### Prerequisites

- **Slice 111 (OpenAI-Compatible Provider Core)** — complete. Provides `OpenAICompatibleProvider` with `base_url` pass-through.
- **Slice 112 (Local Daemon)** — complete. Provides daemon/engine architecture where providers are loaded and agents spawned.

### External Dependencies

- `tomllib` (stdlib) + `tomli_w` (already in deps) for TOML read/write
- No new Python packages required

## Architecture

### Component Structure

```
src/orchestration/providers/
├── profiles.py          # ProviderProfile model, load/merge logic, built-in defaults
└── (existing files unchanged)

src/orchestration/cli/commands/
├── spawn.py             # Add --profile flag, profile resolution
└── models.py            # New: list-models command (local model discovery)

tests/providers/
├── test_profiles.py     # Profile loading, merging, built-in defaults

tests/cli/
├── test_spawn_profile.py  # --profile flag tests
└── test_models.py         # list-models command tests
```

### ProviderProfile Model

```python
@dataclass(frozen=True)
class ProviderProfile:
    """A named bundle of provider configuration."""

    name: str                          # profile alias (e.g., "openrouter")
    provider: str                      # provider registry name (e.g., "openai")
    base_url: str | None = None        # endpoint override
    api_key_env: str | None = None     # env var name for API key (e.g., "OPENROUTER_API_KEY")
    default_headers: dict[str, str] | None = None  # extra HTTP headers
    description: str = ""              # human-readable description
```

Using a `dataclass` rather than Pydantic — profiles are config data, not request/response models. They don't need validation, serialization, or schema generation.

### Built-in Profiles

```python
BUILT_IN_PROFILES: dict[str, ProviderProfile] = {
    "openrouter": ProviderProfile(
        name="openrouter",
        provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_headers={
            "HTTP-Referer": "https://github.com/manta/orchestration",
            "X-Title": "orchestration",
        },
        description="OpenRouter multi-model gateway",
    ),
    "local": ProviderProfile(
        name="local",
        provider="openai",
        base_url="http://localhost:11434/v1",
        api_key_env=None,  # local models typically need no auth
        description="Local model server (Ollama, vLLM, LM Studio)",
    ),
    "gemini": ProviderProfile(
        name="gemini",
        provider="openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        description="Google Gemini via OpenAI-compatible endpoint",
    ),
    "openai": ProviderProfile(
        name="openai",
        provider="openai",
        base_url=None,  # uses SDK default
        api_key_env="OPENAI_API_KEY",
        description="OpenAI direct API",
    ),
}
```

The `openai` profile is included as a first-class entry so that all providers can be referenced by profile name consistently. Users can also define custom profiles in `providers.toml`.

### providers.toml Format

Located at `~/.config/orchestration/providers.toml` (same directory as `config.toml`):

```toml
# Custom profiles
[profiles.my-ollama]
provider = "openai"
base_url = "http://192.168.1.100:11434/v1"
description = "Remote Ollama server"

[profiles.azure-openai]
provider = "openai"
base_url = "https://my-deployment.openai.azure.com/openai/deployments/gpt-4/v1"
api_key_env = "AZURE_OPENAI_API_KEY"
description = "Azure OpenAI deployment"
```

Built-in profiles can be overridden by defining a profile with the same name in `providers.toml`. User-defined profiles take precedence.

### Profile Resolution Flow

```
CLI spawn --profile openrouter --model anthropic/claude-3.5-sonnet --name my-agent
  │
  ▼
spawn.py: resolve profile
  │  1. Look up "openrouter" in user profiles (providers.toml)
  │  2. Fall back to BUILT_IN_PROFILES["openrouter"]
  │  3. Merge: CLI flags override profile fields
  ▼
Build request_data dict:
  {
    name: "my-agent",
    provider: "openai",          ← from profile
    model: "anthropic/...",      ← from CLI --model
    base_url: "https://openrouter.ai/api/v1",  ← from profile
    credentials: {
      api_key_env: "OPENROUTER_API_KEY",
      default_headers: { ... }
    }
  }
  │
  ▼
DaemonClient.spawn(request_data) → Engine
  │
  ▼
Engine._load_provider("openai")  ← normal auto-load
Engine.spawn_agent(config)
  │
  ▼
OpenAICompatibleProvider.create_agent(config)
  │  Resolves API key: config.api_key → env var from credentials.api_key_env → OPENAI_API_KEY → error
  │  Applies default_headers to client (if present in credentials)
  ▼
OpenAICompatibleAgent created
```

### Credential Resolution Enhancement

The current `OpenAICompatibleProvider.create_agent()` resolves API key from:
1. `config.api_key`
2. `os.environ["OPENAI_API_KEY"]`

This must be extended to support profile-specific env var names:
1. `config.api_key` (explicit, always wins)
2. `os.environ[config.credentials["api_key_env"]]` (if `api_key_env` is in credentials)
3. `os.environ["OPENAI_API_KEY"]` (default fallback)

For the `local` profile, `api_key_env` is `None` and `OPENAI_API_KEY` may not be set — but local models typically accept any value or don't require auth. The provider should treat empty/missing API key as acceptable when `base_url` points to localhost. Implementation: if no API key is found and `base_url` starts with `http://localhost` or `http://127.0.0.1`, use a placeholder key (`"not-needed"`) instead of raising `ProviderAuthError`.

### Default Headers Support

OpenRouter requires `HTTP-Referer` and `X-Title` headers on every request. The `AsyncOpenAI` client constructor accepts a `default_headers` parameter:

```python
client = AsyncOpenAI(
    api_key=api_key,
    base_url=profile.base_url,
    default_headers=credentials.get("default_headers"),
)
```

This is the cleanest integration point — no HTTP interceptors or middleware needed. The `default_headers` dict flows from profile → credentials → provider → `AsyncOpenAI` constructor.

### Local Model Discovery

A `list-models` command queries the `/v1/models` endpoint of a local (or any) provider:

```
orchestration models --profile local
orchestration models --base-url http://localhost:11434/v1
```

This sends `GET /v1/models` to the configured endpoint and displays available models. It's a convenience command — it doesn't go through the daemon. It's a direct HTTP call from the CLI.

Implementation: a simple `httpx.get()` to `{base_url}/models`, parse the OpenAI-compatible model list response, display model IDs.

### CLI Changes

#### spawn command additions

```
--profile <name>    Profile name (built-in or from providers.toml)
```

Profile fields provide defaults that CLI flags can override. Precedence:
1. Explicit CLI flags (highest)
2. Profile fields
3. Existing defaults (lowest)

Example combinations:
```bash
# Profile only — uses all profile defaults
orchestration spawn --name agent1 --profile openrouter --model anthropic/claude-3.5-sonnet

# Profile + override — uses profile but overrides base_url
orchestration spawn --name agent1 --profile local --model llama3 --base-url http://other-host:11434/v1

# No profile — current behavior unchanged
orchestration spawn --name agent1 --type api --provider openai --model gpt-4o-mini
```

#### models command

```
orchestration models [--profile <name>] [--base-url <url>]
```

Queries `/v1/models` and displays available models. Requires either `--profile` or `--base-url`.

## Technical Decisions

### Why profiles instead of provider subclasses

The slice plan mentions "OpenRouter configuration," "local model configuration," and "Gemini-via-compatible configuration." These are all just `OpenAICompatibleProvider` with different `base_url` and auth settings. Creating separate provider classes (`OpenRouterProvider`, `LocalModelProvider`, `GeminiProvider`) would duplicate the entire OpenAI provider implementation for what amounts to config differences. Profiles are the right abstraction — they're data, not behavior.

### Why a separate providers.toml instead of extending config.toml

The existing config system (`config.toml` + `ConfigKey` registry) is designed for scalar key-value pairs with typed defaults. Provider profiles are structured, nested data (each profile has multiple fields). Extending `ConfigKey` to handle nested structures would complicate the simple config system. A separate `providers.toml` keeps concerns clean and is independently parseable.

### Why dataclass instead of Pydantic for ProviderProfile

Profiles are internal configuration objects, not API request/response models. They don't need JSON schema generation, serialization, or the validation overhead of Pydantic. A frozen dataclass is simpler and sufficient.

### Why placeholder API key for localhost

Local model servers (Ollama, vLLM, LM Studio) typically don't require authentication, but the OpenAI SDK requires a non-empty `api_key` parameter. Rather than making `api_key` optional in the SDK client (which would require forking or wrapping it), we use a placeholder value `"not-needed"` when the target is localhost. This is a well-known pattern in the local LLM community.

### Why `--profile` instead of overloading `--provider`

The slice 111 design discussed whether to overload `--model` or add `--profile`. Adding `--profile` as a separate flag is cleaner because:
- `--provider` means "which provider implementation" (openai, sdk, anthropic)
- `--profile` means "which configuration preset" (openrouter, local, gemini, my-custom-one)
- A profile *contains* a provider reference — they're different abstraction levels
- No ambiguity when both are specified (profile provides defaults, `--provider` overrides)

### Models command is direct HTTP, not daemon-routed

The `models` command queries an external endpoint to discover available models. Routing this through the daemon would add unnecessary complexity — the daemon doesn't need to know about model discovery. A direct `httpx.get()` from the CLI is simpler and works even when the daemon isn't running.

## Integration Points

### Provides to Other Slices

- **Slice 114 (OAuth & Advanced Auth)**: The profile system provides the extension point for OAuth. An OAuth profile could include `auth_type: "oauth"` and trigger a different credential resolution path.
- **Slice 7 (Anthropic API Provider)**: Can have its own built-in profile (`anthropic`) once the provider exists.
- **Future slices**: Any new provider automatically benefits from the profile system.

### Consumes from Previous Slices

- **Slice 111**: `OpenAICompatibleProvider`, `OpenAICompatibleAgent`, provider auto-registration
- **Slice 112**: `DaemonClient`, engine spawn flow, CLI commands architecture
- **Foundation**: `AgentConfig`, `Message`, provider registry, config infrastructure

## Success Criteria

### Functional Requirements

- Built-in profiles for `openrouter`, `local`, `gemini`, and `openai` are available without any configuration file
- `--profile openrouter --model <model>` spawns an agent using OpenRouter's API endpoint
- `--profile local --model <model>` spawns an agent using localhost:11434 without requiring an API key
- `--profile gemini --model <model>` spawns an agent using Google's OpenAI-compatible endpoint
- User-defined profiles in `~/.config/orchestration/providers.toml` are loaded and usable
- User-defined profiles override built-in profiles with the same name
- CLI flags override profile fields (e.g., `--profile local --base-url http://other:11434/v1`)
- `orchestration models --profile local` queries the local model server and displays available models
- Spawning without `--profile` works exactly as before (no regression)
- OpenRouter requests include required `HTTP-Referer` and `X-Title` headers
- Profile-specific env vars are used for API key resolution (e.g., `OPENROUTER_API_KEY` for openrouter)

### Technical Requirements

- All unit tests pass with external APIs mocked
- `pyright` passes with zero errors
- `ruff check` and `ruff format` pass
- Profile loading has test coverage for: built-in defaults, user overrides, merge logic, missing file
- Credential resolution has test coverage for: explicit key, profile env var, default env var, localhost placeholder
- CLI `--profile` flag has test coverage for: valid profile, unknown profile, profile + flag override

## Implementation Notes

### Development Approach

Suggested order:

1. `ProviderProfile` model + built-in defaults + TOML loading (`profiles.py`)
2. Unit tests for profile loading and merging
3. Credential resolution enhancement in `OpenAICompatibleProvider` (env var from credentials, localhost placeholder)
4. Tests for enhanced credential resolution
5. Default headers support in `OpenAICompatibleProvider`
6. CLI `--profile` flag in spawn command + profile resolution logic
7. Tests for `--profile` flag
8. `models` command + tests
9. Validation pass (full test suite, ruff, pyright)

### Testing Strategy

- **Profile tests**: Load from built-in defaults, load from mock TOML file, user profile overrides built-in, merge with CLI flags
- **Provider tests**: API key from `credentials.api_key_env`, localhost placeholder key, `default_headers` passed to `AsyncOpenAI`
- **CLI tests**: `--profile openrouter`, `--profile unknown` (error), `--profile local --base-url override`, no profile (regression)
- **Models command tests**: Mock `httpx.get` response, display formatting, connection error handling

### Migration Considerations

No migration needed. This is purely additive:
- New `providers.toml` file (user creates if desired)
- New `--profile` CLI flag (optional, existing commands unchanged)
- New `models` command
- Enhanced credential resolution in existing provider (backwards-compatible — existing behavior when no `credentials.api_key_env` is present)
