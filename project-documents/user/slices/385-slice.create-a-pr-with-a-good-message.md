---
docType: slice-design
slice: create-a-pr-with-a-good-message
project: squadron
parent: user/architecture/380-slices.pull-request-workflow.md
dependencies: [381]
interfaces: [386]
dateCreated: 20260917
dateUpdated: 20260917
status: not_started
---

# Slice Design: Create a PR with a Good Message

## Overview

381 through 384 all point one direction: squadron reads a pull request, reviews it, and writes
findings back. This slice points the other way. `sq pr create` opens the pull request, and writes
a description built from what squadron already knows about the branch.

The inputs exist today and go unused. A slice branch carries a design document and a task file
with checked and unchecked items. The branch's commits are semantic by project convention. A
saved review carries a verdict and a reviewed sha. Every one of those is something a reader of
the PR wants, and today the operator either retypes it or writes "see slice 385" and moves on.

The slice is not, however, "ask a model to write a PR description." The architecture is specific
about the split: the parts that can be exact are assembled without a model, the prose is written
by a model that is given only those inputs, and the section structure is squadron's, not the
model's. What the model contributes is sentences. What squadron contributes is every fact in
them and the shape they arrive in.

Three things carry the design's weight.

The first is **base selection** (D1). The architecture fixes an order — `--base`, then the
configured integration branch, then the host default — and then adds a condition that makes the
middle term interesting: an integration branch is a local fork-and-merge convention, and it
qualifies as a PR base only if the adapter confirms it exists on the host. When it does not, the
command fails. It does not fall through to the next term. This initiative's own branch,
`squadron-pr`, is exactly that case — a configured integration branch that may or may not have
been pushed — so the failure path is not hypothetical here.

The second is **the section contract** (D4, D5). Five headings, written by squadron. Each is
filled from its inputs or carries an explicit no-input line. A model response that omits a
section fails a check and creates nothing, because a PR body missing "how it was verified" is
worse than one that says the information was unavailable — the first reads as an oversight the
reader must chase, the second is a fact.

The third is **the one-shot path** (D3). The plan entry flags it as the slice's live risk: the
composition runs through `pipeline/summary_oneshot`, whose docstring scopes it to non-SDK
profiles while the review default is `sdk`. That is resolved in this design rather than deferred
to implementation, and the answer changes what the slice builds.

## Value

**User value.** A PR description assembled from the branch's own artifacts, written for two
readers at once: a human deciding whether to look, and an AI reviewer — including `sq review pr`
— parsing for claimed intent and claimed verification. The operator stops retyping what squadron
already has on disk.

**Developer value.** The deterministic-assembly-plus-constrained-prose pattern gets its first
implementation here. Initiative 360's traceability rule (assert nothing an input does not
support) becomes code rather than a principle, and the branch-name → slice-index parser the
tree currently lacks is written once, in one place.

## Technical Scope

### Included

- `src/squadron/cli/commands/pr.py`: the `create` subcommand beside `show`, with `--base`,
  `--dry-run`, `--model`, `--profile`, `--cwd`, and `--title`.
- A new `src/squadron/pr/` package (CLI-layer-adjacent, see D6) holding:
  - **base selection** — the three-term chain with host confirmation and printed provenance.
  - **precondition checks** — head branch pushed, present on the host, and matching local.
  - **input gathering** — commits in range, slice artifacts when the branch names a slice, the
    latest in-range review.
  - **deterministic assembly** — the exact parts, built without a model.
  - **body composition** — the section contract, the prompt, and the presence-and-filled check.
- A branch-name parser for the `{index}-slice.{name}` convention.
- A task-file checkbox parser (checked items and unchecked items), which does not exist today.
- A git helper for listing commits in a base-to-head range, and one for the current branch name.
- Verification of the `sdk` profile through the one-shot path, and correction of whichever of
  the docstring or the routing is wrong (D3).
- Unit tests against the fake process runner for every host interaction and every refusal path;
  a fake composer for the model call.
- One recorded live creation.

### Excluded

- **Pushing.** `sq pr create` never pushes a branch. An unpushed head is a refusal that names
  the push command. The initiative's host writes stay exactly two: a comment (384) and a PR.
- **Editing an existing PR.** Creation only. Updating a PR's body when one is already open is
  Future Work, not a silent second behavior of `create`.
