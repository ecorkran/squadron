"""Per-invocation spend tally and cost-cap config (slice 947 D3-D6)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.config.keys import COST_CAP_KEY
from squadron.config.manager import set_config
from squadron.core.usage import TokenUsage, UsageRecord
from squadron.pipeline.run_spend import RunSpend, read_cost_cap

_MOD = "squadron.pipeline.run_spend"


def _usage(cost_usd: float | None, alias: str | None = "opus") -> dict[str, object]:
    record = UsageRecord(
        model=None,
        alias=alias,
        profile=None,
        effort=None,
        turns=1,
        duration_seconds=1.0,
        usage=TokenUsage(),
        cost_usd=cost_usd,
        cost_basis=None,
    )
    return record.to_dict()


class TestReadCostCap:
    def test_unset_means_no_cap(self, patch_config_paths: dict[str, Path], tmp_path: Path) -> None:
        assert read_cost_cap(str(tmp_path)) is None

    def test_set_through_config_command_path_reads_back_as_float(
        self, patch_config_paths: dict[str, Path], tmp_path: Path
    ) -> None:
        set_config(COST_CAP_KEY, "12.5", project=True, cwd=str(tmp_path))

        cap = read_cost_cap(str(tmp_path))

        assert cap == 12.5
        assert isinstance(cap, float)

    def test_whole_number_cap_is_a_float(
        self, patch_config_paths: dict[str, Path], tmp_path: Path
    ) -> None:
        set_config(COST_CAP_KEY, "20", project=True, cwd=str(tmp_path))

        assert read_cost_cap(str(tmp_path)) == 20.0

    @pytest.mark.parametrize("raw", ["0", "-1", "-0.5", "inf", "nan"])
    def test_non_positive_or_non_finite_cap_raises_naming_the_key(
        self, patch_config_paths: dict[str, Path], tmp_path: Path, raw: str
    ) -> None:
        set_config(COST_CAP_KEY, raw, project=True, cwd=str(tmp_path))

        with pytest.raises(ValueError, match=COST_CAP_KEY):
            read_cost_cap(str(tmp_path))

    def test_non_numeric_config_value_raises_naming_the_key(
        self, patch_config_paths: dict[str, Path], tmp_path: Path
    ) -> None:
        patch_config_paths["project"].write_text(f'"{COST_CAP_KEY}" = "lots"\n')

        with pytest.raises(ValueError, match=COST_CAP_KEY):
            read_cost_cap(str(tmp_path))

    def test_non_numeric_value_is_rejected_by_the_config_command(
        self, patch_config_paths: dict[str, Path], tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError):
            set_config(COST_CAP_KEY, "lots", project=True, cwd=str(tmp_path))


class TestRunSpend:
    def test_sums_known_costs(self) -> None:
        spend = RunSpend()
        spend.add(_usage(0.25), step_name="a")
        spend.add(_usage(1.5), step_name="b")

        assert spend.known_usd == pytest.approx(1.75)

    def test_none_usage_adds_nothing(self) -> None:
        spend = RunSpend()
        spend.add(None, step_name="a")

        assert spend.known_usd == 0.0

    def test_unknown_cost_adds_nothing_and_warns_once_per_alias(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        spend = RunSpend()
        with caplog.at_level(logging.WARNING, logger=_MOD):
            spend.add(_usage(None, alias="sol"), step_name="one")
            spend.add(_usage(None, alias="sol"), step_name="two")
            spend.add(_usage(None, alias="luna"), step_name="three")

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert spend.known_usd == 0.0
        assert len(warnings) == 2
        assert "step one (alias sol) reported no cost" in warnings[0]
        assert "step three (alias luna)" in warnings[1]

    @pytest.mark.parametrize("raw", ["not a mapping", {"tokens": "x"}])
    def test_malformed_record_logs_error_and_leaves_total_unchanged(
        self, caplog: pytest.LogCaptureFixture, raw: object
    ) -> None:
        spend = RunSpend()
        spend.add(_usage(2.0), step_name="good")

        with caplog.at_level(logging.ERROR, logger=_MOD):
            spend.add(raw, step_name="bad")

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1 and "bad" in errors[0].getMessage()
        assert spend.known_usd == 2.0
