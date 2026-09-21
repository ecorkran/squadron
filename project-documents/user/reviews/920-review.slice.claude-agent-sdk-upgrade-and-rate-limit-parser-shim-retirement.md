---
docType: review
layer: project
reviewType: slice
slice: claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 5380878e4bd14286afcd727c79062ed47baeed81
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Slice scope aligns precisely with the architecture's maintenance container definition"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Dependency directions and layer responsibilities are correct"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Integration points match consuming/providing slice expectations — the pipeline dispatch asymmetry is correctly identified"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md#decision-d4--raise-a-typed-signal-at-dispatch-not-a-new-control-path"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Failure modes for the new RateLimitEvent message type are enumerated with explicit handling strategies"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md#data-flow"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Probe findings replace assumptions with verified compatibility facts"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md#probe-findings"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Test integrity criteria prevent false confidence against a dead path"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md#success-criteria"
  - id: F007
    severity: concern
    category: scope-accuracy
    summary: "OpenAI test file listed as affected has no SDK rate-limit dependency"
    location: "project-documents/user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md"
---

# Review: slice — slice 920

**Verdict:** PASS
**Model:** z-ai/glm-5.2

## Findings

### [PASS] Slice scope aligns precisely with the architecture's maintenance container definition

The architecture document (900-arch.maintenance-and-refactoring.md) defines this initiative's scope as including "Dependency management: Version bumps, migration to newer APIs, removing unused dependencies," "Tech debt: Code that works but should be restructured for clarity, performance, or maintainability," and "Bug fixes: Non-trivial bugs that don't belong to an active feature slice." This slice does all three: it bumps the claude-agent-sdk pin (dependency management), removes ~50 lines of monkey-patching against SDK private modules (tech debt removal), and re-keys throttle detection off a typed event rather than an exception substring match (bug fix for issue #30). The architecture also says "Slices in this initiative should be small and focused — prefer many small slices over few large ones" and "Each slice should be independently deliverable." This slice is independently deliverable (no dependencies on other slices, as confirmed by `dependencies: []`) and tightly focused on one mechanism. The explicitly-out-of-scope section (lines 130–157) correctly fences off new SDK methods, StreamEvent/ConversationResetMessage handling, and optional-dependency restructuring (slice 907), preventing scope creep.

### [PASS] Dependency directions and layer responsibilities are correct

The slice's changes are confined to `providers/sdk/rate_limit.py`, `providers/sdk/agent.py`, `providers/sdk/translation.py`, `providers/sdk/provider.py`, and `pipeline/sdk_session.py`. Verified against the source: `sdk_session.py` already imports from `squadron.providers.sdk.rate_limit` (line 30) and `squadron.providers.sdk.translation` (line 31), so the pipeline→provider-sdk dependency direction is pre-existing, not introduced by this slice. The new `RateLimitRejected` exception subclasses `ClaudeSDKError` and lives in the SDK provider layer (`rate_limit.py`), which is the correct layer for SDK-specific error types. The new `event_blocks` function and `_is_throttle` helper follow the same module placement as the existing `rate_limit_event_blocks` and `RATE_LIMIT_MARKER`, maintaining the single-home-for-rate-limit-policy pattern already established. No new cross-layer dependencies are introduced; no architectural boundaries are violated.

### [PASS] Integration points match consuming/providing slice expectations — the pipeline dispatch asymmetry is correctly identified

The slice identifies that `sdk_session.dispatch` (sdk_session.py:152) iterates `self.client.receive_response()` directly without the `_skip_unparseable` wrapper that `agent.py` uses in both query and client modes. Verified against source: `sdk_session.py` line 152 shows `async for sdk_msg in self.client.receive_response():` with no `_skip_unparseable` wrapper, while `agent.py` wraps both paths (lines 108, 163). The design correctly calls this asymmetry "the most likely place for the slice to half-land" and mandates inline inspection at that site (D4). Additionally, D6 correctly identifies the `sdk_type` exclusion set in `sdk_session.dispatch` (verified at sdk_session.py:~175, filtering `SDK_RESULT_TYPE`, `"tool_use"`, `"tool_result"`) and requires adding `"rate_limit_event"` to that set to prevent rate-limit notices from concatenating into returned prose — issue #23's exact defect class. This is a concrete integration-point verification, not a hand-wave.

