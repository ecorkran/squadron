---
docType: tasks
slice: add-understand-anything-to-analysis-pack
project: squadron
lld: user/slices/344-slice.add-understand-anything-to-analysis-pack.md
dependencies: [342, 343]
projectState: >
  Slices 340–343 complete. Analysis pack exists at commands/analysis/ with
  tech-debt-audit.md. Installer copies all *.md via _install_prefix(). Receipt
  system and sq doctor Skill Packs section are live.
dateCreated: 20260628
dateUpdated: 20260628
status: not_started
---

## Context Summary

- Working on slice 344: Add `understand-anything` to the bundled analysis pack
- Content-only slice — no Python code changes; installer already handles all `*.md` in `commands/analysis/`
- Key work: fork upstream repo, extract and adapt SKILL.md (attribution + self-reference patching), update dispatcher
- Self-reference patching is the critical step: instructional `/understand` calls in the skill body must become `/analysis:understand-anything`
- User must run the skill on a real repo and confirm output before merge (gate task)
- Slice design: `user/slices/344-slice.add-understand-anything-to-analysis-pack.md`

---

## Pre-work

- [ ] **T1 — Branch setup**
  - [ ] Confirm current branch is `main` or create slice branch: `git checkout -b 344-slice.add-understand-anything-to-analysis-pack`
  - [ ] Confirm `commands/analysis/tech-debt-audit.md` exists (slice 342 prerequisite)

- [ ] **T2 — Fork the upstream repo** *(user action)*
  - [ ] On GitHub, fork `Egonex-AI/Understand-Anything` to `ecorkran/understand-anything`
  - [ ] Confirm the fork is public and the file `understand-anything-plugin/skills/understand/SKILL.md` is present
  - [ ] Success: fork exists at `github.com/ecorkran/understand-anything`

---

## Skill File: Extract and Adapt

- [ ] **T3 — Obtain SKILL.md from the fork**
  - [ ] Clone or download the fork; locate `understand-anything-plugin/skills/understand/SKILL.md`
  - [ ] Copy the raw file content to a local working copy
  - [ ] Success: raw SKILL.md content is available for editing

- [ ] **T4 — Prepend attribution comment**
  - [ ] Insert the following as the very first line of the file, before any YAML frontmatter:
    ```
    <!-- Forked from github:ecorkran/understand-anything (MIT). Original: github:Egonex-AI/Understand-Anything, Copyright 2026 Yuxiang Lin and Infinite Universe Inc. -->
    ```
  - [ ] Success: attribution comment is line 1; original content follows unchanged

- [ ] **T5 — Audit SKILL.md for `/understand` self-references**
  - [ ] Search the entire file for the string `/understand` (with the leading slash)
  - [ ] For each occurrence, classify it as:
    - **Instructional** — a directive telling Claude to invoke the skill by slash-command name (e.g., "Run `/understand --auto-update`", "invoke `/understand` again"). These must be patched.
    - **Descriptive** — prose, section headings, output path names (`.understand-anything/`), or attribute names. Do not patch these.
  - [ ] Record the line numbers and classification of every `/understand` occurrence before patching
  - [ ] Success: all occurrences are classified; at least one instructional reference is found (if none exist, note the finding and skip T6)

- [ ] **T6 — Patch instructional `/understand` references**
  - [ ] For each instructional occurrence identified in T5: replace `/understand` with `/analysis:understand-anything`, preserving any flags that follow (e.g., `/understand --full` → `/analysis:understand-anything --full`)
  - [ ] Re-scan the file for `/understand` after patching to confirm no instructional references remain
  - [ ] Descriptive occurrences (`.understand-anything/`, section headings, etc.) are untouched
  - [ ] Success: `grep -n '/understand[^-]' commands/analysis/understand-anything.md` returns no lines with instructional slash-command invocations

- [ ] **T7 — Save as `commands/analysis/understand-anything.md`**
  - [ ] Write the adapted file to `commands/analysis/understand-anything.md` in the squadron repo
  - [ ] Verify the file begins with the attribution comment, followed by the original YAML frontmatter
  - [ ] Success: `ls commands/analysis/` shows both `tech-debt-audit.md` and `understand-anything.md`

- [ ] **T8 — Verify install picks up the new file**
  - [ ] Run `sq skills install analysis --commands-dir /tmp/sq-test-commands` (use a temp dir to avoid affecting the live install)
  - [ ] Confirm output reports `2 file(s)` installed
  - [ ] Confirm both files exist under `/tmp/sq-test-commands/analysis/`
  - [ ] Confirm the receipt (`~/.config/squadron/receipts/analysis.toml` or temp receipts dir) lists both `tech-debt-audit.md` and `understand-anything.md` in `files_written`
  - [ ] Success: 2-file install confirmed; receipt is correct

