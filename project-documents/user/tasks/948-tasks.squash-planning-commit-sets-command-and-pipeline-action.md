---
docType: tasks
slice: squash-planning-commit-sets-command-and-pipeline-action
project: squadron
lld: user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md
dependencies: []
projectState: v0.24.1 released; 400-series (401 merged, 402 tasks written) paused
  so this lands first. Target is main (git.integration_branch unset).
dateCreated: 20261025
dateUpdated: 20261025
status: not_started
turns: 47
promptTokens: 3162332
cachedTokens: 3039905
cacheWriteTokens: 122357
completionTokens: 33350
durationSeconds: 307.6
costUsd: 2.256376
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 2.256376
    completionTokens: 33350
revision_number: 2
---

## Context Summary
- Working on slice 948: collapse the newest planning commit set (design, tasks or architecture) into one commit. Fixes #257 (command) and #258 (pipeline action). Part B: `sq metr` as a hidden alias of `sq metrology`.
- Read the slice design (D1–D7, Failure Modes, Tests) before starting. Tasks reference its decisions by number instead of repeating them.
- Existing code this slice builds on:
  - `src/squadron/pipeline/commit_plan.py`: `CommitSubject`, `CommitTarget`, `_candidates`, `_archived_reviews`, `_SUBJECT_BY_TEMPLATE`, `DEVLOG_FILE`.
  - `src/squadron/pipeline/git_ops.py`: `read_integration_target`, `current_branch`, `GitEnvironmentError`, `parse_slice_index`.
  - `src/squadron/review/git_utils.py`: `run_git` (returns `None` when git cannot run).
  - The `branch` feature is the pattern for every layer: step type `pipeline/steps/branch.py`, action `pipeline/actions/branch.py`, hidden CLI `cli/commands/branch_run.py`, renderer `_render_branch` in `pipeline/prompt_renderer.py`, registration imports in `pipeline/steps/__init__.py` and `pipeline/executor.py` (`_a_branch`).
  - Test fixture `temp_git_repo` and helper `run_test_git` in `tests/conftest.py`: a real repo on `main` with one commit.
- Decisions made in this breakdown (the design left them to it):
  - **Architecture scope.** An architecture artifact is initiative-scoped (`CommitTarget.plan`), so `sq squash architecture` takes `--plan N`; `design` and `tasks` take `--slice N`. Exactly one is required, matching the subject. No built-in pipeline gets an architecture squash (P2 has no revise loop).
  - **Pipelines that get the step.** P4, P5, P45 (after each of its two loops), P456 and P56 (after the design and tasks loops only), and the batch pipelines `slices-plan` and `tasks-plan` (their loops use `commit_each_iteration: true` per slice, the way P4 and P5 do; the step uses `slice: "{slice.index}"`). P6 and every code-review loop get none (`CommitSubject.CODE` is out of scope).
  - **Pushed-commit check.** A remote ref that contains any commit of the run also contains the run's oldest commit, so checking the oldest commit with `git for-each-ref --contains <sha> refs/remotes` covers the whole run.
  - **Rerun on the same HEAD.** If the backup tag already exists and points at HEAD, reuse it and say so; if it exists and points elsewhere, refuse.
- Next planned work: resume the 400 series (slice 402 implementation).

## Tasks

### Part A: path set extraction

