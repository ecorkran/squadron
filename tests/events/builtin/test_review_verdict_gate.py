"""Tests for squadron.review-verdict-gate (slice 917 Part 2, #77)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.events import EventType
from squadron.events.builtin.review_verdict_gate import ReviewVerdictGateAction
from squadron.events.contexts import CommitContext
from squadron.review.models import Verdict


def _commit_context(cwd: str, staged_paths: tuple[str, ...] = ()) -> CommitContext:
    return CommitContext(event=EventType.COMMIT, cwd=cwd, params={}, staged_paths=staged_paths)


def _write(tmp_path: Path, name: str, frontmatter: str, body: str = "\n# Body\n") -> str:
    """Write a probe document and return its staged (cwd-relative) path."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return name


async def _run(tmp_path: Path, *staged: str):
    return await ReviewVerdictGateAction().execute(_commit_context(str(tmp_path), staged))


class TestIdentity:
    def test_action_identity(self) -> None:
        action = ReviewVerdictGateAction()
        assert action.name == "squadron.review-verdict-gate"
        assert action.events == frozenset({EventType.COMMIT})

    def test_validate_accepts_any_config(self) -> None:
        assert ReviewVerdictGateAction().validate({}) == []


class TestBuiltInBinding:
    def test_gate_is_bound_to_commit_by_default(self) -> None:
        """Registration alone does not run the gate.

        An action is registered by importing its module, but only
        ``DEFAULT_BINDINGS`` makes it fire. The gate was registered and inert
        until it was bound, and nothing failed — so the binding is pinned here.
        """
        from squadron.events.manifest import DEFAULT_BINDINGS

        bound = {binding.action for binding in DEFAULT_BINDINGS if binding.event is EventType.COMMIT}
        assert ReviewVerdictGateAction.name in bound


class TestInvalidVerdicts:
    @pytest.mark.asyncio
    async def test_unknown_value_rejected_with_value_and_allowed_set(self, tmp_path: Path) -> None:
        """The message must name the offending value and the real allowed set."""
        staged = _write(tmp_path, "bad.md", "docType: review\nverdict: BANANA")

        result = await _run(tmp_path, staged)

        assert result.success is False
        assert result.error is not None
        assert "BANANA" in result.error
        # Derived from the enum, never spelled out here — a literal list in the
        # assertion would drift exactly the way a literal list in the gate would.
        for member in Verdict:
            assert member.value in result.error

    @pytest.mark.asyncio
    async def test_resolved_is_rejected(self, tmp_path: Path) -> None:
        """Slice 266's two artifacts read RESOLVED; the gate exists to stop that."""
        staged = _write(tmp_path, "resolved.md", "docType: review\nverdict: RESOLVED")

        result = await _run(tmp_path, staged)

        assert result.success is False
        assert result.error is not None
        assert "RESOLVED" in result.error

    @pytest.mark.asyncio
    async def test_singular_concern_is_rejected(self, tmp_path: Path) -> None:
        """CONCERN (singular) is not CONCERNS — the 305 artifact's corruption."""
        staged = _write(tmp_path, "concern.md", "docType: review\nverdict: CONCERN")

        result = await _run(tmp_path, staged)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_missing_verdict_key_rejected(self, tmp_path: Path) -> None:
        staged = _write(tmp_path, "noverdict.md", "docType: review\nslice: foo")

        result = await _run(tmp_path, staged)

        assert result.success is False
        assert result.error is not None
        assert "noverdict.md" in result.error

    @pytest.mark.asyncio
    async def test_unparseable_frontmatter_rejected(self, tmp_path: Path) -> None:
        """A block that is present but unreadable must not pass: the gate
        cannot determine validity, so it fails closed."""
        staged = _write(tmp_path, "broken.md", "docType: review\n  verdict: [unclosed")

        result = await _run(tmp_path, staged)

        assert result.success is False


class TestValidAndInapplicable:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("member", list(Verdict))
    async def test_each_real_member_passes(self, tmp_path: Path, member: Verdict) -> None:
        staged = _write(tmp_path, "good.md", f"docType: review\nverdict: {member.value}")

        result = await _run(tmp_path, staged)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_non_review_doctype_ignored(self, tmp_path: Path) -> None:
        """Keyed on the document's own declaration, not on a path convention."""
        staged = _write(tmp_path, "design.md", "docType: slice-design\nverdict: BANANA")

        result = await _run(tmp_path, staged)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_file_without_frontmatter_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "plain.md"
        path.write_text("# Just a heading\n", encoding="utf-8")

        result = await _run(tmp_path, "plain.md")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_non_markdown_path_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "code.py"
        path.write_text("verdict = 'BANANA'\n", encoding="utf-8")

        result = await _run(tmp_path, "code.py")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_staged_deletion_is_not_a_violation(self, tmp_path: Path) -> None:
        """Deleting a review is not committing an invalid verdict.

        The repo's hook filters deletions out with --diff-filter=ACMR, but the
        gate is reachable directly with no such filter, so it must handle an
        absent path itself rather than reporting it as unreadable.
        """
        result = await _run(tmp_path, "deleted-review.md")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_present_but_unreadable_still_fails_closed(self, tmp_path: Path) -> None:
        """An absent path is skipped; an unreadable one is not."""
        import os

        if os.geteuid() == 0:
            pytest.skip("root reads regardless of mode bits")
        staged = _write(tmp_path, "locked.md", "docType: review\nverdict: PASS")
        target = tmp_path / staged
        target.chmod(0o000)
        try:
            result = await _run(tmp_path, staged)
        finally:
            target.chmod(0o644)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_no_staged_paths_passes(self, tmp_path: Path) -> None:
        result = await _run(tmp_path)

        assert result.success is True


class TestMultipleFiles:
    @pytest.mark.asyncio
    async def test_result_names_only_the_bad_file(self, tmp_path: Path) -> None:
        good = _write(tmp_path, "good.md", f"docType: review\nverdict: {Verdict.PASS.value}")
        bad = _write(tmp_path, "bad.md", "docType: review\nverdict: BANANA")

        result = await _run(tmp_path, good, bad)

        assert result.success is False
        assert result.error is not None
        assert bad in result.error
        assert good not in result.error
