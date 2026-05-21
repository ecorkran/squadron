---
docType: review
layer: project
reviewType: tasks
slice: sq-setup-one-call-install-orchestrator
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/908-tasks.sq-setup-one-call-install-orchestrator.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260519
dateUpdated: 20260519
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Interactive mode recheck logic may be underspecified in task description"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md:T16
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Test for `--check-only` on all-OK fixture exists but is not standalone"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md:T18
  - id: F003
    severity: concern
    category: test-design
    summary: "Missing explicit test for `install.sh` state-diffing"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md:T26
  - id: F004
    severity: note
    category: design-clarity
    summary: "T28 conditional design is intentional"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md:T28
  - id: F005
    severity: note
    category: design-clarity
    summary: "Aggregate \"at least one provider OK\" suppression deferred per design"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md:T7
  - id: F006
    severity: pass
    category: uncategorized
    summary: "All 10 success criteria have corresponding tasks"
    location: unverified
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Test-with pattern is correctly applied throughout"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Task scope is well-bounded; no scope creep detected"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md
  - id: F009
    severity: pass
    category: uncategorized
    summary: "All tasks are independently completable by a junior AI"
    location: 908-tasks.sq-setup-one-call-install-orchestrator.md
---

# Review: tasks — slice 908

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Interactive mode recheck logic may be underspecified in task description

The slice design explicitly states that interactive mode re-checks **after each step** ("empty / enter → re-run that one check"), but T16's task description only says "After the loop, re-run `run_all_checks()` once and print a summary banner." While the indented behavior in T16's bullet points does describe per-step re-prompts, the summary line could mislead an implementer into skipping per-step recheck. The per-step recheck is tested in T23, so the coverage exists — but the task description should mirror the design's language more precisely to avoid confusion.

---

### [CONCERN] Test for `--check-only` on all-OK fixture exists but is not standalone

Success criterion 4 requires that "`sq setup --check-only` on a fully configured machine exits 0 with no prompts." T18 tests `--check-only` against a mixed fixture and an all-missing fixture, but the "all-OK → exit 0" assertion is bundled as a variant ("Variant with all-OK fixture → exit 0") rather than a named, independently runnable test. This is a minor granularity issue — the coverage exists — but it should be a separate test or clearly separated block to ensure it remains maintained if T18 is refactored.

---

### [CONCERN] Missing explicit test for `install.sh` state-diffing

Success criterion 6 states: "running it twice from a clean machine leaves the same state as running it once. (Tested by running it, recording state, running again, diffing.)" T26 creates stub functions and checks that install-side stubs are not re-invoked on the second run. This is a valid idempotency test, but it tests *command-invocation* idempotency rather than *state* idempotency. If a stub is called but the underlying state doesn't change (e.g., `npm i -g` run twice but the second is a no-op), the test passes. The test does not verify the "no state change" condition directly. For this slice the distinction is likely moot (the stub approach is sufficient), but the task should clarify which interpretation is intended.

---

### [NOTE] T28 conditional design is intentional

T28 says "If 906 has not yet merged, skip this task and add a TODO." This conditional execution is deliberate — the task design anticipates that docs/QUICKSTART.md may not exist yet. No action needed; this is correctly handled.

---

### [NOTE] Aggregate "at least one provider OK" suppression deferred per design

Success criterion 8 mentions "the aggregate 'at least one provider' suppression rule," but the design's implementation notes explicitly say: "In the initial release we keep this simple and just show all profile rows; the suppression optimisation is a follow-up." T7 implements no suppression. This is consistent with the slice design — not a gap. However, the task description does not call out this deviation, so if an implementer reads only the tasks (not the slice), they may not realize the suppression is intentionally omitted.

---

### [PASS] All 10 success criteria have corresponding tasks

Cross-reference summary:
- SC1 (`--help`): T17
- SC2 (non-interactive fresh machine): T15, T19
- SC3 (interactive walkthrough with recheck): T16, T23
- SC4 (`--check-only` fully configured): T14, T18
- SC5 (`--profile` filter): T7, T11, T20
- SC6 (idempotent `install.sh`): T25, T26
- SC7 (exit codes 0/1/2/3): T13, T16, T24
- SC8 (unit tests `build_steps`): T10, T11, T12
- SC9 (integration tests CliRunner): T18, T19, T20, T21
- SC10 (shell smoke test): T26

---

### [PASS] Test-with pattern is correctly applied throughout

Every implementation task has an immediate test task following it:
- T2 (data model) → T3 (test data model)
- T5 (_classify) → T6 (test _classify)
- T7 (build_steps) → T10, T11, T12 (test build_steps variants)
- T13 (Typer skeleton) → T17 (register) — though T14-T16 come before T17
- T14-T16 (rendering) → T18-T24 (tests)

The pattern is correctly applied.

---

### [PASS] Task scope is well-bounded; no scope creep detected

Every task traces to a success criterion or an explicitly documented deliverable (README pointer, DEVLOG, status update). No tasks introduce new check logic, provider changes, or other out-of-scope work. The `install.sh` scope is explicitly limited to pre-Squadron bootstrap steps.

---

### [PASS] All tasks are independently completable by a junior AI

Each task has explicit success criteria expressed as runnable commands (`pytest`, `pyright`, `python -c`, `shellcheck`). No task requires cross-cutting decisions or ambiguous judgment calls. The few points where judgment is needed (e.g., T8 docs anchor mapping "reproduce verbatim from 906") are explicitly documented.
