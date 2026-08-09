"""Executable remediation in `sq setup` (issue #29).

Every failure mode asserts on the *message*, not just the boolean: an
install that fails silently, or fails with "install failed", leaves the user
exactly as stuck as before. Naming the missing tool or surfacing npm's own
diagnostic is the whole point.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.cli.commands.doctor_checks import (
    CONTEXT_FORGE_INSTALL_CMD,
    CONTEXT_FORGE_PACKAGE,
    GIT_HOOKS_PATH,
)
from squadron.cli.commands.setup_install import (
    AUTO_INSTALL_CHECKS,
    CF_INIT_HINT,
    PRE_COMMIT_HOOK,
    installer_for,
    run_install,
)

_MODULE = "squadron.cli.commands.setup_install"


def _completed(returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stderr = stderr
    result.stdout = ""
    return result


# ---------------------------------------------------------------------------
# Which checks are automatable
# ---------------------------------------------------------------------------


def test_installer_exists_for_automatable_checks() -> None:
    assert installer_for("slash commands") is not None
    assert installer_for("context-forge") is not None


def test_no_installer_for_credential_checks() -> None:
    """Secrets and provider choices need a human — never guessed at."""
    for name in ("openai", "at least one provider OK", "project .env", "providers.toml"):
        assert installer_for(name) is None


def test_unknown_check_returns_failure_not_exception() -> None:
    outcome = run_install("nonexistent check")
    assert outcome.succeeded is False
    assert "No automatic install" in outcome.message


# ---------------------------------------------------------------------------
# Context Forge: the npm path
# ---------------------------------------------------------------------------


def test_context_forge_installs_correct_package() -> None:
    """The 404 package must never come back (#29)."""
    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/npm"),
        patch(f"{_MODULE}.subprocess.run", return_value=_completed()) as run,
    ):
        outcome = run_install("context-forge")

    assert outcome.succeeded is True
    npm_argv = run.call_args_list[0].args[0]
    assert npm_argv == ["npm", "install", "-g", CONTEXT_FORGE_PACKAGE]
    assert "manta-digital" not in " ".join(npm_argv)


def test_context_forge_also_installs_cf_commands() -> None:
    """The binary alone leaves the user without /cf:* commands."""
    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/npm"),
        patch(f"{_MODULE}.subprocess.run", return_value=_completed()) as run,
    ):
        outcome = run_install("context-forge")

    assert outcome.succeeded is True
    commands = [call.args[0] for call in run.call_args_list]
    assert ["cf", "install-commands"] in commands


def test_missing_npm_names_the_missing_tool() -> None:
    """'npm not found' is actionable; 'install failed' is not."""
    with patch(f"{_MODULE}.shutil.which", return_value=None):
        outcome = run_install("context-forge")

    assert outcome.succeeded is False
    assert "npm not found" in outcome.message
    assert CONTEXT_FORGE_INSTALL_CMD in outcome.message


def test_npm_failure_surfaces_npm_diagnostic() -> None:
    """EACCES/network/404 detail is what the user needs, not a generic message."""
    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/npm"),
        patch(
            f"{_MODULE}.subprocess.run",
            return_value=_completed(returncode=1, stderr="npm error code EACCES\nnpm error path /usr"),
        ),
    ):
        outcome = run_install("context-forge")

    assert outcome.succeeded is False
    assert "EACCES" in outcome.message or "npm error" in outcome.message


def test_npm_timeout_is_reported_not_hung() -> None:
    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/npm"),
        patch(
            f"{_MODULE}.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="npm", timeout=300),
        ),
    ):
        outcome = run_install("context-forge")

    assert outcome.succeeded is False
    assert "timed out" in outcome.message


def test_cf_commands_failure_still_reports_binary_installed() -> None:
    """A partial success is reported as such — not as total failure."""
    calls: list[list[str]] = []

    def _run(argv: list[str], **_: object) -> MagicMock:
        calls.append(argv)
        return _completed() if argv[0] == "npm" else _completed(returncode=1, stderr="boom")

    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/npm"),
        patch(f"{_MODULE}.subprocess.run", side_effect=_run),
    ):
        outcome = run_install("context-forge")

    assert outcome.succeeded is True
    assert "cf install-commands" in outcome.message


# ---------------------------------------------------------------------------
# Squadron's own slash commands
# ---------------------------------------------------------------------------


def test_sq_commands_install_in_process() -> None:
    with patch("squadron.cli.commands.install.install_commands") as install:
        outcome = run_install("slash commands")

    assert outcome.succeeded is True
    install.assert_called_once()


def test_sq_commands_oserror_is_caught() -> None:
    with patch(
        "squadron.cli.commands.install.install_commands",
        side_effect=OSError("permission denied"),
    ):
        outcome = run_install("slash commands")

    assert outcome.succeeded is False
    assert "permission denied" in outcome.message


# ---------------------------------------------------------------------------
# cf init stays the user's call
# ---------------------------------------------------------------------------


def test_cf_init_is_never_run_automatically() -> None:
    """cf init writes into the CWD, so a global setup pass must not run it."""
    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/npm"),
        patch(f"{_MODULE}.subprocess.run", return_value=_completed()) as run,
    ):
        run_install("context-forge")

    for call in run.call_args_list:
        assert "init" not in call.args[0], f"cf init must not run automatically: {call.args[0]}"


def test_cf_init_hint_is_offered() -> None:
    assert "cf init" in CF_INIT_HINT


# ---------------------------------------------------------------------------
# Frontmatter pre-commit gate (D11: the gate installs itself)
# ---------------------------------------------------------------------------


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_gate_hook_matches_tracked_copy() -> None:
    """The tracked .githooks/pre-commit and the installed hook must not drift."""
    tracked = Path(".githooks/pre-commit").read_text(encoding="utf-8")
    assert tracked == PRE_COMMIT_HOOK


def test_gate_is_auto_installed() -> None:
    assert "git pre-commit hook" in AUTO_INSTALL_CHECKS
    assert installer_for("git pre-commit hook") is not None


def test_gate_install_writes_hook_and_sets_hookspath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    outcome = run_install("git pre-commit hook")

    assert outcome.succeeded is True, outcome.message
    hook = tmp_path / GIT_HOOKS_PATH / "pre-commit"
    assert hook.read_text(encoding="utf-8") == PRE_COMMIT_HOOK
    assert hook.stat().st_mode & 0o111, "hook must be executable"
    configured = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert configured.stdout.strip() == GIT_HOOKS_PATH


def test_gate_install_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    first = run_install("git pre-commit hook")
    second = run_install("git pre-commit hook")

    assert first.succeeded and second.succeeded


def test_gate_install_refuses_foreign_hookspath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user's own hooks directory is never overwritten to install ours."""
    _init_repo(tmp_path)
    subprocess.run(["git", "config", "core.hooksPath", "my/own/hooks"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)

    outcome = run_install("git pre-commit hook")

    assert outcome.succeeded is False
    assert "my/own/hooks" in outcome.message
    assert not (tmp_path / GIT_HOOKS_PATH).exists()


def test_gate_install_outside_repo_fails_with_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    outcome = run_install("git pre-commit hook")

    assert outcome.succeeded is False
    assert "not inside a git repository" in outcome.message
