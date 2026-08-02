"""Tests for project-identity derivation (T2/T3).

Covers URL normalization across remote-form variants, the recorded-id
fallback, explicit failure when neither source is present, and the
remote-absent / non-repo fall-through (git-remote-absent failure-mode row).
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.metrology.errors import MetrologyIdentityError, MetrologyTargetError
from squadron.metrology.identity import (
    derive_project_id,
    normalize_remote_url,
    read_review_frontmatter,
)
from squadron.metrology.models import ProjectIdSource


class TestNormalizeRemoteUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/manta/example-repo.git",
            "https://github.com/manta/example-repo",
            "git@github.com:manta/example-repo.git",
            "git@github.com:manta/example-repo",
            "https://user:token@github.com/manta/example-repo.git",
            "ssh://git@github.com/manta/example-repo.git",
            "https://github.com/manta/example-repo/",
        ],
    )
    def test_variants_collapse_to_one_canonical_id(self, url: str) -> None:
        assert normalize_remote_url(url) == "github.com/manta/example-repo"


class TestDeriveProjectId:
    def test_remote_url_yields_remote_sourced_id(self, repo_with_remote: Path) -> None:
        pid = derive_project_id(str(repo_with_remote))
        assert pid.value == "github.com/manta/example-repo"
        assert pid.source == ProjectIdSource.REMOTE

    def test_no_remote_with_recorded_id_returns_recorded(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.project_id": "acme/widget"})
        pid = derive_project_id(str(repo_no_remote))
        assert pid.value == "acme/widget"
        assert pid.source == ProjectIdSource.RECORDED

    def test_no_remote_no_recorded_id_raises_actionable(self, repo_no_remote: Path) -> None:
        with pytest.raises(MetrologyIdentityError) as exc:
            derive_project_id(str(repo_no_remote))
        # Actionable: names the config fix, never a path-derived fallback.
        assert "metrology.project_id" in str(exc.value)

    def test_non_repo_falls_through_to_recorded(
        self,
        non_repo_dir: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        # git absent-as-remote (non-repo) must not crash — it falls through.
        write_project_config(non_repo_dir, {"metrology.project_id": "plain/dir"})
        pid = derive_project_id(str(non_repo_dir))
        assert pid.value == "plain/dir"
        assert pid.source == ProjectIdSource.RECORDED

    def test_non_repo_no_recorded_id_raises(self, non_repo_dir: Path) -> None:
        with pytest.raises(MetrologyIdentityError):
            derive_project_id(str(non_repo_dir))

    def test_git_remote_timeout_falls_through_with_warning(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Failure-mode row: a hung git must not hang the function — a timeout is
        # treated as remote-absent (falls through to recorded id) and logged.
        write_project_config(repo_no_remote, {"metrology.project_id": "timeout/id"})
        with (
            caplog.at_level(logging.WARNING, logger="squadron.metrology.identity"),
            patch(
                "squadron.metrology.identity.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5.0),
            ),
        ):
            pid = derive_project_id(str(repo_no_remote))
        assert pid.value == "timeout/id"
        assert pid.source == ProjectIdSource.RECORDED
        assert any(
            "timed out" in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        )

    def test_git_remote_timeout_then_no_recorded_id_raises(self, repo_no_remote: Path) -> None:
        # Timeout + no recorded id → the identity error still fires (loud, not
        # a hang or a silent path-derived fallback).
        with patch(
            "squadron.metrology.identity.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5.0),
        ):
            with pytest.raises(MetrologyIdentityError):
                derive_project_id(str(repo_no_remote))


class TestReadReviewFrontmatter:
    """Direct coverage of read_review_frontmatter's own failure shapes, now
    that its parse delegates to documents.frontmatter.read_frontmatter
    (slice 911 Part B). Required-judge-field validation is a downstream
    concern tested in test_result_ref.py::TestResultRefFailures and is not
    duplicated here.
    """

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        with pytest.raises(MetrologyTargetError) as exc:
            read_review_frontmatter(missing)
        assert "nope.md" in str(exc.value)

    def test_no_frontmatter_block_raises(self, tmp_path: Path) -> None:
        review_file = tmp_path / "review.md"
        review_file.write_text("# Just a heading\n\nno frontmatter", encoding="utf-8")
        with pytest.raises(MetrologyTargetError):
            read_review_frontmatter(review_file)

    def test_unclosed_block_raises(self, tmp_path: Path) -> None:
        review_file = tmp_path / "review.md"
        review_file.write_text("---\ndocType: review\nno closing fence\n", encoding="utf-8")
        with pytest.raises(MetrologyTargetError):
            read_review_frontmatter(review_file)

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        review_file = tmp_path / "review.md"
        review_file.write_text("---\ndocType: [unclosed\n---\nbody\n", encoding="utf-8")
        with pytest.raises(MetrologyTargetError):
            read_review_frontmatter(review_file)

    def test_non_mapping_block_raises(self, tmp_path: Path) -> None:
        review_file = tmp_path / "review.md"
        review_file.write_text("---\njust a scalar string\n---\nbody\n", encoding="utf-8")
        with pytest.raises(MetrologyTargetError):
            read_review_frontmatter(review_file)

    def test_valid_frontmatter_returns_dict(self, tmp_path: Path) -> None:
        review_file = tmp_path / "review.md"
        review_file.write_text("---\ndocType: review\nverdict: PASS\n---\nbody\n", encoding="utf-8")
        result = read_review_frontmatter(review_file)
        assert result == {"docType": "review", "verdict": "PASS"}
