# Squadron

Repeatable AI workflows from the terminal — structured reviews, YAML pipelines, and project artifacts, using whatever model you want.

Point `sq` at an architecture doc, a slice design, a task plan, or a diff and get back a structured verdict with specific findings. Define a pipeline in YAML and it chains reviews, artifact generation, judges, and loops into one repeatable command. Every step can run on the model of your choice.

```bash
sq review slice 120 -v
```
![Review output from current squadron branch](assets/review-image.png)

## What Squadron does

- **Repeatable reviews with structured findings** — for architecture documents, slice designs, task breakdowns, and code. Each review runs against a purpose-built template that tells the agent exactly what to evaluate and how to report it: a verdict (PASS, CONCERNS, or FAIL) plus findings with severity levels. Same template, structurally consistent output, every run.
- **Any model** — Anthropic, OpenAI, anything supported by OpenRouter, or local models. Any step of any workflow can use any model.
- **YAML-definable pipelines** — automate reviews, summaries, and context lifetimes, and generate project artifacts: architectural concepts, slice designs, task breakdowns.
- **Pipeline control flow** — `loop-each` and `loop-until` iteration, judge nodes for resolution, configurable escalation checkpoints, and composition of steps and loops into extended pipelines.
- **Context summaries and handoffs** — carry working context from a plain terminal to an agent CLI to VS Code. Squadron doesn't care where you run it.

## Review templates

Four built-in templates cover the common review patterns:

| Template | What it reviews |
|----------|----------------|
| `arch` | An architecture document on its own merits — completeness, consistency, feasibility |
| `slice` | A design document against an architecture reference |
| `tasks` | A task breakdown against its parent slice design |
| `code` | Source code, optionally scoped to a diff or glob |

The template system is extensible — each template is a YAML file, and adding new review types means writing a new YAML definition and optionally a prompt builder function. See [docs/TEMPLATES.md](docs/TEMPLATES.md) for details.

## Install

### Global install (recommended)

Squadron ships on PyPI as `squadron-ai`:

```bash
# Using uv (recommended)
uv tool install squadron-ai

# Or using pipx
pipx install squadron-ai
```

This installs Squadron **only**. Squadron drives its pipelines through Context Forge (the `cf` CLI), which ships on npm rather than PyPI, so `uv`/`pipx` cannot pull it in. Run `sq setup` next and it installs the rest for you:

```bash
sq --version
sq setup          # installs cf, /sq: and /cf: slash commands, then checks providers
```

`sq setup` is interactive and idempotent — safe to re-run. Use `--non-interactive` to print the commands instead of running them.

The `/sq:` and `/cf:` slash commands land in `~/.claude/commands` — user-level, so they're available in every project. To reinstall or update them later without a full setup pass:

```bash
sq install-commands   # refresh /sq:* commands (sq uninstall-commands removes them)
```

Then, inside a project you want to work on:

```bash
cf init           # per-project: installs AI project guides and IDE config
```

New to Squadron? See **[docs/QUICKSTART.md](docs/QUICKSTART.md)** to verify your install and configure a provider.

### Install script (alternative)

The one-line installer does the same steps — installs Squadron and Context Forge, then guides setup:

```bash
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh
```

You can inspect the script first:

```bash
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh \
    -o install.sh && less install.sh && bash install.sh
```

Either path ends in the same place.

### Development install

```bash
git clone https://github.com/manta/squadron.git
cd squadron
uv sync --dev
```

#### Pre-commit hook (recommended)

