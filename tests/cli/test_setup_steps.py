"""Tests for setup_steps.py — StepKind, SetupStep, _classify, build_steps."""

from __future__ import annotations

import pytest

from squadron.cli.commands.doctor_checks import (
    SECTION_CONFIG,
    SECTION_INSTALL,
    SECTION_INTEGRATIONS,
    SECTION_PROVIDERS,
    CheckResult,
    CheckStatus,
)
from squadron.cli.commands.setup_steps import (
    SetupStep,
    StepKind,
    _classify,  # pyright: ignore[reportPrivateUsage]
    build_steps,
)

# ---------------------------------------------------------------------------
# T3 — StepKind and SetupStep basics
# ---------------------------------------------------------------------------


def test_stepkind_string_equality() -> None:
    assert StepKind.INSTALL == "install"
    assert StepKind.ALREADY_DONE == "already-done"
    assert StepKind.CONFIGURE == "configure"
    assert StepKind.OPTIONAL == "optional"


def test_setupstep_is_hashable() -> None:
    step = SetupStep(title="t", kind=StepKind.INSTALL, section="s", detail="d")
    assert hash(step) is not None
    # Can be stored in a set (requires hashability)
    assert step in {step}


def test_setupstep_optional_defaults() -> None:
    step = SetupStep(title="t", kind=StepKind.CONFIGURE, section="s", detail="d")
    assert step.command is None
    assert step.explanation is None
    assert step.docs_anchor is None
    assert step.recheck is None
    assert step.check_name == ""


# ---------------------------------------------------------------------------
# T6 — _classify parametrized
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, section, expected_kind",
    [
        # OK always → ALREADY_DONE
        (CheckStatus.OK, SECTION_INSTALL, StepKind.ALREADY_DONE),
        (CheckStatus.OK, SECTION_CONFIG, StepKind.ALREADY_DONE),
        # WARN always → OPTIONAL
        (CheckStatus.WARN, SECTION_INSTALL, StepKind.OPTIONAL),
        (CheckStatus.WARN, SECTION_PROVIDERS, StepKind.OPTIONAL),
        # MISSING + Install/Integrations → INSTALL
        (CheckStatus.MISSING, SECTION_INSTALL, StepKind.INSTALL),
        (CheckStatus.MISSING, SECTION_INTEGRATIONS, StepKind.INSTALL),
        # MISSING + Providers/Config → CONFIGURE
        (CheckStatus.MISSING, SECTION_PROVIDERS, StepKind.CONFIGURE),
        (CheckStatus.MISSING, SECTION_CONFIG, StepKind.CONFIGURE),
    ],
)
def test_classify(status: CheckStatus, section: str, expected_kind: StepKind) -> None:
    result = CheckResult(name="x", status=status, detail="d", section=section)
    assert _classify(result) == expected_kind


# ---------------------------------------------------------------------------
# T10 — build_steps happy paths
# ---------------------------------------------------------------------------


def _make_result(
    name: str,
    status: CheckStatus,
    section: str,
    fix_hint: str | None = None,
    required: bool = True,
) -> CheckResult:
    return CheckResult(
        name=name,
        status=status,
        detail=f"detail for {name}",
        fix_hint=fix_hint,
        section=section,
        required=required,
    )


def test_build_steps_all_ok() -> None:
    results = [
        _make_result("squadron", CheckStatus.OK, SECTION_INSTALL),
        _make_result("context-forge", CheckStatus.OK, SECTION_INTEGRATIONS),
        _make_result("providers.toml", CheckStatus.OK, SECTION_CONFIG),
    ]
    steps = build_steps(results)
    assert all(s.kind == StepKind.ALREADY_DONE for s in steps)
    assert len(steps) == 3


def test_build_steps_missing_install() -> None:
    result = _make_result(
        "context-forge", CheckStatus.MISSING, SECTION_INTEGRATIONS, fix_hint="npm i -g cf"
    )
    steps = build_steps([result])
    assert len(steps) == 1
    assert steps[0].kind == StepKind.INSTALL
    assert steps[0].command == "npm i -g cf"


def test_build_steps_missing_configure() -> None:
    result = _make_result("providers.toml", CheckStatus.MISSING, SECTION_CONFIG, fix_hint="fix it")
    steps = build_steps([result])
    assert len(steps) == 1
    assert steps[0].kind == StepKind.CONFIGURE


def test_build_steps_warn() -> None:
    result = _make_result("project .env", CheckStatus.WARN, SECTION_CONFIG)
    steps = build_steps([result])
    assert len(steps) == 1
    assert steps[0].kind == StepKind.OPTIONAL


# ---------------------------------------------------------------------------
# T11 — build_steps --profile filter
# ---------------------------------------------------------------------------


def _provider_results(profile_names: list[str]) -> list[CheckResult]:
    """Synthetic Providers-section results for testing."""
    rows: list[CheckResult] = [
        CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail="no credential",
            fix_hint=f"set {name.upper()}_API_KEY",
            section=SECTION_PROVIDERS,
            required=False,
        )
        for name in profile_names
    ]
    # Aggregate row
    rows.append(
        CheckResult(
            name="at least one provider OK",
            status=CheckStatus.MISSING,
            detail="none authenticated",
            fix_hint="configure a profile",
            section=SECTION_PROVIDERS,
            required=True,
        )
    )
    return rows


def test_build_steps_profile_filter_keeps_matching_row_and_aggregate() -> None:
    results = _provider_results(["openai", "openrouter", "gemini"])
    steps = build_steps(results, profile="openai")
    provider_steps = [s for s in steps if s.section == SECTION_PROVIDERS]
    names = {s.check_name for s in provider_steps}
    assert names == {"openai", "at least one provider OK"}


def test_build_steps_unknown_profile_raises() -> None:
    results = _provider_results(["openai"])
    with pytest.raises(ValueError, match="nonexistent"):
        build_steps(results, profile="nonexistent")


# ---------------------------------------------------------------------------
# T12 — recheck attachment and degradation
# ---------------------------------------------------------------------------


def test_build_steps_known_check_has_recheck() -> None:
    result = _make_result("context-forge", CheckStatus.WARN, SECTION_INTEGRATIONS)
    steps = build_steps([result])
    assert steps[0].recheck is not None
    # Calling it should return a CheckResult (real check against current env)
    outcome = steps[0].recheck()
    assert isinstance(outcome, CheckResult)


def test_build_steps_unknown_check_recheck_is_none() -> None:
    result = _make_result("future-unknown-check", CheckStatus.WARN, SECTION_INTEGRATIONS)
    steps = build_steps([result])
    assert steps[0].recheck is None


def test_build_steps_provider_profile_has_synthesised_recheck() -> None:
    # A Providers-section row that is NOT in _RECHECK_MAP should get a synthesised lambda.
    result = CheckResult(
        name="openai",
        status=CheckStatus.WARN,
        detail="no credential",
        section=SECTION_PROVIDERS,
        required=False,
    )
    steps = build_steps([result])
    assert steps[0].recheck is not None
    outcome = steps[0].recheck()
    assert isinstance(outcome, CheckResult)
