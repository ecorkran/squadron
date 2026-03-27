---
docType: review
layer: project
reviewType: code
slice: review-transport-unification-provider-decoupling
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/128-slice.review-transport-unification-provider-decoupling.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260327
dateUpdated: 20260327
---

# Review: code — slice 128

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] ProviderCapabilities dataclass is correctly implemented

`src/squadron/providers/base.py`: The frozen dataclass with appropriate defaults (`can_read_files=False`, `supports_system_prompt=True`, `supports_streaming=False`) follows the dataclass pattern correctly. All three providers (OpenAI, SDK, Codex) expose `capabilities` as required by the `AgentProvider` Protocol.

### [PASS] Registry-driven auth dispatch eliminates string conditionals

`src/squadron/providers/auth.py`: The refactored `resolve_auth_strategy()` now uses `AUTH_STRATEGIES[auth_type].from_config(config, profile)` with no if/elif chains on auth types. The `_register_oauth_strategy()` lazy import pattern correctly avoids circular dependencies. The new `resolve_auth_strategy_for_profile()` convenience function is well-designed for CLI auth status checks.

### [PASS] Codex provider MCP transport implementation is solid

`src/squadron/providers/codex/agent.py`: Lazy MCP client initialization, proper thread ID management for session continuity, and `AsyncExitStack` for clean resource cleanup. The `_extract_thread_id()` method handles both `structuredContent` and `result._meta` fallbacks. Error handling wraps MCP errors in `ProviderError`.

### [PASS] OAuthFileStrategy credential resolution is correct

`src/squadron/providers/codex/auth.py`: Auth file is correctly preferred over `OPENAI_API_KEY` fallback per specification. The `is_valid()` check and `get_credentials()` implementation are consistent.

### [PASS] SDK class rename is complete and consistent

`src/squadron/providers/sdk/`: `SDKAgent` → `ClaudeSDKAgent` and `SDKAgentProvider` → `ClaudeSDKProvider` are applied consistently across agent, provider, `__init__.py`, and all test files. Registration key `"sdk"` remains unchanged for backward compatibility.

### [PASS] Test coverage is comprehensive

Tests cover: state transitions, lazy initialization, session reuse, error propagation, capabilities defaults, frozen dataclass behavior, `active_source`/`setup_hint` properties, and registration mechanics. Test isolation via `_clean_registry` fixture is properly implemented.

### [PASS] Codex provider capabilities are correctly declared

`src/squadron/providers/codex/provider.py`: `can_read_files=True`, `supports_system_prompt=False`, `supports_streaming=False` accurately reflects Codex MCP capabilities per specification.

---

## Debug: Prompt & Response

### System Prompt

You are a code reviewer. Review code against language-specific rules, testing
standards, and project conventions loaded from CLAUDE.md.

Focus areas:
- Project conventions (from CLAUDE.md)
- Language-appropriate style and correctness
- Test coverage patterns (test-with, not test-after)
- Error handling patterns
- Security concerns
- Naming, structure, and documentation quality

CRITICAL: Your verdict and findings MUST be consistent.
- If verdict is CONCERNS or FAIL, include at least one finding with that severity.
- If no CONCERN or FAIL findings exist, verdict MUST be PASS.
- Every finding MUST use the exact format: ### [SEVERITY] Title

Report your findings using severity levels:

## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
Description with specific file and line references.


### User Prompt

Review code in the project at: ./project-documents/user

