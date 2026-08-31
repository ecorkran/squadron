---
docType: review
layer: project
reviewType: code
slice: openaicompatibleagent-agentic-loop
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md
aiModel: claude-opus-5
status: complete
dateCreated: 20260830
dateUpdated: 20260830
reviewedSha: 2b17e13a4a384a0a0e78b4d06b61ff726c0066a6
findings:
  - id: F001
    severity: fail
    category: static-analysis
    summary: "Pyright strict fails with 35 new errors in `agent.py` — CI merge gate"
    location: "src/squadron/providers/openai/agent.py:154-165"
  - id: F002
    severity: concern
    category: async-correctness
    summary: "Blocking config file I/O on the event loop, once per `handle_message`"
    location: "src/squadron/providers/openai/agent.py:252-253"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Missing tool-call `id` silently produces a malformed history entry"
    location: "src/squadron/providers/openai/agent.py:270"
  - id: F004
    severity: concern
    category: test-isolation
    summary: "Four agentic-loop tests read the developer's real `~/.config/squadron/config.toml`"
    location: "tests/providers/openai/test_agentic_loop.py:231-374"
  - id: F005
    severity: note
    category: correctness
    summary: "History-budget guard firing on the final iteration still raises the max-iterations error"
    location: "src/squadron/providers/openai/agent.py:272-291"
  - id: F006
    severity: note
    category: correctness
    summary: "`_history_chars` measures Python `repr` output, not message content"
    location: "src/squadron/providers/openai/agent.py:303-305"
  - id: F007
    severity: note
    category: documentation
    summary: "`AgentConfig.cwd` / `allowed_tools` comments still say \"SDK agents\""
    location: "src/squadron/core/models.py:56-58"
  - id: F008
    severity: pass
    category: project-conventions
    summary: "Guard limits centralized as config keys with no magic defaults"
    location: "src/squadron/config/keys.py:274-291"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Tool failures are converted to values, with correct observability per failure mode"
    location: "src/squadron/providers/openai/agent.py:194-242"
  - id: F010
    severity: pass
    category: test-coverage
    summary: "Append-only history invariant is tested structurally, not by convention"
    location: "tests/providers/openai/test_agentic_loop.py:337-366"
---

# Review: code — slice 262

**Verdict:** FAIL
**Model:** claude-opus-5

## Findings

### [FAIL] Pyright strict fails with 35 new errors in `agent.py` — CI merge gate

`.github/workflows/ci.yml:30` runs `uv run pyright`, and the project rule makes zero errors a merge blocker. Base `agent.py` = 0 errors; branch `agent.py` = 35 errors. Two independent root causes:

1. **`**create_kwargs` erases the SDK's typed overload** (lines 154–165). Building a `dict[str, Any]` and unpacking it prevents pyright from resolving `chat.completions.create`'s overloads, so the result is `Unknown`. The declared `stream: AsyncStream[ChatCompletionChunk]` annotation does not repair this — it is an assignment *from* Unknown. That single change cascades into 33 `reportUnknown*` errors across the whole delta-aggregation block (lines 163–190) and downstream through `TurnResult.tool_calls` (line 43), `_execute_tool_call` (lines 205, 226, 239), and `handle_message` (lines 89–91). Beyond the CI failure, this is a real loss of coverage: the streaming chunk-assembly loop — the most protocol-fragile code in the slice — is now entirely untyped. Passing `tools=...` explicitly (e.g. two `create(...)` calls, or `tools=tool_schemas if tool_schemas else NOT_GIVEN`) restores it.

2. **`range(max_iterations)` with an `int | float`** (line 256). `get_typed_config` is declared to return `int | float`, which is not `SupportsIndex`. The established idiom elsewhere in this codebase already handles it — `src/squadron/metrology/audit.py:599` writes `int(get_typed_config("metrology.audit_timeout_s", int, cwd=cwd))`. Lines 252–253 omit the `int()` wrapper.

### [CONCERN] Blocking config file I/O on the event loop, once per `handle_message`

`_run_agentic_loop` is `async def` and calls `get_typed_config` twice. That chain is fully synchronous and uncached: `get_typed_config` → `get_config` → `load_config`, which calls `user_config_path()` → `_config_dir()` (two `Path.exists()` stats, plus a `shutil.copytree` on the legacy-migration branch) and then two `open()` + `tomllib.load()` calls — all of that *twice*, since neither `get_config` nor `load_config` memoizes. The Python rules require synchronous work inside an awaitable to be under 1ms worst case; cold-cache filesystem stats and TOML parses are not bounded that way, and with several agents concurrently handling messages this serializes on the loop.

Both values are per-agent constants and are already known at construction time. The provider (`provider.py:59-63`) already injects `model`, `system_prompt`, `allowed_tools`, and `cwd`; reaching into global config from inside the agent is also a DIP inversion relative to that established seam — resolving both limits in `OpenAICompatibleProvider.create_agent` and passing them to `__init__` fixes the blocking call and the dependency direction together, and would remove the need for `assert self._cwd is not None` at line 251.

### [CONCERN] Missing tool-call `id` silently produces a malformed history entry

