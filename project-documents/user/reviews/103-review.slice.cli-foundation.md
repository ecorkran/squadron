---
docType: review
layer: project
reviewType: slice
slice: cli-foundation
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/103-slice.cli-foundation.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260327
dateUpdated: 20260327
---

# Review: slice — slice 103

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Package namespace mismatch with architecture document

**Description**: The slice specifies the CLI package at `src/orchestration/cli/` with entry point `orchestration`, while the architecture document shows it at `src/squadron/cli/` with CLI named `sq`. The slice frontmatter shows `project: squadron`, which matches the architecture, but the package path uses `orchestration` instead of `squadron`.

Specific reference from slice:
> Package Structure: `src/orchestration/cli/` and `pyproject.toml` script entry: `orchestration = "orchestration.cli.app:app"`

Architecture document shows:
> Project structure: `src/squadron/cli/` and infrastructure section references: `sq` CLI commands

The slice notes it is "completing Milestone 1" with `orchestration` as the command name, but the architecture document explicitly states `sq` CLI commands. This could indicate either:
1. The slice is using a different namespace convention than the architecture prescribes
2. The project name or CLI command name was reconsidered between architecture and slice planning

This inconsistency should be resolved for consistency with the architecture unless the parent slice plan document explicitly overrides this.

### [PASS] CLI layer responsibility and design aligns with architecture

The slice correctly implements the CLI as a thin interface layer above the core engine. The design matches the architecture's intent: CLI commands delegate to the Agent Registry, which manages agent lifecycle through providers. The four commands (spawn, list, task, shutdown) are appropriate for M1.

### [PASS] Dependency direction is correct and architecturally sound

The CLI correctly depends on:
- **Agent Registry** (slice 102): Primary runtime dependency for all agent operations
- **Foundation** (slice 100): Shared models (AgentConfig, AgentState, Message, etc.)
- **SDK Agent Provider**: Accessed through the registry/provider registry pattern, not imported directly

This respects the architectural invariant: "the core engine never depends on provider internals."

### [PASS] Async bridge pattern follows standard Typer conventions

The slice documents the `asyncio.run()` bridge pattern for synchronous Typer handlers calling async registry methods. This is the standard, well-understood approach and appropriate for a CLI tool that doesn't need a persistent event loop.

### [PASS] Exclusions appropriately scoped to current slice

The slice correctly defers:
- `chat` command (requires message bus - slice 6+)
- `observe` command (requires multi-agent routing - slice 8)
- `pool` command (SDK client warm pool - slice 5)
- `review` command (workflow templates - slice 15)
- `workflow` commands (ADK integration - slice 12)
- Streaming output (requires message bus patterns - slice 9)

These align with the stated M1 milestone: "a developer can spawn an SDK agent, give it a task, and see structured output."

### [PASS] Error handling maps correctly to architectural error types

The error translation table correctly maps CLI user messages to architectural error types:
- `AgentNotFoundError` / `AgentAlreadyExistsError` (from registry - slice 102)
- `ProviderError` / `ProviderAuthError` (from foundation/provider layer)

This maintains the architectural principle of translating low-level errors to user-friendly messages at the interface layer.
