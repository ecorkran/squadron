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
- **C — Per-turn usage.** Each streamed turn requests and reads usage. The agentic loop sums it, along with reasoning characters and the turn count. Review wall-clock is measured in `review_client`. All of it goes to frontmatter, digest, and JSON. That includes a provider-failure artifact, which gets whatever the run had gathered when it failed (D12).

**Why one slice.** The initiative's guidelines prefer small, independently deliverable slices. Bundling these three is a Project Manager decision: #154's comment says to bundle #157 and #158 into one slice, and the slice plan entry does so. This design keeps that decision and does not reopen it. It does keep the parts independently deliverable inside the slice:

- Each part lands as its own commit or commits, in the order C → B → A. Each commit passes the full suite on its own, and each can be reverted without touching the others. B and A share no code, and neither depends on C for correctness.
- No gate on one part holds back another. The only unverified external fact (Gemini's handling of `stream_options`) is settled by shipping Gemini with the parameter off (see Risk Assessment), so there is no merge precondition at all.
- **B can be cut out.** B shares no code with A or C, so it is the one part whose inclusion rests only on the PM decision and shared fixture work. If implementation runs long, B moves to its own slice, which needs no design change: D5–D7 stand alone. A and C stay together, because A's recorded level renders through C's frontmatter and digest additions.
- The bundle is justified by shared work, not shared behavior:
  - C is the instrument that shows whether B and A worked.
  - All three edit `_stream_turn`/`_run_agentic_loop` and the same `ReviewResult` rendering. Three slices would mean three rounds of fixture regeneration over one snapshot.

**Initiative fit.** Each part maps to a line of the 900 architecture's "Work that belongs here" list (`900-arch.maintenance-and-refactoring.md`, Scope):

| Part | Scope line | Why |
|---|---|---|
| A — Effort | **Operational:** "configuration improvements that span subsystems" | An alias setting applied across three providers, the pipeline, and the CLI. It has the same shape as 924's `max_output_tokens`, which this initiative already shipped. This is the weakest of the three mappings, so its two halves are stated separately. **The fix:** recording the level the run actually used. An artifact that cannot state the condition it ran under is defective. #154 records glm-flash spending 68,841 reasoning characters on slice 929's tasks review at a level nobody chose or could see. That half belongs here unambiguously. **The control:** the alias field is included because it is the smallest thing that makes the recorded level meaningful. Without it, every run records "backend default", and the record says nothing a user can act on. It is one optional field on an existing mechanism, following 924's precedent, not a new workflow. |
| B — Batched reads | **Tech debt:** "restructured for … performance" | The loop already executes several tool calls per turn. The read tool's one-path shape and the silent guidance force the slowest pattern. |
| C — Per-turn usage | **Operational:** logging; **Bug fixes** | `Reasoning characters` under-reports what its label claims (final turn only), and usage is never read. |

It is not "a new feature or capability" in the excluded sense: no new command, workflow, or user task becomes possible. Two optional inputs (an alias field and a tool parameter) change how existing reviews run, and each keeps today's behavior when absent.

**Out of scope**

- Lowering `agent.max_tool_iterations`.
- Preloading predictable reads into the prompt ([#159](https://github.com/ecorkran/squadron/issues/159), which touches cf).
- #155 and #156 (SDK system prompt and setting sources).
- A `--effort` CLI flag and a per-step `effort:` key (D2).
- Codex effort. The Codex SDK is not installed in this environment, so its parameter cannot be verified. Filed as a follow-up issue during implementation (D4).
- Token usage for SDK and Codex runs. Those rows render `not reported`. SDK usage from `ResultMessage` is a follow-up issue. The neutral types in D8 are what that issue plugs into.
- Recording OpenRouter's `usage.cost`.
- Effort on AgentConfig sites that do not resolve an alias: `pr/composer.py`, `metrology/audit.py`, `server/routes/agents.py`, `providers/auth.py`.
- A timeout on `read_file` reads (D12, hung reads).

## Dependencies

### Prerequisites

- **924 (complete).** It set the pattern this slice follows: `max_output_tokens` is an alias field with one reader, carried on `ResolvedModel`/`AgentConfig`, gated by `ProviderCapabilities.applies_output_budget`, and recorded as the value actually sent.
- **927 (complete).** It added `answering_models` and the per-turn `chunk.model` read in `_stream_turn`. Usage is read the same way.
- **195 (complete).** Its provider-failure artifact (`format_provider_failure_markdown`) reads telemetry off the `ProviderError` (`tool_calls_made` today). D12 extends that.
- `openai` 2.24.0: `chat.completions.create` has typed `reasoning_effort` (`none|minimal|low|medium|high|xhigh`) and `stream_options`.
- `claude-agent-sdk` 0.2.160: `ClaudeAgentOptions.effort` (`low|medium|high|xhigh|max`) and `thinking` (`{"type": "disabled"}` among others).

### Interfaces Required

Backend behavior for the two new request parameters, per built-in OpenAI-compatible profile. The Source column says whether this was checked against docs, live, or both (20260928).

| Profile | `stream_options.include_usage` | `reasoning_effort` | Usage chunk shape | Source |
|---|---|---|---|---|
| openai | Required for usage | Typed in SDK | Empty `choices` | OpenAI SDK types |
| openrouter | Accepted, ignored; usage always sent | Documented OpenAI-style alias of `reasoning.effort`. Unsupported non-`none` levels map to the nearest level. | One choice, empty delta, repeats `finish_reason` | OpenRouter API reference: parameters, streaming |
| local (Ollama 0.34.2) | Accepted, usage sent | Documented. `xhigh` maps to `max`; `none` disables thinking. | Empty `choices`; `prompt_tokens_details.cached_tokens` present, no `completion_tokens_details` | Ollama docs, plus a live probe against `llama3.2` |
| gemini | **Undocumented. Live probes on 20260928 across `gemini-3.8-flash`, `gemini-3.5-flash-lite`, and `gemini-3.1-pro-preview-customtools` returned only 503 (demand) or 429 (free-tier quota).** | Documented (`minimal\|low\|medium\|high\|none`) | Unknown | Gemini OpenAI-compat docs |

Gemini's `stream_options` behavior is the one open fact. The gemini built-in profile therefore ships with `sends_stream_usage = False` and keeps today's exact request (see Risk Assessment). Nothing waits on the answer.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `core/models.py` | New `Effort` StrEnum. `AgentConfig.effort: Effort \| None`. |
| `core/usage.py` (new) | Provider-neutral `TokenUsage`, `RunTelemetry` (turns, reasoning chars, usage), and `add_optional` (the `None`-preserving sum, moved from `turn_capture._add`). |
| `models/aliases.py` | `ModelAlias.effort`. `_extract_metadata` validates it. New single reader `model_effort(name)`. |
| `pipeline/resolver.py` | `ResolvedModel.effort`, filled by `model_effort(alias)`. |
| `pipeline/actions/review.py`, `dispatch.py`, `summary.py` | Pass `resolved.effort` into the config they build. |
| `cli/commands/review.py` | Reads `model_effort(alias_name)` next to `model_max_output_tokens` and passes it through. |
| `providers/base.py` | `ProviderCapabilities.applies_effort: bool = False`. |
| `providers/profiles.py` | `ProviderProfile.sends_stream_usage: bool = True`, readable from a user profile table. The gemini built-in sets it False. New `profile_credentials(profile)` returns the profile-derived `credentials` entries (`api_key_env`, `default_headers`, `sends_stream_usage`). |
| `review/review_client.py`, `pipeline/actions/dispatch.py`, `pipeline/summary_oneshot.py`, `metrology/audit.py`, `pr/composer.py`, `cli/commands/spawn.py` | Each builds `credentials` by copying profile fields by hand today. Each switches to `**profile_credentials(profile)`, so the new flag reaches every OpenAI-compatible agent from one definition. |
| `providers/errors.py` | `ProviderError` gains `telemetry: RunTelemetry \| None` and `duration_seconds: float \| None`, beside `tool_calls_made`. `EmptyFinalTurnError` uses the inherited `telemetry`. |
| `providers/openai/usage.py` (new) | OpenAI-shaped only: `read_chunk_usage(chunk) -> TokenUsage \| None`, which also reports malformed detail fields. |
| `providers/openai/provider.py`, `agent.py` | `applies_effort=True`. Sends `reasoning_effort`, and sends `stream_options` unless `credentials["sends_stream_usage"]` is False. Only a profile can opt out. An absent key means no profile was involved, which is today only the daemon's `server/routes/agents.py`, whose agents are built from request bodies. Those agents send it, which is the OpenAI spec's behavior. A test pins both cases. Accumulates `RunTelemetry`. Attaches it to every `ProviderError` leaving `handle_message`. Adds `httpx.TimeoutException`/`httpx.TransportError` to the existing conversions. Logs the exit WARNING on any non-normal exit (D12). |
| `providers/sdk/provider.py` | `applies_effort=True`. Maps `Effort` to `effort` / `thinking`. |
| `providers/codex/agent.py` | WARNING when `config.effort` is set, the same as `max_output_tokens`. |
| `review/turn_capture.py` | `TurnCapture` gains `turns` and `usage`, summed with `core.usage.add_optional`. |
| `review/review_client.py` | Records the sent effort. Times the review. Copies turns and usage onto `ReviewResult`. Stamps `duration_seconds` on a `ProviderError` before it propagates. |
| `review/models.py`, `review/persistence.py` | New `ReviewResult` fields, frontmatter keys, digest lines, and `to_dict()` keys. The provider-failure artifact renders the same keys from the error. |
| `tools/builtin/file_tools.py`, `tools/limits.py` | `read_file` `paths`. `MAX_READ_BATCH_BYTES`. |
| `tools/guidance.py` | One added paragraph on batching. |
| `data/models.toml` | Header comment documents `effort`. No built-in alias sets it. |

**Dependency direction.** `frontmatter.parent` is the slice plan, per the template. The 900 architecture document above it defines scope and guidelines, not layers, so the layering rule here has two sources: the project's rules, and the import graph as it stands.

- **Project rules:** CLAUDE.md, "Program to interfaces (contracts). Maintain clear separation between components". `review-code.md`, Dependency Inversion: "Business logic imports concrete infrastructure … directly rather than through an interface" is a violation.
- **Current imports:** `review/` imports the provider layer's shared modules only: `providers.base`, `providers.errors`, `providers.loader`, `providers.profiles`, and `providers.registry` (verified by grep, 20260928). It imports no concrete provider package (`providers/openai`, `providers/sdk`, `providers/codex`).

This slice keeps that rule. The only new imports into `review/` are `core.usage` and `providers.errors`, and nothing there imports `providers/openai`. `providers/openai` imports `core.usage`, never the reverse.

**`core` ↔ `providers` today.** The two packages already depend on each other at package level: `core/agent_registry.py` imports `providers.base` and `providers.registry` (verified by grep, 20260928). The new edges are `providers/errors.py` → `core.usage` and `providers/openai` → `core.usage`. They cannot form an import cycle, because `core/usage.py` is a leaf. It imports only the standard library (`dataclasses`), nothing from `squadron`. It holds plain data and one summing function, so it has no reason to import anything.

Two greps in the Technical Requirements enforce the rule:

- `review/` never imports `providers/openai`.
- `core/usage.py` imports nothing from `squadron`.

### Data Flow

**Effort.** An alias in models.toml carries `effort = "low"`. `_extract_metadata` validates it into `ModelAlias`. `model_effort(alias)` fills `ResolvedModel.effort` in the pipeline, or the CLI reads it directly. The value lands on `AgentConfig.effort`, and each provider applies it:

- **openai:** `reasoning_effort=<value>` on every turn.
- **sdk:** `ClaudeAgentOptions(effort=...)`, or `thinking={"type": "disabled"}` for `none`.
- **codex:** WARNING, not sent.

`review_client` records `sent_effort = effort if provider.capabilities.applies_effort else None` onto `ReviewResult.effort`.

**Usage on success.**

1. Each OpenAI turn is created with `stream_options={"include_usage": True}`.
2. `read_chunk_usage` reads every chunk before the `choices` check. The last non-None value in a turn wins, and becomes `TurnResult.usage`.
3. The agent folds each turn into its `RunTelemetry`, which is reset at the top of `handle_message`.
4. `_stamp_tool_telemetry` stamps `turns`, `usage`, and the run's `reasoning_chars` onto the final Message metadata.
5. `collect_turn` sums them into `TurnCapture` across calls, including the recovery turn.
6. `review_client` copies them onto `ReviewResult` with `duration_seconds`.
7. They render in frontmatter, the digest, and JSON.

**Usage on failure.** Any `ProviderError` leaving `handle_message` carries a snapshot of the `RunTelemetry` gathered so far in its `telemetry` attribute (D12). `EmptyFinalTurnError` is a subclass, and `fold_empty_turn` reads the same attribute. `review_client` stamps `duration_seconds` on the error as it propagates. `format_provider_failure_markdown` reads both off the error, the same way it already reads `exc.tool_calls_made`, so the CLI and pipeline call sites are unchanged.

### State Management

`RunTelemetry` is per-`handle_message` agent state, reset at the top of every call the same way as `_answering_models`. `TurnCapture` sums across calls. Nothing persists beyond the review artifact.

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

One typed parameter works for every built-in OpenAI-compatible profile (see the Interfaces Required table). Profile-specific dispatch, such as OpenRouter's `reasoning: {effort}` object in `extra_body`, is not needed and would branch on profile identity. It is passed explicitly, not through `**kwargs`, which keeps the typed overload (see the existing comment at `_stream_turn`).

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

### D8 — Usage: neutral types, one OpenAI reader, summed per run

**Placement.** The types are provider-neutral and live in `core/usage.py`:

- `TokenUsage` has `prompt`, `cached`, `completion`, and `reasoning`, each `int | None`.
- `RunTelemetry` has `turns: int`, `reasoning_chars: int`, and `usage: TokenUsage`.
- `add_optional` is moved from `turn_capture._add` unchanged. `turn_capture` and the agent both import it from `core/usage.py`.

`ReviewResult` and `TurnCapture` refer only to these. The OpenAI wire format stays in `providers/openai/usage.py`. When the SDK-usage issue lands, it maps `ResultMessage.usage` onto the same `TokenUsage` without touching `review/`.

**Reading.**

- `stream_options={"include_usage": True}` is sent on every turn, unconditionally.
- `chunk.usage` is read before the `if not chunk.choices: continue` guard. That covers both shapes in the Interfaces table: OpenAI and Ollama send no choices, OpenRouter sends one empty choice. The existing aggregation already handles OpenRouter's repeated `finish_reason`.
- `cached` comes from `prompt_tokens_details.cached_tokens`, and `reasoning` from `completion_tokens_details.reasoning_tokens`. Each is `None` when the backend did not report it. Ollama omits `completion_tokens_details` entirely.
- Sums use `add_optional`, where `None` survives only when no turn reported the field.

**Reasoning characters becomes the run total.** `_stamp_tool_telemetry` stamps `RunTelemetry.reasoning_chars`, not `turn.reasoning_chars`. The digest line keeps its label, which now means what a reader already assumed it meant. `EmptyFinalTurnError`'s message and its `reasoning_chars` attribute keep the final turn's value, because that diagnoses the empty turn. Its `telemetry` carries the total, and `fold_empty_turn` reads the total from there.

**Turns.** `turns` counts `_stream_turn` calls, which are the requests actually sent. That is not the same as tool calls.

### D9 — Wall-clock is measured once, in `review_client`, for every provider

`time.monotonic()` is read before `provider.create_agent`. On success it is read again after `_collect_review`, so the recovery turn is included. On a `ProviderError`, an `except` clause sets `exc.duration_seconds` and re-raises. That clause is narrow and does not swallow anything. It is provider-agnostic, so SDK and Codex reviews get it too.

The value is stored as `ReviewResult.duration_seconds: float | None` and rendered with one decimal place. It is `None` only on a hand-built result.

### D10 — Frontmatter carries effort and run cost; keys appear only when reported

The slice plan puts these in frontmatter. That differs from slice 918 D10, which kept diagnostics out, but these are not parse diagnostics: they describe what the run cost. A consumer comparing runs across artifacts (amoeba, cf) needs them without parsing the body. The keys follow the slice 265/266/927 convention: each is emitted only when it has a value.

| Key | Present when |
|---|---|
| `effort` | An effort was sent. |
| `turns` | The provider stamped it (openai), on success or failure. |
| `promptTokens`, `cachedTokens`, `completionTokens`, `reasoningTokens` | Individually, when summed to a non-None value. |
| `durationSeconds` | On every `review_client` result, and on a failure artifact whose error carries it. |

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

### D12 — Failure modes and their signals

Each new I/O path has its failure modes listed below, with the signal each one produces and a test that asserts it. The rule is that a failure logs at WARNING or above, and that no count degrades to 0 without saying so.

| Failure | Behavior | Signal | Test |
|---|---|---|---|
| **Request fails before or at stream start.** A connect timeout, a refused connection, or a 4xx/5xx makes the openai SDK raise `APITimeoutError`, `APIConnectionError`, or `APIStatusError` on some turn. | `handle_message`'s existing conversions produce `ProviderTimeoutError` / `ProviderError` / `ProviderAPIError`. An outer `except ProviderError` attaches a snapshot of `RunTelemetry` (turns and usage from the turns that completed) and re-raises. The same covers the iteration-guard `ProviderError`. | The exit WARNING (last row). The failure artifact carries `turns`, the token keys, and `durationSeconds`. | A stubbed stream raises on turn 3. Assert the error's `telemetry.turns == 2` with summed usage, and the rendered failure frontmatter. |
| **Stream fails mid-body.** The peer disconnects, the connection resets, or the read timeout fires between chunks. | Today this escapes unconverted, because `openai/_streaming.py` does not wrap errors raised while iterating (verified in openai 2.24.0): a raw `httpx.ReadTimeout` or `httpx.RemoteProtocolError` becomes a traceback and no artifact. This slice adds two conversions next to the existing ones: `httpx.TimeoutException` → `ProviderTimeoutError`, and `httpx.TransportError` → `ProviderError`. `httpx` is already a declared dependency. The outer handler then attaches telemetry as above. | The exit WARNING. A failure artifact with telemetry. | Stubbed streams that raise `httpx.ReadTimeout` and `httpx.RemoteProtocolError` mid-iteration: assert the converted type, the attached telemetry, and the artifact. |
| **Stream stalls** (the connection is open and no bytes arrive). | Bounded by the openai client's read timeout, which is the SDK default `Timeout(connect=5, read=600)`, since `AsyncOpenAI` is built without a timeout argument. After 600 s without a byte, `httpx.ReadTimeout` fires, which is the row above. A stream that keeps trickling bytes is not bounded, which is unchanged from today, and this slice does not add a per-turn deadline. | As above. | Covered by the `ReadTimeout` test above. |
| **Usage chunk never arrives.** The backend accepts `stream_options` but sends no usage chunk before `[DONE]`. | Nothing waits on the usage chunk. `async for chunk in stream` ends when the stream closes, whatever the last chunk carried, and usage is read opportunistically from whichever chunks have it. The turn completes normally with usage `None`. | The no-usage WARNING ("Backend sends no usage" row) once the call ends. | The "Backend sends no usage" test, which also asserts the turn's text and tool calls are intact. |
| **Any other exception** (a programming error, or cancellation). | Propagates unconverted, as today, and no artifact is written, because only a `ProviderError` reaches `save_provider_failure`. | The exit WARNING (last row) still fires, so the gathered telemetry reaches the log, which is the only record on this path. | A stubbed stream raises `RuntimeError` on turn 2: assert it propagates unchanged and the exit WARNING carries `turns=1`. |
| **Every non-normal exit** from `handle_message`. | A `completed` flag is set only on the normal return. `handle_message`'s existing `finally` logs when it is unset, so this covers every exit path without a broad `except`. | WARNING `"OpenAI agent ended without a final response after %d turn(s) (prompt=%s, cached=%s, completion=%s, reasoning=%s tokens)"`. | Asserted by the three failure tests above. |
| **Backend sends no usage at all** (no usage chunk on any turn). | Fields stay `None` and render `not reported` / absent. | One WARNING per `handle_message`: `"backend reported no token usage across %d turn(s); usage will not be recorded"`. It fires once per call, not per turn, so a backend that never reports is not noisy. | A stubbed stream with no usage chunk: assert the single WARNING and the `None` fields. |
| **Malformed usage detail** (a non-int token count, or a details object of the wrong type). | `read_chunk_usage` treats that field as `None`. The other fields are still read. Nothing raises, because a bad accounting frame must not fail a review that produced its answer. | WARNING naming the field and the raw value (truncated `%.200r`), once per `handle_message`. | Parametrized malformed shapes: assert the field is `None`, the siblings are intact, and the WARNING. |
| **Backend rejects `reasoning_effort` or `stream_options`** (400). | `ProviderAPIError`, and the failure artifact records it, which is today's path. | ERROR panel / failure artifact. | Covered by existing 4xx tests. For `stream_options`, see Risk Assessment. |
| **Batch hits the byte budget.** | Remaining paths get the `[not read: …]` line (D6). | WARNING in `read_file`: `"read_file: batch budget of %d bytes reached; %d path(s) not read"`. This follows the `list_files` cap precedent. | Assert the marker lines and the WARNING. |
| **Every file in a batch fails.** | `is_error=True`, counted in `failed_tool_calls`. | The existing INFO for an error result, plus `Tool calls failed` in the digest. | Assert `is_error` and the per-file errors inline. |
| **A read hangs** (a regular file on a stalled network mount). | Not bounded, which is today's single-read behavior. `reject_special_file` already rejects FIFOs and devices before any read, so the hang case is a regular file on stalled storage. A batch runs its reads sequentially inside the one `asyncio.to_thread` call, so a hang blocks that worker thread and that tool call, not the event loop. Batching does not add a new unbounded case; it runs at most the reads the model would otherwise spread over several turns. | None new. | None (unchanged behavior). |
| **Effort not appliable** (Codex), or **invalid alias value.** | Not sent, not recorded (D4, D1). | WARNING. | Assert the WARNING and the absent `effort` key. |

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

The existing keys are unchanged, except that `reasoning_chars` becomes the run total. New keys: `turns: int` and `usage: TokenUsage`.

**`ProviderError` additions**

`telemetry: RunTelemetry | None = None` and `duration_seconds: float | None = None`. Both are keyword-only and default to `None`, so existing raisers are unchanged.

## Integration Points

### Provides to Other Slices

- `Effort` and `model_effort()` give any future site that resolves an alias one reader.
- `core.usage` (`TokenUsage`, `RunTelemetry`) is the provider-neutral contract the SDK-usage follow-up plugs into.
- Usage fields in frontmatter and JSON give amoeba and metrology cost data per review. #159 (preloading) can measure its own effect against these fields.

### Consumes from Other Slices

- 924's alias-field and capability-flag pattern, and 927's per-chunk read in `_stream_turn`.
- `collect_turn` and `fold_empty_turn` (918/924). Their per-call summing extends to the new fields with no change to the recovery-turn logic.
- 195's provider-failure artifact, which gains the telemetry keys.

## Success Criteria

### Functional Requirements

1. An alias with `effort = "low"` sends `reasoning_effort="low"` on every turn of an OpenAI-compatible review, including tool-loop turns and the recovery turn.
2. The same alias on the SDK profile yields `ClaudeAgentOptions.effort="low"`. `effort = "none"` yields `thinking={"type": "disabled"}` and no `effort`.
3. On Codex, a set effort logs a WARNING and the artifact records no effort.
4. An invalid `effort` value logs a WARNING naming the alias and file, and nothing is sent.
5. No `effort` set gives request parameters identical to today, apart from `stream_options`.
6. `read_file` with `path` returns byte-identical output to today. With `paths` it returns headed sections in request order, per-file errors inline, and the batch-budget marker for files past `MAX_READ_BATCH_BYTES`. `is_error` is set only when every file failed. Both or neither of `path`/`paths` returns an error.
7. The tool-use guidance block contains the batching paragraph.
8. A review whose stream reports usage records summed prompt, cached, completion, and reasoning tokens and a turn count in frontmatter, digest, and JSON. `Reasoning characters` is the run total.
9. A backend that omits a usage field records it as `not reported` / null / absent key, never as 0.
10. An empty final turn still contributes its turns and usage to the capture (via `ProviderError.telemetry`).
11. Every `review_client` review records `durationSeconds`, including SDK and Codex runs.
12. A review that fails mid-loop writes a provider-failure artifact carrying the turns, usage, and duration gathered before the failure, and logs the D12 WARNING.
13. Each D12 failure mode with a listed signal emits it.

### Technical Requirements

- `ruff format`, `ruff check`, and `pyright` (strict) clean. The full test suite passes, with fixtures regenerated only where D10 says the output changes.
- Import greps in the task's verification step: `review/` has no import from `providers/openai`, and `core/usage.py` has no `squadron` import.
- `sends_stream_usage` tests:
  - A gemini-profile agent omits `stream_options`.
  - An openrouter-profile agent sends it.
  - An agent built without a profile (the server-route shape) sends it.
  - All six call sites produce the same credentials as `profile_credentials`.
- Unit tests:
  - alias parsing of `effort` (valid, invalid, bool, absent), parametrized
  - `ResolvedModel.effort` round-trip
  - the provider mappings (openai kwargs, SDK options, Codex warning)
  - `read_file` single, batch, mixed failure, all-fail, budget cutoff, oversize first file, and both/neither
  - the `MAX_READ_BATCH_BYTES` vs floor invariant
  - usage-chunk parsing for the OpenAI/Ollama (no choices) and OpenRouter (one empty choice) shapes
  - summing across a three-turn loop plus the recovery turn
  - `None`-preserving sums
  - every row of the D12 table that names a test, each asserting its signal with `caplog`
  - frontmatter, digest, and JSON rendering agreeing from one `ReviewResult`, and from one failed `ProviderError`

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

7. **Every built-in OpenAI-compatible profile accepts the new request.** Run one short review per profile: `openrouter` (steps 2–3), `local` (with Ollama running, using an alias on the `local` profile), `openai`, and `gemini` (`--model gemini-flash`). Each completes. `local` shows prompt and completion tokens and `Reasoning tokens` `not reported`, matching the Interfaces table. `gemini`'s profile does not send `stream_options`, so it records only the usage the backend sends unasked. If it sends none, every token field shows `not reported` and the D12 no-usage WARNING is logged. Its request is byte-for-byte today's apart from `reasoning_effort` when an effort is set.

8. **Mid-loop failure is recorded.** Run a review against the `local` profile and stop Ollama (`ollama stop` / quit the app) once the first tool call appears at `-v`. The failure artifact has `providerFailure: true`, `turns` ≥ 1, `durationSeconds`, and the `## Provider Failure` section, and the D12 WARNING is logged.

9. **Codex refuses loudly.** Define an alias on the `openai-oauth` profile with `effort = "low"` and run a review. A WARNING says effort cannot be applied, and the artifact has no `effort` key.

10. **Invalid value.** Set `effort = "extreme"` on the test alias. Any `sq` command that loads aliases logs the skip WARNING naming the alias and file.

## Risk Assessment

### Technical Risks

- **A backend that rejects `stream_options`.** `stream_options` now goes on OpenAI-compatible requests, including those with no effort set. A backend that rejects it would fail every request, where today it succeeds.
  - Three of the four built-in profiles are settled (Interfaces table): openai and openrouter by docs, local/Ollama by docs and a live probe.
  - Gemini does not document the parameter. Every live probe on 20260928 returned 503 or 429, which says nothing about the parameter.

### Mitigation Strategies

- **Gemini ships unchanged instead of gating the merge.** The gemini built-in profile sets `sends_stream_usage = False`, so its requests stay exactly as today. Nothing in the slice depends on the Gemini answer, and no part waits on it.
  - The cost is that Gemini reviews record usage only if the backend sends it unasked. The D12 WARNING makes that visible.
  - Turning it on is a one-line change in `BUILT_IN_PROFILES` once a probe succeeds. A follow-up issue tracks it and records the probe command: one `curl` with `stream_options` and `reasoning_effort="low"` against `gemini-3.8-flash`.
  - This is a declared per-profile field, not string dispatch on the profile name.
- **User-defined profiles** on other OpenAI-compatible backends default to sending the parameter, because that is the OpenAI spec's behavior. If a backend rejects it, the failure is a loud 400 (D12) naming it, and the fix is `sends_stream_usage = false` in the user's profile table. That needs no code change.

## Implementation Notes

### Development Approach

Order: **C → B → A**. Usage first, so B and A are measured, not guessed. Each part ends at a green, separately revertible commit. B and A touch none of each other's code.

1. **C:**
   - `core/usage.py` (move `add_optional` first, with `turn_capture`'s existing tests as the guard), then `providers/openai/usage.py`
   - `profile_credentials` and `sends_stream_usage` (gemini False), switching the six call sites
   - `_stream_turn` reads usage and sends `stream_options` per the flag
   - loop accumulation and stamping
   - `ProviderError.telemetry`/`duration_seconds` and the failure-artifact rendering
   - the D12 WARNINGs
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
   - live runs: walkthrough steps 3–10
4. File the three follow-up issues (Codex effort, SDK usage, enabling `sends_stream_usage` on gemini once a probe succeeds), and comment the D2 decision on #154.

Tests use stubbed `AsyncStream`s for the chunk shapes, the way slice 927's `chunk.model` tests do. No live calls run in the suite.

### Special Considerations

- `_stream_turn` runs inside the event loop. Reading usage is attribute access and a few dict lookups per chunk, well under the 1 ms rule. `read_file` batches keep every blocking read inside the one existing `asyncio.to_thread` call, so a batch is one worker hop, not N, and a hung read never blocks the event loop (D12).
- The `add_optional` move must not change `turn_capture`'s behavior. Its existing tests are the guard.
- `answering_models` and usage are both read from choice-less chunks. Read them in the same spot so the next field added there has one obvious home.
- `providers/openai/agent.py` is 630 lines, over the 300-line guideline. The usage reader goes in its own module rather than growing the agent, and the attach-telemetry wrapper stays a few lines. Splitting the agent itself is out of scope.
- There are no initiative-level NFRs to restate. The event-loop constraint above is the one NFR this slice has.
