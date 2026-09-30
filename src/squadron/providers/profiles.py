"""Provider profile definitions and loading from providers.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from squadron.providers.base import AuthType, ProfileName, ProviderType

__all__ = [
    "BUILT_IN_PROFILES",
    "ProviderProfile",
    "get_all_profiles",
    "get_profile",
    "is_sdk_profile",
    "load_user_profiles",
    "profile_credentials",
    "providers_toml_path",
]


@dataclass(frozen=True)
class ProviderProfile:
    """A named configuration preset bundling provider, base URL, and auth."""

    name: str
    provider: str
    base_url: str | None = None
    api_key_env: str | None = None
    default_headers: dict[str, str] | None = None
    description: str = ""
    auth_type: str = AuthType.API_KEY
    # Whether the backend accepts ``stream_options={"include_usage": True}`` (slice 931).
    # True is the OpenAI spec's behavior; a profile opts out only for a backend that
    # rejects the parameter.
    sends_stream_usage: bool = True


BUILT_IN_PROFILES: dict[str, ProviderProfile] = {
    ProfileName.OPENAI: ProviderProfile(
        name=ProfileName.OPENAI,
        provider=ProviderType.OPENAI,
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        description="OpenAI direct API",
    ),
    ProfileName.OPENROUTER: ProviderProfile(
        name=ProfileName.OPENROUTER,
        provider=ProviderType.OPENAI,
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_headers={
            "HTTP-Referer": "https://github.com/manta/squadron",
            "X-Title": "squadron",
        },
        description="OpenRouter multi-model gateway",
    ),
    ProfileName.LOCAL: ProviderProfile(
        name=ProfileName.LOCAL,
        provider=ProviderType.OPENAI,
        base_url="http://localhost:11434/v1",
        api_key_env=None,
        description="Local model server (Ollama, vLLM, LM Studio)",
    ),
    ProfileName.GEMINI: ProviderProfile(
        name=ProfileName.GEMINI,
        provider=ProviderType.OPENAI,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        description="Google Gemini via OpenAI-compatible endpoint",
        # Gemini's OpenAI-compatible endpoint is not verified to accept stream_options.
        sends_stream_usage=False,
    ),
    ProfileName.SDK: ProviderProfile(
        name=ProfileName.SDK,
        provider=ProviderType.SDK,
        api_key_env=None,
        description="Claude Code SDK (uses active Claude Code session credentials)",
        auth_type=AuthType.SESSION,
    ),
    ProfileName.OPENAI_OAUTH: ProviderProfile(
        name=ProfileName.OPENAI_OAUTH,
        provider=ProviderType.OPENAI_OAUTH,
        api_key_env=None,
        description="OpenAI Codex agent (MCP) — agentic tasks via subscription auth",
        auth_type=AuthType.OAUTH,
    ),
}


def providers_toml_path() -> Path:
    """Return the path to the user providers configuration file."""
    return Path.home() / ".config" / "squadron" / "providers.toml"


def load_user_profiles() -> dict[str, ProviderProfile]:
    """Load user-defined profiles from providers.toml.

    Returns an empty dict if the file does not exist.
    """
    path = providers_toml_path()
    if not path.exists():
        return {}

    with path.open("rb") as f:
        data = tomllib.load(f)

    profiles_data: dict[str, dict[str, object]] = data.get("profiles", {})
    result: dict[str, ProviderProfile] = {}
    for name, fields in profiles_data.items():
        result[name] = ProviderProfile(
            name=name,
            provider=str(fields["provider"]),
            base_url=str(fields["base_url"]) if "base_url" in fields else None,
            api_key_env=str(fields["api_key_env"]) if "api_key_env" in fields else None,
            default_headers=(
                {str(k): str(v) for k, v in fields["default_headers"].items()}  # type: ignore[union-attr]
                if "default_headers" in fields
                else None
            ),
            description=str(fields.get("description", "")),
            auth_type=str(fields.get("auth_type", "api_key")),
            sends_stream_usage=_read_sends_stream_usage(fields, name, path),
        )
    return result


def _read_sends_stream_usage(fields: dict[str, object], profile: str, path: Path) -> bool:
    """Read the optional ``sends_stream_usage`` flag; absent means the dataclass default."""
    if "sends_stream_usage" not in fields:
        return ProviderProfile.sends_stream_usage
    value = fields["sends_stream_usage"]
    if not isinstance(value, bool):
        raise ValueError(
            f"Profile {profile!r} in {path}: sends_stream_usage must be true or false, got {value!r}"
        )
    return value


def profile_credentials(profile: ProviderProfile) -> dict[str, object]:
    """The ``AgentConfig.credentials`` entries every agent built from ``profile`` carries.

    One definition, so a new profile field reaches every call site at once. Callers
    add their own keys (``hooks``, ``mode``, ...) beside these. ``sends_stream_usage``
    is read only by the OpenAI provider; the others ignore it.
    """
    return {
        "api_key_env": profile.api_key_env,
        "default_headers": profile.default_headers,
        "sends_stream_usage": profile.sends_stream_usage,
    }


def get_all_profiles() -> dict[str, ProviderProfile]:
    """Return merged profiles: built-ins plus user overrides."""
    merged = dict(BUILT_IN_PROFILES)
    merged.update(load_user_profiles())
    return merged


def get_profile(name: str) -> ProviderProfile:
    """Return the profile for the given name.

    Raises KeyError with a descriptive message if not found.
    """
    profiles = get_all_profiles()
    if name not in profiles:
        available = ", ".join(sorted(profiles))
        raise KeyError(f"Profile {name!r} not found. Available profiles: {available}")
    return profiles[name]


def is_sdk_profile(profile: str | None) -> bool:
    """Return True iff the profile routes through the Claude Code SDK session.

    Pure function of the profiles registry. Returns True for the 'sdk'
    profile name and for None (sentinel meaning "no profile specified —
    fall back to the SDK session's default model"; preserves the
    existing renderer / summary semantics). Returns False for every
    other registered profile (openrouter, openai, gemini, local,
    openai_oauth) and for unknown profile strings.

    Does not probe the Claude CLI, check authentication, or read
    config. Callers needing auth checks must do so separately. The
    classification layer (slice 243 pre-scan) operates only on
    resolved profiles and does not pass None to this predicate.
    """
    return profile is None or profile == ProfileName.SDK
