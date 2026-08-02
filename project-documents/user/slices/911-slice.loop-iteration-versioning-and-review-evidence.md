---
docType: slice-design
slice: loop-iteration-versioning-and-review-evidence
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [910]
interfaces: [912]
dateCreated: 20260731
dateUpdated: 20260801
status: complete
---

# Slice Design: Loop Iteration Versioning and Review Evidence

## Overview

Slice 910 made a `loop:` iteration *converge* — findings from round N now reach
round N+1's prompt. This slice makes an iteration *legible*: recoverable from
git, identifiable from the artifact itself, and governed by a stated contract
about what survives a round.

Fixes [issue #44](https://github.com/ecorkran/squadron/issues/44) (no commit
between iterations) plus two adjacent problems it does not record: the artifact
carries no round indicator, and there is no written contract for whether a
round regenerates or accumulates.

**Part D is not in this slice.** The slice plan scoped a fourth part — whether
review notes carry forward and whether a reviewer may see the prior version —
and flagged it as needing a design conversation rather than a design document.
It is carved out to **slice 912**, which this slice enables: a "were the prior
findings addressed?" check is only answerable once there is a prior round to
diff against, which is exactly what Part A creates.

## Value

Evidence integrity for the pipeline's quality-gate construct. Today a
three-iteration loop leaves one artifact on disk and no way to answer the two
questions that matter after the fact:

- *Did the loop actually converge, or did it re-roll the same prompt?* Without
  per-round history there is nothing to diff. This is precisely the symptom
  910 Part A fixed, and precisely the symptom nothing can currently prove was
  fixed.
- *Which round is this artifact, and what verdict did it last survive?* Open a
  slice design produced by a loop and it is silent on both.

The value is diagnostic and auditable, not user-facing: a converging loop that
cannot be inspected is a convergence claim taken on faith.

## Technical Scope

**Included:**

- **Part A — per-iteration commits.** Make each loop iteration leave a
  distinguishable commit, for loop bodies that commit today and for bodies that
  do not; make a byte-identical round observable rather than silent.
- **Part B — `revision_number:` on the artifact.** Squadron stamps a monotonic integer
  `revision_number:` into the frontmatter of the artifact a loop iteration produces,
  and emits the same field on the review file it authors itself.
- **Part C — the round contract.** State and document what survives a round
  (clean regeneration; `revision_number:` is the only carryover) and what an absent
  `revision_number:` means.

**Excluded:**

- **Part D — review-note carry-forward and reviewer access to prior versions.**
  Moved to slice 912. Nothing in this slice changes what a reviewer sees.
