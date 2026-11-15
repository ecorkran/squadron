"""Reviewer resolution (slice 425 Task 20, D7)."""

from __future__ import annotations

import logging

import pytest

from squadron.benchmark.grade_review import code_template_text, resolve_reviewer
from squadron.core.models import Effort
from squadron.models.aliases import ModelAlias, UnknownModelAliasError


@pytest.fixture
def aliases(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModelAlias]:
    table: dict[str, ModelAlias] = {
        "gpt-review": {"model": "gpt-x", "profile": "openai-oauth", "effort": Effort.high},
        "plain": {"model": "plain-model", "profile": "openrouter"},
    }
    monkeypatch.setattr("squadron.benchmark.grade_review.get_all_aliases", lambda: table)
    monkeypatch.setattr("squadron.models.aliases.get_all_aliases", lambda: table)
    return table


def test_a_known_alias_resolves_with_a_stable_template_hash(aliases: dict[str, ModelAlias]) -> None:
    first = resolve_reviewer("gpt-review", template_text=lambda: "review the diff")
    second = resolve_reviewer("gpt-review", template_text=lambda: "review the diff")
    assert (first.alias, first.model, first.profile) == ("gpt-review", "gpt-x", "openai-oauth")
    assert first.effort == "high"
    assert first.template_hash == second.template_hash
    assert first.reviewer_key == second.reviewer_key


def test_an_alias_without_effort_has_none(aliases: dict[str, ModelAlias]) -> None:
    assert resolve_reviewer("plain", template_text=lambda: "t").effort is None


def test_changing_the_template_text_changes_the_reviewer_key(
    aliases: dict[str, ModelAlias],
) -> None:
    before = resolve_reviewer("gpt-review", template_text=lambda: "review the diff")
    after = resolve_reviewer("gpt-review", template_text=lambda: "review the diff, carefully")
    assert before.template_hash != after.template_hash
    assert before.reviewer_key != after.reviewer_key


def test_an_unknown_alias_raises_naming_it_and_logs_error(
    aliases: dict[str, ModelAlias], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(UnknownModelAliasError, match="gpt-reveiw"):
        resolve_reviewer("gpt-reveiw", template_text=lambda: "t")
    assert any("gpt-reveiw" in record.getMessage() for record in caplog.records)


def test_the_real_code_template_text_is_available_and_non_empty() -> None:
    assert code_template_text().strip()
