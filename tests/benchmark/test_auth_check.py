"""run_auth_check with a scripted ProcessRunner."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.auth_check import (
    AuthAnswer,
    ProbeStartError,
    UnresolvedProfileError,
    run_auth_check,
)
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
)
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed, ok

ALIASES = {
    "a1": ("m1", "openai"),
    "a2": ("m2", "openai"),
    "g1": ("m3", "gemini"),
    "o1": ("m4", "openai-oauth"),
    "nop": ("m5", None),
}


@pytest.fixture(autouse=True)
def patch_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "squadron.benchmark.auth_check.resolve_model_alias",
        lambda alias: ALIASES.get(alias, (alias, None)),
    )


@pytest.fixture
def harness_env(tmp_path: Path) -> dict[str, str]:
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("git", "uv"):
        (tools / name).write_text("")
        (tools / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    return {
        "HOME": str(home),
        "PATH": str(tools),
        "OPENAI_API_KEY": "k",
        "GEMINI_API_KEY": "g",
        "GH_TOKEN": "secret",
    }


def probe_ok(call: RunnerCall) -> ProcessResult:
    if "_auth-probe" in call.argv:
        return ok(call.argv, stdout="ok")
    return ok(call.argv, stdout="sq 1")


def check(
    aliases: list[str],
    runner: ScriptedRunner,
    tmp_path: Path,
    harness_env: dict[str, str],
):
    root = tmp_path / "root"
    return run_auth_check(aliases, runner, root, harness_env, "/abs/sq", 5)


def probes(runner: ScriptedRunner) -> list[RunnerCall]:
    return [c for c in runner.calls if "_auth-probe" in c.argv]


def test_same_profile_one_probe_two_profiles_two_rows(
    tmp_path: Path, harness_env: dict[str, str]
) -> None:
    runner = ScriptedRunner(probe_ok)
    rows = check(["a1", "a2"], runner, tmp_path, harness_env)
    assert [r.alias for r in rows] == ["a1"]
    assert len(probes(runner)) == 1
    runner = ScriptedRunner(probe_ok)
    rows = check(["a1", "g1"], runner, tmp_path, harness_env)
    assert [r.alias for r in rows] == ["a1", "g1"]
    assert all(r.answer is AuthAnswer.YES for r in rows)


def test_nonzero_exit_is_no_with_stderr(tmp_path: Path, harness_env: dict[str, str]) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        if "_auth-probe" in call.argv:
            return failed(call.argv, 1, "401 unauthorized")
        return ok(call.argv)

    rows = check(["a1"], ScriptedRunner(handler), tmp_path, harness_env)
    assert rows[0].answer is AuthAnswer.NO
    assert rows[0].exit_code == 1
    assert "401 unauthorized" in rows[0].stderr


def test_timeout_is_no_timed_out(tmp_path: Path, harness_env: dict[str, str]) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        if "_auth-probe" in call.argv:
            raise ProcessTimedOutError(call.argv, 5)
        return ok(call.argv)

    rows = check(["a1"], ScriptedRunner(handler), tmp_path, harness_env)
    assert rows[0].answer is AuthAnswer.NO
    assert rows[0].stderr == "timed out"


def _carried_setup(harness_env: dict[str, str]) -> None:
    source = Path(harness_env["HOME"]) / ".codex" / "auth.json"
    source.parent.mkdir(parents=True)
    source.write_text("{}")


def _replacer(probe_result: int):
    def handler(call: RunnerCall) -> ProcessResult:
        if "_auth-probe" not in call.argv:
            return ok(call.argv)
        assert call.env is not None
        carried = Path(call.env["HOME"]) / ".codex" / "auth.json"
        carried.unlink()
        carried.write_text("{new}")
        if probe_result == 0:
            return ok(call.argv, stdout="ok")
        return failed(call.argv, probe_result, "boom")

    return handler


def test_replaced_symlink_turns_yes_into_carryover_replaced(
    tmp_path: Path, harness_env: dict[str, str]
) -> None:
    _carried_setup(harness_env)
    rows = check(["o1"], ScriptedRunner(_replacer(0)), tmp_path, harness_env)
    assert rows[0].answer is AuthAnswer.YES_CARRYOVER_REPLACED
    assert "auth.json" in rows[0].detail


def test_failed_probe_with_replaced_symlink_stays_no(
    tmp_path: Path, harness_env: dict[str, str]
) -> None:
    _carried_setup(harness_env)
    rows = check(["o1"], ScriptedRunner(_replacer(1)), tmp_path, harness_env)
    assert rows[0].answer is AuthAnswer.NO
    assert "auth.json" in rows[0].detail


@pytest.mark.parametrize("failure", ["exit127", "notfound", "timeout"])
def test_preflight_failure_raises_probe_start_error(
    failure: str, tmp_path: Path, harness_env: dict[str, str]
) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        if failure == "exit127":
            return failed(call.argv, 127, "no interpreter")
        if failure == "notfound":
            raise ProcessNotFoundError("/abs/sq")
        raise ProcessTimedOutError(call.argv, 5)

    runner = ScriptedRunner(handler)
    with pytest.raises(ProbeStartError):
        check(["a1"], runner, tmp_path, harness_env)
    assert probes(runner) == []


def test_unresolved_alias_raises_before_any_probe(tmp_path: Path, harness_env: dict[str, str]) -> None:
    runner = ScriptedRunner(probe_ok)
    for alias in ("nope", "nop"):
        with pytest.raises(UnresolvedProfileError, match=alias):
            check(["a1", alias], runner, tmp_path, harness_env)
    assert runner.calls == []


def test_missing_credential_variable_is_no_and_runner_not_called(
    tmp_path: Path, harness_env: dict[str, str]
) -> None:
    del harness_env["OPENAI_API_KEY"]
    runner = ScriptedRunner(probe_ok)
    rows = check(["a1"], runner, tmp_path, harness_env)
    assert rows[0].answer is AuthAnswer.NO
    assert "credential variable OPENAI_API_KEY not set" in rows[0].stderr
    assert runner.calls == []


def test_scrubbed_call_shape_and_cleanup(tmp_path: Path, harness_env: dict[str, str]) -> None:
    runner = ScriptedRunner(probe_ok)
    check(["a1"], runner, tmp_path, harness_env)
    for call in runner.calls:
        assert call.replace_env is True
        assert call.env is not None
        assert "GH_TOKEN" not in call.env
        assert call.env["HOME"] != harness_env["HOME"]
        assert call.env["HOME"].endswith(".home")
    assert not Path(runner.calls[0].env["HOME"]).exists()  # type: ignore[index]
