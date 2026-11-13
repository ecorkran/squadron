# Precision review, grid 2

Cases graded: 175, 188, 197, 225, 227, 307, 921, 932, a122, u103. Findings are CONCERN and FAIL only.
Grades are a first pass by one agent per case. Mark each issue below; disagreements change the table.

| Config | Findings | REAL | MINOR | FALSE | PREEXISTING | UNSURE | Precision (REAL/all) | False rate | REAL per run | FAIL justified |
|---|---|---|---|---|---|---|---|---|---|---|
| haiku-xhigh | 235 | 57 | 166 | 2 | 5 | 5 | 24% | 1% | 1.9 | 13 of 23 |
| sol | 91 | 72 | 18 | 0 | 1 | 0 | 79% | 0% | 2.4 | 30 of 50 |
| sonnet-high | 128 | 24 | 103 | 1 | 0 | 0 | 19% | 1% | 0.8 | 2 of 3 |
| sonnet | 106 | 13 | 87 | 4 | 2 | 0 | 12% | 4% | 0.4 | 0 of 0 |

## 175

### 175-I1 · REAL (high)
**Folding a split review keeps only part 1's usage record, so parts 2..N spend is lost.**

Found by: haiku-xhigh ×1, sol ×3, sonnet-high ×1 · CONCERN ×1, FAIL ×4

Each part now stamps its own USAGE_KEY record in _run_part, but review_fold._metadata copies parts[0].metadata and only sums TOOL_CALLS_MADE_KEY. The folded step result persisted to run state therefore carries part 1's tokens/turns/cost only, and pipeline review artifacts are excluded from sq stats reviews, so the rest of the spend appears nowhere. This undercounts exactly what slice 175 exists to measure.

Evidence: `src/squadron/pipeline/actions/review_fold.py:85-91`, `src/squadron/pipeline/actions/review.py:505-506`, `src/squadron/stats/reviews_report.py:75-78`

- [ ] agree   - [ ] disagree →

### 175-I19 · REAL (high)
**sq stats run omits earlier loop rounds because only the final round's action_results are persisted.**

Found by: sol ×3 · FAIL ×3

Loop steps keep earlier rounds in StepResult.prior_rounds, but StateManager._append_step serializes only step_result.action_results and RunStateRecorder.round_completed records nothing. The new run_usage_report reads only persisted action_results, so a multi-round loop reports only its last round, contradicting the slice's stated 'the cost of a loop is the whole loop' and 'run totals include failed attempts'.

Evidence: `src/squadron/stats/usage_report.py:112-116`, `src/squadron/pipeline/state.py:507-508`, `src/squadron/pipeline/executor.py:223-226`, `src/squadron/pipeline/run_observer.py:52-53`, `project-documents/user/slices/175-slice.usage-and-cost-tracking.md:157`

- [ ] agree   - [ ] disagree →

### 175-I2 · REAL (high)
**A provider failure in one part of a split review no longer stops the loop and makes the fold raise TypeError, hiding the provider error.**

Found by: haiku-xhigh ×2, sol ×3, sonnet-high ×1 · CONCERN ×1, FAIL ×5

The ProviderError branch of _run_part used to re-raise; it now returns _exception_result with outputs={} and verdict None. _review's loop has no early exit, so later parts still make paid model calls, then fold_review_parts calls _part_input which raises TypeError('review part must name exactly one input file, got []'). execute's catch-all reports that TypeError as the step error, dropping the provider message and the per-part usage records.

Evidence: `src/squadron/pipeline/actions/review.py:283-294`, `src/squadron/pipeline/actions/review.py:486-493`, `src/squadron/pipeline/actions/review_fold.py:38`, `src/squadron/pipeline/actions/review_fold.py:102-106`, `src/squadron/pipeline/actions/review.py:180-182`

- [ ] agree   - [ ] disagree →

### 175-I20 · REAL (medium)
**Fan-out branch usage records are discarded by the fan-in reducers and on branch failure.**

Found by: sol ×1 · FAIL ×1

The diff passes usage_capture into fan-out branches, but CollectReducer and FirstPassReducer build a new ActionResult without metadata, and the failed-branch path returns action_results=[]. The persisted action has type 'fan_out', which is not in LLM_ACTION_TYPES, so the lost spend is not even counted as unrecorded.

Evidence: `src/squadron/pipeline/executor.py:2072-2093`, `src/squadron/pipeline/intelligence/fan_in/reducers.py:62-83`, `src/squadron/stats/usage_report.py:26-28`

- [ ] agree   - [ ] disagree →

### 175-I4 · REAL (medium)
**A failed SDK compact drops the spend carried on the ProviderError or captured before a reconnect failure.**

Found by: haiku-xhigh ×3, sol ×2, sonnet ×1 · CONCERN ×6

SDKExecutionSession.dispatch now attaches telemetry to a ProviderError, and compact() captures the summary reply before _reconnect; but CompactAction's except branch returns a failed ActionResult with no metadata, and a reconnect failure discards reply.telemetry. Dispatch, summary and review all stamp failed-call usage per D5, and success criterion 2 names failed compact actions. The row shows as unrecorded rather than silently, but the spend is lost.

Evidence: `src/squadron/pipeline/actions/compact.py:82-89`, `src/squadron/pipeline/sdk_session.py:234`, `src/squadron/pipeline/sdk_session.py:493-499`

- [ ] agree   - [ ] disagree →

### 175-I5 · REAL (medium)
**Compact usage records are built with resolved=None, so alias is None and subscription costs are labeled as provider money.**

Found by: haiku-xhigh ×2, sonnet-high ×1 · CONCERN ×3

compact.py calls record_from_telemetry(None, ...), so _build sets alias=None. cost_cell only labels a provider cost 'api-rate equiv.' when _is_subscription(record.alias) is true, and returns False for None, so every SDK compact row on a subscription alias renders '$X prov', contradicting D3, while dispatch and summary rows for the same alias are labeled correctly. The comment claiming no resolution is needed is wrong for labeling.

Evidence: `src/squadron/pipeline/actions/compact.py:91-99`, `src/squadron/pipeline/usage_capture.py:200`, `src/squadron/cli/stats_views.py:165-179`

- [ ] agree   - [ ] disagree →

### 175-I24 · FALSE (high)
**Moving the dispatch except ProviderError clause above other handlers could misroute subclasses.**

Found by: sonnet ×1 · CONCERN ×1

None of the later-handled types subclass ProviderError: ModelResolutionError and ModelPoolNotImplemented subclass Exception, ContextForgeError subclasses Exception, ProjectRulesError subclasses RuntimeError, and KeyError is builtin. The reordering changes no matching.

Evidence: `src/squadron/pipeline/actions/dispatch.py:404-406`, `src/squadron/pipeline/resolver.py:93-97`, `src/squadron/project_rules/errors.py:6`, `src/squadron/integrations/context_forge.py:33`

- [ ] agree   - [ ] disagree →

### 175-I10 · MINOR (high)
**dispatch.py, _execute_summary and _dispatch_via_session exceed the length guidelines.**

Found by: haiku-xhigh ×3 · CONCERN ×3

File and function length are style guideline points; the lengths largely predate the diff and cause no defect.

Evidence: `src/squadron/pipeline/actions/dispatch.py:1`, `src/squadron/pipeline/actions/summary.py:187`

- [ ] agree   - [ ] disagree →

### 175-I11 · MINOR (medium)
**SDK prompt token total is a partial sum when a cache field is malformed.**

Found by: haiku-xhigh ×1 · CONCERN ×1

read_result_usage adds only the cache classes that parse, so a malformed cache value gives prompt equal to the uncached count; the code matches its docstring and logs a WARNING. Real SDK results carry both keys as ints, so this is hardening against input that does not arrive.

Evidence: `src/squadron/providers/sdk/usage.py:43-48`

- [ ] agree   - [ ] disagree →

### 175-I12 · MINOR (medium)
**get_all_aliases re-parses models.toml on each call and the diff adds calls on async paths.**

Found by: haiku-xhigh ×1 · CONCERN ×1

resolver._resolved now calls get_all_aliases per resolve, adding to several existing calls. An unmeasured performance point with no shown effect.

Evidence: `src/squadron/pipeline/resolver.py:89`

- [ ] agree   - [ ] disagree →

### 175-I13 · MINOR (high)
**review_client prices with a fresh warned set, bypassing the per-run pricing-warning dedup.**

Found by: haiku-xhigh ×1, sonnet ×2, sonnet-high ×3 · CONCERN ×6

resolve_cost(..., set()) at review_client lines 315 and 321 means a partially priced alias warns once per review instead of once per run. True, but the only effect is repeated WARNING lines; costs are correct.

Evidence: `src/squadron/review/review_client.py:315`, `src/squadron/review/review_client.py:321`, `src/squadron/pipeline/executor.py:549-550`

- [ ] agree   - [ ] disagree →

### 175-I14 · MINOR (high)
**record_from_error re-resolves a failed review's cost instead of reusing exc.cost_usd/cost_basis.**

Found by: haiku-xhigh ×1, sonnet ×1, sonnet-high ×1 · CONCERN ×3

review_client resolves cost onto the exception, then UsageCapture.record_from_error calls _build which resolves again from the same telemetry and the same alias (settings.resolved.alias is passed to both), so the values agree. The effect is duplicated pricing logic and a possible second warning, not wrong data.

Evidence: `src/squadron/review/review_client.py:315`, `src/squadron/pipeline/usage_capture.py:154-174`, `src/squadron/pipeline/actions/review.py:446`

- [ ] agree   - [ ] disagree →

### 175-I15 · MINOR (high)
**The subscription cost-tier literal is defined again in stats_views rather than once.**

Found by: haiku-xhigh ×1, sonnet-high ×1 · CONCERN ×2

SUBSCRIPTION_TIER='subscription' duplicates a value used in other modules. Style/DRY rule point; behavior is correct.

Evidence: `src/squadron/cli/stats_views.py:29`

- [ ] agree   - [ ] disagree →

### 175-I16 · MINOR (medium)
**An unreadable or non-UTF-8 review artifact aborts sq stats reviews instead of being skipped.**

Found by: haiku-xhigh ×1 · CONCERN ×1

read_frontmatter calls path.read_text without catching OSError/UnicodeDecodeError, and reviews_usage_report does not catch them. True, but artifacts are written by squadron as UTF-8, so this is hardening against input that does not normally arrive.

Evidence: `src/squadron/documents/frontmatter.py:66`, `src/squadron/stats/reviews_report.py:67-72`

- [ ] agree   - [ ] disagree →

### 175-I17 · MINOR (high)
**A list or mapping costBasis value raises TypeError (unhashable) in the reviews report.**

Found by: haiku-xhigh ×1, sol ×1 · CONCERN ×2

_basis tests value in a set, which raises TypeError for an unhashable YAML value. True, but squadron writes costBasis as a scalar string, so only a hand-corrupted artifact triggers it.

Evidence: `src/squadron/stats/reviews_report.py:151-158`

- [ ] agree   - [ ] disagree →

### 175-I18 · MINOR (high)
**effort_for_session is annotated -> None yet its result is used as the effort value.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The function always returns None and callers bind it to effort_sent, which is the intended D7 value today. Naming/clarity point with no wrong behavior.

Evidence: `src/squadron/pipeline/usage_capture.py:176-183`, `src/squadron/pipeline/actions/dispatch.py:572`, `src/squadron/pipeline/actions/summary.py:274`

- [ ] agree   - [ ] disagree →

### 175-I21 · MINOR (high)
**The review ProviderError branch logs a misleading 'unexpected error' with a traceback after its WARNING.**

Found by: sonnet ×3, sonnet-high ×3 · CONCERN ×6

The new branch calls _logger.exception('review: unexpected error ...'). Before the diff the re-raise reached execute's catch-all, which logged the same message with a traceback, so log output is unchanged; the wording is merely inaccurate and inconsistent with dispatch.

Evidence: `src/squadron/pipeline/actions/review.py:486`, `src/squadron/pipeline/actions/review.py:180-182`

- [ ] agree   - [ ] disagree →

### 175-I22 · MINOR (medium)
**effort_sent_by_profile inside the except block could raise and mask the original ProviderError.**

Found by: sonnet ×1 · CONCERN ×1

effort_sent_by_profile calls get_profile, ensure_provider_loaded and get_provider for the same profile run_review_with_profile has already looked up and loaded, so those calls cannot realistically fail at that point. Speculative hardening.

Evidence: `src/squadron/pipeline/usage_capture.py:56-63`, `src/squadron/pipeline/actions/review.py:487-492`

- [ ] agree   - [ ] disagree →

### 175-I23 · MINOR (medium)
**sq stats reviews --json prints plain text when the review directory is missing.**

Found by: sonnet ×2, sonnet-high ×2 · CONCERN ×4

The missing_dir check runs before the as_json branch, so --json outputs 'No review directory at ...' with exit 0. True, but the only shipped consumers (the sq-stats skill and slash command) display output rather than parse it, and the case is a project with no reviews directory.

Evidence: `src/squadron/cli/commands/stats.py:60-65`

- [ ] agree   - [ ] disagree →

### 175-I25 · MINOR (high)
**run_usage_report catches AttributeError and re-declares STATE_READ_ERRORS.**

Found by: sonnet-high ×1 · CONCERN ×1

The except tuple is broader than STATE_READ_ERRORS and includes AttributeError, which could relabel a bug as an unreadable file. A maintainability point; no wrong behavior shown.

Evidence: `src/squadron/stats/usage_report.py:107-110`, `src/squadron/pipeline/state.py:103-109`

- [ ] agree   - [ ] disagree →

### 175-I3 · MINOR (high)
**The existing two-part provider-failure test passes on the TypeError because it never checks result.error or call count.**

Found by: haiku-xhigh ×1 · CONCERN ×1

test_provider_failure_on_part_two_keeps_part_one asserts only success is False, artifacts and a log line, so it is green despite the bug in 175-I2. The claim is true, but it is a test-strength point; the defect itself is graded in I2.

Evidence: `tests/pipeline/actions/test_review_action_parts.py:143-153`

- [ ] agree   - [ ] disagree →

### 175-I6 · MINOR (high)
**Findings-addressed judge spend (and prompt-only compact spend) is not recorded and gates are excluded from LLM action counting.**

Found by: haiku-xhigh ×2, sonnet-high ×1 · CONCERN ×3

True that judge_residue_core's review spend is never stamped and GATE is not in LLM_ACTION_TYPES, but the judge code was not changed in this diff and the slice design explicitly lists the addressed-findings judge as out of scope; compact capture is scoped to the SDK session path. This is a documented scope gap, not a defect in the changed code.

Evidence: `project-documents/user/slices/175-slice.usage-and-cost-tracking.md:55`, `project-documents/user/slices/175-slice.usage-and-cost-tracking.md:36`, `src/squadron/stats/usage_report.py:24-28`

- [ ] agree   - [ ] disagree →

### 175-I7 · MINOR (high)
**Review frontmatter cost key names are spelled separately in the writer and the stats reader.**

Found by: haiku-xhigh ×1 · CONCERN ×1

run_cost.py writes the key literals and reviews_report.py repeats them in _INT_KEYS and its _int/_float/_basis calls. It is a DRY point; the keys currently agree, so nothing is wrong at head.

Evidence: `src/squadron/stats/reviews_report.py:26-31`, `src/squadron/stats/reviews_report.py:108-123`

- [ ] agree   - [ ] disagree →

### 175-I8 · MINOR (medium)
**The reviews reader tests use hand-written frontmatter instead of the real writer.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The fixtures are hand-written. This is a test-coverage concern for an already-working reader, not a defect.

Evidence: `tests/stats/test_reviews_report.py:15`

- [ ] agree   - [ ] disagree →

### 175-I9 · MINOR (high)
**Usage-fold and one-shot plumbing logic is duplicated between the SDK agent and the session turns.**

Found by: haiku-xhigh ×2 · CONCERN ×2

ClaudeSDKAgent._fold_result and DispatchTurns.fold_result do the same read-warn-fold steps. Duplication is a maintainability point with no wrong behavior at head.

Evidence: `src/squadron/providers/sdk/agent.py:248-254`, `src/squadron/pipeline/sdk_turns.py:141-147`

- [ ] agree   - [ ] disagree →

## 188

### 188-I1 · REAL (high)
**Midnight timestamps in start/end parse as bare dates and expand to whole-day bounds.**

Found by: sol ×3, sonnet-high ×2 · CONCERN ×2, FAIL ×3

Both routes declare `start`/`end` as `date | datetime | None`. Under the locked pydantic 2.12.5 / fastapi 0.136.1, I reproduced that `end=2026-06-01T00:00:00Z` and `end=2026-06-01T00:00:00+05:00` both validate as `date(2026, 6, 1)`, while `...T00:00:01Z` stays a datetime. `resolve_window` then turns that date into `23:59:59.999999` UTC, so an explicit midnight end returns an extra day of rows, and an offset midnight loses its offset. This is new code in base..head and returns wrong data silently.

Evidence: `src/manta_trading/api_server/routes/kalshi_timeseries.py:91-92`, `src/manta_trading/api_server/routes/kalshi_timeseries.py:139-140`, `src/manta_trading/api_server/routes/windows.py:46-48`

- [ ] agree   - [ ] disagree →

### 188-I2 · REAL (medium)
**Building and serializing a ceiling-sized response runs synchronously on the event loop.**

Found by: haiku-xhigh ×3, sol ×3, sonnet ×1, sonnet-high ×1 · CONCERN ×2, FAIL ×6

