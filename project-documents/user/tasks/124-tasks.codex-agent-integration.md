---
docType: tasks
slice: codex-agent-integration
project: squadron
lld: user/slices/124-slice.codex-agent-integration.md
dependencies: [auth-strategy-credential-management, agent-registry-lifecycle, cli-foundation]
projectState: "M1 shipped (v0.2.7). Provider layer has SDK and OpenAI-compatible providers. Auth has ApiKeyStrategy only. Codex models already work via Chat Completions through openai profile."
dateCreated: 20260326
dateUpdated: 20260326
status: not_started
---

## Context Summary
- Working on slice 124: Codex Agent Integration
- Adding a new agentic provider (`CodexProvider`/`CodexAgent`) for OpenAI Codex
- Transport: Python SDK (`codex-app-server`) primary, MCP fallback
- Codex models already work for reviews via existing `openai` profile — no review system changes
- This slice adds agentic capability: spawn, task, multi-turn with sandbox file access
- Existing provider pattern to follow: `src/squadron/providers/openai/`
- Next planned slice: 123 (Review Findings Pipeline) or 125 (Conversation Persistence)

---

## Tasks

### T1: Transport evaluation and optional dependency setup

- [ ] **Evaluate Codex Python SDK stability and select transport**
  - [ ] Attempt `pip install codex-app-server` and verify import (`from codex_app_server import Codex`)
  - [ ] If Python SDK works: add `codex-app-server` to `[project.optional-dependencies]` in `pyproject.toml` under a `codex` extra (e.g. `codex = ["codex-app-server>=0.2.0"]`)
  - [ ] If Python SDK fails or is too unstable: document the issue, proceed with MCP fallback path. No optional dependency needed (squadron already depends on `mcp`)
  - [ ] Record the transport decision in the slice design status section
  - [ ] Success: transport decision made and documented; dependency added if using Python SDK path

**Commit**: `chore: add codex-app-server optional dependency`

---

### T2: CodexAuthStrategy

