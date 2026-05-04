---
docType: slice-design
slice: resolution-pre-scan
project: squadron
parent: 240-slices.pipeline-auth-boundary-flexibility.md
dependencies:
  - 241-is-sdk-profile-predicate-re-homing
  - 145-dispatch-action
  - 155-sdk-pipeline-executor
interfaces:
  - PipelineClassification (data)
  - StepClassification (data)
  - classify_pipeline (function)
dateCreated: 20260503
dateUpdated: 20260504
status: complete
reviewIteration: 2
completedCommit: e838898
completedDate: 20260504
---

# Slice Design: Resolution Pre-Scan

## Overview

This slice introduces a pure, side-effect-free pipeline-walking pass
that classifies each model-dispatching step of a `PipelineDefinition`
as `SDK_REQUIRED`, `NON_SDK`, or `POOL_UNCERTAIN`, and aggregates the
per-step results into a `PipelineClassification` value.

The pre-scan is the data foundation for two downstream consumers:

- Slice 244 (Conditional Persistent Session Construction) gates
  `SDKExecutionSession` construction on `needs_persistent_session`
  derived from the classification.
- Slice 246 (Auth-Classification Diagnostics CLI) renders the
  classification as a human-readable report for `sq run --explain`.

This slice ships the classifier and its unit tests only. No executor
behaviour changes — the pre-scan is computed but its output is not yet
acted on. That keeps slice 244's scope to "wire the gate" and lets the
data structure stabilise under unit-test pressure first.

## Problem Statement

The arch document (240, §Envisioned State, point 1) describes a pass
that, for each step that will dispatch a model (`dispatch`, `review`,
`summary`, `compact`), asks the model resolver for `(model_id,
profile)` using the same cascade the action would use at runtime, and
classifies the step. Today no such pass exists — every classification
question is answered ad hoc inside an action's `execute` method, after
the persistent session has already been constructed and connected.

Three concrete properties are required of the pre-scan and are not
provided by any existing code path:

1. **Same resolver, same inputs.** The classification must use the
   *same* `ModelResolver` instance the executor will pass into each
   step's `ActionContext`, with the same `cli_override` (including
   `--param model=…`), `pipeline_model`, and `config_default`. A
   classification that ignored CLI overrides would miss the case the
   initiative was promoted to fix.
2. **No side effects on pool selection.** Pool steps must be classified
   without invoking the pool backend's `select()` method. Selection
   advances 180-band state (round-robin counters, weighted-decay
   telemetry); a pre-scan that triggered selection would alter the
   runtime selection the executor then performs. Classification must
   use only the *static* alias list from `ModelPool.models`.
3. **Per-step granularity.** Slice 244 and slice 246 both consume
   per-step rationale, not just a single pipeline-level boolean.
   Slice 244 needs `(step_name, profile)` to make the
   `needs_persistent_session` decision (which is the union over
   `dispatch`/`summary`/`compact` SDK-resolved steps, *excluding*
   reviews — see arch §Envisioned State point 2). Slice 246 needs the
   full per-step report for its `--explain` output.

## Goals

- Define `StepClassification` and `PipelineClassification` dataclasses
  capturing per-step and pipeline-level results.
- Define `classify_pipeline(definition, resolver, pool_backend) ->
  PipelineClassification` as the single public entry point.
- Classify each model-dispatching step (`dispatch`, `review`,
  `summary`, `compact`) using the per-action cascade key the action
  uses at runtime. Non-model steps (`checkpoint`, `cf-op`, `commit`,
  `devlog`) are skipped (no entry in the report).
- For pool steps, classify using `ModelPool.models` alias list +
  `is_sdk_profile` per alias — never call `pool_backend.select()`.
- Verify, in code comments and test, the side-effect-freeness contract
  the pre-scan relies on (`resolve_model_alias` and
  `ModelResolver.resolve` are pure dict lookups for non-pool inputs;
  `ModelPool.models` is static data).
- Compute the two pipeline-level booleans
  (`needs_persistent_session`, `needs_one_shot_claude`) from per-step
  classifications, exactly as defined in arch §Envisioned State
  point 2. (Slice 244 will *consume* these; this slice produces them.)
- Comprehensive unit-test coverage of the classifier with no executor
  changes.

## Non-Goals

