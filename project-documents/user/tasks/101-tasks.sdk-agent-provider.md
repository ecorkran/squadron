---
docType: task-breakdown
slice: sdk-agent-provider
project: squadron
lld: user/slices/101-slice.sdk-agent-provider.md
dependencies: [foundation]
projectState: Foundation slice complete with migration applied. Agent/AgentProvider Protocols, AgentConfig model, Message model, AgentState enum, provider registry, ProviderError hierarchy, Settings, and logging are all in place. Provider subdirectory stubs exist at src/orchestration/providers/sdk/.
status: complete
dateCreated: 20260219
dateUpdated: 20260219
---

## Context Summary

- Working on the **SDK Agent Provider** slice — first concrete provider implementation
- Foundation is complete: Protocols, models, registry, errors, config, logging all in place
- Stub files exist at `src/orchestration/providers/sdk/` (`__init__.py`, `provider.py`, `agent.py`)
- This slice adds `translation.py` and replaces all three stubs with real implementations
- Next planned slices: Agent Registry (slice 3), CLI Foundation (slice 4)
- **Task ordering**: test-with pattern — implementation immediately followed by tests
- **All tests mock the SDK** — no real Claude CLI or Max subscription needed for unit tests

### SDK Package Reference

The `claude-agent-sdk` package (already installed) uses import name `claude_agent_sdk`. Key imports:

```python
# Core functions and classes
from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient

# Message types for translation
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage,
)

# Error types for error mapping
from claude_agent_sdk import (
    ClaudeSDKError,       # Base error
    CLINotFoundError,     # Claude Code CLI not installed
    CLIConnectionError,   # Connection to CLI failed
    ProcessError,         # CLI process exited with error (has .exit_code)
    CLIJSONDecodeError,   # Malformed JSON from CLI
)
```

`query()` signature:
```python
async def query(
    *, prompt: str, options: ClaudeAgentOptions | None = None
) -> AsyncIterator[Message]:  # SDK Message, not our Message
```

`ClaudeAgentOptions` key fields:
```python
ClaudeAgentOptions(
    system_prompt: str | None = None,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    permission_mode: str | None = None,  # "default", "acceptEdits", etc.
    cwd: str | Path | None = None,
    setting_sources: list[str] | None = None,  # e.g. ["project"]
)
```

`ClaudeSDKClient` key methods:
```python
class ClaudeSDKClient:
    def __init__(self, options: ClaudeAgentOptions | None = None)
    async def connect(self, prompt: str | None = None) -> None
    async def query(self, prompt: str, session_id: str = "default") -> None
    async def receive_response(self) -> AsyncIterator[Message]  # SDK Message
    async def disconnect(self) -> None
    # Also usable as async context manager: async with ClaudeSDKClient() as client:
```

SDK message types are dataclass-like objects with these key attributes:
- `AssistantMessage`: has `.content` (list of blocks: TextBlock, ToolUseBlock, etc.)
- `TextBlock`: has `.text` (str)
- `ToolUseBlock`: has `.name` (str), `.input` (dict)
- `ToolResultBlock`: has `.content` (str or list)
- `ResultMessage`: has `.subtype` ("success" or "error"), may have `.result` (str)

**Important**: Do NOT use `break` to exit `receive_response()` iteration early — the SDK docs warn this causes asyncio cleanup issues. Always iterate to completion using flags.

---

## Tasks

### Task 1: Implement Message Translation Module
**Owner**: Junior AI
**Dependencies**: None (purely functional, uses only SDK types and orchestration Message)
**Effort**: 2/5
**Objective**: Create `src/orchestration/providers/sdk/translation.py` with a function that converts SDK message types to orchestration `Message` objects.

**Steps**:
- [x] Create `src/orchestration/providers/sdk/translation.py`
- [x] Import SDK message types:
  ```python
  from claude_agent_sdk import (
      AssistantMessage,
      TextBlock,
      ToolUseBlock,
      ToolResultBlock,
      ResultMessage,
  )
  ```
- [x] Import orchestration types:
  ```python
  from orchestration.core.models import Message, MessageType
  ```
