---
docType: review
layer: project
reviewType: slice
slice: implementation-batch-pipeline-implement-plan
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261004
dateUpdated: 20261004
reviewedSha: 6ed3b49d27b64531233cb1607551484d56d9a4fc
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 51.4
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Git-mutating step rules match the architecture"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md#Technical Decisions (D4, D5, D8)"
  - id: F002
    severity: pass
    category: dependencies
    summary: "Dependency direction and the 140 extension model are respected"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md#Architecture"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "Run lock, single-slice pipeline rewrite and control params aren't in the architecture's 197 scope"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:35-43, 352-394"
  - id: F004
    severity: concern
    category: concurrency
    summary: "The run lock doesn't cover the other mutating batch pipelines"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:389-391"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Report durability and unrun items after a halt or kill are unspecified"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:140, 281, 462"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "No failure-mode enumeration for the new I/O paths, and no observable-signal tests"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:480-492"
  - id: F007
    severity: concern
    category: design
    summary: "Control signals are carried in the user param namespace"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:339, 345"
  - id: F008
    severity: note
    category: nfr
    summary: "The architecture states no NFR for these paths"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md"
  - id: F009
    severity: note
    category: interface
    summary: "The lock-busy exit code differs between commands"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:391"
  - id: F010
    severity: note
    category: integration
    summary: "The Amoeba contract lives in squadron's docs before Amoeba has a document for it"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:436-444"
---

# Review: slice — slice 197

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Git-mutating step rules match the architecture

- **Catch-up:** D5 follows the architecture's catch-up rules. It fast-forwards when the branch has no commits of its own and otherwise merges with `--no-ff`. A conflict is aborted back to a clean slice branch, and the item is flagged. No rebase or reset is used.
- **Item failure:** a failed item leaves the checkout on its slice branch. The next enter or item resume commits the leftovers and returns to the target (D8 precondition).
- **Target and git state:** the target is read strictly, an unknown state raises `GitStateUnknownError`, and nothing is pushed or deleted.

### [PASS] Dependency direction and the 140 extension model are respected

- **Import direction:** `ItemDecision` and `FlagKind` live in `batch_report.py`, and the doc says why, so imports run `item_resume` → `batch_report`.
- **Shared constants:** `control_params.py` is imported by the executor and by dispatch.
- **Batch grammar:** the batch itself is a YAML file composed from 194–196 primitives, as the architecture intends.
- **Term clash:** the flag handoff is explicitly separated from the architecture's "escalation behaviors".

### [CONCERN] Run lock, single-slice pipeline rewrite and control params aren't in the architecture's 197 scope

The architecture's 197 paragraph names five things:
- the ordered source
- `existing: keep` on implement
- `branch: { plan: }`
- `FlagKind` and `report.json`
- `--item` resume

The slice also adds these, and the architecture never mentions them:
- **D11:** a per-project `flock` run lock.
- **D10:** a rewrite of P6, `implement`, P56 and P456 that gives them a new revise loop and new params. This changes the behavior of four existing human-facing pipelines.
- **`StepResult.exhausted`** and the reserved-key mechanism in `control_params.py`.

The architecture says engine changes beyond 194–197's batch pieces are out of scope. The slice should either update the architecture's 197 paragraph or justify each addition against it. D10 carries the most regression risk, because it changes human-operated pipelines.

### [CONCERN] The run lock doesn't cover the other mutating batch pipelines

- **Lock coverage:** the lock is taken only by item resume and by pipelines containing a `branch:` step.
- **Planning pipelines:** `slices-plan` and `tasks-plan` have no `branch:` step. They still commit to the target and move cf's arch, slice and phase, per the slice's own State Management section.
- **The gap:** a planning batch can run alongside an `implement-plan` run or an item resume without taking the lock, which defeats the interleaving protection D11 exists for.
- **Item resume on planning runs:** the Integration Requirements say item resume works on `slices-plan` and `tasks-plan` runs, so these runs do interact with the lock.
- **Fix:** key the lock on "mutates git or cf state" (any git-mutating step), not on the presence of `branch:`.

### [CONCERN] Report durability and unrun items after a halt or kill are unspecified

- **Report timing:** `report.json` is written once, in the batch's `finally`.
- **Killed batch:** a SIGKILL, OOM or machine loss leaves no report. Merged slices and flagged branches then exist with no record, and item resume has nothing to load.
- **Halt on `GitEnvironmentError`:** criterion 6 says a report is written, but it doesn't say how items that never started are represented. They can't be resumed (the resume validation requires a FLAGGED record), and the contract gives Amoeba no signal for them.
- **Resume interrupted after the merge:** a resume killed after `branch merge` but before the report rewrite leaves the report saying FLAGGED for a slice that is now merged. The next resume then fails source re-evaluation with "no longer returned". The doc covers the kill-before-merge case but not this one.

