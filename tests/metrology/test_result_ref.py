"""Tests for the content-addressed result ref and judge-config id (T4/T5).

Fixtures write the review file via the production ``format_review_markdown``
writer, so these assert on the exact on-disk shape the parser meets in
production (CLAUDE.md parser-fixture rule).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.metrology.errors import MetrologyTargetError
from squadron.metrology.identity import derive_judge_config_id, derive_result_ref
from squadron.metrology.models import ProjectId, ProjectIdSource
from squadron.review.models import ReviewFinding, Severity, Verdict
from tests.metrology.conftest import make_judge_result

_PID = ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE)


class TestResultRefStability:
    def test_identical_content_yields_identical_hash(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        a = write_review_file(tmp_path / "a", filename="302-review.judge.x.example.md")
        b = write_review_file(tmp_path / "b", filename="302-review.judge.x.example.md")
        ref_a = derive_result_ref(a, _PID, cwd=str(tmp_path / "a"))
        ref_b = derive_result_ref(b, _PID, cwd=str(tmp_path / "b"))
        assert ref_a.content_hash == ref_b.content_hash

    def test_changed_score_changes_hash(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        base = write_review_file(tmp_path / "a", result=make_judge_result(score=98.0))
        changed = write_review_file(tmp_path / "b", result=make_judge_result(score=42.0))
        ref_a = derive_result_ref(base, _PID, cwd=str(tmp_path / "a"))
        ref_b = derive_result_ref(changed, _PID, cwd=str(tmp_path / "b"))
        assert ref_a.content_hash != ref_b.content_hash

    def test_changed_verdict_changes_hash(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        base = write_review_file(tmp_path / "a", result=make_judge_result(verdict=Verdict.PASS))
        changed = write_review_file(tmp_path / "b", result=make_judge_result(verdict=Verdict.FAIL))
        ref_a = derive_result_ref(base, _PID, cwd=str(tmp_path / "a"))
        ref_b = derive_result_ref(changed, _PID, cwd=str(tmp_path / "b"))
        assert ref_a.content_hash != ref_b.content_hash

    def test_finding_order_does_not_change_hash(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        f1 = ReviewFinding(severity=Severity.NOTE, title="Alpha", description="a")
        f2 = ReviewFinding(severity=Severity.CONCERN, title="Beta", description="b")
        forward = write_review_file(tmp_path / "a", result=make_judge_result(findings=[f1, f2]))
        reversed_order = write_review_file(tmp_path / "b", result=make_judge_result(findings=[f2, f1]))
        ref_a = derive_result_ref(forward, _PID, cwd=str(tmp_path / "a"))
        ref_b = derive_result_ref(reversed_order, _PID, cwd=str(tmp_path / "b"))
        # Positional ids (F001, F002…) flip on reorder, so the canonical
        # projection excludes the id and sorts findings by content — the same
        # finding set hashes identically regardless of listed order.
        assert ref_a.content_hash == ref_b.content_hash

    def test_changed_findings_change_hash(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        f1 = ReviewFinding(severity=Severity.NOTE, title="Alpha", description="a")
        base = write_review_file(tmp_path / "a", result=make_judge_result(findings=[]))
        with_finding = write_review_file(tmp_path / "b", result=make_judge_result(findings=[f1]))
        ref_a = derive_result_ref(base, _PID, cwd=str(tmp_path / "a"))
        ref_b = derive_result_ref(with_finding, _PID, cwd=str(tmp_path / "b"))
        assert ref_a.content_hash != ref_b.content_hash


class TestResultRefFailures:
    def test_missing_file_raises_target_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        with pytest.raises(MetrologyTargetError) as exc:
            derive_result_ref(missing, _PID, cwd=str(tmp_path))
        assert "nope.md" in str(exc.value)

    def test_no_frontmatter_raises_target_error(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        path = write_review_file(tmp_path, raw_text="# Just a heading\n\nno frontmatter")
        with pytest.raises(MetrologyTargetError):
            derive_result_ref(path, _PID, cwd=str(tmp_path))

    def test_missing_required_judge_fields_raises(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        # Frontmatter present but no score/reviewType/aiModel — a partial
        # result must never be hashed.
        raw = "---\ndocType: review\nslice: x\n---\n\n# body\n"
        path = write_review_file(tmp_path, raw_text=raw)
        with pytest.raises(MetrologyTargetError) as exc:
            derive_result_ref(path, _PID, cwd=str(tmp_path))
        assert "missing required judge field" in str(exc.value)


class TestJudgeConfigId:
    def test_returns_template_model_and_hash_slot(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        path = write_review_file(tmp_path)
        cfg = derive_judge_config_id(path)
        assert cfg.template_name == "judge.slice-vs-arch"
        assert cfg.model == "minimax/minimax-m2.7"
        # template_content_hash is None when the reviewType doesn't resolve to
        # a known template by name (never fabricated) — 322 finalizes the key.
        assert cfg.template_content_hash is None

    def test_malformed_file_raises_target_error(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        raw = "---\ndocType: review\n---\n\nbody\n"
        path = write_review_file(tmp_path, raw_text=raw)
        with pytest.raises(MetrologyTargetError):
            derive_judge_config_id(path)
