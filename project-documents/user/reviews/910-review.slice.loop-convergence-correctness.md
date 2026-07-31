---
docType: review
layer: project
reviewType: slice
slice: loop-convergence-correctness
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/910-slice.loop-convergence-correctness.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260731
dateUpdated: 20260731
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Under-specified design decisions deferred to implementation"
    location: 910-slice.loop-convergence-correctness.md#part-a---findings-feedback-between-iterations-42
  - id: F002
    severity: note
    category: scope
    summary: "Three bugs bundled into one slice vs. \"prefer many small slices\""
    location: 910-slice.loop-convergence-correctness.md#overview
  - id: F003
    severity: pass
    category: scope-alignment
    summary: "Scope alignment with architecture's bug-fix category"
    location: 910-slice.loop-convergence-correctness.md#technical-scope
  - id: F004
    severity: pass
    category: dependencies
    summary: "Dependency direction and integration points are correct"
    location: 910-slice.loop-convergence-correctness.md#integration-points
---

# Review: slice — slice 910

**Verdict:** PASS
**Model:** z-ai/glm-5.2

## Resolution (20260731)

- **F001 (concern, ACCEPTED)** — All three deferred items were traced against
  the actual code rather than left as implementation-time guesses:
  - **Key naming (Part A):** confirmed the plain `{action_type}-{action_index}`
    scheme (no iteration number folded in, same-key overwrite across
    iterations) is safe by construction, not just convenient. `action_type`
    is an unqualified string with no inner-step identity
    ([models.py:28-42](src/squadron/pipeline/models.py#L28-L42)), so two
    inner steps in one loop body could only collide on the same key if both
    produced the same action type — exactly the shape Part B's validation
    bans. With Part B landing first, the collision case cannot occur, and
    same-key overwrite across iterations is the *desired* "latest review
    wins" behavior, not a bug to guard against.
  - **`step_outputs` interaction (Part A):** traced its full lifecycle —
    created once per run, threaded by reference (never copied), and written
    exactly once per *top-level* step after that step fully returns
    ([executor.py:717](src/squadron/pipeline/executor.py#L717),
    [executor.py:889-899](src/squadron/pipeline/executor.py#L889-L899)).
    Confirmed it is a disjoint mechanism from `prior_outputs`, scoped to
    completed steps outside the loop, and Part A's iteration-to-iteration
    fix never touches it. No scope growth.
  - **`expand()` purity (Part B):** read every `expand()` implementation
    reachable inside a loop body (`compact`, `devlog`, `dispatch`, `gate`,
    `phase`, `review`, `summary` — nested `loop:` is separately banned).
    Each is a pure dict transform with no I/O of any kind. Confirmed safe to
    call at validation time; the raw-config fallback is retained as
    documentation only.

  The slice design's Part A and Part B sections were rewritten in place to
  state these as resolved decisions ("resolved, not deferred" / "resolved,
  purity confirmed") rather than implementation-time questions, and the Risk
  Assessment section (which listed both as open risks) was removed since no
  open risk remains that would change either Part's 1/5 effort estimate.
- **F002 (note, ACKNOWLEDGED)** — Bundling justification (shared function,
  shared test file) already in the design; no action, per the review's own
  assessment that this is acceptable for a maintenance initiative.
- **F003, F004 (pass)** — no action.

## Findings

### [CONCERN] Under-specified design decisions deferred to implementation

Three design decisions are explicitly left as "confirm during implementation" rather than resolved in the design document:

1. **Key naming scheme (Part A):** The slice asks the implementer to "confirm whether the iteration number needs to be folded into the key" and recommends an approach (letting same-key overwrites happen) but does not commit to it. The wrong choice silently corrupts `_resolve_prompt_from_prior_review`'s "most recent review" lookup — the exact bug being fixed.

2. **`step_outputs` interaction (Part A):** The slice states a "working assumption" that `step_outputs` needs no change and flags that "if that assumption is wrong, Part A's scope grows to cover it." A scope-gating assumption that can expand the slice's footprint is a design question, not an implementation detail.

3. **`expand()` side-effect-freeness (Part B):** The entire validation-time approach depends on `expand()` being pure, but this is deferred to implementation verification with a fallback to raw-config inspection.

Each has a documented fallback, which mitigates the risk, but the pattern of deferring core design decisions — particularly one (step_outputs) that can change the slice's own scope boundary — is under-specification by the criteria's definition.

### [NOTE] Three bugs bundled into one slice vs. "prefer many small slices"

The architecture guideline says "prefer many small slices over few large ones." This slice bundles three distinct defects (#42, #43, #45) into one design. The justification — Parts A and B share a single function (`_execute_loop_body`) and one test file — is reasonable and the architecture uses "prefer" rather than "require." Part C is fully independent of the other two and could have been a separate slice, but its effort (1/5, display-only) makes the overhead of a separate design document arguably wasteful. This is acceptable for a maintenance initiative but worth noting.

### [PASS] Scope alignment with architecture's bug-fix category

All three parts fix non-trivial correctness bugs that do not belong to an active feature slice: #42 (loop re-sends identical prompts, never converges), #43 (ambiguous verdict gating silently discards failures), and #45 (`--dry-run` hides loop body). This matches the architecture's "Bug fixes: Non-trivial bugs that don't belong to an active feature slice" scope category. The slice correctly excludes new features, and the deferred `on_exhaust: skip` issue is documented as an explicit out-of-scope decision with three resolution paths for future work.

### [PASS] Dependency direction and integration points are correct

The slice declares `dependencies: []` (no prerequisites) and `interfaces: [911]` in frontmatter, and the Integration Points section confirms: slice 911 consumes from this slice (Part A provides well-defined iteration outputs that 911 needs for version metadata), while this slice consumes nothing from other slices. The dependency direction is correct — this slice is a provider, not a consumer. The sequencing note (911 "assumes this one is done") is consistent with the interface declaration.
