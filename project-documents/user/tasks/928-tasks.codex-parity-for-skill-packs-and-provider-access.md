---
docType: tasks
slice: codex-parity-for-skill-packs-and-provider-access
project: squadron
lld: user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md
dependencies: [925]
projectState: >
  Slice design reviewed (verdict CONCERNS, commit 16194f3e). Findings F001/F002 are
  resolved below with concrete rules the design left ambiguous; F003/F004/F005/F006 are
  addressed as explicit task steps. No code written yet. `sq skills install` writes only
  to ~/.claude/commands; the Codex sandbox rule is undocumented for most `sq` commands.
dateCreated: 20260927
dateUpdated: 20261003
status: in_progress
---

## Context Summary

- Working on the **928 codex-parity** slice: threads `CommandTarget` through `sq skills`
  and documents the Codex sandbox approval rule (see slice design for D1-D12).
- **Review findings folded into these tasks** (928-review, verdict CONCERNS):
  - **F001** (D7 ambiguity): `remove_receipt_files` never removes `receipt.destination`
    itself — that matches `uninstall_commands`'s existing pruning loop exactly. The
    Claude-prefix-directory removal in `skills.py` (today gated on `SurfaceType.PREFIX`)
    stays a separate step in `skills.py`, layered *after* calling the shared routine —
    it does not move into it. Task 1 states this explicitly.
  - **F002** (D8 gap): "pack ships no Codex content" is only ever determined for sources
    `resolve_source` can read without a subprocess (`bundled`, relative, absolute paths).
    `github:` sources skip the classification and get the plain pre-D8 "not installed"
    row — determining their content would mean cloning inside a check that must stay
    pure. Task 6 states this explicitly.
  - **F003** (walkthrough bug): bare `sq doctor` hides WARN rows; Task 13's walkthrough
    step uses `sq doctor -v`.
  - **F004** (missing amendment): Task 11 adds a dated amendment to 340-arch.
  - **F005** (undercount): `sq model list` appears **three times per file, six total**
    (`commands/sq/review.md:60,112,158`; `commands/agents/sq-review/SKILL.md:82,134,180`),
    not "one line each." Task 10 fixes all six.
  - **F006** (hint placement): the new D12 hint section goes immediately after the
    closing `---` of "## Waiting on the command" (or at end-of-file where that section
    is already last), never inside the span `test_long_command_skills_carry_one_waiting_rule`
    extracts. `sq-task` is out of scope for the hint per the design's own success
    criteria — Task 9 notes this rather than silently deviating.
- **Key constraints:** no auto-conversion of Claude packs (D2); no doctor check for the
  rule itself (D11); `sq setup` prints the rule, never writes it (unchanged).
- **Delivers:** `sq skills install|uninstall|list --ide {claude|agents|codex|openai} [--local]`,
  a per-target `PACK_LAYOUTS` table, the agents pack-format validation (D3), doctor rows
  per target, the Codex approval rule in README/QUICKSTART, and the `sq models list` fix.
- **Next planned slice:** per the 900 plan, after 928 closes.

---

## Task 1 — Generalize `receipt_name`; extract `remove_receipt_files` (D5, D7)

Pure refactor first, per the design's own development order — existing tests stay green
throughout.

- [x] In `src/squadron/skills/targets.py`, rename `TargetDelivery.receipt_base` to
      `receipt_suffix`
  - [x] Claude entry: `receipt_suffix = ""`
  - [x] Agents entry: `receipt_suffix = "-agents"`
  - [x] Change `receipt_name` to `receipt_name(base: str, target: CommandTarget, *, local: bool) -> str`
        returning `base + DELIVERIES[target].receipt_suffix + ("-local" if local else "")`
  - [x] Update both call sites in `cli/commands/install.py` (currently
        `receipt_name(command_target, local=...)`) to pass `"squadron-commands"` as `base`
  - [x] Success: the four names produced for `base="squadron-commands"` are byte-identical
        to today's `squadron-commands`, `squadron-commands-local`, `squadron-commands-agents`,
        `squadron-commands-agents-local`

