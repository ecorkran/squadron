"""#140: `sq review` reports a judge template's threshold verdict, not the raw parse."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.review.models import ReviewResult, Verdict
from squadron.review.templates import ReviewTemplate


def _judge_template() -> ReviewTemplate:
    return ReviewTemplate(
        name="judge-test",
        description="Judge template",
        system_prompt="You are a judge.",
        allowed_tools=[],
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        prompt_template="judge {input}",
        profile="sdk",
        judge={"pass_floor": 80, "concerns_floor": 60},
    )


@pytest.mark.parametrize(("score", "expected"), [(85.0, "PASS"), (70.0, "CONCERNS"), (None, "UNKNOWN")])
def test_json_output_carries_the_threshold_verdict(
    score: float | None,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from squadron.cli.commands.review import _run_review_command

    (tmp_path / "f.md").write_text("# f\n")
    result = ReviewResult(
        verdict=Verdict.UNKNOWN,
        findings=[],
        raw_output="raw",
        template_name="judge-test",
        input_files={"input": "f.md"},
        model="opus",
        score=score,
    )
    monkeypatch.setattr("squadron.cli.commands.review.load_all_templates", lambda: None)
    monkeypatch.setattr("squadron.cli.commands.review.get_template", lambda name: _judge_template())
    monkeypatch.setattr("squadron.cli.commands.review.get_config", lambda k: None)

    with patch(
        "squadron.cli.commands.review._execute_review", new_callable=AsyncMock, return_value=result
    ):
        returned = _run_review_command(
            "judge-test",
            {"input": "f.md", "cwd": str(tmp_path)},
            "json",
            None,
            0,
            model_flag="opus",
            profile_flag="sdk",
        )

    assert json.loads(capsys.readouterr().out)["verdict"] == expected
    # The returned result is what callers save, so the artifact agrees with stdout.
    assert returned.verdict.value == expected