Only the DB reads go through `run_in_executor`. `CandlesResponse.build`/`TradesResponse.build` (up to 75,000 pydantic records) and `timeseries_response` run inline in the `async def`. Reviewers measured about 1.2 s for this, and the load test records a 34.8 MB candle body. The repo's python rule (.claude/rules/python.md:91) explicitly requires CPU-bound work to go to an executor. The bars route has the same pre-existing shape and the architecture frames the API as single-user, so it is not a merge blocker, but the new routes do stall every other request.

Evidence: `src/manta_trading/api_server/routes/kalshi_timeseries.py:123-126`, `src/manta_trading/api_server/routes/kalshi_timeseries.py:166-174`, `.claude/rules/python.md:91`, `test/load/test_188_kalshi_api_nfr.py:120`

- [ ] agree   - [ ] disagree →

### 188-I10 · MINOR (high)
**The ceiling comparison is written twice per handler, once in _read and once in _admit_rows.**

Found by: sonnet ×1 · CONCERN ×1

Each handler checks `count > max_rows` inside the executor closure to skip the fetch, then calls `_admit_rows` with the same comparison to raise after the connection is released. This split is deliberate (the module docstring explains it), and the two checks agree today. It is a duplication point only.

Evidence: `src/manta_trading/api_server/routes/kalshi_timeseries.py:115-117`, `src/manta_trading/api_server/routes/kalshi_timeseries.py:124`, `src/manta_trading/api_server/routes/kalshi_timeseries.py:161-167`

- [ ] agree   - [ ] disagree →

### 188-I11 · MINOR (high)
**_admit_rows and _not_found are near-duplicates of the helpers in kalshi_catalog.py.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The new `_admit_rows`/`_not_found` duplicate the catalog route's versions except for the remedy text. Behavior is correct. This is DRY cleanup, and it was later extracted to admission.py in daf30bec.

Evidence: `src/manta_trading/api_server/routes/kalshi_timeseries.py:59-79`, `src/manta_trading/api_server/routes/kalshi_catalog.py:81-97`

- [ ] agree   - [ ] disagree →

### 188-I12 · MINOR (high)
**The reversed-range 422 check and message are copied into windows.py rather than shared with bars.py.**

Found by: haiku-xhigh ×1 · CONCERN ×1

`resolve_window` re-spells the reversed-range check and message that `bars.py` already has for its date-typed bounds. Both behave correctly. The finding also mentions gaps.py's own window helpers, which are pre-existing (see 188-I13). The new part is a minor duplication.

Evidence: `src/manta_trading/api_server/routes/windows.py:65-72`, `src/manta_trading/api_server/routes/bars.py:93-100`

- [ ] agree   - [ ] disagree →

### 188-I14 · MINOR (high)
**The candle-ceiling load test asserts no latency or size bound and CANDLES_CEILING_RESPONSE_MB is never referenced.**

Found by: haiku-xhigh ×2 · CONCERN ×2

The candle test asserts only the row count, and the constant's docstring says it is 'recorded here rather than asserted' on purpose. The markets-list test checks correctness, not latency, and the module docstring's 'Four assertions' undercounts the six tests. These are test-quality points.

Evidence: `test/load/test_188_kalshi_api_nfr.py:120-129`, `test/load/test_188_kalshi_api_nfr.py:241-266`, `test/load/test_188_kalshi_api_nfr.py:348-361`

- [ ] agree   - [ ] disagree →

### 188-I15 · MINOR (high)
**The new load tier is not gated by CI.**

Found by: haiku-xhigh ×1, sol ×1 · CONCERN ×2

The tier is skipped unless MT_RUN_LOAD_TESTS=1, and the module docstring states that CI wiring belongs to slice 907. This is a documented, tracked process gap, not a code defect.

Evidence: `test/load/test_188_kalshi_api_nfr.py:37-46`, `test/load/test_188_kalshi_api_nfr.py:80-87`

- [ ] agree   - [ ] disagree →

### 188-I16 · MINOR (high)
**The load test installs its recording cursor through the private pool._pool attribute and uses class-level mutable state.**

Found by: sonnet ×2, sonnet-high ×1 · CONCERN ×3

`_client` waits for the pool, sets the factory on a probe connection, and then walks `pool._pool` (noqa SLF001). `_RecordingCursor.statements` is class-level, and the test resets it before use. The no-fetch assertion is paired with `assert counts`, which limits vacuous passes. This is test brittleness, not a product defect.

Evidence: `test/load/test_188_kalshi_api_nfr.py:132-169`, `test/load/test_188_kalshi_api_nfr.py:282-295`

- [ ] agree   - [ ] disagree →

### 188-I17 · MINOR (high)
**The concurrency load assertion uses the median, which cannot see the queued half of the requests.**

Found by: haiku-xhigh ×1 · CONCERN ×1

With 16 requests against a pool of 8, the median of 16 samples sits at the boundary between connected and queued requests, so a regression in queue wait could pass. This is true but concerns test sensitivity only.

Evidence: `test/load/test_188_kalshi_api_nfr.py:338-345`

- [ ] agree   - [ ] disagree →

### 188-I18 · MINOR (high)
**Docstrings say 'fourteen' candle value columns where CANDLE_COLUMNS has sixteen.**

Found by: haiku-xhigh ×1 · CONCERN ×1

`CandleRow` and the models module docstring say fourteen. The mapping has 14 nested columns plus `volume_fp` and `open_interest_fp`, and the code zips with strict=True, so it is correct. Only the prose is off.

Evidence: `src/manta_trading/data/kalshi/serve_timeseries.py:72`, `src/manta_trading/api_server/models/kalshi_timeseries.py:5`

- [ ] agree   - [ ] disagree →

### 188-I19 · MINOR (high)
**New test helpers and modules exceed the size guidance.**

Found by: haiku-xhigh ×1 · CONCERN ×1

`_seed_kalshi_dense` and the enlarged test modules are long, but this is a style guideline about size with no behavioral effect.

Evidence: `test/load/conftest.py:446`

- [ ] agree   - [ ] disagree →

### 188-I3 · MINOR (high)
**TradeRecord.from_row maps trade values by position instead of by TRADE_VALUE_COLUMNS.**

Found by: haiku-xhigh ×3, sonnet ×3, sonnet-high ×3 · CONCERN ×9

`from_row` reads `values[0..7]`. At head that order exactly matches `TRADE_VALUE_COLUMNS` (TRADE_COLUMNS minus market_ticker), so every field is assigned correctly today. The risk applies only if a future edit reorders TRADE_COLUMNS. That is maintainability hardening, not a current defect. It was later changed in daf30bec, and the regression test there needs a monkeypatched reorder to fail.

Evidence: `src/manta_trading/api_server/models/kalshi_timeseries.py:163-175`, `src/manta_trading/data/kalshi/serve_timeseries.py:41-43`, `src/manta_trading/data/kalshi/trade_repository.py:45-55`

- [ ] agree   - [ ] disagree →

### 188-I4 · MINOR (high)
**tape_filtered re-implements the trades-filter membership test and hard-codes its parameter key, contrary to its docstring.**

Found by: haiku-xhigh ×3, sonnet ×1, sonnet-high ×2 · CONCERN ×6

`tape_filtered` reads `selection.params["trades_excluded_categories"]` and evaluates `(category or "") in bound`, which is a Python restatement of `COALESCE(s.category,'') = ANY(...)`. The docstring's claim that it is 'not re-spelled' is therefore inaccurate. The two forms agree today, and an integration test checks parity, so this is duplication and a misleading comment, not wrong behavior.

Evidence: `src/manta_trading/data/kalshi/serve_timeseries.py:147-166`, `src/manta_trading/data/kalshi/selection.py:152-172`

- [ ] agree   - [ ] disagree →

### 188-I5 · MINOR (high)
**Candle module docstring wrongly claims a new CANDLE_COLUMNS entry is served without an edit; models are hand-listed and _CANDLE_OBJECTS values are unused.**

Found by: haiku-xhigh ×2, sonnet-high ×2 · CONCERN ×4

`CandleBidAsk`/`CandlePrice` list their fields by hand, `from_row` hard-codes the object names and `volume_fp`/`open_interest_fp`, and only the keys of `_CANDLE_OBJECTS` are used. A new column would be dropped by pydantic's default `extra='ignore'` or would raise KeyError. Current output is correct, and a unit test catches mapping drift, so the defect is an overstated docstring plus a hypothetical future change.

Evidence: `src/manta_trading/api_server/models/kalshi_timeseries.py:5-9`, `src/manta_trading/api_server/models/kalshi_timeseries.py:58-62`, `src/manta_trading/api_server/models/kalshi_timeseries.py:82-99`

- [ ] agree   - [ ] disagree →

### 188-I6 · MINOR (high)
**tape_complete_through is described as the newest stored trade's time but carries the trades sync watermark.**

Found by: haiku-xhigh ×2 · CONCERN ×2

`tape_facts` returns `sync_state['trades'].watermark_ts`, which `advance_watermark(window_edge)` sets and which slice 265 defines as explicitly NOT the newest stored trade. The value matches the 188 spec (slice line 302). Only the Field description and the `tape_facts` docstring are wrong. It is a published OpenAPI text error, not wrong data.

Evidence: `src/manta_trading/api_server/models/kalshi_timeseries.py:188-193`, `src/manta_trading/data/kalshi/serve_timeseries.py:123-144`, `src/manta_trading/data/kalshi/trade_repository.py:272-276`

- [ ] agree   - [ ] disagree →

### 188-I7 · MINOR (medium)
**tape_filtered description says no trades are stored for an excluded category, but previously stored trades are still served.**

Found by: haiku-xhigh ×1 · CONCERN ×1

`fetch_trades`/`count_trades` filter only on ticker and window, so any trades already stored for a category excluded later would still be returned while `tape_filtered` is true. This concerns the wording of a field description. Whether such rows actually exist depends on whether exclusion ever purges history, which I did not trace.

Evidence: `src/manta_trading/api_server/models/kalshi_timeseries.py:194-200`, `src/manta_trading/data/kalshi/serve_timeseries.py:257-296`

- [ ] agree   - [ ] disagree →

### 188-I8 · MINOR (high)
**_window uses the truthiness of a generic extra dict as the switch for a hard-coded period predicate.**

Found by: sonnet ×3, sonnet-high ×3 · CONCERN ×6

`_window` appends `period = %(period)s` when `extra` is truthy, and does not check that the key exists. The only callers are `_candle_window`, which always passes `{'period': period}`, and `_trade_window`, which passes nothing, so behavior is correct today. The concern is about an API shape that only a future caller could misuse.

Evidence: `src/manta_trading/data/kalshi/serve_timeseries.py:177-200`, `src/manta_trading/data/kalshi/serve_timeseries.py:215-218`, `src/manta_trading/data/kalshi/serve_timeseries.py:257-258`

- [ ] agree   - [ ] disagree →

### 188-I9 · MINOR (medium)
**Count and fetch run as separate statements with separate snapshots, so the overage can exceed the 'one row' the docstring describes.**

Found by: haiku-xhigh ×1, sonnet ×1 · CONCERN ×2

The count and the fetch are separate statements on one connection with no REPEATABLE READ, so under READ COMMITTED a trades page committed in between can land in the response. The design accepts that the response may go over and is never truncated. The docstring's 'one row over' is illustrative wording, and the ceiling is a soft guard, so the effect is a slightly larger response and imprecise prose.

Evidence: `src/manta_trading/data/kalshi/serve_timeseries.py:6-11`, `src/manta_trading/api_server/routes/kalshi_timeseries.py:108-121`, `src/manta_trading/api_server/routes/kalshi_timeseries.py:155-164`

- [ ] agree   - [ ] disagree →

### 188-I13 · PREEXISTING (high)
**gaps.py still defines its own day-boundary window helpers instead of using windows.py.**

Found by: haiku-xhigh ×1, sonnet ×1 · CONCERN ×2

gaps.py is not touched in base..head; its `_window_start_utc`/`_window_end_utc` predate the slice (5b9bbcd5). Its end helper uses a different, documented half-open convention that is correct for its own predicate. Only the start helper is a true duplicate.

Evidence: `src/manta_trading/api_server/routes/gaps.py:54-71`

- [ ] agree   - [ ] disagree →

## 197

### 197-I1 · REAL (medium)
**cf errors (and other unexpected exceptions) during item resume escape as a traceback with exit 1, which the ResumeExit contract defines as FLAGGED.**

Found by: haiku-xhigh ×3 · CONCERN ×3

resume_item catches only _Stop, GitEnvironmentError and OSError, and handle_item_resume catches only typer.Exit. _select_item and _open_dependencies call cf_client.list_slices directly and evaluate_each_source runs the cf sources, so a ContextForgeError (or a cycle ValueError from order_by_dependencies) escapes asyncio.run and exits 1. D8 defines exit 1 as FLAGGED for an automated caller, so a crash is indistinguishable from 'flagged again'. Only the target read is wrapped (read_integration_target -> GitEnvironmentError), so a full cf outage is caught first, which keeps this to cf command failures mid-resume.

Evidence: `src/squadron/pipeline/item_resume.py:124-135`, `src/squadron/pipeline/item_resume.py:292`, `src/squadron/pipeline/item_resume.py:333`, `src/squadron/cli/commands/run_item.py:89-105`

- [ ] agree   - [ ] disagree →

### 197-I11 · REAL (low)
**Item resume treats a deferred in-plan dependency as open while batch selection does not, so a dependent the batch ran can never be resumed.**

Found by: haiku-xhigh ×2 · CONCERN ×2

_cf_slices_ready_to_implement builds open_in_plan excluding _EXCLUDED_STATUSES (complete and deferred), so a batch runs a slice whose dependency is deferred; _open_dependencies flags any dependency whose status is not COMPLETE, so on resume the same item is flagged 'dependency N not complete' and its body never runs. Each side follows its own design paragraph (D2 vs D8 step 2), so the paths genuinely disagree. Confidence is low because which behavior is intended for deferred dependencies is a design call, and the case is uncommon. Not B1: B1 is a merged slice still reading open in cf.

Evidence: `src/squadron/pipeline/sources.py:48`, `src/squadron/pipeline/sources.py:257`, `src/squadron/pipeline/item_resume.py:333-335`

- [ ] agree   - [ ] disagree →

### 197-I18 · REAL (high)
**Item resume on a slices-plan run rejects a review_unresolved item because its design now exists and cf.undesigned_slices no longer selects it.**

Found by: sol ×3 · FAIL ×3

_select_item re-evaluates the run's source; slices-plan uses cf.undesigned_slices, which drops any slice with a design file. A review_unresolved planning item has a design by definition, so it falls through to the 'no longer selected' REJECTED path for both retry and accept. The design's Integration Requirements say item resume must work on slices-plan runs, accept on review_unresolved included. test_item_resume_on_a_planning_batch hides it by returning no design only when the plan argument is passed.

Evidence: `src/squadron/pipeline/item_resume.py:286-305`, `src/squadron/pipeline/sources.py:134-143`, `tests/pipeline/test_item_resume_plan_batches.py:34-39`

- [ ] agree   - [ ] disagree →

### 197-I19 · REAL (medium)
**Item resume's git precondition acts on cf's integration target without checking that a linked worktree is registered.**

Found by: sol ×2 · FAIL ×2

enter_slice_branch calls _require_registered_worktree before using the target, but _git_precondition reads the target and may call restore_target (commit leftovers, checkout) with no such check. In an unregistered worktree that target belongs to the primary checkout, so resume can switch to the wrong branch, and planning pipelines (no branch step) would then commit there. This is an edge case and the leftovers commit lands on the slice branch, so it does not block a merge.

Evidence: `src/squadron/pipeline/item_resume.py:230-242`, `src/squadron/pipeline/branch_ops.py:95-96`, `src/squadron/pipeline/branch_ops.py:123-141`

- [ ] agree   - [ ] disagree →

### 197-I23 · FALSE (high)
**_write_each_report's signature exceeds the 104-column line limit.**

Found by: sonnet ×1 · CONCERN ×1

The cited line at executor.py:1454 is exactly 104 characters, within line-length = 104, and the named test files have no line over 104. ruff would not flag it.

Evidence: `src/squadron/pipeline/executor.py:1454`, `pyproject.toml:71`

- [ ] agree   - [ ] disagree →

### 197-I14 · UNSURE (low)
**Item resume finalizes the batch run's state with one item's result and appends an each StepState, which can make a later plain --resume report all steps complete.**

Found by: haiku-xhigh ×1 · CONCERN ×1

Confirmed in code: _run_pipeline skips init_run for a given run_id but still calls state_mgr.finalize(run_id, result), and the step callback appends the each step's StepState, so first_unfinished_step can return None after a halted batch while not_run items remain. Whether run state is meant to track item resumes is not specified in D8, and at head a plain resume of a halted each step reruns the whole source anyway. Settled by the PM stating the intended run-state semantics after item resume, or by an end-to-end run: halt a batch, item-resume one item, then plain --resume.

Evidence: `src/squadron/cli/commands/run.py:238`, `src/squadron/cli/commands/run.py:279`, `src/squadron/pipeline/state.py:459-471`

- [ ] agree   - [ ] disagree →

### 197-I10 · MINOR (high)
**_validate builds the report.json file name by hand instead of using BatchReport.json_path / REPORT_JSON_SUFFIX.**

Found by: haiku-xhigh ×1 · CONCERN ×1

item_resume.py:187 formats f'{run_id}.{each.name}.report.json' while batch_report.json_path builds the same name from REPORT_JSON_SUFFIX. Duplicated constant; the names agree today. Later centralized in 20ceecff.

Evidence: `src/squadron/pipeline/item_resume.py:187`, `src/squadron/pipeline/batch_report.py:299-300`

- [ ] agree   - [ ] disagree →

### 197-I12 · MINOR (high)
**_execute_each_step and executor.py keep growing, and the accept-decision short-circuit is pasted into both loop executors.**

Found by: haiku-xhigh ×1, sonnet ×1, sonnet-high ×1 · CONCERN ×3

