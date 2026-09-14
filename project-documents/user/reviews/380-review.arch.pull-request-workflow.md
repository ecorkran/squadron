---
docType: review
layer: project
reviewType: arch
slice: pull-request-workflow
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/380-arch.pull-request-workflow.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: b49cca4e91ebd0ca5aa3c688720f3e7f4c221ad5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "The cf-owned frontmatter schema and commit gate are never addressed for the new PR frontmatter shape"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F002
    severity: concern
    category: technology
    summary: "`--output-path` does not mean what the document says it means"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F003
    severity: concern
    category: consistency
    summary: "CLAUDE.md injection contradicts the two-root design in both directions"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F004
    severity: concern
    category: feasibility
    summary: "\"Latest saved review\" ancestor-scoping cites unrelated reviews as this PR's provenance"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Comment-update idempotency assumes the poster can edit the prior comment, which gh-as-operator cannot do across identities"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F006
    severity: concern
    category: feasibility
    summary: "PR-keyed filenames collide with existing index-keyed glob consumers"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#envisioned-state"
  - id: F007
    severity: concern
    category: consistency
    summary: "Unconditional multi-remote failure contradicts the explicit-target forms two sentences later"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F008
    severity: concern
    category: consistency
    summary: "The protocol list omits an operation the design itself requires: arbitrary branch-existence-on-host"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#design-goals"
  - id: F009
    severity: concern
    category: completeness
    summary: "`sq pr create` is silent on the pushed-branch precondition, and the failure enumeration omits create/base-fetch failures"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#envisioned-state"
  - id: F010
    severity: concern
    category: technology
    summary: "Composition reuses `pipeline/summary_oneshot` while requiring the flags reviews use — but that module declares itself non-SDK-only, and reviews default to `sdk`"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F011
    severity: concern
    category: feasibility
    summary: "Scratch worktree invariants omit content completeness — submodules are missing from the reviewed tree"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F012
    severity: note
    category: feasibility
    summary: "Orphan sweep's PID-liveness check has no PID-reuse or cross-platform story"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F013
    severity: note
    category: consistency
    summary: "\"One persistence shape\" arithmetic ignores the pipeline's existing step-keyed shape"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F014
    severity: note
    category: dependencies
    summary: "Ownership of the PR-record → save-target conversion is unspecified, and the naive split creates an import cycle"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
---

# Review: arch — slice 380

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] The cf-owned frontmatter schema and commit gate are never addressed for the new PR frontmatter shape

The "Persistence shape and location" bullet specifies `sourceDocument` as the PR URL, a new `pr` field carrying the typed record, and "no slice fields are written." But frontmatter validity is not squadron's to decide: `cf validate frontmatter` runs as a pre-commit gate (`src/squadron/events/builtin/frontmatter_gate.py`), cf owns the schema, and `tests/documents/test_schema_drift.py` exists precisely because squadron-emitted values can drift — it deliberately fails rather than skips when cf is absent. In a planned repository, PR-keyed reviews land in `project-documents/user/reviews/` and will hit that gate on commit; if cf's `review` schema rejects an unknown `pr:` key, requires `slice:`/`project:`, or type-checks `sourceDocument` as a path, every PR review commit is blocked. The 360 architecture called out exactly this constraint ("the frontmatter gate validates docType and status against fixed enums, so a new type could not be committed until the gate was changed first"); this document never mentions the gate, the drift test, or cf schema acceptance. Also note `format_review_markdown` (`src/squadron/review/persistence.py`) writes `slice:` and `project:` unconditionally with `"unknown"` fallbacks — "no slice fields are written" is a rewrite of that function, which the persistence slice must own explicitly.

### [CONCERN] `--output-path` does not mean what the document says it means

The unplanned-repository location is described as "overridden per invocation by the existing `--output-path`." In the current CLI, `--output-path` is consumed only by `display_result` in `--output file` mode, where `_write_file` writes `json.dumps(result.to_dict())` — a JSON dump, not the frontmatter artifact (`src/squadron/cli/commands/review.py`). It never redirects where the review artifact is saved; `save_review_result` always writes to `REVIEWS_DIR`. `_warn_not_persistable` reinforces the JSON-dump semantics ("use --output file with --output-path to choose a destination"). Either the document intends to change an existing flag's semantics (a breaking change to documented behavior that is nowhere flagged as such, contrary to the document's own "Existing flows do not change" constraint) or the claim is wrong. The persistence slice needs a new, separate override for the artifact location.

