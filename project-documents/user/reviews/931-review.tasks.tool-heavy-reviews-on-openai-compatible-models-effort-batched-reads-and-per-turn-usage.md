---
docType: review
layer: project
reviewType: tasks
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20260929
dateUpdated: 20260929
reviewedSha: d45e735369c7a8f2816da5a1c55d11182863aa98
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
runId: run-20260930-p5-f12cfe4d
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "Event-loop NFR tests are placed in unit files, not the load-test tier, and no CI wiring task exists"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Task 4B's equality assertion contradicts the extra credential keys four sites carry"
    location: "src/squadron/review/review_client.py:224-229"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Task 5 reads `credentials.get(\"sends_stream_usage\")` on the agent, but no task gives the agent a `credentials` member"
    location: "src/squadron/providers/openai/agent.py"
  - id: F004
    severity: note
    category: code-structure
    summary: "Task 3's `warned`-set cross-reference points at the wrong task"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F005
    severity: note
    category: code-structure
    summary: "Task 6 does not state the stamping order relative to the `_stamp_tool_telemetry` early return"
    location: "src/squadron/providers/openai/agent.py:574-609"
  - id: F006
    severity: note
    category: code-structure
    summary: "Tasks 10 and 19 are large, multi-file, multi-concern units"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
---

# Review: tasks — slice 931

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Event-loop NFR tests are placed in unit files, not the load-test tier, and no CI wiring task exists

The slice design explicitly restates one NFR ("the event-loop constraint above is the one NFR this slice has"). The breakdown acknowledges it twice — Task 3 ("a test times 1,000 calls to `read_chunk_usage` ... mean is under 1 ms per call") and Task 13 ("a five-path batch calls `asyncio.to_thread` exactly once") — but places both in unit test files (`tests/providers/openai/test_usage.py`, `tests/tools/test_read_file.py`). `.claude/rules/python.md` requires the load-test tier (`tests/load/`) for "network, concurrency, or environment-layer paths," and the repo's existing precedent (`tests/load/test_grep_timeout.py`) covers exactly this `asyncio.to_thread` + event-loop-starvation concern for the same `squadron.tools` package, with a docstring citing the tier rule. Neither NFR test is a `tests/load/` task, and no task wires load-test gating into CI (the Python rule states "CI must gate load tests for slices touching these paths"; `.github/workflows/ci.yml` runs a single `uv run pytest`, leaving gating implicit rather than an explicit step). Add a `tests/load/` task (or move the two NFR tests there) and make the CI gate explicit.

### [CONCERN] Task 4B's equality assertion contradicts the extra credential keys four sites carry

Task 4B instructs: "Add a parametrized test asserting each site's built `credentials` equals `profile_credentials(profile)` for the same profile." But `profile_credentials` per the design returns only `api_key_env`, `default_headers`, `sends_stream_usage`. Four of the six call sites carry additional keys today: `review/review_client.py` adds `hooks` and `mode` (lines 227-229), `pipeline/summary_oneshot.py` adds `hooks` and `mode` (lines 121-122), `pr/composer.py` adds `hooks` and `mode` (lines 90-91), and `metrology/audit.py` adds `mode`, `max_rate_limit_retries`, and `rate_limit_cap_s` (lines 653-656). An `==` assertion against `profile_credentials(profile)` would fail for these four. The task should specify a superset/subset assertion (e.g. that `profile_credentials(profile)` is a subset of each site's credentials) and require the extra keys be preserved through the `**profile_credentials(profile)` splat.

### [CONCERN] Task 5 reads `credentials.get("sends_stream_usage")` on the agent, but no task gives the agent a `credentials` member

Task 5 states that `_stream_turn` should gate `stream_options` "unless `credentials.get("sends_stream_usage")` is `False`" and asserts gemini/openrouter/no-profile agent behavior in tests. `OpenAICompatibleAgent.__init__` (agent.py:135-230) has no `credentials` attribute — it holds `_client`, `_model`, `_max_output_tokens`, etc. `providers/openai/provider.py` currently reads only `config.credentials.get("default_headers")` and passes no credential value into the agent constructor. Task 4B adds `sends_stream_usage` to the six call-site `credentials` dicts, but no task adds a constructor parameter to `OpenAICompatibleAgent` and threads the flag from `provider.py`. Without that step, Task 5's gemini/absent-key tests cannot pass. Add an explicit step (in Task 4B or Task 5) to pass the flag from `config.credentials` through `provider.py` into the agent.

### [NOTE] Task 3's `warned`-set cross-reference points at the wrong task

Task 3 says the agent "owns the set and clears it at the top of `handle_message` (Task 6)," but the per-call `warned` attribute is actually created and cleared in Task 5 ("Pass the agent's `warned` set (a new per-call attribute, cleared at the top of `handle_message`, beside `_answering_models`)"). The stale back-reference is harmless but could misdirect a junior implementer to defer the set creation to Task 6.

### [NOTE] Task 6 does not state the stamping order relative to the `_stamp_tool_telemetry` early return

Task 6 says `_stamp_tool_telemetry` "stamps `turns`, `usage`, and `RunTelemetry.reasoning_chars` (run total) onto the final Message metadata," but does not say these new keys must be stamped *before* the `if not self._tools_given: return` early return (as the design's existing stop-reason keys already are). It also does not state whether the tool-less `handle_message` branch (agent.py:242-259) folds its single `_stream_turn` result into `RunTelemetry`. The design's D10 table expects `turns` for an OpenAI review "on success or failure," so both details affect the rendered artifact; call them out explicitly.

### [NOTE] Tasks 10 and 19 are large, multi-file, multi-concern units

Task 10 bundles `review/persistence.py` + `review/models.py` changes (frontmatter, digest, `to_dict()`, failure render) plus tests in two files plus a fixture regeneration. Task 19 bundles the CLI read, `providers/base.py`, `review_client.py`, `review/models.py`, `review/persistence.py`, and tests across four files. Each is internally coherent (one feature) and both follow the repo's "test-with" pattern, so this is a judgment call rather than a defect — but they are the two largest tasks and the design's D10 gives a natural split boundary (rendering vs. provider-record) if they prove unwieldy.

### Run Digest

- Response length: 6383 chars
- Response is newline-free: no
- Tool calls made: 33
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 21312
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
