---
docType: tasks
slice: one-commit-per-planning-document-loops-collapse-their-own-round-commits
project: squadron
lld: user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md
dependencies:
- 196
projectState: 'Slice design complete (20261101, revision 2). No code written. 196
  is complete; the target is read with `cf config get git.integration_branch` (`main`
  if empty).

  '
dateCreated: 20261101
dateUpdated: 20261101
status: in_progress
turns: 23
promptTokens: 1337141
cachedTokens: 1267221
cacheWriteTokens: 69876
completionTokens: 15778
durationSeconds: 120.5
costUsd: 0.564422
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.5644220999999999
    completionTokens: 15778
revision_number: 2
---

## Context Summary

- Working on **202 one-commit-per-planning-document**: a `commit_each_iteration` planning loop
  records the shas of its own commits (plus the phase commit just before it) in a ledger. When the
  loop completes, it replaces exactly those commits with one commit of identical tree, only if it
  can prove they are still the unpublished, unmixed tail of the target. Fixes issue #257.
- Tasks reference the slice design by decision number (D1–D8). Its Data Flow, Success Criteria and
  Verification Walkthrough are the contract.
- Effort scale 1–5 (relative). New logic goes in `pipeline/loop_ledger.py` and
  `pipeline/loop_collapse.py` (each under ~300 lines); `executor.py` gains call sites only.
- Tests use real temporary git repos, no git mocks. Assert on `CollapseOutcome` and git state,
  never on log text.
- Before each commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched
  area's tests.
- Next planned slice: none dependent (the design lists nothing provided to other slices).

---

## Tasks

### 1. Commit action outputs: subject and scope (effort 1)

- [x] **1.1 Add `commit_subject` and scope key to `CommitAction` outputs**
  - [x] In `src/squadron/pipeline/actions/commit.py` (`_stage_and_commit` success result), add
        `commit_subject` and the scope key (`slice` or `plan`, whichever the commit target uses)
        to `outputs`, next to `committed`, `sha`, `message`
  - [x] Take both values from the commit plan/target already built in `execute`; do not parse the
        message. Thread them through `CommitPlan` or the target if they are not already available
  - [x] No existing key is removed or renamed
- [x] **1.2 Test the new outputs** in `tests/pipeline/actions/test_commit.py`
  - [x] Slice-scoped commit: outputs carry the subject and `slice` value
  - [x] Architecture (plan-scoped) commit: outputs carry the subject and `plan` value
  - [x] Existing commit tests still pass

**Commit**: `feat: commit action outputs its subject and scope`

### 2. Ledger model and state persistence (effort 2)

- [ ] **2.1 Create `src/squadron/pipeline/loop_ledger.py` with `LoopCommitLedger`**
  - [ ] Pydantic model with fields `base_sha: str`, `commits: list[str]` (oldest first),
        `unprovable: bool = False` (design State Management table)
  - [ ] `StepResult` (`executor.py`) gains `loop_commits: LoopCommitLedger | None = None`
  - [ ] `StepState` (`state.py`) gains `loop_commits: LoopCommitLedger | None = None`, and the
        code that converts a `StepResult` into a `StepState` copies it
  - [ ] Avoid an import cycle: `loop_ledger.py` must not import `executor.py` at module level
- [ ] **2.2 Test persistence** in `tests/pipeline/test_loop_ledger.py`
  - [ ] A ledger on a `StepState` round-trips through the state file
  - [ ] A state file written without `loop_commits` still loads, with `None`

**Commit**: `feat: add loop commit ledger model and state field`

### 3. Open a ledger at loop start (effort 3)

- [ ] **3.1 Implement `open_ledger` in `loop_ledger.py`** (design Data Flow step 1, D1, D7)
  - [ ] Inputs: `inner_steps`, merged params, `prior_outputs`, `cwd`. Returns `None` when
        `round_commit_params` raises, or when the round subject is `CommitSubject.CODE` (compare
        enum, not names)
  - [ ] Read `HEAD` with `run_git(["rev-parse", "HEAD"])` as `start_head`; if unreadable, return
        an `unprovable` ledger and log WARNING
  - [ ] Find the newest commit result in `prior_outputs` with `committed: true`. If its `sha`
        equals `start_head` and its `commit_subject` and scope equal the loop's
        `round_commit_params`, then `commits = [start_head]` and `base_sha = start_head^`
        (via `git rev-parse <start_head>^`)
  - [ ] Otherwise `commits = []`, `base_sha = start_head`. If a phase commit exists but does not
        match, log one WARNING naming why it was left out; if none exists, log nothing
