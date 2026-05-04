---
docType: task-breakdown
slice: resolution-pre-scan
project: squadron
lldReference: user/slices/243-slice.resolution-pre-scan.md
dependencies:
  - 241-is-sdk-profile-predicate-re-homing
  - 242-profile-aware-dispatch-router-pure-cli
dateCreated: 20260504
dateUpdated: 20260504
status: complete
---

# Task Breakdown: Resolution Pre-Scan

## Context Summary

This slice introduces `src/squadron/pipeline/classification.py`, a pure
planning-time module that classifies each model-dispatching step of a
`PipelineDefinition` as `SDK_REQUIRED`, `NON_SDK`, or `POOL_UNCERTAIN`.

Two changes are made to `ModelResolver` in `resolver.py`:
1. Add `cascade_candidates(action_model, step_model)` — returns the ordered
   cascade inputs with no alias resolution and no pool selection.
2. Refactor `resolve()` to consume `cascade_candidates()` internally so the
   cascade ordering is single-source.

New test module: `tests/pipeline/test_classification.py` (~16 tests). No
executor wiring in this slice — the classifier is exercised by tests only.

**Branch:** `242-slice.profile-aware-dispatch-router-pure-cli` (extend in
place; 243 ships on a new branch cut from main after 242 merges, or directly
as the next commit on main once 242 is merged).

**Dependencies satisfied:** slice 241 complete (`393af52`), slice 242 complete
(`0dbe41a`, on branch).

---

## Tasks

### T1 — Set up test infrastructure: `SpyPoolBackend` and definition builders

- [x] In `tests/pipeline/test_classification.py` (create new file), add:
  - [x] A `SpyPoolBackend` class that implements the `PoolBackend` protocol
        and records every `select()` call. It must expose
        `select_call_count: int` and delegate `get_pool()` / `list_pools()` /
        `reset_pool_state()` to `DefaultPoolBackend`.
  - [x] A `make_step(step_type, name, config)` helper that constructs a
        `StepConfig` for use in tests. Avoids loading real YAML.
  - [x] A `make_pipeline(steps, model=None)` helper that wraps a step list in
        a `PipelineDefinition`.
  - [x] A `make_resolver(cli_override=None, pipeline_model=None,
        config_default=None, pool_backend=None)` helper producing a
        `ModelResolver`.
- [x] **Success:** `SpyPoolBackend().select_call_count == 0` before any
      calls; `SpyPoolBackend().select(...)` increments it; `get_pool()` returns
      a `ModelPool`.

### T2 — Add `ModelResolver.cascade_candidates()`

- [x] In `src/squadron/pipeline/resolver.py`, add a public method:

  ```python
  def cascade_candidates(
      self,
      action_model: str | None = None,
      step_model: str | None = None,
  ) -> tuple[str | None, ...]:
  ```

  Body returns `(self._cli_override, action_model, step_model,
  self._pipeline_model, self._config_default)`.
  Include the docstring from slice design §7 (side-effect contract,
  single-source rationale).

- [x] Refactor `resolve()` to replace its inlined `candidates` tuple with a
      call to `self.cascade_candidates(action_model, step_model)`. Behaviour
      must be identical — same iteration order, same first-non-None selection.
- [x] **Success criteria:**
  - [x] `ModelResolver("a", pipeline_model="d", config_default="e")
          .cascade_candidates("b", "c") == ("a", "b", "c", "d", "e")`
  - [x] `ModelResolver(pipeline_model="d").cascade_candidates() ==
          (None, None, None, "d", None)`
  - [x] All existing resolver tests pass (`uv run pytest tests/ -k resolver`).

### T3 — Test `cascade_candidates` and resolver refactor

- [x] In `tests/pipeline/test_classification.py`, add:
  - [x] `test_cascade_candidates_returns_ordered_inputs` — assert exact tuple
        output for a fully specified resolver with both per-call args.
  - [x] `test_cascade_candidates_nones_for_unspecified` — assert `None` in
        positions with no value.
  - [x] `test_resolve_consumes_cascade_candidates` — patch
        `ModelResolver.cascade_candidates` to return a fixed tuple (all valid
        non-pool aliases) and assert `resolve()` selects the first non-None
        from that tuple; confirms the two paths are wired together.
- [x] **Success:** all three tests green; full resolver test suite still passes.

### T4 — Define `StepClass`, `PipelineShape`, `StepClassification`, `PipelineClassification`

- [x] Create `src/squadron/pipeline/classification.py`.
- [x] Define `StepClass(StrEnum)` with values `sdk_required`, `non_sdk`,
      `pool_uncertain`.
- [x] Define `PipelineShape(StrEnum)` with values `claude_required_persistent`,
      `claude_required_one_shot`, `claude_free`.
- [x] Define `ClassificationError(Exception)`.
- [x] Define `StepClassification` as a frozen dataclass per slice design §2.
      Fields: `step_name`, `step_index`, `action_type`, `resolved_alias`,
      `resolved_model_id`, `profile`, `classification`, `rationale`,
      `pool_name`.
