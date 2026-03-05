---
docType: slice-plan
parent: 100-arch.orchestration-v2.md
project: orchestration
dateCreated: 20260217
dateUpdated: 20260226
---

# Slice Plan: Orchestration (Python Reboot)

## Parent Document
`100-arch.orchestration-v2.md` — High-Level Design: Orchestration (Python Reboot)

## Milestone Targets

These milestones define the priority ordering. Slices are sequenced to reach each milestone as early as possible.

**M1 — SDK agent task execution:** Spawn a Claude Agent SDK agent, give it a task, get structured output via CLI. Uses Max subscription — no API cost.

**M2 — Multi-agent communication:** Two agents (SDK and/or API) communicate through the message bus. Proves the unified Agent Protocol works across provider types.

**M3 — Human + agents:** Human participates alongside multiple agents in a shared conversation with configurable topologies.

---

## Foundation Work

1. [x] **Project Setup & Core Models** — `uv init`, pyproject.toml with dependencies (claude-agent-sdk, anthropic, typer, fastapi, pydantic, google-adk, mcp), src/orchestration/ package layout matching HLD structure. Pydantic models for AgentConfig, Message, TopologyConfig. Agent and AgentProvider Protocols in providers/base.py. Provider registry. Pydantic Settings for application configuration. Shared provider error hierarchy. Basic logging setup. Effort: 2/5

---

## Feature Slices (in implementation order)

### → Milestone 1: SDK Agent Task Execution

2. [x] **SDK Agent Provider** — Implement SDKAgentProvider satisfying the AgentProvider Protocol. SDKAgent wraps claude-agent-sdk's `query()` for one-shot tasks and `ClaudeSDKClient` for multi-turn sessions. Agent translates orchestration Messages into SDK queries and SDK responses back into Messages. Configurable: system_prompt, allowed_tools, permission_mode, cwd, setting_sources (for CLAUDE.md loading). Provider auto-registers as "sdk" in the provider registry. Dependencies: [Foundation]. Risk: Low (SDK is well-documented, auth handled by Claude CLI). Effort: 3/5

3. [x] **Agent Registry & Lifecycle** — Agent registry: spawn agent by name, type (sdk/api), and provider config. Track agent state (idle, processing, terminated). Graceful shutdown of individual agents and all-agents. In-process async agent execution. Uses AgentProvider Protocol to create agent instances — registry is provider-agnostic. Dependencies: [SDK Agent Provider]. Risk: Low. Effort: 2/5

4. [x] **CLI Foundation & SDK Agent Tasks** — Typer app with commands: `spawn` (create agent with --type, --provider, --cwd), `list` (show agents with type and state), `task` (send a one-shot task to a named agent, display streaming output), `shutdown` (stop agent). Wire the full path: CLI → Agent Registry → SDK Agent Provider → claude-agent-sdk → response displayed. Dependencies: [Agent Registry]. Risk: Low. Effort: 2/5

5. [DEFERRED] **SDK Client Warm Pool** — Deferred during design. SDK research revealed that `ClaudeSDKClient` does not maintain persistent connectable processes — each `query()` spawns a fresh subprocess with options baked in at creation. The original pool concept (pre-initialized clients handed out on demand) is not viable. To be revisited as a **session cache with agent profile management** once review workflows (slice 15) establish usage patterns. See `104-slice.sdk-client-warm-pool.md` for full rationale and future design direction. Dependencies: [CLI Foundation]. Risk: Medium. Effort: 3/5

**M1 is complete at slice 4 (CLI Foundation).** The M1 value proposition — spawn an SDK agent, give it a task, see structured output from the terminal — is fully delivered. Review Workflow Templates (slice 15, pulled forward below) is the immediate next priority.

### Post-M1

15. [x] **Review Workflow Templates** — Predefined workflow configurations for common review patterns: architectural review (agent evaluates slice design against architecture doc and stated goals), task plan review (agent checks task breakdown against slice design for completeness and feasibility), code review (agent reviews files against language-specific rules, testing standards, and project conventions). Each template is a configuration combining system_prompt, allowed_tools, cwd, and setting_sources. CLI command: `review` with `--template` flag. Uses SDK agents for file access. Dependencies: [CLI Foundation, SDK Agent Provider]. Risk: Low. Effort: 2/5

