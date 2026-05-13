---
docType: tasks
slice: sq-doctor-environment-diagnostic-command
project: squadron
lld: user/slices/905-slice.sq-doctor-environment-diagnostic-command.md
dependencies: []
projectState: 0.6.0 released. Branch will be 905-sq-doctor-environment-diagnostic-command from main.
dateCreated: 20260513
dateUpdated: 20260513
status: complete
---

## Context Summary

- New `sq doctor` Typer command: read-only environment diagnostic. Prints a Rich checklist (or JSON), exits 1 iff any required check is MISSING.
- Two new files: `cli/commands/doctor.py` (Typer + rendering) and `cli/commands/doctor_checks.py` (pure check functions returning `CheckResult` dataclass). One edit: register in `cli/app.py`.
- All inspection targets already exist — `get_all_profiles()`, `resolve_auth_strategy_for_profile()`, `providers_toml_path()`, `models_toml_path()`, `shutil.which`. No new code outside the doctor module.
- Status taxonomy: `OK` / `MISSING` / `WARN`. WARN hidden by default; revealed with `-v`. JSON output always includes all rows.
- Required-ness: only the package itself, at-least-one provider authenticated, and parseability of any *present* TOML config files are required. Provider-specific and integration-specific rows are WARN.
- No network calls. Auth correctness against the wire stays `sq auth login`'s job.
- Failure-mode discipline: every I/O catch logs at WARNING via `logger.exception`. No bare/broad excepts.
- Pairs with slice 906 (Quickstart). `fix_hint` strings are the contract 906 will reference verbatim.
- Effort: 2/5. Risk: Low.

---

## Tasks

### Phase A — Setup and data model

- [x] **T1. Create branch and skeleton files**
  - Branch: `git checkout -b 905-sq-doctor-environment-diagnostic-command` from `main`.
  - Create empty files: `src/squadron/cli/commands/doctor.py`, `src/squadron/cli/commands/doctor_checks.py`, `tests/cli/test_doctor.py`, `tests/cli/test_doctor_checks.py`.
  - Confirm `tests/cli/` already exists; if not, add `__init__.py`.
  - Success: `git status` shows the four new files; existing test suite still green (no regression from empty modules).

- [x] **T2. Define `CheckStatus` and `CheckResult` in `doctor_checks.py`**
  - Add `CheckStatus(StrEnum)` with values `OK = "ok"`, `MISSING = "missing"`, `WARN = "warn"`.
  - Add `@dataclass(frozen=True)` `CheckResult` with fields: `name: str`, `status: CheckStatus`, `detail: str`, `fix_hint: str | None = None`, `section: str = ""`, `required: bool = True`.
  - Add module-level constants for section names: `SECTION_INSTALL = "Install"`, `SECTION_PROVIDERS = "Providers and Auth"`, `SECTION_INTEGRATIONS = "Integrations"`, `SECTION_CONFIG = "Configuration"`.
  - Add module logger: `logger = logging.getLogger(__name__)`.
  - Success: `python -c "from squadron.cli.commands.doctor_checks import CheckResult, CheckStatus"` works; `pyright` clean on the new module.

- [x] **T3. Add unit tests for `CheckResult` and `CheckStatus`**
  - File: `tests/cli/test_doctor_checks.py`
  - Tests: `CheckStatus.OK == "ok"` (StrEnum string equality), `CheckResult` is hashable (frozen), `CheckResult` defaults to `required=True` and `fix_hint=None`.
  - Success: `uv run pytest tests/cli/test_doctor_checks.py -q` passes 3 tests.

### Phase B — Individual check functions (test-with-pattern)

Each check function is pure: no network, no spawning subprocesses. Each returns exactly one `CheckResult`. Each is tested immediately after implementation.

- [x] **T4. Implement `check_squadron_install()`**
  - In `doctor_checks.py`.
  - Use `importlib.metadata.version("squadron-ai")`. On `PackageNotFoundError`, fall back to detail `"(dev install)"` and the source path of the `squadron` module (via `importlib.resources.files("squadron")`). Status remains `OK` in both cases — `required=True` is for paste-into-issue ergonomics, not gating.
  - Catch `PackageNotFoundError` specifically; log at WARNING via `logger.exception` only on unexpected exceptions, not on the normal dev-install path.
  - Section: `SECTION_INSTALL`. Name: `"squadron"`. `required=True`.