- [x] Define `PipelineClassification` as a frozen dataclass with `pipeline_name`
      and `steps: tuple[StepClassification, ...]`. Implement three `@property`
      methods per slice design §2:
  - [x] `needs_persistent_session` — true iff any `dispatch` / `summary` /
        `compact` step is `SDK_REQUIRED` or `POOL_UNCERTAIN`.
  - [x] `needs_one_shot_claude` — true iff any `review` step is `SDK_REQUIRED`
        or `POOL_UNCERTAIN` (reviews are the only action that routes through
        the one-shot `ClaudeSDKAgent` path). Dispatch-via-agent with SDK
        profile is empty post-slice-242 but included in the filter for
        arch-correctness.
  - [x] `shape` — derives `PipelineShape` from the two booleans per arch.
- [x] **Success:** `from squadron.pipeline.classification import
        PipelineClassification, StepClassification, StepClass, PipelineShape,
        ClassificationError` imports cleanly; `pyright` 0 errors on the file.

### T5 — Test dataclass properties

- [x] In `tests/pipeline/test_classification.py`, add unit tests for
      `PipelineClassification` properties using hand-constructed
      `StepClassification` lists (no resolver or pipeline walk yet):
  - [x] `test_needs_persistent_session_true_for_sdk_dispatch` — dispatch step
        `SDK_REQUIRED` → `needs_persistent_session=True`.
  - [x] `test_needs_persistent_session_false_for_sdk_review_only` — review step
        `SDK_REQUIRED`, no dispatch/summary/compact steps →
        `needs_persistent_session=False`.
  - [x] `test_needs_one_shot_claude_true_for_sdk_review` — review `SDK_REQUIRED`
        → `needs_one_shot_claude=True`.
  - [x] `test_needs_one_shot_claude_false_for_sdk_dispatch_only` — dispatch
        `SDK_REQUIRED`, no reviews → `needs_one_shot_claude=False`. (Direct F002
        regression guard from review finding.)
  - [x] `test_shape_persistent` — both booleans true → `claude_required_persistent`.
  - [x] `test_shape_one_shot` — `needs_persistent_session=False`,
        `needs_one_shot_claude=True` → `claude_required_one_shot`.
  - [x] `test_shape_free` — both false → `claude_free`.
- [x] **Success:** all 7 property tests green.

### T6 — Implement `classify_pipeline` — non-pool path

- [x] In `classification.py`, implement `classify_pipeline(definition,
      resolver, pool_backend) -> PipelineClassification`.
- [x] Walk `definition.steps`. For each step whose `step_type` is in
      `{dispatch, review, summary, compact}`:
  - [x] Extract `action_model` from `step.config.get("model")` and
        `step_model` from `step.config.get("step_model")` (per the cascade-key
        table in slice design §3).
  - [x] Call `resolver.cascade_candidates(action_model, step_model)` to get
        ordered inputs. Take first non-None as `candidate`.
  - [x] If `candidate` is `None`: raise `ClassificationError` with step name
        and index.
  - [x] If `candidate.startswith("pool:")`: defer to pool path (T7 — leave a
        `raise NotImplementedError` placeholder for now).
  - [x] Otherwise: call `resolve_model_alias(candidate)` → `(model_id, profile)`.
        Classify as `SDK_REQUIRED` if `is_sdk_profile(profile)` else `NON_SDK`.
        Populate `StepClassification` with `rationale` string.
- [x] Skip steps not in the model-dispatching set (no entry produced).
- [x] Return `PipelineClassification(pipeline_name=definition.name, steps=tuple(results))`.
- [x] **Success:** function works for non-pool pipelines; `NotImplementedError`
      raised for any pool step (tested in T7 after pool path is added).

### T7 — Test `classify_pipeline` — non-pool cases

- [x] Add tests exercising the non-pool path:
  - [x] `test_classifies_all_claude_pipeline_as_persistent` — three dispatch
        steps with no model config, `config_default` resolving to a Claude alias
        → all `SDK_REQUIRED`, `needs_persistent_session=True`,
        `shape == claude_required_persistent`.
  - [x] `test_classifies_all_minimax_pipeline_as_claude_free` — three dispatch
        steps with `config["model"] = "minimax"` → all `NON_SDK`,
        `needs_persistent_session=False`, `needs_one_shot_claude=False`,
        `shape == claude_free`.
  - [x] `test_classifies_review_only_sdk_as_one_shot` — one review step with
        Claude alias → `SDK_REQUIRED`, `needs_persistent_session=False`,
        `needs_one_shot_claude=True`, `shape == claude_required_one_shot`.
  - [x] `test_classifies_mixed_pipeline_per_step` — dispatch (Claude) +
        dispatch (minimax) + review (sonnet) → per-step classifications match;
        `needs_persistent_session=True`, `needs_one_shot_claude=True`,
        `shape == claude_required_persistent`.
  - [x] `test_cli_override_honored` — `ModelResolver(cli_override="minimax")`,
        steps with no config → all `NON_SDK` (CLI override wins cascade).
  - [x] `test_non_model_steps_skipped` — `cf-op` and `checkpoint` steps
        interleaved with a dispatch step → only dispatch appears in
        `classification.steps`; `step_index` field reflects original position.
  - [x] `test_misconfigured_step_raises` — step with all cascade levels None →
        `ClassificationError` raised before any other step is processed.
  - [x] `test_step_index_matches_definition_order` — three-step pipeline:
        dispatch (index 0) + cf-op (index 1, skipped) + dispatch (index 2);
        assert `classification.steps[0].step_index == 0` and
        `classification.steps[1].step_index == 2`. Verifies SC1's
        "in pipeline order, non-model steps omitted" requirement.
  - [x] `test_one_shot_excludes_non_sdk_review` — dispatch (Claude, SDK
        profile) + review (minimax, non-SDK) → `needs_one_shot_claude=False`
        (review is non-SDK so does not contribute to one-shot path;
        persistent dispatch does not contribute either). Covers SC4 third
        sub-case.
