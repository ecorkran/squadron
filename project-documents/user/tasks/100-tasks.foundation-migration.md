---
docType: task-breakdown
slice: foundation
project: squadron
lld: user/slices/100-slice.foundation.md
dependencies: []
status: complete
projectState: Foundation slice (v1) fully implemented. Architecture has pivoted to dual-provider model (SDK agents + API agents). This migration brings the implemented code into alignment with the updated 100-arch.orchestration-v2.md.
dateCreated: 20260219
dateUpdated: 20260219
---

## Context Summary

- Working on the **foundation** slice migration — updating implemented code to match the revised architecture
- Foundation v1 is fully implemented and passing all checks (see 100-tasks.foundation.md, all tasks complete)
- Architecture has changed: `LLMProvider` Protocol replaced by `Agent` + `AgentProvider` Protocols; `Agent` Pydantic model renamed to `AgentConfig`; `ProviderConfig` absorbed into `AgentConfig`; provider registry retyped
- New additions: `claude-agent-sdk` dependency, `providers/errors.py`, `providers/sdk/` and `providers/anthropic/` subdirectories
- After migration, next slice is **SDK Agent Provider** (slice 2)
- **Task ordering**: test-with pattern — each change is immediately followed by its test updates

### What Exists (implemented in v1)
- `src/orchestration/core/models.py`: `AgentState`, `MessageType`, `TopologyType` enums; `Agent`, `Message`, `ProviderConfig`, `TopologyConfig` models
- `src/orchestration/providers/base.py`: `LLMProvider` Protocol
- `src/orchestration/providers/registry.py`: dict-based registry mapping `str` → factory callables, `register_provider`, `get_provider`, `list_providers`
- `src/orchestration/config.py`: `Settings` with `ORCH_` prefix env vars
- `src/orchestration/logging.py`: `get_logger`, JSON/text formatters
- `tests/test_models.py`, `tests/test_providers.py`, `tests/test_config.py`, `tests/test_logging.py`
- Stub modules for core/, adk/, cli/, server/, mcp/
- `.env.example`, `py.typed`, type checker configured

### What Changes
- `Agent` model → renamed to `AgentConfig`, fields adjusted for dual-provider support
- `ProviderConfig` model → removed, absorbed into `AgentConfig`
- `LLMProvider` Protocol → replaced by `Agent` Protocol + `AgentProvider` Protocol
- Provider registry → retyped from factory callables to `AgentProvider` instances
- New: `providers/errors.py` (shared error hierarchy)
- New: `providers/sdk/` and `providers/anthropic/` subdirectories (stubs)
- New dependency: `claude-agent-sdk`
- Settings gains new fields for SDK and auth token support
- `.env.example` updated
- Stub docstrings updated for new slice numbers

---

## Tasks

### Task 1: Add claude-agent-sdk Dependency
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1/5
**Objective**: Add `claude-agent-sdk` to project dependencies.

**Steps**:
- [x] Run `uv add claude-agent-sdk`
- [x] Verify `uv sync` completes without errors
- [x] Verify the package is importable: `python -c "import claude_agent_sdk"` (or check the actual import name — the package may use a different module name; check with `uv run python -c "import claude_code_sdk"` as well)

**Success Criteria**:
- [x] `claude-agent-sdk` appears in `pyproject.toml` dependencies
- [x] `uv sync` succeeds
- [x] The package is importable from the virtual environment

---

### Task 2: Add Provider Subdirectories
**Owner**: Junior AI
**Dependencies**: Task 1
**Effort**: 1/5
**Objective**: Create `providers/sdk/` and `providers/anthropic/` subdirectory structure with stub modules. These will be populated by slices 2 and 6 respectively.

