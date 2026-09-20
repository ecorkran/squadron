---
docType: tasks
slice: small-fixes-batch-2
project: squadron
lldReference: project-documents/user/slices/922-slice.small-fixes-batch-2.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Continuation of 922-tasks.small-fixes-batch-2-1.md. Covers Fix 1 (#65 findings 2-3, dependency cleanup) and slice closeout. Fix 1 is ordered last because it regenerates uv.lock.
status: not_started
dateCreated: 20260920
dateUpdated: 20260920
---

# Tasks: Small Fixes Batch 2 (part 2)

## Context Summary

Continuation of
[922-tasks.small-fixes-batch-2-1.md](project-documents/user/tasks/922-tasks.small-fixes-batch-2-1.md),
which carries the full slice context and Parts A–E (Fixes 2, 3, 4, 6, 5).
Read its Context Summary first — the two corrections it records (`mcp` is
still imported and stays; #100's policy belongs to slice 918 D3, not 917)
apply here too.

This file covers **Part F** (Fix 1 — declared dependencies, design decision
**D1**) and **Part G** (slice verification and closeout). Fix 1 is ordered
last in the slice because it regenerates `uv.lock` and is the item most
likely to conflict with anything else in flight.

**Prerequisite:** Parts A–E complete and committed, one commit per fix.

---

## Part F — Fix 1 (#65 findings 2–3): declared dependencies

Design decision **D1**. **Last**, because it regenerates `uv.lock`.

### F1. Correct `[project.dependencies]`

- [ ] Open `pyproject.toml`.
- [ ] **Remove** `anthropic` — zero importing files under `src/` (verified
      20260919).
- [ ] **Remove** `google-adk` — zero importing files; it pulls a large
      transitive tree into every install.
- [ ] **Keep** `mcp` — imported by `tools/mcp_bridge.py` and
      `tools/cf_tools.py`. #65's claim that it is unimported is stale.
- [ ] **Add** `rich` with a lower bound at the major version `uv.lock`
      already resolves (currently 14.3.2, arriving transitively via typer).
      21 files under `src/` import it.
- [ ] Before editing, re-run the import grep over `src/` to confirm the four
      counts still hold — the design's numbers are dated 20260919.
- **Effort:** 1
- **Success:** criterion 1 holds.

### F2. Delete the three stub packages

- [ ] Delete `src/squadron/providers/anthropic/` (`__init__.py`, `agent.py`,
      `provider.py`).
- [ ] Delete `src/squadron/adk/`.
- [ ] Delete `src/squadron/mcp/` — the real MCP code lives in `tools/`; the
      `mcp` *dependency* stays.
- [ ] Each file is three lines: a docstring and
      `from __future__ import annotations`. Confirm this before deleting —
      if any file has grown real code since 20260919, **stop** and raise it.
- [ ] Confirm nothing under `src/`, `tests/`, or `pyproject.toml` references
      `squadron.adk`, `squadron.providers.anthropic`, or `squadron.mcp`.
      Check `[tool.setuptools]` / packaging config for explicit package
      listings.
- **Effort:** 1
- **Success:** criterion 2 holds; no import of a deleted package remains.

### F3. Regenerate the lockfile

- [ ] Regenerate `uv.lock`.
- [ ] Confirm `rich` and `mcp` resolve; confirm `anthropic` and `google-adk`
      are gone from squadron's own requirement set.
- **Effort:** 1
- **Success:** the lockfile matches the corrected dependency set.

### F4. Test Fix 1

- [ ] Add the test to `tests/test_smoke.py` — package-level, where
      `test_package_importable` already lives. There is no packaging-specific
      test module and this slice does not create one.
- [ ] Assert the declared dependency set: `rich` and `mcp` present,
      `anthropic` and `google-adk` absent. Read the declared requirements via
      `importlib.metadata` (as `tests/cli/test_version.py:17` does for the
      version) rather than parsing `pyproject.toml` by hand.
- [ ] Confirm the full suite passes with the stub packages deleted — any
      collection error names an overlooked reference.
- **Effort:** 1
- **Success:** the dependency set is pinned by a test, not only by review.

### F5. Verify Fix 1 in a clean virtualenv

- [ ] Run the design's Verification Walkthrough for Fix 1:

  ```bash
  python -m venv "$TMPDIR/sq-922" && "$TMPDIR/sq-922/bin/pip" install -q -e .
  "$TMPDIR/sq-922/bin/pip" show google-adk anthropic     # expect: not found
  "$TMPDIR/sq-922/bin/pip" show rich mcp                 # expect: both installed
  "$TMPDIR/sq-922/bin/sq" doctor
  "$TMPDIR/sq-922/bin/sq" run --help
  "$TMPDIR/sq-922/bin/sq" review --help
  rm -rf "$TMPDIR/sq-922"
  ```

- [ ] If `pip show anthropic` finds it anyway, another installed package
      requires it transitively — confirm via `uv tree` that `squadron-ai` is
      not the requirer before concluding the removal failed.
- [ ] All three `sq` invocations must complete without `ImportError`
      (criterion 3).
- **Effort:** 2
- **Success:** criteria 1–3 hold against a real clean install.

### F6. CHANGELOG and commit

- [ ] Add a CHANGELOG entry: two dependencies dropped (`anthropic`,
      `google-adk`), `rich` now declared. Keep it a short user-facing bullet;
      technical detail belongs in the DEVLOG.
- [ ] This is a **user-visible install change** — the entry is required, not
      optional.
- [ ] Commit Fix 1 on its own.
- **Effort:** 1
- **Success:** the install change is discoverable from the CHANGELOG.

---

## Part G — Slice verification and closeout

### G1. Full gate

- [ ] `ruff format .`
- [ ] `ruff check .`
- [ ] `pyright` — **zero errors is a merge blocker**.
- [ ] `pytest` — full suite passes.
- **Effort:** 1
- **Success:** all four clean.

### G2. Walk the success criteria

Check each one against running code. Do not assume; do not batch. The wording
below is the design's — consult it for the full statement where one is
abbreviated.

- [ ] **1.** `[project.dependencies]` has `rich` and `mcp`, not `anthropic` or
      `google-adk`; `uv.lock` regenerated.
- [ ] **2.** `providers/anthropic/`, `adk/`, and `mcp/` no longer exist.
- [ ] **3.** A clean-venv base install runs `sq doctor`, `sq run --help`, and
      `sq review --help` without `ImportError`.
- [ ] **4.** Gate **passes** when every staged path is outside
      `project-documents/user/` and cf reports `filesChecked: 0`.
- [ ] **5.** Gate still **fails closed**, with the D10 message, when ≥1 staged
      path is under `project-documents/user/` and cf reports `filesChecked: 0`.
- [ ] **6.** Gate unchanged for `filesChecked > 0`, unreadable count, timeout,
      and missing `cf`.
- [ ] **7.** `SubprocessRunner.run` with a nonexistent `cwd` raises
      `ProcessCwdNotFoundError` naming the directory; missing executable with
      a valid or `None` `cwd` still raises `ProcessNotFoundError`.
- [ ] **8.** `GitHubCli` does not report "gh is not on PATH" for a nonexistent
      `cwd`, and logs at WARNING.
- [ ] **9.** No `"tool_use"` / `"tool_result"` literal in `translation.py`,
      `sdk_session.py`, `summary_oneshot.py`, `review_client.py`, or
      `metrology/audit.py`.
- [ ] **10.** `_ICON[StepKind.INSTALL]` differs from `_ICON[StepKind.CONFIGURE]`
      in both glyph and color, and is not red.
- [ ] **11.** A policy-exclusion refusal emits no record at INFO or above; a
      jail-escape refusal still emits exactly one WARNING.
- [ ] **Integration.** A release-shaped commit passes the installed pre-commit
      hook without `--no-verify`.
- **Effort:** 2
- **Success:** every criterion verified against running code.

### G3. Close the issues

- [ ] Close [#65](https://github.com/ecorkran/squadron/issues/65),
      [#117](https://github.com/ecorkran/squadron/issues/117),
      [#112](https://github.com/ecorkran/squadron/issues/112),
      [#108](https://github.com/ecorkran/squadron/issues/108),
      [#57](https://github.com/ecorkran/squadron/issues/57), and
      [#100](https://github.com/ecorkran/squadron/issues/100), each citing its
      fixing commit.
- [ ] On #65, note that `mcp` was **kept** and why — the issue text is stale.
- [ ] On #100, note that the policy belongs to slice **918 D3**, not 917.
- [ ] Leave [#118](https://github.com/ecorkran/squadron/issues/118) open — the
      `[serve]` extra is a Non-goal of this slice.
- **Effort:** 1
- **Success:** six issues closed with commit references; #118 untouched.

### G4. DEVLOG and slice closeout

- [ ] Write a DEVLOG entry per `prompt.ai-project.system.md`, section
      "Session State Summary".
- [ ] Mark the slice complete in
      [922-slice.small-fixes-batch-2.md](project-documents/user/slices/922-slice.small-fixes-batch-2.md)
      (`status`) and in
      [900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md)
      entry 20.
- [ ] Set `status: complete` in **both** task files —
      `922-tasks.small-fixes-batch-2-1.md` and this one.
- [ ] Confirm every checklist item in **both** files is checked — including
      any deliberately skipped, which are marked `[x]` with a note rather
      than left open.
- **Effort:** 1
- **Success:** slice records reflect completion; no orphaned open checkbox.
