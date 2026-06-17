---
docType: tasks
slice: numeric-scoring-foundation
project: squadron
lld: ../slices/300-slice.numeric-scoring-foundation.md
dependencies:
  - 100 orchestration-v2 (complete) — ReviewResult, parser, run_review_with_profile
  - 140 pipeline-foundation (complete) — ActionResult, review action, StepState/RunState, state manager
projectState: "Initiatives 100 and 140 complete. ReviewResult/ReviewFinding/Verdict/Severity in src/squadron/review/models.py; parser in src/squadron/review/parsers.py; review-file formatter/persistence in src/squadron/review/persistence.py. Pipeline ActionResult in src/squadron/pipeline/models.py; review action in src/squadron/pipeline/actions/review.py; StepState/RunState + StateManager._append_step in src/squadron/pipeline/state.py. No SQL DB — persistence is review-file YAML frontmatter and run-state JSON."
dateCreated: 20260607
dateUpdated: 20260617
status: complete
---

# Tasks: Numeric Scoring Foundation (300)

## Context Summary

- **Working on:** the keystone slice of initiative 300. Add an optional numeric `score` (0–100), a reserved optional `criteria` map, and a reserved optional `provenance` field to the review/action result models, the response parser, and the persisted run state — **additively**.
- **Current state:** the only quality signal anywhere is the categorical `verdict`. The parser extracts verdict + findings and ignores any score. Results persist to review-file frontmatter and run-state JSON, both of which hoist `verdict` as a first-class field today.
- **Key assumptions / discipline (from the LLD):**
  - **No judging logic.** No required-ness, no range validation, no thresholding, no verdict derivation. `provenance` is *added as a field* but never populated or read in this slice (it stays `None`). All of that is slice 301.
  - **Parser stays lenient and judging-unaware.** Extract `score`/`criteria` when present, silent-to-`None` when absent or malformed, never raise, never fabricate a number.
  - **`None` is the only "absent" representation** — no `0`/`-1` sentinels (project no-silent-fallback rule; correctness prerequisite for 301).
  - **Minimal recognized shape:** a top-level `score: <number>` line. The structured-output JSON shape is deferred to 302; do not implement it here.
  - **Every existing test must pass unchanged** (backward-compatibility gate).
- **Dependencies:** initiatives 100 and 140, both complete. Nothing new consumed.
- **What this slice delivers:** the settled result-model shape (`score`/`criteria`/`provenance`), the parser's optional score extraction, threading into `ActionResult`, and persistence on both surfaces — the foundation every later 300 slice builds on with no further model re-open.
- **Next slice:** 301 (Judge Enforcement Layer) — populates `provenance`, validates the score, derives the verdict by thresholding.

---

## Tasks

### T1: Add score / criteria / provenance to ReviewResult

- [x] **Add three optional fields to `ReviewResult` in `src/squadron/review/models.py`**
  - [x] `score: float | None = None`
  - [x] `criteria: dict[str, float] | None = None`
  - [x] `provenance: str | None = None`
  - [x] Place after the existing optional fields; all three default to `None` so existing constructor calls are unaffected
- [x] **Extend `ReviewResult.to_dict()`** to include `score`, `criteria`, and `provenance` keys (emit the raw values; `None` serializes to JSON `null`)
- [x] Success: constructing `ReviewResult(verdict=..., findings=[], raw_output="", template_name="t", input_files={})` succeeds with `score is None`, `criteria is None`, `provenance is None`; `to_dict()` contains all three keys; `uv run pyright` passes

**Commit:** `feat: add score/criteria/provenance fields to ReviewResult`

---

### T2: Tests for ReviewResult fields

- [x] **Add tests in `tests/review/test_models.py`** (extend existing file)
  - [x] A `ReviewResult` built without the new kwargs has `score`, `criteria`, `provenance` all `None`
  - [x] A `ReviewResult` built *with* `score=87.5`, `criteria={"alignment": 90.0}`, `provenance="judge"` round-trips those values
  - [x] `to_dict()` includes keys `score`, `criteria`, `provenance`; values match (and are `null`/`None` when unset)
  - [x] An existing-shape `ReviewResult` (no new fields) still serializes its prior keys unchanged
- [x] Success: `uv run pytest tests/review/test_models.py` passes

**Commit:** `test: cover ReviewResult score/criteria/provenance`

---

### T3: Add score / criteria / provenance to ActionResult

- [x] **Add three optional fields to `ActionResult` in `src/squadron/pipeline/models.py`**
  - [x] `score: float | None = None`
  - [x] `criteria: dict[str, float] | None = None`
  - [x] `provenance: str | None = None`
  - [x] Mirror the existing optional `verdict: str | None = None` field placement/style
  - [x] Confirm `dataclasses.asdict(ar)` (used in `state.py::_append_step`) picks the new fields up automatically — no extra serialization code needed
