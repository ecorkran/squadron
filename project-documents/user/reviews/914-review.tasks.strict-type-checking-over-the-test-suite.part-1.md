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
sourceDocument: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-1.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 71bd75d55c483b99321610b7e16a1e4e8991e28f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "All 11 success criteria trace to tasks across the three files"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md:381-402"
  - id: F002
    severity: pass
    category: ci-gating
    summary: "CI wiring is explicitly confirmed, not left implicit"
    location: ".github/workflows/ci.yml:36"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Commit checkpoints are distributed, not end-batched"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-1.md:303-332"
  - id: F004
    severity: concern
    category: coverage
    summary: "D8 hidden-error workload is never converted into per-file task assignments"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-1.md:156-170"
  - id: F005
    severity: concern
    category: coverage
    summary: "Task 1.5's grep misses the `_invoke` population the design says Helper 1 resolves"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-1.md:179-194"
  - id: F006
    severity: note
    category: accuracy
    summary: "Task 1.5's stated site count is already stale against the tree"
    location: "tests/cli/commands/test_dispatch_run.py:17"
  - id: F007
    severity: note
    category: sequencing
    summary: "File 2's standing rule misnumbers the gate tasks it defers commits to"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:54"
  - id: F008
    severity: note
    category: sequencing
    summary: "Minor wording inconsistency around the temporary widening's lifetime"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-1.md:318"
  - id: F009
    severity: note
    category: accuracy
    summary: "Small count inconsistencies in the per-file tables"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-3.md:218"
  - id: F010
    severity: note
    category: granularity
    summary: "The two global passes are the largest single tasks; acceptable as scoped"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-1.md:257-276"
---

# Review: tasks — slice 914

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] All 11 success criteria trace to tasks across the three files

SC1 → Task 1.14 (0 errors with widened include, seeded exclude) and the part gates; SC2 → Task 5.9 plus walkthrough step 1 in Task 6.1; SC3 → D1 standing rules plus Task 6.2's `executionEnvironments` grep; SC4 → Task 6.1's config eyeball check; SC5 → Task 1.14; SC6 → Task 1.4's recorded floor enforced at 1.7/1.11/2.11/3.10/4.8/5.9; SC7 → the same gates; SC8 → Task 6.2's suppression audit; SC9 → Tasks 1.8–1.10 plus the kept-private table in 6.3; SC10 → the D6 standing rule in file 2 plus 6.3's "record zero if zero" instruction; SC11 → Task 6.3. The walkthrough's acceptance probe (plant a type error, confirm `reportReturnType` fires) is explicitly scheduled in Task 6.1. Per-file tasks embed their own module pytest runs in their success criteria, so the test-after-implementation pattern holds without separate test tasks — correct here, since the design puts "adding new tests" out of scope.

### [PASS] CI wiring is explicitly confirmed, not left implicit

The design's Migration Plan requires confirming that CI picks up the config change with no edit, and Task 1.1 operationalizes that with a stop-and-report condition instead of an edit. I verified the claim is accurate: `.github/workflows/ci.yml:36` runs `uv run pyright` with no path argument, so the `include` widening propagates automatically. No load-test requirement exists in this slice (no NFR is restated), so no `tests/load/` task or CI load-gate is owed.

### [PASS] Commit checkpoints are distributed, not end-batched