- [ ] **T1: Create the slice branch, then extract and test the subject path set** (Effort 3)
  - [ ] Run `cf config get git.integration_branch` (target is its value, or `main` when empty); create `948-slice.squash-planning-commit-sets-command-and-pipeline-action` from the target, or switch to it if it exists
  - [ ] In `commit_plan.py`, add a public `subject_paths(target, cwd, cf_client)` whose result answers whether a repo-relative path belongs to the target's set: the candidates `_candidates` builds today, or an archived copy of one of its reviews under the rule `_archived_reviews` uses today. It reads no git status, so it does not depend on what is dirty
  - [ ] Rewrite `build_commit_plan` and `_archived_reviews` to use it, so the archive-match rule exists in one place
  - [ ] Add `template_for_subject(subject) -> str` beside `subject_for_template`, derived from `_SUBJECT_BY_TEMPLATE` (no second literal mapping); it raises `UnmappedTemplateError` for `DEVLOG`
  - [ ] Tests in `tests/pipeline/test_commit_plan.py`, with the cf mocks the existing commit-plan tests use:
    1. design and tasks targets contain the artifact, the review file, the slice plan file and `DEVLOG.md`; a path from another slice is not contained
    2. an archived review (`archive/{stem}.md` and `archive/{stem}.{timestamp}.md`) is contained; a sibling file sharing only part of the stem is not
    3. an architecture target contains the architecture file, its review and `DEVLOG.md`
    4. `template_for_subject` round-trips with `subject_for_template` for design, tasks, architecture and code, and raises for devlog
  - [ ] SC: no behavior change for commits: `pytest tests/pipeline/test_commit_plan.py tests/pipeline/test_commit_plan_builder.py tests/pipeline/test_loop_round_commits.py tests/cli/test_commit_run.py` passes, including the new tests
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean; commit `refactor: extract the commit subject path set for reuse by squash`

### Part A: squash core

- [ ] **T2: Types and run detection in `squash.py`** (Effort 3)
  - [ ] Create `src/squadron/pipeline/squash.py` with a module docstring citing slice 948 D1–D4
  - [ ] Define once, in this module:
    1. `SQUASHABLE_SUBJECTS`: `DESIGN`, `TASKS`, `ARCHITECTURE` (every caller validates against this set)
    2. `SquashRefusedError(ValueError)` for every pre-rewrite refusal, and `SquashRewriteError(RuntimeError)` for a failed rewrite (T6); git that cannot run raises the existing `GitEnvironmentError`
    3. a frozen `SquashPlan` with these fields: the run's commits oldest-first (sha, subject), the survivor sha, the parent sha of the oldest commit, the tree id (`HEAD^{tree}` read at plan time, which T6 verifies against), the backup tag name, and a `tag_exists` flag
    4. the backup tag format `squash-backup/{subject}-{index}-{short sha of HEAD}` (D4) as one function
    5. `check_squash_scope(subject, has_slice, has_plan)`, the one subject/scope rule every caller uses: the subject is in `SQUASHABLE_SUBJECTS`; `architecture` needs a plan and no slice; `design` and `tasks` need a slice and no plan. Raises `ValueError` naming the rule
  - [ ] `plan_squash(target: CommitTarget, target_branch: str, cwd: Path, cf_client) -> SquashPlan | None`:
    1. call `check_squash_scope` on the target
    2. build the `CommitTarget` review template with `template_for_subject`, then call `subject_paths`
    3. walk `git rev-list --first-parent HEAD` newest-first; per commit read its parent count and its changed paths (`git diff-tree --no-commit-id --name-only -r -z --root <sha>`); stop at the first merge commit or the first commit with any path outside the set (D1)
    4. trim commits that touch only `DEVLOG.md` from the oldest end of the run (D1)
    5. a run of fewer than two commits returns `None` ("nothing to squash", D2)
    6. otherwise call `_check_refusals` (T4; until then a stub that returns), then return the plan
    7. any `run_git` returning `None` or a non-zero exit raises `GitEnvironmentError` naming the git command and its stderr
  - [ ] Detection reads paths only, never commit subjects (D2)
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean

- [ ] **T3: Test run detection against real repositories** (Effort 2)
  - [ ] Create `tests/pipeline/test_squash_plan.py` built on `temp_git_repo`; add the helper that writes a slice's design, review and DEVLOG files at the paths `subject_paths` returns and commits them to `tests/pipeline/squash_helpers.py` (T5, T7, T9 and T11 import it; no copies), and a shared assertion that `git log` and HEAD are unchanged, called at the end of every test; mock only cf (slice info, slice plan), never git output
  - [ ] Cases:
    1. runs of 2 and 7 commits are found, oldest-first, with the oldest commit as survivor
    2. a run of 1 commit returns `None`
    3. a foreign commit in the middle ends the run; only the newer commits are in it
    4. a merge commit ends the run
    5. a commit touching both the design and the tasks file ends the run
    6. DEVLOG-only commits inside the run stay in it; DEVLOG-only commits at the oldest end are trimmed
    7. an architecture target (`plan` set, no slice) finds its run of architecture-document commits
    8. `check_squash_scope` raises for `code`, for architecture with a slice or without a plan, and for design with a plan
  - [ ] SC: tests pass; commit `feat: find the newest planning commit run for squash`

