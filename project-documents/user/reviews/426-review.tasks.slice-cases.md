---
docType: review
layer: project
reviewType: tasks
slice: slice-cases
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/426-tasks.slice-cases.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 6e72e0f769e06d2b77dab57914904ebebfea7b91
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 633459
cachedTokens: 447401
cacheWriteTokens: 186048
completionTokens: 69092
durationSeconds: 297.1
costUsd: 0.369145
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/slices/426-slice.slice-cases.md:430"
  - id: F002
    severity: pass
    category: conventions
    summary: "Test-with pattern, commit markers and no merge tasks"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:64"
  - id: F003
    severity: pass
    category: coverage
    summary: "Referenced code names exist, and the Task 6 gate fires correctly"
    location: "src/squadron/replay/start_point.py:23"
  - id: F004
    severity: concern
    category: testability
    summary: "Task 2's success grep cannot pass after the rename"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:71"
  - id: F005
    severity: concern
    category: sequencing
    summary: "The Task 6 gate blocks Tasks 11 and 12, which do not depend on 421–425"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:102"
  - id: F006
    severity: concern
    category: consistency
    summary: "Task 12 does not define the predicate Task 13 reuses"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:143"
  - id: F007
    severity: concern
    category: consistency
    summary: "The skip rule for pre-sandbox rejections has no defined digest"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:166"
  - id: F008
    severity: concern
    category: consistency
    summary: "The design says \"no edits to 424 or 425\", but the tasks edit both"
    location: "project-documents/user/slices/426-slice.slice-cases.md:42"
  - id: F009
    severity: concern
    category: coverage
    summary: "The breakdown has no load test for network and environment-layer paths"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:51"
  - id: F010
    severity: concern
    category: sizing
    summary: "Task 33 bundles five concerns, and Task 37 bundles an end-to-end test into a rendering task"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:272"
  - id: F011
    severity: concern
    category: testability
    summary: "Task 26's success requires `committed`, with no outcome to record otherwise"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:234"
  - id: F012
    severity: note
    category: testability
    summary: "Task 39 step 7 does not say how to create the fresh benchmark"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:316"
  - id: F013
    severity: note
    category: testability
    summary: "Task 24's argv says `--max-cost <cap>`, but the design says per-replay cap"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:220"
  - id: F014
    severity: note
    category: sequencing
    summary: "Task 8 has a forward reference and runs after the design's spike-first step"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:116"
  - id: F015
    severity: note
    category: testability
    summary: "Task 14's module-level success criterion cannot be checked as written"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:159"
  - id: F016
    severity: note
    category: sequencing
    summary: "Task 4 should keep the initiative lookup before `cf init`"
    location: "src/squadron/replay/sandbox.py:175"
  - id: F017
    severity: note
    category: sizing
    summary: "Task 11 has ten smoke tests where one parametrized test would cover them"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:136"
  - id: F018
    severity: note
    category: consistency
    summary: "Task 30 constructs its sidecar store inside the diff judge loop"
    location: "project-documents/user/tasks/426-tasks.slice-cases.md:256"
---

# Review: tasks — slice 426

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria are covered by tasks

Each functional, technical and integration criterion has a task. Rejections come from fixtures (Task 11) and their checks (Tasks 13, 15, 18). Replay on P6 with cf in the scrubbed home is covered by Tasks 7, 8, 24 and 26. Over-size, forfeit and harness-absent handling are covered by Tasks 27, 29, 31 and 33. The failure-mode tests are in Tasks 3, 4, 10, 13, 19, 24, 30, 31 and 33. Pairwise hand-computed tests are in Task 36. Yield rows are in Task 22 and the report in Tasks 35 to 37. No success criterion is unassigned.

### [PASS] Test-with pattern, commit markers and no merge tasks

Each implementation task carries its own tests. The roughly 18 `**Commit**:` markers sit after tested groups, not after every task. No task merges or pushes, which matches the git rules.

### [PASS] Referenced code names exist, and the Task 6 gate fires correctly

`_ArtifactKind`, `_KINDS` and `_suffix_order` exist as Task 2 says. `_call` and `_judge_pair` are in `replay/judging.py`, and `_register_with_cf` and `_initiative` are in `replay/sandbox.py`. `plan_file_for`, `get_slice_ranges`, `get_positive_int_config`, `judge_timeout_s`, `data_dir`, `DOCS_ROOT`, `ARCHITECTURE_DIR` and `tests/metrology/slice_range_repos.py` all exist. `src/squadron/benchmark/` does not exist, and nothing from 421 or 424 (`CaseDrop`, `BenchmarkCase`, `ScrubbedEnvironment`, `run_suite`) is in `src`, so the BLOCKED gate in Task 6 is correct.

### [CONCERN] Task 2's success grep cannot pass after the rename

The check `grep -rn "_KINDS\|_ArtifactKind\|_suffix_order" src tests` must find nothing. But `ARTIFACT_KINDS`, the required new name, contains the substring `_KINDS`, so the grep matches the renamed constant. A junior will either fail the check or adjust it without a record. Use `grep -rnw "_KINDS\|_ArtifactKind\|_suffix_order"`, since `-w` does not match inside `ARTIFACT_KINDS`.

