"""Every agent-building site carries ``profile_credentials`` (slice 931).

Each path runs its real builder against an ``sdk`` profile given distinctive values, so
a site that hand-copied fields again, or dropped the new flag, fails here. Sites add
keys of their own, so the check is containment plus each site's own extras — equality
would fail wherever a site carries more.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.cli.commands.spawn import _resolve_profile  # pyright: ignore[reportPrivateUsage]
from squadron.providers import profiles
from squadron.providers.base import ProfileName
from squadron.providers.profiles import profile_credentials
from tests.providers import agent_config_sites as sites

_DISTINCT_SDK = dataclasses.replace(
    profiles.BUILT_IN_PROFILES[ProfileName.SDK],
    api_key_env="SQ_TEST_KEY_ENV",
    default_headers={"X-Test": "1"},
    sends_stream_usage=False,
)


@pytest.fixture
def distinct_sdk_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(profiles.BUILT_IN_PROFILES, ProfileName.SDK, _DISTINCT_SDK)
    # No user providers.toml can shadow the patched built-in.
    monkeypatch.setattr(profiles, "providers_toml_path", lambda: tmp_path / "absent.toml")
    yield


# (builder, the site's own credentials keys beside the profile's)
_SITES: list[tuple[sites.ConfigBuilder, set[str]]] = [
    (sites.builtin_review, {"hooks", "mode"}),
    (sites.one_shot_dispatch, set()),
    (sites.summary_one_shot, {"hooks", "mode"}),
    (sites.audit, {"mode", "max_rate_limit_retries", "rate_limit_cap_s"}),
    (sites.pr_composer, {"hooks", "mode"}),
]


@pytest.mark.asyncio
@pytest.mark.usefixtures("distinct_sdk_profile")
@pytest.mark.parametrize(("builder", "extras"), _SITES, ids=[builder.__name__ for builder, _ in _SITES])
async def test_site_credentials_carry_profile_credentials(
    patch_config_paths: dict[str, Path],
    tmp_path: Path,
    builder: sites.ConfigBuilder,
    extras: set[str],
) -> None:
    expected = profile_credentials(_DISTINCT_SDK)

    credentials = (await builder(tmp_path)).credentials

    assert expected.items() <= credentials.items()
    assert set(credentials) - set(expected) == extras
    if "mode" in extras:
        assert credentials["mode"] == "client"


@pytest.mark.usefixtures("distinct_sdk_profile")
def test_spawn_credentials_carry_profile_credentials() -> None:
    credentials = _resolve_profile(ProfileName.SDK, None, None)["credentials"]

    assert credentials == profile_credentials(_DISTINCT_SDK)


def test_spawn_omits_unset_profile_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The daemon request body leaves out None fields, as it did before the helper."""
    partial = dataclasses.replace(_DISTINCT_SDK, default_headers=None)
    monkeypatch.setitem(profiles.BUILT_IN_PROFILES, ProfileName.SDK, partial)
    monkeypatch.setattr(profiles, "providers_toml_path", lambda: tmp_path / "absent.toml")

    credentials = _resolve_profile(ProfileName.SDK, None, None)["credentials"]

    assert "default_headers" not in credentials
    assert credentials == {"api_key_env": "SQ_TEST_KEY_ENV", "sends_stream_usage": False}