- [x] Implement `translate_sdk_message(sdk_msg: Any, sender: str) -> Message | None`
  - The function examines the type of `sdk_msg` and extracts meaningful content
  - Type `sdk_msg` as `Any` to avoid tight coupling — we check with `isinstance`
  - Translation rules (each returns a `Message` or `None`):
    1. `AssistantMessage` — iterate `.content` blocks. For each `TextBlock`, yield a Message with `content=block.text`, `message_type=MessageType.chat`, `metadata={"sdk_type": "assistant_text"}`. For each `ToolUseBlock`, yield a Message with `content=f"Using tool: {block.name}"`, `message_type=MessageType.system`, `metadata={"sdk_type": "tool_use", "tool_name": block.name, "tool_input": block.input}`.
    2. `ToolResultBlock` — yield a Message with `content=str(block.content)` (may be str or list, coerce to str), `message_type=MessageType.system`, `metadata={"sdk_type": "tool_result"}`.
    3. `ResultMessage` — if `subtype == "success"`, yield with `message_type=MessageType.chat`, `metadata={"sdk_type": "result", "subtype": "success"}`. If `subtype == "error"`, yield with `message_type=MessageType.system`, `metadata={"sdk_type": "result", "subtype": "error"}`. Content is `getattr(sdk_msg, "result", str(sdk_msg))`.
    4. Any other type — return `None` (skip unknown message types)
  - Since `AssistantMessage` can contain multiple blocks, the function should actually be `translate_sdk_message(sdk_msg, sender) -> list[Message]` returning zero or more Messages. Alternatively, keep it returning `Message | None` and have a separate `translate_sdk_messages(sdk_msg, sender) -> list[Message]` that handles the multi-block case. Choose whichever is cleaner — the important thing is that one `AssistantMessage` with 3 blocks produces up to 3 orchestration Messages.
  - All returned Messages should have: `sender=sender`, `recipients=["all"]`, auto-generated `id` and `timestamp` (Pydantic defaults handle this)

**Success Criteria**:
- [x] `translate_sdk_message` handles all five SDK message types from the translation table
- [x] `AssistantMessage` with multiple content blocks produces multiple Messages
- [x] Unknown message types return `None` (or empty list)
- [x] All returned Messages are valid orchestration `Message` objects with correct `sender`, `recipients`, `message_type`, and `metadata`

---

### Task 2: Write Translation Tests
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 2/5
**Objective**: Create `tests/providers/sdk/test_translation.py` with tests for the translation module.

**Steps**:
- [x] Create `tests/providers/` directory and `tests/providers/__init__.py` if they don't exist
- [x] Create `tests/providers/sdk/` directory and `tests/providers/sdk/__init__.py`
- [x] Create `tests/providers/sdk/test_translation.py`
- [x] For constructing test data, try to import and instantiate real SDK message types. If SDK types require CLI interaction to construct, use `unittest.mock.MagicMock` with matching attributes instead. Example mock approach:
  ```python
  def make_text_block(text: str):
      block = MagicMock()
      block.text = text
      # Make isinstance checks work:
      block.__class__ = TextBlock
      return block
  ```
  If `isinstance` mocking is too fragile, structure the translation function to check for attribute presence (duck typing) rather than strict `isinstance`, and document this decision.
- [x] Test cases:
  1. `AssistantMessage` with a single `TextBlock` → one Message, `message_type=chat`, metadata has `sdk_type=assistant_text`
  2. `AssistantMessage` with a single `ToolUseBlock` → one Message, `message_type=system`, metadata has `tool_name` and `tool_input`
  3. `AssistantMessage` with mixed blocks (TextBlock + ToolUseBlock + TextBlock) → three Messages in order
  4. `ToolResultBlock` → one Message, `message_type=system`, metadata has `sdk_type=tool_result`
  5. `ResultMessage` with `subtype="success"` → one Message, `message_type=chat`
  6. `ResultMessage` with `subtype="error"` → one Message, `message_type=system`
  7. Unknown type (e.g., a plain object) → returns `None` or empty list
  8. All Messages have correct `sender` and `recipients=["all"]`

**Success Criteria**:
- [x] All translation tests pass via `uv run pytest tests/providers/sdk/test_translation.py`
- [x] Every row of the translation table from the slice design has test coverage
- [x] Edge cases (empty content, unknown types) are covered

---

### Task 3: Implement SDKAgentProvider
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 2/5
**Objective**: Implement `SDKAgentProvider` in `src/orchestration/providers/sdk/provider.py` satisfying the `AgentProvider` Protocol.

