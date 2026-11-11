"""fix_case_adapter_for: Python resolves, every other language raises (slice 422 D13)."""

from __future__ import annotations

import pytest

from squadron.benchmark.fairness import FixCaseAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.registry import UnsupportedLanguageError, fix_case_adapter_for
from squadron.metrology.snapshot_models import SourceLanguage


def test_python_returns_the_python_fix_case_adapter() -> None:
    # The annotation is checked by pyright (the registry's own return type is FixCaseAdapter).
    adapter: FixCaseAdapter = fix_case_adapter_for(SourceLanguage.PYTHON)
    assert isinstance(adapter, PythonFixCaseAdapter)
    assert adapter.language is SourceLanguage.PYTHON


@pytest.mark.parametrize(
    "language", [lang for lang in SourceLanguage if lang is not SourceLanguage.PYTHON]
)
def test_other_languages_raise_the_same_named_error(language: SourceLanguage) -> None:
    with pytest.raises(UnsupportedLanguageError, match=language.value):
        fix_case_adapter_for(language)


def test_the_python_adapter_has_every_protocol_method() -> None:
    adapter = fix_case_adapter_for(SourceLanguage.PYTHON)
    for name in (
        "is_test_side",
        "is_test_source",
        "lockfile_names",
        "collect",
        "overlay",
        "boundary",
        "trace",
        "grader_commands",
    ):
        assert callable(getattr(adapter, name)), name
