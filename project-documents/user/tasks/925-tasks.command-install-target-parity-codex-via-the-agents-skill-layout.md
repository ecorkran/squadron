---
docType: tasks
slice: command-install-target-parity-codex-via-the-agents-skill-layout
project: squadron
lld: user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md
dependencies: []
projectState: >
  Slice design approved after review (CONCERNS resolved, commit 2f52d4e2). No code
  written yet. `sq install-commands` installs only to ~/.claude/commands.
dateCreated: 20260922
dateUpdated: 20260922
status: not_started
---

## Context Summary

- Working on the **925 command-install-target-parity** slice: `sq install-commands` gains an
  `--ide` target so squadron's commands can be installed for Codex, not just Claude Code.
- **Current state:** `install.py` hardcodes `~/.claude/commands` and walks every subdirectory
  of the bundled `commands/`. Receipts (slice 922, #65) already govern what uninstall removes.
- **Delivers:** a `CommandTarget` vocabulary matching Context Forge's (`claude`, `agents`,
  aliases `codex`/`openai`), a sibling `commands/agents/` asset tree in Codex's skill-directory
  layout, per-target receipts, and `--ide` on `install-commands`/`uninstall-commands`/`setup`.
- **Key constraints:**
  - Nothing in `commands/` moves (D8). `skills/resolver.py` and `metrology/audit.py` resolve
    `commands/analysis/` by pack name and must keep working untouched.
  - A bare `sq install-commands` must stay byte-for-byte identical in files, paths, receipt
    name and output.
  - Codex skills get **no** argument substitution — each agents `SKILL.md` is authored, not
    generated (D3).
- **Next planned slice:** 923 (test suite machine-state isolation) or 914, per the 900 plan.

---

## Task 1 — Target vocabulary and delivery table

- [ ] Create `src/squadron/skills/targets.py` with the target vocabulary (D1)
  - [ ] `CommandTarget(StrEnum)` with exactly two members: `CLAUDE = "claude"`, `AGENTS = "agents"`
  - [ ] `TARGET_ALIASES: dict[str, CommandTarget]` mapping `"codex"` and `"openai"` to `AGENTS`
  - [ ] `normalize_target(raw: str) -> CommandTarget` — strip and lowercase, check enum members
        first then aliases, raise `ValueError` naming every accepted spelling when neither matches
  - [ ] Success: `normalize_target` accepts `claude`, `agents`, `codex`, `openai` in any case and
        with surrounding whitespace; `copilot`, `cursor`, `""` and arbitrary text all raise
  - [ ] Success: no other module in `src/` compares a target string literal (grep proves it)

