"""Pin the ``openai_codex`` surface squadron uses against the real SDK types.

D1's pin is loose (``>=0.159.3,<1``), so this is the drift alarm: it runs only where
the ``codex`` extra is installed (the CI codex leg) and skips everywhere else.
"""

from __future__ import annotations

import inspect

import pytest

from squadron.core.models import Effort

openai_codex = pytest.importorskip("openai_codex")


def test_client_and_config_names() -> None:
    from openai_codex import AsyncCodex, CodexConfig

    assert CodexConfig(codex_bin="/usr/local/bin/codex").codex_bin == "/usr/local/bin/codex"
    assert CodexConfig().codex_bin is None
    for method in ("thread_start", "login_chatgpt", "login_chatgpt_device_code", "account", "logout"):
        assert callable(getattr(AsyncCodex, method)), method


def test_thread_start_keywords() -> None:
    from openai_codex import AsyncCodex

    params = inspect.signature(AsyncCodex.thread_start).parameters
    for name in ("model", "sandbox", "cwd", "approval_mode", "base_instructions"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY, name


def test_turn_api() -> None:
    from openai_codex import AsyncThread, AsyncTurnHandle

    assert "effort" in inspect.signature(AsyncThread.turn).parameters
    assert callable(AsyncTurnHandle.run)
    assert callable(AsyncTurnHandle.interrupt)


def test_enums() -> None:
    from openai_codex import ApprovalMode, Sandbox
    from openai_codex.types import ReasoningEffort, TurnStatus

    assert Sandbox.read_only.value == "read-only"
    assert ApprovalMode.deny_all
    assert TurnStatus.completed
    assert TurnStatus.interrupted
    for effort in Effort:
        assert ReasoningEffort(effort.value).value == effort.value


def test_error_types() -> None:
    from openai_codex import (
        CodexError,
        CodexRpcError,
        RetryLimitExceededError,
        ServerBusyError,
        TransportClosedError,
    )

    assert issubclass(TransportClosedError, CodexError)
    assert issubclass(CodexRpcError, CodexError)
    assert issubclass(ServerBusyError, CodexRpcError)
    assert issubclass(RetryLimitExceededError, ServerBusyError)


def test_turn_usage_fields() -> None:
    from openai_codex.types import ThreadTokenUsage

    last_fields = ThreadTokenUsage.model_fields["last"].annotation.model_fields  # type: ignore[union-attr]
    for name in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
        assert name in last_fields, name
