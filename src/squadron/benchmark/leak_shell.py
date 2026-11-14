"""Shell command parsing shared by the leak rules (slice 424 D7).

Rules match on parsed tokens, never on substrings of the command line: ``echo gh`` does not
invoke ``gh``. Tokenizing is lenient: unbalanced quoting falls back to word-like runs
instead of failing, because a command the shell would reject is still evidence of intent.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath

#: Characters that end a token on their own (shell operators and newline).
_PUNCTUATION = ";&|()<>`\n"
_INLINE_WHITESPACE = " \t\r"
#: Tokens that end one simple command and start the next. Redirections stay in a command.
# A backtick opens and closes a command substitution, so it separates commands like ``(``.
COMMAND_SEPARATORS = frozenset({";", "&", "&&", "|", "||", "(", ")", "`", "\n"})
#: Programs that run their arguments as a command: the real program follows them.
WRAPPER_PROGRAMS = frozenset(
    {"env", "command", "exec", "nohup", "time", "sudo", "timeout", "nice", "xargs", "stdbuf", "setsid"}
)
#: What follows a wrapper before the real program: its options and a number or duration
#: (``timeout 30``, ``nice -n 5``).
_WRAPPER_ARGUMENT = re.compile(r"-.*|\d+(\.\d+)?[smhd]?")
#: Per wrapper, the options that take their value as the next word (``sudo -u bob gh``: ``bob``
#: is not the program). A wrapper not listed has none; an attached value (``-ubob``) needs no entry.
WRAPPER_VALUE_OPTIONS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}),
    "env": frozenset({"-u", "-C", "-S"}),
    "timeout": frozenset({"-s", "-k"}),
    "nice": frozenset({"-n"}),
    "xargs": frozenset({"-I", "-n", "-P", "-L", "-s", "-d", "-E", "-a"}),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
    "time": frozenset({"-f", "-o"}),
    "exec": frozenset({"-a"}),
}
#: Shells whose ``-c`` argument is itself a command line.
SHELL_PROGRAMS = frozenset({"sh", "bash", "zsh", "dash"})
#: ``eval`` runs its joined arguments as a command line.
EVAL_PROGRAM = "eval"
_SHELL_COMMAND_FLAG = re.compile(r"-[a-z]*c[a-z]*")
#: How many times a token containing spaces (``bash -c "cat /x"``) is tokenized again.
MAX_NESTED_COMMAND_DEPTH = 2
#: Fallback tokens: command separators stay their own tokens (``ls; gh x "3`` still shows
#: ``gh`` as a command), then word-like runs. Quotes and redirections are dropped.
_TOKEN_FALLBACK = re.compile(r"""&&|\|\||[;&|()`\n]|[^\s'"`;|&<>()]+""")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


@dataclass(frozen=True)
class Invocation:
    """One simple command: the program (basename), its arguments and the ``NAME=value``
    assignments that preceded it (``GIT_DIR=/x git log``), kept so rules can judge them."""

    program: str
    args: tuple[str, ...]
    assignments: tuple[str, ...] = ()


def command_tokens(command: str, depth: int = 0) -> list[str]:
    """Shell tokens of *command*; operators split off, nested quoted commands tokenized too."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=_PUNCTUATION)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.whitespace = _INLINE_WHITESPACE
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quoting: shlex cannot say where tokens end, so take every word-like run.
        return _TOKEN_FALLBACK.findall(command)
    if depth >= MAX_NESTED_COMMAND_DEPTH:
        return tokens
    nested = [t for token in tokens if " " in token for t in command_tokens(token, depth + 1)]
    return [*tokens, *nested]


def _simple_commands(tokens: list[str]) -> list[list[str]]:
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token in COMMAND_SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [command for command in commands if command]


def _strip_prefixes(command: list[str]) -> tuple[list[str], list[str]]:
    """Split off leading ``NAME=value`` assignments and wrapper programs (``env gh`` runs ``gh``).

    Returns the assignments and the words from the real program on. A wrapper option's
    separate value (``sudo -u bob gh``) is dropped with the option.
    """
    rest = list(command)
    assignments: list[str] = []
    wrapper: str | None = None
    while rest:
        word = rest[0]
        if PurePosixPath(word).name in WRAPPER_PROGRAMS:
            wrapper = PurePosixPath(word).name
        elif _ASSIGNMENT.match(word):
            assignments.append(word)
        elif wrapper is not None and _WRAPPER_ARGUMENT.fullmatch(word):
            if word in WRAPPER_VALUE_OPTIONS.get(wrapper, frozenset()) and len(rest) > 1:
                rest.pop(0)  # the option's value is the next word
        else:
            break
        rest.pop(0)
    return assignments, rest


def _shell_command_argument(invocation: Invocation) -> str | None:
    """The command line a ``sh -c`` / ``bash -lc`` / ``eval`` invocation runs, else ``None``."""
    if invocation.program == EVAL_PROGRAM:
        return " ".join(invocation.args) or None
    if invocation.program not in SHELL_PROGRAMS:
        return None
    for index, arg in enumerate(invocation.args[:-1]):
        if _SHELL_COMMAND_FLAG.fullmatch(arg):
            return invocation.args[index + 1]
    return None


def invocations(command: str, depth: int = 0) -> list[Invocation]:
    """Every simple command in *command*, including those a ``sh -c`` argument runs."""
    found: list[Invocation] = []
    for simple in _simple_commands(command_tokens(command)):
        assignments, words = _strip_prefixes(simple)
        if not words:
            continue
        invocation = Invocation(
            program=PurePosixPath(words[0]).name,
            args=tuple(words[1:]),
            assignments=tuple(assignments),
        )
        found.append(invocation)
        nested = _shell_command_argument(invocation)
        if nested is not None and depth < MAX_NESTED_COMMAND_DEPTH:
            found.extend(invocations(nested, depth + 1))
    return found
