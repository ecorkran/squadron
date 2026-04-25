---
docType: changelog
scope: project-wide
---

# Changelog

All notable changes to Squadron will be documented in this file.  This file should contain concise entries from user point of view and should answer the following questions:
* What can I do now that I couldn't do before?
* What specific bugs, if any, are fixed?
* Were any features removed?

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `loop:` step type with a `steps:` body. Enables multi-step loops where an entire sequence (e.g., `dispatch:` then `review:`) is re-run per iteration, with `until`, `on_exhaust`, and `max` semantics inherited unchanged from the existing single-step `loop:` sub-field. Nested loops are not supported in v1. Prerequisite for weighted-decay convergence (slice 184).

## [0.5.0] - 20260424

### Added
- `compact:` step now works in all execution environments. In `sq run` (true CLI), the existing session-rotate flow is preserved. In IDE/Claude Code CLI (prompt-only), `/compact` is dispatched automatically via `claude_agent_sdk.query()` and the pipeline awaits `compact_boundary` before continuing.
- `summary: restore: true` mode: re-inject a previously captured summary into the current session. Use after `compact:` to preserve a summary artifact across context reduction.
- `CompactAction` registered in the action registry as `ActionType.COMPACT`.

### Changed
- `compact:` step no longer implicitly captures a summary artifact. Pipelines that relied on `compact:` producing a summary must add an explicit `summary: emit: [file]` step before `compact:`. See PIPELINES.md for the recommended compose pattern.
- `compact:` YAML fields: `template`, `keep`, and `summarize` are no longer meaningful (silently ignored). Use `model` and `instructions` instead.

## [0.4.2] - 20260417

### Added
- `fan_out` step type: run the same inner step concurrently against N models and reduce results via a configurable `fan_in` reducer (`collect` or `first_pass`).
- Pool-based fan-out: set `models: pool:<name>` with `n: N` to draw N models from a named pool and run them in parallel.
- `FanInReducer` protocol for registering custom reducers at import time (used by slice 189 for ensemble review).

### Fixed
- `fan_out` steps now execute correctly in SDK pipeline runs (the session guard was over-broad; branches always run without a session).
- OpenRouter and other non-SDK models in `fan_out` now route to the correct provider; previously the resolved profile was dropped on a second alias lookup, causing all branches to fall back to the Claude SDK provider.
- Concurrent `fan_out` branches with the same inner step name no longer collide in the agent registry; each branch gets a unique agent name suffixed with its branch index.
- `sdk_query` (one-shot agent dispatch) now retries on `rate_limit_event` instead of failing; mirrors the existing retry logic in client/session mode.

## [0.4.1] - 20260415

### Added
- `sq review code <N>` now resolves the correct diff for slices merged directly to main (no surviving branch) by grepping commit messages for the slice number.
- `sq review code --fan N` flag accepted as a placeholder for future fan-out support (slice 182); currently warns and proceeds normally.

### Fixed
- `sq review code` was running `git diff` from the config `cwd` (e.g. `project-documents/user`) instead of the git root, causing empty diffs and UNKNOWN verdicts.
- Language-specific rules files (e.g. `python.md`) were not injected because quoted paths in block-list YAML frontmatter (`"**/*.py"`) were not stripped of quotes during parsing.
- `CLAUDE.md` is now injected into review prompts for API-only providers (e.g. OpenRouter) that cannot read files directly; headings are demoted to match the rules hierarchy.

## [0.4.0] - 20260414

### Added
- **Pool-based model selection.** `pool:` is now a first-class model specifier at every
  cascade level (`--model pool:<name>`, pipeline YAML, action config). Squadron transparently
  rotates through pool members per the pool's strategy; every selection is recorded in the
  run state file.
- **`sq pools` CLI command group.** Inspect and manage model pools:
  - `sq pools list` — Rich table of all configured pools (Name, Strategy, Members, Source)
  - `sq pools list <name>` — detail view: pool metadata, members table, last 10 selections
  - `sq pools reset <name>` — clear round-robin position for a named pool
- **Built-in model pools.** Three pools ship out of the box in the alias registry:
  `review` (round-robin, mid-tier), `high` (random, strongest), `cheap` (cheapest).
  User overrides in `~/.config/squadron/pools.toml` layer on top.
- **Four selection strategies:** `random`, `round-robin`, `cheapest`, `weighted-random`.
  Round-robin position persists across runs in `~/.config/squadron/pool-state.toml`.

## [0.3.14] - 20260412

### Fixed
- Non-SDK summary models (e.g. minimax via openrouter) no longer produce empty
  or hallucinated summaries. Prior pipeline step results (dispatch responses,
  review findings, build_context output) are now assembled into a context block
  and prepended to the instructions sent to one-shot summary models. SDK-session
  summary paths are unaffected.

### Added
- `dispatch` is now a valid pipeline step type in YAML. Accepts optional `prompt`
  and `model` fields. Enables direct dispatch steps without wrapping in a phase
  step (design/tasks/implement).

## [0.3.13] - 20260411