- **No executor wiring.** `_run_pipeline_sdk` does not call
  `classify_pipeline` in this slice. The classification is computed
  in tests only. Slice 244 wires the call site.
- **No conditional session construction.** The persistent session
  still always connects in `_run_pipeline_sdk`. Slice 244 changes that.
- **No `--explain` CLI surface.** Slice 246 builds the diagnostic.
- **No pool selection.** This slice never calls `pool_backend.select()`.
  Pool steps that contain any SDK alias are reported `POOL_UNCERTAIN`
  with the alias-set rationale.
- **No mid-run lazy-construction policy.** Slice 245 layers that on top.
- **No new *selection-performing* resolver entrypoint.** The classifier
  must never invoke `pool_backend.select()`. The arch's "classify,
  don't select" intent is satisfied by adding a side-effect-free
  `ModelResolver.cascade_candidates()` accessor (§7) that returns the
  ordered cascade *inputs*, not a selected output. The
  classification-vs-selection split lives at the call boundary
  (classifier reads candidates, then dispatches non-pool to
  `resolve_model_alias` and pool to a structural inspection of
  `pool.models`).

## Design

### 1. Module placement

New module: `src/squadron/pipeline/classification.py`. Sibling to
`resolver.py`, `executor.py`, `sdk_session.py`. Owns the
classification dataclasses and the `classify_pipeline` function.

Rationale for not putting it in `resolver.py`: classification is a
*consumer* of the resolver, not a resolver concern. The resolver
performs an action-runtime job (returning a single resolved model);
the classifier performs a planning-time job (walking the whole
pipeline). Different responsibilities, different failure modes,
different test surfaces.

### 2. Dataclasses

```python
class StepClass(StrEnum):
    SDK_REQUIRED = "sdk_required"
    NON_SDK = "non_sdk"
    POOL_UNCERTAIN = "pool_uncertain"


@dataclass(frozen=True)
class StepClassification:
    step_name: str
    step_index: int
    action_type: str            # ActionType value, e.g. "dispatch"
    resolved_alias: str | None  # alias name fed to resolver, None if pool/empty
    resolved_model_id: str | None  # None for pool-uncertain
    profile: str | None         # None for pool-uncertain or unset
    classification: StepClass
    rationale: str              # short human string for --explain
    pool_name: str | None = None  # set iff classification == POOL_UNCERTAIN


@dataclass(frozen=True)
class PipelineClassification:
    pipeline_name: str
    steps: tuple[StepClassification, ...]

    @property
    def needs_persistent_session(self) -> bool:
        """True iff at least one dispatch/summary/compact step is
        SDK-resolved or POOL-uncertain (under conservative default).

        Reviews are intentionally excluded — they route through the
        provider registry's one-shot ClaudeSDKAgent, not the
        persistent session.  Arch §Envisioned State point 2.
        """

    @property
    def needs_one_shot_claude(self) -> bool:
        """True iff at least one step routes through the provider
        registry's one-shot ClaudeSDKAgent path with an SDK profile.

        Per arch §Envisioned State point 2, the one-shot path is used
        by:
          - review steps (always route through the provider registry;
            an SDK-resolved review spawns a one-shot ClaudeSDKAgent),
          - and, in principle, dispatch steps that route through
            `_dispatch_via_agent` *and* resolve to an SDK profile.
            After slice 242, the agent path is only taken for non-SDK
            profiles, so this case is empty in practice; included in
            the predicate for correctness against the arch contract.

        Excludes dispatch/summary/compact steps that route through
        the persistent SDKExecutionSession — those drive
        `needs_persistent_session`, not this property.

        Informational; does not gate startup. Slice 246's --explain
        consumes this to tell users "Claude auth required for
        review-only pipelines that resolve to sonnet" without
        misleading them about the persistent session.
        """

    @property
    def shape(self) -> PipelineShape: ...  # CLAUDE_PERSISTENT, CLAUDE_ONE_SHOT, CLAUDE_FREE
```

`PipelineShape` is a `StrEnum` with three values matching arch
terminology: `claude_required_persistent`, `claude_required_one_shot`,
`claude_free`. Slice 246 will render this directly.

The pool-uncertain conservative-vs-lazy policy is layered in slice 245.
This slice defaults to **conservative** (pool-uncertain → treated as
SDK-required for `needs_persistent_session`). Slice 245 will add a
policy parameter.