106. [x] **M1 Polish & Publish** — Verbosity levels, persistent configuration (`orchestration config`), text color improvements, `--rules` flag for code review, README and documentation. Makes the CLI presentable and usable by external developers. Dependencies: [Review Workflow Templates, CLI Foundation]. Risk: Low. Effort: 2/5

111. [x] **OpenAI-Compatible Provider Core** — `OpenAICompatibleProvider` and `OpenAICompatibleAgent` implementing AgentProvider/Agent Protocols against the Chat Completions API. Request/response mapping, streaming, tool use translation (OpenAI function calling ↔ orchestration tool model), API key auth. Provider registry integration with configurable base URL. CLI `--provider openai --model gpt-4o` flags. Validates that the AgentProvider Protocol generalizes beyond Anthropic. Dependencies: [Foundation]. Risk: Low. Effort: 2-3/5

112. [x] **Local Server & CLI Client** — Persistent daemon process (`orchestration serve`) that holds agent registry, agent instances, and conversation state in memory. CLI commands become thin clients communicating with the daemon via Unix socket or localhost HTTP. Enables spawn-then-message workflows that are impossible with the current per-command process model. All non-SDK providers require this for useful multi-turn interaction. Future interfaces (MCP server, REST+WebSocket API) become additional frontends to the same daemon rather than separate infrastructure. GitHub issue #4. Dependencies: [Foundation, Agent Registry, CLI Foundation]. Risk: Medium (daemon lifecycle, PID management, orphan cleanup). Effort: 3/5

