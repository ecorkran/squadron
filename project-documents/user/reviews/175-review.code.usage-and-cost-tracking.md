---
docType: review
layer: project
reviewType: code
slice: usage-and-cost-tracking
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/175-slice.usage-and-cost-tracking.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 1cbd6be4317f37498b07a31cd9cb64562fdb9d0a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: false
durationSeconds: 36.8
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Provider failure in a review part now returns instead of raising, and logs a misleading \"unexpected error\""
    location: "src/squadron/pipeline/actions/review.py:486-493"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`sq stats reviews --json` prints plain text when the review directory is missing"
    location: "src/squadron/cli/commands/stats.py:60-63"
  - id: F003
    severity: concern
    category: design
    summary: "Pricing-warning dedupe is not shared in standalone reviews, and the UsageCapture dedupe set is bypassed for pipeline reviews"
    location: "src/squadron/review/review_client.py:313-321"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Broad exception tuple including `AttributeError` used to detect a malformed state file"
    location: "src/squadron/stats/usage_report.py:101-104"
  - id: F005
    severity: note
    category: design
    summary: "`usage_capture` is an optional parameter threaded through about ten executor functions"
    location: "src/squadron/pipeline/executor.py"
  - id: F006
    severity: note
    category: design
    summary: "Duplicated and loosely coupled usage-metadata plumbing in summary"
    location: "src/squadron/pipeline/actions/summary.py:266-270"
  - id: F007
    severity: note
    category: style
    summary: "Magic strings and dead surface in the stats view"
    location: "src/squadron/cli/stats_views.py"
  - id: F008
    severity: pass
    category: testing
    summary: "Usage reading, record round-trip and tests"
    location: "src/squadron/providers/sdk/usage.py"
---

# Review: code — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Provider failure in a review part now returns instead of raising, and logs a misleading "unexpected error"

The `except ProviderError` branch in `_run_part` used to `raise`, so `execute`'s catch-all built the failed result and the step stopped. It now logs `"review: unexpected error in step ..."` with `logger.exception` and returns `self._exception_result(...)`. I see three problems:
- **Misleading log.** A `ProviderError` is a named failure. Dispatch and summary treat it as "one ERROR line, no traceback" (issue 200). This path now prints a traceback labelled "unexpected" for it.
- **Possible loop continuation.** `_run_part` is called at line 293 as `results.append(await self._run_part(...))`. The returned failure `ActionResult` is now appended like a successful part, so a split review may carry on to later parts or aggregate a failed part as if it were a normal one. I did not read the loop, so confirm that it still stops on a failed part. A test with a multi-part review where one part fails would settle it.
- **Masked original error.** `effort_sent_by_profile(...)` calls `get_profile` and `ensure_provider_loaded` inside the except block. If either raises, it replaces the original `ProviderError`.

Keep the `raise` and attach the usage record to the exception, or log with `_logger.error` and add a test that a failing part stops the step.

### [CONCERN] `sq stats reviews --json` prints plain text when the review directory is missing

When `report.missing_dir` is true, the command echoes `No review directory at ...` and exits 0, before the `--json` check. A script running `sq stats reviews --json` gets non-JSON on stdout. Emit the JSON report (empty rows) for `--json`, or exit non-zero. The `missing_dir` flag is already in the report, so `reviews_report_json` could include it.

### [CONCERN] Pricing-warning dedupe is not shared in standalone reviews, and the UsageCapture dedupe set is bypassed for pipeline reviews

`run_review_with_profile` calls `resolve_cost(alias, ..., set())` with a fresh set on each call. In a pipeline run, `UsageCapture` owns the per-run `warned` set, but review cost is resolved in `review_client` and `record_from_review` only reuses the result. A split or looped review therefore logs the same "Cannot price alias" WARNING once per call, and the "once per alias per run" contract in `price_usage` does not hold for reviews. The `warned` set could be passed in as a parameter, or the dedupe could live at the `aliases` module level. The duplicated `resolve_cost` calls on the success and failure paths could also share one helper.

