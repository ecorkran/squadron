---
docType: review
layer: project
reviewType: tasks
slice: initiative-candidates
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/364-tasks.initiative-candidates.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260823
dateUpdated: 20260823
reviewedSha: b6d02ee469afbf2d7210a569a3b1964ca4bc9b66
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "All ten success criteria trace to a task and a verification step"
    location: "project-documents/user/tasks/364-tasks.initiative-candidates.md:346-414"
  - id: F002
    severity: pass
    category: coverage
    summary: "Cross-document corrections already satisfied, not a task-breakdown gap"
    location: "project-documents/user/architecture/360-slices.document-intelligence.md:154-160"
  - id: F003
    severity: concern
    category: sequencing
    summary: "No task commits (or explicitly discards) the real analysis document the walkthrough writes"
    location: "project-documents/user/tasks/364-tasks.initiative-candidates.md:361-367"
    resolution: addressed
  - id: F004
    severity: concern
    category: sequencing
    summary: "Close-out commits are batched rather than distributed"
    location: "project-documents/user/tasks/364-tasks.initiative-candidates.md:418-441"
    resolution: addressed
---

# Review: tasks — slice 364

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] All ten success criteria trace to a task and a verification step

Every SC1–SC10 has both an authoring task (Tasks 1–7) and an explicit `Success (SCn)` tag in Task 8's walkthrough subtasks (8.1→SC1, 8.2→SC2/SC3/SC5, 8.3→SC2/SC4/SC6/SC8, 8.4→SC2, 8.5→SC4, 8.6→SC6, 8.7→SC7, 8.8→SC3, 8.9→SC9/SC10). No criterion is unaddressed, and no task lacks a traceable criterion.

### [PASS] Cross-document corrections already satisfied, not a task-breakdown gap

The slice design's Implementation Notes require edits to `360-slices.document-intelligence.md` entry 4 and to `363-slice.concept-generation.md`'s Integration Points line. I initially suspected these had no corresponding task (Task 9.2 only says "Check slice-plan entry 4"), but both edits are already present in the committed files (360-slices.md:154-160 has the Phase 4 resolution; 363-slice.md:340-342 already qualifies "when a concept exists"). These were evidently made during the Phase 5 design commit (`192cdcf`), which is permitted to touch planning docs directly. Task 9.2's "check" wording is therefore a correct, minimal checklist-verification step, not a missing edit.

### [CONCERN] No task commits (or explicitly discards) the real analysis document the walkthrough writes

Task 8.3 runs the flow for real and confirms, which per the design writes `project-documents/user/analysis/945-analysis.initiative-candidates.md` into the actual repo tree (not a scratch copy, unlike 8.7/8.8). No later task explicitly stages/commits this file with an intentional message, nor states it should be deleted/left as a fixture. Task 9.3 only mentions a "final commit" for the DEVLOG before merge — it's ambiguous whether the walkthrough artifact rides along silently, is forgotten as untracked, or is accidentally swept into an unrelated commit. Add an explicit line (e.g., in 9.3 or a new 8.3 sub-bullet) stating what happens to `945-analysis.initiative-candidates.md`.

### [CONCERN] Close-out commits are batched rather than distributed

Tasks 1–7 each end with an explicit `Commit:` line, giving one commit per section. Task 9 breaks this pattern: 9.1 (reconcile walkthrough into design + record four deferred decisions) and 9.2 (status flips, slice-plan checkbox) have no `Commit:` line of their own; only 9.3 mentions a commit, implicitly bundling DEVLOG + whatever 9.1/9.2 changed into one final commit before merge. This is a minor inconsistency with the pattern established elsewhere in the same file — worth an explicit commit line on 9.1/9.2 (or an explicit statement that they're intentionally bundled into 9.3's commit) so a junior AI doesn't leave uncommitted state mid-close-out.

---

## Resolution

Both concerns addressed in the task file; the two PASS findings need no action. A second task review
(`deepseek-v4-pro`, archived at `reviews/archive/364-review.tasks.initiative-candidates.md`) raised
two additional concerns that are **false positives** — see below.

### F003 — walkthrough artifact — **addressed**

Correct and worth catching: Task 8.3 writes into the real tree while 8.7 and 8.8 use scratch copies,
and nothing said what became of the written file. It would have ended up untracked or swept into an
unrelated commit.

Resolved by keeping it deliberately rather than discarding it. Task 8.3 gains a statement that the
document is kept and committed, notes that it takes index **945**, and gets its own commit line
(`docs: add generated initiative candidates from walkthrough`). The reasoning recorded in the task:
it is the slice's proof artifact — the thing a reader checks the walkthrough's claims against — so
it is committed on its own rather than riding along in a later commit. The 8.3 success line now
requires the commit.

This mirrors how 363 handled its generated concept, with one difference: 363's output was archived
because squadron is not a repo that needs a generated concept. An initiative-candidates document has
no such conflict — it is an `analysis` artifact in the same series as `943`/`944`, and keeping it is
the normal outcome.

### F004 — batched close-out commits — **addressed**

Correct on the pattern break. Tasks 1–7 each end with a commit line; Task 9 had one only at 9.3,
implicitly bundling the design reconciliation and the status flips into the DEVLOG commit.

Resolved by distributing rather than by documenting the bundling: 9.1 gains
`docs: reconcile 364 walkthrough and record deferred decisions`, 9.2 gains
`docs: mark slice 364 complete`, and 9.3's commit is now explicitly scoped to the DEVLOG. 9.3 also
gains a clean-tree confirmation before the merge, naming 8.3, 9.1, and 9.2 as the steps that should
already have committed their own work — so an uncommitted close-out is caught at the merge boundary
rather than discovered afterward.

### Findings from the archived review — **not addressed, false positives**

The archived `deepseek-v4-pro` review raised two concerns claiming the cross-document corrections
were missing from the task breakdown:

- **F001 (archived)** — "Missing tasks to update `360-slices.document-intelligence.md` entry 4"
- **F002 (archived)** — "Missing task to update `363-slice.concept-generation.md` Integration Points"

Both edits were already made during Phase 4 and committed in `192cdcf`. Verified at
`360-slices.document-intelligence.md:154-160` (the two "Resolved in Phase 4" blocks replacing the
"Open at design time" blocks) and `363-slice.concept-generation.md:340-343` (the 364 line qualified
with **when a concept exists**). Planning-phase work commits directly to the target branch, so these
landed with the design rather than waiting for implementation.

Task 9.2's "check slice-plan entry 4" wording is therefore correct as written — a checklist
verification of an edit already made, not a placeholder for a missing one. The primary review
(`claude-sonnet-5`) reached the same conclusion independently and recorded it as F002 PASS, having
initially suspected the same gap and then verified the files.

No task-file change results from the archived review.