- **Draft PRs, reviewers, labels, milestones.** The adapter's `open_pull_request` takes base,
  head, title, and body, and this slice does not widen it.
- **Cross-repository PRs.** Excluded at the architecture level; the locator is the current
  repository's.
- **Posting the review to the created PR.** That is 384's `--post` on a review command, and
  composing the two is the operator's call, not an implicit one.
- **A slash-command transport.** 386 owns `/sq:pr`.

## Scope corrections against the plan entry

The plan entry says composition runs "through `pipeline/summary_oneshot` with the review model
and profile flags, after verifying the `sdk` profile through it and correcting the docstring or
the routing." The verification is done in this design (D3) and the answer is that
`summary_oneshot` is not the right module to call — `review_client.run_review_with_profile` is
the existing CLI-side one-shot, and the correction owed is to `summary_oneshot`'s docstring, not
to its routing. The slice builds a small composer beside those two rather than calling either.
Same inputs, same flags, same provider registry; a different and more honest entry point.

The plan entry also lists "the latest review whose reviewed sha lies in that range" as an input
without noting that no "list reviews and read their frontmatter" surface exists for this purpose
— `locate_review` is index-keyed and raises on ambiguity rather than ordering. D7 specifies the
scan this slice writes.

## Dependencies

### Prerequisites

- **381** — the adapter protocol and its GitHub implementation. This slice consumes
  `open_pull_request`, `default_branch`, `branch_exists`, `identify_operator`, and the remote
  selection helpers. All four host operations exist and are covered by the fake runner; none has
  a production caller before this slice.
- **[100]** — CLI command registration, the provider registry, and the profile system.
- **383** is *not* a prerequisite. Without it the review-provenance section carries its no-input
  line, which the architecture names as a supported degraded path. 383 is merged, so the
  provenance section will have real input in practice; the degraded path is still built and
  tested, because an unplanned repository hits it regardless.

### Interfaces Required

- `CodeHost.open_pull_request(locator, *, base, head, title, body) -> PullRequestRecord` —
  raises `PullRequestCreationRejectedError` on HTTP 422.
- `CodeHost.default_branch(locator) -> str`, `CodeHost.branch_exists(locator, branch) -> bool`,
  `CodeHost.identify_operator(hostname) -> OperatorIdentity`.
- `RepositoryLocator` and the remote-selection path from 381 — but *not*
  `resolve_and_fetch_pull_request`, which resolves an existing PR. See D6.
- `ContextForgeClient.get_config("git.integration_branch")`, `list_slices()`, `list_tasks()`,
  and `resolve_slice_info` for the slice lookup.
- `get_profile` / `ensure_provider_loaded` / `get_provider` from the provider registry.

## Architecture

### Component Structure

```
src/squadron/pr/
  base.py          select_base()         → BaseSelection(base, source)
  preconditions.py check_head_pushed()   → refusal or HeadState
  inputs.py        gather_inputs()       → PrInputs (commits, slice, review)
  assembly.py      assemble_facts()      → PrFacts  (exact parts, no model)
  body.py          compose_body()        → str      (sections + prose)
  branch.py        parse_slice_branch()  → int | None
  tasks.py         parse_task_items()    → TaskItems(checked, unchecked)

src/squadron/cli/commands/pr.py
  create()         orchestration, printing, exit codes
```

`pr/` sits in the CLI layer's dependency tier: it may import `codehost` types and `review`
helpers, which is exactly the combination the import-boundary test forbids inside `review/` and
permits above it (D6).

### Data Flow: creating a pull request

```
  operator: sq pr create [--base B] [--dry-run]
      │
      ├─ resolve repo cwd, build host, select remote        → RepositoryLocator
      ├─ current branch name                                → head
      │
      ├─ PRECONDITIONS ─────────────────────────────────────────────────
      │    identify_operator(host)        no login    → refuse, exit 1
      │    branch_exists(locator, head)   absent      → refuse + push cmd
      │    local head sha == remote sha   mismatch    → refuse + push cmd
      │
      ├─ BASE (D1) ─────────────────────────────────────────────────────
      │    --base given                   → use it, source=flag
      │    else integration_branch set    → branch_exists? use : REFUSE
      │    else default_branch(locator)   → use it, source=host-default
      │    print chosen base and source
      │
      ├─ INPUTS (D7) ───────────────────────────────────────────────────
      │    commits in base..head                       (always present)
      │    branch matches {index}-slice.{name}?
      │        → cf resolve_slice_info → design, tasks → checked/unchecked
      │    latest review whose reviewedSha ∈ range     (else none)
      │
      ├─ ASSEMBLY ──────────────────────────────────────────────────────
      │    PrFacts: commit list, slice ref, review path, reviewed sha,
      │             verdict — every one copied, none inferred
      │
      ├─ COMPOSE (D3, D4) ──────────────────────────────────────────────
      │    one-shot model call, given PrFacts only
      │    squadron writes the five headings; model fills prose
      │    presence-and-filled check (D5)   fails → exit 1, nothing created
      │
      ├─ --dry-run? → print title + body to stdout, exit 0, no host write
      │
      └─ open_pull_request(locator, base, head, title, body)
             → print URL
```

