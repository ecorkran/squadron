"""Turns, token usage, and duration in review artifacts (slice 931 D10, D12).

Frontmatter, the Run Digest, and JSON must agree when rendered from one ``ReviewResult``,
and the provider-failure artifact must render the same keys from one ``ProviderError``.
Unreported values are never rendered as 0.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from squadron.core.usage import RunTelemetry, TokenUsage
from squadron.documents.frontmatter import read_frontmatter
from squadron.providers.errors import ProviderAPIError, ProviderError
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import format_provider_failure_markdown, format_review_markdown
from squadron.review.run_cost import NOT_COMPUTED

_SLICE_INFO = {
    "index": 931,
    "name": "s",
    "slice_name": "s",
    "design_file": "d.md",
    "phase": "6",
    "project": "squadron",
}

_TOKEN_LINE = "- Tokens — prompt / cached / completion / reasoning: "


def _result(**cost: object) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="clean",
        template_name="code",
        input_files={"input": "f.md"},
        timestamp=datetime(2026, 9, 30, 12, 0, 0),
        model="m",
        **cost,  # type: ignore[arg-type]
    )


def _frontmatter(md: str) -> dict[str, object]:
    return yaml.safe_load(md.split("---")[1])


def _digest_value(md: str, prefix: str) -> str:
    line = next(line for line in md.splitlines() if line.startswith(prefix))
    return line[len(prefix) :]


def test_success_frontmatter_digest_and_json_agree() -> None:
    result = _result(
        turns=9,
        usage=TokenUsage(prompt=412803, cached=380112, completion=9214, reasoning=6120),
        duration_seconds=214.34,
    )

    md = format_review_markdown(result, "code", _SLICE_INFO)  # type: ignore[arg-type]
    front = _frontmatter(md)
    payload = result.to_dict()

    assert (front["turns"], payload["turns"], _digest_value(md, "- Turns: ")) == (9, 9, "9")
    assert front["promptTokens"] == payload["prompt_tokens"] == 412803
    assert front["cachedTokens"] == payload["cached_tokens"] == 380112
    assert front["completionTokens"] == payload["completion_tokens"] == 9214
    assert front["reasoningTokens"] == payload["reasoning_tokens"] == 6120
    assert _digest_value(md, _TOKEN_LINE) == "412803 / 380112 / 9214 / 6120"
    assert front["durationSeconds"] == 214.3
    assert payload["duration_seconds"] == 214.34
    assert _digest_value(md, "- Duration: ") == "214.3 s"


def test_unreported_fields_are_absent_sentinel_and_null_never_zero() -> None:
    result = _result(turns=2, usage=TokenUsage(prompt=10, completion=3), duration_seconds=None)

    md = format_review_markdown(result, "code", _SLICE_INFO)  # type: ignore[arg-type]
    front = _frontmatter(md)
    payload = result.to_dict()

    for key in ("cachedTokens", "reasoningTokens", "durationSeconds"):
        assert key not in front
    assert payload["cached_tokens"] is None
    assert payload["reasoning_tokens"] is None
    assert payload["duration_seconds"] is None
    assert _digest_value(md, _TOKEN_LINE) == f"10 / {NOT_COMPUTED} / 3 / {NOT_COMPUTED}"
    assert _digest_value(md, "- Duration: ") == NOT_COMPUTED


def test_new_keys_parse_under_the_existing_frontmatter_reader(tmp_path: Path) -> None:
    result = _result(turns=3, usage=TokenUsage(prompt=1, cached=0), duration_seconds=1.0)
    path = tmp_path / "review.md"
    path.write_text(format_review_markdown(result, "code", _SLICE_INFO))  # type: ignore[arg-type]

    front = read_frontmatter(path)

    assert front["verdict"] == "PASS"
    assert front["turns"] == 3
    # A reported 0 is a real value and is emitted.
    assert front["cachedTokens"] == 0


def _failed(telemetry: RunTelemetry | None, duration: float | None) -> ProviderError:
    exc = ProviderAPIError("boom", status_code=500)
    exc.telemetry = telemetry
    exc.duration_seconds = duration
    return exc


def test_failure_frontmatter_and_digest_agree_from_one_error() -> None:
    exc = _failed(
        RunTelemetry(turns=2, reasoning_chars=5, usage=TokenUsage(prompt=30, cached=6, completion=3)),
        12.04,
    )

    md = format_provider_failure_markdown(exc, "code", _SLICE_INFO)  # type: ignore[arg-type]
    front = _frontmatter(md)

    assert front["providerFailure"] is True
    assert (front["turns"], _digest_value(md, "- Turns: ")) == (2, "2")
    assert (front["promptTokens"], front["cachedTokens"], front["completionTokens"]) == (30, 6, 3)
    assert "reasoningTokens" not in front
    assert _digest_value(md, _TOKEN_LINE) == f"30 / 6 / 3 / {NOT_COMPUTED}"
    assert front["durationSeconds"] == 12.0
    assert _digest_value(md, "- Duration: ") == "12.0 s"


def test_failure_without_telemetry_renders_no_fabricated_zeros() -> None:
    md = format_provider_failure_markdown(_failed(None, None), "code", _SLICE_INFO)  # type: ignore[arg-type]
    front = _frontmatter(md)

    for key in ("turns", "promptTokens", "cachedTokens", "durationSeconds"):
        assert key not in front
    assert _digest_value(md, "- Turns: ") == NOT_COMPUTED
    assert _digest_value(md, "- Duration: ") == NOT_COMPUTED
