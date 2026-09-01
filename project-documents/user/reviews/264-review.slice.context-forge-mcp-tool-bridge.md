---
docType: review
layer: project
reviewType: slice
slice: context-forge-mcp-tool-bridge
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260831
dateUpdated: 20260831
reviewedSha: 054cb786765999a23c8cf5ea7ab60b5ef3577ed0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`isError` failure mode logs below the required observability floor"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md:145"
  - id: F002
    severity: concern
    category: failure-mode-handling
    summary: "Timeout teardown claim doesn't address npx grandchild-process survival"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md:124-126"
  - id: F003
    severity: note
    category: scope
    summary: "Curated tool set silently grows beyond the slice plan's named list"
    location: "project-documents/user/architecture/260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md:53"
  - id: F004
    severity: pass
    category: alignment
    summary: "Adapter claim matches architecture's stated design intent"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md:34-36"
  - id: F005
    severity: pass
    category: security
    summary: "CWD trust boundary and cwd-injection pattern correctly followed"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md:165-172"
  - id: F006
    severity: pass
    category: integration
    summary: "Registry/allowlist integration requires no changes to 262/263, consistent with registry-driven design"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md:174-184"
---

# Review: slice — slice 264

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] `isError` failure mode logs below the required observability floor

The project's failure-mode rule (review-code.md, Failure-Mode Enumeration) requires every identified failure mode to be observable "at WARNING+ or metric increment," not silent. The slice's own Failure Modes table (lines 141–147) has one row that violates this: `Server returns isError` is logged at DEBUG, justified only as "model-level error, not a bridge fault." That's a reasonable distinction to draw, but the design doc doesn't reconcile it against the explicit house rule it otherwise follows correctly for the other four rows (all WARNING). Either bump this row to WARNING or add one sentence explaining why business-level CF errors are exempt from the WARNING+ bar — right now it reads as an inconsistency rather than a deliberate, stated exception.

### [CONCERN] Timeout teardown claim doesn't address npx grandchild-process survival

The Data-flow and Failure-modes sections both assert that on timeout, "session teardown kills the subprocess" (lines 123–126, 144). The default launch command is `npx -y @context-forge/mcp` (line 156) — `npx` commonly forks the actual server as a child of itself, so an `asyncio.timeout`-triggered cancellation that terminates the directly-spawned process is not guaranteed to reach that grandchild on all platforms/npm versions (a known npx/signal-propagation gotcha). The design states the hang failure mode is fully handled but doesn't specify process-group termination (e.g., `start_new_session` + killing the group) or otherwise confirm the mcp SDK's stdio client accounts for this. As written this is an implicit assumption inside a section that otherwise explicitly enumerates failure handling — worth either verifying against the `mcp` SDK's subprocess management or calling out as a known residual risk.

### [NOTE] Curated tool set silently grows beyond the slice plan's named list

The slice plan names `set_phase`, `set_slice`, `build_context`, `prompt_get` as the curated subset (with "e.g.," so extension is permitted). The slice doc adds a fifth, `cf_workflow_status`, with a clear justification (state-mutating tools need a paired read). This is within the plan's "e.g." latitude and is well-reasoned (lines 106–109), not a violation — flagging only so the scope addition is visible to reviewers comparing against the plan's literal list.

### [PASS] Adapter claim matches architecture's stated design intent

The slice explicitly reuses the architecture's own framing ("MCP composition is an adapter, not a re-architecture") from arch §Technical Considerations and §Anticipated Slices (260-arch:72, 95), and the component layout (mcp_bridge.py generic, cf_tools.py CF-specific, one-way dependency) actually delivers that seam rather than just asserting it.

### [PASS] CWD trust boundary and cwd-injection pattern correctly followed

Architecture principle "CWD as the trust boundary" and "cwd injection... must not appear in the tool's JSON Schema" (260-arch:38, 71) are honored: the model never sees `projectId`/`projectPath`, and project identity resolves from the factory-bound `cwd` passed to `StdioServerParameters(cwd=...)`.

### [PASS] Registry/allowlist integration requires no changes to 262/263, consistent with registry-driven design

Matches the architecture's "Tool registry parallels action registry" principle (260-arch:40) and slice 263's registry-driven `validate_allowed_tools` — new `cf_*` names become valid YAML without touching the loop or validation layers, which is exactly the extension point the architecture describes.