- [x] Extract `remove_receipt_files(receipt: InstallReceipt) -> int` into `skills/receipts.py`
  - [x] Move the containment-check-and-deepest-first-prune loop currently inline in
        `uninstall_commands` (`cli/commands/install.py`, the `removed`/`touched_dirs` block)
        verbatim in behavior: skip entries outside `receipt.destination` with the existing
        warning, unlink existing files, prune emptied directories deepest-first, and **never
        remove `receipt.destination` itself** — this last property is unchanged from today
        and is the F001 resolution above
  - [x] Returns the count of files removed
  - [x] `uninstall_commands` calls `remove_receipt_files(receipt)` instead of the inline loop;
        no behavior change
  - [x] Success: `install.py` no longer contains the prune loop inline

- [x] **Test** `tests/skills/test_receipts.py` and `tests/cli/test_install_commands.py`
  - [x] New `remove_receipt_files` unit tests: nested directories pruned deepest-first, an
        out-of-destination entry is skipped with a warning and not removed, a directory
        holding an unrelated file is not pruned, `receipt.destination` itself is never removed
        even when every recorded file is gone
  - [x] New `receipt_name` unit tests: parametrize `base × target × local` and assert the
        four existing bundled-command names plus at least one pack-name base (e.g.
        `receipt_name("analysis", CommandTarget.AGENTS, local=False) == "analysis-agents"`)
  - [x] Success: `pytest tests/skills/test_receipts.py tests/cli/test_install_commands.py`
        passes with no modification to existing test bodies beyond call-site signature updates
  - [x] Commit: `refactor: generalize receipt_name and extract remove_receipt_files`

---

## Task 2 — Move the analysis agents skills; generalize agents bundle subdirs (D4)

- [x] `git mv commands/agents/analysis-understand commands/analysis/agents/analysis-understand`
- [x] `git mv commands/agents/analysis-tech-debt-audit commands/analysis/agents/analysis-tech-debt-audit`
- [x] In `targets.py`, change the AGENTS `TargetDelivery.bundle_subdirs` from `("agents",)`
      to `("agents", "analysis/agents")`
- [x] Change `bundled_skill_names` to iterate `DELIVERIES[CommandTarget.AGENTS].bundle_subdirs`
      (resolved against the given source root) instead of hardcoding `source / "agents"`
- [x] Update fixture paths in `tests/cli/test_install_commands.py` and
      `tests/skills/test_targets.py` that reference the old `commands/agents/analysis-*` location
- [x] Success: `commands/analysis/` still resolves for `resolve_source("bundled", "analysis")` —
      nothing else reads it recursively, so no other consumer changes

- [x] **Test** — confirms slice criterion 7 (install-commands unaffected by the move)
  - [x] `pytest tests/cli/test_install_commands.py tests/skills tests/metrology` all pass
  - [x] `sq install-commands --ide codex` against a `tmp_path` HOME writes both
        `analysis-understand/` and `analysis-tech-debt-audit/` at the destination root,
        identical to the pre-move paths
  - [x] Success: no test reads `commands/agents/analysis-*` (grep confirms)
  - [x] Commit: `refactor: move analysis agents skills under commands/analysis/agents`

---

## Task 3 — `PackLayout` and `PACK_LAYOUTS`; lift the Claude layout (D6)

