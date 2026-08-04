---
docType: tasks
sliceIndex: 142
sliceName: pipeline-core-models-and-action-protocol
project: squadron
sliceDesign: user/slices/142-slice.pipeline-core-models-and-action-protocol.md
architecture: user/architecture/140-arch.pipeline-foundation.md
dependencies: [100-band complete, slice 141 complete]
dateCreated: 20260330
dateUpdated: 20260330
status: complete
---

# Task Breakdown: Pipeline Core Models and Action Protocol (142)

## Context Summary

Creates `src/squadron/pipeline/` — the foundational scaffolding for the
pipeline system.  Nothing executes yet.  Deliverables: data models
(`ActionContext`, `ActionResult`, `PipelineDefinition`, `StepConfig`,
`ValidationError`), `Action` and `StepType` protocols, action and step-type
registries, `ModelResolver` with 5-level cascade chain, and stub modules for
all future action/step-type files.  All tests under `tests/pipeline/`.

**Branch:** `142-pipeline-core-models-and-action-protocol`

---

## Tasks

### T1 — Create branch and package skeleton

- [x] Verify current branch is `main`: `git status`
- [x] Create and switch to slice branch:
  `git checkout -b 142-pipeline-core-models-and-action-protocol`
- [x] Create directory tree (all empty `__init__.py` files):
  - `src/squadron/pipeline/__init__.py`
  - `src/squadron/pipeline/actions/__init__.py`
  - `src/squadron/pipeline/steps/__init__.py`
- [x] Create stub action modules (docstring + `# TODO: slice NNN`):
  - `src/squadron/pipeline/actions/dispatch.py` (slice 145)
  - `src/squadron/pipeline/actions/review.py` (slice 146)
  - `src/squadron/pipeline/actions/compact.py` (slice 147)
  - `src/squadron/pipeline/actions/checkpoint.py` (slice 146)
  - `src/squadron/pipeline/actions/cf_op.py` (slice 144)
  - `src/squadron/pipeline/actions/commit.py` (slice 144)
  - `src/squadron/pipeline/actions/devlog.py` (slice 144)
- [x] Create stub step-type modules (docstring + `# TODO: slice NNN`):
  - `src/squadron/pipeline/steps/phase.py` (slice 147)
  - `src/squadron/pipeline/steps/compact.py` (slice 147)
  - `src/squadron/pipeline/steps/review.py` (slice 147)
  - `src/squadron/pipeline/steps/collection.py` (slice 149)
  - `src/squadron/pipeline/steps/devlog.py` (slice 147)
- [x] Confirm `uv run python -c "import squadron.pipeline"` succeeds with no
  errors

### T2 — Implement `pipeline/models.py`

- [x] Create `src/squadron/pipeline/models.py` with the following dataclasses
  (all use `@dataclass`, `from __future__ import annotations`, no Pydantic):
  - `ValidationError(field, message, action_type)` — all `str`
  - `ActionContext(pipeline_name, run_id, params, step_name, step_index,
    prior_outputs, resolver, cf_client, cwd)` — see slice design for types;
    `resolver` is forward-referenced as `"ModelResolver"`;
    `cf_client` typed as `object`
  - `ActionResult(success, action_type, outputs, error, metadata, verdict,
    findings)` — `success: bool`, `outputs: dict[str, object]`,
    `error: str | None = None`, `metadata` and `findings` use
    `field(default_factory=...)`, `verdict: str | None = None`
  - `StepConfig(step_type, name, config)` — all `str`/`dict[str, object]`
  - `PipelineDefinition(name, description, params, steps, model)` —
    `steps: list[StepConfig]`, `model: str | None = None`
- [x] Verify pyright: `uv run pyright src/squadron/pipeline/models.py`

### T3 — Test `pipeline/models.py`

- [x] Create `tests/pipeline/__init__.py` (empty)
- [x] Create `tests/pipeline/test_models.py` with:
  - [x] `test_validation_error_fields` — construct `ValidationError`, check
    `field`, `message`, `action_type`
  - [x] `test_action_result_defaults` — `ActionResult(success=True,
    action_type="test", outputs={})` → `error` is None, `verdict` is None,
    `findings` is `[]`, `metadata` is `{}`
  - [x] `test_action_result_failure` — construct with `success=False`,
    `error="oops"`, verify attributes
  - [x] `test_step_config_fields` — construct `StepConfig`, verify all fields
  - [x] `test_pipeline_definition_model_default` — `PipelineDefinition` with
    no `model` arg → `model` is None
  - [x] `test_pipeline_definition_with_model` — pass `model="sonnet"`, verify
