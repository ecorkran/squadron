"""Tests for resolve_argv — PATH resolution of argv[0] before spawning."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from squadron.core.executables import resolve_argv

_CMD_SHIM = r"C:\Users\dev\AppData\Roaming\npm\cf.CMD"


@pytest.fixture
def on_windows():
    with patch("squadron.core.executables._RESOLVE_ON_PATH", True):
        yield


@pytest.mark.usefixtures("on_windows")
def test_bare_name_resolves_to_windows_cmd_shim() -> None:
    # npm installs cf as cf.cmd on Windows; CreateProcess only appends .exe, so the
    # bare name raises FileNotFoundError unless it is resolved through PATHEXT first.
    with patch("shutil.which", return_value=_CMD_SHIM):
        assert resolve_argv(["cf", "build", "--json"]) == [_CMD_SHIM, "build", "--json"]


@pytest.mark.usefixtures("on_windows")
def test_unresolvable_name_is_returned_unchanged() -> None:
    # The caller's FileNotFoundError handling still reports the missing tool by name.
    with patch("shutil.which", return_value=None):
        assert resolve_argv(["cf", "--version"]) == ["cf", "--version"]


@pytest.mark.usefixtures("on_windows")
def test_arguments_are_never_resolved() -> None:
    with patch("shutil.which", return_value=r"C:\Program Files\Git\cmd\git.exe") as which:
        assert resolve_argv(["git", "status"])[1:] == ["status"]
    which.assert_called_once_with("git")


def test_posix_leaves_argv_to_exec_path_search() -> None:
    with (
        patch("squadron.core.executables._RESOLVE_ON_PATH", False),
        patch("shutil.which") as which,
    ):
        assert resolve_argv(["cf", "--version"]) == ["cf", "--version"]
    which.assert_not_called()


@pytest.mark.usefixtures("on_windows")
def test_context_forge_client_spawns_resolved_path() -> None:
    from squadron.integrations.context_forge import ContextForgeClient

    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="0.19.19", stderr="")
    with (
        patch("shutil.which", return_value=_CMD_SHIM),
        patch("subprocess.run", return_value=completed) as run,
    ):
        ContextForgeClient()._run(["--version"])
    assert run.call_args.args[0] == [_CMD_SHIM, "--version"]
