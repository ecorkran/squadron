---
docType: slice-design
slice: review-a-pr
project: squadron
parent: user/architecture/380-slices.pull-request-workflow.md
dependencies: [381, 916, 904]
interfaces: [383, 384, 386]
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Slice Design: Review a PR

## Overview

381 built the boundary: a target resolves to a `ResolvedPullRequest` and a `FetchedRange` whose
`diff_range` is a merge-base range over two refs squadron just fetched. This slice spends that
boundary on the initiative's headline capability — `sq review pr <target>` — by handing the range
and the PR record to the existing code review rather than building a second reviewer.

Three things make it more than wiring. A tool-enabled review must read the *PR's* files, not the
operator's checkout, which means a squadron-owned scratch worktree with a lifecycle that survives
concurrency and process death. The convention inputs (rules, `CLAUDE.md`) must keep coming from
the checkout even when the code comes from the worktree, which is the architecture's two-root
rule and which today's single `cwd` cannot express. And the PR's own prose — title, body,
discussions — is untrusted third-party text that has to reach the model as data it cannot mistake
for instructions.

Until 383 lands, the result is displayed and the existing not-persistable path reports why.

## Value

User value, and the reason the initiative exists. A PR is reviewed with one command, against the
range the host displays, by a reviewer reading the PR's own files and the PR's own claims. The
operator stops doing checkout-guess-diff-copy by hand, and stops reviewing the wrong thing when
the base has moved.

## Technical Scope

### Included

- `src/squadron/cli/commands/review.py`: the `pr` subcommand, at full flag parity with `code`.
- `src/squadron/codehost/worktree.py`: scratch-worktree lifecycle — create, lock, sweep, remove.
- `src/squadron/core/models.py`: one new `AgentConfig` field for the convention root (D1).
- `src/squadron/providers/{sdk,openai}/`: thread that field to the jail and tool binding.
- `src/squadron/review/review_client.py`: read convention inputs from the new root; `_SKIP_KEYS`.
- `src/squadron/review/builders/code.py`: render the PR metadata block (D4).
- `src/squadron/data/templates/code.yaml`: declare the new optional input.
- Tests: worktree lifecycle including orphan sweep, the two-root split, fence containment, flag
  parity, and one recorded live run.

### Excluded

- Persistence of the PR review (383). This slice ends at display plus the not-persistable report.
- Posting (384), PR creation (385), slash-command parity and documentation (386).
- Any pipeline surface for PR targets. The template gains an optional input the pipeline action
  tolerates and ignores; nothing supplies it.
- Changes to `sq review code`'s behavior. Its tests pass unchanged.

## Scope corrections against the plan entry

| Plan text | Finding at design | Disposition |
|---|---|---|
| "the two-root rule, with every convention input loaded from the operator's checkout and only reviewed code from the worktree" | Not expressible through today's seams. `AgentConfig.cwd` is simultaneously the SDK jail root, the `tools.materialize` root, and the directory `_inject_file_contents` reads `CLAUDE.md` from. Pointing it at the worktree moves the convention inputs with it — the precise thing the architecture forbids. | A second field, `convention_root`, threaded `inputs` → `AgentConfig` → both providers. Named decision D1; it is a contract change, not wiring. |
| "the adapter-resolved range ... handed to the existing code review" (implying the range needs the checkout) | Probed on this repository at design time, not assumed: a linked worktree resolves `refs/squadron/...` (the ref store is shared, not per-worktree) and `git diff base...head` across those refs succeeds from inside it. | The range computes correctly from either root. `assert_reviewable_scope` and the diff injection keep taking one cwd and are untouched. The two-root split is about the jail and convention inputs only. Recorded as D2. |
| "PR metadata ... rendered by the code prompt builder as one labeled fenced block" | Correct as far as it goes, but there is a second hole the plan does not name. `_inject_file_contents` iterates *every* input key and injects any value that is a real file path. A `pr` value is rendered text, so it is skipped — unless a body happens to name a real path, which would then be read off disk and injected. | Block goes through the builder as planned, **and** the new key joins `_SKIP_KEYS`. D4. |
| "`--files`" in the parity list | `--files` scopes a review to a glob within one tree. On a PR the reviewable set is the range, and a glob would silently narrow it with no relation to what the host shows. | Accepted with a restriction: `--files` intersects the range rather than replacing it, and is documented as such. D7. |

Effort stays 4/5.

## Dependencies

### Prerequisites