- [x] Create `src/squadron/skills/pack_layouts.py`
  - [x] `PackLayout` frozen dataclass: `install: Callable[[str, PackEntry, Path, Path], InstallResult]`,
        `installed_path: Callable[[PackEntry, Path], Path | None]`
  - [x] `PACK_LAYOUTS: dict[CommandTarget, PackLayout]` with a module-level assertion
        `set(PACK_LAYOUTS) == set(CommandTarget)`, matching the `DELIVERIES` pattern
  - [x] Claude `installed_path`: prefix surface → `root / entry.prefix` if it exists and is
        non-empty, else `None`; dispatch_file surface → `root / "sq" / f"{entry.dispatch_file}.md"`
        if it exists, else `None` (D6's table, Claude column)
- [x] Move `_install_prefix` and `_install_dispatch` from `installer.py` into the Claude
      `PackLayout.install`, unchanged in behavior
- [x] `installer.install_pack` gains `target: CommandTarget = CommandTarget.CLAUDE`; after
      resolving the source exactly as today, dispatches to `PACK_LAYOUTS[target].install`
  - [x] Success: `install_pack`'s Claude-target behavior (files written, receipt, exceptions)
        is identical to today's for every existing caller

- [x] **Test** `tests/skills/test_installer.py`, new `tests/skills/test_pack_layouts.py`
  - [x] Existing installer tests pass with no changes beyond the new `target` parameter
        defaulting correctly when omitted
  - [x] `PACK_LAYOUTS` exhaustiveness assertion is exercised (both members present)
  - [x] Claude `installed_path`: parametrized over prefix (empty dir → `None`, non-empty → path)
        and dispatch_file (missing file → `None`, present → path)
  - [x] Success: `pytest tests/skills` passes; `pyright` clean
  - [x] Commit: `refactor: add PACK_LAYOUTS table, lift Claude layout from installer`

---

## Task 4 — Agents `PackLayout`: install and D3 validation

- [x] Implement the agents `PackLayout.install`
  - [x] `agents_dir = source / "agents"`; if missing, raise `SkillSourceError`:
        `Pack '{pack_name}' has no agents/ directory at {source}; it ships no Codex content. Install it for Claude with --ide claude.`
        Nothing is written.
  - [x] Validate every directory under `agents_dir` per D3, collecting **all** violations
        before raising (do not stop at the first):
        - prefix pack: every directory name matches `^{prefix}-[a-z0-9-]+$` (and overall `^[a-z0-9-]+$`)
        - dispatch_file pack: `agents/` holds exactly one directory, named `sq-{dispatch_file}`
        - each skill directory has a `SKILL.md` with YAML frontmatter: `name` equal to the
          directory name, and a non-empty `description`
        - `agents/` present but containing no skill directories is itself a violation (not an
          empty, successful install)
  - [x] On any violation, raise `SkillSourceError` listing every problem found, one per line;
        write nothing
  - [x] On success, call `write_skill_dirs(agents_dir, root)` (from `targets.py`) and build the
        `InstallResult`
  - [x] Agents `installed_path` (D6 table, Agents column): prefix surface → first
        `root / f"{entry.prefix}-*"` directory containing a `SKILL.md`, else `None`;
        dispatch_file surface → `root / f"sq-{entry.dispatch_file}" / "SKILL.md"` if present,
        else `None`

- [x] **Test** `tests/skills/test_pack_layouts.py`
  - [x] No `agents/` directory → the exact D2 message, nothing written (assert the
        destination tree is untouched)
  - [x] Each D3 rule individually: wrong prefix naming, wrong dispatch_file directory name,
        missing/mismatched `name` frontmatter, empty `description`, empty `agents/`
  - [x] Multiple simultaneous violations → all appear in the one raised message
  - [x] Successful install: every skill directory (including nested files like
        `agents/openai.yaml`) lands under `root`, `InstallResult.files_written` lists them
  - [x] Agents `installed_path` parametrized the same way as Claude's in Task 3
  - [x] Success: reproduces walkthrough steps 3 and 4 from the slice design's Verification
        Walkthrough exactly (no `agents/` → refuses; misnamed skill → refuses with all
        problems listed; corrected → installs)
  - [x] Commit: `feat: add agents pack layout with D3 validation`

---

## Task 5 — `--ide`/`--local` on `sq skills install|uninstall|list` (D1)

- [x] `skills install`: add `--ide` (default `claude`, through `normalize_target`, raising
      `typer.BadParameter` on failure) and `--local`
  - [x] Root resolution: `DELIVERIES[target].resolve_root(local=local)`; `--commands-dir`
        still wins over both, and when given together with `--local`, print the same
        "ignored" warning `install-commands` prints — never silently
  - [x] Pass `target` to `install_pack`; receipt written as
        `receipt_name(pack_name, target, local=local_honored)`
- [x] `skills list`: same `--ide`/`--local` flags; status comes from
      `PACK_LAYOUTS[target].installed_path(entry, root)`, replacing the inline prefix/dispatch
      existence checks
- [x] `skills uninstall`: same flags for receipt lookup — `receipt_name(pack_name, target, local)`;
      replace the current flat `unlink` loop with `remove_receipt_files(receipt)` (Task 1),
      then keep the existing `SurfaceType.PREFIX` destination-removal as a separate step
      immediately after (F001 — this step is unchanged from today, just now sequenced after
      the shared routine instead of interleaved with it)

- [x] **Test** `tests/skills/test_cli_skills.py`
  - [x] Reproduces walkthrough steps 1, 2 and 5 from the slice design: bundled `analysis`
        pack installs under `--ide codex` to `~/.agents/skills/` with receipt
        `analysis-agents.toml`; `--local` writes under `./.agents/skills/` with
        `analysis-agents-local.toml`; the Claude path is unchanged
  - [x] `skills list --ide codex` shows correct installed/not-installed status;
        `skills list` (no flags) output is byte-identical to before this task
  - [x] Uninstall removes exactly the receipt's files and prunes emptied nested skill
        directories, never `~/.agents/skills` itself and never a file the receipt doesn't name
        (create an unrelated file first and assert it survives — walkthrough step 5)
  - [x] No-flag `skills install/uninstall/list` behavior is unchanged (criterion 6); a
        pre-existing `analysis.toml` receipt (pre-928 shape) still uninstalls correctly
  - [x] Success: all new and existing tests in the file pass; `pyright` clean
  - [x] Commit: `feat: add --ide and --local to sq skills install/uninstall/list`

---

## Task 6 — Doctor: per-target skill-pack rows (D8)

- [x] Change `check_skill_packs` to loop `_command_targets_to_check(None)` (explicitly
      `None`, not the caller's `ide` — D8's stated rule: skill-pack rows show every
      applicable target regardless of which target `sq setup` is currently targeting)
  - [x] Claude rows: name and hint unchanged from today
  - [x] Agents rows: named `f"{name} (codex)"`, hint `f"sq skills install {name} --ide codex"`
  - [x] Status via `PACK_LAYOUTS[target].installed_path(entry, root)` where `root` is
        `DELIVERIES[target].check_root()`
  - [x] **F002 resolution — apply literally, do not extend it:** the "ships no Codex
        content" classification (WARN with no install hint, distinct from plain
        "not installed") applies **only** when `entry.source` is resolvable by
        `resolve_source` without cloning — i.e. `"bundled"`, and paths starting with
        `./`, `../`, or absolute. For `entry.source.startswith("github:")`, skip the
        content classification entirely and emit the pre-D8 plain "not installed" row
        with the normal install hint — determining Codex content there would require
        `clone_github` (subprocess + network), which this check must not perform
  - [x] For non-github sources: call `resolve_source(entry, name)` inside a `try`; on
        `SkillSourceError` (source itself unreadable), fall through to the plain
        "not installed" row rather than a content-specific one — that is a different,
        pre-existing failure mode, not new to this task
  - [x] On successful resolution, check `bundled_agents_dir = source / "agents"`: if
        absent, the WARN is `pack ships no Codex content` with no `fix_hint`; if present,
        proceed with the normal installed/not-installed check via `installed_path`

