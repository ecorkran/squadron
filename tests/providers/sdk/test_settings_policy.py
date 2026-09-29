"""Settings policy per automated SDK path (slice 932 D10).

Each case drives that path's real builder with its collaborators faked and
records the settings sources and auto-memory it would run with. One-shot paths
are intercepted at ``ClaudeSDKProvider.create_agent``; the pipeline session at
its client constructor. No case may resolve to ``None``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.config.manager import set_config
from squadron.core.models import AgentConfig
from squadron.providers.sdk.provider import ClaudeSDKProvider
from squadron.providers.sdk.settings import AUTO_MEMORY_DISABLE_ENV

Observed = tuple[list[str] | None, bool]


class _Captured(Exception):
    """Stops a path right after its AgentConfig reaches the provider."""


async def _capture_config(entry: Callable[[], Awaitable[object]]) -> Observed:
    captured: list[AgentConfig] = []

    async def _create_agent(self: ClaudeSDKProvider, config: AgentConfig) -> object:
        captured.append(config)
        raise _Captured

    with patch.object(ClaudeSDKProvider, "create_agent", _create_agent):
        # Paths wrap agent failures in their own error types; the config is
        # recorded before that, which is all this test reads.
        with contextlib.suppress(Exception):
            await entry()
    assert len(captured) == 1, "path never reached the SDK provider"
    return captured[0].setting_sources, captured[0].auto_memory


async def _review(tmp_path: Path, template_name: str, override: list[str] | None) -> Observed:
    from squadron.review.review_client import run_review_with_profile
    from squadron.review.templates import get_template, load_all_templates

    load_all_templates()
    template = get_template(template_name)
    assert template is not None
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc\n")
    inputs = {i.name: str(doc) for i in template.required_inputs}
    inputs["cwd"] = str(tmp_path)
    return await _capture_config(
        lambda: run_review_with_profile(
            template, inputs, profile="sdk", setting_sources_override=override
        )
    )


async def _builtin_review(tmp_path: Path) -> Observed:
    return await _review(tmp_path, "slice", None)


async def _pr_review(tmp_path: Path) -> Observed:
    # review_pr passes this override for every PR review (slice 382 D8).
    return await _review(tmp_path, "code", [])


async def _pipeline_session(tmp_path: Path) -> Observed:
    from squadron.pipeline.sdk_session import open_pipeline_session

    client = MagicMock()
    client.connect = AsyncMock()
    with patch("squadron.pipeline.sdk_session.ClaudeSDKClient", return_value=client) as ctor:
        await open_pipeline_session()
    options = ctor.call_args.kwargs["options"]
    return options.setting_sources, AUTO_MEMORY_DISABLE_ENV not in options.env


async def _one_shot_dispatch(tmp_path: Path) -> Observed:
    from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry

    return await _capture_config(
        lambda: one_shot_dispatch_with_telemetry(
            prompt="p", model_id="m", profile_name="sdk", cwd=str(tmp_path)
        )
    )


async def _summary_one_shot(tmp_path: Path) -> Observed:
    from squadron.pipeline.summary_oneshot import capture_summary_via_profile_with_telemetry

    return await _capture_config(
        lambda: capture_summary_via_profile_with_telemetry(
            instructions="summarize", model_id=None, profile="sdk"
        )
    )


async def _audit(tmp_path: Path) -> Observed:
    from squadron.metrology import audit

    preflight = MagicMock()
    preflight.project_id.value = "proj"
    preflight.commit_sha = "abcdef1234"
    with (
        patch.object(audit, "preflight_project", return_value=preflight),
        patch.object(audit, "resolve_audit_skill", return_value=tmp_path / "SKILL.md"),
        patch.object(audit, "audit_prompt_hash", return_value="h"),
        patch.object(audit, "build_audit_prompt", return_value="audit"),
        patch.object(audit, "resolve_audit_profile", return_value="sdk"),
    ):
        return await _capture_config(
            lambda: audit.run_audit(tmp_path, store=MagicMock(), cwd=str(tmp_path))
        )


async def _pr_composer(tmp_path: Path) -> Observed:
    from squadron.pr.composer import compose_one_shot

    return await _capture_config(lambda: compose_one_shot("p", model=None, profile="sdk"))


# (builder, expected setting_sources, auto-memory follows pipeline.auto_memory?)
_POLICY: list[tuple[Callable[[Path], Awaitable[Observed]], list[str], bool]] = [
    (_builtin_review, ["project"], False),
    (_pr_review, [], False),
    (_pipeline_session, ["project"], True),
    (_one_shot_dispatch, ["project"], True),
    (_summary_one_shot, [], False),
    (_audit, ["project"], False),
    (_pr_composer, [], False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("config_value", [True, False], ids=["memory-on", "memory-off"])
@pytest.mark.parametrize(
    ("builder", "sources", "follows_config"),
    _POLICY,
    ids=[builder.__name__.lstrip("_") for builder, _, _ in _POLICY],
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