**Steps**:
- [x] Create `src/orchestration/providers/sdk/__init__.py` — stub with docstring: "SDK Agent Provider using claude-agent-sdk. Populated in slice 2."
- [x] Create `src/orchestration/providers/sdk/provider.py` — stub with docstring: "SDKAgentProvider implementation. Creates and manages SDK-based agents."
- [x] Create `src/orchestration/providers/sdk/agent.py` — stub with docstring: "SDKAgent implementation. Wraps claude-agent-sdk query/client for task execution."
- [x] Create `src/orchestration/providers/anthropic/__init__.py` — stub with docstring: "Anthropic API Provider using anthropic SDK. Populated in slice 6."
- [x] Create `src/orchestration/providers/anthropic/provider.py` — stub with docstring: "AnthropicAPIProvider implementation. Creates and manages API-based agents."
- [x] Create `src/orchestration/providers/anthropic/agent.py` — stub with docstring: "AnthropicAPIAgent implementation. Wraps anthropic SDK for conversational agents."
- [x] Verify all new stubs are importable:
  - `from orchestration.providers.sdk import provider, agent`
  - `from orchestration.providers.anthropic import provider, agent`

**Success Criteria**:
- [x] Both subdirectories exist with `__init__.py`, `provider.py`, and `agent.py`
- [x] All stub modules contain descriptive docstrings
- [x] All stubs are importable

---

### Task 3: Create Shared Error Hierarchy
**Owner**: Junior AI
**Dependencies**: Task 2
**Effort**: 1/5
**Objective**: Create `src/orchestration/providers/errors.py` with the shared exception hierarchy that all providers will use.

**Steps**:
- [x] Create `src/orchestration/providers/errors.py`
- [x] Define exception classes:
  ```python
  class ProviderError(Exception):
      """Base exception for all provider errors."""

  class ProviderAuthError(ProviderError):
      """Authentication or credential errors."""

  class ProviderAPIError(ProviderError):
      """Errors from the underlying LLM API (rate limits, server errors, etc.)."""
      def __init__(self, message: str, status_code: int | None = None):
          super().__init__(message)
          self.status_code = status_code

  class ProviderTimeoutError(ProviderError):
      """Request timeout errors."""
  ```
- [x] Export all error classes from `src/orchestration/providers/__init__.py`

**Success Criteria**:
- [x] `from orchestration.providers.errors import ProviderError, ProviderAuthError, ProviderAPIError, ProviderTimeoutError` works
- [x] `ProviderAuthError` and `ProviderAPIError` are subclasses of `ProviderError`
- [x] `ProviderAPIError` accepts optional `status_code`

---

### Task 4: Migrate Core Models
**Owner**: Junior AI
**Dependencies**: Task 3
**Effort**: 2/5
**Objective**: In `src/orchestration/core/models.py`, rename `Agent` to `AgentConfig`, remove `ProviderConfig`, and adjust fields for dual-provider support.

This is the most impactful change. The name `Agent` is now reserved for the runtime Protocol (Task 6). The Pydantic model becomes `AgentConfig` — it's what you pass to a provider to create an agent.

**Steps**:
- [x] Rename the `Agent` class to `AgentConfig`
- [x] Update `AgentConfig` fields to:
  ```python
  class AgentConfig(BaseModel):
      """Configuration for creating an agent instance."""
      name: str
      agent_type: str  # "sdk" or "api"
      provider: str  # "sdk", "anthropic", "openai", etc.
      model: str | None = None  # None for SDK agents (uses Claude Code default)
      instructions: str | None = None  # system prompt, optional
      api_key: str | None = None
      auth_token: str | None = None
      base_url: str | None = None
      cwd: str | None = None  # SDK agents: working directory
      setting_sources: list[str] | None = None  # SDK agents: e.g. ["project"]
      allowed_tools: list[str] | None = None  # SDK agents: tool whitelist
      permission_mode: str | None = None  # SDK agents: permission handling
      credentials: dict[str, Any] = Field(default_factory=dict)  # generic provider-specific creds
  ```
- [x] Remove the `ProviderConfig` class entirely
- [x] Remove `id`, `state`, and `created_at` from the config model — these are runtime state, now tracked by the Agent Protocol implementation or the agent registry
- [x] Update `__init__.py` exports in `orchestration/core/models.py` if there are any `__all__` definitions
- [x] Update any imports in other files that reference `Agent` or `ProviderConfig` from models (check `providers/registry.py`, `providers/base.py`, `config.py`)

