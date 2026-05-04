---
docType: review
layer: project
reviewType: slice
slice: conditional-persistent-session-construction
project: squadron
verdict: UNKNOWN
sourceDocument: project-documents/user/slices/244-slice.conditional-persistent-session-construction.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260504
dateUpdated: 20260504
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Core gating logic aligns with architecture's envisioned state"
    location: 244-slice.conditional-persistent-session-construction.md#Architecture
  - id: F002
    severity: pass
    category: architectural-alignment
    summary: "Shared resolver and pool_backend instance satisfies pre-scan correctness requirement"
    location: 244-slice.conditional-persistent-session-construction.md#Refactoring:-pool_backend-construction-site
  - id: F003
    severity: concern
    category: error-handling
    summary: "Deferred failure mode for `claude_required_one_shot` shape not acknowledged"
    location: 244-slice.conditional-persistent-session-construction.md#Technical-Scope
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for conditional session path not fully enumerated"
    location: 244-slice.conditional-persistent-session-construction.md#Implementation-Details
  - id: F005
    severity: concern
    category: dependency-direction
    summary: "Hidden dependency on downstream step handlers for `sdk_session=None` not called out"
    location: 244-slice.conditional-persistent-session-construction.md#Integration-Points
  - id: F006
    severity: note
    category: sequencing
    summary: "Architecture's anticipated slice ordering not reflected as dependency"
    location: 244-slice.conditional-persistent-session-construction.md#Integration-Points
---

# Review: slice — slice 244

**Verdict:** UNKNOWN
**Model:** z-ai/glm-5.1

## Findings

### [PASS] Core gating logic aligns with architecture's envisioned state

The conditional session construction (`if needs_persistent_session: construct else: None`) directly implements architecture §Envisioned State item 3. The three pipeline shapes are correctly identified and logged. The conservative treatment of `POOL_UNCERTAIN` steps matches the architecture's "Conservative on uncertainty" principle. Resume re-classification matches the architecture's stated policy ("re-classification on resume uses current YAML and current alias mappings; the new classification wins").

### [PASS] Shared resolver and pool_backend instance satisfies pre-scan correctness requirement

Option A (threading `resolver` and `pool_backend` as optional parameters into `_run_pipeline`) ensures the same `ModelResolver` instance — with the same `cli_override` and `pipeline_model` — is used by both the classifier and the executor, satisfying the architecture's requirement: "the executor builds the resolver once, the pre-scan and every step's `ActionContext` share that instance." The backward-compatible fallback preserves existing integration test surface.

### [CONCERN] Deferred failure mode for `claude_required_one_shot` shape not acknowledged

The architecture defines `needs_one_shot_claude` as a distinct pipeline-level property and identifies the `claude_required_one_shot` shape (e.g., review-only pipelines with SDK-profile reviews). Currently, these pipelines fail at startup when `session.connect()` is unconditionally called. After this slice, the persistent session is not constructed for this shape, and the Claude auth failure is deferred to one-shot review time — a regression in fail-fast behavior. The architecture states "Fail fast at classification time" as a design goal and says the `needs_one_shot_claude` property "feeds the diagnostic surface and the auth pre-flight check," but the slice does not: (1) enumerate this deferred failure mode, (2) acknowledge the gap until the pre-flight check ships, or (3) note that logging the `claude_required_one_shot` shape is the only mitigation currently provided. The architecture also requires the design to "state explicitly when classification is conservative-pessimistic vs. lazy" — the deferred one-shot failure is a form of lazy auth detection that goes unmentioned.

### [CONCERN] Failure modes for conditional session path not fully enumerated

The evaluation criteria require failure modes enumerated for each new or changed I/O path with explicit handling strategy. The slice handles `ClassificationError` explicitly but does not enumerate failure modes for the conditional `session.connect()` path: what happens on auth unavailability, CLI-not-found, connection timeout, or subprocess crash mid-connect in the conditional context. While these are existing failure modes, their *conditional* nature changes the user experience (they only occur for `claude_required_persistent` pipelines, not for all pipelines as today). The slice should explicitly state the handling strategy for each, particularly since the `try/finally` block wrapping `_run_pipeline` means a `connect()` failure bypasses the `finally` disconnect — the slice should confirm this is intentional and that the session is not in a partially-connected state.

### [CONCERN] Hidden dependency on downstream step handlers for `sdk_session=None` not called out

The slice passes `sdk_session=None` through `_run_pipeline` to all step types (dispatch, summary, compact) for `claude_free` and `claude_required_one_shot` pipelines. Success criterion #1 asserts such pipelines "run successfully," but the slice does not explicitly verify or call out that all step-type handlers (summary actions, compact actions) correctly handle `sdk_session=None` for non-SDK profiles. The dispatch router's handling is covered by slice 242, but summary/compact step behavior with `sdk_session=None` is not discussed. The test coverage table (T1–T6) does not include a scenario exercising summary or compact steps on a `sdk_session=None` code path, leaving a gap between the stated success criterion and the verification plan.

### [NOTE] Architecture's anticipated slice ordering not reflected as dependency

The architecture's "Anticipated Slices" section lists the "Profile-Aware Dispatch Router" as shipping first ("Small, high-value, ships first."). Slice 244 lists 242 as a dependency but states "DispatchAction routing unchanged — this slice does not touch per-step routing logic." For the shapes this slice directly gates (`claude_free` and `claude_required_persistent`), the existing dispatch routing is sufficient: `sdk_session=None` causes non-SDK dispatches to fall through to `_dispatch_via_agent`, and `sdk_session` non-None preserves current behavior. This is not a blocking concern but is worth noting for the slice plan document.
