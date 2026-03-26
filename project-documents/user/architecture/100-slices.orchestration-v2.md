---
docType: slice-plan
parent: 100-arch.orchestration-v2.md
project: squadron
dateCreated: 20260217
dateUpdated: 20260325
status: in-progress
---

# Slice Plan: Orchestration (Python Reboot)

## Parent Document
`100-arch.orchestration-v2.md` — High-Level Design: Orchestration (Python Reboot)

## Milestone Targets

**M1 — SDK agent task execution:** Spawn a Claude Agent SDK agent, give it a task, get structured output via CLI. Uses Max subscription — no API cost.

Multi-agent milestones (M2, M3) have been moved to `160-slices.multi-agent-communication.md`.

---

## Foundation Work

1. [x] **(100) Project Setup & Core Models** — `uv init`, pyproject.toml with dependencies (claude-agent-sdk, anthropic, typer, fastapi, pydantic, google-adk, mcp), src/orchestration/ package layout matching HLD structure. Pydantic models for AgentConfig, Message, TopologyConfig. Agent and AgentProvider Protocols in providers/base.py. Provider registry. Pydantic Settings for application configuration. Shared provider error hierarchy. Basic logging setup. Effort: 2/5

---

## Feature Slices (in implementation order)

### → Milestone 1: SDK Agent Task Execution

2. [x] **(101) SDK Agent Provider** — Implement SDKAgentProvider satisfying the AgentProvider Protocol. SDKAgent wraps claude-agent-sdk's `query()` for one-shot tasks and `ClaudeSDKClient` for multi-turn sessions. Agent translates orchestration Messages into SDK queries and SDK responses back into Messages. Configurable: system_prompt, allowed_tools, permission_mode, cwd, setting_sources (for CLAUDE.md loading). Provider auto-registers as "sdk" in the provider registry. Dependencies: [Foundation]. Risk: Low (SDK is well-documented, auth handled by Claude CLI). Effort: 3/5

3. [x] **(102) Agent Registry & Lifecycle** — Agent registry: spawn agent by name, type (sdk/api), and provider config. Track agent state (idle, processing, terminated). Graceful shutdown of individual agents and all-agents. In-process async agent execution. Uses AgentProvider Protocol to create agent instances — registry is provider-agnostic. Dependencies: [SDK Agent Provider]. Risk: Low. Effort: 2/5

4. [x] **(103) CLI Foundation & SDK Agent Tasks** — Typer app with commands: `spawn` (create agent with --type, --provider, --cwd), `list` (show agents with type and state), `task` (send a one-shot task to a named agent, display streaming output), `shutdown` (stop agent). Wire the full path: CLI → Agent Registry → SDK Agent Provider → claude-agent-sdk → response displayed. Dependencies: [Agent Registry]. Risk: Low. Effort: 2/5

**M1 is complete at slice 103 (CLI Foundation).** The M1 value proposition — spawn an SDK agent, give it a task, see structured output from the terminal — is fully delivered.

### Post-M1

6. [x] **(105) Review Workflow Templates** — Predefined workflow configurations for common review patterns: architectural review (agent evaluates slice design against architecture doc and stated goals), task plan review (agent checks task breakdown against slice design for completeness and feasibility), code review (agent reviews files against language-specific rules, testing standards, and project conventions). Each template is a configuration combining system_prompt, allowed_tools, cwd, and setting_sources. CLI command: `review` with `--template` flag. Uses SDK agents for file access. Dependencies: [CLI Foundation, SDK Agent Provider]. Risk: Low. Effort: 2/5

7. [x] **(106) M1 Polish & Publish** — Verbosity levels, persistent configuration (`orchestration config`), text color improvements, `--rules` flag for code review, README and documentation. Makes the CLI presentable and usable by external developers. Dependencies: [Review Workflow Templates, CLI Foundation]. Risk: Low. Effort: 2/5

8. [x] **(111) OpenAI-Compatible Provider Core** — `OpenAICompatibleProvider` and `OpenAICompatibleAgent` implementing AgentProvider/Agent Protocols against the Chat Completions API. Request/response mapping, streaming, tool use translation (OpenAI function calling ↔ orchestration tool model), API key auth. Provider registry integration with configurable base URL. CLI `--provider openai --model gpt-4o` flags. Validates that the AgentProvider Protocol generalizes beyond Anthropic. Dependencies: [Foundation]. Risk: Low. Effort: 2-3/5

