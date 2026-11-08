"""Sorting collected tests into hidden, superseded and unchanged sets (slice 422 D3)."""

from __future__ import annotations

from squadron.benchmark.fairness import CollectedTests
from squadron.benchmark.test_sets import sort_tests
from squadron.metrology.benchmark_models import ConftestFixture

CONFTEST = "tests/conftest.py"


def fixture(name: str, path: str = CONFTEST) -> ConftestFixture:
    return ConftestFixture(conftest_path=path, fixture_name=name)


def collected(
    digests: dict[str, str],
    reached: dict[str, tuple[ConftestFixture, ...]] | None = None,
    defined: frozenset[ConftestFixture] = frozenset(),
) -> CollectedTests:
    return CollectedTests(digests=digests, fixtures_reached=reached or {}, conftest_fixtures=defined)


def test_a_fix_that_adds_changes_deletes_and_adds_a_fixture() -> None:
    """The success-criteria shape: one added test, one changed, one deleted, one new fixture."""
    existing = fixture("workdir")
    added = fixture("snapshot_dir")
    parent = collected(
        {
            "tests/test_a.py::test_kept": "d1",
            "tests/test_a.py::test_changed": "d2",
            "tests/test_a.py::test_deleted": "d3",
        },
        defined=frozenset({existing}),
    )
    reference = collected(
        {
            "tests/test_a.py::test_kept": "d1",
            "tests/test_a.py::test_changed": "d2-new",
            "tests/test_a.py::test_added": "d4",
        },
        reached={"tests/test_a.py::test_added": (existing, added)},
        defined=frozenset({existing, added}),
    )
    sets = sort_tests(parent, reference)
    assert sets.hidden_candidates == ("tests/test_a.py::test_added", "tests/test_a.py::test_changed")
    assert sets.superseded == ("tests/test_a.py::test_changed", "tests/test_a.py::test_deleted")
    assert sets.unchanged == ("tests/test_a.py::test_kept",)
    assert sets.hidden_fixtures == (added,)


def test_a_changed_test_is_both_hidden_and_superseded() -> None:
    sets = sort_tests(collected({"t.py::a": "old"}), collected({"t.py::a": "new"}))
    assert sets.hidden_candidates == ("t.py::a",)
    assert sets.superseded == ("t.py::a",)
    assert sets.unchanged == ()


def test_equal_digests_are_unchanged() -> None:
    sets = sort_tests(collected({"t.py::a": "same"}), collected({"t.py::a": "same"}))
    assert sets.unchanged == ("t.py::a",)
    assert sets.hidden_candidates == ()
    assert sets.superseded == ()


def test_an_added_fixture_no_hidden_test_reaches_is_not_hidden() -> None:
    added = fixture("unused")
    parent = collected({"t.py::a": "x"})
    reference = collected(
        {"t.py::a": "x", "t.py::b": "y"},
        reached={"t.py::a": (added,)},  # reached only by an unchanged test
        defined=frozenset({added}),
    )
    sets = sort_tests(parent, reference)
    assert sets.hidden_candidates == ("t.py::b",)
    assert sets.hidden_fixtures == ()


def test_a_fixture_already_at_the_parent_is_not_hidden_even_when_reached() -> None:
    existing = fixture("workdir")
    parent = collected({"t.py::a": "x"}, defined=frozenset({existing}))
    reference = collected(
        {"t.py::a": "x", "t.py::b": "y"},
        reached={"t.py::b": (existing,)},
        defined=frozenset({existing}),
    )
    assert sort_tests(parent, reference).hidden_fixtures == ()


def test_fixtures_are_sorted_and_deduplicated_across_hidden_tests() -> None:
    first, second = (
        fixture("b_fixture", "tests/conftest.py"),
        fixture("a_fixture", "tests/sub/conftest.py"),
    )
    parent = collected({})
    reference = collected(
        {"t.py::a": "1", "t.py::b": "2"},
        reached={"t.py::a": (first, second), "t.py::b": (first,)},
        defined=frozenset({first, second}),
    )
    assert sort_tests(parent, reference).hidden_fixtures == (first, second)


def test_every_output_is_sorted() -> None:
    parent = collected({"z.py::t": "1", "a.py::t": "1"})
    reference = collected({"m.py::t": "1", "b.py::t": "1"})
    sets = sort_tests(parent, reference)
    assert sets.hidden_candidates == ("b.py::t", "m.py::t")
    assert sets.superseded == ("a.py::t", "z.py::t")


def test_empty_collections_give_empty_sets() -> None:
    sets = sort_tests(collected({}), collected({}))
    assert (sets.hidden_candidates, sets.superseded, sets.unchanged, sets.hidden_fixtures) == (
        (),
        (),
        (),
        (),
    )
