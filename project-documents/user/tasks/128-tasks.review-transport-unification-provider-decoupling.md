---
docType: tasks
slice: review-transport-unification-provider-decoupling
project: squadron
lld: user/slices/128-slice.review-transport-unification-provider-decoupling.md
dependencies: [review-provider-model-selection, auth-strategy-credential-management]
projectState: "M1 shipped (v0.2.7). Review system has two bespoke transport paths (SDK via runner.py, non-SDK via AsyncOpenAI in review_client.py). Neither uses Agent/AgentProvider Protocols. String dispatch on profile names and auth types. Slice 124 (Codex) rewound — provider code not on main."
dateCreated: 20260327
dateUpdated: 20260327
status: not_started
---

## Context Summary
- Working on slice 128: Review Transport Unification & Provider Decoupling
- Review system bypasses Agent/AgentProvider Protocols — directly instantiates AsyncOpenAI and ClaudeSDKClient
- String-based dispatch (`if profile == "sdk"`, `if auth_type == "codex"`) throughout codebase
- Goal: reviews use `Agent.handle_message()` via provider registry; providers declare capabilities; no string dispatch
- Codex provider (from rewound slice 124) rebuilt as part of this slice, now usable for reviews
- Key files: `review_client.py`, `runner.py` (to delete), `auth.py`, `base.py`, `cli/commands/auth.py`
- Existing providers to update: `sdk/`, `openai/`; new provider: `codex/`

---

## Tasks

### T1: ProviderCapabilities dataclass and AgentProvider Protocol update

- [ ] **Add `ProviderCapabilities` to `src/squadron/providers/base.py`**
  - [ ] Create frozen dataclass: `can_read_files: bool = False`, `supports_system_prompt: bool = True`, `supports_streaming: bool = False`
  - [ ] Add `capabilities` property to `AgentProvider` Protocol
  - [ ] Update `__all__` exports
- [ ] **Add `capabilities` to `OpenAICompatibleProvider`**
  - [ ] Return `ProviderCapabilities(can_read_files=False, supports_system_prompt=True, supports_streaming=True)`
- [ ] **Add `capabilities` to `SDKAgentProvider` (pre-rename)**
  - [ ] Return `ProviderCapabilities(can_read_files=True, supports_system_prompt=True, supports_streaming=True)`
- [ ] Success: all providers expose `capabilities`; existing tests pass

### T2: ProviderCapabilities tests

- [ ] **Add tests for ProviderCapabilities**
  - [ ] Test: `ProviderCapabilities()` defaults are `can_read_files=False, supports_system_prompt=True, supports_streaming=False`
  - [ ] Test: OpenAI provider `capabilities.can_read_files` is `False`
  - [ ] Test: SDK provider `capabilities.can_read_files` is `True`
  - [ ] Test: capabilities dataclass is frozen (assignment raises)
  - [ ] Success: all tests pass

**Commit**: `feat: add ProviderCapabilities dataclass to AgentProvider Protocol`

---

### T3: Auth strategy `from_config` factory and registry-driven dispatch

- [ ] **Add `from_config` classmethod to `ApiKeyStrategy`**
  - [ ] Signature: `from_config(cls, config: AgentConfig, profile: ProviderProfile | None) -> ApiKeyStrategy`
  - [ ] Extracts `explicit_key`, `env_var`, `fallback_env_var`, `base_url` from config and profile (same logic currently in `resolve_auth_strategy`)
- [ ] **Add `active_source` property and `setup_hint` property to `ApiKeyStrategy`**
  - [ ] `active_source`: returns the env var name or "explicit" or "localhost" depending on which source resolved
  - [ ] `setup_hint`: returns actionable instruction (e.g., "Set OPENAI_API_KEY environment variable")
- [ ] **Refactor `resolve_auth_strategy()` to use registry only**
  - [ ] Remove the `if auth_type == "api_key"` and `if auth_type == "codex"` branches
  - [ ] Use: `strategy_cls = AUTH_STRATEGIES[auth_type]; return strategy_cls.from_config(config, profile)`
  - [ ] Raise `ProviderAuthError` for unknown auth_type (unchanged)
