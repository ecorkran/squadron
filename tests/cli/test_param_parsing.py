"""``-p a=1, b=2`` (space after the comma) behaves like ``-p a=1,b=2`` (#291)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.param_parsing import param_pairs, with_stray_pairs

runner = CliRunner()


def test_trailing_comma_is_dropped() -> None:
    assert param_pairs(["model=sonnet-high,"]) == [("model", "sonnet-high")]


def test_interior_empty_pair_still_fails() -> None:
    with pytest.raises(typer.BadParameter, match="expected key=value"):
        param_pairs(["a=1,,b=2"])


def test_stray_pair_is_folded_into_params() -> None:
    folded = with_stray_pairs(["model=sonnet-high,"], ["review-model=haiku-xhigh"])
    assert param_pairs(folded) == [("model", "sonnet-high"), ("review-model", "haiku-xhigh")]


def test_stray_non_pair_is_an_error() -> None:
    with pytest.raises(typer.BadParameter, match="Unexpected extra argument 'oops'"):
        with_stray_pairs(None, ["oops"])


def test_run_command_receives_both_params_after_space_comma() -> None:
    with patch("squadron.cli.commands.run._apply_param_overrides") as apply:
        runner.invoke(
            app,
            [
                "run",
                "tasks-plan",
                "180",
                "--dry-run",
                "-p",
                "model=sonnet-high,",
                "review-model=haiku-xhigh",
            ],
        )
    seen = [call.args[1] for call in apply.call_args_list]
    assert ["model=sonnet-high,", "review-model=haiku-xhigh"] in seen


def test_run_command_rejects_stray_non_pair() -> None:
    result = runner.invoke(app, ["run", "tasks-plan", "180", "oops"])
    assert result.exit_code != 0
    assert "Unexpected extra argument" in result.output