### Fixed
- `/sq:summary --restore` no longer reports wrong filename when restoring in a
  project with a single summary file. The CLI now always emits the selected
  filename on stderr, and the slash command parses it explicitly instead of
  relying on a nearby example value.

### Added
- "Hallucination traps in prompts" rule added to CLAUDE.md — prevents placing
  hardcoded example values near fill-in slots in model instructions.

## [0.3.12] - 20260411

### Fixed
- `compact:` pipeline steps now work correctly in prompt-only mode. Previously,
  every pipeline using `compact:` (P6, slice, tasks, app, example) would stall
  because the prompt-only renderer emitted a literal `/compact [...]` string
  that Claude Code never interpreted as a slash command. `compact:` now routes
  through the same `summary` action as SDK mode, producing a proper summary
  action with `emit: [rotate]`.

### Changed
- `compact:` in pipeline YAML is now a pure step-type alias. The runtime
  `CompactAction`, `ActionType.COMPACT`, and `_render_compact` have been removed.
  All summary/compaction logic is now unified under `SummaryAction`. Existing
  pipeline YAML files using `compact:` require no changes.

## [0.3.11] - 20260411

### Added
- `/sq:summary` now writes the summary to disk (`{project}-interactive.md`) so
  `/sq:summary --restore` can restore it in a new session, exactly like pipeline
  summaries.

## [0.3.10] - 20260411

### Added
- Checkpoints now show an interactive menu instead of always exiting. When a
  review checkpoint fires during an SDK pipeline run, you can choose:
  - **[a] Accept** — use the review findings as instructions for the next step and
    keep going without restarting.
  - **[o] Override** — type custom instructions and continue in-place.
  - **[e] Exit** — save state and exit (previous behavior, unchanged).
- The resume command (`sq run --resume <run-id>`) is shown in the menu so you
  always know how to pick up where you left off after an Exit.
- Non-interactive environments (piped stdin, `SQUADRON_NO_INTERACTIVE=1`) default
  to Exit silently so CI pipelines never hang.
- Prompt-only checkpoint instructions now describe all three choices so a human
  operator knows exactly what to do at each checkpoint.

## [0.3.9] - 20260411

### Added
- Summary and compact pipeline steps now accept any configured model alias,
  not just Claude models. You can use openrouter, gemini, or local models
  as your summary model by setting `model:` on the step.
- Using `emit: [rotate]` with a non-SDK summary model now fails immediately
  with a clear error instead of silently misbehaving.

## [0.3.8] - 20260411

### Added
- Phase pipelines (P1, P2, P4, P5, P6) now write summaries to disk automatically.
  After any phase pipeline run, `/sq:summary --restore` will find the summary
  without needing a run-id.

### Fixed
- CI pyright failure introduced in 0.3.5; `main` is green again.

## [0.3.5] - 20260410

### Added
- `emit: [file]` in a pipeline summary step now writes to a standard path
  (`~/.config/squadron/runs/summaries/{project}-{pipeline}.md`) when no
  explicit path is given. The file is overwritten each run (latest-only).
- `/sq:summary --restore` — seeds the current conversation with the most
  recent pipeline summary for this project. No run-id needed; works after
  both SDK and prompt-only runs.

## [0.3.4] - 20260409

### Added
- `/sq:summary [template]` slash command — generates a structured summary of
  the current conversation and copies it to the clipboard. Intended for the
  `/sq:summary` → `/clear` → paste workflow. Uses your configured
  `compact.template` by default.

### Removed
- PreCompact hook subcommand removed; it was dead code since 0.3.3.

## [0.3.3] - 20260408

### Added
- `summary` pipeline step type — captures a session summary and sends it to
  one or more destinations: `stdout`, `file`, `clipboard`, or `rotate`
  (compact the session in place). `compact:` remains a supported alias.
  Add `checkpoint: true` to pause after the summary emits.
- `minimal-sdk` compaction template ships with Squadron for clean
  third-person summaries suitable for seeding a fresh session.

### Changed
- `sq install-commands` no longer installs a PreCompact hook — the hook API
  doesn't reliably override compaction instructions in practice.

### Fixed
- API errors returned as assistant text (e.g. `API Error: 500 …`) are now
  treated as dispatch failures. Previously the pipeline continued to the next
  step as if dispatch had succeeded.

## [0.3.2] - 20260407

### Fixed
- `sq run` was broken for all SDK pipelines — the Claude Agent SDK stopped
  accepting runtime permission-mode changes. Permissions are now set at
  session start.
- PreCompact hook payload was malformed, producing a "Hook JSON output
  validation failed" error in Claude Code sessions.
- `.squadron.toml` is now gitignored so per-developer config isn't
  accidentally committed.

## [0.3.1] - 20260407

### Added
- `/compact` in Claude Code now uses your Squadron compaction template
  automatically. Configure with `compact.template` (template name) or
  `compact.instructions` (literal text override) in your Squadron config.
  Install via `sq install-commands`.
- `sq run --status` now shows whether a run used SDK or prompt-only mode.
- Pipeline names are now case-insensitive on all platforms.

