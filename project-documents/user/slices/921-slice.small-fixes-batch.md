---
docType: slice-design
slice: small-fixes-batch
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260916
dateUpdated: 20260917
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

**Correction from slice review (20260917):** an earlier draft keyed the guard
on `profile_flag is None` while justifying it as "the ambiguity only exists
when profile is unresolved" — those are not the same condition. `_resolve_profile`
(review.py:490-506) is called as `_resolve_profile(profile_flag or
alias_profile, template)` and internally falls back further through
`template.profile` → config `default_review_profile` → `"sdk"`. A literal
model ID with a template- or config-supplied profile would be wrongly
rejected under the flag-only guard, contradicting the fix's own rationale.
The guard below fixes this by checking the same fallback chain the
rationale actually describes.

**Fix.** At the point in `review.py:604-607` where alias resolution happens:
when `resolve_model_alias` returns `(name, None)`, determine whether
`_resolve_profile` would resolve to anything other than the bare `"sdk"`
default through the flag → template → config chain (i.e. call the same
three checks `_resolve_profile` performs — `profile_flag`, `template.profile`,
`get_config("default_review_profile")` — before falling through). Only when
all three are absent (profile is genuinely unresolved, matching the design's
actual rationale) treat this as an unknown-alias condition and fail fast with
`unknown model alias '{name}'; known: {sorted(get_all_aliases().keys())}`
before `_execute_review` runs. When any of the three supplies a profile, the
name passes through as a literal model ID exactly as today — that explicit
signal is what distinguishes "user meant a literal model ID" from "user
typo'd an alias."

This also prevents the second half of the reported symptom: an UNKNOWN
verdict from a name that was never a real model should not reach the
overwrite-prior-review path, because it now never dispatches.

**Collateral effects to record, not silently absorb:** `raw_model` itself can
arrive from config (`_resolve_model`'s cascade: flag → `default_model_{template}`
→ global `default_model`, review.py:509+), so a stale `default_model` config
value with no explicit profile anywhere will now fail every affected review
command with the alias error, rather than silently dispatching as today —
consistent with the project's fail-explicit convention, but a real behavior
change worth calling out in the task's acceptance criteria, not just the
`--model` flag case the issue title names.

A second, currently-working invocation shape also starts failing (review
F003): no shipped template declares `profile:` (verified — `grep profile:
src/squadron/data/templates/*.yaml` finds nothing, only `model:` keys), so
`template.profile` is always `None` in practice, and `sq review code --model
<a-valid-literal-model-id>` with no `--profile` flag and no
`default_review_profile` config — which dispatches correctly today via the
bare `"sdk"` default — will fail with the unknown-alias error after this fix.
This is not a typo case; it is a valid literal model ID that the guard cannot
distinguish from a typo without the now-required `--profile` signal. Record
this explicitly in the task's acceptance criteria and consider whether the
error message should suggest `--profile` as the remedy for users hitting
this specific shape.

**Judge path (review F004).** `_resolve_judge_model` (review.py:1160-1176)
has the identical shape: `resolve_model_alias(raw_model)` returning `(name,
None)` flows into `_resolve_profile(profile_flag or alias_profile, template)`
with no guard, so `sq review resolve <index> --model <typo>` reproduces #67
on this sibling path. This fix applies the same guard to
`_resolve_judge_model`, sharing the check as a small helper (e.g.
`_reject_unknown_alias(name, profile_flag, template) -> None`, raising or
returning the error) called from both `_run_review_command` and
`_resolve_judge_model` — rather than duplicating the three-way profile check
inline at both call sites.

**Explicitly out of scope, unchanged:** the pipeline `--model` runtime
passthrough (`ModelResolver.resolve`) — covered by #60's existing non-goal —
and the loader's `_validate_model_alias` (loader.py:229-248), which already
fail-closes unresolved pipeline/step-level aliases when validation runs and
needs no change here.

## Fix 2 — #103: `--restore` matches sibling projects by prefix

**Current behavior.** `_handle_restore`
(`src/squadron/cli/commands/summary_instructions.py:91-131`) resolves the
current project name via `gather_cf_params` — which, per
`src/squadron/pipeline/summary_render.py:73`, sets `project_name =
resolved_cwd.name`, the checkout directory's basename, **not** a value read
from Context Forge (CF's `get_project()` is consulted only for `slice`/
`phase`). It then globs `_SUMMARIES_DIR.glob(f"{project}-*.md")` (line 111).
This is a bare prefix match: for `project == "squadron"`, it also matches
`squadron-pr-*.md` and any other sibling project whose directory name starts
with `squadron-`. `_summary_key` (lines 82-88) has the same flaw via
`path.stem.removeprefix(f"{project}-")`. With no `--key`, `_select_summary`
(lines 134-154) just takes `matches[0]` (most recently modified) — so a
recently-touched sibling project's summary can silently win over the current
project's own.

