---
docType: tasks
slice: command-surface-parity
project: squadron
lld: project-documents/user/slices/140-slice.command-surface-parity.md
dependencies: [100-band-complete]
projectState: 100-band complete; sq review arch CLI shipped in v0.2.11; current slash commands use hyphenated names
dateCreated: 20260328
dateUpdated: 20260328
status: complete
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

- [x] **T1 — Create `commands/sq/review.md`**
  - [x] Read all three existing files (`review-code.md`, `review-slice.md`, `review-tasks.md`) to capture current content
  - [x] Structure: input parsing header → `code` section → `slice` section → `tasks` section → `arch` section → usage/error section
  - [x] **Input parsing header**: extract first word of `$ARGUMENTS` as subcommand; remainder becomes the args passed to CLI; if missing or unrecognized, show usage listing valid subcommands
  - [x] **`code` section**: content from `review-code.md`; replace `$ARGUMENTS` references with the remainder after stripping the leading `code` word
  - [x] **`slice` section**: content from `review-slice.md`; strip leading `slice` word from args
  - [x] **`tasks` section**: content from `review-tasks.md`; strip leading `tasks` word from args
  - [x] **`arch` section**: new — mirrors slice/tasks pattern; initiative index shorthand (`sq review arch {number} -v`); no `--against` flag; flags: `--cwd`, `--model`, `--profile`, `-v`/`-vv`, `--json`, `--no-save`, `--rules-dir`
  - [x] Success: file exists; each subcommand section accurately reflects current CLI behavior; `arch` section present and correct

- [x] **T2 — Verify `review.md` against CLI help**
  - [x] Run `sq review code --help`, `sq review slice --help`, `sq review tasks --help`, `sq review arch --help`
  - [x] Confirm all flags listed in each section match CLI output; confirm `--against` absent from arch section
  - [x] Success: no discrepancy between `review.md` and CLI help output for any subcommand

- [x] **T3 — Create `commands/sq/auth.md`**
  - [x] Content: dispatch on first word of `$ARGUMENTS` being `status`; invoke `sq auth status` with remaining args
  - [x] For direct invocation without subcommand (bare `$ARGUMENTS`), default to `status` behavior (auth has only one subcommand currently)
  - [x] Carry over the description from `auth-status.md`: "Shows configured credentials and their validation status for each provider profile"
  - [x] Success: file exists; `/sq:auth status` invokes `sq auth status`; `/sq:auth` alone also works

- [x] **T4 — Delete old hyphenated slash command files**
  - [x] Delete `commands/sq/review-code.md`
  - [x] Delete `commands/sq/review-slice.md`
  - [x] Delete `commands/sq/review-tasks.md`
  - [x] Delete `commands/sq/auth-status.md`
  - [x] Success: all four files absent from `commands/sq/`; only `review.md` and `auth.md` cover this functionality

- [x] **T5 — Commit checkpoint: slash command consolidation**
  - [x] Stage: `commands/sq/review.md`, `commands/sq/auth.md`, and the four deleted files
  - [x] Commit: `feat: consolidate review and auth slash commands to subcommand dispatch pattern`
  - [x] Success: clean working tree for `commands/sq/`; commit includes both creates and deletes

- [x] **T6 — Handle `commands/sq/run-slice.md`**
  - [x] Read `run-slice.md` — assess whether content adapts cleanly to `run.md` with `slice` as first-word dispatch
  - [x] **If straightforward:** create `commands/sq/run.md` dispatching on `$ARGUMENTS` starting with `slice`; content is the existing run-slice workflow; delete `run-slice.md`
  - [x] **If messy:** add deprecation banner at top of `run-slice.md`: `> **DEPRECATED:** Use \`sq run slice-lifecycle\` (coming in slice 151). Until then, \`/sq:run-slice\` continues to work.`; leave file in place
  - [x] Success: either `run.md` exists and accepts `/sq:run slice {number}`, OR `run-slice.md` has visible deprecation banner

- [x] **T7 — Update `install_commands()` to remove stale files**
  - [x] Edit `src/squadron/cli/commands/install.py` — inside the per-subdirectory loop, after copying source files, find any `.md` files in the target subdir that are not in the source and delete them
  - [x] Report removed files to the user (same style as installed files output)
  - [x] Pattern: build `source_files` as a set of filenames; after copy loop, iterate target `.md` files and delete any not in `source_files`; collect into `removed` list; print after install summary if non-empty
  - [x] Success: function removes stale files from target; reports them; existing install behavior unchanged when no stale files present

- [x] **T8 — Test stale-file removal**
  - [x] Manually place a dummy `commands/sq/review-code.md` file back (or confirm old installed copy exists at `~/.claude/commands/sq/`)
  - [x] Run `sq install-commands`
  - [x] Confirm output reports removal of `review-code.md` (and any other deleted files)
  - [x] Confirm `~/.claude/commands/sq/` contains only files present in `commands/sq/`
  - [x] Success: install is idempotent and self-cleaning; no orphaned files remain

- [x] **T9 — Commit: installer stale-file cleanup**
  - [x] Stage: `src/squadron/cli/commands/install.py`
  - [x] Commit: `fix: remove stale slash commands from install target on reinstall`
  - [x] Success: commit created; clean working tree

- [x] **T10 — Smoke-test all new slash commands**
  - [x] Run `sq install-commands` — verify output lists `sq/review.md`, `sq/auth.md`; no old hyphenated files listed
  - [x] Confirm `~/.claude/commands/sq/` contains `review.md`, `auth.md` and does not contain `review-code.md`, `review-slice.md`, `review-tasks.md`, `auth-status.md`
  - [x] In Claude Code: invoke `/sq:review arch 140` — confirm it runs `sq review arch 140 -v` and produces output
  - [x] In Claude Code: invoke `/sq:review code 191` — confirm number shorthand routes to `sq review code 191 -v` (not a bare path invocation)
  - [x] In Claude Code: invoke `/sq:review code --no-save --diff main` — confirm flag passthrough works
  - [x] In Claude Code: invoke `/sq:auth status` — confirm it runs `sq auth status`
  - [x] In Claude Code: invoke `/sq:review bogus` — confirm usage message shown, no crash
  - [x] In Claude Code: attempt `/sq:review-code` — confirm command is not found (stale command absent after reinstall)
  - [x] Success: all subcommands route correctly; number shorthand works; old hyphenated commands absent; no regressions

- [x] **T11 — Final commit and slice closure**
  - [x] Update slice design status to `complete` in `140-slice.command-surface-parity.md`
  - [x] Update slice plan entry checkbox for slice 140 in `140-slices.pipeline-foundation.md`
  - [x] Stage and commit: `docs: mark slice 140 command-surface-parity complete`
  - [x] Success: clean working tree; slice marked complete in both design and plan
