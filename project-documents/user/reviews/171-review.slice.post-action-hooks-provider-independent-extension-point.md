---
docType: review
layer: project
reviewType: slice
slice: post-action-hooks-provider-independent-extension-point
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md
aiModel: claude-fable-5
status: complete
dateCreated: 20260803
dateUpdated: 20260803
findings:
  - id: F001
    severity: concern
    category: dependencies
    summary: "Frontmatter dependencies omit slice 911, which the design declares a prerequisite"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:6
  - id: F002
    severity: concern
    category: scope
    summary: "New extension surface not reflected in the parent architecture"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:115-251
  - id: F003
    severity: note
    category: configuration
    summary: "`hooks.disabled` as comma-separated string is a documented workaround for config-type limits"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:245-251
  - id: F004
    severity: note
    category: observability
    summary: "Duplicate suppression is per-process, weaker in prompt-only mode"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:378-382
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated with observable handling for every new path"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:298-313
  - id: F006
    severity: pass
    category: alignment
    summary: "Mechanism aligns with the architecture's extensibility idiom and layering"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:136-172
  - id: F007
    severity: pass
    category: alignment
    summary: "Prompt-only parity decision is consistent with the architecture's execution-mode model"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:317-356
  - id: F008
    severity: pass
    category: verification
    summary: "Migration preserves 909/911 behavior with a falsifiable acceptance test"
    location: project-documents/user/slices/171-slice.post-action-hooks-provider-independent-extension-point.md:398-441
---

# Review: slice — slice 171

**Verdict:** CONCERNS
**Model:** claude-fable-5

## Findings

### [CONCERN] Frontmatter dependencies omit slice 911, which the design declares a prerequisite

Frontmatter lists `dependencies: [142, 149, 909]`, but the Prerequisites section (lines 103–104) names 911 explicitly ("**911** — the `revision_number` stamp layered on it. Both complete"), and the migration plan, success criteria (#13, #17), and verification walkthrough all depend on 911's code and tests. Any tooling or reviewer reading frontmatter for the dependency graph gets an incomplete picture. Add 911 to the frontmatter list.

### [CONCERN] New extension surface not reflected in the parent architecture

The architecture's component diagram, package structure, and YAML grammar (140-arch.pipeline-foundation.md, "Component Architecture", "Pipeline Definitions") define step-type and action registries as the two extension points, and enumerate the pipeline YAML vocabulary. This slice adds a third registry (`pipeline/hooks/`), a new pipeline-YAML block (`hooks: {disable: [...]}`), two config keys (`hooks.disabled`, `hooks.timeout_seconds`), and two new modules outside the pipeline package (`documents/paths.py`, `documents/status.py`). The generalization itself is defensible — it removes the open/closed violation the executor accrued via 909/911 — but it is architecture-level surface being introduced at slice level. Future work (initiative 180 convergence strategies, custom step types) needs to know this extension point exists and what its authority model is (severity clamp, chain-stop). The parent architecture document should be updated to include the hooks registry in the component architecture and the `hooks:` block in the grammar, or the slice should record an explicit deferral of that update.

### [NOTE] `hooks.disabled` as comma-separated string is a documented workaround for config-type limits

Because `_coerce_value` supports only `int`/`str`, the config-side disable list is a comma-separated string while the YAML side is a proper list. The design justifies this explicitly and keeps the list form where lists are natural, so it is acceptable — but it creates two encodings of the same concept. If a third list-valued config key appears, widening the config type system becomes the right fix; worth recording as the trigger condition.

### [NOTE] Duplicate suppression is per-process, weaker in prompt-only mode

The dedup set keyed `(hook_name, message)` is "per-run in-memory." In prompt-only mode each `--step-done` is a fresh CLI process, so the same warning recurs once per step invocation rather than once per run. This is log noise only (metadata records every occurrence by design) and is arguably even desirable at step boundaries, but the design's "once per run" claim (success criterion #10) is only true for the in-process executor. Worth one clarifying sentence so criterion #10 is testable as written.

### [PASS] Failure modes enumerated with observable handling for every new path

Each failure mode of the new execution path is explicit: hook raise (ERROR via `logger.exception`, outcome per declared severity), hang (`asyncio.wait_for` with `hooks.timeout_seconds`, treated as raise), severity overreach (clamped + ERROR log), unreadable run state (fails closed, doctrine travels with the dispatch hook), unavailable watermark (PASS + WARNING naming the reason). "There is no silent path" is stated as a contract, and success criterion #20 requires a test asserting the observable signal for raise, timeout, disabled, clamp, and chain-stop. This satisfies the failure-mode-enumeration requirement fully; peer-disconnect modes are inapplicable (no network I/O — filesystem and in-process only).

### [PASS] Mechanism aligns with the architecture's extensibility idiom and layering

The hook registry mirrors the action registry pattern the architecture establishes ("The executor resolves action types through a registry — same pattern as the agent provider registry"), uses the same Protocol/bootstrap idiom, and sits above the provider layer — consistent with the architecture's provider-independence and with the "Reinventing LangGraph" mitigation: registered typed protocol implementations, not lambdas, with shell hooks and file-based discovery explicitly excluded. Dependency direction is correct: hooks depend on pipeline models, documents, and config; the executor depends on the runner; nothing below depends on hooks.

### [PASS] Prompt-only parity decision is consistent with the architecture's execution-mode model

The architecture defines prompt-only mode as "the human is the runtime" with no persistent session. The slice correctly identifies `--step-done` as that mode's post-action moment, closes a pre-existing parity gap rather than introducing one, and derives a load-bearing contract from it (hooks may not read `result.outputs`) so hooks cannot silently diverge across modes — honoring the standing interface-parity rule. The `--step-done` exit-code behavior break is identified and mitigated (CHANGELOG, named failure message, documented disable escape hatch).

### [PASS] Migration preserves 909/911 behavior with a falsifiable acceptance test

"No assertion in an existing 909/911 test may change; only patch targets move" is a concrete, mechanically checkable acceptance criterion, with the explicit inversion rule that if a test assertion must change, the design — not the test — is revised. This is the right shape for a generalize-in-place slice.
