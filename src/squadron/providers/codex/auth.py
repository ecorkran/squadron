"""OAuthFileStrategy — credential resolution from cached Codex OAuth tokens."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from squadron.providers.errors import ProviderAuthError

if TYPE_CHECKING:
    from squadron.core.models import AgentConfig
    from squadron.providers.profiles import ProviderProfile


# Default location for Codex CLI cached credentials.
def _codex_auth_file() -> Path:
    return Path.home() / ".codex" / "auth.json"


class OAuthFileStrategy:
    """Resolve credentials from the cached Codex OAuth token file.

    Only the auth file (``~/.codex/auth.json``, written by login) counts.
    The Codex runtime ignores ``OPENAI_API_KEY`` (verified in slice 129,
    Task 1: a key-only turn fails with 401), so the key is not a source
    here; API-key users belong on the ``openai`` profile.
    """

    def __init__(self, auth_file: Path | None = None) -> None:
        self._auth_file = auth_file or _codex_auth_file()

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        profile: ProviderProfile | None = None,
    ) -> OAuthFileStrategy:
        """Construct from config — no config needed (reads fixed file path)."""
        return cls()

    def _has_auth_file(self) -> bool:
        return self._auth_file.is_file()

    @property
    def active_source(self) -> str | None:
        """Return the credential source that would be used, or None."""
        if self._has_auth_file():
            return "~/.codex/auth.json"
        return None

    @property
    def setup_hint(self) -> str:
        """Return actionable setup instructions."""
        return (
            "Run 'sq auth login openai-oauth' to sign in with ChatGPT, "
            "or use the 'openai' profile for API-key access"
        )

    async def get_credentials(self) -> dict[str, str]:
        """Return ``{"auth_file": "<path>"}`` when the auth file exists."""
        if self._has_auth_file():
            return {"auth_file": str(self._auth_file)}
        raise ProviderAuthError(f"No credentials found. {self.setup_hint}.")

    async def refresh_if_needed(self) -> None:
        """No-op — token refresh handled by the runtime internally."""

    def is_valid(self) -> bool:
        """Return True if the auth file exists."""
        return self._has_auth_file()
