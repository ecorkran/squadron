---
docType: slice-design
slice: small-fixes-batch
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260916
dateUpdated: 20260916
status: not_started
---

# Slice Design: Small Fixes Batch

## Overview

Bundles two independently small, root-caused bugs: [#67](https://github.com/ecorkran/squadron/issues/67)
(unknown model alias dispatches silently instead of failing fast) and
[#103](https://github.com/ecorkran/squadron/issues/103) (`sq summary --restore`
without `--key` can pick a sibling project's summary instead of the current
project's).

Originally scoped to four issues. [#78](https://github.com/ecorkran/squadron/issues/78)
and [#65](https://github.com/ecorkran/squadron/issues/65) finding 1 were found
already fixed on `main` during this design pass (`0aae0c8c`, `9c0d7a37`) —
verified by reading the current code, not just trusting the issue text — and
closed/updated rather than carried into tasks here.

## Fix 1 — #67: unknown `--model` alias dispatches silently

**Current behavior.** `resolve_model_alias` (`src/squadron/models/aliases.py:179-190`)
returns `(name, None)` for any name absent from the merged alias table — by
design, since a literal model ID (not an alias) is legitimate input and must
pass through unresolved. There is no distinction today between "typo'd an
alias" and "gave a valid literal model ID."

`_run_review_command` (`src/squadron/cli/commands/review.py:597-608`) calls
`resolve_model_alias(raw_model)`; when it returns `(name, None)`,
`resolved_profile` falls back through config to the `"sdk"` default
(`_resolve_profile`, ~line 506) with no explicit `--profile` given. The
unresolved name is then dispatched straight to the Claude Code SDK, which
emits its own `[claude-code:unrecognized_model]` line and — per the reported
case — a misleading workspace-trust warning as a fallthrough artifact. The
review still runs to UNKNOWN and overwrites the prior valid review file.

**Fix.** At the exact point in `review.py:604-607` where alias resolution
happens: when `resolve_model_alias` returns `(name, None)` **and** no
explicit `--profile` was given (i.e. resolution is about to fall back to the
`sdk` default), treat this as an unknown-alias condition rather than a literal
model ID passthrough. Fail fast with `unknown model alias '{name}'; known:
{sorted(get_all_aliases().keys())}` before `_execute_review` runs. A user who
truly wants to hand a literal SDK model string through can still do so via
explicit `--profile`, which is the signal that this isn't an alias lookup at
all — the ambiguity only exists when profile is unresolved.

This also prevents the second half of the reported symptom: an UNKNOWN
verdict from a name that was never a real model should not reach the
overwrite-prior-review path, because it now never dispatches.

## Fix 2 — #103: `--restore` matches sibling projects by prefix

**Current behavior.** `_handle_restore`
(`src/squadron/cli/commands/summary_instructions.py:91-131`) resolves the
current project name via CF, then globs
`_SUMMARIES_DIR.glob(f"{project}-*.md")` (line 111). This is a bare prefix
match: for `project == "squadron"`, it also matches `squadron-pr-*.md` and any
other sibling project whose name starts with `squadron-`. `_summary_key`
(lines 82-88) has the same flaw via `path.stem.removeprefix(f"{project}-")`.
With no `--key`, `_select_summary` (lines 134-154) just takes `matches[0]`
(most recently modified) — so a recently-touched sibling project's summary
can silently win over the current project's own.

**Fix.** Reject a glob match whose remainder (`path.stem.removeprefix(f"{project}-")`)
is itself a real sibling project name followed by `-`. Concretely: after
computing `matches` at line 110-114, filter out any path whose stem, with the
`{project}-` prefix stripped, still starts with `{other_project}-` for some
other known project name. Known project names come from the same CF source
`gather_cf_params`/project listing already uses elsewhere in this file — no
new dependency. Apply the same predicate inside `_summary_key` so the picker
listing (line 126) and the key-matching path (line 146) can't disagree with
the default-selection path about what counts as "this project's" summary.

## Non-goals

- Issue #67's third suggested item (SDK workspace-trust preflight/remediation
  messaging) is a separate, larger UX concern — not required to fix the
  "silent dispatch of an unknown alias" defect and not included here.
- Issue #60 (`sq models check`, validating alias references across pools/
  pipelines statically) overlaps conceptually but is a separate command-level
  feature, not this runtime dispatch-path fix.
