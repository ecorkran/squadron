---
docType: review
layer: project
reviewType: slice
slice: review-transport-unification-provider-decoupling
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/128-slice.review-transport-unification-provider-decoupling.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260326
dateUpdated: 20260326
---

# Review: slice — slice 128

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Review transport unification aligns with Agent Protocol contract

The slice correctly replaces bespoke transport implementations in `review_client.py` with calls to `agent.handle_message()`, the same contract used by `sq spawn`/`sq task`. This enforces the architecture's key invariant: "the core engine never depends on provider internals" and the core engine (and review module) never depends on provider-specific types. The new flow (`get_provider` → `create_agent` → `handle_message`) is consistent with the documented Agent Lifecycle data flow.

### [PASS] Provider capabilities use capability-based dispatch, not identity-based dispatch

The slice introduces `ProviderCapabilities` to answer "can this provider read files?" via `provider.capabilities.can_read_files` rather than `if provider_type == "sdk"`. This is a direct application of the architecture's principle that "the core engine never depends on provider internals." Callers adapt based on declared capabilities, not hardcoded identity checks. This generalizes correctly when new providers (Anthropic API, future agents) are added.

### [PASS] Auth strategy cleanup removes string-based dispatch from auth layer

Replacing `if auth_type == "api_key": return ApiKeyStrategy(...)` with `AUTH_STRATEGIES.get(auth_type)` followed by `strategy_cls.from_config(config, profile)` eliminates the if/elif chain in `auth.py`. The slice's auth type rename (`"codex"` → `"oauth"`, `CodexAuthStrategy` → `OAuthFileStrategy`) is appropriate — auth types should describe mechanisms, not products. This is consistent with the architecture's multi-provider auth pattern where each provider manages its own authentication.

### [PASS] `runner.py` deletion consolidates duplicate SDK execution paths

The architecture defines SDK agent behavior as: "squadron sends task message → SDK agent translates to query() call → Claude Agent SDK executes autonomously → SDK streams response messages → SDK agent converts to squadron Messages." The slice moves the review-specific SDK logic (retry logic, config handling) into `ClaudeSDKAgent.handle_message()`, eliminating duplicate SDK execution paths. The slice correctly identifies that the review-specific config (`allowed_tools`, `hooks`, `setting_sources`) is already on `AgentConfig` and will be consumed by `ClaudeSDKProvider.create_agent()`.

### [PASS] Naming changes increase clarity without breaking user-facing contracts

Renaming `SDKAgent` → `ClaudeSDKAgent` and `SDKAgentProvider` → `ClaudeSDKProvider` clarifies that these wrap `claude-agent-sdk` specifically. The slice explicitly preserves the registry keys `"sdk"` and `"codex"` since those are user-facing profile identifiers. The distinction between internal implementation names (changed) and user-facing profile names (unchanged) is correct.

### [PASS] Scope is contained within defined boundaries

The slice touches: `providers/base.py`, `providers/auth.py`, `providers/profiles.py`, SDK provider classes, review module, and CLI auth commands. No changes to core engine, message bus, topology, or supervisor. The project structure in the architecture document is respected.

### [PASS] Verification walkthrough demonstrates integration consistency

The verification scenarios show:
- Default SDK review routes through `ClaudeSDKAgent` (same behavior)
- API review via alias routes through `OpenAICompatibleAgent` (same behavior)
- **New capability**: Codex subscription review routes through `CodexAgent` (architecture allows any provider to be used)
- Auth status uses `AuthStrategy.is_valid()` (consistent with auth strategy Protocol)

The verification scenarios are achievable without architectural changes because the slice uses existing Protocol contracts and the provider registry.
