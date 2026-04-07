---
docType: slice-design
parent: 140-arch.pipeline-foundation.md
slicePlan: 140-slices.pipeline-foundation.md
project: squadron
sliceIndex: 142
sliceName: pipeline-core-models-and-action-protocol
dateCreated: 20260330
dateUpdated: 20260330
status: complete
slice: pipeline-core-models-and-action-protocol
---

# Slice Design: Pipeline Core Models and Action Protocol (142)

## Overview

This slice creates the foundational scaffolding for the pipeline system:
the data models, protocols, and registries that every subsequent pipeline
slice builds on.  Nothing executes yet — this is the load-bearing frame
on which actions (143–147), step types (147), definitions (148), and the
executor (149) will hang.

**Slice plan entry:** **(142) Pipeline Core Models and Action Protocol** —
Pydantic models for pipeline infrastructure (PipelineDefinition, StepConfig,
ActionContext, ActionResult).  Action protocol and action registry.  StepType
protocol and step type registry.  Model resolver with cascade chain (5 levels).
Package scaffolding for `src/squadron/pipeline/` matching the architecture's
package structure.  Pool prefix (`pool:`) acknowledged in resolver interface
but not implemented (180 scope).
Dependencies: [100-band complete].  Risk: Low.  Effort: 2/5

---

## Scope

### In scope

- Create `src/squadron/pipeline/` package with full directory tree matching
  architecture (empty action/step modules as stubs)
- `pipeline/models.py` — core data models: `ActionContext`, `ActionResult`,
  `PipelineDefinition`, `StepConfig`, `ValidationError`
- `pipeline/actions/protocol.py` — `Action` protocol definition
- `pipeline/actions/__init__.py` — registry functions: `register_action`,
  `get_action`, `list_actions`; action type constant enum
- `pipeline/steps/protocol.py` — `StepType` protocol definition
- `pipeline/steps/__init__.py` — registry functions: `register_step_type`,
  `get_step_type`, `list_step_types`; step type constant enum
- `pipeline/resolver.py` — `ModelResolver` with 5-level cascade chain
  (CLI override, action, step, pipeline, config default); `pool:` prefix
  recognized and raises `ModelPoolNotImplemented` error
- `pipeline/__init__.py` — package entry exposing public surface
- Stub modules for future actions (dispatch, review, compact, checkpoint,
  cf_op, commit, devlog) and step types (phase, compact, review, collection,
  devlog) — empty modules with a single `# TODO: slice NNN` comment
- Tests: unit tests for `ActionContext`, `ActionResult`, `ValidationError`,
  the registry functions, and the resolver cascade

### Out of scope

- Any actual action implementation (144–147)
- Any actual step type implementation (147)
- YAML pipeline definition loading (148)
- Executor (149)
- State persistence (150)
- CLI integration (151)
- Structured review findings extraction (143)

---

## Data Models (`pipeline/models.py`)

All models in this file use `@dataclass` — they are internal DTOs, not
external-boundary types.  No Pydantic in this file.  Pydantic is reserved
for YAML loading in slice 148 and any external API surfaces.

### `ValidationError`

```python
@dataclass
class ValidationError:
    """A single configuration validation error from an Action or StepType."""
    field: str          # dotted field path, e.g. "review.model"
    message: str        # human-readable description
    action_type: str    # which action/step reported the error
```

### `ActionContext`

Carries everything an action may need during execution.  A struct, not a
service locator.  Actions pull what they need and ignore the rest.

```python
@dataclass
class ActionContext:
    """Execution context passed to every action."""
    pipeline_name: str
    run_id: str
    params: dict[str, object]         # resolved pipeline params (slice, model, …)
    step_name: str                    # name of the currently executing step
    step_index: int                   # 0-based position in the step sequence
    prior_outputs: dict[str, object]  # keyed by step name → step output dict
    resolver: ModelResolver           # model resolution service (forward ref)
    cf_client: object                 # ContextForgeClient (typed as object here;
                                      # real type imported in actions that use it)
    cwd: str                          # working directory for file operations
```

`cf_client` is typed as `object` in the models module to avoid a circular
import between `pipeline/models.py` and `integrations/context_forge.py`.
Actions that use it import `ContextForgeClient` directly and cast.

### `ActionResult`

```python
@dataclass
class ActionResult:
    """Typed result from an action execution."""
    success: bool
    action_type: str
    outputs: dict[str, object]     # action-specific data (file paths, verdicts, …)
    error: str | None = None       # error message on failure
    metadata: dict[str, object] = field(default_factory=dict)
    # Populated by review action (slice 143):
    verdict: str | None = None     # PASS | CONCERNS | FAIL | UNKNOWN
    findings: list[object] = field(default_factory=list)  # structured findings
```

