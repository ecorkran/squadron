---
docType: review
layer: project
reviewType: arch
slice: pipeline-auth-boundary-flexibility
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/240-arch.pipeline-auth-boundary-flexibility.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260428
dateUpdated: 20260428
findings:
  - id: F001
    severity: concern
    category: abstraction
    summary: "Classification conflates \"needs persistent session\" with \"needs any Claude auth\""
    location: 240-arch.pipeline-auth-boundary-flexibility.md#envisioned-state
  - id: F002
    severity: concern
    category: completeness
    summary: "Mid-run session construction for Claude-optional pipelines is architecturally undesigned"
    location: 240-arch.pipeline-auth-boundary-flexibility.md#envisioned-state
  - id: F003
    severity: concern
    category: dependencies
    summary: "Hidden dependency on 180-band for \"classify, don't select\" resolver entrypoint"
    location: 240-arch.pipeline-auth-boundary-flexibility.md#technical-considerations
  - id: F004
    severity: concern
    category: completeness
    summary: "`--param model=` CLI override interaction with pre-scan is unspecified"
    location: 240-arch.pipeline-auth-boundary-flexibility.md#envisioned-state
  - id: F005
    severity: concern
    category: feasibility
    summary: "Side-effect-free resolver assumption for non-pool aliases is unverified"
    location: 240-arch.pipeline-auth-boundary-flexibility.md#technical-considerations
  - id: F006
    severity: concern
    category: consistency
    summary: "`is_sdk_profile()` shared with Slice 170 has no ownership or contract specification"
    location: 240-arch.pipeline-auth-boundary-flexibility.md#technical-considerations
  - id: F007
    severity: note
    category: completeness
    summary: "Resume under changed pipeline definitions may produce different classification"
    location: 240-arch.pipeline-auth-boundary-flexibility.md#technical-considerations
---

# Review: arch — slice 240

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Classification conflates "needs persistent session" with "needs any Claude auth"

The per-step classification yields `SDK-required`, `non-SDK`, or `pool-uncertain`, and the pipeline-level classification of `Claude-required` triggers persistent `SDKExecutionSession` construction. But a pipeline whose only SDK-profile steps are reviews does not need the persistent session — reviews route through the one-shot `ClaudeSDKAgent` via the provider registry (step 5 of the Envisioned State explicitly states this path is unchanged). Such a pipeline would be classified `Claude-required`, causing the persistent session to be constructed unnecessarily. The document carefully documents the two paths as distinct surfaces with different lifecycles (Technical Considerations, first bullet) but then folds both into the same classification outcome. The classification is missing a distinction between "needs persistent session" (dispatch/summary/compact steps with SDK profile) and "needs one-shot Claude only" (review steps with SDK profile). Without it, review-only pipelines with SDK reviews still pay the persistent-session connect cost — partially defeating the initiative's own goal.

### [CONCERN] Mid-run session construction for Claude-optional pipelines is architecturally undesigned

The Envisioned State step 3 states the persistent session is constructed "iff classification is Claude-required (or Claude-optional and a pool selection has chosen an SDK alias mid-run)." The mid-run construction case is the hardest part of the initiative: `ActionContext` carries `sdk_session` which was `None` for already-executed steps; a mid-pool selection that yields SDK must either mutate the context, replace it, or block the current step while a session is constructed and connected (Claude CLI subprocess spawn). The document identifies this as a concern in Technical Considerations ("Auth-failure UX at the boundary") and Anticipated Slices ("Error Semantics and Mid-Run Auth Failure"), but doesn't sketch the mechanism at the architecture level. The key architectural questions — is `ActionContext` mutable? does the session construction block the step? how does the state machine transition? — are load-bearing decisions that should at least be constrained here, not deferred entirely to slice design.

### [CONCERN] Hidden dependency on 180-band for "classify, don't select" resolver entrypoint

The Technical Considerations section states the pre-scan "must use a separate 'classify, don't select' resolver entrypoint, distinct from the runtime path that authoritatively selects." This is a new API surface on the pool/resolver system (180-band). Yet the Relationship to Other Components section claims "coordinates with, does not depend on" 180-band, and the Boundary with 180-band principle says "the pool side is not touched." If the "classify, don't select" entrypoint must be built into the resolver (which lives in 180-band), this initiative either depends on 180-band providing it, or must build it itself (violating the stated boundary). The dependency relationship is misstated.

### [CONCERN] `--param model=` CLI override interaction with pre-scan is unspecified

The motivating defect (Motivation point 1) is `sq run p5 X --param model=minimax` silently failing. The pre-scan is described as using "the same cascade that the action would use at runtime," but nowhere does the document explicitly state whether CLI parameter overrides (`--param`) are fed into the pre-scan resolver cascade. If they aren't, the pre-scan would classify the step as SDK (using the pipeline's default model), construct the persistent session, and then the runtime dispatch with the overridden model would hit the same broken `set_model` path — the defect would persist for the pre-scan-to-runtime consistency check, even if the dispatch router itself is fixed.

### [CONCERN] Side-effect-free resolver assumption for non-pool aliases is unverified

The document asserts that "calling `resolve(alias)` in pre-scan returns the same `(model_id, profile)` it would at runtime" for non-pool aliases, and that this is "side-effect-free." This is a critical assumption — if the resolver has any side effects (telemetry emission, cache population, state mutation for pool weighting), the pre-scan would alter runtime behavior or produce inconsistent results. The document doesn't establish this as a guaranteed contract of the resolver; it asserts it. If the resolver in 140-band doesn't actually guarantee side-effect-freedom, the pre-scan design doesn't work as described.

### [CONCERN] `is_sdk_profile()` shared with Slice 170 has no ownership or contract specification

The Technical Considerations note that this initiative and Slice 170 "share the `is_sdk_profile()` predicate and must agree on profile semantics." But the document doesn't specify who owns this predicate, where it lives, what its contract is (what makes a profile "SDK"? is it `profile == "sdk"`? is it a method on the profile object? does it check for Claude CLI availability?), or what happens if the two initiatives ship in different orders with different definitions. A shared predicate with no designated owner is a consistency risk.

### [NOTE] Resume under changed pipeline definitions may produce different classification

The document states "Resume must not require [the classification field] (older runs predate the field) and must compute classification from the resumed pipeline's resolved models, not from cached state." But if the pipeline YAML or model aliases have changed between the original run and resume, the recomputed classification could differ from what the original run used. A pipeline originally classified as Claude-free might resume as Claude-required if a model alias was remapped to an SDK profile in the interim. The document doesn't address whether resume should use the original or current resolution.
