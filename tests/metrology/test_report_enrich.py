"""Tests for the content-verified judge-side join (T7's enrichment pass)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from squadron.metrology.identity import derive_project_id, derive_result_ref
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import JudgeConfigId, JudgeResultRef, SampleVerdict
from squadron.metrology.report import enrich_samples
from squadron.review.models import Verdict

from .conftest import make_sample_verdict


def _sample_for(
    review_file: Path, cwd: Path, *, human_verdict: Verdict = Verdict.PASS
) -> SampleVerdict:
    project_id = derive_project_id(str(cwd))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(cwd))
    return make_sample_verdict(
        project_value=project_id.value,
        human_verdict=human_verdict,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(update={"result_ref": result_ref, "project_id": project_id})


def test_admissible_sample_enriches_with_verdict_source_document_and_level(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    sample = _sample_for(review_file, repo_with_remote)

    enriched = enrich_samples([sample], str(repo_with_remote))

    assert len(enriched) == 1
    result = enriched[0]
    assert result.admissible == "admissible"
    assert result.judge_verdict == Verdict.PASS
    assert result.source_document == "project-documents/user/slices/302-slice.example.md"
    assert result.artifact_level == ArtifactLevel.SLICE_DESIGN_VS_ARCH


def test_overwritten_review_file_enriches_as_stale(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    sample = _sample_for(review_file, repo_with_remote)

    # Re-write with different content — a new content_hash.
    write_review_file(
        reviews_dir,
        filename=review_file.name,
        review_type="judge.slice-vs-arch",
    )
    # make_judge_result() defaults are identical, so force a real diff.
    review_file.write_text(
        review_file.read_text(encoding="utf-8").replace("score: 98.0", "score: 42.0"),
        encoding="utf-8",
    )

    enriched = enrich_samples([sample], str(repo_with_remote))

    assert len(enriched) == 1
    result = enriched[0]
    assert result.admissible == "stale-judge-result"
    assert result.judge_verdict is None


def test_missing_review_file_enriches_as_stale(repo_with_remote: Path) -> None:
    project_id = derive_project_id(str(repo_with_remote))
    sample = make_sample_verdict(
        project_value=project_id.value,
        artifact_level=None,
    ).model_copy(
        update={
            "project_id": project_id,
            "result_ref": JudgeResultRef(
                project_id=project_id.value,
                relative_review_path="project-documents/user/reviews/999-review.judge.gone.md",
                content_hash="deadbeef" * 8,
            ),
        }
    )

    enriched = enrich_samples([sample], str(repo_with_remote))

    assert len(enriched) == 1
    result = enriched[0]
    assert result.admissible == "stale-judge-result"
    assert result.judge_verdict is None


def test_malformed_frontmatter_enriches_as_stale(repo_with_remote: Path) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_file = reviews_dir / "500-review.judge.broken.md"
    review_file.write_text("not frontmatter at all\n", encoding="utf-8")

    project_id = derive_project_id(str(repo_with_remote))
    sample = make_sample_verdict(
        project_value=project_id.value,
        artifact_level=None,
    ).model_copy(
        update={
            "project_id": project_id,
            "result_ref": JudgeResultRef(
                project_id=project_id.value,
                relative_review_path="project-documents/user/reviews/500-review.judge.broken.md",
                content_hash="0" * 64,
            ),
        }
    )

    enriched = enrich_samples([sample], str(repo_with_remote))

    assert len(enriched) == 1
    result = enriched[0]
    assert result.admissible == "stale-judge-result"
    assert result.judge_verdict is None


def test_missing_source_document_still_admissible_for_agreement(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    # Strip the sourceDocument line while keeping everything else intact.
    text = review_file.read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("sourceDocument:"))
    review_file.write_text(text, encoding="utf-8")

    project_id = derive_project_id(str(repo_with_remote))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(repo_with_remote))
    sample = make_sample_verdict(
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(update={"result_ref": result_ref, "project_id": project_id})

    enriched = enrich_samples([sample], str(repo_with_remote))

    assert len(enriched) == 1
    result = enriched[0]
    assert result.admissible == "admissible"
    assert result.source_document is None
    assert result.judge_verdict == Verdict.PASS


def test_unversioned_record_flagged(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    project_id = derive_project_id(str(repo_with_remote))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(repo_with_remote))
    sample = make_sample_verdict(
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(
        update={
            "result_ref": result_ref,
            "project_id": project_id,
            "judge_config": JudgeConfigId(
                template_name="judge.slice-vs-arch",
                model="minimax/minimax-m2.7",
                template_content_hash=None,
            ),
        }
    )

    enriched = enrich_samples([sample], str(repo_with_remote))

    assert len(enriched) == 1
    assert enriched[0].unversioned is True
