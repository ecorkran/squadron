---
docType: tasks
slice: judge-enforcement-layer
project: squadron
lld: ../slices/301-slice.judge-enforcement-layer.md
dependencies:
  - 300 numeric-scoring-foundation (complete) — ReviewResult.score/.criteria/.provenance, ActionResult.score/.criteria/.provenance, lenient parser extraction, StepState.score hoist
projectState: "Slice 300 complete. ReviewResult/ActionResult carry optional score/criteria/provenance (all None until this slice). ReviewTemplate in src/squadron/review/templates/__init__.py has no judge-related field yet. ReviewAction._review() in src/squadron/pipeline/actions/review.py maps ReviewResult to ActionResult but never sets provenance and never derives a verdict from score. ReviewStepType.expand() in src/squadron/pipeline/steps/review.py builds the review action's param dict but has no judge: passthrough. CheckpointAction._TRIGGER_THRESHOLDS already fires ON_CONCERNS/ON_FAIL for UNKNOWN verdicts — verified in the LLD, no checkpoint change needed."
dateCreated: 20260704
dateUpdated: 20260704
status: not_started
---

## Context Summary

- **Working on:** the judge **use** layer — the second half of the two-layer split from `300-arch.eval-actions-llm-as-judge-scoring.md`. Slice 300 made the score/criteria/provenance fields exist and parse leniently. This slice enforces what's required at judge run-time: a score must be present and in range, the verdict is *derived from it* by configurable threshold (never a raw model opinion), and every failure mode maps to a named, logged, non-passing outcome.
- **Current state:** no template can be identified as a judge; no verdict is ever threshold-derived; `provenance` is reserved but never populated on any result.
- **Key assumptions / discipline (from the LLD):**
  - A template is a judge **iff** its YAML has a `judge:` block — no naming convention, no separate boolean flag (project rule: never use user-accessible labels as logical structure).
  - `enforce_judge()` must be a **pure function** (logger passed in, no global state) — ignores `result.verdict` entirely and derives a fresh verdict from `result.score` only.
  - `provenance` becomes non-`None` for **every** `ReviewAction` result from this slice forward — `"judge"` for judge templates, `"review"` for standard templates.
  - Conservative module-level defaults: `pass_floor=75.0`, `concerns_floor=50.0`. Threshold resolution order: step override → template default → module constant, merged **per-key**.
  - Every failure mode (score absent, score out of range, action exception) must produce `UNKNOWN` (or `success=False` with `verdict="UNKNOWN"`) and a `WARNING`+ log line, each asserted by a `caplog`-based test.
  - `JudgeThresholds` is a plain `@dataclass`, not Pydantic — internal to the action layer, never serialized.
  - All existing tests must keep passing unchanged (backward-compatibility gate).
- **Dependencies:** slice 300, complete. Nothing else consumed.
- **What this slice delivers:** `ReviewTemplate.is_judge`, the new `pipeline/actions/judge.py` module (`Provenance`, `JudgeThresholds`, `resolve_thresholds`, `enforce_judge`), enforcement wired into `ReviewAction._review()`, and step-level `judge:` override passthrough in `ReviewStepType.expand()`.
- **Next slice:** 302 (Design-Phase Judge Templates) — authors the first real judge YAML templates against this enforcement contract; no engine changes expected there.

---

## Tasks

### T1: Add `judge` field and `is_judge` property to `ReviewTemplate`

- [ ] **Add to `ReviewTemplate` in `src/squadron/review/templates/__init__.py`**
  - [ ] `judge: dict[str, object] | None = None` field (place with the other optional fields, e.g. near `diff_exclude_patterns`)
  - [ ] `is_judge` computed property returning `self.judge is not None`
- [ ] **Update `load_template`** to parse an optional `judge:` block from the YAML
  - [ ] Raw dict passthrough — `dict(data["judge"])` when present and a mapping, else `None`
  - [ ] No schema validation or key-presence checks at load time (the LLD: a template with `pass_floor: 80` must load regardless of whether 80 is a "good" threshold — validation is `resolve_thresholds`'s job, not the loader's)
- [ ] Success: a `ReviewTemplate` constructed with `judge={"pass_floor": 75, "concerns_floor": 50}` has `is_judge is True`; one constructed without `judge` has `is_judge is False`; `uv run pyright` passes

**Commit:** `feat: add judge field and is_judge property to ReviewTemplate`

---

### T2: Tests for `ReviewTemplate.is_judge` and YAML loading

- [ ] **Add tests in `tests/review/test_templates.py`** (extend existing)
  - [ ] `ReviewTemplate` built without `judge` kwarg → `is_judge is False`
  - [ ] `ReviewTemplate` built with `judge={"pass_floor": 75, "concerns_floor": 50}` → `is_judge is True`
  - [ ] `load_template()` on a fixture YAML containing a `judge:` block → resulting template has `is_judge is True` and `.judge` matches the block's raw values
  - [ ] `load_template()` on a fixture YAML with no `judge:` key → `is_judge is False`, `.judge is None`
  - [ ] Existing non-judge template fixtures still load unchanged (backward-compat regression guard)
