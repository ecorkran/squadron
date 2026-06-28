"""Integration tests for sq skills install and sq skills list commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()

_USER_MANIFEST_ATTR = "squadron.skills.manifest.USER_MANIFEST"
_EFFECTIVE_MANIFEST_ATTR = "squadron.skills.manifest.load_effective"


def _write_manifest(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestListNoManifest:
    def test_shows_shipped_default_when_no_user_skills_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No user manifest — shipped default provides the analysis pack.
        monkeypatch.setattr(_USER_MANIFEST_ATTR, tmp_path / "no-such.toml")
        result = runner.invoke(app, ["skills", "list", "--commands-dir", str(tmp_path / "commands")])
        assert result.exit_code == 0, result.output
        assert "analysis" in result.output

    def test_exits_1_when_all_sources_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Patch out both user manifest and shipped default to assert the None path.
        monkeypatch.setattr(_USER_MANIFEST_ATTR, tmp_path / "no-such.toml")
        monkeypatch.setattr("squadron.skills.manifest._load_shipped_default", lambda: None)
        result = runner.invoke(app, ["skills", "list", "--commands-dir", str(tmp_path / "commands")])
        assert result.exit_code == 1
        assert "No skills.toml found" in result.output


class TestInstallNotFound:
    def test_exits_1_when_pack_not_in_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_file = tmp_path / "skills.toml"
        _write_manifest(manifest_file, '[packs.existing]\nsource = "bundled"\nprefix = "existing"\n')
        monkeypatch.setattr(_USER_MANIFEST_ATTR, manifest_file)

        result = runner.invoke(
            app, ["skills", "install", "nonexistent", "--commands-dir", str(tmp_path / "commands")]
        )
        assert result.exit_code == 1
        assert "nonexistent" in result.output
        assert "not found" in result.output


class TestInstallLocalPack:
    def test_exits_0_and_shows_file_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Build a real source directory with .md files
        src = tmp_path / "pack-src"
        src.mkdir()
        (src / "skill_one.md").write_text("# skill one")
        (src / "skill_two.md").write_text("# skill two")

        manifest_file = tmp_path / "skills.toml"
        _write_manifest(
            manifest_file,
            f'[packs.testpack]\nsource = "{src}"\nprefix = "testpack"\n',
        )
        monkeypatch.setattr(_USER_MANIFEST_ATTR, manifest_file)

        commands_dir = tmp_path / "commands"
        result = runner.invoke(
            app,
            [
                "skills",
                "install",
                "testpack",
                "--commands-dir",
                str(commands_dir),
                "--receipts-dir",
                str(tmp_path / "receipts"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "2" in result.output  # 2 files written
        assert (commands_dir / "testpack" / "skill_one.md").exists()


class TestUninstall:
    def _manifest_with_local_pack(self, tmp_path: Path) -> Path:
        src = tmp_path / "pack-src"
        src.mkdir()
        (src / "tech-debt-audit.md").write_text("# audit")
        manifest_file = tmp_path / "skills.toml"
        _write_manifest(
            manifest_file,
            f'[packs.analysis]\nsource = "{src}"\nprefix = "analysis"\n',
        )
        return manifest_file

    def test_install_then_uninstall_round_trip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_file = self._manifest_with_local_pack(tmp_path)
        monkeypatch.setattr(_USER_MANIFEST_ATTR, manifest_file)

        commands_dir = tmp_path / "commands"
        receipts_dir = tmp_path / "receipts"
        common = [
            "--commands-dir",
            str(commands_dir),
            "--receipts-dir",
            str(receipts_dir),
        ]

        install = runner.invoke(app, ["skills", "install", "analysis", *common])
        assert install.exit_code == 0, install.output
        assert (commands_dir / "analysis" / "tech-debt-audit.md").exists()
        assert (receipts_dir / "analysis.toml").exists()

        uninstall = runner.invoke(app, ["skills", "uninstall", "analysis", *common])
        assert uninstall.exit_code == 0, uninstall.output
        assert not (commands_dir / "analysis" / "tech-debt-audit.md").exists()
        assert not (receipts_dir / "analysis.toml").exists()

    def test_unrelated_file_not_removed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest_file = self._manifest_with_local_pack(tmp_path)
        monkeypatch.setattr(_USER_MANIFEST_ATTR, manifest_file)

        commands_dir = tmp_path / "commands"
        receipts_dir = tmp_path / "receipts"
        common = [
            "--commands-dir",
            str(commands_dir),
            "--receipts-dir",
            str(receipts_dir),
        ]

        runner.invoke(app, ["skills", "install", "analysis", *common])
        custom = commands_dir / "analysis" / "my-custom-skill.md"
        custom.write_text("keep me")

        result = runner.invoke(app, ["skills", "uninstall", "analysis", *common])
        assert result.exit_code == 0, result.output
        assert custom.read_text() == "keep me"
        # Prefix dir is preserved because it still holds the unrelated file.
        assert (commands_dir / "analysis").is_dir()
        assert not (commands_dir / "analysis" / "tech-debt-audit.md").exists()

    def test_uninstall_when_not_installed_exits_1(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "skills",
                "uninstall",
                "analysis",
                "--commands-dir",
                str(tmp_path / "commands"),
                "--receipts-dir",
                str(tmp_path / "receipts"),
            ],
        )
        assert result.exit_code == 1
        assert "not installed" in result.output

    def test_uninstall_idempotent_when_file_already_gone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_file = self._manifest_with_local_pack(tmp_path)
        monkeypatch.setattr(_USER_MANIFEST_ATTR, manifest_file)

        commands_dir = tmp_path / "commands"
        receipts_dir = tmp_path / "receipts"
        common = [
            "--commands-dir",
            str(commands_dir),
            "--receipts-dir",
            str(receipts_dir),
        ]

        runner.invoke(app, ["skills", "install", "analysis", *common])
        # Remove the installed file out from under uninstall.
        (commands_dir / "analysis" / "tech-debt-audit.md").unlink()

        result = runner.invoke(app, ["skills", "uninstall", "analysis", *common])
        assert result.exit_code == 0, result.output
        assert "0 file(s) removed" in result.output
        assert not (receipts_dir / "analysis.toml").exists()


class TestListWithStatus:
    def test_shows_installed_and_not_installed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Source dir for packs
        src = tmp_path / "pack-src"
        src.mkdir()
        (src / "skill.md").write_text("# skill")

        manifest_file = tmp_path / "skills.toml"
        _write_manifest(
            manifest_file,
            f'[packs.alpha]\nsource = "{src}"\nprefix = "alpha"\n'
            f'[packs.beta]\nsource = "{src}"\nprefix = "beta"\n',
        )
        monkeypatch.setattr(_USER_MANIFEST_ATTR, manifest_file)

        commands_dir = tmp_path / "commands"
        # Only install alpha
        alpha_dest = commands_dir / "alpha"
        alpha_dest.mkdir(parents=True)
        (alpha_dest / "skill.md").write_text("# skill")

        result = runner.invoke(app, ["skills", "list", "--commands-dir", str(commands_dir)])
        assert result.exit_code == 0, result.output
        assert "alpha" in result.output
        assert "beta" in result.output
        # Rich strips markup in test runner; check plain text presence
        assert "Installed" in result.output
        assert "Not installed" in result.output
