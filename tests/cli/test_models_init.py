"""The ``sq models init`` starter file (slice 940 D2)."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.models_init import build_starter_text, leading_comment_block
from squadron.data import data_dir
from squadron.models.aliases import ModelAlias

_BUILTIN = data_dir() / "models.toml"


def _starter() -> str:
    return build_starter_text(_BUILTIN.read_text(encoding="utf-8"), source=_BUILTIN)


def test_starter_parses_as_toml_and_defines_no_aliases() -> None:
    assert tomllib.loads(_starter()) == {}


def test_every_line_is_a_comment_or_blank() -> None:
    assert all(not line.strip() or line.startswith("#") for line in _starter().splitlines())


def test_reference_block_names_every_field_the_alias_loader_accepts() -> None:
    reference = leading_comment_block(_BUILTIN.read_text(encoding="utf-8"))

    assert reference
    missing = [field for field in ModelAlias.__annotations__ if field not in reference]
    assert missing == [], f"the built-in header no longer documents: {missing}"
    assert reference in _starter()


@pytest.mark.parametrize("text", ["\n# late comment\n", "[aliases.x]\n# not a header\n", ""])
def test_text_without_a_leading_comment_block_is_an_error_naming_the_file(text: str) -> None:
    with pytest.raises(ValueError, match=str(Path("some/models.toml"))):
        build_starter_text(text, source=Path("some/models.toml"))


# --- the command ---


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path / ".config" / "squadron" / "models.toml"


def _init(*args: str) -> Result:
    return CliRunner().invoke(app, ["models", "init", *args])


def test_init_writes_the_starter_at_the_user_path(home: Path) -> None:
    result = _init()

    assert result.exit_code == 0, result.output
    assert result.stdout == f"{home}\n"
    assert tomllib.loads(home.read_text(encoding="utf-8")) == {}


def test_second_run_needs_force(home: Path) -> None:
    _init()
    home.write_text("# mine\n", encoding="utf-8")

    refused = _init()
    forced = _init("--force")

    assert refused.exit_code == 1
    assert str(home) in refused.stderr.replace("\n", "")
    assert forced.exit_code == 0
    assert home.read_text(encoding="utf-8") == _starter()


def test_unreadable_builtin_logs_and_exits_1(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    with (
        patch.object(Path, "read_text", side_effect=PermissionError(13, "denied")),
        caplog.at_level(logging.ERROR),
    ):
        result = _init()

    assert result.exit_code == 1
    assert any(str(_BUILTIN) in record.getMessage() for record in caplog.records)
    assert not home.exists()


def test_write_error_logs_and_leaves_no_partial_file(
    home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        patch("squadron.cli.commands.models.write_new_file", side_effect=OSError(28, "No space")),
        caplog.at_level(logging.ERROR),
    ):
        result = _init()

    assert result.exit_code == 1
    assert any(str(home) in record.getMessage() for record in caplog.records)
    assert not home.exists()
