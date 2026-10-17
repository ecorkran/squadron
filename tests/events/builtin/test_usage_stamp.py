"""squadron.usage-stamp: eligibility and happy paths (slice 178 D1, D2)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.documents.frontmatter import read_frontmatter
from squadron.events.builtin.usage_stamp import UsageStampAction
from squadron.pipeline.steps.phase import ArtifactKind
from tests.events.builtin.usage_stamp_helpers import (
    ARCH_FRONT,
    ARCH_REL,
    BODY,
    DESIGN_REL,
    SLICE_FRONT,
    TASKS_FRONT,
    TASKS_REL,
    post_action_context,
    usage_record,
    write_doc,
)

_ACTION = UsageStampAction()


def _front(path: Path) -> dict[str, object]:
    front = read_frontmatter(path)
    assert front is not None
    return dict(front)


async def test_slice_design_gains_review_keys_and_one_round(tmp_path: Path) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    result = await _ACTION.execute(post_action_context(tmp_path))
    assert result.success
    front = _front(path)
    assert front["usageRounds"] == 1
    assert front["pricedRounds"] == 1
    assert front["costUsd"] == 0.5
    assert front["turns"] == 2
    assert front["promptTokens"] == 100
    assert front["durationSeconds"] == 4.0
    assert "costBasis" not in front


async def test_task_file_dispatch_is_stamped(tmp_path: Path) -> None:
    path = write_doc(tmp_path, TASKS_REL, TASKS_FRONT)
    ctx = post_action_context(tmp_path, kind=ArtifactKind.TASKS)
    await _ACTION.execute(ctx)
    assert _front(path)["usageRounds"] == 1


async def test_plan_scoped_design_stamps_the_architecture_doc(tmp_path: Path) -> None:
    path = write_doc(tmp_path, ARCH_REL, ARCH_FRONT)
    ctx = post_action_context(tmp_path, params={"plan": "140"})
    await _ACTION.execute(ctx)
    assert _front(path)["usageRounds"] == 1


async def test_second_fold_sums_without_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    await _ACTION.execute(post_action_context(tmp_path))
    with caplog.at_level(logging.WARNING):
        await _ACTION.execute(post_action_context(tmp_path, iteration=1))
    front = _front(path)
    assert front["usageRounds"] == 2
    assert front["costUsd"] == pytest.approx(1.0)
    assert front["turns"] == 4
    assert front["promptTokens"] == 200
    assert caplog.records == []


async def test_unpriced_record_counts_round_but_not_cost(tmp_path: Path) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    await _ACTION.execute(post_action_context(tmp_path))
    await _ACTION.execute(post_action_context(tmp_path, record=usage_record(cost_usd=None)))
    front = _front(path)
    assert front["usageRounds"] == 2
    assert front["pricedRounds"] == 1
    assert front["costUsd"] == 0.5


async def test_body_bytes_and_existing_key_order_are_kept(tmp_path: Path) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    await _ACTION.execute(post_action_context(tmp_path))
    text = path.read_text(encoding="utf-8")
    assert text.endswith(BODY)
    keys = list(_front(path))
    original = list(_front(write_doc(tmp_path, Path("orig.md"), SLICE_FRONT)))
    assert keys[: len(original)] == original


@pytest.mark.parametrize(
    "overrides",
    [
        {"action_type": "review"},
        {"success": False},
        {"kind": None},  # implement dispatch
        {"metadata": {}},  # existing: keep / prompt-only
    ],
    ids=["non-dispatch", "failed", "no-artifact-kind", "no-usage"],
)
async def test_ineligible_dispatch_leaves_file_untouched(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    before = path.read_bytes()
    result = await _ACTION.execute(post_action_context(tmp_path, **overrides))  # type: ignore[arg-type]
    assert result.success
    assert path.read_bytes() == before


async def test_stamp_writes_no_run_state(tmp_path: Path) -> None:
    write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    with patch("squadron.pipeline.state.StateManager._save") as save:  # pyright: ignore[reportPrivateUsage]
        await _ACTION.execute(post_action_context(tmp_path))
    save.assert_not_called()
