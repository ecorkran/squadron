---
docType: review
layer: project
reviewType: tasks
slice: pipeline-executor-hardening
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/156-tasks.pipeline-executor-hardening.md
aiModel: moonshotai/kimi-k2.5
status: complete
dateCreated: 20260405
dateUpdated: 20260405
findings:
  - id: F001
    severity: concern
    category: static-analysis
    summary: "Pyright strict mode not specified in lint task"
    location: T13
  - id: F002
    severity: concern
    category: testing
    summary: "Schema version error message content not verified"
    location: T2 (Test T2)
  - id: F003
    severity: note
    category: consistency
    summary: "Test file naming discrepancy with slice design"
    location: tests/cli/test_run_pipeline.py
  - id: F004
    severity: note
    category: design-consistency
    summary: "ExecutionMode not explicitly passed in resume dispatch"
    location: T6, T7
---

# Review: tasks — slice 156

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.5

## Findings

### [CONCERN] Pyright strict mode not specified in lint task

Technical success criterion #3 requires `pyright --strict` to pass with zero errors. Task T13 currently specifies `pyright src/squadron/pipeline/state.py src/squadron/pipeline/loader.py src/squadron/cli/commands/run.py` without the `--strict` flag. While this may be configured in `pyproject.toml`, the task should explicitly include `--strict` to guarantee compliance with the success criterion regardless of configuration drift.

**Recommendation:** Update T13 to run `pyright --strict src/squadron/pipeline/state.py src/squadron/pipeline/loader.py src/squadron/cli/commands/run.py`.

### [CONCERN] Schema version error message content not verified

Functional success criterion #5 requires that resuming a schema v1 state file prints a `SchemaVersionError` with a "clear message". T2's test only verifies that `SchemaVersionError` is raised for schema version 1, but does not verify the error message content. The slice design notes the expected message format ("Unsupported state file schema_version: 1"), but without an explicit assertion on the message string, regressions in error clarity would not be caught.

**Recommendation:** Add a test assertion verifying that the exception message contains "Unsupported state file schema_version" or similar descriptive text.

### [NOTE] Test file naming discrepancy with slice design

The slice design references `tests/cli/test_run.py` for CLI tests, while the tasks file creates `tests/cli/test_run_pipeline.py` as a new file. This is a reasonable organizational choice to prevent test bloat, but represents a minor divergence from the slice design document.

### [NOTE] ExecutionMode not explicitly passed in resume dispatch

Tasks T6 and T7 do not explicitly pass `execution_mode` to `_run_pipeline` or `_run_pipeline_sdk` in the dispatch branches (relying on parameter defaults). While this is technically correct for resume scenarios (where `run_id` is provided, skipping `init_run`), and matches the slice design's architecture section, explicitly passing the mode would be more defensive and self-documenting. This is noted for informational purposes only.
