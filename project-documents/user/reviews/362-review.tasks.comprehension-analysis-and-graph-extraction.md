---
docType: review
layer: project
reviewType: tasks
slice: comprehension-analysis-and-graph-extraction
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/362-tasks.comprehension-analysis-and-graph-extraction.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260819
dateUpdated: 20260819
reviewedSha: db72b8637ed87ffc8c8e14b1d4f7cc466f364207
findings:
  - id: F001
    severity: concern
    category: requirements-traceability
    summary: "SC1's \"inline in the body\" requirement has no task-level test"
    location: "project-documents/user/tasks/362-tasks.comprehension-analysis-and-graph-extraction.md:163-262"
  - id: F002
    severity: note
    category: test-coverage
    summary: "Task 6 batches four implementations behind one verification, unlike Task 5's tighter interleaving"
    location: "project-documents/user/tasks/362-tasks.comprehension-analysis-and-graph-extraction.md:208-262"
  - id: F003
    severity: pass
    category: requirements-traceability
    summary: "All thirteen success criteria trace to concrete tasks"
    location: "project-documents/user/tasks/362-tasks.comprehension-analysis-and-graph-extraction.md"
  - id: F004
    severity: pass
    category: sequencing
    summary: "Sequencing is dependency-correct and commits are distributed throughout"
    location: "project-documents/user/tasks/362-tasks.comprehension-analysis-and-graph-extraction.md"
---

# Review: tasks — slice 362

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] SC1's "inline in the body" requirement has no task-level test

Success Criterion 1 requires: "Every section of the generated document names the graph fields it derives from, **inline in the body**, matching the extraction mapping table." The precedent document (`project-documents/user/analysis/943-*.md`) satisfies this by opening each section with a lead sentence naming its source fields (e.g. "From `layers[]`.", "From `nodes[]` where `type == "file"`, field `complexity`."), in addition to the Provenance block's separate section-sourcing bullet list.

None of the section-authoring tasks (5.1 project identity, 5.3 entry points, 5.5 coverage, 6.1–6.4 deepened sections) include a success bullet requiring this inline lead-in convention — their "Source:" lines describe what the skill instructions should pull from, not what the generated section body must state. Task 8.1 (happy-path walkthrough) only checks for "`## Provenance` immediately under the H1 ... with a section-sourcing line per section," which is the Provenance-block attribution, not per-section inline attribution. As written, an implementer can satisfy every explicit checkbox in Tasks 4–6 and 8.1 while producing a document whose section bodies never restate their source fields, technically failing SC1 as literally worded. Recommend adding an explicit success bullet to each section-authoring task (mirroring the 943 "From X[]." pattern) and a corresponding check to Task 8.1.

### [NOTE] Task 6 batches four implementations behind one verification, unlike Task 5's tighter interleaving

Task 5 pairs each new section with its own immediate verify subtask (5.1→5.2, 5.3→5.4, 5.5→5.6). Task 6 instead implements four deepened sections (6.1–6.4, including 6.4's more complex endpoint-resolution logic) and defers all verification to a single 6.5. This is not a correctness gap — 6.5 does specifically re-check the mapping table row-for-row and exercises the section 6 edge selections — but it's an inconsistent granularity within the same breakdown, and it means a regression introduced in 6.1 or 6.2 isn't caught until three more edits have landed. Consider splitting 6.5 per-section (as in Task 5) if tighter localization of failures is wanted; not blocking.

### [PASS] All thirteen success criteria trace to concrete tasks

SC4/SC5 (layer counting, file-level selector) → Tasks 1, 2 with real-graph verification against the design's measured numbers (34/6/238). SC7 (fingerprints note) → Task 3. SC8 (analyze-codebase-prompt decision) → Tasks 7.2/7.3. SC9 (zero `[INFERRED]`) → Task 7.1, checked in 8.1. SC10/SC11 (read discipline, endpoint drift) → Tasks 0.3, 6.4, 8.5, 8.7. SC12/SC13 (spot-checks, changed-file set) → Tasks 8.3, 8.8. No orphaned criteria found beyond the SC1 nuance above; no scope creep — every task traces back to a design section, correction, or walkthrough step.

### [PASS] Sequencing is dependency-correct and commits are distributed throughout

Task 0.3's id-prefix contract check correctly precedes Task 6.4, which depends on that contract holding. Corrections (Tasks 1–3) precede the mapping table (Task 4), which precedes new/deepened sections (Tasks 5–6), which precede the walkthrough (Task 8) — matching the design's Implementation Notes order, with the one deviation (deferring the full flow run to Task 8.1 instead of re-running after corrections 1/2) explicitly documented and justified with a stated fallback (index 945 if the PM wants literal fidelity). Commits land at 1.2, 2.2, 3.1, 4.2, 5.6, 6.5, 7.3, 8.8, and 9.3 — spread across the whole breakdown, not batched at the end. No load-test/CI-gating requirement applies (the slice has no throughput NFR), and no task invents a vacuous one.
