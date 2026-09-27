---
docType: review
layer: project
reviewType: tasks
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 85ff3f94ae1d510a457793682d3c3de95e82cea5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "Every functional requirement traces to at least one task"
    location: "project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md"
  - id: F002
    severity: concern
    category: verification-gate
    summary: "The `\"length\"`/`\"max_tokens\"` grep success gate cannot pass as written"
    location: "project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md:53"
  - id: F003
    severity: pass
    category: task-structure
    summary: "Sequencing, granularity, and test-with pattern are correct"
    location: "project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md"
  - id: F004
    severity: pass
    category: task-structure
    summary: "Commit checkpoints are distributed and code-grounded"
    location: "project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md"
  - id: F005
    severity: note
    category: test-coverage
    summary: "FR3's `stop`/`end_turn` recovery paths rely on existing tests"
    location: "project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md:81"
  - id: F006
    severity: note
    category: test-coverage
    summary: "FR13 (dispatch/summary fail as today) has no dedicated task or test"
    location: "project-documents/user/tasks/924-tasks.recover-a-review-the-model-reasoned-out-but-never-emitted.md:125"
---

# Review: tasks — slice 924

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Every functional requirement traces to at least one task

Cross-reference of the slice design's 13 functional requirements: FR1 → A.1/A.7/A.8; FR2 → A.1/A.3/A.5/A.6/A.7; FR3 → A.5/A.6; FR4 → A.6 (D3 pin); FR5 → B.1/B.2/B.3; FR6 → A.3/B.14; FR7 → B.12/B.13; FR8 → B.4/B.5; FR9 → C.4/C.5; FR10 → C.4/C.5; FR11 → C.4/C.5; FR12 → C.2/C.3; FR13 → C.1 (subclass keeps every `except ProviderError` working). Technical requirements map to A.1 (single stop-reason set), B.7/B.8 (loader validation), F.2 (ruff/pyright/pytest), and every design-named test file has a corresponding task (A.2, A.4, A.6, A.8, B.3, B.5, B.8, B.9, B.10, B.11, B.13, B.14, C.3, C.5). Integration requirements map to A.8 (`cf validate frontmatter`) and B.13 (CLI/pipeline parity). No gaps, no scope creep — F.1's issue filing and B.16's OpenRouter values are both design-mandated.

### [CONCERN] The `"length"`/`"max_tokens"` grep success gate cannot pass as written

A.1's success criterion and F.2's re-check (line 210) run `grep -rn '"length"\|"max_tokens"' src/` and expect "only this constant". I ran the equivalent search: the strings already appear in comments at `src/squadron/providers/openai/agent.py:102` (`finish_reason="length" and no content`) and `src/squadron/review/models.py:178` (`an abnormal value ("length") is a`). The gate as written can never show "only" the constant, so a junior implementer hits a success criterion that cannot be satisfied — and might "fix" it by editing comments, or worse, treat the slice as failed. The design's technical requirement ("the only place those strings appear in `src/`") clearly means live comparison values, not comments. Amend both task lines to scope the gate to code (e.g., document the two known comment sites as acceptable, or exclude comment matches) before implementation starts.

### [PASS] Sequencing, granularity, and test-with pattern are correct

The A → C → B order matches the design's Development Approach, and C.4 correctly depends on A.1's `budget_exhausted`. Within Part B, dependencies are respected: B.1 (AgentConfig field) precedes B.2 (agent sends it); B.7 (alias field) precedes B.9 (resolver reads it); B.9/B.10 precede the B.11/B.12 call sites; B.14 renders from the result B.10 sets. No circular dependencies. Every test task immediately follows its implementation task (A.2→A.1, A.4→A.3, A.6→A.5, A.8→A.7, C.3→C.2, C.5→C.4, B.3→B.2, B.5→B.4, B.8→B.7, B.13→B.12); the combined impl+test tasks (B.9, B.10, B.11, B.14) are each single-file and small enough that the pairing inside one task is fine. All tasks are effort 1/5–2/5 — none too large, none needlessly granular.

### [PASS] Commit checkpoints are distributed and code-grounded

Seven commit checkpoints (A.9, C.6, B.6, B.15, B.16, F.4, F.5) are spread across all three parts and the finish, not batched at the end, each with a semantic message per project convention. The slice design contains no NFR that requires load testing, so no `tests/load/` task or CI gating task is required — that check does not trigger for this slice. I also verified the tasks' code claims: the recovery branch is at `src/squadron/review/review_client.py:254` region, `verdictSource` at `persistence.py:390`, alias `tool_use` parsing at `aliases.py:67`, `_require_final_content` call sites at `agent.py:236-239` and `agent.py:464-467`, `TurnResult.is_empty()` exists at `agent.py:114`, `resolve_full()` at `resolver.py:151`, the two `resolve()` calls at `pipeline/actions/review.py:176-180`, the seven digest fixtures exist as listed, and JSON output flows through `result.to_dict()` (`cli/commands/review.py:238`), which makes A.3's `to_dict()` additions satisfy the JSON requirements without a second rendering path.

### [NOTE] FR3's `stop`/`end_turn` recovery paths rely on existing tests

A.6 adds a new test only for recover-on-`None`; the `stop` and `end_turn` cases of FR3 are covered by the success line "the existing recovery tests pass unchanged". This matches the design's own test list, which also names only `recover-on-None`, and `end_mid_task` recovery on those stop reasons is shipped behavior — so this is acceptable as written. A.5's success line restates the requirement, so the intent is visible even if no new test pins `stop`/`end_turn` explicitly.

### [NOTE] FR13 (dispatch/summary fail as today) has no dedicated task or test

No task touches dispatch or summary, which is correct — the design explicitly excludes them, and C.1's subclassing preserves their behavior by construction. The pin is indirect: C.5's success line requires the existing failure-artifact tests to pass unchanged, and I confirmed such tests exist (`tests/pipeline/actions/test_review_action.py:1540-1584` construct `ProviderError` failure paths, and line 1518 quotes the empty-turn message). That is sufficient; a reviewer should just know FR13 is verified by regression rather than by a new assertion.

## Response (20260927)

- **F002: accepted.** Both existing hits are `#` comments (`providers/openai/agent.py:102`, `review/models.py:178`). A.1 and F.2 now use `grep -rnE '^[^#]*("length"|"max_tokens")' src/`, which skips comments, and name the two comment sites as expected.
- **F005: accepted.** A.6's recovery case now parametrizes over `None`, `"stop"`, and `"end_turn"`, so FR3 is pinned directly rather than by regression.
- **F006: no change.** FR13 holds by construction (subclass of `ProviderError`) and is covered by the existing failure-artifact tests, as the finding says.

### Run Digest

- Response length: 6491 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 4988
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
