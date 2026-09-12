---
docType: review
layer: project
reviewType: arch
slice: pull-request-workflow
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/380-arch.pull-request-workflow.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: 76bd02517e79e52467863985f18166c69f5c5cb9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Save-target contract surface is load-bearing but undefined"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F002
    severity: concern
    category: completeness
    summary: "Base ref for merge-base computation is fetched nowhere"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F003
    severity: concern
    category: completeness
    summary: "Idempotency mechanism for posted comments is unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F004
    severity: concern
    category: completeness
    summary: "Direct GitHub API implementation is deferred without a slice"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#design-goals"
  - id: F005
    severity: concern
    category: completeness
    summary: "Auth source for the direct-API GitHub implementation is hand-waved"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F006
    severity: concern
    category: consistency
    summary: "PR base conflates local integration branch with PR target"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F007
    severity: concern
    category: feasibility
    summary: "Idempotent comment update has a race window"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F008
    severity: concern
    category: completeness
    summary: "Scratch worktree cleanup after abnormal exit is not described"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F009
    severity: concern
    category: abstraction
    summary: "Adapter protocol operation names carry GitHub vocabulary"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F010
    severity: concern
    category: feasibility
    summary: "PR description's fixed-section contract depends on model output"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F011
    severity: note
    category: completeness
    summary: "Rules-source provenance adds an unwritten frontmatter field"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
---

# Review: arch — slice 380

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Findings

### [CONCERN] Save-target contract surface is load-bearing but undefined

The document introduces "a save-target contract on the persistence side that a slice target and a PR target both satisfy," then migrates the arch review onto it "in the same slice." The current `save_review_result` (src/squadron/review/persistence.py:331) takes a concrete `SliceInfo` and constructs the filename as `f"{slice_info['index']}-review.{review_type}.{slice_info['slice_name']}"`. The CLI helper `_resolve_save_outcome` (src/squadron/cli/commands/review.py:280) is generic over `SaveTargetT` but the closure is typed as `Callable[[SaveTargetT], bool]` — meaning the contract's methods (filename, frontmatter extras, location, persistence location) are implicit. Slice 3 ("PR-keyed review persistence") cannot be planned without enumerating that surface, and "migrate arch review onto it" assumes the existing fabricated `SliceInfo` (src/squadron/cli/commands/review.py:556-577) can be replaced cleanly. Decide the contract's required members and where the unplanned-repo persistence location comes from (CLI flag? config key? home-dir default?) before slice 3 is sized.

### [CONCERN] Base ref for merge-base computation is fetched nowhere

The document states the reviewed range is "merge-base to head" and that "the adapter fetches into a namespaced local ref." Computing merge-base between two refs requires *both* to exist locally. The document only describes fetching the head. The base may be the host default branch (`main`), an integration branch, or a feature branch the user picked. If the local repository has never fetched `origin/main` (shallow clone, freshly cloned repo with no fetch, etc.) or the PR targets a base ref that hasn't been fetched, `git merge-base` returns empty and `assert_reviewable_scope` raises `EmptyScopeError(case=UNCOMPUTABLE)` — which the operator will read as "wrong base" rather than "fetch failed." The fix is small (fetch the base under the same namespacing discipline) but the document doesn't list it among the invariants.

### [CONCERN] Idempotency mechanism for posted comments is unspecified

The document says "The comment is marked so squadron can find and update its own prior comment" but does not choose between the two viable mechanisms: (a) a hidden marker in the comment body (HTML comment, magic prefix), discoverable via the host API on every post; or (b) a local index file mapping `(host, owner, repo, PR)` to the comment id. (a) is host-agnostic but the marker format must not leak through the adapter protocol and must survive the operator editing the body. (b) is faster but breaks when the operator moves machines, runs `--post` from CI on a fresh checkout, or runs `sq pr create` on the same PR twice from different working copies. This is a load-bearing decision and its consequences differ — pick one and write it down.

### [CONCERN] Direct GitHub API implementation is deferred without a slice

The document says "The concrete second is GitHub over its API directly, for CI and hosted runs where `gh` is not installed; that is what keeps `gh`-specific shapes out of the protocol." That second implementation is also what justifies the adapter protocol as "host behind a protocol" rather than "gh wrapper." But the Anticipated Slices list does not allocate a slice for it. A direct-API implementation needs auth handling, pagination, rate-limit handling, and error mapping — and without it, the protocol's only real exercise is `gh`, so `gh`-specific shapes will inevitably leak because nothing else pressure-tests the boundary. Either allocate a slice for the second implementation (perhaps in slice 1 alongside the protocol) or drop the claim that it constrains the design.

