---
docType: tasks
slice: usage-and-cost-tracking
project: squadron
lld: user/slices/175-slice.usage-and-cost-tracking.md
dependencies: [174, 931]
projectState: >
  Slice 175 design approved after two review rounds (20261014). 931 built the neutral
  usage types and the OpenAI/Codex readers; 174 built SDK session stall interrupts and
  drains. This slice adds SDK capture, per-action UsageRecords in run state, cost, and
  `sq stats`. Closes #172, #36, #154, #151, #158.
dateCreated: 20261014
dateUpdated: 20261014
status: not_started
---

## Context Summary

- Working on **175 usage-and-cost-tracking**. Every LLM action (dispatch, summary, compact, review) stamps a `UsageRecord` into `ActionResult.metadata`; SDK paths stop discarding `ResultMessage` usage; cost follows D3 precedence; `sq stats run|reviews` reports it.
- Decisions D1–D10, the API contracts, the persisted shape, the UI layout, and the failure table live in the slice design. Tasks reference them and do not repeat them. Use the design's WARNING texts verbatim.
- Key files: `core/usage.py`, `providers/base.py`, `providers/sdk/{agent,translation}.py`, new `providers/sdk/usage.py`, `pipeline/{sdk_session,sdk_turns}.py`, `models/aliases.py`, new `pipeline/usage_capture.py`, `pipeline/actions/{dispatch,summary,compact,review}.py`, `pipeline/summary_oneshot.py`, `review/{run_cost,models,review_client,turn_capture}.py`, new `stats/usage_report.py`, new `cli/commands/stats.py`.
- `pipeline/actions/dispatch.py` (835 lines) and `review.py` (720) are already over size. New logic goes in `pipeline/usage_capture.py`; actions only call it.
- Three implementation choices not spelled out in the design, fixed here so no task has to decide them:
  - **Cost precedence lives in one function.** `resolve_cost(...)` beside `price_usage` in `models/aliases.py` applies D3 (provider cost, else alias pricing, else none). Both `review_client` (standalone reviews) and `usage_capture` call it. Neither re-implements the precedence.
  - **The pricing-warning set** is created once per run by the executor and handed to `usage_capture`, and once per call by `review_client`. Each CLI process runs one run or one review, so this gives "once per alias per process" without a module global (failure table).
  - **SDK session telemetry.** `dispatch`, `capture_summary`, and `compact` return a small `SessionReply(text, telemetry)` instead of `str`. On failure the `ProviderError` (including `DispatchStalledError`) carries the telemetry in its existing `telemetry` field. A stall whose drain failed (`session_usable is False`) is the D5 `partial` case.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors) and the touched tests. Commit on the slice branch where a task says so.
- Effort: 4/5. Next planned work: the #214/#210 follow-on slice (needs a slice plan entry, D10).

## Tasks

### Neutral record (D1, D3, D5, D6)

- [ ] **Task 1: Extend `core/usage.py`**
  - [ ] Read the target (`cf config get git.integration_branch`, empty means `main`) and create `175-slice.usage-and-cost-tracking` from it
  - [ ] `TokenUsage` gains `cache_write: int | None = None` (after `cached`). Include it in `plus()` and `reported`. Update the D1 field comments.
  - [ ] Add `add_optional_float(total, value)` with the same `None` rule as `add_optional`
  - [ ] `RunTelemetry` gains `cost_usd: float | None = None`. Add a `fold_result(*, turns, usage, cost_usd)` method for providers that report a whole query at once (SDK): adds `turns` to `turns`, `usage` through `plus`, `cost_usd` through `add_optional_float`. `fold_turn` stays unchanged.
  - [ ] Add `CostBasis(StrEnum)` and the frozen `UsageRecord` dataclass exactly as in the design's API Contracts, including `partial: bool = False`
  - [ ] `UsageRecord.to_dict()` emits the design's persisted shape: tokens nested under `"tokens"`, `cost_basis` as its string value, `partial` only when true
  - [ ] `UsageRecord.from_dict()` is the inverse. It raises `ValueError` naming the offending key when a field has the wrong type or `tokens` is not a mapping. Missing optional keys read as `None`.
  - [ ] The module stays stdlib-only
  - **Success:** `tests/test_import_purity.py` still passes; `from_dict(to_dict(r)) == r` for any record