- [ ] **3.2 Test `open_ledger`** in `tests/pipeline/test_loop_ledger.py` (temp git repo)
  - [ ] Matching phase commit at HEAD: included, `base_sha` is its parent
  - [ ] Phase commit for a different document: excluded, WARNING logged, `base_sha == HEAD`
  - [ ] Phase commit sha not at HEAD (an operator commit followed): excluded
  - [ ] No prior commit result: empty ledger, no warning
  - [ ] Code-subject loop: returns `None`

**Commit**: `feat: open a commit ledger at planning-loop start`

### 4. Record rounds and carry the ledger on resume (effort 3)

- [ ] **4.1 Implement `record_round_commit` in `loop_ledger.py`** (Data Flow step 3)
  - [ ] Takes the ledger and the round's commit `ActionResult`. `committed: true` with a real sha
        appends it; sha `unknown` sets `unprovable`; `committed: false` or a failed result changes
        nothing
- [ ] **4.2 Implement `carried_ledger` in `loop_ledger.py`** (Data Flow step 2)
  - [ ] Add `StateManager.loop_ledger_for(run_id, step_name)` in `state.py`, mirroring
        `resume_iteration_for` (last occurrence of the step name wins). It returns the stored
        ledger, or `None` when the step has no record
  - [ ] When the step has a record whose `loop_commits` is `None` (pre-slice state file), the
        carried ledger is `unprovable` with empty `base_sha`/`commits`
  - [ ] When the step has no record, the caller opens a fresh ledger (task 3)
