---
docType: slice-design
slice: sq-setup-one-call-install-orchestrator
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [905, 906]
interfaces: []
dateCreated: 20260519
dateUpdated: 20260520
status: complete
---

# Slice Design: `sq setup` — One-Call Install Orchestrator

## Overview

A new `sq setup` subcommand that walks a fresh user through the full Squadron
install sequence in one invocation. It does not install anything itself —
it inspects the environment (reusing `sq doctor`'s check infrastructure),
walks the user step by step, prints the exact shell command needed for each
missing item, and finishes with a `sq doctor` summary so the user can confirm
they are ready.

Interactive by default (pauses at each step for "press enter when done");
`--non-interactive` (`-y`) emits the full checklist without prompting, suitable
for scripted use, paste-into-README, or CI dry-runs.

A companion `install.sh` script (committed alongside the repo, also fetched
from the GitHub raw URL for `curl | sh` use) wraps the *bootstrap* steps a
user can't perform from inside Python — installing `pipx`/`uv`, installing
`squadron-ai` as a tool, installing Context Forge via `npm` — then invokes
`sq setup` to take over. Scope of the shell script is intentionally small;
the orchestration logic lives in `sq setup` so it is testable.

## Value

- **First-time users** get a single guided path from "I just heard about
  Squadron" to "`sq run P4 my-slice` works." No section-grepping across
  README, QUICKSTART, and provider docs.
- **Evaluators / demo audiences** can be told "run `curl <one URL> | sh`" and
  reliably land in a working state.
- **Existing users** who add a new provider or move machines get a
  re-runnable orchestrator instead of memorising `OPENAI_API_KEY` /
  `OPENROUTER_API_KEY` / etc.
- **Slice 906 (QUICKSTART)** can keep prose under the assumption that
  `sq setup` is the canonical path; QUICKSTART becomes the "what each step
  means" companion rather than the only path.
- **Slice 905 (`sq doctor`)** becomes the verification surface — `sq setup`
  runs `sq doctor` at the end and shows the result. Each "fix it with:"
  hint in doctor maps to a step in setup.

## Technical Scope

### Included

1. **New top-level Typer command `sq setup`** at
   `src/squadron/cli/commands/setup.py`.
   - Default: interactive (one step per missing item, prompt to continue).
   - `--non-interactive` / `-y`: emit every step's command without
     prompting; useful for piping to a file or pasting into a script.
   - `--profile <name>`: optionally target a specific provider profile so
     setup only walks that profile's auth step (skips others).
   - `--check-only`: print what would be done, exit with the same code as
     `sq doctor` (no prompts, no rendering of long blocks). This is the
     fast path for re-runs.

2. **Reuse `sq doctor`'s check infrastructure** — `setup` is a *renderer*
   over `run_all_checks()` (see slice 905). It does not add new check logic.
   The mapping it owns is `CheckResult → SetupStep`:
   each missing/warn check that has a `fix_hint` becomes a step the user
   walks through. OK checks are confirmation-only ("✓ Context Forge already
   installed — skipping").

3. **`SetupStep` model** at `src/squadron/cli/commands/setup_steps.py` —
   pure, no I/O — builds an ordered list of steps from a list of
   `CheckResult`. Sequence is fixed (Install → Integrations → Providers →
   Configuration), matching `sq doctor`'s section order. One step per
   missing check; aggregate "at least one provider OK" produces a special
   step that fans out into per-provider sub-steps if `--profile` is not
   set.

4. **`install.sh` bootstrap script** at repo root `scripts/install.sh`
   (also published to a stable URL — see "Distribution" below). Performs
   only the *pre-Squadron* steps:
   1. Detect `uv` / `pipx` / `python3.12+`; install `pipx` via the system
      Python if neither tool is present (with explicit user prompt — no
      silent installs).
   2. `pipx install squadron-ai` (or `uv tool install squadron-ai`).
   3. Detect `node`/`npm`; if absent, print install instructions for the
      user's OS (does not install node itself — too much OS-specific
      surface).
   4. `npm i -g @manta-digital/context-forge`.
   5. `sq setup` — hand control to the Python orchestrator.

5. **README + QUICKSTART updates** (slice 906 is the canonical doc; this
   slice only adds a one-line pointer):
   - README: "New user? `curl -sSL <install.sh URL> | sh`."
   - QUICKSTART (slice 906): note that `sq setup` exists as an alternative
     to following the step-by-step manually.

### Explicitly Excluded

- **No automatic execution of installer commands inside Python.** `sq setup`
  *prints* the command; it does not invoke `npm`, `pipx`, `pip`, or any
  system package manager. The only exceptions are commands that are
  already wholly Squadron-internal: `sq install-commands` (we can call its
  function directly with consent) and (optionally) writing to a `.env`
  file the user explicitly opted into.
- **No remote network calls** beyond what `sq doctor` already does
  (i.e., none — doctor is filesystem/env-only).
- **No interactive provider authentication flows.** `sq setup` tells the
  user "run `sq auth login openai-oauth`" — it does not embed the OAuth
  flow.
- **No prompting for or storing of API keys.** We print the
  `export VAR=...` line, and we link to the relevant QUICKSTART section
  for explanation. Keys never enter Squadron's process.
- **No support for arbitrary user-defined profiles** in the initial
  release beyond what `get_all_profiles()` returns. A user-defined
  profile with a custom auth strategy will show up as a step iff it has a
  `fix_hint`.
- **No PowerShell port of `install.sh` yet.** macOS/Linux only in the
  initial slice; Windows users follow the manual QUICKSTART path. A
  PowerShell port is a candidate follow-up but not required to ship this
  slice.

## Dependencies

### Prerequisites

- **Slice 905** (`sq doctor`) — provides `run_all_checks()`, `CheckResult`,
  `CheckStatus`, and the `fix_hint` contract. `sq setup` is a strict
  consumer of this surface.
- **Slice 906** (QUICKSTART) — provides anchor links that setup's verbose
  output references. If 906 ships first, anchors are real; if not, setup
  emits the section names as plain text (still useful, less clickable).
  Setup can ship in either order; the only coupling is link targets.

### Interfaces required

- `squadron.cli.commands.doctor_checks.run_all_checks()` →
  `list[CheckResult]`. Stable contract from slice 905.
- `squadron.cli.commands.doctor_checks.CheckStatus`,
  `CheckResult` (dataclass; fields `name`, `status`, `detail`, `fix_hint`,
  `section`, `required`).
- `squadron.cli.commands.install.install_commands()` — invokable as a
  Python function, with the user's explicit consent, for the slash-command
  step. (We re-use the Typer command body; safe because the function only
  copies files.)
- `squadron.providers.profiles.get_all_profiles()` — to enumerate
  per-provider sub-steps when the aggregate "at least one provider OK"
  step fires.

### Downstream consumers

- README install pointer (this slice).
- QUICKSTART troubleshooting section (slice 906) — "if you got stuck,
  re-run `sq setup --check-only` and follow the prompts."

## Architecture

### Component structure

Two new files, two edits:

- **New:** `src/squadron/cli/commands/setup.py` — Typer command body and
  rendering (~180 lines target). Interactive prompting, non-interactive
  emission, exit code handling.
- **New:** `src/squadron/cli/commands/setup_steps.py` — pure conversion
  layer: `CheckResult → SetupStep`. No I/O. ~120 lines.
- **New:** `scripts/install.sh` — bash bootstrap (~80 lines). POSIX-safe,
  `set -euo pipefail`, prompts before any destructive operation.
- **Edit:** `src/squadron/cli/app.py` — register
  `app.command("setup")(setup)`.
- **Edit:** `README.md` — replace "New user?" line with `curl | sh`
  pointer to install.sh.

### Data model

```python
from dataclasses import dataclass
from enum import StrEnum

class StepKind(StrEnum):
    ALREADY_DONE = "already-done"     # green — nothing to do
    INSTALL = "install"               # red — must run a shell command
    CONFIGURE = "configure"           # red — must set an env var or run sq auth
    OPTIONAL = "optional"             # yellow — warn-level; skip unless --all

@dataclass(frozen=True)
class SetupStep:
    title: str                # short label, e.g. "Install Context Forge"
    kind: StepKind
    section: str              # mirrors doctor's section name
    detail: str               # human-readable current state
    command: str | None       # the exact shell command, if any
    explanation: str | None   # 1-2 sentence why-this-step, shown with --verbose
    docs_anchor: str | None   # e.g. "docs/QUICKSTART.md#step-1-install-context-forge"
```

### Data flow

```
sq setup [--non-interactive] [--profile P] [--check-only]
   │
   ▼
1. Load env (load_dotenv) — same as sq doctor.
2. results = run_all_checks()                # reuse slice 905
3. steps  = build_steps(results, profile)    # pure
4. branch on flags:
     --check-only        → emit one-line summary per step, exit doctor's code
     --non-interactive   → emit full steps + commands in order, exit doctor's code
     default (interactive):
        for step in steps:
            render_step(step)
            if step.kind == ALREADY_DONE:    # skip prompt
                continue
            if step.kind == OPTIONAL and not --all:
                ask("skip?") (default yes) → continue
            else:
                print command
                prompt("press enter when done, 's' to skip, 'q' to quit")
                on quit: exit with code 2 (incomplete)
                on skip: continue, mark skipped
        run sq doctor at the end → render summary
        exit code: doctor's exit code (0 if all required OK)
```

`build_steps` is pure: same input → same output. This is the testable
contract; all rendering and I/O are in `setup.py`.

### Mapping table — `CheckResult` → `SetupStep`

| CheckResult (name) | Section | OK case | Missing case | Warn case |
|---|---|---|---|---|
| `squadron` | Install | ALREADY_DONE | INSTALL (impossible — they ran `sq setup`) | — |
| `slash commands` | Install | ALREADY_DONE | INSTALL `sq install-commands` (also offer to run in-process) | OPTIONAL same |
| `context-forge` | Integrations | ALREADY_DONE | INSTALL `npm i -g @manta-digital/context-forge` | OPTIONAL same |
| `codex CLI` | Integrations | ALREADY_DONE | OPTIONAL `npm i -g @openai/codex` | OPTIONAL same |
| `Claude Code session` | Integrations | ALREADY_DONE | OPTIONAL "launch Claude Code if you want SDK provider" | OPTIONAL same |
| `<profile-name>` (per-profile) | Providers | ALREADY_DONE | CONFIGURE `<fix_hint verbatim>` | OPTIONAL same |
| `at least one provider OK` | Providers | ALREADY_DONE | aggregate CONFIGURE "configure at least one profile above" | — |
| `providers.toml` | Configuration | ALREADY_DONE | CONFIGURE `<fix_hint>` (malformed file) | — |
| `models.toml` | Configuration | ALREADY_DONE | CONFIGURE `<fix_hint>` (malformed file) | — |
| `project .env` | Configuration | ALREADY_DONE | OPTIONAL "create a project .env if you want per-project overrides" | OPTIONAL same |

Rules encoded in `build_steps`:
1. Every `CheckResult` with `status == MISSING` produces a step of kind
   `INSTALL` (Install/Integrations section) or `CONFIGURE` (others).
2. Every `CheckResult` with `status == WARN` produces a step of kind
   `OPTIONAL`.
3. Every `CheckResult` with `status == OK` produces a step of kind
   `ALREADY_DONE` (rendered as a green confirmation, not prompted).
4. The aggregate "at least one provider OK" missing case suppresses
   individual provider OPTIONAL steps and replaces them with prompts to
   pick one. (Implementation detail: in the initial release we keep this
   simple and just show all profile rows; the suppression optimisation
   is a follow-up.)

### Interactive prompting model

We use Typer's built-in `typer.confirm` and `typer.prompt`. No third-party
TUI library. The interaction at each non-`ALREADY_DONE` step is:

```
Step 2/7 — Install Context Forge
─────────────────────────────────
Context Forge is not on PATH. Squadron uses `cf` to drive pipeline runs.

Run this command in another terminal:

  npm i -g @manta-digital/context-forge

Press enter when done, 's' to skip, 'q' to quit:
```

Responses:
- empty / enter → re-run that one check; if still missing, re-prompt
  (offer "skip"); if now OK, advance.
- `s` → mark skipped (status code stays at whatever doctor would say),
  advance.
- `q` → exit with code 2 (user-aborted, distinct from doctor's 1).

In `--non-interactive` mode we just print the block (no prompts, no
re-checks) and emit the next one.

### Re-check semantics

After each step the user marks "done," we re-run only that check's
function (not all of `run_all_checks`). This is an extension point —
slice 905's `run_all_checks` aggregates many checks; we want per-check
re-run. To support this without bloating the API, `setup_steps` keeps a
reference to the *check function* alongside each step:

```python
@dataclass(frozen=True)
class SetupStep:
    ...
    recheck: Callable[[], CheckResult] | None = None
```

`build_steps` populates `recheck` from a fixed map of "check name →
function" maintained inside `setup_steps.py`. If the map doesn't know a
check name, `recheck` is `None` and we just say "press enter when done"
without verifying. This degrades gracefully if slice 905 adds new checks
we haven't mapped yet.

(Alternative considered: have `run_all_checks` return checks keyed by a
stable identifier, and re-call by key. That requires an API change to
slice 905 and is a larger surface. The per-check-function map is local to
this slice and changes here, not in 905.)

### Distribution of `install.sh`

The script lives at `scripts/install.sh` in the repo. We publish it via
GitHub raw URL (stable at `main`):

```
https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh
```

The README pointer is the canonical one-liner:

```
curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh
```

We do *not* host the script on a separate domain; the GitHub URL is
fine. Pinning to a tag (e.g. `/v0.7.0/scripts/install.sh`) is a follow-up
hardening once we've shipped a tagged release.

### Failure-mode enumeration

| Failure mode | `sq setup` observably handles by |
|---|---|
| User says "done" but check is still missing | Re-render the same step with "still not detected" in detail; offer `skip` or `q`. Cap re-prompts at 5 to avoid infinite loops in scripted runs. |
| `run_all_checks` raises (slice 905 bug) | Top-level process boundary catches, logs at ERROR via `logger.exception`, prints "sq doctor failed; cannot continue setup", exit 3. |
| Slash-commands install fails (file system error) | `install_commands` already prints its own error and raises `typer.Exit(1)`; our caller catches `typer.Exit`, marks step as failed, advances. |
| `--profile <name>` names a profile not in `get_all_profiles()` | Validate before the loop; exit 64 (usage error) with the list of available profiles. |
| User has slash commands installed to a non-default path | Detected by slice 905's check, which only inspects `~/.claude/commands/sq`. Setup prints the standard install hint; user can ignore or skip. Acceptable — non-standard installs are out of mainstream. |
| `install.sh` invoked but `bash` not present (Alpine, busybox) | Script begins with `#!/usr/bin/env bash`; if `bash` is missing, the kernel emits its own ENOENT message. The script does not attempt POSIX-shell compatibility — too much surface for too few users. README notes "requires bash 4+ on macOS/Linux." |
| `install.sh` partial completion (user Ctrl-C between steps) | `set -euo pipefail` means we exit. Re-running re-detects what's done and skips it. The script is idempotent by virtue of using detection (`command -v cf`, `command -v sq`) before each install. |

All catches above log via `logger.exception` at WARNING+ and emit a
visible row — no swallowed exceptions.

### Why this design

- **Setup as a renderer over doctor.** The check logic already exists.
  Duplicating it in setup would invite drift. Treating setup as a UI on
  top of doctor's data model means every check that gets added to doctor
  becomes orchestratable by setup automatically (with the small caveat of
  the recheck-function map).
- **No automatic shell execution.** Two reasons: (a) curl-pipe-to-shell
  is a known trust surface, so the *Python* part of the install does not
  arbitrarily execute commands; (b) writing a robust cross-platform
  installer for npm/pipx in Python is more work than it's worth — let
  bash do bash's job in `install.sh`, and let Squadron's Python guide the
  rest.
- **Re-runnable.** A user who runs setup, fixes some things, runs again,
  should see progress and only be prompted for what's still missing.
  Achieved trivially because every step is derived from a fresh
  `run_all_checks()` invocation.

## Cross-slice dependencies and interfaces

- **Slice 905 (`sq doctor`)** — strict consumer of `CheckResult` and
  `run_all_checks()`. `setup` adds no new checks and asks for no API
  changes to 905. If 905 ever needs to expose per-check identifiers
  beyond the human-readable name, that's a follow-up — but not blocking.
- **Slice 906 (QUICKSTART)** — anchor targets. The
  `SetupStep.docs_anchor` field references QUICKSTART headings. If 906
  renames a section, this slice's mapping must update in the same PR.
- **Slice 907 (already merged)** — `sq serve` daemon documentation. Setup
  may add a future "is your daemon running?" step, but the initial
  release does not — the daemon is required only for `sq spawn`/`sq task`
  and a fresh user does not need it.

## Success criteria

1. `sq setup --help` prints sensible help text describing interactive,
   non-interactive, and check-only modes.
2. On a freshly cloned machine (no `cf`, no `OPENAI_API_KEY`, no slash
   commands), running `sq setup --non-interactive` prints, in order,
   every step needed to reach a working install, each with a copy-pastable
   shell command.
3. On the same fresh machine, running `sq setup` interactively walks
   through each step and re-checks after the user marks done; the user
   reaches "sq doctor: 0 missing" without leaving the terminal.
4. Running `sq setup --check-only` on a fully configured machine exits 0
   with no prompts and no long output beyond a one-line summary per step.
5. Running `sq setup --profile openai` on a fresh machine walks through
   *only* the openai profile's auth step (plus shared Install /
   Integrations steps); other provider rows are silently skipped.
6. `scripts/install.sh` is idempotent: running it twice from a clean
   machine leaves the same state as running it once. (Tested by running
   it, recording state, running again, diffing.)
7. The final `sq doctor` invocation embedded in setup uses the same exit
   code as standalone `sq doctor` (i.e., 0 if all required checks pass,
   1 otherwise, 2 if user quit, 3 if an internal error occurred).
8. Unit tests cover `build_steps` with at least: all-missing, all-ok,
   partial, unknown-check-name, `--profile` filter, and the aggregate
   "at least one provider" suppression rule.
9. Integration test invokes `sq setup --non-interactive` via Typer's
   `CliRunner` against three fixture environments (all-missing, partial,
   all-ok) and asserts exit code and step ordering.
10. `install.sh` has at least one shell-level smoke test
    (`bats` or a bash script that asserts idempotency on a temp `HOME`).

## Verification walkthrough

Walkthrough validated in Phase 6 (20260520). Results recorded below.

### Scenario 1 — fresh laptop, non-interactive

```bash
# Simulated fresh env (credentials cleared):
env HOME=$(mktemp -d) OPENAI_API_KEY="" OPENROUTER_API_KEY="" \
    GEMINI_API_KEY="" ANTHROPIC_API_KEY="" CLAUDECODE="" \
    uv run sq setup --non-interactive
```

Actual output (abridged): numbered step blocks printed for all 15 steps.
WARN steps (slash commands, unconfigured profiles) shown as `!` yellow.
OK steps (squadron version, detected session) shown as `✓` green.
Install-section steps include `$ <command>` lines.
Exit code: 0 (SDK session was still detected via other env vars on this dev machine;
on a true isolated machine with no squadron env vars, exit would be 1).

### Scenario 2 — fresh laptop, interactive

Verified manually: interactive prompt loop advances on enter, skips on `s`,
quits with exit code 2 on `q`. Recheck loop tested via unit test T23.

### Scenario 3 — re-run after partial completion / check-only on fully configured machine

```bash
uv run sq setup --check-only
```

Actual output (fully configured dev machine):
```
✓ Squadron installed              version 0.6.0
✓ Install slash commands          8 command(s) at ~/.claude/commands/sq
✓ gemini                          GEMINI_API_KEY
✓ local                           OPENAI_API_KEY
✓ openai                          OPENAI_API_KEY
✓ openai-oauth                    ~/.codex/auth.json
✓ openrouter                      OPENROUTER_API_KEY
✓ sdk                             (session)
✓ At least one provider authenticated  6 of 6 profiles authenticated
✓ Install Context Forge           cf at /Users/manta/Library/pnpm/cf
✓ Install Codex CLI               codex at ...
✓ Claude Code session             CLAUDECODE=1
✓ providers.toml valid            using defaults (...)
✓ models.toml valid               using defaults (...)
✓ Project .env file               loaded from ./.env
```
Exit code: 0. No prompts, one line per step, no command blocks.

### Scenario 4 — `--profile` filter

```bash
uv run sq setup --profile openai --check-only
```

Actual: only `openai` + `at least one provider OK` appear in Providers section.
Other profiles (gemini, openrouter, etc.) suppressed. Exit code: 0.

```bash
uv run sq setup --profile nonexistent --check-only
```

Actual output: `sq setup: Unknown profile 'nonexistent'. Available: gemini, local, openai, openai-oauth, openrouter, sdk`
Exit code: 64. ✓

### Scenario 5 — `install.sh` idempotency

Verified via automated test at `tests/scripts/test_install_sh.py`:

```bash
uv run pytest tests/scripts/test_install_sh.py -q
# 1 passed
```

The test stubs `sq`, `cf`, `uv`, `pipx`, and `npm`, verifies that two consecutive
runs do not invoke install-side stubs when the tools are already on PATH.

### Scenario 6 — full gate

```bash
uv run pytest tests/cli/test_setup.py tests/cli/test_setup_steps.py \
    tests/scripts/test_install_sh.py -q
# 31 passed

uv run pytest -q
# 1936 passed, 2 skipped

uv run ruff check && uv run ruff format --check && uv run pyright
# All checks passed / 313 files formatted / 0 errors
```

All tests pass; lint/format/typecheck clean. ✓

## Risks

- **`install.sh` is a trust surface.** Anything fetched via `curl | sh`
  is a security concern. Mitigation: the script does not run with `sudo`
  unless the user explicitly invokes it as such; it prompts before any
  install that touches a system path; the README documents how to read
  the script first (`curl -sSL <url> -o install.sh; less install.sh; bash
  install.sh`). We don't attempt to make `curl | sh` *safe* — we make it
  *honest about what it does.*
- **Drift between `sq setup`'s recheck-function map and slice 905.** If
  905 renames a check (e.g. `openai` → `openai-api`), setup's recheck
  fallback degrades to "press enter when done" without verifying — a
  noticeable UX regression but not a crash. Mitigated by a slice-905
  CI test that compares the doctor check name list to setup's recheck
  map (extra check fail → loud warning, not a build break).
- **Per-OS install command divergence** — `npm i -g` may need `sudo` on
  some Linux configurations, or fail entirely on Nix/Homebrew managed
  installs. Setup prints the canonical command; the user adapts. Risk is
  bounded: setup is guidance, not execution.

## Effort

2/5. Mostly orchestration code (renderer + prompt loop + step builder)
and a small bash script. No new check logic, no provider changes, no
template changes. The verification walkthrough requires a fresh shell
environment which takes care to set up but is straightforward.
