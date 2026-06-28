from pathlib import Path

import pytest
from pydantic import ValidationError

from squadron.skills.models import (
    InstallReceipt,
    InstallResult,
    PackEntry,
    SkillSourceError,
    SurfaceType,
)


class TestPackEntry:
    def test_prefix_only_passes(self) -> None:
        entry = PackEntry(source="bundled", prefix="mypack")
        assert entry.prefix == "mypack"
        assert entry.dispatch_file is None

    def test_dispatch_file_only_passes(self) -> None:
        entry = PackEntry(source="bundled", dispatch_file="myskill")
        assert entry.dispatch_file == "myskill"
        assert entry.prefix is None

    def test_both_raises(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            PackEntry(source="bundled", prefix="a", dispatch_file="b")

    def test_neither_raises(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            PackEntry(source="bundled")

    def test_source_stored(self) -> None:
        entry = PackEntry(source="github:org/repo", prefix="pack")
        assert entry.source == "github:org/repo"


class TestInstallResult:
    def test_defaults(self) -> None:
        result = InstallResult(pack_name="test")
        assert result.files_written == []

    def test_files_written(self) -> None:
        from pathlib import Path

        result = InstallResult(
            pack_name="test", files_written=["a.md", "b.md"], destination=Path("/tmp")
        )
        assert len(result.files_written) == 2


class TestInstallReceipt:
    def test_prefix_surface_construction(self) -> None:
        receipt = InstallReceipt(
            pack_name="analysis",
            surface=SurfaceType.PREFIX,
            destination=Path("/Users/you/.claude/commands/analysis"),
            files_written=["tech-debt-audit.md"],
        )
        assert receipt.surface == SurfaceType.PREFIX
        assert receipt.files_written == ["tech-debt-audit.md"]

    def test_dispatch_file_surface_construction(self) -> None:
        receipt = InstallReceipt(
            pack_name="core",
            surface=SurfaceType.DISPATCH_FILE,
            destination=Path("/Users/you/.claude/commands/sq"),
            files_written=["run.md"],
        )
        assert receipt.surface == SurfaceType.DISPATCH_FILE

    def test_destination_path_round_trips(self) -> None:
        original = InstallReceipt(
            pack_name="analysis",
            surface=SurfaceType.PREFIX,
            destination=Path("/Users/you/.claude/commands/analysis"),
            files_written=["a.md", "b.md"],
        )
        restored = InstallReceipt.model_validate(original.model_dump())
        assert restored == original
        assert isinstance(restored.destination, Path)

    def test_surface_accepts_string_value(self) -> None:
        receipt = InstallReceipt.model_validate(
            {
                "pack_name": "analysis",
                "surface": "prefix",
                "destination": "/tmp/analysis",
                "files_written": ["x.md"],
            }
        )
        assert receipt.surface is SurfaceType.PREFIX


class TestSkillSourceError:
    def test_is_exception(self) -> None:
        err = SkillSourceError("something went wrong")
        assert isinstance(err, Exception)

    def test_catchable_as_exception(self) -> None:
        with pytest.raises(Exception):
            raise SkillSourceError("test")
