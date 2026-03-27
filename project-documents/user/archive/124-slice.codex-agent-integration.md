---
docType: slice-design
slice: codex-agent-integration
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [auth-strategy-credential-management, agent-registry-lifecycle]
interfaces: []
status: superseded
dateCreated: 20260325
dateUpdated: 20260327
supersededBy: 128-slice.review-transport-unification-provider-decoupling.md
---

# Slice Design: Codex Agent Integration

⏪ **Status: Superseded by [Slice 128](128-slice.review-transport-unification-provider-decoupling.md)**

This slice was rewound during Phase 6 implementation. The Codex agent provider was built in isolation without addressing the underlying review system coupling issue — reviews still used direct `AsyncOpenAI` instantiation and if/elif dispatch on profile names. Rather than patch around that, we addressed the root architectural problem in slice 128 (Review Transport Unification & Provider Decoupling), which includes the Codex provider as a natural consequence of proper provider abstraction.

Slice 124 is preserved for reference. All Codex agent integration goals were achieved in slice 128.

## Overview

Add OpenAI Codex as a provider in squadron, enabling Codex-powered agent tasks. Codex is OpenAI's coding agent — it runs in a sandboxed environment with file access, command execution, and repository context. Unlike the existing OpenAI-compatible provider (which uses Chat Completions for stateless LLM calls), Codex is an agentic system that can read files, run commands, and iterate on its own output — similar in capability to the Claude SDK agent provider.

### Two distinct capabilities, two paths

**Codex models via API** (already works — no changes needed): Codex models (`gpt-5.3-codex`, `gpt-5.4`, etc.) are available through the standard OpenAI Chat Completions API with an API key. The existing `openai` provider profile and `_run_non_sdk_review()` path handle this today. Reviews using Codex models work now: `sq review slice 100 --model codex -v` routes through the OpenAI-compatible provider. No new review system wiring is needed.

**Codex as an agentic provider** (this slice): A new `CodexProvider`/`CodexAgent` that spawns Codex as an autonomous agent with sandboxed file access and command execution — for general agent tasks (spawn, task, multi-turn). This goes through the existing `AgentProvider`/`Agent` Protocol abstraction, keeping the core engine provider-agnostic.

### Agent transport

Codex offers two programmatic paths for agent control:

1. **Codex Python SDK** (`codex-app-server`, experimental v0.2.0) — Native Python API: `Codex()` context manager → `thread_start(model=...)` → `thread.run(prompt)`. Bundles the Codex binary via `codex-cli-bin` wheel — no separate Node.js install. Talks to the Codex app-server via JSON-RPC over stdio.
2. **Codex CLI as MCP server** (`codex mcp-server`) — Exposes `codex()` and `codex-reply()` tools via MCP stdio transport. Any MCP client can orchestrate Codex through these tools. Requires Node.js 18+.

This slice uses **path 1 (Python SDK) as primary**, with **path 2 (MCP server) as fallback**:

**Python SDK (preferred):**
- Native Python — no Node.js dependency, `pip install codex-app-server` brings everything including the binary
- Clean API: context manager lifecycle, thread objects, `thread.run()` returns structured results
- Subprocess management handled internally by the SDK
- Squadron adds `codex-app-server` as an optional dependency

**MCP fallback (if Python SDK is too unstable at implementation time):**
- Squadron already depends on the `mcp` Python package
- The MCP tools (`codex()`, `codex-reply()`) map cleanly to squadron's `handle_message()` pattern
- Requires Node.js 18+ and `@openai/codex` installed separately

The core architecture (CodexProvider, CodexAgent, CodexAuthStrategy) is identical regardless of transport. Only the `CodexAgent` internals differ.

### Authentication

Authentication uses either a ChatGPT subscription (OAuth via browser login, tokens cached at `~/.codex/auth.json`) or an OpenAI API key. Squadron does not implement the OAuth flow itself — it relies on the user having authenticated via `codex` CLI first. Squadron validates that credentials exist before attempting to use Codex.

For API-only usage (reviews via Chat Completions), the standard `OPENAI_API_KEY` is sufficient — no Codex-specific auth needed.

## Value

**Agentic tasks beyond reviews.** The existing OpenAI-compatible provider handles Codex models for reviews (stateless prompt → response). But for tasks that require file access, command execution, or multi-turn interaction — the same capabilities the Claude SDK provider offers — squadron needs a Codex agent provider. This is the foundation for `sq spawn --provider codex` and `sq task` workflows.

