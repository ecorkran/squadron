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
reviewedSha: 9b2dbeceb1d6f180b15bfe0b54078bda1928ae3f
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 39.3
runId: run-20261007-p5-56b33e7c
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: design-consistency
    summary: "Task 22a contradicts D10 on ancestry-check timeout handling"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:227"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Task 22a does not say where `head_fallback_sources` enters `fetch_and_range`"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:214"
  - id: F003
    severity: note
    category: task-scoping
    summary: "Task 25a bundles three independent changes"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:265-271"
  - id: F004
    severity: note
    category: task-scoping
    summary: "Task 11 mixes dry-run classification with a real-run artifact-integrity test"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:119-125"
  - id: F005
    severity: note
    category: coverage
    summary: "Walkthrough step 4's live GHE confirmation is omitted"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:306"
  - id: F006
    severity: note
    category: nfr-coverage
    summary: "No NFR restated in the slice, so no load-test or CI-gating task is required"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria traceability and scope"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit distribution"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md"
---

# Review: tasks — slice 934

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 22a contradicts D10 on ancestry-check timeout handling

Task 22a's tests say "ancestry timeout and non-0/1 exit answer 'no' with the existing WARNING, giving the same error." The slice design's D10 table (slice design line 294) splits these two cases:
- `ProcessTimedOutError` on `merge-base --is-ancestor` → `HostCommandTimeoutError`.
- Exit not in (0, 1) → answered no, which is the existing fail-closed behavior.

No task converts the ancestry timeout to `HostCommandTimeoutError`. Task 20 covers only the primary fetch, Task 21 `cat-file`, and Task 22b `update-ref`. The success criterion "A fetch timeout … never escapes as a traceback" is therefore at risk for this call. Fix by adding the timeout conversion and a timeout-specific test to 22a, or by revising D10 if "answer no" is the intended behavior.

### [CONCERN] Task 22a does not say where `head_fallback_sources` enters `fetch_and_range`

Task 21 introduces `head_fallback_sources` as an argument of the new helper. Task 23 passes it from the GitHub adapter into `fetch_and_range`. Neither task, nor 22a, states that `fetch_and_range` gains this parameter or threads it through to the helper. 22a is the first caller, so it is the natural place. A junior implementer could either invent a default (a silent fallback the project forbids) or leave a gap between 22a and 23. Make 22a add a required parameter and update its existing callers and tests.

### [NOTE] Task 25a bundles three independent changes

Task 25a does three things in one commit:
- prints adjustment lines in two commands,
- changes the PR review artifact provenance, and
- re-tags the Task 19 and 22b warnings.

The provenance change is the least specified: no file or field is named, and "existing provenance" is not located. It is still completable, but splitting provenance into its own task would make 25a's success criteria sharper. Add a `grep` hint for the provenance writer, as other tasks do.

### [NOTE] Task 11 mixes dry-run classification with a real-run artifact-integrity test

This task has two behaviors: dry-run/`--strict` handling, and a real run that must leave the slot's review artifact byte-identical. The second one traces to a success criterion, so it is not scope creep. It could sit in Task 10 or in its own test step, because it exercises the real-run path, which Task 10 already refactors. Optional.

### [NOTE] Walkthrough step 4's live GHE confirmation is omitted

Task 28 runs the unit-fixture form of step 4 only. The slice design's optional live check on a lagging host is not mentioned. The design says that case cannot be produced on demand, so this is acceptable. A one-line DEVLOG note that the live check was not run would match how Task 28 handles step 2.

### [NOTE] No NFR restated in the slice, so no load-test or CI-gating task is required

The slice restates no performance or throughput NFR. The predicate's call count (one `for-each-ref`, one `rev-list`, N `is-ancestor`) is a design property, not a stated NFR. The load-test and CI-wiring checks do not apply.

### [PASS] Success criteria traceability and scope

Every criterion maps to a task:
- **#188:** Tasks 13–16, including the `cwd`-different-from-process test (15) and the D10 failure rows (13).
- **#184 / #175:** Tasks 2–11, including the parity test (6), unknown-template pre-run failure (7–8), `_classify_for_run` (10), and `--dry-run` / `--strict` (11).
- **#186:** Tasks 18–25c, including the absent-locally fixture (21, 22a), source-naming errors (18), render-once logging (24a–25c), and the primary-fetch timeout (20).

No task falls outside a decision or criterion. Task 7's refactor is required by D4. The "no `"sdk"` literal" and "no second cascade" criteria are enforced by greps in Tasks 3 and 5.

### [PASS] Sequencing, test-with pattern and commit distribution

No circular dependencies; each task builds on earlier ones:
- 2 → 3, 5.
- 4 → 5.
- 7 → 8 → 9.
- 13 → 15, 16.
- 18 → 19–22.
- 21 → 22a → 22b → 23.

Tests ship in the same task as their implementation. Every task ends with its own semantic commit, and each part closes with a validation task. The staging of the `RENDERED_BY_CALLER` tag (inert until 25b/25c, with adjustment tags deferred to 25a so no run has a tag without its printed line) is deliberate and explained. The merge is correctly excluded from the task list per the Git Rules.

### Run Digest

- Response length: 6019 chars
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
- Duration: 39.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