Six commit tasks spread across the slice: Task 1.12 (D3+D5 fixes, config still `["src"]`) and Task 1.14 (D2's first commit with `include`+`exclude` landing together), then one gate-and-commit task per part (2.11, 3.10, 4.8, 5.9). This matches D2's "pyright passes at every commit" discipline, and Task 1.12's constraint that the temporary widening stay out of the first commit is consistent with 1.14 landing it. Task dependencies are acyclic and the Part B–E ordering respects the exclude-shrink mechanism (including conftest-first handling in Task 4.5 and re-measure-before-fixing in the catch-all tasks 3.9/4.7/5.8).

### [CONCERN] D8 hidden-error workload is never converted into per-file task assignments

The design (D8) says Part A's re-measurement "counts the hidden errors **per file** … so each part's workload is known." Task 1.3 captures only aggregate numbers (`summary.errorCount` delta and two `grep | wc -l` counts) — no per-file hidden-error list. Every downstream enumeration then keys on *visible* errors: Task 1.13's `exclude` seed is the per-file visible-error list, and the catch-all tasks (3.9, 4.7, 5.2, 5.8) all instruct "re-derive the exact current list from a fresh `uv run pyright --outputjson` filtered to `<scope>`". A test file whose errors are entirely suppressed by `# type: ignore` comments — plausible given 262 comments across 67 files (e.g. `tests/cli/test_history.py:14,18` carries two) — produces no visible errors, so it lands in no exclude list, no named per-file task, and no catch-all sweep. Its D8 disposition then has no home until Task 6.2 fails at the very end of file 3, surfacing unplanned remediation mid-verification. The extent is unverified (I cannot run pyright here), but the structural gap is verifiable from the documents. Fix: have Task 1.3 record the per-file hidden-error list the design already asks for, and make the per-part file assignments (or the catch-alls' re-derivation) draw from visible errors ∪ Task 1.3's type-ignore file list.

### [CONCERN] Task 1.5's grep misses the `_invoke` population the design says Helper 1 resolves

The design's D8 states "the `[no-untyped-def]` sites on `_invoke` helpers go away with D5's Helper 1" — i.e. Helper 1 is meant to annotate the untyped `_invoke` wrappers too, deleting those ignores. Task 1.5's detection pattern (`grep -rn "def _invoke.*-> object" tests/`) and success criterion ("the grep returns nothing") only cover the `-> object` erasure variant, not the untyped variant. I verified the untyped shape exists in the tree: `tests/cli/test_history.py:14`, and the same pattern in `tests/cli/test_list.py:14`, `test_message.py:14`, `test_models.py:15`, `test_pools_command.py:14` — several of the ~12 `_invoke` modules the design counted. A junior executing Task 1.5 exactly as written satisfies its success criterion while the design's expected bulk resolution never materializes in Part A; the work then silently shifts into Parts C/D via the per-file D8 rule (which only fires for files that happen to be touched — same blind spot as the previous finding). Fix: broaden the grep to `def _invoke` and require every found helper to carry `-> click.testing.Result` with the ignore comment deleted.

### [NOTE] Task 1.5's stated site count is already stale against the tree

The task claims "As of 20260927 this is one site, `tests/cli/commands/test_summary_run.py:14`", but the grep it prescribes returns two sites — `test_dispatch_run.py:17` also declares `def _invoke(*args: str) -> object:`. Harmless because the task explicitly orders a fresh grep rather than trusting the count, but the "verified via `inspect.signature`" framing overstates the measurement's freshness.

### [NOTE] File 2's standing rule misnumbers the gate tasks it defers commits to

The standing rule says "do **not** commit until this file's gate tasks (2.11, 3.9 in file 3's numbering…)", but 3.9 is a straggler-fixing task, Part C's gate is 3.10 in this same file, and Part D's gate is 4.8 in file 3. The trailing "see each Part's own gate task" hedge resolves the ambiguity, so a literal reading wastes effort at worst rather than breaking anything — still worth correcting to avoid a junior holding commits past the real gate.

### [NOTE] Minor wording inconsistency around the temporary widening's lifetime

Task 1.13 says "Temporarily widen `include` **again** (not committed)", but Task 1.2 (lines 151–152) instructs not reverting it and nothing between 1.12 and 1.13 removes it — the widening should still be in place, so "again" implies a revert that never happens. The instruction is idempotent so the practical risk is a moment of confusion, not a wrong state. The underlying design trade-off (a multi-task uncommitted `pyproject.toml` edit, inherent to D2's first-commit requirement) is handled as well as the design allows.

### [NOTE] Small count inconsistencies in the per-file tables

Task 5.8 says "37 errors across 11 files" but its own enumeration lists 12 files (the error sum of 37 checks out). Similar spot-checks elsewhere pass — the Part E table's 265 errors/54 files sums correctly. Each catch-all task orders re-derivation from a fresh pyright run, so these stale tallies are cosmetic, but they erode trust in figures the executor is told not to trust.

### [NOTE] The two global passes are the largest single tasks; acceptable as scoped

Task 1.9 (effort 4/5, ~80 promote-list symbols touching 922 lines including 261 in `src`) and Task 1.6 (120 lambda sites across 21 files) are chunky, but each has a crisp mechanical success criterion (0 `reportPrivateUsage` / 0 `reportUnknownLambdaType` from a pyright run), prescribes internal batching with per-batch verification, and resists splitting because D3/D5 deliberately globalize the work before any per-directory part. Splitting them would trade real gating value for task count. Worth watching during execution; no change requested.

### Run Digest

- Response length: 9323 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 52283
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
