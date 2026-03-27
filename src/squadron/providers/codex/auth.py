"""OAuthFileStrategy — credential resolution from cached OAuth tokens or API key."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from squadron.providers.errors import ProviderAuthError

if TYPE_CHECKING:
    from squadron.core.models import AgentConfig
    from squadron.providers.profiles import ProviderProfile

# Default location for Codex CLI cached credentials.
_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"


class OAuthFileStrategy:
    """Resolve credentials from a cached OAuth token file or API key fallback.

    Resolution order (subscription-first):
    1. Auth file (e.g. ``~/.codex/auth.json``, written by OAuth login)
    2. ``OPENAI_API_KEY`` environment variable (fallback)
    3. Raise ``ProviderAuthError`` with actionable instructions

    The auth file is preferred so that users with a subscription
    use their subscription quota, while ``OPENAI_API_KEY`` remains
    available for other providers via the ``api_key`` auth type.
    """

    def __init__(self, auth_file: Path | None = None) -> None:
        self._auth_file = auth_file or _CODEX_AUTH_FILE

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        profile: ProviderProfile | None = None,
    ) -> OAuthFileStrategy:
        """Construct from config — no config needed (reads fixed file path)."""
        return cls()

    def _has_api_key(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def _has_auth_file(self) -> bool:
        return self._auth_file.is_file()

    @property
    def active_source(self) -> str | None:
        """Return the credential source that would be used, or None."""
        if self._has_auth_file():
            return "~/.codex/auth.json"
        if self._has_api_key():
            return "OPENAI_API_KEY"
        return None

    @property
    def setup_hint(self) -> str:
        """Return actionable setup instructions."""
        return "Run 'codex' CLI to authenticate, or set OPENAI_API_KEY"

    async def get_credentials(self) -> dict[str, str]:
        """Return credentials dict.

        Returns ``{"auth_file": "<path>"}`` when the auth file exists
        (subscription), or ``{"api_key": "<value>"}`` when ``OPENAI_API_KEY``
        is set (API credits fallback).
        """
        if self._has_auth_file():
            return {"auth_file": str(self._auth_file)}

        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            return {"api_key": api_key}

        raise ProviderAuthError(f"No credentials found. {self.setup_hint}.")

    async def refresh_if_needed(self) -> None:
        """No-op — token refresh handled by the runtime internally."""

    def is_valid(self) -> bool:
        """Return True if either credential source resolves."""
        return self._has_auth_file() or self._has_api_key()
