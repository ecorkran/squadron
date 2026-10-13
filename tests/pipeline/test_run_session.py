"""Tests for the shared run-session helper (slice 941)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.run_session import pipeline_session


def _classification(*, needs_session: bool) -> MagicMock:
    classification = MagicMock()
    classification.needs_persistent_session = needs_session
    return classification


@pytest.mark.asyncio
async def test_no_session_is_opened_when_none_is_needed() -> None:
    with patch("squadron.pipeline.run_session.open_pipeline_session", new=AsyncMock()) as opener:
        async with pipeline_session(_classification(needs_session=False)) as session:
            assert session is None
    opener.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_is_opened_and_disconnected_on_success() -> None:
    session = MagicMock(disconnect=AsyncMock())
    with patch(
        "squadron.pipeline.run_session.open_pipeline_session", new=AsyncMock(return_value=session)
    ):
        async with pipeline_session(_classification(needs_session=True)) as yielded:
            assert yielded is session
            session.disconnect.assert_not_awaited()
    session.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_is_disconnected_when_the_body_raises() -> None:
    session = MagicMock(disconnect=AsyncMock())
    with patch(
        "squadron.pipeline.run_session.open_pipeline_session", new=AsyncMock(return_value=session)
    ):
        with pytest.raises(RuntimeError, match="boom"):
            async with pipeline_session(_classification(needs_session=True)):
                raise RuntimeError("boom")
    session.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_failed_connect_propagates_before_the_body_runs() -> None:
    ran = False
    with patch(
        "squadron.pipeline.run_session.open_pipeline_session",
        new=AsyncMock(side_effect=ConnectionError("no auth")),
    ):
        with pytest.raises(ConnectionError):
            async with pipeline_session(_classification(needs_session=True)):
                ran = True
    assert not ran
