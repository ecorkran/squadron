---
docType: review
layer: project
reviewType: tasks
slice: analysis-pack-bundled
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260625
dateUpdated: 20260626
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Dispatcher routing verification gap"
    location: unverified
    resolution: "T6 updated: added sq install-commands verification step, file presence check, and explicit manual Claude Code routing check with recorded result requirement."
  - id: F002
    severity: pass
    category: requirements-coverage
    summary: "Success criteria coverage"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F003
    severity: pass
    category: task-dependencies
    summary: "Task sequencing"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F004
    severity: pass
    category: test-coverage
    summary: "Test-with pattern"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F005
    severity: pass
    category: commit-hygiene
    summary: "Commit checkpoint distribution"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F006
    severity: pass
    category: backward-compatibility
    summary: "Backward compatibility verification"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F007
    severity: pass
    category: requirements-coverage
    summary: "No load test requirement applicable"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F008
    severity: pass
    category: scope-management
    summary: "No scope creep detected"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
  - id: F009
    severity: pass
    category: task-sizing
    summary: "No tasks too large or too granular"
    location: project-documents/user/tasks/342-tasks.analysis-pack-bundled.md
---

# Review: tasks — slice 342

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Dispatcher routing verification gap

The slice design Success Criterion 2 states: "`commands/sq/analysis.md` exists and, when invoked as `/sq:analysis tech-debt`, routes to the tech-debt-analyze skill."

The verification walkthrough explicitly expects:
```bash
sq install-commands    # installs commands/sq/analysis.md alongside other sq commands
# then in Claude Code:
# /sq:analysis tech-debt
# → routes to tech-debt-analyze skill
```

Task T6 creates the dispatcher file and checks it follows the dispatch pattern, but none of the tasks actually verify the routing works by running `sq install-commands` and then invoking the dispatcher with `/sq:analysis tech-debt`. T8 and T11 smoke test `sq skills list`, not the dispatcher routing path. This is a meaningful verification gap since the dispatcher's routing behavior is the core functionality being added.

**Resolution (20260626):** T6 updated to include: `sq install-commands` run with output verification, file presence check at `~/.claude/commands/sq/analysis.md`, and an explicit manual Claude Code routing check step with a recorded result requirement.

### [PASS] Success criteria coverage

All 9 success criteria (1-9) from the slice design have corresponding tasks:
- SC1 (tech-debt-analyze.md exists): T5, T2, T11
- SC2 (dispatcher routes correctly): T6 (see gap above)
- SC3 (sq skills list shows analysis): T3, T8, T4
- SC4 (install without network): T9, T10
- SC5 (installed file exists and invocable): T9, T5, T11
- SC6 (idempotent reinstall): T9, T10
- SC7 (skills.toml loadable via importlib.resources): T2, T11
- SC8 (load_effective includes shipped default, tests green): T3, T4, T11
- SC9 (pyright strict and ruff lint/format): T7, T11

### [PASS] Task sequencing

Task sequencing is correct:
- T1 (branch/prereqs) → all subsequent tasks
- T2 (data package) → T3 (manifest extension depends on package existing)
- T3 (manifest logic) → T4 (tests follow implementation)
- T5 (skill file) → T6 (dispatcher depends on skill file for routing knowledge)
- T9 (CLI smoke) → T10 (integration test follows smoke test)
- No circular dependencies detected

### [PASS] Test-with pattern

Tests immediately follow their implementation tasks:
- T3 (load_effective extension) → T4 (tests for load_effective)
- T9 (CLI smoke test) → T10 (integration test)

### [PASS] Commit checkpoint distribution

Commit checkpoints are distributed throughout, not batched at end:
- T7: Commit after core implementation (data package + manifest extension)
- T12: Commit final and status update

This allows for meaningful rollback points.

### [PASS] Backward compatibility verification

T4 explicitly tests that "existing tests remain green" and includes "user manifest with a different `analysis` entry overrides the shipped default for that pack; other shipped packs are still present" — this confirms the backward compatibility requirement from Success Criterion 8.

### [PASS] No load test requirement applicable

The slice design does not restate any NFR requiring load testing. No `tests/load/` task is needed or expected.

### [PASS] No scope creep detected

All tasks trace to the slice design scope:
- Data package creation (T2) — supports shipped default manifest requirement
- Manifest extension (T3) — explicitly stated in Technical Decisions
- Skill file and dispatcher (T5, T6) — core functionality
- Tests and validation (T4, T8, T9, T10, T11) — verification of functional requirements
- No tasks address out-of-scope items (sq doctor, sq uninstall, additional skills beyond tech-debt-analyze)

### [PASS] No tasks too large or too granular

Tasks are appropriately sized. Each task has a single clear focus with specific success criteria that a junior AI could verify. No task attempts to do too much (largest is T11 with validation checks, but these are standard pre-commit checks that belong together).
