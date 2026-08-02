---
docType: review
layer: project
reviewType: slice
slice: findings-addressed-gate
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/305-slice.findings-addressed-gate.md
aiModel: claude-fable-5
status: complete
dateCreated: 20260802
dateUpdated: 20260802
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "New capability housed in an initiative that excludes new capabilities"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:72-110
  - id: F002
    severity: concern
    category: error-handling
    summary: "Git-diff evidence path has no enumerated failure handling"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:156-167
  - id: F003
    severity: concern
    category: hidden-dependency
    summary: "Judge output persisted as a review file is a hidden cross-consumer contract"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:206-217
  - id: F004
    severity: note
    category: under-specification
    summary: "`moved`-with-successor-tracked is under-specified"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:195-196
  - id: F005
    severity: note
    category: error-handling
    summary: "Screen 2 exact matching collides on `unverified` locations"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:169-175
  - id: F006
    severity: note
    category: documentation
    summary: "Frontmatter dependencies omit 301"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:6
  - id: F007
    severity: pass
    category: architectural-alignment
    summary: "Parent plan alignment and process compliance"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md
  - id: F008
    severity: pass
    category: architectural-alignment
    summary: "304's boundaries respected; fail-closed NFR restated with specifics"
    location: project-documents/user/slices/305-slice.findings-addressed-gate.md:231-263
---

# Review: slice — slice 912

**Verdict:** CONCERNS
**Model:** claude-fable-5

## Findings

### [CONCERN] New capability housed in an initiative that excludes new capabilities

The parent architecture (`900-arch.maintenance-and-refactoring.md`, "Scope") explicitly excludes "New features or capabilities (use the appropriate feature initiative)." Slice 912 delivers a new gate policy (the first model-capable one), a new policy module, a new bundled judge template, and an example pipeline — this is a capability extension of the gate machinery whose extension seam (`VALID_GATE_POLICIES`) was declared by slice 304 in the **300 initiative** (eval-actions / LLM-as-judge). The natural home for "first use of 304's policy seam, consulting a judge" is that feature initiative, not the maintenance container. The slice plan (entry 10) does host it, and the lineage from 910/911 bug-fix work is real — but 910/911 were correctness fixes; 912 crosses from fixing behavior to adding behavior. At minimum the design should state why this lands under 900 rather than 300, since the parent architecture's own scope rule points the other way.

### [CONCERN] Git-diff evidence path has no enumerated failure handling

The decision procedure introduces a new I/O path — `git diff <sha_{n-1}> <sha_n>` via SHAs "in the commit action's outputs" — but unlike the judge path (transport failure → `UNKNOWN`, explicitly stated at lines 197-199 and pinned by a success criterion), the git path's failure modes are unhandled: (a) 911's `CommitAction` no-ops on a clean tree (`committed: False`), so a byte-identical round may leave **no** `sha_n` in outputs — the exact round Screen 1 most needs to detect; (b) the prior round's commit may be absent when `commit_each_iteration` is unset (the design's target shape sets it, but nothing stated forbids the policy on a non-committing loop); (c) the git subprocess itself can fail (bad SHA after history rewrite, detached state on resume). Whether these resolve to `UNKNOWN` (fail-closed, consistent with decision 2), to skipping Screens 1–2 and sending everything to the judge, or to a validation-time rejection of `findings-addressed` without `commit_each_iteration`, is unstated. Per the fail-closed principle the design otherwise applies uniformly, this needs an explicit strategy, not an implicit one.

### [CONCERN] Judge output persisted as a review file is a hidden cross-consumer contract