- [ ] **4.3 Tests** in `tests/pipeline/test_loop_ledger.py` and `tests/pipeline/test_state_loop_rounds.py`
  - [ ] Record: appended in order; `committed: false` adds nothing; `unknown` marks `unprovable`
  - [ ] Carry: a stored ledger is returned unchanged; an old record without a ledger gives
        `unprovable`; a step with two records returns the later one's ledger
  - [ ] The `each` rule (one item never inherits another item's ledger) is covered in 7.5

**Commit**: `feat: record round commits and carry the ledger across resume`

### 5. Collapse: proof checks and message (effort 4)

- [ ] **5.1 Create `src/squadron/pipeline/loop_collapse.py` with `CollapseOutcome`**
  - [ ] `CollapseOutcome` StrEnum: `collapsed`, `nothing_to_collapse`, `refused`, `git_failed`
  - [ ] A result type carrying the outcome, a `reason` string (for `refused`/`git_failed`), and the
        new sha when collapsed
  - [ ] `collapse_loop_commits(ledger, target, commit_params, step_name, cwd, cf_client)`, where
        `target` is the integration target branch and `commit_params` is the loop's
        `round_commit_params` result (the subject and scope source for 5.4). Fewer than two commits returns `nothing_to_collapse`, silently
- [ ] **5.2 Implement the proof checks (D3), in this order, first failure wins**
  - [ ] 1. ledger not `unprovable`
  - [ ] 2. current branch equals the target (`read_integration_target`); detached HEAD fails
  - [ ] 3. `HEAD == commits[-1]`
  - [ ] 4. `git rev-list --first-parent <base_sha>..HEAD` equals `reversed(commits)` exactly
  - [ ] 5. `git for-each-ref --contains <commits[0]> refs/remotes` is empty
  - [ ] Any failing or timed-out git command gives `git_failed` with the command text (D6)
  - [ ] The refusal reason names the shas or the remote ref involved
- [ ] **5.3 Test the proof checks** in `tests/pipeline/test_loop_collapse.py` (temp git repos, a
      small helper that makes N loop-style commits and a ledger for them)
  - [ ] Each of the five refusals leaves `HEAD` and the branch byte-identical, with the reason text
        naming the relevant sha/ref
  - [ ] An operator commit made mid-range (HEAD still equals the last ledger commit) is refused by
        check 4
  - [ ] A merge commit in the range is refused by check 4
  - [ ] A remote-tracking ref containing `commits[0]` (created with `git update-ref
        refs/remotes/origin/x`) is refused by check 5
- [ ] **5.4 Implement the surviving message (D4)**
  - [ ] Derive `StagedFacts` from the collapsed range: `git diff --name-status <base_sha> HEAD`
        limited to `subject_paths`; `A` is ADD, `M` is REVISE; whether a review file is in range;
        verdict from the newest review file via `read_review_verdict`
  - [ ] Build the `CommitTarget` from `commit_params` (subject, slice or plan, review template)
        with `round = 0`, using the same params-to-`CommitTarget` conversion as the commit
        action: extract `_target_from_params` (`actions/commit.py`) so it takes the params dict
        and a round number rather than an `ActionContext` (the commit action passes
        `context.iteration`, collapse passes 0), and have both callers use it. Never read subject or scope
        from commit messages
  - [ ] Call `compose_message` with that target and the facts. No new message template and no parsing of
        existing commit messages
- [ ] **5.5 Test the message** in `tests/pipeline/test_loop_collapse.py`
  - [ ] Phase commit included (document added in range): `docs: add slice {n} design (review: PASS)`
  - [ ] Only rounds collapsed (document pre-existing): `revise` wording
  - [ ] Verdict reflects the final review, not the first

**Commit**: `feat: loop collapse proof checks and composed message`

### 6. Collapse: writes, backup ref, race (effort 3)

- [ ] **6.1 Implement the git writes (D2, D5, D6)**
  - [ ] `git commit-tree <HEAD>^{tree} -p <base_sha> -F <message>` (message via a temp file or
        stdin, not shell quoting)
  - [ ] `git update-ref -m "squadron: collapse loop <step>" refs/squadron/pre-collapse/<new> <old_head>`
        (backup ref; failure means no rewrite, `git_failed`)
  - [ ] `git update-ref -m "squadron: collapse loop <step>" HEAD <new> <old_head>` as the
        compare-and-swap. A refused swap is `refused` (HEAD moved after the checks)
  - [ ] A timeout on either `update-ref` raises `GitStateUnknownError` (reuse the commit action's
        existing class/behavior); all other failures return `git_failed` and never raise
  - [ ] Never touch the index or working tree
  - [ ] Log INFO on `collapsed` and WARNING on `refused`/`git_failed`, with the formats in the
        design's Patterns and Conventions; no log for `nothing_to_collapse`
- [ ] **6.2 Test the writes** in `tests/pipeline/test_loop_collapse.py`
  - [ ] Happy path: one commit with parent `base_sha`, tree identical to the old HEAD's tree,
        `refs/squadron/pre-collapse/<new>` points at the old head, `git diff <new> <ref>` empty
  - [ ] Staged and unstaged operator edits present before collapse are still staged/unstaged and
        unchanged after
  - [ ] CAS race: split collapse into a check function and a write function, and have the test
        call the write function directly with a stale `old_head` after moving `HEAD` in the
        temp repo. No patching; outcome is `refused`, no commit lost
  - [ ] Backup-ref write failure (pre-create a conflicting ref path) gives `git_failed` and
        HEAD unchanged
  - [ ] `GitStateUnknownError` raised when an `update-ref` times out: the write function takes
        its git runner as a parameter (defaulting to `run_git`), and the test passes a runner
        that returns a timeout for `update-ref`. This is the only injected fake; all other
        tests use real git
  - [ ] Every original round sha is still reachable from `refs/squadron/pre-collapse/<new>`
        (`git merge-base --is-ancestor`). This is the test for the design's `sq review resolve`
        integration criterion: reachability is the property D5 provides, and no resolve-command
        test is added
  - [ ] WARNING and INFO lines each appear once for refused/collapsed (assert via `caplog`
        alongside the enum assertion)

**Commit**: `feat: collapse loop commits with backup ref and compare-and-swap`

### 7. Executor call sites (effort 4)

- [ ] **7.1 Open or carry the ledger at loop start** in `_execute_loop_body` (`executor.py`)
  - [ ] Only when `loop_config.commit_each_iteration` is true
  - [ ] Resumed invocation (`start_iteration > 1` or the `--decision accept` resume path): use
        `carried_ledger` from run state. Fresh invocation (including an `each` item rerun via
        `resume_item`): `open_ledger`
  - [ ] Thread the needed state access (`StateManager`/`runs_dir`) into the function without
        adding logic to `executor.py`
- [ ] **7.2 Record after each round commit**
  - [ ] Right after `commit_result` is produced, call `record_round_commit`
- [ ] **7.3 Attach the ledger to every `StepResult` return** in `_execute_loop_body` (completed,
      paused, failed, skipped, exhausted via `_loop_exhaust_result`), so a pause persists it
- [ ] **7.4 Collapse on COMPLETED**
  - [ ] On each COMPLETED return (until met, accepted on exhaustion, accepted by decision) call
        `collapse_loop_commits` once, with the target from `read_integration_target` and the
        `round_commit_params` result already computed for the loop
  - [ ] PAUSED, FAILED, SKIPPED never collapse
  - [ ] Collapse outcome never changes the loop status (D6); only `GitStateUnknownError`
        propagates
  - [ ] The returned `StepResult.loop_commits` is the ledger as it stood at completion,
        whatever the outcome (collapsed or not). Nothing resumes a COMPLETED loop, so it is
        not rewritten after collapse
- [ ] **7.5 Executor-level tests** in `tests/pipeline/test_loop_collapse_executor.py` (temp git
      repo, scripted stub dispatch and review actions, as in `test_executor_loop_body.py`)
  - [ ] Phase commit plus two rounds, `until` met: exactly one commit remains, same tree as before
        collapse, message `docs: add slice {n} design (review: PASS)`
  - [ ] Single commit (first review passes) or `skip_if_met`: history unchanged, no collapse log
  - [ ] Exhaustion: `accept_if` met collapses; pause, fail, skip do not
  - [ ] Pause at a checkpoint, then resume for more rounds, and separately resume with
        `--decision accept`: one commit spans the phase commit and rounds from both executions
  - [ ] Unrelated operator commit during the pause: resume completes, history unchanged,
        `refused` WARNING logged
  - [ ] Pre-slice state record (no ledger) resumed: history unchanged, `refused`
  - [ ] `each` item rerun: `--decision retry` collapses only the rerun's commits and leaves the
        flagged attempt's commits; `--decision accept` runs no rounds and collapses nothing;
        one item never inherits another item's ledger
  - [ ] Code loop (`revise-code`): never collapses
  - [ ] Findings-addressed gate's per-round base behaves as before during the loop (existing
        `test_findings_addressed*` still pass)