- [x] **Success:** all 9 tests green; `NotImplementedError` not triggered (no
      pool steps in this batch).

### T8 — Implement `classify_pipeline` — pool path

- [x] Replace the `NotImplementedError` placeholder in `classify_pipeline` with
      the pool classification logic from slice design §5:
  - [x] If `pool_backend is None` when a pool candidate is encountered: raise
        `ClassificationError`.
  - [x] Call `pool_backend.get_pool(pool_name)` → `ModelPool`.
  - [x] Walk `pool.models`; for each alias call `resolve_model_alias(alias)`
        → `(_, profile)` and apply `is_sdk_profile(profile)`.
  - [x] Collapse: all-non-SDK → `NON_SDK`; all-SDK → `SDK_REQUIRED`; mixed →
        `POOL_UNCERTAIN`. Populate `pool_name` field on `StepClassification`.
  - [x] Set `resolved_model_id=None` and `profile=None` for `POOL_UNCERTAIN`
        steps (runtime alias is unknown at planning time).

### T9 — Test `classify_pipeline` — pool cases

- [x] Add pool tests (using `SpyPoolBackend` from T1):
  - [x] `test_pool_all_sdk_collapses_to_sdk_required` — pool with two Claude-alias
        members → `SDK_REQUIRED`; `spy.select_call_count == 0`.
  - [x] `test_pool_all_non_sdk_collapses_to_non_sdk` — pool with two non-SDK alias
        members → `NON_SDK`; zero select calls.
  - [x] `test_pool_mixed_classifies_as_pool_uncertain` — pool with one Claude alias
        and one minimax alias → `POOL_UNCERTAIN`; `pool_name` populated; zero
        select calls.
  - [x] `test_pool_uncertain_conservative_treats_as_persistent` — `POOL_UNCERTAIN`
        dispatch step → `needs_persistent_session=True`.
  - [x] `test_pool_without_backend_raises` — pool candidate, `pool_backend=None`
        → `ClassificationError`.
- [x] **Success:** all 5 tests green; `SpyPoolBackend.select_call_count` is 0 in
      every pool test.

### T10 — Side-effect-freeness regression test

- [x] Add `test_classification_is_idempotent_and_side_effect_free`:
  - [x] Build a pipeline with both non-pool and pool steps.
  - [x] Classify twice with the same `SpyPoolBackend` instance.
  - [x] Assert both results are structurally equal (field-by-field, since
        `PipelineClassification` is a frozen dataclass).
  - [x] Assert `spy.select_call_count == 0` after both calls.
- [x] **Success:** test green; any future side-effect introduction to the pool
      or alias resolution path will break this test.

### T11 — Quality gates and first commit

- [x] Run `uv run ruff format src/ tests/`.
- [x] Run `uv run ruff check src/ tests/` — 0 errors.
- [x] Run `uv run pyright` — 0 errors.
- [x] Run `uv run pytest tests/pipeline/test_classification.py -v` — all tests
      pass (target: ~18 green).
- [x] Run full suite `uv run pytest` — baseline count + ~16 new tests, nothing
      red.
- [x] Verify no executor behaviour change: `uv run sq run test-compact-compose
      -vv` completes identically to slice-242 baseline (classification is not
      wired into the executor in this slice).
- [x] Commit: `feat: add pipeline classification pre-scan (slice 243)`.
  - [x] Stage: `src/squadron/pipeline/classification.py`,
        `src/squadron/pipeline/resolver.py`,
        `tests/pipeline/test_classification.py`.
- [x] **Success:** commit exists; CI gates green (ruff, pyright, pytest).

### T12 — Close out slice

- [x] Mark slice `243-slice.resolution-pre-scan.md` `status: complete` in
      frontmatter and add completion note (commit hash, date).
- [x] Delegate checklist updates to `task-checker` agent: mark T1–T12 complete
      in this file.
- [x] Write DEVLOG Phase 6 entry per `prompt.ai-project.system.md` §Session
      State Summary.
- [x] **Success:** slice design shows `status: complete`; DEVLOG entry written.
