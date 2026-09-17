---
docType: slice-design
slice: post-findings-to-the-pr
project: squadron
parent: user/architecture/380-slices.pull-request-workflow.md
dependencies: [381, 383]
interfaces: [386]
dateCreated: 20260916
dateUpdated: 20260917
status: complete
---

# Slice Design: Post Findings to the PR

## Overview

383 gave `sq review pr` an artifact. It lands on disk, and the person reading the PR never sees
it. This slice closes that last step: `--post` writes the review back to the pull request as one
comment.

381 already built the transport. `post_comment`, `update_comment`, `find_own_comment`, and
`identify_operator` are implemented over `gh` and covered by the fake runner, with no caller in
the tree — 381's Excluded section says so explicitly, so that "384 and 385 add behavior rather
than transport." This slice is that behavior, and it is genuinely small: render a body, decide
between create and update, write once.

Two things are not small, and they are where the design actually lives.

The first is **idempotency**, which the architecture defines per authenticated login: a repeated
post updates rather than stacks, discovery runs through the host on every post so no local state
is kept, and marked comments from other operators are reported and never edited. 381's
`find_own_comment` cannot express that. Its signature returns `HostComment | None` and its body
filters to `_nested_login(comment) == operator` before choosing, so both of the things the
architecture asks squadron to *report* — another operator's marked comment, and the operator's
own duplicates left by a concurrent double-post — are discarded inside the adapter and
unreachable from above. 381 could not have known; it wrote the operation before the consumer
existed. This slice is that consumer, and the correction belongs here (D1).

The second is **what gets posted**. A review artifact is a document with frontmatter, a run
digest, and at `-vv` a full prompt-and-response appendix. A PR comment is none of those. The body
is composed for the PR from the review's own structured data, not excerpted from the artifact
file (D2), and the same composition serves `--dry-run`, which is what makes the dry run's promise
— that it equals what the next real run posts — a property of construction rather than of
discipline (D3).

## Value

**User value.** The review reaches the people reading the PR, attributed to the operator who
asked for it, without a copy-paste step. A second run corrects the comment in place instead of
burying the thread.

**Developer value.** 381's comment operations acquire their first consumer and, with it, the
signature the consumer actually needs. The marker convention that every later poster must match
is fixed once, here, in one place.

## Technical Scope

### Included

- `src/squadron/codehost/protocol.py`, `github_cli.py`: `find_own_comment` becomes
  `find_marked_comments`, returning every marked comment with its author, so the caller can
  partition them (D1).
- `src/squadron/review/pr_comment.py`: the marker, the body composer, and the staleness statement
  (D2, D4). Imports no `codehost` symbol except `PullRequestRecord` — the same rule 383 followed.
- `src/squadron/cli/commands/review_pr.py`: `--post` and `--dry-run`; the post step after the save
  step; identity refusal; the create-or-update decision (D3, D5).
- `tests/codehost/test_github_cli.py`: the five `find_own_comment` tests migrate to the new
  signature and gain the other-author and duplicate cases.
- `tests/cli/test_review_pr_post.py`: the decision table and every refusal path.
- `tests/review/test_pr_comment.py`: the body composer, the marker, and dry-run/real equality.
- `project-documents/user/architecture/380-arch.pull-request-workflow.md`: the protocol operation
  list and the posting paragraph, brought into agreement with D1 and D2 following 381's precedent
  for recording protocol changes in the parent; 383's Provides entry likewise.
- CHANGELOG line; DEVLOG entry with one recorded live post.

### Excluded

- **Inline, line-anchored comments.** The plan's Future Work item 3. The adapter has no
  review-comment operation and `ReviewFinding.location` is free text that would have to be mapped
  to the host's diff-position model. One summary comment is the whole scope.
- **Resolving or replying to existing discussions.** `list_unresolved_discussions` is read-only
  input to the review prompt and stays that way.
- **Posting anything other than a review.** No status checks, no labels, no PR body edits. The
  initiative's host writes remain exactly two, and this slice owns one of them.
