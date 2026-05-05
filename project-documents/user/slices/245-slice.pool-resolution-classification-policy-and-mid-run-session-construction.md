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

This slice introduces:

1. A **conservative-vs-lazy policy** for pool-uncertain steps, controlled by a
   CLI flag (`--lazy-auth`) and/or a pipeline config key.
2. A **mid-run session construction mechanism** so that when lazy mode is active,
   the persistent `SDKExecutionSession` is constructed and connected on the first
   step that actually resolves to an SDK profile, not at pipeline startup.
3. The **auth-failure UX** for lazy mode: when a mid-run pool selection yields an
   SDK alias but Claude auth is unavailable, the pipeline emits a clear error,
   persists recoverable run state, and documents the resume path.

## Value

- Users with mixed-SDK pools who know their pipeline will pick non-SDK members
  can opt in to lazy mode and run without Claude auth until and unless an SDK
  step actually fires.
- The conservative default is preserved: `POOL_UNCERTAIN` still means
  Claude-required unless the user explicitly opts in.
- The mid-run mechanism (arch §5a) is implemented, unblocking the adversarial
  test matrix (slice 248) and the full pool-resolution correctness story.

## Technical Scope

**In scope:**

- `--lazy-auth` CLI flag on `sq run` (and equivalent pipeline config key
  `auth_policy: lazy`).
- `PoolClassificationPolicy` enum (`conservative` / `lazy`) surfaced through the
  executor and classification layer.
- Updated `PipelineClassification.needs_persistent_session` to accept the policy.
- Mid-run session construction in `execute_pipeline` when `sdk_session` is `None`
  and an action's resolved step is SDK-required.
- Auth-failure error path and run-state shape for the mid-run lazy case.
- Tests: 10–15 new tests; existing pool-uncertain tests updated.

**Out of scope:**

- `sq run --explain` diagnostic surface (slice 246).
- Authoring guide updates (slice 247).
- Full adversarial test matrix (slice 248).
- Any 180-band pool selection strategy changes.
- One-shot `ClaudeSDKAgent` session reuse or pooling.

---

## Architecture

### Policy Enum

A new `PoolClassificationPolicy` enum, placed in
`src/squadron/pipeline/classification.py` alongside the existing
`StepClass` / `PipelineShape` enums:

```python
class PoolClassificationPolicy(StrEnum):
    CONSERVATIVE = "conservative"
    LAZY = "lazy"
```

This enum is the single definition of the conservative/lazy vocabulary.
The CLI flag, pipeline config key, and classification function all reference it.

### Updated Classification Contract

`classify_pipeline` gains an optional `policy` parameter:

```python
def classify_pipeline(
    definition: PipelineDefinition,
    resolver: ModelResolver,
    pool_backend: PoolBackend | None = None,
    policy: PoolClassificationPolicy = PoolClassificationPolicy.CONSERVATIVE,
) -> PipelineClassification:
```

`PipelineClassification` stores the policy used:

```python
@dataclass(frozen=True)
class PipelineClassification:
    pipeline_name: str
    steps: tuple[StepClassification, ...]
    policy: PoolClassificationPolicy = PoolClassificationPolicy.CONSERVATIVE
```

`needs_persistent_session` evaluates `POOL_UNCERTAIN` steps relative to the
stored policy:

- `CONSERVATIVE` (default): `POOL_UNCERTAIN` counts as SDK-required (current
  behavior, no change).
- `LAZY`: `POOL_UNCERTAIN` does **not** count toward `needs_persistent_session`;
  only statically-confirmed `SDK_REQUIRED` steps do.

`StepClassification` and `StepClass` are unchanged.

### Mid-Run Session Construction

Arch §5a describes the mechanism: `execute_pipeline` holds the mutable
`sdk_session` reference. When lazy mode is active and `sdk_session` is `None`
at action-context build time, the executor checks whether the current step is
SDK-dispatching; if so, it constructs and connects the session before building
`ActionContext`. All subsequent steps reuse the same session.

The step-level SDK check in the executor is a direct call to
`is_sdk_profile(resolver.resolve(step_model))` — the same predicate used by
classification — not a re-run of full pipeline classification. This is a
per-step resolved-profile check, not a re-scan.

**The mid-run construction hook lives in `execute_pipeline`**, immediately
before the `sdk_session` argument is passed to each step dispatch call. It is
not inside `_execute_action_step`; keeping it at the `execute_pipeline` level
ensures the session reference is owned in one place and propagated cleanly.

