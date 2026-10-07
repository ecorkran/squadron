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
reviewedSha: e4682938999636a2c22135d7923ae81cc5968bc3
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 59.4
runId: run-20261007-p5-f492c43d
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:30-32"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and dependencies are sound"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:53-454"
  - id: F003
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating task is required"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:415"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 24 is too large for one junior-completable unit"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:272-289"
  - id: F005
    severity: concern
    category: commit-checkpoints
    summary: "The Task 12 refactor has no commit checkpoint and lands in a `feat:` commit"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:149-186"
  - id: F006
    severity: concern
    category: testing
    summary: "The CLI tests' hermetic runs-dir injection is unspecified"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:337-347"
  - id: F007
    severity: note
    category: test-with-pattern
    summary: "Some tests trail their implementation by several tasks"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:161-185"
  - id: F008
    severity: note
    category: process
    summary: "Task 35 runs `gh issue create` and edits the design on the slice branch"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:416-426"
  - id: F009
    severity: note
    category: task-sizing
    summary: "Task 36 is broad, and Task 31 uses different wording from the design"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:430-454"
---

# Review: tasks — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage is complete

- **Functional requirements:**
  - Pipeline grouping and shadowing: Tasks 13 and 15.
  - Run listing, `--all` and `--pipeline`: Tasks 25, 27 and 28.
  - Resume-at equals the `--resume` step: Tasks 3 and 23.
  - Item-resume equivalence for open and accept counts: Tasks 9 and 26.
  - `--list` removal: Tasks 16 and 17.
  - `sq agents list` and slash commands: Tasks 18 to 20.
  - `wait` exit codes: Tasks 29 to 32.
- **Technical requirements:**
  - I/O-bounds test with the 300-run mix: Task 26.
  - `caplog` assertions per `ResumeProblem`: Tasks 23 and 24.
  - Marker-text test: Task 27.
  - Parity test: Task 9.
  - Real fixtures and the `tmp_path` hermetic rule: stated in the Context Summary and applied in each test task.
- **Process steps:** the Verification Walkthrough is Task 36, and docs, CHANGELOG and follow-up issues are Tasks 33 to 35.

I found no scope creep. The `RUNNING_STATUS` constant in Task 3 traces to D13 and is called out there.

### [PASS] Sequencing and dependencies are sound

- Part A (refactor) comes first and ends in commits at Tasks 4, 6, 9 and 11, before any new surface.
- `run_views` (Task 12) exists before its consumers in Tasks 13, 27 and 31.
- `run_listing` types (Task 21) come before the resolvers (22 to 24), then `list_run_summaries` (25), then the renderer (27) and the command (28).
- There are no circular dependencies.
- Commits are spread across the file rather than batched at the end.
- Merging is correctly left to Phase 7, and Task 36 says so.

### [PASS] No load-test or CI-gating task is required

The slice states that "the architecture sets no NFR for this path" and that the under-1-second target is advisory. The count-based I/O-bounds test (Task 26) stands in for a load test. A `tests/load/` task and a CI wiring task are therefore not required.

### [CONCERN] Task 24 is too large for one junior-completable unit

Task 24 bundles three things:
- The completed-run resolver, which is two or more helpers: `report_json_paths`, `single_each_step`, `load_report` and counting `open_items` and `acceptable_items`.
- The dispatch for `running` and other statuses.
- A test list of about eight scenarios, each with enum and `caplog` assertions.

Split it into:
- 24a: the resolver plus the `running` dispatch.
- 24b: its tests.

Keep the commit after 24b. Task 23 shows the right size, with its implementation and tests as separate bullets.

### [CONCERN] The Task 12 refactor has no commit checkpoint and lands in a `feat:` commit

Task 12 moves `_STATUS_COLORS` and `_display_run_status` out of `run.py`. That is a behaviour-preserving refactor of existing code. It sits uncommitted through Tasks 13 and 14 and is committed with Task 15 as `feat: add sq pipelines list`. The design's Development Approach calls for refactors to be committed on their own. Add a verification step to Task 12 (`ruff`, `pyright`, and the `tests/cli` run for the `--status` tests) and a `refactor: move STATUS_COLORS and render_run_status to run_views` commit.

### [CONCERN] The CLI tests' hermetic runs-dir injection is unspecified

Task 28 says "hermetic runs dir", and Task 32 injects "poll/clock via the helper's parameters or a monkeypatched `wait_for_run`". Neither says how a `CliRunner` test points the command at a `tmp_path` runs directory. That depends on how `run.py --status` builds its `StateManager`: a config path, an env var, or a patched factory. Without this, a junior could write tests that read `~/.config/squadron/runs`. Task 36's `HOME=$(mktemp -d)` check would catch that only afterwards. Name the exact mechanism in Task 28 and reuse it in Task 32. The design points only to `tests/_hermetic.py`.

### [NOTE] Some tests trail their implementation by several tasks

- **Part B:** Tasks 13 and 14 (renderer, command) have their tests in Task 15, with Task 12 before them.
- **Tasks 18 to 20:** Tasks 18 and 19 (`agents list` and its references) are tested together in Task 20.
- **Task 27:** it bundles its tests with the implementation, which is fine.

Test-with is mostly honoured, and each group is small enough to be acceptable. Consider moving the render tests of Task 15 into Task 13.

### [NOTE] Task 35 runs `gh issue create` and edits the design on the slice branch

- **External action:** creating GitHub issues publishes content externally. The design (Development Approach step 6) authorises opening them. The implementer should still show the Project Manager the issue titles and bodies before creating them.
- **Planning artifact edited on the slice branch:** the task edits the slice design, and CLAUDE.md says planning artifacts commit to the target. The edit is only link additions, so this is minor. State explicitly that it is intended.

### [NOTE] Task 36 is broad, and Task 31 uses different wording from the design

- **Task 36:** it combines the walkthrough, the hermeticity check and the full gate. It is acceptable because the sub-items are independent and each has its own success line.
- **Task 31:** it says "status panel", while D13 and the design say "status line". Task 12 resolves this by moving the Rich "Run Status" panel into `render_run_status`. Use one term in Tasks 31 and 36 to avoid confusion.

### Run Digest

- Response length: 6797 chars
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
- Duration: 59.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