- [ ] **Add `resolve_auth_strategy_for_profile()` convenience function**
  - [ ] Takes `ProviderProfile` only (no `AgentConfig` needed for status checks)
  - [ ] Constructs minimal config, delegates to `resolve_auth_strategy()`
- [ ] Success: `resolve_auth_strategy()` has no if/elif on auth_type; all tests pass

### T4: Auth strategy refactor tests

- [ ] **Update existing auth resolution tests in `tests/providers/test_auth_resolution.py`**
  - [ ] Tests should still pass — `resolve_auth_strategy` returns same results
- [ ] **Add tests for `from_config` classmethods**
  - [ ] Test: `ApiKeyStrategy.from_config()` with profile containing `api_key_env`
  - [ ] Test: `ApiKeyStrategy.from_config()` with explicit key in config
  - [ ] Test: `ApiKeyStrategy.from_config()` with localhost base_url
- [ ] **Add tests for `active_source` and `setup_hint`**
  - [ ] Test: `active_source` returns env var name when key found via env var
  - [ ] Test: `setup_hint` returns actionable message
- [ ] **Test `resolve_auth_strategy_for_profile()`**
  - [ ] Test: returns valid strategy for `openai` profile
  - [ ] Test: returns valid strategy for `sdk` profile
- [ ] Success: all auth tests pass; no string dispatch in `resolve_auth_strategy`

**Commit**: `refactor: registry-driven auth strategy dispatch with from_config factory`

---

### T5: OAuthFileStrategy (rename + from_config)

- [ ] **Create `src/squadron/providers/codex/auth.py` with `OAuthFileStrategy`**
  - [ ] Resolution order: `~/.codex/auth.json` (subscription) → `OPENAI_API_KEY` (fallback) → raise `ProviderAuthError`
  - [ ] `from_config` classmethod (no-op — reads from fixed file path)
  - [ ] `active_source` property: returns `"~/.codex/auth.json"` or `"OPENAI_API_KEY"` or `None`
  - [ ] `setup_hint` property: returns `"Run 'codex' CLI to authenticate, or set OPENAI_API_KEY"`
  - [ ] `is_valid()`, `get_credentials()`, `refresh_if_needed()` per AuthStrategy Protocol
- [ ] **Register `"oauth"` in `AUTH_STRATEGIES` dict**
- [ ] **Update codex profile in `BUILT_IN_PROFILES` (`profiles.py`)**
  - [ ] Add `codex` profile with `provider="codex"`, `auth_type="oauth"`
- [ ] Success: `OAuthFileStrategy` satisfies `AuthStrategy` Protocol; registered as `"oauth"`

### T6: OAuthFileStrategy tests

- [ ] **Create `tests/providers/codex/test_auth.py`**
  - [ ] Test: auth file exists → `is_valid()` True, `get_credentials()` returns `{"auth_file": path}`
  - [ ] Test: no auth file, `OPENAI_API_KEY` set → `is_valid()` True, `get_credentials()` returns `{"api_key": value}`
  - [ ] Test: neither source → `is_valid()` False, `get_credentials()` raises `ProviderAuthError`
  - [ ] Test: auth file preferred over API key when both exist
  - [ ] Test: `from_config` returns working strategy
  - [ ] Test: `active_source` reports correct source
  - [ ] Test: `setup_hint` returns actionable message
  - [ ] Use `monkeypatch` for env vars and `tmp_path` for auth file fixture
- [ ] Success: all tests pass

**Commit**: `feat: add OAuthFileStrategy for subscription credential resolution`

---

### T7: Rename SDKAgent → ClaudeSDKAgent, SDKAgentProvider → ClaudeSDKProvider

- [ ] **Rename classes in `src/squadron/providers/sdk/agent.py`**
  - [ ] `SDKAgent` → `ClaudeSDKAgent`
  - [ ] Update all internal references
- [ ] **Rename classes in `src/squadron/providers/sdk/provider.py`**
  - [ ] `SDKAgentProvider` → `ClaudeSDKProvider`
  - [ ] Update all internal references
