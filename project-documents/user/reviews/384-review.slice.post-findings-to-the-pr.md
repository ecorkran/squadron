---
docType: review
layer: project
reviewType: slice
slice: post-findings-to-the-pr
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/384-slice.post-findings-to-the-pr.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260916
dateUpdated: 20260916
responseStatus: addressed
reviewedSha: 0a8d1576271df1c219e9555ac1f4e424ad151037
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
findings:
  - id: F001
    severity: concern
    category: design-consistency
    summary: "Data Flow diagram contradicts D7's post-time head read"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:145-171"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure modes for the new read call sites are implicit, not enumerated"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:327-360"
  - id: F003
    severity: concern
    category: nfr
    summary: "Timeout NFR for the post path is not restated"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md"
  - id: F004
    severity: concern
    category: under-specification
    summary: "The truncation line promises an artifact location the composer cannot know"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:268-270"
  - id: F005
    severity: note
    category: protocol-change
    summary: "D1 replaces a protocol method the parent's fixed operation list names; record it in the parent"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:177-226"
  - id: F006
    severity: note
    category: scope-deviation
    summary: "Posting source deviates from \"the saved review is rendered\"; refresh the parent and 383's Provides"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:88-100"
  - id: F007
    severity: pass
    category: idempotency
    summary: "Idempotency and attribution match the architecture clause for clause"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:327-360"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Writes are explicit, read-ordered, and refused without identity"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:420-453"
  - id: F009
    severity: pass
    category: dependency-direction
    summary: "Composer placement preserves the one-way review-to-codehost rule"
    location: "project-documents/user/slices/384-slice.post-findings-to-the-pr.md:122-143"
---

# Review: slice — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Data Flow diagram contradicts D7's post-time head read

The Data Flow section passes `live_head_sha=record.head_sha` into `compose_comment` (line 166) and describes the post step as identity → discovery → partition → compose → write, with no head-read step; the closing note names only two reads ("Both the identity call and the discovery call are reads"). D7 (lines 375-400) explicitly rejects exactly this: the comparison "uses a head read **at post time**, not the one captured at resolution — otherwise the two values are the same variable and the line could never appear." D3 is internally inconsistent on the same point: line 300 says "the same two reads (identity, discovery)" in the same sentence that observes "the staleness line depends on the live head" — the post path has three reads. D7 and Implementation Notes step 4 are the correct design, but an implementer working from the flow diagram would build a staleness line that can never fire, silently defeating the architecture's requirement that "a review posted against a PR whose head has since moved must say so." The diagram and the read-count statements should be corrected to match D7 before implementation.

### [CONCERN] Failure modes for the new read call sites are implicit, not enumerated

The D5 table enumerates the semantic refusals and the write failure, but the post step adds three new read call sites whose failure modes have no row and no listed test. `identify_operator` can raise `HostUnauthenticatedError`, `GitHubCliMissingError`, `HostUnreachableError`, or `HostCommandTimeoutError` — the table covers only `OperatorUnidentifiedError`. `find_marked_comments` can fail on transport; the criterion "zero calls after the identity call" covers only the refusal case. The D7 post-time re-resolve has an explicit strategy (refuse the post rather than omit the statement) but appears neither in the D5 table nor in the Functional criteria (lines 420-453), so nothing asserts its signal. The architecture requires each failure mode to be "a named error with a WARNING-or-higher log line and a non-zero exit, and each has a test asserting that signal"; 381 established the errors, but these new CLI-level call sites are where the handling must be shown to compose. The inherited CLI catch-all probably yields exit 1, but the slice leaves that implicit — the criteria should assert it.

### [CONCERN] Timeout NFR for the post path is not restated

The parent architecture states the NFR for every host call: bounded by a timeout constant "so a wedged host is the timeout error rather than a hang." This slice adds four new host call sites on the `--post` path (identity, discovery, the D7 post-time re-resolve, the write), plus a dry run that performs the reads and is explicitly "not an offline mode" (line 300), yet the document never restates the bound (381's `HOST_COMMAND_TIMEOUT_SECONDS = 30`) or names `HostCommandTimeoutError` as this path's hang outcome. The 65536-character host limit is restated with its specific target (line 268) — the timeout deserves the same one-sentence treatment.

### [CONCERN] The truncation line promises an artifact location the composer cannot know

D2's size rule has the composer "append a line naming how many findings were omitted and where the full artifact is," but the composer's specified inputs — `(ReviewResult, PullRequestRecord, live_head_sha)` — carry no artifact path. 383 resolves the location invocation-dependently in the CLI layer (`resolve_reviews_dir` precedence, `--reviews-dir`), and `pr_comment.py` is a pure function in `review/` that must not learn persistence; either the path is threaded into the composition call or the line is appended by the CLI, and the design specifies neither. D6 sharpens it: posting proceeds when the save fails (`UNSAVED`), in which case no artifact exists and the line names a path that is not there — a silent false statement on a public PR, precisely the silent fallback the project rules forbid. The interaction needs a defined behavior before implementation.

### [NOTE] D1 replaces a protocol method the parent's fixed operation list names; record it in the parent

The parent fixes the protocol's operation list ("find and update the operator's own prior squadron comment"), and 381's precedent for protocol changes was to record them in the architecture document itself (`serves_host`, "Added at 381 design"). D1 is well-justified — the old `find_own_comment` signature structurally cannot express two of the parent's own idempotency requirements, so the replacement brings the protocol into compliance with the architecture rather than out of it — and it is contained (no production caller, zero-remaining-references criterion, tests migrated). The missing piece is the parent-side record: the architecture document still describes the operation this slice deletes, and the slice's Included list commits to no architecture-document edit.

### [NOTE] Posting source deviates from "the saved review is rendered"; refresh the parent and 383's Provides

The architecture says "the saved review is rendered as one PR comment," the plan says 384 "posts the saved artifact," and 383's Provides says "the persisted PR review artifact, which 384 renders into a PR comment." The slice composes from the in-memory `ReviewResult` instead and documents why: the artifact carries frontmatter, a run digest, and at `-vv` a full prompt appendix that must not be published to a public PR, and reading it back would gate posting on a successful save. Content identity is preserved by construction — the comment and artifact draw from the same `structured_findings` projection — so what the plan's wording protects survives. The deviation is properly recorded in the slice's scope-corrections section (following 383's precedent); the parent architecture and 383's Provides entry should be refreshed so the documents agree.

