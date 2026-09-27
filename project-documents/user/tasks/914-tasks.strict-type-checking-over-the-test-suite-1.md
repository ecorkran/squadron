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

# Tasks: Strict Type Checking Over the Test Suite (1 of 3)

## Context Summary

Part 1 of three; Part 2 is `914-tasks.strict-type-checking-over-the-test-suite-2.md`,
Part 3 is `914-tasks.strict-type-checking-over-the-test-suite-3.md`. All three
share this frontmatter and dependency set.

Closes the fourth and final step of
[issue #50](https://github.com/ecorkran/squadron/issues/50). Widens
`[tool.pyright] include` from `["src"]` to `["src", "tests"]` under the
existing `typeCheckingMode = "strict"`, resolves every error the widening
surfaces, and deletes the deferral comment above `include` in `pyproject.toml`.
Full rationale for every decision below (D1–D8) is in the slice design; tasks
reference it by letter rather than repeating it.

**914 is the last un-started item in the 900-series maintenance plan's original
sequence** — items 915–927 (all later-numbered) already merged while 914
waited, which is why the baseline below has moved twice since the design was
written and moves again in this re-measurement. 928 and 929 remain open but do
not depend on 914.

### Baseline (re-measured 20260927 at `caedf4e5`, superseding the design's two
prior measurements)

The design measured 905 errors/104 files (`03cdd73`, 20260817) and then 1208/139
(`bb65ac9`, 20260926). Re-measured today by temporarily setting
`include = ["src", "tests"]` (not committed, reverted after measurement):

**1270 errors across 143 test files. `src` remains 0 errors** — widening does
not disturb the production baseline. `filesAnalyzed`: 592.

| Count | Rule |
|------:|------|
| 268 | `reportArgumentType` |
| 257 | `reportPrivateUsage` |
| 143 | `reportUnknownMemberType` |
| 120 | `reportUnknownArgumentType` |
| 120 | `reportUnknownLambdaType` |
| 75 | `reportUnknownVariableType` |
| 59 | `reportAttributeAccessIssue` |
| 43 | `reportUnknownParameterType` |
| 35 | `reportMissingParameterType` |
| 25 | `reportUnusedFunction` |
| 25 | `reportOperatorIssue` |
| 24 | `reportUnusedImport` |
| 22 | `reportTypedDictNotRequiredAccess` |
| 21 | `reportIndexIssue` |
| 12 | (7 rules with ≤5 each) |

Top 10 files by error count (542 errors, 43% of the total, spanning 6
directories) — this is Part B in file 2:

| Errors | File | Dominant rules |
|------:|------|------|
| 168 | `tests/providers/openai/test_provider.py` | `reportArgumentType` (all 168) |
| 81 | `tests/server/test_engine.py` | `reportUnknownMemberType`, `reportUnknown/MissingParameterType` |
| 66 | `tests/cli/test_review_profile.py` | `reportUnknownArgumentType`/`reportUnknownLambdaType` (27 each) |
| 46 | `tests/codehost/test_worktree.py` | `reportUnknownArgumentType`/`reportMissingParameterType` (12 each) |
| 34 | `tests/pipeline/test_executor.py` | `reportPrivateUsage` (10) |
| 31 | `tests/pipeline/actions/test_review_action.py` | `reportAttributeAccessIssue` (10) |
| 31 | `tests/pipeline/actions/test_summary.py` | `reportPrivateUsage` (23) |
| 29 | `tests/pr/test_composer.py` | `reportUnknownMemberType` (11) |
| 28 | `tests/pipeline/steps/test_fan_out.py` | `reportUnknownLambdaType` (16) |
| 28 | `tests/pipeline/test_prompt_only_integration.py` | `reportUnknownMemberType`/`reportUnknownArgumentType` (8 each) |

Remainder: `tests/pipeline` (excl. top 10) 275 errors/45 files, `tests/cli`
(excl. top 10) 188/34, everything else 265/54 — these are Parts C, D, E,
covered in files 2 and 3.