### 3. Per-action cascade key

`classify_pipeline` walks `definition.steps` and, for each step whose
`step_type` is in `{dispatch, review, summary, compact}`, extracts the
appropriate model-cascade input from the step's `config` dict. The
inputs are:

| Action    | Action-level key | Step-level key | Source                                       |
|-----------|------------------|----------------|----------------------------------------------|
| dispatch  | `model`          | `step_model`   | `step.config.get("model")` / etc.            |
| review    | `model`          | `step_model`   | same                                         |
| summary   | `model` (a.k.a. `summary_model_alias` in code) | `None` | `step.config.get("model")` |
| compact   | `model`          | `None`         | `step.config.get("model")`                   |

The classifier reads these statically from `step.config` (never from
`context.params`, which doesn't exist at planning time — params live
on the run, not on the definition; the resolver's `cli_override`
already encodes `--param model=…`).

### 4. Per-step classification algorithm

```
classify_step(step, resolver, pool_backend) -> StepClassification:
  action_model, step_model = extract_keys(step)

  # Single source of truth: the resolver owns the cascade ordering.
  # cascade_candidates() returns the same tuple resolve() iterates,
  # but as raw inputs (no alias resolution, no pool selection).
  candidate = first_non_none(
      resolver.cascade_candidates(action_model, step_model)
  )

  if candidate is None:
      raise ClassificationError(...)   # arch: misconfigured pipeline
  if candidate.startswith("pool:"):
      return classify_pool_step(candidate, pool_backend)
  model_id, profile = resolve_model_alias(candidate)
  cls = SDK_REQUIRED if profile == "sdk" else NON_SDK
  return StepClassification(..., resolved_model_id=model_id, profile, cls)
```

The classifier deliberately does **not** call `resolver.resolve()`,
because `resolver.resolve()` would invoke `pool_backend.select()` for
pool candidates. Instead the resolver exposes its cascade *inputs* via
`cascade_candidates()` (§7), the classifier picks the first non-None,
and dispatches:

