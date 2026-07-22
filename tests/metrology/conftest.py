"""Shared fixtures for metrology tests.

Provides isolated tmp_path git repos (with / without a remote), a
project-config writer for ``.squadron.toml``, and user-config isolation so
that a developer's real ``~/.config/squadron/config.toml`` can never leak a
recorded ``metrology.project_id`` into a test that asserts its absence.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w

from squadron.review.models import ReviewFinding, ReviewResult, Verdict
from squadron.review.persistence import SliceInfo, format_review_markdown


def _git(*args: str, cwd: Path) -> None:
    """Run a git command in ``cwd``, raising on failure (test setup only)."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", cwd=path)
    # Local identity so commits (if any) don't depend on global git config.
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)


@pytest.fixture
def isolated_user_config(tmp_path: Path) -> Iterator[Path]:
    """Redirect the user-level config file to an empty temp file.

    Without this, ``get_config`` merges the real user config, which could
    supply a ``metrology.project_id`` and mask the no-identity path.
    """
    user_file = tmp_path / "user-config" / "config.toml"
    user_file.parent.mkdir(parents=True, exist_ok=True)
    with patch("squadron.config.manager.user_config_path", return_value=user_file):
        yield user_file


@pytest.fixture
def repo_with_remote(tmp_path: Path, isolated_user_config: Path) -> Path:
    """A git repo whose origin remote is a known URL."""
    repo = tmp_path / "repo-remote"
    _init_repo(repo)
    _git(
        "remote",
        "add",
        "origin",
        "https://github.com/manta/example-repo.git",
        cwd=repo,
    )
    return repo


@pytest.fixture
def repo_no_remote(tmp_path: Path, isolated_user_config: Path) -> Path:
    """A git repo with no origin remote."""
    repo = tmp_path / "repo-no-remote"
    _init_repo(repo)
    return repo


@pytest.fixture
def non_repo_dir(tmp_path: Path, isolated_user_config: Path) -> Path:
    """A plain directory that is not a git repository."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    return plain


@pytest.fixture
def write_project_config() -> Callable[[Path, dict[str, object]], Path]:
    """Return a writer that dumps keys into ``<cwd>/.squadron.toml``."""

    def _write(cwd: Path, values: dict[str, object]) -> Path:
        path = cwd / ".squadron.toml"
        existing: dict[str, object] = {}
        if path.is_file():
            import tomllib

            with open(path, "rb") as handle:
                existing = dict(tomllib.load(handle))
        existing.update(values)
        with open(path, "wb") as handle:
            tomli_w.dump(existing, handle)
        return path

    return _write


def make_judge_result(
    *,
    verdict: Verdict = Verdict.PASS,
    score: float = 98.0,
    criteria: dict[str, float] | None = None,
    findings: list[ReviewFinding] | None = None,
    model: str = "minimax/minimax-m2.7",
) -> ReviewResult:
    """A ReviewResult shaped like a persisted 300 judge result."""
    return ReviewResult(
        verdict=verdict,
        findings=findings if findings is not None else [],
        raw_output="",
        template_name="judge.slice-vs-arch",
        input_files={"slice_design": "slices/302-slice.example.md"},
        timestamp=datetime(2026, 7, 14, tzinfo=UTC),
        model=model,
        score=score,
        criteria=criteria if criteria is not None else {"alignment": 95.0, "scope": 100.0},
    )


@pytest.fixture
def write_review_file() -> Callable[..., Path]:
    """Return a writer that persists a judge review in the production format.

    Uses ``format_review_markdown`` — the exact writer the 300 path uses — so
    the parser under test consumes the real on-disk shape, not a hand-rolled
    approximation (CLAUDE.md parser-fixture rule).
    """

    def _write(
        target_dir: Path,
        *,
        filename: str = "302-review.judge.slice-vs-arch.example.md",
        review_type: str = "judge.slice-vs-arch",
        result: ReviewResult | None = None,
        raw_text: str | None = None,
    ) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        if raw_text is not None:
            path.write_text(raw_text, encoding="utf-8")
            return path
        review = result if result is not None else make_judge_result()
        slice_info = SliceInfo(
            index=302,
            name="Example",
            slice_name="example",
            design_file="project-documents/user/slices/302-slice.example.md",
            task_files=[],
            arch_file="",
            project="squadron",
        )
        content = format_review_markdown(
            review,
            review_type,
            slice_info=slice_info,
            source_document="project-documents/user/slices/302-slice.example.md",
            verdict_override=review.verdict.value,
        )
        path.write_text(content, encoding="utf-8")
        return path

    return _write
