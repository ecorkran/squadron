---
docType: tasks
slice: gate-composition
project: squadron
lld: user/slices/304-slice.gate-composition.md
dependencies: [302, 140]
projectState: >
  Slice 304 design complete and review-addressed (CONCERNS resolved: F001
  None-verdict → UNKNOWN normalization, F002 executor read-surface reframed as
  140-adjacent needing up-front sign-off). Integration slice for initiative
  300: reduce a judge verdict and a standard review verdict into one checkpoint
  gate via upstream reduction (option a). Slices 300/301/302/303 are complete.
  No branch yet — created at Phase 6 start per git rules.
dateCreated: 20260716
dateUpdated: 20260716
reviewsAddressed: [304-review.tasks.gate-composition]
status: not_started
---

## Context Summary

- Working on the **gate-composition** slice (304), the integration slice that
  closes initiative 300's gating story: how a **judge** result and a **standard
  review** result compose into one checkpoint gate. Parent:
  `300-slices.eval-actions-llm-as-judge-scoring.md`.
- **The decisive verified constraint:** the checkpoint is single-verdict-per-step
  because `prior_outputs` is keyed `{action_type}-{idx}` with `idx` resetting per
  step (`executor.py:880-883`), and a `review` step emits exactly one review
  action (`steps/review.py:69-76`) — so a judge step and a review step both write
  key `review-0` and **overwrite each other**. `_find_review_verdict`
  (`checkpoint.py:28-37`) then sees only the last. Two separately-stepped verdicts
  cannot be combined without changing the checkpoint (that would be option b, a
  140 change). **Option (a):** reduce the two verdicts to **one** *upstream*, in
  the same step as the checkpoint.
- **The deliverable** is a new `gate` action + `gate` step (both additive
  registrations), a pure most-severe-wins `reduce_verdicts`, a `composed`
  provenance value, one example pipeline, the escalation-to-140 boundary test,
  and an authoring-guide section. `_find_review_verdict` and the checkpoint are
  **not modified**.
- **Suggested order = dependency order:** reduction fn (T1–T2, no deps) →
  executor read surface (T3–T4, the 140-adjacent touch) → gate action (T5–T6) →
  gate step (T7–T8) → example pipeline + boundary docs (T9–T11) → authoring guide
  (T12) → commit (T13). Each impl task is followed immediately by its test.

### Grounding notes carried from the design (read before starting)

Verified against on-disk code during Phase 4; a junior AI should not re-derive
these:

- **Registries.** `register_action(action_type: str, action: Action)` and
  `register_step_type(step_type: str, impl: StepType)` — module-level, additive.
  `ActionType` / `StepTypeName` are `StrEnum`s (`actions/__init__.py:21`,
  `steps/__init__.py:24`); add `GATE = "gate"` to **each**.
- **Protocols.** `Action` needs `action_type` (property), `async execute(ctx)
  -> ActionResult`, `validate(config) -> list[ValidationError]`
  (`actions/protocol.py`). `StepType` needs `step_type` (property),
  `expand(config) -> list[tuple[str, dict]]`, `validate(config) ->
  list[ValidationError]` (`steps/protocol.py`).
- **Provenance / thresholds live in `actions/judge.py`.** `Provenance` is a
  `StrEnum` (`JUDGE`, `REVIEW`) — add `COMPOSED = "composed"`. `enforce_judge` /
  `resolve_thresholds` already exist (301).
- **`ActionResult`** (`models.py:28`) carries `verdict: str | None`, `score`,
  `criteria`, `provenance`, `metadata`, `findings`. The verdict enum values are
  `PASS | CONCERNS | FAIL | UNKNOWN` (strings; `checkpoint.py` compares against
  these string literals).
- **Where source results live.** `StepResult` (`executor.py:244`) has
  `step_name: str` and `action_results: list[ActionResult]`. The executor
  accumulates a `step_results: list[StepResult]` (`executor.py:712,860`) AND the
  lossy action-keyed `prior_outputs` dict. The gate resolves `judge_from` /
  `review_from` (step **names**) against a **step-keyed** view — which does NOT
  exist yet on `ActionContext` (it has only `prior_outputs`, `models.py:54`).
  Building that view is T3 (the F002 140-adjacent touch).
- **F001 handling (fail-closed).** A source `ActionResult` with `verdict=None`
  (non-review action, or a review that produced no verdict) is normalized to
  `UNKNOWN` **before** ranking — the gate does NOT skip `None` like
  `_find_review_verdict` does. Logged at WARNING+.
