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
