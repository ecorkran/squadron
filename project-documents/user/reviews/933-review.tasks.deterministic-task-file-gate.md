---
docType: review
layer: project
reviewType: tasks
slice: deterministic-task-file-gate
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261011
dateUpdated: 20261011
reviewedSha: 44249cc543781dbf4c68cb248d6a89774490a1a1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 27.5
squadronVersion: 0.21.3
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are traced to tasks"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and checkpoints"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md"
  - id: F003
    severity: concern
    category: design-consistency
    summary: "Task 7 may put file I/O in the module the design and Task 3 call pure"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md:132"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 5 leaves `input_files` population ambiguous"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md:115"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Pattern rules R2 and R3 have thin test coverage"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md:96-104"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "No test that non-tasks templates are not gated"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md:163-175"
  - id: F007
    severity: note
    category: coverage
    summary: "Slash-command parity has no explicit verification"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:91"
  - id: F008
    severity: note
    category: sizing
    summary: "Task granularity is acceptable"
    location: "project-documents/user/tasks/933-tasks.deterministic-task-file-gate.md"
---

# Review: tasks — slice 933

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are traced to tasks

Each functional and technical criterion in the slice design has a task:
- **Scanner and pattern table:** Tasks 3 and 4.
- **FAIL result fields, including the artifact read-back with `aiModel`, `verdictSource` and no `toolsGiven`/`toolCallsMade`:** Tasks 5 and 6.
- **Failure mode (`OSError`/`UnicodeDecodeError` with the path):** Task 7.
- **CLI hook and the no-model-call assertions:** Tasks 8 and 9.
- **Pipeline hook, plus CLI/pipeline parity:** Tasks 10 and 11.
- **Fixtures vendored under `tests/review/fixtures/task_gate/`:** Task 2, covering the fixed list P1–P6 plus negatives.
- **Verification Walkthrough steps 1–3 and ruff/pyright:** Task 12 and the per-task gates.

All nine negatives from the design's "Not flagged" list are covered by one parametrized test. No task is scope creep. The Task 7 shared helper serves the design's interface-parity requirement.

### [PASS] Sequencing and checkpoints

Dependencies run in order: branch, fixtures, scanner, scanner tests, builder, builder tests, helper, CLI hook, CLI tests, pipeline hook, pipeline tests, validation. There are no cycles. Each implementation task is immediately followed by its test task, and the commit sits on the test task. Commits are spread across Tasks 4, 6, 7, 9, 11 and 12, not batched at the end. No load-test or CI task is needed because the slice states no NFR.

### [CONCERN] Task 7 may put file I/O in the module the design and Task 3 call pure

The design's Component Structure says `task_gate.py` holds pure functions with no I/O. Task 3's success criterion says "module has no file or network I/O". Task 7 then adds `gate_task_files`, which reads files, and allows it to go "in `task_gate.py`, or a small sibling". A junior could put the reads in `task_gate.py` and break the Task 3 invariant. It also departs from the design's "reads happen inline in the callers" wording. Specify the sibling module name and path (for example `task_gate_io.py`) so the pure module stays pure. Or amend the design to record the helper as a deliberate change.

### [CONCERN] Task 5 leaves `input_files` population ambiguous

Task 5 says the callers set the `against` and `cwd` entries, but then says "accept them as parameters if `ReviewResult` needs them at build time". The design fixes the signature as `merge_gate_results(scans)`. Task 7's `gate_task_files(paths)` has no way to pass `against` or `cwd`. Tasks 8 and 10 never say that callers fill those fields in afterwards. Decide this once, either by checking what `ReviewResult` requires or by stating the caller-side enrichment step in Tasks 8 and 10. As written, the junior implementer has to guess.

### [CONCERN] Pattern rules R2 and R3 have thin test coverage

Task 4's tests depend on the vendored fixtures and the design's negatives. The R1 and R4 hits are exercised by P1, P2 and P6. Nothing explicitly covers the `MERGE_OBJECT_WINDOW` boundary: a git object 4 words after the merge word should be flagged, and one 5 words after should not. R2 variants such as `merge and release` and `merge, tag` are covered only if P3 and P4 happen to hit them. Add a small parametrized positive/boundary test per rule. This would also guard the "adjust the pattern table" loop in Task 4 against over-fitting to the six fixtures.

### [CONCERN] No test that non-tasks templates are not gated

Task 10 gates the pipeline only when the template is tasks, and the design states this explicitly. Task 11 tests offending and clean tasks files, but no test shows that a non-tasks template (for example a slice or code review) skips the gate. The CLI's other review commands are likewise untested for isolation. A single negative test would guard against the gate leaking into other reviews.

### [NOTE] Slash-command parity has no explicit verification

The design's functional requirements list the slash command as a parity surface. The command shells out to the CLI, so Tasks 8 and 9 cover it indirectly. Task 12's manual walkthrough could name it, but this is optional.

### [NOTE] Task granularity is acceptable

Task 3 bundles the dataclass, the pattern table, four rules, boundary handling and the scanner. It is the densest task but cohesive for effort 2/5, and splitting it would be too granular. Tasks 8 and 10 each include a helper extraction ("extract a helper if needed"). That is acceptable as long as the existing tests keep passing, which their success criteria require.

### Run Digest

- Response length: 5326 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 27.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