### [CONCERN] CLAUDE.md injection contradicts the two-root design in both directions

The "Which tree rules load from" bullet carefully splits the jail root (scratch worktree) from the rules root (operator checkout) so "a PR that edits the rules cannot review itself against its own edits." But `_inject_file_contents` (`src/squadron/review/review_client.py`) injects CLAUDE.md from `inputs["cwd"]` — the jail root — **unconditionally**, outside the `include_bodies` gate that controls file bodies and glob files. With the jail root set to the scratch worktree, a PR that edits CLAUDE.md has its own edits injected as the review's conventions — the exact contamination the document excludes for rules, unaddressed for CLAUDE.md. Conversely, on the no-tools path ("A review without tools needs only the fetched ref"), cwd remains the operator's checkout, so CLAUDE.md comes from the operator's tree rather than the PR head. The document never states which tree CLAUDE.md is taken from on either path, and the recorded rules-source provenance ("names the checkout") covers only rules.

### [CONCERN] "Latest saved review" ancestor-scoping cites unrelated reviews as this PR's provenance

"Description composition" defines the input as "the most recent review artifact whose reviewed sha is in the branch's history at or before its head, else none." Every merged slice's review has a reviewedSha that is an ancestor of every later branch forked from the same base. So for any new branch that has not itself been reviewed — the common first-run case for `sq pr create` — the most recent qualifying artifact is the *previous, already-merged slice's* review, and "review provenance" is then written from it instead of carrying the explicit no-input line. That violates the same bullet's own rule ("never a guess and never a silent omission") and the Design Goal that deterministic parts are "exact by construction": the section would assert a review relationship that does not exist. The scope must be the branch's own commits (fork-point..head), not mere ancestry.

### [CONCERN] Comment-update idempotency assumes the poster can edit the prior comment, which gh-as-operator cannot do across identities

"Posting idempotency and attribution" combines two facts: discovery of the prior comment is by a hidden marker (author-agnostic), and the comment is posted "under the operator's identity... with their credentials." A post run by operator B will therefore discover operator A's marked comment as "squadron's own prior comment," and "the next post updates the earliest marked comment" will fail — the GitHub API only permits editing comments authored by the authenticated user. The race paragraph covers two concurrent posts, not two different operators, which on enterprise PRs is the normal state (author plus reviewers running squadron). Either the update must be scoped to the authenticated login (accepting stacking across operators as a stated consequence) or the mechanism needs supersede-then-post semantics; as written, the named-error discipline ("post rejected") catches it only accidentally.

### [CONCERN] PR-keyed filenames collide with existing index-keyed glob consumers

The envisioned state asserts "Archiving, digest, and integrity checks from the 900-band review work apply unchanged" for PR-keyed persistence, but does not analyze the consumers that key on the numeric filename prefix: `metrology/capture.py` globs `{index}-review.*` and parses the index and review type out of the filename; `sq review resolve` → `locate_review` globs `{index}-review.*` (`src/squadron/review/resolution.py`); `metrology/discovery.py` globs `*-review.*`. If the "PR key" filename prefix begins with the PR number (any bare-numeric form), a PR review of PR 123 is indistinguishable from a slice-123 review to all of these: `sq review resolve 123` can locate a PR review and attempt findings-resolution against it, and metrology capture will treat PR 123 as slice 123. The PR key's filename grammar must be specified — and constrained to be non-numeric-colliding — before "apply unchanged" is true.

### [CONCERN] Unconditional multi-remote failure contradicts the explicit-target forms two sentences later

"Target grammar" states resolution "must fail loudly when the repository has no host remote, has more than one, or the branch has no open PR." Read as written, a repository with `origin` plus `upstream` — the standard fork-setup configuration, and likely the *dominant* configuration for the enterprise repositories this initiative targets — always fails, including when the operator supplied a full URL or `owner/repo#n`, which names the repository unambiguously. The next sentence ("A target that names a repository other than one of the current repository's remotes is refused with the mismatch named") implies explicit targets are checked against the remote set and otherwise permitted. The failure rule must be scoped to the repo-inference cases (bare number, absent target, branch name); as written the two sentences cannot both hold.

### [CONCERN] The protocol list omits an operation the design itself requires: arbitrary branch-existence-on-host