### [CONCERN] The Task 6 gate blocks Tasks 11 and 12, which do not depend on 421–425

The task file says that once Task 6 stops, Tasks 7 onward wait. Task 11 needs only git fixtures, the existing `tests/metrology/slice_range_repos.py` helper, and 403's `get_slice_ranges`. Task 12 (`normalize`) is a pure function that uses only `DOCS_ROOT`. Neither needs 421–425. The working rule is to finish whatever does not depend on the blocked part. Move Tasks 11 and 12 ahead of the gate, or state that the gate blocks only tasks that import 421–425 names.

### [CONCERN] Task 12 does not define the predicate Task 13 reuses

Task 13's `has_code_change` says to reuse "diff_normalize's dropped-path rule ... exported as one function". Task 12 never names or tests that function, so Task 13 depends on something no task builds. Add to Task 12 a named predicate, for example `is_dropped_path(path) -> bool`, with a test, and have `normalize` call it.

### [CONCERN] The skip rule for pre-sandbox rejections has no defined digest

Task 15 defines `can_skip(record, digest)`, and Task 20 skips candidates whose record satisfies it. Pre-sandbox rejections such as `no_design_at_fork` have no environment digest. The design keys those records as "pre" (project-documents/user/slices/426-slice.slice-cases.md:207), but its Data Flow checks the skip key after sandboxes are created (design:118–119), which a candidate rejected before sandboxes never reaches. The tasks don't say what digest a `start_environment=None` record passes. Specify this in Task 15 and Task 20: run the pre-sandbox checks first, pass "pre" for those records, and check skip before any sandbox is created.

### [CONCERN] The design says "no edits to 424 or 425", but the tasks edit both

The design's Technical Scope says "No edits to 424 or 425". Task 9 widens 424's `CaseDrop.reason`. Task 25 removes a 424 refusal and changes its test. Tasks 35 and 37 change 425's `bench_report.py`, which the design also asks for (design:427). The design's Technical Requirements (design:451) say D17 "extracts the interval", but design:312 says "No change to 425". Task 1's correction list (task:61) does not reconcile any of this. Task 1 should correct design:42 and design:451 to name exactly which 424 and 425 code changes this slice makes.

### [CONCERN] The breakdown has no load test for network and environment-layer paths

The Context Summary states "Load test: none added" because the work is sequential and every call has a timeout. The python rules (`.claude/rules/python.md`, Load-test tier) require at least one `tests/load/` test for code on network, concurrency or environment-layer paths, and require CI to gate it. This slice adds judge dispatch (network), `ScrubbedEnvironment.with_tools` (environment layer, Task 7) and sandbox subprocess calls. Add a `tests/load/` task that asserts latency or resource bounds on a realistic configuration, plus a CI wiring task that gates on it. Alternatively, record in the task file why the rule does not apply to these paths.

### [CONCERN] Task 33 bundles five concerns, and Task 37 bundles an end-to-end test into a rendering task

Task 33 covers the bound arithmetic, the cap, the judge lock, `OverSizeCase` replacement and resume, with seven tests, in one module the design caps near 300 lines. Split it into (a) bound, cap and the before-first-dispatch ordering, and (b) lock, over-size replacement and resume. Task 37 (line 294) combines the pairwise rendering and count line with a mixed-kind test that runs run, grade, judge, report and yield with doubles. Move that mixed test into its own task after Task 34, which is the point where every stage exists.

### [CONCERN] Task 26's success requires `committed`, with no outcome to record otherwise

A replay can legitimately end in a config absence (`no_commit`, `blocked`, `cost_cap`, `producer_failed`). The design treats those as forfeits (design:281–285). The task gives no way to record such a result, so a junior either re-runs against the spend cap or reports a false failure. State that a config absence is recorded in the DEVLOG with its name and that a forfeit is an acceptable result. Re-run only on a harness absence.

### [NOTE] Task 39 step 7 does not say how to create the fresh benchmark

"Rerun step 5 on a fresh benchmark id (another `--samples` value)" needs replays first, and the step does not name the `sq benchmark run` command, the sample count or the cap. Name the command, as Task 26 does, with its `--samples` value and caps.

### [NOTE] Task 24's argv says `--max-cost <cap>`, but the design says per-replay cap

Design:221 says `--max-cost <per-replay cap>`. Task 24 writes only `<cap>`, which a junior could read as the run cap. Name the per-replay cap explicitly.

### [NOTE] Task 8 has a forward reference and runs after the design's spike-first step

Task 8 says "branch as Task 24 defines it", which points forward. The rule is already stated in Task 1's Context Summary (task:45), so cite that. The design says the spike runs first and that nothing is built before it (design:505, design:512). The task file runs Tasks 2–7 first. That order is forced, because the spike needs 421 and 424 code, but Task 1's corrections should say so.

