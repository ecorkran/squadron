---
docType: tasks
slice: strict-type-checking-over-the-test-suite
project: squadron
lldReference: project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [913, 923]
projectState: Design complete. 913 and 923 both merged (status complete). No code changes made yet for 914.
status: not_started
dateCreated: 20260927
dateUpdated: 20260927
---

# Tasks: Strict Type Checking Over the Test Suite (2 of 3)

## Context Summary

Part 2 of three; Part 1 (`914-tasks.strict-type-checking-over-the-test-suite-1.md`)
did the global setup — `include` is now `["src", "tests"]`, `exclude` lists
every file that still errors, `reportPrivateUsage` and the two D5 helper rules
are already at 0 project-wide. Part 3 is
`914-tasks.strict-type-checking-over-the-test-suite-3.md`.

This file covers design Parts B and C: the 10 heaviest files, then the
`tests/pipeline` remainder. Each file's error count below is what remained
*after* Part 1's global fixes, so it may already be lower than the design's
original figures for the same file.

### Standing rules for every fixing task in this file

Apply these at every site, referencing the design by letter rather than
re-deriving the reasoning:

- **D1** — no rule relaxation, no `executionEnvironments` block. If a file
  seems to need one, stop and report rather than adding it.
- **D4** — `reportUnusedFunction`: if the function carries `@pytest.fixture`,
  add `# pyright: ignore[reportUnusedFunction]` on the `def` line (pytest
  invokes fixtures by collection, not by name — not dead code). Otherwise
  delete the function; a genuinely unreferenced test helper is real dead code.
- **D6** — `reportArgumentType`: read and fix each site individually. If the
  *production* signature is what's wrong (not the test), record it — do not
  quietly change the test to accommodate a wrong signature. Zero found is a
  valid, recorded outcome.
- **D8** — any `# type: ignore` in a file you touch: fix the underlying error
  and delete the comment, or convert it to a single-line
  `# pyright: ignore[rule]` with a justifying comment. No mypy-style bare
  `# type: ignore` may remain in a file once this slice has touched it.
- If a file still reports `reportPrivateUsage` here, Part 1 missed it (or a
  merge since introduced it) — classify and resolve it using Part 1's Task 1.8
  rule, and note the addition for the completion summary in file 3.
- After fixing a file: delete its `exclude` entry in
  [pyproject.toml](pyproject.toml), run `uv run pyright` (0 errors expected
  project-wide, not just in that file), run the file's own test module, and
  `git add` — but do **not** commit until this file's gate tasks (2.11, 3.9 in
  file 3's numbering... see each Part's own gate task). Each Part is one
  commit, matching Part 1's Task 1.12/1.14 pattern.

---

## Part B — The 10 Heaviest Files (design table, spans 6 directories)

### Task 2.1 — `tests/providers/openai/test_provider.py`