Design Goals declares the enumerated operation list to be *the* protocol ("That list is the protocol; a slice that needs another operation adds it to the protocol"). But "PR base selection" requires the adapter to "confirm the same branch exists on the host" when qualifying the configured integration branch as a PR base — none of the listed operations does that. "Report its base branch and the host's default branch" is about a resolved PR's base and the default branch, not arbitrary branch existence. The architecture's own rule says additions happen at the protocol level; this one is needed by the architecture itself and is missing from its own enumeration, so the keystone adapter slice would either under-build the protocol or quietly stretch an existing operation's meaning.

### [CONCERN] `sq pr create` is silent on the pushed-branch precondition, and the failure enumeration omits create/base-fetch failures

`gh pr create` requires the head branch to exist on the host. The document never says whether `sq pr create` pushes the branch (a host write of a third kind — a ref push — entirely outside the "reads before writes" framing, which covers PR and comment writes only), requires it to be pushed, or verifies it. "PR base selection" says the chosen base is printed before creation, but nothing covers the branch-not-on-host outcome. Relatedly, the Architectural Principles' enumerated failure modes list "head ref not fetchable" and "post rejected" but omit PR-creation rejection and base-ref-not-fetchable — a PR whose base branch was deleted after opening (routine in stacked-PR workflows; GitHub exposes `refs/pull/N/head` but the base must be fetched as a branch) has no named error. "Base moved since resolution" does not cover deletion.

### [CONCERN] Composition reuses `pipeline/summary_oneshot` while requiring the flags reviews use — but that module declares itself non-SDK-only, and reviews default to `sdk`

"Description composition" pins the one-shot call to "the existing non-review one-shot path (`pipeline/summary_oneshot`...), with the same model and profile flags reviews use." Reviews' default profile is `sdk` (`_resolve_profile` falls back to `"sdk"`), but `src/squadron/pipeline/summary_oneshot.py`'s module docstring scopes it to "non-SDK provider profiles." The implementation looks registry-generic, so this may be a stale docstring — but the document asserts reuse of a path whose own contract excludes the default review profile without noting the discrepancy. Slice design must verify the `sdk` profile works through `capture_summary_via_profile` (its `instructions=""` + message-carries-content shape) or the default `sq pr create` invocation fails.

### [CONCERN] Scratch worktree invariants omit content completeness — submodules are missing from the reviewed tree

"Fetching without checkout" enumerates careful worktree lifecycle invariants (naming, registration, removal, timeouts, orphan sweep) but no content invariant. `git worktree add` checks out the superproject only; submodule working trees are not created. This repository itself carries `.gitmodules`, and the enterprise repositories this initiative targets commonly do too. A tool-enabled PR review in a scratch worktree would see absent submodule paths, producing findings against files that do not exist in the reviewed tree — and the parser's path-existence check (`src/squadron/review/parsers.py`) would emit a WARNING per submodule citation, inverting its purpose. The design needs either a submodule-init step in the worktree lifecycle or a stated, tested exclusion.

### [NOTE] Orphan sweep's PID-liveness check has no PID-reuse or cross-platform story

"a run is alive while that process exists" — PID liveness is platform-specific and subject to PID reuse: a recycled PID makes a dead owner's worktree look alive indefinitely. The per-run-id naming keeps orphans non-blocking (as stated), so the failure mode is unbounded accumulation rather than a hang, but the sweep's correctness claim ("worktrees whose owner is gone are pruned") does not hold under PID reuse. Minor, but the invariant is stated as absolute.

### [NOTE] "One persistence shape" arithmetic ignores the pipeline's existing step-keyed shape

Current State says "There is no target type for 'this review is about something that is not a slice,'" and the principles promise "one persistence shape for 'this review is not about a slice' rather than two." But a third shape already exists: the pipeline review action persists slice-less reviews as `{step_index}-review.{template}.{step_name}.md` via `save_review_file` (`src/squadron/pipeline/actions/review.py`), keyed by step index. Unless the save-target contract also migrates that path, the end state is three shapes, not one — and the Current State claim is inaccurate as written.

### [NOTE] Ownership of the PR-record → save-target conversion is unspecified, and the naive split creates an import cycle

"PR identity is a value" places the record type in the adapter package with the review package importing it; "Persistence takes a target" places the save-target contract "on the persistence side." Something must convert the adapter's PR record into a save target. If that conversion lives in the adapter package and references the persistence contract by inheritance, adapter→review plus review→adapter (record type) is a package cycle. Structural `Protocol` typing (the pattern `persistence.py` already uses for `CfClientProtocol`) avoids it with no adapter-side import, but the document does not say who owns the conversion or that the contract must be structural. Worth one sentence in slice design.
