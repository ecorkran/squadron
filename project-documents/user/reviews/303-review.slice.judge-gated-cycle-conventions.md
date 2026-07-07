---
docType: review
layer: project
reviewType: slice
slice: judge-gated-cycle-conventions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md
aiModel: claude-fable-5
status: complete
dateCreated: 20260707
dateUpdated: 20260707
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "Judge-first \"no wasted fix\" claim contradicts loop `until` semantics"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:225-241
  - id: F002
    severity: concern
    category: error-handling
    summary: "Hang/timeout of in-loop provider calls not enumerated"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:435-454
  - id: F003
    severity: note
    category: documentation
    summary: "Frontmatter `dependencies` omits direct dependencies 301 (and 300)"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:6
  - id: F004
    severity: note
    category: error-handling
    summary: "Dispatch-failure row slightly misstates existing loop semantics"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:444
  - id: F005
    severity: note
    category: design
    summary: "Advisory-only depends on thresholds remaining unclamped above 100"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:200-223
  - id: F006
    severity: pass
    category: alignment
    summary: "Scope matches the architecture's anticipated slice exactly, with disciplined boundaries"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:49-95
  - id: F007
    severity: pass
    category: error-handling
    summary: "No-silent-pass NFR restated with specific handling, verified against machinery"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:449-454
  - id: F008
    severity: pass
    category: alignment
    summary: "Advisory-only mode is architecture-conformant and mechanically sound"
    location: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md:200-223
---

# Review: slice — slice 303

**Verdict:** CONCERNS
**Model:** claude-fable-5

## Resolution (20260707)

All actionable findings addressed in `303-slice.judge-gated-cycle-conventions.md`.

- **F001 (concern) — FIXED.** Verified against `_execute_loop_body`
  (`executor.py:1109`): the loop is post-test with per-iteration result reset, so
  a pre-loop judge PASS cannot short-circuit iteration 1. The review is correct;
  the "no wasted fix" rationale was wrong. Reference pipeline switched to
  **fix-first**; an "Executor semantics" note now documents the post-test
  behavior explicitly, and "auto-advance when already good" is reworded to mean
  "exits after one `[fix, judge]` iteration," not "loop skipped."
- **F002 (concern) — FIXED.** Confirmed no per-call timeout exists in the
  review/dispatch/client path. Added a hang/timeout row to the failure-mode table
  and a Technical Risk entry naming it an accepted risk owned by **140**
  (per-call timeout → `UNKNOWN`), and added Future Work item (4) to the parent
  slice plan. The gap is now explicit, not implicit.
- **F004 (note) — FIXED.** Verified inner-step FAILED is transient
  (`executor.py:1143`): the judge still runs against the un-revised artifact. The
  dispatch-failure table row now states the actual semantics (and the correct
  no-silent-pass outcome).
- **F005 (note) — FIXED.** Verified `resolve_thresholds` does no range
  validation. Added a Note that `pass_floor > 100` is a sanctioned value and a
  Special Consideration requiring the authoring doc to say so, guarding against a
  future clamp cleanup.
- **F003 (note) — NOT CHANGED, with rationale.** The established frontmatter
  convention is *direct* dependency only: slice 302 lists `[301]` (not `[300,
  301]`), slice 301 lists `[300]`. 303's direct dependency is 302; 301/300 are
  transitive through it. `dependencies: [302]` is therefore correct per
  convention; 301/300 remain named in Prerequisites prose. The reviewer's
  suggested `[301, 302]` would break the direct-only convention.
- **F006 / F007 / F008 — PASS, no action.**

## Findings

### [CONCERN] Judge-first "no wasted fix" claim contradicts loop `until` semantics

The First-iteration shape section recommends judge-first (pre-loop judge, then loop `[fix, judge]`) on the grounds that "if the pre-loop judge already clears the floor, `until` is satisfied on iteration 1 with no wasted fix." The executor's multi-step loop body is a **post-test** loop: `until` is evaluated only *after* all inner steps of an iteration complete, and it is evaluated against that iteration's own action results only — the loop resets `iteration_action_results` at the start of each iteration and never sees pre-loop step results. A pre-loop judge PASS therefore does not short-circuit the loop; iteration 1 always runs the fix leg (against an already-passing artifact) and re-judges before `until` can exit. The core convention (`loop [fix, judge]`, `until: review.pass`) is unaffected, but the stated rationale for the recommended reference-pipeline shape is wrong, and the "auto-advance when already good is observable" property does not hold as described. In a slice whose central claim is "every construct verified in the codebase during this design," this specific claim was not. Fix options: wrap the loop's entry behind a conditional (if one exists), accept the one wasted fix and correct the prose, or prefer the fix-first shape.