- [ ] **Task 2: Test the neutral record**
  - [ ] In `tests/core/test_usage.py`: `cache_write` sums through `plus` and keeps `None` when no side reported; `reported` is true when only `cache_write` is set
  - [ ] `add_optional_float`: `None + None → None`, `None + 0.5 → 0.5`, `0.25 + 0.5 → 0.75`
  - [ ] `fold_result` across two results sums turns, tokens, and cost; a `None` cost on both stays `None`
  - [ ] `UsageRecord` round-trip: a full record, an all-`None` record, `partial=True` (key present) and `partial=False` (key absent from `to_dict`)
  - [ ] `from_dict` raises `ValueError` for `tokens` as a list, `turns` as a string, and an unknown `cost_basis` value
  - [ ] Run `pytest tests/core tests/test_import_purity.py -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 3: Metadata key constants**
  - [ ] In `providers/base.py`, beside the existing tool-telemetry keys, add `USAGE_KEY = "usage"`, `TURNS_KEY = "turns"`, `COST_USD_KEY = "cost_usd"`
  - [ ] Replace the literals in `providers/codex/agent.py:109`, `providers/openai/agent.py:729-730`, and `review/turn_capture.py:159-162` with the constants. Find any others with `grep -rn '"usage"\|"turns"' --include='*.py' src/squadron`. Keys in `review/run_cost.py` that name frontmatter/JSON fields (`"turns"` at lines 43, 68) are output-format keys, not message metadata; leave them.
  - [ ] In `review/turn_capture.py`, also read `COST_USD_KEY` from the final message metadata and keep it on the capture result beside `usage` and `turns`
  - [ ] Run `pytest tests/core tests/providers tests/review -q`, ruff, pyright
  - [ ] Commit: `feat: add UsageRecord, cache_write, and usage metadata constants`
  - **Success:** the grep finds no message-metadata `"usage"`/`"turns"` literal under `src/squadron`; tests pass, zero pyright errors

### Pricing (D3)

- [ ] **Task 4: `price_usage` and `resolve_cost`; delete `estimate_cost`**
  - [ ] In `models/aliases.py`, add `price_usage(alias_name, usage, warned) -> float | None` per the design signature and D3 rule 2: uncached input `prompt − cached − cache_write`, each class at its own `ModelPricing` key (`input`, `cache_read`, `cache_write`, `output`). Reasoning is inside `completion` (D1) and is not priced separately.
  - [ ] Return `None` when the alias is `None` or unknown, has no `pricing`, a class with a nonzero count has no price, `prompt` or `completion` is `None`, or `cached + cache_write > prompt`
  - [ ] For the missing-price and inconsistent-count cases only, log one WARNING per alias per `warned` set naming the alias and the missing key (or the counts), then add the alias to `warned`. An alias with no `pricing` table at all is not warned (expected).
  - [ ] Add `resolve_cost(alias_name, usage, provider_cost, warned) -> tuple[float | None, CostBasis | None]`: `provider_cost` not `None` → `(provider_cost, PROVIDER)`; else a priced value → `(value, ALIAS_PRICING)`; else `(None, None)`
  - [ ] Delete `estimate_cost`, its export, and the `estimate_cost` tests in `tests/cli/test_model_list.py` (T8 block from line 258). `grep -rn estimate_cost src tests` returns nothing.
  - [ ] No price literal appears in Python (design D3)
  - **Success:** one function holds D3 precedence; `estimate_cost` is gone

- [ ] **Task 5: Test pricing**
  - [ ] New `tests/models/test_price_usage.py`, patching `get_all_aliases` as the deleted T8 tests did. One table-driven test per D3 branch:
    1. Full pricing with cached and cache_write → exact sum per class
    2. No cache tokens → input and output only
    3. `cache_write > 0` and no `cache_write` price → `None` + one WARNING naming the alias and `cache_write`; a second call with the same `warned` set logs nothing
    4. `cached + cache_write > prompt` → `None` + WARNING
    5. Alias without `pricing`, unknown alias, `None` alias → `None`, no WARNING
  - [ ] `resolve_cost`: provider cost wins over alias pricing; alias pricing when provider cost is `None`; `(None, None)` when neither; provider cost `0.0` is kept as `0.0` with basis `provider` (a reported zero is not "none")
  - [ ] Run `pytest tests/models tests/cli/test_model_list.py -q`, ruff, pyright
  - [ ] Commit: `feat: replace estimate_cost with price_usage and D3 cost precedence`
  - **Success:** tests pass (design criterion 5 at unit level)

### SDK capture (D1, D2; #172, #36)

- [ ] **Task 6: Capture a real `ResultMessage` fixture**
  - [ ] Run `claude -p --output-format json "Reply with the word ok."` once (a live call that spends real tokens). Its JSON result object is what the SDK parses into `ResultMessage` (the `usage` dict is passed through unchanged).
  - [ ] Save it as `tests/providers/sdk/fixtures/result_message_real.json`. Replace `result` with `"ok"` and `session_id` with a placeholder; keep `usage`, `num_turns`, `total_cost_usd`, `subtype`, `is_error`, `duration_ms` exactly as emitted. Add a sibling `README.md` (with frontmatter) recording the `claude` CLI version and `claude-agent-sdk` version (0.2.162 pin) and the capture command.
  - [ ] Add a test helper that builds a `ResultMessage` from this JSON (`ResultMessage(**fields)` with the SDK's field names), for Tasks 7–10 and 15
  - [ ] If the command fails or its output has no `usage` object, stop and report to the Project Manager; do not write a fixture by hand
  - **Success:** the fixture's `usage` keys are exactly the keys the CLI emitted; no prompt or response content

- [ ] **Task 7: SDK result reader**
  - [ ] New `providers/sdk/usage.py`: `read_result_usage(msg: ResultMessage) -> tuple[TokenUsage | None, int | None, float | None]` (tokens, turns, cost)
  - [ ] Map per D1. `prompt` is `None` only if `input_tokens` is missing; a missing cache key adds nothing and leaves that field `None`; never substitute 0. `reasoning` is always `None`.
  - [ ] `msg.usage is None` → tokens `None` (the caller warns, Task 8); turns and cost still read
  - [ ] A non-int usage value (bool counts as non-int) → that field `None`, siblings read, WARNING naming the field and value with `%.200r`
  - [ ] `num_turns` and `total_cost_usd` read only when the type matches, else `None`
  - [ ] Do not read `model_usage` or per-message usage (D2)
  - **Success:** the reader is the only code that knows SDK usage key names

- [ ] **Task 8: Test the SDK reader**
  - [ ] New `tests/providers/sdk/test_usage.py`: the real fixture maps to the D1 sums (assert against values computed from the fixture's own dict, not hard-coded numbers)
  - [ ] Stubs: no cache keys → `cached`/`cache_write` `None`, `prompt == input_tokens`; missing `input_tokens` → `prompt` `None`; `usage=None` → tokens `None`, turns and cost read; `cache_read_input_tokens="12"` → that field `None`, siblings read, one WARNING containing the field name
  - [ ] Run `pytest tests/providers/sdk -q`, ruff, pyright
  - **Success:** tests pass; an SDK upgrade that renames a usage key fails the fixture test

- [ ] **Task 9: `ClaudeSDKAgent` stamps usage**
  - [ ] In `providers/sdk/agent.py`, hold a `RunTelemetry` per `handle_message` call. In `_translate_and_track`, for every `ResultMessage`, `fold_result` with `read_result_usage`'s output (D2: sum across results in one call, never per-message usage).
  - [ ] Stamp `TURNS_KEY`, `USAGE_KEY`, and `COST_USD_KEY` on the final message, where tool telemetry is already stamped. `USAGE_KEY` is `None` when no result reported usage.
  - [ ] When a `ResultMessage` has `usage is None`, log the WARNING once per `handle_message` (mirror the OpenAI agent's 931 wording, naming the SDK)
  - [ ] In the agent's existing failure path, attach `telemetry.snapshot()` to the raised `ProviderError` (D5)
  - [ ] Leave `providers/sdk/translation.py` `_translate_result` unchanged: the agent reads the raw `ResultMessage`, the translator stays content-only
  - **Success:** SDK reviews get usage through the existing `review_client` / `turn_capture` path with no review-side change beyond Task 3

- [ ] **Task 10: Test the SDK agent**
  - [ ] In `tests/providers/sdk/test_agent.py`: feed messages ending in the real-fixture `ResultMessage`; assert the final message's three keys equal the reader's output
  - [ ] Two `ResultMessage`s in one call → turns, tokens, and cost summed; a preceding `AssistantMessage` carrying its own `usage` is not counted
  - [ ] `usage=None` → `USAGE_KEY` is `None`, exactly one WARNING for the call
  - [ ] A failing call after one result → the raised `ProviderError.telemetry` holds that result's tokens
  - [ ] Run `pytest tests/providers/sdk tests/review -q`, ruff, pyright
  - [ ] Commit: `feat: capture Claude SDK result usage, turns, and cost`
  - **Success:** tests pass

### Review artifacts (D3; criterion 1)

- [ ] **Task 11: `ReviewResult` and `RunCost` carry cache write and cost**
  - [ ] `ReviewResult` (`review/models.py`) gains `cost_usd: float | None = None` and `cost_basis: CostBasis | None = None`. `to_dict()` gains `cache_write_tokens`, `cost_usd`, `cost_basis`, always present, `null` when not reported.
  - [ ] In `review/review_client.py`, where `result.usage` is set (line ~312), call `resolve_cost(alias, capture.usage, capture.cost_usd, warned)` with a `warned` set created for this call; set both fields. Apply the same on the `ProviderError` path where `RunCost.from_error` is used, using the error's `telemetry.cost_usd`.
  - [ ] `RunCost` (`review/run_cost.py`) gains `cost_usd` and `cost_basis`, filled from `ReviewResult` and from `from_error`
  - [ ] `frontmatter_lines` adds `cacheWriteTokens`, `costUsd`, `costBasis` (each only when set; `costBasis` as its string value)
  - [ ] `digest_lines`: token line becomes `prompt / cached / cache write / completion / reasoning`; add the `Cost: $0.41 (provider)` line, or `Cost: not reported` when `cost_usd` is `None`
  - **Success:** an artifact with no cost renders `Cost: not reported` and has no `costUsd` key

- [ ] **Task 12: Test review rendering and regenerate the fixture**
  - [ ] In the existing `RunCost` / review persistence tests under `tests/review`: all keys present with provider cost; OpenAI-style usage (no cache write) priced from alias → `costBasis: alias_pricing`, no `cacheWriteTokens`; no cost → no `costUsd`, digest says `not reported`; `to_dict()` always has the three new keys
  - [ ] Regenerate `tests/review/fixtures/clean_pass_artifact.md` once for the digest token-line change; confirm with `git diff` that only the token line and the new `Cost:` line changed
  - [ ] Run `pytest tests/review tests/cli -q`, ruff, pyright
  - [ ] Commit: `feat: add cache write and cost to review artifacts`
  - **Success:** tests pass; an existing artifact without the new keys still parses

### SDK session telemetry (D2, D5; criterion 3)

- [ ] **Task 13: `DispatchTurns` telemetry and error telemetry**
  - [ ] In `pipeline/sdk_turns.py`, `DispatchTurns` gains `telemetry: RunTelemetry`. `collect()` folds every `ResultMessage` it sees with `read_result_usage` and `fold_result`: the own result, injected follow-up turns, and results read during `_interrupt_and_drain` all pass through `collect`. Warn once per dispatch when a result has `usage is None`.
  - [ ] On every raise path in `SDKExecutionSession.dispatch` (including `DispatchStalledError` after the drain), set the error's `telemetry` to `turns.telemetry.snapshot()` before it propagates. Return types do not change in this task.
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `feat: fold SDK session result usage into dispatch telemetry`
  - **Success:** existing tests pass unchanged; zero pyright errors

- [ ] **Task 14: `SessionReply` return type and caller migration**
  - [ ] Add frozen `SessionReply(text: str, telemetry: RunTelemetry)` in `sdk_turns.py`; `SDKExecutionSession.dispatch` returns it
  - [ ] `capture_summary` returns the `SessionReply` from its dispatch. `compact` returns a `SessionReply` with the summary text and the capture's telemetry; when `summary` is passed in (no capture), telemetry is an empty `RunTelemetry` with `turns == 0`.
  - [ ] Update callers to read `.text`: `pipeline/actions/dispatch.py:543`, `pipeline/actions/summary.py:265`, `pipeline/actions/compact.py:73`, `pipeline/emit.py:155`. Recording usage at those sites is Tasks 18–21; `emit.py` only reads `.text` (not an action in scope).
  - [ ] Migrate existing fakes and mocks of `dispatch`, `capture_summary`, and `compact` under `tests/` that return a `str` to return `SessionReply` (find them with `grep -rn 'dispatch\|capture_summary\|compact' tests/pipeline | grep -i 'return_value\|async def'`)
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - **Success:** no caller or test fake treats the reply as `str`; existing tests pass; zero pyright errors

- [ ] **Task 15: Test session telemetry**
  - [ ] In the existing SDK session tests under `tests/pipeline` (the ones that drive `dispatch` with a fake client): own result plus one injected follow-up turn → telemetry sums both
  - [ ] Stall with a successful drain → `DispatchStalledError.telemetry` includes the drained result, `session_usable` true
  - [ ] Stall whose drain ends with no result → `telemetry` holds only completed results, `session_usable` false
  - [ ] `compact(summary="x")` → `turns == 0`
  - [ ] Two results with `usage=None` in one `dispatch()` → exactly one WARNING
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `feat: return SDK session usage from dispatch, summary, and compact`
  - **Success:** tests pass

### Action capture (D4–D7; #151, #154)

- [ ] **Task 16: `pipeline/usage_capture.py`**
  - [ ] Add a `UsageCapture` class constructed with the run's `warned: set[str]`. It is the only place a `UsageRecord` is built (D4).
  - [ ] `record_from_message(resolved, message_metadata, *, started, model, effort_sent) -> UsageRecord | None` for `Agent` paths: reads the three `providers/base.py` keys
  - [ ] `record_from_telemetry(resolved, telemetry, *, started, model, effort_sent, partial=False)` for the session path and for `ProviderError.telemetry`
  - [ ] `record_from_review(result: ReviewResult, resolved, effort_sent)` reuses the review's already-resolved cost and basis and its `duration_seconds` (measured by `review_client`, 931 D9); no re-pricing, no `started`
  - [ ] `record_from_error(resolved, exc: ProviderError, *, model, effort_sent)` for a failed review: tokens from `exc.telemetry`, duration from `exc.duration_seconds` (set by `review_client.py:307`); `None` when `exc.telemetry` is `None`
  - [ ] `record_from_message` and `record_from_telemetry` compute `duration_seconds = time.monotonic() - started` at call time (D6). Every builder fills `alias`/`profile` from `ResolvedModel` (alias `None` for a bare model id), and calls `resolve_cost`
  - [ ] Return `None` when there is nothing to record: no turns, no usage, and no cost reported (a provider that reports nothing)
  - [ ] `partial=True` logs the D5 WARNING verbatim with run id and step name (passed in)
  - [ ] `stamp(metadata, record)` writes `metadata[USAGE_KEY] = record.to_dict()` only when `record` is not `None`. Every action writes the key through it, never directly.
  - [ ] `effort_for_session(resolved) -> None` returns `None` (D7) and, when `resolved.effort` is set, logs the D7 DEBUG line the first time per `UsageCapture`. One `UsageCapture` per run and one run per `sq run` process makes this once per process.
  - [ ] Holds no state beyond `warned` and the D7 logged flag; catches no exceptions (failure table, `CancelledError` row)
  - [ ] Wire construction: the executor creates one `UsageCapture` per run; `ActionContext` gains a `usage_capture: UsageCapture` field set by the executor for every step
  - **Success:** stdlib + squadron imports only; no Typer; under ~150 lines

- [ ] **Task 17: Test `usage_capture`**
  - [ ] New `tests/pipeline/test_usage_capture.py`, one test per provider shape: SDK agent metadata (provider cost → `provider`); OpenAI metadata with a priced alias (→ `alias_pricing`); Codex metadata (`turns: 1`); session telemetry; telemetry from a `ProviderError`
  - [ ] Bare model id → `alias` `None`, provider cost kept, no WARNING
  - [ ] `partial=True` → record flag set, D5 WARNING contains run id and step
  - [ ] Pricing WARNING fires once across two records on the same `UsageCapture`, again on a fresh one
  - [ ] `duration_seconds` equals the patched `time.monotonic` delta
  - [ ] Nothing reported → `None`; `stamp` with `None` leaves `metadata` without `USAGE_KEY`
  - [ ] `effort_for_session` with alias effort logs the D7 DEBUG line once across two calls on one `UsageCapture`
  - [ ] `record_from_review` takes `ReviewResult.duration_seconds`; `record_from_error` takes `exc.duration_seconds`
  - [ ] Executor wiring: run a two-step pipeline through the executor with stub actions that capture `context.usage_capture`; assert both steps received the same instance, and a pricing WARNING triggered from both steps fires once
  - [ ] Run `pytest tests/pipeline/test_usage_capture.py -q`, ruff, pyright
  - [ ] Commit: `feat: add usage_capture to build UsageRecords for actions`
  - **Success:** tests pass

- [ ] **Task 18: Wire dispatch (one-shot and session)**
  - [ ] In `pipeline/actions/dispatch.py`, take `started = time.monotonic()` immediately before the LLM call on both paths
  - [ ] One-shot: pass the alias `max_output_tokens` (`ResolvedModel.max_output_tokens`) into the agent config when the provider's `applies_output_budget` is true, as `review_client.py:283` does (#151). On success, `stamp` the record from `record_from_message`.
  - [ ] Session: `record_from_telemetry(reply.telemetry, ...)`. On `DispatchStalledError`, `partial = not exc.session_usable`.
  - [ ] On `ProviderError` with `telemetry`, the failed `ActionResult` gets the record too (D5)
  - [ ] `effort_sent` per D7: `resolved.effort` on the one-shot path when the provider's `applies_effort` is true, else `None`. The session path uses `usage_capture.effort_for_session(resolved)`.
  - [ ] Update the slice 931 D11 comment at `dispatch.py:220` ("no artifact records it here"): the record now does (#154)
  - [ ] Keep the action's added lines to the calls; any branching beyond picking `record_from_message` vs `record_from_telemetry` goes in `usage_capture.py`
  - **Success:** every dispatch exit path with an LLM call (success, `ProviderError`, stall) records usage when the provider reported any

- [ ] **Task 19: Test dispatch capture**
  - [ ] In `tests/pipeline/test_dispatch.py` (or a new `test_dispatch_usage.py` if that file is over size): one-shot success has `metadata["usage"]` with the persisted shape; the agent config received `max_output_tokens`; one-shot `ProviderError` with telemetry → failed result has a record; session success; session stall with failed drain → `partial: true`; SDK session with alias effort → `effort` `None` and the D7 DEBUG line logged once across two session dispatches in one run
  - [ ] The failed one-shot result and the stalled session result each carry a non-`None` `duration_seconds` (criterion 4)
  - [ ] `asyncio.CancelledError` from the agent propagates and no `usage` key is written (failure table)
  - [ ] State save count per action is unchanged (patch `StateManager` save and count; design "Hot-path cost")
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `feat: record usage and pass output budget on dispatch steps`
  - **Success:** tests pass (criteria 2, 4, 6, 7 for dispatch)

- [ ] **Task 20: Wire summary (one-shot and session)**
  - [ ] In `pipeline/actions/summary.py` and `pipeline/summary_oneshot.py`: same pattern as Task 18. One-shot passes `max_output_tokens` under the same `applies_output_budget` rule (#151) and records from message metadata; session records from `reply.telemetry` with effort from `effort_for_session` (D7).
  - [ ] `summary_oneshot.py` returns the final message metadata (or the record inputs) to the action; the action stamps `metadata[USAGE_KEY]`
  - [ ] Failure path with telemetry records (D5)
  - **Success:** summary steps record usage on both paths

- [ ] **Task 21: Test summary capture**
  - [ ] In the existing summary action tests: one-shot record with `max_output_tokens` passed and effort per D7; session record with effort `None`; a failure with telemetry records, with non-`None` `duration_seconds`
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `feat: record usage and pass output budget on summary steps`
  - **Success:** tests pass

- [ ] **Task 22: Wire compact and review**
  - [ ] In `pipeline/actions/compact.py`, take `started = time.monotonic()` immediately before `sdk_session.compact(...)`, then `stamp` the record from the `compact` `SessionReply.telemetry`, effort from `effort_for_session`. A compact with a supplied summary (turns 0, nothing reported) records nothing.
  - [ ] In `pipeline/actions/review.py`, after the review returns, `stamp` `usage_capture.record_from_review(...)`. `effort_sent` is `ReviewResult.effort`, which `review_client.py:317` already sets to the effort sent.
  - [ ] Failed review (D5): in the `except ProviderError` handler at `review.py:439`, where `settings.resolved` is in scope, build `record_from_error(settings.resolved, exc, ...)` (effort sent per D7). Replace that handler's bare re-raise with `_logger.exception` (the message `execute`'s catch-all logs today) and `return self._exception_result(context, exc, usage_record=record)`; `_exception_result` gains an optional `usage_record` and `stamp`s it.
  - [ ] No pricing or duration arithmetic in either action
  - **Success:** compact steps that ran a capture turn record usage; a pipeline review records the same tokens and cost its artifact shows; a failed review with telemetry records it

- [ ] **Task 23: Test compact and review capture**
  - [ ] Compact: capture turn → record with non-`None` `duration_seconds`; supplied summary → no `usage` key
  - [ ] Review: action metadata `usage.tokens` and `cost_usd` equal the `ReviewResult` values; a review raising `ProviderError` with telemetry → failed result has `usage` with `duration_seconds` equal to the error's, and the ERROR log still fires
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `feat: record usage on compact and review steps`
  - **Success:** tests pass (criterion 2 complete)

- [ ] **Task 24: State round-trip**
  - [ ] In `tests/pipeline` state tests: a run with usage records saves and loads with `metadata["usage"]` intact; checked-in pre-slice run files at schema v3, v4, v5 (add minimal files under `tests/pipeline/fixtures/state/`; none exist today) load without error
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `test: cover usage records through run-state round-trip`
  - **Success:** tests pass (criterion 9 at the state layer)

### Stats core (D8, D9)

- [ ] **Task 25: `stats/usage_report.py` — run report**
  - [ ] New package `src/squadron/stats/` (`__init__.py`, `usage_report.py`). No Typer, no Rich.
  - [ ] Typed results: `ActionUsageRow` (step, action type, record or `None`, `unreadable` flag), `RunUsageReport` (run header fields, rows, totals, priced count, LLM action count, unrecorded count, any-partial flag)
  - [ ] `run_usage_report(run_id, state_manager) -> RunUsageReport` loads through `StateManager.load` (never raw `open`). An unknown id or a load error raises a typed error carrying the id, runs directory, file, and parse/schema message.
  - [ ] Per action: `UsageRecord.from_dict`; `ValueError` → row `unreadable` + WARNING naming run and step (D9)
  - [ ] Non-LLM actions are identified by `ActionType` enum membership (one module constant set), not string matching. LLM actions with no record count toward "no usage recorded".
  - [ ] Totals computed at read time by one helper, `usage_totals(records)`: tokens with `add_optional`, turns summed, cost with `add_optional_float` over priced rows only, plus the priced count (D9). Nothing is stored. The reviews report (Task 27) reuses this helper.
  - **Success:** under ~300 lines; returns data only

- [ ] **Task 26: Test the run report**
  - [ ] New `tests/stats/test_usage_report.py`: mixed run (priced, unpriced, non-LLM, pre-slice) → totals, `N of M priced`, unrecorded count; malformed usage → `unreadable` row + WARNING; partial record → flag set; unknown id and corrupt file → typed error with the id/file; a test asserts loading goes through `StateManager`
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add run usage report core`
  - **Success:** tests pass

