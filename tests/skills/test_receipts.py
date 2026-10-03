"""Tests for install receipt write/read round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.skills.models import InstallReceipt, SurfaceType
from squadron.skills.receipts import read_receipt, remove_receipt_files, write_receipt


def _sample_receipt(destination: Path) -> InstallReceipt:
    return InstallReceipt(
        pack_name="analysis",
        surface=SurfaceType.PREFIX,
        destination=destination,
        files_written=["tech-debt-audit.md", "understand-anything.md"],
    )


def test_write_read_round_trip(tmp_path: Path) -> None:
    receipts_dir = tmp_path / "receipts"
    dest = tmp_path / "commands" / "analysis"
    receipt = _sample_receipt(dest)

    write_receipt(receipt, receipts_dir)
    restored = read_receipt("analysis", receipts_dir)

    assert restored is not None
    assert restored.pack_name == receipt.pack_name
    assert restored.surface == SurfaceType.PREFIX
    assert restored.destination == dest
    assert restored.files_written == receipt.files_written


def test_read_returns_none_when_absent(tmp_path: Path) -> None:
    assert read_receipt("nonexistent", tmp_path) is None


def test_write_creates_receipts_dir(tmp_path: Path) -> None:
    receipts_dir = tmp_path / "deep" / "nested" / "receipts"
    assert not receipts_dir.exists()

    write_receipt(_sample_receipt(tmp_path / "dest"), receipts_dir)

    assert receipts_dir.is_dir()
    assert (receipts_dir / "analysis.toml").is_file()


def test_read_raises_on_malformed_toml(tmp_path: Path) -> None:
    (tmp_path / "broken.toml").write_text("this is = = not valid toml ][")

    with pytest.raises(ValueError, match="Malformed install receipt"):
        read_receipt("broken", tmp_path)


def test_read_raises_on_schema_violation(tmp_path: Path) -> None:
    # Valid TOML, but missing required fields → ValidationError (a ValueError subclass)
    (tmp_path / "partial.toml").write_text('pack_name = "x"\n')

    with pytest.raises(ValueError, match="Malformed install receipt"):
        read_receipt("partial", tmp_path)


def test_dispatch_surface_round_trip(tmp_path: Path) -> None:
    receipts_dir = tmp_path / "receipts"
    receipt = InstallReceipt(
        pack_name="core",
        surface=SurfaceType.DISPATCH_FILE,
        destination=tmp_path / "sq",
        files_written=["run.md"],
    )
    write_receipt(receipt, receipts_dir)

    restored = read_receipt("core", receipts_dir)
    assert restored is not None
    assert restored.surface == SurfaceType.DISPATCH_FILE


def _receipt_for(destination: Path, files: list[str]) -> InstallReceipt:
    return InstallReceipt(pack_name="p", destination=destination, files_written=files)


def _write_files(root: Path, files: list[str]) -> None:
    for relative in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")


def test_remove_receipt_files_prunes_nested_dirs_deepest_first(tmp_path: Path) -> None:
    dest = tmp_path / "skills"
    files = ["demo-a/SKILL.md", "demo-a/agents/openai.yaml", "demo-b/SKILL.md"]
    _write_files(dest, files)

    removed = remove_receipt_files(_receipt_for(dest, files))

    assert removed == 3
    assert not (dest / "demo-a").exists()
    assert not (dest / "demo-b").exists()


def test_remove_receipt_files_never_removes_destination(tmp_path: Path) -> None:
    dest = tmp_path / "skills"
    _write_files(dest, ["a.md"])

    remove_receipt_files(_receipt_for(dest, ["a.md"]))

    assert dest.is_dir()
    assert not any(dest.iterdir())


def test_remove_receipt_files_keeps_dir_with_unrelated_file(tmp_path: Path) -> None:
    dest = tmp_path / "skills"
    _write_files(dest, ["demo-a/SKILL.md", "demo-a/mine.txt"])

    removed = remove_receipt_files(_receipt_for(dest, ["demo-a/SKILL.md"]))

    assert removed == 1
    assert (dest / "demo-a" / "mine.txt").exists()


def test_remove_receipt_files_skips_entries_outside_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "skills"
    dest.mkdir()
    outside = tmp_path / "victim.md"
    outside.write_text("keep")

    removed = remove_receipt_files(_receipt_for(dest, ["../victim.md"]))

    assert removed == 0
    assert outside.exists()
    assert "Skipping receipt entry outside the install destination" in capsys.readouterr().out


def test_remove_receipt_files_tolerates_already_missing_file(tmp_path: Path) -> None:
    dest = tmp_path / "skills"
    dest.mkdir()
    assert remove_receipt_files(_receipt_for(dest, ["gone.md"])) == 0
