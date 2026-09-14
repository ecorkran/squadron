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
reviewedSha: 1c176acd8d4c05defa2b854f856b1ece3f3e56a2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
findings:
  - id: F001
    severity: concern
    category: extension-points
    summary: "Adapter protocol operation set cannot implement the posting and base-selection behaviors the document specifies"
    location: "architecture/380-arch.pull-request-workflow.md#design-goals"
  - id: F002
    severity: concern
    category: consistency
    summary: "Current State and Technical Considerations contradict each other on what the rules loader does outside a planned project"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F003
    severity: concern
    category: technology
    summary: "`sq doctor` adapter checks contradict the shipped doctor contract (no network, no subprocess)"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F004
    severity: concern
    category: consistency
    summary: "Reviewed-head-sha provenance source is unspecified, and the slice-review mechanism records the wrong commit in the no-tools path"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F005
    severity: concern
    category: completeness
    summary: "Unplanned-repository persistence location has no named config key, default, or override"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F006
    severity: concern
    category: consistency
    summary: "Tool-enabled PR review leaves the rules-resolution cwd ambiguous; \"project rules\" can silently become the PR head's own rules"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F007
    severity: concern
    category: consistency
    summary: "`sq pr create`'s required-section check makes the document's own supported scenario uncreatable, and the review-provenance input is unscoped"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F008
    severity: concern
    category: feasibility
    summary: "Single-fenced \"treat as data\" block is escapable by the untrusted content it exists to contain"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F009
    severity: concern
    category: consistency
    summary: "Traceability guarantee for model-authored prose has no enforcement mechanism"
    location: "architecture/380-arch.pull-request-workflow.md#design-goals"
  - id: F010
    severity: concern
    category: completeness
    summary: "`gh` process calls have no timeout; hang is missing from the failure-mode enumeration"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F011
    severity: note
    category: dependencies
    summary: "Typed PR record's home module is unspecified, and it sets the reviewâ† adapter dependency direction"
    location: "architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F012
    severity: note
    category: consistency
    summary: "\"The pipeline `review` action... gains the same optional input for free\" overstates the scope"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F013
    severity: note
    category: completeness
    summary: "Target grammar admits cross-repository targets that every downstream mechanism assumes away"
    location: "architecture/380-arch.pull-request-workflow.md#technical-considerations"
---

# Review: arch — slice 380

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Adapter protocol operation set cannot implement the posting and base-selection behaviors the document specifies

Design Goals enumerates the protocol's operations as exhaustive: "Every hosting interaction (resolve a PR, fetch its base and head, list unresolved review discussions, post a review comment, open a PR, identify the operator) goes through one adapter protocol." Three behaviors specified elsewhere in the document require operations not in that set:

1. Posting idempotency (Technical Considerations, "Posting idempotency and attribution"): "the prior comment is discovered through the host on every post and no local state is kept" and "the next post updates the earliest marked comment" require (a) an operation that lists the PR's comments — the hidden marker lives in squadron's own summary comment, which is not an "unresolved review discussion" (and would not be found by that operation once resolved) — and (b) an update/edit-comment operation. "Post a review comment" only creates.
2. Base selection (Technical Considerations, "PR base selection"): "else the host's default branch as reported by the adapter" requires a default-branch operation.
3. Staleness detection ("a review posted against a PR whose head has since moved must say so") requires re-resolving the PR at post time — arguably covered by "resolve a PR," but the doc never says posting re-resolves.

The keystone slice is explicitly "the protocol, its GitHub implementation over `gh`... the enumerated failure modes." As enumerated, slice 1 builds a protocol that slices 4 and 5 must then extend — or the `gh` implementation grows these as extra methods outside the protocol, which is exactly the leak the "host behind a protocol" goal exists to prevent. Complete the enumeration (list-own-prior-comment, update-comment, default-branch) or state the list is a subset.

### [CONCERN] Current State and Technical Considerations contradict each other on what the rules loader does outside a planned project

Current State states: "Outside such a project the rules and persistence steps have no defined behavior." Technical Considerations ("Rules outside a planned project") states the opposite as established fact: "The rules loader resolves the project's rules directory and, when none exists, silently falls back to a per-user directory under the home config path."

One of these is wrong about the codebase, and which one changes the persistence slice's scope: if the fallback exists, the slice only adds the INFO log and the provenance frontmatter field; if it does not, the slice must build the fallback (and decide its content — an empty per-user directory behaves identically to template-only, which the provenance field's three-way "project, user fallback, or template-only" classification assumes is already distinguishable). The design goal "degrade explicitly, not silently" is premised on the silent fallback being real. Reconcile the two sections before slice 3 is planned.

### [CONCERN] `sq doctor` adapter checks contradict the shipped doctor contract (no network, no subprocess)