- **Registering a `commit` step type.** `commit` is an action, not a step type
  ([steps/\_\_init\_\_.py:24-38](src/squadron/pipeline/steps/__init__.py#L24-L38)
  has no `COMMIT` member). Part A adds a loop-level option, not a new step type
  — see Technical Decisions.
- **`on_exhaust: skip` fall-through.** The 910 design deferred this; still
  deferred, and untouched here.
- **Review file naming.** Review files are still overwritten per run under the
  same name; Part B makes them self-describing, it does not version their
  filenames.
- **Changing the canonical frontmatter schema in `ai-project-guide`.** See
  Part C — recorded as a cross-repo follow-up, not done here.

## Dependencies

### Prerequisites

- **Slice 910** (complete). Part A of 910 defines what an iteration produces
  and feeds forward; this slice records it. 910 Part B's one-review-per-body
  rule is also the shape Part A's commit-message and validation work assume.
- **Slice 909 Part A** (complete). `_expected_artifact_paths()`
  ([executor.py:109-121](src/squadron/pipeline/executor.py#L109-L121)) and the
  dispatch artifact post-condition
  ([executor.py:1064-1082](src/squadron/pipeline/executor.py#L1064-L1082))
  are the hook Part B stamps from. Without them squadron would not know which
  file a dispatch was supposed to write.

### Interfaces Required

- **Context Forge** supplies the artifact paths — `design_file` and
  `task_files`, read via `resolve_slice_info`
  ([integrations/context_forge.py:114-135](src/squadron/integrations/context_forge.py#L114-L135)).
  Part B stamps whatever CF names; it does not compute paths itself.
- **git**, via the existing `CommitAction` subprocess wrapper
  ([actions/commit.py:104-114](src/squadron/pipeline/actions/commit.py#L104-L114)).

## Architecture

### Verified current behavior

Issue #44 states that iterations overwrite artifacts "with no commit in
between." That is true for some loop bodies and false for others, and the
design depends on the distinction:

- `commit` is emitted **only** by phase-step expansion
  ([steps/phase.py:176](src/squadron/pipeline/steps/phase.py#L176)), which
  appends `("commit", {"message_prefix": f"phase-{phase}", "slice": slice_ref})`
  unconditionally at the end of every phase step.
- Therefore a loop whose body is **phase steps** already commits once per
  iteration — *conditionally*. `p45b.yaml`'s two loops are this shape, and the
  condition matters: the commit is the **last** action in the expansion
  `[cf-op, cf-op, cf-op, dispatch, review, checkpoint, commit]`, and
  `_execute_step_once` returns immediately on any action failure
  ([executor.py:1116-1124](src/squadron/pipeline/executor.py#L1116-L1124)) or
  on a checkpoint `Exit`
  ([executor.py:1104-1111](src/squadron/pipeline/executor.py#L1104-L1111)).
  A review action returns `success=True` regardless of verdict
  ([actions/review.py:288](src/squadron/pipeline/actions/review.py#L288)), so a
  `FAIL` alone does not skip the commit — but `checkpoint: on-fail` fires on
  `FAIL` and `UNKNOWN`
  ([actions/checkpoint.py:23](src/squadron/pipeline/actions/checkpoint.py#L23)),
  and it sits *before* the commit
  ([steps/phase.py:174-176](src/squadron/pipeline/steps/phase.py#L174-L176)).
  Choosing `Exit` at that prompt therefore discards the round: no commit, and
  the loop short-circuits to `PAUSED`. The rounds most worth keeping are the
  ones most likely to be dropped.
- A loop whose body is a bare **`dispatch:`** step commits nothing.
  `judge-cycle.yaml` and `test-loop.yaml` are this shape.
- `CommitAction` no-ops when the tree is clean, returning
  `success=True, outputs={"committed": False}`
  ([commit.py:37-42](src/squadron/pipeline/actions/commit.py#L37-L42)). So a
  byte-identical round — the "useful signal" #44 hopes for — currently leaves
  **no** trace of any kind.
- `docs/PIPELINES.md` documents the gap as a hard constraint ("Constraint: no
  per-iteration commit"), which this slice makes obsolete and must update.

Two consequences: the phase-bodied case needs commit messages that *identify*
the round (three identical `chore: phase-4 slice 911` entries are not history),
and the dispatch-bodied case needs a commit at all.

### Component Structure

| Component | Change |
|---|---|
| `pipeline/models.py` — `ActionContext` | New `iteration: int = 0` field (0 = not in a loop) |
| `pipeline/executor.py` — `_execute_step_once` | Populate `ctx.iteration`; stamp `revision_number:` after the artifact post-condition passes |
| `pipeline/executor.py` — `_execute_loop_body` | Append a commit action per iteration when `commit_each_iteration` is set |
| `pipeline/steps/loop.py` — `LoopStepType.validate` | Validate `commit_each_iteration`; reject it when the body already commits |
| `pipeline/actions/commit.py` — `CommitAction` | Iteration-qualified message; WARNING on a no-change round inside a loop |
| `documents/frontmatter.py` **(new)** | Generic lenient frontmatter read / update helpers |
| `metrology/identity.py` — `read_review_frontmatter` | Delegate its parse to the new helper (DRY), keep its review-specific validation |
| `review/persistence.py` — `format_review_markdown` | Emit `revision_number:` when the caller supplies one |
| `pipeline/actions/review.py` | Pass `context.iteration` through to persistence |
| `cli/commands/run.py` | `--dry-run` prints `commit_each_iteration` |
| `docs/PIPELINES.md` | Replace the "no per-iteration commit" constraint |

### Data Flow

Per iteration of a `loop:` step, with `commit_each_iteration: true` and a
phase-shaped body:

```
_execute_loop_body(iteration=N)
  └─ _execute_step_once(inner_step, iteration=N)
       ├─ ActionContext(iteration=N)              ← new field
       ├─ dispatch  → agent writes design_file
       │    └─ post-condition passes (909)
       │         └─ update_frontmatter(design_file, revision_number=prev+1)
       ├─ review    → format_review_markdown(..., revision_number=N)
       └─ commit    → "chore: phase-4 slice 911 (iteration N)"        ← Part A
            └─ committed == False → WARNING                            ← Part A
```

The stamp happens *after* the post-condition, so squadron only ever writes into
a file it has already confirmed the dispatch produced this run.

## Technical Decisions

### Part A — per-iteration commits

**A1 — Iteration-qualified commit messages.** `ActionContext` gains
`iteration: int = 0`. `_execute_step_once` already receives an `iteration`
parameter and already constructs the `ActionContext`
([executor.py:1044-1056](src/squadron/pipeline/executor.py#L1044-L1056)); it
passes the value straight through. `CommitAction` appends ` (iteration {n})` to
the message it *composes* when `context.iteration >= 1`.

**Sentinel: `0` means "not executing inside a loop."** This is not a new
convention — `_execute_step_once` already declares `iteration: int = 0`
([executor.py:995](src/squadron/pipeline/executor.py#L995)), and only the two
loop paths pass it (`_execute_loop_step` at
[:1201](src/squadron/pipeline/executor.py#L1201) and `_execute_loop_body` at
[:1309](src/squadron/pipeline/executor.py#L1309)); the top-level, `each`, and
`fan_out` callers take the default. Mirroring it on `ActionContext` keeps one
sentinel in the codebase. Introducing `int | None` here instead would force a
conversion at the one place the two meet, which is strictly worse.

An explicit `message:` param is used verbatim and is **not** suffixed — an
explicit message is a caller contract, not a template. Documented, not silent.

**A2 — `commit_each_iteration` on `loop:`, opt-in.** A new boolean loop option,
default false, so no existing pipeline starts writing history unexpectedly.
When true, `_execute_loop_body` appends one commit action after the body's inner
steps in each iteration, with `message_prefix: "loop-{step.name}"` and the A1
iteration suffix.

*Rejected: registering a `commit` step type so it can appear in the body.* That
is a larger change (a step type carries validation, expansion, and dry-run
surface) for a strictly weaker guarantee — an in-body commit could be placed
before the review, capturing the round without its verdict. Loop-level
placement is unambiguous: after everything the iteration did.

*Rejected: automatic (non-opt-in) commits.* `judge-cycle.yaml` and
`test-loop.yaml` would begin writing commits into a user's repo on upgrade.

**Validation — reject the double-commit rather than tolerating it.** A
phase-bodied loop with `commit_each_iteration: true` would commit twice per
round; the second is a silent no-op today because the tree is already clean.
`LoopStepType.validate` walks the body with `get_step_type(...).expand(...)` —
the same machinery `_validate_verdict_count` already uses
([steps/loop.py:165-213](src/squadron/pipeline/steps/loop.py#L165-L213)) — and
if any inner step expands to a `commit` action while `commit_each_iteration` is
true, it returns an actionable `ValidationError` naming the step. This mirrors
910 Part B's stance: reject the ambiguity, do not resolve it silently.

**A3 — A no-change round must be observable.** When `CommitAction` finds a
clean tree and `context.iteration >= 1`, it logs at WARNING naming
pipeline, step, and iteration. A round that produced byte-identical output is
the #42 symptom; it is currently indistinguishable from success. Per
`.claude/rules/review-code.md` (failure-mode enumeration) at least one test
asserts the WARNING is emitted.

### Part B — `revision_number:` in frontmatter

**Field.** A plain integer `revision_number: {n}` — deliberately not semver. An
iteration count is a counter, not a compatibility contract.

**Semantics.** Monotonic count of squadron-stamped revisions of that file. On
stamp: read the existing value; if present and an `int`, write `n+1`; otherwise
write `1`. The value is not the loop's iteration index, so re-running a
pipeline against an existing artifact continues the count rather than resetting
it to 1 — which is what "which revision am I looking at" actually means.

#### Field contract — what `revision_number:` means to anyone who reads it

Adding a field makes it usable. Once it exists in a document other tools and
agents read, they will read it, and some will write it. The contract below is
therefore part of the deliverable, not commentary on it — it is the text that
must accompany the field wherever it is documented, including the eventual
`ai-project-guide` schema entry.

| Question | Answer |
|---|---|
| What does it count? | The number of times **squadron** has stamped this file. Nothing else. |
| Who writes it? | Squadron's loop-iteration stamping path, only. |
| Who must **not** write it? | Humans, agents authoring or editing the document, and any other tool. A hand-edit is not a squadron revision, and bumping it by hand makes the count mean nothing. |
| Is it semver? | No. Not major/minor/patch, no ordering relationship to any release, no compatibility meaning. |
| Is it the loop's iteration index? | No. Three rounds in run 1 then two in run 2 gives `5`, not `2`. It counts revisions of the document, not position in a loop. |
| What does absent mean? | "Never stamped by squadron." Explicitly **not** round 1, and not a default. Readers must treat absent as *no information*. |
| Which docTypes? | `slice-design` and `tasks` — the artifacts a phase-step dispatch produces — plus `review`, which squadron authors itself. Undefined elsewhere; do not infer it onto other docTypes. |
| Does `1` mean the document is new? | No. It means it is the first squadron-tracked revision. It makes no claim about what preceded it. |
| Can it decrease or reset? | No. It is monotonic per file. A file that loses its `revision_number:` has been hand-edited, not reset. |
| What is it *for*? | Naming a round so a reader — human or slice 912's findings-addressed check — can say which revision they are looking at. It is an identifier, not a state machine. |

The failure this table is written against: a field named `version` in a
document header reads, to anything that has not been told otherwise, like a
compatibility contract it should branch on. It is not one. Nothing should gate
behavior on its value; the only correct uses are display and diff-labeling.

**Name.** `revision_number`, not `version` (PM decision, 20260731). `version`
invites exactly the semver misreading above; `revision` alone still leaves room
for a reader to treat the value as a label rather than a count. The `_number`
suffix closes that — it cannot be read as anything but an integer counter, so
nothing downstream can creatively reinterpret it as a draft state, a stage
name, or a release tag.

**Who writes it.** Squadron, not the dispatched agent. Squadron never authors
slice designs or task files — `DispatchAction` has no file-write code at all,
it resolves a prompt and returns the response
([actions/dispatch.py:200-205](src/squadron/pipeline/actions/dispatch.py#L200-L205)).
Instructing the agent to stamp its own revision number was rejected: it is an LLM
instruction, so it will be missed, and a missed stamp is indistinguishable from
a pre-field artifact. Squadron post-processing is deterministic.

**Where it hooks.** Immediately after the dispatch artifact post-condition
passes ([executor.py:1064-1082](src/squadron/pipeline/executor.py#L1064-L1082)),
gated on `expected_kind is not None` **and** `ctx.iteration >= 1` — i.e.
a phase step with a known `ArtifactKind`, executing inside a loop. Paths come
from the existing `_expected_artifact_paths()`.

**Failure mode.** If the file cannot be parsed or rewritten, log at WARNING and
continue — a failed *evidence* stamp must not fail a converging loop, and
raising here would abort a run over a cosmetic write. This is explicit and
observable, not a silent fallback; a test asserts the WARNING.

**New module — `src/squadron/documents/frontmatter.py`.** No generic
frontmatter read/modify/write utility exists today. `read_review_frontmatter`
([metrology/identity.py:162-196](src/squadron/metrology/identity.py#L162-L196))
is lenient and correct but scoped to reviews, and its docstring asserts it is
the only reader of a persisted review. The new module provides:

- `read_frontmatter(path) -> dict[str, object] | None` — BOM- and
  blank-line-tolerant `---` split, `yaml.safe_load`, `None` when there is no
  block or it is not a mapping.
- `update_frontmatter(path, fields) -> None` — read/modify/write preserving the
  body **byte-for-byte** and existing key order; new keys appended to the end of
  the block.

To avoid two lenient parsers, `read_review_frontmatter` delegates its parse
step to `read_frontmatter` and keeps its own review-specific validation and
`MetrologyTargetError` behavior. Its six metrology consumers are unaffected.

**Review files.** Review files are overwritten per run under the same name
(`{index}-review.{type}.{slice}.md`,
[persistence.py:238](src/squadron/review/persistence.py#L238)), so they lose
round history exactly as the artifact does. `format_review_markdown`
([persistence.py:130-165](src/squadron/review/persistence.py#L130-L165)) gains
an optional `revision_number` that is emitted only when supplied;
`pipeline/actions/review.py` supplies `context.iteration` **when it is `>= 1`**,
and supplies nothing when it is `0`.

**Two paths produce no `revision_number:` key, both deliberately.** A review
action running outside a loop has `iteration == 0`, and a CLI-invoked
`sq review` never goes through the action at all. Neither emits the key —
not `0`, not `1`. This is not a parity gap between CLI / slash / MCP surfaces
(all three behave identically); it is the absence of a concept outside a loop,
and it is exactly consistent with the absent-means-never-stamped rule below.

### Part C — the round contract

**Clean regeneration.** Each iteration regenerates the artifact from the phase
prompt. `revision_number:` is the only thing squadron carries across a round. Content
does not accumulate, and no round-specific scaffolding is injected into the
document. Round-over-round history lives in git (Part A), not inside the file.

Rationale: the artifact is a contract other tools read, and simplest-that-works
is the right default for a contract. Accumulating content would also make the
document a second, weaker history mechanism competing with the one Part A adds.

**Absent `revision_number:` means "never stamped by squadron"** — explicitly *not*
"round 1." Readers must not default it. The first stamp writes `1`, meaning
"first squadron-tracked revision," which makes no claim about what preceded it.
This is the migration answer for every artifact written before this slice.

**Cross-repo seam.** `project-documents/ai-project-guide` is a git submodule
(`ecorkran/ai-project-guide`); its `file-naming-conventions.md` is the canonical
frontmatter schema that Context Forge also reads. Registering `revision_number:` there
is a cross-tool contract change and is **out of scope for this slice** by PM
decision — squadron-side first, guide follow-up second. Until that lands,
`revision_number:` is a key not present in the canonical schema. This slice changes no
CF behavior; whether CF's own frontmatter consumers tolerate unregistered keys
is the open compatibility question.

Filed as [ai-project-guide issue #14](https://github.com/ecorkran/ai-project-guide/issues/14),
which carries the proposed schema entry, the naming rationale, and the
unknown-key question. Squadron follows whatever name that issue settles on; if
it lands as something other than `revision_number`, this slice's field is
renamed before Phase 6 rather than migrated after.

## Implementation Details

### `loop:` config surface (additions)

```yaml
- loop:
    max: 3
    until: review.pass
    on_exhaust: checkpoint
    commit_each_iteration: true    # new; optional; default false
    steps:
      - dispatch:
          model: "{model}"
      - review:
          template: slice
          model: "{review-model}"
```

Validation rules for `commit_each_iteration`:

1. Optional. If present, must be a `bool` (reject non-bool with a field error,
   matching the existing `max` / `strategy` validators).
2. If `true` and any inner step expands to a `commit` action → `ValidationError`
   naming the offending step and stating that phase steps already commit each
   iteration.

### Frontmatter helper contract

```python
def read_frontmatter(path: Path) -> dict[str, object] | None: ...
def update_frontmatter(path: Path, fields: dict[str, object]) -> None: ...
```

`update_frontmatter` must round-trip a file whose frontmatter it does not
change without altering a byte of the body. A test asserts this against a real
slice design document from `project-documents/user/slices/`, not a synthetic
fixture — per the project rule that a parser's test fixture must be the format
it consumes in production.

### `--dry-run` surface

910 Part C added loop expansion to `--dry-run`
([cli/commands/run.py](src/squadron/cli/commands/run.py)). This slice adds one
line to that block: `commit_each_iteration` when set, alongside `max`, `until`,
and `on_exhaust`.

### Documentation

`docs/PIPELINES.md` currently carries a section titled "Constraint: no
per-iteration commit" stating that a loop body cannot commit. That becomes
false. Replace it with the `commit_each_iteration` option, the phase-body
double-commit rule, and the `revision_number:` contract from Part C.

## Integration Points

### Provides to Other Slices

- **Slice 912 (Part D).** Per-iteration commits give a "were the prior findings
  addressed?" check something to diff (`git diff HEAD~1 HEAD -- <artifact>`),
  and `revision_number:` gives it a stable way to name the round it is judging. Both are
  prerequisites; 912 designs the review semantics on top of them.
- **`documents/frontmatter.py`** becomes the shared read/update primitive for
  any future consumer that needs to touch a document header.

### Consumes from Other Slices

- 910 Part A's `running_prior` threading — unchanged, but it is the reason a
  round-over-round diff is expected to be non-empty.
- 909 Part A's artifact post-condition — Part B stamps only when it passes. If
  CF cannot resolve the artifact path, the post-condition already fails closed
  with a WARNING and no stamp is attempted.

## Success Criteria

### Functional Requirements

- A `loop:` with `commit_each_iteration: true` and a dispatch-shaped body
  produces one commit per iteration, each message carrying its iteration number.
- A phase-shaped loop body's existing commits carry iteration numbers, with no
  config change required.
- `commit_each_iteration: true` on a body that already commits is rejected at
  validation time with a message naming the offending step.
- A round that changes nothing logs a WARNING identifying pipeline, step, and
  iteration.
- The artifact a loop iteration produces carries `revision_number: {n}`, incrementing
  round over round; an artifact with no prior `revision_number:` receives `1`.
- The review file squadron writes inside a loop carries the same field; one
  written by `sq review` from the CLI carries no `revision_number:` key.
- A frontmatter update leaves the document body byte-identical.

### Technical Requirements

- `ruff format --check .`, `ruff check .`, and full-project strict `pyright`
  clean.
- New tests for: iteration-qualified messages, the `commit_each_iteration`
  validation rejection, the no-change WARNING, the failed-stamp WARNING,
  `revision_number` increment from absent / present / non-int prior values, and body
  byte-preservation against a real project document.
- Each new failure path has a test asserting its observable signal, per
  `.claude/rules/review-code.md`.
- `docs/PIPELINES.md` no longer states that per-iteration commits are impossible.

### Verification Walkthrough

*Corrected against real output during Phase 6 (implementation branch
`911-slice.loop-iteration-versioning-and-review-evidence`).*

**1. The new option is visible before spending model calls.** `p45b.yaml`
itself is phase-bodied and does not set `commit_each_iteration` (it must not —
see step 2), so it does not render the new line. Confirmed instead with a
throwaway loop that does set it:

```bash
sq run --dry-run <fixture>.yaml
```

Reproduced output:

```
Steps:
  loop-0 (loop)
    max: 2, until: review.pass, on_exhaust: skip, commit_each_iteration: true
    dispatch-0 (dispatch)
    review-1 (review)
```

`p45b.yaml` on its own still dry-runs unchanged
(`sq run --dry-run p45b 911` — verified against the real pipeline at
`~/.config/squadron/pipelines/p45b.yaml`), confirming the option is additive
and does not disturb an existing phase-bodied loop.

**2. Validation rejects the double-commit.** A throwaway pipeline whose loop
body is a phase step and which sets `commit_each_iteration: true`:

```bash
sq run --validate <fixture>.yaml
```

Reproduced output:

```
Validation errors for 'double-commit-fixture':
  commit_each_iteration: loop body already commits via design-0 (phase steps
commit each iteration automatically) — remove 'commit_each_iteration' from the
loop config
```

Matches the design: the offending step is named and the fix is stated. Fixture
deleted after the check.

**3. A dispatch-bodied loop now leaves history.** `commit_each_iteration: true`
on a `[dispatch, review]` body (`test-loop.yaml`'s shape), run from a standard
terminal (`sq run`'s SDK mode refuses to execute nested inside a Claude Code
session — this is an intentional recursion guard, not specific to this slice):

```bash
git log --oneline -5
```

Expect one commit per iteration, each message
`chore: loop-{step name} (iteration N)` — not identical subject lines.

**4. The artifact says which round it is.** Run a phase-bodied loop that takes
more than one round, then read the head of the design file CF reports for the
slice. Expect `revision_number:` in the frontmatter with a value matching the
number of rounds squadron stamped. Covered end-to-end by automated tests
(`tests/pipeline/test_executor.py::TestRevisionNumberStamping`, 7 cases
including absent → 1, existing int → n+1, existing non-int → 1) rather than a
separate live CF-backed run, since reproducing it live requires a full Context
Forge slice-plan/tasks setup beyond a throwaway fixture.

**5. Round-over-round diff — the thing #44 asked for.**

Attempted live in a disposable scratch repo with a dispatch-bodied
`commit_each_iteration: true` loop (`loop-smoke.yaml`). Mechanically this
confirmed the feature: each invocation of the pipeline produced one commit per
iteration with a distinguishable message (`chore: loop-{name} (iteration N)`),
and `git log --oneline -- <path>` / `git diff HEAD~1 HEAD -- <path>` against
the file the loop touched showed the expected non-empty round-over-round diff.
(Two commits both read "iteration 1" on first inspection — traced to two
separate invocations of `sq run loop-smoke` 28 seconds apart, confirmed via
their distinct `run_id`s in `~/.config/squadron/runs/`, not a defect: each
un-resumed run numbers its own iterations from 1.)

The specific fixture used had an unrelated flaw — its dispatch prompt asked
the model to write a throwaway `calc.py`, but the coding agent went off-task
and copied this repo's own `CLAUDE.md`/`.claude/` scaffolding into the scratch
project instead. That's a smoke-test-prompt problem, not a squadron defect;
tracked separately rather than re-run to convergence here (see project
DEVLOG). Round-over-round diffing itself — the mechanism, not this one
fixture's prompt — is otherwise covered by
`tests/pipeline/test_executor_loop_body.py` (per-iteration commit dispatch)
and `tests/pipeline/actions/test_commit.py` (message formatting), which assert
the same invariant without depending on a specific model's task-following.

Expect a non-empty diff between consecutive rounds. An empty diff, paired with
the Part A WARNING in the run log, is the honest report that the round did
nothing — which is the diagnostic this slice exists to make possible.

## Risk Assessment

### Technical Risks

- **`git add -A` scope.** `CommitAction` stages the whole tree when no `paths`
  are given ([commit.py:52](src/squadron/pipeline/actions/commit.py#L52)). A
  per-iteration commit therefore sweeps unrelated working-tree changes into the
  round's commit. This is not new — phase-emitted commits already behave this
  way — but a loop multiplies how often it happens.
- **Body-preserving frontmatter rewrite.** Any bug in `update_frontmatter`
  corrupts a document squadron did not author. Mitigated by the
  byte-preservation test against a real project document, and by the
  WARNING-and-continue failure mode rather than a partial write.

### Mitigation Strategies

- Keep the loop-appended commit's staging behavior **identical** to the
  phase-emitted one (`-A`) rather than inventing a second rule, and document in
  `docs/PIPELINES.md` that pipeline runs assume a clean working tree. Scoped
  staging is a candidate follow-up, not a change to make inconsistently in one
  of two commit paths.

## Implementation Notes

### Development Approach

Sequence: **A1 → B → A2/A3 → C.**

- **A1 first** (`ActionContext.iteration`) because both Part A's messages and
  Part B's review-file stamping depend on it, and it is the smallest change.
- **B second** — the frontmatter module and the stamping hook — because it is
  the only genuinely new code and the only part with a corruption risk worth
  isolating in its own commit.
- **A2/A3 third**: the loop option, its validation, and the no-change WARNING.
- **C last**: documentation, the `--dry-run` line, and recording the
  `ai-project-guide` schema follow-up as future work.

Each part is independently verifiable and independently committable, matching
910's structure.

### Special Considerations

- The verdict-counting walk in `LoopStepType._validate_verdict_count` skips
  inner steps that fail their own `validate()` before calling `expand()`
  ([steps/loop.py:186-190](src/squadron/pipeline/steps/loop.py#L186-L190)) —
  because `expand()` raises `KeyError` on an incomplete config. The new
  commit-detection walk must do the same, and should reuse that traversal rather
  than adding a second one.
- Effort: Part A 2/5, Part B 2/5, Part C 1/5. Overall 2/5 with Part D removed.
