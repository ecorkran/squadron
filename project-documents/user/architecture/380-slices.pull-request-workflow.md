---
docType: slice-plan
parent: 380-arch.pull-request-workflow.md
project: squadron
dateCreated: 20260912
dateUpdated: 20260912
status: not_started
---

# Slice Plan: Pull Request Workflow

## Parent Document
`380-arch.pull-request-workflow.md` — Architecture: Pull Request Workflow

## Planning Context

Architecture-level. The parent describes three capabilities on one new boundary:

- **Review a PR** — `sq review pr <target>` as the existing code review with adapter-resolved inputs.
- **Post findings back** — an opt-in, attributed, idempotent write of the saved review to the PR.
- **Create a PR** — `sq pr create` composing a title and body from commits, slice artifacts, and
  the latest review, with squadron-written sections the model fills.

The one genuine foundation is the code-host adapter: a protocol whose operation list the parent
fixes, a GitHub implementation over the operator's `gh`, a typed PR record, and the enumerated
failure modes. Everything else consumes it. The review command and the PR-creation command are
independent of each other once the adapter exists; posting depends on persistence, because it
posts a saved artifact; persistence is sequenced behind the 900-band slices 916 and 917 that are
changing the seams it attaches to.

Two constraints from the parent shape the order. First, existing flows do not change and no PR is
ever required, so every slice adds a path beside the current ones and each leaves `sq review code`,
slice persistence, and the pipeline action behaving as today. Second, the review command can ship
before persistence: an unsaveable PR review displays its result and warns that it was not
persisted, through the existing not-persistable path, until the persistence slice lands. That is
stated, not silent, and it lets the two `main`-side dependencies land on their own schedule.

Slice indices follow the initiative base, 381 onward. Work forks from and merges into
`squadron-pr`, the configured integration branch for this initiative.

---

## Foundation Work

1. [x] **(381) Code-Host Adapter and PR Target Resolution** — The adapter protocol with exactly the
   operation list the parent fixes (resolve a PR, report its base and the host default branch,
   check a branch exists on the host, fetch base and head, list unresolved review discussions,
   find and update the operator's own prior comment, post a review comment, open a PR, identify
   the operator); its GitHub implementation over `gh`, reached through one injected process-runner
   seam with a timeout constant; the typed PR record (host, owner, repository, number, base ref,
   head ref, head sha, URL) produced once at the boundary and living in the adapter package; the
   target grammar (number, URL, `owner/repo#n`, branch, absent) with explicit forms resolving
   against any matching local remote and bare forms requiring exactly one host remote, foreign
   repositories refused by name; base and head fetched into namespaced local refs with the
   merge-base range computed between them; every failure mode named in the parent as a distinct
   error with a WARNING-or-higher log line and a non-zero exit, each tested against a fake runner;
   and `sq doctor` presence checks (`gh` on PATH, hosts file readable) within 905's pure-check
   contract. Read-only against the host. The proving consumer is `sq pr show <target>`, a
   read-only command in the new `sq pr` group that prints the resolved record, the fetched refs,
   and the range that a review would examine.
   - **Value:** Architectural enablement — every other slice consumes this boundary, and the
     failure modes are implemented and tested once. Operator value from `sq pr show`: "what would
     be reviewed" is answerable before any model runs.
   - **Success Criteria:**
     - Each of the five target forms resolves to the same PR record for the same PR; the
       fork-with-`upstream` layout resolves explicit forms and refuses bare forms with the remote
       names listed.
     - After resolution, `git merge-base` between the two namespaced refs succeeds without the
       operator's clone having fetched either branch beforehand, and no operator branch or the
       working tree has changed.
     - Every named failure mode has a unit test using the fake runner that asserts the error type,
       the log line, and the exit code; a wedged `gh` produces the timeout error within the bound.
     - `sq doctor` reports `gh` presence and hosts-file readability and makes no subprocess or
       network call; a missing `gh` is reported, not installed.
     - `sq pr show` on a real PR prints the record, refs, and range, and one such run is recorded.
     - No import from the adapter package into the review package's call graph; the review
       package imports only the record type.
   - **Dependencies:** [100] (CLI command registration), 905 (doctor contract).
   - **Interfaces:** Provides the adapter protocol, the GitHub implementation, the PR record, and
     the process-runner seam consumed by 382, 384, and 385.
   - **Risk:** Medium — `gh`'s JSON shapes and the fetchable-ref conventions are observed, not
     guaranteed, and enterprise host configurations vary.
   - **Relative Effort:** 4/5

---

## Feature Slices

