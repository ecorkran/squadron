---
docType: review
layer: project
reviewType: tasks
slice: precompact-hook-for-interactive-claude-code
project: squadron
verdict: PASS
sourceDocument: project-documents/user/tasks/157-tasks.precompact-hook-for-interactive-claude-code.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260407
dateUpdated: 20260407
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "All success criteria mapped to tasks"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Task sequencing respects dependencies"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Test-with pattern properly followed"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Commit checkpoints distributed throughout"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Exhaustive merge test coverage"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Appropriate scoping: each task is independently completable"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Error handling is explicitly justified"
  - id: F008
    severity: note
    category: error-handling
    summary: "Schema validation caveat is acknowledged"
  - id: F009
    severity: note
    category: documentation
    summary: "README vs authoring guide scope"
    location: Slice design: Implementation Details
  - id: F010
    severity: pass
    category: uncategorized
    summary: "No scope creep detected"
---

# Review: tasks — slice 157

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] All success criteria mapped to tasks

Each of the 15 success criteria has corresponding implementation and test tasks:

| Success Criteria | Tasks |
|-----------------|-------|
| SC #1: Fresh install creates settings.json with hook entry | T10, T8 |
| SC #2: Install is idempotent | T10, T8 |
| SC #3: Appends to existing unrelated PreCompact hooks | T8 |
| SC #4: Uninstall removes squadron entry, leaves others | T11, T9 |
| SC #5: Uninstall on no squadron entry is no-op | T11, T9 |
| SC #6: `compact.template` config key works | T1 |
| SC #7: `compact.instructions` config key stores literal | T1 |
| SC #8: Hook with CF project resolves `{slice}` | T3, T4, T5 |
| SC #9: Hook outside CF project preserves placeholders | T4 (returns `{}`), T5 |
| SC #10: `compact.instructions` wins over template | T3 |
| SC #11: Both keys set → instructions wins | T3 |
| SC #12: Missing/corrupt template → exit 0 with empty context | T3 |
| SC #13: Hidden from `sq --help` | T6 |
| SC #14: Real end-to-end smoke in Claude Code | T14 |
| SC #15: All tests pass | T13 |

No gaps between success criteria and tasks.

---

### [PASS] Task sequencing respects dependencies

The dependency chain is sound:
- T1 (config keys) → required before anything can use the keys
- T2 (extract helper) → required by T3 and T5
- T3 + T4 (helpers) → required by T5 (main command)
- T5 (command) → required by T6 (registration)
- T7 (settings helpers) → required by T8 + T9 (merge logic)
- T8 + T9 (merge logic) → required by T10 + T11 (wiring)
- T10 + T11 (wiring) → required by T14 (e2e smoke)
- T13 (lint/test) → should run before T14 (smoke)

No circular dependencies or ordering violations.

---

### [PASS] Test-with pattern properly followed

Every implementation task (T1–T11) has a corresponding test task immediately following it:

```
T1 → Test T1
T2 → Test T2
T3 → Test T3
T4 → Test T4 (extend)
T5 → Test T5 (extend)
T6 → Test T6
T7 → Test T7
T8 → Test T8 (extend)
T9 → Test T9 (extend)
T10 → Test T10
T11 → Test T11
```

Tests extend the same file rather than creating new files where appropriate (T4 extends T3's test file, T8/T9 extend T7's test file), which is appropriate given the module structure.

---

### [PASS] Commit checkpoints distributed throughout

Commits are distributed at logical points after each major unit of work:
1. `feat: add compact.template and compact.instructions config keys`
2. `refactor: extract LenientDict and render_with_params to compact_render module`
3. `feat: add _resolve_instructions helper for PreCompact hook`
4. `feat: add _gather_params helper for PreCompact hook`
5. `feat: implement _precompact-hook Typer command`
6. `feat: register hidden _precompact-hook subcommand on sq app`
7. `feat: add settings.json load/save helpers for hook install`
8. `feat: implement _write_precompact_hook with non-destructive merge`
9. `feat: implement _remove_precompact_hook preserving third-party hooks`
10. `feat: install PreCompact hook entry during sq install-commands`
11. `feat: remove PreCompact hook entry during sq uninstall-commands`
12. `docs: document PreCompact hook and compact config keys`
13. `chore: lint and typing fixes for precompact hook slice` (conditional)
14. `fix: adjust PreCompact hook payload to match Claude Code schema` (conditional)
15. `docs: mark slice 157 PreCompact hook for interactive Claude Code complete`

