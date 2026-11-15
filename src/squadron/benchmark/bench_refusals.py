"""Planning refusals for ``sq benchmark run`` (slice 424 D5, D6, D8).

Everything here runs before any sandbox exists or any model is called, and never calls a
runner or an invoker: it only reads what the plan and the registries already say.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from squadron.benchmark.auth_check import AuthAnswer
from squadron.benchmark.bench_plan import BenchConfig, BenchmarkRefusal
from squadron.benchmark.case_runners import CaseKindRunner
from squadron.benchmark.fix_case_candidate import issue_number
from squadron.benchmark.transcripts import TranscriptSource
from squadron.config.keys import BENCHMARK_PLANNED_SAMPLES_KEY
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind
from squadron.providers.base import ProfileName

SAMPLES_FLAG = "--samples"
AUTH_CHECK_COMMAND = "sq benchmark auth-check"
AUTH_YES = frozenset({AuthAnswer.YES, AuthAnswer.YES_CARRYOVER_REPLACED})


def _check_samples(samples: int | None) -> int:
    if samples is None:
        raise BenchmarkRefusal(
            f"no sample count: set {SAMPLES_FLAG} or the config key {BENCHMARK_PLANNED_SAMPLES_KEY}"
        )
    return samples


def _check_profile(
    config: BenchConfig,
    transcript_sources: Callable[[ProfileName], TranscriptSource | None],
    auth_state: Mapping[ProfileName, AuthAnswer],
) -> None:
    if config.profile is None:
        raise BenchmarkRefusal(f"model alias '{config.alias}' resolves to no provider profile")
    profile = ProfileName(config.profile)
    if transcript_sources(profile) is None:
        raise BenchmarkRefusal(
            f"profile {profile.value} has no transcript source; its replays cannot be leak-scanned"
        )
    if auth_state.get(profile) not in AUTH_YES:
        raise BenchmarkRefusal(
            f"profile {profile.value} (alias '{config.alias}') has no passing auth check; "
            f"run `{AUTH_CHECK_COMMAND}` first"
        )


def _check_case(case: BenchmarkCase, runners: Callable[[CaseKind], CaseKindRunner | None]) -> None:
    if runners(case.kind) is None:
        raise BenchmarkRefusal(
            f"case {case.case_id} is of kind '{case.kind.value}', which has no case runner"
        )
    if case.kind is CaseKind.FIX and issue_number(case) is None:
        raise BenchmarkRefusal(
            f"fix case {case.case_id} has no provenance issue ref the producer can use "
            f"(got {case.provenance.source_ref!r}); it needs the issue number"
        )


def check_plan(
    cases: Sequence[BenchmarkCase],
    configs: Sequence[BenchConfig],
    samples: int | None,
    runners: Callable[[CaseKind], CaseKindRunner | None],
    transcript_sources: Callable[[ProfileName], TranscriptSource | None],
    auth_state: Mapping[ProfileName, AuthAnswer],
) -> int:
    """Raise ``BenchmarkRefusal`` for the first problem found; else return the sample count."""
    checked_samples = _check_samples(samples)
    for config in configs:
        _check_profile(config, transcript_sources, auth_state)
    for case in cases:
        _check_case(case, runners)
    return checked_samples
