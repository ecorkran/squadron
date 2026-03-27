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
