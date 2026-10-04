---
docType: review
layer: project
reviewType: slice
slice: pipeline-branch-steps-scoped-commits-and-dependency-aware-batches
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261004
dateUpdated: 20261004
reviewedSha: a88eb56b152e8571d21cb16f6b6f63370f1e1b69
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 45.2
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Git-mutating steps follow the architecture's rules"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#D5-branch-enter"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with observable handling"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#D6-branch-merge"
  - id: F003
    severity: concern
    category: integration
    summary: "Item failure at merge or implement leaves the checkout off-target, so the \"clean-target-on-failure\" guarantee to 197 doesn't hold"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#Provides-to-Other-Slices"
  - id: F004
    severity: concern
    category: scope
    summary: "Scope extends past the architecture's description of slice 196"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#Technical-Scope"
  - id: F005
    severity: concern
    category: integration
    summary: "New load-time rule for `implement` may break other pipelines, and its scope is under-specified"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#D4-branch-step-type"
  - id: F006
    severity: concern
    category: architecture-alignment
    summary: "Planning commits aren't verified to be on the target"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#D8-planning-commits-stay-on-the-target"
  - id: F007
    severity: note
    category: dependency-direction
    summary: "Git state helpers placed in the `review` package"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#Component-Structure"
  - id: F008
    severity: note
    category: under-specification
    summary: "Default target value and deferred verification are underspecified"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md#D13-175-unknown-aliases-fail-before-the-run"
---

# Review: slice — slice 196

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Git-mutating steps follow the architecture's rules

The architecture requires a strict target read, planning commits on the target, and code on `{index}-slice.{name}` merged with `--no-ff`. It also requires scoped staging except for code on its slice branch, no force, reset, delete or push, abort on a failed merge, and a halt when state can't be verified. D3, D5, D6, D8 and the "Patterns and Conventions" section implement each of these. `resolve_diff_base`'s degrade-to-main behavior is explicitly not reused for write paths. That honors the "failed read never becomes `main`" rule.

### [PASS] Failure modes are enumerated with observable handling

Every git I/O path has an explicit outcome:
- **Environment failures** raise `GitEnvironmentError` and end the run.
- **Item failures** are distinguished from environment failures.
- **`run_git` timeouts** go to `verify_git_state` and raise `GitStateUnknownError` when the state can't be verified.
- **`merge --abort` failures** are handled.
- **Commit timeouts** are treated as unknown state.
- **Batch report on halted runs:** it is written in a `finally`.

The Technical Requirements ask for tests that assert the ERROR log for these paths. No NFR is defined in the parent architecture for these paths, so there is nothing to restate.

### [CONCERN] Item failure at merge or implement leaves the checkout off-target, so the "clean-target-on-failure" guarantee to 197 doesn't hold

"Provides to Other Slices" promises 197 a clean target on failure, and the Integration Requirements say 197 can compose `each` → enter → implement → review loop → merge "with no engine changes". The design doesn't deliver this.
- An implement or review failure, a checkpoint pause, or a failed devlog commit skips `branch merge`, so the item is FLAGGED with the checkout still on the slice branch.
- A dirty-tree or wrong-branch failure at D6 step 3 is an item failure that also leaves the checkout on the slice branch.
- The next independent item's `branch enter` then finds the current branch is neither the target nor its own slice branch (D5.4) and raises `GitEnvironmentError`. That halts the whole batch.

This contradicts D10's "independent items run" and the architecture's intent that a flagged slice stops only its dependents. Only the merge-conflict path returns to the target (D6.6).

The slice should either:
- return to the target on item failure (a cleanup in `each`, or an `on-fail` branch step), or
- state that enter must accept an unmerged slice branch, or
- state plainly that 197 owns this.

Add a success criterion for a flagged item followed by an independent item in a branch-composed batch.

### [CONCERN] Scope extends past the architecture's description of slice 196

The architecture lists 196 as `branch:`, scoped commits, dependency flags in `each`, and `existing: keep`. This slice adds:
- the `tasks-plan` re-review source rename (D11),
- #152 truncation imposition in `review/coverage.py`,
- #175 alias validation across `models/aliases.py`, `classification.py`, the resolver and `cli/commands/review.py`,
- #179 `-v` labels.

The latter three are review and model-resolution integrity fixes touching modules outside the batch-pipeline engine. The slice itself calls the work "six independent fixes" and raises the effort to 4/5. They are individually small and justified. But the architecture's scope boundary allows 194–197 only "general batch-pipeline pieces". Either update the architecture's 196 bullet and Out of Scope exception to cover these, or split them into a separate slice. Otherwise the documents drift.