The ordering is deliberate. Every refusal that can be decided without a model call happens before
the model call, so a missing push or an absent integration branch costs no tokens.

## Technical Decisions

### D1 — Base selection refuses rather than falls through

The architecture states the order and the condition: `--base`, then the configured integration
branch *when the adapter confirms it exists on the host*, else the host default branch, "and if
it does not, creation fails and says so rather than falling through to `main`."

The temptation is to treat the chain as a fallback chain, where each term that cannot be
satisfied yields to the next. That is wrong, and the architecture says why. A configured
integration branch is a statement about where this work merges. If it is configured and absent
from the host, the situation is not "no integration branch, use the default" — it is "this
repository says work merges to `dev/erik` and the host has never heard of `dev/erik`." Opening a
PR against `main` there would target the wrong branch on purpose, and the operator's own config
is what says so.

So the middle term has three outcomes, not two:

| Condition | Outcome |
|---|---|
| `--base` given | use it, `source=flag`. No host confirmation — the operator named it. |
| no flag, integration branch set, `branch_exists` true | use it, `source=integration-branch` |
| no flag, integration branch set, `branch_exists` false | **refuse**, naming the branch |
| no flag, integration branch unset or empty | `default_branch(locator)`, `source=host-default` |

Note the first row. An explicit `--base` is not confirmed against the host, because
`open_pull_request` will reject an invalid base with a 422 that names it, and a pre-check would
add a host round-trip to tell the operator something the write already tells them. The
integration branch gets its check because the fall-through it prevents is silent, where a bad
`--base` is loud.

`git.integration_branch` is read through `ContextForgeClient.get_config`, the same subprocess
path `resolve_diff_base` uses. Unlike `resolve_diff_base`, this slice does **not** degrade an
unreachable `cf` to a default: `resolve_diff_base` falling back to `main` for a diff base is a
read-only guess with a visible consequence, while silently retargeting a PR is a write. When `cf`
is unavailable the integration-branch term is simply absent (the key is unset as far as we can
tell) and the chain proceeds to the host default — but when `cf` answers with a branch name, that
name is authoritative and the confirmation check applies.

The chosen base and its source are printed before any write, per the architecture.

### D2 — The pushed-branch precondition, and why it is two checks

The architecture: "The head branch must already be on the host and match the local branch;
`sq pr create` never pushes, and when the branch is missing or behind it fails naming the push
the operator should run."

"Missing" and "behind" are different failures and need different checks.

**Missing** is `branch_exists(locator, head)` returning false. The fix is `git push -u <remote>
<head>`.

**Behind** is subtler: the branch is on the host, but the host's copy is not the commit the
operator is about to describe. Squadron would assemble a description from local commits, some of
which no reader of the PR can see. The check compares the local head sha against the sha the host
reports for that branch. The fix is `git push <remote> <head>`.

The remote sha comes from `git ls-remote <remote> refs/heads/<head>` through the adapter's
process-runner seam, bounded by `GIT_QUERY_TIMEOUT_SECONDS` — the constant `codehost/refs.py` and
`codehost/remotes.py` already use for git queries, *not* `HOST_COMMAND_TIMEOUT_SECONDS`, which is
for `gh` invocations. Both are 30 seconds today, so the practical bound is the same and the
distinction is about which constant a future change to either would move.

This is a git call, not a `gh` call, and it is deliberately not a new protocol operation: the
protocol's operation list is fixed by the architecture and adding an operation requires a reason.
"What sha does the remote have for this branch" is answerable with git against a remote the
locator already names, the way 381 fetches refs with git rather than through `gh`.

