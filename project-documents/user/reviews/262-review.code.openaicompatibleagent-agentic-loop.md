---
docType: review
layer: project
reviewType: code
slice: openaicompatibleagent-agentic-loop
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md
aiModel: claude-opus-5
status: complete
dateCreated: 20260830
dateUpdated: 20260830
reviewedSha: 7d49d58678a18f91013efcee585dc0817437285f
findings:
  - id: F001
    severity: concern
    category: performance
    summary: "History budget guard re-stringifies the entire history every iteration, on the event loop"
    location: "src/squadron/providers/openai/agent.py:348-350"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Id-less tool call is logged but not surfaced; the loop executes the tool and sends poisoned history anyway"
    location: "src/squadron/providers/openai/agent.py:304-316"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Cancellation mid-tool-execution leaves an unmatched `tool_calls` entry that silently poisons the agent"
    location: "src/squadron/providers/openai/agent.py:293-316"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Agentic loop has no wall-clock deadline — only iteration and character bounds"
    location: "src/squadron/providers/openai/agent.py:292"
  - id: F005
    severity: concern
    category: fail-fast
    summary: "Loop bounds are not validated; a non-positive value fails confusingly on every turn"
    location: "src/squadron/providers/openai/provider.py:59-66"
  - id: F006
    severity: note
    category: dead-code
    summary: "`self._cwd` is stored but never read by production code"
    location: "src/squadron/providers/openai/agent.py:78"
  - id: F007
    severity: note
    category: simplification
    summary: "`tools.lookup()` is called twice per requested tool name"
    location: "src/squadron/providers/openai/agent.py:107-118"
  - id: F008
    severity: note
    category: documentation
    summary: "Provider comment overstates where config I/O moved to"
    location: "src/squadron/providers/openai/provider.py:57-58"
  - id: F009
    severity: note
    category: test-coverage
    summary: "No load-test coverage for a new network + concurrency path"
    location: "tests"
  - id: F010
    severity: pass
    category: error-handling
    summary: "Tool-failure surfacing is thorough and well-tested"
    location: "src/squadron/providers/openai/agent.py#_execute_tool_call"
  - id: F011
    severity: pass
    category: correctness
    summary: "Budget-guard notice correctly uses a user-role message, not a synthetic tool result"
    location: "src/squadron/providers/openai/agent.py:326-336"
  - id: F012
    severity: pass
    category: design
    summary: "Wire-shape builders correctly centralized in translation.py"
    location: "src/squadron/providers/openai/translation.py:72-108"
---

# Review: code — slice 262

**Verdict:** CONCERNS
**Model:** claude-opus-5

## Findings

### [CONCERN] History budget guard re-stringifies the entire history every iteration, on the event loop

`_history_chars()` computes `sum(len(str(entry)) for entry in self._history)` and is called once per loop iteration from `_run_agentic_loop` (agent.py:318). This is synchronous, CPU-bound work inside an `async def`, and it is O(n²) across the loop: at the default `max_history_chars=400_000` the final iterations each build ~400KB of `repr()` output that is immediately discarded, and the whole scan repeats up to `max_tool_iterations` times. The project Python rule is explicit — "Any async def function that calls synchronous code must guarantee that the synchronous code runs in <1ms in the worst case." A 400KB `str()` of nested dicts does not meet that bound, and `max_history_chars` is user-configurable upward with no ceiling.

Failure scenario: an agent configured with `agent.max_history_chars = 4_000_000` and a `read_file` loop pulling 256KB chunks stalls the event loop for tens of milliseconds per iteration, blocking every other coroutine in the process (other agents' streams, the server's request handling).

Fix: maintain a running counter incremented at each `self._history.append(...)` site rather than rescanning. That also makes the metric stable — the current `str(entry)` measure counts dict-repr punctuation and key names, so `max_history_chars` does not actually mean "characters of history."

### [CONCERN] Id-less tool call is logged but not surfaced; the loop executes the tool and sends poisoned history anyway

