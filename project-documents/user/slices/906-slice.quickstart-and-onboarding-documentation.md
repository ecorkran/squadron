---
docType: slice-design
slice: quickstart-and-onboarding-documentation
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [905, 908]
interfaces: []
dateCreated: 20260513
dateUpdated: 20260712
status: complete
codeReview: none
review: none
---

# Slice Design: Quickstart and Onboarding Documentation

## Overview

A single `docs/QUICKSTART.md` that walks a new user from nothing installed to a working `sq run` invocation. This is the second rebuild of this design (20260513 original → 20260711 first rebuild → this revision), each correcting for drift discovered by checking live state instead of trusting the prior draft:

- The 20260513 original assumed a manual multi-step install narrative that `sq setup` (908) has since superseded.
- The first 20260711 rebuild assumed the README's Install/Quickstart sections still needed the `curl | sh` one-liner added and needed replacing with an install-pointer — **both wrong**, discovered only by actually reading the current README instead of reasoning from the stale design. In truth: **Install already has the `curl | sh` one-liner** (908 landed it), and **Quickstart is a different, already-solid section** — SDK auth, review-a-design, review-tasks-then-code — that has nothing to do with install steps and is not what this slice should touch.

The actual gap, confirmed by reading `README.md` in full: **no `docs/QUICKSTART.md` exists, and `sq run` (pipeline execution) is never mentioned anywhere in the README** — the entire README is scoped to `sq review`. `sq doctor` and `sq setup` are also never mentioned in any doc. That is the real scope of this slice: write the missing QUICKSTART covering install verification and first pipeline run, and add pointers to it — not replace existing README content that already works.

## Value

- **New users** already have a working `curl | sh` → `sq setup` install path (908) and an already-good "your first review" Quickstart section (existing README). What's missing is the bridge from "installed" to "I understand what `sq doctor`/`sq setup --check-only` tell me" and "I can run a full pipeline (`sq run`), not just a review."
- **Existing users** troubleshooting a broken environment have no doc to land on — `sq doctor`/`sq setup` exist in code but are undocumented.
- **README stays exactly as good as it is today** for the review-first use case; QUICKSTART adds the install-verification and pipeline-run material without duplicating or replacing README content that already works well.

## Technical Scope

### Included

