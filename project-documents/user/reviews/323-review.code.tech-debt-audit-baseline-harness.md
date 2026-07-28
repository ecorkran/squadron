---
docType: review
layer: project
reviewType: code
slice: tech-debt-audit-baseline-harness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260727
dateUpdated: 20260727
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "`audit.py` far exceeds the ~300-line file-size guideline"
    location: src/squadron/metrology/audit.py
  - id: F002
    severity: concern
    category: uncategorized
    summary: "Broad `except Exception` in `run_audit` catches programming errors as stream errors"
    location: src/squadron/metrology/audit.py:518
  - id: F003
    severity: concern
    category: uncategorized
    summary: "`AuditRun.model` records provider name instead of actual model when model is unpinned"
    location: src/squadron/metrology/audit.py:567
  - id: F004
    severity: note
    category: uncategorized
    summary: "`list_noise_floors` does not sort results, unlike `list_audit_runs`"
    location: src/squadron/metrology/store.py:279
  - id: F005
    severity: note
    category: uncategorized
    summary: "Rate-limit parser shim monkey-patches private SDK internals"
    location: src/squadron/providers/sdk/rate_limit.py:84
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Excellent failure-mode enumeration and test coverage"
    location: tests/metrology/test_audit_harness.py
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Rate-limit logic properly centralized (DRY)"
    location: src/squadron/providers/sdk/rate_limit.py
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Surface-agnostic design maintained across audit modules"
    location: src/squadron/metrology/audit.py
---

# Review: code — slice 323

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] `audit.py` far exceeds the ~300-line file-size guideline

The CLAUDE.md convention states "Keep source files to ~300 lines." At 789 lines, `audit.py` significantly exceeds this. The module handles multiple responsibilities: skill resolution, prompt building, pre-flight validation, agent execution, output collection, file discovery, and result construction. Consider splitting into focused modules (e.g., `audit_preflight.py` for pre-flight checks, `audit_prompt.py` for skill resolution and prompt building, keeping `run_audit` as the orchestrator). The test file `test_audit_harness.py` at 814 lines has the same issue.

### [CONCERN] Broad `except Exception` in `run_audit` catches programming errors as stream errors

The `except Exception as exc:` block catches all `Exception` subclasses, including `TypeError`, `AttributeError`, and other programming bugs, converting them to `AuditRunFailure.STREAM_ERROR`. Per the project's Python rules, every `try/except` must either (a) re-raise after logging at ERROR via `logger.exception`, (b) handle a specific exception type with a justification comment, or (c) be a documented top-level handler. While this is at a process boundary, it logs at WARNING (not ERROR) using `_logger.warning` rather than `logger.exception`, meaning tracebacks are lost—making debugging of real bugs impossible. It should either catch specific infrastructure exceptions (`ConnectionError`, `ProviderError`, etc.) or log at ERROR with `logger.exception` before converting to the typed failure.

### [CONCERN] `AuditRun.model` records provider name instead of actual model when model is unpinned

When `resolved_model` is `None` (no model configured), the code stores `provider_profile.provider` (e.g., `"sdk"`) as the model: `model=resolved_model or provider_profile.provider`. The actual model used is the CLI's default (a 1M-context Opus, per the config key description). This is misleading: two runs taken under different CLI defaults would show the same `model` value, masking exactly the instrument drift the system is designed to detect. The config description explicitly warns "an unpinned model is not a fixed instrument, so a floor measured today is not comparable to one measured after that default shifts"—but the persisted record doesn't even correctly identify the instrument. The `model` field should be `str | None` to allow `None` when the model is unknown, or the actual model should be captured from the run.

### [NOTE] `list_noise_floors` does not sort results, unlike `list_audit_runs`

`list_audit_runs` sorts by `measured_at` descending (newest first), but `list_noise_floors` returns results in filesystem glob order (`sorted(self._store_dir.glob("*.json"))` sorts by path, not by date). Callers that depend on ordering (e.g., to pick the "latest" floor) would get non-deterministic results. The `baseline_report` function uses a dict to key floors, so it's not affected, but the inconsistency could cause subtle bugs in future consumers.

### [NOTE] Rate-limit parser shim monkey-patches private SDK internals

`install_rate_limit_parser_shim()` patches `claude_agent_sdk._internal.message_parser.parse_message` and `claude_agent_sdk._internal.client.parse_message`—private internals of a third-party package. This is fragile: any SDK upgrade could change internal module structure. The code is documented as temporary ("Remove once the pin moves past a parser with native support") and is idempotent with tests, but the fragility is a maintenance risk. The two-site patching requirement (documented in the code) illustrates how easily this could break.

### [PASS] Excellent failure-mode enumeration and test coverage

The test suite demonstrates thorough failure-mode enumeration: timeout, mid-stream exception, absent block, malformed block, rate limiting, dirty worktree, stale audit files, and HEAD movement. Each failure path is asserted to persist nothing and emit an observable WARNING log. The tests use stubbed agents (no token cost) and include a real-world fixture (`real-audit-migratory-viewer.md`) per the project's parser-fixture rule. The test-with approach is evident throughout—tests are co-located and cover the implementation comprehensively.

### [PASS] Rate-limit logic properly centralized (DRY)

The `rate_limit.py` module consolidates the retry budget, backoff calculation, event classification, and cumulative stats that were previously duplicated across `agent.py` and `sdk_session.py`. The distinction between informational rate-limit events (absorbed by the shim) and rejected-status events (re-raised for backoff) is well-documented and tested. The `RateLimitStats` dataclass provides honest cost reporting per run.

### [PASS] Surface-agnostic design maintained across audit modules

The core audit modules (`audit.py`, `audit_parse.py`, `audit_variance.py`, `audit_report.py`) contain no `typer` or `rich` imports, maintaining the 320/321/322 CLI/core split. All rendering lives in `cli/commands/metrology.py`. A test (`test_audit_modules_are_surface_agnostic`) asserts this mechanically via AST inspection, preventing future regressions.
