---
docType: review
layer: project
reviewType: slice
slice: resolution-pre-scan
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/243-slice.resolution-pre-scan.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260504
dateUpdated: 20260504
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "Cascade logic duplicated outside the resolver instead of adding a side-effect-free resolver entrypoint"
    location: 243-slice.resolution-pre-scan.md#4-per-step-classification-algorithm
  - id: F002
    severity: concern
    category: interface-contract
    summary: "`needs_one_shot_claude` property semantics diverge from the architecture definition"
    location: 243-slice.resolution-pre-scan.md#2-dataclasses
  - id: F003
    severity: pass
    category: correctness
    summary: "Side-effect-freeness contract is thoroughly documented and regression-guarded"
    location: 243-slice.resolution-pre-scan.md#8-verification-of-side-effect-freeness-contract
  - id: F004
    severity: pass
    category: alignment
    summary: "Conservative default for pool-uncertain steps aligns with architectural principle"
    location: 243-slice.resolution-pre-scan.md#2-dataclasses
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes are explicitly enumerated with handling strategies, not TBD"
    location: 243-slice.resolution-pre-scan.md#6-failure-modes
  - id: F006
    severity: pass
    category: scope
    summary: "Scope is well-bounded with clear non-goals"
    location: 243-slice.resolution-pre-scan.md#non-goals
  - id: F007
    severity: pass
    category: boundary
    summary: "180-band boundary discipline is maintained"
    location: 243-slice.resolution-pre-scan.md#5-pool-step-classification
---

# Review: slice — slice 243

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Cascade logic duplicated outside the resolver instead of adding a side-effect-free resolver entrypoint

The architecture's Envisioned State §1 states: "ask the model resolver for `(model_id, profile)` using the same cascade that the action would use at runtime." The Anticipated Slices section further specifies a "classify, don't select" resolver entrypoint to avoid pool-selection side effects. The slice deliberately rejects this, reproducing the five-tier cascade ordering inline in the classifier module and justifying it as "cleaner" because it avoids coupling the resolver to classification semantics.

However, the real effect is that the cascade logic is now in two places: `ModelResolver.resolve()` and `classify_pipeline`. The slice's own Risks section acknowledges that a future sixth cascade tier would be *silently missed* by the classifier. The proposed mitigation — a `cascade_candidates()` helper on the resolver — is deferred to a "follow-up consideration" even though it would eliminate the divergence risk entirely and is itself a resolver-side change (not a classification coupling).

A side-effect-free `resolve_for_classification()` or `cascade_candidates()` method on `ModelResolver` would keep the cascade single-source and still avoid `pool_backend.select()`. The slice's argument that this "couples resolver to classification semantics" is weak: the resolver already returns `(model_id, profile)` tuples; a non-selecting resolve variant is a resolver concern (side-effect isolation), not a classification concern. Given that slices 244–246 all depend on the classification output, the cascade duplication should be resolved before the API stabilizes, not after.

### [CONCERN] `needs_one_shot_claude` property semantics diverge from the architecture definition

The architecture (§Envisioned State point 2) defines `needs_one_shot_claude` as: "true iff at least one step (review or non-SDK-mode dispatch) resolves to an SDK profile and will route through the provider registry's `ClaudeSDKAgent` path." This is intentionally scoped to steps that actually use the one-shot path.

The slice defines it as: "True iff at least one step (any action type) is SDK-resolved or POOL-uncertain." This includes dispatch/summary/compact steps that route through the persistent session — steps that *never* use the one-shot `ClaudeSDKAgent` path.

While the derived `PipelineShape.shape` property likely still produces correct values (since `needs_persistent_session` takes priority in the shape derivation), the standalone `needs_one_shot_claude` property is semantically incorrect per the architecture. This matters because slice 246 will expose this property in `--explain` diagnostics, and slice 244 may use it for the auth pre-flight check. A user-facing property that says "needs one-shot Claude" but is True for pipelines that only use the persistent session is actively misleading.

The fix is straightforward: compute `needs_one_shot_claude` only from steps that route through the one-shot path (reviews with SDK profile, and dispatch steps with non-SDK profile), consistent with the arch definition. The current `needs_one_shot_claude` value ("any SDK step") is already captured by `needs_persistent_session OR needs_one_shot_claude` in the arch's formulation, so no information is lost.

### [PASS] Side-effect-freeness contract is thoroughly documented and regression-guarded

The slice correctly identifies the three purity contracts the classifier relies on (`resolve_model_alias` is a pure dict lookup, non-pool `ModelResolver.resolve` delegates to it, `ModelPool.models` is static frozen data), documents them as a docstring contract on `classify_pipeline`, and provides an idempotency test with a `SpyPoolBackend` that asserts zero `select()` calls. This directly addresses the architecture's Technical Consideration on resolver determinism and pool-selection isolation. The regression guard is well-designed.

### [PASS] Conservative default for pool-uncertain steps aligns with architectural principle

The architecture's principle "Conservative on uncertainty" states that pool-uncertain steps should default to treating the pipeline as Claude-required. The slice implements this correctly: `POOL_UNCERTAIN` steps contribute to `needs_persistent_session = True`, and the design explicitly notes that slice 245 will layer the policy parameter on top. The "all-SDK pool collapses to `SDK_REQUIRED`" and "all-non-SDK pool collapses to `NON_SDK`" optimizations are sound — they reduce uncertainty without violating the conservative default.

### [PASS] Failure modes are explicitly enumerated with handling strategies, not TBD

All four failure modes (misconfigured step, pool not found, bad alias, pool candidate without backend) have explicit handling: raise or propagate, never swallow or silently fallback. This aligns with the architecture's "Fail fast at classification time" goal and the project rule against silent fallbacks. Since the classifier is a pure computation with no I/O paths, network-timeout/hang/peer-disconnect failure modes do not apply.

### [PASS] Scope is well-bounded with clear non-goals

The slice correctly limits itself to the classifier and its data structures, explicitly deferring executor wiring (244), CLI diagnostics (246), lazy-mode policy (245), and mid-run session construction (245). No executor behavior changes ship in this slice. This prevents scope creep and lets the data structures stabilize under unit-test pressure before downstream slices depend on them.

### [PASS] 180-band boundary discipline is maintained

The classifier accesses only `PoolBackend.get_pool()` (static definition retrieval) and `ModelPool.models` (frozen alias list). It never calls `pool_backend.select()`, never invokes selection strategies, and never reads weighted-decay telemetry or round-robin counters. This is exactly the boundary the architecture prescribes: "The classification question the pre-scan asks is purely structural."
