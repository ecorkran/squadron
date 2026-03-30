---
docType: task-breakdown
sliceIndex: 142
sliceName: pipeline-core-models-and-action-protocol
project: squadron
sliceDesign: user/slices/142-slice.pipeline-core-models-and-action-protocol.md
architecture: user/architecture/140-arch.pipeline-foundation.md
dependencies: [100-band complete, slice 141 complete]
dateCreated: 20260330
dateUpdated: 20260330
status: not_started
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

- [ ] Verify current branch is `main`: `git status`
- [ ] Create and switch to slice branch:
  `git checkout -b 142-pipeline-core-models-and-action-protocol`
- [ ] Create directory tree (all empty `__init__.py` files):
  - `src/squadron/pipeline/__init__.py`
  - `src/squadron/pipeline/actions/__init__.py`
  - `src/squadron/pipeline/steps/__init__.py`
- [ ] Create stub action modules (docstring + `# TODO: slice NNN`):
  - `src/squadron/pipeline/actions/dispatch.py` (slice 145)
  - `src/squadron/pipeline/actions/review.py` (slice 146)
  - `src/squadron/pipeline/actions/compact.py` (slice 147)
  - `src/squadron/pipeline/actions/checkpoint.py` (slice 146)
  - `src/squadron/pipeline/actions/cf_op.py` (slice 144)
  - `src/squadron/pipeline/actions/commit.py` (slice 144)
  - `src/squadron/pipeline/actions/devlog.py` (slice 144)
- [ ] Create stub step-type modules (docstring + `# TODO: slice NNN`):
  - `src/squadron/pipeline/steps/phase.py` (slice 147)
  - `src/squadron/pipeline/steps/compact.py` (slice 147)
  - `src/squadron/pipeline/steps/review.py` (slice 147)
  - `src/squadron/pipeline/steps/collection.py` (slice 149)
  - `src/squadron/pipeline/steps/devlog.py` (slice 147)
- [ ] Confirm `uv run python -c "import squadron.pipeline"` succeeds with no
  errors

### T2 — Implement `pipeline/models.py`

- [ ] Create `src/squadron/pipeline/models.py` with the following dataclasses
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
- [ ] Verify pyright: `uv run pyright src/squadron/pipeline/models.py`

### T3 — Test `pipeline/models.py`

- [ ] Create `tests/pipeline/__init__.py` (empty)
- [ ] Create `tests/pipeline/test_models.py` with:
  - [ ] `test_validation_error_fields` — construct `ValidationError`, check
    `field`, `message`, `action_type`
  - [ ] `test_action_result_defaults` — `ActionResult(success=True,
    action_type="test", outputs={})` → `error` is None, `verdict` is None,
    `findings` is `[]`, `metadata` is `{}`
  - [ ] `test_action_result_failure` — construct with `success=False`,
    `error="oops"`, verify attributes
  - [ ] `test_step_config_fields` — construct `StepConfig`, verify all fields
  - [ ] `test_pipeline_definition_model_default` — `PipelineDefinition` with
    no `model` arg → `model` is None
  - [ ] `test_pipeline_definition_with_model` — pass `model="sonnet"`, verify
