"""Tests for SubprocessRunner — results, the two error types, env, decoding.

Every case runs ``python -c`` so no external binary is required.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessTimedOutError,
    SubprocessRunner,
)


def test_success_captures_streams_and_returncode() -> None:
    runner = SubprocessRunner()
    result = runner.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('out'); sys.stderr.write('err')",
        ],
        cwd=None,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.argv[0] == sys.executable


def test_nonzero_exit_is_returned_not_raised() -> None:
    runner = SubprocessRunner()
    result = runner.run([sys.executable, "-c", "import sys; sys.exit(3)"], cwd=None, timeout=30)
    assert result.returncode == 3


def test_missing_executable_raises_naming_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = SubprocessRunner()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ProcessNotFoundError) as excinfo:
            runner.run(["squadron-no-such-executable"], cwd=None, timeout=30)
    assert excinfo.value.executable == "squadron-no-such-executable"
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_timeout_raises_naming_the_bound(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = SubprocessRunner()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ProcessTimedOutError) as excinfo:
            runner.run(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=None,
                timeout=0.2,
            )
    assert excinfo.value.timeout == 0.2
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_nonexistent_cwd_raises_naming_the_directory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = SubprocessRunner()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ProcessCwdNotFoundError) as excinfo:
            runner.run(["git", "status"], cwd="/nonexistent-922", timeout=30)
    assert excinfo.value.cwd == "/nonexistent-922"
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_missing_executable_with_valid_cwd_still_raises_process_not_found(
    tmp_path: Path,
) -> None:
    runner = SubprocessRunner()
    with pytest.raises(ProcessNotFoundError) as excinfo:
        runner.run(["squadron-no-such-executable"], cwd=str(tmp_path), timeout=30)
    assert excinfo.value.executable == "squadron-no-such-executable"


def test_missing_executable_with_none_cwd_still_raises_process_not_found() -> None:
    runner = SubprocessRunner()
    with pytest.raises(ProcessNotFoundError) as excinfo:
        runner.run(["squadron-no-such-executable"], cwd=None, timeout=30)
    assert excinfo.value.executable == "squadron-no-such-executable"


def test_env_merges_over_os_environ_rather_than_replacing_it() -> None:
    runner = SubprocessRunner()
    os.environ["SQUADRON_PREEXISTING"] = "kept"
    try:
        result = runner.run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ.get('SQUADRON_PREEXISTING'), "
                "os.environ.get('SQUADRON_INJECTED'))",
            ],
            cwd=None,
            timeout=30,
            env={"SQUADRON_INJECTED": "added"},
        )
    finally:
        del os.environ["SQUADRON_PREEXISTING"]
    assert result.stdout.strip() == "kept added"


def test_non_utf8_stdout_does_not_raise() -> None:
    runner = SubprocessRunner()
    result = runner.run(
        [
            sys.executable,
            "-c",
            r"import sys; sys.stdout.buffer.write(b'\xff\xfe')",
        ],
        cwd=None,
        timeout=30,
    )
    assert result.returncode == 0


def test_stdin_is_passed_to_the_child() -> None:
    runner = SubprocessRunner()
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"],
        cwd=None,
        timeout=30,
        stdin="body",
    )
    assert result.stdout == "body"