2. [x] **(382) Review a PR** — `sq review pr <target>` on top of 381: the adapter-resolved range and
   PR record handed to the existing code review; the scratch worktree for tool-enabled reviews
   with its full lifecycle (created under squadron's data directory, named by PR key plus run id,
   registered with git, lock file carrying pid and process start time, orphan sweep on every
   invocation, submodules initialized, removed on success, failure, and timeout, unremovable
   worktree reported by path); the two-root rule, with every convention input (rules directory,
   project instructions file) loaded from the operator's checkout and only reviewed code from the
   worktree, both roots recorded; PR metadata (title, body, linked issues, unresolved discussions)
   rendered by the code prompt builder as one labeled fenced block whose outer fence is longer
   than any inner fence run and whose label is neutralized inside the content, truncated by the
   file-injection size discipline, as one optional input on the existing code template that the
   pipeline action tolerates and ignores; the no-tools path reviewing from the fetched ref alone;
   and full parity with the existing review flags (`--model`, `--profile`, `--no-tools`, `--rules`,
   `--rules-dir`, `--no-rules`, `--files`, `-v`, `--output`, `--json`). Until 383 lands, the result
   is displayed and the existing not-persistable warning names the reason.
   - **Value:** User value — the initiative's headline capability. A PR is reviewed with one
     command, against the range the host shows, by a reviewer reading the PR's own files.
   - **Success Criteria:**
     - `sq review pr` on a PR whose base has moved produces the same changed-file set the host's
       PR view shows; `sq review code --diff` behavior is unchanged by the slice.
     - With tools enabled, findings cite paths that exist in the PR head; the operator's checkout
       is byte-identical before and after, including after a forced failure mid-review.
     - Two concurrent tool-enabled reviews of the same PR both complete; a worktree orphaned by a
       killed process is pruned by the next invocation and does not block it.
     - A PR that edits the rules directory or the project instructions file is reviewed against
       the checkout's versions, and the artifact's recorded roots show it.
     - A PR body containing a triple-backtick fence and a copy of the block label does not escape
       the data block; a test asserts the rendered prompt keeps the block intact.
     - A repository with submodules yields a worktree in which submodule paths exist; an
       unfetchable submodule fails the review naming it.
     - Every existing review flag behaves on `sq review pr` as on `sq review code`; running without
       383 prints the not-persistable warning with the reason.
   - **Dependencies:** 381; [100] (code review builder, `run_review_with_profile`); 916 (merge-base
     `--diff` semantics, jail-root handling) and 904 (diff-membership location check) as they exist
     on `main`.
   - **Interfaces:** Consumes the adapter protocol and PR record. Provides the PR review path that
     383 persists and 384 posts. Adds one optional input to the code template.
   - **Risk:** Medium — worktree lifecycle under concurrency and abnormal exit, and submodule
     handling in enterprise repositories.
   - **Relative Effort:** 4/5

3. [x] **(383) PR-Keyed Review Persistence** — The structural save-target contract on the persistence
   side (filename stem, target-specific frontmatter fields, reviews directory) that a slice target
   and a PR target both satisfy, with the arch review migrated off its minimal-`SliceInfo`
   fabrication and the pipeline action's step-keyed save migrated onto the same contract, so one
   shape replaces three; the PR review's frontmatter (`docType: review`, `reviewType`, `aiModel`,
   `sourceDocument` as the PR URL, a `pr` field carrying the record, reviewed sha taken from the
   record, no slice fields) verified against `cf validate frontmatter` and the schema-drift test,
   with any required context-forge schema change landed first as a named dependency; the
   non-numeric PR filename prefix, with `{index}-review.*` consumers (resolution, metrology
   capture) shown never to match and `*-review.*` consumers taught to read the target kind from
   the prefix; the `review.external_reviews_dir` config key with its default under squadron's
   per-user data directory keyed by host, owner, and repository, the new `--reviews-dir` override,
   and the chosen location and its source printed; the rules-source provenance field as one
   additive optional frontmatter key; and the naming-conventions guide updated with the PR form.
   The conversion from PR record to save target lives in the CLI layer.
   - **Value:** User value — PR reviews are kept, archived, and digested like every other review,
     in repositories squadron did or did not plan. Developer value — persistence stops fabricating
     slice records for non-slice reviews.
   - **Success Criteria:**
     - A PR review in a planned repository saves under `project-documents/user/reviews/` with the
       PR-keyed name, passes `cf validate frontmatter` and the commit gate, and its `reviewedSha`
       equals the PR record's head sha, not the operator's HEAD.
     - In a repository with no `project-documents/`, the review saves under the configured external
       directory, the location and its source are printed, and nothing is written inside the
       repository.
     - `sq review resolve <n>` and metrology capture for slice `n` never pick up a PR review of
       PR `n`; `*-review.*` discovery classifies PR reviews by target kind.
     - Arch reviews and pipeline step-keyed reviews save exactly as before, byte-for-byte on their
       existing fixtures, through the new contract.
     - Archiving, digest, and 917's integrity checks run on a PR review artifact unchanged.
     - The rules-source field reads `project`, `user`, or `template` and matches the directory the
       loader actually used; existing artifacts without the field still parse.
   - **Dependencies:** 382; 916 and 917 merged to `main` and present on `squadron-pr`; context-forge
     schema change if `cf validate frontmatter` rejects the PR shape.
   - **Interfaces:** Provides the save-target contract consumed by 384 and 385, and the PR review
     artifact 384 posts. Changes `persistence.py` shape for all three existing callers.
   - **Risk:** Medium — the `cf` schema is not squadron's to change, and three callers migrate at
     once.
   - **Relative Effort:** 3/5

