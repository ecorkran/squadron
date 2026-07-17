---
docType: review
layer: project
reviewType: code
slice: gate-composition
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/304-slice.gate-composition.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260717
dateUpdated: 20260717
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Gate step validates and forwards `policy` but GateAction ignores it"
    location: src/squadron/pipeline/steps/gate.py:55-60
  - id: F002
    severity: concern
    category: project-conventions
    summary: "gate test file far exceeds project source-file line guideline"
    location: tests/pipeline/test_gate.py
  - id: F003
    severity: pass
    category: error-handling
    summary: "Fail-closed verdict ranking with observable missing/None legs"
    location: src/squadron/pipeline/actions/gate.py:19-54
  - id: F004
    severity: pass
    category: design
    summary: "Additive step_outputs surface preserves prior semantics"
    location: src/squadron/pipeline/executor.py:712-900
  - id: F005
    severity: pass
    category: validation
    summary: "Load-time cross-step reference validation"
    location: src/squadron/pipeline/loader.py:213-308
  - id: F006
    severity: note
    category: documentation
    summary: "GateAction success semantics for non-pass verdicts are undocumented"
    location: src/squadron/pipeline/actions/gate.py:112
---

# Review: code — slice 304

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] Gate step validates and forwards `policy` but GateAction ignores it

GateStepType.validate() accepts a `policy` field, validates it against `_VALID_POLICIES`, and expand() forwards it in the gate action params. However, `GateAction.execute()` never reads `context.params["policy"]`; the reduction is hardcoded to `most-severe` in `reduce_verdicts`. This creates unused config surface and an inconsistency between step validation and action behavior. Either make GateAction dispatch on `policy`, or remove/ignore `policy` in GateStepType until a second policy is implemented.

### [CONCERN] gate test file far exceeds project source-file line guideline

tests/pipeline/test_gate.py is ~720 lines, well over the project guideline of ~300 lines per source file. The file mixes action unit tests, executor integration tests, step-type tests, loader validation tests, and design-boundary documentation. Splitting it into focused files (e.g., test_gate_action.py, test_gate_step.py, test_gate_loader.py, test_gate_executor.py) would improve maintainability and align with the convention.

### [PASS] Fail-closed verdict ranking with observable missing/None legs

The `_Severity` enum ranks `UNKNOWN` above `FAIL/CONCERNS/PASS`, `_normalize()` maps `None` to `UNKNOWN`, and `GateAction.execute()` logs `WARNING` when a referenced step is missing or a result has no verdict. This satisfies fail-closed and failure-mode observability requirements. The pure `reduce_verdicts()` function is thoroughly tested with a 4x4 cross-product and None-normalization cases.

### [PASS] Additive step_outputs surface preserves prior semantics

`step_outputs` is accumulated alongside `prior_outputs` and passed into `ActionContext` without mutating the existing checkpoint/read path. Tests explicitly confirm the lossy `prior_outputs` collision behavior (`review-0` overwriting) is unchanged while step-name-keyed results become available for gate composition.

### [PASS] Load-time cross-step reference validation

`_validate_gate_references()` fails fast when a gate names a nonexistent or later step, while skipping `{param}` placeholders. This correctly separates own-config validation (step type) from cross-step validation (loader), matching the project's fail-fast preference.

### [NOTE] GateAction success semantics for non-pass verdicts are undocumented

`GateAction.execute()` always sets `result.success = True`, regardless of whether the reduced verdict is `PASS`, `CONCERNS`, `FAIL`, or `UNKNOWN`. Tests assert this for the passing case. Confirm that `success` indicates action execution health rather than verdict outcome, and add a comment or test for non-pass cases to prevent future confusion.
