---
docType: slice-design
project: squadron
slice: 262-slice.openaicompatibleagent-agentic-loop
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261]
interfaces: [263, 264, 265, 266]
dateCreated: 20260827
dateUpdated: 20260829
status: complete
---

# Slice Design: OpenAICompatibleAgent Agentic Loop

## Parent Documents

- Architecture: `260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
- Slice Plan: `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`, entry 2

## Overview

Slice 261 shipped tools that nothing consumes. This slice makes `OpenAICompatibleAgent`
consume them: it replaces the single API round-trip in `handle_message` with an agentic loop
that passes tool schemas to the model, executes returned tool calls against the slice-261
registry, accumulates the OpenAI-protocol message history across turns, and re-invokes until
the model returns an assistant message with no `tool_calls`.

The loop is gated entirely by `AgentConfig.allowed_tools`. With no tools configured — every
caller today — the agent takes a path that is byte-for-byte the current behavior, including
the existing "tool call surfaced as a system Message" case. After this slice, the agent uses
tools **when given them**, but no pipeline YAML yet declares them (263) and the review path
still declares Claude-vocabulary names it cannot use (265). Default-path behavior is
unchanged.

Two structural gaps in the current code must close here, and they are the real work of the
slice: the agent constructor never receives `allowed_tools` or `cwd` (they stop at
`OpenAICompatibleProvider.create_agent`), and `_call_api` both performs I/O and builds
caller-facing Messages, which a loop cannot reuse as-is.

## Value

This is the slice where the initiative's premise becomes true: a capable non-SDK model can
actually write a file. 261 was enablement with no observable effect; 263 and 265 are wiring
onto this loop. Everything downstream — pipeline `allowed_tools`, review file-access (issue
#68), the MCP bridge, `--no-tools` comparison runs — consumes the loop built here.

It is also the seam the future orchestration initiative lifts: `_run_agentic_loop` is
deliberately a single named private method with no executor-visible surface, so a later layer
can intercept it without re-shaping the `Agent` protocol.

## Technical Scope

**In scope**

- `AgentConfig.allowed_tools` and `cwd` threaded from `OpenAICompatibleProvider.create_agent`
  into `OpenAICompatibleAgent.__init__`.
- `_run_agentic_loop` inside `handle_message`: schema materialization, multi-turn history
  accumulation, tool execution, termination conditions.
- Refactor of `_call_api` into a reusable single-turn primitive that returns raw turn data
  rather than caller-facing Messages.
- Tool-schema construction from `ToolDescriptor` into OpenAI `tools[]` shape.
- OpenAI-protocol message construction (assistant-with-`tool_calls`, `role: "tool"` results),
  placed in `translation.py`.
- Three termination conditions: no `tool_calls`, `max_iterations`, history-size budget.
- Per-tool-call error surfacing back to the model (malformed JSON args, unknown tool,
  executor failure).
- Unknown-name tolerance at materialization time (see D1) — required so non-SDK reviews
  degrade predictably rather than crashing before 265 lands.
- Logging contract for loop visibility (DEBUG per call, INFO summary, WARNING for guards).

**Out of scope**

- Pipeline YAML surface and `dispatch` wiring — slice 263.
- Review injection-skip logic, `list_files`/`grep`, template vocabulary migration — slice 265.
- `tool_use` capability field and `--no-tools` — slice 266.
- MCP-bridged tools — slice 264.
- Streaming intermediate turns to the caller. Final turn only (arch §Streaming contract).
- History truncation/summarization. The budget guard returns an error to the model instead.
- Any `ClaudeSDKAgent` or `CodexAgent` change.

## Architecture

### Current shape and why it cannot host a loop

`handle_message` appends the user message to `self._history`, calls `_call_api()` once, and
yields the resulting Messages. `_call_api` does three things at once: issues the streaming
request, aggregates deltas, and calls `translation.build_messages` to produce caller-facing
`Message` objects. A loop needs turns 1..n-1 aggregated but *not* translated, and only turn n
translated. So `_call_api` splits:

```
_call_api()                  # today: request + aggregate + translate + append history
  ->  _stream_turn(messages, tools) -> TurnResult(text, tool_calls)   # request + aggregate only