- [ ] **Task 27: Reviews report**
  - [ ] New `stats/reviews_report.py`: `reviews_usage_report(reviews_dir, slice_filter) -> ReviewsUsageReport` reads top-level `*.md` in `REVIEWS_DIR` with `read_frontmatter` only (no body reads)
  - [ ] `None` frontmatter → skipped, one WARNING per file, counted for the footer
  - [ ] `runId` present → excluded, counted, run ids kept for the footer hint (D8)
  - [ ] `slice_filter` compares against frontmatter `slice`
  - [ ] Missing directory → empty report with a `missing_dir` flag (not an error)
  - [ ] Rows: date, slice, review type, model, verdict, token and cost keys from the 931/175 frontmatter table; totals from `usage_totals` (Task 25)
  - [ ] Map each artifact to a `UsageRecord` for `usage_totals`: `promptTokens`, `cachedTokens`, `cacheWriteTokens`, `completionTokens`, `reasoningTokens`, `turns` → ints; `durationSeconds`, `costUsd` → floats (an int is accepted); `costBasis` → `CostBasis`; `requestedModel` → `alias` when it is a known alias, else `None`; `aiProfile` → `profile`; `effort` → `effort`. A missing key is `None`. A wrong type (bool counts as wrong for ints) or an unknown `costBasis` makes that field `None` and logs a WARNING naming the file and key; the row stays. The CLI's `api-rate equiv.` label then reads the alias the same way as for run rows.
  - **Success:** one frontmatter parse per artifact; each `stats` module under ~300 lines

