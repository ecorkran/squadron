---
docType: review
layer: project
reviewType: tasks
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260803
dateUpdated: 20260803
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "F003 archive fail-closed behavior partially covered by tests"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F002
    severity: concern
    category: uncategorized
    summary: "T14 sequencing dependency on T12 is documented but fragile"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F003
    severity: concern
    category: uncategorized
    summary: "Success criterion for judge-leg behavior preservation only covered by one suite"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F004
    severity: concern
    category: uncategorized
    summary: "No task for frontmatter findings parser production-shape test in this file"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F005
    severity: note
    category: uncategorized
    summary: "Part C success criteria deferred to file 2 with explicit handoff"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F006
    severity: note
    category: uncategorized
    summary: "Commit checkpoint distribution is appropriate"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F007
    severity: note
    category: uncategorized
    summary: "No NFR restated in slice design — no load test required"
    location: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md
  - id: F008
    severity: pass
    category: uncategorized
    summary: "All success criteria for Parts 0/A/D traced to tasks"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  - id: F009
    severity: pass
    category: uncategorized
    summary: "Test-with discipline and sequencing are correct"
    location: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
---

# Review: tasks — slice 306

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Resolution (20260803)

All four concerns fixed in the task file; all three notes acknowledged, no action needed.

- **F001 (concern, FIXED)** — What is now T14 (renumbered, see F002) gained a
  third test bullet for the read-back-verification-fails path, distinct
  from the copy-cannot-be-created case already covered: mock/monkeypatch
  the verification step to report a mismatch after a real successful copy,
  assert the overwrite still aborts and the original is unchanged.
- **F002 (concern, FIXED)** — Took the reviewer's option (a): the
  cf-archive-scanning checkpoint is now **T12, structurally before** the
  archive-guard implementation and its test (now T13/T14, renumbered up
  from T12/T13). The old trailing verification task (previously T14) is
  removed as a duplicate. T13 now states plainly that T12 must be complete
  before it starts and to use whichever archived-filename scheme T12
  settled on; the Handoff section and Context Summary's task references
  were updated to match.
- **F003 (concern, FIXED)** — Added an explicit NOTE to T2, T4, and T6
  stating each verifies a focused subset, not the full-suite gate, and
  that T8's `uv run pytest -q` is what actually confirms no regression
  outside the findings-addressed package for any of Part 0's intermediate
  commits.
- **F004 (concern, FIXED)** — Added a binding "findings round-trip test"
  bullet to T11: render a multi-severity `ReviewFinding` set through the
  real `format_review_markdown` (with `reviewed_sha` now set) and assert
  the `findings:` frontmatter shape is unchanged. Cross-referenced from
  file 2's T15 so a shape mismatch discovered there points back to this
  test rather than being silently absorbed into a looser reader.
- **F005, F006, F007 (note, ACKNOWLEDGED)** — no action. F005's "confirm
  file 2 exists" is satisfied — it was written in the same session as this
  breakdown, before this review ran.

## Findings

### [CONCERN] F003 archive fail-closed behavior partially covered by tests

T13 covers the unwritable-directory case but does not explicitly test the "verification fails after a successful copy" branch that T12 calls out (read back and compare bytes/size). The implementation in T12 enumerates two failure modes — copy cannot be created, OR verification fails — and both must abort. T13's bullet list only describes the copy-creation failure (file-where-dir-should-be). A junior AI implementing T13 against the listed bullets would likely omit the post-copy verification failure test. Consider adding a third bullet: simulate a copy that succeeds but mismatches on read-back (e.g., corrupt the archive file between copy and verify) and assert abort + original unchanged.

### [CONCERN] T14 sequencing dependency on T12 is documented but fragile

T14 is a "verification checkpoint" that may force changes back into T12/T13, but T12's effort budget (2/5) and T13's test list were written assuming the non-recursive cf case. The task acknowledges this ("Do not mark this task done until T14's verification outcome is known") but does not specify who re-opens T12/T13 or how the loop closes. Recommend either (a) reordering to put T14 immediately before T12 in the file so the gating is structural, or (b) adding an explicit "T12 re-open if T14 finds recursive scanning" checklist item with named acceptance criteria.

