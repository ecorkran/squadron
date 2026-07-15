---
docType: review
layer: project
reviewType: code
slice: judge-gated-cycle-conventions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md
aiModel: claude-sonnet-5 (via /code-review skill, medium effort)
status: complete
dateCreated: 20260715
dateUpdated: 20260715
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Loop's dispatch (fix) step never receives the prior judge's findings/score"
    location: src/squadron/data/pipelines/judge-cycle.yaml:15
  - id: F002
    severity: concern
    category: correctness
    summary: "template.model fallback is invisible to the slice-243 classification pre-scan, causing a false ClassificationError"
    location: src/squadron/pipeline/actions/review.py:111
  - id: F003
    severity: concern
    category: correctness
    summary: "Judge-verdict computation moved before persistence — a malformed threshold now discards the review file entirely"
    location: src/squadron/pipeline/actions/review.py:213
  - id: F004
    severity: note
    category: correctness
    summary: "as_json persistence path never receives verdict_override (currently dormant, no live caller)"
    location: src/squadron/review/persistence.py:284
---

# Review: code — slice 303

**Verdict:** CONCERNS
**Model:** claude-sonnet-5 (via `/code-review` skill, medium effort — 8 finder angles, 1-vote verify)

## Findings

### [CONCERN] Loop's dispatch (fix) step never receives the prior judge's findings/score

`judge-cycle.yaml`'s loop body sets a static `prompt:` string on the `dispatch` step ("Address any findings from the prior judge review if present; otherwise perform an initial improvement pass..."). `dispatch.py`'s `_resolve_prompt` takes an explicit `prompt` from step config verbatim (`dispatch.py:217-219`) and only scans `prior_outputs` for review results when `prompt` is *absent* (`dispatch.py:220-233`, the `else` branch). Since the YAML always sets `prompt`, that scan never runs. The only other injection point, `override_instructions`, is populated solely by the interactive checkpoint handler — not by the loop or the review step. Consequently, on iteration 2+ the model doing the "fix" has no access to what the judge actually found wrong; it receives the same generic instruction every iteration. The judge-gated cycle can still auto-advance (if the artifact happens to already clear the floor) or exhaust to checkpoint, but the fix leg cannot act on specific feedback — the loop retries the same blind pass up to `max` rather than genuinely converging toward a passing score.

**Verified:** CONFIRMED (independent agent traced `dispatch.py:217-233` and `judge-cycle.yaml`'s prompt/override_instructions fields).

### [CONCERN] template.model fallback is invisible to the slice-243 classification pre-scan, causing a false ClassificationError

This slice's live-validation fix (T7 discovery) added a retry in `ReviewAction._review`: when `context.resolver.resolve(action_model, step_model)` raises `ModelResolutionError`, it retries with `template.model` as a substitute `action_model`. This retry is call-site-local — it does not go through `ModelResolver.cascade_candidates()`, which `resolver.py`'s own docstring calls the cascade's single source of truth, used by the slice-243 classification pre-scan (`classification.py`) to predict which tier wins *before* deciding whether to invoke pool selection. `classify_pipeline` (`classification.py:465-476`) sees all 5 cascade tiers as `None` and raises `ClassificationError` in exactly the case where the new fallback is meant to succeed at runtime. Any pipeline relying solely on a template's declared default model (no CLI/action/step/pipeline/config value) — including `judge-cycle.yaml` if its `review-model` param were ever omitted — will fail classification before execution starts, even though `ReviewAction._review` itself would resolve fine.

**Verified:** CONFIRMED (independent agent traced `classification.py:465-476` and `_classify_container_inner:307-311`, both blind to `template.model`).

### [CONCERN] Judge-verdict computation moved before persistence — a malformed threshold now discards the review file entirely

To fix the persisted-verdict bug (T7 discovery: judge templates always parse as `UNKNOWN`), the `if template.is_judge:` block computing `resolve_thresholds`/`enforce_judge` was moved from *after* the persistence try/except to *before* it, so the derived verdict could be passed into `verdict_override`. `resolve_thresholds` (`judge.py`) calls unguarded `float()` on `pass_floor`/`concerns_floor` values from the template default or a step-level `judge:` override, with no validation. A malformed override (e.g. `judge: {pass_floor: "not-a-number"}`) now raises before the persistence `try:` block (`review.py:230`) is ever reached — meaning a review whose model call already succeeded is discarded with **no file written at all**. Previously, persistence ran first (in its own non-fatal try/except), so the review artifact was saved even when the later judge computation failed.

**Verified:** CONFIRMED (independent agent confirmed the reorder via git history and traced the unguarded `float()` call).

### [NOTE] as_json persistence path never receives verdict_override (currently dormant, no live caller)

`save_review_result`'s `as_json=True` branch calls `result.to_dict()` directly and never receives the new `verdict_override` parameter — only the markdown branch does (the docstring says as much: "Ignored for `as_json` output"). For a judge template persisted as JSON, the JSON `verdict` field would show `UNKNOWN` while the markdown persistence of the identical run shows the threshold-derived verdict. No production call site currently passes `as_json=True` for a judge template (only test files use `as_json=True`, and not alongside `verdict_override`), so this is real but dormant — it would surface the moment any caller (a `--json` CLI flag, a future webhook, or the judge-cycle pipeline reading back its own output) persists a judge review as JSON.

**Verified:** PLAUSIBLE (independent agent confirmed the mechanism but found no live trigger path today).

---

## Review methodology note

Run via the `/code-review` skill at medium effort: 8 independent finder angles (line-by-line scan, removed-behavior audit, cross-file trace, reuse, simplification, efficiency, altitude, CLAUDE.md conventions) each surfacing up to 6 candidates, followed by a 1-vote verification pass per surviving candidate. ~30 raw candidates were produced; 4 survived verification (3 CONFIRMED, 1 PLAUSIBLE). Two candidates were REFUTED and dropped: a claimed CLI judge-review gating gap (refuted — `sq review` has no argument-driven template path; judge templates are unreachable via the CLI today, making the claim moot rather than a live bug) and a claimed empty-string `verdict_override` footgun (refuted — `enforce_judge`'s return type structurally cannot produce an empty string).
