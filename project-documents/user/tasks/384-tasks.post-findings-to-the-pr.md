---
docType: tasks
slice: post-findings-to-the-pr
project: squadron
lld: user/slices/384-slice.post-findings-to-the-pr.md
dependencies: [381, 383]
projectState: "383 merged to `squadron-pr`; `sq review pr` reviews and persists. 381's comment operations (`find_own_comment`, `post_comment`, `update_comment`, `identify_operator`) are implemented over `gh` and fake-runner tested, with no production caller — this slice is their first. Design reviewed (CONCERNS, all findings addressed) at a527599a."
dateCreated: 20260916
dateUpdated: 20260916
status: not_started
---

## Context Summary

- Working on the **post-findings-to-the-pr** slice (384), fourth of six in the 380 pull-request-workflow initiative.
- **Current state:** 383 gave `sq review pr` a persisted artifact. Nothing reaches the pull request. 381 built the transport — four comment/identity operations over `gh`, covered by the fake runner, deliberately with no caller — so this slice adds behavior, not transport.
- **What this slice delivers:** an opt-in `--post` that writes the review to the PR as one comment, idempotent per authenticated login through a hidden marker, with `--dry-run`, identity refusal, and a staleness statement.
- **The slice is small in code and precise in contract.** Most tasks below are one function or one decision branch. The care goes into three places: the protocol change (Task 1), the composer's containment and size rules (Task 2), and the failure matrix (Task 6).
- **One breaking protocol change (D1).** `find_own_comment` → `find_marked_comments`. 381's signature returns `HostComment | None` and filters to the operator inside the adapter, which structurally cannot express two of the architecture's own idempotency requirements — other operators' marked comments and the operator's own duplicates are discarded before the caller sees them. It has no production caller, so the change is contained to this slice; the criterion is zero remaining references.
- **Two things must not drift, and both are structural rather than disciplinary.** The dry-run body and the posted body come from one `compose_comment` call bound to one variable (D3). The comment and the artifact both draw from `structured_findings`, so they cannot disagree about what was found (D2).
- **The parent architecture and 383's Provides were already updated** when the design was reviewed. No task below edits them; they are done.
- **Next planned slice:** 385 (Create a PR with a Good Message), which depends on 381 only and does not consume anything this slice produces.
- Work commits directly to `squadron-pr` (integration branch) through Phase 5; Phase 6 implementation uses branch `384-slice.post-findings-to-the-pr`.

### Reference

Design decisions are cited as **D1**–**D8**; see the LLD rather than duplicating them here. Tasks follow the design's implementation order (LLD, "Implementation Notes → Order"). The decision table in **D5** is the specification for Task 5; the failure matrix in **D8** is the specification for Task 6.

---

## Task 1 — `find_marked_comments` replaces `find_own_comment` (D1)

Sequenced first and landing alone. Nothing depends on it yet, so a regression here is unambiguous; once Task 5 consumes it, a failure could be either side.

- [ ] **1.1 Change the protocol declaration**
  - [ ] In `src/squadron/codehost/protocol.py`, replace `find_own_comment(self, record, *, marker) -> HostComment | None` with `find_marked_comments(self, record: PullRequestRecord, *, marker: str) -> list[HostComment]`
  - [ ] Docstring states the three contract points: every match regardless of author, ordered oldest-first by `created_at`, and `author_login` populated from the payload rather than assumed
  - [ ] Docstring notes that partitioning by author is the caller's job, because the caller is what reports the non-own matches (D1)
  - [ ] Success: `pyright` reports the implementation no longer satisfies the protocol — expected until 1.2
  - [ ] Effort: 1

- [ ] **1.2 Change the `gh` implementation**
  - [ ] In `src/squadron/codehost/github_cli.py`, rename the method and drop the `_nested_login(comment) == operator` clause from the filter, keeping `marker in body`
  - [ ] **Remove the internal `identify_operator` call.** It exists only to serve the author filter. The caller resolves identity itself (Task 5.2), which is also what makes the identity refusal an early exit
  - [ ] Replace the `min(...)` with a sort over all matches, ascending by `created_at`, returning a list
  - [ ] Populate each `HostComment.author_login` from the payload via `_nested_login`, not from the operator — the whole point is that some of these are not ours
  - [ ] A comment missing `created_at` sorts first under an empty-string key, matching how 381's `min()` treated it
  - [ ] Keep `--paginate` and the `issues/{number}/comments` path unchanged
  - [ ] Success: `ruff check` and `pyright` clean; `grep -r find_own_comment src tests` returns nothing
  - [ ] Effort: 2

