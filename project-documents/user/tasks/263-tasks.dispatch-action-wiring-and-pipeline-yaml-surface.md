---
docType: tasks
project: squadron
slice: 263-slice.dispatch-action-wiring-and-pipeline-yaml-surface
lldReference: project-documents/user/slices/263-slice.dispatch-action-wiring-and-pipeline-yaml-surface.md
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [262]
dateCreated: 20260831
dateUpdated: 20260831
status: not_started
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

---

## Task 1: Shared `validate_allowed_tools` helper

- [ ] **1.1** Add `validate_allowed_tools` to `src/squadron/pipeline/steps/utils.py`
  - [ ] Signature: `def validate_allowed_tools(config: StepConfig, action_type: str) -> list[ValidationError]:`
  - [ ] Import `ValidationError` from `squadron.pipeline.models` (`StepConfig` is already imported there)
  - [ ] Return `[]` immediately when the `allowed_tools` key is absent from `config.config` — absence is valid and must cost nothing
  - [ ] Add `"validate_allowed_tools"` to the module's existing `__all__` list
- [ ] **1.2** Implement the type check
  - [ ] Value is not a `list` → one `ValidationError(field="allowed_tools", message=..., action_type=action_type)` stating the field must be a list of tool names; return immediately (do not proceed to membership checks on a non-list)
  - [ ] Value is a list containing any non-`str` element → one `ValidationError` naming the offending element and stating entries must be strings; return immediately
- [ ] **1.3** Implement the registry membership check
  - [ ] Import `squadron.tools` **locally inside the function**, not at module scope. Registering built-ins is an import side effect of that package (`tools/__init__.py`), and it is otherwise only reachable through the lazily loaded openai provider — a module-scope import would change import ordering for every step type
  - [ ] For each name absent from `tools.list_tools()`, append its own `ValidationError` so a YAML with two typos reports both in one pass rather than one per fix cycle
  - [ ] Message names the offending tool and lists the registered tools, matching the shape of `ToolNotRegisteredError` in `tools/registry.py`
  - [ ] Effort: 2/5

- [ ] **Task 1 success criteria**
  - [ ] Absent key returns `[]`
  - [ ] Non-list value, and list-with-non-string, each return exactly one error with distinct messages
  - [ ] Two unknown names return two errors
  - [ ] No hard-coded tool-name list anywhere in the function

## Task 2: Test the helper

- [ ] **2.1** Create `tests/pipeline/steps/test_allowed_tools_validation.py`
  - [ ] `test_absent_field_returns_no_errors`
  - [ ] `test_valid_tool_names_return_no_errors` — use `read_file` and `write_file`
  - [ ] `test_non_list_value_returns_type_error` — e.g. the string `"read_file"`, a common YAML mistake (`allowed_tools: read_file` without brackets)
  - [ ] `test_list_with_non_string_returns_type_error` — e.g. `[read_file, 42]`
  - [ ] `test_unknown_tool_name_returns_error` — assert the offending name appears in the message
  - [ ] `test_two_unknown_names_return_two_errors` — guards the accumulate-don't-short-circuit behavior
  - [ ] `test_error_carries_action_type` — assert `action_type` matches what was passed
- [ ] **2.2** Assert on error content, not just count
  - [ ] At least one test asserts `field == "allowed_tools"`
  - [ ] The unknown-name test asserts the message contains the bad name — a test that only counts errors would pass against a message that names the wrong tool
  - [ ] Effort: 2/5

- [ ] **Task 2 success criteria**
  - [ ] `uv run pytest tests/pipeline/steps/test_allowed_tools_validation.py -q` green
  - [ ] Tests call the helper directly; no pipeline load or model call involved

## Task 3: Wire validation into the four step types

- [ ] **3.1** `DispatchStepType.validate` in `src/squadron/pipeline/steps/dispatch.py`
  - [ ] Extend the returned `errors` list with `validate_allowed_tools(config, self.step_type)`
  - [ ] Place the call after the existing `pre_emption_fragment` check, before `return errors`
