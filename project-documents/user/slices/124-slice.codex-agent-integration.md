---
docType: slice-design
slice: codex-agent-integration
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [auth-strategy-credential-management, agent-registry-lifecycle]
interfaces: [review-provider-model-selection]
status: not_started
dateCreated: 20260325
dateUpdated: 20260325
---

# Slice Design: Codex Agent Integration

## Overview

Add OpenAI Codex as a provider in squadron, enabling Codex-powered reviews and agent tasks. Codex is OpenAI's coding agent — it runs in a sandboxed environment with file access, command execution, and repository context. Unlike the existing OpenAI-compatible provider (which uses Chat Completions for stateless LLM calls), Codex is an agentic system that can read files, run commands, and iterate on its own output — similar in capability to the Claude SDK agent provider.

Codex offers three programmatic integration paths:

1. **Codex Python SDK** (`codex-app-server`, experimental v0.2.0) — Native Python API: `Codex()` context manager → `thread_start(model=...)` → `thread.run(prompt)`. Bundles the Codex binary via `codex-cli-bin` wheel — no separate Node.js install. Talks to the Codex app-server via JSON-RPC over stdio.
2. **Codex TypeScript SDK** (`@openai/codex-sdk`) — Thread-based API: `startThread()`, `thread.run(prompt)`, resume by thread ID. Requires Node.js 18+.
3. **Codex CLI as MCP server** (`codex mcp-server`) — Exposes `codex()` and `codex-reply()` tools via MCP stdio transport. Any MCP client can orchestrate Codex through these tools.

This slice uses **path 1 (Python SDK) as primary**, with **path 3 (MCP server) as fallback**:

**Python SDK (preferred):**
- Native Python — no Node.js dependency, `pip install codex-app-server` brings everything including the binary
- Clean API: context manager lifecycle, thread objects, `thread.run()` returns structured results
- Subprocess management handled internally by the SDK
- Squadron adds `codex-app-server` as an optional dependency

**MCP fallback (if Python SDK is too unstable at implementation time):**
- Squadron already depends on the `mcp` Python package
- The MCP tools (`codex()`, `codex-reply()`) map cleanly to squadron's `handle_message()` pattern
- Requires Node.js 18+ and `@openai/codex` installed separately

The core architecture (CodexProvider, CodexAgent, CodexAuthStrategy, review system wiring) is identical regardless of transport. Only the `CodexAgent` internals differ — either calling `thread.run()` or invoking MCP tools.

Authentication uses either a ChatGPT subscription (OAuth via browser login, tokens cached at `~/.codex/auth.json`) or an OpenAI API key. Squadron does not implement the OAuth flow itself — it relies on the user having authenticated via `codex` CLI first. Squadron validates that credentials exist before attempting to use Codex.

## Value

**Architecture-level reviews with file access.** Codex can read the actual repository files referenced in a review prompt — it doesn't need file contents injected into the prompt. This is the same advantage the Claude SDK provider has over the OpenAI-compatible API providers. For architecture reviews of large documents, this eliminates prompt size constraints.

**Subscription-based usage.** ChatGPT Plus/Pro/Teams subscribers can use Codex without API credits, similar to how Claude SDK agents use the Max subscription. This gives users a second "free" agentic provider.

**Multi-model review comparison.** With both Claude SDK and Codex as agentic providers, users can compare architectural reviews across model families on the same codebase.

## Technical Scope

### Included
- `CodexProvider` implementing `AgentProvider` Protocol
- `CodexAgent` implementing `Agent` Protocol via Python SDK (primary) or MCP client (fallback)
- Provider profile `codex` with `auth_type: "codex"`
- `CodexAuthStrategy` implementing `AuthStrategy` Protocol — checks for valid Codex credentials (either `~/.codex/auth.json` exists and is non-expired, or `OPENAI_API_KEY` env var is set)
- Registration in provider registry as `"codex"`
- Review system integration: `sq review slice 100 --profile codex` works
- Model alias updates for Codex model IDs (`gpt-5.3-codex`, `gpt-5.4`, etc.)