_execute_each_step spans about 100 lines and _loop_accept_decision_result is called identically at two sites next to the existing duplicated skip check. Size and duplication points with no behavioral defect.

Evidence: `src/squadron/pipeline/executor.py:1157`, `src/squadron/pipeline/executor.py:1293`, `src/squadron/pipeline/executor.py:1511-1610`

- [ ] agree   - [ ] disagree →

### 197-I16 · MINOR (high)
**_pre_flag silently defaults a missing flag_kind to NOT_READY.**

Found by: haiku-xhigh ×1, sonnet ×1 · CONCERN ×2

FlagKind(str(item.get(FLAG_KIND_KEY, FlagKind.NOT_READY))) defaults the kind, and _cf_slices_needing_tasks sets flag_reason without a kind. The default gives the correct kind for every current producer, so this is a style/rule point.

Evidence: `src/squadron/pipeline/executor.py:1617`

- [ ] agree   - [ ] disagree →

### 197-I17 · MINOR (high)
**Three separate atomic-write helpers and a duplicated flock sequence.**

Found by: haiku-xhigh ×1 · CONCERN ×1

batch_report, state and metrology each have their own _write_atomic, and run_lock repeats the flock probe from metadata_lock. A DRY point with no defect.

Evidence: `src/squadron/pipeline/batch_report.py:343`, `src/squadron/pipeline/run_lock.py:111-141`

- [ ] agree   - [ ] disagree →

### 197-I2 · MINOR (medium)
**The blanket except OSError in resume_item reports any OSError, including a missing pipeline from load_pipeline, as a batch-report write failure with HALTED.**

Found by: haiku-xhigh ×2, sonnet-high ×3 · CONCERN ×5

_validate calls load_pipeline(state.pipeline) unguarded; its FileNotFoundError is an OSError, so it reaches the except OSError and returns HALTED (3) with 'cannot write the batch report', where REJECTED (2) with an accurate message fits. Any other OSError (git binary, state read) gets the same wrong label. The finding sonnet-high/1/0 says FileNotFoundError prints a traceback, which is wrong (it is caught as OSError); only loader validation errors would escape. Rare path, wrong message and code but loud; the message was later changed in 39dda24d.

Evidence: `src/squadron/pipeline/item_resume.py:133-135`, `src/squadron/pipeline/item_resume.py:186`

- [ ] agree   - [ ] disagree →

### 197-I20 · MINOR (high)
**Item resume runs synchronous git, cf and file I/O directly inside async functions.**

Found by: sol ×3, sonnet ×2, sonnet-high ×1 · CONCERN ×6

_resume_locked and helpers call run_git, restore_target, dirty_paths, cf_client.list_slices and report.write synchronously. True, but the CLI runs this single coroutine under asyncio.run with nothing else on the loop, so there is no observable effect.

Evidence: `src/squadron/pipeline/item_resume.py:139-160`, `src/squadron/pipeline/item_resume.py:230-242`

- [ ] agree   - [ ] disagree →

### 197-I21 · MINOR (high)
**Bare next() without a default in ItemRerun.replace/_outcome/_reconcile, and a dead raise AssertionError after the with block.**

Found by: sonnet ×2 · CONCERN ×2

next() without a default would raise StopIteration if the index were absent, but _check_record has already verified the record exists and the item index matches the request, so it cannot fire. The trailing AssertionError is dead code for the type checker.

Evidence: `src/squadron/pipeline/batch_report.py:378`, `src/squadron/pipeline/item_resume.py:136`, `src/squadron/pipeline/item_resume.py:164`

- [ ] agree   - [ ] disagree →

### 197-I24 · MINOR (medium)
**The per-item report write has no fsync, and a per-item write failure ends the batch without that being documented or tested.**

Found by: sonnet ×1 · CONCERN ×1

Writes go through asyncio.to_thread with temp-and-rename, so the loop is not blocked. The lack of fsync and the undocumented 'write failure ends the batch' behavior are hardening and docs points; D12 already states that a report write failure fails the run.

Evidence: `src/squadron/pipeline/executor.py:1598`

- [ ] agree   - [ ] disagree →

### 197-I25 · MINOR (high)
**_locked takes an already-created coroutine and must close it when the lock is refused.**

Found by: sonnet-high ×1 · CONCERN ×1

_locked receives a coroutine object and calls run_coroutine.close() on lock refusal; that is correct, but a factory or nullcontext would be simpler. Complexity point only.

Evidence: `src/squadron/cli/commands/run.py:944-955`

- [ ] agree   - [ ] disagree →

### 197-I26 · MINOR (high)
**New test helpers and tests use type: ignore and untyped signatures.**

Found by: sonnet-high ×1 · CONCERN ×1

item_resume_support.py and several tests carry type: ignore[no-untyped-def] and [attr-defined]. A test typing point with no effect on product behavior.

Evidence: `tests/pipeline/item_resume_support.py:176`, `tests/cli/commands/test_run_lock_cli.py:79`

- [ ] agree   - [ ] disagree →

### 197-I27 · MINOR (high)
**item_params pops reserved keys inside a generator expression, so a reserved key stored as None is dropped without a warning.**

Found by: sonnet-high ×1 · CONCERN ×1

The comprehension mutates params and reports only non-None values, so a None-valued reserved key is removed silently. Harmless (the key is removed as intended) and only a readability point; the assert in run.py is guarded by check_item_flags.

Evidence: `src/squadron/pipeline/item_resume.py:257`, `src/squadron/cli/commands/run.py:1201`

- [ ] agree   - [ ] disagree →

### 197-I3 · MINOR (medium)
**BatchReport.load lets a non-object item escape as AttributeError and turns missing index/name into the string 'None'.**

Found by: haiku-xhigh ×3, sol ×3 · CONCERN ×6

from_json does data.get(...) on each item, so an item like null raises AttributeError, which load's except (KeyError, TypeError, ValueError) does not catch, breaking the documented BatchReportLoadError contract; a missing index or name becomes 'None'. True, but report.json is written only by squadron itself, so this needs a hand-edited or corrupted file; the result is a loud traceback, and a 'None' index simply fails _check_record with REJECTED.

Evidence: `src/squadron/pipeline/batch_report.py:164-170`, `src/squadron/pipeline/batch_report.py:330-340`

- [ ] agree   - [ ] disagree →

### 197-I4 · MINOR (medium)
**_write_atomic leaves its NamedTemporaryFile behind when the write or rename fails (and the reports become mode 0600).**

Found by: haiku-xhigh ×3, sonnet ×1, sonnet-high ×3 · CONCERN ×7

The temp file is created with delete=False and the except OSError branch logs and re-raises without unlinking it, so each failed write leaves a hidden .name.XXXX file; mkstemp also makes the renamed reports 0600. Real but low impact: it only occurs when the disk is already failing, the names do not end in .json so list_runs ignores them, and the previous report stays intact. Fixed later in 39dda24d.

Evidence: `src/squadron/pipeline/batch_report.py:343-355`

- [ ] agree   - [ ] disagree →

### 197-I5 · MINOR (medium)
**list_tasks now requires 'completed' and 'total' and raises a bare KeyError without them; TaskEntry defaults both to 0.**

Found by: haiku-xhigh ×3, sonnet-high ×1 · CONCERN ×4

int(e['completed']) and int(e['total']) are hard lookups, so a cf that omits them raises KeyError rather than ContextForgeError. context-forge's task listing has emitted completed/total since 2026-03 (packages/cli/src/commands/task.ts), so this needs a months-old cf. The 0 defaults are only reachable from hand-built entries (tests); production always passes explicit values. Hardening and style, not a defect at head.

Evidence: `src/squadron/integrations/context_forge.py:58-59`, `src/squadron/integrations/context_forge.py:183-184`

- [ ] agree   - [ ] disagree →

### 197-I6 · MINOR (high)
**item_resume types cf_client as Any and BodyRunner returns object, erasing the client and result contracts.**

Found by: haiku-xhigh ×2, sonnet ×1, sonnet-high ×2 · CONCERN ×5

resume_item, _resume_locked, _git_precondition, _select_item and _open_dependencies take cf_client: Any and BodyRunner returns Awaitable[object]. True, but it is a typing gap; the calls made are correct for ContextForgeClient, which is what run_item passes.

Evidence: `src/squadron/pipeline/item_resume.py:60`, `src/squadron/pipeline/item_resume.py:109-116`

- [ ] agree   - [ ] disagree →

### 197-I7 · MINOR (high)
**run_item.py imports private helpers back from run.py inside a function, forming a circular dependency.**

Found by: haiku-xhigh ×3, sonnet ×3, sonnet-high ×3 · CONCERN ×9

run.py imports run_item at module level and handle_item_resume imports _apply_param_overrides and _run_pipeline_sdk from run.py locally with reportPrivateUsage suppressions. Accurate layering/style point with no behavioral effect; it was refactored away in 39dda24d.

Evidence: `src/squadron/cli/commands/run_item.py:61-65`, `src/squadron/cli/commands/run.py:24`

- [ ] agree   - [ ] disagree →

### 197-I8 · MINOR (medium)
**pipeline_mutates does not count dispatch, so judge-cycle (a non-committing revise loop) runs without the project lock.**

Found by: haiku-xhigh ×1 · CONCERN ×1

_MUTATING_STEP_TYPES lists DESIGN, TASKS, IMPLEMENT, DEVLOG, BRANCH, and a loop only counts with commit_each_iteration, so judge-cycle's revise dispatch is unlocked. That matches D11's stated scope exactly (steps that commit or move cf); a concurrent judge-cycle in the same checkout would at worst make a batch see a dirty tree and halt explicitly. A scope question, not a defect against the design.

Evidence: `src/squadron/pipeline/run_lock.py:36-45`, `src/squadron/data/pipelines/judge-cycle.yaml:16-29`

- [ ] agree   - [ ] disagree →

### 197-I9 · MINOR (high)
**The mutating-step allowlist fails open for step types added later.**

Found by: haiku-xhigh ×1, sonnet ×1, sonnet-high ×2 · CONCERN ×4

A step type not in _MUTATING_STEP_TYPES is treated as non-mutating with no warning. True, but it concerns hypothetical future step types; every current mutating pipeline classifies correctly per D11.

Evidence: `src/squadron/pipeline/run_lock.py:36-67`

- [ ] agree   - [ ] disagree →

### 197-I13 · PREEXISTING (high)
**run_dry_run._item_label still reads the 'flag_reason' literal instead of FLAG_REASON_KEY.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The literal is in run_dry_run.py, which base..head does not touch; the diff only added the constant elsewhere. The value matches, so nothing breaks today.

Evidence: `src/squadron/cli/commands/run_dry_run.py:92`

- [ ] agree   - [ ] disagree →

### 197-I15 · PREEXISTING (medium)
**A halted item's record is built with no step results, so it loses the slice branch it entered.**

Found by: haiku-xhigh ×1 · CONCERN ×1

_finish_each_report passes a literal [] to from_item for the in-flight item, so branch is None. That [] was there before the diff (base had the same from_item(item, position, [], reason) call); the diff only added flag_kind. Item resume's restore path uses the current branch, not record.branch, so the effect is informational.

Evidence: `src/squadron/pipeline/executor.py:1490`

- [ ] agree   - [ ] disagree →

### 197-I22 · PREEXISTING (medium)
**run() is oversized and repeats the SDK/PROMPT_ONLY dispatch in its resume branches.**

Found by: sonnet ×1 · CONCERN ×1

The duplicated match blocks in the resume and implicit-resume branches were already there; the diff only wraps each existing call in _locked and does not add a new copy as the finding says. The item-resume branch calls handle_item_resume, not another dispatch.

Evidence: `src/squadron/cli/commands/run.py:1231-1257`, `src/squadron/cli/commands/run.py:1289-1315`

- [ ] agree   - [ ] disagree →

## 225

### 225-I1 · REAL (high) — known B1
**raw_counts counts every tick_trade row in the session windows with no product/instrument filter, so other products' rows show as mismatches**

Found by: haiku-xhigh ×2, sol ×2, sonnet ×1, sonnet-high ×2 · CONCERN ×7

raw_counts filters tick_trade only by ts_event against the session windows, while ledger_totals is filtered by the product's shape. _session_row takes the union of instrument keys from both maps, so any instrument with raw rows but no shape ledger row becomes a Mismatch(ledger 0, raw n) and coverage exits 3. This is the case's known bug, fixed later in 459ac7bd.

Evidence: `src/manta_trading/data/tick/status_reads.py:154-174`, `src/manta_trading/data/tick/status_reads.py:96-106`, `src/manta_trading/data/tick/tick_coverage.py:81-90`

- [ ] agree   - [ ] disagree →

### 225-I2 · REAL (medium)
**caught_up is evaluated (and can read 'yes') when a tier and start are set but the wanted end is unknown**

Found by: haiku-xhigh ×3, sonnet-high ×2 · CONCERN ×5

_product_status sets wanted=None when _wanted_end returns None (no entry.end and no tick_dataset_edge row), so _scope covers only held sessions, yet line 217 passes wanted=wanted_start is not None, which is True. caught_up then returns all(...) over held sessions only (vacuously True with none), so status prints 'caught up: yes' beside 'edge: never observed', against the slice's 'without a wanted range: n/a'. Latent while ES has tier=None, but reachable once a tier is set on a database with no edge row (for example one rebuilt by ingest alone); the later 8a9c47ec fix kept the same wanted flag.

Evidence: `src/manta_trading/data/tick/tick_status_build.py:186-193`, `src/manta_trading/data/tick/tick_status_build.py:217`, `src/manta_trading/data/tick/tick_status.py:152-163`, `src/manta_trading/data/tick/universe.py:45-47`

- [ ] agree   - [ ] disagree →

### 225-I3 · REAL (medium)
**Coverage reads ledger totals and raw counts in separate autocommit snapshots, so an ingest committing between them gives a false mismatch**

Found by: sol ×3 · FAIL ×3

_connect opens the read connection with autocommit=True, and build_coverage runs session_verdicts, ledger_totals and raw_counts as separate statements with no enclosing transaction. Ingest commits a unit's tick_trade rows and ledger rows together, so a commit landing between the ledger_totals and raw_counts statements leaves raw > ledger for that session and coverage exits 3 reporting corruption. The window is real but transient and clears on rerun, so it is worth a REPEATABLE READ fix but does not block merge.

Evidence: `src/manta_trading/data/tick/store_context.py:157-161`, `src/manta_trading/data/tick/tick_coverage.py:107-113`, `src/manta_trading/cli/commands/tick_store_cmds.py:156-167`

- [ ] agree   - [ ] disagree →

### 225-I11 · FALSE (medium)
**Unannotated SQL fragments in status_reads may fail strict pyright's LiteralString check**

Found by: haiku-xhigh ×1 · CONCERN ×1

The project's type checker is mypy, not pyright (pyproject says so explicitly), and mypy treats LiteralString as str, so these str constants do not produce a merge-blocking error. The fragments are unchanged at the current HEAD, consistent with the check passing.

Evidence: `pyproject.toml:68-75`, `src/manta_trading/data/tick/status_reads.py:50-59`

- [ ] agree   - [ ] disagree →

### 225-I5 · FALSE (high)
**calendar_sessions misses psycopg_pool PoolTimeout, so a calendar outage escapes as a traceback**

Found by: haiku-xhigh ×1 · CONCERN ×1

psycopg_pool defines PoolTimeout (and PoolClosed) as subclasses of psycopg.OperationalError, so the existing except (psycopg.OperationalError, CalendarNotFoundError) catches it and maps it to TickCalendarError, which exit_code_for maps to exit 4. The claimed traceback cannot happen.

Evidence: `src/manta_trading/data/tick/tick_status_build.py:70-71`, `src/manta_trading/data/base/trading_calendar.py:154,194`, `src/manta_trading/cli/commands/tick_exit.py:54-57`, `psycopg_pool/errors.py:16 (class PoolTimeout(e.OperationalError))`

- [ ] agree   - [ ] disagree →

### 225-I4 · UNSURE (medium)
**raw_counts' range join against unnested sessions may cost rows x sessions with no ts_event index; the cost is unmeasured**

Found by: haiku-xhigh ×3 · CONCERN ×3

tick_trade is a hypertable on ts_event created with create_default_indexes => FALSE and its key leads with instrument_id, so the outer WHERE bound gives chunk exclusion but the BETWEEN join to unnest has no index and will likely be a nested loop with a join filter evaluated rows x sessions times. Whether that is materially slow on realistic ranges is not settled by the code; the slice design chose this exact join. An EXPLAIN ANALYZE of coverage over a multi-month ES range on production-sized data would settle it.

Evidence: `src/manta_trading/data/tick/status_reads.py:166-173`, `src/manta_trading/market/schema/migrations/tick.py:248-254`

- [ ] agree   - [ ] disagree →

### 225-I10 · MINOR (high)
**status_reads re-declares the unit/request join instead of using manifest_reads.UNIT_FROM**

Found by: haiku-xhigh ×1 · CONCERN ×1

_UNITS is the same string as manifest_reads.UNIT_FROM, and status_reads adds SQL on tick_request/tick_archive_unit outside the modules manifest_reads' docstring names. Structure and DRY only; no behavior difference.

Evidence: `src/manta_trading/data/tick/status_reads.py:50-59`, `src/manta_trading/data/tick/manifest_reads.py:90`

- [ ] agree   - [ ] disagree →

### 225-I12 · MINOR (high)
**Wanted-range/tier path of status (caught_up, holed, tier rendering) has no integration test**

Found by: haiku-xhigh ×2 · CONCERN ×2

Every integration test uses TICK_UNIVERSE[0], which has tier=None, so _wanted_end, the wanted branch of _scope and caught_up True/False are not exercised end to end. A test gap; the defect it would catch is graded separately.