- [ ] Run: `uv run pytest tests/pipeline/test_models.py -v` — all pass
- [ ] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add pipeline package skeleton and core data models`

---

### T4 — Implement `Action` protocol and `ActionType` enum

- [ ] Create `src/squadron/pipeline/actions/protocol.py`:
  - [ ] Import `Protocol`, `runtime_checkable` from `typing`
  - [ ] Import `ActionContext`, `ActionResult`, `ValidationError` from
    `squadron.pipeline.models`
  - [ ] Define `@runtime_checkable class Action(Protocol)` with:
    - `action_type` property → `str`
    - `async def execute(self, context: ActionContext) -> ActionResult`
    - `def validate(self, config: dict[str, object]) -> list[ValidationError]`
- [ ] Add `ActionType(StrEnum)` to `pipeline/actions/__init__.py`:
  - Values: `DISPATCH="dispatch"`, `REVIEW="review"`, `COMPACT="compact"`,
    `CHECKPOINT="checkpoint"`, `CF_OP="cf-op"`, `COMMIT="commit"`,
    `DEVLOG="devlog"`
- [ ] Verify pyright on both files

### T5 — Implement action registry in `pipeline/actions/__init__.py`

- [ ] Add module-level `_REGISTRY: dict[str, Action] = {}` (after imports)
- [ ] Implement `register_action(action_type: str, action: Action) -> None`
- [ ] Implement `get_action(action_type: str) -> Action` — raises `KeyError`
  with helpful message listing registered types on miss (match
  `providers/registry.py` pattern)
- [ ] Implement `list_actions() -> list[str]`
- [ ] Export `Action` (re-export from `protocol.py`) and `ActionType` from
  the `__init__.py`
- [ ] Verify pyright: `uv run pyright src/squadron/pipeline/actions/`

### T6 — Test action protocol and registry

- [ ] Create `tests/pipeline/test_action_registry.py` with:
  - [ ] `test_action_type_values` — spot-check `ActionType.DISPATCH == "dispatch"`,
    `ActionType.CF_OP == "cf-op"`
  - [ ] `test_register_and_get_action` — create a minimal object satisfying
    `Action` protocol (use a simple class with the three required members),
    register it, retrieve it, assert `isinstance(obj, Action)`
  - [ ] `test_get_unregistered_action_raises` — `get_action("nonexistent")`
    raises `KeyError`
  - [ ] `test_list_actions` — register two actions, `list_actions()` returns
    both type strings
  - [ ] `test_list_actions_empty` — fresh import (or monkeypatch `_REGISTRY`
    to `{}`) → `list_actions()` returns `[]`
- [ ] Run: `uv run pytest tests/pipeline/test_action_registry.py -v` — all pass
- [ ] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add Action protocol, ActionType enum, and action registry`

---

### T7 — Implement `StepType` protocol and `StepTypeName` enum

- [ ] Create `src/squadron/pipeline/steps/protocol.py`:
  - [ ] Import `Protocol`, `runtime_checkable` from `typing`
  - [ ] Import `StepConfig`, `ValidationError` from `squadron.pipeline.models`
  - [ ] Define `@runtime_checkable class StepType(Protocol)` with:
    - `step_type` property → `str`
    - `def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]`
    - `def validate(self, config: StepConfig) -> list[ValidationError]`
- [ ] Add `StepTypeName(StrEnum)` to `pipeline/steps/__init__.py`:
  - Values: `DESIGN="design"`, `TASKS="tasks"`, `IMPLEMENT="implement"`,
    `COMPACT="compact"`, `REVIEW="review"`, `EACH="each"`, `DEVLOG="devlog"`
- [ ] Verify pyright on both files

### T8 — Implement step-type registry in `pipeline/steps/__init__.py`

- [ ] Add `_REGISTRY: dict[str, StepType] = {}`
- [ ] Implement `register_step_type(step_type: str, impl: StepType) -> None`
- [ ] Implement `get_step_type(step_type: str) -> StepType` — raises `KeyError`
  with helpful message listing registered types on miss
- [ ] Implement `list_step_types() -> list[str]`
- [ ] Export `StepType` (re-export from `protocol.py`) and `StepTypeName`
- [ ] Verify pyright: `uv run pyright src/squadron/pipeline/steps/`

### T9 — Test step-type protocol and registry

- [ ] Create `tests/pipeline/test_step_registry.py` with:
  - [ ] `test_step_type_name_values` — spot-check `StepTypeName.DESIGN == "design"`,
    `StepTypeName.EACH == "each"`
  - [ ] `test_register_and_get_step_type` — create a minimal object satisfying
    `StepType` protocol, register, retrieve, assert `isinstance(obj, StepType)`
  - [ ] `test_get_unregistered_step_type_raises` — `get_step_type("nonexistent")`
    raises `KeyError`
  - [ ] `test_list_step_types` — register two step types, `list_step_types()`
    returns both
  - [ ] `test_list_step_types_empty` — monkeypatch `_REGISTRY` to `{}` →
    `list_step_types()` returns `[]`
