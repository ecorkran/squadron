"""Codex sandbox rules written by a Codex skills install (issue #127)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.skills.codex_rules import (
    NETWORK_COMMAND_PREFIXES,
    RULES_RELATIVE_PATH,
    codex_home,
    ensure_sq_rules,
)

runner = CliRunner()

_EXPECTED_LINES = [
    'prefix_rule(pattern=["sq", "review"], decision="allow")',
    'prefix_rule(pattern=["sq", "run"], decision="allow")',
    'prefix_rule(pattern=["sq", "pr"], decision="allow")',
]


def _rules(home: Path) -> str:
    return (home / RULES_RELATIVE_PATH).read_text(encoding="utf-8")


def test_creates_rules_file_with_every_network_command(tmp_path: Path) -> None:
    added = ensure_sq_rules(tmp_path)
    assert added == _EXPECTED_LINES
    assert _rules(tmp_path) == "\n".join(_EXPECTED_LINES) + "\n"
    assert len(NETWORK_COMMAND_PREFIXES) == len(_EXPECTED_LINES)


def test_second_run_adds_nothing(tmp_path: Path) -> None:
    ensure_sq_rules(tmp_path)
    assert ensure_sq_rules(tmp_path) == []
    assert _rules(tmp_path).count("prefix_rule") == len(_EXPECTED_LINES)


def test_preserves_existing_rules_and_appends_after_them(tmp_path: Path) -> None:
    path = tmp_path / RULES_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text('prefix_rule(pattern=["sed"], decision="allow")', encoding="utf-8")

    ensure_sq_rules(tmp_path)

    lines = _rules(tmp_path).splitlines()
    assert lines[0] == 'prefix_rule(pattern=["sed"], decision="allow")'
    assert lines[1:] == _EXPECTED_LINES


def test_recognizes_the_hand_pasted_multiline_form(tmp_path: Path) -> None:
    """The README's old instructions had users paste this layout."""
    path = tmp_path / RULES_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text(
        'prefix_rule(\n    pattern = ["sq", "review"],\n    decision = "allow",\n)\n',
        encoding="utf-8",
    )

    added = ensure_sq_rules(tmp_path)

    assert added == _EXPECTED_LINES[1:]


def test_a_bare_sq_rule_covers_every_command(tmp_path: Path) -> None:
    path = tmp_path / RULES_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text('prefix_rule(pattern=["sq"], decision="allow")\n', encoding="utf-8")

    assert ensure_sq_rules(tmp_path) == []


def test_codex_home_honors_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "custom"))
    assert codex_home() == tmp_path / "custom"


def test_codex_home_defaults_under_home() -> None:
    assert codex_home() == Path.home() / ".codex"


def _install_codex(target: Path) -> str:
    result = runner.invoke(
        app,
        [
            "install-commands",
            "--ide",
            "codex",
            "--target",
            str(target),
            "--receipts-dir",
            str(target / "receipts"),
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_codex_install_writes_rules_when_codex_home_exists(tmp_path: Path) -> None:
    home = codex_home()
    home.mkdir()

    output = _install_codex(tmp_path / "skills")

    assert _rules(home).splitlines() == _EXPECTED_LINES
    assert "Added 3 Codex sandbox rule(s)" in output


def test_codex_install_skips_rules_without_codex_home(tmp_path: Path) -> None:
    output = _install_codex(tmp_path / "skills")

    assert not codex_home().exists()
    assert "No Codex home" in output


def test_claude_install_never_touches_codex(tmp_path: Path) -> None:
    home = codex_home()
    home.mkdir()

    result = runner.invoke(
        app,
        [
            "install-commands",
            "--target",
            str(tmp_path / "commands"),
            "--receipts-dir",
            str(tmp_path / "receipts"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (home / RULES_RELATIVE_PATH).exists()
