---
docType: review
layer: project
reviewType: slice
slice: verification-that-verified-nothing
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/919-slice.verification-that-verified-nothing.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: 7b36737d0d1fcf25969eb20bc7c65a1244d8c8e7
findings:
  - id: F001
    severity: pass
    category: scope-alignment
    summary: "Scope fits the maintenance-and-refactoring container"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md"
  - id: F002
    severity: pass
    category: dependencies
    summary: "Dependency direction and cross-repo integration points are correctly modeled"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md#Cross-slice-dependencies-and-interfaces"
  - id: F003
    severity: concern
    category: correctness
    summary: "Part 3's file citations point at a package that does not exist"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md:104"
  - id: F004
    severity: concern
    category: correctness
    summary: "`_FENCE_OPENER` is cited by a name that doesn't exist in the codebase"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md:146"
  - id: F005
    severity: concern
    category: failure-mode-enumeration
    summary: "No hang/timeout handling specified for the modified subprocess I/O path in Part 3"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md#Part-3--Frontmatter-gate-fails-closed-98"
  - id: F006
    severity: note
    category: documentation-accuracy
    summary: "Several `parsers.py` line citations have drifted from current `main`"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md:135"
  - id: F007
    severity: note
    category: scope-cohesion
    summary: "Three-part bundling repeats an established pattern, not new scope creep"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md"
---

# Review: slice — slice 919

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Scope fits the maintenance-and-refactoring container

All three parts (#96 parser leniency, #97 verdict provenance, #98 fail-closed gate) are bug fixes / operational correctness work spanning the review subsystem and the commit-gate subsystem, matching 900-arch's scope ("Bug fixes," "Operational: ... configuration improvements that span subsystems") and its explicit exclusion of new features. No part introduces a new capability comparable to the one that got slice 912 moved out to initiative 300.

### [PASS] Dependency direction and cross-repo integration points are correctly modeled

Dependencies `[917, 918]` in frontmatter match the slice plan entry and point strictly backward to completed slices. The Context Forge schema addition (D6) and the Amoeba consumer relationship are named explicitly, and the doc correctly refuses to let squadron unilaterally enforce policy on a cross-repo consumer (D9) — consistent with the established seam recorded for this codebase (review-gating lives in CF/Amoeba, not squadron).

### [CONCERN] Part 3's file citations point at a package that does not exist

The "Lands in" table entry and two supporting citations (`frontmatter_gate.py:61` at line 380, `review_verdict_gate.py:97` at line 441) all resolve the path as `src/squadron/events/actions/...`. On current `main` there is no `src/squadron/events/actions/` package at all — both files actually live under `src/squadron/events/builtin/` (`pipeline/actions/` is a separate, unrelated subsystem used for dispatch/checkpoint actions). The line numbers themselves are correct (verified against the real files), but the directory is wrong everywhere it's cited, which risks task breakdown creating or searching a nonexistent path for Part 3's edit.

### [CONCERN] `_FENCE_OPENER` is cited by a name that doesn't exist in the codebase

D1's seven-construct list cites `_FENCE_OPENER` at `parsers.py:488`. The line number is correct, but the actual identifier at that line is `_FENCE_OPEN_RE`. A slice whose entire premise is that verification claims must be trustworthy ("a check that verified nothing must not report success") citing a symbol name that a grep for `_FENCE_OPENER` will never find is a small but pointed instance of the exact failure mode this slice exists to eliminate.

### [CONCERN] No hang/timeout handling specified for the modified subprocess I/O path in Part 3

Part 3 changes how `frontmatter_gate.py` invokes and interprets `cf validate frontmatter` (adding `--json`, parsing `filesChecked`). D10–D13 enumerate the "wrong output" failure modes (zero-checked, unparseable/absent key, empty staged list) but never address the process-hang case. The current implementation (`await proc.communicate()` in `frontmatter_gate.py`, confirmed on disk) has no timeout, so a `cf` process that hangs blocks the commit indefinitely with no WARNING and no observable signal — the "What if this hangs?" question `rules/review-code.md`'s Failure-Mode Enumeration rule requires be answered explicitly for any I/O path a slice touches is left unaddressed, even though this slice is actively modifying that path's contract.

### [NOTE] Several `parsers.py` line citations have drifted from current `main`

`_SUMMARY_RE` (cited 69, actual 70), `_FINDING_RE` (cited 80, actual 81), `_CATEGORY_RE`/`_LOCATION_RE` (cited 105-106, actual 106-107), `_verdict_from_findings` (cited 122, actual 124), and the title/body split (cited 641-644, but `body = "\n".join(lines[1:])` is actually at 646) are all off by 1-2 lines, while `_HEADING_RE`, `_mask_fences`, and every `persistence.py`/`models.py` citation checked landed exactly on the money. Not blocking — the doc already schedules a Phase 6 refresh ("Verification walkthrough... Draft. To be refined at Phase 6 completion") — but worth a pass before task breakdown locks these in as edit targets.

### [NOTE] Three-part bundling repeats an established pattern, not new scope creep

900-arch's guideline prefers "many small slices over few large ones," and this slice bundles three issues under a shared theme rather than three slices. This mirrors 901, 909, 910, and 916-918's own structure in this same slice plan, none of which were flagged for it, so it's consistent with accepted practice in this initiative rather than a new deviation worth blocking on.
