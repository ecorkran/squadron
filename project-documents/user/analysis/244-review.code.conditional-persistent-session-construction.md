---
docType: review
layer: project
reviewType: code
slice: conditional-persistent-session-construction
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/244-slice.conditional-persistent-session-construction.md
aiModel: claude-haiku-4-5-20251001
status: complete
dateCreated: 20260716
dateUpdated: 20260716
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "Resource cleanup bug: disconnect() called even when connect() fails"
    location: src/squadron/cli/commands/run.py:322-369
  - id: F002
    severity: concern
    category: testing
    summary: "Test mocks incomplete for policy attribute access"
    location: tests/cli/commands/test_run_pipeline_sdk.py:55-75
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Type annotations and modern Python syntax"
    location: src/squadron/cli/commands/run.py:1-50
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Backward compatibility and dependency injection"
    location: src/squadron/cli/commands/run.py:176, 206-207
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Explicit error handling with user-friendly messages"
    location: src/squadron/cli/commands/run.py:300-304, 357-366
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Informative logging at appropriate levels"
    location: src/squadron/cli/commands/run.py:54, 306-320
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Docstring documentation updated for new behavior"
    location: src/squadron/cli/commands/run.py:253-271
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Comprehensive test coverage of classification gate logic"
    location: tests/cli/commands/test_run_pipeline_sdk.py
---

# Review: code — slice 244

**Verdict:** FAIL
**Model:** claude-haiku-4-5-20251001

## Findings

### [FAIL] Resource cleanup bug: disconnect() called even when connect() fails

The `session` object is assigned on line 339 **before** `await session.connect()` on line 340. If `connect()` raises an exception (e.g., `CLINotFoundError`), the exception propagates but `session` is not None, causing the finally block (lines 368-369) to call `await session.disconnect()` on an unconnected session. This directly contradicts the expected behavior tested in `test_t8_connect_failure_propagates_no_disconnect` (line 447), which asserts `mock_session.disconnect.assert_not_awaited()`. 

The code structure:
```python
session = SDKExecutionSession(...)  # Assigned before connect
await session.connect()  # If this raises...
# ... exception propagates to finally:
finally:
    if session is not None:  # True, so disconnect() is called
        await session.disconnect()
```

To fix this, assign `session` only after a successful `connect()`, or use a temporary variable:
```python
temp_session = SDKExecutionSession(...)
await temp_session.connect()  # If this fails, exception propagates, session stays None
session = temp_session  # Only assign if connect() succeeds
```

This is a test-code mismatch that will cause the test suite to fail.

---

### [CONCERN] Test mocks incomplete for policy attribute access

The `_make_classification()` helper returns a `MagicMock(spec=PipelineClassification)` without setting the `policy` attribute. Meanwhile, the actual code (line 355 in run.py) accesses `classification.policy` and passes it to `_run_pipeline`. While the real `PipelineClassification` class does define `policy` with a default value, the test mocks should explicitly set this attribute for clarity and to catch potential regressions. Additionally, the tests that use `_make_classification()` mock `_run_pipeline`, so they don't actually exercise the code path that accesses `classification.policy`, which masks test coverage gaps.

All test helper mocks should explicitly set attributes they provide (lines 72-74 in test_run_pipeline_sdk.py and lines 121-124 in test_sdk_wiring.py).

---

### [PASS] Type annotations and modern Python syntax

All function signatures are properly type-hinted using modern Python 3.10+ union syntax (`|` instead of `Union`). The use of `TYPE_CHECKING` block (lines 17-18) to avoid circular imports is correct. The type annotation `session: SDKExecutionSession | None` on line 322 without initialization is valid and intentional (subsequent if/else branches assign values to all code paths).

---

### [PASS] Backward compatibility and dependency injection

The new `pool_backend: PoolBackend | None = None` parameter maintains backward compatibility by defaulting to None. The code correctly constructs `DefaultPoolBackend()` only when needed (lines 206-207), following the Dependency Inversion Principle. This allows tests to inject a mock backend and enables the pool_backend to be shared between the classification and authoritative resolvers (lines 288-298).

---

### [PASS] Explicit error handling with user-friendly messages

Specific exception types are caught:
- `ClassificationError` (lines 302-304) with a user-friendly error message
- `LazySessionConnectError` (lines 357-366) with contextual guidance (resume command)

Errors are not silently swallowed; they're logged and re-raised with `typer.Exit(1)`, following the project's fail-fast principle.

---

### [PASS] Informative logging at appropriate levels

Module-level logger (line 54) logs classification results at INFO level (summary: shape and step count) and DEBUG level (detailed step classification info). This provides good observability without excessive verbosity, following Python logging best practices.

---

### [PASS] Docstring documentation updated for new behavior

The `_run_pipeline_sdk` docstring is updated to document the new classification-first flow, the conditional session construction, non-SDK pipeline handling, and updated exit conditions (now including classification failure).

---

### [PASS] Comprehensive test coverage of classification gate logic

The test file provides coverage of:
- T3: Backward-compatible fallback (no pool_backend parameter)
- T1-T5, T8: Classification gate scenarios (no session needed, session needed, one-shot only, uncertain pools, classification error, connection failure, exception propagation)
- T6-T7: Resume path re-classification

Tests verify session construction, connection, disconnection, and error handling across multiple scenarios. However, they don't verify the `pool_policy` parameter is correctly passed to `_run_pipeline` (noted above in CONCERN).