A self-healing pre-commit hook auto-formats code and fixes import order before every commit, keeping CI green:

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/sh
uv run ruff format .
uv run ruff check --fix --exit-zero .
git add -u
EOF
chmod +x .git/hooks/pre-commit
```

> **Note:** `.git/hooks/` is not tracked by git. Run the above after every fresh clone or worktree creation.

## Quickstart

### 1. Configure credentials

The default provider is Claude via the Claude Agent SDK, which supports two authentication methods:

**Claude Max subscription** (recommended): If you're already signed into Claude Code, you're set — the SDK uses your existing session. No API key needed.
```bash
# Verify you're authenticated
claude --version
```

**API key**: Alternatively, set an Anthropic API key:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Other providers (OpenAI, Gemini, OpenRouter, local) are configured with their own keys — see [Using different models](#using-different-models) and [docs/QUICKSTART.md](docs/QUICKSTART.md).

### 2. Review a design before writing code

Everyone reviews code. Almost nobody reviews the spec before writing the code. Start there:

```bash
# Does this slice design align with the architecture?
sq review slice 120 -v
```

The CLI resolves file paths automatically when you pass a slice number (requires [Context Forge](https://github.com/context-forge/context-forge)). Or pass paths directly:

```bash
sq review slice design.md --against architecture.md -v
```

You should see Rich-formatted output with a verdict and findings within about 30 seconds.

### 3. Review the task breakdown, then the code

```bash
# Does this task plan cover everything in the design?
sq review tasks 118 -v

# Review code changes
sq review code --diff main -v
```

### 4. After you fix the findings, record that you did

A review is a fact about the code at a moment. Once you've fixed what it found, the file still says `verdict: FAIL` — correctly, because editing it would make the record unfalsifiable. So squadron writes a *second* record instead:

```bash
sq review resolve 118 -v
```

It measures what changed since the review was written, settles what it can for free, asks a judge only about the rest, and writes a `118-resolution.*.md` beside the review. The review file is never touched. Exits 0 on `ADDRESSED`, 1 otherwise, so it composes in CI.

## Using different models

Use `--model` with a built-in alias to run any review or pipeline step through any supported provider:

```bash
# Claude (default — uses SDK)
sq review slice 120 -v

# OpenAI
sq review code --diff main --model gpt54-nano -v

# Google Gemini
sq review slice 120 --model flash3 -v

# OpenRouter
sq review tasks 118 --model kimi27 -v
```

Non-SDK models automatically get file contents and diffs injected into the prompt, so they can review actual code without tool access.

Run `sq models` to see all available aliases (trimmed here — around 30 ship built-in):

```
$ sq models
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Alias           ┃ Profile      ┃ Model ID                           ┃ Source ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ fable           │ sdk          │ claude-fable-5                     │        │
│ haiku           │ sdk          │ claude-haiku-4-5-20251001          │        │
│ opus            │ sdk          │ claude-opus-5                      │        │
│ sonnet          │ sdk          │ claude-sonnet-5                    │        │
│ codex           │ openai       │ gpt-5.3-codex                      │        │
│ gpt54           │ openai       │ gpt-5.4                            │        │
│ gpt54-nano      │ openai       │ gpt-5.4-nano                       │        │
│ codex-agent     │ openai-oauth │ gpt-5.3-codex                      │        │
│ flash3          │ gemini       │ gemini-3-flash-preview             │        │
│ gemini          │ gemini       │ gemini-3.1-pro-preview-customtools │        │
│ deepseek4-flash │ openrouter   │ deepseek/deepseek-v4-flash-0731    │        │
│ glm53           │ openrouter   │ z-ai/glm-5.3                       │        │
│ kimi27          │ openrouter   │ moonshotai/kimi-k2.7-code          │        │
│ minimax         │ openrouter   │ minimax/minimax-m3                 │        │
│ qwen38          │ openrouter   │ qwen/qwen3.8-2.4t-a95b             │        │
│ …               │              │                                    │        │
└─────────────────┴──────────────┴────────────────────────────────────┴────────┘
```

`sq models list -v` adds privacy, cost tier, per-million-token pricing, and notes columns.

Add your own aliases in `~/.config/squadron/models.toml`. Only `profile` and `model` are required — the rest feeds the `-v` display (shown: the built-in `deepseek4-flash` definition):

```toml
[aliases.deepseek4-flash]
profile = "openrouter"
model = "deepseek/deepseek-v4-flash-0731"
private = true
cost_tier = "cheap"

