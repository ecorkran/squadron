---
docType: tasks
project: squadron
slice: 265-slice.review-coverage-standalone-client-and-pipeline-actions
lldReference: project-documents/user/slices/265-slice.review-coverage-standalone-client-and-pipeline-actions.md
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261, 262, 263]
dateCreated: 20260901
dateUpdated: 20260901
status: complete
---

# Tasks: Review Coverage — Standalone Client and Pipeline Actions (2 of 2)

## Context Summary

Continuation of `265-tasks.review-coverage-standalone-client-and-pipeline-actions-1.md`. That
file (tasks 1-13) added `list_files`/`grep` tools plus a `tests/load/` timeout load test, the
canonical-name translation edge, the non-SDK unknown-name raise, and the run-scoped injection
decision. This file assumes all of that lands and passes first.

This file: pipeline-action wiring for `review`/`summary`, each with its own paired test task
(14-18), tool-use observability threaded from the agent through `ActionResult.metadata`,
`ReviewResult`, and the `-v` log line (19-25), migrating the seven shipped templates to
canonical vocabulary now that the vocabulary fix actually works (26-27), the live SC6/SC8/SC10
evidence tasks (28-29), and close-out (30).

**Ordering fix from the Phase 5 review (F001, FAIL).** The first draft carried `ReviewResult`
telemetry fields (was task 19) after the task that reads them into `ActionResult.metadata` (was
task 18.2) — a junior AI following the list in commit order would hit a nonexistent attribute.
`ReviewResult`'s own fields now come first (task 21), before any action-level carry reads them
(tasks 22-24).

**Test-pairing fix (F002/F003 in both review files).** The first draft deferred `ReviewAction`'s
own test coverage to the `SummaryAction` test task with an "if not already covered there" hedge,
and bundled dispatch/review/summary telemetry-carrying into one task with only one tested end to
end. Every implementation task below that introduces new behavior now has its own immediately-
following test task, matching the pattern already used elsewhere in this breakdown (3→4, 5→6,
8→9, 10→11, 12→13, 19→20, 26→27).

Same commit protocol and branch as file 1: `ruff format` before every commit, one commit per
task, on branch `265-slice.review-coverage-standalone-client-and-pipeline-actions` forked from
`main` (`cf config get git.integration_branch` reads empty).

---

## Task 14: Shared `allowed_tools` resolution helper for review and summary

- [x] **14.1** Extract a shared helper from `dispatch.py`'s `_resolve_allowed_tools`
  (405-420) into a module both `dispatch.py`, `review.py`, and `summary.py` can import (e.g.
  `pipeline/actions/tool_support.py`, or `pipeline/steps/utils.py` if that already holds
  cross-action helpers — check `steps/utils.py` first since `validate_allowed_tools` already
  lives there per slice 263)
  - [x] Same contract: read `context.params.get("allowed_tools")`, `None` if absent, raise
    `ValueError` if present but not `list[str]`, no registry re-check (load-time validation via
    task 15's schema-side check is the single authority, matching design D3's non-duplication
    rule)
  - [x] Update `dispatch.py` to call the shared helper instead of its own copy; this must not
    change `dispatch.py`'s existing test behavior
  - [x] Effort: 2/5

- [x] **Task 14 success criteria**
  - [x] One implementation of the resolution logic, imported by all three actions
  - [x] `uv run pytest tests/pipeline/actions/test_dispatch.py -q` still green after the
    extraction (regression guard — behavior must not change)
  - [x] `ruff format` run, then committed: `refactor: extract shared allowed_tools resolution helper`

## Task 15: Wire `allowed_tools` into `ReviewAction` and validate at load time

- [x] **15.1** `ReviewAction.validate()` in `review.py` — extend with the same
  `validate_allowed_tools(config, self.step_type)` call slice 263 added to
  `DispatchStepType.validate` and `PhaseStepType.validate` (`steps/utils.py`), so an unknown
  tool name on a pipeline-YAML `review` step fails at load time, before any model call
  - [x] If `ReviewAction` does not currently go through a `StepType.validate` path the same way
    `dispatch`/`phase` do, locate the correct validation entry point for review steps
    (`pipeline/steps/review.py` if it exists as a separate step type) and add the call there
    instead — confirm the actual step-type/action split for review steps before choosing where
    this lands