Decide whether to write the report incrementally per item, and add an explicit `not_run` outcome or an equivalent for items cut short by a halt. Define the reconcile path for the post-merge kill case.

### [CONCERN] No failure-mode enumeration for the new I/O paths, and no observable-signal tests

Several failure modes are handled well: the `rev-list` timeout, the catch-up conflict, a held lock and a version mismatch. Other new or newly-exercised paths have no stated hang, timeout or mid-operation-disconnect handling:
- **Implement dispatch:** it can hang, time out or lose its peer mid-send. Only #163 is mentioned, and it's deferred. The mitigation row covers an empty diff, not a hung or crashed dispatch with a partial worktree.
- **D5 catch-up commands:** the `rev-list` count and the `merge` have no timeout or failure handling stated. D4 covers only its own `rev-list`.
- **Report temp-write and rename:** the doc doesn't say what happens on ENOSPC or a rename failure.
- **Lock acquisition:** the doc doesn't cover an unreadable git-dir path or a failing `rev-parse --git-dir`.
- **Observability and tests:** the review rules require each failure mode to be observable (WARNING or above, or a metric) and at least one test to assert that signal. The test list asserts outcomes and exit codes, but not logged or observable signals, apart from the lock's ERROR log.

Add a short failure-mode table covering each new path with its handling, its observable signal and its test.

### [CONCERN] Control signals are carried in the user param namespace

`accept_decision` and `override_instructions` travel in the item params, next to user `-p` values. Rejecting them as `-p` keys protects the CLI entry point. Anything else that builds params, such as a pipeline YAML default or run-state-loaded params, can still set them. D8 also says run-state params are reloaded on resume. Say whether reserved keys are also validated when params come from run state or from a pipeline `params:` block. If they aren't, the accept path depends on a CLI-only guard.

### [NOTE] The architecture states no NFR for these paths

180 has no latency or throughput targets for the batch, resume or report paths, so there is nothing to restate here. The slice's implicit reliability targets are in the success criteria: unattended runs, no partial report reads, and atomic report writes.

### [NOTE] The lock-busy exit code differs between commands

A busy lock exits 2 for item resume and 1 for `sq run`. For `sq run`, 1 may already mean a flagged or failed batch. A caller can't tell "busy, try later" from "ran and flagged" by exit code alone. The slice should confirm this is intentional, or give `sq run` its own code.

### [NOTE] The Amoeba contract lives in squadron's docs before Amoeba has a document for it

The handoff contract is concrete and versioned: a closed `FlagKind`, `schemaVersion`, and exit codes 0, 1, 2 and 3. That reduces drift risk. Squadron doesn't depend on Amoeba, so the dependency direction is correct. Keep the PIPELINES.md copy in sync with amoeba#1.

### Run Digest

- Response length: 8494 chars
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
- Duration: 51.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Response

- **Scope vs architecture (CONCERN): partly valid.**
  - The run lock and the single-slice refresh are now listed in `180-arch` 197's paragraph.
  - False positive in part: D10 is in the slice plan entry itself ("refreshes the single-slice `slice.yaml` onto the 195/196 machinery … so the one-slice and whole-plan paths share steps").
  - `StepResult.exhausted` and `control_params.py` are implementation details, not architecture scope.
- **Run lock coverage (CONCERN): valid.** The lock is now taken by any pipeline that commits or moves cf: phase steps, `devlog`, `branch`, or a loop with `commit_each_iteration`. That includes `slices-plan` and `tasks-plan` (D11).
- **Report durability (CONCERN): valid.**
  - The report is rewritten atomically after every item.
  - A halt records the in-flight item as FLAGGED and every unreached item as the new `not_run` outcome. `not_run` can be resumed with `retry`.
  - A resume killed after the merge reconciles to PASSED when the slice is complete on the target and its branch is merged (D7, D8).
  - A batch killed outright loses only the in-flight item's record, and a rerun reselects that item from repository state.
- **Failure-mode enumeration (CONCERN): valid.** New D12 table: each new path gets its handling and log signal, and each row gets a test asserting the log record. A hung implement dispatch is honestly marked as not bounded by this slice (#165, #163).
- **Control params outside the CLI (CONCERN): valid.** Reserved keys are now also rejected in a pipeline `params:` block. Item resume strips them, with a WARNING, from params loaded out of run state, so an earlier checkpoint's instructions can't carry into a new decision.
- **Lock-busy exit code (NOTE): valid.** A busy lock now exits 2 for both item resume and `sq run`.
- **NFR (NOTE), contract location (NOTE):** no change. The PIPELINES.md copy is tracked against amoeba#1.
