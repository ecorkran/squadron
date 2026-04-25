---
docType: review
layer: project
reviewType: slice
slice: per-action-model-override-convention
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/167-slice.per-action-model-override-convention.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260424
dateUpdated: 20260424
findings:
  - id: F001
    severity: pass
    category: design-alignment
    summary: "Convention aligns with pipeline model resolution architecture"
  - id: F002
    severity: pass
    category: scope-management
    summary: "Scope is appropriately bounded"
  - id: F003
    severity: pass
    category: integration-points
    summary: "Dependency references are appropriate"
  - id: F004
    severity: pass
    category: design-anti-patterns
    summary: "Anti-pattern explicitly rejected"
    location: "User-Provided Concept" section
  - id: F005
    severity: pass
    category: integration-points
    summary: "Data flow analysis is sound"
    location: "How `review_model` Enters `context.params`" section
  - id: F006
    severity: note
    category: documentation
    summary: "Verification walkthrough could show YAML override example"
  - id: F007
    severity: note
    category: documentation
    summary: "ReviewAction code change references YAML mapping verification"
    location: "ReviewAction Change" section, paragraph 3
---

# Review: slice — slice 167

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Convention aligns with pipeline model resolution architecture

The `{purpose}_model` convention fits cleanly within the 5-level cascade defined in the architecture (`140-arch.pipeline-foundation.md`, "Model Resolution" section). The convention:
- Extends the existing cascade via a new channel (CLI `--param`) without modifying the cascade structure
- Preserves `--model` as the pipeline-wide default feeding `ModelResolver._cli_override`
- Passes override values through `context.resolver.resolve()` so alias resolution and pool handling work uniformly
- Documented in `docs/PIPELINES.md` per the slice's own success criteria

The User-Provided Concept section's invariant — "pipeline YAML and `--param` are two sides of the same slot" — is consistent with the architecture's design principle that model aliases appear everywhere and resolve through a unified resolver.

### [PASS] Scope is appropriately bounded

The slice clearly delimits what's in scope (convention documentation, `ReviewAction` application, tests) vs. out of scope (other actions, new CLI flags, cascade changes). This aligns with the architecture's initiative boundary — the 140-band owns the foundation, and this slice adds a convention within that space without reaching into 160 (Pipeline Intelligence, model pools with selection strategies).

### [PASS] Dependency references are appropriate

Dependencies listed (`142-pipeline-core-models-and-action-protocol`, `146-review-and-checkpoint-actions`, `ReviewAction` interface, `ModelResolver`, `docs/PIPELINES.md`) all fall within the 140 scope. The slice correctly depends on existing components rather than proposing to change them.

### [PASS] Anti-pattern explicitly rejected

The slice identifies and explicitly rejects the anti-pattern of a "generic auto-resolve any `*_model` param" system that would require the resolver to enumerate action types. This is the correct architectural choice — the architecture places model resolution in the resolver, but action-level semantics belong in the action. The pattern of each action checking its own override key (`params["{purpose}_model"]`) is consistent with the architecture's principle that actions are "independently testable" units.

### [PASS] Data flow analysis is sound

The analysis correctly identifies that `--param review_model=Y` arrives via `merged_params` (pipeline-level params), while action config from step expansion (`{"model": "minimax"}`) goes into `params["model"]`. The two channels are separate by design — no loader change needed. The key insight that if both are present, `review_model` wins (by the action's own priority logic) is correct.

### [NOTE] Verification walkthrough could show YAML override example

The Verification Walkthrough section shows dry-run commands for `--param` override but doesn't include a command that exercises the YAML channel (`review.model: X` in step config) to demonstrate the fallback path. Adding a test case like:

```bash
sq run p4 123 --dry-run
```

with a pipeline where `review.model: "{review-model}"` is set in YAML would confirm the fallback path works. This is minor — the code logic is clear, and the test suite (`test_review_model_absent_falls_through_to_model`) covers it — but a spot-check in the verification section would strengthen confidence in the two-channel separation claim.

### [NOTE] ReviewAction code change references YAML mapping verification

The current code block says "If the pipeline YAML sets `review.model: X`, the loader should continue to map that into `params["review_model"]` (verify during implementation — may already be the case, or may require a loader tweak)." The data flow section later states "no loader change needed," which creates a slight documentation inconsistency. During implementation, the author should confirm one location documents the final verdict on whether the loader needs change. This is a coordination note, not an architectural misalignment.
