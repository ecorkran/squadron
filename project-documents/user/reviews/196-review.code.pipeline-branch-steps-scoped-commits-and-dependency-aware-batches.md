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
aiModel: claude-opus-5-5
status: complete
dateCreated: 20261004
dateUpdated: 20261004
reviewedSha: a273241af356a4584c2b792932abd232f7a6fba0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
diffTruncated: true
durationSeconds: 89.3
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: concern
    category: async-correctness
    summary: "Synchronous git and cf subprocesses run inside `async def execute` on the event loop"
    location: "src/squadron/pipeline/actions/branch.py:28-56"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`existing: keep` pre-check can raise past the dispatch action and end the run"
    location: "src/squadron/pipeline/actions/dispatch.py#_kept_artifact_paths"
  - id: F003
    severity: concern
    category: correctness
    summary: "Pipeline alias check counts fewer profile sources than `sq review`, so the two can disagree"
    location: "src/squadron/pipeline/resolver.py:70-78"
  - id: F004
    severity: concern
    category: interface-parity
    summary: "Prompt-only mode can no longer render the explicit `paths` + `message` commit that SDK mode supports"
    location: "src/squadron/pipeline/prompt_renderer.py#_render_commit"
  - id: F005
    severity: concern
    category: error-handling
    summary: "`BranchAction` turns every `ValueError` into an item failure, including internal faults"
    location: "src/squadron/pipeline/actions/branch.py:49-54"
  - id: F006
    severity: concern
    category: design/DRY
    summary: "Template names and param keys are hard-coded in several places"
    location: "src/squadron/pipeline/commit_plan.py:60-66"
  - id: F007
    severity: concern
    category: design/ISP
    summary: "`CfClientProtocol` is widened for every client, though only the branch code needs the new methods"
    location: "src/squadron/review/persistence.py:55-62"
  - id: F008
    severity: note
    category: fail-fast
    summary: "CODE placement check passes when no slice is given"
    location: "src/squadron/pipeline/actions/commit.py#_check_placement"
  - id: F009
    severity: note
    category: error-handling
    summary: "SHA lookup returns the placeholder `\"unknown\"` and ignores git's exit code"
    location: "src/squadron/pipeline/actions/commit.py#_stage_and_commit"
  - id: F010
    severity: note
    category: error-handling
    summary: "Deleted review files and design files that cannot be read"
    location: "src/squadron/pipeline/commit_plan.py#read_review_verdict"
  - id: F011
    severity: note
    category: error-handling
    summary: "The `finally` block that writes the report can hide the original exception"
    location: "src/squadron/pipeline/executor.py#_execute_each_step"
  - id: F012
    severity: note
    category: structure
    summary: "Several functions are well over the size guideline"
    location: "src/squadron/pipeline/executor.py#_execute_each_step"
  - id: F013
    severity: pass
    category: correctness
    summary: "The strict git state model is well designed and tested"
    location: "src/squadron/pipeline/git_ops.py"
  - id: F014
    severity: pass
    category: design
    summary: "Commits stage only the planned paths, and both modes share one builder"
    location: "src/squadron/pipeline/commit_plan.py#build_commit_plan"
---

# Review: code — slice 196

**Verdict:** CONCERNS
**Model:** claude-opus-5-5
**Diff:** truncated: 256000 of 320270 characters reached the model

## Findings

### [CONCERN] Synchronous git and cf subprocesses run inside `async def execute` on the event loop

`BranchAction.execute` calls `enter_slice_branch` and `merge_slice_branch` directly. These run synchronously and make many `run_git` subprocess calls: rev-parse, status, checkout, merge, merge-base, and the abort/verify path. They also call cf (`list_worktrees`, `get_config`, `list_slices`). `CommitAction.execute` (`src/squadron/pipeline/actions/commit.py`) does the same through `_check_placement`, `build_commit_plan` and `_stage_and_commit`. The new dispatch pre-check `_kept_artifact_paths` (`src/squadron/pipeline/actions/dispatch.py`) runs a cf subprocess before the model call. Each call can block for up to the `run_git` timeout. That breaks the rule that sync work inside an `async def` must take under 1 ms. The executor already offloads the batch-report write with `asyncio.to_thread` (`_write_each_report`), so the same pattern fits here: `await asyncio.to_thread(enter_slice_branch, ...)` and the equivalents for the commit plan and staging.

### [CONCERN] `existing: keep` pre-check can raise past the dispatch action and end the run

`_kept_artifact_paths` runs at the top of `DispatchAction.execute`, outside any try. Three things in it can raise:
- `parse_slice_index` raises `ValueError` when `slice` is unresolved or is a whole `each` record.
- `expected_artifact_paths` raises `ValueError` or `TypeError` when cf cannot resolve the slice. Its docstring says the caller should treat this as "path unresolvable".
- `ArtifactKind(...)` raises `KeyError` or `ValueError` when the param is missing.

None of these become a failed `ActionResult`. So a slice that cf cannot resolve stops the whole batch instead of flagging one item. That is the opposite of the item/run split this slice sets up everywhere else. Catch the expected exceptions, return `success=False` with the message, and log at WARNING.

