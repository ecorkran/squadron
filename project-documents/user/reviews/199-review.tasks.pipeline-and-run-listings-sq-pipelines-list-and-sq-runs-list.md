---
docType: review
layer: project
reviewType: tasks
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 4c997ba56244211bd57f1382dc5908c7dd324bdd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 35.6
runId: run-20261007-p5-f492c43d
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Shared status-line renderer is never created"
    location: "src/squadron/cli/commands/run.py:555"
  - id: F002
    severity: concern
    category: scope
    summary: "Task 36 opens an issue that already exists"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:195"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 36's design edit is not committed in its own step"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:410-418"
  - id: F004
    severity: note
    category: test-with
    summary: "Tasks 27–29 delay tests across two implementation tasks"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:312-344"
  - id: F005
    severity: note
    category: clarity
    summary: "`wait_for_run` does not say how it distinguishes NOT_FOUND from UNREADABLE"
    location: "src/squadron/pipeline/state.py:421-429"
  - id: F006
    severity: note
    category: scope
    summary: "`RUNNING_STATUS` change is untested and missing from the commit message"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:63-72"
  - id: F007
    severity: pass
    category: nfr
    summary: "Load test and CI gating not required"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:415"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and traceability"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:30-32"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing, sizing and commit distribution"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md"
---

# Review: tasks — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Shared status-line renderer is never created

Task 32 says `sq runs wait` prints its status line "through the shared `run_views` renderer (same as `sq run --status <run-id>`)" and "not duplicated". No earlier task creates that renderer. Task 12 moves only `STATUS_COLORS`, and `_display_run_status` stays in `run.py` (line 555). The design rule that no command module imports another means `runs.py` cannot import it from `run.py`. A junior implementer would either duplicate the function or break the rule. Fix: add a sub-item to Task 12 that moves `_display_run_status`, and the status line it prints, into `run_views`, with `run.py` importing it. Task 12 should also add a regression test that the `sq run --status` output is unchanged. As written, Task 12 asserts "output unchanged" with no test behind it.

### [CONCERN] Task 36 opens an issue that already exists

D13 already links the PID-in-run-state follow-up to #190, and the recent commit "link slice 199 orphan-run follow-up to #190" confirms this. Task 36 item (2) still tells the implementer to `gh issue create` for the same thing. That would produce a duplicate issue. The design's Development Approach step 6 lists only two issues to open, the `RunState.status` typing and `--json`. Fix: reduce Task 36 to two issues and reference #190 for the PID item. Also change the success line "three issue numbers recorded" to match. The D13 link no longer needs adding.

### [CONCERN] Task 36's design edit is not committed in its own step

Task 36 edits the slice design and creates outward-facing GitHub issues, but it has no commit step. The changes would sit uncommitted until Task 37's catch-all "finalize" commit. Also, Task 35's commit lands before Task 36. Fix: add a commit (`docs: link slice 199 follow-up issues`) at the end of Task 36. Task 37's final commit would then only cover leftovers.

### [NOTE] Tasks 27–29 delay tests across two implementation tasks

Task 27 (marker text and renderer) and Task 28 (command) are both implemented before Task 29 holds any tests. Tasks 13–15 follow the same pattern for the pipeline listing. This is acceptable because the units are small and share one commit. Splitting the rendering tests into Task 27 would match the test-with pattern more closely.

### [NOTE] `wait_for_run` does not say how it distinguishes NOT_FOUND from UNREADABLE

`StateManager.load` raises `FileNotFoundError` for a missing run and `SchemaVersionError` (line 71, raised at line 199) for a bad schema. A corrupt JSON file may raise other exception types. Task 30 states the outcome mapping but not which exceptions map to `UNREADABLE`. Fix: name the exact exception set, in the style of Task 22. Task 31's "unreadable state file" test should cover both a corrupt file and a schema-version mismatch.

### [NOTE] `RUNNING_STATUS` change is untested and missing from the commit message

Task 3 adds the `RUNNING_STATUS` constant to the Part A refactor, but Task 4's tests and its commit message cover only `first_unfinished_step_of` and `RESUMABLE_STATUSES`. The change is trivial and the grep success check is enough. It is, though, an unlisted change in a commit labelled as a pure extraction.

### [PASS] Load test and CI gating not required

The slice states that the architecture sets no NFR for this path. The under-1s target is advisory and is measured once in the walkthrough, not asserted in a test. Task 26's I/O-bounds test enforces the call counts without wall-clock timing. No `tests/load/` task or CI wiring task is required.

### [PASS] Success-criteria coverage and traceability

Every functional and technical requirement maps to a task:
- **Pipeline listing and ordering:** Tasks 10–15.
- **Run listing filters and hidden runs:** Tasks 25 and 29.
- **Resume equivalence:** parity tests in Tasks 9 and 26.
- **Flag removal:** Tasks 16–17.
- **`sq agents list`:** Tasks 18–20.
- **`wait` exit codes:** Tasks 30–33.
- **I/O bounds, marker-text test, hermeticity:** Tasks 26, 29 and 37.

No scope creep beyond the Task 36 duplicate issue. The traceability line in the Context Summary matches the design sections.

### [PASS] Sequencing, sizing and commit distribution

- **Dependencies:** `first_unfinished_step_of` (Task 3), the report helpers (Task 5) and `item_eligibility` (Task 7) all land before `run_listing` (Tasks 21–26). There are no circular dependencies.
- **Test-with:** tests follow the implementation in nearly every pair.
- **Commit cadence:** about a dozen semantic commits are spread across Parts A–F rather than batched at the end.
- **Merge:** merging is correctly deferred to Phase 7.
- **Size:** tasks are appropriately sized, and Tasks 23 and 24 are split to stay under the ~50-line function limit.

### Run Digest

- Response length: 6070 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 35.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
