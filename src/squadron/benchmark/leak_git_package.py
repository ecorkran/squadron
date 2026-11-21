"""Git, code-host and own-package leak rules (slice 424 D7).

All three match parsed tokens: the program name and its subcommand, never a substring of the
command line. ``echo gh`` and ``echo <distribution>`` invoke nothing and are not hits.

* **Git / code host.** Any ``gh``; ``git`` aimed outside the tree (``-C``, ``--git-dir``,
  ``--work-tree``); ``git clone``, ``fetch``, ``pull``, ``remote add``; a fetch of a URL whose
  path names the case's repository (``curl``, ``wget`` or a fetch tool's ``url`` field). The
  repository is matched as consecutive ``<owner>/<repo>`` path segments, so web, API and raw
  forms on any host of that repository all match.
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
GIT = "git"
URL_FETCHERS = frozenset({"curl", "wget"})
#: ``git`` subcommands that reach the network for a repository.
GIT_NETWORK_SUBCOMMANDS = frozenset({"clone", "fetch", "pull"})
GIT_REMOTE = "remote"
GIT_REMOTE_ADD = "add"
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
    if subcommand in GIT_NETWORK_SUBCOMMANDS:
        hits.append(f"git {subcommand}")
    elif (
        subcommand == GIT_REMOTE
        and next((w for w in rest if not w.startswith("-")), None) == GIT_REMOTE_ADD
    ):
        hits.append("git remote add")
    return hits


def names_repository(url: str, rules: LeakRules) -> bool:
    """Whether *url*'s path holds the case's ``<owner>/<repo>`` as consecutive segments."""
    parsed = urlparse(url if "//" in url else f"//{url}")
    segments = [segment.lower() for segment in PurePosixPath(parsed.path).parts if segment != "/"]
    segments = [segment.removesuffix(_GIT_SUFFIX) for segment in segments]
    wanted = [rules.host_owner.lower(), rules.host_repo.lower().removesuffix(_GIT_SUFFIX)]
    return any(segments[i : i + 2] == wanted for i in range(len(segments)))


def _fetch_hits(invocation: Invocation, rules: LeakRules) -> list[str]:
    return [arg for arg in invocation.args if "/" in arg and names_repository(arg, rules)]


def git_host_hits(call: ToolCall, rules: LeakRules) -> list[str]:
    """What in *call* reaches the git remote or code host, in call order."""
    hits: list[str] = []
    url = call.input.get(URL_FIELD)
    if isinstance(url, str) and names_repository(url, rules):
        hits.append(url)
    command = call.input.get(COMMAND_FIELD)
    for invocation in invocations(command) if isinstance(command, str) else []:
        if invocation.program == HOST_CLI:
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
