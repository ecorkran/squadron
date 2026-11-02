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
status: complete
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
- No inference. The rewrite covers only commits the loop's own actions made, proven by an unbroken chain of HEAD stamps, so the 948 failure class (a guessed commit run that includes someone else's work) can't happen.
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
- Loops whose body commits by itself rather than through `commit_each_iteration`. Validation already makes the two mutually exclusive, and only `commit_each_iteration` loops keep a ledger.
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
pipeline/head_stamp.py       stamps dispatch and commit results with the HEAD before and after
pipeline/loop_ledger.py      LoopCommitLedger: base_sha, tip_sha, commit_count, unprovable;
                             open_ledger(), claim_actions(), start_ledger()  — data + state I/O
pipeline/loop_collapse.py    collapse_loop_commits(ledger, target, cwd, cf_client)
                             -> CollapseOutcome; proof checks, message, git writes
        │
        ├── commit_message.compose_message   (unchanged, reused)
        ├── commit_plan.subject_paths / read_review_verdict (reused)
        └── review.git_utils.run_git
```

`executor.py` is already far past the size guideline, so it gets only call sites: open or carry the ledger at loop start, append after each successful round commit, and call `collapse_loop_commits` once when the loop returns COMPLETED. All logic is in the two new modules.

### Data Flow

1. **Loop start (fresh).** If the loop has `commit_each_iteration: true` and its round subject is not `code`, read `HEAD` as `start_head`. Find the newest commit result in `prior_outputs` that has `committed: true`. If its `sha == start_head` and its `commit_subject` and scope equal the loop's `round_commit_params`, the phase commit is included. `base_sha` is the HEAD the phase dispatch started from, when that dispatch's `head_after` equals the commit's `head_before` (the agent's own commits before the phase commit), else the commit's `head_before`. `tip_sha = start_head`, and `commit_count` is `git rev-list --count base..start_head`. Otherwise the ledger is empty (`base_sha = tip_sha = start_head`), and a WARNING records why the phase commit was left out (only if a phase commit exists but doesn't match).
2. **Loop start (resumed).** When the executor resumes this loop step (`start_from`, or a `--decision accept` resume), the ledger comes from the step's latest record in the run state, using the same lookup as `resume_iteration_for`. If that record exists but has no ledger (a state file written before this slice), the ledger is marked `unprovable` and collapse refuses later.
   An item rerun (`sq run --resume <run-id> --item N --decision retry|accept`, slice 197) is not a carried resume. `resume_item` returns git to the target first, then runs the `each` body fresh, so the loop opens a new ledger. Commits from the flagged attempt stay as they are, and the rerun collapses only what it commits itself. With `--decision accept`, the loop runs no rounds and collapses nothing. If the checkout is somehow not on the target, collapse refuses (D3.2).
3. **Each round.** After the round's commit action returns, the ledger claims every dispatch and commit result of the round, in order. A result is claimed only when its `head_before` equals the ledger's `tip_sha`; the tip then moves to its `head_after` and the count grows by the commits between. A dispatch agent that commits its own work is claimed this way. A gap (a commit no action of the loop made) or a missing stamp marks the ledger `unprovable`. A pause inside a round claims that round's results so far, because the round is redone on resume.
4. **Every return.** The ledger is attached to the StepResult on every exit path (completed, paused, failed, skipped), so a pause persists it for the resume.
5. **Loop completed** (`until` met, accepted on exhaustion, or accepted by decision): run `collapse_loop_commits`. With fewer than two commits claimed there is nothing to collapse, and the outcome is `nothing_to_collapse` (no log line). PAUSED, FAILED and SKIPPED loops never collapse: their per-round history is the diagnosis.
6. **Collapse.** Proof checks (D3), then backup ref, new commit, compare-and-swap (D2). The outcome is logged.

### State Management

`StepResult` and `StepState` gain one optional field, `loop_commits: LoopCommitLedger | None` (default `None`, so older state files load). Ledger fields:

| Field | Meaning |
|---|---|
| `base_sha` | the HEAD before the first claimed commit |
| `tip_sha` | the HEAD after the last claimed action |
| `commit_count` | how many commits the ledger claims, base to tip |
| `unprovable` | `True` when the ledger cannot vouch for its claim (resumed state with no ledger, a gap in the chain, or a missing stamp) |

The ledger is cumulative: a resumed loop continues the claim it carried, and each record of the step holds the whole claim so far.

## Technical Decisions

### D1 — The loop claims its own actions' commits by HEAD stamps; nothing is inferred
Status: decided (revised 20261101)
- A dispatch agent commits its own work, so the commits in a loop are not all the commit action's. The first design listed the commit action's shas and a live run refused to collapse: the agents' commits sat between them.
- Each dispatch and commit result is stamped with the HEAD it started from and the HEAD it left (`head_stamp`). The ledger claims a result only when its starting HEAD is the ledger's tip, so the claimed commits form one unbroken chain. A commit made between actions, such as an operator's during a pause, breaks the chain and the ledger becomes unprovable.
- Subjects and messages are never parsed. Not claimed: a commit landing while an agent is mid-action looks like the agent's own. The run lock stops other squadron runs, so only a person committing in the same checkout during a run can do this.
- Rejected: listing shas and having the prompt forbid agent commits. Not enforceable.
- Rejected: reconstructing from `prior_round_results` action dicts on resume. Inside `each`, the same loop step name recurs per item, and the phase-commit decision made at first start would be lost. One explicit cumulative ledger is simpler to prove.

### D2 — Mechanism: `commit-tree` plus compare-and-swap `update-ref`
Status: decided
- `new = git commit-tree <HEAD>^{tree} -p <base_sha> -F <message>`, then `git update-ref -m "squadron: collapse loop <step>" refs/squadron/pre-collapse/<new> <old_head>`, then `git update-ref -m "squadron: collapse loop <step>" HEAD <new> <old_head>`.
- Why: the tree is identical to the pre-collapse tree by construction. The index and working tree are never touched, so an operator's staged or unstaged edits survive and no clean-tree precondition is needed. The final `update-ref` with an expected old value is atomic: if `HEAD` moved after the checks, git refuses and nothing changes.
- Rejected: `git reset --soft` plus `git commit` (948's mechanism). It commits whatever else is in the index, and a failed commit hook leaves `HEAD` reset with changes staged. Commit hooks don't run under `commit-tree`. That's acceptable: the tree is byte-identical to round commits that already passed them.
- A timeout on either `update-ref` raises `GitStateUnknownError`, the commit action's existing D6 behavior. A refused swap is a `refused` outcome (HEAD moved after the checks instead of before them).
- **Architecture exception.** Moving the target's HEAD to a new commit with a different parent is a reset in effect. 180-arch's Git-Mutating Steps section records this as the one exception to "never force, reset": the commits must be the loop's own recorded, unpublished tail on the target (D3), the tree must be identical, and the swap must be a compare-and-swap, with a backup ref kept. It applies to the target only.

### D3 — What "provably ours" means
Status: decided (revised 20261101)
All of the following must hold, checked in this order. The first failure gives the `refused` outcome, and its reason goes in the WARNING line:
1. The ledger is not `unprovable`.
2. At least two commits are claimed; fewer is `nothing_to_collapse`.
3. The current branch is the target (`read_integration_target`). A detached HEAD fails this check.
4. `HEAD == tip_sha`.
5. `base_sha` is an ancestor of `HEAD`, `git rev-list --merges <base_sha>..HEAD` is empty, and `git rev-list --count <base_sha>..HEAD` equals `commit_count`. The claim was built from stamps, so the git history must agree with it: an amend, a reset or a merge after the claim fails here.
6. `git for-each-ref --contains <oldest commit in the range> refs/remotes` is empty. Checking the oldest commit is enough, since it is an ancestor of every other.
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

Run in a scratch clone of a cf project on its target branch, with slices that have no design yet (`{n}`, `{m}`, `{k}` below). The live runs for this slice used a clone of squadron registered with cf under another name, a copy of P4 without its summary step (the summary step copies to the clipboard), and `model=sonnet,review-model=sonnet`. The built-in review model needs `OPENROUTER_API_KEY`. Commit hashes below are examples.

1. Collapse on a normal run, with dispatch agents that commit their own work:
   ```bash
   sq run P4 {n} -v
   git log --oneline -3
   ```
   Expected: the run log ends with `loop loop-1: collapsed 6 commits into fd8cfe4 "docs: add slice {n} design (review: CONCERNS)" (pre-collapse head: refs/squadron/pre-collapse/fd8cfe4…)`, and `git log` shows that one commit above the commit the run started from. The count is the phase agent's commit, the phase commit, then an agent commit and a round commit per round. The verdict in the message is the final review's. If the first review passes, the loop is skipped, no collapse line appears, and the phase commit stands alone.
2. Backup ref and round history:
   ```bash
   git for-each-ref refs/squadron/pre-collapse
   git log --oneline <base>..refs/squadron/pre-collapse/<full sha of the collapsed commit>
   git diff HEAD refs/squadron/pre-collapse/<full sha of the collapsed commit>   # empty: identical tree
   ```
   Expected: the log lists the six original commits (agent commits and pipeline commits), and the diff prints nothing. The collapsed commit's parent is `<base>`.
3. Accept after a checkpoint. P4's checkpoint comes only when the loop exhausts without meeting `accept-threshold`:
   ```bash
   sq run P4 {m} -p max-revisions=1,accept-threshold=review.pass -v      # pauses at the loop
   sq run --resume <run-id> --decision accept -v
   git log --oneline -3
   ```
   Expected: the resume logs `loop step loop-1: accepted by decision at round 1; 0 rounds run` then `loop loop-1: collapsed 2 commits into d14cc53 "docs: add slice {m} design (review: CONCERNS)"`, and `git log` shows one commit for the slice.
4. Refusal: repeat step 3 on slice `{k}`, but run `git commit --allow-empty -m "chore: unrelated"` before resuming. Expected: `loop loop-1: left 2 commits uncollapsed: HEAD <x> is not the loop's last commit <y>`, the run still completes, and `git log` is unchanged, with the unrelated commit on top.

Observed on 20261101: steps 1 and 2 on slice 185 (six commits into one, empty diff against the backup ref), step 3 on slice 187, step 4 on slice 188. A first attempt at step 3 exposed a bug, now fixed and covered by a test: a pause at the exhaustion checkpoint claimed the final round a second time and made the ledger unprovable.

## Risk Assessment

### Technical Risks
- Rewriting the target's tail during an unattended run (`implement-plan`, `tasks-plan` batches) while someone else commits to the same branch.

### Mitigation Strategies
- Squadron against squadron: the per-checkout run lock (197) already allows only one git-mutating run at a time.
- Squadron against an operator's manual commit: the final write is a compare-and-swap on `HEAD` (D2), and the proof (D3) requires the unbroken stamped chain, so a commit made between the loop's actions gives `refused`, never a lost commit. The backup ref makes every collapse reversible with one `git update-ref`.

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
