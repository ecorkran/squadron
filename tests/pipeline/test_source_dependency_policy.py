"""Which each-sources need their in-plan dependencies implemented before an item runs (#298)."""

from __future__ import annotations

import pytest

from squadron.pipeline.item_eligibility import single_each_step
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.sources import source_needs_implemented_dependencies


@pytest.mark.parametrize(
    ("pipeline", "needs_implemented"),
    [("implement-plan", True), ("tasks-plan", False), ("slices-plan", False)],
)
def test_only_the_implement_source_needs_implemented_dependencies(
    pipeline: str, needs_implemented: bool
) -> None:
    source = str(single_each_step(load_pipeline(pipeline)).config["source"])

    assert source_needs_implemented_dependencies(source) is needs_implemented


def test_an_unknown_source_is_an_error_not_a_default() -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        source_needs_implemented_dependencies("cf.no_such_source()")