- [ ] **1.3 Migrate and extend the discovery tests** *(test-with 1.1–1.2)*
  - [ ] In `tests/codehost/test_github_cli.py`, migrate the five existing `find_own_comment` tests to the new signature
  - [ ] **Two of them invert, and that is the point.** `test_find_own_comment_ignores_another_authors_marker` becomes an assertion that the other author's comment **is** returned with its own `author_login`; `test_find_own_comment_takes_the_earliest_by_created_at` becomes an assertion about list order
  - [ ] Supply the comments to the fake in **non-chronological** order, so passing by input order is impossible
  - [ ] Assert a comment missing `created_at` sorts first
  - [ ] Assert `--paginate` is still in the recorded argv
  - [ ] Assert no `user` (identity) call is recorded during discovery — pins that 1.2 removed it
  - [ ] Success: the whole `tests/codehost/` suite passes
  - [ ] Effort: 2

---

## Task 2 — The comment composer (D2, D4)

Pure functions in `src/squadron/review/pr_comment.py`. No host, no filesystem, no `codehost` import beyond the `PullRequestRecord` type — the one-way rule 383 established.

- [ ] **2.1 Define the marker**
  - [ ] `MARKER_PREFIX` constant and `marker_for(record: PullRequestRecord) -> str` producing `<!-- squadron-review: {record.key} -->` (D4)
  - [ ] Use `record.key` (`{host}/{owner}/{repository}#{number}`), **not** `path_key` — there is no filesystem here, and the flattened form is only harder to read in comment source
  - [ ] These are the only two places the marker's shape is written
  - [ ] Success: `pyright` clean
  - [ ] Effort: 1

- [ ] **2.2 Compose the body**
  - [ ] `compose_comment(result: ReviewResult, record: PullRequestRecord, *, live_head_sha: str) -> str`
  - [ ] Marker first line; then `## Squadron review — {verdict}`; then a model line and the reviewed sha; then findings; then the generated-by-squadron line naming the model (D2)
  - [ ] **Findings come from `result.structured_findings`, not `result.findings`** — that projection assigns the same stable ids and lowercased severities the artifact's frontmatter carries, which is what makes the two incapable of disagreeing
  - [ ] Group findings `fail`, `concern`, `note`, `pass`; preserve original order within each group. A PR reader must meet blocking findings first; the artifact keeps parse order and is untouched
  - [ ] No findings renders an explicit `_No findings._` — never an empty section, never an omitted one, so a PASS comment is visibly a review rather than a truncation
  - [ ] Success: `pyright` clean; no import from `squadron.codehost` except the `PullRequestRecord` type
  - [ ] Effort: 3

- [ ] **2.3 Containment and size**
  - [ ] Emit finding summaries inline, not fenced, so a summary containing a triple-backtick run cannot break the body's structure (D2)
  - [ ] **Neutralize any `<!-- squadron-review:` occurring inside a summary** by breaking the comment opener, so composed content can never contain a second marker
  - [ ] Truncate the findings list at a module constant below GitHub's 65536-character body limit
  - [ ] The truncation line names **only the omitted count**: `_N further findings omitted; see the full review._` It must not name the artifact's location — the composer has no path argument, and D6 permits posting when the save failed, so there may be no artifact to point at (D2, F004)
  - [ ] Success: `ruff check` and `pyright` clean
  - [ ] Effort: 2

- [ ] **2.4 Test the composer** *(test-with 2.1–2.3)*
  - [ ] New `tests/review/test_pr_comment.py` — no host, no fake runner needed
  - [ ] Marker shape, and that `marker_for` uses `key` rather than `path_key`
  - [ ] Severity grouping and within-group order preservation
  - [ ] The explicit no-findings line for a `PASS` result with an empty findings list
  - [ ] A summary containing a triple-backtick run and a copy of the marker opener: assert the body contains **exactly one** marker, by count
  - [ ] A result with more findings than the bound: assert the body is under 65536 characters and the omission line names the count
  - [ ] **Assert the truncation line contains no path** — pins F004's fix against regression
  - [ ] Success: all pass
  - [ ] Effort: 3

---

## Task 3 — Import-graph guard

- [ ] **3.1 Extend the existing import-graph test**
  - [ ] Add `pr_comment.py` to the existing test asserting no module under `review/` imports `squadron.codehost` beyond the permitted record type
  - [ ] Extend the existing test rather than adding a parallel one — a second guard that can pass while the first fails is worse than one that covers everything
  - [ ] Success: passes with Task 2's module present
  - [ ] Effort: 1

---

## Task 4 — `--post` and `--dry-run` flags (D3)

