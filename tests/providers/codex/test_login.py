"""Tests for Codex login, logout, and account summary (SDK faked)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from squadron.providers.codex import login as codex_login
from squadron.providers.codex.runtime import CODEX_INSTALL_COMMAND
from squadron.providers.errors import ProviderError
from tests.providers.codex.fake_sdk import FakeSdk

_AUTH_URL = "https://auth.openai.com/oauth/authorize?state=secret-state"
_DEVICE_URL = "https://auth.openai.com/codex/device"
_USER_CODE = "WXYZ-1234"
_CONFIG = "squadron.providers.codex.login.get_typed_config"
_MODULE_AVAILABLE = "squadron.providers.codex.runtime._module_available"


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

    def test_extra_absent_gives_install_hint(self) -> None:
        with patch(_MODULE_AVAILABLE, return_value=False):
            with pytest.raises(ProviderError) as exc_info:
                _login()
        assert CODEX_INSTALL_COMMAND in str(exc_info.value)

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
