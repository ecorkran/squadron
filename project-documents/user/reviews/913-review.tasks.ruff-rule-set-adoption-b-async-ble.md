---
docType: review
layer: project
reviewType: tasks
slice: ruff-rule-set-adoption-b-async-ble
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260816
dateUpdated: 20260816
reviewedSha: 71745244ebacb83d19119a7d5f1dd16085d9814c
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Comprehensive success criteria coverage"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Sequencing respects dependencies"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Test-immediately-after-implementation pattern respected"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Commit checkpoints distributed across parts"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Verification anchors are pre-measured and cited"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "`per-file-ignores` ignore-scope verification is explicit"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md:Task 1.2"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "Part C narrowings without explicit per-site test review may miss regressions"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md:Task 3.4"
  - id: F008
    severity: concern
    category: scope-clarity
    summary: "Task 3.2 may be too large for a junior AI to scope-check"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md:Task 3.2"
  - id: F009
    severity: concern
    category: scope-creep
    summary: "Scope creep: `extend-exclude` is repeatedly mentioned but never installed"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md"
  - id: F010
    severity: concern
    category: verification-depth
    summary: "Task 4.1's \"revert and confirm clean `git status`\" understates the verification"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md:Task 4.1"
  - id: F011
    severity: concern
    category: task-granularity
    summary: "Possible size mismatch between Part A's \"3 stragglers\" and Part B's `ASYNC` total"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md:Tasks 1.3, 1.4"
  - id: F012
    severity: note
    category: commit-granularity
    summary: "Final commit boundary for Task 3.7 spans large prior work"
    location: "project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md:Task 3.7"
  - id: F013
    severity: note
    category: uncategorized
    summary: "No NFR-driven load test is present or required"
    location: "unverified"
---

# Review: tasks — slice 913

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Comprehensive success criteria coverage

All 10 success criteria from the slice design map cleanly onto tasks: the `select` list exact value (Task 3.7), zero-exit ruff (Task 3.7 / 4.1), full gate commands (Tasks 1.5/2.5/3.7), suppression inventory (Task 4.2), no `extend-exclude` (Tasks 3.1/4.2), no blanket `BLE`/`ASYNC` ignores (Tasks 2.3/3.5/4.2), every retained broad catch justified with `logger.exception` (Task 3.6), D6-deferred sites referencing filed issues (Task 3.6), stale comment removal (Task 3.7), and `client/http.py:42` off the event loop (Task 2.1). No criteria appear orphaned.

### [PASS] Sequencing respects dependencies

Tasks follow the A → B → C progression cleanly: the `per-file-ignores` block from 1.1 is reused by 3.1; `B904` fixes in 1.3 must precede the `B` enable in 1.5 (D7); the `select` addition is last in each part; the `extend-exclude`-is-absent check in 3.1 runs before the final enable in 3.7. No circular dependencies.

### [PASS] Test-immediately-after-implementation pattern respected

Task 2.1 (socket-existence fix) is followed by Task 2.2 (`tests/client` verification). Task 3.2 (resolve the two flagged sites) is followed by Task 3.3 (test those sites). Where tests already cover the behavior (Part A `B904` sites), the gate command in 1.5 implicitly relies on the existing 3016-test baseline per the migration plan.

### [PASS] Commit checkpoints distributed across parts

Each part ends with an explicit enable-and-commit task (1.5, 2.5, 3.7), satisfying D7's "no part leaves the build red, and `git bisect` stays meaningful." The acceptance gate (Task 4.1) is appropriately separated as a whole-slice confirmation rather than a Part C tail item.

### [PASS] Verification anchors are pre-measured and cited

The "Verified counts" and "Verified code anchors" tables at the top bind the abstract counts in the slice design (which the design itself flags as drifted) to current line numbers. A junior AI can locate every site without re-probing the codebase.

### [PASS] `per-file-ignores` ignore-scope verification is explicit

Task 1.2's probe-function test for `B006` directly implements the slice design's verification walkthrough ("Prove the ignore did not disable `B` for the CLI"). This is the kind of guard that is easy to omit and would silently let a misconfigured ignore ship; well caught here.

### [CONCERN] Part C narrowings without explicit per-site test review may miss regressions

