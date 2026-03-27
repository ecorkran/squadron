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

### [PASS] ProviderCapabilities dataclass follows frozen dataclass pattern correctly

`src/squadron/providers/base.py` (lines 6-23): The `@dataclass(frozen=True)` with appropriate defaults (`can_read_files=False`, `supports_system_prompt=True`, `supports_streaming=False`) is correctly implemented. All three providers (OpenAI, SDK, Codex) expose `capabilities` as required by the `AgentProvider` Protocol.

### [PASS] Registry-driven auth dispatch eliminates string conditionals

`src/squadron/providers/auth.py` (lines 155-224): The refactored `resolve_auth_strategy()` now uses `AUTH_STRATEGIES[auth_type].from_config(config, profile)` with no if/elif chains on auth types. The `_register_oauth_strategy()` lazy import pattern correctly avoids circular dependencies. The new `resolve_auth_strategy_for_profile()` convenience function is well-designed for CLI auth status checks.

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
