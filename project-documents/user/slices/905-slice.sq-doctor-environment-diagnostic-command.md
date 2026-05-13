---
docType: slice-design
slice: sq-doctor-environment-diagnostic-command
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [906]
dateCreated: 20260513
dateUpdated: 20260513
status: not_started
---

# Slice Design: `sq doctor` Environment Diagnostic Command

## Overview

A new read-only `sq doctor` subcommand that inspects the runtime environment a user has assembled and reports it as a human-readable checklist. For every check it answers three questions: is it there, what would Squadron do with it, and — if missing or broken — how do I fix it?

Primary motivation is onboarding friction: Squadron's working environment is assembled from three package managers (npm Context Forge, pipx Squadron, per-provider auth via env vars or `codex login`), and there is currently no single place a new user can run to see what is and isn't wired up. Secondary motivation is promotion-readiness: a discoverable "is everything OK?" command is table stakes for tools that span multiple install paths.

Scope is strictly read-only inspection. No config is written, nothing is installed, no auth flows are triggered. Out of scope: auto-remediation, interactive setup wizard, network probes against provider endpoints (auth correctness is verified by `sq auth login`, not here).

## Value

- **New users** get a single command that says what's missing and how to fix it, without grepping README sections.
- **Existing users** get a one-shot environment sanity check before filing bug reports ("paste your `sq doctor` output").
- **Slice 906 (Quickstart)** gets a referenced command — the QUICKSTART can say "if you get stuck, run `sq doctor`."
- **CI / scripts** get a non-zero exit code when at least one required item is missing, suitable for use as a pre-flight gate.

## Technical Scope

### Included

A new top-level Typer command `sq doctor` that runs a fixed set of read-only checks, prints a Rich-formatted checklist to stdout, and exits with code 0 when all required checks pass or non-zero when at least one required check fails.

Checks are grouped into four sections:

1. **Squadron install** — package version, slash-commands installed location.
2. **Providers and auth** — for every profile in `get_all_profiles()`, run the existing `resolve_auth_strategy_for_profile(profile).is_valid()` and report the active source or setup hint.
3. **Integrations** — Context Forge CLI on `PATH`, Codex CLI binary on `PATH`, Claude Code session detection (best-effort: presence of `CLAUDE_CODE_*` env vars or `CLAUDECODE=1`).
4. **Configuration files** — existence (and parseability) of `~/.config/squadron/providers.toml` and `~/.config/squadron/models.toml`; presence of project-local `.env`.

Each check produces one row: status icon (`✓` / `✗` / `!`), short name, one-line detail, and — when not OK — a "fix it with:" hint.

Optional flags:

