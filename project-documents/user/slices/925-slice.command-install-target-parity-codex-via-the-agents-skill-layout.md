---
docType: slice-design
slice: command-install-target-parity-codex-via-the-agents-skill-layout
project: squadron
parent: ../architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260921
dateUpdated: 20260922
status: in_progress
---

# Slice Design: command-install-target-parity-codex-via-the-agents-skill-layout

## Overview

`sq install-commands` knows one destination. It takes a raw `--target` directory defaulting to `~/.claude/commands`, copies `commands/sq/*.md` and `commands/analysis/*.md` into it, writes a receipt, and stops ([install.py](../../../src/squadron/cli/commands/install.py)). Squadron ships a Codex provider and `sq doctor` detects the Codex binary, yet in a Codex session no `sq` command exists, because nothing was ever written where Codex looks ([issue #123](https://github.com/ecorkran/squadron/issues/123)).

This slice gives `install-commands` / `uninstall-commands` a target *kind* — a closed vocabulary matching Context Forge's (`claude`, `agents`; `codex` and `openai` as aliases of `agents`) — a per-target delivery description, a second checked-in asset tree in Codex's skill-directory layout, and the two callers that hardcode the Claude path (`sq doctor`, `sq setup`) learn the same flag. A bare `sq install-commands` is byte-for-byte unchanged.

## Value

- **Users running squadron under Codex** get `$sq-review`, `$sq-run`, `$sq-summary` and the rest, installed by the same command and flag spelling they already use for `cf` (`cf install-commands --ide codex`). Today they get nothing and no error telling them why.
- **Developers** get one place where "what does the string `codex` mean" is answered, shared by every command that will ever take an IDE target (skill packs are the obvious next consumer — [skills.py](../../../src/squadron/cli/commands/skills.py) hardcodes the same `~/.claude/commands`).
- **The Claude and agents asset trees cannot drift silently**: a test enforces that every Claude command has an agents counterpart.

## Technical Scope

**In scope**

1. `CommandTarget` enum, alias table, and one normalize function (`src/squadron/skills/targets.py`).
2. Per-target delivery descriptors: machine-level root, project-local root, bundle subdirectory, layout writer.
3. `--ide` and `--local` on `install-commands` and `uninstall-commands`; `--target DIR` retained as the override that beats both.
4. A second bundle tree, `commands/agents/<skill>/SKILL.md` (new, checked in), beside the existing `commands/sq/` and `commands/analysis/`, which do not move (D8). `pyproject.toml` force-include and `_get_commands_source()` are untouched.
5. Authoring the agents asset tree: one skill per Claude command file, prose argument handling, `name`/`description` frontmatter, `agents/openai.yaml` where the Claude file carries `disable-model-invocation: true`.
6. Per-target receipts, with the existing Claude receipt name preserved so pre-existing receipts still read.
7. `sq doctor`: the commands check becomes per-target and doctor emits one row per detectable target. `sq setup`: gains `--ide`, threaded through `run_all_checks` and the name-keyed step tables in `setup_steps.py` (D9).
8. Drift test between the two asset trees; tests for normalization, per-target install/uninstall, receipt isolation, and the unchanged Claude default.
9. `docs/QUICKSTART.md` install section and README: mention `--ide codex`.

**Out of scope**

- `sq skills install` targets. Tracked as a follow-up issue filed when this slice closes; it consumes `CommandTarget` but is its own change (pack manifests describe Claude surfaces).
- `copilot`, `cursor`: `cf` rejects them for command delivery because no delivery mechanism exists; squadron does the same and does not list them in the enum (there is nothing they would select).
- `setup-ide`-style guide propagation (`AGENTS.md`, project-guide skills): that is Context Forge's job.
- Retiring Codex's deprecated `~/.codex/prompts` flat-prompt format: not used, not supported.

## Dependencies

### Prerequisites

- Slice 922 landed the receipt-based uninstall (#65) this builds on; nothing else.
- Codex CLI present on the machine for the live walkthrough only; unit tests do not need it.

### Interfaces Required

- `InstallReceipt` / `write_receipt` / `read_receipt` from [skills/receipts.py](../../../src/squadron/skills/receipts.py) — used as-is; receipts are keyed by `pack_name`, and the target/scope is folded into the name (D5), so no schema change.
- `CheckResult` / `CheckStatus` / `SECTION_INSTALL` from [doctor_checks.py](../../../src/squadron/cli/commands/doctor_checks.py).
- `check_codex_cli()` (same module) — the agents-target doctor check runs only when this reports the binary present.

## Architecture

### Component Structure

```
src/squadron/skills/targets.py          NEW  CommandTarget, TARGET_ALIASES, normalize_target, TargetDelivery table
src/squadron/cli/commands/install.py    MOD  --ide/--local; delegates per-target copy to the delivery's layout
src/squadron/cli/commands/doctor_checks.py  MOD  check_commands_installed(target) -> CheckResult; run_all_checks(ide=...)
src/squadron/cli/commands/setup_steps.py    MOD  codex-skills entries in the name-keyed step tables (D9)
src/squadron/cli/commands/setup.py      MOD  --ide, forwarded to run_all_checks and the installer
src/squadron/cli/commands/setup_install.py  MOD  _install_sq_commands(target)
commands/sq/*.md, commands/analysis/*.md    UNCHANGED (the Claude tree; D8)
commands/agents/sq-<name>/SKILL.md      NEW  one per commands/sq/<name>.md
commands/agents/analysis-<name>/SKILL.md (+ agents/openai.yaml)  NEW  one per commands/analysis/<name>.md
```

`targets.py` owns the vocabulary and the table. `install.py` owns the copy/receipt/stale-removal loop it has today, parameterized by a `TargetDelivery` instead of a hardcoded path and glob. Nothing in `install.py` mentions `.claude` or `.agents` after this slice. `skills/resolver.py` and `metrology/audit.py`, which resolve `commands/analysis/` by pack name, are not touched.

### Data Flow

`sq install-commands --ide codex [--local] [--target DIR]`

1. `normalize_target("codex")` → `CommandTarget.AGENTS`; unknown strings raise `typer.BadParameter` listing the accepted names and aliases.
2. Resolve destination: `--target DIR` if given; else `delivery.local_root` (relative to cwd) if `--local`; else `delivery.machine_root`.
3. Sources = `_get_commands_source() / sub` for each `sub` in `delivery.bundle_subdirs` — `("sq", "analysis")` for Claude, `("agents",)` for agents. The Claude delivery names its subdirectories explicitly; it no longer walks every directory under `commands/` (which would now include `agents/`).
4. Layout writer walks each source: for the agents layout, each `<skill>/` directory is copied whole (`SKILL.md` and, when present, `agents/openai.yaml`); for the Claude layout, `<sub>/*.md` as today. Both return `files_written` relative to the destination.
5. Receipt read/write under the per-target name (D5); stale entries from the previous receipt of the *same* name are removed exactly as today.

`sq uninstall-commands --ide codex [--local]` reads the same receipt name and removes the files it lists from `receipt.destination`, pruning emptied skill directories. It never removes a directory that still holds anything.

### State Management

Receipts under `~/.config/squadron/receipts/` remain the only authority for what squadron owns. The name is `delivery.receipt_base` plus `-local` for project-local scope, giving four: `squadron-commands` (Claude machine, the existing name), `squadron-commands-local`, `squadron-commands-agents`, `squadron-commands-agents-local`. Each records its own `destination`, so a local install in one project does not let uninstall in another remove files it did not write.

## Technical Decisions

### Technology Choices

**D1 — Adopt Context Forge's target vocabulary verbatim.** `claude`, `agents`; aliases `codex`→`agents`, `openai`→`agents`. `cf`'s `ideTargets.ts` also has `copilot`/`cursor` for `setup-ide`, but its `install-commands` rejects them — there is no command-delivery mechanism. Squadron's enum has only the two deliverable members; a `copilot` string fails normalization with the same list-of-accepted message an arbitrary typo gets. Rationale: a user who has typed `cf install-commands --ide codex` should not learn a second spelling for `sq`.

**D2 — Machine-level agents root is `~/.agents/skills`, not `~/.codex/skills`.** Codex's own source marks `$CODEX_HOME/skills` "deprecated user skills location, kept for backward compatibility"; the documented user location is `$HOME/.agents/skills` (Codex `host_roots.rs`; docs at learn.chatgpt.com/docs/build-skills). Project-local is `.agents/skills/` relative to cwd, the open agent-skills convention Codex scans from cwd up to repo root. This diverges from `cf`'s slice 924 D2 (`~/.codex/skills`); that is a `cf` defect to raise on the `cf` repo, not a reason to install into a deprecated path here.

**D3 — Second checked-in asset tree, not generated.** Codex skills receive no argument substitution: the user's message is sent verbatim and the `SKILL.md` body is appended as a `<skill>` block in the same turn (Codex `skills.rs` test suite, `fragments.rs`). Every `commands/sq/*.md` that says "the first word of `$ARGUMENTS`" must instead say "the first word the user typed after `$sq-review`". That is authoring, not transformation — the same conclusion `cf` reached (its `commands/codex/cf-*/SKILL.md` contain no `$ARGUMENTS`; cf-set says "using the field and value the user supplied. If either is missing, ask for it — do not guess"). Squadron's commands use no `` !`cmd` `` output injection, so unlike `cf` no passthrough needs rewriting as a "run this and print verbatim" step; the delta per file is frontmatter, the argument sentence, and the invocation name.

**D4 — Skill naming `sq-<name>` and `analysis-<name>`, directory == `name`.** Codex only requires `name` non-empty and ≤64 chars, but the agentskills.io spec requires lowercase `a-z0-9-` and that `name` match the parent directory; `sq-review/SKILL.md` with `name: sq-review` satisfies both and the `$` mention tokenizer. The subdirectory prefix keeps the Claude `/sq:x` ↔ agents `$sq-x` correspondence legible and keeps `analysis` skills from colliding with a user's own.

**D5 — Per-target receipts by name, no schema change.** `pack_name` already keys the receipt file. Claude machine keeps `squadron-commands` so every receipt written since #65 still reads and still governs stale removal; the other three combinations get suffixed names. Alternative rejected: adding `target`/`scope` fields to `InstallReceipt` — forces a read-compat path for a field old receipts lack, to express something the filename already can.

**D6 — Uninstall removes from `receipt.destination`.** Today's uninstall computes `target_dir / relative` from the flag, ignoring the destination the receipt recorded. With `--local` the two can differ (uninstall run from a different directory). The receipt's destination is the truth about where files went; `--target` on uninstall becomes a check rather than a source of paths. When the check fails — `--target` given and it differs from `receipt.destination` — uninstall exits 1 with both paths in the message and removes nothing; it does not proceed from either path. Without `--target`, the receipt's destination is used and the resolved default is not consulted. For the default path this changes nothing.

**D8 — No bundle move; the agents tree is a sibling.** The first draft moved `commands/{sq,analysis}/` under `commands/claude/`. Review found two more resolvers of `commands/analysis/` by name: `skills/resolver.py::_resolve_bundled` (behind `sq skills install analysis`, via the shipped `skills.toml` `source = "bundled"`) and `metrology/audit.py::resolve_audit_skill` (behind `sq metrology audit run`), plus their tests. Moving the tree would have broken both. Instead `commands/sq/` and `commands/analysis/` stay where they are, `commands/agents/` is added beside them, and each `TargetDelivery` names its bundle subdirectories explicitly. Nothing that resolves the Claude tree today changes.

**D9 — `--ide` on `sq setup` lands in `run_all_checks(ide=...)`; the commands check is single-result per target.** `setup_steps.py` types a step's recheck as `Callable[[], CheckResult]`, and five tables key on the check name — four in `setup_steps.py` (`_RECHECK_MAP`, `DOCS_ANCHOR`, `_EXPLANATION`, `_TITLE_MAP`) and `_INSTALLERS` in `setup_install.py` — so a list-returning check would not fit the step machinery. Therefore: `check_commands_installed(target: CommandTarget) -> CheckResult`, whose `name` comes from the delivery (`slash commands` for Claude, `codex skills` for agents). `run_all_checks(*, git_hooks_path, ide: CommandTarget | None = None)`: with `None` (doctor) it emits the Claude row always and the agents row when `check_codex_cli()` is OK; with a target (setup) it emits only that target's row, so `sq setup --ide codex` never offers to install Claude commands. Both of setup's `run_all_checks` calls pass the flag. The five tables gain `codex skills` entries — recheck is `functools.partial(check_commands_installed, CommandTarget.AGENTS)`, installer is `_install_sq_commands(CommandTarget.AGENTS)`. (That these tables key on the user-visible check name predates this slice and is a smell; not changed here.)

**D7 — `disable-model-invocation: true` maps to `agents/openai.yaml` `policy.allow_implicit_invocation: false`.** The two `analysis/` files carry the Claude flag. Codex's equivalent lives in a sibling YAML, not in `SKILL.md` frontmatter. Skills without the flag ship `SKILL.md` alone.

*Amended 20260922 (implementation).* The key was confirmed against primary sources rather than the docs page: OpenAI's own `skill-creator` reference (`references/openai_yaml.md`), Codex's plugin validator (`validate_plugin.py`, which permits `allow_implicit_invocation` as the sole `policy` key and requires a boolean), shipped examples under `~/.codex/plugins/`, and an OpenAI test asserting the exact bytes `policy:\n  allow_implicit_invocation: false\n`. The path `<skill-dir>/agents/openai.yaml` is confirmed.

One thing the design did not know: OpenAI's own Claude-Code migration guide (`migrate-to-codex/references/differences.md`) lists `disable-model-invocation` as having **no direct equivalent** in Codex, and maps `allow_implicit_invocation` to Claude's `user-invocable` instead, calling it "similar intent, not equivalent semantics". The difference is where the skill lives: Claude's flag keeps the skill in context but forbids the model invoking it, while `allow_implicit_invocation: false` keeps it out of model context entirely, still reachable as `$analysis-<name>`. For these two skills that is the desired outcome and cheaper besides — both are heavyweight, explicitly-invoked audits whose own descriptions say "Does not auto-invoke". The mapping stands; the semantic gap is recorded here so a future skill that depends on *being in context while not self-invoking* is not ported by assuming this key does that.

### Patterns and Conventions

- `CommandTarget(StrEnum)`; `TARGET_ALIASES: dict[str, CommandTarget]`; `normalize_target(raw: str) -> CommandTarget` trims and lowercases, checks members then aliases, raises with the accepted list. Nothing else in the codebase compares a target string.
- `TargetDelivery` is a frozen dataclass; `DELIVERIES: dict[CommandTarget, TargetDelivery]` with a module-level assertion that its keys equal the enum — the closest Python gets to `cf`'s compiler-enforced exhaustive `Record<Target, …>`.
- Layout writers are two small functions with one signature `(source: Path, destination: Path) -> list[str]`; the delivery holds a reference. No class hierarchy for two cases.
- Doctor check names: `slash commands` (unchanged, Claude) and `codex skills` (agents), both `required=False`, `section=SECTION_INSTALL`; fix hints `sq install-commands` and `sq install-commands --ide codex`. The name lives on the `TargetDelivery`, so the check, the step tables, and the tests all read it from one place.
- The drift test reads both trees from the bundle source and asserts a bijection: `commands/<sub>/<name>.md` ↔ `commands/agents/<sub>-<name>/SKILL.md` for each Claude subdirectory, and that each agents `name:` equals its directory.

## Implementation Details

### Migration Plan

Nothing moves (D8). The one behavioral migration is in `install.py`: the Claude delivery lists `("sq", "analysis")` instead of walking every subdirectory of `commands/`, so that `commands/agents/` is not copied into `~/.claude/commands/`. A test runs the pre-slice and post-slice default install into `tmp_path` and asserts identical file sets and receipt contents. Architecture amendments: `340-arch.skill-pack-infrastructure.md` ("This is the only install path") and `360-arch.document-intelligence.md` ("adding a file to `commands/sq/` is its registration") each get a dated amendment line pointing here.

### API Contracts

```
sq install-commands   [--ide {claude|agents|codex|openai}] [--local] [--target DIR] [--receipts-dir DIR]
sq uninstall-commands [--ide {claude|agents|codex|openai}] [--local] [--target DIR] [--receipts-dir DIR]
sq setup              ... [--ide {claude|agents|codex|openai}]
```

`--ide` default `claude`. On install, `--local` and `--target` together: `--target` wins and `--local` is reported as ignored (not silently). On uninstall, `--target` is verified against the receipt's recorded destination and a mismatch is an error (D6). Unknown `--ide` exits 2 with `typer.BadParameter` naming the accepted values.

### Database / Storage Schema

Agents-target file layout written:

```
<root>/sq-review/SKILL.md
<root>/sq-run/SKILL.md
…
<root>/analysis-tech-debt-audit/SKILL.md
<root>/analysis-tech-debt-audit/agents/openai.yaml
<root>/analysis-understand/SKILL.md
<root>/analysis-understand/agents/openai.yaml
```

`SKILL.md` frontmatter: `name` (== directory), `description` (one sentence; ends with when to use it, as Codex surfaces descriptions to the model for selection). Body: the Claude command's steps with `$ARGUMENTS` prose replaced per D3.

## Integration Points

### Provides to Other Slices

- `squadron.skills.targets.CommandTarget`, `normalize_target`, `DELIVERIES` — for the follow-up skill-pack targeting work and any future IDE-aware command.
- The `commands/agents/` tree and its drift test — adding a new `/sq:*` command now fails CI until its agents twin exists.

### Consumes from Other Slices

- Receipts (#65, slice 922). If a receipt is malformed the existing `ValueError` → exit 1 path is unchanged.
- `check_codex_cli()`: when Codex is absent the agents doctor check is not emitted at all (not WARN), so a Claude-only user sees no new noise.

## Success Criteria

### Functional Requirements

- `sq install-commands --ide codex` writes every skill directory under `~/.agents/skills/`, prints the list, and writes `squadron-commands-agents.toml`. `--ide agents` and `--ide openai` do the same. `--local` writes under `./.agents/skills/`.
- `sq uninstall-commands --ide codex` removes exactly the listed files, prunes emptied skill directories, leaves anything else in `~/.agents/skills/` untouched, and deletes its receipt.
- `sq install-commands` (no flags) is unchanged in files, paths, receipt name, and output.
- `sq install-commands --ide copilot` and `--ide nonsense` fail with the same message listing the accepted values.
- `sq doctor` shows `codex skills` only when the Codex binary is detected; `OK` with a count when installed, `WARN` with the fix hint when not.
- `sq setup --ide codex` installs the agents commands in place of the Claude ones and its slash-commands step reports against the agents root.
- In a live Codex session in a project, typing `$sq-` offers the installed skills; `$sq-review code 925` runs `sq review code 925 -v` and displays the result.

### Technical Requirements

- Zero pyright errors; ruff format/check clean.
- Tests: normalization table (members, aliases, case/whitespace, rejects); per-target install/uninstall into `tmp_path`; receipt isolation between targets and scopes; uninstall-from-receipt-destination (D6); unchanged Claude default; drift bijection; doctor emits/omits the agents check based on a stubbed `shutil.which` (per #47, never the host PATH).
- CHANGELOG `[Unreleased]` → `### Added`; QUICKSTART and README install sections mention `--ide codex`.

### Integration Requirements

- `sq setup` end-to-end on a machine with Codex and without Claude Code produces a working `$sq-*` set.
- `sq skills install analysis` and `sq metrology audit run` resolve the analysis pack exactly as before (D8); their existing tests pass unmodified.
- A follow-up issue is filed for `sq skills install --ide`, citing `CommandTarget`.
- A `cf` issue is filed noting `~/.codex/skills` is deprecated upstream (D2).
- 340-arch and 360-arch carry their amendment lines.

### Verification Walkthrough

*Verified 20260922 during implementation. Steps 1–5 and 8–9 were run against a throwaway
`HOME` (`export H=$(mktemp -d)` then `HOME=$H sq …`) so nothing touched the developer's own
install; run them the same way. Output below is what the commands actually print, with paths
shortened to `$H`. Two predictions in the original draft were wrong and are corrected in place —
see the notes on steps 3 and 4.*

1. **Baseline unchanged.**
   `sq install-commands` → `Installed 12 command(s) to $H/.claude/commands:` with the same `sq/…`, `analysis/…` list as before the slice. `ls $H/.config/squadron/receipts/` → `squadron-commands.toml`.

2. **Install for Codex.**
   `sq install-commands --ide codex` → `Installed 14 command(s) to $H/.agents/skills:` listing `analysis-tech-debt-audit/SKILL.md`, `analysis-tech-debt-audit/agents/openai.yaml`, … through `sq-task/SKILL.md`. `ls $H/.agents/skills/` shows twelve directories: `analysis-tech-debt-audit`, `analysis-understand`, and ten `sq-*`. `ls $H/.config/squadron/receipts/` now has `squadron-commands-agents.toml` beside the Claude receipt.

3. **Aliases and rejects.**
   `sq install-commands --ide openai` reinstalls the same 14 files and reports no stale removals (idempotent). `sq install-commands --ide copilot` → exit 2:
   ```
   Invalid value: Unknown install target 'copilot'. Accepted: agents, claude, codex, openai.
   ```
   *Correction:* the design predicted `'copilot' is not one of claude, agents (aliases: codex, openai)`. The message comes from `normalize_target`'s `ValueError` wrapped in `typer.BadParameter`, so it lists every accepted spelling flat rather than separating members from aliases. Same exit code, same information.

4. **Doctor sees it.**
   With the agents install present, `sq doctor` → `✓ codex skills  12 command(s) at $H/.agents/skills`. After `sq uninstall-commands --ide codex`, the WARN state needs **`sq doctor -v`**:
   ```
   ! codex skills                not installed at $H/.agents/skills
     fix: sq install-commands --ide codex
   ```
   *Correction:* the design expected the WARN row from a bare `sq doctor`. It is not shown there — `doctor.py:64` hides every WARN row unless `--verbose`, which predates this slice and applies to all optional checks. The row and its fix hint are correct; only the flag was missing from the walkthrough. The Claude `slash commands` line is unaffected either way.

   Note the agents row appears at all only when the Codex CLI is on `PATH` (D9). On a Claude-only machine the row set is exactly what it was before this slice.

5. **Project-local.**
   From a project root: `sq install-commands --ide codex --local` → 14 files under `./.agents/skills/`, receipt `squadron-commands-agents-local.toml` whose `destination` is that absolute path. `cd` elsewhere, `sq uninstall-commands --ide codex --local` → `Removed 14 command(s) from <the project path>`, and the project's `.agents/skills/` is empty. This is D6: the removal follows the receipt, not the new cwd.

6. **Live in Codex.**
   In a squadron project with Codex CLI: type `$sq-` — the completer lists `sq-review`, `sq-run`, `sq-summary`, …. Send `$sq-review code 925`. Codex runs `sq review code 925 -v` and shows the review. Send `$sq-auth` → runs `sq auth status`.

7. **Setup path.** *Verified 20260922.*
   On a fresh `HOME`, run setup **interactively and with `-v`** — `printf '\n' | HOME=$H sq setup --ide codex -v`:
   ```
   ! Step 2/19 — Install Codex skills
   [Enter] to install, 's' to skip, 'q' to quit:   installing…
     ✓ sq install-commands --ide codex completed.
     ✓ detected — moving on
   ```
   `sq doctor` in the same `HOME` then shows `✓ codex skills  12 command(s) at $H/.agents/skills`, and no `slash commands` row, because `--ide codex` scopes the run to one target.

   *Correction:* the design named `--non-interactive`, which prints every step without running any, so it reports the step but never installs. And `-v` is required: the step is WARN (optional), and `_run_interactive` skips optional steps without it — the same pre-existing convention as `sq doctor`. This is the path that exercises setup's in-process install, which is worth running because a Typer command cannot be called directly from Python (see Implementation Notes).

8. **Drift guard.**
   `pytest tests/cli/test_install_commands.py -k "twin or drift"` → 3 passed. The teeth are asserted by `test_drift_guard_fails_on_a_command_with_no_twin`, which copies the bundle to a tmp directory, adds a command with no twin there, and asserts the guard raises naming the missing path — the real tree is never edited.

9. **Nothing else moved.**
   `sq skills install analysis --commands-dir $(mktemp -d)` → `Installed pack 'analysis': 2 file(s)`. `pytest tests/skills tests/metrology -q` → 403 passed, unchanged. Both prove D8: the analysis pack still resolves by name from `commands/analysis/`.

## Risk Assessment

### Technical Risks

- **Codex skill discovery specifics** (whether project-local shadows a same-named global skill; whether `agents/openai.yaml`'s key is exactly `policy.allow_implicit_invocation`) were read from Codex source and docs at design time, not exercised. The live walkthrough step 6 is the check.
- **Codex has both deprecated (`~/.codex/skills`) and current (`~/.agents/skills`) roots.** A user who also ran `cf install-commands --ide codex` has `cf-*` in one and `sq-*` in the other. Both are scanned; nothing breaks, but it is untidy until `cf` moves.

### Mitigation Strategies

- Step 6 of the walkthrough runs before the slice is marked complete; if Codex ignores `agents/openai.yaml` the `analysis-*` skills simply become implicitly invocable, which is the pre-slice Claude behavior for any command without the flag — degraded, not broken.
- File the `cf` issue for D2 during this slice so the two tools converge.

## Implementation Notes

### Development Approach

1. `targets.py` with tests (pure, no I/O).
2. Thread `TargetDelivery` through `install.py` with the Claude delivery only; the existing install tests must pass with no behavioral change before any new flag exists.
3. Add `--ide`/`--local`; per-target receipts; D6. Tests for each.
4. Author `commands/agents/` — twelve skills, prose argument handling per D3, `openai.yaml` for the two `analysis` skills. Drift test.
5. Doctor and setup per D9. Stub `shutil.which` in tests.
6. Docs, CHANGELOG, arch amendment lines, live walkthrough under Codex, file the two follow-up issues.

### Special Considerations

- The agents-tree authoring is the effort center, not the Python. Each `SKILL.md` must be checked against its Claude twin for every step — the drift test proves existence, not equivalence.
- `description` frontmatter is how Codex decides whether to suggest a skill; write it as "what it does + when the user would ask for it", per the pattern `cf` used (`Use when the user asks for cf status or where the project stands.`).
- No test may touch the real `~/.agents/skills` or `~/.config/squadron/receipts` — extend `test_no_test_touches_the_real_receipts_directory` to the new root.

### Found During Implementation (20260922)

**A Typer command is not a callable.** `setup_install._install_sq_commands` called `install_commands()` directly from Python. That worked while every parameter had a plain default, but adding `--ide` as a `typer.Option` meant an unsupplied argument arrived as an `OptionInfo` object, and `normalize_target` raised `AttributeError` on it — `sq setup`'s install action was broken for one task. Every CLI-driven test still passed, because they invoke through the command line where Typer fills the defaults. Resolved by extracting `install_for_target()`, a plain keyword-only function holding the command body, which both `install_commands` and setup call. Any future flag added to a Typer command with in-process callers has this shape.

**A stale mock target is a live write.** The two tests covering that in-process path patched `squadron.cli.commands.install.install_commands` by name. When that stopped being the function setup calls, the patch silently stopped intercepting and the test installed into the developer's real `~/.claude/commands`. `patch` raises on a missing attribute, but the module still had *an* install entry point, so the failure mode was a live write rather than an error — the #47 shape, from a direction the receipts-directory guard does not cover. Both patches were repointed and `test_the_patched_installer_name_still_exists` added.

**Two walkthrough predictions were wrong**, both because the design assumed output rather than running the command: the `--ide` rejection message wording, and that a bare `sq doctor` / `sq setup --non-interactive` would surface the WARN-level agents row. Corrected in place in the Verification Walkthrough above. The underlying behavior was right in both cases; only the expected text was wrong. Worth noting that WARN rows hiding without `-v` is pre-existing and applies to every optional check, not something this slice introduced.