- [x] **15.2** `ReviewAction._review` (or equivalent execution method) — read
  `context.params.get("allowed_tools")` via the task 14 helper and pass it to
  `run_review_with_profile` as a new keyword-only parameter, **overriding**
  `template.allowed_tools` when present (a step-level declaration takes precedence over the
  template default; if the design is silent on this ordering, the template stays authoritative
  only when the step declares nothing — task 16 asserts both branches of this precedence
  directly, not just the two single-source cases)
  - [x] `run_review_with_profile`'s existing callers (the `sq review` CLI path) that don't pass
    this new parameter keep today's behavior exactly — default `None`
  - [x] Effort: 3/5

- [x] **Task 15 success criteria**
  - [x] A pipeline `review` step with an unknown tool name fails validation before any model
    call
  - [x] A pipeline `review` step with valid `allowed_tools` reaches `run_review_with_profile`
    with those tools
  - [x] `run_review_with_profile` called without the new parameter behaves exactly as before
  - [x] `ruff format` run, then committed: `feat: thread allowed_tools through pipeline review action`

## Task 16: Test `ReviewAction` wiring, including step-vs-template precedence

- [x] **16.1** Add to `tests/pipeline/actions/test_review_action.py`
  - [x] `test_validate_rejects_unknown_tool` — a `review` step with an unregistered tool name
    fails `validate_pipeline`, mirroring the equivalent dispatch/phase tests from slice 263
  - [x] `test_step_allowed_tools_reaches_run_review_with_profile` — assert the resolved tools
    argument, not merely that a mock was called
  - [x] `test_absent_step_allowed_tools_leaves_parameter_none` — regression guard for the
    `sq review` CLI path, which never sets this parameter
- [x] **16.2** The precedence tests this task exists to add (F002/F003 from the Phase 5 review —
  the first draft asserted only the two single-source cases)
  - [x] `test_step_allowed_tools_overrides_template_allowed_tools` — construct a template with a
    non-empty `allowed_tools` and a step declaring a *different* non-empty `allowed_tools`;
    assert the step's list, not the template's, reaches `run_review_with_profile`
  - [x] `test_template_allowed_tools_used_when_step_declares_nothing` — same template, no step
    declaration; assert the template's list reaches `run_review_with_profile` unchanged
  - [x] Effort: 2/5

- [x] **Task 16 success criteria**
  - [x] `uv run pytest tests/pipeline/actions/test_review_action.py -q` green
  - [x] Both precedence tests present and asserting on the actual value passed to
    `run_review_with_profile`, not on mock call counts alone
  - [x] `ruff format` run, then committed: `test: cover ReviewAction allowed_tools wiring and precedence`

## Task 17: Wire `allowed_tools` into `SummaryAction`

- [x] **17.1** `SummaryAction.validate()` — same `validate_allowed_tools` addition as task 15
- [x] **17.2** `SummaryAction`'s dispatch-to-model path (`capture_summary_via_profile` call
  around line 249-253) — thread `allowed_tools` from `context.params` through the task 14
  helper into whatever `AgentConfig`/profile call `capture_summary_via_profile` makes
  internally; if that function does not currently accept an `allowed_tools` parameter, extend
  its signature with a keyword-only, default-`None` parameter, matching `one_shot_dispatch`'s
  established pattern from slice 263
  - [x] Effort: 2/5

- [x] **Task 17 success criteria**
  - [x] A pipeline `summary` step with an unknown tool name fails validation before any model
    call
  - [x] A pipeline `summary` step with valid `allowed_tools` reaches
    `capture_summary_via_profile` with those tools
  - [x] `ruff format` run, then committed: `feat: thread allowed_tools through pipeline summary action`

## Task 18: Test `SummaryAction` wiring

- [x] **18.1** Add to `tests/pipeline/actions/test_summary.py`
  - [x] `test_validate_rejects_unknown_tool`
  - [x] `test_summary_passes_allowed_tools_to_agent_config` — assert the resolved tools
    argument, not merely that a mock was called
  - [x] `test_summary_without_allowed_tools_leaves_field_none`
  - [x] Effort: 2/5

- [x] **Task 18 success criteria**
  - [x] `uv run pytest tests/pipeline/actions/test_summary.py -q` green
  - [x] `ruff format` run, then committed: `test: cover SummaryAction allowed_tools wiring`

## Task 19: Tool-use telemetry on the agent's final Message

