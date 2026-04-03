---
docType: slice-design
slice: pipeline-definitions-and-loader
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [147]
interfaces: [149, 151]
dateCreated: 20260402
dateUpdated: 20260402
status: not_started
---

# Slice 148: Pipeline Definitions and Loader

## Overview

Implement the YAML pipeline definition grammar, Pydantic-based schema validation, definition loader with multi-source discovery (built-in, project, user), four built-in pipeline definitions, and `sq run --validate` for pre-execution validation. This slice makes pipeline definitions parseable and validated data — the executor (slice 149) consumes them.

## Value

- **Declarative pipeline authoring.** Users and built-in pipelines express intent in YAML. The loader validates structure, the step types (slice 147) handle expansion, and the executor (slice 149) runs them. This slice bridges raw YAML to validated `PipelineDefinition` objects.
- **Built-in pipelines ship as data.** `slice-lifecycle`, `review-only`, `implementation-only`, and `design-batch` are YAML files in `src/squadron/data/pipelines/`, not hardcoded Python. Users can copy and customize them.
- **Pre-execution validation.** `sq run --validate` catches definition errors before execution starts — unknown step types, unresolvable model aliases, missing review templates, structural errors.
- **Custom pipeline discovery.** Users place YAML definitions in their project or user config directory and `sq run --list` discovers them alongside built-ins.

## Technical Scope

### Included

1. **Pydantic schema models** (`src/squadron/pipeline/schema.py`) — Pydantic v2 models for pipeline YAML validation: `PipelineSchema`, `StepSchema`, `ParamSchema`. These parse and validate raw YAML into typed structures, then convert to the existing `PipelineDefinition` / `StepConfig` dataclasses that the executor consumes.

2. **Pipeline loader** (`src/squadron/pipeline/loader.py`) — Load a pipeline by name or path. Multi-source discovery: built-in (`data/pipelines/`), project (`project-documents/user/pipelines/`), user (`~/.config/squadron/pipelines/`). Name collision resolution: project overrides user overrides built-in.

3. **Pipeline validator** (integrated into loader + dedicated validation function) — Validates beyond schema: step types exist in registry, model aliases resolve, review templates exist, required params declared. Calls each step type's `validate()` method with the parsed config. Produces a list of `ValidationError` objects.

4. **Built-in pipeline definitions** (`src/squadron/data/pipelines/`) — Four YAML files:
   - `slice-lifecycle.yaml` — Full design → tasks → compact → implementation → devlog
   - `review-only.yaml` — Run a review against existing artifacts
   - `implementation-only.yaml` — When design and tasks already exist
   - `design-batch.yaml` — Phase 4 design across unfinished slices (uses `each` step)

5. **Pipeline listing** — Function to discover and list all available pipelines from all sources with their descriptions and source location.

6. **`sq run --validate`** — CLI surface for pre-execution validation (wired in slice 151, but the validation logic lives here).

### Excluded

- **Pipeline executor** — Slice 149. This slice produces validated `PipelineDefinition` objects; the executor consumes them.
- **Loop execution semantics** — Slice 149. The `each` step in `design-batch.yaml` is syntactically valid here but executed there.
- **`sq run` CLI command surface** — Slice 151. This slice provides the loader/validator functions; 151 wires them into Typer commands.
- **State persistence / resume** — Slice 150.

## Dependencies

### Prerequisites

- **Slice 142** (Pipeline Core Models) — `PipelineDefinition`, `StepConfig`, `ValidationError` dataclasses, step type registry, action registry. Complete.
- **Slice 147** (Step Types) — All step types registered: design, tasks, implement, compact, review, devlog. Their `validate()` methods are called during pipeline validation. Complete.
- **Pydantic v2** — Already in `pyproject.toml` dependencies. First use in the pipeline package.

### Interfaces Required

