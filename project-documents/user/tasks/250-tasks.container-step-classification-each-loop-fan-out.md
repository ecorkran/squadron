---
docType: tasks
slice: container-step-classification-each-loop-fan-out
project: squadron
lld: user/slices/250-slice.container-step-classification-each-loop-fan-out.md
dependencies:
  - 243-resolution-pre-scan
  - 246-auth-classification-diagnostics-cli
projectState: Slice 246 complete (branch 246-slice.auth-classification-diagnostics-cli). Slice 250 design and review complete. Ready for implementation.
dateCreated: 20260510
dateUpdated: 20260510
status: not_started
---

# Tasks: Container Step Classification (each / loop / fan_out)

## Context Summary

`classify_pipeline` currently skips container step types (`each`, `loop`, `fan_out`) because their
`expand()` returns `[]`. This slice extends the classifier to descend into container inner steps
so that pipelines wrapping model dispatches in containers are classified correctly.

Key changes:
1. Extract `_unpack_inner_steps` from `executor.py` to a shared utility module.
2. Add optional `inner_steps(config)` to `EachStepType`, `LoopStepType`, `FanOutStepType`.
3. Extract `_classify_alias_set` helper from `_classify_pool_step` in `classification.py`.
4. Extend `classify_pipeline` to call `inner_steps()` on container steps and classify results.
5. Add `container_path: str | None` field to `StepClassification`.
6. Update `_render_explain` in `run.py` to show container rows with `↳` indentation.

Files touched:
- `src/squadron/pipeline/steps/utils.py` — new shared utility (extracted from executor)
- `src/squadron/pipeline/executor.py` — import `unpack_inner_steps` from utils
- `src/squadron/pipeline/steps/collection.py` — add `inner_steps()`
- `src/squadron/pipeline/steps/loop.py` — add `inner_steps()`
- `src/squadron/pipeline/steps/fan_out.py` — add `inner_steps()`
- `src/squadron/pipeline/classification.py` — `_classify_alias_set`, extended classifier
- `src/squadron/cli/commands/run.py` — container rendering in `_render_explain`
- `tests/pipeline/test_classification.py` — container classification tests
- `tests/cli/commands/test_run.py` — `--explain` container rendering tests

---

## Tasks

### T1 — Branch setup

- [ ] Verify current branch is `main` or create/switch to `250-slice.container-step-classification-each-loop-fan-out`
  - [ ] `git status` — confirm clean working tree
  - [ ] `git checkout -b 250-slice.container-step-classification-each-loop-fan-out` (or switch if exists)

---

### T2 — Extract `unpack_inner_steps` to shared utility

Extract `_unpack_inner_steps` from `executor.py` into a new `src/squadron/pipeline/steps/utils.py`
module. This removes the circular-import obstacle for step type `inner_steps()` implementations.

- [ ] Create `src/squadron/pipeline/steps/utils.py`:
  - [ ] Copy `_unpack_inner_steps` body from `executor.py:1172` verbatim; name it `unpack_inner_steps` (no leading underscore — it is now a public utility)
  - [ ] Import `StepConfig` from `squadron.pipeline.models`
  - [ ] `__all__ = ["unpack_inner_steps"]`
- [ ] In `executor.py`: replace the local definition with `from squadron.pipeline.steps.utils import unpack_inner_steps`; update all three call sites (`_execute_loop_body`, `_execute_each_step`, `_execute_fan_out_step`) to use the imported name
- [ ] Export `unpack_inner_steps` from `src/squadron/pipeline/steps/__init__.py` `__all__`

#### T2 test

- [ ] Run `uv run pytest tests/pipeline/test_executor.py tests/pipeline/test_executor_loop_body.py -x -q`
  — all executor tests pass (confirms the extracted utility behaves identically)

---

### T3 — Add `inner_steps()` to `EachStepType`