9. [x] **(112) Local Daemon** — Persistent daemon process (`orchestration serve`) that holds agent registry, agent instances, and conversation state in memory. CLI commands become thin clients communicating with the daemon via Unix socket or localhost HTTP. Enables spawn-then-message workflows that are impossible with the current per-command process model. All non-SDK providers require this for useful multi-turn interaction. Future interfaces (MCP server, REST+WebSocket API) become additional frontends to the same daemon rather than separate infrastructure. GitHub issue #4. Dependencies: [Foundation, Agent Registry, CLI Foundation]. Risk: Medium (daemon lifecycle, PID management, orphan cleanup). Effort: 3/5

10. [x] **(113) Provider Variants & Registry** — OpenRouter configuration (base URL, required headers, model name mapping), local model configuration (localhost, no auth, model discovery via `/v1/models`), Gemini-via-compatible configuration (Google's OpenAI-compatible endpoint). Provider config file (`~/.config/orchestration/providers.toml`) for persistent endpoint definitions. CLI `--provider openrouter --model anthropic/claude-3.5-sonnet` etc. Dependencies: [OpenAI-Compatible Provider Core]. Risk: Low. Effort: 1-2/5

11. [x] **(114) Auth Strategy & Credential Management** — Auth strategy abstraction (`AuthStrategy` protocol) that decouples credential resolution from provider logic. API key implementation as the concrete strategy (env var lookup, profile-specified env var, localhost placeholder — formalizing the pattern already in `OpenAICompatibleProvider`). `orchestration auth login <provider>` CLI flow for validating and storing API keys. `orchestration auth status` to show configured credentials per provider. Auth strategy selection per profile (`auth_type` field on `ProviderProfile`). Extension points documented for future token-refresh strategies (OAuth, service account rotation). Dependencies: [OpenAI-Compatible Provider Core, Provider Variants & Registry]. Risk: Low (API key auth is well-understood; scope reduced from original OAuth ambition after research showed OpenAI API lacks general OAuth). Effort: 2/5

12. [x] **(115) Project Rename: orchestration → squadron** — Rename the project, package, CLI entry point, and all internal references from orchestration to squadron. CLI command becomes sq (short alias) with squadron as the long form. Package directory: src/orchestration/ → src/squadron/. pyproject.toml: name, entry point (sq = "squadron.cli.app:app"), package references. Config paths: ~/.config/orchestration/ → ~/.config/squadron/ with one-time migration of existing config/provider profiles. Daemon socket path and PID file updated. All imports, logging namespaces, and test references updated. README and documentation updated. Dependencies: [Auth Strategy & Credential Management]. Risk: Low (mechanical refactor, no logic changes). Effort: 1/5

13. [x] **(116) Claude Code Commands — sq Wrappers** — Markdown command files for ~/.claude/commands/ that expose squadron CLI capabilities as Claude Code slash commands. Commands: /sq:spawn, /sq:task, /sq:list, /sq:shutdown, /sq:review-slice, /sq:review-tasks, /sq:review-code, /sq:auth-status. Commands shell out to the globally-installed `sq` CLI. Includes `sq install-commands` and `sq uninstall-commands`. Dependencies: [Project Rename]. Risk: Low. Effort: 1/5

14. [x] **(117) PyPI Publishing & Global Install** — Publish squadron to PyPI so users can install globally via `pipx install squadron` or `uv tool install squadron`, making `sq` available on PATH without venv activation. GitHub Actions publish workflow (test on push, publish on tag). Dependencies: [Claude Code Commands — sq Wrappers]. Risk: Low. Effort: 1-2/5

15. [x] **(118) Claude Code Commands — Composed Workflows** — `/sq:run-slice` command automating the full slice lifecycle. Review command updates: bare number shorthand (`sq review slice 118`), path resolution via Context-Forge, review file auto-save. CLI/slash-command parity. Dependencies: [Claude Code Commands — sq Wrappers, context-forge workflow navigation]. Risk: Low. Effort: 2/5

16. [x] **(119) Review Provider & Model Selection** — Enable review commands to use any configured provider/model, not just the hardcoded Claude SDK. Add `--profile` flag to `sq review slice|tasks|code`. User-customizable review templates. Model-to-profile inference. Dependencies: [Review Workflow Templates (105), Provider Variants & Registry (113), Auth Strategy (114), Composed Workflows (118)]. Risk: Low. Effort: 3/5

17. [x] **(120) Model Alias Registry** — Data-driven model shorthand resolution. Ships a default `models.toml` mapping short names (e.g., `opus`, `sonnet`, `gpt54-nano`, `kimi25`) to `(profile, full_model_id)` tuples. User-editable at `~/.config/squadron/models.toml`. Dependencies: [Review Provider & Model Selection (119)]. Risk: Low. Effort: 2/5

18. [x] **(121) Model Alias Metadata** — Extend the ModelAlias structure with optional metadata fields: `private` (bool — whether the provider trains on prompts), `cost_tier` (free/cheap/moderate/expensive), `notes` (free-text). Update `models.toml` format to support inline table or full table syntax for aliases with metadata. `sq models` displays metadata columns. Built-in aliases ship with curated metadata for all defaults. Dependencies: [Model Alias Registry (120)]. Risk: Low. Effort: 1/5

19. [x] **(122) Review Context Enrichment** — Automatically enrich review prompts with applicable rules and context. Code reviews auto-detect language from the diff/files under review and inject matching rules from the project's `rules/` directory (e.g. Python files → `rules/python.md`). Supports multiple language detection in a single review. Config key `rules_dir` points to the rules directory. The `--rules` CLI flag continues to work as an explicit override/addition. Slice and task reviews can optionally pull review criteria from Context Forge's process guide prompts when available. Dependencies: [Review Provider & Model Selection (119)]. Risk: Low. Effort: 1/5

20. [x] **(127) Scoped Code Review & Prompt Logging** — Enable `sq review code 122` to automatically scope the diff to the commits introduced by slice 122's branch, rather than diffing against main. Resolve commit range from branch name (`122-slice.*`) or merge base. Add prompt log persistence: `-vvv` output written to `~/.config/squadron/logs/review-prompt-{timestamp}.md` alongside stderr. Optionally include full prompt/response in the saved review file at `-vv+`. Dependencies: [Review Context Enrichment (122)]. Risk: Low. Effort: 2/5

21. [ ] **(123) Review Findings Pipeline** — Automated triage and tracking for review output. When a review produces findings, classify each by complexity (auto-fix, guided fix, design decision, skip/acknowledged) and route accordingly. Auto-fixable findings applied directly with commit. Guided fixes get context annotation before handoff. Design decisions surfaced to human PM. Findings ledger for pattern detection and audit trail. Dependencies: [Review Workflow Templates (105), M1 Polish (106)]. Risk: Medium (classification heuristics need tuning). Effort: 3/5

21. [ ] **(124) Codex Agent Integration** — New agent type (`CodexProvider`) integrating OpenAI Codex via the Python SDK (`codex-app-server`, primary) or MCP server (fallback). Codex agents run in sandboxed environments with file access, enabling agentic reviews. Auth delegates to Codex CLI (ChatGPT subscription or API key). Dependencies: [Auth Strategy & Credential Management (114), Agent Registry (102)]. Risk: Medium (Python SDK is experimental v0.2.0). Effort: 3/5

22. [ ] **(125) Conversation Persistence & Management** — Replace the engine's in-memory _histories dict with a ConversationStore protocol backed by SQLite. Conversations persist across daemon restarts and agent shutdowns. CLI additions: history --list, --export, --search. Retention policies with --prune. Dependencies: [Local Daemon (112)]. Risk: Low. Effort: 2/5

23. [x] **(126) Context Forge Integration Layer** — Centralize all Context Forge CLI interactions behind a `ContextForgeClient` abstraction in `src/squadron/integrations/context_forge.py`. Replace scattered `subprocess.run(["cf", ...])` calls with typed methods. Update to CF's current command surface (`cf list slices --json`, etc.). Design for multiple transport backends: subprocess CLI (current, fallback), MCP client (preferred when CF MCP server is available). Optionally surface key CF commands as `sq` subcommands (`sq guides`, `sq list slices`) delegating to CF — no logic duplication. Dependencies: [CLI Foundation (103)]. Risk: Low. Effort: 2/5

---

## Future Work

1. [FUTURE] **Context Forge as Agent Tools** — Expose Context Forge commands as tools available to non-SDK agents. Likely moves to the automated pipeline initiative. Dependencies: [160-series MCP Server or Agent Registry]. Risk: Low. Effort: 2/5

2. [DEFERRED] **SDK Client Warm Pool** — Deferred during design. SDK architecture incompatible with original pool concept. To be revisited as a session cache. See `104-slice.sdk-client-warm-pool.md`. Dependencies: [CLI Foundation]. Risk: Medium. Effort: 3/5

---

## Implementation Order

```
Foundation:
  100. Project Setup & Core Models                    ✅ complete

M1 — SDK Agent Task Execution:
  101. SDK Agent Provider                             ✅ complete
  102. Agent Registry & Lifecycle                     ✅ complete
  103. CLI Foundation & SDK Agent Tasks               ✅ complete (M1 complete)
  104. SDK Client Warm Pool                           ⏸ DEFERRED

Post-M1:
  105. Review Workflow Templates                      ✅ complete
  106. M1 Polish & Publish                            ✅ complete
  111. OpenAI-Compatible Provider Core                ✅ complete
  112. Local Daemon                                   ✅ complete
  113. Provider Variants & Registry                   ✅ complete
  114. Auth Strategy & Credential Management          ✅ complete
  115. Project Rename: orchestration → squadron       ✅ complete
  116. Claude Code Commands — sq Wrappers             ✅ complete
  117. PyPI Publishing & Global Install               ✅ complete
  118. Composed Workflows                             ✅ complete
  119. Review Provider & Model Selection              ✅ complete
  120. Model Alias Registry                            ✅ complete
  121. Model Alias Metadata                           ✅ complete
  126. Context Forge Integration Layer                   ✅ complete
  122. Review Context Enrichment                        ✅ complete
  127. Scoped Code Review & Prompt Logging              ✅ complete
  123. Review Findings Pipeline                         (after 105, 106)
  124. Codex Agent Integration                          (after 114)
  125. Conversation Persistence & Management           (after 112)
```

### Parallelization Notes

- **Slice 126 (Context Forge Integration Layer) is complete.** CF calls centralized behind `ContextForgeClient` in `src/squadron/integrations/context_forge.py`.
- **Slice 104 (SDK Client Warm Pool) is deferred.** When revisited, it should be redesigned as a session cache with agent profile management.
- Multi-agent slices (M2, M3) are now tracked in `160-slices.multi-agent-communication.md`.

---

## Tracked Enhancements

### SDK Agent Enhancements (parent: slice 101 — SDK Agent Provider)

- **Hook system integration**: The SDK's `PreToolUse` / `PostToolUse` hooks enable programmatic control over agent behavior. Natural complement to review workflow templates (slice 105).

- **Custom MCP tool definitions**: The SDK's `@tool` decorator and `create_sdk_mcp_server` allow defining Python functions as tools available to SDK agents. Enables orchestration-aware tools. Candidate: dedicated slice post-M2.

- **Subagent spawning**: The SDK natively supports subagent definitions via `ClaudeAgentOptions.agents`. Candidate: explore post-M2.

### Model Registry Enhancements (parent: slice 120 — Model Alias Registry)

- **Provider API metadata hydration**: Pull pricing, context length, and capability metadata from provider APIs (OpenRouter `/api/v1/models`, OpenAI, Anthropic, Google) to auto-populate alias metadata. Candidate: dedicated slice after 136 (Metadata).

---

## Notes

- **Slices 100-122, 126-127 are complete.** M1 is fully shipped and published. Project renamed to squadron, published to PyPI as v0.2.5.
- **Multi-agent work** (M2, M3) has been moved to `160-arch.multi-agent-communication.md` and `160-slices.multi-agent-communication.md`.
- **SDK initialization cost**: Each `query()` call spawns a fresh subprocess with 2-12s+ overhead. Slice 104 deferred pending redesign.
- **Multi-provider validation**: Slices 111-114 complete. The AgentProvider Protocol generalizes beyond Anthropic.
