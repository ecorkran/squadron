---
docType: devlog
project: squadron
dateCreated: 20260218
dateUpdated: 20260324
---

# Development Log

A lightweight, append-only record of development activity. Newest entries first.
Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).

---

## 20260324

### Slice 126: Context Forge Integration Layer — Design Complete

- Created `project-documents/user/slices/126-slice.context-forge-integration-layer.md`
- `ContextForgeClient` class in `src/squadron/integrations/context_forge.py` — typed methods replacing scattered `subprocess.run(["cf", ...])` calls
- Typed return dataclasses: `SliceEntry`, `TaskEntry`, `ProjectInfo`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) separated from CLI layer
- Adapts to CF's new command surface (`cf list slices --json` replacing `cf slice list --json`)
- Markdown command files updated to reference new CF command names
- Scope limited to abstraction and migration — MCP transport, command aliasing deferred

### Slice 122: Review Context Enrichment — Design Complete

- Created `project-documents/user/slices/122-slice.review-context-enrichment.md`
- Two-pronged scope: (1) fix verdict/findings inconsistency (issue #5) via prompt hardening + parser post-processing guard, (2) auto-detect and inject language-specific rules for code reviews
- Language detection from diff file paths or glob matches, matched against rules files' `paths` frontmatter globs
- Rules directory resolution: `--rules-dir` flag > config `rules_dir` > `{cwd}/rules/` > `{cwd}/.claude/rules/`
- Slice/task reviews inject `rules/general.md` if present
- `--no-rules` flag to suppress all rule injection
- Legacy P0-P3 priorities extracted as optional copyable rules file, not baked into templates

## 20260323

### .env support for API keys

Added `python-dotenv` dependency. `load_dotenv()` runs at CLI startup (`cli/app.py`), so API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, etc.) can be set in a `.env` file instead of exported in the shell. `.env` already gitignored.

### Slice 121: Model Alias Metadata — Implementation Complete

- All 12 tasks (T1-T12) complete. 537 tests pass, pyright/ruff/format clean.
- `ModelPricing` TypedDict (input, output, cache_read, cache_write — USD per 1M tokens)
- `ModelAlias` extended with `private`, `cost_tier`, `notes`, `pricing` — all optional via inheritance pattern (`_ModelAliasRequired` base + `total=False`)
- All 12 `BUILT_IN_ALIASES` populated with curated metadata and pricing
- `load_user_aliases()` extracts metadata and pricing from TOML (inline and sub-table formats)
- `estimate_cost()` utility: alias name + token counts → USD float or None
- `sq models` compact by default; `sq models -v` shows Private, Cost, In $/1M, Out $/1M, Notes columns
- 21 new tests across T4 (3), T6 (6), T8 (6), T10 (6)

## 20260322

### Slice 121: Model Alias Metadata — Task Breakdown Complete

Task file at `project-documents/user/tasks/121-tasks.model-alias-metadata.md` (12 tasks: T1-T12). Three workstreams: type extensions with built-in metadata (T1-T4), TOML parsing and cost estimation (T5-T8), display updates and validation (T9-T12). Test-with pattern: each implementation task followed immediately by its test task.

### Slice 121: Model Alias Metadata — Design Complete

- Created `project-documents/user/slices/121-slice.model-alias-metadata.md`
- Extends `ModelAlias` TypedDict with optional `private` (bool), `cost_tier` (str), `notes` (str), `pricing` (ModelPricing) fields
- `ModelPricing` TypedDict: `input`, `output`, `cache_read`, `cache_write` (USD per 1M tokens)
- `total=False` on TypedDict for backward-compatible optional fields
- `cost_tier` values: free, cheap, moderate, expensive, subscription (new — for Max sub models)
- `estimate_cost()` utility: pure function, alias name + token counts → USD or None
- `sq models` gains Private, Cost, In $/1M, Out $/1M, Notes columns with compact mode
- Curated metadata and pricing for all 12 built-in aliases
- Also in this session: slice plan refactored (100-series trimmed, 160-series created for multi-agent), reindexing (161-172, 121-125), test fixes, template clarification, architecture docs updated to squadron naming

## 20260321

### Slice 120: Model Alias Registry — Implementation Complete

- All 22 tasks (T1-T22) complete. 514 tests pass, pyright/ruff clean.
- `review arch` renamed to `review slice` with backward-compat hidden alias + deprecation notice
- `src/squadron/models/aliases.py`: `resolve_model_alias()` with built-in defaults (opus, sonnet, haiku, gpt4o, o3, o1) and user `~/.config/squadron/models.toml` override
- `_infer_profile_from_model()` removed — alias registry handles all model→profile inference
- `_inject_file_contents()` in `review_client.py`: reads file contents and appends to prompt for non-SDK reviews; handles git diff and glob patterns for code reviews; size limits (100KB/file, 500KB total)
- `sq model list` command showing built-in + user aliases in a rich table
- 5 commits on branch `120-model-alias-registry`
- Post-impl live tests remain for PM (alias resolution, content injection, diff injection)

### Slice 120: Model Alias Registry — Task Breakdown Complete

Task file at `project-documents/user/tasks/120-tasks.model-alias-registry.md` (22 tasks: T1-T22). Three workstreams: rename review arch→slice (T1-T5), model alias registry with wiring (T6-T10), content injection for non-SDK reviews including code review diff/files (T11-T16), plus model list CLI (T17-T19) and slash command updates (T20-T22). Post-impl: live tests with OpenRouter, alias customization, diff injection.

### Slice 120: Model Alias Registry — Design Complete

