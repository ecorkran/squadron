"""Planning refusals and the case-runner registry (slice 424 Task 24)."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from squadron.benchmark import case_runners
from squadron.benchmark.auth_check import AuthAnswer
from squadron.benchmark.bench_plan import BenchConfig, BenchmarkRefusal, Caps
from squadron.benchmark.bench_refusals import check_plan
from squadron.benchmark.case_runners import (
    ProducerRun,
    ReplaySandbox,
    case_runner_for,
    register_case_runner,
)
from squadron.benchmark.replay_outcome import ProducerClassification
from squadron.benchmark.transcripts import TranscriptResult, TranscriptSource
from squadron.config.keys import BENCHMARK_PLANNED_SAMPLES_KEY
from squadron.core.process_runner import ProcessResult
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    FixQualification,
)
from squadron.pipeline.state import RunState
from squadron.providers.base import ProfileName
from tests.benchmark.test_fix_case_runner import fix_case

SDK_CONFIG = BenchConfig("opus", "claude-opus-5-5", "sdk", "high")
OAUTH_CONFIG = BenchConfig("sol", "sol-model", "openai-oauth", None)
API_CONFIG = BenchConfig("gpt", "gpt-model", "openai", None)
AUTH_OK: Mapping[ProfileName, AuthAnswer] = {
    ProfileName.SDK: AuthAnswer.YES,
    ProfileName.OPENAI_OAUTH: AuthAnswer.YES_CARRYOVER_REPLACED,
    ProfileName.OPENAI: AuthAnswer.YES,
}


class _Source:
    def read(self, home: object) -> TranscriptResult:  # pragma: no cover - never called
        raise AssertionError("a planning check must not read a transcript")


class _Runner:
    """A runner double: any call is a test failure."""

    pipeline = "fix"
    producer_step = "fix"

    def requalify(
        self, case: BenchmarkCase, environment: EnvironmentIdentity
    ) -> FixQualification | CandidateRejection:
        raise AssertionError("a planning check must not requalify")

    def run(
        self,
        case: BenchmarkCase,
        config: BenchConfig,
        sandbox: ReplaySandbox,
        caps: Caps,
        record_id: str,
    ) -> ProducerRun:
        raise AssertionError("a planning check must not run a producer")

    def classify(
        self,
        case: BenchmarkCase,
        process: ProcessResult,
        state: RunState | None,
        head_before: str,
        head_after: str,
    ) -> ProducerClassification:
        raise AssertionError("a planning check must not classify a run")


def _runners(*kinds: CaseKind) -> Callable[[CaseKind], _Runner | None]:
    runner = _Runner()
    return lambda kind: runner if kind in kinds else None


def _sources(*profiles: ProfileName) -> Callable[[ProfileName], TranscriptSource | None]:
    source = _Source()
    return lambda profile: source if profile in profiles else None


SOURCES = _sources(ProfileName.SDK, ProfileName.OPENAI_OAUTH)


def _check(
    *,
    cases: list[BenchmarkCase] | None = None,
    configs: list[BenchConfig] | None = None,
    samples: int | None = 3,
    runners: Callable[[CaseKind], _Runner | None] | None = None,
    sources: Callable[[ProfileName], TranscriptSource | None] = SOURCES,
    auth: Mapping[ProfileName, AuthAnswer] = AUTH_OK,
) -> None:
    check_plan(
        cases if cases is not None else [fix_case()],
        configs if configs is not None else [SDK_CONFIG, OAUTH_CONFIG],
        samples,
        runners if runners is not None else _runners(CaseKind.FIX),
        sources,
        auth,
    )


class TestRegistry:
    def test_registered_runner_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(case_runners, "_RUNNERS", {})
        runner = _Runner()
        register_case_runner(CaseKind.FIX, runner)
        assert case_runner_for(CaseKind.FIX) is runner

    def test_unregistered_kind_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(case_runners, "_RUNNERS", {})
        assert case_runner_for(CaseKind.SLICE) is None


class TestRefusals:
    def test_valid_plan_passes(self) -> None:
        _check()

    def test_profile_without_a_transcript_source_is_refused(self) -> None:
        with pytest.raises(BenchmarkRefusal) as raised:
            _check(configs=[API_CONFIG])
        assert str(raised.value) == (
            "profile openai has no transcript source; its replays cannot be leak-scanned"
        )

    def test_profile_without_a_passing_auth_check_is_refused_naming_the_command(self) -> None:
        auth = {**AUTH_OK, ProfileName.OPENAI_OAUTH: AuthAnswer.NO}
        with pytest.raises(BenchmarkRefusal, match="sq benchmark auth-check") as raised:
            _check(auth=auth)
        assert "openai-oauth" in str(raised.value)

    def test_profile_never_auth_checked_is_refused(self) -> None:
        with pytest.raises(BenchmarkRefusal, match="no passing auth check"):
            _check(auth={})

    def test_case_kind_without_a_runner_is_refused_naming_kind_and_slice(self) -> None:
        slice_case = fix_case().model_copy(update={"kind": CaseKind.SLICE})
        with pytest.raises(BenchmarkRefusal) as raised:
            _check(cases=[slice_case])
        message = str(raised.value)
        assert slice_case.case_id in message
        assert "'slice'" in message
        assert "426" in message

    @pytest.mark.parametrize("source_ref", ["", " ", "issue-1", "owner/repo"])
    def test_fix_case_without_a_usable_issue_ref_is_refused_naming_the_case(
        self, source_ref: str
    ) -> None:
        refused = fix_case(source_ref)
        with pytest.raises(BenchmarkRefusal, match="no provenance issue ref") as raised:
            _check(cases=[refused])
        assert refused.case_id in str(raised.value)

    def test_samples_unset_names_flag_and_config_key(self) -> None:
        with pytest.raises(BenchmarkRefusal) as raised:
            _check(samples=None)
        assert "--samples" in str(raised.value)
        assert BENCHMARK_PLANNED_SAMPLES_KEY in str(raised.value)

    def test_config_with_no_profile_is_refused(self) -> None:
        with pytest.raises(BenchmarkRefusal, match="no provider profile"):
            _check(configs=[BenchConfig("odd", "m", None, None)])

    def test_check_never_calls_a_runner_or_a_transcript_source(self) -> None:
        # _Runner and _Source raise if touched; a passing plan and a refused one both finish.
        _check()
        with pytest.raises(BenchmarkRefusal):
            _check(sources=_sources())
