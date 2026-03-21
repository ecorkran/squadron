---
docType: slice-design
slice: review-provider-model-selection
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [review-workflow-templates, provider-variants-registry, auth-strategy, composed-workflows]
interfaces: []
dateCreated: 20260321
dateUpdated: 20260321
status: not_started
---

# Slice Design: Review Provider & Model Selection

## Overview

Currently, all review commands (`sq review arch|tasks|code`) are hardcoded to the Claude SDK — `runner.py` imports `ClaudeSDKClient` directly and creates an ephemeral SDK session per review. This means reviews can only run through Claude Code's session credentials, which causes "Claude-in-Claude" nesting issues when invoked from within Claude Code itself.

This slice decouples the review execution layer from the SDK, allowing reviews to route through any configured provider: Anthropic API (direct), OpenAI, OpenRouter, local models, or the existing SDK. It adds `--profile` to review CLI commands, a `profile` field to review templates, user-customizable templates loaded from `~/.config/squadron/templates/`, and config-level defaults.

## Value

- **Run reviews from inside Claude Code** without nesting errors (use Anthropic API profile instead of SDK)
- **Use any model for reviews** — GPT-4o for code review, local model for quick task checks, Opus via OpenRouter, etc.
- **User-customizable templates** — modify system prompts, change default models/profiles, create new review types without touching source code
- **Prerequisite for Ensemble Review (slice 130)** — multi-provider fan-out requires reviews to be provider-agnostic

## Technical Scope

### Included

- New `review_client.py` module providing a provider-agnostic review execution function
- `--profile` flag on all review CLI commands
- `profile` field on `ReviewTemplate` dataclass and in YAML templates
- User template loading from `~/.config/squadron/templates/`
- Config keys: `default_review_profile`
- Model-to-profile inference for common models
- Update `run-slice.md` and review slash commands to document `--profile`

### Excluded

