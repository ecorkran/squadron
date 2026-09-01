---
docType: review
layer: project
reviewType: code
slice: context-forge-mcp-tool-bridge
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/264-slice.context-forge-mcp-tool-bridge.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260901
dateUpdated: 20260901
reviewedSha: d06a446216868a73e7b2fbbd7f4890456fde08d0
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "McpError and generic-exception branches untested"
    location: "src/squadron/tools/mcp_bridge.py:408"
  - id: F002
    severity: note
    category: style
    summary: "Unnecessary lambda for dict default_factory"
    location: "src/squadron/tools/cf_tools.py:132"
  - id: F003
    severity: note
    category: async-correctness
    summary: "Sync TOML config read inside async executor"
    location: "src/squadron/tools/cf_tools.py:261"
---

# Review: code — slice 264

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

Reviewed at `d06a446`. F001 was accepted and proved to be a live defect rather than a coverage
gap — writing the requested test showed the `except McpError` branch was unreachable, because
the SDK's anyio task groups wrap in-band failures in a `BaseExceptionGroup`. Fixing it also
exposed a second latent misclassification (`TimeoutError` subclasses `OSError`). F002 was
rejected with evidence: bare `dict` as `default_factory` fails this project's strict pyright
config, so the lambda is load-bearing. F003 was acknowledged without change as a pre-existing
codebase-wide pattern, per the reviewer's own non-blocking assessment. Four tests added; full
suite green (3192 passed, 2 skipped), pyright zero errors, ruff clean.

## Findings

### [CONCERN] McpError and generic-exception branches untested

`call_mcp_tool`'s `except McpError` (408-410) and final `except Exception` (411-418) handlers have no corresponding test in `tests/tools/test_mcp_bridge.py`, despite both the module docstring and the test file's own docstring explicitly claiming every failure path is covered and asserts its WARNING. The five tests present cover isError, empty-content, non-text, timeout, and spawn-failure — but not a genuine protocol-level `McpError` or an unexpected/unclassified exception. This is exactly the kind of silent regression the Failure-Mode Enumeration rule is meant to prevent: a future SDK behavior change in either path could go unnoticed.

### [NOTE] Unnecessary lambda for dict default_factory

`CfToolSpec.arg_map`/`param_descriptions` use `field(default_factory=lambda: {})`; `dict` works directly as `default_factory`. Cosmetic only — not enforced by the project's configured ruff rule set.

### [NOTE] Sync TOML config read inside async executor

The async `execute()` closure calls `get_typed_config`/`get_config`, which do synchronous file I/O rather than going through an executor, technically at odds with the python.md <1ms-sync-work-in-async-def rule. This mirrors an existing pattern already in the codebase (`providers/openai/provider.py`), so it's not a regression introduced here — noted for awareness, not blocking.
