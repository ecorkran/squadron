---
docType: review
layer: project
reviewType: tasks
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20260929
dateUpdated: 20260929
reviewedSha: 233c9bb339c093f19fd83ea01972edad41bed5c8
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
runId: run-20260930-p5-f12cfe4d
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "All success criteria trace to tasks"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
  - id: F002
    severity: pass
    category: nfr-coverage
    summary: "Load-test NFR covered and CI gating is explicit, not implicit"
    location: ".github/workflows/ci.yml:44"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Sequencing and dependency ordering are sound"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
  - id: F004
    severity: note
    category: contract-drift
    summary: "`read_chunk_usage` signature is extended past the design's stated contract"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
  - id: F005
    severity: note
    category: verification-coverage
    summary: "Walkthrough steps 7–9 (local/openai/gemini profiles) are environment-gated"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 4B carries a comparatively large test-surface obligation"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md"
---

# Review: tasks — slice 931

**Verdict:** PASS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] All success criteria trace to tasks

Every slice Success Criteria item maps: FR1→Task 20, FR2→Task 21, FR3→Task 22, FR4→Task 17, FR6→Tasks 12–13, FR7→Task 14, FR8→Tasks 6/8/9/10, FR9→Tasks 6/10, FR10→Tasks 7/8, FR11→Task 9, FR12→Tasks 7/10B, FR13→D12 rows distributed across Tasks 3, 5B, 6B, 7, 13. The Technical Requirement "sends_stream_usage tests" → Tasks 4/4B/5; "alias parsing parametrized" → Task 17; "ResolvedModel.effort round-trip" → Task 18; "MAX_READ_BATCH_BYTES vs floor invariant" → Task 13; "frontmatter/digest/JSON from one ReviewResult and one failed ProviderError" → Tasks 10/10B. Integration parity → Task 19; `cf validate frontmatter` → Task 23. Every entry in the design's Component Structure table is covered, including `data/models.toml` (Task 17), `providers/base.py` (Task 19), and the six credential sites (Task 4B).

### [PASS] Load-test NFR covered and CI gating is explicit, not implicit

The design's only NFR (event-loop responsiveness) produces two load-test tasks: Task 11 (`tests/load/test_usage_reader_loop.py`) and Task 15 (`tests/load/test_read_file_batch_loop.py`). I verified the gating claim rather than accepting it: `pyproject.toml` sets `[tool.pytest.ini_options] testpaths = ["tests"]` and `ci.yml` runs `uv run pytest` with no `addopts`/marker deselection, so `tests/load/` is exercised on every push. Task 11 states this and instructs a confirming run; the existing `tests/load/test_grep_timeout.py` is styled the same way. Gating is therefore satisfied by the pre-existing CI step and is stated, not left implicit.

### [PASS] Sequencing and dependency ordering are sound

The C → B → A order holds with no cycles. Within Part C, dependencies flow strictly forward: Task 2 (`core/usage.py`) → 3 (reader) → 4/4B (`profile_credentials`) → 5/5B (flag + read) → 6/6B (accumulate/stamp) → 7 (`ProviderError.telemetry`) → 8 (`TurnCapture`) → 9 (`review_client`) → 10/10B (render). Task 3's forward reference to "the agent owns the set and clears it at the top of `handle_message` (Task 5B)" is a correct forward pointer, not a backward dependency. Part A's Task 19/19B correctly layer on Part C's `ReviewResult`/persistence changes. Commit checkpoints appear after every task.

### [NOTE] `read_chunk_usage` signature is extended past the design's stated contract

The design (Technical Decisions D8, Component Structure) states the contract as `read_chunk_usage(chunk) -> TokenUsage | None` (one argument). Task 3 adds a keyword-only `warned: set[str] | None = None` so D12's "WARNING … once per `handle_message`" can be satisfied without agent state inside the reader. The addition is justified and preserves the one-arg form, but it is a deviation from the design's written signature that a downstream reader of the design won't see. Not a blocker; worth recording so the design and task agree.

### [NOTE] Walkthrough steps 7–9 (local/openai/gemini profiles) are environment-gated

Task 23 instructs running steps 7–9 "whichever the environment has; list the rest by name in the DEVLOG entry as not run," and Task 11's live baseline stops if an OpenRouter key is absent. This is a reasonable accommodation the design already anticipates (probes returned only 503/429), but it means the end-to-end verification of the local/openai/gemini request shapes may be deferred to a DEVLOG note rather than executed. Acceptable given the design's stated constraints; flagged so the gap is a conscious one.

### [NOTE] Task 4B carries a comparatively large test-surface obligation

Task 4B switches six sites and requires a parametrized test per site, with instruction to "add the smallest seam if one is missing" at any site that lacks one. This traces directly to the Technical Requirement ("All six call sites produce the same credentials as `profile_credentials`"), so it is not scope creep, but it is the heaviest single task in Part C and could be split per-site if the seams prove to need more than trivial work. Tasks 7, 10, and 13 are similarly at the upper bound of a single task but each remains internally coherent.

### Run Digest

- Response length: 5565 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 28811
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
