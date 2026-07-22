"""Tests for the blind capture core (T10/T11).

The blindness assertion is load-bearing: it checks the payload *object* has no
judge score/verdict/findings field, not a substring scan (the ground-truth
artifact may legitimately contain those words in prose).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from squadron.metrology.capture import (
    CapturePayload,
    build_capture_payload,
    record_sample,
    resolve_target,
    reveal,
)
from squadron.metrology.errors import MetrologyTargetError
from squadron.metrology.store import MetrologyStore
from squadron.review.models import Verdict
from tests.metrology.conftest import CaptureProject


class TestBlindness:
    def test_payload_excludes_judge_output(self, capture_project: CaptureProject) -> None:
        payload = build_capture_payload(capture_project.review_file, cwd=str(capture_project.root))
        # Structural: the payload dataclass exposes only artifact + ground
        # truth. There is no field that could carry judge output.
        field_names = {f.name for f in dataclasses.fields(CapturePayload)}
        assert field_names == {"review_file", "artifact_path", "ground_truth_text"}
        assert payload.artifact_path is not None
        assert payload.ground_truth_text is not None
        assert "Ground truth body." in payload.ground_truth_text
        # The judge's actual score value (98.0) must not appear in the payload.
        assert "98.0" not in (payload.ground_truth_text or "")


class TestTargetResolution:
    def test_path_resolves(self, capture_project: CaptureProject) -> None:
        resolved = resolve_target(str(capture_project.review_file), None, str(capture_project.root))
        assert resolved == capture_project.review_file

    def test_index_and_type_resolves(self, capture_project: CaptureProject) -> None:
        resolved = resolve_target(
            str(capture_project.review_index),
            capture_project.review_type,
            str(capture_project.root),
        )
        assert resolved == capture_project.review_file

    def test_zero_match_raises(self, capture_project: CaptureProject) -> None:
        with pytest.raises(MetrologyTargetError):
            resolve_target("999", "slice", str(capture_project.root))

    def test_ambiguous_index_lists_candidates(self, capture_project: CaptureProject) -> None:
        # Add a second review type for the same index → bare index is ambiguous.
        reviews_dir = capture_project.review_file.parent
        (reviews_dir / "500-review.code.example.md").write_text(
            "---\nreviewType: code\naiModel: m\nscore: 1.0\n---\n", encoding="utf-8"
        )
        with pytest.raises(MetrologyTargetError) as exc:
            resolve_target("500", None, str(capture_project.root))
        message = str(exc.value)
        assert "code" in message and "judge.slice-vs-arch" in message


class TestRecordSample:
    def test_writes_blind_record_joinable_by_result_ref(
        self, capture_project: CaptureProject, tmp_path: Path
    ) -> None:
        store = MetrologyStore(store_dir=tmp_path / "store")
        payload = build_capture_payload(capture_project.review_file, cwd=str(capture_project.root))
        outcome = record_sample(
            payload,
            Verdict.CONCERNS,
            "looks off",
            store=store,
            cwd=str(capture_project.root),
            sample_budget=10,
        )
        assert outcome.sample_id is not None
        assert outcome.budget_reached is False

        stored = store.list_samples()
        assert len(stored) == 1
        sample = stored[0]
        assert sample.blind is True
        assert sample.human_verdict == Verdict.CONCERNS
        # Joins back to the target: result_ref path names the graded review.
        assert sample.result_ref.relative_review_path.endswith(
            "500-review.judge.slice-vs-arch.example.md"
        )
        assert sample.project_id.value == "github.com/manta/capture-repo"


class TestBudgetEnforcement:
    def test_ceiling_refuses_write_and_records_nothing(
        self, capture_project: CaptureProject, tmp_path: Path
    ) -> None:
        store = MetrologyStore(store_dir=tmp_path / "store")
        payload = build_capture_payload(capture_project.review_file, cwd=str(capture_project.root))
        budget = 2
        # Fill to the ceiling.
        for _ in range(budget):
            out = record_sample(
                payload,
                Verdict.PASS,
                None,
                store=store,
                cwd=str(capture_project.root),
                sample_budget=budget,
            )
            assert out.sample_id is not None
        assert store.count_samples("github.com/manta/capture-repo") == budget

        # The (N+1)th is refused, writes nothing, and is not an error.
        refused = record_sample(
            payload,
            Verdict.PASS,
            None,
            store=store,
            cwd=str(capture_project.root),
            sample_budget=budget,
        )
        assert refused.sample_id is None
        assert refused.budget_reached is True
        assert refused.budget_limit == budget
        assert store.count_samples("github.com/manta/capture-repo") == budget

    def test_ceiling_is_per_project(
        self,
        capture_project: CaptureProject,
        tmp_path: Path,
        make_second_project: CaptureProject,
    ) -> None:
        store = MetrologyStore(store_dir=tmp_path / "store")
        payload_a = build_capture_payload(capture_project.review_file, cwd=str(capture_project.root))
        # Project A is at its ceiling of 1.
        record_sample(
            payload_a,
            Verdict.PASS,
            None,
            store=store,
            cwd=str(capture_project.root),
            sample_budget=1,
        )
        refused = record_sample(
            payload_a,
            Verdict.PASS,
            None,
            store=store,
            cwd=str(capture_project.root),
            sample_budget=1,
        )
        assert refused.budget_reached is True

        # Project B under its own budget still succeeds.
        project_b = make_second_project
        payload_b = build_capture_payload(project_b.review_file, cwd=str(project_b.root))
        out_b = record_sample(
            payload_b,
            Verdict.PASS,
            None,
            store=store,
            cwd=str(project_b.root),
            sample_budget=1,
        )
        assert out_b.sample_id is not None
        assert out_b.budget_reached is False


class TestReveal:
    def test_reveal_returns_judge_output(self, capture_project: CaptureProject) -> None:
        revealed = reveal(capture_project.review_file)
        # Post-commit reveal exposes the judge fields the blind payload withheld.
        assert revealed["score"] == 98.0
        assert revealed["verdict"] == "PASS"
        assert set(revealed.keys()) == {"verdict", "score", "criteria", "findings"}
