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
- **Host behind a protocol.** Every hosting interaction (resolve a PR, report its base branch
  and the host's default branch, check that a named branch exists on the host, fetch base and
  head, list unresolved review discussions, find and update the operator's own prior squadron
  comment, post a review comment, open a PR, identify the operator)
  goes through one adapter protocol, plus one local, read-only question added by slice 381:
  whether the implementation serves a given hostname, which bare-form target resolution needs
  to tell a host remote from any other. That list is the protocol; a slice that needs another
  operation adds it to the protocol, never as an extra method on the `gh` implementation. It whose operations are named by intent, not by any host's
  feature vocabulary. GitHub via the operator's authenticated `gh` is the only implementation
  this initiative builds. The protocol is shaped so that GitHub over its API directly (for CI and
  hosted runs without `gh`, authenticated by a token read from the environment and never stored)
  is a second implementation with no protocol change; that implementation is designed for, not
  scheduled, and gets a slice when a CI consumer exists. Other hosts are possible but not
  designed for.
- **Never surprise the operator.** Squadron never writes to a PR unless asked on that invocation,
  never checks out or mutates the operator's working tree to review something, and never holds a
  token of its own. What it posts is attributed to the operator, who asked for it.
- **Work in repositories squadron did not plan.** A PR review runs in a repository with no
  `project-documents/`, no `cf` project, and no slice indices. Persistence, rules loading, and
  scope resolution all degrade explicitly, not silently, when those are absent.
- **PR descriptions traceable to inputs.** The deterministic parts of what `sq pr create` writes
  (commit list, linked slice, review provenance, reviewed sha) are exact by construction. The
  model-written prose is constrained by prompt to those same inputs and is labeled as generated;
  that constraint is not a guarantee, and the body says which inputs it was built from so a
  reader can check the prose against them.

## Architectural Principles

- **The adapter resolves, the review engine reviews.** The adapter's job ends when it has produced
  a local diff range, a head ref present in the local repository, and a metadata record. From
  that point the review path is the existing one. No review logic lives in the adapter; no
  hosting call lives in the review package.
- **PR identity is a value, not a string.** A resolved target is a typed record (host, owner,
  repository, number, base ref, head ref, head sha, URL) produced once at the boundary. Every
  downstream consumer, including persistence and posting, keys on that record. No component
  re-parses a URL or a `#123` fragment. The record type lives in the adapter package; the review
  package imports that type and nothing else from it, so types flow from adapter to review and
  calls never flow from review to host.
- **Persistence takes a target, not a slice.** Today the CLI's save-outcome helper is generic but
  everything beneath it is hardwired to `SliceInfo`, and arch reviews save by fabricating a
  minimal `SliceInfo` from the initiative index. This initiative introduces a save-target contract
  on the persistence side that a slice target and a PR target both satisfy, and migrates the arch
  review and the pipeline action's step-keyed save onto it in the same slice, so there is one
  persistence shape for "this review is not
  about a slice" rather than two. The contract is small: a target yields the filename stem, the
  target-specific frontmatter fields, and the reviews directory. It is structural (a `Protocol`,
  as persistence already does for its `cf` client), so the adapter package never imports the
  review package; the conversion from PR record to save target lives in the CLI layer that
  already imports both. Everything else in formatting, archiving, and digest stays
  target-agnostic.
- **Reads before writes, and writes are explicit.** Resolution and review are read-only against
  the host. Posting and creating are separate operations behind separate flags or commands, each
  with a dry-run form that prints what would be sent. Before any write the adapter's
  identify-operator operation must return a login; if it cannot (no auth, no host), the write is
  refused with that reason rather than attempted.
- **Isolated checkout for tool-enabled reviews.** A tool-enabled review reads files from a
  working tree. The PR's head is materialized in a scratch worktree owned by squadron, so the
  reviewer reads the PR's files and the operator's checkout is untouched. A review without tools
  needs only the fetched ref.
- **Interface parity.** Whatever `sq review pr` accepts, the `/sq:review` slash command and any
  later pipeline input accept identically, producing the same artifact. The CLI is the contract;
  the others are transports.
