---
docType: review
layer: project
reviewType: code
slice: metrology-data-layer-sample-capture-keystone
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260722
dateUpdated: 20260722
findings:
  - id: F001
    severity: concern
    category: configuration
    summary: "Sample-budget lookup ignores project cwd and silently disables capture on bad config"
    location: src/squadron/cli/commands/metrology.py:67-69
  - id: F002
    severity: concern
    category: error-handling
    summary: "`metrology list` does not handle store initialization errors"
    location: src/squadron/cli/commands/metrology.py#list_samples
  - id: F003
    severity: concern
    category: correctness
    summary: "`--judge-config` filter compares the optional template-content hash"
    location: src/squadron/cli/commands/metrology.py#list_samples
  - id: F004
    severity: concern
    category: testing
    summary: "Git-remote timeout failure mode is not covered by tests"
    location: src/squadron/metrology/identity.py#_read_git_remote_url
  - id: F005
    severity: pass
    category: design
    summary: "Surface-agnostic core with blindness enforced by data structure"
    location: src/squadron/metrology/capture.py:34-45
  - id: F006
    severity: pass
    category: reliability
    summary: "Atomic writes and schema-version guard mirror StateManager"
    location: src/squadron/metrology/store.py:68-79
---

# Review: code — slice 320

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] Sample-budget lookup ignores project cwd and silently disables capture on bad config

`_sample_budget()` calls `get_config("metrology.sample_budget")` without passing `cwd`, so a per-project `.squadron.toml` override is missed whenever `--cwd` differs from the process working directory (the manager is consistently called with `cwd=cwd` everywhere else, e.g., `resolve_store_dir` and `derive_project_id`). Worse, if the value is not an `int` it silently falls back to `0`, causing every capture to report `budget_reached` with no error or warning. This violates the CLAUDE.md rule “Never use silent fallback values. Fail explicitly with errors or obviously-placeholder values.” Fix by passing `cwd` to `get_config` and raising a configuration error for non-integer budgets.

### [CONCERN] `metrology list` does not handle store initialization errors

`list_samples` calls `_build_store(resolved_cwd)`, which can raise `MetrologyStoreError` if the configured/default store directory cannot be created. Unlike the `sample` command, `list` has no try/except around store construction, so the user sees a Python traceback instead of a formatted error and a clean non-zero exit. Wrap store creation (and the subsequent list call) in the same exception handling used in the `sample` command.

### [CONCERN] `--judge-config` filter compares the optional template-content hash

The `list --judge-config` option builds a `JudgeConfigId(template_name=..., model=...)` with `template_content_hash=None` and relies on Pydantic equality inside `MetrologyStore.list_samples` (`sample.judge_config != judge_config`). Once `derive_judge_config_id` populates `template_content_hash` for resolvable templates, the equality check will include the hash field and the filter will silently return no matches even for the same template/model. The filter should compare only `template_name` and `model`, either by normalizing the filter in the CLI or by changing the store predicate.

### [CONCERN] Git-remote timeout failure mode is not covered by tests

`_read_git_remote_url` explicitly enumerates the timeout failure mode and emits a `WARNING` log so a chronically slow git is observable. However, `tests/metrology/test_identity.py` does not include a test that patches `subprocess.run` to raise `subprocess.TimeoutExpired` and asserts the warning log or the resulting fallback behavior. Per the Failure-Mode Enumeration rule, every identified failure mode needs a test asserting its observable signal.

### [PASS] Surface-agnostic core with blindness enforced by data structure

`CapturePayload` is a frozen dataclass exposing only `review_file`, `artifact_path`, and `ground_truth_text`, with no field that can accidentally carry judge output. The CLI is a thin wrapper over this core, which lets the future MCP surface reuse the same functions. The tests assert the structural exclusion of judge output rather than a fragile substring scan.

### [PASS] Atomic writes and schema-version guard mirror StateManager

`MetrologyStore._write_atomic` publishes records via a sibling `.tmp` file and an atomic rename, and `_load_raw` rejects unsupported `schema_version` values. Tests cover both the atomic-write failure path and tolerant skipping of corrupt records during listing, matching the reliability patterns in the existing state manager.