- **Posting a review this run did not produce.** There is no `sq review post <artifact>`. The
  comment comes from the review in hand (D2); posting a stored artifact from an earlier run is
  unbuilt surface and stays that way until something asks for it.
- **Changing what is saved.** 383's artifact is unchanged by this slice — no new frontmatter key,
  no record of the posted comment. See D6.

## Scope corrections against the plan entry

The plan entry says "the saved review rendered as one summary comment." Taken literally that
reads as *rendering the artifact file*, which D2 rejects: the artifact carries frontmatter, a run
digest, and possibly a debug appendix, none of which belong in a PR comment, and reading it back
would make posting depend on a successful save. The comment is composed from the same
`ReviewResult` the artifact was written from. What the plan's wording protects — that the posted
content is the review that was persisted, not a second opinion — is preserved, and D6 records
what happens when the save fails.

The plan entry also lists `--dry-run` as a flag of this slice alongside `--post`. It is, but with
the precedence stated in D3: `--dry-run` without `--post` is an error rather than a silent
no-op, because "print what would be posted" is meaningless when nothing would be posted.

Both corrections — this one and D1's protocol change — are recorded in the parent architecture
document as part of this design, following 381's precedent of noting protocol changes where the
protocol is specified rather than only in the slice that made them. The architecture's operation
list, its posting paragraph, and 383's Provides entry were updated when this design was reviewed;
no document still describes the shape this slice replaces.

## Dependencies

### Prerequisites

- **383**, merged. The `ReviewResult` and `PullRequestRecord` this slice posts from, and the
  `reviewedSha` the staleness statement compares against, are 383's.
- **381**, for the comment operations and `identify_operator`. This slice changes one of those
  signatures (D1); no other consumer exists, so nothing else moves.

### Interfaces Required

- `CodeHost.post_comment`, `update_comment`, `identify_operator` — used as they are.
- `CodeHost.find_own_comment` — replaced by `find_marked_comments` (D1).
- `HostComment` (`id`, `author_login`, `body`, `url`) and `OperatorIdentity` (`host`, `login`).
- `ReviewResult.structured_findings`, `.verdict`, `.model`; `PullRequestRecord.key`, `.head_sha`.
- `FakeProcessRunner.write_calls()`, which 381 built with this slice's zero-writes assertion named
  in its own comment.

## Architecture

### Component Structure

```
cli/commands/review_pr.py
  review_pr(...)              --post / --dry-run, after the save step
    _post_review(...)         identity → discover → decide → write or print

review/pr_comment.py          no codehost import beyond PullRequestRecord
  MARKER_PREFIX               the convention, defined once
  marker_for(record)          the hidden marker carrying the PR key
  compose_comment(...)        ReviewResult + record + live head → body
  PostDecision                CREATE | UPDATE (StrEnum)

codehost/
  protocol.py                 find_marked_comments(record, *, marker)
  github_cli.py               same query, no author filter, ordered
```

The composer lives under `review/` and not `codehost/` for the reason 383 established: the review
package must not learn the host's shapes. It takes a `PullRequestRecord` — a frozen dataclass that
383 already made a review-package-visible type — and returns a string. The adapter never sees a
`ReviewResult`, and the composer never sees a `HostComment`.

### Data Flow: posting a review

```
review completes → ReviewResult
  │
  ├─ save step (383, unchanged) ────────────────→ artifact on disk
  │
  └─ post step (this slice), only when --post
       │
       identify_operator(record.host)
       │   └─ OperatorUnidentifiedError → report, exit 1, no write
       │
       find_marked_comments(record, marker=marker_for(record))
       │      returns every marked comment, any author, oldest first
       │
       partition by author_login == operator.login
       │   ├─ theirs → report each, never touched
       │   └─ mine   → [] → CREATE
       │              → [c] → UPDATE c
       │              → [c, …] → UPDATE c, report the rest
       │
       resolve_pull_request(...) → live_head = resolved.record.head_sha
       │   └─ CodeHostError → report, exit 1, no write (D7)
       │
       compose_comment(result, record, live_head_sha=live_head)
       │      record.head_sha is what was reviewed; live_head is what the PR
       │      has now. Distinct values, or the staleness line could never fire.
       │
       ├─ --dry-run → print body, exit on verdict, no write
       └─ else      → post_comment | update_comment → print comment URL
```

