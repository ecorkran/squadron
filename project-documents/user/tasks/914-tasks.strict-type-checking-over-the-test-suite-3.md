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

# Tasks: Strict Type Checking Over the Test Suite (3 of 3)

## Context Summary

Part 3 of three. Part 1
(`914-tasks.strict-type-checking-over-the-test-suite-1.md`) did the global
setup; Part 2 (`914-tasks.strict-type-checking-over-the-test-suite-2.md`)
cleared the 10 heaviest files and the `tests/pipeline` remainder. This file
covers design Parts D and E — `tests/cli` remainder and everything else — then
the final verification walkthrough and the slice's required Completion
Summary.

The standing rules from file 2's Context Summary (D1, D4, D6, D8 applied per
file; delete the `exclude` entry; gate once per Part, not per file) apply here
unchanged.

---

## Part D — `tests/cli` Remainder (excl. `test_review_profile.py`, `test_worktree.py` is `tests/codehost`)

188 errors across 34 files as of the Part 1 baseline:

| Errors | Location | Files |
|------:|------|------:|
| 44 | `tests/cli/commands/` | 7 |
| 144 | `tests/cli/` top-level (excl. `test_review_profile.py`) | 27 |

### Task 4.1 — `tests/cli/commands/` remainder

- [ ] Effort: 3/5
- [ ] 7 files, 44 errors as of the Part 1 baseline. Apply the standing rules.
- [ ] Success: 0 errors across the directory, `exclude` entries removed,
      `uv run pytest tests/cli/commands/ -q` passes.

### Task 4.2 — `tests/cli/test_model_list.py`

- [ ] Effort: 3/5
- [ ] 23 errors as of the Part 1 baseline, concentrated in
      `reportTypedDictNotRequiredAccess` (per design D5: accessing optional
      `ModelAlias` keys — `private`, `cost_tier`, `notes`, `pricing` — without
      a presence check). Each site needs a real presence check or explicit
      narrowing, **not** a suppression — this is the fixture-drift signal the
      slice exists to surface (D5 explicitly rejects treating these as helper
      material).
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/cli/test_model_list.py -q` passes.

### Task 4.3 — `tests/cli/test_doctor_checks.py`

- [ ] Effort: 2/5
- [ ] 21 errors as of the Part 1 baseline.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/cli/test_doctor_checks.py -q` passes.

### Task 4.4 — `tests/cli/test_review_resolve.py`

- [ ] Effort: 2/5
- [ ] 17 errors as of the Part 1 baseline.
- [ ] Success: 0 errors, `exclude` entry removed,
      `uv run pytest tests/cli/test_review_resolve.py -q` passes.

### Task 4.5 — `tests/cli/test_review_pr_worktree.py` and `tests/cli/conftest.py`

- [ ] Effort: 2/5
- [ ] 13 and 11 errors respectively as of the Part 1 baseline. `conftest.py`
      fixtures are shared across the directory — fix it first within this task
      and re-measure the rest of `tests/cli/` before continuing, since a
      conftest annotation fix can silently clear downstream errors.
- [ ] Success: 0 errors across both files, `exclude` entries removed,
      `uv run pytest tests/cli/ -q -k "review_pr_worktree"` passes and the full
      `tests/cli/` collection still succeeds.

### Task 4.6 — Mid-tier `tests/cli/` stragglers

- [ ] Effort: 2/5
- [ ] `test_doctor.py` (8), `test_review_pr.py` (7), `test_review_format.py`
      (6) as of the Part 1 baseline (21 total). Apply the standing rules.
- [ ] Success: 0 errors across all three files, `exclude` entries removed,
      `uv run pytest tests/cli/test_doctor.py tests/cli/test_review_pr.py tests/cli/test_review_format.py -q`
      passes.

### Task 4.7 — Remaining `tests/cli/` stragglers

- [ ] Effort: 2/5
- [ ] The remaining ~19 `tests/cli/` files not yet covered, each with ≤5
      errors as of the Part 1 baseline (`test_command_surface.py`,
      `test_install_commands.py`, `test_setup.py`, `test_review_save.py`,
      `test_review_save_outcome.py`, `test_review_scope.py`,
      `test_spawn_profile.py`, and the remaining single-error files). Re-derive
      the exact current list from a fresh `uv run pyright --outputjson`
      filtered to `tests/cli/*.py` rather than trusting this enumeration.
- [ ] Success: 0 errors remaining anywhere under `tests/cli/`, every remaining
      `exclude` entry under that directory removed,
      `uv run pytest tests/cli/ -q` passes.

### Task 4.8 — Gate and commit Part D

