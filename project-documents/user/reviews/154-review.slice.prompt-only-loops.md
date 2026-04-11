---
docType: review
layer: project
reviewType: slice
slice: prompt-only-loops
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/154-slice.prompt-only-loops.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260411
dateUpdated: 20260411
findings:
  - id: F001
    severity: concern
    category: separation-of-concerns
    summary: "Potential duplication of loop expansion logic between prompt renderer and executor"
    location: Technical Scope, Implementation Details
  - id: F002
    severity: concern
    category: specification-clarity
    summary: "Incomplete resolution of item binding mechanism"
    location: Data Flow, Technical Decisions
  - id: F003
    severity: note
    category: documentation
    summary: "Schema versioning for RunState is described but version number not specified"
    location: Implementation Details
  - id: F004
    severity: pass
    category: scope-management
    summary: "Correct scoping of convergence-related features"
  - id: F005
    severity: pass
    category: interface-stability
    summary: "Slash command compatibility properly scoped"
  - id: F006
    severity: pass
    category: error-handling
    summary: "State schema backward compatibility addressed"
    location: Implementation Details
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Component structure aligns with architecture"
    location: Component Structure
---

# Review: slice — slice 154

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Potential duplication of loop expansion logic between prompt renderer and executor

The document describes `render_step_instructions()` detecting `each` steps, resolving the collection source query, and expanding inner steps. This mirrors logic that the executor (slice 149, which already implements collection loops per the architecture) should own.

The architecture states: *"The pipeline executor (slice 149) already supports loops; prompt-only mode just needs to expose those iterations as instruction steps."* This suggests the executor should produce the flattened step sequence that the prompt renderer consumes. Instead, the document describes the prompt renderer reconstructing the loop iteration logic independently.

**Specific concern:** The flow shows `render_step_instructions()` calling *"Resolve the source query (same as executor does)"* — this "same as executor" phrasing implies duplicate logic rather than shared consumption of executor output.

**Recommendation:** Clarify how the prompt renderer obtains its step sequence. Ideally, the executor produces a flattened sequence that the prompt renderer consumes. If the renderer must traverse the pipeline definition independently, document why this is necessary and ensure the two implementations stay consistent.

---

### [CONCERN] Incomplete resolution of item binding mechanism

The document uses `{slice.index}` syntax throughout for item binding within `each` loops. The architecture explicitly defers this to 149: *"Full semantics (item type/schema, field traversal, missing field behavior, read-only binding) are a 149 design decision."*

The slice 154 document uses this syntax without acknowledging the deferral or referencing how 149 has resolved it. If 149's design is complete, this should be cited. If the syntax is illustrative only, the document should state this explicitly.

---

### [NOTE] Schema versioning for RunState is described but version number not specified

The document states: *"The JSON state file version increments (if versioned)."* This hedging ("if versioned") is appropriate since the architecture's RunState example doesn't include an explicit version field, but the document should align with whatever versioning scheme 150 established.

---

### [PASS] Correct scoping of convergence-related features

The document correctly excludes:
- `loop.strategy` (weighted decay, etc.) → marked as 160 scope
- Convergence loop strategies in prompt-only mode → correctly identified as SDK-executor territory

This aligns with the architecture's boundary between 140's loop construct (acknowledged but stub-executed) and 160's strategies.

---

### [PASS] Slash command compatibility properly scoped

The document correctly identifies that `/sq:run` (updated in slice 153) works transparently with loops and requires no modifications. The instruction-stream abstraction (loops flattened into sequential instructions) is the correct design for maintaining compatibility.

---

### [PASS] State schema backward compatibility addressed

The document correctly handles the transition from v1 state files (pre-loop) to v2 (with `loop_context`):
- v1 files have `loop_context: null` → treated as "not in a loop"
- v2 files have populated `loop_context` → restored on resume

This is the correct backward-compatible approach.

---

### [PASS] Component structure aligns with architecture

The document specifies:
- `prompt_renderer.py` is **modified** (not new)
- No new components required
- Integration with existing models, loader, and state manager

This matches the architecture's treatment of prompt-only mode as a variant path through existing components.
