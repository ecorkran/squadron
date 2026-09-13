---
docType: tasks
slice: code-host-adapter-and-pr-target-resolution
project: squadron
lldReference: project-documents/user/slices/381-slice.code-host-adapter-and-pr-target-resolution.md
parent: project-documents/user/architecture/380-slices.pull-request-workflow.md
dependencies: [905]
interfaces: [382, 384, 385]
status: not_started
dateCreated: 20260913
dateUpdated: 20260913
---

# Tasks: Code-Host Adapter and PR Target Resolution (2 of 2)

Continues
[381-tasks.code-host-adapter-and-pr-target-resolution-1.md](project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md),
which holds the Context Summary, the verified code anchors, the corrections
against the design, the `sq-base` coordination note, the standing constraints,
and Parts A–E. All of those govern the parts below; read that file first.

Parts A–E build the seam and the pure local logic (process runner, models,
errors, protocol, target grammar, remote selection, doctor checks). Everything
here touches the host or the operator-facing surface.

---

## Part F — GitHub Implementation: Reads

### Task F.1 — Capture `gh` response fixtures

- [x] Create `tests/codehost/fixtures/gh/`. Capture from **real** `gh` responses
      against `ecorkran/squadron` — a fixture invented by hand proves nothing about
      a shape squadron does not control.
- [x] Capture: PR 83 resolution (GraphQL), `repos/ecorkran/squadron` (default
      branch), the 404 body for a nonexistent branch, `user` (identity), and
      `reviewThreads` both empty and populated.
- [x] Record the `gh` version the fixtures came from in a README beside them. The
      design's risk register names `gh` output drift as the live risk;
      `HostResponseMalformedError` is the runtime half, and this note is how a
      future reader knows when the fixtures went stale.
- [x] Effort: 2

### Task F.2 — `GitHubCli` construction and `serves_host`

- [x] Create `src/squadron/codehost/github_cli.py`.
      `GitHubCli(runner: ProcessRunner, hosts: frozenset[str])`.
- [x] `hosts` is built once by the CLI from `read_gh_hosts()` plus `github.com`.
      `serves_host` is a set-membership test — `github.com` is the one host
      recognized without a `hosts.yml` entry.
- [x] Module constants: `HOST_COMMAND_TIMEOUT_SECONDS = 30`,
      `MAX_DISCUSSION_PAGES = 10`. Values, not literals at call sites.
- [x] A private `_run_gh` helper is the **only** place `gh` is invoked. It appends
      `--hostname <host>`, sets env `GH_PROMPT_DISABLED=1`,
      `GH_NO_UPDATE_NOTIFIER=1`, `NO_COLOR=1`, and applies the timeout. A wedged
      prompt or an update banner in parsed output is what this prevents.
- [x] `build_github_host(runner)` factory — the one entry point the CLI uses.
- [x] Effort: 3

### Task F.3 — `_classify_failure`

- [x] One function every operation calls on a non-zero exit. **Structural signals
      only — never message-text matching.** Applied in this order:
  1. [ ] `returncode == 4` → `HostUnauthenticatedError(host)`, fix hint
         `gh auth login --hostname <host>`.
  2. [ ] stdout parses as JSON with a `status` field → `401` unauthenticated,
         `404` not-found (the caller turns it into the operation-specific error),
         anything else `HostRequestRejectedError(status, message)`.
  3. [ ] stdout parses as JSON with `errors` (GraphQL) → `NOT_FOUND` type as
         above; other types `HostRequestRejectedError`.
  4. [ ] otherwise → `HostUnreachableError` carrying `gh`'s **stderr verbatim**.
         This is the residual "ran but got no HTTP response" bucket; the verbatim
         stderr is what tells the operator the real cause, including for a
         squadron-side argv bug.
- [x] `ProcessNotFoundError` → `GitHubCliMissingError`; `ProcessTimedOutError` →
      `HostCommandTimeoutError(argv, seconds)`.
- [x] JSON that should parse and does not, or JSON missing a required field →
      `HostResponseMalformedError(argv, detail)`. This is how `gh` drift is
      reported instead of a `KeyError`.
- [x] Effort: 3

### Task F.4 — Read operations

- [x] `resolve_pull_request` **by number**: `gh api graphql -F owner -F name
      -F number -f query=<PR_QUERY>`. `PR_QUERY` is a module constant requesting
      `number url title body state author{login} baseRefName baseRefOid
      headRefName headRefOid isCrossRepository headRepository{nameWithOwner}
      closingIssuesReferences(first:20){nodes{number}}`.
