---
docType: architecture
project: squadron
initiative: 380
dateCreated: 20260912
dateUpdated: 20260912
status: not_started
archIndex: 380
component: pull-request-workflow
---

# Architecture: Pull Request Workflow

## Overview

Squadron reviews code well and knows nothing about pull requests. `sq review code` takes a slice
number or a `--diff` ref; persistence is keyed by slice index; nothing under `src/squadron` calls
`gh` or a hosting API. This initiative makes squadron a first-class participant in PR-based
development, in three capabilities that share one new boundary and nothing else:

1. **Review a PR.** `sq review pr <target>` resolves a PR to a diff range plus PR metadata and runs
   the existing code review over it, with every existing review flag behaving as it does today.
2. **Post findings back.** An opt-in flag writes the finished review to the PR as one summary
   comment under the operator's own identity.
3. **Create a PR with a good message.** `sq pr create` composes a title and body from the branch's
   commits, the slice artifacts when a slice branch is detected, and the latest saved review,
   structured for both human readers and AI reviewers.

**Scope:** A code-host adapter boundary, a PR review target on the existing review engine, a
persistence target that does not require a slice index, and one new top-level CLI group. No
pipeline actions, no new agent providers, no executor changes.

**Motivation:** Slice 916 recorded the driver: squadron reviews are moving toward PR-centric use
against enterprise repositories, where the artifact under review is a PR, not a slice, and the
repository was often never planned in squadron at all. Today an operator does that by hand:
checkout, work out the base, run `sq review code --diff`, copy the result into the PR. Each
step is a place to review the wrong thing. On the authoring side, PR descriptions are the one
document every human and every AI reviewer of a change reads first, and squadron already holds
the inputs that make a good one (commits, slice design, tasks, review artifacts) without using
them.

**Constraint:** Existing flows do not change. No PR is ever required. `sq review code`, slice
branches, review persistence for slices, and the merge-to-target rule behave exactly as they do
now.

## Design Goals

- **One review engine.** A PR review is the code review with a different way of resolving its
  inputs. It produces the same `ReviewResult`, passes through the same parser, rules loading,
  scope assertion, and tool wiring, and inherits every fix that lands on the code path. There is
  no second reviewer.
- **Host behind a protocol.** Every hosting interaction (resolve a PR, fetch its head, read its
  threads, post a comment, create a PR, identify the operator) goes through one adapter protocol.
  GitHub via the operator's authenticated `gh` is the first implementation. A second host is a
  new implementation, not an edit.
- **Never surprise the operator.** Squadron never writes to a PR unless asked on that invocation,
  never checks out or mutates the operator's working tree to review something, and never holds a
  token of its own. What it posts is attributed to the operator, who asked for it.
- **Work in repositories squadron did not plan.** A PR review runs in a repository with no
  `project-documents/`, no `cf` project, and no slice indices. Persistence, rules loading, and
  scope resolution all degrade explicitly, not silently, when those are absent.
- **PR descriptions traceable to inputs.** Everything `sq pr create` writes is derived from a
  named input (a commit, a slice document, a review artifact). Nothing is asserted that no input
  supports, and the body says which inputs it was built from.

## Architectural Principles

- **The adapter resolves, the review engine reviews.** The adapter's job ends when it has produced
  a local diff range, a head ref present in the local repository, and a metadata record. From
  that point the review path is the existing one. No review logic lives in the adapter; no
  hosting call lives in the review package.
- **PR identity is a value, not a string.** A resolved target is a typed record (host, owner,
  repository, number, base ref, head ref, head sha, URL) produced once at the boundary. Every
  downstream consumer, including persistence and posting, keys on that record. No component
  re-parses a URL or a `#123` fragment.
- **Persistence takes a target, not a slice.** The save path already accepts a generic save
  target in the CLI; the PR review makes that generic on the persistence side too. A slice-keyed
  target and a PR-keyed target satisfy the same contract. The existing pattern of fabricating a
  minimal slice record so a non-slice review can be saved is not extended to PRs.
- **Reads before writes, and writes are explicit.** Resolution and review are read-only against
  the host. Posting and creating are separate operations behind separate flags or commands, each
  with a dry-run form that prints what would be sent. A write operation that cannot confirm the
  operator's identity refuses rather than posting anonymously.
- **Isolated checkout for tool-enabled reviews.** A tool-enabled review reads files from a
  working tree. The PR's head is materialized in a scratch worktree owned by squadron, so the
  reviewer reads the PR's files and the operator's checkout is untouched. A review without tools
  needs only the fetched ref.