- [x] **Test** `tests/cli/test_doctor_checks.py`
  - [x] Table-driven over `{bundled, local dir, github}` × `{agents/ present, agents/
        absent, not installed at all}` for the agents row; Claude row behavior unchanged
        in every case
  - [x] A `github:` pack never triggers a clone — assert by monkeypatching
        `clone_github` to raise if called, then confirming the check still returns a
        plain "not installed" agents row with the ordinary install hint
  - [x] Success: `pytest tests/cli/test_doctor_checks.py tests/cli/test_doctor.py` passes;
        no test reaches the network or a real git clone
  - [x] Commit: `feat: report skill-pack status per target in sq doctor`

---

## Task 7 — Sandbox probe from a real terminal (D10)

Not code — evidence-gathering. Requires the Codex CLI on the verification machine (a
stated slice prerequisite) and a terminal outside any Codex session, per the design's
Special Considerations (a probe run from inside Codex measures the outer sandbox).

- [ ] Carry forward the design's already-confirmed rows unchanged: `sq --version`,
      `sq models list`, `sq auth status` (ran, no rule needed); `sq pr show 1`
      (`HostUnreachableError`, needs the rule)
- [ ] Probe and record a concrete result for every row the design marks "confirm by
      probe" or "unprobed":
  - [ ] `sq review …`, `sq run …`, `sq metrology …` under `codex sandbox --`
  - [ ] `sq skills install <pack-with-github-source>` under `codex sandbox --`
  - [ ] With `sq serve` running in a separate terminal: `sq spawn`, `sq task`,
        `sq message`, `sq list`, `sq history`, `sq shutdown` under `codex sandbox --`
  - [ ] `sq auth login` under `codex sandbox --`
