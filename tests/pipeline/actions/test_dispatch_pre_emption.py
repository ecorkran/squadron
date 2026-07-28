"""Pre-emption fragment injection at dispatch (324 T8, T10).

The failure-mode cases are the substance here: a fragment problem must
never fail a dispatch, so every malformed input asserts *both* that the
prompt is unchanged and that the condition was made observable via a
WARNING. A silent skip would be indistinguishable from a working fragment.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.metrology.audit_models import AuditCategory, BaselineCell, ProjectBaseline
from squadron.metrology.models import ProjectId, ProjectIdSource
from squadron.metrology.preemption import render_fragment, write_fragment
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionContext, ActionResult

_FRAGMENT_OPEN = "--- Pre-emption: known issue classes for this project ---\n"
_FRAGMENT_CLOSE = "--- End pre-emption ---\n\n"
_OVERRIDE_OPEN = "--- Instructions from checkpoint resolution ---\n"


def _make_context(
    params: dict[str, object],
    prior_outputs: dict[str, ActionResult] | None = None,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test",
        run_id="run-123",
        params=params,
        step_name="step-1",
        step_index=0,
        prior_outputs=prior_outputs or {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/tmp",
        sdk_session=None,
    )


def _write_real_fragment(directory: Path) -> Path:
    """A fragment written by the production writer, not a hand-rolled string."""
    baseline = ProjectBaseline(
        project_id=ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE),
        commit_sha="a" * 40,
        audit_prompt_hash="b" * 64,
        run_id="audit-20260726-abcd1234",
        measured_at=datetime(2026, 7, 26, tzinfo=UTC),
        total_findings=3,
        unnormalized_count=0,
        cells=[BaselineCell(category=AuditCategory.TEST_DEBT, count=3, floor_note="no floor")],
    )
    return write_fragment(render_fragment(baseline), directory=directory)


class TestPreEmptionFragmentInjection:
    def test_valid_fragment_is_prepended(self, tmp_path: Path) -> None:
        path = _write_real_fragment(tmp_path)
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": str(path)})

        result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result.startswith(_FRAGMENT_OPEN)
        assert _FRAGMENT_CLOSE in result
        assert result.endswith("Original context")
        assert "Test debt" in result or "test" in result.lower()

    def test_fragment_wraps_outside_checkpoint_override(self, tmp_path: Path) -> None:
        """Decision 1's ordering: the override stays innermost, nearest the task."""
        path = _write_real_fragment(tmp_path)
        ctx = _make_context(
            params={
                "prompt": "Original context",
                "override_instructions": "do X",
                "pre_emption_fragment": str(path),
            }
        )

        result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result.startswith(_FRAGMENT_OPEN)
        assert result.index(_FRAGMENT_OPEN) < result.index(_OVERRIDE_OPEN)
        assert result.index(_OVERRIDE_OPEN) < result.index("Original context")
        assert result.endswith("Original context")

    def test_absent_param_leaves_prompt_unchanged(self) -> None:
        """Pre-324 behavior for every pipeline that does not opt in."""
        ctx = _make_context(params={"prompt": "Original context"})

        result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"
        assert "Pre-emption" not in result

    def test_empty_param_leaves_prompt_unchanged(self) -> None:
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": "   "})

        result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"

    def test_user_path_is_expanded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A configured '~/...' path must resolve, not be read literally."""
        path = _write_real_fragment(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        ctx = _make_context(
            params={"prompt": "Original context", "pre_emption_fragment": f"~/{path.name}"}
        )

        result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result.startswith(_FRAGMENT_OPEN)


class TestPreEmptionFragmentFailureModes:
    """All three modes degrade to a skipped prepend plus an observable WARNING."""

    def test_missing_path_warns_and_skips(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        missing = tmp_path / "never-generated.md"
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": str(missing)})

        with caplog.at_level(logging.WARNING):
            result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING
        assert str(missing) in caplog.text
        assert "not found" in caplog.text

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission semantics")
    def test_unreadable_file_warns_and_skips(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = _write_real_fragment(tmp_path)
        path.chmod(0o000)
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": str(path)})

        try:
            with caplog.at_level(logging.WARNING):
                result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]
        finally:
            path.chmod(0o644)

        assert result == "Original context"
        assert len(caplog.records) == 1
        assert "unreadable or has a malformed header" in caplog.text

    def test_empty_file_warns_and_skips(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        path = tmp_path / "empty.md"
        path.write_text("", encoding="utf-8")
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": str(path)})

        with caplog.at_level(logging.WARNING):
            result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"
        assert len(caplog.records) == 1
        assert "unreadable or has a malformed header" in caplog.text

    def test_malformed_header_warns_and_skips(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "malformed.md"
        path.write_text("no header here, just prose\n", encoding="utf-8")
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": str(path)})

        with caplog.at_level(logging.WARNING):
            result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"
        assert len(caplog.records) == 1
        assert "malformed header" in caplog.text

    def test_empty_body_is_distinguishable_from_malformed_header(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A valid header with no body names a different condition in the log."""
        path = tmp_path / "headers-only.md"
        path.write_text(
            f"---\naudit_prompt_hash: {'b' * 64}\n"
            f"measured_at: {datetime(2026, 7, 26, tzinfo=UTC).isoformat()}\n---\n\n\n",
            encoding="utf-8",
        )
        ctx = _make_context(params={"prompt": "Original context", "pre_emption_fragment": str(path)})

        with caplog.at_level(logging.WARNING):
            result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"
        assert len(caplog.records) == 1
        assert "empty body" in caplog.text
        assert "malformed header" not in caplog.text

    def test_directory_path_warns_and_skips(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A directory where a file was expected must not raise IsADirectoryError."""
        ctx = _make_context(
            params={"prompt": "Original context", "pre_emption_fragment": str(tmp_path)}
        )

        with caplog.at_level(logging.WARNING):
            result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result == "Original context"
        assert len(caplog.records) == 1

    def test_failure_still_applies_checkpoint_override(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A broken fragment must not cost the override its injection."""
        ctx = _make_context(
            params={
                "prompt": "Original context",
                "override_instructions": "do X",
                "pre_emption_fragment": str(tmp_path / "missing.md"),
            }
        )

        with caplog.at_level(logging.WARNING):
            result = DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]

        assert result.startswith(_OVERRIDE_OPEN)
        assert result.endswith("Original context")
        assert "Pre-emption" not in result
