---
docType: tasks
slice: command-surface-parity
project: squadron
lld: project-documents/user/slices/140-slice.command-surface-parity.md
dependencies: [100-band-complete]
projectState: 100-band complete; sq review arch CLI shipped in v0.2.11; current slash commands use hyphenated names
dateCreated: 20260328
dateUpdated: 20260328
status: not_started
---

## Context Summary

- Working on **command-surface-parity** slice (140)
- Goal: replace four hyphenated slash commands with two consolidated files (`review.md`, `auth.md`) that dispatch on subcommand — matching the CLI surface exactly
- Pattern: same as `cf/prompt.md` — first word of `$ARGUMENTS` is the subcommand, remainder passed through
- Also: port `run-slice.md` → `run.md` (or deprecate), update installer to remove stale files
- No Python changes except `install.py` stale-file cleanup
- Next slice: 141 (Configuration Externalization) — independent, can start immediately after this

---

## Tasks

- [ ] **T1 — Create `commands/sq/review.md`**
  - [ ] Read all three existing files (`review-code.md`, `review-slice.md`, `review-tasks.md`) to capture current content
  - [ ] Structure: input parsing header → `code` section → `slice` section → `tasks` section → `arch` section → usage/error section
  - [ ] **Input parsing header**: extract first word of `$ARGUMENTS` as subcommand; remainder becomes the args passed to CLI; if missing or unrecognized, show usage listing valid subcommands
  - [ ] **`code` section**: content from `review-code.md`; replace `$ARGUMENTS` references with the remainder after stripping the leading `code` word
  - [ ] **`slice` section**: content from `review-slice.md`; strip leading `slice` word from args
  - [ ] **`tasks` section**: content from `review-tasks.md`; strip leading `tasks` word from args
  - [ ] **`arch` section**: new — mirrors slice/tasks pattern; initiative index shorthand (`sq review arch {number} -v`); no `--against` flag; flags: `--cwd`, `--model`, `--profile`, `-v`/`-vv`, `--json`, `--no-save`, `--rules-dir`
  - [ ] Success: file exists; each subcommand section accurately reflects current CLI behavior; `arch` section present and correct

- [ ] **T2 — Verify `review.md` against CLI help**
  - [ ] Run `sq review code --help`, `sq review slice --help`, `sq review tasks --help`, `sq review arch --help`
  - [ ] Confirm all flags listed in each section match CLI output; confirm `--against` absent from arch section
  - [ ] Success: no discrepancy between `review.md` and CLI help output for any subcommand

- [ ] **T3 — Create `commands/sq/auth.md`**
  - [ ] Content: dispatch on first word of `$ARGUMENTS` being `status`; invoke `sq auth status` with remaining args
  - [ ] For direct invocation without subcommand (bare `$ARGUMENTS`), default to `status` behavior (auth has only one subcommand currently)
  - [ ] Carry over the description from `auth-status.md`: "Shows configured credentials and their validation status for each provider profile"
  - [ ] Success: file exists; `/sq:auth status` invokes `sq auth status`; `/sq:auth` alone also works

- [ ] **T4 — Delete old hyphenated slash command files**
  - [ ] Delete `commands/sq/review-code.md`
  - [ ] Delete `commands/sq/review-slice.md`
  - [ ] Delete `commands/sq/review-tasks.md`
  - [ ] Delete `commands/sq/auth-status.md`
  - [ ] Success: all four files absent from `commands/sq/`; only `review.md` and `auth.md` cover this functionality

- [ ] **T5 — Commit checkpoint: slash command consolidation**
  - [ ] Stage: `commands/sq/review.md`, `commands/sq/auth.md`, and the four deleted files
  - [ ] Commit: `feat: consolidate review and auth slash commands to subcommand dispatch pattern`
  - [ ] Success: clean working tree for `commands/sq/`; commit includes both creates and deletes

- [ ] **T6 — Handle `commands/sq/run-slice.md`**
  - [ ] Read `run-slice.md` — assess whether content adapts cleanly to `run.md` with `slice` as first-word dispatch
  - [ ] **If straightforward:** create `commands/sq/run.md` dispatching on `$ARGUMENTS` starting with `slice`; content is the existing run-slice workflow; delete `run-slice.md`
  - [ ] **If messy:** add deprecation banner at top of `run-slice.md`: `> **DEPRECATED:** Use \`sq run slice-lifecycle\` (coming in slice 151). Until then, \`/sq:run-slice\` continues to work.`; leave file in place
  - [ ] Success: either `run.md` exists and accepts `/sq:run slice {number}`, OR `run-slice.md` has visible deprecation banner

- [ ] **T7 — Update `install_commands()` to remove stale files**
  - [ ] Edit `src/squadron/cli/commands/install.py` — inside the per-subdirectory loop, after copying source files, find any `.md` files in the target subdir that are not in the source and delete them
  - [ ] Report removed files to the user (same style as installed files output)
  - [ ] Pattern: build `source_files` as a set of filenames; after copy loop, iterate target `.md` files and delete any not in `source_files`; collect into `removed` list; print after install summary if non-empty
  - [ ] Success: function removes stale files from target; reports them; existing install behavior unchanged when no stale files present

- [ ] **T8 — Test stale-file removal**
  - [ ] Manually place a dummy `commands/sq/review-code.md` file back (or confirm old installed copy exists at `~/.claude/commands/sq/`)
  - [ ] Run `sq install-commands`
  - [ ] Confirm output reports removal of `review-code.md` (and any other deleted files)
  - [ ] Confirm `~/.claude/commands/sq/` contains only files present in `commands/sq/`
  - [ ] Success: install is idempotent and self-cleaning; no orphaned files remain

- [ ] **T9 — Commit: installer stale-file cleanup**
  - [ ] Stage: `src/squadron/cli/commands/install.py`
  - [ ] Commit: `fix: remove stale slash commands from install target on reinstall`
  - [ ] Success: commit created; clean working tree

- [ ] **T10 — Smoke-test all new slash commands**
  - [ ] Run `sq install-commands` — verify output lists `sq/review.md`, `sq/auth.md`; no old hyphenated files listed
  - [ ] Confirm `~/.claude/commands/sq/` contains `review.md`, `auth.md` and does not contain `review-code.md`, `review-slice.md`, `review-tasks.md`, `auth-status.md`
  - [ ] In Claude Code: invoke `/sq:review arch 140` — confirm it runs `sq review arch 140 -v` and produces output
  - [ ] In Claude Code: invoke `/sq:review code 191` — confirm number shorthand routes to `sq review code 191 -v` (not a bare path invocation)
  - [ ] In Claude Code: invoke `/sq:review code --no-save --diff main` — confirm flag passthrough works
  - [ ] In Claude Code: invoke `/sq:auth status` — confirm it runs `sq auth status`
  - [ ] In Claude Code: invoke `/sq:review bogus` — confirm usage message shown, no crash
  - [ ] In Claude Code: attempt `/sq:review-code` — confirm command is not found (stale command absent after reinstall)
  - [ ] Success: all subcommands route correctly; number shorthand works; old hyphenated commands absent; no regressions

- [ ] **T11 — Final commit and slice closure**
  - [ ] Update slice design status to `complete` in `140-slice.command-surface-parity.md`
  - [ ] Update slice plan entry checkbox for slice 140 in `140-slices.pipeline-foundation.md`
  - [ ] Stage and commit: `docs: mark slice 140 command-surface-parity complete`
  - [ ] Success: clean working tree; slice marked complete in both design and plan