- [ ] Success: every row in D10's table has an observed result (ran / blocked with the
      specific error), not a "probe" placeholder; the final subcommand list for D9's rule
      is written down for Task 8
- [ ] If any daemon-client command (`sq spawn`/`task`/`message`/`list`/`history`/`shutdown`)
      needs the rule, note it for Task 8's README correction (the "fine to invoke
      directly" sentence) and for Task 9's scope note on `sq-task`
- [ ] Record the full probe table for the DEVLOG entry (Task 13)

---

## Task 8 — Codex approval rule in README and QUICKSTART (D9)

- [ ] Replace README's existing `default.rules` snippet (currently a single
      `prefix_rule(pattern = ["sq", "review"], decision = "allow")` block) with the
      `~/.codex/rules/squadron.rules` rule from D9, using Task 7's confirmed subcommand
      list as `pattern`'s alternatives and one `match` example per subcommand
  - [ ] State in the same paragraph as the snippet — not a footnote — that a matching
        rule runs the command outside Codex's sandbox with no prompt: network **and**
        unrestricted filesystem
  - [ ] Name the `decision = "prompt"` alternative and `<project>/.codex/rules/` for a
        per-project rule
  - [ ] Name that a command using redirection, an env-var prefix, or a glob never
        matches a rule
  - [ ] If Task 7 found a daemon-client command needs the rule, correct the "fine to
        invoke directly" sentence about those commands in the same edit
- [ ] Add the equivalent section to `docs/QUICKSTART.md`'s Codex section
- [ ] Success: both docs describe one rule file, its exact contents, and what it
      authorizes, with no leftover reference to editing `default.rules`

- [ ] **Verify** (live, requires Codex CLI)
  - [ ] `codex execpolicy check --rules ~/.codex/rules/squadron.rules sq <cmd> …` returns
        `"decision":"allow"` for every subcommand in the pattern (walkthrough step 9)
  - [ ] The same check for `sq models list` returns no matched rule
  - [ ] Success: both checks match; record the exact commands run in the DEVLOG entry
  - [ ] Commit: `docs: document the Codex sandbox approval rule`

---

## Task 9 — Sandbox-rejection hint in sq-review, sq-run, sq-pr (D12)

