---
docType: slice-design
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [924]
interfaces: []
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: Tool-Heavy Reviews on OpenAI-Compatible Models — Effort, Batched Reads, and Per-Turn Usage

## Overview

amoeba's `sq run slices-plan` (run `run-20260928-slices-plan-a04bdb07`) reviewed slice 105 with `glm-flash` three times. The first round took ≤4 min with 7 tool calls. The next two took ~55 and ~26 min with 22 calls each. Output speed does not explain the difference. Three things do, and this slice fixes each one:

1. **Nobody chooses the reasoning effort** ([#154](https://github.com/ecorkran/squadron/issues/154)). No provider gets an effort setting, so every turn reasons at the upstream model's default depth, and the artifact does not record what that depth was.
2. **One file per turn** ([#157](https://github.com/ecorkran/squadron/issues/157)). `read_file` takes one `path`. Each turn resends the whole history, so a 22-turn review reprocesses the document plus every earlier read 22 times.
3. **Most of the cost goes unrecorded** ([#158](https://github.com/ecorkran/squadron/issues/158)). `_stream_turn` never reads usage, so prompt, cached, completion, and reasoning tokens are unknown. The digest's `Reasoning characters` comes from the final turn only (`_stamp_tool_telemetry`, [agent.py:604](../../../src/squadron/providers/openai/agent.py#L604)). In the 105 review that final turn alone was 66k characters, and the other ~20 turns went uncounted.

## Value

- A user can set a per-alias effort (`effort = "low"`) and cut the reasoning spent on every turn of a tool loop. The artifact records the level it ran with.
- Reviews take fewer turns because a model can read several files in one call, and the guidance tells it to. Fewer turns mean fewer resends of the history.
- Every OpenAI-compatible review records its turns, token totals (prompt, cached, completion, reasoning), and wall-clock time. That answers two open questions with data: does OpenRouter cache the resent history, and did the first two changes help?

## Technical Scope

**In scope**

- **A — Effort.** An optional `effort` field on a models.toml alias, from a closed vocabulary. It is carried `ResolvedModel` → `AgentConfig` and applied by the OpenAI-compatible and SDK providers. Codex warns that it cannot apply it. The level is recorded in frontmatter, the Run Digest, and `--output json`.
- **B — Batched reads.** `read_file` accepts `paths: list[str]` alongside `path`. Per-file caps stay as they are, and a new batch byte budget sits alongside them. Tool guidance says to batch reads and independent calls.
- **C — Per-turn usage.** Each streamed turn requests and reads usage. The agentic loop sums it, along with reasoning characters and the turn count. Review wall-clock is measured in `review_client`. All of it goes to frontmatter, digest, and JSON.

**Out of scope**

- Lowering `agent.max_tool_iterations`.
- Preloading predictable reads into the prompt ([#159](https://github.com/ecorkran/squadron/issues/159), which touches cf).
- #155 and #156 (SDK system prompt and setting sources).
- A `--effort` CLI flag and a per-step `effort:` key (D2).
- Codex effort. The Codex SDK is not installed in this environment, so its parameter cannot be verified. Filed as a follow-up issue during implementation (D4).
- Token usage for SDK and Codex runs. Those rows render `not reported`; SDK usage from `ResultMessage` is a follow-up issue.
- Recording OpenRouter's `usage.cost`.
- Effort on AgentConfig sites that do not resolve an alias: `pr/composer.py`, `metrology/audit.py`, `server/routes/agents.py`, `providers/auth.py`.

## Dependencies

### Prerequisites

- **924 (complete).** It set the pattern this slice follows: `max_output_tokens` is an alias field with one reader, carried on `ResolvedModel`/`AgentConfig`, gated by `ProviderCapabilities.applies_output_budget`, and recorded as the value actually sent.
- **927 (complete).** It added `answering_models` and the per-turn `chunk.model` read in `_stream_turn`. Usage is read the same way.
- `openai` 2.24.0: `chat.completions.create` has typed `reasoning_effort` (`none|minimal|low|medium|high|xhigh`) and `stream_options`.
- `claude-agent-sdk` 0.2.160: `ClaudeAgentOptions.effort` (`low|medium|high|xhigh|max`) and `thinking` (`{"type": "disabled"}` among others).

### Interfaces Required

- OpenRouter accepts top-level `reasoning_effort` as the OpenAI-style alias of `reasoning.effort` (API reference, parameters). It maps an unsupported non-`none` level to the nearest supported one. Its streams always end with a usage chunk, and that chunk carries one choice with an empty delta, not zero choices (API reference, streaming). `stream_options` is accepted and ignored there.
- OpenAI native streams report usage only when `stream_options={"include_usage": True}` is sent. Its usage chunk has an empty `choices` list.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `core/models.py` | New `Effort` StrEnum. `AgentConfig.effort: Effort \| None`. |
| `models/aliases.py` | `ModelAlias.effort`. `_extract_metadata` validates it. New single reader `model_effort(name)`. |
| `pipeline/resolver.py` | `ResolvedModel.effort`, filled by `model_effort(alias)`. |
| `pipeline/actions/review.py`, `dispatch.py`, `summary.py` | Pass `resolved.effort` into the config they build. |
| `cli/commands/review.py` | Reads `model_effort(alias_name)` next to `model_max_output_tokens` and passes it through. |
| `providers/base.py` | `ProviderCapabilities.applies_effort: bool = False`. |
| `providers/openai/provider.py`, `agent.py` | `applies_effort=True`. Sends `reasoning_effort` and `stream_options`. Reads `chunk.usage`. Accumulates `LoopTelemetry`. |
| `providers/sdk/provider.py` | `applies_effort=True`. Maps `Effort` to `effort` / `thinking`. |
| `providers/codex/agent.py` | WARNING when `config.effort` is set, the same as `max_output_tokens`. |
| `providers/errors.py` | `EmptyFinalTurnError` also carries the loop's `LoopTelemetry`. |
| `providers/openai/usage.py` (new) | `TokenUsage` and `LoopTelemetry` dataclasses, plus the chunk-usage reader. |
| `review/turn_capture.py` | `TurnCapture` gains `turns` and `usage`, summed across calls and the recovery turn. |
| `review/review_client.py` | Records the sent effort, times the review, and copies turns and usage onto `ReviewResult`. |
| `review/models.py`, `review/persistence.py` | New `ReviewResult` fields, frontmatter keys, digest lines, and `to_dict()` keys. |
| `tools/builtin/file_tools.py`, `tools/limits.py` | `read_file` `paths`. `MAX_READ_BATCH_BYTES`. |
| `tools/guidance.py` | One added paragraph on batching. |
| `data/models.toml` | Header comment documents `effort`. No built-in alias sets it. |

### Data Flow

**Effort.** An alias in models.toml carries `effort = "low"`. `_extract_metadata` validates it into `ModelAlias`. `model_effort(alias)` fills `ResolvedModel.effort` in the pipeline, or the CLI reads it directly. The value lands on `AgentConfig.effort`, and each provider applies it:

- **openai:** `reasoning_effort=<value>` on every turn.
- **sdk:** `ClaudeAgentOptions(effort=...)`, or `thinking={"type": "disabled"}` for `none`.
- **codex:** WARNING, not sent.

`review_client` records `sent_effort = effort if provider.capabilities.applies_effort else None` onto `ReviewResult.effort`.

**Usage.** Each OpenAI turn is created with `stream_options={"include_usage": True}`. Every chunk's `chunk.usage` is read before the `choices` check; the last non-null value per turn wins. `TurnResult.usage` feeds the agent's `LoopTelemetry`, which accumulates turns, usage, and reasoning characters and is reset at the top of `handle_message`. `_stamp_tool_telemetry` stamps `turns`, `usage`, and the loop's `reasoning_chars` onto the final Message metadata. An empty final turn does not return normally, so it rides `EmptyFinalTurnError.telemetry` instead. `collect_turn` or `fold_empty_turn` then sums the values into `TurnCapture` across the recovery turn. `review_client` copies them onto `ReviewResult` along with `duration_seconds`, and they render in frontmatter, the digest, and JSON.

### State Management

`LoopTelemetry` is per-`handle_message` agent state, reset at the top of every call the same way as `_answering_models`. `TurnCapture` sums across calls. Nothing persists beyond the review artifact.

## Technical Decisions

### D1 — One closed vocabulary: `none`, `low`, `medium`, `high`, `xhigh`

`Effort(StrEnum)` lives in `core/models.py`, next to `AgentConfig`, which is its consumer. The vocabulary is the intersection of the two providers that apply it (OpenAI-style `reasoning_effort` and SDK `effort`), plus `none`.

- `none` is kept because disabling reasoning is the most useful setting for a tool-heavy loop. It maps to `reasoning_effort="none"` and to SDK `thinking={"type": "disabled"}` with no `effort`.
- `minimal` (OpenAI only) and `max` (SDK only) are left out. Each would need a "valid here, unappliable there" rule. Add one when a user asks for it.

Validation follows the `max_output_tokens` precedent. A value outside the vocabulary logs a WARNING naming the alias and file, and the field is skipped. Unset means nothing is sent, which is today's behavior.

**Effort covers thinking.** #154 asks whether `thinking` needs a separate field. It does not: `none` is the only thinking control a review needs, and a token budget (`reasoning.max_tokens`, SDK `ThinkingConfigEnabled`) is a second knob nobody has asked for.

### D2 — Overrides come from aliases, not flags

#154 asks for `--effort` and a step-level `effort:`. Both are left out. An alias is already the per-invocation and per-step selector: `--model` and a step's `model:` both take one, and `~/.config/squadron/models.toml` can define `glm-flash-low` next to `glm-flash` with the same model id. That gives the same control with no new CLI option, pipeline schema key, or precedence rule. The rationale is recorded on #154 when this slice lands.

### D3 — OpenAI-compatible wire format: top-level `reasoning_effort`

One typed parameter works for OpenAI native and OpenRouter, since OpenRouter documents `reasoning_effort` as the OpenAI-style alias. Gemini's OpenAI-compatible endpoint accepts it too. Profile-specific dispatch (OpenRouter's `reasoning: {effort}` object in `extra_body`) is not needed and would branch on profile identity. It is passed explicitly, not through `**kwargs`, which keeps the typed overload (see the existing comment at `_stream_turn`).

A backend that rejects the level returns a 400. That surfaces as `ProviderAPIError`, which is loud, and that is correct: the user asked for a level the model cannot run at.

### D4 — Capability flag `applies_effort`; Codex warns

This mirrors `applies_output_budget` exactly. `ProviderCapabilities.applies_effort` is True for openai and sdk. Codex logs `"Codex agent cannot apply effort=%s; the backend default applies"` and records nothing. The artifact never claims a level that was not sent. Codex applies nothing because `codex_app_server` is not installed here, so `thread_start`'s reasoning parameter cannot be verified. A follow-up issue is filed at implementation.

### D5 — `read_file`: `path` or `paths`, exactly one

The parameters schema declares both properties with `required: []`, not `oneOf`, because several backends mishandle `oneOf` in tool schemas. The executor enforces the rule:

- Both or neither → an error result naming the rule.
- An empty `paths` list → an error.
- `path` alone → byte-for-byte today's result, with no header.
- `paths`, even with one entry → each file under a `==> {requested path} <==` header, in request order. This is `head`'s convention, which models already know.

Each file is read through the existing single-file body: jail check, line-reference fallback, special-file rejection, and `MAX_READ_BYTES` truncation. That body is extracted into a helper that both shapes call, so single-file behavior cannot drift. A per-file failure renders inline under that file's header. The batch's `ToolResult.is_error` is True only when every file failed, so `failed_tool_calls` still means "the call gave the model nothing".

### D6 — A batch byte budget keeps the per-result floor valid

`limits.min_tool_result_chars()` is 1.5 × `MAX_READ_BYTES`, and the agent-side cap truncates any single result above it. Three 256 KB files in one call would therefore be cut mid-file, and the tool's own marker would be lost. That is the failure `limits.py` documents twice.

New constant `MAX_READ_BATCH_BYTES = MAX_READ_BYTES`. Files are appended in order until the next one would exceed the budget. Every remaining path then gets one line: `[not read: batch budget of N bytes reached; request it in another call]`. A first file larger than the budget is still read with its normal per-file truncation, so a batch never returns less than a single read would.

The floor formula needs no change, because the batch output is bounded by the same number plus headers. A unit test asserts that `MAX_READ_BATCH_BYTES` plus header overhead stays under `min_tool_result_chars()`, so raising one without the other fails.

### D7 — Guidance wording stays tool-agnostic

`guidance.py`'s docstring says the prose never names a specific tool. The new paragraph keeps to that:

> When you already know several files you need, request them together — in one call if the tool accepts several paths, and as parallel tool calls in one turn otherwise. Every turn resends the whole conversation, so one file per turn is the slowest way to read.

The first sentence covers #157. The second covers what the loop already supports (several tool calls per turn) and what nothing currently asks for. The existing sentence "Do not read files a claim does not depend on" stays, so batching is not an invitation to read everything.

### D8 — Usage: read every chunk, last value per turn, sum per loop

- `stream_options={"include_usage": True}` is sent on every turn, unconditionally. OpenAI needs it. OpenRouter ignores it and always reports usage.
- `chunk.usage` is read before the `if not chunk.choices: continue` guard. OpenAI's usage chunk has no choices. OpenRouter's has one choice with an empty delta that repeats `finish_reason`, which the existing aggregation already handles without change.
- `TokenUsage` fields are `prompt`, `cached`, `completion`, and `reasoning`, each `int | None`. `cached` comes from `prompt_tokens_details.cached_tokens` and `reasoning` from `completion_tokens_details.reasoning_tokens`. Each is `None` when the backend did not report it. The summing rule is `turn_capture._add`, where `None` survives only when no turn reported the field. That helper moves to the new `usage.py` module and both callers import it, keeping one definition.
- **Reasoning characters becomes the loop total.** `_stamp_tool_telemetry` stamps `LoopTelemetry.reasoning_chars`, not `turn.reasoning_chars`. The digest line keeps its label, which now means what a reader already assumed it meant. `EmptyFinalTurnError`'s message keeps the final turn's value, since that diagnoses the empty turn, and its `telemetry` carries the total.
- `turns` counts `_stream_turn` calls, the requests actually sent. It is not the same as tool calls.

### D9 — Wall-clock is measured once, in `review_client`, for every provider

`time.monotonic()` is read before `provider.create_agent` and after `_collect_review`, so it includes the recovery turn. It is provider-agnostic, so SDK and Codex reviews get it too. It is stored as `ReviewResult.duration_seconds: float | None` and rendered with one decimal place. `None` only on a hand-built result.

### D10 — Frontmatter carries effort and run cost; keys appear only when reported

The slice plan puts these in frontmatter. That differs from slice 918 D10, which kept diagnostics out, but these are not parse diagnostics: they describe what the run cost. A consumer comparing runs across artifacts (amoeba, cf) needs them without parsing the body. The keys follow the slice 265/266/927 convention: each is emitted only when it has a value.

| Key | Present when |
|---|---|
| `effort` | An effort was sent. |
| `turns` | The provider stamped it (openai). |
| `promptTokens`, `cachedTokens`, `completionTokens`, `reasoningTokens` | Individually, when summed to a non-None value. |
| `durationSeconds` | Always on a `review_client` result. |

`durationSeconds` changes every artifact, including the `clean_pass_artifact.md` snapshot, so the fixture is regenerated once, deliberately. cf does not reject unknown keys, which is how `runId` and `diffTruncated` were added without cf changes.

New Run Digest lines always render, with the `not reported` sentinel via `_render_optional`:

```
- Effort: low                       # or "backend default"
- Turns: 9
- Tokens — prompt / cached / completion / reasoning: 412803 / 380112 / 9214 / 6120
- Duration: 214.3 s
```

`to_dict()` gains `effort`, `turns`, `prompt_tokens`, `cached_tokens`, `completion_tokens`, `reasoning_tokens`, and `duration_seconds`. They are always present and null when not reported, matching `stop_reason`.

### D11 — Where effort flows, and where it does not

Effort reaches every site that resolves an alias: the `sq review` CLI, and the pipeline review, dispatch, and summary actions via `resolve_full`. Sites that build `AgentConfig` without an alias (listed in Out of scope) have no alias to read. Dispatch and summary get effort but have no artifact, so the provider's own behavior is the record, plus a DEBUG log of the sent level in `create_agent`.

## Implementation Details

### API Contracts

**models.toml alias field**

```toml
[aliases.glm-flash-low]
profile = "openrouter"
model = "z-ai/glm-5.3-flash"   # same id as built-in glm-flash (data/models.toml)
effort = "low"                 # none | low | medium | high | xhigh
```

**`read_file` tool schema**

```json
{
  "type": "object",
  "properties": {
    "path":  {"type": "string", "description": "One file to read, relative to the working directory."},
    "paths": {"type": "array", "items": {"type": "string"},
              "description": "Several files to read in one call. Use this instead of one call per file. Give either path or paths, not both."}
  },
  "required": []
}
```

**Batched result shape**

```
==> src/a.py <==
<contents or per-file error / truncation marker>

==> src/b.py <==
<contents>

==> src/c.py <==
[not read: batch budget of 256000 bytes reached; request it in another call]
```

**Message metadata (final Message, OpenAI agent)**

The existing keys are unchanged, except that `reasoning_chars` becomes the loop total. New keys: `turns: int` and `usage: {"prompt": int|None, "cached": ..., "completion": ..., "reasoning": ...}`.

## Integration Points

### Provides to Other Slices

- `Effort` and `model_effort()` give any future site that resolves an alias one reader.
- Usage fields in frontmatter and JSON give amoeba and metrology cost data per review. #159 (preloading) can measure its own effect against these fields.

### Consumes from Other Slices

- 924's alias-field and capability-flag pattern, and 927's per-chunk read in `_stream_turn`.
- `collect_turn` and `fold_empty_turn` (918/924). Their per-call summing extends to the new fields with no change to the recovery-turn logic.

## Success Criteria

### Functional Requirements

1. An alias with `effort = "low"` sends `reasoning_effort="low"` on every turn of an OpenAI-compatible review, including tool-loop turns and the recovery turn.
2. The same alias on the SDK profile yields `ClaudeAgentOptions.effort="low"`. `effort = "none"` yields `thinking={"type": "disabled"}` and no `effort`.
3. On Codex, a set effort logs a WARNING and the artifact records no effort.
4. An invalid `effort` value logs a WARNING naming the alias and file, and nothing is sent.
5. No `effort` set gives request parameters identical to today, apart from `stream_options`.
6. `read_file` with `path` returns byte-identical output to today. With `paths` it returns headed sections in request order, per-file errors inline, and the batch-budget marker for files past `MAX_READ_BATCH_BYTES`. `is_error` is set only when every file failed. Both or neither of `path`/`paths` returns an error.
7. The tool-use guidance block contains the batching paragraph.
8. A review whose stream reports usage records summed prompt, cached, completion, and reasoning tokens and a turn count in frontmatter, digest, and JSON. `Reasoning characters` is the loop total.
9. A backend that omits a usage field records it as `not reported` / null / absent key, never as 0.
10. An empty final turn still contributes its turns and usage to the capture (via `EmptyFinalTurnError`).
11. Every `review_client` review records `durationSeconds`, including SDK and Codex runs.

### Technical Requirements

- `ruff format`, `ruff check`, and `pyright` (strict) clean. The full test suite passes, with fixtures regenerated only where D10 says the output changes.
- Unit tests:
  - alias parsing of `effort` (valid, invalid, bool, absent), parametrized
  - `ResolvedModel.effort` round-trip
  - the provider mappings (openai kwargs, SDK options, Codex warning)
  - `read_file` single, batch, mixed failure, all-fail, budget cutoff, oversize first file, and both/neither
  - the `MAX_READ_BATCH_BYTES` vs floor invariant
  - usage-chunk parsing for both the OpenAI (no choices) and OpenRouter (one empty choice) shapes
  - summing across a three-turn loop plus the recovery turn
  - `None`-preserving sums
  - frontmatter, digest, and JSON rendering agreeing from one `ReviewResult`

### Integration Requirements

- `sq review` CLI and `sq run` pipeline reviews produce the same effort and usage fields for the same alias (interface parity).
- The artifact still passes `cf validate frontmatter` with the new keys.

### Verification Walkthrough

Draft; refined after Phase 6.

1. **Define a low-effort alias.** Add to `~/.config/squadron/models.toml`:
   ```toml
   [aliases.glm-flash-low]
   profile = "openrouter"
   model = "z-ai/glm-5.3-flash"
   effort = "low"
   ```
   The model id must match the built-in `glm-flash` alias, which `sq models list` shows. `sq models list` also shows the new alias.

2. **Baseline review at the default effort.**
   ```
   sq review slice 931 --model glm-flash -v
   ```
   Open the saved review in `project-documents/user/reviews/`. Frontmatter has `turns`, the four token keys, and `durationSeconds`, and no `effort` key. The Run Digest shows `Effort: backend default`, `Turns: N`, the token line, and `Duration`. `cachedTokens` answers whether OpenRouter cached the resent history. A non-zero value means yes.

3. **Same review at low effort.**
   ```
   sq review slice 931 --model glm-flash-low -v
   ```
   Frontmatter has `effort: low`. Compare `reasoningTokens`, `turns`, and `durationSeconds` against step 2.

4. **Batched reads happen.** Run step 3 at `-vv`, or read the prompt log at `-vvv`. At least one `read_file` call carries `paths` with more than one entry, and the output shows `==> path <==` headers. `Tool calls made` is lower than the 22 seen in the amoeba run for a comparable document.

5. **JSON parity.**
   ```
   sq review slice 931 --model glm-flash-low --output json --no-save | jq '{effort, turns, prompt_tokens, cached_tokens, reasoning_tokens, duration_seconds}'
   ```
   The values match the markdown artifact's frontmatter for the same kind of run.

6. **Pipeline parity.** The built-in `review` pipeline runs a code review of slice 931's branch through the pipeline review action, which is the `resolve_full` path:
   ```
   sq run review 931 --model glm-flash-low --dry-run
   sq run review 931 --model glm-flash-low
   ```
   The dry run shows `glm-flash-low` on the review step. The saved code review has `effort: low` and the usage keys.

7. **Codex refuses loudly.** Define an alias on the `openai-oauth` profile with `effort = "low"` and run a review. A WARNING says effort cannot be applied, and the artifact has no `effort` key.

8. **Invalid value.** Set `effort = "extreme"` on the test alias. Any `sq` command that loads aliases logs the skip WARNING naming the alias and file.

## Risk Assessment

### Technical Risks

- `stream_options` now goes on every OpenAI-compatible request, including backends without effort set. A backend that rejects the parameter would fail every request, where today it succeeds. The built-in profiles are openai, openrouter, gemini, and local (Ollama). OpenAI and OpenRouter document it. Gemini's and Ollama's OpenAI-compatible endpoints need confirming.

### Mitigation Strategies

- Phase 6 runs one live review per reachable built-in profile before merge. If a backend rejects `stream_options`, the fix is a profile-level opt-out field, not string dispatch on the profile name. That field is added only if a backend actually fails.

## Implementation Notes

### Development Approach

Order: **C → B → A**. Usage first, so B and A are measured, not guessed.

1. **C:**
   - `usage.py` (`TokenUsage`, `LoopTelemetry`, the moved `_add`)
   - `_stream_turn` reads usage and sends `stream_options`
   - loop accumulation and stamping, and `EmptyFinalTurnError.telemetry`
   - `TurnCapture` and `review_client` timing
   - `ReviewResult` fields and rendering, then regenerate fixtures
   - live baseline run: walkthrough step 2
2. **B:**
   - extract the single-file read helper, with the single-path byte-identical test first
   - `paths` and the batch budget
   - the guidance paragraph
   - live run
3. **A:**
   - `Effort` and the alias field and reader
   - `ResolvedModel` and the call sites
   - the capability flag and the three providers
   - rendering
   - live runs: walkthrough steps 3–8
4. File the two follow-up issues (Codex effort, SDK usage), and comment the D2 decision on #154.

Tests use stubbed `AsyncStream`s for the chunk shapes, the way slice 927's `chunk.model` tests do. No live calls run in the suite.

### Special Considerations

- `_stream_turn` runs inside the event loop. Reading usage is attribute access, well under the 1 ms rule. `read_file` batches keep every blocking read inside the one existing `asyncio.to_thread` call, so a batch is one worker hop, not N.
- The `_add` move must not change `turn_capture`'s behavior. Its existing tests are the guard.
- `answering_models` and usage are both read from choice-less chunks. Read them in the same spot so the next field added there has one obvious home.