**Steps**:
- [x] Replace the stub in `src/orchestration/providers/sdk/provider.py` with the implementation
- [x] Import required types:
  ```python
  from claude_agent_sdk import ClaudeAgentOptions
  from orchestration.core.models import AgentConfig
  from orchestration.providers.base import Agent  # Protocol
  from orchestration.providers.sdk.agent import SDKAgent
  from orchestration.logging import get_logger
  ```
- [x] Implement `SDKAgentProvider` class:
  - `provider_type` property → returns `"sdk"`
  - `create_agent(self, config: AgentConfig) -> SDKAgent`:
    1. Build `ClaudeAgentOptions` from config fields using the mapping table:
       - `system_prompt=config.instructions` (if not None)
       - `model=config.model` (if not None)
       - `allowed_tools=config.allowed_tools` (if not None)
       - `cwd=config.cwd` (if not None)
       - `setting_sources=config.setting_sources` (if not None)
       - `permission_mode`: use `config.permission_mode` if set, otherwise default to `"acceptEdits"` (see slice design — interactive mode hangs programmatic agents)
    2. Extract mode from `config.credentials.get("mode", "query")`
    3. Return `SDKAgent(name=config.name, options=options, mode=mode)`
  - `validate_credentials(self) -> bool`:
    1. Try to import `claude_agent_sdk` — if ImportError, return False
    2. Optionally check if the bundled CLI is accessible (the SDK bundles it). A simple approach: `import claude_agent_sdk; return True` since the package being importable means it's installed. A more thorough check could attempt `shutil.which("claude")` but this is not required — the SDK handles CLI discovery internally.
    3. Must not throw — always returns bool
- [x] Only pass non-None values to `ClaudeAgentOptions`. Build a dict of kwargs, filter out None values, then unpack: `ClaudeAgentOptions(**{k: v for k, v in kwargs.items() if v is not None})`

**Success Criteria**:
- [x] `SDKAgentProvider` has `provider_type`, `create_agent`, and `validate_credentials` matching the `AgentProvider` Protocol
- [x] `create_agent` correctly maps all `AgentConfig` fields to `ClaudeAgentOptions`
- [x] `permission_mode` defaults to `"acceptEdits"` when not specified
- [x] `mode` is read from `config.credentials` dict
- [x] `validate_credentials` returns bool, never throws
- [x] API-specific fields (`api_key`, `auth_token`, `base_url`) are silently ignored

---

### Task 4: Write SDKAgentProvider Tests
**Owner**: Junior AI
**Dependencies**: Task 3
**Effort**: 2/5
**Objective**: Create `tests/providers/sdk/test_provider.py` with tests for the provider.

