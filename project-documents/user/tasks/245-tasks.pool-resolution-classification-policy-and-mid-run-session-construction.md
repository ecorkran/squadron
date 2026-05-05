---
docType: tasks
slice: 245-slice.pool-resolution-classification-policy-and-mid-run-session-construction
project: squadron
parent: 245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md
dependencies: [244]
dateCreated: 20260504
dateUpdated: 20260504
status: not_started
---

# Tasks: Pool-Resolution Classification Policy and Mid-Run Session Construction

## Context

Slice 244 always treats `POOL_UNCERTAIN` steps as SDK-required. This slice
makes lazy the default: no persistent session is constructed at startup unless
a step is statically confirmed SDK. `--strict` CLI flag (and `auth_policy:
strict` pipeline YAML key) opts in to eager upfront connection. The mid-run
session construction hook (arch §5a) is implemented in `execute_pipeline`.

**Key files:**
- `src/squadron/pipeline/classification.py` — add `PoolClassificationPolicy` enum; update `classify_pipeline` and `PipelineClassification`
- `src/squadron/pipeline/schema.py` — add `auth_policy` field to `PipelineSchema`; update `to_definition()`
- `src/squadron/pipeline/models.py` — add `auth_policy` field to `PipelineDefinition`
- `src/squadron/pipeline/executor.py` — add `pool_policy` param; add mid-run hook
- `src/squadron/cli/commands/run.py` — add `--strict` flag; pass policy through `_run_pipeline_sdk`
- `tests/pipeline/test_classification.py` — extend with policy tests
- `tests/cli/commands/test_run_pipeline_lazy.py` — new test file

---

## Tasks

### T1 — Add `PoolClassificationPolicy` enum to `classification.py`

- [ ] In `src/squadron/pipeline/classification.py`, add after the existing `PipelineShape` enum:
  ```python
  class PoolClassificationPolicy(StrEnum):
      LAZY = "lazy"
      STRICT = "strict"
  ```
- [ ] Export `PoolClassificationPolicy` from `__all__` if `classification.py` has one; otherwise ensure it is importable.

**Success:** `from squadron.pipeline.classification import PoolClassificationPolicy` works; `PoolClassificationPolicy.LAZY` and `PoolClassificationPolicy.STRICT` are the two members.

---

### T2 — Test: `PoolClassificationPolicy` enum

- [ ] In `tests/pipeline/test_classification.py`, add a test class `TestPoolClassificationPolicy`:
  - [ ] `test_lazy_value` — `PoolClassificationPolicy.LAZY == "lazy"`
  - [ ] `test_strict_value` — `PoolClassificationPolicy.STRICT == "strict"`

**Success:** Both tests pass.

---

### T3 — Update `PipelineClassification` to store policy

- [ ] In `src/squadron/pipeline/classification.py`, add `policy` field to `PipelineClassification`:
  ```python
  policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY
  ```
- [ ] Update `needs_persistent_session` property:
  - Under `LAZY`: `POOL_UNCERTAIN` steps do **not** count — only `SDK_REQUIRED` steps do.
  - Under `STRICT`: `POOL_UNCERTAIN` counts as SDK-required (existing behavior).
- [ ] `needs_one_shot_claude` is unchanged (reviews are not gated by policy).

**Success:** `PipelineClassification` has a `policy` field; `needs_persistent_session` returns correctly under both policies.

---

### T4 — Test: `needs_persistent_session` under both policies

- [ ] In `tests/pipeline/test_classification.py`, add to (or extend) the classification test suite:
  - [ ] `test_lazy_pool_uncertain_not_needs_persistent` — pipeline with one `POOL_UNCERTAIN` dispatch step; `policy=LAZY`; assert `needs_persistent_session is False`.
  - [ ] `test_strict_pool_uncertain_needs_persistent` — same pipeline; `policy=STRICT`; assert `needs_persistent_session is True`.
  - [ ] `test_lazy_sdk_required_still_needs_persistent` — pipeline with one `SDK_REQUIRED` dispatch step; `policy=LAZY`; assert `needs_persistent_session is True`.
  - [ ] `test_lazy_mixed_sdk_and_pool_uncertain` — pipeline with one `SDK_REQUIRED` step and one `POOL_UNCERTAIN` step; `policy=LAZY`; assert `needs_persistent_session is True` (SDK_REQUIRED alone is sufficient).

