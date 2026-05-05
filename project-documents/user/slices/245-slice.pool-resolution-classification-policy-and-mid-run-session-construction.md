---
docType: slice-design
slice: pool-resolution-classification-policy-and-mid-run-session-construction
project: squadron
parent: 240-slices.pipeline-auth-boundary-flexibility.md
dependencies: [244]
interfaces: [246, 247, 248]
dateCreated: 20260504
dateUpdated: 20260504
status: not_started
---

# Slice Design: Pool-Resolution Classification Policy and Mid-Run Session Construction

## Overview

Slice 244 classifies `POOL_UNCERTAIN` steps conservatively — any pool step that
_could_ resolve to an SDK alias forces `needs_persistent_session = True` and
connects the persistent session at startup. This is safe but over-eager: a pool
that _happens_ to mix SDK and non-SDK members forces Claude auth even when
runtime pool selection never picks an SDK member.

This slice changes the default: **lazy is the default policy**. The persistent
session is not constructed until a step that actually needs it runs. Users who
want the old conservative (eager-connect, fail-fast) behavior opt in explicitly
via `--strict` or `auth_policy: strict`.

This slice introduces:

1. A **lazy-vs-strict policy** for pool-uncertain steps. Lazy is the default.
   Strict is opt-in via `--strict` CLI flag and/or `auth_policy: strict`
   pipeline config key.
2. A **mid-run session construction mechanism**: when the default lazy policy is
   active, the persistent `SDKExecutionSession` is constructed and connected on
   the first step that actually resolves to an SDK profile, not at pipeline
   startup.
3. The **auth-failure UX** for lazy mode: when a mid-run pool selection yields an
   SDK alias but Claude auth is unavailable, the pipeline emits a clear error,
   persists recoverable run state, and documents the resume path.

## Value

- By default, no persistent session is constructed until a step actually needs
  one. Pipelines whose pool steps never select an SDK alias run without Claude
  auth.
- Static-SDK pipelines (no pool-uncertain steps) are unaffected in practice:
  the session is constructed immediately before the first SDK step, which is
  step 1 in the common case.
- Users who want upfront fail-fast behavior (e.g., CI pipelines, long runs
  where a mid-run auth failure would waste time) opt in with `--strict`.
- The mid-run mechanism (arch §5a) is implemented, unblocking the adversarial
  test matrix (slice 248) and the full pool-resolution correctness story.

## Technical Scope

**In scope:**

- `--strict` CLI flag on `sq run` (opt-in conservative/eager behavior).
- Equivalent pipeline config key: `auth_policy: strict`.
- `PoolClassificationPolicy` enum (`lazy` / `strict`) in `classification.py`.
- `classify_pipeline` default policy changed to `LAZY`.
- Updated `PipelineClassification.needs_persistent_session` to evaluate
  `POOL_UNCERTAIN` steps relative to the stored policy.
- Mid-run session construction hook in `execute_pipeline`.
- Auth-failure error path and run-state shape for the mid-run lazy case.
- Tests: 10–15 new tests; existing pool-uncertain tests updated to reflect new
  default.

**Out of scope:**

- `sq run --explain` diagnostic surface (slice 246).
- Authoring guide updates (slice 247).
- Full adversarial test matrix (slice 248).
- Any 180-band pool selection strategy changes.
- One-shot `ClaudeSDKAgent` session reuse or pooling.

---

## Architecture

### Policy Enum

A new `PoolClassificationPolicy` enum in
`src/squadron/pipeline/classification.py` alongside the existing
`StepClass` / `PipelineShape` enums:

```python
class PoolClassificationPolicy(StrEnum):
    LAZY = "lazy"
    STRICT = "strict"
```

This enum is the single definition of the lazy/strict vocabulary. The CLI flag,
pipeline config key, and classification function all reference it.

### Updated Classification Contract

`classify_pipeline` gains an optional `policy` parameter defaulting to `LAZY`:

```python
def classify_pipeline(
    definition: PipelineDefinition,
    resolver: ModelResolver,
    pool_backend: PoolBackend | None = None,
    policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
) -> PipelineClassification:
```

`PipelineClassification` stores the policy used:

```python
@dataclass(frozen=True)
class PipelineClassification:
    pipeline_name: str
    steps: tuple[StepClassification, ...]
    policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY
```

`needs_persistent_session` evaluates `POOL_UNCERTAIN` steps relative to the
stored policy:

- `LAZY` (default): `POOL_UNCERTAIN` does **not** count toward
  `needs_persistent_session`; only statically-confirmed `SDK_REQUIRED` steps do.