- **381** — `resolve_pull_request`, `fetch_pull_request_refs`, `list_unresolved_discussions`, the
  record types, `build_github_host`, the `ProcessRunner` seam, and `FakeProcessRunner`.
- **916** — merge-base `--diff` semantics (`normalize_diff_spec`), `assert_reviewable_scope`, and
  the review-root unification this slice deliberately splits.
- **904** — the parser's diff-membership location check, which must see the same file set the
  range produced.
- **918** (merged) — `JailSpec`, `materialize(names, cwd, exclude_patterns)`. D1 composes with it
  rather than reopening it.

### Coordination

None outstanding. 918 has merged; `cli/app.py` already registers both `review_app` and `pr_app`.

## Architecture

### Component Structure

```
src/squadron/codehost/worktree.py    ScratchWorktree (context manager), sweep_orphans(),
                                      WorktreeError hierarchy, lock read/write
src/squadron/cli/commands/review.py  review_pr(): resolve → fetch → worktree → review → report
src/squadron/core/models.py          AgentConfig.convention_root
src/squadron/review/review_client.py convention inputs read from convention_root
src/squadron/review/builders/code.py _pr_block(): the fenced, label-neutralized metadata block
```

Dependency direction is unchanged: `cli` → `codehost` → `core`, and `cli` → `review`. The review
package still imports nothing from `codehost`; `review_pr` lives in the CLI layer, which already
imports both. `worktree.py` sits in `codehost` because its lifecycle is keyed by the PR record and
it is host-adjacent, but it names no host and runs only git through the injected runner.

### Data Flow: `sq review pr <target>`

```
target ──(381 boundary)──▶ ResolvedPullRequest + FetchedRange
                                    │
                    sweep_orphans(data_dir)  ← prune dead owners' worktrees first
                                    │
              tools enabled? ──yes──▶ ScratchWorktree(record, run_id)  ← git worktree add
                            └──no───▶ (no tree; review reads the fetched ref alone)
                                    │
   inputs = {cwd: <checkout>, diff: range, pr: <rendered block>,
             review_root: <worktree or checkout>}
                                    │
                    assert_reviewable_scope(range, checkout)   ← D2: either root works
                                    │
                    run_review_with_profile(code template, inputs, ...)
                                    │
                      AgentConfig(cwd=review_root, convention_root=checkout)
                                    ▼
                        ReviewResult ──▶ display ──▶ not-persistable report (until 383)
                                    │
                        ScratchWorktree.__exit__ ← removed on success, failure, and timeout
```

## Technical Decisions

### D1 — The two-root split is a new field, not a new value in `cwd`

`AgentConfig.cwd` answers three questions today, and the architecture requires two different
answers. `convention_root: str | None = None` is added beside it:

- `cwd` keeps its meaning — the jail root, the tree the reviewer reads code from.
- `convention_root` is where "how this project works" is read from: the rules directory and
  `CLAUDE.md`. `None` means "same as `cwd`", which is exactly today's behavior for every
  existing caller, so no other review path changes.

