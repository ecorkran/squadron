---
docType: changelog
scope: project-wide
---

# Changelog

All notable changes to Squadron will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.5] - 20260410

### Added
- `emit: [file]` (bare, no explicit path) in pipeline YAML now writes the
  summary to `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
  (latest-only overwrite). Project name resolved from CF via CWD; falls back
  to `"unknown"`.
- `_project` param automatically injected into `ActionContext.params` at
  pipeline init via `gather_cf_params()`. Caller-supplied `_project` is not
  overwritten.
- `sq _summary-instructions --restore` hidden CLI flag — reads the most recent
  summary file for the current CF project and prints it to stdout. Lists all
  matching pipelines on stderr when multiple exist.
- `/sq:summary --restore` skill branch — seeds the current conversation with
  the latest pipeline summary; no clipboard write; prints a one-line
  confirmation. No run-id needed.
- `commands/sq/run.md` summary handler now writes the summary to the
  conventional file path via Bash, enabling `/sq:summary --restore` after a
  prompt-only pipeline run.

## [0.3.4] - 20260409

### Added
- `/sq:summary [template]` slash command — generates a summary of the current
  conversation using a compaction template and copies it to the clipboard.
  Designed for `/sq:summary` → `/clear` → paste workflow. Template resolves
  via explicit arg, then `compact.template` config, then `"minimal"` default.
  Clipboard via `pbcopy` (macOS) / `xclip` / `wl-copy` (Linux).
- `sq _summary-instructions [template]` hidden CLI — prints rendered template
  instructions to stdout. Used internally by `/sq:summary`.

### Removed
- `sq _precompact-hook` subcommand and all PreCompact hook install/uninstall
  logic. Dead code since 0.3.3; useful parts salvaged into `summary_render.py`.

## [0.3.3] - 20260408

### Added
- `summary` pipeline step type — captures a session summary and emits it to one
  or more destinations: `stdout`, `file: <path>`, `clipboard`, or `rotate`
  (session-rotate compaction). Replaces `compact:` for new pipelines; `compact:`
  remains a backward-compatible alias. Optional `checkpoint:` shorthand pauses
  after emit.
- `SDKExecutionSession.capture_summary()` — generates a session summary without
  rotating. Useful for fanout: capture once, emit to multiple destinations.
- SDK session management and compaction — `SDKExecutionSession.compact()` rotates
  the session: switches to a summary model, captures a summary, disconnects,
  reconnects a fresh session, and seeds it with the summary. On resume, the
  executor automatically re-seeds from the persisted compact summary.
- `CompactSummary` stored in `RunState.compact_summaries` (schema v3) so summaries
  survive checkpoint pauses and resume correctly.
- `minimal-sdk` compaction template for producing clean third-person summaries
  suitable for seeding a fresh session.

### Changed
- `SDKExecutionSession.compact()` accepts an optional `summary=` kwarg — skips
  the capture phase and uses the provided text directly, enabling reuse across
  multiple emit destinations.
- SDK pipeline sessions now default to the Claude Code system prompt preset
  instead of the Agent SDK's minimal tool-only prompt.
- `sq install-commands` no longer installs the `PreCompact` hook. The hook API
  doesn't reliably override compaction instructions in practice.

### Fixed
- CLI-formatted API errors (e.g. `API Error: 500 ...`) returned as assistant text
  by the Claude CLI are now detected and treated as dispatch failures — previously
  the pipeline continued to the next action (review, checkpoint) as if dispatch
  had succeeded.

### Removed
- `SDKExecutionSession.configure_compaction()` stub — replaced by `compact()`.

## [0.3.2] - 20260407

### Fixed
- SDK permission mode is now set at session start via `ClaudeAgentOptions(permission_mode="bypassPermissions")` instead of via runtime `set_permission_mode()`. The Claude Agent SDK began rejecting the runtime call (requires `--dangerously-skip-permissions` at CLI launch), which broke `sq run` against pipelines using the SDK executor. Affects all pipeline runs in SDK mode.
- PreCompact hook payload now uses top-level `systemMessage` instead of `hookSpecificOutput.additionalContext`. Claude Code's `PreCompact` hook does not support `hookSpecificOutput` (that field is for `PreToolUse` / `UserPromptSubmit` / `PostToolUse`); the prior shape produced a "Hook JSON output validation failed" error in interactive Claude Code sessions. Verified end-to-end via the BANANA literal test in a real `/compact` session.
- `.squadron.toml` is now gitignored — per-developer project config should not be committed.

## [0.3.1] - 20260407

### Added
- Interactive `/compact` PreCompact hook for Claude Code (slice 157)
  - Hidden `sq _precompact-hook` subcommand emits the Claude Code `PreCompact` payload on stdout; user-facing surface is config only
  - Two new config keys: `compact.template` (YAML template name, default `minimal`) and `compact.instructions` (literal override; wins over template)
  - `sq install-commands` / `sq uninstall-commands` now write/remove the squadron-managed `PreCompact` entry in project-local `.claude/settings.json` alongside the slash commands, non-destructively merging with existing hooks via a `_managed_by: "squadron"` marker
  - `--hook-target` option on install/uninstall (defaults to `./.claude/settings.json`)
  - `LenientDict` and `render_with_params` extracted from `actions/compact.py` into shared `squadron.pipeline.compact_render` module
  - Hook is fail-open: any render failure degrades to empty `additionalContext`, always exits 0
- Pipeline executor hardening — resume mode correctness and case-insensitive pipeline names (slice 156)
  - `ExecutionMode` StrEnum (`SDK`, `PROMPT_ONLY`) in `state.py` — no string literals in dispatch logic
  - `RunState.execution_mode` field — persisted in state file (schema v2); defaults to `SDK` for forward-compat
  - `_run_pipeline_sdk` and `_run_pipeline` accept `run_id` param — resumes reuse existing state file
  - `--resume` and implicit resume both dispatch via `match state.execution_mode:` — correct runner always used
  - `_handle_prompt_only_init` records `ExecutionMode.PROMPT_ONLY` in initial state
  - `sq run --status` output includes `Mode:` line showing execution mode
  - Pipeline name normalised to lowercase at four boundaries: `load_pipeline`, `discover_pipelines`, `init_run`, CLI input
  - Schema version bumped to 2; v1 state files raise `SchemaVersionError` on resume

### Fixed
- `sq run` now validates pipeline before execution — invalid action parameters (e.g. bad checkpoint trigger) caught with clear errors instead of runtime `ValueError`
- `CheckpointAction.execute()` returns `ActionResult(success=False)` on invalid trigger instead of unhandled exception
- `sq run --resume <id>` on SDK runs no longer falls through to non-existent `cf compact` CLI call
- Implicit resume detects paused runs regardless of pipeline name case (macOS/Linux consistent)
- SDK pipeline executor — autonomous pipeline execution via `ClaudeSDKClient` (slice 155)
  - `SDKExecutionSession` — persistent client wrapper with `set_model()`, `dispatch()`, `configure_compaction()` lifecycle
  - Per-step model switching via `client.set_model(model_id)` across pipeline steps
  - Compact action SDK path — configures server-side compaction instead of calling CF
  - `ActionContext.sdk_session` — optional field propagated to all actions by the executor
  - Environment detection — `sq run` from inside Claude Code session shows clear error directing to `--prompt-only`
  - Session lifecycle managed in `_run_pipeline_sdk()` with `finally` disconnect on success, failure, or interrupt
- Prompt-only pipeline executor — `--prompt-only` mode for `sq run` (slice 153)
  - `sq run <pipeline> <target> --prompt-only` — output first step's JSON instructions
  - `sq run --prompt-only --next --resume <run-id>` — advance to next step
  - `sq run --step-done <run-id> [--verdict PASS|CONCERNS|FAIL]` — mark step complete
  - `StepInstructions`, `ActionInstruction`, `CompletionResult` data models
  - Per-action-type instruction builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog)
  - `render_step_instructions()` — pure function that expands steps without execution
  - `StateManager.record_step_done()` — public method for prompt-only feedback
  - `/sq:run` slash command rewritten to consume prompt-only executor output
- `sq run` CLI command — pipeline execution, inspection, and management (slice 151)
  - `sq run <pipeline> <target>` — execute a pipeline with positional target resolution
  - `sq run --list` — discover and display available pipelines in a Rich table
  - `sq run --validate <pipeline>` — semantic validation of pipeline definitions
  - `sq run --dry-run <pipeline> <target>` — show execution plan without running
  - `sq run --status [latest|<run-id>]` — display run status in a Rich panel
  - `sq run --resume <run-id>` — resume a paused run from its checkpoint
  - `sq run --from <step>` — mid-process adoption starting at a named step
  - Implicit resume detection — prompts when a matching paused run is found
  - `--param key=value` — repeatable option for additional pipeline parameters
  - `--model` — CLI-level model override (cascade level 1)
  - Keyboard interrupt handling with resume instructions
  - CF pre-flight check prevents orphan state files
- Pipeline state persistence — `StateManager` in `state.py` (slice 150)
  - `RunState`, `StepState`, `CheckpointState` Pydantic models; `SchemaVersionError` exception
  - Atomic write-then-rename: interrupted writes never corrupt existing state files
  - `init_run()` creates state file; `make_step_callback()` appends step after each step completes
  - `finalize()` writes terminal status (`completed`/`failed`)
  - `load()` deserializes and validates; `load_prior_outputs()` reconstructs `prior_outputs` for resume
  - `first_unfinished_step()` locates resume entry point; `find_matching_run()` for implicit resume detection
  - `list_runs()` with pipeline/status filters; `prune()` auto-deletes oldest completed/failed runs
  - All tests use `tmp_path` injection — real `~/.config` is never touched during tests
- Pipeline executor — `execute_pipeline()` async function in `executor.py` (slice 149)
  - Sequential step execution: resolves placeholders, expands step types, runs each action
  - Parameter merging: definition defaults merged with caller params; required params validated
  - `start_from` skip logic: resume from a named step, `ValueError` if step not found
  - Checkpoint pause propagation: `outputs["checkpoint"] == "paused"` stops pipeline with `PAUSED` status
  - Action failure propagation: `ActionResult.success == False` stops pipeline with `FAILED` status
  - `on_step_complete` observer callback for progress tracking (enables state manager and CLI integration)
  - Auto-generated `run_id` (12-char hex) when not provided
- Result types for executor (slice 149)
  - `ExecutionStatus(StrEnum)` — `COMPLETED`, `FAILED`, `PAUSED`, `SKIPPED`
  - `StepResult` dataclass — step name, type, status, action results, iteration, error
  - `PipelineResult` dataclass — pipeline name, status, step results, paused_at, error
- Parameter placeholder resolution — `resolve_placeholders(config, params)` (slice 149)
  - Simple `{name}` → `str(params[name])`; left as-is if missing
  - Dotted `{name.field}` → nested dict traversal; left as-is if not resolvable
  - Recursive resolution for nested dicts and list elements
- Retry loop execution with configurable exit conditions (slice 149)
  - `LoopCondition(StrEnum)` — `REVIEW_PASS`, `REVIEW_CONCERNS_OR_BETTER`, `ACTION_SUCCESS`
  - `ExhaustBehavior(StrEnum)` — `FAIL`, `CHECKPOINT`, `SKIP`
  - `LoopConfig` dataclass parsed from `loop:` step config key
  - Loop runs until `until` condition met or `max` iterations exhausted
  - `on_exhaust` controls behavior at max: fail pipeline, pause at checkpoint, or skip step
  - `loop.strategy` field logged as warning; falls back to basic max-iteration loop (160 scope)
  - Checkpoint pause inside a loop stops the loop immediately
- `EachStepType` in `steps/collection.py` — iterates over a source collection (slice 149)
  - Structural validation: `source`, `as`, `steps` required; source must match regex pattern
  - `expand()` returns empty list; executor handles `each` execution directly
  - Registered under `StepTypeName.EACH` at module load
- Source registry for `each` collection queries (slice 149)
  - `_SOURCE_REGISTRY` keyed by `(namespace, function)` tuple
  - `_cf_unfinished_slices` — queries `ContextForgeClient.list_slices()`, filters `status != "complete"`
  - `_parse_source()` parses and validates source strings against registered registry entries
  - Item binding: `{as_name.field}` resolves against item dict for each iteration

- Pipeline Pydantic schema models — `PipelineSchema`, `StepSchema` for YAML validation with step shorthand expansion (slice 148)
- Pipeline loader — `load_pipeline()` with multi-source discovery: project → user → built-in directory precedence (slice 148)
- Pipeline discovery — `discover_pipelines()` enumerates all available pipelines with source attribution (slice 148)
- Pipeline semantic validation — `validate_pipeline()` checks step type registry, model alias resolution, review template existence, param placeholder declarations (slice 148)
- Built-in pipeline definitions — `slice-lifecycle`, `review-only`, `implementation-only`, `design-batch` YAML files in `data/pipelines/` (slice 148)
- `CompactAction` — pipeline action for context compaction (slice 147)
  - Loads compaction instruction templates by name from `data/compaction/` with user override layering
  - Renders instructions with `keep` and `summarize` parameters
  - Issues rendered instructions to CF via `_run()`, optionally triggers CF summarize
  - Auto-registers at module import time
- Compaction instruction templates — YAML-based instruction templates (slice 147)
  - Ships `default.yaml` with draft compaction instructions
  - User overrides via `~/.config/squadron/compaction/`
- `PhaseStepType` — step type for design/tasks/implement phases (slice 147)
  - Expands to 6-action sequence: cf-op(set_phase) → cf-op(build) → dispatch → review → checkpoint → commit
  - Handles optional review (str or dict) and checkpoint config
  - Registers for all three phase names
- `CompactStepType` — step type for context compaction (slice 147)
  - Translates keep/summarize/template config into single compact action
- `ReviewStepType` — standalone review step type (slice 147)
  - Expands to review + optional checkpoint
- `DevlogStepType` — devlog step type (slice 147)
  - Expands to single devlog action with auto/explicit mode support
- `ReviewAction` — pipeline action for review gates (slice 146)
  - Delegates to `run_review_with_profile()`, maps `ReviewResult` to `ActionResult` with verdict and structured findings
  - Model/profile resolution via 5-level cascade, same pattern as dispatch
  - Review file persistence (non-fatal on failure)
  - Auto-registers at module import time
- `CheckpointAction` — pipeline action for quality gates (slice 146)
  - Evaluates trigger (`always`, `on-concerns`, `on-fail`, `never`) against prior review verdict
  - Returns `paused`/`skipped` data — executor interprets the result
  - `CheckpointTrigger` StrEnum with four values
  - Auto-registers at module import time
- `review/persistence.py` — shared review file formatting and saving (slice 146)
  - `format_review_markdown()`, `save_review_file()`, `yaml_escape()`, `SliceInfo` TypedDict
  - Extracted from `cli/commands/review.py` for reuse by pipeline review action
- `DispatchAction` — pipeline action for language model dispatch (slice 145)
  - Resolves model alias via 5-level cascade (`ModelResolver`), creates one-shot agent, sends prompt, captures response
  - Profile resolution: explicit param override > alias-derived profile > SDK default
  - SDK response deduplication (skips `sdk_type="result"` messages)
  - Token metadata passthrough (`prompt_tokens`, `completion_tokens`, `total_tokens`)
  - Error handling: never raises, returns `ActionResult(success=False)` on any failure
  - Agent shutdown guaranteed via `try/finally` block
  - Auto-registers at module import time

### Fixed
- Review files now saved on FAIL verdict; exit-on-fail moved after file write in all review commands
- Terminal finding display: removed excess indentation on headings and descriptions, added blank-line separators

### Changed
- Extracted `_ensure_provider_loaded` from `review_client.py` to shared `providers/loader.py` as public `ensure_provider_loaded()` (slice 145)

### Previous
- Three utility actions for the pipeline system (slice 144)
  - `CfOpAction` in `pipeline/actions/cf_op.py` — delegates `set_phase`, `build_context`, `summarize` to ContextForge CLI via `cf_client._run()`
  - `CommitAction` in `pipeline/actions/commit.py` — stages files and creates git commits with semantic messages; returns `committed=False` on clean working tree
  - `DevlogAction` in `pipeline/actions/devlog.py` — appends structured entries to DEVLOG.md; auto-generates content from `prior_outputs` or accepts explicit content; handles date header deduplication
  - All three satisfy the `Action` protocol and auto-register at import time
- Structured review findings in YAML frontmatter (slice 143)
  - `StructuredFinding` dataclass in `review/models.py` — machine-readable finding with `id`, `severity`, `category`, `summary`, `location`
  - `NOTE` severity level added to `Severity` enum (between PASS and CONCERN)
  - `ReviewResult.structured_findings` computed property derives structured findings from parsed findings
  - Parser extracts `category:` and `location:` tags from finding blocks; strips tags from description
  - Review frontmatter now includes `findings:` array with structured finding entries
  - JSON output (`to_dict()`) includes `structured_findings` array and `category`/`location` on findings
  - Structured output instructions injected into all review template system prompts
- `src/squadron/pipeline/` package — foundational scaffolding for the pipeline system (slice 142)
  - `pipeline/models.py`: `ActionContext`, `ActionResult`, `PipelineDefinition`, `StepConfig`, `ValidationError` dataclasses
  - `pipeline/actions/`: `Action` protocol (`@runtime_checkable`), `ActionType` StrEnum, action registry (`register_action`, `get_action`, `list_actions`)
  - `pipeline/steps/`: `StepType` protocol, `StepTypeName` StrEnum, step-type registry
  - `pipeline/resolver.py`: `ModelResolver` with 5-level cascade (CLI → action → step → pipeline → config default); delegates to `resolve_model_alias()`; raises `ModelPoolNotImplemented` on `pool:` prefix (160 scope stub)
  - Stub modules for all future action/step-type files

### Fixed
- SDK reviews (Claude/Anthropic) no longer duplicate findings — `ResultMessage` content was being appended alongside the identical `AssistantMessage`

### Changed
- Built-in model aliases moved from Python dict `BUILT_IN_ALIASES` to `src/squadron/data/models.toml` (same TOML format as user `~/.config/squadron/models.toml`)
- Built-in review templates moved from `src/squadron/review/templates/builtin/` to `src/squadron/data/templates/`
- Added `src/squadron/data/` as canonical location for all shipped default data files; `data_dir()` utility resolves path in both wheel and editable installs
- Reserved `src/squadron/data/pipelines/` for pipeline definitions (slice 148)

## [0.2.12] - 20260328

### Added
- `SQUADRON_APP_NAME` env var support — when set, passed as `user` field in OpenAI-compatible requests; visible in OpenRouter traces and Langfuse dashboards

## [0.2.11] - 20260328

### Added
- `sq review arch` command — standalone architecture review using `arch.yaml` template, reviews documents on their own merits without `--against` (replaces deprecated redirect to `review slice`)
- Initiative index shorthand for arch reviews: `sq review arch 140` resolves to the matching architecture document
- Per-template default model config keys: `default_model_arch`, `default_model_slice`, `default_model_tasks`, `default_model_code` (override `default_model` per review type)
- `sq config unset` command for removing config keys, reverting to defaults
- `arch.yaml` built-in review template for architecture document evaluation

### Changed
- Model resolution cascade extended: CLI flag > per-template config > global config > template default

## [0.2.7]

### Added
- **[Experimental]** Codex provider — `CodexProvider`/`CodexAgent` via Codex Python SDK (slice 128). Requires separate Codex SDK install.
- `ProviderCapabilities` on `AgentProvider` protocol — `can_read_files`, `supports_system_prompt`, `supports_streaming`
- `ProviderType`, `ProfileName`, `AuthType` enums — all identifier strings in one place
- `openai-oauth` profile and `codex-agent`/`codex-spark` model aliases
- Review finding parser extended to match five formats: `### [SEV]`, `### SEV`, `### SEV:`, `**[SEV]**`, `- [SEV]` (slice 122)
- Lenient fallback parsing for CONCERNS/FAIL verdicts with no structured findings
- Auto-detection of language rules in `review code`; template-specific rule injection
- `--rules-dir` / `--no-rules` options on review commands; `rules_dir` config key
- Scoped `sq review code` diff — auto-resolves to slice branch commits via merge-base detection (slice 127)
- `-vvv` debug output: system prompt, user prompt, and injected rules printed to stderr; prompt log saved to `~/.config/squadron/logs/`