The judge's output rides the existing review parse/persist machinery with severity **overloaded** to encode status (`PASS`=addressed, `NOTE`=moved, `CONCERN`=unaddressed, `FAIL`=disputed) and `category:` overloaded to carry the prior finding id. The mapping is defined once in-module — good — but the *persisted file* is indistinguishable from a real review to every other consumer of review files: 904's location-discipline warnings and path-existence checks, `read_review_frontmatter`'s metrology consumers, and the ensemble-review dedup (slices 182/189) that keys merged findings on location/category. A `FAIL`-severity finding that actually means "disputed" (which the gate maps to `UNKNOWN`, *not* `FAIL`) sitting in a file named like a review is exactly the kind of semantic aliasing that misleads later tooling and humans reading the round's committed artifacts. The design should either name the file/frontmatter so downstream consumers can distinguish it (e.g., a distinct docType or provenance marker, consistent with 304's `composed` provenance precedent) or explicitly analyze why no current consumer misreads it.

### [NOTE] `moved`-with-successor-tracked is under-specified

The derivation rule passes the addressed leg when findings are `addressed` or "`moved`-with-successor-tracked," but the design never defines how a successor is tracked: which fresh finding is the successor, where the linkage is recorded (gate metadata? judge output field?), and what happens when the judge says `moved` but no successor appears in the fresh set (silently passed? downgraded to `disputed`?). Given the fail-closed discipline elsewhere, the untracked-successor case should have a stated outcome.

### [NOTE] Screen 2 exact matching collides on `unverified` locations

904 normalizes missing/blank locations to `unverified`, so two unrelated findings sharing a category and both located `unverified` will exact-match, marking a genuinely-addressed prior finding `unaddressed` with no judge consulted. This fails in the safe direction (consistent with decision 4), but a persistent false `unaddressed` traps the loop until exhaustion. Excluding `unverified` from Screen 2 keys (routing those to the judge) would preserve conservatism without the trap; worth a sentence either way.

### [NOTE] Frontmatter dependencies omit 301

The dependency table (lines 114-119) lists slice 301 as providing the derived-not-declared precedent this policy's derivation rule follows, but the frontmatter `dependencies:` field lists only `[911, 910, 304]`. Minor inconsistency; if 301 is precedent-only rather than a mechanical dependency, the table could say so.

### [PASS] Parent plan alignment and process compliance

The slice plan required a design conversation before Phase 4 and the design records it (20260801–20260802), including the reframe from "second history-aware reviewer" to gate policy — and the plan's entry 10 was updated to match, so plan and design tell one story. The plan's cost concern ("doubles review cost per iteration") is resolved structurally (screens spend no tokens, round 1 never consults a judge), and 900's lighter-weight guideline is respected in effort estimation and sequencing.

### [PASS] 304's boundaries respected; fail-closed NFR restated with specifics

The design extends the gate through 304's declared seam without touching what 304 forbade: the checkpoint and `_find_review_verdict` are unmentioned because they are unneeded — the judge is invoked inside gate execution, verdict accounting is unchanged, and the final verdict flows through the existing `reduce_verdicts` most-severe arithmetic where `UNKNOWN` dominates. The no-silent-pass posture is restated concretely (disputed/judge-failure → `UNKNOWN` → checkpoint; `most-severe` byte-identical regression pinned in success criteria), and the one deliberate deviation — round 1 as `PASS`-with-annotation rather than `UNKNOWN` — is argued, observable, and test-pinned rather than silent.

---

## Resolution (20260802)

All findings resolved by design revision and renumbering, same day. Note:
this file and the design were renamed 912→305 as part of F001's resolution;
finding `location:` line numbers reference the 912-numbered draft and drift
slightly against the revised document.

- **F001 — FIXED (renumbered).** Moved to slice **305 under initiative 300**
  (`300-slices` entry 6), which declared the `VALID_GATE_POLICIES` seam;
  `900-slices` entry 10 remains as a pointer preserving the
  design-conversation record. PM decision: a compromise, not a full cleanup —
  other judge-adjacent maintenance slices arguably belong there too, but they
  have code, commits, and closed issues; only this slice was still cheap to
  move. No new initiative.
- **F002 — FIXED (decomposed, not blanket-UNKNOWN).** Explicit git-path
  disposition added: policy on a loop with no per-round commit source →
  validation-time rejection; missing round-N SHA at runtime is not unknown —
  `committed: False` is already in `prior_outputs` and *is* Screen 1's
  byte-identical signal → `FAIL`; only a genuine git subprocess failure
  (unresolvable SHA) earns `UNKNOWN`. A new technical decision (8) states the
  governing rule: `UNKNOWN` is reserved for "the check could not run, and the
  system stops" — never the disposition for a condition whose right action is
  knowable.
- **F003 — FIXED (persistence dropped, transport kept).** The
  severity-encoding/review-file persistence is removed: it was decider
  evidence dressed in assessor vocabulary (violating the design's own
  principle 5), and metrology's `discover_judge_results` (`*-review.*` glob +
  `is_judge` filter) would have swept the evidence into the 320 calibration
  sample set today. The judge now emits status lines parsed by a small
  dedicated parser, and the gate persists one `gate-evidence` artifact with a
  distinct docType and a filename outside the `*-review.*` namespace —
  excluded by construction, not by filtering. Success criterion added pinning
  that `discover_judge_results` never returns one.
- **F004 — FIXED.** `moved` must name `successor=<fresh-finding-id>`; the
  gate verifies it exists in the fresh set; missing/unverifiable successor
  downgrades to `disputed` with a WARNING.
- **F005 — FIXED.** `unverified` locations excluded from Screen 2 match keys;
  those findings route to the judge. Success criterion added.
- **F006 — FIXED.** Dependency table now marks 301 as precedent-only,
  explaining its absence from frontmatter `dependencies:`.
