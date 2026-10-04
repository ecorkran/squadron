---
docType: tasks
slice: pipeline-branch-steps-scoped-commits-and-dependency-aware-batches
project: squadron
lld: user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md
dependencies: [195]
projectState: >
  Slice design complete (20261004) and through two review rounds (both CONCERNS, all findings
  addressed). Task breakdown revised after its first review. No code written. Squadron 0.18.4
  is released; main is the integration target (`git.integration_branch` unset).
dateCreated: 20261004
dateUpdated: 20261004
status: in_progress
---

## Context Summary

- Working on **196 pipeline-branch-steps-scoped-commits-and-dependency-aware-batches**. Slice 197
  (`implement-plan`) needs it: commits that stage only their own work, `branch: {op: enter|merge}`
  steps, dependency-aware `each`, `tasks-plan` re-review, and the review-trust fixes #152, #175, #179.
- Tasks reference the slice design by decision number (D1–D14) rather than restating it. The
  design's D-sections, Success Criteria and Verification Walkthrough are the contract.
- Order follows the design's Development Approach: #175/#179, #152, scoped commits (a), branch
  steps (b), dependency flags (c), tasks re-review (d), docs and live walkthrough.
  `pipeline/git_ops.py` is built at the start of (a) rather than (b), because the commit action
  needs its error classes and strict target reader (D6 commit timeout, D8 target guard).
- Every git test runs in a temporary repo the test creates, never the project checkout.
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero errors),
  its tests, and a commit on the slice branch. Locate existing tests with `grep` before adding
  new files. Commit messages use the repo's semantic prefixes.
- Out of scope: `implement-plan`, reordering items, pushing or deleting branches, merging into
  `main` or a wider integration branch, a cf-side `dependencies` field.
- Effort: 4/5. Next planned slice: 197.

---

## Task 1 — Create the slice branch

- [x] Confirm `cf config get git.integration_branch` is empty (target = `main`) and `git status` is clean
- [x] `git checkout -b 196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches main`
  - [x] Success: `git branch --show-current` prints the new branch name

---

## Part A — #175 and #179: model alias checks and honest labels

## Task 2 — `UnknownModelAliasError` and `require_known_model`

- [x] In `models/aliases.py` add `UnknownModelAliasError(name, close_matches)` (D13)
  - [x] Message text exactly as D13: `unknown model alias '…'; did you mean: …? If this is a literal model ID, set a profile.`
  - [x] Omit the "did you mean" clause when there are no close matches
- [x] Add `require_known_model(name, *, profile_source: bool)`
  - [x] Passes when `name` is an alias, when it is a model id some alias resolves to, or when `profile_source` is true
  - [x] Otherwise raises with `difflib.get_close_matches(name, aliases, n=3)`
  - [x] Success: function and error importable; pyright clean

## Task 3 — Tests: `require_known_model`

- [x] Add tests beside the existing aliases tests
  - [x] Alias passes; literal model id passes; unknown name with a profile source passes
  - [x] Unknown name without a profile source raises, naming the alias and listing close matches
  - [x] `glm-flash-low.` suggests `glm-flash-low`; a name with no close match gives no suggestion clause
  - [x] Success: tests pass
- [x] Commit: `feat: add require_known_model with close-match suggestions`

## Task 4 — Resolver backstop

- [x] `ModelResolver._resolved` (`pipeline/resolver.py`) calls `require_known_model` (D13 backstop)
  - [x] Pass the profile-source flag the resolver already knows about; do not add a new source of truth
  - Deviation: the resolver had no profile knowledge (the `profile` param is read in the review action), so `ModelResolver` gained a `profile_source` constructor flag, set from `"profile" in params` at the run.py construction sites; the prompt renderer's display-only review model also tolerates UnknownModelAliasError.
