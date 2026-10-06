"""Item resume builds its params from run state and the decision (slice 197 D8, Task 28a)."""

from __future__ import annotations

import logging

import pytest

from squadron.pipeline.batch_report import ItemDecision
from squadron.pipeline.item_resume import ResumeRequest, item_params

_STORED: dict[str, object] = {"plan": "400", "model": "haiku", "review-model": "minimax"}


def _request(**kwargs: object) -> ResumeRequest:
    return ResumeRequest(run_id="r1", index="401", decision=ItemDecision.RETRY, **kwargs)  # type: ignore[arg-type]


def test_run_state_params_and_models_carry_over() -> None:
    assert item_params(_STORED, _request()) == _STORED


def test_overrides_apply_on_top() -> None:
    params = item_params(_STORED, _request(model="sonnet", param_overrides={"max-revisions": "4"}))

    assert (params["model"], params["max-revisions"], params["plan"]) == ("sonnet", "4", "400")


def test_stored_instructions_are_dropped_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    stored = {**_STORED, "override_instructions": "from an old checkpoint"}

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.item_resume"):
        params = item_params(stored, _request())

    assert "override_instructions" not in params
    assert any(
        r.levelno == logging.WARNING and "dropped stored override_instructions" in r.getMessage()
        for r in caplog.records
    )


def test_instructions_and_accept_set_their_keys() -> None:
    params = item_params(
        _STORED,
        ResumeRequest(
            run_id="r1", index="401", decision=ItemDecision.ACCEPT, instructions="keep the flags"
        ),
    )

    assert params["override_instructions"] == "keep the flags"
    assert params["accept_decision"] is True


def test_retry_leaves_accept_decision_unset() -> None:
    params = item_params({**_STORED, "accept_decision": True}, _request())

    assert "accept_decision" not in params
