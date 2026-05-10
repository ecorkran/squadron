---
docType: slice-design
slice: container-step-classification-each-loop-fan-out
project: squadron
parent: 240-slices.pipeline-auth-boundary-flexibility.md
dependencies:
  - 243-resolution-pre-scan
  - 246-auth-classification-diagnostics-cli
interfaces:
  - 248-adversarial-test-matrix
dateCreated: 20260510
dateUpdated: 20260510
status: complete
---

# Slice Design: Container Step Classification (each / loop / fan_out)

## Overview

`classify_pipeline` (slice 243) currently calls `StepType.expand()` and classifies each emitted
action. Container step types (`each`, `loop`, `fan_out`) return `[]` from `expand()` — the executor
handles their inner dispatches directly. As a result, any model-dispatching action inside a container
is invisible to the classifier.

This slice extends the classifier to descend into container step types, surfacing their inner
dispatches so that:

1. `sq run --explain` shows a complete picture of what models a container-wrapped pipeline uses.
2. `needs_persistent_session` and `needs_one_shot_claude` are accurate for container-wrapped
   pipelines, and the executor's lazy/strict session decision is based on a complete classification.

No executor logic changes. The fix is entirely in the classification layer and the `--explain`
rendering.

## Value

- **Correctness:** A pipeline that wraps a `sonnet` dispatch inside an `each` loop currently
  classifies as `claude_free`. After this slice it classifies as `claude_required_persistent`, which
  matches executor behavior.
- **Transparency:** `--explain` users see every model-dispatching action, including those inside
  containers, without needing to understand how the executor handles them internally.
- **Completeness blocker:** Slice 248 (adversarial test matrix) explicitly depends on this slice so
  that container-wrapped pipelines are included in the matrix against a complete classifier.

## Technical Scope

**In scope:**
- New protocol method `inner_steps(step: StepConfig) -> list[StepConfig]` on `StepType` with a
  default implementation that returns `[]`.
- Implementations on `EachStepType`, `LoopStepType`, and `FanOutStepType`.
- Classifier (`classify_pipeline`) extended to call `inner_steps()` for any step whose `expand()`
  returns `[]`, then recursively classify the returned inner steps.
- Shared helper `_classify_alias_list` extracted from `_classify_pool_step` to support fan_out's
  literal alias list case.
- `--explain` table rendering updated to indicate container parentage (indent or annotation column).

**Out of scope:**
- Any changes to the executor (`_execute_each_step`, `_execute_loop_body`, `_execute_fan_out_step`).
- Mid-run session construction or pool policy changes.
- Nested containers deeper than one level (each-inside-loop, loop-inside-each). The classifier
  handles one level of descent; recursive descent handles the rest naturally if inner_steps returns
  StepConfig objects the classifier can walk.

## Protocol Addition

Add `inner_steps` to the `StepType` protocol in
[protocol.py](../../src/squadron/pipeline/steps/protocol.py):

```python
def inner_steps(self, config: StepConfig) -> list[StepConfig]:
    """Return inner StepConfig objects for container step types.

    Leaf step types return []. Container step types (each, loop, fan_out)
    return the inner steps whose model dispatches the executor handles
    directly. The classifier walks this list to classify dispatches inside
    containers.

    The returned StepConfig objects must have valid step_type, name, and
    config fields. fan_out returns one synthetic representative step rather
    than N per-branch copies (see design doc §fan_out aggregate semantics).
    """
    ...
```

The protocol is `runtime_checkable`. The default implementation (`[]`) must be provided as a mixin
or concrete base so existing step types do not need updating. The cleanest approach: add the method
directly to the `StepType` protocol with a `...` body (Protocol members have no default), and
provide a concrete default on a `BaseStepType` helper class that all existing types inherit from.
However, since existing step types do not inherit from a common base today, the simpler path is to
**add `inner_steps` as an optional method** checked by `hasattr` in the classifier, rather than
requiring every existing implementation to add it. This avoids a sweeping change across all step
type files.

**Decision:** Use `hasattr(step_impl, "inner_steps")` in the classifier. If the method is absent,
treat the step as having no inner steps (equivalent to returning `[]`). Add the method to
`EachStepType`, `LoopStepType`, and `FanOutStepType` only.

Update the protocol docstring to document `inner_steps` as an optional extension method.

## Implementation: each and loop

