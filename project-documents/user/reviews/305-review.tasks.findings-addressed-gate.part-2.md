---
docType: review
layer: project
reviewType: tasks
slice: findings-addressed-gate
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/305-tasks.findings-addressed-gate-2.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260802
dateUpdated: 20260802
findings:
  - id: F001
    severity: concern
    category: process
    summary: "Commit checkpoints batched at end of slice; file 2 contributes zero commit tasks across Parts D–G"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-2.md
  - id: F002
    severity: concern
    category: task-scoping
    summary: "T14 conflates a behavior-preserving refactor with new Screen 1 logic in one task"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-2.md:68-102
  - id: F003
    severity: note
    category: coverage
    summary: "Slice design's literal \"round SHAs\" (plural) criterion is only half-satisfiable, and the design doc's checkbox text isn't reconciled"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-2.md:94-100
  - id: F004
    severity: pass
    category: coverage
    summary: "Success criteria in scope for file 2 all trace to tasks"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-2.md
  - id: F005
    severity: note
    category: sequencing
    summary: "File 2's Part D is blocked on an unresolved FAIL in file 1's task sequencing"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-1.md:198-201
---

# Review: tasks — slice 305

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Commit checkpoints batched at end of slice; file 2 contributes zero commit tasks across Parts D–G

Parts D (T12–T16), E (T17–T22), and F (T23–T25) each end with a dedicated test task and a clear, independently-green success bar (T16: "`pytest tests/pipeline/` green"; T22: "all pass; no test reaches a real provider"; T25: "all pass") — but none is followed by a commit instruction. The only commit in the entire file is T30's close-out ("`ruff format` immediately before the commit; commit from the project root"). This confirms and extends the CONCERN already raised against file 1 (`305-review.tasks.findings-addressed-gate.part-1.md`, F002): across both files, the 30-task, 3/5-effort slice has exactly one commit point. This contradicts the project guideline "Git add and commit from project root at least once per task" and the review criterion that commit checkpoints be distributed throughout, not batched at the end. Each Part boundary here (post-T16, post-T22, post-T25) is a natural, test-verified commit point — losing work or needing to bisect a regression means reverting all of Parts D–G at once. Recommend adding an explicit commit step after each Part's test task.

### [CONCERN] T14 conflates a behavior-preserving refactor with new Screen 1 logic in one task

T14 ("Round diff and Screen 1 — byte-identical round", effort 3) does two structurally different things: (1) extract a new public `run_git` helper in `src/squadron/review/git_utils.py` and rewire `commit.py`'s private `_git` to delegate to it — an explicitly no-behavior-change refactor of existing, already-tested production code ("existing commit tests must stay green unmodified") — and (2) implement the new Screen 1 detection logic (working-tree diff vs `HEAD`, porcelain check, git-failure→`UNKNOWN` disposition, prior-SHA recording for the audit trail). Bundling a refactor of shared infrastructure with new gate-policy logic in a single task means a regression surfaced by T16's tests can't cleanly indicate whether the refactor or the new logic broke — and if the refactor step fails cleanly on its own (e.g., existing commit tests break), there's no task boundary at which to stop and commit the working refactor before attempting the riskier new logic. Splitting into "extract `run_git`, delegate `commit.py`, confirm existing commit tests green" (commit point) followed by "implement Screen 1 using `run_git`" would isolate the refactor's own success criterion from the new logic's, and give a rollback point if the new logic needs rework.

### [NOTE] Slice design's literal "round SHAs" (plural) criterion is only half-satisfiable, and the design doc's checkbox text isn't reconciled

T14 and T24 correctly implement and disclose (per file 1's Context Summary, "Item 3") that round N's own commit SHA cannot exist at gate-evidence-write time — only the prior round's SHA is recordable, paired with `revision_number`. This is a legitimate, well-justified deviation discovered during breakdown, not a defect in the task file. However, the slice design's Success Criteria still reads "Gate metadata carries per-finding statuses, settling screen, leg verdicts, and round SHAs" unchanged (`305-slice.findings-addressed-gate.md:380-381`), and no task in either file updates that wording to match the resolved (prior-SHA-only) contract. T28's "the design's Success Criteria list is walked item-by-item" will need a judgment call here rather than a literal check. Consider a small addendum in T30's close-out (or T28) to note the design-doc wording should be reconciled post-merge — informational, not blocking.

### [PASS] Success criteria in scope for file 2 all trace to tasks

Cross-referencing the slice design's 14 success criteria against Parts D–G: byte-identical→FAIL/zero-judge-calls (T14/T16/T28), round-1 `no_prior_round` (T13/T16/T28), exact-match settles without judge (T15/T16), contradiction downgrade (T20/T22), `moved`-without-successor downgrade (T20/T22), judge-transport-failure fail-closed path (T19/T21/T28), `unverified` excluded from Screen 2 (T15/T16), gate-evidence filename/discovery exclusion (T23/T25), metadata parity (T24), example pipeline end-to-end (T26/T28) all have a corresponding implementation task immediately followed by a test task. No task in file 2 is unmoored from a success criterion or design section (T27's resume-pinning task is explicitly scoped to Decision 5's caveat, not new work).

### [NOTE] File 2's Part D is blocked on an unresolved FAIL in file 1's task sequencing

Not a defect in this file, but worth restating since it gates file 2's start: the existing review of file 1 (`305-review.tasks.findings-addressed-gate.part-1.md`, F001, FAIL) found that T4 references T6's per-policy field mapping before T6 is scheduled, making Part B (and its test task T5, which constructs a `findings-addressed` gate before that policy value is registered) uncompletable as ordered. File 2's Part D correctly assumes Parts A–C are complete and consistent (per its own header), so this file cannot be a valid starting point for implementation until file 1's F001 is resolved.

---

## Resolution (20260802)

All three actionable findings resolved in
`305-tasks.findings-addressed-gate-2.md`.

**F001 (CONCERN) — resolved.** Commit instructions added at each part boundary,
as the final sub-item of that part's test task: Part D after T17, Part E after
T23, Part F after T26, Part G's integration work after T29 (T31's close-out
commit already existed). Parts A–C in file 1 received the same treatment. The
slice now has seven distributed commit points instead of one.

**F002 (CONCERN) — resolved by splitting the task.** The `run_git` extraction is
now **T14** ("Extract a shared `run_git` helper", refactor only, effort 1) with
its own success criterion — existing commit tests pass *unmodified* — and its own
commit instruction before the next task begins. Screen 1 is now **T15** and
consumes T14's helper. The finding's reasoning is adopted verbatim: a regression
surfaced downstream is now attributable to one or the other. Tasks T15–T30
renumbered to T16–T31; cross-references updated in both files.

**F003 (NOTE) — resolved at the source rather than deferred.** Rather than
carrying a reconciliation note into close-out, the slice design's success
criterion was corrected directly
(`305-slice.findings-addressed-gate.md`, Success Criteria): it now reads prior
round's SHA + `revision_number`, and states that round N's own SHA is
deliberately absent and not recordable, with the reason. Pre-implementation is
the cheap moment to fix design text; deferring it to T31 would have left a known
contradiction standing through all of Phase 6. T29's success bullet now says the
criterion is a literal check rather than a judgment call.

**F005 (NOTE)** — the file-1 sequencing FAIL it restates is resolved; see the
Resolution block in `305-review.tasks.findings-addressed-gate.part-1.md`.

The one PASS finding is recorded as-is; no action taken.