- [x] **T5. Test `check_squadron_install()`**
  - Test 1 (installed): patch `importlib.metadata.version` to return `"0.6.0"`. Assert status `OK`, detail contains `"0.6.0"`.
  - Test 2 (dev install): patch `importlib.metadata.version` to raise `PackageNotFoundError`. Assert status `OK`, detail contains `"(dev install)"`.

- [x] **T6. Implement `check_slash_commands(target: Path | None = None)`**
  - Default target: `Path("~/.claude/commands/sq").expanduser()`.
  - If the directory exists and contains at least one `.md` file: `OK`, detail with file count.
  - Otherwise: `WARN`, detail `"not installed at {target}"`, fix `"sq install-commands"`.
  - Section: `SECTION_INSTALL`. Name: `"slash commands"`. `required=False`.
  - Accept the target as a parameter so tests can point at a tmp dir.

- [x] **T7. Test `check_slash_commands()`**
  - Test 1 (present): create tmp dir with one `.md` file → `OK`.
  - Test 2 (empty dir): tmp dir with no `.md` → `WARN`.
  - Test 3 (missing dir): tmp dir + `/nope` → `WARN`, fix hint mentions `sq install-commands`.

- [x] **T8. Implement `check_provider_profiles()`**
  - Returns `list[CheckResult]`, one per profile from `get_all_profiles()`.
  - For each profile, call `resolve_auth_strategy_for_profile(profile)`:
    - On `.is_valid() == True`: `OK`, detail = `strategy.active_source or ""`.
    - On `.is_valid() == False`: `WARN`, detail = `"no credential found"`, fix = `strategy.setup_hint`.
  - Wrap the per-profile body in `try/except Exception` (typed-narrow if a concrete exception class is identifiable from auth.py; broad otherwise with an inline justification comment). On exception: `logger.exception`, emit `WARN` row with detail `"internal error: <exception class>"` and no fix hint. This is a Squadron bug surfacing in doctor; better than a stack trace.
  - Section: `SECTION_PROVIDERS`. Name: profile name. `required=False`.
  - Sort the returned list by profile name for stable output.

- [x] **T9. Test `check_provider_profiles()`**
  - Use `monkeypatch.setenv` / `monkeypatch.delenv` to control env vars seen by the real auth strategies — do not mock `resolve_auth_strategy_for_profile` itself. The contract under test is the *integration* with the real auth registry.
  - Test 1 (none set): delete `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY` — every profile row is `WARN` (sdk profile remains `OK` because session strategy returns valid unconditionally).
  - Test 2 (one set): set `OPENAI_API_KEY=test` — `openai` row is `OK` with detail mentioning `OPENAI_API_KEY`.
  - Test 3 (stable order): results are sorted alphabetically by `name`.

- [x] **T10. Implement `check_at_least_one_provider(profile_results: list[CheckResult])`**
  - Pure function over the output of `check_provider_profiles()`.
  - Counts OK rows; if `>= 1`: `OK` with detail `"N of M profiles authenticated"`. If `== 0`: `MISSING` with detail `"no provider profile has usable credentials"`, fix `"see fix hints above, or run 'sq auth status' for details"`.
  - Section: `SECTION_PROVIDERS`. Name: `"at least one provider OK"`. `required=True`.

- [x] **T11. Test `check_at_least_one_provider()`**
  - Test 1: synthetic `list[CheckResult]` with no OK rows → `MISSING`.
  - Test 2: synthetic list with one OK row → `OK`, detail contains `"1 of"`.

- [x] **T12. Implement `check_context_forge()`**
  - Use `shutil.which("cf")`. If found: `OK`, detail `"cf at {path}"`.
  - If not found: `WARN`, detail `"not on PATH"`, fix `"npm i -g @manta-digital/context-forge"`.
  - Section: `SECTION_INTEGRATIONS`. Name: `"context-forge"`. `required=False`.
  - Do *not* invoke `cf --version` in the default path. Slice design defers that to a verbose-mode follow-up.

- [x] **T13. Test `check_context_forge()`**
  - Test 1 (present): `monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/cf")` → `OK`.
  - Test 2 (absent): `monkeypatch.setattr(shutil, "which", lambda _: None)` → `WARN`, fix hint contains `npm i -g`.

- [x] **T14. Implement `check_codex_cli()`**
  - Same shape as T12 but for `shutil.which("codex")`. Fix hint: `"npm i -g @openai/codex"`.
  - Section: `SECTION_INTEGRATIONS`. Name: `"codex CLI"`. `required=False`.

- [x] **T15. Test `check_codex_cli()`**
  - Test 1 (present): `shutil.which("codex")` returns a path → `OK`.
  - Test 2 (absent): returns None → `WARN` with `@openai/codex` in fix hint.

