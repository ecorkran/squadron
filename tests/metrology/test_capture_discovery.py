"""Tests for judge-result discovery enumeration and tolerance (T13/T13b)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from squadron.metrology.discovery import discover_judge_results
from squadron.review.templates import ReviewTemplate, clear_registry, register_template

_REVIEWS_DIR = "project-documents/user/reviews"


def _make_template(name: str, *, is_judge: bool) -> ReviewTemplate:
    return ReviewTemplate(
        name=name,
        description="Example",
        system_prompt="You are a reviewer.",
        allowed_tools=[],
        permission_mode="default",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        prompt_template="Review this: {input}",
        judge={"pass_floor": 78, "concerns_floor": 55} if is_judge else None,
    )


@pytest.fixture(autouse=True)
def _clear_template_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    clear_registry()
    yield
    clear_registry()


class TestDiscoverJudgeResults:
    def test_mixed_fixture_returns_only_judge_results(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        register_template(_make_template("judge.example", is_judge=True))
        register_template(_make_template("arch", is_judge=False))

        reviews_dir = tmp_path / _REVIEWS_DIR
        judge_file = write_review_file(
            reviews_dir,
            filename="500-review.judge.example.md",
            review_type="judge.example",
        )
        write_review_file(
            reviews_dir,
            filename="500-review.arch.md",
            review_type="arch",
        )

        result = discover_judge_results(str(tmp_path))
        assert result == [judge_file]

    def test_corrupt_sibling_skipped_with_warning(
        self,
        tmp_path: Path,
        write_review_file: Callable[..., Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        register_template(_make_template("judge.example", is_judge=True))
        reviews_dir = tmp_path / _REVIEWS_DIR
        judge_file = write_review_file(
            reviews_dir,
            filename="500-review.judge.example.md",
            review_type="judge.example",
        )
        corrupt = reviews_dir / "501-review.judge.corrupt.md"
        corrupt.write_text("no frontmatter here at all", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="squadron.metrology.discovery"):
            result = discover_judge_results(str(tmp_path))

        assert result == [judge_file]
        assert any(
            "501-review.judge.corrupt.md" in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        )

    def test_empty_reviews_directory_returns_empty_list(self, tmp_path: Path) -> None:
        (tmp_path / _REVIEWS_DIR).mkdir(parents=True)
        assert discover_judge_results(str(tmp_path)) == []

    def test_missing_reviews_directory_returns_empty_list(self, tmp_path: Path) -> None:
        assert discover_judge_results(str(tmp_path)) == []

    def test_gate_evidence_artifact_is_never_a_judge_result(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        """A findings-addressed gate's evidence sits in the reviews directory
        beside real judge results and must be excluded by its name, not by a
        filter (slice 305 F003). Written through the real persistence path so
        a filename-pattern change breaks this test."""
        from squadron.pipeline.actions.findings_addressed import GateEvidence, save_gate_evidence

        register_template(_make_template("judge.example", is_judge=True))
        reviews_dir = tmp_path / _REVIEWS_DIR
        judge_file = write_review_file(
            reviews_dir,
            filename="305-review.judge.example.md",
            review_type="judge.example",
        )
        save_gate_evidence(
            GateEvidence(
                policy="findings-addressed",
                reduced_verdict="FAIL",
                addressed_verdict="FAIL",
                review_verdict="CONCERNS",
                revision_number=2,
            ),
            step_name="settled",
            slice_index=305,
            cwd=str(tmp_path),
        )

        assert discover_judge_results(str(tmp_path)) == [judge_file]

    def test_unresolvable_review_type_skipped(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        # Deliberately do not register any template for this reviewType.
        reviews_dir = tmp_path / _REVIEWS_DIR
        write_review_file(
            reviews_dir,
            filename="500-review.judge.unregistered.md",
            review_type="judge.unregistered",
        )
        assert discover_judge_results(str(tmp_path)) == []
