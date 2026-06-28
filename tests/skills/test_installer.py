from pathlib import Path

import pytest

import squadron.skills.installer as installer_mod
from squadron.skills.installer import install_pack
from squadron.skills.models import PackEntry, SkillSourceError, SurfaceType
from squadron.skills.receipts import read_receipt


@pytest.fixture(autouse=True)
def _isolate_receipts(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Redirect the default receipts dir into tmp so installs never touch $HOME."""
    receipts_dir = tmp_path / "_receipts"
    monkeypatch.setattr(installer_mod, "DEFAULT_RECEIPTS_DIR", receipts_dir)
    return receipts_dir


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


class TestBundledAnalysisPack:
    def test_install_analysis_pack_creates_tech_debt_audit(self, tmp_path: Path) -> None:
        commands_dir = tmp_path
        entry = PackEntry(source="bundled", prefix="analysis")

        result = install_pack("analysis", entry, commands_dir)

        assert (commands_dir / "analysis" / "tech-debt-audit.md").exists()
        assert "tech-debt-audit.md" in result.files_written

    def test_install_analysis_pack_result_fields(self, tmp_path: Path) -> None:
        commands_dir = tmp_path
        entry = PackEntry(source="bundled", prefix="analysis")

        result = install_pack("analysis", entry, commands_dir)

        assert result.pack_name == "analysis"
        assert result.destination == commands_dir / "analysis"


class TestReceiptWriting:
    def test_prefix_install_writes_receipt(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["skill_a.md", "skill_b.md"])
        commands_dir = tmp_path / "commands"
        receipts_dir = tmp_path / "receipts"
        entry = PackEntry(source=str(src), prefix="mypack")

        install_pack("mypack", entry, commands_dir, receipts_dir=receipts_dir)

        receipt = read_receipt("mypack", receipts_dir)
        assert receipt is not None
        assert receipt.pack_name == "mypack"
        assert receipt.surface == SurfaceType.PREFIX
        assert receipt.destination == commands_dir / "mypack"
        assert set(receipt.files_written) == {"skill_a.md", "skill_b.md"}

    def test_dispatch_install_writes_dispatch_surface(self, tmp_path: Path) -> None:
        src = _make_source(tmp_path, ["myskill.md"])
        commands_dir = tmp_path / "commands"
        receipts_dir = tmp_path / "receipts"
        entry = PackEntry(source=str(src), dispatch_file="myskill")

        install_pack("myskillpack", entry, commands_dir, receipts_dir=receipts_dir)

        receipt = read_receipt("myskillpack", receipts_dir)
        assert receipt is not None
        assert receipt.surface == SurfaceType.DISPATCH_FILE
        assert receipt.files_written == ["myskill.md"]

    def test_receipt_write_failure_does_not_fail_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = _make_source(tmp_path, ["skill.md"])
        commands_dir = tmp_path / "commands"
        receipts_dir = tmp_path / "receipts"
        entry = PackEntry(source=str(src), prefix="mypack")

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(installer_mod, "write_receipt", _boom)

        # Install must still succeed and place files despite the receipt failure.
        result = install_pack("mypack", entry, commands_dir, receipts_dir=receipts_dir)

        assert (commands_dir / "mypack" / "skill.md").exists()
        assert result.files_written == ["skill.md"]
        assert read_receipt("mypack", receipts_dir) is None

    def test_install_without_receipts_dir_uses_default(self, tmp_path: Path) -> None:
        # The autouse fixture redirects DEFAULT_RECEIPTS_DIR into tmp.
        src = _make_source(tmp_path, ["skill.md"])
        commands_dir = tmp_path / "commands"
        entry = PackEntry(source=str(src), prefix="mypack")

        install_pack("mypack", entry, commands_dir)

        assert read_receipt("mypack", installer_mod.DEFAULT_RECEIPTS_DIR) is not None
