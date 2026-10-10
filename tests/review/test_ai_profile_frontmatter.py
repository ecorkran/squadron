"""``aiProfile`` in review artifact frontmatter (slice 940 D6, #193).

Present only when the profile is known; never a placeholder. Readers that predate
the key must parse an artifact that has it, and artifacts without it must still parse.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
import yaml

from squadron.documents.frontmatter import read_frontmatter
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.providers.errors import ProviderAPIError
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import (
    SliceInfo,
    format_provider_failure_markdown,
    format_review_markdown,
)

_SLICE_INFO = cast(
    "SliceInfo",
    {
        "index": 940,
        "name": "s",
        "slice_name": "s",
        "design_file": "d.md",
        "phase": "6",
        "project": "squadron",
    },
)
_PROFILE = "openrouter"
_KEY = "aiProfile"
_P = "squadron.pipeline.actions.review"


def _result(profile: str | None) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="clean",
        template_name="code",
        input_files={"input": "f.md"},
        timestamp=datetime(2026, 10, 9, 12, 0, 0),
        model="m",
        profile=profile,
    )


def _frontmatter(markdown: str) -> dict[str, object]:
    return cast("dict[str, object]", yaml.safe_load(markdown.split("---")[1]))


def test_success_artifact_records_profile_beside_model() -> None:
    markdown = format_review_markdown(_result(_PROFILE), "code", _SLICE_INFO)

    assert _frontmatter(markdown)[_KEY] == _PROFILE
    lines = markdown.splitlines()
    assert lines.index(f"{_KEY}: {_PROFILE}") == lines.index("aiModel: m") + 1


def test_success_artifact_omits_profile_when_unknown() -> None:
    assert _KEY not in _frontmatter(format_review_markdown(_result(None), "code", _SLICE_INFO))


def test_failure_artifact_records_profile_when_passed() -> None:
    exc = ProviderAPIError("boom", status_code=500)

    with_profile = format_provider_failure_markdown(exc, "code", _SLICE_INFO, profile=_PROFILE)
    without = format_provider_failure_markdown(exc, "code", _SLICE_INFO)

    assert _frontmatter(with_profile)[_KEY] == _PROFILE
    assert _KEY not in _frontmatter(without)


@pytest.mark.parametrize("profile", [_PROFILE, None])
def test_frontmatter_readers_parse_artifacts_with_and_without_the_key(
    tmp_path: Path, profile: str | None
) -> None:
    path = tmp_path / "review.md"
    path.write_text(format_review_markdown(_result(profile), "code", _SLICE_INFO))

    front = read_frontmatter(path)

    assert front is not None
    assert front["verdict"] == "PASS"
    assert front.get(_KEY) == profile


@pytest.mark.asyncio
async def test_pipeline_review_artifact_carries_the_resolved_profile(tmp_path: Path) -> None:
    template = MagicMock(name="code")
    template.required_inputs = []
    template.optional_inputs = []
    template.judge = None
    template.is_judge = False
    template.model = None
    template.profile = "template-profile"
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel("my-model", None)
    context = ActionContext(
        pipeline_name="p",
        run_id="run-12345678",
        params={"template": "code"},
        step_name="review-step",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(tmp_path),
    )
    stub = _result(None)  # the client did not stamp a profile; the action does

    with (
        patch(f"{_P}.get_template", return_value=template),
        patch(f"{_P}.load_all_templates"),
        patch(f"{_P}.run_review_with_profile", return_value=stub),
        patch(f"{_P}.resolve_reviewed_sha", return_value=None),
    ):
        result = await ReviewAction().execute(context)

    artifact = Path(str(result.outputs["review_file"]))
    front = read_frontmatter(artifact)
    assert front is not None
    assert front[_KEY] == "template-profile"