### [CONCERN] Auth source for the direct-API GitHub implementation is hand-waved

The document says "delegating to `gh` avoids token handling... keeps auth out of squadron entirely." That justification dissolves the moment the second implementation exists: a direct GitHub API call needs *some* token. The document doesn't name where it comes from (`GITHUB_TOKEN` env var? a configured `gh` token via `gh auth token`? an app installation token? a fine-grained PAT?). This is precisely the kind of decision `CLAUDE.md` flags ("Never use silent fallback values. Fail explicitly..."). The auth contract for the second impl is left for slice 1 to discover under pressure rather than designed up front.

### [CONCERN] PR base conflates local integration branch with PR target

"PR base selection: `sq pr create` targets, in order: an explicit `--base`, the configured integration branch when `cf` reports one (never `main` in that case), else the host's default branch as reported by the adapter." The `git.integration_branch` config key (src/squadron/review/git_utils.py:17) is a *local* concept: "the ref that slice branches fork from and merge into." It is not the host-side PR target. In the standard workflow the integration branch is a personal/team scratch ref, and the PR targets `main`. Treating the integration branch as the PR base (a) reverses the integration-branch rule's intent (it becomes "what I PR against" instead of "what I merge into"), and (b) silently changes the meaning of an existing setting for anyone who already configured `git.integration_branch` for slice review. If the intent is "PR against integration branch instead of main," say so explicitly and call out that this is a different use of the same key. If the intent is something else, this paragraph needs rewriting.

### [CONCERN] Idempotent comment update has a race window

"Posting idempotency and attribution: A repeated `--post` on the same PR must not stack comments." Two concurrent invocations (different operators, different worktrees, or two CI runs against the same PR) both list prior comments, both fail to see the other's marker, and both post — yielding two squadron comments on the same PR. The window is small but real, and the contract says "must not." The document doesn't say whether posting is serialized by host (most hosts return the comment URL synchronously; an idempotency key would help), whether the local index is consulted first, or whether concurrent posts are explicitly out of contract (then "best effort" should replace "must not").

### [CONCERN] Scratch worktree cleanup after abnormal exit is not described

The invariants list cleanup on success, failure, and timeout, plus "A review that cannot remove its worktree says so and names the path." But process death (`SIGKILL`, OOM kill, machine reboot) bypasses every cleanup path. After a crash, an orphan worktree sits under squadron's data directory with `git worktree` still tracking it — and a second review of the same PR collides on the "named by the PR record plus a per-run id" rule only if the per-run id is fresh per invocation (it is), so collisions are avoided but orphans accumulate. There is no "on startup, prune orphan worktrees older than N" or "list orphans on `sq doctor`." Without one, a heavy PR-review workload leaks worktrees silently.

### [CONCERN] Adapter protocol operation names carry GitHub vocabulary

The protocol lists "read its open review comments, post a comment, create a PR, identify the operator." "Open review comments" is a GitHub-specific term (GitLab uses "unresolved threads," Gerrit has "open patch sets," etc.). If the protocol is genuinely host-neutral, the operation should be named by the *intent* (e.g., `list_unresolved_review_threads`, `post_review`, `open_pull_request`) rather than the GitHub feature. The document explicitly says "operations are named by what squadron needs, not by any host's feature vocabulary," but the example list does exactly the opposite.

### [CONCERN] PR description's fixed-section contract depends on model output

"The body is written for two readers at once: prose for humans, and a stable section structure that an AI reviewer, including `sq review pr` itself, can parse for intent and claimed verification." The structure is generated by a one-shot model call through `capture_summary_via_profile` (src/squadron/pipeline/summary_oneshot.py). Models do not reliably emit exact markdown headers verbatim — a model may produce `## What changed` instead of `## What Changed`, or drop a section entirely when the input has no content for it. If the section structure is a contract `sq review pr` will parse, the contract needs enforcement (template that fails closed on missing sections, deterministic section emission from a structured intermediate that the model only fills in), not model-emitted headers. The document does not say which.

### [NOTE] Rules-source provenance adds an unwritten frontmatter field

"For a PR review 'explicit degradation' means the resolved rules source (project, user fallback, or template-only) is logged at INFO and recorded in the artifact." `format_review_markdown` (src/squadron/review/persistence.py:153) has no such field; adding one is a schema change to the review frontmatter, which initiative 360 (Document Intelligence) appears to own. The note is to flag that slice 3 ("PR-keyed review persistence") will need an explicit contract change coordinated with 360 rather than a local addition, and that this is not called out in the Anticipated Slices dependencies.
