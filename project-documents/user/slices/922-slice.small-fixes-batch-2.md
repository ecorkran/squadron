---
docType: slice-design
slice: small-fixes-batch-2
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260919
dateUpdated: 20260919
status: not_started
---

# Slice Design: small-fixes-batch-2

## Overview

Six independently small, root-caused items bundled into one slice. None shares
code with another; they are batched to avoid a slice per issue.

| Fix | Issue | One-line statement |
|---|---|---|
| 1 | [#65](https://github.com/ecorkran/squadron/issues/65) (findings 2–3) | Declared dependencies do not match what `src/` imports |
| 2 | [#117](https://github.com/ecorkran/squadron/issues/117) | Frontmatter gate fails closed on commits whose staged markdown is all outside cf's scope |
| 3 | [#112](https://github.com/ecorkran/squadron/issues/112) | `ProcessRunner` reports a nonexistent `cwd` as "executable not found" |
| 4 | [#108](https://github.com/ecorkran/squadron/issues/108) | `tool_use` / `tool_result` sdk_type literals are scattered |
| 5 | [#57](https://github.com/ecorkran/squadron/issues/57) | `sq setup` renders routine INSTALL steps as red errors |
| 6 | [#100](https://github.com/ecorkran/squadron/issues/100) | Jail-exclusion refusals flood `-v` review output |

## Value

- **Release flow stops needing `--no-verify`.** Every release commit
  (`CHANGELOG.md` + `pyproject.toml` + `uv.lock`) currently trips the gate
  (Fix 2). Bypassing hooks as routine trains the operator to bypass them.
- **Smaller, honest installs.** `google-adk` pulls a large transitive tree into
  every `pip install squadron-ai` and nothing imports it; `rich` is used in 21
  files and is not declared (Fix 1).
- **Errors that point at the actual cause.** A bad `cwd` currently sends the
  operator to check PATH and the git install (Fix 3); a first-run `sq setup`
  looks broken when it is not (Fix 5).
- **Readable `-v`.** Review output is currently buried under dozens of
  refusal lines for a policy working as designed (Fix 6).
- **One definition per comparison value** (Fix 4), per the project rule.

## Technical Scope

Included: the six fixes below, each with tests. Excluded: see Non-goals under
Implementation Notes — notably the `[serve]` extra
([#118](https://github.com/ecorkran/squadron/issues/118)), which stays deferred.

### Fix 1 — #65: declared dependencies

Verified 20260919 by grepping `src/` for top-level imports:

| Package | Importing files | Action |
|---|---|---|
| `anthropic` | 0 | remove from `[project.dependencies]` |
| `google-adk` | 0 | remove |
| `mcp` | 2 (`tools/mcp_bridge.py`, `tools/cf_tools.py`) | **keep** — #65 listed it as unimported; that is no longer true |
| `rich` | 21 | declare |

`uv.lock` currently resolves `rich` 14.3.2 (transitively, via typer).

Three packages are docstring-only stubs — each file is three lines, a docstring
and `from __future__ import annotations`: `src/squadron/providers/anthropic/`
(`__init__.py`, `agent.py`, `provider.py`), `src/squadron/adk/`, and
`src/squadron/mcp/`. Nothing under `src/`, `tests/`, or `pyproject.toml`
references `squadron.adk` or `squadron.providers.anthropic`.

### Fix 2 — #117: gate scope

`src/squadron/events/builtin/frontmatter_gate.py`, the D12 zero-of-N branch
(`staged_count > 0 and files_checked == 0`). `cf validate frontmatter` silently
skips paths outside its document scope, so `filesChecked: 0` has two meanings
the gate cannot tell apart: "cf resolved against the wrong checkout" (#98, fail
closed is right) and "nothing staged was in scope" (pass is right).

Observed cf scope, probed 20260919 with one path per call:

| Path | `filesChecked` |
|---|---|
| `CHANGELOG.md`, `README.md`, `docs/QUICKSTART.md` | 0 |
| `.claude/rules/python.md` | 0 |
| `project-documents/DEVLOG.md` | 0 |
| `project-documents/ai-project-guide/readme.md` | 0 |
| `project-documents/user/slices/921-slice.small-fixes-batch.md` | 1 |

### Fix 3 — #112: `cwd` misreport

`src/squadron/core/process_runner.py`, `SubprocessRunner.run`. `Popen` raises
`FileNotFoundError` for both a missing executable and a missing `cwd`; the
handler maps both to `ProcessNotFoundError(argv[0])`. One catcher exists:
`codehost/github_cli.py:490`, which converts it to `GitHubCliMissingError`
("gh is not on PATH"). The git call sites in `codehost/remotes.py` and
`codehost/refs.py` do not catch it.

### Fix 4 — #108: sdk_type literals

`core/models.py` already defines `SDK_RESULT_TYPE` and `RATE_LIMIT_EVENT_TYPE`.
The `"tool_use"` / `"tool_result"` literal sites, verified 20260919:

- `providers/sdk/translation.py:62,78` — the **producer** (writes `metadata["sdk_type"]`)
- `pipeline/sdk_session.py:188-189`
- `pipeline/summary_oneshot.py:147`
- `review/review_client.py:271`
- `metrology/audit.py:542,547`

#108 also names `pipeline/actions/dispatch.py:174`; that line no longer
contains either literal.

### Fix 5 — #57: setup iconography

`cli/commands/setup.py` `_ICON` maps `StepKind.INSTALL` and
`StepKind.CONFIGURE` to the same `("✗", "red")`. `setup_steps._classify` assigns
INSTALL to any `MISSING` result in `SECTION_INSTALL` / `SECTION_INTEGRATIONS` —
the normal first-run state.

### Fix 6 — #100: refusal log level

`tools/builtin/_shared.py` logs two distinct refusals at WARNING, at two sites
each (the walk filter near line 85 and `jail_violation` near line 173):
a **jail escape** (path resolves outside the root) and a **policy exclusion**
(path is inside an excluded subtree, slice 918 D3 — issue #100 attributes this
to slice 917, which is incorrect). `-v` maps to `INFO`, so
every WARNING prints. A `grep` over a tree containing the excluded `reviews/`
directory emits one line per excluded file.

## Dependencies

### Prerequisites

None. Each fix is independent of the others and of any open slice.

### Interfaces Required

- `cf validate frontmatter --json` — existing contract (`filesChecked`, exit code). Unchanged.
- `ProcessRunner` protocol — extended with one additional documented exception (Fix 3).

## Architecture

### Component Structure

No new modules. Each fix edits one existing component:

| Fix | Component | Layer |
|---|---|---|
| 1 | `pyproject.toml`, `uv.lock`, three stub packages | packaging |
| 2 | `events/builtin/frontmatter_gate.py` | events |
| 3 | `core/process_runner.py`, `codehost/github_cli.py` | core / codehost |
| 4 | `core/models.py` + five consumers | core |
| 5 | `cli/commands/setup.py` | CLI |
| 6 | `tools/builtin/_shared.py` | tools |

### Data Flow

Only Fix 2 changes a decision path:

```
pre-commit hook ──staged *.md (repo-relative)──▶ sq events fire commit
    ──▶ FrontmatterGateAction.execute
          cf validate frontmatter --json <all staged paths>      (unchanged)
          files_checked == 0 ?
             ├─ in-scope staged count == 0 ──▶ PASS   (new: nothing cf would check)
             └─ in-scope staged count  > 0 ──▶ FAIL CLOSED (existing D10 worktree message)
```

The hook (`setup_install.py`) passes `git diff --cached --name-only` output, so
staged paths are repository-root-relative.

### State Management

None. No fix adds or persists state.

## Technical Decisions

### Technology Choices

No new libraries. `rich` becomes a declared dependency rather than a new one.

### Patterns and Conventions

**D1 — Fix 1: remove unimported, declare imported, delete the stubs.**
Remove `anthropic` and `google-adk`; add `rich` with a lower bound at the
major version `uv.lock` already resolves. Delete the three docstring-only stub
packages: they exist only as placeholders for the dependencies being removed,
carry no code, and nothing references them. If an Anthropic-API or ADK provider
is built later it arrives with its own dependency and its own package.
`src/squadron/mcp/` is deleted on the same grounds — the real MCP code lives in
`tools/`, and the `mcp` *dependency* stays.

**D2 — Fix 2: always call cf with every staged path; use a scope predicate only to interpret zero.**
The gate keeps passing all staged paths to cf, so cf remains the sole authority
on what gets validated in the normal case. A squadron-side predicate — "is this
path under the cf user-document root" — is consulted **only** in the zero
branch, to count how many staged paths cf should have checked. Zero in scope
means pass; non-zero in scope with zero checked keeps the D10 fail-closed
message, now reporting the in-scope count.

Rejected alternatives:
- *Filter staged paths before calling cf.* Makes squadron's predicate the
  authority: if cf's scope is ever broader than the predicate, in-scope files
  go unvalidated in every checkout. D2 confines that drift to the zero branch.
- *Have cf report skipped files.* The right long-term contract, but it is a
  context-forge change this slice cannot produce. Filed upstream as part of
  this slice (see Implementation Notes); the predicate is removed when it lands.

The document root is defined once as a module constant in
`frontmatter_gate.py`. The predicate compares normalized path parts, not string
prefixes, so `./project-documents/user/x.md` and
`project-documents/user/x.md` classify the same.

Residual drift, accepted: if cf skips some markdown *under* the user-document
root, a commit staging only such files still fails closed. That is today's
behavior for those files, not a regression.

**D3 — Fix 3: a distinct exception, classified inside the existing handler.**
Add `ProcessCwdNotFoundError(cwd)` beside `ProcessNotFoundError`. In the
existing `except FileNotFoundError` handler, raise it when `cwd` is not `None`
and is not a directory; otherwise raise `ProcessNotFoundError` as today.
Classifying in the handler rather than pre-checking before `Popen` keeps the
success path free of an extra stat and avoids a check-then-use gap. The
`ProcessRunner` protocol docstring documents the new exception.
`SubprocessRunner` is the only production implementation. The one other
implementation, `tests/codehost/fake_runner.py::FakeProcessRunner`, raises
whatever `Exception` a test scripts and so needs no change — tests produce the
condition by scripting a `ProcessCwdNotFoundError`. The protocol obliges no
caller to handle it: it signals a configuration error and is meant to surface.
`github_cli.py` must not convert it to "gh is not on PATH": it lets
`ProcessCwdNotFoundError` propagate, after logging at WARNING. A missing
working directory is a configuration error, not a code-host condition, so it
does not join the `CodeHostError` hierarchy.

**D4 — Fix 4: two constants beside the existing two.**
`TOOL_USE_TYPE` and `TOOL_RESULT_TYPE` in `core/models.py`, referenced by the
producer in `translation.py` and all four consumers. `cli/commands/task.py:47`
compares `metadata["type"]`, a different key on the daemon message path, and is
left alone.

**D5 — Fix 5: INSTALL gets its own neutral icon; copy is untouched.**
`StepKind.INSTALL` maps to a non-error glyph and color, distinct from all three
other kinds; `StepKind.CONFIGURE` keeps the red ✗. The `detail="not on PATH"`
strings live in `doctor_checks.py` and are shared with `sq doctor`, where that
wording is accurate diagnostic output — they are not changed.

**D6 — Fix 6: exclusions log at DEBUG; escapes stay at WARNING.**
At both sites, the *policy exclusion* record drops to DEBUG (visible at `-vv`);
the *jail escape* record stays WARNING. An escape means something reached for
the trust boundary; an exclusion is slice 918's policy working as designed and
is not a failure mode. This deliberately amends 918 D3 ("Silent to the model,
WARNING to the operator") for the policy-exclusion case only; the
silent-to-the-model half of D3 is untouched. The "one refusal, one record" property of
`jail_violation` and the distinguishable wording are preserved. The docstrings
that state "both are logged at WARNING" are corrected.

## Integration Points

### Provides to Other Slices

- `ProcessCwdNotFoundError` — available to any future `ProcessRunner` caller.
- `TOOL_USE_TYPE` / `TOOL_RESULT_TYPE` — the single definition for new sdk_type consumers.

### Consumes from Other Slices

- Slice 919's gate postures (D10–D14) are preserved; only D12's zero branch gains a condition.
- Slice 918's exclusion semantics (D3: silent to the model) are unchanged; only the operator log level for exclusions moves.

## Success Criteria

### Functional Requirements

1. `[project.dependencies]` contains `rich` and `mcp`, and does not contain `anthropic` or `google-adk`. `uv.lock` is regenerated.
2. `src/squadron/providers/anthropic/`, `src/squadron/adk/`, and `src/squadron/mcp/` no longer exist.
3. A base install in a clean virtualenv runs `sq doctor`, `sq run --help`, and `sq review --help` without `ImportError`.
4. The gate passes when every staged path is outside `project-documents/user/` and cf reports `filesChecked: 0`.
5. The gate still fails closed, with the D10 message, when at least one staged path is under `project-documents/user/` and cf reports `filesChecked: 0`.
6. The gate's behavior is unchanged when cf reports `filesChecked > 0`, an unreadable count, a timeout, or a missing `cf`.
7. `SubprocessRunner.run` with a nonexistent `cwd` raises `ProcessCwdNotFoundError` naming the directory; with a missing executable and a valid or `None` `cwd` it raises `ProcessNotFoundError` as before.
8. `GitHubCli` does not report "gh is not on PATH" for a nonexistent `cwd`, and logs the condition at WARNING.
9. No `"tool_use"` or `"tool_result"` string literal remains in `translation.py`, `sdk_session.py`, `summary_oneshot.py`, `review_client.py`, or `metrology/audit.py`.
10. `_ICON[StepKind.INSTALL]` differs from `_ICON[StepKind.CONFIGURE]` in both glyph and color, and is not red.
11. A policy-exclusion refusal emits no record at INFO or above; a jail-escape refusal still emits exactly one WARNING.

### Technical Requirements

- Each fix has tests. Fix 2's tests cover criteria 4–6 with the real cf JSON shape shown in Technical Scope. Fix 6 has one test per refusal kind asserting level and count, at both sites.
- `ruff format`, `ruff check`, and `pyright` clean; zero pyright errors.
- Full test suite passes.

### Integration Requirements

- A release-shaped commit passes the installed pre-commit hook without `--no-verify`.
- Issues #65, #117, #112, #108, #57, and #100 are closed citing the fixing commits.

### Verification Walkthrough

**Fix 1 — dependencies.**

```bash
python -m venv "$TMPDIR/sq-922" && "$TMPDIR/sq-922/bin/pip" install -q -e .
"$TMPDIR/sq-922/bin/pip" show google-adk anthropic     # expect: not found for both
"$TMPDIR/sq-922/bin/pip" show rich mcp                 # expect: both installed
"$TMPDIR/sq-922/bin/sq" doctor
"$TMPDIR/sq-922/bin/sq" run --help
"$TMPDIR/sq-922/bin/sq" review --help
rm -rf "$TMPDIR/sq-922"
```

If another installed package depends on `anthropic` transitively, `pip show
anthropic` will still find it; in that case confirm via `uv tree` that
`squadron-ai` is not the requirer.

**Fix 2 — gate, against the real hook.** On a scratch branch:

```bash
echo "" >> CHANGELOG.md && git add CHANGELOG.md
git commit -m "test: gate scope"        # expect: squadron.frontmatter-gate: ok
git reset --hard HEAD~1
```

The fail-closed side needs a worktree and is covered by the unit test for
criterion 5; reproducing it live requires the sibling-worktree setup from #98.

**Fix 3 — cwd.**

```bash
uv run python -c "
from squadron.core.process_runner import SubprocessRunner
SubprocessRunner().run(['git','status'], cwd='/nonexistent-922', timeout=5)"
# expect: ProcessCwdNotFoundError naming /nonexistent-922 — not 'executable not found: git'
```

The exact `run` keyword arguments are to be confirmed against the protocol
during implementation.

**Fix 4 — literals.**

```bash
grep -rnE '"tool_(use|result)"' src/squadron/providers/sdk/translation.py \
  src/squadron/pipeline/sdk_session.py src/squadron/pipeline/summary_oneshot.py \
  src/squadron/review/review_client.py src/squadron/metrology/audit.py
# expect: no output
```

**Fix 5 — setup.** Run `sq setup --check` on a machine (or with a PATH) lacking
one integration; the missing step shows the new neutral icon, not a red ✗.
The `--check` flag name is to be confirmed against `sq setup --help`.

**Fix 6 — refusals.** #100's own repro:

```bash
uv run sq review tasks 919 -v --model deepseek4-flash
# expect: no "refusing excluded path" lines; the same command with -vv shows them
```

**Gate.** `ruff format --check . && ruff check . && pyright && pytest`.

## Implementation Notes

### Development Approach

Order: Fix 2 first — it unblocks hook-clean commits for the rest of the slice —
then 3, 4, 6, 5, and Fix 1 last, since it regenerates `uv.lock` and is the one
most likely to conflict with anything else in flight. One commit per fix.

File a context-forge issue asking `cf validate frontmatter --json` to report
skipped-as-out-of-scope paths, and link it from a comment at the D2 predicate,
so the predicate has a recorded removal condition.

### Special Considerations

- **Fix 1 is a user-visible install change.** Add a CHANGELOG entry: two dependencies dropped, `rich` declared.
- **Fix 6 changes what slice 918's tests assert.** Expect existing tests pinned to WARNING for exclusions; update them rather than adding parallel ones.

### Non-goals

- The `[serve]` extra and lazy `serve` import — deferred, [#118](https://github.com/ecorkran/squadron/issues/118).
- Consolidating the scattered `project-documents/user/...` path constants across `review/`, `metrology/`, `pipeline/`, and `events/`. Fix 2 adds one constant and does not touch the others.
- Pruning excluded subtrees at walk descent so they are never visited. It would remove the per-file refusals at the source, but changes where exclusion is enforced (the walk filter's docstring records enforcing at candidate production as deliberate).
- Rewording `doctor_checks.py` detail strings.
- Comparing `filesChecked` against the in-scope count for partial mismatches; the gate's check remains zero-of-N.
