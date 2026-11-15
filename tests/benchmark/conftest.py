"""Benchmark test configuration.

The fixture projects hold deliberately failing tests; the repo's own pytest run must not
collect them (``testpaths = ["tests"]``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmark.grading_fixtures import GradingRepo, build_grading_repo

collect_ignore_glob = ["fixtures/*"]


@pytest.fixture
def grading_repo(tmp_path: Path) -> GradingRepo:
    """The start and reference commits of the grading fixture trees (slice 425)."""
    return build_grading_repo(tmp_path / "repo")
