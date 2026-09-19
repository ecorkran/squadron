---
docType: tasks
slice: small-fixes-batch
project: squadron
lldReference: project-documents/user/slices/921-slice.small-fixes-batch.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Design finalized through two review rounds (FAIL → CONCERNS, both addressed). Scope is #67 (unknown model alias dispatches silently) and #103 (--restore matches sibling projects by prefix). #78 and #65-finding-1 were found already fixed and dropped from scope during design.
status: complete
dateCreated: 20260917
dateUpdated: 20260917
---

# Tasks: Small Fixes Batch

## Context Summary

Two independently small, root-caused bugs, bundled as one maintenance slice
per [900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md)
entry 19:

- **Fix 1 (#67)** — `resolve_model_alias` returns `(name, None)` for any
  unrecognized name, on the assumption that it's a literal model ID. There's
  no way today to distinguish a typo'd alias from a real literal ID, so a
  typo silently dispatches to the SDK and produces a misleading
  workspace-trust warning plus an UNKNOWN verdict that overwrites a prior
  valid review. The fix adds a guard: when alias resolution is a no-op *and*
  no profile is supplied through any of the three normal channels (flag,
  template, config), that's now treated as a genuine unknown-alias error and
  rejected before dispatch. When any of the three channels does supply a
  profile, today's passthrough behavior is unchanged — that's the signal
  that the name is a deliberate literal model ID. The same guard applies to
  the judge-resolution path (`_resolve_judge_model`), sharing one helper.
- **Fix 2 (#103)** — `sq summary --restore` with no `--key` resolves the most
  recently modified file matching `{project}-*.md`, which also matches any
  sibling checkout whose directory name starts with `{project}-` (e.g.
  `squadron` matching `squadron-pr-*.md`). The fix derives sibling project
  names from real sibling checkout directories on disk and excludes
  sibling-owned files from the *default* (no-`--key`) selection only —
  `--key` continues to reach every file, including excluded ones.

Both fixes are grounded in the finalized design
([921-slice.small-fixes-batch.md](project-documents/user/slices/921-slice.small-fixes-batch.md)),
which went through two review rounds. Read the design's "Correction from
slice review" and numbered review-finding callouts (F001–F004 across both
rounds) before implementing — they record predicates that look plausible but
are wrong, and the design explains why.

**Current project state:** no code changes yet; design only. Both fixes are
independent of each other and can be implemented in either order — this task
file does Fix 1 first, then Fix 2, then a combined final verification.

**Dependencies:** none.

**Next planned slice:** none specific — general maintenance backlog per
[900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md).

---

## Part A — Fix 1 (#67): reject unknown model alias before dispatch

### Task 1.1 — Add the shared `_reject_unknown_alias` helper

- [x] Effort: 2/5
- [x] In [src/squadron/cli/commands/review.py](src/squadron/cli/commands/review.py),
      add a new function near `_resolve_profile` (~line 506):
      `_reject_unknown_alias(name: str, profile_flag: str | None, template: ReviewTemplate | None) -> None`.
- [x] The helper performs the same three-step check `_resolve_profile`
      performs internally — `profile_flag`, then `template.profile`, then
      `get_config("default_review_profile")` — **without** the `"sdk"`
      fallback. If all three are `None`/absent, raise with a clear message:
      `unknown model alias '{name}'; known: {sorted(get_all_aliases().keys())}`,
      followed by a remedy clause naming `--profile` — e.g. `If this is a
      literal model ID, pass --profile to dispatch it directly.` The remedy
      clause is required, not cosmetic: per the design's review-F003
      paragraph, a *valid* literal model ID with no profile from any channel
      now hits this same error, and the message is the only place that
      distinguishes "you typo'd" from "you need to say --profile" (see
      Task 1.2). If any of the three supplies a value, return normally (no
      rejection).
- [x] Import `get_all_aliases` from `squadron.models.aliases` alongside the
      existing `model_allows_tools, resolve_model_alias` import (line 28).
- [x] Raise a `typer.Exit(code=1)` after printing the error with `rprint`, in
      the same style as the other error paths in this file (e.g.
      lines 566-568) — not a bare `ValueError` or similar, so the CLI exits
      cleanly rather than printing a traceback.
- [x] Do not call this helper from anywhere yet — that's Tasks 1.2 and 1.3.
- [x] Success: the helper compiles and type-checks (`uv run pyright`); it is
      not yet referenced by any call site.

### Task 1.2 — Wire the guard into `_run_review_command`

- [x] Effort: 2/5
- [x] In `_run_review_command` (review.py:538+), add the guard **inside** the
      `if raw_model is not None:` block (review.py:604-605), immediately
      after `alias_model, alias_profile = resolve_model_alias(raw_model)` and
      before the block closes: if `alias_model == raw_model and alias_profile
      is None` (i.e. resolution was a no-op — the exact condition the
      design's Fix 1 names), call
      `_reject_unknown_alias(raw_model, profile_flag, template)`.
- [x] **Placement is load-bearing.** `alias_model` and `alias_profile` are
      both initialized to `None` and only assigned inside that `if` block, so
      placing the guard *after* the block makes `None == None and None is
      None` true for every model-less invocation — the guard would fire with
      `unknown model alias 'None'` whenever no model is supplied by flag,
      config, or template. If you prefer the guard outside the block, the
      condition must also include `raw_model is not None`.
- [x] Do not change the `resolved_model = alias_model or raw_model` or
      `resolved_profile = _resolve_profile(...)` lines — when the guard does
      not reject, behavior is identical to today.
- [x] Read the design's "Collateral effects to record" section
      (921-slice.small-fixes-batch.md) before finishing this task. It records
      **two** behavior changes, both intentional, neither a bug to work
      around:
      1. A stale `default_model` config value with no profile anywhere now
         fails loudly instead of silently dispatching.
      2. (design review F003) A **valid literal model ID** — not a typo —
         passed as `--model` with no `--profile` flag and no
         `default_review_profile` config now fails too. No shipped template
         declares `profile:`, so `template.profile` is always `None` in
         practice and that channel cannot rescue this shape. The guard cannot
         distinguish a valid literal ID from a typo without the `--profile`
         signal.
- [x] Because of (2), `_reject_unknown_alias`'s message from Task 1.1 must
      name `--profile` as the remedy, so a user passing a real literal model
      ID is told how to proceed rather than being told only that their name
      is unknown. Amend Task 1.1's message accordingly, e.g.
      `unknown model alias '{name}'; known: {...}. If this is a literal model
      ID, pass --profile to dispatch it directly.`
- [x] Success: `uv run pyright` reports 0 new errors; manual trace confirms
      the guard only fires on the no-op-resolution branch **and** never on a
      model-less invocation; the error message names `--profile`.

### Task 1.3 — Wire the same guard into `_resolve_judge_model`

- [x] Effort: 1/5
- [x] In `_resolve_judge_model` (review.py:1160-1176), apply the identical
      guard **inside** that function's `if raw_model is not None:` block,
      immediately after `alias_model, alias_profile =
      resolve_model_alias(raw_model)`: if resolution was a no-op, call
      `_reject_unknown_alias(raw_model, profile_flag, template)`.
- [x] The same placement trap as Task 1.2 applies verbatim — this function
      has the identical `None`-initialization shape, so a guard placed after
      the block fires on every model-less judge resolution.
- [x] Use the same helper from Task 1.1 — do not duplicate the three-way
      profile check inline (design explicitly calls this out, review F004).
- [x] Success: `uv run pyright` reports 0 new errors; `_resolve_judge_model`
      and `_run_review_command` both call the same helper function.

### Task 1.4 — Update the existing test that now contradicts the fix

- [x] Effort: 1/5
- [x] In [tests/cli/test_review_profile.py](tests/cli/test_review_profile.py),
      `test_unknown_model_passes_through` (~line 290) currently asserts that
      an unrecognized model name (`"llama-3-70b"`) with no `--profile` flag
      and `get_config` mocked to return `None` passes through unchanged with
      profile defaulting to `"sdk"`. Under this fix, that exact scenario (no
      profile from any of the three channels) must now raise the
      unknown-alias error instead.
- [x] Rename the test to reflect the new behavior (e.g.
      `test_unknown_model_with_no_profile_source_raises`) and change its body
      to assert `_run_review_command(...)` raises `typer.Exit` with
      `exc_info.value.exit_code == 1`, rather than asserting on
      `mock_exec.call_args`.
- [x] Add a second test in the same class,
      `test_unknown_model_with_explicit_profile_passes_through`, that
      reproduces the old passthrough case but supplies `profile_flag="sdk"`
      (or any explicit profile) — confirming the previous behavior is
      preserved exactly when a profile is explicitly supplied, matching the
      design's "explicit signal" rationale.
- [x] Success: `uv run pytest tests/cli/test_review_profile.py -q` passes,
      including both the renamed and new test.

### Task 1.5 — Add tests for the new guard's three-channel check

- [x] Effort: 2/5
- [x] In the same file, add tests covering the two channels not exercised by
      Task 1.4: (a) unknown alias with no `--profile` flag but a
      `template.profile` set — passes through, does not raise; (b) unknown
      alias with no flag, no template profile, but
      `default_review_profile` config set — passes through, does not raise.
- [x] Add one test asserting the error message includes
      `unknown model alias`, the literal name that was passed, and the
      `--profile` remedy clause from Task 1.1 — so a user sees both what was
      rejected and how to proceed with a real literal model ID.
- [x] Add a **no-model regression test**: `_run_review_command` invoked with
      no model from any channel (no `--model` flag, `get_config` returning
      `None`, template with no `model:`) must dispatch normally and **not**
      raise — guarding the Task 1.2 placement trap directly rather than
      relying on `test_run_review_command_defaults_to_sdk`
      (tests/cli/test_review_profile.py:144) to catch it incidentally.
- [x] Success: `uv run pytest tests/cli/test_review_profile.py -q` passes,
      covering all three profile-source channels, the reject case, and the
      no-model case.

### Task 1.6 — Add a test for the judge path

- [x] Effort: 1/5
- [x] Locate or create a test module for `_resolve_judge_model` (check
      [tests/cli/test_review_resolve.py](tests/cli/test_review_resolve.py) and
      [tests/review/test_cli_review_resolve.py](tests/review/test_cli_review_resolve.py)
      first — extend whichever already covers judge-model resolution rather
      than creating a third file).
- [x] Add a test: `_resolve_judge_model` called with an unknown model name,
      no `--profile` flag, and no config default raises the same
      unknown-alias error as the main review path.
- [x] Success: the new test passes; `uv run pytest tests/cli tests/review -q`
      passes in full (no regressions in either directory).

### Task 1.7 — Gate and commit Part A

- [x] Effort: 1/5
- [x] Run: `uv run ruff format --check`, `uv run ruff check`,
      `uv run pyright` (0 errors), `uv run pytest -q` (record the baseline
      pass count from `main` before this slice, confirm no unexplained
      drop — only the intentionally-changed test from Task 1.4 and the new
      tests from 1.5/1.6 should account for any count change).
- [x] Commit Part A alone: the helper, both call sites, and all Part-A test
      changes together (so no commit in history has the guard active with a
      contradicting test still in the suite).
- [x] Commit message: `fix: reject unknown model alias before dispatch (#67)`.
- [x] Success: all four gate commands pass; Fix 1 is live on its own commit.

---

## Part B — Fix 2 (#103): scope `--restore` default selection to sibling-excluded matches

### Task 2.1 — Add the sibling-project derivation helper

- [x] Effort: 2/5
- [x] In [src/squadron/cli/commands/summary_instructions.py](src/squadron/cli/commands/summary_instructions.py),
      add a new function near `_summary_key` (line 82):
      `_sibling_projects(cwd: str, project: str) -> set[str]`.
- [x] Implementation: resolve `Path(cwd).resolve().parent`, then
      `iterdir()` over it, collecting directory names other than `project`
      itself into a `set[str]`. Only directory entries count (skip files).
- [x] Wrap the `iterdir()` call in `try/except OSError`: on failure, log at
      WARNING with the parent path and the exception (use `logging.exception`
      or `logger.warning(..., exc_info=True)` per the project's exception
      rule — this file currently has no module logger, so add
      `logger = logging.getLogger(__name__)` near the top-level imports), and
      return an empty `set[str]` — this degrades to today's unfiltered
      behavior for that invocation rather than crashing (design's Fix 2
      "Failure modes" section, review F002).
- [x] Add a one-line code comment stating the heuristic's known limitation:
      it only catches sibling projects checked out next to the current one on
      the same machine (design's "Known-project-name source" section) —
      state this rather than implying completeness.
- [x] Success: `uv run pyright` reports 0 new errors. Not yet called from
      `_handle_restore` — that's Task 2.2.

### Task 2.2 — Partition matches into clean/excluded and scope default selection

- [x] Effort: 3/5
- [x] In `_handle_restore` (summary_instructions.py:91-131), after computing
      `matches` (lines 110-114), call `_sibling_projects(cwd, project)` and
      partition `matches` into two lists:
      - `excluded`: stem starts with `f"{sibling}-"` for some `sibling` in
        the returned set **where `project` does not itself start with
        `f"{sibling}-"`** (the design's "prefix-continuation" qualifier).
      - `clean`: everything else.
- [x] **The qualifier is load-bearing — do not simplify it away.** It guards
      the case where the sibling's name is *shorter* than the current
      project's. Run from the `squadron-pr` worktree, `project` is
      `squadron-pr` and the sibling set contains `squadron`; every stem in
      `matches` starts with `squadron-` by construction of the
      `{project}-*.md` glob, so the unqualified predicate marks **every**
      `squadron-pr` summary as excluded, leaving `clean` empty and making
      bare `--restore` raise "no summary files found" in a worktree that has
      eight summaries of its own. That is the inverse of #103 and strictly
      worse than today's behavior. With the qualifier, `squadron-pr` starts
      with `squadron-`, so `squadron` is skipped as an exclusion source and
      the summaries stay clean.
- [x] Task 2.4 must cover this direction explicitly — see its
      reversed-roles case.
- [x] Change the no-`--key` default selection (currently `matches[0]` inside
      `_select_summary`, line 142) to select from `clean` only. Read the
      design's "Disambiguation policy" section carefully before implementing
      this: `_summary_key`'s return value must **not** change for any
      stem — it always returns `path.stem.removeprefix(f"{project}-")`,
      including for excluded files. Only the default (no-`--key`) selection
      pool is restricted; `--key` matching still searches the full
      `matches` list unchanged, so an excluded file stays reachable by its
      exact key. Do not apply any exclusion filtering inside `_summary_key`
      or the `--key` branch of `_select_summary`.
- [x] When `clean` is empty but `matches` (unfiltered) is not, the no-`--key`
      path must raise the same "no summary files found for project
      '{project}'" error (line 117-121) that fires when `matches` itself is
      empty — not silently fall through to an excluded file. This likely
      means passing both `matches` and `clean` into `_select_summary`, or
      restructuring so `_handle_restore` checks `clean` emptiness directly
      before calling `_select_summary` for the no-key case.
- [x] Update the stderr picker listing (lines 123-126, `Found {N} summaries
      for '{project}':` loop) to mark excluded entries distinctly, e.g.
      appending `(excluded from default — matches sibling project
      '{sibling}'; use --key '{key}' to restore)` to that entry's line. The
      listing must still show every file in `matches` (clean and excluded
      alike) — only the default-selection pool is restricted, not the
      picker's visibility.
- [x] Success: manual trace of the three cases (clean-only matches,
      mixed clean+excluded matches, excluded-only matches) confirms: default
      selection only ever returns a `clean` file or raises; `--key` reaches
      any file regardless of exclusion; the stderr listing shows all files
      with excluded ones marked.

### Task 2.3 — Test the sibling-derivation helper directly

- [x] Effort: 2/5
- [x] In whichever of the two existing test files covers `--restore`
      internals —
      [tests/cli/commands/test_summary_instructions.py](tests/cli/commands/test_summary_instructions.py)
      (has the `--restore`/`--key` test classes and the `_write_summary`
      helper; use this one) — add a new test class for `_sibling_projects`.
- [x] Cases: (a) parent directory contains sibling checkouts —
      returns their names, excludes `project` itself; (b) parent directory
      has no siblings — returns an empty set; (c) `iterdir()` raising
      `OSError` (monkeypatch `Path.iterdir` to raise) — returns an empty set
      and does not propagate the exception. For case (c), also assert a
      WARNING-level log record was emitted (use `caplog` at `WARNING` level)
      — this is the project's observable-failure-mode requirement, not
      optional per `.claude/rules/review-code.md` Failure-Mode Enumeration.
- [x] Success: `uv run pytest tests/cli/commands/test_summary_instructions.py -q`
      passes, including all three new cases.

### Task 2.4 — Test the end-to-end default-exclusion behavior

- [x] Effort: 3/5
- [x] In the same test file, add a new test class (or extend
      `TestRestoreKey`'s sibling class) exercising `_handle_restore` through
      the CLI (`runner.invoke`), following the existing pattern of patching
      `gather_cf_params` and `_SUMMARIES_DIR`, plus now also needing a real
      sibling directory on disk since `_sibling_projects` reads
      `Path(cwd).resolve().parent`. Use `tmp_path` with a real parent/child
      layout: e.g. `tmp_path / "squadron"` (cwd) and
      `tmp_path / "squadron-pr"` (sibling), both real directories.
- [x] **Every new invocation must pass `--cwd <that tmp_path child>`.** The
      existing `TestRestoreFlag`/`TestRestoreKey` invocations omit `--cwd`,
      which defaults to `"."` — so without it `_sibling_projects` reads the
      real parent of the process CWD, not the `tmp_path` layout. On this dev
      machine that parent genuinely contains `squadron-pr`, so a test that
      forgets `--cwd` passes here for the wrong reason and fails on CI where
      no sibling exists. A test that only passes on the author's machine is
      false confidence of exactly the kind the project's parsing rules warn
      against.
- [x] Reproduce #103's exact motivating case: summaries directory has both
      `squadron-interactive.md` (older) and `squadron-pr-p5a.md` (newer,
      would win under today's `matches[0]` logic). Assert bare `--restore`
      (no `--key`) selects `squadron-interactive.md`, not the sibling file.
- [x] Assert `--key pr-p5a` still restores the excluded sibling file — the
      escape hatch from the design's disambiguation policy must work.
- [x] Assert the stderr picker listing shows the sibling file marked as
      excluded (matching the format decided in Task 2.2) while still showing
      it in the list.
- [x] Add a case where **all** matches are sibling-owned (current project has
      no summary of its own): default `--restore` must raise the
      "no summary files found" error rather than falling back to an excluded
      file.
- [x] Add the **reversed-roles regression case** for Task 2.2's
      prefix-continuation qualifier: `--cwd` pointing at
      `tmp_path / "squadron-pr"` with `tmp_path / "squadron"` as the sibling,
      `gather_cf_params` patched to return project `squadron-pr`, and two
      summaries `squadron-pr-interactive.md` / `squadron-pr-p5a.md`. Bare
      `--restore` must select the most recent of those two — **not** raise
      "no summary files found". Without the qualifier every stem starts with
      the shorter sibling's `squadron-` prefix, `clean` is empty, and this
      test fails; it is the direct guard against that regression.
- [x] Success: `uv run pytest tests/cli/commands/test_summary_instructions.py -q`
      passes, including all new end-to-end cases.

### Task 2.5 — Regression-check the unfiltered single/no-sibling paths

- [x] Effort: 2/5
- [x] **Add `--cwd` to the existing `TestRestoreFlag` and `TestRestoreKey`
      invocations** (including the `_run` helper at
      [tests/cli/commands/test_summary_instructions.py:158](tests/cli/commands/test_summary_instructions.py#L158)),
      pointing at a real `tmp_path` child directory. Today they omit `--cwd`,
      so it defaults to `"."` and `_sibling_projects` enumerates the real
      parent of whatever directory pytest runs in — making every one of these
      tests machine-dependent under this fix. This contradicts an earlier
      draft of this task that called them "unchanged"; the edit is small but
      required for determinism.
- [x] Do **not** assume `_sibling_projects` returns an empty set for these
      tests before that edit — it returns whatever really sits in the process
      CWD's parent, minus the patched project name. On a dev machine with a
      `squadron-pr` checkout that set is non-empty, so a failure here may be
      an environment collision rather than a logic bug.
- [x] Only after `--cwd` is wired through: if a pre-existing test still
      fails, the partitioning logic is over-broad — fix Task 2.2's
      implementation, not the test.
- [x] Success: `uv run pytest tests/cli/commands/test_summary_instructions.py -q`
      — every test in the file passes, old and new alike.

### Task 2.6 — Gate and commit Part B

- [x] Effort: 1/5
- [x] Run: `uv run ruff format --check`, `uv run ruff check`,
      `uv run pyright` (0 errors), `uv run pytest -q` (full suite).
- [x] Commit Part B alone: the helper, the partitioning/selection change, the
      stderr listing update, and all Part-B test changes together.
- [x] Commit message: `fix: scope summary --restore default to non-sibling matches (#103)`.
- [x] Success: all four gate commands pass; Fix 2 is live on its own commit.

---

## Final Verification

### Task 3.1 — Full-suite gate and manual smoke check

- [x] Effort: 1/5
- [x] Run the full gate once more on the combined state:
      `uv run ruff format --check`, `uv run ruff check`, `uv run pyright`,
      `uv run pytest -q`.
- [x] Manually smoke-test Fix 1: run
      `sq review code --files "**/*" --model definitely-not-a-real-alias`
      against a scratch/test repo and confirm it fails fast with the
      unknown-alias message rather than dispatching. **A scope argument
      (`--files`, `--diff`, or a slice number) is required**: without one the
      command exits 1 at the scope check
      ([review.py:1062](src/squadron/cli/commands/review.py#L1062)) before
      `_run_review_command` is ever reached, so the guard is unreachable.
      Both failures exit 1, so a non-zero exit alone does not verify the fix
      — read the message and confirm it is the unknown-alias one.
- [x] Manually smoke-test Fix 2 with the real command name
      `sq _summary-instructions --restore` — there is no `sq summary`
      command; both summary commands are registered hidden and
      `_`-prefixed ([app.py:64-65](src/squadron/cli/app.py#L64)), so the
      design's and issue's `sq summary` prose is a naming shorthand, not an
      invocation. Run it from the `squadron` checkout with a `squadron-pr`
      sibling present: this is #103's exact motivating case, and it currently
      selects `squadron-pr-*.md`. Confirm it now selects squadron's own most
      recent summary, that the stderr listing still shows the sibling file
      marked as excluded, and that `--key pr-interactive` still restores it.
- [x] Success: gate is fully green; both manual checks behave as designed,
      each verified by its message/selection rather than by exit code alone.

### Task 3.2 — Update slice and plan status, write DEVLOG

- [x] Effort: 1/5
- [x] Set `status: complete` in the slice design frontmatter
      (`921-slice.small-fixes-batch.md`) and in this task file's frontmatter.
- [x] Check off entry 19 in
      [900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md)
      and set its status line to complete with the date.
- [x] Close [issue #67](https://github.com/ecorkran/squadron/issues/67) and
      [issue #103](https://github.com/ecorkran/squadron/issues/103) with a
      comment citing the fixing commits.
- [x] Write the DEVLOG entry per `prompt.ai-project.system.md`, Session State
      Summary — note that #78 and #65-finding-1 were dropped from this
      slice's scope after being found already fixed during design, and that
      #65 remains open (findings 2-3 routed to slice 907).
- [x] Success: slice, plan, both issues, and DEVLOG all reflect the landed
      state.