- [ ] Run: `uv run pytest tests/pipeline/test_step_registry.py -v` — all pass
- [ ] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add StepType protocol, StepTypeName enum, and step-type registry`

---

### T10 — Implement `ModelResolver` (`pipeline/resolver.py`)

- [ ] Create `src/squadron/pipeline/resolver.py`:
  - [ ] Define `ModelResolutionError(Exception)` with docstring
  - [ ] Define `ModelPoolNotImplemented(Exception)` with docstring noting
    "160 scope"
  - [ ] Implement `ModelResolver` class:
    - `__init__(self, cli_override, pipeline_model, config_default)` — all
      `str | None = None`
    - `resolve(self, action_model=None, step_model=None) -> tuple[str, str | None]`
      — iterate the 5-level cascade in order, first non-None value wins;
      raise `ModelPoolNotImplemented` on `pool:` prefix;
      raise `ModelResolutionError` if all None;
      delegate to `resolve_model_alias()` from `squadron.models.aliases`
      for the final lookup
- [ ] Verify pyright: `uv run pyright src/squadron/pipeline/resolver.py`

### T11 — Test `ModelResolver`

- [ ] Create `tests/pipeline/test_resolver.py` with:
  - [ ] `test_cli_override_wins` — set all levels, CLI override is returned
  - [ ] `test_action_model_over_step` — no CLI, action_model and step_model
    both set → action_model wins
  - [ ] `test_step_model_over_pipeline` — no CLI/action, step and pipeline
    set → step wins
  - [ ] `test_pipeline_model_over_config` — step not set, pipeline and config
    set → pipeline wins
  - [ ] `test_config_default_fallback` — only config_default set → used
  - [ ] `test_all_none_raises_resolution_error` — no levels set →
    `ModelResolutionError`
  - [ ] `test_pool_prefix_raises_not_implemented` — set `pipeline_model="pool:high"` →
    `ModelPoolNotImplemented`
  - [ ] `test_pool_prefix_at_action_level` — `action_model="pool:review"` →
    `ModelPoolNotImplemented`
  - [ ] `test_resolves_known_alias` — `pipeline_model="sonnet"` → returns
    `("claude-sonnet-4-6", "sdk")`
  - [ ] `test_resolves_unknown_alias_as_literal` — `pipeline_model="my-custom-model"` →
    returns `("my-custom-model", None)` (passthrough behavior)
- [ ] Run: `uv run pytest tests/pipeline/test_resolver.py -v` — all pass
- [ ] `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: add ModelResolver with 5-level cascade and pool: stub`

---

### T12 — Wire `pipeline/__init__.py` public surface

- [ ] Update `src/squadron/pipeline/__init__.py` to re-export:
  - From `squadron.pipeline.models`: `ActionContext`, `ActionResult`,
    `PipelineDefinition`, `StepConfig`, `ValidationError`
  - From `squadron.pipeline.resolver`: `ModelResolver`,
    `ModelResolutionError`, `ModelPoolNotImplemented`
  - From `squadron.pipeline.actions`: `ActionType`
  - From `squadron.pipeline.steps`: `StepTypeName`
- [ ] Confirm top-level import works:
  `uv run python -c "from squadron.pipeline import ActionContext, ActionResult, ModelResolver, ActionType, StepTypeName; print('OK')"`
- [ ] Verify pyright: `uv run pyright src/squadron/pipeline/__init__.py`

### T13 — Full test run and pyright check

- [ ] Run full pipeline test suite: `uv run pytest tests/pipeline/ -v`
  — all tests pass
- [ ] Run full repo test suite: `uv run pytest` — no regressions (8 pre-existing
  failures in `test_install_commands.py` and `test_auth_resolution.py` are
  expected and unrelated)
- [ ] Run pyright on the new package:
  `uv run pyright src/squadron/pipeline/`
  — 0 errors
- [ ] Run ruff format before final commit:
  `uv run ruff format src/squadron/pipeline/ tests/pipeline/`

**Commit:** `feat: wire pipeline __init__ public surface and verify pyright`

---

### T14 — Verification walkthrough

- [ ] Run each command from the slice design Verification Walkthrough and
  confirm output matches expectations:
  - `find src/squadron/pipeline -type f | sort` — all expected files present
  - Import smoke test — `imports OK`
  - Resolver cascade smoke test — `claude-sonnet-4-6 sdk`
  - Pool prefix smoke test — `pool: correctly blocked: …`
  - Empty cascade smoke test — `empty cascade correctly raised: …`
- [ ] Update the Verification Walkthrough section of the slice design with
  actual command output and any caveats discovered
- [ ] Update `status: design` → `status: complete` and `dateUpdated` in
  slice design frontmatter
- [ ] Mark slice 142 entry in `140-slices.pipeline-foundation.md` as `[x]`
- [ ] Update `CHANGELOG.md` with the slice 142 additions under `[Unreleased]`
- [ ] Write DEVLOG entry for Phase 6 completion

**Commit:** `docs: mark slice 142 complete, update changelog and devlog`