4. [x] **(384) Post Findings to the PR** — The opt-in `--post` on `sq review pr`: the saved review
   rendered as one summary comment carrying verdict, findings, model, reviewed head sha, a
   generated-by-squadron statement, and a hidden marker with the PR key; idempotency per
   authenticated login (update the marked comment authored by the current login, report marked
   comments from other operators, never edit them; after a concurrent double-post by one operator,
   update the earliest and report the rest); identity refusal (no login from the adapter, no
   post, with the reason); `--dry-run` printing the exact comment; and the staleness statement
   when the PR head has moved since the reviewed sha.
   - **Value:** User value — the review reaches the people reading the PR, attributed to the
     operator who asked for it, without a copy-paste step.
   - **Success Criteria:**
     - `--post` is off by default; without it no host write occurs, verified by the fake runner
       recording zero write calls.
     - Two consecutive posts by the same login leave one squadron comment, updated; a post by a
       second login leaves two, one per login, and reports the other.
     - With the adapter unable to identify the operator, the command exits non-zero, names the
       reason, and makes no write.
     - Posting against a PR whose head sha differs from the artifact's `reviewedSha` includes the
       staleness line naming both shas.
     - `--dry-run` output equals the body actually posted on the next real run.
     - One recorded live post on a real PR.
   - **Dependencies:** 383 (posts the saved artifact), 381 (comment operations).
   - **Interfaces:** Consumes the adapter's comment operations and the persisted PR review. Adds
     `--post` and `--dry-run` to `sq review pr` only.
   - **Risk:** Low — the operations are small and the fake runner covers the branches.
   - **Relative Effort:** 2/5

5. [x] **(385) Create a PR with a Good Message** — Designed: `385-slice.create-a-pr-with-a-good-message.md`. `sq pr create`: base selection in the parent's
   order (`--base`, then the configured integration branch when the adapter confirms it exists on
   the host, else the host default branch, with the chosen base and its source printed and no
   fall-through to `main`); the pushed-branch precondition (head on the host and matching the
   local branch; never pushes; names the push command on failure); input gathering (commits in the
   base-to-head range, the slice design and tasks when the branch name matches
   `{index}-slice.{name}` and `cf` resolves it, and the latest review whose reviewed sha lies in
   that range, else none); deterministic assembly of the exact parts (commit list, linked slice,
   review provenance, reviewed sha); one-shot prose composition with the review model and profile
   flags (385 design resolved the `sdk`-through-one-shot question: `summary_oneshot` does not
   refuse `sdk` — its caller `pipeline/actions/summary.py` gates on SDK-session reuse, a pipeline
   concern the CLI does not have — so the composer performs the one-shot sequence directly, as
   `run_review_with_profile` already does, and the correction owed is to `summary_oneshot`'s
   docstring, not its routing); squadron-written section headings (what changed, why,
   how it was verified, known gaps, review provenance) with the model filling prose, sections
   without an input carrying an explicit no-input line, and a presence-and-filled check before
   creation; `--dry-run` printing title and body; and creation through the adapter.
   - **Value:** User value — a PR description built from what squadron already knows, readable by
     humans and parseable by AI reviewers including `sq review pr` itself.
   - **Success Criteria:**
     - On a slice branch in a planned repository, the body cites the slice design, lists checked
       tasks under "how it was verified" and unchecked under "known gaps", and names the review
       artifact and reviewed sha under "review provenance".
     - On a non-slice branch in an unplanned repository, the body has all five sections, three of
       them carrying the explicit no-input line, and creation succeeds.
     - A branch reviewed only by a merged ancestor's review yields the no-input provenance line,
       not that review.
     - With `git.integration_branch` set to a branch absent from the host, creation fails naming
       the branch and does not target the default branch.
     - An unpushed or behind branch fails before any host write and prints the push command.
     - A model response missing a section fails the check and creates nothing.
     - `--dry-run` title and body equal what the next real run creates; one recorded live creation.
   - **Dependencies:** 381 (base, branch-exists, open-PR operations); 383 for the review input
     (without it the provenance section carries the no-input line, which is the supported
     degraded path).
   - **Interfaces:** Consumes the adapter, `cf` slice resolution, and the one-shot summary path.
     Adds `create` to the `sq pr` group.
   - **Risk:** Medium — model composition quality and the `sdk` profile through the one-shot path
     are unverified until tried.
   - **Relative Effort:** 3/5

