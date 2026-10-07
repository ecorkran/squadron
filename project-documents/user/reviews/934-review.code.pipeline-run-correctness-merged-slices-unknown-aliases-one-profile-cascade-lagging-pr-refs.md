---
docType: review
layer: project
reviewType: code
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: cc3674f61d48f5f02f5a66a97c5555db74806982
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
durationSeconds: 38.2
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Fast-forward-merged slices are no longer reconciled in `--resume --item`"
    location: "src/squadron/pipeline/item_resume.py:294-308"
  - id: F002
    severity: concern
    category: conventions
    summary: "The 7-character sha display length is hard-coded in two places"
    location: "src/squadron/codehost/models.py:130"
  - id: F003
    severity: concern
    category: performance
    summary: "`merged_slice_branches` walks the full first-parent history on every call"
    location: "src/squadron/pipeline/git_ops.py:157-185"
  - id: F004
    severity: concern
    category: design
    summary: "`refs.py` is now far over the file-size guideline and mixes responsibilities"
    location: "src/squadron/codehost/refs.py"
  - id: F005
    severity: note
    category: design
    summary: "`resolve_and_fetch_pull_request` now prints to stderr"
    location: "src/squadron/cli/commands/pr.py:94-105"
  - id: F006
    severity: note
    category: housekeeping
    summary: "Leftover local `api-head` ref"
    location: "src/squadron/codehost/refs.py#ensure_api_head"
  - id: F007
    severity: note
    category: testing
    summary: "One test imports private helpers from another test module"
    location: "tests/cli/test_review_pr.py:471-485"
  - id: F008
    severity: pass
    category: design
    summary: "Shared review-profile cascade, logging scope and failure observability"
    location: "src/squadron/review/profile_resolution.py"
---

# Review: code — slice 934

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Fast-forward-merged slices are no longer reconciled in `--resume --item`

`_select_item` used to reconcile a slice that cf marks COMPLETE when `merge-base --is-ancestor <branch> <target>` succeeded. That check accepted fast-forward merges. It now calls `merged_slice_branches`, which counts a slice as merged only for a `--no-ff` merge whose tip is off the first-parent chain. The tests confirm this (`test_fast_forward_merged_branch_is_not_merged`).

A slice that cf reports COMPLETE and that was fast-forwarded into the target used to reconcile to PASSED. It now falls through to `REJECTED` with "complete but … is not merged into …". The `--no-ff` guarantee is only asserted for the pipeline's own merge step. Slices merged by hand or by the PM, or under older behavior, are not covered. Either keep the old ancestor test for the cf-COMPLETE branch, or add a test for the ff + COMPLETE case that documents it as intentionally rejected.

### [CONCERN] The 7-character sha display length is hard-coded in two places

`errors.py` defines `_SHA_DISPLAY_LENGTH = 7` and a `_short()` helper. `RefAdjustment.describe` then repeats `self.used_sha[:7]…` as a literal. The project rule is one definition per value, so a change to the length would have to be made in two files. Export one helper (for example from `models.py`, which `errors.py` already imports) and use it in both.

### [CONCERN] `merged_slice_branches` walks the full first-parent history on every call

Each call runs `rev-list --first-parent <target>` and builds a set of every commit. `_merged_open_slices` runs it unconditionally, even when no candidate slice has a design file. `_open_dependencies` runs it again per resume. On a large repository this is wasted time and memory. Short-circuit when there are no candidates. Alternatively, test each tip with `merge-base --is-ancestor` plus a bounded `rev-list --first-parent --merges` check, instead of materializing the whole chain.

### [CONCERN] `refs.py` is now far over the file-size guideline and mixes responsibilities

The file is roughly 500 lines against a ~300-line guideline. It now holds fetch orchestration, base verification, head-lag resolution, API-head acquisition and ref repointing. `ensure_api_head`, `_resolve_head` and the `_HeadRelation` logic could move to their own module (for example `head_resolution.py`), leaving `refs.py` as the entry point. A related point is the two `_is_ancestor` helpers, in `refs.py` and `git_ops.py`. They have different failure semantics (fail-closed with a log versus raising `GitStateUnknownError`), and nothing in the code says so. A short comment would stop the next reader from merging them.

### [NOTE] `resolve_and_fetch_pull_request` now prints to stderr

`_print_adjustments` renders output from a resolution helper that each command calls. This is what makes the print happen exactly once across `show` and `review pr`. It also means a future caller of the helper gets unrequested output. Consider returning the adjustments and having the commands print them.

### [NOTE] Leftover local `api-head` ref

`refs/squadron/pr/<remote>/<n>/api-head` is created and never removed. It is namespaced and harmless, but it accumulates across PRs. A comment saying that is deliberate, or a cleanup, would help.

### [NOTE] One test imports private helpers from another test module

It imports `_lagging_script` and `_resolved_pr83` from `tests/codehost/test_github_cli.py`. That couples the two test files. Moving the helpers into a shared fixtures module would be more robust.

### [PASS] Shared review-profile cascade, logging scope and failure observability

The profile cascade for `sq review` and pipeline review steps is now one implementation, with a parity test over every source. `code_host_logging` is exception-safe and idempotent, and it propagates to root handlers. The new I/O paths (timeouts, `update-ref` failures, API-head fetch failures) all raise typed `CodeHostError`s with a WARNING log, and tests assert on them. The sha check rejects a fork's same-named branch. Git failures in the merged-slice predicate fail loudly rather than reopening merged slices.

## Response (20261007)

- **F001, fast-forward in `--resume --item` — fixed.** `merged_slice_branches` takes `fast_forward_counts`, and `_select_item` passes it when cf reports the slice COMPLETE, so a fast-forwarded or hand-merged branch reconciles as it did before. For a slice cf shows open the `--no-ff` shape is still required, so a branch with no work of its own is never read as merged. Tests: `test_fast_forward_counts_*` and `test_a_complete_slice_fast_forwarded_into_the_target_still_reconciles`.
- **F002, sha display length — fixed.** `SHA_DISPLAY_LENGTH` and `short_sha()` live in `codehost/models.py`; `errors.py` and `RefAdjustment.describe` both use them.
- **F003, first-parent walk — partly fixed.** The target's history is no longer read when no candidate slice has a branch (test asserts only `for-each-ref` runs). The `rev-list --first-parent` pass itself stays: it is one linear read per call and the design chose it over per-tip merge scans (D1); a bounded alternative would need a merge-commit scan per tip and is not worth the complexity at this size.
- **F004, `refs.py` size and the two ancestry helpers — fixed.** `refs.py` is split: `git_refs.py` (bounded git reads and timeouts, 94 lines), `head_resolution.py` (API-head fetch, relation, repointing, 233 lines), and `refs.py` (the fetch entry point and base verification, 246 lines). Importers moved to the new homes. Both `is_ancestor` helpers now say why they differ: a wrong "no" in codehost ends in a rerunnable error, in the pipeline it would reopen a merged slice.
- **F005, printing from the shared helper — no change.** Printing in `resolve_and_fetch_pull_request` is what guarantees `pr show` and `review pr` each print once and no caller can forget. The docstring now says so.
- **F006, leftover `api-head` ref — fixed.** `ensure_api_head`'s docstring records that it is left in place, like the base and head refs, namespaced and force-updated by the next fetch.
- **F007, test cross-import — fixed.** The shared setup moved to `tests/codehost/lagging_support.py`.
- Final finding: pass.

### Run Digest

- Response length: 4736 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 38.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