Both `EachStepType` and `LoopStepType` store their inner steps under the `steps:` key as a raw
YAML list (list of single-key dicts). The `_unpack_inner_steps` helper in the executor already
converts this format to `list[StepConfig]`. The classifier cannot import from `executor.py` without
creating a circular import, so a local equivalent must be provided, or `_unpack_inner_steps` must
be moved to a shared location.

**Decision:** Extract `_unpack_inner_steps` from `executor.py` to a new
`squadron.pipeline.steps.utils` module (or into `squadron.pipeline.models`). The executor imports
it from the new location. The step type `inner_steps()` implementations import the same utility.
This is a small, mechanical move with no logic change.

### EachStepType.inner_steps

```python
def inner_steps(self, config: StepConfig) -> list[StepConfig]:
    raw = config.config.get("steps", [])
    if not isinstance(raw, list):
        return []
    return unpack_inner_steps([s for s in raw if isinstance(s, dict)])
```

### LoopStepType.inner_steps

Identical structure; the `steps:` key has the same format.

### Container nesting (note)

`each` and `loop` both ban nested loops at validation time. The classifier's depth-first walk will
naturally handle any nesting that validation permits by recursing into `inner_steps()` of each
returned `StepConfig`. No special depth-limit logic is needed.

## Implementation: fan_out

`fan_out` is structurally different: its `models:` field drives model dispatch, not the inner step's
`model:` key. The inner step's action type (always `dispatch`) is fixed, but the resolved model
comes from the branch model list, not from inner step config.

`inner_steps()` for `fan_out` returns **one synthetic representative `StepConfig`** whose config
encodes the aggregate classification intent. The classifier must recognize this synthetic step and
route it through a dedicated path.

### Aggregate alias classification

Extract a shared helper `_classify_alias_set` from `_classify_pool_step`:

```python
def _classify_alias_set(
    aliases: list[str],
    step: StepConfig,
    step_index: int,
    action_type: str,
    label: str,
) -> StepClassification:
    """Classify a set of aliases by walking their profiles.

    Returns NON_SDK (all non-SDK), SDK_REQUIRED (all SDK), or
    POOL_UNCERTAIN (mixed). Used by both pool steps and fan_out literal lists.
    """
    member_profiles = [resolve_model_alias(alias)[1] for alias in aliases]
    all_non_sdk = all(not is_sdk_profile(p) for p in member_profiles)
    all_sdk = all(is_sdk_profile(p) for p in member_profiles)
    if all_non_sdk:
        return StepClassification(..., classification=StepClass.NON_SDK, rationale=f"{label}: all non-SDK")
    if all_sdk:
        return StepClassification(..., classification=StepClass.SDK_REQUIRED, rationale=f"{label}: all SDK")
    return StepClassification(..., classification=StepClass.POOL_UNCERTAIN, rationale=f"{label}: mixed SDK and non-SDK")
```

`_classify_pool_step` is then a thin wrapper that calls `_classify_alias_set(pool.models, ...)`.

### FanOutStepType.inner_steps

Returns a synthetic `StepConfig` with a sentinel step type (e.g. `_fan_out_aggregate`) and the
`models:` value forwarded verbatim. The classifier detects the sentinel step type and handles it
specially rather than looking it up in the registry:

```python
def inner_steps(self, config: StepConfig) -> list[StepConfig]:
    return [StepConfig(
        step_type="_fan_out_aggregate",
        name=config.name,
        config={"models": config.config.get("models")},
    )]
```

The classifier, when it encounters `step_type == "_fan_out_aggregate"`, reads `models:` and:
- If `pool:<name>`: calls `_classify_pool_step` as today.
- If a list of aliases: calls `_classify_alias_set(aliases, ...)`.
- The resulting `StepClassification` carries `action_type="dispatch"` (fan_out always dispatches)
  and the parent `step_name` from the outer fan_out step.

