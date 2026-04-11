"""Integration tests — verify all registered actions coexist."""

from __future__ import annotations

import squadron.pipeline.actions.cf_op  # noqa: F401
import squadron.pipeline.actions.checkpoint  # noqa: F401
import squadron.pipeline.actions.commit  # noqa: F401
import squadron.pipeline.actions.devlog  # noqa: F401
import squadron.pipeline.actions.dispatch  # noqa: F401
import squadron.pipeline.actions.review  # noqa: F401
import squadron.pipeline.actions.summary  # noqa: F401
from squadron.pipeline.actions import get_action, list_actions
from squadron.pipeline.actions.cf_op import CfOpAction
from squadron.pipeline.actions.checkpoint import CheckpointAction
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.devlog import DevlogAction
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.actions.summary import SummaryAction


def test_list_actions_includes_all_registered() -> None:
    actions = list_actions()
    assert "cf-op" in actions
    assert "checkpoint" in actions
    assert "commit" in actions
    assert "summary" in actions
    assert "devlog" in actions
    assert "dispatch" in actions
    assert "review" in actions
    # Compact action is no longer registered
    assert "compact" not in actions


def test_get_action_cf_op() -> None:
    action = get_action("cf-op")
    assert isinstance(action, CfOpAction)
    assert isinstance(action, Action)


def test_get_action_commit() -> None:
    action = get_action("commit")
    assert isinstance(action, CommitAction)
    assert isinstance(action, Action)


def test_get_action_devlog() -> None:
    action = get_action("devlog")
    assert isinstance(action, DevlogAction)
    assert isinstance(action, Action)


def test_get_action_dispatch() -> None:
    action = get_action("dispatch")
    assert isinstance(action, DispatchAction)
    assert isinstance(action, Action)


def test_get_action_review() -> None:
    action = get_action("review")
    assert isinstance(action, ReviewAction)
    assert isinstance(action, Action)


def test_get_action_checkpoint() -> None:
    action = get_action("checkpoint")
    assert isinstance(action, CheckpointAction)
    assert isinstance(action, Action)


def test_get_action_summary() -> None:
    action = get_action("summary")
    assert isinstance(action, SummaryAction)
    assert isinstance(action, Action)


def test_no_import_errors() -> None:
    """Importing all action modules should not raise."""

    # If we got here, no circular dependency or import error
    assert True
