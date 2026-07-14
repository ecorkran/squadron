---
docType: tasks
slice: judge-gated-cycle-conventions
project: squadron
lld: ../slices/303-slice.judge-gated-cycle-conventions.md
dependencies:
  - 300 numeric-scoring-foundation (complete) — score field, criteria parser
  - 301 judge-enforcement-layer (complete) — enforce_judge(), resolve_thresholds(), step-level judge: override
  - 302 design-phase-judge-templates (complete) — judge.slice-vs-arch / judge.tasks-vs-slice templates
projectState: "Slices 300–302 complete. Both judge templates verified live (judge.tasks-vs-slice scored 91, judge.slice-vs-arch scored 86). test-loop.yaml already ships the dispatch-then-review loop-body shape with a standard review template. No judge-gated pipeline exists; docs/PIPELINES.md has no loop step-type documentation. Since the 303 design was written, commit 4564471 (issue #18) made missing input/against files a hard error in ReviewAction._review — this affects how the control-flow tests must be set up (see Context Summary)."
dateCreated: 20260714
dateUpdated: 20260714
status: not_started
---

## Context Summary

- **Working on:** the judge-gated-cycle convention — review→fix→re-review as an
  unattended bounded `loop`, gated by a slice-302 judge's score-derived verdict.
  Deliverables: a worked built-in reference pipeline (`judge-cycle.yaml`),
  structural + control-flow tests, and authoring documentation. **Zero engine
  code** — no new step type, action, selector, or executor branch (design
  Success Criterion #6).
- **Current state:** all machinery exists and was verified during design:
  `loop` (`max` / `until` / `on_exhaust`), `LoopCondition.REVIEW_PASS`,
  `ExhaustBehavior.CHECKPOINT` → `PAUSED`, the judge templates, and the
  step-level `judge:` threshold override. `test-loop.yaml` proves the body
  shape; the delta to a judge cycle is data only (template name +
  `on_exhaust: checkpoint`).
- **Key discipline (from the LLD):**
  - Body is **fix-first**: `loop [dispatch, review]` with NO pre-loop judge.
    The executor's multi-step loop is post-test with per-iteration result reset
    (`_execute_loop_body`, `executor.py:1109`) — a pre-loop judge cannot
    short-circuit iteration 1. Do not write YAML or prose implying it can.
  - Advisory-only mode is `judge: {pass_floor: 101}` via the existing
    step-level override — never a new `advisory:` flag or field.
    `resolve_thresholds` does not clamp threshold values; `pass_floor > 100`
    is a *sanctioned* value and the docs must say so explicitly.
  - `commit` is an action, NOT a registered step type — it cannot appear as a
    bare loop-body step. The body is `[fix, judge]` only; the docs state the
    per-iteration-commit limitation as a constraint.
  - The bound (`max`) is always explicit; no unbounded pattern is documented
    anywhere.
  - `each` fan-out may only be documented against `cf.unfinished_slices` (the
    sole registered source).
- **Discovered during Phase 5 (affects tasks below):**
  - `docs/PIPELINES.md` (the pipeline authoring guide) has **no `### loop`
    entry** in its Step Type Catalog, and no bare-`dispatch` step entry — a
    user cannot follow the convention section without them. T6 adds them.
  - Commit `4564471` (issue #18, post-design) makes a missing `input`/`against`
    file a **hard error** in `ReviewAction._review` before any model call. The
    control-flow tests (T3–T5) therefore cannot rely on mocking
    `run_review_with_profile` alone — they must also provide real temp
    input/against files or patch the slice-input resolution.
- **Mocking seam for tests (verified):** patch `run_review_with_profile` (and
  the persistence helpers) in `squadron.pipeline.actions.review` — the pattern
  `tests/pipeline/actions/test_review_action.py` already uses — while keeping
  `resolve_thresholds` / `enforce_judge` and the loop evaluation REAL. The
  tests prove control flow (score → derived verdict → `until` / exhaust), not
  model behavior.
- **What this slice delivers:** `judge-cycle.yaml`, its structural test, three
  deterministic control-flow tests (auto-advance, escalate-at-max,
  advisory-always-escalates), the authoring-guide section, and one live
  unattended validation run.
- **Next slice:** 304 (gate composition — judge verdict + review verdict at
  one gate; explicitly out of scope here).

---

## Tasks

### T0: Branch setup

**Effort: 1**

- [x] **Create the slice branch per project git rules**
  - [x] `cd` to project root; confirm with `pwd`
  - [x] Read `cf config get git.integration_branch`; call its value (or `main`
    if empty) the target
  - [x] Create `303-slice.judge-gated-cycle-conventions` from the target if it
    does not exist; otherwise switch to it
- [x] Success: `git branch --show-current` prints
  `303-slice.judge-gated-cycle-conventions`

---

### T1: Author `judge-cycle.yaml`

**Effort: 2**

- [x] **Create `src/squadron/data/pipelines/judge-cycle.yaml`**, modeled on
  `src/squadron/data/pipelines/test-loop.yaml` (the proven
  dispatch-then-review body shape)
  - [x] `name: judge-cycle`; description states it is the judge-gated
    review→fix→re-review reference pipeline
  - [x] `params:` block with `slice: required` (quote placeholders as
    `"{slice}"` per the authoring guide's placeholder rule)
  - [x] A single `loop` step, fix-first body, no pre-loop judge:
    - [x] `max: 3`
    - [x] `until: review.pass`
    - [x] `on_exhaust: checkpoint` (not `fail` — the run is *undecided*, not
      wrong; escalation to a human is the point)
    - [x] Body step 1 — `dispatch:` fix leg. Prompt does double duty per the
      fix-first shape: address prior judge findings if any exist, otherwise
      perform an initial improvement pass on the artifact
    - [x] Body step 2 — `review:` with `template: judge.slice-vs-arch` and
      `slice: "{slice}"` so `input`/`against` auto-resolve via
      `TEMPLATE_INPUTS` (the same path slice 302's live runs exercised)
  - [x] No `judge:` override in the shipped file — the reference pipeline is
    the auto-advance mode; advisory-only is shown in docs (T6) and pinned by
    test (T5)
- [x] Success: `uv run sq run judge-cycle --validate` reports the pipeline
  valid with no unknown step types

**Commit:** `feat: add judge-cycle reference pipeline` (277620c)

---

### T2: Structural test for `judge-cycle.yaml`

**Effort: 1**

- [x] **Extend `tests/pipeline/test_loader_integration.py`**
  - [x] Add `"judge-cycle"` to `_BUILTIN_NAMES` (covers load + validate via
    the existing parametrized tests)
  - [x] Add a structure test in `TestBuiltInPipelineStructure` asserting the
    judge-gated shape: exactly one `loop` step whose config has `max >= 1`,
    `until == "review.pass"`, `on_exhaust == "checkpoint"`, and a body of
    `dispatch` followed by `review` where the review's
    `template == "judge.slice-vs-arch"` (a `judge.`-prefixed slice-302
    template)
- [x] Success: `uv run pytest tests/pipeline/test_loader_integration.py`
  passes

**Commit:** `test: assert judge-cycle loads with the bounded judge-gated shape` (d013d8b)

---

### T3: Control-flow harness + auto-advance test

**Effort: 3**

- [x] **Create `tests/pipeline/test_judge_cycle.py`** with a shared harness
  that drives the REAL loaded pipeline through `execute_pipeline`
  - [x] Load the real definition via
    `load_pipeline("judge-cycle", project_dir=..., user_dir=...)` (nonexistent
    dirs, as `test_loader_integration.py` does) — the tests exercise the
    shipped artifact, not a hand-built copy
  - [x] Action registry: the REAL `ReviewAction` for `review`; a mocked
    dispatch action returning `success=True` (the fix leg's model call is not
    under test)
  - [x] Patch `run_review_with_profile` in `squadron.pipeline.actions.review`
    to return a `ReviewResult` with a **forced score** (follow the
    `_make_review_result` pattern in
    `tests/pipeline/actions/test_review_action.py`); patch
    `save_review_file` / `format_review_markdown` likewise
  - [x] Do NOT patch `resolve_thresholds`, `enforce_judge`, or anything in the
    loop/executor path — the derived verdict and `until` evaluation must be
    real
  - [x] Satisfy the missing-input hard-fail (commit `4564471`): provide real
    tmp-path `input`/`against` files for the review step's resolved slice
    inputs, or patch the slice-input resolution seam in
    `squadron.pipeline.actions.review` — whichever is smaller; the judge
    threshold path must remain real either way
- [x] **Auto-advance test** (`test_judge_cycle_auto_advance`)
  - [x] Forced score above `judge.slice-vs-arch`'s default `pass_floor` (82)
    — e.g. 90 → derived verdict PASS
  - [x] Assert the run COMPLETED (not PAUSED), the loop exited at iteration 1
    (auto-advance = exit after ONE `[fix, judge]` iteration, not zero), and
    the dispatch mock was called exactly once
- [x] Success: `uv run pytest tests/pipeline/test_judge_cycle.py -k
  auto_advance` passes

**Commit:** `test: judge-cycle auto-advances when the score clears the floor` (7bce968)

---

### T4: Escalate-at-max test

**Effort: 2**

- [x] **Add `test_judge_cycle_escalates`** to
  `tests/pipeline/test_judge_cycle.py` using the T3 harness
  - [x] Forced score below `concerns_floor` (60) — e.g. 40 → derived verdict
    FAIL on every iteration
  - [x] Assert the loop runs exactly `max` (3) iterations (dispatch mock
    called 3 times), then exhausts: the loop's `StepResult` has
    `status=PAUSED` — never a silent pass, never unbounded
  - [x] Assert observability (design Success Criterion #4): the exhausted
    step's `action_results` carry the last judge result (score and findings
    reachable by the human)
- [x] Success: `uv run pytest tests/pipeline/test_judge_cycle.py -k
  escalates` passes

**Commit:** `test: judge-cycle exhausts to PAUSED at max when the floor is never cleared` (35af4f0)

---

### T5: Advisory-always-escalates test

**Effort: 2**

- [ ] **Add `test_judge_cycle_advisory_always_escalates`** to
  `tests/pipeline/test_judge_cycle.py`
  - [ ] Load the real `judge-cycle` definition, then inject
    `judge: {pass_floor: 101}` into the loop-body review step's config — the
    exact step-level override a user would write; no other change
  - [ ] Forced raw score 95 (well above the default floor) → derived verdict
    still non-PASS because `score < 101`
  - [ ] Assert the loop always exhausts to `PAUSED` — proving the gate is the
    threshold, not the model, and pinning unclamped thresholds
    (`pass_floor > 100` sanctioned) as a regression guard per the LLD's
    advisory-only note
- [ ] Success: `uv run pytest tests/pipeline/test_judge_cycle.py -k
  advisory` passes; full suite, `uv run pyright`, and `uv run ruff check`
  remain clean

**Commit:** `test: advisory pass_floor override forces judge-cycle escalation`

---

### T6: Authoring documentation in `docs/PIPELINES.md`

**Effort: 3**

- [ ] **Add a `### loop` entry to the Step Type Catalog** (currently absent —
  discovered this phase)
  - [ ] Fields: `max` (required positive int — the bound), `until`
    (`review.pass`, `review.concerns_or_better`, `action.success`),
    `on_exhaust` (`fail`, `checkpoint`, `skip`), `steps` (body of registered
    step types)
  - [ ] Note the post-test semantics: `until` is evaluated only after an
    iteration's body completes, against that iteration's own results
  - [ ] Add a minimal bare-`dispatch` step entry if none exists (verify at
    impl time) — the convention body uses it
- [ ] **Add a "Judge-Gated Cycles" section** covering, per the LLD:
  - [ ] The convention: body `[fix, judge]`, `until: review.pass`,
    `on_exhaust: checkpoint`, with the element-to-role table from the design
  - [ ] The two gating modes: auto-advance (default floors, strong ground
    truth) vs. advisory-only / always-escalate (weak ground truth)
  - [ ] Advisory-only expressed purely as `judge: {pass_floor: 101}` — state
    explicitly that an above-100 floor is a *sanctioned* value relying on
    thresholds staying unclamped, so a future 0–100 threshold clamp must
    preserve a "never passes" sentinel or this convention breaks
  - [ ] The bound: `max` is always explicit; document no unbounded pattern
  - [ ] Escalation observability: exhaustion produces a PAUSED run carrying
    the last judge's score and findings
  - [ ] First-iteration shape: fix-first recommended; a pre-loop judge is
    informational only and cannot short-circuit iteration 1 (post-test loop)
  - [ ] Stated constraint: `commit` is not a bare loop-body step —
    per-iteration commit is not expressible; commit after the loop via a
    phase step instead
  - [ ] `each` fan-out caveat: only against `cf.unfinished_slices`; do not
    imply other sources exist
  - [ ] `on_exhaust: fail` documented as the alternative only where an
    unclearable artifact should abort rather than wait for a human
- [ ] **Add `judge-cycle` to the Built-in Pipelines table** (name,
  description, key params: `slice`)
- [ ] Success: a reader can author their own judge-gated pipeline from the
  section alone; every convention above appears; no unbounded pattern is
  documented anywhere in the file

**Commit:** `docs: add loop step and judge-gated cycle conventions to authoring guide`

---

### T7: Live unattended validation run

**Effort: 2**

- [ ] **Run the reference pipeline against a real slice** (requires provider
  access; mirrors slice 302's live-run caveats)
  - [ ] `set -a && source .env && set +a` first; from inside a Claude Code
    session use `profile="openrouter"` with an explicit model
  - [ ] Confirm the exact invocation shape at run time (`sq run judge-cycle
    --validate`, then the run with the slice param as the CLI expects) —
    target a real slice with an existing design + arch pair, e.g. 302
  - [ ] Expected: the judge scores the design vs. its arch doc; the loop
    auto-advances when the score clears the floor, otherwise the fix leg
    revises and it re-judges up to `max`, then PAUSES with the score/findings
    visible in the run output
  - [ ] Treat the first runs' fix-prompt behavior as tuning data, not a
    one-shot final draft — prompt adjustments to the dispatch leg are
    in-scope data changes (commit as `fix:` if made)
- [ ] Success: one complete unattended run reaching either auto-advance or an
  observable PAUSED escalation, with the judge's score visible in the run
  output; the outcome is recorded in the DEVLOG entry (T8)

---

### T8: Full gate, slice close-out

**Effort: 1**

- [ ] **Full regression + static analysis from project root**
  - [ ] `uv run pytest` — all pass
  - [ ] `uv run pyright` — zero errors
  - [ ] `uv run ruff check` and `uv run ruff format` — clean (format
    immediately before committing)
- [ ] **Verify design success criteria** — walk the LLD's Success Criteria
  list (six functional, five technical, two integration) and confirm each is
  satisfied; anything unmet returns to the relevant task above
- [ ] **Close out**
  - [ ] Mark completed/dropped items `[x]` in this file (task-checker agent)
  - [ ] Update slice design status to complete; mark slice 303 complete in
    the slice plan (`100-slices.orchestration-v2.md`) if applicable
  - [ ] DEVLOG entry per `prompt.ai-project.system.md` Session State Summary,
    including the T7 live-run outcome
  - [ ] Merge `303-slice.judge-gated-cycle-conventions` into the target
    branch per project git rules

**Commit:** `docs: close out slice 303 judge-gated cycle conventions`
