---
docType: review
layer: project
reviewType: code
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260803
dateUpdated: 20260803
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Refactoring extracts a shared review-domain vocabulary with correct dependency direction"
    location: src/squadron/review/addressed/__init__.py:1
  - id: F002
    severity: pass
    category: uncategorized
    summary: "`archive_existing_review` uses a defensive read-write-verify pattern"
    location: src/squadron/review/persistence.py:282
  - id: F003
    severity: pass
    category: uncategorized
    summary: "CLI exit code policy is explicit and tested"
    location: src/squadron/cli/commands/review.py:898
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Metrology exclusion is asserted separately for two distinct globs"
    location: tests/review/test_resolution_artifact.py:175
  - id: F005
    severity: note
    category: testing
    summary: "Test coverage gaps for `sq review resolve` CLI flags"
    location: tests/review/test_cli_review_resolve.py:1
  - id: F006
    severity: note
    category: naming
    summary: "`exceeds_injection_cap` return semantics are non-obvious from the name"
    location: src/squadron/review/resolution_evidence.py:178
  - id: F007
    severity: note
    category: error-handling
    summary: "`_render_findings` does not defensively handle multi-line summary fields"
    location: src/squadron/review/addressed/judge.py:54
  - id: F008
    severity: note
    category: project-conventions
    summary: "`resolution.py` is slightly over the project's ~300-line guideline"
    location: src/squadron/review/resolution.py:1
  - id: F009
    severity: note
    category: error-handling
    summary: "`_save_and_report` introduces a behavior change for archive failures"
    location: src/squadron/cli/commands/review.py:179
  - id: F010
    severity: note
    category: testing
    summary: "`--since` precedence is asserted in unit tests but not at the CLI layer"
    location: tests/review/test_resolution.py:209
---

# Review: code — slice 306

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Refactoring extracts a shared review-domain vocabulary with correct dependency direction

The vocabulary (statuses, settling-screen names, finding records), the judge transport (`judge_residue_core`), the context-free screens (`compute_diff_since`, `screen_byte_identical`, `screen_git_failure`), the parser, and the verification logic now live in `squadron.review.addressed`, free of any pipeline dependency. The pipeline package retains only what is loop-specific: screen 0 (`screen_no_prior_round`), screen 2 (`screen_exact_match`), the gate-evidence artifact, and the policy. The `models.py` annotation-only `TYPE_CHECKING` import for `ActionResult` explicitly preserves the established direction (pipeline consumes review, not vice versa).

### [PASS] `archive_existing_review` uses a defensive read-write-verify pattern

The function reads the original bytes, copies them, and then reads the copy back to verify the byte-for-byte match before allowing the caller to proceed. The verification path is the corruption case the guard exists to catch, and the test `test_unverifiable_copy_aborts_and_leaves_original_intact` covers this with a corrupted read-back that proves the abort happens for verification failure (not just write failure).

### [PASS] CLI exit code policy is explicit and tested

The docstring documents the policy (exit 0 on ADDRESSED, exit 1 on UNADDRESSED/UNKNOWN), and the test `test_unaddressed_exits_one` asserts it as a shell-composable contract: "Nothing changed since the review — a shell can gate on the exit code."

### [PASS] Metrology exclusion is asserted separately for two distinct globs

The test `test_index_scoped_review_discovery_ignores_them` notes that one glob's exclusion does not imply the other's, so neither is inferred from the other — exactly the right level of paranoia for a metrology invariant.

### [NOTE] Test coverage gaps for `sq review resolve` CLI flags

The CLI test covers the happy path, UNADDRESSED, `--no-judge`, ambiguous type, explicit type, and missing review — but not `--since` (overrides stamp), `--model` (alias expansion), `--profile` (profile override), or `--verbose` (table column toggling). These flags have non-trivial behavior, and CLI-level tests would catch regressions where the resolution cascade drifts from the other review commands.

### [NOTE] `exceeds_injection_cap` return semantics are non-obvious from the name

The function name suggests a boolean check (`True`/`False`), but it returns the configured cap value (an `int`) when exceeded and `None` when not. The caller uses the return value to log the cap, so the actual purpose is "check-and-report-the-cap". A name like `get_injection_cap_if_exceeded` or returning a `(bool, int)` tuple would be clearer.

### [NOTE] `_render_findings` does not defensively handle multi-line summary fields

The function joins finding lines with `"\n".join(...)`. If a `FindingRecord.summary` (or any other field) contains a newline — possible via YAML block scalars like `summary: |\n  ...` — the rendered prompt would break the one-finding-per-line format the parser expects. In practice summaries are single-line, so this is an edge case, but the new `records_from_frontmatter` reader does not strip newlines from `summary`, so a hostile or accidental multi-line input reaches the judge prompt unchanged.

### [NOTE] `resolution.py` is slightly over the project's ~300-line guideline

The file is 384 lines and contains the orchestrator role (enum, screen helpers, async leg, dataclasses, resolve_review). Cohesion is reasonable for an orchestrator, and the project's guideline says "where practical", so this is an observation rather than a violation. If the file grows further, splitting `screen_verdict_consistency` and `_with_unsettled_recorded` into a `resolution_screens.py` would be the natural cut.

### [NOTE] `_save_and_report` introduces a behavior change for archive failures

Previously, archive failure in `save_review_result` would propagate as an `OSError` traceback. The new `_save_and_report` wrapper catches the error, prints `[red]Review not saved: ...[/red]`, and returns. The docstring explains the policy ("the review itself has already been displayed, so the run is not lost"), so the intent is clear, but downstream tooling that depended on non-zero exit codes on save failure would now see exit 0 instead.

### [NOTE] `--since` precedence is asserted in unit tests but not at the CLI layer

The unit test `test_since_wins_with_nothing_to_fall_back_to` proves the precedence bug would surface as a `WARNING` rather than a wrong return value, which is good defensive testing. A CLI-level test that invokes `sq review resolve --since HEAD~3` would catch a regression where the CLI fails to pass the flag through to `resolve_review`.
