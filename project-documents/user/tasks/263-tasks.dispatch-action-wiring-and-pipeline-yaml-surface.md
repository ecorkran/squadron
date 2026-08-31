---
docType: tasks
project: squadron
slice: 263-slice.dispatch-action-wiring-and-pipeline-yaml-surface
lldReference: project-documents/user/slices/263-slice.dispatch-action-wiring-and-pipeline-yaml-surface.md
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [262]
dateCreated: 20260831
dateUpdated: 20260831
status: in_progress
---

# Tasks: Dispatch Action Wiring and Pipeline YAML Surface

## Context Summary

Slice 262 shipped an agentic loop that `OpenAICompatibleAgent` runs **when given tools**.
Nothing gives it tools: no pipeline YAML can declare them, and the one-shot dispatch path
builds its `AgentConfig` without `allowed_tools` and with a hardcoded `cwd=None`. This slice
opens that surface end to end.

Five files change. Nothing changes in `schema.py`, `loader.py`, `executor.py`,
`core/models.py`, the agent, or the provider — the design uses existing extension points
rather than adding one.

Two facts from the shipped 262 code drive the whole breakdown, and a junior implementer must
not lose either:

1. **`cwd` travels with `allowed_tools`.** `OpenAICompatibleAgent.__init__` raises
   `ProviderError` when `allowed_tools` is non-empty and `cwd is None`
   ([agent.py:115-119](../../../src/squadron/providers/openai/agent.py#L115-L119)), while
   `one_shot_dispatch` passes `cwd=None` unconditionally
   ([dispatch.py:65](../../../src/squadron/pipeline/actions/dispatch.py#L65)). Wiring tools
   without `cwd` fails 100% of the time on any step declaring a tool. Task 4 threads both.

2. **Validation at load time is the substance of the slice.** The agent drops unknown tool
   names with a WARNING and continues
   ([agent.py:127-133](../../../src/squadron/providers/openai/agent.py#L127-L133)) — kept
   deliberately (design D5) so review templates carrying Claude-vocabulary names survive
   until slice 265. Without a load-time check, `allowed_tools: [read_fil]` runs the step with
   no tools and the model writes prose describing a file it never created. Tasks 1–3 are that
   check.

Registered tool names today are exactly `read_file`, `write_file`, `bash`
(`src/squadron/tools/builtin.py:26-28`). The registry is the authority — never hard-code this
list in source; read it via `tools.list_tools()`.

**Sequencing:** tasks are ordered so each one leaves the suite green. Tasks 1–3 add validation
with nothing yet producing the field; task 4 threads it; tasks 5–6 prove the end-to-end path.
Test tasks immediately follow their implementation task.

**Commit protocol — applies to every task below.** Because each task leaves the suite green,
each task ends with a commit rather than batching them at close-out. For every task:

1. `uv run ruff format .` — immediately before the commit, never skipped
2. `git add` from the project root and commit with a semantic message
   (`feat:`, `test:`, `refactor:`, `docs:`, `chore:` — see CLAUDE.md Git Rules)
3. The relevant scoped test command passes first; a task is not done until it is committed

This keeps an interruption from losing prior work and makes the history match the task-by-task
narrative. Each task's success criteria restate the commit as its final checkbox.

**Branch.** This is Phase 6 implementation work, so it happens on
`263-slice.dispatch-action-wiring-and-pipeline-yaml-surface`. Before creating it, read
`cf config get git.integration_branch` and fork from that value (or `main` if empty) — do not
assume the value recorded at plan-authoring time is still current.

---

## Task 1: Shared `validate_allowed_tools` helper

- [x] **1.1** Add `validate_allowed_tools` to `src/squadron/pipeline/steps/utils.py`
  - [x] Signature: `def validate_allowed_tools(config: StepConfig, action_type: str) -> list[ValidationError]:`
  - [x] Import `ValidationError` from `squadron.pipeline.models` (`StepConfig` is already imported there)
  - [x] Return `[]` immediately when the `allowed_tools` key is absent from `config.config` — absence is valid and must cost nothing
  - [x] Add `"validate_allowed_tools"` to the module's existing `__all__` list
- [x] **1.2** Implement the type check
  - [x] Value is not a `list` → one `ValidationError(field="allowed_tools", message=..., action_type=action_type)` stating the field must be a list of tool names; return immediately (do not proceed to membership checks on a non-list)
  - [x] Value is a list containing any non-`str` element → one `ValidationError` naming the offending element and stating entries must be strings; return immediately
- [x] **1.3** Implement the registry membership check
  - [x] Import `squadron.tools` **locally inside the function**, not at module scope. Registering built-ins is an import side effect of that package (`tools/__init__.py`), and it is otherwise only reachable through the lazily loaded openai provider — a module-scope import would change import ordering for every step type
  - [x] For each name absent from `tools.list_tools()`, append its own `ValidationError` so a YAML with two typos reports both in one pass rather than one per fix cycle
  - [x] Message names the offending tool and lists the registered tools, matching the shape of `ToolNotRegisteredError` in `tools/registry.py`
  - [x] Effort: 2/5

- [x] **Task 1 success criteria**
  - [x] Absent key returns `[]`
  - [x] Non-list value, and list-with-non-string, each return exactly one error with distinct messages
  - [x] Two unknown names return two errors
  - [x] No hard-coded tool-name list anywhere in the function
  - [x] `ruff format` run, then committed: `feat: add validate_allowed_tools helper for pipeline step configs`

## Task 2: Test the helper

- [x] **2.1** Create `tests/pipeline/steps/test_allowed_tools_validation.py`
  - [x] `test_absent_field_returns_no_errors`
  - [x] `test_valid_tool_names_return_no_errors` — use `read_file` and `write_file`
  - [x] `test_non_list_value_returns_type_error` — e.g. the string `"read_file"`, a common YAML mistake (`allowed_tools: read_file` without brackets)
  - [x] `test_list_with_non_string_returns_type_error` — e.g. `[read_file, 42]`
  - [x] `test_unknown_tool_name_returns_error` — assert the offending name appears in the message
  - [x] `test_two_unknown_names_return_two_errors` — guards the accumulate-don't-short-circuit behavior
  - [x] `test_error_carries_action_type` — assert `action_type` matches what was passed
- [x] **2.2** Assert on error content, not just count
  - [x] At least one test asserts `field == "allowed_tools"`
  - [x] The unknown-name test asserts the message contains the bad name — a test that only counts errors would pass against a message that names the wrong tool
  - [x] Effort: 2/5

- [x] **Task 2 success criteria**
  - [x] `uv run pytest tests/pipeline/steps/test_allowed_tools_validation.py -q` green
  - [x] Tests call the helper directly; no pipeline load or model call involved
  - [x] `ruff format` run, then committed: `test: add coverage for validate_allowed_tools`

## Task 3: Wire validation into the four step types

- [x] **3.1** `DispatchStepType.validate` in `src/squadron/pipeline/steps/dispatch.py`
  - [x] Extend the returned `errors` list with `validate_allowed_tools(config, self.step_type)`
  - [x] Place the call after the existing `pre_emption_fragment` check, before `return errors`
- [x] **3.2** `PhaseStepType.validate` in `src/squadron/pipeline/steps/phase.py`
  - [x] Same extension, using `self._phase_name` as `action_type` (matching the other errors this method builds)
  - [x] One edit covers all three registered phase step types (`design`, `tasks`, `implement`) — they are three instances of one class, not three classes
- [x] **3.3** Confirm no `loader.py` change is needed
  - [x] `validate_pipeline` already calls `step_impl.validate(step)` for every step
    ([loader.py:203](../../../src/squadron/pipeline/loader.py#L203)) and all six
    `cli/commands/run.py` call sites already surface the result. If you find yourself editing
    `loader.py`, stop — the design's D1 says the extension point already exists
  - [x] Effort: 1/5

- [x] **Task 3 success criteria**
  - [x] A pipeline definition with a bad tool name on a `dispatch` step yields a `ValidationError` from `validate_pipeline`
  - [x] The same is true for a `design` step
  - [x] `loader.py` is unmodified in the diff
  - [x] `ruff format` run, then committed: `feat: validate allowed_tools in dispatch and phase step types`

## Task 4: Test step-type validation through the loader

- [x] **4.1** Add tests to `tests/pipeline/steps/test_dispatch_step.py`
  - [x] `test_validate_accepts_known_tools`
  - [x] `test_validate_rejects_unknown_tool`
- [x] **4.2** Add the equivalent tests to `tests/pipeline/steps/test_phase.py`
  - [x] Use the existing `design_step` fixture already in that file
- [x] **4.3** Add one end-to-end validation test exercising `validate_pipeline`
  - [x] Build a `PipelineDefinition` containing a step with an unknown tool name, call `validate_pipeline`, assert a non-empty error list mentioning the bad name
  - [x] This is the test that proves the check is actually reachable from the real entry point rather than only callable in isolation
  - [x] Effort: 2/5

- [x] **Task 4 success criteria**
  - [x] `uv run pytest tests/pipeline/ -q` green
  - [x] Pre-existing exact-equality `expand()` tests in both files still pass **unmodified**
  - [x] `ruff format` run, then committed: `test: cover allowed_tools validation through validate_pipeline`

## Task 5: Conditional pass-through in `expand()`

- [x] **5.1** `DispatchStepType.expand` in `src/squadron/pipeline/steps/dispatch.py`
  - [x] Add `if "allowed_tools" in cfg: action_config["allowed_tools"] = cfg["allowed_tools"]`
  - [x] Follow the existing conditional style used for `prompt`, `model`, and `pre_emption_fragment`
- [x] **5.2** `PhaseStepType.expand` in `src/squadron/pipeline/steps/phase.py`
  - [x] Add the same conditional to `dispatch_config`, adjacent to the existing
    `pre_emption_fragment` conditional
  - [x] **Conditional, never unconditional.** An absent key must leave the expanded dict
    byte-identical to its pre-slice shape. The existing exact-equality `expand()` tests assert
    on whole dicts and will fail on an added `"allowed_tools": None` key — that failure is the
    guard working, not a test to update
  - [x] The field goes only into the `dispatch` action's config. Do **not** add it to the
    `review`, `checkpoint`, `commit`, or `cf-op` entries — the review path is slice 265
  - [x] Effort: 1/5

- [x] **Task 5 success criteria**
  - [x] Declared field reaches the expanded dispatch action config unchanged
  - [x] Absent field leaves expansion byte-identical; existing tests pass with zero edits
  - [x] `ruff format` run, then committed: `feat: forward allowed_tools through dispatch and phase expand`

## Task 6: Test expansion

- [x] **6.1** Add to `tests/pipeline/steps/test_dispatch_step.py`
  - [x] `test_expand_forwards_allowed_tools` — mirror the existing
    `test_expand_forwards_pre_emption_fragment`
  - [x] `test_expand_omits_allowed_tools_when_absent` — assert the key is not present in the
    expanded config
- [x] **6.2** Add the equivalent two tests to `tests/pipeline/steps/test_phase.py`
  - [x] Assert the field lands on the `dispatch` action entry and on no other action in the
    expanded list
  - [x] Effort: 1/5

- [x] **Task 6 success criteria**
  - [x] All four tests green; the omission tests fail if the conditional is made unconditional
  - [x] `ruff format` run, then committed: `test: cover allowed_tools expansion pass-through`

## Task 7: Thread `allowed_tools` and `cwd` through the dispatch action

- [x] **7.1** Extend `one_shot_dispatch` in `src/squadron/pipeline/actions/dispatch.py`
  - [x] Add keyword-only params `allowed_tools: list[str] | None = None` and
    `cwd: str | None = None`, both defaulting to `None` so existing direct callers keep
    today's behavior exactly
  - [x] Pass both into the `AgentConfig(...)` construction
  - [x] Replace the hardcoded `cwd=None` literal with the parameter
- [x] **7.2** Extend `DispatchAction._dispatch_via_agent`
  - [x] Read `allowed_tools` from `context.params` — the same source already used for `model`,
    `profile`, `system_prompt`, and `pre_emption_fragment`
  - [x] Pass `cwd=context.cwd` **unconditionally**, not only when tools are declared (design
    D2). `AgentConfig.cwd` is inert for the non-SDK agent unless tools are configured, and
    unconditional threading removes the latent `ProviderError` path entirely
- [x] **7.3** Narrow the type at the params boundary
  - [x] `context.params` is `dict[str, object]`; narrow the value to `list[str]` before passing
  - [x] A value that is not a list of strings here is a defect that task 1's validation should
    have caught, so **raise** rather than silently dropping tools — the project forbids silent
    fallbacks, and a silent drop reproduces exactly the failure this slice exists to prevent
  - [x] Do **not** re-check names against the registry here. Load time is the single authority
    (design D3); a second copy of the "unknown tool" message would drift from the first
  - [x] Leave `_dispatch_via_session` (the SDK path) untouched
  - [x] Effort: 2/5

- [x] **Task 7 success criteria**
  - [x] `AgentConfig.cwd` is populated from `context.cwd` on every agent dispatch
  - [x] `AgentConfig.allowed_tools` carries the declared names exactly
  - [x] No tool-name registry lookup exists in `actions/dispatch.py`
  - [x] `ruff format` run, then committed: `feat: thread allowed_tools and cwd into AgentConfig from dispatch`

## Task 8: Test the threading

- [x] **8.1** Add tests to `tests/pipeline/actions/test_dispatch.py`
  - [x] `test_dispatch_passes_allowed_tools_to_agent_config` — assert on the constructed
    `AgentConfig`, not merely that a mock was called
  - [x] `test_dispatch_passes_cwd_to_agent_config` — assert `AgentConfig.cwd == context.cwd`
  - [x] `test_dispatch_passes_cwd_even_without_tools` — the D2 regression guard
  - [x] `test_dispatch_without_allowed_tools_leaves_field_none`
- [x] **8.2** Add the list-integrity test
  - [x] `test_allowed_tools_list_survives_param_resolution` — assert the value arriving at
    `AgentConfig` is a `list[str]` with the exact declared names
  - [x] This covers the design's one named risk: `allowed_tools` is the first list-valued step
    config field to travel the param-placeholder resolution path, which is exercised on scalars
    everywhere else
- [x] **8.3** Add the malformed-value test
  - [x] Assert a non-list value in `context.params` raises rather than silently dropping tools
  - [x] Effort: 2/5

- [x] **Task 8 success criteria**
  - [x] `uv run pytest tests/pipeline/actions/ -q` green
  - [x] Every assertion inspects the resulting `AgentConfig` field values
  - [x] `ruff format` run, then committed: `test: assert allowed_tools and cwd reach AgentConfig`

## Task 9: End-to-end integration test with a mocked endpoint

- [x] **9.1** Create `tests/pipeline/test_dispatch_tools.py`
  - [x] Stand up a mocked OpenAI-compatible endpoint returning two turns: first a `write_file`
    tool call, then a final assistant message with text and no `tool_calls`
  - [x] Follow the mocking approach already used in `tests/providers/openai/` for the 262 loop
    tests rather than inventing a second pattern
  - [x] Run a one-step pipeline with `allowed_tools: [write_file]` in a `tmp_path` cwd
- [x] **9.2** Assert on real effects
  - [x] The file **exists on disk** at the expected path with the expected content — this is
    the assertion that would have caught the silent-no-op class of bug (issue #15)
  - [x] The dispatch `ActionResult.success` is `True` and `outputs["response"]` carries the
    final turn's text, not the tool-call turn
  - [x] Effort: 3/5

- [x] **Task 9 success criteria**
  - [x] Test passes and fails loudly if `cwd` threading is reverted
  - [x] No network access; no real model call
  - [x] `ruff format` run, then committed: `test: add end-to-end dispatch tool-call integration test`

## Task 10: Ship `allowed_tools` in `test-p4.yaml`

- [x] **10.1** Edit `src/squadron/data/pipelines/test-p4.yaml`
  - [x] Add `allowed_tools: [read_file, write_file]` to the `design` step, as a sibling of
    `phase`, `model`, and `review`
  - [x] Do **not** add `bash` (design D4) — the demo proves file writing, and `bash` is
    unrestricted beyond CWD scoping, widening the blast radius of a shipped pipeline with no
    added demonstrated capability
  - [x] Leave the `summary` step untouched — the summary path is slice 265
- [x] **10.2** Verify the shipped pipeline still validates
  - [x] `uv run sq run test-p4 --slice 263 --dry-run` exits zero
  - [x] Effort: 1/5

- [x] **Task 10 success criteria**
  - [x] `test-p4.yaml` declares exactly `read_file` and `write_file` on the design step
  - [x] Dry-run validation passes
  - [x] `ruff format` run, then committed: `feat: declare allowed_tools on test-p4 design step`

## Task 11: Manual end-to-end verification

- [x] **11.1** Negative case first — prove the validation gate
  - [x] Temporarily set a bad tool name in a scratch pipeline and confirm the run fails before
    any model call, with an error naming the bad tool and listing registered ones
- [ ] **11.2** Positive case — real non-SDK model
  - [ ] `uv run sq run test-p4 <an unstarted slice index> -v` (positional, not `--slice`)
  - [ ] Confirm the slice-design file **exists on disk** afterward and the review step finds it
    as input rather than reporting a missing artifact
- [ ] **11.3** Contrast case — prove the field is what changed
  - [ ] Remove the `allowed_tools` line, re-run, and confirm the model produces prose and no
    file appears. That contrast is the slice's whole point and is the evidence for the
    verification walkthrough
  - [ ] Record the outcome in the slice design's Verification Walkthrough section
  - [ ] Effort: 2/5

- **Note:** 11.2 and 11.3 deferred — `sq run` refuses execution inside Claude Code (unconditional CLAUDECODE guard at `src/squadron/cli/commands/run.py:148`). These must be run from a standard terminal.

- [ ] **Task 11 success criteria**
  - [ ] All three cases behave as described, with the observed results recorded
  - [ ] `ruff format` run, then committed: `docs: record slice 263 end-to-end verification results`

## Task 12: Quality gates and close-out

- [x] **12.1** Run the full gate set
  - [x] `uv run ruff format .`
  - [x] `uv run ruff check .`
  - [x] `uv run pyright` — must be 0 errors. Use `uv run`, not `.venv/bin/pyright`: the local
    venv cannot resolve `openai` and reports large phantom counts
  - [x] `uv run pytest -q` — full suite. Takes ~7 minutes and includes metrology tests that
    perform real `time.sleep`; this is expected, not a hang. Do not kill it
- [x] **12.2** Confirm the diff's shape matches the design
  - [x] Exactly five source files changed: `steps/utils.py`, `steps/dispatch.py`,
    `steps/phase.py`, `actions/dispatch.py`, `data/pipelines/test-p4.yaml`
  - [x] `schema.py`, `loader.py`, `executor.py`, `core/models.py`, the agent, and the provider
    are unmodified. Any change there means the design was departed from — stop and reconcile
    before committing
- [x] **12.3** Close out
  - [x] Mark this task file and the slice design complete; check off slice 263 in
    `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
  - [x] Write the DEVLOG entry
  - [x] `ruff format` run, then commit the close-out docs: `docs: close out slice 263`
- [ ] **12.4** Merge
  - [ ] Re-read `cf config get git.integration_branch` **now**, at merge time — do not rely on
    the value recorded when this file was written, or on what the branch was forked from. The
    merge target is that value, or `main` if it is empty
  - [ ] Merge the slice branch into that target with `--no-ff`
  - [ ] Do not delete the branch, and do not push — both are PM actions
  - [ ] Effort: 1/5

- [ ] **Task 12 success criteria**
  - [ ] All four gates clean
  - [ ] Diff touches only the five named source files plus tests
  - [ ] Every task 1–11 landed its own commit; the history reads as the task sequence
  - [ ] Merge target was re-read at merge time, not assumed
