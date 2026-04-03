---
docType: tasks
slice: pipeline-definitions-and-loader
project: squadron
lld: user/slices/148-slice.pipeline-definitions-and-loader.md
dependencies: [147]
projectState: Slice 147 complete — all step types and actions implemented. Pipeline models, registries, and resolver in place.
dateCreated: 20260402
dateUpdated: 20260402
status: complete
---

## Context Summary

- Working on slice 148: Pipeline Definitions and Loader
- All prerequisite slices complete (142, 147): `PipelineDefinition`, `StepConfig`, `ValidationError` dataclasses exist; step type and action registries populated
- Pydantic v2 already in `pyproject.toml`; not yet used in `src/squadron/pipeline/`
- `src/squadron/data/pipelines/` exists with only a `.gitkeep`
- This slice produces `schema.py` and `loader.py` plus four built-in pipeline YAML files
- Next slice: 149 (Pipeline Executor), which consumes `load_pipeline()` and `PipelineDefinition`
- Test-with pattern throughout; pyright and ruff must be clean at each checkpoint

---

## Tasks

### T1 — Pydantic schema models (`schema.py`)

- [x] Create `src/squadron/pipeline/schema.py` with three Pydantic v2 models
  - [x] `StepSchema(BaseModel)` — fields: `step_type: str`, `name: str | None = None`, `config: dict[str, object]`
  - [x] `PipelineSchema(BaseModel)` — fields: `name: str`, `description: str = ""`, `params: dict[str, str] = {}`, `model: str | None = None`, `steps: list[StepSchema]`
  - [x] `PipelineSchema` uses a `@model_validator(mode="before")` to unpack the raw `steps` list — each step is a single-key dict `{type_name: config_or_scalar}`; scalar value (e.g. `"auto"`) expands to `{"mode": value}`; result is fed into `StepSchema`
  - [x] `StepSchema` auto-generates `name` from `"{step_type}-{index}"` when not explicitly provided (accept index as part of the `before` validator context or generate during `to_definition()`)
  - [x] `PipelineSchema.to_definition()` converts to `PipelineDefinition` + `list[StepConfig]` dataclasses from `squadron.pipeline.models`
  - [x] Use `model_config = ConfigDict(extra="forbid")` on `PipelineSchema` to reject unknown top-level keys
  - [x] Success: `pyright src/squadron/pipeline/schema.py` reports 0 errors; `ruff check` clean

### T2 — Schema unit tests

- [x] Create `tests/pipeline/test_schema.py`
  - [x] Test valid minimal pipeline (name + steps only) parses without error
  - [x] Test full pipeline with params, model, multi-step parses correctly
  - [x] Test step shorthand expansion: `devlog: auto` → `StepSchema(step_type="devlog", config={"mode": "auto"})`
  - [x] Test step mapping form: `design: {phase: 4, review: arch}` → `StepSchema(step_type="design", config={...})`
  - [x] Test missing `name` raises `pydantic.ValidationError`
  - [x] Test empty `steps` list raises `pydantic.ValidationError` (steps must be non-empty)
  - [x] Test unknown top-level key raises `pydantic.ValidationError`
  - [x] Test `to_definition()` returns `PipelineDefinition` with correct `name`, `model`, `steps`
  - [x] Test step auto-naming: step without explicit `name` gets `"{type}-{index}"` name in `StepConfig`
  - [x] Success: `pytest tests/pipeline/test_schema.py -v` all pass

### T3 — Built-in pipeline YAML files

- [x] Create `src/squadron/data/pipelines/slice-lifecycle.yaml` (5 steps: design, tasks, compact, implement, devlog) — see slice design §Built-in Pipeline Definitions
- [x] Create `src/squadron/data/pipelines/review-only.yaml` (1 step: review with template param placeholder)
- [x] Create `src/squadron/data/pipelines/implementation-only.yaml` (2 steps: implement, devlog)
- [x] Create `src/squadron/data/pipelines/design-batch.yaml` (1 step: each with nested design)
- [x] Remove `src/squadron/data/pipelines/.gitkeep` (files now exist)
- [x] Success: all four YAML files are syntactically valid (`python -c "import yaml; yaml.safe_load(open('...'))"` for each)

