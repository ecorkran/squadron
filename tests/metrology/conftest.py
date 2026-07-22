"""Shared fixtures for metrology tests.

Provides isolated tmp_path git repos (with / without a remote), a
project-config writer for ``.squadron.toml``, and user-config isolation so
that a developer's real ``~/.config/squadron/config.toml`` can never leak a
recorded ``metrology.project_id`` into a test that asserts its absence.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w

from squadron.metrology.models import (
    JudgeConfigId,
    JudgeResultRef,
    ProjectId,
    ProjectIdSource,
    SampleVerdict,
)
from squadron.review.models import ReviewFinding, ReviewResult, Verdict
from squadron.review.persistence import SliceInfo, format_review_markdown


def make_sample_verdict(
    *,
    sample_id: str = "sample-20260722-abcd1234",
    project_value: str = "github.com/manta/example-repo",
    template_name: str = "judge.slice-vs-arch",
    model: str = "minimax/minimax-m2.7",
    human_verdict: Verdict = Verdict.PASS,
    content_hash: str = "0" * 64,
    artifact_level: str | None = "slice",
) -> SampleVerdict:
    """A fully-populated SampleVerdict for store/model tests."""
    pid = ProjectId(value=project_value, source=ProjectIdSource.REMOTE)
    return SampleVerdict(
        sample_id=sample_id,
        project_id=pid,
        result_ref=JudgeResultRef(
            project_id=project_value,
            relative_review_path="project-documents/user/reviews/302-review.judge.x.example.md",
            content_hash=content_hash,
        ),
        judge_config=JudgeConfigId(template_name=template_name, model=model),
        human_verdict=human_verdict,
        human_note=None,
        artifact_level=artifact_level,
        captured_at=datetime(2026, 7, 22, tzinfo=UTC),
    )


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


@dataclass(frozen=True)
class CaptureProject:
    """A ready-to-sample project: git repo + reviews dir + graded artifact."""

    root: Path
    review_file: Path
    artifact_file: Path
    review_index: int
    review_type: str


def _build_capture_project(root: Path, remote: str, body: str) -> CaptureProject:
    """Build a capture-ready project at ``root``: repo + review + artifact.

    The persisted review's ``sourceDocument`` points at a real on-disk slice
    design (the ground truth capture loads), so the whole capture flow — target
    resolution, blind payload, identity, ref — runs end to end.
    """
    _init_repo(root)
    _git("remote", "add", "origin", remote, cwd=root)

    artifact_rel = "project-documents/user/slices/500-slice.example.md"
    artifact = root / artifact_rel
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        f"---\ndocType: slice-design\nslice: example\n---\n\n# Example slice\n\n{body}\n",
        encoding="utf-8",
    )

    reviews_dir = root / "project-documents/user/reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review = make_judge_result()
    slice_info = SliceInfo(
        index=500,
        name="Example",
        slice_name="example",
        design_file=artifact_rel,
        task_files=[],
        arch_file="",
        project="squadron",
    )
    content = format_review_markdown(
        review,
        "judge.slice-vs-arch",
        slice_info=slice_info,
        source_document=artifact_rel,
        verdict_override=review.verdict.value,
    )
    review_file = reviews_dir / "500-review.judge.slice-vs-arch.example.md"
    review_file.write_text(content, encoding="utf-8")

    return CaptureProject(
        root=root,
        review_file=review_file,
        artifact_file=artifact,
        review_index=500,
        review_type="judge.slice-vs-arch",
    )


@pytest.fixture
def capture_project(tmp_path: Path, isolated_user_config: Path) -> CaptureProject:
    """A ready-to-sample project rooted in a git repo with a known remote."""
    return _build_capture_project(
        tmp_path / "capture-repo",
        "https://github.com/manta/capture-repo.git",
        "Ground truth body.",
    )


@pytest.fixture
def make_second_project(tmp_path: Path, isolated_user_config: Path) -> CaptureProject:
    """A second capture-ready project with a distinct remote (cross-project)."""
    return _build_capture_project(
        tmp_path / "capture-repo-b",
        "https://github.com/manta/capture-repo-b.git",
        "Second project body.",
    )
