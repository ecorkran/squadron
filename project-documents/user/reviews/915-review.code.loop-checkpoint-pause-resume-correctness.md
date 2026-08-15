---
docType: review
layer: project
reviewType: code
slice: loop-checkpoint-pause-resume-correctness
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/915-slice.loop-checkpoint-pause-resume-correctness.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260813
dateUpdated: 20260813
reviewedSha: 367e9f08ccd6ced25586a4aa4ed66ebd94666cdf
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Single source of truth for resume iteration lookup"
    location: "src/squadron/cli/commands/run.py:177-184"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Defensive invalid-input handling for start_from_iteration"
    location: "src/squadron/pipeline/executor.py:1117-1135"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "WARNING at round abandonment closes the silent-failure path for #48"
    location: "src/squadron/pipeline/executor.py:1098-1116"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Predicate symmetry for PAUSED and FAILED"
    location: "src/squadron/pipeline/state.py:46-51"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Comprehensive coverage of both loop shapes and resume entry points"
    location: "tests/pipeline/test_executor_loop_body.py:1095-1759"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Integration test updated to reflect new behavior"
    location: "tests/pipeline/test_cli_integration.py:220-225"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Stepped docstrings with design traceability"
    location: "src/squadron/pipeline/executor.py:530-535,1097-1098,1098-1116,1118-1135,1138-1167"
  - id: F008
    severity: note
    category: naming
    summary: "Three context-specific names for the same concept"
    location: "src/squadron/cli/commands/run.py:183, src/squadron/pipeline/executor.py:506, src/squadron/pipeline/executor.py:1182"
  - id: F009
    severity: note
    category: design
    summary: "Thin wrapper with one-line body"
    location: "src/squadron/cli/commands/run.py:177-184"
  - id: F010
    severity: note
    category: typing
    summary: "`step: Any` in helper signatures"
    location: "src/squadron/pipeline/executor.py:1101,1121,1118"
  - id: F011
    severity: note
    category: coupling
    summary: "`resume_iteration_for` relies on iteration=0 as a sentinel"
    location: "src/squadron/pipeline/state.py:466-475"
---

# Review: code — slice 915

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Single source of truth for resume iteration lookup

The `_resolve_resume_iteration` wrapper consolidates the lookup so neither the `--resume` path nor the implicit paused-run detection carries its own copy. Consistent with the project's DRY guidance and explicitly cited in the docstring.

### [PASS] Defensive invalid-input handling for start_from_iteration

`_resume_start_iteration` clamps to `>= 1` and emits the INFO "re-entering at round" only when `iteration > 1`, so the default case (iteration == 1) stays quiet. `_degenerate_start_iteration_result` fails loudly (FAILED step result + WARNING) instead of silently reporting COMPLETED for zero rounds run — directly addressing the defect class the slice exists to fix.

### [PASS] WARNING at round abandonment closes the silent-failure path for #48

`_warn_loop_abandoned_on_pause` is shared between both loop shapes (`_execute_loop_step`, `_execute_loop_body`) so the operator-visible signal is single-sourced. The message names the pipeline, step, paused round, loop max, and rounds-not-run — actionable for someone reading logs.

### [PASS] Predicate symmetry for PAUSED and FAILED

Adding `ExecutionStatus.FAILED.value` to `_RESUMABLE_STATUSES` matches the design D2 reasoning (the top-level walk appends both via the same unconditional append), and the test `test_failed_step_resume_returns_to_it` locks the behavior in.

### [PASS] Comprehensive coverage of both loop shapes and resume entry points

New tests cover: warning emission on pause for both loop shapes, no warning on convergence, single-step and multi-step body resume at iteration 2, equals-max, above-max degenerate, re-entry INFO, ignored DEBUG for non-loop steps, clamping of 0 to 1, earlier-step skip with iteration set, and two end-to-end walkthrough scenarios (round-1 paused + resumed; round-2-of-3 paused + resumed at round 2). The last is the strongest assertion that the loop counter does not restart.

### [PASS] Integration test updated to reflect new behavior

The expected `len(completed_steps) == 11` (10 distinct steps; paused step recorded twice: once PAUSED, once COMPLETED on resume) is correctly documented inline with the slice reference. This is a fixture-level behavior change, not a bug.

### [PASS] Stepped docstrings with design traceability

Each new helper documents its slice reference (915 Part A/B/C, D2, D3, D4) and the contract (what it returns, when, why). This makes future review and refactoring traceable to the originating design decisions.

### [NOTE] Three context-specific names for the same concept

`from_iteration` (CLI), `start_from_iteration` (executor public kwarg), `start_iteration` (inner loop kwarg). Each is locally correct, but anyone tracing the resume chain has to remember three names map to one concept. Not a defect — flagging only so reviewers know the mapping is intentional.

### [NOTE] Thin wrapper with one-line body

`_resolve_resume_iteration` adds a docstring (with slice context) above a single delegation. Defensible because it enforces single-source between the two CLI entry points and provides a docstring foothold; reasonable critics could inline both call sites with their own slice comment. Leaving as-is matches the project's DRY preference.

### [NOTE] `step: Any` in helper signatures

Helpers `_warn_loop_abandoned_on_pause`, `_resume_start_iteration`, `_degenerate_start_iteration_result` use `step: Any` even though they only touch `step.name` and `step.step_type`. A small `Protocol` (`_Steplike` with those two attributes) would tighten the type and make the contract explicit, but it's not a blocker — these helpers are private and the project uses duck typing elsewhere.

### [NOTE] `resume_iteration_for` relies on iteration=0 as a sentinel

The docstring documents iteration=0 as the "not in a loop" sentinel and the test `test_non_loop_step_with_no_iteration_returns_zero` relies on `_make_step_result` producing a StepResult with iteration=0. This is consistent with the executor's own `_execute_step_once` invariant referenced in the docstring, but if the StepResult default ever changes from 0, the silent-failure path is back. A `if step_state.iteration > 0` guard inside the loop (or modeling `iteration` as `Optional[int]` with explicit None) would make this robust to schema changes — minor robustness suggestion, not a current bug.
