"""Settings policy per automated SDK path (slice 932 D10).

Each case drives that path's real builder with its collaborators faked and
records the settings sources and auto-memory it would run with. One-shot paths
are intercepted at ``ClaudeSDKProvider.create_agent``; the pipeline session at
its client constructor. No case may resolve to ``None``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.config.manager import set_config
from squadron.providers.sdk.settings import AUTO_MEMORY_DISABLE_ENV
from tests.providers import agent_config_sites as sites

Observed = tuple[list[str] | None, bool]


def _observed(builder: sites.ConfigBuilder) -> Callable[[Path], Awaitable[Observed]]:
    """Read a one-shot path's settings sources and auto-memory off its AgentConfig."""

    async def _observe(tmp_path: Path) -> Observed:
        config = await builder(tmp_path)
        return config.setting_sources, config.auto_memory

    _observe.__name__ = builder.__name__
    return _observe


async def pipeline_session(tmp_path: Path) -> Observed:
    from squadron.pipeline.sdk_session import open_pipeline_session

    client = MagicMock()
    client.connect = AsyncMock()
    with patch("squadron.pipeline.sdk_session.ClaudeSDKClient", return_value=client) as ctor:
        await open_pipeline_session()
    options = ctor.call_args.kwargs["options"]
    return options.setting_sources, AUTO_MEMORY_DISABLE_ENV not in options.env


# (builder, expected setting_sources, auto-memory follows pipeline.auto_memory?)
_POLICY: list[tuple[Callable[[Path], Awaitable[Observed]], list[str], bool]] = [
    (_observed(sites.builtin_review), ["project"], False),
    (_observed(sites.pr_review), [], False),
    (pipeline_session, ["project"], True),
    (_observed(sites.one_shot_dispatch), ["project"], True),
    (_observed(sites.summary_one_shot), [], False),
    (_observed(sites.audit), ["project"], False),
    (_observed(sites.pr_composer), [], False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("config_value", [True, False], ids=["memory-on", "memory-off"])
@pytest.mark.parametrize(
    ("builder", "sources", "follows_config"),
    _POLICY,
    ids=[builder.__name__ for builder, _, _ in _POLICY],
)
async def test_path_settings_policy(
    patch_config_paths: dict[str, Path],
    tmp_path: Path,
    builder: Callable[[Path], Awaitable[Observed]],
    sources: list[str],
    follows_config: bool,
    config_value: bool,
) -> None:
    set_config("pipeline.auto_memory", str(config_value).lower())

    setting_sources, auto_memory = await builder(tmp_path)

    assert setting_sources == sources
    assert auto_memory is (config_value if follows_config else False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("builder", "sources", "follows_config"),
    _POLICY,
    ids=[builder.__name__ for builder, _, _ in _POLICY],
)
async def test_user_settings_widens_pipeline_paths_only(
    patch_config_paths: dict[str, Path],
    tmp_path: Path,
    builder: Callable[[Path], Awaitable[Observed]],
    sources: list[str],
    follows_config: bool,
) -> None:
    """pipeline.user_settings adds "user" to pipeline sessions and dispatch, nowhere else."""
    set_config("pipeline.user_settings", "true")

    setting_sources, _ = await builder(tmp_path)

    assert setting_sources == (["user", *sources] if follows_config else sources)