**Subscription-based agentic usage.** ChatGPT Plus/Pro/Teams subscribers can use Codex agents without API credits, similar to how Claude SDK agents use the Max subscription. This gives users a second "free" agentic provider.

**Provider abstraction validation.** Adding a second agentic provider (alongside Claude SDK) validates that the `AgentProvider`/`Agent` Protocol generalizes to non-Anthropic autonomous agents. If the abstraction holds, future agentic providers (Gemini Code Assist, etc.) follow the same pattern.

**Review system stays clean.** Codex models work through the existing non-SDK review path via Chat Completions API — no review system changes needed. The agentic provider is for general agent tasks, not reviews.

## Technical Scope

### Included
- `CodexProvider` implementing `AgentProvider` Protocol
- `CodexAgent` implementing `Agent` Protocol via Python SDK (primary) or MCP client (fallback)
- Provider profile `codex` with `auth_type: "codex"` (for agentic tasks)
- `CodexAuthStrategy` implementing `AuthStrategy` Protocol — checks for valid Codex credentials (either `~/.codex/auth.json` exists and is non-expired, or `OPENAI_API_KEY` env var is set)
- Registration in provider registry as `"codex"`
- CLI wiring: `sq spawn --provider codex`, `sq task` works with Codex agents
- Model alias updates: existing `codex` alias keeps `profile: "openai"` for API access; new `codex-agent` alias points to the `codex` provider profile for agentic use
- `sq auth status` shows Codex credential status

### Excluded
- Review system changes — Codex models already work via Chat Completions through the existing `openai` profile
- Implementing the OAuth PKCE browser login flow — user authenticates via Codex CLI/app first
- Codex TypeScript SDK integration
- Codex Cloud (web-based) integration
- Multi-agent orchestration patterns with Codex (future: 160-series)

## Dependencies

### Prerequisites
- **Python SDK path**: `pip install codex-app-server` (bundles Codex binary, no Node.js needed)
- **MCP fallback path**: Node.js 18+ and `@openai/codex` installed globally (`npm i -g @openai/codex`)
- User has authenticated via Codex CLI or app (ChatGPT login or API key)

### From Squadron
- Auth Strategy & Credential Management (slice 114) — `AuthStrategy` Protocol
- Agent Registry & Lifecycle (slice 102) — agent registration
- CLI Foundation (slice 103) — `sq spawn`, `sq task` commands

## Architecture

### Component Structure

```
src/squadron/
├── providers/
│   └── codex/
│       ├── __init__.py        # Auto-register "codex" provider
│       ├── provider.py        # CodexProvider (AgentProvider Protocol)
│       ├── agent.py           # CodexAgent (Agent Protocol, MCP client)
│       └── auth.py            # CodexAuthStrategy (AuthStrategy Protocol)
tests/
└── providers/
    └── codex/
        ├── test_provider.py
        ├── test_agent.py
        └── test_auth.py
```

### Integration Pattern: Python SDK (Primary)

The Codex Python SDK (`codex-app-server`) manages the Codex binary subprocess internally via JSON-RPC over stdio:

```
Squadron (Python)                    Codex binary (bundled)
┌─────────────┐                     ┌──────────────────┐
│ CodexAgent   │                     │ codex app-server │
│              │                     │                  │
│ Codex()      │ ── JSON-RPC ────▶  │ sandbox env      │
│ thread.run() │ ◀── response ───   │ file access      │
└─────────────┘                     └──────────────────┘
```

```python
from codex_app_server import Codex

with Codex() as codex:
    thread = codex.thread_start(model="gpt-5.3-codex")
    result = thread.run("Review this slice design...")
    raw_output = result.final_response
```

### Integration Pattern: MCP Client (Fallback)

If the Python SDK is too unstable at implementation time, the Codex CLI exposes an MCP server via `codex mcp-server`. Squadron connects as an MCP client using the `mcp` Python package's stdio transport:

```
Squadron (Python)                    Codex CLI (Node.js)
┌─────────────┐                     ┌──────────────────┐
│ CodexAgent   │ ── stdio/MCP ──▶   │ codex mcp-server │
│              │                     │                  │
│ codex() tool │ ◀── response ───   │ sandbox env      │
│ codex-reply()│                     │ file access      │
└─────────────┘                     └──────────────────┘
```

