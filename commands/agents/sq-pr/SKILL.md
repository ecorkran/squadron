---
name: sq-pr
description: Resolves and reports a pull request, or opens one from the current branch with a description assembled from the branch's own artifacts. Use when the user asks to show, check, or create a PR through squadron.
---

# sq pr

Run a pull-request command using squadron.

## Input parsing

The first word the user typed after `$sq-pr` is the subcommand. The remainder is passed to the CLI
unchanged — nothing is appended, substituted, or removed.

Valid subcommands: `show`, `create`

If the subcommand is missing or unrecognized, show the usage below and stop.

**Usage:**
```
$sq-pr show [TARGET] [FLAGS]     — resolve and report a pull request
$sq-pr create [FLAGS]            — open a pull request from the current branch
```

---

## Subcommand: show

Resolve a pull request, fetch its endpoints, and report the range.

Pass what the user typed after the leading `show` word directly to:

`sq pr show {remainder}`

An absent remainder is valid and passes through as absent — `sq pr show` with no target and no
flags resolves the current branch's pull request.

Optional arguments:
- Positional: pull request to show — a number, `owner/repo#number`, `repo#number`, a
  pull-request URL, or a branch. Omit to use the current branch.

Optional flags:
- `--cwd TEXT`: repository to resolve against
- `--json`: emit machine-readable JSON

Show the command's output.

---

## Subcommand: create

Open a pull request with a description assembled from the branch's own artifacts.

Pass what the user typed after the leading `create` word directly to:

`sq pr create {remainder}`

`sq pr create` writes to the host — it is the only thing that writes. This section carries four
rules for running it from a session:

- **`--dry-run` is offered, never substituted.** The flag is documented below; do not convert an
  operator's `create` into a dry run, and do not convert a `--dry-run` into a real create.
- **The command runs once.** On a non-zero exit, show the output and stop — do not retry. A
  create that failed after landing opens a second pull request if retried.
- **Printed remediation is shown, not executed.** A refusal for an unpushed branch prints the
  `git push` command to run. Show that line; do not run it — squadron does not push, and running
  it on the operator's behalf makes squadron push by proxy.
- **A refused base is not worked around.** Do not pass `--base` on the operator's behalf to get
  past a base-selection refusal.

Optional flags:
- `--base TEXT`: base branch
- `--dry-run`: print title and body without creating
- `--model TEXT`: model for the one-shot composer
- `--profile TEXT`: provider profile for the one-shot composer (default: `sdk`)
- `--cwd TEXT`: repository to resolve against
- `--title TEXT`: PR title, overriding the slice's name

Show the command's output.
