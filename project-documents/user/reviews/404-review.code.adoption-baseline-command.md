---
docType: review
layer: project
reviewType: code
slice: adoption-baseline-command
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/404-slice.adoption-baseline-command.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261030
dateUpdated: 20261030
reviewedSha: 50270bcc209d10716b01901df9b7c86c2d90f613
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 157845
cachedTokens: 17597
cacheWriteTokens: 140244
completionTokens: 3185
durationSeconds: 26.9
costUsd: 0.598123
costBasis: provider
squadronVersion: 0.24.9
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "Baseline success path hides why a series ended early"
    location: "src/squadron/cli/commands/metrology_baseline.py#_report_result"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "Duplicated \"no floor\" reporting in two commands"
    location: "src/squadron/cli/commands/metrology.py#_print_no_floor"
  - id: F003
    severity: note
    category: consistency-rot
    summary: "`audit variance` rate-limit message now prints without the earlier break guard"
    location: "src/squadron/cli/commands/metrology.py:880-895"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "Observer protocol has an unused hook and an inheritance-based extension"
    location: "src/squadron/cli/commands/metrology_audit_output.py#SeriesPrinter"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Long lines and mutable session object"
    location: "src/squadron/cli/commands/metrology_baseline.py:55"
  - id: F006
    severity: pass
    category: other
    summary: "Series extraction and exception handling"
    location: "src/squadron/metrology/audit_series.py"
---

# Review: code — slice 404

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Baseline success path hides why a series ended early

`_report_result` prints `result.stop_error` and `result.rate_limited` only inside `_print_no_floor`, which runs only when no floor was produced. Suppose runs 1 and 2 succeed and run 3 hits a HEAD-moved `AuditPreflightError` or a rate limit. A floor is still written, and the command exits 0 with "2 succeeded, 1 failed". The cause is dropped, and the user is never told the series was cut short. The old `audit variance` path printed both messages in this case, and the refactored `audit_variance` in `metrology.py` still does. The two commands now disagree. Print `stop_error` and the rate-limit notice regardless of whether a floor exists, and add a test for a floor written alongside a stop error.

### [CONCERN] Duplicated "no floor" reporting in two commands

`metrology.py` and `metrology_baseline.py` each define `_print_no_floor(…, result: AuditSeriesResult)`. Both branch on `NoFloorReason` and print similar text. The wording and the points at which they emit `stop_error` and `rate_limited` differ, which is how the drift above arose. The other shared output helpers were moved into `metrology_audit_output.py`. This one should follow them. Give it a parameter for the caller-specific prefix and recovery hint.

### [NOTE] `audit variance` rate-limit message now prints without the earlier break guard

The rate-limit and stop-error messages now print after the whole series returns, not at the moment they occur. Ordering relative to the per-run output is preserved, so this is acceptable. The `audit variance` behaviour should be confirmed by an existing CLI test, and none appears in this diff.

### [NOTE] Observer protocol has an unused hook and an inheritance-based extension

`SeriesPrinter.on_run_start` is a no-op, and `progress_callback` is typed `| None` but never returns `None`. `_CountingPrinter` subclasses `SeriesPrinter` only to add a counter. Composition would be cleaner, for example counting from `result.runs` after the series. `_report_interrupt` and `_report_store_error` need the count mid-series, so the subclass is defensible. Neither point blocks the change.

### [NOTE] Long lines and mutable session object

`PREFLIGHT_FAILURES` runs past 100 characters, and a few test lines are similarly long. If `ruff format` or `ruff check` passes, ignore this. `_Session` is a mutable dataclass whose `snapshot` field is written by `_take_snapshot`. It works, but it is hidden state shared across helpers.

### [PASS] Series extraction and exception handling

The series loop is now a pure, non-printing function with an injectable `audit` callable and observer. Its exception handling follows the rules. Preflight, skill and identity errors become a typed `stop_error`. `AuditVarianceError` becomes a typed `NoFloorReason`. `MetrologyStoreError` and `KeyboardInterrupt` propagate to the one documented process-boundary handler in `_execute`, which logs with `logger.exception`. The new tests cover pinning, mid-series failure, rate limit, too few runs, moved HEAD and cooldown. The CLI tests use throwaway stores and never read a production URL.

### Run Digest

- Response length: 3719 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 157845 / 17597 / 140244 / 3185 / not computed
- Duration: 26.9 s
- Cost: $0.60 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response (20261030)

- **F001 (fixed).** Confirmed: with a floor written, `baseline` dropped `stop_error` and the rate-limit notice. `_report_result` now prints both before it branches on the floor. Two tests added to `tests/metrology/test_baseline_cli.py`: a floor beside a moved-HEAD error, and a floor beside a rate limit. Both exit 0 and show the cause.
- **F002 (fixed in part).** The drifted part, the `stop_error` and rate-limit lines, is now one helper, `print_series_stop`, in `metrology_audit_output.py`, called by both commands with each command's own rate-limit wording. The no-floor lines stay separate on purpose: `audit variance` addresses several projects and says its runs "can be reduced later", while `baseline` has one project and the recovery is a fresh series (D6). A shared function would need a flag for every sentence.
- **F003 (no change).** `tests/metrology/test_audit_cli.py` already covers the rate-limit path of `audit variance` and passes unedited.
- **F004 (no change).** `progress_callback` returns `| None` because the protocol allows an observer with no live line; `on_run_start` is the hook `baseline` may use later. `_CountingPrinter` needs the count mid-series for the interrupt and store-error reports, as the review notes.
- **F005 (no change).** `ruff format` and `ruff check` pass. `_Session.snapshot` is set once in `_take_snapshot` and read by the failure reports.
- Validation: ruff clean, pyright 0 errors, 33 tests in the three 404 test files, plus the `audit variance` and rate-limit CLI tests. The review's verdict line still reads CONCERNS; a re-run would clear it.
