---
docType: tasks
slice: sq-setup-one-call-install-orchestrator
project: squadron
lld: user/slices/908-slice.sq-setup-one-call-install-orchestrator.md
dependencies: [905, 906]
projectState: 0.6.x. Branch 908-sq-setup-one-call-install-orchestrator already created from main.
dateCreated: 20260519
dateUpdated: 20260520
status: complete
---

## Context Summary

- New `sq setup` Typer command at `src/squadron/cli/commands/setup.py`: a *renderer* over slice 905's `run_all_checks()`. No new check logic.
- Pure conversion layer at `src/squadron/cli/commands/setup_steps.py`: maps each `CheckResult` to a `SetupStep` (kind = `ALREADY_DONE` / `INSTALL` / `CONFIGURE` / `OPTIONAL`).
- Three modes: interactive (default; one prompt per missing step with enter/s/q); `--non-interactive` / `-y` (emit all steps without prompts); `--check-only` (one-line summary per step, exits with `sq doctor`'s code).
- Optional flags: `--profile <name>` (filter Provider-section steps to one profile); `--verbose` / `-v` (include `OPTIONAL` warn-level steps in interactive mode).
- Per-step re-check via a local "check-name → function" map inside `setup_steps.py`. Unknown names degrade to "press enter when done" (no crash if 905 adds checks).
- Companion `scripts/install.sh` (bash): handles only the pre-Squadron bootstrap (pipx/uv → `pipx install squadron-ai` → `npm i -g @manta-digital/context-forge` → handoff to `sq setup`).
- Distribution via GitHub raw URL: `curl -sSL <raw URL> | sh`.
- No automatic shell execution from Python beyond `sq install-commands` (already in-process, explicit consent).
- Exit codes: 0 (all required OK), 1 (`sq doctor` reports missing), 2 (user-aborted via `q`), 3 (internal error during checks), 64 (usage error, e.g. unknown `--profile`).
- Failure-mode discipline: every I/O catch logs at WARNING+ via `logger.exception`. No bare/broad excepts.
- Effort: 2/5. Risk: Low.

---

## Tasks

### Phase A — Setup and data model

- [x] **T1. Confirm branch and create skeleton files**
  - [x] Confirm `git branch --show-current` is `908-sq-setup-one-call-install-orchestrator`. If not, branch from `main`.
  - [x] Create empty files: `src/squadron/cli/commands/setup.py`, `src/squadron/cli/commands/setup_steps.py`, `tests/cli/test_setup.py`, `tests/cli/test_setup_steps.py`, `scripts/install.sh`.
  - [x] Confirm `tests/cli/` already exists (it does, from slice 905).
  - [x] Success: `git status` shows the five new files; existing test suite still green.

- [x] **T2. Define `StepKind` and `SetupStep` in `setup_steps.py`**
  - [x] Add `StepKind(StrEnum)` with values `ALREADY_DONE = "already-done"`, `INSTALL = "install"`, `CONFIGURE = "configure"`, `OPTIONAL = "optional"`.
  - [x] Add `@dataclass(frozen=True)` `SetupStep` with fields: `title: str`, `kind: StepKind`, `section: str`, `detail: str`, `command: str | None = None`, `explanation: str | None = None`, `docs_anchor: str | None = None`, `recheck: Callable[[], CheckResult] | None = None`, `check_name: str = ""`.
  - [x] `recheck` and `check_name` are populated by `build_steps`; `check_name` mirrors the source `CheckResult.name` (used for filtering and tests).
  - [x] Add module logger.
  - [x] Success: `python -c "from squadron.cli.commands.setup_steps import SetupStep, StepKind"` works; pyright clean.

- [x] **T3. Test `StepKind` and `SetupStep`**
  - [x] File: `tests/cli/test_setup_steps.py`.
  - [x] Tests: `StepKind.INSTALL == "install"` (StrEnum string equality); `SetupStep` is hashable (frozen); defaults for `command`, `explanation`, `docs_anchor`, `recheck` are `None`; `check_name` defaults to `""`.
  - [x] Success: `uv run pytest tests/cli/test_setup_steps.py -q` passes 3 tests.

### Phase B — `build_steps` conversion layer (pure)

- [x] **T4. Add the check-name → recheck-function map**
  - [x] In `setup_steps.py`, add a module-level constant `_RECHECK_MAP: dict[str, Callable[[], CheckResult]]` that points each known `CheckResult.name` to the appropriate function in `doctor_checks.py`.
  - [x] For per-profile rows (whose names are dynamic from `get_all_profiles()`), do not pre-populate the map; `build_steps` will synthesise a recheck lambda using `check_provider_profiles()` filtered by name.
  - [x] Keys to include from slice 905 (current `doctor_checks.py`): `"squadron"`, `"slash commands"`, `"context-forge"`, `"codex CLI"`, `"Claude Code session"`, `"at least one provider OK"`, `"providers.toml"`, `"models.toml"`, `"project .env"`.
  - [x] Imports of `doctor_checks` functions should happen at module top (no deferred imports — they are sibling modules).
  - [x] Success: `python -c "from squadron.cli.commands.setup_steps import _RECHECK_MAP; assert 'squadron' in _RECHECK_MAP"` works.

- [x] **T5. Implement `_classify(result: CheckResult) -> StepKind`**
  - [x] Pure function. Rules:
    - [x] `result.status == OK` → `ALREADY_DONE`.
    - [x] `result.status == WARN` → `OPTIONAL`.
    - [x] `result.status == MISSING` and `result.section in {SECTION_INSTALL, SECTION_INTEGRATIONS}` → `INSTALL`.
    - [x] `result.status == MISSING` otherwise → `CONFIGURE`.
  - [x] Import the section constants from `doctor_checks`. No string literals duplicated.

- [x] **T6. Test `_classify`**
  - [x] Parametrised pytest covering all six classification branches (OK/WARN/MISSING × Install/Integrations vs Providers/Configuration).
  - [x] Success: `uv run pytest tests/cli/test_setup_steps.py -q -k classify` passes.

- [x] **T7. Implement `build_steps(results: list[CheckResult], profile: str | None = None) -> list[SetupStep]`**
  - [x] For each `CheckResult` in `results`:
    - [x] 1. Compute `kind = _classify(result)`.
    - [x] 2. Lookup `recheck = _RECHECK_MAP.get(result.name)`; if absent and the result is in the Providers section (per-profile row), synthesise a lambda that re-runs `check_provider_profiles()` and returns the matching row by name (fallback to a synthetic WARN if the profile disappears).
    - [x] 3. Build the `SetupStep`: `title` is the human-readable label, `command` is `result.fix_hint`, `detail` is `result.detail`, `docs_anchor` is computed from `result.name` via a small mapping (see T8), `explanation` is left `None` for now (populated in T9).
  - [x] If `profile is not None`:
    - [x] Validate that `profile` matches one of `get_all_profiles()`; raise `ValueError` if not. (Caller in `setup.py` converts this to `typer.Exit(64)`.)
    - [x] In the Providers section, keep only the row whose `name == profile` plus the aggregate `"at least one provider OK"` row. Drop all other per-profile rows.
  - [x] Preserve the source ordering of `results` for non-Providers sections; sort Providers-section rows alphabetically (matching slice 905's existing behavior).
  - [x] **Deferred per slice design:** do not implement the "aggregate 'at least one provider OK' suppresses individual provider OPTIONAL rows" optimisation. The initial release shows all profile rows; suppression is a follow-up slice. If you find yourself adding that logic, stop and re-read the slice design's "Mapping table" notes.
  - [x] Return the list.

- [x] **T8. Add the docs-anchor mapping**
  - [x] In `setup_steps.py`, add `_DOCS_ANCHOR: dict[str, str]` mapping known check names to QUICKSTART anchors. Slice 906's design lists the canonical mapping; reproduce verbatim here.
  - [x] Entries: `"slash commands" → "docs/QUICKSTART.md#step-3-install-slash-commands"`, `"context-forge" → "docs/QUICKSTART.md#step-1-install-context-forge"`, `"codex CLI" → "docs/QUICKSTART.md#step-4-codex"`, per-profile anchors keyed by profile name (e.g. `"openai" → "docs/QUICKSTART.md#step-4-openai"`).
  - [x] Unknown names → `None` (degrade gracefully if QUICKSTART hasn't shipped yet).

- [x] **T9. Add the explanation strings**
  - [x] In `setup_steps.py`, add `_EXPLANATION: dict[str, str]` providing 1–2 sentence "why this step" text for each known check.
  - [x] Example: `"context-forge" → "Squadron uses Context Forge (the cf CLI) to drive pipeline runs. Without it, sq run cannot dispatch slices."`
  - [x] Unknown names → `None`. Explanation is only rendered with `--verbose` in interactive mode.

- [x] **T10. Test `build_steps` — happy paths**
  - [x] File: `tests/cli/test_setup_steps.py`.
  - [x] Test 1 (all-OK): synthetic `list[CheckResult]` with every row OK → every step kind is `ALREADY_DONE`.
  - [x] Test 2 (all-missing-install): synthetic Install-section MISSING row → step kind `INSTALL`, `command` matches `fix_hint`.
  - [x] Test 3 (all-missing-config): synthetic Configuration-section MISSING row → step kind `CONFIGURE`.
  - [x] Test 4 (warn): WARN row → step kind `OPTIONAL`.
  - [x] Success: all four pass.

- [x] **T11. Test `build_steps` — `--profile` filter**
  - [x] Synthetic results with three Providers rows (`openai`, `openrouter`, `gemini`) plus the aggregate row.
  - [x] Call `build_steps(results, profile="openai")` — expect Providers section to contain exactly `openai` + aggregate; other rows dropped.
  - [x] Call `build_steps(results, profile="nonexistent")` — expect `ValueError` (or whatever exception T7 chose; document precisely in the test).

- [x] **T12. Test `build_steps` — recheck attachment and degradation**
  - [x] Test 1: synthetic result with `name == "context-forge"` — built step has `recheck is not None` and calling it returns a `CheckResult` (use real `check_context_forge` against tmp env).
  - [x] Test 2: synthetic result with `name == "future-unknown-check"` — built step has `recheck is None` (graceful degradation).
  - [x] Test 3: synthetic per-profile result with `name == "openai"` — built step has `recheck is not None` (synthesised lambda over `check_provider_profiles`).

### Phase C — `setup.py` Typer command and rendering

- [x] **T13. Implement the Typer command skeleton**
  - [x] In `setup.py`: define `def setup(...)` with parameters `non_interactive: bool = typer.Option(False, "--non-interactive", "-y")`, `check_only: bool = typer.Option(False, "--check-only")`, `profile: str | None = typer.Option(None, "--profile")`, `verbose: bool = typer.Option(False, "--verbose", "-v")`.
  - [x] Function body: call `run_all_checks()` (slice 905), then `build_steps(results, profile)`. Catch `ValueError` from `build_steps` (unknown profile) → print available profiles, `raise typer.Exit(64)`.
  - [x] Top-level try/except `Exception` around `run_all_checks()` → `logger.exception`, print "sq setup: internal error during checks; try `sq doctor` directly", `raise typer.Exit(3)`. This is a documented process-boundary catch.
  - [x] Branch on flags to call `_render_check_only`, `_render_non_interactive`, or `_run_interactive` (defined in following tasks).
  - [x] Final exit code: 0 if no `MISSING` rows remain after the run; 1 otherwise. (User-quit case overrides to 2 inside `_run_interactive`.)

- [x] **T14. Implement `_render_check_only(steps: list[SetupStep])`**
  - [x] One line per step: `{icon} {title:<32} {detail}`. Icons: `ALREADY_DONE` → `✓` green; `INSTALL` / `CONFIGURE` → `✗` red; `OPTIONAL` → `!` yellow.
  - [x] No commands, no explanations, no prompts.
  - [x] Use Rich `Console` with `soft_wrap=True` (matches `doctor.py`).
  - [x] Return value: integer count of `INSTALL` + `CONFIGURE` steps (used by caller to compute exit code).

- [x] **T15. Implement `_render_non_interactive(steps: list[SetupStep], verbose: bool)`**
  - [x] For each step:
    - [x] Print a header line: `{n}/{total} — {title}` with icon and color per kind.
    - [x] Print `detail` on the next line, indented.
    - [x] If `step.command`: print a blank line and `  $ {command}`.
    - [x] If `verbose` and `step.explanation`: print the explanation block.
    - [x] If `step.docs_anchor`: print `  see: {docs_anchor}`.
    - [x] Blank line separator before next step.
  - [x] No prompts, no rechecks.
  - [x] Same return value as T14.

- [x] **T16. Implement `_run_interactive(steps: list[SetupStep], verbose: bool)`**
  - [x] Iterate over steps:
    - [x] If `step.kind == ALREADY_DONE`: print a one-line green confirmation, advance.
    - [x] If `step.kind == OPTIONAL` and not `verbose`: skip silently (consistent with `sq doctor` default).
    - [x] Else: render the step block (same shape as T15), then `typer.prompt("[Enter] when done, 's' to skip, 'q' to quit", default="", show_default=False)`.
      - [x] Empty → if `step.recheck` is not None, call it and inspect new status: if now OK, advance; if still missing, re-prompt. Cap re-prompts at 5 per step; after the 5th, print "still not detected — skipping" and advance.
      - [x] `s` → mark skipped (do not run recheck), advance.
      - [x] `q` → raise `typer.Exit(2)` immediately (caller does not override this).
  - [x] After the loop completes, re-run `run_all_checks()` once more to produce a final summary banner mirroring `sq doctor`'s tail line. This final run is *in addition to* the per-step rechecks above — do not replace per-step rechecks with this single end-of-loop call.
  - [x] Return the final missing count.

- [x] **T17. Register the command in `cli/app.py`**
  - [x] Add `from squadron.cli.commands.setup import setup` near other command imports.
  - [x] Add `app.command("setup")(setup)` next to `app.command("doctor")(doctor)`.
  - [x] Success: `uv run sq setup --help` prints help text including all four flags.

### Phase D — Tests for `setup.py`

- [x] **T18. Test `--check-only` mode**
  - [x] Use Typer's `CliRunner`.
  - [x] Sub-test 18a (mixed fixture): monkeypatch `run_all_checks` to return a synthetic `list[CheckResult]` (mix of OK / WARN / MISSING rows). Assert exit code 1 (MISSING present), output contains one line per step, no command blocks printed.
  - [x] Sub-test 18b (all-OK fixture, standalone — covers SC4): monkeypatch `run_all_checks` to return only OK rows. Assert exit code 0, no prompts, output is short (one line per step). Keep this as a separate `def test_` so it survives refactoring of 18a.

- [x] **T19. Test `--non-interactive` mode**
  - [x] Monkeypatch `run_all_checks` with the all-missing fixture.
  - [x] Assert output contains the expected `$ {command}` lines for the Install/Integrations rows.
  - [x] Assert exit code 1.

- [x] **T20. Test `--profile <name>` filter**
  - [x] Fixture: results include three provider rows + aggregate.
  - [x] Invoke `sq setup --profile openai --non-interactive`.
  - [x] Assert only the `openai` row and aggregate appear in the Providers section.
  - [x] Invoke `sq setup --profile nonexistent --non-interactive` → exit 64, output mentions available profiles.

- [x] **T21. Test `--verbose` reveals OPTIONAL steps**
  - [x] Fixture with one WARN row.
  - [x] Without `-v`: row absent from non-interactive output.
  - [x] With `-v`: row present.

- [x] **T22. Test interactive `q` exit**
  - [x] Use `CliRunner` with `input="q\n"`.
  - [x] Fixture has at least one MISSING row.
  - [x] Assert exit code 2.

- [x] **T23. Test interactive recheck loop**
  - [x] Fixture: one MISSING row with `name == "context-forge"`.
  - [x] Monkeypatch `check_context_forge` so the first call returns MISSING and the second returns OK.
  - [x] Use `CliRunner` with `input="\n\n"` (user presses enter twice).
  - [x] Assert the step is reported as resolved and exit code is 0 (or 1 if other rows remain — pick a fixture with only this one row to keep the assertion clean).

- [x] **T24. Test internal-error path**
  - [x] Monkeypatch `run_all_checks` to raise `RuntimeError("boom")`.
  - [x] Assert exit code 3, output mentions falling back to `sq doctor`.

### Phase E — `install.sh` bootstrap script

- [x] **T25. Author `scripts/install.sh`**
  - [x] Shebang `#!/usr/bin/env bash`. First line after: `set -euo pipefail`.
  - [x] Detection order:
    - [x] 1. `command -v sq` — if present, skip to step 5.
    - [x] 2. `command -v uv` — prefer `uv tool install squadron-ai`.
    - [x] 3. `command -v pipx` — fallback `pipx install squadron-ai`.
    - [x] 4. Otherwise: prompt the user with the two install URLs (uv: astral.sh; pipx: pypa.github.io). Exit 1 if the user declines.
    - [x] 5. `command -v cf` — if present, skip to step 6.
    - [x] 6. `command -v npm` — if present, prompt before running `npm i -g @manta-digital/context-forge`. If absent, print OS-specific install hints and exit 1.
    - [x] 7. `exec sq setup` — hand off to the Python orchestrator.
  - [x] Every install command is preceded by an explicit `read -p "Install X via Y? [y/N] "` prompt unless `--yes` was passed (parse `--yes` / `-y` at the top of the script).
  - [x] Header comment block documents what the script does, where it is canonically hosted, and how to read it before running.
  - [x] Success: `bash scripts/install.sh --help` (add a small help branch) prints a usage block; `shellcheck scripts/install.sh` reports zero issues (advisory — install via `brew install shellcheck` if missing).

- [x] **T26. Add an `install.sh` idempotency smoke test**
  - [x] Bash test at `tests/scripts/test_install_sh.sh` (create `tests/scripts/` if needed).
  - [x] The script:
    - [x] 1. Sets `HOME=$(mktemp -d)` and a controlled `PATH`.
    - [x] 2. Stubs `pipx`, `uv`, `npm`, `cf`, `sq` as no-op shell functions on `PATH` (write them to a tmp dir at the head of `PATH`).
    - [x] 3. Runs `bash scripts/install.sh --yes` once, captures state (which stubs were called via a log file).
    - [x] 4. Runs `bash scripts/install.sh --yes` again, captures state.
    - [x] 5. Asserts the second run did not re-invoke install-side stubs (idempotent path detection).
  - [x] Note on idempotency interpretation: this test verifies *invocation*-idempotency (the second run does not issue another `pipx install` / `npm i -g`). *State*-idempotency (the host system ends up the same regardless of how many times the underlying tools run) is delegated to the tools themselves — `pipx install` is a no-op on second run, `npm i -g` reinstalls but converges on the same package version. Do not attempt to verify state-idempotency in this test.
  - [x] Wire the test into `pytest` via a thin `tests/scripts/test_install_sh.py` that `subprocess.run`s the bash test and asserts exit code 0. This keeps the CI surface uniform.
  - [x] Success: `uv run pytest tests/scripts/test_install_sh.py -q` passes.

### Phase F — Documentation and integration

- [x] **T27. Update README pointer**
  - [x] Replace (or add) a "Fresh install (one liner)" callout near the existing Quickstart section pointing at `curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh`.
  - [x] Note that this command can be inspected first via `curl -sSL <url> -o install.sh; less install.sh; bash install.sh`.
  - [x] Do not duplicate QUICKSTART content; the README pointer is one paragraph.

- [x] **T28. Add a `sq setup` mention to QUICKSTART (if 906 has merged)**
  - [x] If `docs/QUICKSTART.md` exists, add a "Faster path: `sq setup`" callout under Step 5 (Verify) and Troubleshooting.
  - [x] If 906 has not yet merged, skip this task and add a TODO in the slice's DEVLOG entry for follow-up after 906.

### Phase G — Final gate

- [x] **T29. Full test gate**
  - [x] `uv run pytest tests/cli/test_setup.py tests/cli/test_setup_steps.py tests/scripts/test_install_sh.py -q`.
  - [x] `uv run pytest -q` — full suite, expect ≤ pre-existing 2 skipped, no regressions.
  - [x] `uv run ruff check && uv run ruff format --check && uv run pyright`.
  - [x] All must be clean before merge.

- [x] **T30. Verification walkthrough**
  - [x] Execute the six scenarios from the slice design's "Verification walkthrough" section against a fresh shell environment.
  - [x] Record actual output in the slice design's verification section (overwriting the draft text) and update `dateUpdated`.
  - [x] Confirm exit codes match the documented values for each scenario.

- [x] **T31. Update slice plan and slice design status on merge**
  - [x] On merge of the PR, change `status: not_started` → `status: complete` in `908-slice.sq-setup-one-call-install-orchestrator.md`.
  - [x] Update `dateUpdated` in both the slice design and this task file.
  - [x] In `900-slices.maintenance-and-refactoring.md`, flip entry 7 checkbox to `[x]` and add `**Status:** complete (20260...) · **Risk:** Low · **Effort:** 2/5 · **Dependencies:** [905, 906]` tail line matching the format of earlier entries.

- [x] **T32. DEVLOG entry**
  - [x] Append a Phase 6 completion entry to `project-documents/DEVLOG.md` summarising shipped behaviour, deviations from the design (if any), and the final commit hash.

---

## Notes for the implementer

- **Do not duplicate slice 905's checks.** Every check this slice consumes is already in `doctor_checks.py`. If a check needs to change behavior, that's a 905 follow-up, not work for this slice.
- **Anchor mapping is a contract.** When QUICKSTART (slice 906) renames a section, update `_DOCS_ANCHOR` in the same commit.
- **No automatic shell execution from Python.** The only sanctioned in-process call is `install_commands()` (the Typer body of `sq install-commands`), and only after the user has consented at an interactive prompt.
- **Re-prompt cap = 5.** Prevents infinite loops if a user pipes the wrong thing into stdin in scripted contexts; the user can still skip explicitly with `s`.
- **`q` exits 2, not 1.** Distinguishes "user aborted" from "doctor reports missing." This matters for scripted callers that want to retry vs surface the failure.