The post step runs **after** the save step and does not gate on it (D6). All three calls before
the write — identity, discovery, and the post-time head read — are reads; the single write is the
last thing that happens.

## Technical Decisions

### D1 — `find_own_comment` becomes `find_marked_comments`, because the caller must see what the adapter was discarding

381 shipped:

```python
def find_own_comment(self, record: PullRequestRecord, *, marker: str) -> HostComment | None: ...
```

whose implementation calls `identify_operator`, filters `_nested_login(comment) == operator and
marker in body`, and returns the earliest by `created_at`. Two of the architecture's four
idempotency requirements cannot be met through it:

- *"marked comments from other operators are reported, never edited"* — the filter drops them
  before the caller sees them. There is no second operation that would return them.
- *"the next post updates the earliest and reports the rest"* — the `min()` discards the rest.

The signature becomes:

```python
def find_marked_comments(self, record: PullRequestRecord, *, marker: str) -> list[HostComment]: ...
```

returning every comment whose body contains the marker, any author, **ordered oldest-first by
`created_at`**, with `author_login` populated from the payload rather than assumed. Partitioning
by author and choosing the earliest move to the caller, where the reporting also happens.

Three properties are worth stating because tests pin them:

- **Ordering is the adapter's, not the caller's.** `created_at` is in the payload and not in
  `HostComment`, so a caller cannot re-sort. The adapter sorts and the type carries the order.
  Comments missing `created_at` sort first under an empty-string key, exactly as 381's `min()`
  treated them.
- **The author filter is gone, so `identify_operator` is no longer called inside the operation.**
  That is a behavior change the caller absorbs: `_post_review` calls `identify_operator` first,
  once, explicitly, which is also what makes the identity refusal a clean early exit rather than
  a failure discovered mid-discovery.
- **`marker in body` stays a substring test.** The marker is an HTML comment and a body may
  legitimately quote one; 381's guard against that was the author check, which is now the
  caller's partition. A quoted marker from another author lands in `theirs` and is reported, not
  edited, which is the correct outcome and a better one than being invisible.

The five existing `find_own_comment` tests migrate. Two of them —
`test_find_own_comment_ignores_another_authors_marker` and
`test_find_own_comment_takes_the_earliest_by_created_at` — invert: the other author's comment is
now *returned* (and the CLI test asserts it is reported and untouched), and earliest-first becomes
an assertion about list order.

This is a breaking change to a published protocol method with no production caller. It is made
here rather than added beside the old one because two operations answering the same question,
one of which cannot express the contract, is the fourth-shape problem 383 spent a slice removing.

### D2 — The comment is composed from the result, not excerpted from the artifact

The artifact is a document: YAML frontmatter, `# Review: code — PR #42`, findings as `###`
sections, a run digest, and at `-vv` a `## Debug: Prompt & Response` appendix containing the full
system prompt, user prompt, and injected rules. Posting that file verbatim would publish the
prompt text to a public PR at `-vv`, and the frontmatter and digest are noise to a human reader.

So `compose_comment` builds the body from `ReviewResult` directly:

```
<!-- squadron-review: github.com/ecorkran/squadron#42 -->
## Squadron review — CONCERNS

**Model:** `z-ai/glm-5.3` · **Reviewed:** `a1b2c3d`

### Findings

- **[concern]** `F001` error-handling — summary text
  `src/squadron/review/persistence.py:657`
- **[note]** `F002` naming — summary text

_Generated by squadron. Not a substitute for human review._
```

Composition rules, each of which a test pins:

