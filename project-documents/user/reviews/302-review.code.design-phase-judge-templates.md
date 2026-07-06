---
docType: review
layer: project
reviewType: code
slice: design-phase-judge-templates
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/302-slice.design-phase-judge-templates.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260705
dateUpdated: 20260705
findings:
  - id: F001
    severity: concern
    category: test-correctness
    summary: "Test may pass for the wrong reason — doesn't exercise the code path it claims to test"
    location: tests/pipeline/actions/test_review_action.py:660
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Missing unit test for _arch_file source returning None on empty arch_file"
    location: tests/review/test_template_inputs.py
  - id: F003
    severity: note
    category: code-duplication
    summary: "DRY violation across judge template test classes"
    location: tests/review/test_templates.py:373
  - id: F004
    severity: note
    category: magic-values
    summary: "Hardcoded threshold values in tests without single-source reference"
    location: tests/review/test_templates.py:396
---

# Review: code — slice 302

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] Test may pass for the wrong reason — doesn't exercise the code path it claims to test

The test `test_template_inputs_resolution_failure_yields_unknown` claims to verify that an empty `arch_file` causes `against` to be unresolved for `judge.slice-vs-arch`. However, the context is constructed with `template="judge.test"`, which has no entry in `TEMPLATE_INPUTS`. If the code resolves inputs by looking up the template name in the `TEMPLATE_INPUTS` registry, then no inputs are populated regardless of `arch_file`'s value — the test passes because "judge.test" isn't registered, not because `arch_file` is empty. This provides false confidence: a future regression in `_arch_file` source resolution would go undetected by this test. The test should either use `"judge.slice-vs-arch"` as the template name (so the TEMPLATE_INPUTS entry exists and the empty `arch_file` is the actual cause), or the test should be restructured to directly exercise `_arch_file`'s behavior with an empty string.

### [CONCERN] Missing unit test for _arch_file source returning None on empty arch_file

There is a test for the symmetric edge case — `test_judge_tasks_vs_slice_no_input_when_task_files_empty` verifies that empty `task_files` causes `_tasks_input` to return None and `input` to be absent from the resolved dict. But there is no corresponding test for `judge.slice-vs-arch` when `arch_file` is empty/falsy. The `_arch_file` source function should be tested to confirm it returns None for an empty `arch_file`, preventing the `against` key from being set. This is exactly the scenario the integration test in `test_review_action.py` attempts (but likely fails) to cover. A direct unit test here would close the gap.

### [NOTE] DRY violation across judge template test classes

`TestJudgeTasksVsSliceTemplate` and `TestJudgeSliceVsArchTemplate` share identical structure: the `_load` fixture, `_get` helper, `test_is_judge`, `test_required_inputs`, and `test_registered_in_list_templates` are all structurally the same — only the template name and expected thresholds differ. This could be refactored using `@pytest.mark.parametrize` over `(template_name, expected_thresholds)` tuples, or a shared base class, reducing ~40 lines of duplication and making it trivial to add a third judge template later.

### [NOTE] Hardcoded threshold values in tests without single-source reference

Threshold values (`pass_floor=78, concerns_floor=55`, `pass_floor=82, concerns_floor=60`) are hardcoded in both the template definitions and the test assertions with no shared constant. Per project conventions: *"Never scatter comparison values across code. If a value is used in conditionals, switch cases, or lookups, define it once."* If these thresholds are business-critical (the cross-template differentiation test at line 449 suggests they are), they should be defined as named constants in one place and referenced by both the template registrations and the tests.
