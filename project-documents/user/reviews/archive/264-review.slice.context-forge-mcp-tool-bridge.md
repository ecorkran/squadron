---
docType: review
layer: project
reviewType: slice
slice: context-forge-mcp-tool-bridge
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260831
dateUpdated: 20260831
reviewedSha: 054cb786765999a23c8cf5ea7ab60b5ef3577ed0
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "MCP bridge composed as an adapter through the descriptor protocol, exactly as the architecture specified"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes fully enumerated for the new I/O path with explicit handling strategies"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md"
  - id: F003
    severity: pass
    category: dependency-direction
    summary: "Dependency direction, integration points, and trust-boundary handling are correct"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md"
  - id: F004
    severity: note
    category: scope-management
    summary: "Fifth tool extends beyond the four named in the slice plan"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md"
  - id: F005
    severity: note
    category: under-specification
    summary: "Frontmatter metadata understates the slice's integration surface"
    location: "project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md"
---

# Review: slice — slice 264

**Verdict:** PASS
**Model:** moonshotai/kimi-k3

## Findings

### [PASS] MCP bridge composed as an adapter through the descriptor protocol, exactly as the architecture specified

The 260 architecture (Technical Considerations: "Async-first execution interface," "Registry vs. inline tools") designed the async-first execute interface precisely so that "MCP-bridged tools (slice 264) compose as adapters rather than requiring a re-architecture." The slice delivers exactly that: five `cf_*` descriptors registered through the existing 261 `register()`/`materialize()` path, no changes to `models.py`, `registry.py`, `builtin.py`, the 262 loop, or 263 validation. Design decision D1 explicitly anchors the choice (real MCP client over a CLI wrapper) to this architectural purpose. The slice also correctly scopes itself: the "optional, separate slice" boundary is respected — review-path activation is deferred to 265, session pooling and other-server bridging are explicitly out of scope.

### [PASS] Failure modes fully enumerated for the new I/O path with explicit handling strategies

The failure-mode table covers all required categories for the new stdio/subprocess I/O path: spawn failure, hang (cancelled via `asyncio.timeout` with subprocess teardown), timeout value logged, server-reported `isError` passthrough, and protocol/transport error mid-call (`McpError`, closed stream — the peer-disconnect case). Required-argument validation fails before any spawn. Each row names an observable signal (WARNING/DEBUG log or explicit result text) and is backed by a test, including a real stdio round-trip against a fake python MCP server. No "TBD" or implicit handling. This is the criterion the review most often fails on; here it passes cleanly, including the slice-909 lesson (no empty-success results).

### [PASS] Dependency direction, integration points, and trust-boundary handling are correct

`cf_tools.py` → `mcp_bridge.py` is one-directional; the transport helper has no CF knowledge, matching the architecture's adapter-separation intent. Integration points match what the providing slices expect: the factory receives the bound `cwd` (per the architecture's `cwd`-injection principle) and enforces it via `StdioServerParameters(cwd=...)`; tool schemas deliberately omit `projectId`/`projectPath`, preserving the architecture's CWD-as-trust-boundary principle; executors never raise (261's errors-are-values contract) and remain ordinary async `ToolExecutor`s to the 262 loop. The curated subset (no destructive CF surface) is consistent with the allowlist-not-denylist principle.

### [NOTE] Fifth tool extends beyond the four named in the slice plan

The slice plan entry names four tools (`cf_set_phase`, `cf_set_slice`, `cf_build_context`, `cf_prompt_get`); the slice ships five, adding `cf_workflow_status`. The justification is sound — state-mutating tools without a state reader force blind mutation — and the addition is trivially small and still within the architecture's "selected context-forge MCP operations" boundary. Noted as a documented deviation from the slice plan rather than a concern; if the slice plan is treated as authoritative, the plan entry should be updated to match.

### [NOTE] Frontmatter metadata understates the slice's integration surface

`interfaces: []` is empty despite the slice adding new registry tool names plus two config keys (`cf.mcp_command`, `cf.mcp_timeout_s`). Additionally, `dependencies: [261, 262]` omits 263, yet Success Criterion 1 and the Integration Points section rely on 263's `validate_allowed_tools` surface ("no changes; registry-driven"). The integration assertion is correct (no code dependency), but the metadata doesn't reflect the validation dependency needed to verify Success Criterion 1. Metadata hygiene only; no design impact.
