---
docType: slice-design
slice: judge-enforcement-layer
project: squadron
parent: 300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [300]
interfaces: [302, 303, 304]
dateCreated: 20260617
dateUpdated: 20260705
status: complete
---

# Slice Design: Judge Enforcement Layer

## Overview

This slice implements the second half of the two-layer architecture split defined in
`300-arch.eval-actions-llm-as-judge-scoring.md`: the judge **use** layer. Slice 300
(Numeric Scoring Foundation) settled the result-model shape and made parsing lenient
and score-optional. Slice 301 enforces what is required at the point a judge actually
runs: a score must be present, it must be in range, the verdict is *derived from it*
by configurable threshold (never independently model-produced), and every failure mode
maps to a named, logged, non-passing outcome.

The result is an enforcement contract — validation, thresholding, provenance, and
observable failure handling — that every judge template (slice 302) plugs into without
any further engine changes.

## Value

**Architectural enablement.** After this slice, the system can gate on a judge result
confidently: the verdict on any judge `ActionResult` is always derived from the score
by threshold, never a raw model opinion, and any failure mode that cannot produce a
reliable score yields `UNKNOWN` — which the existing checkpoint machinery already
escalates. No judge template can be safely gated before this enforcement layer exists;
authoring templates (slice 302) without it would produce ungatable results.

## Technical Scope

### What changes

1. **`ReviewTemplate` (`review/templates/__init__.py`)** — add a `judge:
   dict[str, object] | None = None` field and an `is_judge: bool` computed property.
   Update `load_template` to parse the `judge:` block from the YAML when present
   (raw dict passthrough; no schema commitment beyond two optional numeric keys).

2. **`pipeline/actions/judge.py`** (new module) — three public exports:
   - `Provenance` StrEnum (`JUDGE = "judge"`, `REVIEW = "review"`)
   - `JudgeThresholds` dataclass (`pass_floor: float`, `concerns_floor: float`,
     `derive_verdict(score) -> str`)
   - `resolve_thresholds(template_judge, step_override) -> JudgeThresholds`
   - `enforce_judge(result, thresholds, template_name, logger) -> tuple[str, str]`
     — returns `(verdict, provenance)`

3. **`pipeline/actions/review.py`** — after executing the review:
   - If the template is a judge: call `enforce_judge()`, replace `verdict`/`provenance`
     on the returned `ActionResult`, and set `verdict="UNKNOWN"` on action exceptions.
   - For all results (judge or standard): populate `ActionResult.provenance`.

4. **`pipeline/steps/review.py`** — pass through the `judge:` override dict from step
   config to action params so `ReviewAction` can apply step-level threshold overrides.

### What does NOT change

- The `Verdict` enum or the verdict strings (`PASS | CONCERNS | FAIL | UNKNOWN`);
  `JudgeThresholds.derive_verdict()` returns these string values directly.
- The response parser (`parsers.py`) — enforcement is at the action, not the parser.
  The parser stays judging-unaware (the architectural two-layer commitment).
- The checkpoint machinery (`checkpoint.py`) — `UNKNOWN` already fires `ON_CONCERNS`
  and `ON_FAIL`; no change required.
- Any existing review template or pipeline that uses a standard (non-judge) template —
  behavior is unchanged except that `provenance` is now set to `"review"`.
- `ReviewResult.provenance` field type (`str | None`) — already reserved in 300.

### Explicitly out of scope

- Judge system-prompt templates — **slice 302**.
- The judge-gated cycle conventions — **slice 303**.
- Gate composition (judge + standard review into one verdict) — **slice 304**.
- Multi-sample judging (fan-out + median) — Future Work 1 in the slice plan.

## Dependencies

### Prerequisites
- **Slice 300 (complete):** `ReviewResult.score`, `.criteria`, `.provenance` reserved
  on both `ReviewResult` and `ActionResult`; the parser's optional score extraction;
  `StepState.score` hoist.

### Interfaces Required
- `ReviewResult.score: float | None` — the field whose presence/range enforcement
  derives the verdict.
