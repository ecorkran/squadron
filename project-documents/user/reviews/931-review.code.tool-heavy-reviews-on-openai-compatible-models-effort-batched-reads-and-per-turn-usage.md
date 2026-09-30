---
docType: review
layer: project
reviewType: code
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20260930
dateUpdated: 20260930
reviewedSha: ba894347035d4d24a7f92945b4fa8f8df0053298
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 37
diffTruncated: false
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: pass
    category: testing
    summary: "Shared-capture test infrastructure replaces copy-pasted path drivers"
    location: "tests/providers/agent_config_sites.py"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The batch byte budget is not actually bounded by the per-result floor"
    location: "src/squadron/tools/builtin/file_tools.py#_read_batch"
  - id: F003
    severity: concern
    category: documentation
    summary: "`Effort` is described as the SDK's vocabulary but silently rejects `max`"
    location: "src/squadron/core/models.py:40"
  - id: F004
    severity: note
    category: error-handling
    summary: "Effort validation keys on member names, not values"
    location: "src/squadron/models/aliases.py:91"
  - id: F005
    severity: note
    category: observability
    summary: "Two WARNINGs fire for one empty final turn"
    location: "src/squadron/providers/openai/agent.py#_log_run_signals"
  - id: F006
    severity: note
    category: observability
    summary: "Success and failure measure duration over different spans"
    location: "src/squadron/review/review_client.py:271"
  - id: F007
    severity: note
    category: testing
    summary: "`spawn`'s None-filter is invisible to its own test, and `sends_stream_usage` ships to every provider"
    location: "src/squadron/cli/commands/spawn.py:39"
  - id: F008
    severity: note
    category: testing
    summary: "Timing thresholds in the load tests are wall-clock sensitive"
    location: "tests/load/test_usage_reader_loop.py"
---

# Review: code — slice 931

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Shared-capture test infrastructure replaces copy-pasted path drivers

Extracting the seven per-path builders into `agent_config_sites` (stopping each path where its `AgentConfig` reaches `ClaudeSDKProvider.create_agent`) removes the duplication that previously lived in `test_settings_policy.py`, and `tests/providers/test_profile_credentials_sites.py` reuses it to assert every agent-building site carries `profile_credentials`. Tests accompany the implementation rather than trailing it (test-with, not test-after), which is the pattern the rules ask for. `tests/tools/test_read_file.py`'s characterization block ("written against the pre-batch implementation and left unedited") is a good regression guard for the `_read_one` extraction.

### [CONCERN] The batch byte budget is not actually bounded by the per-result floor

`limits.py` states the invariant plainly: `MAX_READ_BATCH_BYTES` is "Kept equal to MAX_READ_BYTES so a whole batch, headers included, stays under min_tool_result_chars() and the agent's per-result cap never cuts one mid-file; a test pins that invariant." That test (`test_full_batch_stays_under_the_per_result_floor`) pins it only for "100 more requested paths of 200 characters each" — a heuristic. `_read_batch` emits one `[not read: batch budget of N bytes reached...]` section for *every* remaining path (`sections.extend(_section(path, marker) for path in remaining)`), and the number of remaining paths is chosen by the model, bounded only by how large a tool-call argument the backend streams. With a few thousand paths the output exceeds `min_tool_result_chars()` and the agent's per-result cap re-truncates it mid-section, which is exactly the failure mode the floor exists to prevent (the comment in `limits.py` cites two live incidents of this). The first-N-files behavior is correct; the marker tail is the unbounded part. Either cap the number of marker lines (e.g. summarize the remainder in one line) or name the real bound in the comment instead of claiming an invariant that the tests only sample.

### [CONCERN] `Effort` is described as the SDK's vocabulary but silently rejects `max`

The docstring says the enum is "The intersection of OpenAI-style `reasoning_effort` and the Claude SDK's `effort`, plus `none`". Two problems: (a) `claude_agent_sdk.types. EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]`, so the enum is *not* the SDK's set — it includes `xhigh` (not an OpenAI value) and omits `max` (a valid SDK level); `_effort_options` in `src/squadron/providers/sdk/provider.py` documents the same claim ("Every other level is one the SDK accepts as-is"). (b) An alias writing `effort = "max"` for an SDK profile is not honored — `test_invalid_effort_is_skipped_with_a_warning` parametrizes `'"max"'` as an *invalid* value, so the only signal is a WARNING and the request silently runs at the backend default. I could not verify the OpenAI `ReasoningEffort` literal to confirm the `none` claim, so treat that half as unverified; the `max` half is verifiable from the installed SDK and the added test. If dropping `max` is deliberate, the docstring should say so (and the warning should tell the operator what to use instead); if it is not, `max` belongs in the enum and the SDK path is already able to carry it.

### [NOTE] Effort validation keys on member names, not values