### Fixed
- `sq run` now validates the pipeline before starting — bad checkpoint
  triggers and other config errors are reported upfront instead of crashing
  mid-run.
- `sq run --resume` on SDK runs no longer falls through to a missing CF
  command.
- Implicit resume now works regardless of pipeline name casing.

## [0.3.0] - 20260407

### Added
- `sq run <pipeline> <target>` — execute a named pipeline end-to-end. SDK
  mode runs autonomously; `--prompt-only` mode emits step-by-step
  instructions for manual execution inside Claude Code.
- `sq run --list` — show all available pipelines.
- `sq run --validate <pipeline>` — check pipeline config for errors without
  running.
- `sq run --dry-run <pipeline> <target>` — preview the execution plan.
- `sq run --status [latest|<run-id>]` — inspect a run's current state.
- `sq run --resume <run-id>` — continue a paused run from its checkpoint.
- `sq run --from <step>` — start execution from a named step (adoption).
- `--param key=value` — pass additional parameters to a pipeline at runtime.
- `--model` — override the model for the entire run.
- Pipelines pause automatically at checkpoints and can be resumed; keyboard
  interrupt also pauses with resume instructions.
- Built-in pipelines: `slice-lifecycle`, `review-only`,
  `implementation-only`, `design-batch`.
- Pipeline steps iterate over CF collections with `each:` — e.g. run a
  review loop over every unfinished slice.
- `/sq:run` slash command updated to drive prompt-only pipeline execution.

### Fixed
- Review files are now saved even on FAIL verdict (previously only saved on
  CONCERNS or better).
- Review terminal output no longer has excess indentation on headings.
- SDK reviews (Claude/Anthropic) no longer duplicate findings in output.

## [0.2.12] - 20260328

### Added
- Set `SQUADRON_APP_NAME` to tag your requests in OpenRouter traces and
  Langfuse dashboards.

## [0.2.11] - 20260328

### Added
- `sq review arch <index>` — review an architecture document on its own
  merits (no `--against` required). Accepts a bare initiative number as
  shorthand.
- Per-review-type default model config: `default_model_arch`,
  `default_model_slice`, `default_model_tasks`, `default_model_code`.
- `sq config unset <key>` — remove a config key, reverting to the default.

## [0.2.7]

### Added
- **[Experimental]** Codex provider — use OpenAI Codex as a review or
  dispatch provider. Requires the separate Codex SDK.
- `sq review code` now auto-detects language rules and injects them into the
  review prompt. Use `--rules-dir` to point at a custom rules directory or
  `--no-rules` to disable.
- `sq review code` diff is now scoped to the current slice branch
  automatically via merge-base detection.
- `-vvv` prints the full system prompt, user prompt, and injected rules to
  stderr, and saves a prompt log to `~/.config/squadron/logs/`.

## [0.2.6] - 20260325

### Fixed
- `default_model` in config now goes through alias resolution. Previously
  only `--model` on the CLI was resolved, causing UNKNOWN verdict when using
  a config default.

## [0.2.5] - 20260323

### Fixed
- `.env` file loading now looks in the current working directory only,
  instead of walking up the directory tree from the package install location.

## [0.2.4] - 20260323

### Added
- API keys are now loaded from a `.env` file in the current directory at
  startup.

## [0.2.3] - 20260323

### Added
- `sq models --verbose` displays cost tier, privacy, and notes alongside
  each model alias.

## [0.2.2] - 20260322

### Changed
- `sq model` and `sq models` merged into a single `sq models` command.

## [0.2.1] - 20260321

### Added
- README updates: model aliases, slice reviews, version info.

## [0.2.0] - 20260321

### Added
- Model alias registry — define short names like `haiku` or `minimax` in
  `~/.config/squadron/models.toml` and use them everywhere.
- `sq models` command to list available aliases.
- `--profile` flag on all `sq review` commands to choose the provider
  (sdk, openrouter, openai, gemini, local).
- User-customizable review templates from `~/.config/squadron/templates/`.
- File content and git diff injected into prompts for non-SDK reviews.

### Changed
- `review arch` renamed to `review slice`.

## [0.1.1] - 20260321

### Added
- `/sq:run-slice` slash command — runs the full slice lifecycle
  (design → tasks → implement → review) in one command.
- Bare number shorthand for review commands: `sq review slice 118`,
  `sq review tasks 118`. Review files are saved automatically when using
  the shorthand.

## [0.1.0] - 20260217

### Added
- Initial release published to PyPI as `squadron-ai`.
- `sq` CLI with agent management commands: `spawn`, `list`, `task`,
  `shutdown`.
- Review workflows: slice, tasks, and code reviews with built-in templates.
- Verbosity levels, persistent config, text colors, `--rules` flag.
- Providers: Claude SDK, OpenAI-compatible, OpenRouter, local models,
  Gemini-via-compatible.
- `sq auth login` / `sq auth status` for API key management.
- `sq install-commands` for Claude Code slash command setup.
- GitHub Actions CI and PyPI publishing on tag.
