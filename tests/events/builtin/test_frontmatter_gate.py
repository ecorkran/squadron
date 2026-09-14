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
        # staged_paths is empty (D12) and filesChecked: 0 matches it, so this is a
        # legitimate pass, not the D10/D11 fail-closed cases.
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                return_value=_fake_process(0, stdout=b'{"totalFindings":0,"filesChecked":0}')
            ),
        ):
            result = await FrontmatterGateAction().execute(_commit_context(str(tmp_path)))

        assert result.success is True

    @pytest.mark.asyncio
    async def test_exit_1_fails_with_findings_passed_through(self, tmp_path: Path) -> None:
        # filesChecked matches the one staged path, so this exercises cf's own
        # findings-based failure, not the D10 worktree or D11 unreadable-count paths.
        findings = b'{"totalFindings":1,"findings":[{"message":"bad status"}],"filesChecked":1}'
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(1, stdout=findings)),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("doc.md",))
            )

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


class TestFilesCheckedFailClosed:
    """Slice 919 Part 3 (#98): D10 worktree cause, D11 unreadable count, D12
    zero-staged-is-fine, and the three failure messages must be pairwise
    distinguishable by content, not merely by ``success is False``.
    """

    @pytest.mark.asyncio
    async def test_zero_checked_against_nonempty_staged_fails_with_worktree_message(
        self, tmp_path: Path
    ) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                return_value=_fake_process(0, stdout=b'{"totalFindings":0,"filesChecked":0}')
            ),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md", "b.md"))
            )

        assert result.success is False
        assert result.error is not None
        assert "0 of 2" in result.error
        assert "worktree" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_staged_list_with_zero_checked_passes(self, tmp_path: Path) -> None:
        """D12: a commit staging no markdown gives cf nothing to check."""
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                return_value=_fake_process(0, stdout=b'{"totalFindings":0,"filesChecked":0}')
            ),
        ):
            result = await FrontmatterGateAction().execute(_commit_context(str(tmp_path)))

        assert result.success is True

    @pytest.mark.asyncio
    async def test_matching_checked_count_with_findings_fails_with_cfs_own_message(
        self, tmp_path: Path
    ) -> None:
        """Design criterion 2: the default-checkout, everything-worked-as-
        cf-intended failure case must still carry cf's own finding text, not
        one of the fail-closed messages this part adds."""
        findings = b'{"totalFindings":1,"findings":[{"message":"bad status"}],"filesChecked":1}'
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(1, stdout=findings)),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert result.success is False
        assert result.error is not None
        assert "bad status" in result.error
        assert "worktree" not in result.error.lower()
        assert "could not be read" not in result.error

    @pytest.mark.asyncio
    async def test_matching_checked_count_with_no_findings_passes(self, tmp_path: Path) -> None:
        """Design criterion 2's positive half: the default-checkout case that
        actually worked must still pass, unchanged from today."""
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                return_value=_fake_process(0, stdout=b'{"totalFindings":0,"filesChecked":1}')
            ),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_missing_files_checked_key_fails_with_unreadable_count_message(
        self, tmp_path: Path
    ) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(0, stdout=b'{"totalFindings":0}')),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert result.success is False
        assert result.error is not None
        assert "could not be read" in result.error

    @pytest.mark.asyncio
    async def test_unparseable_json_fails_with_unreadable_count_message(self, tmp_path: Path) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(0, stdout=b"not json at all")),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert result.success is False
        assert result.error is not None
        assert "could not be read" in result.error

    @pytest.mark.asyncio
    async def test_worktree_and_unreadable_count_messages_are_distinguishable(
        self, tmp_path: Path
    ) -> None:
        """The two D10/D11 messages must not collapse to the same text."""
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                return_value=_fake_process(0, stdout=b'{"totalFindings":0,"filesChecked":0}')
            ),
        ):
            worktree_result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(0, stdout=b"garbage")),
        ):
            unreadable_result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert worktree_result.error != unreadable_result.error


class TestSubprocessTimeout:
    """Slice 919 Part 3, D14: a hung ``cf`` is killed, reaped, logged at
    WARNING, and fails the gate with its own distinct message — the
    Failure-Mode Enumeration rule's required observable signal.
    """

    @pytest.mark.asyncio
    async def test_hung_process_is_killed_and_gate_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        from squadron.tools import limits

        monkeypatch.setattr(limits, "FRONTMATTER_GATE_TIMEOUT_S", 0.05)

        proc = MagicMock()

        async def _hang(*args: object, **kwargs: object) -> tuple[bytes, bytes]:
            await asyncio.sleep(10)
            return (b"", b"")  # pragma: no cover - never reached, timeout fires first

        proc.communicate = _hang
        proc.returncode = None
        proc.pid = 99999
        proc.wait = AsyncMock(return_value=None)

        kill_mock = AsyncMock()
        with (
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
            patch("squadron.events.builtin.frontmatter_gate._kill_process_group", new=kill_mock),
            caplog.at_level("WARNING", logger="squadron.events.builtin.frontmatter_gate"),
        ):
            result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error
        kill_mock.assert_awaited_once_with(proc)
        assert any("timed out" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_timeout_message_is_distinguishable_from_worktree_and_unreadable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from squadron.tools import limits

        monkeypatch.setattr(limits, "FRONTMATTER_GATE_TIMEOUT_S", 0.05)

        proc = MagicMock()

        async def _hang(*args: object, **kwargs: object) -> tuple[bytes, bytes]:
            await asyncio.sleep(10)
            return (b"", b"")  # pragma: no cover

        proc.communicate = _hang
        proc.returncode = None
        proc.pid = 99999
        proc.wait = AsyncMock(return_value=None)

        with (
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
            patch("squadron.events.builtin.frontmatter_gate._kill_process_group", new=AsyncMock()),
        ):
            timeout_result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                return_value=_fake_process(0, stdout=b'{"totalFindings":0,"filesChecked":0}')
            ),
        ):
            worktree_result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=_fake_process(0, stdout=b"garbage")),
        ):
            unreadable_result = await FrontmatterGateAction().execute(
                _commit_context(str(tmp_path), staged_paths=("a.md",))
            )

        assert timeout_result.error != worktree_result.error
        assert timeout_result.error != unreadable_result.error


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
