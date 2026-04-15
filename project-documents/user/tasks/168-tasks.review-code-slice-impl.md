---
docType: tasks
slice: review-code-slice-impl
project: squadron
lld: user/slices/168-slice.review-code-slice-impl.md
dependencies: []
projectState: v0.4.0 on main at 61c0c7f, working tree clean. sq review code <N> already resolves slice number and calls resolve_slice_diff_range, but the commit-grep path (step 3) is missing — slices merged directly to main without a surviving branch fall back to --diff main. Slice 167 (per-action model override) is designed but not yet implemented.
dateCreated: 20260414
dateUpdated: 20260414
status: not_started
---

## Context Summary

- Working on slice 168: `sq review code` slice implementation review.
- Core change: add commit-message grep as step 3 in
  `resolve_slice_diff_range` (`src/squadron/review/git_utils.py`).
- Pattern: `git log --oneline --all --grep="\b{N}\b"` — broad, no type
  filtering. Oldest-to-newest commit range. Diff exclude patterns on
  the code review template strip `.md` and doc files before review.
- Also: add `--fan N` to `sq review code` CLI — accepted, warned,
  ignored. Placeholder for slice 182 fan-out integration.
- No new subcommand. No behavior changes to existing `--files` /
  `--diff` paths.

---

## Tasks

### Phase 6: Implementation

- [ ] **T1 — Add commit-grep resolution to `resolve_slice_diff_range`**
    - [ ] In `src/squadron/review/git_utils.py`, add
          `_find_commit_range(slice_number, cwd) -> str | None` that
          runs `git log --oneline --all --grep="\b{N}\b"`, collects
          all matching hashes, returns `"{oldest}^..{newest}"` or
          `None` if fewer than one commit found.
    - [ ] Insert as step 3 in `resolve_slice_diff_range`, between the
          existing merge-commit check and the fallback warning.
    - [ ] Verify the existing fallback warning still fires only when
          all three paths fail.

- [ ] **T2 — Add `--fan` flag to `sq review code`**
    - [ ] In `src/squadron/cli/commands/review.py`, add
          `fan: int | None = typer.Option(None, "--fan", ...)` to
          `review_code`.
    - [ ] If `fan` is not None, print a warning:
          `"--fan is reserved for future fan-out support (slice 182); ignored."`
          then proceed normally.
    - [ ] No other behavior change.

- [ ] **T3 — Tests for `_find_commit_range`**
    - [ ] Branch found → returns three-dot range (existing path,
          confirm still works).
    - [ ] Merge commit found → returns parent diff (existing path,
          confirm still works).
    - [ ] Commit grep finds matches → returns `{oldest}^..{newest}`.
    - [ ] Commit grep finds exactly one commit → returns
          `{sha}^..{sha}` (single commit).
    - [ ] No matches anywhere → fallback warning, returns `"main"`.
    - [ ] Use `subprocess` mocking or a real temp git repo fixture
          (prefer the latter if one already exists in the test suite).

- [ ] **T4 — Verify diff exclude patterns filter doc files**
    - [ ] Confirm `diff_exclude_patterns` on the `code` template
          includes `.md` and task/doc file patterns.
    - [ ] If missing entries, add them to
          `src/squadron/data/templates/code.yaml`.
    - [ ] Spot-check: running `git diff {range} -- '*.py'` for a
          slice-181-style range produces only code files.

### Phase 7: Ship

- [ ] **T5 — Format, type-check, test**
    - [ ] `ruff format` changed files.
    - [ ] `pyright` clean on changed files.
    - [ ] `pytest` full suite green.

- [ ] **T6 — Commit and update changelog**
    - [ ] Semantic commit: `feat: resolve slice impl diff via commit grep`.
    - [ ] Append bullet to `CHANGELOG.md` under `[Unreleased]`.
    - [ ] Append note to `DEVLOG.md`.

---

## Implementation Notes

_(Populate during implementation.)_

---

## Open Questions

- [ ] **Single-commit edge case:** if only one commit matches the grep,
      `{sha}^..{sha}` is an empty range. Should we use `{sha}^!`
      (single-commit diff) instead? Decide in T1.
