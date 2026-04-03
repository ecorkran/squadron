---
docType: slice-design
slice: compact-action-and-step-types
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [144, 145, 146]
interfaces: [148, 149]
dateCreated: 20260402
dateUpdated: 20260402
status: not_started
---

# Slice 147: Compact Action and Step Types

## Overview

Implement the compact action and four step type implementations that bridge the terse YAML pipeline grammar (slice 148) to the action layer (slices 142–146). Each step type's `expand()` method translates step-level YAML config into a concrete sequence of `(action_type, action_config)` tuples that the executor (slice 149) will run sequentially.

## Value

- **Pipeline-ready action set complete.** After this slice, every action type defined in the architecture is implemented: dispatch, review, checkpoint, cf-op, commit, devlog, and now compact.
- **Step types as the composition layer.** Step types encode the canonical action sequences (e.g., phase step = cf-op → dispatch → review → checkpoint → commit) so that pipeline definitions in slice 148 can express intent at a high level while the step type handles the expansion details.
- **Compact action enables context management.** Long-running multi-phase pipelines accumulate context. The compact action issues parameterized compaction instructions to Context Forge, preserving designated artifacts while summarizing the rest.

## Technical Scope

### Included

1. **Compact action** (`src/squadron/pipeline/actions/compact.py`) — Issue compaction instructions to CF with configurable preservation rules.
2. **Phase step type** (`src/squadron/pipeline/steps/phase.py`) — Expands to: cf-op(set_phase) → cf-op(build) → dispatch → review → checkpoint → commit. Handles optional review/checkpoint/model config.
3. **Compact step type** (`src/squadron/pipeline/steps/compact.py`) — Translates high-level params (`keep`, `summarize`) into compact action config.
4. **Review step type** (`src/squadron/pipeline/steps/review.py`) — Standalone review + optional checkpoint sequence.
5. **Devlog step type** (`src/squadron/pipeline/steps/devlog.py`) — Single devlog action with mode support (`auto` or explicit content).
6. **Step type auto-registration** — Each step type module registers itself at import time (same pattern as actions).
7. **Registry integration tests** — Verify all step types coexist in the registry.

### Excluded

- **Collection/each step type** — Slice 149 scope (depends on executor loop semantics).
- **Pipeline YAML loading/validation** — Slice 148 scope.
- **Pipeline executor** — Slice 149 scope. Step types produce expansion data; the executor consumes it.
- **Built-in pipeline definitions** — Slice 148 scope.

## Dependencies

### Prerequisites

- **Slice 142** (Pipeline Core Models) — `StepConfig`, `ActionResult`, `ActionContext`, `ValidationError`, `StepType` protocol, registries. Complete.
- **Slice 144** (Utility Actions) — `cf-op`, `commit`, `devlog` actions. Complete.
- **Slice 145** (Dispatch Action) — `dispatch` action. Complete.
- **Slice 146** (Review and Checkpoint Actions) — `review`, `checkpoint` actions. Complete.

### Interfaces Required

- `ActionType` enum values for all action types (from `pipeline/actions/__init__.py`)
- `StepTypeName` enum values (from `pipeline/steps/__init__.py`)
- `StepConfig` dataclass (from `pipeline/models.py`)
- `ValidationError` dataclass (from `pipeline/models.py`)
- `ContextForgeClient._run()` for compact action CF commands
- `CfOperation` enum from `pipeline/actions/cf_op.py` for reference

## Architecture

### Component Structure

```
pipeline/actions/
  compact.py          ← NEW: CompactAction implementation

pipeline/steps/
  phase.py            ← NEW: PhaseStepType implementation
  compact.py          ← NEW: CompactStepType implementation
  review.py           ← NEW: ReviewStepType implementation
  devlog.py           ← NEW: DevlogStepType implementation
```

### Data Flow

```
StepConfig (from YAML, slice 148)
    │
    ▼
StepType.expand(config)
    │
    ▼
list[(action_type, action_config)]
    │
    ▼
Executor runs actions sequentially (slice 149)
```