1. **`docs/QUICKSTART.md`** — new file. Sections:
   - Prerequisites
   - Install (mirrors README's existing `curl | sh` / pipx / uv options — link back to README as source of truth rather than re-authoring, to avoid drift between two install descriptions)
   - Verify your install: `sq doctor` and `sq setup --check-only` — what each check means, what OK/MISSING/WARN mean, what to do about each (this is wholly new content; neither `sq doctor` nor `sq setup` is documented anywhere today)
   - Provider auth reference: all built-in profiles, required env vars, which need nothing (README's Quickstart only documents SDK auth; this fills in the other five profiles)
   - Your first review (link to/summarize README's existing Quickstart — do not duplicate wholesale)
   - **Your first pipeline run (`sq run`)** — net-new; `sq run` does not appear in README at all today
   - Troubleshooting: pointer to `sq doctor`, `sq setup --check-only`, `sq auth status`
   - Provider matrix table (current `BUILT_IN_PROFILES`, verified live — see below)

2. **`README.md`** — minimal, additive edits only (not a rewrite of Install/Quickstart, which already work):
   - Add a one-line pointer to `docs/QUICKSTART.md` near the top of Install or Quickstart (e.g. "New to Squadron? See the full [Quickstart guide](docs/QUICKSTART.md) for install verification and running your first pipeline.") — placement and exact wording decided at Phase 6 by reading the current section boundaries, not prescribed here.
   - Do **not** remove or restructure the existing `curl | sh` block, the existing Quickstart walkthrough, or the Codex/model-alias sections — all confirmed current and accurate as of 20260711.

### Explicitly Excluded

- No code changes of any kind
- No new slash commands or CLI flags
- No changes to COMMANDS.md, TEMPLATES.md, or PIPELINES.md (those are reference docs, not onboarding)
- No changes to `install.sh` or `sq setup` — this slice documents them, it does not modify them
- No rewriting or removal of README's existing Install/Quickstart/Codex/model-alias content — it is accurate and should not be touched beyond adding a pointer
- No Windows-native install automation (908 explicitly deferred this; QUICKSTART's Windows path stays manual, matching install.sh's own macOS/Linux-only scope)

## Content Design

### `docs/QUICKSTART.md` structure

```
# Squadron Quickstart

## Prerequisites
## Install
### One-line install (curl | sh)
### Global install (pipx / uv tool)
(both mirror README — link, don't duplicate, if content is identical)
## Verify your install
### sq doctor
### sq setup --check-only
### What OK / MISSING / WARN mean
## Configure a provider
### Provider matrix (table)
### Claude Code / SDK (no API key needed)
### OpenAI
### OpenRouter
### Gemini
### Local (Ollama / vLLM)
### Codex (openai-oauth)
## Your first review
(brief — links to README's existing Quickstart section rather than restating it)
## Your first pipeline run
### sq run
## Troubleshooting
## Windows
```

### Provider table

Columns: Provider, Profile name, Auth required, Status. Verified live against `src/squadron/providers/profiles.py` (`BUILT_IN_PROFILES`) as of 20260711 — re-verify at Phase 6, do not carry this table forward without re-checking, per the drift already found twice in this design's history.

| Provider | Profile | Auth required | Status |
|---|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` | Works today |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | Works today |
| Local (Ollama/vLLM/LM Studio) | `local` | None | Works today |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | Works today |
| Claude Code SDK | `sdk` | None (active Claude Code session) | Works today |
| OpenAI Codex (agentic, MCP) | `openai-oauth` | `codex auth login` (`~/.codex/auth.json`) or `OPENAI_API_KEY` | Works today |

There is no "Anthropic API — planned" row. No such profile exists in `BUILT_IN_PROFILES`, and there is no scaffolding for it in `src/squadron/providers/base.py`. Do not add speculative rows for unshipped work without verifying against current code at write time.

### Agent SDK credit note (effective June 15, 2026)

Still relevant, but the framing needs a tense check at Phase 6 — today's date (20260711) is past the 20260615 cutover, so "before June 15" language must become past tense or be reworded as a standing fact:

The SDK provider (`sdk`, plus `haiku`/`sonnet`/`opus` aliases) authenticates via the Claude Agent SDK — the same mechanism as `claude -p`. Since June 15, 2026, Anthropic separates Agent SDK usage from interactive Claude Code usage:

- **Prompt-only pipelines (`/sq:run` slash command in IDE):** unaffected. Squadron emits instructions; Claude Code's interactive session executes them. Draws from subscription usage limit as before.
- **Full-CLI pipelines (`sq run ...`):** any step that dispatches to an SDK model (`sdk` profile) invokes `claude -p` directly. This is Agent SDK usage and draws from the monthly credit ($20–$200 depending on plan).
- **`sq doctor`/`sq setup`** report the SDK profile as OK based on session presence — neither can inspect credit balance. A depleted credit will cause `sq run` failures even when doctor/setup show all-OK.
- Users running only non-Claude models (`openai`, `openrouter`, `gemini`, `local`) are unaffected.

### `sq setup` / `sq doctor` documentation

Neither command is documented anywhere in the current README or docs/ tree — this is wholly new content, not a migration of existing text. Base it on live `sq doctor --help` / `sq setup --help` output and, if needed, the source (`src/squadron/cli/commands/doctor.py`, `doctor_checks.py`, `setup.py`, `setup_steps.py`) rather than on the 908/905 slice design docs, since implementation may have drifted from those designs during Phase 6 of each.

### README changes

Additive only. Example (exact wording/placement to be finalized at Phase 6 against the live file, not prescribed here since prior drafts of this design over-specified README edits that turned out to not match reality):

```markdown
New to Squadron? See [docs/QUICKSTART.md](docs/QUICKSTART.md) for install verification, provider setup, and running your first pipeline.
```

## Cross-slice dependencies and interfaces

- **Slice 905 (`sq doctor`)** — QUICKSTART documents `sq doctor`'s output/fix-hints as a primary interface. No such documentation exists today.
- **Slice 908 (`sq setup`, complete)** — QUICKSTART documents `sq setup`/`install.sh`, which the README already surfaces at the install-command level but does not explain (what `sq setup`'s steps mean, what `--check-only` does, etc).

## Success Criteria

1. `docs/QUICKSTART.md` exists and a user who has run `curl | sh` (or manual install) can use it to verify their install (`sq doctor`/`sq setup --check-only`), configure any of the six built-in provider profiles, and run both a review and a pipeline (`sq run`) without consulting any other document.
2. Every profile in `BUILT_IN_PROFILES` (verified live, not copied from this design) has a corresponding auth instruction in QUICKSTART.
3. `sq run` — currently undocumented anywhere — has a documented first-use walkthrough.
4. README gains a single pointer to QUICKSTART; none of its existing Install/Quickstart/Codex/model-alias content is removed, restructured, or duplicated.
5. Provider matrix table is accurate relative to live `BUILT_IN_PROFILES` — no stale/planned rows carried forward without re-verification.

## Verification Walkthrough

Walkthrough validated in Phase 6 (20260712). Results recorded below.

1. **Read `docs/QUICKSTART.md` top to bottom.** Confirmed complete and internally consistent — no forward references to nonexistent sections, no stale claims. One scope correction made during Phase A re-verification: README already documents `sq run` (a `## Pipelines (sq run)` section), contradicting the original design's premise that it was undocumented. "Your first pipeline run" was written as a bridge/pointer to README + `docs/PIPELINES.md`, matching the treatment of "Your first review", rather than as net-new content.

2. **`sq doctor --help` / `sq doctor -v` / `sq setup --help` / `sq setup --check-only` against QUICKSTART's descriptions.** Ran live; captured real output before writing QUICKSTART's example block (not fabricated). One correction to the design's assumed section order: actual `sq doctor` output groups as Install → Providers and Auth → Integrations → Skill Packs → Configuration, not the Install → Integrations → Providers → Configuration order the design assumed — QUICKSTART documents the real order.

3. **Diff `README.md` against pre-slice version.**
   ```
   $ git diff README.md
   +New to Squadron? See **[docs/QUICKSTART.md](docs/QUICKSTART.md)** to verify your install and configure a provider.
   +- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** — Verify your install, configure any provider, troubleshoot `sq doctor`/`sq setup` output
   ```
   Two insertions, zero deletions — confirmed additive-only.

4. **`sq run` example command.** QUICKSTART's example (`sq run slice 152`) verified via `sq run slice 906 --dry-run`, which resolved correctly (pipeline `slice`, target `906`, 10-step plan printed). Matches README's own pre-existing example shape.

5. **`uv run ruff check && uv run ruff format --check && uv run pyright`:**
   ```
   All checks passed!
   329 files already formatted
   0 errors, 0 warnings, 0 informations
   ```

6. **`uv run pytest -q`:**
   ```
   2101 passed, 2 skipped, 6 warnings in 19.18s
   ```
   No regressions from the pre-slice baseline (docs-only change).

## Effort

1/5. Pure documentation authoring. No design decisions beyond content accuracy — but content accuracy has already required two corrections in this design's history, so Phase 6 should verify every command/output/table cell against live state rather than trusting this document.