- `ReviewResult.provenance: str | None` — the reserved field this slice populates.
- `ActionResult.verdict`, `.provenance` — the output fields enforcement writes.
- `run_review_with_profile` — already called by `ReviewAction._review()`; no change.
- `CheckpointAction._TRIGGER_THRESHOLDS` — verified that `UNKNOWN` is already in
  the `ON_CONCERNS` and `ON_FAIL` firing sets, so enforcement's `UNKNOWN` outcome
  gates correctly with no checkpoint changes.

## Architecture

### Component Structure

One new module; three existing modules updated:

| Module | Change |
|--------|--------|
| `review/templates/__init__.py` | `ReviewTemplate.judge` field + `is_judge` property; YAML loader parses `judge:` block |
| `pipeline/actions/judge.py` (new) | `Provenance`, `JudgeThresholds`, `resolve_thresholds`, `enforce_judge` |
| `pipeline/actions/review.py` | Apply enforcement post-review for judge templates; set `provenance` always |
| `pipeline/steps/review.py` | Pass through `judge:` override dict to action params |

### Data Flow

```
Pipeline YAML step (template: judge.*, judge: {pass_floor: N})
    │
    ▼
ReviewStepType.expand()
    │  passes judge: override into review action params
    │
    ▼
ReviewAction._review()
    │  loads template → template.is_judge = True
    │  calls resolve_thresholds(template.judge, params["judge"])
    │  → JudgeThresholds(pass_floor=N or default, concerns_floor=N or default)
    │
    ├── run_review_with_profile(template, inputs, ...) → ReviewResult
    │       result.score: float | None   (from parser, may be None)
    │       result.provenance: None      (reserved in 300, not yet set)
    │
    ├── enforce_judge(result, thresholds, template_name)
    │       ├── score is None? → ("UNKNOWN", "judge") + WARNING log
    │       ├── score < 0 or > 100? → ("UNKNOWN", "judge") + WARNING log
    │       └── valid score → (thresholds.derive_verdict(score), "judge")
    │               ≥ pass_floor → "PASS"
    │               ≥ concerns_floor → "CONCERNS"
    │               else → "FAIL"
    │
    ▼
ActionResult
    .verdict    = enforcement-derived string    (replaces parsed verdict)
    .score      = result.score                  (unchanged passthrough from 300)
    .provenance = "judge"                       (set by enforcement)
    ...

For standard (non-judge) review:
    .verdict    = parsed verdict                (unchanged)
    .score      = result.score | None           (from parser, unchanged)
    .provenance = "review"                      (set here for the first time)
```

### Threshold Resolution

Two levels, merged at execution time:

```
Template YAML default           Step-level override (pipeline YAML)
  judge:                          - name: judge-design
    pass_floor: 75                  type: review
    concerns_floor: 50              template: judge.slice-vs-arch
                                    judge:
                                      pass_floor: 80

resolve_thresholds(template.judge, params.get("judge"))
  → JudgeThresholds(pass_floor=80, concerns_floor=50)
  (step override wins per key; absent keys use template default; absent
   template value uses the module-level hardcoded conservative default)
```

Conservative defaults (constants in `judge.py`):
- `_DEFAULT_PASS_FLOOR = 75.0`
- `_DEFAULT_CONCERNS_FLOOR = 50.0`

Score bands from resolved thresholds:
- `score >= pass_floor` → `PASS`
- `concerns_floor <= score < pass_floor` → `CONCERNS`
- `score < concerns_floor` → `FAIL`

## Technical Decisions

### Judge template identification: `judge:` block (not naming convention, not flag)

A template is identified as a judge by the **presence of a `judge:` mapping block**
in its YAML, which also carries its default thresholds. Three alternatives considered:

1. **Naming convention** (`judge.*`): rejected — CLAUDE.md forbids using
   user-accessible labels as logical structure.
2. **Flat `is_judge: true` flag**: acceptable but adds a key without carrying the
   threshold defaults alongside it. Combining both into one `judge:` block is cleaner.
