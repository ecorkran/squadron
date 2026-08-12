"""Tests for squadron.frontmatter-gate (design D8, carrying 172's D6 posture)."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.events import EventType
from squadron.events.builtin.frontmatter_gate import FrontmatterGateAction
from squadron.events.contexts import CommitContext


def _commit_context(cwd: str, staged_paths: tuple[str, ...] = ()) -> CommitContext:
    return CommitContext(event=EventType.COMMIT, cwd=cwd, params={}, staged_paths=staged_paths)


async def _run_cf(args: list[str], *, cwd: str) -> None:
    """Off-thread ``cf`` invocation — a blocking subprocess call must not
    run directly inside an ``async def`` test method (project async rule)."""
    await asyncio.to_thread(subprocess.run, ["cf", *args], cwd=cwd, capture_output=True)


def _fake_process(returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


class TestExitMapping:
    def test_action_identity(self) -> None:
        action = FrontmatterGateAction()
        assert action.name == "squadron.frontmatter-gate"
        assert action.events == frozenset({EventType.COMMIT})

    @pytest.mark.asyncio
    async def test_exit_0_succeeds(self, tmp_path: Path) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(0, stdout=b'{"totalFindings":0}')),
        ):
            result = await FrontmatterGateAction().execute(_commit_context(str(tmp_path)))

        assert result.success is True

    @pytest.mark.asyncio
    async def test_exit_1_fails_with_findings_passed_through(self, tmp_path: Path) -> None:
        findings = b'{"totalFindings":1,"findings":[{"message":"bad status"}]}'
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(1, stdout=findings)),
        ):
            result = await FrontmatterGateAction().execute(_commit_context(str(tmp_path)))

        assert result.success is False
        assert result.error is not None and "bad status" in result.error

    @pytest.mark.asyncio
    async def test_exit_2_fails_with_actionable_message(self, tmp_path: Path) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(2, stderr=b"not a cf project")),
        ):
            result = await FrontmatterGateAction().execute(_commit_context(str(tmp_path)))

        assert result.success is False
        assert result.error is not None
        assert "cf init" in result.error

    @pytest.mark.asyncio
    async def test_missing_cf_fails_with_install_hint(self, tmp_path: Path) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await FrontmatterGateAction().execute(_commit_context(str(tmp_path)))

        assert result.success is False
        assert result.error is not None
        assert "not on PATH" in result.error


@pytest.mark.skipif(shutil.which("cf") is None, reason="handled by _require_cf below")
class TestRealCfIntegration:
    """One real-cf integration test per T15 — fails (never skips) if cf is
    absent, matching test_schema_drift.py's posture."""

    def _require_cf(self) -> None:
        if shutil.which("cf") is None:
            pytest.fail(
                "'cf' is not on PATH — this integration test requires "
                "context-forge >= 0.12.0 and must fail, not skip, without it."
            )

    @pytest.mark.asyncio
    async def test_bad_frontmatter_fails_with_finding_text(self, tmp_path: Path) -> None:
        self._require_cf()
        doc_root = tmp_path / "project-documents" / "user" / "reviews"
        doc_root.mkdir(parents=True)
        bad_doc = doc_root / "zz-test-bad.md"
        bad_doc.write_text(
            "---\ndocType: review\nproject: test-project\nstatus: not-a-real-status\n"
            "dateCreated: 20260101\ndateUpdated: 20260101\n---\nbody\n"
        )
        await _run_cf(["init", "--lite", "--no-ide"], cwd=str(tmp_path))
        try:
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=(str(bad_doc),))
            )
        finally:
            await _run_cf(["project", "rm", tmp_path.name, "--yes"], cwd=str(tmp_path))

        assert result.success is False
        assert result.error is not None and "status" in result.error.lower()

    @pytest.mark.asyncio
    async def test_clean_doc_succeeds(self, tmp_path: Path) -> None:
        self._require_cf()
        doc_root = tmp_path / "project-documents" / "user" / "reviews"
        doc_root.mkdir(parents=True)
        clean_doc = doc_root / "zz-test-clean.md"
        clean_doc.write_text(
            "---\ndocType: review\nproject: test-project\nstatus: complete\n"
            "dateCreated: 20260101\ndateUpdated: 20260101\n---\nbody\n"
        )
        await _run_cf(["init", "--lite", "--no-ide"], cwd=str(tmp_path))
        try:
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=(str(clean_doc),))
            )
        finally:
            await _run_cf(["project", "rm", tmp_path.name, "--yes"], cwd=str(tmp_path))

        assert result.success is True