- [ ] Add `TargetDelivery` and the `DELIVERIES` table to the same module
  - [ ] Frozen dataclass fields: `machine_root: Path`, `local_root: Path`, `bundle_subdirs: tuple[str, ...]`,
        `check_name: str`, `receipt_base: str`, `layout: Callable[[Path, Path], list[str]]`
  - [ ] Claude entry: machine `~/.claude/commands`, local `.claude/commands`, subdirs `("sq", "analysis")`,
        check name `slash commands`, receipt base `squadron-commands` (D5 — the existing name, unchanged)
  - [ ] Agents entry: machine `~/.agents/skills`, local `.agents/skills`, subdirs `("agents",)`,
        check name `codex skills`, receipt base `squadron-commands-agents` (D2)
  - [ ] `receipt_name(target, local: bool) -> str` — appends `-local` for project-local scope, giving
        the four names in the design's State Management section
  - [ ] Module-level assertion that `DELIVERIES.keys() == set(CommandTarget)` so a new member cannot
        be added without a delivery
  - [ ] Success: `~` is expanded at use, not at import — the module must be importable under a patched
        `HOME` and resolve against it (per #47 / slice 923 isolation discipline)

- [ ] **Test** `tests/skills/test_targets.py`
  - [ ] Parametrized accept cases: every member and alias, mixed case, leading/trailing whitespace
  - [ ] Reject cases: `copilot`, `cursor`, empty string, `claude-code`; assert the message lists the
        accepted values
  - [ ] `DELIVERIES` covers every enum member; the two entries have distinct roots, check names and
        receipt bases
  - [ ] `receipt_name` returns the four expected names, and the Claude machine name is exactly
        `squadron-commands`
  - [ ] Roots resolve under a monkeypatched `HOME`, not the real one
  - [ ] Success: `pytest tests/skills/test_targets.py` passes; `pyright` clean

---

## Task 2 — Thread the delivery through `install.py` (Claude only, no new flags)

This task changes only *how* the existing behavior is produced. No user-visible change.

- [ ] Add the two layout writers to `install.py`, each `(source: Path, destination: Path) -> list[str]`
  - [ ] `_write_flat_markdown` — the current behavior: for each `*.md` directly under `source`,
        copy to `destination/<source.name>/<file>.md`; return paths relative to `destination`
  - [ ] `_write_skill_dirs` — for each directory under `source`, copy the whole directory
        (`SKILL.md` plus any nested files such as `agents/openai.yaml`) to `destination/<dir>/`;
        return paths relative to `destination`
  - [ ] Success: neither writer mentions `.claude` or `.agents`; both create parent directories

- [ ] Rewrite `install_commands` to resolve a `TargetDelivery` and drive it
  - [ ] Hardcode `CommandTarget.CLAUDE` for now (the flag arrives in Task 4)
  - [ ] Iterate `delivery.bundle_subdirs` explicitly instead of walking every directory under the
        bundle source — this is the one behavioral change, and it is what keeps `commands/agents/`
        out of `~/.claude/commands/` once it exists (D8)
  - [ ] Receipt name from `receipt_name(target, local=False)`; stale-removal logic unchanged
  - [ ] Success: `install.py` contains no literal `~/.claude/commands` outside the delivery table
  - [ ] Success: the `--target` option's default is now derived from the delivery, not a literal

- [ ] Apply the same treatment to `uninstall_commands` (receipt name from the delivery; behavior
      otherwise unchanged — D6 arrives in Task 5)

- [ ] **Test** — the existing suite is the test for this task
  - [ ] `pytest tests/cli/test_install_commands.py` passes with **no modifications to the test file**
  - [ ] Add `test_agents_tree_is_not_installed_for_claude`: create a fake bundle with `sq/`,
        `analysis/` and `agents/` subdirectories, install with the Claude default, assert nothing
        from `agents/` is written and it is absent from the receipt
  - [ ] Success: `pytest tests/cli/test_install_commands.py tests/skills tests/metrology` all pass —
        the last two prove D8 (the analysis pack still resolves)

---

## Task 3 — Author the `commands/agents/` asset tree

Twelve skills, one per file under `commands/sq/` (10) and `commands/analysis/` (2). Each is
authored against its Claude twin, not mechanically converted (D3).

- [ ] Confirm the `agents/openai.yaml` key for implicit invocation before authoring (D7)
  - [ ] Check the current Codex skills documentation for the exact key path
        (design records `policy.allow_implicit_invocation: false`)
  - [ ] Success: the key is confirmed against current docs, or — if it cannot be confirmed — the
        task stops and asks the Project Manager rather than guessing

- [ ] Author `commands/agents/sq-<name>/SKILL.md` for each of the ten `commands/sq/*.md` files
  - [ ] One sub-item per file: `analysis`, `auth`, `list`, `pr`, `review`, `run`, `shutdown`,
        `spawn`, `summary`, `task`
  - [ ] Frontmatter: `name` equal to the directory name; `description` one sentence stating what it
        does and when the user would ask for it (Codex selects skills on description)
  - [ ] Body: the Claude command's steps, with every `$ARGUMENTS` reference rewritten as prose
        describing what the user typed after `$sq-<name>` (D3). Preserve each command's CLI
        invocations, flags and output instructions exactly
  - [ ] Where the Claude file tells the model to ask rather than guess a missing value, keep that
        instruction — Codex has no argument slot to fall back on
  - [ ] Success: no `$ARGUMENTS`, `$1`, or `` !`cmd` `` appears anywhere under `commands/agents/`
  - [ ] Success: each file's CLI commands match its Claude twin's (same subcommands and flags)

- [ ] Author `commands/agents/analysis-<name>/` for the two `commands/analysis/*.md` files
  - [ ] `analysis-tech-debt-audit/SKILL.md` and `analysis-understand/SKILL.md`
  - [ ] Each gets a sibling `agents/openai.yaml` disabling implicit invocation, because both Claude
        twins carry `disable-model-invocation: true` (D7)
  - [ ] Success: exactly these two skills have an `openai.yaml`; the ten `sq-*` skills do not

- [ ] **Test** `tests/cli/test_install_commands.py` — add the drift guard
  - [ ] Bijection: for each `commands/<sub>/<name>.md` where sub is a Claude bundle subdir, assert
        `commands/agents/<sub>-<name>/SKILL.md` exists; and for each agents skill dir, assert its
        Claude twin exists. Failure message names the missing path
  - [ ] Every agents `SKILL.md` has `name` frontmatter equal to its directory name, matching
        `^[a-z0-9]+(-[a-z0-9]+)*$`, and a non-empty `description` (D4)
  - [ ] Assert `openai.yaml` presence exactly mirrors `disable-model-invocation: true` in the twin
  - [ ] Assert no `$ARGUMENTS` under `commands/agents/`
  - [ ] Success: the drift test fails when a `commands/sq/*.md` is added with no twin — verify by
        creating one in a tmp copy of the tree, not by editing the real bundle

---

## Task 4 — `--ide` and `--local` on install

- [ ] Add the flags to `install_commands`
  - [ ] `--ide` (default `claude`) parsed through `normalize_target`; on `ValueError` raise
        `typer.BadParameter` so Typer exits 2 with the accepted values in the message
  - [ ] `--local` selects `delivery.local_root` resolved against cwd; otherwise `machine_root`
  - [ ] `--target DIR` still wins over both. When `--target` and `--local` are both given, use
        `--target` and print that `--local` was ignored — never silently (project rule: no silent
        fallbacks)
  - [ ] Receipt name from `receipt_name(target, local)` so the four scopes never share a receipt
  - [ ] Success: `sq install-commands --ide codex` writes skill directories under `~/.agents/skills`
  - [ ] Success: `sq install-commands --ide copilot` exits 2 naming the accepted values

- [ ] Mirror the flags on `uninstall_commands` (resolution only; D6 semantics in Task 5)

- [ ] **Test** `tests/cli/test_install_commands.py`
  - [ ] Agents install into `tmp_path`: every authored skill directory is written, `SKILL.md` and
        `openai.yaml` both land, output lists them, receipt `squadron-commands-agents` written
  - [ ] `--ide codex`, `--ide openai` and `--ide agents` produce identical results
  - [ ] `--ide copilot` and `--ide nonsense` exit 2 with the accepted values in the message
  - [ ] `--local` writes under the cwd-relative root and uses the `-local` receipt name
  - [ ] `--target` with `--local` uses `--target` and says `--local` was ignored
  - [ ] Receipt isolation: install Claude then agents into the same `tmp_path` receipts dir; both
        receipts exist, and uninstalling one leaves the other's files intact
  - [ ] Claude default unchanged: same file set, receipt name and output as before the flag existed
  - [ ] Success: all new and existing tests in the file pass; `pyright` clean

---

## Task 5 — Uninstall from the receipt's destination (D6)

- [ ] Change `uninstall_commands` to remove files from `receipt.destination`
  - [ ] Paths come from `receipt.destination / relative`, not from the resolved flag value
  - [ ] When `--target` is given and differs from `receipt.destination`, exit 1 with both paths in
        the message and remove nothing — do not proceed from either path
  - [ ] Without `--target`, use the receipt's destination and do not consult the resolved default
  - [ ] Keep the existing behavior for a missing receipt (message, nothing removed) and for
        directory pruning (remove a directory only once empty)
  - [ ] Success: the default Claude path behaves exactly as before

- [ ] **Test** `tests/cli/test_install_commands.py`
  - [ ] Install `--local` from directory A, run uninstall `--local` from directory B, assert the
        files under A are removed (the pre-D6 code would have missed them)
  - [ ] `--target` pointing somewhere other than the receipt's destination exits 1, names both
        paths, and leaves every installed file in place
  - [ ] Emptied skill directories are pruned; a directory holding a user's own file is not
  - [ ] Success: existing uninstall tests pass unchanged

---

## Task 6 — Doctor: per-target commands check (D9)

- [ ] Replace `check_slash_commands` with `check_commands_installed(target, root=None)` in
      `doctor_checks.py`
  - [ ] Returns a single `CheckResult` (not a list) — the step machinery in `setup_steps.py` types
        recheck as `Callable[[], CheckResult]`
  - [ ] `name` and `fix_hint` come from the `TargetDelivery` (`slash commands` / `sq install-commands`
        and `codex skills` / `sq install-commands --ide codex`); keep `required=False` and
        `section=SECTION_INSTALL`
  - [ ] Counts installed items: `*.md` for the Claude layout, skill directories for agents
  - [ ] Success: the Claude result is identical in name, status, detail shape and fix hint to today's

- [ ] Add the `ide` parameter to `run_all_checks`
  - [ ] Signature `run_all_checks(*, git_hooks_path: str | None = None, ide: CommandTarget | None = None)`
  - [ ] `ide=None` (doctor): emit the Claude row always, and the agents row only when
        `check_codex_cli()` reports OK — a Claude-only user sees no new row
  - [ ] `ide=<target>` (setup): emit only that target's row
  - [ ] Success: `sq doctor` on a machine without Codex produces exactly today's row set

- [ ] **Test** `tests/cli/test_doctor_checks.py` and `tests/cli/test_doctor.py`
  - [ ] Both targets: OK with a count when installed, WARN with the right fix hint when not —
        against `tmp_path` roots, never the real home
  - [ ] Agents row present when `shutil.which("codex")` is stubbed present, absent when stubbed
        absent. **Stub it** — never read the host `PATH` (#47)
  - [ ] `ide=CommandTarget.AGENTS` yields the agents row and no `slash commands` row
  - [ ] Success: existing doctor tests pass unchanged

---

## Task 7 — Setup: `--ide` threaded end to end (D9)

- [ ] Add `--ide` to `sq setup` and forward it
  - [ ] Parse through `normalize_target`; pass to **both** `run_all_checks` call sites in
        `setup.py` (the interactive pass and the final summary)
  - [ ] `_install_sq_commands(target: CommandTarget)` in `setup_install.py` installs for that target
  - [ ] Success: `sq setup --ide codex` never offers to install Claude commands

- [ ] Register the `codex skills` check name in the five name-keyed tables
  - [ ] Four in `setup_steps.py`: `_RECHECK_MAP`, `DOCS_ANCHOR`, `_EXPLANATION`, `_TITLE_MAP`
  - [ ] One in `setup_install.py`: `_INSTALLERS`
  - [ ] Recheck and installer entries bind the agents target (e.g. via `functools.partial`)
  - [ ] Read the check names from the delivery table rather than retyping the literals
  - [ ] Success: a `codex skills` row in setup renders a title, explanation and docs anchor, and its
        install action runs the agents install

- [ ] **Test** `tests/cli/test_setup.py`, `test_setup_steps.py`, `test_setup_install.py`
  - [ ] `--ide codex` produces a `codex skills` step and no `slash commands` step; default produces
        the reverse
  - [ ] The agents step's recheck returns a `CheckResult` (not a list) and its installer targets the
        agents root
  - [ ] Every check name the tables key on exists in some `run_all_checks` output — guards the
        name-keying smell D9 notes
  - [ ] Stub `shutil.which` throughout (#47)
  - [ ] Success: existing setup tests pass unchanged

---

## Task 8 — Documentation and follow-ups

- [ ] Update user-facing docs
  - [ ] `docs/QUICKSTART.md` install section: `--ide codex` and where skills land
  - [ ] `README.md`: the same, wherever `install-commands` is described
  - [ ] CHANGELOG `[Unreleased]` → `### Added`, one user-facing bullet (no technical detail —
        that belongs in DEVLOG)
  - [ ] Success: neither doc claims `~/.claude/commands` is the only destination

- [ ] File the follow-up issues named in the design's Integration Requirements
  - [ ] squadron issue: `sq skills install --ide`, citing `CommandTarget` and the hardcoded
        `~/.claude/commands` in `skills.py`
  - [ ] context-forge issue: `cf install-commands --ide codex` installs to `~/.codex/skills`, which
        Codex's own source marks deprecated in favor of `~/.agents/skills` (D2)
  - [ ] Success: both issue numbers recorded in the DEVLOG entry

- [ ] Full validation pass
  - [ ] `ruff format`, `ruff check`, `pyright` — zero errors is the merge gate
  - [ ] Full `pytest` run, not just the touched files
  - [ ] Success: green on all four

---

## Task 9 — Live verification under Codex

The design's premises about Codex's runtime behavior were read from source and docs, not
exercised. This task is where they are proven.

- [ ] Run the design's Verification Walkthrough steps 1–5 and 8–9 (CLI-level, no Codex needed)
  - [ ] Success: each step's stated output matches

- [ ] Walkthrough step 6 — live in a Codex session
  - [ ] Install with `--ide codex`, start Codex in a squadron project, type `$sq-` and confirm the
        skills are offered
  - [ ] Run `$sq-review code 925` and confirm it invokes `sq review code 925 -v` and shows the result
  - [ ] Run `$sq-auth` and confirm it runs `sq auth status`
  - [ ] Confirm the two `analysis-*` skills are not implicitly invoked (D7's `openai.yaml`). If Codex
        ignores the file, record the actual behavior — the degraded case is that they become
        implicitly invocable, which matches pre-slice Claude behavior for unflagged commands
  - [ ] Success: argument-bearing invocations work, or the specific failure is recorded with the
        `SKILL.md` wording that caused it

- [ ] Walkthrough step 7 — `sq setup --ide codex` on a fresh `HOME`
  - [ ] Success: the slash-commands step reports the agents install and `sq doctor` in the same
        `HOME` shows `codex skills OK`

- [ ] Record results and close out
  - [ ] Note any divergence between the design's Codex assumptions and observed behavior
  - [ ] Write the DEVLOG entry (Session State Summary format)
  - [ ] Mark the slice complete in the design's frontmatter and in the 900 slice plan entry
  - [ ] Success: DEVLOG entry written, both status markers updated
