---
docType: tasks
slice: implementation-batch-pipeline-implement-plan
project: squadron
lld: user/slices/197-slice.implementation-batch-pipeline-implement-plan.md
dependencies: [196]
projectState: >
  Slice design complete (20261004) and through two review rounds (both CONCERNS, all findings
  addressed). No code written. 196 is complete on main; main is the integration target
  (`git.integration_branch` unset).
dateCreated: 20261005
dateUpdated: 20261005
status: not_started
---

## Context Summary

- Working on **197 implementation-batch-pipeline-implement-plan**: `implement-plan` runs Phase 6
  over every ready slice of a plan in dependency order (branch → implement → code review →
  revise loop → devlog → merge), flags failures with a closed `FlagKind`, writes `report.json`,
  and adds item resume (`sq run --resume <run_id> --item N --decision retry|accept`).
- Tasks reference the slice design by decision number (D1–D12) rather than restating it. The
  design's D-sections, D12 failure-mode table, Success Criteria (1–17) and Verification
  Walkthrough are the contract.
- Order follows the design's Development Approach: D5/D6 branch changes, D4 keep, D2/D3 source,
  D7 flags and report, D1/D10 pipelines, D11 lock and reserved params, D8/D9 item resume, docs
  and live walkthrough.
- Every git test runs in a temporary repo the test creates, never the project checkout. Every
  D12 row has a test asserting both the outcome and the log record (level and message).
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero errors),
  its tests, and a commit on the slice branch. Locate existing tests with `grep` before adding
  new files. Commit messages use the repo's semantic prefixes.
