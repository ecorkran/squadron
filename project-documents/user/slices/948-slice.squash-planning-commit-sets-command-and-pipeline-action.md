---
docType: slice-design
slice: squash-planning-commit-sets-command-and-pipeline-action
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261025
dateUpdated: 20261025
status: complete
---

# Slice Design: Squash Planning Commit Sets — Command and Pipeline Action

## Overview
Fixes [issue #257](https://github.com/ecorkran/squadron/issues/257) (the squash command) and [issue #258](https://github.com/ecorkran/squadron/issues/258) (the pipeline action). A planning artifact (slice design, task breakdown, architecture) accumulates a commit set: create, review, revise, and one commit per loop round. The reviews are archived in files, so the intermediate commits only add noise to `git log`. Slice 402's task file has seven commits. This slice collapses the newest such set into one commit, from a command and from a pipeline step that runs when the loop ends.

## Value
`git log --oneline` reads as one line per artifact. Today it takes a hand-run rebase (slice 400 was done that way, 7 commits twice), and nothing tells an agent to do it. A deterministic step means no model call, no judgement, and no forgotten cleanup.

## Technical Scope
In scope:
- `sq squash <kind> <index> [--dry-run]`, where kind is `slice` (slice design), `tasks` (task breakdown), `arch` (initiative architecture) or `plan` (initiative slice plan), and index is the slice index for `slice`/`tasks` and the initiative index for `arch`/`plan` (`--dry-run` prints the commits in the run, the surviving message, and the backup tag it would make, and rewrites nothing). `arch` covers the architecture document only; folding the slice plan into it may come later.
- A `squash` pipeline action over the same function, added to the planning pipelines after their revise loop.
- Prompt-only runs call the same command, as they do for commit and branch.
- Part B, unrelated and tiny: `sq metr` accepted as a shorthand for `sq metrology` (D7).

Out of scope:
- Code commits (`CommitSubject.CODE`). Slice branches are not planning sets.
- Sets in the middle of history. The command takes the newest run ending at HEAD only. Older sets stay a manual job.
- Pushing, and squashing anything already on a remote.
- A `cf` command. The file set comes from squadron's `commit_plan`, so squadron owns it.

## Dependencies
### Interfaces Required
- `commit_plan.py`: the artifact's path set (the design, tasks or architecture file, its reviews, its archived reviews) plus `DEVLOG.md`, which every planning commit may touch. Today `_candidates` is private and filters by dirty state; this slice extracts a pure "paths for this subject and slice" function that the commit plan and the squash both call, so the two cannot drift.
- `git_ops.read_integration_target`, `git_ops.current_branch`, `review.git_utils.run_git`.
- The action registry (`ActionType`, `register_action`) and the `commit`/`branch` actions as the pattern.

## Architecture
### Component Structure
- `squadron/pipeline/squash.py` (new): `plan_squash(...)` finds the run and checks every refusal; `apply_squash(plan)` rewrites. Both take the target and cwd as arguments.
- `squadron/pipeline/actions/squash.py` (new): the action, validation of `subject`, calls the same two functions through `asyncio.to_thread`.
- `squadron/cli/commands/squash_run.py` (new): the command, mounted in `cli/app.py` like `commit_run`.
- `commit_plan.py`: the extracted path-set function.
- `ActionType.SQUASH`; one `squash` step after the loop in the planning pipelines (the design lists which, see D6).

### Data Flow
`sq squash tasks 402` → path set for (tasks, 402) → walk first-parent commits back from HEAD while every changed path is inside the set → run of N commits → checks → backup tag → `git reset --soft <parent of the run's first commit>` → `git commit -C <first commit>` → compare tree ids → report.

## Technical Decisions
### D1 The run is anchored at HEAD, so no rebase is needed
The run is the newest consecutive commits whose paths all fall inside the artifact's set, stopping at the first commit outside it or at any merge commit. Because the run ends at HEAD, the rewrite is `reset --soft` to the commit before the run, then one commit that reuses the first commit's message and author (`-C`). No interactive rebase, no sequence-editor script, no `--rebase-merges`: nothing above the run exists, so merge topology, which slice-range resolution reads (403), cannot change. A commit that touches two artifacts ends the run; it and everything older stay as they are. The run's first (oldest) commit must touch the artifact file itself: leading commits that touch only `DEVLOG.md`, the slice plan or a review are trimmed off, so an unrelated DEVLOG or plan commit can never become the survivor (found in the live check: plan-only commits were folded under a slice squash). DEVLOG-only commits inside the run are folded in, which is accepted.

### D2 Detection is by file, never by subject
Commit subjects are labels and drive nothing. A run of fewer than two commits is a successful no-op, reported as "nothing to squash".

### D3 Refusals are explicit failures
Before the rewrite, each of these stops with an error that names the cause, and nothing is touched:
- the working tree is not clean;
- the run reaches the root commit, so there is no parent to reset to;
- HEAD is not on the target (`git.integration_branch`, or `main`);
- any commit in the run is contained in a remote-tracking ref. The check uses local refs as of the last fetch and does not contact the remote, so it cannot hang; the message says so;

After the rewrite, the tree id is compared with the one taken before. A mismatch, or a failed `git commit` (pre-commit hook, signing, empty commit), is handled the same way: the command runs `git reset --hard <backup tag>` itself (safe, the tree was clean) and exits non-zero with the cause. If that restore also fails, the error prints the exact recovery command (`git reset --hard <tag>`). A rewritten history is therefore never left behind by a failure.

### D4 Backup tag
Before rewriting, a tag `squash-backup/{kind}-{index}-{short-sha-of-HEAD}` points at the old HEAD. It is never deleted by the command and is named in the output. Tags are local; a rerun on the same HEAD finds the tag already present and says so. Tags accumulate by design: one per squash, listed with `git tag -l 'squash-backup/*'`, deleted by hand with `git tag -d`. No cleanup command; they are small and the cost is a long tag list.

### D5 Survivor
The first commit's message, author and author date are kept (the issue's rule; `git commit -C` keeps all three). The committer date is the squash time.

