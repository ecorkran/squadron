---
docType: slice-plan
parent: 200-arch.multi-agent-communication.md
project: squadron
dateCreated: 20260322
dateUpdated: 20260514
status: not_started
---

# Slice Plan: Multi-Agent Communication

## Parent Document
`200-arch.multi-agent-communication.md` — High-Level Design: Multi-Agent Communication

## Milestone Targets

**M1 — Task Store + Daemon Socket:** `sq run` posts tasks to the store; a Claude Code IDE session can poll, claim, and complete them. Single-agent pipeline via task store proven end-to-end.

**M2 — Multi-Agent Participation:** Claude Code and Codex (or Hermes) both participate in the same pipeline run. Capability routing assigns steps to the right agent.

**M3 — Ensemble Review:** Fan-out review to multiple models, synthesize results.

---

## Feature Slices

### → Standalone (no task store dependency)

1. [ ] **(203) Anthropic API Provider** — Implement `AnthropicAPIProvider` and `AnthropicAPIAgent` satisfying the existing `AgentProvider` / `Agent` Protocols. Authentication via `ANTHROPIC_API_KEY` (existing `ApiKeyStrategy` pattern). Manages conversation history internally. Adds model aliases (`haiku-api`, `sonnet-api`, `opus-api`) pointing to the new profile. **Standalone-eligible:** ships before the rest of the 200-series. Primary motivation post-June-15: pipeline steps can route to Anthropic API instead of Agent SDK, avoiding the monthly credit constraint for non-interactive use. Risk: Low. Effort: 3/5. Dependencies: [Foundation (100)].

### → Milestone 1: Task Store + Daemon Socket

2. [ ] **(221) Task Store — Schema and Migrations** — Create `workspace.db` SQLite schema (`tasks`, `events` tables as defined in arch doc). Migration runner (simple version table, apply-once scripts). DB path resolution: project-local `.squadron/workspace.db` takes precedence over user-global `~/.config/squadron/workspace.db`. WAL mode enabled. Read-only connection helper for agent-side polling. Risk: Low. Effort: 1/5. Dependencies: [Daemon (112)].

3. [ ] **(222) Daemon Socket Server** — Extend `sq serve` daemon with a Unix socket listener at `~/.config/squadron/daemon.sock`. Newline-delimited JSON protocol: `post_task`, `claim_task`, `complete_task`, `fail_task`, `list_tasks`, `watch_task`. Atomic claim (reject if already claimed). Stale task requeue: background loop checks `timeout_at`, requeues claimed-but-not-completed tasks, writes `requeued` event. Daemon holds the SQLite write connection. Risk: Low. Effort: 2/5. Dependencies: [Task Store (221), Daemon (112)].

4. [ ] **(223) Pipeline Executor Integration** — Update `sq run` pipeline executor: dispatch steps via `post_task` to daemon socket instead of spawning SDK sessions directly. Poll `workspace.db` read-only for result rows; advance pipeline when `status='complete'`. Retain existing SDK-spawn path as fallback when daemon is not running (or behind a `--legacy` flag). Auto-start daemon if not running (existing behavior). Risk: Medium (behavioral change to core executor). Effort: 2/5. Dependencies: [Daemon Socket (222)].

5. [ ] **(224) MCP Tools — Poll/Claim/Complete** — MCP server exposing task store to IDE agents. Tools: `squadron_check_work(project_path)`, `squadron_claim_task(task_id, agent)`, `squadron_complete_task(task_id, result)`, `squadron_fail_task(task_id, error)`, `squadron_list_tasks(project_path, status?)`. Stdio transport for Claude Code / Cursor integration. All write operations proxy through daemon socket; reads hit `workspace.db` directly. **Completes M1** when paired with `/sq:work` slash command (225). Risk: Low. Effort: 2/5. Dependencies: [Daemon Socket (222)].

6. [ ] **(225) `/sq:work` Slash Command** — New Claude Code slash command. Calls `squadron_check_work` MCP tool, claims the returned task, presents it to the interactive session for execution, calls `squadron_complete_task` on completion. Installed by `sq install-commands` alongside existing slash commands. The primary human-facing interface for Claude Code IDE participation in pipeline runs. Risk: Low. Effort: 1/5. Dependencies: [MCP Tools (224)].

### → Milestone 2: Multi-Agent Participation