- [x] Run: `uv run pytest tests/pipeline/test_models.py -v` — all pass
- [x] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add pipeline package skeleton and core data models`

---

### T4 — Implement `Action` protocol and `ActionType` enum

- [x] Create `src/squadron/pipeline/actions/protocol.py`:
  - [x] Import `Protocol`, `runtime_checkable` from `typing`
  - [x] Import `ActionContext`, `ActionResult`, `ValidationError` from
    `squadron.pipeline.models`
  - [x] Define `@runtime_checkable class Action(Protocol)` with:
    - `action_type` property → `str`
    - `async def execute(self, context: ActionContext) -> ActionResult`
    - `def validate(self, config: dict[str, object]) -> list[ValidationError]`
- [x] Add `ActionType(StrEnum)` to `pipeline/actions/__init__.py`:
  - Values: `DISPATCH="dispatch"`, `REVIEW="review"`, `COMPACT="compact"`,
    `CHECKPOINT="checkpoint"`, `CF_OP="cf-op"`, `COMMIT="commit"`,
    `DEVLOG="devlog"`
- [x] Verify pyright on both files

### T5 — Implement action registry in `pipeline/actions/__init__.py`

- [x] Add module-level `_REGISTRY: dict[str, Action] = {}` (after imports)
- [x] Implement `register_action(action_type: str, action: Action) -> None`
- [x] Implement `get_action(action_type: str) -> Action` — raises `KeyError`
  with helpful message listing registered types on miss (match
  `providers/registry.py` pattern)
- [x] Implement `list_actions() -> list[str]`
- [x] Export `Action` (re-export from `protocol.py`) and `ActionType` from
  the `__init__.py`
- [x] Verify pyright: `uv run pyright src/squadron/pipeline/actions/`

### T6 — Test action protocol and registry

- [x] Create `tests/pipeline/test_action_registry.py` with:
  - [x] `test_action_type_values` — spot-check `ActionType.DISPATCH == "dispatch"`,
    `ActionType.CF_OP == "cf-op"`
  - [x] `test_register_and_get_action` — create a minimal object satisfying
    `Action` protocol (use a simple class with the three required members),
    register it, retrieve it, assert `isinstance(obj, Action)`
  - [x] `test_get_unregistered_action_raises` — `get_action("nonexistent")`
    raises `KeyError`
  - [x] `test_list_actions` — register two actions, `list_actions()` returns
    both type strings
  - [x] `test_list_actions_empty` — fresh import (or monkeypatch `_REGISTRY`
    to `{}`) → `list_actions()` returns `[]`
- [x] Run: `uv run pytest tests/pipeline/test_action_registry.py -v` — all pass
- [x] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add Action protocol, ActionType enum, and action registry`

---

### T7 — Implement `StepType` protocol and `StepTypeName` enum

- [x] Create `src/squadron/pipeline/steps/protocol.py`:
  - [x] Import `Protocol`, `runtime_checkable` from `typing`
  - [x] Import `StepConfig`, `ValidationError` from `squadron.pipeline.models`
  - [x] Define `@runtime_checkable class StepType(Protocol)` with:
    - `step_type` property → `str`
    - `def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]`
    - `def validate(self, config: StepConfig) -> list[ValidationError]`
- [x] Add `StepTypeName(StrEnum)` to `pipeline/steps/__init__.py`:
  - Values: `DESIGN="design"`, `TASKS="tasks"`, `IMPLEMENT="implement"`,
    `COMPACT="compact"`, `REVIEW="review"`, `EACH="each"`, `DEVLOG="devlog"`
- [x] Verify pyright on both files

### T8 — Implement step-type registry in `pipeline/steps/__init__.py`

- [x] Add `_REGISTRY: dict[str, StepType] = {}`
- [x] Implement `register_step_type(step_type: str, impl: StepType) -> None`
- [x] Implement `get_step_type(step_type: str) -> StepType` — raises `KeyError`
  with helpful message listing registered types on miss
- [x] Implement `list_step_types() -> list[str]`
- [x] Export `StepType` (re-export from `protocol.py`) and `StepTypeName`
- [x] Verify pyright: `uv run pyright src/squadron/pipeline/steps/`

### T9 — Test step-type protocol and registry

- [x] Create `tests/pipeline/test_step_registry.py` with:
  - [x] `test_step_type_name_values` — spot-check `StepTypeName.DESIGN == "design"`,
    `StepTypeName.EACH == "each"`
  - [x] `test_register_and_get_step_type` — create a minimal object satisfying
    `StepType` protocol, register, retrieve, assert `isinstance(obj, StepType)`
  - [x] `test_get_unregistered_step_type_raises` — `get_step_type("nonexistent")`
    raises `KeyError`
  - [x] `test_list_step_types` — register two step types, `list_step_types()`
    returns both
  - [x] `test_list_step_types_empty` — monkeypatch `_REGISTRY` to `{}` →
    `list_step_types()` returns `[]`
