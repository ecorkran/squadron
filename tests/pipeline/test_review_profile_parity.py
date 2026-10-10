"""`sq review` and the pipeline review action select the same profile (#184)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.cli.commands.review import (
    _resolve_model_and_profile,  # pyright: ignore[reportPrivateUsage]
)
from squadron.models.aliases import resolve_model_alias
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.review.models import ReviewResult, Verdict
from squadron.review.profile_resolution import ReviewProfileSource
from squadron.review.templates import ReviewTemplate

_P = "squadron.pipeline.actions.review"
_CONFIG_PATH = "squadron.review.profile_resolution.get_config"
# An alias whose own profile is not the sdk fallback, so ALIAS is distinguishable.
_ALIAS_WITH_PROFILE = "glm-flash-low"

# source -> (explicit profile, model, template profile, config profile)
_SCENARIOS: dict[ReviewProfileSource, tuple[str | None, str | None, str | None, str | None]] = {
    ReviewProfileSource.EXPLICIT: ("explicit-prof", "my-model", "tmpl-prof", "cfg-prof"),
    ReviewProfileSource.ALIAS: (None, _ALIAS_WITH_PROFILE, "tmpl-prof", "cfg-prof"),
    ReviewProfileSource.TEMPLATE: (None, "my-model", "tmpl-prof", "cfg-prof"),
    ReviewProfileSource.CONFIG: (None, "my-model", None, "cfg-prof"),
    ReviewProfileSource.DEFAULT: (None, None, None, None),
}


def _template(profile: str | None) -> ReviewTemplate:
    template = MagicMock(spec=ReviewTemplate, name="code")
    template.required_inputs = []
    template.optional_inputs = []
    template.judge = None
    template.is_judge = False
    template.model = None
    template.profile = profile
    return template


async def _pipeline_profile(explicit: str | None, model: str | None, template: ReviewTemplate) -> str:
    alias_profile = resolve_model_alias(model)[1] if model is not None else None
    params: dict[str, object] = {"template": "code"}
    if explicit is not None:
        params["profile"] = explicit
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(model or "unused", alias_profile)
    context = ActionContext(
        pipeline_name="parity",
        run_id="run-12345678",
        params=params,
        step_name="review-step",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd="/tmp/test",
    )
    result_stub = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Review\nPASS\n",
        template_name="code",
        input_files={},
        model=model,
    )
    with (
        patch(f"{_P}.get_template", return_value=template),
        patch(f"{_P}.load_all_templates"),
        patch(f"{_P}.run_review_with_profile", return_value=result_stub),
        patch(f"{_P}.save_review_result", return_value=Path("/tmp/reviews/review.md")),
    ):
        result = await ReviewAction().execute(context)
    return str(result.metadata["profile"])


@pytest.mark.asyncio
@pytest.mark.parametrize("source", list(ReviewProfileSource))
async def test_same_profile_from_both_paths(
    source: ReviewProfileSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit, model, template_profile, config_profile = _SCENARIOS[source]

    def fake_get_config(key: str) -> str | None:
        return config_profile if key == "default_review_profile" else None

    monkeypatch.setattr(_CONFIG_PATH, fake_get_config)
    template = _template(template_profile)

    _, cli_profile = _resolve_model_and_profile(model, explicit, template, "code")
    pipeline_profile = await _pipeline_profile(explicit, model, template)

    assert cli_profile == pipeline_profile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [ReviewProfileSource.ALIAS, ReviewProfileSource.TEMPLATE, ReviewProfileSource.DEFAULT],
)
async def test_review_step_logs_its_resolved_profile_and_model(
    source: ReviewProfileSource, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    explicit, model, template_profile, config_profile = _SCENARIOS[source]

    def fake_get_config(key: str) -> str | None:
        return config_profile if key == "default_review_profile" else None

    monkeypatch.setattr(_CONFIG_PATH, fake_get_config)

    with caplog.at_level("INFO", logger=_P):
        profile = await _pipeline_profile(explicit, model, _template(template_profile))

    expected = f"review: step review-step profile={profile} model={model or 'unused'}"
    assert expected in [record.getMessage() for record in caplog.records]
