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
aiModel: claude-opus-5-5
status: complete
dateCreated: 20261004
dateUpdated: 20261004
reviewedSha: 5046f56203b602307f2f844b7993e7a762bc5caa
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
durationSeconds: 61.8
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "The architecture's out-of-scope rule doesn't cover the grammar this slice adds"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:219-230"
  - id: F002
    severity: concern
    category: integration
    summary: "DEVLOG left uncommitted after merge makes the next `branch enter` fail"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:256-259"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Merge path doesn't cover timeouts, a failed abort, or a non-conflict merge failure"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:245-252"
  - id: F004
    severity: concern
    category: integration
    summary: "Pipeline-step order around `branch enter` doesn't address all dirty-tree sources"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:240"
  - id: F005
    severity: note
    category: nfr
    summary: "The architecture states no NFRs for these paths"
    location: "project-documents/user/architecture/180-arch.pipeline-intelligence.md"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "#175 and #179 match the architecture's resolver and pool model"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:298-314"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "#152 reuses the existing imposition pattern instead of adding a second signal"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:291-296"
  - id: F008
    severity: pass
    category: dependencies
    summary: "Dependencies point the right way and integration points match 195, 197 and 198"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:344-356"
  - id: F009
    severity: pass
    category: scope
    summary: "Scope is held to the slice-plan entry"
    location: "project-documents/user/slices/196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md:48-55"
---

# Review: slice — slice 196

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] The architecture's out-of-scope rule doesn't cover the grammar this slice adds

Under Out of Scope, 180-arch says changes to 140's pipeline grammar are allowed only as "the general batch-pipeline pieces added by 194 and 195". It also names 194/195 as the one exception to "register through 140's registries" (Relationship to 140 section). This slice adds a new top-level step type (`branch:`), a new phase-step key (`existing: keep`), a new load-time validation rule (an implement step needs a preceding enter), two hidden CLI commands, and pipeline steps that write to git. None of this is a convergence, pool, escalation, or persistence registration.

The slice plan approves the scope (item 16), so the work itself is fine. The architecture document just hasn't caught up. By the architecture's own triage model this is an architecture-scope finding, so the arch doc should be updated rather than the slice:
- Extend the exception to "194–197".
- Add a short section on git-mutating steps: the target rules, never force or delete, and abort to a clean target.

Otherwise later reviews of 196 and 197 will keep flagging this as a boundary violation.

### [CONCERN] DEVLOG left uncommitted after merge makes the next `branch enter` fail

D7 leaves `devlog` output "uncommitted on the target, as it is today." D5.5 requires `git status --porcelain` to be empty before entering. So after any P6, P456, P56 or `implement` run finishes, the next code pipeline (or the next item in a 197 batch, if 197 keeps a per-item devlog) fails with `working tree not clean: DEVLOG.md`.

The Verification Walkthrough misses this because it dirties the tree on purpose between runs, and step 9 (`--prompt-only P6 106` after step 2) would hit it. D1 already treats `DEVLOG.md` as a candidate path for scoped commits. Pick one and state it in the doc:
- Commit DEVLOG after merge with a scoped plan, or
- Have the enter guard ignore DEVLOG.md explicitly (a single constant), or
- Leave it as is, but tell 197 so it doesn't run devlog per item.

The Integration Requirements claim that "197 can compose … with no engine changes" depends on this.

### [CONCERN] Merge path doesn't cover timeouts, a failed abort, or a non-conflict merge failure

D6 handles a conflict (`merge --abort`) and a checkout failure. It doesn't cover these:
- **`run_git` returns `None` (timeout or git unavailable) during `merge` or `checkout`.** The repository state is then unknown and `MERGE_HEAD` may be present. Line 319 promises "git stderr included", but there is no stderr in this case.
- **`git merge --abort` itself fails.** The target is left mid-merge, which is exactly the risk named at line 432.
- **Non-conflict merge failures,** for example untracked files that would be overwritten.

Every later item in 197 inherits whatever state is left. For each case, state the handling: re-check `MERGE_HEAD` and the current branch after any failure, fail with an explicit "target state unknown" error that stops the whole batch (not just the item), and log at ERROR. The same gap applies to `checkout -b` in D5.6 and to the commit action's `git add`/`commit` timing out. Add tests for the `None` and abort-failure cases next to the conflict test in the Technical Requirements.

### [CONCERN] Pipeline-step order around `branch enter` doesn't address all dirty-tree sources

