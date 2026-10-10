"""`sq run -v` carries pipeline INFO logs, including the review profile line, to the terminal (D6)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app

_PIPELINE_LOGGER = "squadron.pipeline"
_REVIEW_ACTION_LOGGER = "squadron.pipeline.actions.review"


@pytest.fixture
def pristine_pipeline_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger(_PIPELINE_LOGGER)
    level, handlers = logger.level, list(logger.handlers)
    logger.handlers.clear()
    yield logger
    logger.setLevel(level)
    logger.handlers[:] = handlers


def test_verbose_run_routes_review_info_logs_to_a_handler(
    pristine_pipeline_logger: logging.Logger,
) -> None:
    result = CliRunner().invoke(app, ["run", "-v", "--validate", "slices-plan"])

    assert result.exit_code == 0
    review_logger = logging.getLogger(_REVIEW_ACTION_LOGGER)
    assert review_logger.isEnabledFor(logging.INFO)
    assert pristine_pipeline_logger.handlers, "no handler would print the profile= line"
