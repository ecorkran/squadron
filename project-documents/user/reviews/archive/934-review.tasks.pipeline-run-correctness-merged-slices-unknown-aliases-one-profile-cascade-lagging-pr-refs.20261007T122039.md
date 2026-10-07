---
docType: review
layer: project
reviewType: tasks
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: f2501b28b735b879f0b3333043d71a0e623da752
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 41.1
runId: run-20261007-p5-56b33e7c
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:37-281"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit cadence are sound"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:45-256"
  - id: F003
    severity: pass
    category: nfr
    summary: "Load-test and CI-gating requirements do not apply"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:316-339"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 18 changes an error constructor that an existing call site still uses"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:190"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 22 bundles too many behaviours for one task"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:219-225"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 24 mixes a new component with a cross-cutting tagging sweep"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:234-242"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "`sq pr create` wiring has no test"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:246-248"
  - id: F008
    severity: note
    category: clarity
    summary: "Smaller inconsistencies and omissions"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:211"
---

# Review: tasks — slice 934

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage is complete

Each functional criterion maps to at least one task, and the failure-mode tables have tests too.
- **#188:** Tasks 13–16 cover the predicate, `cwd` plumbing, source selection, item resume, the D10 failure rows and the `cwd`-differs-from-process test.
- **#184 and #175:** Tasks 2–9 cover the shared module, the parity test (Task 6), the unknown-template pre-run error, and the review-step profile source in the alias check. Tasks 10–11 cover `--dry-run`, `--strict` and the byte-identical artifact check.
- **#186:** Tasks 18–25 cover the models, the base fast-forward adjustment, the primary-fetch timeout, the head fallback with an absent-locally fixture, classification, the GitHub refspec, the logging scope and the CLI wiring.
- **Walkthrough, docs and close-out:** Tasks 27–29 cover these.

### [PASS] Sequencing, test-with pattern and commit cadence are sound

- **Dependencies:** each task's inputs exist before it runs. For example, Task 2 comes before Tasks 3 and 5, Task 7 before Task 8, Task 8 before Task 9, Task 13 before Tasks 15–16, and Task 14 before Task 15.
- **Test-with:** tests sit inside the task that implements the behaviour.
- **Commits and checkpoints:** every code task ends with a commit, and each part closes with a validation checkpoint (Tasks 12, 17, 26), so commits are spread across the slice rather than batched.
- **Merge:** no merge task is listed, which matches the project rule.
- **Cycles:** there are none.

### [PASS] Load-test and CI-gating requirements do not apply

The slice restates no throughput, latency or scale NFR. D10 bounds are timeouts with failure-mode tests, not performance targets. A `tests/load/` task and a CI gate are therefore not required.

### [CONCERN] Task 18 changes an error constructor that an existing call site still uses

Task 18 adds `expected_source` and `actual_source` to `RefMovedSinceResolutionError`, but the only task that updates the raise site in `refs.py` is Task 22. If the new fields are required, Task 18's pyright and test run, and its commit, break at the existing raise site. Task 18 does not say how existing callers and tests keep working.

Do one of these:
- update the current raise site in Task 18;
- make the new fields temporarily optional; or
- move the constructor change into Task 22.

### [CONCERN] Task 22 bundles too many behaviours for one task

Task 22 changes `fetch_and_range` to call the Task 21 helper, add the ancestry classification, run `update-ref`, record the adjustment, and raise `RefMovedSinceResolutionError`. It also renders `update-ref` failure and timeout, and adds the lagging-fixture test suite with about eight cases. That is a lot for one junior-AI task.

Suggested split:
- 22a: classification and `RefMovedSinceResolutionError` for the descends and unrelated cases.
- 22b: `update-ref`, the adjustment record, and the failure and timeout rendering.

### [CONCERN] Task 24 mixes a new component with a cross-cutting tagging sweep

Task 24 builds the `code_host_logging` context manager, its filter, nesting and cleanup. It also asks the implementer to find and tag every WARNING that precedes a raised `CodeHostError` across the adapter and `refs.py`. The sweep is open-ended, and Tasks 19, 21 and 22 already tag some records themselves.

Split the sweep out as its own sub-task. It would list the tagged call sites explicitly and add a test that those, and only those, carry the tag.

### [CONCERN] `sq pr create` wiring has no test

D8 requires `sq pr show` and `sq pr create` to use `code_host_logging(0)`. Task 25's tests name `test_review_pr.py` and `test_pr_show.py` only. Nothing asserts that `pr create` is wrapped or prints a `CodeHostError` once. Add a `pr create` case so one of the three commands cannot silently go unwrapped.

### [NOTE] Smaller inconsistencies and omissions

- **Task 21** names the parameter `head_fallback_sources: tuple[str, ...]` but also writes "`head_fallback_source`" (singular). Use the plural name throughout.
- **Plan entry:** the design says the plan entry is updated to Effort 4/5. Task 29 only checks off 934 in `900-slices.maintenance-and-refactoring.md`. Add a sub-item to confirm the effort and risk text there matches.
- **Task 10:** it is a pure refactor with no new tests. That is acceptable because it relies on the existing run and explain tests, and the new `--dry-run` tests in Task 11 exercise the shared helper. Consider adding a small direct unit test of `_classify_for_run`.

### Run Digest

- Response length: 6093 chars
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
- Duration: 41.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