- **Findings come from `structured_findings`**, not `findings`. That projection already assigns
  stable ids (`F001…`), lowercases severity, and defaults an absent category to
  `uncategorized` — the same values the artifact's frontmatter carries, so the comment and the
  artifact cannot disagree about what was found.
- **Severity order, not parse order.** Findings are grouped `fail`, `concern`, `note`, `pass`,
  and within a group keep their original order. A reader scanning a PR comment should meet the
  blocking findings first; the artifact keeps parse order and is unchanged.
- **No findings is a stated outcome**, rendered `_No findings._` — never an empty section and
  never an omitted one, so a `PASS` comment is visibly a review and not a truncation.
- **The body is data, and the host renders markdown.** A finding summary containing a
  triple-backtick run or an HTML comment is emitted inside the line, not fenced, and the marker
  is matched as a whole HTML comment (D4) so a summary quoting `<!-- squadron-review:` cannot
  forge one. This is the same containment concern 382 handled for the inbound direction, in the
  outbound one.
- **Size.** GitHub rejects an issue comment body over 65536 characters. The composer truncates the
  findings list at a constant under that bound and appends a line naming **how many findings were
  omitted** — a count it can compute from its own inputs. It does not name the artifact's
  location: `compose_comment(result, record, live_head_sha)` carries no path, 383 resolves the
  location invocation-dependently in the CLI layer, and `pr_comment.py` must not learn
  persistence. D6 makes the omission necessary rather than merely convenient — a post proceeds
  when the save failed, so there may be no artifact to point at, and a comment naming a path that
  does not exist would be a false statement on a public PR. The truncation line therefore reads
  `_N further findings omitted; see the full review._` and nothing more. A review with 400
  findings posts a usable comment rather than a rejected one.

### D3 — `--post` and `--dry-run`, and why the dry run cannot drift

Two flags on `sq review pr` only:

- `--post` — off by default. Without it, no host write occurs. The fake runner's
  `write_calls()` is empty across an entire review, which is the assertion 381 built that helper
  for.
- `--dry-run` — print the exact body to stdout and make no write. **Requires `--post`**: given
  alone it exits 1 naming the requirement, because "show me what would be posted" has no meaning
  when nothing would be posted. A silent no-op there would be the kind of quiet nothing the
  project's rules forbid.

Dry-run equality is structural. Both paths call `compose_comment` with the same arguments at the
same point in the flow, and the value is bound once:

```python
body = compose_comment(result, record, live_head_sha=live_head)
if dry_run:
    print(body)
    return
```

There is no second renderer and no "dry-run formatting." The only divergence permitted is that
the dry run also prints which action *would* have been taken (`would create` / `would update
<url>`) and the reports for other operators' comments — on **stderr**, so stdout is the body and
nothing else, and a test can compare stdout against the body a real run sends over stdin.

One consequence worth naming: the dry run performs the same three reads (identity, discovery, and
the post-time head read of D7) as a real post. It must, or it could not say whether it would
create or update, and the staleness line depends on the live head. `--dry-run` is not an offline
mode, and every one of those reads is bounded by the same timeout as a real post (D8).

### D4 — The marker

```
<!-- squadron-review: {record.key} -->
```

`PullRequestRecord.key` is `{host}/{owner}/{repository}#{number}` — the human-readable form, not
`path_key`. There is no filesystem here, and the flattening that 383 needed for a filename would
only make the marker harder to read when someone views the comment source.

The marker is the first line of the body. Requirements it satisfies:

- **Hidden.** An HTML comment renders as nothing on the host.
- **No local state.** Discovery reads it back from the host on every post, so two machines, a CI
  runner, and a fresh clone all find the same comment.
- **Keyed by PR.** A comment posted to the wrong PR could never match, and a marker carrying the
  PR key makes that a detectable condition rather than a silent cross-post.

`marker_for(record)` is the only place the string is constructed, and `MARKER_PREFIX` the only
place its shape is written. Matching, per D1, is the substring test the adapter performs; the
composer additionally neutralizes any `<!-- squadron-review:` occurring inside a finding summary
(by breaking the comment opener) so composed content can never contain a second marker.

