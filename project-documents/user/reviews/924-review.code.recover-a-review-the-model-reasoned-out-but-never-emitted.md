---
docType: review
layer: project
reviewType: code
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
targetKind: slice
rulesSource: project
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
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: concern
    category: observability
    summary: "Artifact records the budget as \"sent\" even for providers that cannot apply it"
    location: "src/squadron/review/review_client.py#run_review_with_profile"
  - id: F002
    severity: note
    category: style
    summary: "Several new lines exceed the project's 88-character limit"
    location: "src/squadron/pipeline/resolver.py:73"
  - id: F003
    severity: note
    category: testing
    summary: "Test classes alias another class's private helpers"
    location: "tests/review/test_review_client.py#TestEmptyFinalTurnRecovery"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure-mode enumeration and single-sourced comparison values are well handled"
    location: "src/squadron/review/turn_capture.py"
---

# Review: code — slice 924

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [CONCERN] Artifact records the budget as "sent" even for providers that cannot apply it

`run_review_with_profile` stamps `result.max_output_tokens = max_output_tokens` unconditionally, and the digest (`src/squadron/review/persistence.py`, "- Output budget: N tokens") plus `ReviewResult.to_dict()` then report that value as fact. But for the SDK and Codex providers the budget is never sent — `src/squadron/providers/sdk/provider.py` and `src/squadron/providers/codex/agent.py` only log a warning that "the backend default applies". The field's own comment in `src/squadron/review/models.py` ("the per-request output budget sent. None means no budget was sent") is therefore false for those two providers: a configured budget produces an artifact claiming "Output budget: 4096 tokens" while the backend ran uncapped. Someone debugging a truncated SDK/Codex review from the artifact alone would conclude the wrong thing — the warning only lives in logs. Consider either leaving the field `None` when the active provider cannot apply a budget, or recording the distinction (e.g., a `budget_applied` flag or digest wording such as "configured (not supported by provider)").

### [NOTE] Several new lines exceed the project's 88-character limit

New lines visibly over 88 chars: the `_resolved` return in `src/squadron/pipeline/resolver.py:73` (~102 chars); the unwrapped `await collect_turn(agent, content=FINISH_REVIEW_PROMPT, recipient=recipient, capture=capture)` in `src/squadron/review/review_client.py#_collect_review` (~97 — the pre-change code wrapped this same call); the `describe_budget` docstring in `src/squadron/review/turn_capture.py` (~101); and several test lines (e.g., `tests/review/test_review_client.py` `test_skip_warning_names_the_sent_budget` def ~104, `tests/providers/openai/test_agentic_loop.py` `test_loop_error_is_typed_and_carries_the_turn_telemetry` def ~101, the `hits = [r for r in caplog.records ...]` lines in the codex/sdk provider tests ~103). The pre-existing 104-char `_append_history(...)` line this diff *removes* from `openai/agent.py` suggests E501 is not mechanically enforced here, so treat as a convention nudge rather than a lint failure — but if ruff `E` is expected to gate, these will trip it.

### [NOTE] Test classes alias another class's private helpers

`TestEmptyFinalTurnRecovery` and `TestOutputBudgetThreading` reuse `TestRecoveryTurn._scripted_provider` / `._run` via class-attribute assignment with `pyright: ignore[reportPrivateUsage]` suppressions. It works (the function rebinds as a method of the new class), but it couples the classes and needs private-access suppressions under strict pyright. Promoting `_scripted_provider`/`_run` to module-level helpers or `conftest.py` fixtures would match the project's shared-fixture convention and drop the ignores.

### [PASS] Failure-mode enumeration and single-sourced comparison values are well handled

The new failure modes are each observable and tested: budget-exhausted skips log at WARNING with stop reason and budget (`_log_budget_skip`), providers that can't apply a budget warn rather than silently drop, and the typed `EmptyFinalTurnError` carries turn telemetry that `fold_empty_turn` sums into the capture (verified by `test_empty_first_turn_is_recovered_with_summed_telemetry`). The stop-reason strings live in exactly one place (`OUTPUT_BUDGET_STOP_REASONS`) per the project's no-scattered-comparison-values rule, the TOML `true`-reads-as-1 trap is explicitly guarded and parametrized in tests, and agent shutdown is guaranteed via `finally` on every raise path (`test_empty_recovery_turn_propagates` asserts it).

### Run Digest

- Response length: 4722 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- Reasoning characters: 76949
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
