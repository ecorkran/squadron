---
docType: review
layer: project
reviewType: tasks
slice: strict-type-checking-over-the-test-suite
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 71bd75d55c483b99321610b7e16a1e4e8991e28f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "D4's \"each site classified explicitly in the task breakdown\" is only partially met — ~17 of 25 `reportUnusedFunction` sites are left to a generic standing rule"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F002
    severity: concern
    category: process
    summary: "No commit checkpoint after Task 5.9 — the required Completion Summary has no commit home"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F003
    severity: concern
    category: traceability
    summary: "Task 6.3 reads promote-table rationale from data Task 1.8 never captures"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F004
    severity: note
    category: accuracy
    summary: "Task 6.4's \"three commits from Parts A–E\" miscounts — the slice produces six"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F005
    severity: note
    category: accuracy
    summary: "Task 5.8 header says 11 files but enumerates 12; it is also the widest-scope task"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F006
    severity: note
    category: sequencing
    summary: "`tests/cli/conftest.py` is fixed fifth in Part D despite being shared directory-wide"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F007
    severity: note
    category: coverage
    summary: "Task 6.2's config greps would not catch a leftover `enableTypeIgnoreComments = false`"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
  - id: F008
    severity: note
    category: scope
    summary: "No NFR/load-test gap: the slice design restates no performance NFR"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md"
  - id: F009
    severity: pass
    category: coverage
    summary: "All 11 success criteria trace to tasks, with gates distributed at every part boundary and no scope creep"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md"
---

# Review: tasks — slice 914

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] D4's "each site classified explicitly in the task breakdown" is only partially met — ~17 of 25 `reportUnusedFunction` sites are left to a generic standing rule

Design D4 ends with "Each of the 23 is classified explicitly in the task breakdown; none is resolved by guessing." The breakdowns explicitly enumerate only 8 sites: file 2's Tasks 2.7 (test_summary.py, 2) and 3.3 (test_inner_steps.py, 3), and this file's Task 5.3 (codex `test_agent.py`, 1) and 5.6 (`test_dispatcher.py` + `test_registry.py`, 2). File 1's re-measurement counts 25 sites across 20 files, so ~17 are handled only via this file's Context Summary ("D4, D6, D8 — applied per file") and file 2's standing rule. The rule is mechanical (fixture-decorated → suppress; otherwise delete), so nothing is resolved by guessing, but the design's letter requires site-level classification in the breakdown. Fix: add a per-site classification appendix derived from a fresh pyright run, or restate the standing rule so each fixing task records the sites it dispositioned.

### [CONCERN] No commit checkpoint after Task 5.9 — the required Completion Summary has no commit home

Tasks 6.1–6.4 modify real artifacts (the slice design's Completion Summary, frontmatter in three task files plus the slice, plan item 12, DEVLOG) but none contains a commit step. The design states "The slice is not done until this table is filled in and committed with it," and CLAUDE.md requires committing at least once per task. A literal executor could finish all four tasks with the summary and status flips uncommitted. Add an explicit commit step to 6.3/6.4 (e.g. `docs: fill in 914 completion summary, close statuses and issue`).

### [CONCERN] Task 6.3 reads promote-table rationale from data Task 1.8 never captures

Task 6.3 requires "the full promote table from file 1 Task 1.8/1.9 (symbol, new name, `src` sites, why it belongs in the contract)" — but file 1's Task 1.8 records one-line reasons only for keep-private entries; nothing captures a per-symbol rationale for promoted symbols. Task 6.3 is therefore not independently completable: a fresh session must reconstruct up to ~90 rationales after the fact, which invites exactly the circular "the test calls it, therefore it is de-facto public" justification D3 explicitly rejects. Fix: either Task 1.8 records a one-line promote rationale per symbol, or Task 6.3 states the rationale is re-derived per the D3 test at summary time.

### [NOTE] Task 6.4's "three commits from Parts A–E" miscounts — the slice produces six

Part A lands two commits (Tasks 1.12 and 1.14), plus 2.11, 3.10, 4.8, and 5.9 — six total. Task 6.4's issue-close text should reference the commits actually in `git log`, not the stated count of three.

### [NOTE] Task 5.8 header says 11 files but enumerates 12; it is also the widest-scope task

The enumerated list is 12 files (integrations 1, metrology 2, providers top-level 2, sdk 2, pr 1, core 1, documents 1, root conftest 1, load 1), and the Part E directory table also sums to 12 files; the error total of 37 is correct. The task's own "re-derive from a fresh `uv run pyright --outputjson`" instruction neutralizes the impact. Size is acceptable (each file ≤6 errors, effort 3/5, all within one part commit per D2), but it spans 8 directories — the most heterogeneous unit in the breakdown.

### [NOTE] `tests/cli/conftest.py` is fixed fifth in Part D despite being shared directory-wide

Task 4.5 itself notes that a conftest annotation fix "can silently clear downstream errors," yet it follows Tasks 4.1–4.4. Design D2 establishes that the cross-test import graph imposes no ordering constraint on parts, and Tasks 4.5 and 4.7 both re-measure, so this costs possible rework rather than correctness. Ordering conftest before 4.1 would have been cheaper but is not required.

### [NOTE] Task 6.2's config greps would not catch a leftover `enableTypeIgnoreComments = false`

The grep `basic|reportUnknown.*false|executionEnvironments` catches rule relaxations and per-directory blocks but not `enableTypeIgnoreComments`, which design D8 requires to stay at default. File 1's Task 1.3 removes the temporary value and Task 1.14 commits the real config, so the risk is low, but adding that key to Task 6.2's grep would close the audit hole.

### [NOTE] No NFR/load-test gap: the slice design restates no performance NFR

The design is a type-checking slice with no NFR restated, so no `tests/load/` coverage task or CI load-gate task is required. The only `tests/load/` touchpoint is remediating one error in `tests/load/test_grep_timeout.py` via Task 5.8, which is remediation, not NFR coverage. CI pickup of the config change is verified rather than assumed in file 1's Task 1.1, satisfying the Migration Plan's "confirm this in Part A" instruction.

### [PASS] All 11 success criteria trace to tasks, with gates distributed at every part boundary and no scope creep

Criteria 1–2 trace to Tasks 5.8/5.9 (plus file 1's 1.14); 3 to Task 6.2's grep; 4–5 to Task 6.1 step 1 (deletion done in 1.14); 6–7 to the per-part gates (4.8, 5.9) against file 1's Task 1.4 floor, re-verified in 6.1 step 3; 8 to Task 6.2; 9–11 to Task 6.3, which correctly preserves D6's "record zero if zero" clause. Part D and E file arithmetic is internally consistent and every file in file 1's baseline is claimed by exactly one task, with Tasks 4.7, 5.2, and 5.8 instructed to re-derive their lists rather than trust the enumeration. The test-with pattern is satisfied intrinsically: every fixing task carries its own pyright and pytest success criterion, and the rename pass has a dedicated test task (1.11) following implementation. The only tasks without a numbered-criterion trace are Task 6.4's bookkeeping steps, which trace to the design's Overview (issue #50 closure) and CLAUDE.md conventions — process mandate, not scope creep.

### Run Digest

- Response length: 8134 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 61448
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
