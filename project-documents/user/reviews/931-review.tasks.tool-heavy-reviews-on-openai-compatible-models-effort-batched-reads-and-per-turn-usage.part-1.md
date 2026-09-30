---
docType: review
layer: project
reviewType: tasks
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20260929
dateUpdated: 20260929
reviewedSha: c444e4a4670dc6bcbfcc876debe5c4ac01ecfb4d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
runId: run-20260930-p5-f12cfe4d
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 10 commits a knowingly failing test, contradicting the stated per-commit-green invariant"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md:278-280"
  - id: F002
    severity: concern
    category: api-contract
    summary: "`read_chunk_usage` signature both self-contradicts and diverges from the design contract"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md:74-83"
  - id: F003
    severity: note
    category: test-coverage
    summary: "One D12 row delegates to \"existing 4xx tests\" with no task to confirm they cover the new parameters"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
  - id: F004
    severity: note
    category: task-granularity
    summary: "Task 5 bundles flag wiring across provider and agent, plus five test scenarios"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md:126-158"
  - id: F005
    severity: pass
    category: nfr-coverage
    summary: "Load tests for the event-loop NFR exist and CI gating is explicitly resolved"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md:305-316"
---

# Review: tasks — slice 931

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Task 10 commits a knowingly failing test, contradicting the stated per-commit-green invariant

Task 10 instructs committing the code and tests "**without** the snapshot fixture" and states "Expected: the `clean_pass_artifact.md` snapshot test fails until Task 10B." The document's own Context Summary asserts the invariant this violates: "Each part lands as its own commits, each green on the full suite and revertible alone." The slice design repeats it ("Each commit passes the full suite on its own"). A commit whose tree has a failing test is not green and is not independently revertible — reverting Task 10B alone leaves Task 10 red, and CI (`.github/workflows/ci.yml` runs `uv run pytest`) would fail on that commit if ever pushed or bisected. The design permits regenerating the fixture once (D10); it does not require splitting it across two commits. Either fold the fixture regeneration into Task 10, or drop the "green on the full suite" claim from the Context Summary so the plan is internally consistent.

### [CONCERN] `read_chunk_usage` signature both self-contradicts and diverges from the design contract

Task 3 opens by specifying the reader as `read_chunk_usage(chunk) -> TokenUsage | None` (line 75), then later states "Signature is `read_chunk_usage(chunk, warned: set[str])`" (line 83). A junior implementer reading the first bullet will build the wrong signature. Separately, the design's API Contracts section declares the same reader as `read_chunk_usage(chunk) -> TokenUsage | None`, with no `warned` parameter — so the task introduces a parameter the design's stated interface does not carry. The intent (achieving the D12 "once per call" WARNING without agent state in the reader) is reasonable, but it is a contract change that should be stated once, unambiguously, and reconciled with the design so the two documents agree.

### [NOTE] One D12 row delegates to "existing 4xx tests" with no task to confirm they cover the new parameters

Success criterion 13 requires that "Each D12 failure mode with a listed signal emits it." The D12 row "Backend rejects `reasoning_effort` or `stream_options` (400)" lists its test as "Covered by existing 4xx tests," and no task in either file inspects or extends those tests to ensure they now exercise `reasoning_effort`/`stream_options` (the request shape this slice changes). Relative to every other D12 row, which gets an explicit assertion, this is the sole un-verified signal. A one-line task bullet confirming an existing 4xx test covers the new request path would close the gap; without it, Task 11/Task 23's "every D12 row" claim is untested for this row.

### [NOTE] Task 5 bundles flag wiring across provider and agent, plus five test scenarios

Task 5 changes three files (`providers/openai/provider.py` `create_agent`, the agent constructor, and `_stream_turn`), and carries five distinct test bullets spanning two chunk shapes, three profile shapes, and the no-effort equivalence. It is coherent and each sub-item is actionable, so I am not flagging it as blocking — but it is on the large side for a single commit, and splitting the constructor/`create_agent` wiring from the `_stream_turn` read would make each diff independently reviewable, consistent with how Task 4/4B separates the helper from its call sites.

### [PASS] Load tests for the event-loop NFR exist and CI gating is explicitly resolved

The slice's one NFR (the event loop must not be starved by per-chunk usage reads or batched file reads) is covered by load tests in `tests/load/` (Task 11 for `read_chunk_usage`; Task 15 for the read batch), styled after the existing `tests/load/test_grep_timeout.py`. CI gating is not left implicit: Task 11 states that `.github/workflows/ci.yml` runs `uv run pytest` over `testpaths = ["tests"]`, which includes `tests/load/`. I verified this claim — `pyproject.toml:83` sets `testpaths = ["tests"]`, `pyproject.toml:81-90` has no `addopts` exclusion, and `.github/workflows/ci.yml:38` runs `uv run pytest` — so the load tests do run in CI without a separate wiring task.

### Run Digest

- Response length: 5559 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 32644
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
