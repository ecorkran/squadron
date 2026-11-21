"""Document reviews get the whole document in the prompt (#382)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

import squadron
from squadron.providers.base import AuthType, ProfileName, ProviderType
from squadron.providers.profiles import ProviderProfile
from squadron.review.document_injection import ReviewDocumentError, number_lines
from squadron.review.persistence import format_review_markdown
from squadron.review.review_client import (
    _inject_file_contents,  # pyright: ignore[reportPrivateUsage]
    run_review_with_profile,
)
from squadron.review.templates import ReviewTemplate, load_template
from tests.review.test_injection_decision import (
    _P,  # pyright: ignore[reportPrivateUsage]
    _capture_provider,  # pyright: ignore[reportPrivateUsage]
)

DOCUMENT_TEMPLATES = ("slice", "tasks", "arch", "judge-slice-vs-arch", "judge-tasks-vs-slice")
_BUILT_IN = Path(squadron.__file__).parent / "data" / "templates"
TASKS_BODY = "TASK FILE SENTINEL"
DESIGN_BODY = "SLICE DESIGN SENTINEL"


def _template(*, inject_documents: bool) -> ReviewTemplate:
    return ReviewTemplate(
        name="test",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=["read_file", "list_files", "grep"],
        permission_mode="bypassPermissions",
        setting_sources=[],
        required_inputs=[],
        optional_inputs=[],
        prompt_template="Review: {input} against {against}",
        inject_documents=inject_documents,
    )


async def _prompt(tmp_path: Path, *, sdk: bool, inject_documents: bool) -> str:
    (tmp_path / "tasks.md").write_text(TASKS_BODY)
    (tmp_path / "design.md").write_text(DESIGN_BODY)
    captured: dict[str, str] = {}
    provider = _capture_provider(captured, can_read_files=sdk)
    profile = (
        ProviderProfile(name=ProfileName.SDK, provider=ProviderType.SDK, auth_type=AuthType.SESSION)
        if sdk
        else ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")
    )
    with (
        patch(f"{_P}.get_profile", return_value=profile),
        patch(f"{_P}.get_provider", return_value=provider),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await run_review_with_profile(
            _template(inject_documents=inject_documents),
            {
                "input": str(tmp_path / "tasks.md"),
                "against": str(tmp_path / "design.md"),
                "cwd": str(tmp_path),
            },
            profile=profile.name,
        )
    return captured["prompt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("sdk", [True, False])
async def test_a_document_review_carries_both_documents_whatever_the_run_can_read(
    tmp_path: Path, sdk: bool
) -> None:
    prompt = await _prompt(tmp_path, sdk=sdk, inject_documents=True)
    assert TASKS_BODY in prompt and DESIGN_BODY in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("sdk", [True, False])
async def test_a_tool_enabled_review_without_the_flag_injects_as_before(
    tmp_path: Path, sdk: bool
) -> None:
    prompt = await _prompt(tmp_path, sdk=sdk, inject_documents=False)
    assert TASKS_BODY not in prompt and DESIGN_BODY not in prompt


def _tiny_caps(key: str, cwd: str = ".") -> int:
    return 10


def test_a_document_over_both_size_caps_is_injected_whole(tmp_path: Path) -> None:
    body = "line of the document\n" * 500
    (tmp_path / "tasks.md").write_text(body)
    inputs = {"input": str(tmp_path / "tasks.md"), "cwd": str(tmp_path)}
    with patch(f"{_P}.get_config", side_effect=_tiny_caps):
        result = _inject_file_contents("Review", inputs, include_bodies=False, whole_documents=True)
    assert result.prompt.count("line of the document") == 500
    assert "500\tline of the document" in result.prompt
    assert "truncated" not in result.prompt


def test_documents_are_injected_with_line_numbers() -> None:
    assert number_lines("first\n\nthird") == "1\tfirst\n2\t\n3\tthird"
    assert number_lines("\n".join("x" * 1 for _ in range(10))).splitlines()[0] == " 1\tx"


def test_the_injection_is_recorded_with_its_size_and_hash(tmp_path: Path) -> None:
    (tmp_path / "tasks.md").write_text(TASKS_BODY)
    inputs = {"input": str(tmp_path / "tasks.md"), "cwd": str(tmp_path)}
    (record,) = _inject_file_contents("Review", inputs, whole_documents=True).files
    assert (record.key, record.chars, record.whole) == ("input", len(TASKS_BODY), True)
    assert record.sha256 == hashlib.sha256(TASKS_BODY.encode()).hexdigest()
    assert record.path == str(tmp_path / "tasks.md")


def test_a_capped_file_is_recorded_as_cut(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("x" * 50)
    inputs = {"input": str(tmp_path / "notes.md"), "cwd": str(tmp_path)}

    def caps(key: str, cwd: str = ".") -> int:
        return 20 if key == "review.max_file_size_bytes" else 10_000

    with patch(f"{_P}.get_config", side_effect=caps):
        (record,) = _inject_file_contents("Review", inputs).files
    assert (record.chars, record.whole) == (50, False)


def test_a_document_path_relative_to_the_review_cwd_is_found(tmp_path: Path) -> None:
    (tmp_path / "tasks.md").write_text(TASKS_BODY)
    inputs = {"input": "tasks.md", "cwd": str(tmp_path)}
    result = _inject_file_contents("Review", inputs, include_bodies=False, whole_documents=True)
    assert TASKS_BODY in result.prompt


def test_a_missing_document_fails_the_review(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    inputs = {"input": str(tmp_path / "gone.md"), "cwd": str(tmp_path)}
    with pytest.raises(ReviewDocumentError, match="gone.md"):
        _inject_file_contents("Review", inputs, whole_documents=True)
    assert "is not a file" in caplog.text


@pytest.mark.parametrize("name", DOCUMENT_TEMPLATES)
def test_built_in_document_templates_inject_their_documents(name: str) -> None:
    assert load_template(_BUILT_IN / f"{name}.yaml").inject_documents is True


def test_the_code_template_does_not() -> None:
    assert load_template(_BUILT_IN / "code.yaml").inject_documents is False


@pytest.mark.asyncio
async def test_the_review_file_records_what_was_injected(tmp_path: Path) -> None:
    (tmp_path / "tasks.md").write_text(TASKS_BODY)
    (tmp_path / "design.md").write_text(DESIGN_BODY)
    provider = _capture_provider({}, can_read_files=True)
    profile = ProviderProfile(
        name=ProfileName.SDK, provider=ProviderType.SDK, auth_type=AuthType.SESSION
    )
    with (
        patch(f"{_P}.get_profile", return_value=profile),
        patch(f"{_P}.get_provider", return_value=provider),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await run_review_with_profile(
            _template(inject_documents=True),
            {
                "input": str(tmp_path / "tasks.md"),
                "against": str(tmp_path / "design.md"),
                "cwd": str(tmp_path),
            },
            profile=profile.name,
        )
    assert result.injected_files is not None
    assert [(item.key, item.whole) for item in result.injected_files] == [
        ("input", True),
        ("against", True),
    ]
    markdown = format_review_markdown(result, "tasks", project_name="demo")
    assert 'path: "tasks.md"' in markdown and 'path: "design.md"' in markdown
    # The mock agent stamps no tool-call record, and the file says so.
    assert "readRecord: unreported" in markdown


@pytest.mark.parametrize("name", ["tasks", "slice"])
def test_plan_and_design_reviews_check_what_the_document_breaks_in_existing_code(name: str) -> None:
    prompt = load_template(_BUILT_IN / f"{name}.yaml").system_prompt

    assert "open the existing code and tests that depend on it" in prompt
    assert "would break" in prompt


def test_the_conventions_file_is_in_the_read_record(tmp_path: Path) -> None:
    (tmp_path / "tasks.md").write_text(TASKS_BODY)
    (tmp_path / "AGENTS.md").write_text("# Rules\n\nNo silent fallbacks.\n")
    inputs = {"input": str(tmp_path / "tasks.md"), "cwd": str(tmp_path)}

    records = _inject_file_contents("Review", inputs, whole_documents=True).files

    conventions = next(record for record in records if record.key == "conventions")
    assert conventions.path == str(tmp_path / "AGENTS.md")
    assert conventions.whole is True
    assert conventions.sha256 == hashlib.sha256(b"# Rules\n\nNo silent fallbacks.\n").hexdigest()


def test_the_conventions_file_is_left_out_when_the_project_turns_it_off(tmp_path: Path) -> None:
    (tmp_path / "tasks.md").write_text(TASKS_BODY)
    (tmp_path / "AGENTS.md").write_text("CONVENTIONS SENTINEL\n")
    inputs = {"input": str(tmp_path / "tasks.md"), "cwd": str(tmp_path)}

    def config(key: str, cwd: str = ".") -> object:
        return False if key == "review.inject_conventions" else 500_000

    with patch(f"{_P}.get_config", side_effect=config):
        injected = _inject_file_contents("Review", inputs, whole_documents=True)

    assert "CONVENTIONS SENTINEL" not in injected.prompt
    assert [record.key for record in injected.files] == ["input"]