```python
# Pseudocode — not final implementation
for step_index, step in enumerate(definition.steps):
    ...
    # Lazy mid-run hook
    if sdk_session is None and _step_needs_sdk(step, resolver, merged_params):
        sdk_session = await _connect_lazy_session()

    step_result = await _execute_..._step(..., sdk_session=sdk_session)
```

`_step_needs_sdk` is a private helper: given a step and resolver, return `True`
iff the step's action type is in `_PERSISTENT_SESSION_STEP_TYPES` and the
resolved profile `is_sdk_profile`. It must **not** mutate resolver state or
invoke pool selection.

For pool-uncertain steps in lazy mode, `_step_needs_sdk` cannot know whether
runtime selection will yield SDK — that is the whole point of the uncertain
classification. The hook fires only when the resolved profile is _statically_
confirmed SDK. When a pool selects SDK at runtime, the dispatch action itself
will call `set_model` on the session; if the session is `None` at that point,
the dispatch action should detect the missing session and return a `FAILED`
result with a clear error (see §Auth-Failure UX below).

### Lazy Mode Opt-In

Two opt-in surfaces, either of which activates lazy mode:

1. **CLI flag:** `--lazy-auth` on `sq run`. Mutually exclusive with `--dry-run`.
2. **Pipeline config key:** `auth_policy: lazy` in the pipeline YAML top-level.
   CLI flag takes precedence over pipeline config key.

The resolved policy is passed through `_run_pipeline_sdk` → `classify_pipeline`
→ stored in `PipelineClassification` → passed into `execute_pipeline` via a new
`pool_policy` parameter.

`_run_pipeline_sdk` does not need to pass the policy object all the way to
`execute_pipeline` as a separate argument — it passes it as part of the
classification result stored in `PipelineClassification`. `execute_pipeline`
reads `classification.policy` to decide whether to arm the lazy hook.

### Auth-Failure UX for Mid-Run Lazy Case

When a pool-uncertain step runs in lazy mode and runtime pool selection yields
an SDK alias, the dispatch action calls `context.sdk_session.set_model(...)`.
If `context.sdk_session is None`, the dispatch action already returns a
`FAILED` `ActionResult` (existing guard from slice 244 review). However, the
message needs to be precise for the lazy-mode scenario.

Two sub-cases:

**A. Static-SDK step in lazy mode, session construction fails** (e.g., Claude
auth unavailable). The `_connect_lazy_session` helper in `execute_pipeline`
catches the connect failure, logs at `ERROR`, persists run state as `failed`
(paused at the triggering step), and re-raises as a structured error. The
pipeline does not resume automatically. The user sees:

```
[red]Error: Claude auth required — connection failed mid-run at step 'N'.[/red]
Run state saved. Resume with: sq run --resume <run-id>
```

**B. Pool-uncertain step selects SDK at runtime, session is None (lazy mode,
no prior static-SDK step fired).** This is the case where `_step_needs_sdk`
returned `False` (pool was uncertain, not confirmed SDK), so no lazy hook fired,
but the runtime selection yielded an SDK alias. The dispatch action guard
(`sdk_session is None`) fires and returns `FAILED`. The executor records the
step as failed, saves run state, and surfaces:

```
[red]Error: Step 'N' resolved to an SDK profile at runtime but no persistent
session is available. Re-run with --lazy-auth disabled (default) or set
auth_policy: conservative in your pipeline.[/red]
```

Both cases leave run state with `status: failed` and the completed steps
intact. Resume (after the user addresses auth) re-classifies and proceeds.

---

## Component Interactions

```
CLI flag (--lazy-auth) or pipeline config (auth_policy: lazy)
    │
    ▼
_run_pipeline_sdk (cli/commands/run.py)
    │  resolves policy → PoolClassificationPolicy
    │
    ▼
classify_pipeline(policy=policy)  (pipeline/classification.py)
    │  POOL_UNCERTAIN treated as SDK or not-SDK per policy
    │  classification.needs_persistent_session may be False in lazy mode
    │
    ▼
session = None if not needs_persistent_session
    │
    ▼
execute_pipeline(sdk_session=session, pool_policy=policy)  (pipeline/executor.py)
    │
    │  Per-step loop:
    │    _step_needs_sdk(step, resolver) → True?
    │      Yes + sdk_session is None → _connect_lazy_session() → sdk_session
    │    build ActionContext(sdk_session=sdk_session)
    │    execute action
    │      if sdk_session is None and action needs session → FAILED + clear error
```

---

## Data Flow

1. User invokes `sq run my-pipeline --lazy-auth`.
2. `_run_pipeline_sdk` resolves `policy = PoolClassificationPolicy.LAZY`.
3. `classify_pipeline(definition, resolver, pool_backend, policy=LAZY)` runs.
   - `POOL_UNCERTAIN` steps are included in `classification.steps` with their
     `POOL_UNCERTAIN` classification _unchanged_ — the policy does not alter
     per-step classification, only the `needs_persistent_session` evaluation.
