---
docType: review
layer: project
reviewType: tasks
slice: run-liveness-stall-bounds-pruning-and-readable-listings
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/174-tasks.run-liveness-stall-bounds-pruning-and-readable-listings.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 875d199b2949281a7143a0d82cd548ac4c77cde4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
turns: 10
promptTokens: 268147
cachedTokens: 229248
completionTokens: 19399
reasoningTokens: 17649
durationSeconds: 90.0
runId: run-20261007-p5-6aea1f6e
squadronVersion: 0.21.0
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "Restated listing-time NFR has no `tests/load/` task"
    location: "project-documents/user/tasks/174-tasks.run-liveness-stall-bounds-pruning-and-readable-listings.md"
  - id: F002
    severity: note
    category: test-coverage
    summary: "Item-resume path asserted only indirectly"
    location: "project-documents/user/tasks/174-tasks.run-liveness-stall-bounds-pruning-and-readable-listings.md"
  - id: F003
    severity: note
    category: task-scoping
    summary: "`ActiveItem` definition split across two tasks"
    location: "project-documents/user/tasks/174-tasks.run-liveness-stall-bounds-pruning-and-readable-listings.md"
---

# Review: tasks — slice 174

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Restated listing-time NFR has no `tests/load/` task

The slice design restates an NFR under Success Criteria / Functional Requirements: "`sq runs list --all` stays under 1 s with a few hundred run-state files on local disk (199's advisory target, restated in Special Considerations)." The breakdown has no task that adds a `tests/load/` case covering it. Task 22 only "extends the I/O-bounds test with 20 running runs" and asserts `process_alive` call counts and load counts — a resource-count assertion that lives in `tests/pipeline/test_run_listing.py`, not `tests/load/`, and that asserts no latency. Task 42 step 8 merely *measures* wall-clock time manually (`time sq runs list --all`) and explicitly records "there is still no assertion on time in tests." The listing path is filesystem/environment-layer (`StateManager` file reads plus one `os.kill(pid, 0)` per running run) and now runs `process_alive` per row, so `.claude/rules/python.md`'s load-test tier applies. No load test task exists, and consequently no CI-gating task for it either (CI picks up `tests/load/` implicitly via `testpaths = ["tests"]`, so gating is left implicit). Add a load test task (e.g. `tests/load/test_run_listing_scale.py` asserting the wall-clock bound with a few hundred seeded run-state files) so the restated NFR is enforced.

### [NOTE] Item-resume path asserted only indirectly

A Success Criteria item states "A new SDK run, a resumed run and an item-resumed run each record `owner` and set `status: running` at start." Task 13's implementation covers all three SDK paths (`claim=True` on resume and item-resume), but the verification in Task 14 only asserts "a resumed run is `running` with an owner while the executor runs, and `failed` or `completed` after" — the item-resumed (`--item`) case is not named in the test bullet. Consider adding an explicit `--item` resume assertion, or extend the CLI-level test to parametrize over the three paths.

### [NOTE] `ActiveItem` definition split across two tasks

Task 4 ("define `ActiveItem` (D2) in `state.py` now so the module imports it") and Task 8 ("add the five `RunState` fields from D2") both touch the D2 model additions in `state.py`. This is not a defect — Task 4 needs `ActiveItem` before the observer refactor can land, and Task 8 adds `RunOwner` plus the `RunState` fields — but the split of the same model block across a "no-behaviour-change" refactor task and the schema task is worth a one-line note in Task 8 so the implementer knows `ActiveItem` already exists.

### Run Digest

- Response length: 3502 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 67608
- Effort: backend default
- Turns: 10
- Tokens — prompt / cached / completion / reasoning: 268147 / 229248 / 19399 / 17649
- Duration: 90.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 3
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 3
- Finding-shaped matches — surviving validation: 3