**Correction from slice review (20260917):** an earlier draft of this fix
proposed filtering matches whose *stripped* remainder started with another
known project's prefix. That predicate is a no-op on the motivating case:
for stem `squadron-pr-p5a` and project `squadron`, the remainder after
stripping `squadron-` is `pr-p5a`, which does not start with `squadron-pr-` —
stripping the first project's prefix already consumes part of the second
project's name, so the check can never fire. The correct predicate tests the
**unstripped stem** against `{other_project}-` for every other known project
name. The review also found that "known project names come from the same CF
source" was false — no such source exists (`ContextForgeClient` exposes
`is_available`, `list_slices`, `list_tasks`, `get_project`, `get_config`; no
project-listing operation). This fix restates both correctly below.

**Known-project-name source.** There is no project registry to query. The one
non-circular source available is the filesystem: sibling checkout
directories under the current checkout's parent are real project names
regardless of what summary files happen to exist. `gather_cf_params` already
derives the current project name the same way (`resolved_cwd.name`), so
deriving siblings from `resolved_cwd.parent.iterdir()` (directory entries
only, excluding the current project's own name) is consistent with the
existing convention rather than a new one. This is a heuristic, not a
complete solution — it only catches sibling projects that happen to be
checked out next to the current one on the same machine, which is the exact
layout that produced #103's report (sibling worktrees under one parent) but
will not catch a same-prefix project checked out elsewhere. State this
limitation in the code comment rather than implying completeness.

**Fix.** After computing `matches` at line 110-114: derive `sibling_projects`
from `Path(cwd).resolve().parent.iterdir()` (directory names other than
`project` itself), then partition `matches` into `clean` (stem does not start
with `f"{sibling}-"` for any `sibling` in `sibling_projects` where `project`
is not itself a prefix-continuation of `sibling`) and `excluded` (the rest).
Default (no `--key`) selects `matches[0]` restricted to `clean` — never
`excluded` — matching today's `_select_summary` shape but scoped to the
unambiguous set.

**Disambiguation policy (required by review F001 and F001-followup):** the
first draft required both "apply the identical predicate inside
`_summary_key` so key-matching can't disagree with default-selection" and
"an excluded file must remain restorable via `--key`" — these do not compose,
since removing a match from the matchable set makes it unselectable under any
key. Resolved: `excluded` files are **not** removed from the set `--key`
matches against; only the **default** (no-`--key`) selection is restricted to
`clean`. `_summary_key`'s return value is unchanged for every stem, including
excluded ones — it always returns `path.stem.removeprefix(f"{project}-")`,
so an excluded file's key is that same value (e.g. `pr-p5a` for stem
`squadron-pr-p5a` under project `squadron`) and is not given special-cased
ambiguity; the caller who already knows the exact stem-derived key can
still pass it via `--key`. What changes: the stderr listing (line 126) marks
excluded entries distinctly (e.g. a trailing `(excluded from default —
matches sibling project 'squadron-pr'; use --key '{key}' to restore)`), and
the no-`--key` path in `_handle_restore` raises the same "no summary files
found" error when `clean` is empty even though `matches` (unfiltered) is not
— rather than silently falling through to an excluded file.

**Failure modes on the new I/O path (required by review F002).** `iterdir()`
on the parent directory is a new filesystem call with its own failure modes,
per this project's own precedent (916's design named the hang/timeout/no-repo
family explicitly for a new git call, and its review confirmed that rigor).
Enumerated: parent directory unreadable (permissions), parent removed
between `resolve()` and `iterdir()` (race), or cwd resolving to a filesystem
root with no meaningful "siblings" concept — all surface as `OSError` (or a
subclass) from `iterdir()`, uncaught today. Handling: catch `OSError` around
the sibling-derivation call specifically, log at WARNING with the parent path
and the exception, and degrade to an empty `sibling_projects` set — i.e. fall
back to today's unfiltered behavior for that single invocation rather than
crashing `_handle_restore` entirely. This keeps the enumeration a pure
enhancement: on failure, restore behaves exactly as it does before this fix,
never worse.

## Non-goals

- Issue #67's third suggested item (SDK workspace-trust preflight/remediation
  messaging) is a separate, larger UX concern — not required to fix the
  "silent dispatch of an unknown alias" defect and not included here.
- Issue #60 (`sq models check`, validating alias references across pools/
  pipelines statically) overlaps conceptually but is a separate command-level
  feature, not this runtime dispatch-path fix.