- [ ] **Update `src/squadron/providers/sdk/__init__.py`**
  - [ ] Update imports and `__all__` exports
  - [ ] Registration: `register_provider("sdk", ClaudeSDKProvider())` (key unchanged)
- [ ] **Update all test files referencing old names**
  - [ ] `tests/providers/sdk/test_agent.py`, `test_provider.py`, `test_registration.py`
- [ ] **Update any other imports across codebase**
  - [ ] Search for `SDKAgent` and `SDKAgentProvider` in all `.py` files
- [ ] Success: `ruff check` clean; all tests pass; `get_provider("sdk")` returns `ClaudeSDKProvider`

### T8: Rename tests

- [ ] **Verify all SDK tests pass after rename**
  - [ ] `pytest tests/providers/sdk/ -v` — all green
  - [ ] `pytest tests/ -v` — full suite green (no broken imports)
- [ ] Success: zero test failures

**Commit**: `refactor: rename SDKAgent to ClaudeSDKAgent for clarity`

---

### T9: Codex provider implementation

- [ ] **Create `src/squadron/providers/codex/agent.py` with `CodexAgent`**
  - [ ] Implement `Agent` Protocol: `name`, `agent_type`, `state`, `handle_message()`, `shutdown()`
  - [ ] `agent_type` returns `"codex"`
  - [ ] Lazy MCP client initialization on first `handle_message()` call
  - [ ] First message: start Codex session via `codex` MCP tool
  - [ ] Subsequent messages: continue session via `codex-reply` with stored thread ID
  - [ ] Convert Codex response to squadron `Message` objects
  - [ ] `shutdown()`: clean up MCP client and subprocess
  - [ ] Handle missing `codex` CLI with actionable error message
- [ ] **Create `src/squadron/providers/codex/provider.py` with `CodexProvider`**
  - [ ] Implement `AgentProvider` Protocol: `provider_type`, `capabilities`, `create_agent()`, `validate_credentials()`
  - [ ] `capabilities`: `can_read_files=True, supports_system_prompt=False, supports_streaming=False`
  - [ ] `create_agent()`: validate credentials via `OAuthFileStrategy`, return `CodexAgent`
  - [ ] `validate_credentials()`: check `codex` CLI on PATH + credentials exist
- [ ] **Create `src/squadron/providers/codex/__init__.py`**
  - [ ] Auto-register: `register_provider("codex", CodexProvider())`
- [ ] Success: `get_provider("codex")` returns `CodexProvider`; `CodexAgent` satisfies `Agent` Protocol

### T10: Codex provider tests

- [ ] **Create `tests/providers/codex/test_agent.py`**
  - [ ] Test: agent starts idle, transitions processing → idle during handle_message
  - [ ] Test: first message initializes MCP client lazily (mock)
  - [ ] Test: subsequent messages reuse thread (mock)
  - [ ] Test: shutdown sets terminated, cleans up
  - [ ] Test: handle_message yields Message with correct fields
  - [ ] Test: missing codex CLI raises ProviderError with install instructions
- [ ] **Create `tests/providers/codex/test_provider.py`**
  - [ ] Test: `provider_type` returns `"codex"`
  - [ ] Test: `capabilities.can_read_files` is `True`
  - [ ] Test: `create_agent()` returns CodexAgent when credentials valid
  - [ ] Test: `create_agent()` raises ProviderAuthError when no credentials
- [ ] **Create `tests/providers/codex/test_registration.py`**
  - [ ] Test: importing `squadron.providers.codex` registers `"codex"` in registry
  - [ ] Test: `get_provider("codex")` returns CodexProvider instance
- [ ] Success: all codex tests pass

**Commit**: `feat: add CodexProvider with MCP transport and OAuthFileStrategy`

---

### T11: Migrate SDK review path from runner.py into ClaudeSDKAgent

