"""Git, code-host and own-package leak rules (slice 424 D7).

All three match parsed tokens: the program name and its subcommand, never a substring of the
command line. ``echo gh`` and ``echo <distribution>`` invoke nothing and are not hits.

* **Git / code host.** Only what can read the case's answer counts. A ``gh`` command that
  reads from a repository (every command but the ones listed as local, and ``repo view``
  asked only for the fields that name the repository); ``git`` aimed outside the tree
  (``-C``, ``--git-dir``, ``--work-tree``); ``git clone``, ``fetch``, ``pull``, ``ls-remote``,
  ``remote``, ``submodule`` or ``config`` with an argument that names the case's repository;
  a fetch of a URL whose path names it (``curl``, ``wget`` or a fetch tool's ``url`` field).
  The sandbox repository has no remote, so a bare ``git fetch`` reaches nothing, and another
  repository does not hold the answer. The repository is matched as consecutive
  ``<owner>/<repo>`` path segments, so web, API, raw and ``host:owner/repo`` forms on any
  host of that repository all match.
* **Own package.** An install or run of the project's own distribution through ``pip install``
  (also ``python -m pip install``), ``uv pip install``, ``uv add``, ``uvx``, ``uv tool`` or
  ``pipx``: the network route to the project's source that the scrub cannot close.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import PurePosixPath
from urllib.parse import urlparse

from squadron.benchmark.leak_paths import COMMAND_FIELD, is_under, resolve_in_tree
from squadron.benchmark.leak_rules import LeakRules, normalize_distribution
from squadron.benchmark.leak_shell import Invocation, invocations
from squadron.benchmark.transcripts import ToolCall

URL_FIELD = "url"
HOST_CLI = "gh"
#: ``gh`` commands that read nothing from a repository. Any other command counts.
HOST_CLI_LOCAL_COMMANDS = frozenset(
    {"auth", "version", "--version", "help", "--help", "-h", "config", "completion", "alias"}
)
HOST_CLI_REPOSITORY_VIEW = ("repo", "view")
HOST_CLI_JSON_OPTION = "--json"
#: ``gh repo view --json`` fields that say which repository this is and nothing about its
#: content. Without ``--json`` the command prints the README of the default branch.
REPOSITORY_IDENTITY_FIELDS = frozenset(
    {"nameWithOwner", "name", "owner", "url", "sshUrl", "defaultBranchRef", "isPrivate", "isFork"}
)
GIT = "git"
URL_FETCHERS = frozenset({"curl", "wget"})
#: ``git`` subcommands that take the repository to read from, or record it as a remote.
GIT_REPOSITORY_SUBCOMMANDS = frozenset(
    {"clone", "fetch", "pull", "ls-remote", "remote", "submodule", "config"}
)
#: Global git options that take their value as the next word, or as ``--name=value``.
GIT_DIRECTORY_OPTIONS = frozenset({"-C", "--git-dir", "--work-tree"})
#: Environment variables that aim git at a directory, like the options above.
GIT_DIRECTORY_VARIABLES = frozenset({"GIT_DIR", "GIT_WORK_TREE"})
#: Other global git options that take a value as the next word.
GIT_VALUE_OPTIONS = frozenset({"-c", "--namespace", "--exec-path", "--super-prefix"})
PIP = "pip"
PIP_PROGRAMS = frozenset({"pip", "pip3"})
PYTHON_MODULE_FLAG = "-m"
PIP_INSTALL = "install"
UV = "uv"
UV_ADD = "add"
UV_TOOL = "tool"
UVX = "uvx"
PIPX = "pipx"
_PYTHON_PROGRAM = re.compile(r"python[\d.]*")
_NAME_END = re.compile(r"[=<>!~@\[;\s]")
_GIT_SUFFIX = ".git"
#: git's ``[user@]host:owner/repo`` remote form, which has no ``//``.
_HOST_COLON_PATH = re.compile(r"(?P<host>[^/:]+):(?P<path>.+)")


def _git_directory_values(args: tuple[str, ...]) -> Iterator[str]:
    """Values of ``-C`` / ``--git-dir`` / ``--work-tree`` among git's global options."""
    words = iter(args)
    for word in words:
        name, equals, inline = word.partition("=")
        if name in GIT_DIRECTORY_OPTIONS and equals:
            yield inline
        elif word in GIT_DIRECTORY_OPTIONS:
            value = next(words, None)
            if value is not None:
                yield value
        elif word in GIT_VALUE_OPTIONS:
            next(words, None)
        elif not word.startswith("-"):
            return  # the subcommand ends the global options


def git_subcommand(args: tuple[str, ...]) -> tuple[str | None, tuple[str, ...]]:
    """The subcommand and the words after it, skipping git's global options."""
    words = iter(enumerate(args))
    for index, word in words:
        if word in GIT_DIRECTORY_OPTIONS or word in GIT_VALUE_OPTIONS:
            next(words, None)
        elif not word.startswith("-"):
            return word, args[index + 1 :]
    return None, ()


