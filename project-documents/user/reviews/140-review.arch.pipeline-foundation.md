---
docType: review
layer: project
reviewType: arch
slice: pipeline-foundation
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/140-arch.pipeline-foundation.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260328
dateUpdated: 20260328
---

# Review: arch — slice 140

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Open Question 5 is unresolved but not reflected in scope/status

category: completeness
Open Question 5 ("How does `{slice.index}` resolve inside an `each` block?") was explicitly deferred as an open question at document creation, but the document status is "draft" and the collection loop feature is listed as in-scope. The `design-batch` example uses `{slice.index}` interpolation without defining the resolution mechanism. A user implementing `each` loops cannot proceed without this decision, yet it's positioned as a minor detail rather than a blocking open question. The grammar section does not address template interpolation syntax at all.

### [CONCERN] Loop condition grammar is underspecified

category: completeness
The document uses `until: review.pass` as an example condition for basic loops but never defines the condition grammar. Is `review.pass` a field path into `ActionResult`? A magic property of the step output? A YAML key that maps to a structured expression? Without a grammar definition, the validator (`--validate`) cannot check loop conditions, and the executor cannot reliably interpret conditions. The absence is especially notable because the document explicitly acknowledges `loop.strategy` as an extension point — suggesting a formal condition syntax exists or should exist.

### [CONCERN] `checkpoint` action conflates two distinct responsibilities

category: abstraction
The Core Action Types table assigns `checkpoint` a single responsibility ("Pause for human decision") with two owned concerns ("State serialization, presentation, resume token"). These are three distinct operations: (1) serializing and persisting pipeline state, (2) presenting state to a human, and (3) issuing a resume token for continuation. The state manager (a separate component in the architecture diagram) already handles serialization. If the checkpoint action also "owns" state serialization, there is a boundary violation — the checkpoint action would need to call the state manager or duplicate its logic. The "resume token" concept is never defined: is it a token string? How is it generated, stored, and consumed on resume? The state file schema shows `checkpoint.reason` and `checkpoint.paused_at` but no token field. The `sq run --resume <run-id>` command takes a `run-id`, not a token, suggesting resume is file-based — in which case "resume token" is either redundant or undefined.

### [CONCERN] Runtime error handling strategy is entirely deferred

category: completeness
The document describes `ActionResult` as carrying success/failure but never specifies what the executor does with a failure result. Does a failed action fail the entire pipeline? Skip to the next step? Retry? The only retry mechanism described is the explicit `loop` construct. There is no mention of transient error handling (network blips during CF operations), no timeout strategy for the `dispatch` action's agent call, and no cancellation behavior when a user interrupts with Ctrl+C. The state manager description (persist/resume) says nothing about how partial state is handled if the process is killed mid-action. These are not exotic edge cases — they are the expected failure modes of a CLI tool running external processes.

### [CONCERN] State file schema doesn't cover all documented state

category: completeness
The state file schema shows `completed_steps[].outputs` as a flat key-value object (e.g., `{"design_file": "191-slice.some-feature.md"}`), but the design envisions custom action types that users can register. The schema does not define how outputs from non-built-in actions should be structured, whether outputs can be nested, or whether outputs are append-only or replaceable across retries. The `each` collection loop (which iterates and produces multiple inner step results) has no specified effect on the state schema. The schema also does not cover the `review_verdict` field format beyond being a string — it should reference the structured findings format defined elsewhere in the document.

### [CONCERN] Async execution model for CF subprocess calls needs explicit validation

category: feasibility
The document states CF operations "run via `asyncio.to_thread` to avoid blocking the async executor." This is correct for CPU-bound or I/O-bound blocking calls, but subprocess execution with `asyncio.to_thread` has subtleties: if a CF subprocess hangs or produces unbounded stdout/stderr, it blocks the thread indefinitely. There is no mention of timeout configuration for CF operations, no mention of how the `asyncio.to_thread` call is made (direct call in each action? centralized in `ContextForgeClient`?), and no mention of what happens if the CF CLI is not installed or returns a non-zero exit code. The assumption that `asyncio.to_thread` solves async compatibility is sound, but the details matter for reliability.

### [CONCERN] `each` step type's parameter flow is not defined

category: completeness
The `design-batch` example shows:
```yaml
- each:
    source: cf.unfinished_slices("{plan}")
    as: slice
    steps:
      - design:
          phase: 4
          slice: "{slice.index}"
```
The `{slice.index}` binding implies the bound item has an `index` field accessible via dot notation. But the schema of collection items returned by CF queries is not documented. The executor needs to know: (1) the type of each collection item (dict? typed object?), (2) how to traverse fields, (3) what happens if a field is missing, (4) whether the binding is read-only or can be modified. This is not a minor detail — it is the core semantics of the `each` construct.

### [CONCERN] Package structure shows two `devlog.py` files without clarifying their relationship

category: abstraction
The package structure shows:
```
actions/devlog.py            # DEVLOG entry
steps/devlog.py              # devlog step type
```
These files share a name but serve different purposes: `actions/devlog.py` handles "formatting and file write using entry templates"; `steps/devlog.py` handles "deciding what to log by inspecting pipeline state." The design is correct (separation of content decision from content rendering), but identical file names in different directories create a mental-model hazard. A reader will reasonably wonder whether these are duplicates or related. The architecture description does not explicitly call out this separation.

### [PASS] Action protocol and async/sync signatures are correctly defined

category: technology
The `Action` protocol defines `async def execute()` and sync `validate()` — no mismatches between blocking and non-blocking calls. The executor is consistently described as async. Python's `Protocol` from `typing` works across the 3.8+ range the project targets. `ActionContext` and `ActionResult` as typed structs (rather than service objects) are consistent with the stated goal of avoiding deep dependency injection.

### [PASS] Action/step separation is well-designed

category: abstraction
The two-audience model (users write steps, custom step type authors write action sequences) correctly hides complexity. Each core action has one responsibility. The action registry follows the established pattern of the agent provider registry, reducing conceptual surface area.

### [PASS] 140/160 boundary is architecturally sound

category: extension-points
The extension points are well-placed: `loop.strategy` field reserves syntax, `pool:` prefix on model references is acknowledged, `persistence:` flag on steps is defined. Each is handled by a no-op stub in 140 and a concrete implementation in 160 without requiring architectural changes.

### [PASS] Prerequisite dependencies are accurately listed

category: dependencies
The document correctly identifies all consumed components (agent registry, model alias registry, CF integration layer, review system) as complete from the 100-band. There are no circular dependencies in the described relationships. The CF client abstraction correctly isolates the subprocess-to-MCP transport migration.