- **F002 handling (140 coordination).** The executor read-surface addition (T3)
  is 140-owned code; it must be a **pure additive read view** (new field on
  `ActionContext`, no change to `prior_outputs` semantics or the checkpoint) and
  requires up-front 140 sign-off. If it cannot stay pure, STOP and escalate to
  option (b) per the design's escalation boundary — do not force it.

---

## T1. Reduction core: severity table, `reduce_verdicts`, `Provenance.COMPOSED`

- [ ] Create `src/squadron/pipeline/actions/gate.py`. Define the severity
  ordering **once** as an ordered mapping/enum (most severe first):
  `UNKNOWN > FAIL > CONCERNS > PASS`. Do not scatter verdict-string comparisons —
  one table, referenced everywhere (project rule).
- [ ] Add `COMPOSED = "composed"` to the `Provenance` `StrEnum` in
  `actions/judge.py`.
- [ ] Implement a **pure** `reduce_verdicts(a: str | None, b: str | None) -> str`:
  - Normalize each argument: `None` → `"UNKNOWN"` **before** ranking (F001).
  - Return the more severe of the two per the severity table.
  - Ties (equal severity) return that shared value by construction — no
    tie-break, no score context needed.
  - The function must not read files, call providers, or mutate anything — pure
    over its inputs.
- [ ] **Success:** `reduce_verdicts` is importable and returns the correct
  most-severe result for any pair including `None` inputs; `Provenance.COMPOSED`
  exists; the severity order is defined in exactly one place.
- Effort: 2/5

## T2. Test the reduction core *(test-with T1)*

- [ ] Add `tests/pipeline/test_gate.py`. Unit-test `reduce_verdicts` across the
  **full 4×4 cross-product** of `{PASS, CONCERNS, FAIL, UNKNOWN}` × the same (all
  16 pairs), asserting most-severe-wins for each, **including the four diagonal
  ties** (`CONCERNS`+`CONCERNS` → `CONCERNS`, etc.).
- [ ] Add cases for `None` on each leg: `(None, PASS)` → `UNKNOWN`,
  `(PASS, None)` → `UNKNOWN`, `(None, None)` → `UNKNOWN` — pinning the fail-closed
  normalization and its divergence from skip-`None`.
- [ ] Parametrize (`@pytest.mark.parametrize`) rather than 19 separate functions.
- [ ] **Success:** all pairs pass; the `None`-normalization cases prove a
  verdict-less leg dominates rather than vanishing.
- Effort: 2/5

- [ ] **T2c. Commit the reduction core** *(after T2 green)*
  - [ ] `uv run ruff format`, run the reduction tests, then commit
    (`feat: add pure verdict reduction and composed provenance for gate`).
    This deliverable is self-contained (pure function + enum), independently
    bisectable.
  - Effort: 1/5

## T3. Executor step-keyed read surface (F002 — 140-adjacent, needs sign-off)

> **STOP-gate:** this task modifies 140-owned executor code. It must be a **pure
> additive read view** — a new optional field on `ActionContext` populated from
> the already-accumulated `step_results`, changing **no** existing behavior,
> touching **no** checkpoint code, and altering **no** `prior_outputs`
> semantics. Obtain 140 sign-off before landing. If a pure addition proves
> impossible (it forces a change to `_find_review_verdict`, the checkpoint's
> single-verdict contract, or existing `prior_outputs` semantics), **STOP** and
> escalate to option (b) per the design's escalation boundary — do not force it.

- [ ] In `models.py`, add an optional field to `ActionContext`:
  `step_outputs: dict[str, ActionResult] = field(default_factory=...)` — a
  **step-name → that step's review ActionResult** view. Keep `prior_outputs`
  exactly as-is (do not remove or repurpose it).
- [ ] In `executor.py`, where the per-step accumulation happens
  (~line 880-883, alongside the existing `prior_outputs[key] = ...` loop), also
  populate a `step_outputs` map keyed by `step_result.step_name`, choosing that
  step's verdict-bearing review `ActionResult` (the one the checkpoint would
  consider). Thread it into the `ActionContext` construction in
  `_execute_step_once` (~line 1027) exactly like `prior_outputs` is threaded.
- [ ] Decide and document (inline comment) which `ActionResult` a step maps to
  when it has several — the last verdict-bearing one, mirroring
  `_find_review_verdict`'s "most recent verdict" intent, scoped to that one step.
- [ ] **Success:** `ActionContext.step_outputs` exposes prior steps' results by
  step name; every existing executor test still passes unchanged (pure addition);
  no checkpoint or `_find_review_verdict` edit.
- Effort: 3/5

## T4. Test the read surface *(test-with T3)*

