"""adapter_for: Python resolves, every other language raises."""

from __future__ import annotations

import pytest

from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.registry import UnsupportedLanguageError, adapter_for
from squadron.metrology.snapshot_models import SourceLanguage


def test_python_returns_the_python_adapter() -> None:
    adapter = adapter_for(SourceLanguage.PYTHON)
    assert isinstance(adapter, PythonBenchmarkAdapter)
    assert adapter.language is SourceLanguage.PYTHON


@pytest.mark.parametrize(
    "language", [lang for lang in SourceLanguage if lang is not SourceLanguage.PYTHON]
)
def test_other_languages_raise(language: SourceLanguage) -> None:
    with pytest.raises(UnsupportedLanguageError, match=language.value):
        adapter_for(language)