- [ ] **Create `src/squadron/providers/codex/auth.py` with `CodexAuthStrategy`**
  - [ ] Implement `AuthStrategy` Protocol: `get_credentials()`, `refresh_if_needed()`, `is_valid()`
  - [ ] Resolution order in `get_credentials()`:
    1. `OPENAI_API_KEY` env var → return `{"api_key": value}`
    2. `~/.codex/auth.json` exists → return `{"auth_file": path}` (squadron doesn't read the token, just confirms existence)
    3. Raise `ProviderAuthError` with message: `"No Codex credentials found. Run 'codex' CLI to authenticate, or set OPENAI_API_KEY."`
  - [ ] `refresh_if_needed()`: no-op (Codex handles refresh internally)
  - [ ] `is_valid()`: return True if either credential source resolves
  - [ ] Register `"codex"` in `AUTH_STRATEGIES` dict in `src/squadron/providers/auth.py`
  - [ ] Success: `CodexAuthStrategy` satisfies `AuthStrategy` Protocol; registered in auth strategies dict

### T3: CodexAuthStrategy tests

- [ ] **Create `tests/providers/codex/test_auth.py`**
  - [ ] Test: `OPENAI_API_KEY` set → `is_valid()` returns True, `get_credentials()` returns key
  - [ ] Test: `OPENAI_API_KEY` not set, `~/.codex/auth.json` exists → `is_valid()` returns True
  - [ ] Test: neither source available → `is_valid()` returns False, `get_credentials()` raises `ProviderAuthError`
  - [ ] Test: `refresh_if_needed()` is a no-op (does not raise)
  - [ ] Use `monkeypatch` for env vars and `tmp_path` for auth.json fixture
  - [ ] Success: all tests pass; `pytest tests/providers/codex/test_auth.py -v` green

**Commit**: `feat: add CodexAuthStrategy for Codex credential resolution`

---

### T4: CodexAgent implementation

- [ ] **Create `src/squadron/providers/codex/agent.py` with `CodexAgent`**
  - [ ] Implement `Agent` Protocol: `name`, `agent_type`, `state`, `handle_message()`, `shutdown()`
  - [ ] `agent_type` property returns `"codex"`
  - [ ] State management: `idle` → `processing` (during handle_message) → `idle` (after response), `terminated` (after shutdown)
  - [ ] Lazy client initialization on first `handle_message()` call:
    - **Python SDK path**: instantiate `Codex()` context manager, call `thread_start(model=...)`
    - **MCP path**: spawn `codex mcp-server` subprocess via `mcp` stdio client, call `codex()` tool
  - [ ] First message: initialize client + send prompt via `thread.run()` (SDK) or `codex()` tool (MCP)
  - [ ] Subsequent messages: continue thread via `thread.run()` (SDK) or `codex-reply()` with stored thread ID (MCP)
  - [ ] Convert Codex response to squadron `Message` objects (role=`"assistant"`, content=response text)
  - [ ] `shutdown()`: clean up client (SDK: exit context manager; MCP: terminate subprocess), set state to `terminated`
  - [ ] Handle `ImportError` for `codex_app_server` gracefully — raise `ProviderError` with install instructions
  - [ ] Configure sandbox policy from agent config: default `"read-only"`, configurable via `AgentConfig.credentials["sandbox"]`
  - [ ] Configure `cwd` from `AgentConfig.cwd` (defaults to current directory)
  - [ ] Success: `CodexAgent` satisfies `Agent` Protocol; handles message lifecycle correctly

### T5: CodexAgent tests

- [ ] **Create `tests/providers/codex/test_agent.py`**
  - [ ] Test: agent starts in `idle` state, transitions to `processing` during handle_message, returns to `idle`
  - [ ] Test: first message initializes client lazily (mock the SDK/MCP client)
  - [ ] Test: subsequent messages reuse existing thread
  - [ ] Test: `shutdown()` sets state to `terminated` and cleans up client
  - [ ] Test: handle_message yields `Message` objects with correct role and content
  - [ ] Test: `ImportError` for `codex_app_server` produces clear `ProviderError`
  - [ ] Mock `codex_app_server.Codex` (or MCP client) — do not spawn real Codex processes in tests
  - [ ] Success: all tests pass; `pytest tests/providers/codex/test_agent.py -v` green

**Commit**: `feat: add CodexAgent with lazy client initialization`

---

### T6: CodexProvider implementation

- [ ] **Create `src/squadron/providers/codex/provider.py` with `CodexProvider`**
  - [ ] Implement `AgentProvider` Protocol: `provider_type`, `create_agent()`, `validate_credentials()`
  - [ ] `provider_type` returns `"codex"`
  - [ ] `create_agent(config: AgentConfig)` → instantiate `CodexAuthStrategy`, validate credentials, return `CodexAgent`
  - [ ] `validate_credentials()` → check if `codex_app_server` is importable (SDK path) or `codex` is on PATH (MCP path), and credentials exist
  - [ ] Follow the pattern in `src/squadron/providers/openai/provider.py`
  - [ ] Success: `CodexProvider` satisfies `AgentProvider` Protocol

### T7: CodexProvider tests

- [ ] **Create `tests/providers/codex/test_provider.py`**
  - [ ] Test: `provider_type` returns `"codex"`
  - [ ] Test: `create_agent()` returns a `CodexAgent` with correct name and config
  - [ ] Test: `create_agent()` raises `ProviderAuthError` when no credentials available
  - [ ] Test: `validate_credentials()` returns True when SDK importable and credentials exist
  - [ ] Test: `validate_credentials()` returns False when SDK not importable
  - [ ] Success: all tests pass; `pytest tests/providers/codex/test_provider.py -v` green

**Commit**: `feat: add CodexProvider implementing AgentProvider Protocol`

---

### T8: Provider registration and profile

- [ ] **Create `src/squadron/providers/codex/__init__.py`**
  - [ ] Import `CodexProvider` and `CodexAgent`
  - [ ] Auto-register: `register_provider("codex", CodexProvider())` — same pattern as OpenAI provider
  - [ ] Add `__all__` export list
- [ ] **Add `codex` built-in profile to `BUILT_IN_PROFILES` in `src/squadron/providers/profiles.py`**
  - [ ] Profile: `name="codex"`, `provider="codex"`, `auth_type="codex"`, `description="OpenAI Codex agent (Python SDK or MCP) — agentic tasks with sandbox"`
  - [ ] No `api_key_env` — auth handled by `CodexAuthStrategy`
- [ ] **Update `sq auth status` in `src/squadron/cli/commands/auth.py`**
  - [ ] Current implementation only checks `api_key_env` env vars — extend to handle `auth_type="codex"` by delegating to `CodexAuthStrategy.is_valid()` for the status check
  - [ ] Show: `codex: ✓ authenticated` or `codex: ✗ not authenticated (run 'codex' to sign in)`
- [ ] Success: `get_provider("codex")` returns `CodexProvider`; `sq auth status` shows Codex row

### T9: Registration and profile tests

- [ ] **Test provider registration**
  - [ ] Test: importing `squadron.providers.codex` registers `"codex"` in the provider registry
  - [ ] Test: `get_provider("codex")` returns a `CodexProvider` instance
- [ ] **Test profile lookup**
  - [ ] Test: `get_profile("codex")` returns the codex profile with correct auth_type
- [ ] **Test auth status output**
  - [ ] Test: `sq auth status` includes a row for the `codex` profile (mock credentials)
  - [ ] Success: all tests pass

**Commit**: `feat: register Codex provider and add codex profile`

---

### T10: Model alias updates

- [ ] **Add `codex-agent` alias to `BUILT_IN_ALIASES` in `src/squadron/models/aliases.py`**
  - [ ] `"codex-agent"`: `profile: "codex"`, `model: "gpt-5.3-codex"`, `notes: "Agentic: sandbox file access, command execution"`
  - [ ] Existing `"codex"` alias stays unchanged (`profile: "openai"`) — API path for reviews
  - [ ] Add `"codex-spark"`: `profile: "openai"`, `model: "gpt-5.3-codex-spark"`, `notes: "Near-instant, Pro only"`
- [ ] **Test: alias resolution**
  - [ ] Test: `codex` alias resolves to `profile="openai"` (unchanged)
  - [ ] Test: `codex-agent` alias resolves to `profile="codex"`
  - [ ] Test: `codex-spark` alias resolves correctly
  - [ ] Success: all alias tests pass; existing alias behavior unchanged

**Commit**: `feat: add codex-agent and codex-spark model aliases`

---

### T11: Full validation pass

- [ ] **Run full test suite**
  - [ ] `pytest tests/ -v` — all tests pass (existing + new)
  - [ ] `ruff check src/ tests/` — no lint errors
  - [ ] `ruff format --check src/ tests/` — no formatting issues
  - [ ] `pyright src/` — no type errors (or only pre-existing ones)
- [ ] **Verify no review system regression**
  - [ ] Confirm `codex` model alias still has `profile: "openai"` (not `"codex"`)
  - [ ] Confirm review system has no `if profile == "codex"` branching
- [ ] **Verify provider registration doesn't break existing providers**
  - [ ] Confirm `get_provider("openai")` and `get_provider("sdk")` still work
- [ ] Success: all checks green; no regressions

---

### T12: Documentation and slice completion

- [ ] **Update CHANGELOG.md**
  - [ ] Add entry for Codex agent integration under appropriate version section
- [ ] **Update DEVLOG.md**
  - [ ] Add Phase 6 implementation entry for slice 124
- [ ] **Update slice design status**
  - [ ] Set status to `complete` in `124-slice.codex-agent-integration.md` frontmatter
  - [ ] Update `dateUpdated` to today's date
- [ ] **Update slice plan**
  - [ ] Check off slice 124 in `100-slices.orchestration-v2.md`
  - [ ] Update implementation order section
- [ ] **Update Verification Walkthrough** in slice design with actual commands and results from implementation
- [ ] Success: all documentation updated; slice marked complete

**Commit**: `docs: complete slice 124 Codex agent integration`
