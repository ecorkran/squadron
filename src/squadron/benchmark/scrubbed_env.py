"""Scrubbed producer environment and credential grants (slice 421 D7, D8)."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.benchmark.auth_carryover import AUTH_CARRYOVER_FILES, AUTH_OPTIONAL_VARIABLES
from squadron.providers.base import ProfileName
from squadron.providers.profiles import get_profile

# Bump when the scrub rules below change; recorded in the environment identity.
SCRUB_SPEC_VERSION = 1
SQUADRON_CONFIG_SEED = ("config.toml", "models.toml", "providers.toml")
HARNESS_TOOL_ALLOWLIST = ("git", "uv")
BENCHMARK_GIT_USER_NAME = "squadron-benchmark"
BENCHMARK_GIT_USER_EMAIL = "benchmark@squadron.invalid"
SYSTEM_PATH_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
PASS_THROUGH_VARIABLES = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
)
_SQUADRON_CONFIG_RELATIVE = Path(".config") / "squadron"


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MissingCredentialError(Exception):
    """A granted credential variable is not set in the harness environment."""

    def __init__(self, variable: str) -> None:
        super().__init__(f"credential variable {variable} not set")
        self.variable = variable


class MissingHarnessHomeError(Exception):
    """The harness environment has no HOME, so there is no real home to seed from."""

    def __init__(self) -> None:
        super().__init__("HOME is not set in the harness environment")


class MissingHarnessToolError(Exception):
    """A tool the sandbox needs is not on the harness PATH."""

    def __init__(self, tool: str) -> None:
        super().__init__(f"{tool} not found on the harness PATH")
        self.tool = tool


@dataclass(frozen=True)
class CredentialGrant:
    """What authentication enters a sandbox: variable names and home-relative files."""

    variables: tuple[str, ...] = ()
    carryover_files: tuple[str, ...] = ()
    optional_variables: tuple[str, ...] = ()

    @classmethod
    def none(cls) -> CredentialGrant:
        """Grant nothing (suite runs)."""
        return cls()

    @classmethod
    def for_profiles(cls, profiles: Iterable[ProfileName]) -> CredentialGrant:
        """Grant each profile's ``api_key_env`` variable, carryover files and optional tokens."""
        variables: list[str] = []
        files: list[str] = []
        optional: list[str] = []
        for profile_name in profiles:
            env_name = get_profile(profile_name).api_key_env
            if env_name is not None and env_name not in variables:
                variables.append(env_name)
            for path in AUTH_CARRYOVER_FILES[profile_name]:
                if path not in files:
                    files.append(path)
            for name in AUTH_OPTIONAL_VARIABLES.get(profile_name, ()):
                if name not in optional:
                    optional.append(name)
        return cls(
            variables=tuple(variables),
            carryover_files=tuple(files),
            optional_variables=tuple(optional),
        )


class ScrubbedEnvironment:
    """A fresh home and an explicit variable map for producer and suite children.

    ``harness_env`` is injected (never read from ``os.environ`` here) so tests
    control it. Callers pass ``variables()`` to ``ProcessRunner.run`` with
    ``replace_env=True``.
    """

    def __init__(
        self,
        root: Path,
        sandbox_id: str,
        grant: CredentialGrant,
        harness_env: Mapping[str, str],
    ) -> None:
        self._grant = grant
        self._harness_env = harness_env
        self.home = root / f"{sandbox_id}.home"
        self._carried_digests: dict[Path, str] = {}

    @property
    def changed_carried_paths(self) -> list[Path]:
        """Carried copies whose content differs from what was copied in, or that are gone.

        A copy is never the real file, so a tool that rewrites its login (a refresh-token
        rotation) changes only the copy; this reports it.
        """
        return [
            path
            for path, digest in self._carried_digests.items()
            if not path.is_file() or _file_digest(path) != digest
        ]

    def prepare(self) -> None:
        """Create the home: seed config, gitconfig, tool symlinks, carried files."""
        real_home = self._real_home()
        self.home.mkdir(parents=True)
        self._seed_config(real_home)
        self._write_gitconfig()
        self._link_tools()
        self._link_carryover(real_home)

    def cleanup(self) -> None:
        """Remove the home directory if it exists."""
        shutil.rmtree(self.home, ignore_errors=True)

    def variables(self, path_entries: Sequence[str | Path]) -> dict[str, str]:
        """The complete child environment: nothing but what this method names."""
        env = {
            name: self._harness_env[name]
            for name in PASS_THROUGH_VARIABLES
            if name in self._harness_env
        }
        path = [str(entry) for entry in path_entries]
        path += [str(self.home / "bin"), *SYSTEM_PATH_DIRS]
        env.update(
            HOME=str(self.home),
            TZ="UTC",
            GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_TERMINAL_PROMPT="0",
            PATH=":".join(path),
        )
        for name in self._grant.variables:
            env[name] = self._harness_env.get(name) or self._missing_credential(name)
        for name in self._grant.optional_variables:
            if self._harness_env.get(name):
                env[name] = self._harness_env[name]
        return env

    @staticmethod
    def _missing_credential(name: str) -> str:
        raise MissingCredentialError(name)

    def _real_home(self) -> Path:
        home = self._harness_env.get("HOME")
        if not home:
            raise MissingHarnessHomeError
        return Path(home)

    def _seed_config(self, real_home: Path) -> None:
        source_dir = real_home / _SQUADRON_CONFIG_RELATIVE
        target_dir = self.home / _SQUADRON_CONFIG_RELATIVE
        target_dir.mkdir(parents=True)
        for name in SQUADRON_CONFIG_SEED:
            if (source_dir / name).is_file():
                shutil.copy2(source_dir / name, target_dir / name)

    def _write_gitconfig(self) -> None:
        (self.home / ".gitconfig").write_text(
            "[user]\n"
            f"\tname = {BENCHMARK_GIT_USER_NAME}\n"
            f"\temail = {BENCHMARK_GIT_USER_EMAIL}\n"
            "[init]\n\tdefaultBranch = main\n"
        )

    def _link_tools(self) -> None:
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        harness_path = self._harness_env.get("PATH", "")
        for tool in HARNESS_TOOL_ALLOWLIST:
            found = shutil.which(tool, path=harness_path)
            if found is None:
                raise MissingHarnessToolError(tool)
            (bin_dir / tool).symlink_to(found)

    def _link_carryover(self, real_home: Path) -> None:
        for rel in self._grant.carryover_files:
            source = real_home / rel
            if not source.exists():
                continue
            target = self.home / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            # A copy, not a symlink: a tool that opens the file for writing must not
            # modify the real login (#301). copy2 keeps the file's mode (0600).
            shutil.copy2(source, target)
            self._carried_digests[target] = _file_digest(target)