- [ ] **4.1 Add the flags**
  - [ ] On `review_pr` in `src/squadron/cli/commands/review_pr.py`: `--post` (default `False`) and `--dry-run` (default `False`)
  - [ ] Help text for `--dry-run` states it requires `--post`
  - [ ] Success: `sq review pr --help` shows both
  - [ ] Effort: 1

- [ ] **4.2 Guard the flag combination**
  - [ ] `--dry-run` without `--post` exits 1 naming the requirement, before any host call (D3, D5 row 2)
  - [ ] Not a silent no-op — "print what would be posted" is meaningless when nothing would be posted
  - [ ] Success: manual `sq review pr 1 --dry-run` exits 1 with the message
  - [ ] Effort: 1

- [ ] **4.3 Test the default and the guard** *(test-with 4.1–4.2)*
  - [ ] New `tests/cli/test_review_pr_post.py`
  - [ ] **The zero-writes assertion:** a full `sq review pr` run with no post flag records `FakeProcessRunner.write_calls() == []` across the **whole invocation**, not only the post step — this is the assertion 381 built that helper for
  - [ ] `--dry-run` without `--post` exits 1 and records zero calls of any kind
  - [ ] Success: both pass
  - [ ] Effort: 2

---

## Task 5 — The post step (D5)

The decision table in D5 is this task's specification. Each row is a test in 5.5.

- [ ] **5.1 Add the post step to the command**
  - [ ] `_post_review(...)` called **after** the save step, only when `--post` is given
  - [ ] Does not gate on the save's outcome — the review exists in memory and the operator asked for it on the PR (D6)
  - [ ] Success: the step runs; the save path is unchanged
  - [ ] Effort: 2

- [ ] **5.2 Resolve identity first, and refuse on failure**
  - [ ] Call `identify_operator(record.host)` before discovery
  - [ ] `OperatorUnidentifiedError` → report the reason and the `gh auth login --hostname <host>` hint, exit 1, **no write and no discovery call** (D5 row 3)
  - [ ] This row exists separately from D8's generic handling because its reason carries a specific remediation worth naming
  - [ ] Success: the refusal is an early exit, not a failure caught partway through
  - [ ] Effort: 2

- [ ] **5.3 Discover and partition**
  - [ ] `find_marked_comments(record, marker=marker_for(record))`
  - [ ] Partition on `author_login == operator.login` into `mine` and `theirs`
  - [ ] Report each of `theirs` — one stderr line naming the author login and the URL, and one INFO log line. Never edited (D5)
  - [ ] Success: partitioning is in the CLI layer, where the reporting is
  - [ ] Effort: 2

- [ ] **5.4 Decide and write**
  - [ ] `mine` empty → `post_comment`; one → `update_comment` on it; several → `update_comment` on the **earliest** and report the rest by URL (D5)
  - [ ] Bind the body once: `body = compose_comment(...)`, then branch on `--dry-run`. **One call site, one variable** — this is what makes dry-run equality structural rather than disciplinary (D3)
  - [ ] `--dry-run` prints the body to **stdout** and the would-be action plus the `theirs` reports to **stderr**, so stdout is the body and nothing else
  - [ ] A real post prints the resulting comment URL
  - [ ] **Never more than one write on any path**
  - [ ] Success: every D5 row reachable; `ruff check` and `pyright` clean
  - [ ] Effort: 3

- [ ] **5.5 Test the decision table row by row** *(test-with 5.1–5.4)*
  - [ ] In `tests/cli/test_review_pr_post.py`, one test per D5 row, each asserting the recorded argv and the write count
  - [ ] Two consecutive posts by the same login: first calls `POST`, second calls `PATCH` with the first comment's id
  - [ ] A marked comment by another login present: the run calls `POST` (not `PATCH`), reports the other by author and URL, and records **no `PATCH` to its id**
  - [ ] Several of the operator's own, supplied **out of chronological order**: updates the earliest, reports the rest
  - [ ] Identity refusal: exit 1, and **zero calls recorded after the identity call** — in particular no comment listing
  - [ ] Save failed but post succeeded: the comment is written and the command exits 1 for the save (D6)
  - [ ] Success: every row covered
  - [ ] Effort: 3

- [ ] **5.6 Test dry-run/real equality** *(test-with 5.4)*
  - [ ] New `tests/cli/test_review_pr_post_equality.py` — kept separate because it is the one test that drives two full invocations and compares their outputs
  - [ ] Capture stdout from a `--post --dry-run` run and the `stdin` of the `POST` from a real run over the same `ReviewResult`; assert the two strings are equal
  - [ ] **A composer test cannot substitute for this.** Two call sites passing different arguments to the same correct function is exactly the drift this exists to catch
  - [ ] Success: passes
  - [ ] Effort: 2