A detached HEAD refuses before either check, naming the condition — there is no branch to open a
PR from. `github_cli._branch_for` already raises `TargetUnresolvableError` for exactly this, and
the current-branch helper this slice adds behaves the same way.

Both checks run before the model call, and neither writes.

### D3 — The one-shot path is `run_review_with_profile`'s sibling, not `summary_oneshot`

The plan entry directs composition "through `pipeline/summary_oneshot` ... after verifying the
`sdk` profile through it and correcting the docstring or the routing." That verification is done,
and here is what it found.

`summary_oneshot.capture_summary_via_profile_with_telemetry` contains no `is_sdk_profile` check
and no rejection path. It calls `get_profile(profile)`, `ensure_provider_loaded`, `get_provider`,
builds an `AgentConfig`, and iterates `handle_message`. Passing `"sdk"` resolves the SDK profile
and dispatches through the SDK provider; the response loop even carries SDK-specific handling for
`tool_use` and `tool_result` message types. So the module does not refuse `sdk`.

The gate is in its caller. `pipeline/actions/summary.py` branches on `is_sdk_profile(profile)`
and routes the SDK arm to `context.sdk_session.capture_summary(...)`, refusing outright when
`context.sdk_session is None`. That is a pipeline concern: a pipeline summary step runs inside a
live SDK session and must reuse it rather than opening a second one.

`sq pr create` has no SDK session and no pipeline context. It is a CLI command, and the CLI
already has a one-shot that handles `sdk`: `review_client.run_review_with_profile`, which
`sq review code --profile sdk` uses today with the same `get_profile` → `get_provider` →
`create_agent` → `handle_message` sequence and no session. The `sdk` profile through a one-shot
CLI call is therefore not a risk — it is the review command's daily path.

**Decision.** The composer does not call `summary_oneshot`. It performs the same one-shot
sequence directly, in `pr/body.py`, taking `model` and `profile` exactly as the review flags
supply them. Reasons:

- `summary_oneshot`'s parameters (`allowed_tools`, `model_allows_tools`, the dispatch-context
  assembly its caller prepends) are pipeline-shaped. PR composition wants none of them; the model
  gets facts and nothing else, and giving a description-writer tools would let it assert things
  no input supports, which is precisely what initiative 360's traceability rule forbids.
- `run_review_with_profile` is review-shaped — it takes a `ReviewTemplate`, injects file
  contents, and parses a `ReviewResult`. None of that applies.
- Both are ~200-line functions serving their own callers well. A third caller bending either one
  is how those functions become the thing nobody can change.

The composer is small because it does one thing: prompt in, text out, through a profile.

**The correction owed.** `summary_oneshot`'s docstring says "One-shot summary execution for
non-SDK provider profiles," which describes its caller's policy, not its behavior. This slice
corrects the docstring to say the module routes any registered profile and that the pipeline's
SDK-session reuse is the *caller's* rule. The routing is not changed — it is correct, and the
pipeline gate stays where it belongs.

### D4 — Squadron writes the headings; the model writes only prose

Five sections, fixed, in this order:

| Section | Input | No-input line |
|---|---|---|
| What changed | commits (+ slice design when present) | never — commits always exist |
| Why | slice design, else commits | never |
| How it was verified | checked task items | "No task records for this branch." |
| Known gaps | unchecked task items | "No task records for this branch." |
| Review provenance | latest in-range review | "No squadron review covers this branch's commits." |

The body is not one model response parsed into sections. Squadron emits the headings and requests
prose per section, and the deterministic facts are written by squadron directly beneath the prose
they support: the commit list under "what changed," the slice design path under "why," the review
artifact path, verdict, and reviewed sha under "review provenance." A reader can check the prose
against the facts because both are in the same section, and the facts are copied, never
generated.

"How it was verified" and "known gaps" both derive from the task file, which is why they share a
no-input line. The task-file checkbox parser is new — `_tasks_input` passes task files to the
review template as *paths* for injection and nothing in the tree reads their checkbox state.
Parsing is lenient per the project's parsing rules: any list item whose marker is `[x]` or `[X]`
counts as checked, `[ ]` as unchecked, at any indent depth, with sub-items attributed to their
own state rather than their parent's.

A section with no input carries its line verbatim and the model is not asked for prose there. The
architecture is explicit: "never a guess and never a silent omission."

### D4a — The title