"Doctor and setup" says: "`sq doctor` gains checks for the host adapter (`gh` present, authenticated, host reachable)." Slice 905 — complete and shipped — defines the opposite contract: "No network calls to provider endpoints — auth file presence and env-var presence are sufficient"; check functions are "synchronous and pure (no I/O beyond `Path.exists()`, `os.environ.get`, `shutil.which`, and `tomllib.load`)," no subprocesses, with an explicit design rationale of keeping doctor fast and never promising "will work" ("authenticated locally," not "will work").

Only "gh present" (`shutil.which`) survives that contract. "Authenticated" requires either a subprocess (`gh auth status`) or parsing `~/.config/gh/hosts.yml`, which is fragile across enterprise host configurations; "host reachable" is a network probe, squarely outside it. The document neither amends 905's contract nor acknowledges the conflict. Either the checks degrade to presence-only (`gh` on PATH, hosts.yml readable — with 905's contract explicitly extended in this document), or the doctor contract change must be scoped as its own deliverable. Note the prior arch review raised this and the current text is unchanged.

### [CONCERN] Reviewed-head-sha provenance source is unspecified, and the slice-review mechanism records the wrong commit in the no-tools path

"Persistence shape and location" says "the reviewed head sha is recorded as it is for slice reviews." But the reviewed tree for a PR review is a fetched namespaced ref (no-tools) or a scratch worktree (tools); in the no-tools case there is no checkout at the PR head at all, so any cwd/HEAD-derived resolution — which is what the slice-review mechanism is, per the prior arch review's reading of `resolve_reviewed_sha` in `src/squadron/review/persistence.py` (source not present in this working tree; unverified directly) — would record the operator's current branch, not the PR head.

The document already resolved the correct value at the boundary: the typed PR record carries "head sha" ("PR identity is a value"). It never says persistence takes the sha from that record rather than re-deriving it. This field is load-bearing three ways: "The head sha recorded in the artifact is what was reviewed"; "a review posted against a PR whose head has since moved must say so" compares against it; and the posted comment "carries the verdict, findings, model, and the reviewed head sha, so a reader can tell what was reviewed." A silently wrong sha defeats all three. State that the artifact sha is sourced from the PR record, not from HEAD resolution.

### [CONCERN] Unplanned-repository persistence location has no named config key, default, or override

"When the repository has no `project-documents/`, the location is a configured squadron data directory keyed by host, owner, and repository... and the chosen location is printed with the result." The prior review flagged the unspecified location; this revision added the printing but not the decision: no config key, no default path, no CLI override, no precedence rule against `--output-path`. The project's standing rules are "Never use silent fallback values. Fail explicitly" and "Do not hard-code magic defaults... they should be centralized at the config level."

This is not an edge case — the Motivation section makes the unplanned repository the primary scenario ("the repository was often never planned in squadron at all"), which makes the unplanned persistence path the main path for slice 3, and it is the one part of persistence with no specified surface. Printing the chosen location addresses discoverability after the fact, not the unspecified decision. Name the config key, the default, and the override in this document.

### [CONCERN] Tool-enabled PR review leaves the rules-resolution cwd ambiguous; "project rules" can silently become the PR head's own rules

Slice 916 (complete) just unified the reviewer's jail root and the rules directory under one `review_cwd = find_git_root(resolved_cwd)`, passing that root to `resolve_rules_dir`. This document introduces a second tree: the PR head "materialized in a scratch worktree owned by squadron," with "range, working directory, and PR metadata" handed to the existing code review. It never says which tree rules resolve from:

- If rules resolve from the operator's checkout while the reviewer reads the worktree, one review now has two roots — the exact inconsistency 916 Part D was written to eliminate, reintroduced on the new path.
- If rules resolve from the worktree (the natural reading of "working directory" being handed to the existing review), then in a planned repository the "project" rules are the PR head's own `.claude/rules` — a PR that edits the rules reviews itself against its own edits — and the new rules-source provenance field records "project" for content that came from the PR's tree, misreporting exactly what the field exists to disclose.

The "Rules outside a planned project" bullet frames the rules question entirely as planned-vs-unplanned and does not consider the worktree wrinkle its own "Fetching without checkout" bullet creates. State which tree rules load from and what the provenance field records in the tool-enabled case.

### [CONCERN] `sq pr create`'s required-section check makes the document's own supported scenario uncreatable, and the review-provenance input is unscoped

"Description composition" fixes five sections — "(what changed, why, how it was verified, known gaps, review provenance)" — and enforces: "checks that every required section is present and non-empty before creating the PR. A body that fails that check is an error, not a degraded PR." It also states the degradation path: "a branch that does not match gets a commits-only description, not a guessed slice," and "Tasks feed two sections: checked items inform 'how it was verified' and unchecked items populate 'known gaps'."

On a non-slice branch — and a fortiori in an unplanned repository, this initiative's stated motivation — there are no tasks, no slice design, and (before the first PR-keyed review exists) no review artifact. Four of the five sections then have no named input. Either the check fails and PR creation is impossible in exactly the scenario the "commits-only description" sentence says is supported, or sections are conditional on input availability — which the document never says. Which sections are conditional on which inputs must be stated; the current text makes the two rules collide.