### D5 — The decision table, and every path that refuses to write

`_post_review` resolves to exactly one outcome. The table is the test:

| Condition | Action | Writes | Exit |
|---|---|---|---|
| No `--post` | none | 0 | verdict only |
| `--dry-run` without `--post` | error naming the requirement | 0 | 1 |
| `identify_operator` raises `OperatorUnidentifiedError` | report the reason and the `gh auth login` hint | 0 | 1 |
| No marked comments | `post_comment` | 1 | verdict / save |
| One mine | `update_comment` | 1 | verdict / save |
| Several mine | `update_comment` on the earliest; report the rest by URL | 1 | verdict / save |
| Only theirs | `post_comment`; report each of theirs by author and URL | 1 | verdict / save |
| Mine and theirs | `update_comment` on my earliest; report theirs | 1 | verdict / save |
| `--dry-run` with `--post` | print body and the action that would be taken | 0 | verdict / save |
| Any of the four host calls raises another `CodeHostError` (transport, auth, timeout) | `render_code_host_error`, already logged at WARNING by the adapter (D8) | 0 | 1 |

Notes the table compresses:

- **Identity is refused before discovery.** The architecture's "no login from the adapter, no
  post, with the reason" is an early exit, not a caught failure partway through. It is also the
  reason D1 moved `identify_operator` out of the discovery operation.
- **Never more than one write.** Every row writes zero or one comment. There is no path that
  posts and then updates, or updates twice.
- **Other operators' comments are reported, never counted as mine.** Reporting is one stderr line
  per comment naming the author login and the URL, at INFO in the log — the architecture's
  "reported, never edited," observable per the project's failure-mode rule.
- **A failed post does not unsave the review.** The artifact is already on disk; the command
  exits 1 naming the host error, and the operator can re-run `--post`.

Exit-code composition: `_exit_on(result.verdict, outcome)` already yields 2 on `FAIL` and 1 on
`UNSAVED`. A post failure exits 1 through `typer.Exit` before reaching it, so a failed post on a
`FAIL` verdict exits 1 rather than 2. That is deliberate — the actionable failure is the one the
operator can retry — and it is asserted rather than left to fall out of ordering.

### D6 — Posting does not gate on saving, and the artifact does not record the post

The two steps are independent, and the order is save-then-post. If the save fails (`UNSAVED`), the
post still runs: the review exists in memory, the operator asked for it on the PR, and refusing to
post because a directory was unwritable would withhold the result they can still act on. The
save failure is already reported and already sets exit 1.

The reverse gating — recording the posted comment's URL back into the artifact — is excluded. It
would mean a second write to a file that was already archived and written, it would make the
artifact differ between a posted and an unposted review of the same code, and nothing consumes it.
The comment carries the marker; the host is the record of what was posted. If a later slice wants
a posted-at field, it adds one additively as 383 added `rulesSource`.

### D7 — The staleness statement

The architecture requires that a review posted against a PR whose head has since moved says so.
Both shas are in hand: `record.head_sha` is what was reviewed and what 383 stamped as
`reviewedSha`, and the live head is what the PR has now.

`resolve_and_fetch_pull_request` resolved the record at the start of the review, and a
tool-enabled review of a large diff is not instantaneous, so the head genuinely can move during
the run. The comparison therefore uses a head read **at post time**, not the one captured at
resolution — otherwise the two values are the same variable and the line could never appear.

When they differ, the body carries, under the model line:

```
> **Stale:** reviewed `a1b2c3d`, the pull request is now at `e4f5a6b`.
```

naming both shas, as the plan's success criterion requires. When they match, no line — a
statement that everything is current on every comment is noise that trains readers to skip the
block where the warning will eventually appear.

Where the live head comes from: `resolve_pull_request` re-run at post time returns a
`ResolvedPullRequest` whose `record.head_sha` is current. That is one additional read on the
`--post` path only. If that read fails with a `CodeHostError`, the post is refused rather than
posted without the statement — a comment that silently omits a staleness warning it could not
compute is worse than one that did not appear.