**`codex` tool** — Start a new Codex session:
```json
{
  "prompt": "Review this slice design for architectural alignment...",
  "approval-policy": "never",
  "sandbox": "read-only",
  "model": "gpt-5.3-codex",
  "cwd": "/path/to/project"
}
```

**`codex-reply` tool** — Continue an existing session:
```json
{
  "prompt": "Now check the integration points...",
  "threadId": "<thread-id-from-previous-response>"
}
```

### CodexAgent Lifecycle

1. **Creation**: `CodexProvider.create_agent()` validates credentials, stores config
2. **First message**: `handle_message()` initializes the Codex client (Python SDK: `Codex()` context manager + `thread_start()`; MCP: spawns `codex mcp-server` subprocess)
3. **Subsequent messages**: continues thread (Python SDK: `thread.run()`; MCP: `codex-reply()` with stored thread ID)
4. **Shutdown**: cleans up client (Python SDK: exits context manager; MCP: terminates subprocess)

The Codex client is started lazily on first message (not at agent creation) to avoid unnecessary process overhead.

### CodexAuthStrategy

```python
class CodexAuthStrategy:
    """Check for valid Codex credentials.

    Resolution order:
    1. OPENAI_API_KEY env var (works for API key auth)
    2. ~/.codex/auth.json exists and contains non-expired tokens
    3. Raise ProviderAuthError with instructions to run `codex` CLI
    """
```

This strategy does **not** perform token refresh — Codex CLI handles that internally when the app-server starts. Squadron only needs to verify that *some* credential exists before attempting to launch the subprocess.

### Review System — No Changes Needed

Codex models (`gpt-5.3-codex`, `gpt-5.4`, etc.) are available via the standard OpenAI Chat Completions API. The existing review system already handles this through the `openai` provider profile and `_run_non_sdk_review()`. No third review path is needed.

This means:
- `sq review slice 100 --model codex` → resolves alias to `profile: "openai", model: "gpt-5.3-codex"` → existing non-SDK path → Chat Completions API
- `sq review slice 100 --profile sdk` → existing SDK path → Claude SDK
- No `if profile == "codex"` branching in the review system

The review system remains provider-agnostic. The Codex agent provider exists for general agent tasks, not reviews.

### Provider Profile

```toml
[codex]
provider = "codex"
auth_type = "codex"
description = "OpenAI Codex agent (Python SDK or MCP) — agentic tasks with sandbox"
```

This is a built-in profile for agentic use, added alongside existing `openai`, `openrouter`, `local`, `gemini`, and `sdk` profiles. It is distinct from the `openai` profile — the `openai` profile routes to Chat Completions API, the `codex` profile routes to the Codex agent runtime.

### Model Alias Updates

The existing `codex` alias **keeps** `profile: "openai"` — this ensures reviews and stateless API calls continue working through Chat Completions:

```toml
# Existing — unchanged (API path for reviews and stateless calls)
[codex]
profile = "openai"
model = "gpt-5.3-codex"

# New — for agentic tasks via Codex agent provider
[codex-agent]
profile = "codex"
model = "gpt-5.3-codex"
notes = "Agentic: sandbox file access, command execution"

[codex-spark]
profile = "openai"
model = "gpt-5.3-codex-spark"
notes = "Near-instant, Pro only"
```

Users who want agentic Codex tasks use `--provider codex` or `--model codex-agent`. Users who want Codex model reviews use `--model codex` (routes through existing OpenAI API path).

## Protocol Compatibility

The `Agent` and `AgentProvider` Protocols (slice 102, [base.py](src/squadron/providers/base.py)) are confirmed compatible with the Codex integration:

- **`AgentProvider.create_agent(config: AgentConfig) -> Agent`**: `CodexProvider` validates credentials, stores config, returns a `CodexAgent`. No Protocol changes needed.
- **`AgentProvider.validate_credentials() -> bool`**: `CodexProvider` delegates to `CodexAuthStrategy.is_valid()`.
- **`Agent.handle_message(message: Message) -> AsyncIterator[Message]`**: `CodexAgent` translates the incoming `Message` into a `thread.run()` call (Python SDK) or `codex()` MCP tool call, then yields response `Message` objects. Same pattern as the existing OpenAI agent in [agent.py](src/squadron/providers/openai/agent.py).
- **`Agent.shutdown()`**: `CodexAgent` tears down the Codex client (exits context manager or kills subprocess).