Evidence: `test/integration/data/test_tick_status_build.py:87`, `src/manta_trading/data/tick/universe.py:46`

- [ ] agree   - [ ] disagree →

### 225-I13 · MINOR (high)
**Render branches and age() in tick_status_render have no direct tests**

Found by: sonnet-high ×1 · CONCERN ×1

No test imports tick_status_render, and the CLI tests cover only the tier-less, edge-less path. Missing tests for paths that are otherwise correct (apart from the cosmetic negative-age case graded separately).

Evidence: `src/manta_trading/cli/commands/tick_status_render.py:43-110`

- [ ] agree   - [ ] disagree →

### 225-I14 · MINOR (high)
**_session_row rescans all ledger/raw keys per session (quadratic) synchronously**

Found by: sol ×3 · CONCERN ×3

Each _session_row builds the instrument set by scanning every key of both dicts, so assembly is O(sessions x keys). This is a one-shot CLI with no concurrent tasks on its loop, and the cost is small next to the tick_trade scan for the same range; no real effect.

Evidence: `src/manta_trading/data/tick/tick_coverage.py:81`, `src/manta_trading/data/tick/tick_coverage.py:114`

- [ ] agree   - [ ] disagree →

### 225-I15 · MINOR (high)
**Module-level assert guards that _BUCKET_ROWS covers every TickSessionStatus**

Found by: sonnet ×2, sonnet-high ×2 · CONCERN ×4

The exhaustiveness check is a bare module-level assert, stripped under -O. The same pattern already exists in tick_exit.py; a missing bucket would only drop a row from human output. Style/hardening.

Evidence: `src/manta_trading/cli/commands/tick_status_render.py:38-40`, `src/manta_trading/cli/commands/tick_exit.py:32-35`

- [ ] agree   - [ ] disagree →

### 225-I16 · MINOR (high)
**run_mapped's per-verb storage tuple splits exit-code policy from tick_exit.exit_code_for**

Found by: sonnet ×1, sonnet-high ×1 · CONCERN ×2

run_mapped checks the caller's storage tuple before exit_code_for so read verbs map TickDatabaseUnreachable to 4 while writers keep 1. Behavior is correct and tested; this is a design-cohesion point.

Evidence: `src/manta_trading/cli/commands/tick_store_cmds.py:66-82`, `src/manta_trading/cli/commands/tick_store_cmds.py:170-173`

- [ ] agree   - [ ] disagree →

### 225-I17 · MINOR (high)
**_product_status and _product_lines are long and mix responsibilities; jsonable lives in the status module**

Found by: sonnet ×1 · CONCERN ×1

Function length and module placement concerns only; no behavior effect.

Evidence: `src/manta_trading/data/tick/tick_status_build.py:179-227`, `src/manta_trading/cli/commands/tick_status_render.py:57-110`

- [ ] agree   - [ ] disagree →

### 225-I18 · MINOR (high)
**shape_units is queried twice per product, and spread filtering uses list membership**

Found by: sonnet ×1, sonnet-high ×2 · CONCERN ×3

_scope and session_verdicts each call shape_units for the same shape, and contracts are filtered with 'c not in spreads'. Both true; one extra manifest query and a small quadratic over a handful of contracts have no real effect.

Evidence: `src/manta_trading/data/tick/tick_status_build.py:87`, `src/manta_trading/data/tick/tick_status_build.py:155`, `src/manta_trading/data/tick/tick_status_build.py:224`

- [ ] agree   - [ ] disagree →

### 225-I19 · MINOR (high)
**_read and the coverage read callback type the connection as Any**

Found by: sonnet-high ×1 · CONCERN ×1

_read takes Callable[[Any, str], ...] and the inner read uses conn: Any although manifest_reads defines Conn. Typing looseness only.

Evidence: `src/manta_trading/cli/commands/tick_store_cmds.py:156-158`, `src/manta_trading/cli/commands/tick_store_cmds.py:228`

- [ ] agree   - [ ] disagree →

### 225-I6 · MINOR (medium)
**An out-of-calendar-range --start/--end exits 4 (storage), which the read epilog does not describe; unreachable-calendar path untested**

Found by: haiku-xhigh ×1 · CONCERN ×1

calendar_sessions turns OutOfPopulatedRangeError into TickCalendarError, which exit_code_for maps to EXIT_STORAGE, while READ_EPILOG names exit 4 only for an unreachable database. The message is still printed, so the effect is a misclassified exit code for an input/range problem (later changed to exit 1 in 3188a92f); the second bullet's pool-exception doubt is unfounded since PoolTimeout is an OperationalError.

Evidence: `src/manta_trading/data/tick/tick_status_build.py:72-73`, `src/manta_trading/cli/commands/tick_store_cmds.py:37-42`, `src/manta_trading/cli/commands/tick_exit.py:54-57`

- [ ] agree   - [ ] disagree →

### 225-I7 · MINOR (high)
**age() renders negative ages (clock skew) as '-1d 23h'**

Found by: haiku-xhigh ×2 · CONCERN ×2

age() applies floor divmod to int(seconds), so a negative input yields days=-1, hours=23 and prints '-1d 23h'. A negative age needs the status host's clock to lag the pass host's; the effect is a cosmetic line in human output only.

Evidence: `src/manta_trading/cli/commands/tick_status_render.py:43-50`, `src/manta_trading/data/tick/tick_status_build.py:211-213`

- [ ] agree   - [ ] disagree →

### 225-I8 · MINOR (high)
**build_coverage itself does not reject end <= start**

Found by: haiku-xhigh ×1 · CONCERN ×1

The only caller at head, the CLI, rejects end <= start before calling build_coverage. The unguarded path matters only for a future API caller (slice 230), so this is hardening against input that cannot arrive today.

Evidence: `src/manta_trading/cli/commands/tick_store_cmds.py:216-222`, `src/manta_trading/data/tick/tick_coverage.py:94-115`

- [ ] agree   - [ ] disagree →

### 225-I9 · MINOR (high)
**calendar_sessions duplicates product_session_days' calendar open/error-mapping/close**

Found by: haiku-xhigh ×2, sonnet-high ×1 · CONCERN ×3

calendar_sessions repeats the same TradingCalendar open, the same exception-to-TickCalendarError mapping and close as tick_calendar.product_session_days. True duplication, but both copies behave identically today; a DRY refactor, not a defect.

Evidence: `src/manta_trading/data/tick/tick_status_build.py:63-75`, `src/manta_trading/data/tick/tick_calendar.py:67-81`

- [ ] agree   - [ ] disagree →

## 227

### 227-I1 · REAL (medium)
**The cutover runner catches only StepFailed and CalledProcessError, so any other exception skips the report the docstring promises.**

Found by: haiku-xhigh ×3, sol ×3, sonnet ×3, sonnet-high ×3 · CONCERN ×12

run_steps catches only (StepFailed, CalledProcessError), and main() writes the report only after run_steps returns. step_production reads the production health log with no exists/empty guard, shell() has no timeout, and OSError from rclone/arm.touch or IndexError on an empty log escape, so a mid-cutover failure on a host being changed leaves no report, against the module docstring. Most individual triggers are unlikely, but the broken guarantee is in new code; the author accepted it as review F002 and widened the handler and added log_tail in 94beba1b.

Evidence: `scripts/cutover_227_tick_backup.py:4-6`, `scripts/cutover_227_tick_backup.py:224`, `scripts/cutover_227_tick_backup.py:269-284`, `scripts/cutover_227_tick_backup.py:309-312`, `scripts/cutover_227_host.py:56`, `scripts/cutover_227_host.py:82`

- [ ] agree   - [ ] disagree →

### 227-I10 · REAL (high) — known B1
**b2_lifecycle.sh captures rclone's stderr with 2>&1 into the JSON it parses with jq.**

Found by: haiku-xhigh ×1 · CONCERN ×1

RULES=$(... rclone backend lifecycle ... 2>&1) merges stderr into the rule list, so any rclone notice makes jq's type check fail and setup-backup reports MISSING lifecycle-read, failing the check. This is the known bug, fixed in 0ccf9b00 after it broke cutover step 2 under sudo.

Evidence: `deploy/lib/b2_lifecycle.sh:65-72`, `deploy/setup-backup.sh:240-247`

- [ ] agree   - [ ] disagree →

### 227-I12 · REAL (high)
**production_changes strips the new arguments only from the new file, so every re-run after cron installation fails step 4.**

Found by: sol ×3 · FAIL ×3

step_check stores the installed cron file as old_cron; after a first run that file already has --url-key etc. production_changes strips only the new side, so identical files compare unequal and step_apply raises StepFailed. That breaks the documented recovery ('fix the cause, re-run') for any failure after step 4. The author fixed it as F001 in 94beba1b by stripping both sides.

Evidence: `scripts/cutover_227_helpers.py:91-99`, `scripts/cutover_227_tick_backup.py:95`, `scripts/cutover_227_tick_backup.py:114-120`, `scripts/cutover_227_tick_backup.py:7-8`

- [ ] agree   - [ ] disagree →

### 227-I16 · REAL (high)
**step_apply rejects pg_settings' pre-restart DRIFT lines, so the first enrolment of tick always stops at step 4.**

Found by: sol ×1 · FAIL ×1

run_lib echoes all of pg_settings.sh's output, including the DRIFT lines printed before ALTER SYSTEM. archive_mode stays DRIFT 'on' 'off' until the restart in step 5. APPLY_ALLOWED admits only PENDING RESTART and arm-file lines, so setup_not_ok flags them and step 4 fails before the restart. The 2026-10-05 run stopped at step 4 this way, and d14f8a60 added r'^DRIFT 17/tick archive_mode ' to APPLY_ALLOWED.

Evidence: `scripts/cutover_227_tick_backup.py:73`, `scripts/cutover_227_tick_backup.py:108-113`, `deploy/setup-backup.sh:151-157`, `deploy/lib/pg_settings.sh:85-118`

- [ ] agree   - [ ] disagree →

### 227-I11 · MINOR (high)
**test_setup_backup.py has grown to 1072 lines.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The file grew from 812 to 1072 lines in this diff. File size is a style point.

Evidence: `test/unit/test_setup_backup.py`

- [ ] agree   - [ ] disagree →

### 227-I13 · MINOR (medium)
**run_health ignores the health command's result and can judge a stale last log line.**

Found by: sol ×2, sonnet ×1 · CONCERN ×3

run_health discards shell()'s result and reads the last line of an append-only log. backup_health_cron.sh writes a FAIL cannot_check line on most failures, which health_flags rejects; a stale pass needs the script to exit before logging (argument errors) right after an earlier clean run with the same command. The gap is true but needs unlikely conditions.

Evidence: `scripts/cutover_227_tick_backup.py:157-165`, `scripts/backup_health_cron.sh:60-92`

- [ ] agree   - [ ] disagree →

### 227-I15 · MINOR (medium)
**After an offsite upload failure, re-running step_weekly cannot resume because backup_prod.sh refuses an existing destination.**

Found by: sol ×1 · CONCERN ×1

step_weekly skips only when today's base dir and the arm file both exist; otherwise it reruns the full weekly job, and backup_prod.sh exits on 'destination already exists'. The re-run fails loudly and the operator can delete the local dir or wait a day, so it is a recovery inconvenience, not wrong data.

Evidence: `scripts/cutover_227_tick_backup.py:173-189`, `scripts/backup_prod.sh:74-75`

- [ ] agree   - [ ] disagree →

### 227-I17 · MINOR (high)
**assert is used for type narrowing in runtime code (block_commands, run_health).**

Found by: sonnet ×2 · CONCERN ×2

Both asserts are present, but each is unreachable as a failure: _job_lines already filtered on the same regex, and require() raises before the assert in run_health. Stripping them under -O changes nothing; it is style.

Evidence: `scripts/cutover_227_helpers.py:64`, `scripts/cutover_227_tick_backup.py:163-164`

- [ ] agree   - [ ] disagree →

### 227-I18 · MINOR (medium)
**production_lines identifies the host block by the cron user field 'root'.**

Found by: sonnet ×1 · CONCERN ×1

The check j.split()[5] == 'root' exists and depends on the host jobs running as root, which the template fixes. It is a field of a root-owned generated file, not a user-visible label, and it is correct today; a robustness point.

Evidence: `scripts/cutover_227_helpers.py:74-81`, `deploy/cron.d/manta-trading-backup`

- [ ] agree   - [ ] disagree →

### 227-I19 · MINOR (high)
**The provisioning tests assert on shell and SQL source text instead of behaviour.**

Found by: sonnet ×1, sonnet-high ×1 · CONCERN ×2

The new tests regex-extract script text and compare substrings and positions. That is a test-design point; no production defect follows from it.

Evidence: `test/unit/test_provision_tick_lib.py:177-258`

- [ ] agree   - [ ] disagree →

### 227-I2 · MINOR (high)
**The assertion that cron commands carry no user field can never fail.**

Found by: haiku-xhigh ×3 · CONCERN ×3

block_commands returns the command text, which starts with the absolute checkout path, so c.split('/')[0] is always '' and the assertion is vacuous. It is a test-quality defect only; the production code it covers is correct. haiku 1/1's added point, that the report test never calls main(), is also a test gap.

Evidence: `test/unit/test_cutover_227.py:101`, `test/unit/test_cutover_227.py:194-215`

- [ ] agree   - [ ] disagree →

### 227-I20 · MINOR (medium)
**Provisioning drops trading_tick_proof and the MT_PROOF_226_* keys while the 226 proof harness still references them.**

Found by: sonnet ×1, sonnet-high ×1 · CONCERN ×2

The removal is deliberate: the slice design at head says the proof database is gone and the MT_PROOF_226_* lines are stale. The harness and TICK_PROOF_DB_NAME are left as dead references to a one-off proof, a cleanup point rather than a regression.

Evidence: `project-documents/user/slices/227-slice.backup-coverage-for-tick-archive-and-database.md:57`, `project-documents/user/slices/227-slice.backup-coverage-for-tick-archive-and-database.md:74`, `scripts/provision_tick_cluster.sh`

- [ ] agree   - [ ] disagree →

### 227-I21 · MINOR (high)
**The cutover tests leave step_apply, step_check, step_offsite and main() untested, and the render test exempts a nonexistent @192.**

Found by: sonnet-high ×1 · CONCERN ×1

Those steps have no tests, and test_setup_backup.py:777 replaces '@192' although no '@192' exists under deploy/, which weakens the placeholder check (removed later in 229fa4de). These are test gaps and test quality, not production defects.

Evidence: `test/unit/test_setup_backup.py:777`, `test/unit/test_cutover_227.py`

- [ ] agree   - [ ] disagree →

### 227-I3 · MINOR (high)
**The new with_replication branch of provision_tick_roles.sql runs in no database-backed test.**

Found by: haiku-xhigh ×3 · CONCERN ×3

The REPLICATION branch is checked only by text order in the unit test; the DB fixture applies the file without with_replication. The branch is copied from provision_roles.sql and reads correctly (\if :{?with_replication}, format(... %I REPLICATION) with \gexec), so this is a missing test for a path with no shown defect.

Evidence: `scripts/provision_tick_roles.sql:116-125`, `test/unit/test_provision_tick_lib.py:255-258`

- [ ] agree   - [ ] disagree →

### 227-I4 · MINOR (medium)
**Step 2 runs setup-backup --check before provisioning, and setup-backup dies when 17/tick is not in pg_lsclusters.**

Found by: haiku-xhigh ×1 · CONCERN ×1

setup-backup.sh dies in check mode too when a table cluster is absent from pg_lsclusters, and step_check runs before step_provision, which is the step that can pg_createcluster. On manta9000, the only host this cutover targets, 17/tick already exists, as the finding itself says, so the run is not blocked. It matters only for a hypothetical fresh-host use of a one-off script.

Evidence: `deploy/setup-backup.sh:125-127`, `scripts/cutover_227_tick_backup.py:87-95`, `scripts/provision_tick_cluster.sh:184-188`

- [ ] agree   - [ ] disagree →

### 227-I5 · MINOR (high)
**tick_locks_held builds SQL with an f-string and env_value interpolates the library path into bash -c.**

Found by: haiku-xhigh ×1 · CONCERN ×1

Both interpolations exist, but the SQL values are two integer constants and the library path is the script's own checkout location. No input that could break or inject arrives here; it is rule-conformance hardening.

Evidence: `scripts/cutover_227_host.py:75`, `scripts/cutover_227_host.py:90-96`

- [ ] agree   - [ ] disagree →

### 227-I6 · MINOR (high)
**Host constants (the '-' sentinel, ARM_FILE, RCLONE_REMOTE, bucket key, cluster names, paths) are defined in several places.**

Found by: haiku-xhigh ×2, sonnet-high ×2 · CONCERN ×4

The duplicates exist across Python and shell (ARM_FILE in setup-backup.sh:80 and cutover:69, RCLONE_REMOTE, TABLE_NONE, 17/tick in regexes, the date format in step_weekly). None currently disagrees, so this is a maintainability and DRY point with no wrong behavior at head.

Evidence: `deploy/setup-backup.sh:80-81`, `scripts/cutover_227_tick_backup.py:69-73`, `scripts/cutover_227_host.py:23-27`, `scripts/cutover_227_tick_backup.py:176`

- [ ] agree   - [ ] disagree →

### 227-I7 · MINOR (high)
**strip_new_args hard-codes --replication-host 127.0.0.1 instead of reading it from the table row.**

Found by: sonnet ×1, sonnet-high ×1 · CONCERN ×2

The literal is present and duplicates the 17/main row value. If the row changed, the TD3 comparison would report a change and stop the cutover, which fails safe. It agrees with the table today; the author changed it later (F003) as cleanup.

