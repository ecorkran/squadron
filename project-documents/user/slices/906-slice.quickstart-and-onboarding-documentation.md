---
docType: slice-design
slice: quickstart-and-onboarding-documentation
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [905]
interfaces: []
dateCreated: 20260513
dateUpdated: 20260513
status: not_started
---

# Slice Design: Quickstart and Onboarding Documentation

## Overview

A single `docs/QUICKSTART.md` that walks a new user from nothing installed to a working `sq run` invocation. The README's installation section is trimmed to a pointer; `sq doctor` is the runtime self-check that replaces README-section archaeology. Scope is docs-only — no code changes.

## Value

- **New users** have one document to follow instead of piecing together install steps scattered across README, COMMANDS.md, and provider-specific notes.
- **Existing users** can run `sq doctor` when something stops working — QUICKSTART is the "for more context" link that doctor's fix hints point to.
- **README** becomes a pitch-and-link document rather than an install manual, reducing duplication that drifts over time.

## Technical Scope

### Included

1. **`docs/QUICKSTART.md`** — new file. Sections:
   - Prerequisites
   - Step-by-step install (Context Forge → Squadron → slash commands)
   - Provider auth (all built-in profiles, required env vars, which ones need nothing)
   - Verifying the install with `sq doctor`
   - First commands (review, run)
   - Troubleshooting pointer back to `sq doctor` and `sq auth status`
   - Provider matrix table (what works today, what's planned, what's out of scope)

2. **`README.md`** — two targeted edits:
   - Replace the existing "Quickstart" section with a single paragraph + link to `docs/QUICKSTART.md`
   - Replace the existing "Install" section with the global-install block only (remove dev-install duplication; keep dev-install in QUICKSTART under a collapsible/section)

### Explicitly Excluded

- No code changes of any kind
- No new slash commands or CLI flags
- No changes to COMMANDS.md, TEMPLATES.md, or PIPELINES.md (those are reference docs, not onboarding)
- No auto-install scripts

## Content Design

### `docs/QUICKSTART.md` structure

```
# Squadron Quickstart

## Prerequisites
## Step 1 — Install Context Forge
## Step 2 — Install Squadron
## Step 3 — Install slash commands
## Step 4 — Configure a provider
### Provider options (table)
### Claude Code / SDK (no API key needed)
### OpenAI
### OpenRouter
### Gemini
### Local (Ollama / vLLM)
### Codex (experimental)
## Step 5 — Verify with sq doctor
## Step 6 — Your first review
## Step 7 — Your first pipeline run
## Troubleshooting
## Provider matrix
```

### Provider table

The provider matrix must be accurate as of 0.6.x. Columns: Provider, Profile name, Auth required, Status (works today / planned / deferred / out of scope). Based on current `BUILT_IN_PROFILES` and `sq doctor` output:

| Provider | Profile | Auth required | Status |
|---|---|---|---|
| Claude Code SDK | `sdk` | None (Claude Code session) | Works today |
| OpenAI | `openai` | `OPENAI_API_KEY` | Works today |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | Works today |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | Works today (limited) |
| Local (Ollama/vLLM) | `local` | None | Works today |
| OpenAI Codex (agentic) | `openai-oauth` | `codex auth login` or `OPENAI_API_KEY` | Experimental |
| Anthropic API | *(slice 203)* | `ANTHROPIC_API_KEY` | Planned — see slice 203 |

### Agent SDK credit note (effective June 15, 2026)

The SDK provider (`sdk`, `haiku`, `sonnet`, `opus` aliases) authenticates via the Claude Agent SDK — the same mechanism as `claude -p`. Starting June 15, 2026, Anthropic separates Agent SDK usage from interactive Claude Code usage:

- **Prompt-only pipelines (`/sq:run` slash command in IDE):** unaffected. Squadron emits instructions; Claude Code's interactive session executes them. Draws from subscription usage limit as before.
- **Full-CLI pipelines (`sq run ...`):** any step that dispatches to an SDK model (`sdk` profile) invokes `claude -p` directly. This is Agent SDK usage and draws from the monthly credit ($20–$200 depending on plan) starting June 15.

QUICKSTART must include a callout under the SDK provider section instructing users to claim their Agent SDK monthly credit at claude.ai/settings before June 15, 2026. Key points to cover:

1. The credit is a one-time opt-in that then auto-refreshes each billing cycle.
2. Once the credit is exhausted, additional SDK calls spill to extra usage (if enabled) or stop until the credit refreshes.
3. `sq doctor` reports the SDK profile as OK based on session presence — it cannot inspect credit balance. A depleted credit will cause `sq run` failures even when `sq doctor` shows all-OK.
4. Users running only non-Claude models (`openai`, `openrouter`, `gemini`, `local`) via `sq run` are unaffected — those profiles don't use the Agent SDK.

### `sq doctor` integration

QUICKSTART's "Verify" section should instruct the user to run `sq doctor` and interpret the output. The fix hints that `doctor` emits are designed to be self-contained one-liners; QUICKSTART provides the expanded explanation for each.

Mapping from doctor fix hint → QUICKSTART anchor:

| Doctor fix hint | QUICKSTART section |
|---|---|
| `sq install-commands` | Step 3 — Install slash commands |
| `Set OPENAI_API_KEY environment variable` | Step 4 — OpenAI |
| `Set OPENROUTER_API_KEY environment variable` | Step 4 — OpenRouter |
| `Set GEMINI_API_KEY environment variable` | Step 4 — Gemini |
| `npm i -g @manta-digital/context-forge` | Step 1 — Install Context Forge |
| `npm i -g @openai/codex` | Step 4 — Codex |
| `see fix hints above, or run 'sq auth status'` | Troubleshooting |

This mapping is a design contract — if doctor's fix hints change, QUICKSTART anchors should be updated in the same commit.

### README changes

The existing README Quickstart section is 3 subsections and ~40 lines. Replace with:

```markdown
## Quickstart

New to Squadron? Follow the step-by-step install in **[docs/QUICKSTART.md](docs/QUICKSTART.md)**.

Once installed, run `sq doctor` to confirm everything is wired up.
```

The README Install section keeps the global-install block (pipx / uv tool) and the pre-commit hook snippet, but drops the dev-install block (that moves to QUICKSTART under a "Contributing / dev install" subsection).

## Success Criteria

1. A user who has never used Squadron can follow `docs/QUICKSTART.md` from top to bottom and reach a working `sq run` invocation without consulting any other document.
2. Every provider listed in `BUILT_IN_PROFILES` has a corresponding auth instruction in QUICKSTART.
3. Running `sq doctor` after following QUICKSTART should show exit code 0 with the configured provider as OK.
4. The README Quickstart section links to QUICKSTART and does not duplicate install steps.
5. All `sq doctor` fix hints have a corresponding anchor or section in QUICKSTART.
6. Provider matrix table is accurate relative to `get_all_profiles()` output and slice 203 status.

## Verification Walkthrough

Manual review — no automated tests for docs.

1. Read `docs/QUICKSTART.md` top to bottom and confirm each step is complete and actionable.
2. Check every `sq doctor` fix hint against the QUICKSTART mapping table above — each hint must resolve to a named section.
3. Run `sq doctor` in a fresh environment (minimal env vars) and confirm that every MISSING/WARN row has a matching fix path in QUICKSTART.
4. Read the updated README Quickstart and Install sections — confirm no duplication with QUICKSTART, and that the link is present.
5. Run `uv run ruff check && uv run pyright` — should be zero errors (no code changes, but confirm the `.md` edits don't affect Python).
6. Run `uv run pytest -q` — full suite green (no regressions; docs-only change).

## Effort

1/5. Pure documentation authoring. No design decisions beyond content accuracy.