```

`_stream_turn` is the single-turn primitive. Both the no-tools path and every loop iteration
call it. The delta-aggregation logic moves into it unchanged — it is already correct and
already handles multi-chunk tool-call assembly.

### Control flow

```
handle_message(message)
  append {"role": "user", ...} to self._history
  if not self._tool_executors:          # no tools configured -> today's behavior exactly
      turn = await _stream_turn(history, tools=None)
      append assistant turn to history
      yield *translation.build_messages(turn.text, turn.tool_calls, ...)
  else:
      yield *await _run_agentic_loop()

_run_agentic_loop() -> list[Message]
  for iteration in 1..max_iterations:
      turn = await _stream_turn(self._history, tools=self._tool_schemas)
      append assistant turn to self._history        # verbatim, content + tool_calls
      if not turn.tool_calls:
          return translation.build_messages(turn.text, [], ...)   # FINAL — only yield point
      for tc in turn.tool_calls:                    # in order
          result = await _execute_tool_call(tc)
          append {"role": "tool", "tool_call_id": tc.id, "content": result.content}
      if _history_chars() > max_history_chars:      # read once, before the loop
          append budget-exceeded tool message ... (see Budget guard)
  return max-iterations error            # structured, via normal failure path
```

Only one `return` translates a turn into caller Messages: the no-`tool_calls` exit. That is
what makes "intermediate turns are not yielded" structurally true rather than a convention a
future edit can break.

### Where state lives

`allowed_tools` and `cwd` are resolved **once, at construction**, not per message:

- `OpenAICompatibleProvider.create_agent` passes `config.allowed_tools` and `config.cwd` to
  the constructor.
- The constructor calls `registry.materialize(names, cwd)` once and stores
  `self._tool_executors: dict[str, ToolExecutor]` plus `self._tool_schemas: list[dict]`.

Rationale: `materialize` is the slice-261 contract for binding `cwd` to executors, and the
agent's `cwd` cannot change during its lifetime. Materializing per-message would repeat
filesystem resolution on every turn for no gain. An agent with empty/None `allowed_tools`
holds an empty executor dict, which is the flag the no-tools branch tests.

### cwd resolution

`AgentConfig.cwd` is `None` on the dispatch path today (`dispatch.py:63` hardcodes it) and
set on the review path. The loop needs a jail root, and a silent wrong default is the failure
mode the project rules forbid.

**Decision (revised 20260828 — review F002):** when `allowed_tools` resolves to a non-empty
tool set and `cwd` is `None`, **raise `ProviderError`** at agent construction. There is no
default jail root.

The original decision here was to fall back to `Path.cwd()` with an INFO log, defended as
"explicit and observable." That defense was wrong. `cwd` is the trust boundary for `write_file`
and `bash` (arch §CWD as the trust boundary), and the project rule is "never use silent
fallback values" — logging a fallback does not stop it from being one. A caller that asks for
write-capable tools without saying where they may write has a configuration defect, and the
correct response is to refuse, not to guess the process working directory and write into
whatever tree the process happens to be running from.

Reachability today (verified, not assumed): `dispatch.py:63` sets `cwd=None` but never sets
`allowed_tools`, so it materializes no tools and never reaches this check.
`review_client.py:116` and `metrology/audit.py:621` both set `cwd`. So no current caller trips
the raise; it exists to keep a future one — a partial 263 rollout, a new integration, a test
harness — from silently escaping the jail.

When `allowed_tools` is empty or `None`, `cwd` is not consulted at all and no error is raised;
that is the path every caller takes today.

### Tool schema construction

`ToolDescriptor` already carries OpenAI-shaped `parameters`. Schema construction is a pure
mapping and belongs next to the other OpenAI-shape helpers in `translation.py`:

```python
{"type": "function",
 "function": {"name": d.name, "description": d.description, "parameters": d.parameters}}