The body gets five sections and a presence check; the title got named in the flag list and
nowhere else. It needs its own rule, because "produces a title and a body" is all the
architecture says.

The title is resolved in three terms, in order:

| Term | Title | Source |
|---|---|---|
| `--title` given | use it verbatim | flag |
| slice branch, `cf` resolved it | the design's `# Slice Design: {name}` H1, minus the prefix | slice |
| otherwise | the model composes it, constrained to the commit subjects | model |

The middle term is the common case on this initiative and it is deterministic. The frontmatter's
`slice` field is the kebab-case slug (`create-a-pr-with-a-good-message`), not a title, so the
human-readable name comes from the design's H1 — `# Slice Design: Create a PR with a Good Message`
— with the `Slice Design: ` prefix stripped. Asking a model to invent a title when the slice is
literally named already would be spending tokens to lose information. A design whose H1 does not
match that shape falls through to the third term rather than emitting a malformed title.

The third term is the only one that reaches the model, and it is bounded: the model is asked for
one line under 72 characters, given the commit subjects and nothing else. That length is the
project's own commit-summary convention, applied to the same kind of object — the one-line
summary a reader scans. A response that is empty, multi-line, or over the bound falls back to the
first commit's subject, which is always present and always truthful. This is the one place in the
slice where a model failure degrades rather than refuses, and the reason is proportion: a
mediocre title on a PR whose body is correct is not worth failing a creation over, where a
missing body *section* is.

The title participates in the dry-run equality guarantee exactly as the body does — resolved
once, bound to one variable, shared by both paths (D8).

### D5 — The presence-and-filled check, and what "filled" means

Before creation, the composed body is checked: all five headings present, in order, and each
section either containing prose or containing exactly its no-input line. A failure is an error
and creates nothing — "a body that fails that check is an error, not a degraded PR."

"Filled" needs a definition that a model cannot accidentally satisfy. A section is filled when
its content, after stripping whitespace and the squadron-written deterministic block, is
non-empty and is not solely a restatement of the heading. The check is structural, not semantic:
it catches the model dropping a section or emitting a bare heading, which is the failure mode
that actually occurs. It does not attempt to judge prose quality, which is not checkable and
would be a false promise.

The check runs on the assembled body, after squadron has inserted its own headings and facts. It
therefore validates the artifact that would be posted, not the model's raw response — which
means a model that returns a section out of order or with a reworded heading fails at assembly
time, where squadron's headings are authoritative and the model's are discarded.

One deliberate asymmetry: the check failing exits non-zero without a retry. A retry loop would
make the token cost of `sq pr create` unbounded and unpredictable, and the operator can rerun the
command themselves having seen why it failed.

### D6 — The `pr/` package sits above the import boundary

`tests/codehost/test_import_boundaries.py` pins the rule that `review/` never imports
`codehost/`, with one narrow exception carved at 384 (`review/pr_comment.py` importing
`PullRequestRecord` alone). The graph is `cli → codehost → core` and `cli → review`.

This slice's logic needs both: `PullRequestRecord` and `RepositoryLocator` from `codehost`, and
`resolve_slice_info`, frontmatter reading, and git helpers from `review`. Per the 384 precedent,
that combination belongs in the CLI layer. But putting it *in* `cli/commands/pr.py` would give
that file base selection, preconditions, three input gatherers, assembly, composition, and the
section check — far past the ~300-line guideline and untestable without Typer's runner.

So `src/squadron/pr/` is a new package in the CLI's dependency tier: it imports `codehost` and
`review` freely, nothing imports it except `cli/`, and the import-boundary test gains a case
asserting `review/` still does not import `pr/`. The command function keeps orchestration,
printing, and exit codes — the shape `review_pr.py` already has, where `_post_review` holds the
decision table and the command holds the flags.

`create` does **not** reuse `pr.py`'s `resolve_and_fetch_pull_request`, which resolves an
*existing* PR and fetches its refs. Creation needs only host + remotes + locator, which are that
helper's first three steps. Those three are extracted into a shared `resolve_locator(...)` that
both `show`'s helper and `create` call, rather than duplicated — the extraction is small and both
callers land in this slice's diff.

### D7 — "The latest review" is scoped to this branch's commits

The architecture: "the most recent review artifact whose reviewed sha lies in the base-to-head
range, so a review of an earlier merged branch that is an ancestor of this one never qualifies,
else none."

