"""Seed a scratch HOME for slice 174's Verification Walkthrough (not a test).

Run with HOME pointing at a scratch directory, from a scratch project directory:

    HOME=$S/home python -m tests.pipeline.walkthrough_seed $S/proj --stale-pid <pid>

*stale-pid* must be a live process (e.g. a background ``sleep 600``). Prints one
``<label> <run-id>`` line per seeded run. Writes only under HOME and the project.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.state import StateManager
from tests.pipeline.liveness_support import exited_pid
from tests.pipeline.run_listing_support import (
    STEP_NAMES,
    begin,
    begin_owned,
    end,
    fail_at,
    pause_at,
    write_step_pipeline,
)


def seed(project: Path, stale_pid: int) -> dict[str, str]:
    write_step_pipeline(project / "project-documents/user/pipelines", "steps")
    sm = StateManager()
    paused = begin(sm, "steps", {"slice": "174", "model": "opus", "note": "a long param " * 4})
    failed = begin(sm, "steps", {"slice": "175"})
    gone = begin(sm, "gone", {"slice": "176"})
    gone_paused = begin(sm, "gone", {"slice": "180"})
    orphan = begin_owned(sm, "steps", exited_pid(), {"slice": "177"})
    stale = begin_owned(sm, "steps", stale_pid, {"slice": "178"})
    unowned = begin(sm, "steps", {"slice": "179"})
    pause_at(sm, paused, STEP_NAMES[1], done=[STEP_NAMES[0]])
    fail_at(sm, failed, STEP_NAMES[0])
    end(sm, gone, ExecutionStatus.COMPLETED)
    pause_at(sm, gone_paused, "design-0")
    sm.record_step_started(orphan, STEP_NAMES[1])
    state = sm.load(stale)
    state.heartbeat_at = datetime(2026, 1, 1, tzinfo=UTC)
    sm._save(state)  # pyright: ignore[reportPrivateUsage]
    (sm.runs_dir / "run-20261001-junk-00000000.json").write_text("{not json")
    return {
        "paused": paused,
        "failed": failed,
        "gone": gone,
        "gone-paused": gone_paused,
        "orphan": orphan,
        "stale": stale,
        "unowned": unowned,
        "junk": "run-20261001-junk-00000000",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--stale-pid", type=int, required=True)
    args = parser.parse_args()
    for label, run_id in seed(args.project, args.stale_pid).items():
        print(label, run_id)


if __name__ == "__main__":
    main()