Evidence: `scripts/cutover_227_helpers.py:84-88`

- [ ] agree   - [ ] disagree →

### 227-I8 · MINOR (medium)
**The report is named by date only, so a same-day re-run overwrites the failed run's report.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The report path is NOTES_DIR/<date>-227-cutover.md and is written with write_text, so a same-day re-run replaces it. The failure output also went to the terminal, and the cost is lost audit notes, not wrong behavior.

Evidence: `scripts/cutover_227_tick_backup.py:310-312`

- [ ] agree   - [ ] disagree →

### 227-I9 · MINOR (medium)
**The cutover writes provision and setup output into the notes directory without the log_scrub pass the provision script uses.**

Found by: haiku-xhigh ×1 · CONCERN ×1

True that no scrub runs before report.write_text. provision_tick_cluster.sh passes passwords through stdin and PGPASSWORD and prints no secrets, so this is defence-in-depth against output that is not shown to occur.

Evidence: `scripts/cutover_227_tick_backup.py:310-312`, `scripts/provision_tick_cluster.sh:305-313`

- [ ] agree   - [ ] disagree →

### 227-I14 · PREEXISTING (medium)
**On a cluster that never archived, pg_settings.sh never persists archive_command because it shows as (disabled).**

Found by: sol ×1 · FAIL ×1

pg_settings.sh reports a (disabled) archive_command as PENDING RESTART and never adds it to DRIFTED, so the tick enrolment would restart into archive_mode=on with no command; the 2026-10-05 cutover run hit this and d14f8a60 fixed it. The claim is correct and the new tick enrolment exposes it, but the defective code in deploy/lib/pg_settings.sh was not changed in base..head, and the case file excludes d14f8a60 for that reason.

Evidence: `deploy/lib/pg_settings.sh:90-94`, `deploy/setup-backup.sh:225-228`

- [ ] agree   - [ ] disagree →

## 307

### 307-I1 · REAL (high) — known B1
**The estimate judge reads plan keys at the top level of the pass --json payload, where the purchase summary is nested under phases[].summary, so the first lookup raises KeyError.**

Found by: haiku-xhigh ×1 · FAIL ×1

fetch_estimate returns json.loads of `pass --estimate-only --json` unchanged; PassResult.to_dict puts each phase's summary under phases[i].summary. _check_scope reads summary["wanted_days"] and the new _estimate_only reads summary["planned_usd"] at top level, so both the full cutover and --estimate crash before judging. Fixed in a7c5e36f (purchase_summary unwraps the purchase phase).

Evidence: `scripts/cutover_304_first_purchase.py:152-163`, `scripts/cutover_304_first_purchase.py:269-270`, `scripts/cutover_304_checks.py:196`, `src/manta_trading/data/tick/pass_contract.py:119-135`

- [ ] agree   - [ ] disagree →

### 307-I13 · REAL (medium)
**Session evidence reads only history wants, so the ES and GC tbbo tick-tier families are never judged by the D6 item 3 exit rule.**

Found by: sol ×3 · CONCERN ×2, FAIL ×1

coverage_reads iterates entry.history only, so not_caught_up_report is never called for the tbbo tier, while D6 item 2 lists tbbo and item 3 and the exit criterion require every family not caught up to have each session named. An unhealthy tbbo family with an unchanged health baseline would pass unnamed. Impact is bounded because 307 buys no tbbo days.

Evidence: `scripts/cutover_304_evidence.py:72-91`, `scripts/cutover_304_evidence.py:217-231`, `project-documents/user/slices/307-slice.futures-history-acquisition.md:229-235`

- [ ] agree   - [ ] disagree →

### 307-I14 · REAL (high)
**Every provider_hole session is skipped from the not-caught-up report, though only holes on provider-missing days are exempt.**

Found by: sol ×1 · FAIL ×1

_LISTED_NEVER includes PROVIDER_HOLE unconditionally. classify_day returns PROVIDER_HOLE for a unit whose fetch_status is PROVIDER_HOLE regardless of condition, and tick_status.caught_up exempts a hole only when provider_missing; D6 item 3 says the same. A hole on an available day leaves the family not caught up yet produces no line and no failure, so the exit rule passes silently.

Evidence: `scripts/purchase_verdicts.py:207-210`, `scripts/purchase_verdicts.py:285-286`, `src/manta_trading/data/tick/tick_status.py:108-109`, `src/manta_trading/data/tick/tick_status.py:158-168`

- [ ] agree   - [ ] disagree →

### 307-I15 · REAL (high)
**--estimate runs the installed production mt, so it prices the old universe's wants, not the requested release's.**

Found by: sol ×1 · FAIL ×1

_estimate_only never installs; fetch_estimate calls `sudo mt-run` (the installed release), and preflight only resolves the ref. Before 307 is installed the universe lacks the widened bars and GC bars, so the D4 ceiling command is derived from the wrong plan. The full cutover still stops on short ceilings before spending and prints the right command, so it costs a re-run, not money.

Evidence: `scripts/cutover_304_first_purchase.py:255-276`, `scripts/cutover_304_first_purchase.py:152-163`, `scripts/cutover_304_evidence.py:51-53`, `scripts/cutover_common.py:97-117`

- [ ] agree   - [ ] disagree →

### 307-I16 · REAL (high)
**The record-totals baseline is read before install, so it lacks the new GC bar_1m family and totals_delta raises after the purchase.**

Found by: sol ×1 · FAIL ×1

_steps calls record_start_and_baselines (accounting via the installed mt) before install_release. Accounting reports one row per family_wants family, and the base universe gives GC no ohlcv-1m want, so the baseline has no GC/bar_1m; after the purchase totals_delta raises on the missing key. Re-runs reuse the same baseline, so evidence step 5 can never complete.

Evidence: `scripts/cutover_304_first_purchase.py:286-288`, `scripts/cutover_304_evidence.py:98-101`, `scripts/purchase_accounting.py:136-144`, `src/manta_trading/data/tick/tick_status_scope.py:74-87`, `src/manta_trading/data/tick/family_report.py:249`

- [ ] agree   - [ ] disagree →

### 307-I2 · REAL (high) — known B2
**judge_estimate buys only on verdict "allowed", but --estimate-only always reports "estimate_only" for a non-empty plan, so the buy step is unreachable.**

Found by: haiku-xhigh ×3 · FAIL ×3

evaluate_spend sets VerdictStatus.ESTIMATE_ONLY whenever estimate_only is passed, and plan_summary emits that as verdict; judge_estimate raises unless verdict == VERDICT_ALLOWED. The verdict line itself predates base, but judge_estimate was rewritten in this diff and the case lists it as B2; a7c5e36f changed the check to estimate_only.

Evidence: `scripts/cutover_304_checks.py:242-245`, `src/manta_trading/data/tick/spend_guard.py:266-269`, `src/manta_trading/data/tick/purchase_plan.py:303`

- [ ] agree   - [ ] disagree →

### 307-I4 · REAL (medium)
**Over-session names are collected per product, not per volume family, so each family's over failure lists the other family's sessions.**

Found by: haiku-xhigh ×2, sol ×1 · CONCERN ×3

_family_evidence keys `named` by product and over_sessions discards each volume check's family; over_failures then attaches all of a product's over names to both its tick-tier and bar rows. Counts stay right but D6 item 4's named listing is wrong data. Fixed in a7c5e36f (keyed by (product, family)). The secondary `.get("volume_checks") or ()` point is needed for docs that carry no volume checks.

Evidence: `scripts/cutover_304_evidence.py:216`, `scripts/cutover_304_evidence.py:232-234`, `scripts/purchase_accounting.py:105-128`

- [ ] agree   - [ ] disagree →

### 307-I10 · MINOR (medium)
**A wanted family whose caught_up is None (no source edge) passes the D6 item 3 rule with nothing listed.**

Found by: haiku-xhigh ×1 · CONCERN ×1

not_caught_up_report returns empty unless caught_up is False. caught_up is None only when no dataset edge is known (family_source_edge/scope_caught_up), and run_gates already refuses a missing dataset edge before any spend, so the case is speculative hardening.

Evidence: `scripts/purchase_verdicts.py:275-276`, `src/manta_trading/data/tick/tick_status_scope.py:204-208`, `scripts/purchase_verdicts.py:79-90`

- [ ] agree   - [ ] disagree →

### 307-I11 · MINOR (high)
**Loose type annotations in new code and tests (untyped origins = {}, bare dict/list, -> object, __doc__ used as str).**

Found by: haiku-xhigh ×1, sonnet ×1, sonnet-high ×2 · CONCERN ×4

The annotations are as described (first_purchase.py:171, :209; test_purchase_verdicts.py:76, 187, 207, 250, 273-274), but the project's configured checker is mypy over src only, and none of these changes runtime behavior; __doc__ is None only under -OO.

Evidence: `scripts/cutover_304_first_purchase.py:171`, `scripts/cutover_304_first_purchase.py:209`, `test/unit/scripts/test_purchase_verdicts.py:76`, `test/unit/scripts/test_purchase_verdicts.py:187`

- [ ] agree   - [ ] disagree →

### 307-I12 · MINOR (high)
**EXIT_USAGE is defined and never used.**

Found by: haiku-xhigh ×1 · CONCERN ×1

EXIT_USAGE = 2 at line 79 has no reference; main returns argparse's code. Dead constant, removed in a7c5e36f.

Evidence: `scripts/cutover_304_first_purchase.py:79`

- [ ] agree   - [ ] disagree →

### 307-I17 · MINOR (high)
**resubmit_origins does not guard against naive requested_at, so comparing with the aware start would raise TypeError.**

Found by: sonnet ×1, sonnet-high ×1 · CONCERN ×2

requested_at is TIMESTAMPTZ NOT NULL, so psycopg yields an aware datetime and _cell's isoformat carries an offset; a naive value cannot arrive from the real CLI. Speculative hardening (the author added the guard anyway in a7c5e36f).

Evidence: `scripts/cutover_304_checks.py:157-164`, `src/manta_trading/market/schema/migrations/tick.py:146`

- [ ] agree   - [ ] disagree →

### 307-I18 · MINOR (high)
**Three cutover scripts are slightly over the ~300-line guideline.**

Found by: sonnet ×1 · CONCERN ×1

cutover_304_checks.py is 311 lines and the others are near 308-312. Style guideline only.

Evidence: `scripts/cutover_304_checks.py:311`

- [ ] agree   - [ ] disagree →

### 307-I19 · MINOR (high)
**Session dates and request ranges are compared as ISO strings, and gh state is matched by a string literal.**

Found by: sonnet ×1, sonnet-high ×1 · CONCERN ×2

_label compares str(range_start) and str(session_date), which _cell renders as YYYY-MM-DD, so lexicographic order is correct today; unknown buckets already raise CutoverError. Fragility against a hypothetical format change, no current wrong behavior.

Evidence: `scripts/purchase_verdicts.py:238-242`, `scripts/purchase_verdicts.py:37`, `scripts/purchase_verdicts.py:255`

- [ ] agree   - [ ] disagree →

### 307-I20 · MINOR (high)
**main catches SystemExit from argparse and converts its code with int().**

Found by: sonnet ×1 · CONCERN ×1

The swallow is narrow and commented; argparse only exits with int codes, so the str-code ValueError is theoretical.

Evidence: `scripts/cutover_304_first_purchase.py:229-234`

- [ ] agree   - [ ] disagree →

### 307-I21 · MINOR (high)
**No test that --estimate with a resubmit refuses without reading debug requests.**

Found by: sonnet ×1 · CONCERN ×1

judge only reads debug requests when since is not None, and _check_resubmit raises for since None; the path is correct and only a test is missing.

Evidence: `scripts/cutover_304_first_purchase.py:166-175`, `scripts/cutover_304_checks.py:175-176`

- [ ] agree   - [ ] disagree →

### 307-I22 · MINOR (high)
**The "want has no end date" loop and message are duplicated in coverage_reads and latest_want_end.**

Found by: sonnet-high ×3 · CONCERN ×3

