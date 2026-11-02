"""Unit tests for DispatchStepType (T8 — slice 191)."""

from __future__ import annotations

import pytest

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.dispatch import DispatchStepType


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="dispatch", name="test-dispatch", config=config)


def _make() -> DispatchStepType:
    return DispatchStepType()


def test_step_type_name() -> None:
    assert _make().step_type == "dispatch"


def test_expand_with_prompt_and_model() -> None:
    actions = _make().expand(_step({"prompt": "Do something.", "model": "haiku"}))
    assert actions == [("dispatch", {"prompt": "Do something.", "model": "haiku"})]


def test_expand_prompt_only() -> None:
    actions = _make().expand(_step({"prompt": "Do something."}))
    assert actions == [("dispatch", {"prompt": "Do something."})]
    # model key should be absent — not injected as None
    assert "model" not in actions[0][1]


def test_expand_empty_config() -> None:
    actions = _make().expand(_step({}))
    assert actions == [("dispatch", {})]


def test_validate_prompt_non_string() -> None:
    errors = _make().validate(_step({"prompt": 42}))
    assert len(errors) == 1
    assert errors[0].field == "prompt"


def test_validate_model_non_string() -> None:
    errors = _make().validate(_step({"model": 99}))
    assert len(errors) == 1
    assert errors[0].field == "model"


def test_validate_valid_config() -> None:
    errors = _make().validate(_step({"prompt": "Go.", "model": "haiku"}))
    assert errors == []


def test_validate_empty_config() -> None:
    errors = _make().validate(_step({}))
    assert errors == []


def test_expand_forwards_pre_emption_fragment() -> None:
    """324: an opted-in fragment path threads through to the action config."""
    actions = _make().expand(_step({"prompt": "Do something.", "pre_emption_fragment": "/tmp/frag.md"}))
    assert actions == [
        ("dispatch", {"prompt": "Do something.", "pre_emption_fragment": "/tmp/frag.md"})
    ]


def test_validate_pre_emption_fragment_non_string() -> None:
    errors = _make().validate(_step({"pre_emption_fragment": 42}))
    assert len(errors) == 1
    assert errors[0].field == "pre_emption_fragment"


# --- allowed_tools validation (slice 263) ---


def test_validate_accepts_known_tools() -> None:
    errors = _make().validate(_step({"allowed_tools": ["read_file", "write_file"]}))
    assert errors == []


def test_validate_rejects_unknown_tool() -> None:
    errors = _make().validate(_step({"allowed_tools": ["read_fil"]}))
    assert len(errors) == 1
    assert errors[0].field == "allowed_tools"
    assert "read_fil" in errors[0].message
    assert errors[0].action_type == "dispatch"


def test_expand_forwards_allowed_tools() -> None:
    """263: declared tools thread through to the dispatch action config."""
    actions = _make().expand(_step({"prompt": "Do something.", "allowed_tools": ["write_file"]}))
    assert actions == [("dispatch", {"prompt": "Do something.", "allowed_tools": ["write_file"]})]


def test_expand_omits_allowed_tools_when_absent() -> None:
    actions = _make().expand(_step({"prompt": "Do something."}))
    assert "allowed_tools" not in actions[0][1]


# --- file and reply keys (slice 949 D1) ---


def _field_errors(config: dict[str, object]) -> list[str]:
    return [e.field for e in _make().validate(_step(config))]


def test_expand_forwards_all_file_and_reply_keys() -> None:
    config: dict[str, object] = {
        "prompt_files": ["a.md"],
        "reply_from": "earlier",
        "reply_format": "json",
        "reply_file": "out/reply.json",
        "delivered_prompt_file": "out/prompt.md",
    }
    assert _make().expand(_step(config)) == [("dispatch", config)]


def test_valid_file_and_reply_keys_pass() -> None:
    config: dict[str, object] = {
        "prompt": "p",
        "prompt_files": ["a.md", "dir/b.md"],
        "reply_from": "earlier",
        "reply_format": "text",
        "reply_file": "out/reply.json",
        "delivered_prompt_file": "out/prompt.md",
    }
    assert _make().validate(_step(config)) == []


def test_prompt_files_bare_string_is_rejected_with_a_list_hint() -> None:
    (error,) = _make().validate(_step({"prompt_files": "a.md"}))
    assert error.field == "prompt_files"
    assert "list" in error.message


def test_prompt_files_empty_list_is_rejected() -> None:
    assert _field_errors({"prompt_files": []}) == ["prompt_files"]


def test_prompt_files_non_string_entry_is_rejected() -> None:
    assert _field_errors({"prompt_files": ["a.md", 3]}) == ["prompt_files"]


def test_reply_format_must_be_a_known_value() -> None:
    assert _field_errors({"reply_format": "yaml"}) == ["reply_format"]


@pytest.mark.parametrize("key", ["prompt_files", "reply_file", "delivered_prompt_file"])
@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.md", "a/../../b.md"])
def test_unsafe_paths_are_rejected(key: str, path: str) -> None:
    value: object = [path] if key == "prompt_files" else path
    assert _field_errors({key: value}) == [key]


@pytest.mark.parametrize("key", ["prompt_files", "reply_file", "delivered_prompt_file"])
def test_placeholder_paths_skip_the_load_time_check(key: str) -> None:
    value: object = ["{dir}/../x.md"] if key == "prompt_files" else "{dir}/../x.md"
    assert _field_errors({key: value}) == []


def test_reply_and_prompt_output_files_must_differ() -> None:
    assert _field_errors({"reply_file": "same.md", "delivered_prompt_file": "same.md"}) == [
        "reply_file"
    ]


def test_reply_from_must_be_a_non_empty_string() -> None:
    assert _field_errors({"reply_from": ""}) == ["reply_from"]
    assert _field_errors({"reply_from": 4}) == ["reply_from"]


@pytest.mark.parametrize("key", ["prompt_files", "reply_from"])
def test_feedback_cannot_combine_with_another_prompt_source(key: str) -> None:
    value: object = ["a.md"] if key == "prompt_files" else "earlier"
    assert _field_errors({"feedback": "review", key: value}) == ["feedback"]
