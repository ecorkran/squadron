---
docType: slice-design
slice: sdk-client-warm-pool
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [foundation, sdk-agent-provider, agent-registry, cli-foundation]
interfaces: [review-workflow-templates, end-to-end-testing]
status: deferred
dateCreated: 20260220
dateUpdated: 20260220
---

# Slice Design: SDK Client Warm Pool — DEFERRED

## Status: Deferred

This slice was deferred during design after SDK research revealed that the original warm pool concept (pre-initializing persistent `ClaudeSDKClient` instances) is not viable with the current SDK architecture. The slice should be revisited as a **session cache with agent profile management** once Review Workflow Templates (slice 15) are in active use and cold-start latency data is available from real review workflows.

## Deferral Rationale

### Original Assumption (Invalid)

The slice plan assumed `ClaudeSDKClient` is a long-lived, connectable process that could be pre-initialized and held in a pool. The design called for checkout/return semantics where a warm client is handed to a new agent, eliminating the ~20-30s cold-start penalty.

### What SDK Research Revealed

The Claude Agent SDK does not maintain persistent client processes. Each `query()` call spawns a fresh subprocess (Go binary + Node runtime), and configuration (`ClaudeAgentOptions`) is serialized into CLI arguments at spawn time. Key findings:

- **No persistent connectable client.** There is no long-lived process to keep warm.
- **Options are baked in at spawn.** System prompt, allowed tools, cwd, MCP servers, and permission mode are fixed per `query()` invocation. Only model, permission mode, and max thinking tokens are mutable at runtime (streaming mode only).
- **Cold-start cost is real but architectural.** The 2-12s+ overhead (up to 20-30s on some platforms) comes from subprocess spawn + project context loading + tool initialization + MCP server setup, not from a connection handshake that could be pooled.
- **Session resume exists but still spawns a new process.** `resume` with `forkSession: true` preserves conversation context from a prior session, but does not eliminate subprocess startup cost.

### Why Defer (Not Cancel)

The optimization is still valuable — just needs a different implementation approach. During active development sessions, architectural and task reviews run 1-4 times per hour. At that frequency, 5-15s cold starts per review are meaningful friction.

The viable approach is **session caching with agent profiles**:

1. Define a small, stable set of agent profiles (arch-reviewer, task-reviewer, code-reviewer-python, etc.)
2. Pre-warm sessions per profile: run an initial `query()` that loads project context, reads key files, establishes orientation — capture `session_id`
3. On review request, `resume` with `forkSession: true` + the real task. The forked session inherits all context from the warm-up, so the agent skips the "let me first understand the project" phase.

This doesn't eliminate subprocess startup, but it amortizes the agent orientation time — which is often the larger portion of latency for review tasks.

### Prerequisites for Revisiting

- **Review Workflow Templates (slice 15) in active use.** Need real profile definitions and usage patterns before optimizing.
- **Cold-start latency data.** Measure actual per-review overhead to quantify the improvement.
- **SDK evolution check.** The SDK may add persistent process support or faster startup, changing the optimization landscape.

### M1 Completion Note

The original slice plan designated this slice as completing M1. With deferral, **M1 is considered complete at slice 103 (CLI Foundation)**. The M1 value proposition — spawn an SDK agent, give it a task, see structured output from the terminal — is fully delivered without the warm pool.

## SDK Research Sources

Research conducted 2026-02-20 via Anthropic Agent SDK documentation and GitHub issues. Key references:

- Agent SDK overview: `platform.claude.com/docs/en/agent-sdk/overview`
- Sessions documentation: `platform.claude.com/docs/en/agent-sdk/sessions`
- TypeScript SDK reference: `platform.claude.com/docs/en/agent-sdk/typescript`
- TypeScript V2 preview: `platform.claude.com/docs/en/agent-sdk/typescript-v2-preview`
- GitHub issues on startup overhead: `anthropics/claude-agent-sdk-typescript#34`, `anthropics/claude-agent-sdk-typescript#55`

## Future Design Direction

When this slice is revisited, the design should address:

- **Profile definition format**: How agent profiles (system prompt, tools, cwd, project context) are declared — likely as config files or as part of review template definitions from slice 15.
- **Session lifecycle management**: How pre-warmed sessions are created, stored, and invalidated (e.g., when project files change, the cached context is stale).
- **Scope of pre-warming**: Whether the initial warm-up query should just load context passively, or actively scan/index project structure.
- **CLI integration**: Whether `pool warm` becomes `profile warm` or integrates into the review command directly.
- **Staleness detection**: Project file changes should invalidate cached sessions. A file-watcher or timestamp check could trigger re-warming.