### Changed
- Review system unified through `Agent.handle_message()` — no more direct SDK/OpenAI calls in `review_client.py` (slice 128)
- File injection in reviews gated on `provider.capabilities.can_read_files` instead of hardcoded profile identity
- `SDKAgent` → `ClaudeSDKAgent`, `SDKAgentProvider` → `ClaudeSDKProvider`

### Removed
- `src/squadron/review/runner.py` — absorbed into `ClaudeSDKAgent.handle_message()`

## [0.2.6] - 20260325

### Added
- `ContextForgeClient` in `src/squadron/integrations/context_forge.py` — typed interface to Context Forge CLI with `list_slices()`, `list_tasks()`, `get_project()`, `is_available()` (slice 126)
- Typed dataclasses for CF responses: `SliceEntry`, `TaskEntry`, `ProjectInfo`
- Custom exceptions `ContextForgeNotAvailable` and `ContextForgeError` replacing inline `typer.Exit` in CF calls

### Changed
- Migrated `review.py` from direct `subprocess.run(["cf", ...])` calls to `ContextForgeClient`
- Removed `_run_cf()` helper and `subprocess` import from `review.py`
- Updated markdown command files to CF's new command surface (`cf list slices --json`, `cf list tasks --json`)

### Fixed
- Config `default_model` now goes through alias resolution — previously only `--model` CLI flag was resolved, causing UNKNOWN verdict when using config defaults

