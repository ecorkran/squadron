"""Tests for Codex login, logout, and account summary (SDK faked)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from squadron.providers.codex import login as codex_login
from squadron.providers.errors import ProviderError
from tests.providers.codex.fake_sdk import CodexError, FakeSdk

_AUTH_URL = "https://auth.openai.com/oauth/authorize?state=secret-state"
_DEVICE_URL = "https://auth.openai.com/codex/device"
_USER_CODE = "WXYZ-1234"
_CONFIG = "squadron.providers.codex.login.get_typed_config"


@dataclass
class _Completed:
    success: bool = True
    error: str | None = None


def _handle(**attrs: str) -> SimpleNamespace:
    return SimpleNamespace(
        wait=AsyncMock(return_value=_Completed()),
        cancel=AsyncMock(),
        **attrs,
    )


@pytest.fixture()
def browser_handle(fake_sdk: FakeSdk) -> SimpleNamespace:
    handle = _handle(auth_url=_AUTH_URL)
    fake_sdk.client.login_chatgpt = AsyncMock(return_value=handle)
    return handle


@pytest.fixture()
def device_handle(fake_sdk: FakeSdk) -> SimpleNamespace:
    handle = _handle(verification_url=_DEVICE_URL, user_code=_USER_CODE)
    fake_sdk.client.login_chatgpt_device_code = AsyncMock(return_value=handle)
    return handle


@pytest.fixture(autouse=True)
def _no_real_browser() -> object:
    with patch("squadron.providers.codex.login.webbrowser.open", return_value=True) as opened:
        yield opened


def _login(*, device_code: bool = False, timeout_s: float = 5) -> list[str]:
    notes: list[str] = []
    asyncio.run(codex_login.login(device_code=device_code, timeout_s=timeout_s, notify=notes.append))
    return notes


class TestLogin:
    def test_browser_success(
        self, fake_sdk: FakeSdk, browser_handle: SimpleNamespace, _no_real_browser: AsyncMock
    ) -> None:
        notes = _login()
        assert any(_AUTH_URL in note for note in notes)
        _no_real_browser.assert_called_once_with(_AUTH_URL)
        browser_handle.wait.assert_awaited_once()
        fake_sdk.client.close.assert_awaited_once()

    def test_device_code_success(
        self, fake_sdk: FakeSdk, device_handle: SimpleNamespace, _no_real_browser: AsyncMock
    ) -> None:
        notes = _login(device_code=True)
        assert any(_DEVICE_URL in note and _USER_CODE in note for note in notes)
        _no_real_browser.assert_not_called()
        fake_sdk.client.close.assert_awaited_once()

    def test_unsuccessful_completion_surfaces_error(
        self, fake_sdk: FakeSdk, browser_handle: SimpleNamespace
    ) -> None:
        browser_handle.wait.return_value = _Completed(success=False, error="access denied")
        with pytest.raises(ProviderError, match="access denied"):
            _login()
        fake_sdk.client.close.assert_awaited_once()

    def test_timeout_cancels_handle(self, fake_sdk: FakeSdk, browser_handle: SimpleNamespace) -> None:
        async def never() -> _Completed:
            await asyncio.sleep(10)
            raise AssertionError("wait should have timed out")

        browser_handle.wait.side_effect = never
        with patch(_CONFIG, return_value=5):
            with pytest.raises(ProviderError, match="timed out after 0.01 s"):
                _login(timeout_s=0.01)
        browser_handle.cancel.assert_awaited_once()
        fake_sdk.client.close.assert_awaited_once()

    def test_cancellation_cancels_handle(
        self, fake_sdk: FakeSdk, browser_handle: SimpleNamespace
    ) -> None:
        async def run() -> None:
            task = asyncio.create_task(
                codex_login.login(device_code=False, timeout_s=60, notify=lambda _m: None)
            )
            await asyncio.sleep(0.01)
            task.cancel()
            await task

        async def never() -> _Completed:
            await asyncio.sleep(10)
            raise AssertionError("wait should have been cancelled")

        browser_handle.wait.side_effect = never
        with patch(_CONFIG, return_value=5):
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(run())
        browser_handle.cancel.assert_awaited_once()
        fake_sdk.client.close.assert_awaited_once()

    def test_browser_open_failure_does_not_fail_login(
        self, browser_handle: SimpleNamespace, _no_real_browser: AsyncMock
    ) -> None:
        _no_real_browser.return_value = False
        notes = _login()
        assert any(_AUTH_URL in note for note in notes)

    @pytest.mark.parametrize("device_code", [False, True])
    def test_url_and_code_never_logged(
        self,
        browser_handle: SimpleNamespace,
        device_handle: SimpleNamespace,
        caplog: pytest.LogCaptureFixture,
        device_code: bool,
        _no_real_browser: AsyncMock,
    ) -> None:
        _no_real_browser.return_value = False  # exercise the warning path too
        with caplog.at_level(logging.DEBUG):
            _login(device_code=device_code)
        logged = caplog.text
        for secret in (_AUTH_URL, _DEVICE_URL, _USER_CODE):
            assert secret not in logged


class _PlanType(StrEnum):
    plus = "plus"


def _account(email: str | None = "you@example.com") -> SimpleNamespace:
    details = SimpleNamespace(email=email, plan_type=_PlanType.plus, type="chatgpt")
    return SimpleNamespace(account=SimpleNamespace(root=details), requires_openai_auth=True)


async def _hang() -> None:
    await asyncio.sleep(10)
    raise AssertionError("call should have timed out")


class TestAccountSummary:
    def test_formats_email_and_plan(self, fake_sdk: FakeSdk) -> None:
        fake_sdk.client.account = AsyncMock(return_value=_account())
        assert asyncio.run(codex_login.account_summary()) == "you@example.com, plus"
        fake_sdk.client.close.assert_awaited_once()

    def test_sdk_error_returns_none_and_warns(
        self, fake_sdk: FakeSdk, caplog: pytest.LogCaptureFixture
    ) -> None:
        fake_sdk.client.account = AsyncMock(side_effect=CodexError("rpc failed"))
        with caplog.at_level("WARNING", logger="squadron.providers.codex.login"):
            assert asyncio.run(codex_login.account_summary()) is None
        assert any("account lookup failed" in r.getMessage() for r in caplog.records)

    def test_timeout_returns_none_and_warns(
        self, fake_sdk: FakeSdk, caplog: pytest.LogCaptureFixture
    ) -> None:
        fake_sdk.client.account = AsyncMock(side_effect=_hang)
        with patch(_CONFIG, return_value=0), caplog.at_level("WARNING"):
            assert asyncio.run(codex_login.account_summary()) is None
        assert any("timed out" in r.getMessage() for r in caplog.records)


class TestLoginStartFailure:
    def test_runtime_start_failure_raises_provider_error(self, fake_sdk: FakeSdk) -> None:
        start_error = OSError("codex binary cannot run")
        fake_sdk.client.__aenter__ = AsyncMock(side_effect=start_error)
        with pytest.raises(
            ProviderError, match="Codex login failed: codex binary cannot run"
        ) as exc_info:
            _login()
        assert exc_info.value.__cause__ is start_error


class TestLogout:
    def test_success(self, fake_sdk: FakeSdk) -> None:
        asyncio.run(codex_login.logout())
        fake_sdk.client.logout.assert_awaited_once()
        fake_sdk.client.close.assert_awaited_once()

    def test_timeout_raises(self, fake_sdk: FakeSdk) -> None:
        fake_sdk.client.logout = AsyncMock(side_effect=_hang)
        with patch(_CONFIG, return_value=0):
            with pytest.raises(ProviderError, match="logout timed out after 0 s"):
                asyncio.run(codex_login.logout())

    def test_sdk_error_raises(self, fake_sdk: FakeSdk) -> None:
        sdk_error = CodexError("rpc failed")
        fake_sdk.client.logout = AsyncMock(side_effect=sdk_error)
        with pytest.raises(ProviderError, match="rpc failed") as exc_info:
            asyncio.run(codex_login.logout())
        assert exc_info.value.__cause__ is sdk_error