### D8 — Every host call on the post path is bounded, and transport failure refuses the post

D5's table enumerates the *semantic* outcomes — who owns which comment, and what to do about it.
It does not cover the case where a call simply fails, and the post path adds four host call sites
(identity, discovery, the D7 head read, the write) where 382 and 383 added none.

**The bound.** Every one of the four goes through 381's `_run_gh`, so each is bounded by
`HOST_COMMAND_TIMEOUT_SECONDS` (30s) and a wedged host surfaces as `HostCommandTimeoutError`
rather than a hang. This slice adds no new timeout constant and introduces no unbounded call. The
dry run is bounded identically, since it performs three of the four (D3).

**The handling.** All four raise `CodeHostError` subclasses, and 381 established that each is
logged once at WARNING or above by the layer that raises it. The CLI half is uniform: any
`CodeHostError` from the post step is rendered by `render_code_host_error` and exits 1 with no
write. That covers `HostUnauthenticatedError`, `GitHubCliMissingError`, `HostUnreachableError`,
and `HostCommandTimeoutError` at every one of the four sites, and it is why `OperatorUnidentifiedError`
gets its own D5 row: it is the one failure whose *reason* is worth a specific operator-facing
message (`gh auth login --hostname <host>`) rather than the generic render.

Two properties this fixes in place rather than leaving to fall out of the catch:

- **A refusal before the write is a refusal, not a partial post.** Identity, discovery, and the
  head read all precede the single write, so a transport failure at any of them means zero writes.
  The saved artifact is untouched and the operator re-runs `--post`.
