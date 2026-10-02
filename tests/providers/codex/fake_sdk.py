"""A fake ``openai_codex`` SDK for tests, installed at the import boundary.

Tests that exercise SDK calls patch this fake into ``sys.modules`` so no real
Codex runtime is spawned.
"""

from __future__ import annotations

import types
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from unittest.mock import AsyncMock, MagicMock, patch


class Sandbox(StrEnum):
    read_only = "read-only"
    workspace_write = "workspace-write"
    full_access = "full-access"


class ApprovalMode(StrEnum):
    deny_all = "deny_all"
    auto_review = "auto_review"


class ReasoningEffort(StrEnum):
    none = "none"
    minimal = "minimal"
    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"
    max = "max"


class TurnStatus(StrEnum):
    completed = "completed"
    interrupted = "interrupted"
    failed = "failed"


class CodexError(Exception):
    pass


class TransportClosedError(CodexError):
    pass


class JsonRpcError(CodexError):
    pass


class CodexRpcError(JsonRpcError):
    pass


class ServerBusyError(CodexRpcError):
    pass


class RetryLimitExceededError(ServerBusyError):
    pass


@dataclass
class CodexConfig:
    codex_bin: str | None = None


@dataclass
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0


@dataclass
class ThreadTokenUsage:
    last: Usage = field(default_factory=Usage)


@dataclass
class TurnResult:
    final_response: str | None = "Codex response"
    status: TurnStatus = TurnStatus.completed
    usage: ThreadTokenUsage | None = None


@dataclass
class FakeSdk:
    """Handles on the fake SDK objects a test configures or asserts on."""

    module: types.ModuleType
    async_codex: MagicMock
    client: AsyncMock
    thread: AsyncMock
    turn: AsyncMock


def _build_fake_sdk() -> FakeSdk:
    turn = AsyncMock()
    turn.run = AsyncMock(return_value=TurnResult())
    thread = AsyncMock()
    thread.run = turn.run
    thread.turn = AsyncMock(return_value=turn)
    client = AsyncMock()
    client.thread_start = AsyncMock(return_value=thread)
    client.__aenter__ = AsyncMock(return_value=client)
    async_codex = MagicMock(return_value=client)

    module = types.ModuleType("openai_codex")
    sdk_types = types.ModuleType("openai_codex.types")
    for name, value in {
        "AsyncCodex": async_codex,
        "CodexConfig": CodexConfig,
        "Sandbox": Sandbox,
        "ApprovalMode": ApprovalMode,
        "CodexError": CodexError,
        "TransportClosedError": TransportClosedError,
        "CodexRpcError": CodexRpcError,
        "ServerBusyError": ServerBusyError,
        "RetryLimitExceededError": RetryLimitExceededError,
    }.items():
        setattr(module, name, value)
    sdk_types.ReasoningEffort = ReasoningEffort  # type: ignore[attr-defined]
    sdk_types.TurnStatus = TurnStatus  # type: ignore[attr-defined]
    module.types = sdk_types  # type: ignore[attr-defined]
    return FakeSdk(module=module, async_codex=async_codex, client=client, thread=thread, turn=turn)


@contextmanager
def installed_fake_sdk() -> Iterator[FakeSdk]:
    """Install a fresh fake SDK in place of ``openai_codex``."""
    sdk = _build_fake_sdk()
    with patch.dict(
        "sys.modules", {"openai_codex": sdk.module, "openai_codex.types": sdk.module.types}
    ):
        yield sdk
