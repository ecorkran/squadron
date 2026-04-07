---
docType: slice-design
parent: 200-slices.multi-agent-communication.md
project: squadron
status: not-started
dateCreated: 20260218
dateUpdated: 20260218
slice: supervisor-component
---

## Architecture Note from Parent:
This slice and the next should combine to cover the two Supervisor slices described in the parent document.  The resulting slice design should be split into this document and a 107-slice.supervisor-recovery.md


### Agent Supervision

The core engine includes a supervision layer responsible for detecting agent failures and applying configurable recovery strategies. This is a separate concern from agent communication and topology — agents do not supervise each other. An orthogonal Supervisor component monitors agent health and manages restarts independently of conversation flow.

This separation is a deliberate architectural choice. In hierarchical orchestration systems, the "lead" or "orchestrator" agent typically acts as both coordinator and supervisor. In peer-based topologies — where no agent is inherently in charge — supervision must be a distinct system concern rather than a role assigned to a participant. This keeps the topology layer clean: topology defines who talks to whom, supervision defines what happens when someone stops talking.

**Design principles (adapted from OTP/BEAM patterns for Python/asyncio):**

- **Let it crash, then recover.** Rather than wrapping every LLM call in defensive try/except chains, agents implement the happy path. The supervisor detects failures (crashed asyncio tasks, timeouts, bad state) and applies a restart strategy. This produces cleaner agent code and centralizes recovery logic.

- **Restart strategies.** Configurable per agent group:
  - `one_for_one` — Restart only the failed agent. Other agents continue unaffected. Default for independent peer agents.
  - `one_for_all` — Restart all agents in a supervision group. Appropriate when agents share conversational state and a partial restart would leave inconsistent context.
  - `rest_for_one` — Restart the failed agent and all agents registered after it. Useful for pipeline/sequential topologies where downstream agents depend on upstream state.

- **Circuit breaker.** Max restarts within a time window (e.g., 3 restarts in 60 seconds). If exceeded, the agent is marked `failed` and the supervisor emits an event rather than continuing to thrash. This prevents infinite restart loops from a persistently broken LLM provider or malformed agent configuration.

- **State recovery policy.** On restart, an agent either:
  - **Clean slate** — Fresh agent instance, no conversation history. Simple, predictable, matches OTP semantics most closely.
  - **Conversation resume** — Agent restarts with its message history preserved from the message bus. Appropriate when accumulated context is valuable and the failure was transient (e.g., a single timeout).
  - Policy is configurable per-agent at spawn time.

- **Health detection.** The supervisor monitors:
  - asyncio task state (done/cancelled/exception)
  - Response timeout thresholds (agent in `processing` state beyond configurable limit)
  - Explicit failure signals from providers (auth failures, rate limits, model errors)

**Agent states** (extends the registry's existing state tracking):

```
idle → processing → idle          (normal cycle)
processing → restarting → idle    (supervisor recovery)
processing → failed               (circuit breaker tripped)
terminated                        (graceful shutdown, not supervised)
```

**Supervisor events** are published to the message bus, making them observable by the CLI (`observe` command), other agents, and external interfaces. Events include: `agent_restarted`, `agent_failed`, `restart_limit_exceeded`.
