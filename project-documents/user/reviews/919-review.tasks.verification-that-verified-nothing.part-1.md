---
docType: review
layer: project
reviewType: tasks
slice: verification-that-verified-nothing
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md
aiModel: deepseek/deepseek-v4-flash-0731
status: complete
dateCreated: 20260914
dateUpdated: 20260914
reviewedSha: cbb88c2e42d93be8de8f9f91a89564acf2d5e7ed
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
findings:
  - id: F001
    severity: concern
    category: scope-creep
    summary: "T1.1 re-extracts a specimen that is already a committed fixture, from a path not present in the working tree"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md:83-101"
  - id: F002
    severity: note
    category: sequencing
    summary: "T1.8's \"no fixture drift\" claim and T1.9's digest change can conflict depending on the un-pinned field design"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md:246-267"
  - id: F003
    severity: note
    category: test-with
    summary: "Part 1's acceptance does not pin *stated* PASS — a wired-only-for-findings implementation would still pass every Part 1 check"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md:213-228"
  - id: F004
    severity: note
    category: git-conventions
    summary: "Part 1 batches ten tasks into a single commit against CLAUDE.md's per-task commit convention"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md:268-281"
  - id: F005
    severity: pass
    category: test-coverage
    summary: "The three D2 traps and the D3 fusion case each get dedicated, independently-failing regression tests"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md:103-186"
  - id: F006
    severity: pass
    category: coverage
    summary: "Diger/disclosure and persistence-of-original coverage is complete (SC7/SC8)"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-1.md:187-212"
---

# Review: tasks — slice 919

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4-flash-0731

## Findings

### [CONCERN] T1.1 re-extracts a specimen that is already a committed fixture, from a path not present in the working tree

The first checklist item tells the implementer to extract the `### Raw Response` section of `project-documents/user/reviews/918-review.slice.review-grounding.md` into a new `tests/review/fixtures/newline_free_specimen.txt`. Two facts make this wrong as written: (a) the working tree contains no `project-documents/user/reviews/` directory (its entries are `analysis/`, `archive/`, `slices/`, `tasks/`, …), so the cited source file is not available for extraction; and (b) the identical 3076-char, zero-newline specimen is already committed at `tests/review/fixtures/918-newline-free-response.txt` (content verified — it begins "I have enough information to evaluate the slice. Let me craft the final review.## SummaryPASS…" and is the verbatim fixture 918's walkthrough recorded, already consumed by `test_real_newline_free_specimen_is_reported_as_newline_free` in `tests/review/test_persistence.py:1194` and cited by this same design at `919-slice.verification-that-verified-nothing.md:135`). A second copy of the same 3076-char blob violates `CLAUDE.md`'s DRY rule and creates a drift hazard (design SC2 only requires the specimen be a committed fixture — it already is). T1.1 should reuse `918-newline-free-response.txt`, treating the re-verification step (`len()==3076`, zero `\n`) as a guard against drift rather than creating a parallel fixture.

### [NOTE] T1.8's "no fixture drift" claim and T1.9's digest change can conflict depending on the un-pinned field design

T1.8 (runs before T1.9) asserts the `clean_pass_artifact.md` snapshot guard "still passes with no fixture drift," but T1.9 immediately changes `_run_digest_lines` (`persistence.py:162`) and explicitly leaves open whether the normalization line is absent or `count: 0` when normalization did not run ("per whichever the field design chose — pin one explicitly"). Because T1.8 executes against the pre-T1.9 code, its assertion is trivially true and gives no assurance about the post-T1.9 state; if the implementation picks "always emit," the clean snapshot drifts and T1.8's claim is retroactively false. Recommend T1.9 pin the design as *emit only when normalization ran* (both the line and the count), which keeps design SC6's "byte-identical except for intended digest lines" intact and removes the contradiction.

### [NOTE] Part 1's acceptance does not pin *stated* PASS — a wired-only-for-findings implementation would still pass every Part 1 check

T1.6's checklist says to call the normalizer in `parse_review_output` before `_mask_fences` and that "no function receives a mix of normalized and raw text," but neither T1.6's nor T1.7's success criteria can detect a literal-minded implementation that normalizes only inside the findings path (`_extract_findings` masks internally) while still feeding raw text to `_extract_verdict`: the fixture would then yield `PASS` via `_verdict_from_findings` derivation (4 findings, most-severe-wins) with `fallback_used=True`, satisfying "verdict PASS, 4 findings, non-empty category/location/description" exactly. The stated-vs-derived distinction (D4/D7) only surfaces in Part 2's T2.3 cross-part test. Suggest T1.7 additionally assert `summary_section_located is True` (or `fallback_used is False`) on the shared fixture run so the stated path is pinned at Part 1 time.

### [NOTE] Part 1 batches ten tasks into a single commit against CLAUDE.md's per-task commit convention

T1.1–T1.9 accumulate with no commit until T1.10, departing from `CLAUDE.md`'s "Git add and commit from project root at least once per task." This is a deliberate, documented design override ("Each part ends in its own verify-and-commit task — do not batch across parts"), and slices 917/918 use the same pattern, so the three part-boundary commits (T1.10, T2.7, T3.11) do satisfy "commits distributed throughout, not batched at end." Recording this as informational so the deviation from the stated convention is explicit rather than accidental.

### [PASS] The three D2 traps and the D3 fusion case each get dedicated, independently-failing regression tests

T1.4 structures three unit tests that each fail on the naive normalizer, T1.3 adds an isolation test for the `location:` anchor trap, and T1.5 asserts `PASS` explicitly (with the "also passes on CONCERNS is unacceptable" guard matching D3's requirement). The baseline test in T1.1 with the red-to-green flip at T1.7 is an exemplary test-with pattern, and verified against `parsers.py` the cited anchors (`_SUMMARY_RE:70`, `_extract_verdict:115`/124, `_mask_fences:498`, `_locate_section:565`, `parse_review_output:728`, `_run_digest_lines:162`) exist as the tasks claim.

### [PASS] Diger/disclosure and persistence-of-original coverage is complete (SC7/SC8)

T1.6 explicitly tasks tracing the `### Raw Response` writer so the *original* (un-normalized) `raw_output` is persisted, and T1.9 adds the `ReviewResult` field threaded from `parse_review_output` plus digest lines near the existing newline-free indicator at `persistence.py:200-206` (verified present in source), closing both Part 1 SC7 and SC8 with tests. The D5 byte-identical-path pin (newline-containing input never normalized) is also present and is the correct guard for the `clean_pass_artifact.md` snapshot.

### Run Digest

- Response length: 6671 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 45885
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
