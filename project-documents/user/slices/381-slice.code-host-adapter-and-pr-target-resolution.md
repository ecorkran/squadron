---
docType: slice-design
slice: code-host-adapter-and-pr-target-resolution
project: squadron
parent: user/architecture/380-slices.pull-request-workflow.md
dependencies: [905]
interfaces: [382, 384, 385]
dateCreated: 20260912
dateUpdated: 20260913
status: not_started
---

# Slice Design: Code-Host Adapter and PR Target Resolution

## Overview

Squadron has no notion of a pull request and nothing under `src/squadron` calls `gh`. This slice
adds the one boundary the whole 380 initiative stands on: a code-host adapter protocol with the
operation list the architecture fixes, a GitHub implementation over the operator's `gh`, a typed
PR record, the target grammar, base-and-head fetch into namespaced local refs with the merge-base
range computed between them, the enumerated failure modes, and two presence checks in `sq doctor`.
It is read-only against the host. Its proving consumer is `sq pr show <target>`, a read-only
command that answers "what would be reviewed" before any model runs.

Two facts checked on a real host during design shape the detail below. `gh api` failures carry a
structured signal (`status` in the JSON body for REST, `errors[].type` for GraphQL, exit code 4 for
"authentication required" per `gh help exit-codes`), so failure classification never matches on
message text. And `refs/pull/<n>/head` is fetchable on `ecorkran/squadron` for merged and
cross-repository PRs alike (PRs 64, 66, 83 confirmed with `git ls-remote`), so a fork head needs no
second remote.

## Value

Architectural enablement. 382, 384, and 385 each consume this boundary and none of them touches
`gh` directly; the failure modes and the process seam are implemented and tested once. Operator
value from `sq pr show`: the resolved PR, the refs squadron fetched, the merge-base, and the
changed-file list a review would examine, without a model in the loop.

## Technical Scope

### Included

- `src/squadron/core/process_runner.py`: the injected process-runner seam with a timeout on every
  call, its real implementation, and the two errors a runner raises.
- `src/squadron/codehost/`: a new package beside `review/`. Protocol, typed records, target grammar,
  remote enumeration, ref fetching and range computation, the GitHub implementation, and the
  error hierarchy.
- `src/squadron/cli/commands/pr.py`: the `sq pr` Typer group with one command, `show`.
- `src/squadron/cli/commands/doctor_checks.py`: two presence checks (`gh` on PATH, `gh` hosts file
  readable) within 905's pure-check contract.
- Registration of `pr_app` in `src/squadron/cli/app.py`.
- Unit tests against a fake runner for every operation and every failure mode; doctor tests; one
  recorded live `sq pr show` run.

### Excluded

- Any host write invoked by a command. The protocol's write operations (post comment, update
  comment, open PR) are implemented and tested against the fake runner here so 384 and 385 add
  behavior rather than transport, but no 381 command calls them.
- Scratch worktrees, PR metadata in prompts, review persistence, posting, PR creation (382-385).
- The direct-API implementation and non-GitHub hosts (future work; the protocol is shaped for them).
- Any change under `src/squadron/review/` **beyond the cwd-helper extraction recorded in Scope
  corrections below**. The review package imports nothing from `codehost` in this slice; 382
  imports the record type only.
- Cross-repository targets (a PR in a repository none of the local remotes point at).

## Scope corrections against the plan entry

| Plan text | Finding at design | Disposition |
|---|---|---|
| "exactly the operation list the parent fixes" | Bare-form resolution needs to know which remotes belong to the host an implementation serves (a fork layout with a GitLab mirror must still count one GitHub remote). That is a question to the implementation, not a git question. | The protocol gains one local, read-only operation, `serves_host(hostname)`. The parent permits additions to the protocol; it forbids extra methods on the `gh` implementation. Recorded in the parent under Design Goals, alongside the `repo#n` grammar form. |
| "base moved since resolution" as a failure mode | `gh` exposes `baseRefOid`, so the base tip at resolution time is known and the post-fetch check is exact, not heuristic. The same check applies to the head. | One error class with a role field (base or head). |
| "check a branch exists on the host" | A missing branch is an answer, not a failure. | Returns `False`; only transport and auth failures raise. |
| "Nothing under `src/squadron/review/` changes" (Excluded, Coordination) | Found at task breakdown, not at design: `sq pr show --cwd` must anchor at the git root exactly as `sq review code` does, but that logic is `_resolve_review_cwd`, private to `review.py`, and it also resolves a rules directory `pr show` has no use for. Duplicating it violates DRY; importing a private helper across command modules is worse. | PM decision 20260913: extract the cwd half into a shared CLI helper; `_resolve_review_cwd` becomes a thin wrapper with an unchanged signature and all five call sites untouched. Behavior-preserving, committed on its own, and announced to `sq-base` as a second coordinated edit. |
| "`run_all_checks` still makes no subprocess call (**existing test extended**)" (Success Criteria → Functional) | Found at task breakdown: no such test exists — `grep subprocess tests/cli/test_doctor_checks.py` returns nothing. The invariant is also narrower than stated: `run_all_checks` calls `shutil.which` freely, and `git_hooks_path` is resolved by the caller precisely because a subprocess would violate the module's contract. | The criterion is amended to say the test is **written** by this slice, and to state the invariant as it actually holds. The doctor test task in Part E writes it. |
| "`test_errors_observable.py`" under `tests/codehost/` (Testing) | Found at task breakdown: exit codes are observable only through the CLI, and the design's own criterion couples type, log level, and exit code in a single assertion — which a test under `tests/codehost/` cannot make. | Placement deviation, deliberate: the table-driven type/log/exit test lives in `tests/cli/test_pr_show.py`. The Testing listing is amended. If it outgrows that home, split it out then. |