**Success Criteria**:
- [x] `from orchestration.core.models import AgentConfig` works
- [x] `from orchestration.core.models import Agent` raises ImportError (name is freed for Protocol)
- [x] `from orchestration.core.models import ProviderConfig` raises ImportError (removed)
- [x] `AgentConfig(name="test", agent_type="sdk", provider="sdk")` validates successfully
- [x] `AgentConfig(name="test", agent_type="api", provider="anthropic", model="claude-sonnet-4-20250514")` validates successfully
- [x] `AgentState`, `MessageType`, `TopologyType` enums are unchanged
- [x] `Message` and `TopologyConfig` models are unchanged

---

### Task 5: Update Model Tests
**Owner**: Junior AI
**Dependencies**: Task 4
**Effort**: 2/5
**Objective**: Update `tests/test_models.py` to test the new `AgentConfig` model and remove tests for the old `Agent` and `ProviderConfig` models.

**Steps**:
- [x] Remove all tests for the old `Agent` Pydantic model (creation, defaults, validation)
- [x] Remove all tests for `ProviderConfig`
- [x] Add tests for `AgentConfig`:
  1. Creation with minimal required fields (`name`, `agent_type`, `provider`)
  2. Creation with SDK-specific fields (`cwd`, `setting_sources`, `allowed_tools`, `permission_mode`)
  3. Creation with API-specific fields (`model`, `api_key`, `auth_token`, `base_url`)
  4. Optional fields default to `None` or empty dict
  5. JSON serialization/deserialization round-trip
- [x] Verify existing enum tests (`AgentState`, `MessageType`, `TopologyType`) still pass unchanged
- [x] Verify existing `Message` and `TopologyConfig` tests still pass unchanged

**Success Criteria**:
- [x] All model tests pass via `uv run pytest tests/test_models.py`
- [x] No references to old `Agent` model or `ProviderConfig` in test file
- [x] `AgentConfig` has full test coverage for required fields, optional fields, and serialization

---

### Task 6: Replace LLMProvider with Agent and AgentProvider Protocols
**Owner**: Junior AI
**Dependencies**: Task 4
**Effort**: 2/5
**Objective**: Replace the `LLMProvider` Protocol in `src/orchestration/providers/base.py` with `Agent` and `AgentProvider` Protocols matching the HLD.

**Steps**:
- [x] Remove the `LLMProvider` Protocol class
- [x] Define the `Agent` Protocol:
  ```python
  class Agent(Protocol):
      """A participant that can receive and produce messages."""
      @property
      def name(self) -> str: ...
      @property
      def agent_type(self) -> str: ...  # "sdk" | "api"
      @property
      def state(self) -> AgentState: ...

      async def handle_message(self, message: Message) -> AsyncIterator[Message]: ...
      async def shutdown(self) -> None: ...
  ```
- [x] Define the `AgentProvider` Protocol:
  ```python
  class AgentProvider(Protocol):
      """Creates and manages agents of a specific type."""
      @property
      def provider_type(self) -> str: ...  # "sdk" | "anthropic" | "openai" | ...

      async def create_agent(self, config: AgentConfig) -> Agent: ...
      async def validate_credentials(self) -> bool: ...
  ```
- [x] Ensure imports are correct: `AgentState` and `Message` from `orchestration.core.models`, `AgentConfig` from `orchestration.core.models`, `AsyncIterator` from `collections.abc`
- [x] Export both Protocols from `providers/__init__.py` if applicable

**Success Criteria**:
- [x] `from orchestration.providers.base import Agent, AgentProvider` works
- [x] `from orchestration.providers.base import LLMProvider` raises ImportError (removed)
- [x] Both are `Protocol` classes (structural typing)
- [x] `Agent` defines `name`, `agent_type`, `state` properties and `handle_message`, `shutdown` methods
- [x] `AgentProvider` defines `provider_type` property and `create_agent`, `validate_credentials` methods

