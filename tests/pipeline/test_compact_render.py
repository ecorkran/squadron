"""Tests for squadron.pipeline.compact_render helpers."""

from __future__ import annotations

from squadron.pipeline.compact_render import LenientDict, render_with_params


class TestLenientDict:
    def test_missing_key_returns_placeholder(self) -> None:
        d = LenientDict()
        assert d["missing"] == "{missing}"

    def test_present_key_returns_value(self) -> None:
        d = LenientDict(slice="157")
        assert d["slice"] == "157"


class TestRenderWithParams:
    def test_substitutes_present_param(self) -> None:
        assert render_with_params("Hello {name}", {"name": "world"}) == "Hello world"

    def test_preserves_missing_placeholder(self) -> None:
        assert render_with_params("Slice {slice}", {}) == "Slice {slice}"

    def test_mixed_present_and_missing(self) -> None:
        result = render_with_params("Slice {slice}, phase {phase}", {"slice": "157"})
        assert result == "Slice 157, phase {phase}"

    def test_empty_instructions(self) -> None:
        assert render_with_params("", {"slice": "157"}) == ""

    def test_non_string_param_value_coerced_by_format_map(self) -> None:
        # int values are stringified by Python's format protocol
        assert render_with_params("n={n}", {"n": 42}) == "n=42"
