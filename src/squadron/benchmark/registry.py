"""Adapter registry: the only importer of concrete benchmark adapters (slice 421 D9)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from squadron.benchmark.adapter import BenchmarkAdapter
from squadron.benchmark.fairness import FixCaseAdapter
from squadron.benchmark.grading_adapter import GradingAdapter
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.python_grading import PythonGradingAdapter
from squadron.metrology.snapshot_models import SourceLanguage

_logger = logging.getLogger(__name__)


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


def fix_case_adapter_for(language: SourceLanguage) -> FixCaseAdapter:
    """The fix-case (fairness) adapter for ``language``; any language without one raises."""
    if language is SourceLanguage.PYTHON:
        return PythonFixCaseAdapter()
    raise UnsupportedLanguageError(language)


#: Grading adapters by language (slice 425). Each entry is a factory, so every lookup
#: returns a fresh adapter.
_GRADING_ADAPTERS: dict[SourceLanguage, Callable[[], GradingAdapter]] = {
    SourceLanguage.PYTHON: PythonGradingAdapter,
}


def grading_adapter_for(language: SourceLanguage) -> GradingAdapter:
    """The grading adapter for ``language``; a language with none is logged and raises."""
    factory = _GRADING_ADAPTERS.get(language)
    if factory is None:
        _logger.error("no grading adapter registered for language '%s'", language.value)
        raise UnsupportedLanguageError(language)
    return factory()