4. `classification.needs_persistent_session` returns `False` (all persistent-
   session steps are POOL_UNCERTAIN; no statically-confirmed SDK steps).
5. `session = None` — no persistent session constructed at startup.
6. `execute_pipeline(sdk_session=None, pool_policy=LAZY)` begins.
7. Step 1 (dispatch, pool): `_step_needs_sdk` cannot confirm (pool-uncertain) →
   no lazy hook. `ActionContext(sdk_session=None)`. Dispatch action runs; pool
   selects a non-SDK alias. Dispatch routes via `_dispatch_via_agent`. OK.
8. Step 2 (dispatch, pool): same pool selects an SDK alias. Dispatch action
   receives `ctx.sdk_session = None`. Dispatch action returns `FAILED` with
   clear message.
9. Executor saves run state `failed`, surfaces error to user.

---

## Technical Decisions

### Policy Does Not Alter Per-Step StepClassification

`StepClassification.classification` retains `POOL_UNCERTAIN` regardless of
policy. The policy only changes how `PipelineClassification.needs_persistent_session`
aggregates those values. This keeps the classification data truthful for the
diagnostic surface (slice 246) and the adversarial tests (slice 248).

### Static-SDK Lazy Hook Is Safe

For steps that are _statically confirmed_ SDK (non-pool), the lazy hook fires
immediately before the first such step. This is equivalent to eager construction
except the session is not created if no SDK step is reached (e.g., pipeline
aborts earlier). No behavior change for purely-static SDK pipelines.

### Pool-Uncertain in Lazy Mode: No Runtime Oracle

The executor does not attempt to predict runtime pool selection. The lazy hook
ignores `POOL_UNCERTAIN` steps. If runtime selection yields SDK on a
pool-uncertain step and no session exists, the dispatch guard fires and fails
clearly. This is the documented and expected failure mode for lazy mode with
mixed pools.

### Pipeline Config Key Is a Top-Level Field

`auth_policy: lazy` is a top-level key on `PipelineDefinition`. The YAML parser
and `PipelineDefinition` model gain an `auth_policy: str | None = None` field.
Validation accepts `conservative`, `lazy`, or absent (defaulting to
`conservative`). Unknown values raise a `ValidationError` at load time.

### execute_pipeline Gains pool_policy Parameter

```python
async def execute_pipeline(
    definition: PipelineDefinition,
    params: dict[str, object],
    *,
    resolver: ModelResolver,
    cf_client: ContextForgeClient,
    ...
    sdk_session: SDKExecutionSession | None = None,
    pool_policy: PoolClassificationPolicy = PoolClassificationPolicy.CONSERVATIVE,
    ...
) -> PipelineResult:
```

This lets `execute_pipeline` arm the lazy hook independently from whether
`sdk_session` was passed in — the caller (tests, resume path) may want to pass
a pre-constructed session with lazy policy for testing purposes.

---

## Failure Modes

| Scenario | Detection | Observable Signal |
|---|---|---|
| Lazy mode, static-SDK step, auth unavailable | `connect()` raises in `_connect_lazy_session` | ERROR log + red message + run state `failed` |
| Lazy mode, pool selects SDK, no session | `ctx.sdk_session is None` guard in dispatch action | `FAILED` step result + red message + run state `failed` |
| Conservative mode (default), no change | `needs_persistent_session` eager-connect as in 244 | No change from 244 behavior |
| Bad `auth_policy` value in pipeline YAML | `ValidationError` at load time | Validation error message before run starts |

---

## Cross-Slice Dependencies

- **Slice 244 (prerequisite):** supplies `PipelineClassification`, `StepClass`,
  `classify_pipeline`, and the conservative default. This slice extends the
  classification contract without breaking it.
- **Slice 246:** reads `classification.policy` and `POOL_UNCERTAIN` per-step
  classifications for the `--explain` display. Unchanged by this slice.
- **Slice 248:** tests the lazy-mode failure modes end-to-end. Depends on this
  slice's implementation being present.

---

## Success Criteria

1. `sq run <pipeline> --lazy-auth` on a pipeline with only POOL_UNCERTAIN
   persistent-session steps does not construct a persistent session at startup.
2. When a static-SDK step is reached in lazy mode, the session is constructed
   and connected before that step's `ActionContext` is built.
3. All subsequent steps after first SDK construction reuse the same session
   (verified by session identity checks in tests).
