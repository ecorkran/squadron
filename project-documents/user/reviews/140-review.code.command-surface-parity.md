---
docType: review
layer: project
reviewType: code
slice: command-surface-parity
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/140-slice.command-surface-parity.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260328
dateUpdated: 20260328
---

# Review: code — slice 140

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Review findings lack consistency between removed and added concerns

The diff shows that 14 CONCERN findings were removed and replaced with 8 different concerns. While some replacement is valid (e.g., the "Loop condition grammar is underspecified" finding is a refinement of the original), several original concerns appear to have been dropped without adequate justification:

1. **State file format has no versioning** - Removed but not addressed. The state file schema still lacks a `version` field.

2. **No concurrency model defined for future expansion** - Removed. The concern about sequential-only execution remains valid.

3. **CF connection model deferred but affects action design** - Removed, but the async protocol with potentially sync CLI calls issue is not resolved.

4. **Custom step type error handling not addressed** - Removed, yet the finding that users writing custom step types need guidance is valid.

5. **Findings format decision is deferred but relied upon by validation** - Removed without resolution. The chicken-and-egg problem between validation and output format persists.

**Reference:** `project-documents/user/reviews/140-review.arch.pipeline-foundation.md` - The entire Findings section diff

### [CONCERN] New `checkpoint` action finding contains internal inconsistency

The new finding states the `checkpoint` action "owns state serialization" while acknowledging "the state manager (a separate component) already handles serialization." The finding then concludes there is a "boundary violation" — but the document itself (as of this review) correctly shows state serialization handled by StateManager. The finding appears to critique a design that was already improved, or the architecture diagram and text should be reconciled.

**Reference:** "The state manager (a separate component in the architecture diagram) already handles serialization" vs. "If the checkpoint action also 'owns' state serialization"

### [CONCERN] New `each` step type finding is speculative

The finding states "`{slice.index}` binding implies the bound item has an `index` field" — but the document doesn't actually show `{slice.index}` being used. The `design-batch` example shows `slice: "{slice.index}"` but `slice.index` is a logical field on the iteration context (0, 1, 2...), not a field of the CF query result. This finding may be based on a misreading of the example.

**Reference:** `source: cf.unfinished_slices("{plan}")` — the `.index` is iteration position, not a CF result field

### [CONCERN] Two `devlog.py` finding is a documentation hygiene issue, not a technical concern

The finding states identical file names "create a mental-model hazard." This is a documentation clarity issue, not a technical quality or correctness concern for the architecture being reviewed. The finding should be categorized as `documentation` or `clarity`, not as an architectural concern warranting attention before implementation.

**Reference:** `actions/devlog.py` vs `steps/devlog.py` — the architecture section correctly explains their different responsibilities

### [PASS] New PASS findings accurately reflect the unchanged architecture

The three PASS findings correctly identify aspects of the architecture that remain sound:
- Action protocol async/sync signatures are correct
- Action/step separation is well-designed  
- 140/160 boundary is architecturally sound
- Prerequisite dependencies are accurately listed

These findings accurately reflect the unchanged architecture.

### [CONCERN] `dateUpdated` changed without corresponding content justification

The `dateUpdated` field changed from `20260327` to `20260328`, but no substantive architectural changes are evident — the findings were largely replaced, not improved. If this is a review-only change (not a re-review of updated source architecture), the date should reflect when the review was conducted, not arbitrarily updated.

**Reference:** Header metadata block
