---
docType: review
layer: project
reviewType: tasks
slice: artifact-usage-stamping
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/178-tasks.artifact-usage-stamping.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 9057f0adcd78fa804ec9b8acf7b545fc55f49512
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 172784
cachedTokens: 87416
cacheWriteTokens: 85362
completionTokens: 3916
durationSeconds: 31.4
costUsd: 0.390026
costBasis: provider
runId: run-20261017-p5-a1cd3acb
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 4 references RunCost key-name definitions that no task creates"
    location: "src/squadron/review/run_cost.py:54"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Task 12 is overweight and carries the unpersisted work of Tasks 10 and 11"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F003
    severity: concern
    category: completeness
    summary: "Task 10 depends on `context.iteration`, which the slice design does not list"
    location: "src/squadron/events/contexts.py:55"
  - id: F004
    severity: note
    category: scope
    summary: "Dispatcher-order test checks existing behavior no success criterion requires"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F005
    severity: note
    category: documentation
    summary: "Slice design still names the wrong file for the slice header"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md:81"
  - id: F006
    severity: note
    category: robustness
    summary: "Task 18 uses line numbers as anchors in the architecture doc"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered by tasks"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing, test placement and merge handling are sound"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
---

# Review: tasks — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 4 references RunCost key-name definitions that no task creates

Task 4's second step says to replace the key string literals with "the key names `RunCost` defines", so each key is defined once (D4). Task 2 adds `frontmatter_fields()` and `from_record` but never says to extract key-name constants. At `run_cost.py:54`, `"promptTokens"` is an inline literal inside a tuple list. No constants exist today. A junior implementer would find nothing to reference. Fix: add a Task 2 sub-item that extracts the key names into constants (or an enum) that `frontmatter_fields()` uses. Alternatively, reword Task 4 to create them.

### [CONCERN] Task 12 is overweight and carries the unpersisted work of Tasks 10 and 11

Tasks 10 (action) and 11 (registration) have no commit. Task 12 commits both together with about 15 test assertions across five themes: happy paths, eligibility, a StateManager spy, binding order, `disable:`, and dispatcher order. The context summary says every code-changing task ends with a commit. That holds for the whole file only if "task" means each implementation-and-test pair. Split Task 12 into (a) happy-path and eligibility tests with a commit, and (b) binding and `disable:` tests with Task 11's commit. This keeps commits small and matches the stated rule.

### [CONCERN] Task 10 depends on `context.iteration`, which the slice design does not list

The slice design's "Interfaces Required" lists the `PostActionContext` fields as `action_type`, `result`, `expected_artifact_kind`, `params`, `run_started_at`, `cf_client` and `cwd`. It does not list `iteration`. The code does have `iteration: int` at `contexts.py:55`, and `revision_stamp.py:104` uses it, so the dependency is satisfiable. Task 10 still says "find where the iteration is available… do not guess". Name `context.iteration` directly, citing `revision_stamp.py:104`. Also fix the design's interface list so the two documents agree.

### [NOTE] Dispatcher-order test checks existing behavior no success criterion requires

The Task 12 sub-item "when `dispatch-artifact` fails, `usage-stamp` does not run" tests `fire`, not new code. The only support is a design rationale in "Interfaces Required", not a success criterion. It is small and cheap, so I'm flagging it only. Drop it if you want a leaner file. The related sub-item about `disable:` does trace to an Integration Requirement, so it should stay.

### [NOTE] Slice design still names the wrong file for the slice header

The component table says `cli/stats_views.py`. The task file's context summary corrects this to `cli/stats_effort_views.py`. Fix the design too, so the corrected path doesn't live only in the task file.

### [NOTE] Task 18 uses line numbers as anchors in the architecture doc

Task 18 locates edits by "near line 597", "Line 124" and "Line 122" in `140-arch.pipeline-foundation.md`. Line numbers drift when the doc is edited. Anchor on the text instead (for example the `events/builtin/` tree entry and the sentence about "reusing only `ActionResult` and `ValidationError`").

### [PASS] Success criteria are fully covered by tasks

Each criterion maps to at least one task:
- **Design, task-file and arch-doc stamping:** Tasks 10 and 12.
- **Loop folding:** Task 12.
- **Revision-restart WARNING:** Task 13.
- **Nothing stamped for keep, failed, implement, summary or compact:** Task 12 eligibility.
- **Split task breakdowns:** Task 13.
- **Unpriced rounds:** Tasks 9 and 12.
- **Artifact spend line surviving a prune, and not summed with recorded spend:** Tasks 16 and 17.
- **Byte-identical review artifacts:** Task 3.
- **`dispatch-artifact` tests unchanged:** Task 7.
- **No StateManager writes:** Task 12.
- **D6 failure rows with log signals:** Task 13.
- **ruff, pyright and the full suite:** Task 19.

Nothing traces to no criterion except the dispatcher-order test noted above. The summary and compact exclusions are handled correctly.

### [PASS] Sequencing, test placement and merge handling are sound

The order is refactors (Part A), then model (B), then action (C), then report and line (D), then docs and validation (E). There are no circular dependencies. Commits occur after Tasks 3, 5, 7, 9, 12, 13, 15, 17, 18 and 19. The branch is created in Task 1 and no merge task is written, as the Git Rules require. The Task 19 live-pipeline walkthrough is gated on Project Manager confirmation and prunes only scratch runs. No NFR is restated in the slice, so no load-test or CI-gate task is needed.

### Run Digest

- Response length: 5550 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 172784 / 87416 / 85362 / 3916 / not computed
- Duration: 31.4 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