Run `git diff 24465e1e3384f5f302c0f16cb04cb52da4886350...128-slice.review-transport-unification-provider-decoupling` to identify changed files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/project-documents/user/tasks/128-tasks.review-transport-unification-provider-decoupling.md b/project-documents/user/tasks/128-tasks.review-transport-unification-provider-decoupling.md
index 6c336d7..09de2e7 100644
--- a/project-documents/user/tasks/128-tasks.review-transport-unification-provider-decoupling.md
+++ b/project-documents/user/tasks/128-tasks.review-transport-unification-provider-decoupling.md
@@ -7,7 +7,7 @@ dependencies: [review-provider-model-selection, auth-strategy-credential-managem
 projectState: "M1 shipped (v0.2.7). Review system has two bespoke transport paths (SDK via runner.py, non-SDK via AsyncOpenAI in review_client.py). Neither uses Agent/AgentProvider Protocols. String dispatch on profile names and auth types. Slice 124 (Codex) rewound — provider code not on main."
 dateCreated: 20260327
 dateUpdated: 20260327
-status: not_started
+status: in_progress
 ---
 
 ## Context Summary
@@ -25,24 +25,24 @@ status: not_started
 
 ### T1: ProviderCapabilities dataclass and AgentProvider Protocol update
 
-- [ ] **Add `ProviderCapabilities` to `src/squadron/providers/base.py`**
-  - [ ] Create frozen dataclass: `can_read_files: bool = False`, `supports_system_prompt: bool = True`, `supports_streaming: bool = False`
-  - [ ] Add `capabilities` property to `AgentProvider` Protocol
-  - [ ] Update `__all__` exports
-- [ ] **Add `capabilities` to `OpenAICompatibleProvider`**
-  - [ ] Return `ProviderCapabilities(can_read_files=False, supports_system_prompt=True, supports_streaming=True)`
-- [ ] **Add `capabilities` to `SDKAgentProvider` (pre-rename)**
-  - [ ] Return `ProviderCapabilities(can_read_files=True, supports_system_prompt=True, supports_streaming=True)`
-- [ ] Success: all providers expose `capabilities`; existing tests pass
+- [x] **Add `ProviderCapabilities` to `src/squadron/providers/base.py`**
+  - [x] Create frozen dataclass: `can_read_files: bool = False`, `supports_system_prompt: bool = True`, `supports_streaming: bool = False`
+  - [x] Add `capabilities` property to `AgentProvider` Protocol
+  - [x] Update `__all__` exports
+- [x] **Add `capabilities` to `OpenAICompatibleProvider`**
+  - [x] Return `ProviderCapabilities(can_read_files=False, supports_system_prompt=True, supports_streaming=True)`
+- [x] **Add `capabilities` to `SDKAgentProvider` (pre-rename)**
+  - [x] Return `ProviderCapabilities(can_read_files=True, supports_system_prompt=True, supports_streaming=True)`
+- [x] Success: all providers expose `capabilities`; existing tests pass
 
 ### T2: ProviderCapabilities tests
 
-- [ ] **Add tests for ProviderCapabilities**
-  - [ ] Test: `ProviderCapabilities()` defaults are `can_read_files=False, supports_system_prompt=True, supports_streaming=False`
-  - [ ] Test: OpenAI provider `capabilities.can_read_files` is `False`
-  - [ ] Test: SDK provider `capabilities.can_read_files` is `True`
-  - [ ] Test: capabilities dataclass is frozen (assignment raises)
-  - [ ] Success: all tests pass
+- [x] **Add tests for ProviderCapabilities**
+  - [x] Test: `ProviderCapabilities()` defaults are `can_read_files=False, supports_system_prompt=True, supports_streaming=False`
+  - [x] Test: OpenAI provider `capabilities.can_read_files` is `False`
+  - [x] Test: SDK provider `capabilities.can_read_files` is `True`
+  - [x] Test: capabilities dataclass is frozen (assignment raises)
+  - [x] Success: all tests pass
 
 **Commit**: `feat: add ProviderCapabilities dataclass to AgentProvider Protocol`
 
@@ -50,36 +50,36 @@ status: not_started
 
 ### T3: Auth strategy `from_config` factory and registry-driven dispatch
 
-- [ ] **Add `from_config` classmethod to `ApiKeyStrategy`**
-  - [ ] Signature: `from_config(cls, config: AgentConfig, profile: ProviderProfile | None) -> ApiKeyStrategy`
-  - [ ] Extracts `explicit_key`, `env_var`, `fallback_env_var`, `base_url` from config and profile (same logic currently in `resolve_auth_strategy`)
-- [ ] **Add `active_source` property and `setup_hint` property to `ApiKeyStrategy`**
-  - [ ] `active_source`: returns the env var name or "explicit" or "localhost" depending on which source resolved
-  - [ ] `setup_hint`: returns actionable instruction (e.g., "Set OPENAI_API_KEY environment variable")
-- [ ] **Refactor `resolve_auth_strategy()` to use registry only**
-  - [ ] Remove the `if auth_type == "api_key"` and `if auth_type == "codex"` branches
-  - [ ] Use: `strategy_cls = AUTH_STRATEGIES[auth_type]; return strategy_cls.from_config(config, profile)`
-  - [ ] Raise `ProviderAuthError` for unknown auth_type (unchanged)
-- [ ] **Add `resolve_auth_strategy_for_profile()` convenience function**
-  - [ ] Takes `ProviderProfile` only (no `AgentConfig` needed for status checks)
-  - [ ] Constructs minimal config, delegates to `resolve_auth_strategy()`
-- [ ] Success: `resolve_auth_strategy()` has no if/elif on auth_type; all tests pass
+- [x] **Add `from_config` classmethod to `ApiKeyStrategy`**
+  - [x] Signature: `from_config(cls, config: AgentConfig, profile: ProviderProfile | None) -> ApiKeyStrategy`
+  - [x] Extracts `explicit_key`, `env_var`, `fallback_env_var`, `base_url` from config and profile (same logic currently in `resolve_auth_strategy`)
+- [x] **Add `active_source` property and `setup_hint` property to `ApiKeyStrategy`**
+  - [x] `active_source`: returns the env var name or "explicit" or "localhost" depending on which source resolved
+  - [x] `setup_hint`: returns actionable instruction (e.g., "Set OPENAI_API_KEY environment variable")
+- [x] **Refactor `resolve_auth_strategy()` to use registry only**
+  - [x] Remove the `if auth_type == "api_key"` and `if auth_type == "codex"` branches
+  - [x] Use: `strategy_cls = AUTH_STRATEGIES[auth_type]; return strategy_cls.from_config(config, profile)`
+  - [x] Raise `ProviderAuthError` for unknown auth_type (unchanged)
+- [x] **Add `resolve_auth_strategy_for_profile()` convenience function**
+  - [x] Takes `ProviderProfile` only (no `AgentConfig` needed for status checks)
+  - [x] Constructs minimal config, delegates to `resolve_auth_strategy()`
+- [x] Success: `resolve_auth_strategy()` has no if/elif on auth_type; all tests pass
 
 ### T4: Auth strategy refactor tests
 
-- [ ] **Update existing auth resolution tests in `tests/providers/test_auth_resolution.py`**
-  - [ ] Tests should still pass — `resolve_auth_strategy` returns same results
-- [ ] **Add tests for `from_config` classmethods**
-  - [ ] Test: `ApiKeyStrategy.from_config()` with profile containing `api_key_env`
-  - [ ] Test: `ApiKeyStrategy.from_config()` with explicit key in config
-  - [ ] Test: `ApiKeyStrategy.from_config()` with localhost base_url
-- [ ] **Add tests for `active_source` and `setup_hint`**
-  - [ ] Test: `active_source` returns env var name when key found via env var
-  - [ ] Test: `setup_hint` returns actionable message
-- [ ] **Test `resolve_auth_strategy_for_profile()`**
-  - [ ] Test: returns valid strategy for `openai` profile
-  - [ ] Test: returns valid strategy for `sdk` profile
-- [ ] Success: all auth tests pass; no string dispatch in `resolve_auth_strategy`
+- [x] **Update existing auth resolution tests in `tests/providers/test_auth_resolution.py`**
+  - [x] Tests should still pass — `resolve_auth_strategy` returns same results
+- [x] **Add tests for `from_config` classmethods**
+  - [x] Test: `ApiKeyStrategy.from_config()` with profile containing `api_key_env`
+  - [x] Test: `ApiKeyStrategy.from_config()` with explicit key in config
+  - [x] Test: `ApiKeyStrategy.from_config()` with localhost base_url
+- [x] **Add tests for `active_source` and `setup_hint`**
+  - [x] Test: `active_source` returns env var name when key found via env var
+  - [x] Test: `setup_hint` returns actionable message
+- [x] **Test `resolve_auth_strategy_for_profile()`**
+  - [x] Test: returns valid strategy for `openai` profile
+  - [x] Test: returns valid strategy for `sdk` profile
+- [x] Success: all auth tests pass; no string dispatch in `resolve_auth_strategy`
 
 **Commit**: `refactor: registry-driven auth strategy dispatch with from_config factory`
 
@@ -87,29 +87,29 @@ status: not_started
 
 ### T5: OAuthFileStrategy (rename + from_config)
 
-- [ ] **Create `src/squadron/providers/codex/auth.py` with `OAuthFileStrategy`**
-  - [ ] Resolution order: `~/.codex/auth.json` (subscription) → `OPENAI_API_KEY` (fallback) → raise `ProviderAuthError`
-  - [ ] `from_config` classmethod (no-op — reads from fixed file path)
-  - [ ] `active_source` property: returns `"~/.codex/auth.json"` or `"OPENAI_API_KEY"` or `None`
-  - [ ] `setup_hint` property: returns `"Run 'codex' CLI to authenticate, or set OPENAI_API_KEY"`
-  - [ ] `is_valid()`, `get_credentials()`, `refresh_if_needed()` per AuthStrategy Protocol
-- [ ] **Register `"oauth"` in `AUTH_STRATEGIES` dict**
-- [ ] **Update codex profile in `BUILT_IN_PROFILES` (`profiles.py`)**
-  - [ ] Add `codex` profile with `provider="codex"`, `auth_type="oauth"`
-- [ ] Success: `OAuthFileStrategy` satisfies `AuthStrategy` Protocol; registered as `"oauth"`
+- [x] **Create `src/squadron/providers/codex/auth.py` with `OAuthFileStrategy`**
+  - [x] Resolution order: `~/.codex/auth.json` (subscription) → `OPENAI_API_KEY` (fallback) → raise `ProviderAuthError`
+  - [x] `from_config` classmethod (no-op — reads from fixed file path)
+  - [x] `active_source` property: returns `"~/.codex/auth.json"` or `"OPENAI_API_KEY"` or `None`
+  - [x] `setup_hint` property: returns `"Run 'codex' CLI to authenticate, or set OPENAI_API_KEY"`
+  - [x] `is_valid()`, `get_credentials()`, `refresh_if_needed()` per AuthStrategy Protocol
+- [x] **Register `"oauth"` in `AUTH_STRATEGIES` dict**
+- [x] **Update codex profile in `BUILT_IN_PROFILES` (`profiles.py`)**
+  - [x] Add `codex` profile with `provider="codex"`, `auth_type="oauth"`
+- [x] Success: `OAuthFileStrategy` satisfies `AuthStrategy` Protocol; registered as `"oauth"`
 
 ### T6: OAuthFileStrategy tests
 
-- [ ] **Create `tests/providers/codex/test_auth.py`**
-  - [ ] Test: auth file exists → `is_valid()` True, `get_credentials()` returns `{"auth_file": path}`
-  - [ ] Test: no auth file, `OPENAI_API_KEY` set → `is_valid()` True, `get_credentials()` returns `{"api_key": value}`
-  - [ ] Test: neither source → `is_valid()` False, `get_credentials()` raises `ProviderAuthError`
-  - [ ] Test: auth file preferred over API key when both exist
-  - [ ] Test: `from_config` returns working strategy
-  - [ ] Test: `active_source` reports correct source
-  - [ ] Test: `setup_hint` returns actionable message
-  - [ ] Use `monkeypatch` for env vars and `tmp_path` for auth file fixture
-- [ ] Success: all tests pass
+- [x] **Create `tests/providers/codex/test_auth.py`**
+  - [x] Test: auth file exists → `is_valid()` True, `get_credentials()` returns `{"auth_file": path}`
+  - [x] Test: no auth file, `OPENAI_API_KEY` set → `is_valid()` True, `get_credentials()` returns `{"api_key": value}`
+  - [x] Test: neither source → `is_valid()` False, `get_credentials()` raises `ProviderAuthError`
+  - [x] Test: auth file preferred over API key when both exist
+  - [x] Test: `from_config` returns working strategy
+  - [x] Test: `active_source` reports correct source
+  - [x] Test: `setup_hint` returns actionable message
+  - [x] Use `monkeypatch` for env vars and `tmp_path` for auth file fixture
+- [x] Success: all tests pass
 
 **Commit**: `feat: add OAuthFileStrategy for subscription credential resolution`
 
@@ -117,27 +117,27 @@ status: not_started
 
 ### T7: Rename SDKAgent → ClaudeSDKAgent, SDKAgentProvider → ClaudeSDKProvider
 
-- [ ] **Rename classes in `src/squadron/providers/sdk/agent.py`**
-  - [ ] `SDKAgent` → `ClaudeSDKAgent`
-  - [ ] Update all internal references
-- [ ] **Rename classes in `src/squadron/providers/sdk/provider.py`**
-  - [ ] `SDKAgentProvider` → `ClaudeSDKProvider`
-  - [ ] Update all internal references
-- [ ] **Update `src/squadron/providers/sdk/__init__.py`**
-  - [ ] Update imports and `__all__` exports
-  - [ ] Registration: `register_provider("sdk", ClaudeSDKProvider())` (key unchanged)
-- [ ] **Update all test files referencing old names**
-  - [ ] `tests/providers/sdk/test_agent.py`, `test_provider.py`, `test_registration.py`
-- [ ] **Update any other imports across codebase**
-  - [ ] Search for `SDKAgent` and `SDKAgentProvider` in all `.py` files
-- [ ] Success: `ruff check` clean; all tests pass; `get_provider("sdk")` returns `ClaudeSDKProvider`
+- [x] **Rename classes in `src/squadron/providers/sdk/agent.py`**
+  - [x] `SDKAgent` → `ClaudeSDKAgent`
+  - [x] Update all internal references
+- [x] **Rename classes in `src/squadron/providers/sdk/provider.py`**
+  - [x] `SDKAgentProvider` → `ClaudeSDKProvider`
+  - [x] Update all internal references
+- [x] **Update `src/squadron/providers/sdk/__init__.py`**
+  - [x] Update imports and `__all__` exports
+  - [x] Registration: `register_provider("sdk", ClaudeSDKProvider())` (key unchanged)
+- [x] **Update all test files referencing old names**
+  - [x] `tests/providers/sdk/test_agent.py`, `test_provider.py`, `test_registration.py`
+- [x] **Update any other imports across codebase**
+  - [x] Search for `SDKAgent` and `SDKAgentProvider` in all `.py` files
+- [x] Success: `ruff check` clean; all tests pass; `get_provider("sdk")` returns `ClaudeSDKProvider`
 
 ### T8: Rename tests
 
-- [ ] **Verify all SDK tests pass after rename**
-  - [ ] `pytest tests/providers/sdk/ -v` — all green
-  - [ ] `pytest tests/ -v` — full suite green (no broken imports)
-- [ ] Success: zero test failures
+- [x] **Verify all SDK tests pass after rename**
+  - [x] `pytest tests/providers/sdk/ -v` — all green
+  - [x] `pytest tests/ -v` — full suite green (no broken imports)
+- [x] Success: zero test failures
 
 **Commit**: `refactor: rename SDKAgent to ClaudeSDKAgent for clarity`
 
@@ -145,42 +145,42 @@ status: not_started
 
 ### T9: Codex provider implementation
 
-- [ ] **Create `src/squadron/providers/codex/agent.py` with `CodexAgent`**
-  - [ ] Implement `Agent` Protocol: `name`, `agent_type`, `state`, `handle_message()`, `shutdown()`
-  - [ ] `agent_type` returns `"codex"`
-  - [ ] Lazy MCP client initialization on first `handle_message()` call
-  - [ ] First message: start Codex session via `codex` MCP tool
-  - [ ] Subsequent messages: continue session via `codex-reply` with stored thread ID
-  - [ ] Convert Codex response to squadron `Message` objects
-  - [ ] `shutdown()`: clean up MCP client and subprocess
-  - [ ] Handle missing `codex` CLI with actionable error message
-- [ ] **Create `src/squadron/providers/codex/provider.py` with `CodexProvider`**
-  - [ ] Implement `AgentProvider` Protocol: `provider_type`, `capabilities`, `create_agent()`, `validate_credentials()`
-  - [ ] `capabilities`: `can_read_files=True, supports_system_prompt=False, supports_streaming=False`
-  - [ ] `create_agent()`: validate credentials via `OAuthFileStrategy`, return `CodexAgent`
-  - [ ] `validate_credentials()`: check `codex` CLI on PATH + credentials exist
-- [ ] **Create `src/squadron/providers/codex/__init__.py`**
-  - [ ] Auto-register: `register_provider("codex", CodexProvider())`
-- [ ] Success: `get_provider("codex")` returns `CodexProvider`; `CodexAgent` satisfies `Agent` Protocol
+- [x] **Create `src/squadron/providers/codex/agent.py` with `CodexAgent`**
+  - [x] Implement `Agent` Protocol: `name`, `agent_type`, `state`, `handle_message()`, `shutdown()`
+  - [x] `agent_type` returns `"codex"`
+  - [x] Lazy MCP client initialization on first `handle_message()` call
+  - [x] First message: start Codex session via `codex` MCP tool
+  - [x] Subsequent messages: continue session via `codex-reply` with stored thread ID
+  - [x] Convert Codex response to squadron `Message` objects
+  - [x] `shutdown()`: clean up MCP client and subprocess
+  - [x] Handle missing `codex` CLI with actionable error message
+- [x] **Create `src/squadron/providers/codex/provider.py` with `CodexProvider`**
+  - [x] Implement `AgentProvider` Protocol: `provider_type`, `capabilities`, `create_agent()`, `validate_credentials()`
+  - [x] `capabilities`: `can_read_files=True, supports_system_prompt=False, supports_streaming=False`
+  - [x] `create_agent()`: validate credentials via `OAuthFileStrategy`, return `CodexAgent`
+  - [x] `validate_credentials()`: check `codex` CLI on PATH + credentials exist
+- [x] **Create `src/squadron/providers/codex/__init__.py`**
+  - [x] Auto-register: `register_provider("codex", CodexProvider())`
+- [x] Success: `get_provider("codex")` returns `CodexProvider`; `CodexAgent` satisfies `Agent` Protocol
 
 ### T10: Codex provider tests
 
-- [ ] **Create `tests/providers/codex/test_agent.py`**
-  - [ ] Test: agent starts idle, transitions processing → idle during handle_message
-  - [ ] Test: first message initializes MCP client lazily (mock)
-  - [ ] Test: subsequent messages reuse thread (mock)
-  - [ ] Test: shutdown sets terminated, cleans up
-  - [ ] Test: handle_message yields Message with correct fields
-  - [ ] Test: missing codex CLI raises ProviderError with install instructions
-- [ ] **Create `tests/providers/codex/test_provider.py`**
-  - [ ] Test: `provider_type` returns `"codex"`
-  - [ ] Test: `capabilities.can_read_files` is `True`
-  - [ ] Test: `create_agent()` returns CodexAgent when credentials valid
-  - [ ] Test: `create_agent()` raises ProviderAuthError when no credentials
-- [ ] **Create `tests/providers/codex/test_registration.py`**
-  - [ ] Test: importing `squadron.providers.codex` registers `"codex"` in registry
-  - [ ] Test: `get_provider("codex")` returns CodexProvider instance
-- [ ] Success: all codex tests pass
+- [x] **Create `tests/providers/codex/test_agent.py`**
+  - [x] Test: agent starts idle, transitions processing → idle during handle_message
+  - [x] Test: first message initializes MCP client lazily (mock)
+  - [x] Test: subsequent messages reuse thread (mock)
+  - [x] Test: shutdown sets terminated, cleans up
+  - [x] Test: handle_message yields Message with correct fields
+  - [x] Test: missing codex CLI raises ProviderError with install instructions
+- [x] **Create `tests/providers/codex/test_provider.py`**
+  - [x] Test: `provider_type` returns `"codex"`
+  - [x] Test: `capabilities.can_read_files` is `True`
+  - [x] Test: `create_agent()` returns CodexAgent when credentials valid
+  - [x] Test: `create_agent()` raises ProviderAuthError when no credentials
+- [x] **Create `tests/providers/codex/test_registration.py`**
+  - [x] Test: importing `squadron.providers.codex` registers `"codex"` in registry
+  - [x] Test: `get_provider("codex")` returns CodexProvider instance
+- [x] Success: all codex tests pass
 
 **Commit**: `feat: add CodexProvider with MCP transport and OAuthFileStrategy`
 
diff --git a/src/squadron/providers/auth.py b/src/squadron/providers/auth.py
index 9dfa35d..b139093 100644
--- a/src/squadron/providers/auth.py
+++ b/src/squadron/providers/auth.py
@@ -34,6 +34,25 @@ class AuthStrategy(Protocol):
         """Return True if credentials are currently available and usable."""
         ...
 
+    @property
+    def active_source(self) -> str | None:
+        """Return the credential source that would be used, or None."""
+        ...
+
+    @property
+    def setup_hint(self) -> str:
+        """Return actionable instructions for setting up credentials."""
+        ...
+
+    @classmethod
+    def from_config(
+        cls,
+        config: AgentConfig,
+        profile: ProviderProfile | None = None,
+    ) -> AuthStrategy:
+        """Construct a strategy instance from config and optional profile."""
+        ...
+
 
 class ApiKeyStrategy:
     """Resolve an API key from explicit value, env var chain, or localhost bypass."""
@@ -51,6 +70,27 @@ class ApiKeyStrategy:
         self._fallback_env_var = fallback_env_var
         self._base_url = base_url
 
+    @classmethod
+    def from_config(
+        cls,
+        config: AgentConfig,
+        profile: ProviderProfile | None = None,
+    ) -> ApiKeyStrategy:
+        """Build from AgentConfig and optional profile."""
+        env_var: str | None
+        if profile is not None:
+            env_var = profile.api_key_env
+        else:
+            raw = config.credentials.get("api_key_env")
+            env_var = str(raw) if raw is not None else None
+
+        return cls(
+            explicit_key=config.api_key,
+            env_var=env_var,
+            fallback_env_var="OPENAI_API_KEY",
+            base_url=config.base_url,
+        )
+
     def _is_localhost(self) -> bool:
         url = self._base_url or ""
         return url.startswith("http://localhost") or url.startswith("http://127.0.0.1")
@@ -70,6 +110,25 @@ class ApiKeyStrategy:
             return "not-needed"
         return None
 
+    @property
+    def active_source(self) -> str | None:
+        """Return which credential source would be used."""
+        if self._explicit_key:
+            return "explicit"
+        if self._env_var and os.environ.get(self._env_var):
+            return self._env_var
+        if os.environ.get(self._fallback_env_var):
+            return self._fallback_env_var
+        if self._is_localhost():
+            return "localhost"
+        return None
+
+    @property
+    def setup_hint(self) -> str:
+        """Return actionable setup instructions."""
+        env = self._env_var or self._fallback_env_var
+        return f"Set {env} environment variable"
+
     async def get_credentials(self) -> dict[str, str]:
         """Return {"api_key": "<resolved_key>"}.
 
@@ -83,8 +142,7 @@ class ApiKeyStrategy:
         key = self._resolve()
         if key is None:
             raise ProviderAuthError(
-                "No API key found. Set config.api_key, the profile"
-                " api_key_env var, or OPENAI_API_KEY."
+                f"No API key found. {self.setup_hint}."
             )
         return {"api_key": key}
 
@@ -97,12 +155,56 @@ class ApiKeyStrategy:
 
 
 # Registry mapping auth_type strings to strategy classes.
+# Each class must implement from_config(config, profile) classmethod.
 AUTH_STRATEGIES: dict[str, type] = {
     "api_key": ApiKeyStrategy,
-    # Future: "oauth": OAuthStrategy (slice 116)
+    # "session" added below
+    # "oauth" added below (lazy import to avoid circular dependency)
 }
 
 
+def _register_oauth_strategy() -> None:
+    """Register OAuthFileStrategy lazily to avoid circular import."""
+    from squadron.providers.codex.auth import OAuthFileStrategy
+
+    AUTH_STRATEGIES["oauth"] = OAuthFileStrategy
+
+
+_register_oauth_strategy()
+
+
+class _SessionStrategy:
+    """No-op auth strategy for SDK sessions (no credentials needed)."""
+
+    @classmethod
+    def from_config(
+        cls,
+        config: AgentConfig,
+        profile: ProviderProfile | None = None,
+    ) -> _SessionStrategy:
+        return cls()
+
+    async def get_credentials(self) -> dict[str, str]:
+        return {}
+
+    async def refresh_if_needed(self) -> None:
+        pass
+
+    def is_valid(self) -> bool:
+        return True
+
+    @property
+    def active_source(self) -> str | None:
+        return "(session)"
+
+    @property
+    def setup_hint(self) -> str:
+        return "No setup needed — uses active Claude Code session"
+
+
+AUTH_STRATEGIES["session"] = _SessionStrategy
+
+
 def resolve_auth_strategy(
     config: AgentConfig,
     profile: ProviderProfile | None = None,
@@ -110,7 +212,8 @@ def resolve_auth_strategy(
     """Build an AuthStrategy from config and optional profile.
 
     Reads auth_type from profile (defaults to "api_key" if no profile).
-    Raises ProviderAuthError for unknown auth_type values.
+    Dispatches to the strategy's ``from_config`` classmethod — no
+    if/elif chains on auth_type values.
     """
     auth_type: str = profile.auth_type if profile is not None else "api_key"
 
@@ -121,20 +224,19 @@ def resolve_auth_strategy(
             f"Unknown auth_type {auth_type!r}. Available: {available}"
         )
 
-    if auth_type == "api_key":
-        env_var: str | None
-        if profile is not None:
-            env_var = profile.api_key_env
-        else:
-            raw = config.credentials.get("api_key_env")
-            env_var = str(raw) if raw is not None else None
+    return strategy_cls.from_config(config, profile)
 
-        return ApiKeyStrategy(
-            explicit_key=config.api_key,
-            env_var=env_var,
-            fallback_env_var="OPENAI_API_KEY",
-            base_url=config.base_url,
-        )
 
-    # Unreachable until additional auth types are added to the registry.
-    raise ProviderAuthError(f"Auth type {auth_type!r} not yet implemented")
+def resolve_auth_strategy_for_profile(profile: ProviderProfile) -> AuthStrategy:
+    """Convenience: resolve auth strategy from profile alone (no AgentConfig).
+
+    Used by CLI auth status where no agent config exists.
+    """
+    from squadron.core.models import AgentConfig
+
+    minimal_config = AgentConfig(
+        name="_auth_check",
+        agent_type="api",
+        provider=profile.provider,
+    )
+    return resolve_auth_strategy(minimal_config, profile)
diff --git a/src/squadron/providers/base.py b/src/squadron/providers/base.py
index 1c5b142..4b6c068 100644
--- a/src/squadron/providers/base.py
+++ b/src/squadron/providers/base.py
@@ -3,11 +3,29 @@
 from __future__ import annotations
 
 from collections.abc import AsyncIterator
+from dataclasses import dataclass
 from typing import Protocol, runtime_checkable
 
 from squadron.core.models import AgentConfig, AgentState, Message
 
 
+@dataclass(frozen=True)
+class ProviderCapabilities:
+    """Declared capabilities of a provider.
+
+    Callers adapt based on capabilities, not provider identity.
+    """
+
+    can_read_files: bool = False
+    """Agent can read project files directly (e.g. SDK, Codex sandbox)."""
+
+    supports_system_prompt: bool = True
+    """Agent accepts a system prompt via config."""
+
+    supports_streaming: bool = False
+    """Agent yields incremental response chunks."""
+
+
 @runtime_checkable
 class Agent(Protocol):
     """A participant that can receive and produce messages."""
@@ -19,7 +37,7 @@ class Agent(Protocol):
 
     @property
     def agent_type(self) -> str:
-        """Execution model: "sdk" or "api"."""
+        """Execution model identifier."""
         ...
 
     @property
@@ -42,7 +60,12 @@ class AgentProvider(Protocol):
 
     @property
     def provider_type(self) -> str:
-        """Provider identifier: "sdk", "anthropic", "openai", etc."""
+        """Provider identifier."""
+        ...
+
+    @property
+    def capabilities(self) -> ProviderCapabilities:
+        """Declared capabilities of this provider."""
         ...
 
     async def create_agent(self, config: AgentConfig) -> Agent:
diff --git a/src/squadron/providers/codex/__init__.py b/src/squadron/providers/codex/__init__.py
new file mode 100644
index 0000000..505f4ac
--- /dev/null
+++ b/src/squadron/providers/codex/__init__.py
@@ -0,0 +1,13 @@
+"""Codex Agent Provider — agentic tasks via Codex MCP server."""
+
+from __future__ import annotations
+
+from squadron.providers.codex.agent import CodexAgent
+from squadron.providers.codex.provider import CodexProvider
+from squadron.providers.registry import register_provider
+
+# Auto-register on import.
+_provider = CodexProvider()
+register_provider("codex", _provider)
+
+__all__ = ["CodexProvider", "CodexAgent"]
diff --git a/src/squadron/providers/codex/agent.py b/src/squadron/providers/codex/agent.py
new file mode 100644
index 0000000..8f79e9c
--- /dev/null
+++ b/src/squadron/providers/codex/agent.py
@@ -0,0 +1,177 @@
+"""CodexAgent — agentic provider via Codex MCP server (stdio transport)."""
+
+from __future__ import annotations
+
+import os
+from collections.abc import AsyncIterator
+from contextlib import AsyncExitStack
+from typing import Any
+
+from mcp import ClientSession, StdioServerParameters, stdio_client
+
+from squadron.core.models import AgentConfig, AgentState, Message, MessageType
+from squadron.logging import get_logger
+from squadron.providers.errors import ProviderError
+
+_log = get_logger("squadron.providers.codex.agent")
+
+_DEFAULT_SANDBOX = "read-only"
+
+
+class CodexAgent:
+    """Agentic provider backed by Codex MCP server (``codex mcp-server``).
+
+    The MCP client is started lazily on first ``handle_message()`` call
+    to avoid spawning a subprocess for agents that may never be used.
+    """
+
+    def __init__(self, name: str, config: AgentConfig) -> None:
+        self._name = name
+        self._config = config
+        self._state = AgentState.idle
+        self._session: ClientSession | None = None
+        self._exit_stack: AsyncExitStack | None = None
+        self._thread_id: str | None = None
+
+    @property
+    def name(self) -> str:
+        return self._name
+
+    @property
+    def agent_type(self) -> str:
+        return "codex"
+
+    @property
+    def state(self) -> AgentState:
+        return self._state
+
+    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
+        """Send a message to the Codex agent and yield response Messages."""
+        self._state = AgentState.processing
+        try:
+            if self._session is None:
+                await self._start_client()
+
+            if self._thread_id is None:
+                response = await self._codex_start(message.content)
+            else:
+                response = await self._codex_reply(message.content)
+
+            yield response
+        except ProviderError:
+            raise
+        except Exception as exc:
+            raise ProviderError(f"Codex agent error: {exc}") from exc
+        finally:
+            self._state = AgentState.idle
+
+    async def shutdown(self) -> None:
+        """Tear down the MCP client and subprocess."""
+        if self._exit_stack is not None:
+            await self._exit_stack.aclose()
+            self._exit_stack = None
+        self._session = None
+        self._thread_id = None
+        self._state = AgentState.terminated
+
+    async def _start_client(self) -> None:
+        """Spawn ``codex mcp-server`` and initialize MCP session."""
+        codex_cmd = self._resolve_codex_command()
+        server_params = StdioServerParameters(
+            command=codex_cmd,
+            args=["mcp-server"],
+        )
+
+        self._exit_stack = AsyncExitStack()
+        try:
+            transport = await self._exit_stack.enter_async_context(
+                stdio_client(server_params)
+            )
+            read_stream, write_stream = transport
+            session = await self._exit_stack.enter_async_context(
+                ClientSession(read_stream, write_stream)
+            )
+            await session.initialize()
+            self._session = session
+            _log.debug("Codex MCP session initialized for agent %r", self._name)
+        except Exception:
+            await self._exit_stack.aclose()
+            self._exit_stack = None
+            raise
+
+    def _resolve_codex_command(self) -> str:
+        """Find the ``codex`` CLI binary on PATH."""
+        import shutil
+
+        cmd = shutil.which("codex")
+        if cmd is None:
+            raise ProviderError(
+                "Codex CLI not found on PATH. "
+                "Install it with: npm i -g @openai/codex"
+            )
+        return cmd
+
+    async def _codex_start(self, prompt: str) -> Message:
+        """Start a new Codex session via the ``codex`` MCP tool."""
+        assert self._session is not None  # noqa: S101
+        model = self._config.model or "gpt-5.3-codex"
+        sandbox = self._config.credentials.get("sandbox", _DEFAULT_SANDBOX)
+        cwd = self._config.cwd or os.getcwd()
+
+        arguments: dict[str, Any] = {
+            "prompt": prompt,
+            "model": model,
+            "approval-policy": "never",
+            "sandbox": sandbox,
+            "cwd": cwd,
+        }
+        _log.debug("Calling codex tool: model=%s, sandbox=%s", model, sandbox)
+        result = await self._session.call_tool("codex", arguments)
+
+        response_text = self._extract_text(result)
+        thread_id = self._extract_thread_id(result)
+        if thread_id:
+            self._thread_id = thread_id
+
+        return Message(
+            sender=self._name,
+            recipients=[],
+            content=response_text,
+            message_type=MessageType.chat,
+        )
+
+    async def _codex_reply(self, prompt: str) -> Message:
+        """Continue an existing Codex session via ``codex-reply`` MCP tool."""
+        assert self._session is not None  # noqa: S101
+        assert self._thread_id is not None  # noqa: S101
+
+        arguments: dict[str, Any] = {
+            "prompt": prompt,
+            "threadId": self._thread_id,
+        }
+        _log.debug("Calling codex-reply: threadId=%s", self._thread_id)
+        result = await self._session.call_tool("codex-reply", arguments)
+        response_text = self._extract_text(result)
+        return Message(
+            sender=self._name,
+            recipients=[],
+            content=response_text,
+            message_type=MessageType.chat,
+        )
+
+    def _extract_text(self, result: Any) -> str:
+        """Extract text content from an MCP CallToolResult."""
+        if result.isError:
+            parts = [c.text for c in result.content if hasattr(c, "text")]
+            raise ProviderError(f"Codex tool error: {' '.join(parts)}")
+
+        parts = [c.text for c in result.content if hasattr(c, "text")]
+        return "\n".join(parts) if parts else ""
+
+    def _extract_thread_id(self, result: Any) -> str | None:
+        """Extract thread ID from structured content if present."""
+        if result.structuredContent and "threadId" in result.structuredContent:
+            return str(result.structuredContent["threadId"])
+        if result._meta and "threadId" in result._meta:
+            return str(result._meta["threadId"])
+        return None
diff --git a/src/squadron/providers/codex/auth.py b/src/squadron/providers/codex/auth.py
new file mode 100644
index 0000000..94e7c6b
--- /dev/null
+++ b/src/squadron/providers/codex/auth.py
@@ -0,0 +1,87 @@
+"""OAuthFileStrategy — credential resolution from cached OAuth tokens or API key."""
+
+from __future__ import annotations
+
+import os
+from pathlib import Path
+from typing import TYPE_CHECKING
+
+from squadron.providers.errors import ProviderAuthError
+
+if TYPE_CHECKING:
+    from squadron.core.models import AgentConfig
+    from squadron.providers.profiles import ProviderProfile
+
+# Default location for Codex CLI cached credentials.
+_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"
+
+
+class OAuthFileStrategy:
+    """Resolve credentials from a cached OAuth token file or API key fallback.
+
+    Resolution order (subscription-first):
+    1. Auth file (e.g. ``~/.codex/auth.json``, written by OAuth login)
+    2. ``OPENAI_API_KEY`` environment variable (fallback)
+    3. Raise ``ProviderAuthError`` with actionable instructions
+
+    The auth file is preferred so that users with a subscription
+    use their subscription quota, while ``OPENAI_API_KEY`` remains
+    available for other providers via the ``api_key`` auth type.
+    """
+
+    def __init__(self, auth_file: Path | None = None) -> None:
+        self._auth_file = auth_file or _CODEX_AUTH_FILE
+
+    @classmethod
+    def from_config(
+        cls,
+        config: AgentConfig,
+        profile: ProviderProfile | None = None,
+    ) -> OAuthFileStrategy:
+        """Construct from config — no config needed (reads fixed file path)."""
+        return cls()
+
+    def _has_api_key(self) -> bool:
+        return bool(os.environ.get("OPENAI_API_KEY"))
+
+    def _has_auth_file(self) -> bool:
+        return self._auth_file.is_file()
+
+    @property
+    def active_source(self) -> str | None:
+        """Return the credential source that would be used, or None."""
+        if self._has_auth_file():
+            return "~/.codex/auth.json"
+        if self._has_api_key():
+            return "OPENAI_API_KEY"
+        return None
+
+    @property
+    def setup_hint(self) -> str:
+        """Return actionable setup instructions."""
+        return "Run 'codex' CLI to authenticate, or set OPENAI_API_KEY"
+
+    async def get_credentials(self) -> dict[str, str]:
+        """Return credentials dict.
+
+        Returns ``{"auth_file": "<path>"}`` when the auth file exists
+        (subscription), or ``{"api_key": "<value>"}`` when ``OPENAI_API_KEY``
+        is set (API credits fallback).
+        """
+        if self._has_auth_file():
+            return {"auth_file": str(self._auth_file)}
+
+        api_key = os.environ.get("OPENAI_API_KEY")
+        if api_key:
+            return {"api_key": api_key}
+
+        raise ProviderAuthError(
+            f"No credentials found. {self.setup_hint}."
+        )
+
+    async def refresh_if_needed(self) -> None:
+        """No-op — token refresh handled by the runtime internally."""
+
+    def is_valid(self) -> bool:
+        """Return True if either credential source resolves."""
+        return self._has_auth_file() or self._has_api_key()
diff --git a/src/squadron/providers/codex/provider.py b/src/squadron/providers/codex/provider.py
new file mode 100644
index 0000000..e7a953a
--- /dev/null
+++ b/src/squadron/providers/codex/provider.py
@@ -0,0 +1,47 @@
+"""CodexProvider — creates Codex agents via MCP transport."""
+
+from __future__ import annotations
+
+import shutil
+
+from squadron.core.models import AgentConfig
+from squadron.logging import get_logger
+from squadron.providers.base import ProviderCapabilities
+from squadron.providers.codex.agent import CodexAgent
+from squadron.providers.codex.auth import OAuthFileStrategy
+from squadron.providers.errors import ProviderAuthError
+
+_log = get_logger("squadron.providers.codex.provider")
+
+
+class CodexProvider:
+    """Creates agentic Codex agents backed by ``codex mcp-server``."""
+
+    @property
+    def provider_type(self) -> str:
+        return "codex"
+
+    @property
+    def capabilities(self) -> ProviderCapabilities:
+        return ProviderCapabilities(
+            can_read_files=True,
+            supports_system_prompt=False,
+            supports_streaming=False,
+        )
+
+    async def create_agent(self, config: AgentConfig) -> CodexAgent:
+        """Validate credentials and return a ``CodexAgent``."""
+        strategy = OAuthFileStrategy()
+        if not strategy.is_valid():
+            raise ProviderAuthError(
+                f"No Codex credentials found. {strategy.setup_hint}."
+            )
+
+        _log.debug("Creating Codex agent %r (model=%s)", config.name, config.model)
+        return CodexAgent(name=config.name, config=config)
+
+    async def validate_credentials(self) -> bool:
+        """Return True if ``codex`` CLI is on PATH and credentials exist."""
+        if shutil.which("codex") is None:
+            return False
+        return OAuthFileStrategy().is_valid()
diff --git a/src/squadron/providers/openai/provider.py b/src/squadron/providers/openai/provider.py
index fde4c82..37dc38c 100644
--- a/src/squadron/providers/openai/provider.py
+++ b/src/squadron/providers/openai/provider.py
@@ -10,6 +10,7 @@ from openai import AsyncOpenAI
 from squadron.core.models import AgentConfig
 from squadron.logging import get_logger
 from squadron.providers.auth import resolve_auth_strategy
+from squadron.providers.base import ProviderCapabilities
 from squadron.providers.errors import ProviderError
 
 if TYPE_CHECKING:
@@ -25,6 +26,14 @@ class OpenAICompatibleProvider:
     def provider_type(self) -> str:
         return "openai"
 
+    @property
+    def capabilities(self) -> ProviderCapabilities:
+        return ProviderCapabilities(
+            can_read_files=False,
+            supports_system_prompt=True,
+            supports_streaming=True,
+        )
+
     async def create_agent(self, config: AgentConfig) -> OpenAICompatibleAgent:
         """Resolve credentials via AuthStrategy, construct AsyncOpenAI client."""
         strategy = resolve_auth_strategy(config, profile=None)
diff --git a/src/squadron/providers/profiles.py b/src/squadron/providers/profiles.py
index 4e0d3e7..a7b804c 100644
--- a/src/squadron/providers/profiles.py
+++ b/src/squadron/providers/profiles.py
@@ -60,6 +60,13 @@ BUILT_IN_PROFILES: dict[str, ProviderProfile] = {
         description="Claude Code SDK (uses active Claude Code session credentials)",
         auth_type="session",
     ),
+    "codex": ProviderProfile(
+        name="codex",
+        provider="codex",
+        api_key_env=None,
+        description="OpenAI Codex agent (MCP) — agentic tasks with sandbox",
+        auth_type="oauth",
+    ),
 }
 
 
diff --git a/src/squadron/providers/sdk/__init__.py b/src/squadron/providers/sdk/__init__.py
index 26a79c2..062ae40 100644
--- a/src/squadron/providers/sdk/__init__.py
+++ b/src/squadron/providers/sdk/__init__.py
@@ -1,13 +1,13 @@
-"""SDK Agent Provider using claude-agent-sdk."""
+"""Claude SDK Agent Provider using claude-agent-sdk."""
 
 from __future__ import annotations
 
 from squadron.providers.registry import register_provider
-from squadron.providers.sdk.agent import SDKAgent
-from squadron.providers.sdk.provider import SDKAgentProvider
+from squadron.providers.sdk.agent import ClaudeSDKAgent
+from squadron.providers.sdk.provider import ClaudeSDKProvider
 
 # Auto-register on import.
-_provider = SDKAgentProvider()
+_provider = ClaudeSDKProvider()
 register_provider("sdk", _provider)
 
-__all__ = ["SDKAgentProvider", "SDKAgent"]
+__all__ = ["ClaudeSDKProvider", "ClaudeSDKAgent"]
diff --git a/src/squadron/providers/sdk/agent.py b/src/squadron/providers/sdk/agent.py
index 4f9f8fd..aaf03c0 100644
--- a/src/squadron/providers/sdk/agent.py
+++ b/src/squadron/providers/sdk/agent.py
@@ -1,4 +1,4 @@
-"""SDKAgent implementation. Wraps claude-agent-sdk query/client for task execution."""
+"""ClaudeSDKAgent — wraps claude-agent-sdk for task execution."""
 
 from __future__ import annotations
 
@@ -27,7 +27,7 @@ from squadron.providers.errors import (
 from squadron.providers.sdk.translation import translate_sdk_message
 
 
-class SDKAgent:
+class ClaudeSDKAgent:
     """An autonomous agent backed by claude-agent-sdk."""
 
     def __init__(
diff --git a/src/squadron/providers/sdk/provider.py b/src/squadron/providers/sdk/provider.py
index 4fbb74e..a3b8a78 100644
--- a/src/squadron/providers/sdk/provider.py
+++ b/src/squadron/providers/sdk/provider.py
@@ -1,4 +1,4 @@
-"""SDKAgentProvider implementation. Creates and manages SDK-based agents."""
+"""ClaudeSDKProvider implementation. Creates and manages SDK-based agents."""
 
 from __future__ import annotations
 
@@ -8,9 +8,10 @@ from claude_agent_sdk import ClaudeAgentOptions
 
 from squadron.core.models import AgentConfig
 from squadron.logging import get_logger
+from squadron.providers.base import ProviderCapabilities
 
 if TYPE_CHECKING:
-    from squadron.providers.sdk.agent import SDKAgent
+    from squadron.providers.sdk.agent import ClaudeSDKAgent
 
 _log = get_logger("squadron.providers.sdk.provider")
 
@@ -18,15 +19,23 @@ _log = get_logger("squadron.providers.sdk.provider")
 _DEFAULT_PERMISSION_MODE = "acceptEdits"
 
 
-class SDKAgentProvider:
+class ClaudeSDKProvider:
     """Creates SDK-based agents backed by claude-agent-sdk."""
 
     @property
     def provider_type(self) -> str:
         return "sdk"
 
-    async def create_agent(self, config: AgentConfig) -> SDKAgent:
-        """Build ``ClaudeAgentOptions`` from *config* and return an ``SDKAgent``."""
+    @property
+    def capabilities(self) -> ProviderCapabilities:
+        return ProviderCapabilities(
+            can_read_files=True,
+            supports_system_prompt=True,
+            supports_streaming=True,
+        )
+
+    async def create_agent(self, config: AgentConfig) -> ClaudeSDKAgent:
+        """Build ``ClaudeAgentOptions`` from *config* and return an ``ClaudeSDKAgent``."""
         kwargs: dict[str, object] = {}
 
         if config.instructions is not None:
@@ -50,10 +59,10 @@ class SDKAgentProvider:
         mode = config.credentials.get("mode", "query")
 
         # Deferred import to avoid circular / stub-state issues at module load.
-        from squadron.providers.sdk.agent import SDKAgent
+        from squadron.providers.sdk.agent import ClaudeSDKAgent
 
         _log.debug("Creating SDK agent %r (mode=%s)", config.name, mode)
-        return SDKAgent(name=config.name, options=options, mode=mode)
+        return ClaudeSDKAgent(name=config.name, options=options, mode=mode)
 
     async def validate_credentials(self) -> bool:
         """Return ``True`` if ``claude_agent_sdk`` is importable."""
diff --git a/tests/providers/codex/__init__.py b/tests/providers/codex/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/providers/codex/test_agent.py b/tests/providers/codex/test_agent.py
new file mode 100644
index 0000000..9c51c4d
--- /dev/null
+++ b/tests/providers/codex/test_agent.py
@@ -0,0 +1,199 @@
+"""Tests for CodexAgent — MCP transport path."""
+
+from __future__ import annotations
+
+import asyncio
+from unittest.mock import AsyncMock, MagicMock, patch
+
+import pytest
+
+from squadron.core.models import AgentConfig, AgentState, Message, MessageType
+from squadron.providers.codex.agent import CodexAgent
+from squadron.providers.errors import ProviderError
+
+
+@pytest.fixture()
+def agent_config() -> AgentConfig:
+    return AgentConfig(
+        name="test-codex",
+        agent_type="codex",
+        provider="codex",
+        model="gpt-5.3-codex",
+        cwd="/tmp/test-project",
+    )
+
+
+@pytest.fixture()
+def agent(agent_config: AgentConfig) -> CodexAgent:
+    return CodexAgent(name="test-codex", config=agent_config)
+
+
+def _make_message(content: str = "hello") -> Message:
+    return Message(
+        sender="user",
+        recipients=["test-codex"],
+        content=content,
+        message_type=MessageType.chat,
+    )
+
+
+def _mock_call_tool_result(
+    text: str = "Codex response",
+    *,
+    is_error: bool = False,
+    thread_id: str | None = "thread-abc-123",
+) -> MagicMock:
+    text_content = MagicMock()
+    text_content.text = text
+    result = MagicMock()
+    result.isError = is_error
+    result.content = [text_content]
+    result.structuredContent = {"threadId": thread_id} if thread_id else None
+    result._meta = None
+    return result
+
+
+class TestInitialState:
+    def test_starts_idle(self, agent: CodexAgent) -> None:
+        assert agent.state == AgentState.idle
+
+    def test_name(self, agent: CodexAgent) -> None:
+        assert agent.name == "test-codex"
+
+    def test_agent_type(self, agent: CodexAgent) -> None:
+        assert agent.agent_type == "codex"
+
+
+class TestHandleMessage:
+    def test_first_message_initializes_client(self, agent: CodexAgent) -> None:
+        mock_session = AsyncMock()
+        mock_session.call_tool = AsyncMock(return_value=_mock_call_tool_result())
+        mock_session.initialize = AsyncMock()
+
+        with patch.object(
+            agent, "_start_client", new_callable=AsyncMock
+        ) as mock_start:
+            agent._session = None
+
+            async def run() -> list[Message]:
+                async def fake_start() -> None:
+                    agent._session = mock_session
+
+                mock_start.side_effect = fake_start
+                msgs: list[Message] = []
+                async for msg in agent.handle_message(_make_message()):
+                    msgs.append(msg)
+                return msgs
+
+            msgs = asyncio.run(run())
+            mock_start.assert_awaited_once()
+            assert len(msgs) == 1
+            assert msgs[0].content == "Codex response"
+
+    def test_subsequent_message_reuses_thread(self, agent: CodexAgent) -> None:
+        mock_session = AsyncMock()
+        mock_session.call_tool = AsyncMock(return_value=_mock_call_tool_result())
+
+        agent._session = mock_session
+        agent._thread_id = "existing-thread"
+
+        async def run() -> list[Message]:
+            msgs: list[Message] = []
+            async for msg in agent.handle_message(_make_message("follow up")):
+                msgs.append(msg)
+            return msgs
+
+        msgs = asyncio.run(run())
+        mock_session.call_tool.assert_awaited_once_with(
+            "codex-reply",
+            {"prompt": "follow up", "threadId": "existing-thread"},
+        )
+        assert msgs[0].content == "Codex response"
+
+    def test_state_transitions(self, agent: CodexAgent) -> None:
+        mock_session = AsyncMock()
+        mock_session.call_tool = AsyncMock(return_value=_mock_call_tool_result())
+        agent._session = mock_session
+        agent._thread_id = "thread-1"
+
+        observed_states: list[AgentState] = []
+        original_codex_reply = agent._codex_reply
+
+        async def spy_reply(prompt: str) -> Message:
+            observed_states.append(agent.state)
+            return await original_codex_reply(prompt)
+
+        agent._codex_reply = spy_reply  # type: ignore[assignment]
+
+        async def run() -> None:
+            async for _ in agent.handle_message(_make_message()):
+                pass
+
+        asyncio.run(run())
+        assert AgentState.processing in observed_states
+        assert agent.state == AgentState.idle
+
+    def test_yields_message_with_correct_fields(self, agent: CodexAgent) -> None:
+        mock_session = AsyncMock()
+        mock_session.call_tool = AsyncMock(
+            return_value=_mock_call_tool_result(text="detailed output")
+        )
+        agent._session = mock_session
+        agent._thread_id = None
+
+        async def run() -> Message:
+            async for msg in agent.handle_message(_make_message()):
+                return msg
+            raise AssertionError("no message yielded")
+
+        msg = asyncio.run(run())
+        assert msg.sender == "test-codex"
+        assert msg.content == "detailed output"
+        assert msg.message_type == MessageType.chat
+
+    def test_tool_error_raises_provider_error(self, agent: CodexAgent) -> None:
+        mock_session = AsyncMock()
+        mock_session.call_tool = AsyncMock(
+            return_value=_mock_call_tool_result(
+                text="something went wrong", is_error=True
+            )
+        )
+        agent._session = mock_session
+        agent._thread_id = None
+
+        async def run() -> None:
+            async for _ in agent.handle_message(_make_message()):
+                pass
+
+        with pytest.raises(ProviderError, match="Codex tool error"):
+            asyncio.run(run())
+
+
+class TestShutdown:
+    def test_sets_terminated(self, agent: CodexAgent) -> None:
+        asyncio.run(agent.shutdown())
+        assert agent.state == AgentState.terminated
+
+    def test_cleans_up_exit_stack(self, agent: CodexAgent) -> None:
+        mock_stack = AsyncMock()
+        agent._exit_stack = mock_stack
+        agent._session = MagicMock()
+        agent._thread_id = "thread-1"
+
+        asyncio.run(agent.shutdown())
+
+        mock_stack.aclose.assert_awaited_once()
+        assert agent._session is None
+        assert agent._thread_id is None
+        assert agent._exit_stack is None
+
+
+class TestResolveCodexCommand:
+    def test_not_found_raises(self, agent: CodexAgent) -> None:
+        with patch("shutil.which", return_value=None):
+            with pytest.raises(ProviderError, match="Codex CLI not found"):
+                agent._resolve_codex_command()
+
+    def test_found_returns_path(self, agent: CodexAgent) -> None:
+        with patch("shutil.which", return_value="/usr/local/bin/codex"):
+            assert agent._resolve_codex_command() == "/usr/local/bin/codex"
diff --git a/tests/providers/codex/test_auth.py b/tests/providers/codex/test_auth.py
new file mode 100644
index 0000000..a612655
--- /dev/null
+++ b/tests/providers/codex/test_auth.py
@@ -0,0 +1,129 @@
+"""Tests for OAuthFileStrategy credential resolution."""
+
+from __future__ import annotations
+
+import asyncio
+import json
+
+import pytest
+
+from squadron.providers.codex.auth import OAuthFileStrategy
+from squadron.providers.errors import ProviderAuthError
+
+
+@pytest.fixture()
+def _no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
+    """Ensure OPENAI_API_KEY is not set."""
+    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
+
+
+class TestGetCredentials:
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_auth_file_returns_path(self, tmp_path: pytest.TempPathFactory) -> None:
+        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
+        auth_file.write_text(json.dumps({"token": "tok-abc"}))
+        strategy = OAuthFileStrategy(auth_file=auth_file)
+        result = asyncio.run(strategy.get_credentials())
+        assert result == {"auth_file": str(auth_file)}
+
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_api_key_fallback(
+        self,
+        monkeypatch: pytest.MonkeyPatch,
+        tmp_path: pytest.TempPathFactory,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
+        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
+        strategy = OAuthFileStrategy(auth_file=missing)
+        result = asyncio.run(strategy.get_credentials())
+        assert result == {"api_key": "sk-test-key"}
+
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_no_credentials_raises(self, tmp_path: pytest.TempPathFactory) -> None:
+        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
+        strategy = OAuthFileStrategy(auth_file=missing)
+        with pytest.raises(ProviderAuthError, match="No credentials found"):
+            asyncio.run(strategy.get_credentials())
+
+    def test_auth_file_preferred_over_api_key(
+        self,
+        monkeypatch: pytest.MonkeyPatch,
+        tmp_path: pytest.TempPathFactory,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-use")
+        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
+        auth_file.write_text(json.dumps({"token": "tok-abc"}))
+        strategy = OAuthFileStrategy(auth_file=auth_file)
+        result = asyncio.run(strategy.get_credentials())
+        assert result == {"auth_file": str(auth_file)}
+
+
+class TestIsValid:
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_valid_with_auth_file(self, tmp_path: pytest.TempPathFactory) -> None:
+        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
+        auth_file.write_text("{}")
+        assert OAuthFileStrategy(auth_file=auth_file).is_valid() is True
+
+    def test_valid_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        assert OAuthFileStrategy().is_valid() is True
+
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_invalid_no_sources(self, tmp_path: pytest.TempPathFactory) -> None:
+        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
+        assert OAuthFileStrategy(auth_file=missing).is_valid() is False
+
+
+class TestFromConfig:
+    def test_returns_working_strategy(self) -> None:
+        from squadron.core.models import AgentConfig
+
+        config = AgentConfig(name="test", agent_type="codex", provider="codex")
+        strategy = OAuthFileStrategy.from_config(config)
+        assert isinstance(strategy, OAuthFileStrategy)
+
+
+class TestActiveSource:
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_auth_file_source(self, tmp_path: pytest.TempPathFactory) -> None:
+        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
+        auth_file.write_text("{}")
+        assert OAuthFileStrategy(auth_file=auth_file).active_source == "~/.codex/auth.json"
+
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_api_key_source(
+        self,
+        monkeypatch: pytest.MonkeyPatch,
+        tmp_path: pytest.TempPathFactory,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
+        assert OAuthFileStrategy(auth_file=missing).active_source == "OPENAI_API_KEY"
+
+    @pytest.mark.usefixtures("_no_api_key")
+    def test_no_source(self, tmp_path: pytest.TempPathFactory) -> None:
+        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
+        assert OAuthFileStrategy(auth_file=missing).active_source is None
+
+    def test_auth_file_preferred_source(
+        self,
+        monkeypatch: pytest.MonkeyPatch,
+        tmp_path: pytest.TempPathFactory,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
+        auth_file.write_text("{}")
+        assert OAuthFileStrategy(auth_file=auth_file).active_source == "~/.codex/auth.json"
+
+
+class TestSetupHint:
+    def test_returns_actionable_message(self) -> None:
+        strategy = OAuthFileStrategy()
+        assert "codex" in strategy.setup_hint.lower()
+        assert "OPENAI_API_KEY" in strategy.setup_hint
+
+
+class TestRefreshIfNeeded:
+    def test_is_noop(self) -> None:
+        asyncio.run(OAuthFileStrategy().refresh_if_needed())
diff --git a/tests/providers/codex/test_provider.py b/tests/providers/codex/test_provider.py
new file mode 100644
index 0000000..6ac0c9f
--- /dev/null
+++ b/tests/providers/codex/test_provider.py
@@ -0,0 +1,92 @@
+"""Tests for CodexProvider."""
+
+from __future__ import annotations
+
+import asyncio
+from unittest.mock import patch
+
+import pytest
+
+from squadron.core.models import AgentConfig
+from squadron.providers.codex.agent import CodexAgent
+from squadron.providers.codex.provider import CodexProvider
+from squadron.providers.errors import ProviderAuthError
+
+
+@pytest.fixture()
+def provider() -> CodexProvider:
+    return CodexProvider()
+
+
+@pytest.fixture()
+def agent_config() -> AgentConfig:
+    return AgentConfig(
+        name="test-codex",
+        agent_type="codex",
+        provider="codex",
+        model="gpt-5.3-codex",
+    )
+
+
+class TestProviderType:
+    def test_returns_codex(self, provider: CodexProvider) -> None:
+        assert provider.provider_type == "codex"
+
+
+class TestCapabilities:
+    def test_can_read_files(self, provider: CodexProvider) -> None:
+        assert provider.capabilities.can_read_files is True
+
+    def test_no_system_prompt(self, provider: CodexProvider) -> None:
+        assert provider.capabilities.supports_system_prompt is False
+
+    def test_no_streaming(self, provider: CodexProvider) -> None:
+        assert provider.capabilities.supports_streaming is False
+
+
+class TestCreateAgent:
+    def test_returns_codex_agent(
+        self,
+        provider: CodexProvider,
+        agent_config: AgentConfig,
+        monkeypatch: pytest.MonkeyPatch,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        agent = asyncio.run(provider.create_agent(agent_config))
+        assert isinstance(agent, CodexAgent)
+        assert agent.name == "test-codex"
+
+    def test_raises_when_no_credentials(
+        self,
+        provider: CodexProvider,
+        agent_config: AgentConfig,
+        monkeypatch: pytest.MonkeyPatch,
+        tmp_path: pytest.TempPathFactory,
+    ) -> None:
+        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
+        with patch(
+            "squadron.providers.codex.auth._CODEX_AUTH_FILE",
+            tmp_path / "nonexistent" / "auth.json",  # type: ignore[operator]
+        ):
+            with pytest.raises(ProviderAuthError, match="No Codex credentials"):
+                asyncio.run(provider.create_agent(agent_config))
+
+
+class TestValidateCredentials:
+    def test_true_when_codex_on_path_and_creds(
+        self,
+        provider: CodexProvider,
+        monkeypatch: pytest.MonkeyPatch,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        with patch("shutil.which", return_value="/usr/local/bin/codex"):
+            assert asyncio.run(provider.validate_credentials()) is True
+
+    def test_false_when_codex_not_on_path(
+        self,
+        provider: CodexProvider,
+        monkeypatch: pytest.MonkeyPatch,
+    ) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        with patch("shutil.which", return_value=None):
+            assert asyncio.run(provider.validate_credentials()) is False
diff --git a/tests/providers/codex/test_registration.py b/tests/providers/codex/test_registration.py
new file mode 100644
index 0000000..8ccded1
--- /dev/null
+++ b/tests/providers/codex/test_registration.py
@@ -0,0 +1,45 @@
+"""Integration tests for Codex provider auto-registration."""
+
+from __future__ import annotations
+
+from collections.abc import Generator
+
+import pytest
+
+from squadron.providers import registry as reg_module
+from squadron.providers.registry import get_provider, list_providers
+
+
+@pytest.fixture(autouse=True)
+def _clean_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
+    """Save and restore registry state so tests are isolated."""
+    original = dict(reg_module._REGISTRY)  # pyright: ignore[reportPrivateUsage]
+    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
+    yield
+    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
+    reg_module._REGISTRY.update(original)  # pyright: ignore[reportPrivateUsage]
+
+
+def _import_codex_package() -> None:
+    """Force the Codex package import and its auto-registration side effect."""
+    import importlib
+
+    import squadron.providers.codex  # noqa: F401
+
+    importlib.reload(squadron.providers.codex)
+
+
+class TestAutoRegistration:
+    def test_codex_in_list_after_import(self) -> None:
+        _import_codex_package()
+        assert "codex" in list_providers()
+
+    def test_get_provider_returns_codex_provider(self) -> None:
+        _import_codex_package()
+        from squadron.providers.codex.provider import CodexProvider
+
+        assert isinstance(get_provider("codex"), CodexProvider)
+
+    def test_provider_type_is_codex(self) -> None:
+        _import_codex_package()
+        assert get_provider("codex").provider_type == "codex"
diff --git a/tests/providers/sdk/test_agent.py b/tests/providers/sdk/test_agent.py
index 1e4e3df..872dc2c 100644
--- a/tests/providers/sdk/test_agent.py
+++ b/tests/providers/sdk/test_agent.py
@@ -1,4 +1,4 @@
-"""Tests for SDKAgent — query mode and client mode."""
+"""Tests for ClaudeSDKAgent — query mode and client mode."""
 
 from __future__ import annotations
 
@@ -23,7 +23,7 @@ from squadron.providers.errors import (
     ProviderAuthError,
     ProviderError,
 )
-from squadron.providers.sdk.agent import SDKAgent
+from squadron.providers.sdk.agent import ClaudeSDKAgent
 
 # Patch target for the SDK query function.
 _QUERY = "squadron.providers.sdk.agent.sdk_query"
@@ -40,13 +40,13 @@ def options() -> ClaudeAgentOptions:
 
 
 @pytest.fixture
-def query_agent(options: ClaudeAgentOptions) -> SDKAgent:
-    return SDKAgent(name="query-bot", options=options, mode="query")
+def query_agent(options: ClaudeAgentOptions) -> ClaudeSDKAgent:
+    return ClaudeSDKAgent(name="query-bot", options=options, mode="query")
 
 
 @pytest.fixture
-def client_agent(options: ClaudeAgentOptions) -> SDKAgent:
-    return SDKAgent(name="client-bot", options=options, mode="client")
+def client_agent(options: ClaudeAgentOptions) -> ClaudeSDKAgent:
+    return ClaudeSDKAgent(name="client-bot", options=options, mode="client")
 
 
 @pytest.fixture
@@ -75,13 +75,13 @@ async def _collect(ait: AsyncIterator[Message]) -> list[Message]:
 
 
 class TestProperties:
-    def test_name(self, query_agent: SDKAgent) -> None:
+    def test_name(self, query_agent: ClaudeSDKAgent) -> None:
         assert query_agent.name == "query-bot"
 
-    def test_agent_type(self, query_agent: SDKAgent) -> None:
+    def test_agent_type(self, query_agent: ClaudeSDKAgent) -> None:
         assert query_agent.agent_type == "sdk"
 
-    def test_initial_state(self, query_agent: SDKAgent) -> None:
+    def test_initial_state(self, query_agent: ClaudeSDKAgent) -> None:
         assert query_agent.state == AgentState.idle
 
 
@@ -93,7 +93,7 @@ class TestProperties:
 class TestQueryModeHappyPath:
     @pytest.mark.asyncio
     async def test_calls_query_with_prompt(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         async def mock_query(  # type: ignore[override]
             *, prompt: str, options: object = None
@@ -108,7 +108,7 @@ class TestQueryModeHappyPath:
     @pytest.mark.asyncio
     async def test_calls_query_with_options(
         self,
-        query_agent: SDKAgent,
+        query_agent: ClaudeSDKAgent,
         input_message: Message,
         options: ClaudeAgentOptions,
     ) -> None:
@@ -128,7 +128,7 @@ class TestQueryModeHappyPath:
 
     @pytest.mark.asyncio
     async def test_yields_translated_messages(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         async def mock_query(  # type: ignore[override]
             *, prompt: str, options: object = None
@@ -144,7 +144,7 @@ class TestQueryModeHappyPath:
 
     @pytest.mark.asyncio
     async def test_state_idle_after_success(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         async def mock_query(  # type: ignore[override]
             *, prompt: str, options: object = None
@@ -157,7 +157,7 @@ class TestQueryModeHappyPath:
 
     @pytest.mark.asyncio
     async def test_state_processing_during_execution(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         observed_state: AgentState | None = None
 
@@ -193,7 +193,7 @@ def _make_error_gen(exc: Exception):
 class TestQueryModeErrors:
     @pytest.mark.asyncio
     async def test_cli_not_found_raises_auth_error(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         gen = _make_error_gen(CLINotFoundError("not found"))
         with patch(_QUERY, side_effect=gen):
@@ -203,7 +203,7 @@ class TestQueryModeErrors:
 
     @pytest.mark.asyncio
     async def test_process_error_raises_api_error(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         gen = _make_error_gen(ProcessError("exit failure", exit_code=1))
         with patch(_QUERY, side_effect=gen):
@@ -214,7 +214,7 @@ class TestQueryModeErrors:
 
     @pytest.mark.asyncio
     async def test_cli_connection_error(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         gen = _make_error_gen(CLIConnectionError("connection failed"))
         with patch(_QUERY, side_effect=gen):
@@ -224,7 +224,7 @@ class TestQueryModeErrors:
 
     @pytest.mark.asyncio
     async def test_json_decode_error(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         gen = _make_error_gen(CLIJSONDecodeError("bad json", ValueError("oops")))
         with patch(_QUERY, side_effect=gen):
@@ -234,7 +234,7 @@ class TestQueryModeErrors:
 
     @pytest.mark.asyncio
     async def test_base_sdk_error(
-        self, query_agent: SDKAgent, input_message: Message
+        self, query_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         gen = _make_error_gen(ClaudeSDKError("unknown"))
         with patch(_QUERY, side_effect=gen):
@@ -250,12 +250,12 @@ class TestQueryModeErrors:
 
 class TestShutdown:
     @pytest.mark.asyncio
-    async def test_shutdown_sets_terminated(self, query_agent: SDKAgent) -> None:
+    async def test_shutdown_sets_terminated(self, query_agent: ClaudeSDKAgent) -> None:
         await query_agent.shutdown()
         assert query_agent.state == AgentState.terminated
 
     @pytest.mark.asyncio
-    async def test_shutdown_no_client_safe(self, query_agent: SDKAgent) -> None:
+    async def test_shutdown_no_client_safe(self, query_agent: ClaudeSDKAgent) -> None:
         await query_agent.shutdown()
 
 
@@ -267,7 +267,7 @@ class TestShutdown:
 class TestClientModeHappyPath:
     @pytest.mark.asyncio
     async def test_first_message_creates_and_connects(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
 
@@ -285,7 +285,7 @@ class TestClientModeHappyPath:
 
     @pytest.mark.asyncio
     async def test_second_message_reuses_client(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
 
@@ -314,7 +314,7 @@ class TestClientModeHappyPath:
 
     @pytest.mark.asyncio
     async def test_yields_translated_messages(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
 
@@ -330,7 +330,7 @@ class TestClientModeHappyPath:
 
     @pytest.mark.asyncio
     async def test_state_idle_after_success(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
 
@@ -352,7 +352,7 @@ class TestClientModeHappyPath:
 class TestClientModeErrors:
     @pytest.mark.asyncio
     async def test_connect_error_maps_correctly(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
         mock_client.connect.side_effect = CLINotFoundError()
@@ -364,7 +364,7 @@ class TestClientModeErrors:
 
     @pytest.mark.asyncio
     async def test_receive_error_maps_correctly(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
 
@@ -388,7 +388,7 @@ class TestClientModeErrors:
 class TestClientShutdown:
     @pytest.mark.asyncio
     async def test_shutdown_disconnects_client(
-        self, client_agent: SDKAgent, input_message: Message
+        self, client_agent: ClaudeSDKAgent, input_message: Message
     ) -> None:
         mock_client = AsyncMock()
 
@@ -406,7 +406,7 @@ class TestClientShutdown:
 
     @pytest.mark.asyncio
     async def test_shutdown_without_client_is_safe(
-        self, client_agent: SDKAgent
+        self, client_agent: ClaudeSDKAgent
     ) -> None:
         await client_agent.shutdown()
         assert client_agent.state == AgentState.terminated
diff --git a/tests/providers/sdk/test_provider.py b/tests/providers/sdk/test_provider.py
index 7392e38..5f619af 100644
--- a/tests/providers/sdk/test_provider.py
+++ b/tests/providers/sdk/test_provider.py
@@ -1,4 +1,4 @@
-"""Tests for SDKAgentProvider — options mapping, defaults, and credentials."""
+"""Tests for ClaudeSDKProvider — options mapping, defaults, and credentials."""
 
 from __future__ import annotations
 
@@ -7,15 +7,15 @@ from unittest.mock import MagicMock, patch
 import pytest
 
 from squadron.core.models import AgentConfig
-from squadron.providers.sdk.provider import SDKAgentProvider
+from squadron.providers.sdk.provider import ClaudeSDKProvider
 
 # Patch target: the deferred import inside create_agent resolves from this module.
-_AGENT_PATCH = "squadron.providers.sdk.agent.SDKAgent"
+_AGENT_PATCH = "squadron.providers.sdk.agent.ClaudeSDKAgent"
 
 
 @pytest.fixture
-def provider() -> SDKAgentProvider:
-    return SDKAgentProvider()
+def provider() -> ClaudeSDKProvider:
+    return ClaudeSDKProvider()
 
 
 # ---------------------------------------------------------------------------
@@ -23,7 +23,7 @@ def provider() -> SDKAgentProvider:
 # ---------------------------------------------------------------------------
 
 
-def test_provider_type(provider: SDKAgentProvider) -> None:
+def test_provider_type(provider: ClaudeSDKProvider) -> None:
     assert provider.provider_type == "sdk"
 
 
@@ -34,7 +34,7 @@ def test_provider_type(provider: SDKAgentProvider) -> None:
 
 class TestCreateAgent:
     @pytest.mark.asyncio
-    async def test_minimal_config(self, provider: SDKAgentProvider) -> None:
+    async def test_minimal_config(self, provider: ClaudeSDKProvider) -> None:
         config = AgentConfig(name="basic", agent_type="sdk", provider="sdk")
         with patch(
             _AGENT_PATCH,
@@ -52,7 +52,7 @@ class TestCreateAgent:
             assert opts.permission_mode == "acceptEdits"
 
     @pytest.mark.asyncio
-    async def test_full_sdk_config(self, provider: SDKAgentProvider) -> None:
+    async def test_full_sdk_config(self, provider: ClaudeSDKProvider) -> None:
         config = AgentConfig(
             name="full",
             agent_type="sdk",
@@ -80,7 +80,7 @@ class TestCreateAgent:
             assert opts.permission_mode == "bypassPermissions"
 
     @pytest.mark.asyncio
-    async def test_default_permission_mode(self, provider: SDKAgentProvider) -> None:
+    async def test_default_permission_mode(self, provider: ClaudeSDKProvider) -> None:
         config = AgentConfig(name="noperm", agent_type="sdk", provider="sdk")
         with patch(
             _AGENT_PATCH,
@@ -93,7 +93,7 @@ class TestCreateAgent:
             assert opts.permission_mode == "acceptEdits"
 
     @pytest.mark.asyncio
-    async def test_mode_from_credentials(self, provider: SDKAgentProvider) -> None:
+    async def test_mode_from_credentials(self, provider: ClaudeSDKProvider) -> None:
         config = AgentConfig(
             name="client-mode",
             agent_type="sdk",
@@ -110,7 +110,7 @@ class TestCreateAgent:
             assert mock_cls.call_args.kwargs["mode"] == "client"
 
     @pytest.mark.asyncio
-    async def test_api_only_fields_ignored(self, provider: SDKAgentProvider) -> None:
+    async def test_api_only_fields_ignored(self, provider: ClaudeSDKProvider) -> None:
         config = AgentConfig(
             name="api-fields",
             agent_type="sdk",
@@ -138,14 +138,14 @@ class TestCreateAgent:
 class TestValidateCredentials:
     @pytest.mark.asyncio
     async def test_returns_true_when_importable(
-        self, provider: SDKAgentProvider
+        self, provider: ClaudeSDKProvider
     ) -> None:
         result = await provider.validate_credentials()
         assert result is True
 
     @pytest.mark.asyncio
     async def test_returns_false_when_import_fails(
-        self, provider: SDKAgentProvider
+        self, provider: ClaudeSDKProvider
     ) -> None:
         with patch.dict("sys.modules", {"claude_agent_sdk": None}):
             # When the module entry is None, Python raises ImportError
diff --git a/tests/providers/sdk/test_registration.py b/tests/providers/sdk/test_registration.py
index eddb7fe..3853710 100644
--- a/tests/providers/sdk/test_registration.py
+++ b/tests/providers/sdk/test_registration.py
@@ -26,9 +26,9 @@ def _import_sdk_package() -> None:
     from squadron.providers.registry import register_provider
 
     # Re-register since the fixture clears the registry before each test.
-    from squadron.providers.sdk.provider import SDKAgentProvider
+    from squadron.providers.sdk.provider import ClaudeSDKProvider
 
-    register_provider("sdk", SDKAgentProvider())
+    register_provider("sdk", ClaudeSDKProvider())
 
 
 class TestAutoRegistration:
@@ -39,9 +39,9 @@ class TestAutoRegistration:
     def test_get_provider_returns_sdk_provider(self) -> None:
         _import_sdk_package()
         provider = get_provider("sdk")
-        from squadron.providers.sdk.provider import SDKAgentProvider
+        from squadron.providers.sdk.provider import ClaudeSDKProvider
 
-        assert isinstance(provider, SDKAgentProvider)
+        assert isinstance(provider, ClaudeSDKProvider)
 
     def test_provider_type_is_sdk(self) -> None:
         _import_sdk_package()
@@ -51,11 +51,11 @@ class TestAutoRegistration:
     async def test_full_flow_create_agent(self) -> None:
         _import_sdk_package()
         from squadron.core.models import AgentConfig
-        from squadron.providers.sdk.agent import SDKAgent
+        from squadron.providers.sdk.agent import ClaudeSDKAgent
 
         provider = get_provider("sdk")
         config = AgentConfig(name="integration-test", agent_type="sdk", provider="sdk")
         agent = await provider.create_agent(config)
-        assert isinstance(agent, SDKAgent)
+        assert isinstance(agent, ClaudeSDKAgent)
         assert agent.name == "integration-test"
         assert agent.agent_type == "sdk"
diff --git a/tests/providers/test_auth_resolution.py b/tests/providers/test_auth_resolution.py
index 145c60b..26c476c 100644
--- a/tests/providers/test_auth_resolution.py
+++ b/tests/providers/test_auth_resolution.py
@@ -7,8 +7,13 @@ from types import SimpleNamespace
 import pytest
 
 from squadron.core.models import AgentConfig
-from squadron.providers.auth import ApiKeyStrategy, resolve_auth_strategy
+from squadron.providers.auth import (
+    ApiKeyStrategy,
+    resolve_auth_strategy,
+    resolve_auth_strategy_for_profile,
+)
 from squadron.providers.errors import ProviderAuthError
+from squadron.providers.profiles import get_profile
 
 
 def _make_config(**kwargs: object) -> AgentConfig:
@@ -59,3 +64,88 @@ def test_resolve_no_profile_uses_credentials(monkeypatch: pytest.MonkeyPatch) ->
 
     result = asyncio.run(strategy.get_credentials())
     assert result == {"api_key": "resolved-from-credentials"}
+
+
+# ---------------------------------------------------------------------------
+# from_config classmethod tests
+# ---------------------------------------------------------------------------
+
+
+class TestFromConfig:
+    def test_from_config_with_profile_env_var(self) -> None:
+        config = _make_config()
+        profile = SimpleNamespace(
+            auth_type="api_key", api_key_env="CUSTOM_KEY", base_url=None
+        )
+        strategy = ApiKeyStrategy.from_config(config, profile=profile)  # type: ignore[arg-type]
+        assert isinstance(strategy, ApiKeyStrategy)
+        assert strategy._env_var == "CUSTOM_KEY"
+
+    def test_from_config_with_explicit_key(self) -> None:
+        config = _make_config(api_key="sk-explicit")
+        strategy = ApiKeyStrategy.from_config(config, profile=None)
+        assert strategy._explicit_key == "sk-explicit"
+
+    def test_from_config_with_localhost(self) -> None:
+        config = _make_config(base_url="http://localhost:11434/v1")
+        strategy = ApiKeyStrategy.from_config(config, profile=None)
+        assert strategy._is_localhost() is True
+
+
+# ---------------------------------------------------------------------------
+# active_source and setup_hint tests
+# ---------------------------------------------------------------------------
+
+
+class TestActiveSource:
+    def test_returns_env_var_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
+        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
+        strategy = ApiKeyStrategy(env_var="OPENROUTER_API_KEY")
+        assert strategy.active_source == "OPENROUTER_API_KEY"
+
+    def test_returns_fallback_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        strategy = ApiKeyStrategy()
+        assert strategy.active_source == "OPENAI_API_KEY"
+
+    def test_returns_explicit(self) -> None:
+        strategy = ApiKeyStrategy(explicit_key="sk-explicit")
+        assert strategy.active_source == "explicit"
+
+    def test_returns_localhost(self) -> None:
+        strategy = ApiKeyStrategy(base_url="http://localhost:8080")
+        assert strategy.active_source == "localhost"
+
+    def test_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
+        strategy = ApiKeyStrategy()
+        assert strategy.active_source is None
+
+
+class TestSetupHint:
+    def test_returns_actionable_message(self) -> None:
+        strategy = ApiKeyStrategy(env_var="OPENROUTER_API_KEY")
+        assert "OPENROUTER_API_KEY" in strategy.setup_hint
+
+    def test_uses_fallback_when_no_env_var(self) -> None:
+        strategy = ApiKeyStrategy()
+        assert "OPENAI_API_KEY" in strategy.setup_hint
+
+
+# ---------------------------------------------------------------------------
+# resolve_auth_strategy_for_profile tests
+# ---------------------------------------------------------------------------
+
+
+class TestResolveForProfile:
+    def test_openai_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
+        profile = get_profile("openai")
+        strategy = resolve_auth_strategy_for_profile(profile)
+        assert strategy.is_valid() is True
+
+    def test_sdk_profile(self) -> None:
+        profile = get_profile("sdk")
+        strategy = resolve_auth_strategy_for_profile(profile)
+        assert strategy.is_valid() is True
diff --git a/tests/providers/test_capabilities.py b/tests/providers/test_capabilities.py
new file mode 100644
index 0000000..e3bf670
--- /dev/null
+++ b/tests/providers/test_capabilities.py
@@ -0,0 +1,47 @@
+"""Tests for ProviderCapabilities dataclass."""
+
+from __future__ import annotations
+
+import pytest
+
+from squadron.providers.base import ProviderCapabilities
+
+
+class TestDefaults:
+    def test_can_read_files_defaults_false(self) -> None:
+        assert ProviderCapabilities().can_read_files is False
+
+    def test_supports_system_prompt_defaults_true(self) -> None:
+        assert ProviderCapabilities().supports_system_prompt is True
+
+    def test_supports_streaming_defaults_false(self) -> None:
+        assert ProviderCapabilities().supports_streaming is False
+
+
+class TestFrozen:
+    def test_assignment_raises(self) -> None:
+        caps = ProviderCapabilities()
+        with pytest.raises(AttributeError):
+            caps.can_read_files = True  # type: ignore[misc]
+
+
+class TestProviderCapabilities:
+    def test_openai_provider_cannot_read_files(self) -> None:
+        from squadron.providers.openai.provider import OpenAICompatibleProvider
+
+        assert OpenAICompatibleProvider().capabilities.can_read_files is False
+
+    def test_sdk_provider_can_read_files(self) -> None:
+        from squadron.providers.sdk.provider import ClaudeSDKProvider
+
+        assert ClaudeSDKProvider().capabilities.can_read_files is True
+
+    def test_openai_supports_streaming(self) -> None:
+        from squadron.providers.openai.provider import OpenAICompatibleProvider
+
+        assert OpenAICompatibleProvider().capabilities.supports_streaming is True
+
+    def test_sdk_supports_streaming(self) -> None:
+        from squadron.providers.sdk.provider import ClaudeSDKProvider
+
+        assert ClaudeSDKProvider().capabilities.supports_streaming is True
diff --git a/tests/test_providers.py b/tests/test_providers.py
index f3579c5..34a44c6 100644
--- a/tests/test_providers.py
+++ b/tests/test_providers.py
@@ -8,7 +8,7 @@ import pytest
 
 from squadron.core.models import AgentConfig, AgentState, Message
 from squadron.providers import registry as reg_module
-from squadron.providers.base import Agent, AgentProvider
+from squadron.providers.base import Agent, AgentProvider, ProviderCapabilities
 from squadron.providers.errors import (
     ProviderAPIError,
     ProviderAuthError,
@@ -33,6 +33,10 @@ class _MockAgentProvider:
     def provider_type(self) -> str:
         return "mock"
 
+    @property
+    def capabilities(self) -> ProviderCapabilities:
+        return ProviderCapabilities()
+
     async def create_agent(self, config: AgentConfig) -> _MockAgent:
         return _MockAgent(config.name, config.agent_type)
 

```

### Rules Injected

None

### Raw Response

I'll review the code changes from the git diff. Let me analyze the key files for quality and correctness.

## Summary

**PASS**

The implementation is well-structured and follows good practices. The refactoring achieves the goal of decoupled provider architecture with registry-driven dispatch, and the new Codex provider is properly implemented. Minor notes are documented below but do not constitute concerns.

---

## Findings

### [PASS] ProviderCapabilities dataclass is correctly implemented
`src/squadron/providers/base.py`: The frozen dataclass with appropriate defaults (`can_read_files=False`, `supports_system_prompt=True`, `supports_streaming=False`) follows the dataclass pattern correctly. All three providers (OpenAI, SDK, Codex) expose `capabilities` as required by the `AgentProvider` Protocol.

### [PASS] Registry-driven auth dispatch eliminates string conditionals
`src/squadron/providers/auth.py`: The refactored `resolve_auth_strategy()` now uses `AUTH_STRATEGIES[auth_type].from_config(config, profile)` with no if/elif chains on auth types. The `_register_oauth_strategy()` lazy import pattern correctly avoids circular dependencies. The new `resolve_auth_strategy_for_profile()` convenience function is well-designed for CLI auth status checks.

### [PASS] Codex provider MCP transport implementation is solid
`src/squadron/providers/codex/agent.py`: Lazy MCP client initialization, proper thread ID management for session continuity, and `AsyncExitStack` for clean resource cleanup. The `_extract_thread_id()` method handles both `structuredContent` and `result._meta` fallbacks. Error handling wraps MCP errors in `ProviderError`.

### [PASS] OAuthFileStrategy credential resolution is correct
`src/squadron/providers/codex/auth.py`: Auth file is correctly preferred over `OPENAI_API_KEY` fallback per specification. The `is_valid()` check and `get_credentials()` implementation are consistent.

### [PASS] SDK class rename is complete and consistent
`src/squadron/providers/sdk/`: `SDKAgent` → `ClaudeSDKAgent` and `SDKAgentProvider` → `ClaudeSDKProvider` are applied consistently across agent, provider, `__init__.py`, and all test files. Registration key `"sdk"` remains unchanged for backward compatibility.

### [PASS] Test coverage is comprehensive
Tests cover: state transitions, lazy initialization, session reuse, error propagation, capabilities defaults, frozen dataclass behavior, `active_source`/`setup_hint` properties, and registration mechanics. Test isolation via `_clean_registry` fixture is properly implemented.

### [PASS] Codex provider capabilities are correctly declared
`src/squadron/providers/codex/provider.py`: `can_read_files=True`, `supports_system_prompt=False`, `supports_streaming=False` accurately reflects Codex MCP capabilities per specification.