**Commit**: `feat: planning loops collapse their own commits on completion`

### 8. CHANGELOG and validation (effort 2)

- [ ] **8.1 Add the CHANGELOG bullet**: planning loops now leave one commit per document (short,
      user-facing)
- [ ] **8.2 Full validation**
  - [ ] `ruff format`, `ruff check`, `pyright` (zero errors), full test suite pass
  - [ ] `loop_ledger.py` and `loop_collapse.py` each under ~300 lines; `executor.py` changes are
        call sites only

**Commit**: `docs: add loop collapse changelog entry`

### 9. Live walkthrough (effort 2)

- [ ] **9.1 Run the design's Verification Walkthrough steps 1–4** in a scratch clone of a cf
      project on its target branch
  - [ ] Step 1: P4 run, single resulting commit, INFO collapse line
  - [ ] Step 2: backup ref exists, `git diff` against it is empty
  - [ ] Step 3: pause and `--decision accept` resume gives one commit across the pause
  - [ ] Step 4: unrelated commit before resuming gives the WARNING and unchanged history
  - [ ] The live run is evidence, not a gate: the behavior is gated by the 7.5 tests. If the
        review model passes first time or never exhausts, so steps 3–4 cannot be reached, record
        that in the DEVLOG and leave those sub-items unchecked
- [ ] **9.2 Record the outcome in the DEVLOG** (Session State Summary); mark the slice design
      `status: complete` and update the slice plan only if every criterion above is met

**Commit**: `docs: record slice 202 walkthrough results`