- non-pool candidate → `resolve_model_alias()` (pure dict lookup,
  same as resolver's non-pool path)
- pool candidate → `classify_pool_step()` (structural, see below)

This is the only viable shape: inspecting the cascade winner before
deciding whether to invoke selection is the whole point. The
resolver's `resolve()` already commits to selection by the time the
candidate type is known. Reading the cascade inputs through a
resolver-owned method (rather than reproducing the tuple ordering in
the classifier) keeps the cascade single-source: if a future tier is
added, both `resolve()` and `cascade_candidates()` pick it up
together, so the classifier cannot silently miss it.

### 5. Pool step classification

```
classify_pool_step(candidate: str, backend: PoolBackend) -> StepClassification:
  pool_name = candidate.removeprefix("pool:")
  pool = backend.get_pool(pool_name)   # static definition, no selection
  member_profiles = []
  for alias in pool.models:
      _, profile = resolve_model_alias(alias)
      member_profiles.append(profile)

  if all(not is_sdk_profile(p) for p in member_profiles):
      return NON_SDK with rationale "pool members all non-SDK"
  if all(is_sdk_profile(p) for p in member_profiles):
      return SDK_REQUIRED with rationale "pool members all SDK"
  return POOL_UNCERTAIN with rationale "pool mixes SDK and non-SDK aliases"
```

`PoolBackend.get_pool` is the existing protocol method that returns
the static `ModelPool` definition without selection. `pool.models` is
the alias list. No 180-band selection state is consulted or mutated.

The "all-SDK pool" optimisation (collapse to `SDK_REQUIRED`, not
`POOL_UNCERTAIN`) is included because it strengthens the classification
without ambiguity — there is no runtime decision that could change the
answer. The "all-non-SDK pool" optimisation similarly collapses to
`NON_SDK`. Mixed pools are genuinely uncertain.

### 6. Failure modes

- **Misconfigured step (no model).** Arch §`is_sdk_profile()` predicate
  classification-layer note: pipelines whose steps have no model
  configuration are misconfigured; the classification layer fails
  fast. Concretely: when the cascade yields no candidate (all five
  levels None), the classifier raises `ClassificationError` with the
  step name and the empty-cascade message. This is observable
  (raised before the run starts) and tested.
- **Pool not found.** `backend.get_pool(name)` raises
  `PoolNotFoundError`; the classifier lets this propagate. Caller
  (slice 244 / 246) decides how to surface it. Not swallowed.
- **`resolve_model_alias` raises on bad alias.** Same: propagate. The
  user sees the resolver's existing error.
- **Pool backend not configured but pool candidate present.** The
  classifier requires a pool backend whenever any step's resolved
  candidate begins with `pool:`. If the candidate is non-pool, the
  backend is unused. `classify_pipeline` accepts `pool_backend:
  PoolBackend | None`; if None and a pool candidate is encountered,
  raises `ClassificationError`. (Same posture as
  `ModelPoolNotImplemented` from the resolver, just at planning time.)

All raises happen before any executor work. Per the project rule: no
silent fallbacks; no broad except.

### 7. Resolver cascade exposure (`cascade_candidates`)

Add one method to `ModelResolver` that returns the ordered cascade
*inputs* (raw alias / pool strings), with no alias resolution and no
pool selection:

```python
def cascade_candidates(
    self,
    action_model: str | None = None,
    step_model: str | None = None,
) -> tuple[str | None, ...]:
    """Return the cascade inputs in priority order.

    Mirrors the candidate ordering used by `resolve()` but performs
    no alias resolution and no pool selection. Pure read of the
    resolver's configuration plus the two per-call inputs.

    Used by the classification pre-scan (slice 243) to inspect which
    tier wins *before* deciding whether to invoke pool selection.
    Keeping this in the resolver makes the cascade ordering a single
    source of truth: if a future tier is added, `resolve()` and
    `cascade_candidates()` see it together and the classifier cannot
    silently miss it.
    """
    return (
        self._cli_override,
        action_model,
        step_model,
        self._pipeline_model,
        self._config_default,
    )
```

`resolve()` is refactored in the same change to consume
`cascade_candidates()` internally — replacing its inlined `candidates`
tuple with the call — so the two paths cannot drift. The refactor is
behaviour-preserving: same inputs, same iteration order, same
`first-non-None` selection.

Rationale (responding to slice review F001): the earlier draft
proposed three read-only properties (`cli_override`, `pipeline_model`,
`config_default`) and reproduced the cascade ordering inside the
classifier. That left the cascade in two places and accepted a known
divergence risk under future tier additions. The single
`cascade_candidates()` method is the cleaner shape: classifier reads
candidates, resolver owns the ordering, side-effect-freeness is
explicit in the method's contract. No coupling to classification
semantics is introduced — the method returns raw cascade inputs, not
a classification.

### 8. Verification of side-effect-freeness contract

The slice's correctness rests on three contracts that are external
to the classifier:

- `models/aliases.py:resolve_model_alias` is a pure dict lookup over
  built-in + user aliases. No telemetry, no logging, no cache mutation.
- `pipeline/resolver.py:ModelResolver.cascade_candidates` is a pure
  read of resolver configuration plus the two per-call inputs — no
  alias resolution, no pool selection. (The classifier consumes this
  method, not `resolve()`, precisely so that pool-selection side
  effects cannot occur.)
- `pipeline/resolver.py:ModelResolver.resolve` for non-pool candidates
  delegates to `resolve_model_alias` only; pool candidates trigger
  `_resolve_pool` which calls `pool_backend.select()` — *which the
  classifier never invokes*. (Documented as a contract the classifier
  *does not* depend on, but called out so the resolver's full surface
  is explicit.)
- `ModelPool.models` is static data on the frozen dataclass; reading
  it does not mutate any state.

These are verified by inspection (already done in slice 242's risks
section and arch §Technical Considerations) and re-asserted as a
docstring contract on `classify_pipeline`. A test exercises each of
the three by classifying a pipeline twice with the same resolver
instance and a stateful pool backend recorder, asserting the
recorder observed zero `select()` calls and zero alias-cache
mutations.

If any future change introduces a side effect to one of those three
contracts, the test fails before the regression reaches main.

### Data flow

```
sq run <pipeline> [--param model=…]
  └─ load_pipeline + validate (today)
  └─ build resolver: ModelResolver(cli_override, pipeline_model,
                                   config_default, pool_backend, ...)
  └─ classify_pipeline(definition, resolver, pool_backend)   ← NEW (this slice)
       ├─ for each step in definition.steps:
       │    └─ if step_type in {dispatch, review, summary, compact}:
       │         ├─ extract action_model / step_model from step.config
       │         ├─ resolve cascade (read-only, no pool select)
       │         └─ classify: SDK_REQUIRED | NON_SDK | POOL_UNCERTAIN
       └─ assemble PipelineClassification(steps=tuple(...))

  (this slice ends here — output is computed in tests, not consumed)

  └─ slice 244 will: gate SDKExecutionSession construction on
                      classification.needs_persistent_session
  └─ slice 246 will: render classification.shape and per-step
                      rationale for `sq run --explain`
```

### Performance notes

The pre-scan walks `len(definition.steps)` model-dispatching steps;
each step's classification is one alias lookup (or a small alias-list
walk for pool members). For a pipeline with N steps and pool members
of size M, total cost is O(N + sum-of-pool-Ms) dict lookups. Pipelines
have ~10–30 steps and pools have ~3–5 aliases; the entire pre-scan is
microseconds. No measurable startup cost.