`verdict` and `findings` are pre-declared here so the executor can read them
uniformly without knowing whether the action was a review.  Review action
(slice 143) will populate them.  Default is `None`/`[]` for non-review actions.

`findings` is typed as `list[object]` to avoid importing structured finding
types from the review module.  Slice 143 will define `StructuredFinding`; the
executor reads `verdict` as a plain string and treats `findings` as opaque
until 143 lands.

### `StepConfig`

Thin data bag for one YAML step entry, used by step type implementations:

```python
@dataclass
class StepConfig:
    """Raw configuration for a single pipeline step."""
    step_type: str                  # e.g. "design", "compact", "each"
    name: str                       # user-facing step name (or auto-generated)
    config: dict[str, object]       # step-type-specific parameters from YAML
```

### `PipelineDefinition`

Minimal model for a parsed pipeline.  Slice 148 will replace/extend this with
a Pydantic model that adds full YAML validation.  The version here is only
enough to satisfy the resolver and registries.

```python
@dataclass
class PipelineDefinition:
    """A loaded pipeline definition."""
    name: str
    description: str
    params: dict[str, object]       # declared params with defaults
    steps: list[StepConfig]
    model: str | None = None        # pipeline-level model default
```

---

## Action Protocol (`pipeline/actions/protocol.py`)

Mirrors the `Agent` and `AgentProvider` protocols in `providers/base.py`.
`@runtime_checkable` so the registry can use `isinstance` for duck-type
verification.

```python
@runtime_checkable
class Action(Protocol):
    """A discrete, typed operation that a pipeline can execute."""

    @property
    def action_type(self) -> str:
        """Identifier for this action type (e.g. 'dispatch', 'review')."""
        ...

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action and return a typed result."""
        ...

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """Validate configuration before execution.

        Called during ``sq run --validate``.  Returns an empty list if config
        is valid.
        """
        ...
```

### `ActionType` enum

```python
class ActionType(StrEnum):
    """Known action type identifiers."""
    DISPATCH   = "dispatch"
    REVIEW     = "review"
    COMPACT    = "compact"
    CHECKPOINT = "checkpoint"
    CF_OP      = "cf-op"
    COMMIT     = "commit"
    DEVLOG     = "devlog"
```

This enum is the canonical list.  No code should match on raw strings.
Custom actions registered by users will not appear here — they use their own
string identifiers.  The registry accepts any string key.

---

## Action Registry (`pipeline/actions/__init__.py`)

Same pattern as `providers/registry.py`:

```python
_REGISTRY: dict[str, Action] = {}

def register_action(action_type: str, action: Action) -> None: ...
def get_action(action_type: str) -> Action: ...  # raises KeyError on miss
def list_actions() -> list[str]: ...
```

Registration happens at module import time in each action module (slice 144+).
The registry is open — users can register custom action types.

---

## StepType Protocol (`pipeline/steps/protocol.py`)

```python
@runtime_checkable
class StepType(Protocol):
    """A named expansion from a step config to an action sequence."""

    @property
    def step_type(self) -> str:
        """Identifier for this step type (e.g. 'design', 'compact')."""
        ...

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Expand a step config into (action_type, action_config) pairs.

        The executor calls this to get the action sequence to run.
        Each tuple: (action_type_string, config_dict_for_that_action).
        """
        ...

    def validate(self, config: StepConfig) -> list[ValidationError]:
        """Validate step configuration before execution."""
        ...
```

### `StepTypeName` enum

```python
class StepTypeName(StrEnum):
    """Known built-in step type identifiers."""
    DESIGN     = "design"
    TASKS      = "tasks"
    IMPLEMENT  = "implement"
    COMPACT    = "compact"
    REVIEW     = "review"
    EACH       = "each"
    DEVLOG     = "devlog"
```

---

## StepType Registry (`pipeline/steps/__init__.py`)

Same registry pattern as actions:

```python
_REGISTRY: dict[str, StepType] = {}

def register_step_type(step_type: str, impl: StepType) -> None: ...
def get_step_type(step_type: str) -> StepType: ...   # raises KeyError on miss
def list_step_types() -> list[str]: ...
```

---

## Model Resolver (`pipeline/resolver.py`)

### Interface

```python
class ModelResolver:
    """Resolves model references through the 5-level cascade chain.

    Cascade order (first non-None wins, highest to lowest priority):
      1. CLI runtime override  (set once at pipeline start)
      2. Action-level model    (passed per resolve() call)
      3. Step-level model      (passed per resolve() call)
      4. Pipeline-level model  (set once at pipeline start)
      5. Config default        (loaded from ~/.config/squadron/config.toml)
    """

    def __init__(
        self,
        cli_override: str | None = None,
        pipeline_model: str | None = None,
        config_default: str | None = None,
    ) -> None: ...

    def resolve(
        self,
        action_model: str | None = None,
        step_model: str | None = None,
    ) -> tuple[str, str | None]:
        """Return (resolved_model_id, profile_or_none).

        Raises ModelResolutionError if no level supplies a model.
        Raises ModelPoolNotImplemented if the resolved alias starts with 'pool:'.
        """
        ...
```