- `squadron.pipeline.steps.get_step_type()` — Look up step types by name for validation.
- `squadron.pipeline.steps.list_step_types()` — Enumerate registered step types.
- `squadron.pipeline.actions.get_action()` — Look up actions for action-level validation.
- `squadron.pipeline.resolver.ModelResolver` — Validate model aliases resolve.
- `squadron.models.aliases.resolve_model_alias()` — Direct alias resolution check.
- `squadron.data.data_dir()` — Locate built-in pipeline YAML files.
- `squadron.review.templates.get_template()` — Validate review template names exist.

## Architecture

### Component Structure

```
src/squadron/pipeline/
├── schema.py          # NEW: Pydantic models for YAML validation
├── loader.py          # NEW: Pipeline discovery, loading, validation
├── models.py          # EXISTING: PipelineDefinition, StepConfig (unchanged)
├── resolver.py        # EXISTING: ModelResolver (consumed, unchanged)

src/squadron/data/pipelines/
├── slice-lifecycle.yaml       # NEW: Built-in pipeline
├── review-only.yaml           # NEW: Built-in pipeline
├── implementation-only.yaml   # NEW: Built-in pipeline
└── design-batch.yaml          # NEW: Built-in pipeline
```

### Data Flow

```
YAML file on disk
  │
  ▼
yaml.safe_load() → raw dict
  │
  ▼
PipelineSchema.model_validate(raw) → Pydantic model (structural validation)
  │
  ▼
schema.to_definition() → PipelineDefinition + list[StepConfig] (dataclasses)
  │
  ▼
validate_pipeline(definition) → list[ValidationError] (semantic validation)
  │
  ▼
PipelineDefinition ready for executor (slice 149)
```

**Two-phase validation:**
1. **Structural** (Pydantic) — Required fields present, correct types, enum values valid, no unknown keys.
2. **Semantic** (validator) — Step types registered, model aliases resolve, review templates exist, step-level configs pass each step type's own `validate()`.

## Technical Decisions

### Pydantic for Schema, Dataclasses for Runtime

The pipeline YAML is an external boundary — Pydantic validates it. Once validated, the schema converts to the existing `PipelineDefinition` and `StepConfig` dataclasses that the rest of the pipeline system already uses. This follows the project's rule: Pydantic at boundaries, dataclasses for internal DTOs.

The `PipelineDefinition` and `StepConfig` dataclasses in `models.py` remain unchanged. The Pydantic schema is a parallel type that knows how to produce them.

### Step Config as Opaque Dict

Each step in the YAML is parsed as `{step_type_name: config_dict}`. The loader does not interpret step-level config beyond extracting the step type name — validation of step config is delegated to the step type's `validate()` method. This keeps the loader decoupled from step type internals.

### Param Declaration

Pipeline params use a simple schema:

```yaml
params:
  slice: required        # caller must provide
  model: opus            # default value; caller can override
```

A param value of the literal string `"required"` means the caller must supply it. Any other value is the default. This avoids a more complex param schema while being unambiguous — no real model alias or slice index would ever be the string "required".

### Discovery Precedence

Pipeline definitions are discovered from three locations, with later sources overriding earlier ones by name:

1. **Built-in** — `data_dir() / "pipelines/"` (lowest priority)
2. **User** — `~/.config/squadron/pipelines/` (overrides built-in)
3. **Project** — `{cwd}/project-documents/user/pipelines/` (highest priority)

This matches the review template and compaction template layering pattern.

### Step YAML Grammar

Each step is a single-key mapping where the key is the step type name:

```yaml
steps:
  - design:              # step type name is the key
      phase: 4           # step config is the value
      review: arch
      checkpoint: on-concerns

  - compact:
      keep: [design, tasks]
      summarize: true

  - devlog: auto         # shorthand: scalar value becomes {"mode": "auto"}
```

**Shorthand expansion:** When a step value is a scalar string instead of a mapping, it's expanded to `{"mode": value}`. This supports `devlog: auto` as shorthand for `devlog: {mode: auto}`.

**Step naming:** Steps are automatically named from their type and position (e.g., `design-0`, `compact-1`). An explicit `name` field in step config overrides this.

## Implementation Details

### Pydantic Schema (`schema.py`)

