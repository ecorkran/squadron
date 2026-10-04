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
aiModel: claude-opus-5-5
status: complete
dateCreated: 20261004
dateUpdated: 20261004
reviewedSha: 777935accef16718eb68ce2eaf0d54fe6e570aa8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 92.7
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Catch-up merge commit makes `existing: keep` see work that isn't there"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:218-225"
  - id: F002
    severity: concern
    category: scope
    summary: "Slice scope is much larger than the architecture's description of 197"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:37-44"
  - id: F003
    severity: concern
    category: architecture-boundary
    summary: "Merging the target into a slice branch is a new git mutation the architecture's rules don't cover"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:223-230"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Item resume has no stated git or checkout precondition before reading cf"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:290-299"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Concurrent or interrupted item resumes are unhandled"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:133"
  - id: F006
    severity: concern
    category: integration
    summary: "Flag kind is classified by step type, not by the failure cause"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:256"
  - id: F007
    severity: concern
    category: integration
    summary: "Exit code 1 means both \"flagged again\" and \"invalid request\""
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:390"
  - id: F008
    severity: concern
    category: dependencies
    summary: "`ItemDecision` placement creates a circular module dependency"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:252"
  - id: F009
    severity: note
    category: integration
    summary: "`report.json` is an external contract with no schema version"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:261-279"
  - id: F010
    severity: note
    category: naming
    summary: "\"Escalation\" means two different things in squadron"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:386"
  - id: F011
    severity: note
    category: design
    summary: "Control flags are passed through the user params namespace"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:306"
  - id: F012
    severity: pass
    category: architecture-boundary
    summary: "Strict target read and the no-force / no-reset / no-delete rules are kept"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:349"
  - id: F013
    severity: pass
    category: complexity
    summary: "Reuses existing machinery instead of adding abstractions"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:313-344"
  - id: F014
    severity: pass
    category: error-handling
    summary: "Failure modes for source evaluation and ordering"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:208-213"
  - id: F015
    severity: pass
    category: nfr
    summary: "NFR restatement"
    location: "unverified"
---

# Review: slice — slice 197

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [FAIL] Catch-up merge commit makes `existing: keep` see work that isn't there

D4 counts a branch as having work when `git rev-list --count {target}..{slice_branch}` is greater than 0. D5 then catch-up merges with `--no-ff`, which always creates a merge commit on the slice branch. That merge commit is reachable from the slice branch and not from the target, so it counts as "ahead".

