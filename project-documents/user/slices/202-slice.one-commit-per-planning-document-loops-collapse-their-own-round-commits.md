---
docType: slice-design
slice: one-commit-per-planning-document-loops-collapse-their-own-round-commits
project: squadron
parent: user/architecture/180-slices.pipeline-intelligence.md
dependencies:
- 196
interfaces: []
dateCreated: 20261101
dateUpdated: 20261101
status: not_started
turns: 67
promptTokens: 4415860
cachedTokens: 4281548
cacheWriteTokens: 134218
completionTokens: 39716
durationSeconds: 419.2
costUsd: 2.725109
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 2.725108900000001
    completionTokens: 39716
revision_number: 2
---

# Slice Design: One Commit Per Planning Document — Loops Collapse Their Own Round Commits

## Overview

Planning pipelines (P4, P5, P45, P456, P56, P2, `tasks-plan`, `slices-plan`) commit once for the phase step and once per review round (`commit_each_iteration: true`). A design that takes two revisions leaves three commits; the guide's rule is one commit per planning document, made when its review loop finishes. Slice 948 tried to fix this after the fact (`sq squash`) by inferring commit runs from file path sets, and was removed in 0.24.12 because inference broke on ordinary history.

This slice moves the job to the one place that knows which commits are its own: the loop. A `commit_each_iteration` loop keeps a ledger of the commits it makes (plus the phase step commit immediately before it). When the loop completes, it replaces exactly those commits with one commit carrying the same tree, if and only if it can prove they are still the tail of the branch, unpublished and unmixed. Otherwise it leaves history alone and logs one warning line. Fixes [issue #257](https://github.com/ecorkran/squadron/issues/257).

## Value

- `git log --oneline` on the target reads one line per planning document (`docs: add slice 202 design (review: PASS)`) instead of add/revise/re-review sets. No more manual squashing after each pipeline run.
- No inference. The rewrite covers only commits whose shas the loop recorded as it made them, so the 948 failure class (a guessed commit run that includes someone else's work) can't happen.
- Per-round history still exists while the loop runs, so the findings-addressed gate keeps its prior-round base. After collapse it stays reachable through a backup ref, so review files' `reviewedSha` stamps keep resolving.

## Technical Scope

Included:
- A commit ledger for `commit_each_iteration` loops (multi-step `loop:` bodies, `_execute_loop_body`): base sha, the included phase commit, and each round commit sha in order.
- Ledger persistence in the run state file, so a paused loop that is resumed (more rounds, or `--decision accept`) still collapses everything it made.
- The collapse: proof checks, backup ref, one new commit with the identical tree, compare-and-swap update of the branch.
- The surviving commit message, built from the collapsed range with the existing message composer.
- One observable signal per outcome: an INFO line on success and a WARNING line naming the reason for each refusal.
- Commit action outputs gain the commit's subject and scope, so the loop can prove the preceding phase commit is about the same document.

Excluded:
- Code loops (`revise-code`, round subject `code`). They commit on the slice branch, whose history the merge keeps. Collapsing implementation history is a separate decision and is not part of #257.
- Loops whose body commits by itself rather than through `commit_each_iteration`. Validation already makes the two mutually exclusive, and only `commit_each_iteration` commits are recorded.
- `--prompt-only` loops. Loops are not rendered in prompt-only mode yet (#145).
- Collapsing across loops or across documents. Each loop collapses only its own document's commits.
- Pruning backup refs. They are listed and deleted with plain git (`git for-each-ref refs/squadron/pre-collapse`, `git update-ref -d`).

## Dependencies

### Prerequisites
- Slice 196 (complete): scoped phase and round commits, `round_commit_params`, `compose_message`, `subject_paths`, and the commit action's `sha` output.
- Slice 176 / 915 (complete): loop rounds persisted as `prior_round_results`, resume at a recorded round, `--decision accept`.

### Interfaces Required
- `CommitAction` outputs (`pipeline/actions/commit.py`): `committed`, `sha`, `message`. This slice adds `commit_subject` and the scope key (`slice` or `plan`).
- `round_commit_params` (`pipeline/loop_commit.py`): the subject and scope every round of the loop commits under.
- `compose_message`, `StagedFacts`, `ArtifactChange` (`pipeline/commit_message.py`), `subject_paths` and `read_review_verdict` (`pipeline/commit_plan.py`).
- `StepState` / `StepResult` and `StateManager` (`pipeline/state.py`, `pipeline/models.py`), plus `run_git` (`review/git_utils.py`).
- `read_integration_target` (`pipeline/git_ops.py`): the target collapse runs on.

## Architecture

### Component Structure

```
executor._execute_loop_body           (existing; gains ledger recording at the round commit)
        │
        ▼
pipeline/loop_ledger.py      LoopCommitLedger: base_sha, commits[], unprovable;
                             open_ledger(), carried_ledger()  — pure data + state I/O
pipeline/loop_collapse.py    collapse_loop_commits(ledger, target, cwd, cf_client)
                             -> CollapseOutcome; proof checks, message, git writes
        │
        ├── commit_message.compose_message   (unchanged, reused)
        ├── commit_plan.subject_paths / read_review_verdict (reused)
        └── review.git_utils.run_git
```

`executor.py` is already far past the size guideline, so it gets only call sites: open or carry the ledger at loop start, append after each successful round commit, and call `collapse_loop_commits` once when the loop returns COMPLETED. All logic is in the two new modules.

### Data Flow

1. **Loop start (fresh).** If the loop has `commit_each_iteration: true` and its round subject is not `code`, read `HEAD` as `start_head`. Find the newest commit result in `prior_outputs` that has `committed: true`. If its `sha == start_head` and its `commit_subject` and scope equal the loop's `round_commit_params`, the phase commit is included: `commits = [start_head]`, `base_sha = start_head^`. Otherwise `commits = []` and `base_sha = start_head`, and a WARNING records why the phase commit was left out (only if a phase commit exists but doesn't match).
2. **Loop start (resumed).** When the executor resumes this loop step (`start_from`, or a `--decision accept` resume), the ledger comes from the step's latest record in the run state, using the same lookup as `resume_iteration_for`. If that record exists but has no ledger (a state file written before this slice), the ledger is marked `unprovable` and collapse refuses later.
   An item rerun (`sq run --resume <run-id> --item N --decision retry|accept`, slice 197) is not a carried resume. `resume_item` returns git to the target first, then runs the `each` body fresh, so the loop opens a new ledger. Commits from the flagged attempt stay as they are, and the rerun collapses only what it commits itself. With `--decision accept`, the loop runs no rounds and collapses nothing. If the checkout is somehow not on the target, collapse refuses (D3.2).
3. **Each round.** After the round's commit action succeeds with `committed: true`, append its `sha`. A sha of `unknown` (HEAD unreadable after the commit) marks the ledger `unprovable`. `committed: false` rounds add nothing.
4. **Every return.** The ledger is attached to the StepResult on every exit path (completed, paused, failed, skipped), so a pause persists it for the resume.
5. **Loop completed** (`until` met, accepted on exhaustion, or accepted by decision): run `collapse_loop_commits`. With fewer than two commits in the ledger there is nothing to collapse, and the outcome is `nothing_to_collapse` (no log line). PAUSED, FAILED and SKIPPED loops never collapse: their per-round history is the diagnosis.
6. **Collapse.** Proof checks (D3), then backup ref, new commit, compare-and-swap (D2). The outcome is logged.

### State Management

`StepResult` and `StepState` gain one optional field, `loop_commits: LoopCommitLedger | None` (default `None`, so older state files load). Ledger fields:

| Field | Meaning |
|---|---|
| `base_sha` | parent of the oldest commit the loop may collapse |
| `commits` | collapsible shas, oldest first (phase commit first when included) |
| `unprovable` | `True` when the ledger cannot vouch for its own list (resumed state with no ledger, or an unreadable commit sha) |

The ledger is cumulative: a resumed loop continues the list it carried, and each record of the step holds the whole list so far.

## Technical Decisions

### D1 — The loop records its own commits; nothing is inferred
Status: decided
- The ledger is filled only from commit action results the loop itself received, plus a phase commit proven by sha equality with `HEAD` at loop start and matching subject and scope. Subjects and messages are never parsed.
- Rejected: reconstructing from `prior_round_results` action dicts on resume. Inside `each`, the same loop step name recurs per item, and the phase-commit decision made at first start would be lost. One explicit cumulative ledger is simpler to prove.

### D2 — Mechanism: `commit-tree` plus compare-and-swap `update-ref`
Status: decided
- `new = git commit-tree <HEAD>^{tree} -p <base_sha> -F <message>`, then `git update-ref -m "squadron: collapse loop <step>" refs/squadron/pre-collapse/<new> <old_head>`, then `git update-ref -m "squadron: collapse loop <step>" HEAD <new> <old_head>`.
- Why: the tree is identical to the pre-collapse tree by construction. The index and working tree are never touched, so an operator's staged or unstaged edits survive and no clean-tree precondition is needed. The final `update-ref` with an expected old value is atomic: if `HEAD` moved after the checks, git refuses and nothing changes.
- Rejected: `git reset --soft` plus `git commit` (948's mechanism). It commits whatever else is in the index, and a failed commit hook leaves `HEAD` reset with changes staged. Commit hooks don't run under `commit-tree`. That's acceptable: the tree is byte-identical to round commits that already passed them.
- A timeout on either `update-ref` raises `GitStateUnknownError`, the commit action's existing D6 behavior. A refused swap is a `refused` outcome (HEAD moved after the checks instead of before them).
- **Architecture exception.** Moving the target's HEAD to a new commit with a different parent is a reset in effect. 180-arch's Git-Mutating Steps section records this as the one exception to "never force, reset": the commits must be the loop's own recorded, unpublished tail on the target (D3), the tree must be identical, and the swap must be a compare-and-swap, with a backup ref kept. It applies to the target only.

### D3 — What "provably ours" means
Status: decided
All of the following must hold, checked in this order. The first failure gives the `refused` outcome, and its reason goes in the WARNING line:
1. The ledger is not `unprovable`.
2. The current branch is the target (`read_integration_target`). A detached HEAD fails this check.
3. `HEAD == commits[-1]`.
4. `git rev-list --first-parent <base_sha>..HEAD` equals `reversed(commits)` exactly. Check 3 alone is not enough: an operator commit made during a pause becomes the parent of the next round commit, so HEAD still equals the loop's last commit while a foreign commit sits in the middle. A merge or an amend also fails this check, because the loop's own commits are never merges.
5. `git for-each-ref --contains <commits[0]> refs/remotes` is empty. Checking the oldest commit is enough, since it is an ancestor of every other.
- Any git command failing during the checks produces `git_failed` with the command text.

### D4 — Surviving commit message
Status: decided
- Reuse `compose_message` with `round = 0` and `StagedFacts` derived from the collapsed range instead of the index. `git diff --name-status <base_sha> HEAD` limited to `subject_paths` gives artifact ADD (status `A`) or REVISE (`M`) and whether a review file is in the range. The verdict is the newest review file's frontmatter verdict, read with `read_review_verdict`.
- Result: `docs: add slice 202 design (review: PASS)` when the phase commit is included, and `docs: revise slice 202 design (review: CONCERNS)` when only rounds are collapsed or the phase step revised an existing document. The message describes the commit's contents by the same rule as every other pipeline commit, with no second template.
- Rejected: keeping the first commit's message (the issue's proposal). Its verdict clause names the first review, not the final one.
- Rejected: keeping the last round's message and rewriting its verb. A round message can be `docs: revise …, round 2` or `review: re-review …`, so turning it into `add` means parsing and editing message text. That uses labels as logic. Composing from facts reuses the existing rule.

### D5 — Backup ref kept for every collapse
Status: decided
- `refs/squadron/pre-collapse/<collapsed-sha>` points at the pre-collapse head. This covers the issue's "tag a backup" requirement and keeps the round commits reachable, so `reviewedSha` stamps in the collapsed rounds' review files, and the findings-addressed audit's prior shas, keep resolving for `sq review resolve` and metrology.
- A ref outside `refs/heads` and `refs/tags` is not pushed by a normal `git push` or listed by `git branch`/`git tag`.
- If writing the backup ref fails, there's no rewrite (`git_failed`).

### D6 — Collapse never changes the loop's status
Status: decided
- A refusal or git failure in collapse leaves the loop COMPLETED and the pipeline continues. Tidy history isn't worth failing a document whose review passed. `GitStateUnknownError` is the one exception: it propagates like it does from a commit, because later commits would build on an unknown ref state.
- This is consistent with 180-arch's "when the repository state can't be verified, the run stops": the run stops only when a ref write may have happened. Each other failure leaves the repository in a known state:
  - A failed or timed-out read-only check (`rev-parse HEAD`, `rev-list`, `for-each-ref`) is `git_failed` and the run continues. No write has happened, so the refs are exactly what the loop's own commits left.
  - A failed or timed-out `commit-tree` is `git_failed` and the run continues. At most it leaves an unreferenced object, and no ref has moved.
  - A crash or failure between the backup-ref write and the HEAD swap leaves `refs/squadron/pre-collapse/<new>` pointing at the unchanged pre-collapse head. HEAD is untouched and the ref is harmless, so no handling is needed.

### D7 — Scope by round subject
Status: decided
- Collapse applies when the loop's round subject (`round_commit_params`) is `design`, `tasks` or `architecture`. A `code` subject gets no ledger. The check uses the `CommitSubject` enum, not names or labels.

### D8 — No configuration switch
Status: decided
- Collapse is how `commit_each_iteration` loops finish. There's no opt-out key: the guide's rule has no exception, and the backup ref already preserves round history. Revisit only with a concrete need.

### Patterns and Conventions
- `CollapseOutcome` (StrEnum): `collapsed`, `nothing_to_collapse`, `refused`, `git_failed`. A `refused` or `git_failed` result also carries a reason string for the WARNING line. Tests branch on the enum and on git state, never on log text.
- Log lines, one per outcome:
  - INFO `loop {step}: collapsed {n} commits into {short} "{message}" (pre-collapse head: refs/squadron/pre-collapse/{short})`
  - WARNING `loop {step}: left {n} commits uncollapsed: {reason text}`, e.g. `HEAD is {x}, the loop's last commit is {y}`, or `{sha} is on {remote ref}`.
- `nothing_to_collapse` is silent: it's the normal single-commit outcome.

## Implementation Details

### Migration Plan
- `StepState.loop_commits` defaults to `None`. State files from before the slice load, and a resume against one is refused (D3.1) with history untouched.
- Commit action outputs gain keys and lose none. Readers that ignore unknown output keys are unaffected.
- Pipeline YAML is unchanged. Every built-in planning loop collapses once the slice ships.

## Integration Points

### Provides to Other Slices
- None. The ledger and collapse function are internal to loop execution.

### Consumes from Other Slices
- 196's commit plan and message composer, unchanged apart from the extra output keys.
- 183 (findings ledger, not built) reads `reviewedSha` diffs between rounds. D5 keeps those shas reachable, so 183 has no collapse-related work beyond one rule: reachable is not in `base..HEAD`. After a collapse the round shas fall outside that range, so 183 must diff by sha, never by `<sha>..HEAD`.
- Range-membership consumers, such as `sq pr create` (`src/squadron/pr/inputs.py` selects reviews by membership in `base..head` and skips an out-of-range sha silently), are out of scope for planning documents. Design reviews are committed on the target before a slice branch forks, so the collapse never changes what those consumers see.

## Success Criteria

### Functional Requirements
- A P4 run on a fresh slice whose design passes after two revisions leaves one commit on the target for the design and its reviews, with message `docs: add slice {n} design (review: PASS)`, and the same tree the per-round commits produced.
- A loop skipped by `skip_if_met`, or one with a single commit, leaves history unchanged and logs nothing about collapse.
- A loop accepted on exhaustion collapses. A loop that pauses, fails or is skipped on exhaustion does not.
- A loop paused at a checkpoint and resumed with `--decision accept`, or resumed for more rounds, collapses the phase commit and every round from both executions.
- Each refusal in D3 leaves history byte-identical, and logs one WARNING line naming the reason and the shas involved.
- An item rerun (`--item N --decision retry`) collapses only the commits it makes itself and leaves the flagged attempt's commits unchanged. With `--decision accept`, it collapses nothing.
- Staged and unstaged operator changes present during collapse are still staged or unstaged, unchanged, afterwards.
- `refs/squadron/pre-collapse/{collapsed-sha}` exists after every collapse and points at the pre-collapse head.
- Code loops (`revise-code`) never collapse.

### Technical Requirements
- New logic lives in `pipeline/loop_ledger.py` and `pipeline/loop_collapse.py`, each under ~300 lines. `executor.py` gains call sites only.
- Tests use real temporary git repositories, no git mocks, for every `CollapseOutcome`, the backup ref, the CAS race (move HEAD between check and swap), a remote-tracking ref containing a ledger commit, and index and working-tree preservation.
- An executor-level test runs a scripted loop (stub dispatch and review actions) through two rounds plus a pause and resume, and asserts the single resulting commit. A second test runs an `each` item rerun with `retry` and with `accept` and asserts the item-rerun criterion above.
- `ruff format`, `ruff check`, `pyright` with zero errors, and the full test suite pass.
- A CHANGELOG bullet: planning loops now leave one commit per document.

### Integration Requirements
- The findings-addressed gate's per-round base (`review/addressed/screens.py`) behaves exactly as before during the loop.
- `sq review resolve` against a collapsed round's review file resolves its `reviewedSha` through the backup ref.

### Verification Walkthrough

Run in a scratch clone of a cf project on its target branch, with a slice that has no design yet (`{n}` below).

1. Collapse on a normal run:
   ```bash
   sq run P4 --slice {n} -v
   git log --oneline -3
   ```
   Expected: the run log has `loop revise-design: collapsed 3 commits into abc1234 "docs: add slice {n} design (review: PASS)"`, and `git log` shows that single commit at the top. If the first review passes, the loop is skipped, no collapse line appears, and there is one commit anyway.
2. Backup ref and round history:
   ```bash
   git for-each-ref refs/squadron/pre-collapse
   git log --oneline <base>..refs/squadron/pre-collapse/abc1234
   git diff abc1234 refs/squadron/pre-collapse/abc1234   # empty: identical tree
   ```
3. Resume after a checkpoint: run P4 with `--param max-revisions=1` and a review model strict enough to exhaust, so the run pauses. Then:
   ```bash
   sq run --resume <run-id> --decision accept
   git log --oneline -3
   ```
   Expected: one commit spanning the phase commit and the round from before the pause.
4. Refusal: repeat step 3, but make an unrelated commit (`git commit --allow-empty -m "chore: unrelated"`) before resuming. Expected: `loop revise-design: left 2 commits uncollapsed: HEAD is <x>, the loop's last commit is <y>`, and history unchanged.

## Risk Assessment

### Technical Risks
- Rewriting the target's tail during an unattended run (`implement-plan`, `tasks-plan` batches) while someone else commits to the same branch.

### Mitigation Strategies
- Squadron against squadron: the per-checkout run lock (197) already allows only one git-mutating run at a time.
- Squadron against an operator's manual commit: the final write is a compare-and-swap on `HEAD` (D2), and the proof (D3) requires the exact recorded chain, so a concurrent commit gives `refused`, never a lost commit. The backup ref makes every collapse reversible with one `git update-ref`.

## Implementation Notes

### Development Approach
1. Commit action outputs: add `commit_subject` and scope, with a test.
2. `loop_ledger.py`: the ledger model, phase-commit matching, and carry-forward from state. Add `StepState`/`StepResult` fields and test that old files load.
3. `loop_collapse.py`: proof checks, message, writes, and outcomes, tested against temp git repos.
4. Executor call sites: open or carry, record, attach on every return, collapse on COMPLETED. Then the scripted-loop executor test, including resume.
5. Live walkthrough steps 1–4 on a scratch project, then the CHANGELOG bullet.

### Special Considerations
- Inside `each` (`tasks-plan`, `slices-plan`), each item's loop gets its own ledger. Carry-forward applies only to the loop invocation the executor resumes, so one item never inherits another item's ledger.
- `commit-tree` uses the current git identity and time, the same as a pipeline commit.