7. [ ] **(226) Capability Routing** — Add `capabilities` JSON array column to tasks (e.g. `["file_access", "sandbox", "compute"]`). Agent self-declaration: each agent (Claude Code, Codex, Hermes worker) declares its capability set when connecting. `squadron_check_work` filters by declared capabilities + `assigned_to` hint. `sq run` pipeline YAML gains optional `capabilities` and `assigned_to` per step. Risk: Low. Effort: 2/5. Dependencies: [MCP Tools (224), Task Store (221)].

8. [ ] **(227) `sq work` — Hermes Worker CLI** — New `sq work --agent <name>` CLI command. Runs the poll/claim/complete loop as a persistent process — the Hermes-side worker. Connects to daemon socket (configurable path, supports TCP for SSH tunnel). Accepts `--capabilities` flag to declare what this worker can handle. Graceful shutdown on SIGTERM/SIGINT; marks in-progress tasks as failed before exit. Documentation: SSH tunnel setup for remote participation. Risk: Low. Effort: 2/5. Dependencies: [Capability Routing (226)].

### → Milestone 3: Ensemble Review

9. [ ] **(210) Ensemble Review & Cross-Model Analysis** — Pipeline pattern for multi-model review fan-out. Squadron posts N identical review tasks with different model/profile hints, waits for all N results via task store, posts a synthesis task to an evaluator model. Analysis dimensions: agreement frequency (high-confidence signal), novel detection (finding unique to one reviewer), noise filtering. Implemented as a pipeline YAML pattern — no new infrastructure beyond what M1/M2 deliver. Risk: Medium (evaluator prompt engineering). Effort: 3/5. Dependencies: [Capability Routing (226), Pipeline Executor Integration (223)].

### → Integration and Documentation

10. [ ] **(228) End-to-End Testing & Documentation** — Integration tests: task store lifecycle, socket protocol, pipeline executor post/poll, MCP tool round-trip, multi-agent claim race (two agents, one task — only one claims), Hermes worker via local socket. CLI help text. README section on task store and multi-agent participation. Deployment notes for Hermes SSH tunnel setup. Risk: Low. Effort: 2/5. Dependencies: [all prior slices].

---

## Implementation Order

```
Standalone (no sequencing constraint):
  203. Anthropic API Provider

M1 — Task Store + Daemon Socket:
  221. Task Store Schema
  222. Daemon Socket Server          (after 221)
  223. Pipeline Executor Integration (after 222)
  224. MCP Tools                     (after 222, parallel with 223)
  225. /sq:work Slash Command        (after 224)

M2 — Multi-Agent Participation:
  226. Capability Routing            (after 224, 221)
  227. sq work — Hermes Worker CLI   (after 226)

M3 — Ensemble Review:
  210. Ensemble Review               (after 226, 223)

Integration:
  228. E2E Testing & Documentation   (after all prior)
```

### Parallelization Notes

- **203 (Anthropic API Provider) is fully independent** — can start immediately, does not touch the task store.
- **221 and 222 are sequential** — schema before socket server.
- **223 and 224 are parallel** after 222 — pipeline executor and MCP tools are independent consumers of the daemon socket.
- **225 is a thin wrapper** on 224 — fast to deliver once MCP tools exist.

---

## Dropped from Original 200-series

The following slices from the original plan are dropped in this revision. They addressed a push-based message bus model that doesn't fit IDE plugin constraints:

| Original | Title | Reason dropped |
|---|---|---|
| 201 | Supervisor Component | Replaced by daemon timeout/requeue + events table |
| 202 | Message Bus Core | Replaced by task store |
| 204 | Multi-Agent Message Routing | Replaced by capability routing |
| 205 | Human-in-the-Loop (bus participant) | Human *is* the interactive session; no bus needed |
| 206 | Communication Topologies | Replaced by `assigned_to` + `capabilities` |
| 207 | ADK Integration | Squadron pipeline YAML covers sequencing |
| 209 | REST + WebSocket API | Daemon socket is the interface; REST deferred |
| 211 | Subprocess Agent Support | Agents are external pollers, not daemon children |

## Notes

- **100-series prerequisites:** Agent Registry (102), Foundation (100), SDK Agent Provider (101), Local Daemon (112), and provider infrastructure are complete.
- **June 15, 2026 relevance:** Slice 203 (Anthropic API Provider) and slice 223 (Pipeline Executor Integration, task-store model) together eliminate the Agent SDK credit dependency for `sq run` pipeline steps. Prioritizing these two slices before June 15 is recommended.
- **Frontend deferred:** REST+WebSocket and a React UI remain possible future work. When the use case materializes, they warrant their own architecture document.
- **Remote TCP upgrade path:** V1 uses SSH tunnel for Hermes. A future slice can add native TCP with mTLS to the daemon socket without changing the protocol.
