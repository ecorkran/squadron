---
slice: openai-provider-core
project: squadron
lld: project-documents/user/slices/111-slice.openai-provider-core.md
dependencies: [foundation]
projectState: M1 complete and published. Review workflows and M1 polish done. SDK provider, agent registry, and CLI all operational. Expanding to multi-provider support.
status: complete
dateCreated: 20260226
dateUpdated: 20260226
---

## Context Summary

- Working on **openai-provider-core** (slice 111)
- Implements `OpenAICompatibleProvider` and `OpenAICompatibleAgent` against the OpenAI Chat Completions API
- Single implementation covers OpenAI, OpenRouter, Ollama/vLLM, and Gemini-compatible endpoints via `base_url`
- Validates that `AgentProvider` Protocol generalizes beyond Anthropic — no core engine changes required
- Also fixes a provider auto-loader gap in `spawn.py` and adds `--base-url` CLI flag
- Depends on Foundation slice only
- Next slice: 112 (Provider Variants & Registry — OpenRouter, local, Gemini configs + model alias profiles)
- Full design: `project-documents/user/slices/111-slice.openai-provider-core.md`

---

## Tasks

- [x] **T1: Add openai dependency**
  - [x] Add `openai>=1.0.0` to `pyproject.toml` `[project.dependencies]` list
  - [x] Run `uv sync` to install; resolve any conflicts
  - [x] Success: `python -c "import openai; print(openai.__version__)"` prints a version ≥ 1.0.0

- [x] **T2: Create test infrastructure for providers/openai**
  - [x] Create `tests/providers/openai/__init__.py` (empty)
  - [x] Create `tests/providers/openai/conftest.py` with:
    - [x] `mock_async_openai` fixture — `MagicMock` of `AsyncOpenAI` with `chat.completions.create` set to `AsyncMock`; `close` set to `AsyncMock`
    - [x] `text_chunk(content)` factory — returns a minimal `ChatCompletionChunk` with `delta.content` set and `delta.tool_calls` as `None`
    - [x] `tool_chunk(index, id, name, args_fragment)` factory — returns a `ChatCompletionChunk` with `delta.tool_calls` populated
  - [x] Success: `pytest tests/providers/openai/` runs (0 tests, 0 errors)

- [x] **T3: Implement translation.py**
  - [x] Create `src/orchestration/providers/openai/translation.py`
  - [x] `build_text_message(text, agent_name, model) -> Message | None` — returns a `chat` Message; returns `None` if text is empty/whitespace
  - [x] `build_tool_call_message(tool_call: dict, agent_name) -> Message` — returns a `system` Message; metadata: `{"provider": "openai", "type": "tool_call", "tool_call_id": ..., "tool_name": ..., "tool_arguments": ...}`
  - [x] `build_messages(text_buffer, tool_calls_list, agent_name, model) -> list[Message]` — calls both builders; text message first (if non-empty), then tool call messages
  - [x] Success: module importable; all three functions present with correct signatures

- [x] **T4: Test translation.py**
  - [x] `test_build_text_message_non_empty` — returns chat Message with correct content, sender=agent_name, recipients=["all"], metadata has provider and model
  - [x] `test_build_text_message_empty_returns_none` — empty string → `None`
  - [x] `test_build_tool_call_message_metadata` — all four metadata keys present with correct values
  - [x] `test_build_messages_text_only` — text set, no tool calls → one chat Message
  - [x] `test_build_messages_tool_calls_only` — two tool calls, no text → two system Messages, no chat Message
  - [x] `test_build_messages_mixed` — text + one tool call → chat Message first, system Message second
  - [x] `test_build_messages_empty` — empty text, no tool calls → empty list
  - [x] Success: all tests pass; `ruff check src/orchestration/providers/openai/translation.py` clean

- [x] **T5: Implement provider.py**
  - [x] Create `src/orchestration/providers/openai/provider.py`
  - [x] `OpenAICompatibleProvider` class:
    - [x] `provider_type` property → `"openai"`
    - [x] `create_agent(config)` — resolve API key: `config.api_key` → `os.environ.get("OPENAI_API_KEY")` → raise `ProviderAuthError`; raise `ProviderError` if `config.model is None`; construct `AsyncOpenAI(api_key=..., base_url=config.base_url)`; return `OpenAICompatibleAgent`
    - [x] `validate_credentials()` — check `openai` importable AND `OPENAI_API_KEY` env var is set; return bool, never raise
  - [x] Success: class satisfies `AgentProvider` Protocol; pyright reports no errors on this module

