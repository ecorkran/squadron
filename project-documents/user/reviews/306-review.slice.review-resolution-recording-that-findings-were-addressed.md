---
docType: review
layer: project
reviewType: slice
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md
aiModel: claude-fable-5
status: complete
dateCreated: 20260802
dateUpdated: 20260802
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Empty CONCERN+ subset yields ADDRESSED, creating a silent-pass path on parse failure"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:150-152
  - id: F002
    severity: concern
    category: dependency-direction
    summary: "Review-package module depends on pipeline/actions internals — layering inversion with a package-level cycle"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:120-139
  - id: F003
    severity: concern
    category: error-handling
    summary: "Part D archive-copy failure mode not enumerated"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:298-301
  - id: F004
    severity: concern
    category: error-handling
    summary: "Judge-leg failure modes on the interactive path are covered only by implication; injection-cap constraint not restated"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:162-167
  - id: F005
    severity: note
    category: under-specification
    summary: "cf `archive/` scanning verification is an open pre-landing item"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:233-241
  - id: F006
    severity: pass
    category: alignment
    summary: "Verdict immutability and the second-assertion design align with the governing constraint"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:26-56
  - id: F007
    severity: pass
    category: alignment
    summary: "Reuse over rebuild; judge stays one-shot"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:207-215
  - id: F008
    severity: pass
    category: scope
    summary: "Scope matches the slice-plan entry; no creep"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md:71-101
---

# Review: slice — slice 306

**Verdict:** CONCERNS
**Model:** claude-fable-5

## Resolution (20260802)

All four concerns resolved by design edits; both notes carried.

- **F001 (concern, FIXED)** — The empty-CONCERN+ rule is now conditioned on
  verdict consistency: empty subset with a PASS verdict → ADDRESSED as
  before; empty subset with a FAIL/CONCERNS verdict → UNKNOWN + WARNING
  naming the mismatch. Data flow updated and pinned by a new success
  criterion citing the #28 parser lineage.
- **F002 (concern, FIXED)** — The context-free core (models, parsing,
  verification, extracted judge transport) **relocates to
  `review/addressed/`** rather than being imported across the boundary;
  `pipeline/actions/findings_addressed/` keeps only the loop-specific
  machinery (screens, gate evidence, policy) and imports the core in the
  established pipeline→review direction. Component structure, Decision 4,
  and a success criterion updated; 305's tests must pass unchanged across
  the move.
- **F003 (concern, FIXED)** — Part D is now explicitly fail-closed: copy to
  `archive/`, verify the copy, and only then overwrite; a failed or
  unverifiable copy aborts the save with an ERROR naming both paths and
  leaves the original byte-identical. Second test added for the unwritable-
  archive case.
- **F004 (concern, FIXED)** — Judge-leg failure modes are stated in the
  data flow rather than left to inference: transport failure/timeout/
  unreadable response → UNKNOWN + WARNING, and a diff exceeding the
  injection cap (reachable via `--since`) → UNKNOWN naming the cap and
  base. Success criterion added.
- **F005 (note, ACCEPTED)** — The cf `archive/`-scanning verification is
  pinned as a mandatory Phase 5 checklist item, sequenced before Part D.
- **F006–F008 (pass)** — no action.

## Findings

### [CONCERN] Empty CONCERN+ subset yields ADDRESSED, creating a silent-pass path on parse failure

