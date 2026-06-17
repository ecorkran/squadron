---
docType: slice-design
slice: numeric-scoring-foundation
project: squadron
parent: 300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [100, 140]
interfaces: [301, 302, 303, 304]
dateCreated: 20260605
dateUpdated: 20260617
status: complete
---

# Slice Design: Numeric Scoring Foundation

## Overview

Add an optional numeric **`score`** (0–100) and a reserved optional **`criteria`** map (criterion name → sub-score) to the review/action result models, the response parser, and the persisted run state — additively, so quality becomes a representable, persistable, queryable quantity. The parser extracts the score **when present** and returns the prior shape **when absent**; existing score-less reviews parse byte-for-byte as before. This slice carries **no judging logic**: no required-ness, no range validation, no thresholding, no verdict derivation, no provenance. The parser never knows it is in a judging context. Those concerns belong to slice 301 (Judge Enforcement Layer), which consumes the field this slice provides.

This is the keystone slice of initiative 300, ordered first and done alone, because it is the one cross-cutting model change every later slice composes on.

## Value

**Architectural enablement.** Today the only quality signal anywhere in the review-and-judge layer is the categorical `verdict` (`PASS | CONCERNS | FAIL | UNKNOWN`). After this slice, a result can carry a 0–100 number alongside the verdict, the parser surfaces it when a response includes it, and it persists as a first-class field rather than buried in an opaque payload. Every subsequent slice — enforcement (301), judge templates (302), the judge-gated cycle (303), gate composition (304) — builds directly on the field shape this slice settles.

There is also modest **standalone value before any judge exists**: a standard `review` template *may* now emit a score, and if it does, that score is parsed, serialized to JSON, written to review-file frontmatter, and hoisted into run state — available to any script that greps the YAML header or reads the JSON output.

## Technical Scope

### What changes

1. **`ReviewResult` (`review/models.py`)** — add three optional fields: `score: float | None = None`, `criteria: dict[str, float] | None = None`, and `provenance: str | None = None`. Extend `to_dict()` to include all three. Constructing a `ReviewResult` without them succeeds unchanged (they default to `None`).

2. **`ActionResult` (`pipeline/models.py`)** — add `score: float | None = None`, `criteria: dict[str, float] | None = None`, and `provenance: str | None = None`, mirroring the existing optional `verdict` field. `dataclasses.asdict()` (used by state serialization) picks these up automatically.

3. **Response parser (`review/parsers.py`)** — add lenient, optional extraction of a top-level numeric `score` and a `criteria` map. When neither is present, behavior is identical to today. When present, they populate the new `ReviewResult` fields. No validation, no range check, no failure on absence — extraction only.

4. **Review action (`pipeline/actions/review.py`)** — thread `result.score` / `result.criteria` from the `ReviewResult` into the returned `ActionResult` (the `ReviewResult → ActionResult` map at lines 204–215).

5. **Review-file frontmatter (`review/persistence.py::format_review_markdown`)** — emit `score:` (and `criteria:` when present) as **top-level frontmatter fields**, alongside the existing `verdict:` field, only when the result carries a score. This is the "first-class, queryable, not-opaque" persistence commitment for the file artifact.

6. **Run state (`pipeline/state.py`)** — add `score: float | None = None` to `StepState`, and in `_append_step` hoist the score from the last non-`None` action score into `StepState.score`, exactly mirroring how `verdict` is already hoisted (state.py:267–286). This is the "first-class, queryable" commitment for the persisted run record.

### What does NOT change

- The `Verdict` / `Severity` enums (the verdict remains the operational gating signal; the score is purely additive).
- The verdict-extraction and finding-extraction logic in the parser (extended with a new optional pass, not modified).
- Any existing pipeline, checkpoint, or gating behavior — every existing test passes unchanged.
- The prose markdown body of review files.
- **No judging logic of any kind** — required-ness, range-checking, thresholding, verdict derivation, and *populating/consuming* provenance are all explicitly out of scope (slice 301). Note: the provenance **field** is *added* here (latent, defaulting to `None`) — see Technical Decisions — but no code sets or reads it in this slice.
- **The existing review templates** (`data/templates/{slice,code,arch,tasks}.yaml`) — verified unchanged. They instruct the agent to emit `## Summary` + verdict + findings, never a score, so they continue to parse identically (`score` stays `None`). The template that *emits* a score is a new **judge** template, authored in **slice 302** ("a judge is a review with a judge-flavored system prompt that emits a score"). Adding a score to a standard review template here would be scope creep and pointless — nothing enforces or gates on the score until 301.

### Explicitly out of scope (downstream slices)

