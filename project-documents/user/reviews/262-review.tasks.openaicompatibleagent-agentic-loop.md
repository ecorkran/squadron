---
docType: review
layer: project
reviewType: tasks
slice: openaicompatibleagent-agentic-loop
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/262-tasks.openaicompatibleagent-agentic-loop.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260829
dateUpdated: 20260829
reviewedSha: e9bc2786870429a8faa369574e302b220108ae62
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 2 depends on a helper function Task 3 hasn't built yet"
    location: "project-documents/user/tasks/262-tasks.openaicompatibleagent-agentic-loop.md:146-147"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Success criterion 2 (config→constructor threading) has no dedicated automated test for the tools-configured path"
    location: "project-documents/user/tasks/262-tasks.openaicompatibleagent-agentic-loop.md:170-178"
  - id: F003
    severity: pass
    category: completeness
    summary: "All 15 slice-design success criteria trace to specific tasks"
    location: "project-documents/user/tasks/262-tasks.openaicompatibleagent-agentic-loop.md:471-497"
  - id: F004
    severity: pass
    category: process
    summary: "Commit checkpoints are distributed per task group, not batched"
    location: "project-documents/user/tasks/262-tasks.openaicompatibleagent-agentic-loop.md"
  - id: F005
    severity: pass
    category: scope
    summary: "No NFR restated in the slice design; no `tests/load/` or CI-gating gap"
    location: "project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md"
  - id: F006
    severity: note
    category: clarity
    summary: "Minor implementation-choice ambiguity in Task 4.3"
    location: "project-documents/user/tasks/262-tasks.openaicompatibleagent-agentic-loop.md:255-256"
---

# Review: tasks — slice 262

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Task 2 depends on a helper function Task 3 hasn't built yet

Task 2.1 ("Extend `OpenAICompatibleAgent.__init__`") instructs: "Build `self._tool_schemas` once from the materialized names via the schema helper (Task 3.1)." But `build_tool_schemas` is not implemented until Task 3.1 (line 188), which is sequenced *after* Task 2 in the document and after Task 2's own commit checkpoint (2.4, line 179-182). The task file's own stated cadence contract (lines 93-98) requires "each group ends with a commit step" and "every commit must leave the tree in a state where `pytest tests/providers/openai/ -q` passes." Executed literally in order, Task 2's implementation calls a `translation.build_tool_schemas` that doesn't exist yet, which would break the import/tests before Task 2.4's commit can be made cleanly. Fix: either swap the order of Task 2 and Task 3 (translation helpers have no dependency on the constructor work), or pull `build_tool_schemas` specifically ahead of Task 2.

### [CONCERN] Success criterion 2 (config→constructor threading) has no dedicated automated test for the tools-configured path

Task 2.3 threads `config.allowed_tools`/`config.cwd` through `OpenAICompatibleProvider.create_agent` into the constructor — this is exactly the "structural gap" the slice calls out as real work (design lines 36-38: "the agent constructor never receives `allowed_tools` or `cwd`... they stop at `create_agent`"). Its stated success bar is only: `test_provider.py` passes *unmodified* (which only exercises the no-tools case) plus "a manual read of the diff." There is no automated test that constructs an `AgentConfig` with a non-empty `allowed_tools`/`cwd`, calls `create_agent`, and asserts the resulting agent actually received/materialized them. A future refactor of `provider.py` could silently drop this wiring and nothing in the test suite would catch it — the exact "correctness-of-cost" property the slice is built to guarantee. Suggest adding one unit test in Task 2.3 or 2.2 that exercises `create_agent` (not just the constructor directly) with a populated `allowed_tools`/`cwd` and asserts the agent's `_tool_executors`/`_cwd` reflect the config.

### [PASS] All 15 slice-design success criteria trace to specific tasks

The task file's closing "Success Criteria (from the design, restated as a checklist)" section maps each of the slice design's 15 bulleted criteria (design lines 366-394) 1:1 to concrete task numbers (e.g., criterion 9 — cwd=None raise — to Tasks 2.1/2.2; criterion 14 — append-only history — to Task 6.6). Cross-checking each mapping against the referenced task's actual content confirms no gaps and no criterion left unaddressed. No scope-creep tasks were found either — every task (branch setup, config keys, constructor threading, translation helpers, `_stream_turn` split, tool execution, the loop itself, full-suite verification, close-out) traces back to either a success criterion or standard slice-closure process.

### [PASS] Commit checkpoints are distributed per task group, not batched

Each of Tasks 1 through 6 ends with its own commit subtask (1.3, 2.4, 3.5, 4.4, 5.3, 6.8), each preceded by `ruff format` and gated on `pytest tests/providers/openai/ -q` passing (aside from the Task-2/Task-3 ordering issue noted above). Task 7 adds a conditional fix-up commit only if needed, and Task 8 closes out with a final docs commit. This matches the slice's stated intent ("Commit per task group, not once at the end, mirroring slice 261," line 36) and the reviewer instruction to check for end-batched commits.

### [PASS] No NFR restated in the slice design; no `tests/load/` or CI-gating gap

The design's loop-limit config keys (`agent.max_tool_iterations`, `agent.max_history_chars`) are framed as operational safety caps with an explicitly "unmeasured starting value" (design lines 240-242), not a throughput/latency/concurrency SLA. This matches the established pattern in this project's other slice-task reviews (e.g. 261, 302, 322, 910 reviews all conclude "no NFR restated → no `tests/load/` task needed"). No load-test or CI-gating task is missing here.

### [NOTE] Minor implementation-choice ambiguity in Task 4.3

Task 4.3's title, "Rebuild `_call_api` (or inline it into `handle_message`) on top of `_stream_turn`," leaves open whether `_call_api` should remain a named method or be folded directly into `handle_message`. Low impact since the task's success bar is behavior-based (all 15 original tests pass unmodified), so either implementation choice satisfies it — but a junior AI could reasonably ask which is intended. Worth a one-line clarification before implementation, not a blocker.