### [PASS] Idempotency and attribution match the architecture clause for clause

Every requirement in the parent's "Posting idempotency and attribution" paragraph is implemented and tested: a hidden marker carrying the PR key (D4), discovery through the host on every post with no local state, the per-login unit of idempotency with author partitioning moved to the caller (D1), other operators' marked comments reported and never edited, the concurrent-double-post race handled by update-the-earliest-and-report-the-rest (with duplicates supplied to the fake in non-chronological order so input order cannot pass), and the generated-by-squadron statement naming the model. The success criteria mirror each clause one-for-one.

### [PASS] Writes are explicit, read-ordered, and refused without identity

"Never surprise the operator" and "reads before writes" are satisfied structurally: `--post` is off by default with the zero-write assertion spanning the whole invocation through `FakeProcessRunner.write_calls()` (the helper 381 built for exactly this), identity is resolved before discovery so the refusal is an early exit with zero calls after it, every row of the decision table writes zero or one, and the single write is the last thing that happens. The comment carries the verdict, findings, model, and reviewed sha as the architecture requires.

### [PASS] Composer placement preserves the one-way review-to-codehost rule

The composer lives under `review/` and imports nothing from `codehost` beyond the `PullRequestRecord` type — exactly the import the architecture permits ("the review package imports that type and nothing else from it") — the adapter never sees a `ReviewResult`, and the create-or-update decision sits in the CLI layer that already imports both packages. The existing import-graph test is extended to cover `pr_comment.py` rather than weakened.

### Run Digest

- Response length: 9706 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 106803
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Response

All six actionable findings verified against the document and addressed. Four concerns were
accurate as written; the two notes correctly identified parent documents left describing shapes
this slice replaces.

### F001 — Data Flow contradicts D7 (concern) — **fixed**

Confirmed. The diagram passed `live_head_sha=record.head_sha`, which is the self-comparison D7
exists to reject, and the closing note counted two reads. An implementer following the diagram
would have built a staleness line that could never fire. The diagram now shows the
`resolve_pull_request` head read as its own step with its refusal branch, names both values and
why they must differ, and the read count reads three. D3's "same two reads" corrected to three.

### F002 — Read-site failure modes not enumerated (concern) — **fixed**

Confirmed. D5's table covered the semantic outcomes and `OperatorUnidentifiedError`, but not
transport failure at the three new read sites. Added **D8**, which states the uniform handling
(any `CodeHostError` → `render_code_host_error`, exit 1, zero writes), explains why
`OperatorUnidentifiedError` keeps its own row (its reason carries a specific remediation), and
notes the D7 head read is not exempt. The D5 catch-all row now covers all four sites and
references D8. Criteria assert the signal per site rather than once, with the head-read site
additionally asserting no comment was posted.

### F003 — Timeout NFR not restated (concern) — **fixed**

Confirmed exactly: the document contained zero occurrences of "timeout". D8 states the bound —
all four calls go through 381's `_run_gh`, so each is bounded by `HOST_COMMAND_TIMEOUT_SECONDS`
(30s) and a wedged host surfaces as `HostCommandTimeoutError`. The slice adds no new constant and
no unbounded call. D3 notes the dry run is bounded identically. A criterion asserts the recorded
`timeout` on every post-path call and a scripted `ProcessTimedOutError` at each site.

### F004 — Truncation line promises an unknowable path (concern) — **fixed**

Confirmed, and the review's sharpening is the important half: `compose_comment`'s inputs carry no
path, and D6 permits posting when the save failed, so the line could have named a file that does
not exist — a false statement on a public PR. The composer now emits only the omitted **count**,
which it can compute from its own inputs: `_N further findings omitted; see the full review._`
D2 records why the location is absent rather than leaving it to look like an oversight.

### F005 — Protocol change not recorded in the parent (note) — **fixed**

Confirmed, including the precedent: the architecture records `serves_host` as "Added at 381
design (`79986dea`)". The architecture's operation list now reads "find the comments carrying
squadron's marker, update a comment", and a new bullet records why the shape changed — that
`find_own_comment` discarded both the other-operator matches and the operator's own duplicates
before the caller could see them, that 384 was its first consumer, and that it had no production
caller so the change was contained.

### F006 — Posting source deviates from the parent's wording (note) — **fixed**

Confirmed. The architecture's posting paragraph now says the review is *composed into* a comment
from the same `ReviewResult` the artifact is written from, names the reason (frontmatter, run
digest, and `-vv` prompt text must not reach a public PR), and notes that posting therefore does
not gate on a successful save. 383's Provides entry updated to match. 384's scope-corrections
section records that these edits were made as part of this design, and its Included list now
covers them.

### F007, F008, F009 — pass

No action.

### Verification

`cf validate frontmatter` — 530 files checked, zero findings. No code changed; this slice is
unimplemented.
