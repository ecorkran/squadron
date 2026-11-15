"""``grading_adapter_for``: a registered language resolves, any other raises (slice 425)."""

from __future__ import annotations

import logging

import pytest

from squadron.benchmark import registry
from squadron.benchmark.grading_adapter import GradingAdapter
from squadron.benchmark.registry import UnsupportedLanguageError, grading_adapter_for
from squadron.metrology.snapshot_models import SourceLanguage


class _StubGradingAdapter:
    language = SourceLanguage.PYTHON


def test_a_registered_language_resolves_to_a_fresh_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(registry._GRADING_ADAPTERS, SourceLanguage.PYTHON, _StubGradingAdapter)  # pyright: ignore[reportPrivateUsage]
    first = grading_adapter_for(SourceLanguage.PYTHON)
    assert isinstance(first, _StubGradingAdapter)
    assert grading_adapter_for(SourceLanguage.PYTHON) is not first


@pytest.mark.parametrize("language", list(SourceLanguage))
def test_an_unregistered_language_raises_naming_it_and_logs_error(
    language: SourceLanguage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delitem(registry._GRADING_ADAPTERS, language, raising=False)  # pyright: ignore[reportPrivateUsage]
    with caplog.at_level(logging.ERROR), pytest.raises(UnsupportedLanguageError, match=language.value):
        grading_adapter_for(language)
    assert any(r.levelno == logging.ERROR and language.value in r.getMessage() for r in caplog.records)


def test_the_protocol_names_every_design_method() -> None:
    names = {
        "restore_tool_config",
        "deps_changed",
        "test_side_edits",
        "restore_test_files",
        "inject_hidden",
        "count_suppressions",
    }
    assert names <= set(dir(GradingAdapter))
