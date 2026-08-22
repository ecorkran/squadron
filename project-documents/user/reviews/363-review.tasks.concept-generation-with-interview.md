---
docType: review
layer: project
reviewType: tasks
slice: concept-generation-with-interview
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/363-tasks.concept-generation-with-interview.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260822
dateUpdated: 20260822
reviewedSha: a73aa02f6ae91b277981b05723bb15908030ed66
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "All 15 success criteria trace to implementation and verification tasks"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Verification Walkthrough step 3 (live flow-selection check) has no task, and Task 1.2 points at a Task 8 item that doesn't exist"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:101-106"
  - id: F003
    severity: concern
    category: coverage
    summary: "Design Implementation Note — editing 362's \"slices 363 and 364\" sentence — has no owning task"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Task 8.3 (correction path) doesn't specify its run environment and is blocked on the real tree by 8.1's output"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:342-348"
  - id: F005
    severity: concern
    category: commit-checkpoints
    summary: "All implementation work is committed in a single final commit"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:389-394"
  - id: F006
    severity: note
    category: coverage
    summary: "SC12's coverage boundary is implemented only via a table-cell transcription"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:124-135"
  - id: F007
    severity: note
    category: coverage
    summary: "SC14 has no explicit verification step"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:317-331"
  - id: F008
    severity: note
    category: test-coverage
    summary: "Decline-path (6.2) and path/provenance rules (7.1, 7.3) have no immediate test task"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:254-311"
  - id: F009
    severity: note
    category: task-clarity
    summary: "Placement and anti-duplication guidance for the new flow section lives only in the design"
    location: "project-documents/user/tasks/363-tasks.concept-generation-with-interview.md:112-135"
---

# Review: tasks — slice 363

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [PASS] All 15 success criteria trace to implementation and verification tasks

Cross-referencing every criterion: SC1→1.1/1.2; SC2→2.1/2.2/3.2; SC3→3.1/3.2/8.1; SC4→6.2/8.2; SC5→4.1/5.1/8.1/8.4; SC6→4.1/4.2; SC7→5.1/5.2/8.4; SC8→7.2/7.4/8.1; SC9→6.2/7.3/8.1; SC10→6.1/6.3/8.1; SC11→7.1/8.1; SC12→2.2 (table row)/8.1; SC13→8.5; SC14→8.1 (implicit); SC15→4.2/8.5. Design walkthrough steps 1, 2, and 4–9 are all mapped to tasks (0.2, 4.2, 8.1–8.5) — only step 3 is missing (see the concern below). No task traces to anything outside the design's scope; Tasks 0 and 9 are standard process/closure overhead.

### [CONCERN] Verification Walkthrough step 3 (live flow-selection check) has no task, and Task 1.2 points at a Task 8 item that doesn't exist

Task 1.2 states "This check is re-verified live in Task 8 (walkthrough step 3); no standalone execution here," but Task 8 (8.1–8.5) implements only design walkthrough steps 4–9. Steps 1 and 2 were correctly distributed to Tasks 0.2 and 4.2; step 3 ("Confirm all four cases: no argument and `comprehension` run the comprehension flow; `concept` runs this flow; `candidates` is unrecognized and stops") was dropped entirely. As written, SC1's four-case routing receives only the read-through inspection in 1.2, the design's live confirmation never happens, and a junior AI following the checklist is misled by a dangling cross-reference into believing it is covered. Fix: add a Task 8 subtask executing design walkthrough step 3 (naturally placed before 8.1), or correct 1.2's claim.

### [CONCERN] Design Implementation Note — editing 362's "slices 363 and 364" sentence — has no owning task

The design's Implementation Notes require: "362's sentence 'The concept flow and the initiative-candidates flow are slices 363 and 364' is edited to reflect that the concept flow now exists." No subtask in Tasks 0–9 mentions this edit — Task 1.1 touches only the unrecognized-argument sentence, and Task 6.1 touches only the Gap markers forward-pointer. If missed, the shipped `commands/analysis/understand.md` will describe the concept flow as a future slice after it exists, contradicting itself. Trivial fix: add a checkbox to Task 1.1 or 2.1.

