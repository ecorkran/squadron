---
docType: architecture
archIndex: 280
component: shared-agent-artifact-store
initiative: shared-agent-artifact-store
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [100, 140, 260]
dateCreated: 20260513
dateUpdated: 20260519
status: not_started
---

# Architecture: Shared Agent Artifact Store

## Overview

Squadron pipelines are stateless between steps: each step receives a fully-assembled prompt, produces text output, and the executor moves on. For single-model, single-agent pipelines this is sufficient — the pipeline YAML and template system provide enough context continuity. But multi-model, multi-agent pipelines expose a gap: agents running in separate steps (or separate processes) have no shared medium through which to record what they did, what they found, what they changed, or what is left to do.

This initiative introduces a **shared agent artifact store** — a lightweight SQLite-backed persistent store that any agent in a pipeline (or across pipelines on the same project) can write structured artifacts to and read from. It is not a message bus (that is initiative 200) and not conversation history (that is initiative 180). It is a **coordination log**: structured, queryable, durable across runs, and accessible to any agent that knows the project root.

**Primary motivation.** The Codex agentic provider (`CodexAgent` / `AsyncCodex`) operates by executing file-level side effects in a working directory. It does not return structured output — its `final_response` is a human-readable summary. A subsequent reviewer (Claude, Codex, or another model) cannot know what files were changed, what tasks were completed, or what was left unfinished from the response text alone. A shared store lets the implementer write a structured entry ("T2-T5 complete, files A/B/C modified, tests passing, T6 blocked on X") and the reviewer read it before starting.

**Secondary motivations.**
- Cross-run continuity: a long implementation across multiple `sq run` invocations can resume from the last recorded checkpoint without re-reading the entire codebase.
- Multi-model review chains: a Codex implementer, Claude reviewer, and minimax summarizer can each append to the same artifact chain and the next step in the pipeline reads only the relevant entries.
- Observability: operators can query the store to see what any agent did on a given run without parsing unstructured log files.

**Explicit non-goals.**
- Real-time messaging between live agents (initiative 200).
- Conversation history / session replay for retry loops (initiative 180).
- Replacing the pipeline state file (run JSON) — that remains the authoritative execution record.
- A general-purpose key-value store or ORM. The schema is narrow and purpose-built.

---

## Design Goals

- **Minimal schema.** Store artifacts (text blobs with structured metadata), not a relational model of the world. Agents write what they did; the store records it faithfully.
- **Append-only for agent writes.** Agents append entries; they do not update or delete existing entries. This makes the store a reliable audit log and prevents concurrent-write conflicts.
- **Queryable by pipeline run, agent, artifact type, and step name.** The primary query patterns are "what did the implementer write for this run?" and "what is the latest finding for artifact X?".
- **Zero config for the common case.** Store location defaults to `{project_root}/.squadron/artifacts.db`. No setup required; the file is created on first write.
- **Agent-agnostic write interface.** Any agent (Claude SDK, Codex, OpenAI-compatible) can write to the store via a tool call or a post-step hook — no special SDK required.
- **Forward-compatible with initiative 200.** The store schema and access pattern should not conflict with the message bus architecture. The store is for durable artifacts; the bus is for ephemeral coordination signals.

---

## Core Concepts

### Artifact

An artifact is a single named, typed entry written by an agent during a pipeline run. Fields:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Auto-assigned on insert |
| `run_id` | str | Pipeline run ID (from existing state) |
| `step_name` | str | Pipeline step that produced this artifact |
| `agent_name` | str | Agent identifier (e.g. `codex-impl`, `claude-reviewer`) |
| `artifact_type` | str | Semantic type: `implementation_summary`, `review_findings`, `checkpoint`, `task_progress`, `devlog` |
| `content` | str | Free-form text (markdown, JSON, or plain) |
| `metadata` | JSON | Optional structured payload (file list, test results, task counts, etc.) |
| `created_at` | datetime | UTC timestamp |

### Artifact Types (initial set)

- **`implementation_summary`** — What an implementer agent did: tasks completed, files changed, test status, blockers.
- **`review_findings`** — Structured review output: verdict, findings list, severity breakdown.
- **`task_progress`** — Checklist state: tasks attempted, completed, skipped, with reasons.
- **`checkpoint`** — An agent's self-declared save point: "I have completed up to T5; T6 onwards is next."
- **`devlog`** — Free-form session notes, equivalent to what a human would write in DEVLOG.md.

### Store Location

Default: `{cwd}/.squadron/artifacts.db` (SQLite file, created on first write).

Override via `SQUADRON_ARTIFACTS_DB` environment variable or `artifacts_db` in `~/.config/squadron/config.toml`.

---

## Write Interface

Two write paths:

**1. Post-step hook (automatic).** After any step completes, the executor calls an optional `artifact_writer` hook if configured on the step. The hook receives the step result and writes a structured artifact. This is the primary path for non-agentic steps (Claude SDK design/review/summary steps where the output is captured text).