4. When lazy mode is active and a pool selects SDK at runtime with no session
   available, the step result is `FAILED` with a message identifying the step
   and the remediation (`--lazy-auth disabled`).
5. When lazy mode is active and `connect()` fails, run state is saved as
   `failed` with the triggering step identified; the pipeline can be resumed
   after auth is resolved.
6. `auth_policy: conservative` in pipeline YAML behaves identically to the
   default (no flag).
7. `auth_policy: lazy` in pipeline YAML activates lazy mode without the CLI
   flag; `--lazy-auth` flag takes precedence over pipeline config.
8. Conservative-mode pipelines (no flag, no config key) are unaffected —
   existing 244 behavior is preserved exactly.
9. All existing tests in `test_run_pipeline_sdk.py` and `test_sdk_wiring.py`
   pass without modification.

---

## Test Coverage

New test file: `tests/cli/commands/test_run_pipeline_lazy.py` and additions to
`tests/pipeline/test_classification.py`.

| Test | What it asserts |
|---|---|
| `test_classify_lazy_pool_uncertain_does_not_set_needs_persistent` | `needs_persistent_session` is `False` when policy is LAZY and all persistent steps are POOL_UNCERTAIN |
| `test_classify_conservative_pool_uncertain_sets_needs_persistent` | `needs_persistent_session` is `True` for same pipeline with CONSERVATIVE policy |
| `test_lazy_static_sdk_step_constructs_session_before_step` | Session constructed on first static-SDK step in lazy mode; not before |
| `test_lazy_multiple_sdk_steps_reuse_same_session` | Second SDK step receives same session object as first |
| `test_lazy_no_sdk_steps_reached_no_session_constructed` | Pipeline that aborts before first SDK step never constructs a session |
| `test_lazy_pool_selects_sdk_no_session_fails_with_clear_error` | FAILED result with correct error message when pool selects SDK and no session |
| `test_lazy_connect_failure_saves_failed_run_state` | Run state is `failed` at triggering step on connect error |
| `test_lazy_flag_activates_lazy_policy` | `--lazy-auth` CLI flag passes LAZY policy through to classification |
| `test_pipeline_yaml_auth_policy_lazy` | `auth_policy: lazy` in pipeline YAML activates lazy mode |
| `test_pipeline_yaml_auth_policy_invalid_raises_validation_error` | Unknown `auth_policy` value raises `ValidationError` at load |
| `test_cli_flag_overrides_pipeline_config_conservative` | `--lazy-auth` flag overrides `auth_policy: conservative` |
| `test_conservative_mode_unchanged` | Default (no flag, no config) behavior identical to post-244 baseline |

---

## Verification Walkthrough

After implementation, a reviewer can verify the slice as follows:

### 1. Conservative mode unchanged

```bash
# Pipeline with dispatch steps using a homogeneous non-SDK pool
# expect: no session constructed, runs without Claude auth
sq run my-non-sdk-pool-pipeline
```

### 2. Lazy mode: no session at startup, constructed mid-run

```bash
# Pipeline with one pool-uncertain step followed by a static-SDK step
sq run mixed-pool-pipeline --lazy-auth
# Expect log output:
#   INFO: pipeline 'mixed-pool-pipeline' shape: claude_required_persistent (2 classified steps)
#   DEBUG: lazy mode active; session not constructed at startup
#   DEBUG: step 'sdk-step' resolved to SDK profile; constructing session mid-run
```

### 3. Lazy mode: pool selects SDK, session unavailable

Ensure no Claude auth is active. Run a pipeline with a pool-uncertain step in
lazy mode where the pool will select an SDK alias:

```bash
sq run uncertain-pool-pipeline --lazy-auth
# Expect: FAILED result with message:
# "Step 'step-name' resolved to an SDK profile at runtime but no persistent
#  session is available. Re-run with --lazy-auth disabled..."
```

### 4. Pipeline config key

```yaml
# pipeline YAML
auth_policy: lazy
```

```bash
sq run that-pipeline   # no --lazy-auth flag needed
# Expect lazy behavior as above
```

### 5. Auth failure mid-run (lazy, static-SDK step, no Claude auth)

Ensure Claude auth is unavailable. Use a pipeline whose first step is a
static-SDK dispatch step (not pool-uncertain):

```bash
sq run static-sdk-pipeline --lazy-auth
# Expect: red error message identifying the step, run state saved as failed
sq run --resume <run-id>  # after fixing auth, resume picks up at the failing step
```

### 6. Unit test suite

```bash
pytest tests/cli/commands/test_run_pipeline_lazy.py tests/pipeline/test_classification.py -v
# Expect: all new tests pass; zero regressions in existing suite
```
