---
docType: slice-design
slice: pr-review-artifact-naming-drop-the-host-owner-repo-prefix
project: squadron
parent: ../architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260925
dateUpdated: 20260925
status: not_started
---

# Slice Design: PR Review Artifact Naming — Drop the Host/Owner/Repo Prefix

## Overview

Fixes [issue #124](https://github.com/ecorkran/squadron/issues/124). `sq review pr` names its artifact `github.com-ecorkran-squadron-83-review.code.md`, built from `PullRequestRecord.path_key`. The host/owner/repo prefix is redundant wherever the artifact lands in a directory that already belongs to one repository — which is both the common case (the project's own `user/reviews/`) and the built-in default (`~/.config/squadron/reviews/<host>/<owner>/<repo>/`). This slice shortens the name to `pr-{number}-review.{type}.md` and keeps a repository qualifier only where the directory can hold reviews from more than one repository.

The question the plan left open — how "is this PR from this repo" gets decided — is answered by **not asking it**. The reviews directory is already chosen by an explicit, printed precedence rule (`ReviewsDirRule`), and that rule alone says whether the directory is scoped to one repository. No remote inspection, and no "cannot be determined" branch.

## Value

- Short, sortable, tab-completable PR review names that sit naturally beside `380-review.arch.pull-request-workflow.md`.
- Qualification kept exactly where collisions are real (a shared external directory), so nothing that works today starts overwriting.
- The `path_key` single-definition claim gets resolved deliberately rather than left drifting.

## Technical Scope

**In scope**

- New PR artifact stem, qualified or not by the reviews-directory rule (D1, D2).
- `path_key` stays the worktree's name; `PrTarget` stops using it; docstring corrected (D3).
- `metrology/capture.py` error message states that PR reviews are addressed by path (D4).
- A test pinning that `pr/inputs.py`'s `*-review.*.md` glob matches both new forms (D5).
- `file-naming-conventions.md` updated upstream in `ai-project-guide` (D7).

**Excluded**

- Renaming or migrating existing old-name artifacts (D6).
- [#90](https://github.com/ecorkran/squadron/issues/90) — slice-less `--diff-only` review naming. Separate question; stays in Future Slices.
- Resolving `sq metrology sample pr-83` by PR number. Addressed by path only.

## Dependencies

### Prerequisites

None. Initiative 380 (the `sq review pr` path) is complete.

### Interfaces Required

- `ReviewsDirRule` / `resolve_reviews_dir` ([reviews_dir.py](../../../src/squadron/review/reviews_dir.py)) — already returns which rule chose the directory.
- `select_remote` ([remotes.py:123](../../../src/squadron/codehost/remotes.py#L123)) — its guarantee that a reviewed PR's repository is always one of the checkout's remotes (`ForeignRepositoryError` otherwise) is what makes the PROJECT rule safe to leave unqualified.
- `SaveTargetProtocol.filename_stem` — unchanged signature.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `review/reviews_dir.py` — `ReviewsDirRule` | Gains a `repository_scoped` property: `True` for `PROJECT` and `DEFAULT`, `False` for `CONFIG` and `FLAG`. The one place the mapping lives. |
| `cli/commands/review_pr.py` — `PrTarget` | Takes `qualify: bool`. `filename_stem` builds from `number` (and `owner`/`repository` when qualifying) instead of `path_key`. |
| `cli/commands/review_pr.py` — `review_pr` | Resolves the reviews directory **before** building `PrTarget` (today it resolves inside `_save_pr`), passes `qualify=not rule.repository_scoped`. `_save_pr` uses the pre-resolved directory and rule. |
| `codehost/models.py` — `path_key` | Code unchanged; docstring now names one consumer (the worktree) and says why the artifact left. |
| `metrology/capture.py` — `resolve_target` | Non-digit error message says PR reviews are addressed by path. |

### Data Flow

```
sq review pr 83
  → resolve_and_fetch_pull_request        (record: host/owner/repo/number)
  → resolve_reviews_dir(...)  → (dir, rule)     ← moved earlier, still side-effect free
  → PrTarget(record, rules_source, qualify=not rule.repository_scoped)
  → save_review_result(target=...)        → dir / f"{target.filename_stem('code')}.md"
  → prints "Saved review to <path> (<rule>)"   (unchanged)
```

`resolve_reviews_dir` only reads config and checks `is_dir()`, so resolving it before a `--no-save` run is harmless.

### State Management

No new state. The artifact's identity lives where it already does: the `pr:` frontmatter mapping (`host`, `owner`, `repository`, `number`, `url`). Consumers classify by frontmatter, never by filename — the conventions already require that.

## Technical Decisions

### D1 — Qualification follows the reviews-directory rule

| Rule | Directory | Qualified? | Why |
|---|---|---|---|
| `PROJECT` | checkout's `project-documents/user/reviews/` | no | `select_remote` refuses any PR whose repo isn't a remote of this checkout. The directory belongs to that project. |
| `DEFAULT` | `~/.config/squadron/reviews/<host>/<owner>/<repo>/` | no | The path already carries the full identity. |
| `CONFIG` | `review.external_reviews_dir` | yes | Its purpose is collecting reviews for checkouts that have no `project-documents/` — many repositories into one place. |
| `FLAG` | `--reviews-dir` | yes | Arbitrary directory; squadron can't know what else lands there. |

**Rejected: compare the PR's repo with the `origin` remote** (the issue's suggestion). It keys logic on a remote's *name* — a user-controlled label — and gets fork layouts backwards (origin is the fork; the PR usually lives on upstream). It also needs an answer for "no origin", which D1 never needs.

**Accepted edge:** in a fork checkout, PR #83 on the fork and PR #83 on upstream would share `pr-83-review.code.md` in the project directory. `archive_existing_review` preserves the earlier one, and the frontmatter names which PR each is. Fork-side PR reviews are rare enough that qualifying every project review to cover them would undo the slice.

### D2 — Name forms

```
pr-{number}-review.{type}.md                    # repository-scoped directory
pr-{number}-review.{type}.{owner}-{repo}.md     # shared directory
```

`pr-` keeps the non-numeric prefix the conventions call load-bearing: an index-built glob (`83-review.*`) still can't match a PR review. Host is dropped from the qualified form — same owner/repo on two hosts inside one shared directory is not a real case. `{owner}-{repo}` can in theory alias (`a-b`/`c` vs `a`/`b-c`); with an identical PR number in the same shared directory that's not worth a less readable separator.

### D3 — `path_key` stays the worktree's; the artifact moves off it

The scratch worktree must stay fully qualified: every repo's worktrees share `~/.config/squadron/worktrees/`. The "directory and review agree" rationale in `path_key`'s docstring has no reader — the worktree is removed at run end, and `sweep_orphans` identifies worktrees by lock file, not by name. So the split is safe. `path_key` keeps one consumer and its docstring says so, including that the review artifact deliberately stopped using it (slice 926) — so nobody "fixes" the divergence back.

### D4 — Metrology addresses PR reviews by path

`resolve_target` already accepts any review-file path, and a digit index never matched an old-name PR review either — no behavior change. Only the refusal text changes, so it says something true: `Pass a review-file path (PR reviews are always addressed by path), or a slice index with --type.`

### D5 — `pr/inputs.py` glob needs no change

The slice plan said `*-review.*.md` misses `pr-83-review.code.md` for want of a third dotted segment. Verified with `fnmatch`: it matches — the `*` before `.md` absorbs `code`. Both new forms and the old form match. The slice adds a test pinning that, so a future glob tightening fails loudly.

### D6 — Existing artifacts are left alone

This repo has one old-name artifact, already in `user/reviews/archive/`. No migration code: discovery (`sq pr create` provenance, metrology by path) never depends on the name, and a migrator for other repos' stray files is complexity without a consumer. A re-review of an old-name PR writes the new name beside it; the old file stays readable by every consumer. Archive copies take whatever name the live artifact had, so they need nothing.

### D7 — Conventions change goes upstream

`project-documents/ai-project-guide/` is an installed copy, replaced on each guide update. The **Pull-Request Reviews** section is edited in the `ai-project-guide` repo (`/Users/manta/source/repos/manta/ai-project-guide/file-naming-conventions.md`) and pulled in with the next guide update. The edit: both forms, the D1 rule table in one line each, the `pr-` prefix replacing the host prefix in the "non-numeric prefix is load-bearing" paragraph.

## Implementation Details

### Migration Plan

- **Moved:** the PR artifact stem, from `PullRequestRecord.path_key` to `PrTarget`'s own rule.
- **Consumers updated:** `PrTarget.filename_stem`, `review_pr`'s save ordering, `tests/cli/test_review_pr_persistence.py` (lines 59, 62, 74, 175).
- **Unchanged consumers, verified:** `ScratchWorktree.__enter__` (still `path_key`), `pr_comment.marker_for` (uses `key`), `pr/inputs.py` provenance glob (D5), `metrology/capture.py` index glob (D4).
- **Data:** none migrated (D6).
- **Behavior preserved:** everything except the filename — frontmatter, `reviewedSha`, archive-before-overwrite, printed location and rule.

## Integration Points

### Provides to Other Slices

- `ReviewsDirRule.repository_scoped` — reusable by anything else that names artifacts per-directory (#90 may want it).

### Consumes from Other Slices

- 380/383's reviews-directory precedence and `SaveTargetProtocol`. No new contract.
- Context Forge scans reviews by slice-index filename; a `pr-` file matches no index, same as the old prefix. No cf change.

## Success Criteria

### Functional Requirements

- `sq review pr N` in a checkout with `project-documents/user/reviews/` writes `pr-N-review.code.md`.
- With the built-in default directory, writes `pr-N-review.code.md` under `~/.config/squadron/reviews/<host>/<owner>/<repo>/`.
- With `--reviews-dir` or `review.external_reviews_dir`, writes `pr-N-review.code.{owner}-{repo}.md`.
- `--json` produces the same stems with `.json`.
- The scratch worktree directory name is unchanged (`{path_key}-{run_id}`).
- `sq metrology sample pr-83` refuses with the D4 message; `sq metrology sample <path-to-pr-review>` works.
- `sq pr create` still finds a PR review under both new forms.

### Technical Requirements

- `ReviewsDirRule.repository_scoped` defined once; a test asserts every enum member has an explicit value (adding a rule without deciding fails).
- `PrTarget` stem tests cover qualified and unqualified; persistence tests updated to new stems.
- Glob-pinning test in `tests/pr/` for both forms (D5).
- `path_key` docstring updated (D3).
- ruff format, ruff check, pyright zero errors; full suite green.

### Integration Requirements

- Upstream `ai-project-guide` `file-naming-conventions.md` updated (D7).
- `docs/COMMANDS.md` `sq review pr` section names the artifact forms and when the qualifier appears.

### Verification Walkthrough

Run from the squadron checkout (it has `project-documents/user/reviews/`). PR 116 is an existing merged PR; any real PR number works.

1. Project directory — unqualified:
   ```
   sq review pr 116 --no-tools
   ```
   stderr ends with `Saved review to .../project-documents/user/reviews/pr-116-review.code.md (project reviews directory)`.
   ```
   head -12 project-documents/user/reviews/pr-116-review.code.md
   ```
   The `pr:` mapping still names `github.com` / `ecorkran` / `squadron` / `116`.

2. Explicit directory — qualified:
   ```
   sq review pr 116 --no-tools --reviews-dir /tmp/sq-926
   ls /tmp/sq-926
   ```
   Lists `pr-116-review.code.ecorkran-squadron.md`; stderr names `(--reviews-dir)`.

3. Worktree name unchanged: run step 1 without `--no-tools`. The printed `worktree:` path ends `github.com-ecorkran-squadron-116-<run_id>`.

4. Metrology:
   ```
   sq metrology sample pr-116
   ```
   Refuses with the "PR reviews are always addressed by path" message.
   ```
   sq metrology sample project-documents/user/reviews/pr-116-review.code.md
   ```
   Resolves the file.

5. Discovery glob: `pytest tests/pr -k glob` passes for both forms.

6. Clean up the step-1 artifact (`git checkout`/`rm`) unless it's wanted.

## Implementation Notes

### Development Approach

1. `ReviewsDirRule.repository_scoped` + exhaustiveness test.
2. `PrTarget(qualify=...)` and new `filename_stem`; update persistence tests.
3. Reorder `review_pr` to resolve the directory before building the target.
4. `path_key` docstring; metrology message + test; inputs glob test.
5. `docs/COMMANDS.md`; upstream conventions edit in `ai-project-guide`.

Effort: 2/5.

### Special Considerations

- The conventions edit is a commit in a different repository; land it there, don't hand-edit the installed copy here.
