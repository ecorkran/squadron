"""squadron.usage-stamp failure modes: each returns success and leaves a log signal (178 D6)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.documents.frontmatter import read_frontmatter
from squadron.events.builtin.usage_stamp import UsageStampAction
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.steps.phase import ArtifactKind
from tests.events.builtin.usage_stamp_helpers import (
    DESIGN_REL,
    SLICE_FRONT,
    TASKS_FRONT,
    TASKS_REL,
    fake_cf_client,
    post_action_context,
    write_doc,
)

_ACTION = UsageStampAction()


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


async def _run_expecting_one_warning(
    caplog: pytest.LogCaptureFixture, ctx_cwd: Path, **kwargs: object
) -> str:
    with caplog.at_level(logging.DEBUG):
        result = await _ACTION.execute(post_action_context(ctx_cwd, **kwargs))  # type: ignore[arg-type]
    assert result.success
    warnings = _warnings(caplog)
    assert len(warnings) == 1, warnings
    return warnings[0]


async def test_cf_resolution_error_warns_with_kind_scope_and_reason(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = fake_cf_client()
    cf_client.list_slices.side_effect = ContextForgeError("cf is down")
    message = await _run_expecting_one_warning(caplog, tmp_path, cf_client=cf_client)
    assert "design" in message and "slice=178" in message and "cf is down" in message


async def test_plan_scope_without_arch_doc_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    message = await _run_expecting_one_warning(caplog, tmp_path, params={"plan": "140"})
    assert "plan=140" in message and "140-arch" in message


async def test_non_numeric_slice_param_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    message = await _run_expecting_one_warning(caplog, tmp_path, params={"slice": "abc"})
    assert "not a numeric index" in message


@pytest.mark.parametrize(
    "content",
    ["# No frontmatter at all\n", "---\nkey: [unclosed\n---\n\nbody\n"],
    ids=["no-block", "invalid-yaml"],
)
async def test_unreadable_frontmatter_warns_with_path_and_error_type(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, content: str
) -> None:
    path = tmp_path / DESIGN_REL
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    message = await _run_expecting_one_warning(caplog, tmp_path)
    assert str(path) in message and "FrontmatterError" in message
    assert path.read_text(encoding="utf-8") == content


async def test_non_utf8_artifact_warns_and_is_untouched(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / DESIGN_REL
    path.parent.mkdir(parents=True)
    content = b"---\ndocType: slice-design\n---\n\n\xff\xfe body\n"
    path.write_bytes(content)
    message = await _run_expecting_one_warning(caplog, tmp_path)
    assert str(path) in message and "UnicodeDecodeError" in message
    assert path.read_bytes() == content


async def test_write_oserror_warns_with_path(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    with patch(
        "squadron.events.builtin.usage_stamp.update_frontmatter", side_effect=OSError("disk full")
    ):
        message = await _run_expecting_one_warning(caplog, tmp_path)
    assert str(path) in message and "disk full" in message


async def test_two_candidates_stamp_nothing_and_name_both(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    names = ["178-tasks.example-1.md", "178-tasks.example-2.md"]
    paths = [write_doc(tmp_path, TASKS_REL.parent / name, TASKS_FRONT) for name in names]
    before = [p.read_bytes() for p in paths]
    message = await _run_expecting_one_warning(
        caplog, tmp_path, kind=ArtifactKind.TASKS, cf_client=fake_cf_client(names)
    )
    assert all(name in message for name in names)
    assert [p.read_bytes() for p in paths] == before


async def test_revision_round_without_prior_keys_warns_and_stamps_one_round(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    message = await _run_expecting_one_warning(caplog, tmp_path, iteration=2)
    assert (
        f"usage stamp: no prior usage keys on revision round 2 of {path}; "
        "total restarts and undercounts"
    ) == message
    front = read_frontmatter(path)
    assert front is not None and front["usageRounds"] == 1


async def test_malformed_prior_key_warns_and_total_restarts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    front = SLICE_FRONT.removesuffix("---\n") + (
        "usageRounds: 2\npricedRounds: 1\ncostUsd: free\n---\n"
    )
    path = write_doc(tmp_path, DESIGN_REL, front)
    message = await _run_expecting_one_warning(caplog, tmp_path, iteration=1)
    assert str(path) in message and "costUsd" in message
    stamped = read_frontmatter(path)
    assert stamped is not None
    assert stamped["usageRounds"] == 1 and stamped["costUsd"] == 0.5


async def test_no_usage_record_logs_debug_naming_the_step(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    before = path.read_bytes()
    with caplog.at_level(logging.DEBUG):
        result = await _ACTION.execute(post_action_context(tmp_path, metadata={}))
    assert result.success
    debug = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("design" in m and "usage" in m for m in debug)
    assert _warnings(caplog) == []
    assert path.read_bytes() == before