def _git_environment_values(assignments: tuple[str, ...]) -> Iterator[str]:
    """Values of ``GIT_DIR`` / ``GIT_WORK_TREE`` set before the command (``GIT_DIR=/x git log``)."""
    for assignment in assignments:
        name, _, value = assignment.partition("=")
        if name in GIT_DIRECTORY_VARIABLES:
            yield value


def _git_hits(invocation: Invocation, rules: LeakRules) -> list[str]:
    aimed = (*_git_directory_values(invocation.args), *_git_environment_values(invocation.assignments))
    hits = [
        f"git {value}"
        for value in aimed
        if not is_under(resolve_in_tree(value, rules), (*rules.tree_roots, *rules.confined_roots))
    ]
    subcommand, rest = git_subcommand(invocation.args)
    if subcommand in GIT_REPOSITORY_SUBCOMMANDS:
        hits.extend(f"git {subcommand} {word}" for word in rest if names_repository(word, rules))
    return hits


def _with_authority(url: str) -> str:
    """*url* in a form ``urlparse`` splits into host and path."""
    if "//" in url:
        return url
    remote = _HOST_COLON_PATH.fullmatch(url)
    return f"//{remote['host']}/{remote['path']}" if remote else f"//{url}"


def names_repository(url: str, rules: LeakRules) -> bool:
    """Whether *url*'s path holds the case's ``<owner>/<repo>`` as consecutive segments."""
    parsed = urlparse(_with_authority(url))
    segments = [segment.lower() for segment in PurePosixPath(parsed.path).parts if segment != "/"]
    segments = [segment.removesuffix(_GIT_SUFFIX) for segment in segments]
    wanted = [rules.host_owner.lower(), rules.host_repo.lower().removesuffix(_GIT_SUFFIX)]
    return any(segments[i : i + 2] == wanted for i in range(len(segments)))


def _fetch_hits(invocation: Invocation, rules: LeakRules) -> list[str]:
    return [arg for arg in invocation.args if "/" in arg and names_repository(arg, rules)]


def _json_fields(args: tuple[str, ...]) -> frozenset[str] | None:
    """The fields a ``--json a,b`` / ``--json=a,b`` option asks for; ``None`` without one."""
    words = iter(args)
    for word in words:
        name, equals, inline = word.partition("=")
        if name == HOST_CLI_JSON_OPTION:
            value = inline if equals else next(words, "")
            return frozenset(field for field in value.split(",") if field)
    return None


def _host_cli_reads_repository(args: tuple[str, ...]) -> bool:
    """Whether a ``gh`` invocation asks the code host for anything a repository holds."""
    if not args or args[0] in HOST_CLI_LOCAL_COMMANDS:
        return False
    if args[:2] == HOST_CLI_REPOSITORY_VIEW:
        fields = _json_fields(args[2:])
        return fields is None or not fields <= REPOSITORY_IDENTITY_FIELDS
    return True


def git_host_hits(call: ToolCall, rules: LeakRules) -> list[str]:
    """What in *call* reaches the git remote or code host, in call order."""
    hits: list[str] = []
    url = call.input.get(URL_FIELD)
    if isinstance(url, str) and names_repository(url, rules):
        hits.append(url)
    command = call.input.get(COMMAND_FIELD)
    for invocation in invocations(command) if isinstance(command, str) else []:
        if invocation.program == HOST_CLI:
            if _host_cli_reads_repository(invocation.args):
                hits.append(" ".join([HOST_CLI, *invocation.args]))
        elif invocation.program == GIT:
            hits.extend(_git_hits(invocation, rules))
        elif invocation.program in URL_FETCHERS:
            hits.extend(_fetch_hits(invocation, rules))
    return hits


def _names_distribution(word: str, rules: LeakRules) -> bool:
    if word.startswith("-"):
        return False
    return normalize_distribution(_NAME_END.split(word, maxsplit=1)[0]) == rules.distribution_name


def _installs_or_runs(invocation: Invocation) -> tuple[str, ...] | None:
    """The words after an install/run subcommand, ``None`` when the command is neither."""
    program, args = invocation.program, invocation.args
    if _PYTHON_PROGRAM.fullmatch(program) and args[:2] == (PYTHON_MODULE_FLAG, PIP):
        program, args = PIP, args[2:]
    if program in PIP_PROGRAMS:
        return args[1:] if args[:1] == (PIP_INSTALL,) else None
    if program == UV:
        if args[:2] == (PIP, PIP_INSTALL):
            return args[2:]
        return args[1:] if args[:1] in ((UV_ADD,), (UV_TOOL,)) else None
    return args if program in (UVX, PIPX) else None


def own_package_hits(call: ToolCall, rules: LeakRules) -> list[str]:
    """Installs or runs of the project's own distribution in *call*'s shell command."""
    command = call.input.get(COMMAND_FIELD)
    if not isinstance(command, str):
        return []
    hits: list[str] = []
    for invocation in invocations(command):
        after = _installs_or_runs(invocation)
        if after is not None and any(_names_distribution(word, rules) for word in after):
            hits.append(" ".join([invocation.program, *invocation.args]))
    return hits