**2. Tool call (agent-initiated).** For agentic steps (Codex, tool-use-enabled OpenAI-compatible), a `write_artifact` tool is added to the tool registry (initiative 260). The agent calls it explicitly as part of its response — e.g. "I completed T2-T5, here is my implementation summary" → `write_artifact(type="implementation_summary", content="...", metadata={...})`. This is the primary path for Codex steps.

---

## Read Interface

Three read patterns:

**1. Template injection.** The template renderer gains a `artifacts.latest(run_id, type)` and `artifacts.for_step(run_id, step_name)` helper. Pipeline templates can inject prior artifact content directly into the prompt — e.g. the reviewer template injects the implementer's `implementation_summary` so the reviewer knows what was done.

**2. CLI query.** `sq artifacts list [--run <id>] [--type <type>] [--step <step>]` — human-readable table of artifacts for a run.

**3. Direct Python API.** `ArtifactStore.query(run_id, ...)` returns a list of `Artifact` objects. Used by post-step hooks and test fixtures.

---

## Integration Points

### With Codex (CodexAgent)

The primary use case. After a `codex-agent` step completes, the `final_response` text is written as an `implementation_summary` artifact via the post-step hook. If the Codex thread called `write_artifact` as a tool during execution, those entries are already in the store; the post-step hook writes the summary only if no `implementation_summary` exists for that step yet.

The subsequent review step's template reads the `implementation_summary` artifact and injects it into the reviewer prompt alongside the slice design and code diff.

### With Pipeline Templates

A new template variable family: `{artifacts.impl_summary}`, `{artifacts.review_verdict}`, etc. These resolve to the latest matching artifact for the current run. If no artifact exists (e.g. first run), the variable resolves to an empty string — not an error.

### With `sq run --explain`

`--explain` gains an optional `--artifacts` flag that also prints the artifact store entries for the last run of the specified pipeline. Useful for post-run inspection without reading the DB directly.

### With Initiative 200 (Multi-Agent Communication)

The artifact store is a complement, not a replacement. When initiative 200's message bus is implemented, the bus handles real-time coordination signals ("reviewer ready", "@implementer please fix T6") while the store holds durable content artifacts ("here is what I implemented"). The store's `run_id` links artifacts to message bus conversation threads.

---

## Schema (SQLite)

```sql
CREATE TABLE artifacts (
    id          TEXT PRIMARY KEY,          -- UUID v4
    run_id      TEXT NOT NULL,
    step_name   TEXT NOT NULL,
    agent_name  TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    TEXT,                      -- JSON, nullable
    created_at  TEXT NOT NULL              -- ISO 8601 UTC
);

CREATE INDEX idx_artifacts_run     ON artifacts(run_id);
CREATE INDEX idx_artifacts_run_type ON artifacts(run_id, artifact_type);
CREATE INDEX idx_artifacts_step    ON artifacts(run_id, step_name);
```

Single table, three indices. No foreign keys, no migrations in v1 — schema is additive.

---

## Failure Modes

| Path | Mode | Strategy |
|---|---|---|
| DB write fails (disk full, permissions) | `sqlite3.OperationalError` | Log at WARNING, do not fail the pipeline step. Artifact loss is preferable to execution failure. |
| DB read fails in template renderer | Missing artifact | Resolve to empty string. Log at DEBUG. |
| Concurrent writes from parallel steps | SQLite write lock contention | SQLite WAL mode; writes are append-only and fast. Acceptable for pipeline-scale concurrency. |
| `artifacts.db` missing on read | File not found | Return empty result set, do not raise. |
| `write_artifact` tool called with invalid type | Unknown artifact_type | Accept and store with the provided type. The registry is advisory, not enforced. |

---

## Slice Outline

Planned as three slices:

1. **Store foundation** — `ArtifactStore`, SQLite schema, `Artifact` dataclass, `write` / `query` API, CLI `sq artifacts list`. No pipeline integration yet. Fully tested in isolation.

2. **Pipeline integration** — Post-step hook wiring in executor, `write_artifact` tool in tool registry (coordinates with initiative 260 tool foundation), template variable injection (`artifacts.*`). Codex post-step hook writes `implementation_summary`.

3. **End-to-end demo and `--explain` integration** — P6 pipeline running with `codex-agent` implementer + Claude reviewer, reviewer template reads implementer artifact, `sq run --explain --artifacts` output. Includes fixture pipeline for CI verification.

---

## Risk Notes

- **SQLite for multi-process access:** WAL mode handles concurrent readers + one writer safely at pipeline scale. Not designed for high-concurrency server use — that is a future concern.
- **Artifact content size:** No size limit in v1. Implementer summaries for large task files could be several KB. Acceptable for SQLite at project scale.
- **Schema evolution:** Additive-only policy for v1. New artifact types and metadata fields are backward-compatible. Breaking schema changes require a migration tool (deferred).