- **Failure modes are enumerated and observable.** Host unreachable, `gh` missing or
  unauthenticated, PR not found, head or base ref not fetchable, base moved since resolution,
  head branch not on the host, post rejected, creation rejected, host call exceeded its
  timeout: each is a named error with a WARNING-or-higher log
  line and a non-zero exit, and each has a test asserting that signal. The adapter reaches `gh`
  through one injected process-runner seam whose every call is bounded by a timeout constant, as
  git calls already are, so a wedged host is the timeout error rather than a hang. Those tests are unit-level against a fake runner returning each failure shape, plus one
  recorded live run against a real PR as evidence. No live test exercises auth or network state.

## Current State

- `sq review code` resolves its diff from a slice branch (fork point or merge commit, via
  `review/git_utils.py`) or from a user `--diff` ref normalized to merge-base semantics (slice
  916). It asserts a non-empty reviewable scope before calling the model, loads rules with
  language auto-detection from the changed paths, injects the diff, and saves under
  `{index}-review.code.{slice-name}.md`.
- Persistence is `SliceInfo`-keyed. Reviews with no slice either warn that they are not
  persistable or, for arch reviews, build a minimal `SliceInfo` from the initiative index, and the
  pipeline review action saves slice-less reviews under a step index. Three filename shapes, no
  target type for "this review is about something that is not a slice."
- The review path assumes it runs inside a squadron-planned project: rules directories, the
  reviews directory, and `cf` slice lookups are resolved relative to the project. Outside such a
  project, rules loading silently falls back to a per-user directory under the home config path,
  and persistence has no defined location.
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
target into a PR record, fetches the base and head refs into the local repository, materializes
the head in a scratch worktree when tools are enabled, computes the base-to-head range with the
same merge-base semantics `--diff` uses, and hands range, working directory, and PR metadata to the existing code
review. PR metadata (title, body, linked issues, open review comments) is available to the
prompt as one additional input so the reviewer knows what the PR claims to do and what previous
reviewers already raised and not yet resolved. The result is the ordinary `ReviewResult`, displayed and gated exactly as
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
review; produces a title and a body whose fixed sections (what changed, why, how it was
verified, known gaps, review provenance) squadron writes and the model fills; shows it; and
creates the PR through the adapter. The body is
written for two readers at once: prose for humans, and a stable section structure that an AI
reviewer, including `sq review pr` itself, can parse for intent and claimed verification.

Nothing else moves. Slice reviews, `sq review code`, the pipeline `review` action, and the
integration-branch rules are unchanged. A pipeline input for PR review is a later decision, taken
only after the CLI has proven the shape.

## Technical Considerations

- **Target grammar.** A target may be a number, a full URL, `owner/repo#n`, `repo#n`, a branch
  name, or absent (the PR for the current branch). Resolution must be unambiguous. The explicit
  forms (URL, `owner/repo#n`) name their repository and resolve against whichever local remote
  points at it; `repo#n` names only the repository and resolves against the host remotes with
  that repository name, failing when more than one owner has it; the bare forms (number, branch,
  absent) need exactly one host remote and fail loudly when there are none or several, as they
  do when the branch has no open PR. A target that names
  a repository none of the current repository's remotes points at is refused with the mismatch
  named; cross-repository review is not supported. The grammar is fixed at the adapter
  boundary and nowhere else.
- **Base semantics.** A PR's base branch routinely moves after the PR is opened. The reviewed range
  must be merge-base to head, as 916 established for `--diff`, so the review matches what the host
  displays. The head sha recorded in the artifact is what was reviewed; a review posted against a
  PR whose head has since moved must say so.
- **Fetching without checkout.** Hosts expose PR heads as fetchable refs. The adapter fetches both
  the PR's base branch and its head into namespaced local refs, so the merge-base is computed
  between two refs squadron just fetched rather than whatever the operator's clone last saw, and
  the operator's branches and working tree are untouched. Tool-enabled
  reviews need a real tree; a squadron-owned scratch worktree provides one. Invariants: one
  scratch worktree per review invocation, created under squadron's data directory and named by
  the PR record plus a per-run id so two reviews of the same PR never collide; registered with
  `git worktree` so the repository knows about it; removed on success, on failure, and on
  timeout; every git call in its lifecycle bounded by the existing git timeout. Process death
  bypasses all of that, so each invocation also sweeps: every scratch worktree carries a lock
  file naming its owning process and that process's start time (so a reused pid does not look
  alive), a run is alive while that process exists, and worktrees whose owner is gone are pruned
  before the new one is created. The worktree is complete: when the repository has submodules
  they are initialized in it, and a submodule that cannot be fetched fails the review by name
  rather than leaving paths the reviewer will cite as missing. The per-run id means an orphan never
  blocks a new review. A review that cannot remove its worktree says so and names the path. The
  operator's checkout is never touched.
