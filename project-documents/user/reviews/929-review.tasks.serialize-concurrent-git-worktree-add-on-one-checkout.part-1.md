---
docType: review
layer: project
reviewType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-1.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 3849f8676b4f7655171279ab9804afe5b353a85b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`_OverlapTrackingRunner` dispatch logic compares a list slice to a tuple literal — every branch fails to match"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-1.md:101-131"
  - id: F002
    severity: concern
    category: scoping
    summary: "Task C.3 bundles seven distinct unit tests under one checklist item at Effort 3/5"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-1.md:235-287"
  - id: F003
    severity: pass
    category: coverage
    summary: "Success criteria map cleanly onto tasks across both files, no scope creep found"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-1.md"
  - id: F004
    severity: pass
    category: process
    summary: "Load test and CI gating both present and explicit"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-2.md:269-358"
  - id: F005
    severity: note
    category: documentation
    summary: "Task file transparently resolves a naming inconsistency in the slice design itself"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:72,111"
---

# Review: tasks — slice 929

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] `_OverlapTrackingRunner` dispatch logic compares a list slice to a tuple literal — every branch fails to match

Task B.1 specifies dispatch via `argv[:2] == ("git", "worktree")`, `argv[:1] == ("ps",)`, and `argv[:2] == ("git", "submodule")`. Every real caller passes `argv` as a `list[str]` — confirmed at `src/squadron/codehost/worktree.py:333` (`["git", "worktree", "add", ...]`), `:365` (`["git", "submodule", "update", ...]`), and `:128` (`["ps", "-o", "lstart=", ...]`) — and `ProcessRunner.run`'s own `argv` parameter is typed `Sequence[str]` (`src/squadron/core/process_runner.py:78`). A slice of a list is a list; `["git", "worktree"] == ("git", "worktree")` is `False` in Python regardless of element equality. As written, none of the three dispatch branches ever matches, so every call falls through to "anything else: raise" and `_OverlapTrackingRunner` cannot function at all.

The existing `FakeProcessRunner` in the same test suite (`tests/codehost/fake_runner.py:57`, `argv_tuple = tuple(argv)`) already establishes the correct idiom in this codebase — Task B.1 doesn't carry it over. Worse, this isn't a silent failure: it's a loud `UnscriptedCallError`, and Task B.2's own success criterion is "confirm it fails against today's code (no lock exists yet)." A test that fails with `UnscriptedCallError` instead of an overlap-count assertion failure satisfies that literal instruction for the wrong reason — the "proof" test (D6's whole point: prove the race is gone, not just rare) would never actually exercise the overlap-counting logic, and a less careful implementer could check the box without noticing the test never ran real overlap detection.

Task D.6 (`929-tasks...-2.md:162-165`) explicitly extends Task B.1's runner for the submodule-barrier test, so the same defect propagates there too.

Fix: convert `argv` to a tuple once at the top of `.run(...)` (mirroring `fake_runner.py`) before any slice comparison, or compare against list literals instead of tuples.

### [CONCERN] Task C.3 bundles seven distinct unit tests under one checklist item at Effort 3/5

Seven tests (`test_lock_is_acquired_and_released_for_reuse` through `test_lock_release_failure_does_not_mask_a_body_exception`), each requiring a different setup technique (real cross-process `flock`, `os.chmod`, three separate `monkeypatch.setattr(fcntl, "flock", ...)` variants distinguishing acquire vs. release, and a `sys.modules` import-failure trick) are checked off as a single task item. Compare to Part D's task granularity in the companion file, where individual call sites each get their own task (D.1/D.2/D.3) even though they're mechanically similar. This one is disproportionately dense for its effort rating and would benefit from a split (e.g., "acquire/release + timeout" vs. "D7 error-mapping tests" vs. "release-failure pair") so a junior AI's progress and any failure is localized to a smaller unit of work. Not blocking — each sub-bullet is unambiguous — but worth flagging per the granularity criterion.

### [PASS] Success criteria map cleanly onto tasks across both files, no scope creep found

Every Functional/Technical/Integration Requirement and Verification Walkthrough step in the slice design traces to a specific task: no-overlap guarantee → B.2/D.1-D.3/D.5; per-call-site timeout behavior → D.1-D.4; holder-death → C.4; read-only-root immediate failure → C.3; submodule exclusion → D.6; `review_pr.py` panel rendering → D.7/D.8; existing suite passes unchanged → D.9. Nothing in either task file traces to no success criterion. Verified line-number references in the task text against the actual source (`worktree.py:251-267,332-350,398-403`; `review_pr.py:32,355,425-429`) — all accurate.

### [PASS] Load test and CI gating both present and explicit

Task E.1 extends the existing `tests/load/test_worktree_concurrency.py` acceptance test into `ROUNDS` repetitions tied to a measured baseline (Task A.1), and Task G.1 is a dedicated task that reads `.github/workflows/ci.yml` to confirm the `test` job actually collects `tests/load/` unfiltered, with an explicit instruction to fix and commit the workflow file if it doesn't. CI gating is not left implicit.

### [NOTE] Task file transparently resolves a naming inconsistency in the slice design itself

The slice design's Architecture table names the poll-interval constant `_POLL_SECONDS` while D3's prose calls it `_METADATA_LOCK_POLL_SECONDS`. The task file's Context Summary calls this out explicitly and picks one name with a stated rationale, rather than silently guessing (a hallucination trap this project's CLAUDE.md specifically warns about). Good practice, no action needed.

### Run Digest

- Response length: 5378 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