- [ ] Effort: 4/5
- [ ] 168 errors, entirely `reportArgumentType` — the largest single-file
      concentration in the tree and, per D6, the rule with no shortcut. Read
      each site; these are the most likely to be real findings (a test passing
      a value the production signature doesn't accept) rather than annotation
      debt.
- [ ] Apply the standing rules above (D4/D6/D8 as encountered).
- [ ] Success: 0 pyright errors attributable to this file; its `exclude` entry
      removed; `uv run pytest tests/providers/openai/test_provider.py -q`
      passes.

### Task 2.2 — `tests/server/test_engine.py`

- [ ] Effort: 3/5
- [ ] 81 errors: `reportUnknownMemberType`, `reportUnknown/MissingParameterType`
      dominate — ordinary missing annotations on locals and helper parameters,
      per D1's finding that this is not `MagicMock` noise.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/server/test_engine.py -q` passes.

### Task 2.3 — `tests/cli/test_review_profile.py`

- [ ] Effort: 3/5
- [ ] Remaining errors after Part 1's Helper 2 pass already removed this
      file's `reportUnknownLambdaType` share — re-measure fresh
      (`uv run pyright`) rather than trusting the 66/27/27 figures from the
      Part 1 baseline, which predate that fix.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/cli/test_review_profile.py -q` passes.

### Task 2.4 — `tests/codehost/test_worktree.py`

- [ ] Effort: 3/5
- [ ] 46 errors before Part 1's lambda fix (9 `reportUnknownLambdaType` sites
      already cleared); remainder is `reportUnknownArgumentType` /
      `reportMissingParameterType` — untyped helper parameters.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/codehost/test_worktree.py -q` passes.

### Task 2.5 — `tests/pipeline/test_executor.py`

- [ ] Effort: 2/5
- [ ] 34 errors before Part 1; 10 were `reportPrivateUsage` (already resolved
      by Task 1.8–1.10) and 7 `reportUnknownLambdaType` (already resolved by
      Task 1.6). Re-measure to size the actual remainder.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/test_executor.py -q` passes.

### Task 2.6 — `tests/pipeline/actions/test_review_action.py`

- [ ] Effort: 2/5
- [ ] 31 errors before Part 1; 10 `reportAttributeAccessIssue` + 9
      `reportUnknownLambdaType` + 6 `reportPrivateUsage` already addressed by
      Parts 1's helper/rename passes if the same shapes. Re-measure for the
      true remainder — expect this file to be mostly clear already.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/actions/test_review_action.py -q` passes.

### Task 2.7 — `tests/pipeline/actions/test_summary.py`

- [ ] Effort: 2/5
- [ ] 31 errors before Part 1; 23 were `reportPrivateUsage` (`_execute_summary`
      is this file's heaviest symbol per Part 1's baseline) — already resolved
      by Task 1.8–1.10. Re-measure the true remainder; also has 2
      `reportUnusedFunction` sites to classify per D4.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/actions/test_summary.py -q` passes.

### Task 2.8 — `tests/pr/test_composer.py`

- [ ] Effort: 2/5
- [ ] 29 errors before Part 1: `reportUnknownMemberType` (11),
      `reportPrivateUsage` (7, already resolved), `reportAttributeAccessIssue`
      (4). Re-measure for the true remainder.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pr/test_composer.py -q` passes.

### Task 2.9 — `tests/pipeline/steps/test_fan_out.py`

- [ ] Effort: 2/5
- [ ] 28 errors before Part 1, 16 of them `reportUnknownLambdaType` (already
      resolved by Task 1.6). Re-measure for the true remainder.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/steps/test_fan_out.py -q` passes.

### Task 2.10 — `tests/pipeline/test_prompt_only_integration.py`

- [ ] Effort: 2/5
- [ ] 28 errors before Part 1: `reportUnknownMemberType`/`reportUnknownArgumentType`
      (8 each), `reportAttributeAccessIssue` (7). Re-measure for the true
      remainder.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/test_prompt_only_integration.py -q` passes.

### Task 2.11 — Gate and commit Part B

- [ ] Effort: 1/5
- [ ] Run the full gate: `uv run ruff format --check . && uv run ruff check .`,
      `uv run pyright` (0 errors), `uv run pytest -q` (at/above file 1 Task
      1.4's floor).
- [ ] Confirm all 10 files' `exclude` entries are gone and no directory-level
      entry was accidentally left covering any of them.
- [ ] Commit Part B as one commit (D2's "each part is one commit" discipline).
      Suggested message: `fix(tests): resolve pyright errors in the 10 heaviest test files`
- [ ] Success: gate passes; commit created.

---

## Part C — `tests/pipeline` Remainder (excl. Part B's 4 pipeline files)

275 errors across 45 files as of the Part 1 baseline (before this file's
earlier fixes reduce it further). Broken out by subdirectory:

| Errors | Location | Files |
|------:|------|------:|
| 40 | `tests/pipeline/actions/` (excl. `test_review_action.py`, `test_summary.py`) | 7 |
| 19 | `tests/pipeline/intelligence/pools/` | 2 |
| 15 | `tests/pipeline/steps/` (excl. `test_fan_out.py`) | 3 |
| 201 | `tests/pipeline/` top-level (excl. `test_executor.py`, `test_prompt_only_integration.py`) | 33 |

### Task 3.1 — `tests/pipeline/actions/` remainder

- [ ] Effort: 3/5
- [ ] 7 files, 40 errors as of the Part 1 baseline. Re-measure current state
      (Part B's fixes may have touched shared fixtures these files import).
      Apply the standing rules per file.
- [ ] Success: 0 errors across the directory, all its files' `exclude` entries
      removed, `uv run pytest tests/pipeline/actions/ -q` passes.

### Task 3.2 — `tests/pipeline/intelligence/pools/` remainder

- [ ] Effort: 2/5
- [ ] 2 files, 19 errors. Apply the standing rules.
- [ ] Success: 0 errors, `exclude` entries removed,
      `uv run pytest tests/pipeline/intelligence/pools/ -q` passes.

### Task 3.3 — `tests/pipeline/steps/` remainder

- [ ] Effort: 2/5
- [ ] 3 files, 15 errors. `tests/pipeline/steps/test_inner_steps.py` has 3
      `reportUnusedFunction` sites — classify each per D4 before deleting or
      suppressing.
- [ ] Success: 0 errors, `exclude` entries removed,
      `uv run pytest tests/pipeline/steps/ -q` passes.

### Task 3.4 — `tests/pipeline/test_prompt_renderer.py`

- [ ] Effort: 2/5
- [ ] 26 errors as of the Part 1 baseline.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/test_prompt_renderer.py -q` passes.

### Task 3.5 — `tests/pipeline/test_state.py`

- [ ] Effort: 2/5
- [ ] 24 errors as of the Part 1 baseline.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/test_state.py -q` passes.

### Task 3.6 — `tests/pipeline/test_judge_cycle.py`

- [ ] Effort: 2/5
- [ ] 23 errors as of the Part 1 baseline.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/pipeline/test_judge_cycle.py -q` passes.

### Task 3.7 — `test_loader_integration.py` and `test_summary_oneshot.py`

- [ ] Effort: 2/5
- [ ] 16 errors each as of the Part 1 baseline (32 total).
- [ ] Success: 0 errors across both files, `exclude` entries removed,
      `uv run pytest tests/pipeline/test_loader_integration.py tests/pipeline/test_summary_oneshot.py -q`
      passes.

### Task 3.8 — `test_emit.py`, `test_sdk_session.py`, `test_findings_addressed_e2e.py`, `test_sources.py`

- [ ] Effort: 2/5
- [ ] 13, 12, 9, 9 errors respectively (43 total) as of the Part 1 baseline.
- [ ] Success: 0 errors across all four files, `exclude` entries removed,
      `uv run pytest tests/pipeline/test_emit.py tests/pipeline/test_sdk_session.py tests/pipeline/test_findings_addressed_e2e.py tests/pipeline/test_sources.py -q`
      passes.

### Task 3.9 — Remaining `tests/pipeline/` top-level stragglers

- [ ] Effort: 3/5
- [ ] The remaining ~24 top-level `tests/pipeline/` files not yet covered by
      Task 3.4–3.8 or Part B, each with ≤5 errors as of the Part 1 baseline
      (`test_executor_integration.py`, `test_batch_report.py`,
      `test_compact_integration.py`, `test_sdk_integration.py`,
      `test_state_integration.py`, `test_cli_integration.py`,
      `test_compact_compose_integration.py`, `test_executor_each.py`,
      `test_findings_addressed_evidence.py`, `test_findings_addressed_judge.py`,
      `test_dispatch.py`, `test_sdk_wiring.py`, `test_summary_context.py`,
      `conftest.py`, and the remaining single-error files). Re-derive the exact
      current list from a fresh `uv run pyright --outputjson` filtered to
      `tests/pipeline/*.py` rather than trusting this enumeration, which
      predates every earlier task in this Part.
- [ ] Apply the standing rules to each; most are single-annotation fixes.
- [ ] Success: 0 errors remaining anywhere under `tests/pipeline/`, every
      remaining `exclude` entry under that directory removed,
      `uv run pytest tests/pipeline/ -q` passes.

### Task 3.10 — Gate and commit Part C

- [ ] Effort: 1/5
- [ ] Run the full gate: `uv run ruff format --check . && uv run ruff check .`,
      `uv run pyright` (0 errors), `uv run pytest -q` (at/above the floor).
- [ ] Confirm `grep -n "tests/pipeline" pyproject.toml` (against the `exclude`
      list) returns nothing.
- [ ] Commit Part C as one commit. Suggested message:
      `fix(tests): resolve pyright errors in the tests/pipeline remainder`
- [ ] Success: gate passes; commit created.