### [CONCERN] Task 8.3 (correction path) doesn't specify its run environment and is blocked on the real tree by 8.1's output

Task 8.1 writes the real `000-concept.squadron.md`; per the re-run semantics added in Task 5.1, any subsequent run on the real tree reports the existing document and defaults to stop — never reaching the Overview confirm-or-correct interaction that 8.3 must exercise. Task 8.2 explicitly runs "in a scratch copy of the tree"; 8.3 says only "re-run and correct," inheriting the design's step 6 ambiguity. The task should specify a fresh scratch copy containing no concept document (or deletion of the doc within a copy) so the correction interaction is actually reachable. It would also help to state for 8.2 that the scratch copy must not contain 8.1's output (true only if copied from committed state, since 8.1's file commits in Task 9 — currently implicit).

### [CONCERN] All implementation work is committed in a single final commit

The only commits in the plan are Task 0.1 (the design-review file, before branching) and Task 9.3 ("commit remaining changes"); Task 8.1 even defers its artifact ("file committed in Task 9"). All skill-file edits from Tasks 1–7, the generated concept document, status updates, and the DEVLOG land in one end-of-slice commit — checkpoint commits are batched at the end rather than distributed. Committing after logical groups (e.g., after Task 1, after Task 5, after Task 7, after Task 8) would keep the walkthrough's `git diff` evidence in 8.4 and 8.5 scoped per stage and avoid losing a long session's work. If single-commit-per-slice is an established project convention it should be stated; nothing in the file says so.

### [NOTE] SC12's coverage boundary is implemented only via a table-cell transcription

Task 2.2's success criterion is a faithful transcription of the design's seven-row table, whose Solution Approach interaction cell reads "Confirm-or-correct the derived summary, plus coverage boundary." That single phrase is the only implementation instruction for SC12 — no task tells the skill text what the coverage boundary is or that it is sourced from 362's coverage facts (design, "Three facts that shaped this design," fact 3). Task 8.1 verifies the boundary live, so a gap here surfaces only at the end of the slice. A junior AI could satisfy 2.2's success criteria while the skill gives the executing flow no content for the boundary. Consider a bullet in 2.1 or 2.2 naming the boundary's source.

### [NOTE] SC14 has no explicit verification step

"Running against squadron produces a concept a PM would edit rather than discard" (SC14) is subjective and is only implicitly the aggregate of 8.1's checklist — the design's walkthrough has no dedicated step for it either. Consider an explicit judgment line in 8.1's success criteria, or an explicit statement that SC14 acceptance happens at PM review in 9.3, so it isn't silently assumed.

### [NOTE] Decline-path (6.2) and path/provenance rules (7.1, 7.3) have no immediate test task

Task 6.3 tests only 6.1's worked examples; 6.2's decline-path text is first exercised live in 8.2. Task 7.4 tests only 7.2's frontmatter against the gate; 7.1's path/divergence rule and 7.3's provenance shape are first verified in 8.1. Additionally, SC11's "the graph value appears in provenance" half is implemented in 7.1 but appears in no later checklist — 8.1 checks the filename and the Overview statement only (mirroring the design's step 4, so the omission is inherited). Deferring live checks to Task 8 is defensible for prose-only artifacts, but cheap inspection checks — e.g., confirming 7.3's four-outcome enumeration matches the design and 7.1's provenance clause is present — would tighten the loop.

### [NOTE] Placement and anti-duplication guidance for the new flow section lives only in the design

The design's Implementation Notes specify the new flow is a sibling section placed "after Flow: Comprehension Analysis and before the human-documentation divider," and that shared conventions (Preflight, Document Conventions) are referenced rather than duplicated. The Context Summary conveys the sibling-section intent, but no task's instructions state the position or the no-duplication rule — Tasks 2.1–7.3 all say "Add..." without placement. Since tasks already cite design line numbers for content, adding the placement/no-duplication requirement to Task 2.1 (the first "add a new subsection" task) would keep a junior AI from scattering the additions or copying the preflight text into the new section.