- `STRICT`: `POOL_UNCERTAIN` counts as SDK-required (same as 244's behavior).

`StepClassification` and `StepClass` are unchanged. The per-step
`POOL_UNCERTAIN` classification is always emitted accurately; the policy only
affects how the pipeline-level aggregation interprets it.

### Mid-Run Session Construction

Arch §5a describes the mechanism: `execute_pipeline` holds the mutable
`sdk_session` reference. When `sdk_session` is `None` at action-context build
time and the current step is statically confirmed SDK, the executor constructs
and connects the session before building `ActionContext`. All subsequent steps
reuse the same session.

The step-level SDK check in the executor is a call to
`is_sdk_profile(resolver.resolve(step_model))` — the same predicate used by
classification — not a re-run of full pipeline classification.

**The mid-run construction hook lives in `execute_pipeline`**, immediately
before the `sdk_session` argument is passed to each step dispatch call. This
keeps the session reference owned in one place.

```python
# Pseudocode — not final implementation
for step_index, step in enumerate(definition.steps):
    ...
    # Mid-run lazy hook: construct session on first confirmed-SDK step
    if sdk_session is None and _step_needs_sdk(step, resolver, merged_params):
        sdk_session = await _connect_lazy_session()

    step_result = await _execute_..._step(..., sdk_session=sdk_session)
```

`_step_needs_sdk` is a private helper: given a step and resolver, return `True`
iff the step's action type is in `_PERSISTENT_SESSION_STEP_TYPES` and the
resolved profile `is_sdk_profile`. It must not mutate resolver state or invoke
pool selection.

For pool-uncertain steps, `_step_needs_sdk` cannot know whether runtime
selection will yield SDK. The hook fires only when the profile is _statically_
confirmed SDK. When a pool selects SDK at runtime, the dispatch action calls
`set_model` on the session; if the session is `None` at that point, the dispatch
action detects the missing session and returns a `FAILED` result with a clear
error (see §Auth-Failure UX below).

The mid-run hook is always active when `sdk_session` is `None`, regardless of
policy. Under strict mode, `needs_persistent_session` will be `True` for any
pipeline with pool-uncertain steps, so the session is constructed at startup —
the hook will never fire because `sdk_session` is already set. Under lazy mode
(default), the hook is the primary construction path.

### Strict Mode Opt-In

Two opt-in surfaces, either of which activates strict (eager-connect) mode:

1. **CLI flag:** `--strict` on `sq run`.
2. **Pipeline config key:** `auth_policy: strict` in the pipeline YAML
   top-level. CLI flag takes precedence over pipeline config key.

The resolved policy is passed through `_run_pipeline_sdk` → `classify_pipeline`
→ stored in `PipelineClassification` → passed into `execute_pipeline` via a new
`pool_policy` parameter. `execute_pipeline` reads `classification.policy` to
determine whether the lazy hook should be armed (always the case when
`sdk_session is None`, but under strict mode the session is pre-constructed so
the hook becomes a no-op).

### Auth-Failure UX for Mid-Run Case

**A. Static-SDK step, session construction fails** (e.g., Claude auth
unavailable). The `_connect_lazy_session` helper catches the connect failure,
logs at `ERROR`, persists run state as `failed` (paused at the triggering step),
and re-raises. The user sees:

```
[red]Error: Claude auth required — connection failed mid-run at step 'N'.[/red]
Run state saved. Resume with: sq run --resume <run-id>
```

**B. Pool-uncertain step selects SDK at runtime, session is None** (no prior
static-SDK step fired, so the lazy hook never triggered). The dispatch action
guard (`sdk_session is None`) fires and returns `FAILED`. The executor records
the step as failed, saves run state, and surfaces:

```
[red]Error: Step 'N' resolved to an SDK profile at runtime but no persistent
session is available. Re-run with --strict to connect at startup, or ensure
this pool's runtime selection does not yield an SDK alias.[/red]
```

Both cases leave run state with `status: failed` and completed steps intact.
Resume re-classifies and proceeds after auth is addressed.

---

## Component Interactions

```
Default (lazy) or --strict flag or auth_policy: strict pipeline config
    │
    ▼
_run_pipeline_sdk (cli/commands/run.py)
    │  resolves policy → PoolClassificationPolicy (default: LAZY)
    │
    ▼
classify_pipeline(policy=policy)  (pipeline/classification.py)
    │  POOL_UNCERTAIN: counted as SDK-required only under STRICT
    │  classification.needs_persistent_session False by default for uncertain pools
    │
    ▼
session = None (lazy default) or SDKExecutionSession (strict)
    │
    ▼
execute_pipeline(sdk_session=session, pool_policy=policy)  (pipeline/executor.py)
    │
    │  Per-step loop:
    │    sdk_session is None and _step_needs_sdk(step) → True?
    │      → _connect_lazy_session() → sdk_session
    │    build ActionContext(sdk_session=sdk_session)
    │    execute action
    │      if sdk_session is None and action needs session → FAILED + clear error
```

---

## Data Flow

Default lazy run, mixed pool pipeline:

1. `sq run my-pipeline` — no flag, `policy = LAZY`.
2. `classify_pipeline(..., policy=LAZY)`: pool-uncertain steps classified
   `POOL_UNCERTAIN`; `needs_persistent_session = False`.
3. `session = None` — no session constructed at startup.
4. Step 1 (dispatch, pool): `_step_needs_sdk` returns `False` (pool-uncertain).
   No hook. `ActionContext(sdk_session=None)`. Pool selects non-SDK → `_dispatch_via_agent`. OK.
5. Step 2 (dispatch, static sonnet): `_step_needs_sdk` returns `True`. Hook fires,
   session constructed and connected. `ActionContext(sdk_session=session)`. OK.
6. Step 3 (dispatch, pool): pool selects SDK alias. `ActionContext(sdk_session=session)`.
   `set_model(...)` called. OK (session exists from step 2).

Strict run, same pipeline:

1. `sq run my-pipeline --strict` — `policy = STRICT`.
2. `classify_pipeline(..., policy=STRICT)`: `needs_persistent_session = True`.
3. Session constructed and connected at startup.
4. All steps receive `ActionContext(sdk_session=session)`. No mid-run hook.

---

## Technical Decisions

### Policy Does Not Alter Per-Step StepClassification

`StepClassification.classification` retains `POOL_UNCERTAIN` regardless of
policy. The policy only changes how `PipelineClassification.needs_persistent_session`
aggregates those values. The classification data remains truthful for the
diagnostic surface (slice 246) and adversarial tests (slice 248).

### Mid-Run Hook Is Policy-Agnostic

The hook (`sdk_session is None → connect`) fires for any confirmed-SDK step
regardless of policy. Under strict mode it is a dead code path (session already
exists). This avoids a conditional inside the loop and keeps the step execution
path uniform.

### Pipeline Config Key Is a Top-Level Field

`auth_policy: strict` is a top-level key on `PipelineDefinition`. The YAML
parser and `PipelineDefinition` model gain `auth_policy: str | None = None`.
Validation accepts `strict`, `lazy`, or absent (defaulting to `lazy`). Unknown
values raise `ValidationError` at load time.

### execute_pipeline Gains pool_policy Parameter

```python
async def execute_pipeline(
    ...
    sdk_session: SDKExecutionSession | None = None,
    pool_policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
    ...
) -> PipelineResult:
```

The default matches the new system default. Callers that pre-construct a session
(strict mode, resume path) pass the session; the hook is a no-op.

### Existing 244 Tests Need Policy Annotation

The existing `test_run_pipeline_sdk.py` tests were written against the
conservative default. After this slice, the default is lazy. Tests that expect
`needs_persistent_session = True` for pool-uncertain pipelines must either
pass `policy=STRICT` or use statically-confirmed SDK steps. Tests that expect
`needs_persistent_session = False` require no change.

---

## Failure Modes

| Scenario | Detection | Observable Signal |
|---|---|---|
| Lazy (default), static-SDK step, auth unavailable | `connect()` raises in `_connect_lazy_session` | ERROR log + red message + run state `failed` |
| Lazy (default), pool selects SDK, no session | `ctx.sdk_session is None` guard in dispatch action | `FAILED` step result + red message + run state `failed` |
| Strict mode, auth unavailable at startup | existing `connect()` failure path (244) | Unchanged from 244 behavior |
| Bad `auth_policy` value in pipeline YAML | `ValidationError` at load time | Validation error before run starts |

---

## Cross-Slice Dependencies

- **Slice 244 (prerequisite):** supplies `PipelineClassification`, `StepClass`,
  `classify_pipeline`. This slice extends the classification contract, changes
  the default, and adds the mid-run hook.
- **Slice 246:** reads `classification.policy` and `POOL_UNCERTAIN` per-step
  classifications. No changes needed in 246 design; it consumes policy as-is.
- **Slice 248:** exercises the lazy-mode failure modes end-to-end.

---

## Success Criteria

1. `sq run <pipeline>` (no flag) on a pipeline with only `POOL_UNCERTAIN`
   persistent-session steps does not construct a persistent session at startup.
2. When a static-SDK step is reached in the default lazy run, the session is
   constructed and connected before that step's `ActionContext` is built.
3. All subsequent steps after first SDK construction reuse the same session
   (verified by session identity checks in tests).
4. When the default lazy run hits a pool that selects SDK at runtime with no
   session available, the step result is `FAILED` with a message identifying
   the step and the remediation (`--strict`).
5. When `connect()` fails mid-run, run state is saved as `failed` with the
   triggering step identified; the pipeline can be resumed after auth is resolved.
6. `--strict` flag forces session construction at startup (pre-244 behavior
   for pool-uncertain pipelines).
7. `auth_policy: strict` in pipeline YAML activates strict mode without the CLI
   flag; `--strict` CLI flag takes precedence over pipeline config.
8. `auth_policy: lazy` in pipeline YAML is the explicit default; behaves
   identically to the absent key.
9. All existing tests in `test_run_pipeline_sdk.py` and `test_sdk_wiring.py`
   pass (updated where needed to account for default policy change).

---

## Test Coverage

New test file: `tests/cli/commands/test_run_pipeline_lazy.py` and additions to
`tests/pipeline/test_classification.py`.

| Test | What it asserts |
|---|---|
| `test_classify_lazy_default_pool_uncertain_not_needs_persistent` | `needs_persistent_session` is `False` when policy is LAZY (default) and all persistent steps are POOL_UNCERTAIN |
| `test_classify_strict_pool_uncertain_sets_needs_persistent` | `needs_persistent_session` is `True` for same pipeline with STRICT policy |
| `test_lazy_static_sdk_step_constructs_session_before_step` | Session constructed on first static-SDK step in lazy run; not before |
| `test_lazy_multiple_sdk_steps_reuse_same_session` | Second SDK step receives same session object as first |
| `test_lazy_no_sdk_steps_reached_no_session_constructed` | Pipeline that aborts before first SDK step never constructs a session |
| `test_lazy_pool_selects_sdk_no_session_fails_with_clear_error` | FAILED result with correct error message when pool selects SDK and no session |
| `test_lazy_connect_failure_saves_failed_run_state` | Run state is `failed` at triggering step on connect error |
| `test_strict_flag_activates_strict_policy` | `--strict` CLI flag passes STRICT policy through to classification |
| `test_pipeline_yaml_auth_policy_strict` | `auth_policy: strict` in pipeline YAML activates strict mode |
| `test_pipeline_yaml_auth_policy_invalid_raises_validation_error` | Unknown `auth_policy` value raises `ValidationError` at load |
| `test_cli_flag_overrides_pipeline_config` | `--strict` flag overrides `auth_policy: lazy` |
| `test_lazy_explicit_yaml_key_matches_default` | `auth_policy: lazy` in YAML behaves identically to absent key |

---

## Verification Walkthrough

### 1. Default (lazy): no session constructed at startup

```bash
# Pipeline with dispatch steps using a mixed pool (SDK and non-SDK members)
sq run my-mixed-pool-pipeline
# Expect: no session constructed at startup; runs without Claude auth until
# an SDK step is reached (or not at all if pool never selects SDK).
```

### 2. Default (lazy): session constructed mid-run on first SDK step

```bash
# Pipeline: step 1 = pool-uncertain dispatch, step 2 = static sonnet dispatch
sq run mixed-pipeline -v
# Expect log:
#   INFO: pipeline 'mixed-pipeline' shape: claude_required_persistent (2 classified steps)
#   DEBUG: step 'step-2' resolved to SDK profile; constructing session mid-run
```

### 3. Default (lazy): pool selects SDK, session unavailable

With no Claude auth active, run a pipeline with a pool-uncertain step where the
pool will select an SDK alias:

```bash
sq run uncertain-pool-pipeline
# Expect: FAILED result with message:
# "Step 'step-name' resolved to an SDK profile at runtime but no persistent
#  session is available. Re-run with --strict to connect at startup..."
```

### 4. Strict mode: session constructed at startup

```bash
sq run my-mixed-pool-pipeline --strict
# Expect: session constructed and connected before any step executes.
# If Claude auth is unavailable, error surfaces immediately.
```

### 5. Pipeline config key

```yaml
# pipeline YAML
auth_policy: strict
```

```bash
sq run that-pipeline   # no --strict flag needed; strict from YAML
```

### 6. Unit test suite

```bash
pytest tests/cli/commands/test_run_pipeline_lazy.py tests/pipeline/test_classification.py -v
# Expect: all new tests pass; zero regressions in existing suite
```
