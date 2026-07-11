---
docType: review
layer: project
reviewType: slice
slice: pipeline-phase-step-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/909-slice.pipeline-phase-step-correctness.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260709
dateUpdated: 20260709
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Part A artifact verification I/O failure modes not enumerated"
    location: 909-slice.pipeline-phase-step-correctness.md#architecture
  - id: F002
    severity: concern
    category: scope-boundary
    summary: "Phase→artifact mapping boundary insufficiently specified"
    location: 909-slice.pipeline-phase-step-correctness.md#architecture
  - id: F003
    severity: pass
    category: scope-alignment
    summary: "Slice scope aligns with maintenance architecture"
    location: 909-slice.pipeline-phase-step-correctness.md#overview
  - id: F004
    severity: pass
    category: dependency-direction
    summary: "Part A SRP decision on DispatchAction is well-justified"
    location: 909-slice.pipeline-phase-step-correctness.md#architecture
  - id: F005
    severity: pass
    category: integration
    summary: "Part B verified data source and single-point fix"
    location: 909-slice.pipeline-phase-step-correctness.md#architecture
  - id: F006
    severity: pass
    category: consistency
    summary: "Part C mirrors existing guard pattern"
    location: 909-slice.pipeline-phase-step-correctness.md#architecture
  - id: F007
    severity: note
    category: scope
    summary: "Three bugs bundled into one slice vs. architecture preference"
    location: 909-slice.pipeline-phase-step-correctness.md#overview
---

# Review: slice — slice 909

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Resolution (20260709)

Both concerns were valid design gaps and are addressed in the slice design (commit follows this review).

- **F001 (concern, ACCEPTED)** — Part A's artifact-verification I/O path now enumerates its failure modes explicitly (path-resolution failure, permission denied, I/O error during the existence/mtime check, race delete-after-write), each with an observable outcome (failed step + WARNING-level log), per the Failure-Mode Enumeration rule. Added a failure-mode table to the Part A architecture section and a Technical Risk entry.
- **F002 (concern, ACCEPTED)** — The phase→artifact mapping is now explicit: an `expected_artifact_kind` property on `PhaseStepType`, enumerated for all three registered phases (`design`→design file, `tasks`→task file, `implement`→`None`, i.e. no single deterministic artifact so the post-condition does not apply). A future no-artifact phase sets `None` and is correctly skipped. This resolves the "does every PhaseStepType imply an artifact?" ambiguity — the answer is "only those with a non-`None` `expected_artifact_kind`."
- **F007 (note, ACKNOWLEDGED)** — Bundling justification and C→B→A independent-commit ordering already in the design; added an explicit split-out fallback (if any part stalls, promote it to its own slice rather than blocking the others).
- **F003, F004, F005, F006 (pass)** — no action.

## Findings

### [CONCERN] Part A artifact verification I/O failure modes not enumerated

Part A introduces a new file-system check (verify the expected artifact exists and was written/modified by this run) after dispatch completes. The design does not enumerate failure modes for this new I/O path beyond the intentional "file not written" case. Unaddressed failure modes include: path resolution failure (the expected artifact path cannot be computed from the project layout), permission denied on the artifact path, I/O errors during the existence/modification check, and race conditions (file created then deleted between dispatch and check). The architecture review criterion requires each new I/O path to have explicit handling strategies, not implicit ones. While the existing pipeline error-handling machinery would likely catch an unhandled exception, the design should state what the pipeline does on each of these failure paths rather than relying on implicit propagation.

### [CONCERN] Phase→artifact mapping boundary insufficiently specified

The design states the post-condition is scoped to "phases that *do* produce artifacts" and scoped to `PhaseStepType`, but never enumerates which phase types produce artifacts and which don't. The Risk Assessment section mentions "phases that *do* produce artifacts" as a mitigation but doesn't define the set. This ambiguity leaves an implementer unsure: does *every* `PhaseStepType` imply an artifact, or is there a subset? If a new phase type is later added that legitimately writes nothing, will it incorrectly fail? The document should either enumerate the phase→artifact mapping it references (design→design file, tasks→task file, etc.) or specify how the post-condition determines applicability (e.g., an explicit `expected_artifact_kind` property that is `None` for non-artifact phases).

### [PASS] Slice scope aligns with maintenance architecture

All three parts are bug fixes — explicitly in-scope for the maintenance architecture. The exclusions (no generic DispatchAction redesign, no per-iteration commit mechanics, no issue #14) demonstrate good boundary discipline and prevent scope creep beyond the stated scope of "non-trivial bugs that don't belong to an active feature slice."

### [PASS] Part A SRP decision on DispatchAction is well-justified

The explicit rejection of pushing artifact-awareness into generic `DispatchAction` preserves SRP and prevents the no-artifact bare dispatch case from breaking. The dependency direction is correct: `PhaseStepType` (which knows about phase semantics) owns the post-condition, while `DispatchAction` remains a general-purpose component with no new coupling.

### [PASS] Part B verified data source and single-point fix

The design explicitly verifies that `cf get --json` returns a `name` field (marked as verified, not assumed), threads the data through existing seams (`resolve_slice_info` already calls `get_project`), and fixes at the single convergence point (`format_review_markdown`). The `"unknown"` fallback for resolution failure is an explicit strategy, not a silent degradation. Both CLI and pipeline write paths are covered by construction.

### [PASS] Part C mirrors existing guard pattern

The scope guard in Part C directly mirrors the existing `review_slice`/`review_tasks` guard shape (`if not against: raise typer.Exit(code=1)`), maintaining consistency rather than inventing a new validation style. The single post-resolution guard covers both the missing-argument and malformed-non-digit-argument cases, which is clean.

### [NOTE] Three bugs bundled into one slice vs. architecture preference

The architecture states "prefer many small slices over few large ones." Bundling three bugs into one slice technically runs counter to this, even though the doc justifies it by noting each is small and all three sit on the same correctness path. Since each part is independently committable and testable, this is a reasonable pragmatic choice — but if any part stalls, it would be cleaner to split it out into its own slice rather than letting it block the others. The Implementation Notes section's suggested ordering (C, B, A) and statement that "a stall on Part A does not block Parts B and C" partially addresses this.
