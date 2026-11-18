"""Shared pieces of the ``sq benchmark recall`` command modules (slice 430)."""

from __future__ import annotations

from squadron.benchmark.recall.recall_services import (
    RecallRefusal,
    RecallServices,
    RecallServicesFactory,
)
from squadron.cli.commands.benchmark_common import repo_root_for
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.errors import MetrologyStoreError

#: Failures reported as ``Error: <message>`` with exit 1 rather than a traceback.
REFUSED_ERRORS = (RecallRefusal, MetrologyStoreError, ValueError)


def open_services(services_factory: RecallServicesFactory) -> RecallServices:
    return services_factory(repo_root_for(SubprocessRunner(), None))