## Cross-Slice Dependencies

- **Slice 241 (`is_sdk_profile` re-homing)** — required. The classifier
  imports `is_sdk_profile` from `squadron.providers.profiles`.
  Complete (`393af52`).
- **Slice 242 (Profile-Aware Dispatch Router pure CLI)** — sibling.
  Slice 242 already inlines the per-step classification logic for
  the dispatch action's runtime routing; this slice does the
  pipeline-level analogue at planning time. The two share
  `is_sdk_profile` and the per-action cascade-key shape.
  Complete (`0dbe41a`, on branch).
- **Slice 244 (Conditional Persistent Session Construction)** —
  consumer. Will call `classify_pipeline` from `_run_pipeline_sdk`
  before constructing `SDKExecutionSession`. Depends on this slice's
  data structures being stable.
- **Slice 246 (Auth-Classification Diagnostics CLI)** — consumer.
  Will render `PipelineClassification` for `sq run --explain`.
- **Slice 245 (Pool-Resolution Classification Policy)** — extends.
  Will add a `policy: ConservativeOrLazy` parameter to
  `classify_pipeline` and adjust how `needs_persistent_session`
  treats `POOL_UNCERTAIN` steps. This slice ships with conservative
  default hard-coded.

No interfaces from other components are changed. New surface only.

## Migration Plan

Not a migration — this is a new module with no prior implementation.
No file moves, no import-site fan-out.

The new `ModelResolver.cascade_candidates()` method is additive.
`resolve()` is refactored in the same change to consume the new
method internally, replacing its inlined `candidates` tuple. Refactor
is behaviour-preserving (same inputs, same iteration order, same
selection); existing resolver tests cover the equivalence.

## Success Criteria

1. `classify_pipeline(definition, resolver, pool_backend)` returns a
   `PipelineClassification` whose `.steps` tuple has one
   `StepClassification` per model-dispatching step in
   `definition.steps`, in pipeline order, with non-model steps
   omitted.
2. For a pipeline with all-default Claude steps,
   `classification.needs_persistent_session` is `True`,
   `classification.shape == claude_required_persistent`.
3. For a pipeline with all `model: minimax` steps,
   `classification.needs_persistent_session` is `False`,
   `classification.needs_one_shot_claude` is `False`,
   `classification.shape == claude_free`.
4. For a review-only pipeline whose reviews all resolve to `sonnet`,
   `classification.needs_persistent_session` is `False`,
   `classification.needs_one_shot_claude` is `True`,
   `classification.shape == claude_required_one_shot`. For a mixed
   pipeline of dispatch-Claude + review-sonnet,
   `needs_persistent_session=True` and `needs_one_shot_claude=True`
   (review uses one-shot path, dispatch uses persistent). For a
   pipeline of dispatch-Claude + review-minimax, `needs_one_shot_claude`
   is `False` (no SDK-resolved review; non-SDK dispatch through the
   one-shot path is empty post-slice-242).
5. CLI override honored: `ModelResolver(cli_override="minimax", ...)`
   classifies a step whose YAML default is Claude as `NON_SDK`.