- [x] **T6: Test provider.py**
  - [x] `test_provider_type` — `provider_type == "openai"`
  - [x] `test_create_agent_uses_config_api_key` — `config.api_key` set → passed to `AsyncOpenAI` constructor
  - [x] `test_create_agent_falls_back_to_env_var` — `config.api_key` None, env var set → uses env var
  - [x] `test_create_agent_raises_auth_error_no_key` — neither source has a key → `ProviderAuthError`
  - [x] `test_create_agent_raises_error_model_none` — `config.model` is None → `ProviderError`
  - [x] `test_create_agent_passes_base_url` — `config.base_url` set → `AsyncOpenAI` constructed with it
  - [x] `test_validate_credentials_true` — package importable, env var set → True
  - [x] `test_validate_credentials_false_no_env` — env var absent → False; no exception raised
  - [x] Success: all tests pass; ruff clean

- [x] **T7: Implement agent.py**
  - [x] Create `src/orchestration/providers/openai/agent.py`
  - [x] `OpenAICompatibleAgent.__init__(name, client, model, system_prompt)`:
    - [x] `_history: list[dict[str, Any]] = []`; append system entry if `system_prompt` is not None
    - [x] `_state = AgentState.idle`
  - [x] Properties: `name`, `agent_type` → `"api"`, `state`
  - [x] `handle_message(message)` as async generator:
    1. [x] State → `processing`; append user entry to `_history`
    2. [x] Call `client.chat.completions.create(model=..., messages=_history, stream=True)`
    3. [x] Iterate stream: accumulate `delta.content` into text buffer; accumulate `delta.tool_calls` fragments by `index` into a dict
    4. [x] After stream ends, flatten accumulated tool_calls dict into ordered list
    5. [x] Call `translation.build_messages(text, tool_calls, name, model)` and yield each Message
    6. [x] Append assistant turn to `_history` (text content and/or tool_calls in OpenAI assistant format)
    7. [x] In `finally`: state → `idle`
    8. [x] Map openai exceptions → ProviderError hierarchy (see slice design §Error Mapping table)
  - [x] `shutdown()` — `await self._client.close()`; state → `terminated`
  - [x] Success: class satisfies `Agent` Protocol; pyright reports no errors on this module

- [x] **T8: Test agent.py**
  - [x] `test_initial_state_is_idle`
  - [x] `test_system_prompt_prepended_to_history` — system_prompt set → `_history[0]["role"] == "system"`
  - [x] `test_no_system_prompt_history_empty` — no system_prompt → history empty before first message
  - [x] `test_handle_message_appends_user_entry` — after call, history contains user entry
  - [x] `test_handle_message_appends_assistant_entry` — after call, history contains assistant entry
  - [x] `test_handle_message_yields_chat_message` — text stream → one chat Message yielded
  - [x] `test_handle_message_multi_turn_history_grows` — two sequential calls → history has user, assistant, user, assistant entries
  - [x] `test_handle_message_yields_system_for_tool_call` — tool_call stream → one system Message yielded
  - [x] `test_state_is_idle_after_success` — state returns to idle after handle_message completes
  - [x] `test_error_auth` — `openai.AuthenticationError` raised → `ProviderAuthError`; state returns to idle
  - [x] `test_error_rate_limit` — `openai.RateLimitError` → `ProviderAPIError` with `status_code=429`
  - [x] `test_error_api_status` — `openai.APIStatusError(status_code=503)` → `ProviderAPIError(status_code=503)`
  - [x] `test_error_connection` — `openai.APIConnectionError` → `ProviderError`
  - [x] `test_error_timeout` — `openai.APITimeoutError` → `ProviderTimeoutError`
  - [x] `test_shutdown_closes_client_and_sets_terminated` — `shutdown()` calls `client.close()`; state → terminated
  - [x] Success: all tests pass; ruff clean

- [x] **T9: Implement __init__.py (auto-registration)**
  - [x] Create `src/orchestration/providers/openai/__init__.py`
  - [x] Instantiate `_provider = OpenAICompatibleProvider()`; call `register_provider("openai", _provider)`
  - [x] Set `__all__ = ["OpenAICompatibleProvider", "OpenAICompatibleAgent"]`
  - [x] Success: importing `orchestration.providers.openai` succeeds; `get_provider("openai")` returns the instance

