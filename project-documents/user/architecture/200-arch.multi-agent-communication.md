---
docType: architecture
layer: project
project: squadron
archIndex: 200
component: multi-agent-communication
dateCreated: 20260322
dateUpdated: 20260514
status: not_started
---

# High-Level Design: Multi-Agent Communication

## Overview

Multi-agent communication transforms Squadron from a single-agent dispatcher into a shared workspace coordinator. Multiple AI agents — Claude Code (IDE), Codex (IDE plugin), remote machines (Hermes), and future participants — coordinate through a persistent task store owned by the Squadron daemon. Agents poll for work, claim tasks atomically, execute them using their native capabilities, and write results back. Squadron CLI sequences pipeline steps by posting tasks and waiting for results.

The motivating shift: IDE plugins and interactive Claude Code sessions are reactive — they cannot receive push messages. A shared pull-based store fits this constraint naturally. The daemon is the sole writer to SQLite; agents read directly and write back through the daemon socket.

### Relationship to 100-Series

The 100-series delivers the single-agent platform: CLI, reviews, provider infrastructure, model aliases, pipeline executor, and the local daemon. This 200-series adds:

- Persistent task store (SQLite, daemon-owned)
- Daemon socket protocol for task lifecycle (post, claim, complete, fail)
- Capability-based routing (tasks tagged by what they need; agents declare what they can do)
- Multi-agent participation: Claude Code IDE, Codex IDE plugin, Hermes remote machine
- MCP tools for agent-side polling and result writing
- Ensemble review (fan-out same review to multiple models, synthesize)
- Anthropic API provider (Claude models without Max subscription, for CI and cost optimization)

---

## System Architecture

### Core Components

**Task Store** — SQLite database at `~/.config/squadron/workspace.db` (user-global) or `.squadron/workspace.db` (project-local, takes precedence). WAL mode enabled. Daemon holds the write connection; agents open read-only connections directly for low-latency polling. Schema:

```sql
tasks (
    id              TEXT PRIMARY KEY,   -- {project_hash}-{run_uuid}-{step}
    project_path    TEXT NOT NULL,      -- canonical absolute path, for isolation
    pipeline_run_id TEXT NOT NULL,
    step            TEXT NOT NULL,
    assigned_to     TEXT,               -- agent hint: "claude", "codex", null=any
    capabilities    TEXT,               -- JSON array: ["file_access","sandbox",...]
    status          TEXT NOT NULL,      -- pending|claimed|complete|failed
    payload         TEXT NOT NULL,      -- JSON: prompt, context, inputs
    result          TEXT,               -- JSON: output, findings, structured data
    created_at      TEXT NOT NULL,
    claimed_at      TEXT,
    completed_at    TEXT,
    timeout_at      TEXT                -- daemon requeues if claimed but not completed
)

events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    event       TEXT NOT NULL,          -- posted|claimed|completed|failed|requeued
    agent       TEXT,                   -- which agent acted
    ts          TEXT NOT NULL,
    detail      TEXT                    -- JSON, optional
)
```

Project isolation is via `project_path` — a single daemon and single DB serve multiple projects simultaneously. Agents filter by `project_path` when polling.

**Daemon (`sq serve`)** — Extended from current daemon. Gains:
- Owns `workspace.db`, holds the write connection in WAL mode
- Listens on Unix socket: `~/.config/squadron/daemon.sock`
- Accepts protocol messages: `post_task`, `claim_task`, `complete_task`, `fail_task`, `list_tasks`, `watch_task`
- Requeues stale claimed tasks (claimed but not completed within `timeout_at`)
- Auto-started by `sq run` if not already running (existing behavior, unchanged)

**Daemon Socket Protocol** — Newline-delimited JSON over Unix socket (local) or TCP over SSH tunnel (remote). Same message format either way — transport is the only difference. This makes Hermes participation a connection config change, not an architecture change.

```json
// post_task request
{"op": "post_task", "task": {"id": "...", "project_path": "...", "step": "...",
  "assigned_to": "claude", "capabilities": ["file_access"], "payload": {...},
  "timeout_seconds": 300}}

// claim_task request (atomic — daemon rejects if already claimed)
{"op": "claim_task", "task_id": "...", "agent": "claude-code-ide"}

// complete_task request
{"op": "complete_task", "task_id": "...", "result": {...}}
```