---

### Task 7: Retype Provider Registry
**Owner**: Junior AI
**Dependencies**: Task 6
**Effort**: 1/5
**Objective**: Update `src/orchestration/providers/registry.py` to map provider type names to `AgentProvider` instances instead of factory callables.

**Steps**:
- [x] Change the registry dict type from `dict[str, Callable]` to `dict[str, AgentProvider]`
- [x] Update `register_provider(name: str, provider: AgentProvider)` — accepts an `AgentProvider` instance, not a factory
- [x] Update `get_provider(name: str) -> AgentProvider` — returns the registered instance directly (no factory invocation, no config parameter)
- [x] `list_providers() -> list[str]` — unchanged
- [x] Update imports: replace `LLMProvider` / `ProviderConfig` references with `AgentProvider`

**Success Criteria**:
- [x] `register_provider("sdk", some_provider_instance)` stores the instance
- [x] `get_provider("sdk")` returns the stored `AgentProvider` instance
- [x] `get_provider("nonexistent")` raises a clear error
- [x] `list_providers()` returns registered provider type names
- [x] No references to `LLMProvider`, `ProviderConfig`, or factory callables remain

---

### Task 8: Update Provider Tests
**Owner**: Junior AI
**Dependencies**: Task 7
**Effort**: 1/5
**Objective**: Update `tests/test_providers.py` to test the retyped registry with `AgentProvider` instances.

**Steps**:
- [x] Create a minimal mock class satisfying the `AgentProvider` Protocol (can use a simple class with `provider_type` property, stub `create_agent`, stub `validate_credentials`)
- [x] Update registration test: register a mock `AgentProvider`, verify it's stored
- [x] Update lookup test: `get_provider` returns the registered instance directly
- [x] Update error test: `get_provider` for unregistered name raises error
- [x] Update listing test: `list_providers` returns names
- [x] Remove any tests that reference `LLMProvider`, `ProviderConfig`, or factory callables

**Success Criteria**:
- [x] All provider tests pass via `uv run pytest tests/test_providers.py`
- [x] Tests use mock `AgentProvider` instances, not factories
- [x] No references to old types remain

---

### Task 9: Update Settings
**Owner**: Junior AI
**Dependencies**: Task 7
**Effort**: 1/5
**Objective**: Add new fields to `src/orchestration/config.py` for SDK agent support and auth token authentication.

**Steps**:
- [x] Add new fields to `Settings`:
  - `default_agent_type`: `str` = `"sdk"` — default agent type when spawning
  - `anthropic_auth_token`: `str | None` = `None` — for bearer token auth
  - `anthropic_base_url`: `str | None` = `None` — for proxy/gateway configs
- [x] Update `default_provider` default value from `"anthropic"` to `"sdk"` — SDK agents are now the primary provider
- [x] Keep all existing fields (`anthropic_api_key`, `log_level`, `log_format`, `host`, `port`, etc.)

**Success Criteria**:
- [x] `Settings()` produces valid defaults including `default_agent_type="sdk"` and `default_provider="sdk"`
- [x] `ORCH_ANTHROPIC_AUTH_TOKEN=test` is picked up
- [x] `ORCH_ANTHROPIC_BASE_URL=http://localhost:4000` is picked up
- [x] `ORCH_DEFAULT_AGENT_TYPE=api` overrides the default
- [x] All previously existing settings still work

---

### Task 10: Update Config Tests
**Owner**: Junior AI
**Dependencies**: Task 9
**Effort**: 1/5
**Objective**: Update `tests/test_config.py` to cover new Settings fields.

**Steps**:
- [x] Add test: `default_agent_type` defaults to `"sdk"`
- [x] Add test: `default_provider` defaults to `"sdk"`
- [x] Add test: `ORCH_ANTHROPIC_AUTH_TOKEN` env var is picked up
- [x] Add test: `ORCH_ANTHROPIC_BASE_URL` env var is picked up
- [x] Verify existing config tests still pass (update any that assert `default_provider == "anthropic"`)