### [CONCERN] Pipeline alias check counts fewer profile sources than `sq review`, so the two can disagree

`_resolved` now calls `require_known_model(alias, profile_source=self._profile_source)` on every resolve. Every caller in `run.py` sets `profile_source="profile" in params`. `sq review` (`src/squadron/cli/commands/review.py#_reject_unknown_alias`) also counts `template.profile` and the `default_review_profile` config as profile sources.

Here is the case that breaks. A user has `default_review_profile` set, or a review template that declares a profile, and uses a literal model id. `sq review` accepts it. The same model in a pipeline `review:` step is rejected by the classifier, and the resolver backstop rejects it at run time too. The test `test_message_matches_the_pipeline_pre_run_check` checks that the error messages match, but not that the two accept the same inputs. Put the "is there a profile source" decision in one shared helper and use it on both paths.

### [CONCERN] Prompt-only mode can no longer render the explicit `paths` + `message` commit that SDK mode supports

`CommitAction` still accepts a user-pipeline commit with explicit `paths` and `message` (`_explicit_plan`). `_render_commit` raises `ValueError` whenever `commit_subject` is missing. A user pipeline that works under the SDK executor therefore fails to render with `--prompt-only`. Old pipelines that set only `message_prefix` now fail differently in each mode: an item failure in SDK mode, a render crash in prompt-only. Either give `sq _commit` `--path`/`--message` options or reject such commits at load time in both modes. Add a test that pins down whichever behaviour you pick.

### [CONCERN] `BranchAction` turns every `ValueError` into an item failure, including internal faults

The `except ValueError` is meant for `NoDesignFileError`, `MergeFailedError` and "slice not in plan". It also catches unrelated `ValueError`s. One example: in `_require_registered_worktree` (`src/squadron/pipeline/branch_ops.py`), `git_dir, common_dir = dirs.splitlines()` raises an unpacking `ValueError` if git's output has an unexpected shape. That is an environment fault, but it would be reported as one flagged item and the batch would continue.

`TypeError` from `resolve_slice_info` (documented in `artifact_paths.py`) is not caught by `_slice_facts` or the action at all. Catch the specific item-failure types, and wrap the `resolve_slice_info` `ValueError`/`TypeError` explicitly.

### [CONCERN] Template names and param keys are hard-coded in several places

The review template names `"slice"`, `"tasks"`, `"code"` and `"arch"` are written out in at least three places:
- `_SUBJECT_BY_TEMPLATE` in `commit_plan.py`
- `_DESIGN_REVIEW_TEMPLATE = "slice"` and `_TASKS_REVIEW_TEMPLATE = "tasks"` in `src/squadron/pipeline/sources.py`
- the phase-step review defaults

`SLICE_PARAM` is defined, but `dispatch.py` (`context.params.get("slice")`), `steps/branch.py` (`"slice"`, `"op"`, `_ALLOWED_KEYS`) and `branch_run.py` still use the bare strings. `"profile" in params` is repeated six times in `cli/commands/run.py`. CLAUDE.md says to define a comparison value once and reference it everywhere. Use one template-name enum and a single source for the param keys.

### [CONCERN] `CfClientProtocol` is widened for every client, though only the branch code needs the new methods

`get_config` and `list_worktrees` are added to the protocol that `resolve_slice_info` and many other callers use. Neither method is needed for slice resolution, yet every fake and implementation of the protocol must now provide both. `git_ops.ConfigReader` already shows the narrower approach. Define a small `WorktreeLister` (or `BranchCfClient`) protocol for `branch_ops` and leave `CfClientProtocol` as it was.

### [NOTE] CODE placement check passes when no slice is given

When `target.slice_index is None`, `on_slice == target.slice_index` evaluates `None == None`. That is true on `main` or any other non-slice branch, so placement passes. The commit is only stopped because `_candidates` later calls `_slice_name`, which raises through `_require_slice`. The guard should fail on its own terms: reject CODE without a slice index in `_target_from_params` or at the top of `_check_placement`.

### [NOTE] SHA lookup returns the placeholder `"unknown"` and ignores git's exit code

`sha = sha_result.stdout.strip() if sha_result else "unknown"` uses an obvious placeholder, which is acceptable. But it never checks `returncode`, so a failed `rev-parse` produces an empty SHA and no log line. Log a WARNING when the commit succeeded but the SHA could not be read.

### [NOTE] Deleted review files and design files that cannot be read

- A deleted review file shows as dirty (`_Dirty.CHANGED`), so `read_review_verdict` calls `read_frontmatter`, which calls `path.read_text`, which raises `FileNotFoundError`. `_planned` turns that into an item failure, so a legitimate deletion makes the commit fail. Check `is_file()` first.
- In `sources.py#_design_dependencies`, `read_frontmatter` can raise `UnicodeDecodeError` or `OSError`, and nothing catches it there. One bad design file would abort source evaluation for the whole batch.

### [NOTE] The `finally` block that writes the report can hide the original exception