The comment at agent.py:306-310 states the intent: "surface it here rather than as an opaque API error several turns later." The code does not do that. It emits a WARNING and then falls through to `await self._execute_tool_call(tool_call)` and appends `{"role": "tool", "tool_call_id": "", ...}` — so the opaque upstream 400 happens anyway, one turn later, exactly as the comment says it should not. `test_tool_call_without_id_logs_warning` (test_agentic_loop.py:399-421) locks in the fall-through behavior by asserting the loop proceeds to `"done"`, which it can only do because the API is mocked.

Two consequences beyond the comment/behavior mismatch: (1) a side-effecting tool — `write_file` or `bash`, both registered built-ins — is executed even though its result provably cannot be delivered to the model; (2) the agent's `_history` is permanently corrupted, so every subsequent `handle_message` on this long-lived agent fails, not just this turn.

Failure scenario: a local OpenAI-compatible backend (vLLM, llama.cpp, Ollama) streams a `tool_calls` delta without an `id`. The model's `bash` command runs against the jail, the request that follows is rejected with `invalid tool_call_id`, the caller sees a generic `ProviderAPIError`, and the agent is unusable from then on.

Suggest either raising `ProviderError` before executing (matching the comment), or skipping the call and appending nothing. Either way, do not execute a tool whose result is undeliverable.

### [CONCERN] Cancellation mid-tool-execution leaves an unmatched `tool_calls` entry that silently poisons the agent

The assistant entry carrying `tool_calls` is appended at agent.py:294, and the matching `role: "tool"` results are appended one at a time at agent.py:316. `_execute_tool_call` catches `Exception`, but not `BaseException` — `asyncio.CancelledError` and `GeneratorExit` propagate. If the turn is cancelled while an executor is awaiting (very plausible: `bash` has a 120s timeout per `tools/limits.py`, and callers abandoning an async generator raise `GeneratorExit`), history is left with an assistant `tool_calls` entry and zero-to-partial tool results.

Failure scenario: a client disconnects while the model's `bash` call is running. The task is cancelled, `_history` retains `{"role": "assistant", "tool_calls": [call_1, call_2]}` with only `call_1`'s result appended. The agent object survives; the next `handle_message` sends that history and the API rejects it. Nothing logs at WARNING or above at the moment of corruption — the "Failure-Mode Enumeration" rule requires this be observable, and it is not.

Suggest either appending the assistant entry and all tool-result placeholders together (try/finally around the dispatch loop, backfilling an error result for each un-executed call), or trimming the dangling assistant entry in a `finally`.

### [CONCERN] Agentic loop has no wall-clock deadline — only iteration and character bounds

The two guards bound *turns* and *history size*, never *time*. `AsyncOpenAI` is constructed in `provider.py:49-53` with no `timeout=`, so each `_stream_turn` inherits the SDK's 600s default; `bash` adds up to 120s per call (`tools/limits.py:BASH_TIMEOUT_S`). At the default `max_tool_iterations=20` the worst-case turn is measured in hours, with no intermediate output yielded to the caller (see the NOTE below) — so from outside, the agent is indistinguishable from a hang.

Failure scenario: the model repeatedly calls `bash` on a command that runs to its 120s timeout. Twenty iterations later the caller has waited ~40 minutes, received not a single `Message`, and then gets `ProviderError: exceeded agent.max_tool_iterations`. "What if this hangs?" has no answer in this code path.

Suggest a deadline checked at the top of each iteration (a third bound alongside the existing two), and/or an explicit `timeout=` on the `AsyncOpenAI` client.

### [CONCERN] Loop bounds are not validated; a non-positive value fails confusingly on every turn

`get_typed_config` validates only that the value is an `int`; `ConfigKey` (config/keys.py:9-15) has no range facility. `provider.py` catches `ValueError` for type mismatch but never checks bounds. With `agent.max_tool_iterations = 0` or `-1`, `range(max_iterations)` at agent.py:292 yields nothing, the loop body never executes, and the code falls straight through to `raise ProviderError("Agentic loop exceeded agent.max_tool_iterations (0) without the model producing a final response.")` — a message that is actively misleading, since no API call was ever made. `agent.max_history_chars <= 0` fires the budget guard on the first check, silently reducing every agent to a single tool-using turn.