- [ ] **Absorb `runner.py` rate-limit retry logic into `ClaudeSDKAgent.handle_message()`**
  - [ ] The `ClaudeSDKClient` lifecycle (query + receive_response + rate-limit retry loop) from `runner.py` becomes the internal implementation of `ClaudeSDKAgent.handle_message()` in "query" mode
  - [ ] Preserve `MAX_PARSE_RETRIES` and the `rate_limit_event` handling
  - [ ] `handle_message()` must yield `Message` objects with the extracted text content
- [ ] **Ensure `ClaudeSDKProvider.create_agent()` accepts review-relevant config**
  - [ ] `AgentConfig.credentials.get("hooks")` → passed to `ClaudeAgentOptions` if present
  - [ ] `allowed_tools`, `permission_mode`, `setting_sources` already on `AgentConfig` and consumed
- [ ] **Delete `src/squadron/review/runner.py`**
- [ ] **Remove `run_review` import from `review_client.py`**
- [ ] Success: SDK agent handles the full review lifecycle internally; `runner.py` is gone

### T12: Migrate runner.py tests

- [ ] **Migrate `tests/review/test_runner.py` tests to `tests/providers/sdk/test_agent.py`**
  - [ ] Adapt test fixtures to use `ClaudeSDKAgent.handle_message()` instead of `run_review()`
  - [ ] Preserve coverage for rate-limit retry behavior
  - [ ] Preserve coverage for text extraction from SDK messages
- [ ] **Delete `tests/review/test_runner.py`** (or empty it with a note pointing to new location)
- [ ] Success: equivalent coverage exists in SDK agent tests; no test file references `runner.py`

**Commit**: `refactor: absorb runner.py SDK review path into ClaudeSDKAgent`

---

### T13: Unify review_client.py — replace bespoke transports with handle_message()

- [ ] **Rewrite `run_review_with_profile()` to use provider registry**
  - [ ] Look up profile: `profile_obj = get_profile(profile_name)`
  - [ ] Load provider: ensure provider module imported (same pattern as `engine.py:_load_provider`)
  - [ ] Get provider: `provider = get_provider(profile_obj.provider)`
  - [ ] Check capabilities: `if not provider.capabilities.can_read_files: prompt = _inject_file_contents(prompt, inputs)`
  - [ ] Build `AgentConfig` from profile, model, system_prompt, review template settings
  - [ ] Create agent: `agent = await provider.create_agent(config)`
  - [ ] Send message: collect all `Message` objects from `agent.handle_message(message)`
  - [ ] Extract raw text, shut down agent
  - [ ] Pass to `parse_review_output()` (unchanged)