6. Pool step with all-SDK members → `SDK_REQUIRED`. Pool with all
   non-SDK members → `NON_SDK`. Pool with mixed members →
   `POOL_UNCERTAIN`. None of these invoke `pool_backend.select()`
   (asserted via spy backend).
7. Misconfigured step (cascade yields nothing) raises
   `ClassificationError` with the step name and the offending step's
   index.
8. Pool candidate present but `pool_backend is None` raises
   `ClassificationError` (not `ModelPoolNotImplemented` — different
   layer).
9. Classifying the same pipeline twice with the same resolver and
   pool-backend instances yields identical `PipelineClassification`
   values and zero `select()` calls observed by a spy backend
   (side-effect-freeness regression guard).
10. `ruff format` / `ruff check` / `pyright` clean; full pytest
    suite green; no executor behaviour change observable in any
    existing test (the new module is unimported by `_run_pipeline_sdk`).

## Test Plan

New test module: `tests/pipeline/test_classification.py`. Pure unit
tests against `classify_pipeline`; no executor invocation, no Claude
CLI.

Test fixtures (in `tests/pipeline/conftest.py` or local to the file):

- A `SpyPoolBackend` that wraps `DefaultPoolBackend` and counts
  `select()` calls, recording any pool name + context observed.
- Synthetic `PipelineDefinition` builders for the matrix below
  (avoid loading real YAML; test against the in-memory data shape
  directly).

Test matrix:

- `test_classifies_all_claude_pipeline_as_persistent` — three
  dispatches default-Claude → all `SDK_REQUIRED`,
  `needs_persistent_session`, shape `claude_required_persistent`.
- `test_classifies_all_minimax_pipeline_as_claude_free` — three
  dispatches with `step.config["model"] = "minimax"` → all
  `NON_SDK`, `needs_persistent_session=False`,
  `needs_one_shot_claude=False`, shape `claude_free`.
