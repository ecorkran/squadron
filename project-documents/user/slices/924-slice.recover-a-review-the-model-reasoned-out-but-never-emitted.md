---
docType: slice-design
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [918, 919, 927]
interfaces: []
dateCreated: 20260927
dateUpdated: 20260927
status: complete
---

# Slice Design: Recover a Review the Model Reasoned Out but Never Emitted

## Overview

Issue [#92](https://github.com/ecorkran/squadron/issues/92): a complete, well-grounded review reaches disk as `verdict: UNKNOWN` with zero findings, because the model finished its analysis in prose and stopped before writing the `## Summary` / findings block.

**The plan entry is partly out of date. This design supersedes it where they differ.** It was verified against `main` at `90d96cec` on 20260927.

- **Part A's core already shipped.** Commit `7dbd1e18` (20260924, "fix: give a review that ends mid-task one follow-up turn") closed #92. Two new captures (minimax-m3 on the 925 code review and on PR 116) settled the mechanism the plan entry left open. In both, the model stopped cleanly partway through the work, writing its own tool-call markup or a command it meant to run as plain text. The loop treated that turn as final. The commit added:
  - `ended_mid_task()` and `FINISH_REVIEW_PROMPT` in [turn_capture.py](../../../src/squadron/review/turn_capture.py);
  - one bounded follow-up turn in [review_client.py:254](../../../src/squadron/review/review_client.py#L254);
  - telemetry that adds up across both turns;
  - `ReviewResult.recovery_turn_used`, rendered in the Run Digest, the report header, and `--output json`.

  Because both entry points call `run_review_with_profile` and save through `save_review_result`, the CLI and the pipeline review action already behave the same.
- **What Part A still owes** is the plan entry's remaining questions:
  - which provenance a recovered verdict carries, so a gate can see it;
  - what happens when the stop reason is an exhausted output budget, where the shipped code asks again regardless;
  - whether the recovery turn keeps its tools. The shipped code keeps them. The plan entry leaned the other way, and this design records why the evidence favors keeping them.
- **Part B is unchanged and still open.** No request under `providers/openai/` sets an output budget.
- **Part C (added 20260927) covers a second shape of the same bug that the shipped recovery never sees.** The model reasons, then ends its final turn with no text and no tool calls. The OpenAI-compatible agent refuses that turn in `_require_final_content` ([agent.py:67](../../../src/squadron/providers/openai/agent.py#L67)) by raising `ProviderError`. The exception leaves `run_review_with_profile` before the `ended_mid_task` check runs, so the review becomes a failure artifact. Live capture: slice 928's design review under glmflash failed this way twice in a row (`finish_reason='stop', reasoning_chars=1022`), which flagged 928 in the `slices-plan 900` batch run.

## Value

- **Gates can tell a second-ask verdict apart.** A verdict the model gave only after squadron prompted it again is weaker evidence than one it gave unprompted. Today that difference is visible only in the report body and JSON. Context Forge's review gate and the Amoeba orchestrator read frontmatter, so to them a recovered PASS looks the same as a clean one.
- **No wasted turn on a spent budget.** When the model ran out of output budget, asking again repeats the failure and spends another turn. The artifact should name the budget as the cause.
- **Output budgets become explicit.** The budget moves from an unknown backend default to a per-model value squadron sends and records. The #84 follow-up has waited on this, and without it the digest's `Stop reason: length` has no number to point at.
- **The `tool_use = false` gate works in pipeline reviews.** It never has. The budget has to take the same route, and fixing that route fixes the gate too (see D6).
- **An empty final turn gets the same one follow-up turn as a mid-task ending.** Today it stops a batch item outright. After this slice it is recovered, and flagged `recoveryTurn: true` like any other recovery.

## Technical Scope

**Included**

- **A1:** a `recoveryTurn: true` frontmatter key, emitted only when the recovery turn ran.
- **A2:** skip the recovery turn when the first turn's stop reason says the output budget ran out, and disclose the skip.
- **A3:** keep tools enabled on the recovery turn. This is recorded as a decision and pinned by a test; the code does not change.
- **B1:** an optional per-alias `max_output_tokens` in `models.toml`, carried alias → resolved model → `AgentConfig` → request.
- **B2:** the OpenAI-compatible agent sends `max_completion_tokens` only when a budget is set. Agents that cannot apply a budget log a warning instead of ignoring it.
- **B3:** the budget is recorded in the Run Digest and JSON.
- **B4:** the pipeline review action resolves through `resolve_full()`. This carries the budget and fixes the `tool_use` gate as a side effect.
- **B5:** set budget values on the built-in OpenRouter reasoning-model aliases.
- **C1:** `EmptyFinalTurnError(ProviderError)`, raised by `_require_final_content` in place of the bare `ProviderError`. It carries the turn's `finish_reason`, `reasoning_chars`, `tool_calls_made`, and `failed_tool_calls`.
- **C2:** the OpenAI-compatible agent does not append an empty turn to its history.
- **C3:** `run_review_with_profile` catches `EmptyFinalTurnError` on the first turn, folds its telemetry into the capture, and runs the shipped recovery turn. The D2 budget skip applies to it too.

**Excluded**

- Prompt changes aimed at adherence. The captures point to a turn boundary, not the template.
- Inferring a verdict from prose. A regex for "Verdict: PASS" in free text reopens the #91 surface where incidental matches get read as verdicts.
- A global or provider-level default budget. See D4.
- Budgets for the Claude SDK and Codex agents. They get a warning, not an implementation.
- `metrology/audit.py` and `review/addressed/judge.py`. They call `run_review_with_profile` without a resolved alias, and they keep today's behavior.
- A second recovery attempt. One bounded turn remains the contract.
- Recovering an empty final turn in dispatch and summary actions. They receive the new subclass as a `ProviderError` and behave exactly as today.

## Dependencies

### Prerequisites

- **918:** the Run Digest's `Stop reason` and `Reasoning characters` fields, and `TurnCapture.stop_reason`.
- **919:** the `VerdictSource` contract. Its D7 is the ground for A1.
- **927:** the frontmatter convention that an optional key appears only when its condition holds (`diffTruncated`, `requestedModel`). `recoveryTurn` follows it.
- **`7dbd1e18`:** the shipped recovery turn this slice completes.

### Interfaces Required

- Stop-reason strings as providers stamp them today:
  - the OpenAI-compatible agent passes `finish_reason` through as-is (`"length"` on a spent budget);
  - the SDK agent passes Anthropic's `stop_reason` (`"max_tokens"`);
  - Codex stamps nothing, so its stop reason is `None`.
- OpenRouter's chat request schema: `max_completion_tokens` is current and `max_tokens` is deprecated. Reasoning tokens count against both, so a reasoning model can use up the whole budget before writing any answer text. This comes from OpenRouter's API reference, checked via context7 on 20260927.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `review/turn_capture.py` | Adds `OUTPUT_BUDGET_STOP_REASONS`, a closed set defined once, and `budget_exhausted(capture)`. |
| `review/review_client.py` | The recovery branch checks `budget_exhausted` before asking again. A new `max_output_tokens` parameter goes into `AgentConfig` and onto the result. |
| `review/models.py` | `ReviewResult` gains `output_budget_exhausted: bool` and `max_output_tokens: int \| None`. `to_dict()` gains both. |
| `review/persistence.py` | Frontmatter gets `recoveryTurn: true`. The Run Digest gets the budget line and the skip line. |
| `models/aliases.py` + `data/models.toml` | Optional `max_output_tokens` field, one reader `model_max_output_tokens(name)`, and values on the built-in aliases. |
| `pipeline/resolver.py` | `ResolvedModel` gains `max_output_tokens: int \| None = None`. |
| `pipeline/actions/review.py` | Switches from `resolve()` to `resolve_full()` and passes `model_allows_tools` and `max_output_tokens`. |
| `cli/commands/review.py` | Reads the budget next to `model_allows_tools` while the alias name is still known, and passes it through. |
| `core/models.py` | `AgentConfig.max_output_tokens: int \| None = None`. |
| `providers/openai/agent.py` | `_stream_turn` sends `max_completion_tokens` when set and `omit` otherwise. |
| `providers/sdk/agent.py`, `providers/codex/agent.py` | Log a WARNING when `max_output_tokens` is set, because they cannot apply it. |
| `providers/errors.py` | Adds `EmptyFinalTurnError(ProviderError)` with `finish_reason`, `reasoning_chars`, and `failed_tool_calls` attributes (`tool_calls_made` is inherited). |
| `providers/openai/agent.py` (Part C) | `_require_final_content` raises `EmptyFinalTurnError` with the same message text. Both call sites skip `_append_history` for an empty turn. |
| `review/review_client.py` (Part C) | The first `collect_turn` catches `EmptyFinalTurnError`, folds its telemetry into `TurnCapture`, and joins the recovery decision below. |

### Data Flow

**Budget:**

```
models.toml [aliases.kimi3] max_output_tokens
  → model_max_output_tokens(alias)          (CLI: next to model_allows_tools)
  → ResolvedModel.max_output_tokens         (pipeline: resolve_full)
  → run_review_with_profile(max_output_tokens=…)
  → AgentConfig.max_output_tokens
  → chat.completions.create(max_completion_tokens=… | omit)
  → ReviewResult.max_output_tokens → digest / JSON
```

**Recovery decision** (review_client, after the first turn is parsed):

```
first turn raised EmptyFinalTurnError?            (Part C)
  yes → fold error telemetry into capture; treat as "ended mid-task"
  no  → parse; ended_mid_task(result)?
          no  → done
ended mid-task (either way):
  budget_exhausted(capture)?
    yes → no second turn; WARNING log
          · from an empty turn: re-raise the EmptyFinalTurnError (failure artifact, as today)
          · from a parsed turn: result.output_budget_exhausted = True
    no  → FINISH_REVIEW_PROMPT turn (as shipped); recovery_turn_used = True
          · if the recovery turn also raises EmptyFinalTurnError, it propagates (failure artifact)
```

`output_budget_exhausted` is set from the **final** stop reason on every run, not only the skip path. A recovery turn that itself ends on `length` is reported the same way.

### State Management

No persistent state. The new facts are fields on `ReviewResult`, written once to the artifact and JSON.

## Technical Decisions

### D1 — A recovered verdict is flagged by its own key, not a new `verdictSource` value (Architect)

The plan entry asked that 919's contract "say which value that is rather than letting it read as plain `stated`." Adding a `VerdictSource.RECOVERED` would mix two separate questions.

- 919 D7 defines `verdictSource` as answering "did the model say this?"
- A recovered verdict can itself be `stated` or `derived`: the second reply may carry a `## Summary` verdict, or only findings. 927 already showed that `imposed` can apply on top of either.
- A fourth enum value would have to replace one of those, and a gate would lose the fact it was actually filtering on.

So `verdictSource` stays exactly as the parser sets it. Frontmatter gains `recoveryTurn: true` right after `verdictSource`, and only when the recovery turn ran. That follows the 927 rule, so every other artifact stays byte-for-byte unchanged.

This is gate-facing evidence, not a diagnostic, so 918 D10's "diagnostics stay out of frontmatter" does not apply. It belongs with `diffTruncated` and `requestedModel`: facts a gate may want to act on.

A context-forge issue is filed once the key ships, the same pattern 919 used with context-forge#89. It is not a precondition, since cf tolerates unknown keys (919 D6, verified).

### D2 — Skip the recovery turn when the output budget ran out (Architect)

A turn that stopped because it hit the output limit will stop again for the same reason when asked for the whole review a second time. That wastes a turn and makes the artifact look like the prompt failed rather than the budget.

- `OUTPUT_BUDGET_STOP_REASONS = frozenset({"length", "max_tokens"})` sits in `turn_capture.py`: `"length"` from OpenAI-compatible backends and `"max_tokens"` from Anthropic via the SDK. It is defined once and used by both the skip check and `output_budget_exhausted`.
- A `None` stop reason (Codex) is not budget exhaustion, so recovery goes ahead as today.
- A skip logs at WARNING and names the stop reason and the budget ("backend default" when none was sent).
- **Observable signal:** the Run Digest gets a skip line only when a skip happened: `Recovery turn: skipped — output budget exhausted (stop reason: length; budget: 32000 tokens)`. JSON carries `output_budget_exhausted: true`.

### D3 — The recovery turn keeps its tools (Architect; confirms shipped behavior)

The plan entry expected the repair turn "should need none." The evidence says otherwise:

- Both captures that led to `7dbd1e18` ended by writing tool-call markup or a pending command as text. The model had not finished reading.
- A turn without tools would force a verdict from half-read material. That produces a confident artifact built on less evidence, which is worse than an honest UNKNOWN.

`FINISH_REVIEW_PROMPT` already says "If you still need to read something, use your tools now." The turn stays capped at one `handle_message` call, and tool use inside it is bounded by the agentic loop's existing limits.

This decision adds a test that pins it: the second `handle_message` runs on the same agent with the same tool set.

### D4 — The budget is per-model alias metadata, and when it is absent no budget is sent (Architect)

Output limits vary by model and backend. A single global number would be too small for some models and rejected as too large by others (many backends return 400 when the budget exceeds the model's maximum).

`tool_use` (slice 266) already set the pattern for per-model capability data: an optional alias field in `models.toml`, read once while the alias name is still known. `max_output_tokens` follows it exactly.

**Absent means no budget is sent**, which is today's behavior. That is not a silent fallback: the digest line says `Output budget: backend default`, so the artifact names what happened. This keeps the provider free of hard-coded defaults, as the plan entry requires, and keeps unconfigured aliases (Gemini, local, user-defined) exactly as they are.

### D5 — Send `max_completion_tokens`, not `max_tokens` (Architect)

- OpenRouter's schema marks `max_tokens` deprecated in favor of `max_completion_tokens`, with the same semantics.
- OpenAI's own API rejects `max_tokens` on reasoning models.

Because D4 sends a budget only for aliases that configure one, and the built-in values in B5 go only on OpenRouter-profile aliases, no backend gets the parameter unless it has been checked to accept it. If a user sets it on a `local` or `gemini` alias whose server rejects the name, the result is an explicit `ProviderAPIError`, not silent truncation.

### D6 — The pipeline review action resolves through `resolve_full()` (Architect)

[pipeline/actions/review.py:176](../../../src/squadron/pipeline/actions/review.py#L176) calls `context.resolver.resolve()`, which returns only `(model_id, profile)`. It passes no `model_allows_tools`, so `run_review_with_profile` falls back to `model_allows_tools(model_id)`. That looks up a resolved **id** in a table keyed by **alias**, which always misses and returns `True`.

The result: a `tool_use = false` alias has never been gated in a pipeline review. `ResolvedModel`'s docstring states that an id cannot be traced back to its alias. The budget needs the alias for the same reason, so switching this call site to `resolve_full()` carries both. That closes a parity gap between the CLI and the pipeline (per the memory rule on interface parity) at no extra cost.

The `except ModelResolutionError` fallback to `template.model` switches the same way.

### D7 — An empty final turn is recovered like a mid-task ending (Architect; Part C)

An empty final turn has the same cause as the #92 captures: the model did the work in reasoning and ended its turn before writing the review. It gets the same single `FINISH_REVIEW_PROMPT` turn. It is not retried as a fresh request, because that would throw away the tool results already in history.

- **Typed, not string-matched.** `EmptyFinalTurnError` subclasses `ProviderError`, so every existing `except ProviderError` (the pipeline review action's failure artifact, the CLI, dispatch, summary) keeps working unchanged. `review_client` catches only the subclass. The message text stays byte-identical, because tests and failure artifacts already quote it.
- **Telemetry survives the exception.** `collect_turn` folds counts only after its `async for` completes, so a raise loses turn 1's numbers. The error carries `finish_reason`, `reasoning_chars`, `tool_calls_made`, and `failed_tool_calls`. `review_client` writes them into `TurnCapture` before deciding, so `stop_reason` feeds `budget_exhausted` and the counts sum across both turns as they do for the shipped recovery.
- **No empty assistant entry in history.** Today the agent appends `{"role": "assistant", "content": ""}` before raising. Whether a backend accepts an empty assistant message on the next request has not been verified for any backend. Consecutive user messages are accepted by the OpenAI chat schema, so dropping the empty entry takes the unverified case off the table. An empty turn carries nothing worth keeping.
- **Budget skip applies.** An empty turn with `finish_reason='length'` spent its budget on reasoning. D2's rule holds: no second turn, and the original `EmptyFinalTurnError` is re-raised so the failure artifact reads exactly as it does today.
- **One turn, still.** If the recovery turn also comes back empty, its `EmptyFinalTurnError` propagates. The WARNING logged before the recovery turn names the first failure, so the log shows both.
- **Provenance.** A recovered empty turn sets `recovery_turn_used`, so it gets `recoveryTurn: true` (D1).
- **Observable signal.** The existing `_require_final_content` WARNING still fires for each empty turn. `review_client` logs one WARNING before asking again: `review (model=…) returned an empty final turn (stop reason: …, reasoning chars: …); asking once more for the review`.

### Patterns and Conventions

- Stop-reason comparison values live only in `OUTPUT_BUDGET_STOP_REASONS`, not inline strings (project rule against scattered comparison values).
- New `ReviewResult` fields follow the existing tri-state convention: `max_output_tokens=None` means no budget was sent, and `output_budget_exhausted` is a plain bool because it is always computable.
- Frontmatter and digest additions appear only when their condition holds, so existing snapshot guards (`clean_pass_artifact.md`) stay unchanged. The one exception is the digest's budget line, which is always present (see B3).

## Implementation Details

### API Contracts

**`models.toml` alias field (B1):**

```toml
[aliases.kimi3]
profile = "openrouter"
model = "moonshotai/kimi-k3"
max_output_tokens = <from OpenRouter's listing, see B5>
```

- It must be an integer ≥ 1. The alias loader rejects anything else with the same error shape it uses for `tool_use`.
- Document it in the `models.toml` header comment next to `tool_use`.

**Reader (B1):** `model_max_output_tokens(name: str | None) -> int | None` in `models/aliases.py`. Unknown name, `None`, or unset all return `None`. It is the only reader of the field.

**`--output json` additions (A2, B3):** `max_output_tokens` (int or null) and `output_budget_exhausted` (bool). Both are always present, following 918's always-emit convention.

**Frontmatter (A1):** `recoveryTurn: true`, emitted only when `recovery_turn_used`.

**Run Digest:**

- **B3:** `Output budget: 32000 tokens` or `Output budget: backend default`. This line is always present. It is a new always-on line, so the digest snapshot fixtures are updated in the same commit.
- **A2:** the skip line from D2, only when the skip happened.

**Budget values (B5).** For each built-in alias with `profile = "openrouter"`, take the model's `top_provider.max_completion_tokens` from OpenRouter's `GET /api/v1/models` listing at implementation time. Record the listing date in the `models.toml` comment. Where the listing reports null, leave the field unset. Do not invent a value.

## Integration Points

### Provides to Other Slices

- `recoveryTurn` frontmatter key, for Context Forge's review gate and Amoeba (issue filed per D1).
- `ResolvedModel.max_output_tokens` and `AgentConfig.max_output_tokens`. The dispatch and summary actions already hold a `ResolvedModel` and can pass it on with one line each. That is left out here to keep the risk surface to reviews, and noted as a follow-up issue.

### Consumes from Other Slices

- 918's `TurnCapture.stop_reason`. If a provider stops stamping it, `budget_exhausted` returns False and recovery runs as today. Only an actual budget-exhausted signal suppresses the second turn.
- 919's `VerdictSource`, unchanged.

## Success Criteria

### Functional Requirements

1. A review whose first reply ends mid-task and is recovered carries `recoveryTurn: true` in frontmatter. Its `verdictSource` is whatever the recovered parse produced. A review that needed no recovery has no `recoveryTurn` key.
2. A review whose first reply ends mid-task with stop reason `length` or `max_tokens` makes **no** second `handle_message` call. It logs a WARNING naming the stop reason and budget, writes the skip line to the digest, and sets `output_budget_exhausted: true` in JSON. The verdict stays UNKNOWN.
3. A mid-task ending with stop reason `stop`, `end_turn`, or `None` still triggers exactly one recovery turn, as shipped.
4. The recovery turn runs on the same agent with the same tools available as the first turn.
5. An alias with `max_output_tokens = N` sends `max_completion_tokens=N` on every streamed request of an OpenAI-compatible review, including each turn of the agentic loop. An alias without it sends no budget parameter.
6. The digest shows `Output budget: N tokens` or `Output budget: backend default`, and JSON carries `max_output_tokens`.
7. A `sq run` pipeline review step using an alias with `tool_use = false` runs without tools, and one with `max_output_tokens` sends the budget. Both match `sq review` for the same alias.
8. The SDK and Codex agents log a WARNING when handed a `max_output_tokens` they cannot apply.
9. A review whose first turn ends empty with stop reason `stop` (the 928 capture) makes exactly one recovery turn. If that turn writes a review, the artifact is a normal review with `recoveryTurn: true`, and its tool-call count and reasoning chars include turn 1.
10. A review whose first turn ends empty with stop reason `length` makes no second call and produces the same failure artifact it does today.
11. A review whose recovery turn also ends empty produces a failure artifact carrying the recovery turn's error.
12. After an empty turn, the agent's history has no assistant entry with empty content.
13. Dispatch and summary actions that hit an empty final turn fail exactly as today.

### Technical Requirements

- `OUTPUT_BUDGET_STOP_REASONS` is the only place those strings appear in `src/`.
- `models.toml` loader rejects a non-integer or non-positive `max_output_tokens`.
- `ruff format`, `ruff check`, and `pyright` (strict) are clean. The full test suite is green.
- Tests (all in the existing files):
  - `tests/review/test_review_client.py`: skip-on-`length`, skip-on-`max_tokens`, recover-on-`None`, and a tool-set-preserved assertion for D3;
  - `tests/review/test_persistence.py`: `recoveryTurn` present and absent, budget digest line in both forms, skip line;
  - alias loader tests for the new field;
  - an OpenAI agent test asserting `max_completion_tokens` is passed, or `omit` when unset;
  - a pipeline review action test asserting `resolve_full` feeds both `model_allows_tools` and `max_output_tokens`;
  - `tests/providers/openai/test_agentic_loop.py`: the empty-turn test asserts `EmptyFinalTurnError` with its four attributes (it still matches `ProviderError`), and history has no empty assistant entry afterward, on both the tools and no-tools paths;
  - `tests/review/test_review_client.py`: empty-then-review recovers with summed telemetry; empty on `length` re-raises with no second call; empty-then-empty propagates the second error.

### Integration Requirements

- The CLI (`sq review`) and the pipeline review action produce the same frontmatter keys and digest lines for the same run shape.
- Existing artifacts stay valid, and `cf validate frontmatter` passes on an artifact carrying `recoveryTurn: true`.

### Verification Walkthrough

Run on 20260927 from the slice branch. Use `uv run sq` from the checkout: a globally installed `sq` (a `uv tool` install) is a released build without this slice. Steps 1–3 and 6 call paid models. Steps 1 and 3 overwrite the slice's review artifact and archive the previous one, so copy it aside first if it matters.

1. **Budget reaches the request and the artifact.**
   ```bash
   uv run sq review slice 924 --model kimi3 -v
   grep -E "Stop reason|Output budget" project-documents/user/reviews/924-review.slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md
   grep -A2 'model = "moonshotai/kimi-k3"' src/squadron/data/models.toml
   ```
   Actual: `- Stop reason: stop`, then `- Output budget: 943718 tokens`, which matches `max_output_tokens = 943718` on `kimi3` in `models.toml`. Verdict PASS, `verdictSource: stated`.

   For the no-budget case, every built-in OpenRouter alias now has a budget, and on 20260927 `gemini` and `gpt54-nano` both returned 429 (quota). Use a user alias with no budget (see step 3 for where to add it):
   ```toml
   [aliases.kimi3-nobudget]
   profile = "openrouter"
   model = "moonshotai/kimi-k3"
   ```
   Its JSON shows `"max_output_tokens": null` (step 2), and the digest renders `Output budget: backend default`, which the unit test `TestOutputBudgetDigestLine` pins.
2. **JSON carries the new fields.** `--output json` sends errors to stdout too, so redirect to a file before `jq`:
   ```bash
   uv run sq review slice 924 --model kimi3-nobudget --no-save --output json > out.json
   jq '{max_output_tokens, output_budget_exhausted, recovery_turn_used, verdictSource, stop_reason}' out.json
   ```
   Actual: `null`, `false`, `false`, `"stated"`, `"stop"`. With `--model kimi3` the first field is `943718`.
3. **A spent budget skips recovery.** Back up `~/.config/squadron/models.toml`, then add:
   ```toml
   [aliases.kimi3-tiny]
   profile = "openrouter"
   model = "moonshotai/kimi-k3"
   max_output_tokens = 64
   ```
   ```bash
   uv run sq review slice 924 --model kimi3-tiny -v
   ```
   Actual with 64 tokens (exit 1). This is the empty-turn branch of D2/D7, requirement 10:
   - stderr: `Model returned an empty final turn (finish_reason='length', reasoning_chars=348)`, then one `ended without writing the review and its output budget ran out (stop reason: length; budget: 64 tokens); not asking again`. No "asking once more" line.
   - The artifact is the usual provider-failure artifact: `verdict: UNKNOWN`, `providerFailure: true`.

   **Caveat, and a gap the design does not cover.** At `max_output_tokens = 256` the model made 26 small tool-call turns, then wrote `## Summary` with PASS and was cut off at `length` before any findings. The parse succeeded, so no recovery was needed and none was skipped. The artifact is a clean `verdict: PASS` / `verdictSource: stated` with `Stop reason: length` in the digest and `output_budget_exhausted: true` in JSON. Nothing in frontmatter tells a gate the review was truncated. See the note after step 6.

   A mid-task text ending on `length` (the skip line `Recovery turn: skipped — output budget exhausted (...)` in the digest) was not reproduced live. It is covered by `TestRecoveryTurn::test_spent_budget_skips_recovery` and `TestRecoveryTurnRendering::test_budget_skip_is_disclosed_in_the_digest`.

   Restore the backed-up `models.toml` afterward.
4. **Recovery provenance reaches frontmatter.** A live mid-task ending cannot be triggered on demand.
   ```bash
   uv run pytest tests/review/test_persistence.py -k "recovery or RecoveryTurn" -q
   ```
   Also verified: an artifact carrying `recoveryTurn: true`, placed under `project-documents/user/reviews/`, passes `cf validate frontmatter <path>` with "No inconsistencies found". cf validates only in-root files.
5. **Pipeline parity.** `sq run` refuses to run inside Claude Code (#144), so the Project Manager runs this step. No built-in alias sets `tool_use = false`, so add a user alias:
   ```toml
   [aliases.kimi3-notools]
   profile = "openrouter"
   model = "moonshotai/kimi-k3"
   tool_use = false
   ```
   ```bash
   uv run sq run review 924 --model kimi3-notools -v
   uv run sq review code 924 --model kimi3-notools -v
   ```
   Expected: both code-review artifacts show `toolsSuppressedReason` and no `toolsGiven`/`toolCallsMade`, and both digests show `Output budget: backend default`. The `review` pipeline's `checkpoint: on-concerns` pauses for input when the verdict is CONCERNS.

   Actual (PM, 20260927): both artifacts show `toolsSuppressedReason: model-capability`, no `toolsGiven`/`toolCallsMade`, `Tool calls made: not offered`, and `Output budget: backend default`. The only frontmatter difference is the pipeline's `runId`. Both reviews raised the same CONCERN: a budget was recorded even for providers that cannot send one. Fixed in `1d767962` with `ProviderCapabilities.applies_output_budget`. Before this slice the pipeline artifact showed tools offered. Unit coverage: `TestReviewAliasParity` in `tests/pipeline/actions/test_review_action.py`.
6. **Empty final turn is recovered (Part C).** Rerun the review that failed live:
   ```bash
   uv run sq review slice 928 --model glmflash -v
   ```
   If stderr shows the "returned an empty final turn … asking once more" WARNING, the artifact is a normal review with `recoveryTurn: true`. If the model answers on the first turn, the run proves nothing about Part C. In that case rely on the unit tests (`uv run pytest tests/review/test_review_client.py -k "Empty or empty" -q`) and grep future batch reports for the WARNING.

   Actual (about 30 minutes, exit 0): answered on the first turn. `verdict: CONCERNS`, `verdictSource: stated`, 43 tool calls (the loop hit its 20-iteration cap and withdrew tools), `Stop reason: stop`, `Output budget: 128000 tokens`, and no empty-turn WARNING. Part C's live coverage is step 3's empty turn on `length`, the skip branch. The recover branch is unit-tested only.

**Note: gap found in step 3.** A review cut off by its budget after writing a stated verdict saves as a clean PASS, and only the digest and JSON show the truncation. The design does not cover this case. It is filed as [#152](https://github.com/ecorkran/squadron/issues/152) rather than changed here.

## Risk Assessment

### Technical Risks

- **A budget below what a model needs** turns a working review into a truncated one.
- **The digest's always-on budget line** changes the bytes of every artifact.

### Mitigation Strategies

- B5 takes values from the model's published maximum, not a guess. D2 makes a too-small budget show up in the artifact rather than being retried.
- Update the digest snapshot fixtures in the same commit that adds the budget line, and call out the change in the CHANGELOG as a user-visible digest addition.

## Implementation Notes

### Development Approach

1. **Part A first; it is independent of the budget.**
   - A2: `OUTPUT_BUDGET_STOP_REASONS` and `budget_exhausted`, the skip branch and its WARNING, and `output_budget_exhausted` on the result, JSON, and digest skip line.
   - A1: the `recoveryTurn` frontmatter key.
   - A3: the tools-preserved test.
2. **Part B, bottom-up.**
   - `AgentConfig` field, then OpenAI agent request, then SDK/Codex warnings.
   - Alias field, reader, and loader validation.
   - `ResolvedModel` field, then `run_review_with_profile` parameter, then CLI threading.
   - Pipeline review action switched to `resolve_full` (D6).
   - Digest budget line and JSON, with snapshot fixture updates.
   - B5 values from OpenRouter's listing.
3. **Part C, after Part A** (it reuses A2's `budget_exhausted` and A1's `recoveryTurn`).
   - `EmptyFinalTurnError` in `providers/errors.py`, raised by `_require_final_content`; drop the empty history append at both call sites.
   - `review_client` catches it on the first turn, folds its telemetry, and joins the recovery decision.
4. File the context-forge issue for `recoveryTurn` and the dispatch/summary budget follow-up issue. Link both from the slice plan entry.

Effort moves to 3.5/5: Part A shrinks, D6 adds a call-site change of about the same size, and Part C adds one error type and one catch branch.

### Special Considerations

- `_stream_turn` is called once per agentic-loop iteration. The budget applies per request, not per review. That is the correct reading: the limit is on each response the model writes.
- B5 uses the OpenRouter models listing, a public unauthenticated endpoint. No credentials are involved.
