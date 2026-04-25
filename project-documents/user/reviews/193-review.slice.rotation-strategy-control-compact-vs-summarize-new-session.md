---
docType: review
layer: project
reviewType: slice
slice: rotation-strategy-control-compact-vs-summarize-new-session
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/193-slice.rotation-strategy-control-compact-vs-summarize-new-session.md
aiModel: moonshotai/kimi-k2.5
status: complete
dateCreated: 20260422
dateUpdated: 20260422
findings:
  - id: F001
    severity: concern
    category: architecture/layer-boundary
    summary: "Layer responsibility violation - Foundational pipeline action modification"
    location: CompactStepType.expand(), CompactAction implementation
  - id: F002
    severity: concern
    category: architecture/infrastructure-scope
    summary: "Scope boundary - Core executor capability discovery"
    location: SessionCapabilities dataclass, executor session initialization hook
  - id: F003
    severity: concern
    category: dependencies/boundaries
    summary: "Dependency direction and undocumented foundational changes"
    location: Integration Points section
  - id: F004
    severity: pass
    category: alignment/goals
    summary: "Alignment with conversation persistence goals"
  - id: F005
    severity: note
    category: design-quality
    summary: "Clean separation of concerns between actions"
---

# Review: slice — slice 193

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.5

## Findings

### [CONCERN] Layer responsibility violation - Foundational pipeline action modification

The architecture document explicitly states: "No 140 code is modified. 180 registers new strategies, new resolver backends, and new action behaviors through the registries 140 establishes." This slice violates that boundary by modifying the behavior of `CompactStepType` ("no longer expands to `summary(emit=[rotate])`") and fundamentally restructuring `CompactAction` from a thin wrapper into an environment-aware dispatch mechanism. These are changes to Pipeline Foundation (140) constructs, not extensions through 140's registries. The slice effectively modifies how existing YAML syntax (`compact:`) is interpreted at the foundation level, which must either be done within 140 or require an architecture amendment allowing 180 to modify action expansion logic.

### [CONCERN] Scope boundary - Core executor capability discovery

The slice introduces `SessionCapabilities` and SDK slash-command capability probing that hooks into the executor's session initialization ("Capability probe hook — called once per session in the executor"). This is foundational infrastructure for the pipeline execution environment (140-level), not intelligence-layer heuristics (180-level). The architecture describes 180 as providing "judgment" (convergence, pools, escalation) atop 140's "machinery." Capability discovery is machinery—it should be defined in 140 or a dedicated infrastructure slice, with 180 consuming the capability information, not defining the discovery mechanism.

### [CONCERN] Dependency direction and undocumented foundational changes

The slice lists dependencies on 149, 161, 164, and 166 but omits 140-arch.pipeline-foundation despite making foundational changes to action interpretation and step expansion. Furthermore, the slice provides `SessionCapabilities` to "Other Slices" including 188 (conversation persistence). Since conversation persistence is a defined capability of 180, and 188 is presumably also in 180, this creates a dependency where 180 slices are providing core infrastructure to each other that should be established at the 140 foundation level. This suggests the infrastructure belongs in 140, not scattered across 180 slices.

### [PASS] Alignment with conversation persistence goals

The slice's primary value proposition—enabling the `compact` action to function in prompt-only environments (IDE, Claude Code CLI) via `/compact` dispatch—directly supports the "Conversation Persistence" capability defined in the architecture. The architecture section "Interaction with Compaction" explicitly depends on the `compact` action from 140 working between retry iterations. By removing environment restrictions on compact execution, this slice enables the persistence compaction flow described in the architecture to work across all three execution environments.

### [NOTE] Clean separation of concerns between actions

The slice's re-separation of `summarize` (artifact production), `compact` (context reduction), and `summarize restore` (context injection) into distinct composable actions aligns well with the architecture's principle of clear responsibility boundaries. This design supports the architecture's goal of making pipeline steps deterministic and understandable, even as the intelligence layer adds probabilistic convergence strategies atop them.
