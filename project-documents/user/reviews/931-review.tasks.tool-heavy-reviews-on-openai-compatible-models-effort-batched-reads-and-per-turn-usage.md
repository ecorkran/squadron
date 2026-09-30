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
reviewedSha: 467ed4555b2799edd89de4be68bf286eab5379a9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
runId: run-20260930-p5-f12cfe4d
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Every functional success criterion traces to a task"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Sequencing and test-with pattern are sound"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F003
    severity: concern
    category: uncategorized
    summary: "The slice's one stated NFR has no load test task"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F004
    severity: note
    category: uncategorized
    summary: "Two task interfaces are left as an open choice"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F005
    severity: note
    category: uncategorized
    summary: "Task 4 and Task 6 are large but defensible"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
---

# Review: tasks — slice 931

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Every functional success criterion traces to a task

I cross-referenced the slice design's Success Criteria (Functional 1–13, Technical, Integration) against the tasks. Effort send/mapping/warn/invalid (1–4) → Tasks 17, 18, 19, 20, 21, 22. Request parity when unset (5) → Tasks 5, 20. `read_file` path/paths/budget/is_error (6) → Tasks 12, 13. Guidance paragraph (7) → Task 14. Summed usage + turns + run-total reasoning chars (8) → Tasks 5, 6, 8, 10. Unreported-never-zero (9) → Task 10 tests. Empty-final-turn contribution (10) → Tasks 6, 8. durationSeconds for every provider (11) → Task 9. Mid-loop failure artifact + D12 warnings (12) → Tasks 7, 10, 23. D12 signals (13) → Tasks 3, 5, 6, 7, 13. Integration parity and `cf validate frontmatter` → Tasks 19, 23. No criterion is orphaned, and no task implements behavior outside the design.

### [PASS] Sequencing and test-with pattern are sound

Dependencies flow correctly: `core/usage` (Task 2) precedes its consumers (Tasks 3, 6, 8); `profile_credentials`/`sends_stream_usage` (Task 4) precedes the agent that reads the flag (Task 5); the `ProviderError.telemetry` extension (Task 7) precedes `fold_empty_turn` reading it (Task 8). Task 12 adds a byte-identical characterization test before the source extraction, and every implementation task carries its tests and a semantic commit. No circular dependencies.

### [CONCERN] The slice's one stated NFR has no load test task

The slice restates a performance/concurrency NFR in Special Considerations ("`_stream_turn` runs inside the event loop … well under the 1 ms rule. `read_file` batches keep every blocking read inside the one existing `asyncio.to_thread` call … a hung read never blocks the event loop") and calls it out explicitly: "The event-loop constraint above is the one NFR this slice has." The task file contains no `tests/load/` task exercising that constraint. `tests/load/test_grep_timeout.py` already has an event-loop-liveness harness (`probe_ticks`), but nothing gates the new per-chunk usage read or the batched-read path against it. Per the review rules, a restated NFR should have a load test task in `tests/load/` (or this breakdown should add one). Either add a load task asserting the batch read stays on one worker hop and does not stall the loop, or state in the task file that the NFR is covered by inspection — otherwise the claim is untested.

### [NOTE] Two task interfaces are left as an open choice

Task 3 leaves the malformed-usage logging mechanism undecided ("takes a caller-owned set of already-warned field names, or returns the malformed field names for the caller to log … pick one"), and Task 9 leaves the `ReviewResult` shape open ("`turns`, `usage` (or the four token fields)"). Neither breaks downstream tasks, but a junior implementer has to choose the contract that Task 6 and Task 10 then depend on. Pinning one here would remove an unnecessary decision point.

### [NOTE] Task 4 and Task 6 are large but defensible

Task 4 bundles the profile flag, the new `profile_credentials` helper, six call-site migrations, and a parametrized parity test; Task 6 bundles loop accumulation, stamping, exception telemetry, the `completed`-flag exit warning, and two once-per-call warnings. Both are coherent single-file changes with their own commits and existing-test guards (the design mandates the six-site migration so `sends_stream_usage` reaches the agent from one definition), so neither crosses into scope creep. Flagging only so the implementer keeps each diff reviewable rather than squatting in one task.

### Run Digest

- Response length: 4780 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 17491
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
