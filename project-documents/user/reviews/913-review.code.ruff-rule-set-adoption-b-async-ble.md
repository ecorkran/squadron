---
docType: review
layer: project
reviewType: code
slice: ruff-rule-set-adoption-b-async-ble
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/913-slice.ruff-rule-set-adoption-b-async-ble.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260817
dateUpdated: 20260817
reviewedSha: 245b3aa349a23b238d2520abb75062abdcb09ea5
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Exception handling improvements follow project conventions"
    location: "src/squadron/cli/commands/*.py"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Exception chaining uses `from None` appropriately at CLI boundaries"
    location: "src/squadron/cli/commands/*.py"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Logging added for previously silent failures"
    location: "Multiple files"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Exception types narrowed where possible"
    location: "src/squadron/cli/commands/doctor_checks.py, src/squadron/pipeline/loader.py, src/squadron/pipeline/state.py, src/squadron/client/http.py"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Async/blocking operations properly threaded"
    location: "tests/metrology/test_audit_harness.py, tests/pipeline/actions/test_commit.py, tests/pipeline/test_executor.py, src/squadron/client/http.py"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "`strict=True` added to zip for fail-fast"
    location: "src/squadron/pipeline/actions/summary.py:279"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Test coverage for new behaviors"
    location: "tests/client/test_http.py, tests/pipeline/actions/test_cf_op.py, tests/pipeline/steps/test_fan_out.py, tests/pipeline/test_dispatch_render.py, tests/pipeline/test_state.py"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "`_render_dispatch` no longer swallows resolution errors"
    location: "src/squadron/pipeline/prompt_renderer.py:155-158"
  - id: F009
    severity: pass
    category: uncategorized
    summary: "ValueError re-raised with context chain"
    location: "src/squadron/pipeline/emit.py:193"
---

# Review: code — slice 913

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Exception handling improvements follow project conventions

The changes add `# noqa: BLE001` comments with explicit justifications for broad exception catches at CLI process boundaries. Per project conventions: "Every try/except must either: (a) re-raise after logging at ERROR level with logger.exception, (b) handle a specific exception with a comment explaining why swallowing is correct, or (c) be a top-level handler at a process boundary."

Examples correctly implemented:
- `dispatch_run.py:66-71` — justification explains pool prefix errors
- `dispatch_run.py:90-95` — justification explains external provider failure modes
- `spawn.py:103-110` — justification explains httpx HTTP call failure modes
- `summary_run.py:69-74` — justification explains external provider failure modes

### [PASS] Exception chaining uses `from None` appropriately at CLI boundaries

The `raise typer.Exit(code=1) from None` pattern correctly suppresses traceback display at CLI boundaries where error messages are already printed to stderr. This is consistent with the pattern that for a CLI tool, a clean user-facing error is preferred over a traceback. The exception is logged with `logger.exception()` before the re-raise, preserving observability.

### [PASS] Logging added for previously silent failures

Changes add `_logger.exception()` calls to make failures observable rather than silent, satisfying the "Failure-Mode Enumeration" rule: "Each identified failure mode must be *observable* (log at WARNING+ or metric increment), not silent."

Verified implementations:
- `dispatch_run.py:67` — logs model resolution failure
- `dispatch_run.py:91` — logs provider dispatch failure
- `spawn.py:110` — logs daemon request failure
- `cf_op.py:116-122` — logs resolution failure with `--embed` degradation context
- `summary.py:257` — logs capture summary failure
- `emit.py:159-166` — logs session compaction failure
- `executor.py:1607-1612` — logs branch model resolution failure
- `executor.py:1664-1669` — logs branch gather failure

### [PASS] Exception types narrowed where possible

Specific exception types used where the raisable set is known:
- `doctor_checks.py:70` — `ModuleNotFoundError` specifically
- `loader.py:142` — `OSError | yaml.YAMLError | PydanticValidationError`
- `state.py:434` — `TypeError` for missing required fields
- `state.py:491-497` — narrowed to `OSError | UnicodeDecodeError | json.JSONDecodeError | SchemaVersionError | ValidationError`
- `http.py:74` — `json.JSONDecodeError | AttributeError`

### [PASS] Async/blocking operations properly threaded

Per Python rules: "Any async def function that calls synchronous code must guarantee that the synchronous code runs in <1ms in the worst case."

Verified correct usage:
- `test_audit_harness.py:464-472` — `subprocess.run` calls wrapped with `asyncio.to_thread`
- `test_commit.py:132,150` — `subprocess.run` calls wrapped with `asyncio.to_thread`
- `test_executor.py:967` — `path.write_text` wrapped with `asyncio.to_thread`
- `http.py:48` — `Path.exists()` wrapped with `await asyncio.to_thread`

### [PASS] `strict=True` added to zip for fail-fast

The `strict=True` parameter to `zip()` ensures mismatched iterable lengths fail immediately rather than silently truncating. This aligns with the "Fail Fast" principle.

### [PASS] Test coverage for new behaviors

New tests cover the failure modes made observable:
- `test_http.py:124-143` — socket vs HTTP transport fallback behavior
- `test_cf_op.py:123-143` — resolution failure skips `--embed` and logs
- `test_fan_out.py:368-389` — pool resolution failure is logged
- `test_dispatch_render.py:170-193` — unresolvable pool propagates (not silently swallowed)
- `test_state.py:518-549` — malformed ActionResult field skipped gracefully

### [PASS] `_render_dispatch` no longer swallows resolution errors

The previous bare `except Exception:` that silently fell back to raw model alias has been removed. Now `resolver.resolve()` propagates normally, and specific handlers in `cf_op.py` and `_render_review` handle resolution failures with logging. This fixes a subtle bug where `pool:review` would silently dispatch as the literal string.

### [PASS] ValueError re-raised with context chain

The `ValueError` for unknown emit destination correctly uses `raise ... from exc` to preserve the exception chain, unlike the broad CLI handlers that use `from None`. This is appropriate since `ValueError` is a specific, enumerable failure at this boundary.