- `test_classifies_review_only_sdk_as_one_shot` — one review with
  `model: sonnet` → `SDK_REQUIRED`, but `needs_persistent_session=
  False` (reviews don't use the persistent session), shape
  `claude_required_one_shot`.
- `test_classifies_mixed_pipeline_per_step` — dispatch (Claude) +
  dispatch (`minimax`) + review (`sonnet`) → step entries match,
  `needs_persistent_session=True`, `needs_one_shot_claude=True`
  (sonnet review → one-shot path), shape
  `claude_required_persistent`.
- `test_one_shot_excludes_persistent_session_steps` — dispatch
  (Claude) + summary (Claude) only, no reviews →
  `needs_persistent_session=True` but `needs_one_shot_claude=False`
  (those Claude steps go through the persistent session, not the
  one-shot ClaudeSDKAgent path). Direct regression guard for review
  finding F002.
- `test_one_shot_excludes_non_sdk_review` — dispatch (Claude) +
  review (`minimax`) → `needs_one_shot_claude=False` (review is
  non-SDK; persistent dispatch does not contribute to the one-shot
  predicate).
- `test_cli_override_honored_in_classification` —
  `ModelResolver(cli_override="minimax", ...)`, all default-Claude
  YAML → all `NON_SDK`. Regression guard for the motivating defect.
- `test_pool_all_sdk_collapses_to_sdk_required` — pool with members
  `[sonnet, opus]` → `SDK_REQUIRED`, no `select()` calls observed.
- `test_pool_all_non_sdk_collapses_to_non_sdk` — pool with members
  `[minimax, gpt-4o]` → `NON_SDK`, no `select()` calls.
- `test_pool_mixed_classifies_as_pool_uncertain` — pool with members
  `[sonnet, minimax]` → `POOL_UNCERTAIN`, no `select()` calls.
  `pool_name` field populated.
- `test_pool_uncertain_conservative_treats_as_persistent` —
  pool-uncertain step contributes to `needs_persistent_session=True`
  (conservative default for this slice).
- `test_misconfigured_step_raises` — step with no model anywhere in
  cascade → `ClassificationError`.
- `test_pool_without_backend_raises` — pool candidate but
  `pool_backend=None` → `ClassificationError`.
- `test_non_model_steps_skipped` — pipeline with `cf-op` and
  `checkpoint` steps interleaved → those steps absent from
  `classification.steps`.
- `test_classification_is_idempotent_and_side_effect_free` —
  classify twice; assert structural equality and zero
  `select()` calls.
- `test_cascade_candidates_returns_ordered_inputs` — sanity that
  `ModelResolver(cli_override="a", pipeline_model="d",
  config_default="e").cascade_candidates(action_model="b",
  step_model="c")` returns `("a", "b", "c", "d", "e")`. None for
  unspecified positions.
- `test_resolve_consumes_cascade_candidates` — patch
  `cascade_candidates` to return a fixed tuple and assert
  `resolve()` iterates the patched output. Regression guard that
  the two paths cannot drift.
- `test_step_index_matches_definition_order` — three-step pipeline
  with non-model step in the middle; surviving classifications
  carry `step_index = 0` and `step_index = 2` (skipped index 1
  preserved in the index field).

Existing tests unaffected (no executor changes).

## Risks

- **Pool-uncertain conservative-vs-lazy split with slice 245.** This
  slice hard-codes conservative. Slice 245 will introduce a policy
  enum and a parameter. Risk: `PipelineClassification.shape` and
  `needs_persistent_session` may need to become functions instead of
  cached `@property` once policy is parameterised. Mitigation: keep
  the `@property` shape for now; if slice 245 needs runtime policy
  variation, refactor to a `classify(policy=...)` method on the
  result. Cost: one rename in slice 245, no public-API breakage in
  this slice.

## Verification Walkthrough

This slice does not change any user-observable executor behaviour; the
walkthrough is therefore **test-driven**, not behaviour-driven. End-
to-end `sq run` invocations are deferred to slice 244 (when the
classification first gates session construction).

**Step 1 — Run the new test suite.**

```
uv run pytest tests/pipeline/test_classification.py -v
```

Expected: every test in the matrix above passes. ~16 tests, all green.

Actual (20260504): 28 tests, all green. (T1 spy-backend verification adds 3
tests beyond the original matrix count.)

**Step 2 — Spy backend confirms zero pool selections.**

```
uv run pytest tests/pipeline/test_classification.py -v \
  -k "pool or side_effect"
```

Expected: each pool-related test asserts the `SpyPoolBackend`'s
`select_call_count == 0`.

**Step 3 — Quality gates.**

```
uv run ruff format src/ tests/
uv run ruff check src/ tests/
uv run pyright
uv run pytest
```

Expected: clean / green. Full suite passes (no executor changes
reach existing tests; the new module is leaf code).

**Step 4 — Inspect the produced classification by hand (developer
sanity check, not a formal test).**

In a Python REPL inside the project:

```python
from squadron.pipeline.classification import classify_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend

defn = load_pipeline("test-compact-compose")
resolver = ModelResolver(
    cli_override="minimax",
    pipeline_model=defn.model,
    pool_backend=DefaultPoolBackend(),
)
classification = classify_pipeline(defn, resolver, DefaultPoolBackend())
for step in classification.steps:
    print(step.step_name, step.action_type, step.classification, step.rationale)
print("shape:", classification.shape)
print("needs_persistent_session:", classification.needs_persistent_session)
```

Expected: every dispatch / summary step prints `non_sdk` because
`cli_override="minimax"` wins the cascade. `shape == claude_free`
(or `claude_required_one_shot` if the test pipeline has a sonnet
review). This is the same logical decision slice 244 will use to
gate session construction.

**Step 5 — Confirm no executor regression.**

```
uv run sq run test-compact-compose -vv
```

Expected: identical behaviour to today (slice 242 routing applies;
classification is computed nowhere yet). This walkthrough step is a
regression guard against accidental executor wiring inside this
slice.

**Step 6 — Targeted test re-run for the side-effect contract.**

```
uv run pytest tests/pipeline/test_classification.py::test_classification_is_idempotent_and_side_effect_free -v
```

Expected: passes. This is the load-bearing assertion that the
contracts the design relies on still hold.

## Out of Scope (for future slices)

- Calling `classify_pipeline` from `_run_pipeline_sdk` (slice 244).
- The `--explain` CLI surface (slice 246).
- Lazy-mode pool-uncertain handling (slice 245).
- Mid-run session construction (slice 245).
- Process-level adversarial test of "no Claude subprocess for
  Claude-free runs" (slice 248).
