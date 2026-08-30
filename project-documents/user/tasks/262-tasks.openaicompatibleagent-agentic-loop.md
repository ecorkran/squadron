---
docType: tasks
slice: openaicompatibleagent-agentic-loop
project: squadron
lldReference: project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md
parent: project-documents/user/architecture/260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261]
projectState: Phase 5 tasks complete; tasks-review CONCERNS findings (F001, F002) and note (F006) addressed. Task 2/3 swapped so translation helpers precede constructor threading; added a create_agent-level test for the tools-configured wiring path; Task 4.3 resolved to inline the no-tools path rather than keep a `_call_api` wrapper. Slice 261 (tool registry) is merged to main. No agent, provider, or config code has changed for this slice yet.
dateCreated: 20260828
dateUpdated: 20260829
status: not_started
---

# Tasks: OpenAICompatibleAgent Agentic Loop

## Context Summary

- Slice **262** makes `OpenAICompatibleAgent` consume the slice-261 tool registry. It replaces
  the single API round-trip in `handle_message` with a loop: materialize tool executors once at
  construction, call the API with a `tools` schema, execute any returned tool calls against the
  registry, append results to history, and re-invoke until the model stops calling tools.
- **Gated entirely by `AgentConfig.allowed_tools`.** Every caller today passes no tools (or
  `[]`), so the no-tools branch must be byte-for-byte the current behavior — this is the
  strongest regression signal and is proven by the existing 15-test suite passing unmodified.
- **Two structural gaps close here, not assumed as preconditions:** the agent constructor never
  receives `allowed_tools` or `cwd` today (they stop at `create_agent`), and `_call_api` mixes
  I/O with Message-building in a way a loop cannot reuse. Tasks 2 and 3 close these.
- **Two design decisions came from slice-review fixes** (commit `0f88c66`) and are load-bearing,
  not optional: D8 — a non-empty tool set with `cwd=None` raises `ProviderError` at construction
  (no silent jail-root fallback); D9 — malformed tool-call JSON and unknown tool names from the
  model log at WARNING, not DEBUG. Both have dedicated test tasks below.
- **D1 — unknown declared tool names are dropped, not fatal.** Every shipped review template and
  `metrology/audit.py` declare Claude vocabulary (`Read`, `Glob`, `Grep`, `Bash`); this slice's
  filter is what keeps those callers from crashing the moment they reach this code. Vocabulary
  migration is slice 265 — until then, the WARNING is expected on every non-SDK review.
- **Commit per task group, not once at the end**, mirroring slice 261. Task 0 creates the
  branch; each group ends with a commit step. Every commit leaves
  `pytest tests/providers/openai/ -q` passing.

### Verified anchors (traced 20260828 on `0f88c66`)

