---
docType: review
layer: project
reviewType: code
slice: loop-convergence-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/910-slice.loop-convergence-correctness.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260731
dateUpdated: 20260731
findings:
  - id: F001
    severity: concern
    category: concurrency
    summary: "running_prior key collision can hide prior step's same-type action"
    location: src/squadron/pipeline/executor.py:1328
  - id: F002
    severity: note
    category: error-handling
    summary: "offending_names can list the same inner step multiple times"
    location: src/squadron/pipeline/steps/loop.py:184-188
  - id: F003
    severity: note
    category: testing
    summary: "Hardcoded \"no until\" display string duplicated in code and test"
    location: src/squadron/cli/commands/run.py:986
  - id: F004
    severity: note
    category: docs
    summary: "Comment about \"inner-step validation exists\" is slightly stale"
    location: src/squadron/pipeline/steps/loop.py:178-182
  - id: F005
    severity: note
    category: solid
    summary: "Dry-run output uses utility directly, bypassing LoopStepType's encapsulation"
    location: src/squadron/cli/commands/run.py:993-998
  - id: F006
    severity: pass
    category: correctness
    summary: "Findings-feedback change is well-documented and correctly tested"
    location: src/squadron/pipeline/executor.py:1298-1331
  - id: F007
    severity: pass
    category: error-handling
    summary: "Verdict-count validation provides a clear, actionable error"
    location: src/squadron/pipeline/steps/loop.py:165-209
  - id: F008
    severity: pass
    category: testing
    summary: "Dry-run loop expansion test mirrors production data shape"
    location: tests/cli/commands/test_run.py:402-456
---

# Review: code — slice 910

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Resolution (20260731)

