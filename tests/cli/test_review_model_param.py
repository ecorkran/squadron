"""``sq review ... -p review-model=X`` is an alias for ``--model`` (#286)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review_model_param import resolve_review_model

runner = CliRunner()

_RUNNER = "squadron.cli.commands.review.run_review_revise"
_REVISE = "squadron.cli.commands.review_revise"


def _invoke(*args: str) -> Any:
    return runner.invoke(app, ["review", *args])


def _model_reaching_the_runner(*args: str) -> str | None:
    """The model the --max path hands to the revise runner for these flags."""
    with patch(_RUNNER, return_value=0) as run, patch(f"{_REVISE}._require_branch_preconditions"):
        result = _invoke("code", "941", "--max", "1", *args)
    assert result.exit_code == 0, result.output
    return run.call_args.args[2]


def test_param_resolves_the_same_model_as_the_flag() -> None:
    assert _model_reaching_the_runner("-p", "review-model=sol") == "sol"
    assert _model_reaching_the_runner("--param", "review-model=sol") == "sol"
    assert _model_reaching_the_runner("--model", "sol") == "sol"


@pytest.mark.parametrize("command", ["slice", "arch", "tasks", "code"])
def test_every_review_command_accepts_the_param(command: str) -> None:
    result = _invoke(command, "--help")
    assert "--param" in result.output


def test_unknown_key_fails_naming_review_model() -> None:
    result = _invoke("code", "941", "-p", "model=sol")
    assert result.exit_code != 0
    assert "review-model" in result.output


def test_param_without_equals_is_an_error() -> None:
    with pytest.raises(typer.BadParameter, match="expected key=value"):
        resolve_review_model(None, ["review-model"])


def test_both_given_and_different_is_an_error() -> None:
    with pytest.raises(typer.BadParameter, match="conflicts"):
        resolve_review_model("opus", ["review-model=sonnet"])


def test_both_given_and_equal_is_accepted() -> None:
    assert resolve_review_model("sonnet", ["review-model=sonnet"]) == "sonnet"


def test_comma_separated_entry_with_another_key_is_an_error() -> None:
    with pytest.raises(typer.BadParameter, match="review-model"):
        resolve_review_model(None, ["review-model=sonnet,other=1"])


def test_neither_given_is_none() -> None:
    assert resolve_review_model(None, None) is None
