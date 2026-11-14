"""Benchmark id, config key and replay record ids (slice 424 Task 22)."""

from __future__ import annotations

import inspect
import re

import pytest

from squadron.benchmark.bench_plan import (
    BenchConfig,
    ReplayIdError,
    benchmark_id,
    config_key,
    replay_record_id,
)

OPUS = BenchConfig(alias="opus", model="claude-opus-5-5", profile="sdk", effort_configured="high")
SOL = BenchConfig(alias="sol", model="sol-model", profile="openai-oauth", effort_configured=None)
CASE_ID = "case-0123456789abcdef"


def _id(**changes: object) -> str:
    args: dict[str, object] = {
        "set_name": "fixes",
        "set_version": 1,
        "config_keys": [config_key(OPUS), config_key(SOL)],
        "samples": 3,
    }
    args.update(changes)
    return benchmark_id(**args)  # type: ignore[arg-type]


class TestConfigKey:
    def test_is_canonical_json_of_the_four_fields(self) -> None:
        assert config_key(OPUS) == (
            '{"alias":"opus","effort_configured":"high","model":"claude-opus-5-5","profile":"sdk"}'
        )

    def test_none_fields_are_kept_distinct_from_values(self) -> None:
        assert config_key(SOL) != config_key(
            SOL.__class__(**{**SOL.__dict__, "effort_configured": "low"})
        )
        assert '"effort_configured":null' in config_key(SOL)


class TestBenchmarkId:
    def test_has_prefix_and_sixteen_hex_digits(self) -> None:
        assert re.fullmatch(r"bench-[0-9a-f]{16}", _id())

    def test_stable_across_calls_and_config_order(self) -> None:
        reversed_keys = [config_key(SOL), config_key(OPUS)]
        assert _id() == _id() == _id(config_keys=reversed_keys)

    @pytest.mark.parametrize(
        "changes",
        [
            {"samples": 4},
            {"set_version": 2},
            {"set_name": "other"},
            {"config_keys": [config_key(OPUS)]},
            {
                "config_keys": [
                    config_key(OPUS),
                    config_key(BenchConfig("sol2", "sol-model", "openai-oauth", None)),
                ]
            },
            {
                "config_keys": [
                    config_key(OPUS),
                    config_key(BenchConfig("sol", "sol-model", "openai-oauth", "low")),
                ]
            },
            {
                "config_keys": [
                    config_key(OPUS),
                    config_key(BenchConfig("sol", "sol-model", "sdk", None)),
                ]
            },
        ],
        ids=["samples", "set-version", "set-name", "fewer-configs", "alias", "effort", "profile"],
    )
    def test_each_identity_input_changes_the_id(self, changes: dict[str, object]) -> None:
        assert _id(**changes) != _id()

    def test_no_cap_can_enter_the_identity(self) -> None:
        names = inspect.signature(benchmark_id).parameters
        assert not [name for name in names if "cap" in name or "cost" in name]


class TestReplayRecordId:
    def test_segments_have_the_exact_lengths(self) -> None:
        record_id = replay_record_id(_id(), CASE_ID, config_key(OPUS), 0)
        assert re.fullmatch(r"implreplay-[0-9a-f]{12}-[0-9a-f]{12}-[0-9a-f]{8}-s0", record_id)

    def test_segments_come_from_the_benchmark_and_case_ids(self) -> None:
        benchmark = _id()
        record_id = replay_record_id(benchmark, CASE_ID, config_key(OPUS), 2)
        assert record_id.startswith(f"implreplay-{benchmark[6:18]}-{CASE_ID[5:17]}-")
        assert record_id.endswith("-s2")

    def test_two_samples_differ_only_in_the_suffix(self) -> None:
        first = replay_record_id(_id(), CASE_ID, config_key(OPUS), 0)
        second = replay_record_id(_id(), CASE_ID, config_key(OPUS), 1)
        assert first != second
        assert first.rsplit("-s", 1)[0] == second.rsplit("-s", 1)[0]

    def test_different_configs_differ_in_the_config_segment(self) -> None:
        opus = replay_record_id(_id(), CASE_ID, config_key(OPUS), 0)
        sol = replay_record_id(_id(), CASE_ID, config_key(SOL), 0)
        assert opus.split("-")[3] != sol.split("-")[3]

    def test_stable_across_calls(self) -> None:
        args = (_id(), CASE_ID, config_key(OPUS), 0)
        assert replay_record_id(*args) == replay_record_id(*args)

    @pytest.mark.parametrize("case_id", ["case-0123456789a", "case-", "", "0123456789abcdef0123"])
    def test_short_or_unprefixed_case_id_raises_a_clear_error(self, case_id: str) -> None:
        with pytest.raises(ReplayIdError, match="case id"):
            replay_record_id(_id(), case_id, config_key(OPUS), 0)

    def test_short_benchmark_id_raises_a_clear_error(self) -> None:
        with pytest.raises(ReplayIdError, match="benchmark id"):
            replay_record_id("bench-0123", CASE_ID, config_key(OPUS), 0)
