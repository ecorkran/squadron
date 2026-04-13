---
docType: review
layer: project
reviewType: slice
slice: dispatch-summary-context-injection
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/191-slice.dispatch-summary-context-injection.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260412
dateUpdated: 20260412
findings:
  - id: F001
    severity: note
    category: scope-alignment
    summary: "Deterministic code may belong in foundation rather than intelligence"
    location: slice frontmatter and technical scope
  - id: F002
    severity: concern
    category: package-structure
    summary: "Module placement outside intelligence package structure"
    location: src/squadron/pipeline/summary_context.py
  - id: F003
    severity: concern
    category: architectural-boundary
    summary: "Direct modification of foundation action bypasses registry extension"
    location: src/squadron/pipeline/actions/summary.py modification
  - id: F004
    severity: pass
    category: design-quality
    summary: "Pure function design enables testing and reusability"
  - id: F005
    severity: pass
    category: dependency-direction
    summary: "Correct dependency direction and integration"
  - id: F006
    severity: note
    category: scope-coverage
    summary: "Fills gap not addressed by architecture"
---

# Review: slice — slice 191

**Verdict:** CONCERNS
**Model:** z-ai/glm-5

## Findings

### [NOTE] Deterministic code may belong in foundation rather than intelligence

The architecture explicitly states: "The boundary between 'always works the same way' and 'requires calibration' is the initiative split." The `assemble_dispatch_context()` function is a pure, deterministic transformation with no heuristics, tuning parameters, or probabilistic behavior—it "always works the same way." This suggests the work may be better classified as foundation (initiative 140) rather than intelligence (initiative 180). The slice acknowledges it has "no dependency on any 180-band slice" and "should land first in the 180 initiative"—but this positioning is contradictory. Foundation work should be 140-band.

### [CONCERN] Module placement outside intelligence package structure

The architecture defines that initiative 180 code belongs under `src/squadron/pipeline/intelligence/` with a detailed package structure for convergence, ledger, pools, triage, escalation, and persistence modules. This slice creates `src/squadron/pipeline/summary_context.py` directly under `pipeline/`, outside the `intelligence/` package. If this is 180-band work, the module should be placed under `intelligence/` (potentially as `intelligence/context/` or similar). If the placement is intentional because the code is foundation rather than intelligence, the slice should be reclassified to 140-band.

### [CONCERN] Direct modification of foundation action bypasses registry extension

The architecture states: "No 140 code is modified. 180 registers new strategies, new resolver backends, and new action behaviors through the registries 140 establishes." This slice directly modifies `_execute_summary()` in the summary action (from slice 161, a 140-band slice) rather than extending through a registry. The architecture's extension points are `loop.strategy`, `pool:` prefix, `escalation` field, `persistence` field, and structured findings. Context injection doesn't use any of these mechanisms—it modifies foundation code directly. If this is foundation work (140-band), direct modification is appropriate. If it's intelligence work (180-band), a registry-based extension mechanism should be designed.

### [PASS] Pure function design enables testing and reusability

The `assemble_dispatch_context()` function is designed as a pure function with no I/O, side effects, or external dependencies—exactly matching the architecture's preference for testable, modular components. The design correctly returns an empty string for empty inputs, allowing unconditional prepending without special-case handling at the call site.

### [PASS] Correct dependency direction and integration

The slice correctly consumes from lower-level modules (`ActionContext.prior_outputs`, `ActionType` enum) without creating circular dependencies. The integration into `_execute_summary()` is minimal and surgical—a 5-line addition to the non-SDK branch, leaving the SDK path completely untouched. The slice correctly identifies the extension point: the non-SDK profile branch added in slice 164.

### [NOTE] Fills gap not addressed by architecture

The architecture document focuses on convergence strategies, model pools, escalation, and persistence—collectively "intelligence" capabilities. Context injection for one-shot dispatch models isn't mentioned as in-scope or out-of-scope. The slice fills a legitimate gap (non-SDK summaries produce garbage without context), but the architecture should be updated to acknowledge this capability—either as part of intelligence or explicitly delegated to foundation.