- [ ] In `src/squadron/pipeline/steps/collection.py`:
  - [ ] Add import: `from squadron.pipeline.steps.utils import unpack_inner_steps`
  - [ ] Add method to `EachStepType`:
    ```python
    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        raw = config.config.get("steps", [])
        if not isinstance(raw, list):
            return []
        return unpack_inner_steps([s for s in raw if isinstance(s, dict)])
    ```

#### T3 test

- [ ] In `tests/pipeline/steps/` (or `tests/pipeline/test_step_registry.py` if no dedicated file exists):
  - [ ] Add `TestEachInnerSteps` class with cases:
    - [ ] `test_each_inner_steps_returns_step_configs` — `each` config with one `dispatch` inner step; assert `inner_steps()` returns one `StepConfig` with `step_type="dispatch"`
    - [ ] `test_each_inner_steps_empty_if_no_steps_key` — config without `steps:` key returns `[]`
    - [ ] `test_each_inner_steps_empty_if_steps_not_list` — config with `steps: "bad"` returns `[]`
- [ ] `uv run pytest` on new tests — pass

---

### T4 — Add `inner_steps()` to `LoopStepType`

- [ ] In `src/squadron/pipeline/steps/loop.py`:
  - [ ] Add import: `from squadron.pipeline.steps.utils import unpack_inner_steps`
  - [ ] Add method to `LoopStepType` (identical structure to `EachStepType.inner_steps`):
    ```python
    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        raw = config.config.get("steps", [])
        if not isinstance(raw, list):
            return []
        return unpack_inner_steps([s for s in raw if isinstance(s, dict)])
    ```

#### T4 test

- [ ] Add `TestLoopInnerSteps` alongside T3 tests:
  - [ ] `test_loop_inner_steps_returns_step_configs` — loop config with one `dispatch` inner; assert returns one `StepConfig`
  - [ ] `test_loop_inner_steps_empty_if_no_steps_key`
- [ ] `uv run pytest` on new tests — pass

---

### T5 — Add `inner_steps()` to `FanOutStepType`

`fan_out` returns one synthetic sentinel `StepConfig` encoding the `models:` value. The sentinel's
`step_type` is `"_fan_out_aggregate"` — it is never registered in the step-type registry.

- [ ] In `src/squadron/pipeline/steps/fan_out.py`:
  - [ ] Add import: `from squadron.pipeline.models import StepConfig` (if not already present — check existing imports)
  - [ ] Add method to `FanOutStepType`:
    ```python
    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        return [StepConfig(
            step_type="_fan_out_aggregate",
            name=config.name,
            config={"models": config.config.get("models")},
        )]
    ```

#### T5 test

- [ ] Add `TestFanOutInnerSteps`:
  - [ ] `test_fan_out_inner_steps_returns_sentinel` — fan_out config with `models: [a, b]`; assert returns one `StepConfig` with `step_type="_fan_out_aggregate"` and `config["models"] == ["a", "b"]`
  - [ ] `test_fan_out_inner_steps_pool_ref_preserved` — `models: "pool:review"`; assert sentinel carries `config["models"] == "pool:review"`
- [ ] `uv run pytest` on new tests — pass

---

### T6 — Extract `_classify_alias_set` from `_classify_pool_step`

In `src/squadron/pipeline/classification.py`, extract the SDK/non-SDK/mixed aggregation logic
from `_classify_pool_step` into a standalone helper. `_classify_pool_step` becomes a thin wrapper.

- [ ] Add `_classify_alias_set` above `_classify_pool_step`:
  ```python
  def _classify_alias_set(
      aliases: list[str],
      step: StepConfig,
      step_index: int,
      action_type: str,
      rationale_label: str,
  ) -> StepClassification:
      member_profiles = [resolve_model_alias(alias)[1] for alias in aliases]
      all_non_sdk = all(not is_sdk_profile(p) for p in member_profiles)
      all_sdk = all(is_sdk_profile(p) for p in member_profiles)
      if all_non_sdk:
          classification, rationale = StepClass.NON_SDK, f"{rationale_label}: all non-SDK"
      elif all_sdk:
          classification, rationale = StepClass.SDK_REQUIRED, f"{rationale_label}: all SDK"
      else:
          classification, rationale = StepClass.POOL_UNCERTAIN, f"{rationale_label}: mixed SDK and non-SDK"
      return StepClassification(
          step_name=step.name,
          step_index=step_index,
          action_type=action_type,
          resolved_alias=None,
          resolved_model_id=None,
          profile=None,
          classification=classification,
          rationale=rationale,
      )
  ```