- Anthropic API provider implementation (slice 122 — exists in plan, partial code exists)
- Ensemble review orchestration (slice 130 — consumes this slice's output)
- MCP-exposed review execution (slice 127)
- Tool use support for non-SDK providers during reviews (most reviews use Read/Glob/Grep via SDK; non-SDK providers would run without tools — document as a known limitation)

## Dependencies

### Prerequisites

- **Review Workflow Templates (slice 105)** — complete. Provides `ReviewTemplate`, YAML loader, template registry.
- **Provider Variants & Registry (slice 113)** — complete. Provides `ProviderProfile`, `get_profile()`, `get_all_profiles()`, user `providers.toml`.
- **Auth Strategy (slice 114)** — complete. Provides `resolve_auth_strategy()`, `ApiKeyStrategy`.
- **Composed Workflows (slice 118)** — complete. Provides `--model` flag, `_resolve_slice_number()`, review auto-save.

### External Packages

- `openai` (already a dependency) — used by `OpenAICompatibleProvider`
- `anthropic` (already a dependency) — for direct Anthropic API access

## Technical Decisions

### Review Execution: Provider-Agnostic Runner

The current `run_review()` in `runner.py` is tightly coupled to `ClaudeSDKClient`. Rather than rewriting it in place, we introduce a new function `run_review_with_profile()` that:

1. Resolves the profile (explicit `--profile` → template `profile` → config `default_review_profile` → `"sdk"`)
2. If profile is `"sdk"` — delegates to the existing `run_review()` (preserving all SDK-specific behavior: tools, permissions, hooks, rate limit retry)
3. If profile is any other — creates a lightweight review session using the OpenAI-compatible path:
   - Builds the prompt from the template (same as SDK path)
   - Creates an `AsyncOpenAI` client from the profile's credentials/base_url
   - Sends system prompt + user prompt via Chat Completions API
   - Parses the response through the existing `parse_review_output()`

This approach:
- **Preserves the SDK path exactly** — no regression risk for the primary use case
- **Reuses existing infrastructure** — profiles, auth, OpenAI client, parser
- **Avoids the Agent Protocol overhead** — reviews don't need agent lifecycle, registry, message bus; they're one-shot request/response

### Profile Resolution Chain

```
1. CLI flag: --profile openrouter
2. Template field: profile: openrouter (in YAML)
3. Config default: default_review_profile (in .squadron.toml)
4. Fallback: "sdk"
```

The `--model` flag continues to work as before and is orthogonal to `--profile`. When both are specified, the model overrides the template/config default but the profile determines the provider routing.

### Model-to-Profile Inference

When `--model` is specified without `--profile`, attempt to infer the profile:

| Model pattern | Inferred profile |
|---|---|
| `opus`, `sonnet`, `haiku`, `claude-*` | `sdk` (current behavior) |
| `gpt-*`, `o1-*`, `o3-*` | `openai` |
| Contains `/` (e.g., `anthropic/claude-3.5-sonnet`) | `openrouter` |

If inference fails, fall back to the template or config default. This is a convenience — explicit `--profile` always wins.

### Tool Availability by Provider

The SDK path provides tools (Read, Glob, Grep, Bash) via Claude Code's tool infrastructure. Non-SDK providers go through the Chat Completions API which has no access to these tools. This means:

- **SDK reviews** (default): full tool access, can read files, search code
- **Non-SDK reviews**: prompt-only, no tool access. The review prompt already includes file paths; the model reviews based on what's in the prompt. For arch and task reviews this is usually sufficient since the prompt includes the full document content. For code reviews, the diff content is included in the prompt.

This is a known limitation, documented in the slice design. Future work could add function-calling tool support to the non-SDK path, but that's substantial scope (tool serialization, execution, multi-turn loop) and belongs in a separate slice.

### User-Customizable Templates

Templates load from two locations, with user templates taking precedence:

1. **Built-in:** `src/squadron/review/templates/builtin/` (packaged in wheel)
2. **User:** `~/.config/squadron/templates/` (user-managed)

If a user template has the same `name` as a built-in, it overrides. This lets users:
- Modify default models/profiles for built-in review types
- Add entirely new review types (e.g., `security.yaml`, `docs.yaml`)
- Change system prompts without forking the package

The `load_builtin_templates()` function is renamed to `load_all_templates()` and loads both directories. Template loading order: built-in first, then user (user overrides built-in on name collision).

### Template YAML Changes

Add optional `profile` field to template YAML:

```yaml
name: arch
description: "Architectural review"
model: opus
profile: sdk          # NEW — defaults to sdk if omitted
system_prompt: |
  ...
```

The `ReviewTemplate` dataclass gains a `profile: str | None` field. When `None`, falls back to config or `"sdk"`.

### Config Key Addition

```python
"default_review_profile": ConfigKey(
    name="default_review_profile",
    type_=str,
    default=None,
    description="Default provider profile for review commands (e.g. openrouter, sdk)",
),
```

This lets users set a global default: `sq config set default_review_profile openrouter`.

## Data Flow

### SDK Path (default, unchanged)

```
CLI → _resolve_model() → run_review_with_profile(profile="sdk")
  → run_review() [existing]
  → ClaudeSDKClient session
  → parse_review_output()
  → ReviewResult
```

### Non-SDK Path (new)

```
CLI → _resolve_model() + _resolve_profile() → run_review_with_profile(profile="openrouter")
  → resolve profile → get_profile("openrouter") → ProviderProfile
  → resolve auth → ApiKeyStrategy → API key
  → build prompt from template
  → AsyncOpenAI(base_url=..., api_key=...) → chat.completions.create()
  → extract text response
  → parse_review_output()
  → ReviewResult
```

## Success Criteria

### Functional Requirements

- `sq review arch 118 --profile openrouter --model anthropic/claude-3.5-sonnet` routes through OpenRouter
- `sq review tasks 118 --profile openai --model gpt-4o` routes through OpenAI
- `sq review code 118 --profile local --model llama3` routes through local model server
- `sq review arch 118` (no `--profile`) continues to use SDK (backward compatible)
- `sq review arch 118 --model gpt-4o` infers `openai` profile from model name
- User templates in `~/.config/squadron/templates/` are loaded and override built-in templates by name
- User template with `profile: openrouter` uses that profile by default
- `sq config set default_review_profile openrouter` changes the default for all reviews
- Review auto-save and `--json`/`--no-save` flags work identically regardless of profile
- Slash commands (`/sq:review-arch`, `/sq:review-tasks`, `/sq:review-code`) document `--profile`

### Technical Requirements

- `review_client.py` provides `run_review_with_profile()`
- `ReviewTemplate` gains `profile: str | None` field
- Template YAML loader handles `profile` field
- User template directory scanned alongside built-in
- Config key `default_review_profile` added
- All existing tests pass (SDK path unchanged)
- New tests for profile resolution, non-SDK execution (mocked), user template loading
- `pyright`, `ruff check`, `ruff format` pass

### Verification Walkthrough

1. **SDK path unchanged (regression check):**
   ```bash
   sq review arch 118 -v
   # Expected: runs via SDK as before, same output format
   ```

2. **Explicit profile:**
   ```bash
   sq review arch 118 --profile openrouter --model anthropic/claude-3.5-sonnet -v
   # Expected: routes through OpenRouter, review output in same format
   ```

3. **Model inference:**
   ```bash
   sq review arch 118 --model gpt-4o -v
   # Expected: infers openai profile, routes through OpenAI
   ```

4. **User template:**
   ```bash
   mkdir -p ~/.config/squadron/templates
   cat > ~/.config/squadron/templates/arch.yaml << 'EOF'
   name: arch
   description: "Architectural review (custom)"
   model: gpt-4o
   profile: openai
   system_prompt: |
     You are an architectural reviewer. ...
   allowed_tools: [Read, Glob, Grep]
   permission_mode: bypassPermissions
   inputs:
     required:
       - name: input
         description: "Document to review"
       - name: against
         description: "Architecture document"
     optional:
       - name: cwd
         description: "Working directory"
         default: "."
   prompt_template: |
     Review: {input} against {against}
   EOF
   sq review arch 118 -v
   # Expected: uses custom template, routes through OpenAI with gpt-4o
   ```

5. **Config default:**
   ```bash
   sq config set default_review_profile openrouter
   sq review arch 118 --model anthropic/claude-3.5-sonnet -v
   # Expected: uses openrouter profile from config
   ```

6. **Review list shows custom templates:**
   ```bash
   sq review list
   # Expected: shows both built-in and user templates
   ```

## Implementation Notes

### Suggested Implementation Order

1. **Add `profile` field to `ReviewTemplate` and YAML loader** (effort: 1/5)
2. **Add `_resolve_profile()` and config key** (effort: 1/5)
3. **Create `review_client.py` with `run_review_with_profile()`** (effort: 2/5) — the core change; handles SDK delegation vs. non-SDK execution
4. **Wire `--profile` into CLI commands** (effort: 1/5)
5. **User template loading** (effort: 1/5)
6. **Model-to-profile inference** (effort: 0.5/5)
7. **Update slash commands** (effort: 0.5/5)
8. **Tests** (effort: 1.5/5)

### Known Limitations

- **Non-SDK reviews have no tool access.** The model reviews based on prompt content only. For arch/task reviews (document-based) this works well. For code reviews relying on `--diff` or `--files`, the diff content is injected into the prompt but the model can't explore the codebase further. This matches how reviews work when sent to an API endpoint — it's inherent to the non-SDK path.
- **Anthropic API provider (slice 122) is not yet complete.** Users wanting to use Anthropic models without the SDK can route through OpenRouter (`openrouter` profile with `anthropic/claude-3.5-sonnet` model). Direct Anthropic API support comes with slice 122.

### Testing Strategy

- **Profile resolution:** unit tests for the resolution chain (flag → template → config → sdk)
- **Model inference:** unit tests for pattern matching
- **Non-SDK execution:** mocked `AsyncOpenAI` client, verify correct routing
- **User template loading:** tmp_path-based, verify override behavior
- **SDK regression:** existing tests unchanged — SDK path delegates to existing `run_review()`