---

## Integration Work

6. [ ] **(386) Slash-Command Parity, Documentation, and Live Evidence** — Designed: `386-slice.slash-command-parity-documentation-and-live-evidence.md`. `/sq:review pr` and
   `/sq:pr` transports producing the same artifacts as the CLI; README and quickstart coverage for
   review, post, and create, including the unplanned-repository path and the `--reviews-dir`
   and `review.external_reviews_dir` surface; `sq doctor` output documented; and a recorded
   end-to-end run on a real PR of this initiative's own branch (review, post, and a PR created by
   `sq pr create`), kept as evidence in the initiative's DEVLOG entry.
   - **Value:** User value — the capabilities are discoverable and the transports agree. Evidence
     that the whole path works on a real host, not only against the fake runner.
   - **Success Criteria:**
     - `/sq:review pr <target>` and `sq review pr <target>` produce identical artifacts for the
       same PR and model.
     - Documentation examples run as written.
     - The recorded live run shows one squadron comment on the PR and a PR body with all five
       sections.
   - **Dependencies:** 382, 384, 385.
   - **Interfaces:** None new.
   - **Risk:** Low.
   - **Relative Effort:** 2/5

---

## Implementation Order

381 → 382 → 383 → 384 → 385 → 386, with 385 buildable any time after 381.

381 is first because it owns the only external contract (`gh` and the host's fetchable refs) and
every other slice consumes it; `sq pr show` proves it without a model in the loop.

382 follows because it is the headline capability and needs nothing from persistence to be useful;
its not-persistable warning is the stated bridge until 383.

383 waits for 916 and 917 to reach `main`, since it changes the persistence seams those slices are
changing, and possibly for a context-forge schema change. Nothing in 382 blocks on it.

384 follows 383 because it posts a saved artifact and the artifact's reviewed sha is what the
staleness statement compares against.

385 depends only on 381 and is placed after 384 for coherence, not sequence. It can be pulled
forward if PR creation is wanted before posting; without 383 its provenance section carries the
no-input line, which is a supported outcome.

386 is last because it documents and advertises what exists, and its live run needs all three
capabilities.

---

## Future Work

1. [ ] **(1) Direct GitHub API Implementation** — The second adapter implementation, for CI and
   hosted runs without `gh`, authenticated by a token from the environment. Designed for by the
   protocol; scheduled when a CI consumer exists.
2. [ ] **(2) Pipeline PR Input** — A pipeline `review` step accepting a PR target, once the CLI has
   proven the shape. The code template's optional PR input already tolerates it.
3. [ ] **(3) Inline Review Comments** — Posting findings as line-anchored comments rather than one
   summary comment. Needs the parser's location data mapped to the host's diff-position model.
4. [ ] **(4) Other Hosts** — GitLab or Gitea implementations of the adapter protocol.
5. [ ] **(5) Cross-Repository Targets** — Reviewing a PR in a repository that is not the current
   one, which needs a clone-or-fetch strategy the parent explicitly excludes.

---

## Notes

- Every slice adds beside existing paths. `sq review code`, slice-keyed persistence, and the
  pipeline action must pass their existing tests unchanged after each slice; 383 is the one slice
  that changes their internals and does so behind the same interfaces.
- Host writes in this initiative are exactly two: a comment (384) and a PR (385). No slice pushes
  a branch, merges, or edits another operator's comment.
- The fake process runner from 381 is the test seam for every later slice's host interaction;
  live runs are evidence, not the test suite.
- 383's context-forge dependency is discovered by running `cf validate frontmatter` on a sample PR
  review artifact early in its design, not at implementation time.