```

Built once at construction from the same descriptor lookups `materialize` uses.

### Message-history shape (OpenAI protocol)

Two constructors, both in `translation.py`, so the protocol shape lives in one place
(arch §Message history shape):

- `build_assistant_history_entry(text, tool_calls)` — the existing
  `_append_assistant_history` logic, moved. `content` is `None` when empty and `tool_calls`
  are present; `tool_calls` is included verbatim as assembled from the stream.
- `build_tool_result_entry(tool_call_id, content)` -> `{"role": "tool", "tool_call_id": ...,
  "content": ...}`.

**Append-only invariant.** The loop never mutates an existing history entry — no re-rendered
content, no injected timestamps, no rewritten system prompt. Each request is therefore a
strict prefix-extension of the previous one, which is what provider-side automatic prefix
caching matches (arch §Cache-friendly history). This is a correctness-of-cost property, and
it is asserted by test, not just by convention: a test captures the `messages` argument of
each successive `create()` call and asserts call N+1's list starts with call N's list.

### Termination conditions

| Condition | Detection | Result |
|---|---|---|
| Normal | assistant message has no `tool_calls` | final `content` yielded as Messages |
| Max iterations | loop counter reaches `max_iterations` | `ProviderError` via normal failure path; WARNING logged |
| History budget | accumulated history chars > threshold | budget-exceeded `role: "tool"` message appended; loop continues so the model can finalize; WARNING logged once |

Max-iterations raises rather than returning a partial response, because a loop that hit 20
turns without finalizing produced no answer — returning its last intermediate text would be
a plausible-looking non-answer. `ProviderError` is what `handle_message` already surfaces to
the executor, so no new failure channel is introduced.

The budget guard is deliberately *not* a termination: it appends one extra tool-result
message telling the model the budget is exhausted and it must finalize now. If the model
ignores that and keeps calling tools, `max_iterations` still terminates the loop. The guard
fires at most once per loop to avoid appending a message per iteration.

### Loop limits (configurable)

Both loop limits are **config keys**, not hard-coded constants, following the established
`review.max_file_size_bytes` precedent (`config/keys.py`, read via `get_typed_config`):

| Key | Type | Default | Meaning |
|---|---|---|---|
| `agent.max_tool_iterations` | int | 20 | Max loop turns before the guard fires (arch §Loop iteration cost) |
| `agent.max_history_chars` | int | 400_000 | Accumulated history size that triggers the budget guard |

Rationale: these are operational caps whose right value varies by model context window and by
user, and non-SDK reviews run frequently against models with very different windows. A value
baked into source would eventually need a code edit to change. Registering them in
`CONFIG_KEYS` keeps exactly one definition per value (the `default=` field) with no magic
number at any use site, and gives users `sq config set` without a later retrofit.

Both are read **once at loop start**, not per iteration, and held as locals — so a mid-run
config change cannot alter a loop's termination behavior halfway through. Read via
`get_typed_config(key, int, cwd=...)`, which raises on a type mismatch rather than silently
coercing.

The `400_000` default is an unmeasured starting value (arch notes a typical loop finishes in
2–5 turns, so it should rarely fire). Configurability is what makes an unmeasured default
acceptable rather than a guess baked into source.

This does not overlap slice 266, which adds the orthogonal `tool_use` model-capability field
and the `--no-tools` run flag — those govern *whether* tools are offered, not how long the
loop may run.

### Error surfacing inside the loop

Per arch §Tool argument validation, a bad tool call is data for the model, not a crash:

| Failure | Handling |
|---|---|
| `arguments` is not valid JSON | `role: "tool"` result, error text naming the parse failure |
| tool name not in `self._tool_executors` | `role: "tool"` result listing the allowed names |
| executor returns `is_error=True` | passed through verbatim — the tool owns its message |
| executor raises | caught, logged via `logger.exception`, converted to an error tool result |

Executors returning `ToolResult(is_error=True)` is the slice-261 contract; the "executor
raises" row is defense against a future or MCP-bridged tool that violates it, and is the only
place the loop logs at ERROR.

Every branch produces exactly one `role: "tool"` message per `tool_call_id`. This is a
protocol requirement — a missing tool result for an issued call id makes the next request
malformed — and is asserted directly by test.

### D1: unknown tool names must not crash the loop

`registry.materialize` raises `ToolNotRegisteredError` on an unknown name. The review path
already passes `template.allowed_tools` into `AgentConfig`, and every shipped template
declares Claude vocabulary (`[Read, Glob, Grep, Bash]` in `code.yaml`, `[Read, Glob, Grep]`
in the other six). Vocabulary migration is slice 265. So the moment this slice activates the
non-SDK consumer of `allowed_tools`, a non-SDK review would call `materialize(["Read", ...])`
and raise — turning a working (if tool-less) review into a hard failure.

**Decision:** the agent filters names through `registry.lookup` before materializing.
Unknown names are dropped with a **WARNING** naming each dropped name and the registered
vocabulary; known names materialize normally. `materialize` itself is unchanged — its
fail-fast contract is right for a caller that controls its own name list.

This is not a silent fallback: it is loud, observable, and the surviving behavior (a review
with no tools) is exactly today's behavior. The alternative — crashing every non-SDK review
until 265 lands — makes 262 un-shippable on its own and violates the slice-plan requirement
that each slice leave the system in a working state. Load-time validation of declared names
belongs where names are declared: pipeline YAML (263) and templates (265).

Consequence to accept knowingly: between 262 and 265, a non-SDK review logs a WARNING and
runs tool-less. That is issue #68's current behavior plus a diagnostic, and 265 closes it.

### Logging contract

Asserted by `caplog` tests, following the 261 precedent:

| Level | Event |
|---|---|
| DEBUG | each successful tool call (name, args) and its result (truncated), each iteration boundary |
| INFO | per-loop summary on exit: iterations used, tool-call count |
| WARNING | **malformed JSON in `arguments`**; **model named a tool not in the allowed set**; dropped unknown declared names (D1); budget guard fired; max-iterations reached |
| ERROR | executor raised (via `logger.exception`) |

**Revised 20260828 (review F001).** The two bolded rows were originally DEBUG, folded in with
routine per-call logging. They are protocol violations by the model, they originate in
loop code written by this slice, and `.claude/rules/review-code.md` (Failure-Mode Enumeration)
requires every identified failure mode to be observable at WARNING+ or by metric — DEBUG does
not meet that bar. The asymmetry was real and verified: the slice-261 tool layer already logs
path-escape at WARNING ([builtin.py:76](src/squadron/tools/builtin.py#L76)) and bash timeout at
WARNING ([builtin.py:308](src/squadron/tools/builtin.py#L308)), so the loop calling those tools
would have been quieter than the tools themselves.

These stay non-fatal — they still return an error tool result so the model can correct itself
(arch §Tool argument validation). WARNING reflects that a turn was wasted on a malformed call,
which is exactly what a user debugging a bad model needs to see without `-vv`.

Intermediate turn *content* remains DEBUG only — that is the observability substitute for not
streaming intermediate turns (arch §Loop visibility).

## Implementation Details

Files changed:

| File | Change |
|---|---|
| `providers/openai/agent.py` | constructor params; `_stream_turn` split; `_run_agentic_loop`; `_execute_tool_call` |
| `providers/openai/translation.py` | `build_tool_schemas`, `build_assistant_history_entry`, `build_tool_result_entry` |
| `config/keys.py` | register `agent.max_tool_iterations`, `agent.max_history_chars` |
| `providers/openai/provider.py` | pass `config.allowed_tools` and `config.cwd` to the agent |

`agent.py` is 141 lines today; the loop and its helper add roughly 100, keeping it inside the
~300-line project guideline. Keeping the loop in `agent.py` (rather than a new module) is
deliberate — arch §Design Goals calls for it to live inside `handle_message` behind a clean
caller boundary, as a clearly named private method that a future orchestration layer lifts.

`TurnResult` is a small frozen dataclass (`text: str`, `tool_calls: list[dict]`) defined in
`agent.py`. It is internal plumbing between two private methods, not part of any protocol.

**Constructor signature.** New parameters are keyword-only with defaults
(`allowed_tools: list[str] | None = None`, `cwd: str | None = None`), so the existing
test-helper construction and any other caller keep working unchanged. Registration side
effects require `squadron.tools` to be imported for the built-ins to exist in the registry;
the agent imports the registry module, which does not itself trigger `builtin` registration —
so the agent must import `squadron.tools` (the package `__init__`, which performs the
registration import) to guarantee the built-ins are present.

## Integration Points

**Consumes (slice 261):** `registry.lookup`, `registry.materialize`, `ToolDescriptor`,
`ToolResult`, `ToolExecutor`. No change to any of them. `ToolNotRegisteredError` becomes
unreachable from this caller because of the D1 pre-filter, which is intentional.

**Provides:**

- *263* — a working non-SDK tool loop keyed off `AgentConfig.allowed_tools`; 263 only has to
  populate that field (and `cwd`) from step YAML.
- *265* — the same activation for the review path; 265 adds injection-skip and vocabulary
  migration, and its migration is what makes D1's WARNING stop firing.
- *266* — the effective-tool-set computation intersects into `allowed_tools` upstream of the
  agent; no agent change needed.
- *264* — MCP-bridged descriptors execute through `_execute_tool_call` unchanged, because the
  loop depends only on the `ToolExecutor` alias.

**Unchanged:** `Agent` protocol, executor, `ClaudeSDKAgent`, `CodexAgent`,
`ProviderCapabilities` (the `supports_tool_use` signal is 265's decision), pipeline schema.

## Success Criteria

- [ ] With `allowed_tools` empty or `None`, agent behavior is unchanged: existing
      `tests/providers/openai/` suite passes without modification, including
      `test_handle_message_yields_system_for_tool_call`.
- [ ] `OpenAICompatibleProvider.create_agent` threads `config.allowed_tools` and `config.cwd`
      into the agent.
- [ ] Tool schemas are sent as the `tools` parameter only when tools are configured; never
      otherwise (asserted on the captured `create()` kwargs).
- [ ] An assistant turn with `tool_calls` continues the loop; a turn without them terminates
      it and its content is the yielded response.
- [ ] Intermediate turn content is never yielded to the caller.
- [ ] A multi-tool single turn dispatches every call and appends one `role: "tool"` result per
      `tool_call_id`, in call order.
- [ ] Malformed JSON arguments produce an error tool result, not an exception; the loop
      continues; **a WARNING is logged** (asserted via `caplog`).
- [ ] An unknown tool name in a model response produces an error tool result naming the
      allowed tools; the loop continues; **a WARNING is logged** (asserted via `caplog`).
- [ ] Constructing an agent with a non-empty tool set and `cwd=None` raises `ProviderError`;
      constructing with an empty tool set and `cwd=None` does not.
- [ ] Unknown names in `allowed_tools` are dropped with a WARNING; known names still
      materialize (D1).
- [ ] `agent.max_tool_iterations` fires a `ProviderError` through the normal failure path with
      a WARNING.
- [ ] The history budget guard appends a budget-exceeded tool message once and logs WARNING.
- [ ] Both loop limits are registered config keys read via `get_typed_config`, honoring a
      user-set value and falling back to the registered default.
- [ ] History is append-only: each request's `messages` is a strict prefix-extension of the
      previous request's.
- [ ] Full suite passes (~3078 tests, no regression); `ruff check` clean;
      `pyright src/squadron/providers/openai/` clean.

## Design Decisions

- **D1 — unknown names are dropped, not fatal.** Recorded above. Driven by the shipped
  templates' Claude vocabulary and the requirement that 262 ship independently.
- **D2 — materialize once at construction, not per message.** `cwd` is fixed for an agent's
  lifetime; per-message materialization repeats path resolution for no benefit.
- **D3 — max-iterations raises rather than returning partial text.** A partial intermediate
  turn is a plausible-looking non-answer; the project rule against silent fallbacks applies.
- **D4 — budget guard warns and continues rather than terminating.** It gives the model one
  chance to finalize; `max_iterations` remains the hard stop. Truncation is out of scope.
- **D8 — no `cwd` fallback; refuse instead.** Revised 20260828 (review F002). A non-empty tool
  set with `cwd=None` raises `ProviderError` at construction. Supersedes the original
  `Path.cwd()`-with-INFO-log decision, which was a silent fallback wearing a log line. No
  current caller trips it (verified: dispatch sets no tools; review and audit both set `cwd`).
- **D9 — model protocol violations log at WARNING.** Revised 20260828 (review F001). Malformed
  tool-call JSON and unknown tool names in model responses are WARNING, not DEBUG, matching the
  slice-261 tool layer and the Failure-Mode Enumeration rule. They remain non-fatal.
- **D7 — loop limits are config keys, not source constants.** Revised 20260827 after review.
  Both caps follow the `review.max_file_size_bytes` precedent. Non-SDK reviews run frequently
  against models with widely differing context windows; a source-baked cap would require a
  code edit to tune. Read once at loop start so a mid-run change cannot alter termination
  behavior.
- **D5 — protocol message construction lives in `translation.py`.** One home for OpenAI wire
  shapes prevents drift between the assistant-entry and tool-result builders.
- **D6 — loop stays in `agent.py` as a named private method.** Matches arch §Design Goals and
  keeps the future orchestration seam explicit.

## Risks

- **Tool-call protocol fidelity across providers.** Some OpenAI-compatible endpoints emit
  non-standard tool-call shapes. Mitigation: the "tools requested but model returned plain
  text" case is treated as a normal final response (arch §Provider-side support varies); no
  coercion is attempted. Tests cover the graceful path.
- **Multi-chunk tool-call aggregation.** Already implemented and tested in the current
  `_call_api`; the refactor moves it verbatim into `_stream_turn` rather than rewriting it.

## Verification Walkthrough

Run from the project root. `ruff`/`pyright`/`pytest` are not on PATH; invoke from `.venv/bin/`.
Commands and output below are real, captured at close-out on commit `dbb7549`.

**1. No-tools path is untouched.** The strongest regression signal is the pre-existing suite
passing unmodified, plus the new loop/constructor/tool-execution tests alongside it:

```bash
.venv/bin/pytest tests/providers/openai/ -q
```

```
........................................................................ [100%]
72 passed in 0.52s
```

The original 15 `test_agent.py` tests (including
`test_handle_message_yields_system_for_tool_call`) are unmodified and pass; 57 further tests
cover Tasks 2–6.

**2–3. Loop drives a real tool against a real filesystem; intermediate turns are not
surfaced.** `TestAgenticLoop.test_normal_termination_suppresses_intermediate_turn`
(`tests/providers/openai/test_agentic_loop.py`) scripts a `write_file` tool call on turn 1 and
plain text on turn 2 against a real temp directory (via the real slice-261 registry, not a
mock), then asserts: exactly 2 `create()` calls; the yielded Messages contain only turn 2's
text; no `MessageType.system` tool-call Message is emitted; the file exists on disk with the
expected content. Included in the 72 passing above.

**4. Error paths return to the model rather than crashing, and are observable (D9).**
`TestExecuteToolCall` (5 cases: malformed JSON, unknown tool, executor error-result,
executor-raises, success) asserts both the returned tool-result content and the `caplog`
level for each branch. Included in the 72 passing above.

**4a. A tool set with no jail root is refused (D8).**

```bash
.venv/bin/pytest tests/providers/openai/test_agentic_loop.py -q -k cwd
```

```
.....                                                                    [100%]
5 passed, 16 deselected in 0.02s
```

Covers: no tools + no `cwd` doesn't raise; a known tool + no `cwd` raises `ProviderError`;
requesting only unknown names + no `cwd` also raises (Constraint 3 — the check is against the
*requested* set, not the post-filter one).

**5. Guards fire, using the real config path.**

```bash
.venv/bin/pytest tests/providers/openai/test_agentic_loop.py -q -k max_iterations
```

```
.                                                                        [100%]
1 passed, 20 deselected in 0.34s
```

```bash
.venv/bin/pytest tests/providers/openai/test_agentic_loop.py -q -k budget
```

```
.                                                                        [100%]
1 passed, 20 deselected in 0.34s
```

Both tests set the config key via `set_config` against a real temp-dir `.squadron.toml` (the
`patch_config_paths` fixture), not a monkeypatched module attribute — proving the keys are
actually wired through `get_typed_config`. The history-budget test additionally asserts that
once the guard fires, no `tools` kwarg is sent on the following `create()` call (a slice-review
fix: the notice is a plain `user`-role message, not a fake `role: "tool"` entry with an empty
`tool_call_id`, and tool schemas are withdrawn so the model cannot simply ignore the notice and
keep calling tools).

**6. Cache-friendly prefix.** `test_append_only_history_is_strict_prefix_extension` snapshots
each `create()` call's `messages` (deep-copied at call time, since the mock otherwise captures
a reference into the same growing list) and asserts every successive call's list is a strict
prefix-extension of the previous one. Included in the 72 passing above.

**7. Unknown declared names degrade loudly (D1).**
`test_mixed_known_and_unknown_drops_unknown_with_one_warning` constructs an agent with
`allowed_tools=["Read", "read_file"]`; asserts `read_file` is materialized, `Read` is dropped,
and exactly one WARNING naming `Read` is logged. Included in the 72 passing above.

**8. Full-suite and static checks.**

```bash
.venv/bin/pytest -q
```

```
3115 passed, 2 skipped, 3 warnings in 430.59s (0:07:10)
```

(Design baseline was ~3078 passed, 2 skipped, prior to this slice's additions; the delta is
this slice's new tests. The suite takes ~7 minutes end-to-end because
`tests/metrology/test_audit_cli.py`'s variance-series tests sleep for real against
`metrology.audit_run_cooldown_s` — pre-existing, unrelated to this slice. The 3 warnings are
pre-existing `coroutine ... was never awaited` `RuntimeWarning`s in
`tests/cli/commands/test_run.py` / `test_run_pipeline_lazy.py`, also unrelated.)

```bash
.venv/bin/ruff check .
```

```
All checks passed!
```

```bash
.venv/bin/pyright src/squadron/providers/openai/
.venv/bin/pyright src/squadron/config/
```

Both report errors — **known and pre-existing, not introduced by this slice.** The `openai`
and `pydantic_settings`/`tomli_w` packages' type stubs are not resolving in this project's
pyright/venv configuration; every symbol imported from them type-checks as `Unknown`, cascading
into every file that touches them. Verified via `git stash` before any slice-262 change: `main`
already reported 72 errors on `src/squadron/providers/openai/` and equivalent counts in
`config/`. `src/squadron/config/keys.py` — the only file this slice changed in `config/` — is
independently clean (`pyright src/squadron/config/keys.py` → 0 errors). This baseline issue was
raised to and explicitly accepted by the Project Manager as out of scope for slice 262; fixing
the stub-resolution problem project-wide is a separate task.

Do **not** run whole-repo `pyright` as a pass/fail gate — it reports a large pre-existing error
count unrelated to this work, for the same reason (261 precedent).

**9. Live smoke (optional, requires credentials).** A non-SDK review against a tool-capable
model, run at `-vv`, shows the DEBUG tool-call lines and the INFO loop summary. Until slice
265 migrates template vocabulary, this run logs the D1 WARNING and proceeds tool-less — that
is the expected intermediate state, not a defect. Not run at close-out (no live credentials in
this environment); the mocked-endpoint tests above are the verified substitute.

### Known follow-ups (not fixed in this slice)

Raised by a multi-agent code review of the branch diff at close-out; verified against the
actual code, triaged with the Project Manager, and deliberately deferred rather than expanded
into this slice's scope:

- `get_typed_config` can raise a bare `ValueError` on a misconfigured (non-integer)
  `agent.max_tool_iterations`/`agent.max_history_chars` value; nothing between
  `_run_agentic_loop` and `handle_message`'s `except` clauses catches it, so it would propagate
  uncaught instead of surfacing as a `ProviderError`.
- Multiple tool calls within a single turn are awaited sequentially in `_run_agentic_loop`
  rather than concurrently (`asyncio.gather`) — correct today, but leaves wall-clock
  performance on the table for multi-tool turns.
- `_execute_tool_call` builds ad hoc `f"Error: ..."` strings for the malformed-JSON and
  unknown-tool branches instead of reusing the `ToolResult`/`_error` convention already
  established in `tools/builtin.py`.
- `tool_call.get("id", "")` silently substitutes an empty string if a streamed tool call from
  the model itself (not the budget guard, which no longer does this) never carries an `id`.
  Low-likelihood (most OpenAI-compatible backends send `id` on the first chunk), unobserved
  today, and not covered by a test.
- `agent.max_tool_iterations` set to `0` skips the loop body entirely (`range(0)`) and raises
  `ProviderError` with a message implying iterations were attempted, when zero API calls were
  made. Undocumented, untested edge case.
- The `AgentConfig.allowed_tools`/`cwd` vocabulary mismatch between SDK-style names (`Read`,
  `Bash`) and this slice's registry names (`read_file`, `bash`) is **not** a new finding — it
  is D1, already documented and accepted as the expected state until slice 265 migrates
  template vocabulary.
