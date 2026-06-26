---
docType: review
layer: project
reviewType: tasks
slice: manifest-format-and-sq-skills-install-list
project: squadron
verdict: PASS
sourceDocument: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260625
dateUpdated: 20260625
findings:
  - id: F001
    severity: note
    category: uncategorized
    summary: "Origin column in `sq skills list` not explicitly tested"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
  - id: F002
    severity: pass
    category: uncategorized
    summary: "All success criteria trace to tasks"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Task sequencing respects dependencies"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Test-with pattern is correctly applied"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Commit checkpoints are distributed, not batched at end"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
  - id: F006
    severity: pass
    category: uncategorized
    summary: "No load test required; no NFR stated"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
  - id: F007
    severity: pass
    category: uncategorized
    summary: "All tasks are independently completable and appropriately scoped"
    location: project-documents/user/tasks/341-tasks.manifest-format-and-sq-skills-install-list.md
---

# Review: tasks — slice 341

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [NOTE] Origin column in `sq skills list` not explicitly tested

Success criterion 3 states "`sq skills list` shows installed/not-installed status for all manifest entries, noting origin (user-level or project-level)." The implementation plan in T10 correctly includes an "Origin (user/project)" column in the Rich table, and the data flow section confirms merged entries carry origin metadata. However, T12's only list test involving two packs (`Test sq skills list with a manifest containing one installed and one not-installed pack: output shows both with correct status`) does not verify that the origin column is present or populated in the output. The test checks status correctness but not origin-field correctness.

This is a minor gap: the schema is explicit, the implementation is specified, and the table-column test implies the column exists. Adding `and "Origin" in output` (or checking for "user" and "project" strings) to that test assertion would close it. No action required to unblock.

### [PASS] All success criteria trace to tasks

Every success criterion maps to implementation tasks:
- SC1 (schema + Pydantic validation): T1/T2/T4
- SC2 (install all source types): T5/T8/T10/T12
- SC3 (list with status + origin): T10/T12
- SC4 (idempotent install): T9
- SC5 (invalid source type → SkillSourceError, no traceback): T5/T10/T12
- SC6 (unreachable GitHub → clear message): T5/T10/T12
- SC7 (no manifest → actionable message, exit 1): T10/T12
- SC8 (mutually exclusive prefix/dispatch_file): T1/T2/T4
- SC9 (project-level override + both appear in list): T3/T4/T10/T12
- SC10 (pyright + ruff, zero errors): T7/T13/T14

No unmapped tasks; no orphan success criteria.

### [PASS] Task sequencing respects dependencies

Build order is correct: models (T1) → tests (T2) → manifest (T3) → tests (T4) → resolver (T5) → tests (T6) → commit (T7) → installer (T8) → tests (T9) → CLI (T10) → wiring (T11) → tests (T12) → full validation (T13) → commit (T14). Each layer depends only on already-built lower layers. No circular dependencies.

### [PASS] Test-with pattern is correctly applied

Every implementation task has a companion test task immediately following it: T1→T2, T3→T4, T5→T6, T8→T9, T10→T12. This pattern is consistently applied.

### [PASS] Commit checkpoints are distributed, not batched at end

Two checkpoints: T7 after the subpackage foundation (`models`, `manifest`, `resolver`) and T14 at final completion. This is appropriate — mid-stream checkpoint prevents a large feature commit from lumping unrelated modules together.

### [PASS] No load test required; no NFR stated

The slice design states no NFRs. All criteria are functional correctness statements. No load test task is needed, and none is missing.

### [PASS] All tasks are independently completable and appropriately scoped

Each task has a concrete success criterion (a command or import that must exit 0). Tasks are neither trivially small (e.g., T1 groups three model classes into one task rather than splitting into three) nor too large (the largest, T5, covers five source types but each has a single-entry specification). A junior AI can complete any task independently given its description.
