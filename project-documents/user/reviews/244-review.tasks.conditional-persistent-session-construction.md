---
docType: review
layer: project
reviewType: tasks
slice: conditional-persistent-session-construction
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/244-tasks.conditional-persistent-session-construction.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260504
dateUpdated: 20260504
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Missing test for `claude_required_one_shot` shape (Success Criterion 8)"
    location: tests/cli/test_run_pipeline_sdk.py
  - id: F002
    severity: concern
    category: task-clarity
    summary: "T4 `on_pool_selection` callback resolution is ambiguous"
    location: src/squadron/cli/commands/run.py
  - id: F003
    severity: note
    category: consistency
    summary: "Test file location differs from slice design"
    location: tests/cli/test_run_pipeline_sdk.py
  - id: F004
    severity: note
    category: test-with-pattern
    summary: "T4 refactoring step lacks immediate test (test-with pattern gap)"
    location: src/squadron/cli/commands/run.py
  - id: F005
    severity: pass
    category: coverage
    summary: "All other success criteria have corresponding tasks"
    location: unverified
  - id: F006
    severity: pass
    category: sequencing
    summary: "Task sequencing respects dependencies"
    location: unverified
---

# Review: tasks — slice 244

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Missing test for `claude_required_one_shot` shape (Success Criterion 8)

Success Criterion 8 explicitly requires that "`claude_required_one_shot` pipelines (review-only, SDK profiles) run without a persistent session." No task or test case covers this shape. T6 test T1 covers `claude_free` (all non-SDK), and T6 test T3 covers `claude_required_persistent` (at least one SDK dispatch step). But `claude_required_one_shot` is a distinct classification: it has SDK-resolved steps (reviews using one-shot), yet `needs_persistent_session=False`. Neither existing test exercises this combination. A test should be added to T6 (e.g., mock `classify_pipeline` returning `shape=claude_required_one_shot, needs_persistent_session=False` with at least one SDK-classified review step) and assert no persistent session is constructed.

### [CONCERN] T4 `on_pool_selection` callback resolution is ambiguous

T4 contains an extended discussion with multiple unresolved options for handling the `on_pool_selection` callback when the resolver is pre-built in `_run_pipeline_sdk`:
- "thread `state_mgr` creation up to `_run_pipeline_sdk`"
- "accept that pool selections during classification are not logged"
- "set `resolver._on_pool_selection = lambda ...` after `state_mgr` is known"
- "add an `attach_pool_callback(fn)` method on `ModelResolver`"
- "Check `ModelResolver` for an existing setter or direct attribute; use whatever is cleanest"

A junior AI implementer cannot resolve this ambiguity. The task should prescribe a single approach. The slice design's implementation detail section shows the resolver constructed without `on_pool_selection` in the `_run_pipeline_sdk` code block, implying the callback is attached later. The task should state the chosen approach definitively (e.g., "Inside `_run_pipeline`, when `resolver is not None`, attach the `on_pool_selection` callback by setting `resolver.on_pool_selection = ...` after `state_mgr` and `_run_id` are available").

### [NOTE] Test file location differs from slice design

The slice design specifies `tests/pipeline/test_conditional_session.py` as the test file, but the tasks use `tests/cli/test_run_pipeline_sdk.py`. Either location is defensible, but the discrepancy should be acknowledged or the slice design updated to match.

### [NOTE] T4 refactoring step lacks immediate test (test-with pattern gap)

T4 lifts `pool_backend` and `resolver` construction into `_run_pipeline_sdk` — a behavioral no-op refactoring step. No test immediately follows T4; the next test task (T6) comes after T5. Since T4 doesn't change observable behavior, the gap is low-risk, but a quick "existing integration tests still pass" check after T4 would strengthen confidence before T5 adds the classification gate. Consider adding a `uv run pytest tests/cli/ -q` verification step at the end of T4.

### [PASS] All other success criteria have corresponding tasks

Cross-referencing success criteria 1–7 against tasks: SC 1 (non-SDK pipeline runs with `sdk_session=None`) → T6 T1/T2; SC 2 (no SDKExecutionSession constructed for non-SDK) → T6 T1; SC 3 (SDK pipeline constructs session) → T6 T3; SC 4 (POOL_UNCERTAIN constructs session) → T6 T4; SC 5 (ClassificationError → typer.Exit(1)) → T5 impl + T6 T5; SC 6 (resume re-classifies) → T7 T6/T7; SC 7 (connect() failure propagation) → T6 T8. Technical requirements (ruff, pyright, full suite) → T8, T10. Commit checkpoints are distributed (T8, T10, T11), not batched at end. No scope creep detected — all tasks trace to a success criterion or necessary infrastructure.

### [PASS] Task sequencing respects dependencies

T1→T2→T3 (param addition + test) →T4→T5→T6/T7 (gate implementation + tests) →T8 (commit) →T9 (audit) →T10 (final validation) →T11 (docs). No circular dependencies. The test-with pattern is correctly applied for the two behavioral change points: T2→T3 (fallback test) and T5→T6/T7 (gate tests).
