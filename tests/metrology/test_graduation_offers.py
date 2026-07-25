"""Tests for residual-offer selection (T14/T15)."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.graduation import find_graduation, select_residual_offers, write_graduation
from squadron.metrology.identity import derive_judge_config_id, derive_project_id, derive_result_ref
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import EvidenceSnapshot, GraduatedConfig, SampleVerdict
from squadron.metrology.store import MetrologyStore
from squadron.review.models import Verdict
from squadron.review.templates import ReviewTemplate, clear_registry, register_template

_TEMPLATE_NAME = "judge.slice-vs-arch"


def _register_judge_template(*, system_prompt: str = "You are a judge.") -> None:
    register_template(
        ReviewTemplate(
            name=_TEMPLATE_NAME,
            description="Example",
            system_prompt=system_prompt,
            allowed_tools=[],
            permission_mode="default",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            model="minimax/minimax-m2.7",
            prompt_template="Judge this: {input}",
            judge={"pass_floor": 78, "concerns_floor": 55},
        )
    )


@pytest.fixture(autouse=True)
def _clear_template_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def project_repo(
    repo_no_remote: Path,
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> Path:
    """A repo with a recorded ``metrology.project_id`` so derive_project_id resolves."""
    write_project_config(repo_no_remote, {"metrology.project_id": "acme/widget"})
    return repo_no_remote


def _write_judge_review(write_review_file: Callable[..., Path], reviews_dir: Path, index: int) -> Path:
    return write_review_file(
        reviews_dir,
        filename=f"{index}-review.judge.slice-vs-arch.example.md",
        review_type=_TEMPLATE_NAME,
    )


def _graduation_for(review_file: Path) -> GraduatedConfig:
    judge_config = derive_judge_config_id(review_file)
    return GraduatedConfig(
        judge_config=judge_config,
        artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH,
        evidence=EvidenceSnapshot(n=10, match_rate=0.95, floor_applied=5, below_floor=False),
        graduated_at=datetime(2026, 7, 25, tzinfo=UTC),
    )


def _mark_sampled(store: MetrologyStore, review_file: Path, cwd: str) -> None:
    project_id = derive_project_id(cwd)
    judge_config = derive_judge_config_id(review_file)
    result_ref = derive_result_ref(review_file, project_id, cwd=cwd)
    sample = SampleVerdict(
        sample_id=f"sample-marked-{review_file.stem}",
        project_id=project_id,
        result_ref=result_ref,
        judge_config=judge_config,
        human_verdict=Verdict.PASS,
        captured_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    store.write_sample(sample)


class TestNonEmptyGuarantee:
    def test_unsampled_matching_results_yield_non_empty_offers(
        self, project_repo: Path, write_review_file: Callable[..., Path]
    ) -> None:
        _register_judge_template()
        reviews_dir = project_repo / "project-documents/user/reviews"
        review_a = _write_judge_review(write_review_file, reviews_dir, 500)
        review_b = _write_judge_review(write_review_file, reviews_dir, 501)
        review_c = _write_judge_review(write_review_file, reviews_dir, 502)

        store = MetrologyStore(store_dir=project_repo / "store")
        graduated = _graduation_for(review_a)
        write_graduation(store, graduated)

        offers = select_residual_offers(store, [graduated], rate=1.0, cwd=str(project_repo))
        assert len(offers) == 3
        project_id = derive_project_id(str(project_repo))
        expected_paths = {
            derive_result_ref(f, project_id, cwd=str(project_repo)).relative_review_path
            for f in (review_a, review_b, review_c)
        }
        assert {o.review_path for o in offers} == expected_paths


class TestExhaustedConfig:
    def test_all_sampled_yields_empty_list(
        self, project_repo: Path, write_review_file: Callable[..., Path]
    ) -> None:
        _register_judge_template()
        reviews_dir = project_repo / "project-documents/user/reviews"
        review_a = _write_judge_review(write_review_file, reviews_dir, 500)

        store = MetrologyStore(store_dir=project_repo / "store")
        graduated = _graduation_for(review_a)
        write_graduation(store, graduated)
        _mark_sampled(store, review_a, str(project_repo))

        offers = select_residual_offers(store, [graduated], rate=1.0, cwd=str(project_repo))
        assert offers == []


class TestLapsedGraduation:
    def test_template_edited_post_graduation_yields_zero_offers(
        self, project_repo: Path, write_review_file: Callable[..., Path]
    ) -> None:
        _register_judge_template(system_prompt="Original prompt.")
        reviews_dir = project_repo / "project-documents/user/reviews"
        old_review = _write_judge_review(write_review_file, reviews_dir, 500)
        graduated = _graduation_for(old_review)

        store = MetrologyStore(store_dir=project_repo / "store")
        write_graduation(store, graduated)

        # Edit the template (a real instrument change) and produce a new
        # judge review under the rewritten template.
        clear_registry()
        _register_judge_template(system_prompt="Rewritten prompt.")
        _write_judge_review(write_review_file, reviews_dir, 501)

        offers = select_residual_offers(store, [graduated], rate=1.0, cwd=str(project_repo))
        assert offers == []

    def test_lapsed_is_distinguishable_from_exhausted_via_find_graduation(
        self, project_repo: Path, write_review_file: Callable[..., Path]
    ) -> None:
        # Lapsed: find_graduation against the *new* result's JudgeConfigId
        # finds nothing (different hash). Exhausted: find_graduation would
        # still find the graduation, it just has no unsampled matches.
        _register_judge_template(system_prompt="Original prompt.")
        reviews_dir = project_repo / "project-documents/user/reviews"
        old_review = _write_judge_review(write_review_file, reviews_dir, 500)
        graduated = _graduation_for(old_review)

        store = MetrologyStore(store_dir=project_repo / "store")
        write_graduation(store, graduated)

        clear_registry()
        _register_judge_template(system_prompt="Rewritten prompt.")
        new_review = _write_judge_review(write_review_file, reviews_dir, 501)
        new_judge_config = derive_judge_config_id(new_review)

        found_for_new_config = find_graduation(
            store, new_judge_config, ArtifactLevel.SLICE_DESIGN_VS_ARCH
        )
        assert found_for_new_config is None  # lapsed: no graduation matches the new instrument

        found_for_old_config = find_graduation(
            store, graduated.judge_config, ArtifactLevel.SLICE_DESIGN_VS_ARCH
        )
        assert found_for_old_config is not None  # the old graduation still exists, just stale


class TestPrunedReviewFile:
    def test_deleted_review_file_is_skipped_not_crashed(
        self, project_repo: Path, write_review_file: Callable[..., Path]
    ) -> None:
        _register_judge_template()
        reviews_dir = project_repo / "project-documents/user/reviews"
        review_a = _write_judge_review(write_review_file, reviews_dir, 500)
        review_b = _write_judge_review(write_review_file, reviews_dir, 501)

        store = MetrologyStore(store_dir=project_repo / "store")
        graduated = _graduation_for(review_a)
        write_graduation(store, graduated)

        # Prune review_b's file before discovery runs — a matching judge
        # result whose file has been deleted since graduation.
        review_b.unlink()

        offers = select_residual_offers(store, [graduated], rate=1.0, cwd=str(project_repo))
        assert len(offers) == 1
        project_id = derive_project_id(str(project_repo))
        assert (
            offers[0].review_path
            == derive_result_ref(review_a, project_id, cwd=str(project_repo)).relative_review_path
        )


class TestRateFraction:
    def test_rate_half_over_four_unsampled_selects_two(
        self, project_repo: Path, write_review_file: Callable[..., Path]
    ) -> None:
        _register_judge_template()
        reviews_dir = project_repo / "project-documents/user/reviews"
        reviews = [_write_judge_review(write_review_file, reviews_dir, 500 + i) for i in range(4)]

        store = MetrologyStore(store_dir=project_repo / "store")
        graduated = _graduation_for(reviews[0])
        write_graduation(store, graduated)

        offers = select_residual_offers(store, [graduated], rate=0.5, cwd=str(project_repo))
        assert len(offers) == 2
