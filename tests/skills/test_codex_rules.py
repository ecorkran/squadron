"""Codex sandbox rules written by a Codex skills install (issue #127, 928 D9)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.skills.codex_rules import (
    RULES_RELATIVE_PATH,
    SQ_RULE_EXAMPLES,
    codex_home,
    remove_sq_rules,
    render_sq_rules,
    write_sq_rules,
)

runner = CliRunner()


def test_rules_file_is_squadron_owned_not_default_rules() -> None:
    assert RULES_RELATIVE_PATH == Path("rules") / "squadron.rules"


def test_render_names_every_subcommand_and_an_example_for_each() -> None:
    text = render_sq_rules()
    for name, example in SQ_RULE_EXAMPLES.items():
        assert f'"{name}"' in text
        assert f'"{example}"' in text
        assert example.split()[:2] == ["sq", name]
    assert 'decision = "allow"' in text


def test_write_replaces_the_whole_file(tmp_path: Path) -> None:
    path = tmp_path / RULES_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text("stale content from an older squadron\n")

    assert write_sq_rules(tmp_path) == path
    assert path.read_text(encoding="utf-8") == render_sq_rules()


def test_write_never_touches_default_rules(tmp_path: Path) -> None:
    default = tmp_path / "rules" / "default.rules"
    default.parent.mkdir(parents=True)
    default.write_text('prefix_rule(pattern=["git"], decision="allow")\n')

    write_sq_rules(tmp_path)

    assert default.read_text() == 'prefix_rule(pattern=["git"], decision="allow")\n'


def test_remove_deletes_only_our_file(tmp_path: Path) -> None:
    write_sq_rules(tmp_path)
    default = tmp_path / "rules" / "default.rules"
    default.write_text("mine\n")

    assert remove_sq_rules(tmp_path) == tmp_path / RULES_RELATIVE_PATH
    assert not (tmp_path / RULES_RELATIVE_PATH).exists()
    assert default.read_text() == "mine\n"
    assert remove_sq_rules(tmp_path) is None


def test_codex_home_honors_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "custom"))
    assert codex_home() == tmp_path / "custom"


def test_codex_home_defaults_under_home() -> None:
    assert codex_home() == Path.home() / ".codex"


@pytest.mark.skipif(shutil.which("codex") is None, reason="needs the Codex CLI")
def test_codex_accepts_the_rules_and_allows_exactly_the_listed_commands(tmp_path: Path) -> None:
    """Codex parses the file and validates its ``match`` examples at load time."""
    rules = write_sq_rules(tmp_path)

    def decision(*command: str) -> str:
        result = subprocess.run(
            ["codex", "execpolicy", "check", "--rules", str(rules), *command],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    for example in SQ_RULE_EXAMPLES.values():
        assert '"decision":"allow"' in decision(*example.split())
    assert '"matchedRules":[]' in decision("sq", "models", "list")


def _invoke(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def _install_codex(target: Path) -> str:
    return _invoke(
        "install-commands", "--ide", "codex", "--target", str(target),
        "--receipts-dir", str(target / "receipts"),
    )  # fmt: skip


def test_codex_install_writes_rules_when_codex_home_exists(tmp_path: Path) -> None:
    home = codex_home()
    home.mkdir()

    output = _install_codex(tmp_path / "skills")

    assert (home / RULES_RELATIVE_PATH).read_text(encoding="utf-8") == render_sq_rules()
    assert "Wrote Codex sandbox rules" in output


def test_codex_install_skips_rules_without_codex_home(tmp_path: Path) -> None:
    output = _install_codex(tmp_path / "skills")

    assert not codex_home().exists()
    assert "No Codex home" in output


def test_claude_install_never_touches_codex(tmp_path: Path) -> None:
    home = codex_home()
    home.mkdir()

    _invoke(
        "install-commands", "--target", str(tmp_path / "commands"),
        "--receipts-dir", str(tmp_path / "receipts"),
    )  # fmt: skip

    assert not (home / RULES_RELATIVE_PATH).exists()


def test_codex_uninstall_removes_the_rules(tmp_path: Path) -> None:
    home = codex_home()
    home.mkdir()
    _install_codex(tmp_path / "skills")

    output = _invoke(
        "uninstall-commands", "--ide", "codex", "--target", str(tmp_path / "skills"),
        "--receipts-dir", str(tmp_path / "skills" / "receipts"),
    )  # fmt: skip

    assert not (home / RULES_RELATIVE_PATH).exists()
    assert "Removed Codex sandbox rules" in output


def test_local_codex_uninstall_keeps_the_machine_wide_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = codex_home()
    home.mkdir()
    monkeypatch.chdir(tmp_path)
    receipts = str(tmp_path / "receipts")
    _invoke("install-commands", "--ide", "codex", "--local", "--receipts-dir", receipts)

    _invoke("uninstall-commands", "--ide", "codex", "--local", "--receipts-dir", receipts)

    assert (home / RULES_RELATIVE_PATH).exists()
