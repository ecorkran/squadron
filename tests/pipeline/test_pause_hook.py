"""The command started when a run ends paused (#302)."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import pytest

from squadron.config.keys import ON_PAUSE_COMMAND_KEY
from squadron.config.manager import set_config
from squadron.pipeline.pause_hook import start_pause_command


def _wait_for(path: Path) -> str:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists() and path.read_text():
            return path.read_text()
        time.sleep(0.05)
    raise AssertionError(f"{path} was never written")


def _writer_command(script: Path) -> str:
    script.write_text(
        "import os, sys\n"
        "open(sys.argv[1], 'w').write(f'{sys.argv[2]}|{os.getcwd()}|{os.getsid(0) != os.getppid()}')\n"
    )
    return f"{sys.executable} {script}"


class TestStartPauseCommand:
    def test_unset_starts_nothing(self, patch_config_paths: dict[str, Path], tmp_path: Path) -> None:
        assert start_pause_command("run-1", str(tmp_path)) is False

    def test_starts_command_in_working_directory_with_run_id(
        self, patch_config_paths: dict[str, Path], tmp_path: Path
    ) -> None:
        out = tmp_path / "out.txt"
        command = _writer_command(tmp_path / "hook.py") + f" {out}"
        set_config(ON_PAUSE_COMMAND_KEY, command, project=True, cwd=str(tmp_path))

        assert start_pause_command("run-42", str(tmp_path)) is True

        run_id, cwd, _ = _wait_for(out).split("|")
        assert run_id == "run-42"
        assert Path(cwd).resolve() == tmp_path.resolve()

    def test_command_runs_in_its_own_session(
        self, patch_config_paths: dict[str, Path], tmp_path: Path
    ) -> None:
        out = tmp_path / "sid.txt"
        script = tmp_path / "sid.py"
        script.write_text(f"import os\nopen({str(out)!r}, 'w').write(str(os.getsid(0)))\n")
        set_config(ON_PAUSE_COMMAND_KEY, f"{sys.executable} {script}", project=True, cwd=str(tmp_path))

        start_pause_command("run-1", str(tmp_path))

        assert int(_wait_for(out)) != os.getsid(0)

    def test_unstartable_command_warns_and_returns_false(
        self,
        patch_config_paths: dict[str, Path],
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        set_config(ON_PAUSE_COMMAND_KEY, "/no/such/binary-302", project=True, cwd=str(tmp_path))

        with caplog.at_level(logging.WARNING):
            assert start_pause_command("run-1", str(tmp_path)) is False

        assert [r.levelno for r in caplog.records] == [logging.WARNING]
        assert "/no/such/binary-302" in caplog.text

    def test_unparseable_command_warns_and_returns_false(
        self,
        patch_config_paths: dict[str, Path],
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        set_config(ON_PAUSE_COMMAND_KEY, "echo 'unterminated", project=True, cwd=str(tmp_path))

        with caplog.at_level(logging.WARNING):
            assert start_pause_command("run-1", str(tmp_path)) is False

        assert len(caplog.records) == 1