This is the rule that makes provenance honest. A long-lived integration branch accumulates merged
work, and every one of those merges brought review artifacts whose reviewed shas are ancestors of
the current head. Citing the most recent one by mtime would attach a neighboring slice's review
to this PR.

The scan:

1. Enumerate `*-review.*.md` in the reviews directory — both the project's and, when the
   repository is unplanned, the configured external directory 383 established.
2. Read each file's frontmatter for `reviewedSha` (the field 383 writes; PR reviews take it from
   the record's head sha, slice reviews from `git rev-parse HEAD` at save time).
3. Keep those whose sha is in `git rev-list <base>..<head>` — membership in the range, not
   ancestry of head, which is what excludes the merged ancestor.
4. Of the survivors, take the one whose reviewed sha is newest in the range.

An artifact with no `reviewedSha`, an unparseable sha, or a sha git does not recognize is skipped
with a WARNING naming the file — not fatal, because a malformed neighbor artifact should not
block PR creation, and observable, because silently dropping a review that *should* have been
cited is exactly the failure the provenance section exists to prevent.

No qualifying review yields the no-input line. That is the supported path, not a degradation to
apologize for: a branch nobody reviewed says so.

The scan is written in `pr/inputs.py`. `locate_review` is not reusable — it is index-keyed and
raises on ambiguity rather than ordering, both correct for its own callers.

### D8 — Every host call is bounded; the write is last and happens once

Following 384's D8. The calls on this path are four `gh` calls — `identify_operator`,
`branch_exists`, `default_branch`, `open_pull_request` — and one git call, the `ls-remote` sha
read. All but `open_pull_request` are reads and all precede the model call; `open_pull_request` is
the only write and is the last thing the command does.

All five go through the adapter's process-runner seam, the `gh` calls bounded by
`HOST_COMMAND_TIMEOUT_SECONDS` and the git call by `GIT_QUERY_TIMEOUT_SECONDS` (D2), and every one
is wrapped in the pattern `review_pr.py` set:
`except CodeHostError as exc: render_code_host_error(exc); raise typer.Exit(code=1) from exc`.
A transport failure or timeout at any read refuses before the model runs. A failure at the write
is reported with the host's reason — notably `PullRequestCreationRejectedError`, which
`open_pull_request` raises on HTTP 422 with the hint that the head branch may already have an
open PR.

The write is not retried. A 422 for "PR already exists" is the operator's to resolve, and a
retried create that succeeds on the second attempt after a network error that actually landed
would open two PRs.

**The model call is the sixth I/O path, and it fails differently.** The composer is a new I/O path
— provider dispatch through `create_agent` and `handle_message` — so the failure-mode enumeration
rule applies to it too, and its failures are not `CodeHostError`. A provider that is unreachable,
unauthenticated, or times out mid-stream, and any exception raised during `handle_message`, are
caught at the composer's boundary, logged at ERROR with `logger.exception`, and become a non-zero
exit that creates nothing. This is a process-boundary handler in the project's exception rules'
sense, which is what permits catching broadly there; every narrower handler in the slice names its
exception type.

The consequence of position is worth stating: because the model call sits after every read and
before the only write, a composition failure costs tokens but writes nothing, and there is no
state to unwind. That is the same reason the presence check (D5) can refuse without cleanup.

`--dry-run` returns before the write, printing title and body to stdout with the base and its
source on stderr — the same stdout/stderr split 384 chose, so the body can be piped. Because the
body is bound once and shared by both paths, dry-run/real equality is structural, not
disciplinary. Unlike 384's `--dry-run`, this one does **not** require an opt-in flag to
accompany it: `sq review pr --dry-run` needed `--post` because posting was the opt-in behavior
and a dry run of a non-write is meaningless, whereas `sq pr create` *is* the write, so
`--dry-run` is simply its preview.

## Integration Points

### Provides

- `sq pr create` — the initiative's second and final host write.
- The `src/squadron/pr/` package: base selection, preconditions, input gathering, assembly, and
  body composition, each independently testable.
- `parse_slice_branch(branch) -> int | None` — the `{index}-slice.{name}` parser the tree lacks.
- `parse_task_items(text) -> TaskItems` — the first checkbox reader in the codebase. Written
  generally enough that a later consumer (progress reporting, slice closeout) can use it, but
  not generalized beyond this slice's need.
- Git helpers for current branch and for commits in a range.

### Consumes from Other Slices