- `--json` — emit a machine-readable JSON report instead of the Rich table. Useful for CI and for paste-into-issue.
- `--verbose` / `-v` — include WARN-level rows that are hidden by default (e.g., optional integrations that are not wired up but not required for the user's apparent intent).

### Explicitly Excluded

- No auto-remediation (don't run `codex login`, don't `pipx install`, don't write config).
- No interactive prompts.
- No network calls to provider endpoints — auth file presence and env-var presence are sufficient. Validating an actual API key works against the wire is `sq auth login`'s job.
- No "apparent intent" inference (initial release): every defined check runs, every missing required item contributes to non-zero exit. The "user's apparent intent" wording in the slice plan is satisfied by classifying profiles as required vs optional, not by inferring which providers a user wants.
- No discovery of arbitrary user-defined profiles in `providers.toml` for additional checks beyond auth validity — they fall under the providers section like any built-in profile.

## Dependencies

### Prerequisites

- None. All inspection targets (`get_all_profiles`, `resolve_auth_strategy_for_profile`, `providers_toml_path`, `models_toml_path`, `_CODEX_AUTH_FILE`) already exist.

### Interfaces Required

- `squadron.providers.profiles.get_all_profiles()` — iterates built-in + user profiles.
- `squadron.providers.auth.resolve_auth_strategy_for_profile(profile)` — already returns a strategy with `.is_valid()`, `.active_source`, `.setup_hint`. This is the contract `doctor` consumes; no new code on the providers side.
- `squadron.providers.profiles.providers_toml_path()` and `squadron.models.aliases.models_toml_path()` — already exposed.
- `importlib.metadata.version("squadron-ai")` — already used in `app.py:59`.
- `shutil.which("cf")`, `shutil.which("codex")` — stdlib.

### Slice 906 (Quickstart) — downstream consumer

Slice 906 will reference `sq doctor` in the QUICKSTART. To support that, `doctor`'s "fix it with:" hints should be self-contained one-liners that don't *require* reading the QUICKSTART. The QUICKSTART link is a "for more detail, see ..." pointer, not a substitute for the hint itself.

## Architecture

### Component Structure

Two new files, one edit:

- **New:** `src/squadron/cli/commands/doctor.py` — the Typer command body. Orchestrates checks and renders output. Target ~150 lines.
- **New:** `src/squadron/cli/commands/doctor_checks.py` — pure check functions, one per inspection target. Each returns a `CheckResult` dataclass. Target ~200 lines. Keeping checks separate from rendering keeps them unit-testable without spinning up Typer.
- **Edit:** `src/squadron/cli/app.py` — register the command via `app.command("doctor")(doctor)`.

### Data Model

```python
from enum import StrEnum
from dataclasses import dataclass, field

class CheckStatus(StrEnum):
    OK = "ok"           # green ✓ — nothing to do
    MISSING = "missing" # red ✗   — required item not present
    WARN = "warn"       # yellow ! — optional/degraded; hidden without -v

@dataclass(frozen=True)
class CheckResult:
    name: str                 # short label, e.g. "openai profile"
    status: CheckStatus
    detail: str               # one-line state description
    fix_hint: str | None = None  # actionable instruction, None when OK
    section: str = ""         # group label for rendering
    required: bool = True     # MISSING with required=False → WARN
```

Required-ness is per-check, not per-section. The `sdk` profile is *required* for SDK pipelines but *optional* for users who only call the API; rather than infer intent we mark every built-in profile's auth check as `required=False` (warn-only) and mark only the few things that genuinely block all use as required: Squadron package itself, slash-commands directory existence, and at least one usable provider profile aggregate (see "At-least-one provider" below).

### Data Flow

```
sq doctor
   │
   ▼
doctor.run()
   ├── collect: list[CheckResult] = run_all_checks()        # pure, sync
   │     ├── check_squadron_install()
   │     ├── check_slash_commands()
   │     ├── check_provider_profiles()      → 1 row per profile
   │     ├── check_at_least_one_provider()  → aggregate row
   │     ├── check_context_forge()
   │     ├── check_codex_cli()
   │     ├── check_claude_code_session()
   │     ├── check_providers_toml()
   │     ├── check_models_toml()
   │     └── check_project_env()
   │
   ├── filter by verbosity (drop WARN rows when -v not set)
   ├── render: Rich table (or JSON if --json)
   └── exit code: 0 if no MISSING rows, 1 otherwise
```

All check functions are synchronous and pure (no I/O beyond `Path.exists()`, `os.environ.get`, `shutil.which`, and `tomllib.load` on small known files). No threads, no asyncio, no provider instantiation that would trigger network calls.

### Required vs Optional

| Check | Default required? | Notes |
|---|---|---|
| Squadron package version | Yes | Trivially always passes; included for paste-into-issue ergonomics. |
| Slash-commands directory exists | No (WARN) | Users running headless CLI don't need it. |
| Individual provider profile auth | No (WARN) | Per-profile auth is informational; aggregate is what gates exit. |
| At-least-one provider authenticated | Yes | If no profile is usable, Squadron cannot run anything. |
| Context Forge CLI on PATH | No (WARN) | Required for `/sq:run`-style pipelines but not for `sq review` etc. |
| Codex CLI binary on PATH | No (WARN) | Only needed for codex-agent profile. |
| Claude Code session detected | No (WARN) | Only needed for SDK profile. |
| `providers.toml` parseable | Yes *iff* present | Missing file is fine; broken file is MISSING. |
| `models.toml` parseable | Yes *iff* present | Same as above. |
| Project `.env` | No (WARN) | Informational. |

Exit code rule: exit 1 if any row has `status == MISSING`; otherwise exit 0. WARN rows never affect exit code.

### Rendering

Default (Rich table, grouped by section):

```
Squadron Environment Diagnostic
────────────────────────────────────────────────────────────────
Install
  ✓ squadron 0.6.0            installed via pipx
  ! slash commands             not installed at ~/.claude/commands
                               fix: sq install-commands

Providers and Auth
  ✓ openai                     OPENAI_API_KEY (env)
  ✗ openrouter                 no credential found
                               fix: export OPENROUTER_API_KEY=...
  ✓ sdk                        (Claude Code session)
  ! gemini                     no credential found
                               fix: export GEMINI_API_KEY=... (optional)
  ✓ at least one provider OK   3 of 6 profiles authenticated

Integrations
  ✓ context-forge              cf v1.4.2 at /usr/local/bin/cf
  ! codex CLI                  not on PATH
                               fix: npm i -g @openai/codex (optional)
  ✓ Claude Code session        CLAUDECODE=1

Configuration
  · providers.toml             not present at ~/.config/squadron/providers.toml
  · models.toml                not present at ~/.config/squadron/models.toml
  ✓ project .env               loaded from ./.env

────────────────────────────────────────────────────────────────
0 missing · 3 warnings (run with -v to show)
```

`--json` form:

```json
{
  "squadron_version": "0.6.0",
  "exit_code": 0,
  "summary": {"ok": 5, "missing": 0, "warn": 3},
  "checks": [
    {
      "section": "Install",
      "name": "squadron",
      "status": "ok",
      "detail": "installed via pipx",
      "fix_hint": null,
      "required": true
    },
    ...
  ]
}
```

The JSON form is the contract for CI / paste-into-issue. Field names are stable; new fields may be added but existing ones won't be renamed without a version bump.

### "Apparent intent" — deferred

The slice plan mentions "non-zero when at least one required item is missing *for the user's apparent intent*." We interpret this minimally: rather than inferring user intent, we mark only checks that block *all* Squadron use as required. Everything provider-specific or integration-specific is WARN. This avoids the inference trap (today's user runs only `sq review`, doesn't need Context Forge; tomorrow same user runs `sq run`, does). If real-world feedback shows this is too lenient, we can add a `--for <profile>` flag in a follow-up slice that promotes a profile's checks to required.

## Failure-mode enumeration

Each check is itself I/O. What can go wrong:

| Failure mode | Check observably handles by |
|---|---|
| `tomllib.load` raises on malformed `providers.toml` | Catch `tomllib.TOMLDecodeError`, report `MISSING` with `detail="malformed: <exception>"` and `fix_hint="repair or remove ~/.config/squadron/providers.toml"`. |
| `Path.home()` returns a path the user can't read | `Path.exists()` returns False, treated as "not present" (WARN). Acceptable — doctor is read-only and shouldn't escalate. |
| `shutil.which("cf")` returns a path that no longer exists (race) | Report path that `which` returned; we don't `--version` it in the default check to keep doctor fast. Optional: in `--verbose` mode, run `cf --version` to catch broken installs. |
| Auth strategy `.is_valid()` raises on unexpected profile shape | Wrap each profile check in `try/except` (typed) — log at WARNING via `logger.exception`, report row as `MISSING` with detail "internal error: <exc>". This is a Squadron bug surfacing in doctor output; better than a stack trace. |
| `importlib.metadata.version` raises `PackageNotFoundError` (running from source without install) | Catch, report version as "(dev install)" and source path. Not MISSING. |
| `~/.config/squadron/` does not exist | Don't try to create it. Configuration files are reported as "not present" (informational, never MISSING). |

Every catch above logs at WARNING via `logger.exception` per project rules (no swallowed exceptions).

## Cross-slice dependencies and interfaces

- **Slice 906 (Quickstart docs)** is the downstream consumer. Doctor's `fix_hint` strings are the contract: 906 will reference these verbatim. Keep hints short, imperative, copy-pasteable.
- **No interface change** to providers, profiles, auth, or any other subsystem. Doctor is a pure consumer.

## Success criteria

A user running `sq doctor` on a fresh machine with nothing configured sees:

1. A row for the squadron package itself (OK — they ran the command).
2. A row per provider profile, all marked MISSING with the env-var name in the fix hint.
3. An aggregate "at least one provider OK" row marked MISSING.
4. A row for Context Forge marked WARN with `npm i -g @manta-digital/context-forge`.
5. Exit code 1.

A user who has configured `OPENAI_API_KEY` and `cf` on PATH but nothing else sees:

1. Package row OK.
2. `openai` profile OK, others WARN.
3. Aggregate provider row OK.
4. Context Forge row OK.
5. Exit code 0.

A user with a broken `providers.toml` sees that profile's parse error in the row's `detail`, MISSING status, and exit code 1 — regardless of what else is configured.

`--json` output is parseable JSON; all fields documented above are present; status values are exactly `ok` / `missing` / `warn`.

`sq doctor --help` produces sensible help text.

Unit tests cover each check function with at least: present-and-valid, present-and-broken, absent cases. Integration test invokes the full command via Typer's `CliRunner` and asserts exit code and section presence on three fixture environments (all-OK, all-missing, partial).

## Verification walkthrough

The user can prove the slice works without touching their real config by exercising three scenarios.

### Scenario 1 — fresh-system simulation

```bash
env -i HOME=$(mktemp -d) PATH=/usr/bin:/bin uv run sq doctor
```

Expected:
- Several MISSING rows under "Providers and Auth" (no env vars).
- "At least one provider OK" row MISSING.
- Context Forge, Codex CLI rows WARN (not on PATH).
- Exit code 1.

### Scenario 2 — minimum-viable configuration

```bash
env -i HOME=$HOME PATH=$PATH OPENAI_API_KEY=$OPENAI_API_KEY uv run sq doctor
```

Expected:
- `openai` profile OK.
- Aggregate "at least one provider OK" OK.
- Other provider rows WARN.
- Exit code 0.

### Scenario 3 — broken config file

```bash
mkdir -p /tmp/sqdoctor-home/.config/squadron
echo 'this is not toml = "' > /tmp/sqdoctor-home/.config/squadron/providers.toml
env -i HOME=/tmp/sqdoctor-home PATH=$PATH OPENAI_API_KEY=$OPENAI_API_KEY uv run sq doctor
```

Expected:
- "providers.toml" row MISSING with detail containing `TOMLDecodeError`.
- Exit code 1 (overriding the otherwise-OK provider state).

### Scenario 4 — JSON output

```bash
uv run sq doctor --json | jq '.summary'
```

Expected: prints `{"ok": N, "missing": M, "warn": W}` where the three numbers sum to the total check count.

### Scenario 5 — verbosity gate

```bash
uv run sq doctor       # WARN rows hidden
uv run sq doctor -v    # WARN rows shown
```

Expected: the `-v` form contains strictly more rows than the default form (or equal if no WARN rows exist). The default form's row count plus the hidden-warning count printed in the footer should equal the `-v` form's row count.

### Scenario 6 — full gate

```bash
uv run pytest tests/cli/test_doctor.py -q
uv run pytest -q
uv run ruff check && uv run ruff format --check && uv run pyright
```

Expected: new doctor tests pass; full suite remains green; lint and type-check pass.

## Risks

- **Drift between `sq doctor` output and reality.** Doctor reports what *it* sees, not what a given pipeline actually needs. A user could see "all OK" and still hit a different failure at run time (network down, key revoked, etc.). Mitigated by hint phrasing: "authenticated locally" not "will work" — and by `sq auth login` being the place that actually pings the provider when that exists.
- **`shutil.which` cache / PATH quirks** can make Codex/Context Forge appear missing in unusual shell environments (asdf, mise). Mitigation: print the actual `PATH` snippet in `--verbose` mode for the binary checks that fail. Trivial cost, large debuggability win.

## Effort

2/5. The harder parts already exist (auth strategies, profile registry); doctor is mostly orchestration and rendering.
