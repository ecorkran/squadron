---
docType: review
layer: project
reviewType: tasks
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20260929
dateUpdated: 20260929
reviewedSha: c444e4a4670dc6bcbfcc876debe5c4ac01ecfb4d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
runId: run-20260930-p5-f12cfe4d
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "Task 10 commits a knowingly failing test suite, contradicting the design's per-commit-green invariant"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
  - id: F002
    severity: note
    category: uncategorized
    summary: "Task 3 changes the `read_chunk_usage` signature from the design's stated contract"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
  - id: F003
    severity: note
    category: uncategorized
    summary: "Task 23 skips walkthrough step 1, a prerequisite for the steps it runs"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Load-test tasks exist and CI gating is explicit and verified"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Success-criteria-to-task cross-reference is complete"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md"
---

# Review: tasks — slice 931

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Task 10 commits a knowingly failing test suite, contradicting the design's per-commit-green invariant

Task 10 instructs the implementer to "commit the code and tests **without** the snapshot fixture" and marks "Expected: the `clean_pass_artifact.md` snapshot test fails until Task 10B." The slice design's "Why one slice" section states the opposite invariant: "Each part lands as its own commit or commits, in the order C → B → A. Each commit passes the full suite on its own, and each can be reverted without touching the others." Task 10's commit is deliberately red, which breaks that invariant and means any CI run or `git bisect` anchored on that commit fails. The fix is either to fold the snapshot regeneration into Task 10 (single green commit) or to make the render change and the fixture regeneration an explicitly ordered pair within one commit. This is a sequencing/quality defect, not a coverage gap.

### [NOTE] Task 3 changes the `read_chunk_usage` signature from the design's stated contract

The design's Component Structure table specifies `read_chunk_usage(chunk) -> TokenUsage | None`. Task 3 implements `read_chunk_usage(chunk, warned: set[str])`, passing a per-call dedup set owned by the agent, to satisfy D12's "once per `handle_message`" malformed-usage WARNING without putting agent state in the reader. The rationale is sound, but the deviation from the stated API contract should be written back into the design rather than living only in the task, since the design is the interface source of truth the tasks cite.

### [NOTE] Task 23 skips walkthrough step 1, a prerequisite for the steps it runs

Task 23 runs walkthrough steps 3, 5, 6, and 10, and steps 7–9 on available environments. Walkthrough step 1 (define the `glm-flash-low` alias in `~/.config/squadron/models.toml`) is the prerequisite for steps 3, 5, and 6, and step 10 requires editing that alias to `effort = "extreme"`. The task does not list step 1, so a junior implementer following the task literally would have no alias to exercise. Adding the step-1 alias definition (and the step-10 invalidation) as explicit sub-items removes the ambiguity.

### [PASS] Load-test tasks exist and CI gating is explicit and verified

The slice's one NFR is the event-loop constraint. Task 11 creates `tests/load/test_usage_reader_loop.py` and Task 15 creates `tests/load/test_read_file_batch_loop.py`, both styled after the existing `tests/load/test_grep_timeout.py`. Both tasks state that no separate CI-wiring task is needed and give the reason: `pyproject.toml` sets `testpaths = ["tests"]` and `.github/workflows/ci.yml` runs `uv run pytest`, which already includes `tests/load/`. I confirmed both: `pyproject.toml:83` sets `testpaths = ["tests"]`, `ci.yml` runs `uv run pytest`, and `tests/load/` already holds `test_grep_timeout.py` and `test_worktree_concurrency.py`. Gating is not left implicit.

### [PASS] Success-criteria-to-task cross-reference is complete

Each functional criterion traces to a task with tests: effort on every turn incl. recovery (Task 20); SDK mapping and `none → thinking` (Task 21); Codex WARNING with no recorded effort (Task 22); invalid-value WARNING (Task 17); unchanged params when unset (Task 5); `read_file` path/paths/is_error rules (Tasks 12–13); guidance paragraph (Task 14); usage sums with run-total reasoning chars (Tasks 6, 10); omitted fields never 0 (Tasks 6, 10); empty-turn telemetry (Task 8); duration for all providers (Task 9); failure artifact (Tasks 7, 10B); every D12 row's signal (Tasks 3, 5, 6B, 7, 13, 17, 22). The technical-requirement unit-test list, the `MAX_READ_BATCH_BYTES` vs floor invariant, the `sends_stream_usage` cases, the two import greps, and the `cf validate frontmatter` check are all present, and no task traces to something outside the design's stated scope.

### Run Digest

- Response length: 5513 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 27379
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
