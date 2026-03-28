---
docType: slice-design
slice: command-surface-parity
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [100-band-complete]
interfaces: [151-cli-integration-and-e2e-validation]
dateCreated: 20260328
dateUpdated: 20260328
status: complete
---

# Slice Design: Command Surface Parity

## Overview

Squadron's CLI uses `sq review code`, `sq review slice`, etc. — space-separated subcommands. The current slash commands use hyphenated names (`/sq:review-code`, `/sq:review-slice`) that don't match. The goal is a single `/sq:review` slash command that accepts a subcommand as its first argument — the same pattern `cf` already uses (`/cf:prompt get`, `/cf:build`, etc.).

Additionally, `sq review arch` exists in the CLI (v0.2.11) but has no slash command. And `/sq:run-slice` will be superseded by `sq run` (slice 151); this slice ports it to `/sq:run slice` if practical, otherwise retires it with a deprecation notice.

## Value

**For users:** The slash command surface matches the CLI. Knowing `sq review arch` means knowing `/sq:review arch`. No hyphen guessing.

**For maintainers:** New CLI subcommands get a slash command for free — update one file (`review.md`), not four. The `cf` pattern is proven.

## Technical Scope

### In Scope

1. **Create `commands/sq/review.md`** — single file handling all four review subcommands: `code`, `slice`, `tasks`, `arch`. Dispatches on first word of `$ARGUMENTS`.
2. **Delete `commands/sq/review-code.md`, `review-slice.md`, `review-tasks.md`** — replaced by `review.md`
3. **Create `commands/sq/auth.md`** — replaces `auth-status.md`; dispatches on first word of `$ARGUMENTS` (`status`), giving `/sq:auth status`
4. **Delete `commands/sq/auth-status.md`** — replaced by `auth.md`
5. **Handle `commands/sq/run-slice.md`** — port to `run.md` (dispatching on `$ARGUMENTS` starting with `slice`) if straightforward; otherwise add deprecation notice pointing to future `sq run`
6. **Update `sq install-commands`** — update installer to remove stale files from target on reinstall

### Out of Scope

- Changes to CLI commands (already correctly named)
- `/sq:run` full implementation (that's slice 151 — `sq run` doesn't exist yet)
- Review template or pipeline changes

## Architecture

### Pattern: Single File with Subcommand Dispatch

`cf/prompt.md` handles `/cf:prompt list` and `/cf:prompt get {name}` by reading the first word of `$ARGUMENTS` and branching. The same pattern applies here.

`commands/sq/review.md` reads `$ARGUMENTS`:
- First word is the subcommand: `code`, `slice`, `tasks`, `arch`
- Remainder is passed through to the CLI unchanged

```
/sq:review code 191           → sq review code 191 -v
/sq:review slice 191          → sq review slice 191 -v
/sq:review tasks 191          → sq review tasks 191 -v
/sq:review arch 140           → sq review arch 140 -v
/sq:review code --diff main   → sq review code --diff main
```

### File Changes

| Action | File | Notes |
|--------|------|-------|
| **CREATE** | `commands/sq/review.md` | Replaces the three existing review files + adds arch |
| **DELETE** | `commands/sq/review-code.md` | Superseded |
| **DELETE** | `commands/sq/review-slice.md` | Superseded |
| **DELETE** | `commands/sq/review-tasks.md` | Superseded |
| **CREATE** | `commands/sq/auth.md` | Replaces `auth-status.md`; dispatches on `status` subcommand |
| **DELETE** | `commands/sq/auth-status.md` | Superseded |
| **MODIFY or DELETE** | `commands/sq/run-slice.md` | Port to `run.md` or add deprecation notice |

### `commands/sq/review.md` Content Spec

The file must handle all four subcommands. Structure:

```
## Input parsing
Parse first word of $ARGUMENTS as subcommand: code | slice | tasks | arch.
Remainder of $ARGUMENTS is passed to the CLI.
If subcommand is missing or unrecognized, show usage.

## Subcommand: code
[content from current review-code.md, adjusted to strip leading "code" from $ARGUMENTS]

## Subcommand: slice
[content from current review-slice.md, adjusted to strip leading "slice"]

## Subcommand: tasks
[content from current review-tasks.md, adjusted to strip leading "tasks"]

## Subcommand: arch
[new — mirrors slice/tasks pattern; no --against flag; initiative index shorthand]
```

### `run-slice.md` Handling

Port to `commands/sq/run.md` dispatching on `$ARGUMENTS` starting with `slice`. If `$ARGUMENTS` is `slice {number}`, run the existing run-slice workflow. This makes `/sq:run slice 191` work — same content, new name. Delete `run-slice.md`.

If the porting is messier than expected (the run-slice content doesn't adapt cleanly), fall back: add a deprecation notice to `run-slice.md` pointing to future `sq run slice-lifecycle` and leave it in place.

### Install Command: Handling Deletions

`sq install-commands` currently only copies new files — it doesn't remove stale files from the target. After this slice, users who reinstall will have orphaned `review-code.md`, `review-slice.md`, `review-tasks.md` in `~/.claude/commands/sq/`. Those stale files will surface as dead slash commands.

Fix: update `install_commands()` in `src/squadron/cli/commands/install.py` to remove stale `.md` files from the target `sq/` directory on each run — same approach context-forge applied in `daec117`. Source is authoritative: any `.md` in the target that is not in the source gets deleted and reported. The user runs `sq install-commands` once; it installs new files and removes old ones in a single step.

## Success Criteria

### Functional Requirements

- [ ] `/sq:review code $ARGS` invokes `sq review code $ARGS` with all existing flag support
- [ ] `/sq:review slice $ARGS` invokes `sq review slice $ARGS` with all existing flag support
- [ ] `/sq:review tasks $ARGS` invokes `sq review tasks $ARGS` with all existing flag support
- [ ] `/sq:review arch $ARGS` invokes `sq review arch $ARGS` (new)
- [ ] Number shorthand works: `/sq:review code 191` → `sq review code 191 -v`
- [ ] `/sq:review` with no subcommand shows usage rather than silently failing
- [ ] `/sq:auth status` invokes `sq auth status $ARGS`
- [ ] Old hyphenated commands (`/sq:review-code`, `/sq:auth-status` etc.) no longer exist after reinstall
- [ ] `/sq:run slice 191` works (or `/sq:run-slice` has visible deprecation notice)
- [ ] `sq install-commands` leaves no stale files in target

### Technical Requirements

- [ ] `review.md` is the single source of truth for all review slash command behavior
- [ ] Deleted source files are removed from install target on reinstall

### Verification Walkthrough

```bash
# 1. Reinstall commands
sq install-commands

# 2. Verify old files gone from target
ls ~/.claude/commands/sq/
# Expected: no review-code.md, review-slice.md, review-tasks.md
# Expected: review.md present

# 3. In Claude Code — test each subcommand
/sq:review arch 140       # should run sq review arch 140 -v, save review file
/sq:review slice 140      # should run sq review slice 140 -v
/sq:review tasks 140      # should run sq review tasks 140 -v
/sq:review code 140       # should run sq review code 140 -v
/sq:auth status           # should run sq auth status, show credential state

# 4. Test flag passthrough
/sq:review code --diff main --no-save

# 5. Test unrecognized subcommand shows usage
/sq:review bogus
```
