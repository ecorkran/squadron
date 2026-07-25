"""Tests for the agreement report."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from squadron.metrology.identity import derive_project_id, derive_result_ref
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import JudgeConfigId, SampleVerdict
from squadron.metrology.report import agreement_report
from squadron.review.models import Verdict

from .conftest import make_sample_verdict


def _sample_for(
    review_file: Path,
    cwd: Path,
    *,
    human_verdict: Verdict = Verdict.PASS,
    judge_config: JudgeConfigId | None = None,
) -> SampleVerdict:
    project_id = derive_project_id(str(cwd))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(cwd))
    sample = make_sample_verdict(
        project_value=project_id.value,
        human_verdict=human_verdict,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    )
    update: dict[str, object] = {"result_ref": result_ref, "project_id": project_id}
    if judge_config is not None:
        update["judge_config"] = judge_config
    return sample.model_copy(update=update)


def test_multi_level_multi_config_yields_multiple_cells_never_one_aggregate(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    tasks_review = write_review_file(
        reviews_dir,
        filename="600-review.judge.tasks-vs-slice.example.md",
        review_type="judge.tasks-vs-slice",
    )
    slice_review = write_review_file(
        reviews_dir,
        filename="601-review.judge.slice-vs-arch.example.md",
        review_type="judge.slice-vs-arch",
    )
    samples = [
        _sample_for(
            tasks_review,
            repo_with_remote,
            judge_config=JudgeConfigId(template_name="judge.tasks-vs-slice", model="model-a"),
        ),
        _sample_for(
            slice_review,
            repo_with_remote,
            judge_config=JudgeConfigId(template_name="judge.slice-vs-arch", model="model-b"),
        ),
    ]

    report = agreement_report(samples, str(repo_with_remote))

    assert len(report.cells) == 2
    levels = {cell.group.artifact_level for cell in report.cells}
    assert levels == {ArtifactLevel.TASKS_VS_SLICE, ArtifactLevel.SLICE_DESIGN_VS_ARCH}


def test_match_rate_and_n_correct_for_agree_disagree_mix(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    judge_config = JudgeConfigId(template_name="judge.slice-vs-arch", model="model-a")

    samples = [
        _sample_for(
            review_file, repo_with_remote, human_verdict=Verdict.PASS, judge_config=judge_config
        ).model_copy(update={"sample_id": "sample-1"}),
        _sample_for(
            review_file, repo_with_remote, human_verdict=Verdict.PASS, judge_config=judge_config
        ).model_copy(update={"sample_id": "sample-2"}),
        _sample_for(
            review_file, repo_with_remote, human_verdict=Verdict.FAIL, judge_config=judge_config
        ).model_copy(update={"sample_id": "sample-3"}),
    ]
    # review file's judge verdict is PASS (make_judge_result default), so
    # samples 1-2 agree, sample 3 disagrees.

    report = agreement_report(samples, str(repo_with_remote))

    assert len(report.cells) == 1
    cell = report.cells[0]
    assert cell.n == 3
    assert cell.match_rate == 2 / 3


def test_below_floor_set_exactly_when_n_under_floor(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> None:
    write_project_config(repo_with_remote, {"metrology.min_evidence_n": 5})
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    judge_config = JudgeConfigId(template_name="judge.slice-vs-arch", model="model-a")
    samples = [
        _sample_for(review_file, repo_with_remote, judge_config=judge_config).model_copy(
            update={"sample_id": f"sample-{i}"}
        )
        for i in range(3)
    ]

    report = agreement_report(samples, str(repo_with_remote))

    assert len(report.cells) == 1
    assert report.cells[0].n == 3
    assert report.cells[0].below_floor is True


def test_stale_sample_excluded_from_match_rate_and_counted(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    sample = _sample_for(review_file, repo_with_remote)

    # Overwrite after capture — content_hash mismatch.
    review_file.write_text(
        review_file.read_text(encoding="utf-8").replace("score: 98.0", "score: 11.0"),
        encoding="utf-8",
    )

    report = agreement_report([sample], str(repo_with_remote))

    assert report.cells == []
    assert report.excluded.stale_judge_result == 1
    assert report.excluded.total_excluded == 1


def test_unversioned_record_segregated_from_hash_bearing_same_name_model(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")

    hash_bearing = JudgeConfigId(
        template_name="judge.slice-vs-arch", model="model-a", template_content_hash="abc123"
    )
    unversioned = JudgeConfigId(template_name="judge.slice-vs-arch", model="model-a")

    samples = [
        _sample_for(review_file, repo_with_remote, judge_config=hash_bearing).model_copy(
            update={"sample_id": "sample-hash"}
        ),
        _sample_for(review_file, repo_with_remote, judge_config=unversioned).model_copy(
            update={"sample_id": "sample-unversioned"}
        ),
    ]

    report = agreement_report(samples, str(repo_with_remote))

    assert len(report.cells) == 2
    assert report.excluded.unversioned == 1
    assert report.excluded.total_excluded == 1


def test_empty_store_yields_empty_report_not_a_crash(repo_with_remote: Path) -> None:
    report = agreement_report([], str(repo_with_remote))

    assert report.cells == []
    assert report.excluded.total_excluded == 0
    assert report.excluded.stale_judge_result == 0
    assert report.excluded.unversioned == 0
