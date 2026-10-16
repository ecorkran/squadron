"""Initiative-scoped (``plan``, no slice) dispatch post-condition: the
architecture document must have been written this run."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.events import EventType
from squadron.events.builtin.dispatch_artifact import (
    _dispatch_artifact_post_condition_error,  # pyright: ignore[reportPrivateUsage]
)
from squadron.events.contexts import PostActionContext
from squadron.events.dispatcher import (  # pyright: ignore[reportPrivateUsage]
    OutcomeErrorKind,
    _run_binding,
)
from squadron.events.manifest import Binding
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.failure_kind import FailureKind
from squadron.pipeline.models import ActionResult
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


# --- ContextForgeError is a one-line failure (slice 945 D5, #202) ---

_CF_MESSAGE = "No slice plan configured. Set one with: cf set slicePlan <path>"


def _cf_failing_context() -> PostActionContext:
    cf_client = MagicMock()
    cf_client.list_slices.side_effect = ContextForgeError(_CF_MESSAGE)
    return PostActionContext(
        event=EventType.POST_ACTION,
        cwd=".",
        params={"slice": "127"},
        action_type="dispatch",
        result=ActionResult(success=True, action_type="dispatch", outputs={"response": "done"}),
        run_id="run-1",
        run_started_at=datetime.now(tz=UTC),
        run_state_error=None,
        step_name="design",
        step_type="design",
        expected_artifact_kind=ArtifactKind.DESIGN,
        iteration=0,
        cf_client=cf_client,
    )


async def test_cf_error_is_a_failed_outcome_with_the_cf_text_and_no_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    binding = Binding(
        event=EventType.POST_ACTION,
        action="squadron.dispatch-artifact",
        params={},
        source="built-in",
    )

    with caplog.at_level(logging.WARNING):
        outcome = await _run_binding(binding, _cf_failing_context(), 5)

    assert outcome.error_kind is OutcomeErrorKind.NONE
    assert outcome.result is not None
    assert outcome.result.success is False
    assert outcome.result.error is not None
    assert _CF_MESSAGE in outcome.result.error
    assert outcome.result.metadata["failure_kind"] == FailureKind.ARTIFACT_MISSING.value
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any(_CF_MESSAGE in r.getMessage() for r in errors)
    assert all(r.exc_info is None for r in errors)