Both functions walk TICK_UNIVERSE histories and raise the same message; the universe comment already forbids open ends. DRY concern with no behavior impact (sonnet-high/2/0's exit-code half is the same point as I8).

Evidence: `scripts/cutover_304_evidence.py:72-91`, `scripts/purchase_verdicts.py:64-76`

- [ ] agree   - [ ] disagree →

### 307-I3 · MINOR (medium)
**--estimate returns BUY and prints the ceiling command for any non-nothing verdict, even when the blocker is something a ceiling cannot fix (archive space).**

Found by: haiku-xhigh ×2, sonnet ×1, sonnet-high ×1 · CONCERN ×4

With check_ceilings=False judge_estimate returns BUY right after the nothing_to_buy check. In estimate-only mode the verdict is only ever estimate_only or nothing_to_buy, so a "refused" verdict (sonnet's framing) cannot arrive; the one true case is a space reason appended to reasons, which yields a misleading ceiling command. The real pass still guards space, so this is misleading operator narration, not wrong spending.

Evidence: `scripts/cutover_304_checks.py:225-226`, `scripts/cutover_304_first_purchase.py:269-276`, `src/manta_trading/data/tick/purchase_plan.py:304`

- [ ] agree   - [ ] disagree →

### 307-I5 · MINOR (high)
**--slice accepts any non-empty text and that text names the state files and log.**

Found by: haiku-xhigh ×2 · CONCERN ×2

_nonempty only strips; the value builds {slice}-cutover-start.txt, -baseline.json and the log name. True, but it is an operator-typed argument on the operator's own host; a mistyped id is operator error, not a defect a reviewer would block on.

Evidence: `scripts/cutover_304_first_purchase.py:99-104`, `scripts/cutover_304_first_purchase.py:201-205`, `scripts/cutover_304_first_purchase.py:224-226`

- [ ] agree   - [ ] disagree →

### 307-I7 · MINOR (medium)
**A reused baseline is not checked for the records key until evidence collection, after install and purchase.**

Found by: haiku-xhigh ×1 · CONCERN ×1

record_start_and_baselines returns an existing baseline as-is and only _baseline_records (in collect) raises "predates 307". Baselines are per slice, so the only way to hit it is re-running with an old slice id's files; an operator-misuse scenario.

Evidence: `scripts/cutover_304_first_purchase.py:107-111`, `scripts/cutover_304_evidence.py:237-241`

- [ ] agree   - [ ] disagree →

### 307-I8 · MINOR (high)
**Exit codes and the complete bucket are defined locally in cutover_304_evidence.py instead of imported.**

Found by: haiku-xhigh ×1 · CONCERN ×1

EXIT_OK, EXIT_PARTIAL = 0, 3 and COMPLETE are local while purchase_verdicts imports tick_exit; the EXIT line predates base and values match. Duplication only.

Evidence: `scripts/cutover_304_evidence.py:42`, `scripts/cutover_304_evidence.py:45`, `scripts/purchase_verdicts.py:25`

- [ ] agree   - [ ] disagree →

### 307-I9 · MINOR (high)
**Unit-test fixtures use verdicts ("allowed", "refused") the estimate-only producer never emits, and a resubmit branch is untested.**

Found by: haiku-xhigh ×1 · CONCERN ×1

test_cutover_304_checks builds summaries with verdict "allowed" and "refused"; real estimate-only output is estimate_only. This is why B2 escaped, but as a finding it is a test-fixture gap, not the defect itself (graded under I2).

Evidence: `test/unit/scripts/test_cutover_304_checks.py:80`, `test/unit/scripts/test_cutover_304_checks.py:107`

- [ ] agree   - [ ] disagree →

### 307-I6 · PREEXISTING (high)
**The configured type checker (mypy, files = src) does not cover the new scripts and tests.**

Found by: haiku-xhigh ×1 · CONCERN ×1

[tool.mypy] files = ["src/manta_trading"] and there is no pyright config; pyproject.toml is not changed in base..head. The coverage gap is in existing configuration.

Evidence: `pyproject.toml:72-75`

- [ ] agree   - [ ] disagree →

## 921

### 921-I1 · REAL (high) — known B3
**fire_unit_until starts the firing with the blocking `mt-run minute`, so the trailing-phase stop never runs until the unit has already ended.**

Found by: haiku-xhigh ×3, sol ×3, sonnet-high ×1 · FAIL ×7

fire_unit_until calls run(['mt-run', ...], stream=True) synchronously, and mt-run's start_and_stream loops `while is_running unit; sleep 2` before exiting. wait_for_unit_or_line only starts after the unit is inactive, so `reached and unit_active(unit)` can never be true and the stop never happens; the cutover waits for the whole unbounded pass. This is known bug B3, fixed later in f94c9e58.

Evidence: `scripts/cutover_common.py:356-360`, `deploy/mt-run:129`, `scripts/cutover_921_minute_sessions.py:180-182`

- [ ] agree   - [ ] disagree →

### 921-I2 · REAL (high) — known B1
**Judging per session makes any chunk with a genuinely empty session (no trades, halt) PARTIAL forever, so it is re-requested on every walk and never converges.**

Found by: haiku-xhigh ×1, sonnet-high ×1 · CONCERN ×2

judge_chunk_by_sessions returns PARTIAL whenever any closed session in the chunk has no bar in (open, close]. It cannot tell an unpublished session from one with no trades, so an illiquid or halted symbol's chunk stays open, increments attempt_count and is fetched again each cycle, spending quota. This is known bug B1, fixed in dc391881 with PROVIDER_HOLE and a publication-lag cutoff.

Evidence: `src/manta_trading/data/acquisition/daemon/minute_sessions.py:62`, `src/manta_trading/data/acquisition/daemon/minute_sessions.py:90`, `src/manta_trading/data/acquisition/daemon/minute.py:905-916`, `src/manta_trading/data/acquisition/daemon/minute.py:1142-1151`

- [ ] agree   - [ ] disagree →

### 921-I3 · REAL (medium)
**The NOPASSWD root rule runs install-production.sh from the operator's own writable checkout, which makes it root-equivalent despite the header's 'limited root' claim.**

Found by: haiku-xhigh ×3, sol ×3, sonnet ×3, sonnet-high ×3 · CONCERN ×5, FAIL ×7

MT_INSTALL names /home/manta/source/repos/manta/trading-data/deploy/install-production.sh, in the manta account's own checkout, and grants it to manta as root with NOPASSWD. Anyone with that account's shell can edit the script and run it as root without a password. The header says the grant is limited, so this is a real security hole. It is not merge-blocking on its own, because the account already holds password sudo (preflight runs `sudo -v`), and the rule still points at the checkout at HEAD.

Evidence: `deploy/sudoers.d/manta-ops:1-4`, `deploy/sudoers.d/manta-ops:9`, `deploy/sudoers.d/manta-ops:13`, `scripts/cutover_common.py:134-135`

- [ ] agree   - [ ] disagree →

### 921-I4 · REAL (medium)
**The sudoers wildcards (`systemctl ... mt-*`, `mt-run *`) also match whitespace and extra arguments, so they cover other units and the whole production mt CLI as root.**

Found by: haiku-xhigh ×1, sol ×1, sonnet ×1, sonnet-high ×1 · CONCERN ×3, FAIL ×1

A sudoers `*` in arguments matches any characters, including spaces, so `systemctl stop mt-x sshd.service` or `start mt-x <any unit>` matches MT_UNITS. Under sudo, mt-run's fall-through runs run_production_mt, whose `-r env_file` branch execs the production mt binary as root with arbitrary arguments, though the scripts only need four fixed invocations. That is wider than the header's 'nothing wider', and 635fa500 later pinned the units and dropped the wildcards. sonnet-high/3/1 says mt-run runs as manta-trading, but root reads the env file and takes the exec-as-root branch.

Evidence: `deploy/sudoers.d/manta-ops:7-8`, `deploy/mt-run:165-168`, `deploy/mt-run:197`

- [ ] agree   - [ ] disagree →

### 921-I5 · REAL (medium)
**The sudoers rule does not cover the cutover's `sudo /opt/manta-trading/.venv/bin/python scripts/repair_921_minute_sessions.py` calls, so repair and verify still prompt for a password mid-run.**

Found by: haiku-xhigh ×3, sonnet-high ×1 · CONCERN ×4

_repair runs the production interpreter under sudo for --check, --apply and every --verify poll, and no alias in manta-ops matches it. After a long firing, or across the 15-minute verify polls, sudo prompts again. If the prompt times out, the output carries no FAIL text, and the cutover's substring verdict would then pass. The header's 'exactly the commands those scripts issue' is false. A later HEAD runs the repair unprivileged because 'root added nothing but a password prompt'.

Evidence: `scripts/cutover_921_minute_sessions.py:96-100`, `deploy/sudoers.d/manta-ops:7-13`, `scripts/cutover_921_minute_sessions.py:200-212`

- [ ] agree   - [ ] disagree →

### 921-I6 · REAL (medium)
**The new narration log tees only `say` lines, so the repair/verify output (the acceptance numbers) never reaches the log file.**

Found by: haiku-xhigh ×3, sol ×2 · CONCERN ×4, FAIL ×1

start_log only makes say() append to the file, and _repair emits the captured repair output with a plain print(). The [PASS]/[FAIL]/[WAIT] lines that start_log's docstring calls 'the cutover's report' are therefore absent from the file, while the closing message tells the reader to 'read the FAIL lines'. The new feature fails its stated purpose. It was fixed as review finding F002 in 635fa500 (log_text). It does not block a merge, because the terminal still shows the output.

Evidence: `scripts/cutover_common.py:44-62`, `scripts/cutover_921_minute_sessions.py:101-102`, `scripts/cutover_921_minute_sessions.py:277`

- [ ] agree   - [ ] disagree →

### 921-I8 · REAL (low)
**Truncated days are passed to the seed only when seeding runs, and the frontier-only seed starts at MAX(gap_end), so truncated sessions behind a newer terminal row are never re-seeded.**

Found by: haiku-xhigh ×1, sol ×2 · CONCERN ×3

uncovered_days reaches compute_missing_minute_sessions only inside `if seed_from is not None`. With no UNKNOWN rows and a terminal row (for example a PROVIDER_HOLE or RETRY_EXHAUSTED for a recent session) newer than the truncated day, seed_from is the frontier, past the truncated day, or no seed runs at all. The truncation then stays silent, contrary to _build_truncated_index's docstring. The gating is unchanged at HEAD. How often that row state occurs in production is unverified, which is why confidence is low. It is not B2, which is the 7-day scan floor.

Evidence: `src/manta_trading/data/acquisition/daemon/minute.py:717-750`, `src/manta_trading/data/acquisition/daemon/minute.py:752-772`, `src/manta_trading/data/acquisition/daemon/minute.py:352-364`

- [ ] agree   - [ ] disagree →

### 921-I10 · FALSE (high)
**The claim that the probe's `job.hypertable_name = <view name>` join matches no row, so verify would WAIT forever.**

Found by: sonnet-high ×1 · CONCERN ×1

For a cagg refresh policy, timescaledb_information.jobs.hypertable_name carries the view name. The existing cagg_freshness._JOB_SQL and cagg_repair use the same predicate, and cagg_freshness documents it. The lookup finds the job.

Evidence: `src/manta_trading/data/gaps/repair_921.py:205`, `src/manta_trading/market/maintenance/cagg_freshness.py:82`, `src/manta_trading/market/maintenance/cagg_freshness.py:275`

- [ ] agree   - [ ] disagree →

### 921-I19 · FALSE (high)
**An extra pool connection is opened per chunk for fetch_session_bounds while another connection is held, risking pool exhaustion.**

Found by: sonnet ×1 · CONCERN ×1

No other connection is held at that point. The seed connection is returned at line 792, the gap-pick chunk_conn is closed by line 833, and the write connection opens after bounds_conn closes. The checkouts are sequential, not nested, so the exhaustion or deadlock claim cannot happen.

Evidence: `src/manta_trading/data/acquisition/daemon/minute.py:792`, `src/manta_trading/data/acquisition/daemon/minute.py:823-833`, `src/manta_trading/data/acquisition/daemon/minute.py:901-904`, `src/manta_trading/data/acquisition/daemon/minute.py:923`

- [ ] agree   - [ ] disagree →

### 921-I11 · MINOR (medium)
**The cagg freshness probe re-implements the existing refresh-job lookup and drops its '-infinity' normalization and scheduled/last_run_status signals.**

Found by: haiku-xhigh ×3 · CONCERN ×3

True duplication of cagg_freshness._read_refresh_job/_JOB_SQL. The missing nullif('-infinity') only matters for a policy that has never completed, which minute_4hour_ohlcv in production is not. A paused or failing job only makes verify WAIT for the bounded 5 polls and then report incomplete. That is a DRY point plus speculative hardening.

Evidence: `src/manta_trading/data/gaps/repair_921.py:196-209`, `src/manta_trading/market/maintenance/cagg_freshness.py:68-83`

- [ ] agree   - [ ] disagree →

### 921-I12 · MINOR (medium)
**The 04:05 UTC firing rationale assumes 20:00 ET = 00:00 UTC, which leaves only about five minutes of margin in standard time.**

Found by: haiku-xhigh ×2 · CONCERN ×2

The docstring's arithmetic holds only under EDT. In EST, 20:00 ET is 01:00 UTC, and the provider's 2-3 h upper bound is 04:00 UTC. The comment is wrong half the year and the margin is thin. A firing that misses publication only keeps the row and retries at 13:05, so the cost is a delay, not data loss.

Evidence: `src/manta_trading/constants.py:150-165`, `deploy/systemd/mt-minute-pass.timer:8`

- [ ] agree   - [ ] disagree →

### 921-I13 · MINOR (high)
**The mt-minute-pass.timer comment still says the minute pass is staggered 30 minutes behind the daily pass.**

Found by: haiku-xhigh ×1, sonnet ×2 · CONCERN ×3

The daily timer fires at 00:35/12:35, and the minute timer now fires at 04:05/13:05, so only the 13:05 firing is 30 minutes behind. This is a stale comment with no behavior impact. It was corrected in 635fa500.

Evidence: `deploy/systemd/mt-minute-pass.timer:6-8`, `deploy/systemd/mt-daily-pass.timer`

- [ ] agree   - [ ] disagree →

### 921-I14 · MINOR (high)
**Import blocks added by the diff are out of isort order and fail the enabled ruff `I` rule.**

Found by: sonnet ×3, sonnet-high ×3 · CONCERN ×6

pyproject selects `I`, and ruff reports I001 on the new cutover_921 import block (line 45), which base did not have, and on minute.py, where new imports were placed out of order (that file and repair_921.py already failed I001 at base). This is lint and style only.

Evidence: `pyproject.toml:63`, `scripts/cutover_921_minute_sessions.py:45-52`, `src/manta_trading/data/acquisition/daemon/minute.py:50-68`

- [ ] agree   - [ ] disagree →

### 921-I15 · MINOR (high)
**The verdict markers '[WAIT]' and 'FAIL' are bare string literals matched across two scripts.**

Found by: haiku-xhigh ×1, sonnet-high ×2 · CONCERN ×3

'[WAIT]' is printed in the repair script and substring-matched three times in the cutover. That breaks the project's single-definition rule, but the code works as written today. It is a maintainability point.

Evidence: `scripts/repair_921_minute_sessions.py:288`, `scripts/cutover_921_minute_sessions.py:204`, `scripts/cutover_921_minute_sessions.py:265`, `scripts/cutover_921_minute_sessions.py:273`

- [ ] agree   - [ ] disagree →

### 921-I16 · MINOR (high)
**The new daemon tests copy-paste heavy mock scaffolding instead of reusing `_run`.**

Found by: sonnet ×2, sonnet-high ×2 · CONCERN ×4

Test-code duplication and log-string assertions in test_minute.py. These are test-quality points with no production behavior impact.

Evidence: `test/unit/data/acquisition/daemon/test_minute.py:2339-2470`

- [ ] agree   - [ ] disagree →

### 921-I17 · MINOR (high)
**The production daemon now imports the one-off slice-921 repair module.**

Found by: haiku-xhigh ×1, sonnet-high ×2 · CONCERN ×3

minute.py imports build_truncated_day_index and RepairScanTimeout from data/gaps/repair_921.py. That is true, but it is a module-placement and architecture point with no behavioral defect.

Evidence: `src/manta_trading/data/acquisition/daemon/minute.py:60-63`

- [ ] agree   - [ ] disagree →

### 921-I18 · MINOR (high)
**fire_unit_until duplicates fire_unit's cursor/run/wait/sudo -v shape.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The two functions share most of their body, and wait_for_unit_or_line repeats the poll loop. This is a DRY point. The blocking bug is graded separately as I1.

Evidence: `scripts/cutover_common.py:341-383`

- [ ] agree   - [ ] disagree →

### 921-I20 · MINOR (high)
**Each minute chunk now pays an extra connection checkout and session-bounds query.**

Found by: sonnet-high ×1 · CONCERN ×1

True: bounds_conn plus fetch_session_bounds run once per chunk. But each chunk already makes a 5-credit HTTP call and a write transaction, so one indexed query has no meaningful effect. The finding's side note about empty sessions exhausting retries is B1 (I2).

Evidence: `src/manta_trading/data/acquisition/daemon/minute.py:901-904`

- [ ] agree   - [ ] disagree →

### 921-I21 · MINOR (medium)
**Ctrl-C during a firing aborts the cutover script and releases the timers, despite the printed 'Ctrl-C only detaches, the script keeps waiting'.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The Python process is in the foreground process group with no SIGINT handler, so Ctrl-C raises KeyboardInterrupt out of subprocess.run, and main()'s finally restarts the timers. The new fire_unit_until copies the misleading message from the pre-existing fire/fire_unit. The abort is visible to the operator and the running unit is unaffected, so the cost is a misleading message and a lost supervised run, not wrong data.

Evidence: `scripts/cutover_common.py:352-356`, `scripts/cutover_921_minute_sessions.py:274-275`

- [ ] agree   - [ ] disagree →

### 921-I22 · MINOR (medium)
**The cutover loop fires another minute pass when verify is still WAIT after its polls.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The loop breaks only on neither FAIL nor WAIT, so a WAIT that persists after the five 15-minute polls triggers another firing. With an hourly refresh, the 75-minute polling window spans a refresh, so a persistent WAIT needs an abnormal cagg state (a paused or failing policy). The point is true but limited to that edge.

Evidence: `scripts/cutover_921_minute_sessions.py:200-212`, `scripts/cutover_921_minute_sessions.py:259-269`

- [ ] agree   - [ ] disagree →

### 921-I23 · MINOR (high)
**The narration log is created relative to the cwd before preflight checks the working directory.**

Found by: sonnet-high ×1 · CONCERN ×1

start_log(NOTES_DIR/...) runs before preflight(), and NOTES_DIR is relative, so running from the wrong directory leaves a stray notes directory and log before the CutoverError. That is harmless clutter.

Evidence: `scripts/cutover_921_minute_sessions.py:226-232`, `scripts/cutover_common.py:32`, `scripts/cutover_common.py:95`

- [ ] agree   - [ ] disagree →

### 921-I24 · MINOR (high)
**start_log truncates an existing file, and an OSError while writing the log would crash the cutover.**

Found by: sonnet ×1 · CONCERN ×1

write_text does truncate, but the file name is timestamped to the second, so no collision occurs in practice. An OSError while appending is speculative. This is hardening against inputs that do not arrive.

Evidence: `scripts/cutover_common.py:44-62`, `scripts/cutover_921_minute_sessions.py:226-228`

- [ ] agree   - [ ] disagree →

### 921-I9 · MINOR (medium)
**The cagg freshness probe compares the refresh's finish time with bar created_at, so a refresh that started before the last bars were written reads as fresh.**

Found by: sonnet ×1, sonnet-high ×2 · CONCERN ×3

stale is `last_successful_finish < max(created_at)`, and created_at defaults to NOW() (transaction start), so bars committed during a refresh run can be missed while the probe says fresh. The race is real, but it can only undercount the session mass, which biases toward a spurious FAIL or one more poll and firing, never a false pass. The window is the refresh duration. This is low-value hardening rather than a merge blocker.

Evidence: `src/manta_trading/data/gaps/repair_921.py:174-179`, `src/manta_trading/data/gaps/repair_921.py:201`, `src/manta_trading/data/gaps/repair_921.py:213`

- [ ] agree   - [ ] disagree →

### 921-I7 · PREEXISTING (medium)
**Acceptance is decided by the absence of 'FAIL'/'[WAIT]' text and ignores the exit code, so a crashed or refused verify counts as passing.**

Found by: haiku-xhigh ×1 · FAIL ×1

The claim is true: `scan refused` on exit 2, or a traceback, contains no 'FAIL', and _repair only narrates the return code. But `ok = "FAIL" not in report` and the matching loop check were already in base. The diff only added the `[WAIT]` clause, and the defect (a missing verdict reads as a pass) is unchanged by it.

Evidence: `scripts/cutover_921_minute_sessions.py:103-105`, `scripts/cutover_921_minute_sessions.py:265`, `scripts/cutover_921_minute_sessions.py:273`, `scripts/repair_921_minute_sessions.py:342`

- [ ] agree   - [ ] disagree →

## 932

### 932-I1 · REAL (high) — known B1
**Dispatch returns once the ledger is empty after its own result, losing the follow-up turn when the task notification arrived before that result.**

Found by: sol ×3 · FAIL ×3

_collect_turns returns as soon as own_result_seen is true and the ledger is empty. BackgroundLedger.observe drops a task on its TaskNotificationMessage, so a notification that lands mid-turn, before the human-origin result, empties the ledger and the dispatch returns without reading the parent continuation the notification triggers. That continuation is then discarded as leftover by the next dispatch. This is the known B1 defect, fixed later in 5e384226 (#239) by ending on the CLI idle state.

Evidence: `src/squadron/pipeline/sdk_session.py:252`, `src/squadron/pipeline/sdk_turns.py:61-65`, `src/squadron/pipeline/sdk_session.py:243-251`

- [ ] agree   - [ ] disagree →

### 932-I2 · REAL (medium)
**The background idle timer stays applied to the parent's foreground continuation after the last background task finishes.**

Found by: sol ×3 · FAIL ×3

When turns.waiting is true, _collect_turns passes idle_s into _read_turn, which applies asyncio.timeout(idle_s) to every message wait until the next ResultMessage. A notification that clears the ledger mid-pass does not lift it, so the follow-up foreground turn runs under the background timer, contrary to the stated 'foreground turns get no timer (#165)' policy. On expiry _stop_background stops nothing and dispatch returns partial text as success. The 1800 s default makes it rare (needs a single silent gap that long), so it does not block merge.

Evidence: `src/squadron/pipeline/sdk_session.py:219-229`, `src/squadron/pipeline/sdk_session.py:298-301`, `src/squadron/pipeline/sdk_session.py:329-349`

- [ ] agree   - [ ] disagree →

### 932-I10 · MINOR (high)
**The pipeline settings policy and its config key literals are wired separately in one-shot dispatch and open_pipeline_session.**

Found by: haiku-xhigh ×1, sonnet-high ×1 · CONCERN ×2

Both sites read pipeline.user_settings and pipeline.auto_memory by literal and call pipeline_setting_sources. True duplication of two short lines; both currently agree, so this is DRY hygiene.

Evidence: `src/squadron/pipeline/actions/dispatch.py:143-153`, `src/squadron/pipeline/sdk_session.py:455-461`

- [ ] agree   - [ ] disagree →

### 932-I11 · MINOR (high)
**The session dispatch path builds the system_prompt_mode/setting_sources/auto_memory metadata keys by hand instead of reusing describe_run_settings.**

Found by: haiku-xhigh ×1 · CONCERN ×1

_dispatch_via_session writes the three keys literally while the one-shot path uses describe_run_settings. The two agree today; drift risk only.

Evidence: `src/squadron/pipeline/actions/dispatch.py:370-375`, `src/squadron/core/models.py:125-131`

- [ ] agree   - [ ] disagree →

### 932-I12 · MINOR (medium)
**_stop_background catches bare Exception and continues.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The catch logs with logger.exception and carries a comment explaining that the SDK raises bare Exception for stop failures, so no narrower type exists. The failure is observable; the point is a strict reading of the exception rule.

Evidence: `src/squadron/pipeline/sdk_session.py:334-341`

- [ ] agree   - [ ] disagree →

### 932-I13 · MINOR (high)
**ReviewTemplate.setting_sources is typed non-optional but nothing outside the loader rejects None, and test fixtures pass None.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The dataclass has no __post_init__ and tests such as test_review_client.py:35 build templates with setting_sources=None. Production builds templates only through load_template, which resolves None to REVIEW_SETTING_SOURCES, so no production path yields None.

Evidence: `src/squadron/review/templates/__init__.py:35-36`, `src/squadron/review/templates/__init__.py:97-107`, `tests/review/test_review_client.py:35`

- [ ] agree   - [ ] disagree →

### 932-I14 · MINOR (high)
**Idle-timeout tests rely on short wall-clock sleeps.**

Found by: sonnet ×1 · CONCERN ×1

The tests patch the timeout to 0.05 s against 0.15 s sleeps; a 3x margin is a flake risk on loaded CI, not a code defect.

Evidence: `tests/pipeline/test_sdk_session.py`

- [ ] agree   - [ ] disagree →

### 932-I15 · MINOR (high)
**A pyright ignore hides the list[str] vs SettingSource literal mismatch at the ClaudeAgentOptions boundary.**

Found by: sonnet ×1 · CONCERN ×1

open_pipeline_session passes settings['setting_sources'] with # pyright: ignore[reportArgumentType]. The values are valid literals, so this is typing hygiene.

Evidence: `src/squadron/pipeline/sdk_session.py:466`

- [ ] agree   - [ ] disagree →

### 932-I16 · MINOR (low)
**One-shot dispatch reads pipeline config from the caller's cwd while the SDK agent runs in the process cwd and the session reads from Path.cwd().**

Found by: sonnet ×1 · CONCERN ×1

one_shot_dispatch_with_telemetry reads config at cwd or '.', while the SDK AgentConfig gets cwd=None, and open_pipeline_session reads at Path.cwd(). The mismatch is real but only matters when a caller passes a cwd whose .squadron.toml differs; reading the target project's config is arguably intended.

Evidence: `src/squadron/pipeline/actions/dispatch.py:143`, `src/squadron/pipeline/actions/dispatch.py:164`, `src/squadron/pipeline/sdk_session.py:455`

- [ ] agree   - [ ] disagree →

### 932-I17 · MINOR (high)
**SystemPromptMode docstring refers to 'the table above', which is a comment in a different class.**

Found by: sonnet ×1 · CONCERN ×1

The table is the comment on AgentConfig.use_default_system_prompt about 40 lines earlier; the docstring wording is imprecise. Comment-only.

Evidence: `src/squadron/core/models.py:54`, `src/squadron/core/models.py:93`

- [ ] agree   - [ ] disagree →

### 932-I18 · MINOR (high)
**ReviewResult comment says unreported values render as 'not reported' but they render as 'not computed'.**

Found by: sonnet-high ×1 · CONCERN ×1

_render_optional returns the shared _NOT_COMPUTED sentinel ('not computed') and the new test asserts that; the comment in review/models.py is wrong. Comment-only.

Evidence: `src/squadron/review/models.py:213-216`, `src/squadron/review/persistence.py:199`, `src/squadron/review/persistence.py:317`

- [ ] agree   - [ ] disagree →

### 932-I19 · MINOR (medium)
**except TimeoutError in _collect_turns would treat any TimeoutError from the read as a background idle timeout.**

Found by: sonnet-high ×1 · CONCERN ×1

The handler wraps the whole _read_turn_with_retry call, so a TimeoutError raised from inside the SDK stream would be handled as idle. No source of such a TimeoutError in the read path is shown, so this is speculative hardening; it was later narrowed in f0d6b5db, and the case notes count it as unrelated to B1.

Evidence: `src/squadron/pipeline/sdk_session.py:225-229`, `src/squadron/pipeline/sdk_session.py:299-303`

- [ ] agree   - [ ] disagree →

### 932-I3 · MINOR (medium)
**set_model is not guarded by _require_usable, so after a failed reconnect the next step fails with 'Not connected' instead of the recorded unusable reason.**

Found by: haiku-xhigh ×2, sol ×1 · CONCERN ×3

_reconnect resets current_model to None, and _dispatch_via_session calls session.set_model before dispatch, so set_model always reaches the unconnected client, whose SDK set_model raises CLIConnectionError('Not connected. Call connect() first.'). DispatchAction.execute still turns that into a failed step, so later items still fail and never query; only the error text differs from the D13 design, and the real cause is logged on the first item. The batch test passes only because ScriptedClient.set_model is an AsyncMock.

Evidence: `src/squadron/pipeline/sdk_session.py:168-179`, `src/squadron/pipeline/sdk_session.py:418-437`, `src/squadron/pipeline/actions/dispatch.py:353`, `src/squadron/pipeline/actions/dispatch.py:251-258`

- [ ] agree   - [ ] disagree →

### 932-I4 · MINOR (high)
**background_tasks_stopped and the warning count every id as stopped even when stop_task failed.**

Found by: haiku-xhigh ×2 · CONCERN ×2

_stop_background logs each failed stop_task at ERROR and continues, then sets background_tasks_stopped = len(ids) and names every description as stopped. The claim is true, but each failure is already logged with a traceback, so this is an inaccurate metadata count rather than a silent failure.

Evidence: `src/squadron/pipeline/sdk_session.py:333-349`

- [ ] agree   - [ ] disagree →

### 932-I5 · MINOR (medium)
**pipeline.background_idle_timeout_s accepts zero, negative and boolean values with no range check.**

Found by: haiku-xhigh ×2, sonnet ×1, sonnet-high ×1 · CONCERN ×4

The new key is a plain int; _coerce_value does int(raw) and get_typed_config's int branch accepts any int including bool. A value of 0 or below makes asyncio.timeout fire at once and stop agents. True, but it needs a user to deliberately set a nonsensical value, so it is hardening rather than a defect on any normal input.

Evidence: `src/squadron/config/keys.py:118-127`, `src/squadron/config/manager.py:75-76`, `src/squadron/config/manager.py:134-137`, `src/squadron/pipeline/sdk_session.py:323-327`

- [ ] agree   - [ ] disagree →

### 932-I6 · MINOR (high)
**New get_typed_config calls read TOML synchronously inside async session and dispatch code instead of being resolved once at a composition root.**

Found by: haiku-xhigh ×3, sonnet-high ×1 · CONCERN ×4

one_shot_dispatch_with_telemetry, open_pipeline_session and _background_idle_timeout_s do call get_typed_config, which reads two small TOML files synchronously. The cost is negligible and runs once per dispatch or session; the copytree migration is a one-time pre-existing path. This is a rule/architecture point with no real behavioral effect.

Evidence: `src/squadron/pipeline/actions/dispatch.py:143-153`, `src/squadron/pipeline/sdk_session.py:455-461`, `src/squadron/pipeline/sdk_session.py:323-327`

- [ ] agree   - [ ] disagree →

### 932-I7 · MINOR (high)
**No tests/load/ test covers the new background-wait and idle-timeout path.**

Found by: haiku-xhigh ×3 · CONCERN ×3

True that the diff adds no load test, but the path is covered by unit tests and the missing load test is a process point, not a defect in the code.

Evidence: `tests/pipeline/test_sdk_session.py`

- [ ] agree   - [ ] disagree →

### 932-I8 · MINOR (high)
**sdk_session.py is about 470 lines and mixes lifecycle with turn reading.**

Found by: haiku-xhigh ×3, sonnet-high ×1 · CONCERN ×4

The file is 472 lines at head against a ~300-line guideline, and the read loop lives in the session class. Structure only; no behavioral effect.

Evidence: `src/squadron/pipeline/sdk_session.py:1-472`

- [ ] agree   - [ ] disagree →

### 932-I9 · MINOR (high)
**New test helpers are annotated -> object, forcing many type-ignore comments.**

Found by: haiku-xhigh ×1, sonnet ×1, sonnet-high ×2 · CONCERN ×3, FAIL ×1

scripted_session, the sdk_* builders, failing_reconnect_patch and typed_config return object, and the tests carry many ignores. The FAIL member's claim that this breaks the strict pyright gate is wrong: pyproject.toml sets include = ["src"], so tests are not type-checked. Test typing quality only.

Evidence: `tests/pipeline/conftest.py:208-238`, `pyproject.toml:94`

- [ ] agree   - [ ] disagree →

## a122

### a122-I1 · REAL (high)
**The one RunObserver shared by all projects prunes its poll, overdue and fault state to the current project's entries, so each project's tick erases the others'.**

Found by: haiku-xhigh ×3, sol ×3 · CONCERN ×1, FAIL ×5

RunnerTenant builds a single RunObserver and passes it to every ProjectTick, and observe() filters _last_poll, _overdue and _faulted to the ids of the entries it was given, which are only the current project's. With two or more hosted projects every run loses its last-poll time each tick, so it is polled every tick instead of once per run_poll_interval_seconds, and standing faults and overdue markers are dropped. The author removed the pruning in 8736ea5 ('address slice 122 code review findings') with a comment that the observer is shared by every project.

Evidence: `src/amoeba/runner/tenant.py:74`, `src/amoeba/runner/tenant.py:133`, `src/amoeba/runner/observe.py:108-111`, `src/amoeba/runner/tick.py:114-119`

- [ ] agree   - [ ] disagree →

### a122-I13 · REAL (medium)
**escalate() reads entry.parameters[PARAM_RUN_ID] unguarded, so an in-flight sq_run entry with no run_id raises KeyError inside the last-resort fault handler.**

Found by: sonnet-high ×1 · CONCERN ×1

_in_flight_run_ids indexes parameters[PARAM_RUN_ID] directly. The codebase at head treats sq_run entries journaled before slice 120, which have no run_id, as a real case (sq_run_id.py routes them to a legacy matcher). For such an entry, observe raises ValueError, the tenant's broad catch calls escalate, and the KeyError escapes the except block. That takes down the whole process instead of isolating one project. The author changed it to .get(PARAM_RUN_ID, entry.id) for legacy entries in 8736ea5. Confidence is medium because it depends on an unresolved pre-120 entry surviving recovery.

Evidence: `src/amoeba/runner/faults.py:194-199`, `src/amoeba/runner/tenant.py:145-148`, `src/amoeba/process/observers/sq_run_id.py:14`

- [ ] agree   - [ ] disagree →

### a122-I2 · REAL (medium)
**An unconfirmed launch whose poll failed does not replay the stored fault on ticks between polls, so the run_observation_failed escalation closes and reopens.**

Found by: haiku-xhigh ×3, sol ×3 · CONCERN ×6

_after_launch_poll stores a PollFailure in _faulted via _fault, but _unconfirmed never reads _faulted. On the next tick, with the poll not due, it calls _still_overdue, which adds a fault only for ids in _overdue (a PollFailure never adds one) and returns LAUNCHING. _close_recovered then closes the run_observation_failed escalation because the kind did not recur, and the next poll reopens it. The comment at observe.py:92-93 and the D8 closure rule say a standing fault must not look recovered, and _confirmed does replay it.

Evidence: `src/amoeba/runner/observe.py:92-94`, `src/amoeba/runner/observe.py:140-145`, `src/amoeba/runner/observe.py:186-187`, `src/amoeba/runner/observe.py:233-234`, `src/amoeba/runner/observe.py:260`, `src/amoeba/runner/tick.py:194-200`

- [ ] agree   - [ ] disagree →

### a122-I3 · REAL (high) — known B2
**The tenant's broad catch always returns (COMPLETE, True), so a fault that recurs every tick reports work and the host loop never idles.**

Found by: haiku-xhigh ×2, sol ×1 · CONCERN ×2, FAIL ×1

After logging and escalate(), _tick_project returns TickResult.COMPLETE, True unconditionally, even when escalate wrote nothing (node already blocked, or the project escalation is already open and deduplicated). RunnerTenant.tick returns that True, contradicting its own docstring, and the host skips its idle wait when a tenant reports work, so a persistent fault spins with a traceback per pass. This is the case's known bug B2, fixed later in 43ba517.

Evidence: `src/amoeba/runner/tenant.py:93-100`, `src/amoeba/runner/tenant.py:145-149`, `src/amoeba/runner/faults.py:171-191`

- [ ] agree   - [ ] disagree →

### a122-I19 · FALSE (high)
**tenant.py:145 is over 88 characters and would fail ruff E501.**

Found by: sonnet ×1 · CONCERN ×1

The line is 91 characters, but running ruff 0.17.2 with the repo's own pyproject.toml config (line-length 88, select E) on tenant.py at head gives 'All checks passed!', because ruff leaves a trailing noqa pragma out of the line-length count. The claimed lint failure does not happen.

Evidence: `src/amoeba/runner/tenant.py:145`, `pyproject.toml:36-43`

- [ ] agree   - [ ] disagree →

### a122-I10 · MINOR (high)
**LaunchTracker.confirm is never called from production code; the observer sets tracked.confirmed directly.**

Found by: haiku-xhigh ×1, sonnet-high ×1 · CONCERN ×2

git grep finds .confirm( only in tests, and RunObserver._confirm writes tracked.confirmed = True directly. Both paths set the same flag, so behavior is correct. This is a dead-code and encapsulation point.

Evidence: `src/amoeba/runner/launch.py:257-259`, `src/amoeba/runner/observe.py:275-277`

- [ ] agree   - [ ] disagree →

### a122-I11 · MINOR (high)
**faults.py's docstring says escalation writes come in a later task, but the module already contains them.**

Found by: haiku-xhigh ×2 · CONCERN ×2

faults.py:4 says 'Escalation writes join this module in a later task.', but raise_expected_faults and escalate are defined in the same file. Only the docstring is stale.

Evidence: `src/amoeba/runner/faults.py:3-4`, `src/amoeba/runner/faults.py:120`, `src/amoeba/runner/faults.py:152`

- [ ] agree   - [ ] disagree →

### a122-I12 · MINOR (high)
**The check that a journal entry has a usable run_id is written separately in observe, finish and launch, with slightly different rules.**

Found by: haiku-xhigh ×1, sonnet ×1, sonnet-high ×1 · CONCERN ×3

observe._observe_one rejects a non-string or empty id, finish._run_id rejects only a non-string, and launch._text_parameter rejects both. journal_issue requires run_id and the Runner always writes a minted string, so the differences do not change behavior for entries the Runner creates. This is a DRY point.

Evidence: `src/amoeba/runner/observe.py:127-129`, `src/amoeba/runner/finish.py:141-145`, `src/amoeba/runner/launch.py:166-170`

- [ ] agree   - [ ] disagree →

### a122-I14 · MINOR (medium)
**probe_link quotes only stdout on a non-zero cf exit, so a cf error reported on stderr leaves the fault detail with no reason.**

Found by: haiku-xhigh ×1 · CONCERN ×1

probes.py:131-133 builds the failure detail from completed.stdout only, even though stderr is captured. The probe still fails and escalates correctly, so detection is unaffected. Only the operator-facing diagnostic text is thinner.

Evidence: `src/amoeba/runner/probes.py:131-133`

- [ ] agree   - [ ] disagree →

### a122-I15 · MINOR (medium)
**Any exit 2 from sq run with no run state is classified as a missing shape and stops the whole process.**

Found by: haiku-xhigh ×1 · CONCERN ×1

observe.py:243-247 classifies by exit code alone, and tick.py raises UpstreamShapeError, which the tenant re-raises. The slice design (line 267 and success criterion 426) specifies exactly this: exit 2 with no state means a missing shape and exits with UPSTREAM_SHAPE. The message includes the stderr tail. This questions the design choice and is not a deviation from it.

Evidence: `src/amoeba/runner/observe.py:243-247`, `src/amoeba/runner/tick.py:132-140`

- [ ] agree   - [ ] disagree →

### a122-I16 · MINOR (medium)
**launch() can raise ValueError after the entry is journaled, leaving an untracked entry that is later recorded as vanished rather than as a launch failure.**

Found by: sonnet ×1 · CONCERN ×1

launch() validates the journaled parameters after journal_issue. But _launch writes them itself from a typed LaunchRun: str(Path) is never empty, params were already checked by build_argv, and run_id is freshly minted. Only an empty pipeline from a planner could trigger it, and production planners are empty at head. The consequence would be a misleading 'vanished' reason, not a lost entry. This is speculative hardening.

Evidence: `src/amoeba/runner/tick.py:170-192`, `src/amoeba/runner/launch.py:186-208`

- [ ] agree   - [ ] disagree →

### a122-I17 · MINOR (high)
**observe.py is 326 lines, over the ~300-line guideline, and mixes the confirmed and unconfirmed state machines.**

Found by: sonnet ×2 · CONCERN ×2

The diffstat shows observe.py at 326 added lines. This is a structure and style point with no behavioral effect.

Evidence: `src/amoeba/runner/observe.py`

- [ ] agree   - [ ] disagree →

### a122-I18 · MINOR (high)
**validate_settings reads fields by string name with getattr and does not check launch_grace_seconds.**

Found by: sonnet ×2 · CONCERN ×2

factory.py:38-45 iterates string names through getattr, so pyright cannot check a renamed field, and launch_grace_seconds is not bounded. A negative grace would require an operator to pass a bad flag. The getattr loop was replaced with direct attribute pairs in 8736ea5. This is type-safety hardening.

Evidence: `src/amoeba/runner/factory.py:30-51`

- [ ] agree   - [ ] disagree →

### a122-I20 · MINOR (high)
**The single-broad-except test counts a substring in source text, and the tenant and factory tests read private attributes.**

Found by: sonnet ×1 · CONCERN ×1

test_the_runner_package_has_exactly_one_broad_except counts 'except Exception' in file text, and the tests read tenant._tracker and tenant._planners with pyright ignores. These are test-quality points with no production effect.

Evidence: `tests/runner/test_tenant.py:190-196`, `tests/runner/test_factory.py:88`

- [ ] agree   - [ ] disagree →

### a122-I21 · MINOR (high)
**test_budget_coverage imports the private helper _link from another test module.**

Found by: sonnet ×1 · CONCERN ×1

test_budget_coverage.py:18 imports _link from runner.test_probes with a reportPrivateUsage ignore. This only affects how the tests are organized.

Evidence: `tests/runner/test_budget_coverage.py:18`

- [ ] agree   - [ ] disagree →

### a122-I22 · MINOR (high)
**The crash harness uses type-ignores and replaces Store.journal_resolve at runtime.**

Found by: sonnet ×1 · CONCERN ×1

crash_entry.py carries several type: ignore comments and assigns Store.journal_resolve inside a throwaway subprocess. It is test-only code and has no production effect.

Evidence: `tests/runner/crash_entry.py:97-123`, `tests/runner/crash_entry.py:161-163`

- [ ] agree   - [ ] disagree →

### a122-I23 · MINOR (medium)
**_close_recovered closes an unexpected_fault project escalation on the next complete tick, because that kind never enters TickFaults.**

Found by: sonnet-high ×1 · CONCERN ×1

This is true: escalate writes unexpected_fault directly and never into TickFaults, so the next complete tick closes it. The slice design's closure rule (line 297, criterion 429) closes every open project escalation whose kind did not recur. A recurring exception aborts the tick before close, so the escalation stays open while the fault persists. The behavior matches the spec, and the finding is a design preference.

Evidence: `src/amoeba/runner/tick.py:194-200`, `src/amoeba/runner/faults.py:183-191`

- [ ] agree   - [ ] disagree →

### a122-I4 · MINOR (medium)
**The budget is checked before journaling, not again immediately before Popen, so a launch can start after the deadline or a stop request.**

Found by: sol ×3 · CONCERN ×1, FAIL ×2

_act calls budget.allows_call() and then _launch does journal_issue (one SQLite commit) and launch() with no second check, so the claim is literally true. The window is a single local write, and the budget only bounds when a call may begin. Re-checking after journaling would leave a journaled but never-launched entry, which is worse than finishing the launch; a detached child after a stop is reconciled by recovery. This is hardening with no real effect.

Evidence: `src/amoeba/runner/tick.py:161-192`, `src/amoeba/runner/budget.py:28-51`

- [ ] agree   - [ ] disagree →

### a122-I5 · MINOR (high)
**The Runner has no load-tier test although the project's Python rules require one for concurrency and environment-layer code.**

Found by: haiku-xhigh ×3 · CONCERN ×2, FAIL ×1

No file under tests/load/ at head exercises the Runner, and python.md line 57 asks for a load test on such paths. That is a missing test and a rules-compliance point, not a defect in the code itself; the author added tests/load/test_runner_tick_load.py later in 8736ea5. It does not by itself block a merge.

Evidence: `project-documents/ai-project-guide/project-guides/rules/python.md:57`, `src/amoeba/runner/tenant.py:93`

- [ ] agree   - [ ] disagree →

### a122-I6 · MINOR (medium)
**raise_expected_faults keeps only the first fault's payload per (project, kind), so later faults of the same kind lose their details.**

Found by: haiku-xhigh ×2 · CONCERN ×2

raise_expected_faults calls raise_project_escalation once per fault, and the store (from slice 121, unchanged here) returns an already-open (project, kind) row without changing it, so a second subject's detail is not stored. The slice design says escalations are deduplicated on (project, kind), so this is the intended trade-off. What is lost is detail the operator would see, not a fault that goes unreported. The point about one write transaction per tick is performance with no real effect.

Evidence: `src/amoeba/runner/faults.py:120-143`

- [ ] agree   - [ ] disagree →

### a122-I7 · MINOR (high)
**The tenant re-raises store and upstream-shape errors without logging with logger.exception first.**

Found by: haiku-xhigh ×2 · CONCERN ×2

tenant.py:142-144 is a bare re-raise with no log. The errors reach the CLI's process-boundary handlers, which print a message, so nothing fails silently. This is compliance with the project's exception-handling rule, not wrong behavior.

Evidence: `src/amoeba/runner/tenant.py:142-144`

- [ ] agree   - [ ] disagree →

### a122-I8 · MINOR (high)
**The per-project broad catch is not at a process boundary as the project's exception rule words it.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The except Exception at tenant.py:145 isolates one project, logs with logger.exception and escalates. This per-project isolation is a deliberate design (slice 122 D8, line 436), not a silent swallow. The finding is about how the rule is worded, not about a defect.

Evidence: `src/amoeba/runner/tenant.py:145-149`

- [ ] agree   - [ ] disagree →

### a122-I9 · MINOR (high)
**The journal parameter keys 'pipeline' and 'params' are defined again in launch.py, alongside the existing sq_runs.py constants and the store's literals.**

Found by: haiku-xhigh ×1 · CONCERN ×1

launch.py:121-122 adds PARAM_PIPELINE and PARAM_PARAMS, which duplicate the constants already in sq_runs.py (present at base) and the literals in REQUIRED_PARAMETER_KEYS. All of them have the same values today, so behavior is unaffected. This is a DRY point.

Evidence: `src/amoeba/runner/launch.py:121-122`, `src/amoeba/process/observers/sq_runs.py:42-43`, `src/amoeba/store/journal_models.py:85-88`

- [ ] agree   - [ ] disagree →

## u103

### u103-I1 · REAL (high) — known B1
**The visible-range effect gates on a ref, so a series added after the range settles never applies the range.**

Found by: haiku-xhigh ×3, sol ×3, sonnet ×3, sonnet-high ×3 · CONCERN ×12

The effect reads seriesCountRef.current but depends only on [mount.ready, chart, range]; the facade's addSeries only bumps the ref, so no re-run happens and the Context range is not applied until it changes. The translation test calls setRange after addSeries and hides it. This is known bug B1, fixed later in f0ebfb4 by mirroring the count into state; latent at head because the slice adds no series.

Evidence: `src/chart/use-chart-provider.ts:340-345`, `src/chart/use-chart-provider.ts:144-154`, `src/chart/chart-facade.ts:49-56`

- [ ] agree   - [ ] disagree →

### u103-I2 · REAL (medium)
**The series count is not a data-availability gate: an empty-data series or an updateSeries that clears data lets setVisibleRange run on an empty time scale.**

Found by: sol ×3 · CONCERN ×3

addSeries increments the count regardless of config.data length and updateSeries never touches it, so the guard passes with an empty time scale. lightweight-charts' logicalRangeForTimeRange calls ensureNotNull on timeToIndex, which throws 'Value is null', surfacing as a chart error through runGuarded. Latent in this slice (no series), like B1; later code (use-price-volume-series.ts header) works around exactly this by never holding an empty series.

Evidence: `src/chart/chart-facade.ts:49-64`, `src/chart/use-chart-provider.ts:341`, `node_modules/lightweight-charts/dist/lightweight-charts.development.mjs:6088-6092`

- [ ] agree   - [ ] disagree →

### u103-I3 · UNSURE (low)
**Removing a pane does not decrement the series count, so the count can drift above the real number of series.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The facade's removePane does not call series.onRemoved and the provider's removePane (pre-existing) only deletes the pane handle. Whether lightweight-charts drops the pane's series is not evident from model._internal_removePane, which only splices the pane; even if it does, the resulting setVisibleRange throw is surfaced as error state, not silent. Settle by adding a series to a second pane, removing the pane, and calling setVisibleRange in a browser.

Evidence: `src/chart/chart-facade.ts:78-80`, `src/chart/use-chart-provider.ts:149-151`

- [ ] agree   - [ ] disagree →

### u103-I10 · MINOR (high)
**The teardown-race tests pass whether or not the disposed guards exist.**

Found by: haiku-xhigh ×3 · CONCERN ×3

Because the handlers do nothing, asserting that a post-teardown callback calls nothing cannot fail. Test-quality issue on code that has no observable behavior to protect.

Evidence: `src/chart/use-chart-provider.ts:286-301`, `src/test/use-chart-provider.errors.test.tsx:255-271`

- [ ] agree   - [ ] disagree →

### u103-I11 · MINOR (high)
**Measured-rect and Host test scaffolding is duplicated across four hook test files.**

Found by: haiku-xhigh ×2, sonnet ×2, sonnet-high ×1 · CONCERN ×5

The helpers are repeated per test file while other test support was centralized. DRY in tests only.

Evidence: `src/test/use-chart-provider.errors.test.tsx:30-52`, `src/test/use-chart-provider.facade.test.tsx:33-60`

- [ ] agree   - [ ] disagree →

### u103-I12 · MINOR (high)
**The provider spy is not typed against IChartProvider, so interface drift would not break the tests.**

Found by: haiku-xhigh ×1 · CONCERN ×1

The spy's vi.fn signatures use `unknown` parameters and do not declare implements IChartProvider. Test typing hardening.

Evidence: `src/test/support/chart-provider-spy.ts:22-32`

- [ ] agree   - [ ] disagree →

### u103-I13 · MINOR (high)
**The initial resize uses the border box while the ResizeObserver reports the content box.**

Found by: haiku-xhigh ×1 · CONCERN ×1

getBoundingClientRect includes the section's 1px border; contentRect does not, so the first size is off by 2px until the observer fires. Transient and the finding itself calls it probably never painted.

Evidence: `src/chart/use-chart-provider.ts:249-250`, `src/chart/use-chart-provider.ts:257-268`, `src/routes/chart-route.tsx:88-93`

- [ ] agree   - [ ] disagree →

### u103-I14 · MINOR (medium)
**`error` is documented as the first operation error but setOperationError keeps the latest.**

Found by: haiku-xhigh ×2, sonnet ×1, sonnet-high ×1 · CONCERN ×4

setOperationError unconditionally replaces error, contradicting the doc at chart-operations.ts:77 and the test name. Which error is displayed is a doc/contract mismatch with negligible user impact; fixing the doc or adding `current.error ?? failure` are both trivial.

Evidence: `src/chart/use-chart-provider.ts:97-99`, `src/chart/chart-operations.ts:77`

- [ ] agree   - [ ] disagree →

### u103-I15 · MINOR (high)
**The hook constructs LightweightChartsProvider directly instead of taking an injected factory.**

Found by: haiku-xhigh ×1 · CONCERN ×1

True at line 173; tests use module mocking instead. A design/testability preference, not a defect.

Evidence: `src/chart/use-chart-provider.ts:173`

- [ ] agree   - [ ] disagree →

### u103-I16 · MINOR (high)
**Playwright now builds in e2e mode, so its header claim about testing the production artifact is false and nothing checks the harness is excluded from production.**

Found by: haiku-xhigh ×2 · CONCERN ×2

The webServer command uses `--mode e2e` while the header still says specs run the production artifact. Stale comment plus a missing guard test; no runtime defect.

Evidence: `playwright.config.ts:6-7`, `playwright.config.ts:44`

- [ ] agree   - [ ] disagree →

### u103-I17 · MINOR (medium)
**A failed create() leads teardown to call destroy() on an uncreated provider, logging a second misleading error.**

Found by: haiku-xhigh ×1, sonnet-high ×2 · CONCERN ×3

If createChart throws, provider.chart stays null and destroy() throws from assertReady; teardown catches it and logs 'provider teardown failed' after the real 'provider create failed'. The real failure is still logged first and committed as error state, so the result is log noise, not lost or wrong behavior.

Evidence: `src/chart/use-chart-provider.ts:216-222`, `src/chart/use-chart-provider.ts:302-309`, `src/chart/providers/lightweight-charts-provider.ts:67-86`

- [ ] agree   - [ ] disagree →

### u103-I18 · MINOR (high)
**The Context provider nesting is duplicated between App.tsx and the test wrapper.**

Found by: haiku-xhigh ×1 · CONCERN ×1

App and ChartContexts both nest SymbolTimeframeProvider around IndicatorProvider. Test-maintenance DRY point.

Evidence: `src/app/App.tsx:16-24`, `src/test/support/render-with-contexts.tsx:20-26`

- [ ] agree   - [ ] disagree →

### u103-I19 · MINOR (high)
**The smoke spec comment points at the wrong spec for the live chart and matches on user-visible copy.**

Found by: sonnet ×1 · CONCERN ×1

smoke.spec.ts says the chart is asserted in chart-render.spec.ts, which covers the harness route; chart-live.spec.ts covers '/'. Stale comment.

Evidence: `e2e/smoke.spec.ts:9-10`

- [ ] agree   - [ ] disagree →

### u103-I20 · MINOR (high)
**Hook comments carry stale task-number notes and a misplaced facade comment block.**

Found by: sonnet-high ×2 · CONCERN ×2

The header references tasks 8/10/12/14, the teardown comment says subscriptions join in task 12, and the facade comment sits above the series memo. Comment hygiene only.

Evidence: `src/chart/use-chart-provider.ts:10-20`, `src/chart/use-chart-provider.ts:128-143`, `src/chart/use-chart-provider.ts:185-186`

- [ ] agree   - [ ] disagree →

### u103-I21 · MINOR (high)
**A constant is declared between import statements in the translation test.**

Found by: sonnet ×1 · CONCERN ×1

LINE_SERIES sits between imports. Style.

Evidence: `src/test/use-chart-provider.translation.test.tsx:14-24`

- [ ] agree   - [ ] disagree →

### u103-I22 · MINOR (high)
**The e2e hexToRgba helper assumes a six-digit hex token with no validation.**

Found by: sonnet ×1 · CONCERN ×1

True; a different color format would fail with an opaque NaN mismatch rather than a clear error. Test diagnostics only.

Evidence: `e2e/chart-live.spec.ts:100-106`

- [ ] agree   - [ ] disagree →

### u103-I4 · MINOR (medium)
**Operations called before the chart is live are dropped silently by runGuarded.**

Found by: haiku-xhigh ×3 · CONCERN ×3

runGuarded returns undefined with no log when providerRef is null; the comment documents dropping calls unless the chart is live, and consumers have `ready` to gate on. No caller in this slice issues pre-ready calls. The findings also note the null-container early return is silent, but none identify the control defect (the effect never re-runs when the container appears late, because the dependency is the stable ref object), so this is not credited as the control.

Evidence: `src/chart/use-chart-provider.ts:101-113`, `src/chart/use-chart-provider.ts:167-171`

- [ ] agree   - [ ] disagree →

### u103-I5 · MINOR (medium)
**readChartStyle silently falls back to library default colors when a theme token resolves empty.**

Found by: haiku-xhigh ×3, sonnet-high ×3 · CONCERN ×6

True: empty tokens map to undefined and all-empty returns undefined, and styling.ts claims there is no silent theme fallback hiding a missing token. But it is a documented choice for environments without the stylesheet, the tokens exist in theme.css, and the e2e spec asserts the surface color; the risk is a future token rename, i.e. hardening against misconfiguration rather than a defect that arrives at head.

Evidence: `src/routes/chart-route.tsx:29-55`, `src/chart/types/styling.ts:12-14`

- [ ] agree   - [ ] disagree →

### u103-I6 · MINOR (high)
**use-chart-provider.ts exceeds the ~300-line file guide and its mount effect far exceeds the ~50-line function guide.**

Found by: haiku-xhigh ×3, sonnet ×3, sonnet-high ×2 · CONCERN ×8

The file is 366 lines and the mount effect spans lines 167-324, much of it comments. True but a size/style guideline with no behavioral effect.

Evidence: `src/chart/use-chart-provider.ts:167-324`

- [ ] agree   - [ ] disagree →

### u103-I7 · MINOR (high)
**react-hooks/refs is disabled for the whole hook file instead of the one construct that false-positives.**

Found by: haiku-xhigh ×3, sonnet-high ×1 · CONCERN ×4

eslint.config.js turns the rule off for all of use-chart-provider.ts with a documented justification. Narrowing it is a lint-hygiene point; no current defect results.

Evidence: `eslint.config.js:55-79`

- [ ] agree   - [ ] disagree →

### u103-I8 · MINOR (high)
**The indicator observer effect has an empty body and only adds a Context dependency.**

Found by: haiku-xhigh ×2 · CONCERN ×2

The effect returns early or does nothing; it is documented as a deliberate placeholder for initiative 120. Dead code and a vacuous test, no wrong behavior.

Evidence: `src/chart/use-chart-provider.ts:347-363`

- [ ] agree   - [ ] disagree →

### u103-I9 · MINOR (high)
**The crosshair and visible-range subscriptions are registered with no-op handlers.**

Found by: sonnet ×2, sonnet-high ×3 · CONCERN ×5

Both handlers contain only `if (disposedRef.current) return`. This is documented as proving the disposer lifecycle; it adds dead code and a little per-event work but no incorrect behavior.

Evidence: `src/chart/use-chart-provider.ts:286-301`

- [ ] agree   - [ ] disagree →