- **381**: `open_pull_request`, `default_branch`, `branch_exists`, `identify_operator`,
  `RepositoryLocator`, remote selection, the process-runner seam, `HOST_COMMAND_TIMEOUT_SECONDS`,
  and `render_code_host_error`.
- **383**: the reviews directory resolution (project and external) and the `reviewedSha`
  frontmatter field the provenance scan reads.
- **384**: the CLI structure precedent — decision logic in a helper, flags and exit codes in the
  command, and the stdout/stderr split for dry runs.
- **[100]**: the provider registry and profile system.

## Success Criteria

### Functional

- On a slice branch in a planned repository, the body cites the slice design, lists checked task
  items under "how it was verified" and unchecked items under "known gaps," and names the review
  artifact and its reviewed sha under "review provenance."
- On a non-slice branch in an unplanned repository, the body has all five sections, three of them
  carrying the explicit no-input line, and creation succeeds.
- A branch whose only covering review is a merged ancestor's yields the no-input provenance line,
  not that review.
- With `git.integration_branch` set to a branch absent from the host, creation fails naming the
  branch, and does not target the default branch.
- With `git.integration_branch` set to a branch present on the host, that branch is the base and
  the printed source says so.
- An unpushed branch fails before any host write and prints the push command; a branch whose
  host sha differs from local fails the same way with the same command.
- A composed body missing a section fails the presence check, exits non-zero, and creates
  nothing — verified by the fake runner recording zero write calls.
- On a resolved slice branch the title is the slice's human name with no model call; `--title`
  overrides it; on a non-slice branch a model title over 72 characters or empty falls back to the
  first commit's subject.
- `--dry-run` title and body equal what the next real run creates.
- With the adapter unable to identify the operator, the command exits non-zero, names the reason,
  and makes no write.
- One recorded live creation on a real PR.

### Technical

- Every `gh` call on the path carries `HOST_COMMAND_TIMEOUT_SECONDS` and the `ls-remote` call
  carries `GIT_QUERY_TIMEOUT_SECONDS`; a scripted timeout at each of the five call sites exits
  non-zero with no effective write.
- A provider failure during composition exits non-zero, logs at ERROR, and creates nothing.
- The default path (no flags) makes exactly one host write, and only after every read succeeds.
- `review/` does not import `pr/`, asserted by the import-boundary test.
- The checkbox parser handles nested items, `[x]`/`[X]`, and trailing whitespace, with a test
  fixture using this slice's own task file once it exists.
- `pyright` reports zero errors; `ruff format` and `ruff check` are clean.
- The `summary_oneshot` docstring correction lands with a test asserting the module routes a
  registered profile without reference to SDK-ness.

### Verification Walkthrough

Draft — refined at Phase 6 with actual output.

**1. Dry run on this slice's own branch, in a planned repository.**

```bash
git checkout 385-slice.create-a-pr-with-a-good-message
sq pr create --dry-run
```

Expect: base and source on stderr (`squadron-pr`, source `integration-branch`), then title and
body on stdout with all five sections. "How it was verified" lists the checked task items; "known
gaps" lists the unchecked ones; "review provenance" names the review artifact and reviewed sha,
or the no-input line if no review yet covers the branch.

**2. Prove the base refusal.**

```bash
cf config set git.integration_branch dev/does-not-exist
sq pr create --dry-run
cf config set git.integration_branch squadron-pr
```

Expect: exit 1 naming `dev/does-not-exist`, with no mention of `main` and no PR created.

**3. Prove the push precondition.**

```bash
git checkout -b 385-scratch && git commit --allow-empty -m "test: unpushed"
sq pr create --dry-run
```

Expect: exit 1 naming the branch as absent from the host and printing the `git push -u` command.
Then push it, add another local commit, and rerun: exit 1 for the sha mismatch with the
`git push` command.

**4. Unplanned-repository path.**

Run from a clone with no `project-documents/` on a branch whose name does not match the slice
convention. Expect: five sections, three no-input lines, and a successful dry run.

**5. Dry-run/real equality, then live creation.**

```bash
sq pr create --dry-run > /tmp/dry.txt
sq pr create
gh pr view <n> --json title,body
```

Expect: the created PR's title and body match `/tmp/dry.txt`. Record the URL as evidence.

**6. Confirm the review can read it back.**

```bash
sq review pr <n> --dry-run --post
```

