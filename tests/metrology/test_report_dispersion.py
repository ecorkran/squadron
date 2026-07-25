"""Tests for the dispersion report — artifact-identity keyed (F001 fix)."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

from squadron.metrology.identity import derive_project_id, derive_result_ref
from squadron.metrology.models import JudgeConfigId, SampleVerdict
from squadron.metrology.report import dispersion_report
from squadron.review.models import Verdict

from .conftest import make_judge_result, make_sample_verdict


def _sample_for(
    review_file: Path,
    cwd: Path,
    *,
    human_verdict: Verdict = Verdict.PASS,
    judge_config: JudgeConfigId | None = None,
    sample_id: str = "sample-1",
) -> SampleVerdict:
    project_id = derive_project_id(str(cwd))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(cwd))
    sample = make_sample_verdict(
        sample_id=sample_id,
        project_value=project_id.value,
        human_verdict=human_verdict,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    )
    update: dict[str, object] = {"result_ref": result_ref, "project_id": project_id}
    if judge_config is not None:
        update["judge_config"] = judge_config
    return sample.model_copy(update=update)


def test_cross_config_on_one_artifact_yields_one_dispersion_cell(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    source_document = "project-documents/user/slices/700-slice.shared.md"

    review_a = write_review_file(
        reviews_dir,
        filename="700-review.judge.slice-vs-arch.model-a.md",
        review_type="judge.slice-vs-arch",
        result=make_judge_result(verdict=Verdict.PASS, model="model-a"),
    )
    review_b = write_review_file(
        reviews_dir,
        filename="700-review.judge.slice-vs-arch.model-b.md",
        review_type="judge.slice-vs-arch",
        result=make_judge_result(verdict=Verdict.CONCERNS, model="model-b"),
    )
    # Both reviews grade the same artifact — force the same sourceDocument.
    for review_file in (review_a, review_b):
        text = review_file.read_text(encoding="utf-8")
        text = "\n".join(
            (f"sourceDocument: {source_document}" if line.startswith("sourceDocument:") else line)
            for line in text.splitlines()
        )
        review_file.write_text(text, encoding="utf-8")

    samples = [
        _sample_for(
            review_a,
            repo_with_remote,
            judge_config=JudgeConfigId(template_name="judge.slice-vs-arch", model="model-a"),
            sample_id="sample-a",
        ),
        _sample_for(
            review_b,
            repo_with_remote,
            judge_config=JudgeConfigId(template_name="judge.slice-vs-arch", model="model-b"),
            sample_id="sample-b",
        ),
    ]

    report = dispersion_report(samples, str(repo_with_remote))

    assert len(report.cells) == 1
    cell = report.cells[0]
    assert cell.n == 2
    assert cell.disagreement_rate == 1.0
    assert {jc.model for jc in cell.judge_configs} == {"model-a", "model-b"}


def test_result_ref_identity_is_not_the_key_f001_regression(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    """The two review files must have different result_refs (different
    content, different content_hash) yet still land in one dispersion cell —
    proving the group key is artifact identity, not result_ref."""
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    source_document = "project-documents/user/slices/701-slice.shared.md"

    review_a = write_review_file(
        reviews_dir,
        filename="701-review.judge.slice-vs-arch.model-a.md",
        review_type="judge.slice-vs-arch",
        result=make_judge_result(verdict=Verdict.PASS, model="model-a", score=90.0),
    )
    review_b = write_review_file(
        reviews_dir,
        filename="701-review.judge.slice-vs-arch.model-b.md",
        review_type="judge.slice-vs-arch",
        result=make_judge_result(verdict=Verdict.PASS, model="model-b", score=55.0),
    )
    for review_file in (review_a, review_b):
        text = review_file.read_text(encoding="utf-8")
        text = "\n".join(
            (f"sourceDocument: {source_document}" if line.startswith("sourceDocument:") else line)
            for line in text.splitlines()
        )
        review_file.write_text(text, encoding="utf-8")

    project_id = derive_project_id(str(repo_with_remote))
    ref_a = derive_result_ref(review_a, project_id, cwd=str(repo_with_remote))
    ref_b = derive_result_ref(review_b, project_id, cwd=str(repo_with_remote))
    assert ref_a.content_hash != ref_b.content_hash
    assert ref_a.relative_review_path != ref_b.relative_review_path

    samples = [
        _sample_for(
            review_a,
            repo_with_remote,
            judge_config=JudgeConfigId(template_name="judge.slice-vs-arch", model="model-a"),
            sample_id="sample-a",
        ),
        _sample_for(
            review_b,
            repo_with_remote,
            judge_config=JudgeConfigId(template_name="judge.slice-vs-arch", model="model-b"),
            sample_id="sample-b",
        ),
    ]

    report = dispersion_report(samples, str(repo_with_remote))

    assert len(report.cells) == 1


def test_single_config_artifact_produces_no_dispersion_cell(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    sample = _sample_for(review_file, repo_with_remote)

    report = dispersion_report([sample], str(repo_with_remote))

    assert report.cells == []


def test_missing_source_document_excluded_from_dispersion_but_counted(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
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

    report = dispersion_report([sample], str(repo_with_remote))

    assert report.cells == []


def test_empty_store_yields_empty_report_honestly(repo_with_remote: Path) -> None:
    report = dispersion_report([], str(repo_with_remote))

    assert report.cells == []
    assert report.excluded.total_excluded == 0


def test_no_multi_config_artifact_yields_empty_report(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_a = write_review_file(
        reviews_dir, filename="702-review.a.md", review_type="judge.slice-vs-arch"
    )
    review_b = write_review_file(
        reviews_dir, filename="703-review.b.md", review_type="judge.slice-vs-arch"
    )
    # Distinct sourceDocuments (default fixture value) — no shared artifact.
    samples = [
        _sample_for(review_a, repo_with_remote, sample_id="sample-a"),
        _sample_for(review_b, repo_with_remote, sample_id="sample-b"),
    ]

    report = dispersion_report(samples, str(repo_with_remote))

    assert report.cells == []


def test_no_fan_out_import() -> None:
    """321 must not introduce a 180 fan_out dependency to support the
    dormant same-config dispersion path."""
    report_source = Path("src/squadron/metrology/report.py").read_text(encoding="utf-8")
    tree = ast.parse(report_source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert not any("fan_out" in module for module in imported_modules)
