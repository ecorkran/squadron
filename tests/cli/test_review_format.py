"""Tests for structured findings in review frontmatter formatting."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
import yaml

from squadron.cli.commands.review import _display_terminal
from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)
from squadron.review.persistence import (
    SliceInfo,
    format_review_markdown,
    yaml_escape,
)

SLICE_INFO: SliceInfo = {
    "index": 143,
    "name": "Structured Review Findings",
    "slice_name": "structured-review-findings",
    "design_file": ("project-documents/user/slices/143-slice.structured-review-findings.md"),
    "task_files": ["143-tasks.structured-review-findings.md"],
    "arch_file": ("project-documents/user/architecture/140-arch.pipeline-foundation.md"),
    "project": "squadron",
}


def _make_result_with_structured_findings() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="No try/except.",
                file_ref="src/foo.py:10",
                category="error-handling",
                location="src/foo.py:10",
            ),
            ReviewFinding(
                severity=Severity.NOTE,
                title="Variable name unclear",
                description="Variable x is vague.",
                category="naming",
            ),
        ],
        raw_output="raw",
        template_name="code",
        input_files={},
        timestamp=datetime(2026, 3, 30, 12, 0, 0),
        model="opus",
    )


def _make_result_no_findings() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="raw",
        template_name="code",
        input_files={},
        timestamp=datetime(2026, 3, 30, 12, 0, 0),
        model="opus",
    )


class TestFrontmatterFindings:
    """Test structured findings block in YAML frontmatter."""

    def test_findings_block_present(self) -> None:
        result = _make_result_with_structured_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        assert "findings:" in md

    def test_finding_has_required_fields(self) -> None:
        result = _make_result_with_structured_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        assert "  - id: F001" in md
        assert "    severity: concern" in md
        assert "    category: error-handling" in md
        assert '    summary: "Missing error handling"' in md

    def test_finding_with_location(self) -> None:
        result = _make_result_with_structured_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        assert '    location: "src/foo.py:10"' in md

    def test_finding_without_location_omits_field(self) -> None:
        result = _make_result_with_structured_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        # Second finding (F002) has no location — check it's not emitted
        lines = md.split("\n")
        f002_idx = next(i for i, line in enumerate(lines) if "id: F002" in line)
        # Lines between F002 and the closing --- should not have location
        f002_block = []
        for line in lines[f002_idx:]:
            if line.strip() == "---":
                break
            if line.startswith("  - id:") and "F002" not in line:
                break
            f002_block.append(line)
        assert not any("location:" in entry for entry in f002_block)

    def test_summary_with_double_quotes_escaped(self) -> None:
        result = ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title='Variable "x" unclear',
                    description="Rename it.",
                    category="naming",
                ),
            ],
            raw_output="raw",
            template_name="code",
            input_files={},
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            model="opus",
        )
        md = format_review_markdown(result, "code", SLICE_INFO)
        assert r'summary: "Variable \"x\" unclear"' in md

    def test_frontmatter_is_valid_yaml(self) -> None:
        result = _make_result_with_structured_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        # Extract frontmatter between --- markers
        parts = md.split("---")
        frontmatter_text = parts[1]
        data = yaml.safe_load(frontmatter_text)
        assert data["docType"] == "review"
        assert data["verdict"] == "CONCERNS"
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) == 2
        assert data["findings"][0]["id"] == "F001"
        assert data["findings"][0]["severity"] == "concern"

    def test_no_findings_block_when_empty(self) -> None:
        result = _make_result_no_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        assert "findings:" not in md

    def test_prose_body_unchanged(self) -> None:
        result = _make_result_with_structured_findings()
        md = format_review_markdown(result, "code", SLICE_INFO)
        assert "### [CONCERN] Missing error handling" in md
        assert "### [NOTE] Variable name unclear" in md


class TestYamlEscape:
    """Test yaml_escape helper."""

    def test_escapes_double_quotes(self) -> None:
        assert yaml_escape('hello "world"') == 'hello \\"world\\"'

    def test_no_quotes_unchanged(self) -> None:
        assert yaml_escape("hello world") == "hello world"

    def test_escapes_backslash(self) -> None:
        assert yaml_escape("path\\to\\file") == "path\\\\to\\\\file"


class TestTerminalDegradedOutput:
    """A degraded parse must not read as a clean review in the terminal (issue #72)."""

    @staticmethod
    def _result(*, fallback_used: bool) -> ReviewResult:
        return ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[],
            raw_output="the model's prose findings live here",
            template_name="code",
            input_files={},
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            model="opus",
            fallback_used=fallback_used,
        )

    def test_degraded_review_does_not_claim_no_findings(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _display_terminal(self._result(fallback_used=True))
        out = capsys.readouterr().out
        assert "No specific findings" not in out
        assert "degraded" in out.lower()

    def test_degraded_review_points_at_the_raw_response(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _display_terminal(self._result(fallback_used=True))
        assert "raw response" in capsys.readouterr().out.lower()

    def test_genuinely_clean_review_still_reports_no_findings(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _display_terminal(self._result(fallback_used=False))
        out = capsys.readouterr().out
        assert "No specific findings" in out
        assert "degraded" not in out.lower()

    def test_review_with_findings_is_never_marked_degraded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _display_terminal(_make_result_with_structured_findings())
        out = capsys.readouterr().out
        assert "Missing error handling" in out
        assert "degraded" not in out.lower()

    @staticmethod
    def _unknown_result() -> ReviewResult:
        """The other degraded parse: no verdict *and* no findings recovered.

        fallback_used stays False here — nothing was derived — so branching on it
        alone printed "No specific findings." for a review that parsed nothing.
        """
        return ReviewResult(
            verdict=Verdict.UNKNOWN,
            findings=[],
            raw_output="the model's unstructured prose",
            template_name="code",
            input_files={},
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            model="opus",
            fallback_used=False,
        )

    def test_genuinely_unknown_review_does_not_claim_no_findings(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _display_terminal(self._unknown_result())
        out = capsys.readouterr().out
        assert "No specific findings" not in out
        assert "degraded" in out.lower()

    def test_genuinely_unknown_review_points_at_the_raw_response(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _display_terminal(self._unknown_result())
        assert "raw response" in capsys.readouterr().out.lower()


class TestTerminalModelSubstitutionHeader:
    """Slice 927 C.9: the terminal header shows a substituted model (design D10)."""

    @staticmethod
    def _result(
        *, model: str, requested_model: str | None, answering_models: list[str]
    ) -> ReviewResult:
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="code",
            input_files={},
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            model=model,
        )
        result.requested_model = requested_model
        result.answering_models = answering_models
        return result

    def test_substituted_model_shows_requested_suffix(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = self._result(model="gpt-4.1", requested_model="gpt-5", answering_models=["gpt-4.1"])
        _display_terminal(result)
        out = capsys.readouterr().out
        assert "gpt-4.1" in out
        assert "(requested gpt-5)" in out

    def test_unsubstituted_model_shows_no_suffix(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = self._result(
            model="gpt-5-2025-08-07", requested_model="gpt-5", answering_models=["gpt-5-2025-08-07"]
        )
        _display_terminal(result)
        out = capsys.readouterr().out
        assert "requested" not in out.lower()


class TestDefaultSystemPromptPresetLine:
    """#85: the -vv appendix says the recorded prompt is only the appended part."""

    _PRESET_MARKER = "claude_code"

    def _result(self, *, preset_used: bool) -> ReviewResult:
        result = _make_result_no_findings()
        result.system_prompt = "Review the diff."
        result.user_prompt = "diff"
        result.default_system_prompt_preset_used = preset_used
        return result

    def test_preset_line_present_when_preset_was_used(self) -> None:
        md = format_review_markdown(self._result(preset_used=True), SLICE_INFO)

        assert self._PRESET_MARKER in md
        # It must annotate the recorded prompt, not float somewhere else.
        assert md.index("### System Prompt") < md.index(self._PRESET_MARKER)
        assert md.index(self._PRESET_MARKER) < md.index("Review the diff.")

    def test_no_preset_line_when_preset_was_not_used(self) -> None:
        md = format_review_markdown(self._result(preset_used=False), SLICE_INFO)

        assert self._PRESET_MARKER not in md
        assert "Review the diff." in md

    def test_no_appendix_means_no_preset_line(self) -> None:
        """A run below -vv captures no prompt, so there is nothing to annotate."""
        result = _make_result_no_findings()
        result.default_system_prompt_preset_used = True

        md = format_review_markdown(result, SLICE_INFO)

        assert self._PRESET_MARKER not in md


class TestTerminalToolTelemetry:
    """SC5: the three tool-use states stay distinct on the terminal, not just on disk."""

    @staticmethod
    def _result(
        *,
        tools_given: list[str] | None = None,
        tool_calls_made: int | None = None,
        suppressed_reason: str | None = None,
    ) -> ReviewResult:
        result = _make_result_no_findings()
        result.tools_given = tools_given
        result.tool_calls_made = tool_calls_made
        result.tools_suppressed_reason = suppressed_reason
        return result

    @staticmethod
    def _styles(result: ReviewResult, verbosity: int) -> list[tuple[str, object]]:
        """Return (text, style) for each console.print call, so style is assertable."""
        calls: list[tuple[str, object]] = []

        class _RecordingConsole:
            def print(self, *args: object, **kwargs: object) -> None:
                text = str(args[0]) if args else ""
                calls.append((text, kwargs.get("style")))

        with patch("squadron.cli.commands.review.Console", _RecordingConsole):
            _display_terminal(result, verbosity=verbosity)
        return calls

    def _tools_line(self, result: ReviewResult, verbosity: int = 1) -> tuple[str, object] | None:
        return next((call for call in self._styles(result, verbosity) if "Tools:" in call[0]), None)

    def test_tools_used_line_names_tools_and_count(self) -> None:
        line = self._tools_line(self._result(tools_given=["read_file", "grep"], tool_calls_made=12))

        assert line is not None
        assert "read_file, grep" in line[0]
        assert "12 calls" in line[0]

    def test_zero_calls_line_is_visibly_distinct(self) -> None:
        """The state that yields a confident verdict from a model that read nothing."""
        line = self._tools_line(self._result(tools_given=["read_file", "grep"], tool_calls_made=0))

        assert line is not None
        assert "offered, none used" in line[0]
        # Style, not only text: a dim line here reads as routine.
        assert line[1] == "bold yellow"

    def test_suppressed_line_states_the_reason(self) -> None:
        line = self._tools_line(self._result(suppressed_reason="run-suppressed"))

        assert line is not None
        assert "suppressed" in line[0]
        assert "run-suppressed" in line[0]

    def test_no_tools_line_at_verbosity_zero(self) -> None:
        assert (
            self._tools_line(self._result(tools_given=["read_file"], tool_calls_made=3), verbosity=0)
            is None
        )

    def test_no_tools_line_when_the_run_carried_no_telemetry(self) -> None:
        """Tools were never part of the run — say nothing rather than assert an absence."""
        assert self._tools_line(self._result()) is None
