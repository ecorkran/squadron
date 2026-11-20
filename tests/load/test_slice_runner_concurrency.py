"""Load test: concurrent slice-case runs under distinct scrubbed homes (slice 426, Task 24).

Required by the load-test tier: the runner registers a cf project and runs a producer in the
environment layer, and a benchmark replays many cases at once. Eight runs at once must each
register under their own scrubbed home on their own branch, share no registry path, and finish
inside a bound (the registration is three quick commands, so a stall means shared state).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from squadron.benchmark.slice_runner import SliceCaseRunner
from squadron.core.process_runner import SubprocessRunner
from tests.benchmark.slice_qualify_support import typical_setup
from tests.benchmark.slice_repos import two_parent_landing
from tests.benchmark.slice_runner_support import (
    CAPS,
    CONFIG,
    SQ_PATH,
    CfRecorder,
    Events,
    Invoker,
    SandboxDouble,
    make_tools_dir,
    registration_factory,
    slice_case,
)

RUNS = 8
BOUND_S = 30.0


def test_eight_concurrent_runs_register_under_their_own_homes_and_branches(tmp_path: Path) -> None:
    events = Events()
    recorder, invoker = CfRecorder(events), Invoker(events)
    setup = typical_setup(tmp_path / "setup", two_parent_landing(tmp_path / "repo"))
    runner = SliceCaseRunner(
        sq_path=SQ_PATH,
        invoker=invoker,
        runner=SubprocessRunner(),
        registration_for=registration_factory(recorder),
        qualify_deps=setup.deps,
        candidate_for=lambda case: setup.candidate,
    )
    tools = make_tools_dir(tmp_path)
    sandboxes = [
        SandboxDouble(tmp_path / "sandboxes", f"sandbox-{n}", tools, detached=True) for n in range(RUNS)
    ]

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=RUNS) as pool:
        futures = [
            pool.submit(runner.run, slice_case(), CONFIG, sandbox, CAPS, f"implreplay-{n}")
            for n, sandbox in enumerate(sandboxes)
        ]
        for future in futures:
            future.result(timeout=BOUND_S)
    elapsed = time.monotonic() - started

    assert elapsed < BOUND_S
    homes = {call.env["HOME"] for call in recorder.calls if call.env is not None}
    assert homes == {str(sandbox.home) for sandbox in sandboxes}  # one home per run, none shared
    registries = {Path(home) / ".config" / "context-forge" for home in homes}
    assert len(registries) == RUNS
    # Each sandbox is its own repository, so all sit on the same slice branch name; the
    # integration target each registers is its own base branch.
    targets = {
        c.argv[-1] for c in recorder.calls if c.argv[1:4] == ("config", "set", "git.integration_branch")
    }
    assert len(targets) == RUNS
    for sandbox in sandboxes:
        own = [c for c in recorder.calls if c.cwd == str(sandbox.tree)]
        assert len(own) == 3  # init, config set, set arch
        assert {c.env["HOME"] for c in own if c.env is not None} == {str(sandbox.home)}
    assert len(invoker.calls) == RUNS
    assert sorted(call[1] for call in invoker.calls) == sorted(s.tree for s in sandboxes)