Effort stays 4/5.

## Dependencies

### Prerequisites

- Slice 905: `CheckResult`, `CheckStatus`, `run_all_checks` and the pure-check contract in
  `doctor_checks.py`.
- Initiative 100: Typer command registration in `cli/app.py`; `_resolve_cwd` and `find_git_root`
  as used by `_resolve_review_cwd` (the CLI layer already imports both).
- `gh` 2.x on the operator machine for the live run only. Unit tests need no `gh`.
- `pyyaml` (already a dependency) for reading the top-level keys of `gh`'s hosts file.

### Coordination

Session `sq-base` (slice 917) asked to be told before the CLI command registry or anything under
`src/squadron/review/` is touched. This slice makes two such edits, each announced to that
session before it is made:

1. `cli/app.py` — import and `add_typer` for `pr_app`.
2. `review.py` — extracting the cwd half of `_resolve_review_cwd` into a shared CLI helper, so
   `sq pr show --cwd` can anchor at the git root without duplicating the logic or importing a
   private helper across command modules. Behavior-preserving, with the existing review suite as
   the check; `_resolve_review_cwd` keeps its signature and all five call sites are untouched.
   Added by PM decision 20260913 — see Scope corrections.

## Architecture

### Component Structure

```
src/squadron/core/process_runner.py      ProcessRunner protocol, SubprocessRunner, ProcessResult,
                                          ProcessNotFoundError, ProcessTimedOutError
src/squadron/codehost/
  __init__.py                             re-exports the public types below
  models.py                               PullRequestRecord, ResolvedPullRequest, RepositoryLocator,
                                          LocalRemote, FetchedRange, ReviewDiscussion, HostComment,
                                          OperatorIdentity, RefRole
  errors.py                               CodeHostError hierarchy (one class per failure mode)
  protocol.py                             CodeHost protocol
  targets.py                              parse_target() → PullRequestTarget (grammar only)
  remotes.py                              list_remotes(), parse_remote_url(), select_remote()
  refs.py                                 fetch_and_range(): fetch refspecs, verify tips, merge-base,
                                          changed paths — host-agnostic git over the runner
  github_cli.py                           GitHubCli(CodeHost): every operation over `gh`
  github_config.py                        gh_hosts_file_path(), read_gh_hosts() — no subprocess
src/squadron/cli/commands/pr.py           pr_app; `show`
src/squadron/cli/commands/doctor_checks.py check_github_cli(), check_github_cli_hosts_file()
```

Dependency direction: `cli` → `codehost` → `core`. `codehost` never imports `review`, `cli`,
`pipeline`, or `providers`. `review` never imports `codehost` in this slice. A test asserts both
with an import-graph walk over `src/squadron/codehost` and `src/squadron/review`.

### Data Flow: `sq pr show <target>`

```
target string ──parse_target──▶ PullRequestTarget(form, ...)
                                        │
cwd ──list_remotes──▶ [LocalRemote] ────┤ select_remote(target, remotes, host.serves_host)
                                        ▼
                               RepositoryLocator(host, owner, repository, remote_name)
                                        │
                        host.resolve_pull_request(locator, target)      ← gh api graphql
                                        ▼
                               ResolvedPullRequest(record, title, body, state, author_login,
                                                   base_sha, is_cross_repository, linked_issues)
                                        │
            host.fetch_pull_request_refs(record, cwd) → refs.fetch_and_range(...)   ← git fetch,
                                        ▼                                              rev-parse,
                               FetchedRange(base_ref, head_ref, base_sha, head_sha,    merge-base,
                                            merge_base, diff_range, changed_paths)     diff --name-only
                                        │
                              render (table or --json), exit 0
```