- [ ] Effort: 1/5
- [ ] Full gate (`ruff format --check`, `ruff check`, `pyright` 0 errors,
      `pytest -q` at/above the floor).
- [ ] Confirm `grep -n "tests/cli" pyproject.toml` (against `exclude`) returns
      nothing.
- [ ] Commit Part D as one commit. Suggested message:
      `fix(tests): resolve pyright errors in the tests/cli remainder`
- [ ] Success: gate passes; commit created.

---

## Part E — Everything Else

265 errors across 54 files as of the Part 1 baseline, spanning every remaining
directory:

| Errors | Directory | Files |
|------:|------|------:|
| 111 | `tests/review/` | 18 |
| 33 | `tests/providers/codex/` | 2 |
| 26 | `tests/providers/openai/` (excl. `test_provider.py`) | 4 |
| 22 | `tests/tools/` | 12 |
| 19 | `tests/events/` | 3 |
| 10 | `tests/client/` | 1 |
| 7 | `tests/server/` (excl. `test_engine.py`) | 2 |
| 6 each | `tests/integrations/`, `tests/metrology/`, `tests/providers/` (top-level) | 1, 2, 2 |
| 5 | `tests/pr/` (excl. `test_composer.py`) | 1 |
| 4 each | `tests/core/`, `tests/documents/` | 1, 1 |
| 3 | `tests/providers/sdk/` | 2 |
| 2 | `tests/conftest.py` | 1 |
| 1 | `tests/load/` | 1 |

### Task 5.1 — `tests/review/` heaviest 4

- [ ] Effort: 3/5
- [ ] `test_parsers.py` (26), `test_content_injection.py` (21),
      `test_models.py` (15), `test_git_utils.py` (13) as of the Part 1
      baseline (75 total). Apply the standing rules.
- [ ] Success: 0 errors across the four files, `exclude` entries removed,
      `uv run pytest tests/review/test_parsers.py tests/review/test_content_injection.py tests/review/test_models.py tests/review/test_git_utils.py -q`
      passes.

### Task 5.2 — `tests/review/` remainder

- [ ] Effort: 2/5
- [ ] The remaining 14 `tests/review/` files (`test_save_target.py`,
      `test_review_client.py`, `conftest.py`, and the rest at ≤3 errors each),
      ~36 errors total as of the Part 1 baseline. Re-derive the current list
      from a fresh `uv run pyright --outputjson` filtered to `tests/review/`.
- [ ] Success: 0 errors remaining anywhere under `tests/review/`, every
      `exclude` entry under that directory removed,
      `uv run pytest tests/review/ -q` passes.

### Task 5.3 — `tests/providers/codex/`

- [ ] Effort: 2/5
- [ ] `test_auth.py` (18), `test_agent.py` (15) as of the Part 1 baseline.
      `test_agent.py` also has a `reportUnusedFunction` site — classify per D4.
- [ ] Success: 0 errors across both files, `exclude` entries removed,
      `uv run pytest tests/providers/codex/ -q` passes.

### Task 5.4 — `tests/providers/openai/` remainder

- [ ] Effort: 2/5
- [ ] `test_tool_result_cap.py` (13), `test_translation.py` (8),
      `test_agentic_loop.py` (4), `test_agent.py` (1) as of the Part 1
      baseline.