- [x] `resolve_pull_request` **by branch**: `pullRequests(headRefName:$branch,
      states:OPEN, first:2)`. Zero nodes → `NoOpenPullRequestForBranchError`; two →
      `AmbiguousBranchPullRequestsError`. `first:2` is deliberate — it distinguishes
      one from many without paging.
- [x] `resolve_pull_request` under form 1 (current branch) reads the branch via
      `git rev-parse --abbrev-ref HEAD`; a detached HEAD is
      `TargetUnresolvableError` naming the state.
- [x] `default_branch`: `gh api repos/{owner}/{repo}` → `default_branch`.
- [x] `branch_exists`: `gh api repos/{owner}/{repo}/branches/{branch}` — 200 →
      `True`, 404 → `False`, everything else raises.
- [x] `identify_operator`: `gh api --hostname {host} user` → `login`; a response
      with no login is `OperatorUnidentifiedError`.
- [x] `list_unresolved_discussions`: GraphQL `reviewThreads(first:100,
      after:$cursor)` filtered to `isResolved == false`, paged until `hasNextPage`
      is false or `MAX_DISCUSSION_PAGES`. Hitting the cap **logs at WARNING with
      the truncated count** — a silently truncated list is a review that quietly
      misses comments.
- [x] `base_sha` on `ResolvedPullRequest` comes from `baseRefOid`. This is what
      makes Part G's post-fetch check exact rather than heuristic.
- [x] Split the GraphQL constants into `github_queries.py` if `github_cli.py`
      exceeds ~300 lines.
- [x] Effort: 4

### Task F.5 — Test: reads, argv pinning, and classification

- [x] `tests/codehost/test_github_cli.py` against the fake runner and F.1's
      fixtures.
- [x] **Pin the exact argv** for every operation. This is the contract 384 and 385
      build on, and the only defense against the `HostUnreachableError` residual
      bucket absorbing a squadron-side argv bug.
- [x] Assert **every** `gh` argv carries `--hostname` and the three env vars.
- [x] Parametrize every host-dependent case over `github.com` **and**
      `ghe.corp.example`, with a hosts-file fixture listing both. Assert the
      enterprise run's argv carries the enterprise hostname. GitHub Enterprise is a
      stated requirement; no live GHE is available, so this parametrization is the
      whole of the evidence.
- [x] Classification table, one case each: exit 4; REST 401; REST 404; REST 422;
      GraphQL `NOT_FOUND`; GraphQL other; no-JSON-no-HTTP → `HostUnreachableError`
      **with `gh`'s stderr present in the error**; `ProcessNotFoundError` →
      `GitHubCliMissingError`; `ProcessTimedOutError` → `HostCommandTimeoutError`
      naming the bound; malformed JSON and a missing required field →
      `HostResponseMalformedError`.
- [x] `branch_exists` returns `False` on 404 and **does not raise**; it raises on
      500.
- [x] Branch resolution: zero, one, and two open PRs.
- [x] Discussion paging: a populated page, an empty page, and a scripted run
      exceeding `MAX_DISCUSSION_PAGES` asserting the WARNING and the truncation.
- [x] Closed and merged PRs resolve, with `state` reported correctly.
- [x] Effort: 4

### Task F.6 — Commit

- [x] `uv run pytest tests/codehost -q`; ruff; pyright.
- [x] Commit: `feat(codehost): add GitHub host reads over gh with structural failure classification`
- [x] Effort: 1

---

## Part G — Fetch and Range

### Task G.1 — `fetch_and_range`

- [ ] Create `src/squadron/codehost/refs.py`. Host-agnostic git over the runner —
      the caller supplies the refspec sources.
- [ ] Signature: `fetch_and_range(runner, *, cwd, remote_name, namespace,
      base_refspec_source, head_refspec_source, expected_base_sha,
      expected_head_sha) -> FetchedRange`.
- [ ] Module constants `GIT_QUERY_TIMEOUT_SECONDS = 30`,
      `GIT_FETCH_TIMEOUT_SECONDS = 300`. Fetch moves data; the query bound is far
      too tight for it.
- [ ] Local refs: `refs/squadron/pr/<remote_name>/<number>/base` and `.../head`.
      Namespacing by remote keeps PR 12 on `origin` distinct from PR 12 on
      `upstream`.
