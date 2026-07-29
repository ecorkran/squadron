"""Executable remediation for ``sq setup`` steps that can install themselves.

``sq setup`` historically only *printed* fix commands. For the three steps
below that is needless friction: they are all user-global, idempotent, and
have no project side effects, so making the user copy a command back into
the same terminal buys nothing.

Scope is deliberately narrow. Only these three are automated:

- ``sq install-commands`` — the ``/sq:*`` slash commands (in-process)
- ``npm i -g @context-forge/cli`` — the ``cf`` binary
- ``cf install-commands`` — the ``/cf:*`` slash commands

Everything else (provider credentials, ``.env`` files) stays advisory: those
need a human decision or a secret, and running them unattended would be
guessing on the user's behalf.

**``cf init`` is deliberately not run here.** It writes guides and IDE config
*into the current directory*, so it belongs to a project the user has chosen
— not to a global setup pass that may be running from anywhere. Setup points
at it instead.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from squadron.cli.commands.doctor_checks import (
    CONTEXT_FORGE_INSTALL_CMD,
    CONTEXT_FORGE_PACKAGE,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CF_INIT_HINT",
    "InstallOutcome",
    "installer_for",
    "run_install",
]

#: Closing suggestion printed once at the end of setup. Global setup cannot
#: do this step for the user: it is per-project by nature.
CF_INIT_HINT = (
    "Next: run [bold]cf init[/bold] in your project to install the AI project "
    "guides and IDE configuration for that repo."
)

#: How long any single install may run before we stop waiting. Generous —
#: a cold npm global install on a slow link is legitimately slow — but
#: bounded, so setup can never hang forever on a wedged package manager.
_INSTALL_TIMEOUT_S = 300


class InstallOutcome:
    """What happened when an install was attempted.

    Not an enum-plus-message tuple at the call site: the message varies per
    failure mode and the caller renders it verbatim, so they travel together.
    """

    def __init__(self, *, succeeded: bool, message: str) -> None:
        self.succeeded = succeeded
        self.message = message


def _run_command(argv: list[str], *, label: str) -> InstallOutcome:
    """Run one install command, mapping every failure mode to an outcome.

    Never raises: a failed install must leave setup able to fall back to
    telling the user the command, which is strictly better than a traceback.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            argv,
            capture_output=True,
            text=True,
            timeout=_INSTALL_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError:
        # The tool itself is absent (e.g. no npm). Naming it is the whole
        # value here — "install failed" would send the user hunting.
        return InstallOutcome(
            succeeded=False,
            message=f"{argv[0]} not found on PATH — install {argv[0]} first, then re-run.",
        )
    except subprocess.TimeoutExpired:
        return InstallOutcome(
            succeeded=False,
            message=f"{label} timed out after {_INSTALL_TIMEOUT_S}s — run it manually.",
        )
    except OSError as exc:
        logger.exception("%s failed to launch", label)
        return InstallOutcome(succeeded=False, message=f"{label} could not run: {exc}")

    if completed.returncode == 0:
        return InstallOutcome(succeeded=True, message=f"{label} completed.")

    # Surface the tool's own last line rather than a generic failure: npm's
    # diagnostics (EACCES, network, 404) are what the user needs to act on.
    stderr = (completed.stderr or "").strip().splitlines()
    tail = stderr[-1] if stderr else f"exit code {completed.returncode}"
    return InstallOutcome(succeeded=False, message=f"{label} failed: {tail}")


def _install_sq_commands() -> InstallOutcome:
    """Install the ``/sq:*`` slash commands in-process."""
    # Imported here rather than at module scope: cli.commands.install pulls in
    # the Typer app surface, and this module is imported by the check layer.
    from squadron.cli.commands.install import install_commands

    try:
        install_commands()
    except SystemExit as exc:
        # Typer raises SystemExit/Exit on its own error paths.
        if exc.code not in (0, None):
            return InstallOutcome(
                succeeded=False,
                message=f"sq install-commands exited with code {exc.code}.",
            )
    except OSError as exc:
        logger.exception("sq install-commands failed")
        return InstallOutcome(succeeded=False, message=f"sq install-commands failed: {exc}")
    return InstallOutcome(succeeded=True, message="sq install-commands completed.")


def _install_context_forge() -> InstallOutcome:
    """Install the ``cf`` binary globally via npm."""
    if shutil.which("npm") is None:
        return InstallOutcome(
            succeeded=False,
            message=(
                "npm not found on PATH. Context Forge ships on npm, so install "
                f"Node.js first, then run: {CONTEXT_FORGE_INSTALL_CMD}"
            ),
        )
    return _run_command(
        ["npm", "install", "-g", CONTEXT_FORGE_PACKAGE],
        label="npm install",
    )


def _install_cf_commands() -> InstallOutcome:
    """Install the ``/cf:*`` slash commands via the freshly-installed cf."""
    if shutil.which("cf") is None:
        return InstallOutcome(
            succeeded=False,
            message="cf not on PATH yet — install Context Forge first.",
        )
    return _run_command(["cf", "install-commands"], label="cf install-commands")


#: Check name → installer. A check absent from this map is advisory-only and
#: setup falls back to printing its fix command, which is the correct
#: behavior for anything needing a human decision or a secret.
_INSTALLERS = {
    "slash commands": _install_sq_commands,
    "context-forge": _install_context_forge,
}


def installer_for(check_name: str):  # type: ignore[no-untyped-def]
    """Return the installer for a check, or ``None`` if it is advisory-only."""
    return _INSTALLERS.get(check_name)


def run_install(check_name: str) -> InstallOutcome:
    """Run the installer for ``check_name``.

    Installing Context Forge also installs its slash commands: the binary
    alone leaves the user without ``/cf:*``, which is a half-finished state
    they would have no reason to expect.
    """
    installer = _INSTALLERS.get(check_name)
    if installer is None:
        return InstallOutcome(
            succeeded=False,
            message=f"No automatic install available for {check_name!r}.",
        )

    outcome = installer()
    if check_name == "context-forge" and outcome.succeeded:
        commands = _install_cf_commands()
        if not commands.succeeded:
            return InstallOutcome(
                succeeded=True,
                message=(
                    f"{outcome.message} Slash commands not installed "
                    f"({commands.message}) — run 'cf install-commands' manually."
                ),
            )
        return InstallOutcome(
            succeeded=True,
            message=f"{outcome.message} {commands.message}",
        )
    return outcome
