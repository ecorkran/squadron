---
docType: review
layer: project
reviewType: code
slice: post-findings-to-the-pr
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/384-slice.post-findings-to-the-pr.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260917
dateUpdated: 20260917
reviewedSha: 2b33565a2f1f25909fdc8b67fc6b33dcb1eeaaee
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
findings:
  - id: F001
    severity: note
    category: uncategorized
    summary: "Duplicated test fixtures across two test_review_pr_post files"
    location: "tests/cli/test_review_pr_post.py:71-160"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Protocol-driven discovery split keeps partitioning in the caller"
    location: "src/squadron/codehost/github_cli.py:280-304"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Pure composer with one narrowly-scoped exception"
    location: "src/squadron/review/pr_comment.py:1-122"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Staleness check uses a fresh, separately-resolved head"
    location: "src/squadron/cli/commands/review_pr.py:188-202"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Save outcome is independent of post outcome (D6)"
    location: "src/squadron/cli/commands/review_pr.py:455-464"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Failure modes are observable and tested per site"
    location: "src/squadron/cli/commands/review_pr.py:208-292"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Test scripts match the real call sequence"
    location: "tests/cli/test_review_pr_post.py:67-95"
---

# Review: code — slice 0

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [NOTE] Duplicated test fixtures across two test_review_pr_post files

The two new test files share a substantial set of helpers — `_fixture`, `_ok`, `_fail`, `_resolve_script`, `_pr_resolve_payload`, `_comments_page`, `_comment`, `hosts_file`, `patched_host`, `fake_result`, `_arm`, `_runner_of`, `_MARKER`, the `BASE_SHA`/`HEAD_SHA`/`MERGE_BASE` constants, and the `GITHUB`/`_FIXTURES` paths — with effectively identical implementations. The failure-mode file's docstring justifies the split for readability, and the seam is real (one is decision-table-shaped, the other is "one assertion across four sites"), but a `tests/cli/conftest.py` with shared fixtures would remove ~80 lines of pure copy-paste and let the two files keep only the script-tail tables that actually differ. Acceptable for the slice as shipped; worth a follow-up note.

### [PASS] Protocol-driven discovery split keeps partitioning in the caller

Removing the operator filter from `find_marked_comments` is correct: the protocol docstring (D1) explicitly states "partitioning by author ... is the caller's job, because the caller is what reports the non-own matches." `_post_review` then partitions and iterates `theirs + mine[1:]`, logging and printing per-comment reports before any write attempt. The author's `test_find_marked_comments_records_no_identity_call` mechanically enforces the dropped `identify_operator` call.

### [PASS] Pure composer with one narrowly-scoped exception

The module imports exactly `PullRequestRecord` from `codehost.models` and nothing else; `tests/codehost/test_import_boundaries.py` enforces this with both a broad review-package guard (allowing only this one file/symbol) and a precise "names == {PullRequestRecord}" assertion. The marker prefix lives in exactly one place. `_neutralize_marker` defeats the substring match used by `find_marked_comments` without altering rendering. Severity grouping is enforced by tests, and the unknown-severity fallback ("rare but must not vanish silently") is preserved.

### [PASS] Staleness check uses a fresh, separately-resolved head

`_resolve_live_head` reconstructs a `PullRequestTarget` with `form=NUMBER, number=record.number`, which forces the resolver's number-supplied path and avoids the branch-lookup branch. The named `_UNUSED_REMOTE_NAME` constant with an explanatory comment is more readable than an inline `"origin"` literal (which the diff shows but the file supersedes). A failure here refuses the post before any write — verified by `test_head_read_failure_refuses_the_post_with_no_write` and by the parametric `head_read` row in the failure-mode file.

### [PASS] Save outcome is independent of post outcome (D6)

The post runs after `_resolve_save_outcome` regardless of its return value. `test_save_failed_post_succeeded_exits_one_for_save` proves the post still executes when save raises `OSError`, and `test_save_succeeded_write_failed_leaves_the_artifact_in_place` proves the artifact persists when the post fails. Both use `runner.write_calls()` and `tmp_path.glob("*review*")` to assert on durable side effects, not just exit codes.

### [PASS] Failure modes are observable and tested per site

Each of the four host calls (identity, discovery, head_read, write) is wrapped in its own `try/except CodeHostError` that calls `render_code_host_error` (which prints to stderr at WARNING+ via the adapter's own logging) and exits 1. `tests/cli/test_review_pr_post_failures.py` parametrizes over the four sites for both transport failure and timeout, with `_assert_no_successful_write` distinguishing "no attempt made" (identity/discovery/head_read) from "exactly one attempt, no second one racing in" (write). The head_read site also gets an extra "no POST or PATCH was attempted at all" assertion — the one site whose failure mode could be papered over by silently dropping the staleness line.

### [PASS] Test scripts match the real call sequence

The `_resolve_script` reproduces the exact sequence `resolve_and_fetch_pull_request` plus `assemble_pr_metadata` produces (remote enumeration → GraphQL PR resolve → fetch → two rev-parse → merge-base → diff --name-only → GraphQL review-threads), then post-path scripts append the four host calls in the order `_post_review` makes them. `test_every_post_path_call_carries_the_host_timeout` confirms all four post-path calls pass `HOST_COMMAND_TIMEOUT_SECONDS` to the runner.

### Run Digest

- Response length: 5367 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 20190
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
