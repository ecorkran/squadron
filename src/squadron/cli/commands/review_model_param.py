"""``-p review-model=X`` on the review commands: an alias for ``--model`` (#286)."""

from __future__ import annotations

import typer

from squadron.cli.commands.param_parsing import param_pairs

REVIEW_MODEL_PARAM_KEY = "review-model"

PARAM_OPTION_HELP = (
    f"Param as key=value, as on `sq run`. The only key here is {REVIEW_MODEL_PARAM_KEY} "
    "(an alias for --model). A space after a comma is fine."
)


def resolve_review_model(model: str | None, param_list: list[str] | None) -> str | None:
    """Merge ``--model`` with a ``review-model`` param into one model value.

    Any other param key is an error naming the accepted key. Giving both with
    different values is an error; equal values are accepted.
    """
    param_model: str | None = None
    for key, value in param_pairs(param_list):
        if key != REVIEW_MODEL_PARAM_KEY:
            raise typer.BadParameter(
                f"Unknown --param key '{key}' on a review command; "
                f"the only accepted key is {REVIEW_MODEL_PARAM_KEY}"
            )
        if not value:
            raise typer.BadParameter(f"--param {REVIEW_MODEL_PARAM_KEY} needs a value")
        if param_model is not None and param_model != value:
            raise typer.BadParameter(
                f"--param {REVIEW_MODEL_PARAM_KEY} given twice with different values "
                f"('{param_model}', '{value}')"
            )
        param_model = value
    if model is not None and param_model is not None and model != param_model:
        raise typer.BadParameter(
            f"--model '{model}' conflicts with --param {REVIEW_MODEL_PARAM_KEY}={param_model}"
        )
    return model if model is not None else param_model
