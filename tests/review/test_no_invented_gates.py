"""Non-judge reviews carry the no-invented-gates criterion; judges don't (slice 947 D1)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadron.data import data_dir
from squadron.providers.profiles import ProviderProfile
from squadron.review.review_client import (
    NO_INVENTED_GATES_CRITERION,
    assemble_system_prompt,
    run_review_with_profile,
)
from squadron.review.templates import BuiltinReviewTemplate, ReviewTemplate, load_template
from tests.review.test_review_client import (  # pyright: ignore[reportPrivateUsage]
    _make_mock_provider,
    _make_template,
)

_P = "squadron.review.review_client"


def _builtin(name: str) -> ReviewTemplate:
    return load_template(data_dir() / "templates" / f"{name}.yaml")


@pytest.mark.parametrize("name", [t.value for t in BuiltinReviewTemplate])
def test_builtin_non_judge_templates_get_the_criterion(name: str) -> None:
    template = _builtin(name)
    assert not template.is_judge
    assert NO_INVENTED_GATES_CRITERION in assemble_system_prompt(template, None)


@pytest.mark.parametrize("name", ["judge-slice-vs-arch", "judge-tasks-vs-slice"])
def test_judge_templates_do_not_get_the_criterion(name: str) -> None:
    template = _builtin(name)
    assert template.is_judge
    assert NO_INVENTED_GATES_CRITERION not in assemble_system_prompt(template, None)


def test_criterion_precedes_additional_rules() -> None:
    prompt = assemble_system_prompt(_make_template(), "Use tabs.")
    assert prompt.index(NO_INVENTED_GATES_CRITERION) < prompt.index("Use tabs.")


@pytest.mark.asyncio
async def test_user_template_review_sends_the_criterion() -> None:
    """The review call itself uses the assembly point, not just the helper."""
    with (
        patch(f"{_P}.get_profile") as mock_get_profile,
        patch(f"{_P}.get_provider", return_value=_make_mock_provider()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        mock_get_profile.return_value = ProviderProfile(
            name="openai", provider="openai", api_key_env="OPENAI_API_KEY"
        )
        result = await run_review_with_profile(
            _make_template(model="test-model"),
            {"input": "x"},
            profile="openai",
            model="test-model",
            verbosity=2,
        )

    assert result.system_prompt is not None
    assert NO_INVENTED_GATES_CRITERION in result.system_prompt