### T4 — Commit checkpoint: schema + built-in YAMLs

- [x] Run `ruff format src/squadron/pipeline/schema.py`
- [x] Run full test suite: `pytest` — all tests pass
- [x] `git add` and commit: `feat: add pipeline Pydantic schema and built-in pipeline definitions`

### T5 — Pipeline loader: core loading (`loader.py`)

- [x] Create `src/squadron/pipeline/loader.py`
  - [x] `PipelineInfo` dataclass — fields: `name: str`, `description: str`, `source: str` ("built-in" | "user" | "project"), `path: Path`
  - [x] `_load_yaml(path: Path) -> PipelineDefinition` — reads YAML, calls `PipelineSchema.model_validate()`, calls `to_definition()`; raises `FileNotFoundError` or `pydantic.ValidationError` without swallowing
  - [x] `load_pipeline(name_or_path: str, *, project_dir: Path | None = None, user_dir: Path | None = None) -> PipelineDefinition`
    - [x] If `name_or_path` is an existing file path, load directly via `_load_yaml()`
    - [x] Otherwise treat as name: search project dir → user dir → built-in dir for `{name}.yaml`; raise `FileNotFoundError` if not found in any source
  - [x] Default directories: project dir = `Path.cwd() / "project-documents/user/pipelines"`, user dir = `Path.home() / ".config/squadron/pipelines"`, built-in dir = `data_dir() / "pipelines"`
  - [x] Success: `pyright src/squadron/pipeline/loader.py` 0 errors; `ruff check` clean

### T6 — Loader core tests

- [x] Create `tests/pipeline/test_loader.py`
  - [x] Test `load_pipeline("slice-lifecycle")` with no overrides loads the built-in and returns `PipelineDefinition` with `name == "slice-lifecycle"` and 5 steps
  - [x] Test `load_pipeline("/path/to/file.yaml")` loads directly from path (use `tmp_path` fixture)
  - [x] Test unknown name raises `FileNotFoundError`
  - [x] Test project dir overrides built-in with same name (place custom YAML in `tmp_path`, pass as `project_dir`)
  - [x] Test user dir overrides built-in (place custom YAML in `tmp_path`, pass as `user_dir`)
  - [x] Test project dir overrides user dir (both `tmp_path` directories, project name wins)
  - [x] Success: `pytest tests/pipeline/test_loader.py -v` all pass

### T7 — Pipeline discovery (`discover_pipelines`)

- [x] Add `discover_pipelines(*, project_dir: Path | None = None, user_dir: Path | None = None) -> list[PipelineInfo]` to `loader.py`
  - [x] Scan built-in dir, then user dir, then project dir, each for `*.yaml` files
  - [x] Collect into a dict keyed by pipeline name — later sources overwrite earlier (project wins over user wins over built-in)
  - [x] Return `list[PipelineInfo]` sorted by name
  - [x] Gracefully skip directories that do not exist (no error)
  - [x] Skip files that fail YAML parsing or schema validation (log a warning, continue)
  - [x] Success: `pyright` and `ruff check` clean on updated `loader.py`

### T8 — Discovery tests

- [x] Add to `tests/pipeline/test_loader.py`
  - [x] Test `discover_pipelines()` returns at least the 4 built-in pipelines
  - [x] Test each returned `PipelineInfo` has `source == "built-in"` for built-ins
  - [x] Test custom YAML in project dir appears with `source == "project"` and overrides built-in entry of same name
  - [x] Test non-existent project or user dirs are handled without error
  - [x] Test malformed YAML in a discovery dir is skipped without raising
  - [x] Success: all new tests pass

