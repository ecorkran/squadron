"""Tests for format_review_markdown YAML frontmatter alignment (T14/T15)."""

from __future__ import annotations

from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import SliceInfo, format_review_markdown


def _make_result(model: str | None = "claude-opus-4-5") -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="slice",
        input_files={"input": "design.md"},
        model=model,
    )


def _make_slice_info() -> SliceInfo:
    return SliceInfo(
        index=122,
        name="review-context-enrichment",
        slice_name="review-context-enrichment",
        design_file="project-documents/user/slices/122-slice.md",
        task_files=["122-tasks.review-context-enrichment.md"],
        arch_file="project-documents/user/architecture/100-arch.md",
    )


class TestFormatReviewMarkdown:
    """Test YAML frontmatter fields in format_review_markdown."""

    def test_has_layer_field(self) -> None:
        output = format_review_markdown(_make_result(), "slice", _make_slice_info())
        assert "layer: project" in output

    def test_has_source_document(self) -> None:
        output = format_review_markdown(
            _make_result(),
            "slice",
            _make_slice_info(),
            source_document="project-documents/user/slices/122-slice.md",
        )
        assert "sourceDocument:" in output
        assert "122-slice.md" in output

    def test_has_ai_model(self) -> None:
        output = format_review_markdown(
            _make_result(model="claude-opus-4-5"),
            "slice",
            _make_slice_info(),
        )
        assert "aiModel: claude-opus-4-5" in output

    def test_has_status(self) -> None:
        output = format_review_markdown(_make_result(), "slice", _make_slice_info())
        assert "status: complete" in output

    def test_model_unknown_when_none(self) -> None:
        output = format_review_markdown(
            _make_result(model=None), "slice", _make_slice_info()
        )
        assert "aiModel: unknown" in output

    def test_source_document_falls_back_to_design_file(self) -> None:
        """When input_file not provided, uses slice_info design_file."""
        output = format_review_markdown(
            _make_result(), "slice", _make_slice_info(), source_document=None
        )
        assert "sourceDocument:" in output


# ---------------------------------------------------------------------------
# T14: Debug appendix tests
# ---------------------------------------------------------------------------


class TestDebugAppendix:
    """Tests for debug appendix in format_review_markdown."""

    def test_appendix_present_when_prompt_fields_set(self) -> None:
        result = _make_result()
        result.system_prompt = "You are a reviewer."
        result.user_prompt = "Review this."
        output = format_review_markdown(result, "slice", _make_slice_info())
        assert "## Debug: Prompt & Response" in output

    def test_appendix_absent_when_prompt_fields_none(self) -> None:
        result = _make_result()
        output = format_review_markdown(result, "slice", _make_slice_info())
        assert "## Debug: Prompt & Response" not in output

    def test_appendix_shows_rules_none_when_no_rules(self) -> None:
        result = _make_result()
        result.system_prompt = "You are a reviewer."
        result.user_prompt = "Review this."
        result.rules_content_used = None
        output = format_review_markdown(result, "slice", _make_slice_info())
        assert "### Rules Injected" in output
        assert "\nNone\n" in output

    def test_appendix_contains_raw_output(self) -> None:
        result = _make_result()
        result.system_prompt = "You are a reviewer."
        result.user_prompt = "Review this."
        result.raw_output = "## Summary\nPASS\nAll good."
        output = format_review_markdown(result, "slice", _make_slice_info())
        assert "### Raw Response" in output
        assert "All good." in output
