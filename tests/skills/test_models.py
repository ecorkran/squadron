import pytest
from pydantic import ValidationError

from squadron.skills.models import InstallResult, PackEntry, SkillSourceError


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


class TestSkillSourceError:
    def test_is_exception(self) -> None:
        err = SkillSourceError("something went wrong")
        assert isinstance(err, Exception)

    def test_catchable_as_exception(self) -> None:
        with pytest.raises(Exception):
            raise SkillSourceError("test")
