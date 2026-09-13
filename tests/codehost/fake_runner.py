"""A scripted ``ProcessRunner`` for testing code-host calls.

Deliberately not a ``MagicMock``. An unscripted argv raises immediately, so a
test cannot pass on a process the implementation should never have run — the
failure mode a permissive default would hide.

Kept a plain class rather than a fixture so ``tests/core`` can use it too.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from squadron.core.process_runner import ProcessResult

#: argv fragments that identify a call as mutating the host. 384 asserts
#: "zero writes without --post" as one check against ``write_calls()``.
_WRITE_MARKERS: tuple[tuple[str, ...], ...] = (
    ("-X", "POST"),
    ("-X", "PATCH"),
    ("pr", "create"),
)


@dataclass(frozen=True)
class RecordedCall:
    """One invocation, with everything a test might need to assert on."""

    argv: tuple[str, ...]
    cwd: str | None
    timeout: float
    env: Mapping[str, str] | None
    stdin: str | None


class UnscriptedCallError(AssertionError):
    """The implementation ran a process the test did not script."""


class FakeProcessRunner:
    """Answers scripted argv prefixes in order; raises on anything else."""

    def __init__(self, script: Sequence[tuple[Sequence[str], ProcessResult | Exception]]) -> None:
        self._script = [(tuple(prefix), outcome) for prefix, outcome in script]
        self.calls: list[RecordedCall] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        argv_tuple = tuple(argv)
        self.calls.append(RecordedCall(argv=argv_tuple, cwd=cwd, timeout=timeout, env=env, stdin=stdin))
        for index, (prefix, outcome) in enumerate(self._script):
            if argv_tuple[: len(prefix)] == prefix:
                del self._script[index]
                # A scripted Exception is raised, not returned: this is how a
                # wedged or missing host binary is produced in a test.
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise UnscriptedCallError(f"unscripted call: {' '.join(argv_tuple)}")

    def write_calls(self) -> list[RecordedCall]:
        """Return the recorded calls that would mutate the host."""
        return [
            call
            for call in self.calls
            if any(_contains(call.argv, marker) for marker in _WRITE_MARKERS)
        ]


def _contains(argv: tuple[str, ...], marker: tuple[str, ...]) -> bool:
    """Return whether ``marker`` appears as consecutive items of ``argv``."""
    return any(
        argv[index : index + len(marker)] == marker for index in range(len(argv) - len(marker) + 1)
    )
