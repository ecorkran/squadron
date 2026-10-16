"""A runner for sandbox tests: real git and ps, scripted cf (slice 177 D3)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from squadron.core.process_runner import ProcessResult, SubprocessRunner


class HybridRunner:
    """Runs git and ps for real; answers ``cf`` from a script of failures and a project list."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.cf_failures: dict[tuple[str, ...], str] = {}  # argv prefix -> stderr
        self.cf_projects: list[dict[str, str]] = []
        self._real = SubprocessRunner()

    def cf_calls(self) -> list[tuple[str, ...]]:
        return [call[1:] for call in self.calls if call[0] == "cf"]

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        call = tuple(argv)
        self.calls.append(call)
        if call[0] != "cf":
            return self._real.run(argv, cwd=cwd, timeout=timeout, env=env, stdin=stdin)
        for prefix, stderr in self.cf_failures.items():
            if call[1 : 1 + len(prefix)] == prefix:
                return ProcessResult(argv=call, returncode=1, stdout="", stderr=stderr)
        stdout = json.dumps(self.cf_projects) if call[1:3] == ("project", "list") else ""
        return ProcessResult(argv=call, returncode=0, stdout=stdout, stderr="")