**Success Criteria**:
- [x] All config tests pass via `uv run pytest tests/test_config.py`
- [x] New fields have test coverage

---

### Task 11: Update .env.example
**Owner**: Junior AI
**Dependencies**: Task 9
**Effort**: 1/5
**Objective**: Update `.env.example` with new configuration variables.

**Steps**:
- [x] Add section header: `# Agent Defaults`
- [x] Add `ORCH_DEFAULT_AGENT_TYPE=sdk` with comment
- [x] Update `ORCH_DEFAULT_PROVIDER=sdk` (was `anthropic`)
- [x] Add to Anthropic section:
  - `ORCH_ANTHROPIC_AUTH_TOKEN=` with comment: "Bearer token auth (alternative to API key, for proxy/gateway configs)"
  - `ORCH_ANTHROPIC_BASE_URL=` with comment: "Base URL override (for LiteLLM proxy or custom gateway)"
- [x] Keep all existing entries

**Success Criteria**:
- [x] `.env.example` documents all Settings fields including new ones
- [x] Comments explain purpose and defaults
- [x] Logical grouping is maintained

---

### Task 12: Update Stub Docstrings
**Owner**: Junior AI
**Dependencies**: Task 2
**Effort**: 1/5
**Objective**: Update stub module docstrings to reference the correct slice numbers from the revised slice plan.

**Steps**:
- [x] `core/message_bus.py` — update from "Populated in slice 4" to "Populated in slice 5"
- [x] `core/topology.py` — update from "Populated in slice 10" to "Populated in slice 9"
- [x] `core/supervisor.py` — update from "Populated in slice 6" to correct slice (supervisor is not a numbered slice in the current plan — update docstring to: "Supervisor for agent health monitoring and restart strategies.")
- [x] `cli/__init__.py` — update from "Populated in slice 5" to "Populated in slice 4"
- [x] `server/__init__.py` — update from "Populated in slice 14" to "Populated in slice 13"
- [x] `mcp/__init__.py` — update from "Populated in slice 13" to "Populated in slice 12"
- [x] `adk/__init__.py` — update from "Populated in slice 12" to "Populated in slice 11"
- [x] `core/agent_registry.py` — verify it says "Populated in slice 3" (unchanged)

**Success Criteria**:
- [x] All stub docstrings reference correct slice numbers per `100-slices.orchestration-v2.md`
- [x] No stale slice number references remain

---

### Task 13: Full Validation Pass
**Owner**: Junior AI
**Dependencies**: All prior tasks
**Effort**: 1/5
**Objective**: Run the complete quality gate and verify the migration is complete.

**Steps**:
- [x] Run `uv run pytest` — all tests pass
- [x] Run `uv run ruff check src/ tests/` — no linting errors
- [x] Run `uv run ruff format --check src/ tests/` — formatting consistent
- [x] Run type checker — zero errors
- [x] Verify updated import paths work:
  - `from orchestration.core.models import AgentConfig, Message, AgentState, MessageType, TopologyConfig`
  - `from orchestration.providers.base import Agent, AgentProvider`
  - `from orchestration.providers.errors import ProviderError, ProviderAuthError, ProviderAPIError, ProviderTimeoutError`
  - `from orchestration.providers.registry import register_provider, get_provider, list_providers`
  - `from orchestration.config import Settings`
  - `from orchestration.logging import get_logger`
- [x] Verify old import paths are gone:
  - `from orchestration.core.models import Agent` should fail (Agent is now a Protocol in providers.base)
  - `from orchestration.core.models import ProviderConfig` should fail
  - `from orchestration.providers.base import LLMProvider` should fail

**Success Criteria**:
- [x] All tests pass
- [x] `ruff check` passes
- [x] `ruff format --check` passes
- [x] Type checking passes with zero errors
- [x] All new import paths verified working
- [x] All old import paths verified removed
- [x] Project is ready for slice 2 (SDK Agent Provider) to begin