Step types are pure data transformers — they take a `StepConfig` and return a list of `(action_type, action_config)` tuples. No I/O, no side effects, no async. This makes them trivially testable.

### Step Type Expansion Patterns

#### Phase Step Type (`design`, `tasks`, `implement`)

The phase step type handles three named phases that share the same expansion pattern but differ in defaults:

```python
# Input StepConfig.config:
{
    "phase": 4,                       # required: CF phase number
    "model": "opus",                  # optional: dispatch model override
    "review": "slice",                # optional: review template name (str or dict)
    "checkpoint": "on-concerns",      # optional: checkpoint trigger
}

# review can also be a dict for action-level model override:
{
    "review": {
        "template": "code",
        "model": "minimax2.7",        # action-level model override
    }
}

# Expansion:
[
    ("cf-op", {"operation": "set_phase", "phase": 4}),
    ("cf-op", {"operation": "build_context"}),
    ("dispatch", {"model": "opus"}),
    ("review", {"template": "slice", "model": None}),
    ("checkpoint", {"trigger": "on-concerns"}),
    ("commit", {"message_prefix": "phase-4"}),
]
```

When `review` is omitted, the review and checkpoint actions are omitted from the expansion. When `checkpoint` is omitted but `review` is present, checkpoint defaults to `"never"` (review runs but no pause).

#### Compact Step Type

```python
# Input StepConfig.config:
{
    "keep": ["design", "tasks"],      # optional: artifacts to preserve
    "summarize": True,                # optional: update CF summary
}

# Expansion:
[
    ("compact", {"keep": ["design", "tasks"], "summarize": True}),
]
```

#### Review Step Type (Standalone)

```python
# Input StepConfig.config:
{
    "template": "code",               # required: review template name
    "model": "minimax2.7",            # optional: model override
    "checkpoint": "on-fail",          # optional: checkpoint trigger
}

# Expansion:
[
    ("review", {"template": "code", "model": "minimax2.7"}),
    ("checkpoint", {"trigger": "on-fail"}),
]
```

When `checkpoint` is omitted, the checkpoint action is omitted.

#### Devlog Step Type

```python
# Input StepConfig.config:
{
    "mode": "auto",                   # "auto" or "explicit"
    "content": "...",                 # required when mode is "explicit"
}

# For shorthand `devlog: auto`:
# StepConfig.config = {"mode": "auto"}

# Expansion:
[
    ("devlog", {"mode": "auto"}),
]
```

## Technical Decisions

### Compact Action: CF Command Interface

The compact action needs to issue compaction instructions to CF. The existing `ContextForgeClient` doesn't have a dedicated `compact()` method — the `summarize` command is the closest operation, already exposed via `CfOperation.SUMMARIZE`.

**Decision:** The compact action will:
1. Call `cf summarize` via the existing `CfOperation.SUMMARIZE` path for the summarize operation.
2. For `keep` parameters, pass them as arguments to the CF CLI: `cf context summarize --keep design,tasks` (or equivalent CF syntax). If CF doesn't support `--keep` flags directly, the compact action will construct the appropriate CF command.
3. The compact action will validate `keep` values against a known set of artifact names.

If the CF CLI's `summarize` command doesn't support `--keep`, the compact action will issue the compaction as a custom instruction via `cf_client._run(["context", "summarize"])` with appropriate arguments. The action is the integration layer — it adapts pipeline-level semantics to CF-level commands.

### Step Type Registration Pattern

Each step type module registers at import time, following the action pattern:

```python
# At bottom of each step type module:
register_step_type(StepTypeName.DESIGN, PhaseStepType("design"))
register_step_type(StepTypeName.TASKS, PhaseStepType("tasks"))
register_step_type(StepTypeName.IMPLEMENT, PhaseStepType("implement"))
```

The phase step type is instantiated three times (once per phase name) with a `phase_name` parameter that determines defaults. All three share the same class.