3. **`judge:` block** (chosen): presence implies the template is a judge; the block's
   `pass_floor`/`concerns_floor` keys supply the template defaults. Absence means the
   template is not a judge. One key, two purposes, no extra Boolean.

The `ReviewTemplate.judge` field is typed `dict[str, object] | None`: raw YAML
passthrough. `JudgeThresholds` lives in the action layer, not the template model,
keeping cross-layer type sharing to a minimum.

### Verdict derivation: one-directional from score only

The architecture commits that "the verdict is computed by thresholding the parsed
score… the model is not asked for an independent verdict." `enforce_judge()` ignores
`result.verdict` entirely and derives a fresh verdict from the score. This prevents
any model-emitted verdict from leaking into a judge result's `ActionResult.verdict`.
The judge system-prompt template (slice 302) reinforces this by instructing the model
not to emit a verdict — but enforcement is in the action so the constraint holds even
if a model ignores the instruction.

### Provenance set for all results, not just judges

Setting `provenance="review"` for every standard review result (not just judge) ensures
the self-describing guarantee is complete from this slice forward: any consumer (checkpoint,
gate composition in 304, calibration initiative 320) can read `provenance` without
needing to know which template ran. The field was reserved in 300 and is `None` today;
this slice makes it non-`None` universally for results that pass through `ReviewAction`.

### Failure modes: each enumerated with a WARNING+ log, each tested

The architecture's failure-mode enumeration rule requires every new I/O path to have
named, observable failure modes. For the enforcement path:

| Failure mode | Cause | Enforcement result | Log level |
|---|---|---|---|
| Score absent | Parser returned `None` (response had no parseable score) | `UNKNOWN` | WARNING |
| Score out of range | `score < 0` or `score > 100` | `UNKNOWN` | WARNING |
| Score in range | Score is valid | `PASS / CONCERNS / FAIL` from threshold | — |
| Judge action exception | Provider down, inputs missing, etc. (after template load) | `ActionResult(success=False, verdict="UNKNOWN")` | WARNING/ERROR |

The "unparseable response" and "missing/unreadable ground-truth file" cases from the
architecture's list collapse into the first two rows above: an unparseable response
means the parser returns `score=None` (row 1); missing inputs raise before the review
runs (row 4). No new enumeration cases are needed beyond what the two-layer split
already handles.

**The no-silent-pass guarantee**: `CheckpointAction._TRIGGER_THRESHOLDS` includes
`UNKNOWN` in both `ON_CONCERNS` and `ON_FAIL` sets. An `ActionResult` with
`verdict="UNKNOWN"` will fire any checkpoint whose trigger is `on-concerns` or
`on-fail`. `ActionResult(success=False)` with no verdict prevents the step from
completing, which also prevents silent advance. The guarantee holds with the existing
140 machinery.

### Conservative defaults

Default pass floor (75) and concerns floor (50) are chosen to be **above the
mid-range**, so a judge that produces a score must clear a meaningful bar to auto-pass.
The architecture explicitly states "defaults are deliberately conservative — when
uncertain, gate toward escalation, not auto-pass." A step or template can lower them
when in-repo ground truth is strong enough to trust a lower floor.

### JudgeThresholds: dataclass, not Pydantic model

`JudgeThresholds` is internal to the action layer — never serialized to a file
boundary. A plain `@dataclass` suffices. Pydantic enters the pipeline at file-I/O
boundaries (Pydantic project rule); threshold resolution from dicts is validation-free
(values are floats from YAML already parsed by `yaml.safe_load`, coerced at
resolution time, range-checked by the enforcement logic itself — not at model load).

### Step schema: `judge:` dict passthrough

`ReviewStepType.expand()` will pass the `judge:` key from the step config into the
review action's param dict. The action interprets it as the step-level override. No
new step-type keyword or validator is added — the `judge:` key is treated as an
optional passthrough, matching how other optional config (`slice`, `rules_content`)
is handled.

## Integration Points

### Provides to Other Slices

