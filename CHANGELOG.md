---
docType: changelog
scope: project-wide
---

# Changelog

All notable changes to Squadron will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

## [Unreleased]

### Added
- `ProviderCapabilities` dataclass on `AgentProvider` Protocol — `can_read_files`, `supports_system_prompt`, `supports_streaming` (slice 128)
- `ProviderType`, `ProfileName`, `AuthType` enums in `providers/base.py` — all identifier strings defined in one place (slice 128)
- `OAuthFileStrategy` in `providers/codex/auth.py` — subscription-first credential resolution from `~/.codex/auth.json` or `OPENAI_API_KEY` fallback (slice 128)
- **[Experimental]** `CodexProvider` and `CodexAgent` in `providers/codex/` — agentic provider via Codex Python SDK (slice 128). Requires separate install of the official OpenAI Codex SDK from GitHub and `codex` CLI via npm. See README for setup.
- `openai-oauth` built-in profile with OAuth auth type for subscription-auth agent tasks (slice 128)
- `codex-agent` and `codex-spark` model aliases (slice 128)
- `from_config` classmethod, `active_source`, `setup_hint` on all auth strategies (slice 128)
- `resolve_auth_strategy_for_profile()` convenience function for CLI auth status (slice 128)

### Changed
- Review system unified: all reviews route through `Agent.handle_message()` via provider registry — no more direct `AsyncOpenAI` or `ClaudeSDKClient` usage in `review_client.py` (slice 128)
- `SDKAgent` renamed to `ClaudeSDKAgent`, `SDKAgentProvider` renamed to `ClaudeSDKProvider` (slice 128)
- `resolve_auth_strategy()` now uses registry-driven dispatch via `from_config` — no if/elif chains on auth type strings (slice 128)
- `sq auth status` and `sq auth login` delegate to auth strategies — no string dispatch on profile names or auth types (slice 128)
- File injection in reviews now conditional on `provider.capabilities.can_read_files` instead of profile identity (slice 128)

### Removed
- `src/squadron/review/runner.py` — SDK review logic absorbed into `ClaudeSDKAgent.handle_message()` (slice 128)
- `_run_non_sdk_review()` and `_resolve_api_key()` from `review_client.py` (slice 128)

### Added
- Expanded `_FINDING_RE` in `parsers.py` to match five finding formats: `### [SEV]`, `### SEV`, `### SEV:`, `**[SEV]**`, and `- [SEV]` (slice 122)
- Lenient fallback parsing: when verdict is CONCERNS/FAIL but no structured findings parsed, attempt paragraph extraction then synthesize a finding from summary text
- `fallback_used: bool` field on `ReviewResult` (default `False`) — set when fallback parsing triggered
- Diagnostic debug log at `~/.config/squadron/logs/review-debug.jsonl` — written on verdict/findings mismatches
- `CRITICAL` consistency block in all three builtin review templates (slice, tasks, code)
- `src/squadron/review/rules.py` — `resolve_rules_dir()`, `load_rules_frontmatter()`, `detect_languages_from_paths()`, `match_rules_files()`, `load_rules_content()`, `get_template_rules()`
- Auto-detection of language rules in `review code` from diff/files paths, matched against rules dir frontmatter
- Template-specific rule injection: `rules/review.md` and `rules/review-{template}.md` prepended to system prompt
- `--rules-dir` option on all three review commands; `--no-rules` flag on `review code`
- `rules_dir` config key for default rules directory
- Review file YAML alignment: added `layer: project`, `sourceDocument`, `aiModel` (resolved model ID), `status: complete` fields
- `-vvv` debug output: at verbosity >= 3, prints `[DEBUG] System Prompt:`, `[DEBUG] User Prompt:`, and `[DEBUG] Injected Rules:` to stderr before API call

- `src/squadron/review/git_utils.py` — `_find_slice_branch()`, `_find_merge_commit()`, `resolve_slice_diff_range()` for scoped slice diff resolution (slice 127)
- Prompt log persistence: `-vvv` writes full prompt to `~/.config/squadron/logs/review-prompt-{timestamp}.md` and prints path to stderr (slice 127)
- `system_prompt`, `user_prompt`, `rules_content_used` optional fields on `ReviewResult` — populated at verbosity >= 2 (slice 127)
- Debug appendix `## Debug: Prompt & Response` in saved review markdown when prompt fields present (slice 127)

### Changed
- `run_review_with_profile()` accepts `verbosity: int = 0` and threads it through to `_run_non_sdk_review()`
- `sq review code 122` now auto-scopes diff to slice 122's branch commits via merge-base or merge-commit detection, instead of diffing against all of main (slice 127)

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
