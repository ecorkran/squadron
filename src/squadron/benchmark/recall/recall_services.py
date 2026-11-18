"""The services ``sq benchmark recall`` commands are given: the commands' one seam (slice 430).

``build_production_recall_services`` fills this with the real collaborators; command tests
pass doubles, so no test runs a model, a sandbox outside fixtures, or git on real repos.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.bench_lock import BenchmarkLock
from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.recall.kinds import KindContext
from squadron.benchmark.recall.live_services import LiveRunServices, build_production_live_services
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.benchmark.recall.scoring_select import StageIdentityResolver
from squadron.benchmark.recall.stage_identity import LiveStageResolver
from squadron.benchmark.sandbox import benchmark_root
from squadron.config.keys import BENCHMARK_RECALL_FETCH_TIMEOUT_KEY
from squadron.config.manager import get_config, get_positive_int_config
from squadron.core.process_runner import ProcessRunner, SubprocessRunner
from squadron.metrology.identity import derive_project_id
from squadron.metrology.project_id import ProjectId
from squadron.metrology.store import MetrologyStore, resolve_store_dir

_logger = logging.getLogger(__name__)
#: The benchmark lock id every writing recall command takes (D9).
RECALL_LOCK_ID = "recall"


@dataclass(frozen=True)
class RecallServices:
    repo_root: Path
    store: RecallRecordStore
    process_runner: ProcessRunner
    #: The benchmark root: lock, sandboxes, scrubbed homes and ``recall-out/``.
    bench_root: Path
    clock: Callable[[], datetime]
    #: A config value by key, ``None`` when unset.
    read_config: Callable[[str], object | None]
    fetch_timeout: float
    project_id: Callable[[], ProjectId]
    #: How ``report`` resolves a recipe alias to a live stage identity (D4).
    stage_resolver: StageIdentityResolver
    #: What only ``run`` needs: credentials, ``sq``, auth check, leak scan, sandboxes.
    live: LiveRunServices

    def kind_context(self) -> KindContext:
        return KindContext(self.process_runner, self.fetch_timeout, self.project_id())


RecallServicesFactory = Callable[[Path], RecallServices]


@contextmanager
def recall_lock(services: RecallServices) -> Iterator[None]:
    """Hold the recall benchmark lock; a live holder is an ERROR and a refusal naming its pid."""
    try:
        lock = BenchmarkLock.acquire(services.bench_root, RECALL_LOCK_ID, services.process_runner)
    except BenchmarkRefusal as exc:
        _logger.error("recall lock refused: %s", exc)
        raise RecallRefusal(str(exc)) from exc
    try:
        yield
    finally:
        lock.release()


def build_production_recall_services(repo_root: Path) -> RecallServices:
    cwd = str(repo_root)
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)  # noqa: E731
    return RecallServices(
        repo_root=repo_root,
        store=RecallRecordStore(MetrologyStore(store_dir=resolve_store_dir(cwd=cwd)), clock),
        process_runner=SubprocessRunner(),
        bench_root=benchmark_root(),
        clock=clock,
        read_config=lambda key: get_config(key, cwd=cwd),
        fetch_timeout=float(get_positive_int_config(BENCHMARK_RECALL_FETCH_TIMEOUT_KEY, cwd=cwd)),
        project_id=lambda: derive_project_id(cwd),
        stage_resolver=LiveStageResolver(),
        live=build_production_live_services(repo_root),
    )
