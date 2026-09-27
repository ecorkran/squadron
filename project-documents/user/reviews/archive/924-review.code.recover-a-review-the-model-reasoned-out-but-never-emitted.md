---
docType: review
layer: project
reviewType: code
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: b62dca2c411af4a166c990e59dea96345e167603
toolsSuppressedReason: model-capability
diffTruncated: false
runId: run-20260927-review-ed6b7fd5
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "Shipped-models budget test asserts on a file not changed in this diff"
    location: "tests/models/test_aliases.py#test_shipped_models_toml_loads_with_budgets"
  - id: F002
    severity: concern
    category: style
    summary: "Multiple new lines appear to exceed the project's 88-character limit"
    location: "src/squadron/pipeline/resolver.py:73"
  - id: F003
    severity: note
    category: documentation
    summary: "`ReviewResult.max_output_tokens` is documented as \"sent\" but is stamped even when the provider drops it"
    location: "src/squadron/review/review_client.py#run_review_with_profile"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated, observable, and asserted in tests"
    location: "src/squadron/review/review_client.py#_collect_review"
  - id: F005
    severity: pass
    category: validation
    summary: "Alias validation and single-reader design are clean and well tested"
    location: "src/squadron/models/aliases.py:73-84"
---

# Review: code — slice 924

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [CONCERN] Shipped-models budget test asserts on a file not changed in this diff

`test_shipped_models_toml_loads_with_budgets` ("Slice 924 B5") asserts `any(budget is not None ...)` over `load_builtin_aliases()` — i.e., it requires the packaged built-in `models.toml` to actually contain `max_output_tokens` keys. The diff range under review contains no change to any `models.toml`, and prior to this diff `_extract_metadata` ignored the key entirely, so a pre-existing key in the file would have been inert (unusual). If the built-in file does not already carry OpenRouter budgets, this test fails. I could not inspect the packaged file, so this is a verify-before-merge item: either the data change needs to land with this slice, or the test should be adjusted. Note `test_resolve_full_has_no_budget_for_an_alias_without_one` (tests/pipeline/test_resolver.py) pins the complementary expectation for `opus`, so the pair only passes if the built-in file has budgets on *some* aliases but not `opus`.

### [CONCERN] Multiple new lines appear to exceed the project's 88-character limit

The Python rules mandate 88-char lines enforced via ruff (`E` selection includes E501) and the formatter. Counting characters in the added lines, these exceed 88:
- `src/squadron/pipeline/resolver.py:73` — the new `return ResolvedModel(...)` line, ~102 chars
- `src/squadron/models/aliases.py:76` — the `if isinstance(budget_val, int) and not ...` validation line, ~96 chars
- `src/squadron/review/review_client.py` (`_collect_review`) — the single-line `await collect_turn(agent, content=FINISH_REVIEW_PROMPT, ...)`, ~97 chars
- `src/squadron/review/turn_capture.py:51` — the `describe_budget` docstring line, ~100 chars
- Tests: `tests/models/test_aliases.py` (`write_text` helper line ~96), `tests/providers/codex/test_agent.py` and `tests/providers/sdk/test_provider.py` (`hits = [r for r in ...]` ~102), `tests/review/test_review_client.py` (`test_skip_warning_names_the_sent_budget` def ~103 and a `_scripted_provider` call line ~98), `tests/providers/openai/test_agentic_loop.py` (def line ~100, `_async_stream(tool_chunk(...))` ~93), `tests/providers/openai/test_agent.py` (def line ~95), `tests/review/test_persistence.py` (an assert ~97)

The long call sites are ones `ruff format` would normally rewrap, which suggests formatting wasn't run — or the repo's actual `line-length` differs from the stated 88 (I could not inspect `pyproject.toml` to confirm). Please run `ruff format --check` / `ruff check` and either reformat or confirm the configured limit.

### [NOTE] `ReviewResult.max_output_tokens` is documented as "sent" but is stamped even when the provider drops it

The field's comment in `src/squadron/review/models.py` says "the per-request output budget **sent**", and `describe_budget`'s docstring frames "backend default" as "when none was sent". But `result.max_output_tokens = max_output_tokens` is stamped unconditionally, while the SDK and Codex providers explicitly do not apply it (they only log the new warning). For a budgeted Claude alias, the durable artifact will read "Output budget: 4096 tokens" although nothing was sent on the wire, and a `max_tokens` stop on that run would be attributed to a budget that was never transmitted. The WARNING at agent creation mitigates observability, but the artifact itself misstates the wire reality. Consider either clearing the field for providers that can't apply it, or adjusting the docstring/wording to "configured budget".

### [PASS] Failure modes are enumerated, observable, and asserted in tests

Every new failure path has an observable signal and a test asserting it: budget-exhausted mid-task skip (`_log_budget_skip` WARNING + digest skip line + `output_budget_exhausted` on the result), empty final turn (typed `EmptyFinalTurnError` carrying `finish_reason`/`reasoning_chars`/tool-call counts, folded into capture via `fold_empty_turn` with summed telemetry verified in `test_empty_first_turn_is_recovered_with_summed_telemetry`), and unsupported budgets (one WARNING per agent creation, asserted in both Codex and SDK provider tests). The re-raise-on-spent-budget and propagate-empty-recovery-turn paths are also covered. This satisfies the failure-mode-enumeration rule well.

### [PASS] Alias validation and single-reader design are clean and well tested

`_extract_metadata` correctly rejects `bool` (int subclass), floats, strings, and values < 1 with a WARNING naming the alias, file, and offending value — no silent fallback, per project conventions. `model_max_output_tokens` is documented as the single reader, and the parametrized test (`"0"`, `"-1"`, `'"4096"'`, `"4096.0"`, `"true"`) covers each rejection class. Centralizing `OUTPUT_BUDGET_STOP_REASONS` as the one place those strings live in `src/` follows the project's "define comparison values once" rule.

### Run Digest

- Response length: 5862 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- Reasoning characters: 109504
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