- **Persistence shape and location.** The reviews directory, naming convention, and frontmatter
  contract assume `project-documents/user/reviews/` and a numeric index. A PR review keeps the
  `docType: review` contract (`reviewType`, `aiModel`, dates, status) and replaces the slice
  fields: `sourceDocument` is the PR URL, a `pr` field carries the typed PR record, and the
  reviewed head sha is taken from that record, never resolved from HEAD of the working directory,
  which on this path is the operator's branch and not the reviewed tree; no slice fields are
  written. Frontmatter validity is `cf`'s to decide and its commit gate enforces it, so the
  persistence slice verifies the PR shape against `cf validate frontmatter` and the existing
  schema-drift test; a `cf` schema change, if the `review` schema rejects the shape, is a named
  dependency on context-forge and lands before that slice. The
  filename is prefixed by a non-numeric PR key rather than an index, so every consumer that
  globs `{index}-review.*` (resolution, metrology capture) never matches a PR review, and the
  consumers that glob `*-review.*` are taught to read the target kind from the prefix in the same
  slice; the naming-conventions guide gains the form there too. When the repository has no `project-documents/`, the location is
  the `review.external_reviews_dir` config key, defaulting to a `reviews/<host>/<owner>/<repo>/`
  tree under squadron's per-user data directory, overridden per invocation by a new
  `--reviews-dir` flag (the existing `--output-path` is a JSON dump destination and keeps that
  meaning); never an invented directory in someone else's repository. The chosen location
  and its source are printed with the result.
- **Which tree rules load from.** Slice 916 unified the reviewer's tool jail root and the rules
  directory under one review root. A tool-enabled PR review deliberately splits them: the jail
  root is the scratch worktree, so the reviewer reads the PR's files, while rules resolve from the
  operator's checkout root, so a PR that edits the rules cannot review itself against its own
  edits. The rule is general: every convention input the review injects (rules directory,
  project instructions file, anything else read for "how this project works") comes from the
  checkout, and only the code under review comes from the worktree. The artifact records both
  roots, and the rules-source provenance names the checkout.
- **Rules outside a planned project.** The rules loader resolves the project's rules directory
  and, when none exists, silently falls back to a per-user directory under the home config path.
  For a PR review "explicit degradation" means the resolved rules source (project, user
  fallback, or template-only) is logged at INFO and recorded in the artifact as one additive,
  optional frontmatter field alongside the rules content already persisted, so a reviewer can see
  which conventions were applied. The field is added in the persistence slice; existing artifacts
  are unaffected. The fallback is not suppressed; it is reported.
- **Prompt inputs from the PR.** Title, body, linked issues, and open review comments are useful
  context and also untrusted text written by third parties. They reach the model through the code
  template as one additional optional input rendered by the code prompt builder, not through a
  second template: the builder emits one fenced block labeled as PR-provided text that the
  reviewer must treat as data. Containment is the builder's job, not the label's: the outer fence
  is chosen longer than the longest fence run inside the content, so no inner fence can close it,
  and any occurrence of the label inside the content is neutralized before emission; label and
  fence policy live in one place. The block is truncated by the same size discipline file
  injection uses. The pipeline `review` action, which shares that template, tolerates the new
  optional key and ignores it when absent; nothing supplies it until the later pipeline decision.
