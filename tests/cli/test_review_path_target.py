"""`sq review slice|tasks <path>` saves when the file name carries the slice (issue #142).

A path named by the file-naming convention (``{index}-slice.{name}.md``,
``{index}-tasks.{name}.md``) is the slice's own document when Context Forge lists it
under that index; the review then saves exactly as ``sq review slice {index}`` would.
Any other name, or a name Context Forge does not list for that index, keeps today's
refusal: the slice is never guessed.

A failed write exits 1, so ``save_review_result`` raising ``OSError`` proves a save was
attempted without writing anything.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import SliceInfo


@pytest.fixture
def mock_run_review():
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="slice",
        input_files={"cwd": "."},
    )
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock:
        yield mock


@pytest.fixture
def slice_docs(tmp_path: Path) -> dict[str, Path]:
    docs = {
        "design": tmp_path / "916-slice.probe.md",
        "tasks": tmp_path / "916-tasks.probe.md",
        "arch": tmp_path / "100-arch.probe.md",
        "stray": tmp_path / "916-slice.other-name.md",
        "plain": tmp_path / "notes.md",
    }
    for path in docs.values():
        path.write_text("# doc\n")
    return docs


def _slice_info(docs: dict[str, Path]) -> SliceInfo:
    return SliceInfo(
        index=916,
        name="Probe",
        slice_name="probe",
        design_file=str(docs["design"]),
        task_files=[docs["tasks"].name],
        arch_file=str(docs["arch"]),
        project="squadron",
    )


def _invoke(argv: list[str], info: SliceInfo) -> tuple[int, MagicMock, MagicMock]:
    with (
        patch("squadron.cli.commands.review.ContextForgeClient"),
        patch("squadron.cli.commands.review.resolve_slice_info", return_value=info) as resolve,
        patch(
            "squadron.cli.commands.review.save_review_result",
            side_effect=OSError("read-only filesystem"),
        ) as save,
    ):
        result = CliRunner().invoke(app, argv)
    return result.exit_code, resolve, save


@pytest.mark.parametrize("document", ["design", "tasks"])
def test_conventional_path_saves_under_its_slice(
    document: str, slice_docs: dict[str, Path], mock_run_review: AsyncMock
) -> None:
    subcommand = "slice" if document == "design" else "tasks"
    against = slice_docs["arch" if document == "design" else "design"]
    argv = ["review", subcommand, str(slice_docs[document]), "--against", str(against)]

    exit_code, resolve, save = _invoke(argv, _slice_info(slice_docs))

    assert mock_run_review.called
    assert resolve.call_args.args[1] == 916
    assert save.called, "a conventional path must save as the slice number would"
    assert exit_code == 1  # the patched write failed, which proves it was attempted


def test_name_context_forge_does_not_list_is_not_saved(
    slice_docs: dict[str, Path], mock_run_review: AsyncMock
) -> None:
    argv = ["review", "slice", str(slice_docs["stray"]), "--against", str(slice_docs["arch"])]

    exit_code, _resolve, save = _invoke(argv, _slice_info(slice_docs))

    assert mock_run_review.called
    assert not save.called
    assert exit_code == 0


def test_unconventional_name_is_not_resolved_or_saved(
    slice_docs: dict[str, Path], mock_run_review: AsyncMock
) -> None:
    argv = ["review", "slice", str(slice_docs["plain"]), "--against", str(slice_docs["arch"])]

    exit_code, resolve, save = _invoke(argv, _slice_info(slice_docs))

    assert not resolve.called
    assert not save.called
    assert exit_code == 0