- [x] **T10: Test registration**
  - [x] Follow pattern from `tests/providers/sdk/test_registration.py` (clean-registry fixture)
  - [x] `test_openai_in_list_after_import` — import module → "openai" in `list_providers()`
  - [x] `test_get_provider_returns_openai_provider` — `isinstance(get_provider("openai"), OpenAICompatibleProvider)`
  - [x] `test_provider_type_is_openai`
  - [x] Success: all tests pass; `pytest tests/providers/openai/` fully green

- [x] **T11: Commit providers/openai**
  - [x] `pytest tests/providers/openai/` — all green
  - [x] `ruff check src/orchestration/providers/openai/` — clean
  - [x] `pyright src/orchestration/providers/openai/` — zero errors
  - [x] `git add` new provider files and test files; commit: `feat: add OpenAI-compatible provider`

- [x] **T12: Add provider auto-loader to spawn.py**
  - [x] Add `_load_provider(name: str) -> None` to `src/orchestration/cli/commands/spawn.py`; uses `importlib.import_module(f"orchestration.providers.{name}")` in try/except ImportError (silent)
  - [x] Call `_load_provider(config.provider)` in `_spawn()` before `registry.spawn(config)`
  - [x] Success: existing `pytest tests/cli/test_spawn.py` still passes unchanged

- [x] **T13: Test provider auto-loader**
  - [x] `test_load_provider_calls_import_module` — patch `importlib.import_module`; call `_load_provider("openai")`; verify called with `"orchestration.providers.openai"`
  - [x] `test_load_provider_silences_import_error` — patch import_module to raise ImportError; call `_load_provider`; no exception propagates
  - [x] `test_spawn_triggers_load_provider` — patch `_load_provider` and `get_registry`; invoke spawn; verify `_load_provider` called with the provider name
  - [x] Success: all tests pass; ruff clean

- [x] **T14: Add --base-url flag to spawn.py**
  - [x] Add `base_url: str | None = typer.Option(None, "--base-url", help="Base URL for OpenAI-compatible endpoints (e.g. http://localhost:11434/v1)")` to `spawn()` signature
  - [x] Pass `base_url=base_url` to `AgentConfig(...)` constructor
  - [x] Success: `orchestration spawn --help` shows `--base-url` option; existing spawn tests pass

- [x] **T15: Test --base-url flag**
  - [x] `test_base_url_passed_to_agent_config` — invoke spawn with `--base-url http://localhost:11434/v1`; verify `AgentConfig.base_url` matches in the `registry.spawn` call
  - [x] `test_base_url_defaults_to_none` — spawn without `--base-url`; `AgentConfig.base_url` is None
  - [x] Success: both tests pass; ruff clean on spawn.py

- [x] **T16: Full validation pass**
  - [x] `pytest` (full suite) — all green, no errors
  - [x] `ruff check src/` — clean
  - [x] `pyright src/` — zero errors
  - [x] Success: all three checks pass

- [x] **T17: Commit CLI changes**
  - [x] `git add` spawn.py and T12-T15 test files
  - [x] Commit: `feat: add provider auto-loader and --base-url to spawn command`
  - [x] Success: `git status` clean; `orchestration spawn --help` shows `--base-url`

---

## Implementation Notes

- **AsyncOpenAI mock**: `client.chat.completions.create` is called with `stream=True`. The return value must be async-iterable (implement `__aiter__`). Use `AsyncMock` with `__aiter__` returning an async iterator over synthetic chunks.
- **Tool call accumulation**: OpenAI streams tool calls as chunks with an `index` field. Each chunk adds content to the call at that index. Accumulate into `dict[int, dict]`, then flatten to list after stream ends. Prefer the SDK's `stream.get_final_message()` helper if it simplifies the implementation — see openai SDK docs.
- **History type**: Use `list[dict[str, Any]]` (not `list[dict[str, str]]`) because tool call entries include nested structures.
- **Auto-loader retroactive benefit**: After T12, `orchestration spawn --type sdk` also benefits — the SDK provider module is imported on demand rather than requiring a pre-existing import chain.