- [ ] **Remove `_run_non_sdk_review()` function entirely**
- [ ] **Remove `_resolve_api_key()` function** (auth is now the provider's concern via `create_agent`)
- [ ] **Remove `from openai import AsyncOpenAI`** import
- [ ] **Remove `from squadron.review.runner import run_review`** import
- [ ] **Preserve prompt logging and verbosity behavior** (debug output at -vvv, prompt capture at -vv)
- [ ] **Preserve file injection logic** (`_inject_file_contents` stays — called conditionally based on capabilities)
- [ ] Success: `review_client.py` has no provider-specific imports; one code path for all profiles

### T14: Review client unification tests

- [ ] **Update `tests/review/test_review_client.py`**
  - [ ] Existing tests should pass against the new unified path (may need fixture updates)
  - [ ] Test: SDK profile routes through provider registry and ClaudeSDKAgent
  - [ ] Test: OpenAI profile routes through provider registry and OpenAICompatibleAgent
  - [ ] Test: file injection happens when `can_read_files=False`
  - [ ] Test: file injection skipped when `can_read_files=True`
  - [ ] Test: prompt logging preserved at verbosity >= 3
  - [ ] Test: prompt capture fields populated at verbosity >= 2
- [ ] **Update `tests/review/test_content_injection.py`** if it references old functions
- [ ] **Update `tests/review/test_verbosity.py`** if it references old functions
- [ ] Success: all review tests pass; `review_client.py` has zero provider-specific imports

**Commit**: `refactor: unify review transport through Agent.handle_message()`

---

### T15: CLI auth status cleanup

- [ ] **Refactor `auth_status()` in `src/squadron/cli/commands/auth.py`**
  - [ ] Remove `from squadron.providers.codex.auth import CodexAuthStrategy` (if present)
  - [ ] For each profile: call `resolve_auth_strategy_for_profile(profile)`
  - [ ] Use `strategy.is_valid()` for status, `strategy.active_source` for source column
  - [ ] No branching on `auth_type` or `api_key_env` — strategy handles it
- [ ] **Update `auth_login()` if it has string dispatch**
- [ ] Success: `sq auth status` shows correct output; no string dispatch in auth CLI

### T16: CLI auth status tests

- [ ] **Update `tests/cli/test_auth.py`**
  - [ ] Test: `sq auth status` includes rows for all built-in profiles including codex
  - [ ] Test: codex profile shows correct auth source
  - [ ] Test: profiles with no auth needed show correct status
- [ ] Success: all CLI auth tests pass

**Commit**: `refactor: eliminate string dispatch from CLI auth status`

---

### T17: Model aliases for Codex

- [ ] **Add `codex-agent` alias to `BUILT_IN_ALIASES` in `src/squadron/models/aliases.py`**
  - [ ] `"codex-agent"`: `profile: "codex"`, `model: "gpt-5.3-codex"`, `notes: "Agentic: sandbox, subscription auth"`
- [ ] **Add `codex-spark` alias**
  - [ ] `"codex-spark"`: `profile: "openai"`, `model: "gpt-5.3-codex-spark"`, `notes: "Near-instant, Pro only"`
- [ ] **Existing `codex` alias stays unchanged** (`profile: "openai"`)
- [ ] **Add alias tests**
  - [ ] Test: `codex` resolves to `profile="openai"` (unchanged)
  - [ ] Test: `codex-agent` resolves to `profile="codex"`
  - [ ] Test: `codex-spark` resolves correctly
- [ ] Success: all alias tests pass; existing aliases unchanged

**Commit**: `feat: add codex-agent and codex-spark model aliases`

---

### T18: Full validation pass

- [ ] **Run full test suite**
  - [ ] `pytest tests/ -v` — all tests pass
  - [ ] `ruff check src/ tests/` — no lint errors
  - [ ] `ruff format --check src/ tests/` — no formatting issues
  - [ ] `pyright src/` — no type errors (or only pre-existing ones)
- [ ] **Verify no review system regression**
  - [ ] Confirm `codex` model alias still has `profile: "openai"` (not `"codex"`)
  - [ ] Confirm no `if profile == "sdk"` or `if auth_type ==` in `review_client.py` or `auth.py`
  - [ ] Confirm no `AsyncOpenAI` import in `review_client.py`
  - [ ] Confirm `runner.py` is deleted
- [ ] **Verify provider registration**
  - [ ] `get_provider("openai")`, `get_provider("sdk")`, `get_provider("codex")` all work
  - [ ] Each provider exposes `capabilities` property
- [ ] **Verify CLI end-to-end**
  - [ ] `sq auth status` shows codex row with correct source
  - [ ] Error message when codex CLI not installed is user-actionable
  - [ ] Error message when no credentials is user-actionable
- [ ] Success: all checks green; no regressions

---

### T19: Documentation and slice completion

- [ ] **Update CHANGELOG.md**
  - [ ] Add entries for: provider capabilities, auth strategy refactor, SDK rename, Codex provider, review transport unification
- [ ] **Update DEVLOG.md**
  - [ ] Add Phase 6 implementation entry for slice 128
- [ ] **Update slice design status**
  - [ ] Set status to `complete` in `128-slice.review-transport-unification-provider-decoupling.md`
  - [ ] Update `dateUpdated`
- [ ] **Update slice plan**
  - [ ] Check off slice 128 in `100-slices.orchestration-v2.md`
- [ ] **Update Verification Walkthrough** with actual commands and results
- [ ] Success: all documentation updated; slice marked complete

**Commit**: `docs: complete slice 128 review transport unification`