### [CONCERN] New load-time rule for `implement` may break other pipelines, and its scope is under-specified

D4 makes any `implement` step without a preceding `branch: {op: enter}` in the same step list fail `validate_pipeline`. Only P6, P456, P56 and `implement.yaml` are updated. The slice doesn't enumerate:
- other built-in pipelines that contain `implement` steps,
- user pipelines,
- `implement` steps nested in `loop:` or `each:` bodies, where "same step list" is ambiguous.

This is a breaking grammar change that the slice doesn't inventory. Add an audit of built-in and user pipelines, define how nesting is treated, and state migration or compatibility handling.

### [CONCERN] Planning commits aren't verified to be on the target

The architecture says planning commits land on the target. D3 verifies the branch only for CODE `stage_all`. A P4/P5 or P456 planning commit runs on whatever branch is checked out. If the checkout is left on a slice branch (see the first CONCERN), a design or tasks commit would silently land there. This is the same class of hazard the guard in D3 prevents for code. Add a branch check, even if only a WARNING or a refusal, to the DESIGN, TASKS and ARCHITECTURE commit paths.

### [NOTE] Git state helpers placed in the `review` package

`read_integration_target`, `verify_git_state` and `GitEnvironmentError` are added to `review/git_utils.py`, but they serve write operations in pipeline actions and the new CLI commands. The dependency direction (pipeline → review) is acceptable. Still, write-side git state doesn't belong to the review domain, and `GitEnvironmentError` propagating out of `execute_pipeline` makes it an engine-level contract. Consider a neutral location such as `pipeline/git/` or a shared git module.

### [NOTE] Default target value and deferred verification are underspecified

- **Default target:** the `main` default for an unset `git.integration_branch` is architecture-sanctioned. It should be defined once as a constant, per the project's no-scattered-values rule.
- **Deferred params check:** D13 defers confirming that the classifier resolves placeholders against merged params to "the task breakdown". Success criterion 11 depends on it, so the check should be settled in the design or marked as a known risk.

### Run Digest

- Response length: 7618 chars
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
- Duration: 45.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Origin key: **revision** means it was introduced by the round-1 fix (`a88eb56b`). **original** means it was already in the first design (`5046f562`), and this round's reviewer found it where round 1 didn't.

- **F003, off-target after an item failure. Origin: original, made worse by the revision.**
  - The gap existed in `5046f562`: a failed implement left the checkout on the slice branch, and the next enter rejected it. Back then, every later item would have been flagged.
  - Round 1 made a wrong-branch enter halt the run, so the same gap now stopped the whole batch.
  - Fixed in D5.4. If enter finds another slice's branch, it commits that branch's leftovers as `chore: preserve uncommitted work on flagged slice {m}` (`stage_all` is allowed there, per D3), returns to the target with a WARNING, and continues. Any other branch still halts.
  - "Provides to Other Slices" now states what 197 actually gets, and success criterion 7a covers a flagged item followed by an independent one.
- **F004, scope beyond the architecture. Origin: revision.**
  - The 196 bullet I added to 180-arch in round 1 listed only the grammar pieces.
  - Fixed by extending that bullet. It now covers the tasks re-review selection and the #152, #175 and #179 review-trust fixes, and notes they add no grammar and change no review model.
  - Not split into another slice: the slice plan has scoped them to 196 since 20261003.
- **F005, the implement validation rule. Origin: original.**
  - Fixed in D4. The rule now covers nesting (an enter counts if it's earlier in the implement's list, or in any enclosing list before its container).
  - The only built-in pipelines with `implement` steps are P6, P456, P56 and `implement`, and all four are updated. That's checked against `src/squadron/data/pipelines/`.
  - User pipelines break on purpose, with a message that names the fix, plus CHANGELOG and PIPELINES.md notes. There's no compatibility flag.
- **F006, planning commits not verified on the target. Origin: original.**
  - Fixed in D8. Commits other than code must be on the target, or (for DEVLOG only) on their own slice branch. Anything else raises `GitEnvironmentError`. Success criterion 7b covers it.
- **F007, git helpers in `review/`. Origin: revision** for `verify_git_state` and the errors, which round 1 added; **original** for `read_integration_target`.
  - Fixed: they move to a new `pipeline/git_ops.py`. `run_git` stays where it is.
- **F008, the default constant and the deferred params check. Origin: original.**
  - The default branch is now `DEFAULT_DIFF_BASE`, imported and not respelled.
  - The params question is settled. `classify_pipeline` resolved placeholders against YAML defaults only (`run.py:325`, `run.py:504`), so a mistyped `--param review-model=…` would have slipped through. It now takes the merged params. Success criterion 11 includes the `--param` case.