### [CONCERN] Broad exception tuple including `AttributeError` used to detect a malformed state file

`run_usage_report` catches `(OSError, ValueError, AttributeError, SchemaVersionError)` from `state_manager.load`. `AttributeError` is only there to cover a top-level JSON value that is not an object. That catches real programming errors inside `load` and presents them to the user as "cannot read file". Validate the shape (or fix `StateManager.load` to raise `ValueError`) instead of catching `AttributeError`.

### [NOTE] `usage_capture` is an optional parameter threaded through about ten executor functions

`usage_capture: UsageCapture | None = None` is added to every `_execute_*` helper and to `ActionContext`, and LLM actions then fail with `UsageCaptureMissingError` when it is `None`. This is explicit, as the project's fail-fast rule asks, but the optional defaults let a new call site forget it until runtime. Consider making it required where the executor always supplies it.

### [NOTE] Duplicated and loosely coupled usage-metadata plumbing in summary

`usage_metadata` (the input to the one-shot runner) and `usage_metadata_out` (the stamped record) are two similarly named dicts. `"answering_models"` in `USAGE_METADATA_KEYS` is a bare string while its siblings are constants in `providers/base.py`. `_execute_summary` also grows further past the ~50-line guideline. Rename the dicts and promote the key to a constant.

### [NOTE] Magic strings and dead surface in the stats view

`"default"` in `_model_cell` and `"api-rate equiv."` in `cost_cell` are inline literals, while the other display strings are module constants. `count_cell` and `cost_cell` are public but only used in this module. Several lines in the new files (for example `stats_views.py` `render_run_report` and `usage_report.py` `unrecorded`) look over the 88-character limit stated in the Python rules. Run `ruff format` and `ruff check` as the squadron fix rules require.

### [PASS] Usage reading, record round-trip and tests

The SDK reader treats `bool` as not an int and treats malformed values as `None` with a WARNING. `UsageRecord.from_dict` raises `ValueError` naming the bad key. `None` ("not reported") is kept apart from zero throughout, and the stats views render it as `—`. The new tests use a captured real `ResultMessage` fixture, cover the round-trip, pre-slice run files and the observable partial and cancellation signals, and the one executor test for per-step capture sharing works against the real executor. The removal of `estimate_cost` leaves no callers in `src`.

### Run Digest

- Response length: 5775 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 36.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

- **F001 fixed.** A part's `ProviderError` is re-raised as an internal `_PartProviderFailure` carrying the usage record; `execute` logs one ERROR line (no traceback) and returns the failed result with usage stamped. A failed part now stops the step. New test: provider failure on part 1 of 2 stops before part 2 and logs no "unexpected error". The effort lookup stays in the except block: `run_review_with_profile` already resolved the same profile, so it cannot mask the error.
- **F002 fixed.** `sq stats reviews --json` emits JSON for a missing directory, with a new `missing_dir` key. Test added.
- **F003 fixed.** `run_review_with_profile` takes `pricing_warned`; the pipeline review passes the run's `UsageCapture.warned` set, standalone calls get their own scope. Success and failure paths share the one set. Test added.
- **F004 fixed.** `StateManager._load_raw` raises `ValueError` for a non-object top level; `run_usage_report` no longer catches `AttributeError`. The existing `not-an-object` test covers it.
- **F005 declined.** The executor always supplies `usage_capture`, and a missing one fails fast with `UsageCaptureMissingError`. Making it required would change every non-LLM action's test context for no runtime gain.
- **F006 partly fixed.** `answering_models` is now `ANSWERING_MODELS_KEY` in `providers/base.py`, used everywhere it was a bare string. The two dict names stay; they are the runner's input and the stamped output, and the names say so.
- **F007 fixed.** `api-rate equiv.` and `default` are module constants. `ruff format`/`ruff check` are clean (the project line length is 100, not 88).