- [ ] Success: `uv run pytest tests/review/test_templates.py` passes

**Commit:** `test: cover ReviewTemplate is_judge and judge YAML parsing`

---

### T3: Create `pipeline/actions/judge.py` — `Provenance` and `JudgeThresholds`

- [ ] **Create `src/squadron/pipeline/actions/judge.py`**
  - [ ] `Provenance` `StrEnum` with members `JUDGE = "judge"` and `REVIEW = "review"`
  - [ ] Module-level constants `_DEFAULT_PASS_FLOOR = 75.0` and `_DEFAULT_CONCERNS_FLOOR = 50.0` (single source of truth per the project's no-scattered-comparison-values rule)
  - [ ] `JudgeThresholds` `@dataclass` with `pass_floor: float` and `concerns_floor: float`
  - [ ] `JudgeThresholds.derive_verdict(score: float) -> str` method:
    - [ ] `score >= pass_floor` → `"PASS"`
    - [ ] `concerns_floor <= score < pass_floor` → `"CONCERNS"`
    - [ ] `score < concerns_floor` → `"FAIL"`
  - [ ] Return the literal `Verdict` string values (no new verdict strings — reuse the existing `PASS`/`CONCERNS`/`FAIL` from `squadron.review.models.Verdict`)
- [ ] Success: `JudgeThresholds(pass_floor=75.0, concerns_floor=50.0).derive_verdict(80.0) == "PASS"`; boundary values (`75.0` → `"PASS"`, `74.9` → `"CONCERNS"`, `50.0` → `"CONCERNS"`, `49.9` → `"FAIL"`) all correct; `uv run pyright` passes

**Commit:** `feat: add Provenance enum and JudgeThresholds to judge action module`

---

### T4: Tests for `JudgeThresholds.derive_verdict`

- [ ] **Create `tests/pipeline/actions/test_judge.py`**
  - [ ] Parametrized test covering all three bands plus both boundary values (`pass_floor` exactly, `concerns_floor` exactly, one tick below each)
  - [ ] Assert the returned value matches `squadron.review.models.Verdict` string values exactly (no drift between the two)
- [ ] Success: `uv run pytest tests/pipeline/actions/test_judge.py` passes

**Commit:** `test: cover JudgeThresholds.derive_verdict band boundaries`

---

### T5: Add `resolve_thresholds` to `judge.py`

- [ ] **Add `resolve_thresholds(template_judge: dict[str, object] | None, step_override: dict[str, object] | None) -> JudgeThresholds`** to `src/squadron/pipeline/actions/judge.py`
  - [ ] Merge per-key: for each of `pass_floor` / `concerns_floor`, resolution order is step override → template default → module constant
  - [ ] Both `template_judge` and `step_override` may be `None` (absent `judge:` block, absent step-level override) — resolve to full module defaults in that case
  - [ ] Coerce resolved values to `float` (YAML may parse them as `int`)
  - [ ] No range validation here (e.g. a template that sets `pass_floor: 200` resolves as-is; enforcement-time range checks are on the *score*, not on thresholds — out of scope)
- [ ] Success: `resolve_thresholds(None, None)` returns the module defaults; `resolve_thresholds({"concerns_floor": 40}, None)` returns `pass_floor` from the default and `concerns_floor=40.0`; `resolve_thresholds({"pass_floor": 70, "concerns_floor": 45}, {"pass_floor": 80})` returns `pass_floor=80.0, concerns_floor=45.0`; `uv run pyright` passes

**Commit:** `feat: add resolve_thresholds merge logic to judge action module`

---

### T6: Tests for `resolve_thresholds` merging

- [ ] **Add tests in `tests/pipeline/actions/test_judge.py`** (extend from T4)
  - [ ] All-defaults case (`None, None`)
  - [ ] Template partially overrides one key, other key falls to default
  - [ ] Step overrides one key, template supplies the other, module constant unused
  - [ ] Step override wins over template value for the same key
  - [ ] Int-valued YAML inputs (e.g. `{"pass_floor": 80}`) coerce to `float`
- [ ] Success: `uv run pytest tests/pipeline/actions/test_judge.py` passes

**Commit:** `test: cover resolve_thresholds per-key merge precedence`

---

### T7: Add `enforce_judge` to `judge.py`

- [ ] **Add `enforce_judge(result: ReviewResult, thresholds: JudgeThresholds, template_name: str, logger: logging.Logger) -> tuple[str, str]`** to `src/squadron/pipeline/actions/judge.py`
  - [ ] `result.score is None` → return `("UNKNOWN", Provenance.JUDGE)`; log at `WARNING` (include `template_name` in the message)
  - [ ] `result.score` outside `[0, 100]` (either direction) → return `("UNKNOWN", Provenance.JUDGE)`; log at `WARNING` (include `template_name` and the offending score)
  - [ ] Valid score in range → return `(thresholds.derive_verdict(result.score), Provenance.JUDGE)`; no log line for the success path
  - [ ] Pure function: no I/O, no module-level state mutation, logger passed as a parameter (never `logging.getLogger()` internally) — this is what makes it independently testable by slice 302/304 without action context
  - [ ] Ignore `result.verdict` entirely — never read it (the architectural commitment: verdict is always threshold-derived from score, never the model's own opinion)
- [ ] Success: score `None` → `("UNKNOWN", "judge")` + one `WARNING` record in `caplog`; score `150` and score `-3` both → `("UNKNOWN", "judge")` + `WARNING`; score `80.0` with default thresholds → `("PASS", "judge")` with no log record; `uv run pyright` passes

**Commit:** `feat: add enforce_judge to judge action module`

---

### T8: Tests for `enforce_judge` failure modes and success path

- [ ] **Add tests in `tests/pipeline/actions/test_judge.py`** (extend from T4/T6)
  - [ ] Score `None` → `UNKNOWN` + `WARNING` log asserted via `caplog`
  - [ ] Score below 0 (e.g. `-3.0`) → `UNKNOWN` + `WARNING` log
  - [ ] Score above 100 (e.g. `150.0`) → `UNKNOWN` + `WARNING` log
  - [ ] Valid score in each band (`PASS` / `CONCERNS` / `FAIL`) → correct verdict, `"judge"` provenance, **no** `WARNING` log emitted
  - [ ] `enforce_judge` never reads `result.verdict` — construct a `ReviewResult` with a *mismatched* `verdict` (e.g. `Verdict.FAIL` but `score=95.0`) and assert the returned verdict is `"PASS"` (score wins, confirming the ignore-parsed-verdict contract)
- [ ] Success: `uv run pytest tests/pipeline/actions/test_judge.py` passes; all failure-mode rows from the LLD's failure-mode table (score absent, score out of range) are covered

**Commit:** `test: cover enforce_judge failure modes and score-wins-over-verdict contract`

---

### T9: Pass `judge:` step override through `ReviewStepType.expand()`

- [ ] **Update `expand()` in `src/squadron/pipeline/steps/review.py`**
  - [ ] When `"judge"` is present in `config.config`, add it to `review_dict` (same pattern as the existing `"slice"` passthrough at line 64)
  - [ ] No new step-type keyword or validator — `judge:` is treated as optional passthrough, matching how `slice` and `rules_content` are handled today
  - [ ] Do not alter `validate()` — the LLD does not require step-level validation of the `judge:` dict's contents (that validation-free posture is enforcement's job at `resolve_thresholds`)
- [ ] Success: `expand()` on a `StepConfig` with `config={"template": "t", "judge": {"pass_floor": 80}}` produces a review action dict containing `"judge": {"pass_floor": 80}`; `expand()` on a config without `judge` produces no `"judge"` key; `uv run pyright` passes

**Commit:** `feat: pass judge step override through ReviewStepType.expand`

---

### T10: Tests for `judge:` passthrough in `expand()`

- [ ] **Add tests in `tests/pipeline/steps/test_review.py`** (extend existing)
  - [ ] `expand()` with `judge:` in step config → override dict appears verbatim in the review action's param dict
  - [ ] `expand()` without `judge:` → no `judge` key in the review action's param dict (existing behavior unchanged)
  - [ ] Existing `expand()` tests (template, model, slice, checkpoint) still pass unchanged
- [ ] Success: `uv run pytest tests/pipeline/steps/test_review.py` passes

**Commit:** `test: cover judge step override passthrough in ReviewStepType.expand`

---

### T11: Wire enforcement into `ReviewAction._review()`

- [ ] **Update `_review()` in `src/squadron/pipeline/actions/review.py`**, after `run_review_with_profile(...)` returns `result` and before the final `return ActionResult(...)`
  - [ ] If `template.is_judge`: call `resolve_thresholds(template.judge, context.params.get("judge"))`, then `enforce_judge(result, thresholds, template_name, _logger)` to get `(verdict, provenance)`; use these — not `result.verdict.value` — for the returned `ActionResult.verdict` / `.provenance`
  - [ ] If not `template.is_judge`: `ActionResult.provenance = Provenance.REVIEW`; `.verdict` stays `result.verdict.value` as today (unchanged)
  - [ ] Update the module-level import list to bring in `enforce_judge`, `resolve_thresholds`, `Provenance` from `squadron.pipeline.actions.judge`
  - [ ] Remove the now-stale comment at the current `score=result.score, criteria=result.criteria` lines that says provenance is "reserved for slice 301" (this slice populates it)
- [ ] **Update `execute()`'s exception handlers** so that when `template.is_judge` is `True` (need to check this before or during exception handling — resolve template name from `context.params` inside the `except` block, or restructure so template lookup happens before the try/except boundary that can raise) and an exception occurs after template load, the returned `ActionResult` has `verdict="UNKNOWN"` and `provenance=Provenance.JUDGE`, logged at `WARNING`/`ERROR` as today's `_logger.exception` / `_logger.warning` already do
  - [ ] If template lookup itself fails (template not found) before `is_judge` can be checked, the existing `KeyError` path stands — no judge-specific handling needed since there's no template to check
- [ ] Success: mock `run_review_with_profile` to return a `ReviewResult` with `score=None` for a judge template → `ActionResult.verdict == "UNKNOWN"`, `.provenance == "judge"`; mock a valid-score result → threshold-derived verdict, `.provenance == "judge"`; a standard template's result → `.provenance == "review"`, `.verdict` unchanged from `result.verdict.value`; `uv run pyright` passes

**Commit:** `feat: wire judge enforcement into ReviewAction`

---

### T12: Tests for `ReviewAction` judge enforcement integration

- [ ] **Add tests in `tests/pipeline/actions/test_review_action.py`** (extend existing)
  - [ ] Mock judge template (`is_judge=True`, `judge={"pass_floor": 75, "concerns_floor": 50}`) + mocked `run_review_with_profile` returning a scored `ReviewResult` → `ActionResult.verdict` is the threshold-derived value (not `result.verdict.value`), `.provenance == "judge"`
  - [ ] Mock judge template + mocked result with `score=None` → `ActionResult.verdict == "UNKNOWN"`, `.provenance == "judge"`
  - [ ] Mock standard (non-judge) template + mocked result → `ActionResult.provenance == "review"`, `.verdict == result.verdict.value` (unchanged from pre-301 behavior)
  - [ ] Step-level `judge:` override in `context.params` overrides the template's own `judge:` defaults (integration of T9's passthrough with T11's enforcement call)
  - [ ] `run_review_with_profile` raises for a judge template (patch it to raise, e.g. simulate a provider error) → returned `ActionResult(success=False, verdict="UNKNOWN", provenance="judge")`, and a `WARNING`/`ERROR` log line is present via `caplog`
- [ ] Success: `uv run pytest tests/pipeline/actions/test_review_action.py` passes; all existing tests in this file still pass unchanged

**Commit:** `test: cover judge enforcement integration in ReviewAction`

---

### T13: Full validation pass

- [ ] **Run the full suite and static analysis**
  - [ ] `uv run pytest` — entire suite green (existing tests unchanged + all new tests pass)
  - [ ] `uv run pyright` — 0 errors
  - [ ] `uv run ruff check && uv run ruff format --check` — clean
- [ ] **Run the LLD Verification Walkthrough commands 1–5** (the non-interactive ones) from `301-slice.judge-enforcement-layer.md` and confirm the printed `PASS:` lines
- [ ] **Confirm the no-silent-pass guarantee still holds:** verify `CheckpointAction._TRIGGER_THRESHOLDS` includes `UNKNOWN` in both `ON_CONCERNS` and `ON_FAIL` sets (read-only check — no checkpoint code change expected per the LLD)
- [ ] **Confirm no naming-convention dispatch leaked in:** grep the diff for any `template_name.startswith("judge.")`-style check — `is_judge` must be the only signal used to identify a judge template
- [ ] Success: full suite + static analysis clean; walkthrough commands 1–5 all print their `PASS:` line; checkpoint threshold check confirmed; no naming-convention dispatch found

**Commit:** `chore: validate judge enforcement layer slice`

---

## Coverage Check (against LLD)

| LLD change | Task(s) |
|------------|---------|
| `ReviewTemplate.judge` field + `is_judge` property + YAML loader | T1, T2 |
| `Provenance` StrEnum + `JudgeThresholds` dataclass + `derive_verdict` | T3, T4 |
| `resolve_thresholds` per-key merge (template default → step override) | T5, T6 |
| `enforce_judge` — all failure modes (score None, out-of-range) + valid-score path | T7, T8 |
| `ReviewStepType.expand()` — `judge:` step override passthrough | T9, T10 |
| `ReviewAction._review()` — enforcement wiring, provenance always set | T11, T12 |
| Judge action exception → `UNKNOWN` verdict + `WARNING`/`ERROR` log | T11, T12 |
| No verdict/thresholding leak outside enforcement; no naming-convention dispatch | T13 |
| Backward-compat + static-analysis gate | T2, T6, T8, T10, T12, T13 |
