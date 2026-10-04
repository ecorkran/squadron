---
docType: slice-design
slice: pipeline-branch-steps-scoped-commits-and-dependency-aware-batches
project: squadron
parent: project-documents/user/architecture/180-slices.pipeline-intelligence.md
dependencies: [195]
interfaces: [197]
dateCreated: 20261004
dateUpdated: 20261004
status: not_started
---

# Slice Design: pipeline-branch-steps-scoped-commits-and-dependency-aware-batches

## Overview

Slice 197 (`implement-plan`) will run Phase 6 over a whole slice plan with no human watching. Five things it depends on are wrong or missing today:

1. **Commits take whatever is in the tree.** `CommitAction` runs `git add -A` when it is given no paths, and phase steps never pass any. An unrelated `pyproject.toml` and `uv.lock` bump was committed as `chore: phase-4 slice 924` (#150). Messages name the step that ran, not what was committed (#164).
2. **No pipeline creates, switches, or merges branches.** Every code-implementing pipeline (P6, P456, P56, `implement`) implements on whatever is checked out. Its code review then fails with "Could not resolve diff range for slice N: no local branch matching 'N-slice.*'".
3. **`each` ignores dependencies.** When a slice is flagged, the slices that build on it still run.
4. **`tasks-plan` never revisits a slice that already has tasks.** A slice whose task file exists, but whose task review is missing or below the accept threshold, is never selected.
5. **Reviews can report things they never checked.** A stated PASS cut off by its output budget saves as a clean PASS (#152). An unknown model alias runs a fabricated SDK review over the slot's existing artifact (#175). `sq run -v` labels actions with the configured model, not the one that runs (#179).

This slice fixes all five as general engine pieces, and adds branch steps to the four single-slice pipelines that implement code.

## Value

- **Unattended runs commit only their own work**, under messages that say what was committed (`docs: add slice 105 design (review: CONCERNS)`, not `chore: phase-4 slice 105`). `git log --oneline` becomes readable without hand rewording.
- **The single-slice code pipelines work end to end.** P6, P456, P56 and `implement` branch from the integration target, implement and review on the slice branch, and merge back. The code review resolves its diff.
- **A flagged slice stops its dependents.** A batch doesn't spend model time building on unfinished work.
- **`tasks-plan` re-runs pick up every unsettled slice**, not only the untasked ones.
- **A gate can trust what it reads.** A truncated PASS can't pass. A mistyped alias fails before any step runs. The `-v` log names the model that actually ran.
- **Enables 197**, which composes branch → implement → review loop → merge per slice and relies on dependency flags.

## Technical Scope

### Included

- **(a) Scoped commits.** A commit plan (staged paths plus message) is built from what the step produced. It replaces `git add -A` for phase steps and loop rounds. The prompt-only renderer gets the same behavior through a hidden `sq _commit` command.
- **(b) Branch steps.** A new `branch:` step type with `op: enter | merge`. It follows the project's git rules: read the target, create or switch to the slice branch, merge back, and never force. P6, P456, P56 and `implement` gain enter and merge steps.
- **(c) Dependency-aware `each`.** Slice items carry `dependencies` from their design's frontmatter. An item whose dependency was flagged earlier in the same run is flagged with `dependency {n} flagged`, and its body isn't run.
- **(d) `tasks-plan` re-review.** The source also selects slices whose task file exists but whose task review fails the accept threshold. The `tasks` step gains `existing: keep`, which skips creation when the task file already exists.
- **(e) #152.** A stated PASS whose final stop reason is an exhausted output budget is imposed to CONCERNS, using slice 927's mechanism.
- **(e) #175.** An unknown model alias with no profile source fails before any step runs, naming the alias and listing close matches. The resolver raises at run time as a backstop.
- **#179.** The `-v` action line shows the alias the resolver picks, computed the same way the pre-run classification computes it.

### Excluded

- The Phase 6 batch pipeline (`implement-plan`), reordering batch items by dependency, and resuming one flagged item (all 197).
- Pushing branches or opening PRs. Deleting branches (the git rules forbid it unless instructed).
- Merging a worktree's branch into a wider integration branch or into `main`. The rules reserve that for the PM.
- A cf-side `dependencies` field on `cf list slices --json`. See D9.
- Re-review selection for `slices-plan`. Its flagged slices already resurface through `tasks-plan`'s design-review flag (195 D1).

## Dependencies

### Prerequisites

- **195** (complete): the `each` per-item isolation, `ItemFailurePolicy`, `flag_reason`, `BatchReport`, `cf.untasked_slices`, `_design_review_flag`, and loop `accept_if` / `skip_if_met`.
- **927** (complete): `impose_diff_coverage` in `review/coverage.py`, the pattern #152 reuses.
- **929** (complete): `git_metadata_lock`. Branch steps don't add worktrees, so they don't need it. Noted only so nobody adds a second lock.
- GitHub issue #152 is closed on GitHub but was never fixed. This slice delivers it.

### Interfaces Required

- `cf config get git.integration_branch` through `CfClient.get_config` (`integrations/context_forge.py:213`).
- `cf worktree list --json` to detect an unregistered linked worktree. The cf client gains a `list_worktrees()` reader if it lacks one.
- `cf list slices {plan} --json` → `slicePlan` (already used by `set_arch`, 195 D2).
- `review/persistence.py`: `resolve_slice_info`, `resolve_arch_file`, `slice_name_for`, `slice_review_stem`, `REVIEWS_DIR`.
- `events/builtin/artifact_paths.py`: `expected_artifact_paths(kind, slice_index, cf_client)`.
- `models/aliases.py`: the alias table (names and model ids).

## Architecture

### Component Structure

```
pipeline/
  commit_plan.py           NEW   CommitTarget, CommitPlan, build_commit_plan()  (a)
  actions/commit.py        CHANGED stages CommitPlan.paths; message from plan; STAGE_ALL only on slice branch
  actions/branch.py        NEW   BranchAction (enter | merge)                    (b)
  steps/branch.py          NEW   BranchStepType, BranchOp StrEnum                 (b)
  steps/__init__.py        CHANGED StepTypeName.BRANCH; bootstrap import
  steps/phase.py           CHANGED commit config carries artifact kind + target; existing: keep  (a, d)
  steps/devlog.py          CHANGED expand appends a DEVLOG-scoped commit (a)
  actions/dispatch.py      CHANGED existing: keep → skip when artifact exists     (d)
  events/builtin/dispatch_artifact.py  CHANGED skipped dispatch passes the post-condition (d)
  executor.py              CHANGED loop-round commit passes round results; each dependency flags;
                                   _summarize_action_config uses the shared candidate (a, c, #179)
  sources.py               CHANGED item dependencies; tasks re-review selection; shared review-threshold helper (c, d)
  classification.py        CHANGED takes merged params; unknown-alias errors collected before run (#175)
  loader.py                CHANGED implement step requires a preceding branch enter (b)
  resolver.py              CHANGED _resolved raises UnknownModelAliasError (#175 backstop)
  prompt_renderer.py       CHANGED commit renders `sq _commit …`; branch renders `sq _branch …` (a, b)
  git_ops.py               NEW   write-side git: read_integration_target() (strict), verify_git_state(),
                                 slice_branch_name(), GitEnvironmentError/GitStateUnknownError (a, b)
review/
  coverage.py              CHANGED impose_output_coverage()                       (#152)
  review_client.py         CHANGED call impose_output_coverage beside impose_diff_coverage (#152)
models/aliases.py          CHANGED UnknownModelAliasError, require_known_model() with close matches (#175)
cli/commands/review.py     CHANGED _reject_unknown_alias delegates to require_known_model (#175)
cli/commands/commit_run.py NEW `sq _commit`  (a; sibling of summary_run.py, registered in cli/app.py)
cli/commands/branch_run.py NEW `sq _branch`  (b)
data/pipelines/
  P6.yaml, implement.yaml, P456.yaml, P56.yaml   CHANGED branch enter / merge     (b)
  tasks-plan.yaml          CHANGED source rename, existing: keep                 (d)
```

### Data Flow

**P6 on slice 105 (after this slice):**

```
branch op=enter slice=105
  target = cf config git.integration_branch or "main"   (cf failure → halt run, never "main")
  guard: unregistered linked worktree → halt run
  guard: current branch ∉ {target, 105-slice.<name>} → halt run
  guard: dirty tree → halt run (lists paths + recovery)
  guard: no design file → item FAILED
  105-slice.<name> exists? checkout : checkout -b 105-slice.<name> <target>
implement (phase 6)
  cf-ops → dispatch → review(code)   ← diff range now resolves via _find_slice_branch
  checkpoint on-fail
  commit  CommitPlan(STAGE_ALL, on 105-slice.<name>) → "feat: implement slice 105 (review: PASS)"
devlog → commit DEVLOG.md on 105-slice.<name> → "docs: add DEVLOG entry for slice 105"
branch op=merge slice=105
  re-read target; guard: on slice branch or already merged
  guard: target checked out in another worktree → halt run
  checkout <target>; merge --no-ff -m "merge: slice 105 — <name>"
  any failure → abort if MERGE_HEAD → state check
    check passes → item FAILED (slice branch left unmerged, target clean)
    check fails  → GitStateUnknownError, ERROR, halt run
summary  (file emit goes outside the repo)
```

**Design commit in a P4 loop round 2:**

```
round results: dispatch(revise) → review(slice, slice=105) → outputs.input_file, outputs.review_file
commit  build_commit_plan(target=slice 105, subject from review template "slice" → DESIGN, round=2)
  paths   = changed ∩ {design file, review file, slice plan file, DEVLOG.md}
  verdict = review file frontmatter `verdict`
  message = "docs: revise slice 105 design, round 2 (review: CONCERNS)"
          | "review: re-review slice 105 design, round 2 (CONCERNS)"   (only the review changed)
  left out: any other dirty path → WARNING "commit left unstaged: pyproject.toml, uv.lock"
```

**`each` with a flagged dependency:**

```
items: 196 {deps: [195]}, 197 {deps: [196]}, 198 {deps: [194, 195]}
196 → body FAILED → FLAGGED; flagged = {196}
197 → deps ∩ flagged = {196} → FLAGGED "dependency 196 flagged" (body not run); flagged = {196, 197}
198 → no flagged deps → runs
```

### State Management

- **Git state is changed on purpose.** `branch enter` leaves the checkout on the slice branch. `branch merge` leaves it on the target. A failed merge is aborted, so the target is never left mid-merge, and the slice branch stays unmerged for the PM. Branches are never deleted or pushed.
- **Dependency flags are per `each` run.** The flagged-index set lives inside `_execute_each_step` and is discarded when the step ends. Only dependencies flagged in the same run count. A dependency that isn't in the run, or that is complete, doesn't flag anything.
- **Commit plans are computed, not stored.** Paths come from cf, the review persistence helpers, and the step's own results. The verdict comes from the review file on disk. Nothing new is persisted.

## Technical Decisions

### D1: One commit-plan builder for both executors

`pipeline/commit_plan.py`:

```python
class CommitSubject(StrEnum):      # what the commit is about
    DESIGN = "design"
    TASKS = "tasks"
    ARCHITECTURE = "architecture"
    CODE = "code"
    DEVLOG = "devlog"

@dataclass(frozen=True)
class CommitTarget:
    subject: CommitSubject
    slice_index: int | None        # None ⇔ initiative-scoped (plan)
    plan: str | None
    review_template: str | None
    round: int                     # 0 for the step's own commit, n for loop round n

@dataclass(frozen=True)
class CommitPlan:
    paths: tuple[str, ...]         # empty ⇔ nothing to commit
    stage_all: bool                # CODE only, see D3
    message: str
    left_out: tuple[str, ...]      # dirty paths not staged, for the WARNING

def build_commit_plan(target: CommitTarget, cwd: Path, cf_client: CfClientProtocol) -> CommitPlan: ...
```

- **Candidate paths** for DESIGN or TASKS: `expected_artifact_paths(kind, slice, cf)`, plus the review file `REVIEWS_DIR / slice_review_stem(index, template, slice_name_for(...))`, the slice plan file (`cf list slices --json` → `slicePlan`), and `DEVLOG.md`. For ARCHITECTURE: `resolve_arch_file(plan)`, its review file, and `DEVLOG.md`. For DEVLOG: `DEVLOG.md` only.
- **Staged = candidates ∩ `git status --porcelain`** (modified, added, or untracked). Paths are computed, never searched. This is the same rule `_design_review_flag` follows.
- **The verdict** is read from the review file's frontmatter (`read_frontmatter`, the reader `sources.py` uses). It is never taken from the in-memory result. The SDK executor and prompt-only mode then read the same value.
- **One builder, two callers.** `CommitAction` calls it with the target derived from its config and context. The hidden `sq _commit --subject design --slice 105 --template slice --round 2` CLI calls it for prompt-only, which can't compute paths at render time because the design file doesn't exist yet. Keeping the logic in one function keeps CLI and SDK results identical.
- **Subject from template** is defined once in `commit_plan.py`: `slice` → DESIGN, `tasks` → TASKS, `code` → CODE, `arch` → ARCHITECTURE. A loop round derives its subject from its last review action's template. A round with no review in scope fails the commit: `"commit scope unknown: no review in round {n}"`. Every built-in `commit_each_iteration` loop has a review in its body.
- **Rejected: deriving paths from in-scope action outputs.** That works for the SDK path but not for prompt-only, which has no outputs. Two derivations would drift.

### D2: Messages from the staged set (#164)

| Staged | Message |
|---|---|
| new artifact (+ review) | `docs: add slice 105 design (review: CONCERNS)` |
| changed artifact, round n (+ review) | `docs: revise slice 105 design, round 2 (review: PASS)` |
| review only, round 0 | `review: add slice 105 tasks review (CONCERNS)` |
| review only, round n | `review: re-review slice 105 tasks, round 2 (CONCERNS)` |
| CODE | `feat: implement slice 105 (review: PASS)` |
| initiative-scoped | `docs: revise initiative 180 architecture (review: PASS)` |
| DEVLOG (devlog step) | `docs: add DEVLOG entry for slice 105` |

- "add" versus "revise" comes from the artifact's porcelain status: untracked or added means "add", modified means "revise".
- The review clause is omitted when no review file is staged.
- The verdict is the frontmatter `verdict` value as written.
- Internal step names (`phase-4`, `loop-2`, `revise-design`) never appear.
- `message_prefix` and the `(iteration n)` suffix are removed. An explicit `params["message"]` is still honored verbatim, for user pipelines.
- **Nothing staged** returns `committed: False` and logs a WARNING (`"commit: step {name} produced no changes to commit"`). Nothing is padded.

### D3: `implement` stages all, but only on its slice branch

Code changes can touch any file, so a CODE plan has `stage_all=True`. `CommitAction` honors it only when the current branch is `{index}-slice.*` for the plan's slice (`parse_slice_branch`, `pr/branch.py:14`). Otherwise the commit fails with `"refusing to stage all changes off the slice branch (on {branch})"`. `branch enter` (D5) guarantees a clean tree at branch creation, so everything on the slice branch is the slice's work. `git add -A` is never a default anywhere else.

### D4: `branch:` step type

```yaml
- branch: { op: enter }            # slice from "{slice}" by default, or slice: "{slice.index}"
- branch: { op: merge }
```

- `BranchOp` StrEnum: `ENTER`, `MERGE`.
- The step expands to one `branch` action. Validation requires `op`, accepts an optional `slice`, and rejects every other key.
- Prompt-only renders `sq _branch enter --slice N` / `sq _branch merge --slice N`, so both modes run the same code (`BranchAction` logic lives in a function the CLI also calls).
- **Validation rule:** an `implement` step must come after a `branch: { op: enter }` step. Otherwise `validate_pipeline` reports `"implement step {name} needs a preceding branch: {op: enter}"`. This fails at load time rather than after an implement dispatch has run.
  - **Nesting:** an enter counts if it appears earlier in the implement's own step list, or earlier in any enclosing list than the `loop:` or `each:` that contains the implement. An enter inside a sibling container doesn't count.
  - **Inventory:** the only built-in pipelines with `implement` steps are P6, P456, P56 and `implement`. All four are updated in this slice (D7).
  - **User pipelines** with an `implement` step fail validation until they add the enter. This is a deliberate break. Without the enter, the implement commit would refuse to stage anyway (D3), but only after the dispatch had run. The error message names the fix, and the CHANGELOG and `docs/PIPELINES.md` call out the change. There's no compatibility flag, since one would reopen the "implement on whatever is checked out" path this slice closes.
- **Rejected: an implicit enter inside the `implement` phase step.** Merge has to come after the review loop, which is a separate step, so the pair would be half implicit and half explicit. Explicit steps also compose for 197.

### D5: `branch enter`

**Two failure classes.**
- **Environment failures** raise `GitEnvironmentError`. These are a cf read failure, an unregistered worktree, being on the wrong branch, a dirty tree, and a branch checked out elsewhere. Each one would hit every later item in a batch too, so it ends the run instead of flagging one item. It is logged at ERROR and propagates out of `execute_pipeline`, the same path `LazySessionConnectError` takes, so `sq run` exits 1 with the message.
- **Item failures** return `ActionResult(success=False)`, so `each` flags the item and continues. The only one at enter is a slice with no design file.

Steps, in order, each with a message that names the fact:

1. **Target:** `read_integration_target(cf_client)`, a new strict reader in `pipeline/git_ops.py`. Unset (`""`) means `DEFAULT_DIFF_BASE` (`"main"`, `review/git_utils.py:16`). That's the one definition of the default branch, imported rather than respelled. A cf failure raises. `resolve_diff_base`'s degrade-to-main behavior is wrong for a write operation and is not reused.
2. **Unregistered worktree:** when `git rev-parse --git-dir` differs from `--git-common-dir` (a linked worktree) and no `cf worktree list --json` entry has `worktreePath` equal to the git root: `"unregistered worktree {root}: integration target belongs to the primary checkout"`.
3. **Branch name:** `{index}-slice.{name}`, where `name` is the design file's stem without its `{index}-slice.` prefix. This is the same name the git rules and the existing branches use (`195-slice.plan-batch-…`). With no design file: `"slice {n} has no design file; cannot name its branch"`.
4. **Current branch:**
   - **The target, or this slice's branch:** proceed to step 5.
   - **Another slice's branch** (`parse_slice_branch` matches a different index): an earlier item ended there unmerged, because its implement, review, devlog or merge failed or paused. Enter restores the target:
     - If the tree is dirty, commit the leftovers on that branch: `stage_all`, which D3 allows on a slice branch, with the message `chore: preserve uncommitted work on flagged slice {m}`. The tree was clean when that branch was entered (step 5), so everything dirty is that slice's work.
     - Then `git checkout {target}`, and log a WARNING: `"left unmerged slice branch {m}-slice.… for {target}"`.
     - Any failure here goes to the D6 state check.
   - **Any other branch:** `GitEnvironmentError`: `"on {branch}, expected {target} or {slice_branch}"`.
5. **Clean tree:** `git status --porcelain` must be empty. Phase 4/5 commits are now scoped (D1), so unrelated edits stay in the tree and stop Phase 6 here. That is deliberate, because implement stages everything (D3).
   - The message lists the paths and the recovery: `"working tree not clean: {paths}. Commit or remove them, then rerun phase 6 for slice {n}; design and tasks commits from this run are kept."`
   - Every path an earlier scoped commit in the run left out was already named in that commit's WARNING (D2), so the operator can connect the two.
   - In P456 and P56 this ends the run after the planning commits. The rerun is the phase-6 pipeline on the same slice. `--resume` applies only to paused runs, and a dirty tree isn't a checkpoint decision.
6. **Switch:** if the slice branch exists, `git checkout {branch}`. Otherwise `git checkout -b {branch} {target}`.
   - If git reports the branch is checked out in another worktree, the action raises `GitEnvironmentError` with git's message and does not force.
   - Any other failure, or a timeout (`run_git` returns `None`), goes to the D6 state check with the expected branch set to the starting branch.

Outputs: `{"branch", "target", "created": bool}`.

### D6: `branch merge`

1. Re-read the target (D5.1). It is never taken from the enter step's output.
2. **Already merged** (the implement agent follows the same git rules and may merge on its own): if the current branch is the target and `git merge-base --is-ancestor {slice_branch} {target}`, the action succeeds with `merged: "already"`.
3. Otherwise the current branch must be the slice branch, and the tree must be clean.
4. `git checkout {target}`. If the target is checked out in another worktree, raise `GitEnvironmentError`. Any other failure or a timeout goes to the state check, with the slice branch as the expected branch.
5. `git merge --no-ff -m "merge: slice {index} — {name}" {slice_branch}`. This matches the repo's existing merge commits (`merge: slice 920 — …`).
6. **Any merge failure** (a conflict, a refusal such as untracked files that would be overwritten, or a timeout):
   - If `MERGE_HEAD` exists, run `git merge --abort`.
   - Then run the state check with the target as the expected branch.
   - If the check passes, it's an item failure: `"merge failed: {git stderr, or 'git timed out'}; slice branch {branch} left unmerged"`. A conflict lists the conflicted paths, taken from `git diff --name-only --diff-filter=U` before the abort.
   - Aborting keeps the target clean, so the next item (in 197) can branch from it.

**State check** (`verify_git_state(expected_branch)` in `pipeline/git_ops.py`), shared by enter, merge, and the commit action:
- It passes only when all three reads succeed:
  - `git rev-parse -q --verify MERGE_HEAD` finds nothing.
  - The current branch is the expected branch.
  - `git status --porcelain --untracked-files=no` is empty.
- Any failed or timed-out read, a failed `merge --abort`, or a mismatch raises `GitStateUnknownError` (a `GitEnvironmentError`).
  - The error names what was observed, for example `"target state unknown after merge of 105-slice.foo: MERGE_HEAD present, abort failed: …"`.
  - It is logged at ERROR and ends the run (D5). No later item builds on a target in an unknown state.

**Commit action:** a `git add` or `git commit` that exits non-zero with stderr (for example, a hook rejection) stays an ordinary action failure carrying that stderr. A timeout (`run_git` returns `None`) means nobody knows whether the commit landed, or whether `index.lock` is still held. It raises `GitStateUnknownError`.

**Batch report on a halted run:** `_execute_each_step` writes its report in a `finally`, so a `GitEnvironmentError` still produces the report, with the items recorded so far. Today the report is written after the loop, which an exception skips.

### D7: Pipelines gain branch steps

P6, `implement`, P456 and P56 are reordered to:

```
branch enter → implement → devlog → branch merge → summary
```

- **`devlog` commits its own entry.** `DevlogStepType.expand()` appends a commit action with `CommitSubject.DEVLOG`. Its plan stages only `DEVLOG.md`, with the message `docs: add DEVLOG entry for slice {n}` (`docs: add DEVLOG entry` with no slice). This holds in every pipeline.
  - In code pipelines the entry lands on the slice branch and merges with the slice. The merge then sees a clean tree (D6.3), and so does the next run's enter (D5.5).
- **`summary` runs last.** Its `file` emit writes under `~/.config/squadron/runs/summaries`, outside the repo, so it never dirties the tree.
- P6 and `implement` keep `checkpoint: on-fail`. A FAIL code review pauses before the merge. A CONCERNS review merges. That is the pipeline's existing accept rule, now applied to the merge.

### D8: Planning commits stay on the target

Phase 4/5 steps and their loops don't branch (git rules: planning work commits to the target). In P456 and P56 the design and tasks commits land on the target, then `branch enter` forks the slice branch from that state. That matches the manual workflow.

**Enforced in the commit action.** A commit whose subject isn't CODE must be on the target, with one exception: a DEVLOG commit may be on its own slice's branch, because in code pipelines the DEVLOG entry is written there (D7). Any other placement raises `GitEnvironmentError`: `"planning commit for slice {n} on {branch}; expected {target}"`. The target is read the same strict way as D5.1. This is the same guard D3 applies to code.

### D9: Dependencies come from design frontmatter

- `_slice_item` gains `dependencies: list[int]`, read from the design file's `dependencies:` frontmatter when `design_file` is set, and `[]` otherwise.
- **Parsing is lenient:** each element is taken as its leading integer, so `195`, `"195"` and `"195-slice.foo"` all parse to 195. An element with no leading integer (`foundation`) is dropped with a WARNING naming the slice and the value. It is never silently dropped.
- **Rejected: parsing slice-plan prose** (`Dependencies: [149 executor]`). That is free text inside a list item, and the designer has already transcribed it into structured frontmatter.
- **Rejected for now: a cf `dependencies` field.** That is a cross-repo change. Every item 197 runs over has a design, so frontmatter is enough. If a pre-design batch needs dependencies, a context-forge issue gets filed then.
- `slices-plan` items have no design and therefore no dependencies. Designing a slice whose dependency's design was flagged still proceeds, which is the existing behavior.

### D10: Dependency flags in `each`

- `_execute_each_step` keeps `flagged: set[int]`. Every FLAGGED item with an integer `index` is added, whether it was flagged by `flag_reason`, by failure, or by a dependency. Propagation is therefore transitive in run order.
- Before an item runs, `[d for d in item.get("dependencies", []) if d in flagged]` is checked. If it's non-empty, the item is recorded FLAGGED with reason `"dependency {d} flagged"` (several are joined with `"; "`), and the body is skipped. This happens under both failure policies, the same as `flag_reason` (195 D5).
- Items without `dependencies` (for example `app.yaml`'s) are unaffected. There's no opt-in flag.
- Order is unchanged (plan order). A dependency that comes later in the run than its dependent doesn't flag it. Reordering is 197's call.

### D11: `tasks-plan` re-review (d)

- **Source:** `cf.untasked_slices` is renamed `cf.slices_needing_tasks(plan, accept)` because its meaning changes. It selects open, designed slices that are either untasked, or tasked with a task review that is missing, unreadable, or below `accept`. The design-review `flag_reason` still applies first.
- **One threshold helper:** `_design_review_flag` becomes `_review_flag(entry, template, accept) -> str | None`, which computes the path with `slice_review_stem(index, template, …)`. Both checks call it, and the reason strings name the review (`"no tasks review found"`, `"tasks review below threshold (CONCERNS < PASS)"`). For selection, a non-None tasks result means the slice gets selected, not flagged.
- **`existing: keep`** on phase steps (an `ExistingArtifactPolicy` StrEnum with `CREATE` as the default and `KEEP`):
  - The phase step passes it, along with the artifact kind, into the dispatch config.
  - Under `KEEP`, when `expected_artifact_paths` already has an existing file, the dispatch action skips the model call and returns success with `outputs={"skipped": "artifact exists", "paths": [...]}`.
  - `DispatchArtifactAction` and the revision stamp treat `skipped` as satisfied, because the artifact exists by construction, and they don't stamp.
  - The phase step's review, the loop and the commit then run unchanged. A slice whose existing tasks pass on re-review costs one review.
- `tasks-plan.yaml` uses the renamed source and sets `existing: keep` on its `tasks:` step.

### D12: #152, a truncated PASS is imposed to CONCERNS

- `review/coverage.py` gains `impose_output_coverage(result)`. If `result.output_budget_exhausted` and the verdict is PASS, it sets the verdict to CONCERNS with `verdict_source = VerdictSource.IMPOSED`, and prepends a CONCERN finding (category `review-coverage`): "Output cut off at the model's output budget; findings after the cutoff are lost."
- It is called beside `impose_diff_coverage` (`review_client.py:326-328`), so `sq review` and pipelines behave identically.
- **Chosen over a frontmatter flag.** Every gate already reads `verdict`, and `verdictSource: imposed` plus the finding already record why. A separate `outputTruncated` key would be a second signal that each reader (the loop, `sources.py`, checkpoint, and Amoeba) would have to learn. Under `accept-threshold: review.concerns_or_better` the item is reported ACCEPTED, not PASSED, which is the visibility the issue asks for.
- Unlike 927, the tool-call count doesn't matter. Truncation loses findings however much the model read.

### D13: #175, unknown aliases fail before the run

- `models/aliases.py` gains:
  - `UnknownModelAliasError(name, close_matches)`.
  - `require_known_model(name, *, profile_source: bool)`. It passes when `name` is an alias, when `name` is a model id some alias resolves to (so a literal `claude-haiku-4-5-20251001` keeps working), or when a profile source exists. Otherwise it raises with `difflib.get_close_matches(name, aliases, n=3)`.
  - Message: `unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low? If this is a literal model ID, set a profile.`
- **Pre-run:** `classify_pipeline` already resolves every model-dispatching action against the params, with the resolver cascade (CLI override included), before execution (`run.py:325, 504`). It now calls `require_known_model` for each non-pool candidate. It collects every error and raises one error listing them all, before step 1. Today it resolves placeholders against `definition.params` only, the YAML defaults (`run.py:325`, `run.py:504`), so a mistyped `--param review-model=…` would slip past. `classify_pipeline` gains a `params` argument, and both call sites pass the merged params (defaults plus `--param` overrides, the same mapping the executor uses).
- **Backstop:** `ModelResolver._resolved` calls `require_known_model`. A model that only appears at run time (for example, one placed by a source item) fails its action before any request, so the review action never saves an artifact.
- **Pool members:** pools are already validated as alias references at load time (slice 180).
- `sq review`'s `_reject_unknown_alias` delegates to `require_known_model`, so both paths give the same message and the same close matches (interface parity).

### D14: #179, label with the candidate the resolver picks

- The cascade's first non-None candidate is pure (`ModelResolver.cascade_candidates`, which classification already uses). A helper, `action_model_candidate(resolver, action_type, action_config, step_model)`, is extracted from the classifier. `_summarize_action_config` calls it, so the label and the pre-run classification can't disagree.
  - Dispatch and review show `model=haiku` (the alias) or `model=pool:review`.
  - No candidate shows `model=session` for actions that may reuse the live session, matching the classifier's existing rule. The bare `default` and `None` labels go away.
- The result line keeps the answering model id from the action's metadata.

### Patterns and Conventions

- New enums (`BranchOp`, `CommitSubject`, `ExistingArtifactPolicy`) are StrEnums, defined once and referenced everywhere. No string literals are compared.
- Git calls go through `run_git`. Item failures return `ActionResult(success=False, error=…)` with git's stderr (or "git timed out"), logged at WARNING. Environment and unknown-state failures raise `GitEnvironmentError` / `GitStateUnknownError`, logged at ERROR. Nothing is swallowed.
- Paths are computed from cf and persistence helpers, never globbed.

## Implementation Details

### API Contracts

**Pipeline grammar additions**

```yaml
- branch: { op: enter | merge, slice: "<optional, default {slice}>" }
- tasks:  { ..., existing: keep }        # also accepted on design:
```

**Hidden CLI (prompt-only parity)**

```
sq _commit --subject design|tasks|architecture|code|devlog (--slice N | --plan N) [--template T] [--round N]
sq _branch enter|merge --slice N
```

At render time the prompt renderer fills `--template` and `--round` for a loop-round commit the same way the executor does: the template of the round's last review action, and the round number. A devlog commit takes no template or round.

Both print what they did on stdout (`committed <sha> <message>` / `on 105-slice.foo (created from main)`). They exit 1 with the same error text the actions produce.

**Source rename:** `cf.untasked_slices(plan, accept)` → `cf.slices_needing_tasks(plan, accept)`.

## Integration Points

### Provides to Other Slices

- **197:** `branch: {op: enter|merge}`. A flagged item's failure leaves the checkout either on the clean target (a merge failure, D6) or on its own unmerged slice branch, which the next item's enter preserves and leaves (D5.4). Either way, independent items continue. This comes with dependency flags in `each`, scoped commits for code (`stage_all` on the slice branch), and `existing: keep`. A flagged item's reason (`merge conflict…`, `dependency 196 flagged`) goes into the batch report for the Amoeba handoff.
- **183 and later convergence slices:** commit messages now carry slice, subject, round and verdict, so `git log` lines up with ledger rounds.
- **198:** the ARCHITECTURE commit subject already handles initiative-scoped commits. 198's `ArtifactKind.ARCH` can replace the `resolve_arch_file` call inside `build_commit_plan`.

### Consumes from Other Slices

- **195:** the `each` loop internals, `BatchReport`, and the sources module. The dependency check slots in beside the existing `flag_reason` check.
- **927:** the `impose_*` pattern in `review/coverage.py`.
- **cf:** `git.integration_branch`, `worktree list --json`, and `list slices --json` (`slicePlan`). A failing cf call fails the branch or commit action. Nothing degrades to a guessed value.

## Success Criteria

### Functional Requirements

1. A phase-4 step run with an unrelated modified file in the tree commits only the design, its review, and (if changed) the slice plan and DEVLOG. The unrelated file stays modified, and a WARNING names it.
2. Commit messages follow the D2 table. `git log` after a P4 run with one revise round shows `docs: add slice N design (review: …)` then `docs: revise slice N design, round 1 (review: …)` or `review: re-review …`. No `chore: phase-` or `loop-` messages appear.
3. A phase step that produced nothing logs a WARNING and creates no commit.
4. `sq run P6 N` from the target creates `N-slice.<name>`, implements and reviews on it (the code review resolves its diff range), and merges back with `merge: slice N — <name>`. The checkout ends on the target.
5. `branch enter` fails, without touching git state, for each of: a dirty tree, being on an unrelated branch, an unregistered worktree, a slice with no design file, and a cf config read failure.
6. A merge conflict leaves the target clean (no `MERGE_HEAD`), the slice branch unmerged, and the action FAILED with the conflicted paths. An already-merged slice branch makes `merge` succeed with `merged: already`.
7. A pipeline whose `implement` step has no preceding `branch: {op: enter}` fails `sq run --validate`, including when the implement is nested in a `loop:` or `each:` with no enter before the container.
7a. In a two-item batch composed as `each` → enter → implement → merge, where item 1's implement fails, item 1 is FLAGGED and left on `{1}-slice.…` with its leftovers committed. Item 2's enter returns to the target with a WARNING, and item 2 runs and merges.
7b. A design, tasks or architecture commit attempted on a branch other than the target raises `GitEnvironmentError`. A DEVLOG commit on its own slice branch succeeds.
8. In an `each` run where item 196 is flagged, item 197 (`dependencies: [196]`) is flagged `dependency 196 flagged` without running, and 197's dependents are flagged in turn. Independent items run.
9. `tasks-plan` selects a slice with tasks and a missing or below-threshold tasks review, skips its tasks dispatch (`existing: keep`), re-reviews it, and runs the revise loop as needed.
10. A review with a stated PASS and an exhausted output budget saves with `verdict: CONCERNS`, `verdictSource: imposed`, and the coverage finding, in both `sq review` and pipeline runs.
11. `sq run review 931 --model glm-flash-low.`, and equally `--param review-model=glm-flash-low.` on P4, exits 1 before any step, naming the alias and suggesting `glm-flash-low`. No review file is written or archived. `sq review slice 931 --model glm-flash-low.` prints the same message.
12. `sq run P456 102 --model haiku -v` labels every dispatch and review action `model=haiku`.

### Technical Requirements

- Unit tests cover `build_commit_plan` (every D2 row, nothing staged, left-out paths, a round with no review), and the `branch` action against a temporary git repo (every D5 and D6 guard, conflict, already merged).
- Tests also cover dependency flagging (direct, transitive, a dependency outside the run, a bad element), `existing: keep` (skip and post-condition pass), `impose_output_coverage`, `require_known_model` (alias, model id, profile source, close matches), and the `-v` label.
- Update the existing exact-equality `expand()` tests for the phase step's commit config.
- Every git test runs in a temporary repo created by the test, never the project checkout.
- Failure-path tests: `run_git` returning `None` during merge, checkout and commit; `merge --abort` failing; a non-conflict merge refusal; each path asserts the ERROR log and `GitStateUnknownError`, or an item failure when the state check passes. An `each` run halted by `GitEnvironmentError` still writes its report.
- `docs/PIPELINES.md` documents `branch:`, `existing: keep`, the source rename, and the commit message rules.
- ruff format, ruff check, and pyright are all clean.

### Integration Requirements

- 197 can compose `each` → `branch enter` → `implement` → review loop → `branch merge` with no engine changes.
- Prompt-only (`sq run --prompt-only P6 N`) renders `sq _branch` and `sq _commit` commands. Running them produces the same branches, staged paths and messages as the SDK executor.

### Verification Walkthrough

Use the scratch project (`…/scratchpad/sq-scratch`, toy "tally" CLI, plan 100, slices 101–107), with `CLAUDECODE` unset and `uv run --project <squadron>`.

1. **Scoped commit.**
   ```bash
   echo "# stray" >> README.md
   sq run P4 103 --model haiku
   git log --oneline -3      # docs: add slice 103 design (review: …), then revise/re-review lines
   git status --short        # README.md still modified, not committed
   ```
   The run log has `commit left unstaged: README.md`.

2. **Branch, implement, merge.**
   ```bash
   git checkout -- README.md
   sq run P6 103 --model haiku -v
   ```
   The `-v` log shows `branch enter` (`on 103-slice.<name> (created from main)`), `model=haiku` on the dispatch and review lines, a code review with a resolved diff range, and `branch merge`. Afterwards:
   ```bash
   git branch --show-current          # main
   git log --oneline --first-parent -2  # merge: slice 103 — <name>
   git branch --list '103-slice.*'    # still present
   ```

3. **Guards.** Make the tree dirty and run `sq run P6 104 --model haiku`. It fails with `working tree not clean: README.md`, and no branch is created. Then `git checkout -b scratch-other` and rerun on a clean tree. It fails with `on scratch-other, expected main or 104-slice.<name>`.

4. **Merge conflict.** On `main`, commit an edit to a file that slice 104's implementation will also change, then run P6 104. The merge fails with `merge conflict in …; slice branch 104-slice.<name> left unmerged`. `git status` is clean on `main`, and `git rev-parse -q --verify MERGE_HEAD` prints nothing.

5. **Dependency flags.** Give slice 105's design frontmatter `dependencies: [104]`, and make 104 fail its precondition by deleting its design review. Then run `sq run tasks-plan 100 --model haiku`. The report lists 104 as `no design review found` and 105 as `dependency 104 flagged`. Slices that don't depend on 104 run.

6. **Re-review gap.** For a slice that has a task file, delete its tasks review and rerun `tasks-plan 100`. The slice is selected, its log shows `dispatch skipped (artifact exists)`, and a new tasks review is written and committed as `review: add slice N tasks review (…)`.

7. **Unknown alias.** Run `sq run review 103 --model haiku.`. It exits 1 before any step with `unknown model alias 'haiku.'; did you mean: haiku?`, and `git status` shows no new review file. `sq review slice 103 --model haiku.` prints the same message.

8. **Truncated PASS.** Use a user alias with `max_output_tokens = 256` (as in #152) and run `sq review slice 103 --model <tiny-alias>`. If the model states PASS and stops at the budget, the artifact shows `verdict: CONCERNS`, `verdictSource: imposed`, and the review-coverage finding. The live result depends on the model, so the unit test is the gate and this step is a spot check.

9. **Prompt-only parity.** Run `sq run --prompt-only P6 106`. The rendered actions include `sq _branch enter --slice 106`, `sq _commit --subject code --slice 106 …`, and `sq _branch merge --slice 106`. Running them by hand gives the same result as step 2.

## Risk Assessment

### Technical Risks

- **Git writes in unattended runs.** A bug in merge could leave the target mid-merge or on the wrong branch, and every later item would build on it.
- **The implement agent follows the same git rules** and may branch, commit, or merge on its own, racing the steps.

### Mitigation Strategies

- Every git test runs in a temporary repo. On any failure, merge aborts and returns to the target. There is no `--force`, no `reset`, and no branch deletion anywhere.
- `branch enter` runs before the agent, so the agent finds itself on the expected branch (rule 3 of the git rules), and `merge` accepts an already-merged branch (D6.2). A commit by the agent on the slice branch is just more slice work.

## Implementation Notes

### Development Approach

1. **#175 and #179** (`require_known_model`, the classifier check, the resolver backstop, the shared candidate helper). They are small and independent, and they protect every later live test from a mistyped alias.
2. **#152** (`impose_output_coverage`).
3. **(a)** `commit_plan.py`, `CommitAction`, the phase-step and loop-round callers, and `sq _commit`.
4. **(b)** `pipeline/git_ops.py` (strict target reader, state check, errors), `BranchAction`, `BranchStepType`, the implement validation rule, `sq _branch`, and the pipeline YAML. This depends on (a) for D3.
5. **(c)** item dependencies and the `each` flag set.
6. **(d)** `_review_flag`, the source rename, and `existing: keep`.
7. Update `docs/PIPELINES.md` and run the live walkthrough in the scratch project.

### Special Considerations

- `resolve_diff_base` keeps its degrade-to-`main` behavior for review diffs. Changing it is outside this slice. Branch and commit code use the strict reader only.
- The existing loop validation rule stays: `commit_each_iteration` is rejected when the body already commits, and the findings-addressed gate's per-round commit requirement is unchanged.
- Effort: 4/5 (raised from the plan's 3/5: six independent fixes plus a git-writing step type).
