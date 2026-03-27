---
docType: slice-design
slice: review-transport-unification-provider-decoupling
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [review-provider-model-selection, auth-strategy-credential-management]
interfaces: []
status: complete
dateCreated: 20260326
dateUpdated: 20260327
---

# Slice Design: Review Transport Unification & Provider Decoupling

## Overview

The review system currently has two bespoke transport implementations that bypass the `Agent`/`AgentProvider` Protocol abstraction. The SDK path (`runner.py`) directly instantiates `ClaudeSDKClient`. The non-SDK path (`review_client.py`) directly instantiates `AsyncOpenAI`. Neither uses the provider registry. Adding a new review transport (Codex subscription auth, Anthropic API, etc.) requires modifying `review_client.py` — the review module is tightly coupled to its transports.

This slice eliminates that coupling. Reviews use `Agent.handle_message()` via the provider registry, the same contract used by `sq spawn`/`sq task`. The review pipeline (template rendering, file injection, rules, output parsing) stays in the review module. Transport is the provider's concern.

Additionally, the codebase uses string matching for logic dispatch (`if profile == "sdk"`, `if auth_type == "codex"`). This slice replaces all such patterns with data-driven dispatch via registries and protocols.

### What changes

1. **Review transport** — `review_client.py` calls `agent.handle_message()` instead of constructing API clients directly
2. **Provider capabilities** — Providers declare capabilities (e.g., `can_read_files`) so callers can adapt without knowing provider identity
3. **Auth strategy dispatch** — `resolve_auth_strategy()` uses the `AUTH_STRATEGIES` registry consistently instead of if/elif chains
4. **Naming** — `SDKAgent` → `ClaudeSDKAgent`, `SDKAgentProvider` → `ClaudeSDKProvider` (the name implies generality that doesn't exist)
5. **Auth type naming** — `"codex"` auth type → `"oauth"` (auth types describe mechanisms, not products)
6. **CLI auth status** — Delegates to `AuthStrategy.is_valid()` instead of branching on auth_type strings

### What does NOT change

- `ProviderProfile` dataclass and profile resolution
- Provider registry (`register_provider`/`get_provider`)
- `Agent` and `AgentProvider` Protocol definitions
- Review pipeline logic (templates, parsers, file injection, rules injection, output formatting)
- CLI review commands (`sq review slice|tasks|code`) — same flags, same behavior
- Model alias system
- Codex agent's MCP transport internals

## Value

**Extensibility without modification.** Adding a new review transport (Anthropic API, Codex subscription, future providers) requires only: implement `AgentProvider`/`Agent`, register it, create a profile. The review module is never touched.

**Subscription-auth reviews.** Codex agents running via MCP use the `~/.codex/auth.json` OAuth token (ChatGPT subscription). With unified transport, `sq review code 128 --profile codex` routes through the Codex agent, using subscription quota instead of API credits.

**Eliminates fragile dispatch.** No more `if profile == "sdk"` or `if auth_type == "codex"`. Provider identity never controls program flow outside the provider itself.

## Prerequisites

### From Squadron
- Agent/AgentProvider Protocols (slice 100) — `handle_message()` contract
- Provider registry (slice 100) — `get_provider()`/`register_provider()`
- Auth Strategy (slice 114) — `AuthStrategy` Protocol, `AUTH_STRATEGIES` dict
- Review system (slices 105, 119) — templates, parsers, CLI commands

## Architecture

### Component Structure

No new files. Changes to existing files:

```
src/squadron/
├── providers/
│   ├── base.py                # Add ProviderCapabilities
│   ├── auth.py                # Simplify resolve_auth_strategy, rename "codex" → "oauth"
│   ├── profiles.py            # Update codex profile auth_type
│   ├── sdk/
│   │   ├── __init__.py        # Rename exports
│   │   ├── provider.py        # Rename class, add capabilities
│   │   └── agent.py           # Rename class
│   ├── openai/
│   │   └── provider.py        # Add capabilities
│   └── codex/
│       ├── auth.py            # Rename to OAuthFileStrategy
│       └── provider.py        # Add capabilities
├── review/
│   ├── review_client.py       # Replace bespoke transports with handle_message()
│   └── runner.py              # Remove (absorbed into ClaudeSDKAgent)
└── cli/
    └── commands/
        └── auth.py            # Remove string dispatch
```

### Provider Capabilities

Providers declare what they can do. Callers adapt based on capabilities, not identity.

```python
# In base.py
@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities of a provider."""
    can_read_files: bool = False      # Agent can read project files directly
    supports_system_prompt: bool = True  # Agent accepts system prompt in config
    supports_streaming: bool = False  # Agent yields incremental responses
```

Each `AgentProvider` exposes a `capabilities` property:

```python
class AgentProvider(Protocol):
    @property
    def provider_type(self) -> str: ...
    @property
    def capabilities(self) -> ProviderCapabilities: ...
    async def create_agent(self, config: AgentConfig) -> Agent: ...
    async def validate_credentials(self) -> bool: ...
```

Provider implementations:

| Provider | `can_read_files` | `supports_system_prompt` | `supports_streaming` |
|----------|-----------------|-------------------------|---------------------|
| `ClaudeSDKProvider` | `True` | `True` | `True` |
| `OpenAICompatibleProvider` | `False` | `True` | `True` |
| `CodexProvider` | `True` | `False` (instructions via prompt) | `False` |

### Review Transport Unification

**Before (two bespoke paths):**

```
run_review_with_profile()
├─ if profile == "sdk"  →  ClaudeSDKClient(options).query()
└─ else                 →  AsyncOpenAI(api_key).chat.completions.create()
```

**After (one path through provider registry):**

```
run_review_with_profile()
└─ provider = get_provider(profile_obj.provider)
   capabilities = provider.capabilities
   if not capabilities.can_read_files:
       prompt = _inject_file_contents(prompt, inputs)
   agent = provider.create_agent(config)
   response = agent.handle_message(message)
   raw_output = extract text from response
```

The review module:
1. Looks up the profile → gets provider name
2. Gets provider from registry → gets capabilities
3. Builds prompt (injects files only if provider can't read them)
4. Creates an agent via `provider.create_agent(config)`
5. Sends the review prompt via `agent.handle_message()`
6. Collects response text
7. Parses with `parse_review_output()` (unchanged)
8. Shuts down the agent

The review module never imports `AsyncOpenAI`, `ClaudeSDKClient`, or any provider-specific type.

### Auth Strategy Cleanup

**Before:**

```python
# auth.py — redundant dispatch
if auth_type == "api_key":
    return ApiKeyStrategy(...)
if auth_type == "codex":
    return CodexAuthStrategy()
raise ProviderAuthError(...)
```

**After:**

```python
# auth.py — registry-driven
strategy_cls = AUTH_STRATEGIES.get(auth_type)
if strategy_cls is None:
    raise ProviderAuthError(...)
return strategy_cls.from_config(config, profile)  # Factory method on each strategy
```

Each strategy class implements a `from_config` classmethod that extracts what it needs from `AgentConfig` and `ProviderProfile`. No special-casing in `resolve_auth_strategy`.

**Auth type rename:** `"codex"` → `"oauth"` in `AUTH_STRATEGIES`, `ProviderProfile` for codex, and `CodexAuthStrategy` → `OAuthFileStrategy` (it resolves OAuth tokens from a file — that's what it does, not which product it's for).

### CLI Auth Status Cleanup

**Before:**

```python
if profile.auth_type == "codex":
    strategy = CodexAuthStrategy()
    ...
elif profile.api_key_env is None:
    ...
```

**After:**

```python
strategy = resolve_auth_strategy_for_profile(profile)
if strategy.is_valid():
    status = "✓ authenticated"
    source = strategy.active_source or ""
else:
    status = "✗ not authenticated"
    source = strategy.setup_hint
```

No branching on auth_type. The strategy knows how to report its own status.

### SDK Review Path Migration

`runner.py` contains the SDK review execution logic. This logic moves into `ClaudeSDKAgent.handle_message()` and `ClaudeSDKProvider.create_agent()`:

- `allowed_tools`, `permission_mode`, `setting_sources`, `hooks` → set on `AgentConfig`, consumed by `ClaudeSDKProvider.create_agent()` (most of these are already on `AgentConfig`)
- `ClaudeSDKClient` lifecycle (query + receive_response + retry) → internal to `ClaudeSDKAgent.handle_message()`
- Rate limit retry logic → internal to `ClaudeSDKAgent`

`runner.py` is deleted. Its only consumer (`review_client.py`) no longer needs it.

### Naming Changes

| Before | After | Reason |
|--------|-------|--------|
| `SDKAgent` | `ClaudeSDKAgent` | It wraps `claude_agent_sdk` specifically |
| `SDKAgentProvider` | `ClaudeSDKProvider` | Same |
| `CodexAuthStrategy` | `OAuthFileStrategy` | Auth type describes mechanism, not product |
| `auth_type: "codex"` | `auth_type: "oauth"` | Same |

The provider registry key `"sdk"` stays `"sdk"` — it's a user-facing profile identifier, not logic dispatch. Same for `"codex"` as a registry key.

## Technical Decisions

### Capabilities over identity

The review system needs to know "can this provider read files?" to decide whether to inject file contents. The wrong answer is `if provider_type == "sdk"`. The right answer is `provider.capabilities.can_read_files`. This generalizes — when we add Anthropic API (can't read files) or a future agentic provider (can read files), the review system adapts without modification.

### One-shot agent lifecycle for reviews

Reviews create an agent, send one message, collect the response, shut down. This is the same lifecycle the daemon uses for `sq task` one-shot mode. The agent's `handle_message()` is async iterator — for reviews, we collect all yielded messages and concatenate their text content. No streaming needed at the review layer.

### `from_config` factory on auth strategies

Rather than special-casing construction in `resolve_auth_strategy()`, each strategy class gets a `from_config(config, profile)` classmethod. `ApiKeyStrategy.from_config` extracts `api_key_env`, `base_url`, etc. `OAuthFileStrategy.from_config` is a no-op (it reads from a fixed file path). This eliminates the if/elif chain entirely — the registry dict maps auth_type strings to classes, and each class constructs itself.

### `runner.py` deletion

The SDK review path in `runner.py` is 110 lines that duplicate what `ClaudeSDKAgent.handle_message()` should do. Rather than maintaining two SDK execution paths (one for reviews, one for spawn/task), we consolidate. The review-specific config (allowed_tools, hooks, setting_sources) is already on `AgentConfig` — `ClaudeSDKProvider.create_agent()` reads it from there.

## Success Criteria

### Functional Requirements
- `sq review code 128 --profile codex` routes through `CodexAgent.handle_message()` using subscription auth
- `sq review slice 100 --model codex` routes through `OpenAICompatibleAgent` via `openai` profile (unchanged behavior, alias resolves profile)
- `sq review slice 100` (no flags) routes through `ClaudeSDKAgent` (default profile still `"sdk"`)
- `sq review code 128 --profile openrouter --model minimax` works (unchanged behavior)
- `sq auth status` shows correct status for all profiles without string-matching on auth_type
- All existing review tests pass with no behavioral regression
- Adding a hypothetical new provider requires zero changes to `review_client.py`

### Technical Requirements
- No `AsyncOpenAI` import in `review_client.py` or `runner.py`
- No `ClaudeSDKClient` import in `review_client.py`
- No `if profile == "sdk"` or `if auth_type == "..."` anywhere in `review_client.py` or `auth.py`
- `runner.py` deleted — SDK review logic consolidated in `ClaudeSDKAgent`
- `ProviderCapabilities` dataclass on `AgentProvider` Protocol
- `AUTH_STRATEGIES` registry is the single source of truth for auth type dispatch
- All string-based dispatch in `auth.py` and `cli/commands/auth.py` eliminated

## Verification Walkthrough

1. **Default SDK review (unchanged behavior):**
   ```
   sq review slice 100
   ```
   Routes through ClaudeSDKAgent. No flags needed. Same output as before.

2. **API review via alias (unchanged behavior):**
   ```
   sq review slice 100 --model minimax -v
   ```
   Alias resolves to openrouter profile. Routes through OpenAICompatibleAgent.

3. **Codex subscription review (new capability):**
   ```
   sq review code 128 --profile codex -v
   ```
   Routes through CodexAgent using `~/.codex/auth.json`. No API key needed.

4. **Auth status (cleaned up):**
   ```
   sq auth status
   ```
   Shows all profiles with correct status. No string dispatch — each profile's auth strategy reports its own state.

5. **Provider capabilities check:**
   ```python
   from squadron.providers.registry import get_provider
   p = get_provider("sdk")
   assert p.capabilities.can_read_files is True
   p2 = get_provider("openai")
   assert p2.capabilities.can_read_files is False
   ```

6. **No regression in spawn/task:**
   ```
   sq spawn --provider openai --model gpt54-mini --name test
   sq task test "hello"
   sq shutdown test
   ```

## Risks

- **SDK review path has review-specific retry logic** for rate limit events. This must be preserved in `ClaudeSDKAgent.handle_message()` during the migration from `runner.py`. If the retry semantics change, review reliability could degrade.
- **`runner.py` deletion** removes a file that may have test coverage. Tests must be migrated to cover the equivalent paths through `ClaudeSDKAgent`.

## Effort
4/5 — Touches review system, provider system, auth system, and CLI. Many files affected but changes are mechanical (replace direct client usage with `handle_message()`, replace string dispatch with registry lookup). Risk is in behavioral regression during the consolidation.
