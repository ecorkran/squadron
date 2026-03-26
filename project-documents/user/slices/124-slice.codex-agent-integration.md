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

Codex offers two programmatic integration paths:

1. **Codex SDK** (TypeScript, `@openai/codex-sdk`) — Thread-based API: `startThread()`, `thread.run(prompt)`, resume by thread ID. Requires Node.js 18+.
2. **Codex CLI as MCP server** (`codex mcp-server`) — Exposes `codex()` and `codex-reply()` tools via MCP stdio transport. Any MCP client can orchestrate Codex through these tools.

This slice uses **path 2 (MCP server)** because:
- Squadron is Python — no Node.js runtime dependency needed at import time
- The MCP path is already a documented integration pattern
- Squadron already depends on the `mcp` Python package
- The MCP tools (`codex()`, `codex-reply()`) map cleanly to squadron's `handle_message()` pattern: first call uses `codex()`, follow-ups use `codex-reply()` with the thread ID

Authentication uses either a ChatGPT subscription (OAuth via browser login, tokens cached at `~/.codex/auth.json`) or an OpenAI API key. Squadron does not implement the OAuth flow itself — it relies on the user having authenticated via `codex` CLI first. Squadron validates that credentials exist before attempting to use Codex.

## Value

**Architecture-level reviews with file access.** Codex can read the actual repository files referenced in a review prompt — it doesn't need file contents injected into the prompt. This is the same advantage the Claude SDK provider has over the OpenAI-compatible API providers. For architecture reviews of large documents, this eliminates prompt size constraints.

**Subscription-based usage.** ChatGPT Plus/Pro/Teams subscribers can use Codex without API credits, similar to how Claude SDK agents use the Max subscription. This gives users a second "free" agentic provider.

**Multi-model review comparison.** With both Claude SDK and Codex as agentic providers, users can compare architectural reviews across model families on the same codebase.

## Technical Scope

### Included
- `CodexProvider` implementing `AgentProvider` Protocol
- `CodexAgent` implementing `Agent` Protocol via MCP client to `codex mcp-server`
- Provider profile `codex` with `auth_type: "codex"`
- `CodexAuthStrategy` implementing `AuthStrategy` Protocol — checks for valid Codex credentials (either `~/.codex/auth.json` exists and is non-expired, or `OPENAI_API_KEY` env var is set)
- Registration in provider registry as `"codex"`
- Review system integration: `sq review slice 100 --profile codex` works
- Model alias updates for Codex model IDs (`gpt-5.3-codex`, `gpt-5.4`, etc.)

### Excluded
- Implementing the OAuth PKCE browser login flow — user runs `codex` CLI to authenticate first
- Codex SDK (TypeScript) integration — MCP path only
- Codex Cloud (web-based) integration
- Multi-agent orchestration patterns with Codex (future: 160-series)

## Dependencies

### Prerequisites
- Node.js 18+ and `@openai/codex` installed globally (`npm i -g @openai/codex`)
- User has authenticated via `codex` CLI (ChatGPT login or API key)

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

### Integration Pattern: MCP Client

The Codex CLI exposes an MCP server via `codex mcp-server`. Squadron connects as an MCP client using the `mcp` Python package's stdio transport:

```
Squadron (Python)                    Codex CLI (Node.js)
┌─────────────┐                     ┌──────────────────┐
│ CodexAgent   │ ── stdio/MCP ──▶   │ codex mcp-server │
│              │                     │                  │
│ codex() tool │ ◀── response ───   │ sandbox env      │
│ codex-reply()│                     │ file access      │
└─────────────┘                     └──────────────────┘
```

### MCP Tool Interface

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
2. **First message**: `handle_message()` spawns `codex mcp-server` subprocess via MCP stdio client, calls `codex()` tool with the message content and agent config (sandbox policy, model, cwd)
3. **Subsequent messages**: calls `codex-reply()` with the stored thread ID
4. **Shutdown**: terminates the MCP server subprocess

The MCP server subprocess is started lazily on first message (not at agent creation) to avoid unnecessary process overhead.

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
description = "OpenAI Codex agent via MCP"
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

### MCP over SDK
The Codex SDK is TypeScript-only. Wrapping it via subprocess (`node -e "..."` or a helper script) would work but adds fragility and debugging complexity. The MCP server path is a first-class integration point documented by OpenAI, uses a protocol squadron already depends on, and gives clean process isolation.

### Lazy subprocess start
The `codex mcp-server` process is started on first `handle_message()`, not at `create_agent()` time. This avoids spawning Node.js processes for agents that may never receive a message (e.g., during credential validation or dry-run scenarios).

### Read-only sandbox default
For reviews, the Codex sandbox should be `read-only` — the agent can read repository files but cannot modify them. This matches the review use case and prevents accidental side effects. For general agent tasks (future), `workspace-write` would be appropriate but is not needed for this slice.

### No OAuth implementation
Codex's OAuth PKCE flow involves browser interaction that is best handled by the `codex` CLI itself. Squadron checks for existing credentials and tells the user to run `codex` if none are found. This avoids duplicating auth infrastructure and stays within squadron's role as an orchestrator, not an auth provider.

## Success Criteria

### Functional Requirements
- `sq review slice 100 --profile codex` executes a review using Codex and produces parsed findings
- `sq review code --profile codex --diff main` works for code reviews
- `sq auth status` shows Codex credential status
- Error message when Codex is not installed tells user to `npm i -g @openai/codex`
- Error message when not authenticated tells user to run `codex` and sign in
- Model alias `codex` routes through the Codex MCP provider, not OpenAI Chat Completions

### Technical Requirements
- `CodexProvider` and `CodexAgent` implement their respective Protocols
- `CodexAuthStrategy` implements `AuthStrategy` Protocol
- MCP subprocess is cleaned up on agent shutdown and on process exit
- All existing tests continue to pass (no regression)
- New tests cover: auth strategy resolution, provider creation, agent message handling (mocked MCP), review integration

## Verification Walkthrough

1. **Prerequisites check:**
   ```
   codex --version
   # Should show installed version (v0.116.0+)
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

- **Codex MCP server stability**: The MCP server interface is documented but relatively new. If the tool schema changes, the integration breaks. Mitigation: pin to a known Codex CLI version in documentation; the MCP tool interface is simple (two tools) so breakage is easily detectable.
- **Subprocess lifecycle**: Node.js subprocess management adds a failure mode (process hangs, zombie processes). Mitigation: timeout on MCP calls, cleanup on shutdown, process group kill on exit.

## Effort
3/5 — New provider with MCP client integration, auth strategy, review system wiring, and subprocess management. Pattern is established by existing providers but MCP client usage is new territory for squadron.