Threaded to both providers that bind tools: the SDK provider passes `cwd` to the agent as it does
now and does not pass `convention_root` (the SDK reads project settings from its own `cwd`, so
`setting_sources: [project]` would read the worktree's — see the risk below); the non-SDK agent
passes `cwd` to `tools.materialize` unchanged. The field's one consumer inside the review package
is `_inject_file_contents`, which reads `CLAUDE.md` from `convention_root` when set.

Rejected: pointing `cwd` at the worktree and copying the rules into it. That makes the artifact's
recorded roots a fiction and leaves `CLAUDE.md` resolution silently following the code.

### D2 — The range needs no split; the probe says so

Probed rather than assumed, on this repository at design time: `git update-ref refs/squadron/probe`,
`git worktree add --detach`, then from inside the worktree `git rev-parse refs/squadron/probe`
resolved and `git diff --name-only base...HEAD` exited 0. Git's ref store is shared across linked
worktrees, so the namespaced refs 381 fetches are visible from both roots.

Consequently `assert_reviewable_scope`, `extract_diff_paths`, `_run_git_diff`, and
`_run_git_diff_filenames` keep taking one cwd and are not touched. They run against the checkout,
which is where `inputs["cwd"]` points. Only the jail and the convention inputs are split.

### D3 — Scratch worktree lifecycle

One worktree per invocation, under `~/.config/squadron/worktrees/` (the existing user config
directory from `config/manager.py`; `data_dir()` is package data and is the wrong home).

- **Name:** `<host>-<owner>-<repo>-<number>-<run_id>`, the record's `key` with path separators
  flattened plus a per-run id, so two concurrent reviews of one PR never collide.
- **Creation:** `git worktree add --detach <path> <head_ref>` against the fetched head ref,
  bounded by the git timeout. Submodules are initialized (`git submodule update --init
  --recursive`) in it; a submodule that cannot be fetched fails the review naming it, rather than
  leaving paths the reviewer will cite as missing.
- **Lock:** a `lock.json` in the worktree carrying pid **and** that process's start time, so a
  recycled pid does not read as alive.
- **Sweep:** every invocation, before creating its own, prunes worktrees whose owner is gone
  (pid absent, or present with a different start time), then `git worktree prune`. An orphan never
  blocks a new review — the per-run id guarantees it.
- **Removal:** on success, on failure, and on timeout — a context manager, so no path returns
  without passing through it. A worktree that cannot be removed logs at WARNING and names the path;
  the review's own result still stands.

### D4 — PR metadata reaches the model as data, through the builder

One new optional template input, `pr`, carrying the already-rendered block. Rendered by
`code_review_prompt` because the architecture fixes fence policy in one place, and because
`_inject_file_contents` cannot carry it safely (see Scope corrections).

Containment is structural, not a label:

- The outer fence is one backtick longer than the longest backtick run anywhere in the content,
  so no inner fence can close it. This is the same defect class as the review parser's
  closer-length bug fixed on 381's review — a fixed-length fence is not containment.
- Any occurrence of the block's own label inside the content is neutralized before emission.
- The whole block is truncated by the existing size discipline (`review.max_file_size_bytes`),
  and states that it was truncated.

The key joins `_SKIP_KEYS` so injection never treats its value as a path. The pipeline `review`
action tolerates an optional key it does not populate, so it is unaffected.

Content: title, body, linked issue numbers, and unresolved discussions (path, line, author, body).

### D5 — Tools decide which tree, and the artifact records both

With tools enabled the jail is the worktree. With `--no-tools` there is no tree to make, the
review reads the fetched ref through the injected diff alone, and no worktree is created — so the
common path costs nothing. Both roots are reported with the result and, from 383, recorded in the
artifact.

### D6 — Until 383, not persistable, with the reason

`_warn_not_persistable` currently hard-codes "no slice identifier", which is untrue here and would
misdirect the operator. It gains a reason parameter; the slice paths pass today's wording
unchanged, and the PR path passes one naming PR-keyed persistence as not yet available. The
existing `SaveOutcome.NOT_PERSISTABLE` path and exit behavior are otherwise untouched.

### D7 — `--files` intersects, never replaces

On `sq review code` a glob can stand alone. On a PR the range is the truth, so `--files` narrows
within it. A glob matching nothing in the range is an error naming both, not an empty review.

## Integration Points

### Provides

- `sq review pr <target>` and its `ReviewResult` — the path 383 persists and 384 posts.
- `codehost.worktree.ScratchWorktree` and `sweep_orphans`.
- `AgentConfig.convention_root` — available to any later review that reads code and conventions
  from different trees.
- The `pr` template input.

### Consumed by

- 383: the result and both roots, for the PR-keyed artifact and its rules-source provenance.
- 384: the artifact 383 persists; nothing directly from here.
- 386: the CLI surface its slash-command parity must match.

## Success Criteria

### Functional

- `sq review pr` on a PR whose base has moved produces the same changed-file set the host's PR
  view shows. `sq review code --diff` behavior is unchanged — its existing tests pass untouched.
- With tools enabled, findings cite paths that exist in the PR head; the operator's checkout is
  byte-identical before and after, including after a forced failure mid-review (asserted by
  `git status --porcelain` and `git for-each-ref refs/heads` around a review that raises).
- Two concurrent tool-enabled reviews of the same PR both complete with distinct worktrees; a
  worktree orphaned by a killed process is pruned by the next invocation and does not block it.
- A PR that edits the rules directory or `CLAUDE.md` is reviewed against the **checkout's**
  versions — asserted by a worktree whose rules differ from the checkout's, with the prompt
  carrying the checkout's.
- A PR body containing a triple-backtick fence and a copy of the block label does not escape the
  block; a test asserts the rendered prompt keeps it intact. A four-backtick run inside forces a
  five-backtick outer fence.
- A repository with submodules yields a worktree in which submodule paths exist; an unfetchable
  submodule fails the review naming it.
- Every existing review flag (`--model`, `--profile`, `--no-tools`, `--rules`, `--rules-dir`,
  `--no-rules`, `--files`, `-v`, `--output`, `--json`, `--no-save`) behaves on `sq review pr` as
  on `sq review code`; a table-driven test covers each.
- Running without 383 prints the not-persistable warning naming PR persistence, and exits on the
  verdict exactly as the other review paths do.

### Technical

- `ruff format`, `ruff check`, and `pyright` clean; zero pyright errors.
- No module under `review/` imports `squadron.codehost` — the existing import-graph test still
  passes with `worktree.py` added.
- `convention_root` defaulting to `None` leaves every existing `AgentConfig` construction
  behaviorally identical; a test pins that a slice review's prompt is byte-identical before and
  after the field exists.
- Every git call in the worktree lifecycle goes through the injected runner and is bounded; the
  fake runner covers create, sweep, and remove without touching a real repository.

### Verification Walkthrough

Run in a clone of `ecorkran/squadron` with `gh` authenticated, against an open PR.

1. Record the checkout state:
   ```
   git status --porcelain > /tmp/before.status && git for-each-ref refs/heads > /tmp/before.refs
   ```
2. Review with tools, then without:
   ```
   sq review pr <number> -v
   sq review pr <number> --no-tools
   ```
   Both print a verdict and the not-persistable warning naming PR persistence. The first reports
   two roots; the second reports one and creates no worktree.
3. Confirm nothing moved, and no worktree leaked:
   ```
   git status --porcelain | diff - /tmp/before.status
   git for-each-ref refs/heads | diff - /tmp/before.refs
   git worktree list
   ls ~/.config/squadron/worktrees/
   ```
   The diffs print nothing; the worktree list shows only the operator's own; the directory is empty.
4. Orphan sweep: start a review, kill it mid-run, confirm the directory retains a locked worktree,
   then run another review and confirm the orphan is gone and the new review completed.
5. Containment: review a PR whose body contains a fenced block and the literal block label;
   confirm with `-vvv` that the prompt log shows the block intact and the label neutralized.

Steps 3 and 4 for one run are recorded in the DEVLOG entry that closes this slice.

## Risk Assessment

- **Worktree lifecycle under abnormal exit** is the main risk: the sweep is what keeps a killed
  review from accumulating trees. Mitigation: pid plus start time so a recycled pid is not
  mistaken for alive, a per-run id so an orphan can never block, and a test that kills a process
  and asserts the next invocation prunes it.
- **`setting_sources: [project]` on the SDK reads settings from the agent's own `cwd`**, which on
  the tools path is the worktree. So a PR that edits `.claude/settings.json` could influence its
  own review even though `CLAUDE.md` and rules come from the checkout. D1 closes the inputs
  squadron injects; this one is the SDK's own resolution and is not squadron's to redirect.
  Stated rather than assumed away: determine during implementation whether the code template
  should drop `setting_sources` on the PR path, and record the answer. Do not leave it implicit.
- **Submodules in enterprise repositories** may need credentials the fetch does not have.
  Mitigation: named failure rather than a silently incomplete tree.
- **`--files` semantics differ subtly from the code path** (intersect, not replace). Mitigation:
  D7 makes it explicit, an empty intersection is an error, and the help text says so.

## Implementation Notes

### Order

1. `AgentConfig.convention_root` and its threading through both providers, with the
   byte-identical-prompt test. Behavior-preserving, lands alone.
2. `_inject_file_contents` reads `CLAUDE.md` from `convention_root`; `_SKIP_KEYS` gains `pr`.
3. `codehost/worktree.py` with lifecycle and sweep tests against the fake runner.
4. `builders/code.py` — the PR block, fence-length and label-neutralization tests first.
5. `code.yaml` — the optional input; pipeline-action tolerance test.
6. `review.py` — the `pr` subcommand, `_warn_not_persistable`'s reason parameter, flag parity.
7. Live run, DEVLOG entry, CHANGELOG line.

### Testing

- `tests/codehost/test_worktree.py` — create, lock, sweep (live and dead owner), remove on
  success/failure/timeout, unremovable worktree.
- `tests/review/test_code_builder_pr_block.py` — fence length against 3- and 4-backtick content,
  label neutralization, truncation.
- `tests/review/test_convention_root.py` — `CLAUDE.md` from the convention root, and the
  unchanged-prompt pin for existing callers.
- `tests/cli/test_review_pr.py` — flag parity table, not-persistable reason, `--files`
  intersection including the empty-intersection error, checkout-unchanged assertions.
- Live evidence is recorded, not asserted; no test needs `gh`, network, or auth.
