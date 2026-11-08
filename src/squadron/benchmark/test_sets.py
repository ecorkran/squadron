"""Sort collected tests into hidden, superseded and unchanged sets (slice 422 D3).

Pure: two ``CollectedTests`` in, one ``TestSets`` out. Nothing here runs a test.
"""

from __future__ import annotations

from dataclasses import dataclass

from squadron.benchmark.fairness import CollectedTests
from squadron.metrology.benchmark_models import ConftestFixture


@dataclass(frozen=True)
class TestSets:
    """All fields are sorted tuples.

    A changed test is in both ``hidden_candidates`` (its new version) and
    ``superseded`` (its old one). ``hidden_fixtures`` are conftest fixtures the fix
    added that some hidden candidate reaches.
    """

    __test__ = False  # pytest: a class named Test* is not a test class

    hidden_candidates: tuple[str, ...]
    superseded: tuple[str, ...]
    unchanged: tuple[str, ...]
    hidden_fixtures: tuple[ConftestFixture, ...]


def _fixture_order(fixture: ConftestFixture) -> tuple[str, str]:
    return (fixture.conftest_path, fixture.fixture_name)


def sort_tests(parent: CollectedTests, reference: CollectedTests) -> TestSets:
    """Apply D3's four cases to every node id, then pick the added fixtures hidden tests reach."""
    parent_nodes = parent.digests.keys()
    reference_nodes = reference.digests.keys()
    both = parent_nodes & reference_nodes
    changed = {node for node in both if parent.digests[node] != reference.digests[node]}
    hidden = (reference_nodes - parent_nodes) | changed
    superseded = (parent_nodes - reference_nodes) | changed
    unchanged = both - changed

    parent_keys = {_fixture_order(fixture) for fixture in parent.conftest_fixtures}
    added_keys = {_fixture_order(fixture) for fixture in reference.conftest_fixtures} - parent_keys
    # Keyed by (path, name): deduplicates across hidden tests and gives the sort order.
    reached = {
        _fixture_order(fixture): fixture
        for node in hidden
        for fixture in reference.fixtures_reached.get(node, ())
        if _fixture_order(fixture) in added_keys
    }
    return TestSets(
        hidden_candidates=tuple(sorted(hidden)),
        superseded=tuple(sorted(superseded)),
        unchanged=tuple(sorted(unchanged)),
        hidden_fixtures=tuple(reached[key] for key in sorted(reached)),
    )
