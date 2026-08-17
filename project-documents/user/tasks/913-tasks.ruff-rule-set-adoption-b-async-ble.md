---
docType: tasks
slice: ruff-rule-set-adoption-b-async-ble
project: squadron
lldReference: project-documents/user/slices/913-slice.ruff-rule-set-adoption-b-async-ble.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
status: not_started
dateCreated: 20260815
dateUpdated: 20260815
---

# Tasks: Ruff Rule-Set Adoption — `B`, `ASYNC`, `BLE`

## Context Summary

Closes the first three steps of
[issue #50](https://github.com/ecorkran/squadron/issues/50). The Python guide
requires `select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`; the project
selects `["E", "F", "W", "I", "UP"]`
([pyproject.toml:80](pyproject.toml#L80)). Add the three missing sets and fix
what they report.

The point is not lint hygiene. `BLE` and `ASYNC` mechanically enforce two rules
the project otherwise states only in prose. Unenforced, they are aspirational —
which is how [issue #49](https://github.com/ecorkran/squadron/issues/49) landed.

Three parts, sequenced **A → B → C** per the design. Each part ends by adding
its rule to `select` in the same commit that zeroes it (design D7), so no part
leaves the build red and `git bisect` stays meaningful.

- **Part A** — `B` (71). A `per-file-ignores` entry for the Typer idiom, then 54
  `B904` and 3 stragglers. Mechanical, no behavior change.
- **Part B** — `ASYNC` (6). Blocking calls off the event loop, one on a
  production I/O path.
- **Part C** — `BLE` (23 in `src`). The substantive part: one judgment call per
  site.

### Verified counts (measured on `4a1737f`, 20260815)

These supersede the figures in issue #50 and the slice plan, which have drifted.

| Rule | Count | Concentration |
|---|---|---|
| `B904` | 54 | 53 in `cli/commands/`, 25 of those in `run.py`; 1 in `pipeline/emit.py` |
| `B008` | 14 | all in `cli/commands/` (7 files) |
| `B007`/`B017`/`B905` | 3 | `B905` in `src`, other two in `tests` |
| `ASYNC240` | 2 | `client/http.py:42` (production), `tests/pipeline/test_executor.py:966` |
| `ASYNC221` | 4 | all in `tests` |
| `BLE001` | 28 | 23 in `src`, 5 in `project-documents/user/reference/codebase-probe.py` |

### Verified code anchors

| Anchor | Location |
|---|---|
| `select` list and stale deferral comment | [pyproject.toml:74-80](pyproject.toml#L74-L80) |
| No `per-file-ignores` or `extend-exclude` block exists yet | [pyproject.toml:73](pyproject.toml#L73) |
| CI runs `ruff check` with **no path argument** | [.github/workflows/ci.yml:28](.github/workflows/ci.yml#L28) |
| `ASYNC240` — blocking `Path.exists()` in `async def` | [client/http.py:42](src/squadron/client/http.py#L42) |
| `BLE` — resolver failure → silent wrong-model fallback | [prompt_renderer.py:158](src/squadron/pipeline/prompt_renderer.py#L158) |
| `BLE` — any exception → `FAILED` StepResult, no traceback | [executor.py:1603](src/squadron/pipeline/executor.py#L1603) |

### Notes carried from the design

`ruff --fix` does **not** fix `B904` (verified). Every one of the 54 is
hand-touched regardless, so choosing `from exc` vs `from None` per site costs
nothing over choosing uniformly (D2).

Task 3.1's `per-file-ignores` glob was verified against the tree during design:
with it applied, `BLE` drops from 28 to exactly the 23 `src` sites and
`ruff check --select E,F,W,I,UP project-documents/` still passes.

---

## Part A — `B`

### Task 1.1 — Add the `B008` `per-file-ignores` entry

- [ ] Effort: 1/5
- [ ] In [pyproject.toml](pyproject.toml), add a `[tool.ruff.lint.per-file-ignores]`
      section (none exists yet) with one entry:
      `"src/squadron/cli/commands/*.py" = ["B008"]`.
- [ ] Do **not** add `B008` to a global `ignore` list, and do **not** rewrite the
      14 `typer.Option`/`typer.Argument` defaults — they are the framework idiom,
      not debt (design D1).
- [ ] Do not enable `B` in `select` yet; that happens in Task 1.5.
- [ ] Success: `uv run ruff check --select B008 --output-format=concise .`
      reports no `B008` under `src/squadron/cli/commands/`.

### Task 1.2 — Verify the ignore did not disable `B` for the CLI

- [ ] Effort: 1/5
- [ ] Temporarily add a function with a genuine mutable default to any
      `src/squadron/cli/commands/*.py` — e.g.
      `def _probe(x: list[str] = []) -> None: ...`
- [ ] Run `uv run ruff check --select B src/squadron/cli/commands/` and confirm it
      reports `B006`. If it reports nothing, the ignore is too broad — fix it
      before continuing.
- [ ] Remove the probe function. Confirm `git status` shows no change to the file.
- [ ] Success: `B006` fired while `B008` stayed silent, and the probe is reverted.

### Task 1.3 — Fix the 54 `B904` sites

- [ ] Effort: 2/5
- [ ] Work file by file, largest first, so the diff is reviewable:
      `run.py` (25), `skills.py` (4), `dispatch_run.py` (4), `summary_run.py` (3),
      `spawn.py` (3), `shutdown.py` (3), `task.py` (2), `setup.py` (2),
      `message.py` (2), then the six single-site files
      (`summary_instructions.py`, `review.py`, `models.py`, `list.py`,
      `history.py`, and `pipeline/emit.py`).
- [ ] Per site, choose deliberately (design D2):
      **`from exc`** by default — preserves the cause chain;
      **`from None`** only where the CLI has already rendered the error for the
      user and a chained traceback would be noise on a deliberate exit.
- [ ] Do not run `ruff --fix` expecting it to handle these; it reports no fixes
      available for `B904`.
- [ ] Do not change control flow, exception types, or messages — this task is
      chaining only.
- [ ] **Do not commit here.** Part A lands as one commit at Task 1.5.
      Intermediate `git add` is fine; a commit before `select` gains `B` would
      leave a commit in history with the fixes but not the rule, which is the
      inverse of what D7 requires. The same applies to Tasks 1.1, 1.2, and 1.4.
- [ ] Success: `uv run ruff check --select B904 --output-format=concise .` →
      `All checks passed!`

### Task 1.4 — Fix the three stragglers

- [ ] Effort: 1/5
- [ ] `B905` at [actions/summary.py:273](src/squadron/pipeline/actions/summary.py#L273)
      — add an explicit `strict=` to the `zip()` call. Choose the value that
      matches the existing behavior; if the two sequences are guaranteed
      equal-length, `strict=True` documents that.
- [ ] `B007` at `tests/pipeline/test_state.py:810` — unused loop control variable
      `i`; rename to `_` (or `_i`).
- [ ] `B017` at `tests/skills/test_models.py:102` — `pytest.raises(Exception)` is
      too broad. Narrow it to the exception the code under test actually raises.
      If that assertion was masking a mismatch, fix the test to assert the real
      type rather than widening it back.
- [ ] Success: `uv run ruff check --select B007,B017,B905 --output-format=concise .`
      → `All checks passed!`

### Task 1.5 — Enable `B` and gate Part A

- [ ] Effort: 1/5
- [ ] Add `"B"` to `select` in [pyproject.toml:80](pyproject.toml#L80).
- [ ] Run the full per-part gate:
      `uv run ruff check` (no path arg — matches CI),
      `uv run ruff format --check`,
      `uv run pyright` (0 errors),
      `uv run pytest -q` (baseline: 3016 passed, 2 skipped).
- [ ] Commit Part A alone. The commit must contain the `select` change and the
      fixes together, so no commit in history has `B` enabled and failing (D7).
- [ ] Success: all four commands pass; `B` is live.

---

## Part B — `ASYNC`

### Task 2.1 — Move the blocking `Path.exists()` off the event loop

- [ ] Effort: 1/5
- [ ] In [client/http.py:42](src/squadron/client/http.py#L42), `Path(self._socket_path).exists()`
      runs inside `async def _get_client` — a blocking `stat(2)` on the daemon
      client's I/O path.
- [ ] Wrap it with stdlib `asyncio.to_thread`, e.g.
      `if await asyncio.to_thread(Path(self._socket_path).exists):`
- [ ] Do **not** introduce `anyio.Path` or `trio.Path` as the rule message
      suggests — the project is asyncio-native and adding a dependency to satisfy
      a lint message is the wrong trade (design D4).
- [ ] Add the `asyncio` import if not already present.
- [ ] Preserve behavior exactly: the Unix-socket branch is still taken when the
      socket exists, the base-URL branch otherwise.
- [ ] Success: `uv run ruff check --select ASYNC240 src/` → `All checks passed!`

### Task 2.2 — Test the socket-detection branches still select correctly

- [ ] Effort: 1/5
- [ ] Confirm `tests/client` covers both `_get_client` branches — socket present
      (Unix transport) and socket absent (base URL). If either is uncovered, add
      the missing case.
- [ ] The assertion is on which transport/base URL the returned client carries,
      not on the `to_thread` call itself — the change must be invisible to callers.
- [ ] Success: `uv run pytest tests/client -q` passes.

### Task 2.3 — Fix the four `ASYNC221` sites in tests

- [ ] Effort: 1/5
- [ ] Sites: `tests/metrology/test_audit_harness.py:465` and `:466`,
      `tests/pipeline/actions/test_commit.py:132` and `:150` — blocking
      `subprocess.run` (git commands) inside `async def` tests.
- [ ] Wrap each in `asyncio.to_thread`, consistent with Task 2.1.
- [ ] Do **not** add a `per-file-ignores` exemption for `tests/`. These tests are
      what future tests get copied from, and a blanket `ASYNC` exemption would
      license the next `ASYNC240` in a test that *is* exercising loop behavior
      (design D5).
- [ ] Success: `uv run ruff check --select ASYNC221 --output-format=concise .` →
      `All checks passed!`

### Task 2.4 — Fix the `ASYNC240` site in tests

- [ ] Effort: 1/5
- [ ] `tests/pipeline/test_executor.py:966` — blocking pathlib call in an
      `async def`. Same treatment as Task 2.1.
- [ ] Success: `uv run ruff check --select ASYNC --output-format=concise .` →
      `All checks passed!`

### Task 2.5 — Enable `ASYNC` and gate Part B

- [ ] Effort: 1/5
- [ ] Add `"ASYNC"` to `select` in `pyproject.toml`.
- [ ] Run the full per-part gate (same four commands as Task 1.5).
- [ ] Additionally run `sq doctor`, which exercises the http client path
      end-to-end, and confirm it behaves as before the change.
- [ ] Commit Part B alone.
- [ ] Success: all gate commands pass; `ASYNC` is live.

---

## Part C — `BLE`

The substantive part. Each site gets exactly one of three outcomes (design D6);
**"leave it broad without comment" is not among them**:

1. **Narrow** the caught type to what can actually be raised. Preferred.
2. **Keep broad**, add `logger.exception` + `# noqa: BLE001` with a comment
   naming why the boundary must not let anything escape.
3. **Fix a real bug** where the catch swallows something that should propagate.

**Scope guard:** if a site turns out to be a genuine bug of more than trivial
size, file an issue and leave a `# noqa: BLE001` referencing it. Do not absorb an
arbitrary behavior change into this slice under a lint banner (D6).

For every narrowing, answer explicitly: *what now escapes that did not before,
and where does it land?* A site whose answer is "an unhandled traceback to the
user" is not done — it needs a handler or outcome 2.

### Task 3.1 — Exempt the documents tree from `BLE001` only

- [ ] Effort: 1/5
- [ ] The 5 sites in `project-documents/user/reference/codebase-probe.py` are a
      tracked one-off analysis script — not in `src/`, not packaged, not imported.
      CI lints it because `ruff check` runs with no path argument.
- [ ] Add to the existing `[tool.ruff.lint.per-file-ignores]` block (created in
      Task 1.1): `"project-documents/**/*.py" = ["BLE001"]`
- [ ] Do **not** use `extend-exclude` for the tree. That was the design's original
      form and was narrowed after review finding F009: excluding the directory
      also discards `E`/`F`/`W`/`I`/`UP` on a file that passes them today
      (design D3).
- [ ] Success: `uv run ruff check --select E,F,W,I,UP project-documents/` →
      `All checks passed!`, and `grep -n 'extend-exclude' pyproject.toml` finds
      nothing.

### Task 3.2 — Resolve the two flagged high-value sites

- [ ] Effort: 2/5
- [ ] **[prompt_renderer.py:158](src/squadron/pipeline/prompt_renderer.py#L158)** —
      `except Exception` around `resolver.resolve(action_model)`, falling back to
      `model_id = action_model, profile = None`, which then feeds
      `is_sdk_profile(profile)`. A resolver failure is silently reinterpreted as
      "the alias is a literal model id with no profile", degrading an
      unresolvable model into a wrong-but-plausible dispatch. This is issue #49's
      shape structurally. It needs a real answer, not a `noqa` — determine what
      `resolve` actually raises for an unknown alias and decide whether that
      should propagate.
- [ ] **[executor.py:1603](src/squadron/pipeline/executor.py#L1603)** — broad catch
      around branch-model resolution converting *any* exception into a `FAILED`
      StepResult carrying `str(exc)`. Likely outcome 2 (it is a step boundary),
      but it currently has no `logger.exception`, so a programming error inside
      the `try` reaches the user as a step failure with a bare message and no
      traceback. At minimum add the logging; narrow the type if the raisable set
      is knowable.
- [ ] **Concrete scope-guard trigger.** Start by reading `resolver.resolve` and
      listing what it raises for an unknown alias. Stop, file an issue, and take
      outcome 2 (`noqa` referencing the issue) if any of these hold:
      the fix requires editing a file outside `prompt_renderer.py` /
      `executor.py`; it requires changing a function signature or return type; or
      the raisable set is not determinable by reading the resolver and its direct
      callees. Otherwise proceed with outcome 1 or 3.
- [ ] The guard is a stopping rule, not a failure — a filed issue with a
      justified `noqa` is a complete, passing outcome for this task.
- [ ] Success: both sites resolved to outcome 1, 2, or 3 with the reasoning
      recorded in the code comment or the filed issue.

### Task 3.3 — Test the behavior change at the two flagged sites

- [ ] Effort: 2/5
- [ ] For `prompt_renderer.py`: add a test covering an unresolvable model alias,
      asserting the new behavior (error propagates, or the fallback is taken
      deliberately with the reason visible) rather than the old silent
      reinterpretation.
- [ ] For `executor.py`: add or extend a test asserting that a resolution failure
      still produces a `FAILED` StepResult **and** that the failure is logged —
      the observable-failure requirement from the project's review rules.
- [ ] These are the only two `BLE` sites expected to need new tests; the rest are
      narrowings covered by the existing suite.
- [ ] Success: new tests pass and fail against the pre-fix behavior.

### Task 3.4 — Resolve the remaining `pipeline/` sites

- [ ] Effort: 2/5
- [ ] Sites: `prompt_renderer.py` (2 remaining — `:211`, `:309`), `state.py`
      (`:435`, `:485`), `sdk_session.py` (`:108`), `loader.py` (`:141`),
      `emit.py` (`:157`), `actions/cf_op.py` (`:107`), `actions/review.py`
      (`:283`), `actions/summary.py` (`:254`).
- [ ] `cf_op.py` is the module named in issue #49 — read that issue before
      touching it, and confirm the remaining catch there is not a second instance
      of the same defect.
- [ ] Apply the three-outcome rule per site.
- [ ] Success: `uv run ruff check --select BLE src/squadron/pipeline/` →
      `All checks passed!`

### Task 3.5 — Resolve the CLI, provider, client, core, and events sites

- [ ] Effort: 2/5
- [ ] Sites: `cli/commands/dispatch_run.py` (`:63`, `:79`),
      `cli/commands/doctor_checks.py` (`:70`), `cli/commands/spawn.py` (`:101`),
      `cli/commands/summary_run.py` (`:67`), `client/http.py` (`:74`),
      `core/agent_registry.py` (`:147`), `events/builtin/revision_stamp.py`
      (`:50`), `providers/codex/agent.py` (`:82`), `providers/sdk/agent.py`
      (`:247`).
- [ ] CLI top-level command bodies and provider subprocess seams are the most
      likely legitimate outcome-2 sites — a CLI command that must render an error
      rather than traceback is a documented process boundary. They still need the
      comment and the `logger.exception`.
- [ ] `client/http.py:74` catches around `resp.json()` when building an error
      detail — a narrow candidate (JSON decode errors), not a boundary.
- [ ] Success: `uv run ruff check --select BLE src/` → `All checks passed!`

### Task 3.6 — Audit every narrowing and every retained `noqa` before enabling

- [ ] Effort: 2/5
- [ ] **Per-site narrowing audit.** For every site resolved as outcome 1
      (narrowed) in Tasks 3.4 and 3.5, record a one-line answer to the migration
      plan's question: *what now escapes that did not before, and where does it
      land?* A site whose answer is "an unhandled traceback to the user" is not
      done — it needs a handler or outcome 2.
- [ ] For each narrowed site, name the existing test that exercises its failure
      path. If none exists, either add one or state why the escaping exception is
      unreachable in practice. Do not rely on "the suite passes" alone — a
      narrowing that changes an untested path passes the suite by construction.
- [ ] Run `grep -rn -B3 'noqa: BLE001' src/` and read every hit.
- [ ] Each must have: a comment naming why the boundary must not let anything
      escape, and a `logger.exception` nearby — or an explicit documented reason
      it must be silent.
- [ ] A `noqa` without justification is a failed success criterion, not a passing
      one with a note. Fix or narrow it.
- [ ] Any site deferred under the scope guard must reference its filed issue in
      the comment.
- [ ] Success: the retained count is small and every one is justified.

### Task 3.7 — Enable `BLE`, remove the stale comment, and gate Part C

- [ ] Effort: 1/5
- [ ] Add `"BLE"` to `select`. The final list must read exactly
      `["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`, matching the guide's
      baseline.
- [ ] Delete the deferral comment at
      [pyproject.toml:74-79](pyproject.toml#L74-L79) — it stops being true here.
- [ ] Run the full per-part gate (same four commands as Task 1.5).
- [ ] Commit Part C.
- [ ] Success: all gate commands pass; `BLE` is live.

---

## Final Verification

### Task 4.1 — Confirm the rules are load-bearing

- [ ] Effort: 1/5
- [ ] This is the acceptance test for the slice: reintroduce issue #49's shape and
      confirm CI would now catch it.
- [ ] Temporarily add `try: pass` / `except Exception: pass` to any
      `src/squadron/pipeline/*.py` file.
- [ ] Run `uv run ruff check` and confirm it **fails** with `BLE001`.
- [ ] Revert. Confirm `git status` is clean.
- [ ] Success: the failure mode that produced #49 is now caught mechanically
      rather than by review.

### Task 4.2 — Confirm the suppression inventory

- [ ] Effort: 1/5
- [ ] `grep -n 'select = ' pyproject.toml` → the guide's baseline, verbatim.
- [ ] `grep -A4 'per-file-ignores' pyproject.toml` → exactly two entries: `B008`
      for `src/squadron/cli/commands/*.py`, and `BLE001` for
      `project-documents/**/*.py`. No others.
- [ ] `grep -n 'extend-exclude' pyproject.toml` → no match.
- [ ] No blanket `per-file-ignores` for `BLE` or `ASYNC` anywhere in `src/` or
      `tests/`.
- [ ] Success: the only suppressions present are the two config entries and the
      justified per-site `noqa` comments.

### Task 4.3 — Update slice and plan status

- [ ] Effort: 1/5
- [ ] Set `status: complete` in the slice design frontmatter
      (`913-slice.ruff-rule-set-adoption-b-async-ble.md`) and in this task file.
      The gate accepts `complete`, `in_progress`, `not_started`, `deprecated`,
      `deferred` — hyphenated forms fail.
- [ ] Check off entry 11 in
      [900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md)
      and set its `**Status:**` line to complete with the date.
- [ ] Update [issue #50](https://github.com/ecorkran/squadron/issues/50) — steps
      1–3 done, step 4 (pyright over tests) remains as slice 914.
- [ ] Write the DEVLOG entry per `prompt.ai-project.system.md`, Session State
      Summary. Record any `BLE` site that turned out to be a real bug, and any
      issue filed under the scope guard.
- [ ] Success: slice, plan, issue, and DEVLOG all reflect the landed state.
