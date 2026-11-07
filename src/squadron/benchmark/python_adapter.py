"""The Python benchmark adapter: uv lockfile environments and a pytest suite runner (slice 421).

Environment resolution (D5, D6) installs the project at the sandbox commit from its own
``uv.lock`` with ``uv sync --locked``. An unpinned install has no environment identity to
key qualification on, so a missing, stale or foreign lockfile is a named failure, never a
silent fallback.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import shutil
import sys
from pathlib import Path

from squadron.benchmark.adapter import (
    EnvironmentFailureReason,
    EnvironmentIdentity,
    EnvironmentResolutionError,
    SandboxContext,
    SuiteRun,
    SuiteSelection,
)
from squadron.benchmark.python_failure import VENV_DIR, venv_bin
from squadron.benchmark.python_suite import run_pytest_suite
from squadron.benchmark.scrubbed_env import SCRUB_SPEC_VERSION
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
)
from squadron.metrology.snapshot_models import SourceLanguage

_logger = logging.getLogger(__name__)

LOCKFILE_NAME = "uv.lock"
UNSUPPORTED_LOCKFILES = ("poetry.lock",)
REQUIREMENTS_GLOB = "requirements*.txt"
INSTALL_ARGV = ("uv", "sync", "--locked", "--all-extras", "--dev")
VERSION_COMMAND_TIMEOUT_S = 60


def _failure(reason: EnvironmentFailureReason, detail: str) -> EnvironmentResolutionError:
    _logger.error("environment resolution failed: %s: %s", reason.value, detail)
    return EnvironmentResolutionError(reason, detail)


class PythonBenchmarkAdapter:
    language = SourceLanguage.PYTHON

    def resolve_environment(self, ctx: SandboxContext) -> EnvironmentIdentity:
        """Install from ``uv.lock`` and return the grader's environment identity."""
        lockfile = self._require_lockfile(ctx.tree)
        self._install(ctx)
        self._exclude_venv(ctx.tree)
        return EnvironmentIdentity(
            language=self.language,
            lockfile_path=LOCKFILE_NAME,
            lockfile_sha256=hashlib.sha256(lockfile.read_bytes()).hexdigest(),
            interpreter_version=self._version(ctx, [str(self._python(ctx.tree)), "--version"]),
            installer_version=self._version(ctx, ["uv", "--version"]),
            platform=f"{sys.platform}-{platform.machine()}",
            scrub_spec_version=SCRUB_SPEC_VERSION,
        )

    def path_entries(self, ctx: SandboxContext) -> tuple[Path, ...]:
        return (venv_bin(ctx.tree),)

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        """Run pytest under the scrubbed environment and fold the reporter's records."""
        return run_pytest_suite(ctx, selection, ctx.env.variables(self.path_entries(ctx)))

    @staticmethod
    def _python(tree: Path) -> Path:
        return venv_bin(tree) / "python"

    @staticmethod
    def _require_lockfile(tree: Path) -> Path:
        lockfile = tree / LOCKFILE_NAME
        if lockfile.is_file():
            return lockfile
        foreign = [name for name in UNSUPPORTED_LOCKFILES if (tree / name).is_file()]
        foreign += sorted(path.name for path in tree.glob(REQUIREMENTS_GLOB))
        if foreign:
            raise _failure(
                EnvironmentFailureReason.LOCKFILE_UNSUPPORTED,
                f"found {foreign[0]} but only {LOCKFILE_NAME} is supported",
            )
        raise _failure(EnvironmentFailureReason.NO_LOCKFILE, f"no {LOCKFILE_NAME} in the tree")

    @staticmethod
    def _uv_directory(ctx: SandboxContext, kind: str) -> str:
        """uv's real cache or python directory, asked of uv under the harness environment.

        The scrubbed home would otherwise hide the user's uv cache and managed Pythons,
        turning every install into a full download.
        """
        result = ctx.runner.run(
            ["uv", kind, "dir"], cwd=str(ctx.tree), timeout=VERSION_COMMAND_TIMEOUT_S
        )
        if result.returncode != 0:
            raise _failure(
                EnvironmentFailureReason.INSTALLER_MISSING,
                f"uv {kind} dir exited {result.returncode}: {result.stderr.strip()}",
            )
        return result.stdout.strip()

    @classmethod
    def _install(cls, ctx: SandboxContext) -> None:
        # Dependency build scripts run arbitrary code, so the install gets the scrubbed
        # environment (no GH_TOKEN and the rest), plus uv's real cache and Python
        # directories so it stays fast. Proxy and index settings are not carried over.
        try:
            env = {
                **ctx.env.variables(()),
                "UV_CACHE_DIR": cls._uv_directory(ctx, "cache"),
                "UV_PYTHON_INSTALL_DIR": cls._uv_directory(ctx, "python"),
            }
            result = ctx.runner.run(
                INSTALL_ARGV,
                cwd=str(ctx.tree),
                timeout=ctx.install_timeout_s,
                env=env,
                replace_env=True,
            )
        except ProcessTimedOutError as exc:
            shutil.rmtree(ctx.tree / VENV_DIR, ignore_errors=True)
            raise _failure(EnvironmentFailureReason.INSTALL_TIMEOUT, str(exc)) from exc
        except ProcessNotFoundError as exc:
            raise _failure(EnvironmentFailureReason.INSTALLER_MISSING, str(exc)) from exc
        if result.returncode != 0:
            # uv creates .venv before it checks the lock; a failed install leaves no environment.
            shutil.rmtree(ctx.tree / VENV_DIR, ignore_errors=True)
            raise _failure(EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, result.stderr.strip())

    @staticmethod
    def _exclude_venv(tree: Path) -> None:
        """Keep ``.venv/`` out of ``git status`` so it never shows in a producer's diff."""
        exclude = tree / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if f"{VENV_DIR}/" not in existing.splitlines():
            exclude.write_text(f"{existing}{VENV_DIR}/\n", encoding="utf-8")

    @staticmethod
    def _version(ctx: SandboxContext, argv: list[str]) -> str:
        try:
            result: ProcessResult = ctx.runner.run(
                argv, cwd=str(ctx.tree), timeout=VERSION_COMMAND_TIMEOUT_S
            )
        except (ProcessNotFoundError, ProcessTimedOutError) as exc:
            raise _failure(EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, str(exc)) from exc
        if result.returncode != 0:
            raise _failure(
                EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE,
                f"{' '.join(argv)} exited {result.returncode}: {result.stderr.strip()}",
            )
        return result.stdout.strip()
