---
docType: slice-plan
parent: 180-arch.multi-agent-communication.md
project: squadron
dateCreated: 20260322
dateUpdated: 20260327
status: not_started
---

# Slice Plan: Multi-Agent Communication

## Parent Document
`180-arch.multi-agent-communication.md` — High-Level Design: Multi-Agent Communication

## Milestone Targets

**M2 — Multi-agent communication:** Two agents (SDK and/or API) communicate through the message bus. Proves the unified Agent Protocol works across provider types.

**M3 — Human + agents:** Human participates alongside multiple agents in a shared conversation with configurable topologies.

---

## Feature Slices

### → Milestone 2: Multi-Agent Communication

1. [ ] **(181) Supervisor Component** — Core supervision and health monitoring. Supervisor watches asyncio task state, detects failures (crashed tasks, unhandled exceptions) and response timeouts (agent stuck in processing beyond configurable threshold). one_for_one restart strategy: restart only the failed agent with clean state. New agent states (restarting, failed) added to registry state machine. CLI list command reflects supervisor-managed states. Dependencies: [Agent Registry (102), Message Bus Core (182)]. Risk: Low. Effort: 2/5

2. [ ] **(182) Message Bus Core** — Async pub/sub message system. Agents and other participants (human, system) publish and subscribe. Broadcast routing (all subscribers see all messages) as the default topology. Message history (in-memory) with per-agent filtering view. Message schema: sender, recipients, content, timestamp, message_type, metadata. Dependencies: [Agent Registry (102)]. Risk: Low. Effort: 2/5

3. [ ] **(183) Anthropic API Provider** — Implement AnthropicAPIProvider satisfying the AgentProvider Protocol. AnthropicAPIAgent wraps the anthropic SDK's AsyncAnthropic client for conversational message exchange. Supports both api_key and auth_token authentication. Manages conversation history internally. Converts between orchestration Messages and Anthropic message format. Provider auto-registers as "anthropic" in the provider registry. This is the first API provider and validates the Protocol for future providers (OpenAI, Gemini, etc.). Dependencies: [Foundation (100)]. Risk: Low. Effort: 3/5

4. [ ] **(184) Multi-Agent Message Routing** — Connect agents to the message bus. When an agent publishes a message, the bus routes it to other agents based on the active topology. Each receiving agent's `handle_message` is called, and its response messages are published back to the bus. Conversation turn management to prevent infinite loops (max turns, cooldown, explicit stop). CLI `observe` command to watch a multi-agent conversation in real time. **Completes M2.** Dependencies: [Message Bus Core (182), Anthropic API Provider (183) OR SDK Agent Provider (101) (at least one)]. Risk: Medium (turn management and loop prevention need careful design). Effort: 3/5

### → Milestone 3: Human + Agents

5. [ ] **(185) Human-in-the-Loop Participation** — Human becomes a first-class participant on the message bus (not just a CLI command issuer). In multi-agent mode, human messages are broadcast to all agents alongside agent-to-agent messages. CLI interactive mode: human sees all agent messages and can interject at any point. Agents see human messages in their conversation context. Turn-taking options: free-form (anyone can speak), moderated (human approves each round), or prompted (agents wait for human input between rounds). Also retrofits streaming output to the CLI task command (deferred from slice 103 — see 103-slice.cli-foundation.md Tracked Enhancements). Completes M3. Dependencies: [Multi-Agent Message Routing (184)]. Risk: Low. Effort: 2/5

### Post-Milestone Feature Work

6. [ ] **(186) Communication Topologies** — Topology manager as first-class component. Implement filtered topology (agents see addressed messages + broadcasts only), hierarchical topology (orchestrator sees all, workers see assigned scope), and custom topology (user-provided routing function). CLI commands to select and configure topology per session. Topology affects message bus routing, not agent logic — agents remain unaware of topology details. Dependencies: [Human-in-the-Loop (185)]. Risk: Medium. Effort: 3/5

7. [ ] **(187) ADK Integration** — Bridge between ADK workflow patterns (ParallelAgent, SequentialAgent, Loop) and core engine message bus. ADK manages execution order; each agent step routes through the message bus. Define ADK-compatible agent wrappers that use the AgentProvider abstraction. CLI commands for running ADK workflows (`workflow run`, `workflow list`). Dependencies: [Multi-Agent Message Routing (184)]. Risk: Medium (ADK API surface and integration patterns need exploration). Effort: 3/5

8. [ ] **(188) MCP Server** — Expose orchestration as MCP tools via Python MCP SDK. Tools: create_agent, list_agents, send_task, send_message, get_conversation, shutdown_agent, set_topology. Stdio transport for Claude Code / Cursor integration. MCP server reads from same core engine as CLI — no duplication of logic. Dependencies: [Message Bus Core (182), Agent Registry (102)]. Risk: Low. Effort: 2/5

