"""Drive each one-shot agent path's real builder and capture the AgentConfig it builds.

Every path runs with its collaborators faked and the ``sdk`` profile, and is stopped at
``ClaudeSDKProvider.create_agent`` — the moment its AgentConfig reaches a provider.
Shared by the settings-policy tests (slice 932 D10) and the credentials tests
(slice 931), which read different fields off the same capture.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

from squadron.core.models import AgentConfig
from squadron.providers.sdk.provider import ClaudeSDKProvider

ConfigBuilder = Callable[[Path], Awaitable[AgentConfig]]


class _Captured(Exception):
    """Stops a path right after its AgentConfig reaches the provider."""


async def capture_config(entry: Callable[[], Awaitable[object]]) -> AgentConfig:
    captured: list[AgentConfig] = []

    async def _create_agent(self: ClaudeSDKProvider, config: AgentConfig) -> object:
        captured.append(config)
        raise _Captured

    with patch.object(ClaudeSDKProvider, "create_agent", _create_agent):
        # Paths wrap agent failures in their own error types; the config is
        # recorded before that, which is all the callers read.
        with contextlib.suppress(Exception):
            await entry()
    assert len(captured) == 1, "path never reached the SDK provider"
    return captured[0]


async def review(tmp_path: Path, template_name: str, override: list[str] | None) -> AgentConfig:
    from squadron.review.review_client import run_review_with_profile
    from squadron.review.templates import get_template, load_all_templates

    load_all_templates()
    template = get_template(template_name)
    assert template is not None
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc\n")
    inputs = {i.name: str(doc) for i in template.required_inputs}
    inputs["cwd"] = str(tmp_path)
    return await capture_config(
        lambda: run_review_with_profile(
            template, inputs, profile="sdk", setting_sources_override=override
        )
    )


async def builtin_review(tmp_path: Path) -> AgentConfig:
    return await review(tmp_path, "slice", None)


async def pr_review(tmp_path: Path) -> AgentConfig:
    # review_pr passes this override for every PR review (slice 382 D8).
    return await review(tmp_path, "code", [])


async def one_shot_dispatch(tmp_path: Path) -> AgentConfig:
    from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry

    return await capture_config(
        lambda: one_shot_dispatch_with_telemetry(
            prompt="p", model_id="m", profile_name="sdk", cwd=str(tmp_path)
        )
    )


async def summary_one_shot(tmp_path: Path) -> AgentConfig:
    from squadron.pipeline.summary_oneshot import capture_summary_via_profile_with_telemetry

    return await capture_config(
        lambda: capture_summary_via_profile_with_telemetry(
            instructions="summarize", model_id=None, profile="sdk"
        )
    )


async def audit(tmp_path: Path) -> AgentConfig:
    from squadron.metrology import audit as audit_module

    preflight = MagicMock()
    preflight.project_id.value = "proj"
    preflight.commit_sha = "abcdef1234"
    with (
        patch.object(audit_module, "preflight_project", return_value=preflight),
        patch.object(audit_module, "resolve_audit_skill", return_value=tmp_path / "SKILL.md"),
        patch.object(audit_module, "audit_prompt_hash", return_value="h"),
        patch.object(audit_module, "build_audit_prompt", return_value="audit"),
        patch.object(audit_module, "resolve_audit_profile", return_value="sdk"),
    ):
        return await capture_config(
            lambda: audit_module.run_audit(tmp_path, store=MagicMock(), cwd=str(tmp_path))
        )


async def pr_composer(tmp_path: Path) -> AgentConfig:
    from squadron.pr.composer import compose_one_shot

    return await capture_config(lambda: compose_one_shot("p", model=None, profile="sdk"))
