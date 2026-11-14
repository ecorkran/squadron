"""Tests for the packaged fix prompt and its substitution (slice 423 D8)."""

from __future__ import annotations

import re

from squadron.data import data_dir
from squadron.pipeline.fix_issue import (
    FIX_PROMPT_PATH,
    ISSUE_NUMBER_PLACEHOLDER,
    ISSUE_TEXT_PLACEHOLDER,
    render_fix_prompt,
)


def _template() -> str:
    return data_dir().joinpath(*FIX_PROMPT_PATH).read_text(encoding="utf-8")


def test_template_holds_only_the_two_placeholders() -> None:
    template = _template()
    assert re.findall(r"\{[^}]*\}", template) == [ISSUE_NUMBER_PLACEHOLDER, ISSUE_TEXT_PLACEHOLDER]
    assert template.count("{") == 2
    assert template.count("}") == 2
    assert '{"' not in template


def test_both_substitutions_land() -> None:
    prompt = render_fix_prompt(301, "The parser drops the last row.")
    assert "# Fix issue #301" in prompt
    assert "The parser drops the last row." in prompt
    assert ISSUE_NUMBER_PLACEHOLDER not in prompt
    assert ISSUE_TEXT_PLACEHOLDER not in prompt


def test_issue_text_is_placed_between_the_markers() -> None:
    prompt = render_fix_prompt(7, "marker check")
    begin = prompt.index("BEGIN ISSUE TEXT")
    end = prompt.index("END ISSUE TEXT")
    assert begin < prompt.index("marker check") < end


def test_braces_and_placeholders_in_the_issue_text_stay_verbatim() -> None:
    issue = 'config is {"a": {"b": 1}} and the literal {issue_number} and {issue_text} and {0}'
    prompt = render_fix_prompt(301, issue)
    assert issue in prompt
    assert prompt.count("301") == 1