- **`ReviewTemplate.is_judge` property** — slice 302 authors mark templates as judges
  by adding a `judge:` block; the enforcement hook in `ReviewAction` then activates
  automatically with no engine change.
- **`JudgeThresholds`** and **`resolve_thresholds()`** — available for step 302 tests
  and slice 303 pipeline conventions.
- **`enforce_judge()`** — the stable contract; slice 302 can write tests that call it
  directly to verify verdict derivation without running a full review.
- **`Provenance` StrEnum** — available to 304 (gate composition) and 320 (calibration)
  to discriminate judge vs. review results.
- **`ActionResult.provenance` always populated** — from this slice forward, any
  `ActionResult` from the review action has a non-`None` provenance string.

### Consumes from Other Slices

- **Slice 300**: `ReviewResult.score`, `.provenance` (field to populate);
  `ActionResult.score`, `.provenance`; parser's lenient optional extraction.

## Success Criteria

### Functional Requirements

1. A `ReviewTemplate` with a `judge:` YAML block has `is_judge = True`; without it,
   `is_judge = False`.
2. `JudgeThresholds.derive_verdict(score)` returns `"PASS"` for `score >= pass_floor`,
   `"CONCERNS"` for `concerns_floor <= score < pass_floor`, `"FAIL"` for
   `score < concerns_floor`.
3. `resolve_thresholds` merges template defaults and step-level overrides per-key; each
   absent key falls back to the template default, then to the module-level constant.
4. `enforce_judge()` returns `("UNKNOWN", "judge")` when `score` is `None`, and logs
   at `WARNING`.
5. `enforce_judge()` returns `("UNKNOWN", "judge")` when `score` is outside `[0, 100]`,
   and logs at `WARNING`.
6. `enforce_judge()` returns the threshold-derived verdict and `"judge"` provenance for
   a valid score.
7. When the review action runs a judge template, the returned `ActionResult.verdict` is
   the enforcement-derived value — *not* the parsed verdict — and `ActionResult.provenance`
   is `"judge"`.
8. When the review action runs a standard template, `ActionResult.provenance` is `"review"`.
9. When a judge template action raises an exception (provider down, missing inputs, etc.),
   `ActionResult(success=False, verdict="UNKNOWN", provenance="judge")` is returned with
   a WARNING/ERROR log.
10. Each enumerated failure mode in the failure-mode table is asserted by at least one test
    that verifies the non-passing verdict **and** the log line.

### Technical Requirements

- All existing tests pass unchanged (backward-compatibility gate).
- New unit tests cover:
  - `ReviewTemplate.is_judge` True/False based on `judge:` block presence
  - `JudgeThresholds.derive_verdict()` for all three bands + boundary values
  - `resolve_thresholds()` merging template defaults and step overrides per-key
  - `enforce_judge()` for each failure mode (score None, out-of-range low, out-of-range
    high, valid pass, valid concerns, valid fail) — each verifying returned verdict,
    provenance, and WARNING log via `caplog`
  - `ReviewAction` with a mock judge template: enforcement fires, verdict is
    enforcement-derived, provenance = "judge"
  - `ReviewAction` with a mock standard template: provenance = "review", verdict is
    parsed verdict (unchanged)
  - Exception from `run_review_with_profile` for a judge template → `UNKNOWN` verdict
- New code passes `pyright` strict and `ruff check` / `ruff format`.

### Integration Requirements

- Slice 302 can author a judge template (a YAML with `judge:` block) and run it via
  `sq review` or a pipeline review step with no engine changes — the enforcement layer
  activates because `template.is_judge = True`.
- Slice 304 can read `ActionResult.provenance` to distinguish judge vs. review results
  without needing to know the template name.

### Verification Walkthrough

**Status: all commands verified 20260705, output matches exactly as shown below.**

The walkthrough commands below verify each functional layer without a live provider call.