- [x] Run: `uv run pytest tests/pipeline/test_step_registry.py -v` — all pass
- [x] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add StepType protocol, StepTypeName enum, and step-type registry`

---

### T10 — Implement `ModelResolver` (`pipeline/resolver.py`)

- [x] Create `src/squadron/pipeline/resolver.py`:
  - [x] Define `ModelResolutionError(Exception)` with docstring
  - [x] Define `ModelPoolNotImplemented(Exception)` with docstring noting
    "160 scope"
  - [x] Implement `ModelResolver` class:
    - `__init__(self, cli_override, pipeline_model, config_default)` — all
      `str | None = None`
    - `resolve(self, action_model=None, step_model=None) -> tuple[str, str | None]`
      — iterate the 5-level cascade in order, first non-None value wins;
      raise `ModelPoolNotImplemented` on `pool:` prefix;
      raise `ModelResolutionError` if all None;
      delegate to `resolve_model_alias()` from `squadron.models.aliases`
      for the final lookup
- [x] Verify pyright: `uv run pyright src/squadron/pipeline/resolver.py`

### T11 — Test `ModelResolver`

- [x] Create `tests/pipeline/test_resolver.py` with:
  - [x] `test_cli_override_wins` — set all levels, CLI override is returned
  - [x] `test_action_model_over_step` — no CLI, action_model and step_model
    both set → action_model wins
  - [x] `test_step_model_over_pipeline` — no CLI/action, step and pipeline
    set → step wins
  - [x] `test_pipeline_model_over_config` — step not set, pipeline and config
    set → pipeline wins
  - [x] `test_config_default_fallback` — only config_default set → used
  - [x] `test_all_none_raises_resolution_error` — no levels set →
    `ModelResolutionError`
  - [x] `test_pool_prefix_raises_not_implemented` — set `pipeline_model="pool:high"` →
    `ModelPoolNotImplemented`
  - [x] `test_pool_prefix_at_action_level` — `action_model="pool:review"` →
    `ModelPoolNotImplemented`
  - [x] `test_resolves_known_alias` — `pipeline_model="sonnet"` → returns
    `("claude-sonnet-4-6", "sdk")`
  - [x] `test_resolves_unknown_alias_as_literal` — `pipeline_model="my-custom-model"` →
    returns `("my-custom-model", None)` (passthrough behavior)
- [x] Run: `uv run pytest tests/pipeline/test_resolver.py -v` — all pass
- [x] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add ModelResolver with 5-level cascade and pool: stub`

---

### T12 — Wire `pipeline/__init__.py` public surface

- [x] Update `src/squadron/pipeline/__init__.py` to re-export:
  - From `squadron.pipeline.models`: `ActionContext`, `ActionResult`,
    `PipelineDefinition`, `StepConfig`, `ValidationError`
  - From `squadron.pipeline.resolver`: `ModelResolver`,
    `ModelResolutionError`, `ModelPoolNotImplemented`
  - From `squadron.pipeline.actions`: `ActionType`
  - From `squadron.pipeline.steps`: `StepTypeName`
- [x] Confirm top-level import works:
  `uv run python -c "from squadron.pipeline import ActionContext, ActionResult, ModelResolver, ActionType, StepTypeName; print('OK')"`
- [x] Verify pyright: `uv run pyright src/squadron/pipeline/__init__.py`

### T13 — Full test run and pyright check

- [x] Run full pipeline test suite: `uv run pytest tests/pipeline/ -v`
  — all tests pass
- [x] Run full repo test suite: `uv run pytest` — no regressions (8 pre-existing
  failures in `test_install_commands.py` and `test_auth_resolution.py` are
  expected and unrelated)
- [x] Run pyright on the new package:
  `uv run pyright src/squadron/pipeline/`
  — 0 errors
- [x] Run ruff format before final commit:
  `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: wire pipeline __init__ public surface and verify pyright`

---

### T14 — Verification walkthrough

- [x] Run each command from the slice design Verification Walkthrough and
  confirm output matches expectations:
  - `find src/squadron/pipeline -type f | sort` — all expected files present
  - Import smoke test — `imports OK`
  - Resolver cascade smoke test — `claude-sonnet-4-6 sdk`
  - Pool prefix smoke test — `pool: correctly blocked: …`
  - Empty cascade smoke test — `empty cascade correctly raised: …`
- [x] Update the Verification Walkthrough section of the slice design with
  actual command output and any caveats discovered
- [x] Update `status: design` → `status: complete` and `dateUpdated` in
  slice design frontmatter
- [x] Mark slice 142 entry in `140-slices.pipeline-foundation.md` as `[x]`
- [x] Update `CHANGELOG.md` with the slice 142 additions under `[Unreleased]`
- [x] Write DEVLOG entry for Phase 6 completion

**Commit:** `docs: mark slice 142 complete, update changelog and devlog`