- Out of scope: deciding flags, abandoning/deferring slices, concurrent items (#146), mid-body
  item re-entry (#59), `--prompt-only` rendering of `each`/`loop` (#145), background-task waits
  (#163), pushing, PRs, deleting branches.
- Effort: 4/5. Closes #183. Next planned slice: 198.

---

## Task 1 — Create the slice branch

- [ ] Confirm `cf config get git.integration_branch` is empty (target = `main`) and `git status` is clean
- [ ] `git checkout -b 197-slice.implementation-batch-pipeline-implement-plan main`
  - [ ] Success: `git branch --show-current` prints the new branch name

---

## Part A — Branch steps: catch-up merge (D5), `restore_target()`, `branch: { plan: }` (D6)

## Task 2 — Work-count helper

- [ ] In `pipeline/git_ops.py` (next to `run_git`; both `branch_ops.py` and `actions/dispatch.py` import it from there), add one helper that returns `git rev-list --count --no-merges {target}..{branch}` as an int (D4, D5). Both the D4 keep check and the D5 catch-up use it; do not duplicate the call
  - [ ] Non-zero exit or timeout (`run_git` returns `None`) raises `GitStateUnknownError`, logged at ERROR `cannot count work on {branch}: …` (D12 row 1). Never returns 0 on failure
- [ ] Add a second helper for the behind count, `git rev-list --count {branch}..{target}` (merges counted); failure raises `GitStateUnknownError`, ERROR `cannot compare {branch} with {target}: …` (D12 row 2)
- [ ] Tests (temp repo): ahead by N; not ahead; only merge commits ahead → 0; behind by N; each helper's non-zero exit and timeout raise with the asserted ERROR record
  - [ ] Success: tests pass
- [ ] Commit: `feat: add slice branch work and behind counts`

## Task 3 — `BranchFailure` in branch action outputs

- [ ] Add `BranchFailure` StrEnum (`CONFLICT`, `OTHER`) in `pipeline/branch_ops.py` (D7)
- [ ] Every failing branch action result carries `outputs["failure"]`: `conflict` only when a merge or catch-up stopped on conflicted paths; `other` for every other branch action failure (refused merge, missing design file). A failed `set_arch` is a separate cf-op step, not a branch action, so it carries no `failure` key (Task 15 classifies it `step_failed`)
- [ ] A successful enter's outputs include the slice branch name (D7 `branch` field reads it later)
- [ ] Tests: existing merge-conflict path reports `conflict`; refused merge and missing design file report `other`; enter success outputs carry the branch name
  - [ ] Success: tests pass; existing branch tests unchanged
- [ ] Commit: `feat: classify branch action failures`

## Task 4 — Catch-up on enter of an existing branch (D5, #183)

- [ ] In `enter_slice_branch`, after checking out an existing slice branch, use the behind count (Task 2); when > 0:
  - [ ] Work count 0 → `git merge --ff-only {target}` (no merge commit)
  - [ ] Otherwise → `git merge --no-ff -m "merge: {target} into slice {n}" {target}`
  - [ ] Conflict → record conflicted paths, `git merge --abort`, `verify_git_state` expecting the slice branch; item failure with `failure: conflict` and the D5 message (`catch-up merge of {target} into {branch} failed: CONFLICT … (conflicted: …); resolve on the branch and retry`); checkout stays on the clean slice branch
  - [ ] Refusal or timeout → abort if `MERGE_HEAD` exists, state check; passes → item failure `failure: other`; fails → `GitStateUnknownError` (D12 row 4)
- [ ] No rebase, reset, or `--force` anywhere in the path
  - [ ] Success: pyright clean
- [ ] Commit: `feat: catch up existing slice branches to the target on enter`

## Task 5 — Tests: catch-up merge

- [ ] Temp-repo tests (add beside `tests/pipeline/test_branch_enter.py`):
  - [ ] Behind with work: merge commit `merge: main into slice N` created; branch history preserved
  - [ ] Behind with no work: fast-forward, no merge commit; the work count afterwards is 0
  - [ ] Not behind: no merge attempted
  - [ ] Conflict: item failure `conflict` listing the path; no `MERGE_HEAD`; checkout on the slice branch; WARNING record asserted (D12 row 3)
  - [ ] Refusal with passing state check → `other`; failing state check → `GitStateUnknownError` with ERROR record (D12 row 4)
  - [ ] Code review diff range after a catch-up still excludes target-only commits (merge-base based)
  - [ ] Success: tests pass
- [ ] Commit: `test: cover catch-up merge on branch enter`

## Task 6 — Extract `restore_target()`

- [ ] Extract the leave-other-branch logic of `_leave_other_slice_branch` into public `restore_target(cwd)` in `branch_ops.py`: commit leftovers on the current slice branch, then check out the target (196 D5.4). Enter calls it; behavior unchanged
  - [ ] Commit or checkout failure/timeout raises `GitStateUnknownError` with ERROR (D12 row 5)
- [ ] Tests: existing enter tests pass unchanged; direct `restore_target` test from a dirty slice branch ends on target with leftovers committed on the branch; failure test asserts the error and ERROR record
  - [ ] Success: tests pass
- [ ] Commit: `refactor: extract restore_target from branch enter`

## Task 7 — `branch: { plan: }` (D6)

- [ ] `BranchStepType` (`steps/branch.py`) accepts optional `plan:`; expansion emits `cf-op(set_arch, plan)` before the branch action, same order as phase steps
- [ ] Validation accepts `plan:` on `enter`; leave `merge` unchanged (design: merge doesn't need it)
- [ ] Tests: expansion with `plan:` yields cf-op then branch action; without `plan:` no cf-op; a failed `set_arch` fails the item before the branch action runs (its flag kind, `step_failed`, is asserted in Task 15)
  - [ ] Success: tests pass
- [ ] Commit: `feat: align cf plan before branch enter`

## Task 8 — Part A checkpoint

- [ ] Run `tests/pipeline`; `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all green; tree clean

---

## Part B — `existing: keep` on implement (D4)

## Task 9 — Allow keep on implement and skip on branch work

- [ ] `PhaseStepType._validate_existing` accepts `keep` on the implement phase (196 rejected it; update that rule)
- [ ] `actions/dispatch.py`: under `KEEP` for CODE, read the target with `read_integration_target` and the work count (Task 2) for the slice branch; > 0 → skip the model call, return success with `outputs={"skipped": "branch has work", "ahead": n}`, log `implement: step {name} keeps existing work on {branch} ({n} commits ahead of {target})`
  - [ ] Count failure propagates `GitStateUnknownError` (never treated as 0)
  - [ ] Reuse the existing `SKIPPED_KEY` mechanics; post-condition and revision stamp treat the skip as satisfied, as for design/tasks
- [ ] Tests (temp repo, extend `test_existing_keep.py`): ahead → no model call, outputs and log asserted; not ahead → dispatches; merge commits only → dispatches; `rev-list` timeout raises with ERROR record; validation now accepts keep on implement and still rejects unknown values
  - [ ] Success: tests pass
- [ ] Commit: `feat: keep existing slice branch work on implement`

---

## Part C — Source and ordering (D2, D3)

## Task 10 — `order_by_dependencies`

- [ ] Add `order_by_dependencies(items) -> list[dict]` in `pipeline/sources.py`: stable topological sort over dependencies between returned items, ties by plan order (D3)
  - [ ] Dependencies on non-returned indices are ignored by the sort
  - [ ] Cycle raises `ValueError("dependency cycle in plan {plan}: a → b → a")` naming the cycle path
- [ ] Tests: already-ordered input unchanged; dependent listed first moves after its dependency; independent items keep plan order; diamond; two-node and three-node cycles name the path
  - [ ] Success: tests pass
- [ ] Commit: `feat: order batch items by dependencies`

## Task 11 — `cf.slices_ready_to_implement(plan, accept)`

- [ ] Add and register the source (D2): open slices (not `complete`/`deferred`) with a design file; undesigned slices not returned
- [ ] `flag_reason` checks in D2 table order, first hit wins: design review (existing `_review_flag` with design), no task file, tasks review (`_review_flag` with tasks), `all tasks checked but slice not marked complete` (`completed == total > 0`). These set `flag_kind: not_ready`
- [ ] Dependency rows: in-plan, open, not a returned item → `flag_reason: dependency {d} not designed`, `flag_kind: dependency`; out-of-plan dependency → WARNING `slice {n}: dependency {d} is outside plan {plan}; not checked`, no flag
- [ ] Items pass through `order_by_dependencies`; a cycle fails source evaluation (ERROR via the existing source error path)
- [ ] A failing cf call fails the source (no guessed result)
  - [ ] Success: pyright clean
- [ ] Commit: `feat: add slices_ready_to_implement source`

## Task 12 — Tests: `slices_ready_to_implement`

- [ ] Fake cf client tests in `tests/pipeline/test_sources.py`:
  - [ ] Each D2 table row, one test each, asserting reason text and `flag_kind: not_ready`
  - [ ] Precedence: design review flag wins over missing task file
  - [ ] Complete, deferred, and undesigned slices not returned
  - [ ] All tasks checked with open status flagged; partially checked not flagged
  - [ ] Dependency not designed → `dependency` kind; out-of-plan dependency → WARNING record, no flag
  - [ ] Ordering applied; cycle fails source evaluation with the cycle message
  - [ ] Success: tests pass
- [ ] Commit: `test: cover slices_ready_to_implement selection and flags`

---

## Part D — Structured flags and `report.json` (D7)

## Task 13 — Enums and record fields

- [ ] In `batch_report.py` add `FlagKind` and `ItemDecision` StrEnums exactly as D7; add `ItemOutcome.NOT_RUN`
- [ ] `BatchItemRecord` gains `flag_kind`, `failed_step`, `branch`, `decision`, `resumed_at` (all optional)
- [ ] Markdown flagged line gains kind, failed step and branch (D7 example line); `not_run` lines render with their reason; summary counts include `not_run`
- [ ] Tests: render of a flagged line with all fields, a pre-flag (no failed step, no branch), and a `not_run` line; counts
  - [ ] Success: tests pass
- [ ] Commit: `feat: add flag kinds and decision fields to batch records`

## Task 14 — `StepResult.exhausted`

- [ ] `StepResult` gains `exhausted: bool = False`; `_execute_loop_step` sets it whenever rounds run out without `until` met, regardless of `on_exhaust` (accept, fail, pause, skip)
- [ ] Tests in `test_executor_loop_body.py` (or the loop test file `grep` finds): exhausted+accepted, exhausted+fail, exhausted+checkpoint all set it; `until` met and `skip_if_met` do not
  - [ ] Success: tests pass
- [ ] Commit: `feat: mark exhausted loops on step results`

## Task 15 — Flag kind assignment in `each`

- [ ] Where items are flagged in the executor, set the kind at the flag site (no `reason` parsing):
  - [ ] Source `flag_reason` → the item's `flag_kind` (`not_ready` or `dependency`)
  - [ ] `_dependency_flag_reason` → `DEPENDENCY`
  - [ ] Failed loop with `exhausted` → `REVIEW_UNRESOLVED`
  - [ ] Failed branch action with `outputs["failure"] == conflict` → `BRANCH_CONFLICT`; `other` → `STEP_FAILED`
  - [ ] Any other failed step → `STEP_FAILED`; PAUSED status → `PAUSED`
- [ ] Record `failed_step` (the failing step's name) and `branch` (from the enter action's outputs, when enter ran)
- [ ] Tests in `test_executor_each.py`, one per kind, plus each `BranchFailure` class and a refused merge / missing design file / failed `set_arch` each landing `step_failed` (criterion 13)
  - [ ] Success: tests pass
- [ ] Commit: `feat: classify flagged batch items by kind`

## Task 16 — `report.json` write and load

- [ ] `BatchReport` writes `{run_id}.{step}.report.json` with the D7 shape (`docType`, `schemaVersion: 1`, `pipeline`, `runId`, `stepName`, `plan`, `counts` with a `not_run` key per D7, camelCase item keys)
- [ ] Both `.md` and `.json` written atomically: temp file in the same directory, then rename. `OSError` → `logger.exception` with the path, re-raise; prior file stays intact (D12 report row)
- [ ] `BatchReport.load(path)`: missing, unparseable or wrong `schemaVersion` raises a clear error naming the path and problem; version mismatch names both versions
- [ ] Tests: round trip equality; atomic write leaves the previous file intact when rename/write fails (simulate `OSError`), ERROR asserted; version mismatch message; unparseable file message
  - [ ] Success: tests pass
- [ ] Commit: `feat: write and load versioned batch report json`

## Task 17 — Per-item rewrite and `not_run` on halt

- [ ] The executor rewrites both report files after every finished item, not only at the end
- [ ] In the `each` `finally`, on `GitEnvironmentError` or `GitStateUnknownError`: in-flight item FLAGGED `step_failed` with the error as reason; every unreached item `not_run` with the halt's error as reason; then write
- [ ] `sq run` batch summary line prints the JSON path next to the Markdown path
- [ ] Tests: report present after item 1 when item 2 raises mid-body; halt marks in-flight + unreached correctly; summary line prints both paths
  - [ ] Success: tests pass
- [ ] Commit: `feat: rewrite batch reports per item and record unreached items`

## Task 18 — Part D checkpoint

- [ ] Run `tests/pipeline`; `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all green; tree clean

---

## Part E — Pipelines (D1, D10)

## Task 19 — `implement-plan.yaml`

- [ ] Add `data/pipelines/implement-plan.yaml` exactly as D1 (params, `each` body, `on_exhaust: fail`)
- [ ] Tests in `test_builtin_pipelines.py`: loads and validates; params defaults as D1; listed by `sq run --list` (or the existing builtin listing test)
- [ ] Pipeline-level test with fake cf, dispatch and review: two items where the dependent is listed first run in dependency order; a FAIL-at-exhaust item is `review_unresolved` at `revise-code` with branch recorded and its dependent `dependency`; an independent item merges
  - [ ] The flagged item's branch has all its work committed and is unmerged; the next item's `branch enter` starts from a clean target (criterion 3)
  - [ ] An implement dispatch that leaves no commits: the code review's `EmptyDiffError` flags the item `step_failed` with WARNING `item N flagged: …` asserted (D12 last row)
  - [ ] Success: tests pass
- [ ] Commit: `feat: add implement-plan pipeline`

## Task 20 — Refresh single-slice pipelines (D10)

Replace each file's implement section with the D10 steps (`on_exhaust: checkpoint`). Keep each file's model defaults.

- [ ] `P6.yaml`: D10 body; add `max-revisions`, `pass-threshold`, `accept-threshold` params with P456's defaults
- [ ] `implement.yaml`: D10 body; add the three params plus `review-model` (default `minimax`, matching P6)
- [ ] `P56.yaml`: replace its implement section with the D10 body
- [ ] `P456.yaml`: replace its implement section with the D10 body
- [ ] Update existing tests that asserted the old step lists (`test_code_pipelines_branching.py`, `test_builtin_pipelines.py`)
- [ ] Pipeline-level test (fake dispatch and review) for each of the four: a non-PASS review with `-p max-revisions=0 -p accept-threshold=review.pass` pauses the run at a checkpoint, with no merge (criterion 12)
  - [ ] Success: all four validate; updated and new tests pass
- [ ] Commit: `feat: add code review revise loop to single-slice pipelines`

## Task 21 — Drift test

- [ ] Test in `test_builtin_pipelines.py`: for each of P6, `implement`, P56, P456, the steps from `branch enter` through `branch merge` equal the `implement-plan` body from `branch enter` on, after normalizing `slice:`/`plan:` references and `on_exhaust`
  - [ ] Success: passes; editing one file's loop `max` in a scratch copy makes it fail (verify once, don't commit the scratch change)
- [ ] Single-slice test: a second P6 run on a slice whose branch has work skips the implement dispatch (criterion 12)
- [ ] Commit: `test: keep single-slice code pipelines in step with implement-plan`

---

## Part F — Reserved params and run lock (D8, D11)

## Task 22 — `control_params.py`

- [ ] Add `pipeline/control_params.py` defining `OVERRIDE_INSTRUCTIONS` and `ACCEPT_DECISION` keys and the reserved set
- [ ] Replace the string literals in the executor checkpoint path and `_apply_override` with the constants (`grep override_instructions` over `src/` afterwards: only `control_params.py` holds the literal)
- [ ] `_assemble_params` (`cli/commands/run.py`) rejects either key as a `-p` key: `'accept_decision' is reserved; use --decision accept` (and the matching message for instructions)
- [ ] `validate_pipeline` rejects either key in a pipeline `params:` block
- [ ] Tests: each `-p` key rejected with its message (criterion 16); each key rejected in a pipeline `params:` block; checkpoint override still reaches the dispatch prompt
  - [ ] Success: tests pass
- [ ] Commit: `feat: reserve control param keys`

## Task 23 — `project_run_lock`

- [ ] Add `pipeline/run_lock.py` with `project_run_lock(cwd)` context manager: `git rev-parse --git-dir` via `run_git`, exclusive non-blocking `flock` on `{git dir}/squadron-run.flock`; `fcntl` imported inside the function (pattern: `codehost/metadata_lock.py`); Windows raises a clear error
  - [ ] `rev-parse` failure/timeout → `GitEnvironmentError`, ERROR
  - [ ] Held → a dedicated error; message `another squadron run holds the project lock ({path}); one mutating run per project at a time`, ERROR
  - [ ] Other `OSError` → error with the path, ERROR
- [ ] Tests (temp repo): second holder refused with message; lock released after the holder process exits (subprocess holds and is killed); separate worktrees lock independently; each D12 lock row's ERROR record asserted
  - [ ] Success: tests pass
- [ ] Commit: `feat: add per-checkout run lock`

## Task 24 — `sq run` takes the lock for mutating pipelines

- [ ] Add a definition walk (nested steps included) that reports whether a pipeline mutates: any phase step, `devlog`, `branch`, or `loop` with `commit_each_iteration`
- [ ] `sq run` holds `project_run_lock` for the whole run when the pipeline mutates; held lock, `rev-parse --git-dir` failure (`GitEnvironmentError`) and other lock `OSError` all → exit 2, nothing runs
- [ ] Find existing CLI and pipeline tests that run mutating pipelines outside a git repo (`grep` for `sq run`/`run_pipeline` invocations of P-pipelines, `slices-plan`, `tasks-plan`); give them a temp git repo or a lock fixture so they don't start exiting 2
- [ ] Tests: `implement-plan`, `slices-plan`, `tasks-plan`, P6 detected as mutating; a review-only and a summary pipeline not; `sq run` with the lock held, with `rev-parse` failing, and with an `OSError` on open each exit 2 and dispatch nothing (criterion 15, 17)
  - [ ] Success: tests pass
- [ ] Commit: `feat: hold the project run lock for mutating pipelines`

---

## Part G — Item resume (D8, D9)

## Task 25 — Loop `accept_decision` (D9)

- [ ] `_execute_loop_step` checks `ACCEPT_DECISION` in params before round 1 (next to `skip_if_met`): loop met with `accepted=True`, zero rounds run
- [ ] Tests: with the param, no revise dispatch, result accepted; without it, unchanged behavior
  - [ ] Success: tests pass
- [ ] Commit: `feat: accept loops on an accept decision`

## Task 26 — `item_resume.py`: exits and validation

- [ ] Add `pipeline/item_resume.py` with `ResumeExit` IntEnum (`RESOLVED=0`, `FLAGGED=1`, `REJECTED=2`, `HALTED=3`) and `resume_item(...)`
- [ ] Validation, each failing with REJECTED and a message naming the fact, before any git or model work (D8):
  - [ ] Run exists; pipeline has exactly one `each` step (more than one → rejected with message)
  - [ ] `report.json` exists and loads (Task 16 errors → REJECTED, ERROR logged)
  - [ ] Record for the index exists with outcome FLAGGED or NOT_RUN
  - [ ] `accept` requires `flagKind: review_unresolved` (`accept requires flagKind review_unresolved; item {n} is {kind}`); `accept` on NOT_RUN rejected
- [ ] Run lock (Task 23) taken first; held, `rev-parse --git-dir` failure (`GitEnvironmentError`) and other lock `OSError` all → REJECTED (D12: nothing ran). This lock-time `GitEnvironmentError` is REJECTED, not HALTED; only errors after the lock is held map to HALTED (Task 28)
- [ ] Tests: each validation failure returns REJECTED with its message and touches neither git nor dispatch; each of the three lock failures returns REJECTED
  - [ ] Success: tests pass
- [ ] Commit: `feat: validate item resume requests`

## Task 27 — Git precondition

- [ ] After the lock, before source evaluation: on a slice branch → `restore_target()`; then require the target, a clean tree, and `verify_git_state(target)`
  - [ ] Unrelated branch or dirty target → REJECTED with the 196 messages (`on {branch}, expected {target}…`, `working tree not clean: …`), nothing changed
  - [ ] `restore_target` failure → HALTED
- [ ] Tests (temp repo): flagged slice branch with leftovers → leftovers committed on that branch, ends on target, continues; unrelated branch → REJECTED; dirty target → REJECTED; restore failure → HALTED (criterion 14)
  - [ ] Success: tests pass
- [ ] Commit: `feat: return to the target before an item resume`

## Task 28 — Item execution and report rewrite

- [ ] Load pipeline and params from run state; strip reserved keys with a WARNING if present; apply `--model`/`-p` overrides; set `OVERRIDE_INSTRUCTIONS` from `--instructions` and `ACCEPT_DECISION` from `--decision accept` only
- [ ] Re-evaluate the source; take the item by index. Not returned:
  - [ ] Reconcile: slice `complete` on target and slice branch ancestor of target (`git merge-base --is-ancestor`) → record PASSED with `reason: "reconciled: merged before the report was updated"`, WARNING, RESOLVED, nothing runs
  - [ ] Otherwise REJECTED naming the status
- [ ] Single-item dependency check: any in-plan dependency not complete on the target → record FLAGGED `dependency` (`dependency {d} not complete`), body not run, FLAGGED exit
- [ ] Run the body once via `_run_each_item` (existing isolation and classification)
- [ ] Replace the record (with `decision`, `resumed_at`), rewrite both report files atomically; exit RESOLVED for PASSED/ACCEPTED, FLAGGED otherwise; `GitEnvironmentError`/`GitStateUnknownError` raised after the lock is held → HALTED; report temp write or rename `OSError` → HALTED (logged by Task 16's `logger.exception`; prior report intact)
  - [ ] Success: pyright clean
- [ ] Commit: `feat: rerun one batch item on a decision`

## Task 29 — Tests: item execution

- [ ] Fake cf/dispatch/review over a temp repo:
  - [ ] Retry on `review_unresolved` with branch work: implement dispatch skipped, review runs, revise prompts begin with the "Instructions from checkpoint resolution" block, merged, record `decision: retry`, RESOLVED (criterion 7)
  - [ ] Accept: one code review, no revise rounds, merged, ACCEPTED with `decision: accept` (criterion 8)
  - [ ] Retry flagged again → FLAGGED exit, record replaced
  - [ ] Dependency open on target → `dependency N not complete`, no body (criterion 9)
  - [ ] Retry on a `not_run` record runs the body
  - [ ] Reconcile path → PASSED, WARNING, RESOLVED (criterion 17)
  - [ ] Stored `override_instructions` in run state stripped with WARNING and not used
  - [ ] Mid-item `GitStateUnknownError` → HALTED
  - [ ] Report rewrite `OSError` → HALTED, ERROR record asserted, previous `report.json` unchanged
  - [ ] Item resume on a `tasks-plan` run and on a `slices-plan` run (retry, and accept on `review_unresolved`) works with no pipeline-specific code
  - [ ] Success: tests pass
- [ ] Commit: `test: cover item resume execution paths`

## Task 30 — CLI flags

- [ ] `cli/commands/run.py`: `--item`, `--decision` (`retry`|`accept`, from `ItemDecision`), `--instructions` on `--resume`
  - [ ] `--item` requires `--decision` (no default); `--instructions` or `--decision` without `--item` rejected
  - [ ] `--item` works on COMPLETED runs; plain `--resume` unchanged
  - [ ] Output: new record as one line plus the report path; process exit code = `ResumeExit` value
- [ ] CLI tests: each flag-combination rejection exits 2; exit code passthrough for 0/1/2/3 (stub `resume_item`); plain `--resume` behavior unchanged
  - [ ] Success: tests pass
- [ ] Commit: `feat: add item resume flags to sq run`

## Task 31 — Part G checkpoint

- [ ] Full test suite; `ruff format`, `ruff check`, `pyright`
- [ ] Map design Success Criteria 1–17 and each D12 row to a passing test or a walkthrough step; add any missing test (and commit) before continuing
  - [ ] Success: all green; tree clean

---

## Part H — Docs and verification

## Task 32 — Documentation

- [ ] `docs/PIPELINES.md`: `implement-plan`, `existing: keep` on implement, `branch: { plan: }`, enter catch-up, `report.json` (fields, `schemaVersion`), item resume (flags, exit codes, run lock), and a "Batch reports and the flag handoff" section copying the design's flag handoff contract
- [ ] `CHANGELOG.md`: short user-facing bullets (implement-plan, item resume, report.json, revise loop in P6/implement/P56/P456, catch-up on enter #183); technical detail stays in DEVLOG
  - [ ] Success: docs match behavior
- [ ] Commit: `docs: document implement-plan, item resume and the flag handoff`

## Task 33 — Live walkthrough in the scratch project

- [ ] Run Verification Walkthrough setup and steps 1–7 from the slice design in the scratch project (`…/scratchpad/sq-scratch`, plan 100) with `CLAUDECODE` unset and `uv run --project <squadron>`; always pass `--model`; observe the 196 caveats (`cf set arch 100`, DEVLOG frontmatter)
- [ ] Record each step's command and key output line in the DEVLOG entry
  - [ ] Success: each step matches the design; any divergence is fixed (with a test) or filed as a GitHub issue linked from the DEVLOG
- [ ] Commit: `docs: add slice 197 implementation DEVLOG entry`

## Task 34 — Close out

- [ ] Set this file's `status: complete`; slice design `status: complete`; check off 197 in `180-slices.pipeline-intelligence.md`
- [ ] Commit: `docs: mark slice 197 complete`
  - [ ] Success: commit on the slice branch; tree clean

---

## Notes

- No merge task is listed: Phase 7 merges the slice branch into `main` after the code review.
