"""Per-invocation spend tally and cost-cap config (slice 947 D3-D6)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.config.keys import COST_CAP_KEY
from squadron.config.manager import set_config
from squadron.pipeline.run_spend import RunSpend, read_cost_cap
from tests.pipeline.conftest import usage_dict

_MOD = "squadron.pipeline.run_spend"


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
        spend = RunSpend(None)
        spend.add(usage_dict(0.25), step_name="a")
        spend.add(usage_dict(1.5), step_name="b")

        assert spend.known_usd == pytest.approx(1.75)

    def test_none_usage_adds_nothing(self) -> None:
        spend = RunSpend(None)
        spend.add(None, step_name="a")

        assert spend.known_usd == 0.0

    def test_unknown_cost_adds_nothing_and_warns_once_per_alias(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        spend = RunSpend(None)
        with caplog.at_level(logging.WARNING, logger=_MOD):
            spend.add(usage_dict(None, alias="sol"), step_name="one")
            spend.add(usage_dict(None, alias="sol"), step_name="two")
            spend.add(usage_dict(None, alias="luna"), step_name="three")

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert spend.known_usd == 0.0
        assert len(warnings) == 2
        assert "step one (alias sol) reported no cost" in warnings[0]
        assert "step three (alias luna)" in warnings[1]

    @pytest.mark.parametrize("raw", ["not a mapping", {"tokens": "x"}])
    def test_malformed_record_logs_error_and_leaves_total_unchanged(
        self, caplog: pytest.LogCaptureFixture, raw: object
    ) -> None:
        spend = RunSpend(None)
        spend.add(usage_dict(2.0), step_name="good")

        with caplog.at_level(logging.ERROR, logger=_MOD):
            spend.add(raw, step_name="bad")

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1 and "bad" in errors[0].getMessage()
        assert spend.known_usd == 2.0


class TestCapError:
    def test_uncapped_never_errors(self) -> None:
        spend = RunSpend(None)
        spend.add(usage_dict(1000.0), step_name="a")

        assert spend.cap_error() is None

    def test_at_the_cap_is_not_over_it(self) -> None:
        spend = RunSpend(1.0)
        spend.add(usage_dict(1.0), step_name="a")

        assert spend.cap_error() is None

    def test_over_the_cap_states_spend_and_cap(self) -> None:
        spend = RunSpend(1.0)
        spend.add(usage_dict(0.6), step_name="a")
        spend.add(usage_dict(0.7), step_name="b")

        assert spend.cap_error() == (
            f"run spent $1.30 this invocation, over {COST_CAP_KEY} $1.00; "
            "raise the cap and resume to continue"
        )
