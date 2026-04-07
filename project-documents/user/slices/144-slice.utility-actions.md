---
docType: slice-design
parent: 140-arch.pipeline-foundation.md
slicePlan: 140-slices.pipeline-foundation.md
project: squadron
sliceIndex: 144
sliceName: utility-actions
dependencies: [142]
interfaces: [147]
dateCreated: 20260331
dateUpdated: 20260331
status: complete
slice: utility-actions
---

# Slice Design: Utility Actions (144)

## Overview

This slice implements three simple action types — `cf-op`, `commit`, and `devlog` — that validate the action protocol (slice 142) against well-defined, deterministic operations. These are the first concrete `Action` implementations in the pipeline system. Each wraps an existing capability (ContextForgeClient, git, file I/O) behind the action protocol interface.

**Slice plan entry:** **(144) Utility Actions** — Implement three simple actions that validate the action protocol against well-defined operations: cf-op action (set phase, build context, summarize via ContextForgeClient), commit action (git commit at phase boundaries with semantic message conventions), and devlog action (structured DEVLOG entries auto-generated from pipeline state). Dependencies: [142, CF Integration (126)]. Risk: Low. Effort: 2/5

---

## Value

- **First real actions in the pipeline.** Until now, the action protocol is scaffolding with empty stubs. These three implementations prove the protocol works against real I/O operations.
- **Independently useful.** Even before the pipeline executor exists (slice 149), each action can be instantiated and `execute()`-d from tests or future CLI integration.
- **Unblocks step types.** Slice 147 (Compact Action and Step Types) depends on these three actions being operational — the phase step type expands to a sequence that includes `cf-op`, `commit`, and `devlog`.

---

## Scope

### In scope

- **`cf_op.py`** — `CfOpAction` implementation: delegates to `ContextForgeClient` for `set_phase`, `build_context`, and `summarize` operations. Validates that `operation` is a known operation name and that required parameters are present.
- **`commit.py`** — `CommitAction` implementation: stages changed files and creates a git commit with a semantic message. Validates that `cwd` is a git repository.
- **`devlog.py`** — `DevlogAction` implementation: appends a structured entry to `DEVLOG.md`. Generates content from pipeline state (completed steps, review verdicts, model used) or accepts explicit content.
- **Registration:** Each action auto-registers with the action registry at import time.
- **Tests:** Unit tests for each action with mocked I/O boundaries.

### Out of scope

