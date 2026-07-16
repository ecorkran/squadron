---
docType: notes
layer: project
project: squadron
audience: [human, ai]
description: Append-only log of process decisions and design reasoning that has no home in other document types
dateCreated: 20260716
dateUpdated: 20260716
status: in_progress
---

# Overview

Each entry is an h2 heading `## YYYYMMDD — Title`, newest first, followed by
**Context** (what prompted it), **Decision** (what was settled), **Rationale**
(why), and optionally **Follow-ups** (issues/slices/docs affected). Entries are
written in timeless decision language — no session transcripts, no line numbers
that drift. When the file exceeds the standard size limit, split per
file-naming-conventions (`-1`, `-2`, …).

# Entries

## 20260716 — A fix for one silent-fallback bug shipped with a second, undetected one already inside it

**Context:** Issue #14 (fixed and closed earlier this same day, commit `17f3ab1`). The diff-range resolver's unsafe last-resort fallback (unscoped commit-message grep, matching bare slice-number tokens in unrelated commits) was removed and replaced with a loud `DiffRangeUnresolvedError` when neither of the two remaining structural paths — local branch, or merge commit on main — resolves. This was verified at the time with 2133 passing tests and a live check against an intentionally-unresolvable slice number. Later the same day, running `sq review code` against slice 303 — work from the *immediately preceding* session — hit that same "no local branch and no merge commit found" error, even though the branch exists locally and a real merge commit is on `main`.

**Decision:** No process change to the fix itself is needed once the actual defect was found: `_find_merge_commit`'s `--grep` pattern searched for the branch-naming word order (`{slice}-slice`), but this project's real merge commit messages use the reversed prose order ("Merge slice {slice}: ..."), so path 2 could never match a real merge commit and silently failed shut. Fixed the pattern to match both orders with explicit non-digit boundary anchors (POSIX ERE has no `\b`), and — critically — added a test that runs the real `grep -E` pattern against literal commit-message strings rather than mocking `subprocess.run` and asserting only on stdout-parsing.

**Rationale:** The existing `TestFindMergeCommit` tests were shaped exactly like the anti-pattern this project's own parsing-rules guidance warns about: they supplied `mock_result.stdout` by hand and asserted the *parsing* of that string was correct, which can never catch a grep *pattern* that never matches real input — the test fixture never contained the actual format the code would consume in production. The deeper process failure: the #14 fix was reviewed and verified the same day it shipped, with a full green test run and a live manual check, and still missed that the fallback path it was leaving in place (path 2, merge-commit detection) was already broken and had likely been dead code for a while. "All tests pass" was treated as sufficient verification for a fix whose entire premise was removing a fallback and trusting the remaining paths — but neither remaining path had ever been exercised against a real, once-merged, currently-existing branch in this repo. The fix needed for #14 was correct in isolation; the verification was not comprehensive enough to notice a neighboring path was silently non-functional. Going forward, when a fix's safety argument rests on "path X remains as a working fallback," that path must be positively demonstrated against real repository state, not just left standing because it existed before.

**Follow-ups:** No issue number filed (a same-day continuation of #14, not a new bug in an unrelated feature); fix applied directly in `src/squadron/review/git_utils.py` (`_find_merge_commit` grep pattern) with new tests in `tests/review/test_git_utils.py::TestFindMergeCommit::test_grep_pattern_against_real_git`. Verified live against slices 301, 906, 909 (now resolve) and 300 (still correctly unresolved — genuinely has no merge-commit-into-main, only main-into-branch merges, since it was squash-merged with no true two-parent commit).

