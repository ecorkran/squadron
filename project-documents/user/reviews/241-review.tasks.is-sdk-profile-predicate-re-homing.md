---
docType: review
layer: project
reviewType: tasks
slice: is-sdk-profile-predicate-re-homing
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260502
dateUpdated: 20260502
findings:
  - id: F001
    severity: concern
    category: task-completeness
    summary: "T2 omits conditional creation of `tests/providers/` directory and `__init__.py`"
    location: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
  - id: F002
    severity: concern
    category: task-completeness
    summary: "T9 staging list omits potential `tests/providers/__init__.py`"
    location: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
  - id: F003
    severity: pass
    category: completeness
    summary: "All 11 success criteria are mapped to tasks"
    location: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
  - id: F004
    severity: pass
    category: sequencing
    summary: "Task sequencing respects dependencies, no circular dependencies"
    location: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
  - id: F005
    severity: pass
    category: test-pattern
    summary: "Test-with pattern is followed"
    location: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
  - id: F006
    severity: note
    category: commit-strategy
    summary: "Single commit at end is appropriate for this atomic refactor"
    location: project-documents/user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md
---

# Review: tasks — slice 241

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] T2 omits conditional creation of `tests/providers/` directory and `__init__.py`

The slice design explicitly states: "Create `tests/providers/test_profiles.py` (or extend it if it exists)" and "Add `__init__.py` to `tests/providers/` if missing." Task T2 instructs to "Open `tests/providers/test_profiles.py`" and "Add parametric test (append after existing tests)," which assumes the file and directory already exist. A junior AI executor following these instructions literally would fail if `tests/providers/` doesn't exist yet. T2 should include conditional steps: (1) create `tests/providers/` directory if absent, (2) create `tests/providers/__init__.py` if absent, (3) create `tests/providers/test_profiles.py` if absent (versus append if present). This gap means SC7 (`tests/providers/test_profiles.py` exists and contains parametric coverage) could fail on execution through no fault of the implementer.

### [CONCERN] T9 staging list omits potential `tests/providers/__init__.py`

The "Files touched" context section and T9's staging checklist both list exactly 6 files. If `tests/providers/__init__.py` must be created (per the slice design's "if missing" clause), it would be a 7th file requiring staging. The staging step should account for this conditional file, either with a conditional checklist item or by noting it explicitly.

### [PASS] All 11 success criteria are mapped to tasks

Cross-reference of success criteria to tasks:
- SC1 (definition in new home) → T1
- SC2 (no longer defined in old home) → T6
- SC3 (`__all__` and docstring updated) → T6
- SC4 (prompt_renderer imports from new home) → T3
- SC5 (actions/summary imports from new home) → T4
- SC6 (test_summary_oneshot no longer imports/tests) → T5
- SC7 (test_profiles.py with parametric coverage) → T2
- SC8 (grep returns zero) → T7
- SC9 (full pytest passes) → T8
- SC10 (ruff + pyright pass) → T8
- SC11 (behavior identical) → implicitly covered by T3/T4 (unchanged call sites) + T8 (full suite)

No success criteria are unmapped; no tasks exist without a corresponding criterion.

### [PASS] Task sequencing respects dependencies, no circular dependencies

The ordering is correct: T1 (add definition) → T2 (test new definition) → T3/T4 (update importers while old definition still exists) → T5 (remove old test) → T6 (remove old definition) → T7 (grep verification) → T8 (quality gates) → T9 (commit) → T10 (closeout). This ensures callers are updated before the old definition is removed, and verification happens after all changes are complete.

### [PASS] Test-with pattern is followed

T2 (test at new home) immediately follows T1 (add definition at new home), consistent with the test-with pattern. Each import-update task (T3, T4) also includes a focused test run to verify the change immediately.

### [NOTE] Single commit at end is appropriate for this atomic refactor

The evaluation criteria prefer distributed commit checkpoints, but this slice is a mechanical atomic refactor where intermediate states (definition existing in both locations) are intentional migration scaffolding. A single commit capturing the complete migration is the correct strategy here. No action needed.
