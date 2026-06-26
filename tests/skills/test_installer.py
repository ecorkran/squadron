from pathlib import Path

import pytest

from squadron.skills.installer import install_pack
from squadron.skills.models import PackEntry, SkillSourceError


def _make_source(tmp_path: Path, files: list[str]) -> Path:
    src = tmp_path / "source"
    src.mkdir()
    for name in files:
        (src / name).write_text(f"# {name}")
    return src


class TestPrefixInstall:
    def test_md_files_copied_to_prefix_dir(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["skill_a.md", "skill_b.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), prefix="mypack")

        result = install_pack("mypack", entry, commands_dir)

        assert result.pack_name == "mypack"
        assert set(result.files_written) == {"skill_a.md", "skill_b.md"}
        assert (commands_dir / "mypack" / "skill_a.md").exists()
        assert (commands_dir / "mypack" / "skill_b.md").exists()

    def test_destination_is_commands_prefix(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["skill.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), prefix="stuff")

        result = install_pack("mypack", entry, commands_dir)

        assert result.destination == commands_dir / "stuff"

    def test_non_md_files_not_copied(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["skill.md"])
        (src / "readme.txt").write_text("not a skill")
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), prefix="mypack")

        result = install_pack("mypack", entry, commands_dir)

        assert "readme.txt" not in result.files_written
        assert not (commands_dir / "mypack" / "readme.txt").exists()


class TestDispatchFileInstall:
    def test_single_file_copied_to_sq_dir(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["myskill.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), dispatch_file="myskill")

        result = install_pack("myskillpack", entry, commands_dir)

        assert result.files_written == ["myskill.md"]
        assert (commands_dir / "sq" / "myskill.md").exists()

    def test_destination_is_sq_subdir(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["myskill.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), dispatch_file="myskill")

        result = install_pack("myskillpack", entry, commands_dir)

        assert result.destination == commands_dir / "sq"

    def test_missing_dispatch_file_raises(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["other.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), dispatch_file="nothere")

        with pytest.raises(SkillSourceError, match="nothere"):
            install_pack("myskillpack", entry, commands_dir)


class TestIdempotent:
    def test_double_install_does_not_raise(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["skill.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), prefix="mypack")

        install_pack("mypack", entry, commands_dir)
        install_pack("mypack", entry, commands_dir)  # should not raise

        assert (commands_dir / "mypack" / "skill.md").exists()


class TestMissingSource:
    def test_missing_source_dir_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such-dir"
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(missing), prefix="mypack")

        with pytest.raises(SkillSourceError):
            install_pack("mypack", entry, commands_dir)
