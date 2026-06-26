---
docType: slice-plan
parent: 340-arch.skill-pack-infrastructure.md
project: squadron
dateCreated: 20260625
dateUpdated: 20260625
status: in_progress
---

# Slice Plan: Skill Pack Infrastructure

## Parent Document
`340-arch.skill-pack-infrastructure.md` — Architecture: Skill Pack Infrastructure

## Planning Context
Architecture-level. The parent architecture has one open design question — dispatch file vs. prefix-per-pack for the command surface — that must be resolved before the manifest format can commit to a prefix convention. The spike slice closes that question first. All remaining slices are thin: the mechanism is file copy + a TOML manifest, and the delivery primitive (markdown files in `~/.claude/commands/`) is identical to what `sq install-commands` already does.

Slices are ordered: spike → manifest/installer → analysis pack → CLI polish. Each is independently deployable and delivers usable value on its own.

---

## Foundation Work

1. [x] **(340) Command Surface Spike — Dispatch vs. Prefix** `340-slice.command-surface-spike-dispatch-vs-prefix.md` — A focused, time-boxed spike to determine whether `/sq:analysis <skill>` (single dispatcher markdown file routing by first argument) is a reliably usable alternative to `/analysis:<skill>` (prefix-per-pack, a dedicated subdirectory). The spike prototype a minimal `analysis.md` dispatcher that reads its first argument and delegates; test against at least two skill invocations (e.g. `tech-debt` and `understand`) to verify Claude Code passes arguments through reliably and the dispatch does not lose context or mangle invocation. Document the finding as a one-page decision record. **If dispatch is reliable:** update the arch to adopt dispatch; the manifest format gains a `dispatch_file` option alongside `prefix`. **If dispatch is unreliable:** prefix-per-pack is confirmed; the arch note is closed. Either outcome unblocks slice 341.
   - **Value:** Architectural enablement — closes the only open design question before manifest design commits.
   - **Success Criteria:**
     - Dispatch prototype exists and is exercised against at least two skill invocations.
     - A decision record documents whether dispatch is reliable, with observed evidence.
     - The arch doc is updated to reflect the closed decision.
   - **Dependencies:** [100] (install-commands file-copy pattern for reference).
   - **Risk:** Low. **Effort:** 1/5.

---

## Feature Slices

2. [ ] **(341) Manifest Format and `sq skills install/list`** — Define the `skills.toml` schema and implement `sq skills install <pack>` and `sq skills list`. The manifest lives at `~/.config/squadron/skills.toml` (user-level) with optional project-level override. Each pack entry declares a `source` (one of: `bundled`, local path, or `github:<org>/<repo>`) and a `prefix` (or `dispatch_file`, per the spike outcome). `install` resolves the source, copies markdown files to `~/.claude/commands/<prefix>/` (or the dispatch file location), and reports what was written. `list` shows all packs known to the manifest with installed/not-installed status. Git-source fetch is minimal: shallow clone to a temp dir, copy target files, discard. No version pinning in v1.
   - **Value:** Core mechanism — enables any pack to be installed from any source via a single command.
   - **Success Criteria:**
     - `skills.toml` schema is documented; `bundled`, local-path, and `github:` sources all resolve.
     - `sq skills install <pack>` copies markdown files to the correct location and reports success.
     - `sq skills list` shows installed vs. available status for all manifest entries.
     - Installing a pack that is already installed is idempotent (no error, files overwritten or skipped with a note).
     - Invalid source or unreachable git ref fails with a clear actionable error, not a traceback.
   - **Dependencies:** [340] (command surface decision informs prefix vs. dispatch).
   - **Risk:** Low–Medium (git fetch path is new; local and bundled paths are trivial). **Effort:** 3/5.

3. [ ] **(342) Analysis Pack (Bundled)** — Package the forked `tech-debt-analyze` skill and any other analysis-oriented skills into a bundled `analysis` pack shipped with the squadron wheel. The pack lives at `commands/analysis/` in the repo (parallel to `commands/sq/`), bundled via the same `pyproject.toml` `commands` include. The manifest's default `skills.toml` (or a shipped default) includes the `analysis` pack entry with `source = "bundled"`. Running `sq skills install analysis` installs it in one command; `sq doctor` reports the pack's presence.
   - **Value:** User value — `sq skills install analysis` is the one-command on-ramp for existing-codebase analysis work; ships the forked tech-debt-analyze skill in a principled, updateable location.
   - **Success Criteria:**
     - `commands/analysis/` exists in the repo and wheel with at least `tech-debt-analyze.md`.
     - `sq skills install analysis` installs the pack from the bundled source without network access.
     - The installed commands are usable in a Claude Code session immediately after install.
     - `sq doctor` reports the analysis pack as installed or not installed.
   - **Dependencies:** [341] (manifest and installer must exist).
   - **Risk:** Low. **Effort:** 2/5.

---

## Integration Work

4. [ ] **(343) `sq skills uninstall` and `sq doctor` Integration** — Complete the `sq skills` surface with `uninstall <pack>` (removes files written by `install`, does not touch files it did not write) and wire pack status into `sq doctor`'s checklist output. `sq doctor` gains a "Skill Packs" section listing installed packs and flagging packs declared in the manifest but not yet installed, with a "fix it with: `sq skills install <pack>`" hint per missing entry.
   - **Value:** Operational polish — users can cleanly remove packs and `sq doctor` gives a complete picture of the installed skill set alongside provider and integration status.
   - **Success Criteria:**
     - `sq skills uninstall <pack>` removes only files that `install` wrote; leaves unrelated files in the prefix directory untouched.
     - Uninstalling a pack not installed fails gracefully with a clear message.
     - `sq doctor` output includes a Skill Packs section with per-pack installed/missing status and fix hints.
   - **Dependencies:** [342] (analysis pack is the reference for install/uninstall round-trip).
   - **Risk:** Low. **Effort:** 1/5.

---

## Notes

**Key decisions made during planning:**
- Spike first: the command surface question (dispatch vs. prefix) is the only real design unknown. It is small enough to resolve empirically before any manifest format commits to a convention, and cheap enough that it does not block parallel work on anything else.
- Bundled analysis pack ships with the wheel (not fetched on install) so the primary user path (`sq skills install analysis`) works offline and without a GitHub token.
- v1 git-source fetch is deliberately minimal — shallow clone, copy, discard, no pinning. Versioning and lock files are deferred.
- Per-project `skills.toml` override is part of the manifest spec (341) but does not require separate implementation; the resolver checks CWD `.squadron/skills.toml` before user-level config.

**Open questions for slice design:**
- Merge semantics for project-level vs. user-level manifest (union? override? additive-only?). Decide in 341 slice design.
- Whether `sq doctor` should warn on packs installed but absent from any manifest (orphan detection). Decide in 343.

---

## Future Work
Items out of scope for the current plan but worth tracking.

1. [ ] **(1) Pack Versioning and Lock File** — Pin a pack to a git ref and generate a `skills.lock` for reproducible installs across machines. Dependencies: [341]. Effort: 2/5.
2. [ ] **(2) `sq skills update`** — Re-fetch and reinstall all installed packs from their sources. Pairs with lock file. Dependencies: [341]. Effort: 1/5.
3. [ ] **(3) Community Pack Registry** — A lightweight index of known third-party packs (name → source) so users can `sq skills install <name>` without knowing the git URL. Far-term; requires a hosted registry or well-known convention. Dependencies: [341].
