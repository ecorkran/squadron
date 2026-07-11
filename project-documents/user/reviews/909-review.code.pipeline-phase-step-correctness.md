---
docType: review
layer: project
reviewType: code
slice: pipeline-phase-step-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/909-slice.pipeline-phase-step-correctness.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260710
dateUpdated: 20260710
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Unhandled ValueError when slice_param cannot be converted to int"
    location: src/squadron/pipeline/executor.py:802
  - id: F002
    severity: concern
    category: correctness
    summary: "Misleading error message when numeric slice is not found"
    location: src/squadron/cli/commands/review.py:652-656
  - id: F003
    severity: concern
    category: code-quality
    summary: "DRY violation — _phase_artifact_cf_client duplicated across 4 test files"
    location: tests/pipeline/test_cli_integration.py:103
  - id: F004
    severity: concern
    category: error-handling
    summary: "Swallowed exception without logging or justification"
    location: src/squadron/cli/commands/review.py:493-494
  - id: F005
    severity: note
    category: typing
    summary: "cf_client typed as Any instead of CfClientProtocol"
    location: src/squadron/pipeline/executor.py:109
  - id: F006
    severity: note
    category: code-quality
    summary: "Hard-coded task files path prefix"
    location: src/squadron/pipeline/executor.py:118
  - id: F007
    severity: note
    category: code-quality
    summary: "StateManager instantiated twice with same config in execute_pipeline"
    location: src/squadron/pipeline/executor.py:984-985
  - id: F008
    severity: pass
    category: design
    summary: "Dispatch artifact post-condition design is fail-closed and well-logged"
    location: src/squadron/pipeline/executor.py:112-152
  - id: F009
    severity: pass
    category: testing
    summary: "Test coverage for dispatch artifact post-condition is thorough"
    location: tests/pipeline/test_executor.py:635-932
---

# Review: code — slice 909

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Unhandled ValueError when slice_param cannot be converted to int

In `_dispatch_artifact_post_condition_error`, the call `int(str(slice_param))` can raise `ValueError` if `slice_param` is an unresolved placeholder string (e.g., `"{slice.index}"` from a mis-resolved loop context). This `ValueError` is NOT caught — it propagates as an unhandled exception, crashing the pipeline. The `_check_dispatch_artifact_written` function catches `ValueError` from `_expected_artifact_paths`, but the conversion happens *before* that call, so it escapes. This failure mode is also untested. A `try/except ValueError` wrapping the conversion (returning an error message like the other fail-closed branches) would close this gap.

### [CONCERN] Misleading error message when numeric slice is not found

The condition `if not slice_info and not diff and not files` with `slice_number is not None` is reached both when the slice number is non-numeric *and* when a valid numeric slice simply doesn't exist in ContextForge. The message always says `slice number '{slice_number}' is not numeric`, which is incorrect for the "slice not found" case. The message should distinguish between these failure modes — e.g., "slice '{slice_number}' not found" vs. "not numeric".

### [CONCERN] DRY violation — _phase_artifact_cf_client duplicated across 4 test files

The `_phase_artifact_cf_client` helper is copy-pasted verbatim into `test_cli_integration.py`, `test_executor_integration.py`, `test_sdk_integration.py`, and `test_state_integration.py`. Similarly, `_artifact_writing_action` is duplicated in `test_cli_integration.py` and `test_state_integration.py`, and `_artifact_writing_success_registry` appears in `test_executor_integration.py`. These should be extracted to a shared `conftest.py` or test utility module. Per project convention: "Do not duplicate logic. Respect DRY."

### [CONCERN] Swallowed exception without logging or justification

The `try/except (ContextForgeNotAvailable, ContextForgeError)` block catches specific exceptions but sets `project_name = "unknown"` without logging the failure. The project convention requires that every `try/except` must either (a) re-raise after logging at ERROR, (b) handle a specific exception with a comment justifying why swallowing is correct, or (c) be a top-level handler at a process boundary. This is none of those — there's no `logger.warning` or `logger.exception` call, and no inline comment justifying the silent fallback. Add at minimum a `logger.warning("Could not resolve project name from ContextForge: %s", exc)` or an inline comment per convention (b).

### [NOTE] cf_client typed as Any instead of CfClientProtocol

`_expected_artifact_paths`, `_check_dispatch_artifact_written`, and `_dispatch_artifact_post_condition_error` all use `cf_client: Any`. The `CfClientProtocol` is already defined in `squadron.review.persistence` and used by `resolve_slice_info`. Using `Any` loses type safety and contradicts the project convention to "Program to interfaces (contracts)." Since `resolve_slice_info` already requires `CfClientProtocol`, the executor functions should type the parameter the same way.

### [NOTE] Hard-coded task files path prefix

`f"project-documents/user/tasks/{f}"` is a magic string. If the task files directory convention changes, this string must be updated separately from wherever else it may be defined. Per project convention: "Never scatter comparison values across code." Consider extracting this prefix to a named constant or deriving it from the same source that resolves it in `persistence.py`.

### [NOTE] StateManager instantiated twice with same config in execute_pipeline

`StateManager(runs_dir=runs_dir)` is already constructed earlier in `execute_pipeline` (line ~712 as `_state_mgr`). In `_execute_step_once`, it's constructed again to load `started_at`. Consider passing the already-loaded `RunState` or the existing `StateManager` instance through the call chain to avoid redundant instantiation and ensure consistency.

### [PASS] Dispatch artifact post-condition design is fail-closed and well-logged

Every branch in `_check_dispatch_artifact_written` and `_dispatch_artifact_post_condition_error` fails closed with a WARNING-level log message. The post-condition correctly detects absent, stale, and unreadable artifacts. The `expected_artifact_kind` property cleanly scopes the check to design/tasks phases only, leaving implement and generic dispatch unaffected. Good adherence to the failure-mode enumeration principle.

### [PASS] Test coverage for dispatch artifact post-condition is thorough

The `TestDispatchArtifactPostCondition` class covers fresh artifact, absent artifact, stale artifact, unresolvable slice, permission error, implement-phase skip, bare dispatch skip, and no-artifact routing — eight distinct failure/success modes including log verification and routing assertions. This is excellent test-with (not test-after) coverage.
