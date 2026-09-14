---
docType: tasks
slice: verification-that-verified-nothing
project: squadron
lldReference: project-documents/user/slices/919-slice.verification-that-verified-nothing.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [917, 918]
interfaces: []
status: complete
dateCreated: 20260914
dateUpdated: 20260914
---

# Tasks: Verification That Verified Nothing (1 of 2)

## Context Summary

Part 1 of three; Parts 2 and 3 are in `919-tasks.verification-that-verified-nothing-2.md`.

Three layers of this system report success having verified nothing:

- **Part 1 (#96, this file)** — a newline-free provider response breaks seven
  line-structure-dependent constructs in `review/parsers.py`, collapsing 4
  findings into 1 and losing the verdict. Worse: a naive fix can silently
  produce a *wrong* verdict (`CONCERNS` instead of the model's actual `PASS`),
  which is more dangerous than the UNKNOWN it replaces.
- **Part 2 (#97)** — a verdict derived from findings after a failed summary
  parse is indistinguishable, in frontmatter, from one the model actually
  stated, so Context Forge's review gate clears it. Fixed by a `verdictSource`
  frontmatter key.
- **Part 3 (#98)** — the commit gate hands `cf` explicit staged paths; in a
  sibling git worktree `cf` silently checks none of them and exits 0. The gate
  reads only the exit code and reports `ok`.

Full rationale, the three measured traps, and all design decisions (D1-D14)
are in the slice design — read it before starting, this file references it
rather than repeating it. Issues:
[#96](https://github.com/ecorkran/squadron/issues/96),
[#97](https://github.com/ecorkran/squadron/issues/97),
[#98](https://github.com/ecorkran/squadron/issues/98).

Sequenced **1 → 2 → 3** per the design (inverts the plan entry's `C → A → B`
— Part 1 is highest severity and Part 2's provenance vocabulary depends on
knowing how many distinct degradation shapes Part 1 produces). Part 1 lands
entirely in `review/parsers.py` (plus a `review/models.py` field and a
`review/persistence.py` digest line for D4); Parts 2 and 3 touch disjoint
files and do not depend on each other. Each part ends in its own
verify-and-commit task — do not batch across parts.

Branch: `919-slice.verification-that-verified-nothing`. Read
`cf config get git.integration_branch` first — fork from and merge to its
value, or `main` if empty.

### Verified code anchors (traced on `d1863815`, 20260914)

| Anchor | Location |
|---|---|
| `_SUMMARY_RE` | [parsers.py:70](src/squadron/review/parsers.py#L70) |
| `_FINDING_RE` | [parsers.py:81](src/squadron/review/parsers.py#L81) |
| `_CATEGORY_RE` / `_LOCATION_RE` | [parsers.py:106-107](src/squadron/review/parsers.py#L106-L107) |
| `_FILE_REF_RE` | [parsers.py:108](src/squadron/review/parsers.py#L108) |
| `_HEADING_RE` | [parsers.py:495](src/squadron/review/parsers.py#L495) |
| `_FENCE_OPEN_RE` | [parsers.py:487](src/squadron/review/parsers.py#L487) |
| `_mask_fences` (offset-preserving) | [parsers.py:498](src/squadron/review/parsers.py#L498) |
| `_locate_section` | [parsers.py:565](src/squadron/review/parsers.py#L565) |
| Title/body split | [parsers.py:643-646](src/squadron/review/parsers.py#L643-L646) |
| `_extract_verdict` | [parsers.py:124](src/squadron/review/parsers.py#L124) |
| `_verdict_from_findings` (#28 recovery) | [parsers.py:130](src/squadron/review/parsers.py#L130) |
| `parse_review_output` — the entry point to call normalization from | [parsers.py:728](src/squadron/review/parsers.py#L728) |
| `summary_section_located` computed via `_mask_fences` | [parsers.py:760](src/squadron/review/parsers.py#L760) |
| Newline-free digest indicator, D4's note | [persistence.py:197](src/squadron/review/persistence.py#L197), [:206](src/squadron/review/persistence.py#L206) |
| `_run_digest_lines` | [persistence.py:175](src/squadron/review/persistence.py#L175) |
| Fixture specimen (3076 chars, 0 newlines) | `project-documents/user/reviews/918-review.slice.review-grounding.md`, `### Raw Response` section |
| Snapshot guard | `tests/review/test_persistence.py:812`, fixture `tests/review/fixtures/clean_pass_artifact.md` |

Re-verify every cited line number before editing — grep offsets drift, as
918's slice review caught in this same design (F006).

---

## Part 1 — Newline-free responses parse (#96)

### T1.1 — Baseline the failing specimen against the existing committed fixture

- [x] **Do not create a new fixture file.** The specimen is already committed
      at `tests/review/fixtures/918-newline-free-response.txt` (3076 chars,
      zero `\n`, used by
      `test_real_newline_free_specimen_is_reported_as_newline_free` in
      `tests/review/test_persistence.py:1191`) — a second copy of the same
      blob would violate `CLAUDE.md`'s DRY rule and create a drift hazard.
      Reuse this file for every Part 1 test that needs the specimen.
- [x] Confirm it is still 3076 characters with zero `\n` before relying on
      it (`python -c "print(len(open(p).read()), open(p).read().count(chr(10)))"`)
      — this is a drift guard, not a creation step.
- [x] Write a test in `tests/review/` (the parser-focused suite, not
      `test_persistence.py`) that loads the existing fixture and asserts
      today's **broken** baseline via `_extract_verdict` and
      `_extract_findings`: `Verdict.UNKNOWN`, 1 finding,
      `FindingScanCounts(total=1, in_fences=0, in_section=1, surviving=1)`.
      This test is expected to start **failing** once Part 1 lands — that
      transition is the proof the fix works, so mark it clearly (e.g. a
      comment noting it documents the pre-fix baseline) rather than deleting
      it once T1.7 flips it.

**Success:** no new fixture file created; the baseline test reuses
`918-newline-free-response.txt` and its numbers match the design's recorded
20260913 measurement exactly. Effort: 1.

### T1.2 — Implement the normalization function, guarding Traps 1 and 2

- [x] Add a new function in `review/parsers.py` (e.g. `_normalize_line_structure`)
      that inserts a line break before the start of a complete `#{1,6}` hash
      run and after a recognized heading's text, per D1/D2.
- [x] **Trap 1 (mid-run hash insertion):** anchor insertion on the *start* of
      a hash run, never inside one — a lookahead like `(?=#{2,6}\s*\S)` fires
      on the second `#` of `###` and must not be used. Verify by hand against
      a string containing `...text### [FAIL] Title...` that the inserted
      break lands before the first `#`, not between the second and third.
- [x] **Trap 2 (fused heading text):** after inserting the pre-heading break,
      also insert a break after the heading's own text — reuse `_HEADING_RE`
      ([parsers.py:495](src/squadron/review/parsers.py#L495)) to identify
      where the heading word ends before the next word begins, since
      `[^\n]*?$` will otherwise swallow the entire following paragraph as
      heading text.
- [x] Do not yet handle Trap 3 (`location:` anchors) — that is T1.3, and D2
      requires it be verified as a separate, named step so a regression in
      one trap's fix cannot hide behind the other's test passing.

**Success:** running the function against the T1.1 fixture and re-measuring
with `_extract_findings` yields `total=4` (not yet necessarily `in_section=4`
— that requires T1.3). Effort: 3.

### T1.3 — Guard Trap 3: `#` inside a `location:` anchor is not a heading

- [x] Extend the normalizer so a `#` immediately preceded by non-whitespace
      (as in `...918-slice.review-grounding.md#The-problem-in-one-paragraph`)
      is never treated as the start of a heading run — insertion must anchor
      on structural position (start of line, or preceded by whitespace/start
      of string), never on the character alone.
- [x] Re-measure against the T1.1 fixture: `_locate_section(masked,
      "findings")` must now span all four findings, i.e. `in_section=4`,
      matching `total=4`.
- [x] Add a dedicated unit test isolating this trap: a synthetic string
      containing a `location:` line with a markdown anchor, asserting the
      normalizer inserts no break at that `#`.

**Success:** the T1.1 fixture, run through `_extract_findings` after
normalization, reports `total=4, in_section=4`. Effort: 2.

### T1.4 — Test all three traps against the naive normalizer

- [x] Add three unit tests, each constructed to **fail** if the naive
      first-cut approach (unconditional break before every `#`/`##`/`###`
      and every tag) were used instead of T1.2/T1.3's guarded version:
      1. A `###` embedded mid-run is not split into a bogus heading + demoted
         `##`.
      2. A fused heading word (`## SummaryPASSThe rest...`) is separated so
         `_HEADING_RE`'s captured text is just the heading word.
      3. A `#` inside a `location:` anchor does not truncate the findings
         section (T1.3's case, promoted to its own regression test here for
         visibility alongside the other two).
- [x] Each test's docstring or comment must state which trap it guards and
      reference D2, so a future change that reopens one is traceable to the
      decision it violates.

**Success:** all three tests pass against the current implementation and
each independently fails if its corresponding guard is removed (verify by
temporarily reverting one guard locally — do not commit the reverted state).
Effort: 2.

### T1.5 — Fix verdict fusion with a bounded search (D3)

- [x] Confirm the failure mode by hand first: running `_extract_verdict` on
      the T1.1 fixture with only a break inserted after `Summary` (no other
      changes) must return `Verdict.CONCERNS`, not `Verdict.PASS` — this is
      the specimen the design measured. Capture this as a regression test
      *before* fixing it, asserting `PASS` (not merely "not UNKNOWN").
- [x] Fix `_extract_verdict` ([parsers.py:124](src/squadron/review/parsers.py#L124))
      so its search for the verdict keyword is bounded to the summary
      section — it must not scan past a failed/fused match into a later
      finding's severity word. A bounded search within `_locate_section`'s
      summary span (or an equivalent structural bound) is the durable fix;
      do not merely require whitespace after the keyword, since that patches
      only the newline-free case and leaves the same unbounded `.*?` scan
      free to misfire on other malformed but line-broken text.
- [x] Re-run the T1.1 fixture end to end (normalize → mask fences → extract
      verdict): must return exactly `Verdict.PASS`.

**Success:** the fixture asserts `Verdict.PASS` explicitly; a test that
would also pass on `Verdict.CONCERNS` is not acceptable per the design.
Effort: 2.

### T1.6 — Wire normalization into the parse entry point (D5)

- [x] In `parse_review_output` ([parsers.py:728](src/squadron/review/parsers.py#L728)),
      call the T1.2/T1.3 normalizer **before** `_mask_fences`, and only when
      the response is detected as newline-free (`"\n" not in raw_output` —
      the same detection already computed for the digest at
      [persistence.py:197](src/squadron/review/persistence.py#L197)). Every
      other response takes the existing, unmodified path.
- [x] Confirm the offset contract: `_mask_fences` still receives the
      normalized string and every downstream span (`_locate_section`, fence
      masking) operates on it consistently — no function receives a mix of
      normalized and raw text.
- [x] Confirm the `### Raw Response` writer persists the **original**
      (un-normalized) `raw_output`, not the normalized string — trace the
      value it receives and correct if it currently receives whatever the
      parser handled internally.
- [x] Add a test pinning that a response **containing** newlines is passed
      through byte-identical to the normalizer (i.e. the function is a
      no-op on such input, or is not called at all on that path) — this is
      the D5 regression guard.

**Success:** the T1.1 fixture, run through the real `parse_review_output`
entry point (not the normalizer in isolation), yields `Verdict.PASS` and 4
findings, each with non-empty `category`, `location` not `"unverified"`, and
non-empty `description`. Effort: 2.

### T1.7 — Confirm the full pipeline and flip the baseline test

- [x] Run the T1.1 baseline test (still asserting the old broken numbers) —
      confirm it now **fails**, proving the fix changed behavior rather than
      the fixture being unreachable.
- [x] Update or replace that test to assert the fixed outcome instead
      (`Verdict.PASS`, 4 findings, per T1.6), removing the stale
      "documents the pre-fix baseline" framing — the design's success
      criterion 1 is the target state, not the regression marker.
- [x] **Pin that the verdict is *stated*, not merely derived to the same
      value.** `PASS` with 4 findings is also exactly what a
      literal-minded implementation would produce if normalization were
      wired only into the findings path while `_extract_verdict` still
      received raw text — `_verdict_from_findings`'s most-severe-wins
      derivation over 4 non-FAIL/CONCERN findings also yields `PASS`, with
      `fallback_used=True`. That would pass every other Part 1 criterion
      while silently missing D3. Assert `summary_section_located is True`
      (or `fallback_used is False`) on this same fixture run so Part 1
      itself proves the summary was actually parsed, not recovered.
- [x] Run `uv run pytest tests/review/ -k "newline_free or verdict_fusion" -v`
      and confirm every test added in T1.1-T1.6 passes together, not just
      individually.

**Success:** design success criteria 1-4 all hold against one shared run of
the real parse entry point, and the run is confirmed *stated* rather than
derived. Effort: 1.

### T1.8 — Confirm #91 (fence masking) does not reopen

- [x] Run the existing fence-masking test suite unchanged:
      `uv run pytest tests/review/ -k "fence" -v`.
- [x] Add one new test: a newline-free response whose text *quotes* the
      finding format inside a fenced code block (e.g. a fence containing
      literal `### [FAIL] Title` text as an example) must yield **no**
      findings extracted from the quoted text — normalization must not
      un-fence content `_mask_fences` correctly blanked.
- [x] Confirm the byte-identical snapshot guard is unaffected: run
      `uv run pytest tests/review/test_persistence.py -k clean_pass_artifact -v`
      and confirm it still passes with no fixture drift (a response
      containing newlines never reaches the normalizer per T1.6). This
      check runs against pre-T1.9 code, so it only proves today's snapshot
      is clean — it is not itself proof that T1.9's digest addition below
      will leave the snapshot undisturbed; T1.9 re-runs this same check
      after its change for that reason.

**Success:** design success criteria 5 and 6 hold; no existing fence or
snapshot test changed its expected output. Effort: 1.

### T1.9 — Disclose normalization in the run digest (D4)

- [x] Add a field to `ReviewResult` (`review/models.py`) carrying whether
      normalization ran and how many breaks were inserted — an inserted-break
      count is not recoverable from `raw_output` alone at render time
      (contrast the existing newline-free indicator, which is computed
      directly from `raw_output` in `persistence.py` and needs no field).
      Thread it from `parse_review_output`'s return through to the result.
- [x] **Pin the emission rule explicitly: the new digest line(s) are emitted
      only when normalization actually ran; a response that took the
      unmodified path (D5) emits nothing new.** This is not a free choice —
      it is what keeps design SC6 ("byte-identical except for intended
      digest lines") true against the `clean_pass_artifact.md` snapshot,
      which never triggers normalization. An "always emit, with
      count: 0 when it didn't run" design would add a line to every
      existing clean-pass artifact and break that snapshot.
- [x] Extend `_run_digest_lines` ([persistence.py:175](src/squadron/review/persistence.py#L175))
      with one or two new lines stating whether normalization ran and the
      break count, placed near the existing "Response is newline-free"
      indicator ([persistence.py:206](src/squadron/review/persistence.py#L206)),
      following the rule above.
- [x] Test: a normalized parse's digest shows normalization occurred with a
      non-zero count; a response containing newlines shows **no** new
      digest line at all (not a zero-count line — per the pinned rule
      above).
- [x] Re-run `uv run pytest tests/review/test_persistence.py -k clean_pass_artifact -v`
      now that this task's change has landed, and confirm it still passes
      with zero fixture drift — this is the check T1.8 could not yet make.

**Success:** design success criteria 7 and 8 hold — the digest discloses
normalization only when it ran, `### Raw Response` still holds the untouched
original text (re-confirm T1.6's persistence check here now that the digest
change touches the same render path), and the clean-pass snapshot is
unchanged. Effort: 2.

### T1.10 — Verify and commit Part 1

- [x] `uv run pytest tests/review/ -q` green.
- [x] `uv run ruff format --check . && uv run ruff check . && uv run pyright`
      clean — zero pyright errors, per `CLAUDE.md`.
- [x] Run the design's Part 1 verification walkthrough commands directly
      (the `uv run python -` snippet and the two `pytest -k` invocations in
      the slice design's Verification Walkthrough section) and confirm the
      "Expected after" numbers match exactly.
- [x] Commit: `fix(review): normalize newline-free responses before parsing (#96)`
- [x] Effort: 1