- [ ] One `git fetch --no-tags <remote> +<base_source>:<base_local>
      +<head_source>:<head_local>`. The `+` force-updates on every resolution.
- [ ] Refs under `refs/squadron/` are **not branches** — `git branch`,
      `git status`, and the working tree stay untouched. No cleanup in this slice.
- [ ] A non-zero fetch exit is `RefNotFetchableError(role)`; determine the role by
      a follow-up `git rev-parse --verify` of each local ref so the message names
      the one actually missing rather than guessing.
- [ ] Verification: `git rev-parse` of each local ref must equal the sha the host
      reported at resolution. A mismatch is
      `RefMovedSinceResolutionError(role, expected, actual)` — the operator reruns.
- [ ] `git merge-base <base_local> <head_local>`; no merge-base (unrelated
      histories) is `NoMergeBaseError`.
- [ ] `diff_range` is `<base_local>...<head_local>` — the three-dot form the
      existing review path already accepts via `normalize_diff_spec`.
- [ ] `changed_paths` is `git diff --name-only <diff_range>` with **no exclusion
      patterns**; 382 applies the template's patterns through the existing scope
      assertion.
- [ ] Effort: 4

### Task G.2 — Wire `fetch_pull_request_refs`

- [ ] In `github_cli.py`, supply GitHub's refspec sources — `refs/heads/<base_ref>`
      and `refs/pull/<number>/head` — and delegate to `refs.fetch_and_range`.
- [ ] `refs/pull/<n>/head` is fetchable for merged and cross-repository PRs alike
      (confirmed on PRs 64, 66, 83), so a fork head needs **no second remote**.
- [ ] Effort: 2

### Task G.3 — Test: fetch, verification, and the no-mutation guarantee

- [ ] `tests/codehost/test_refs.py` against the fake runner.
- [ ] Happy path: both refs resolve, `merge_base` is a 40-hex sha, `diff_range` is
      the three-dot form, `changed_paths` parses.
- [ ] **The no-mutation assertion**: the recorded argv contains no `checkout`,
      `switch`, `reset`, `branch`, or `worktree` invocation. This is the guarantee
      that lets `sq pr show` run against a dirty working tree.
- [ ] Assert the fetch carries `--no-tags` and both `+`-prefixed refspecs, and that
      the fetch call uses `GIT_FETCH_TIMEOUT_SECONDS` while the queries use
      `GIT_QUERY_TIMEOUT_SECONDS`.
- [ ] Failure cases, each asserting type, structured fields, and log level:
      fetch fails for base only; for head only; a moved base
      (`RefMovedSinceResolutionError(BASE, ...)`); a moved head; unrelated
      histories (`NoMergeBaseError`).
- [ ] Cross-repository: the head fetches from `refs/pull/<n>/head` with only one
      remote configured.
- [ ] **No enterprise-hostname leg here, deliberately.** The design's GHE bullet
      lists "fetch refspecs" among the paths to parametrize over both hosts, but the
      fetch path is host-independent by construction: `refs.py` takes refspec sources
      from its caller and names the *remote*, never the host, so no git argv on this
      path carries a hostname. Parsing and selection are parametrized in D.3,
      resolution and identity in F.5. Record this rather than adding a vacuous leg,
      so the I.2 sweep has a definite answer instead of an apparent gap.