Every arrow that runs a process goes through the one injected `ProcessRunner`. The CLI constructs
`SubprocessRunner()` and `GitHubCli(runner)`; tests construct `GitHubCli(FakeProcessRunner(...))`.

## Technical Decisions

### Process-runner seam

```python
@dataclass(frozen=True)
class ProcessResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

class ProcessRunner(Protocol):
    def run(self, argv: Sequence[str], *, cwd: str | None, timeout: float,
            env: Mapping[str, str] | None = None, stdin: str | None = None) -> ProcessResult: ...
```

`stdin` is how write operations pass a comment or PR body (see the GitHub implementation); the
fake runner records it alongside the argv so a test can assert the exact body sent.

- `SubprocessRunner.run` wraps `subprocess.run(capture_output=True, text=True, **TEXT_DECODING,
  check=False, timeout=timeout)`. `FileNotFoundError` becomes `ProcessNotFoundError(executable)`;
  `subprocess.TimeoutExpired` becomes `ProcessTimedOutError(argv, timeout)`. Both are logged at
  WARNING by the runner with the argv and, for the timeout, the bound. Unlike `review.git_utils.run_git`,
  which returns `None` for both, the two are distinct types because the architecture names
  "host call exceeded its timeout" as its own failure mode.
- `env` is merged over `os.environ` by the runner. `codehost` passes `GH_PROMPT_DISABLED=1`,
  `GH_NO_UPDATE_NOTIFIER=1`, and `NO_COLOR=1` on every `gh` call so a wedged prompt or an update
  banner can never appear in parsed output.
- Timeouts live in `codehost/github_cli.py` and `codehost/refs.py` as module constants:
  `HOST_COMMAND_TIMEOUT_SECONDS = 30` (every `gh` call), `GIT_QUERY_TIMEOUT_SECONDS = 30` (rev-parse,
  merge-base, diff, remote listing), `GIT_FETCH_TIMEOUT_SECONDS = 300` (fetch only, which moves
  data). The 30-second value matches `review.git_utils.GIT_COMMAND_TIMEOUT_SECONDS`; it is not
  imported from there because that would be the reverse import the architecture forbids.
- The fake runner (`tests/codehost/fake_runner.py`) is scripted as an ordered list of
  `(argv_prefix, ProcessResult | Exception)` entries. It records every call; an unscripted argv
  raises immediately so a test never passes on an unexpected process; a scripted
  `ProcessTimedOutError` is how "wedged `gh`" is produced. It also exposes `write_calls()`, the
  subset of recorded argv that would mutate the host (`-X POST`, `-X PATCH`, `pr create`), so
  384's "zero writes without `--post`" assertion is one call.

### Typed records (`codehost/models.py`)

All frozen dataclasses. Field names are the architecture's.

- `PullRequestRecord(host, owner, repository, number, base_ref, head_ref, head_sha, url)`. The
  identity every downstream consumer keys on. `key` property returns
  `f"{host}/{owner}/{repository}#{number}"` for logs and, in 383, the filename prefix.
- `ResolvedPullRequest(record, title, body, state, author_login, base_sha, is_cross_repository,
  head_repository, linked_issue_numbers)`. `state` is an enum `PullRequestState {OPEN, CLOSED,
  MERGED}`. `base_sha` is the base tip the host reported at resolution and is what the post-fetch
  check compares against. Everything 382 needs for the metadata block except unresolved
  discussions, which are a separate operation because they page.
- `RepositoryLocator(host, owner, repository, remote_name)`: the outcome of remote selection; the
  remote name is what fetch uses.
- `LocalRemote(name, host, owner, repository, url)`: one parsed `git remote`.
- `FetchedRange(base_ref, head_ref, base_sha, head_sha, merge_base, diff_range, changed_paths)`.
  `diff_range` is `f"{base_ref}...{head_ref}"`, the three-dot form the existing review path
  already accepts unchanged from `normalize_diff_spec`.
- `ReviewDiscussion(path, line, author_login, body, url)` for an unresolved review thread's first
  comment; `HostComment(id, author_login, body, url)` for an issue comment; `OperatorIdentity(host,
  login)`.
- `RefRole {BASE, HEAD}` for the fetch-verification error.

### Adapter protocol (`codehost/protocol.py`)

