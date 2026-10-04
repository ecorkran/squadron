---
docType: review
layer: project
reviewType: code
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
reviewedSha: f588c3f02c963cd17b2fde44586af2b44d71a64c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: true
durationSeconds: 43.6
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "CommitAction._planned catches bare ValueError, which hides internal faults as item failures"
    location: "src/squadron/pipeline/actions/commit.py#CommitAction._planned"
  - id: F002
    severity: concern
    category: error-handling
    summary: "list_worktrees can leak KeyError and AttributeError instead of ContextForgeError"
    location: "src/squadron/integrations/context_forge.py#ContextForgeClient.list_worktrees"
  - id: F003
    severity: concern
    category: error-handling
    summary: "round_commit_params can raise KeyError that the executor does not catch"
    location: "src/squadron/pipeline/loop_commit.py#round_commit_params"
  - id: F004
    severity: concern
    category: performance
    summary: "require_known_model reloads aliases on every resolution"
    location: "src/squadron/models/aliases.py#require_known_model"
  - id: F005
    severity: concern
    category: documentation
    summary: "Detached comment in classification.py"
    location: "src/squadron/pipeline/classification.py:40-50"
  - id: F006
    severity: concern
    category: correctness
    summary: "Rich markup injection when printing exception text"
    location: "src/squadron/cli/commands/run.py (GitEnvironmentError handler in `_run_pipeline_sdk`)"
  - id: F007
    severity: note
    category: design
    summary: "Wider CfClientProtocol and concrete run_git use"
    location: "src/squadron/review/persistence.py#CfClientProtocol"
  - id: F008
    severity: note
    category: design
    summary: "Function-level imports used to avoid cycles"
    location: "src/squadron/pipeline/commit_plan.py#build_commit_plan"
  - id: F009
    severity: note
    category: process
    summary: "Review coverage"
    location: "unverified"
  - id: F010
    severity: pass
    category: testing
    summary: "Failure-mode handling, tests and parity"
    location: "src/squadron/pipeline/branch_ops.py"
---

# Review: code — slice 196

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5
**Diff:** truncated: 256000 of 333028 characters reached the model

## Findings

### [CONCERN] CommitAction._planned catches bare ValueError, which hides internal faults as item failures

`except (ValueError, FileNotFoundError, ContextForgeError)` turns any `ValueError` into a failed `ActionResult`, logged at WARNING. That includes bugs such as the `int(target.plan)` conversion in `_architecture_candidates`, or a malformed frontmatter value. `BranchAction` is stricter. It catches named subclasses (`NoDesignFileError`, `SliceNotInPlanError`, `MergeFailedError`), and `test_action_lets_an_unrelated_value_error_end_the_run` pins that behavior. `CommitAction` should do the same, with dedicated item-failure exception types. A batch would otherwise flag and continue past a programming error, and the error would be logged without a traceback.

### [CONCERN] list_worktrees can leak KeyError and AttributeError instead of ContextForgeError

It indexes `e["worktreePath"]` and calls `e.get(...)` on each entry after only checking that `worktrees` is a list. An entry that is missing `worktreePath`, or is not a dict, raises `KeyError` or `AttributeError`. `_require_registered_worktree` only handles `ContextForgeError` and `ContextForgeNotAvailable`, so malformed cf output would escape as an untyped crash. Validate each entry and raise `ContextForgeError`, as the method already does for a missing list. Add a test for it.

### [CONCERN] round_commit_params can raise KeyError that the executor does not catch

`str(resolved["template"])` raises `KeyError` if the last review action's config has no `template`. `_execute_loop_body` only catches `CommitScopeUnknownError` and `UnmappedTemplateError`. Use `.get` and raise `CommitScopeUnknownError` with a clear message, which makes it a visible per-round failure.

### [CONCERN] require_known_model reloads aliases on every resolution

It calls `get_all_aliases()` on each invocation. It now runs inside `_resolved`, which runs on every `ModelResolver.resolve`. It also runs once per candidate in `classify_pipeline`. If `get_all_aliases` reads `models.toml` from disk each time, that is repeated blocking I/O on async paths. I did not inspect `get_all_aliases`. Confirm it is cached, or pass the alias map in.

### [CONCERN] Detached comment in classification.py