[aliases.deepseek4-flash.pricing]
input = 0.0765
output = 0.153
```

### Using Codex (experimental)

The `codex-agent` alias enables **OpenAI Codex** agentic mode for reviews and agent tasks. Codex provides sandbox file access, command execution, and subscription-based authentication:

```bash
sq review slice 120 --model codex-agent -v
```

**Setup**: Codex support requires two additional components:

1. **Codex CLI** (via npm):
   ```bash
   npm i -g @openai/codex
   ```

2. **Codex Python SDK** (from GitHub):
   ```bash
   pip install 'codex-app-server-sdk @ git+https://github.com/openai/codex.git#subdirectory=sdk/python'
   ```

3. **Authenticate** via OpenAI API key:
   ```bash
   # Option A: Set environment variable
   export OPENAI_API_KEY="sk-..."

   # Option B: Use Codex CLI (saves to ~/.codex/auth.json)
   codex auth login
   ```

Codex is experimental and requires active OpenAI subscriptions. The standard `codex` alias (without `-agent` suffix) uses OpenAI's Chat Completions API and doesn't require this setup.

## Pipelines (`sq run`)

Pipelines compose multi-step AI workflows into a single repeatable command, defined in YAML:

```bash
sq run slice 152          # design → tasks → implement → devlog for slice 152
sq run --list             # show all available pipelines
```

Pipelines can review, summarize, manage context lifetimes, and generate project artifacts — architectural concepts, slice designs, task breakdowns. Steps compose with `loop-each` and `loop-until` iteration, judge nodes that resolve disagreement, and configurable escalation checkpoints that pause for a human when a gate fails. Each step names its own model, so a cheap model can draft while a stronger one judges.

When running inside Claude Code (VS Code or terminal), use `--prompt-only` to get step-by-step instructions instead of direct LLM dispatch — or use the `/sq:run` slash command (installed by `sq setup`), which wraps this automatically.

See **[docs/PIPELINES.md](docs/PIPELINES.md)** for the full authoring guide: YAML grammar, step types, model resolution, and how to write custom pipelines.

## Reviews in depth

### Scoping code reviews

Code reviews can be scoped by diff, file pattern, or both:

```bash
# Everything in the project
sq review code

# Only changes since main
sq review code --diff main

# Only Python files
sq review code --files "src/**/*.py"

# Changes to Python files since main
sq review code --diff main --files "src/**/*.py"
```

### Recording that findings were addressed

`sq review resolve <n>` answers "did the work actually fix what the review found?" — derived from evidence, not asserted:

```bash
# The common case: resolve the only review for slice 118
sq review resolve 118 -v

# Disambiguate when several reviews exist for one slice
sq review resolve 118 code

# Deterministic checks only — no model call, no tokens
sq review resolve 118 --no-judge

# Measure from a ref you pick instead of the review's own anchor
sq review resolve 118 --since v1.4.0
```

Three outcomes. `ADDRESSED` means every CONCERN-or-worse finding was settled *and* each claim survived checking against the real diff — a judge that claims it fixed a file the diff never touched is overruled. `UNADDRESSED` means at least one finding demonstrably wasn't. `UNKNOWN` means the check couldn't run or couldn't be trusted, and is never treated as a soft pass.

Each run writes a new `-r{n}` file; resolutions are append-only. See [docs/COMMANDS.md](docs/COMMANDS.md) for the frontmatter schema.

### Adding project-specific rules

Point reviews at a rules file to include project conventions in the agent's system prompt:

```bash
sq review code --diff main --rules ./rules/python.md
```

Your project's `CLAUDE.md` is loaded automatically via the SDK's `setting_sources` mechanism — the `--rules` flag is for additional guidance on top of that.

### Verbosity

Default output is compact — just the verdict and finding headings. Turn up verbosity when you want details:

| Flag | Shows |
|------|-------|
| *(default)* | Verdict + finding headings |
| `-v` | Above + full finding descriptions |
| `-vv` | Above + raw agent tool usage |

### Output formats

```bash
# Rich terminal output (default)
sq review code --diff main