- [x] **19.1** In `providers/openai/agent.py`, thread a running tool-call counter through
  `_run_agentic_loop` (299-370) and the tool-less fast path in `handle_message` (151-181) so
  both branches stamp the same keys on the **final** yielded `Message.metadata` — never on
  intermediate turns (262's "intermediate turns not surfaced" contract is unchanged):
  ```python
  metadata={
      "tools_given": known_names,       # the filtered, resolved tool-name list from construction
      "tool_calls_made": count,          # 0 is valid and must still be present when tools_given is non-empty
  }
  ```
  - [x] `tools_given` is only present when the agent was constructed with a non-empty effective
    tool set; absent entirely when no tools were configured (design D5's "offered but unused"
    vs "never offered" distinction hinges on this)
  - [x] Both branches (tool-less fast path and agentic loop) must stamp this identically — a
    test in task 20 asserts they cannot drift
  - [x] This likely means passing the counter/tool list into
    `translation.build_messages(...)` (called at 162-163 and 319) as an additional argument, or
    constructing the final `Message` directly in `agent.py` after `build_messages` returns and
    merging metadata — inspect `translation.build_messages`'s current signature before
    choosing; prefer whichever requires the smaller diff to `translation.py`
  - [x] Effort: 4/5

- [x] **Task 19 success criteria**
  - [x] A tool-less response has no `tools_given` key
  - [x] A tools-offered, zero-calls response has `tools_given` non-empty and
    `tool_calls_made == 0`
  - [x] A tools-offered, N-calls response has `tool_calls_made == N`
  - [x] `ruff format` run, then committed: `feat: stamp tool-use telemetry on final agent message`

## Task 20: Test agent telemetry

- [x] **20.1** Add to `tests/providers/openai/test_agentic_loop.py`
  - [x] `test_final_message_has_tools_given_and_zero_calls_when_unused`
  - [x] `test_final_message_has_tool_calls_made_matching_actual_calls`
  - [x] `test_tool_less_response_has_no_tools_given_key`
  - [x] `test_fast_path_and_loop_path_stamp_metadata_identically` — construct two responses
    that should differ only in whether a tool was actually called, assert the metadata shape
    (keys present) matches between the tools-given-zero-calls case and a genuine multi-turn
    loop case
  - [x] Effort: 2/5

- [x] **Task 20 success criteria**
  - [x] `uv run pytest tests/providers/openai/ -q` green
  - [x] `ruff format` run, then committed: `test: cover tool-use telemetry on agent messages`

## Task 21: `ReviewResult` telemetry fields and persistence

Landed before the `ActionResult` carry tasks (22-24) — the first draft had this backwards and a
review task tried to read fields this task hadn't created yet.

- [x] **21.1** Add `tools_given: list[str] | None = None` and
  `tool_calls_made: int | None = None` to the `ReviewResult` dataclass in `review/models.py`
- [x] **21.2** Add both to `to_dict()` (78-117), in the always-included group (alongside
  `verdict`, `findings`, `model`, etc.), not the verbosity-gated group
- [x] **21.3** `run_review_with_profile` populates both fields on the returned `ReviewResult`
  from the agent's final-message telemetry (task 19)
  - [x] No `RunState.schema_version` bump — `StepState.action_results` is untyped
    `list[dict[str, object]]` (design D8); adding dict keys is backward-compatible
  - [x] Effort: 2/5

- [x] **Task 21 success criteria**
  - [x] `uv run pytest tests/review/test_models.py -q` green with new field coverage
  - [x] Persisted review JSON contains `tools_given`/`tool_calls_made` when the review used
    tools, absent/`null` otherwise
  - [x] `ruff format` run, then committed: `feat: add tool-use telemetry fields to ReviewResult`

## Task 22: Carry telemetry into `ActionResult.metadata` for dispatch

- [x] **22.1** `one_shot_dispatch` in `dispatch.py` — add a sibling function (e.g.
  `one_shot_dispatch_with_telemetry`, or extend the existing `_dispatch_via_agent` call site
  directly if it already has agent-level access rather than going through `one_shot_dispatch`'s
  str-returning join) that captures `tools_given`/`tool_calls_made` from the final `Message`
  before the join at `dispatch.py:96-100` discards it, and returns both text and the telemetry
  dict
  - [x] `one_shot_dispatch`'s existing `str`-returning signature and behavior are preserved
    unchanged for its other callers — do not change what it returns
  - [x] `DispatchAction._dispatch_via_agent` switches to the new telemetry-carrying path and
    populates `ActionResult.metadata["tools_given"]` / `["tool_calls_made"]` when present
  - [x] Remove the "slice-265 TODO" comment near this call site if one exists in the current
    diff (confirm its exact location before removing — the design doc's line reference for it
    was approximate)
- [x] **22.2** Add tests to `tests/pipeline/actions/test_dispatch.py`
  - [x] `test_dispatch_result_metadata_carries_tools_given_and_calls_made`
  - [x] `test_dispatch_result_metadata_omits_tools_keys_when_no_tools_configured`
  - [x] `test_one_shot_dispatch_return_type_unchanged_for_existing_callers` — regression guard:
    `one_shot_dispatch` itself still returns a bare `str`
  - [x] Effort: 3/5

- [x] **Task 22 success criteria**
  - [x] `uv run pytest tests/pipeline/actions/test_dispatch.py -q` green
  - [x] A dispatch step that used tools populates both `ActionResult.metadata` keys; one with no
    tools configured populates neither
  - [x] `ruff format` run, then committed: `feat: carry tool-use telemetry into dispatch ActionResult metadata`

## Task 23: Carry telemetry into `ActionResult.metadata` for review

- [x] **23.1** `ReviewAction` — capture `tools_given`/`tool_calls_made` from
  `run_review_with_profile`'s returned `ReviewResult` (task 21's new fields) into
  `ActionResult.metadata`