- [ ] **Task 28: Test the reviews report**
  - [ ] New `tests/stats/test_reviews_report.py`, using a temp dir: standalone, pipeline (`runId`), unreadable-frontmatter, and other-slice artifacts → correct rows, excluded and skipped counts, filter; `promptTokens: "abc"` and `costBasis: guess` → those fields `None` with a WARNING naming file and key, row kept, totals exclude them; `requestedModel` that is not an alias → `alias` `None`; missing dir → `missing_dir`; patch the body reader to assert no body read
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add reviews usage report core`
  - **Success:** tests pass

### `sq stats` CLI and wrappers (D8; criteria 8, 10)

- [ ] **Task 29: `cli/commands/stats.py`**
  - [ ] Typer group `stats` with `run <run_id> [--json]` and `reviews [--slice INDEX] [--json]`; register in `cli/app.py` with `app.add_typer(stats_app, name="stats")`
  - [ ] Render the design's UI Specifications layout with `cli/columns.py` `fit_widths`. `—` for `None` cells; cost suffix `prov`/`alias`; `api-rate equiv.` label when the record's alias has `cost_tier == "subscription"` (read from the alias table, D3); `*` on partial rows plus the D5 footer; `N LLM actions have no usage recorded.`; reviews footer `N pipeline review(s) excluded; see sq stats run <id>` and `N artifact(s) skipped`
  - [ ] `--json` emits the same rows and totals as the table (one serializer over the report dataclasses)
  - [ ] Errors: unknown id / unreadable file → message naming id and runs dir, or file and error, exit 1. Missing reviews dir → `No review directory at <path>`, exit 0.
  - **Success:** no aggregation logic in the CLI module

- [ ] **Task 30: Test the CLI**
  - [ ] New `tests/cli/test_stats.py` with `CliRunner`: snapshot of each table; `--json` rows equal the table rows; old run shows `—` cells and the unrecorded line; unknown id and corrupt file exit 1 with the named id/file; missing reviews dir exits 0 with the message; subscription alias shows `api-rate equiv.`
  - [ ] Run `pytest tests/cli/test_stats.py -q`, ruff, pyright
  - [ ] Commit: `feat: add sq stats run and reviews commands`
  - **Success:** tests pass

- [ ] **Task 31: Slash command and agents skill**
  - [ ] Add `commands/sq/stats.md` and `commands/agents/sq-stats/SKILL.md`, modeled on `commands/sq/summary.md` and `commands/agents/sq-summary/SKILL.md`, containing only the instruction to run `sq stats $ARGUMENTS` and print its output
  - [ ] Extend `tests/cli/test_install_commands.py` to assert both files install
  - [ ] Run `sq install-commands` locally
  - [ ] Run `pytest tests/cli/test_install_commands.py -q`
  - [ ] Commit: `feat: add /sq:stats slash command and sq-stats skill`
  - **Success:** tests pass (criterion 10)

### Docs and closure

- [ ] **Task 32: CHANGELOG and README**
  - [ ] CHANGELOG (user-facing bullets): `sq stats`; SDK reviews and every pipeline LLM step now record tokens, turns, time, and cost; review artifacts gain cache-write and cost keys; dispatch and summary honor alias `max_output_tokens`
  - [ ] README: a `sq stats` section and the cost-basis meaning (`provider` vs `alias_pricing`, and that `api-rate equiv.` on a subscription is not money spent)
  - [ ] Propose the minor version bump to the Project Manager in one line with the reason (new `sq stats` command group); change no version files
  - [ ] Commit: `docs: add sq stats and cost basis to README and CHANGELOG`
  - **Success:** both files updated

- [ ] **Task 33: Full validation**
  - [ ] Run `ruff format`, `ruff check`, `pyright` (zero errors), and the full `pytest` suite
  - [ ] Run the design's Verification Walkthrough steps 1–7 in a scratch project registered with cf. Record each step's outcome in the DEVLOG entry. If a step cannot run (for example, no OpenRouter alias with pricing for step 2), stop and report it to the Project Manager rather than marking it done.
  - [ ] Commit any fixes: `fix: address 175 walkthrough findings`
  - **Success:** suite green; walkthrough steps pass

- [ ] **Task 34: Draft issue closure comments**
  - [ ] Draft, without posting, one-line closing comments for #172, #36, #154, #151 naming what landed; one for #158 noting 931 implemented it and 175 added the `cache_write` field (always `None` on OpenAI-compatible, D2); and a non-closing comment on #33 that SDK capture landed and `AuditRun` persistence remains open
  - [ ] Give the drafts to the Project Manager. Posting and closing happen at Phase 7 closure, after code review, and only on the Project Manager's go-ahead.
  - **Success:** drafts delivered; no issue posted to or closed in Phase 6