- [x] **T16. Implement `check_claude_code_session()`**
  - Detect Claude Code via env vars: `os.environ.get("CLAUDECODE") == "1"` OR any env var beginning with `"CLAUDE_CODE_"` is set (use `any(k.startswith("CLAUDE_CODE_") for k in os.environ)`).
  - If detected: `OK`, detail `"CLAUDECODE=1"` (or names the matched env var if `CLAUDECODE` wasn't set).
  - Otherwise: `WARN`, detail `"not running inside Claude Code"`, fix = None (this isn't fixable — it's a contextual signal).
  - Section: `SECTION_INTEGRATIONS`. Name: `"Claude Code session"`. `required=False`.

- [x] **T17. Test `check_claude_code_session()`**
  - Test 1: `monkeypatch.setenv("CLAUDECODE", "1")` → `OK`.
  - Test 2: `monkeypatch.delenv("CLAUDECODE", raising=False)` and clear `CLAUDE_CODE_*` keys → `WARN`, fix hint is None.

- [x] **T18. Implement `check_providers_toml()`**
  - Use `providers_toml_path()` from `squadron.providers.profiles`.
  - If file does not exist: `OK` (informational), detail `"not present at {path}"`. *Not* a warning — the file is optional.
  - If file exists: open and `tomllib.load`. Wrap in `try/except tomllib.TOMLDecodeError as exc`: `MISSING`, detail `"malformed: {exc}"`, fix `"repair or remove {path}"`. Any other exception: `logger.exception`, re-raise (process-boundary handler catches in T22).
  - On success: `OK`, detail `"loaded from {path}"`.
  - Section: `SECTION_CONFIG`. Name: `"providers.toml"`. `required=True` (parse failure is required-failing).

- [x] **T19. Test `check_providers_toml()`**
  - Test 1 (absent): `monkeypatch` `providers_toml_path` to return a non-existent path → `OK`, detail `"not present"`.
  - Test 2 (valid): write a minimal valid TOML to a tmp path, monkeypatch → `OK`, detail `"loaded from"`.
  - Test 3 (malformed): write `not = toml = "` to tmp path → `MISSING`, detail contains `malformed`, fix hint contains the path.

- [x] **T20. Implement `check_models_toml()`**
  - Mirror of T18 over `models_toml_path()` from `squadron.models.aliases`.
  - Section: `SECTION_CONFIG`. Name: `"models.toml"`. Same required-iff-present semantics.

- [x] **T21. Test `check_models_toml()`**
  - Mirror of T19 over `models_toml_path`.

- [x] **T22. Implement `check_project_env()`**
  - Look for `.env` in `Path.cwd()`. If present: `OK`, detail `"loaded from ./.env"` (informational — actual loading already happened in `cli/app.py` via `load_dotenv`). If absent: `WARN`, detail `"no project .env"`, fix = None.
  - Section: `SECTION_CONFIG`. Name: `"project .env"`. `required=False`.

- [x] **T23. Test `check_project_env()`**
  - Use `tmp_path` + `monkeypatch.chdir(tmp_path)`.
  - Test 1: create `.env` → `OK`.
  - Test 2: no `.env` → `WARN`, fix is None.

### Phase C — Orchestration and rendering

- [x] **T24. Implement `run_all_checks()` aggregator in `doctor_checks.py`**
  - Synchronous function returning `list[CheckResult]` in section order: Install, Providers and Auth, Integrations, Configuration.
  - Calls each check in order. `check_at_least_one_provider` is called with the output of `check_provider_profiles` so it appears immediately after the per-profile rows.
  - Top-level handler: wrap each individual check call in `try/except Exception as exc` with `logger.exception(...)` and emit a synthetic `WARN` `CheckResult` (`name="<check name>"`, `detail=f"check failed: {exc.__class__.__name__}"`). This is the process-boundary catch from T18.
  - Success: function returns a non-empty list of `CheckResult`s in a default environment.

- [x] **T25. Test `run_all_checks()`**
  - Test 1: returns a list with at least one row per section (count `set` of `r.section`).
  - Test 2: a check function raising `RuntimeError` (via monkeypatched stub) produces a synthetic `WARN` row and does not abort the run.

- [x] **T26. Implement Rich rendering in `doctor.py`**
  - Function `_render_table(results: list[CheckResult], verbose: bool) -> None`.
  - Group by section; render each section as a Rich table or block with rows: status icon, name, detail, indented fix hint when present and status != OK.
  - Icons: `✓` (green) for OK, `✗` (red) for MISSING, `!` (yellow) for WARN.
  - When `verbose=False`, suppress WARN rows; print footer summary `"N missing · M warnings (run with -v to show)"` or omit the warnings clause when M == 0.
  - When `verbose=True`, show all rows; footer becomes `"N missing · M warnings"`.

- [x] **T27. Implement JSON rendering in `doctor.py`**
  - Function `_render_json(results: list[CheckResult], squadron_version: str) -> None`.
  - Print `json.dumps({...}, indent=2)` with keys: `squadron_version`, `exit_code`, `summary` (`{ok, missing, warn}`), `checks` (list of dicts with `section`, `name`, `status` (string), `detail`, `fix_hint`, `required`).
  - JSON output always includes all rows regardless of `--verbose`.

- [x] **T28. Implement `doctor()` Typer command in `doctor.py`**
  - Signature: `def doctor(verbose: bool = typer.Option(False, "--verbose", "-v"), json_output: bool = typer.Option(False, "--json"))`.
  - Body: call `run_all_checks()`, compute `exit_code = 1 if any(r.status == CheckStatus.MISSING for r in results) else 0`, dispatch to `_render_json` or `_render_table`, raise `typer.Exit(exit_code)`.
  - Add typed help text and short docstring `"Inspect runtime environment and report what is configured."`.

- [x] **T29. Register command in `cli/app.py`**
  - Add `from squadron.cli.commands.doctor import doctor` and `app.command("doctor")(doctor)`.
  - Keep the line near the other top-level `app.command(...)` registrations; alphabetical-ish placement next to `install-commands` is fine.

- [x] **T30. Integration test via Typer `CliRunner`**
  - File: `tests/cli/test_doctor.py`
  - Test 1 (fresh-system): `monkeypatch.delenv` for every provider env var, monkeypatch `shutil.which` to return None, monkeypatch `providers_toml_path` and `models_toml_path` to non-existent paths. Invoke `runner.invoke(app, ["doctor"])`. Assert `result.exit_code == 1`, stdout contains `"at least one provider OK"` and `MISSING` indicator.
  - Test 2 (minimum-viable): set `OPENAI_API_KEY=test`. Assert `exit_code == 0`, stdout shows `openai` as OK.
  - Test 3 (broken providers.toml): write malformed TOML to tmp path, monkeypatch `providers_toml_path`. Assert `exit_code == 1`, stdout mentions `malformed`.
  - Test 4 (`--json`): `runner.invoke(app, ["doctor", "--json"])`. Parse `result.stdout` as JSON. Assert top-level keys `squadron_version`, `exit_code`, `summary`, `checks` present. Assert `summary["ok"] + summary["missing"] + summary["warn"]` equals `len(checks)`.
  - Test 5 (`--verbose`): run default and `-v`; assert `-v` stdout line count ≥ default line count. Sufficient to demonstrate gate works.
  - Test 6 (`--help`): assert `"Inspect"` appears in `--help` output.

### Phase D — Final integration

- [x] **T31. Run full gate**
  - `uv run pytest -q` — full suite green.
  - `uv run ruff check && uv run ruff format --check` — clean.
  - `uv run pyright` — zero errors, zero warnings.

- [x] **T32. Manual verification — slice scenarios**
  - Execute the four `env -i` scenarios from the slice design's Verification Walkthrough (fresh, minimum-viable, broken-config, JSON). Record actual output in the slice design's recorded-outcomes section (mirroring 904's pattern).
  - Note any discrepancies between intended and actual rendering; fix or document as follow-up.

- [x] **T33. Update CHANGELOG**
  - Add a user-facing bullet under `[Unreleased]` → `### Added`: short, e.g. `- sq doctor: new command that inspects environment and reports configured providers, integrations, and config files.`
  - Match phrasing style of existing 0.6.0 entries — concise, user-visible behavior only, no implementation detail.

- [x] **T34. Commit and PR**
  - Run `uv run ruff format` immediately before commit.
  - Commit message: `feat: add 'sq doctor' environment diagnostic command`.
  - Open PR against `main`; reference slice 905 and (optionally) 906 as the downstream consumer.

- [x] **T35. Close the slice**
  - When merged: mark slice 905 status `complete` in `user/slices/905-slice.sq-doctor-environment-diagnostic-command.md` frontmatter and update `user/architecture/900-slices.maintenance-and-refactoring.md` entry to `[x]` with completion date.
  - Write DEVLOG entry for slice completion.