**Success:** All four tests pass.

---

### T5 — Update `classify_pipeline` signature and default

- [ ] In `src/squadron/pipeline/classification.py`, update `classify_pipeline`:
  - Add `policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY` parameter.
  - Pass `policy` to `PipelineClassification(...)` constructor.
  - No other logic changes — per-step `StepClassification` is unchanged.
- [ ] Update the docstring to document the `policy` parameter and new default.

**Success:** `classify_pipeline(definition, resolver)` returns a `PipelineClassification` with `policy=LAZY`; passing `policy=PoolClassificationPolicy.STRICT` stores `STRICT`.

---

### T6 — Test: `classify_pipeline` policy parameter

- [ ] In `tests/pipeline/test_classification.py`:
  - [ ] `test_classify_default_policy_is_lazy` — call `classify_pipeline` without `policy` arg; assert `result.policy == PoolClassificationPolicy.LAZY`.
  - [ ] `test_classify_explicit_strict_policy` — call with `policy=STRICT`; assert `result.policy == PoolClassificationPolicy.STRICT`.
- [ ] Verify existing `classify_pipeline` tests still pass with new default (pool-uncertain tests may need `policy=STRICT` annotation if they relied on the old conservative default behavior).

**Success:** All tests in `test_classification.py` pass.

---

### T7 — Add `auth_policy` to `PipelineDefinition` and `PipelineSchema`

- [ ] In `src/squadron/pipeline/models.py`, add to `PipelineDefinition`:
  ```python
  auth_policy: str | None = None
  ```
- [ ] In `src/squadron/pipeline/schema.py`:
  - Add `auth_policy: str | None = None` field to `PipelineSchema`.
  - Add a `@field_validator("auth_policy")` (or inline check) that rejects any value that is not `None`, `"lazy"`, or `"strict"` — raise `ValueError` with a clear message.
  - In `to_definition()`, pass `auth_policy=self.auth_policy` to `PipelineDefinition(...)`.

Note: `PipelineSchema` has `extra="forbid"`, so adding the field is all that is needed for YAML parsing to accept it.

**Success:** A pipeline YAML with `auth_policy: strict` loads without error; `definition.auth_policy == "strict"`. A YAML with `auth_policy: banana` raises `pydantic.ValidationError` at load time.

---

### T8 — Test: `auth_policy` YAML field

- [ ] In `tests/pipeline/test_loader.py` (or a new `test_schema.py`), add:
  - [ ] `test_auth_policy_strict_loads` — pipeline YAML with `auth_policy: strict`; assert `definition.auth_policy == "strict"`.
  - [ ] `test_auth_policy_lazy_loads` — pipeline YAML with `auth_policy: lazy`; assert `definition.auth_policy == "lazy"`.
  - [ ] `test_auth_policy_absent_defaults_none` — pipeline YAML without `auth_policy`; assert `definition.auth_policy is None`.
  - [ ] `test_auth_policy_invalid_raises` — pipeline YAML with `auth_policy: banana`; assert `pydantic.ValidationError` is raised.

**Success:** All four tests pass.

---

### T9 — Add `pool_policy` parameter to `execute_pipeline`

- [ ] In `src/squadron/pipeline/executor.py`, add to `execute_pipeline` signature:
  ```python
  pool_policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
  ```
- [ ] Add mid-run session construction hook inside the step loop, immediately before each step dispatch call:
  ```python
  if sdk_session is None and _step_needs_sdk(step, resolver, merged_params):
      sdk_session = await _connect_lazy_session(run_id=effective_run_id)
  ```
  Apply this before **all** step-type branches (`each`, `fan_out`, `loop`, `each`, and the default branch).