No commit batching at the end; commits track the natural development progression.

---

### [PASS] Exhaustive merge test coverage

The settings.json merge logic (T8/T9) has intentionally comprehensive test coverage:

**T8 write tests:**
- Fresh file creation
- Existing non-squadron entry → appends (not replaces)
- Existing squadron entry → replaces in place
- Both entries present → correct handling
- Idempotency on double-write
- Unrelated keys preserved
- Other hook event names preserved

**T9 remove tests:**
- Nonexistent file → no-op
- No squadron entry → no-op, file unchanged
- Only squadron entry → removes key entirely
- Squadron + third-party → preserves third-party
- Unrelated keys preserved
- Tidy cleanup when `hooks` becomes empty

This directly addresses the risk identified in the slice design: *"Settings.json merge correctness — getting the squadron-managed marker and the merge logic right is the highest-risk piece."*

---

### [PASS] Appropriate scoping: each task is independently completable

Tasks are scoped appropriately for a junior AI:
- T1: Register two config keys (well-defined, isolated change)
- T2: Move one class + one helper function, update one import
- T3: One pure function with clear precedence logic
- T4: One function with explicit exception list (no bare `Exception`)
- T5: Small command function assembling helpers
- T6: Three lines of wiring + import
- T7: Four small helper functions for file I/O
- T8: One function with well-specified merge algorithm
- T9: One function with well-specified filter algorithm
- T10: Add one option + two lines of wiring
- T11: Add one option + two lines of wiring

No task appears too large or too granular.

---

### [PASS] Error handling is explicitly justified

The slice design correctly identifies that the bare `except Exception` in T5 is the one justified case in the codebase. The task includes:
- A comment explaining why
- A tight scope (only wraps steps 1–3)
- Guarantees valid payload output + exit 0 regardless

This satisfies the project's "explicit exception handling" rule while acknowledging the hook's contract requires maximum robustness.

---

### [NOTE] Schema validation caveat is acknowledged

The slice design includes this note in multiple places:
> *"If the hook payload schema turns out to differ from `hookSpecificOutput.additionalContext`"*

T14 explicitly includes the remediation step:
> *"If the hook payload schema turns out to differ... open the corresponding test in T5 and the payload builder in the hook command, adjust both, re-run tests"*

This is appropriate acknowledgment of schema uncertainty for a new Claude Code integration. No action required.

---

### [NOTE] README vs authoring guide scope

The slice design states in **Technical Scope § Documentation**:
> *"README + the slice 152 authoring guide gain a short 'Interactive compaction' section"*

T12 only mentions the README:
> *"Add a short 'Interactive `/compact` for Claude Code' section to `README.md`"*

This is a minor scope discrepancy. The slice design intends to update both the README and the authoring guide, but the task only covers the README. **Recommendation**: Either add a line to T12 to also update the authoring guide, or confirm with the author that the authoring guide update is out of scope for this slice.

---

### [PASS] No scope creep detected

All tasks trace back to slice design requirements:

| Task | Design Requirement |
|------|-------------------|
| T1 | Config Keys section |
| T2 | Implementation Details: "lift into `squadron.pipeline.compact_render`" |
| T3 | Hidden Subcommand: `_resolve_instructions` |
| T4 | Param Sourcing section |
| T5 | Hidden Subcommand: `precompact_hook` function |
| T6 | Hidden Subcommand registration |
| T7 | Installer Changes: helpers |
| T8 | Installer Changes: `_write_precompact_hook` |
| T9 | Installer Changes: `_remove_precompact_hook` |
| T10 | Installer Changes: wire into `install_commands` |
| T11 | Installer Changes: wire into `uninstall_commands` |
| T12 | Documentation requirement |
| T13 | Standard slice closeout |
| T14 | Verification Walkthrough #6 |
| T15 | Standard slice closeout |

No tasks introduce functionality not described in the slice design.