## [0.2.5] - 20260323

### Fixed
- `.env` file loading now uses explicit `Path.cwd() / ".env"` instead of `find_dotenv()` which walked up from the package install location

## [0.2.4] - 20260323

### Added
- Load API keys from `.env` file at CLI startup via `python-dotenv`

## [0.2.3] - 20260323

### Added
- Model alias metadata: `ModelPricing` type, `cost_tier`, `private`, `notes` fields on `ModelAlias` (slice 121)
- `estimate_cost()` utility for per-token cost estimation
- `-v`/`--verbose` flag on `sq models` to display metadata and pricing columns
- Metadata and pricing parsing from user `models.toml`

### Changed
- Single-source version via `importlib.metadata.version()` instead of hardcoded `__version__`

### Fixed
- Tests made resilient to built-in alias data changes

## [0.2.2] - 20260322

### Changed
- Unified `sq model` and `sq models` into single `sq models` command

## [0.2.1] - 20260321

### Added
- Model alias metadata slice plan entry (slice 136/121)
- README updates with model aliases, slice reviews, and version info

### Fixed
- Line-too-long lint errors in test files

## [0.2.0] - 20260321

### Added
- Model alias registry with built-in defaults and user overrides at `~/.config/squadron/models.toml` (slice 120)
- `sq model list` command for viewing available aliases
- Content injection for non-SDK reviews: git diff and glob results injected into prompts
- File content injection into prompts for non-SDK reviews
- Review provider and model selection: `--profile` flag on all `sq review` commands (slice 119)
- User-customizable review templates from `~/.config/squadron/templates/`

