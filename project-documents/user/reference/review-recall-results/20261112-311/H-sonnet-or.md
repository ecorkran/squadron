{
  "verdict": "CONCERNS",
  "findings": [
    {
      "severity": "CONCERN",
      "title": "Docs and comments still say the preflight names the ceiling command",
      "description": "The ceiling command is now derived from the estimate. A missing ceiling raises `\"{key} is not set in the env file; the PM sets the ceilings with the command the --estimate run prints\"` (`NO_CEILING_HINT`). It no longer names a command.\n\nTwo pieces of text still describe the old behaviour:\n- The inline comment in `_ceiling` says `# absent is reported below with the command, same as empty`.\n- The module docstring of `cutover_304_first_purchase.py` says \"the PM's ceiling script already run (the preflight names its command if not)\".\n\nAn operator reading the docstring would expect the preflight to print a runnable command. It now only points to `--estimate`. Update both texts to match.",
      "file_ref": null,
      "category": "documentation-drift",
      "raw_category": null,
      "location": "scripts/cutover_304_checks.py:105-111"
    },
    {
      "severity": "CONCERN",
      "title": "Unused constant `EXIT_USAGE`",
      "description": "`EXIT_USAGE = 2` was added, but nothing in the file uses it. A grep of `scripts/` shows the only other `EXIT_USAGE` is an unrelated definition in `wal_segment_name.py`.\n\n`main` returns `int(exc.code or 0)` from argparse's `SystemExit`, so the constant does nothing. Remove it. Alternatively, use it to document or assert that argparse's usage exit code is 2.",
      "file_ref": null,
      "category": "architectural-decay",
      "raw_category": null,
      "location": "scripts/cutover_304_first_purchase.py:79"
    },
    {
      "severity": "NOTE",
      "title": "`SystemExit` caught to turn argparse exits into return codes",
      "description": "Catching `SystemExit` around `parse_args` is justified by an inline comment and is acceptable. Two small points remain:\n- `int(exc.code or 0)` assumes `code` is an int. That holds for argparse today.\n- `_parser()` uses `__doc__.split(\"\\n\")[0]`. Under `python -OO`, `__doc__` is `None` and this would crash. That is unlikely for an operator script.",
      "file_ref": null,
      "category": "consistency-rot",
      "raw_category": null,
      "location": "scripts/cutover_304_first_purchase.py:main"
    },
    {
      "severity": "NOTE",
      "title": "Tests are loosely typed and reach into private functions",
      "description": "The helpers use bare `-> dict`, `list | None` and `-> object` return types, for example `_status`, `_request` and `_unit`. These would not pass the project's `typeCheckingMode = \"strict\"` pyright rule, which includes `tests`.\n\nSeveral tests also call private functions directly: `pv._unaccounted`, `fp._steps` and `ev._session_placement`. This is acceptable, but it ties the tests to internals.",
      "file_ref": null,
      "category": "test-debt",
      "raw_category": null,
      "location": "test/unit/scripts/test_purchase_verdicts.py:130-160"
    },
    {
      "severity": "PASS",
      "title": "Behaviour changes are covered by tests",
      "description": "The new logic is tested close to its implementation:\n- Ceiling rounding, including the boundary where a multiple of the step is not raised.\n- The resubmit origin rules, including the earliest origin on a shared range.\n- A per-product calendar, with no default for an unmapped product.\n- `bar_job_dirs` against the rows the real CLI renders (`_cell`).\n- The gate issue and the dataset-edge checks, including naive and unparseable timestamps and a failing `status`.\n- The exit rule for unaccounted sessions, retry-exhausted requests and `over` volume sessions.\n\nFailures consistently raise `CutoverError` with distinct messages. No swallowed exceptions were found in the reviewed code.",
      "file_ref": null,
      "category": "test-debt",
      "raw_category": null,
      "location": "test/unit/scripts/test_cutover_304_checks.py"
    }
  ],
  "structured_findings": [
    {
      "id": "F001",
      "severity": "concern",
      "category": "documentation-drift",
      "raw_category": null,
      "summary": "Docs and comments still say the preflight names the ceiling command",
      "location": "scripts/cutover_304_checks.py:105-111",
      "location_verified": true
    },
    {
      "id": "F002",
      "severity": "concern",
      "category": "architectural-decay",
      "raw_category": null,
      "summary": "Unused constant `EXIT_USAGE`",
      "location": "scripts/cutover_304_first_purchase.py:79",
      "location_verified": true
    },
    {
      "id": "F003",
      "severity": "note",
      "category": "consistency-rot",
      "raw_category": null,
      "summary": "`SystemExit` caught to turn argparse exits into return codes",
      "location": "scripts/cutover_304_first_purchase.py:main",
      "location_verified": null
    },
    {
      "id": "F004",
      "severity": "note",
      "category": "test-debt",
      "raw_category": null,
      "summary": "Tests are loosely typed and reach into private functions",
      "location": "test/unit/scripts/test_purchase_verdicts.py:130-160",
      "location_verified": true
    },
    {
      "id": "F005",
      "severity": "pass",
      "category": "test-debt",
      "raw_category": null,
      "summary": "Behaviour changes are covered by tests",
      "location": "test/unit/scripts/test_cutover_304_checks.py",
      "location_verified": null
    }
  ],
  "template_name": "code",
  "input_files": {
    "cwd": "/private/tmp/claude-501/-Users-manta-source-repos-manta-squadron/0805d86d-8435-4d98-bf07-042000f9e694/scratchpad/exp311/t307",
    "diff": "dcfb86f1...HEAD",
    "diff_exclude_patterns": "*.md,*.yaml,*.yml,*.toml,*.json,*.txt,*.lock,*.csv,*.svg,*.png,*.jpg,*.gif,*.ico"
  },
  "timestamp": "2026-11-12T11:02:56.361817",
  "model": "anthropic/claude-sonnet-5.5",
  "score": null,
  "criteria": null,
  "provenance": null,
  "tools_given": [
    "read_file",
    "list_files",
    "grep"
  ],
  "tool_calls_made": 10,
  "categories_normalized": true,
  "stop_reason": "stop",
  "reasoning_chars": 5073,
  "failed_tool_calls": 0,
  "recovery_turn_used": false,
  "output_budget_exhausted": false,
  "max_output_tokens": null,
  "system_prompt_mode": "custom",
  "setting_sources": "n/a (non-SDK)",
  "fallback_used": false,
  "verdictSource": "stated",
  "diff_chars": 97780,
  "diff_chars_injected": 97780,
  "diff_truncated": false,
  "diff_cut_files": [],
  "requested_model": "anthropic/claude-sonnet-5-5",
  "answering_models": [
    "anthropic/claude-sonnet-5.5"
  ],
  "model_substituted": true,
  "run_id": null,
  "squadron_version": "0.24.28",
  "finding_scan": {
    "total": 5,
    "in_fences": 0,
    "in_section": 5,
    "surviving": 5
  },
  "effort": null,
  "profile": "openrouter",
  "turns": 6,
  "prompt_tokens": 438943,
  "cached_tokens": 0,
  "cache_write_tokens": null,
  "completion_tokens": 6769,
  "reasoning_tokens": 4227,
  "duration_seconds": 57.29475574987009,
  "cost_usd": null,
  "cost_basis": null
}