The slice design's migration plan requires that each narrowing answer "what now escapes that did not before, and where does it land?" and identifies Part C as "the only place regressions can hide." Task 3.3 adds tests for the two flagged sites, but Task 3.4 (the remaining 9 `pipeline/` sites) and Task 3.5 (CLI/provider/client/core/events sites, another 9 sites) explicitly rely on "the existing suite." For a slice whose contract is "what now escapes must land somewhere," relying on suite-as-catcher is acceptable for narrowings that route through well-tested boundaries, but the task itself contains no verification step (e.g., a per-site audit of "what existing test covers this catch's failure path?" or a run-with-traceback check during the part gate). Consider adding a short sub-step in 3.4/3.5, or at minimum in 3.7's gate, requiring review of `--tb=long` output for the touched modules before commit.

### [CONCERN] Task 3.2 may be too large for a junior AI to scope-check

The two sites here are precisely the ones the slice design flags as needing "a real answer, not a `noqa`" — i.e., genuine bug-fix tasks with open-ended scope. The task correctly applies D6's scope guard ("if either turns out to be a larger fix, file an issue and leave a `# noqa: BLE001`"), and the success criterion is appropriately outcome-based. However, "determine what `resolve` actually raises for an unknown alias and decide whether that should propagate" requires reading `resolver.py` and tracing its failure modes — non-trivial exploration that could absorb significantly more than 2/5 effort if the resolver turns out to have a wide raisable set. A junior AI may not know when to apply the scope guard. Suggest adding an explicit early-exit signal: e.g., "If reading `resolver.py` shows it can raise more than 2 distinct exception types, stop and file an issue per D6." This makes the guard's trigger concrete rather than judgmental.

### [CONCERN] Scope creep: `extend-exclude` is repeatedly mentioned but never installed

Tasks 3.1 ("Do **not** use `extend-exclude` for the tree") and 4.2 ("`grep -n 'extend-exclude' pyproject.toml` → no match") and the success criteria all restate the negative. This is fine as a guard, but the slice design's Technical Decisions section header (D3) and the In-Scope/Out-of-Scope block both list `extend-exclude` config as "in scope" — the breakdown's actual work plan never adds one. The outcome is correct (use `per-file-ignores`, not `extend-exclude`), and the slicing design's framing of `extend-exclude` as in-scope is for the purpose of recording the rejection. No action needed; flagging only because a reviewer scanning for scope items might miscount.

### [CONCERN] Task 4.1's "revert and confirm clean `git status`" understates the verification

The slice design's verification walkthrough frames this as "the real acceptance test for this slice: the failure mode that produced #49 is now caught by CI rather than by review." The task's success criterion ("the failure mode that produced #49 is now caught mechanically") is correct in substance, but the implementation as written adds `try: pass / except Exception: pass` — a minimal trigger that fires `BLE001` only if `BLE` is selected. It does not exercise the interaction with `B904` chaining, with the `--fix` availability flagged in the slice plan, or with any other rule whose absence would let a similar real-world shape through. For an acceptance test, consider adding one more probe variant (e.g., one that triggers `B904` only, or one that triggers `BLE001` on an `async def` path, since those are the two rule sets whose combine-failure was the motivating concern). This is low-stakes (the rest of the slice already gates on those) but would make the acceptance test genuinely cover the slice's stated contract rather than just its last task.

### [CONCERN] Possible size mismatch between Part A's "3 stragglers" and Part B's `ASYNC` total

Task 1.3 touches 54 sites in 13 files, and Task 1.4 touches 3 sites in 3 files. The breakdown is reasonable for diff-reviewability, but 1.3 spans 13 files which is a non-trivial review surface. A junior AI may stop mid-file at the "largest first" ordering and create N commits rather than one Part A commit, violating D7's "enable `B` in the same commit that zeroes it." Consider adding a sub-bullet under 1.3: "Commit only at the end of 1.5; intermediate `git add`s are fine but do not commit until Task 1.5." This makes the single-commit contract explicit.

### [NOTE] Final commit boundary for Task 3.7 spans large prior work

Tasks 3.1–3.6 collectively make the largest single commit of the slice (the entire Part C). D7 requires "each part enabled in the same commit that zeroes it," but Part C also includes legitimate-behavior changes, two new tests, and the exemption guard — i.e., it bundles feature work and policy enforcement. This is consistent with D7 as written and matches how the slice design describes the boundary, but a reviewer might prefer finer commits for bisect within Part C. Flagging as informational, not as a defect.

### [NOTE] No NFR-driven load test is present or required

The slice design does not restate any NFR that would require a `tests/load/` task; the work is lint/conformance, not performance or capacity. The "load-bearing" phrasing in Task 4.1 refers to CI enforcement, not load testing. No action needed.