| Anchor | Fact |
|---|---|
| Agent constructor today | [agent.py:29-43](src/squadron/providers/openai/agent.py#L29-L43) — `__init__(name, client, model, system_prompt)`. No `allowed_tools`, no `cwd`. |
| `_call_api` today | [agent.py:80-120](src/squadron/providers/openai/agent.py#L80-L120) — single request, delta aggregation into `text_buffer`/`tool_calls_dict`, then `translation.build_messages` and `_append_assistant_history` in the same method. |
| `_append_assistant_history` today | [agent.py:122-136](src/squadron/providers/openai/agent.py#L122-L136) — becomes `translation.build_assistant_history_entry` per design D5. |
| `create_agent` today | [provider.py:37-62](src/squadron/providers/openai/provider.py#L37-L62) — constructs `OpenAICompatibleAgent` with 4 positional/keyword args; `config.allowed_tools` and `config.cwd` are read from `AgentConfig` but never passed through. |
| `AgentConfig` fields used here | [core/models.py:56-58](src/squadron/core/models.py#L56-L58) — `cwd: str | None`, `allowed_tools: list[str] | None`. Already exist; no `AgentConfig` change in this slice. |
| Tool registry API (slice 261) | `squadron.tools`: `lookup(name) -> ToolDescriptor | None`, `materialize(names, cwd) -> dict[str, ToolExecutor]`, raises `ToolNotRegisteredError` on any unknown name — this slice pre-filters through `lookup` so `materialize` never sees an unknown name (D1). |
| `ToolResult` shape | `src/squadron/tools/models.py` — frozen dataclass `content: str`, `is_error: bool = False`. Executors never raise; the loop's "executor raises" branch is defense against a future/MCP-bridged violation only. |
| `ProviderError` | [providers/errors.py:6-7](src/squadron/providers/errors.py#L6-L7) — base exception, already caught nowhere special in `handle_message`; raising it here uses the existing failure path, no new channel. |
| Config key precedent | [config/keys.py:98-105](src/squadron/config/keys.py#L98-L105) — `review.max_file_size_bytes` is the pattern: `ConfigKey(name, type_, default, description)` entries in `CONFIG_KEYS`, read via `get_typed_config(key, int, cwd=...)` which raises on type mismatch. |
| `ConfigKey` dataclass | [config/keys.py:8-15](src/squadron/config/keys.py#L8-L15) — frozen, fields `name: str`, `type_: type`, `default: object`, `description: str`. |
| Test harness (existing) | `tests/providers/openai/conftest.py` — `mock_async_openai` fixture, `text_chunk()`, `tool_chunk(index, id, name, args_fragment)` builders, `_async_stream(*chunks)` helper in `test_agent.py`. All reusable for multi-turn tests via `AsyncMock(side_effect=[stream1, stream2, ...])`. |
| Pinned regression test | `tests/providers/openai/test_agent.py::TestX::test_handle_message_yields_system_for_tool_call` (line 122) — asserts a tool call with **no tools configured** still surfaces as a `MessageType.system` Message. Must keep passing unmodified — it is the no-tools-path contract. |
| pytest config | `pyproject.toml:81` — `asyncio_mode = "auto"`; `async def` tests need no decorator. |
| Ruff lint set | `select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`. `BLE` requires `# noqa: BLE001` on any bare `except Exception`. |
| Pyright | `typeCheckingMode = "strict"`, `include = ["src"]`. New/changed code under `src/squadron/providers/openai/` and `src/squadron/config/` must pass strict. |
| Line length | 104 |
| File size guideline | `agent.py` is 141 lines now; design estimates +100 for the loop, landing near 240 — inside the ~300-line project guideline. No file split expected. |

### Constraints the design implies but does not spell out

1. **`squadron.tools` must be imported for built-ins to exist.** Importing
   `squadron.tools.registry` alone does not trigger `builtin.py`'s registration side effect —
   only `squadron.tools` (the package `__init__`) does. The agent module must import the
   package, not just the registry submodule.
2. **Config reads need a `cwd`.** `get_typed_config(key, type_, cwd=...)` takes a directory to
   resolve project-local config from. Use the agent's own `cwd` (already validated non-None by
   the time loop limits are read, per D8) — do not default to `"."` silently.
3. **The D8 raise must happen even when `allowed_tools` names are all unknown-and-dropped.**
   Order matters: the empty-vs-non-empty check for the D8 raise is against the *requested*
   `allowed_tools` from config, not the post-D1-filter materialized set — otherwise a caller
   requesting only unknown names with no `cwd` would silently skip the cwd check. Confirm this
   against the design's decision text in Task 3 before writing the raise condition.
4. **`caplog` needs an explicit level.** Tests asserting WARNING or INFO records must call
   `caplog.set_level(logging.WARNING)` / `logging.INFO` — default propagation captures WARNING+
   only from the root, and this project's tests set the level explicitly per the 261 precedent.

---

## Task 0: Branch

- [x] **0.1 Create the slice branch** — Effort: 1/5
  - [x] Confirm the integration target: `cf config get git.integration_branch`. An empty value
        means the target is `main`.
  - [x] From the target, create and switch to `262-slice.openaicompatibleagent-agentic-loop`:
        `git checkout -b 262-slice.openaicompatibleagent-agentic-loop <target>`.
  - [x] If the branch already exists, `git checkout` it instead. Never start from another unit's
        branch.
  - [x] Success: `git branch --show-current` prints the slice branch and `git status` is clean.

### Commit cadence for this slice

Every task group below ends with a commit step. Commit from the project root, on the slice
branch, and run `.venv/bin/ruff format .` immediately before each one. Each commit must leave
the tree in a state where `.venv/bin/pytest tests/providers/openai/ -q` passes. Do not merge,
push, or delete the branch at any point without explicit instruction from the Project Manager.

---

## Task 1: Config keys for loop limits

- [x] **1.1 Register `agent.max_tool_iterations` and `agent.max_history_chars`** — Effort: 1/5
  - [x] In `src/squadron/config/keys.py`, add two `ConfigKey` entries to `CONFIG_KEYS`
        following the exact shape of `review.max_file_size_bytes` (line 98):
        `agent.max_tool_iterations` (`type_=int`, `default=20`, description referencing the
        max-iterations guard) and `agent.max_history_chars` (`type_=int`, `default=400_000`,
        description referencing the history-budget guard).
  - [x] Do not add any config plumbing beyond the `CONFIG_KEYS` entries — reading them is the
        agent's job (Task 6).
  - [x] Success: `python -c "from squadron.config.keys import get_default; print(get_default('agent.max_tool_iterations'), get_default('agent.max_history_chars'))"`
        prints `20 400000`.

- [x] **1.2 Test the new keys** — Effort: 1/5
  - [x] Add or extend a config-keys test asserting both keys exist in `CONFIG_KEYS`, have the
        correct `type_` and `default`, and round-trip through `get_config`/`get_typed_config`
        with a temp-dir `cwd` that has no override (returns the default).
  - [x] Success: `.venv/bin/pytest tests/config/ -q` passes, including the new/extended test.

- [x] **1.3 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`
  - [x] `git add -A && git commit -m "feat: add agent loop-limit config keys"`
  - [x] Success: clean tree; `pytest tests/config/ -q` passes on the new commit.

---

## Task 2: Protocol helpers in `translation.py`

*(Reordered ahead of constructor threading — review F001: the constructor task needs
`build_tool_schemas`, so the helper must exist first. Translation helpers have no dependency
on the constructor work.)*

- [x] **2.1 `build_tool_schemas`** — Effort: 2/5
  - [x] Add `build_tool_schemas(descriptors: list[ToolDescriptor]) -> list[dict[str, object]]` to
        `src/squadron/providers/openai/translation.py`, mapping each descriptor to
        `{"type": "function", "function": {"name": d.name, "description": d.description,
        "parameters": d.parameters}}` per the design's Tool Schema Construction section. Pure
        function, no I/O.
  - [x] Success: unit test with two hand-built `ToolDescriptor` values asserts the exact output
        shape, including that `parameters` is passed through unchanged.

- [x] **2.2 `build_assistant_history_entry`** — Effort: 2/5
  - [x] Move the logic currently in `agent.py`'s `_append_assistant_history` (lines 122-136) into
        `translation.py` as `build_assistant_history_entry(text: str, tool_calls: list[dict[str,
        object]]) -> dict[str, object]`, preserving behavior exactly: `content=None` when `text`
        is empty and `tool_calls` is non-empty; plain `{"role": "assistant", "content": text}`
        when there are no tool calls.
  - [x] Success: a test with (a) text-only, (b) tool-calls-only (empty text), and (c) mixed
        text+tool-calls inputs asserts the three known output shapes match what
        `_append_assistant_history` produces today (compare against the pre-move behavior, e.g.
        by running the existing `test_agent.py` history-shape assertions before and after).

- [x] **2.3 `build_tool_result_entry`** — Effort: 1/5
  - [x] Add `build_tool_result_entry(tool_call_id: str, content: str) -> dict[str, object]`
        returning `{"role": "tool", "tool_call_id": tool_call_id, "content": content}`.
  - [x] Success: a one-line unit test asserts the exact dict shape.

- [x] **2.4 Test all three together** — Effort: 1/5
  - [x] Add `tests/providers/openai/test_translation.py` cases for 2.1–2.3 if not already
        colocated with the implementation tasks above (this task exists to confirm nothing was
        skipped — check the file, do not duplicate tests already written).
  - [x] Success: `.venv/bin/pytest tests/providers/openai/test_translation.py -q` passes with the
        three new functions covered.

- [x] **2.5 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`
  - [x] `git add -A && git commit -m "feat: add OpenAI tool-protocol helpers to translation.py"`
  - [x] Success: clean tree; `pytest tests/providers/openai/ -q` passes.

---

## Task 3: Thread `allowed_tools` and `cwd` into the agent constructor

- [x] **3.1 Extend `OpenAICompatibleAgent.__init__`** — Effort: 2/5
  - [x] Add two keyword-only parameters with defaults so existing call sites are unaffected:
        `allowed_tools: list[str] | None = None`, `cwd: str | None = None`.
  - [x] Import `squadron.tools` (the package, not `squadron.tools.registry`) so built-in tools
        are guaranteed registered — see Constraint 1.
  - [x] Resolve the *requested* tool set (`allowed_tools or []`) and, **before** any
        registry call, apply the D8 check: if the requested set is non-empty and `cwd is None`,
        raise `ProviderError` with a message naming the missing `cwd` and the requested tools.
        Confirm this check uses the requested set per Constraint 3, not the post-filter one.
  - [x] If the requested set is non-empty, filter each name through `registry.lookup`; log one
        WARNING per dropped (unknown) name naming it and the full registered vocabulary
        (`registry.list_tools()`); call `registry.materialize` only with the surviving known
        names and the given `cwd`. Store the result as `self._tool_executors: dict[str,
        ToolExecutor]`.
  - [x] If the requested set is empty, set `self._tool_executors = {}` and do not touch `cwd` at
        all (no check, no registry call) — this is the path every current caller takes.
  - [x] Build `self._tool_schemas` once from the materialized names via the schema helper
        (Task 2.1) — empty list when there are no tools.
  - [x] Store `self._cwd = cwd` for later use by the config reads in Task 6.
  - [x] Success (interim, proven by 3.2): constructing with no tools behaves as before;
        constructing with a mix of one known and one unknown name materializes the known one and
        logs a WARNING for the unknown one; constructing with a non-empty known set and
        `cwd=None` raises `ProviderError`.

- [x] **3.2 Test constructor behavior** — Effort: 2/5
  - [x] `tests/providers/openai/test_agent.py` or a new `tests/providers/openai/
        test_agentic_loop.py` (Task 8 decides the final file split — write here for now):
        constructing with `allowed_tools=None` and `cwd=None` does not raise and yields empty
        `self._tool_executors`.
  - [x] Constructing with `allowed_tools=["read_file"]` and a valid temp-dir `cwd` materializes
        `read_file` with no WARNING logged.
  - [x] Constructing with `allowed_tools=["Read", "read_file"]` and a valid `cwd`: `read_file` is
        materialized, `Read` is dropped, and `caplog` (level WARNING) captured exactly one
        WARNING naming `Read`.
  - [x] Constructing with `allowed_tools=["read_file"]` and `cwd=None` raises `ProviderError`.
  - [x] Constructing with `allowed_tools=[]` (or `None`) and `cwd=None` does **not** raise (D8
        applies only to a non-empty requested set).
  - [x] Success: `.venv/bin/pytest tests/providers/openai/ -q -k "construct or cwd or tool_set"`
        passes (adjust the `-k` filter to match the test names actually written).

- [x] **3.3 Thread the fields through `OpenAICompatibleProvider.create_agent`** — Effort: 1/5
  - [x] In `src/squadron/providers/openai/provider.py`, pass `allowed_tools=config.allowed_tools`
        and `cwd=config.cwd` into the `OpenAICompatibleAgent(...)` construction at line 57.
  - [x] No other change to `create_agent` — credential resolution and client construction are
        untouched.
  - [x] Success: `.venv/bin/pytest tests/providers/openai/test_provider.py -q` passes unmodified
        (it exercises `create_agent` without tools, so behavior is unchanged there); a manual
        read of the diff shows only the two new keyword arguments added.

- [x] **3.4 Test `create_agent` with tools configured (review F002)** — Effort: 2/5
  - [x] Task 3.3's success bar alone (unmodified `test_provider.py` + a manual diff read) does
        not exercise the tools-configured path through `create_agent` — it only proves the
        no-tools case is unchanged. Add a dedicated test that builds an `AgentConfig` with a
        non-empty `allowed_tools` (e.g. `["read_file"]`) and a valid `cwd`, calls
        `OpenAICompatibleProvider.create_agent(config)`, and asserts on the **returned agent
        object** — not just on the constructor directly — that its materialized tool set and
        `cwd` reflect what was passed in (e.g. `agent._tool_executors` contains `read_file`,
        `agent._cwd == config.cwd`). This is the wiring correctness-of-cost property the slice
        exists to guarantee; without it, a future edit to `create_agent` could silently drop the
        threading and nothing would catch it.
  - [x] Success: `.venv/bin/pytest tests/providers/openai/test_provider.py -q -k tools` passes.

- [x] **3.5 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`
  - [x] `git add -A && git commit -m "feat: thread allowed_tools and cwd into OpenAICompatibleAgent"`
  - [x] Success: clean tree; `pytest tests/providers/openai/ -q` passes.

---

## Task 4: Split `_call_api` into `_stream_turn`

- [x] **4.1 Extract `_stream_turn`** — Effort: 3/5
  - [x] Add a small frozen dataclass `TurnResult(text: str, tool_calls: list[dict[str,
        object]])` in `agent.py` (internal plumbing only, not exported).
  - [x] Extract the request-and-aggregate logic currently in `_call_api` (lines 88-117: the
        `chat.completions.create` call, the `async for chunk in stream` loop, tool-call delta
        assembly) into `async def _stream_turn(self, messages: list[dict[str, object]], tools:
        list[dict[str, object]] | None) -> TurnResult`. Move the aggregation logic verbatim — do
        not rewrite the multi-chunk tool-call assembly, it is already correct (design
        §Current shape and why it cannot host a loop).
  - [x] Pass `tools=tools` to `chat.completions.create` only when `tools` is non-empty/not None
        — never send an empty `tools` list (matches "tool schemas sent only when tools are
        configured" success criterion).
  - [x] `_stream_turn` does not touch `self._history` and does not call `translation` — it is a
        pure request/aggregate primitive returning `TurnResult`.
  - [x] Success (interim, proven by 4.2): a direct test of `_stream_turn` against a mocked
        streamed response returns the correct `TurnResult` for text-only, tool-call-only, and
        mixed streams.

- [x] **4.2 Test `_stream_turn` in isolation** — Effort: 2/5
  - [x] Reuse `tests/providers/openai/conftest.py`'s `text_chunk`/`tool_chunk`/`_async_stream`
        helpers. Assert: text-only stream → `TurnResult(text=..., tool_calls=[])`; tool-call
        stream → `TurnResult(text="", tool_calls=[...])` with the assembled call matching the
        chunk's id/name/arguments; a stream with `tools=None` passed does not include a `tools`
        kwarg in the captured `create()` call; a stream with `tools=[...]` passed does.
  - [x] Success: `.venv/bin/pytest tests/providers/openai/ -q -k stream_turn` passes.

- [x] **4.3 Inline the no-tools path into `handle_message`, removing `_call_api`** — Effort: 2/5
  - [x] Delete `_call_api` as a named method; its call-and-translate logic (now just a few lines
        given `_stream_turn` does the request/aggregate work) lives directly in `handle_message`
        for the no-tools branch (review F006 — resolves the task's original open choice between
        keeping `_call_api` as a wrapper or inlining it: inline, since a same-file
        one-line-forwarding wrapper adds indirection `_stream_turn` already replaced).
  - [x] With no tools configured, `handle_message` must call `_stream_turn(self._history,
        tools=None)`, append the assistant turn to `self._history` via
        `translation.build_assistant_history_entry`, and yield
        `translation.build_messages(turn.text, turn.tool_calls, ...)` — i.e., today's exact
        output, including the tool-call-as-system-Message case, reproduced through the new
        primitive rather than the old monolithic `_call_api`.
  - [x] Delete the now-unused parts of the old `_call_api`/`_append_assistant_history` bodies
        once their logic lives in `_stream_turn` (Task 4.1) and `translation.py` (Task 2.2). Do
        not leave dead code.
  - [x] Success: `.venv/bin/pytest tests/providers/openai/test_agent.py -q` passes **unmodified**
        — every one of the original 15 tests, byte-for-byte, including
        `test_handle_message_yields_system_for_tool_call`. This is the slice's primary
        regression gate; do not proceed to Task 5 until it is green.

- [x] **4.4 Commit** — Effort: 1/5
  - [x] `.venv/bin/ruff format .`
  - [x] `git add -A && git commit -m "refactor: split _call_api into _stream_turn primitive"`
  - [x] Success: clean tree; `pytest tests/providers/openai/ -q` passes, all 15 original tests
        green with zero modifications to their source.

---

## Task 5: Tool-call execution and error surfacing

- [ ] **5.1 `_execute_tool_call`** — Effort: 3/5
  - [ ] Add `async def _execute_tool_call(self, tool_call: dict[str, object]) -> str` (returns
        the content string for the `role: "tool"` message) implementing the design's error
        table (§Error surfacing inside the loop):
        - Parse `tool_call["function"]["arguments"]` as JSON. On `json.JSONDecodeError`, log a
          WARNING (D9) naming the tool and the parse failure, and return an error content
          string.
        - Look up the tool name in `self._tool_executors`. If absent, log a WARNING (D9) naming
          the tool and listing the allowed names, and return an error content string.
        - Call the executor. If it returns `ToolResult(is_error=True)`, log at INFO (per 261
          precedent — not a WARNING; only the two D9 cases and the executor-raises case exceed
          INFO) and return its `content` verbatim.
        - If the executor raises, catch it, log via `logger.exception` (ERROR), and return an
          error content string. This is the only ERROR-level path in the loop (design
          §Error surfacing).
        - On success, log at DEBUG (name, args, truncated result) and return `content`.
  - [ ] Success (interim, proven by 5.2): each of the five branches is independently testable by
        calling `_execute_tool_call` directly with a hand-built `tool_call` dict and a
        pre-populated `self._tool_executors`.

- [ ] **5.2 Test `_execute_tool_call`** — Effort: 3/5
  - [ ] Malformed JSON args → error content mentions the parse failure; `caplog` (level WARNING)
        captured exactly one WARNING naming the tool.
  - [ ] Unknown tool name → error content lists the allowed tool names; `caplog` (level WARNING)
        captured exactly one WARNING.
  - [ ] Executor returns `ToolResult(is_error=True, content="boom")` → returned content is
        exactly `"boom"`; `caplog` (level INFO) captured an INFO record, no WARNING.
  - [ ] Executor raises `RuntimeError` → returned content is an error string (not a crash);
        `caplog` (level ERROR) captured an ERROR record from `logger.exception`.
  - [ ] Executor succeeds → returned content matches `ToolResult.content`; a DEBUG record was
        emitted (assert via `caplog.set_level(logging.DEBUG)`).
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k execute_tool_call` passes, five
        distinct test cases green.

- [ ] **5.3 Commit** — Effort: 1/5
  - [ ] `.venv/bin/ruff format .`
  - [ ] `git add -A && git commit -m "feat: add tool-call execution with WARNING-level error surfacing"`
  - [ ] Success: clean tree; `pytest tests/providers/openai/ -q` passes.

---

## Task 6: The agentic loop

- [ ] **6.1 `_run_agentic_loop`** — Effort: 4/5
  - [ ] Implement `async def _run_agentic_loop(self) -> list[Message]` per the design's Control
        Flow pseudocode (§Control flow):
        - Read `max_iterations = get_typed_config("agent.max_tool_iterations", int,
          cwd=self._cwd)` and `max_history_chars = get_typed_config("agent.max_history_chars",
          int, cwd=self._cwd)` **once, before the loop starts** (Constraint 2 — use
          `self._cwd`, which D8 guarantees is not `None` whenever `self._tool_executors` is
          non-empty).
        - Loop up to `max_iterations` times: call `_stream_turn(self._history,
          self._tool_schemas)`; append the assistant turn to `self._history` via
          `translation.build_assistant_history_entry` **verbatim** (content and tool_calls as
          returned — no mutation of prior entries, per the append-only invariant);
          if `turn.tool_calls` is empty, return `translation.build_messages(turn.text, [],
          self._name, self._model)` immediately — this is the **only** point that translates a
          turn into caller-facing Messages;
          otherwise, for each tool call in order, call `_execute_tool_call` and append one
          `translation.build_tool_result_entry(tool_call_id, content)` per call, in call order;
          after processing all calls in the turn, if accumulated history character count
          exceeds `max_history_chars` **and the budget guard has not already fired this loop**,
          append one budget-exceeded tool-result-shaped message and log one WARNING (guard
          fires at most once per loop, per design §Termination conditions).
        - If the loop exits by exhausting `max_iterations` without a no-tool-calls turn, log a
          WARNING and raise `ProviderError` naming the iteration count (D3 — no partial-text
          return).
  - [ ] Wire `handle_message` to call `_run_agentic_loop()` when `self._tool_executors` is
        non-empty, and the Task 4.3 no-tools path otherwise — this branch is the top-level gate
        described in the design's control-flow pseudocode.
  - [ ] Success (interim, proven by 6.2–6.6): each termination condition and the append-only
        invariant are independently testable against a scripted multi-turn mock stream using
        `AsyncMock(side_effect=[stream1, stream2, ...])` on `client.chat.completions.create`.

- [ ] **6.2 Test: normal termination and intermediate-turn suppression** — Effort: 2/5
  - [ ] Script turn 1 as a `write_file` tool call, turn 2 as plain text. Against a real temp
        directory (registry `materialize` with a real `cwd`), assert: the loop performs two
        `create()` calls; the yielded Messages contain exactly turn 2's text and nothing from
        turn 1; no `MessageType.system` tool-call Message is emitted (contrast with the
        no-tools-path test in 4.3, which still emits one).
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k "loop and normal"` (or
        equivalent test name) passes.

- [ ] **6.3 Test: multi-tool single turn** — Effort: 2/5
  - [ ] Script one turn with two tool calls (e.g. two `read_file` calls with different `id`s),
        then a final plain-text turn. Assert both tool calls were dispatched, the history
        contains one `role: "tool"` entry per `tool_call_id` in the same order the calls
        appeared, and the loop proceeds to the final turn.
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k multi_tool` passes.

- [ ] **6.4 Test: max-iterations guard (D3)** — Effort: 2/5
  - [ ] Write a temp-dir config setting `agent.max_tool_iterations` low (e.g. 2) — use the real
        config-file path, not a monkeypatched module attribute, per the design's walkthrough
        step 5 ("proves the keys are wired"). Script every turn as a tool call (never
        terminating). Assert `ProviderError` is raised after exactly the configured number of
        iterations, and `caplog` (level WARNING) captured a WARNING.
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k max_iterations` passes.

- [ ] **6.5 Test: history budget guard (D4)** — Effort: 2/5
  - [ ] Write a temp-dir config setting `agent.max_history_chars` low. Script several tool-call
        turns whose accumulated history exceeds the threshold, followed by a final plain-text
        turn. Assert the budget-exceeded message appears in history exactly once (not once per
        remaining iteration), `caplog` (level WARNING) captured exactly one WARNING for it, and
        the loop still reaches the final turn and returns normally (the guard warns and
        continues, per D4 — it is not itself a termination).
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k history_budget` passes.

- [ ] **6.6 Test: append-only / cache-friendly prefix invariant** — Effort: 2/5
  - [ ] Across a 3+ turn scripted loop, capture the `messages` kwarg of each successive
        `create()` call (via the mock's `call_args_list`). Assert, for every consecutive pair,
        that call N+1's `messages` list starts with exactly call N's `messages` list (strict
        prefix-extension) — per design §Message-history shape.
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k append_only` (or `prefix`)
        passes.

- [ ] **6.7 Test: provider returns plain text when tools are configured but unused** — Effort:
      1/5
  - [ ] With tools configured, script a single plain-text turn (model never calls a tool).
        Assert the loop terminates after one `create()` call and returns the text normally —
        the graceful "tools offered but model didn't use them" path from design §Risks.
  - [ ] Success: `.venv/bin/pytest tests/providers/openai/ -q -k tools_unused` passes.

- [ ] **6.8 Commit** — Effort: 1/5
  - [ ] `.venv/bin/ruff format .`
  - [ ] `git add -A && git commit -m "feat: implement OpenAICompatibleAgent agentic loop"`
  - [ ] Success: clean tree; `pytest tests/providers/openai/ -q` passes, all tests from Tasks
        2–6 green alongside the original 15.

---

## Task 7: Full-suite verification and static checks

- [ ] **7.1 Full test suite** — Effort: 1/5
  - [ ] `.venv/bin/pytest -q` from the project root.
  - [ ] Success: full suite passes with no regressions outside `tests/providers/openai/` (design
        baseline: ~3078 passed, 2 skipped, prior to this slice's additions).

- [ ] **7.2 Lint and types** — Effort: 1/5
  - [ ] `.venv/bin/ruff check .` — must be clean.
  - [ ] `.venv/bin/pyright src/squadron/providers/openai/` and
        `.venv/bin/pyright src/squadron/config/` — must be clean (strict mode).
  - [ ] Do **not** run whole-repo `pyright` as a pass/fail gate — it reports a large
        pre-existing error count unrelated to this slice (261 precedent). Use the scoped
        invocations above.
  - [ ] Success: both commands report zero errors on the scoped paths.

- [ ] **7.3 Commit** — Effort: 1/5
  - [ ] Only if 7.1/7.2 required fixes; otherwise skip (no empty commits).
  - [ ] `.venv/bin/ruff format .`
  - [ ] `git add -A && git commit -m "fix: address full-suite/lint findings for slice 262"` (only
        if there were findings to fix)
  - [ ] Success: clean tree; `pytest -q` passes; `ruff check .` clean.

---

## Task 8: Close-out

- [ ] **8.1 Request a slice review** — Effort: 1/5
  - [ ] Follow the project's standard code-review process against the implementation on this
        branch, per `.claude/rules/review-code.md`.
  - [ ] Address any CONCERNS findings before proceeding, verifying each against the actual code
        (as was done for the slice-design review, commit `0f88c66`) rather than accepting
        findings at face value.
  - [ ] Success: review verdict is PASS, or all CONCERNS are addressed and documented.

- [ ] **8.2 Refine the design's Verification Walkthrough** — Effort: 1/5
  - [ ] The design's Verification Walkthrough is marked "Draft — to be replaced with actual
        commands and real output at Phase 6 close-out." Replace it with the commands actually
        run in Tasks 6–7 and their real output.
  - [ ] Set the design document's `status` to `complete` and update `dateUpdated`.
  - [ ] Check off slice 262 in
        `project-documents/user/architecture/260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
        (Feature Slices entry 2), materializing the checkbox the way entry 1 was checked off for
        261. Leave the initiative itself `not_started` — 263–266 remain.

- [ ] **8.3 DEVLOG and commit** — Effort: 1/5
  - [ ] Append a DEVLOG entry to `DEVLOG.md` at the repo root covering: the constructor threading,
        the `_stream_turn` split, the loop's three termination conditions, the D8/D9 fixes
        carried from the design review, and the fact that no pipeline or review caller declares
        tools in canonical vocabulary yet (D1's WARNING window continues until 265).
  - [ ] Set this task file's `status` to `complete` and update `dateUpdated`.
  - [ ] `.venv/bin/ruff format .`, then commit:
        `docs: close out slice 262 — agentic loop implementation`.
  - [ ] Do **not** merge, push, or delete the branch without explicit instruction from the
        Project Manager.
  - [ ] Success: clean tree; the frontmatter gate passes; `git log --oneline <target>..HEAD`
        shows the per-task commits from groups 1–7 plus this close-out commit.

---

## Success Criteria (from the design, restated as a checklist)

- [ ] 1. No-tools behavior unchanged: `tests/providers/openai/test_agent.py` passes with zero
      source modifications, including `test_handle_message_yields_system_for_tool_call` (Task
      4.3).
- [ ] 2. `create_agent` threads `allowed_tools` and `cwd` into the agent (Tasks 3.3, 3.4).
- [ ] 3. `tools` schema sent only when tools are configured, verified on captured `create()`
      kwargs (Tasks 4.1, 4.2).
- [ ] 4. Tool-call turn continues the loop; no-tool-call turn terminates and its content is
      yielded (Task 6.2).
- [ ] 5. Intermediate turn content is never yielded (Task 6.2).
- [ ] 6. Multi-tool single turn dispatches all calls, one result per `tool_call_id`, in order
      (Task 6.3).
- [ ] 7. Malformed JSON args → error tool result + WARNING, loop continues (Tasks 5.1, 5.2).
- [ ] 8. Unknown tool name in a response → error tool result + WARNING, loop continues (Tasks
      5.1, 5.2).
- [ ] 9. Non-empty tool set with `cwd=None` raises `ProviderError`; empty set with `cwd=None`
      does not (Tasks 3.1, 3.2).
- [ ] 10. Unknown *declared* names dropped with WARNING; known names still materialize (Tasks
      3.1, 3.2).
- [ ] 11. `agent.max_tool_iterations` fires `ProviderError` + WARNING (Task 6.4).
- [ ] 12. History budget guard appends its message once and logs WARNING once (Task 6.5).
- [ ] 13. Both loop limits are registered config keys via `get_typed_config`, honoring a
      user-set value and the registered default (Tasks 1.1, 1.2, 6.4, 6.5).
- [ ] 14. History is append-only / strict prefix-extension across turns (Task 6.6).
- [ ] 15. Full suite passes with no regression; `ruff check` clean; scoped `pyright` clean
      (Task 7).

---

## Out of Scope (do not implement here)

- Pipeline YAML surface and `dispatch` wiring for `allowed_tools` — slice 263.
- Review injection-skip logic, `list_files`/`grep` tools, template vocabulary migration from
  Claude names to canonical names — slice 265. Non-SDK reviews continue to log the D1 WARNING
  and run tool-less until then; that is expected, not a defect to fix here.
- `tool_use` model-capability config field and `sq review --no-tools` — slice 266.
- MCP-bridged tool descriptors — slice 264.
- Streaming intermediate loop turns to the caller — final turn only, by design.
- History truncation or summarization — the budget guard returns an error to the model instead.
- Any change to `ClaudeSDKAgent`, `CodexAgent`, `AgentConfig`, the `Agent` protocol, or the
  pipeline executor.