### [PASS] Failure modes for the new RateLimitEvent message type are enumerated with explicit handling strategies

The design enumerates explicit handling for each `RateLimitEvent` status: `rejected` → raise `RateLimitRejected` → existing `except ClaudeSDKError` catches it → backoff/retry; informational (`allowed`/`allowed_warning`) → DEBUG log, skip, stream continues; unknown future type → existing `_skip_unparseable` WARNING + skip. The design also explicitly addresses the stream-lifecycle difference: under the old parser, a `MessageParseError` permanently killed the SDK generator (requiring full query restart), whereas with native parsing the stream is alive when the event arrives, so the existing restart-on-retry is safe but an in-stream pause optimization is explicitly deferred. The risk assessment section names four distinct failure modes with impact/likelihood ratings and concrete mitigations. No failure mode is left as "TBD" or implicit.

### [PASS] Probe findings replace assumptions with verified compatibility facts

The design verifies all 14 public names squadron imports, all 9 `ClaudeAgentOptions` fields, and all 3 private module shapes against the actual 0.2.152 release in a throwaway venv. It confirms `RateLimitEvent` fields, `RateLimitStatus` literal values, and that both `rejected` and `allowed_warning` payloads parse without raising. This follows the architecture's intent for maintenance slices to be evidence-based rather than speculative, and it de-risks the upgrade by establishing that the public API surface held across the bump before designing the changes.

### [PASS] Test integrity criteria prevent false confidence against a dead path

Success criteria 9–10 directly address the antipattern of tests that pass against a broken implementation. Verified against the test files: `tests/providers/sdk/test_agent.py` constructs `MessageParseError` with `rate_limit_event` payloads (lines 658–668) and `ClaudeSDKError("rate_limit_event: ...")` (lines 526, 562, 612, 639); `tests/pipeline/test_sdk_session.py` constructs `ClaudeSDKError("rate_limit_event")` (line 208). These tests simulate the old parse-failure mechanism that will no longer occur after the upgrade. Criterion 9 requires rewriting them to yield real `RateLimitEvent` objects, and criterion 10 requires an explicit assertion that informational events do not trigger backoff — the regression that would re-break issue #23. The verification walkthrough also mandates live end-to-end testing (steps 3–5) because unit tests alone cannot detect the silent-loss-of-backoff failure mode.

### [CONCERN] OpenAI test file listed as affected has no SDK rate-limit dependency

The "Affected test files" list (after success criterion 11) includes `tests/providers/openai/test_agent.py`. Verified against the file's contents: the only rate-limit test in that file is `test_error_rate_limit` (line 166), which constructs `openai.RateLimitError` — the OpenAI Python SDK's own rate-limit exception, mapped to `ProviderAPIError(status_code=429)`. The file contains no `MessageParseError`, no `ClaudeSDKError("rate_limit_event...")`, and no import of `claude_agent_sdk` at all. Success criterion 9 requires rewriting tests that construct `MessageParseError` or `ClaudeSDKError("rate_limit_event: ...")`, but the OpenAI test constructs neither — it is on an entirely independent error path in a different provider. Listing this file as affected is inaccurate and could mislead an implementer into modifying an unrelated provider's tests. The file should either be removed from the list or the list should clarify that it is included only as a "must-not-break" regression check (which the verification walkthrough's `pytest tests/providers` already covers implicitly), not as a file requiring the criterion-9 rewrite.

### Run Digest

- Response length: 8401 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 2
- Stop reason: stop
- Reasoning characters: 17189
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
