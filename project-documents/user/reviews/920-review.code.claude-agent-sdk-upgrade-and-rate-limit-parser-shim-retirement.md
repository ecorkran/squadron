---
docType: review
layer: project
reviewType: code
slice: claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement
project: squadron
verdict: CONCERNS
verdictSource: stated
verdictResolved: true
resolutionDate: 20260915
sourceDocument: project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 20e08882bbc1d9ea77bad2142a9aaaf4683f76e7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Retry budget resets on every rejected RateLimitEvent in sdk_session.dispatch"
    location: "src/squadron/pipeline/sdk_session.py:153-158"
  - id: F002
    severity: note
    category: design
    summary: "Pre-existing: \"tool_use\" and \"tool_result\" string literals not centralized"
    location: "src/squadron/pipeline/actions/dispatch.py:174"
  - id: F003
    severity: pass
    category: design
    summary: "Typed RateLimitEvent classification is clean and well-tested"
    location: "src/squadron/providers/sdk/rate_limit.py:42-65"
  - id: F004
    severity: pass
    category: design
    summary: "Translation layer correctly makes informational events observable"
    location: "src/squadron/providers/sdk/translation.py:82-92"
---

# Review: code — slice 920

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] Retry budget resets on every rejected RateLimitEvent in sdk_session.dispatch — RESOLVED

**Resolution (20260915):** Confirmed — `progressed = True` was set before the `RateLimitEvent`/`event_blocks` check, so a rejected event as the first message in a stream never counted against the retry budget. Fixed in `src/squadron/pipeline/sdk_session.py` by moving `progressed = True` after the rejection check, so a rejected event is never treated as progress. Added `test_dispatch_exhausts_retry_budget_on_persistent_rejection` (tests/pipeline/test_sdk_session.py), which rejects on every call and asserts the dispatch raises after exhausting `MAX_RATE_LIMIT_RETRIES` — this test failed before the fix (infinite retry) and passes after.

In `SDKExecutionSession.dispatch`, `progressed = True` is set unconditionally at the top of the `async for` body, **before** the `RateLimitEvent` / `event_blocks` check that raises `RateLimitRejected`. When a rejected event is the first (and possibly only) message in the stream, `progressed` is already `True`, so the `except ClaudeSDKError` handler resets `retries = 0` every time:

```
                                                    
                                                                                
                                                                     
                                    
```

Because the budget is always reset to 0 and then incremented to 1 (which is always `< MAX_RATE_LIMIT_RETRIES` = 10), the retry loop never exits. A persistently rejecting provider causes the dispatch to retry indefinitely with a flat 2-second delay (`rate_limit_backoff_s(1)`), hanging the pipeline step with no timeout.

This is a behavioral regression from the pre-diff code. Previously, a rate-limit surfaced as a `ClaudeSDKError` raised by the SDK's async generator (`__anext__`), not inside the loop body — so `progressed` was only `True` when a prior message had been received. A rejected event as the first message correctly consumed budget.

Contrast with `agent.py`'s client mode, where `_skip_unparseable` raises `RateLimitRejected` **before** yielding, so the caller's `progressed = True` is never set for a rejected event:

```python
                                
                                                                             
                                                                            
```

The fix is to move the `RateLimitEvent` check before the `progressed = True` assignment:

```python
                                                    
                                                                     
                                
                                                                         
         
                     
       
```

There is also no test verifying budget exhaustion on the `sdk_session.py` path. `test_dispatch_retries_on_rate_limit` (tests/pipeline/test_sdk_session.py:227) only retries twice with success on the third attempt, so it would not catch this issue. A test that yields a rejected event on every call and asserts the dispatch eventually raises after `MAX_RATE_LIMIT_RETRIES` attempts would prevent regression.

### [NOTE] Pre-existing: "tool_use" and "tool_result" string literals not centralized — DEFERRED

The diff adds `RATE_LIMIT_EVENT_TYPE` to the sdk_type filter in `dispatch.py`, `summary_oneshot.py`, `review_client.py`, and `audit.py`. `SDK_RESULT_TYPE` and `RATE_LIMIT_EVENT_TYPE` are imported constants from `core/models.py`, but `"tool_use"` and `"tool_result"` remain inline string literals in every filter site. This is pre-existing (not introduced by this diff) and the project convention says comparison values should be defined once. Consider extracting these to constants in `core/models.py` alongside `SDK_RESULT_TYPE` and `RATE_LIMIT_EVENT_TYPE` in a future pass.

**Disposition (20260915):** Deferred, out of scope for this diff — filed as [issue #108](https://github.com/ecorkran/squadron/issues/108).

### [PASS] Typed RateLimitEvent classification is clean and well-tested

The new `event_blocks`, `RateLimitRejected`, and `is_throttle` form a clean classification layer. `RateLimitRejected` subclasses `ClaudeSDKError` so existing `except ClaudeSDKError` backoff loops catch it without restructuring. `is_throttle` correctly checks `RateLimitRejected` before the substring fallback. The old `install_rate_limit_parser_shim` monkey-patch and dict-payload inspection (`is_rate_limit_event`, `rate_limit_event_blocks`) are fully removed, and `RATE_LIMIT_EVENT_TYPE` is centralized in `core/models.py` as the single source of truth. Tests in `TestRateLimitClassification` and `TestRateLimitEvent` cover all three statuses (rejected/allowed/allowed_warning) at both the unit and integration level.

### [PASS] Translation layer correctly makes informational events observable

`_translate_rate_limit_event` produces a `MessageType.system` message with `sdk_type=RATE_LIMIT_EVENT_TYPE` and `status` in metadata, making informational rate-limit events observable rather than silently dropped. Every prose-collecting consumer (dispatch, summary_oneshot, review_client, audit, sdk_session) now filters `RATE_LIMIT_EVENT_TYPE` alongside `SDK_RESULT_TYPE` and tool narration types, preventing usage-meter notices from contaminating response text. This is consistent across all five sites.

### Run Digest

- Response length: 5620 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 38326
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