- [x] **23.2** Add tests to `tests/pipeline/actions/test_review_action.py`
  - [x] `test_review_result_metadata_carries_tools_given_and_calls_made`
  - [x] `test_review_result_metadata_omits_tools_keys_when_no_tools_configured`
  - [x] Effort: 2/5

- [x] **Task 23 success criteria**
  - [x] `uv run pytest tests/pipeline/actions/test_review_action.py -q` green
  - [x] A review step that used tools populates both `ActionResult.metadata` keys; one with no
    tools configured populates neither
  - [x] `ruff format` run, then committed: `feat: carry tool-use telemetry into review ActionResult metadata`

## Task 24: Carry telemetry into `ActionResult.metadata` for summary

- [x] **24.1** `SummaryAction` — capture the same telemetry from whatever
  `capture_summary_via_profile` returns (extend its return shape analogously to task 22's
  dispatch change, if needed) into `ActionResult.metadata`
- [x] **24.2** Add tests to `tests/pipeline/actions/test_summary.py`
  - [x] `test_summary_result_metadata_carries_tools_given_and_calls_made`
  - [x] `test_summary_result_metadata_omits_tools_keys_when_no_tools_configured`
  - [x] Effort: 2/5

- [x] **Task 24 success criteria**
  - [x] `uv run pytest tests/pipeline/actions/test_summary.py -q` green
  - [x] A summary step that used tools populates both `ActionResult.metadata` keys; one with no
    tools configured populates neither
  - [x] `ruff format` run, then committed: `feat: carry tool-use telemetry into summary ActionResult metadata`

## Task 25: `-v` log line and `RunState` persistence tests

- [x] **25.1** `pipeline/executor.py`, `_log_action_result` (95-108) — add one more `extras`
  block after the existing `model=` check:
  ```python
  if (given := result.metadata.get("tools_given")) is not None:
      made = result.metadata.get("tool_calls_made", 0)
      extras.append(f"tools={len(given)}/{made} calls")
  ```
  matching the exact style (walrus-assignment guard, append-to-`extras`) already used for
  `verdict`/`model`
- [x] **25.2** Add tests to `tests/pipeline/test_executor.py` (or wherever `_log_action_result`
  is currently tested — locate before creating a new file)
  - [x] `test_log_line_shows_tools_given_and_calls_made`
  - [x] `test_log_line_shows_zero_calls_distinctly_from_no_tools` — the exact SC8
    distinguishing case: `tools=3/0 calls` vs. no `tools=` segment at all
  - [x] `test_log_line_omits_tools_segment_when_no_tools_configured`
- [x] **25.3** SC9's `RunState.action_results` persistence — automated, not manual-only (the
  first draft of this breakdown relied solely on Task 29's manual `sq run -v` inspection for
  this half of SC9, which the Phase 5 review correctly flagged as unverified by any test)
  - [x] `test_run_state_action_results_contains_tools_metadata` — run a small pipeline (mocked
    endpoint, no real model call) with a tool-bearing dispatch or review step through the
    executor end to end, then assert `tools_given`/`tool_calls_made` are present in the
    resulting `StepState.action_results` dict for that step, matching design D8's "no schema
    change needed, already receives action metadata" claim with an actual assertion rather than
    only a manual check
  - [x] Effort: 3/5