Resolution delegates to `resolve_model_alias()` from
`squadron.models.aliases` for the final alias → `(model_id, profile)` lookup.

### Error types

```python
class ModelResolutionError(Exception):
    """Raised when no cascade level supplies a model."""

class ModelPoolNotImplemented(Exception):
    """Raised when a pool: reference is encountered (160 scope)."""
```

Both live in `pipeline/resolver.py`.

### Cascade logic (pseudo-code)

```python
def resolve(self, action_model=None, step_model=None):
    for candidate in (
        self._cli_override,
        action_model,
        step_model,
        self._pipeline_model,
        self._config_default,
    ):
        if candidate is not None:
            if candidate.startswith("pool:"):
                raise ModelPoolNotImplemented(
                    f"Model pools require Pipeline Intelligence (initiative 160). "
                    f"Got: {candidate!r}"
                )
            return resolve_model_alias(candidate)
    raise ModelResolutionError(
        "No model specified at any cascade level. "
        "Set a pipeline default, step model, or --model flag."
    )
```

---

## Package Structure Created by This Slice

```
src/squadron/pipeline/
├── __init__.py              # public surface: re-exports key types
├── models.py                # ActionContext, ActionResult, PipelineDefinition,
│                            # StepConfig, ValidationError
├── resolver.py              # ModelResolver, ModelResolutionError,
│                            # ModelPoolNotImplemented
├── actions/
│   ├── __init__.py          # register_action, get_action, list_actions, ActionType
│   ├── protocol.py          # Action protocol
│   ├── dispatch.py          # stub — slice 145
│   ├── review.py            # stub — slice 146
│   ├── compact.py           # stub — slice 147
│   ├── checkpoint.py        # stub — slice 146
│   ├── cf_op.py             # stub — slice 144
│   ├── commit.py            # stub — slice 144
│   └── devlog.py            # stub — slice 144
└── steps/
    ├── __init__.py          # register_step_type, get_step_type, list_step_types,
    │                        # StepTypeName
    ├── protocol.py          # StepType protocol
    ├── phase.py             # stub — slice 147 (design/tasks/implement)
    ├── compact.py           # stub — slice 147
    ├── review.py            # stub — slice 147
    ├── collection.py        # stub — slice 149 (each loop)
    └── devlog.py            # stub — slice 147
```

Stub modules contain only a `# TODO: slice NNN — not yet implemented` comment
and a module-level docstring.  They exist so the package imports cleanly and
pyright sees the expected layout.

---

## `pipeline/__init__.py` Public Surface

Re-exports the types downstream callers will import most frequently:

```python
from squadron.pipeline.models import (
    ActionContext,
    ActionResult,
    PipelineDefinition,
    StepConfig,
    ValidationError,
)
from squadron.pipeline.resolver import (
    ModelResolver,
    ModelResolutionError,
    ModelPoolNotImplemented,
)
from squadron.pipeline.actions import ActionType
from squadron.pipeline.steps import StepTypeName
```

---

## Cross-Slice Interfaces

**Slice 143 (Structured Review Findings):** Will add `StructuredFinding`
dataclass and populate `ActionResult.findings`.  No change to `ActionResult`
interface — fields are already declared.

**Slice 144 (Utility Actions):** First actual action implementations.  They
`register_action()` on import.  `ActionContext.cf_client` becomes actively
used here — `ContextForgeClient` type import happens inside `cf_op.py`.

**Slice 145 (Dispatch Action):** Uses `ActionContext.resolver` to call
`ModelResolver.resolve()` and `ActionContext.cf_client` to build context.

**Slice 147 (Compact Action and Step Types):** Implements all step type
modules, replacing stubs.  Calls `register_step_type()` on import.

**Slice 148 (Pipeline Definitions and Loader):** Replaces `PipelineDefinition`
with a Pydantic model for YAML validation, or extends it.  The dataclass
version defined here is the interim internal representation that 148 produces
after parsing.

**Slice 149 (Pipeline Executor and Loops):** Consumes `StepType.expand()` to
get action sequences.  Uses `ActionContext` as the shared execution struct.

**`config/keys.py`:** `ModelResolver` reads `default_model` from the config
manager on construction.  No new config keys needed in this slice.

---

## Success Criteria

1. `src/squadron/pipeline/` exists with all files listed in the package
   structure above (models, protocols, registries, resolver, stubs)
2. `from squadron.pipeline import ActionContext, ActionResult, ModelResolver`
   works without error
