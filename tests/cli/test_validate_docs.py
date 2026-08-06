"""Integration tests for `sq validate docs` via CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()

_VALID_DOC = (
    "---\n"
    "docType: notes\n"
    "project: squadron\n"
    "dateCreated: 20260803\n"
    "dateUpdated: 20260803\n"
    "status: not_started\n"
    "---\n\nbody\n"
)

_INVALID_DOC = (
    "---\n"
    "docType: notes\n"
    "project: squadron\n"
    "dateCreated: 20260803\n"
    "dateUpdated: 20260803\n"
    "status: draft\n"
    "---\n\nbody\n"
)


def test_clean_run_exits_zero(tmp_path: Path) -> None:
    doc = tmp_path / "good.md"
    doc.write_text(_VALID_DOC, encoding="utf-8")

    result = runner.invoke(app, ["validate", "docs", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "0 violations" in result.output or "0 violations" in result.stderr


def test_violating_document_exits_one(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(_INVALID_DOC, encoding="utf-8")

    result = runner.invoke(app, ["validate", "docs", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "FM005" in result.output


def test_nonexistent_root_exits_two(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    result = runner.invoke(app, ["validate", "docs", "--root", str(missing)])

    assert result.exit_code == 2


def test_nonexistent_named_path_exits_two(tmp_path: Path) -> None:
    missing = tmp_path / "ghost.md"

    result = runner.invoke(app, ["validate", "docs", str(missing), "--root", str(tmp_path)])

    assert result.exit_code == 2


def test_non_utf8_file_exits_one_with_fm008(tmp_path: Path) -> None:
    doc = tmp_path / "bad-encoding.md"
    doc.write_bytes(b"---\ndocType: notes\n---\n\n\xff\xfe garbage\n")

    result = runner.invoke(app, ["validate", "docs", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "FM008" in result.output
    assert "Traceback" not in result.output


def test_summary_line_present_on_clean_run(tmp_path: Path) -> None:
    doc = tmp_path / "good.md"
    doc.write_text(_VALID_DOC, encoding="utf-8")

    result = runner.invoke(app, ["validate", "docs", "--root", str(tmp_path)])

    assert "documents checked" in result.output


def test_quiet_suppresses_summary_but_keeps_violations(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(_INVALID_DOC, encoding="utf-8")

    result = runner.invoke(app, ["validate", "docs", "--root", str(tmp_path), "--quiet"])

    assert "documents checked" not in result.output
    assert "FM005" in result.output


def test_accepted_values_line_present_for_fm005(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(_INVALID_DOC, encoding="utf-8")

    result = runner.invoke(app, ["validate", "docs", "--root", str(tmp_path)])

    assert "accepted:" in result.output
    assert "not_started" in result.output


def test_help_renders() -> None:
    result = runner.invoke(app, ["validate", "docs", "--help"])

    assert result.exit_code == 0
    assert "docs_root" in result.output or "root" in result.output.lower()