- [ ] (The doctor-module subprocess invariant test lives with the doctor checks in
      Part E, not here — it guards Part E's work and belongs in its test task.)
- [ ] Effort: 3

### Task G.4 — Commit

- [ ] `uv run pytest tests/codehost tests/cli -q`; ruff; pyright.
- [ ] Commit: `feat(codehost): fetch PR refs into namespaced refs with merge-base range`
- [ ] Effort: 1

---

## Part H — Writes, CLI, and Registration

### Task H.1 — Write operations

- [ ] Implemented and tested here so 384 and 385 add behavior rather than
      transport. **No 381 command calls them.**
- [ ] `find_own_comment`: `gh api --paginate repos/{owner}/{repo}/issues/{n}/comments`,
      filtered to `user.login == operator` **and** the marker in the body; earliest
      by `created_at`. The marker's format is 384's to define — take it as a
      parameter, do not invent one.
- [ ] `post_comment`: `gh api -X POST repos/{owner}/{repo}/issues/{n}/comments
      -f body=@-`.
- [ ] `update_comment`: `gh api -X PATCH repos/{owner}/{repo}/issues/comments/{id}
      -f body=@-`.
- [ ] `open_pull_request`: `gh api -X POST repos/{owner}/{repo}/pulls -f title
      -f head -f base -f body=@-`; 422 → `PullRequestCreationRejectedError`
      carrying the host's message.
- [ ] **Every body goes over stdin** (`-f body=@-`), never through argv. A review
      body of any size or content cannot then hit the argument-length limit or be
      mangled by shell-adjacent handling. This is what the runner's `stdin`
      parameter exists for.
- [ ] Effort: 3

### Task H.2 — Test: writes and `write_calls()`

- [ ] Pin the exact argv for all four operations.
- [ ] Assert the body arrives **over stdin**, byte-for-byte, including a body with
      newlines, quotes, backticks, and a leading `-`. Assert the body does **not**
      appear anywhere in argv.
- [ ] Assert `write_calls()` captures each of the four.
- [ ] Assert it stays **empty across a full scripted adapter pipeline** — parse
      target, select remote, resolve, fetch and range — which is everything the
      read path does and is all that exists at this point in the sequence. The
      CLI-level counterpart runs in the `sq pr show` test task, once the command
      exists. Together they are 381's proof the slice is read-only, and the
      mechanism 384 reuses; neither half may be dropped.
- [ ] `find_own_comment`: no match → `None`; several matches → earliest by
      `created_at`; a comment by another author with the marker is **not** matched.
- [ ] Effort: 3

### Task H.3 — `sq pr show`

- [ ] Create `src/squadron/cli/commands/pr.py`.
      `pr_app = typer.Typer(name="pr", help=..., no_args_is_help=True)`; 385 adds
      `create` here.
- [ ] `sq pr show [TARGET] [--cwd PATH] [--json]`.
- [ ] `--cwd` resolves through the **shared cwd helper** extracted in Part A.
- [ ] Terminal output: one Rich panel with the record (host, owner/repository,
      number, state, title, author, URL, base ref and sha, head ref and sha,
      cross-repository flag), then the fetched refs with shas, the merge-base, the
      diff range, and the changed paths.
- [ ] `--json`: one object with `record`, `resolved` (title, body, state, author,
      base_sha, linked_issue_numbers), and `fetched` (the `FetchedRange` fields).
      Follow `doctor.py`'s `_render_json` shape
      ([doctor.py:90](src/squadron/cli/commands/doctor.py#L90)). Written for 386's
      parity test.
- [ ] Any `CodeHostError` → message and fix hint on stderr in red, exit 1, as the
      review commands do. Exit 0 on success.
- [ ] **Notify `sq-base` before editing `app.py`.** Then add the import and
      `app.add_typer(pr_app, name="pr")` alongside
      [app.py:49-56](src/squadron/cli/app.py#L49-L56).
- [ ] Effort: 3

### Task H.4 — Test: `sq pr show` behavior

- [ ] `tests/cli/test_pr_show.py`, using the `cli_runner` fixture
      ([tests/cli/conftest.py:14](tests/cli/conftest.py#L14)).
- [ ] **The injection seam — name it, do not invent one at execution time.**
      `pr.py` reaches the host through `build_github_host(runner)` (F.2), so that
      factory is the single patch point: monkeypatch it in a module-scoped fixture to
      return `GitHubCli(FakeProcessRunner(script), hosts)`. Do not patch
      `SubprocessRunner`, and do not thread a test-only parameter through the command
      signature. Every other mechanism in this slice is pinned to the call; this one
      is the mechanism the headline criterion depends on, so it is pinned here too.
- [ ] The enterprise leg needs the CLI's own `read_gh_hosts()` to see both hosts:
      set `GH_CONFIG_DIR` to a two-host `hosts.yml` fixture, as the doctor test task
      already does — not by passing `hosts` past the factory, which would bypass the
      path under test.
- [ ] **All six target forms resolve to the same `PullRequestRecord`** for the same
      PR — one parametrized test with identical scripted host responses, run once
      on `github.com` and once on the enterprise hostname. This is the slice's
      headline functional criterion.
- [ ] `--json` emits the three-key object and parses.
- [ ] The **CLI-level `write_calls()` assertion**: empty across a full `sq pr show`
      run. This is the half deferred from the write-operations test task, which
      could only script the adapter pipeline; together the two are the slice's
      read-only proof. Neither may be dropped.
- [ ] Effort: 2

### Task H.5 — Test: error observability and import boundaries

- [ ] Every error in the design's error table — **all nineteen classes** — reaches
      exit 1 through `sq pr show`, with a WARNING-or-higher record (`caplog`).
      Table-driven; one row per class, and the count is the check.
- [ ] This is the design's `test_errors_observable.py`. **Placement deviation,
      deliberate:** it lives in `tests/cli/test_pr_show.py` rather than its own file
      under `tests/codehost/`, because exit codes are only observable through the
      CLI and the design's own criterion couples type, log level, and exit code in
      one assertion. If it outgrows that home, split it out then.
- [ ] `tests/codehost/test_import_boundaries.py`: walk the import graph of
      `src/squadron/codehost` and `src/squadron/review`. Assert no `codehost`
      module imports `squadron.review`, `squadron.cli`, `squadron.pipeline`, or
      `squadron.providers`, and no `review` module imports `squadron.codehost`.
- [ ] Separated from the task above because this is the densest test work in the
      slice — nineteen error classes times three assertions each, plus a two-package
      graph walk. Buried in a four-deliverable task it is the part most likely to
      be left half-done.
- [ ] Effort: 3

### Task H.6 — Commit

- [ ] `uv run pytest -q`. **Full suite** — this is the first point where the new
      command is registered and could affect unrelated CLI tests.
- [ ] ruff; pyright.
- [ ] Commit: `feat(cli): add sq pr show over the code-host adapter`
- [ ] Effort: 1

---

## Part I — Live Evidence and Closeout

### Task I.1 — Live verification walkthrough

- [ ] Run in a clone of `ecorkran/squadron` with `gh` authenticated. PR 83 is
      merged and cross-repository, which exercises the fork-head fetch.
- [ ] `sq doctor -v` → two rows under Integrations with real paths. Then
      `PATH=/usr/bin sq doctor -v` → `github cli` WARN with the install hint,
      **exit 0** (not required).
- [ ] Record the working state:
      ```bash
      git for-each-ref refs/heads > /tmp/before.refs
      git status --porcelain > /tmp/before.status
      ```
- [ ] Run every target form:
      ```bash
      sq pr show 83
      sq pr show https://github.com/ecorkran/squadron/pull/83
      sq pr show ecorkran/squadron#83
      sq pr show squadron#83
      sq pr show codex/issue-82-diff-review-context
      ```
      The first four print the same record (number 83, base `main`, head sha
      `b67cf55…`, cross-repository true, state MERGED), both namespaced refs, the
      merge-base, the range, and the changed paths.
- [ ] The **branch form resolves only while an open PR has that head**. On this
      merged PR it reports `NoOpenPullRequestForBranchError` — that is the expected
      output for that step, not a failure.
- [ ] Absent target: on a branch with an open PR, the same shape; on `squadron-pr`
      with no PR, exit 1 naming the branch.
- [ ] Confirm nothing moved:
      ```bash
      git for-each-ref refs/heads | diff - /tmp/before.refs
      git status --porcelain | diff - /tmp/before.status
      git for-each-ref refs/squadron/
      ```
      The diffs print nothing; the last lists the two namespaced refs.
- [ ] Live failure modes, each exit 1 with a named message:
      ```bash
      sq pr show 999999                       # PullRequestNotFoundError
      sq pr show someone-else/other-repo#1    # ForeignRepositoryError
      GH_CONFIG_DIR=/tmp/empty sq pr show 83  # HostUnauthenticatedError
      ```
- [ ] `sq pr show 83 --json | python -m json.tool` prints the three-key object.
- [ ] Effort: 2

### Task I.2 — Success criteria sweep

- [ ] Walk the design's Functional criteria and confirm each is demonstrated by a
      test or by I.1's recorded run:
  - [ ] six forms → one record, on both `github.com` and an enterprise hostname
  - [ ] fork layout: explicit resolves, bare raises naming both remotes; one
        GitHub remote + non-GitHub mirror resolves bare
  - [ ] foreign repository named on both sides
  - [ ] both refs exist, merge-base is 40-hex, three-dot range, **no mutating git
        verb** in recorded argv, and `for-each-ref`/`status` unchanged live
  - [ ] every error: type, WARNING+ record, exit 1; scripted timeout names the bound
  - [ ] closed and merged PRs resolve; cross-repository fetches without a second remote
  - [ ] two doctor rows; `gh` absent reports and does not install
- [ ] **Package-root re-exports**: every name in the design's Integration Points →
      Provides list imports from `squadron.codehost` directly, not by deep path.
      This is the contract 382, 384, and 385 consume; an empty or partial
      `__init__.py` breaks them into deep-path imports and the divergence would
      otherwise surface only at 382 integration.
- [ ] Technical criteria: ruff clean, **pyright zero errors**, the import-graph test
      passes, every emitted `gh` argv is pinned, every parsed JSON shape has a
      fixture captured from a real response, files near 300 lines.
- [ ] Effort: 2

### Task I.3 — Documentation and closeout

- [ ] DEVLOG entry per `prompt.ai-project.system.md`, "Session State Summary",
      including the step-3 and step-5 output from I.1 (the design requires one run
      recorded).
- [ ] CHANGELOG: a short user-facing line for `sq pr show` and one for the two new
      doctor rows. Technical detail belongs in the DEVLOG, not here.
- [ ] Record the protocol addition (`serves_host`) and the `repo#n` grammar form in
      [380-arch.pull-request-workflow.md](project-documents/user/architecture/380-arch.pull-request-workflow.md)
      under Design Goals — **verify both are already present** from commit
      `79986dea` rather than adding them twice.
- [ ] Note in the DEVLOG that no live GitHub Enterprise host was available; the GHE
      evidence is the parametrized test suite, and a recorded GHE run closes the gap
      when one is.
- [ ] Mark this task file `status: complete`, set `dateUpdated`, and mark the slice
      complete in
      [381-slice.code-host-adapter-and-pr-target-resolution.md](project-documents/user/slices/381-slice.code-host-adapter-and-pr-target-resolution.md)
      and in the slice plan
      [380-slices.pull-request-workflow.md](project-documents/user/architecture/380-slices.pull-request-workflow.md).
- [ ] Confirm [issue #95](https://github.com/ecorkran/squadron/issues/95) (two-token
      target form) remains open — deliberately not addressed here.
- [ ] Merge the slice branch into `squadron-pr` (the configured
      `git.integration_branch`). **Never to `main`.**
- [ ] Effort: 2

---

## Task Review Disposition (part 2)

Task review (`381-review.tasks.code-host-adapter-and-pr-target-resolution.part-2.md`,
z-ai/glm-5.3-flash, CONCERNS, 20260913, sha `ea0fca58`, 34 tool calls) — the
companion to the part-1 disposition in file 1, reviewing this file against the
post-disposition state. Two concerns and one note actioned.

- **F007 (concern) — accepted, the substantive one.** H.4 and H.5 require
  `sq pr show` to run against the fake runner through `cli_runner`, and H.4 requires
  the two-host enterprise leg, but no task said how a CLI-level test routes the
  command onto the fake or how the CLI's `read_gh_hosts()` sees the fixture. Verified:
  the design names the construction pattern and F.2 supplies `build_github_host` as
  the entry point, but neither is connected to the CLI tests. This was the one
  mechanism left for the implementer to invent, and it is the one the slice's
  headline criterion rests on. H.4 now names the seam — monkeypatch
  `build_github_host` in a fixture — and names `GH_CONFIG_DIR` for the hosts fixture,
  with the two wrong ways to do it ruled out explicitly.
- **F008 (concern) — accepted.** Two design statements superseded at task breakdown
  were never synced back into the design: the seventh functional criterion still said
  the subprocess-invariant test was an "existing test extended", and the Testing
  listing still placed `test_errors_observable.py` under `tests/codehost/`. Verified
  both still read that way. This is the same procedural defect part-1's F007 raised
  about the cwd extraction — which *was* synced, leaving these two as the stragglers.
  Both design lines are amended and two rows added to the design's Scope corrections
  table, so a reader auditing tasks against design finds no stale text. No scope
  change: the task files already carried the corrected work.
- **F006 (note) — accepted.** The design's GHE bullet lists "fetch refspecs" among the
  paths to parametrize over both hosts, but G.3 had no enterprise leg. The review
  reasons the leg is vacuous; that is right — `refs.py` names the remote, never the
  host, so no git argv on the fetch path carries a hostname. G.3 now records why the
  path is host-independent rather than adding an empty parametrization, giving the
  I.2 sweep a definite answer instead of an apparent gap.
- **F005 (note) — acknowledged, no change.** F.5 is flagged as the densest remaining
  task and a candidate for the same split H.4/H.5 received. It is one cohesive
  subject with a table-driven structure specified; carried as an execution watch-item,
  to be split then if it balloons.
- **F004 (note)** — confirms no load/performance NFR exists to cover; no action.
- **F001–F003 (pass)** — no action.