- Step type implementations (slice 147)
- Pipeline executor integration (slice 149)
- The `compact` action (slice 147 — distinct from `cf-op`'s `summarize`)
- CF client modifications — the existing `ContextForgeClient` interface is consumed as-is

---

## Dependencies

### Prerequisites

- **Slice 142 (Pipeline Core Models)** — `Action` protocol, `ActionType` enum, `ActionContext`, `ActionResult`, `ValidationError`, action registry. All complete.
- **Slice 126 (CF Integration)** — `ContextForgeClient` with `_run()` subprocess interface. Complete.

### Interfaces Required

- **`ActionContext`** — provides `cf_client`, `cwd`, `params`, `step_name`, `prior_outputs`
- **`ActionResult`** — standard return type with `success`, `action_type`, `outputs`, `error`, `metadata`
- **`ContextForgeClient`** — `_run(args)` for CF CLI operations
- **Action registry** — `register_action()` for self-registration

---

## Architecture

### Component Structure

```
src/squadron/pipeline/actions/
├── cf_op.py        # CfOpAction — CF operations via ContextForgeClient
├── commit.py       # CommitAction — git commit at boundaries
└── devlog.py       # DevlogAction — structured DEVLOG entries
```

Each action module follows the same pattern:

1. A class implementing the `Action` protocol
2. Module-level auto-registration: `register_action(ActionType.X, XAction())`
3. No direct imports from other action modules

### Data Flow

```
ActionContext
  ├── params (operation-specific config from step/pipeline)
  ├── cf_client (ContextForgeClient instance)
  ├── cwd (working directory)
  ├── prior_outputs (results from earlier actions in the step)
  └── pipeline_name, run_id, step_name (metadata for logging/devlog)
       │
       ▼
  Action.execute(context)
       │
       ├── cf_op:   context.cf_client._run([...]) → stdout
       ├── commit:  subprocess git add/commit → returncode
       └── devlog:  read DEVLOG.md → append entry → write
       │
       ▼
  ActionResult
    success: bool
    action_type: str
    outputs: { operation-specific key-value pairs }
    error: str | None
    metadata: { timing, details }
```

---

## Technical Decisions

### CF Client Interaction Pattern

The `ContextForgeClient` currently exposes `_run(args)` and `_run_json(args)` as the core subprocess interface. The `cf-op` action needs operations not currently on the public API:
- `cf set phase <N>` — set project phase
- `cf build` — build context
- `cf summarize` — summarize context (via `context_summarize` MCP tool or equivalent CLI)

**Decision:** The `CfOpAction` calls `cf_client._run()` directly with the appropriate CLI args rather than adding new public methods to `ContextForgeClient`. This keeps the client interface minimal and avoids churn on a stable class. The action itself is the typed interface for these operations.

**Alternative considered:** Adding `set_phase()`, `build_context()`, `summarize()` to `ContextForgeClient`. Rejected — these are pipeline-specific orchestration methods that don't belong on a general-purpose CF client. If other consumers need them, they can be promoted later.

### Git Operations

The `CommitAction` uses `subprocess.run()` for git commands (same pattern as the existing `_run_git_diff()` in `review_client.py`). It does not use a git library.

**Commit message construction:** The action receives a `message` parameter from the step config. If absent, it constructs a semantic message from pipeline context: `{type}: {step_name} for {pipeline_name}`. The type prefix is derived from the step context (e.g., `docs` for design steps, `feat` for implementation).

**Staging strategy:** The action stages all modified and untracked files (`git add -A`) by default. An optional `paths` config parameter allows scoping to specific paths. The action validates that there are changes to commit before attempting the commit — a no-op commit is a success (not an error), with `outputs["committed"]` set to `False`.

### DEVLOG Entry Format

The `DevlogAction` follows the existing DEVLOG format (see `DEVLOG.md`): `## YYYYMMDD` header followed by bold title and descriptive text.

**Content sources (priority order):**
1. Explicit `content` parameter in step config — used verbatim
2. Auto-generated from pipeline state — constructed from `prior_outputs`, extracting step names, review verdicts, and key metadata

**File location:** Defaults to `{cwd}/DEVLOG.md`. An optional `path` config parameter overrides this.

**Append behavior:** The action reads the existing file, finds the insertion point (after the frontmatter and header, before existing date entries), and inserts the new entry. If today's date header already exists, the entry is appended under it rather than creating a duplicate date header.

### Auto-Registration Pattern

Each action module registers itself at import time:

```python
# Bottom of cf_op.py
register_action(ActionType.CF_OP, CfOpAction())
```

This mirrors the provider registry pattern established in the codebase. Actions are registered when the actions package is imported. The executor (slice 149) will import the package to populate the registry.

---

## Implementation Details

### CfOpAction

**Supported operations** (defined as a StrEnum within the module):

| Operation | CF CLI command | Required params | Optional params |
|-----------|---------------|-----------------|-----------------|
| `set_phase` | `cf set phase {phase}` | `phase` (int or str) | — |
| `build_context` | `cf build` | — | `summarize` (bool) |
| `summarize` | `cf summarize` | — | — |

**Config schema** (from step config `dict`):

```python
{
    "operation": "set_phase",    # required — CfOperation enum value
    "phase": 4,                  # operation-specific params
}
```

**Validation rules:**
- `operation` must be a recognized `CfOperation` value
- Operation-specific required params must be present
- `cf_client` on context must not be `None`

**ActionResult outputs:**
- `"stdout"`: raw CF CLI output
- `"operation"`: operation name that was executed

### CommitAction

**Config schema:**

```python
{
    "message": "docs: complete slice design for 144",  # optional
    "paths": ["src/", "tests/"],                       # optional, defaults to all
    "type": "docs",                                    # optional, for auto-message
}
```

**Validation rules:**
- `cwd` on context must exist and be a git repository (contains `.git`)

**Execution flow:**
1. Check for changes: `git status --porcelain` in `cwd`
2. If no changes: return success with `outputs["committed"] = False`
3. Stage: `git add -A` or `git add {paths}`
4. Commit: `git commit -m "{message}"`
5. Return success with `outputs["committed"] = True`, `outputs["sha"]` = commit hash

**ActionResult outputs:**
- `"committed"`: `True` if a commit was made, `False` if nothing to commit
- `"sha"`: commit SHA (when committed)
- `"message"`: commit message used

### DevlogAction

**Config schema:**

```python
{
    "content": "Explicit entry text",  # optional — if absent, auto-generate
    "title": "Slice 144: Utility Actions — Implementation Complete",  # optional
    "path": "DEVLOG.md",              # optional, defaults to {cwd}/DEVLOG.md
}
```

**Validation rules:**
- If `content` is absent and no `prior_outputs` exist in context, warn (but don't fail — the action can still write a minimal entry)

**Auto-generation logic:**
1. Extract completed step names from `context.prior_outputs`
2. Extract review verdicts from steps that produced them
3. Extract the model used (from resolver or prior outputs)
4. Format: `**{title}**\n{summary of steps and outcomes}`

**File manipulation:**
1. Read existing DEVLOG.md
2. Find first `## YYYYMMDD` line (or `---` separator after frontmatter)
3. If today's date header exists: insert entry after the header
4. If not: insert new date header + entry before the first existing date entry
5. Write back

**ActionResult outputs:**
- `"path"`: path to DEVLOG file written
- `"entry"`: the text that was appended

---

## Integration Points

### Provides to Other Slices

- **Slice 147 (Compact Action and Step Types):** The phase step type expands to `cf-op → dispatch → review → checkpoint → commit`. This slice provides the `cf-op`, `commit`, and `devlog` actions that the phase and devlog step types need.
- **Slice 149 (Pipeline Executor):** The executor iterates action sequences and calls `action.execute()`. These actions are the first implementations it will exercise.

### Consumes from Other Slices

- **Slice 142:** `Action` protocol, `ActionType`, `ActionContext`, `ActionResult`, `ValidationError`, `register_action`
- **Slice 126:** `ContextForgeClient` (consumed via `context.cf_client`)

---

## Success Criteria

### Functional

- [x] `CfOpAction` successfully executes `set_phase`, `build_context`, and `summarize` operations against a mocked `ContextForgeClient`
- [x] `CommitAction` creates a git commit with the expected message in a test repository
- [x] `CommitAction` returns `committed=False` (not an error) when there are no changes
- [x] `DevlogAction` appends an entry to DEVLOG.md at the correct insertion point
- [x] `DevlogAction` auto-generates content from `prior_outputs` when no explicit content is provided
- [x] Each action's `validate()` method returns errors for missing required config

### Technical

- [x] All three actions satisfy the `Action` protocol (runtime checkable)
- [x] All three actions auto-register in the action registry at import time
- [x] `get_action(ActionType.CF_OP)` / `COMMIT` / `DEVLOG` returns the registered instance
- [x] Pyright reports 0 errors
- [x] Ruff reports 0 warnings
- [x] All existing tests continue to pass

### Integration

- [x] Action registry contains all three new actions plus any previously registered
- [x] `list_actions()` includes `"cf-op"`, `"commit"`, `"devlog"`

---

## Verification Walkthrough

*Verified during implementation — 2026-03-31.*

```bash
# 1. Run the new tests (13 + 9 + 12 + 5 = 39 tests)
cd /Users/manta/source/repos/manta/squadron
python -m pytest tests/pipeline/actions/test_cf_op.py -v          # 13 passed
python -m pytest tests/pipeline/actions/test_commit.py -v         # 9 passed
python -m pytest tests/pipeline/actions/test_devlog.py -v         # 12 passed
python -m pytest tests/pipeline/actions/test_registry_integration.py -v  # 5 passed

# 2. Verify action registration
# NOTE: Action modules must be explicitly imported to trigger registration.
# The actions package __init__.py does NOT auto-import them.
# The executor (slice 149) will import the package to populate the registry.
python -c "
import squadron.pipeline.actions.cf_op
import squadron.pipeline.actions.commit
import squadron.pipeline.actions.devlog
from squadron.pipeline.actions import list_actions, get_action
actions = list_actions()
print('Registered actions:', actions)
assert 'cf-op' in actions
assert 'commit' in actions
assert 'devlog' in actions
from squadron.pipeline.actions.protocol import Action
for name in ['cf-op', 'commit', 'devlog']:
    a = get_action(name)
    assert isinstance(a, Action), f'{name} does not satisfy Action protocol'
print('All actions registered and protocol-compliant')
"
# Output: Registered actions: ['cf-op', 'commit', 'devlog']
# Output: All actions registered and protocol-compliant

# 3. Verify no regressions
python -m pytest --tb=short -q     # 800 passed
pyright src/squadron/pipeline/actions/  # 0 errors
ruff check src/squadron/pipeline/actions/  # All checks passed
```

---

## Risk Assessment

**Low risk overall.** Each action wraps a well-understood operation (CF CLI, git, file I/O) behind a proven protocol. The primary risk is getting the I/O mocking right in tests.

- **DEVLOG insertion logic** — Parsing an existing markdown file to find the right insertion point has edge cases (empty file, missing frontmatter, multiple same-date headers). Mitigate with test cases for each variant.
- **Git subprocess failures** — Network issues, lock files, uncommittable state. Mitigate by returning clear `ActionResult.error` messages rather than raising exceptions.

---

## Implementation Notes

### Development Approach

Implement in order: `cf_op.py` → `commit.py` → `devlog.py`. Each action is fully independent — no cross-action dependencies. Write tests alongside each action (test file per action module).

### Test Strategy

Mock I/O boundaries:
- `CfOpAction`: mock `ContextForgeClient._run()` to return expected stdout
- `CommitAction`: use `tmp_path` fixture with `git init` for a real test repo, or mock `subprocess.run`
- `DevlogAction`: use `tmp_path` fixture with a sample DEVLOG.md file

All tests are unit tests — no network calls, no real CF operations. Integration testing happens when the executor runs full pipelines (slice 149+).