- [ ] **3.2** `PhaseStepType.validate` in `src/squadron/pipeline/steps/phase.py`
  - [ ] Same extension, using `self._phase_name` as `action_type` (matching the other errors this method builds)
  - [ ] One edit covers all three registered phase step types (`design`, `tasks`, `implement`) — they are three instances of one class, not three classes
- [ ] **3.3** Confirm no `loader.py` change is needed
  - [ ] `validate_pipeline` already calls `step_impl.validate(step)` for every step
    ([loader.py:203](../../../src/squadron/pipeline/loader.py#L203)) and all six
    `cli/commands/run.py` call sites already surface the result. If you find yourself editing
    `loader.py`, stop — the design's D1 says the extension point already exists
  - [ ] Effort: 1/5

- [ ] **Task 3 success criteria**
  - [ ] A pipeline definition with a bad tool name on a `dispatch` step yields a `ValidationError` from `validate_pipeline`
  - [ ] The same is true for a `design` step
  - [ ] `loader.py` is unmodified in the diff

## Task 4: Test step-type validation through the loader

- [ ] **4.1** Add tests to `tests/pipeline/steps/test_dispatch_step.py`
  - [ ] `test_validate_accepts_known_tools`
  - [ ] `test_validate_rejects_unknown_tool`
- [ ] **4.2** Add the equivalent tests to `tests/pipeline/steps/test_phase.py`
  - [ ] Use the existing `design_step` fixture already in that file
- [ ] **4.3** Add one end-to-end validation test exercising `validate_pipeline`
  - [ ] Build a `PipelineDefinition` containing a step with an unknown tool name, call `validate_pipeline`, assert a non-empty error list mentioning the bad name
  - [ ] This is the test that proves the check is actually reachable from the real entry point rather than only callable in isolation
  - [ ] Effort: 2/5

- [ ] **Task 4 success criteria**
  - [ ] `uv run pytest tests/pipeline/ -q` green
  - [ ] Pre-existing exact-equality `expand()` tests in both files still pass **unmodified**

## Task 5: Conditional pass-through in `expand()`

- [ ] **5.1** `DispatchStepType.expand` in `src/squadron/pipeline/steps/dispatch.py`
  - [ ] Add `if "allowed_tools" in cfg: action_config["allowed_tools"] = cfg["allowed_tools"]`
  - [ ] Follow the existing conditional style used for `prompt`, `model`, and `pre_emption_fragment`
- [ ] **5.2** `PhaseStepType.expand` in `src/squadron/pipeline/steps/phase.py`
  - [ ] Add the same conditional to `dispatch_config`, adjacent to the existing
    `pre_emption_fragment` conditional
  - [ ] **Conditional, never unconditional.** An absent key must leave the expanded dict
    byte-identical to its pre-slice shape. The existing exact-equality `expand()` tests assert
    on whole dicts and will fail on an added `"allowed_tools": None` key — that failure is the
    guard working, not a test to update
  - [ ] The field goes only into the `dispatch` action's config. Do **not** add it to the
    `review`, `checkpoint`, `commit`, or `cf-op` entries — the review path is slice 265
  - [ ] Effort: 1/5

- [ ] **Task 5 success criteria**
  - [ ] Declared field reaches the expanded dispatch action config unchanged
  - [ ] Absent field leaves expansion byte-identical; existing tests pass with zero edits

## Task 6: Test expansion

- [ ] **6.1** Add to `tests/pipeline/steps/test_dispatch_step.py`
  - [ ] `test_expand_forwards_allowed_tools` — mirror the existing
    `test_expand_forwards_pre_emption_fragment`
  - [ ] `test_expand_omits_allowed_tools_when_absent` — assert the key is not present in the
    expanded config
- [ ] **6.2** Add the equivalent two tests to `tests/pipeline/steps/test_phase.py`
  - [ ] Assert the field lands on the `dispatch` action entry and on no other action in the
    expanded list
  - [ ] Effort: 1/5

- [ ] **Task 6 success criteria**
  - [ ] All four tests green; the omission tests fail if the conditional is made unconditional

## Task 7: Thread `allowed_tools` and `cwd` through the dispatch action

- [ ] **7.1** Extend `one_shot_dispatch` in `src/squadron/pipeline/actions/dispatch.py`
  - [ ] Add keyword-only params `allowed_tools: list[str] | None = None` and
    `cwd: str | None = None`, both defaulting to `None` so existing direct callers keep
    today's behavior exactly
  - [ ] Pass both into the `AgentConfig(...)` construction
  - [ ] Replace the hardcoded `cwd=None` literal with the parameter
- [ ] **7.2** Extend `DispatchAction._dispatch_via_agent`
  - [ ] Read `allowed_tools` from `context.params` — the same source already used for `model`,
    `profile`, `system_prompt`, and `pre_emption_fragment`
  - [ ] Pass `cwd=context.cwd` **unconditionally**, not only when tools are declared (design
    D2). `AgentConfig.cwd` is inert for the non-SDK agent unless tools are configured, and
    unconditional threading removes the latent `ProviderError` path entirely
- [ ] **7.3** Narrow the type at the params boundary
  - [ ] `context.params` is `dict[str, object]`; narrow the value to `list[str]` before passing
  - [ ] A value that is not a list of strings here is a defect that task 1's validation should
    have caught, so **raise** rather than silently dropping tools — the project forbids silent
    fallbacks, and a silent drop reproduces exactly the failure this slice exists to prevent
  - [ ] Do **not** re-check names against the registry here. Load time is the single authority
    (design D3); a second copy of the "unknown tool" message would drift from the first
  - [ ] Leave `_dispatch_via_session` (the SDK path) untouched
  - [ ] Effort: 2/5

- [ ] **Task 7 success criteria**
  - [ ] `AgentConfig.cwd` is populated from `context.cwd` on every agent dispatch
  - [ ] `AgentConfig.allowed_tools` carries the declared names exactly
  - [ ] No tool-name registry lookup exists in `actions/dispatch.py`

## Task 8: Test the threading

- [ ] **8.1** Add tests to `tests/pipeline/actions/test_dispatch.py`
  - [ ] `test_dispatch_passes_allowed_tools_to_agent_config` — assert on the constructed
    `AgentConfig`, not merely that a mock was called
  - [ ] `test_dispatch_passes_cwd_to_agent_config` — assert `AgentConfig.cwd == context.cwd`
  - [ ] `test_dispatch_passes_cwd_even_without_tools` — the D2 regression guard
  - [ ] `test_dispatch_without_allowed_tools_leaves_field_none`
- [ ] **8.2** Add the list-integrity test
  - [ ] `test_allowed_tools_list_survives_param_resolution` — assert the value arriving at
    `AgentConfig` is a `list[str]` with the exact declared names
  - [ ] This covers the design's one named risk: `allowed_tools` is the first list-valued step
    config field to travel the param-placeholder resolution path, which is exercised on scalars
    everywhere else
- [ ] **8.3** Add the malformed-value test
  - [ ] Assert a non-list value in `context.params` raises rather than silently dropping tools
  - [ ] Effort: 2/5

- [ ] **Task 8 success criteria**
  - [ ] `uv run pytest tests/pipeline/actions/ -q` green
  - [ ] Every assertion inspects the resulting `AgentConfig` field values

## Task 9: End-to-end integration test with a mocked endpoint

- [ ] **9.1** Create `tests/pipeline/test_dispatch_tools.py`
  - [ ] Stand up a mocked OpenAI-compatible endpoint returning two turns: first a `write_file`
    tool call, then a final assistant message with text and no `tool_calls`
  - [ ] Follow the mocking approach already used in `tests/providers/openai/` for the 262 loop
    tests rather than inventing a second pattern
  - [ ] Run a one-step pipeline with `allowed_tools: [write_file]` in a `tmp_path` cwd
- [ ] **9.2** Assert on real effects
  - [ ] The file **exists on disk** at the expected path with the expected content — this is
    the assertion that would have caught the silent-no-op class of bug (issue #15)
  - [ ] The dispatch `ActionResult.success` is `True` and `outputs["response"]` carries the
    final turn's text, not the tool-call turn
  - [ ] Effort: 3/5

- [ ] **Task 9 success criteria**
  - [ ] Test passes and fails loudly if `cwd` threading is reverted
  - [ ] No network access; no real model call

## Task 10: Ship `allowed_tools` in `test-p4.yaml`

- [ ] **10.1** Edit `src/squadron/data/pipelines/test-p4.yaml`
  - [ ] Add `allowed_tools: [read_file, write_file]` to the `design` step, as a sibling of
    `phase`, `model`, and `review`
  - [ ] Do **not** add `bash` (design D4) — the demo proves file writing, and `bash` is
    unrestricted beyond CWD scoping, widening the blast radius of a shipped pipeline with no
    added demonstrated capability
  - [ ] Leave the `summary` step untouched — the summary path is slice 265
- [ ] **10.2** Verify the shipped pipeline still validates
  - [ ] `uv run sq run test-p4 --slice 263 --dry-run` exits zero
  - [ ] Effort: 1/5

- [ ] **Task 10 success criteria**
  - [ ] `test-p4.yaml` declares exactly `read_file` and `write_file` on the design step
  - [ ] Dry-run validation passes

## Task 11: Manual end-to-end verification

- [ ] **11.1** Negative case first — prove the validation gate
  - [ ] Temporarily set a bad tool name in a scratch pipeline and confirm the run fails before
    any model call, with an error naming the bad tool and listing registered ones
- [ ] **11.2** Positive case — real non-SDK model
  - [ ] `uv run sq run test-p4 --slice <an unstarted slice> -v`
  - [ ] Confirm the slice-design file **exists on disk** afterward and the review step finds it
    as input rather than reporting a missing artifact
- [ ] **11.3** Contrast case — prove the field is what changed
  - [ ] Remove the `allowed_tools` line, re-run, and confirm the model produces prose and no
    file appears. That contrast is the slice's whole point and is the evidence for the
    verification walkthrough
  - [ ] Record the outcome in the slice design's Verification Walkthrough section
  - [ ] Effort: 2/5

- [ ] **Task 11 success criteria**
  - [ ] All three cases behave as described, with the observed results recorded

## Task 12: Quality gates and close-out

- [ ] **12.1** Run the full gate set
  - [ ] `uv run ruff format .`
  - [ ] `uv run ruff check .`
  - [ ] `uv run pyright` — must be 0 errors. Use `uv run`, not `.venv/bin/pyright`: the local
    venv cannot resolve `openai` and reports large phantom counts
  - [ ] `uv run pytest -q` — full suite. Takes ~7 minutes and includes metrology tests that
    perform real `time.sleep`; this is expected, not a hang. Do not kill it
- [ ] **12.2** Confirm the diff's shape matches the design
  - [ ] Exactly five source files changed: `steps/utils.py`, `steps/dispatch.py`,
    `steps/phase.py`, `actions/dispatch.py`, `data/pipelines/test-p4.yaml`
  - [ ] `schema.py`, `loader.py`, `executor.py`, `core/models.py`, the agent, and the provider
    are unmodified. Any change there means the design was departed from — stop and reconcile
    before committing
- [ ] **12.3** Close out
  - [ ] `ruff format .` immediately before committing
  - [ ] Mark this task file and the slice design complete; check off slice 263 in
    `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
  - [ ] Write the DEVLOG entry
  - [ ] Merge the slice branch to `main` (integration branch is unset)
  - [ ] Effort: 1/5

- [ ] **Task 12 success criteria**
  - [ ] All four gates clean
  - [ ] Diff touches only the five named source files plus tests