- **F001 (concern, FIXED)** — Confirmed real: `action_index` in the
  `running_prior` key resets to 0 for every inner step's own
  `action_results`, so two different inner steps producing the same
  `action_type` in one iteration (e.g. `dispatch → dispatch → review`)
  collided and silently dropped the first result before the review even
  ran — outside the shape Part B's validation guards (which only counts
  `review`/`gate` actions, not `dispatch`). Fixed by folding the inner
  step's own position into the key:
  `f"{inner_step_index}-{result.action_type}-{action_index}"`
  ([executor.py:1328-1331](src/squadron/pipeline/executor.py#L1328-L1331)).
  Verified the fix is load-bearing, not cosmetic: a new regression test
  (`test_two_inner_steps_same_action_type_do_not_collide_within_iteration`,
  `tests/pipeline/test_executor_loop_body.py`) reproduces the exact
  scenario and was confirmed to fail against the pre-fix key scheme (via
  `git stash`) before passing after.
- **F002 (note, FIXED)** — `offending_names` now appends an inner step's
  name at most once, even if that inner step's `expand()` produces
  multiple verdict-bearing actions
  ([loop.py:190-193](src/squadron/pipeline/steps/loop.py#L190-L193)).
- **F003 (note, FIXED)** — Hoisted the "no until" fallback string to a
  module-level constant `_DRY_RUN_NO_UNTIL_DISPLAY` in `run.py`, matching
  the file's existing `_STATUS_COLORS` convention for centralized display
  values; the CLI test now asserts against the same constant instead of a
  duplicated literal.
- **F004 (note, FIXED)** — Reworded the skip-if-invalid comment in
  `_validate_verdict_count` to state that `_validate_inner_steps` already
  exists and reports shape errors for the inner step, rather than
  implying that validation is future work.
- **F005 (note, ACKNOWLEDGED)** — No action. The design explicitly holds
  Part C to a "no new step-type-specific rendering abstraction" bar; a
  `display_inner_steps()` method on `LoopStepType` is a reasonable future
  refactor if dry-run rendering grows more cases, not a defect in the
  current minimal diff.
- **F006, F007, F008 (pass)** — no action.

## Findings

### [CONCERN] running_prior key collision can hide prior step's same-type action

The accumulator keys each result as `f"{result.action_type}-{action_index}"` where `action_index` resets for each inner step's `action_results`. If a loop body contains two inner steps that both produce the same `action_type` (e.g., two `dispatch:` steps, or an inner step that expands to multiple `review:` actions), the second step's action overwrites the first within the same iteration's `running_prior`. This is rarely a problem in practice (most inner steps produce a single action of a unique type), but the keying scheme is fragile: it loses provenance (which step produced which result) and silently drops information. Consider including the inner-step index in the key, e.g., `f"{inner_step_index}-{result.action_type}-{action_index}"`, so each inner step's results are addressable independently and no overwriting happens within an iteration. The accompanying test does not exercise this case.

### [NOTE] offending_names can list the same inner step multiple times

`offending_names.append(inner.name)` is called for every verdict-bearing action produced by `step_impl.expand(inner)`. If a single inner step produces multiple verdict-bearing actions (e.g., a future `design` step with two inline `review:` fields), the same name appears twice in the error message and the count inflates. The duplicate is cosmetic — the `verdict_count > 1` check still triggers — but the user-facing message reads strangely. Either de-duplicate (e.g., `seen: set[str] = set()` then append only if not seen, or change `verdict_count` to count unique steps) or phrase the message in terms of distinct step names.

### [NOTE] Hardcoded "no until" display string duplicated in code and test

The fallback string `"no until — completes after first iteration"` is defined inline at the call site and asserted verbatim in `tests/cli/commands/test_run.py::test_dry_run_loop_without_until_shows_default_message`. If the wording changes, both must move together, which is a low-grade DRY violation. Promoting it to a module-level constant (e.g., `_NO_UNTIL_DISPLAY = "..."`) keeps the magic string in one place while the test can still pin the exact phrasing. Minor; the string is unlikely to change frequently.

### [NOTE] Comment about "inner-step validation exists" is slightly stale

The skip-if-invalid comment says verdict-counting is skipped "until inner-step validation exists", but inner-step validation does already exist via `_validate_inner_steps`, which is called just above. The skip is intentional — to avoid double-reporting and to keep `expand()` from crashing on configs missing required fields — but the comment's framing ("once inner-step validation exists") reads as if that validation is planned future work. Reword to explain *why* the skip is necessary (avoiding `expand()` crashes on incomplete configs, and letting `_validate_inner_steps` own those errors) rather than implying the validation is missing.

### [NOTE] Dry-run output uses utility directly, bypassing LoopStepType's encapsulation

The CLI now reaches into `step.config.get("steps", [])` and calls `unpack_inner_steps` itself to render inner steps. This works but couples the CLI to the loop config's internal layout (the `steps:` key, the list-of-single-key-dicts convention, and the unpack helper). A `display_inner_steps()` method on `LoopStepType` would let the loop step type own that knowledge and keep the CLI to "render what the step type reports." Not a blocker — the diff is small and the helper is already project-internal — but worth noting for future expansion (e.g., nested loops in nested loops in dry-run output).

### [PASS] Findings-feedback change is well-documented and correctly tested

The `running_prior = dict(prior_outputs)` snapshot plus per-inner-step accumulation is exactly the right shape: a shallow copy at loop entry prevents leaking mutations back to the caller's `prior_outputs`, and the comment explicitly references the canonical `step_prior` snapshot pattern in `_execute_step_once`. The two new executor tests (one asserting the `ActionContext.prior_outputs` contract, one asserting the `DispatchAction._resolve_prompt_from_prior_review` consumer turns that context into the right prompt) close the gap between "data is forwarded" and "data is consumed" — exactly what the slice design's verification walkthrough calls for. The `pyright: ignore[reportPrivateUsage]` is a justified white-box test boundary with an explanatory comment.

### [PASS] Verdict-count validation provides a clear, actionable error

Rejecting >1 verdict-bearing action when `until:` is set fails fast at config-load time and tells the user *exactly* what to do ("Split into sequential loops, one review/gate per loop body"). The skip-if-invalid guard is the right defensive call — `expand()` may require fields that `validate()` would have rejected — and `unpack_inner_steps` is reused rather than duplicated. The `_VERDICT_BEARING_ACTION_TYPES` frozenset is correctly hoisted to module scope. Coverage in both `tests/pipeline/steps/test_loop.py` (direct validator) and `tests/pipeline/test_loop_validation.py` (full `validate_pipeline`) ensures both layers exercise the check, including the inline-review-inside-design expansion case that proves the check inspects expanded actions rather than just step-type names.

### [PASS] Dry-run loop expansion test mirrors production data shape

The new tests use a real-shape config (nested `steps:`, `max`, `until`, `on_exhaust`, and inner steps with the `template:` field reviews actually require). This matches what `loop.py`'s validation accepts, so the test would catch a regression where the dry-run renderer fell out of sync with the validation rules — e.g., if `unpack_inner_steps` gained a new convention the CLI didn't follow. The `with (...)` patch block is idiomatic.