The data flow states: empty CONCERN+ subset → resolution artifact with `resolution: ADDRESSED`, "nothing to judge." But the review parser is known to drop findings on occasion (this project has observed CONCERNS verdicts with empty parsed findings — issues #17/#28 lineage). A review whose frontmatter reads `verdict: FAIL` or `CONCERNS` but whose findings list parses to zero CONCERN+ entries is *inconsistent evidence*, and under this rule it produces `ADDRESSED` — the exact "quiet pass" the slice's own Principle 3 ("UNKNOWN means the check could not run") and the architecture's failure-mode commitment ("no failure mode silently yields a passing result," Technical Considerations) forbid. The rule should be conditioned on the parsed findings being consistent with the recorded verdict: FAIL/CONCERNS verdict + zero CONCERN+ findings → `UNKNOWN`, with a WARNING naming the mismatch.

### [CONCERN] Review-package module depends on pipeline/actions internals — layering inversion with a package-level cycle

`review/resolution.py` imports building blocks that live in `pipeline/actions/findings_addressed/` (judge core, `models.records_from_frontmatter`, evidence helpers). Verified against the code: every module in that package imports from `squadron.review.*` (`git_utils`, `models`, `parsers`, `review_client`, `templates`). The established direction — pipeline (140) consumes the review subsystem (100), per the architecture's Related Work — is inverted here, creating a review ↔ pipeline package-level cycle. The Decision 4 extraction decouples the judge from `ActionContext` but leaves the extracted core *physically* inside `pipeline/actions/`, so the CLI-facing review workflow still imports pipeline-action modules. The design already argues these are context-free building blocks; the consistent conclusion is to relocate them (e.g. into `review/` or a neutral shared module) rather than import across the layer boundary. Not blocking — no module-level import cycle results today — but the slice should either move the extracted core or explicitly justify the cross-package dependency.

### [CONCERN] Part D archive-copy failure mode not enumerated

Part D introduces a new I/O path (copy existing review into `archive/`, then overwrite). The design does not state what happens when the archive write itself fails — permissions, missing directory, disk full. If the subsequent `write_text` proceeds after a failed copy, the guard silently destroys exactly the content it exists to protect, inverting Part D's purpose. Per the architecture's failure-mode commitment and the project's Failure-Mode Enumeration rule, this path needs an explicit strategy (fail-closed: abort the overwrite and error if the archive copy cannot be confirmed) and a test asserting it.

### [CONCERN] Judge-leg failure modes on the interactive path are covered only by implication; injection-cap constraint not restated

The architecture enumerates judge failure modes explicitly — unparseable response, provider unavailable, injected ground truth exceeding the cap — each mapping to a non-passing, logged outcome. The slice's Principle 3 ("a residue finding no judge settled is disputed → UNKNOWN") plausibly subsumes transport failures, but the design never says so: timeout/hang, provider error, and unparseable judge output on the `sq review resolve` path are handled by inference from 305 reuse, not stated. More concretely, `--since REF` lets the diff base be arbitrarily old, so the injected diff can be unbounded — the architecture's injection-cap constraint applies to this path and is not restated in the slice, nor is cap-exceeded → UNKNOWN in the data flow or success criteria. One paragraph mapping {judge transport failure, oversized diff injection} → disputed → UNKNOWN + WARNING would close this.

### [NOTE] cf `archive/` scanning verification is an open pre-landing item

Decision 7 carries an explicit unresolved verification ("confirm cf's artifact scanning also ignores `archive/` before landing") with a stated fallback (mangle the archived name). This is honest and tracked, so informational only — but it should be a checklist item in the Phase 6 task breakdown so it cannot be skipped.

### [PASS] Verdict immutability and the second-assertion design align with the governing constraint

The slice-plan entry's central constraint — agents never edit `verdict:`; resolution is a separate, derived assertion — is faithfully carried through: separate `-r{n}` versioned artifact, `resolution:` deliberately not named `verdict:`, no flag that declares "addressed," derived-not-declared throughout. This also honors the architecture's *Additive over migratory* principle (the review artifact and existing verdict-gating are untouched) and the verified fact that cf gates on review frontmatter (cf consumption offered as a contract, not assumed — matching the review-gate-home boundary).

### [PASS] Reuse over rebuild; judge stays one-shot

The slice reuses 305's screens, `FindingStatus` vocabulary, `verify_outcomes`, judge template, and evidence rendering; the judge leg remains a one-shot call through `run_review_with_profile`. No new action type, no agentic loop — consistent with the architecture's *Reuse, don't rebuild* goal and the one-shot Non-Goal. Decision 3's honest accounting of what the interactive path loses (no exact-match screen, MOVED always downgraded) matches the arch's bubble-up/fail-toward-escalation posture.

### [PASS] Scope matches the slice-plan entry; no creep

Parts A–D map directly onto the slice-plan's verified facts and open contracts (reachability outside the loop, the overwrite hazard at `persistence.py:303`, the cf coordination seam). Part D looks like infrastructure work unrelated to judging, but the plan entry documents the overwrite hazard as a discovered constraint of this slice, so its inclusion is grounded, not creep. Exclusions (verdict edits, cf-side gating, fresh-review-inside-resolve) are explicit and correctly bounded.

**Verdict: CONCERNS** — four CONCERN findings, none blocking. The most important is the first: the empty-CONCERN+-subset → ADDRESSED rule combined with the known finding-dropping parser bug is a live silent-pass path that contradicts both the slice's own Principle 3 and the architecture's no-silent-pass commitment.
