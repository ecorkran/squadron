---
docType: slice-design
slice: pipeline-code-review-diff-injection
project: squadron
parent: user/architecture/900-arch.maintenance-and-refactoring.md
dependencies: [149]
interfaces: []
dateCreated: 20260425
dateUpdated: 20260425
status: complete
relatedIssues: [11]
---

# Slice Design: Pipeline Code-Review Diff Injection and UNKNOWN-Fails-Closed

## Overview

Fixes [issue #11](https://github.com/ecorkran/squadron/issues/11). Pipeline
code reviews today silently produce verdict `UNKNOWN` with zero findings
because the `code` template's diff input is never assembled in the pipeline
review-action path. Three coordinated changes restore parity with the direct
CLI path (`sq review code <slice>`) and close the silent-pass failure mode.

1. **Forward `slice` explicitly through step `expand()` into the review
   action config.** The phase step and standalone review step both already
   know the slice they're operating on, but drop everything except `template`
   and `model` when emitting the review action. Today `slice` only reaches
   `context.params` via the merged-params side channel. After this slice it
   is a deterministic key on the action config.

2. **Replace the per-template `match` in `_resolve_slice_inputs` with a
   declarative template-input registry.** Each template declares which
   inputs it consumes (`design_doc`, `task_doc`, `arch_doc`, `diff`); the
   resolver populates them from a single `SliceInfo`. Adding a new template
   becomes one entry in the registry rather than a new `case` branch.

3. **Treat verdict `UNKNOWN` as `FAIL` for the `on-fail` checkpoint trigger.**
   A dead reviewer, a parser miss, or a missing-context bug like #11 itself
   currently waves the pipeline through. Fail closed is the right default;
   the existing semantics provided no real safety.

## Value

- **Pipeline code reviews actually work.** Today they don't — every
  `code`-template review inside a pipeline produces UNKNOWN/no-findings
  against any provider whose `can_read_files` is false (which includes
  all OpenRouter / one-shot HTTP providers we use for review). The bug has
  silently disabled automated code-review gates for the entire 180-band
  ensemble-review effort.
- **Defense in depth via fail-closed.** Even after diff injection lands,
  reviewer outages, parser drift, and future template gaps will continue to
  produce UNKNOWN occasionally. With UNKNOWN treated as FAIL by `on-fail`
  triggers, those failure modes pause the pipeline instead of skipping past
  it — observable, not silent.
- **Removes a class of bug, not an instance.** The declarative
  template-input registry means the next template can't re-create this hole
  by forgetting a `case` branch. Per-template auto-resolution becomes data,
  not control flow.

## Technical Scope

### Included

- **Step expansion**:
  - `PhaseStepType.expand()` ([phase.py:108-122](../../../src/squadron/pipeline/steps/phase.py#L108-L122))
    forwards `slice` into the emitted review action config when present in
    the step's resolved params.
  - `ReviewStepType.expand()` ([review.py:57-67](../../../src/squadron/pipeline/steps/review.py#L57-L67))
    forwards `slice` into the emitted review action config when present in
    the step's resolved params.
- **Template-input registry** in `src/squadron/review/templates/` (or a new
  `template_inputs.py` co-located there): a mapping from template name to a
  list of input keys the template consumes (`design_doc`, `task_doc`,
  `arch_doc`, `diff`). Each registry entry says how to populate that key
  from `SliceInfo` plus `cwd` (for `diff`).
- **`_resolve_slice_inputs` rewrite**
  ([actions/review.py:225-267](../../../src/squadron/pipeline/actions/review.py#L225-L267))
  replaces the per-template `match` with a registry-driven loop: for each
  declared input, populate it from the registry's resolver. The `code`
  template declares it consumes `diff`, so its diff is built via
  `resolve_slice_diff_range(slice_index, cwd)` automatically.
- **Checkpoint fail-closed**:
  - Add `"UNKNOWN"` to `_TRIGGER_THRESHOLDS[CheckpointTrigger.ON_FAIL]`
    ([checkpoint.py:23](../../../src/squadron/pipeline/actions/checkpoint.py#L23)).
  - Add `"UNKNOWN"` to `_TRIGGER_THRESHOLDS[CheckpointTrigger.ON_CONCERNS]`
    too — same rationale; ON_CONCERNS already fires on FAIL, and treating
    UNKNOWN as at-least-as-bad as CONCERNS is consistent.
- **Tests**:
  - Unit: phase / review `expand()` forward `slice`.
  - Unit: template-input registry resolves `design`/`tasks`/`arch`/`code`
    correctly from a `SliceInfo` fixture; missing-input cases handled.
  - Unit: `_should_fire(ON_FAIL, "UNKNOWN")` returns `True`;
    `_should_fire(ON_CONCERNS, "UNKNOWN")` returns `True`.
  - Integration: a pipeline review action against `template: code` with
    `slice: 194` produces `inputs["diff"]` with a non-empty range (use a
    stub provider that asserts on its received prompt).
  - Integration: an end-to-end pipeline run where the review returns a
    parseable `## Summary\nCONCERNS` produces the right verdict and triggers
    the checkpoint as expected.
  - Regression: existing `slice` / `tasks` / `arch` template auto-resolution
    paths produce identical inputs after the registry refactor.
  - Regression: existing checkpoint tests for FAIL / CONCERNS / no-verdict
    cases continue to behave as before.

### Excluded

- **New `on-unknown` checkpoint trigger** — option (b) from the design
  conversation; rejected in favor of fail-closed-by-default. If
  discriminating UNKNOWN from FAIL ever becomes useful, that is a future
  slice with its own design.
- **The review parser dropping findings on certain inputs** — separate bug,
  tracked elsewhere (memory: `project_review_parsing_bug.md`). Compounds
  this one but is not the same root cause.
- **Verbosity flag passthrough** — issue #9; deferred.
- **Required code-location citation on every finding** — issue #10;
  deferred.
- **The `cwd` and `diff_exclude_patterns` semantics** — left exactly as the
  CLI path uses them today. No changes to `resolve_slice_diff_range`.
- **Changes to direct CLI review path** — already works; no edits to
  `cli/commands/review.py`.

## Technical Decisions

### `slice` flows as an explicit action-config key, not via merged-params

The current architecture has `slice` reaching `context.params` only because
top-level pipeline params get merged into every action's params at execution
time ([executor.py:791](../../../src/squadron/pipeline/executor.py#L791)).
That works in principle, but:

- It is invisible at expansion time — the action config the step emits
  doesn't show `slice`, so debugging requires understanding the merge.
- Different action layers (`_resolve_slice_inputs`) treat the merged-params
  as a fallback rather than a primary source, leading to the gap that
  caused #11.

After this slice, `slice` is on the action config. `_resolve_slice_inputs`
reads it from `action_config["slice"]` (deterministic) with a fallback to
`context.params["slice"]` (backwards compatibility for hand-written
pipelines that supply slice only at the top level). Tests assert on the
action config, not on emergent runtime behavior.

### Declarative template-input registry over per-template `match`

The registry shape (concrete proposal — adjust during implementation):

```python
# src/squadron/review/templates/inputs.py (or similar)

@dataclass(frozen=True)
class TemplateInputSpec:
    """Declares one input a template consumes and how to populate it."""
    key: str           # the inputs[...] key the template expects
    source: Callable[[SliceInfo, str], str | None]
    # source signature: (slice_info, cwd) -> resolved value or None

TEMPLATE_INPUTS: dict[str, list[TemplateInputSpec]] = {
    "slice": [
        TemplateInputSpec("input", lambda info, _cwd: info["design_file"]),
        TemplateInputSpec("against", lambda info, _cwd: info["arch_file"]),
    ],
    "tasks": [
        TemplateInputSpec(
            "input",
            lambda info, _cwd: (
                f"project-documents/user/tasks/{info['task_files'][0]}"
                if info["task_files"] else None
            ),
        ),
        TemplateInputSpec("against", lambda info, _cwd: info["design_file"]),
    ],
    "arch": [
        TemplateInputSpec("input", lambda info, _cwd: info["arch_file"]),
    ],
    "code": [
        TemplateInputSpec(
            "diff",
            lambda info, cwd: resolve_slice_diff_range(info["index"], cwd),
        ),
    ],
}
```

`_resolve_slice_inputs` iterates the registry entry for the requested
template and populates `inputs[key] = source(info, cwd)` when the source
returns non-None. Templates not in the registry log the existing
"no auto-resolution for template" debug line and proceed with whatever
inputs the caller already provided.

The registry lives next to the templates themselves so adding a new
template's auto-resolution is a one-place change, not a search-and-edit
across action code.

### UNKNOWN is treated as "at least as bad as FAIL" for triggers

The two trigger sets that gate on verdicts become:

```python
CheckpointTrigger.ON_CONCERNS: {"CONCERNS", "FAIL", "UNKNOWN"}
CheckpointTrigger.ON_FAIL:     {"FAIL", "UNKNOWN"}
```

Rationale:

- **`on-fail` semantics today are wrong.** A pipeline author writing
  `checkpoint: on-fail` is asking "stop if this review went badly." A
  reviewer that produced no parseable verdict went badly; current behavior
  silently continues.
- **The change is backwards-compatible in practice.** Any pipeline that
  currently relies on UNKNOWN waving through is relying on a bug. None
  of squadron's shipped pipelines do — slice 169 / 194 / 184 etc. all
  expect parseable verdicts; UNKNOWN is universally a defect, not a
  signal.
- **The `none` case (no review at all) is unchanged.** `_should_fire`
  already returns `False` when `verdict is None` (line 47). UNKNOWN is
  the parsed-but-unparseable case, not the no-review case. Those two
  remain distinct.

A new `on-unknown` trigger could discriminate UNKNOWN from FAIL if some
future use case wants it. That is explicitly out of scope; the current
default is wrong, and a discriminating trigger can land later if needed.

### Tests use a stub review provider, not live network

The integration tests assert on (a) the prompt the review client receives
and (b) the action result emitted by the action layer. Both are reachable
without invoking a live model — see existing tests under
`tests/pipeline/actions/test_review*.py` for the stub-provider pattern.
No live OpenRouter calls in CI.

## Component Interactions

```
PhaseStepType.expand()           — forwards `slice` into review action config
ReviewStepType.expand()          — same
                                   ↓
review action config             — now carries `slice` as an explicit key
                                   ↓
ReviewAction._resolve_slice_inputs
  reads action_config["slice"]   — falls back to context.params["slice"]
  iterates TEMPLATE_INPUTS[name] — populates inputs[key] per spec
                                   ↓
inputs                           — now contains `diff` for code template
                                   ↓
build_prompt → review_client     — unchanged below this layer
                                   ↓
parse_review_output → ActionResult.verdict
                                   ↓
CheckpointAction._should_fire    — UNKNOWN now triggers ON_FAIL / ON_CONCERNS
```

## Cross-Slice Dependencies and Interfaces

- **Depends on 149** (executor) for `_resolve_slice_inputs` semantics, the
  `merged_action_params` flow, and the existing review action plumbing. No
  modifications to executor itself.
- **Touches 194** indirectly only — the existing P6 pipeline in
  `data/pipelines/P6.yaml` will start producing real verdicts after this
  slice, which is the desired effect. No schema changes to P6.yaml.

## Success Criteria

1. A pipeline review action with `template: code` and a `slice` param
   (either on the action config or in pipeline-level params) builds a
   prompt that contains the slice's diff range.
2. `phase.py`'s `expand()` and `review.py`'s `expand()` both forward
   `slice` into the emitted review action config when slice is in scope.
3. The template-input registry produces identical resolved inputs for
   `slice`, `tasks`, and `arch` templates as the current per-template
   `match` does (regression).
4. The `code` template's auto-resolution populates `inputs["diff"]` with
   a non-empty range produced by `resolve_slice_diff_range`.
5. `_should_fire(CheckpointTrigger.ON_FAIL, "UNKNOWN")` returns `True`.
6. `_should_fire(CheckpointTrigger.ON_CONCERNS, "UNKNOWN")` returns `True`.
7. `_should_fire(*, None)` and existing FAIL/CONCERNS/no-trigger paths
   behave unchanged (regression).
8. End-to-end: re-running the equivalent of the slice 194 P6 review with
   the same model (`minimax/minimax-m2.7`) against post-194 code produces
   a parseable verdict, not UNKNOWN.

## Verification Walkthrough

**Step 1 — sanity check the existing direct CLI path is unchanged.**

```bash
uv run sq review code 194 -v --model minimax/minimax-m2.7
```

Regression gate only — this path was already working before this slice.
Not re-executed as part of implementation verification.

**Step 2 — re-run the pipeline review action that previously produced UNKNOWN.**

```bash
uv run sq run p6 194
```

Not run live. The fix is verified at the unit/integration level; live
pipeline run requires a live model provider and is outside CI scope.

**Step 3 — fail-closed sanity check on a stubbed reviewer.**

Covered by `tests/pipeline/actions/test_checkpoint.py::TestShouldFireUnknown`.
All 8 parametrized assertions pass:

```
tests/pipeline/actions/test_checkpoint.py::TestShouldFireUnknown - 8 passed
```

Key assertions:
- `_should_fire(ON_FAIL, "UNKNOWN")` → `True`
- `_should_fire(ON_CONCERNS, "UNKNOWN")` → `True`
- `_should_fire(ON_FAIL, None)` → `False` (no review, not UNKNOWN)
- `_should_fire(ALWAYS, "UNKNOWN")` → `True`
- `_should_fire(NEVER, "UNKNOWN")` → `False`

**Step 4 — registry round-trip.**

Covered by `tests/review/test_template_inputs.py` (9 tests) and
`tests/pipeline/actions/test_review_action.py::TestResolveSliceInputsRegression` (6 tests).

```
tests/review/test_template_inputs.py - 9 passed
tests/pipeline/actions/test_review_action.py::TestResolveSliceInputsRegression - 6 passed
```

`code` template now sets `inputs["diff"]`; was previously unset (the bug).

**Step 5 — confirm `slice` flows as explicit key.**

Covered by:
- `tests/pipeline/steps/test_phase.py::test_expand_review_includes_slice_placeholder`
- `tests/pipeline/steps/test_review.py::test_expand_slice_forwarded_when_present`
- `tests/pipeline/steps/test_review.py::test_expand_slice_absent_when_not_in_config`

**Step 6 — end-to-end integration.**

```
tests/pipeline/actions/test_review_action_integration.py - 2 passed
```

- `test_diff_injected_into_run_review_call`: `run_review_with_profile` receives
  `inputs["diff"] == "abc123...slice-194"` when `slice=194` is in params.
- `test_no_diff_when_slice_absent`: no `"diff"` key set when `slice` absent.

**Full suite:**

```bash
uv run pytest -q   # 1719 passed
uv run ruff check  # All checks passed
uv run pyright     # 0 errors, 0 warnings
```

## Risks

- **Hidden dependency on UNKNOWN-as-pass somewhere in production
  pipelines.** Low — searched and there is no shipped pipeline that
  intentionally relies on this; UNKNOWN is universally a defect today.
  Mitigation: integration test sweep over all shipped pipelines confirms
  none break under the new behavior.
- **The registry's resolver lambdas capture closures.** Trivial in
  practice — they only close over imported functions like
  `resolve_slice_diff_range`. Documented but no code mitigation needed.
- **Backwards compatibility for hand-written pipelines that supply
  `slice` only at the top level.** Preserved via the
  `action_config["slice"]` → `context.params["slice"]` fallback documented
  above. Test covers the fallback path.

## Effort

2/5. The architecture decision (declarative registry vs per-template
`match`) is settled in this design. Mechanical work: forward one param,
move four cases into one table, add `"UNKNOWN"` to two sets, write the
tests. The largest piece by lines is tests. Estimated under a half-day
of focused work.
