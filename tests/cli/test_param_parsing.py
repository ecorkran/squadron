"""``-p a=1, b=2`` (space after the comma) behaves like ``-p a=1,b=2`` (#291)."""

from __future__ import annotations

from unittest.mock import patch

import click.testing
import pytest
import typer
import typer.main
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.param_parsing import (
    StrayParamCommand,
    param_pairs,
    with_stray_pairs,
)
from squadron.pipeline.models import PipelineDefinition, StepConfig

runner = CliRunner()

_DEFINITION = PipelineDefinition(
    name="test-pipeline",
    description="Test pipeline",
    params={"slice": "required"},
    steps=[StepConfig(step_type="phase", name="s1", config={})],
)


def _dry_run(*extra: str) -> click.testing.Result:
    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_DEFINITION),
        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
    ):
        return runner.invoke(app, ["run", "test", "191", "--dry-run", *extra])


def test_trailing_comma_is_dropped() -> None:
    assert param_pairs(["model=sonnet-high,"]) == [("model", "sonnet-high")]


def test_interior_empty_pair_still_fails() -> None:
    with pytest.raises(typer.BadParameter, match="expected key=value"):
        param_pairs(["a=1,,b=2"])


def test_stray_pair_after_trailing_comma_is_folded_into_params() -> None:
    folded = with_stray_pairs(["model=sonnet-high,"], ["review-model=haiku-xhigh"])
    assert param_pairs(folded) == [("model", "sonnet-high"), ("review-model", "haiku-xhigh")]


def test_stray_pair_without_trailing_comma_is_an_error() -> None:
    with pytest.raises(typer.BadParameter, match="Unexpected extra argument 'b=2'"):
        with_stray_pairs(["a=1"], ["b=2"])
    with pytest.raises(typer.BadParameter, match="Unexpected extra argument 'b=2'"):
        with_stray_pairs(None, ["b=2"])


def test_stray_non_pair_is_an_error() -> None:
    with pytest.raises(typer.BadParameter, match="Unexpected extra argument 'oops'"):
        with_stray_pairs(["a=1,"], ["oops"])


def test_no_stray_arguments_leaves_params_unchanged() -> None:
    assert with_stray_pairs(None, []) is None
    assert with_stray_pairs(["a=1"], []) == ["a=1"]


def test_run_dry_run_shows_both_params_after_space_comma() -> None:
    result = _dry_run("-p", "alpha=one,", "beta=two")
    assert result.exit_code == 0, result.output
    assert "'alpha': 'one'" in result.output
    assert "'beta': 'two'" in result.output


def test_run_dry_run_without_p_is_unchanged() -> None:
    result = _dry_run()
    assert result.exit_code == 0, result.output
    assert "'slice': '191'" in result.output


def test_run_rejects_bare_pair_without_trailing_comma() -> None:
    result = _dry_run("beta=two")
    assert result.exit_code != 0
    assert "Unexpected extra argument" in result.output


@pytest.mark.parametrize("name", ["slice", "arch", "tasks", "code"])
def test_review_commands_use_stray_param_handling(name: str) -> None:
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    review = root.commands["review"]
    assert isinstance(review, click.Group)
    assert isinstance(review.commands[name], StrayParamCommand)
