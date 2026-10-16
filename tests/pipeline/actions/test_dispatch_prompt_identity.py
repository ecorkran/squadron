"""Prompt identity on dispatch (slice 177 D8): hash, source and versions per branch."""

from __future__ import annotations

import hashlib
from pathlib import Path

import squadron
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.actions.prompt_identity import PromptSource
from squadron.pipeline.models import ActionResult
from tests.pipeline.actions.dispatch_helpers import make_context
from tests.pipeline.actions.test_dispatch_pre_emption import (
    _write_real_fragment,  # pyright: ignore[reportPrivateUsage]
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_context_result(stdout: str, *, cf: str | None, guide: str | None) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="cf-op",
        outputs={
            "operation": "build_context",
            "stdout": stdout,
            "cf_version": cf,
            "guide_version": guide,
        },
    )


def _review_result() -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={},
        verdict="CONCERNS",
        findings=[{"severity": "concern", "summary": "Plan is ignored", "location": "a.py:1"}],
    )


def _resolve(**overrides: object):  # pyright: ignore[reportUnknownParameterType]
    ctx = make_context(**overrides)
    return DispatchAction()._resolve_prompt(ctx)  # pyright: ignore[reportPrivateUsage]


def test_build_context_source_carries_versions() -> None:
    prior = {"0-cf-op-0": _build_context_result("Built context", cf="0.19.13", guide="v0.21.1")}

    resolved = _resolve(params={}, prior_outputs=prior)

    assert resolved.source is PromptSource.BUILD_CONTEXT
    identity = resolved.identity()
    assert identity["sha256"] == _sha(resolved.text) == _sha("Built context")
    assert identity["source"] == "build_context"
    assert identity["squadron_version"] == squadron.__version__
    assert identity["cf_version"] == "0.19.13"
    assert identity["guide_version"] == "v0.21.1"


def test_build_context_without_guide_file_records_none() -> None:
    prior = {"0-cf-op-0": _build_context_result("Built", cf="0.19.13", guide=None)}

    identity = _resolve(params={}, prior_outputs=prior).identity()

    assert identity["cf_version"] == "0.19.13"
    assert identity["guide_version"] is None


def test_explicit_source_has_no_cf_or_guide_version() -> None:
    resolved = _resolve(params={"prompt": "Do the thing"})

    identity = resolved.identity()
    assert resolved.source is PromptSource.EXPLICIT
    assert identity["sha256"] == _sha("Do the thing")
    assert identity["cf_version"] is None
    assert identity["guide_version"] is None
    assert identity["squadron_version"] == squadron.__version__


def test_feedback_source_ignores_build_context_versions() -> None:
    prior = {
        "0-review-0": _review_result(),
        "1-cf-op-1": _build_context_result("Built", cf="0.19.13", guide="v0.21.1"),
    }

    resolved = _resolve(params={"feedback": "review"}, prior_outputs=prior)

    identity = resolved.identity()
    assert resolved.source is PromptSource.FEEDBACK
    assert identity["sha256"] == _sha(resolved.text)
    assert identity["cf_version"] is None
    assert identity["guide_version"] is None


def test_review_findings_source() -> None:
    resolved = _resolve(params={}, prior_outputs={"0-review-0": _review_result()})

    identity = resolved.identity()
    assert resolved.source is PromptSource.REVIEW_FINDINGS
    assert identity["sha256"] == _sha(resolved.text)
    assert identity["cf_version"] is None
    assert identity["guide_version"] is None


def test_override_changes_the_hash() -> None:
    plain = _resolve(params={"prompt": "Do the thing"}).identity()["sha256"]
    overridden = _resolve(
        params={"prompt": "Do the thing", "override_instructions": "do X"}
    ).identity()["sha256"]

    assert plain != overridden


def test_pre_emption_fragment_changes_the_hash(tmp_path: Path) -> None:
    fragment = _write_real_fragment(tmp_path)

    plain = _resolve(params={"prompt": "Do the thing"})
    with_fragment = _resolve(params={"prompt": "Do the thing", "pre_emption_fragment": str(fragment)})

    assert with_fragment.text != plain.text
    assert with_fragment.identity()["sha256"] == _sha(with_fragment.text)
    assert with_fragment.identity()["sha256"] != plain.identity()["sha256"]
