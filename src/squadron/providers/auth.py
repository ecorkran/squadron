"""AuthStrategy protocol and concrete implementations for credential resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from squadron.providers.errors import ProviderAuthError

if TYPE_CHECKING:
    from squadron.core.models import AgentConfig
    from squadron.providers.profiles import ProviderProfile


@runtime_checkable
class AuthStrategy(Protocol):
    """Credential resolution strategy for a provider."""

    async def get_credentials(self) -> dict[str, str]:
        """Return credentials dict (e.g. {"api_key": "sk-..."}).

        Raises ProviderAuthError if credentials cannot be resolved.
        """
        ...

    async def refresh_if_needed(self) -> None:
        """Refresh credentials if they are expired or near expiry.

        No-op for strategies that don't support refresh (e.g. API keys).
        """
        ...

    def is_valid(self) -> bool:
        """Return True if credentials are currently available and usable."""
        ...

    @property
    def active_source(self) -> str | None:
        """Return the credential source that would be used, or None."""
        ...

    @property
    def setup_hint(self) -> str:
        """Return actionable instructions for setting up credentials."""
        ...

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        profile: ProviderProfile | None = None,
    ) -> AuthStrategy:
        """Construct a strategy instance from config and optional profile."""
        ...


class ApiKeyStrategy:
    """Resolve an API key from explicit value, env var chain, or localhost bypass."""

    def __init__(
        self,
        *,
        explicit_key: str | None = None,
        env_var: str | None = None,
        fallback_env_var: str = "OPENAI_API_KEY",
        base_url: str | None = None,
    ) -> None:
        self._explicit_key = explicit_key
        self._env_var = env_var
        self._fallback_env_var = fallback_env_var
        self._base_url = base_url

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        profile: ProviderProfile | None = None,
    ) -> ApiKeyStrategy:
        """Build from AgentConfig and optional profile."""
        env_var: str | None
        if profile is not None:
            env_var = profile.api_key_env
        else:
            raw = config.credentials.get("api_key_env")
            env_var = str(raw) if raw is not None else None

        return cls(
            explicit_key=config.api_key,
            env_var=env_var,
            fallback_env_var="OPENAI_API_KEY",
            base_url=config.base_url,
        )

    def _is_localhost(self) -> bool:
        url = self._base_url or ""
        return url.startswith("http://localhost") or url.startswith("http://127.0.0.1")

    def _resolve(self) -> str | None:
        """Return resolved key or None if nothing found (excluding error case)."""
        if self._explicit_key:
            return self._explicit_key
        if self._env_var:
            val = os.environ.get(self._env_var)
            if val:
                return val
        fallback = os.environ.get(self._fallback_env_var)
        if fallback:
            return fallback
        if self._is_localhost():
            return "not-needed"
        return None

    @property
    def active_source(self) -> str | None:
        """Return which credential source would be used."""
        if self._explicit_key:
            return "explicit"
        if self._env_var and os.environ.get(self._env_var):
            return self._env_var
        if os.environ.get(self._fallback_env_var):
            return self._fallback_env_var
        if self._is_localhost():
            return "localhost"
        return None

    @property
    def setup_hint(self) -> str:
        """Return actionable setup instructions."""
        env = self._env_var or self._fallback_env_var
        return f"Set {env} environment variable"

    async def get_credentials(self) -> dict[str, str]:
        """Return {"api_key": "<resolved_key>"}.

        Resolution order:
        1. explicit_key (from AgentConfig.api_key)
        2. os.environ[env_var] (profile-specified, e.g. OPENROUTER_API_KEY)
        3. os.environ[fallback_env_var] (default OPENAI_API_KEY)
        4. "not-needed" if base_url is localhost
        5. Raise ProviderAuthError
        """
        key = self._resolve()
        if key is None:
            raise ProviderAuthError(
                f"No API key found. {self.setup_hint}."
            )
        return {"api_key": key}

    async def refresh_if_needed(self) -> None:
        """No-op — API keys don't expire."""

    def is_valid(self) -> bool:
        """Return True if any key source resolves to a non-empty value."""
        return self._resolve() is not None


# Registry mapping auth_type strings to strategy classes.
# Each class must implement from_config(config, profile) classmethod.
AUTH_STRATEGIES: dict[str, type] = {
    "api_key": ApiKeyStrategy,
    # "session" added below
    # "oauth" added below (lazy import to avoid circular dependency)
}


def _register_oauth_strategy() -> None:
    """Register OAuthFileStrategy lazily to avoid circular import."""
    from squadron.providers.codex.auth import OAuthFileStrategy

    AUTH_STRATEGIES["oauth"] = OAuthFileStrategy


_register_oauth_strategy()


class _SessionStrategy:
    """No-op auth strategy for SDK sessions (no credentials needed)."""

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        profile: ProviderProfile | None = None,
    ) -> _SessionStrategy:
        return cls()

    async def get_credentials(self) -> dict[str, str]:
        return {}

    async def refresh_if_needed(self) -> None:
        pass

    def is_valid(self) -> bool:
        return True

    @property
    def active_source(self) -> str | None:
        return "(session)"

    @property
    def setup_hint(self) -> str:
        return "No setup needed — uses active Claude Code session"


AUTH_STRATEGIES["session"] = _SessionStrategy


def resolve_auth_strategy(
    config: AgentConfig,
    profile: ProviderProfile | None = None,
) -> AuthStrategy:
    """Build an AuthStrategy from config and optional profile.

    Reads auth_type from profile (defaults to "api_key" if no profile).
    Dispatches to the strategy's ``from_config`` classmethod — no
    if/elif chains on auth_type values.
    """
    auth_type: str = profile.auth_type if profile is not None else "api_key"

    strategy_cls = AUTH_STRATEGIES.get(auth_type)
    if strategy_cls is None:
        available = ", ".join(sorted(AUTH_STRATEGIES))
        raise ProviderAuthError(
            f"Unknown auth_type {auth_type!r}. Available: {available}"
        )

    return strategy_cls.from_config(config, profile)


def resolve_auth_strategy_for_profile(profile: ProviderProfile) -> AuthStrategy:
    """Convenience: resolve auth strategy from profile alone (no AgentConfig).

    Used by CLI auth status where no agent config exists.
    """
    from squadron.core.models import AgentConfig

    minimal_config = AgentConfig(
        name="_auth_check",
        agent_type="api",
        provider=profile.provider,
    )
    return resolve_auth_strategy(minimal_config, profile)
