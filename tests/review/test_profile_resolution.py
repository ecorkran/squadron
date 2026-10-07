"""Tests for the shared review-profile cascade."""

from __future__ import annotations

import pytest

from squadron.review.profile_resolution import (
    ReviewProfileSource,
    resolve_review_profile,
    review_profile_source,
)
from squadron.review.templates import ReviewTemplate

_CONFIG_PATH = "squadron.review.profile_resolution.get_config"


def _template(profile: str | None = None) -> ReviewTemplate:
    return ReviewTemplate(
        name="test",
        description="Test",
        system_prompt="Review.",
        allowed_tools=["Read"],
        permission_mode="bypassPermissions",
        setting_sources=[],
        required_inputs=[],
        optional_inputs=[],
        profile=profile,
        prompt_template="Review all.",
    )


def _set_config(monkeypatch: pytest.MonkeyPatch, value: object) -> None:
    def fake_get_config(key: str) -> object | None:
        return value if key == "default_review_profile" else None

    monkeypatch.setattr(_CONFIG_PATH, fake_get_config)


class TestResolveReviewProfile:
    def test_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, "cfg")
        choice = resolve_review_profile("flag", "alias", _template("tmpl"))
        assert (choice.name, choice.source) == ("flag", ReviewProfileSource.EXPLICIT)

    def test_alias_beats_template_and_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, "cfg")
        choice = resolve_review_profile(None, "alias", _template("tmpl"))
        assert (choice.name, choice.source) == ("alias", ReviewProfileSource.ALIAS)

    def test_template_beats_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, "cfg")
        choice = resolve_review_profile(None, None, _template("tmpl"))
        assert (choice.name, choice.source) == ("tmpl", ReviewProfileSource.TEMPLATE)

    def test_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, "cfg")
        choice = resolve_review_profile(None, None, _template())
        assert (choice.name, choice.source) == ("cfg", ReviewProfileSource.CONFIG)

    def test_template_none_falls_to_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, "cfg")
        choice = resolve_review_profile(None, None, None)
        assert choice.source is ReviewProfileSource.CONFIG

    def test_default_is_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, None)
        choice = resolve_review_profile(None, None, _template())
        assert (choice.name, choice.source) == ("sdk", ReviewProfileSource.DEFAULT)

    def test_non_string_config_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, 42)
        choice = resolve_review_profile(None, None, None)
        assert choice.source is ReviewProfileSource.DEFAULT


@pytest.mark.parametrize("explicit", [None, "flag"])
@pytest.mark.parametrize("template_profile", [None, "tmpl"])
@pytest.mark.parametrize("config", [None, "cfg"])
def test_source_flag_agrees_with_resolution(
    monkeypatch: pytest.MonkeyPatch,
    explicit: str | None,
    template_profile: str | None,
    config: str | None,
) -> None:
    """With no alias profile, the flag is True exactly when the source is not DEFAULT."""
    _set_config(monkeypatch, config)
    template = _template(template_profile)
    choice = resolve_review_profile(explicit, None, template)
    justified = review_profile_source(explicit is not None, template)
    assert justified == (
        choice.source
        in {
            ReviewProfileSource.EXPLICIT,
            ReviewProfileSource.TEMPLATE,
            ReviewProfileSource.CONFIG,
        }
    )


def test_alias_profile_alone_does_not_justify_literal_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_config(monkeypatch, None)
    template = _template()
    assert resolve_review_profile(None, "alias", template).source is ReviewProfileSource.ALIAS
    assert review_profile_source(False, template) is False


def test_review_profile_source_template_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, None)
    assert review_profile_source(False, None) is False