9. [ ] **(189) REST + WebSocket API** — FastAPI server. REST endpoints for agent lifecycle (create, list, delete) and conversation management (send message, get history). WebSocket endpoint for real-time message streaming (subscribe to message bus events). Automatic OpenAPI docs. CORS configuration for future frontend consumption. Dependencies: [Message Bus Core (182), Agent Registry (102)]. Risk: Low. Effort: 2/5

10. [ ] **(190) Ensemble Review & Cross-Model Analysis** — Run the same review across multiple models (e.g., Haiku, Sonnet, Opus) and synthesize results. Fan out identical review tasks to N agents with different --model settings, collect structured ReviewResult outputs, then route to an evaluator model that compares findings across reviewers. Key analysis dimensions: agreement frequency (findings that appear across multiple reviewers are high-confidence signal), novel detection (findings unique to one reviewer — especially interesting when a smaller model catches something a larger one missed), and noise filtering (findings from weaker models that the evaluator determines are false positives). The evaluator produces a consensus ReviewResult with provenance metadata indicating which models flagged each finding. Pre-M2: can run sequentially with current review system using different --model flags per run and manual comparison. Post-M2: parallel fan-out via message bus. Builds on the findings pipeline (findings ledger provides the structured comparison substrate). Prior art in the embedding-cluster repo explored clustering similar observations across multiple sources — that technique applies directly to grouping findings by semantic similarity across reviewers. Dependencies: [Review Workflow Templates (105), Findings Pipeline (130), model selection support]. Requires M2 for parallel execution but experimentally viable with sequential runs immediately. Risk: Medium (evaluator prompt engineering, cost/value calibration). Effort: 3/5

---

## Integration Work

11. [ ] **(191) Subprocess Agent Support** — Extend agent registry to spawn agents as OS processes (`asyncio.create_subprocess_exec`). Stdout/stderr streaming piped back through message bus. PID tracking in agent registry. Graceful and forced termination. Orphan cleanup on restart (PID file strategy). Primary use case: spawning non-SDK CLI tools as agent participants. Dependencies: [Agent Registry (102), Message Bus Core (182)]. Risk: Medium. Effort: 2/5

12. [ ] **(192) End-to-End Testing & Documentation** — Integration tests for core flows (SDK agent task, API agent chat, multi-agent conversation, human-in-the-loop, topology switching, review workflows). CLI help text and usage examples. README with quickstart (install, configure credentials, spawn first agent). Deployment documentation (local dev, MCP config, server mode). Dependencies: [all prior slices]. Risk: Low. Effort: 2/5

---

## Implementation Order

```
M2 — Multi-Agent Communication:
  182. Message Bus Core                                (can start after 102)
  181. Supervisor Component                            (after 102, Message Bus)
  183. Anthropic API Provider                          (can start after 100, parallel with 162)
  184. Multi-Agent Message Routing                     (after Message Bus + at least one provider)

M3 — Human + Agents:
  185. Human-in-the-Loop Participation                 (after Multi-Agent Message Routing)

Post-Milestone (order flexible):
  186. Communication Topologies                        (after Human-in-the-Loop)
  187. ADK Integration                                 (after Multi-Agent Message Routing)
  188. MCP Server                                      (after Message Bus + 102)
  189. REST + WebSocket API                             (after Message Bus + 102)
  190. Ensemble Review & Cross-Model Analysis           (after Findings Pipeline)

Integration:
  191. Subprocess Agent Support                         (after 102, Message Bus)
  192. End-to-End Testing & Documentation               (after all prior slices)
```

### Parallelization Notes

- **Anthropic API Provider (183) and Message Bus Core (182) are parallel tracks.** Both depend only on Foundation/Registry (complete). An agent working on one doesn't block the other.
- **MCP Server and REST + WebSocket API are independent of each other** and can be done in any order after their dependencies are met.
- **ADK exploration**: ADK Integration depends on the current ADK Python SDK API surface. A brief spike at the start of that slice may be warranted to validate assumptions.

---

## Notes

- **Slice numbering**: Slices are reindexed to 181-192 to reflect their residence in the 160-series. Original numbers were 161-172.
- **100-series prerequisites**: Agent Registry (102), Foundation (100), SDK Agent Provider (101), Local Daemon (112), and the provider infrastructure (111-114) are all complete in the 100-series.
- **Frontend deferred**: The HLD identifies a future React UI. When it arrives, it connects to the REST + WebSocket API and warrants its own architecture document and slice plan.
- **Ensemble Review**: Included here because its full value (parallel fan-out) requires M2. However, it can be experimentally run sequentially using the 100-series review system with different `--model` flags.
