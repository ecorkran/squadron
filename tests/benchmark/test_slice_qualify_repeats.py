"""Repeated runs at the tip and the exclusions they give (slice 426, Task 17)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.slice_qualify import qualify_slice_candidate
from squadron.metrology.benchmark_models import TestRejection
from tests.benchmark.slice_qualify_support import typical_setup
from tests.benchmark.slice_repos import two_parent_landing


def test_a_flaky_node_and_an_always_failing_node_are_excluded_with_their_reasons(
    tmp_path: Path,
) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert result.record.excluded_with_reasons == (
        ("t::u2", TestRejection.FLAKY),
        ("t::u3", TestRejection.FAILS_AT_REFERENCE),
    )
    assert result.case is not None
    assert result.case.excluded_tests == ("t::u2", "t::u3")


def test_a_node_that_passes_every_run_is_not_excluded(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    excluded = {node for node, _ in result.record.excluded_with_reasons}
    assert {"t::u1", "t::u4"}.isdisjoint(excluded)


@pytest.mark.parametrize("repeats", [1, 2, 5])
def test_the_suite_runs_exactly_qualification_repeats_times(tmp_path: Path, repeats: int) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"), repeats=repeats)

    qualify_slice_candidate(setup.candidate, setup.deps)

    assert setup.suite.calls == repeats