```python
class ParamSchema(BaseModel):
    """Single pipeline parameter declaration."""
    name: str
    default: str | None  # None means required

class StepSchema(BaseModel):
    """Single step as parsed from YAML."""
    step_type: str
    name: str | None = None
    config: dict[str, object]

class PipelineSchema(BaseModel):
    """Top-level pipeline definition validated from YAML."""
    name: str
    description: str = ""
    params: dict[str, str] = {}      # param_name -> "required" | default_value
    model: str | None = None         # pipeline-level default model
    steps: list[StepSchema]

    def to_definition(self) -> PipelineDefinition:
        """Convert validated schema to runtime PipelineDefinition."""
```

The `PipelineSchema` accepts the raw YAML structure. A custom `model_validator` (or `@field_validator`) handles the step list parsing — each step in the YAML is `{type_name: config_dict}`, which must be unpacked into `StepSchema(step_type=type_name, config=config_dict)`.

### Loader (`loader.py`)

Key functions:

```python
def load_pipeline(
    name_or_path: str,
    *,
    project_dir: Path | None = None,
    user_dir: Path | None = None,
) -> PipelineDefinition:
    """Load and validate a pipeline by name or file path."""

def discover_pipelines(
    *,
    project_dir: Path | None = None,
    user_dir: Path | None = None,
) -> list[PipelineInfo]:
    """Discover all available pipelines from all sources."""

def validate_pipeline(
    definition: PipelineDefinition,
) -> list[ValidationError]:
    """Semantic validation: step types, model aliases, templates."""
```

`PipelineInfo` is a small dataclass: `name`, `description`, `source` (built-in/user/project), `path`.

**Name resolution:** `load_pipeline("slice-lifecycle")` searches project → user → built-in directories for `slice-lifecycle.yaml`. `load_pipeline("/path/to/custom.yaml")` loads directly from the path.

### Built-in Pipeline Definitions

**`slice-lifecycle.yaml`:**
```yaml
name: slice-lifecycle
description: Full slice lifecycle — design through implementation

params:
  slice: required
  model: opus

steps:
  - design:
      phase: 4
      review: arch
      checkpoint: on-concerns

  - tasks:
      phase: 5
      review: tasks
      checkpoint: on-fail

  - compact:
      keep: [design, tasks]
      summarize: true

  - implement:
      phase: 6
      review:
        template: code
      checkpoint: on-fail

  - devlog: auto
```

**`review-only.yaml`:**
```yaml
name: review-only
description: Run a review against existing artifacts

params:
  slice: required
  template: required
  model: sonnet

steps:
  - review:
      template: "{template}"
      checkpoint: on-concerns
```

**`implementation-only.yaml`:**
```yaml
name: implementation-only
description: Implementation when design and tasks already exist

params:
  slice: required
  model: sonnet

steps:
  - implement:
      phase: 6
      review:
        template: code
      checkpoint: on-fail

  - devlog: auto
```

**`design-batch.yaml`:**
```yaml
name: design-batch
description: Run phase 4 design for every unfinished slice in a plan

params:
  plan: required
  model: opus

steps:
  - each:
      source: cf.unfinished_slices("{plan}")
      as: slice
      steps:
        - design:
            phase: 4
            slice: "{slice.index}"
            review: arch
            checkpoint: always
```

Note: The `each` step type is syntactically valid here (parsed and stored in `StepConfig`). Its execution semantics are slice 149 scope. Validation will skip unknown step types with a warning if the step type isn't registered yet, or the `each` step type stub will be registered during 149 implementation.

### Param Resolution in Step Configs

Step configs may contain `{param_name}` placeholders referencing pipeline params. The loader does **not** resolve these — param resolution happens at execution time (slice 149) when actual param values are available. The loader validates that referenced param names exist in the pipeline's `params` declaration.

## Integration Points

### Provides to Other Slices

- **Slice 149 (Executor):** `load_pipeline()` returns validated `PipelineDefinition` objects. The executor expands step types and runs action sequences.
- **Slice 150 (State/Resume):** `PipelineDefinition` is serializable. State file references the pipeline name for reload on resume.
- **Slice 151 (CLI):** `discover_pipelines()` powers `sq run --list`. `validate_pipeline()` powers `sq run --validate`. `load_pipeline()` is the entry point for `sq run <name>`.