3. `register_action` / `get_action` round-trip: register an object that
   satisfies `Action`, retrieve by type string, verify `isinstance(obj, Action)`
4. `register_step_type` / `get_step_type` round-trip analogously
5. `ModelResolver` cascade: given levels set at different priorities, `resolve()`
   returns the highest-priority non-None value after alias resolution
6. `ModelResolver.resolve()` raises `ModelPoolNotImplemented` on `pool:` prefix
7. `ModelResolver.resolve()` raises `ModelResolutionError` when all levels are None
8. `pyright` clean — zero new type errors introduced
9. `uv run pytest` passes (all existing tests continue to pass; new unit tests pass)

---

## Verification Walkthrough

```bash
# 1. Package structure exists
find src/squadron/pipeline -type f | sort
# Actual output (verified 2026-03-30, Python 3.13.3):
# src/squadron/pipeline/__init__.py
# src/squadron/pipeline/actions/__init__.py
# src/squadron/pipeline/actions/cf_op.py
# src/squadron/pipeline/actions/checkpoint.py
# src/squadron/pipeline/actions/commit.py
# src/squadron/pipeline/actions/compact.py
# src/squadron/pipeline/actions/devlog.py
# src/squadron/pipeline/actions/dispatch.py
# src/squadron/pipeline/actions/protocol.py
# src/squadron/pipeline/actions/review.py
# src/squadron/pipeline/models.py
# src/squadron/pipeline/resolver.py
# src/squadron/pipeline/steps/__init__.py
# src/squadron/pipeline/steps/collection.py
# src/squadron/pipeline/steps/compact.py
# src/squadron/pipeline/steps/devlog.py
# src/squadron/pipeline/steps/phase.py
# src/squadron/pipeline/steps/protocol.py
# src/squadron/pipeline/steps/review.py

# 2. Top-level imports work
uv run python -c "
from squadron.pipeline import (
    ActionContext, ActionResult, PipelineDefinition,
    StepConfig, ValidationError, ModelResolver,
    ModelResolutionError, ModelPoolNotImplemented,
    ActionType, StepTypeName,
)
print('imports OK')
"
# → imports OK

# 3. Resolver cascade
uv run python -c "
from squadron.pipeline.resolver import ModelResolver
r = ModelResolver(pipeline_model='sonnet')
model_id, profile = r.resolve()
print(model_id, profile)
"
# → claude-sonnet-4-6 sdk

# 4. Pool prefix raises
uv run python -c "
from squadron.pipeline.resolver import ModelResolver, ModelPoolNotImplemented
r = ModelResolver(pipeline_model='pool:high')
try:
    r.resolve()
except ModelPoolNotImplemented as e:
    print('pool: correctly blocked:', e)
"
# → pool: correctly blocked: Pool-based model selection is not yet implemented (slate 160): 'pool:high'

# 5. No model raises
uv run python -c "
from squadron.pipeline.resolver import ModelResolver, ModelResolutionError
r = ModelResolver()
try:
    r.resolve()
except ModelResolutionError as e:
    print('empty cascade correctly raised:', e)
"
# → empty cascade correctly raised: No model could be resolved: all cascade levels are None. Set a pipeline model, config default, or pass --model.

# 6. Tests
uv run pytest tests/pipeline/ -v
# → 26 passed in 0.03s

# 7. Pyright
uv run pyright src/squadron/pipeline/
# → 0 errors, 0 warnings, 0 informations
```

---

## Notes

- **No Pydantic in `models.py`.** These are internal DTOs that never cross
  an external boundary in this slice.  Pydantic enters in slice 148 for YAML
  parsing.  Mixing the two in one file creates unnecessary cognitive overhead.

- **`cf_client: object` in `ActionContext`.** The `ContextForgeClient` type
  lives in `squadron.integrations.context_forge`.  Importing it into
  `pipeline/models.py` would create a cross-package dependency from the pipeline
  core models to the integrations layer.  Typing it as `object` here and letting
  each action module cast is the cleaner boundary.  An alternative is a protocol
  `ContextForgeProtocol` defined in `pipeline/` — defer unless more than one
  CF client implementation emerges.

- **Registry singletons are module-level dicts.** Same pattern as
  `providers/registry.py`.  No class needed.  The registry is global state, but
  it is populated once at startup (module imports) and read-only during execution.

- **Stub modules import cleanly.** Each stub is a valid Python file with a
  docstring and a comment.  This ensures `pyright` and `pytest` collection
  succeed with no "module not found" errors when later slices reference them.

- **`findings: list[object]`** — using `object` avoids importing
  `ReviewFinding` from the review module.  When slice 143 defines
  `StructuredFinding`, it can be stored here and retrieved by callers that know
  the type.  This is intentional loose coupling, not a design flaw.
