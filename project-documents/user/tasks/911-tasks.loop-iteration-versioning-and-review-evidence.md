---
docType: tasks
slice: loop-iteration-versioning-and-review-evidence
project: squadron
lld: user/slices/911-slice.loop-iteration-versioning-and-review-evidence.md
dependencies: [910, 909]
projectState: >
  Slice 911 design complete. Part D (reviewer access to prior versions) split
  out to slice 912 during design. Artifact field named revision_number, not
  version; ai-project-guide issue #14 filed to register it in the canonical
  frontmatter schema. Three parts remain: A per-iteration commits (#44),
  B revision_number stamping, C the round contract and docs. Not yet branched.
dateCreated: 20260731
dateUpdated: 20260731
status: not_started
---

## Context Summary

- Working on the **loop-iteration-versioning-and-review-evidence** slice (911),
  a maintenance slice making a `loop:` iteration *legible* — recoverable from
  git, identifiable from the artifact, and governed by a stated contract.
  Parent: `900-slices.maintenance-and-refactoring.md`. Slice 910 made an
  iteration converge; this one makes it provable.
- **Part A (#44):** loop iterations leave no usable history. Verified on disk,
  and more nuanced than the issue states:
  - `commit` is an **action**, not a step type — absent from `StepTypeName`
    (`steps/__init__.py:24-38`), emitted only by phase-step expansion
    (`phase.py:176`), and `docs/PIPELINES.md` documents "no per-iteration
    commit" as a hard constraint.
  - A **phase-bodied** loop (`p45b.yaml`) *does* commit each round — but the
    commit is last in `[cf-op ×3, dispatch, review, checkpoint, commit]`, and
    `_execute_step_once` returns early on any action failure
    (`executor.py:1116-1124`) or a checkpoint `Exit` (`executor.py:1104-1111`).
    `checkpoint: on-fail` fires on FAIL and UNKNOWN (`checkpoint.py:23`) and
    sits one line before the commit (`phase.py:174-176`), so an Exit discards
    the round. Every round that *is* kept emits the identical message.
  - A **dispatch-bodied** loop (`judge-cycle.yaml`, `test-loop.yaml`) commits
    nothing at all.
  - `CommitAction` no-ops on a clean tree, returning `committed: False`
    silently (`commit.py:37-42`) — so a byte-identical round, the #42 symptom,
    leaves no trace and no warning.
- **Part B:** squadron stamps an integer `revision_number:` into the
  frontmatter of the artifact a loop iteration produces, and emits the same
  field on review files it authors. No generic frontmatter read/modify/write
  utility exists today; this slice adds one.
- **Part C:** clean regeneration is the contract (`revision_number:` is the
  only carryover); absent means "never stamped by squadron", explicitly not
  round 1. Plus the `docs/PIPELINES.md` correction and the `--dry-run` line.
- **Order: A1 → B → A2/A3 → C.** A1 first because both Part A's messages and
  Part B's review-file stamping depend on `ActionContext.iteration`. B second
  because it is the only genuinely new code and the only part that can corrupt
  a document squadron did not author.
- **`iteration` sentinel:** `0` means "not executing inside a loop." Existing
  convention — `_execute_step_once` declares `iteration: int = 0`
  (`executor.py:995`) and only the two loop paths pass it (`:1201`, `:1309`);
  top-level, `each`, and `fan_out` callers take the default. Do not introduce
  `int | None`.
- **Field name is provisional-but-decided.** `revision_number` per PM decision.
  ai-project-guide issue #14 proposes registering it upstream; if that issue
  settles on a different name, rename before Phase 6 completes rather than
  migrating after. Do not change the name on your own initiative.
- **Out of scope, do not touch:** Part D / slice 912 (nothing here changes what
  a reviewer sees), registering a `commit` step type, the `on_exhaust: skip`
  fall-through deferred by 910, review file naming, and the
  `ai-project-guide` submodule.

---

## Part A1 — `ActionContext.iteration` and Iteration-Qualified Commits

- [ ] **T1. Add `iteration` to `ActionContext` and populate it**
  - [ ] In `src/squadron/pipeline/models.py`, add `iteration: int = 0` to the
    `ActionContext` dataclass (line 46). It must go **after** `step_outputs`
    (line 62) — the preceding fields already carry defaults, so a
    non-defaulted field cannot be inserted before them.
  - [ ] Add a short comment stating the sentinel: `0` means the step is not
    executing inside a loop; `>= 1` is the 1-based iteration index.
  - [ ] In `src/squadron/pipeline/executor.py`, pass `iteration=iteration` into
    the `ActionContext(...)` construction at lines 1044-1056. The enclosing
    `_execute_step_once` already declares the parameter (line 995) — no
    signature change is needed anywhere.
  - [ ] Success: `pyright` strict passes; every existing test still passes; no
    caller of `_execute_step_once` is modified.

- [ ] **T2. Qualify the composed commit message with the iteration**
  - [ ] In `src/squadron/pipeline/actions/commit.py`, after the message is
    composed from `type` / `message_prefix` / `slice` (lines 63-76), append
    ` (iteration {n})` when `context.iteration >= 1`.
  - [ ] An explicit `message:` param (line 64) is used **verbatim** and must
    **not** be suffixed — an explicit message is a caller contract, not a
    template. Add a comment saying so.
  - [ ] Do not introduce a second sentinel or a magic literal for the suffix
    format; define the format string once at module level alongside the
    existing module constants.
  - [ ] Success: outside a loop (`iteration == 0`) the message is byte-identical
    to today's.

- [ ] **T3. Tests for A1** (test-with — must pass before Part B starts)
  - [ ] In `tests/pipeline/actions/test_commit.py` (create if absent): composed
    message gains ` (iteration 2)` when `context.iteration == 2`.
  - [ ] Composed message is unchanged when `context.iteration == 0`.
  - [ ] Explicit `message:` param is emitted verbatim with `iteration == 2` set.
  - [ ] In the executor tests, assert the `ActionContext` an action receives
    inside a loop body carries the loop's iteration number, and that the same
    step executed outside a loop receives `0`.
  - [ ] Success: all four pass; full `tests/pipeline/` suite green.

---

## Part B — `revision_number` Stamping

- [ ] **T4. New module `src/squadron/documents/frontmatter.py`**
  - [ ] Create the package `src/squadron/documents/` with `__init__.py`.
  - [ ] `read_frontmatter(path: Path) -> dict[str, object] | None` — tolerate a
    BOM and leading blank lines before the opening `---`, split on the closing
    `---`, `yaml.safe_load` the block. Return `None` when there is no block or
    it does not parse to a mapping. Model the leniency on the existing
    `read_review_frontmatter` (`metrology/identity.py:162-196`), which is the
    reference implementation for this project's real files.
  - [ ] `update_frontmatter(path: Path, fields: dict[str, object]) -> None` —
    read, merge `fields` over the existing keys, write back. Existing key order
    is preserved and new keys are appended to the end of the block. **The
    document body must be preserved byte-for-byte.**
  - [ ] Raise a specific, named exception on a malformed or absent block —
    callers decide whether that is fatal. Do not return a default.
  - [ ] Success: module is under ~120 lines; `ruff` and `pyright` strict clean.

- [ ] **T5. Tests for the frontmatter helpers**
  - [ ] New `tests/documents/test_frontmatter.py`.
  - [ ] `read_frontmatter` handles: normal block, BOM-prefixed file, leading
    blank lines, no block at all, block that parses to a scalar not a mapping.
  - [ ] `update_frontmatter` adds a new key, updates an existing key, and
    preserves the order of untouched keys.
  - [ ] **Byte-preservation test against a real project document** — copy an
    actual file from `project-documents/user/slices/` into `tmp_path`, run an
    update that changes one key, and assert everything after the closing `---`
    is byte-identical to the original. A synthetic fixture does not satisfy
    this task (project rule: a parser's fixture must be the format it consumes
    in production).
  - [ ] Malformed input raises the named exception rather than returning a
    default.
  - [ ] Success: all pass.

- [ ] **T6. Delegate `read_review_frontmatter`'s parse to the new helper**
  - [ ] In `src/squadron/metrology/identity.py`, replace the inline parse in
    `read_review_frontmatter` (lines 162-196) with a call to
    `read_frontmatter`, keeping its review-specific validation and its
    `MetrologyTargetError` behavior exactly as-is.
  - [ ] Its docstring asserts it is the only reader of a persisted review —
    that stays true and the docstring stays accurate; update only the sentence
    describing how it parses.
  - [ ] Goal is one lenient parser in the codebase, not two. Do not change any
    of its six consumers (`discovery.py`, `capture.py`, `report.py`,
    `graduation.py`).
  - [ ] Success: the full `tests/metrology/` suite passes unchanged.

- [ ] **T7. Tests for the delegation**
  - [ ] Assert `read_review_frontmatter` still raises `MetrologyTargetError`
    for each input shape it rejected before the refactor (no block, non-mapping
    block, missing required review keys).
  - [ ] Success: `tests/metrology/` fully green with no test modified to
    accommodate the refactor. If a test needs changing, the refactor changed
    behavior — stop and reassess.

- [ ] **T8. Stamp `revision_number` after the dispatch post-condition**
  - [ ] In `src/squadron/pipeline/executor.py`, extend the existing
    post-condition block (lines 1064-1082). After `artifact_error is None`
    confirms the artifact was written this run, stamp each path returned by
    `_expected_artifact_paths()` (lines 109-121).
  - [ ] Gate on `expected_kind is not None` **and** `ctx.iteration >= 1`. A
    phase step outside a loop is not stamped.
  - [ ] Value rule: read the existing `revision_number`; if present and an
    `int`, write `n + 1`; otherwise write `1`. It is a count of squadron
    stamps, **not** the loop's iteration index — do not write `ctx.iteration`.
  - [ ] Failure mode: if the file cannot be parsed or rewritten, log at WARNING
    naming the path and the reason, and continue. A failed evidence stamp must
    not fail a converging loop. This is explicit and observable, not a silent
    fallback — do not swallow the exception without logging.
  - [ ] Extract the stamping into a small named helper rather than inlining it;
    `_execute_step_once` is already long.
  - [ ] Success: `ruff`, `pyright` strict clean.

- [ ] **T9. Tests for stamping**
  - [ ] In `tests/pipeline/` (alongside the existing post-condition tests):
    absent prior value → `1`; existing `3` → `4`; existing non-int (e.g. a
    string) → `1`.
  - [ ] Not stamped when `iteration == 0`; not stamped when `expected_kind` is
    `None`; not stamped when the post-condition failed.
  - [ ] An unwritable or malformed target logs a WARNING **and** the dispatch
    still reports success (assert on the log record, per
    `.claude/rules/review-code.md` — every failure path needs an observable
    signal and a test asserting it).
  - [ ] Success: all pass.

- [ ] **T10. Emit `revision_number` on review files**
  - [ ] In `src/squadron/review/persistence.py`, give `format_review_markdown`
    an optional `revision_number` parameter, emitted in the frontmatter block
    (lines 130-165) only when supplied. Place it adjacent to the other
    document-identity fields, not among the findings.
  - [ ] In `src/squadron/pipeline/actions/review.py`, pass
    `context.iteration` when it is `>= 1` and pass nothing when it is `0`.
  - [ ] Do not touch the CLI review path (`cli/commands/review.py`) — it never
    runs inside a loop and must keep emitting no such key.
  - [ ] Success: `ruff`, `pyright` strict clean.

- [ ] **T11. Tests for the review-file field**
  - [ ] `format_review_markdown` omits the key entirely when no
    `revision_number` is supplied — asserts absence, not `0` or `1`.
  - [ ] The key is present with the right value when supplied.
  - [ ] A review action inside a loop body produces a file carrying the key; a
    review action outside a loop produces one without it.
  - [ ] Success: full `tests/review/` and `tests/pipeline/` suites green.

---

## Part A2 / A3 — `commit_each_iteration` and the No-Change Warning

- [ ] **T12. Validate `commit_each_iteration` in `LoopStepType.validate()`**
  - [ ] In `src/squadron/pipeline/steps/loop.py`, validate the new optional key:
    if present it must be a `bool`, matching the shape of the existing `max`
    and `strategy` validators (lines 38-86). Note `bool` is a subclass of
    `int` — here that is what we want, but do not accept `0`/`1`.
  - [ ] When it is `true`, reject a body that already commits: walk the inner
    steps and return a `ValidationError` naming the offending step if any
    expands to a `commit` action.
  - [ ] **Reuse the existing traversal in `_validate_verdict_count`
    (lines 165-213) rather than adding a second one.** That helper already
    unpacks inner steps, resolves step types, and — critically — skips any
    inner step that fails its own `validate()` before calling `expand()`,
    because `expand()` raises `KeyError` on an incomplete config
    (lines 186-190). A new independent walk would reintroduce that crash.
    Factor the shared walk out; do not copy it.
  - [ ] Error message must be actionable: name the inner step and state that
    phase steps already commit each iteration, so `commit_each_iteration`
    should be removed.
  - [ ] Success: `ruff`, `pyright` strict clean.

- [ ] **T13. Tests for the validation**
  - [ ] In `tests/pipeline/steps/test_loop.py`: non-bool value rejected.
  - [ ] `commit_each_iteration: true` with a `phase`-typed inner step rejected,
    with the offending step named in the message.
  - [ ] `commit_each_iteration: true` with a dispatch+review body accepted.
  - [ ] Absent key accepted (default false) — existing loop pipelines unchanged.
  - [ ] An inner step with a malformed config does **not** crash the new check
    (regression guard for the `expand()` `KeyError` noted in T12).
  - [ ] Verify the real `p45b.yaml` still validates: `sq run --validate p45b`.
    Pipeline names omit the `.yaml` extension; the loader appends it.
  - [ ] Success: all pass.

- [ ] **T14. Append a commit action per iteration in `_execute_loop_body`**
  - [ ] In `src/squadron/pipeline/executor.py`, in `_execute_loop_body`
    (lines 1251-1370), when `commit_each_iteration` is set, execute one commit
    action after the body's inner steps complete for that iteration — before
    the `until:` evaluation at line 1348.
  - [ ] Pass `message_prefix: "loop-{step.name}"` and the current `iteration`,
    so T2's suffix produces a distinguishable message per round.
  - [ ] Fold its `ActionResult` into `iteration_action_results` and into
    `running_prior` using the same key scheme already in place at lines
    1332-1334 — do not invent a second scheme.
  - [ ] Staging behavior stays identical to the phase-emitted commit
    (`git add -A`). Do not add scoped staging in one commit path and not the
    other; the inconsistency is worse than the sweep.
  - [ ] Success: `ruff`, `pyright` strict clean.

- [ ] **T15. Tests for per-iteration commits**
  - [ ] In `tests/pipeline/test_executor_loop_body.py`: with
    `commit_each_iteration: true`, a three-iteration loop invokes the commit
    action three times, each with a distinct iteration.
  - [ ] With the key absent, the commit action is never invoked — existing
    loops are unaffected.
  - [ ] The commit result appears in that iteration's `action_results`.
  - [ ] Success: all pass.

- [ ] **T16. Warn when an iteration changed nothing**
  - [ ] In `src/squadron/pipeline/actions/commit.py`, on the clean-tree
    early-return path (lines 37-42), log at WARNING when
    `context.iteration >= 1`, naming pipeline, step, and iteration.
  - [ ] Message must say what it means: the iteration produced byte-identical
    output, i.e. the retry did not change anything.
  - [ ] Outside a loop (`iteration == 0`) a clean tree is normal — no warning.
  - [ ] Keep the return value unchanged (`success=True`,
    `outputs={"committed": False}`); this task adds a signal, not a failure.
  - [ ] Success: `ruff`, `pyright` strict clean.

- [ ] **T17. Tests for the no-change warning**
  - [ ] Clean tree with `iteration == 2` emits a WARNING naming the iteration
    (assert on the captured log record).
  - [ ] Clean tree with `iteration == 0` emits no warning.
  - [ ] The action still returns `success=True` and `committed: False` in both.
  - [ ] Success: all pass.

---

## Part C — Contract, Dry-Run, and Documentation

- [ ] **T18. Show `commit_each_iteration` in `--dry-run`**
  - [ ] In `src/squadron/cli/commands/run.py`, extend the loop-expansion block
    added by slice 910 Part C to print `commit_each_iteration` when set,
    alongside `max`, `until`, and `on_exhaust`.
  - [ ] Follow the existing convention in that file: hoist any fixed display
    string to a module-level constant next to `_DRY_RUN_NO_UNTIL_DISPLAY`
    rather than inlining a literal.
  - [ ] Success: `sq run --dry-run p45b 911` renders without error.

- [ ] **T19. Test for the dry-run line**
  - [ ] In `tests/cli/commands/test_run.py`: a loop with
    `commit_each_iteration: true` renders the line; a loop without the key does
    not. Assert against the module constant, not a duplicated literal.
  - [ ] Success: both pass.

- [ ] **T20. Update `docs/PIPELINES.md`**
  - [ ] Replace the section titled "Constraint: no per-iteration commit" — it
    becomes false with T14. State instead: `commit_each_iteration` (opt-in,
    default false), that phase-bodied loops already commit and must not set it,
    and that the commit runs after the body and before the `until:` check.
  - [ ] Document the `revision_number:` contract in the same pass — what it
    counts, that squadron alone writes it, that absent means "never stamped"
    and not round 1, which docTypes it applies to, and that nothing should
    branch on its value. Source the wording from the slice design's **Field
    contract** table so the two do not drift.
  - [ ] Note the clean-regeneration rule: a round regenerates the artifact and
    `revision_number:` is the only carryover; round history lives in git.
  - [ ] Success: no statement in the file contradicts shipped behavior.

- [ ] **T21. Final validation gate and close-out**
  - [ ] `ruff format .` then `ruff format --check .`, then `ruff check .`.
  - [ ] `pyright` full-project strict — zero errors is a merge blocker.
  - [ ] Full `tests/` suite; compare pass/skip counts against the pre-slice
    baseline and account for every difference.
  - [ ] Walk the slice design's **Verification Walkthrough** end to end and
    correct it in place against real output — it is a draft written before
    implementation, exactly as 910's was.
  - [ ] Confirm the artifact-facing claims by hand: run a loop that takes more
    than one round, then check `git log --oneline -- <artifact>` shows one
    commit per round with distinguishable messages, and that the artifact's
    frontmatter carries `revision_number:`.
  - [ ] Re-check ai-project-guide issue #14 before closing: if it settled on a
    different field name, rename now rather than shipping a name that will need
    migrating.
  - [ ] Delegate task-file checkbox updates to the `task-checker` agent.
  - [ ] Set `status: complete` in the slice design frontmatter; check off
    entry 9 in `900-slices.maintenance-and-refactoring.md` with the completion
    date; add CHANGELOG entries (short, user-facing) and a Phase 6 DEVLOG entry.
  - [ ] Close issue #44 on merge. Do not close anything belonging to slice 912.
  - [ ] Success: gate fully clean, walkthrough reproduced, slice marked complete.