- Slice design at `project-documents/user/slices/120-slice.model-alias-registry.md`
- Two problems addressed: (1) hardcoded model inference replaced by data-driven alias registry in `models.toml`, (2) non-SDK reviews fail because prompts contain file paths but models can't read files — content injection adds file contents to prompt for non-SDK path
- Ships built-in aliases (opus, sonnet, gpt4o, etc.) + user `~/.config/squadron/models.toml`
- Content injection: auto-reads files from `inputs` dict, appends to prompt; handles git diff for code reviews; 100KB/file, 500KB total limits
- New `sq model list` command

### Slice 119: Review Provider & Model Selection — Implementation Complete

- All 20 implementation tasks (T1-T20) complete. 491 tests pass.
- New `review_client.py` with `run_review_with_profile()` — SDK delegation or OpenAI-compatible API path
- `--profile` flag on all `sq review` commands (arch, tasks, code)
- `_resolve_profile()`: CLI flag → model inference → template → config → sdk fallback
- `_infer_profile_from_model()`: opus→sdk, gpt-4o→openai, slash→openrouter
- `load_all_templates()` loads from built-in + `~/.config/squadron/templates/` (user override by name)
- `default_review_profile` config key added
- Slash commands updated with `--profile` documentation
- Slice 120 (Model Alias Registry) added to slice plan as next priority
- Post-impl live tests remain for PM

### Slice 119: Review Provider & Model Selection — Task Breakdown Complete

Task file created at `project-documents/user/tasks/119-tasks.review-provider-model-selection.md` (20 tasks: T1-T20). Key task groups: template profile field (T1-T2), config key + profile resolution (T3-T7), review client with provider routing (T9-T10), CLI `--profile` flag (T12-T13), user template loading (T15-T16), slash command updates (T18), validation (T19-T20). Post-impl: live tests with OpenRouter, OpenAI, user templates, config defaults.

### Slice 119: Review Provider & Model Selection — Design Complete

- Slice design created at `project-documents/user/slices/119-slice.review-provider-model-selection.md`
- Scope: decouple review execution from hardcoded Claude SDK. Add `--profile` flag, `profile` field in templates, user-customizable templates from `~/.config/squadron/templates/`, config default `default_review_profile`, model-to-profile inference
- Key decision: SDK path preserved exactly (delegation), non-SDK path uses `AsyncOpenAI` directly via existing profile/auth infrastructure
- Known limitation: non-SDK reviews have no tool access (prompt-only)
- Slice plan updated: new slice 119 inserted, old 119 (Conversation Persistence) re-indexed to 134

---

## 20260320

### Slice 118: Claude Code Commands — Composed Workflows — In Progress

- Implementation complete (T1-T9 checked off). Remaining items are PM manual tests.
- Commits:
  - `a2058c9` feat: add /sq:run-slice command, update review commands with number shorthand
  - `f31cd44` test: update install tests for 9 command files
- What works: all 448 tests pass, ruff/pyright clean, wheel bundles `run-slice.md`, install produces 9 commands
- Scope expanded from original design:
  - Updated `review-tasks.md`, `review-code.md`, `review-arch.md` with bare number shorthand (e.g., `/sq:review-tasks 191`)
  - Path resolution via `cf slice list --json` / `cf task list --json` — worktree-aware, CF owns conventions
  - `review-arch` performs holistic check: slice design vs. architecture doc + slice plan entry
  - Review file persistence to `project-documents/user/reviews/` with YAML frontmatter
  - DEVLOG entry step added to `run-slice` pipeline (Step 5)
- Pending: PM live tests (`/sq:run-slice` on real slice, `/sq:review-tasks {nnn}` shorthand), prompt iteration

---

## 20260317

### Slice 118: Claude Code Commands — Composed Workflows — Task Breakdown Complete

Task file created at `project-documents/user/tasks/118-tasks.claude-code-commands-composed-workflows.md` (6 tasks: T1-T6). T1 create `run-slice.md` command file with full pipeline prompt. T2 update install tests (8→9 expected files). T3 commit. T4 validation pass. T5 commit. T6 verify wheel bundling. Post-impl: live test on a real slice, iterate on prompt.

### Slice 118: Claude Code Commands — Composed Workflows — Design Complete

Slice design created at `project-documents/user/slices/118-slice.claude-code-commands-composed-workflows.md`.

Scope: Single `/sq:run-slice` command that automates the full slice lifecycle — phase 4 (design) → phase 5 (task breakdown + review) → compact → phase 6 (implementation + code review). Chains `cf set/build` with `sq review tasks/code` and `/compact`. Review gates: PASS proceeds, FAIL stops for human input. Smart resume (skip completed phases) documented as future enhancement. Lives in existing `sq/` namespace — no new directories or Python code.

---

## 20260307

### Slice 117: PyPI Publishing & Global Install — Task Breakdown Complete

Task file created at `project-documents/user/tasks/117-tasks.pypi.md` (13 tasks: T1-T13). T1-T2 version flag + test, T3 commit. T4-T5 metadata polish + wheel verification, T6 commit. T7-T8 GitHub Actions CI (test + publish jobs), T9 commit. T10 README install section, T11 commit. T12-T13 validation pass + commit. Post-implementation section documents manual PM steps (PyPI account, first publish, smoke test).

---

## 20260306

### Slice 117: PyPI Publishing & Global Install — Design Complete

Slice design created at `project-documents/user/slices/117-slice.pypi.md`.

Scope: Publish `squadron` to PyPI for global install via `pipx install squadron` / `uv tool install squadron`. SemVer versioning (start at 0.1.0, single-sourced in pyproject.toml). `sq --version` via `importlib.metadata`. pyproject.toml metadata polish (classifiers, license, project-urls). GitHub Actions CI workflow (lint+test on push, publish to TestPyPI+PyPI on version tag). README install instructions.