### D6 Pipeline placement
The action takes `kind` as a step param written in the YAML (`slice` for a design loop, `tasks` for a tasks loop) and its `index` from the `{slice}` pipeline param by default, the way the loop's own `review:` step already does. Inside an `each` step that param is the current item, so several slices are squashed one after another, each on its own run, and one refusal fails only that item's step. The action runs after the revise loop and before the next phase. A loop that ends on `on_exhaust: checkpoint` pauses before the squash step, so nothing is squashed until a person resumes. The action finds its run by the same file rule as the command, not by "commits since the step started", which answers #258's open question: the loop's commits are the newest run by construction. Any refusal fails the step. The step goes after each planning loop in P4, P5, P45 (two), P456 (design and tasks loops) and P56 (tasks loop). P6's loops, the code-review loops in P456 and P56, and the batch pipelines `slices-plan` and `tasks-plan` are checked in the task breakdown; a batch loop gets the step only if its loop commits per artifact the way P4 and P5 do. Pipeline `--dry-run` lists the step and runs no git.

### D7 `sq metr` is a hidden second mount, not a new group
`app.add_typer(metrology_app, name="metr", hidden=True)` beside the existing line in `cli/app.py`. Same Typer object, so every present and future metrology subcommand works under both names with no per-command code, and `--help` still lists one group. No alias table and no prefix matching: other prefixes (`metro`, `met`) are not accepted. One test runs `sq metr --help` and one real subcommand and checks the output matches `sq metrology`. The slash commands and docs keep the full name.

## Failure Modes
- Git cannot answer (timeout, bad cwd): `run_git` returns `None`; the command fails with that cause and exits non-zero. No silent skip.
- Process killed between the reset and the commit: HEAD sits on the run's parent with the old tree staged. The backup tag already exists, and its name is printed before the rewrite starts, so the recovery line (`git reset --hard <tag>`) is always available.
- `git commit` fails after the reset: restored automatically (D3).
- Every failure above is logged (`logger.exception` for caught errors, WARNING for refusals) and carried in the exit code or step failure. Tests assert the log record (`caplog`) for the commit-failure, tree-mismatch and root-commit cases.
- Remote-ref state is stale: a commit pushed from elsewhere and not yet fetched is not seen. Stated in the refusal text; accepted.

## Tests
Real temporary git repositories, no mocked git output, because tests that feed git parsers hand-written output are what hid the dead merge-commit grep in `_find_merge_commit` (process journal, #14). Cases: run of 2, 7 and 1 commits; a foreign commit in the middle ends the run; a merge commit ends the run; a pushed commit refuses; dirty tree refuses; wrong branch refuses; tree-identity check trips on a forced difference; DEVLOG-only touches stay in the set; first message and author survive; `--dry-run` rewrites nothing; the action fails the step on refusal and succeeds on no-op.

## Verification Walkthrough
Run in a throwaway clone, never in a working checkout. `sq` resolves the slice through `cf`, so the clone must be a registered cf project with the slice plan set; the steps register it and remove it afterwards.

```bash
git clone -q -b main <squadron checkout> /tmp/sq-live && cd /tmp/sq-live
cf init --lite --name sq-squash-live-check
cf set plan 900-slices.maintenance-and-refactoring
D=project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md
for i in 1 2 3; do echo "live edit $i" >> $D; echo "live $i" >> DEVLOG.md; git add -A; git commit -qm "docs: live check round $i"; done
sq squash slice 948 --dry-run
```
Expected (shas differ):
```
run of 3 commits (oldest first):
  c060d29c docs: live check round 1
  11d05219 docs: live check round 2
  ce5bf060 docs: live check round 3
surviving message: docs: live check round 1
backup tag: squash-backup/slice-948-ce5bf060
dry run: nothing rewritten
```
Then:
```bash
sq squash slice 948               # squashed 3 commits into <sha>, backup tag, git tag -d line
git log --oneline -2              # one "docs: live check round 1" above the previous main tip
git diff squash-backup/slice-948-<sha> HEAD   # empty: the tree is unchanged
sq squash slice 948               # nothing to squash
cf project rm sq-squash-live-check -y
```
Caveats found while verifying: without the cf registration the command exits 1 with cf's `PROJECT_NOT_FOUND` error (and logs the traceback); the run stops at the commit before the three because that one touches the 948 tasks file, which is outside the design's path set.

## Complexity
Effort 3/5, Risk Medium. Three new modules (`pipeline/squash.py`, the action, the CLI command) plus one extraction from `commit_plan.py`, all outside the metrology and review paths. Part B lands as its own commit and reverts alone. The risk is the history rewrite, which D1 reduces to one soft reset and D3/D4 make recoverable.

## Sequencing relative to the 400s
Independent of them in code. It touches `ActionType`, `cli/app.py`, two pipeline YAMLs and CHANGELOG, none of which 400-series work owns. Run it before resuming the 400s: it is a rewrite of the target's tail, so it should not run while another worktree commits planning work to the same branch, and it then tidies the 400s' own planning sets as they land.