`# type: ignore` in `tests/`: **262 comments across 67 files** (D8), hiding
**648 errors** (measured with `enableTypeIgnoreComments = false`: 1918 total vs
1270 — up from the design's 442/1650 figure).

`reportPrivateUsage`: **95 distinct symbols** (up from the design's measured
67). Heaviest: `_REGISTRY` (24), `_execute_summary` (22), `_run_review_command`
(11), `_write_atomic` (11), `_run_pipeline_sdk` (10), `_normalize_line_structure`
(9), `_codex` (7), `_run_pipeline` (6), `_dispatch` (6), `_resolve_slice_inputs`
(6), `_emit_file` (6), `_prompt_checkpoint_interactive` (6), `_state_path` (6),
`_thread` (6); 81 more with ≤4 occurrences each.

`reportUnusedFunction`: 25 sites (D4), spread across 20 files — none
concentrated enough to warrant its own part; dispositioned per file wherever
that file is fixed.

**Pytest floor (D7), measured 20260927:** `4781 passed, 4 skipped`. No later
part may drop below this.

**CI needs no change (Migration Plan):** confirmed —
[`.github/workflows/ci.yml:36`](.github/workflows/ci.yml#L36) runs `uv run
pyright` with no path argument and picks up the config change automatically.

### Decisions this file's tasks apply

- **D1** — no rule relaxation, no `executionEnvironments` block, ever.
- **D5** — two shared mechanical fixes, applied globally before any
  per-directory work, so a file touched by both a helper fix and a later part
  arrives at that part with fewer errors rather than the helper being
  reinvented per directory.
- **D3** — likewise applied globally in this file (not deferred into whichever
  part happens to touch a symbol's file first). `_REGISTRY`, `_execute_summary`,
  and most other heavy symbols are referenced from files scattered across
  Parts B–E; renaming a `src` symbol once here, rather than piecemeal per part,
  is what avoids either double-editing it or leaving later parts still seeing
  the private name.
- **D4, D6, D8** — genuinely per-site/per-file; applied wherever that file is
  fixed in Parts B–E (file 2 and file 3), not globalized here.
- **D2, D7** — per-directory landing with a shrinking `exclude`, gate at every
  part boundary. This file's last task performs the D2 "first commit": widen
  `include`, seed `exclude` with every file still erroring after this file's
  global fixes, delete the deferral comment.

---

## Part A — Infra, Baseline, and the Two Global Passes (D3, D5)

### Task 1.1 — Confirm CI requires no edit

- [ ] Effort: 1/5
- [ ] Read [.github/workflows/ci.yml](.github/workflows/ci.yml) and confirm the
      `uv run pyright` step passes no path argument.
- [ ] Success: confirmed (already true as of this writing); if it is not true,
      stop and report the discrepancy rather than editing the workflow — that
      would be a scope change from the design's Migration Plan.

### Task 1.2 — Re-confirm the error and file-count baseline

- [ ] Effort: 1/5
- [ ] Temporarily set `include = ["src", "tests"]` in
      [pyproject.toml](pyproject.toml) (do not commit). Run
      `uv run pyright --outputjson > /tmp/pyright_baseline.json`.
- [ ] Parse the JSON (`summary.errorCount`, `summary.filesAnalyzed`, and a
      per-file count via `generalDiagnostics`) and compare against the table
      above. If the numbers differ by more than a handful, that is expected
      drift (this baseline is already the third measurement) — use the fresh
      numbers, not this document's, for every later task in this slice.
- [ ] Confirm `src` still reports 0 errors.
- [ ] Do not revert `include` yet — Tasks 1.5–1.10 need it in place to verify
      their fixes. Revert only if you stop before Task 1.14.
- [ ] Success: current total error count and per-file breakdown recorded for
      use in this file and files 2–3.

### Task 1.3 — Measure hidden `# type: ignore` errors (D8)

- [ ] Effort: 1/5
- [ ] With `include` still widened, additionally set
      `enableTypeIgnoreComments = false` (temporary, do not commit). Run
      `uv run pyright --outputjson`, record `summary.errorCount`. Subtract
      Task 1.2's count to get the hidden-error count.
- [ ] Remove `enableTypeIgnoreComments = false`. `include` stays widened for
      now (see Task 1.2).
- [ ] Run `grep -rn "type: ignore" tests/ | wc -l` and
      `grep -rln "type: ignore" tests/ | wc -l` to confirm the comment/file
      counts.
- [ ] Success: hidden-error count and comment/file counts recorded; these are
      the workload figures for D8's per-file disposition in Parts B–E.

### Task 1.4 — Record the pytest floor (D7)

- [ ] Effort: 1/5
- [ ] Run `uv run pytest -q`, record the final passed/skipped/failed line.
- [ ] This is the floor: no task in this slice, in any of the three files, may
      end with a lower passed count or a nonzero failed count.
- [ ] Success: floor recorded.

### Task 1.5 — Fix Helper 1: the `CliRunner.invoke` return-type annotation (D5)

- [ ] Effort: 1/5
- [ ] `typer.testing.CliRunner.invoke` returns `click.testing.Result` (verified
      via `inspect.signature`). Grep for any test helper that wraps it but
      annotates its own return as `-> object` (or otherwise erases the type):
      `grep -rn "def _invoke.*-> object" tests/`. As of 20260927 this is one
      site, `tests/cli/commands/test_summary_run.py:14`, but re-run the grep
      fresh rather than trusting that count — most of the design's originally
      identified 12 modules have already been corrected by intervening slices.
- [ ] For each site found, change the annotation to
      `-> click.testing.Result` and add the import
      (`from click.testing import Result` or via `typer.testing`, whichever the
      file already imports from).
- [ ] Do not touch any `_invoke` helper that is already correctly typed.
- [ ] Success: `grep -rn "def _invoke.*-> object" tests/` returns nothing.

### Task 1.6 — Fix Helper 2: typed `monkeypatch.setattr` lambdas (D5)

- [ ] Effort: 3/5
- [ ] `reportUnknownLambdaType` — 120 sites across 21 files as of 20260927;
      re-derive the current list from Task 1.2's JSON
      (`rule == "reportUnknownLambdaType"`) rather than trusting this count.
      Heaviest files: `tests/cli/test_review_profile.py` (27),
      `tests/pipeline/steps/test_fan_out.py` (16),
      `tests/cli/test_doctor_checks.py` (10),
      `tests/pipeline/test_sdk_session.py` (10),
      `tests/codehost/test_worktree.py` (9),
      `tests/pipeline/actions/test_review_action.py` (9),
      `tests/pipeline/test_executor.py` (7); the remaining 14 files have ≤5
      each.
- [ ] Each site is a lambda passed to `monkeypatch.setattr` whose parameter(s)
      pyright cannot infer. Fix by either replacing the lambda with an
      annotated `def`, or annotating the lambda's binding
      (`f: Callable[[str], bool] = lambda name: ...`). Match the annotation to
      what the patched attribute actually expects — read the target's real
      signature, don't guess a type that merely silences the error.
- [ ] No new shared abstraction is introduced here (design D5) — this is
      annotation work with a consistent shape, done inline at each site.
- [ ] Work file by file, heaviest first, so the diff stays reviewable in `git
      add -p` even though the commit is deferred to Task 1.14.
- [ ] Success: `uv run pyright --outputjson` (with `include` still widened)
      shows 0 `reportUnknownLambdaType` diagnostics.

### Task 1.7 — Gate the two global helper fixes

- [ ] Effort: 1/5
- [ ] Run `uv run ruff format --check . && uv run ruff check .` and
      `uv run pytest -q` (compare against Task 1.4's floor — must not drop).
- [ ] Do **not** commit yet. `include` in `pyproject.toml` is still
      temporarily widened for verification and must not land until Task 1.14
      seeds `exclude` alongside it (D2's "first commit" requirement).
- [ ] Success: format/check clean, pytest at or above the floor.

### Task 1.8 — Classify every `reportPrivateUsage` symbol (D3)

- [ ] Effort: 3/5
- [ ] With `include` still widened, re-run
      `uv run pyright --outputjson` and extract every `reportPrivateUsage`
      diagnostic's symbol name (regex `"(_\w+)"` in the message). As of
      20260927 this is 95 distinct symbols across 257 occurrences.
- [ ] For each symbol, apply the design's test: *does a public name read
      correctly to a caller who is not the test?* Reject the circular
      justification "the test calls it, therefore it is de-facto public" (D3
      names this explicitly as wrong).
- [ ] Pre-classify the design's named exceptions as **keep private** and
      re-verify each still applies given current usage: `_run`, `_client`,
      `_codex`, `_REGISTRY`, `_thread`, `_HEADER`, `_FOOTER`.
- [ ] Classify the remaining heavy symbols and every other symbol the grep
      surfaces. Default to **promote** unless the symbol reads wrong public —
      module-level internals and framework-idiom names are the clear
      keep-private candidates, ordinary helper/accessor functions are not.
- [ ] Record the classification as two lists (promote / keep-private) with a
      one-line reason for each keep-private entry. This becomes the source for
      the Completion Summary tables in file 3.
- [ ] Success: every symbol from the fresh grep appears in exactly one list,
      with a reason recorded for every keep-private entry.

### Task 1.9 — Execute the promotions

- [ ] Effort: 4/5
- [ ] For each symbol in Task 1.8's promote list: rename it in its `src`
      definition (drop the leading underscore) and update every call site in
      both `src` and `tests` (`grep -rn '\b_symbol\b' src/ tests/` before and
      after each rename to confirm no site is missed).
- [ ] Work symbol by symbol or in small batches grouped by module, largest
      blast-radius first (`_REGISTRY`, `_execute_summary`,
      `_run_review_command`, `_write_atomic`, `_run_pipeline_sdk`, … per Task
      1.8's list).
- [ ] Signature-only. No behavior change — do not alter what a renamed
      function does, only what it is called.
- [ ] Re-run `uv run pyright --outputjson` after each batch to confirm the
      renamed symbols' `reportPrivateUsage` diagnostics are gone and no new
      diagnostic appeared (a rename that shadows an existing public name would
      surface as a new error here).
- [ ] Success: every promote-list symbol has zero `reportPrivateUsage` hits and
      no new pyright errors were introduced.

### Task 1.10 — Suppress the kept-private set

- [ ] Effort: 2/5
- [ ] For each symbol in Task 1.8's keep-private list, at every remaining test
      call site add `# pyright: ignore[reportPrivateUsage]` on that line with
      a one-line comment stating why a public name would read wrong (matching
      the reason recorded in Task 1.8).
- [ ] No bulk suppression — one line, one reason, at the call site, not a
      blanket rule (D1, D3).
- [ ] Success: `uv run pyright --outputjson` shows 0 `reportPrivateUsage`
      diagnostics anywhere in the tree.

### Task 1.11 — Test the rename pass

- [ ] Effort: 2/5
- [ ] Run `uv run pytest -q` in full. Compare against Task 1.4's floor —
      identical or higher passed count, zero failures. A drop means a rename
      or a promotion changed behavior, which is a bug in this pass, not an
      acceptable side effect.
- [ ] Spot-run the test modules that reference the heaviest-blast-radius
      symbols (`_REGISTRY`, `_execute_summary`, `_run_review_command`,
      `_write_atomic`, `_run_pipeline_sdk`) individually and confirm they pass
      with informative output, not just green via the full-suite run.
- [ ] Success: full suite at/above the floor; targeted modules pass
      individually.

### Task 1.12 — Gate and commit the D3 rename pass

- [ ] Effort: 1/5
- [ ] Run `uv run ruff format --check . && uv run ruff check .`.
- [ ] Commit the D3 renames and D5 helper fixes together (Tasks 1.5, 1.6, 1.9,
      1.10) as one commit. `include` in `pyproject.toml` is still `["src"]` in
      this commit — do not include the temporary widening.
- [ ] Suggested message:
      `fix(tests): promote private symbols read by tests, type CLI/monkeypatch helpers`
- [ ] Success: commit created; `git status` clean; `pyproject.toml`'s
      `[tool.pyright]` block is unchanged from before this file's work.

### Task 1.13 — Final residual measurement for the exclude seed

- [ ] Effort: 1/5
- [ ] Temporarily widen `include` again (not committed). Run
      `uv run pyright --outputjson`. This per-file list — smaller now than
      Task 1.2's, since Tasks 1.5–1.12 already cleared the two helper rules and
      all `reportPrivateUsage` — is the authoritative `exclude` seed.
- [ ] Success: current per-file error list captured for Task 1.14.

### Task 1.14 — Widen `include`, seed `exclude`, delete the deferral comment; commit

- [ ] Effort: 2/5
- [ ] In [pyproject.toml](pyproject.toml): set
      `include = ["src", "tests"]` permanently. Delete the deferral comment
      above it (the one citing "868 errors" and issue #50).
- [ ] Add every file from Task 1.13's list to `exclude`, one glob per file
      (file-level entries only — no directory entries; a directory entry keeps
      everything under it excluded regardless of the file-level lines added
      later, per design D2). Keep the existing
      `src/squadron/providers/codex/agent.py` entry.
- [ ] Run `uv run pyright` (no temporary edits now — this is the real config).
      Must report **0 errors**. If it does not, a file is missing from
      `exclude` — add it, do not adjust a rule to make it pass.
- [ ] Run `uv run pyright --outputjson | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'])"`
      and confirm `filesAnalyzed` is roughly double the `src`-only count (design's
      sanity check against a config typo that matches nothing).
- [ ] Run `uv run ruff format --check . && uv run ruff check . && uv run pytest -q`
      (at/above Task 1.4's floor).
- [ ] Commit. Suggested message:
      `feat(pyright): widen include to src and tests, seed exclude per file (#50)`
- [ ] Success: all four gate commands pass; this is D2's "first commit" — every
      commit from here forward in this slice keeps pyright at 0 errors.
