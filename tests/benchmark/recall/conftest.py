"""Recall test fixtures: the fixture bug repo, a scripted process runner, a fixed clock."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from tests.benchmark.recall.fixtures.bug_repo.build import BuiltBugRepo, build
from tests.benchmark.recall.support import FIXED_NOW
from tests.benchmark.support import Handler, ScriptedRunner


@pytest.fixture
def bug_repo(tmp_path: Path) -> BuiltBugRepo:
    return build(tmp_path / "bug_repo")


@pytest.fixture
def scripted_runner() -> Callable[[Handler], ScriptedRunner]:
    """Build a ``ScriptedRunner`` from a handler; it records argv of every call."""
    return ScriptedRunner


@pytest.fixture
def fixed_clock() -> Callable[[], datetime]:
    return lambda: FIXED_NOW
