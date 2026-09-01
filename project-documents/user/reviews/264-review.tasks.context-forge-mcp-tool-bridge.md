---
docType: review
layer: project
reviewType: tasks
slice: context-forge-mcp-tool-bridge
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/264-tasks.context-forge-mcp-tool-bridge.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260831
dateUpdated: 20260831
reviewedSha: af1f3c9783c11cdbe143a60a9aeed03356f0d0d1
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Non-text-block result-mapping rule has no test coverage"
    location: "tests/tools/test_mcp_bridge.py"
  - id: F002
    severity: note
    category: test-coverage
    summary: "Protocol-error failure-mode row's WARNING assertion is left implicit"
    location: "tests/tools/test_mcp_bridge.py"
  - id: F003
    severity: note
    category: cross-task-consistency
    summary: "Timeout-test PID capture depends on fixture behavior Task 3 never specifies"
    location: "tests/tools/fake_mcp_server.py"
  - id: F004
    severity: note
    category: traceability
    summary: "Walkthrough step 4 (SC6 live-model demo) is deferred while the slice is marked complete"
    location: "project-documents/user/tasks/264-tasks.context-forge-mcp-tool-bridge.md"
  - id: F005
    severity: pass
    category: coverage-summary
    summary: "Success criteria coverage, sequencing, scoping, and commit hygiene all check out"
    location: "project-documents/user/tasks/264-tasks.context-forge-mcp-tool-bridge.md"
---

# Review: tasks — slice 264

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [CONCERN] Non-text-block result-mapping rule has no test coverage

The slice design's Result mapping rules (feeding SC2: "maps results per the Result mapping rules") require that non-text blocks in a `CallToolResult` are "noted by type in the content, not dropped." Task 4.2 implements this, but no task ever tests it: the Task 3 fixture exposes only `echo`/`fail`/`sleep`/`empty` (all text or zero-content results), the Task 5 bridge tests never produce a non-text block, and Task 7 mocks `call_mcp_tool`, which bypasses bridge-side mapping entirely. The sibling rule — zero text blocks — got a dedicated fixture tool (`empty`) and an explicit test because it is a called-out lesson; the non-text rule is an equally enumerated mapping rule and currently has implementation but zero verification. Fix: add a `nontext` (or `mixed`) tool to `tests/tools/fake_mcp_server.py` returning an `ImageContent`/`EmbeddedResource` block, plus one assertion in `tests/tools/test_mcp_bridge.py` that the content notes the block type.

### [NOTE] Protocol-error failure-mode row's WARNING assertion is left implicit

The design's failure-mode table states each row "has a test asserting the observable signal." Task 5.1's `test_unknown_tool_name` does exercise the `McpError`/protocol-error path, but Task 5.4's caplog enumeration names only timeout, server `isError`, and spawn failure. A charitable reading of "each failure-mode test above also asserts its WARNING" covers it, but making the caplog assertion explicit in `test_unknown_tool_name` would remove the ambiguity and keep the failure-mode table fully honored.

### [NOTE] Timeout-test PID capture depends on fixture behavior Task 3 never specifies

Task 5.2's preferred teardown assertion is "capture the child PID via the fake server printing it to a temp file at startup," but Task 3.1's fixture spec (four tools, under ~80 lines) never mentions PID emission. A junior implementing Task 3 in isolation will produce a fixture that doesn't support Task 5.2's first-choice mechanism. The stated fallback (scanning for the fixture's command line) works without fixture changes, so this is an ambiguity rather than a blocker — adding "emit PID to a temp file at startup" to Task 3.1's checklist would close it cleanly.

### [NOTE] Walkthrough step 4 (SC6 live-model demo) is deferred while the slice is marked complete

SC6 includes "a dispatch with a tool-capable non-SDK model can call `cf_build_context`" (walkthrough §4). Task 9.3 marks the slice `status: complete` while noting step 4 "remains open alongside 263's demo." This matches the design's own caveat (the `sq run` CLAUDECODE guard requires a standard terminal), so the deferral is legitimate — but SC6 will not be fully evidenced at close-out. Consider an explicit annotation on the slice status or a tracked follow-up so the open demo isn't lost.

### [PASS] Success criteria coverage, sequencing, scoping, and commit hygiene all check out

Cross-reference results: SC1 → Tasks 6 (success criteria), 7.1, 7.4 (`cf_bogus` rejection proves the registry-driven YAML surface); SC2 → Tasks 4.2, 5.1, 7.2–7.3 (modulo the non-text gap above); SC3 → Tasks 5.1, 5.2, 5.4 (round-trip, `isError`, timeout, caplog); SC4 → Tasks 5.3 + 5.4; SC5 → Task 8 (availability-gated, constants imported rather than restated); SC6 → Tasks 8.2, 9.1 (step 4 deferred per note above); SC7 → Task 9.2. Design §Configuration maps to Tasks 1–2; the failure-mode table rows each have a test. Sequencing is acyclic with the fixture (Task 3) correctly preceding its consumers (Tasks 4 smoke, 5). Test-with holds: 2 follows 1, 5 follows 4, 7 follows 6. Commits are distributed per task, not batched. No scope creep detected — every task traces to an In-scope design item or standard close-out. No NFR is restated in the slice, so no load test or CI gating task is required. Task sizes are appropriate (largest are 3/5 with clear sub-steps; the 1/5 config tasks are small but justified by the test-with split), and each task's success criteria are concrete enough for a junior implementer.
