"""Tests for DevlogAction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions.devlog import DevlogAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext, ActionResult


@pytest.fixture
def action() -> DevlogAction:
    return DevlogAction()


def _make_context(
    cwd: str,
    prior_outputs: dict[str, ActionResult] | None = None,
    **params: object,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-001",
        params=dict(params),
        step_name="devlog-step",
        step_index=0,
        prior_outputs=prior_outputs or {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=cwd,
    )


SAMPLE_DEVLOG = """\
---
docType: devlog
project: test
dateCreated: 20260101
dateUpdated: 20260330
---

# Development Log

A lightweight, append-only record.

---

## 20260330

**Previous entry**
Some earlier content.

---

## 20260329

**Even older entry**
Old content.
"""


def test_action_type(action: DevlogAction) -> None:
    assert action.action_type == "devlog"


def test_protocol_compliance(action: DevlogAction) -> None:
    assert isinstance(action, Action)


# --- validate() ---


def test_validate_warns_no_content_no_prior(action: DevlogAction) -> None:
    errors = action.validate({})
    assert len(errors) == 1
    assert errors[0].field == "content"
    assert "minimal" in errors[0].message


def test_validate_ok_with_content(action: DevlogAction) -> None:
    errors = action.validate({"content": "Some text"})
    assert errors == []


# --- execute() ---


@pytest.mark.asyncio
async def test_explicit_content(action: DevlogAction, tmp_path: Path) -> None:
    devlog = tmp_path / "DEVLOG.md"
    devlog.write_text(SAMPLE_DEVLOG)

    ctx = _make_context(str(tmp_path), content="Explicit entry text")

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    text = devlog.read_text()
    assert "Explicit entry text" in text


@pytest.mark.asyncio
async def test_auto_generated_from_prior_outputs(
    action: DevlogAction, tmp_path: Path
) -> None:
    devlog = tmp_path / "DEVLOG.md"
    devlog.write_text(SAMPLE_DEVLOG)

    prior = {
        "step-a": ActionResult(success=True, action_type="cf-op", outputs={}),
        "step-b": ActionResult(
            success=False,
            action_type="commit",
            outputs={},
            verdict="FAIL",
        ),
    }
    ctx = _make_context(str(tmp_path), prior_outputs=prior)

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    text = devlog.read_text()
    assert "step-a: PASS" in text
    assert "step-b: FAIL" in text
    assert "verdict: FAIL" in text


@pytest.mark.asyncio
async def test_creates_devlog_if_missing(action: DevlogAction, tmp_path: Path) -> None:
    devlog = tmp_path / "DEVLOG.md"
    assert not devlog.exists()

    ctx = _make_context(str(tmp_path), content="New entry")

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    assert devlog.exists()
    text = devlog.read_text()
    assert "New entry" in text
    assert "## 20260331" in text


@pytest.mark.asyncio
async def test_inserts_under_existing_today_header(
    action: DevlogAction, tmp_path: Path
) -> None:
    devlog = tmp_path / "DEVLOG.md"
    devlog.write_text(SAMPLE_DEVLOG)

    ctx = _make_context(str(tmp_path), content="Today's addition")

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260330"
        result = await action.execute(ctx)

    assert result.success is True
    text = devlog.read_text()
    # Should only have one ## 20260330 header
    assert text.count("## 20260330") == 1
    assert "Today's addition" in text
    # Existing content preserved
    assert "Previous entry" in text


@pytest.mark.asyncio
async def test_creates_new_date_header(action: DevlogAction, tmp_path: Path) -> None:
    devlog = tmp_path / "DEVLOG.md"
    devlog.write_text(SAMPLE_DEVLOG)

    ctx = _make_context(str(tmp_path), content="New day entry")

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    text = devlog.read_text()
    assert "## 20260331" in text
    # New header should appear before existing dates
    idx_new = text.index("## 20260331")
    idx_old = text.index("## 20260330")
    assert idx_new < idx_old


@pytest.mark.asyncio
async def test_preserves_existing_content(action: DevlogAction, tmp_path: Path) -> None:
    devlog = tmp_path / "DEVLOG.md"
    devlog.write_text(SAMPLE_DEVLOG)

    ctx = _make_context(str(tmp_path), content="Added entry")

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    text = devlog.read_text()
    assert "Previous entry" in text
    assert "Even older entry" in text
    assert "docType: devlog" in text


@pytest.mark.asyncio
async def test_custom_path_override(action: DevlogAction, tmp_path: Path) -> None:
    custom_path = tmp_path / "subdir" / "MY_DEVLOG.md"
    ctx = _make_context(
        str(tmp_path), content="Custom path entry", path=str(custom_path)
    )

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    assert custom_path.exists()
    assert "Custom path entry" in custom_path.read_text()
    assert result.outputs["path"] == str(custom_path)


@pytest.mark.asyncio
async def test_returns_path_and_entry_in_outputs(
    action: DevlogAction, tmp_path: Path
) -> None:
    devlog = tmp_path / "DEVLOG.md"
    devlog.write_text(SAMPLE_DEVLOG)

    ctx = _make_context(str(tmp_path), content="Output test")

    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
        mock_date.today.return_value.strftime.return_value = "20260331"
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["path"] == str(devlog)
    assert "Output test" in str(result.outputs["entry"])