- [x] Success: `ActionResult(success=True, action_type="review", outputs={})` has all three new fields `None`; `dataclasses.asdict()` of such a result includes the three keys; `uv run pyright` passes

**Commit:** `feat: add score/criteria/provenance fields to ActionResult`

---

### T4: Tests for ActionResult fields

- [x] **Add tests in `tests/pipeline/test_models.py`** (extend existing; create if absent)
  - [x] A default `ActionResult` has `score`, `criteria`, `provenance` all `None`
  - [x] An `ActionResult` built with explicit values round-trips them
  - [x] `dataclasses.asdict()` of an `ActionResult` contains the three new keys
- [x] Success: `uv run pytest tests/pipeline/test_models.py` passes

**Commit:** `test: cover ActionResult score/criteria/provenance`

---

### T5: Add optional score extraction to the parser

- [x] **Add a `_extract_score` helper in `src/squadron/review/parsers.py`** (small, single-purpose, mirroring `_extract_verdict`)
  - [x] Recognizes a top-level `score: <number>` line (case-insensitive label, tolerant of surrounding whitespace; lenient like the existing patterns)
  - [x] Returns `float | None` — `None` when no `score:` line is present
  - [x] **First match wins** when multiple `score:` lines appear (consistent with `_extract_verdict` taking the first `## Summary` match)
  - [x] Non-numeric value (e.g. `score: high`) → returns `None`, **does not raise**
  - [x] `inf` / `nan` (any case) → rejected as non-finite → returns `None` (use a finite-number check; never return a non-finite float)
  - [x] Does **not** range-check — `score: 150` and `score: -3` are returned as `150.0` / `-3.0` (range validation is 301's job)
- [x] **Add a `_extract_criteria` helper** for an optional `criteria` map
  - [x] **Recognized shape:** a top-level `criteria:` label followed by an indented block of `key: <number>` lines (the ordinary YAML-map frontmatter idiom — the same shape T9 emits). Read that block into a `dict[str, float]`
  - [x] Returns `dict[str, float] | None`; `None` when no `criteria:` block is present
  - [x] Malformed criteria (not a map / any value not a finite number / unexpected nesting) → returns `None` as a **whole** (no partial or coerced map), no raise
  - [x] Do not implement the structured-output/JSON variant — that is 302
- [x] **Wire both into `parse_review_output`**: populate `ReviewResult.score` / `.criteria` from the helpers; leave `provenance` untouched (parser never sets it)
  - [x] When neither is present, the returned `ReviewResult` is identical in shape to today (both `None`)
  - [x] No new WARNING log lines (absence/malformed-to-`None` is a normal, silent outcome here — the observable-on-required-absence treatment belongs to 301)
- [x] Success: `parse_review_output("## Summary\nPASS\n", "t", {}).score is None`; a fixture containing a `score:` line parses to the expected float; `uv run pyright` passes

**Commit:** `feat: extract optional score/criteria in review parser`

---

### T6: Tests for parser extraction (including failure-mode table)

- [x] **Add fixtures + tests in `tests/review/test_parsers.py`** (extend existing)
  - [x] **Score-less real fixture:** an actual existing-template review output (slice/code/arch/tasks shape) → `score is None`, `criteria is None`, and verdict/findings parse exactly as before (regression guard)
  - [x] **Score-bearing fixture:** a response with a top-level `score: <n>` line → correct float extracted
  - [x] **Criteria-bearing fixture:** a response with a `criteria:` block of indented `key: <number>` lines → correct `dict[str, float]` extracted
  - [x] Failure-mode table cases, each its own assertion:
    1. Non-numeric value (`score: high`) → `score is None`, no exception
    2. `score: inf` and `score: nan` → `score is None`, no exception
    3. Multiple `score:` lines → first value wins
    4. Malformed `criteria` (non-map / non-float values) → `criteria is None`, no exception
  - [x] Out-of-range value (`score: 150`) → extracted as `150.0` (proves range-checking is NOT done here)
- [x] Success: `uv run pytest tests/review/test_parsers.py` passes; all existing parser tests still pass

**Commit:** `test: cover parser score extraction and failure modes`

---

### T7: Thread score/criteria through the review action

- [x] **Update the `ReviewResult → ActionResult` map in `src/squadron/pipeline/actions/review.py`** (the `return ActionResult(...)` at ~line 204)
  - [x] Pass `score=result.score` and `criteria=result.criteria` into the returned `ActionResult`
  - [x] Leave `provenance` unset (passes through as `None` — not this slice's concern)
  - [x] Do not alter the existing `verdict` / `findings` / `outputs` / `metadata` mapping
- [x] Success: a review whose `ReviewResult` carries a score yields an `ActionResult` with the same `score`; a score-less review yields `ActionResult.score is None`; `uv run pyright` passes

**Commit:** `feat: thread score/criteria into review ActionResult`

---

### T8: Tests for review action threading

- [x] **Add tests in `tests/pipeline/actions/test_review_action.py`** (extend existing)
  - [x] With a parser/result producing a score, the action's `ActionResult.score` equals it (mock or construct the `ReviewResult`; do not require live providers)
  - [x] With a score-less result, `ActionResult.score is None` and `.criteria is None`
  - [x] `ActionResult.provenance is None` (action does not set it)
- [x] Success: `uv run pytest tests/pipeline/actions/test_review_action.py` passes

**Commit:** `test: cover review action score threading`

---

### T9: Emit score/criteria in review-file frontmatter

- [x] **Update `format_review_markdown` in `src/squadron/review/persistence.py`**
  - [x] When `result.score is not None`, emit a top-level `score: <value>` line in the YAML frontmatter, alongside the existing `verdict:` line
  - [x] When `result.criteria is not None`, emit a `criteria:` block (YAML map) in the frontmatter
  - [x] Emit **nothing** for either when the value is `None` (score-less reviews produce byte-for-byte the prior frontmatter)
  - [x] Do not emit `provenance` (not populated this slice)
- [x] Success: a score-bearing result's frontmatter contains a top-level `score:` line greppable with `grep -E '^score:'`; a score-less result's frontmatter is unchanged from today; `uv run pyright` passes

**Commit:** `feat: emit score/criteria in review frontmatter`

---

### T10: Tests for frontmatter emission

- [x] **Add tests in `tests/review/test_persistence.py`** (extend existing)
  - [x] Score-bearing result → frontmatter string contains a line matching `^score:` with the right value
  - [x] Score-less result → frontmatter contains no `score:` line and matches the prior expected output
  - [x] Criteria present → a `criteria:` block appears; criteria absent → no such block
- [x] Success: `uv run pytest tests/review/test_persistence.py` passes

**Commit:** `test: cover review frontmatter score emission`

---

### T11: Hoist score into StepState (run-state persistence)

- [x] **Add `score: float | None = None` to `StepState` in `src/squadron/pipeline/state.py`** (mirror the existing `verdict: str | None = None` field)
- [x] **Update `StateManager._append_step`** to hoist the score from the last non-`None` action score into `StepState.score`
  - [x] Mirror the existing verdict hoist loop (iterate `reversed(step_result.action_results)`, take the first `ar.score is not None`)
  - [x] Leave the existing verdict hoist and `action_results` serialization untouched (the full `ActionResult` incl. its `score` already lands in `action_results` via `dataclasses.asdict`)
- [x] Success: after a step whose action carried a score, the persisted `StepState.score` equals it; a score-less step has `StepState.score is None`; older run-state JSON lacking `score` still loads (Pydantic default); `uv run pyright` passes

**Commit:** `feat: hoist score into StepState run-state`

---

### T12: Tests for run-state score hoist

- [x] **Add tests in `tests/pipeline/test_state.py`** (extend existing)
  - [x] `_append_step` with an action carrying `score=87.5` → persisted `StepState.score == 87.5`
  - [x] `_append_step` with no action score → `StepState.score is None`
  - [x] Multiple actions, last non-`None` score wins (mirror the verdict-hoist semantics)
  - [x] Round-trip: a `RunState` JSON written without `score` deserializes with `StepState.score is None` (backward-compat for existing run-state files)
- [x] Success: `uv run pytest tests/pipeline/test_state.py` passes

**Commit:** `test: cover StepState score hoist and backward compat`

---

### T13: Full validation pass

- [x] **Run the full suite and static analysis**
  - [x] `uv run pytest` — entire suite green (existing tests unchanged + all new tests pass)
  - [x] `uv run pyright` — 0 errors
  - [x] `uv run ruff check && uv run ruff format --check` — clean
- [x] **Run the LLD Verification Walkthrough commands 1–3** (the non-interactive ones) and confirm the expected output
- [x] **Confirm no judging logic leaked in:** grep the diff for any range check on the score, any verdict-from-score derivation, any read/write of `provenance` — there must be none (all are 301)
- [x] Success: full suite + static analysis clean; walkthrough commands produce expected output; the no-judging-logic check passes

**Commit:** `chore: validate numeric-scoring foundation slice`

---

## Coverage Check (against LLD)

| LLD change | Task(s) |
|------------|---------|
| `ReviewResult` fields + `to_dict()` | T1, T2 |
| `ActionResult` fields | T3, T4 |
| Parser optional extraction + failure modes | T5, T6 |
| Review action threading | T7, T8 |
| Frontmatter emission | T9, T10 |
| `StepState.score` + `_append_step` hoist | T11, T12 |
| Backward-compat + static-analysis gate | T2, T6, T12, T13 |
| Provenance reserved (field only, never populated) | T1, T3 (added); T13 (verified unused) |
