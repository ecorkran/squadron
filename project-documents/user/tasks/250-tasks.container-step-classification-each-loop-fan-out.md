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
status: complete
dateUpdated: 20260510
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

- [x] Verify current branch is `main` or create/switch to `250-slice.container-step-classification-each-loop-fan-out`
  - [x] `git status` — confirm clean working tree
  - [x] `git checkout -b 250-slice.container-step-classification-each-loop-fan-out` (or switch if exists)

---

### T2 — Extract `unpack_inner_steps` to shared utility

Extract `_unpack_inner_steps` from `executor.py` into a new `src/squadron/pipeline/steps/utils.py`
module. This removes the circular-import obstacle for step type `inner_steps()` implementations.

- [x] Create `src/squadron/pipeline/steps/utils.py`:
  - [x] Copy `_unpack_inner_steps` body from `executor.py:1172` verbatim; name it `unpack_inner_steps` (no leading underscore — it is now a public utility)
  - [x] Import `StepConfig` from `squadron.pipeline.models`
  - [x] `__all__ = ["unpack_inner_steps"]`
- [x] In `executor.py`: replace the local definition with `from squadron.pipeline.steps.utils import unpack_inner_steps`; update all three call sites (`_execute_loop_body`, `_execute_each_step`, `_execute_fan_out_step`) to use the imported name
- [x] Export `unpack_inner_steps` from `src/squadron/pipeline/steps/__init__.py` `__all__`

#### T2 test

- [x] Run `uv run pytest tests/pipeline/test_executor.py tests/pipeline/test_executor_loop_body.py -x -q`
  — all executor tests pass (confirms the extracted utility behaves identically)

---

### T3 — Add `inner_steps()` to `EachStepType`

- [x] In `src/squadron/pipeline/steps/collection.py`:
  - [x] Add import: `from squadron.pipeline.steps.utils import unpack_inner_steps`
  - [x] Add method to `EachStepType`:
    ```python
    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        raw = config.config.get("steps", [])
        if not isinstance(raw, list):
            return []
        return unpack_inner_steps([s for s in raw if isinstance(s, dict)])
    ```

#### T3 test

- [x] In `tests/pipeline/steps/` (or `tests/pipeline/test_step_registry.py` if no dedicated file exists):
  - [x] Add `TestEachInnerSteps` class with cases:
    - [x] `test_each_inner_steps_returns_step_configs` — `each` config with one `dispatch` inner step; assert `inner_steps()` returns one `StepConfig` with `step_type="dispatch"`
    - [x] `test_each_inner_steps_empty_if_no_steps_key` — config without `steps:` key returns `[]`
    - [x] `test_each_inner_steps_empty_if_steps_not_list` — config with `steps: "bad"` returns `[]`
- [x] `uv run pytest` on new tests — pass

---

### T4 — Add `inner_steps()` to `LoopStepType`

- [x] In `src/squadron/pipeline/steps/loop.py`:
  - [x] Add import: `from squadron.pipeline.steps.utils import unpack_inner_steps`
  - [x] Add method to `LoopStepType` (identical structure to `EachStepType.inner_steps`):
    ```python
    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        raw = config.config.get("steps", [])
        if not isinstance(raw, list):
            return []
        return unpack_inner_steps([s for s in raw if isinstance(s, dict)])
    ```

#### T4 test

- [x] Add `TestLoopInnerSteps` alongside T3 tests:
  - [x] `test_loop_inner_steps_returns_step_configs` — loop config with one `dispatch` inner; assert returns one `StepConfig`
  - [x] `test_loop_inner_steps_empty_if_no_steps_key`
- [x] `uv run pytest` on new tests — pass

---

### T5 — Add `inner_steps()` to `FanOutStepType`

`fan_out` returns one synthetic sentinel `StepConfig` encoding the `models:` value. The sentinel's
`step_type` is `"_fan_out_aggregate"` — it is never registered in the step-type registry.

- [x] In `src/squadron/pipeline/steps/fan_out.py`:
  - [x] Add import: `from squadron.pipeline.models import StepConfig` (if not already present — check existing imports)
  - [x] Add method to `FanOutStepType`:
    ```python
    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        return [StepConfig(
            step_type="_fan_out_aggregate",
            name=config.name,
            config={"models": config.config.get("models")},
        )]
    ```