### Excluded
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
- Review Provider & Model Selection (slice 119) — `--profile` flag wiring

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

This strategy does **not** perform token refresh — Codex CLI handles that internally when the MCP server starts. Squadron only needs to verify that *some* credential exists before attempting to launch the subprocess.

### Review System Integration

The review system currently has two paths:
- `profile == "sdk"` → `run_review()` (Claude SDK, agentic)
- anything else → `_run_non_sdk_review()` (OpenAI Chat Completions API, stateless)

Codex needs a **third path** because it is agentic (like SDK) but not Claude SDK. The Codex path:
1. Builds the same system prompt and user prompt as `_run_non_sdk_review()`
2. Instead of calling Chat Completions, calls the `codex()` MCP tool with the prompt
3. The Codex agent reads files from the repository directly (it has `cwd` access)
4. Parses the response through the same `parse_review_output()` pipeline

This is wired as:
```python
async def run_review_with_profile(...):
    if profile == "sdk":
        return await run_review(...)
    if profile == "codex":
        return await _run_codex_review(...)
    return await _run_non_sdk_review(...)
```

### Provider Profile

```toml
[codex]
provider = "codex"
auth_type = "codex"
description = "OpenAI Codex agent (Python SDK or MCP)"
```

This is a built-in profile, added alongside existing `openai`, `openrouter`, `local`, `gemini`, and `sdk` profiles.

### Model Alias Updates

Update existing `codex` alias and add new entries:

```toml
[codex]
profile = "codex"       # was "openai" — now routes through Codex MCP
model = "gpt-5.3-codex"

[codex-spark]
profile = "codex"
model = "gpt-5.3-codex-spark"
notes = "Near-instant, Pro only"

[gpt54]
profile = "codex"       # or "openai" depending on user preference
model = "gpt-5.4"
```

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
- `sq review slice 100 --profile codex` executes a review using Codex and produces parsed findings
- `sq review code --profile codex --diff main` works for code reviews
- `sq auth status` shows Codex credential status
- Error message when Codex is not installed tells user to `pip install codex-app-server` (or `npm i -g @openai/codex` for MCP path)
- Error message when not authenticated tells user to run `codex` and sign in
- Model alias `codex` routes through the Codex MCP provider, not OpenAI Chat Completions

### Technical Requirements
- `CodexProvider` and `CodexAgent` implement their respective Protocols
- `CodexAuthStrategy` implements `AuthStrategy` Protocol
- Codex client (SDK or MCP subprocess) is cleaned up on agent shutdown and on process exit
- All existing tests continue to pass (no regression)
- New tests cover: auth strategy resolution, provider creation, agent message handling (mocked MCP), review integration

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

3. **Slice review via Codex:**
   ```
   sq review slice 100 --profile codex -v
   ```
   Expect: Review output with verdict, findings, and model name showing a Codex model.

4. **Code review via Codex:**
   ```
   sq review code --profile codex --diff main -v
   ```
   Expect: Code review findings. Codex reads the diff files directly from the repo.

5. **Model alias routing:**
   ```
   sq review slice 100 --model codex -v
   ```
   Expect: Routes through Codex MCP provider (not OpenAI Chat Completions).

6. **Error when Codex not installed:**
   ```
   # With codex not on PATH:
   sq review slice 100 --profile codex
   ```
   Expect: Clear error message with installation instructions.

## Risks

- **Python SDK maturity**: The `codex-app-server` package is experimental (v0.2.0). The wire protocol is tied to `codex-cli-bin` versions, so SDK/CLI version skew could cause issues. Mitigation: MCP fallback path is available; pin compatible versions in documentation.
- **Subprocess lifecycle**: Both paths spawn a Codex subprocess. Process hangs or zombie processes are possible. Mitigation: timeout on calls, cleanup on shutdown, process group kill on exit. The Python SDK handles this internally, which is one reason it's preferred over raw MCP subprocess management.

## Effort
3/5 — New provider with MCP client integration, auth strategy, review system wiring, and subprocess management. Pattern is established by existing providers but MCP client usage is new territory for squadron.