- [x] Add resolver tests
  - [x] A model that appears only at run time raises `UnknownModelAliasError` before any request
  - [x] A valid alias and a profile-sourced name still resolve
  - [x] With a review artifact already in the slot, the backstop firing leaves that artifact unchanged and creates no archive copy (the #175 bug was a fabricated review written over the existing artifact)
  - [x] Success: tests pass
- [x] Commit: `fix: fail unknown model aliases in the resolver before any request`

## Task 5 — Classifier takes merged params and collects alias errors

- [x] `classify_pipeline` (`pipeline/classification.py`) gains a `params` argument (merged defaults plus `--param` overrides, the mapping the executor uses)
  - `params` is optional on `classify_pipeline` (None = pipeline defaults only); `--explain` builds its merged params from defaults plus `--param` overrides via the extracted `_apply_param_overrides`.
- [x] For each non-pool model candidate, call `require_known_model`; collect every error and raise one error listing them all before step 1
- [x] Update both call sites in `cli/commands/run.py` (the two sites cited in D13) to pass merged params
- [x] Add tests
  - [x] Unknown alias via `--model` is rejected pre-run
  - [x] Unknown alias via `--param review-model=…` is rejected pre-run (this slipped through before)
  - [x] Two bad aliases appear in one error
  - [x] Pool candidates are not alias-checked here
  - [x] Run-level test with a pre-existing review artifact: the rejected run writes no review file and archives nothing (design criterion 11)
  - [x] Success: tests pass
- [x] Commit: `fix: reject unknown model aliases in pre-run classification`

## Task 6 — `sq review` delegates to the shared check

- [ ] `cli/commands/review.py` `_reject_unknown_alias` calls `require_known_model` and prints its message (interface parity, D13)
- [ ] Add a test that `sq review slice N --model <bad>` prints the same message `sq run` gives for the same alias
  - [ ] Success: tests pass; no duplicate difflib logic remains in `review.py`
- [ ] Commit: `refactor: route sq review alias check through require_known_model`

## Task 7 — Shared model-candidate helper and `-v` label (#179)

- [ ] Extract `action_model_candidate(resolver, action_type, action_config, step_model)` from the classifier (D14), built on `ModelResolver.cascade_candidates`
- [ ] Classifier uses the helper (no behavior change); `_summarize_action_config` in `executor.py` uses it too
  - [ ] Dispatch and review show `model=<alias>` or `model=pool:<name>`; no candidate shows `model=session` for actions that may reuse the live session
  - [ ] The bare `default` and `None` labels are gone
- [ ] Update existing label tests; add tests for alias, pool and session labels, and one asserting label and classifier agree
  - [ ] Success: criterion 12 of the design holds in a unit-level form (`--model haiku` labels `model=haiku`)
- [ ] Commit: `fix: label pipeline actions with the model the resolver picks`

---

## Task 8 — Part A checkpoint

- [ ] Run the full pipeline and review test directories; `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all green; tree clean (no extra commit unless fixes were needed)

---

## Part B — #152: truncated PASS imposed to CONCERNS

## Task 9 — `impose_output_coverage`

- [ ] In `review/coverage.py` add `impose_output_coverage(result)` (D12)
  - [ ] If `result.output_budget_exhausted` and verdict is PASS: set CONCERNS, `verdict_source = VerdictSource.IMPOSED`, prepend a CONCERN finding with category `review-coverage` and the D12 text
  - [ ] No change for non-PASS verdicts or when the budget was not exhausted; tool-call count is ignored
- [ ] Call it beside `impose_diff_coverage` in `review/review_client.py`
- [ ] Add tests
  - [ ] PASS + exhausted → CONCERNS, IMPOSED, finding present and first
  - [ ] PASS not exhausted, CONCERNS exhausted, FAIL exhausted → unchanged
  - [ ] Saved artifact frontmatter shows `verdict: CONCERNS` and `verdictSource: imposed` through the real review save path
  - [ ] `sq review` and a pipeline review action produce the same result for the same input (shared call site)
  - [ ] Success: tests pass
- [ ] Commit: `fix: impose CONCERNS on a PASS cut off by the output budget`

---

## Part C — (a) Scoped commits

## Task 11 — `pipeline/git_ops.py`

- [ ] Create `pipeline/git_ops.py` (D5, D6, Patterns)
  - [ ] `GitEnvironmentError`; `GitStateUnknownError(GitEnvironmentError)`
  - [ ] `read_integration_target(cf_client)`: strict; unset means `DEFAULT_DIFF_BASE` imported from `review/git_utils.py`; a cf failure raises `GitEnvironmentError` and never degrades to `main`
  - [ ] `slice_branch_name(index, design_file)`: `{index}-slice.{stem-without-prefix}`; raises the D5.3 message with no design file
  - [ ] `verify_git_state(expected_branch)`: the three-read check from D6; any failed or timed-out read, or a mismatch, raises `GitStateUnknownError` naming what was observed, logged at ERROR
  - [ ] All git calls go through `run_git` (stays in `review/git_utils.py`; do not move it)
- [ ] Add a shared temp-repo test fixture (conftest or helper module) that creates a throwaway repo with an initial commit on `main`
  - [ ] Success: fixture usable by later tasks; never touches the project checkout

## Task 12 — Tests: `git_ops`

- [ ] `read_integration_target`: unset → `main`; set value returned; cf failure raises
- [ ] `slice_branch_name`: normal stem; no design file raises
- [ ] `verify_git_state`: passes clean on expected branch; each of MERGE_HEAD present, wrong branch, tracked changes, a `run_git` returning `None` raises `GitStateUnknownError` and logs at ERROR
  - [ ] Success: tests pass
- [ ] Commit: `feat: add git_ops with strict target reader and state check`

## Task 13 — `commit_plan.py`: types and subject mapping

- [ ] Create `pipeline/commit_plan.py` with `CommitSubject`, `CommitTarget`, `CommitPlan` (D1)
- [ ] Define the template→subject map once (`slice`→DESIGN, `tasks`→TASKS, `code`→CODE, `arch`→ARCHITECTURE) with a lookup function that raises on an unmapped template; the executor and the prompt renderer both use it
  - [ ] Success: no string literals compared elsewhere; pyright clean
- [ ] Commit: `feat: add commit plan types and template-to-subject map`

## Task 14a — `build_commit_plan`: candidates and staging

- [ ] Implement `build_commit_plan(target, cwd, cf_client)` paths and verdict (D1)
  - [ ] Candidates per subject: DESIGN/TASKS = artifact via `expected_artifact_paths`, review file via `slice_review_stem`/`slice_name_for`, slice plan file via `cf list slices --json` `slicePlan`, `DEVLOG.md`; ARCHITECTURE = `resolve_arch_file`, its review file, `DEVLOG.md`; DEVLOG = `DEVLOG.md`; CODE = `stage_all=True`
  - [ ] Staged = candidates ∩ `git status --porcelain` (modified, added, untracked); paths computed, never globbed
  - [ ] Verdict read from the review file frontmatter with `read_frontmatter`, never from memory
  - [ ] `left_out` lists every other dirty path; nothing staged → empty `paths`
- [ ] Add tests (temp repo, fake cf client): candidate sets for DESIGN, TASKS, ARCHITECTURE, DEVLOG, CODE; staged∩dirty only; left-out paths; nothing staged; verdict read from disk; unmapped template error
  - [ ] Success: tests pass
- [ ] Commit: `feat: compute commit plan paths from produced artifacts`

## Task 14b — `build_commit_plan`: messages

- [ ] Add message generation (D2)
  - [ ] One message per D2 table row; add vs revise from porcelain status (untracked/added = add, modified = revise)
  - [ ] Review clause omitted when no review file is staged; verdict as written in frontmatter; no internal step names
- [ ] Add tests, one per D2 row, plus review-only round 0, review-only round n, initiative-scoped, DEVLOG with and without a slice
  - [ ] Success: tests pass
- [ ] Commit: `feat: derive commit messages from the staged set`

## Task 15a — `CommitAction`: plan staging and messages

- [ ] Rework `pipeline/actions/commit.py` to stage `CommitPlan.paths` and use the plan's message (D2)
  - [ ] Explicit `params["message"]` still honored verbatim
  - [ ] Remove `message_prefix` and the `(iteration n)` suffix
  - [ ] Nothing staged → `committed: False` and WARNING `commit: step {name} produced no changes to commit`; left-out paths named in a WARNING
  - [ ] `git add -A` is never a default
  - [ ] `git add`/`git commit` nonzero exit with stderr → ordinary action failure carrying stderr
- [ ] Add tests (temp repo): stray file stays modified and is named in the WARNING; nothing staged; explicit message honored; hook rejection as failure
  - [ ] Success: tests pass; design criteria 1 and 3 hold
- [ ] Commit: `feat: stage only planned paths in the commit action`

## Task 15b — `CommitAction`: branch guards and timeout

- [ ] Add the guards (D3, D6 commit paragraph, D8)
  - [ ] `stage_all` honored only on `{index}-slice.*` for the plan's slice (`parse_slice_branch`); else fail with `refusing to stage all changes off the slice branch (on {branch})`
  - [ ] Non-CODE commit off the target raises `GitEnvironmentError` (`planning commit for slice {n} on {branch}; expected {target}`), except a DEVLOG commit on its own slice branch; target read with `read_integration_target`
  - [ ] `run_git` returning `None` during add or commit → `GitStateUnknownError`, logged at ERROR
- [ ] Add tests: CODE on its slice branch stages all; CODE off the branch refused; design/tasks/architecture commit off the target raises; DEVLOG on its own slice branch succeeds; DEVLOG on another slice's branch raises; timeout raises `GitStateUnknownError` with the ERROR log
  - [ ] Success: tests pass; design criterion 7b holds
- [ ] Commit: `feat: guard commit placement and classify git timeouts`

## Task 16 — Phase step and loop-round callers

- [ ] `steps/phase.py`: commit config carries the artifact kind and target subject (D1)
- [ ] `executor.py`: a loop round's commit passes round results; subject comes from the round's last review action template via the Task 13 lookup; a round with no review fails with `commit scope unknown: no review in round {n}`
- [ ] Update the existing exact-equality `expand()` tests for the phase step's commit config
- [ ] Add a loop test: round 2 of a P4-style loop yields `docs: revise slice N design, round 2 (review: …)`; a review-only round yields the `review: re-review …` form
  - [ ] Success: tests pass; no `chore: phase-` or `loop-` messages remain in any test expectation
- [ ] Commit: `feat: build phase and loop-round commits from the commit plan`

## Task 17 — `devlog` step commits its entry

- [ ] `steps/devlog.py` `expand()` appends a commit action with `CommitSubject.DEVLOG` (D7); message `docs: add DEVLOG entry for slice {n}` (no slice: `docs: add DEVLOG entry`)
- [ ] Update existing devlog `expand()` tests; add a test that only `DEVLOG.md` is staged
  - [ ] Success: tests pass
- [ ] Commit: `feat: commit the devlog entry from the devlog step`

## Task 18 — Hidden `sq _commit` and prompt-only rendering

- [ ] Create `cli/commands/commit_run.py` (sibling of `summary_run.py`), register in `cli/app.py`
  - [ ] Flags: `--subject design|tasks|architecture|code|devlog`, `--slice` or `--plan`, `--template`, `--round` (design API contract, amended)
  - [ ] Calls `build_commit_plan` and the same commit logic as the action; prints `committed <sha> <message>`; exits 1 with the action's error text
- [ ] `prompt_renderer.py` renders the commit action as `sq _commit …`
  - [ ] For a loop-round commit, fill `--template` and `--round` as the executor does: the template of the round's last review action (Task 13 lookup) and the round number; a round with no review fails at render time with the same message as Task 16
  - [ ] A devlog commit renders `--subject devlog` with no template or round
- [ ] Add tests
  - [ ] CLI and action give identical paths and message for the same input
  - [ ] Renderer output for a P4 loop round contains the expected `--subject`, `--template`, `--round`
  - [ ] Renderer output for the devlog step contains `--subject devlog`
  - [ ] Success: tests pass
- [ ] Commit: `feat: add sq _commit and render scoped commits for prompt-only runs`

## Task 19 — Part C checkpoint

- [ ] Run the full pipeline test suite; `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all green; tree clean

---

## Part D — (b) Branch steps

## Task 20 — cf worktree reader

- [ ] Check `integrations/context_forge.py` for an existing `cf worktree list --json` reader; if absent add `list_worktrees()` returning entries with `worktreePath`
  - [ ] A cf failure raises; no degrade
- [ ] Add a test with a faked cf runner
  - [ ] Success: test passes
- [ ] Commit: `feat: add cf worktree list reader`

## Task 21 — `BranchOp` and `BranchStepType`

- [ ] Create `steps/branch.py`: `BranchOp` StrEnum (`ENTER`, `MERGE`) and `BranchStepType` (D4)
  - [ ] Validation requires `op`, accepts optional `slice` (default `{slice}`), rejects every other key
  - [ ] Expands to one `branch` action
- [ ] `steps/__init__.py`: add `StepTypeName.BRANCH` and the bootstrap import
- [ ] Add tests: valid enter and merge, missing `op`, unknown key, bad op value
  - [ ] Success: tests pass
- [ ] Commit: `feat: add branch step type`

## Task 22a — `BranchAction` enter: guards

- [ ] Create `actions/branch.py` with enter logic in a function the CLI also calls (D4); implement D5 steps 1–5
  - [ ] Environment failures raise `GitEnvironmentError`, logged at ERROR: cf failure, unregistered linked worktree, foreign branch, dirty tree (message lists paths and the D5.5 recovery text)
  - [ ] Item failure (no design file) returns `ActionResult(success=False)`
  - [ ] Guards run in D5 order and leave git state untouched when they fail
- [ ] Add temp-repo tests, one per guard; each failing guard asserts branch and `git status` unchanged
  - [ ] Success: tests pass; design criterion 5 holds
- [ ] Commit: `feat: add branch enter guards`

## Task 22b — `BranchAction` enter: switch and leftover preservation

- [ ] Add D5 steps 4 (another slice's branch) and 6 (switch) to the enter function
  - [ ] On another slice's branch: commit leftovers as `chore: preserve uncommitted work on flagged slice {m}` (`stage_all` allowed there), checkout target, WARNING `left unmerged slice branch …`
  - [ ] Existing slice branch → checkout; otherwise `git checkout -b {branch} {target}`
  - [ ] Branch checked out in another worktree raises `GitEnvironmentError` with git's message, no force
  - [ ] Other switch failures or a `run_git` timeout go to `verify_git_state` with the starting branch
  - [ ] Outputs `{"branch", "target", "created"}`; no `--force`, `reset` or delete anywhere
- [ ] Add temp-repo tests: new branch created from target; existing branch checked out; on another slice's branch with leftovers (committed, then target checked out, WARNING asserted); on another slice's branch clean; branch checked out elsewhere; `run_git` timeout
  - [ ] Success: tests pass
- [ ] Commit: `feat: add branch enter switch and leftover preservation`

## Task 23a — `BranchAction` merge: happy path and already merged

- [ ] Implement D6 steps 1–5 in the same module
  - [ ] Re-read the target; already-merged (on target, `merge-base --is-ancestor`) succeeds with `merged: "already"`
  - [ ] Otherwise require the slice branch and a clean tree; `checkout target`; `merge --no-ff -m "merge: slice {index} — {name}"`
  - [ ] Target checked out in another worktree raises `GitEnvironmentError`
- [ ] Add temp-repo tests: clean merge with the expected message and checkout ending on target; already merged; wrong branch; dirty tree; target checked out elsewhere
  - [ ] Success: tests pass
- [ ] Commit: `feat: add branch merge`

## Task 23b — `BranchAction` merge: failure and abort path

- [ ] Implement D6 step 6 and the state check wiring
  - [ ] On any merge failure capture conflicted paths (`diff --name-only --diff-filter=U`), `merge --abort` if `MERGE_HEAD` exists, then `verify_git_state(target)`
  - [ ] Passing check → item failure `merge failed: …; slice branch {branch} left unmerged`; failing check → `GitStateUnknownError` (ERROR log)
  - [ ] A `run_git` timeout during checkout or merge goes to the same state check
- [ ] Add temp-repo tests: conflict (target clean, no `MERGE_HEAD`, branch unmerged, conflicted paths listed); non-conflict refusal (untracked file overwritten); `merge --abort` failing; `run_git` `None` during checkout and during merge; each asserts the ERROR log plus `GitStateUnknownError`, or an item failure when the state check passes
  - [ ] Success: tests pass; design criterion 6 holds
- [ ] Commit: `feat: abort failed merges back to a clean target`

## Task 24 — Halting run, `each` report, and batch composition

- [ ] `_execute_each_step` writes its batch report in a `finally` so a `GitEnvironmentError` still produces it (D6 last paragraph)
- [ ] Confirm `GitEnvironmentError` propagates out of `execute_pipeline` the way `LazySessionConnectError` does, and `sq run` exits 1 with the message
- [ ] Add tests
  - [ ] A halted `each` run writes its report with items recorded so far
  - [ ] `sq run` exits 1 and prints the message
  - [ ] Design criterion 7a: a two-item `each → enter → implement → merge` composition (fake dispatch) where item 1's implement fails: item 1 FLAGGED on its slice branch with leftovers committed; item 2's enter returns to the target with a WARNING; item 2 runs and merges
  - [ ] Success: tests pass
- [ ] Commit: `feat: write the batch report on a halted run`

## Task 25 — Loader rule: `implement` needs a preceding enter

- [ ] `pipeline/loader.py` `validate_pipeline` reports `implement step {name} needs a preceding branch: {op: enter}` (D4)
  - [ ] An enter counts if earlier in the implement's own list, or earlier in any enclosing list than the `loop:`/`each:` containing it; an enter in a sibling container does not count
- [ ] Add tests: flat valid and invalid; enter before a containing `each`/`loop` valid; enter inside the container before the implement valid; enter only in a sibling container invalid; error text names the fix
  - [ ] Success: tests pass; design criterion 7 holds
- [ ] Commit: `feat: require branch enter before implement steps`

## Task 26 — Hidden `sq _branch` and prompt-only rendering

- [ ] Create `cli/commands/branch_run.py`, register in `cli/app.py`: `sq _branch enter|merge --slice N`
  - [ ] Calls the same functions as `BranchAction`; prints `on <branch> (created from <target>)` or the merge result; exits 1 with the action's error text
- [ ] `prompt_renderer.py` renders branch steps as `sq _branch enter --slice N` / `sq _branch merge --slice N`
- [ ] Add tests: CLI and action produce the same branch and outcome in a temp repo; renderer output contains the commands
  - [ ] Success: tests pass
- [ ] Commit: `feat: add sq _branch and render branch steps for prompt-only runs`

## Task 27 — Built-in pipelines gain branch steps

- [ ] Reorder `data/pipelines/P6.yaml`, `implement.yaml`, `P456.yaml`, `P56.yaml` to `branch enter → implement → devlog → branch merge → summary` (D7)
  - [ ] Keep `checkpoint: on-fail` in P6 and `implement`; planning steps in P456 and P56 stay on the target (D8)
- [ ] Add tests
  - [ ] All four load and validate; step order as specified
  - [ ] A repo-wide test that every built-in pipeline with an `implement` step passes the Task 25 rule
  - [ ] Design criterion 4: a P6 run with fake dispatch and review in a temp repo asserts `_find_slice_branch` (`review/git_utils.py`) resolves the slice branch while on the entered branch, the code review's diff range resolves, and the run ends on the target with `merge: slice N — <name>`
  - [ ] Success: tests pass
- [ ] Commit: `feat: wire branch enter and merge into code pipelines`

## Task 28 — Part D checkpoint

- [ ] Run the full test suite; `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all green; tree clean

---

## Part E — (c) Dependency-aware `each`

## Task 29 — Item dependencies from design frontmatter

- [ ] `sources.py` `_slice_item` gains `dependencies: list[int]` from the design's `dependencies:` frontmatter when `design_file` is set, else `[]` (D9)
  - [ ] Each element is parsed as its leading integer (`195`, `"195"`, `"195-slice.foo"` → 195); an element with no leading integer is dropped with a WARNING naming the slice and value
- [ ] Add tests: int, string, prefixed string, bad element (WARNING asserted), no design file, no `dependencies` key
  - [ ] Success: tests pass
- [ ] Commit: `feat: read slice dependencies from design frontmatter`

## Task 30 — Flagged-index set in `each`

- [ ] `_execute_each_step` keeps `flagged: set[int]` and flags dependents before the body runs (D10)
  - [ ] Reason `dependency {d} flagged`, several joined with `; `; every FLAGGED item with an integer `index` joins the set (transitive in run order)
  - [ ] Applies under both failure policies, same as `flag_reason`; items without `dependencies` unaffected; order unchanged
- [ ] Add tests: direct, transitive, independent item runs, dependency outside the run, dependency that comes later in the run does not flag, both failure policies, body not executed for a flagged dependent
  - [ ] Success: tests pass; design criterion 8 holds
- [ ] Commit: `feat: flag batch items whose dependencies were flagged`

---

## Part F — (d) `tasks-plan` re-review

## Task 32 — `_review_flag` and `slices_needing_tasks`

- [ ] Generalize `_design_review_flag` to `_review_flag(entry, template, accept) -> str | None` using `slice_review_stem(index, template, …)` (D11); reason strings name the review (`no tasks review found`, `tasks review below threshold (CONCERNS < PASS)`)
- [ ] Rename `cf.untasked_slices` to `cf.slices_needing_tasks(plan, accept)`; it selects open, designed slices that are untasked, or tasked with a tasks review missing, unreadable or below `accept`; the design-review `flag_reason` still applies first
- [ ] Update every caller and YAML reference to the old name (grep the whole repo, docs included)
- [ ] Add tests: untasked selected; tasked + missing review selected; tasked + unreadable review selected; tasked + below threshold selected; tasked + passing review not selected; design-review flag precedence
  - [ ] Success: tests pass; `grep -r untasked_slices` finds nothing outside the CHANGELOG
- [ ] Commit: `feat: select tasked slices with unsettled task reviews`

## Task 33 — `existing: keep`

- [ ] Add `ExistingArtifactPolicy` StrEnum (`CREATE` default, `KEEP`) (D11)
- [ ] `steps/phase.py` accepts `existing:` and passes it with the artifact kind into the dispatch config
- [ ] `actions/dispatch.py`: under `KEEP`, when `expected_artifact_paths` has an existing file, skip the model call and return success with `outputs={"skipped": "artifact exists", "paths": [...]}`
- [ ] `events/builtin/dispatch_artifact.py` and the revision stamp treat `skipped` as satisfied and do not stamp
- [ ] Add tests
  - [ ] `KEEP` with an existing artifact: no model call, success, post-condition passes, no stamp
  - [ ] `KEEP` with no artifact: dispatches normally
  - [ ] `CREATE` (default) unchanged
  - [ ] Step validation rejects an unknown `existing:` value
  - [ ] Success: tests pass
- [ ] Commit: `feat: add existing keep policy to phase steps`

## Task 34 — `tasks-plan.yaml`

- [ ] Switch `data/pipelines/tasks-plan.yaml` to `slices_needing_tasks` and set `existing: keep` on its `tasks:` step (D11)
- [ ] Add a pipeline-level test (fake cf, fake dispatch/review): a slice with tasks and no tasks review is selected, dispatch skipped, review runs, and the revise loop runs as needed (design criterion 9)
  - [ ] Success: tests pass
- [ ] Commit: `feat: re-review tasked slices in tasks-plan`

---

## Part G — Docs and verification

## Task 36 — Documentation

- [ ] `docs/PIPELINES.md`: document `branch:` (ops, validation rule, the deliberate break for user pipelines), `existing: keep`, the `slices_needing_tasks` rename, and the commit message rules (D2 table)
- [ ] `CHANGELOG.md`: short user-facing bullets (scoped commits and messages, branch steps and the `implement` requirement, dependency flags, tasks re-review, #152, #175, #179); technical detail stays in DEVLOG
- [ ] `docs/COMMANDS.md`: only if hidden `_commit`/`_branch` commands are listed alongside other hidden commands; otherwise leave unchanged
  - [ ] Success: docs match behavior; no stale `message_prefix` or `untasked_slices` references
- [ ] Commit: `docs: document branch steps, scoped commits, and tasks-plan re-review`

## Task 37 — Full validation

- [ ] `ruff format`, `ruff check`, `pyright` (zero errors), full test suite from a clean checkout state
- [ ] Re-read design Success Criteria 1–12 and Technical Requirements; each maps to at least one passing test or a walkthrough step
  - [ ] Success: all green; any criterion without coverage gets a test (and a commit) before proceeding

## Task 38 — Live walkthrough in the scratch project

- [ ] Run Verification Walkthrough steps 1–7 and 9 from the slice design in the scratch project (`…/scratchpad/sq-scratch`, toy tally CLI, plan 100) with `CLAUDECODE` unset and `uv run --project <squadron>`; always pass `--model`
  - [ ] Step 8 (truncated PASS) is a spot check only; the unit test in Task 9 is the gate
- [ ] Record the observed result of each step (command, key output line) in the DEVLOG entry
  - [ ] Success: each step's expected output matches the design; any divergence is fixed or filed as a GitHub issue linked from the DEVLOG
- [ ] Commit: `docs: add slice 196 implementation DEVLOG entry`
  - [ ] Success: commit on the slice branch; tree clean

---

## Notes

- No merge task is listed: Phase 7 merges the slice branch into `main` after the code review.
- Task numbers keep their original values; letter suffixes mark splits made after the first tasks review. Tasks 10, 31 and 35 no longer exist (their commits folded into the preceding tasks), so the sequence has gaps.