# JSON to stdout (for piping / scripting)
sq review code --diff main --output json

# JSON to file
sq review code --diff main --output file --output-path result.json
```

## Configuration

Avoid repeating flags with persistent config. Two levels with clear precedence:

```bash
# Set your default working directory (user-level)
sq config set cwd ~/projects/myapp

# Set project-specific rules (project-level)
sq config set default_rules ./rules/python.md --project

# Check where a value is coming from
sq config get cwd

# See everything
sq config list
```

**Precedence** (highest wins): CLI flag → project config (`.squadron.toml`) → user config (`~/.config/squadron/config.toml`) → built-in default.

Available keys: `cwd`, `verbosity`, `default_rules`, `compact.template`, `compact.instructions`. See [docs/COMMANDS.md](docs/COMMANDS.md) for full details.

## Context summaries and handoffs (`/sq:summary`)

Inside an interactive Claude Code session (VS Code extension or CLI), `/sq:summary` generates a project-aware summary of the conversation, copies it to the clipboard, and saves it under `~/.config/squadron/runs/summaries/`. `/sq:summary --restore` seeds a fresh session from a saved summary — so you can end a session in a plain terminal and pick the same context up in an agent CLI or VS Code, or just reset a long session without losing the thread.

Pick the summary template with either of two config keys:

```bash
# Named template (resolved from ~/.config/squadron/compaction/ then built-ins)
sq config set compact.template minimal --project

# Or a literal string — wins over compact.template if both are set.
# Params {slice}, {phase}, and {project} are substituted from Context Forge.
sq config set compact.instructions "Keep slice {slice} design and tasks only." --project
```

Both keys honour the usual `--project` / user layering.

## Agent management (experimental)

Squadron retains agent lifecycle commands, but they're no longer a primary feature — this functionality is slated to move to the Amoeba project, where it can be addressed more completely. The commands require the Squadron daemon:

```bash
sq serve            # start daemon (included in uv tool install squadron-ai)
sq serve --status   # check if running
sq serve --stop     # stop daemon
```

Then use the agent commands:

```bash
sq spawn --name my-agent
sq task my-agent "Analyze the error handling in src/core/"
sq list
sq shutdown my-agent
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (PASS or CONCERNS verdict) |
| 1 | Error (invalid arguments, missing files, runtime error), or a review that ran but could not be saved |
| 2 | Review verdict is FAIL |

CONCERNS returns exit code 0 — it's informational, not a failure. This makes `sq` usable in CI pipelines where you want to gate on FAIL but not on warnings.

A review that ran but whose file could not be written exits 1 even though you saw the output: the artifact is what tooling reads, so reporting success with nothing on disk would be a silent failure.

`sq review resolve` uses its own two codes — 0 for `ADDRESSED`, 1 for `UNADDRESSED` or `UNKNOWN`.

## Documentation

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** — Verify your install, configure any provider, troubleshoot `sq doctor`/`sq setup` output
- **[docs/COMMANDS.md](docs/COMMANDS.md)** — Full command reference with all options and arguments
- **[docs/TEMPLATES.md](docs/TEMPLATES.md)** — How review templates work and how to create new ones
- **[docs/PIPELINES.md](docs/PIPELINES.md)** — Pipeline authoring guide
- **[docs/EVENTS.md](docs/EVENTS.md)** — Bind project-specific Python callables to squadron's execution lifecycle

## Development

```bash
uv sync                # Install with dev dependencies
uv run pytest          # Tests
uv run pyright         # Type checking
uv run ruff check      # Linting
uv run ruff format     # Formatting
```

`sq setup` installs the tracked pre-commit hook — it runs `cf validate frontmatter`
(Context Forge) against staged markdown and refuses a commit with invalid
frontmatter. To install it manually instead:

```bash
git config core.hooksPath .githooks
```

`sq doctor` reports whether the hook is set and whether `cf` is available.

## License

MIT