```bash
# 1. is_judge property on a judge template
uv run python - <<'PY'
from squadron.review.templates import ReviewTemplate, InputDef
# Minimal judge template (is_judge from judge: block presence)
t = ReviewTemplate(
    name="judge.test", description="test", system_prompt="s",
    allowed_tools=[], permission_mode="default", setting_sources=None,
    required_inputs=[], optional_inputs=[],
    prompt_template="test",
    judge={"pass_floor": 75, "concerns_floor": 50},
)
assert t.is_judge, "expected is_judge=True"
t2 = ReviewTemplate(
    name="standard.test", description="test", system_prompt="s",
    allowed_tools=[], permission_mode="default", setting_sources=None,
    required_inputs=[], optional_inputs=[],
    prompt_template="test",
)
assert not t2.is_judge, "expected is_judge=False"
print("PASS: is_judge correct for judge and standard templates")
PY

# 2. JudgeThresholds verdict derivation
uv run python - <<'PY'
from squadron.pipeline.actions.judge import JudgeThresholds
t = JudgeThresholds(pass_floor=75.0, concerns_floor=50.0)
assert t.derive_verdict(100.0) == "PASS"
assert t.derive_verdict(75.0)  == "PASS"
assert t.derive_verdict(74.9)  == "CONCERNS"
assert t.derive_verdict(50.0)  == "CONCERNS"
assert t.derive_verdict(49.9)  == "FAIL"
assert t.derive_verdict(0.0)   == "FAIL"
print("PASS: derive_verdict correct at all band boundaries")
PY

# 3. resolve_thresholds merges correctly
uv run python - <<'PY'
from squadron.pipeline.actions.judge import resolve_thresholds, _DEFAULT_PASS_FLOOR, _DEFAULT_CONCERNS_FLOOR
# All from defaults
t = resolve_thresholds(None, None)
assert t.pass_floor == _DEFAULT_PASS_FLOOR
assert t.concerns_floor == _DEFAULT_CONCERNS_FLOOR
# Template provides concerns_floor; default for pass_floor
t2 = resolve_thresholds({"concerns_floor": 40}, None)
assert t2.pass_floor == _DEFAULT_PASS_FLOOR
assert t2.concerns_floor == 40.0
# Step override wins for pass_floor
t3 = resolve_thresholds({"pass_floor": 70, "concerns_floor": 45}, {"pass_floor": 80})
assert t3.pass_floor == 80.0
assert t3.concerns_floor == 45.0
print("PASS: resolve_thresholds merges correctly")
PY

# 4. enforce_judge failure modes — score None
uv run python - <<'PY'
import logging
from squadron.review.models import ReviewResult, Verdict
from squadron.pipeline.actions.judge import enforce_judge, JudgeThresholds

result = ReviewResult(
    verdict=Verdict.UNKNOWN, findings=[], raw_output="no score here",
    template_name="judge.test", input_files={}, score=None,
)
thresholds = JudgeThresholds(pass_floor=75.0, concerns_floor=50.0)

import io
handler = logging.StreamHandler(io.StringIO())
handler.setLevel(logging.WARNING)
logger = logging.getLogger("test_enforce")
logger.addHandler(handler)
logger.setLevel(logging.WARNING)

verdict, prov = enforce_judge(result, thresholds, "judge.test", logger)
assert verdict == "UNKNOWN", f"expected UNKNOWN, got {verdict}"
assert prov == "judge"
assert handler.stream.getvalue(), "expected WARNING log for absent score"
print("PASS: enforce_judge returns UNKNOWN + WARNING for absent score")
PY

# 5. enforce_judge — valid score produces threshold-derived verdict
uv run python - <<'PY'
import logging
from squadron.review.models import ReviewResult, Verdict
from squadron.pipeline.actions.judge import enforce_judge, JudgeThresholds

thresholds = JudgeThresholds(pass_floor=75.0, concerns_floor=50.0)
logger = logging.getLogger("test_enforce_valid")

for score, expected_verdict in [(80.0, "PASS"), (60.0, "CONCERNS"), (30.0, "FAIL")]:
    result = ReviewResult(
        verdict=Verdict.UNKNOWN, findings=[], raw_output="",
        template_name="judge.test", input_files={}, score=score,
    )
    verdict, prov = enforce_judge(result, thresholds, "judge.test", logger)
    assert verdict == expected_verdict, f"score={score}: expected {expected_verdict}, got {verdict}"
    assert prov == "judge"
print("PASS: enforce_judge derives PASS/CONCERNS/FAIL correctly from score")
PY

# 6. Full regression + static analysis
uv run pytest             # Actual: 2066 passed, 2 skipped
uv run pyright            # Actual: 0 errors, 0 warnings, 0 informations
uv run ruff check && uv run ruff format --check   # Actual: All checks passed! / 329 files already formatted
```