- **Interface parity.** Whatever `sq review pr` accepts, the `/sq:review` slash command and any
  later pipeline input accept identically, producing the same artifact. The CLI is the contract;
  the others are transports.
- **Failure modes are enumerated and observable.** Host unreachable, `gh` missing or
  unauthenticated, PR not found, head ref not fetchable, base moved since resolution, post
  rejected: each is a named error with a WARNING-or-higher log line and a non-zero exit, and each
  has a test asserting that signal.

## Current State

- `sq review code` resolves its diff from a slice branch (fork point or merge commit, via
  `review/git_utils.py`) or from a user `--diff` ref normalized to merge-base semantics (slice
  916). It asserts a non-empty reviewable scope before calling the model, loads rules with
  language auto-detection from the changed paths, injects the diff, and saves under
  `{index}-review.code.{slice-name}.md`.
- Persistence is `SliceInfo`-keyed. Reviews with no slice either warn that they are not
  persistable or, for arch reviews, build a minimal `SliceInfo` from the initiative index. There is
  no target type for "this review is about something that is not a slice."
- The review path assumes it runs inside a squadron-planned project: rules directories, the
  reviews directory, and `cf` slice lookups are resolved relative to the project. Outside such a
  project the rules and persistence steps have no defined behavior.
- Tool-enabled reviews read the current working tree. Reviewing a ref that is not checked out
  means the diff and the files a reviewer opens can disagree.
- No hosting integration exists. `gh` is installed and authenticated on the operator machine but
  squadron neither preflights it (`sq doctor` does not check it) nor calls it.
- PR creation is manual. The inputs a good description needs already exist as squadron artifacts:
  semantic commit history, slice design and tasks under a `{index}-slice.{name}` branch, and the
  most recent saved review with its verdict and findings.

## Envisioned State

A **code-host adapter** package sits beside the review package. It exposes one protocol with the
operations the three capabilities need, and one GitHub implementation that delegates
authentication and transport to the operator's `gh`. Squadron's doctor reports whether that
implementation is usable.

The **review path gains a PR target.** `sq review pr <target>` asks the adapter to resolve the
target into a PR record, fetches the head ref into the local repository, materializes it in a
scratch worktree when tools are enabled, computes the base-to-head range with the same merge-base
semantics `--diff` uses, and hands range, working directory, and PR metadata to the existing code
review. PR metadata (title, body, linked issues, unresolved review threads) is available to the
prompt as additional inputs so the reviewer knows what the PR claims to do and what previous
reviewers already raised. The result is the ordinary `ReviewResult`, displayed and gated exactly as
today.

**Persistence accepts a PR target.** A PR review saves under a PR-keyed name that satisfies the
review frontmatter contract without a slice index, into the project's reviews directory when one
exists or into a configured squadron-owned location when the repository has none. Archiving,
digest, and integrity checks from the 900-band review work apply unchanged.

**Posting is a separate, explicit write.** With the opt-in flag, the saved review is rendered as
one PR comment and posted through the adapter under the operator's identity. The comment carries
the verdict, findings, model, and the reviewed head sha, so a reader can tell what was reviewed
and by what. A later invocation on the same PR updates or supersedes rather than stacking.

**`sq pr create` is a composition step.** It gathers the branch's commits against the target, the
slice design and tasks when the branch name and `cf` identify a slice, and the latest saved
review; produces a title and a body with fixed sections (what changed, why, how it was verified,
known gaps, review provenance); shows it; and creates the PR through the adapter. The body is
written for two readers at once: prose for humans, and a stable section structure that an AI
reviewer, including `sq review pr` itself, can parse for intent and claimed verification.

Nothing else moves. Slice reviews, `sq review code`, the pipeline `review` action, and the
integration-branch rules are unchanged. A pipeline input for PR review is a later decision, taken
only after the CLI has proven the shape.

## Technical Considerations

- **Target grammar.** A target may be a number, a full URL, `owner/repo#n`, a branch name, or
  absent (the PR for the current branch). Resolution must be unambiguous and must fail loudly when
  the repository has no host remote, has more than one, or the branch has no open PR. The grammar is
  fixed at the adapter boundary and nowhere else.
- **Base semantics.** A PR's base branch routinely moves after the PR is opened. The reviewed range
  must be merge-base to head, as 916 established for `--diff`, so the review matches what the host
  displays. The head sha recorded in the artifact is what was reviewed; a review posted against a
  PR whose head has since moved must say so.
- **Fetching without checkout.** Hosts expose PR heads as fetchable refs. The adapter fetches into a
  namespaced local ref so the operator's branches and working tree are untouched. Tool-enabled
  reviews need a real tree; a squadron-owned scratch worktree provides one and is removed
  afterward. Concurrency with the operator's own worktrees, disk use, and cleanup on failure are
  the slice-level questions.