The `AuthStrategy` Protocol (slice 114, [auth.py](src/squadron/providers/auth.py)) is also compatible: `get_credentials()`, `refresh_if_needed()`, and `is_valid()` map directly to Codex credential checking. `refresh_if_needed()` is a no-op since Codex handles token refresh internally.

No Protocol modifications are required for this slice.

## Technical Decisions

### Python SDK preferred, MCP as fallback
The Python SDK (`codex-app-server`) is preferred because it eliminates the Node.js dependency, bundles the Codex binary via pip, and provides a clean native Python API with internal subprocess management. The tradeoff is that the Python SDK is experimental (v0.2.0) — if it proves too unstable or has breaking changes at implementation time, the MCP path (`codex mcp-server`) is a well-documented fallback that squadron can connect to via the `mcp` Python package it already depends on. The decision is made at implementation time; the core architecture is transport-agnostic.

### Lazy client start
The Codex client (SDK or MCP subprocess) is started on first `handle_message()`, not at `create_agent()` time. This avoids spawning processes for agents that may never receive a message (e.g., during credential validation or dry-run scenarios).

### Read-only sandbox default
For reviews, the Codex sandbox should be `read-only` — the agent can read repository files but cannot modify them. This matches the review use case and prevents accidental side effects. For general agent tasks (future), `workspace-write` would be appropriate but is not needed for this slice.

### No OAuth implementation
Codex's OAuth PKCE flow involves browser interaction that is best handled by the `codex` CLI itself. Squadron checks for existing credentials and tells the user to run `codex` if none are found. This avoids duplicating auth infrastructure and stays within squadron's role as an orchestrator, not an auth provider.

## Success Criteria

### Functional Requirements
- `sq spawn --provider codex` creates a Codex agent
- `sq task <agent> "describe this project"` sends a task to the Codex agent and returns results
- `sq auth status` shows Codex credential status
- Error message when Codex is not installed tells user to `pip install codex-app-server` (or `npm i -g @openai/codex` for MCP path)
- Error message when not authenticated tells user to run `codex` and sign in
- Existing review commands continue to work: `sq review slice 100 --model codex` routes through OpenAI Chat Completions (unchanged)

### Technical Requirements
- `CodexProvider` and `CodexAgent` implement their respective Protocols
- `CodexAuthStrategy` implements `AuthStrategy` Protocol
- Codex client (SDK or MCP subprocess) is cleaned up on agent shutdown and on process exit
- All existing tests continue to pass (no regression)
- New tests cover: auth strategy resolution, provider creation, agent message handling (mocked), lifecycle management

## Verification Walkthrough

1. **Prerequisites check:**
   ```
   python -c "import codex_app_server; print('SDK available')"
   # or: codex --version (for MCP fallback path)
   ```

2. **Auth check via squadron:**
   ```
   sq auth status
   # Should show: codex: ✓ authenticated (or instructions to authenticate)
   ```

3. **Spawn a Codex agent:**
   ```
   sq spawn --provider codex --name codex-test
   sq list
   ```
   Expect: Agent listed with provider `codex`, state `idle`.

4. **Send a task:**
   ```
   sq task codex-test "List the top-level files in this project and describe the project structure"
   ```
   Expect: Codex agent reads the repo and returns a structured description.

5. **Reviews still work via API (no regression):**
   ```
   sq review slice 100 --model codex -v
   ```
   Expect: Routes through existing OpenAI-compatible path, not the agentic provider.

6. **Error when Codex SDK not installed:**
   ```
   # With codex-app-server not installed:
   sq spawn --provider codex --name test
   ```
   Expect: Clear error message with installation instructions.

7. **Shutdown:**
   ```
   sq shutdown codex-test
   ```
   Expect: Agent cleaned up, Codex subprocess terminated.

## Risks

- **Python SDK maturity**: The `codex-app-server` package is experimental (v0.2.0). The wire protocol is tied to `codex-cli-bin` versions, so SDK/CLI version skew could cause issues. Mitigation: MCP fallback path is available; pin compatible versions in documentation.
- **Subprocess lifecycle**: Both paths spawn a Codex subprocess. Process hangs or zombie processes are possible. Mitigation: timeout on calls, cleanup on shutdown, process group kill on exit. The Python SDK handles this internally, which is one reason it's preferred over raw MCP subprocess management.

## Effort
3/5 — New provider with MCP client integration, auth strategy, review system wiring, and subprocess management. Pattern is established by existing providers but MCP client usage is new territory for squadron.
