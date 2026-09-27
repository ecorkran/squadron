---
docType: tasks
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
project: squadron
lld: user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [918, 919, 927]
projectState: Design complete with Part C added (f3856b7e). Recovery turn for a mid-task ending already shipped in 7dbd1e18. Slice 928's design review failed live twice on an empty final turn (glmflash), which Part C fixes.
dateCreated: 20260927
dateUpdated: 20260927
status: not_started
---

# Tasks: Recover a Review the Model Reasoned Out but Never Emitted

## Context Summary

Completes [#92](https://github.com/ecorkran/squadron/issues/92). The single recovery turn for a review that ends mid-task shipped in `7dbd1e18`. This slice adds three parts:

- **Part A:** gates can see a recovered verdict (`recoveryTurn: true`, D1). Recovery is skipped when the output budget ran out (D2). Tools stay on for the recovery turn (D3, pinned by test only).
- **Part C:** an empty final turn, which today raises `ProviderError` before recovery can run, gets the same single recovery turn (D7). This is what flagged 928 in the `slices-plan 900` run.
- **Part B:** per-alias `max_output_tokens`, sent as `max_completion_tokens` and recorded in the digest and JSON (D4, D5). The pipeline review action switches to `resolve_full()`, which also fixes the `tool_use = false` gate there (D6).

Read the design before starting. Each task cites the decision it implements, and those sections are the spec. This file does not repeat them.

Key constraints:
- Both `sq review` and the pipeline `review` action go through `run_review_with_profile` → `save_review_result`. Put every fact on `ReviewResult`, and never add a second rendering path.
- Stop-reason strings `"length"` and `"max_tokens"` appear in `src/` only inside `OUTPUT_BUDGET_STOP_REASONS`.
- The empty-final-turn error message text stays byte-identical. Tests in `test_agentic_loop.py`, `test_review_action.py`, `test_persistence.py`, and `test_cli_review.py` quote it.
- Snapshot fixtures under `tests/review/fixtures/` change only in B.14, and only by the one budget line.
- `None` means "not reported" or "not sent". Use `is None` checks and never `or 0`.
- Before every commit, run `uv run ruff format`, `uv run ruff check`, and `uv run pyright` (zero errors), plus the tests the task names.

Order is A → C → B. Part C reuses A's `budget_exhausted` and `recoveryTurn`. Part B is independent of both. Effort for the slice: 3/5.

**Next planned slice:** 928 (Codex parity for skill packs and provider access). Rerun its design review once this slice merges.

---

## Setup

- [ ] **S.1 — Create the slice branch**
  - [ ] Run `cf config get git.integration_branch`. Its value is the **target**. If it is empty, the target is `main`.
  - [ ] Run `git checkout -b 924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted <target>` with the target from the previous step. Do not hardcode `main`.
  - [ ] `uv run pytest -q` passes on the fresh branch (baseline). Record the pass count for the DEVLOG.

## Part A — Recovery provenance and the budget skip

- [ ] **A.1 — Add the budget stop-reason set and helpers** in `src/squadron/review/turn_capture.py` (D2) (Effort 1/5)
  - [ ] Add a module constant `OUTPUT_BUDGET_STOP_REASONS = frozenset({"length", "max_tokens"})`, with a one-line comment naming which provider stamps each value.
  - [ ] Add `budget_exhausted(stop_reason: str | None) -> bool`. It returns True only when `stop_reason` is in the set, and `None` returns False.
  - [ ] Add `describe_budget(max_output_tokens: int | None) -> str`, which returns `"N tokens"` or `"backend default"`. This is the only place that wording lives. The WARNING, the skip line, and the B.14 digest line all call it.
  - [ ] Success: `grep -rn '"length"\|"max_tokens"' src/` shows only this constant.

- [ ] **A.2 — Test the helpers** in `tests/review/test_turn_capture.py`. Create the file if it does not exist. (Effort 1/5)
  - [ ] `budget_exhausted` is True for `"length"` and `"max_tokens"`, and False for `"stop"`, `"end_turn"`, `"tool_calls"`, and `None`.
  - [ ] `describe_budget(32000) == "32000 tokens"` and `describe_budget(None) == "backend default"`.
  - [ ] Success: the new tests pass.

- [ ] **A.3 — Add `ReviewResult` fields** in `src/squadron/review/models.py` (A2, B3) (Effort 1/5)
  - [ ] Add `output_budget_exhausted: bool = False` and `max_output_tokens: int | None = None` next to `recovery_turn_used`. Comment the None meaning: no budget was sent.
  - [ ] Add both keys to `to_dict()`, always present (918's always-emit convention).
  - [ ] Success: pyright is clean and `tests/review/test_models.py` passes, with any exact-key-set assertions updated for the two keys.

- [ ] **A.4 — Test the `to_dict` keys** in `tests/review/test_models.py` (Effort 1/5)
  - [ ] The default result emits `max_output_tokens: None` and `output_budget_exhausted: False`.
  - [ ] Set values round-trip.

- [ ] **A.5 — Skip recovery on a spent budget** in `src/squadron/review/review_client.py` (D2) (Effort 2/5)
  - [ ] In the `ended_mid_task(result)` branch (currently around line 254), check `budget_exhausted(capture.stop_reason)` first. If it is True, make no second `collect_turn` call. Log one WARNING naming the template, the model, the stop reason, and `describe_budget(<budget>)`. Do not log the existing "asking once more" line.
  - [ ] `<budget>` is a local that is `None` until B.10 adds the parameter. Leave a clear name such as `max_output_tokens = None` so B.10 only replaces its source.
  - [ ] After the `finally`, set `result.output_budget_exhausted = budget_exhausted(capture.stop_reason)` from the **final** stop reason on every run, not only on the skip path.
  - [ ] Success: stop reasons `stop`, `end_turn`, and `None` still take exactly one recovery turn, as shipped.

- [ ] **A.6 — Test the skip and pin D3** in `tests/review/test_review_client.py` (Effort 2/5)
  - [ ] Use the file's existing fake agent. First turn ends mid-task with stop reason `length`: exactly one `handle_message` call, a WARNING containing `stop reason: length` and `backend default`, `recovery_turn_used` False, `output_budget_exhausted` True, verdict UNKNOWN.
  - [ ] Same for `max_tokens`.
  - [ ] Stop reason `None` (Codex): two calls and `recovery_turn_used` True.
  - [ ] Recovery turn itself ends on `length`: `output_budget_exhausted` True and `recovery_turn_used` True.
  - [ ] **D3:** the second `handle_message` runs on the same agent object, and the agent's tool set is unchanged between the calls.
  - [ ] Success: all pass, and the existing recovery tests pass unchanged.

- [ ] **A.7 — Render `recoveryTurn` and the skip line** in `src/squadron/review/persistence.py` (D1, D2) (Effort 1/5)
  - [ ] Frontmatter: emit `recoveryTurn: true` on the line right after `verdictSource` (around line 390), only when `result.recovery_turn_used`. Follow the pattern `requestedModel` and `diffTruncated` use.
  - [ ] Run Digest (`_run_digest_lines`, next to the existing `Recovery turn used` line): when `output_budget_exhausted` is True **and** `recovery_turn_used` is False, append `- Recovery turn: skipped — output budget exhausted (stop reason: <reason>; budget: <describe_budget>)`.
  - [ ] Success: `test_clean_pass_artifact_is_byte_identical_to_the_pre_change_snapshot` passes unchanged.

- [ ] **A.8 — Test the rendering** in `tests/review/test_persistence.py` (Effort 1/5)
  - [ ] `recoveryTurn: true` is present and directly follows `verdictSource` when recovery was used, and absent otherwise.
  - [ ] The skip line is present with stop reason and `backend default` when skipped, and absent on a normal run.
  - [ ] Write a recovered artifact to a temp directory and run `cf validate frontmatter` on it. It passes (D1: cf tolerates unknown keys).
  - [ ] Success: `uv run pytest tests/review -q` passes.

- [ ] **A.9 — Commit Part A**
  - [ ] `feat(review): flag recovered verdicts and skip recovery on a spent budget`

## Part C — Recover an empty final turn

- [ ] **C.1 — Add `EmptyFinalTurnError`** in `src/squadron/providers/errors.py` (D7) (Effort 1/5)
  - [ ] Subclass `ProviderError`. The constructor takes the message plus keyword-only `finish_reason: str | None`, `reasoning_chars: int`, `tool_calls_made: int`, and `failed_tool_calls: int`. Pass `tool_calls_made` to the base and store the rest as attributes.
  - [ ] Add a docstring of one or two lines: the model ended its turn with no text and no tool calls, and the telemetry rides the error because `collect_turn` cannot fold it after a raise.

- [ ] **C.2 — Raise it and drop the empty history entry** in `src/squadron/providers/openai/agent.py` (D7) (Effort 2/5)
  - [ ] `_require_final_content` raises `EmptyFinalTurnError` with the **same message text** and the same WARNING. It gains a `failed_tool_calls` keyword, and its callers pass it (the no-tools path passes 0).
  - [ ] At both call sites (the no-tools branch near line 236 and `_run_agentic_loop` near line 465), call `_append_history` only when `not turn.is_empty()`. Leave `_record_answering_model` where it is.
  - [ ] Success: the existing `pytest.raises(ProviderError, match="empty final turn")` tests pass unchanged.

- [ ] **C.3 — Test the agent change** in `tests/providers/openai/test_agentic_loop.py` (Effort 1/5)
  - [ ] Extend the empty-final-turn test (around line 635): the raised error is an `EmptyFinalTurnError`, and its `finish_reason`, `reasoning_chars`, `tool_calls_made`, and `failed_tool_calls` match the stream.
  - [ ] Afterward, the agent's history contains no `{"role": "assistant", "content": ""}` entry. Cover the agentic-loop path after at least one tool call, and the no-tools path.
  - [ ] A non-empty final turn is still appended to history exactly as before.
  - [ ] Success: `uv run pytest tests/providers/openai -q` passes.

- [ ] **C.4 — Recover in `run_review_with_profile`** in `src/squadron/review/review_client.py` (D7) (Effort 2/5)
  - [ ] Wrap only the **first** `collect_turn` in `except EmptyFinalTurnError`. In the handler, fold the error into `capture`: `stop_reason = finish_reason`, and add `reasoning_chars`, `tool_calls_made`, and `failed_tool_calls` using the same None-aware summing `collect_turn` uses (`_add`). Remember the error.
  - [ ] Restructure the branch to follow the design's Recovery decision diagram. An empty first turn counts as ended mid-task. If `budget_exhausted` is True, log the A.5 WARNING and re-raise the remembered error. Otherwise log `… returned an empty final turn (stop reason: …, reasoning chars: …); asking once more for the review` and run the shipped `FINISH_REVIEW_PROMPT` turn with `recovery_turn_used = True`.
  - [ ] Do not catch the error on the recovery turn. A second empty turn propagates.
  - [ ] The rest of the function runs as today: parse after recovery, `finally: agent.shutdown()`, and telemetry copy-out.
  - [ ] Success: pyright clean. No `except ProviderError` is added anywhere.

- [ ] **C.5 — Test empty-turn recovery** in `tests/review/test_review_client.py` (Effort 2/5)
  - [ ] Fake agent whose first `handle_message` raises `EmptyFinalTurnError(finish_reason="stop", reasoning_chars=1022, tool_calls_made=3, failed_tool_calls=0)` and whose second yields a valid review: verdict parsed, `recovery_turn_used` True, `stop_reason` from turn 2, `reasoning_chars` and `tool_calls_made` include turn 1's values, and the WARNING is logged.
  - [ ] First raise with `finish_reason="length"`: the same error instance propagates and there is exactly one `handle_message` call.
  - [ ] Both turns raise: the **second** error propagates.
  - [ ] Success: `uv run pytest tests/review tests/pipeline/actions/test_review_action.py tests/review/test_cli_review.py -q` passes. The existing failure-artifact tests still see the same message.

- [ ] **C.6 — Commit Part C**
  - [ ] `fix(review): recover a review whose final turn came back empty`

## Part B — Per-model output budget

- [ ] **B.1 — Add `AgentConfig.max_output_tokens`** in `src/squadron/core/models.py` (Effort 1/5)
  - [ ] `max_output_tokens: int | None = None`, with a one-line comment: `None` sends no budget (D4).

- [ ] **B.2 — Send the budget from the OpenAI-compatible agent** in `src/squadron/providers/openai/agent.py` `_stream_turn` (D5) (Effort 1/5)
  - [ ] Pass `max_completion_tokens=self._config.max_output_tokens` if it is not None, and `omit` otherwise. This follows the existing `tools=... else omit` pattern at the `chat.completions.create` call. If the agent does not keep its config, store the value in `__init__`.
  - [ ] Never send `max_tokens`.

- [ ] **B.3 — Test the request parameter** in `tests/providers/openai/test_agent.py` (Effort 1/5)
  - [ ] With a budget of 4096, every `create` call gets `max_completion_tokens=4096`, including each turn of a two-iteration agentic loop.
  - [ ] Without a budget, the call gets `omit` (assert `is omit`).

- [ ] **B.4 — Warn in the SDK and Codex agents** in `src/squadron/providers/sdk/agent.py` and `src/squadron/providers/codex/agent.py` (B2) (Effort 1/5)
  - [ ] In each `__init__`, if `config.max_output_tokens is not None`, log one WARNING: `<provider> agent cannot apply max_output_tokens=<N>; the backend default applies`. This is a separate edit for each file.

- [ ] **B.5 — Test the warnings** in the existing SDK and Codex agent test files (Effort 1/5)
  - [ ] With a budget set, each constructor logs the WARNING once. Without one, it logs nothing.
  - [ ] Success: `uv run pytest tests/providers -q` passes.

- [ ] **B.6 — Commit** `feat(providers): send a per-request output budget when configured`

- [ ] **B.7 — Alias field, validation, and reader** in `src/squadron/models/aliases.py` (B1) (Effort 2/5)
  - [ ] Add `max_output_tokens: int` to the alias TypedDict next to `tool_use`. Parse it in the loader next to `tool_use` (around line 67).
  - [ ] Reject a non-int, a bool, or a value below 1 with the same error shape the loader uses for its other invalid fields. `True` is an `int` in Python, so exclude bool explicitly.
  - [ ] Add `model_max_output_tokens(name: str | None) -> int | None` next to `model_allows_tools`. Unknown name, `None`, and unset all return `None`. It is the only reader of the field.
  - [ ] Document the field in the `data/models.toml` header comment next to `tool_use`.

- [ ] **B.8 — Test the alias field** in `tests/models/test_aliases.py` (Effort 1/5)
  - [ ] A valid value is read back. Values `0`, `-1`, `"4096"`, `4096.0`, and `true` are each rejected. Unknown alias, `None`, and unset return `None`.

- [ ] **B.9 — Carry the budget on `ResolvedModel`** in `src/squadron/pipeline/resolver.py` (Effort 1/5)
  - [ ] Add `max_output_tokens: int | None = None` after `allows_tools`. `_resolved()` (around line 60) fills it from `model_max_output_tokens(alias)`.
  - [ ] The `resolve()` tuple contract is unchanged.
  - [ ] Test in the resolver's existing test file: `resolve_full` on an alias with a budget returns it, and on one without returns `None`.

- [ ] **B.10 — Thread the budget through `run_review_with_profile`** in `src/squadron/review/review_client.py` (Effort 1/5)
  - [ ] Add the keyword parameter `max_output_tokens: int | None = None`. Set it on the `AgentConfig`, replace A.5's local with it, and set `result.max_output_tokens`.
  - [ ] Test in `test_review_client.py`: the fake provider receives an `AgentConfig` with the budget, and the result carries it. The A.6 skip WARNING now shows `N tokens` when a budget is passed.

- [ ] **B.11 — CLI threading** in `src/squadron/cli/commands/review.py` (Effort 1/5)
  - [ ] Next to `allows_tools = model_allows_tools(...)` (around line 711), read `model_max_output_tokens` from the same alias name. Pass it through `_execute_review` to `run_review_with_profile`, following how `model_allows_tools` flows.
  - [ ] Test in `tests/review/test_cli_review.py`: an alias with a budget reaches `run_review_with_profile` (patch it and assert the keyword).

- [ ] **B.12 — Pipeline action via `resolve_full`** in `src/squadron/pipeline/actions/review.py` (D6) (Effort 2/5)
  - [ ] Replace both `context.resolver.resolve(...)` calls (around lines 176 and 180, including the `ModelResolutionError` fallback) with `resolve_full(...)`. Take `model_id` and `profile` from the result.
  - [ ] Pass `model_allows_tools=resolved.allows_tools` and `max_output_tokens=resolved.max_output_tokens` to `run_review_with_profile`.
  - [ ] Profile precedence (explicit param → alias → SDK) is unchanged.

- [ ] **B.13 — Test pipeline parity** in `tests/pipeline/actions/test_review_action.py` (Effort 1/5)
  - [ ] A step naming an alias with `tool_use = false` calls `run_review_with_profile` with `model_allows_tools=False`. Before this change it was never passed.
  - [ ] A step naming an alias with a budget passes `max_output_tokens`.
  - [ ] The template-model fallback path passes the same values.
  - [ ] Success: `uv run pytest tests/pipeline tests/review -q` passes.

- [ ] **B.14 — Budget digest line and fixtures** in `src/squadron/review/persistence.py` (B3) (Effort 2/5)
  - [ ] In `_run_digest_lines`, add `- Output budget: <describe_budget(result.max_output_tokens)>` on the line right after `- Stop reason:`. It is always present.
  - [ ] Regenerate every fixture under `tests/review/fixtures/` that contains `Run Digest` (seven files at planning time: `clean_pass_artifact.md` and the six `383-*` files). For each one, `git diff` must show exactly one added line, `- Output budget: backend default`, and nothing else.
  - [ ] Add a note to `tests/review/fixtures/README.md` recording this as a sanctioned regeneration by slice 924 B3.
  - [ ] Test in `test_persistence.py`: the line shows `N tokens` or `backend default`.
  - [ ] Success: `uv run pytest -q` passes in full.

- [ ] **B.15 — Commit** `feat(review): per-alias output budget, recorded in the digest; pipeline reviews resolve the alias`

- [ ] **B.16 — Set built-in budget values** in `src/squadron/data/models.toml` (B5) (Effort 1/5)
  - [ ] List every alias with `profile = "openrouter"` in the file.
  - [ ] Fetch `https://openrouter.ai/api/v1/models` (public, no auth). For each alias's `model`, read `top_provider.max_completion_tokens`. Where it is an integer, set `max_output_tokens` to it. Where it is null or the model is missing from the listing, leave the field unset. Do not invent a value.
  - [ ] Record the listing date in the header comment next to the field's documentation.
  - [ ] Test: loading the shipped `models.toml` succeeds, and at least one built-in alias returns a non-None `model_max_output_tokens`.
  - [ ] Commit: `feat(models): set output budgets on built-in OpenRouter aliases`

## Finish

- [ ] **F.1 — File follow-up issues** (Effort 1/5)
  - [ ] In context-forge: the review gate may read `recoveryTurn: true` (D1). Follow the context-forge#89 pattern.
  - [ ] In squadron: pass `ResolvedModel.max_output_tokens` from the dispatch and summary actions.
  - [ ] Link both issue numbers from the 924 entry in `900-slices.maintenance-and-refactoring.md`.

- [ ] **F.2 — Validation pass**
  - [ ] `uv run ruff format`, `uv run ruff check`, and `uv run pyright` (zero errors) are clean. `uv run pytest -q` is green, and the pass count is recorded.
  - [ ] `grep -rn '"length"\|"max_tokens"' src/` shows only `OUTPUT_BUDGET_STOP_REASONS`.

- [ ] **F.3 — Verification walkthrough** (design §Verification Walkthrough, steps 1–6)
  - [ ] Run steps 1–3 and 5 live. Step 4 is covered by the unit test. For step 6, run `sq review slice 928 --model glmflash -v` and record whether the empty-turn WARNING appeared and what the artifact shows.
  - [ ] Step 5 uses `sq run`, which refuses to run inside Claude Code (issue #144). Hand that command to the Project Manager and record its output. Do the same for any other step that cannot run in-session.
  - [ ] Update the design's walkthrough with what actually happened.

- [ ] **F.4 — CHANGELOG, DEVLOG, status**
  - [ ] CHANGELOG: short user-facing bullets. Recovered reviews are flagged. An empty final reply now gets a second chance. There are per-model output budgets. The digest has a new `Output budget` line.
  - [ ] DEVLOG: session state summary, including the baseline and final test counts.
  - [ ] Set `status: complete` in this file and in the slice design. Check the 924 entry in the slice plan.
  - [ ] Commit: `docs: complete slice 924`

- [ ] **F.5 — Merge**
  - [ ] Re-read the target with `cf config get git.integration_branch`. Then `git checkout <target>` and `git merge 924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted`. If either command fails, stop and ask the Project Manager.
