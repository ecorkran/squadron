---
docType: review
layer: project
reviewType: tasks
slice: pool-resolver-integration-and-cli
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/181-tasks.pool-resolver-integration-and-cli.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260413
dateUpdated: 20260413
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Task-to-success-criteria coverage is complete"
    location: All tasks
  - id: F002
    severity: concern
    category: design-accuracy
    summary: "Module layout in slice design does not match actual codebase"
    location: 181-slice.pool-resolver-integration-and-cli.md, Module Layout section
  - id: F003
    severity: concern
    category: task-scope
    summary: "Executor integration may be incomplete"
    location: Task 8, 181-slice pool-resolver-integration-and-cli.md:Executor Integration
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Task 2 decision point is appropriate"
    location: Task 2
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Test-after-implementation pattern is well followed"
    location: Tasks 3, 5, 7, 14
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Commits are appropriately distributed"
    location: All tasks
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Tasks are appropriately sized and independently completable"
    location: All tasks
  - id: F008
    severity: note
    category: uncategorized
    summary: "Task 16 final validation is comprehensive but assumes `--prompt-only` smoke check"
    location: Task 16
  - id: F009
    severity: note
    category: uncategorized
    summary: "Schema migration logic placement is ambiguous"
    location: Task 6, slice design
---

# Review: tasks — slice 181

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Task-to-success-criteria coverage is complete

All 9 success criteria from the slice design map to one or more tasks:
- SC1–3 (pool resolution): Tasks 1, 2, 4, 6, 8, 9
- SC4 (backward compatibility): Tasks 4, 15
- SC5–7 (CLI commands): Tasks 10–14
- SC8 (existing resolver tests): Task 5
- SC9 (schema migration): Tasks 6, 7

---

### [CONCERN] Module layout in slice design does not match actual codebase

The slice design references `src/squadron/pools/` with `backend.py` containing `PoolBackend` and `PoolSelection`. The Context Summary in the task file correctly identifies these don't exist as named classes—slice 180 shipped module-level functions instead. The design's module layout should be updated to reflect the actual path `src/squadron/pipeline/intelligence/pools/` and clarify that `PoolBackend` is defined in slice 181. This discrepancy could cause implementers to search for non-existent files.

---

### [CONCERN] Executor integration may be incomplete

The slice design explicitly states "When `execute_pipeline()` builds the `ModelResolver`, it now also instantiates a `PoolLoader` and passes the backend and callback" in `src/squadron/pipeline/executor.py`. However, Task 8 only modifies `src/squadron/cli/commands/run.py` and notes "per project feedback, resolver is actually built in `run.py`." 

Task 9 tests pool resolution via `execute_pipeline()`, which is called from run.py but defined in executor.py. If executor.py directly constructs a resolver (without going through run.py's wiring), the pool backend would not be passed. The task should either confirm that executor.py delegates resolver construction to run.py entirely, or add a fourth modification site in executor.py.

---

### [PASS] Task 2 decision point is appropriate

The "Decide and define" framing is reasonable because slice 180 may have shipped `PoolLoader.load()` as the factory, making a separate `PoolBackend` protocol optional. However, if the decision is (b) (wire to existing functions without a protocol), the design's expected interface won't exist. The default should lean toward (a) creating the protocol for forward compatibility with downstream slices.

---

### [PASS] Test-after-implementation pattern is well followed

All test tasks immediately follow their corresponding implementation tasks. Backend tests (3) follow protocol definition (2); resolver integration tests (5) follow resolver extension (4); state tests (7) follow state extension (6); CLI tests (14) follow all CLI implementations (10–13).

---

### [PASS] Commits are appropriately distributed

Four commits are spaced throughout: after PoolBackend/Selection (Task 3), after resolver integration (Task 5), after state schema bump (Task 7), and after CLI commands (Task 14). No commit is at the very end.

---

### [PASS] Tasks are appropriately sized and independently completable

Each task has clear scope, specific file targets, and success criteria that a junior AI could verify. No task is trivially mergeable nor requires splitting.

---

### [NOTE] Task 16 final validation is comprehensive but assumes `--prompt-only` smoke check

The manual smoke check step "`sq run <some-pipeline> --model pool:review --prompt-only`" assumes this flag exists. If the flag name differs in the actual CLI, this step will fail. Consider verifying the actual flag name or making the smoke check more flexible.

---

### [NOTE] Schema migration logic placement is ambiguous

The slice design says "`StateManager.load()` must already handle forward-only migration" but Task 6 specifies "In `_load_raw`, allow `schema_version in {3, 4}`". The `_load_raw` method is called by `load()`, so functionally they may be the same place. This is not a gap, but the naming in the task could more precisely reference where the version check lives.