#### T5 test

- [x] Add `TestFanOutInnerSteps`:
  - [x] `test_fan_out_inner_steps_returns_sentinel` — fan_out config with `models: [a, b]`; assert returns one `StepConfig` with `step_type="_fan_out_aggregate"` and `config["models"] == ["a", "b"]`
  - [x] `test_fan_out_inner_steps_pool_ref_preserved` — `models: "pool:review"`; assert sentinel carries `config["models"] == "pool:review"`
- [x] `uv run pytest` on new tests — pass

---

### T6 — Extract `_classify_alias_set` from `_classify_pool_step`

In `src/squadron/pipeline/classification.py`, extract the SDK/non-SDK/mixed aggregation logic
from `_classify_pool_step` into a standalone helper. `_classify_pool_step` becomes a thin wrapper.

- [x] Add `_classify_alias_set` above `_classify_pool_step`:
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
- [x] Refactor `_classify_pool_step` to call `_classify_alias_set(pool.models, ...)` and attach `pool_name` to the result

#### T6 test

- [x] Run `uv run pytest tests/pipeline/test_classification.py -x -q` — all existing pool tests pass (regression check on the refactor)

---

### T7 — Add `container_path` field to `StepClassification`

- [x] In `src/squadron/pipeline/classification.py`, add to `StepClassification` dataclass:
  ```python
  container_path: str | None = None  # inner step label; None for top-level rows
  ```
  Place after `pool_name` (last existing optional field).
- [x] Confirm existing tests still pass — `container_path` defaults to `None`, so no existing
  construction call needs updating.

#### T7 test

- [x] `uv run pytest tests/pipeline/test_classification.py -x -q` — all existing tests pass

---

### T8 — Extend `classify_pipeline` to descend into containers

This is the core classifier change. Add `_classify_container_inner` helper and modify the main
step loop.

- [x] Add `_classify_container_inner` function in `classification.py`:
  - [x] Signature: `(inner: StepConfig, parent_step: StepConfig, step_index: int, resolver: ModelResolver, pool_backend: PoolBackend | None, classify_params: dict[str, object]) -> list[StepClassification]`
  - [x] If `inner.step_type == "_fan_out_aggregate"`: handle sentinel (pool ref or literal list)
    - [x] Pool ref (`models` is a string starting with `"pool:"`): call `_classify_pool_step` and return `[result]`
    - [x] Literal list (`models` is a list): call `_classify_alias_set(aliases, parent_step, step_index, "dispatch", "fan_out literal list")` and return `[result]`
    - [x] In both cases, set `container_path="dispatch"` on the returned classification
  - [x] Otherwise: look up `get_step_type(inner.step_type)` — wrap in `try/except KeyError: continue`-equivalent (return `[]` on unregistered type); expand actions; classify each model-dispatching action using existing logic; set `container_path=inner.name` on each result; return list
  - [x] Add assertion before `get_step_type()` call: `assert inner.step_type != "_fan_out_aggregate"`

- [x] Modify the main step loop in `classify_pipeline`:
  - [x] After `actions = step_impl.expand(step)`, add:
    ```python
    if not actions:
        container_inners = getattr(step_impl, "inner_steps", lambda _: [])(step)
        for inner in container_inners:
            results.extend(_classify_container_inner(inner, step, step_index, resolver, pool_backend, classify_params))
        continue
    ```
  - [x] Existing action loop is unchanged

#### T8 tests — container classification

Add to `tests/pipeline/test_classification.py` a new section `# --- Container classification (T8) ---`:

- [x] `test_each_sdk_inner_classifies_as_persistent`:
  - Pipeline with one `each` step; inner dispatch resolves to `sonnet` (SDK)
  - Assert: one `StepClassification` row; `classification == SDK_REQUIRED`; `step_name == "each-0"`; `container_path == "dispatch-0"`
  - Assert: `result.needs_persistent_session == True`

