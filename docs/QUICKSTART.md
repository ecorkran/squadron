# Squadron Quickstart

This guide bridges "installed" to "verified and running." For the actual install and your first review, [README.md](../README.md) is the source of truth — this doc adds what it doesn't cover: how to verify your environment, how to read the six provider profiles, and where to go for your first pipeline run.

## Prerequisites

- Python 3.12+
- `git`
- **Context Forge (`cf`)** — required, not optional. Squadron assembles every dispatch prompt through it, so `sq run` cannot drive a slice without it. It ships on npm, so it needs Node.js/npm:
  ```bash
  npm i -g @context-forge/cli
  cf install-commands       # /cf: slash commands
  ```
  `sq setup` and `install.sh` both do this for you — you only need these commands if you are installing by hand.
- macOS or Linux for the one-line install (`install.sh`); Windows users install manually — see [Windows](#windows) below.

## Install

Full instructions live in [README.md § Install](../README.md#install). Fastest path:

```bash
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh
```

This installs Context Forge, Squadron, and slash commands, then hands off to `sq setup` to walk you through provider configuration. See README for the pipx/uv global-install and dev-install alternatives.

If you installed via `pipx`/`uv` instead, you have Squadron but not Context Forge — those installers only see PyPI. Run `sq setup` to finish:

```bash
sq setup
```

It installs `cf`, both sets of slash commands (`/sq:` and `/cf:`), and then checks your providers. Finally, run `cf init` inside each project you work on to install that repo's guides and IDE config.

## Verify your install

Two commands report on your environment. Both read the same checks; they differ in presentation.

### `sq doctor`

```bash
sq doctor -v
```

Prints a checklist grouped by section — **Providers and Auth**, **Integrations**, **Skill Packs**, **Configuration** — each row marked:

- `✓` OK — nothing to do
- `!` WARN — optional, shown only with `-v`
- (a missing row, not shown above because this environment has none) — required and absent; `sq doctor` exits non-zero if any required row is missing

Example output (fully configured environment):

```
Squadron Environment Diagnostic
────────────────────────────────────────────────────────────────

Install
  ✓ squadron                    version 0.6.2
  ✓ slash commands              9 command(s) at ~/.claude/commands/sq

Providers and Auth
  ✓ gemini                      GEMINI_API_KEY
  ✓ local                       OPENAI_API_KEY
  ✓ openai                      OPENAI_API_KEY
  ✓ openai-oauth                ~/.codex/auth.json
  ✓ openrouter                  OPENROUTER_API_KEY
  ✓ sdk                         (session)
  ✓ at least one provider OK    6 of 6 profiles authenticated

Integrations
  ✓ context-forge               cf at /path/to/cf
  ! codex CLI                   not on PATH
    fix: npm i -g @openai/codex
  ✓ Claude Code CLI             SDK provider available

Skill Packs
  ✓ analysis                    installed at ~/.claude/commands/analysis

Configuration
  ✓ providers.toml              using defaults (no file at ~/.config/squadron/providers.toml)
  ✓ models.toml                 loaded from ~/.config/squadron/models.toml
  ✓ project .env                loaded from ./.env

────────────────────────────────────────────────────────────────
0 missing · 1 warnings
```

Every `!` or missing row prints a `fix:` line with the exact command to run.

### `sq setup --check-only`

```bash
sq setup --check-only
```

Renders the same underlying checks as `sq doctor`, one line per item, with no interactive prompting. Use `sq setup` (no flags) for an interactive walkthrough that pauses at each unresolved item and re-checks after you act — useful the first time through, or when several things need fixing at once. Use `sq doctor` for a quick recheck once you're set up.

## Configure a provider

Squadron ships six built-in provider profiles. Verified against `BUILT_IN_PROFILES` in source as of this writing:

| Provider | Profile | Auth required | Notes |
|---|---|---|---|
| Claude Code SDK | `sdk` | None — uses your active Claude Code session | Default for reviews; see [SDK usage note](#claude-agent-sdk-usage) below |
| OpenAI | `openai` | `OPENAI_API_KEY` | |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | Multi-model gateway |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | Via OpenAI-compatible endpoint |
| Local (Ollama / vLLM / LM Studio) | `local` | None | Points at `http://localhost:11434/v1` by default |
| OpenAI Codex (agentic) | `openai-oauth` | `codex auth login` (saves to `~/.codex/auth.json`) or `OPENAI_API_KEY` | See README's [Using Codex](../README.md#using-codex-experimental) section for full setup |

To configure a profile, either set its env var:

```bash
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="..."
export GEMINI_API_KEY="..."
```

or, for `openai-oauth`, authenticate via the Codex CLI:

```bash
npm i -g @openai/codex
codex auth login
```

`sdk` and `local` need no credentials — `sdk` uses your Claude Code session, `local` assumes a model server already running on your machine.

Run `sq auth status` at any time to see credential state for every configured profile.

### Claude Agent SDK usage

The `sdk` profile (and the `haiku`/`sonnet`/`opus` aliases that route through it) authenticates via the Claude Agent SDK — the same mechanism as `claude -p`. Since June 15, 2026, Anthropic has separated Agent SDK usage from interactive Claude Code usage:

- **Prompt-only pipelines** (the `/sq:run` slash command, run inside a Claude Code IDE session): unaffected. Squadron emits step instructions; your interactive Claude Code session executes them and draws from your normal subscription usage.
- **Full-CLI pipelines** (`sq run ...` invoked directly from a shell): any step that dispatches to an `sdk`-profile model invokes `claude -p` directly. This is Agent SDK usage and draws from the separate monthly Agent SDK credit.
- `sq doctor` and `sq setup` report the `sdk` profile as OK based on session presence alone — neither can inspect your credit balance. If `sq run` fails unexpectedly on an `sdk`-profile step despite `sq doctor` showing all-OK, check your Agent SDK credit at claude.ai/settings.
- If you only use `openai`, `openrouter`, `gemini`, or `local`, none of this applies to you.

## Your first review

See [README.md § Quickstart](../README.md#quickstart) for a full walkthrough — configuring credentials, then running your first `sq review slice`, `sq review tasks`, and `sq review code`, and closing the loop with `sq review resolve` once you've fixed what a review found.

## Your first pipeline run

See [README.md § Pipelines](../README.md#pipelines-sq-run) and [docs/PIPELINES.md](PIPELINES.md) for the full pipeline-authoring guide. Quick start:

```bash
sq run --list              # see available pipelines
sq run slice 152           # design → tasks → implement → devlog for slice 152
```

## Troubleshooting

Start with:

```bash
sq doctor -v          # what's configured, what's missing, and how to fix it
sq setup --check-only # same checks, setup's step-oriented view
sq auth status         # credential state per provider profile
```

Every `fix:` hint printed by `sq doctor` is a copy-pastable command. If a profile you expect to be OK shows as missing, confirm the relevant env var is exported in your current shell (`sq doctor` reads the process environment, not just `.env` files you may have edited since starting the shell).

## Windows

`install.sh` targets macOS and Linux only. On Windows, follow README's [Global install](../README.md#global-install-recommended) section manually (`pipx install squadron-ai` or `uv tool install squadron-ai`), then run `sq setup` to configure a provider — `sq setup` itself is pure Python and works cross-platform even though the bootstrap shell script does not.