### Changed
- Renamed `review arch` to `review slice` for clarity

## [0.1.1] - 20260321

### Added
- Composed workflow commands: `/sq:run-slice` automating full slice lifecycle (slice 118)
- Bare number shorthand for `sq review slice 118`, `sq review tasks 118`
- Auto-save review files when using slice number shorthand
- Context Forge path resolution for slice/task/architecture documents

### Fixed
- Removed `raw_output` from `ReviewResult.to_dict()` serialization
- Removed raw output display from review terminal and saved files

## [0.1.0] - 20260217

### Added
- Initial release published to PyPI as `squadron-ai`
- CLI entry point `sq` with commands: `spawn`, `list`, `task`, `shutdown`
- SDK Agent Provider wrapping Claude Agent SDK (slice 101)
- Agent Registry with lifecycle management (slice 102)
- CLI Foundation with SDK agent tasks (slice 103)
- Review workflow templates: slice, tasks, code reviews (slice 105)
- M1 Polish: verbosity levels, persistent config, text colors, `--rules` flag (slice 106)
- OpenAI-compatible provider with Chat Completions API support (slice 111)
- Local daemon with FastAPI, Unix socket transport (slice 112)
- Provider variants: OpenRouter, local models, Gemini-via-compatible (slice 113)
- Auth strategy with API key management, `auth login`, `auth status` (slice 114)
- Project renamed from `orchestration` to `squadron` (slice 115)
- Claude Code slash commands via `sq install-commands` (slice 116)
- GitHub Actions CI workflow, PyPI publishing on tag (slice 117)
- `--version` flag on CLI
