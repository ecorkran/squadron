"""Fixtures shared by the stats tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.stats.repo_support import StatsRepo


@pytest.fixture
def stats_repo(tmp_path: Path) -> StatsRepo:
    """An empty repo on ``main``; tests add commits with chosen paths and dates."""
    return StatsRepo(tmp_path / "repo")
