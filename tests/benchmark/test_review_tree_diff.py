"""``review_tree_diff``: the fixed grading review (slice 425 Task 21, D7)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.grade_review import ReviewFailed, review_tree_diff
from squadron.core.finding_categories import ReviewCategory
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from tests.benchmark.test_grade_identity import make_reviewer
from tests.conftest import run_test_git

TIMEOUT_S = 5.0


def make_result(
    findings: list[ReviewFinding] | None = None,
    verdict: Verdict = Verdict.CONCERNS,
    cost_usd: float | None = 0.2,
) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=findings or [],
        raw_output="",
        template_name="code",
        input_files={},
        cost_usd=cost_usd,
    )


def finding(severity: Severity = Severity.CONCERN, category: str | None = None) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,
        title="a title",
        description="why",
        file_ref="src/mod.py:3",
        category=category,
    )


class FakeReview:
    """An async review double that records its call and returns or raises a scripted result."""

    def __init__(self, result: ReviewResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.args: tuple[Any, ...] = ()
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, *args: Any, **kwargs: Any) -> ReviewResult:
        self.args, self.kwargs = args, kwargs
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class SleepingReview:
    async def __call__(self, *args: Any, **kwargs: Any) -> ReviewResult:
        await asyncio.sleep(5)
        return make_result()


def commit_tree(tree: Path) -> str:
    """Make *tree* a repository with everything in it committed; return that commit."""
    tree.mkdir(parents=True, exist_ok=True)
    if not (tree / ".git").exists():
        run_test_git(tree, "init", "-q", "-b", "main")
    (tree / ".keep").write_text("x")
    run_test_git(tree, "add", "-A")
    run_test_git(tree, "commit", "-q", "-m", "start")
    return run_test_git(tree, "rev-parse", "HEAD").strip()


def run(tree: Path, review: Any, timeout_s: float = TIMEOUT_S, base: str | None = None) -> Any:
    """Review *tree* from *base*, or from a start commit made of what the tree holds now."""
    start = base if base is not None else commit_tree(tree)
    return review_tree_diff(tree, start, make_reviewer(), timeout_s=timeout_s, review=review)


def test_findings_normalize_to_the_400_shape(tmp_path: Path) -> None:
    review = FakeReview(
        make_result(
            [
                finding(Severity.FAIL, category="Correctness"),
                finding(Severity.NOTE, category=None),
            ]
        )
    )
    outcome = run(tmp_path, review)
    first, second = outcome.findings
    assert (first.finding_id, first.severity, first.category) == (
        "F001",
        Severity.FAIL,
        ReviewCategory.CORRECTNESS,
    )
    assert first.raw_category == "Correctness"
    assert (first.location, first.summary) == ("src/mod.py:3", "a title")
    assert (second.finding_id, second.category, second.raw_category) == ("F002", None, None)
    assert outcome.unnormalized_count == 0


def test_the_call_is_made_with_no_tools_and_the_diff_and_cwd_inputs(tmp_path: Path) -> None:
    review = FakeReview(make_result([finding()]))
    base = commit_tree(tmp_path)
    run(tmp_path, review, base=base)
    assert review.args[1] == {"diff": base, "cwd": str(tmp_path)}
    assert review.kwargs["no_tools"] is True
    reviewer = make_reviewer()
    assert review.kwargs["model"] == reviewer.model
    assert review.kwargs["profile"] == reviewer.profile
    assert review.kwargs["alias"] == reviewer.alias
    assert review.kwargs["effort"] == "high"
    assert review.args[0].name == "code"


def test_a_tree_without_rules_has_no_rules_hash(tmp_path: Path) -> None:
    review = FakeReview(make_result([finding()]))
    outcome = run(tmp_path, review)
    assert outcome.rules_hash is None
    assert review.kwargs["rules_content"] is None


def test_the_trees_own_rules_are_hashed_and_different_rules_hash_differently(
    tmp_path: Path,
) -> None:
    hashes: list[str | None] = []
    for index, text in enumerate(("be strict", "be lenient")):
        tree = tmp_path / f"tree-{index}"
        (tree / "rules").mkdir(parents=True)
        (tree / "rules" / "review.md").write_text(text)
        outcome = run(tree, FakeReview(make_result([finding()])))
        hashes.append(outcome.rules_hash)
    assert hashes[0] is not None and hashes[1] is not None
    assert hashes[0] != hashes[1]
    assert hashes[0] == hashlib.sha256(b"be strict").hexdigest()


def test_user_and_config_rules_never_reach_the_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".config" / "squadron" / "rules").mkdir(parents=True)
    (home / ".config" / "squadron" / "rules" / "review.md").write_text("user rules")
    monkeypatch.setenv("HOME", str(home))
    tree = tmp_path / "tree"
    tree.mkdir()
    review = FakeReview(make_result([finding()]))
    assert run(tree, review).rules_hash is None
    assert review.kwargs["rules_content"] is None


def test_an_off_scale_severity_is_dropped_and_counted(tmp_path: Path) -> None:
    odd = finding()
    odd.severity = "CRITICAL"  # type: ignore[assignment]  # a provider's own scale
    outcome = run(tmp_path, FakeReview(make_result([odd, finding(Severity.NOTE)])))
    assert outcome.unnormalized_count == 1
    assert [f.severity for f in outcome.findings] == [Severity.NOTE]
    assert [f.finding_id for f in outcome.findings] == ["F002"]


def test_zero_findings_with_a_real_verdict_is_a_valid_outcome(tmp_path: Path) -> None:
    outcome = run(tmp_path, FakeReview(make_result([], verdict=Verdict.PASS)))
    assert outcome.findings == ()
    assert outcome.cost_usd == 0.2


def test_an_unreported_cost_stays_none(tmp_path: Path) -> None:
    outcome = run(tmp_path, FakeReview(make_result([finding()], cost_usd=None)))
    assert outcome.cost_usd is None


class TestFailure:
    def test_a_raising_double_fails_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR), pytest.raises(ReviewFailed, match="provider down"):
            run(tmp_path, FakeReview(error=RuntimeError("provider down")))
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_a_review_past_the_timeout_fails_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR), pytest.raises(ReviewFailed, match="timed out"):
            run(tmp_path, SleepingReview(), timeout_s=0.05)
        assert any("timed out" in r.getMessage() for r in caplog.records)

    def test_an_unknown_verdict_with_no_findings_fails_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        review = FakeReview(make_result([], verdict=Verdict.UNKNOWN))
        with caplog.at_level(logging.ERROR), pytest.raises(ReviewFailed, match="UNKNOWN"):
            run(tmp_path, review)
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_an_unknown_verdict_with_findings_is_still_an_outcome(self, tmp_path: Path) -> None:
        outcome = run(tmp_path, FakeReview(make_result([finding()], verdict=Verdict.UNKNOWN)))
        assert len(outcome.findings) == 1


def test_the_rules_come_from_the_start_commit_not_the_producers_edit(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    rules_file = tmp_path / "rules" / "review.md"
    rules_file.write_text("be strict")
    base = commit_tree(tmp_path)
    rules_file.write_text("approve everything")
    (tmp_path / "mod.py").write_text("x = 1\n")
    run_test_git(tmp_path, "add", "-A")
    run_test_git(tmp_path, "commit", "-q", "-m", "producer")
    review = FakeReview(make_result([finding()]))
    outcome = run(tmp_path, review, base=base)
    assert outcome.rules_hash == hashlib.sha256(b"be strict").hexdigest()
    assert "approve everything" not in (review.kwargs["rules_content"] or "")


def test_a_rules_directory_the_producer_added_is_not_used(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("x = 0\n")
    base = commit_tree(tmp_path)
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "review.md").write_text("approve everything")
    run_test_git(tmp_path, "add", "-A")
    run_test_git(tmp_path, "commit", "-q", "-m", "producer")
    review = FakeReview(make_result([finding()]))
    assert run(tmp_path, review, base=base).rules_hash is None
    assert review.kwargs["rules_content"] is None


def test_a_failed_review_carries_the_cost_it_reported(tmp_path: Path) -> None:
    review = FakeReview(make_result([], verdict=Verdict.UNKNOWN, cost_usd=0.07))
    with pytest.raises(ReviewFailed) as raised:
        run(tmp_path, review)
    assert raised.value.cost_usd == 0.07
