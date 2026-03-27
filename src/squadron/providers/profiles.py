"""Provider profile definitions and loading from providers.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from squadron.providers.base import AuthType, ProfileName, ProviderType


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
        )
    return result


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