### Validation Rules

Each step type's `validate()` method checks that required config keys are present and values are acceptable. Validation errors reference the step type and field.

| Step Type | Required Config | Optional Config |
|-----------|----------------|-----------------|
| Phase | `phase` (int) | `model`, `review` (str or dict), `checkpoint` (trigger value) |
| Compact | (none) | `keep` (list of str), `summarize` (bool) |
| Review | `template` (str) | `model`, `checkpoint` (trigger value) |
| Devlog | (none) | `mode` ("auto" or "explicit"), `content` (str, required if explicit) |

## Integration Points

### Provides to Other Slices

- **Slice 148 (Pipeline Definitions):** Step types that the loader validates against and the executor expands. The step type registry is the contract — if a step type name appears in YAML, it must be registered.
- **Slice 149 (Pipeline Executor):** The executor calls `step_type.expand(config)` to get action sequences, then runs them. Expansion is synchronous and side-effect-free.

### Consumes from Other Slices

- **Slice 142:** `StepConfig`, `ValidationError`, `StepType` protocol, `StepTypeName` enum, registry functions.
- **Slices 144–146:** `ActionType` enum values used as the first element of expansion tuples.

## Success Criteria

### Functional Requirements

- [ ] Compact action issues CF compaction commands with configurable `keep` and `summarize` parameters.
- [ ] Compact action validates its config (at minimum, `keep` values are lists of strings if present).
- [ ] Phase step type expands to the canonical 6-action sequence: cf-op(set_phase) → cf-op(build) → dispatch → review → checkpoint → commit.
- [ ] Phase step type omits review+checkpoint actions when `review` is not configured.
- [ ] Phase step type handles review as both a string (template name) and dict (template + model override).
- [ ] Phase step type registers for all three phase names: `design`, `tasks`, `implement`.
- [ ] Compact step type expands to a single compact action with translated params.
- [ ] Review step type expands to review + optional checkpoint.
- [ ] Devlog step type expands to a single devlog action with mode passthrough.
- [ ] All step types validate their config and return `ValidationError` lists.
- [ ] All step types and the compact action are auto-registered at import time.
- [ ] Registry integration tests verify all 7 step types (design, tasks, implement, compact, review, each, devlog) and all 7 actions are discoverable. Note: `each` is registered in slice 149; if its stub doesn't register, test for the 6 that do.

### Technical Requirements

- [ ] Each implementation follows the existing action/step type patterns (protocol compliance, module-level registration).
- [ ] Unit tests cover all expansion paths and validation cases.
- [ ] `ruff check` and `ruff format` pass.
- [ ] `pyright` passes with no new errors.
- [ ] All existing tests continue to pass.

### Verification Walkthrough

1. **Run unit tests for compact action:**
   ```bash
   uv run pytest tests/pipeline/actions/test_compact.py -v
   ```
   Expect: All tests pass — happy path, keep/summarize params, validation, CF errors.

2. **Run unit tests for step types:**
   ```bash
   uv run pytest tests/pipeline/steps/ -v
   ```
   Expect: All tests pass — expansion for each step type, validation, edge cases.

3. **Run registry integration tests:**
   ```bash
   uv run pytest tests/pipeline/actions/test_registry_integration.py -v
   uv run pytest tests/pipeline/steps/test_registry_integration.py -v
   ```
   Expect: All registered actions and step types are discoverable.

4. **Run full test suite:**
   ```bash
   uv run pytest --tb=short -q
   ```
   Expect: No regressions.

5. **Verify type checking:**
   ```bash
   uv run pyright src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/
   ```

## Implementation Notes

### Development Order

1. Compact action (standalone, no step type dependency)
2. Phase step type (most complex expansion, covers the core pattern)
3. Compact step type (simple, one-action expansion)
4. Review step type (review + optional checkpoint)
5. Devlog step type (simplest, one-action expansion)
6. Registry integration tests
7. Verification and cleanup
