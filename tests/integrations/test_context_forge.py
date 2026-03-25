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
        with patch(
            "subprocess.run", return_value=_mock_completed(json.dumps(_SLICES_JSON))
        ):
            slices = ContextForgeClient().list_slices()
            assert len(slices) == 2
            assert slices[0].index == 100
            assert slices[0].name == "Project Setup"
            assert (
                slices[0].design_file
                == "project-documents/user/slices/100-slice.project-setup.md"
            )
            assert slices[0].status == "complete"

    def test_list_slices_missing_design_file(self) -> None:
        with patch(
            "subprocess.run", return_value=_mock_completed(json.dumps(_SLICES_JSON))
        ):
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
        with patch(
            "subprocess.run", return_value=_mock_completed(json.dumps(_TASKS_JSON))
        ):
            tasks = ContextForgeClient().list_tasks()
            assert len(tasks) == 2
            assert tasks[0].index == 100
            assert tasks[0].files == ["100-tasks.project-setup.md"]

    def test_list_tasks_no_files(self) -> None:
        with patch(
            "subprocess.run", return_value=_mock_completed(json.dumps(_TASKS_JSON))
        ):
            tasks = ContextForgeClient().list_tasks()
            assert tasks[1].files == []

    def test_list_tasks_empty(self) -> None:
        with patch("subprocess.run", return_value=_mock_completed(json.dumps([]))):
            assert ContextForgeClient().list_tasks() == []


# ---------------------------------------------------------------------------
# T9 — get_project()
# ---------------------------------------------------------------------------

_PROJECT_JSON = {
    "fileArch": "100-arch.orchestration-v2",
    "fileSlicePlan": "100-slices.orchestration-v2",
    "phase": "Phase 6: Implementation",
    "slice": "126-slice.context-forge-integration-layer",
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
            assert info.slice == "126-slice.context-forge-integration-layer"

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
