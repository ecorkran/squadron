"""A dispatch waits for background shells and reports the ones it stops (slice 947 D11).

Frame order mirrors the D10 probe logs: the CLI reports ``idle`` while a shell runs, then
on its end sends the terminal frames, ``running``, a continuation turn, and ``idle``.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from squadron.providers.errors import ProviderError
from tests.pipeline.conftest import (
    ScriptedClient,
    scripted_session,
    sdk_result,
    sdk_session_state,
    sdk_task_notification,
    sdk_task_started,
    sdk_task_updated,
    sdk_text,
)

_MOD = "squadron.pipeline.sdk_session"
_SHELL = "local_bash"


def _shell_started(task_id: str = "b1", description: str = "sleep 40") -> object:
    return sdk_task_started(task_id, _SHELL, description)


async def _dispatch(client: ScriptedClient) -> tuple[object, object]:
    session = scripted_session(client)
    reply = await session.dispatch("p")  # type: ignore[attr-defined]
    return session, reply


def _finishes(task_id: str = "b1") -> list[object]:
    """A shell's end as the probe logged it: terminal frames, running, the follow-up turn."""
    return [
        sdk_task_updated(task_id, "completed"),
        sdk_task_notification(task_id),
        sdk_session_state("running"),
        sdk_text("Shell finished."),
        sdk_result(injected=True),
    ]


class TestWaitForShell:
    @pytest.mark.asyncio
    async def test_turn_ending_with_a_shell_running_waits_for_its_follow_up_turn(self) -> None:
        client = ScriptedClient(
            [sdk_session_state("running"), _shell_started(), sdk_text("Started it."), sdk_result()],
            [sdk_session_state("idle"), *_finishes()],
            [sdk_session_state("idle")],
        )

        session, reply = await _dispatch(client)

        assert reply.text == "Started it.\nShell finished."  # type: ignore[attr-defined]
        assert client.receive_calls == 3
        assert session.background_shells_running == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_shell_that_exits_non_zero_is_cleared_by_its_terminal_frame(self) -> None:
        client = ScriptedClient(
            [sdk_session_state("running"), _shell_started(), sdk_text("Started it."), sdk_result()],
            [
                sdk_session_state("idle"),
                sdk_task_updated("b1", "failed"),
                sdk_session_state("running"),
                sdk_text("It failed with status 2."),
                sdk_result(injected=True),
            ],
            [sdk_session_state("idle")],
        )

        _, reply = await _dispatch(client)

        assert reply.text == "Started it.\nIt failed with status 2."  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_without_state_frames_the_ledger_alone_holds_the_dispatch(self) -> None:
        client = ScriptedClient(
            [_shell_started(), sdk_text("Started it."), sdk_result()],
            [sdk_task_notification("b1"), sdk_text("Shell finished."), sdk_result(injected=True)],
        )

        _, reply = await _dispatch(client)

        assert reply.text == "Started it.\nShell finished."  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_the_extra_turn_cost_lands_in_the_dispatch_telemetry(self) -> None:
        client = ScriptedClient(
            [_shell_started(), sdk_text("Started it."), sdk_result(total_cost_usd=0.10)],
            [
                sdk_task_notification("b1"),
                sdk_text("Shell finished."),
                sdk_result(injected=True, total_cost_usd=0.16),
            ],
        )

        _, reply = await _dispatch(client)

        assert reply.telemetry.cost_usd == pytest.approx(0.16)  # type: ignore[attr-defined]


class TestShellReporting:
    @pytest.mark.asyncio
    async def test_shell_that_finishes_leaves_no_warning_and_a_zero_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = ScriptedClient(
            [_shell_started(), sdk_text("Started it."), sdk_result()],
            [sdk_task_notification("b1"), sdk_result(injected=True)],
        )

        with caplog.at_level(logging.WARNING, logger=_MOD):
            session, _ = await _dispatch(client)

        assert session.background_shells_running == 0  # type: ignore[attr-defined]
        assert not [r for r in caplog.records if "background shell" in r.getMessage()]

    @pytest.mark.asyncio
    async def test_shell_outliving_the_bound_is_stopped_and_reported(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = ScriptedClient(
            [_shell_started(description="sleep 100000"), sdk_text("Started it."), sdk_result()],
            [0.15],  # silent past the idle bound: shells emit no progress frames
        )

        with (
            patch(f"{_MOD}.get_typed_config", return_value=0.05),
            caplog.at_level(logging.WARNING, logger=_MOD),
        ):
            session, reply = await _dispatch(client)

        assert reply.text == "Started it."  # type: ignore[attr-defined]
        client.stop_task.assert_awaited_once_with("b1")
        assert session.background_shells_running == 1  # type: ignore[attr-defined]
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "dispatch ended with 1 background shell(s) running: sleep 100000" in m for m in warnings
        )

    @pytest.mark.asyncio
    async def test_shells_do_not_change_the_agent_counts(self) -> None:
        client = ScriptedClient(
            [_shell_started(), sdk_text("Started it."), sdk_result()],
            [0.15],
        )

        with patch(f"{_MOD}.get_typed_config", return_value=0.05):
            session, _ = await _dispatch(client)

        assert session.background_tasks_waited == 0  # type: ignore[attr-defined]
        assert session.background_tasks_stopped == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_stream_ending_with_a_shell_running_raises_naming_it(self) -> None:
        client = ScriptedClient(
            [_shell_started(description="sleep 40"), sdk_text("Started it."), sdk_result()],
            [],  # the stream ends: the shell's end can never arrive
        )

        with pytest.raises(ProviderError, match=r"1 background shell\(s\) still running: sleep 40"):
            await _dispatch(client)

    @pytest.mark.asyncio
    async def test_the_count_resets_on_the_next_dispatch(self) -> None:
        client = ScriptedClient(
            [_shell_started(), sdk_text("Started it."), sdk_result()],
            [0.15],
            [sdk_text("Fresh."), sdk_result()],
        )
        session = scripted_session(client)

        with patch(f"{_MOD}.get_typed_config", return_value=0.05):
            await session.dispatch("one")  # type: ignore[attr-defined]
        assert session.background_shells_running == 1  # type: ignore[attr-defined]
        await session.dispatch("two")  # type: ignore[attr-defined]

        assert session.background_shells_running == 0  # type: ignore[attr-defined]
