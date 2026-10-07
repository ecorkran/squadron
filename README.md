# Squadron

Repeatable AI workflows from the terminal: structured reviews, customizable YAML pipelines, and context handoffs between agents. It runs on your existing Claude and ChatGPT subscriptions or on any API model.

```bash
sq review slice 120 -v --model {model-alias}
```
![Review output from current squadron branch](assets/review-image.png)

## What Squadron does

**Structured reviews.** Point `sq` at an architecture doc, a slice design, a task plan, or a diff. You get back a verdict (PASS, CONCERNS, or FAIL) plus specific findings ranked by severity. Each review type runs from a purpose-built template, so the output has the same shape on every run and with any model. Once you've fixed the findings, `sq review resolve` checks them against the actual diff and records whether they were really addressed. → [Reviews](#reviews)

**Customizable pipelines.** A pipeline is a YAML file that chains steps into one command: design, review, revise, judge, implement, commit, summarize. Loops run until a review passes. Judges settle disagreements. Checkpoints stop for a human when a gate fails. Every step names its own model, so a cheap model can draft while a strong one reviews. Squadron ships pipelines for each phase of a project. Copy any of them and change it, or write your own. → [Pipelines](#pipelines-sq-run)

**Handoffs between sessions and tools.** `/sq:summary` saves a project-aware summary of the current session. `/sq:summary --restore` loads it into a fresh one. Use it to reset a long session without losing the thread, or to carry work from Claude Code to Codex and back. → [Summaries and handoffs](#summaries-and-handoffs)

**Your accounts, any model.** Claude runs through the Claude Agent SDK on your Claude subscription. GPT-6 runs through the Codex agent on your ChatGPT subscription. OpenAI, Gemini, OpenRouter, and local models work with API keys. Any step of any workflow can use any of them. → [Connecting providers](#connecting-providers)

**Same commands everywhere.** Every command works from a plain shell (`sq review`), from Claude Code (`/sq:review`), and from Codex (`$sq-review`). All three run the same CLI command and write the same artifacts. → [Claude Code and Codex](#claude-code-and-codex)

It also opens and reviews pull requests, installs skill packs, and reports environment problems with `sq doctor`.

## Install

```bash
uv tool install squadron-ai     # or: pipx install squadron-ai
sq setup                        # installs Context Forge (cf) and the /sq: and /cf: commands, then checks providers
```

`sq setup` is interactive and safe to re-run. Squadron drives its project workflow through Context Forge (the `cf` CLI). `cf` ships on npm, not PyPI, so `sq setup` installs it for you. Then, in each project you want to work on:

```bash
cf init           # installs the AI project guides and IDE config
```

Other install routes (one-line script, development checkout) are under [Other install options](#other-install-options).

## Connecting providers

See what's connected:

```
$ sq auth status
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Profile      ┃ Auth Type ┃ Status          ┃ Source             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ gemini       │ api_key   │ ✓ authenticated │ GEMINI_API_KEY     │
│ local        │ api_key   │ ✓ authenticated │ OPENAI_API_KEY     │
│ openai       │ api_key   │ ✓ authenticated │ OPENAI_API_KEY     │
│ openai-oauth │ oauth     │ ✓ authenticated │ ~/.codex/auth.json │
│ openrouter   │ api_key   │ ✓ authenticated │ OPENROUTER_API_KEY │
│ sdk          │ session   │ ✓ authenticated │ (session)          │
└──────────────┴───────────┴─────────────────┴────────────────────┘
```

Each model alias belongs to a **profile**. A profile is how squadron reaches a provider and authenticates with it:

| Profile | Account | How to connect |
|---|---|---|
| `sdk` | Claude subscription (or API key) | Sign in to Claude Code. Nothing else needed. Set `ANTHROPIC_API_KEY` to bill per token instead. |
| `openai-oauth` | ChatGPT subscription | `sq auth login openai-oauth` (add `--device-code` over SSH) |
| `openai` | OpenAI API | `export OPENAI_API_KEY=...` |
| `openrouter` | OpenRouter API | `export OPENROUTER_API_KEY=...` |
| `gemini` | Google Gemini API | `export GEMINI_API_KEY=...` |
| `local` | Ollama, vLLM, LM Studio | A model server on `http://localhost:11434/v1` |

`sq doctor` checks the whole environment (providers, `cf`, installed commands) and prints a copy-paste fix for anything missing. [docs/QUICKSTART.md](docs/QUICKSTART.md) covers every profile in detail, including how Claude Agent SDK usage is billed.

### Models

Pick a model with `--model` and an alias. List the aliases with `sq models list` (`sq models` works too):

```
$ sq models list
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Alias           ┃ Profile      ┃ Model ID                           ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ fable           │ sdk          │ claude-fable-5-1                   │
│ opus            │ sdk          │ claude-opus-5-5                    │
│ sonnet          │ sdk          │ claude-sonnet-5-5                  │
│ haiku           │ sdk          │ claude-haiku-4-5-20251001          │
│ sol             │ openai-oauth │ gpt-6-sol                          │
│ luna            │ openai-oauth │ gpt-6-luna                         │
│ gpt54           │ openai       │ gpt-5.4                            │
│ gemini-flash    │ gemini       │ gemini-3.8-flash                   │
│ kimi27          │ openrouter   │ moonshotai/kimi-k2.7-code          │
│ deepseek4-flash │ openrouter   │ deepseek/deepseek-v4.1-flash       │
│ …               │              │                                    │
└─────────────────┴──────────────┴────────────────────────────────────┘
```

About 30 aliases ship built in. `sq models list -v` adds privacy, cost tier, and per-million-token pricing. Models without tool access get file contents and diffs injected into the prompt, so they still review the real code.

To add your own aliases, put them in `~/.config/squadron/models.toml`. Only `profile` and `model` are required. The other fields feed the `-v` display:

```toml
[aliases.deepseek4-flash]
profile = "openrouter"
model = "deepseek/deepseek-v4.1-flash"
max_output_tokens = 384000
private = true
cost_tier = "cheap"

[aliases.deepseek4-flash.pricing]
input = 0.12
output = 0.48
```

Custom provider profiles go in `~/.config/squadron/providers.toml`.

### ChatGPT subscription models

The `astra`, `sol`, and `luna` aliases run GPT-6 on the `openai-oauth` profile. They're billed to your ChatGPT plan instead of per token. They run through the Codex agent, which gives the model sandboxed file access and command execution. The Codex SDK ships inside squadron, so signing in is the only setup:

```bash
sq auth login openai-oauth
sq auth status                    # shows the signed-in account and plan
```

`OPENAI_API_KEY` isn't used by this profile. The pricing shown for these aliases is what the same call would cost on the API, for comparison.

## Reviews

```bash
sq review arch 100 -v --model {model-alias}                # architecture doc on its own merits
sq review slice 120 -v --model {model-alias}               # slice design against the architecture
sq review tasks 120 -v --model {model-alias}               # task breakdown against the slice design
sq review code 120 -v --model {model-alias}                # the slice's code changes
sq review code --diff main -v --model {model-alias}        # or any diff or file glob
```

A slice number resolves its files through Context Forge. You can also pass paths directly: `sq review slice design.md --against architecture.md`. Reviews land in the project's reviews directory as markdown with frontmatter that other tools read.

Start with the spec, not the code. Reviewing a design before anyone writes it is where reviews pay off most.

| Template | Reviews |
|---|---|
| `arch` | An architecture document: completeness, consistency, feasibility |
| `slice` | A design document against an architecture reference |
| `tasks` | A task breakdown against its parent slice design |
| `code` | Source code, optionally scoped to a diff or glob |

Templates are YAML files. Adding a review type means writing a new one. See [docs/TEMPLATES.md](docs/TEMPLATES.md).

### Re-running a review

Re-running a review writes the new result to the same file. The previous version moves to `reviews/archive/`, so nothing is lost and the live directory holds only the current review for each slice and type.

### Recording that findings were addressed

A review is a fact about the code at one moment. After you fix what it found, the file still says `verdict: FAIL`, and it should. Editing it would make the record meaningless. So squadron writes a second record instead:

```bash
sq review resolve 120 -v --model {model-alias}
```

It looks at what changed since the review was written, settles every finding it can with deterministic checks, and asks a judge model only about the rest. A judge claiming it fixed a file the diff never touched gets overruled. Result:

- `ADDRESSED`: every CONCERN-or-worse finding was settled and checked against the real diff (exit 0)
- `UNADDRESSED`: at least one finding demonstrably wasn't fixed (exit 1)
- `UNKNOWN`: the check couldn't run or couldn't be trusted. It never counts as a pass (exit 1)

It writes `120-resolution.{type}.{slice}-r1.md` next to the review and never touches the review itself. Each later run writes the next revision (`-r2`, `-r3`, ...). Resolutions are an audit trail, so they're never overwritten or archived.

```bash
sq review resolve 120 code         # pick one when the slice has several reviews
sq review resolve 120 --no-judge   # deterministic checks only, no model call
sq review resolve 120 --since v1.4 # measure from a ref you choose
```

`sq review resolve` is the manual, after-the-fact check. Inside a pipeline loop, use the `findings-addressed` gate instead. It runs the same checks every round and writes one `{index}-gate.findings-addressed.{name}-r{n}.md` per round, so a three-round loop leaves three gate files and one current review. See the `findings-addressed-cycle` pipeline.

### Options

```bash
sq review code --diff main --files "src/**/*.py"   # scope by diff, glob, or both
sq review code --rules ./rules/python.md           # add project rules (CLAUDE.md loads automatically)
sq review code --output json                       # JSON to stdout; --output file --output-path x.json
```

The default output shows the verdict and finding headings. `-v` adds full finding descriptions. `-vv` adds the agent's raw tool use.

## Pipelines (`sq run`)

```bash
sq pipelines list                              # every pipeline, grouped by source
sq run P4 152                                  # design slice 152, revise until the review passes
sq run P456 152 --model {model-alias}          # design → tasks → implement → devlog
sq run P4 152 -p review-model={model-alias}    # override any pipeline param
sq run P4 152 --dry-run                        # show the plan without running it
sq pipelines show P4                           # the YAML a pipeline name runs, and where it lives
sq runs list                                   # running runs, and paused, failed and batch runs you can resume
sq runs wait <run-id> --timeout 3600           # block until a run finishes; exit code says how
sq runs prune                                  # preview failed, orphaned and broken runs; --yes deletes
```

A pipeline is plain YAML. Here's the built-in `P4`, lightly trimmed:

```yaml
name: P4
description: Design a slice (phase 4), then revise until the review passes; checkpoint if it never does

params:
  slice: required
  model: sonnet
  review-model: deepseek4-flash
  max-revisions: "2"

steps:
  - design:
      phase: 4
      model: "{model}"
      review: { template: slice, model: "{review-model}" }
  - loop:
      max: "{max-revisions}"
      until: review.pass
      accept_if: review.concerns_or_better
      commit_each_iteration: true
      on_exhaust: checkpoint
      steps:
        - dispatch: { name: revise, model: "{model}", feedback: review }
        - review: { template: slice, model: "{review-model}", slice: "{slice}" }
  - summary:
      template: minimal-sdk
      emit: [stdout, clipboard, file]
```

The building blocks are phase steps (`design`, `tasks`, `implement`), `dispatch` (send a prompt to a model), `review`, `gate` (decide from a review or a judge), `loop` (with `until`, `accept_if`, and an exhaustion policy), `each` (fan out over a list), `summary`, `compact`, and `devlog`. Loops can commit each round, so you can see the revision history in git.

**Making your own.** Squadron looks for a pipeline by name in three places, first match wins:

1. `project-documents/user/pipelines/` in the current project
2. `~/.config/squadron/pipelines/` for every project
3. The built-ins

To change a built-in, copy it into either directory under the same name. Your copy shadows the original. Give it a new name to keep both. `sq pipelines list` shows which source each pipeline came from. `sq run my-pipeline --validate` checks a file before you run it.

**Inside an agent session,** `/sq:run P4 152` (Claude Code) or `$sq-run P4 152` (Codex) drives the pipeline step by step from the session itself.

[docs/PIPELINES.md](docs/PIPELINES.md) is the full authoring guide: YAML grammar, every step type, model resolution, and judge-gated cycles.

## Summaries and handoffs

```
/sq:summary              # Claude Code: summarize this session, copy it, save it
/sq:summary --restore    # in a fresh session: load the most recent summary
$sq-summary              # Codex: same thing
$sq-summary --restore
```

The summary knows the project, slice, and phase from Context Forge. It's saved under `~/.config/squadron/runs/summaries/` and copied to the clipboard. Since every tool reads the same store, you can summarize in Claude Code and `--restore` in Codex, or the other way around. Add a key after `--restore` to load a specific older summary instead of the latest.

Choose what the summary keeps:

```bash
sq config set compact.template minimal --project     # a named template
sq config set compact.instructions "Keep slice {slice} design and tasks only." --project
```

Named templates come from `~/.config/squadron/compaction/`, then the built-ins. `compact.instructions` wins if both keys are set.

## Claude Code and Codex

`sq setup` installs the `/sq:` and `/cf:` commands into `~/.claude/commands` for every project. To refresh them later: `sq install-commands`.

For Codex, install the same commands as agent skills:

```bash
sq install-commands --ide codex     # or: sq setup --ide codex
```

They go in `~/.agents/skills` (`--local` puts them in the current project instead). Invoke them by name: `$sq-review code 925`, `$sq-run P4 152`, `$sq-pr create`, `$sq-summary`. Codex doesn't substitute arguments, so each skill reads whatever you type after its name.

Long commands like `sq review` and `sq run` are fine to run from inside Codex. The skills wait on the command without polling it.

### Codex sandbox approval rule

Codex's sandbox blocks network access and writes outside the project unless a rule allows the command. When it blocks `sq review`, the error looks like a provider failure ("provider connection failed"), but it isn't one. You don't need to write any rules: `sq install-commands --ide codex` writes squadron's own file, `~/.codex/rules/squadron.rules` (under `$CODEX_HOME` if set). It allows `sq review`, `run`, `pr`, `metrology`, `auth` and `skills`, and Codex picks it up alongside your other rules. Each install rewrites the file, `sq uninstall-commands --ide codex` removes it, and your `default.rules` is never touched. If you installed the Codex skills before this existed, run the install again.

What it allows: those commands run **outside Codex's sandbox without a prompt**, with full network and filesystem access, not just network. Commands that don't need it, like `sq models list` and `sq auth status`, aren't affected. Commands written with a redirect (`>`) or a `VAR=value` prefix never match a rule, so Codex still asks about those.

## Pull requests

```bash
sq review pr 42 -v --model {model-alias}          # review a PR (number, owner/repo#n, URL, or branch)
sq review pr 42 --post --dry-run                  # preview the review comment
sq review pr 42 --post                            # post it; re-posting updates the same comment
sq pr create --dry-run                            # open a PR from this branch, built from its slice, tasks, and commits
```

The same commands run from Claude Code (`/sq:review pr 42`, `/sq:pr create`) and Codex (`$sq-review pr 42`, `$sq-pr create`). `sq pr create` uses the project's integration branch (or `main`) as the base. It never pushes for you. If the branch isn't pushed, it prints the `git push` to run and stops. Full flags: [docs/COMMANDS.md](docs/COMMANDS.md#pr).

PR reviews save to the project's reviews directory, or to `review.external_reviews_dir` when the PR belongs to a different repository. `--reviews-dir` overrides both.

## Configuration

```bash
sq config set cwd ~/projects/myapp                          # user-level
sq config set default_rules ./rules/python.md --project     # project-level
sq config get cwd                                           # value and where it came from
sq config list
```

Precedence, highest first: CLI flag, then project (`.squadron.toml`), then user (`~/.config/squadron/config.toml`), then the built-in default. Everything user-level lives under `~/.config/squadron/`:

| Path | Holds |
|---|---|
| `config.toml` | User config values |
| `models.toml` | Your model aliases |
| `providers.toml` | Your provider profiles |
| `pipelines/` | Your pipelines (override built-ins by name) |
| `compaction/` | Your summary templates |
| `skills.toml` | Skill pack sources |
| `runs/summaries/` | Saved summaries |

## Skill packs (`sq skills`)

A skill pack is a set of commands installed from a source named in `skills.toml` (user-level or in a project). Squadron ships one, `analysis`.

```toml
[packs.mypack]
source = "github:owner/repo"   # or "bundled", "./relative/path", "/absolute/path"
prefix = "mypack"              # commands become /mypack:<name>; or dispatch_file = "name"
```

```bash
sq skills list
sq skills install mypack              # Claude Code: ~/.claude/commands/mypack/
sq skills install mypack --ide codex  # Codex: ~/.agents/skills/mypack-*/
sq skills uninstall mypack --ide codex
```

A pack holds Claude commands at its top level and, optionally, Codex skills under `agents/<name>/SKILL.md`. Each `SKILL.md` needs frontmatter whose `name` matches its directory, plus a non-empty `description`. A Codex install validates everything first and writes nothing if anything is wrong. A pack with no `agents/` directory installs for Claude only. Uninstall removes exactly the files the install wrote.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | PASS or CONCERNS |
| 1 | Error, or a review that ran but couldn't be saved |
| 2 | FAIL |

CONCERNS exits 0, so CI can gate on FAIL without failing on warnings. A review whose file couldn't be written exits 1 even though you saw the output, because tools read the file. `sq review resolve` exits 0 for `ADDRESSED` and 1 otherwise.

## Agent management (experimental)

Squadron still has agent lifecycle commands (`sq serve`, `sq spawn`, `sq task`, `sq agents list`, `sq shutdown`). They're no longer a main feature and are moving to the Amoeba project. They need the daemon: `sq serve`.

## Other install options

### Install script

Installs Squadron and Context Forge, then runs setup:

```bash
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh
```

To read it first: download with `-o install.sh`, read it, then run `bash install.sh`.

### Context Forge guide strategy

`cf init` installs the guides as plain files and commits them (it never pushes), so teammates and CI get them like any other file. That's the default from Context Forge 0.16. Older `cf` versions install a git submodule instead. Update with `npm i -g @context-forge/cli`, or pass `--strategy tarball`. To keep the submodule on purpose, use `cf init --strategy submodule`. To switch an existing submodule install to plain files:

```bash
cf guides uninstall
cf guides install --strategy tarball
git add .context-forge.toml && git commit -m "chore: set guide strategy to tarball"
```

### Development install

```bash
git clone https://github.com/ecorkran/squadron.git
cd squadron
uv sync --dev
git config core.hooksPath .githooks   # tracked pre-commit hook (sq setup does this too)
```

```bash
uv run pytest
uv run pyright
uv run ruff check
uv run ruff format
```

The tracked hook runs `cf validate frontmatter` on staged markdown. `sq doctor` reports whether it's set.

## Documentation

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)**: verify your install, configure each provider, read `sq doctor` output
- **[docs/COMMANDS.md](docs/COMMANDS.md)**: every command and flag
- **[docs/PIPELINES.md](docs/PIPELINES.md)**: pipeline authoring guide
- **[docs/TEMPLATES.md](docs/TEMPLATES.md)**: review templates and how to write new ones
- **[docs/EVENTS.md](docs/EVENTS.md)**: bind your own Python callables to squadron's lifecycle events

## License

MIT