- [ ] In `tests/pipeline/` (executor tests), assert that after two named review
  steps run, an action in a later step sees **both** results via
  `context.step_outputs` keyed by step name — proving the lossy `prior_outputs`
  collision (`review-0` overwrite) is bypassed for the gate's needs.
- [ ] Add a regression assertion that `prior_outputs` behavior and
  `_find_review_verdict` are unchanged (the read surface is purely additive).
- [ ] **Success:** both source results are recoverable by step name; no existing
  executor/checkpoint test changes behavior.
- Effort: 2/5

- [ ] **T4c. Commit the executor read surface** *(after T4 green, with 140 sign-off)*
  - [ ] `uv run ruff format`, run the full executor suite, then commit
    (`feat: add step-keyed result view to ActionContext for gate composition`).
  - [ ] The commit body **must** record the 140 sign-off for the `prior_outputs`
    read-surface addition (per T3's STOP-gate). If sign-off is not yet obtained,
    do not commit — hold the branch and escalate.
  - Effort: 1/5

## T5. `gate` action

- [ ] In `gate.py`, implement `GateAction` satisfying the `Action` protocol:
  - `action_type` property returns `ActionType.GATE` (add `GATE = "gate"` to the
    `ActionType` enum).
  - `execute(ctx)`: read `ctx.params["judge_from"]` and
    `ctx.params["review_from"]` (step names); resolve each against
    `ctx.step_outputs` to its `ActionResult`; call `reduce_verdicts` on the two
    verdicts; return an `ActionResult` with `verdict=<reduced>`,
    `provenance=Provenance.COMPOSED`, and **both raw verdicts on `metadata`**
    (`judge_verdict`, `review_verdict`) for auditability. Pass through the legs'
    `score`/`criteria` on metadata for observability (do not reduce them).
  - `validate(config)`: require `judge_from` and `review_from` keys present.
- [ ] **Failure handling:** if a named source cannot be resolved at execute time,
  return `verdict="UNKNOWN"` with a WARNING+ log (never advance on an unresolved
  source). A `None` leg verdict is handled inside `reduce_verdicts` (T1).
- [ ] `register_action(ActionType.GATE, GateAction())` at module load.
- [ ] **Success:** the action reduces two named source results to one verdict with
  `composed` provenance and both raw verdicts preserved; an unresolved source
  yields a logged `UNKNOWN`.
- Effort: 3/5

## T6. Test the `gate` action *(test-with T5)*

- [ ] In `test_gate.py`, drive `GateAction.execute` with a hand-built
  `ActionContext` whose `step_outputs` holds two named results. Assert:
  - (judge=PASS, review=CONCERNS) → reduced `CONCERNS`, provenance `composed`,
    metadata carries both raw verdicts.
  - (judge=UNKNOWN, review=PASS) → reduced `UNKNOWN` (no-silent-pass under a
    broken judge leg).
  - a source leg with `verdict=None` → reduced `UNKNOWN` **and** a WARNING+ log
    (assert via `caplog`).
  - an unresolvable `judge_from` name → `UNKNOWN` + WARNING+ log.
- [ ] **Success:** all cases pass; the log assertions prove no silent path.
- Effort: 2/5

## T7. `gate` step type

- [ ] Create `src/squadron/pipeline/steps/gate.py`. Implement `GateStepType`
  satisfying `StepType`:
  - `step_type` returns `StepTypeName.GATE` (add `GATE = "gate"` to the
    `StepTypeName` enum).
  - `expand(config)` returns `[("gate", {judge_from, review_from, policy?})]`,
    and appends `("checkpoint", {"trigger": cfg["checkpoint"]})` when a
    `checkpoint:` key is present — mirroring `ReviewStepType.expand`
    (`steps/review.py:69-76`) so the gate's reduced verdict and the checkpoint
    land in the **same step**.
  - `validate(config)`: this is the `StepType.validate(config)` hook, which sees
    **only this step's own config** (per the protocol) — so it validates
    *presence and type* here: `judge_from` and `review_from` required and
    strings, `policy` (if present) is the known value (`most-severe`; only one
    policy exists — keep the key so the rule is named, do not build a
    single-entry registry). It **cannot** check that the named steps exist —
    that is a cross-step check and belongs in the loader (T7b), not here.
- [ ] `register_step_type(StepTypeName.GATE, GateStepType())`.
- [ ] **Success:** a `gate:` step loads and validates via the existing loader;
  it expands to `[gate]` or `[gate, checkpoint]`.
- Effort: 3/5

## T7b. Loader-level cross-step validation of `judge_from` / `review_from` (F005 — fail-fast)

> The design's failure-mode table promises a misspelled/missing source step name
> is caught at **load time**, failing fast — not deferred to the execute-time
> `UNKNOWN` fallback (T5). A step type's own `validate` cannot do this (it sees
> only its own config, T7); the check must live in the loader, which has all
> steps in scope.