### [NOTE] Task 14's module-level success criterion cannot be checked as written

"The module has no filesystem access outside the temporary directory" is not testable, and the module calls git through `ProcessRunner`. The bullet's tests already cover the observable part: the temporary directory is removed after success and after error. Drop the module-level claim or make it a test.

### [NOTE] Task 4 should keep the initiative lookup before `cf init`

The current `_register_with_cf` resolves the initiative (line 175) before `cf init` (line 176), and sets `_registered` after `cf init` succeeds (line 177). Task 4's `registered` semantics match that. The task does not say the lookup must stay first, so a slice in no plan could create a cf project before it fails. State the order.

### [NOTE] Task 11 has ten smoke tests where one parametrized test would cover them

The success criterion needs each builder to produce its shape. One parametrized test over the builders gives the same check with less code.

### [NOTE] Task 30 constructs its sidecar store inside the diff judge loop

The design says `diff_judge` is pure apart from the injected dispatcher and store (design:105). Task 30 constructs `ContentSidecars("diffs")` inside the loop, while Task 34's `judge_deps()` builds it at the wiring layer. Pass the sidecar store in as a parameter so the loop is testable without touching the disk.

### Run Digest

- Response length: 11518 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 633459 / 447401 / 186048 / 69092 / not computed
- Duration: 297.1 s
- Cost: $0.37 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18

## Resolution

- [pass] Success criteria are covered by tasks: no change needed.
- [pass] Test-with pattern, commit markers and no merge tasks: no change needed.
- [pass] Referenced code names exist, and the Task 6 gate fires correctly: no change needed. The gate is now Task 8 after the reorder below.
- [concern] Task 2's success grep cannot pass after the rename: changed to `grep -rnwE '_KINDS|_ArtifactKind|_suffix_order'`, so `ARTIFACT_KINDS` no longer matches.
- [concern] The Task 6 gate blocks Tasks 11 and 12: moved the fixtures and `normalize` ahead of the gate as Tasks 6–7 and renumbered. The gate is Task 8, and the Context Summary and the gate's "already committed" range say Tasks 2–7.
- [concern] Task 12 does not define the predicate Task 13 reuses: Task 7 now exports `is_dropped(path)` with a test, and Task 13 reuses it by name.
- [concern] The skip rule for pre-sandbox rejections has no defined digest: `can_skip` now takes no digest for a pre-sandbox record (key `pre`, since its checks read only git at fixed shas). The store method accepts `env_digest=None` for it. `qualify_slice_candidate` does both reuse lookups (Tasks 15–16), and Task 20's build calls it instead of skipping itself.
- [concern] The design says "no edits to 424 or 425", but the tasks edit both: added a gap bullet naming the two edits to 424 (widening `CaseDrop.reason`, removing the slice-case planning refusal). Task 1 now corrects the design's Scope line. 425 is not edited.
- [concern] The breakdown has no load test for network and environment-layer paths: added an environment-layer test (eight concurrent `invoke` calls under distinct scrubbed homes, Task 24) and a network-layer test (200-pair plan with a slow dispatcher and a hung one, Task 33). The Context Summary bullet is rewritten.
- [concern] Task 33 bundles five concerns, and Task 37 bundles an end-to-end test into a rendering task: Task 33 is split into Task 33 (bound and cap) and Task 34 (lock, resume, over-size records). Task 37 is split into Task 38 (rendering) and Task 39 (mixed-kind test). The commit marker moves after Task 39, and later tasks are renumbered.
- [concern] Task 26's success requires `committed`, with no outcome to record otherwise: success now accepts `committed` or an absence class. If none committed, the DEVLOG records the classes and only the record's `pipeline` and `producer_step` are checked.
- [note] Task 39 step 7 does not say how to create the fresh benchmark: now Task 41. It says to create it with Task 26's `sq benchmark run` command and `--samples 2`, which prints the new id.
- [note] Task 24's argv says `--max-cost <cap>`, but the design says per-replay cap: changed to `--max-cost <per-replay cap>`.
- [note] Task 8 has a forward reference and runs after the design's spike-first step: now Task 10. It defines the registration branch inline, with no reference to Task 24. A gap bullet explains the order: the spike needs 421's sandbox, so it is the first task after the gate, and Tasks 2–7 need none of 421–425. Task 1 corrects the design's Implementation Notes.
- [note] Task 14's module-level success criterion cannot be checked as written: replaced with "after a call (accepted, rejected or failing) the temporary directory no longer exists".
- [note] Task 4 should keep the initiative lookup before `cf init`: Task 4 now resolves the initiative first. Its test asserts a slice in no plan leaves `registered` false and runs no cf command.
- [note] Task 11 has ten smoke tests where one parametrized test would cover them: now Task 6, and it uses one parametrized smoke test over the builders.
- [note] Task 30 constructs its sidecar store inside the diff judge loop: the loop takes the sidecar store as an injected parameter. `judge_deps()` in Task 35 builds it.

Deferred: none, so no GitHub issues were filed.
