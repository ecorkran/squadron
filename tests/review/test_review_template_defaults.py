"""The review templates' default models (#378).

The ``slice`` and ``tasks`` templates agree with the pipelines' document reviewer. The
``code`` template keeps ``haiku-xhigh`` (its model is part of the template hash, so changing
it would give every stored code-review stage a new identity), while four pipelines now review
code with the ``haiku-line-pass`` recipe (slice 437).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import squadron
from squadron.review.templates import load_template

_PACKAGE_DATA = Path(squadron.__file__).parent / "data"
_TEMPLATES_DIR = _PACKAGE_DATA / "templates"
_PIPELINES_DIR = _PACKAGE_DATA / "pipelines"

#: The single reviewer the document templates and the ``code`` template default to, set from
#: the review-recall results (#339); four pipelines override it for code (slice 437).
PIPELINE_REVIEW_MODEL = "haiku-xhigh"
#: The arch reviewer, from RESULTS.md sections 16, 19 and 20 (#378).
ARCH_REVIEW_MODEL = "fable-medium"


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("slice", PIPELINE_REVIEW_MODEL),
        ("tasks", PIPELINE_REVIEW_MODEL),
        ("code", PIPELINE_REVIEW_MODEL),
        ("arch", ARCH_REVIEW_MODEL),
    ],
)
def test_review_template_default_model(template: str, expected: str) -> None:
    loaded = load_template(_TEMPLATES_DIR / f"{template}.yaml")

    assert loaded.model == expected


def test_p2_arch_review_model_matches_the_template_default() -> None:
    pipeline = yaml.safe_load((_PIPELINES_DIR / "P2.yaml").read_text(encoding="utf-8"))

    assert pipeline["params"]["review-model"] == ARCH_REVIEW_MODEL