- [ ] Implement `_connect_lazy_session(run_id: str) -> SDKExecutionSession` as a private async helper in `executor.py`:
  - Constructs `ClaudeAgentOptions` and `ClaudeSDKClient` identically to `_run_pipeline_sdk`.
  - Calls `await session.connect()`.
  - On connect failure: logs at `ERROR`, raises the exception (caller handles state persistence).
  - Returns the connected `SDKExecutionSession`.
- [ ] Implement `_step_needs_sdk(step: StepConfig, resolver: ModelResolver, params: dict[str, object]) -> bool` as a private helper:
  - Returns `True` iff `step.step_type` is in `_PERSISTENT_SESSION_STEP_TYPES` and the resolved profile `is_sdk_profile(...)`.
  - Resolves the step model using the same cascade logic as classification (use `resolver.cascade_candidates` → first non-None → `resolve_model_alias`).
  - Returns `False` for pool candidates (cannot confirm statically) and for non-persistent-session step types.
  - Must not mutate resolver state or invoke pool selection.
- [ ] Import `PoolClassificationPolicy` at top of `executor.py`.
- [ ] Add `_connect_lazy_session` and `_step_needs_sdk` to the module but **not** to `__all__`.

**Success:** `execute_pipeline` accepts `pool_policy`; `_step_needs_sdk` and `_connect_lazy_session` are importable for testing.

---

### T10 — Test: mid-run session construction hook

- [ ] Create `tests/cli/commands/test_run_pipeline_lazy.py`.
- [ ] `test_lazy_static_sdk_step_constructs_session_before_step` — mock `_connect_lazy_session`; verify it is called before the first static-SDK step's `ActionContext` is built; verify all subsequent steps receive the same session object.
- [ ] `test_lazy_no_sdk_steps_no_session_constructed` — pipeline with only non-SDK steps; verify `_connect_lazy_session` is never called.
- [ ] `test_lazy_multiple_sdk_steps_reuse_same_session` — two consecutive SDK steps; verify `_connect_lazy_session` called exactly once; both steps get the same session.
- [ ] `test_step_needs_sdk_returns_true_for_sdk_alias` — unit test `_step_needs_sdk` directly with a static SDK alias.
- [ ] `test_step_needs_sdk_returns_false_for_non_sdk_alias` — non-SDK alias.
- [ ] `test_step_needs_sdk_returns_false_for_pool_candidate` — pool-prefixed candidate.

**Success:** All six tests pass.

---

### T11 — Handle mid-run connect failure in `execute_pipeline`

- [ ] In `execute_pipeline`, wrap the `_connect_lazy_session` call in a `try/except`:
  - On failure: save run state as `failed` via the state manager (use existing failure-persistence pattern in the executor), then re-raise so `_run_pipeline_sdk` surfaces it as a red error message.
  - Log at `ERROR` with the step name and exception.
- [ ] Ensure `_run_pipeline_sdk` catches the re-raised exception and prints:
  ```
  [red]Error: Claude auth required — connection failed mid-run at step '{name}'.[/red]
  Run state saved. Resume with: sq run --resume {run_id}
  ```

**Success:** When `_connect_lazy_session` raises, run state is `failed`, red message is printed, and the process exits with code 1.

---

### T12 — Test: mid-run connect failure UX

- [ ] In `tests/cli/commands/test_run_pipeline_lazy.py`:
  - [ ] `test_lazy_connect_failure_saves_failed_state` — mock `_connect_lazy_session` to raise; verify run state status is `failed`; verify `typer.Exit(1)` raised.
  - [ ] `test_lazy_connect_failure_message_names_step` — verify error message contains the triggering step name.

**Success:** Both tests pass.

---

### T13 — Add `--strict` flag to `sq run`; wire policy through `_run_pipeline_sdk`