```python
class CodeHost(Protocol):
    def serves_host(self, hostname: str) -> bool: ...
    def resolve_pull_request(self, locator: RepositoryLocator, target: PullRequestTarget) -> ResolvedPullRequest: ...
    def default_branch(self, locator: RepositoryLocator) -> str: ...
    def branch_exists(self, locator: RepositoryLocator, branch: str) -> bool: ...
    def fetch_pull_request_refs(self, record: PullRequestRecord, *, remote_name: str, cwd: str) -> FetchedRange: ...
    def list_unresolved_discussions(self, record: PullRequestRecord) -> list[ReviewDiscussion]: ...
    def find_own_comment(self, record: PullRequestRecord, *, marker: str) -> HostComment | None: ...
    def update_comment(self, record: PullRequestRecord, comment_id: str, body: str) -> HostComment: ...
    def post_comment(self, record: PullRequestRecord, body: str) -> HostComment: ...
    def open_pull_request(self, locator: RepositoryLocator, *, base: str, head: str, title: str, body: str) -> PullRequestRecord: ...
    def identify_operator(self, hostname: str) -> OperatorIdentity: ...
```

The base branch is a field of the record (`base_ref`), which is how "report its base" is
satisfied; `default_branch` is the separate host-level query. `find_own_comment` takes the marker
string and matches it against comments authored by `identify_operator`'s login; the marker's format
is 384's to define. `fetch_pull_request_refs` is on the protocol because the refspec is the host's
convention (`refs/pull/<n>/head` on GitHub, `refs/merge-requests/<n>/head` on GitLab); the
implementation supplies the refspecs and delegates the git work to `refs.fetch_and_range`.

### Target grammar (`codehost/targets.py`)

`parse_target(text: str | None) -> PullRequestTarget` with `form: TargetForm` and the fields that
form carries. Classification order, each rule exclusive of the ones after it:

| Order | Form | Rule | Carries |
|---|---|---|---|
| 1 | `CURRENT_BRANCH` | `text` is `None` or empty | nothing; branch read from `git rev-parse --abbrev-ref HEAD` at resolution |
| 2 | `URL` | has a scheme (`https://`, `http://`) and a path matching `/{owner}/{repo}/pull/{n}` | host, owner, repository, number |
| 3 | `OWNER_REPO_NUMBER` | exactly one `/` before a `#`, digits after it, no whitespace | owner, repository, number |
| 4 | `REPO_NUMBER` | no `/`, a `#`, digits after it, a non-empty name before it | repository, number |
| 5 | `NUMBER` | all digits, or `#` followed by digits | number |
| 6 | `BRANCH` | anything else that `git check-ref-format --branch` accepts | branch name |

A detached HEAD under form 1 is `TargetUnresolvableError` naming the state. A string that fails
rule 6 is `TargetSyntaxError`. Trailing `.git`, a trailing slash, and a `?`/`#` fragment on a URL
are tolerated. The grammar lives here and nowhere else; `pr.py` passes the raw string through.

Form 4 (`squadron#7`) is the human form: the operator knows the repository name and should not
have to type the owner, which the remotes already know. The two-token form `squadron 7` is
deferred as issue #95: a second positional argument makes a branch name followed by a number
ambiguous, and the grammar should see real use before it grows.

### Remote enumeration and selection (`codehost/remotes.py`)

- `list_remotes(runner, cwd)` runs `git remote` then `git remote get-url <name>` per remote, and
  parses each URL with `parse_remote_url`: `https://host/owner/repo(.git)`, `ssh://git@host/owner/repo`,
  and the scp-like `git@host:owner/repo(.git)`. A URL that parses to none of these yields a
  `LocalRemote` with `host=None` and is never a candidate; it is listed by name in ambiguity
  messages so the operator sees why it was skipped.
- `select_remote(target, remotes, serves_host) -> RepositoryLocator`:
  - Explicit forms (URL, `owner/repo#n`): candidates are remotes whose owner and repository match
    case-insensitively, and whose host matches when the form names one. No candidate is
    `ForeignRepositoryError` naming the target's repository and every remote's repository.
    Several candidates (two remote names for one repository) take the first in `git remote`
    order and log the choice at INFO.
  - Repository-name form (`repo#n`): candidates are remotes where `serves_host(host)` is true and
    the repository name matches case-insensitively, owner ignored. Zero is
    `ForeignRepositoryError`; more than one owner for that name (fork plus upstream) is
    `AmbiguousHostRemoteError` listing `owner/repo` for each, with the `owner/repo#n` form as the
    remedy.
  - Bare forms (number, branch, current branch): candidates are remotes where
    `serves_host(host)` is true. Exactly one is required. Zero is `NoHostRemoteError`; more than
    one is `AmbiguousHostRemoteError` listing the names, which is the fork-with-`upstream` case
    the plan calls out. The message tells the operator to use the `owner/repo#n` form.

