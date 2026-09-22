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
status: in_progress
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

- [x] Create `src/squadron/skills/targets.py` with the target vocabulary (D1)
  - [x] `CommandTarget(StrEnum)` with exactly two members: `CLAUDE = "claude"`, `AGENTS = "agents"`
  - [x] `TARGET_ALIASES: dict[str, CommandTarget]` mapping `"codex"` and `"openai"` to `AGENTS`
  - [x] `normalize_target(raw: str) -> CommandTarget` — strip and lowercase, check enum members
        first then aliases, raise `ValueError` naming every accepted spelling when neither matches
  - [x] Success: `normalize_target` accepts `claude`, `agents`, `codex`, `openai` in any case and
        with surrounding whitespace; `copilot`, `cursor`, `""` and arbitrary text all raise
  - [x] Success: no other module in `src/` compares a target string literal (grep proves it)

- [x] Add the two layout writers to `targets.py`, each `(source: Path, destination: Path) -> list[str]`
  - [x] They live here, not in `cli/commands/install.py`: `DELIVERIES` holds references to them, and
        `src/squadron/skills/` must not import from `cli/` — that direction is a cycle (`install.py`
        imports `skills.receipts` today) and inverts the layering the codebase already guards
        (`doctor_checks.py` keeps a local default "to keep the pure check layer free of CLI coupling")
  - [x] `write_flat_markdown` — the current Claude behavior: for each `*.md` directly under `source`,
        copy to `destination/<source.name>/<file>.md`; return paths relative to `destination`
  - [x] `write_skill_dirs` — for each directory under `source`, copy the whole directory (`SKILL.md`
        plus any nested files such as `agents/openai.yaml`) to `destination/<dir>/`; return paths
        relative to `destination`
  - [x] Success: both create parent directories; neither mentions `.claude` or `.agents`; neither
        imports anything from `squadron.cli`

