"""Tests for the T1 hash-narrowing fix (322).

`_template_content_hash` must exclude the `judge:` threshold block so that
acting on a calibration recommendation (editing pass_floor/concerns_floor)
does not re-key the config and reset accumulated evidence to zero. A prompt
or model edit must still re-key, since that changes the judged instrument.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from squadron.metrology import identity
from squadron.metrology.identity import derive_judge_config_id
from squadron.review.templates import ReviewTemplate, clear_registry, register_template


def _make_template(
    *,
    name: str = "judge.example",
    system_prompt: str = "You are a judge.",
    model: str = "minimax/minimax-m2.7",
    judge: dict[str, object] | None = None,
) -> ReviewTemplate:
    return ReviewTemplate(
        name=name,
        description="Example judge template",
        system_prompt=system_prompt,
        allowed_tools=[],
        permission_mode="default",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        model=model,
        prompt_template="Judge this: {input}",
        judge=judge if judge is not None else {"pass_floor": 78, "concerns_floor": 55},
    )


@pytest.fixture(autouse=True)
def _clear_template_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    clear_registry()
    yield
    clear_registry()


class TestTemplateContentHashExcludesThresholds:
    def test_threshold_only_edit_does_not_rekey(self) -> None:
        register_template(_make_template(judge={"pass_floor": 78, "concerns_floor": 55}))
        hash_a = identity._template_content_hash("judge.example")  # pyright: ignore[reportPrivateUsage]

        clear_registry()
        register_template(_make_template(judge={"pass_floor": 85, "concerns_floor": 55}))
        hash_b = identity._template_content_hash("judge.example")  # pyright: ignore[reportPrivateUsage]

        assert hash_a is not None
        assert hash_a == hash_b

    def test_system_prompt_edit_rekeys(self) -> None:
        register_template(_make_template(system_prompt="You are a judge."))
        hash_a = identity._template_content_hash("judge.example")  # pyright: ignore[reportPrivateUsage]

        clear_registry()
        register_template(_make_template(system_prompt="You are a different judge."))
        hash_b = identity._template_content_hash("judge.example")  # pyright: ignore[reportPrivateUsage]

        assert hash_a != hash_b

    def test_model_edit_rekeys(self) -> None:
        register_template(_make_template(model="minimax/minimax-m2.7"))
        hash_a = identity._template_content_hash("judge.example")  # pyright: ignore[reportPrivateUsage]

        clear_registry()
        register_template(_make_template(model="anthropic/claude-sonnet-5"))
        hash_b = identity._template_content_hash("judge.example")  # pyright: ignore[reportPrivateUsage]

        assert hash_a != hash_b

    def test_missing_template_returns_none(self) -> None:
        assert identity._template_content_hash("no.such.template") is None  # pyright: ignore[reportPrivateUsage]


class TestDeriveJudgeConfigIdEndToEnd:
    def test_threshold_only_edit_leaves_config_id_unchanged(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        register_template(_make_template(judge={"pass_floor": 78, "concerns_floor": 55}))
        review_file = write_review_file(tmp_path, review_type="judge.example")
        config_id_a = derive_judge_config_id(review_file)

        clear_registry()
        register_template(_make_template(judge={"pass_floor": 90, "concerns_floor": 55}))
        config_id_b = derive_judge_config_id(review_file)

        assert config_id_a.template_content_hash is not None
        assert config_id_a.template_content_hash == config_id_b.template_content_hash

    def test_system_prompt_edit_rekeys_config_id(
        self, tmp_path: Path, write_review_file: Callable[..., Path]
    ) -> None:
        register_template(_make_template(system_prompt="You are a judge."))
        review_file = write_review_file(tmp_path, review_type="judge.example")
        config_id_a = derive_judge_config_id(review_file)

        clear_registry()
        register_template(_make_template(system_prompt="You are a rewritten judge."))
        config_id_b = derive_judge_config_id(review_file)

        assert config_id_a.template_content_hash != config_id_b.template_content_hash