Key decisions: SemVer over CalVer, tag-driven manual releases, `pypa/gh-action-pypi-publish` with OIDC trusted publisher preferred, TestPyPI dry-run before real publish, `astral-sh/setup-uv` for CI.

### Slice 116: Claude Code Commands — Implementation Complete

All 15 tasks complete. Eight command files in `commands/sq/` (`spawn.md`, `task.md`, `list.md`, `shutdown.md`, `review-arch.md`, `review-tasks.md`, `review-code.md`, `auth-status.md`). `pyproject.toml` updated with `force-include` for wheel bundling. `install.py` with `install_commands`/`uninstall_commands` wired into Typer app. 11 tests (8 install/uninstall + 3 source verification). 446 total tests pass, pyright clean, ruff clean.

---

## 20260305

### Slice 116: Claude Code Commands — sq Wrappers — Design Complete

Slice design created at `project-documents/user/slices/116-slice.sq-slash-command.md`.

Scope: Eight Claude Code slash command files (`/sq:spawn`, `/sq:task`, `/sq:list`, `/sq:shutdown`, `/sq:review-arch`, `/sq:review-tasks`, `/sq:review-code`, `/sq:auth-status`) in `commands/sq/`. Install/uninstall CLI commands (`sq install-commands`, `sq uninstall-commands`). Command files bundled in package wheel via `pyproject.toml`. Commands are thin prompts that instruct Claude to execute the corresponding `sq` CLI command via Bash.

### Slice 116: Claude Code Commands — Task Breakdown Complete

Task file created at `project-documents/user/tasks/116-tasks.sq-slash-command.md` (15 tasks). T1 directory setup, T2-T9 command file authoring (one per command), T10 package bundling, T11-T12 install/uninstall CLI, T13-T14 tests, T15 validation.

---

### Slice 115: Project Rename — orchestration → squadron — Complete

- Renamed `src/orchestration/` → `src/squadron/`, updated pyproject.toml (name, dual entry points: `sq` + `squadron`)
- Updated all imports across 127 .py files (61 src + 66 tests)
- Config paths: `~/.config/squadron/`, `.squadron.toml`, `~/.squadron/` for daemon
- Added config migration logic in `config/manager.py` — copies old config dir on first run, writes `MIGRATED.txt`
- Renamed `OrchestrationEngine` → `SquadronEngine`
- Updated README.md, docs/COMMANDS.md, docs/TEMPLATES.md
- 435 tests pass, `sq --help` and `squadron --help` both work

---

## 20260301

### Slice 114: Auth Strategy & Credential Management — Implementation Complete

Implemented all 18 tasks for slice 114. Added `AuthStrategy` protocol and `ApiKeyStrategy` in `providers/auth.py` — direct extraction of existing credential resolution from `OpenAICompatibleProvider`, same behavior. Added `resolve_auth_strategy()` factory and `AUTH_STRATEGIES` registry. Extended `ProviderProfile` with `auth_type` field (default `"api_key"`). Refactored `OpenAICompatibleProvider.create_agent()` to delegate to the strategy. Added `orchestration auth login <profile>` and `orchestration auth status` CLI commands. 435 tests pass; pyright and ruff clean.

New files: `src/orchestration/providers/auth.py`, `src/orchestration/cli/commands/auth.py`, `tests/providers/test_auth.py`, `tests/providers/test_auth_resolution.py`, `tests/cli/test_auth.py`.

---

### Slice 114: Auth Strategy & Credential Management — Design Complete

Research into OpenAI OAuth revealed the API has no general OAuth2 flow — authentication is purely key-based (project-scoped, service account). OAuth exists only for Codex subscription access (browser-based, ChatGPT Plus/Pro/Teams). This finding reshaped slice 114 from "implement OAuth" to "formalize auth strategy abstraction with API key as concrete implementation."

Documents created:
- `project-documents/user/slices/114-slice.oauth-advanced-auth.md` — slice design
- Updated `100-slices.orchestration-v2.md` — revised slice 114 entry, new slice 116 (Codex Agent Integration)

Key decisions:
- `AuthStrategy` protocol with `get_credentials()`, `refresh_if_needed()`, `is_valid()`
- `ApiKeyStrategy` as direct extraction of existing provider credential resolution
- `auth_type` field on `ProviderProfile` for strategy dispatch
- CLI `auth login`/`auth status` commands for credential validation
- Codex agent integration (OAuth) deferred to new slice 116

Scope: `AuthStrategy` protocol, `ApiKeyStrategy`, `ProviderProfile.auth_type`, CLI auth commands, provider refactor

| Hash | Description |
|------|-------------|
| `156d78f` | docs: add slice 114 design (auth strategy) and slice 116 entry (codex) |

---

### Slice 113: Provider Variants & Registry — Post-Merge Fix

Live testing with OpenRouter/Kimi revealed `credentials` dropped at daemon boundary. `SpawnRequest` was missing the field; fixed in `server/models.py` and `routes/agents.py`. Verified working end-to-end with OpenRouter profile.

| Hash | Description |
|------|-------------|
| `146ed4b` | fix: pass credentials through SpawnRequest to AgentConfig |

---

## 20260228

### Slice 113: Provider Variants & Registry — Complete

All 15 tasks implemented across 4 groups. 408 tests passing (31 new). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `b1831c0` | feat: add provider profile model and TOML loading |
| `7eb9eff` | feat: enhance credential resolution and default headers support |
| `45ec6b8` | feat: add --profile flag to spawn and models command |