113. [x] **Provider Variants & Registry** — OpenRouter configuration (base URL, required headers, model name mapping), local model configuration (localhost, no auth, model discovery via `/v1/models`), Gemini-via-compatible configuration (Google's OpenAI-compatible endpoint). Provider config file (`~/.config/orchestration/providers.toml`) for persistent endpoint definitions. CLI `--provider openrouter --model anthropic/claude-3.5-sonnet` etc. Dependencies: [OpenAI-Compatible Provider Core]. Risk: Low. Effort: 1-2/5

114. [x] **Auth Strategy & Credential Management** — Auth strategy abstraction (`AuthStrategy` protocol) that decouples credential resolution from provider logic. API key implementation as the concrete strategy (env var lookup, profile-specified env var, localhost placeholder — formalizing the pattern already in `OpenAICompatibleProvider`). `orchestration auth login <provider>` CLI flow for validating and storing API keys. `orchestration auth status` to show configured credentials per provider. Auth strategy selection per profile (`auth_type` field on `ProviderProfile`). Extension points documented for future token-refresh strategies (OAuth, service account rotation). Dependencies: [OpenAI-Compatible Provider Core, Provider Variants & Registry]. Risk: Low (API key auth is well-understood; scope reduced from original OAuth ambition after research showed OpenAI API lacks general OAuth). Effort: 2/5

115 [ ] **Project Rename: orchestration → squadron** — Rename the project, package, CLI entry point, and all internal references from orchestration to squadron. CLI command becomes sq (short alias) with squadron as the long form. Package directory: src/orchestration/ → src/squadron/. pyproject.toml: name, entry point (sq = "squadron.cli.app:app"), package references. Config paths: ~/.config/orchestration/ → ~/.config/squadron/ with one-time migration of existing config/provider profiles. Daemon socket path and PID file updated. All imports, logging namespaces, and test references updated. README and documentation updated. Migration note: existing providers.toml and auth credentials are copied to the new config directory on first run; old directory left in place with a deprecation notice file. The rename should happen before Claude Code commands (slice 118) ship so that command files reference the correct binary from day one. Dependencies: [Auth Strategy & Credential Management]. Risk: Low (mechanical refactor, no logic changes). Effort: 1/5

116 [ ] **Claude Code Commands — Thin Wrappers** — Markdown command files for ~/.claude/commands/ that expose squadron and context-forge CLI capabilities as Claude Code slash commands. Squadron commands: /sq:spawn, /sq:task, /sq:list, /sq:shutdown, /sq:review-arch, /sq:review-tasks, /sq:review-code, /sq:**auth-status. Context Forge commands: /cf:status, /cf:build, /cf:next, /cf:prompt. Commands shell out to the globally-installed CLIs using ! prefix execution, passing $ARGUMENTS or positional $1/$2 parameters. Both tools are already CWD-aware, so commands work correctly in any project directory. Includes an install mechanism: sq install-commands [--target ~/.claude/commands/] that copies the command markdown files from the package's bundled commands/ directory into place. Uninstall via sq uninstall-commands. Command files are maintained in the squadron repo under commands/ as the source of truth. Also includes YAML frontmatter with description fields for Claude Code auto-discovery (Claude can suggest the command even without explicit / invocation). Dependencies: [Project Rename]. Risk: Low. Effort: 1/5

117 [ ] **Claude Code Commands — Composed Workflows** — Higher-level Claude Code commands in ~/.claude/commands/workflow/ that chain squadron and context-forge together, leveraging Claude Code's reasoning to interpret results and suggest next actions. /workflow:next-step runs cf status + cf next, interprets the project state, and recommends whether to run a review, start implementation, or advance to the next phase. /workflow:design-review runs cf build to assemble context then sq review arch against the appropriate architecture doc. /workflow:ensemble-review runs the same review across multiple providers (using sq task with different --provider flags) and asks Claude Code to synthesize the results — a lightweight ensemble pattern that works before the message bus exists. Commands are designed to be opinionated but overridable via $ARGUMENTS. Depends on daily use of slice 118 to validate which compositions are actually useful vs. theoretical. Dependencies: [Claude Code Commands — Thin Wrappers]. Risk: Low (commands are markdown files, easy to iterate). Effort: 2/5

118 [ ] **Conversation Persistence & Management** — Replace the engine's in-memory _histories dict with a ConversationStore protocol backed by SQLite. Conversations persist across daemon restarts and agent shutdowns — orchestration history gpt works after the agent is gone and after the daemon is recycled. Schema captures orchestration-level messages (sender, content, message_type, timestamp, metadata) with per-agent conversation grouping and session boundaries. CLI additions: orchestration history --list (show all conversations), orchestration history --export <agent> --format json|markdown (export for analysis or context injection), orchestration history --search "query" (full-text search across conversations). Retention policies: configurable per-session or per-project, with orchestration history --prune --older-than 30d for cleanup. The store becomes the backing data for multiple downstream consumers: the findings ledger (slice 15) references review conversations by ID, ensemble reviews (slice 16) compare outputs across conversation records, the ADP pipeline uses conversation history as the decision record at phase transitions, and multi-agent session replay (post-M2) reads from the same store. Design constraint: the ConversationStore protocol should be defined in the engine module so that the in-memory implementation from slice 112 and the SQLite implementation are interchangeable — the engine never knows which backend is active. Dependencies: [Local Server & CLI Client]. Risk: Low (SQLite is well-understood; the schema is straightforward). Effort: 2/5

### → Milestone 2: Multi-Agent Communication

6. [ ] **Message Bus Core** — Async pub/sub message system. Agents and other participants (human, system) publish and subscribe. Broadcast routing (all subscribers see all messages) as the default topology. Message history (in-memory) with per-agent filtering view. Message schema: sender, recipients, content, timestamp, message_type, metadata. Dependencies: [Agent Registry]. Risk: Low. Effort: 2/5

7. [ ] **Anthropic API Provider** — Implement AnthropicAPIProvider satisfying the AgentProvider Protocol. AnthropicAPIAgent wraps the anthropic SDK's AsyncAnthropic client for conversational message exchange. Supports both api_key and auth_token authentication. Manages conversation history internally. Converts between orchestration Messages and Anthropic message format. Provider auto-registers as "anthropic" in the provider registry. This is the first API provider and validates the Protocol for future providers (OpenAI, Gemini, etc.). Dependencies: [Foundation]. Risk: Low. Effort: 3/5

8. [ ] **Multi-Agent Message Routing** — Connect agents to the message bus. When an agent publishes a message, the bus routes it to other agents based on the active topology. Each receiving agent's `handle_message` is called, and its response messages are published back to the bus. Conversation turn management to prevent infinite loops (max turns, cooldown, explicit stop). CLI `observe` command to watch a multi-agent conversation in real time. **Completes M2.** Dependencies: [Message Bus Core, Anthropic API Provider OR SDK Agent Provider (at least one)]. Risk: Medium (turn management and loop prevention need careful design). Effort: 3/5

### → Milestone 3: Human + Agents

9. [ ] **Human-in-the-Loop Participation** — Human becomes a first-class participant on the message bus (not just a CLI command issuer). In multi-agent mode, human messages are broadcast to all agents alongside agent-to-agent messages. CLI interactive mode: human sees all agent messages and can interject at any point. Agents see human messages in their conversation context. Turn-taking options: free-form (anyone can speak), moderated (human approves each round), or prompted (agents wait for human input between rounds). Also retrofits streaming output to the CLI task command (deferred from slice 4 — see 103-slice.cli-foundation.md Tracked Enhancements). Completes M3. Dependencies: [Multi-Agent Message Routing]. Risk: Low. Effort: 2/5

### Post-Milestone Feature Work

10. [ ] **Communication Topologies** — Topology manager as first-class component. Implement filtered topology (agents see addressed messages + broadcasts only), hierarchical topology (orchestrator sees all, workers see assigned scope), and custom topology (user-provided routing function). CLI commands to select and configure topology per session. Topology affects message bus routing, not agent logic — agents remain unaware of topology details. Dependencies: [Human-in-the-Loop]. Risk: Medium. Effort: 3/5

12. [ ] **ADK Integration** — Bridge between ADK workflow patterns (ParallelAgent, SequentialAgent, Loop) and core engine message bus. ADK manages execution order; each agent step routes through the message bus. Define ADK-compatible agent wrappers that use the AgentProvider abstraction. CLI commands for running ADK workflows (`workflow run`, `workflow list`). Dependencies: [Multi-Agent Message Routing]. Risk: Medium (ADK API surface and integration patterns need exploration). Effort: 3/5

13. [ ] **MCP Server** — Expose orchestration as MCP tools via Python MCP SDK. Tools: create_agent, list_agents, send_task, send_message, get_conversation, shutdown_agent, set_topology. Stdio transport for Claude Code / Cursor integration. MCP server reads from same core engine as CLI — no duplication of logic. Dependencies: [Message Bus Core, Agent Registry]. Risk: Low. Effort: 2/5

14. [ ] **REST + WebSocket API** — FastAPI server. REST endpoints for agent lifecycle (create, list, delete) and conversation management (send message, get history). WebSocket endpoint for real-time message streaming (subscribe to message bus events). Automatic OpenAPI docs. CORS configuration for future frontend consumption. Dependencies: [Message Bus Core, Agent Registry]. Risk: Low. Effort: 2/5

15. [ ] **Review Findings Pipeline** — Automated triage and tracking for review output. When a review produces findings, classify each by complexity (auto-fix, guided fix, design decision, skip/acknowledged) and route accordingly. Auto-fixable findings (style violations, missing error handling, fixture consolidation) are applied directly with commit. Guided fixes get context annotation before handoff to an agent. Design decisions are surfaced to human PM for disposition. All findings and their dispositions are recorded in a structured log (findings ledger) that persists across reviews — enables pattern detection ("this category of issue keeps recurring, add it to the template rules") and serves as an audit trail for what was addressed vs. intentionally deferred. Commit strategy: batch commit for auto-fixes, individual commits for guided fixes with finding reference in commit message. Dependencies: [Review Workflow Templates, M1 Polish]. Risk: Medium (classification heuristics need tuning). Effort: 3/5

16. [ ] **Ensemble Review & Cross-Model Analysis** — Run the same review across multiple models (e.g., Haiku, Sonnet, Opus) and synthesize results. Fan out identical review tasks to N agents with different --model settings, collect structured ReviewResult outputs, then route to an evaluator model that compares findings across reviewers. Key analysis dimensions: agreement frequency (findings that appear across multiple reviewers are high-confidence signal), novel detection (findings unique to one reviewer — especially interesting when a smaller model catches something a larger one missed), and noise filtering (findings from weaker models that the evaluator determines are false positives). The evaluator produces a consensus ReviewResult with provenance metadata indicating which models flagged each finding. Pre-M2: can run sequentially with current review system using different --model flags per run and manual comparison. Post-M2: parallel fan-out via message bus. Builds on the findings pipeline (findings ledger provides the structured comparison substrate). Prior art in the embedding-cluster repo explored clustering similar observations across multiple sources — that technique applies directly to grouping findings by semantic similarity across reviewers. Dependencies: [Review Workflow Templates, Findings Pipeline, model selection support]. Requires M2 for parallel execution but experimentally viable with sequential runs immediately. Risk: Medium (evaluator prompt engineering, cost/value calibration). Effort: 3/5

116. [ ] **Codex Agent Integration** — New agent type (`CodexAgentProvider`) that spawns OpenAI Codex as an orchestrated agent using ChatGPT subscription auth (OAuth 2.0 with PKCE). Browser-based login flow (`orchestration codex login`) with token caching at `~/.config/orchestration/codex-auth.json` and automatic refresh. Codex agents run against the user's ChatGPT Plus/Pro/Teams subscription — no API credits consumed. The `AuthStrategy` protocol from slice 114 provides the token-refresh integration point. Research spike at slice start to validate Codex CLI/API surface for programmatic task execution and confirm Teams account compatibility. Dependencies: [Auth Strategy & Credential Management, Agent Registry]. Risk: Medium (Codex API surface is evolving; Teams account OAuth support needs validation). Effort: 3/5

---

## Integration Work

17. [ ] **Subprocess Agent Support** — Extend agent registry to spawn agents as OS processes (`asyncio.create_subprocess_exec`). Stdout/stderr streaming piped back through message bus. PID tracking in agent registry. Graceful and forced termination. Orphan cleanup on restart (PID file strategy). Primary use case: spawning non-SDK CLI tools as agent participants. Dependencies: [Agent Registry, Message Bus Core]. Risk: Medium. Effort: 2/5

18. [ ] **End-to-End Testing & Documentation** — Integration tests for core flows (SDK agent task, API agent chat, multi-agent conversation, human-in-the-loop, topology switching, review workflows). CLI help text and usage examples. README with quickstart (install, configure credentials, spawn first agent). Deployment documentation (local dev, MCP config, server mode). Dependencies: [all prior slices]. Risk: Low. Effort: 2/5

---

## Implementation Order

```
Foundation:
  1. Project Setup & Core Models                    ✅ complete

M1 — SDK Agent Task Execution:
  2. SDK Agent Provider                             ✅ complete
  3. Agent Registry & Lifecycle                     ✅ complete
  4. CLI Foundation & SDK Agent Tasks               ✅ complete (M1 complete)
  5. SDK Client Warm Pool                           ⏸ DEFERRED (SDK architecture incompatible)

Post-M1:
  15. Review Workflow Templates                     ✅ complete
  106. M1 Polish & Publish                           ✅ complete
  111. OpenAI-Compatible Provider Core               ✅ complete
  112. Local Server & CLI Client                     ✅ complete
  113. Provider Variants & Registry                  (after 112)
  114. Auth Strategy & Credential Management          (after 113)
  116. Codex Agent Integration                         (after 114, post-milestone)

M2 — Multi-Agent Communication:
  6. Message Bus Core (can start after 3)
  7. Anthropic API Provider (can start after 1, parallel with 2-5)
  8. Multi-Agent Message Routing

M3 — Human + Agents:
  9. Human-in-the-Loop Participation

Post-Milestone (order flexible):
  10. Communication Topologies
  12. ADK Integration
  13. MCP Server (can start after 6+3)
  14. REST + WebSocket API (can start after 6+3)

Integration:
  17. Subprocess Agent Support
  18. End-to-End Testing & Documentation
```

### Parallelization Notes

- **Slices 111-114 (Multi-Provider) are the immediate next priority.** Slice 111 depends only on Foundation (complete). Validates that the AgentProvider Protocol generalizes beyond Anthropic. 112 and 113 follow directly. Slice 114 (Auth Strategy) follows 113 to formalize the credential patterns established there. Slice 116 (Codex Agent) is post-milestone, depends on 114's auth abstraction.
- **Slices 7 and 111 are parallel tracks.** Both depend only on Foundation. An agent working on one doesn't block the other.
- **Slices 13 and 14 are independent of each other** and can be done in any order after their dependencies are met.
- **Slice 5 (SDK Client Warm Pool) is deferred.** When revisited, it should be redesigned as a session cache with agent profile management. See `104-slice.sdk-client-warm-pool.md`.

---

## Tracked Enhancements

These are high-value capabilities identified during slice design that are intentionally deferred from their parent slices to keep scope bounded. They should be addressed as dedicated slices or folded into existing slices during post-M1 planning.

### SDK Agent Enhancements (parent: slice 2 — SDK Agent Provider)

- **Hook system integration**: The SDK's `PreToolUse` / `PostToolUse` hooks enable programmatic control over agent behavior — deny dangerous commands, enforce read-only mode, log tool usage, inject review constraints. Natural complement to review workflow templates (slice 15). Candidate: fold into slice 15 or create a dedicated slice if hook patterns are reusable beyond reviews.

- **Custom MCP tool definitions**: The SDK's `@tool` decorator and `create_sdk_mcp_server` allow defining Python functions as tools available to SDK agents, running in-process (no subprocess). Enables orchestration-aware tools: "query the message bus," "check agent state," "submit review verdict." Bridges SDK agent autonomy with orchestration system state. Candidate: dedicated slice post-M2, when agents need awareness of each other.

- **Subagent spawning**: The SDK natively supports subagent definitions via `ClaudeAgentOptions.agents`. An SDK agent can spawn its own subagents for parallel work with isolated context. Complementary to (not competing with) the orchestration framework's multi-agent coordination. Candidate: explore post-M2, after the message bus and multi-agent patterns are established. Lower priority than hooks and custom tools.

---

## Notes

- **Numbering**: Slices use the 100 band (100-119) since this is the project's primary initiative. If this creates index pressure with future initiatives, slices can be re-indexed.
- **Frontend deferred**: The HLD identifies a future React UI. This is explicitly out of scope for this slice plan. When it arrives, it connects to the REST + WebSocket API (slice 14) and warrants its own architecture document and slice plan.
- **SDK initialization cost**: Each `query()` call spawns a fresh subprocess with 2-12s+ overhead (up to 20-30s on some platforms). SDK research (2026-02-20) confirmed that `ClaudeSDKClient` options are baked in at creation — no reconfiguration after `connect()`. Slice 5 (SDK Client Warm Pool) is deferred pending redesign as a session cache. See `104-slice.sdk-client-warm-pool.md` for full research findings and future design direction.
- **ADK exploration**: Slice 12 (ADK Integration) depends on the current ADK Python SDK API surface. A brief spike at the start of that slice may be warranted to validate assumptions from the HLD.
- **Multi-provider validation**: Slices 111-114 replace the original slice 11. The OpenAI-compatible provider (111) is the critical Protocol generalization test. Dependency on Anthropic API Provider removed — builds directly against Foundation. If 111 requires Protocol changes, backport to Foundation before proceeding. Expanded scope covers OpenAI, OpenRouter, Gemini (via compatible endpoint), local models, and auth strategy abstraction. OAuth for Team accounts deferred to slice 116 (Codex Agent Integration) after research showed OpenAI API uses key-based auth only — OAuth applies specifically to Codex subscription access.
- **Review workflows (slice 15) and M1 Polish (slice 106) are complete.** M1 is fully shipped and published.
- **Old orchestration artifacts**: The orch-128, 129, 132, 140 documents in project knowledge describe work from the Node.js/Electron era. They are reference material for design rationale only — no code or architecture carries forward into these slices.