### Consumes from Other Slices

- **Step type registry (147):** Validation checks that every step type name in the definition is registered.
- **Action registry (142–147):** Step type `validate()` methods may check action-level config.
- **Model alias registry (120):** Validation checks model aliases resolve.
- **Review template registry (105/141):** Validation checks template names exist.
- **`data_dir()` (141):** Locates built-in pipeline YAML files.

## Success Criteria

### Functional Requirements

- [ ] Pydantic schema validates well-formed pipeline YAML and rejects malformed input with clear errors
- [ ] Loader discovers pipelines from built-in, user, and project directories with correct precedence
- [ ] Four built-in pipeline definitions load and validate without errors
- [ ] `load_pipeline("slice-lifecycle")` returns a valid `PipelineDefinition` with correct steps
- [ ] `discover_pipelines()` returns all available pipelines with source attribution
- [ ] Semantic validation catches: unknown step types, unresolvable model aliases, missing review templates, undeclared param references
- [ ] Step shorthand expansion works (`devlog: auto` → `{mode: auto}`)
- [ ] Custom pipeline from project directory overrides built-in with same name

### Technical Requirements

- [ ] Pydantic models use v2 API (`model_validate`, `model_validator`)
- [ ] Schema converts cleanly to existing `PipelineDefinition` / `StepConfig` dataclasses
- [ ] All tests pass (`pytest`), pyright clean, ruff clean
- [ ] Loader accepts optional `user_dir` / `project_dir` params for testability (same pattern as template loaders)

### Verification Walkthrough

1. **Load a built-in pipeline:**
   ```python
   from squadron.pipeline.loader import load_pipeline
   defn = load_pipeline("slice-lifecycle")
   assert defn.name == "slice-lifecycle"
   assert len(defn.steps) == 5
   assert defn.steps[0].step_type == "design"
   ```

2. **Discover all pipelines:**
   ```python
   from squadron.pipeline.loader import discover_pipelines
   pipelines = discover_pipelines()
   names = [p.name for p in pipelines]
   assert "slice-lifecycle" in names
   assert "review-only" in names
   ```

3. **Validate a pipeline:**
   ```python
   from squadron.pipeline.loader import load_pipeline, validate_pipeline
   defn = load_pipeline("slice-lifecycle")
   errors = validate_pipeline(defn)
   assert errors == []  # built-in definitions should be clean
   ```

4. **Reject malformed YAML:**
   ```python
   # Missing required 'name' field
   import yaml
   from squadron.pipeline.schema import PipelineSchema
   from pydantic import ValidationError
   raw = yaml.safe_load("steps: []")
   try:
       PipelineSchema.model_validate(raw)
       assert False, "Should have raised"
   except ValidationError:
       pass  # expected
   ```

5. **Run tests:**
   ```bash
   cd /Users/manta/source/repos/manta/squadron
   python -m pytest tests/pipeline/ -v
   pyright src/squadron/pipeline/schema.py src/squadron/pipeline/loader.py
   ruff check src/squadron/pipeline/
   ```

## Implementation Notes

### Development Approach

Suggested implementation order:
1. Pydantic schema models (`schema.py`) with unit tests
2. Built-in pipeline YAML files (`data/pipelines/`)
3. Loader with discovery and name resolution (`loader.py`) with unit tests
4. Semantic validation with integration tests
5. End-to-end: load each built-in pipeline, validate, confirm step expansion

### Testing Strategy

- **Schema tests:** Valid YAML parses, invalid YAML raises `ValidationError`, edge cases (empty steps, shorthand expansion, missing fields).
- **Loader tests:** Discovery from multiple directories (via `tmp_path` fixtures), name collision precedence, path-based loading, missing pipeline error.
- **Validation tests:** Known step types pass, unknown step types fail, model alias resolution, review template existence, param reference checking.
- **Integration tests:** Load each built-in pipeline, validate, convert to `PipelineDefinition`, confirm `StepConfig` fields.