**What works:**
- `ProviderProfile` frozen dataclass with 4 built-ins: `openai`, `openrouter`, `local`, `gemini`
- TOML loading from `~/.config/orchestration/providers.toml`; user profiles override built-ins
- Credential resolution chain: `config.api_key` → profile env var → `OPENAI_API_KEY` → localhost placeholder
- OpenRouter `default_headers` via `AsyncOpenAI(default_headers=...)` constructor
- `orchestration spawn --profile openrouter --model x` fully functional
- `orchestration models --profile local` for model discovery (direct HTTP, no daemon)

**Key decisions:**
- Profiles are data (frozen dataclass), not subclasses — all three variants reuse `OpenAICompatibleProvider`
- Localhost placeholder: `"not-needed"` when no API key and `base_url` starts with `http://localhost` or `http://127.0.0.1`
- `models` command calls `/v1/models` directly via `httpx`, bypassing daemon

**Next:** Slice 114 (OAuth & Advanced Auth)

---

### Slice 113: Provider Variants & Registry — Phase 4 Design Complete

Slice design created at `project-documents/user/slices/113-slice.provider-variants.md`.

Key design decisions:
- **Profiles, not subclasses**: All three variants (OpenRouter, local, Gemini) are configurations of `OpenAICompatibleProvider`, bundled as named `ProviderProfile` entries.
- **Separate `providers.toml`**: Structured profile data lives in its own file (`~/.config/orchestration/providers.toml`), not in the flat `config.toml`.
- **`--profile` CLI flag**: New flag on spawn command, separate from `--provider`. Profile provides defaults; CLI flags override.
- **Localhost auth bypass**: Local model servers get a placeholder API key (`"not-needed"`) instead of raising `ProviderAuthError`.
- **`models` command**: Direct HTTP query to `/v1/models` for model discovery, bypasses daemon.

| Hash | Description |
|------|-------------|
| `e399e5f` | docs: add slice 113 design |

### Slice 112: Local Server & CLI Client — Phase 7 Implementation Complete