- [ ] In `src/squadron/pipeline/loader.py`, in `validate_pipeline` (line 147; the
  `for step in definition.steps:` loop at line 184 already has all steps in
  scope), add a gate cross-reference check mirroring `_validate_review_template`
  (line 210): for a `gate` step, verify `judge_from` and `review_from` each name
  a step that **appears earlier** in `definition.steps` (a *prior* step — a gate
  cannot reference a step that runs after it). Emit a `ValidationError` naming the
  offending key and value when not found.
- [ ] Keep the rule DRY — a small helper `_validate_gate_references(step,
  prior_step_names, errors)` called from the loop, consistent with the existing
  `_validate_*` helpers.
- [ ] **Success:** a `gate` step naming a nonexistent or later step fails
  `validate_pipeline` with a clear error at load time; a gate naming two real
  prior steps validates clean.
- Effort: 2/5

## T8. Test the `gate` step and loader validation *(test-with T7, T7b)*

- [ ] In `test_gate.py` (or a loader-integration test), assert:
  - `expand` produces `[gate]` with no `checkpoint:`, and `[gate, checkpoint]`
    with one — checkpoint trigger threaded through.
  - step-type `validate` returns an error when `judge_from` or `review_from` is
    missing or non-string (own-config check).
  - **loader `validate_pipeline` (F005):** a `gate` naming a **nonexistent** step
    → validation error at load time; a `gate` naming a **later** step → error; a
    `gate` naming two real prior steps → clean. This proves the fail-fast promise,
    distinct from T5's execute-time `UNKNOWN` fallback.
  - A minimal valid `gate` pipeline loads/validates with no new-registration
    errors.
- [ ] **Success:** expansion, own-config validation, and loader cross-step
  validation all pass; the bad-reference cases fail at load, not execute.
- Effort: 2/5

- [ ] **T8c. Commit the gate action + step + validation** *(after T8 green)*
  - [ ] `uv run ruff format`, run the gate action/step/loader tests, then commit
    (`feat: add gate action and step type with loader cross-step validation`).
  - Effort: 1/5

## T9. Example composing pipeline

- [ ] Add `src/squadron/data/pipelines/compose-gate-example.yaml`: two `review`
  steps (a `judge.slice-vs-arch` judge leg and a `design` standard-review leg,
  both `slice: "{slice}"`), then a `gate` step naming both
  (`judge_from` / `review_from`) with `checkpoint: on-concerns`. Declare
  `model`/`review-model` as named top-level `params` referenced via placeholders,
  mirroring every other built-in pipeline (`P4.yaml`, `judge-cycle.yaml`) — do
  not rely on fallback model resolution.
- [ ] **Success:** `uv run sq run compose-gate-example --validate` reports valid.
- Effort: 2/5

## T10. Test drives-checkpoint end behavior *(test-with T9)*

- [ ] Add tests asserting the **reduced** verdict drives the checkpoint, not
  either raw leg:
  - gate over (judge=PASS, review=CONCERNS) → the same-step checkpoint **fires**
    on `on-concerns`.
  - gate over (judge=PASS, review=PASS) → checkpoint does **not** fire.
  - gate over (judge=UNKNOWN, review=PASS) → checkpoint **fires** (no silent pass).
  - **(F003) end-to-end `None` leg:** a source leg with `verdict=None` →
    normalized to `UNKNOWN` → reduced `UNKNOWN` → the same-step checkpoint
    **fires**. This exercises the fail-closed path *through the checkpoint*, not
    just at the action level (T6). Assert the WARNING+ log is emitted on this
    path too. This closes the gap between T6 (action-level normalization + log)
    and T10 (checkpoint firing for fixed verdicts) — neither alone proves a
    `None` input fires the gate end-to-end.
- [ ] **Success:** the gate's reduced verdict, not either source leg alone,
  determines whether the checkpoint pauses — including a `None`-leg source, which
  fires the checkpoint fail-closed.
- Effort: 2/5

## T11. Escalation-to-140 boundary test *(required by success criteria)*

- [ ] Add `test_boundary_requires_140`: assert that a policy requiring the
  checkpoint to see **both raw verdicts distinctly** (e.g. branch on *which* leg
  produced the severity) is **not** expressible via the single reduced gate —
  the gate result exposes one `verdict` plus both raw verdicts on `metadata`, but
  the checkpoint reads only the single reduced `verdict`. The test documents (in
  its docstring / an assertion on the recorded boundary) that this case is a
  **140 concern (Future Work 3)**, not silently absorbed here.