- **Posting idempotency and attribution.** A repeated `--post` on the same PR updates rather than
  stacks. The mechanism is a hidden marker in the comment body carrying the PR key, so the prior
  comment is discovered through the host on every post and no local state is kept. A host lets
  a login edit only its own comments, so the unit of idempotency is one squadron comment per
  operator: the update targets the marked comment authored by the authenticated login, and
  marked comments from other operators are reported, never edited. Lookup and post are not
  atomic, so two concurrent posts by one operator can both land; the next post updates the
  earliest and reports the rest rather than pretending the race cannot happen. The
  comment is attributed to the operator's login because it is posted with their credentials; the
  body states it was generated by squadron and names the model.
- **`gh` as the transport.** Delegating to `gh` avoids token handling, honors enterprise hosts the
  operator has already configured, and keeps auth out of squadron entirely. The cost is a process
  boundary and JSON parsing per call, and a hard dependency on `gh` being present for GitHub. The
  protocol must not leak `gh`-specific shapes so a direct-API or other-host implementation stays
  possible.
- **Description composition.** Turning commits, slice documents, and a review into prose is a
  one-shot model call through the existing non-review one-shot path (`pipeline/summary_oneshot`,
  which already runs a prompt through a provider profile with telemetry), with the same model and
  profile flags reviews use. That module's docstring scopes it to non-SDK profiles while the
  review default is `sdk`; the slice verifies the `sdk` profile through it and corrects whichever
  of the docstring or the routing is wrong. Deterministic parts (commit list, linked slice, review provenance,
  reviewed sha) are assembled without a model so they are exact. Tasks feed two sections:
  checked items inform "how it was verified" and unchecked items populate "known gaps"; the
  slice design informs "why". "What changed" and "why" always have an input (commits, with the
  slice design when present); "how it was verified", "known gaps", and "review provenance" are
  written from their inputs when those exist and otherwise carry an explicit no-input line, never
  a guess and never a silent omission. "The latest saved review" is scoped to this branch's own
  commits: the most recent review artifact whose reviewed sha lies in the base-to-head range,
  so a review of an earlier merged branch that is an ancestor of this one never qualifies, else
  none. The section structure is not left to the model: squadron writes the headings
  and asks the model only for the prose under each, then checks that every section is present
  and either filled or explicitly marked before creating the PR. A body that fails that check is
  an error, not a degraded PR.
- **PR base selection.** `sq pr create` targets, in order: an explicit `--base`, the configured
  integration branch when `cf` reports one, else the host's default branch as reported by the
  adapter. The integration branch is a local fork-and-merge target, so it qualifies as a PR base
  only when the adapter confirms the same branch exists on the host; if it does not, creation
  fails and says so rather than falling through to `main`. In an unplanned repository only the
  first and last apply. The chosen base and its source are printed before creation. The head
  branch must already be on the host and match the local branch; `sq pr create` never pushes,
  and when the branch is missing or behind it fails naming the push the operator should run,
  so the initiative's host writes stay exactly two: a comment and a PR. The branch-name convention
  `{index}-slice.{name}` is how a slice is detected; a branch that does not match gets a
  commits-only description, not a guessed slice.
- **Doctor and setup.** Slice 905 fixed doctor's contract as pure checks with no subprocess and no
  network, and this initiative keeps it: `sq doctor` gains presence checks only (`gh` on PATH, its
  hosts file readable). Authentication and reachability are verified by the adapter at
  invocation, where each failure is one of the named errors above. Setup does not install `gh`;
  it reports its absence.

## Anticipated Slices

- **Code-host adapter and PR target resolution.** The protocol, its GitHub implementation over
  `gh`, the typed PR record, target grammar, base and head fetch into namespaced refs, doctor checks, and
  the enumerated failure modes with their tests. Read-only. The keystone.
- **`sq review pr`.** The review command on top of the adapter: range resolution with merge-base
  semantics, scratch worktree with orphan sweep for tool-enabled reviews, PR metadata as one prompt input, and full
  parity with the existing review flags.
- **PR-keyed review persistence.** The save-target contract on the persistence side, migration
  of the arch review off the minimal-`SliceInfo` pattern, the PR naming and frontmatter, the
  unplanned-repository location, and rules-source provenance in the artifact. Sequenced after 916
  and 917 land on `main`.
- **Post findings to the PR.** The opt-in write, comment rendering with provenance and hidden
  marker, update of squadron's prior comment, dry-run, and identity refusal.
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
