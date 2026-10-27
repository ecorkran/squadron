"""Tests for cf adoption report parsing (slice 440 D5–D8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from squadron.config.keys import CF_CLI_TIMEOUT_KEY, get_default
from squadron.integrations.cf_adoption import (
    ADOPTION_PROMPT_KEY,
    ADOPTION_STATE_DECLINED,
    ADOPTION_STATE_KEY,
    AdoptionOutcome,
    CfAdoptionClient,
    ContextForgeReportError,
    parse_detect_report,
    parse_init_report,
)
from squadron.integrations.context_forge import ContextForgeError
from tests.fixtures.cf_adoption import fixture_text, load_fixture


def _fixture(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", load_fixture(name))


class TestParseDetectReport:
    @pytest.mark.parametrize("outcome", list(AdoptionOutcome))
    def test_each_outcome_parses(self, outcome: AdoptionOutcome) -> None:
        data = _fixture(f"detect-{outcome.value}")
        report = parse_detect_report(data)
        assert report.outcome is outcome
        assert report.notices == tuple(data["notices"])

    def test_artifacts_are_read(self) -> None:
        artifacts = parse_detect_report(_fixture("detect-already-planned")).artifacts
        assert artifacts.concept == "project-documents/user/project-guides/000-concept.example.md"
        assert artifacts.derived_architectures == (
            "project-documents/user/architecture/100-arch.example.md",
        )
        assert artifacts.existing_state_plan is not None

    def test_absent_artifacts_are_none(self) -> None:
        artifacts = parse_detect_report(_fixture("detect-brownfield")).artifacts
        assert artifacts.concept is None
        assert artifacts.existing_state_plan is None
        assert artifacts.derived_architectures == ()

    def test_unknown_outcome_raises_naming_it(self) -> None:
        data = _fixture("detect-brownfield")
        data["outcome"] = "half-adopted"
        with pytest.raises(ContextForgeError, match="half-adopted"):
            parse_detect_report(data)

    def test_missing_field_raises_naming_it(self) -> None:
        data = _fixture("detect-brownfield")
        del data["notices"]
        with pytest.raises(ContextForgeError, match="'notices'"):
            parse_detect_report(data)


class TestErrorEnvelope:
    @pytest.mark.parametrize(
        ("fixture", "parse", "command"),
        [
            ("detect-error-path-not-found", parse_detect_report, "detect"),
            ("init-error-worktree", parse_init_report, "init"),
        ],
    )
    def test_envelope_raises_report_error(self, fixture: str, parse: Any, command: str) -> None:
        envelope = _fixture(fixture)
        error = envelope["error"]
        with pytest.raises(ContextForgeReportError) as caught:
            parse(envelope)
        assert caught.value.code == error["code"]
        assert caught.value.message == error["message"]
        assert str(caught.value) == f"cf {command}: {error['code']}: {error['message']}"

    def test_malformed_error_object_raises(self) -> None:
        with pytest.raises(ContextForgeError, match="malformed error object"):
            parse_detect_report({"reportVersion": 1, "error": "oops"})


class TestReportVersion:
    @pytest.mark.parametrize("parse", [parse_detect_report, parse_init_report])
    def test_unknown_version_raises_naming_it(self, parse: Any) -> None:
        with pytest.raises(ContextForgeError, match=r"reportVersion 2"):
            parse({"reportVersion": 2})

    @pytest.mark.parametrize("parse", [parse_detect_report, parse_init_report])
    def test_missing_version_raises(self, parse: Any) -> None:
        with pytest.raises(ContextForgeError, match="reportVersion missing"):
            parse({"outcome": "brownfield"})

    @pytest.mark.parametrize(
        ("fixture", "parse"),
        [
            ("detect-error-path-not-found", parse_detect_report),
            ("init-error-worktree", parse_init_report),
        ],
    )
    def test_version_is_checked_before_the_envelope(self, fixture: str, parse: Any) -> None:
        data = _fixture(fixture)
        data["reportVersion"] = 2
        with pytest.raises(ContextForgeError, match="reportVersion 2") as caught:
            parse(data)
        assert not isinstance(caught.value, ContextForgeReportError)


class TestParseInitReport:
    def test_created_registration(self) -> None:
        report = parse_init_report(_fixture("init-ok"))
        assert report.ok is True
        assert report.registration == "created"
        assert report.project_name == "fixture-project"
        assert [s.step for s in report.steps][:2] == ["git", "register"]

    def test_existing_registration(self) -> None:
        assert parse_init_report(_fixture("init-existing")).registration == "existing"

    def test_failed_step_is_a_report_not_an_error(self) -> None:
        report = parse_init_report(_fixture("init-failed-step"))
        assert report.ok is False
        failed = [s for s in report.steps if s.status == "failed"]
        assert [(s.step, s.message) for s in failed] == [
            (
                "ide",
                "Invalid target 'bogus'. Valid targets: claude, copilot, cursor, agents "
                "(aliases: openai, codex → agents)",
            )
        ]


# ---------------------------------------------------------------------------
# CfAdoptionClient — exact argv, cwd and timeout per cf call
# ---------------------------------------------------------------------------

_TIMEOUT_S = 42


def _completed(stdout: str, returncode: int = 0) -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = ""
    result.returncode = returncode
    return result


@pytest.fixture
def client() -> CfAdoptionClient:
    return CfAdoptionClient(timeout_s=_TIMEOUT_S)


class TestCfAdoptionClient:
    def test_detect_argv_and_report(self, client: CfAdoptionClient, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(fixture_text("detect-brownfield"))) as run:
            report = client.detect(tmp_path)
        assert run.call_args.args[0] == ["cf", "detect", "--path", str(tmp_path), "--json"]
        assert run.call_args.kwargs["cwd"] is None
        assert run.call_args.kwargs["timeout"] == _TIMEOUT_S
        assert report.outcome is AdoptionOutcome.BROWNFIELD

    def test_detect_error_envelope_raises(self, client: CfAdoptionClient, tmp_path: Path) -> None:
        stdout = fixture_text("detect-error-path-not-found")
        with patch("subprocess.run", return_value=_completed(stdout, returncode=1)):
            with pytest.raises(ContextForgeReportError, match="path-not-found"):
                client.detect(tmp_path)

    def test_is_registered_matches_exact_project_path(
        self, client: CfAdoptionClient, tmp_path: Path
    ) -> None:
        listing = json.dumps(
            [
                {"name": "here", "projectPath": str(tmp_path / "sub" / "..")},
                {"name": "no-path"},
                {"name": "elsewhere", "projectPath": str(tmp_path / "other")},
            ]
        )
        with patch("subprocess.run", return_value=_completed(listing)) as run:
            assert client.is_registered(tmp_path) is True
        assert run.call_args.args[0] == ["cf", "project", "list", "--json"]
        assert run.call_args.kwargs["timeout"] == _TIMEOUT_S

    def test_is_registered_is_false_for_a_subdirectory_of_a_registered_root(
        self, client: CfAdoptionClient, tmp_path: Path
    ) -> None:
        listing = json.dumps([{"name": "parent", "projectPath": str(tmp_path)}])
        with patch("subprocess.run", return_value=_completed(listing)):
            assert client.is_registered(tmp_path / "sub") is False

    def test_is_registered_ignores_entries_without_a_path(
        self, client: CfAdoptionClient, tmp_path: Path
    ) -> None:
        listing = fixture_text("project-list")
        with patch("subprocess.run", return_value=_completed(listing)):
            assert client.is_registered(tmp_path) is False

    def test_is_registered_rejects_non_list_output(
        self, client: CfAdoptionClient, tmp_path: Path
    ) -> None:
        with patch("subprocess.run", return_value=_completed("{}")):
            with pytest.raises(ContextForgeError, match="not a list"):
                client.is_registered(tmp_path)

    @pytest.mark.parametrize(("ide", "expected_tail"), [(None, []), ("agents", ["--ide", "agents"])])
    def test_init_project_argv_and_cwd(
        self, client: CfAdoptionClient, tmp_path: Path, ide: str | None, expected_tail: list[str]
    ) -> None:
        with patch("subprocess.run", return_value=_completed(fixture_text("init-ok"))) as run:
            report = client.init_project(tmp_path, ide)
        assert run.call_args.args[0] == ["cf", "init", "--json", *expected_tail]
        assert run.call_args.kwargs["cwd"] == tmp_path
        assert run.call_args.kwargs["timeout"] == _TIMEOUT_S
        assert report.ok

    def test_init_project_failed_step_is_returned_not_raised(
        self, client: CfAdoptionClient, tmp_path: Path
    ) -> None:
        stdout = fixture_text("init-failed-step")
        with patch("subprocess.run", return_value=_completed(stdout, returncode=1)):
            assert client.init_project(tmp_path, None).ok is False

    def test_init_project_worktree_error_raises(self, client: CfAdoptionClient, tmp_path: Path) -> None:
        stdout = fixture_text("init-error-worktree")
        with patch("subprocess.run", return_value=_completed(stdout, returncode=1)):
            with pytest.raises(ContextForgeReportError, match="worktree-of-registered-project"):
                client.init_project(tmp_path, None)

    def test_decline_argv_and_cwd(self, client: CfAdoptionClient, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed("")) as run:
            client.decline(tmp_path)
        assert run.call_args.args[0] == [
            "cf",
            "config",
            "set",
            ADOPTION_STATE_KEY,
            ADOPTION_STATE_DECLINED,
            "--project",
            str(tmp_path),
        ]
        assert run.call_args.kwargs["cwd"] == tmp_path

    def test_adoption_prompt_uses_absolute_doc_path_and_returns_stdout(
        self, client: CfAdoptionClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with patch("subprocess.run", return_value=_completed("PROMPT\n\ntext\n")) as run:
            text = client.adoption_prompt(tmp_path, Path("doc.md"))
        assert run.call_args.args[0] == [
            "cf",
            "prompt",
            "get",
            ADOPTION_PROMPT_KEY,
            "--path",
            str(tmp_path),
            "--comprehension",
            str((tmp_path / "doc.md").resolve()),
        ]
        assert text == "PROMPT\n\ntext\n"

    def test_from_config_uses_cf_cli_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(fixture_text("init-ok"))) as run:
            CfAdoptionClient.from_config(str(tmp_path)).init_project(tmp_path, None)
        assert run.call_args.kwargs["timeout"] == get_default(CF_CLI_TIMEOUT_KEY)
