"""Tests for install receipt write/read round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.skills.models import InstallReceipt, SurfaceType
from squadron.skills.receipts import read_receipt, write_receipt


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