### [CONCERN] Success criterion for judge-leg behavior preservation only covered by one suite

The slice success criterion "305's full test suite passes unchanged — including after the `review/addressed/` relocation (F002)" is a single criterion but spans the full 305 suite (per the slice design, "2832 passed, 2 skipped" baseline). T2 and T4 each run a focused subset (`tests/pipeline/test_findings_addressed*.py` + one metrology test). T6 covers the judge extraction. T8 finally runs the full `uv run pytest -q` against the 2832 baseline. This is correctly sequenced (full-suite at the end of Part 0), but the intermediate T2/T4 partial runs are sufficient to ship each commit locally while the full-suite check is deferred to T8. Acceptable, but a junior AI may not realize that any intermediate commit (T1, T3, T5) is not fully verified until T8 lands. Consider a single in-line NOTE in T2/T4/T6 making this explicit.

### [CONCERN] No task for frontmatter findings parser production-shape test in this file

The slice design (Decision 2 + Dependencies section) calls out the F002 lesson that the parse in Part B must consume "exactly this shape (the production shape... no hand-rolled fixture formats)." Part B lives in file 2, but Part A changes `format_review_markdown` (T9) which produces that shape. There is no explicit test in T11 asserting that findings round-trip through `format_review_markdown` → re-parse — only that `reviewedSha` lands correctly. If T9 inadvertently changes how findings serialize, file 2's `records_from_frontmatter` will silently break against real artifacts. Recommend adding to T11: an assertion that findings emitted by `format_review_markdown` re-parse to equal `FindingRecord` objects (or that the existing 305 parse tests cover this — but the connection should be made explicit rather than left to the implementer).

### [NOTE] Part C success criteria deferred to file 2 with explicit handoff

The slice design's success criteria that pertain to Part B (e.g., `sq review resolve 305` produces correct artifact, `--no-judge` yields UNKNOWN, second run writes `-r2`) are not covered in this file. The handoff section correctly defers them to file 2, and file 1 is explicitly scoped to Parts 0/A/D plus Part B's preconditions. No gap, but a reviewer reading only file 1 should confirm file 2 exists and contains these criteria. If file 2 is not yet written, the breakdown is incomplete; if it exists, the handoff is sound.

### [NOTE] Commit checkpoint distribution is appropriate

Commits are interleaved with verification tasks (T2, T4, T6, T8 for Part 0; T11 for Part A; T13 for Part D) — six commit points across fourteen tasks, distributed throughout rather than batched at end. This matches the test-with discipline described in the file's preamble. PASS.

### [NOTE] No NFR restated in slice design — no load test required

The slice design does not restate any NFR from the parent (300-architecture.eval-actions-llm-as-judge-scoring.md) that would trigger a load-test requirement in `tests/load/`. No load test task is required for this breakdown. The performance-related concern (injection cap on diff size) is handled by a semantic WARNING + UNKNOWN rather than a performance gate, which is appropriate.

### [PASS] All success criteria for Parts 0/A/D traced to tasks

Cross-referenced each Part-0/A/D success criterion against tasks:
- `reviewedSha` from both CLI and pipeline paths → T9/T10/T11
- F002 (305 suite passes unchanged after relocation) → T2/T4/T6/T8
- F003 (failed archive copy aborts overwrite, original byte-identical) → T12/T13 (see CONCERN above on partial test coverage)
- F005 (cf archive-scanning verification as its own task before Part D lands) → T14
- Metrology `discover_judge_results` excludes resolution artifacts → named in T2's test command (covers the `*` glob excluding `*-resolution.*`); full Part C schema test lives in file 2
- Empty diff → UNADDRESSED with no judge → Part B (file 2), correctly out of scope
All in-scope criteria for this file have corresponding tasks. No scope creep detected: every task traces to either a Part-0/A/D success criterion or a design review finding (F002/F003/F005).

### [PASS] Test-with discipline and sequencing are correct

Every implementation task is immediately followed by a verification/test task: T1→T2, T3→T4, T5→T6, T7→T8, T9–T10→T11, T12→T13. T14 is a verification-only checkpoint (no implementation), so no following test is needed. No circular dependencies. Dependencies on 305 are honored (the file explicitly notes 305 is merged and its code review resolved).