- [ ] **T4: Refusals: `_check_refusals`** (Effort 2)
  - [ ] In `squash.py`, `_check_refusals(...)` raises `SquashRefusedError` with a message naming the cause, and touches nothing (D3), when:
    1. the working tree is not clean (`git status --porcelain`)
    2. the run's oldest commit has no parent (the run reaches the root)
    3. `current_branch` is not `target_branch`
    4. the oldest commit is in a remote-tracking ref; the message says the check uses refs as of the last fetch and does not contact the remote
    5. the backup tag exists and points somewhere other than HEAD; a tag already at HEAD sets the plan's "tag exists" flag instead
  - [ ] Each refusal logs one WARNING with the same text before raising
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean

- [ ] **T5: Test refusals** (Effort 2)
  - [ ] In `tests/pipeline/test_squash_plan.py`, importing T3's helpers from `tests/pipeline/squash_helpers.py`: each refusal in T4 raises `SquashRefusedError` and logs a WARNING (`caplog`): dirty tree; wrong branch; run reaches the root commit; oldest commit in a remote-tracking ref (create one with `git update-ref refs/remotes/origin/main <sha>`); backup tag pointing elsewhere
  - [ ] SC: tests pass; commit `feat: refuse unsafe squash runs`

- [ ] **T6: The rewrite: `apply_squash`** (Effort 3)
  - [ ] `apply_squash(plan: SquashPlan, cwd: Path) -> str` (the new commit's sha), in `squash.py`:
    1. create the backup tag at HEAD unless the plan says it exists (then log at INFO that the existing tag is reused); log its name at INFO before any rewrite (Failure Modes: the recovery line is always available)
    2. `git reset --soft <parent>`, then `git commit -C <survivor sha>`
    3. compare `HEAD^{tree}` with the plan's tree id
  - [ ] Per D5, `-C` keeps the author date; add no date-rewriting code
  - [ ] On a failed `git commit` (hook, signing, empty commit) or a tree mismatch: log with `logger.exception` (or ERROR with the cause for the mismatch), run `git reset --hard <backup tag>`, then raise `SquashRewriteError` with the cause. If that reset fails too, the error text contains the exact command `git reset --hard <tag>` (D3)
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean

- [ ] **T7: Test `apply_squash`** (Effort 3)
  - [ ] Create `tests/pipeline/test_squash_apply.py` on `temp_git_repo`:
    1. a 7-commit run becomes one commit whose parent is the run's parent, whose tree equals the old HEAD tree, and whose message and author name/email equal the first commit's
    2. the backup tag exists, points at the old HEAD and matches the D4 format
    3. a failing `pre-commit` hook (write an executable `.git/hooks/pre-commit` that exits 1): raises `SquashRewriteError`, HEAD is back at the old HEAD, an ERROR record is logged (`caplog`)
    4. tree mismatch: build a plan, then change the plan's tree id with `dataclasses.replace` before applying; assert restore, raise and the logged record
    5. reusing a pre-existing backup tag at HEAD creates no second tag and logs at INFO that the existing tag was reused
  - [ ] SC: tests pass; commit `feat: squash a planning commit run with a backup tag and restore on failure`

### Part A: CLI command

- [ ] **T8: `sq squash` command** (Effort 2)
  - [ ] Create `src/squadron/cli/commands/squash_run.py`; mount it in `cli/app.py` as a public command (`app.command("squash")`), not hidden
  - [ ] Arguments: `subject`, `--slice N`, `--plan N`, `--dry-run`; validate with `check_squash_scope` and print its message on failure (exit 1)
  - [ ] Read the target with `read_integration_target(ContextForgeClient())`; call `plan_squash`, then `apply_squash` unless `--dry-run`
  - [ ] Output:
    1. no run: `nothing to squash` and exit 0
    2. dry run: the run's commits (short sha and subject, oldest first), the surviving message's first line, and the backup tag it would make; then `dry run: nothing rewritten`
    3. squash: commit count, new short sha, backup tag name, and the `git tag -d` line for removing it later
  - [ ] Refusals, `SquashRewriteError`, `GitEnvironmentError` and `ContextForgeError` print `Error: …` to stderr and exit 1; the environment errors are logged with `logger.exception` at this process boundary, as `branch_run.py` does
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean

- [ ] **T9: Test the command** (Effort 2)
  - [ ] Create `tests/cli/test_squash_run.py` with Typer's `CliRunner`, running in a `temp_git_repo` (chdir via `monkeypatch`) with cf mocked as `tests/cli/test_branch_run.py` does:
    1. squash of a 3-commit run prints the count and backup tag; `git log` shows one commit in place of three
    2. `--dry-run` prints the commits, the survivor message and the tag, and HEAD and the tag list are unchanged; on a 1-commit run it prints `nothing to squash`, exit 0
    3. `sq squash code --slice 1` and `design` with `--plan` and no `--slice` each exit 1 with the scope message
  - [ ] SC: tests pass; commit `feat: add sq squash command`

### Part A: pipeline action and step

- [ ] **T10: `squash` step type and action** (Effort 3)
  - [ ] Add `StepTypeName.SQUASH` and `ActionType.SQUASH` (`"squash"`)
  - [ ] Create `src/squadron/pipeline/steps/squash.py` on the pattern of `steps/branch.py`: keys `subject` (required), `slice`, `plan`; `slice` defaults to `"{slice}"` for design and tasks only (architecture gets no default); after applying the default, validation reports `check_squash_scope`'s message as one error; unknown keys are validation errors; expands to one `squash` action. Register its import in `pipeline/steps/__init__.py`
  - [ ] Create `src/squadron/pipeline/actions/squash.py` on the pattern of `actions/branch.py`:
    1. parse the subject and the slice (`parse_slice_index`) or plan from `context.params`; a bad value is a step failure
    2. run `read_integration_target`, `plan_squash` and `apply_squash` through `asyncio.to_thread`
    3. `SquashRefusedError` and `SquashRewriteError` return `ActionResult(success=False, error=…)`; `GitEnvironmentError` raises past the action and ends the run, as it does for branch
    4. outputs: `squashed` (commit count, 0 for no run), `commit` (new sha or absent), `backup_tag`
  - [ ] Register the action import in `pipeline/executor.py` beside `_a_branch`
  - [ ] Add `_render_squash` to `prompt_renderer.py` and its `_BUILDERS` entry: renders `sq squash <subject> --slice N` (or `--plan N`), with the slice taken from the action config, else the pipeline's `slice` param, as `_render_branch` does
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean

- [ ] **T11: Test the step, action and renderer** (Effort 3)
  - [ ] Step validation (next to the existing branch step tests in `tests/pipeline/steps/`): missing subject, `subject: code`, `subject: architecture` without `plan`, `subject: design` with `plan`, and an unknown key each give one error; a design config expands to one `squash` action with `slice` defaulting to `"{slice}"`; an architecture config with `plan` gets no slice
  - [ ] Action (`tests/pipeline/actions/test_squash_action.py`, on `temp_git_repo`): a planning run is squashed and the outputs carry count, sha and tag; no run succeeds with `squashed: 0`; a refusal (e.g. dirty tree) maps to `ActionResult(success=False)` with the message in `error`
  - [ ] Renderer (`tests/pipeline/test_prompt_renderer.py`): a squash step renders `sq squash design --slice 948`; inside `each` it renders the item's index
  - [ ] SC: tests pass; commit `feat: add squash pipeline step and action`

- [ ] **T12: Add the step to the built-in pipelines** (Effort 2)
  - [ ] Insert `- squash: { subject: design }` or `{ subject: tasks }` directly after each planning loop, before the next step:
    1. `P4.yaml`: after the loop, subject design
    2. `P5.yaml`: after the loop, subject tasks
    3. `P45.yaml`: after `revise-design` (design) and after `revise-tasks` (tasks)
    4. `P456.yaml`: after `revise-design` and after `revise-tasks` only; nothing after `revise-code`
    5. `P56.yaml`: after `revise-tasks` only; nothing after `revise-code`
    6. `slices-plan.yaml`: inside the `each` body after its loop, `{ subject: design, slice: "{slice.index}" }`
    7. `tasks-plan.yaml`: inside the `each` body after its loop, `{ subject: tasks, slice: "{slice.index}" }`
  - [ ] `P6.yaml`, `implement.yaml` and `implement-plan.yaml` are unchanged
  - [ ] SC: `pytest tests/pipeline/test_loader_integration.py tests/pipeline/test_builtin_pipelines.py` passes (`load_pipeline` and `validate_pipeline` accept every built-in pipeline; the code-pipeline parity test is unaffected)

- [ ] **T13: Test pipeline placement and dry run** (Effort 2)
  - [ ] In `tests/pipeline/test_builtin_pipelines.py`: one parametrized test asserting, for each pipeline in T12, that a `squash` step with the expected subject directly follows each named planning loop, and that no `squash` step follows a code-review loop
  - [ ] `sq run P4 <n> --dry-run` (via the existing dry-run test helpers in `tests/pipeline` or `tests/cli`) lists the squash step and leaves `git log` of a `temp_git_repo` unchanged; add a squash line to `render_steps` in `cli/commands/run_dry_run.py` only if the generic rendering omits it
  - [ ] SC: tests pass; commit `feat: squash planning commit runs after revise loops in built-in pipelines`

### Part A: documentation

- [ ] **T14: Document squash** (Effort 1)
  - [ ] `docs/PIPELINES.md`: a `### squash` section after `### branch` in the Step Type Catalog: purpose, syntax (`subject`, `slice`, `plan`), the run rule (D1), refusals (D3), backup tags and how to list and delete them (D4), and that pipeline `--dry-run` runs no git. Mention in `### Commits` that the built-in planning pipelines squash each loop's commits
  - [ ] `README.md` command list (if it lists `sq` commands): add `sq squash`
  - [ ] `CHANGELOG.md` `[Unreleased]`: one short user-facing bullet under `### Added` for `sq squash` and the pipeline step
  - [ ] SC: commit `docs: document sq squash and the squash pipeline step`

### Part B: `sq metr`

- [ ] **T15: Mount `metr` as a hidden alias** (Effort 1)
  - [ ] In `cli/app.py`, beside `app.add_typer(metrology_app, name="metrology")`, add `app.add_typer(metrology_app, name="metr", hidden=True)` (D7)
  - [ ] Test in `tests/metrology/test_cli.py`: `sq metr --help` lists the same subcommands as `sq metrology --help`; `sq metr list` and `sq metrology list`, run against the temp store the existing `list` tests use, produce identical output; in `sq --help` a line starting with `metrology` appears and no line starts with `metr` followed by whitespace (`metr` is a substring of `metrology`, so match line-start tokens, not substrings)
  - [ ] `CHANGELOG.md` `[Unreleased]`: one bullet under `### Added`
  - [ ] SC: `ruff format`, `ruff check`, `pyright` clean; tests pass; commit alone as `feat: accept sq metr as shorthand for sq metrology` so it reverts on its own

### Validation

- [ ] **T16: Full validation** (Effort 1)
  - [ ] `ruff format`, `ruff check`, `pyright` (zero errors), full `pytest`
  - [ ] Live check, never in this checkout: `git clone` this repo into a temp directory, make three commits there that each touch only slice 948's design file and `DEVLOG.md`, run `sq squash design --slice 948 --dry-run`, then without `--dry-run`; confirm `git log` shows one commit in place of three and `git tag -l 'squash-backup/*'` shows the tag. Delete the temp directory afterwards
  - [ ] SC: all pass; fixes needed here are committed as `fix:` on the slice branch
  - [ ] Write the DEVLOG entry for Phase 6 and commit it on the slice branch
