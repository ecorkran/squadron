"""Integration tests for sq skills install and sq skills list commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()

_USER_MANIFEST_ATTR = "squadron.skills.manifest.user_manifest_path"
_EFFECTIVE_MANIFEST_ATTR = "squadron.skills.manifest.load_effective"


def _write_manifest(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestListNoManifest:
    def test_shows_shipped_default_when_no_user_skills_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No user manifest — shipped default provides the analysis pack.
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: tmp_path / "no-such.toml")
        result = runner.invoke(app, ["skills", "list", "--commands-dir", str(tmp_path / "commands")])
        assert result.exit_code == 0, result.output
        assert "analysis" in result.output

    def test_exits_1_when_all_sources_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Patch out both user manifest and shipped default to assert the None path.
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: tmp_path / "no-such.toml")
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
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: manifest_file)

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
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: manifest_file)

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
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: manifest_file)

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
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: manifest_file)

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
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: manifest_file)

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
        monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: manifest_file)

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


# ---------------------------------------------------------------------------
# Slice 928: --ide and --local
# ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A disposable HOME and cwd, with only the shipped manifest (bundled analysis pack)."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project)
    monkeypatch.setattr(_USER_MANIFEST_ATTR, lambda: home_dir / "no-such.toml")
    return home_dir


def _receipts(home_dir: Path) -> set[str]:
    receipts_dir = home_dir / ".config" / "squadron" / "receipts"
    return {p.name for p in receipts_dir.glob("*.toml")} if receipts_dir.is_dir() else set()


def _skills(root: Path) -> set[str]:
    return {p.name for p in root.iterdir()} if root.is_dir() else set()


ANALYSIS_SKILLS = {"analysis-understand", "analysis-tech-debt-audit"}


def test_codex_install_writes_agents_skills_and_receipt(home: Path) -> None:
    result = runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex"])

    assert result.exit_code == 0, result.output
    assert _skills(home / ".agents" / "skills") == ANALYSIS_SKILLS
    assert _receipts(home) == {"analysis-agents.toml"}


def test_codex_local_install_writes_under_the_project(home: Path) -> None:
    result = runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex", "--local"])

    assert result.exit_code == 0, result.output
    assert _skills(Path.cwd() / ".agents" / "skills") == ANALYSIS_SKILLS
    assert not (home / ".agents").exists()
    assert _receipts(home) == {"analysis-agents-local.toml"}


def test_claude_install_is_unchanged_beside_a_codex_install(home: Path) -> None:
    runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex"])
    result = runner.invoke(app, ["skills", "install", "analysis"])

    assert result.exit_code == 0, result.output
    assert _skills(home / ".claude" / "commands" / "analysis") == {
        "tech-debt-audit.md",
        "understand.md",
    }
    assert _receipts(home) == {"analysis.toml", "analysis-agents.toml"}


def test_local_with_commands_dir_is_reported_not_silent(home: Path, tmp_path: Path) -> None:
    target = tmp_path / "explicit"
    result = runner.invoke(
        app,
        ["skills", "install", "analysis", "--ide", "codex", "--local", "--commands-dir", str(target)],
    )

    assert result.exit_code == 0, result.output
    assert "--local ignored" in result.output
    assert _skills(target) == ANALYSIS_SKILLS
    assert _receipts(home) == {"analysis-agents.toml"}


def test_unknown_ide_is_rejected(home: Path) -> None:
    result = runner.invoke(app, ["skills", "install", "analysis", "--ide", "copilot"])
    assert result.exit_code == 2


def test_list_reports_status_per_target(home: Path) -> None:
    runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex"])

    codex = runner.invoke(app, ["skills", "list", "--ide", "codex"])
    claude = runner.invoke(app, ["skills", "list"])

    assert codex.exit_code == 0, codex.output
    assert "Installed" in codex.output and "Not installed" not in codex.output
    assert "Not installed" in claude.output


def test_codex_uninstall_removes_only_receipt_files(home: Path) -> None:
    skills_root = home / ".agents" / "skills"
    runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex"])
    (skills_root / "mine.txt").write_text("keep")

    result = runner.invoke(app, ["skills", "uninstall", "analysis", "--ide", "codex"])

    assert result.exit_code == 0, result.output
    assert _skills(skills_root) == {"mine.txt"}
    assert _receipts(home) == set()


def test_codex_uninstall_never_removes_the_shared_root(home: Path) -> None:
    runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex"])
    runner.invoke(app, ["skills", "uninstall", "analysis", "--ide", "codex"])
    assert (home / ".agents" / "skills").is_dir()


def test_uninstall_rejects_a_mismatched_commands_dir(home: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["skills", "install", "analysis", "--ide", "codex"])

    result = runner.invoke(
        app,
        [
            "skills",
            "uninstall",
            "analysis",
            "--ide",
            "codex",
            "--commands-dir",
            str(tmp_path / "elsewhere"),
        ],
    )

    assert result.exit_code == 1
    assert "Nothing was removed" in result.output
    assert _skills(home / ".agents" / "skills") == ANALYSIS_SKILLS


def test_pre_928_claude_receipt_still_uninstalls(home: Path) -> None:
    """A receipt written before 928 is named for the pack alone — exactly D5's Claude name."""
    import tomli_w

    dest = home / ".claude" / "commands" / "analysis"
    dest.mkdir(parents=True)
    (dest / "understand.md").write_text("x")
    receipts_dir = home / ".config" / "squadron" / "receipts"
    receipts_dir.mkdir(parents=True)
    with open(receipts_dir / "analysis.toml", "wb") as fh:
        tomli_w.dump(
            {
                "pack_name": "analysis",
                "surface": "prefix",
                "destination": str(dest),
                "files_written": ["understand.md"],
            },
            fh,
        )

    result = runner.invoke(app, ["skills", "uninstall", "analysis"])

    assert result.exit_code == 0, result.output
    assert not dest.exists()
    assert _receipts(home) == set()
