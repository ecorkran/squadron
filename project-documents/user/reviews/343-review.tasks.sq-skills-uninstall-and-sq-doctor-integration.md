---
docType: review
layer: project
reviewType: tasks
slice: sq-skills-uninstall-and-sq-doctor-integration
project: squadron
verdict: RESOLVED
sourceDocument: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260626
dateUpdated: 20260627
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Success criteria complete coverage"
    location: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Test-after-implementation pattern followed"
    location: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Commit checkpoints distributed throughout"
    location: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Correct task sequencing with proper dependencies"
    location: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md
  - id: F005
    severity: concern
    category: documentation-accuracy
    summary: "`pyright --strict` not explicitly specified in linter commands"
    location: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md:Task T8, T11, T16
    resolution: "T8, T11, T16 now read `pyright --strict`, aligning with success criterion 7."
  - id: F006
    severity: concern
    category: error-handling
    summary: "T4 TOML serialization approach could silently produce wrong output"
    location: project-documents/user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md:Task T4
    resolution: "T4 now requires TOML-quoting of all string values (cast destination to str) and TOML array syntax for files_written in the manual fallback."
---

# Review: tasks — slice 343

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Success criteria complete coverage

All 7 success criteria from the slice design are traced to specific tasks:
- SC1 (uninstall preserves unrelated files) → T9, T10 (test: "Unrelated file not removed")
- SC2 (graceful error on uninstalling uninstalled pack) → T9 (error message), T10 (exit code 1 assertion)
- SC3 (idempotent reinstall) → T16 (verification walkthrough step 6)
- SC4 (doctor includes Skill Packs section) → T12, T14, T15
- SC5 (fix hint on not-installed rows) → T12 (fix_hint="sq skills install <name>"), T13
- SC6 (JSON output includes skill pack checks) → T15
- SC7 (pyright/ruff compliance) → T8, T11, T16 (each with ruff format, ruff check, pyright, pytest)

### [PASS] Test-after-implementation pattern followed

All implementation tasks have corresponding test tasks immediately following:
- T2 → T3 (model), T4 → T5 (receipts), T6 → T7 (installer integration), T9 → T10 (uninstall), T12 → T13 (doctor check), T14 → T15 (doctor wiring)

### [PASS] Commit checkpoints distributed throughout

Three commits are distributed: T8 (receipt infrastructure), T11 (uninstall command), T17 (doctor integration + slice status). Not batched at end.

### [PASS] Correct task sequencing with proper dependencies

Logical order maintained: model (T2-T3) → receipts helpers (T4-T5) → installer integration (T6-T7) → CLI commands (T9-T10) → doctor integration (T12-T15) → validation (T16-T17). No circular dependencies detected.

### [CONCERN] `pyright --strict` not explicitly specified in linter commands

**Severity: CONCERN** — Success criterion 7 explicitly requires "pyright strict" but the lint commands in T8, T11, and T16 read `Run \`pyright\`` without the `--strict` flag. The slice design's success criteria states: "All new code passes `pyright` strict and `ruff` lint/format."

While `pyright` without flags uses default strictness which may be sufficient, the explicit mismatch between the stated success criterion and the command specified in tasks creates ambiguity. If strict mode is required per the success criteria, the tasks should read `pyright --strict`. If default mode is acceptable, the success criteria in the slice design should be updated.

Recommendation: Align the task commands with the success criteria by changing `Run \`pyright\`` to `Run \`pyright --strict\`` in T8, T11, and T16.

### [CONCERN] T4 TOML serialization approach could silently produce wrong output

**Severity: CONCERN** — The task instructs to use `tomli-w` if available in `pyproject.toml`, or "build a minimal TOML string manually for this simple flat structure" otherwise. The concern is that `InstallReceipt.destination` is a `Path` object. Pydantic's default JSON serialization of `Path` produces a string like `"/Users/you/.claude/commands/analysis"`, which is valid TOML. However, if the fallback manual TOML serialization uses naive Python string formatting (e.g., `f"destination = {receipt.destination}"`), it would produce invalid TOML like `destination = /Users/you/...` (no quotes).

The task does not specify that the fallback serialization must quote string values properly. The `tomli-w` path avoids this issue, but the manual path needs explicit instruction to use TOML-compliant string quoting.

Recommendation: Add to T4's implementation note: "If using manual TOML, ensure string values (pack_name, surface, destination) are quoted: e.g., `destination = \"{path}\"`."

---
