"""Grouping stored replays into judge jobs (slice 177 D5)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import PairwiseJudgment, ProducerReplay, ReplayPhase
from squadron.replay.judge_jobs import build_jobs, judge_jobs, total_calls
from squadron.replay.judging import JudgeReply
from squadron.replay.start_point import StartPoint
from tests.metrology.replay_builders import make_judge, make_judgment, make_replay

_PROJECT = ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE)
_T0 = datetime(2026, 11, 1, tzinfo=UTC)


class _Reader:
    def __init__(
        self, replays: list[tuple[str, ProducerReplay]], judgments: list[PairwiseJudgment]
    ) -> None:
        self._replays = replays
        self._judgments = judgments

    def list_replays(
        self, project_id: str, phase: ReplayPhase | None = None, replay_set: str | None = None
    ) -> list[tuple[str, ProducerReplay]]:
        return self._replays

    def list_judgments(self, project_id: str, phase: ReplayPhase | None = None, judge: object = None):  # type: ignore[no-untyped-def]
        return self._judgments


def _start(sha: str = "a" * 40) -> StartPoint:
    return StartPoint(
        phase=ReplayPhase.DESIGN,
        slice_index=176,
        slice_name="x",
        artifact_path="x.md",
        original_sha=sha,
        start_sha="b" * 40,
        original_first_draft="# original",
    )


def _replay(draft: str, minutes: int, **kw: object) -> ProducerReplay:
    return make_replay(first_draft=draft, created_at=_T0 + timedelta(minutes=minutes), **kw)  # type: ignore[arg-type]


def test_no_replays_means_no_jobs_and_the_original_is_never_read() -> None:
    def original() -> StartPoint:
        raise AssertionError("the original must not be read when there is nothing to judge")

    jobs = build_jobs(_Reader([], []), _PROJECT, ReplayPhase.DESIGN, 176, make_judge(), original)

    assert jobs == []


def test_replays_group_by_set_and_other_slices_are_ignored() -> None:
    other_slice = make_replay(first_draft="# z").model_copy(update={"slice_index": 999})
    replays = [
        ("r1", _replay("# a", 1, replay_set="set-1")),
        ("r2", _replay("# b", 2, replay_set="set-1")),
        ("r3", _replay("# c", 3, replay_set="set-2")),
        ("r4", other_slice),
    ]

    jobs = build_jobs(
        _Reader(replays, []), _PROJECT, ReplayPhase.DESIGN, 176, make_judge(), lambda: _start()
    )

    assert sorted(len(job.replays) for job in jobs) == [1, 2]
    assert all(job.original_draft == "# original" for job in jobs)


def test_a_changed_original_is_left_out_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    replays = [("r1", _replay("# a", 1)), ("r2", _replay("# b", 2))]

    with caplog.at_level(logging.WARNING):
        (job,) = build_jobs(
            _Reader(replays, []),
            _PROJECT,
            ReplayPhase.DESIGN,
            176,
            make_judge(),
            lambda: _start("f" * 40),
        )

    assert job.original_draft is None
    assert "left out of this set" in caplog.text


def test_existing_judgments_are_attached_to_their_own_set_and_counted() -> None:
    replays = [("r1", _replay("# a", 1)), ("r2", _replay("# b", 2))]
    done = make_judgment()  # a=replay-20261101-aaaaaaaa, b=original:..., replay_set="set-1"
    jobs = build_jobs(
        _Reader(replays, [done]), _PROJECT, ReplayPhase.DESIGN, 176, make_judge(), lambda: _start()
    )

    pairs, calls = total_calls(jobs)

    assert jobs[0].existing == [done]
    assert (pairs, calls) == (3, 6)  # the stored judgment names other contestants


async def test_judge_jobs_adds_up_across_jobs() -> None:
    replays = [
        ("r1", _replay("# a\naaa", 1, replay_set="set-1")),
        ("r2", _replay("# b\nbbb", 2, replay_set="set-1")),
        ("r3", _replay("# c\nccc", 3, replay_set="set-2")),
        ("r4", _replay("# d\nddd", 4, replay_set="set-2")),
    ]
    jobs = build_jobs(
        _Reader(replays, []),
        _PROJECT,
        ReplayPhase.DESIGN,
        176,
        make_judge(),
        lambda: _start(),
    )
    written: list[PairwiseJudgment] = []

    class _Store:
        def write_judgment(self, judgment: PairwiseJudgment) -> str:
            written.append(judgment)
            return "id"

    async def dispatcher(prompt: str) -> JudgeReply:
        return JudgeReply("WINNER: A", None)

    summary = await judge_jobs(jobs, store=_Store(), dispatcher=dispatcher, timeout_s=1)

    assert summary.judged == 6 == len(written)  # two sets x three pairs (two replays + original)
    assert summary.calls == 12 and summary.failed == 0
