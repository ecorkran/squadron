---
docType: review
layer: project
reviewType: tasks
slice: pipeline-branch-steps-scoped-commits-and-dependency-aware-batches
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md
aiModel: claude-opus-5-5
status: complete
dateCreated: 20261004
dateUpdated: 20261004
reviewedSha: aafabd233f4ff78b8942017bd0f3c69fff54a246
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 57.1
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion traces to a task"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing respects dependencies"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:21-26"
  - id: F003
    severity: concern
    category: process
    summary: "Commits are made once per Part, not once per task"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:203-207"
  - id: F004
    severity: concern
    category: completeness
    summary: "Prompt-only rendering of the devlog and loop-round commits is unspecified"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:194-201"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Task 4 doesn't test that the existing artifact survives"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:64-69"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Tasks 14, 15, 22 and 23 are too large for one junior AI"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:229-250"
  - id: F007
    severity: note
    category: test-coverage
    summary: "Criterion 4 is checked only by the live walkthrough"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:274-280"
  - id: F008
    severity: note
    category: organization
    summary: "The criterion 7a test sits in the pipeline-YAML task"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:279"
  - id: F009
    severity: note
    category: process
    summary: "Merging the slice branch is left to Phase 7"
    location: "project-documents/user/tasks/196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:380"
  - id: F010
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating task needed"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:408-440"
---

# Review: tasks — slice 196

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [PASS] Every success criterion traces to a task

- Criteria 1, 3 and 7b → Task 15. Criterion 2 → Tasks 14 and 16.
- Criterion 4 → Task 27 plus walkthrough step 2. Criterion 5 → Task 22. Criterion 6 → Task 23.
- Criterion 7 → Task 25. Criterion 7a → Task 27. Criterion 8 → Tasks 29 and 30. Criterion 9 → Tasks 32–34.
- Criterion 10 → Task 9. Criterion 11 → Tasks 4–6. Criterion 12 → Task 7.
- Technical requirements: the D2-row tests are in Task 14 and the git failure-path tests in Tasks 22–24. The halted-run report is Task 24, docs are Task 36, and lint and types are checked in every commit task. Prompt-only parity is Tasks 18 and 26.

No task falls outside the design's scope. Task 1 (branch setup), Task 36 (CHANGELOG, which D4 requires) and Task 38 (walkthrough) are all process or design-required work.

### [PASS] Sequencing respects dependencies

Each piece is built before anything that uses it:
- `git_ops` (Task 11) comes before `CommitAction` (Task 15), which needs `GitStateUnknownError` and the strict target reader for D6 and D8.
- `CommitAction`'s `stage_all` comes before enter's leftover-preserve commit (Task 22).
- The halting `finally` (Task 24) comes before the batch composition test (Task 27).
- Item dependencies (Task 29) come before the flag set (Task 30).
- `existing: keep` (Task 33) comes before `tasks-plan.yaml` (Task 34).

### [CONCERN] Commits are made once per Part, not once per task

CLAUDE.md says "Git add and commit from project root at least once per task." The breakdown commits only at the end of each Part:
- Part C has 8 tasks (11–18) before its commit in Task 19.
- Part D has 8 tasks (20–27) before Task 28.

Both Parts rework high-risk shared code (`CommitAction`, `executor.py`, `_execute_each_step`), so a failure partway through has no restore point. At minimum, add commits after Task 12 (git_ops), Task 15 (CommitAction), Task 23 (BranchAction) and Task 25 (loader rule). Better still, commit after every implementation-plus-test task.

### [CONCERN] Prompt-only rendering of the devlog and loop-round commits is unspecified

- **Devlog commit.** Task 17 has `DevlogStepType.expand()` add a commit with `CommitSubject.DEVLOG`. But Task 18's `sq _commit` flags follow the design's API contract (`--subject design|tasks|architecture|code`), which leaves out `devlog`. A prompt-only P6 run would then have no way to render its DEVLOG commit.
- **Loop-round commits.** Task 18 doesn't say how the renderer produces `--template` and `--round` for these commits. D1 derives the subject from the round's last review action. The renderer has to do the same at render time, or parity (the integration requirement) breaks.

Fix: add `devlog` to the CLI's `--subject` choices, and state how the renderer fills `--template` and `--round` for loop bodies. Add a renderer test for a P4 loop round and for the devlog step.

### [CONCERN] Task 4 doesn't test that the existing artifact survives

The bug in #175 was a fabricated review written over the slot's existing artifact. D13 and criterion 11 require that "No review file is written or archived." Task 4 only asserts that the error is raised "before any request". Task 5 asserts that no file is *written* for the pre-run path, but nothing checks *archiving*.

