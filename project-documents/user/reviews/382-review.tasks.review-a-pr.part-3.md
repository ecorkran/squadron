---
docType: review
layer: project
reviewType: tasks
slice: review-a-pr
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/382-tasks.review-a-pr-3.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: 78ccf3bbd63bc132645e568041235162c4600f33
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Rules-directory provenance for the two-root split is unspecified and untested"
    location: "src/squadron/cli/commands/review.py:237-248"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "No load-test task for the worktree lifecycle's concurrency/network paths"
    location: "tests/load"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Happy-path submodule-init criterion still has no test or live-walkthrough coverage"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-3.md:242"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Part G batches four implementation tasks before its first test"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-3.md:71-170"
  - id: F005
    severity: note
    category: consistency
    summary: "`pr.py` anchor is one line short of the sequence it describes"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-3.md:83"
  - id: F006
    severity: note
    category: completeness
    summary: "G.2 defers a real implementation choice to the implementer"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-3.md:117-123"
  - id: F007
    severity: note
    category: completeness
    summary: "Closeout still has no explicit commit step"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-3.md:255-269"
  - id: F008
    severity: pass
    category: completeness
    summary: "Parts F/G/H trace cleanly to D6, D2/D5, and closeout; no scope creep"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-3.md:273-280"
  - id: F009
    severity: pass
    category: correctness
    summary: "Code anchors verified accurate against live source"
    location: "src/squadron/cli/commands/review.py:286,538-678,985-1015"
---

# Review: tasks — slice 382

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Rules-directory provenance for the two-root split is unspecified and untested

The design's D1 prose names both "the rules directory and `CLAUDE.md`" as the things `convention_root` must source from the checkout, and the Functional success criteria state: "A PR that edits the rules directory or `CLAUDE.md` is reviewed against the checkout's versions." Yet every task that implements or tests this split (file 1's A.1–A.3, file 3's G.6) touches only `CLAUDE.md` via `_inject_file_contents`. No task in Part G tells the implementer which `cwd` feeds `resolve_rules_dir`/`--rules-dir` for `sq review pr` (the existing shared helper `_resolve_review_cwd` at review.py:237-248 resolves both the checkout path and the rules directory from the same argument — today's single-root assumption). Nothing in G.1–G.4 says "resolve rules_dir from the operator-supplied `--cwd`/checkout, before the worktree exists," and no test in G.5/G.6 asserts rules content comes from the checkout when a worktree carries a different `.claude/rules/`. If an implementer wires rules resolution off `inputs["cwd"]` after G.2 overrides it to the worktree, a malicious PR could plant adversarial rules content that reaches the reviewer's instructions — the same class of risk D8 closes for SDK project settings — and no test in this breakdown would catch it either way.

### [CONCERN] No load-test task for the worktree lifecycle's concurrency/network paths

Project rule (python.md, "Load-test tier") requires at least one load test in `tests/load/` for "any code on the simulation, network, concurrency, or environment-layer paths," asserting latency/throughput/resource bounds, not just functional correctness. The scratch-worktree lifecycle (Part C, file 1) is squarely concurrency (lock/orphan-sweep races) and network (bounded submodule fetch) code, precedented by `tests/load/test_grep_timeout.py` already in the repo. Task C.6's suite exercises only `FakeProcessRunner`-based functional correctness. No task anywhere across the three files adds a `tests/load/` case for concurrent worktree creation or submodule-timeout behavior under a realistic configuration, and file 3's closeout (H.2's "success criteria sweep") does not surface the gap. CI already runs the whole `tests/` tree unconditionally (`.github/workflows/ci.yml` → `uv run pytest`, `testpaths = ["tests"]`), so no separate CI-wiring task would be needed once such a test exists — but the test itself is missing.

### [CONCERN] Happy-path submodule-init criterion still has no test or live-walkthrough coverage

The design's functional criteria require "A repository with submodules yields a worktree in which submodule paths exist" (the positive case), distinct from the two failure modes. This was already flagged (F001, CONCERN) against file 1's Task C.6, which tests only the unfetchable and timeout failure paths. File 3 doesn't add it either: H.1's live walkthrough enumerates six steps (before/after state, tools/no-tools, leak check, orphan sweep, containment, settings isolation) and submodules are not among them, and H.2's "success criteria sweep" — the task whose job is to name evidence for every criterion — has no test or live step to point to for this one. The gap is real and travels all the way to closeout unaddressed.

### [CONCERN] Part G batches four implementation tasks before its first test

G.1–G.4 (effort 3+4+2+3 = 12) land the target resolution, the tools/no-tools worktree branch, the diff/scope/`--files` wiring, and full flag-parity registration before G.5 (the first test task) runs. This is the same pattern the part-1 review already flagged for this Part (it cited the finding at a file-1 location, but the actual G tasks live here in file 3). Parts A, D, E, and F in this breakdown all interleave test-with-implementation at a finer grain; Part G is the outlier, and it's the part assembling the most security-relevant wiring (worktree jail, convention_root, setting_sources_override all converge here).

### [NOTE] `pr.py` anchor is one line short of the sequence it describes

Task G.1 cites `pr.py:34-56` for "the exact sequence `pr.py`'s `show` command already establishes," but the sequence named in the same bullet (`parse_target → list_remotes → select_remote → host.resolve_pull_request → host.fetch_pull_request_refs`) ends with `fetch_pull_request_refs`, which is at `pr.py:57` — one line past the cited range. Verified against current source. Minor; doesn't block a junior implementer since they'll read the whole function regardless.

### [NOTE] G.2 defers a real implementation choice to the implementer

"extend `ReviewResult` or the terminal display (whichever... check `ReviewResult`'s current fields before adding new ones, and prefer a display-layer addition...)" leaves a design-placement decision open, consistent with the pattern already noted (NOTE, not blocking) against D.3/E.1 in the file-2 review. It does include a decision procedure, so it's low-risk, but it's the same class of ambiguity recurring in a third task.

### [NOTE] Closeout still has no explicit commit step

Already flagged in the part-1 review (F003) and still present in file 3: H.3 updates DEVLOG/CHANGELOG/task-status and merges the branch, but names no `git commit` bullet for those doc changes before the merge — every other Part in the three-file breakdown ends with one.

### [PASS] Parts F/G/H trace cleanly to D6, D2/D5, and closeout; no scope creep

The Coverage Check's mapping (D6 → Part F, D2/D5 → G.1/G.3/G.2, D8 → G.2's override calls) matches the actual task content, and nothing in file 3 reaches into excluded territory (persistence, posting, PR creation, pipeline PR targets). `--diff` is correctly omitted from the PR command's flag set, consistent with the design's own parity list and D2's rationale.

### [PASS] Code anchors verified accurate against live source

Spot-checked `_warn_not_persistable` (286), `_run_review_command`/`_execute_review` (538-678), `review_code`'s flag block (985-1015), and `pr.py`'s `show` sequence — all match current source exactly, continuing this doc set's track record of precise citations.
