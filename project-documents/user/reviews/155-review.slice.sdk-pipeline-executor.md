---
docType: review
layer: project
reviewType: slice
slice: sdk-pipeline-executor
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/155-slice.sdk-pipeline-executor.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260404
dateUpdated: 20260404
findings:
  - id: F001
    severity: fail
    category: scope-creep
    summary: "Conversation State Across Steps Violates Architecture Boundary"
  - id: F002
    severity: concern
    category: architectural-boundaries
    summary: "Undocumented Architectural Component"
  - id: F003
    severity: concern
    category: integration-points
    summary: "Compact Action Mechanism Changed Without Architecture Update"
  - id: F004
    severity: concern
    category: layer-responsibilities
    summary: "Dual Dispatch Path in Actions"
  - id: F005
    severity: note
    category: scope-creep
    summary: "Valid Problem Statement, Misplaced Solution"
---

# Review: slice — slice 155

**Verdict:** FAIL
**Model:** z-ai/glm-5

## Findings

### [FAIL] Conversation State Across Steps Violates Architecture Boundary

The architecture document explicitly states that conversation persistence is out of scope for initiative 140: "Conversation Persistence (125) → moved to initiative 160. Pipeline steps are stateless in 140." The architecture further emphasizes: "Pipeline steps use fresh agents by default — no conversation state carries between steps. The pipeline state file is the continuity mechanism, not conversation history."

This slice explicitly implements persistent conversation context across steps: "Creating a new ClaudeSDKClient per step would lose conversation context between steps. A persistent client preserves the context window, allowing later steps to reference earlier work." This directly contradicts the architectural boundary. The slice is numbered in the 140 series and references `parent: 140-slices.pipeline-foundation.md`, placing it squarely within initiative 140, yet it implements a 160-scope feature.

### [CONCERN] Undocumented Architectural Component

The slice introduces `SDKExecutionSession` as a new core abstraction that wraps `ClaudeSDKClient` and manages lifecycle across steps. The component architecture diagram in the architecture document shows no such component. This session wrapper sits between the executor and actions, changing the data flow significantly. While the action protocol extension (`sdk_session` field in `ActionContext`) is modest, the architectural impact of a persistent session manager deserves explicit architecture-level approval before implementation.

### [CONCERN] Compact Action Mechanism Changed Without Architecture Update

The architecture specifies that the compact action "Issue parameterized compaction instructions" via `ContextForgeClient` (slice 126). This slice changes the mechanism to use the server-side `context_management` API instead, stating: "Compact steps don't call CF for compaction. They configure `context_management` on the SDK session." While this may be technically superior, it represents a significant change to how the compact action fulfills its responsibility without corresponding architecture document updates.

### [CONCERN] Dual Dispatch Path in Actions

The dispatch action gains a conditional branching path: "When an `SDKExecutionSession` is present in the `ActionContext`, it uses the session's client instead of spawning a new agent." This creates two fundamentally different execution paths through the same action, with different semantics (persistent session vs. one-shot agent). The architecture defines actions as having single responsibilities, but this bifurcation means the dispatch action now has two modes with different behavioral contracts.

### [NOTE] Valid Problem Statement, Misplaced Solution

The distinction between SDK execution mode (autonomous, straight CLI) and prompt-only mode (interactive, human-in-the-loop) is architecturally sound and valuable. The environment detection and error messaging for Claude Code session detection are good UX. However, implementing this mode by introducing persistent conversation state across steps conflates two separable concerns: (1) the execution entry point and (2) conversation persistence. The SDK execution mode could be implemented with stateless steps, using only the pipeline state file for continuity as the architecture prescribes.