**Agent participation** — Any process that can connect to the daemon socket (or read `workspace.db` directly) is a participant:

- **Claude Code (IDE, interactive):** polls via `/sq:work` slash command or `squadron_check_work` MCP tool. Claims a pending task, executes it as an interactive session with full file/tool access, writes result via `squadron_complete_task` MCP tool.
- **Codex (IDE plugin):** same poll/claim/complete loop. Better suited for sandboxed execution and file manipulation. `assigned_to: "codex"` routes tasks to it preferentially.
- **Hermes (remote machine):** connects to local daemon via SSH tunnel. Same socket protocol. Picks up compute-heavy or long-running tasks. `assigned_to: "hermes"` routes accordingly.
- **`sq run` (CLI pipeline executor):** posts tasks via daemon socket, polls `workspace.db` read-only for result rows, advances pipeline when result appears. No SDK sessions spawned from CLI.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Participants                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Claude Code  │  │    Codex     │  │  Hermes (remote) │  │
│  │ (IDE, inter.)│  │ (IDE plugin) │  │  via SSH tunnel  │  │
│  │              │  │              │  │                  │  │
│  │ /sq:work     │  │ poll+claim   │  │  same socket     │  │
│  │ MCP tools    │  │ MCP tools    │  │  protocol        │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         └─────────────────┴────────────────────┘           │
│                           │ Unix socket / TCP               │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────┐
│              Squadron Daemon (sq serve)                      │
│                           │                                 │
│              ┌────────────▼──────────────┐                  │
│              │      Socket Server         │                  │
│              │  post/claim/complete/fail  │                  │
│              │  requeue on timeout        │                  │
│              └────────────┬──────────────┘                  │
│                           │ write                           │
│              ┌────────────▼──────────────┐                  │
│              │    workspace.db (SQLite)   │                  │
│              │    WAL mode, tasks+events  │                  │
│              └────────────┬──────────────┘                  │
│                           │ read-only (direct)              │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────┐
│              sq run (pipeline executor)                      │
│                                                             │
│   post task → poll workspace.db for result → advance step   │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Pipeline Step Execution (new model)

```
sq run my-pipeline
  │
  ├─ auto-start daemon if not running
  │
  ├─ for each step:
  │    post_task(step, payload, assigned_to, capabilities)
  │    poll workspace.db WHERE task_id=? AND status='complete'
  │    on result: extract output, feed to next step
  │
  └─ pipeline complete when all steps resolved
```

### Agent Work Loop

```
Claude Code (or Codex) in IDE:
  /sq:work  (or MCP tool: squadron_check_work)
    │
    ├─ read workspace.db: SELECT * FROM tasks
    │    WHERE project_path=? AND status='pending'
    │    AND (assigned_to IS NULL OR assigned_to='claude')
    │    ORDER BY created_at LIMIT 1
    │
    ├─ if task found:
    │    claim_task(id) via daemon socket  ← atomic, daemon rejects race
    │    execute task payload as interactive session
    │    complete_task(id, result) via daemon socket
    │
    └─ if no task: report idle
```

### Capability Routing

Tasks declare what they need; agents self-declare what they can do. Routing is a simple filter on the `capabilities` JSON array:

| Capability | Meaning | Preferred agent |
|---|---|---|
| `file_access` | Needs to read/write project files | Claude Code (IDE) |
| `sandbox` | Needs isolated execution environment | Codex |
| `compute` | Long-running or GPU-bound | Hermes |
| `review` | Structured review with findings output | any |
| *(none)* | Prompt-in, text-out | any |

`assigned_to` is a stronger hint (direct routing); `capabilities` is a filter (any capable agent may claim).

---

## Hermes Participation

Hermes connects to the local daemon via SSH tunnel:

```bash
# On Hermes: tunnel local port to local machine's daemon socket
ssh -L /tmp/squadron-remote.sock:~/.config/squadron/daemon.sock local-machine

# Squadron on Hermes uses the tunneled socket
SQUADRON_DAEMON_SOCK=/tmp/squadron-remote.sock sq work --agent hermes
```

`sq work` is a new CLI command (slice 222) that runs the poll/claim/complete loop as a standalone process — the Hermes-side worker. It's the same loop Claude Code runs via slash command, just as a persistent CLI process rather than a one-shot IDE invocation.

