"""The recall ``LeakChecker``: 424's transcript scan with the D6 inputs, or ``confined``.

A profile with a transcript source is scanned with ``build_leak_rules`` (unchanged): the
sandbox tree, the call's scrubbed home and output folder are the only allowed roots; the
user's home, the case's source checkout (it holds the fix), the installed squadron, the
uv cache, the case's distribution and its code-host repository are hits. A profile with
no source whose tools are squadron's jailed builtins is ``confined`` with no scan. A
profile with neither cannot be judged and raises; ``run`` refuses such a plan first.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from squadron.benchmark import leak_scan
from squadron.benchmark.leak_rules import LeakRules, build_leak_rules
from squadron.benchmark.recall.stage_ingest import stage_label
from squadron.benchmark.recall.stage_runner import StageContext
from squadron.benchmark.transcripts import TranscriptSource, transcript_source_for
from squadron.metrology.benchmark_replay_models import LeakScanResult
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import DROPPED_LEAK_VERDICTS, RecallLeakVerdict
from squadron.providers.base import ProfileName, ProviderType
from squadron.providers.profiles import get_profile

_logger = logging.getLogger(__name__)

#: Providers whose tool loop runs squadron's builtins, which refuse paths outside the
#: working directory (``tools/builtin/_shared.py``).
JAILED_BUILTIN_PROVIDERS = frozenset({ProviderType.OPENAI})
HOST_REPO_SEPARATOR = "/"

SourceFor = Callable[[ProfileName], TranscriptSource | None]
ScanFn = Callable[[TranscriptSource, Path, LeakRules], LeakScanResult]


class LeakCheckError(ValueError):
    """A profile with neither a transcript source nor jailed builtin tools."""


@dataclass(frozen=True)
class LeakInputs:
    """The per-command scan inputs (D6) that do not depend on the call."""

    real_home: Path
    install_location: Path
    uv_cache: Path


def has_jailed_builtins(profile: ProfileName) -> bool:
    return get_profile(profile).provider in JAILED_BUILTIN_PROVIDERS


def leak_judgeable(profile: ProfileName, source_for: SourceFor = transcript_source_for) -> bool:
    """A call under *profile* can be scanned or is confined; ``run`` refuses otherwise."""
    return source_for(profile) is not None or has_jailed_builtins(profile)


def recall_leak_rules(context: StageContext, inputs: LeakInputs) -> LeakRules:
    """``build_leak_rules`` with D6's inputs for one call."""
    case: RealBugCase = context.stage.case
    owner, _, repo = case.host_repo.partition(HOST_REPO_SEPARATOR)
    return build_leak_rules(
        tree=context.sandbox,
        home=context.home,
        output_dir=context.output_dir,
        real_home=inputs.real_home,
        repo_root=Path(case.repo).expanduser(),
        install_location=inputs.install_location,
        uv_cache=inputs.uv_cache,
        distribution_name=case.distribution,
        host_owner=owner,
        host_repo=repo,
    )


class TranscriptLeakChecker:
    def __init__(
        self,
        inputs: LeakInputs,
        source_for: SourceFor = transcript_source_for,
        scan: ScanFn = leak_scan.scan,
    ) -> None:
        self._inputs = inputs
        self._source_for = source_for
        self._scan = scan

    def check(self, context: StageContext) -> RecallLeakVerdict:
        source = self._source_for(context.profile)
        if source is None:
            if has_jailed_builtins(context.profile):
                return RecallLeakVerdict.CONFINED
            raise LeakCheckError(
                f"profile {context.profile.value} has no transcript source and no jailed builtin tools"
            )
        result = self._scan(source, context.home, recall_leak_rules(context, self._inputs))
        verdict = RecallLeakVerdict(result.verdict.value)
        if verdict in DROPPED_LEAK_VERDICTS:
            detail = result.detail or "; ".join(str(hit) for hit in result.hits[:3])
            _logger.warning(
                "recall %s: leak scan %s: %s", stage_label(context.stage), verdict.value, detail
            )
        return verdict