- [ ] Success: 0 errors across all four files, `exclude` entries removed,
      `uv run pytest tests/providers/openai/ -q` passes (full directory,
      including Part B's `test_provider.py`).

### Task 5.5 — `tests/tools/`

- [ ] Effort: 2/5
- [ ] 12 files, 22 errors as of the Part 1 baseline, none concentrated.
- [ ] Success: 0 errors across the directory, `exclude` entries removed,
      `uv run pytest tests/tools/ -q` passes.

### Task 5.6 — `tests/events/`

- [ ] Effort: 2/5
- [ ] `test_dispatcher.py` (10), `test_registry.py` (7), `test_discovery.py`
      (2) as of the Part 1 baseline. `test_dispatcher.py` and `test_registry.py`
      each have a `reportUnusedFunction` site — classify per D4.
- [ ] Success: 0 errors across the directory, `exclude` entries removed,
      `uv run pytest tests/events/ -q` passes.

### Task 5.7 — `tests/client/` and `tests/server/` remainder

- [ ] Effort: 2/5
- [ ] `tests/client/test_http.py` (10), `tests/server/test_routes.py` (6),
      `tests/server/conftest.py` (1) as of the Part 1 baseline.
- [ ] Success: 0 errors across all three files, `exclude` entries removed,
      `uv run pytest tests/client/ tests/server/ -q` passes (full directories,
      including Part B's `test_engine.py`).

### Task 5.8 — Remaining small directories, swept together

- [ ] Effort: 3/5
- [ ] `tests/integrations/test_context_forge.py` (6),
      `tests/metrology/test_audit_variance.py` (5) and
      `test_audit_harness.py` (1), `tests/providers/test_auth_resolution.py`
      (5) and `test_loader.py` (1), `tests/pr/test_inputs.py` (5),
      `tests/core/test_agent_registry.py` (4),
      `tests/documents/test_schema_drift.py` (4),
      `tests/providers/sdk/test_agent.py` (2) and `test_registration.py` (1),
      `tests/conftest.py` (2), `tests/load/test_grep_timeout.py` (1) — 37
      errors across 11 files as of the Part 1 baseline. Re-derive the current
      list from a fresh `uv run pyright --outputjson` before starting, since
      this is the last-measured and most drift-prone group.
- [ ] Success: `uv run pyright` reports **0 errors project-wide** — this task
      closes out the last of `exclude`, so this is the point where the file is
      empty of every entry except the pre-existing
      `src/squadron/providers/codex/agent.py` line.

### Task 5.9 — Gate and commit Part E

- [ ] Effort: 1/5
- [ ] Full gate (`ruff format --check`, `ruff check`, `pyright` 0 errors,
      `pytest -q` at/above the floor from file 1's Task 1.4).
- [ ] Confirm `[tool.pyright] exclude` in `pyproject.toml` contains exactly one
      entry: `src/squadron/providers/codex/agent.py`.
- [ ] Commit Part E as one commit. Suggested message:
      `fix(tests): resolve remaining pyright errors, exclude down to one entry`
- [ ] Success: gate passes; commit created; `exclude` has exactly one line.

---

## Final Verification

### Task 6.1 — Run the design's verification walkthrough

- [ ] Effort: 2/5
- [ ] Run every command in the slice design's **Verification Walkthrough**
      section (steps 1–5): the `[tool.pyright]` block eyeball check, `uv run
      pyright` + `--outputjson` summary check (`filesAnalyzed` roughly double
      the `src`-only count), `uv run pytest -q` + ruff, the acceptance-test
      probe (plant `def _probe() -> int: return "not an int"` in any test
      file, confirm `reportReturnType` fires, revert, confirm `git status`
      clean), and the suppression-inventory greps.
- [ ] Success: every walkthrough step produces the expected result stated in
      the design.

### Task 6.2 — Audit every retained suppression

- [ ] Effort: 2/5
- [ ] `grep -rn "type: ignore" tests/` must return **nothing** — every
      instance was fixed or converted to `# pyright: ignore[rule]` across
      files 1–3.
- [ ] `grep -rn "pyright: ignore" tests/` — read every line. Each must sit on
      a `@pytest.fixture`-decorated `def` (D4) or carry a justifying comment
      (D3's kept-private set). Anything else is unresolved work — go fix it,
      don't document it as an exception.
- [ ] `grep -n "basic\|reportUnknown.*false\|executionEnvironments" pyproject.toml`
      must return nothing (D1).
- [ ] Success: both greps come back clean per the above.

### Task 6.3 — Fill in the slice design's Completion Summary

- [ ] Effort: 2/5
- [ ] In `914-slice.strict-type-checking-over-the-test-suite.md`'s Completion
      Summary section: record errors remaining (must be 0), one sentence per
      action taken with files touched and errors cleared, the full promote
      table from file 1 Task 1.8/1.9 (symbol, new name, `src` sites, why it
      belongs in the contract), the full kept-private table (symbol, why a
      public name reads wrong), and the D6 "production signatures found wrong"
      list (record zero if zero — a null result is a valid, required output
      per the design).
- [ ] Success: every row the design's Completion Summary template asks for is
      filled in, none left as the template's example placeholder.

### Task 6.4 — Update statuses, the plan, the issue, and the DEVLOG

- [ ] Effort: 1/5
- [ ] Set `status: complete` in this file's frontmatter, files 1 and 2's
      frontmatter, and the slice design's frontmatter.
- [ ] Check off item 12 in
      [900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md)
      and set its status line to complete with today's date.
- [ ] Update [issue #50](https://github.com/ecorkran/squadron/issues/50):
      step 4 (pyright over tests) is done — all four steps of the issue are
      now complete; close it, referencing this slice and the three commits
      from Parts A–E.
- [ ] Write the DEVLOG entry per `prompt.ai-project.system.md`'s Session State
      Summary guidance. Record: final error count (0), how many symbols were
      promoted vs. kept private, and any production signature found wrong
      under D6.
- [ ] Success: all four artifacts (this file, files 1–2, the slice design, the
      plan) reflect `complete`; the issue is closed; the DEVLOG entry exists.
