"""Codex interactive login, logout, and account lookup via the official SDK.

``openai_codex`` is imported inside functions so tests can substitute a fake SDK.
Auth URLs and device codes go to ``notify`` only — never to the log.
"""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from squadron.config.manager import get_typed_config
from squadron.logging import get_logger
from squadron.providers.errors import ProviderError

if TYPE_CHECKING:
    from openai_codex import AsyncChatgptLoginHandle, AsyncCodex, AsyncDeviceCodeLoginHandle
    from openai_codex.types import GetAccountResponse

_log = get_logger("squadron.providers.codex.login")

_ACCOUNT_TIMEOUT_KEY = "codex.account_timeout_s"
#: Default for ``sq auth login --timeout``; the CLI reads it through the config layer.
LOGIN_TIMEOUT_KEY = "codex.login_timeout_s"


@asynccontextmanager
async def _codex_session() -> AsyncIterator[AsyncCodex]:
    """Start the Codex runtime for one operation and always shut it down."""
    from openai_codex import AsyncCodex, CodexConfig, CodexError

    codex = AsyncCodex(CodexConfig())
    try:
        yield await codex.__aenter__()
    finally:
        try:
            await codex.close()
        except (CodexError, OSError):
            # Teardown of a one-shot runtime: the operation's own outcome is what
            # the caller needs, so a close failure is logged, not raised.
            _log.warning("Codex runtime shutdown failed", exc_info=True)


async def login(*, device_code: bool, timeout_s: float, notify: Callable[[str], None]) -> None:
    """Sign in with ChatGPT (browser or device code), waiting at most ``timeout_s``.

    Raises:
        ProviderError: login failed or timed out.
        asyncio.CancelledError: interrupted (Ctrl-C); the attempt is cancelled first.
    """
    async with _codex_session() as codex:
        if device_code:
            device_handle = await codex.login_chatgpt_device_code()
            notify(f"Open {device_handle.verification_url} and enter code: {device_handle.user_code}")
            await _wait_for_login(device_handle, timeout_s)
        else:
            browser_handle = await codex.login_chatgpt()
            notify(f"Sign in at: {browser_handle.auth_url}")
            _open_browser(browser_handle.auth_url)
            await _wait_for_login(browser_handle, timeout_s)


def _open_browser(url: str) -> None:
    """Best effort: the URL was already shown, so a headless box still works."""
    try:
        opened = webbrowser.open(url)
    except webbrowser.Error:
        opened = False
    if not opened:
        _log.warning("Could not open a browser; use the sign-in URL shown above")


async def _wait_for_login(
    handle: AsyncChatgptLoginHandle | AsyncDeviceCodeLoginHandle, timeout_s: float
) -> None:
    """Wait for completion; cancel the attempt on timeout or interruption."""
    try:
        async with asyncio.timeout(timeout_s):
            completed = await handle.wait()
    except TimeoutError as exc:
        await _cancel_login(handle)
        raise ProviderError(f"Codex login timed out after {timeout_s:g} s") from exc
    except asyncio.CancelledError:
        await _cancel_login(handle)
        raise
    if not completed.success:
        reason = completed.error or "the runtime gave no reason"
        raise ProviderError(f"Codex login failed: {reason}")


async def _cancel_login(handle: AsyncChatgptLoginHandle | AsyncDeviceCodeLoginHandle) -> None:
    """Cancel a login attempt (releases the callback listener); bounded, never raises."""
    from openai_codex import CodexError

    try:
        async with asyncio.timeout(get_typed_config(_ACCOUNT_TIMEOUT_KEY, int)):
            await handle.cancel()
    except (TimeoutError, CodexError):
        # The login already failed; this only tidies up the attempt.
        _log.warning("Cancelling the Codex login attempt failed", exc_info=True)


async def logout() -> None:
    """Sign out, bounded by ``codex.account_timeout_s``.

    Raises:
        ProviderError: SDK error or timeout.
    """
    from openai_codex import CodexError

    timeout_s = get_typed_config(_ACCOUNT_TIMEOUT_KEY, int)
    try:
        async with asyncio.timeout(timeout_s), _codex_session() as codex:
            await codex.logout()
    except TimeoutError as exc:
        raise ProviderError(f"Codex logout timed out after {timeout_s} s") from exc
    except (CodexError, OSError, RuntimeError) as exc:
        raise ProviderError(f"Codex logout failed: {exc}") from exc


async def account_summary() -> str | None:
    """Return ``"<email>, <plan>"`` for the signed-in account, or ``None``.

    Bounded by ``codex.account_timeout_s``. Every failure (runtime error,
    timeout) is logged at WARNING and yields ``None``; this never raises.
    """
    from openai_codex import CodexError

    timeout_s = get_typed_config(_ACCOUNT_TIMEOUT_KEY, int)
    try:
        async with asyncio.timeout(timeout_s), _codex_session() as codex:
            response = await codex.account()
    except TimeoutError:
        _log.warning("Codex account lookup timed out after %s s", timeout_s)
        return None
    except (CodexError, OSError, RuntimeError) as exc:
        _log.warning("Codex account lookup failed: %s", exc)
        return None
    return _format_account(response)


def _format_account(response: GetAccountResponse) -> str | None:
    """``"<email>, <plan>"`` from a ChatGPT account; ``None`` for anything else."""
    account = getattr(response, "account", None)
    details = getattr(account, "root", None)
    email = getattr(details, "email", None)
    plan = getattr(details, "plan_type", None)
    if email is None or plan is None:
        return None
    return f"{email}, {getattr(plan, 'value', plan)}"