Failure scenario: a user runs `sq config set agent.max_tool_iterations 0` intending "no tool loop" and gets a per-turn error claiming the model failed to finalize. The invalid value is accepted at the boundary and surfaces as a runtime error deep in the call chain — the inverse of the project's fail-fast rule.

Suggest a guard in `create_agent` alongside the existing `ValueError` handling (`if max_tool_iterations < 1: raise ProviderError(...)`), with a test; there is currently no test covering the invalid-config path at all.

### [NOTE] `self._cwd` is stored but never read by production code

`cwd` is passed to `tools.materialize(known_names, cwd)` at agent.py:117 directly from the parameter; `self._cwd` has no other reader in `src/`. Its only consumer is `test_threads_allowed_tools_and_cwd_into_agent` (tests/providers/openai/test_provider.py:103), which asserts on a private field that exists only to be asserted on. The same test already asserts `"read_file" in agent._tool_executors`, which is the behavior that actually matters. Either drop the field and that assertion, or give it a real reader.

### [NOTE] `tools.lookup()` is called twice per requested tool name

The filter loop calls `tools.lookup(tool_name)` to test membership (agent.py:109), then the walrus comprehension at agent.py:118 looks every surviving name up a second time. Collecting descriptors in the first pass — `if (descriptor := tools.lookup(tool_name)) is None: ... else: descriptors.append(descriptor)` — removes the second lookup and the `is not None` re-filter, which pyright currently needs the walrus to satisfy.

### [NOTE] Provider comment overstates where config I/O moved to

"resolved here, at the composition boundary, so the agent never does blocking config file I/O from inside an async turn" — but `create_agent` is itself `async def`, so the two `get_typed_config` calls still perform blocking TOML reads on the event loop, just at construction time rather than turn time. The change is a real improvement (once per agent instead of once per turn), and small TOML reads are unlikely to breach the 1ms bound, but the comment claims the I/O left the async path when it did not. Worth rewording to say what it actually achieves.

### [NOTE] No load-test coverage for a new network + concurrency path

The Python rules require that code on network or concurrency paths carry at least one load test asserting latency/throughput/resource bounds. This slice adds a loop issuing up to 20 sequential streamed API calls interleaved with subprocess execution, and there is no `tests/load/` tier anywhere in the repo. Unit tests with mocked streams cannot catch the event-loop starvation described in the first finding. Flagging as informational since the missing tier is repo-wide and predates this slice — but this is precisely the kind of code the rule exists for.

### [PASS] Tool-failure surfacing is thorough and well-tested

Every argument-shape failure (malformed JSON, valid-but-non-object JSON, unknown tool name) and executor breach of the never-raise contract is converted to model-visible content with a matching log at an appropriate level, and each of the four paths has a test asserting both the returned content and the observable log record (test_agentic_loop.py:207-283). The `except Exception` at agent.py:249 carries a `noqa: BLE001` with a substantive justification and logs via `logger.exception`, satisfying the project's exception-handling rule.

### [PASS] Budget-guard notice correctly uses a user-role message, not a synthetic tool result

Injecting the finalize notice as `role: "user"` rather than a fabricated `role: "tool"` entry is the right call — a tool entry requires a `tool_call_id` matching a real pending call — and the reasoning is captured both in the code comment and in an assertion (`not any(e.get("role") == "tool" and e.get("tool_call_id") == "")`, test_agentic_loop.py:349). Withdrawing `tool_schemas` after the guard fires so the model cannot ignore the notice is a nice touch, and it is verified against the actual last call's kwargs.

### [PASS] Wire-shape builders correctly centralized in translation.py

Moving `build_assistant_history_entry` and `build_tool_result_entry` out of the agent gives the OpenAI request/history shape exactly one home, which is what keeps the no-tools path (agent.py:139) and the loop path (agent.py:294) from drifting. `build_tool_schemas` taking `list[ToolDescriptor]` under `TYPE_CHECKING` keeps the translation module free of a runtime dependency on `squadron.tools`. All three have direct unit tests.
