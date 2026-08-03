---
docType: review
layer: project
reviewType: tasks
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-2.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260803
dateUpdated: 20260803
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Full coverage of SC2 through SC13 across Parts B and C"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Test-with-implementation sequencing and distributed commit checkpoints"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md
  - id: F003
    severity: pass
    category: uncategorized
    summary: "CLI exit codes match the design's shell-composability requirement"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md#T35
  - id: F004
    severity: concern
    category: uncategorized
    summary: "SC11 \"review discovery\" function is not separately tested"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md#T32
  - id: F005
    severity: concern
    category: uncategorized
    summary: "Phase 5 note requires an `archive/`-scanning verification task that is not visible in this file"
    location: unverified
  - id: F006
    severity: concern
    category: uncategorized
    summary: "T33's \"no swallowed WARNING/ERROR\" requirement is not directly tested"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md#T33
  - id: F007
    severity: note
    category: uncategorized
    summary: "T20's test cases omit the `--since` + no-`reviewedSha` combination"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md#T20
  - id: F008
    severity: note
    category: uncategorized
    summary: "T29's cross-boundary refactor decision is properly deferred"
    location: 306-tasks.review-resolution-recording-that-findings-were-addressed-2.md#T29
---

# Review: tasks — slice 306

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Full coverage of SC2 through SC13 across Parts B and C

Every Part B/C-relevant success criterion from the slice design has a corresponding implementation and test task: SC2 (e2e + byte-identical review) → T33/T34, SC3 (empty diff) → T21/T22, SC4 (`--no-judge`) → T25/T26, SC5 (untouched-path downgrade) → T27/T28, SC6 (legacy/`--since` fallback) → T19/T20, SC8 (verdict-CONSISTENCY mismatch → UNKNOWN) → T23/T24, SC9 (judge transport failure + injection cap) → T25/T26, SC11 (metrology exclusion) → T32, SC13 (`-r{n}` versioned) → T31/T32, SC12 (305 suite unchanged) → T40. The three design-review rules each have their own dedicated impl/test pair (F001: T23/T24; F004: T25/T26; untouched-path: T27/T28) as the file's own header explicitly requires.

### [PASS] Test-with-implementation sequencing and distributed commit checkpoints

Every implementation task is immediately followed by its dedicated test task (T15→T16, T17→T18, T19→T20, T21→T22, T23→T24, T25→T26, T27→T28, T29→T30, T31→T32, T33→T34, T35→T36). Commit messages are interleaved after each impl+test pair (T16, T18, T20, T22, T24, T26, T28, T30, T32, T34, T36, T37, T38, T40) rather than batched at the end. T37 (slash-command parity, doc-only) and T38/T39 (docs/coordination) appropriately have no test.

### [PASS] CLI exit codes match the design's shell-composability requirement

T35 specifies `sys.exit(0)` on ADDRESSED and `sys.exit(1)` on UNADDRESSED/UNKNOWN, matching Decision 6 and the Verification Walkthrough's composability requirement. T36 explicitly tests both the success exit code and the ambiguous-type error path.

### [CONCERN] SC11 "review discovery" function is not separately tested

SC11 reads: "Metrology `discover_judge_results` and review discovery return no resolution artifacts (test against the real glob)." T32 only tests `discover_judge_results`. The constructive proof cited (the filename `{index}-resolution.{type}.{name}-r{n}.md` contains no `-review.` substring) is convincing only if "review discovery" uses the same `*-review.*` glob pattern as `discover_judge_results`. If they are distinct functions with distinct glob patterns (Decision 2's "verified" wording leaves room for this), then SC11 has a half-tested requirement. Either add a second test in T32 against the review-discovery function specifically, or have T32 assert that the two functions share a glob and the constructive proof applies to both.

### [CONCERN] Phase 5 note requires an `archive/`-scanning verification task that is not visible in this file

The slice design states: "Phase 5 note (review F005): the cf `archive/`-scanning verification in Decision 7 must appear as its own checklist task in the breakdown, sequenced before Part D lands — it is a go/no-go on the archive filename scheme." Part D (T12–T14, the overwrite guard) is in file 1 per this file's header. The verification task is therefore expected in file 1, sequenced before T12–T14. This file does not contain it, which is correct if file 1 contains it — but I can only review file 2, so I cannot confirm file 1 has it. If file 1 also lacks this task, the slice design's own go/no-go requirement is unmet. The reviewer of file 1 should confirm a task exists that (a) inspects cf's artifact-scanning code (or documented behavior) for recursion into `project-documents/user/reviews/archive/`, and (b) precedes T12–T14 in sequencing.

### [CONCERN] T33's "no swallowed WARNING/ERROR" requirement is not directly tested

T33 states: "Every WARNING/ERROR emitted by the steps above must actually surface (this function does not swallow or downgrade any log level a called function already chose)." This is a meaningful behavioral guarantee — without it, the F001 mismatch WARNING, the F004 transport-failure WARNING, and the file-history-fallback WARNING could all be silently dropped by orchestration code. T34's e2e tests do not assert log surfaces, and no other test in T15–T36 does either. Recommend adding one explicit assertion in T34 (or a dedicated test in T34/T36) that captures `caplog` and verifies a representative WARNING (e.g., the F001 mismatch or the file-history fallback) propagates through `resolve_review` at WARNING level, not INFO or below.

### [NOTE] T20's test cases omit the `--since` + no-`reviewedSha` combination

T20 covers: `--since` overriding present `reviewedSha`; `reviewedSha` present, no `--since`; `reviewedSha` absent, no `--since`. The combination of `--since` given with `reviewedSha` absent is not explicitly tested. T19's spec ("`since` given → always wins, `source='since'`") is correct for this case, but a junior implementer could mishandle "absent reviewedSha + since given" if not tested. Low-priority addition — the override-already-present case exercises the same code path, but the absent-frontmatter case is a distinct fixture.

### [NOTE] T29's cross-boundary refactor decision is properly deferred

T29 instructs the implementer to "decide based on what the code actually looks like once file 1's T5–T7 have landed" between promoting `_yaml_safe` to `review/addressed/` or adding a parallel copy. This is appropriately scoped — it matches Decision 4's review-domain logic placement and avoids hand-rolling a third unescaped writer (the F005 lesson). Not a concern, but the implementer should remember to update both call sites once the choice is made; the task wording does not explicitly enumerate the two callers that must change.