Expect: the reviewer parses the created body's sections — the two-readers claim, checked rather
than asserted.

## Risk Assessment

- **Model composition quality (medium).** The prose is only as good as the one-shot call. The
  presence check catches structural failure but not weak writing. Mitigated by giving the model
  facts only, and by the deterministic blocks carrying the load-bearing content — a reader who
  ignores every sentence still has the commit list, the slice link, and the review provenance.
  The plan entry also flagged the `sdk`-through-one-shot risk; D3 resolves it, and the residual
  risk is quality, not routing.
- **Checkbox parsing against real task files (low-medium).** The parser is new and its input is
  hand-edited markdown. Mitigated by lenient parsing and by a fixture using a real task file, per
  the project's parsing rules.
- **The review-scoping scan on large repositories (low).** Reading frontmatter for every review
  artifact is linear in the reviews directory. Acceptable at current scale; if it ever is not,
  the fix is to filter by filename before reading, which needs no design change.

## Implementation Notes

### Order

1. `pr/branch.py` and `pr/tasks.py` — the two pure parsers, with tests. No dependencies.
2. Git helpers (current branch, commits in range) beside the existing ones in `review/git_utils.py`.
3. `resolve_locator` extraction from `resolve_and_fetch_pull_request`, with `show` unchanged.
4. `pr/base.py` and `pr/preconditions.py` — the refusal paths, against the fake runner.
5. `pr/inputs.py` — gathering, including the review scan.
6. `pr/assembly.py` — the deterministic parts.
7. `pr/body.py` — the composer, the section contract, and the presence check, with a fake
   composer in tests so no test calls a model.
8. `cli/commands/pr.py` — the `create` command wiring it together.
9. The `summary_oneshot` docstring correction.
10. Live creation and evidence.

Steps 1–2 and 4–7 are where the tests live; step 8 is thin by construction.

### Testing

Unit tests against the fake process runner for every host interaction, mirroring 384's matrix:
each of the five host call sites gets a classified transport failure and a scripted timeout,
both asserting exit 1 and no effective write. The composer is faked in every test — the model is
exercised once, live, in step 10.

The dry-run/real equality test asserts the body object is bound once and passed to both paths,
structurally, rather than comparing two separately composed strings.

## Design Review Response

Slice review at `385-review.slice.create-a-pr-with-a-good-message.md` (`z-ai/glm-5.2`, reviewed
sha `2c138d42`): **CONCERNS**, six PASS and three concerns. All three addressed; none required a
change of approach.

**F007 — wrong timeout constant for `git ls-remote`.** Correct, and the kind of error that
propagates: D8 called all five calls "host calls bounded by `HOST_COMMAND_TIMEOUT_SECONDS`", but
`ls-remote` is a git query, and `codehost/refs.py` and `codehost/remotes.py` bound those with
`GIT_QUERY_TIMEOUT_SECONDS`. Both constants are 30 seconds today, so the practical bound was never
wrong — what was wrong is which constant a future change would move. Fixed in D2, in D8's call-site
list (now four `gh` calls and one git call), and in the technical success criterion that had
repeated the same conflation.

**F008 — the model call's failure mode was not enumerated.** Correct, and it is the project's own
design-principles rule (failure-mode enumeration for each new I/O path) applied to the one path
the design had treated as neutral. D8 gains the sixth path: provider errors during composition are
caught at the composer's process boundary, logged at ERROR with `logger.exception`, and exit
non-zero creating nothing — with the note that because composition sits after every read and
before the only write, that failure costs tokens but leaves no state to unwind.

**F009 — the title mechanism was under-specified.** Correct, and a real hole: `--title` appeared in
the flag list, the data flow, and the `open_pull_request` call, and the design never said where a
title comes from without the flag. Added as **D4a**, a three-term rule — the flag, else the slice's
human name from the design's frontmatter (deterministic, and the common case here), else a
model-composed line bounded at 72 characters falling back to the first commit's subject. That
fallback is the slice's one degradation rather than refusal, and D4a states the proportionality
argument for the asymmetry against D5's hard failure on a missing body section.

The six PASS findings covered D1's refusal-not-fall-through, the D4/D5 section contract, D3's
one-shot correction, D6's import-boundary placement, D7's range-membership scan, and D8's host-call
enumeration. No finding disputed a decision; the three concerns were a wrong constant, a missing
enumeration, and a gap.