Separately, the input is never scoped: "the latest saved review" (Envisioned State, and Overview capability 3) — latest review of the slice? of the branch? of the repository? In a planned repo with arch, tasks, and code reviews of several slices on disk, an unscoped "latest" can attach an unrelated review's verdict and findings to this PR's provenance section — precisely the misassertion the traceability goal ("Nothing is asserted that no input supports") forbids, and exactly the artifact-identity confusion initiative 320's reference document warns about (grouping on the wrong key).

### [CONCERN] Single-fenced "treat as data" block is escapable by the untrusted content it exists to contain

"Prompt inputs from the PR" correctly identifies the hazard — "untrusted text written by third parties" — and then specifies a containment mechanism: "the builder emits a single fenced block labeled as PR-proveded text that the reviewer must treat as data, with the label and fence defined in one constant."

PR bodies and review comments routinely contain triple-backtick fences. The first inner ``` closes the outer block, and everything after it exits the "PR-provided text" region and re-enters the trusted-instruction region — the exact prompt-injection path the block exists to close. A third-party author can also reproduce the label constant inside the body to forge a second "PR-provided text" region or a fake terminator. Having specified the mechanism at fence level, the document owns the escape case: state the mitigation (four-backtick or `~~~` outer fence, stripping/escaping inner fences, or a content-defined sentinel) rather than leaving "single fenced block" as the whole design. The truncation discipline is imported but containment is not.

### [CONCERN] Traceability guarantee for model-authored prose has no enforcement mechanism

The design goal states: "Everything `sq pr create` writes is derived from a named input... Nothing is asserted that no input supports," and Related Work says initiative 360's "traceability rule for generated documents (assert nothing not supported by an input) is adopted for PR descriptions." The specified enforcement is only "every required section is present and non-empty."

Presence and non-emptiness cannot detect an unsupported assertion in model-written prose — "reduces latency by 40%," "fixes CVE-2026-1234," "verified against the staging cluster" are all non-empty and all unsupported by a commit message, a slice document, or a review artifact. Initiative 360 enforces its traceability rule mechanically (translation rules over input artifacts); nothing analogous is specified here. Either scope the guarantee to the deterministic parts — which the document already isolates ("commit list, linked slice, review provenance, reviewed sha) are assembled without a model so they are exact") — and state that prose is prompt-constrained only, or specify a check. As written, a design goal asserts a property the specified mechanism cannot deliver.

### [CONCERN] `gh` process calls have no timeout; hang is missing from the failure-mode enumeration

The failure-mode principle enumerates: "Host unreachable, `gh` missing or unauthenticated, PR not found, head ref not fetchable, base moved since resolution, post rejected" — every mode is an error return. None is a hang, and "host unreachable" as a named error presumes the call returns. A slow or wedged enterprise host makes `gh` block indefinitely, and the document says nothing about bounding it: the worktree lifecycle gets "every git call in its lifecycle bounded by the existing git timeout," but the `gh` calls — the network-facing ones — get no bound, and the "one injected process-runner seam" is named without a timeout contract.

This project already treats unbounded subprocess as a defect class: 916's slice review forced a timeout into `run_git` precisely because "a `git rev-parse` or merge-base against an unreachable remote-tracking ref currently hangs the CLI before any review begins." The same failure, one layer out, is unenumerated here. Specify the timeout on the injected process-runner seam and add the hang/timeout mode to the enumerated set.

### [NOTE] Typed PR record's home module is unspecified, and it sets the reviewâ† adapter dependency direction

"PR identity is a value, not a string" makes the typed record the shared currency of the adapter, the CLI, persistence, and posting. Persistence is in the review package; if the record type lives in the host-adapter package, `review/persistence.py` imports from it — a reviewâ†adapter dependency the "no hosting call lives in the review package" principle does not address for types. Not a cycle (the adapter needs nothing from review), but the boundary the document calls "one new boundary" should name where its shared type lives.

### [NOTE] "The pipeline `review` action... gains the same optional input for free" overstates the scope

Scope states "No pipeline actions, no new agent providers, no executor changes," and Interface parity defers pipeline PR input to "a later decision." Under that scope the pipeline action can only *tolerate* the new optional key (absent â†’ ignored); nothing can supply it until the later decision adds wiring. "Gains... for free" reads as capability; slice 6 should not discover mid-task whether pipeline supply is in or out.

### [NOTE] Target grammar admits cross-repository targets that every downstream mechanism assumes away

"A target may be a number, a full URL, `owner/repo#n`, a branch name, or absent." Full URLs and `owner/repo#n` invite resolving a PR for a repository that is not the current one, while every downstream mechanism — "fetches both... into namespaced local refs" (into the local repository), the scratch worktree of that repository, "fails loudly when the repository has no host remote" — assumes the current repository. Whether a target naming a repository other than the current one's remotes is refused loudly, resolved cross-repo, or unspecified should be stated in the grammar paragraph, since it determines whether the adapter needs a clone/fetch strategy for foreign repositories at all.
