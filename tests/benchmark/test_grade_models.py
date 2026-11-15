"""``GradeResult``: pass rule and size caps (slice 425 Task 8)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from squadron.metrology.benchmark_nodes import NodeOutcome, NodeResult
from squadron.metrology.grade_models import (
    DETAIL_MAX_CHARS,
    MAX_LISTED_ITEMS,
    GradeResult,
    SnapshotRef,
    SuppressionCounts,
    check_detail,
)

HASH = "a" * 64


def make_result(**override: Any) -> GradeResult:
    fields: dict[str, Any] = {
        "hidden_total": 3,
        "hidden_passed": 3,
        "hidden_failures": (),
        "hidden_id_map_sha256": HASH,
        "injection_clashes": (),
        "injection_clash_count": 0,
        "regression_selected": 10,
        "regression_failures": (),
        "regression_failure_count": 0,
        "producer_new_passed": 0,
        "producer_new_failed": 0,
        "config_edits": (),
        "config_edit_count": 0,
        "test_edits": (),
        "test_edit_count": 0,
        "suppressions": SuppressionCounts(),
        "reinstalled": False,
        "lockfile_sha256": None,
        "snapshot": SnapshotRef(sha256=HASH),
        "lint_total": None,
        "type_total": None,
        "reviews": (),
        **override,
    }
    return GradeResult(**fields)


def node(outcome: NodeOutcome, node_id: str = "t.py::test_x") -> NodeResult:
    return NodeResult(node_id=node_id, outcome=outcome)


class TestPassed:
    def test_all_hidden_pass_and_no_regressions(self) -> None:
        assert make_result().passed

    def test_one_hidden_failure_does_not_pass(self) -> None:
        result = make_result(hidden_passed=2, hidden_failures=(node(NodeOutcome.FAILED),))
        assert not result.passed

    @pytest.mark.parametrize("outcome", [NodeOutcome.SKIPPED, NodeOutcome.NOT_RUN])
    def test_a_hidden_node_that_is_skipped_or_not_run_is_not_a_pass(self, outcome: NodeOutcome) -> None:
        result = make_result(hidden_passed=2, hidden_failures=(node(outcome),))
        assert not result.passed

    def test_one_regression_with_hidden_passing_does_not_pass(self) -> None:
        result = make_result(regression_failures=("t.py::test_y",), regression_failure_count=1)
        assert not result.passed

    def test_zero_hidden_and_zero_regressions_passes(self) -> None:
        """The 426 slice-case shape: no hidden set, so the pass is no regressions."""
        assert make_result(hidden_total=0, hidden_passed=0).passed

    def test_passed_is_not_a_stored_field(self) -> None:
        assert "passed" not in GradeResult.model_fields
        assert "passed" not in make_result().model_dump()


class TestCaps:
    @pytest.mark.parametrize(
        ("listing", "count"),
        [
            ("regression_failures", "regression_failure_count"),
            ("injection_clashes", "injection_clash_count"),
            ("config_edits", "config_edit_count"),
            ("test_edits", "test_edit_count"),
        ],
    )
    def test_a_list_over_the_cap_fails_validation(self, listing: str, count: str) -> None:
        too_many = tuple(f"item-{i}" for i in range(MAX_LISTED_ITEMS + 1))
        with pytest.raises(ValidationError, match=listing):
            make_result(**{listing: too_many, count: len(too_many)})

    def test_hidden_failures_over_the_cap_fail_validation(self) -> None:
        too_many = tuple(node(NodeOutcome.FAILED, f"t.py::t{i}") for i in range(MAX_LISTED_ITEMS + 1))
        with pytest.raises(ValidationError, match="hidden_failures"):
            make_result(hidden_total=100, hidden_passed=100 - len(too_many), hidden_failures=too_many)

    def test_a_list_at_the_cap_keeps_its_true_count(self) -> None:
        ids = tuple(f"item-{i}" for i in range(MAX_LISTED_ITEMS))
        result = make_result(regression_failures=ids, regression_failure_count=51)
        assert len(result.regression_failures) == MAX_LISTED_ITEMS
        assert result.regression_failure_count == 51

    def test_a_count_below_its_listing_fails_validation(self) -> None:
        with pytest.raises(ValidationError, match="regression_failures"):
            make_result(regression_failures=("a", "b"), regression_failure_count=1)

    def test_more_hidden_passed_than_total_fails_validation(self) -> None:
        with pytest.raises(ValidationError, match="hidden_passed"):
            make_result(hidden_total=1, hidden_passed=2)

    def test_a_non_digest_id_map_hash_fails_validation(self) -> None:
        with pytest.raises(ValidationError, match="sha256"):
            make_result(hidden_id_map_sha256="not-a-hash")


class TestDetail:
    def test_a_detail_at_the_cap_is_kept(self) -> None:
        detail = "x" * DETAIL_MAX_CHARS
        assert check_detail(detail) == detail

    def test_a_detail_over_the_cap_fails(self) -> None:
        with pytest.raises(ValueError, match="detail"):
            check_detail("x" * (DETAIL_MAX_CHARS + 1))

    def test_no_detail_is_fine(self) -> None:
        assert check_detail(None) is None