- [ ] **T9 — Commit: skill file addition**
  - [ ] Stage `commands/analysis/understand-anything.md`
  - [ ] Commit: `feat: add understand-anything skill to analysis pack`
  - [ ] Success: commit created; `git status` clean for this file

---

## Dispatcher Update

- [ ] **T10 — Update valid skills line in `commands/sq/analysis.md`**
  - [ ] Change `Valid skills: \`tech-debt-audit\`` to `Valid skills: \`tech-debt-audit\`, \`understand-anything\``
  - [ ] Success: the updated line contains both skill names

- [ ] **T11 — Update usage block in `commands/sq/analysis.md`**
  - [ ] Add the `understand-anything` usage line to the Usage block:
    ```
    /sq:analysis understand-anything [path] [--full|--auto-update|--no-auto-update|--review|--language <lang>]
    ```
  - [ ] Success: usage block shows both `tech-debt-audit` and `understand-anything` patterns

- [ ] **T12 — Add `## Skill: understand-anything` section to `commands/sq/analysis.md`**
  - [ ] Append a new section after the `## Skill: tech-debt-audit` block; see the dispatcher spec in the slice design (`user/slices/344-slice.add-understand-anything-to-analysis-pack.md`, section "Dispatcher update")
  - [ ] The section must: name the skill, state it delegates to `/analysis:understand-anything`, describe the 7-phase pipeline, list the output location, and include the "not installed" guard identical to the `tech-debt-audit` section
  - [ ] Success: `commands/sq/analysis.md` contains a `## Skill: understand-anything` section with a delegation instruction to `/analysis:understand-anything`

- [ ] **T13 — Verify dispatcher file is well-formed**
  - [ ] Read `commands/sq/analysis.md` in full; confirm:
    - Valid skills line lists both `tech-debt-audit` and `understand-anything`
    - Usage block contains both invocation patterns
    - `## Skill: understand-anything` section is present and complete
    - No accidental duplication or missing content from the existing `tech-debt-audit` section
  - [ ] Success: file reads correctly; both skills are fully documented

- [ ] **T14 — Commit: dispatcher update**
  - [ ] Stage `commands/sq/analysis.md`
  - [ ] Commit: `feat: update sq:analysis dispatcher to route understand-anything`
  - [ ] Success: commit created

---

## Verification and Gate

- [ ] **T15 — Run existing test suite**
  - [ ] Run `pytest tests/skills/` from the project root
  - [ ] Success: all tests pass (same count as before this slice); no new failures

- [ ] **T16 — Live install and routing verification** *(user action)*
  - [ ] Uninstall any existing analysis pack: `sq skills uninstall analysis` (if installed)
  - [ ] Run `sq skills install analysis`
  - [ ] Confirm output: `Installed pack 'analysis': 2 file(s) → ~/.claude/commands/analysis`
  - [ ] Confirm both files in `~/.claude/commands/analysis/`: `tech-debt-audit.md` and `understand-anything.md`
  - [ ] Run `sq doctor -v` and confirm "Skill Packs" section shows `✓ analysis`
  - [ ] In a Claude Code session, run `/sq:analysis understand-anything` and confirm it delegates to `/analysis:understand-anything` (skill begins its scan phase)
  - [ ] In a Claude Code session, run `/analysis:understand-anything` directly and confirm same behavior
  - [ ] Success: both invocation paths route correctly; pack installs as 2 files; doctor shows installed

- [ ] **T17 — User verification: skill runs on a real repo** *(required gate before merge)*
  - [ ] Open a Claude Code session in a small-to-medium git repo (e.g., the squadron repo itself)
  - [ ] Run `/sq:analysis understand-anything` and let it complete the full 7-phase pipeline
  - [ ] Confirm `.understand-anything/knowledge-graph.json` is produced and contains valid JSON
  - [ ] Make a small code change, then run `/sq:analysis understand-anything --auto-update`; confirm only changed files are re-analyzed (incremental mode)
  - [ ] Success: full and incremental runs both complete without error; output file is present and valid

- [ ] **T18 — Final cleanup and merge readiness**
  - [ ] Run `ruff format .` and `ruff check .` to confirm no lint issues (no Python changes expected, but confirm)
  - [ ] Confirm `git log --oneline` shows exactly the two commits from T9 and T14 on this branch
  - [ ] Confirm `commands/analysis/` contains exactly `tech-debt-audit.md` and `understand-anything.md`
  - [ ] Success: branch is clean, lint passes, commits are semantic, ready for PM review