- [ ] In `src/squadron/cli/commands/run.py`, add to the `run()` typer function parameters:
  ```python
  strict: bool = typer.Option(False, "--strict", help="Force eager session construction for pool-uncertain steps.")
  ```
- [ ] In `_run_pipeline_sdk`, add `policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY` parameter.
- [ ] Resolve the effective policy in `_run_pipeline_sdk`:
  1. Start with `PoolClassificationPolicy.LAZY`.
  2. If `definition.auth_policy == "strict"`, use `STRICT`.
  3. If the CLI `strict` flag is `True`, use `STRICT` (takes precedence over YAML).
- [ ] Pass `policy` to `classify_pipeline(...)`.
- [ ] Pass `classification.policy` to `execute_pipeline(pool_policy=...)`.
- [ ] Pass `strict` down from `run()` to `_run_pipeline_sdk(...)` (update the call sites).

**Success:** `sq run my-pipeline --strict` results in `policy=STRICT` being used. `sq run my-pipeline` (no flag) results in `policy=LAZY`. A pipeline YAML with `auth_policy: strict` without the CLI flag also results in `STRICT`.

---

### T14 — Test: `--strict` flag and policy resolution

- [ ] In `tests/cli/commands/test_run_pipeline_lazy.py`:
  - [ ] `test_strict_flag_passes_strict_policy_to_classify` — mock `classify_pipeline`; invoke `_run_pipeline_sdk` with `strict=True`; assert `classify_pipeline` called with `policy=STRICT`.
  - [ ] `test_no_flag_passes_lazy_policy_to_classify` — same; `strict=False`; assert `policy=LAZY`.
  - [ ] `test_yaml_auth_policy_strict_overrides_lazy_default` — pipeline definition with `auth_policy="strict"`; `strict=False`; assert `policy=STRICT`.
  - [ ] `test_cli_strict_flag_overrides_yaml_lazy` — `auth_policy="lazy"` in YAML; `strict=True`; assert `policy=STRICT`.

**Success:** All four tests pass.

---

### T15 — Audit and update existing pool-uncertain tests

- [ ] In `tests/pipeline/test_classification.py`, identify any tests that relied on the old conservative default (pool-uncertain → `needs_persistent_session=True` without explicit policy).
- [ ] For each such test, add `policy=PoolClassificationPolicy.STRICT` to the `classify_pipeline` call, or update the assertion to match the new default.
- [ ] In `tests/cli/commands/test_run_pipeline_sdk.py`, identify any tests that expected session construction for pool-uncertain pipelines without a `--strict` flag.
- [ ] Update those tests to pass `strict=True` or to assert `session=None` under the new default.

**Success:** `pytest tests/pipeline/test_classification.py tests/cli/commands/test_run_pipeline_sdk.py` passes with zero failures.

---

### T16 — Full test suite

- [ ] Run: `pytest tests/ -x -q`
- [ ] Confirm: 0 new failures (pre-existing failures in `test_compact_compose_integration.py` are known and acceptable).

**Success:** Test suite passes with zero new failures.

---

### T17 — Build and format

- [ ] Run `ruff format src/ tests/` and commit any formatting changes.
- [ ] Run `ruff check src/ tests/` — address any new lint errors introduced by this slice.
- [ ] Run `pyright src/` — zero new type errors.

**Success:** Ruff and pyright clean.

---

### T18 — Commit

- [ ] Stage all changed files.
- [ ] Commit with message: `feat: lazy pool-auth default; --strict opt-in; mid-run session construction`

---

### T19 — Update slice design and slice plan

- [ ] In `245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md`, set `status: complete` and add commit hash.
- [ ] In `240-slices.pipeline-auth-boundary-flexibility.md`, mark entry 5 `[x]` and add the commit note.
- [ ] Write DEVLOG entry per `prompt.ai-project.system.md § Session State Summary`.

**Success:** Slice plan entry 5 is checked off; slice design status is `complete`.
