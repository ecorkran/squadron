"""Tests for install-commands and uninstall-commands CLI commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.install import _get_commands_source

runner = CliRunner()

EXPECTED_FILES = {
    "auth-status.md",
    "list.md",
    "review-slice.md",
    "review-code.md",
    "review-tasks.md",
    "run-slice.md",
    "shutdown.md",
    "spawn.md",
    "task.md",
}


def test_install_copies_files(tmp_path: Path) -> None:
    """Install copies all 9 command files to the target directory."""
    result = runner.invoke(app, ["install-commands", "--target", str(tmp_path)])
    assert result.exit_code == 0

    sq_dir = tmp_path / "sq"
    assert sq_dir.is_dir()
    installed = {f.name for f in sq_dir.iterdir()}
    assert installed == EXPECTED_FILES


def test_install_creates_directories(tmp_path: Path) -> None:
    """Install creates target and subdirectories if they don't exist."""
    deep_target = tmp_path / "a" / "b" / "c"
    result = runner.invoke(app, ["install-commands", "--target", str(deep_target)])
    assert result.exit_code == 0
    assert (deep_target / "sq").is_dir()
    assert len(list((deep_target / "sq").glob("*.md"))) == 9


def test_install_overwrites_existing(tmp_path: Path) -> None:
    """Install overwrites existing files."""
    sq_dir = tmp_path / "sq"
    sq_dir.mkdir(parents=True)
    (sq_dir / "spawn.md").write_text("old content")

    result = runner.invoke(app, ["install-commands", "--target", str(tmp_path)])
    assert result.exit_code == 0

    content = (sq_dir / "spawn.md").read_text()
    assert content != "old content"
    assert "sq spawn" in content


def test_uninstall_removes_sq_directory(tmp_path: Path) -> None:
    """Uninstall removes the sq/ directory and its contents."""
    # First install
    runner.invoke(app, ["install-commands", "--target", str(tmp_path)])
    assert (tmp_path / "sq").is_dir()

    # Then uninstall
    result = runner.invoke(app, ["uninstall-commands", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert not (tmp_path / "sq").exists()


def test_uninstall_preserves_other_files(tmp_path: Path) -> None:
    """Uninstall only removes sq/, not other files in the target."""
    # Install commands
    runner.invoke(app, ["install-commands", "--target", str(tmp_path)])

    # Add a non-sq file
    (tmp_path / "other-command.md").write_text("keep me")

    # Uninstall
    result = runner.invoke(app, ["uninstall-commands", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert not (tmp_path / "sq").exists()
    assert (tmp_path / "other-command.md").read_text() == "keep me"


def test_uninstall_graceful_when_nothing_installed(tmp_path: Path) -> None:
    """Uninstall reports gracefully when nothing is installed."""
    result = runner.invoke(app, ["uninstall-commands", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert "Nothing to remove" in result.output


def test_target_flag_overrides_default(tmp_path: Path) -> None:
    """--target flag directs installation to a custom path."""
    custom = tmp_path / "custom-location"
    result = runner.invoke(app, ["install-commands", "--target", str(custom)])
    assert result.exit_code == 0
    assert (custom / "sq").is_dir()
    assert len(list((custom / "sq").glob("*.md"))) == 9


def test_get_commands_source_returns_valid_dir() -> None:
    """_get_commands_source returns a directory with sq/ subdirectory."""
    source = _get_commands_source()
    assert source.is_dir()
    assert (source / "sq").is_dir()
    assert len(list((source / "sq").glob("*.md"))) == 9


# ---------------------------------------------------------------------------
# T14: Source file verification
# ---------------------------------------------------------------------------

EXPECTED_COMMANDS = {
    "spawn.md": "sq spawn",
    "task.md": "sq task",
    "list.md": "sq list",
    "shutdown.md": "sq shutdown",
    "review-slice.md": "sq review slice",
    "review-tasks.md": "sq review tasks",
    "review-code.md": "sq review code",
    "auth-status.md": "sq auth status",
    "run-slice.md": "cf get",
}


def test_all_command_files_exist_in_source() -> None:
    """All 9 expected command files exist in commands/sq/."""
    source = _get_commands_source()
    sq_dir = source / "sq"
    for filename in EXPECTED_COMMANDS:
        assert (sq_dir / filename).is_file(), f"Missing: {filename}"


def test_command_files_are_nonempty() -> None:
    """Each command file is non-empty."""
    source = _get_commands_source()
    sq_dir = source / "sq"
    for filename in EXPECTED_COMMANDS:
        content = (sq_dir / filename).read_text()
        assert len(content.strip()) > 0, f"Empty: {filename}"


def test_command_files_reference_correct_subcommand() -> None:
    """Each command file references its expected sq subcommand."""
    source = _get_commands_source()
    sq_dir = source / "sq"
    for filename, expected_cmd in EXPECTED_COMMANDS.items():
        content = (sq_dir / filename).read_text()
        assert expected_cmd in content, (
            f"{filename} missing reference to '{expected_cmd}'"
        )