### T9 — Semantic validation (`validate_pipeline`)

- [x] Add `validate_pipeline(definition: PipelineDefinition) -> list[ValidationError]` to `loader.py`
  - [x] For each step, check `step_type` is registered in `squadron.pipeline.steps`; add `ValidationError` if not (use `list_step_types()`)
  - [x] For each step with a registered step type, call `step_type_impl.validate(step_config)` and collect any returned errors
  - [x] If `definition.model` is set, attempt `resolve_model_alias(definition.model)`; add `ValidationError` on failure
  - [x] For each step config that contains a `"model"` key, attempt alias resolution; add `ValidationError` on failure
  - [x] For each step config that contains a `"review"` key (str or dict with `"template"`), check the template name exists via `squadron.review.templates.get_template()`; add `ValidationError` if not found
  - [x] Check that `{param_name}` placeholders referenced in step configs match declared param names in `definition.params`; add `ValidationError` for undeclared references
  - [x] Import step type modules at top of function to trigger registration (same `import` pattern as test integration tests in slice 147): `import squadron.pipeline.steps.phase`, etc.
  - [x] The `each` step type will not be registered in 148 scope — treat unknown step types as a non-fatal warning (add to errors but continue)
  - [x] Success: `pyright` and `ruff check` clean

### T10 — Semantic validation tests

- [x] Create `tests/pipeline/test_validate_pipeline.py`
  - [x] Test `validate_pipeline` on built-in `slice-lifecycle` returns empty error list
  - [x] Test `validate_pipeline` on built-in `review-only` returns empty error list
  - [x] Test `validate_pipeline` on built-in `implementation-only` returns empty error list
  - [x] Test unknown step type produces a `ValidationError` with `field == "step_type"`
  - [x] Test invalid model alias produces a `ValidationError` with `field == "model"`
  - [x] Test missing review template name produces a `ValidationError` with `field` referencing template
  - [x] Test param placeholder `{undeclared}` in step config produces a `ValidationError`
  - [x] Test declared param placeholder `{slice}` in step config does not produce error when `slice` is in params
  - [x] Success: `pytest tests/pipeline/test_validate_pipeline.py -v` all pass

### T11 — Integration tests: load and validate all built-ins

- [x] Create `tests/pipeline/test_loader_integration.py`
  - [x] Parameterize over all four built-in pipeline names
  - [x] For each: `load_pipeline(name)` succeeds and returns `PipelineDefinition`
  - [x] For each: `validate_pipeline(definition)` returns no errors (excluding `each` step type warning)
  - [x] Verify `slice-lifecycle` has 5 steps in order: design, tasks, compact, implement, devlog
  - [x] Verify `review-only` has 1 step with `step_type == "review"`
  - [x] Verify `design-batch` has 1 step with `step_type == "each"`
  - [x] Success: `pytest tests/pipeline/test_loader_integration.py -v` all pass

### T12 — Commit checkpoint: loader + validator

- [x] Run `ruff format src/squadron/pipeline/loader.py`
- [x] Run full test suite: `pytest` — all tests pass; pyright 0 errors
- [x] `git add` and commit: `feat: add pipeline loader, discovery, and semantic validation`

### T13 — Test suite commit and closeout

- [x] Run full test suite: `pytest` with count confirmation (compare to prior count of 952)
- [x] Run `pyright src/squadron/pipeline/schema.py src/squadron/pipeline/loader.py`
- [x] Run `ruff check src/squadron/pipeline/`
- [x] Update slice design status to `complete` in `148-slice.pipeline-definitions-and-loader.md`
- [x] Mark slice 148 entry complete in `140-slices.pipeline-foundation.md`
- [x] Update `CHANGELOG.md` with slice 148 entries
- [x] Write DEVLOG entry (Phase 6 complete)
- [x] `git add` and commit: `docs: mark slice 148 pipeline definitions and loader complete`
