---
docType: review
layer: project
reviewType: code
slice: deterministic-task-file-gate
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/933-slice.deterministic-task-file-gate.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261011
dateUpdated: 20261011
reviewedSha: 0f5b912d628c436d05acd79d76452e4e4cd2e7bd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
durationSeconds: 21.3
squadronVersion: 0.21.3
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Unreadable task file reaches the pipeline's catch-all handler"
    location: "src/squadron/pipeline/actions/review.py:487-510"
  - id: F002
    severity: concern
    category: async
    summary: "Synchronous file reads and regex scans inside an async function"
    location: "src/squadron/pipeline/actions/review.py:487-510"
  - id: F003
    severity: concern
    category: design
    summary: "Gate control flow in `review_tasks` is harder to follow than needed"
    location: "src/squadron/cli/commands/review.py:1053-1090"
  - id: F004
    severity: concern
    category: dry
    summary: "Pipeline and CLI duplicate the gate-result handling"
    location: "src/squadron/pipeline/actions/review.py:487-510"
  - id: F005
    severity: note
    category: style
    summary: "Line length exceeds the 88-character standard"
    location: "src/squadron/cli/commands/review.py:626"
  - id: F006
    severity: note
    category: parsing
    summary: "Regex-heuristic gate depends on tuned patterns and real-world fixtures"
    location: "src/squadron/review/task_gate.py:58-95"
  - id: F007
    severity: pass
    category: testing
    summary: "Test coverage and structure"
    location: "tests/review/test_task_gate.py"
---

# Review: code — slice 933

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Unreadable task file reaches the pipeline's catch-all handler

The CLI path catches `TaskFileReadError` in `_gate_task_parts` and reports it with a clean exit. `_gated_parts` calls `gate_task_files` with no handling for it. The error propagates to `execute()`'s broad `except Exception` at line 175, which logs "unexpected error" and returns a generic exception result. The failure is observable, so it isn't silent. But a missing or undecodable task file is an expected input failure, not an unexpected bug. Catch `TaskFileReadError` explicitly and return a clear failed `ActionResult`, as the CLI does. Also add a pipeline test for this case. `test_task_gate_files.py` covers the raise, but neither the CLI nor the pipeline test files cover the unreadable-file case.

### [CONCERN] Synchronous file reads and regex scans inside an async function

`_gated_parts` is awaited on the event loop and calls `gate_task_files`, which does disk reads and runs several regexes per line. The Python rules say sync code in async functions must be guaranteed to run in under 1ms in the worst case. The docstring argues the files are small, but that is not a guarantee. Disk latency on a network mount, or a large split task file, can exceed 1ms. Use `asyncio.to_thread`, or document an explicit exemption.

### [CONCERN] Gate control flow in `review_tasks` is harder to follow than needed

The loop uses `if gate_results:` / `else:` to choose between two unrelated behaviors. In the gated branch, clean parts are skipped with `continue`. The model branch is an `else` that was re-indented around the original body, which makes the diff larger. Short-circuiting before the loop is clearer. If `gate_results` is non-empty, process only the gated parts and skip the model loop. `_exit_on_missing_inputs` also now runs twice per part, once in `_gate_task_parts` and again inside `_run_review_command`. The repeat is harmless but redundant.

### [CONCERN] Pipeline and CLI duplicate the gate-result handling

Both callers independently iterate parts, look up `gated.get(part_input)`, and skip clean parts. The shared `gate_task_files` entry point helps. The per-part selection logic is still duplicated, so the CLI and pipeline could drift on it. The new `test_cli_and_pipeline_write_identical_gate_artifacts` test partly mitigates this.

### [NOTE] Line length exceeds the 88-character standard

Several new lines are longer than 88 characters. Examples are the `rprint(f"[red]Error: ...` line, the `part_inputs = [...]` line, and the `raise TaskFileReadError(...)` and `scans = [...]` lines in `task_gate_files.py`. This is fine if the project's ruff config sets a larger limit. I did not check that config.

### [NOTE] Regex-heuristic gate depends on tuned patterns and real-world fixtures

The patterns are defined in one table, use edge guards for `merge-base` and `--no-merges`, and are tested against real excerpts and a negatives list. That matches the project's parsing guidance. The `git_object_window` rule, with bare `main` and `target` as objects, still carries a false-positive risk. One example is "Merge main-branch config" if the edge guards miss it. Because a hit hard-fails the review with no model call, consider logging pattern names in findings to ease triage.

### [PASS] Test coverage and structure

Tests were written alongside the code. They cover unit scanning, the window boundary, frontmatter and prose exclusion, FAIL result fields, artifact round-trip, CLI and pipeline no-model-call guarantees, partial-part saving, and non-task templates not being gated. The shared helpers are in `tests/review/task_gate_support.py`. The `task_gate.py` module is I/O-free and the file reads are isolated in `task_gate_files.py`, which gives a clean separation.

### Run Digest

- Response length: 4296 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 21.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
