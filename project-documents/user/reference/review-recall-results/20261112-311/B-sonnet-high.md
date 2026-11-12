{
  "verdict": "CONCERNS",
  "findings": [
    {
      "severity": "CONCERN",
      "title": "Docstring and comment still say preflight names the ceiling command",
      "description": "The module docstring says the PM's ceiling script is \"already run (the preflight names its command if not)\". That is no longer true. `NO_CEILING_HINT` (`cutover_304_checks.py:42`) now only points at the `--estimate` run, and the command comes from `ceiling_command`. The comment at `cutover_304_checks.py:104` (\"absent is reported below with the command\") is stale in the same way. The \"Steps\" list at lines 16-25 also omits two things this diff added: the `--estimate` mode, and the gate-issue and dataset-edge refusals in step 1. Update these so the operator-facing docs match behaviour.",
      "file_ref": null,
      "category": "documentation-drift",
      "raw_category": null,
      "location": "scripts/cutover_304_first_purchase.py:12-13"
    },
    {
      "severity": "CONCERN",
      "title": "Bare `dict` and `list` annotations in new tests",
      "description": "The project requires strict pyright with tests included. `_request`, `_unit` and `_coverage` return bare `dict`. `_report` takes `units: list[dict] | None` and `exhausted: list | None`. Bare generics trigger `reportMissingTypeArgument` in strict mode. `_status(...) -> object` also hides that it returns a `CompletedProcess`. It only type-checks because `pv` is a `ModuleType`. Use `dict[str, Any]`, `list[ExhaustedRequest]` and `subprocess.CompletedProcess[str]`.",
      "file_ref": null,
      "category": "type-contract-debt",
      "raw_category": null,
      "location": "test/unit/scripts/test_purchase_verdicts.py#_request"
    },
    {
      "severity": "CONCERN",
      "title": "Test helpers copy-pasted across test files instead of living in `conftest.py`",
      "description": "`_load(name)` (which inserts `scripts/` onto `sys.path`) is defined separately in `test_purchase_accounting.py:16`, `test_purchase_verdicts.py:19` and `test_cutover_304_first_purchase.py:24`. The `cutover_error` fixture is repeated in four files in this directory. The testing rules say shared fixtures belong in `conftest.py`. Move `_load` and `cutover_error` into `test/unit/scripts/conftest.py`.",
      "file_ref": null,
      "category": "consistency-rot",
      "raw_category": null,
      "location": "test/unit/scripts/test_purchase_accounting.py:16"
    },
    {
      "severity": "NOTE",
      "title": "Script names still say 304 though the scripts are now shared",
      "description": "The docstring says the script is \"shared by every purchase slice\". `argparse` still uses `prog=\"cutover_304_first_purchase.py\"`, and the `cutover_304_checks` and `cutover_304_evidence` modules keep their slice-specific names. New modules are named `purchase_*`. Renaming would churn imports and tests, so this is acceptable now. A later rename to `purchase_cutover*` would remove the mismatch.",
      "file_ref": null,
      "category": "consistency-rot",
      "raw_category": null,
      "location": "scripts/cutover_304_first_purchase.py:1-10"
    },
    {
      "severity": "NOTE",
      "title": "Resubmit matching is by schema and range only, so it errs towards refusing",
      "description": "`resubmit_origins` keeps the earliest `requested_at` per `(schema, start, end)`. A jobless row from before the cutover that shares a range with a legitimate new resubmit will refuse the cutover. The docstring states this and it fails safe, so no action is needed. A refusal will name the original's timestamp.",
      "file_ref": null,
      "category": "correctness",
      "raw_category": null,
      "location": "scripts/cutover_304_checks.py:143-165"
    },
    {
      "severity": "PASS",
      "title": "Failures stop explicitly, with no silent defaults",
      "description": "`check_gate_issue`, `check_dataset_edge`, `calendar_for` and `product_of_symbols` all raise `CutoverError` with distinct messages on missing, unparseable or unknown input. Every `except` is narrow and re-raises with `from exc`. The `except SystemExit` in `main` is documented as a process-boundary handler. This follows the \"no silent fallback\" rule.",
      "file_ref": null,
      "category": "error-handling-observability",
      "raw_category": null,
      "location": "scripts/purchase_verdicts.py"
    },
    {
      "severity": "PASS",
      "title": "Tests use the real producer shapes and cover the new behaviour",
      "description": "The tests build their inputs from the real code. `_accounting` uses `accounting_futures._product_payload`, `_coverage` uses `coverage_to_dict`, and the bar-job-dir test renders rows through `tick_debug_cmds._cell`. This matches the project's parser-fixture rule. The suite covers:\n- the gates stopping before install, with nothing written\n- `--estimate` buying nothing and writing no state\n- boundary equality on the dataset edge\n- each unaccounted-for session bucket\n- per-product calendars",
      "file_ref": null,
      "category": "test-debt",
      "raw_category": null,
      "location": "test/unit/scripts/test_cutover_304_first_purchase.py"
    }
  ],
  "structured_findings": [
    {
      "id": "F001",
      "severity": "concern",
      "category": "documentation-drift",
      "raw_category": null,
      "summary": "Docstring and comment still say preflight names the ceiling command",
      "location": "scripts/cutover_304_first_purchase.py:12-13",
      "location_verified": true
    },
    {
      "id": "F002",
      "severity": "concern",
      "category": "type-contract-debt",
      "raw_category": null,
      "summary": "Bare `dict` and `list` annotations in new tests",
      "location": "test/unit/scripts/test_purchase_verdicts.py#_request",
      "location_verified": null
    },
    {
      "id": "F003",
      "severity": "concern",
      "category": "consistency-rot",
      "raw_category": null,
      "summary": "Test helpers copy-pasted across test files instead of living in `conftest.py`",
      "location": "test/unit/scripts/test_purchase_accounting.py:16",
      "location_verified": true
    },
    {
      "id": "F004",
      "severity": "note",
      "category": "consistency-rot",
      "raw_category": null,
      "summary": "Script names still say 304 though the scripts are now shared",
      "location": "scripts/cutover_304_first_purchase.py:1-10",
      "location_verified": true
    },
    {
      "id": "F005",
      "severity": "note",
      "category": "correctness",
      "raw_category": null,
      "summary": "Resubmit matching is by schema and range only, so it errs towards refusing",
      "location": "scripts/cutover_304_checks.py:143-165",
      "location_verified": true
    },
    {
      "id": "F006",
      "severity": "pass",
      "category": "error-handling-observability",
      "raw_category": null,
      "summary": "Failures stop explicitly, with no silent defaults",
      "location": "scripts/purchase_verdicts.py",
      "location_verified": null
    },
    {
      "id": "F007",
      "severity": "pass",
      "category": "test-debt",
      "raw_category": null,
      "summary": "Tests use the real producer shapes and cover the new behaviour",
      "location": "test/unit/scripts/test_cutover_304_first_purchase.py",
      "location_verified": null
    }
  ],
  "template_name": "code",
  "input_files": {
    "cwd": "/private/tmp/claude-501/-Users-manta-source-repos-manta-squadron/0805d86d-8435-4d98-bf07-042000f9e694/scratchpad/exp311/t307",
    "diff": "dcfb86f1...HEAD",
    "diff_exclude_patterns": "*.md,*.yaml,*.yml,*.toml,*.json,*.txt,*.lock,*.csv,*.svg,*.png,*.jpg,*.gif,*.ico"
  },
  "timestamp": "2026-11-12T10:32:13.255902",
  "model": "claude-sonnet-5-5",
  "score": null,
  "criteria": null,
  "provenance": null,
  "tools_given": [
    "read_file",
    "list_files",
    "grep"
  ],
  "tool_calls_made": 6,
  "categories_normalized": true,
  "stop_reason": "end_turn",
  "reasoning_chars": 0,
  "failed_tool_calls": 0,
  "recovery_turn_used": false,
  "output_budget_exhausted": false,
  "max_output_tokens": null,
  "system_prompt_mode": "preset+append",
  "setting_sources": "project",
  "fallback_used": false,
  "verdictSource": "stated",
  "diff_chars": 97780,
  "diff_chars_injected": 97780,
  "diff_truncated": false,
  "diff_cut_files": [],
  "requested_model": "claude-sonnet-5-5",
  "answering_models": [
    "claude-sonnet-5-5"
  ],
  "model_substituted": false,
  "run_id": null,
  "squadron_version": "0.24.28",
  "finding_scan": {
    "total": 7,
    "in_fences": 0,
    "in_section": 7,
    "surviving": 7
  },
  "effort": "high",
  "profile": "sdk",
  "turns": 7,
  "prompt_tokens": 359697,
  "cached_tokens": 158998,
  "cache_write_tokens": 200693,
  "completion_tokens": 5952,
  "reasoning_tokens": null,
  "duration_seconds": 51.06577595905401,
  "cost_usd": 0.8834649000000001,
  "cost_basis": "provider"
}