- **The D7 head read is not exempt.** Its failure refuses the post (D7's own rule) through this
  same path, rather than posting a comment whose staleness statement could not be computed.

The criteria assert the signal for each site rather than trusting the catch-all to compose: a
transport failure injected at identity, at discovery, at the head read, and at the write each
exit 1 with zero writes recorded.

## Integration Points

### Provides

- `find_marked_comments` — 385 does not use it, but any later poster (a status comment, a
  metrology digest) discovers its own comments the same way and must partition the same way.
- `MARKER_PREFIX` and `marker_for` — the convention every squadron comment on a PR matches.
- `compose_comment` — 386's parity check asserts the slash-command transport produces the same
  body.

### Consumes from Other Slices

- 383's `ReviewResult`-to-artifact path and `PullRequestRecord.head_sha` as `reviewedSha`.
- 381's `post_comment`, `update_comment`, `identify_operator`, `resolve_pull_request`, the error
  taxonomy, `render_code_host_error`, and `FakeProcessRunner.write_calls()`.

## Success Criteria

### Functional

- `--post` is off by default: a full `sq review pr` run without it records **zero** write calls,
  asserted through `FakeProcessRunner.write_calls()` across the whole invocation, not only the
  post step.
- `--dry-run` without `--post` exits 1 naming the requirement and records zero calls of any kind.
- Two consecutive posts by the same login leave one squadron comment: the first run calls
  `post_comment`, the second calls `update_comment` with the first comment's id, asserted on
  recorded argv.
- A post by a second login leaves two comments, one per login: with a marked comment authored by
  another login present, the run calls `post_comment` (not `update_comment`), and reports the
  other comment by author and URL without any `PATCH` to its id.
- With several of the operator's own marked comments present, the run updates the **earliest by
  `created_at`** and reports the rest by URL — asserted with the duplicates supplied to the fake
  in non-chronological order, so passing by input order is impossible.
- With the adapter unable to identify the operator, the command exits 1, names the reason and the
  `gh auth login` hint, and records **zero** calls after the identity call — in particular no
  comment listing.
- Posting against a PR whose live head differs from the artifact's `reviewedSha` includes the
  staleness line naming both shas; posting against an unmoved head includes no such line.
- `--dry-run` output equals the body posted by the next real run, asserted by capturing stdout
  from a dry run and the `stdin` of the `POST` from a real run over the same `ReviewResult` and
  comparing the two strings.
- A finding summary containing a triple-backtick run and a copy of the marker opener posts intact
  and yields exactly one marker in the body, asserted by counting marker occurrences.
- A review with more findings than the size bound posts a body under 65536 characters whose
  truncation line names the omitted count and **no path** — the composer has no artifact location
  to name, and D6 permits posting when the save failed (D2).
- A `PASS` review with no findings posts a body containing the explicit no-findings line.
- A failed save followed by a successful post: the comment is written, and the command exits 1
  for the save.
- A `CodeHostError` from the write exits 1, names the error, and leaves the saved artifact in
  place.
- A transport failure injected at **each** of the four host call sites — identity, discovery, the
  D7 head read, and the write — exits 1 and records zero writes, asserted per site rather than
  once (D8). The head-read row also asserts no comment was posted, since that is the one site
  whose failure could plausibly be papered over by omitting the staleness line.
- Every recorded host call on the post path carries `HOST_COMMAND_TIMEOUT_SECONDS`, asserted from
  `FakeProcessRunner`'s recorded `timeout`, and a scripted `ProcessTimedOutError` at any of them
  exits 1 with zero writes.
- One recorded live post on a real PR, and a second run against it showing the comment updated
  rather than duplicated.

### Technical

- `ruff format`, `ruff check`, and `pyright` clean; zero pyright errors.
- No module under `review/` imports `squadron.codehost` beyond the `PullRequestRecord` type — the
  existing import-graph test passes with `pr_comment.py` added.
- No test requires `gh`, network, or authentication; every host interaction goes through
  `FakeProcessRunner`.
- `find_own_comment` has no remaining references in `src/` or `tests/`.
- The three `test_schema_drift.py` failures present before this slice are unchanged by it
  (context-forge #88).

### Verification Walkthrough

Run in a clone of `ecorkran/squadron` with `gh` authenticated, against an open PR you can comment
on. Run against a **reviewable** diff — a PR whose only changed files match the code template's
`diff_exclude_patterns` (`*.md`, `*.yaml`, `*.json`, `*.txt`, and others) is refused before
resolution reaches the post step at all, with a message naming the exclusion; add at least one
non-excluded file (e.g. `.py`) to the PR before running any step below.

Confirmed live 20260917 against a throwaway PR (`ecorkran/squadron#115`, opened from `main`,
closed — not merged — once evidence was gathered), carrying one `.py` file under a scratch
directory.

1. Confirm the default writes nothing. Review the PR with no post flag:
   ```
   sq review pr 115 --no-tools --no-save
   ```
   Verdict PASS printed; no `--post`, so no host write. Confirmed via
   `gh pr view 115 --repo ecorkran/squadron --json comments --jq '.comments | length'` → `0`.
2. See exactly what would be posted, without posting:
   ```
   sq review pr 115 --no-tools --no-save --post --dry-run
   ```
   The body printed to stdout, marker first line included; stderr printed `would create`. The
   comment count was still `0` afterward — confirmed unchanged.
3. Post it:
   ```
   sq review pr 115 --no-tools --no-save --post
   ```
   Printed `https://github.com/ecorkran/squadron/pull/115#issuecomment-5719292536`. Reading the
   comment body back (`gh pr view 115 --json comments --jq '.comments[0].body'`) showed
   `<!-- squadron-review: github.com/ecorkran/squadron#115 -->` as the literal first line — an
   HTML comment, so it renders as nothing on the PR itself; "View source" on the comment is what
   shows it.
4. Confirm idempotency. Run the same command again:
   ```
   sq review pr 115 --no-tools --no-save --post
   ```
   Printed the **same** URL (`...issuecomment-5719292536`) as step 3. `gh pr view 115 --json
   comments --jq '.comments | length'` still read `1` — one comment, updated in place (GitHub
   shows a PATCH as an "edited" comment), not a second one.
5. Staleness line — not independently exercised live this run (the throwaway PR's head did not
   move between posts). Its rendering is asserted deterministically at both the composer level
   (`tests/review/test_pr_comment.py::TestStaleness`) and the CLI level
   (`tests/cli/test_review_pr_post.py::test_moved_head_includes_the_staleness_line`, which drives
   a real post-time re-resolution over the fake runner with a scripted head that differs from the
   reviewed sha) — matching the caveat this section already carried before the live run.
6. Confirm the refusal path:
   ```
   sq review pr 115 --no-tools --no-save --dry-run
   ```
   Printed `--dry-run requires --post` and exited 1, before any host call.

Steps 3, 4, and 6 for this run are recorded in the DEVLOG entry that closes this slice.

## Risk Assessment

- **The idempotency change touches a shipped protocol method.** `find_own_comment` is public
  surface from 381. Mitigation: it has no production caller — grep confirms the only references
  are the protocol declaration, the implementation, and five tests — so the change is contained
  to this slice, and the criteria require zero remaining references.
- **Lookup and write are not atomic.** Two concurrent posts by one operator can both land; the
  architecture says so and asks for update-the-earliest rather than a pretense that it cannot
  happen. Mitigation: that is the design (D5), tested with duplicates supplied out of
  chronological order. This slice does not attempt locking.
- **A public PR is a public surface.** The comment is posted with the operator's credentials and
  is visible to everyone who can see the PR. Mitigation: `--post` is opt-in, `--dry-run` shows
  the exact body first, and D2 excludes the artifact's debug appendix so `-vv` cannot publish
  prompt text.

## Implementation Notes

### Order

1. `find_marked_comments` replaces `find_own_comment` in the protocol and the implementation;
   the five existing tests migrate and the other-author and duplicate-ordering cases are added
   (D1). Lands alone — nothing else depends on it yet, so a regression here is unambiguous.
2. `review/pr_comment.py`: `MARKER_PREFIX`, `marker_for`, `compose_comment`, with the severity
   ordering, the no-findings line, the marker-neutralization, and the size bound (D2, D4). Pure
   functions, tested without any host.
3. `--post` and `--dry-run` on `sq review pr`, the identity refusal, and the create-or-update
   decision (D3, D5), against the fake runner. The zero-writes assertion lands with the flag.
4. The staleness statement and its post-time head read (D7).
5. The transport-failure and timeout assertions across all four host call sites (D8). Last of the
   code steps because it asserts a property of the finished path — three of the four sites do not
   exist until step 4 lands.
6. Live post, DEVLOG entry, CHANGELOG line.

### Testing

- `tests/codehost/test_github_cli.py` — the migrated discovery tests: both authors returned,
  oldest-first ordering asserted against non-chronological input, a missing `created_at` sorting
  first, and `--paginate` still in the argv.
- `tests/review/test_pr_comment.py` — the composer: severity ordering, the no-findings line,
  marker neutralization inside a summary, the marker-count assertion, the size bound and its
  omission line, and the marker's exact shape.
- `tests/cli/test_review_pr_post.py` — the D5 decision table row by row, each asserting the
  recorded argv and the write count; the identity refusal asserting no listing call follows; the
  save-failed-post-succeeded combination and its exit code; the `--dry-run` requires-`--post`
  error.
- `tests/cli/test_review_pr_post_failures.py` — D8: a transport failure and a
  `ProcessTimedOutError` injected at each of the four host call sites, each asserting exit 1, zero
  writes, and for the head-read site that no comment was posted; plus the recorded `timeout` on
  every post-path call. Kept separate from the decision table because these are one assertion
  shape applied across four sites, and mixing them into the semantic table obscures both.
- `tests/cli/test_review_pr_post_equality.py` — the dry-run/real equality assertion, kept separate
  because it is the one test that must drive two full invocations and compare their outputs. A
  composer test cannot substitute for it: two call sites passing different arguments to the same
  correct function is exactly the drift it exists to catch.
- Live evidence is recorded, not asserted; no test needs `gh`, network, or auth.
