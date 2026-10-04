"""Initiative-scoped (``plan``, no slice) dispatch post-condition: the
architecture document must have been written this run."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from squadron.events.builtin.dispatch_artifact import (
    _dispatch_artifact_post_condition_error,  # pyright: ignore[reportPrivateUsage]
)
from squadron.pipeline.steps.phase import ArtifactKind

_ARCH = Path("project-documents/user/architecture/100-arch.tally-core.md")


def _check(cwd: Path, started: datetime) -> str | None:
    return _dispatch_artifact_post_condition_error(
        kind=ArtifactKind.DESIGN,
        slice_param=None,
        plan_param="100",
        cf_client=MagicMock(),
        cwd=str(cwd),
        run_started_at=started,
        run_state_error=None,
    )


def _write_arch(cwd: Path, mtime: datetime) -> None:
    path = cwd / _ARCH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Architecture\n")
    os.utime(path, (mtime.timestamp(), mtime.timestamp()))


def test_arch_doc_written_this_run_passes(tmp_path: Path) -> None:
    started = datetime.now(tz=UTC) - timedelta(minutes=1)
    _write_arch(tmp_path, datetime.now(tz=UTC))
    assert _check(tmp_path, started) is None


def test_stale_arch_doc_fails(tmp_path: Path) -> None:
    started = datetime.now(tz=UTC)
    _write_arch(tmp_path, started - timedelta(hours=1))
    error = _check(tmp_path, started)
    assert error is not None
    assert "initiative 100" in error


def test_missing_arch_doc_fails(tmp_path: Path) -> None:
    error = _check(tmp_path, datetime.now(tz=UTC))
    assert error is not None
    assert "100-arch.*.md" in error