Fix: add a test where a review artifact already exists in the slot. When the backstop fires, the artifact should be left unchanged and not archived.

### [CONCERN] Tasks 14, 15, 22 and 23 are too large for one junior AI

- Task 22 covers all six D5 steps, the leftover-preserve path and 10 guard tests.
- Task 23 covers all of D6 plus 7 failure-path tests.
- Task 14 covers every subject's candidate set, the full D2 message table and about 12 tests.
- Task 15 covers six separate behaviours: scoped staging, the `stage_all` guard, the D8 planning-commit guard, the timeout classification, the warnings, and removing `message_prefix`.

Elsewhere the breakdown splits implementation from tests (Tasks 2/3 and 11/12), but these four tasks put everything together.

Fix: split each one, for example:
- Task 22: enter guards (D5.1–5.5) / switch and leftover-preserve (D5.4, D5.6) / tests.
- Task 23: the happy path and already-merged case / the failure and abort path.
- Task 15: plan staging and messages / the branch guards (D3 and D8) and timeout classification.

### [NOTE] Criterion 4 is checked only by the live walkthrough

Task 27 tests that the pipelines load and that their steps are in the right order. The key outcome — the code review resolving its diff range on the slice branch — is only checked in walkthrough step 2 (Task 38). Consider an integration test for P6 with fake dispatch and review that asserts `_find_slice_branch` resolves while on the entered branch.

### [NOTE] The criterion 7a test sits in the pipeline-YAML task

The two-item `each → enter → implement → merge` test is an engine test that needs nothing from the built-in YAML. It would fit better at the end of Task 24, right after the halting and report work it depends on, so that Task 27 is only about YAML.

### [NOTE] Merging the slice branch is left to Phase 7

CLAUDE.md requires merging the slice branch into the target when implementation is done. The Notes section hands this to Phase 7. That works if the process guide sets things up that way, but I didn't check the guide, so I can't confirm it.

### [PASS] No load-test or CI-gating task needed

The slice design states no performance or load NFR, so no `tests/load/` task and no CI wiring task are needed.

### Run Digest

- Response length: 7710 chars
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
- Duration: 57.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Response

Origin key: **original** means the gap was in the first breakdown (`aafabd23`). The design's own origin is noted where the fix touched it.

- **F003, commits once per Part. Origin: original.**
  - Fixed. Every implementation-plus-test task now ends with its own commit (Tasks 3, 4, 5, 6, 7, 9, 12–18, 20–27, 29, 30, 32–34, 36, 38). Parts A, C and D close with a checkpoint task that runs the full suite and creates no commit unless fixes are needed. The Context Summary states the rule.
- **F004, prompt-only devlog and loop-round commits. Origin: original, in the design's API contract.**
  - Fixed in the design and in Task 18. `sq _commit --subject` gains `devlog`, and the design now says the renderer fills `--template` and `--round` for a loop round from the round's last review action, the same lookup the executor uses (Task 13). Task 18 adds renderer tests for a P4 loop round and for the devlog step. This amends the slice design after its two reviews; it adds no new decision.
- **F005, artifact survives the backstop. Origin: original.**
  - Fixed in Task 4 (existing artifact unchanged and not archived when the resolver raises) and Task 5 (the rejected pre-run case also asserts no archive).
- **F006, oversized tasks. Origin: original.**
  - Fixed by splitting: 14 → 14a (paths and staging) / 14b (messages); 15 → 15a (plan staging and messages) / 15b (D3/D8 guards and timeout); 22 → 22a (enter guards) / 22b (switch and leftover preservation); 23 → 23a (merge happy path and already merged) / 23b (failure and abort path). Each half carries its own tests.
- **F007, criterion 4 only in the walkthrough. Origin: original.**
  - Fixed in Task 27: a P6 integration test with fake dispatch and review asserts `_find_slice_branch` resolves the slice branch while on the entered branch, the diff range resolves, and the run ends on the target with the merge commit.
- **F008, 7a test placement. Origin: original.**
  - Fixed. The criterion 7a composition test moved to Task 24, after the halting and report work it depends on. Task 27 is now YAML plus the P6 integration test.
- **F009, merge left to Phase 7. Origin: original. No change.**
  - Checked against the guide: `guide.ai-project.005-task-breakdown.md` says the merge happens in Phase 7 after the code review and forbids a merge item in any task's Success Criteria, because it deadlocks Phase 6 completion. The CLAUDE.md merge rule applies at the end of implementation, which Phase 7 covers.
- **Numbering:** original task numbers are kept, with letter suffixes for the splits. Tasks 10, 31 and 35 no longer exist (their commits folded into the preceding tasks), so the sequence has gaps. The file notes this.