### GitHub implementation (`codehost/github_cli.py`)

`GitHubCli(runner: ProcessRunner, hosts: frozenset[str])` where `hosts` is built once by the CLI
from `read_gh_hosts()` (top-level keys of `hosts.yml`) plus `github.com`. `serves_host` is a set
membership test. Every command carries `--hostname <host>` (for `gh api`) so `gh` never guesses
from the current directory's remotes, which the operator may have configured differently.

**GitHub Enterprise.** A stated requirement: enterprise hosts (GHE Server on a private
hostname, GHE Cloud with data residency on `*.ghe.com`) must work, and more work there follows.
Nothing in this slice assumes `github.com`:

- The operator runs `gh auth login --hostname ghe.corp.example`; `gh` records the host in
  `hosts.yml`, and that key is what makes a remote at that host a GitHub remote for
  `serves_host`. `github.com` is the one host recognized without an entry.
- The host on every record, locator, and `gh api --hostname` call comes from the matched remote's
  URL (or from the URL form of the target), never from a default or from `GH_HOST`.
- The GraphQL and REST endpoints used are identical across `github.com` and GHE; `gh api`
  routes them per host.
- Unit tests parametrize every host-dependent case (remote parsing, selection, resolution,
  identity, fetch refspecs) over `github.com` and `ghe.corp.example`, with a hosts-file fixture
  listing both. No live GHE is available at design time; that gap is stated here and closed by
  a recorded run when one is.