This breaks a scenario the doc itself describes at lines 491 and 486: an implement dispatch ends with no commits (#163), and the item is flagged `step_failed` on `EmptyDiffError`. If the target then advances (for example, an independent slice merges) and the item is retried:
1. Enter creates the merge commit.
2. The branch now counts as 1 ahead, so the implement dispatch is skipped.
3. The code review finds an empty slice diff, so the item is flagged `step_failed` again.

Every later retry does the same thing. That contradicts D4's promise that "the only way to start over is for the PM to delete or rename the branch". Here the PM has to delete the branch even though there is nothing on it to keep. Retry is the main path in the Amoeba escalation contract, so this needs fixing before implementation.

Possible fixes:
- Measure "work" as `rev-list --count --no-merges {target}..{branch}`, or as a non-empty diff against the merge base.
- Let a branch with no commits of its own fast-forward to the target instead of taking a `--no-ff` merge.

Add a temp-repo test for this case: a branch with no commits, behind the target, then retried.

### [CONCERN] Slice scope is much larger than the architecture's description of 197

The architecture (`180-arch.pipeline-intelligence.md:45`) says "197 composes these into the Phase 6 batch". Its Out of Scope section (line 717) allows grammar changes only for "the general batch-pipeline pieces added by 194–197".

The slice composes the batch, but it also adds several capabilities the architecture never names:
- a new CLI mode, `sq run --resume --item --decision --instructions`
- a persisted, externally consumed report format (`report.json`) with a closed `FlagKind`
- an executor path that reruns a single item of a completed run
- loop `accept_decision` override semantics
- new grammar: `branch: { plan: }` and `existing: keep` on implement
- an inter-system contract with Amoeba

Each piece is justified on its own terms. Taken together, though, the escalation and item-resume work is a major part of the design, and the architecture doesn't record it. Update arch line 45 (and the Scope Boundaries section) to list item resume, structured flags and the Amoeba handoff as 197's deliverables. Otherwise, consider splitting D7–D9 into a follow-on slice.

### [CONCERN] Merging the target into a slice branch is a new git mutation the architecture's rules don't cover

The architecture's Git-Mutating Steps section (lines 47–55) lists only `commit`, `branch enter` and `branch merge`. It describes code as landing on the slice branch and merging back. It also says "A failed merge is aborted back to a clean target."

D5 adds a merge in the opposite direction, from the target into the slice branch. On conflict, it aborts back to the slice branch, not to the target. The project's git rules also only describe merging a slice branch into its target.

Walkthrough step 5 (line 475) leaves the result undecided: "The checkout returns to `main` on the next enter, or stays on the branch for the PM to resolve." For a single-item resume there is no next enter, so the run ends checked out on the slice branch. That breaks the batch invariant at line 134, "a batch ends on the target".

Pick one post-conflict checkout state and write it down: either check out the target after the abort, or explicitly document ending on the slice branch. Also amend the architecture's git section to allow and constrain the catch-up merge.

### [CONCERN] Item resume has no stated git or checkout precondition before reading cf

Several steps read slice and task status from cf, which reads the working tree:
- D8 step 1 re-evaluates the source.
- D8 step 2 checks dependencies "on the target".
- D2's "all tasks checked but slice not marked complete" row depends on that status.

Because of the previous finding, a run can end on a flagged slice branch. A resume started from there would read that branch's checkmarks:
- The flagged item could be misflagged by the all-tasks-checked row.
- A dependency could appear complete when it isn't on the target.

The validation list (lines 290–294) checks the run, the report, the record and the decision, but not the git state. Add a precondition to it: a clean tree, checked out on the target from `read_integration_target`, confirmed with `verify_git_state` before the source is evaluated. On failure, exit with a message.

### [CONCERN] Concurrent or interrupted item resumes are unhandled

Item resume is a read-modify-write of `report.json` (line 300). It also moves shared git and cf state (checkout, `set_arch`). The only guard is a convention, "don't run other cf-consuming commands" (line 135). Amoeba is an unattended caller and could issue decisions for several flagged items in parallel. #146 is excluded only for items inside a batch.

The doc doesn't say what happens:
- if two `--resume --item` processes run against the same run or project, which risks lost report updates and interleaved checkouts
- if a resume is killed partway through the body, leaving the report un-rewritten and the checkout possibly on the slice branch

Specify:
- an exclusive per-project lock, or a refusal when another run or resume is active, with a logged error
- atomic report writes (write to a temp file, then rename)
- the record and checkout state an interrupted resume leaves behind

Also add the "one resume at a time" rule to the escalation contract.

### [CONCERN] Flag kind is classified by step type, not by the failure cause

"A branch step is BRANCH_CONFLICT" labels every branch-step failure as a conflict. That includes:
- a dirty tree on enter
- `resolve_slice_info` failing
- the `set_arch` cf-op added by D6 failing
- a merge precondition failing

This contradicts line 257 ("Every kind is set where the flag is raised"). Amoeba routes on `flagKind` because the reason text isn't meant to be parsed, so a misleading kind sends it the wrong way. Have the branch action report its failure class in its outputs, and map to BRANCH_CONFLICT only for actual merge conflicts, with STEP_FAILED for everything else. Add a test for each.

### [CONCERN] Exit code 1 means both "flagged again" and "invalid request"

The escalation contract says "exit 1 means flagged again". D8 validation failures (lines 290–294) also exit 1, as does accept on the wrong kind (line 412). The doc doesn't say what exit code `GitStateUnknownError` produces.

An automated caller can't tell "the decision was applied and the item failed again" from "the decision was rejected and nothing ran". Treating one as the other leads to wrong retry loops. Use distinct exit codes, for example 0 resolved, 1 flagged again, 2 rejected, plus a code for a halted run. Document them in the contract and in `docs/PIPELINES.md`.

### [CONCERN] `ItemDecision` placement creates a circular module dependency

`BatchItemRecord`, in `batch_report.py`, gains a `decision: ItemDecision` field. But `ItemDecision` is defined in `item_resume.py` (line 289), and `item_resume.py` itself imports `BatchReport` and its records. That makes `batch_report` and `item_resume` depend on each other.

Define `ItemDecision` in `batch_report.py`, next to `FlagKind`, so the dependency runs one way: `item_resume` → `batch_report`.

### [NOTE] `report.json` is an external contract with no schema version

Amoeba, a separate system, will parse this file, and `BatchReport.load` reads back files written by earlier versions. Add a `schemaVersion` field now. That way, later changes to the closed `FlagKind` set or the record shape can be detected instead of misread.

### [NOTE] "Escalation" means two different things in squadron

In the architecture, "Escalation Behaviors" (lines 342–412) means retrying with a stronger model. This slice uses "escalation" for a flag being handed to a human or to Amoeba. Consider calling this one "flag handoff" or "decision contract" in the docs and in `PIPELINES.md`, so the two aren't confused.

### [NOTE] Control flags are passed through the user params namespace

`accept_decision` and `override_instructions` travel in the item params, the same dict that `-p` writes to. Define both keys as constants in one place. Also reject them as user `-p` keys, so a user can't trigger accept by accident.

### [PASS] Strict target read and the no-force / no-reset / no-delete rules are kept

These match the architecture's Git-Mutating Steps section (lines 47–55):
- D4 uses `read_integration_target` and refuses to treat a failed or timed-out `rev-list` as 0.
- D5 merges and never rebases or resets.
- The conventions (line 349) rule out `--force`, reset, rebase, branch deletion and push.
- Unknown git state raises `GitStateUnknownError`, which is logged at ERROR.

### [PASS] Reuses existing machinery instead of adding abstractions

The design avoids adding new machinery where existing pieces work:
- D10 rejects a sub-pipeline or include step and uses a drift test instead.
- D8 reuses `_run_each_item` and the existing `override_instructions` plumbing rather than adding a second carrier.
- D9 rejects a merge-only shortcut.

This fits the architecture's preference that batch phases be expressed as YAML rather than engine changes.

### [PASS] Failure modes for source evaluation and ordering

These failures are explicit and visible:
- A dependency cycle fails the run before any item runs, naming the cycle at ERROR.
- A cf failure fails source evaluation and doesn't degrade to a guess (line 399).
- Out-of-plan dependencies are logged at WARNING.
- Not-ready slices are reported, not dropped.

### [PASS] NFR restatement

The parent architecture states no latency or throughput NFRs for the batch or git paths, so the slice doesn't need to restate any.

### Run Digest

- Response length: 12758 chars
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
- Duration: 92.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15

## Response

All findings accepted and addressed in the design (and the architecture where cited):

- **F001:** `existing: keep` counts `--no-merges` commits (D4). A branch with no work of its own fast-forwards on catch-up instead of taking a merge commit (D5). Covered by a temp-repo test and success criterion 10.
- **F002:** `180-arch` line 45 now lists 197's deliverables: the batch pipeline, structured flags and versioned `report.json`, item resume, and the flag handoff.
- **F003:** the catch-up merge is added to the architecture's Git-Mutating Steps section, along with the rule for where a checkout is left after a failure. After a conflict, the checkout stays on the clean slice branch, the same as any item failure. The next enter or item resume returns to the target. The design's State Management no longer claims a batch always ends on the target.
- **F004:** item resume gains a git precondition before the source is read (D8): restore the target from a flagged slice branch, then require a clean target that passes `verify_git_state`.
- **F005:** D11 adds a per-checkout, non-blocking `flock` run lock, taken by item resume and by code pipelines. Report writes are atomic (temp file plus rename). State Management describes what an interrupted resume leaves behind.
- **F006:** branch actions report a `BranchFailure` class. Only `conflict` maps to `branch_conflict`; everything else is `step_failed` (D7).
- **F007:** `ResumeExit` codes: 0 resolved, 1 flagged again, 2 rejected (nothing ran), 3 halted (D8, and in the contract).
- **F008:** `ItemDecision` moves to `batch_report.py`.
- **F009:** `report.json` gets `schemaVersion: 1`, and loading any other version is rejected.
- **F010:** the design uses "flag handoff" throughout and notes that it is distinct from the architecture's escalation behaviors.
- **F011:** the reserved keys are defined once in `pipeline/control_params.py` and rejected as `-p` keys.
