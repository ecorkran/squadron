---
docType: tasks
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
project: squadron
lld: user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md
dependencies: []
projectState: >
  Slice design 945 complete after three review rounds (20261014). No code written. Builds on
  942 (checkbox merge gate) and 944/#200 (failed dispatch ends a loop with on_exhaust).
  Fixes #211, #202, and #212 item 2.
dateCreated: 20261014
dateUpdated: 20261014
status: in_progress
---

## Context Summary

- Working on **945 dispatch-outcomes-match-what-happened**. A dispatch step can report `completed`, `success: True` when the model did nothing (#211). This slice makes providers refuse at spawn what they cannot honor (D1, D2), fails or warns on tool telemetry squadron already has (D3), fixes the SDK failed-call count (D4), makes cf errors in dispatch one line (D5, #202), and pauses a run whose merge finds unfinished tasks (D6, #212 item 2).
- Decisions D1–D6, the D2 refusal messages and the D3 table live in the slice design. Tasks reference them and do not repeat them. Use the D2 messages verbatim.
- Items D5 and D6 share no code with D1–D4. They get separate commits.
- Key files: `core/models.py`, `tools/builtin/_shared.py`, `providers/{sdk,openai,codex}/agent.py`, `pipeline/actions/dispatch.py` (786 lines; new logic goes in the new `pipeline/actions/dispatch_outcome.py`), `events/builtin/dispatch_artifact.py`, `pipeline/models.py`, `pipeline/branch_ops.py`, `pipeline/actions/branch.py`, `pipeline/executor.py`.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors) and the touched tests. Commit on the slice branch where a task says so.
- Every new failure mode logs at WARNING or ERROR (design, Technical Requirements). Spawn refusals (Tasks 7, 9) only raise `ProviderError`: `DispatchAction.execute` already logs it at ERROR, one line, no traceback (#200). The agents do not log refusals.
- Effort: 3/5. Next planned work: #144 (per DEVLOG work order).

## Tasks

- [x] **Task 1: Branch**
  - [x] Read the target: `cf config get git.integration_branch` (empty means `main`)
  - [x] Create `945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success` from the target
  - **Success:** on the slice branch, working tree clean

### Write-required contract (D1)

- [x] **Task 2: `WRITE_TOOL_NAMES`, `AgentConfig.requires_writes`, and the predicate**
  - [x] In `tools/builtin/_shared.py`, add `WRITE_TOOL_NAMES: frozenset[str]` built from the existing `WRITE_FILE_NAME` and `BASH_NAME`. Re-export it from `tools/builtin/__init__.py`.
  - [x] In `providers/base.py`, add key constants for the tool telemetry metadata: `tools_given`, `tool_calls_made`, `failed_tool_calls`, `first_tool_error`. None exist today; the keys are string literals. Replace every existing literal of these keys under `src/squadron` with the constants (find them with `grep -rn '"tools_given"\|"tool_calls_made"\|"failed_tool_calls"' src/squadron`), so no duplicate literal remains. New code in this slice uses only the constants.
  - [x] In `core/models.py` `AgentConfig`, add `requires_writes: bool = False` with a one-line comment: set for phase-step and revise dispatches (D1)
  - [x] In `pipeline/actions/dispatch_rules.py`, next to `rule_step_from_params`, add `dispatch_requires_writes(params) -> bool`: true when `rule_step_from_params(params)` is `StepTypeName.DESIGN`, `TASKS` or `IMPLEMENT`, or when `params.get("feedback") is not None` (the same test `DispatchAction._resolve_prompt` uses)
  - **Success:** the predicate is the only place D1's rule is written; no existing test changes behavior

- [x] **Task 3: Test the D1 predicate**
  - [x] In `tests/pipeline/actions/test_dispatch_rules.py`: `design`, `tasks`, `implement` rules params → true; `feedback` set → true; bare params and a `dispatch` rules param → false
  - [x] Run `pytest tests/pipeline/actions -q`, ruff, pyright
  - [x] Commit: `feat: add write-required dispatch contract to AgentConfig`
  - **Success:** tests pass, zero pyright errors

### SDK failed-call count (D4)

- [ ] **Task 4: Count `ToolResultBlock` errors inside `UserMessage.content`**
  - [ ] In `providers/sdk/agent.py` `_translate_and_track`, replace the top-level `isinstance(sdk_msg, ToolResultBlock)` branch: when `sdk_msg` is a `UserMessage` whose `content` is a list, increment `_failed_tool_calls` once per `ToolResultBlock` with `is_error` true
  - [ ] Keep `content` as a string (no blocks) a no-op
  - **Success:** the dead top-level branch is gone; the count reaches `final.metadata["failed_tool_calls"]`

- [ ] **Task 5: Test the SDK count**
  - [ ] In `tests/providers/sdk/test_agent.py` (or `test_translation.py`, whichever holds `_translate_and_track` tests), feed a `UserMessage` with one error `ToolResultBlock` and one success block, then a `ResultMessage`; assert `failed_tool_calls == 1` on the final message
  - [ ] Assert a string-content `UserMessage` leaves the count at 0
  - [ ] Run `pytest tests/providers/sdk -q`, ruff, pyright
  - [ ] Commit: `fix: count failed SDK tool calls from UserMessage content`
  - **Success:** tests pass (design criterion 9)

### OpenAI-compatible agent (D2, D3 inputs)

- [ ] **Task 6: Capture `first_tool_error`**
  - [ ] In `providers/openai/agent.py`, where `failed_tool_calls += 1` runs in the agentic loop, keep the result text of the first failed call
  - [ ] Truncate it to a length set by one module-level constant in this module (design, Special Considerations)
  - [ ] Stamp it under the `first_tool_error` key constant (Task 2) in `_stamp_tool_telemetry` beside `failed_tool_calls`; `None` when no call failed
  - **Success:** a run with a failed call carries the truncated text; a clean run carries `None`

- [ ] **Task 7: Refuse write-required with no write tool**
  - [ ] At spawn (where `_tools_given` is set from `allowed_tools`), raise `ProviderError` with the D2 OpenAI-compatible message when `config.requires_writes` is true and `_tools_given` has no name in `WRITE_TOOL_NAMES`
  - **Success:** no model call is made on refusal

- [ ] **Task 8: Test the OpenAI-compatible agent**
  - [ ] In `tests/providers/openai/test_agentic_loop.py`: one rejected `write_file` call → `failed_tool_calls == 1` and `first_tool_error` holds the rejection text; an over-long error is truncated to the constant; a clean run → `first_tool_error is None`
  - [ ] In `tests/providers/openai/test_agent.py`: `requires_writes=True` with `allowed_tools=["read_file"]` raises `ProviderError` with the D2 text and the fake client is never called; with `write_file` or `bash` it spawns; `requires_writes=False` with no tools spawns
  - [ ] Run `pytest tests/providers/openai -q`, ruff, pyright
  - [ ] Commit: `feat: refuse write-required OpenAI-compatible dispatch without a write tool`
  - **Success:** tests pass (design criterion 5 at unit level)

### Codex agent (D2)

- [ ] **Task 9: Codex spawn refusals and bare-dispatch warning**
  - [ ] In `providers/codex/agent.py`, before any model call, raise `ProviderError` with the D2 Codex `allowed_tools` message when `config.allowed_tools` is non-empty
  - [ ] Using the sandbox from `_resolve_sandbox`, raise `ProviderError` with the D2 read-only message (naming the profile) when `requires_writes` is true and the sandbox is read-only. Compare against the SDK `Sandbox` enum member, not a string.
  - [ ] When the sandbox is read-only and `requires_writes` is false, the agent itself logs a WARNING (not a refusal) naming the profile and the `sandbox = "workspace-write"` fix, and continue
  - [ ] Check order: `allowed_tools` first, then sandbox
  - **Success:** refusals happen before the Codex thread starts

- [ ] **Task 10: Test the Codex refusals**
  - [ ] In `tests/providers/codex/test_agent.py` using `fake_sdk.py`: `allowed_tools=["write_file"]` → `ProviderError` with the D2 text, fake SDK not called; read-only + `requires_writes` → `ProviderError` naming `sandbox`; `workspace-write` + `requires_writes` → runs; read-only bare → runs and `caplog` holds one WARNING
  - [ ] Run `pytest tests/providers/codex -q`, ruff, pyright
  - [ ] Commit: `feat: refuse Codex dispatches it cannot honor at spawn`
  - **Success:** tests pass (design criteria 1–3 at unit level; one test asserts a log record)

### Outcome rules (D3)

- [ ] **Task 11: `dispatch_outcome.py`**
  - [ ] Create `pipeline/actions/dispatch_outcome.py` with a frozen dataclass `ToolOutcome(fail_reason: str | None, warnings: list[str])` and `assess_tool_outcome(declared_tools, requires_writes, telemetry) -> ToolOutcome`
  - [ ] Implement the three D3 rows in order. Row 2's write-tool check reads `telemetry["tools_given"]` against `WRITE_TOOL_NAMES`. Row 2's reason includes `first_tool_error` when present.
  - [ ] Telemetry without `tool_calls_made` (no tools ran) returns no failure and no warnings
  - [ ] Read the metadata keys through the Task 2 constants
  - [ ] Pure function: no logging, no I/O
  - **Success:** pyright clean

- [ ] **Task 12: Test `assess_tool_outcome`**
  - [ ] New `tests/pipeline/actions/test_dispatch_outcome.py`, one test per row: row 1 fails with the D3 text; row 2 fails and includes `first_tool_error`; row 2 not triggered for a read-only step with only read tools (falls to row 3, warns); row 3 partial failure warns, no failure; no-telemetry → empty outcome; clean run → empty outcome
  - [ ] Run the file, ruff, pyright
  - **Success:** every D3 row and the no-telemetry case covered (design, Technical Requirements)

- [ ] **Task 13: Wire outcomes into `_dispatch_via_agent`**
  - [ ] Compute `requires_writes = dispatch_requires_writes(context.params)` and pass it to `one_shot_dispatch_with_telemetry`, which sets it on the `AgentConfig` it builds
  - [ ] In `one_shot_dispatch_with_telemetry`, copy `failed_tool_calls` and `first_tool_error` into `telemetry` beside the existing keys, keeping them absent when the run had no tools
  - [ ] After `_check_cli_error`, call `assess_tool_outcome`. Log each warning and any fail reason at WARNING with the step name. On a fail reason return `ActionResult(success=False, error=fail_reason, metadata=…)` with the same metadata as the success result.
  - [ ] Leave `_dispatch_via_session` unchanged (design, Excluded)
  - **Success:** dispatch.py grows only by the wiring; the rules stay in `dispatch_outcome.py`

- [ ] **Task 14: Test the dispatch wiring**
  - [ ] In `tests/pipeline/actions/test_dispatch.py` (helpers in `dispatch_helpers.py`), mock the registry to return OpenAI-shaped metadata for: a write-required step with zero calls → failed result, error text from D3, `caplog` WARNING with the step name; all calls failed → failed, metadata holds `failed_tool_calls` and `first_tool_error`; partial failure → success with WARNING and counts (criterion 6)
  - [ ] Add one SDK-shaped case: `tools_given` with `write_file`, all calls failed, no `first_tool_error` key → failed result whose error is the D3 row 2 text without error detail
  - [ ] Assert `AgentConfig.requires_writes` reaches the provider for a phase-step param and for `feedback`, and is false for bare dispatch. Add a dispatch entry to `tests/providers/agent_config_sites.py` (it drives a path's real builder and captures the `AgentConfig` at the SDK provider) and make these three assertions against its capture.
  - [ ] Run `pytest tests/pipeline/actions tests/providers -q`, ruff, pyright
  - [ ] Commit: `feat: fail dispatch steps whose tool telemetry shows no work done`
  - **Success:** tests pass; existing dispatch tests unchanged except where they assert the full metadata dict

- [ ] **Task 15: Test the #200 loop path with a D3-failed revise**
  - [ ] In `tests/pipeline/test_executor_loop_body.py`, add a case: a revise dispatch failed by D3 inside a multi-step loop body ends the loop with its `on_exhaust` status (Integration Requirements)
  - [ ] Run the file, ruff, pyright
  - [ ] Commit: `test: cover a D3-failed revise dispatch ending its loop`
  - **Success:** test passes with no executor change

### One-line cf errors (D5, #202)

- [ ] **Task 16: Catch `ContextForgeError` in the dispatch-artifact post-condition**
  - [ ] In `events/builtin/dispatch_artifact.py` `_resolve_paths`, add `ContextForgeError` (from `integrations/context_forge.py`) to the caught exceptions, or catch it separately if the outcome differs
  - [ ] Return a failed `EventOutcome` whose error is the cf message, with `error_kind` NONE so the executor does not rewrite it to `<action>: raised`
  - [ ] Log the message at ERROR without `exc_info`
  - **Success:** no traceback reaches stderr for a missing slice plan

- [ ] **Task 17: Test the post-condition**
  - [ ] In `tests/events/builtin/test_dispatch_artifact.py`: a cf client raising `ContextForgeError("No slice plan configured. Set one with: cf set slicePlan <path>")` gives a failed outcome carrying that text, `error_kind` NONE, and an ERROR record with no `exc_info`
  - [ ] Run `pytest tests/events -q`, ruff, pyright
  - **Success:** test passes

- [ ] **Task 18: Catch `ContextForgeError` in dispatch's keep path**
  - [ ] In `pipeline/actions/dispatch.py`, catch `ContextForgeError` from `_kept_artifact_paths` (at its call site, before the generic `_logger.exception` handler in `execute`) and return `ActionResult(success=False, error=<cf message>)`
  - [ ] Log at ERROR without `exc_info`, matching the #200 `ProviderError` handling in `execute`
  - **Success:** the generic handler no longer sees `ContextForgeError`

- [ ] **Task 19: Test the keep path**
  - [ ] In `tests/pipeline/test_existing_keep.py`: the same error in the keep path gives a failed `ActionResult` with the cf text and no `_logger.exception` call
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `fix: report cf errors in dispatch as one line without a traceback`
  - **Success:** tests pass (design criterion 7 at unit level)

### Unfinished tasks pause the run (D6, #212 item 2)

- [ ] **Task 20: `ActionResult.awaits_human` and the executor mapping**
  - [ ] In `pipeline/models.py` `ActionResult`, add `awaits_human: bool = False` with a one-line comment: a failed action waiting on a person, not broken
  - [ ] In `pipeline/executor.py`'s "Action failure" branch (`if not result.success:` in the step's action loop), return `ExecutionStatus.PAUSED` when `result.awaits_human`, else `FAILED`. Import nothing from `branch_ops`.
  - [ ] Confirm the existing PAUSED handling writes the checkpoint state and exits 0; change nothing there
  - **Success:** the executor reads only the flag

- [ ] **Task 21: Test the executor mapping**
  - [ ] In `tests/pipeline/test_executor.py`: a fake action returning `success=False, awaits_human=True` → step and run `PAUSED`; the same without the flag → `FAILED`
  - [ ] Run the file, ruff, pyright
  - [ ] Commit: `feat: pause the run on a failed action that awaits a person`
  - **Success:** tests pass

- [ ] **Task 22: `BranchFailure.UNFINISHED_TASKS` and the batch flag mapping**
  - [ ] In `pipeline/branch_ops.py`, add `UNFINISHED_TASKS` to `BranchFailure` with a comment
  - [ ] In `_require_checked_tasks`, raise `MergeFailedError` with `UNFINISHED_TASKS` when unchecked items remain (existing message), and when `info["task_files"]` is empty, with the D6 message ("slice N not merged: cf lists no task files for this slice, so its work cannot be verified.")
  - [ ] Keep an unreadable task file as `OTHER`; update the docstring
  - [ ] In `pipeline/actions/branch.py`, set `awaits_human=True` on the failure `ActionResult` when the failure is `UNFINISHED_TASKS`, and only then
  - [ ] In `executor.py` `_flag_kind`, an item whose failed branch action carries `UNFINISHED_TASKS` returns `FlagKind.STEP_FAILED`, the kind `OTHER` gives today (design D6). With `awaits_human` the item now ends `PAUSED`, and the `PAUSED` status check runs first, so the `UNFINISHED_TASKS` check must come before it.
  - **Success:** the merge refusal for unfinished work carries the new kind; other refusals and batch flags unchanged

- [ ] **Task 23: Test D6 branch and batch behavior**
  - [ ] In `tests/pipeline/test_branch_merge.py`: unchecked items → `UNFINISHED_TASKS`; cf returns no task files → `UNFINISHED_TASKS` with the D6 message; unreadable file → `OTHER`. Update existing assertions that expected `OTHER` for unchecked items.
  - [ ] Branch action test: `UNFINISHED_TASKS` sets `awaits_human`, `OTHER` and `CONFLICT` do not
  - [ ] In `tests/pipeline/test_executor_each.py` (or the file holding `_flag_kind` tests): an item failed by `UNFINISHED_TASKS` flags `STEP_FAILED`
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - [ ] Commit: `fix: pause the run when the merge finds unfinished tasks`
  - **Success:** tests pass (design criterion 8 at unit level; Technical Requirements branch tests)

### Close-out

- [ ] **Task 24: CHANGELOG**
  - [ ] Add short user-facing bullets under the unreleased section: Codex refuses `allowed_tools` and write-required steps on a read-only sandbox (names the fix); OpenAI-compatible steps refuse without a write tool; dispatch steps fail when every tool call failed or a write-required step made no calls (OpenAI-compatible, SDK one-shot with `allowed_tools`); a merge with unfinished tasks ends `paused`; cf errors in dispatch print one line
  - [ ] Do not claim coverage of the default SDK path
  - [ ] Commit: `docs: add CHANGELOG entries for slice 945`
  - **Success:** bullets match design Technical Requirements

- [ ] **Task 25: Full validation**
  - [ ] Run `ruff format`, `ruff check`, `pyright`, and the full `pytest` suite; fix and commit any failure
  - **Success:** full suite passes, zero pyright errors

- [ ] **Task 26: Verification walkthrough**
  - [ ] Precondition: a scratch clone registered with cf; `models.toml` aliases for a Codex model, an OpenRouter model (the #211 probe aliases) and SDK haiku (step 5); and a Codex profile whose `sandbox` credential you may change (step 2). If any is missing, stop and ask the Project Manager; do not substitute a model.
  - [ ] Run walkthrough steps 1–7 from the slice design, recording each command, exit code and the line that matches the expectation
  - [ ] Fix any failure with a test, re-run ruff, pyright and the touched tests, and commit each fix
  - [ ] Add the results to the Phase 6 DEVLOG entry (required at phase completion by `prompt.ai-project.system.md`, "Session State Summary")
  - **Success:** all seven steps match the design's expectations, or each mismatch is fixed or reported to the Project Manager. A step not run (missing precondition) is reported as unverified, never as passed.
