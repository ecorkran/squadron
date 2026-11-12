{
  "verdict": "CONCERNS",
  "findings": [
    {
      "severity": "CONCERN",
      "title": "Stale comment in `_ceiling` points to a command that is no longer in the message",
      "description": "The inline comment says an absent ceiling \"is reported below with the command\". The error now carries only `NO_CEILING_HINT`, which says to run `--estimate`, not a command. The comment should say the hint is reported. I did not re-read the file after the diff, so confirm the comment text is still there.",
      "file_ref": null,
      "category": "documentation-drift",
      "raw_category": null,
      "location": "scripts/cutover_304_checks.py#_ceiling"
    },
    {
      "severity": "CONCERN",
      "title": "Resubmit matching is by range only, so it is a heuristic",
      "description": "The estimate carries no request id. A resubmit is therefore matched to a `debug requests` row by `(schema, start, end)`, and the earliest jobless row wins. If a pre-cutover jobless row shares a range with a legitimate in-cutover resubmit, the cutover stops with a false \"before this cutover started\". That is the safe direction, and the docstring documents it. The error should still say the match is by range, so the operator knows why it stopped. A row that is not jobless is never considered, which is intended.",
      "file_ref": null,
      "category": "correctness",
      "raw_category": null,
      "location": "scripts/cutover_304_checks.py#resubmit_origins"
    },
    {
      "severity": "CONCERN",
      "title": "`main` catches `SystemExit` to keep argparse's exit code",
      "description": "The handler is narrow and commented, and it is a process-boundary handler, so it fits rule (c). `int(exc.code or 0)` would silently turn a non-int code (a string message) into `int(\"...\")` and raise `ValueError`. That cannot happen with argparse's own exits. Using `parser.exit_on_error=False` or checking `isinstance(exc.code, int)` would be more explicit.",
      "file_ref": null,
      "category": "error-handling-observability",
      "raw_category": null,
      "location": "scripts/cutover_304_first_purchase.py#main"
    },
    {
      "severity": "NOTE",
      "title": "Function size and untyped local",
      "description": "`origins = {}` has no annotation, which strict pyright flags as partially unknown. `purchase_verdicts.not_caught_up_report` is about 30 lines, over the preferred 20. The module is just under the 300-line target. Neither blocks.",
      "file_ref": null,
      "category": "consistency-rot",
      "raw_category": null,
      "location": "scripts/cutover_304_first_purchase.py#judge"
    },
    {
      "severity": "PASS",
      "title": "Hard-coded values moved to the universe and calendar mapping",
      "description": "Coverage reads, products and session calendars are now derived from `TICK_UNIVERSE` and `calendar_for_product`. An open-ended want and an unmapped product both raise rather than falling back to a default. Tests cover both cases and the real CLI rendering of `symbols`.",
      "file_ref": null,
      "category": "architectural-decay",
      "raw_category": null,
      "location": "scripts/cutover_304_evidence.py#coverage_reads"
    }
  ],
  "structured_findings": [
    {
      "id": "F001",
      "severity": "concern",
      "category": "documentation-drift",
      "raw_category": null,
      "summary": "Stale comment in `_ceiling` points to a command that is no longer in the message",
      "location": "scripts/cutover_304_checks.py#_ceiling",
      "location_verified": null
    },
    {
      "id": "F002",
      "severity": "concern",
      "category": "correctness",
      "raw_category": null,
      "summary": "Resubmit matching is by range only, so it is a heuristic",
      "location": "scripts/cutover_304_checks.py#resubmit_origins",
      "location_verified": null
    },
    {
      "id": "F003",
      "severity": "concern",
      "category": "error-handling-observability",
      "raw_category": null,
      "summary": "`main` catches `SystemExit` to keep argparse's exit code",
      "location": "scripts/cutover_304_first_purchase.py#main",
      "location_verified": null
    },
    {
      "id": "F004",
      "severity": "note",
      "category": "consistency-rot",
      "raw_category": null,
      "summary": "Function size and untyped local",
      "location": "scripts/cutover_304_first_purchase.py#judge",
      "location_verified": null
    },
    {
      "id": "F005",
      "severity": "pass",
      "category": "architectural-decay",
      "raw_category": null,
      "summary": "Hard-coded values moved to the universe and calendar mapping",
      "location": "scripts/cutover_304_evidence.py#coverage_reads",
      "location_verified": null
    }
  ],
  "template_name": "code",
  "input_files": {
    "cwd": "/private/tmp/claude-501/-Users-manta-source-repos-manta-squadron/0805d86d-8435-4d98-bf07-042000f9e694/scratchpad/exp311/t307",
    "diff": "dcfb86f1...HEAD",
    "diff_exclude_patterns": "*.md,*.yaml,*.yml,*.toml,*.json,*.txt,*.lock,*.csv,*.svg,*.png,*.jpg,*.gif,*.ico"
  },
  "timestamp": "2026-11-12T13:27:17.790799",
  "model": "claude-sonnet-5-5",
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
    "total": 5,
    "in_fences": 0,
    "in_section": 5,
    "surviving": 5
  },
  "effort": null,
  "profile": "sdk",
  "turns": 11,
  "prompt_tokens": 479599,
  "cached_tokens": 397647,
  "cache_write_tokens": 81938,
  "completion_tokens": 4133,
  "reasoning_tokens": null,
  "duration_seconds": 46.172828333918005,
  "cost_usd": 0.41413479999999997,
  "cost_basis": "provider"
}