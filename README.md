# Squadron

Repeatable, template-driven code reviews powered by Claude — from the terminal.

Point `sq` at a diff, an architecture doc, or a task plan and get back a structured verdict with specific findings. No more freeform "hey Claude, review this" — each review runs against a purpose-built prompt template that tells the agent exactly what to evaluate and how to report what it finds.

```bash
sq review slice 120 -v
```
![Review output from current squadron branch](assets/review-image.png)

## Why this exists

Code review with LLMs is powerful but inconsistent. The same prompt gets different levels of scrutiny depending on how you phrase it, what context you include, and whether you remembered to mention your project's conventions.

Squadron makes reviews **repeatable**. A review template defines the system prompt, the tools the agent can use, and the inputs it expects. Run the same template on Monday and Friday and you get structurally consistent output — a verdict (PASS, CONCERNS, or FAIL) and a list of findings with severity levels.

Three built-in templates cover the most common review patterns:

| Template | What it reviews |
|----------|----------------|
| `slice` | A design document against an architecture reference |
| `tasks` | A task breakdown against its parent slice design |
| `code` | Source code, optionally scoped to a diff or glob |

The template system is extensible — each template is a YAML file, and adding new review types means writing a new YAML definition and optionally a prompt builder function. See [docs/TEMPLATES.md](docs/TEMPLATES.md) for details.

## Install

### Fresh install (one liner)

New user? Run this to install Squadron and Context Forge, then get guided setup:

```bash
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh
```

You can inspect the script first:

```bash
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh \
    -o install.sh && less install.sh && bash install.sh
```

### Global install (recommended)

```bash
# Using pipx (recommended)
pipx install squadron-ai

# Or using uv
uv tool install squadron-ai
```

This installs Squadron **only**. Squadron drives its pipelines through Context Forge (the `cf` CLI), which ships on npm rather than PyPI, so `pipx`/`uv` cannot pull it in. Run `sq setup` next and it installs the rest for you:

```bash
sq --version
sq setup          # installs cf, /sq: and /cf: slash commands, then checks providers
```

`sq setup` is interactive and idempotent — safe to re-run. Use `--non-interactive` to print the commands instead of running them.

Then, inside a project you want to work on:

```bash
cf init           # per-project: installs AI project guides and IDE config
```

The one-line `install.sh` above does the same install steps for you; either path ends in the same place.

New to Squadron? See **[docs/QUICKSTART.md](docs/QUICKSTART.md)** to verify your install and configure a provider.

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

Squadron uses the Claude Agent SDK, which supports two authentication methods:

**Claude Max subscription** (recommended): If you're already signed into Claude Code, you're set — the SDK uses your existing session. No API key needed.
```bash
# Verify you're authenticated
claude --version
```

**API key**: Alternatively, set an Anthropic API key:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

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

Use `--model` with a built-in alias to run reviews through any supported provider:

```bash
# Claude (default — uses SDK)
sq review slice 120 -v

# OpenAI
sq review code --diff main --model gpt54-nano -v

# Google Gemini
sq review slice 120 --model flash3 -v

# OpenRouter
sq review tasks 118 --model kimi25 -v
```

Non-SDK models automatically get file contents and diffs injected into the prompt, so they can review actual code without tool access.

Run `sq models` to see all available aliases:

```
$ sq models
┌────────────┬────────────┬────────────────────────────────────────┬────────┐
│ Alias      │ Profile    │ Model ID                               │ Source │
├────────────┼────────────┼────────────────────────────────────────┼────────┤
│ codex      │ openai     │ gpt-5.3-codex                          │        │
│ codex-agent│ openai-oauth│ gpt-5.3-codex                         │        │
│ flash3     │ gemini     │ gemini-3-flash-preview                 │        │
│ gemini     │ gemini     │ gemini-3.1-pro-preview-customtools     │        │
│ glm5       │ openrouter │ z-ai/glm-5                             │        │
│ gpt54      │ openai     │ gpt-5.4                                │        │
│ gpt54-mini │ openai     │ gpt-5.4-mini                           │        │
│ gpt54-nano │ openai     │ gpt-5.4-nano                           │        │
│ haiku      │ sdk        │ claude-haiku-4-5-20251001              │        │
│ kimi25     │ openrouter │ moonshotai/kimi-k2.5                   │        │
│ minimax    │ openrouter │ minimax/minimax-m2.7                   │        │
│ opus       │ sdk        │ claude-opus-4-6                        │        │
│ sonnet     │ sdk        │ claude-sonnet-4-6                      │        │
└────────────┴────────────┴────────────────────────────────────────┴────────┘
```

Add your own aliases in `~/.config/squadron/models.toml`:

```toml
[aliases]
deepseek = { profile = "openrouter", model = "deepseek/deepseek-r2" }
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

## Interactive `/compact` for Claude Code

Squadron ships a `PreCompact` hook that runs whenever you type `/compact` (or auto-compaction fires) inside an interactive Claude Code session — VS Code extension or CLI Claude Code. The hook feeds project-aware instructions into Claude Code's compaction summarizer so slice context isn't lost.

`sq install-commands` writes the hook entry into your project's `.claude/settings.json` alongside the slash command files:

```bash
sq install-commands   # installs slash commands AND the PreCompact hook
```

Pick the instructions the hook emits with either of two config keys:

```bash
# Named template (resolved from ~/.config/squadron/compaction/ then built-ins)
sq config set compact.template minimal --project

# Or a literal string — wins over compact.template if both are set.
# Params {slice}, {phase}, and {project} are substituted from Context Forge.
sq config set compact.instructions "Keep slice {slice} design and tasks only." --project
```

Both keys honour the usual `--project` / user layering. `sq uninstall-commands` removes the squadron-managed hook entry while preserving any third-party hooks.

## Agent management

Agent lifecycle commands require the Squadron daemon. Start it first:

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

## Pipelines (`sq run`)

Pipelines compose multi-step AI workflows into a single repeatable command:

```bash
sq run slice 152          # design → tasks → implement → devlog for slice 152
sq run --list             # show all available pipelines
```

When running inside Claude Code (VS Code or terminal), use `--prompt-only` to get step-by-step instructions instead of direct LLM dispatch — or install the `/sq:run` slash command which wraps this automatically:

```bash
sq install-commands       # installs /sq:run and other slash commands
```

See **[docs/PIPELINES.md](docs/PIPELINES.md)** for the full authoring guide: YAML grammar, step types, model resolution, and how to write custom pipelines.

## Documentation

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** — Verify your install, configure any provider, troubleshoot `sq doctor`/`sq setup` output
- **[docs/COMMANDS.md](docs/COMMANDS.md)** — Full command reference with all options and arguments
- **[docs/TEMPLATES.md](docs/TEMPLATES.md)** — How review templates work and how to create new ones
- **[docs/PIPELINES.md](docs/PIPELINES.md)** — Pipeline authoring guide

## Development

```bash
uv sync                # Install with dev dependencies
uv run pytest          # Tests
uv run pyright         # Type checking
uv run ruff check      # Linting
uv run ruff format     # Formatting
```

Install the tracked pre-commit hook once per clone — it runs `sq validate docs`
against staged markdown and refuses a commit with invalid frontmatter:

```bash
git config core.hooksPath .githooks
```

`sq doctor` reports whether this is set.

## License

MIT