- [ ] Refactor `_classify_pool_step` to call `_classify_alias_set(pool.models, ...)` and attach `pool_name` to the result

#### T6 test

- [ ] Run `uv run pytest tests/pipeline/test_classification.py -x -q` — all existing pool tests pass (regression check on the refactor)

---

### T7 — Add `container_path` field to `StepClassification`

- [ ] In `src/squadron/pipeline/classification.py`, add to `StepClassification` dataclass:
  ```python
  container_path: str | None = None  # inner step label; None for top-level rows
  ```
  Place after `pool_name` (last existing optional field).
- [ ] Confirm existing tests still pass — `container_path` defaults to `None`, so no existing
  construction call needs updating.

#### T7 test

- [ ] `uv run pytest tests/pipeline/test_classification.py -x -q` — all existing tests pass

---

### T8 — Extend `classify_pipeline` to descend into containers

This is the core classifier change. Add `_classify_container_inner` helper and modify the main
step loop.

- [ ] Add `_classify_container_inner` function in `classification.py`:
  - [ ] Signature: `(inner: StepConfig, parent_step: StepConfig, step_index: int, resolver: ModelResolver, pool_backend: PoolBackend | None, classify_params: dict[str, object]) -> list[StepClassification]`
  - [ ] If `inner.step_type == "_fan_out_aggregate"`: handle sentinel (pool ref or literal list)
    - [ ] Pool ref (`models` is a string starting with `"pool:"`): call `_classify_pool_step` and return `[result]`
    - [ ] Literal list (`models` is a list): call `_classify_alias_set(aliases, parent_step, step_index, "dispatch", "fan_out literal list")` and return `[result]`
    - [ ] In both cases, set `container_path="dispatch"` on the returned classification
  - [ ] Otherwise: look up `get_step_type(inner.step_type)` — wrap in `try/except KeyError: continue`-equivalent (return `[]` on unregistered type); expand actions; classify each model-dispatching action using existing logic; set `container_path=inner.name` on each result; return list
  - [ ] Add assertion before `get_step_type()` call: `assert inner.step_type != "_fan_out_aggregate"`

- [ ] Modify the main step loop in `classify_pipeline`:
  - [ ] After `actions = step_impl.expand(step)`, add:
    ```python
    if not actions:
        container_inners = getattr(step_impl, "inner_steps", lambda _: [])(step)
        for inner in container_inners:
            results.extend(_classify_container_inner(inner, step, step_index, resolver, pool_backend, classify_params))
        continue
    ```
  - [ ] Existing action loop is unchanged

#### T8 tests — container classification

Add to `tests/pipeline/test_classification.py` a new section `# --- Container classification (T8) ---`:

- [ ] `test_each_sdk_inner_classifies_as_persistent`:
  - Pipeline with one `each` step; inner dispatch resolves to `sonnet` (SDK)
  - Assert: one `StepClassification` row; `classification == SDK_REQUIRED`; `step_name == "each-0"`; `container_path == "dispatch-0"`
  - Assert: `result.needs_persistent_session == True`

- [ ] `test_each_non_sdk_inner_classifies_as_claude_free`:
  - Inner dispatch resolves to `minimax` (non-SDK)
  - Assert: `classification == NON_SDK`; `result.shape == PipelineShape.CLAUDE_FREE`