**Steps**:
- [x] Create `tests/providers/sdk/test_provider.py`
- [x] Mock `claude_agent_sdk.ClaudeAgentOptions` if needed, or use the real class (it's a simple config object, safe to construct without CLI)
- [x] Mock `SDKAgent` constructor to verify it receives correct arguments
- [x] Test cases:
  1. `provider_type` returns `"sdk"`
  2. `create_agent` with minimal config (`name`, `agent_type="sdk"`, `provider="sdk"`) produces SDKAgent with default options
  3. `create_agent` with full SDK config (`instructions`, `model`, `allowed_tools`, `cwd`, `setting_sources`, `permission_mode`) maps all fields correctly to `ClaudeAgentOptions`
  4. `create_agent` with no `permission_mode` in config → defaults to `"acceptEdits"`
  5. `create_agent` with `credentials={"mode": "client"}` → SDKAgent created with mode `"client"`
  6. `create_agent` with API-only fields (`api_key="sk-..."`, `auth_token="tok"`) → fields silently ignored, valid agent created
  7. `validate_credentials` returns `True` when `claude_agent_sdk` is importable
  8. `validate_credentials` returns `False` when import fails (mock `importlib` or use `unittest.mock.patch`)

**Success Criteria**:
- [x] All provider tests pass via `uv run pytest tests/providers/sdk/test_provider.py`
- [x] Options mapping is verified for each AgentConfig field
- [x] Default permission mode is verified
- [x] Mode selection from credentials dict is verified

---

### Task 5: Implement SDKAgent — Query Mode
**Owner**: Junior AI
**Dependencies**: Tasks 1, 3
**Effort**: 3/5
**Objective**: Implement `SDKAgent` in `src/orchestration/providers/sdk/agent.py` with one-shot query mode.

**Steps**:
- [x] Replace the stub in `src/orchestration/providers/sdk/agent.py`
- [x] Import required types:
  ```python
  from __future__ import annotations
  from collections.abc import AsyncIterator
  from claude_agent_sdk import (
      query as sdk_query,
      ClaudeAgentOptions,
      ClaudeSDKClient,
      ClaudeSDKError,
      CLINotFoundError,
      CLIConnectionError,
      ProcessError,
      CLIJSONDecodeError,
  )
  from orchestration.core.models import AgentState, Message
  from orchestration.providers.errors import (
      ProviderError,
      ProviderAuthError,
      ProviderAPIError,
  )
  from orchestration.providers.sdk.translation import translate_sdk_message
  from orchestration.logging import get_logger
  ```
- [x] Implement `SDKAgent.__init__(self, name: str, options: ClaudeAgentOptions, mode: str = "query")`:
  - Store `_name`, `_options`, `_mode`
  - Initialize `_state = AgentState.idle`
  - Initialize `_client: ClaudeSDKClient | None = None`
  - Create logger: `self._log = get_logger(f"orchestration.providers.sdk.agent.{name}")`
- [x] Implement properties: `name` → `self._name`, `agent_type` → `"sdk"`, `state` → `self._state`
- [x] Implement `handle_message` for query mode:
  ```python
  async def handle_message(self, message: Message) -> AsyncIterator[Message]:
      self._state = AgentState.processing
      try:
          async for sdk_msg in sdk_query(prompt=message.content, options=self._options):
              translated = translate_sdk_message(sdk_msg, sender=self._name)
              # translate_sdk_message returns Message, list[Message], or None
              # depending on Task 1 design — yield each non-None result
              ...
          self._state = AgentState.idle
      except CLINotFoundError as e:
          self._state = AgentState.failed
          raise ProviderAuthError(str(e)) from e
      except ProcessError as e:
          self._state = AgentState.failed
          raise ProviderAPIError(str(e), status_code=getattr(e, "exit_code", None)) from e
      except (CLIConnectionError, CLIJSONDecodeError, ClaudeSDKError) as e:
          self._state = AgentState.failed
          raise ProviderError(str(e)) from e
  ```
- [x] Implement `shutdown` (no-op for query mode since there's no persistent client):
  ```python
  async def shutdown(self) -> None:
      self._state = AgentState.terminated
  ```
- [x] Note: `handle_message` is an `async def` that returns `AsyncIterator[Message]` — this means it should be an async generator (uses `yield`). Make sure the function signature and implementation use `yield` to produce Messages.

**Success Criteria**:
- [x] `SDKAgent` has all properties and methods required by the `Agent` Protocol
- [x] Query mode: `handle_message` calls `sdk_query()` with `message.content` as prompt
- [x] Query mode: SDK responses are translated and yielded as orchestration Messages
- [x] State transitions: idle → processing → idle on success, idle → processing → failed on error
- [x] All SDK exception types are caught and mapped to correct orchestration errors
- [x] `shutdown` sets state to terminated

---

### Task 6: Write SDKAgent Query Mode Tests
**Owner**: Junior AI
**Dependencies**: Task 5
**Effort**: 2/5
**Objective**: Create `tests/providers/sdk/test_agent.py` with tests for query mode.

**Steps**:
- [x] Create `tests/providers/sdk/test_agent.py`
- [x] Mock `claude_agent_sdk.query` using `unittest.mock.patch`. The mock should be an async generator:
  ```python
  async def mock_query(*, prompt, options=None):
      # Yield mock SDK messages
      msg = MagicMock()
      msg.__class__ = AssistantMessage
      msg.content = [MagicMock(text="Hello", __class__=TextBlock)]
      yield msg
  ```
- [x] Test cases:
  1. `handle_message` calls `query()` with correct prompt from `message.content`
  2. `handle_message` calls `query()` with the options passed at construction
  3. `handle_message` yields translated Messages (verify sender, content, message_type)
  4. State is `processing` during execution, `idle` after completion
  5. `CLINotFoundError` → raises `ProviderAuthError`, state becomes `failed`
  6. `ProcessError` → raises `ProviderAPIError` with `status_code`, state becomes `failed`
  7. `CLIConnectionError` → raises `ProviderError`, state becomes `failed`
  8. `CLIJSONDecodeError` → raises `ProviderError`, state becomes `failed`
  9. `ClaudeSDKError` (base) → raises `ProviderError`, state becomes `failed`
  10. `shutdown` sets state to `terminated`
  11. Properties: `name` returns configured name, `agent_type` returns `"sdk"`, `state` returns current state
- [x] To test state during execution, you can check state inside the mock or collect it via a side effect

**Success Criteria**:
- [x] All query mode tests pass via `uv run pytest tests/providers/sdk/test_agent.py`
- [x] Happy path (prompt → translated response) is verified
- [x] All five SDK error types are tested with correct mapping
- [x] State transitions are verified

---

### Task 7: Implement SDKAgent — Client Mode
**Owner**: Junior AI
**Dependencies**: Task 5
**Effort**: 2/5
**Objective**: Add multi-turn client mode to `SDKAgent` in `src/orchestration/providers/sdk/agent.py`.

**Steps**:
- [x] Add client mode logic to `handle_message`. The method should branch on `self._mode`:
  ```python
  async def handle_message(self, message: Message) -> AsyncIterator[Message]:
      if self._mode == "client":
          async for msg in self._handle_client_mode(message):
              yield msg
      else:
          async for msg in self._handle_query_mode(message):
              yield msg
  ```
- [x] Extract existing query mode logic into `_handle_query_mode` private method
- [x] Implement `_handle_client_mode`:
  ```python
  async def _handle_client_mode(self, message: Message) -> AsyncIterator[Message]:
      self._state = AgentState.processing
      try:
          if self._client is None:
              self._client = ClaudeSDKClient(options=self._options)
              await self._client.connect()
          await self._client.query(prompt=message.content)
          async for sdk_msg in self._client.receive_response():
              translated = translate_sdk_message(sdk_msg, sender=self._name)
              # yield each non-None result (same pattern as query mode)
              ...
          self._state = AgentState.idle
      except (CLINotFoundError, ...) as e:
          # Same error mapping as query mode
          ...
  ```
- [x] Update `shutdown` to disconnect client if it exists:
  ```python
  async def shutdown(self) -> None:
      if self._client is not None:
          try:
              await self._client.disconnect()
          except Exception:
              pass  # Best-effort cleanup
          self._client = None
      self._state = AgentState.terminated
  ```
- [x] **Important**: Do NOT use `break` to exit `receive_response()` early. Always iterate the full response. Use a flag if you need to track completion.

**Success Criteria**:
- [x] Client mode creates `ClaudeSDKClient` on first `handle_message` call
- [x] Client mode reuses existing client on subsequent calls (verify client is NOT recreated)
- [x] Client calls `connect()` once, then `query()` + `receive_response()` per message
- [x] `shutdown` calls `disconnect()` on client and sets client to None
- [x] `shutdown` is safe to call when no client exists (no-op)
- [x] Error mapping is the same as query mode

---

### Task 8: Write SDKAgent Client Mode Tests
**Owner**: Junior AI
**Dependencies**: Task 7
**Effort**: 2/5
**Objective**: Add client mode tests to `tests/providers/sdk/test_agent.py`.

**Steps**:
- [x] Mock `claude_agent_sdk.ClaudeSDKClient` class. The mock needs:
  - `connect()` — async no-op
  - `query(prompt)` — async no-op (stores prompt, doesn't return)
  - `receive_response()` — async generator yielding mock SDK messages
  - `disconnect()` — async no-op
- [x] Test cases:
  1. First `handle_message` creates client and calls `connect()`
  2. First `handle_message` calls `client.query()` with correct prompt
  3. First `handle_message` iterates `receive_response()` and yields translated Messages
  4. Second `handle_message` reuses same client (does NOT create new one, does NOT call `connect()` again)
  5. Second `handle_message` calls `client.query()` with new prompt
  6. `shutdown` calls `client.disconnect()`
  7. `shutdown` sets `_client` to `None`
  8. `shutdown` when no client exists (query mode or before first message) — no error
  9. Error during `receive_response()` → correct error mapping, state = failed
  10. Error during `connect()` → correct error mapping, state = failed

**Success Criteria**:
- [x] All client mode tests pass
- [x] Client lifecycle (create once, reuse, disconnect on shutdown) is verified
- [x] Error mapping matches query mode behavior

---

### Task 9: Provider Auto-Registration and Re-exports
**Owner**: Junior AI
**Dependencies**: Tasks 3, 7
**Effort**: 1/5
**Objective**: Set up `providers/sdk/__init__.py` to auto-register the provider and export public API.

**Steps**:
- [x] Replace stub in `src/orchestration/providers/sdk/__init__.py` with:
  ```python
  """SDK Agent Provider using claude-agent-sdk."""
  from orchestration.providers.sdk.provider import SDKAgentProvider
  from orchestration.providers.sdk.agent import SDKAgent
  from orchestration.providers.registry import register_provider

  # Auto-register on import
  _provider = SDKAgentProvider()
  register_provider("sdk", _provider)

  __all__ = ["SDKAgentProvider", "SDKAgent"]
  ```
- [x] Verify that `from orchestration.providers.sdk import SDKAgentProvider, SDKAgent` works
- [x] Verify that after import, `get_provider("sdk")` returns the registered instance

**Success Criteria**:
- [x] Importing `orchestration.providers.sdk` registers `"sdk"` in the provider registry
- [x] `get_provider("sdk")` returns an `SDKAgentProvider` instance
- [x] `SDKAgentProvider` and `SDKAgent` are accessible from the package's public API

---

### Task 10: Write Registration Integration Test
**Owner**: Junior AI
**Dependencies**: Task 9
**Effort**: 1/5
**Objective**: Add a test verifying the full registration and agent creation flow.

**Steps**:
- [x] Add to `tests/providers/sdk/test_provider.py` (or create a new `test_registration.py`):
  1. Test: importing `orchestration.providers.sdk` causes `"sdk"` to appear in `list_providers()`
  2. Test: `get_provider("sdk")` returns instance of `SDKAgentProvider`
  3. Test: `get_provider("sdk").provider_type == "sdk"`
  4. Test: full flow — `get_provider("sdk").create_agent(config)` returns an `SDKAgent` (mock the SDK as needed)
- [x] These tests may need to handle registry state carefully — if other tests also import the sdk package, the provider may already be registered. Use a fixture that clears and restores registry state, or verify idempotent registration.

**Success Criteria**:
- [x] Registration flow tests pass
- [x] The provider is discoverable through the registry after import

---

### Task 11: Full Validation Pass
**Owner**: Junior AI
**Dependencies**: All prior tasks
**Effort**: 1/5
**Objective**: Run the complete quality gate and verify the slice is complete.

**Steps**:
- [x] Run `uv run pytest` — all tests pass (including foundation tests — no regressions)
- [x] Run `uv run ruff check src/ tests/` — no linting errors
- [x] Run `uv run ruff format --check src/ tests/` — formatting consistent
- [x] Run type checker — zero errors. Specifically verify:
  - `SDKAgentProvider` structurally satisfies `AgentProvider` Protocol
  - `SDKAgent` structurally satisfies `Agent` Protocol
- [x] Verify import paths:
  - `from orchestration.providers.sdk import SDKAgentProvider, SDKAgent`
  - `from orchestration.providers.sdk.translation import translate_sdk_message`
  - `from orchestration.providers.sdk.provider import SDKAgentProvider`
  - `from orchestration.providers.sdk.agent import SDKAgent`
- [x] Verify that after importing `orchestration.providers.sdk`:
  - `get_provider("sdk")` works
  - `get_provider("sdk").create_agent(AgentConfig(name="test", agent_type="sdk", provider="sdk"))` returns an `SDKAgent`
- [x] Verify no regressions in foundation tests (`tests/test_models.py`, `tests/test_providers.py`, `tests/test_config.py`, `tests/test_logging.py`)

**Success Criteria**:
- [x] All tests pass (new and existing)
- [x] `ruff check` passes
- [x] `ruff format --check` passes
- [x] Type checking passes with zero errors
- [x] Both Protocols are structurally satisfied
- [x] Provider is auto-registered and functional
- [x] Project is ready for slice 3 (Agent Registry & Lifecycle) to begin