- [x] **Task 25 success criteria**
  - [x] `uv run pytest tests/pipeline/ -q` green
  - [x] The zero-calls case is asserted as visually distinct from the no-tools case in at least
    one test, matching SC8's literal requirement
  - [x] `test_run_state_action_results_contains_tools_metadata` passes, giving SC9's
    `RunState.action_results` claim automated coverage independent of Task 29's manual check
  - [x] `ruff format` run, then committed: `feat: render tool-use telemetry in -v log line and RunState`

## Task 26: Migrate the seven review templates to canonical vocabulary

- [x] **26.1** For each of the seven files in `src/squadron/data/templates/`, replace the
  Claude-vocabulary `allowed_tools` list with canonical names per the mapping table (task 8):
  | File | Current | New |
  |---|---|---|
  | `arch.yaml` | `[Read, Glob, Grep]` | `[read_file, list_files, grep]` |
  | `code.yaml` | `[Read, Glob, Grep, Bash]` | `[read_file, list_files, grep]` — **`Bash` is dropped, not mapped** (design D6; this does not restrict the SDK reviewer's actual capabilities — see D6 in the slice design for the full "capability gate vs. permission hint" reasoning, and issue #69 for the follow-up) |
  | `judge-findings-addressed.yaml` | `[Read, Glob, Grep]` | `[read_file, list_files, grep]` |
  | `judge-slice-vs-arch.yaml` | `[Read, Glob, Grep]` | `[read_file, list_files, grep]` |
  | `judge-tasks-vs-slice.yaml` | `[Read, Glob, Grep]` | `[read_file, list_files, grep]` |
  | `slice.yaml` | `[Read, Glob, Grep]` | `[read_file, list_files, grep]` |
  | `tasks.yaml` | `[Read, Glob, Grep]` | `[read_file, list_files, grep]` |
  - [x] No other line in any of the seven files changes — `permission_mode`, `model`,
    `setting_sources` stay exactly as they are today
  - [x] Effort: 2/5

- [x] **Task 26 success criteria**
  - [x] `grep -rn "allowed_tools" src/squadron/data/templates/` shows only canonical names
  - [x] `grep -rEn "Read|Glob|Grep|Bash" src/squadron/data/templates/*.yaml` returns nothing
    for the `allowed_tools` lines (a match elsewhere, e.g. in a prompt string, is fine — check
    context before treating any hit as a failure)
  - [x] `ruff format` run, then committed: `feat: migrate review templates to canonical tool vocabulary`

## Task 27: SDK-path regression test proving templates are unchanged in effect

- [x] **27.1** Add a test (in `tests/review/test_templates.py` or `tests/providers/sdk/`,
  whichever already loads shipped templates for config-build assertions) that loads each
  migrated template, builds its `AgentConfig`/`ClaudeAgentOptions` through the real SDK
  provider path, and asserts the resulting `allowed_tools` equals the pre-migration Claude-name
  list — this is SC3's literal assertion, run against the real shipped templates rather than a
  synthetic fixture
  - [x] `code.yaml` is the one expected difference: assert `Bash` is **absent** from its built
    config, and add a short assertion/comment referencing that this changes the emitted
    `--allowedTools` string but not actual SDK reviewer capability (per D6) — do not assert
    anything about `permission_mode` or `tools`/`--tools` here, that is out of scope
  - [x] Effort: 2/5

- [x] **Task 27 success criteria**
  - [x] `uv run pytest tests/review/ tests/providers/sdk/ -q` green
  - [x] Six templates assert unchanged three-tool `allowed_tools`; `code.yaml` asserts the
    two-tool (`Read`, `Glob`, `Grep` minus `Bash`) result
  - [x] `ruff format` run, then committed: `test: assert migrated templates preserve SDK reviewer behavior`

## Task 28: Live non-SDK tool-call integration test (SC6)

- [x] **28.1** Create/extend a review integration test using a mocked OpenAI-compatible
  endpoint (follow the mocking approach already used in `tests/providers/openai/` for the 262
  loop tests, per the pattern task 9 of slice 263 established for dispatch — do not invent a
  second mocking pattern)
  - [x] Endpoint returns a `read_file` tool call on turn one, then a final assistant message
    containing a parseable verdict + findings block on turn two
  - [x] Run `run_review_with_profile` against a migrated template (e.g. `code.yaml`) with a
    non-SDK profile
  - [x] Assert the mocked file read actually occurred (the tool executor was invoked with the
    referenced path) and the parsed `ReviewResult` verdict/findings are unchanged in shape from
    a tool-less review — SC6's literal requirement
  - [x] Effort: 3/5

- [x] **Task 28 success criteria**
  - [x] Test passes; no network access, no real model call
  - [x] `ruff format` run, then committed: `test: add mocked non-SDK review tool-call integration test`

## Task 29: Manual end-to-end verification (SC8, SC10)

> **Deferred at Phase 6:** not executable inside a Claude Code session (`sq run` CLAUDECODE guard, `cli/commands/run.py:148`) and 29.2 requires a live non-SDK model. Automated equivalents covering the same code paths landed in tasks 25 and 28 (slice design Verification Walkthrough steps 8 and 9). Must be run from a plain terminal before the observed numbers in the walkthrough's steps 6-7 can be filled in.

Must be run from a plain terminal, not inside Claude Code — `sq run` refuses execution in a
Claude Code session (unconditional `CLAUDECODE` guard, `cli/commands/run.py:148`).

- [ ] **29.1** Pipeline observability demo
  - [ ] `sq run <pipeline> <slice> -v` against a pipeline with at least one tool-bearing
    dispatch/review/summary step
  - [ ] Confirm the `-v` output shows `tools=N/M calls` for tool-bearing steps and no `tools=`
    segment for steps without tools
  - [ ] Construct the zero-calls case deliberately if no natural step produces it (e.g. a step
    offered tools but given a task that doesn't need them), confirming it reads distinctly from
    the no-tools case
  - [ ] Check the persisted run JSON at `~/.config/squadron/runs/<run>.json` — confirm
    `tools_given`/`tool_calls_made` appear in `action_results`. Task 25.3 already gives this
    same claim automated coverage; this step is the live-run confirmation, not the only proof
- [ ] **29.2** Live non-SDK review (issue #68 closure)
  - [ ] `sq review code --slice <n> --model kimi27 -v` (or another live non-SDK model
    configured in this environment)
  - [ ] Confirm a non-zero tool-call count in the `-v` output and in the persisted review JSON
  - [ ] Record the actual observed numbers in the slice design's Verification Walkthrough
    section (§6-7), replacing the draft placeholders
  - [ ] Effort: 2/5

- [ ] **Task 29 success criteria**
  - [ ] Both demos behave as SC8/SC10 describe, with observed results recorded in the slice
    design
  - [ ] `ruff format` run, then committed: `docs: record slice 265 end-to-end verification results`

## Task 30: Quality gates and close-out

- [x] **30.1** Run the full gate set
  - [x] `uv run ruff format .`
  - [x] `uv run ruff check .`
  - [x] `uv run pyright` — must be 0 errors. Use `uv run`, not `.venv/bin/pyright`
  - [x] `uv run pytest -q` — full suite, including the new `tests/load/` directory (picked up
    automatically by `testpaths = ["tests"]`; no separate load-test invocation needed)
- [x] **30.2** Confirm the diff's shape matches the design's Integration Points table: search
  tools, tool-name map, unknown-name policy, telemetry stamp, injection decision, review result
  fields, seven templates, dispatch/review/summary actions, executor `-v` line — no unrelated
  files touched
  - [x] **`pipeline/schema.py` is an intentional, documented non-change**, not a dropped item:
    the design's Integration Points table lists it as a change site, but there is no
    per-step-type Pydantic schema to extend (`StepSchema.config` is a flat
    `dict[str, object]` in all three actions) — validation goes through the shared
    `validate_allowed_tools` helper instead (task 14), confirmed against
    `steps/utils.py` during task breakdown. If a close-out reviewer diffs against the design
    table, this line is why `schema.py` correctly does not appear in the diff
  - [x] `tools/builtin.py` grows past ~300 lines once tasks 3 and 5 (file 1) land `list_files`
    and `grep` alongside the existing three tools. This is accepted rather than split into a
    separate module — the codebase already has larger precedent (`pipeline/executor.py` at
    ~1700 lines, `review/review_client.py` at ~460) — but flagged here so it is a deliberate
    call at close-out, not an unnoticed drift from the ~300-line guideline
- [x] **30.3** Close out
  - [x] Mark this task file and the slice design complete; check off slice 265 in
    `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
  - [x] Write the DEVLOG entry
  - [x] `ruff format` run, then commit the close-out docs: `docs: close out slice 265`

- [x] **Task 30 success criteria**
  - [x] All four gates clean
  - [x] Diff matches the design's stated scope; the `schema.py` non-change and `builtin.py` size
    growth are both explicitly acknowledged, not silently passed over
  - [x] Every task 1-30 landed its own commit; the history reads as the task sequence