- [x] Add `TargetDelivery` and the `DELIVERIES` table to the same module
  - [x] Frozen dataclass fields: `machine_root: Path`, `local_root: Path`, `bundle_subdirs: tuple[str, ...]`,
        `check_name: str`, `fix_hint: str`, `receipt_base: str`, `layout: Callable[[Path, Path], list[str]]`
  - [x] Claude entry: machine `~/.claude/commands`, local `.claude/commands`, subdirs `("sq", "analysis")`,
        check name `slash commands`, fix hint `sq install-commands`, receipt base `squadron-commands`
        (D5 — the existing name, unchanged), layout `write_flat_markdown`
  - [x] Agents entry: machine `~/.agents/skills`, local `.agents/skills`, subdirs `("agents",)`,
        check name `codex skills`, fix hint `sq install-commands --ide codex`, receipt base
        `squadron-commands-agents` (D2), layout `write_skill_dirs`
  - [x] `receipt_name(target, local: bool) -> str` — `delivery.receipt_base`, plus `-local` when
        `local` is true. The four names are exactly `squadron-commands`, `squadron-commands-local`,
        `squadron-commands-agents`, `squadron-commands-agents-local` (the design's State Management
        section was corrected to match this rule; the earlier `squadron-commands-claude-local` is void)
  - [x] Module-level assertion that `DELIVERIES.keys() == set(CommandTarget)` so a new member cannot
        be added without a delivery
  - [x] Success: `~` is expanded at use, not at import — the module must be importable under a patched
        `HOME` and resolve against it (per #47 / slice 923 isolation discipline)

- [x] **Test** `tests/skills/test_targets.py`
  - [x] Parametrized accept cases: every member and alias, mixed case, leading/trailing whitespace
  - [x] Reject cases: `copilot`, `cursor`, empty string, `claude-code`; assert the message lists the
        accepted values
  - [x] `DELIVERIES` covers every enum member; the two entries have distinct roots, check names and
        receipt bases
  - [x] `receipt_name` returns exactly the four names listed above, and the Claude machine name is
        exactly `squadron-commands`
  - [x] Roots resolve under a monkeypatched `HOME`, not the real one
  - [x] Both layout writers against `tmp_path` fixtures: flat markdown produces `<sub>/<name>.md`,
        skill dirs copy nested files (`agents/openai.yaml`), both return destination-relative paths
  - [x] Success: `pytest tests/skills/test_targets.py` passes; `pyright` clean
  - [x] Commit: `feat: add command target vocabulary and delivery table`

---

## Task 2 — Thread the delivery through `install.py` (Claude only, no new flags)

This task changes only *how* the existing behavior is produced. No user-visible change.

- [x] Rewrite `install_commands` to resolve a `TargetDelivery` and drive it
  - [x] `install.py` imports `CommandTarget`, `DELIVERIES`, `receipt_name` and the layout writers
        from `squadron.skills.targets` at module scope — the import goes CLI → skills, never back
  - [x] Hardcode `CommandTarget.CLAUDE` for now (the flag arrives in Task 4)
  - [x] Iterate `delivery.bundle_subdirs` explicitly instead of walking every directory under the
        bundle source — this is the one behavioral change, and it is what keeps `commands/agents/`
        out of `~/.claude/commands/` once it exists (D8)
  - [x] Receipt name from `receipt_name(target, local=False)`; stale-removal logic unchanged
  - [x] Success: `install.py` contains no literal `~/.claude/commands` outside the delivery table
  - [x] Success: the `--target` option's default is now derived from the delivery, not a literal

- [x] Apply the same treatment to `uninstall_commands` (receipt name from the delivery; behavior
      otherwise unchanged — D6 arrives in Task 5)

- [x] **Test** — the existing suite is the test for this task
  - [x] `pytest tests/cli/test_install_commands.py` passes with **no modifications to the test file**
  - [x] Add `test_agents_tree_is_not_installed_for_claude`: create a fake bundle with `sq/`,
        `analysis/` and `agents/` subdirectories, install with the Claude default, assert nothing
        from `agents/` is written and it is absent from the receipt
  - [x] Success: `pytest tests/cli/test_install_commands.py tests/skills tests/metrology` all pass —
        the last two prove D8 (the analysis pack still resolves)
  - [x] Commit: `refactor: drive command install from a target delivery table`

---

## Task 3a — Author the ten `sq-*` agent skills

Ten skills, one per file under `commands/sq/`. Each is authored against its Claude twin, not
mechanically converted (D3). This is the slice's effort center — `review.md` (~277 lines) and
`run.md` (~161) are the largest.

- [x] Author `commands/agents/sq-<name>/SKILL.md`, one sub-item per source file
  - [x] `sq-analysis` ← `commands/sq/analysis.md`
  - [x] `sq-auth` ← `commands/sq/auth.md`
  - [x] `sq-list` ← `commands/sq/list.md`
  - [x] `sq-pr` ← `commands/sq/pr.md`
  - [x] `sq-review` ← `commands/sq/review.md` (largest; subcommand dispatch plus the slice-number
        shorthand must both survive the argument rewrite)
  - [x] `sq-run` ← `commands/sq/run.md` (multi-step pipeline loop)
  - [x] `sq-shutdown` ← `commands/sq/shutdown.md`
  - [x] `sq-spawn` ← `commands/sq/spawn.md`
  - [x] `sq-summary` ← `commands/sq/summary.md` (keep its CRITICAL no-redirect instruction verbatim)
  - [x] `sq-task` ← `commands/sq/task.md`
  - [x] Frontmatter for each: `name` equal to the directory name; `description` one sentence stating
        what it does and when the user would ask for it (Codex selects skills on description)
  - [x] Body: the Claude command's steps, with every `$ARGUMENTS` reference rewritten as prose
        describing what the user typed after `$sq-<name>` (D3). Preserve each command's CLI
        invocations, flags and output instructions exactly
  - [x] Where the Claude file tells the model to ask rather than guess a missing value, keep that
        instruction — Codex has no argument slot to fall back on
  - [x] Success: no `$ARGUMENTS`, `$1`, or `` !`cmd` `` appears in any of the ten files
  - [x] Success: each file's CLI commands match its Claude twin's (same subcommands and flags)
  - [x] Commit: `feat: add sq agent skills for the Codex install target`

---

## Task 3b — Author the two `analysis-*` skills and the drift guard

- [ ] Confirm the `agents/openai.yaml` key for implicit invocation before authoring (D7)
  - [ ] Check the current Codex skills documentation for the exact key path. The design records a
        candidate, but the documentation is the authority
  - [ ] Success: the key is confirmed against current docs, or — if it cannot be confirmed — the
        task stops and asks the Project Manager rather than guessing

- [ ] Author `commands/agents/analysis-<name>/` for the two `commands/analysis/*.md` files
  - [ ] `analysis-tech-debt-audit/SKILL.md` ← `commands/analysis/tech-debt-audit.md`
  - [ ] `analysis-understand/SKILL.md` ← `commands/analysis/understand.md` (~1,260 lines — the
        largest single authoring job in the slice; budget a context session for it alone)
  - [ ] Each gets a sibling `agents/openai.yaml` disabling implicit invocation, because both Claude
        twins carry `disable-model-invocation: true` (D7)
  - [ ] Same frontmatter and argument-rewrite rules as Task 3a
  - [ ] Success: exactly these two skills have an `openai.yaml`; the ten `sq-*` skills do not

- [ ] **Test** `tests/cli/test_install_commands.py` — add the drift guard
  - [ ] Runs after 3b because the bijection asserts both directions and can only hold once both
        halves of the tree exist
  - [ ] Bijection: for each `commands/<sub>/<name>.md` where sub is a Claude bundle subdir, assert
        `commands/agents/<sub>-<name>/SKILL.md` exists; and for each agents skill dir, assert its
        Claude twin exists. Failure message names the missing path
  - [ ] Every agents `SKILL.md` has `name` frontmatter equal to its directory name, matching
        `^[a-z0-9]+(-[a-z0-9]+)*$`, and a non-empty `description` (D4)
  - [ ] Assert `openai.yaml` presence exactly mirrors `disable-model-invocation: true` in the twin
  - [ ] Assert no `$ARGUMENTS` under `commands/agents/`
  - [ ] Success: the drift test fails when a `commands/sq/*.md` is added with no twin — verify by
        creating one in a tmp copy of the tree, not by editing the real bundle
  - [ ] Commit: `feat: add analysis agent skills and the asset-tree drift guard`

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
  - [ ] Extend `test_no_test_touches_the_real_receipts_directory` (`tests/cli/test_install_commands.py:375`)
        to also assert no test writes under the real `~/.agents/skills` — this is exactly where an
        agents install with no `--target` would resolve against the real `HOME` (#47 / slice 923)
  - [ ] Success: all new and existing tests in the file pass; `pyright` clean
  - [ ] Commit: `feat: add --ide and --local to install-commands`

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
  - [ ] Commit: `fix: uninstall commands from the receipt's recorded destination`

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
  - [ ] **Repoint every importer in the same task** — `check_slash_commands` is imported by
        `setup_steps.py:24` and bound in `_RECHECK_MAP:56`, and imported by
        `tests/cli/test_doctor_checks.py:37`. Leaving them for Task 7 breaks `import squadron.cli.app`
        and makes `test_doctor_checks.py` un-collectable. Update the `_RECHECK_MAP` binding to the
        Claude target (Task 7 adds the agents row) and update the test's import and call sites
  - [ ] Success: the Claude result is identical in name, status, detail shape and fix hint to today's
  - [ ] Success: `python -c "import squadron.cli.app"` succeeds at the end of this task

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
  - [ ] Success: `tests/cli/test_doctor.py` passes unchanged (it drives the Typer app and never
        imports the renamed symbol); `test_doctor_checks.py` passes with its import and call sites
        repointed by this task
  - [ ] Commit: `feat: make the doctor commands check per-target`

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
  - [ ] Guard the name-keying smell D9 notes, scoped to the two command check names: assert
        `slash commands` and `codex skills` each appear in a `run_all_checks` output for their
        target and in every table that keys on a check name. Do **not** assert this for all keys —
        `DOCS_ANCHOR` has a pre-existing `anthropic` entry (`setup_steps.py:112`) for a
        user-defined profile that `BUILT_IN_PROFILES` does not contain, so a blanket assertion
        fails on a clean machine for reasons unrelated to this slice. Removing that key is out of
        scope; leave it
  - [ ] Stub `shutil.which` throughout (#47)
  - [ ] Success: existing setup tests pass unchanged
  - [ ] Commit: `feat: thread --ide through sq setup`

---

## Task 8 — Documentation and follow-ups

- [ ] Update user-facing docs
  - [ ] `docs/QUICKSTART.md` install section: `--ide codex` and where skills land
  - [ ] `README.md`: the same, wherever `install-commands` is described
  - [ ] CHANGELOG `[Unreleased]` → `### Added`, one user-facing bullet (no technical detail —
        that belongs in DEVLOG)
  - [ ] Success: neither doc claims `~/.claude/commands` is the only destination

- [ ] Verify the two architecture amendment lines are present and accurate
  - [ ] `project-documents/user/architecture/340-arch.skill-pack-infrastructure.md` — the
        "This is the only install path" statement carries a dated amendment naming the agents target
  - [ ] `project-documents/user/architecture/360-arch.document-intelligence.md` — the
        "adding a file to `commands/sq/` is its registration" statement carries a dated amendment
        naming the required agents twin
  - [ ] Both were written during the design-review response; this item confirms they still match what
        shipped and corrects them if the implementation diverged
  - [ ] Success: both amendments describe the delivered behavior, not the design's intent

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
  - [ ] Commit: `docs: document the Codex install target`

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
  - [ ] Commit: `docs: record slice 925 verification results and close the slice`