- [x] Add a new section to each of `commands/agents/sq-review/SKILL.md`,
      `commands/agents/sq-run/SKILL.md`, `commands/agents/sq-pr/SKILL.md`
  - [x] Placement (F006): immediately after the `---` that closes the existing
        "## Waiting on the command" section (sq-review, sq-run); at the end of the file,
        after that section, for sq-pr (it has no trailing `---` there today) — never
        inside the span between the heading and the next `\n---\n`, which
        `test_long_command_skills_carry_one_waiting_rule` extracts and compares verbatim
  - [x] Content: if Codex rejects or blocks the underlying `sq` command for sandbox or
        approval reasons, state plainly that this is Codex's sandbox — not the model
        provider, not squadron's configuration — and point at the README's Codex
        approval-rule section by heading
  - [x] Out of scope, by the design's own success criteria: `sq-task`. If Task 7 found
        daemon-client commands need the rule, this is a real gap in the hint's coverage —
        file a follow-up issue rather than silently adding a fourth file (which the
        design's Component Structure and Success Criteria both name as exactly three)

- [x] **Test** `tests/cli/test_install_commands.py`
  - [x] `test_long_command_skills_carry_one_waiting_rule` still passes unchanged — proves
        the new section did not land inside the protected span
  - [x] New assertion: each of the three files contains the sandbox-rejection heading and
        the README section reference; `sq-task`'s file does not
  - [x] Success: `pytest tests/cli/test_install_commands.py` passes
  - [x] Commit: `feat: add sandbox-rejection hint to sq-review, sq-run, sq-pr skills`

---

## Task 10 — Fix `sq model list` → `sq models list` (six occurrences)

- [x] `commands/sq/review.md` lines 60, 112, 158
- [x] `commands/agents/sq-review/SKILL.md` lines 82, 134, 180
- [x] Success: `grep -rn "sq model list" commands/` returns nothing (confirms F005 — all
      six sites fixed, not two)
- [x] Commit: `fix: correct sq model list to sq models list in review command docs`

---

## Task 11 — Architecture amendment to 340-arch (F004)

- [x] Add a dated amendment (`*Amendment (20260927, slice 928): …*`) immediately after
      340-arch's "File copy is the delivery primitive" bullet (currently line 32),
      stating that `sq skills install --ide codex` now writes skill directories to
      `~/.agents/skills/` for packs shipping an `agents/` source directory, validated
      per D3, alongside the unchanged Claude prefix-directory copy
  - [x] Also note the pack-source layout gained a required-for-Codex `agents/` tree —
        cross-reference the README's skills section rather than duplicating it
  - [x] Check whether the existing slice-925 amendment on line 41 (about
        `install-commands`, not `skills install`) needs any correction given this
        slice's changes — it should not, since bundle_subdirs and the install path it
        describes are unaffected by 928; confirm and leave a one-line note only if it
        does need one
- [x] Check `360-arch.document-intelligence.md`'s slice-925 amendment (line 411): this
      slice adds no new `commands/sq/*` entries, so it should need no further amendment —
      confirm and record that conclusion rather than skipping the check silently
- [x] Success: 340-arch's stated delivery model matches what this slice ships; the
      360-arch check outcome (amend or no-amend) is recorded
- [x] Commit: `docs: amend 340-arch for the Codex skill-pack install path`

---

## Task 12 — CHANGELOG and full validation pass

- [x] Add a `CHANGELOG` `[Unreleased]` → `### Added` bullet: user-facing, one line, no
      technical detail (e.g. "`sq skills install/uninstall/list` now support `--ide
      codex` for Codex/agent-skill installs")
- [ ] A second bullet for the documented Codex approval rule, if user-facing enough to
      warrant one
- [x] `ruff format`, `ruff check`, `pyright` — zero errors is the merge gate
- [x] Full `pytest` run (not just touched files)
- [x] Success: green on all four
- [x] Commit: `docs: add CHANGELOG entry for Codex skill-pack parity`

---

## Task 13 — Live verification and close-out

- [x] Run the slice design's Verification Walkthrough steps 1–7 (CLI-only, disposable
      `HOME`, no Codex needed)
  - [x] **F003 correction:** step 7 must use `sq doctor -v` — bare `sq doctor` hides
        every WARN-level row, and the walkthrough's expected four skill-pack rows are
        all WARN at that point (nothing installed for the walkthrough's own packs)
  - [x] Success: each step's stated output matches, with the `-v` correction applied
- [ ] Run walkthrough steps 8–11 live, in a real terminal with the Codex CLI, using the
      rule file from Task 8
  - [ ] Before the rule: a sandboxed provider call fails (`HostUnreachableError` or
        equivalent)
  - [ ] After adding the rule: `codex execpolicy check` returns `allow` for the listed
        subcommands (already verified in Task 8) and the same command runs without a
        prompt from a live Codex session
  - [ ] Remove the rule and repeat: Codex blocks the command, and the model's reply
        (via Task 9's hint) names Codex's sandbox and the README section, not the
        provider
  - [ ] Success: each step's outcome is recorded, including any divergence from the
        design's stated expectations
- [ ] Write the DEVLOG Session State Summary entry: commits made, Task 7's full probe
      table, any follow-up issues filed (per Task 7/Task 9's daemon-command note),
      divergences observed during live verification
- [ ] Mark the slice complete: `status: complete` in
      `user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md`
      frontmatter, and check off entry 26 in
      `user/architecture/900-slices.maintenance-and-refactoring.md:453`
- [ ] Success: DEVLOG entry written, both status markers updated
- [ ] Commit: `docs: record slice 928 verification results and close the slice`