`if isinstance(effort_val, str) and effort_val in Effort.__members__` matches against member *names*. It happens to be correct today because every member's name equals its value (`none = "none"`, …), but it is a silent-failure trap: if a member is ever declared as `x_high = "xhigh"`, a TOML `effort = "xhigh"` is rejected while `effort = "x_high"` is accepted, with only a WARNING either way. `Effort(effort_val)` inside `try/except ValueError` (as `AgentConfig` itself does, per `test_agent_config_rejects_an_effort_outside_the_vocabulary`) keys on the value and cannot drift.

### [NOTE] Two WARNINGs fire for one empty final turn

`_require_final_content` already logs "Model returned an empty final turn (finish_reason=…, reasoning_chars=…)" before raising `EmptyFinalTurnError`; the new `finally` then logs "OpenAI agent ended without a final response after N turn(s) (prompt=… cached=… completion=… reasoning=… tokens)" for the same event. The exit warning is genuinely useful for the transport/guard paths (where it is the only signal, and the tests assert exact counts for those), but for the empty-turn path it duplicates an adjacent diagnosis. The tests do not pin the empty-turn case, so nothing catches the doubling. Consider suppressing the exit warning when the exception already explains itself, or asserting the pair in a test so the duplication is intentional rather than incidental.

### [NOTE] Success and failure measure duration over different spans

On success, `duration_seconds = time.monotonic() - started` is evaluated inside the inner `try`, before the `finally` runs `await agent.shutdown()`. On failure, `exc.duration_seconds = time.monotonic() - started` runs in the outer handler, after `shutdown()` has completed — and for the SDK provider `shutdown()` awaits `client.disconnect()`, which is not guaranteed fast. The two artifacts' `durationSeconds` therefore measure different spans for the same run. The docstring says "wall-clock from agent creation through the recovery turn", which matches only the success path. Capturing the timestamp in the same place for both (or stating that shutdown is excluded) would make the two failure/success artifacts comparable.

### [NOTE] `spawn`'s None-filter is invisible to its own test, and `sends_stream_usage` ships to every provider

`test_spawn_credentials_carry_profile_credentials` asserts `credentials == profile_credentials(_DISTINCT_SDK)`, but `_DISTINCT_SDK` sets all three values non-`None` — so the comprehension's `if v is not None` filter is a no-op under the fixture and the test passes whether or not the filter exists. A fixture with one field left `None` would actually exercise the comment's claim. Separately, `profile_credentials` now includes `sends_stream_usage` for every profile, so `sq spawn --profile sdk` (and any non-OpenAI provider) sends that key in the daemon request body. It is inert for the SDK/Codex providers, but it is a credential-shaped key whose only reader is the OpenAI provider — worth a sentence in the docstring or filtering it to the providers that consume it.

### [NOTE] Timing thresholds in the load tests are wall-clock sensitive

The load tier is required for these paths and is otherwise well-constructed (real files, a ticker task, one-worker-hop assertion, reader cost measured over 1,000 calls). The assertions `max(gaps) < 0.050` and `mean < 0.001` are absolute wall-clock bounds; on a saturated CI runner a GC pause or a co-tenant can trip them without any regression in the code under test. The docstrings acknowledge generous bounds, but consider recording the observed value in the failure message (or a ratio against a fixed baseline) so a failure is diagnosable as jitter versus regression.

### Run Digest

- Response length: 8297 chars
- Response is newline-free: no
- Tool calls made: 37
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 51922
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response (20260930)

- **Batch byte budget not bounded (concern): fixed.** `paths` is capped at `MAX_READ_BATCH_PATHS` (50) entries of at most `MAX_READ_PATH_CHARS` (1024) characters; a longer request is a correctable error result. `test_full_batch_stays_under_the_per_result_floor` now computes the executor's true worst case from those limits instead of a sample.
- **`Effort` rejects `max` (concern): intended, now stated.** OpenAI's `ReasoningEffort` (openai 2.24.0) is `none|minimal|low|medium|high|xhigh`, so the vocabulary is the intersection with the SDK's `low|medium|high|xhigh|max`, plus `none` — the docstring was right. D1 excludes `minimal` and `max` deliberately; the docstring and the skip WARNING now say so.
- **Effort validation keys on names: fixed.** Parsed with `Effort(value)`.
- **Two WARNINGs on an empty final turn: kept.** The empty-turn WARNING diagnoses the turn; the exit WARNING carries the run's token totals, which the first does not.
- **Duration spans differ: fixed.** Success now reads the clock after shutdown, as failure does.
- **spawn None-filter untested: fixed** (`test_spawn_omits_unset_profile_fields`). `profile_credentials` documents that only the OpenAI provider reads `sends_stream_usage`.
- **Load-test timing thresholds: kept.** Generous by design (the load-test tier asserts on latency bounds).
