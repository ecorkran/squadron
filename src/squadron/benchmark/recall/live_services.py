"""The collaborators only ``sq benchmark recall run`` needs (slice 430 D6, D9).

Grouped so the services seam stays one object: production fills them with the real alias
registry, auth check, transcript leak scan and kind sandboxes; tests pass doubles.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from squadron.benchmark.auth_check import run_auth_check
from squadron.benchmark.leak_rule_source import installed_package_location, uv_cache_dir
from squadron.benchmark.production_deps import resolve_sq_path
from squadron.benchmark.recall.kinds import KindContext
from squadron.benchmark.recall.leak_check import LeakInputs, TranscriptLeakChecker, leak_judgeable
from squadron.benchmark.recall.run_bound import AuthCheck
from squadron.benchmark.recall.run_loop import KindSandboxFactory, SandboxFactory
from squadron.benchmark.recall.run_plan import ConfigFor
from squadron.benchmark.recall.stage_identity import live_stage_config
from squadron.benchmark.recall.stage_runner import LeakChecker
from squadron.benchmark.sandbox import RECALL_SANDBOXES
from squadron.config.keys import BENCHMARK_AUTH_PROBE_TIMEOUT_KEY
from squadron.config.manager import get_positive_int_config
from squadron.core.process_runner import ProcessRunner
from squadron.providers.base import ProfileName


@dataclass(frozen=True)
class LiveRunServices:
    harness_env: Mapping[str, str]
    sq_path: Callable[[], str]
    auth_check: AuthCheck
    auth_timeout: Callable[[], float]
    leak_checker: Callable[[ProcessRunner], LeakChecker]
    leak_judgeable: Callable[[ProfileName], bool]
    config_for: ConfigFor
    sandboxes: Callable[[KindContext, Path], SandboxFactory]


def production_leak_checker(runner: ProcessRunner) -> LeakChecker:
    inputs = LeakInputs(
        real_home=Path.home(),
        install_location=installed_package_location(),
        uv_cache=uv_cache_dir(runner),
    )
    return TranscriptLeakChecker(inputs)


def build_production_live_services(repo_root: Path) -> LiveRunServices:
    cwd = str(repo_root)
    return LiveRunServices(
        # The harness's own environment: ScrubbedEnvironment copies only what it names.
        harness_env=dict(os.environ),
        sq_path=resolve_sq_path,
        auth_check=run_auth_check,
        auth_timeout=lambda: float(get_positive_int_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY, cwd=cwd)),
        leak_checker=production_leak_checker,
        leak_judgeable=leak_judgeable,
        config_for=live_stage_config,
        sandboxes=lambda context, root: KindSandboxFactory(
            context, root / RECALL_SANDBOXES, uuid.uuid4().hex[:8]
        ),
    )
