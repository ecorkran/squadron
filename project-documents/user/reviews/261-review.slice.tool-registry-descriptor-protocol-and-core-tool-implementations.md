---
docType: review
layer: project
reviewType: slice
slice: tool-registry-descriptor-protocol-and-core-tool-implementations
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260825
dateUpdated: 20260825
reviewedSha: 55af6b31b80506d825d7a232860b554e744af51b
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Descriptor protocol matches architecture specification exactly"
    location: "project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md:84-98"
  - id: F002
    severity: pass
    category: scope
    summary: "Scope boundary correctly excludes agent/provider/pipeline changes"
    location: "project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md:49-56"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Path-escape and other tool-internal failure modes aren't specified to log at WARNING+"
    location: "project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md:146-183"
  - id: F004
    severity: concern
    category: dependency-direction
    summary: "Dependency list mismatch between slice plan and slice design frontmatter"
    location: "project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md:6"
  - id: F005
    severity: note
    category: scope
    summary: "`list_tools()` extends the registry API beyond what the architecture specifies"
    location: "project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md:45"
---

# Review: slice — slice 261

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Descriptor protocol matches architecture specification exactly

`ToolDescriptor` (name/description/parameters/factory) and the factory→async-executor pattern reproduce arch §Technical Considerations "Tool descriptor protocol" and "`cwd` injection" precisely, including the rationale for keeping `cwd` out of the JSON Schema so the model can't override it.

### [PASS] Scope boundary correctly excludes agent/provider/pipeline changes

The "Out" list and Success Criterion 10 match the architecture's Anticipated Slices description of 261 ("No agent changes; tools are testable in isolation") and correctly push agent/provider wiring to 262/263 — dependency direction is downstream-consumer-correct.

### [CONCERN] Path-escape and other tool-internal failure modes aren't specified to log at WARNING+

The project's Failure-Mode Enumeration rule requires each identified failure mode to be independently *observable* (log at WARNING+ or metric increment), not just returned as data. This slice's Error Handling section only specifies `logger.exception` at ERROR for the unexpected top-level `except Exception` catch-all; the *expected* failure paths (jail/path-escape rejection, missing file, permission denied, bash timeout, non-zero exit) are only surfaced as `ToolResult(is_error=True, ...)` back to the caller. Per arch §"Loop visibility via logging," tool-call results are logged at DEBUG by the 262 loop — that's not WARNING+, and it doesn't exist yet at the point 261 ships. A sandbox-escape attempt in particular is a security-relevant event (arch calls CWD "the trust boundary") that an operator should be able to see without `-vv` DEBUG logs; today it's silent except to the model that triggered it. Worth an explicit WARNING-level log (or metric) at minimum for jail violations, decided in this slice rather than deferred implicitly to 262.

### [CONCERN] Dependency list mismatch between slice plan and slice design frontmatter

The slice-plan document (`260-slices...md`, entry 1) states "Dependencies: [100, 140]" for slice 261, but this design doc's frontmatter declares `dependencies: []`, and the Integration Points section reinforces "Consumes from Other Slices: Nothing." The technical content genuinely supports zero artifact-level dependencies (stdlib-only, no imports from prior initiatives), so the design's `[]` is plausibly correct — but the contradiction with the plan is unexplained. Since dependency fields drive sequencing/gating tooling, this should be reconciled explicitly (either correct the plan, or note in the design why the plan's [100,140] doesn't translate to an artifact dependency) rather than left as a silent discrepancy.

### [NOTE] `list_tools()` extends the registry API beyond what the architecture specifies

Architecture's Registry API is explicitly `register(descriptor)`, `lookup(name) -> descriptor | None`, `materialize(names, cwd) -> dict[name, executor]` (arch line 70). The slice adds `list_tools()`. It's well-justified (263 needs it for YAML validation, and it mirrors the existing `list_providers()` pattern) and doesn't conflict with any stated principle, but it's an addition the parent architecture doesn't mention — worth a one-line note back into the architecture doc for traceability rather than only appearing in the slice.
