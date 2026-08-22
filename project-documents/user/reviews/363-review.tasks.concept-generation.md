---
docType: review
layer: project
reviewType: tasks
slice: concept-generation
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/363-tasks.concept-generation.md
aiModel: qwen/qwen3.8-2.4t-a95b
status: complete
dateCreated: 20260822
dateUpdated: 20260822
reviewedSha: 3ae461ce5bacf5081bf3e020ab3a3591c605dc59
findings:
  - id: F001
    severity: concern
    category: requirements-coverage
    summary: "Dropped topics are not checked in the generated document"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.1"
  - id: F002
    severity: concern
    category: verification
    summary: "Guide absent/unreadable failure path is not exercised"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.3"
  - id: F003
    severity: concern
    category: verification
    summary: "Re-run verification does not fully prove mechanical refillability or expected interaction behavior"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.4"
  - id: F004
    severity: concern
    category: verification
    summary: "Inferred-claim governance is authored but not audited in the final artifact"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.1"
  - id: F005
    severity: note
    category: task-clarity
    summary: "Contract-failure walkthrough lacks a safe redirection mechanism"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.3"
  - id: F006
    severity: note
    category: sequencing
    summary: "Scope/discipline check timing is slightly out of order with close-out edits"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.6"
  - id: F007
    severity: note
    category: scope
    summary: "Hygiene checks are project-regression guards rather than slice success criteria"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md#task-8.6"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Core slice scope, sequencing, and commit checkpoints are sound"
    location: "project-documents/user/tasks/363-tasks.concept-generation.md"
---

# Review: tasks — slice 363

**Verdict:** CONCERNS
**Model:** qwen/qwen3.8-2.4t-a95b

## Findings

### [CONCERN] Dropped topics are not checked in the generated document

Slice design Success Criterion 4 requires that dropped topics — why-now, audience evolution, and methodology preference — appear nowhere in the generated concept, neither as content nor as gap markers. Task 4.1 correctly authors the dropped-topics rule, and Task 5.1 prevents extra questions, but no verification task explicitly checks the final `000-concept.squadron.md` for absence of those topics or related gap markers. Task 8.1 checks that nothing else was asked, but that does not prove the generated document did not include dropped-topic content or gap markers. Add an explicit final-document check in Task 8.1 or Task 8.6.

### [CONCERN] Guide absent/unreadable failure path is not exercised

Slice design Success Criterion 7 covers three contract-failure cases: concept guide absent, unreadable, or missing the expected section title. Task 6.1 authors all three failure behaviors, but Task 8.3 only exercises the renamed/missing `## User-Provided Concept` section case. There is no walkthrough step that verifies the loud stop when the guide file is absent or unreadable, or when the whole guide tree is absent and the flow should name `cf init` / `/cf:onboard`. Add a scratch-only failure case for absent/unreadable guide while preserving the rule that the real guide is never modified.

### [CONCERN] Re-run verification does not fully prove mechanical refillability or expected interaction behavior

Slice design Success Criterion 8 requires default-stop behavior, augment-or-stop choice, and mechanical refillability: augment may fill only empty sections or sections containing exactly a `[GAP: ...]` marker. Task 6.2 authors this rule, but Task 8.4 only verifies default stop, appending under a dated subheading, and byte-identity of populated sections. It does not verify that an empty or `[GAP: ...]` section is refillable, nor that real content is left untouched. Task 8.4 is also ambiguous about whether the re-run repeats the engagement interview or confirmation, what answers are appended, and whether the resulting augmented real document is the intended final committed artifact. Clarify the expected re-run interaction and add a scratch-based augment case against a document containing an empty or gap-marked section.

### [CONCERN] Inferred-claim governance is authored but not audited in the final artifact

Slice design Success Criterion 10 requires not only that provenance carries an inferred-claims line, but that every `[INFERRED]` sentence satisfies the checkable rule. Task 7.1 authors the rule, Task 7.3 authors the provenance line, and Task 8.1 checks that the inferred-claims line is present. However, no task verifies that every `[INFERRED]` sentence in the generated concept is actually graph-derived, non-literal, listed in provenance, and that no unmarked inferred claim exists. Add an explicit audit step to Task 8.1 or Task 8.6.

### [NOTE] Contract-failure walkthrough lacks a safe redirection mechanism

Task 8.3 says to copy the concept guide to scratch, rename the section heading in the copy, and “point the check at it.” The task does not explain how the flow is made to read the scratch copy without modifying the real guide or the skill file. A junior executor may improvise in a way that risks touching the real guide or changing the skill contract. Specify the safe scratch mechanism, for example a temporary worktree, path substitution if supported, or a clearly reverted local arrangement.

### [NOTE] Scope/discipline check timing is slightly out of order with close-out edits

Task 8.6 checks the changed-file set before Task 9.1 updates task/slice statuses and before Task 9.2 writes the DEVLOG entry. The check mentions the DEVLOG, but the DEVLOG change may not yet exist at that point. Likewise, status edits made in Task 9.1 occur after the Task 8.6 scope check. Consider clarifying that the changed-file check is preliminary, or adding a final lightweight scope check in Task 9.3 after close-out edits.

### [NOTE] Hygiene checks are project-regression guards rather than slice success criteria

Task 8.6 includes `uv run ruff format --check .` and `uv run pytest tests/skills/`. These are not directly traceable to a slice-design success criterion because the slice is markdown-only and explicitly adds no Python. They are reasonable project hygiene/regression checks, but they should be understood as project convention rather than slice-derived scope. This is not a defect, but it is worth labeling them as regression guards to avoid apparent scope creep.

### [PASS] Core slice scope, sequencing, and commit checkpoints are sound

The task breakdown respects dependencies, starts with branch and premise verification, authors the flow incrementally, verifies each authored section before moving on, and ends with an integrated walkthrough and close-out. There are no circular dependencies, no implementation task is missing its verification step, and commit checkpoints are distributed throughout rather than batched at the end. The tasks are generally small enough for a junior executor, with the largest task, Task 8.1, still bounded by a detailed checklist.