D5.5 says this is deliberate: unrelated edits left out by scoped Phase 4/5 commits stop Phase 6. In P456 and P56, that includes anything the design or tasks agent touched outside the candidate set. Examples are slice-plan prose fixes in files other than `slicePlan`, architecture-doc edits, and files written by `summary emit: file` if those land in the repo.

The result is that a P456 run which used to finish now stops halfway through, after the design and tasks commits, with no recovery path documented. State one of the following:
- the enter failure in P456/P56 is a checkpoint (resume after a human cleans up) rather than a plain FAILED, or
- the WARNING from the scoped commit's `left_out` is repeated in the enter error so the operator can connect the two.

### [NOTE] The architecture states no NFRs for these paths

180-arch states no latency or throughput targets for commit, branch, or source-selection paths, so the slice has nothing to restate. The relevant architectural principle is observability ("prioritize observability… detailed logging"). The slice follows it: WARNING on left-out paths, imposed verdict with a coverage finding, and `-v` labels that match the resolver.

### [PASS] #175 and #179 match the architecture's resolver and pool model

`require_known_model` sits beside the alias registry. Pool members are still validated at load time, matching the arch rule that pools are always one level deep. The `-v` label reuses `cascade_candidates`. Together these address the arch risk "why did this step use model X?" without adding indirection. There is one validator for `sq review` and pipelines, with no duplicated logic.

### [PASS] #152 reuses the existing imposition pattern instead of adding a second signal

Imposing CONCERNS with `verdictSource: imposed` and a `review-coverage` finding keeps every gate reading one field. It leaves `ReviewFinding` unchanged, which honors the arch's "no changes to review core models." The rejected frontmatter flag is reasoned out correctly.

### [PASS] Dependencies point the right way and integration points match 195, 197 and 198

- It consumes 195's `each`, `flag_reason` and sources, and 927's coverage pattern, and doesn't change their contracts beyond the documented source rename.
- It provides 197 with exactly what slice-plan item 17 expects: 196b branch steps and 196c dependency flags.
- The 198 seam (`ArtifactKind.ARCH` replacing `resolve_arch_file`) is named rather than built ahead of time.
- cf failures fail the action rather than falling back to `main`. This follows the project's no-silent-fallback rule, and `resolve_diff_base` is kept separate on purpose.

### [PASS] Scope is held to the slice-plan entry

The Excluded list leaves out 197's work (the batch pipeline, reordering, resume), PM-only git actions, and the cross-repo cf field. D9 picks design frontmatter over a context-forge change, which is the simpler option. Each of (a)–(e) and #179 maps one-to-one to item 16 in the slice plan.

### Run Digest

- Response length: 8441 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 61.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Response

- **F001: fixed in the architecture doc.**
  - The 180-arch exception now covers 194–197, listing what each slice adds to the grammar.
  - The Out of Scope line says 194–197.
  - A new "Git-Mutating Steps" section covers the strict target read, where planning and code land, scoped staging, never force/reset/delete/push, abort to a clean target, and stopping the run when state can't be verified.
- **F002: fixed (D7).** The `devlog` step commits its own entry (`CommitSubject.DEVLOG`, `DEVLOG.md` only). Code pipelines run `branch enter → implement → devlog → branch merge → summary`, so the entry merges with the slice and the tree is clean for merge and for the next enter. Summary file emits go to `~/.config/squadron/runs/summaries`, outside the repo.
- **F003: fixed (D5, D6).**
  - A shared `verify_git_state(expected_branch)` checks three things: no `MERGE_HEAD`, the expected branch, and no tracked changes.
  - Every merge or checkout failure, timeout, or refusal aborts if `MERGE_HEAD` exists, then runs the check.
  - If the check passes, it's an item failure. If it fails, or the abort fails, the action raises `GitStateUnknownError`, logged at ERROR, and the run ends.
  - A commit timeout raises the same error.
  - `each` writes its report in a `finally`, so a halted batch still reports.
  - Tests are added for `None`, abort failure, and a non-conflict refusal.
- **F004: fixed (D5).**
  - Environment failures (dirty tree, wrong branch, unregistered worktree, cf read failure, target checked out elsewhere) raise `GitEnvironmentError` and end the run, because every later item would hit them too.
  - The dirty-tree error lists the paths and the recovery: commit or remove them, then rerun phase 6 for the slice; the planning commits are kept.
  - Paths left out by earlier scoped commits were already named in those commits' WARNING.
  - Not a checkpoint: `--resume` applies to paused runs, and a dirty tree isn't a review decision.
- **F005:** no change. Agreed, no NFRs apply.
