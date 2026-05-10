---
docType: review
layer: project
reviewType: slice
slice: container-step-classification-each-loop-fan-out
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260510
dateUpdated: 20260510
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "New classifier code paths lack failure mode enumeration"
    location: 250-slice.container-step-classification-each-loop-fan-out.md#Classifier-Changes
  - id: F002
    severity: note
    category: api-design
    summary: "hasattr pattern for optional protocol extension is a documented trade-off"
    location: 250-slice.container-step-classification-each-loop-fan-out.md#Protocol-Addition
  - id: F003
    severity: pass
    category: architectural-boundary
    summary: "Boundary discipline preserved — no executor or 180-band changes"
    location: 250-slice.container-step-classification-each-loop-fan-out.md#Technical-Scope
  - id: F004
    severity: pass
    category: classification-correctness
    summary: "Conservative-on-uncertainty preserved for fan_out mixed alias lists"
    location: 250-slice.container-step-classification-each-loop-fan-out.md#Aggregate-alias-classification
  - id: F005
    severity: pass
    category: architectural-alignment
    summary: "Classification extends correctly into containers per architecture's anticipated boundary"
    location: 250-slice.container-step-classification-each-loop-fan-out.md#Overview
  - id: F006
    severity: pass
    category: backward-compatibility
    summary: "Backward-compatible StepClassification schema change"
    location: 250-slice.container-step-classification-each-loop-fan-out.md#StepClassification-Schema-Change
---

# Review: slice — slice 250

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] New classifier code paths lack failure mode enumeration

The slice introduces several new execution paths in `classify_pipeline` — container descent via `getattr(step_impl, "inner_steps", lambda _: [])(step)`, sentinel `_fan_out_aggregate` detection and special routing, `get_step_type(inner.step_type)` on inner steps, and the `_unpack_inner_steps` utility in a new shared location — but does not enumerate failure modes or explicit handling strategies for any of them. Specific gaps:

- **`inner_steps()` raises on malformed config.** The `getattr` callable pattern will propagate any exception from `inner_steps()` directly through `classify_pipeline`. No try/except or explicit handling strategy is stated. The architecture's "fail fast" goal is served by propagation, but this should be an intentional documented decision, not implicit.
- **Sentinel leaks past the guard.** If `_classify_container_inner` is refactored and the `step_type == "_fan_out_aggregate"` check is bypassed, a call to `get_step_type("_fan_out_aggregate")` would fail at the registry. The slice says "a comment must document this invariant" but comments are not enforcement; no defensive coding strategy (e.g., a `StepConfig.is_synthetic` flag, an assertion before registry lookup) is specified.
- **Inner step type not registered.** `get_step_type(inner.step_type)` on a returned inner step could fail if the step type string is unrecognized. No handling strategy is stated.
- **`unpack_inner_steps` returns empty or malformed list.** If the utility produces unexpected output in the new shared location, the classifier would silently produce incomplete results.

The architecture document requires that failure modes be "enumerated for each new I/O path or message type with explicit handling strategy, not 'TBD' or implicit." While these are computational rather than I/O paths, the principle applies: new code paths in a load-bearing function deserve explicit failure-mode analysis.

### [NOTE] hasattr pattern for optional protocol extension is a documented trade-off

The slice deliberately uses `hasattr(step_impl, "inner_steps")` instead of adding `inner_steps` to the `StepType` protocol to avoid modifying all existing step type files. This is a pragmatic and documented trade-off. A minor risk: if a step type adds an `inner_steps` attribute or method with an incompatible signature (e.g., different parameter count), `hasattr` would find it but the call would fail at runtime with a confusing error. The slice's rationale is sound, but the failure mode of a signature mismatch is not addressed.

### [PASS] Boundary discipline preserved — no executor or 180-band changes

The slice explicitly scopes out all executor changes (`_execute_each_step`, `_execute_loop_body`, `_execute_fan_out_step`), mid-run session construction, and pool policy changes. This is consistent with the architecture's principles: "No new lifetime semantics" and "Boundary discipline with 180-band." The classification layer stays within its responsibility; the executor continues to handle container dispatch unchanged.

### [PASS] Conservative-on-uncertainty preserved for fan_out mixed alias lists

Fan_out with a mixed literal alias list (e.g., `[sonnet, minimax]`) classifies as `POOL_UNCERTAIN`, consistent with the architecture's "Conservative on uncertainty" principle. Under LAZY policy, `needs_persistent_session=False` for `POOL_UNCERTAIN`, which the verification walkthrough explicitly acknowledges and cross-references to the existing pool-step semantics. The architecture anticipates the mid-run auth failure case in a dedicated "Error Semantics and Mid-Run Auth Failure" slice, so deferring that handling is architecturally consistent.

### [PASS] Classification extends correctly into containers per architecture's anticipated boundary

The architecture explicitly anticipates this work: "a loop containing an SDK dispatch is Claude-required; a fan-out dispatching to N non-SDK reviewers is not. The classification rule (per-step union) handles the simple cases." The slice's design — descend into container inner steps and classify them using the same resolver — directly implements this. The per-step union rule is preserved: the pipeline's `needs_persistent_session` is the union of all step classifications, now including those inside containers.

### [PASS] Backward-compatible StepClassification schema change

The `container_path: str | None = None` field defaults to `None` for all existing rows, preserving backward compatibility. The architecture's principle that "Pipeline-level classification is a derived property, not durable state" is not violated — `container_path` is a presentation attribute, not a classification driver.