V1 uses SSH tunnel. Upgrade path (not in this initiative): daemon listens on TCP with mTLS, no tunnel needed.

---

## Anthropic API Provider (203)

Standalone slice, independent of task store. Implements `AnthropicAPIProvider` and `AnthropicAPIAgent` satisfying the existing `AgentProvider` / `Agent` Protocols. Enables Claude model use via `ANTHROPIC_API_KEY` without a Max subscription — critical for CI pipelines and cost-optimized runs.

Ships before the rest of the 200-series since it has no task-store dependency. Primary motivation post-June-15: pipeline steps that need Claude models can route to the Anthropic API provider instead of the Agent SDK, avoiding the credit constraint entirely for non-interactive use.

---

## MCP Exposure (208)

The MCP server exposes the task store to IDE agents via Claude Code's MCP tool mechanism. Tools:

- `squadron_check_work(project_path)` — returns next pending task for this project, or null
- `squadron_claim_task(task_id, agent)` — atomic claim via daemon socket
- `squadron_complete_task(task_id, result)` — write result via daemon socket
- `squadron_fail_task(task_id, error)` — mark failed, trigger requeue logic
- `squadron_list_tasks(project_path, status?)` — inspect queue state

The `/sq:work` slash command wraps `squadron_check_work` + `squadron_claim_task` into a single user-facing action.

---

## Ensemble Review (210)

Fan out the same review to multiple models, synthesize results. Implemented as a pipeline pattern on top of the task store — Squadron posts N identical review tasks with different `assigned_to` / model hints, waits for all N results, then posts a synthesis task. No new infrastructure needed beyond the task store.

Analysis dimensions: agreement frequency (findings across multiple reviewers = high-confidence signal), novel detection (finding unique to one reviewer), noise filtering (evaluator marks low-confidence findings from weaker models).

---

## Key Architectural Decisions

- **Pull-based, not push.** IDE plugins and interactive sessions cannot receive async push. All agents poll. SQLite read is fast enough; pipeline step cadence is seconds-to-minutes.
- **Daemon owns writes, agents read directly.** WAL mode makes direct reads safe and low-latency. No round-trip to daemon for polling — only for mutations (claim, complete).
- **One daemon, one DB, multiple projects.** `project_path` column isolates projects. No per-project daemon.
- **Transport-agnostic socket protocol.** Unix socket locally, TCP over SSH tunnel for Hermes. Same JSON protocol either way. Upgrade path to native TCP with mTLS requires no protocol change.
- **`sq run` no longer spawns SDK sessions.** Pipeline steps become task-store operations. SDK sessions are reserved for interactive IDE work where the user's subscription/credit applies naturally.
- **Message bus dropped.** The original 200-arch pub/sub bus solved a different problem (real-time agent-to-agent chat). The actual use case is pipeline step coordination, for which a task queue is simpler and more robust.
- **ADK, REST+WebSocket, subprocess agents dropped.** Out of scope for this model. Not ruled out forever — if a real-time chat use case emerges, a separate initiative is the right container.

---

## What Changed from Original 200-arch

The original design was a message bus / pub-sub system with a supervisor using OTP restart strategies, topology routing, ADK workflow integration, and REST+WebSocket exposure. That design assumed agents could receive push messages — which IDE plugins and interactive Claude Code sessions cannot.

The revised design replaces the bus with a task store, the supervisor with daemon-managed timeout/requeue, and topology routing with capability tags. The result is simpler, immediately usable from the existing IDE environment, and extensible to Hermes without infrastructure changes.

Slices from the original plan that are dropped: 201 (Supervisor), 202 (Message Bus Core), 204 (Multi-Agent Message Routing), 205 (Human-in-the-Loop as bus participant), 206 (Communication Topologies), 207 (ADK Integration), 209 (REST+WebSocket), 211 (Subprocess Agent Support).

Slices retained or adapted: 203 (Anthropic API Provider, unchanged), 208 (MCP Server, repurposed), 210 (Ensemble Review, unchanged), 212 (E2E Testing, rescoped).

New slices: task store schema and migrations, daemon socket server, `sq work` CLI command, `/sq:work` slash command, pipeline executor integration (post/poll replaces spawn), SSH tunnel documentation for Hermes.