- [x] `test_each_non_sdk_inner_classifies_as_claude_free`:
  - Inner dispatch resolves to `minimax` (non-SDK)
  - Assert: `classification == NON_SDK`; `result.shape == PipelineShape.CLAUDE_FREE`

- [x] `test_loop_sdk_inner_classifies_as_persistent`:
  - Pipeline with one `loop` step; inner dispatch resolves to `sonnet`
  - Assert: `classification == SDK_REQUIRED`; `result.needs_persistent_session == True`

- [x] `test_fan_out_all_sdk_literal_list`:
  - `fan_out` with `models: [sonnet, sonnet]`; assert `classification == SDK_REQUIRED`; `action_type == "dispatch"`

- [x] `test_fan_out_all_non_sdk_literal_list`:
  - `models: [minimax, minimax]`; assert `classification == NON_SDK`

- [x] `test_fan_out_mixed_literal_list_is_pool_uncertain`:
  - `models: [sonnet, minimax]`; assert `classification == POOL_UNCERTAIN`

- [x] `test_fan_out_pool_ref_delegates_to_pool_classify`:
  - `models: "pool:review"` with a mixed pool; assert `classification == POOL_UNCERTAIN`; `pool_name == "review"`

- [x] `test_container_with_unregistered_inner_step_type_returns_no_rows`:
  - `inner_steps()` returns a `StepConfig` with `step_type="unknown_type"`
  - Assert: `classify_pipeline` returns zero rows (skipped gracefully)

- [x] `test_top_level_steps_still_classified_alongside_containers`:
  - Pipeline with one `each` (SDK inner) + one top-level `summary` (non-SDK)
  - Assert: two rows total; correct `step_name` attribution on each

- [x] `uv run pytest tests/pipeline/test_classification.py -x -q` — all pass

---

### T9 — Update `_render_explain` for container rows

In `src/squadron/cli/commands/run.py`:

- [x] Add container header row (dim style, no classification) for each container step that has inner rows:
  - Before emitting inner rows for a step, emit one row for the container itself with `—` in Alias/Model/Profile/Classification/Rationale columns and a `(container)` label in the Classification column
- [x] For inner rows (where `container_path is not None`): prefix the Step column value with `  ↳ ` followed by `container_path`
- [x] Rows where `container_path is None` render unchanged

#### T9 tests — `--explain` rendering

Add to `tests/cli/commands/test_run.py` in `TestExplainCommand`:

- [x] `test_explain_each_container_shows_indent_prefix`:
  - Mock `classify_pipeline` to return one `StepClassification` with `step_name="each-0"`, `container_path="dispatch-0"`, `classification=SDK_REQUIRED`
  - Invoke `--explain`; assert output contains `↳ dispatch-0`

- [x] `test_explain_container_header_row_shown`:
  - Same mock; assert output contains the container step name `each-0` as a header row (dim or labeled `(container)`)

- [x] `test_explain_top_level_row_no_indent`:
  - `StepClassification` with `container_path=None`; assert output does NOT contain `↳`

- [x] `uv run pytest tests/cli/commands/test_run.py::TestExplainCommand -x -q` — all pass

---

### T10 — Build, format, and full test gate

- [x] `uv run ruff format src/ tests/`
- [x] `uv run ruff check src/ tests/` — zero errors
- [x] `uv run pyright src/` — zero new errors (pre-existing count must not increase)
- [x] `uv run pytest -x -q` — full suite; confirm 1850+ tests pass; pre-existing failures in `test_compact_compose_integration.py` are the only failures

---

### T11 — Commit

- [x] `git add` all modified files
- [x] `git commit` with message: `feat: classify container steps (each/loop/fan_out) in classify_pipeline`

---

### T12 — Slice closeout

- [x] Update `project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md`:
  - [x] Set `status: complete`
  - [x] Update `dateUpdated` to today
- [x] Update `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md`:
  - [x] Mark slice 250 entry `[x]` with completion annotation and commit reference
- [x] Update `project-documents/CHANGELOG.md` with user-facing bullet under `[Unreleased]`
- [x] Write DEVLOG entry for this session
- [x] `git add` and commit docs: `docs: mark slice 250 complete; update slice plan, CHANGELOG, DEVLOG`
