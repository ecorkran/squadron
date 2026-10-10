"""The ``sq models init`` starter file (slice 940 D2)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

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
