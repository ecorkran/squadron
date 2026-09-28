---
docType: review
layer: project
reviewType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 81be4a9ef8bb48efecb6158e9bb6b2f38169316e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
runId: run-20260927-tasks-plan-1e76e648
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion traces to at least one task; no scope creep; sequencing and test-with pattern hold"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md"
  - id: F002
    severity: concern
    category: testing
    summary: "Task D.6's \"must overlap\" assertion is timing-dependent, undermining the slice's determinism goal"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:430-459"
  - id: F003
    severity: concern
    category: process
    summary: "End-of-slice document edits and G.1's conditional CI fix have no commit step before the branch merge"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md"
  - id: F004
    severity: note
    category: sequencing
    summary: "Part D's commit lands before the CLI suite first runs; a D.7 regression would survive two subsequent commits"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:514-524"
  - id: F005
    severity: note
    category: process
    summary: "The mid-slice red-CI commits are intentional and adequately documented"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:161-173"
  - id: F006
    severity: note
    category: testing
    summary: "Task C.4 should specify `sys.executable`, not bare `python`, for the holder subprocess"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:292"
  - id: F007
    severity: note
    category: testing
    summary: "Task D.8's output-content assertion is click-version sensitive"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:494-513"
---

# Review: tasks — slice 929

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Every success criterion traces to at least one task; no scope creep; sequencing and test-with pattern hold

Functional criteria map cleanly: no-overlap → B.1/B.2 + D.1–D.3 + D.5 + E; error panel with fix hint and exit 1 → D.7/D.8; submodule stays outside the lock → D.6; the three (plus prune) timeout behaviors → D.1–D.4, including the claim-file assertion matching "leaves no claim file behind"; holder-death → C.4; read-only-root immediate failure → C.2 steps 2–3 + C.3. Technical requirements map to C.2 (lazy `fcntl`, D7 table), F.1, G.2. Integration requirements map to D.9 and G.2. All five Verification Walkthrough steps are covered (A.1, D.5, E.2, G.3). I verified the task file's line anchors against the real code: the `add` call spans worktree.py:332-336, `except BaseException` at :346, sweep remove/prune at :253/:265, `_remove` at :400, and the `with ScratchWorktree` block at review_pr.py:426 — all accurate. Two authoring strengths worth keeping: D.1 explicitly orders `except MetadataLockError` before `except BaseException` (without which the conversion to `WorktreeCreationError` would be silently swallowed), and B.1 correctly requires the fake `add` branch to create the target directory because worktree.py writes `lock.json` immediately after the add with no intervening call. G.1 is not scope creep: `.claude/rules/python.md:64` requires CI to gate load tests, and I independently confirmed G.1's factual claim — ci.yml's `test` job runs bare `uv run pytest`, `pyproject.toml` sets `testpaths = ["tests"]` (including `tests/load/`) with only `network`/`host_cf` markers, and the `hermetic` job's `-m "not host_cf"` also leaves the load tier in.

### [CONCERN] Task D.6's "must overlap" assertion is timing-dependent, undermining the slice's determinism goal

`test_submodule_fetch_calls_still_overlap_unlike_worktree_metadata_calls` asserts the submodule max-in-flight is **greater than 1** based on threads happening to interleave (0.02s sleep inside the fake). The never-overlap direction (B.2) is genuinely deterministic — an overlap either happened or a serialized run hangs and the bounded join fails — but the must-overlap direction fails spuriously when a loaded CI scheduler keeps the two threads from entering the 20ms window simultaneously, i.e., the test can go red with correct code. That reintroduces exactly the flakiness this slice exists to eliminate. A `threading.Barrier` (with a bounded timeout so an accidental lock-coverage regression fails loudly rather than hangs) inside the fake's submodule branch would force two concurrent calls to rendezvous, making the assertion deterministic and its failure mode meaningful. The barrier is cheap to specify in the task text and worth adding before implementation.

### [CONCERN] End-of-slice document edits and G.1's conditional CI fix have no commit step before the branch merge

The Completion section edits the task file's frontmatter, the slice design's frontmatter, the parent plan entry (900-slices.maintenance-and-refactoring.md:459), and writes a DEVLOG entry — with no instruction to commit these changes. G.4 asserts a clean tree *before* those edits ("nothing outstanding except this task file's own completion-marking edits below"), so the slice ends with uncommitted document changes, and the next workflow step per the git rules is `git checkout {target}` + merge, which will carry or choke on them. Same gap in G.1's conditional branch ("fix `.github/workflows/ci.yml` ... and note that fix here" — no commit instruction), and G.2's `ruff format` could modify files with no stated commit home. I verified the G.1 fix branch is very unlikely to fire (no exclusion exists today), but the checklist should end with an explicit final commit (e.g., extend G.4 or add a completion commit step) so the merge starts from a clean tree.

### [NOTE] Part D's commit lands before the CLI suite first runs; a D.7 regression would survive two subsequent commits

Task D.9 runs only the full `tests/codehost/test_worktree.py` suite before committing Part D, and D.8 runs only its own new test. The existing tests that exercise D.7's restructured happy path with real worktrees (`tests/cli/test_review_pr_worktree.py`) don't run until G.2's full `pytest`, after the Part E and Part F commits. The blast radius is contained (G.2 is still pre-merge) and D.7's restructure preserves `__exit__` semantics for this class (which ignores `exc_info`), so this is a NOTE, not a CONCERN — but adding the CLI worktree file to D.9's pre-commit run would close the window.

### [NOTE] The mid-slice red-CI commits are intentional and adequately documented

Committing a known-failing test (B.3) and keeping it red through C.5 is deliberate — the design's D6 requires the test to fail before the fix lands — and the task file tells the implementer to note it in the commit body and not to chase it. This is a sound, traceable deviation from "every commit green"; noting it here so a future reviewer doesn't "fix" it.

### [NOTE] Task C.4 should specify `sys.executable`, not bare `python`, for the holder subprocess

The holder-death test spawns `python -c ...`. In a uv-managed project there may be no `python` on PATH outside the venv, making the test environment-dependent. `sys.executable` is the standard robust form; one word in the task text prevents a spurious skip-or-fail.

### [NOTE] Task D.8's output-content assertion is click-version sensitive

`render_code_host_error` prints to a stderr `Console` (pr.py:95-103). Whether `CliRunner`'s `result.output` merges stderr depends on the click version (8.2 split the streams); the existing sibling test the task copies deliberately asserts only `exit_code` and exception type, and D.8 adds a content assertion. The task's hedged "stderr/output" wording is workable, but naming `result.stderr` explicitly (or checking the project's pinned click) would keep a junior implementer from asserting on the wrong stream.

### Run Digest

- Response length: 7405 chars
- Response is newline-free: no
- Tool calls made: 33
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 69937
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