`PROFILE_PARAM` and `has_profile_param` were inserted between the comment block explaining `_MODEL_DISPATCHING_ACTION_TYPES` and the constant itself. The comment now sits above unrelated code. Move the new definitions above that comment block.

### [CONCERN] Rich markup injection when printing exception text

`rprint(f"[red]Error: {exc}[/red]")` interpolates git and cf text, such as paths and conflict lines. Text containing `[...]` can be swallowed or misrendered as markup. Use `rich.markup.escape(str(exc))`. `review.py` has the same pattern with `UnknownModelAliasError`, though that message is less likely to contain brackets.

### [NOTE] Wider CfClientProtocol and concrete run_git use

The protocol gained `get_config` and `list_worktrees`. `resolve_slice_info` needs neither, so every fake must now implement both (ISP). The branch and commit modules also import `run_git` directly, and the tests monkeypatch it per module (DIP). This is consistent with the existing codebase, but an injected git runner would remove that patching.

### [NOTE] Function-level imports used to avoid cycles

`build_commit_plan`, `_slice_candidates`, `_kept_artifact_paths` and `_summarize_action_config` all import inside the function body to break cycles. Examples are `commit_message` ↔ `commit_plan`, and `dispatch` → `events.builtin`. Moving `StagedFacts` and `ArtifactChange` into a leaf module would remove the first cycle.

### [NOTE] Review coverage

The diff was cut off partway through `tests/pipeline/test_commit_plan_builder.py`. Later test files and any other source after that point were not reviewed.

### [PASS] Failure-mode handling, tests and parity

Timeouts and refusals are classified as item failure, environment fault or `GitStateUnknownError`. Each is logged, and each has a test asserting the observable signal. The CLI and action parity tests, the halt-still-writes-report test and the real-repo composition tests give good coverage.

### Run Digest

- Response length: 5500 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 43.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Response

Origin: **original** means the code was in the slice before the first review (`a273241a`). **Update** means it came from the fixes made in response to that review (`f588c3f0`).

- **F001 — valid, original; fixed.**
  - `build_commit_plan` raises a new `CommitTargetError` when a commit is missing its slice or plan, and when the plan is not a number. cf's "slice not in plan" `ValueError` is wrapped in `SliceNotInPlanError`.
  - `CommitAction._planned` catches only those two, `FileNotFoundError` and `ContextForgeError`. Any other `ValueError` propagates.
  - Tests: a slice missing from the plan, a non-numeric plan, and an unrelated `ValueError` propagating.
- **F002 — valid, original; fixed.** `list_worktrees` raises `ContextForgeError` for an entry that is not a dict or has no `worktreePath`. A parametrized test covers both.
- **F003 — invalid, original.** `ReviewAction.validate` rejects a `review` action with no `template` ("'template' is required for review action") at pipeline load. So the resolved config that `round_commit_params` reads always has the key.
- **F004 — invalid as a slice 196 concern, original.** `resolve_model_alias` already called `get_all_aliases()` on every resolve before this slice. `require_known_model` adds one more read of the same two small TOML files per resolve. Caching aliases would change how existing code picks up `models.toml` edits, and that change belongs outside this slice.
- **F005 — valid, update; fixed.** `PROFILE_PARAM` and `has_profile_param` now sit above the `_MODEL_DISPATCHING_ACTION_TYPES` comment block, so that comment is next to its constant again.
- **F006 — valid, original; fixed.**
  - The `GitEnvironmentError` handler in `run.py` and `_reject_unknown_alias` in `review.py` now print `escape(str(exc))`.
  - The run test is parametrized with a message containing `[bold]…[/bold]`, which must print literally.
- **F007 — repeat of the first review's F007, original; declined.** The reasoning is in the archived first review's response. The `run_git` injection point follows the existing review modules and is not new to this slice.
- **F008 — note, original (one import added in the update); no change.** The function-level imports follow the existing cycle-breaking pattern in `pipeline/`. Moving `StagedFacts` and `ArtifactChange` into a leaf module is a refactor with no behavior change, so it is left out here.
- **F009 — note; no action.** The diff was truncated at `tests/pipeline/test_commit_plan_builder.py`. Everything after that point is tests, and those pass (3730 passed, 4 skipped across pipeline, cli, review, models, events and integrations).