### [CONCERN] Hang/timeout of in-loop provider calls not enumerated

The failure-mode table covers "provider down" (→ `UNKNOWN` → never a silent pass) but not a judge or dispatch call that *hangs* or exceeds a timeout mid-iteration. `loop.max` bounds iterations, not wall-clock time — a hung provider call stalls the unattended pipeline indefinitely inside an iteration, which defeats the slice's headline value ("runs unattended, escalates the hard calls"). The parent architecture enumerates judge failure modes ("provider unavailable" among them) and commits that no failure mode is silent; a hang is a distinct mode from "down" and is currently handled only implicitly ("routes through machinery slices 149/301/302 already built"). The review criteria require hang/timeout to be explicit, not implicit. The slice should either state the existing per-call timeout behavior it inherits (and where that timeout maps in the UNKNOWN/iterate/escalate flow) or name the gap as an accepted risk with an owner.

### [NOTE] Frontmatter `dependencies` omits direct dependencies 301 (and 300)

Frontmatter lists `dependencies: [302]`, but the Prerequisites section (lines 98–105) names slices 300, 301, and 302, and 301 is a *direct* dependency — the advisory-only mode is expressed entirely through 301's step-level `judge:` override and `resolve_thresholds`. If the frontmatter convention is direct dependencies, [301, 302] would be accurate.

### [NOTE] Dispatch-failure row slightly misstates existing loop semantics

The table says a failed fix leg means the "loop iteration fails per existing semantics." The executor treats an inner-step FAILED as transient and continues executing the remaining inner steps — so the judge still runs (against the unrevised artifact) and the iteration completes. The resulting behavior (judge doesn't pass → iterate/escalate, no silent pass) is fine and arguably better than stated, but the description should match the actual semantics.

### [NOTE] Advisory-only depends on thresholds remaining unclamped above 100

Verified: `resolve_thresholds` performs no range validation on threshold values (range validation applies to the *score*, per the architecture's two-layer split), so `pass_floor: 101` works today and yields CONCERNS/FAIL, never PASS. The slice's required test (advisory-always-escalates) pins this behavior, which is good. Worth one sentence in the authoring doc noting that `pass_floor > 100` is a *sanctioned* value, so a future "validate thresholds to 0–100" cleanup doesn't silently break the advisory convention.

### [PASS] Scope matches the architecture's anticipated slice exactly, with disciplined boundaries

The slice is the arch's "Judge-gated cycle conventions" item verbatim: convention + reference pipeline + docs, no new step type/action/selector/executor branch. Boundaries are explicitly held: gate composition deferred to 304 (matching the arch's "honest scope boundary" on single-verdict checkpoints), multi-sample judging deferred (arch permits-but-does-not-require), no new `each` sources invented, no `advisory:` flag (consistent with the arch's threshold-locus commitment and the project rule against scattering comparison values). Dependency direction is correct throughout: consumes 300–302 and 140/149 as-is, provides the composition 304 extends.

### [PASS] No-silent-pass NFR restated with specific handling, verified against machinery

The architecture's no-silent-pass commitment (every judge failure mode maps to an observable non-passing outcome) is restated in this slice with the slice-specific specifics: `UNKNOWN` cannot satisfy `until: review.pass` (confirmed — the condition requires the last verdict-bearing result to equal `PASS`), exhaustion produces an observable `PAUSED` StepResult (confirmed at `_loop_exhaust_result`), and the enforcement layer ignores rogue model-emitted verdicts (confirmed in `enforce_judge`, which derives solely from the score and logs at WARNING). The conservative-gating default ("checkpoint, not fail; escalate, not auto-pass") is also carried through.

### [PASS] Advisory-only mode is architecture-conformant and mechanically sound

The arch specifies weak-ground-truth judges are "configured advisory-only (a floor it effectively cannot clear, forcing escalation)"; the slice expresses this precisely as `pass_floor > 100` via the existing step-level override — one knob spanning auto-pass through always-escalate, verified against the enforcement layer's actual merge order (step override → template default → module constant). Score and findings still reach the human at the checkpoint, matching the arch's "advisory, not gating" intent.
