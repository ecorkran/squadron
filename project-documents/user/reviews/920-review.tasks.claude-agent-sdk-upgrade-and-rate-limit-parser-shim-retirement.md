---
docType: review
layer: project
reviewType: tasks
slice: claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/920-tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: b5939ca42bee3eb1ab46871c59eb8950a88b84e0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
findings:
  - id: F001
    severity: concern
    category: task-sequencing
    summary: "Test-with pattern violated: implementation tasks 6–7 break existing tests, rewrites land in tasks 10–11"
    location: "project-documents/user/tasks/920-tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
  - id: F002
    severity: concern
    category: test-coverage-gap
    summary: "Success Criterion 7 (retained substring path) has no integration test through the retry loop"
    location: "project-documents/user/tasks/920-tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
  - id: F003
    severity: concern
    category: task-clarity
    summary: "Task 6 instruction for informational RateLimitEvent handling is internally contradictory"
    location: "project-documents/user/tasks/920-tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
  - id: F004
    severity: note
    category: verification-completeness
    summary: "Task 9 grep verification covers only `src/`, not `tests/` (SC2 says \"in src/ or tests/\")"
    location: "project-documents/user/tasks/920-tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
  - id: F005
    severity: note
    category: code-conventions
    summary: "Task 8 adds string literal `\"rate_limit_event\"` instead of the existing `RATE_LIMIT_EVENT_TYPE` constant"
    location: "src/squadron/pipeline/sdk_session.py:173"
  - id: F006
    severity: note
    category: nfr-load-test
    summary: "No NFR restated; no load test or CI-gating task required — correctly absent"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
---

# Review: tasks — slice 920

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] Test-with pattern violated: implementation tasks 6–7 break existing tests, rewrites land in tasks 10–11

Tasks 6 and 7 rewrite production code in `agent.py` and `sdk_session.py` that existing tests depend on. Task 6 removes the `is_rate_limit_event(exc.data)` special case from `_skip_unparseable` (src/squadron/providers/sdk/agent.py:128), which immediately breaks `test_a_rejected_rate_limit_event_reaches_the_backoff` — that test raises `MessageParseError` with a `rate_limit_event` payload, which after Task 6 would be caught by the general skip branch (WARNING + continue) instead of re-raised, so the test would no longer observe a backoff. Similarly, Task 7 changes the `dispatch` retry gate from `RATE_LIMIT_MARKER in str(exc)` to `_is_throttle(exc)`, but `test_dispatch_retries_on_rate_limit` (tests/pipeline/test_sdk_session.py:208) still raises `ClaudeSDKError("rate_limit_event")`, which the new `_is_throttle` would still match via the substring path — but the test fabricates a dead mechanism and should be rewritten. The test rewrites for both files don't arrive until Tasks 10 and 11, four tasks later. Each task commits individually, so commits after Tasks 6 and 7 would have a broken test suite. The test-with pattern requires test changes to immediately follow the implementation change that necessitates them — either by merging the test rewrite into the implementation task or by ordering them adjacently.

### [CONCERN] Success Criterion 7 (retained substring path) has no integration test through the retry loop

Success Criterion 7 requires "a genuine 429 surfaced as a plain `ClaudeSDKError` containing `rate_limit` still triggers backoff — the substring path is retained, not replaced." Task 2 retains this path in `_is_throttle`, and Task 3 unit-tests `_is_throttle(ClaudeSDKError("rate_limit_event: slow down"))` returning `True`. However, Task 10 rewrites ALL three existing retry-loop tests (`test_retries_actually_sleep`, `test_stats_accumulate_across_retries`, `test_exhausted_rate_limit_raises_a_distinct_error`) from `ClaudeSDKError("rate_limit_event: ...")` to real `RateLimitEvent` objects. After the rewrite, no test exercises a plain `ClaudeSDKError` through the actual backoff loop — the substring path is tested only at the helper level, not through the integrated retry loop where a regression (e.g., a future change dropping the substring check from `_is_throttle`) would go undetected. The task breakdown should retain or add at least one retry-loop test using a plain `ClaudeSDKError` (with `rate_limit` in its text, not a `rate_limit_event` payload) to cover SC7 end-to-end.

### [CONCERN] Task 6 instruction for informational RateLimitEvent handling is internally contradictory

Task 6 states for the informational case: "log at DEBUG and continue the loop without yielding it to the caller as a raw SDK type — let it flow to translation as normal." These two clauses are mutually exclusive: if the event is not yielded from `_skip_unparseable`, it cannot reach `translate_sdk_message` in the consumer loop (`async for sdk_msg in self._skip_unparseable(stream): for translated in translate_sdk_message(sdk_msg, ...)`). The slice design compounds this: D4 says "informational events must not reach translation," while D6 says "an informational one becomes observable rather than dropped," and the Data Flow diagram says "(informational path continues to translation)" for the agent path. The intended behavior (per D4) is that the agent path skips informational events without yielding them, while the pipeline path (Task 7) lets them reach translation. A junior AI could implement either direction, and the wrong choice either leaks rate-limit notices into review/summary/audit prose (if yielded) or drops them silently in the pipeline path (if not).

### [NOTE] Task 9 grep verification covers only `src/`, not `tests/` (SC2 says "in src/ or tests/")

Success Criterion 2 states no `install_rate_limit_parser_shim` remains "in `src/` or `tests/`." Task 9's success check greps only `src` (`grep -rn "install_rate_limit_parser_shim" src`). The four shim-specific tests in `test_agent.py` that import `install_rate_limit_parser_shim` from `claude_agent_sdk._internal` are deleted in Task 10, but no task explicitly greps `tests/` to confirm the symbol is fully gone from the test suite. A `grep -rn "install_rate_limit_parser_shim" tests` after Task 10 would close this gap.

### [NOTE] Task 8 adds string literal `"rate_limit_event"` instead of the existing `RATE_LIMIT_EVENT_TYPE` constant

Task 8 instructs adding `"rate_limit_event"` to the exclusion tuple at sdk_session.py:173. The constant `RATE_LIMIT_EVENT_TYPE = "rate_limit_event"` already exists in rate_limit.py:46, and `sdk_session.py` already imports from that module. CLAUDE.md states: "Never scatter comparison values across code... define it once (enum, constant, or config) and reference that definition everywhere." The existing tuple uses literals for `"tool_use"` and `"tool_result"` (which have no constants), but `rate_limit_event` does have a canonical constant. Using the literal is consistent with the local pattern but reintroduces a second definition of the string. Importing `RATE_LIMIT_EVENT_TYPE` and using it would satisfy the project convention.

### [NOTE] No NFR restated; no load test or CI-gating task required — correctly absent

The slice design mentions "throughput collapse" only when describing the original bug's symptom, not as a restated NFR or performance criterion. All 11 success criteria are functional or behavioral. The "if the parent slice restates an NFR, a load test task exists in `tests/load/`" rule does not trigger, and no CI-gating task is required. This is correctly absent rather than a gap.

### Run Digest

- Response length: 6694 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 36531
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