- Requiring a score, validating 0–100, deriving a verdict from it, **populating and consuming** the provenance discriminator, threshold config — **all slice 301.** (The provenance *field* is reserved here; its *meaning and use* are 301's.)
- Judge system-prompt templates and the score-with-rationale shape — **slice 302.**
- A persisted score and a reserved provenance field are *latent* here; nothing reads either for gating until 301 exists.

## Dependencies

### Prerequisites
- **Initiative 100 (Orchestration v2, complete):** `ReviewResult`, `ReviewFinding`, the parser, and `run_review_with_profile`.
- **Initiative 140 (Pipeline Foundation, complete):** `ActionResult`, the review action, `StepState` / `RunState`, and the state manager.

### Interfaces Required
- The existing `ReviewResult` dataclass and its `to_dict()`.
- The existing `ActionResult` dataclass and `dataclasses.asdict()`-based state serialization.
- The existing `format_review_markdown` frontmatter builder.

## Architecture

### Component Structure

Five existing modules gain additive fields/extraction; no new module is created.

| Module | Change |
|--------|--------|
| `review/models.py` | `ReviewResult.score`, `.criteria`, `.provenance` (reserved); `to_dict()` extension |
| `pipeline/models.py` | `ActionResult.score`, `.criteria`, `.provenance` (reserved) |
| `review/parsers.py` | optional `score` / `criteria` extraction in `parse_review_output` (never sets `provenance`) |
| `pipeline/actions/review.py` | thread score/criteria into the returned `ActionResult` |
| `review/persistence.py` | emit `score:` / `criteria:` in frontmatter when present |
| `pipeline/state.py` | `StepState.score`; hoist in `_append_step` |

### Data Flow

```
Agent output (markdown, optionally containing a score line/block)
    │
    ▼
parsers.py: parse_review_output()
    │  extracts verdict + findings   (existing, unchanged)
    │  NEW: extracts optional score + criteria when present
    │
    ▼
ReviewResult
    │  .verdict, .findings            (existing)
    │  .score: float | None           (NEW — None when absent)
    │  .criteria: dict | None         (NEW — None when absent)
    │  .provenance: str | None        (NEW — reserved; always None this slice)
    │
    ├──▶ to_dict() / JSON output      (NEW: score, criteria, provenance keys)
    │
    ├──▶ format_review_markdown()     (NEW: top-level score:/criteria: frontmatter when present)
    │
    └──▶ ReviewAction maps to ActionResult
              │  .verdict, .findings  (existing)
              │  .score, .criteria    (NEW, passed through)
              │  .provenance          (NEW field — unset, stays None)
              │
              ▼
         StateManager._append_step()
              │  hoists last non-None verdict  (existing)
              │  NEW: hoists last non-None score → StepState.score
              ▼
         RunState JSON (run-state file)
              StepState.score: first-class queryable field
              StepState.action_results[*]: full ActionResult incl. score (via asdict)
```

### State Management

Two persistence surfaces, both already established for `verdict`, now extended for `score`:

- **Review-file frontmatter** (`format_review_markdown`): `score:` becomes a top-level YAML key next to `verdict:`. Greppable / YAML-parseable from the header without reading the prose body.
- **Run-state JSON** (`StepState`): `score` becomes a hoisted top-level field on the step record, populated from the last non-`None` action score, exactly as `verdict` is. Cross-run comparison reads `completed_steps[*].score` without descending into the opaque `action_results` blob.

This is the concrete answer to the architecture's "persist the score as a first-class, queryable field, not buried in an opaque blob" commitment — there is no SQL database in squadron; the queryable surfaces are the frontmatter YAML and the run-state JSON, and in both the score is promoted to a named top-level field rather than left inside a serialized payload.

## Technical Decisions

### Field types
- `score: float | None`. Float (not int) because the architecture's 0–100 range is a quantity, downstream multi-sample median (Future Work 1) produces non-integers, and a float trivially holds integer scores. `None` is the unambiguous "no score present" state — never a sentinel like `-1` or `0` (a real failing score).
- `criteria: dict[str, float] | None`. Reserved per the architecture's "scalar now; criterion breakdown anticipated" principle. `None` when absent; a populated map when a response supplies sub-scores. No schema is committed beyond `str → float`; the architecture explicitly accepts that this reserved shape may still evolve.

### Provenance is a *reserved field* here, not deferred to 301
The architecture commits the provenance discriminator (judge-derived vs. review-produced) to the **result model** — and this is the keystone slice whose stated purpose is to settle the result-model shape *once*, so that 301 adds *logic*, not *fields*. Therefore the **field** is added here — `provenance: str | None = None` on `ReviewResult` and `ActionResult` — as a latent, additive field, exactly as `score` and `criteria` are reserved. **No code in this slice populates or reads it**; constructing a result leaves it `None`, and the existing review/parser/persistence paths never touch it. Slice 301 supplies its *meaning and use*: it sets the value when a judge derives a verdict from a score, and consumers (304, 320) read it to disambiguate a result carrying both score and verdict.

- Type is `str | None` (not a committed enum) for the same reason `criteria` is left as a loose map: the exact enum/values are explicitly 301/slice-design detail per the architecture ("the exact field name/enum is slice-design detail"). Reserving the field as `str | None` settles the *shape* (the model gains the attribute, serialization carries it) without pre-committing 301's enum. If 301 chooses an enum, narrowing a `str | None` that is always `None` here is itself an additive, non-breaking change. The cost if this proves wrong is one unused optional field — the same bounded downside the architecture accepts for `criteria`.

### Parser remains lenient and judging-unaware (architectural commitment)
The parser extracts the score **when present** and is silent **when absent** — it never raises, never range-checks, never defaults to a number. This is the parser side of the architecture's two-layer split: optional at the parser, required at the judge use (301). Per the project's parsing rules, the extraction matches the *semantic content* (a labeled numeric score) tolerantly across format variations, not one exact layout.

**Recognized shape — minimal in 300, extended in 302.** This slice pins only the simplest shape: a top-level `score: <number>` line in the response (mirroring how `verdict` appears under `## Summary` today). That is what 300's tests assert and what the extraction must recognize. The richer **structured-output** shape (a JSON object carrying a `score` key) is **deliberately not committed here** — the judge's emitted output shape is a slice-302 decision, and 302 will extend the extraction and add its own parser test for that variant. Pinning the structured shape in 300 would pre-commit 302's design; pinning only the line shape keeps 300 self-contained and genuinely minimal. The standing commitment for 300 is **lenient extraction of the `score:` line, silent on absence, no validation here.**

**Criteria recognized shape (minimal, matching the frontmatter idiom).** `criteria` is pinned to the same minimal posture as `score`: a top-level `criteria:` label followed by an indented block of `key: <number>` lines — the ordinary YAML-map shape squadron already uses in frontmatter (and exactly what `format_review_markdown` emits in this slice). Extraction reads that block into a `dict[str, float]`; absence → `None`; any line whose value is not a finite number, or a `criteria:` that is not a map, makes the **whole** `criteria` result `None` (no partial map — see the failure-mode table). Like `score`, the richer structured-output variant is 302's to add. This gives T6 a concrete positive fixture to assert against.

### Where range validation is deliberately absent
A value like `score: 150` or `score: -3` is **accepted as-is** by this slice (extracted to `score=150.0`). Range validation and the resulting `UNKNOWN` verdict are 301's responsibility, at the judge use. Putting *range* validation in the parser would (a) break the lenient-parser commitment and (b) wrongly fail a standard review that happens to emit an out-of-range number. The parser's only job is faithful extraction. **Range-checking ≠ parseability**: a value outside 0–100 is still a parseable number and is extracted; a value that is not a number at all is a different case, handled below.

### Failure-mode enumeration for the score/criteria extraction path
The extraction is a new input path, so its malformed-input behavior is enumerated explicitly (project Failure-Mode Enumeration rule; the architecture's own enumerated-failure standard). The governing principle: **the parser never raises on malformed score/criteria input and never invents a number — a value it cannot interpret as the target type leaves the field `None`.** Distinguishing "absent" from "present-but-unusable" is 301's job (a judge requiring a score treats `None` from either cause as `UNKNOWN`); the parser only guarantees it does not crash and does not fabricate.

| Malformed input | Parser behavior |
|-----------------|-----------------|
| No score present at all | `score` stays `None` (the backward-compatible baseline) |
| `score:` line with a non-numeric value (`score: high`) | not interpretable as a float → `score` stays `None`, **no raise** |
| `score: inf` / `score: nan` | rejected as not a finite number → `score` stays `None` (a non-finite score is meaningless as a 0–100 quantity; rejecting at parse keeps `None` the only "no usable score" state rather than letting `inf`/`nan` poison 301's comparison) |
| Multiple `score:` lines in one response | **first match wins**, deterministically (consistent with how `_extract_verdict` takes the first `## Summary` match); the duplicate is ignored |
| `criteria` present but not a map / non-float values / unexpected nesting | `criteria` stays `None` as a whole (no partial/coerced map) — a malformed criteria block yields the same "absent" state, never a half-parsed dict |

Each of these is covered by at least one parser test (see Technical Requirements). None of them is an *observable WARNING* case in 300 — they are silent-to-`None` by design, because the parser is judging-unaware and "I didn't find a usable score" is a normal outcome for the vast majority (score-less) of reviews. The **observable** treatment (logging a WARNING when a judge *required* a score and got `None`) belongs to 301, where absence is actually an error; surfacing it in the parser would fire on every ordinary review.

### Backward compatibility
Every new field defaults to `None`. Every existing constructor call, every existing parse of a score-less response, every existing review-file and run-state record continues to work and serialize identically (absent fields simply do not appear / are `None`). No migration of existing persisted artifacts is required — older run-state files lacking `score` deserialize with the Pydantic default.

## Integration Points

### Provides to Other Slices
- **`ReviewResult.score` / `.criteria` / `.provenance`** and their `to_dict()` keys — `score`/`criteria` consumed by 301 (validation/thresholding), 302 (judge output), 304 (composition); the reserved `provenance` field is *populated* by 301 and *read* by 304/320 (300 only provides the slot).
- **`ActionResult.score` / `.criteria` / `.provenance`** — the pipeline-layer carrier; `score`/`criteria` consumed by 301's enforcement and 304's reduction, `provenance` reserved for 301 to set.
- **`StepState.score`** — the queryable persisted record consumed by 303 (cycle conventions inspecting prior scores) and eventually 320 (calibration/metrology querying scores across runs).
- **The parser's optional score extraction** — consumed by 302's judge templates, whose emitted score this extraction surfaces.

### Consumes from Other Slices
- Nothing new. It extends models and machinery delivered complete by 100 and 140.

## Success Criteria

### Functional Requirements
1. `score`, `criteria`, and `provenance` are optional on `ReviewResult` and `ActionResult`; constructing either without them succeeds, with all three defaulting to `None`.
2. The parser extracts `score` (and `criteria` when present) from a score-bearing response, and returns the prior shape (all `None`) for a score-less response. The parser never sets `provenance`.
3. `ReviewResult.to_dict()` includes `score`, `criteria`, and `provenance` keys.
4. `format_review_markdown` emits a top-level `score:` frontmatter field (and `criteria:` when present) when the result carries a score, and omits them when it does not.
5. The review action populates `ActionResult.score` / `.criteria` from the `ReviewResult`.
6. `StepState` carries a top-level `score` field, populated in `_append_step` from the last non-`None` action score, mirroring the verdict hoist.
7. The malformed-input cases in the failure-mode table each yield `None` (never a raise, never a fabricated number); each is covered by a parser test.
8. No required-ness, range validation, thresholding, or verdict derivation is introduced, and no code populates or reads `provenance` (verified by the absence of any such code path and by 301 being the slice that adds them). The `provenance` *field* exists but stays `None` throughout this slice.

### Technical Requirements
- All existing tests pass unchanged (backward-compatibility gate).
- New tests cover: score-less response → `score is None` (regression of existing behavior, using a **real score-less review response fixture** — one of the existing `slice`/`code`/`arch`/`tasks` template outputs); score-bearing response → correct `score` and `criteria` (using a **fixture with a top-level `score:` line**, the minimal shape 300 pins — *not* the structured-output shape, which is 302's to add); round-trip through `to_dict()`, frontmatter, and run-state hoist.
- New code passes `pyright` strict and `ruff check` / `ruff format`.

### Integration Requirements
- After this slice, slice 301 can build validation/thresholding on `ReviewResult.score` / `ActionResult.score` and populate the already-present `provenance` field with **no model re-open** — the result-model shape is fully settled here, honoring the keystone "settle the shape once" rationale.
- Existing verdict-gating pipelines and the checkpoint machinery behave identically (the score is latent — nothing gates on it yet).

### Verification Walkthrough

```bash
# 1. Optional fields exist and default to None on ReviewResult
uv run python -c "from squadron.review.models import ReviewResult, Verdict; \
r = ReviewResult(verdict=Verdict.PASS, findings=[], raw_output='', template_name='t', input_files={}); \
print('score=', r.score, 'criteria=', r.criteria, 'provenance=', r.provenance); \
d = r.to_dict(); print('to_dict keys present:', {'score','criteria','provenance'} <= d.keys())"
# Expect: score= None criteria= None provenance= None  /  to_dict keys present: True

# 2. Optional fields exist on ActionResult
uv run python -c "from squadron.pipeline.models import ActionResult; \
a = ActionResult(success=True, action_type='review', outputs={}); \
print('score=', a.score, 'criteria=', a.criteria)"
# Expect: score= None criteria= None

# 3. Parser is silent on a score-less response, extracts on a score-bearing one
uv run python -c "from squadron.review.parsers import parse_review_output; \
no_score = parse_review_output('## Summary\nPASS\n', 't', {}); \
print('score-less:', no_score.score)"
# Expect: score-less: None
# (A score-bearing parse is asserted in the test suite against a real fixture;
#  exact recognized shape is pinned during task implementation.)

# 4. Frontmatter carries score only when present.
#    Verified non-interactively (no live review needed) by formatting a
#    score-bearing result and grepping the frontmatter:
uv run python - <<'PY' > /tmp/wt4_review.md
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import format_review_markdown
r = ReviewResult(verdict=Verdict.PASS, findings=[], raw_output="", template_name="code",
                 input_files={}, score=87.5, criteria={"alignment": 90.0})
print(format_review_markdown(r, "code"))
PY
grep -E '^score:' /tmp/wt4_review.md
# Expect: score: 87.5   (a score-less result emits no `^score:` line — 0 matches).

# 5. Run state hoists the score as a first-class field.
#    Verified non-interactively by round-tripping a StepState through the
#    RunState JSON serialization (the same path _append_step writes):
uv run python - <<'PY'
import json
from datetime import UTC, datetime
from squadron.pipeline.state import StepState, RunState
now = datetime.now(UTC)
st = StepState(step_name="review", step_type="review", status="completed",
               verdict="PASS", score=87.5, completed_at=now)
rs = RunState(run_id="r1", pipeline="p", params={}, started_at=now, updated_at=now,
              status="completed", completed_steps=[st])
dumped = json.loads(json.dumps(rs.model_dump(mode="json")))
print([(s["step_name"], s.get("score")) for s in dumped["completed_steps"]])
PY
# Expect: [('review', 87.5)] — the score is a top-level step field, not only
# inside action_results. The hoist from a live action score is covered by
# tests/pipeline/test_state.py::TestStepCallbackScore::test_score_hoisted_from_action.

# 6. Full regression + static analysis
uv run pytest          # Expect: 1969 passed, 2 skipped (existing + new)
uv run pyright         # Expect: 0 errors, 0 warnings, 0 informations
uv run ruff check && uv run ruff format --check   # Expect: clean
```

> **Caveat (verification):** Walkthrough commands 4 and 5 were originally
> phrased against a live review file / run-state file. They are replaced
> above with equivalent **non-interactive probes** that exercise the same
> production code paths (`format_review_markdown`, `RunState`/`StepState`
> serialization) without needing a provider call or a full pipeline run, so an
> external agent can run them verbatim. The live-artifact path is additionally
> covered by the test suite (frontmatter: `tests/review/test_persistence.py`;
> hoist: `tests/pipeline/test_state.py`).

## Risk Assessment

### Technical Risks
- **Cross-cutting model change.** The score touches models every pipeline depends on, plus the parser and two persistence surfaces. A regression here would ripple widely.

### Mitigation Strategies
- **Additive-only, all fields default `None`.** No existing call site or persisted artifact changes shape unless a score is actually present.
- **Isolation.** This slice ships alone, with no judging logic, so the model/parser/persistence change is verified in isolation before any consumer depends on it (the architecture's explicit reason for ordering it first).
- **Real-fixture tests on both paths.** A score-less fixture guards the backward-compatibility path; a `score:`-line fixture guards the new path — preventing a parser that silently returns `None` on valid score-bearing input (the project's "parser must be tested on real input" rule). The failure-mode table's malformed cases are each tested too.

## Implementation Notes

### Development Approach
Suggested order (each step independently testable, each leaves the suite green):
1. `ReviewResult.score` / `.criteria` / `.provenance` + `to_dict()` — and a test that a result without them is unchanged.
2. `ActionResult.score` / `.criteria` / `.provenance` — defaults verified.
3. Parser optional `score`/`criteria` extraction — tested against a real score-less fixture, a `score:`-line fixture, and the malformed-input cases from the failure-mode table. (The parser does not touch `provenance`.)
4. Review action threading `ReviewResult → ActionResult` (`score`/`criteria`; `provenance` passes through as `None`).
5. Frontmatter emission (present/absent cases).
6. `StepState.score` + `_append_step` hoist (mirror the verdict hoist; run-state round-trip test).

### Special Considerations
- Keep the parser's score extraction in its own small function (mirroring `_extract_verdict`), so 301 can reason about "extracted vs. validated" cleanly.
- Do not let any default score leak in (`None` is the only "absent" representation — no `0`, no `-1`); this is a project "no silent fallback values" requirement and a correctness requirement for 301's required-ness check.