| Operation | `gh` invocation | Classification source |
|---|---|---|
| `resolve_pull_request` by number | `gh api graphql -F owner -F name -F number -f query=<PR_QUERY>` | `errors[].type == NOT_FOUND` → not found |
| `resolve_pull_request` by branch | `gh api graphql ... pullRequests(headRefName:$branch, states:OPEN, first:2)` | zero nodes → `NoOpenPullRequestForBranchError`; two → `AmbiguousBranchPullRequestsError` |
| `default_branch` | `gh api repos/{owner}/{repo}` → `default_branch` | `status` |
| `branch_exists` | `gh api repos/{owner}/{repo}/branches/{branch}` | 200 → True, 404 → False |
| `list_unresolved_discussions` | `gh api graphql` `reviewThreads(first:100, after:$cursor)` filtered `isResolved == false`, paged until `hasNextPage` is false or `MAX_DISCUSSION_PAGES = 10` (1000 threads; a PR past that is logged at WARNING with the count truncated) | GraphQL errors |
| `find_own_comment` | `gh api --paginate repos/{owner}/{repo}/issues/{n}/comments`, filter `user.login == operator` and marker in body; earliest by `created_at` | `status` |
| `post_comment` | `gh api -X POST repos/{owner}/{repo}/issues/{n}/comments -f body=@-` (body on stdin) | `status` |
| `update_comment` | `gh api -X PATCH repos/{owner}/{repo}/issues/comments/{id} -f body=@-` | `status` |
| `open_pull_request` | `gh api -X POST repos/{owner}/{repo}/pulls -f title -f head -f base -f body=@-` | `status` (422 → `PullRequestCreationRejectedError` with the host's message) |
| `identify_operator` | `gh api --hostname {host} user` → `login` | exit 4 → unauthenticated |

`PR_QUERY` requests `number url title body state author{login} baseRefName baseRefOid headRefName
headRefOid isCrossRepository headRepository{nameWithOwner} closingIssuesReferences(first:20){nodes{number}}`.
The query strings are module constants; a test renders each against the fake runner and pins the
exact argv, which is the contract 384 and 385 rely on.

Body text for writes goes over stdin (`-f body=@-`), never through argv, so a review body of any
size or content cannot hit the argument-length limit or be mangled by shell-adjacent handling.
This is what the runner's `stdin` parameter exists for.

**Failure classification**, applied in one function `_classify_failure(result) -> CodeHostError`
that every operation calls on a non-zero exit:

1. `returncode == 4` → `HostUnauthenticatedError(host)`; the fix hint is `gh auth login --hostname <host>`.
2. stdout parses as JSON with a `status` field → by status: `401` unauthenticated, `404`
   `NotFoundError` (turned into the operation-specific error by the caller), anything else
   `HostRequestRejectedError(status, message)`.
3. stdout parses as JSON with `errors` (GraphQL) → `NOT_FOUND` type as above; other types
   `HostRequestRejectedError`.
4. otherwise → `HostUnreachableError` carrying `gh`'s stderr verbatim. This bucket is "gh ran
   and got no HTTP response", which is what a connection failure looks like; the stderr in the
   message is what tells the operator the real cause. A `ProcessNotFoundError` from the runner
   is `GitHubCliMissingError`; a `ProcessTimedOutError` is `HostCommandTimeoutError(argv, seconds)`.
5. stdout that should be JSON and is not, or JSON missing a required field →
   `HostResponseMalformedError(argv, detail)`. `gh` JSON shapes are observed, not guaranteed; this
   error is how drift is reported instead of a `KeyError`.

### Fetch and range (`codehost/refs.py`)

`fetch_and_range(runner, *, cwd, remote_name, namespace, base_refspec_source, head_refspec_source,
expected_base_sha, expected_head_sha) -> FetchedRange`.

- Local ref namespace: `refs/squadron/pr/<remote_name>/<number>/base` and `.../head`. Namespacing
  by remote name keeps PR 12 on `origin` distinct from PR 12 on `upstream`. Refs under
  `refs/squadron/` are not branches, so `git branch`, `git status`, and the working tree are
  untouched; the refs are overwritten on every resolution (`+` refspec) and left in place. They
  are listable with `git for-each-ref refs/squadron/`. No cleanup in this slice.
- One `git fetch --no-tags <remote> +<base_source>:<base_local> +<head_source>:<head_local>` bounded
  by `GIT_FETCH_TIMEOUT_SECONDS`. On GitHub `base_source` is `refs/heads/<base_ref>` and
  `head_source` is `refs/pull/<number>/head`. A non-zero exit is `RefNotFetchableError(role)`; the
  role is determined by a follow-up `git rev-parse --verify` of each local ref so the message names
  the one that is missing.
- Verification: `git rev-parse` of each local ref must equal the sha the host reported at
  resolution (`base_sha`, `head_sha`). A mismatch is `RefMovedSinceResolutionError(role, expected,
  actual)`: the operator reruns. This is the architecture's "base moved since resolution" mode
  made exact by `baseRefOid`.
- `git merge-base <base_local> <head_local>`; no merge-base (unrelated histories) is
  `NoMergeBaseError`. `diff_range` is `<base_local>...<head_local>`. `changed_paths` is
  `git diff --name-only <diff_range>` with no exclusion patterns; 382 applies the template's
  patterns through the existing scope assertion.

### Error hierarchy (`codehost/errors.py`)

`CodeHostError(Exception)` with `fix_hint: str | None`, then one subclass per mode. Every raise
site logs at WARNING or ERROR with the structured fields before raising; no error is logged
twice. The CLI maps any `CodeHostError` to exit code 1 after printing its message and hint.

| Error | Mode from the architecture | Log |
|---|---|---|
| `GitHubCliMissingError` | `gh` missing | WARNING |
| `HostUnauthenticatedError` | `gh` unauthenticated | WARNING |
| `HostUnreachableError` | host unreachable | WARNING |
| `HostCommandTimeoutError` | host call exceeded its timeout | WARNING |
| `PullRequestNotFoundError` | PR not found | WARNING |
| `NoOpenPullRequestForBranchError`, `AmbiguousBranchPullRequestsError` | PR not found (branch forms) | WARNING |
| `ForeignRepositoryError`, `NoHostRemoteError`, `AmbiguousHostRemoteError` | target refused | WARNING |
| `TargetSyntaxError`, `TargetUnresolvableError` | target refused | WARNING |
| `RefNotFetchableError` | head or base ref not fetchable | ERROR |
| `RefMovedSinceResolutionError` | base moved since resolution | WARNING |
| `NoMergeBaseError` | (new, discovered by design) | ERROR |
| `HostRequestRejectedError` | post rejected, creation rejected, other refusals | ERROR |
| `PullRequestCreationRejectedError` | creation rejected | ERROR |
| `HostResponseMalformedError` | (new) `gh` output drift | ERROR |
| `OperatorUnidentifiedError` | identify-operator returned no login | WARNING |

"Head branch not on the host" is `branch_exists` returning `False`; 385 turns that into its error.

### Doctor checks

Two new functions in `doctor_checks.py`, both `section=SECTION_INTEGRATIONS`, `required=False`
(a squadron install without PR workflows is complete), run from `run_all_checks` after the
existing CLI presence checks:

- `check_github_cli()`: `shutil.which("gh")`. OK with the path; WARN "not on PATH" with fix hint
  `GITHUB_CLI_INSTALL_HINT` (`brew install gh`, or `https://cli.github.com`).
- `check_github_cli_hosts_file()`: `gh_hosts_file_path()` from `codehost/github_config.py`
  (`$GH_CONFIG_DIR/hosts.yml` when set, else `~/.config/gh/hosts.yml`); OK when it exists and
  `os.access(path, os.R_OK)`; WARN "missing" with hint `gh auth login`; WARN "not readable" with
  the path. The file is not parsed by doctor.

No subprocess, no network, no auth verification: the adapter reports those at invocation as the
named errors above.

### `sq pr show`

```
sq pr show [TARGET] [--cwd PATH] [--json]
```

- `TARGET` is any grammar form or absent.
- `--cwd` resolves as `sq review code` does: configured `cwd`, then the git root above it.
- Terminal output: one Rich panel with the record (host, owner/repository, number, state, title,
  author, URL, base ref and sha, head ref and sha, cross-repository flag), then the fetched refs
  (both local ref names with shas), the merge-base, the diff range, and the changed paths.
- `--json` prints one object: `record`, `resolved` (title, body, state, author, base_sha,
  linked_issue_numbers), `fetched` (`FetchedRange` fields). Written for 386's parity test.
- Exit 0 on success; 1 on any `CodeHostError`, with the message and fix hint on stderr in red,
  as the review commands do.
- `pr_app = typer.Typer(name="pr", help=..., no_args_is_help=True)`; 385 adds `create` here.

## Integration Points

### Provides

- `codehost.CodeHost`, `GitHubCli`, `PullRequestRecord`, `ResolvedPullRequest`, `FetchedRange`,
  `ReviewDiscussion`, `HostComment`, `OperatorIdentity`, the error hierarchy, `parse_target`,
  `list_remotes`, `select_remote`, and `build_github_host(runner)` (the one factory the CLI uses).
- `core.ProcessRunner`, `SubprocessRunner`, and the test-side `FakeProcessRunner` with
  `write_calls()`.
- `pr_app` for 385 to extend.

### Consumed by

- 382: `resolve_pull_request`, `fetch_pull_request_refs`, `list_unresolved_discussions`, the
  record and resolved types; hands `FetchedRange.diff_range` and `head_ref` to the review path.
- 384: `identify_operator`, `find_own_comment`, `update_comment`, `post_comment`, and
  `FakeProcessRunner.write_calls()`.
- 385: `default_branch`, `branch_exists`, `open_pull_request`, `identify_operator`.

## Success Criteria

### Functional

- Each of the six target forms resolves to the same `PullRequestRecord` for the same PR, shown by
  one parametrized test over the fake runner with identical scripted host responses, run once
  with the remote on `github.com` and once on an enterprise hostname listed in the hosts-file
  fixture. The enterprise run's `gh api` argv carries that hostname.
- Fork layout (`origin` fork, `upstream` canonical, both GitHub): explicit forms resolve; bare forms
  raise `AmbiguousHostRemoteError` whose message contains both remote names. A layout with one
  GitHub remote and one non-GitHub mirror resolves bare forms.
- A target naming a repository no remote points at raises `ForeignRepositoryError` naming both.
- After `fetch_and_range`, both namespaced refs exist, `merge_base` is a 40-hex sha, `diff_range`
  is the three-dot form, and the recorded argv contains no `checkout`, `switch`, `reset`,
  `branch`, or `worktree` invocation. The live run shows `git for-each-ref refs/heads` and
  `git status --porcelain` unchanged before and after.
- Every error in the table has a fake-runner test asserting the type, the WARNING-or-higher log
  record (via `caplog`), and exit code 1 through `sq pr show`. A scripted timeout yields
  `HostCommandTimeoutError` naming the bound.
- Closed and merged PRs resolve and fetch; `state` is reported. Cross-repository PRs fetch from
  the base repository's `refs/pull/<n>/head` without a second remote.
- `sq doctor` shows the two new rows; with `gh` absent it reports and does not install;
  `run_all_checks` makes no subprocess call from the doctor-checks module (test written by this
  slice; no such test existed — see Scope corrections). `shutil.which` is permitted, and the
  git-hooks path is resolved by the caller.

### Technical

- `ruff format`, `ruff check`, and `pyright` clean; zero pyright errors.
- No module under `codehost/` imports `squadron.review`, `squadron.cli`, `squadron.pipeline`, or
  `squadron.providers`; no module under `review/` imports `squadron.codehost`. One test walks
  both import graphs.
- Every `gh` argv the implementation emits is pinned by a test, and every JSON shape it parses has
  a fixture captured from a real `gh` response on `ecorkran/squadron` (PR 83 for resolution,
  `repos/ecorkran/squadron` for default branch, the 404 body for branch-exists, `user` for
  identity, an empty and a populated `reviewThreads` page).
- Files stay near 300 lines; `github_cli.py` splits its GraphQL query constants into
  `github_queries.py` if it exceeds that.

### Verification Walkthrough

Run in a clone of `ecorkran/squadron` with `gh` authenticated. PR 83 is merged and
cross-repository, which exercises the fork-head fetch.

1. Doctor reports presence:

   ```
   sq doctor -v
   ```

   Two rows under Integrations: `github cli` with the `gh` path, `gh hosts file` with the path.
   Temporarily `PATH=/usr/bin sq doctor -v` shows `github cli` as WARN with the install hint and
   exits 0, since the check is not required.

2. Record the working state:

   ```
   git for-each-ref refs/heads > /tmp/before.refs && git status --porcelain > /tmp/before.status
   ```

3. Show a PR by number, then by each other form:

   ```
   sq pr show 83
   sq pr show https://github.com/ecorkran/squadron/pull/83
   sq pr show ecorkran/squadron#83
   sq pr show squadron#83
   sq pr show codex/issue-82-diff-review-context
   ```

   Each prints the same record (number 83, base `main`, head sha `b67cf55…`, cross-repository
   true, state MERGED), the two refs `refs/squadron/pr/origin/83/{base,head}`, the merge-base,
   the range, and the changed paths. The branch form resolves only while an open PR has that
   head; on this merged PR it reports `NoOpenPullRequestForBranchError`, which is the expected
   output for that step.

4. Absent target on a branch with an open PR prints the same shape; on `squadron-pr` with no PR it
   exits 1 with the no-open-PR message naming the branch.

5. Confirm nothing moved:

   ```
   git for-each-ref refs/heads | diff - /tmp/before.refs && git status --porcelain | diff - /tmp/before.status
   git for-each-ref refs/squadron/
   ```

   The first line prints nothing; the second lists the two namespaced refs.

6. Failure modes on a live host, each exiting 1 with a named message:

   ```
   sq pr show 999999                      # PullRequestNotFoundError
   sq pr show someone-else/other-repo#1   # ForeignRepositoryError listing origin's repository
   GH_CONFIG_DIR=/tmp/empty sq pr show 83  # HostUnauthenticatedError with the gh auth login hint
   ```

7. `sq pr show 83 --json | python -m json.tool` prints the three-key object.

The output of steps 3 and 5 for one run is recorded in the DEVLOG entry that closes this slice.

## Risk Assessment

- `gh` JSON and ref conventions are observed. Mitigation: fixtures captured from real responses,
  `HostResponseMalformedError` for drift, and a live run as evidence. Enterprise hosts are covered
  by reading `hosts.yml` and passing `--hostname`; none is available to test against, and that is
  stated rather than assumed.
- `HostUnreachableError` is the residual bucket for "no HTTP response". A squadron-side argv bug
  would land there at runtime. Mitigation: every argv is pinned by a test, and the error message
  carries `gh`'s stderr verbatim.

## Implementation Notes

### Order

1. `core/process_runner.py` and the fake runner with tests (the seam everything else is tested
   through).
2. `codehost/models.py`, `errors.py`, `protocol.py`.
3. `targets.py` and `remotes.py` with their tests (pure parsing and selection; no host).
4. `github_config.py` and the two doctor checks with tests.
5. `github_cli.py` read operations (`serves_host`, `resolve_pull_request`, `default_branch`,
   `branch_exists`, `identify_operator`, `list_unresolved_discussions`) with fixtures and
   classification tests.
6. `refs.py` with fetch, verification, merge-base, and the no-mutation argv assertion.
7. `github_cli.py` write operations (`find_own_comment`, `post_comment`, `update_comment`,
   `open_pull_request`) with argv pinning and `write_calls()` coverage.
8. `cli/commands/pr.py`, registration in `app.py` after notifying `sq-base`, CLI tests with
   `CliRunner`, the import-graph test.
9. Live run, DEVLOG entry, `CHANGELOG` line for `sq pr show` and the doctor rows, and the
   protocol-addition note in the architecture document.

### Testing

- `tests/codehost/`: `fake_runner.py`, `fixtures/gh/*.json`, `test_targets.py`, `test_remotes.py`,
  `test_github_cli.py`, `test_refs.py`, `test_import_boundaries.py`.
- The table-driven type/log/exit test (originally listed here as `test_errors_observable.py`)
  lives in `tests/cli/test_pr_show.py` instead: exit codes are observable only through the CLI,
  and this criterion couples type, log level, and exit code in one assertion. See Scope
  corrections.
- `tests/core/test_process_runner.py`: the real runner against `python -c` for success, missing
  executable, and a sleep that exceeds a short timeout.
- `tests/cli/test_pr_show.py` and additions to `tests/cli/test_doctor_checks.py`.
- Live evidence is recorded, not asserted; no test needs `gh`, network, or auth.
