"""Qualification's sandboxes and test sets (slice 426, Task 16)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.slice_qualify import qualify_slice_candidate
from squadron.metrology.benchmark_models import QualificationOutcome
from tests.benchmark.slice_case_support import environment
from tests.benchmark.slice_qualify_support import FORK_ENV, TIP_ENV, typical_setup
from tests.benchmark.slice_repos import two_parent_landing


def test_superseded_is_fork_only_nodes_plus_nodes_changed_at_the_tip(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert result.case is not None
    assert result.case.superseded_tests == ("t::s1", "t::s2")  # removed, and changed


def test_tip_only_nodes_appear_nowhere_on_the_case_and_hidden_is_empty(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    case = result.case
    assert case is not None
    assert "t::n1" not in (*case.superseded_tests, *case.excluded_tests, *case.hidden_tests)
    assert (case.hidden_tests, case.hidden_fixtures) == ((), ())


def test_a_matching_keyed_record_is_returned_and_collect_never_runs(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    first = typical_setup(tmp_path / "s", built)
    qualify_slice_candidate(first.candidate, first.deps)
    second = typical_setup(tmp_path / "s", built)  # a new factory and adapter, the same store

    result = qualify_slice_candidate(second.candidate, second.deps)

    assert result.reused
    assert second.adapter.collected == []
    assert second.suite.calls == 0
    assert second.factory.built == [built.landing.fork]  # only the fork's sandbox, for its digest


def test_a_record_under_another_environment_digest_is_not_reused(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    first = typical_setup(tmp_path / "s", built)
    qualify_slice_candidate(first.candidate, first.deps)
    second = typical_setup(tmp_path / "s", built)
    second.factory.fork_env = environment("5" * 64)

    result = qualify_slice_candidate(second.candidate, second.deps)

    assert not result.reused
    assert second.adapter.collected != []
    assert result.record.start_environment is not None
    assert result.record.start_environment.identity_digest == environment("5" * 64).identity_digest


def test_with_keep_the_sandboxes_are_kept_and_their_paths_returned(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built, keep=True)

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert all(sandbox.kept for sandbox in setup.factory.sandboxes.values())
    assert set(result.kept_paths) == {sandbox.tree for sandbox in setup.factory.sandboxes.values()}
    assert len(result.kept_paths) == 2


def test_without_keep_nothing_is_kept(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert not any(sandbox.kept for sandbox in setup.factory.sandboxes.values())
    assert result.kept_paths == ()


def test_the_record_keys_on_the_fork_environment_and_names_both(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert result.record.outcome is QualificationOutcome.QUALIFIED
    assert result.record.start_environment == FORK_ENV
    assert result.record.reference_environment == TIP_ENV