Writing the report in `finally` is the right call: it meets D9 even when the run halts. But if `_write_each_report` raises during a `GitEnvironmentError` unwind (disk full, permissions), its exception replaces the git fault. Wrap the write in the `finally` path so a write failure is logged with `logger.exception` and the original error still propagates.

### [NOTE] Several functions are well over the size guideline

`_execute_each_step` and `CommitAction.execute`/`_check_placement` exceed the ~50-line guideline. `commit_plan.py` is at the ~300-line limit. Two candidates to pull out: dependency flagging into the existing `_dependency_flag_reason`, and the halted-item record into a helper.

### [PASS] The strict git state model is well designed and tested

- `read_integration_target` refuses to fall back to `main` when cf fails.
- `verify_git_state` treats an unreadable state as unknown.
- `GitStateUnknownError` is a subclass of `GitEnvironmentError`, so callers that halt on environment faults also halt on unknown state.
- A failed merge is aborted back to a clean target, and the error reports git's CONFLICT lines.

The tests use real temp repos, not mocks, for the guards, timeouts, abort failure, worktree registration and the full P6 run. Each failure mode is asserted to log at ERROR or WARNING. This meets the failure-mode enumeration rule.

### [PASS] Commits stage only the planned paths, and both modes share one builder

- Candidate paths are computed, never searched for.
- `-z -uall` porcelain parsing handles renames and files inside untracked directories.
- Archived prior reviews are matched by exact stem, so a longer stem like `105-review.slice.batch-foo-longer.md` is not swept in. A test covers this.
- `git commit -- <paths>` keeps content the operator already staged out of the commit.
- Parity tests compare `sq _commit` and `sq _branch` against the actions on identical repos.

### Run Digest

- Response length: 10851 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 89.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Response

- **F001 — fixed.** `BranchAction`, `CommitAction` and dispatch's `existing: keep` pre-check now run their git and cf work through `asyncio.to_thread`. The executor awaits actions one at a time, so no state is shared across threads.
- **F002 — not a defect.** `_kept_artifact_paths` runs inside `_dispatch`. `execute` wraps `_dispatch` in an `except Exception` that returns `success=False`, so the run does not end. It becomes an item failure, logged at ERROR.
- **F003 — declined; filed as #184.** A pipeline `review:` step never reads `template.profile` or `default_review_profile`. The pipeline check therefore accepts exactly what the pipeline will dispatch. Matching `sq review`'s inputs would let a literal id through on a profile the run then ignores. The real gap is that the two profile cascades differ, which is older than this slice.
- **F004 — fixed.** `sq _commit` now takes `--path` (repeatable) and `--message`, and `--subject` is optional. `_render_commit` passes through whatever the step config has, so `sq _commit` accepts or refuses it with the same text as the action. Tests: the renderer output, a CLI explicit-path commit, and a CLI refusal with no subject.
- **F005 — fixed in part.**
  - `BranchAction` now catches only `NoDesignFileError`, `SliceNotInPlanError` (new; `_slice_facts` wraps `resolve_slice_info`'s `ValueError`) and `MergeFailedError`.
  - Unexpected `git rev-parse` output now raises `GitEnvironmentError`.
  - `resolve_slice_info` has no `TypeError` path, so there was nothing to wrap.
  - Tests: a slice missing from the plan is flagged, an unrelated `ValueError` propagates, and a bad git-dir output halts the run.
- **F006 — fixed for this slice's code.**
  - `BuiltinReviewTemplate` (in `review/templates`) is the one definition of `slice`/`tasks`/`code`/`arch`. `commit_plan` and `sources` both use it.
  - The branch step, action and `sq _branch` use `OP_PARAM` and `SLICE_PARAM`. Dispatch uses `SLICE_PARAM`.
  - `has_profile_param` replaces the six `"profile" in params` checks.
  - Template-name literals that predate this slice elsewhere in the codebase are unchanged.
- **F007 — declined.** `ActionContext.cf_client` is typed `CfClientProtocol`, and the commit and branch actions hand that same client to `read_integration_target` and `branch_ops`. A narrower protocol would still need the context's client type to include both methods, so it would only move the widening, not remove it. The real client implements both, and the test fakes are `MagicMock`s.
- **F008 — fixed.** `_check_placement` refuses a CODE commit that has no slice index. Test added.
- **F009 — fixed.** A failed `rev-parse` after a successful commit now logs a WARNING and reports `sha: unknown`. Test added.
- **F010 — fixed.**
  - `read_review_verdict` checks `is_file()`, so a deleted review commits with no verdict.
  - `_design_dependencies` catches `OSError` and `UnicodeDecodeError` with a WARNING.
  - Tests added for both.
- **F011 — fixed.** `_finish_each_report` handles the halt path. A failed write there is logged with `logger.exception` and not raised, so the halting fault propagates. Test added.
- **F012 — partly addressed.** The `finally` body moved into `_finish_each_report`. `commit_plan.py` and `CommitAction` are unchanged: both are cohesive, and splitting them further adds indirection for no gain.
