---
docType: review
layer: project
reviewType: code
slice: pipeline-verbosity-passthrough-v-vv
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/902-slice.pipeline-verbosity-passthrough-v-vv.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260427
dateUpdated: 20260427
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Bootstrap step types refactoring"
    location: src/squadron/pipeline/steps/__init__.py:65-92
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Location normalization with soft-fail"
    location: src/squadron/review/parsers.py:107-131
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Diff-membership and path-existence validation"
    location: src/squadron/review/parsers.py:133-185
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Git diff filename extraction"
    location: src/squadron/review/review_client.py:297-328
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Updated call sites pass through validation context"
    location: src/squadron/review/review_client.py:164-175
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Updated regex patterns handle edge cases"
    location: src/squadron/review/parsers.py:97-100
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Comprehensive test coverage"
    location: tests/review/test_parsers.py
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Test registry integration tests"
    location: tests/pipeline/steps/test_registry_integration.py:71-91
---

# Review: code — slice 902

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Bootstrap step types refactoring

The introduction of `bootstrap_step_types()` centralizes step-type registration into a single idempotent function. This is a solid DRY improvement: previously, three separate call sites (`executor.py`, `loader.py`, `prompt_renderer.py`) maintained identical import lists — adding a new step type required editing all three. Now there's one source of truth.

The implementation is correct:
- The `_bootstrapped` guard makes it idempotent (multiple calls are cheap no-ops)
- Each import is annotated with `# noqa: F401 pyright: ignore[reportUnusedImport]` to suppress false positives from linters
- The function is properly exported in `__all__`

### [PASS] Location normalization with soft-fail

The `_normalize_location()` function implements the project's "Never use silent fallback values" principle well. Missing or placeholder locations (`""`, `"-"`, `"global"`, `"n/a"`, `"none"`) are normalized to the explicit sentinel `"unverified"` rather than silently passed as `None` or empty strings. A WARNING is logged with enough context (finding ID, title, template name, verdict) for downstream triage.

The test coverage is thorough:
- `test_missing_location_normalized_and_warned` verifies the warning fires with correct details
- `test_placeholder_values_normalized_to_unverified` parameterizes across all placeholder variants
- `test_unverified_passed_through_without_warning` confirms the explicit sentinel doesn't re-trigger

### [PASS] Diff-membership and path-existence validation

Two post-extraction validation functions were added:

1. `_check_diff_membership()` - When a diff file set is provided (code-template reviews), each finding's location is checked against the diff. Files not in the diff log a WARNING.

2. `_check_path_existence()` - When a `cwd` is provided, each finding's location is checked for disk existence. Non-existent paths log a WARNING.

Both checks skip `UNVERIFIED_LOCATION` findings, and `_location_path()` handles path extraction cleanly with a regex that guards against malformed input (values starting with `<` from prompt examples).

### [PASS] Git diff filename extraction

The `_run_git_diff_filenames()` function extracts the list of changed files for the parser's diff-membership check. Error handling follows project conventions:
- Uses `subprocess.run` with `check=False` and explicit return code handling
- Logs a WARNING on failure and returns an empty set (soft-fail rather than crash)
- Catches `FileNotFoundError` and `OSError` specifically (not bare `except:`)

### [PASS] Updated call sites pass through validation context

The `run_review_with_profile()` function now resolves `diff_files` and `cwd` from inputs and passes them to `parse_review_output()`. This wires the validation checks end-to-end.

### [PASS] Updated regex patterns handle edge cases

The regex patterns for extracting `category:` and `location:` tags were updated to use `[ \t]*` instead of `\s*` in the value capture group. This prevents value bleed across empty lines (e.g., an empty `location:` tag would not incorrectly capture the next line's content).

### [PASS] Comprehensive test coverage

The test suite for slice 904 (location validation) is well-structured:
- `TestLocationSoftFail` - covers normalization and warning behavior
- `TestLocationDiffMembershipAndPathExistence` - covers all combinations (in diff + exists, in diff + missing, out of diff + exists, out of diff + missing, arch review paths)
- Tests use `caplog.at_level("WARNING")` to assert log output
- Tests use `tmp_path` fixture for filesystem isolation

### [PASS] Test registry integration tests

Two regression tests added:
- `test_bootstrap_step_types_registers_every_canonical_name` - Guards against drift between `StepTypeName` enum and the bootstrap import list
- `test_bootstrap_resolves_loop_collection_fan_out` - Specifically guards the three step types that were missing from the prompt-only path

Both tests will fail if someone adds a new step type without updating `bootstrap_step_types()`.