All 27 tasks (T1-T27) implemented. 35 new tests (377 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `e8350b2` | chore: add httpx dependency |
| `46c4380` | feat: add test infrastructure for server and client (T2) |
| `ae55e8b` | feat: implement OrchestrationEngine (T3) |
| `5301aa5` | test: add OrchestrationEngine tests (T4) |
| `d0591f6` | feat: add server models and health route (T5) |
| `73acbd8` | feat: add agent CRUD and messaging routes (T6) |
| `4a0dccb` | feat: add app factory and route tests (T7, T8) |
| `51b6f3d` | feat: add daemon module with PID management (T9) |
| `f6c74af` | feat: server core checkpoint (T11) |
| `48a5068` | feat: add DaemonClient (T12-T14) |
| `1733974` | feat: add serve command (T15-T16) |
| `c908121` | refactor: CLI commands use DaemonClient (T17-T20) |
| `2079bfd` | feat: add message and history commands (T21-T23) |
| `1de8866` | feat: validation pass and format fixes (T25) |
| `ca8b1f5` | test: add daemon integration test (T26-T27) |

**New modules:**
- `src/orchestration/server/engine.py` — OrchestrationEngine with agent lifecycle and conversation history
- `src/orchestration/server/models.py` — Pydantic request/response schemas
- `src/orchestration/server/routes/` — FastAPI agent CRUD, messaging, and health routes
- `src/orchestration/server/app.py` — Application factory
- `src/orchestration/server/daemon.py` — PID management, signal handling, dual-transport server
- `src/orchestration/client/http.py` — DaemonClient with Unix socket / HTTP transport
- `src/orchestration/cli/commands/serve.py` — `orchestration serve` with --status/--stop
- `src/orchestration/cli/commands/message.py` — `orchestration message`
- `src/orchestration/cli/commands/history.py` — `orchestration history` with --limit

**Refactored modules:**
- `spawn.py`, `list.py`, `task.py`, `shutdown.py` — all use DaemonClient instead of direct registry

**Next:** Slice 113 (Provider Variants & Registry).

---

### Slice 112: Local Server & CLI Client — Slice Design Complete

**Documents created:**
- `user/slices/112-slice.local-daemon.md` — slice design
- `user/slices/112-slice.local-daemon-agent-brief.md` — technical brief from PM

**Scope:** Persistent daemon process (`orchestration serve`) holding agent registry, agent instances, and conversation history in memory. CLI commands become thin clients communicating with daemon via Unix domain socket (primary) or localhost HTTP (secondary). New `OrchestrationEngine` composes existing `AgentRegistry` and adds conversation history tracking. FastAPI app serves both transports. New commands: `serve`, `message`, `history`. Existing commands (`spawn`, `list`, `task`, `shutdown`) refactored to use `DaemonClient`.

**Key design decisions:**
- `OrchestrationEngine` composes `AgentRegistry` (not subclass/replace) — registry manages lifecycle, engine adds history and coordination
- Dual transport: Unix socket (`~/.orchestration/daemon.sock`) for CLI, HTTP (`127.0.0.1:7862`) for external consumers — same FastAPI app serves both via two uvicorn instances
- `httpx.AsyncHTTPTransport(uds=path)` for CLI→daemon Unix socket communication
- Explicit `orchestration serve` — no auto-start magic, predictable daemon lifecycle
- All agent commands route through daemon — one execution path, enables future observability
- Conversation history at engine level (not just agent-internal) — provider-agnostic, supports `history` command
- Agent lifecycle categories: ephemeral (task) and session (spawn+message) — behavioral patterns, not formal types
- PID file + socket file in `~/.orchestration/` — stale file detection on startup
- `review` and `config` commands left unchanged for now (review uses SDK directly, config is stateless)

**Commit:** `dcab7a9` docs: add slice 112 design for local daemon & CLI client

**Next:** Phase 5 (Task Breakdown) on slice 112.

---

## 20260226

### Slice 111: OpenAI-Compatible Provider Core — Phase 7 Implementation Complete

All 17 tasks (T1-T17) implemented. 41 new tests (342 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `3965380` | chore: add openai>=1.0.0 dependency |
| `b4d1da9` | feat: add OpenAI provider translation module with tests |
| `c53c64c` | feat: add OpenAICompatibleProvider with tests |
| `fba88e6` | feat: implement OpenAICompatibleAgent with tests |
| `ab12531` | feat: add OpenAI-compatible provider |
| `4c547c7` | feat: add provider auto-loader and --base-url to spawn command |

**What was added:**
- `providers/openai/` package: `translation.py`, `provider.py`, `agent.py`, `__init__.py`
- `OpenAICompatibleProvider`: API key resolution (config → env → ProviderAuthError), `AsyncOpenAI` client construction, `base_url` pass-through, explicit `ProviderError` on missing model
- `OpenAICompatibleAgent`: conversation history, streaming accumulation, tool call reconstruction by chunk index, full error mapping (AuthenticationError→ProviderAuthError, RateLimitError→ProviderAPIError(429), APIStatusError→ProviderAPIError(status_code), APIConnectionError→ProviderError, APITimeoutError→ProviderTimeoutError)
- `translation.py`: `build_text_message`, `build_tool_call_message`, `build_messages` — pure functions, independently testable
- Auto-registration: `get_provider("openai")` available after import
- `_load_provider(name)` auto-loader in `spawn.py` — lazy `importlib.import_module` triggers provider registration; silent `ImportError` catch; benefits all providers retroactively
- `--base-url` flag on `spawn` command — passed through to `AgentConfig.base_url`

**Architecture note:** Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns. Accumulate full stream then yield complete `Message` objects to preserve `AsyncIterator[Message]` Protocol contract. Validated that `AgentProvider` Protocol generalizes beyond Anthropic with zero core engine changes.

**Issues logged:** None.

**Next:** Slice 112 (Provider Variants & Registry — OpenRouter, local, Gemini configs + model alias profiles).

### Slice 111: OpenAI-Compatible Provider Core — Slice Design Complete

**Documents created:**
- `user/slices/111-slice.openai-provider-core.md` — slice design (410 lines)

**Scope:** `OpenAICompatibleProvider` and `OpenAICompatibleAgent` using the `openai` Python SDK's `AsyncOpenAI` client with `base_url` override. Single implementation covers OpenAI, OpenRouter, Ollama/vLLM, and Gemini-compatible endpoints. Validates that `AgentProvider` Protocol generalizes beyond Anthropic with no core engine changes. Also fixes provider auto-loader gap in `spawn.py` and adds `--base-url` CLI flag.

**Key design decisions:**
- Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns
- Accumulate full stream response before yielding `Message` objects — preserves `AsyncIterator[Message]` Protocol contract; streaming-through deferred as future evolution
- No silent model default — `ProviderError` if `config.model` is None (billing concern)
- Tool calls surfaced as `system` Messages with metadata; no execution (needs message bus + executor, future slice)
- `_load_provider(name)` auto-loader via `importlib.import_module` in `spawn.py` — silent `ImportError` catch; benefits all current and future providers retroactively
- Model alias / provider profile registry (`codex_53` → openai + model + base_url) deferred to slice 112

**Commit:** `864ed9c` docs: add slice design for 111-openai-provider-core

### Slice 111: OpenAI-Compatible Provider Core — Task Breakdown Complete

Task file created at `project-documents/user/tasks/111-tasks.openai-provider-core.md` (169 lines, 17 tasks). Test-with pattern applied; two commit checkpoints (T11 after providers/openai, T17 after CLI changes).

**Tasks overview:** T1 add dependency → T2 test infra → T3-T4 translation.py → T5-T6 provider.py → T7-T8 agent.py → T9-T10 `__init__.py` registration → T11 commit → T12-T13 auto-loader → T14-T15 `--base-url` flag → T16 full validation → T17 commit.

**Commit:** `5f4a7be` docs: add task breakdown for 111-openai-provider-core

---

## 20260223

### Model selection support (Issue #2)

Added `--model` flag to all review commands and spawn. Model threads through the full pipeline: config key (`default_model`) → ReviewTemplate YAML field → runner → `ClaudeAgentOptions`. Precedence: CLI flag → config → template default → None (SDK default). Template defaults: `opus` for arch/tasks, `sonnet` for code. Model shown in review output panel header at all verbosity levels. 17 new tests (298 total).

**Commit:** `9eae0f7` feat: add model selection support to review and spawn commands

### Rate limit handling fix (Issue #1)

Replaced the retry-entire-session loop (3 retries, 10s delay each) with a `receive_response()` restart on the same session. The SDK's `MessageParseError` (not publicly exported) fires on `rate_limit_event` messages the CLI emits while handling API rate limits internally. Fix catches `ClaudeSDKError` (public parent) with string match, restarts the async generator on the same connected session (anyio channel survives generator death), circuit breaker at 10 retries. Eliminates ~10-20s unnecessary delay. 3 new tests (301 total).

### Post-implementation: code review findings and fixes

Ran `orchestration review code` against its own codebase. Addressed three findings from the review:

1. **`_coerce_value` guard** — added explicit `str` check and `ValueError` for unsupported types (was silently falling through)
2. **Unknown config key warnings** — `load_config` now logs warnings for unrecognized keys in TOML files (catches typos)
3. **Double template loading** — `_execute_review` now accepts `ReviewTemplate` directly instead of re-loading by name
4. **CLAUDE.md exception** — documented that public-facing docs (`docs/`, root `README.md`) are exempt from YAML frontmatter rule

Also added rate-limit retry (3 attempts, 10s delay) in runner and friendlier CLI error message.

**Deferred findings** (logged for future work):
- Duplicated `cli_runner` fixture across 6 test files → promote to root `conftest.py`
- `_resolve_verbosity` can't override config back to 0 from CLI → consider `--quiet` flag

---

## 20260222

### Slice 106: M1 Polish & Publish — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 49 new tests (28 config + 12 verbosity + 6 rules + 3 cwd), 281 total project tests passing. Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `9034843` | feat: add persistent config system with TOML storage |
| `196f03f` | feat: add config CLI commands (set, get, list, path) |
| `b002801` | feat: add verbosity levels and improve text colors |
| `b945fb4` | feat: add --rules flag, config-based cwd, and rules injection |
| `85c953e` | chore: format and fix pyright issues in slice 106 code |
| `eb44cef` | docs: add README, COMMANDS, and TEMPLATES documentation |

**What was added:**
- `config/` package: typed key definitions, TOML load/merge/persist manager, user + project config with precedence
- Config CLI: `config set/get/list/path` commands
- Verbosity levels (0/1/2) with `-v`/`-vv` flags on all review commands
- Text color improvements: bright severity badges, white headings, default foreground body text
- `--rules` flag on `review code` with config-based `default_rules`
- Config-based `--cwd` resolution across all review commands
- Documentation: `docs/README.md`, `docs/COMMANDS.md`, `docs/TEMPLATES.md`

**Architecture note:** `config.py` restructured to `config/__init__.py` package (same pattern as templates in slice 105) to coexist with `keys.py` and `manager.py`. TOML reading via stdlib `tomllib`, writing via `tomli-w`.

### Slice 106: M1 Polish & Publish — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/106-tasks.m1-polish-and-publish.md` (219 lines, 22 tasks).

**Commit:** `09a69cd` docs: add slice 106 task breakdown (m1-polish-and-publish)

### Slice 105: Review Workflow Templates — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 76 review-specific tests, 226 total project tests passing. Zero pyright/ruff errors. Build succeeds.

**Key commits:**
| Hash | Description |
|------|-------------|
| `29c53e2` | feat: add pyyaml dependency |
| `dc8a4a4` | feat: add review result models |
| `fad9109` | feat: add ReviewTemplate, YAML loader, and registry |
| `1d29679` | refactor: restructure templates as package with builtin directory |
| `ea5839d` | feat: add built-in review templates (arch, tasks, code) |
| `a430358` | feat: add review result parser |
| `bff53a0` | feat: add review runner |
| `2feca18` | feat: add review CLI subcommand |
| `74eca88` | chore: review slice 105 final validation pass |

**Architecture note:** `templates.py` moved to `templates/__init__.py` package to coexist with `templates/builtin/` YAML directory. SDK literal types handled via `type: ignore` comments since template values are dynamic from YAML.

### Slice 105: Review Workflow Templates — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/105-tasks.review-workflow-templates.md` (210 lines, 22 tasks). Covers result models, YAML loader/registry, three built-in templates (arch, tasks, code), result parser, review runner, and CLI subcommand. Test-with ordering applied throughout; commit checkpoints after each stable milestone. Merge conflict in slice frontmatter resolved by PM prior to task creation.

---

## 20260220

### Slice 103: CLI Foundation & SDK Agent Tasks — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `8e76a6d` | feat: add Typer app scaffolding and pyproject.toml entry point |
| `4a4a478` | feat: implement CLI commands (spawn, list, task, shutdown) and test infra |
| `faaa5cc` | feat: refactor CLI commands to plain functions + add command tests |
| `b58d539` | feat: add integration smoke test + fix lint/type issues |

**What works:**
- 150 tests passing (22 new + 128 existing), ruff clean, pyright zero errors on src/ and tests/cli/
- `orchestration spawn --name NAME [--type sdk] [--provider P] [--cwd PATH] [--system-prompt TEXT] [--permission-mode MODE]`
- `orchestration list [--state STATE] [--provider P]` — rich table with color-coded state
- `orchestration task AGENT PROMPT` — `handle_message` async bridge, displays text and tool-use summaries
- `orchestration shutdown AGENT` / `orchestration shutdown --all` — individual and bulk with `ShutdownReport`
- `pyproject.toml` entry point registered; `orchestration --help` works
- All commands use `asyncio.run()` bridge pattern (sync Typer → async registry/agent)
- Unit tests: mocked registry via `patch_registry` fixture; integration smoke test: real registry + mock provider

**Key decisions:**
- Commands registered as plain functions via `app.command("name")(fn)` — not sub-typers. Sub-typers created nested groups (`spawn spawn --name`) rather than flat commands (`spawn --name`).
- `task` command uses `agent.handle_message(message)` (the actual Agent Protocol method), not a hypothetical `query()` method referenced in the task design
- `asyncio.run()` per command invocation — no persistent event loop, clean for CLI use
- Integration test patches the provider registry (not the agent registry) to use a mock SDK provider

**Issues logged:** None.

**Next:** Slice 5 (SDK Client Warm Pool).

---

## 20260219

### Slice 103: CLI Foundation & SDK Agent Tasks — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/103-slice.cli-foundation.md` — slice design
- `user/tasks/103-tasks.cli-foundation.md` — 11 tasks, test-with pattern

**Scope:** Typer CLI with four commands (`spawn`, `list`, `task`, `shutdown`) wiring the full path from terminal through Agent Registry and SDK Agent Provider to Claude execution. Async bridge via `asyncio.run()`. Rich output formatting (tables for `list`, styled text for responses). User-friendly error handling for all known failure modes. `pyproject.toml` script entry point. Integration smoke test (spawn → list → task → shutdown). **Completes Milestone 1.**

**Next:** Phase 7 (Implementation) on slice 103.

---

### Slice 102: Agent Registry & Lifecycle — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `23747c4` | feat: add AgentRegistry core with models, errors, spawn, and lookup |
| `9a40ff3` | feat: add list_agents filtering and individual shutdown to AgentRegistry |
| `26f61b4` | feat: add bulk shutdown and singleton accessor to AgentRegistry |
| `16d2a8a` | chore: fix linting, formatting, and type errors for agent registry |
| `a045636` | docs: mark slice 102 (Agent Registry & Lifecycle) as complete |

**What works:**
- 127 tests passing (26 new + 101 existing), ruff clean, pyright zero errors on src/ and new test file
- `AgentInfo` and `ShutdownReport` Pydantic models in `core/models.py`
- `AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError` error hierarchy
- `AgentRegistry.spawn()`: resolves provider, creates agent, tracks by unique name
- `AgentRegistry.get()`, `has()`: lookup by name with proper error raising
- `AgentRegistry.list_agents()`: returns `AgentInfo` summaries with optional state/provider filtering
- `AgentRegistry.shutdown_agent()`: always-remove semantics (agent removed even if shutdown raises)
- `AgentRegistry.shutdown_all()`: best-effort bulk shutdown returning `ShutdownReport`
- `get_registry()` / `reset_registry()` singleton accessor

**Key decisions:**
- Imports moved above error class definitions (ruff E402) — error classes placed after imports, not before
- `AgentInfo.provider` sourced from stored `AgentConfig`, not from the agent object (registry owns this mapping)
- `shutdown_agent()` uses try/finally to guarantee removal regardless of shutdown errors
- `shutdown_all()` collects errors per-agent without aborting — returns structured `ShutdownReport`
- MockAgent uses `set_state()` method instead of direct `_state` access to satisfy pyright's `reportPrivateUsage`

**Issues logged:** None.

**Next:** Slice 4 (CLI Foundation & SDK Agent Tasks).

---

### Slice 102: Agent Registry & Lifecycle — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/102-slice.agent-registry.md` — slice design
- `user/tasks/102-tasks.agent-registry.md` — 14 tasks, test-with pattern

**Scope:** `AgentRegistry` class in `core/agent_registry.py` — spawn, get, has, list_agents (with state/provider filtering), shutdown_agent, shutdown_all. Registry errors (`AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError`). `AgentInfo` and `ShutdownReport` models added to `core/models.py`. Module-level `get_registry()` singleton. All tests use mock providers.

**Next:** Phase 7 (Implementation) on slice 102.

---

### Slice 101: SDK Agent Provider — Complete

**Objective:** Implement the first concrete provider — `SDKAgentProvider` and `SDKAgent` wrapping `claude-agent-sdk` for one-shot and multi-turn agent execution.

**Commits:**
| Hash | Description |
|------|-------------|
| `b44914a` | feat: implement SDK message translation module with tests |
| `f7d15e0` | feat: implement SDKAgentProvider with options mapping and tests |
| `3055fcf` | feat: implement SDKAgent with query and client modes |
| `83611a5` | feat: auto-register SDK provider and add integration tests |
| `8743255` | chore: fix linting, formatting, and type errors |

**What works:**
- 96 tests passing (51 new + 45 foundation), ruff clean, pyright strict zero errors
- `translation.py`: Converts SDK message types (AssistantMessage, ToolUseBlock, ToolResultBlock, ResultMessage) to orchestration Messages
- `SDKAgentProvider`: Maps `AgentConfig` to `ClaudeAgentOptions`, defaults `permission_mode` to `"acceptEdits"`, reads mode from `credentials` dict
- `SDKAgent` query mode: One-shot via `sdk_query()`, translates and yields response messages
- `SDKAgent` client mode: Multi-turn via `ClaudeSDKClient` (create once, reuse), `shutdown()` disconnects
- Error mapping: All 5 SDK exception types → orchestration `ProviderError` hierarchy
- Auto-registration: Importing `orchestration.providers.sdk` registers `"sdk"` in the provider registry
- `validate_credentials()` returns bool without throwing

**Key decisions:**
- `translate_sdk_message` returns `list[Message]` (not `Message | None`) — `AssistantMessage` with multiple blocks produces multiple Messages, empty list for unknown types
- Deferred import of `SDKAgent` in `provider.py` to avoid stub-state issues at module load
- ruff requires `query as sdk_query` alias in a separate import block from other `claude_agent_sdk` imports (isort rule)
- Used `__import__("claude_agent_sdk")` in `validate_credentials` to satisfy pyright's `reportUnusedImport`
- Real SDK dataclasses used for test fixtures (no MagicMock — `TextBlock`, `AssistantMessage`, etc. are simple dataclasses)

**Issues logged:** None.

**Next:** Slice 3 (Agent Registry & Lifecycle) or slice 4 (CLI Foundation).

---

### Slice 100: Foundation Migration — Complete

**Objective:** Migrate foundation from v1 (LLMProvider-based) to v2 (dual-provider Agent/AgentProvider architecture) per `100-arch.orchestration-v2.md`.

**Commits:**
| Hash | Description |
|------|-------------|
| `7200b4e` | feat: add claude-agent-sdk dependency |
| `b6e1264` | feat: add SDK and Anthropic provider subdirectories with stubs |
| `6a389a5` | feat: add shared provider error hierarchy |
| `9700bed` | refactor: rename Agent to AgentConfig, remove ProviderConfig |
| `5ebf6cb` | test: update model tests for AgentConfig migration |
| `2433494` | refactor: replace LLMProvider with Agent and AgentProvider Protocols |
| `0b4302e` | refactor: retype provider registry for AgentProvider instances |
| `90dd38b` | test: update provider tests for AgentProvider instances and error hierarchy |
| `cb1d56c` | refactor: update Settings for dual-provider architecture |
| `0d3da45` | test: update config tests for new Settings fields |
| `f944f02` | docs: update .env.example for dual-provider architecture |
| `fd45a0d` | docs: update stub docstrings with correct slice numbers |
| `f189dc2` | fix: type checking — zero pyright errors |
| `5aaf718` | docs: mark foundation migration tasks and slice complete |

**What works:**
- 45 tests passing, ruff check clean, ruff format clean, pyright strict zero errors
- `AgentConfig` model with SDK-specific fields (cwd, setting_sources, allowed_tools, permission_mode) and API fields (model, api_key, auth_token, base_url)
- `Agent` and `AgentProvider` Protocols (runtime_checkable, structural typing)
- Provider registry maps type names to `AgentProvider` instances
- Shared error hierarchy: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`, `ProviderTimeoutError`
- Settings with `default_provider="sdk"`, `default_agent_type="sdk"`, auth token and base URL support
- Provider subdirectories: `providers/sdk/` and `providers/anthropic/` with stubs
- All stub docstrings updated to correct slice numbers per v2 plan

**Key decisions:**
- `handle_message` in Agent Protocol is a sync method signature (not `async def`) — implementations are async generators, callers use `async for` directly without `await`
- `ProviderTimeoutError` chosen over `ProviderConfigError` — config errors caught at Pydantic validation time; timeout is the real operational concern
- `sdk_default_cwd` kept off Settings (per-agent config via AgentConfig, not global)
- `claude-agent-sdk` imports as `claude_agent_sdk` (module name differs from package name)

**Issues logged:** None.

**Next:** Slice 2 (SDK Agent Provider) or slice 101 (Anthropic Provider) — both can proceed in parallel as they only depend on foundation.

---

## 20260218

### Slice 101: Anthropic Provider — Design Complete

**Documents created:**
- `user/slices/101-slice.anthropic-provider.md` — slice design

**Key design decisions:**
- **API key auth only**: The official Anthropic Python SDK supports `api_key` / `ANTHROPIC_API_KEY` exclusively. No native `auth_token` parameter exists. Claude Max / OAuth bearer token usage requires external gateways (e.g., LiteLLM) — out of scope for this slice but extensible via `ProviderConfig.extra["base_url"]` in future.
- **Async-only client**: `AsyncAnthropic` exclusively — no sync path needed given async framework.
- **SDK streaming helper**: Uses `client.messages.stream()` context manager (not raw `stream=True`) for typed text_stream iterator and automatic cleanup.
- **Minimal error hierarchy**: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`. SDK exceptions mapped to provider-level errors at boundaries.
- **No custom retry**: SDK built-in retry (2 retries, exponential backoff) is sufficient.
- **Default max_tokens=4096**: Required by Anthropic API, configurable via `ProviderConfig.extra`.

**Scope summary:**
- `AnthropicProvider` class satisfying `LLMProvider` Protocol (send_message, stream_message, validate)
- Message conversion: `orchestration.Message` → Anthropic dict format (role mapping, system extraction, consecutive role merging)
- API key resolution: `ProviderConfig.api_key` → `Settings.anthropic_api_key` → explicit error
- Auto-registration in provider registry via `providers/__init__.py`
- Full mock-based test suite (no real API calls)

**Commits:**
- `3c418e0` docs: add slice 101 design (Anthropic Provider)

**Next:** Phase 5 (Task Breakdown) on slice 101, then Phase 7 (Implementation).

### Slice 100: Foundation — Design and Task Creation Complete

**Documents created:**
- `user/slices/100-slice.foundation.md` — slice design (project setup, package structure, core Pydantic models, config, logging, provider protocol, test infrastructure)
- `user/tasks/100-tasks.foundation.md` — 19 granular tasks, sequentially ordered

**Key design decisions:**
- **Test-with ordering**: Tasks are structured so each implementation unit (models, providers, config, logging) is immediately followed by its tests, catching contract issues early rather than batching tests at the end
- **All dependencies installed up front**: `pyproject.toml` includes all project dependencies (anthropic, typer, fastapi, google-adk, mcp, etc.) so later slices just import and use
- **Protocol over ABC**: `LLMProvider` defined as a `Protocol` for structural typing, better ADK compatibility later
- **Stdlib logging only**: No third-party logging library; JSON formatter on stdlib `logging` keeps dependencies minimal

**Scope summary:**
- Project init with `uv`, `src/orchestration/` package layout matching HLD 4-layer architecture
- Pydantic models: Agent, Message, ProviderConfig, TopologyConfig (with StrEnum types)
- Pydantic Settings for env-based config (`ORCH_` prefix), `.env.example`
- LLMProvider Protocol + dict-based provider registry
- Structured logging (JSON + text formats)
- Full test infrastructure and validation pass

**Commits:**
- `007b02f` planning: slice 100 foundation — design and task breakdown complete

**Next:** Phase 6 (Task Expansion) on `100-tasks.foundation.md`, or proceed directly to Phase 7 (implementation) if PM approves skipping expansion for this low-complexity slice.