**Alternative considered and rejected:** returning N per-branch synthetic steps. This would require
knowing N at design time (impossible for pool-backed fan_out where N is `n:`) and produces
misleading output ("3 rows all labeled sdk_required" when the user wants "this container uses SDK
models"). The aggregate approach matches the user intent and reuses pool-classification logic.

## Classifier Changes

`classify_pipeline` in [classification.py](../../src/squadron/pipeline/classification.py) currently
contains a comment noting that container step types "contribute no rows." After this slice, the loop
body is:

```
for step_index, step in enumerate(definition.steps):
    step_impl = get_step_type(step.step_type)
    actions = step_impl.expand(step)

    if not actions:
        # Container step: descend into inner steps if the implementation supports it
        container_inners = getattr(step_impl, "inner_steps", lambda _: [])(step)
        for inner in container_inners:
            results.extend(_classify_container_inner(inner, step, step_index, ...))
        continue

    # ... existing action loop unchanged
```

`_classify_container_inner` handles the sentinel `_fan_out_aggregate` case and the normal step case
(call `get_step_type(inner.step_type).expand(inner)` and classify actions as usual, inheriting the
parent's `step_name` and `step_index` for attribution).

### Parent attribution

`StepClassification.step_name` and `step_index` on inner-step classifications refer to the
**container step** (e.g. `"each-0"`, index 0), not the inner step. This matches the --explain table
where the user wants to know "which container step uses SDK models," not the internal step name.

A new optional field `container_path: str | None = None` is added to `StepClassification` to carry
the inner step name when useful (e.g. `"dispatch-0"` inside `each-0`). This field is displayed in
the `--explain` table under a "Container / Step" column but does not affect classification logic.

### Recursion

`_classify_container_inner` is non-recursive in v1. Inner steps of `each` and `loop` are leaf step
types (dispatch, review, summary) or phase steps — none return `[]` from `expand()`. `fan_out`
inners are also always leaf types. No recursive descent is needed for the container types as
currently defined. If a future container type wraps another container, the classifier will see `[]`
from `expand()` and silently produce no rows (the same gap as today for the top-level case); a
follow-up slice can add recursion then.

## --explain Rendering Changes

The Rich table in `_render_explain` ([run.py](../../src/squadron/cli/commands/run.py)) currently has
columns: `Step / Action / Alias / Model ID / Profile / Classification / Rationale`.

After this slice, add one column: **Container** (before Step). For non-container rows, this cell is
empty. For inner-step rows, it shows the container step name (e.g. `each-0`). Step column for inner
rows shows the inner step name from `container_path` if set, or the action type.

Alternatively, use indentation in the Step column (prefix inner rows with `  ↳`) and omit a
separate column. This is visually cleaner and avoids widening the table.

**Decision:** Use the `  ↳ {inner_name}` indent approach in the Step column. The `container_path`
field carries the inner step label. No new column.

Example rendered table for a pipeline with an `each` containing a `sonnet` dispatch:

```
Pipeline: my-pipeline   Shape: Claude-required (persistent)   Policy: lazy

 Step              Action    Alias    Model ID   Profile  Classification  Rationale
 ────────────────  ────────  ───────  ─────────  ───────  ──────────────  ──────────────────────
 each-0            —         —        —          —        (container)     —
   ↳ dispatch-0   dispatch  sonnet   claude-...  sdk      sdk_required    alias 'sonnet' → sdk
 summary-1        summary   minimax  minimax-... non-sdk  non_sdk         alias 'minimax' → non-sdk

Summary: needs_persistent_session=True  needs_one_shot_claude=False
```

The container row itself (with `—` placeholders) is optional. Including it makes the table
self-documenting ("each-0 is a container"). The implementation should include it with a dim style
and no classification.

## Data Flow

```
classify_pipeline(definition, resolver, pool_backend, policy)
  for each top-level step:
    step_impl = get_step_type(step.step_type)
    actions = step_impl.expand(step)
    if actions:
      → classify each action [existing path]
    else:
      inner_configs = getattr(step_impl, "inner_steps", λ_: [])(step)
      for each inner_config:
        if inner_config.step_type == "_fan_out_aggregate":
          → _classify_fan_out_aggregate(inner_config, parent_step, step_index, ...)
        else:
          inner_impl = get_step_type(inner_config.step_type)
          inner_actions = inner_impl.expand(inner_config)
          → classify each inner action [same logic as existing path]
```

## StepClassification Schema Change

```python
@dataclass(frozen=True)
class StepClassification:
    step_name: str           # container step name (e.g. "each-0"), or top-level step name
    step_index: int          # container step index, or top-level step index
    action_type: str
    resolved_alias: str | None
    resolved_model_id: str | None
    profile: str | None
    classification: StepClass
    rationale: str
    pool_name: str | None = None
    container_path: str | None = None   # NEW: inner step label ("dispatch-0"), None for top-level
```

`container_path` is `None` for all existing (non-container) rows, so the schema change is fully
backward-compatible. Callers that don't know about `container_path` will ignore it.

## Cross-Slice Dependencies

### Prerequisites
- **Slice 243 (Resolution Pre-Scan):** `classify_pipeline`, `_classify_pool_step`, `StepClassification`, and all related types. This slice modifies these.
- **Slice 246 (Auth-Classification Diagnostics CLI):** `_render_explain` and `StepClassification` fields are extended. The rendering change is additive (new optional field, new indented rows).

### Interfaces provided to downstream slices
- **Slice 248 (Adversarial Test Matrix):** Consumes the complete classifier after this slice lands.
  Container-wrapped test cases (`each`/`loop`/`fan_out` with SDK, non-SDK, pool, and mixed models)
  are now classifiable and can be included in the matrix.

## Success Criteria

1. `classify_pipeline` returns `StepClassification` rows for model-dispatching actions inside
   `each`, `loop`, and `fan_out` container steps.
2. `needs_persistent_session` is `True` for any pipeline whose container step dispatches to an SDK
   alias; `False` for pipelines whose containers dispatch only to non-SDK aliases.
3. `sq run --explain` renders container-inner rows with the `↳` indent prefix and shows the parent
   container step with a dim "container" row.
4. `fan_out` with a literal alias list classifies as `sdk_required` / `non_sdk` / `pool_uncertain`
   correctly depending on the mix of aliases.
5. `fan_out` with `pool:<name>` classifies using the existing pool logic (unchanged behavior;
   regression-tested).
6. All existing `classify_pipeline` tests pass without modification (backward compatibility of
   `StepClassification` with `container_path=None`).
7. New test matrix: each container type × {SDK inner, non-SDK inner, pool inner, mixed literal list
   (fan_out only), mixed pool (fan_out only)}.

## Verification Walkthrough

These commands can be run after implementation to confirm the slice delivers its claims.

**Setup:** Use any pipeline that wraps a model dispatch in a container. Two minimal fixtures:

*each_pipeline.yaml* — an `each` step whose inner dispatch resolves to `sonnet` (SDK):
```yaml
name: each-sdk-test
steps:
  - each:
      name: each-0
      source: cf.unfinished_slices()
      as: slice
      steps:
        - dispatch:
            name: dispatch-0
            model: sonnet
            template: P1
```

*fan_out_pipeline.yaml* — a `fan_out` with a literal alias list mixing SDK and non-SDK:
```yaml
name: fan-out-mixed
steps:
  - fan_out:
      name: fan-0
      models: [sonnet, minimax]
      inner:
        dispatch:
          name: inner-dispatch
          template: P1
      fan_in: collect
```

**Step 1 — Verify each pipeline explains correctly:**
```bash
uv run sq run --explain each_pipeline.yaml
```
Expected: table shows `each-0` (dim container row) + `  ↳ dispatch-0 | dispatch | sonnet | ... | sdk_required`. Shape: `Claude-required (persistent)`.

**Step 2 — Verify fan_out mixed literal list:**
```bash
uv run sq run --explain fan_out_pipeline.yaml
```
Expected: `fan-0` (dim container row) + `  ↳ dispatch | dispatch | — | — | pool_uncertain` (or equivalent mixed row). Shape: `Claude-required (persistent)` (since LAZY default treats uncertain as possibly SDK and reports shape truthfully).

Actually: for a literal list `[sonnet, minimax]`, classification is `pool_uncertain` (mixed). Shape under LAZY is computed by `needs_persistent_session` — which under LAZY only counts `SDK_REQUIRED`, so a `pool_uncertain` inner would leave `needs_persistent_session=False`. This is the **same semantics as pool steps** — fan_out with mixed aliases is uncertain until runtime.

To confirm strict-mode forces the session:
```bash
uv run sq run --explain fan_out_pipeline.yaml --strict
```
Expected: Shape `Claude-required (persistent)` (strict counts `pool_uncertain` as SDK).

**Step 3 — Verify non-SDK-only each pipeline stays claude_free:**
Change the each pipeline dispatch to `model: minimax` (non-SDK). Re-run `--explain`.
Expected: Shape `Claude-free`.

**Step 4 — Regression: existing top-level dispatch still renders correctly:**
```bash
uv run sq run --explain p4
```
Expected: same output as before this slice (three rows: design-0/dispatch, design-0/review, summary-1). No regressions.

**Step 5 — Unit test gate:**
```bash
uv run pytest tests/pipeline/test_classification.py -v
```
All existing tests pass. New container-classification tests pass.

## Failure Mode Enumeration

Each new code path in `classify_pipeline` introduced by this slice has an explicit handling strategy.

### `inner_steps()` raises on malformed config

**Path:** `getattr(step_impl, "inner_steps", lambda _: [])(step)`

**Modes:** `inner_steps()` raises `KeyError`, `ValueError`, or `TypeError` if the step config is
malformed (e.g., `each` step missing `steps:` key, `loop` step with non-list `steps:` value).

**Strategy:** Propagate. `classify_pipeline` already propagates expansion errors from `expand()` —
the same contract applies to `inner_steps()`. Callers are expected to call `validate_pipeline`
before `classify_pipeline`; a validated pipeline will never produce a malformed `inner_steps()`.
This is an intentional fail-fast decision, documented here. Observable: caller receives an
exception with a traceback that identifies the step and the malformed key. No silent empty result.

### Sentinel `_fan_out_aggregate` step type escapes the guard

**Path:** `_classify_container_inner` checks `inner.step_type == "_fan_out_aggregate"` before
calling `get_step_type()`.

**Mode:** If the sentinel check is removed or bypassed, `get_step_type("_fan_out_aggregate")` fails
with `KeyError` (sentinel is never registered). This is the correct behavior — it surfaces the bug
rather than producing wrong output.

**Strategy:** The sentinel is an internal classifier artifact. Enforce its scope with an assertion
rather than relying on a comment:

```python
assert inner.step_type != "_fan_out_aggregate", (
    "_fan_out_aggregate sentinel must be handled before get_step_type()"
)
```

placed immediately before the `get_step_type(inner.step_type)` call. Assertion failure is
observable and identifies the exact invariant that was violated. Observable: `AssertionError` in
tests; `KeyError` in production if assertions are disabled (still surfaces, just later).

### Inner step type not registered

**Path:** `get_step_type(inner.step_type)` on a step returned by `EachStepType.inner_steps()` or
`LoopStepType.inner_steps()`.

**Mode:** If `inner_steps()` returns a `StepConfig` with an unrecognized `step_type`, `get_step_type`
raises `KeyError`. This can only happen if the inner step list contains a step type that hasn't been
registered (i.e., a step type the validator doesn't recognize either).

**Strategy:** Propagate. Same contract as the top-level loop's `get_step_type(step.step_type)` call
(currently, an unregistered top-level step type causes `classify_pipeline` to skip the step with a
`continue` — see the `except KeyError: continue` guard). Apply the same guard for inner steps:
skip unregistered inner step types with a `continue`. This mirrors the existing behavior exactly.
Observable: no rows for that inner step (same as today for an unregistered top-level step).

### `unpack_inner_steps` returns empty or unexpected output

**Path:** `unpack_inner_steps(raw_list)` called from `inner_steps()` implementations.

**Mode:** If the raw step list contains malformed entries (non-dict items, dicts with more than one
key), `_unpack_inner_steps` skips them silently. This is existing behavior inherited from the
executor.

**Strategy:** Accept the inherited behavior. Malformed inner-step lists are caught by `validate_pipeline`
before classification runs. The empty-result case (all entries skipped) produces no inner-step
classification rows for the container — incomplete but not wrong. Observable: `--explain` output
will show the container row with no indented children, which is a visible signal that something is
missing. No silent total failure.

### `hasattr` finds `inner_steps` with an incompatible signature (F002)

**Path:** `getattr(step_impl, "inner_steps", lambda _: [])(step)` — if a step type has an
`inner_steps` attribute that is not callable or has a different signature, the call fails.

**Strategy:** The type-narrowing available at call time is `hasattr`, not signature inspection.
Accept that a signature mismatch surfaces as a `TypeError` at runtime, which is observable and
diagnosable from the traceback. To reduce ambiguity: name the parameter `config: StepConfig`
consistently in all three implementations, and document the expected signature in the protocol
docstring. This does not prevent the failure but makes the expected interface unambiguous.

## Risk Notes

- **`_unpack_inner_steps` extraction:** Moving this utility out of `executor.py` is mechanical but
  touches import paths. Run the full test suite after the move; executor tests are the primary
  regression signal.
- **Sentinel step type `_fan_out_aggregate`:** Enforced by assertion immediately before `get_step_type()`
  in `_classify_container_inner`. Never registered in the step-type registry.

Effort: 3/5. Dependencies: [243, 246].