- [ ] **Success:** the test encodes escalation-boundary condition (3) — the slice
  recognizes its own edge rather than overreaching.
- Effort: 2/5

## T12. Authoring-guide section

- [ ] Add a "Composing a judge and a review at one gate" section to
  `docs/PIPELINES.md` (the pipeline authoring guide from slice 152; slice 303's
  `Judge-Gated Cycles` section lives there — add this as a sibling section and
  cross-link it). Cover: the
  composition shape (two review legs + a `gate` step), the most-severe-wins rule
  with `UNKNOWN` most-severe and the `None → UNKNOWN` fail-closed rule, the
  same-step checkpoint requirement, and — explicitly — when a case needs **140**
  instead (the boundary). Reference the fan-out/fan-in distinction (a gate is 2
  heterogeneous judgments; fan-in is N homogeneous samples) so authors don't
  reach for a gate where a fan-in reducer belongs.
- [ ] **Success:** a reader can author a composed gate from the section without
  reading the slice design, and knows the 140 boundary.
- Effort: 2/5

## T13. Final validation + example-pipeline & docs commit

> Commits are distributed across deliverables (F004): the reduction core (T2c),
> executor read surface (T4c), and gate action+step (T8c) are each already
> committed as validated. This task commits the remaining deliverable (example
> pipeline + boundary test + authoring guide) and runs the full-suite gate.

- [ ] `uv run ruff format`, then `uv run pytest && uv run pyright && uv run ruff
  check` — all green across the whole suite (all gate tests included; pyright
  strict, ruff clean).
- [ ] Confirm **non-composed** pipelines are byte-for-byte unchanged (existing
  checkpoint tests pass unmodified — success criterion #2).
- [ ] Commit the example pipeline, boundary test, and authoring-guide section
  from project root
  (`docs: add gate composition example pipeline and authoring guide (slice 304)`).
- [ ] Verify the branch history reads as four coherent commits (reduction,
  read-surface w/ 140 sign-off note, gate action+step, example+docs) — bisectable,
  not one monolithic delta.
- Effort: 1/5

---

## Verification (maps to slice success criteria)

- FR1 (judge+review → one gate via upstream reduction): T1, T5, T9, T10.
- FR2 (non-composed checkpoint unchanged): T3/T4 regression, T13.
- FR3 (option-b need escalated explicitly, not silent): T11.
- FR4 (composition tested incl. escalation boundary): T2, T6, T8, T10, T11.
- F001 slice-design (None-verdict fail-closed): T1, T2, T6, **and T10 end-to-end
  through the checkpoint** (tasks-review F003).
- F002 slice-design (executor touch is 140-adjacent, up-front sign-off):
  T3 STOP-gate, T4c sign-off note.

**Tasks-review concerns (kimi-k2.6, CONCERNS) addressed:**
- **F003** (no end-to-end `None`→checkpoint test): added the `None`-leg
  end-to-end case to T10 — normalizes to `UNKNOWN`, reduces to `UNKNOWN`, fires
  the checkpoint, WARNING+ logged; closes the T6↔T10 gap.
- **F004** (commits batched at the end): commits distributed across the four
  deliverables — T2c (reduction), T4c (read surface + sign-off note), T8c (gate
  action+step), T13 (example + docs); branch reads as four bisectable commits.
- **F005** (gate step omitted prior-step existence check): added T7b — loader
  `validate_pipeline` cross-checks `judge_from`/`review_from` name real *prior*
  steps (fail-fast at load), since a step type's own `validate` sees only its own
  config; T8 asserts the load-time failure, distinct from T5's execute-time
  `UNKNOWN`.

## Notes for the implementer

- **Do not modify `_find_review_verdict` or `checkpoint.py`.** The whole point of
  option (a) is the checkpoint stays single-verdict; the gate feeds it one. Any
  need to change either is the STOP signal to escalate to 140 (T3 gate).
- **Define the severity order once** (T1) — no scattered `if verdict == "FAIL"`
  chains across the action and step.
- **`UNKNOWN` is most severe, deliberately** — including a normalized `None`. A
  verdict-less or broken leg must dominate a passing leg (no-silent-pass NFR).
- **Preserve both raw verdicts on the gate result's `metadata`** — they make the
  reduction auditable and are exactly what the T11 boundary test inspects.
- **The gate reduces exactly two named sources.** Do not generalize to N-way
  composition or build a single-entry policy registry — no caller exists (project
  rule: resist complexity until necessary).