- **Persistence outside a planned project.** The reviews directory, naming convention, and
  frontmatter contract assume `project-documents/user/reviews/` and an index. A PR-keyed name must
  still satisfy the review docType frontmatter. When the repository has no `project-documents/`,
  the location is a configured squadron data directory, not an invented directory in someone
  else's repository, and the choice is reported.
- **Rules outside a planned project.** Rules loading resolves from the project's rules directory.
  In an unplanned repository the review runs with the template's rules and language auto-detection
  only, and says so, rather than silently reviewing with no conventions.
- **Prompt inputs from the PR.** Title, body, linked issues, and unresolved threads are useful
  context and also untrusted text written by third parties. They are injected as clearly delimited
  data, sized with the same truncation discipline as file injection, and never as instructions.
- **Posting idempotency and attribution.** A repeated `--post` on the same PR must not stack
  comments. The comment is marked so squadron can find and update its own prior comment. The
  comment is attributed to the operator's login because it is posted with their credentials; the
  body states it was generated by squadron and names the model.
- **`gh` as the transport.** Delegating to `gh` avoids token handling, honors enterprise hosts the
  operator has already configured, and keeps auth out of squadron entirely. The cost is a process
  boundary and JSON parsing per call, and a hard dependency on `gh` being present for GitHub. The
  protocol must not leak `gh`-specific shapes so a direct-API or other-host implementation stays
  possible.
- **Description composition.** Turning commits, slice documents, and a review into prose is a
  one-shot model call through the existing provider-profile machinery, with the same model and
  profile flags reviews use. Deterministic parts (commit list, linked slice, review provenance,
  reviewed sha) are assembled without a model so they are exact. The body's section structure is
  a contract other tooling can rely on.
- **Squadron's own PR conventions.** `sq pr create` must respect the project's integration-branch
  rule: the PR targets the configured integration branch when one is set, and never `main` in that
  case. The branch-name convention `{index}-slice.{name}` is how a slice is detected; a branch that
  does not match gets a commits-only description, not a guessed slice.
- **Doctor and setup.** `sq doctor` gains checks for the host adapter (`gh` present, authenticated,
  host reachable). Setup does not install `gh`; it reports its absence.

## Anticipated Slices

- **Code-host adapter and PR target resolution.** The protocol, its GitHub implementation over
  `gh`, the typed PR record, target grammar, head fetch into a namespaced ref, doctor checks, and
  the enumerated failure modes with their tests. Read-only. The keystone.
- **`sq review pr`.** The review command on top of the adapter: range resolution with merge-base
  semantics, scratch worktree for tool-enabled reviews, PR metadata as prompt inputs, and full
  parity with the existing review flags.
- **PR-keyed review persistence.** The generic save target on the persistence side, the PR
  naming and frontmatter, the unplanned-repository location, and the explicit rules-degradation
  path. Sequenced after 916 and 917 land on `main`.
- **Post findings to the PR.** The opt-in write, comment rendering with provenance, idempotent
  update of squadron's prior comment, dry-run, and identity refusal.
- **`sq pr create`.** Input gathering (commits, slice artifacts, latest review), deterministic
  assembly plus one-shot composition, the fixed body section contract, integration-branch
  targeting, dry-run, and creation through the adapter.
- **Slash-command and documentation parity.** `/sq:review pr` and `/sq:pr` transports, README and
  quickstart coverage, and a live run against a real PR recorded as evidence.

## Related Work

- Initiative 100 (Orchestration): review engine, `run_review_with_profile`, template registry,
  CLI command registration. All reused; none changed in shape.
- Slice 916 (Review Scope Correctness): merge-base `--diff` semantics, empty-scope refusal,
  tool jail roots. Its motivation names PR-centric enterprise use; this initiative is that use.
- Slice 917 (Review Artifact Integrity): verdict validity, failure artifacts, digest. PR-keyed
  persistence attaches to the seams 917 changes and is sequenced after it.
- Slice 904 (Finding Location Required) and 266/267 (tool-enabled reviews): the parser's
  diff-membership check and the read-only tool set both apply unchanged to a PR review, given a
  correct tree to read.
- Initiative 300 (Judging and Scoring): a PR review carries score and verdict like any review;
  nothing here depends on judging behavior.
- Initiative 360 (Document Intelligence): the traceability rule for generated documents (assert
  nothing not supported by an input) is adopted for PR descriptions.
- `guide.ai-project.process` git rules: branch naming and the integration-branch rule that
  `sq pr create` must honor.
