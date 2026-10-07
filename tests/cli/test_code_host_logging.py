"""``code_host_logging`` prints each code-host failure once and leaves nothing behind (#186)."""

from __future__ import annotations

import logging

import pytest
import typer

from squadron.cli.commands.pr import code_host_logging
from squadron.codehost.errors import RENDERED_BY_CALLER

_LOGGER_NAME = "squadron.codehost"
_SOURCE = logging.getLogger("squadron.codehost.refs")


def _emit(*, tagged: bool, message: str) -> None:
    extra = {RENDERED_BY_CALLER: True} if tagged else None
    _SOURCE.warning(message, extra=extra)


def _handler_count() -> int:
    return len(logging.getLogger(_LOGGER_NAME).handlers)


@pytest.mark.parametrize("verbosity", [0, 1])
def test_tagged_records_are_hidden_below_dash_vv(
    verbosity: int, capsys: pytest.CaptureFixture[str]
) -> None:
    with code_host_logging(verbosity):
        _emit(tagged=True, message="rendered by the command")

    assert "rendered by the command" not in capsys.readouterr().err


def test_tagged_records_show_with_a_prefix_at_dash_vv(capsys: pytest.CaptureFixture[str]) -> None:
    with code_host_logging(2):
        _emit(tagged=True, message="rendered by the command")

    assert "WARNING squadron.codehost.refs: rendered by the command" in capsys.readouterr().err


@pytest.mark.parametrize("verbosity", [0, 1, 2])
def test_untagged_records_reach_stderr_at_every_verbosity(
    verbosity: int, capsys: pytest.CaptureFixture[str]
) -> None:
    with code_host_logging(verbosity):
        _emit(tagged=False, message="a diagnostic nobody else prints")

    assert "WARNING squadron.codehost.refs: a diagnostic nobody else prints" in (
        capsys.readouterr().err
    )


def test_nested_entry_adds_no_second_handler_and_everything_is_cleaned_up() -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    before_level = logger.level
    before_handlers = _handler_count()

    with code_host_logging(0):
        assert _handler_count() == before_handlers + 1
        with code_host_logging(2):
            assert _handler_count() == before_handlers + 1
        assert _handler_count() == before_handlers + 1  # the inner exit left the outer in place

    assert _handler_count() == before_handlers
    assert logger.level == before_level


def test_a_typer_exit_inside_still_cleans_up() -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    before_level = logger.level
    before_handlers = _handler_count()

    with pytest.raises(typer.Exit):
        with code_host_logging(1):
            raise typer.Exit(code=1)

    assert _handler_count() == before_handlers
    assert logger.level == before_level


def test_records_still_reach_root_handlers(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        with code_host_logging(0):
            _emit(tagged=True, message="tagged but still propagated")
            _emit(tagged=False, message="untagged and propagated")

    messages = [record.getMessage() for record in caplog.records]
    assert "tagged but still propagated" in messages
    assert "untagged and propagated" in messages
