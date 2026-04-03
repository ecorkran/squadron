---
docType: tasks
slice: pipeline-definitions-and-loader
project: squadron
lld: user/slices/148-slice.pipeline-definitions-and-loader.md
dependencies: [147]
projectState: Slice 147 complete — all step types and actions implemented. Pipeline models, registries, and resolver in place.
dateCreated: 20260402
dateUpdated: 20260402
status: not_started
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

- [ ] Create `src/squadron/pipeline/schema.py` with three Pydantic v2 models
  - [ ] `StepSchema(BaseModel)` — fields: `step_type: str`, `name: str | None = None`, `config: dict[str, object]`
  - [ ] `PipelineSchema(BaseModel)` — fields: `name: str`, `description: str = ""`, `params: dict[str, str] = {}`, `model: str | None = None`, `steps: list[StepSchema]`
  - [ ] `PipelineSchema` uses a `@model_validator(mode="before")` to unpack the raw `steps` list — each step is a single-key dict `{type_name: config_or_scalar}`; scalar value (e.g. `"auto"`) expands to `{"mode": value}`; result is fed into `StepSchema`
  - [ ] `StepSchema` auto-generates `name` from `"{step_type}-{index}"` when not explicitly provided (accept index as part of the `before` validator context or generate during `to_definition()`)
  - [ ] `PipelineSchema.to_definition()` converts to `PipelineDefinition` + `list[StepConfig]` dataclasses from `squadron.pipeline.models`
  - [ ] Use `model_config = ConfigDict(extra="forbid")` on `PipelineSchema` to reject unknown top-level keys
  - [ ] Success: `pyright src/squadron/pipeline/schema.py` reports 0 errors; `ruff check` clean

### T2 — Schema unit tests

- [ ] Create `tests/pipeline/test_schema.py`
  - [ ] Test valid minimal pipeline (name + steps only) parses without error
  - [ ] Test full pipeline with params, model, multi-step parses correctly
  - [ ] Test step shorthand expansion: `devlog: auto` → `StepSchema(step_type="devlog", config={"mode": "auto"})`
  - [ ] Test step mapping form: `design: {phase: 4, review: arch}` → `StepSchema(step_type="design", config={...})`
  - [ ] Test missing `name` raises `pydantic.ValidationError`
  - [ ] Test empty `steps` list raises `pydantic.ValidationError` (steps must be non-empty)
  - [ ] Test unknown top-level key raises `pydantic.ValidationError`
  - [ ] Test `to_definition()` returns `PipelineDefinition` with correct `name`, `model`, `steps`
  - [ ] Test step auto-naming: step without explicit `name` gets `"{type}-{index}"` name in `StepConfig`
  - [ ] Success: `pytest tests/pipeline/test_schema.py -v` all pass

### T3 — Built-in pipeline YAML files

- [ ] Create `src/squadron/data/pipelines/slice-lifecycle.yaml` (5 steps: design, tasks, compact, implement, devlog) — see slice design §Built-in Pipeline Definitions
- [ ] Create `src/squadron/data/pipelines/review-only.yaml` (1 step: review with template param placeholder)
- [ ] Create `src/squadron/data/pipelines/implementation-only.yaml` (2 steps: implement, devlog)
- [ ] Create `src/squadron/data/pipelines/design-batch.yaml` (1 step: each with nested design)
- [ ] Remove `src/squadron/data/pipelines/.gitkeep` (files now exist)
- [ ] Success: all four YAML files are syntactically valid (`python -c "import yaml; yaml.safe_load(open('...'))"` for each)

### T4 — Commit checkpoint: schema + built-in YAMLs

- [ ] Run `ruff format src/squadron/pipeline/schema.py`
- [ ] Run full test suite: `pytest` — all tests pass
- [ ] `git add` and commit: `feat: add pipeline Pydantic schema and built-in pipeline definitions`

### T5 — Pipeline loader: core loading (`loader.py`)

- [ ] Create `src/squadron/pipeline/loader.py`
  - [ ] `PipelineInfo` dataclass — fields: `name: str`, `description: str`, `source: str` ("built-in" | "user" | "project"), `path: Path`
  - [ ] `_load_yaml(path: Path) -> PipelineDefinition` — reads YAML, calls `PipelineSchema.model_validate()`, calls `to_definition()`; raises `FileNotFoundError` or `pydantic.ValidationError` without swallowing
  - [ ] `load_pipeline(name_or_path: str, *, project_dir: Path | None = None, user_dir: Path | None = None) -> PipelineDefinition`
    - If `name_or_path` is an existing file path, load directly via `_load_yaml()`
    - Otherwise treat as name: search project dir → user dir → built-in dir for `{name}.yaml`; raise `FileNotFoundError` if not found in any source
  - [ ] Default directories: project dir = `Path.cwd() / "project-documents/user/pipelines"`, user dir = `Path.home() / ".config/squadron/pipelines"`, built-in dir = `data_dir() / "pipelines"`
  - [ ] Success: `pyright src/squadron/pipeline/loader.py` 0 errors; `ruff check` clean

### T6 — Loader core tests

- [ ] Create `tests/pipeline/test_loader.py`
  - [ ] Test `load_pipeline("slice-lifecycle")` with no overrides loads the built-in and returns `PipelineDefinition` with `name == "slice-lifecycle"` and 5 steps
  - [ ] Test `load_pipeline("/path/to/file.yaml")` loads directly from path (use `tmp_path` fixture)
  - [ ] Test unknown name raises `FileNotFoundError`
  - [ ] Test project dir overrides built-in with same name (place custom YAML in `tmp_path`, pass as `project_dir`)
  - [ ] Test user dir overrides built-in (place custom YAML in `tmp_path`, pass as `user_dir`)
  - [ ] Test project dir overrides user dir (both `tmp_path` directories, project name wins)
  - [ ] Success: `pytest tests/pipeline/test_loader.py -v` all pass