---

## Task 6 — Staleness statement (D7)

- [ ] **6.1 Read the live head at post time**
  - [ ] Call `resolve_pull_request` again on the post path; the live head is `resolved.record.head_sha` from **that** call
  - [ ] **Do not reuse the record captured at resolution.** It is the reviewed sha; comparing it to itself means the line can never fire. This was F001 in the design review — the data flow originally showed exactly that mistake
  - [ ] A `CodeHostError` here refuses the post rather than posting without the statement (D7) — a comment that silently omits a warning it could not compute is worse than one that did not appear
  - [ ] Success: two distinct values reach the comparison
  - [ ] Effort: 2

- [ ] **6.2 Render the statement**
  - [ ] When `live_head_sha != record.head_sha`, emit under the model line: `> **Stale:** reviewed \`{short}\`, the pull request is now at \`{short}\`.` naming both shas
  - [ ] When they match, emit **nothing** — a "current" line on every comment is noise that trains readers to skip the block where the warning will appear
  - [ ] Success: `pyright` clean
  - [ ] Effort: 1

- [ ] **6.3 Test both branches** *(test-with 6.1–6.2)*
  - [ ] Moved head: the line appears and names both shas
  - [ ] Unmoved head: no staleness line anywhere in the body
  - [ ] The head read failing: exit 1, zero writes, and **no comment posted** — this is the site whose failure could plausibly be papered over by omitting the line
  - [ ] Success: all three pass
  - [ ] Effort: 2

---

## Task 7 — Transport failure and timeout across all four host calls (D8)

Last of the code tasks: it asserts a property of the finished path, and three of the four call sites do not exist until Task 6 lands.

- [ ] **7.1 Confirm uniform handling**
  - [ ] Any `CodeHostError` from the post step is rendered by `render_code_host_error` and exits 1 with no write (D8)
  - [ ] This covers `HostUnauthenticatedError`, `GitHubCliMissingError`, `HostUnreachableError`, and `HostCommandTimeoutError` at all four sites
  - [ ] Confirm no new timeout constant is introduced — all four calls go through 381's `_run_gh` and inherit `HOST_COMMAND_TIMEOUT_SECONDS`
  - [ ] Success: no unbounded host call on the post path
  - [ ] Effort: 1

- [ ] **7.2 Test the failure matrix** *(test-with 7.1)*
  - [ ] New `tests/cli/test_review_pr_post_failures.py` — kept separate from the decision table because this is one assertion shape applied across four sites, and mixing them obscures both
  - [ ] Inject a transport failure at **each** of the four sites (identity, discovery, head read, write): each exits 1 and records zero writes
  - [ ] Inject a scripted `ProcessTimedOutError` at each of the four: same outcome
  - [ ] Assert the recorded `timeout` on every post-path call equals `HOST_COMMAND_TIMEOUT_SECONDS`
  - [ ] Assert the saved artifact is left in place after a failed write
  - [ ] Success: all sites covered per-site, not once
  - [ ] Effort: 3

---

## Task 8 — Verification, evidence, and close

- [ ] **8.1 Full gate**
  - [ ] `ruff format`, `ruff check`, `pyright` — zero pyright errors
  - [ ] Full test suite; the three `tests/documents/test_schema_drift.py` failures are the known context-forge #88 symptom and must be **unchanged** by this slice
  - [ ] `grep -r find_own_comment src tests` returns nothing
  - [ ] Success: gates green
  - [ ] Effort: 1

- [ ] **8.2 Live evidence**
  - [ ] Run the LLD's Verification Walkthrough against a real PR: default writes nothing, `--dry-run` prints without posting, `--post` creates, a second `--post` updates rather than duplicates, and `--dry-run` alone refuses
  - [ ] Confirm the rendered comment shows no marker and that "View source" shows it as the first line
  - [ ] Record steps 3, 4, and 6 in the DEVLOG entry
  - [ ] Success: one squadron comment on the PR after two runs, with an edited indicator
  - [ ] Effort: 2

- [ ] **8.3 Close the slice**
  - [ ] CHANGELOG line — short and user-facing
  - [ ] DEVLOG entry per the Session State Summary guidance, carrying the live evidence
  - [ ] Set `status: complete` in the LLD and mark entry 4 `[x]` in `380-slices.pull-request-workflow.md`
  - [ ] Merge `384-slice.post-findings-to-the-pr` into `squadron-pr`. **Never into `main`** — the integration branch is set for this initiative
  - [ ] Success: slice closed, branch merged, gates green
  - [ ] Effort: 1
