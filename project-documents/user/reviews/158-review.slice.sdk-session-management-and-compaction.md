---
docType: review
layer: project
reviewType: slice
slice: sdk-session-management-and-compaction
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/157-slice.sdk-session-management-and-compaction.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260406
dateUpdated: 20260406
findings:
  - id: F001
    severity: concern
    category: architectural-alignment
    summary: "SDK compaction mechanism differs from architecture specification"
    location: 140-arch.pipeline-foundation.md (SDK execution mode section)
  - id: F002
    severity: pass
    category: model-resolution
    summary: "Model field on compact step aligns with resolution cascade"
  - id: F003
    severity: pass
    category: component-boundaries
    summary: "Session ownership follows architecture's layer responsibilities"
  - id: F004
    severity: pass
    category: data-flow
    summary: "ActionResult outputs align with architecture"
  - id: F005
    severity: note
    category: feature-boundary
    summary: "PreCompact hook is quality-of-life within scope"
  - id: F006
    severity: pass
    category: architectural-principles
    summary: "Maintains logical statelessness of pipeline steps"
  - id: F007
    severity: note
    category: documentation
    summary: "Architecture should document SDK compaction as session rotation"
---

# Review: slice — slice 157

**Verdict:** CONCERNS
**Model:** z-ai/glm-5

## Findings

### [CONCERN] SDK compaction mechanism differs from architecture specification

The architecture document states: "SDK execution mode (slice 155): A single `ClaudeSDKClient` session spans the pipeline run. This enables per-step model switching via `set_model()` and server-side compaction via `context_management`."

The slice correctly identifies that the Agent SDK doesn't expose the `context_management` API and proposes session rotation as an alternative. This is a sound technical decision, but it changes the documented architectural approach. The architecture should be updated to reflect that SDK mode uses session-rotate compaction (switch model → query → disconnect → reconnect with summary) rather than `context_management`.

### [PASS] Model field on compact step aligns with resolution cascade

The slice adds an optional `model` field to the compact step for specifying a summarization model. This correctly integrates with the architecture's model resolution chain: "Every model reference is an alias resolved through the model alias registry." The validation approach reuses `_validate_model_alias`, maintaining consistency.

### [PASS] Session ownership follows architecture's layer responsibilities

The architecture shows actions as the execution layer with `SDKExecutionSession` as the runtime optimization. The slice's decision to have `SDKExecutionSession.compact()` own the full rotate lifecycle (Option A: "Session replaces its own client") keeps lifecycle logic in the appropriate layer. The executor's reference to the session remains valid without needing to know about the client swap.

### [PASS] ActionResult outputs align with architecture

The `ActionResult(success=True, outputs={"summary": ..., "instructions": ...})` structure follows the architecture's description that `ActionResult` carries "output artifacts (files, structured data), and metadata for downstream steps." The summary being available for logging and diagnostics is appropriate.

### [NOTE] PreCompact hook is quality-of-life within scope

The `PreCompact` hook wiring for interactive `/compact` usage is described as "quality-of-life" and "best-effort." The architecture doesn't explicitly discuss hook registration, but this fits within the SDK execution mode scope and the stated goal of supporting interactive pipeline sessions. The slice correctly identifies this as a safety net for long individual steps and a UX improvement rather than the primary compaction mechanism.

### [PASS] Maintains logical statelessness of pipeline steps

The architecture states: "Pipeline steps are logically stateless — the pipeline state file is the continuity mechanism across checkpoints, interruptions, and resume." The slice's session rotation approach preserves this principle: the new session starts with assembled context (the summary), making resume possible without depending on the old conversation's persisted state.

### [NOTE] Architecture should document SDK compaction as session rotation

When updating the architecture document, consider replacing the reference to `context_management` with a description of the session rotation pattern:
1. Current session switches to summarization model
2. Compact instructions sent as query
3. Summary captured from response
4. Old session disconnected
5. New session created with summary as opening context

This documents what the slice implements and provides guidance for future maintainers.
