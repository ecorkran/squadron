"""Tests for ContextForgeClient — typed interface to cf CLI."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_completed(stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a mock CompletedProcess."""
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = 0
    return cp


# ---------------------------------------------------------------------------
# T3 — Client core and is_available()
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_is_available_true(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed("cf 1.0.0")):
            assert ContextForgeClient().is_available() is True

    def test_is_available_false(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert ContextForgeClient().is_available() is False


class TestRun:
    def test_run_cf_not_installed(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ContextForgeNotAvailable):
                ContextForgeClient()._run(["--version"])

    def test_run_cf_command_error(self) -> None:
        exc = subprocess.CalledProcessError(1, "cf", stderr="bad arg")
        with patch("subprocess.run", side_effect=exc):
            with pytest.raises(ContextForgeError, match="bad arg"):
                ContextForgeClient()._run(["bad", "command"])

    def test_run_returns_stdout(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed("hello")):
            assert ContextForgeClient()._run(["--version"]) == "hello"


class TestRunJson:
    def test_run_json_valid(self) -> None:
        payload = {"key": "value"}
        with patch("subprocess.run", return_value=_mock_completed(json.dumps(payload))):
            assert ContextForgeClient()._run_json(["get", "--json"]) == payload

    def test_run_json_invalid(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed("not json")):
            with pytest.raises(ContextForgeError, match="invalid JSON"):
                ContextForgeClient()._run_json(["get", "--json"])


# ---------------------------------------------------------------------------
# T5 — list_slices()
# ---------------------------------------------------------------------------

_SLICES_JSON = {
    "entries": [
        {
            "index": 100,
            "name": "Project Setup",
            "designFile": "project-documents/user/slices/100-slice.project-setup.md",
            "status": "complete",
        },
        {
            "index": 101,
            "name": "SDK Agent Provider",
            "status": "complete",
        },
    ]
}


class TestListSlices:
    def test_list_slices_parses_entries(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed(json.dumps(_SLICES_JSON))):
            slices = ContextForgeClient().list_slices()
            assert len(slices) == 2
            assert slices[0].index == 100
            assert slices[0].name == "Project Setup"
            assert slices[0].design_file == "project-documents/user/slices/100-slice.project-setup.md"
            assert slices[0].status == "complete"

    def test_list_slices_missing_design_file(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed(json.dumps(_SLICES_JSON))):
            slices = ContextForgeClient().list_slices()
            assert slices[1].design_file is None

    def test_list_slices_empty(self) -> None:
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps({"entries": []})),
        ):
            assert ContextForgeClient().list_slices() == []


# ---------------------------------------------------------------------------
# T7 — list_tasks()
# ---------------------------------------------------------------------------

_TASKS_JSON = [
    {"index": 100, "files": ["100-tasks.project-setup.md"]},
    {"index": 101},
]


class TestListTasks:
    def test_list_tasks_parses_entries(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed(json.dumps(_TASKS_JSON))):
            tasks = ContextForgeClient().list_tasks()
            assert len(tasks) == 2
            assert tasks[0].index == 100
            assert tasks[0].files == ["100-tasks.project-setup.md"]

    def test_list_tasks_no_files(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed(json.dumps(_TASKS_JSON))):
            tasks = ContextForgeClient().list_tasks()
            assert tasks[1].files == []

    def test_list_tasks_empty(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed(json.dumps([]))):
            assert ContextForgeClient().list_tasks() == []


# ---------------------------------------------------------------------------
# T9 — get_project()
# ---------------------------------------------------------------------------

_PROJECT_JSON = {
    "name": "squadron",
    "fileArch": "100-arch.orchestration-v2",
    "fileSlicePlan": "100-slices.orchestration-v2",
    "developmentPhase": "Phase 6: Implementation",
    "fileSlice": "126-slice.context-forge-integration-layer",
}


class TestGetProject:
    def test_get_project_parses_fields(self) -> None:
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(_PROJECT_JSON)),
        ):
            info = ContextForgeClient().get_project()
            assert info.slice_plan == "100-slices.orchestration-v2"
            assert info.phase == "Phase 6: Implementation"
            # fileSlice="126-slice.context-forge-..." → slice="126"
            assert info.slice == "126"

    def test_get_project_slice_fallback_when_no_leading_digits(self) -> None:
        data = {**_PROJECT_JSON, "fileSlice": "custom-slice-name"}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            info = ContextForgeClient().get_project()
            # No leading digits → full stem returned as graceful fallback
            assert info.slice == "custom-slice-name"

    def test_get_project_slice_empty_when_no_fileSlice(self) -> None:
        data = {k: v for k, v in _PROJECT_JSON.items() if k != "fileSlice"}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            info = ContextForgeClient().get_project()
            assert info.slice == ""

    def test_get_project_arch_path_resolution(self) -> None:
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(_PROJECT_JSON)),
        ):
            info = ContextForgeClient().get_project()
            assert info.arch_file == (
                "project-documents/user/architecture/100-arch.orchestration-v2.md"
            )

    def test_get_project_arch_already_has_md(self) -> None:
        data = {**_PROJECT_JSON, "fileArch": "custom/path/arch.md"}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            info = ContextForgeClient().get_project()
            assert info.arch_file == "custom/path/arch.md"


#: Real ``cf config get git.integration_branch --json`` output, captured from
#: the CLI on a repo with the key unset. Description truncated for width; the
#: shape (key/value/source/description) is verbatim.
_CONFIG_UNSET_JSON = {
    "key": "git.integration_branch",
    "value": "",
    "source": "default",
    "description": "Optional long-lived integration branch that work branches "
    "fork from and merge into instead of main.",
}


class TestGetConfig:
    def test_get_config_returns_set_value(self) -> None:
        data = {**_CONFIG_UNSET_JSON, "value": "dev/erik", "source": "project"}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ) as run_mock:
            value = ContextForgeClient().get_config("git.integration_branch")

        assert value == "dev/erik"
        argv = run_mock.call_args[0][0]
        assert argv == ["cf", "config", "get", "git.integration_branch", "--json"]

    def test_get_config_unset_key_returns_empty_string(self) -> None:
        """An optional key CF reports as source=default yields ""."""
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(_CONFIG_UNSET_JSON)),
        ):
            assert ContextForgeClient().get_config("git.integration_branch") == ""

    def test_get_config_null_value_returns_empty_string(self) -> None:
        data = {**_CONFIG_UNSET_JSON, "value": None}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            assert ContextForgeClient().get_config("git.integration_branch") == ""

    def test_get_config_missing_value_key_returns_empty_string(self) -> None:
        data = {k: v for k, v in _CONFIG_UNSET_JSON.items() if k != "value"}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            assert ContextForgeClient().get_config("git.integration_branch") == ""

    def test_get_config_stringifies_non_string_value(self) -> None:
        data = {**_CONFIG_UNSET_JSON, "key": "review.max_file_size_bytes", "value": 256000}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            assert ContextForgeClient().get_config("review.max_file_size_bytes") == "256000"

    def test_get_project_name_populated(self) -> None:
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(_PROJECT_JSON)),
        ):
            info = ContextForgeClient().get_project()
            assert info.name == "squadron"

    def test_get_project_name_falls_back_to_unknown_when_absent(self) -> None:
        data = {k: v for k, v in _PROJECT_JSON.items() if k != "name"}
        with patch(
            "subprocess.run",
            return_value=_mock_completed(json.dumps(data)),
        ):
            info = ContextForgeClient().get_project()
            assert info.name == "unknown"
