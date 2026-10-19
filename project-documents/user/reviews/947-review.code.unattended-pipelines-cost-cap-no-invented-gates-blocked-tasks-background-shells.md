---
docType: review
layer: project
reviewType: code
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md
aiModel: xiaomi/mimo-v2.6-pro
aiProfile: openrouter
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: 00e491de1e99d5811df52837cbbf7cd9f3293718
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 23
diffTruncated: false
turns: 12
promptTokens: 943465
cachedTokens: 833664
completionTokens: 30014
reasoningTokens: 27372
durationSeconds: 814.6
costUsd: 0.07721
costBasis: alias_pricing
squadronVersion: 0.23.1
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Cost cap is not enforced in loop-shaped steps; rounds keep spending past the cap"
    location: "src/squadron/pipeline/executor.py:1417"
  - id: F002
    severity: note
    category: error-handling
    summary: "Stream-end error text says \"before the dispatch's result\" even when the result was seen"
    location: "src/squadron/pipeline/sdk_session.py:297"
  - id: F003
    severity: note
    category: correctness
    summary: "`parse_blocked_markers` false positives and empty captures can produce awkward pauses"
    location: "src/squadron/pr/tasks.py:22-27"
  - id: F004
    severity: note
    category: maintainability
    summary: "`_usage` record builder duplicated across two new test files"
    location: "tests/pipeline/test_run_spend.py:21"
  - id: F005
    severity: pass
    category: design
    summary: "Blocked-tasks hand-off is fail-closed, observable, and ordered correctly"
    location: "src/squadron/events/builtin/blocked_tasks.py:43"
---

# Review: code — slice 947

**Verdict:** FAIL
**Model:** xiaomi/mimo-v2.6-pro

## Findings

### [FAIL] Cost cap is not enforced in loop-shaped steps; rounds keep spending past the cap

The per-action cap check in `_execute_step_once` (executor.py:1086-1091) fails the crossing action, but both loop executors treat an action failure as transient and continue: `_execute_loop_step` falls through to the next round at executor.py:1417 ("Action failure is transient in loops — continue to next iteration") for both `until`-set and `until`-unset configs, and `_execute_loop_body` only ends a round early on a *dispatch* failure (`_failed_dispatch_error`, executor.py:1615) — a cost-capped review or other LLM action lets the round and subsequent rounds keep running. Each remaining round executes a full action and only trips the cap check *after* spending, so overshoot is one full action per remaining round, not the documented "one action, or one per branch of a fan_out step" (src/squadron/config/keys.py, `COST_CAP_KEY` description). Worse, the run can finish green over the cap: a round where `until` is satisfied after the capped action returns `COMPLETED` with a `COST_CAP`-failed action in `action_results` (which `_crossed_cost_cap` at executor.py:2024 never sees — it is consulted only when the item's final step is `FAILED`, executor.py:2020), and a loop exhausted with `on_exhaust: skip` returns `SKIPPED` via `_loop_failure_status` (executor.py:1183), letting later steps run. `each`, `fan_out`, and the flat walk all got explicit cap handling; the loop paths need the same (e.g. stop the loop when a round's results contain a `COST_CAP` failure, and/or a cap check between steps in `execute_pipeline`). There is no test asserting cap behavior for a `loop:` step, which is why the gap is invisible to the suite (tests/pipeline/test_executor_cost_cap.py covers only flat, `fan_out`, and `each`).

### [NOTE] Stream-end error text says "before the dispatch's result" even when the result was seen

When our own result was collected and only the CLI's `idle` frame never arrived before the stream ended (the D12 scenario `test_stream_end_while_running_raises` covers), the raised `ProviderError` still reads "stream ended before the dispatch's result". The message does carry `session state` and ledger counts, so the failure is diagnosable, but the first clause is wrong in exactly the case this slice introduced; consider wording that distinguishes "no result" from "result seen, idle never reported".

### [NOTE] `parse_blocked_markers` false positives and empty captures can produce awkward pauses

The regex deliberately accepts a bare space after the marker ("BLOCKED needs the PM"), so a legitimate task line that merely *begins* with the word — e.g. `- [ ] BLOCKED tasks list cleanup` — matches and pauses the run demanding PM intervention. A bare `BLOCKED` line also matches with an empty capture, yielding the message "…need the Project Manager: . Resolve them…". The leniency matches the project's parsing rule and is tested as intended, but since a false positive here is a stuck run rather than a wrong parse, consider requiring a separator (`:`/dash) or falling back to a placeholder text for empty captures.

### [NOTE] `_usage` record builder duplicated across two new test files

`tests/pipeline/test_run_spend.py` and `tests/pipeline/test_executor_cost_cap.py` each define an identical `_usage(cost_usd)` helper building a `UsageRecord(...).to_dict()`. A shared helper in `tests/pipeline/conftest.py` (already the home for `sdk_session_state`) would keep the two suites from drifting when the record shape changes.

### [PASS] Blocked-tasks hand-off is fail-closed, observable, and ordered correctly

The new `squadron.blocked-tasks` action gets this right: unreadable task files, cf errors, and a non-numeric `slice` param all fail the check (logged at ERROR) rather than silently passing; markers pause with `awaits_human` and a WARNING naming the blockers and the resume command; the binding sits before `dispatch-branch-work` in `DEFAULT_BINDINGS` (src/squadron/events/manifest.py:71) and `run_event` stops POST_ACTION at the first failure (src/squadron/events/dispatcher.py:102-103), so the hand-off wins over the "no commits" failure as designed. `RunSpend.add` (src/squadron/pipeline/run_spend.py:65-86) satisfies the exception-handling rule (specific `ValueError` with a justifying comment and ERROR log), and its docstring documents that the shared tally is race-free because it is pure synchronous bookkeeping — appropriate for the concurrent `fan_out` branches. The tests use real production marker formats (the amoeba slice 107 line) per the parser-fixture rule.

### Run Digest

- Response length: 5677 chars
- Response is newline-free: no
- Tool calls made: 23
- Tool calls failed: 2
- Stop reason: stop
- Output budget: 131072 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 112164
- Effort: backend default
- Turns: 12
- Tokens — prompt / cached / cache write / completion / reasoning: 943465 / 833664 / not computed / 30014 / 27372
- Duration: 814.6 s
- Cost: $0.08 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Response

- **F001** fixed (76066603): both loop shapes stop at the round whose action crosses the cap and fail the step, even when `until` is satisfied or `on_exhaust: skip` is set. `tests/pipeline/test_executor_cost_cap.py` covers the single-step and multi-step body shapes.
- **F002** fixed (57adde48): the stream-end error says "after the dispatch's result, before the CLI reported idle" when our result was seen, and keeps "before the dispatch's result" when it was not. Both cases have a test.
- **F003** fixed (57adde48): `parse_blocked_markers` requires a `:` or dash after `BLOCKED`, so a task titled "BLOCKED tasks cleanup" no longer pauses a run. A marker with no text reports "(no reason given)".
- **F004** fixed (57adde48): `usage_dict` lives once in `tests/pipeline/conftest.py`.
- **F005** pass, no change.
- Per-run and rolling-window caps are logged as #241 and #242.