- [ ] `test_loop_sdk_inner_classifies_as_persistent`:
  - Pipeline with one `loop` step; inner dispatch resolves to `sonnet`
  - Assert: `classification == SDK_REQUIRED`; `result.needs_persistent_session == True`

- [ ] `test_fan_out_all_sdk_literal_list`:
  - `fan_out` with `models: [sonnet, sonnet]`; assert `classification == SDK_REQUIRED`; `action_type == "dispatch"`

- [ ] `test_fan_out_all_non_sdk_literal_list`:
  - `models: [minimax, minimax]`; assert `classification == NON_SDK`

- [ ] `test_fan_out_mixed_literal_list_is_pool_uncertain`:
  - `models: [sonnet, minimax]`; assert `classification == POOL_UNCERTAIN`

- [ ] `test_fan_out_pool_ref_delegates_to_pool_classify`:
  - `models: "pool:review"` with a mixed pool; assert `classification == POOL_UNCERTAIN`; `pool_name == "review"`

- [ ] `test_container_with_unregistered_inner_step_type_returns_no_rows`:
  - `inner_steps()` returns a `StepConfig` with `step_type="unknown_type"`
  - Assert: `classify_pipeline` returns zero rows (skipped gracefully)

- [ ] `test_top_level_steps_still_classified_alongside_containers`:
  - Pipeline with one `each` (SDK inner) + one top-level `summary` (non-SDK)
  - Assert: two rows total; correct `step_name` attribution on each

- [ ] `uv run pytest tests/pipeline/test_classification.py -x -q` — all pass

---

### T9 — Update `_render_explain` for container rows

In `src/squadron/cli/commands/run.py`:

- [ ] Add container header row (dim style, no classification) for each container step that has inner rows:
  - Before emitting inner rows for a step, emit one row for the container itself with `—` in Alias/Model/Profile/Classification/Rationale columns and a `(container)` label in the Classification column
- [ ] For inner rows (where `container_path is not None`): prefix the Step column value with `  ↳ ` followed by `container_path`
- [ ] Rows where `container_path is None` render unchanged

#### T9 tests — `--explain` rendering

Add to `tests/cli/commands/test_run.py` in `TestExplainCommand`:

- [ ] `test_explain_each_container_shows_indent_prefix`:
  - Mock `classify_pipeline` to return one `StepClassification` with `step_name="each-0"`, `container_path="dispatch-0"`, `classification=SDK_REQUIRED`
  - Invoke `--explain`; assert output contains `↳ dispatch-0`

- [ ] `test_explain_container_header_row_shown`:
  - Same mock; assert output contains the container step name `each-0` as a header row (dim or labeled `(container)`)

- [ ] `test_explain_top_level_row_no_indent`:
  - `StepClassification` with `container_path=None`; assert output does NOT contain `↳`

- [ ] `uv run pytest tests/cli/commands/test_run.py::TestExplainCommand -x -q` — all pass

---

### T10 — Build, format, and full test gate

- [ ] `uv run ruff format src/ tests/`
- [ ] `uv run ruff check src/ tests/` — zero errors
- [ ] `uv run pyright src/` — zero new errors (pre-existing count must not increase)
- [ ] `uv run pytest -x -q` — full suite; confirm 1850+ tests pass; pre-existing failures in `test_compact_compose_integration.py` are the only failures

---

### T11 — Commit

- [ ] `git add` all modified files
- [ ] `git commit` with message: `feat: classify container steps (each/loop/fan_out) in classify_pipeline`

---

### T12 — Slice closeout

- [ ] Update `project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md`:
  - [ ] Set `status: complete`
  - [ ] Update `dateUpdated` to today
- [ ] Update `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md`:
  - [ ] Mark slice 250 entry `[x]` with completion annotation and commit reference
- [ ] Update `project-documents/CHANGELOG.md` with user-facing bullet under `[Unreleased]`
- [ ] Write DEVLOG entry for this session
- [ ] `git add` and commit docs: `docs: mark slice 250 complete; update slice plan, CHANGELOG, DEVLOG`
