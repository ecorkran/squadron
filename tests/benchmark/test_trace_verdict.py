"""The pure fairness verdict for one traced test (slice 422 D6, D7)."""

from __future__ import annotations

import pytest

from squadron.benchmark.fairness import AllowedBoundary
from squadron.benchmark.trace_verdict import Crossing, PatchFact, Reference, TraceFacts, judge_trace
from squadron.metrology.benchmark_models import TestRejection

ALLOWED = AllowedBoundary(
    frozenset({("fixpkg.api", "exported_function"), ("fixpkg.cli", "main"), ("fixpkg.api", "Exported")})
)


def facts(
    references: tuple[Reference, ...] = (),
    crossings: tuple[Crossing, ...] = (),
    patches: tuple[PatchFact, ...] = (),
    *,
    has_co_qualname: bool = True,
) -> TraceFacts:
    return TraceFacts(references, crossings, patches, has_co_qualname)


def function_reference(module: str, name: str) -> Reference:
    return Reference("function", module, name)


def test_a_test_touching_only_allowed_symbols_is_fair() -> None:
    verdict = judge_trace(
        facts(
            references=(function_reference("fixpkg.api", "exported_function"),),
            crossings=(Crossing("fixpkg.api", "exported_function", "function"),),
        ),
        ALLOWED,
    )
    assert verdict.rejection is None


def test_a_test_with_no_facts_is_fair() -> None:
    assert judge_trace(facts(), ALLOWED).rejection is None


def test_a_static_reference_not_allowed_names_the_symbol() -> None:
    verdict = judge_trace(
        facts(references=(function_reference("fixpkg.internal", "internal_function"),)), ALLOWED
    )
    assert verdict.rejection is TestRejection.REACHES_PAST_BOUNDARY
    assert verdict.detail == "fixpkg.internal.internal_function"


def test_a_class_reference_is_checked_like_a_function() -> None:
    reference = Reference("class", "fixpkg.internal", "InternalWidget")
    assert judge_trace(facts(references=(reference,)), ALLOWED).rejection is (
        TestRejection.REACHES_PAST_BOUNDARY
    )
    assert (
        judge_trace(
            facts(references=(Reference("class", "fixpkg.api", "Exported"),)), ALLOWED
        ).rejection
        is None
    )


def test_a_function_crossing_not_allowed_is_past_the_boundary() -> None:
    verdict = judge_trace(
        facts(crossings=(Crossing("fixpkg.internal", "internal_function", "function"),)), ALLOWED
    )
    assert verdict.rejection is TestRejection.REACHES_PAST_BOUNDARY
    assert verdict.detail == "fixpkg.internal.internal_function"


def test_a_constructor_crossing_checks_the_class_not_the_init() -> None:
    internal = Crossing("fixpkg.internal", "InternalWidget.__init__", "constructor")
    verdict = judge_trace(facts(crossings=(internal,)), ALLOWED)
    assert verdict.rejection is TestRejection.REACHES_PAST_BOUNDARY
    assert verdict.detail == "fixpkg.internal.InternalWidget"
    exported = Crossing("fixpkg.api", "Exported.__init__", "constructor")
    assert judge_trace(facts(crossings=(exported,)), ALLOWED).rejection is None


def test_a_method_crossing_is_allowed_even_on_a_class_that_is_not_exported() -> None:
    method = Crossing("fixpkg.internal", "InternalWidget.run", "method")
    assert judge_trace(facts(crossings=(method,)), ALLOWED).rejection is None


def test_a_static_module_reference_is_undecidable() -> None:
    verdict = judge_trace(facts(references=(Reference("module", "fixpkg", ""),)), ALLOWED)
    assert verdict.rejection is TestRejection.BOUNDARY_UNDECIDABLE
    assert "fixpkg" in verdict.detail


def test_an_interpreter_without_co_qualname_is_undecidable() -> None:
    verdict = judge_trace(facts(has_co_qualname=False), ALLOWED)
    assert verdict.rejection is TestRejection.BOUNDARY_UNDECIDABLE
    assert "co_qualname" in verdict.detail


def test_an_unresolved_patch_is_undecidable() -> None:
    patch = PatchFact("mock.patch", "unresolved", "", "pkg.gone.thing")
    verdict = judge_trace(facts(patches=(patch,)), ALLOWED)
    assert verdict.rejection is TestRejection.BOUNDARY_UNDECIDABLE
    assert "pkg.gone.thing" in verdict.detail


@pytest.mark.parametrize("owner_kind", ["project_module", "project_class", "project_instance"])
def test_patching_project_code_is_rejected_naming_the_target(owner_kind: str) -> None:
    patch = PatchFact("mock.patch", owner_kind, "fixpkg.mod", "fixpkg.mod.run")
    verdict = judge_trace(facts(patches=(patch,)), ALLOWED)
    assert verdict.rejection is TestRejection.PATCHES_PROJECT_CODE
    assert verdict.detail == "fixpkg.mod.run"


def test_patching_something_foreign_is_allowed() -> None:
    patch = PatchFact("mock.patch", "foreign", "subprocess", "subprocess.run")
    assert judge_trace(facts(patches=(patch,)), ALLOWED).rejection is None


def test_environment_isolation_patch_is_not_patching_project_code() -> None:
    patch = PatchFact(
        "monkeypatch.setattr", "project_module", "squadron.cli.app", "squadron.cli.app._load_env_file"
    )
    assert judge_trace(facts(patches=(patch,)), ALLOWED).rejection is None


def test_environment_isolation_exemption_does_not_hide_another_project_patch() -> None:
    isolation = PatchFact(
        "monkeypatch.setattr", "project_module", "squadron.cli.app", "squadron.cli.app._load_env_file"
    )
    other = PatchFact("mock.patch", "project_module", "squadron.cli.app", "squadron.cli.app.run")
    verdict = judge_trace(facts(patches=(isolation, other)), ALLOWED)
    assert verdict.rejection is TestRejection.PATCHES_PROJECT_CODE
    assert verdict.detail == "squadron.cli.app.run"


def test_precedence_patching_then_past_boundary_then_undecidable() -> None:
    patch = PatchFact("mock.patch", "project_module", "fixpkg.mod", "fixpkg.mod.run")
    past = function_reference("fixpkg.internal", "internal_function")
    module = Reference("module", "fixpkg", "")
    everything = judge_trace(
        facts(references=(past, module), patches=(patch,), has_co_qualname=False), ALLOWED
    )
    assert everything.rejection is TestRejection.PATCHES_PROJECT_CODE
    no_patch = judge_trace(facts(references=(past, module), has_co_qualname=False), ALLOWED)
    assert no_patch.rejection is TestRejection.REACHES_PAST_BOUNDARY
    only_undecidable = judge_trace(facts(references=(module,), has_co_qualname=False), ALLOWED)
    assert only_undecidable.rejection is TestRejection.BOUNDARY_UNDECIDABLE


def test_from_plugin_builds_facts_from_a_node_record() -> None:
    record = {
        "references": [["function", "fixpkg.api", "exported_function"]],
        "crossings": [["fixpkg.api", "exported_function", "function"]],
        "patches": [["mock.patch", "foreign", "subprocess", "subprocess.run"]],
    }
    built = TraceFacts.from_plugin(record, has_co_qualname=True)
    assert built.references == (Reference("function", "fixpkg.api", "exported_function"),)
    assert built.crossings == (Crossing("fixpkg.api", "exported_function", "function"),)
    assert built.patches == (PatchFact("mock.patch", "foreign", "subprocess", "subprocess.run"),)
