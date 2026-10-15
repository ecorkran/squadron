---
docType: test-fixture
project: squadron
slice: usage-and-cost-tracking
dateCreated: 20261014
dateUpdated: 20261014
---

# SDK result fixtures

`result_message_real.json` is the JSON result object from one real Claude CLI call. The SDK parses that object into `ResultMessage`, passing `usage` through unchanged.

- Capture command: `claude -p --output-format json "Reply with the word ok."`
- `claude` CLI: 2.1.296
- `claude-agent-sdk`: 0.2.162 (the pinned version)

Sanitizing: `result` was replaced with `"ok"` and `session_id` with a placeholder. Only the fields `ResultMessage` declares were kept: `subtype`, `duration_ms`, `duration_api_ms`, `is_error`, `num_turns`, `stop_reason`, `total_cost_usd`, `usage`, `session_id`, `result`. `usage` is exactly as emitted.
