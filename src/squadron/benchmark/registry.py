"""Adapter registry: the only importer of concrete benchmark adapters (slice 421 D9)."""

from __future__ import annotations

from squadron.benchmark.adapter import BenchmarkAdapter
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.metrology.snapshot_models import SourceLanguage


class UnsupportedLanguageError(Exception):
    """No benchmark adapter exists for the language."""

    def __init__(self, language: SourceLanguage) -> None:
        super().__init__(f"no benchmark adapter for language '{language.value}'")
        self.language = language


def adapter_for(language: SourceLanguage) -> BenchmarkAdapter:
    """The adapter for ``language``; any language without one raises a named error."""
    if language is SourceLanguage.PYTHON:
        return PythonBenchmarkAdapter()
    raise UnsupportedLanguageError(language)