### T7 — Pipeline discovery (`discover_pipelines`)

- [ ] Add `discover_pipelines(*, project_dir: Path | None = None, user_dir: Path | None = None) -> list[PipelineInfo]` to `loader.py`
  - [ ] Scan built-in dir, then user dir, then project dir, each for `*.yaml` files
  - [ ] Collect into a dict keyed by pipeline name — later sources overwrite earlier (project wins over user wins over built-in)
  - [ ] Return `list[PipelineInfo]` sorted by name
  - [ ] Gracefully skip directories that do not exist (no error)
  - [ ] Skip files that fail YAML parsing or schema validation (log a warning, continue)
  - [ ] Success: `pyright` and `ruff check` clean on updated `loader.py`

### T8 — Discovery tests

- [ ] Add to `tests/pipeline/test_loader.py`
  - [ ] Test `discover_pipelines()` returns at least the 4 built-in pipelines
  - [ ] Test each returned `PipelineInfo` has `source == "built-in"` for built-ins
  - [ ] Test custom YAML in project dir appears with `source == "project"` and overrides built-in entry of same name
  - [ ] Test non-existent project or user dirs are handled without error
  - [ ] Test malformed YAML in a discovery dir is skipped without raising
  - [ ] Success: all new tests pass

### T9 — Semantic validation (`validate_pipeline`)

- [ ] Add `validate_pipeline(definition: PipelineDefinition) -> list[ValidationError]` to `loader.py`
  - [ ] For each step, check `step_type` is registered in `squadron.pipeline.steps`; add `ValidationError` if not (use `list_step_types()`)
  - [ ] For each step with a registered step type, call `step_type_impl.validate(step_config)` and collect any returned errors
  - [ ] If `definition.model` is set, attempt `resolve_model_alias(definition.model)`; add `ValidationError` on failure
  - [ ] For each step config that contains a `"model"` key, attempt alias resolution; add `ValidationError` on failure
  - [ ] For each step config that contains a `"review"` key (str or dict with `"template"`), check the template name exists via `squadron.review.templates.get_template()`; add `ValidationError` if not found
  - [ ] Check that `{param_name}` placeholders referenced in step configs match declared param names in `definition.params`; add `ValidationError` for undeclared references
  - [ ] Import step type modules at top of function to trigger registration (same `import` pattern as test integration tests in slice 147): `import squadron.pipeline.steps.phase`, etc.
  - [ ] The `each` step type will not be registered in 148 scope — treat unknown step types as a non-fatal warning (add to errors but continue)
  - [ ] Success: `pyright` and `ruff check` clean

### T10 — Semantic validation tests

- [ ] Create `tests/pipeline/test_validate_pipeline.py`
  - [ ] Test `validate_pipeline` on built-in `slice-lifecycle` returns empty error list
  - [ ] Test `validate_pipeline` on built-in `review-only` returns empty error list
  - [ ] Test `validate_pipeline` on built-in `implementation-only` returns empty error list
  - [ ] Test unknown step type produces a `ValidationError` with `field == "step_type"`
  - [ ] Test invalid model alias produces a `ValidationError` with `field == "model"`
  - [ ] Test missing review template name produces a `ValidationError` with `field` referencing template
  - [ ] Test param placeholder `{undeclared}` in step config produces a `ValidationError`
  - [ ] Test declared param placeholder `{slice}` in step config does not produce error when `slice` is in params
  - [ ] Success: `pytest tests/pipeline/test_validate_pipeline.py -v` all pass

### T11 — Integration tests: load and validate all built-ins

- [ ] Create `tests/pipeline/test_loader_integration.py`
  - [ ] Parameterize over all four built-in pipeline names
  - [ ] For each: `load_pipeline(name)` succeeds and returns `PipelineDefinition`
  - [ ] For each: `validate_pipeline(definition)` returns no errors (excluding `each` step type warning)
  - [ ] Verify `slice-lifecycle` has 5 steps in order: design, tasks, compact, implement, devlog
  - [ ] Verify `review-only` has 1 step with `step_type == "review"`
  - [ ] Verify `design-batch` has 1 step with `step_type == "each"`
  - [ ] Success: `pytest tests/pipeline/test_loader_integration.py -v` all pass

### T12 — Commit checkpoint: loader + validator

- [ ] Run `ruff format src/squadron/pipeline/loader.py`
- [ ] Run full test suite: `pytest` — all tests pass; pyright 0 errors
- [ ] `git add` and commit: `feat: add pipeline loader, discovery, and semantic validation`

### T13 — Test suite commit and closeout

- [ ] Run full test suite: `pytest` with count confirmation (compare to prior count of 952)
- [ ] Run `pyright src/squadron/pipeline/schema.py src/squadron/pipeline/loader.py`
- [ ] Run `ruff check src/squadron/pipeline/`
- [ ] Update slice design status to `complete` in `148-slice.pipeline-definitions-and-loader.md`
- [ ] Mark slice 148 entry complete in `140-slices.pipeline-foundation.md`
- [ ] Update `CHANGELOG.md` with slice 148 entries
- [ ] Write DEVLOG entry (Phase 6 complete)
- [ ] `git add` and commit: `docs: mark slice 148 pipeline definitions and loader complete`