`_stream_turn` initializes each accumulated call with `"id": ""` (line 176) and only overwrites it under `if tc.id:` (line 181), and `_run_agentic_loop` then reads `tool_call.get("id", "")` (line 270). If an OpenAI-*compatible* backend — which is the stated target surface, not just OpenAI itself — streams a tool-call delta without an id, the loop emits `{"role": "tool", "tool_call_id": "", ...}` with no log at any level. The next request in the loop is then rejected by the API for an unmatched `tool_call_id`, surfacing as an opaque `ProviderAPIError` several turns removed from the cause. With two id-less calls in one turn, the two `""` ids are mutually ambiguous.

This is exactly the failure mode the previous commit (`dbb7549`, "fix orphaned tool_call_id in history-budget guard") was about, and the test at `tests/providers/openai/test_agentic_loop.py:329` already asserts `not any(e.get("role") == "tool" and e.get("tool_call_id") == "")` — the code treats empty-id as a defect state in tests while silently manufacturing one in production. Per CLAUDE.md ("never use silent fallback values") and the Failure-Mode Enumeration rule (every failure mode must be observable at WARNING+), an id-less tool call should log a WARNING and be handled explicitly rather than defaulting to `""`.

### [CONCERN] Four agentic-loop tests read the developer's real `~/.config/squadron/config.toml`

`patch_config_paths` (defined at `tests/conftest.py:30`) is opt-in, and only the two guard tests request it. `test_normal_termination_suppresses_intermediate_turn` (line 231), `test_multi_tool_single_turn_dispatches_all_in_order` (line 253), `test_append_only_history_is_strict_prefix_extension` (line 337), and `test_tools_configured_but_unused_returns_plain_text` (line 368) all reach `_run_agentic_loop`, which resolves `agent.max_tool_iterations` through the unpatched real user config path. A developer or CI image with `agent.max_tool_iterations = 1` in `~/.config/squadron/config.toml` fails the first three with an unrelated `ProviderError`. This violates "avoid test interdependence — tests should run independently"; the ambient dependency is invisible from the test body. Adding `patch_config_paths` to these four (or making it autouse for this module) removes it.

### [NOTE] History-budget guard firing on the final iteration still raises the max-iterations error

The guard's contract is "ask the model to finalize, then stop offering tools," which needs one more iteration to pay off. If it fires when `_iteration == max_iterations - 1`, the `for` exits immediately and line 297 raises `ProviderError` — the model never gets the finalize turn the notice promised it, and the surfaced error names `max_tool_iterations` rather than the budget guard that actually ended the run. Reserving a turn for the finalize pass (or raising a distinct budget-guard error) would make the diagnosis match the cause.

### [NOTE] `_history_chars` measures Python `repr` output, not message content

`sum(len(str(entry)) for entry in self._history)` stringifies each dict, so the count includes `{`, `'role': `, quote and escape characters — roughly 15–30% overhead over actual content, and more for entries with nested `tool_calls`. The `agent.max_history_chars` config description (`config/keys.py`) says "Accumulated message-history size (characters)", which reads as content size. The guard still fires monotonically so behavior is safe, but the configured number does not mean what the description says. Either summing `len(str(entry.get("content", "")))` or amending the key description would resolve the mismatch.

### [NOTE] `AgentConfig.cwd` / `allowed_tools` comments still say "SDK agents"

`provider.py:62-63` now forwards both fields to the API-backed `OpenAICompatibleAgent`, so the inline comments `# SDK agents: working directory` and `# SDK agents: tool whitelist` are stale and actively misleading — they suggest an OpenAI-provider config that sets these is a no-op, which is no longer true. This matters more than usual here because the vocabulary mismatch these fields now carry (Claude names vs. squadron names) is the subject of decision D1 and the deferred slice 265.

### [PASS] Guard limits centralized as config keys with no magic defaults

Both loop bounds are declared in `CONFIG_KEYS` with types, defaults, and descriptions rather than hard-coded at the call site — this is exactly what CLAUDE.md's "do not hard-code magic defaults / centralize at the config level" asks for, and `tests/config/test_keys.py` covers the declarations.

### [PASS] Tool failures are converted to values, with correct observability per failure mode

`_execute_tool_call` enumerates its failure modes explicitly — malformed JSON args, unknown tool name, executor raising — and each one logs at the right level (WARNING for model-caused, `logger.exception` for a contract violation) before returning an error string the model can react to. The `except Exception` at line 226 carries a specific written justification for why swallowing is correct, satisfying the exception-handling rule rather than merely silencing `BLE001`. `tests/providers/openai/test_agentic_loop.py:155-224` asserts the observable signal for all five paths, which is what the Failure-Mode Enumeration rule requires.

### [PASS] Append-only history invariant is tested structurally, not by convention

`test_append_only_history_is_strict_prefix_extension` snapshots the message list at each `create()` call and asserts every snapshot is a strict prefix extension of the previous one. It also documents the by-reference aliasing hazard that would have made a naive `call_args_list` assertion vacuously pass. That is the right way to pin an invariant that the loop's correctness depends on.
