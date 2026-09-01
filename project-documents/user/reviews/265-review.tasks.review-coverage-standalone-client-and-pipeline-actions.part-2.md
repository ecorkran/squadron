---
docType: review
layer: project
reviewType: tasks
slice: review-coverage-standalone-client-and-pipeline-actions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260901
dateUpdated: 20260901
reviewedSha: 97b5d10b3a33b8315e7f288043da4fa6b4c8fd04
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "`grep` tool's concurrency/timeout bound has no load-test task"
    location: "src/squadron/tools/builtin.py"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 14 (ReviewAction `allowed_tools` wiring) has no paired test task"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:54-81"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task 18 bundles three action types' telemetry wiring with only partial test coverage"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:151-176"
  - id: F004
    severity: note
    category: consistency
    summary: "Close-out checklist silently drops `pipeline/schema.py` from the design's Integration Points table"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:323-326"
  - id: F005
    severity: note
    category: code-structure
    summary: "File-size guideline applied inconsistently between provider.py and builtin.py"
    location: "src/squadron/tools/builtin.py"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete and traceable"
    location: "unverified"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing has no circular dependencies and respects real build order"
    location: "unverified"
---

# Review: tasks — slice 265

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] `grep` tool's concurrency/timeout bound has no load-test task

`GREP_TIMEOUT_S` (task 1) and the `grep` tool (task 5, tested in task 6) exist specifically to bound a hang from catastrophic backtracking when `regex.search(..., timeout=...)` runs `asyncio.to_thread`d off the event loop — a canonical instance of `.claude/rules/python.md`'s "Load-test tier": *"any code on the simulation, network, concurrency, or environment-layer paths requires at least one load test exercising a realistic configuration... CI must gate load tests for slices touching these paths."* D9 in the slice design is essentially a load-testing writeup already (72.8s hang measurement, exponential backtracking timings at 20/24/26/28/30 chars) but none of that becomes a `tests/load/` task. Task 6.2's `test_pathological_pattern_times_out` is a correctness unit test with a monkeypatched timeout — it doesn't assert latency/throughput/resource bounds under a realistic configuration (e.g., concurrent grep calls saturating the thread pool, or the walk budget holding at the real, non-monkeypatched `GREP_TIMEOUT_S` over a realistic tree). No `tests/load/` directory exists in the repo and no task creates one; consequently there's also no CI-gating task for it, per your own second check ("if a load test task exists, a CI wiring task exists to gate on it") — moot here only because the load test itself is missing.

### [CONCERN] Task 14 (ReviewAction `allowed_tools` wiring) has no paired test task

Every other implementation task that introduces new branching behavior is immediately followed by its own test task (3→4, 5→6, 7→8, 9→10, 11→12, 16→17, 21→22). Task 14 breaks this: its own success criteria list functional expectations but no test file/test names, and coverage is pushed into Task 15.3 as a conditional afterthought — *"Add the equivalent two validate/expand-style tests to `tests/pipeline/actions/test_review_action.py` for the review-side change from task 14, **if not already covered there**"*. That hedge means task 14's commit can land with new validation and override logic (14.2's step-vs-template `allowed_tools` precedence, which the task itself flags as unconfirmed against the design) unverified at the moment it's committed, and the next task's author may skip it believing it's already covered elsewhere. No task or success criterion anywhere asserts the chosen override precedence (step-level `allowed_tools` beating `template.allowed_tools`) when both are present simultaneously — only the "step declares, template doesn't" and "template only" cases are covered.

### [CONCERN] Task 18 bundles three action types' telemetry wiring with only partial test coverage

Task 18 (effort 4/5) threads telemetry into `ActionResult.metadata` for dispatch, review, *and* summary in one task, inconsistent with the finer per-action-type split used for the equivalent `allowed_tools` wiring work (tasks 13/14/15, one per action). No test task follows 18 directly; the closest coverage is Task 20.3's integration test, which explicitly scopes to *"at least one action type"*. That leaves the review and summary sides of 18.2/18.3 — the actual `ActionResult.metadata["tools_given"/"tool_calls_made"]` population, distinct from `ReviewResult`'s own fields (task 19) or the config-passthrough tests (task 15.3) — without a task-level test asserting the metadata actually reaches `ActionResult` for those two action types.

### [NOTE] Close-out checklist silently drops `pipeline/schema.py` from the design's Integration Points table

The slice design's Integration Points table lists `pipeline/schema.py` as a change site ("`allowed_tools` valid on review/summary steps"). File 1's Context Summary correctly explains this doesn't apply — there's no per-step-type Pydantic schema to extend, and validation goes through the shared helper instead (reasonable, verified against `steps/utils.py`/`validate_allowed_tools`). But Task 25.2's diff-matches-Integration-Points-table checklist omits schema.py without calling out that it's an intentional deviation, so a close-out reviewer diffing against the design table has no signal that this is expected rather than dropped.

### [NOTE] File-size guideline applied inconsistently between provider.py and builtin.py

Task 7.1 explicitly hedges on splitting `providers/sdk/provider.py` into a new module "if `provider.py` is already near 300 lines" — but `provider.py` is only 93 lines, so that condition won't trigger. Meanwhile `tools/builtin.py` is already 345 lines *before* tasks 3 and 5 add two more tool implementations (closures, jail resolution, truncation, regex-timeout handling), which will push it well past CLAUDE.md's "~300 lines where practical" guideline — yet no task considers splitting search tools into a separate module the way 7.1 considered doing for provider.py. Low priority: the codebase already has much larger precedent (`pipeline/executor.py` at 1698 lines, `review/review_client.py` at 458), so this isn't a departure from actual practice, just an inconsistency in where the breakdown chose to apply the guideline.

### [PASS] Success-criteria coverage is complete and traceable

All ten success criteria (SC1, SC1a, SC2–SC10) map to at least one concrete task, and no task is free-floating scope creep — including the two out-of-scope carve-outs (D6's `Bash` drop, D8's no-schema-bump) which are correctly reflected rather than silently re-added.

### [PASS] Sequencing has no circular dependencies and respects real build order

Leaf pieces (limit constant, dependency, tools) precede the provider-edge changes that give them meaning, which precede the injection decision, which precedes pipeline-action wiring, which precedes observability threading, which precedes the template migration (deliberately last per the file's own stated rationale), which precedes the live/manual verification and close-out. Each dependency referenced in a later task is committed in an earlier one.