> **Note**: Walkthrough steps 1–5 exercise the pure logic layer without running a
> provider. End-to-end verification — a pipeline step running a judge template against
> real provider output — is covered by the test suite using mocked provider calls.
> The `caplog` fixture asserts WARNING log lines for each failure mode; that is not
> shown here but is required by Success Criteria item 10.
>
> **Caveat discovered during implementation**: existing test helpers in
> `test_review_action.py` and `test_review_action_integration.py` build mock
> `ReviewTemplate`s via `MagicMock(spec=ReviewTemplate)`. Because `is_judge` is a
> real `@property` on the spec, `MagicMock` auto-mocks it as a truthy `Mock` object
> unless explicitly set — every pre-existing test silently became a "judge" template
> until `mock.judge = None; mock.is_judge = False` was added to the shared
> `_mock_template()` helper. One pre-301 assertion (`result.provenance is None`)
> was also updated to `"review"`, since this slice makes provenance non-`None` for
> standard templates too (see "Provenance set for all results" above).

## Risk Assessment

### Technical Risks

- **Scope boundary with 302**: This slice provides the enforcement hook; it cannot
  be tested end-to-end against a real judge template (no templates exist yet). The
  test strategy uses a mock/minimal judge template to keep coverage independent.

### Mitigation Strategies

- Keep `enforce_judge()` a pure function with no I/O so it can be unit-tested in
  complete isolation.
- The `ReviewAction` integration test uses a mocked `run_review_with_profile` to
  return a controlled `ReviewResult` (with and without score), keeping the action
  test free of provider dependencies.

## Implementation Notes

### Development Approach

Suggested order:

1. **`review/templates/__init__.py`**: Add `judge` field and `is_judge` property to
   `ReviewTemplate`; update `load_template` to read the `judge:` block. Test:
   load a mock YAML with `judge:` block → `is_judge=True`; without → `False`.

2. **`pipeline/actions/judge.py`** (new): `Provenance`, `JudgeThresholds`,
   `resolve_thresholds`, `enforce_judge`. Test each function in isolation before
   touching `review.py`.

3. **`pipeline/steps/review.py`**: Pass `judge:` from step config through to action
   params. Test: `expand()` with `judge:` override → override appears in action dict.

4. **`pipeline/actions/review.py`**: Wire enforcement into `_review()` for judge
   templates; set `provenance` for all results. Test: mock judge template + mock
   `ReviewResult` with various score values → enforcement fires; mock standard
   template → provenance = "review", verdict unchanged.

5. **Exception handling**: Verify that exceptions from `run_review_with_profile` for
   a judge template return `verdict="UNKNOWN"` in the `ActionResult`. Test with a
   patched provider that raises.

### Special Considerations

- `enforce_judge()` must be a **pure function** (takes logger as parameter, no global
  state) so it is testable and reusable by 302/304 tests without action context.
- The template `judge:` block is parsed as a raw `dict[str, object]`; float coercion
  happens in `resolve_thresholds()`. Do not validate threshold values at YAML load
  time — a template with `pass_floor: 80` should load successfully regardless of
  whether 80 is a "good" threshold.
- The `is_judge` property is computed from `self.judge is not None` — the only
  sentinel for "this is a judge template." Never use the template name as a dispatch
  signal (project rule: no string dispatch for logic).
