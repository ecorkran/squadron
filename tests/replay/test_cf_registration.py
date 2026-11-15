"""CfRegistration: three cf steps under a given environment, with an observable failure
signal for each way a step can fail (slices 177 D3, 426 D9)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from squadron.core.process_runner import (
    ProcessResult,
    ProcessTimedOutError,
)
from squadron.replay.cf_registration import (
    CfRegistration,
    CfRegistrationError,
    SliceNotInPlanError,
)

_PLAN = "project-documents/user/architecture/140-slices.pipeline-foundation.md"
_PLAN_TEXT = "# Plan\n\n1. [ ] **(176) Effort Calibration** — text. Effort: 4/5\n"
_SLICE = 176
_NAME = "bench-1"
_BRANCH = "426-slice.slice-cases"
_ENV = {"HOME": "/scrub/home", "PATH": "/scrub/home/bin"}


class _Call:
    def __init__(
        self, argv: tuple[str, ...], cwd: str | None, env: Mapping[str, str] | None, replace: bool
    ) -> None:
        self.argv = argv
        self.cwd = cwd
        self.env = env
        self.replace = replace


class _Runner:
    """Records every call; a scripted failure or timeout answers a matching argv prefix."""

    def __init__(self) -> None:
        self.calls: list[_Call] = []
        self.failures: dict[tuple[str, ...], str] = {}
        self.timeouts: set[tuple[str, ...]] = set()

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
        replace_env: bool = False,
    ) -> ProcessResult:
        call = tuple(argv)
        self.calls.append(_Call(call, cwd, env, replace_env))
        for prefix in self.timeouts:
            if call[1 : 1 + len(prefix)] == prefix:
                raise ProcessTimedOutError(call, timeout)
        for prefix, stderr in self.failures.items():
            if call[1 : 1 + len(prefix)] == prefix:
                return ProcessResult(argv=call, returncode=1, stdout="", stderr=f"{stderr}\n")
        return ProcessResult(argv=call, returncode=0, stdout="", stderr="")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    plan = tmp_path / _PLAN
    plan.parent.mkdir(parents=True)
    plan.write_text(_PLAN_TEXT)
    return tmp_path


def test_runs_the_three_commands_in_order_with_cwd_and_env(tree: Path) -> None:
    runner = _Runner()

    CfRegistration(runner, _ENV).register(tree, _NAME, _BRANCH, _SLICE)

    assert [call.argv for call in runner.calls] == [
        ("cf", "init", "--lite", "--no-ide", "--name", _NAME),
        ("cf", "config", "set", "git.integration_branch", _BRANCH),
        ("cf", "set", "arch", "140"),
    ]
    assert {call.cwd for call in runner.calls} == {str(tree)}
    assert all(call.env == _ENV and call.replace for call in runner.calls)


def test_without_an_environment_the_harness_environment_is_used(tree: Path) -> None:
    runner = _Runner()

    CfRegistration(runner, None).register(tree, _NAME, _BRANCH, _SLICE)

    assert all(call.env is None and not call.replace for call in runner.calls)


def test_registered_is_false_before_and_true_after(tree: Path) -> None:
    registration = CfRegistration(_Runner(), _ENV)
    assert not registration.registered

    registration.register(tree, _NAME, _BRANCH, _SLICE)

    assert registration.registered


def test_a_failing_set_arch_leaves_registered_true_and_raises_with_stderr(
    tree: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = _Runner()
    runner.failures[("set", "arch")] = "no such initiative"
    registration = CfRegistration(runner, _ENV)

    with caplog.at_level(logging.ERROR), pytest.raises(CfRegistrationError, match="no such initiative"):
        registration.register(tree, _NAME, _BRANCH, _SLICE)

    assert registration.registered
    assert any(r.levelno == logging.ERROR and "cf set arch" in r.getMessage() for r in caplog.records)


def test_a_failing_cf_init_leaves_registered_false(
    tree: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = _Runner()
    runner.failures[("init",)] = "cf exploded"
    registration = CfRegistration(runner, _ENV)

    with caplog.at_level(logging.ERROR), pytest.raises(CfRegistrationError, match="cf exploded"):
        registration.register(tree, _NAME, _BRANCH, _SLICE)

    assert not registration.registered
    assert len(runner.calls) == 1
    assert any(r.levelno == logging.ERROR and "cf exploded" in r.getMessage() for r in caplog.records)


def test_a_slice_in_no_plan_raises_runs_no_cf_command_and_logs_error(
    tree: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = _Runner()
    registration = CfRegistration(runner, _ENV)

    with caplog.at_level(logging.ERROR), pytest.raises(SliceNotInPlanError, match="slice 999"):
        registration.register(tree, _NAME, _BRANCH, 999)

    assert not registration.registered
    assert runner.calls == []
    assert any(r.levelno == logging.ERROR and "999" in r.getMessage() for r in caplog.records)


def test_a_timeout_raises_and_logs_error(tree: Path, caplog: pytest.LogCaptureFixture) -> None:
    runner = _Runner()
    runner.timeouts.add(("config", "set"))
    registration = CfRegistration(runner, _ENV)

    with caplog.at_level(logging.ERROR), pytest.raises(CfRegistrationError, match="config set"):
        registration.register(tree, _NAME, _BRANCH, _SLICE)

    assert registration.registered  # cf init had succeeded
    assert any(r.levelno == logging.ERROR and "config set" in r.getMessage() for r in caplog.records)
