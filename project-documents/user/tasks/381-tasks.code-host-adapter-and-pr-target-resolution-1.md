---
docType: tasks
slice: code-host-adapter-and-pr-target-resolution
project: squadron
lldReference: project-documents/user/slices/381-slice.code-host-adapter-and-pr-target-resolution.md
parent: project-documents/user/architecture/380-slices.pull-request-workflow.md
dependencies: [905]
interfaces: [382, 384, 385]
status: complete
dateCreated: 20260913
dateUpdated: 20260913
---

# Tasks: Code-Host Adapter and PR Target Resolution (1 of 2)

## Context Summary

The boundary the whole 380 initiative stands on: a code-host adapter protocol, a
GitHub implementation over the operator's `gh`, a typed PR record, the target
grammar, base-and-head fetch into namespaced refs, the enumerated failure modes,
and two `sq doctor` presence checks. Read-only against the host. Proving consumer
is `sq pr show <target>`.

Sequenced **A → I** per the design's Implementation Notes. The order is
load-bearing: every later part is tested *through* the process-runner seam built
in Part A, so that part cannot slip.

Nothing under `src/squadron/review/` changes except the mechanical helper
cwd helper extraction in Part A (see Coordination below).

### Verified code anchors (traced on `79986dea`, 20260913)

| Anchor | Location |
|---|---|
| `CheckResult` / `CheckStatus` shape | [doctor_checks.py:42-56](src/squadron/cli/commands/doctor_checks.py#L42-L56) |
| `SECTION_INTEGRATIONS` | [doctor_checks.py:21](src/squadron/cli/commands/doctor_checks.py#L21) |
| `check_codex_cli` — the WARN-with-hint pattern to copy | [doctor_checks.py:266-285](src/squadron/cli/commands/doctor_checks.py#L266-L285) |
| `run_all_checks` — `_run` wrapper and call order | [doctor_checks.py:465-530](src/squadron/cli/commands/doctor_checks.py#L465-L530) |
| Existing CLI presence checks (new rows go after these) | [doctor_checks.py:508-509](src/squadron/cli/commands/doctor_checks.py#L508-L509) |
| `TEXT_DECODING` | [subprocess_text.py:25](src/squadron/core/subprocess_text.py#L25) |
| `GIT_COMMAND_TIMEOUT_SECONDS = 30` (the value 381 matches, does not import) | [git_utils.py:24](src/squadron/review/git_utils.py#L24) |
| `find_git_root` | [git_utils.py:281](src/squadron/review/git_utils.py#L281) |
| `_resolve_cwd` (config-vs-flag) | [review.py:234-242](src/squadron/cli/commands/review.py#L234-L242) |
| `_resolve_review_cwd` (to be split in A.5) | [review.py:244-258](src/squadron/cli/commands/review.py#L244-L258) |
| `resolve_rules_dir(cwd, config_rules_dir, cli_rules_dir)` | [rules.py:18-22](src/squadron/review/rules.py#L18-L22) |
| `add_typer` registration block | [app.py:49-56](src/squadron/cli/app.py#L49-L56) |
| `doctor.py` `_render_json` + `--json` flag | [doctor.py:90](src/squadron/cli/commands/doctor.py#L90), [:142](src/squadron/cli/commands/doctor.py#L142) |
| `cli_runner` fixture; autouse reviews-dir isolation | [tests/cli/conftest.py:14](tests/cli/conftest.py#L14) |

Confirmed absent at task-writing time (genuinely new, create them):
`src/squadron/codehost/`, `tests/codehost/`, `src/squadron/core/process_runner.py`,
`tests/core/test_process_runner.py`, `src/squadron/cli/commands/pr.py`.

### Corrections against the design

Two design statements did not survive verification. Both are corrected in the
tasks below; neither changes scope.

| Design text | Finding | Disposition |
|---|---|---|
| "`run_all_checks` still makes no subprocess call (**existing test extended**)" | No such test exists — `grep subprocess tests/cli/test_doctor_checks.py` returns nothing. The invariant is also narrower than stated: `run_all_checks` calls `shutil.which` freely, and its docstring records that `git_hooks_path` is resolved *by the caller* precisely because a subprocess would violate the module's contract. | The doctor test task in Part E **writes** the test rather than extending one, and states the invariant as "no `subprocess.run`/`Popen` from the doctor-checks module", which is the property that actually holds. |
| "`--cwd` resolves as `sq review code` does" | That logic is `_resolve_review_cwd`, private to `review.py`, and it also resolves a rules directory `pr show` has no use for. The design does not say how `pr.py` obtains it. | PM decision (20260913): **extract the cwd half** into a shared CLI helper; `_resolve_review_cwd` becomes a thin wrapper. Sequenced early, in Part A. Widens the `sq-base` promise — see Coordination. |

### Coordination

Session `sq-base` (slice 917) asked to be told before the CLI command registry or
anything under `src/squadron/review/` is touched. This slice now makes **two**
such edits, not one:

1. `cli/app.py` — import and `add_typer(pr_app, name="pr")`, in the CLI part.
2. `review.py` — the A.5 helper extraction (mechanical; behavior-preserving).

Both are announced to `sq-base` **before** they are made. A.5 is deliberately
sequenced early and committed on its own so the `review.py` edit lands as one
small reviewable change rather than inside the CLI work.

### Standing constraints

- Every failure path raises a typed `CodeHostError` subclass, logs **once** at
  WARNING or ERROR with structured fields before raising, and exits 1 through the
  CLI. No silent path (Failure-Mode Enumeration rule).
- No test asserts on user-facing message *text* as logical structure. Assert on
  error type, structured fields, log level, and exit code. Message *content* may
  be asserted only where the design names it as the deliverable (e.g. an
  ambiguity message listing remote names).
- Timeouts are module constants, never inlined literals. The 30-second value
  matches `GIT_COMMAND_TIMEOUT_SECONDS` but is **not imported** from
  `squadron.review` — that is the reverse import the architecture forbids.
- No module under `codehost/` imports `squadron.review`, `squadron.cli`,
  `squadron.pipeline`, or `squadron.providers`.
- No `gh` call omits `--hostname`. The host always comes from the matched remote
  or the target URL, never from a default and never from `GH_HOST`.
- `ruff format`, `ruff check`, `pyright` clean before every commit; zero pyright
  errors is a merge blocker.

---

## Part A — Process-Runner Seam

Everything downstream is tested through this seam. Build it first.

### Task A.1 — `ProcessResult`, `ProcessRunner`, `SubprocessRunner`

- [x] Create `src/squadron/core/process_runner.py` beside
      [subprocess_text.py](src/squadron/core/subprocess_text.py).
- [x] `ProcessResult`: frozen dataclass, fields `argv: tuple[str, ...]`,
      `returncode: int`, `stdout: str`, `stderr: str`.
- [x] `ProcessRunner` protocol, exactly this signature — `stdin` is how write
      operations pass a body, and it is load-bearing for Part G:

  ```python
  def run(self, argv: Sequence[str], *, cwd: str | None, timeout: float,
          env: Mapping[str, str] | None = None, stdin: str | None = None) -> ProcessResult: ...
  ```

- [x] `SubprocessRunner.run` wraps `subprocess.run` with
      `capture_output=True, text=True, check=False, timeout=timeout` and
      `**TEXT_DECODING` ([subprocess_text.py:25](src/squadron/core/subprocess_text.py#L25)).
      Every text-mode subprocess call in this repo passes it; do not omit it.
- [x] `env` is merged **over** `os.environ`, not substituted for it. A `gh` call
      with a replaced environment loses `PATH` and `HOME`.
- [x] Effort: 2

### Task A.2 — The two runner errors

- [x] `ProcessNotFoundError(executable)` from `FileNotFoundError`;
      `ProcessTimedOutError(argv, timeout)` from `subprocess.TimeoutExpired`.
- [x] Both are **distinct types**, not a shared `None` return. `run_git`
      ([git_utils.py:27](src/squadron/review/git_utils.py#L27)) returns `None` for
      both; the architecture names "host call exceeded its timeout" as its own
      failure mode, so 381 cannot collapse them.
- [x] The runner logs both at WARNING with the argv, and for the timeout the
      bound, before raising.
- [x] Effort: 1

### Task A.3 — `FakeProcessRunner`

- [x] Create `tests/codehost/` (with `__init__.py` — every tests subdirectory here
      is a package) and `tests/codehost/fake_runner.py`.
- [x] Scripted as an ordered list of `(argv_prefix, ProcessResult | Exception)`.
      A scripted `Exception` is **raised**, which is how a wedged `gh` is produced.
- [x] Records every call including `cwd`, `env`, and `stdin`, so a test can assert
      the exact body sent over stdin.
- [x] An **unscripted argv raises immediately**. A fake that returns a benign
      default lets a test pass on a process the implementation should never have
      run — that is the whole reason this is not a `MagicMock`.
- [x] `write_calls()` returns the recorded argv subset that would mutate the host:
      contains `-X POST`, `-X PATCH`, or `pr create`. 384's "zero writes without
      `--post`" assertion must be one call against this.
- [x] There is no existing `class Fake` in `tests/` to copy — this establishes the
      convention. Keep it a plain class, not a fixture, so `tests/core` can use it
      too.
- [x] Effort: 3

### Task A.4 — Test: the real runner

- [x] Create `tests/core/test_process_runner.py` (`tests/core/` exists and holds
      `test_agent_registry.py`).
- [x] Cover, against `python -c` so no external binary is required:
  - [x] success — stdout, stderr, and returncode land on `ProcessResult`
  - [x] non-zero exit is **returned**, not raised (`check=False`)
  - [x] missing executable → `ProcessNotFoundError` naming the executable
  - [x] a sleep exceeding a short timeout → `ProcessTimedOutError` naming the bound
  - [x] `env` merges over `os.environ` rather than replacing it — assert a
        pre-existing variable survives alongside the injected one
  - [x] non-UTF-8 bytes on stdout do not raise (the `TEXT_DECODING` pin)
- [x] Assert a WARNING record for both error paths (`caplog`).
- [x] Effort: 2

### Task A.5 — Extract the shared cwd helper (touches `review.py`)

- [x] **Notify `sq-base` before making this edit.**
- [x] PM decision 20260913: `pr show --cwd` must anchor at the git root exactly as
      `sq review code` does, but `_resolve_review_cwd`
      ([review.py:244](src/squadron/cli/commands/review.py#L244)) is private and
      also resolves a rules directory `pr show` does not need.
- [x] Create a shared CLI helper module holding the cwd half: the config-vs-flag
      resolution now at [review.py:234-242](src/squadron/cli/commands/review.py#L234-L242)
      and the `find_git_root(...) or resolved_cwd` anchoring at
      [review.py:257](src/squadron/cli/commands/review.py#L257).
- [x] `_resolve_review_cwd` becomes a thin wrapper: call the shared helper, then
      `resolve_rules_dir(review_cwd, None, rules_dir_flag)`
      ([rules.py:18](src/squadron/review/rules.py#L18)). Its signature and return
      tuple **do not change** — all five call sites
      ([:707](src/squadron/cli/commands/review.py#L707),
      [:771](src/squadron/cli/commands/review.py#L771),
      [:877](src/squadron/cli/commands/review.py#L877),
      [:981](src/squadron/cli/commands/review.py#L981),
      [:1192](src/squadron/cli/commands/review.py#L1192)) stay untouched.
- [x] **Behavior-preserving.** If this edit changes any review behavior, it is
      wrong. The existing review test suite is the check.
- [x] `find_git_root` currently lives in `review/git_utils.py`. **Accept the
      `cli → review` import** in the shared helper rather than moving or
      re-exporting the function: `review.py` already imports it
      ([review.py:34](src/squadron/cli/commands/review.py#L34)), `cli → review` is
      an existing and permitted direction, and relocating a function seven other
      callers use would widen a behavior-preserving extraction into a refactor.
      What matters is the prohibition below, not where `find_git_root` sits.
- [x] `codehost/` must **not** acquire this import in either direction. The
      `cli → codehost → core` rule is what the import-graph test pins.
- [x] Effort: 2

### Task A.6 — Test and commit Part A

- [x] Run `uv run pytest tests/core tests/review tests/cli -q`. All green — the
      review suite is what proves A.5 preserved behavior.
- [x] Add a test that the shared cwd helper anchors at the git root, and falls back
      to the resolved cwd outside a work tree.
- [x] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [x] Commit: `feat(core): add injected process-runner seam with bounded timeouts`
- [x] Effort: 1

---

## Part B — Models, Errors, Protocol

Pure declarations. No behavior, so no test task of their own — Parts C onward
exercise every field and every error class.

### Task B.1 — `codehost/models.py`

- [x] Create `src/squadron/codehost/` with `__init__.py`.
- [x] `__init__.py` **re-exports the package's public surface** — the design's
      Integration Points → Provides list, which is the contract 382, 384, and 385
      import. An empty `__init__.py` satisfies the "create it" bullet above and
      still breaks those slices into deep-path imports, so the re-exports are their
      own deliverable: `CodeHost`, `GitHubCli`, `PullRequestRecord`,
      `ResolvedPullRequest`, `FetchedRange`, `ReviewDiscussion`, `HostComment`,
      `OperatorIdentity`, the error hierarchy, `parse_target`, `list_remotes`,
      `select_remote`, `build_github_host`. Add each name as its part lands; the
      sweep in Part I verifies the full list imports from the package root.
- [x] All frozen dataclasses. Field names are the architecture's — do not rename.
- [x] `PullRequestRecord(host, owner, repository, number, base_ref, head_ref,
      head_sha, url)` with a `key` property returning
      `f"{host}/{owner}/{repository}#{number}"`. 383 uses `key` as a filename
      prefix, so it must be stable and filesystem-safe.
- [x] `ResolvedPullRequest(record, title, body, state, author_login, base_sha,
      is_cross_repository, head_repository, linked_issue_numbers)`.
- [x] `PullRequestState` enum `{OPEN, CLOSED, MERGED}`. GraphQL returns these
      uppercase; map explicitly rather than relying on case coincidence.
- [x] `RepositoryLocator(host, owner, repository, remote_name)`,
      `LocalRemote(name, host, owner, repository, url)` where `host` is
      `str | None` for an unparseable URL.
- [x] `FetchedRange(base_ref, head_ref, base_sha, head_sha, merge_base,
      diff_range, changed_paths)`.
- [x] `ReviewDiscussion(path, line, author_login, body, url)`,
      `HostComment(id, author_login, body, url)`, `OperatorIdentity(host, login)`.
- [x] `RefRole` enum `{BASE, HEAD}`.
- [x] Effort: 2

### Task B.2 — `codehost/errors.py`

- [x] `CodeHostError(Exception)` carrying `fix_hint: str | None`.
- [x] One subclass per error named in the design's error table — **nineteen
      classes across its fifteen rows**, since three rows group two or three
      classes each. The count is the check; do not stop early:
      `GitHubCliMissingError`, `HostUnauthenticatedError`, `HostUnreachableError`,
      `HostCommandTimeoutError`, `PullRequestNotFoundError`,
      `NoOpenPullRequestForBranchError`, `AmbiguousBranchPullRequestsError`,
      `ForeignRepositoryError`, `NoHostRemoteError`, `AmbiguousHostRemoteError`,
      `TargetSyntaxError`, `TargetUnresolvableError`, `RefNotFetchableError`,
      `RefMovedSinceResolutionError`, `NoMergeBaseError`,
      `HostRequestRejectedError`, `PullRequestCreationRejectedError`,
      `HostResponseMalformedError`, `OperatorUnidentifiedError`.
- [x] Each carries its structured fields as attributes, not only in the message:
      `RefMovedSinceResolutionError(role, expected, actual)`,
      `HostRequestRejectedError(status, message)`,
      `HostCommandTimeoutError(argv, seconds)`,
      `RefNotFetchableError(role)`, `HostResponseMalformedError(argv, detail)`.
- [x] Effort: 2

### Task B.3 — `codehost/protocol.py`

- [x] `CodeHost` protocol with the eleven operations exactly as the design's
      listing gives them, including `serves_host(hostname) -> bool`.
- [x] `branch_exists` returns `bool` — a missing branch is an answer, not a raise.
      Only transport and auth failures raise.
- [x] `fetch_pull_request_refs` is on the protocol because the refspec is the
      host's convention; the implementation supplies refspecs and delegates the
      git work to `refs.fetch_and_range`.
- [x] Effort: 1

### Task B.4 — Commit Part B

- [x] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [x] Commit: `feat(codehost): add typed records, error hierarchy, and host protocol`
- [x] Effort: 1

---

## Part C — Target Grammar

### Task C.1 — `parse_target`

- [x] Create `src/squadron/codehost/targets.py`. `parse_target(text: str | None)
      -> PullRequestTarget` with `form: TargetForm`.
- [x] Six forms, classified in this order, **each rule exclusive of the ones after
      it**. The order is the specification, not an optimization:

  | Order | Form | Rule | Carries |
  |---|---|---|---|
  | 1 | `CURRENT_BRANCH` | `text` is `None` or empty | nothing |
  | 2 | `URL` | has a scheme and a path matching `/{owner}/{repo}/pull/{n}` | host, owner, repository, number |
  | 3 | `OWNER_REPO_NUMBER` | exactly one `/` before a `#`, digits after, no whitespace | owner, repository, number |
  | 4 | `REPO_NUMBER` | no `/`, a `#`, digits after, non-empty name before | repository, number |
  | 5 | `NUMBER` | all digits, or `#` followed by digits | number |
  | 6 | `BRANCH` | anything else `git check-ref-format --branch` accepts | branch |

- [x] Tolerate a trailing `.git`, a trailing slash, and a `?`/`#` fragment on a URL.
- [x] A string failing rule 6 is `TargetSyntaxError`.
- [x] The grammar lives **here and nowhere else**. `pr.py` passes the raw string
      through; no pre-parsing at the CLI edge.
- [x] Do not implement the two-token form `squadron 7` — deferred as
      [issue #95](https://github.com/ecorkran/squadron/issues/95) because a second
      positional makes "branch name followed by a number" ambiguous.
- [x] Effort: 3

### Task C.2 — Test: the grammar

- [x] `tests/codehost/test_targets.py`, table-driven over all six forms.
- [x] Pin the **exclusivity** of the ordering explicitly — these are the cases a
      reordering would silently break:
  - [x] `owner/repo#7` is form 3, never form 4 or 6
  - [x] `repo#7` is form 4, never form 6
  - [x] `#7` and `7` are form 5, never form 6
  - [x] a branch literally named `7` is unreachable by design; assert form 5 wins
        and record that as intended
- [x] Cover the tolerated suffixes: `.git`, trailing slash, URL fragment/query.
- [x] Cover `None` and `""` → form 1.
- [x] Assert `TargetSyntaxError` for a string valid under no rule (e.g. one
      containing a space or a control character).
- [x] Effort: 2

### Task C.3 — Commit

- [x] `uv run pytest tests/codehost -q`; ruff; pyright.
- [x] Commit: `feat(codehost): add PR target grammar`
- [x] Effort: 1

---

## Part D — Remote Enumeration and Selection

### Task D.1 — `list_remotes` and `parse_remote_url`

- [x] Create `src/squadron/codehost/remotes.py`.
- [x] `list_remotes(runner, cwd)` runs `git remote`, then `git remote get-url
      <name>` per remote, both bounded by `GIT_QUERY_TIMEOUT_SECONDS`.
- [x] `parse_remote_url` handles three shapes: `https://host/owner/repo(.git)`,
      `ssh://git@host/owner/repo`, and the scp-like `git@host:owner/repo(.git)`.
- [x] A URL matching none yields `LocalRemote(host=None, ...)`. It is **never a
      candidate**, but it is retained and listed by name in ambiguity messages so
      the operator sees why it was skipped. Dropping it silently is the failure
      mode this guards.
- [x] Effort: 3

### Task D.2 — `select_remote`

- [x] `select_remote(target, remotes, serves_host) -> RepositoryLocator`. Three
      branches by target form:
  - [x] **Explicit** (URL, `owner/repo#n`): candidates match owner **and**
        repository case-insensitively, and host when the form names one. Zero
        candidates → `ForeignRepositoryError` naming the target's repository and
        every remote's repository. Several → take the first in `git remote` order
        and **log the choice at INFO**.
  - [x] **Repository-name** (`repo#n`): candidates are remotes where
        `serves_host(host)` and the repository name matches case-insensitively,
        owner ignored. Zero → `ForeignRepositoryError`. More than one owner →
        `AmbiguousHostRemoteError` listing `owner/repo` for each, with the
        `owner/repo#n` form as the remedy.
  - [x] **Bare** (number, branch, current branch): candidates are remotes where
        `serves_host(host)`. Exactly one required. Zero → `NoHostRemoteError`.
        More than one → `AmbiguousHostRemoteError` listing the remote names.
- [x] `serves_host` is passed in as a callable, not imported from `github_cli` —
      selection must stay host-agnostic.
- [x] Effort: 3

### Task D.3 — Test: enumeration and selection

- [x] `tests/codehost/test_remotes.py`, against the fake runner.
- [x] URL parsing: all three shapes, with and without `.git`, over **both**
      `github.com` and `ghe.corp.example`.
- [x] An unparseable remote URL yields `host=None` and is skipped as a candidate
      **and** appears by name in the ambiguity message.
- [x] Fork layout (`origin` fork + `upstream` canonical, both GitHub): explicit
      forms resolve; bare forms raise `AmbiguousHostRemoteError` whose message
      contains **both remote names** (the design names the message content as the
      deliverable here).
- [x] One GitHub remote + one non-GitHub mirror: bare forms **resolve**. This is
      why `serves_host` exists; it is the case a naive "exactly one remote" rule
      gets wrong.
- [x] `repo#n` with the same repository name under two owners →
      `AmbiguousHostRemoteError`.
- [x] A target naming a repository no remote points at → `ForeignRepositoryError`
      naming both sides.
- [x] Two remotes for one repository → first in `git remote` order, INFO logged.
- [x] Effort: 3

### Task D.4 — Commit

- [x] `uv run pytest tests/codehost -q`; ruff; pyright.
- [x] Commit: `feat(codehost): add remote enumeration and target-to-remote selection`
- [x] Effort: 1

---

## Part E — `gh` Config Reading and Doctor Checks

### Task E.1 — `github_config.py`

- [x] Create `src/squadron/codehost/github_config.py`. **No subprocess** in this
      module.
- [x] `gh_hosts_file_path()`: `$GH_CONFIG_DIR/hosts.yml` when `GH_CONFIG_DIR` is
      set, else `~/.config/gh/hosts.yml`.
- [x] `read_gh_hosts()`: top-level keys of that YAML file via `pyyaml`
      (`pyyaml>=6.0`, already a dependency — [pyproject.toml:34](pyproject.toml#L34)).
      Missing file, unreadable file, or malformed YAML yields an empty set, not a
      raise — absence of `gh` config is a normal state, and the adapter reports
      auth failures at invocation instead.
- [x] Use `yaml.safe_load`, never `yaml.load`.
- [x] Effort: 2

### Task E.2 — The two doctor checks

- [x] Add to [doctor_checks.py](src/squadron/cli/commands/doctor_checks.py),
      following `check_codex_cli`
      ([:266-285](src/squadron/cli/commands/doctor_checks.py#L266-L285)) exactly —
      same `CheckResult` shape, `section=SECTION_INTEGRATIONS`, `required=False`.
      A squadron install without PR workflows is complete.
- [x] `check_github_cli()`: `shutil.which("gh")`. OK with the path; WARN "not on
      PATH" with a module-level install-hint constant (`brew install gh`, or
      `https://cli.github.com`). Define the hint **once** as a constant, matching
      how the neighbours inline theirs only because they are single-use — this one
      is named in the design, so name it.
- [x] `check_github_cli_hosts_file()`: OK when the path from `gh_hosts_file_path()`
      exists and `os.access(path, os.R_OK)`; WARN "missing" with hint
      `gh auth login`; WARN "not readable" with the path. **The file is not parsed
      by doctor.**
- [x] Register both in `run_all_checks` via `_run`, **after** the existing CLI
      presence checks at
      [:508-509](src/squadron/cli/commands/doctor_checks.py#L508-L509).
- [x] Effort: 2

### Task E.3 — Test: doctor rows

- [x] Extend [tests/cli/test_doctor_checks.py](tests/cli/test_doctor_checks.py).
- [x] `gh` present → OK row carrying the path; absent → WARN with the install hint;
      `sq doctor` still **exits 0** because the check is not required.
- [x] Hosts file present and readable → OK; missing → WARN with the `gh auth login`
      hint; present but unreadable → WARN naming the path. Use `tmp_path` plus
      `GH_CONFIG_DIR` rather than touching the real `~/.config/gh`.
- [x] `read_gh_hosts` on a malformed YAML file returns an empty set and does not
      raise.
- [x] **Write the doctor-module subprocess invariant test** (the design named an
      "existing test extended"; none exists — see the Corrections table above).
      Assert no `subprocess.run`/`Popen` originates in `doctor_checks.py` during
      `run_all_checks`. `shutil.which` is permitted; the git-hooks path is resolved
      by the caller and passed in
      ([doctor_checks.py:465-472](src/squadron/cli/commands/doctor_checks.py#L465-L472)).
      It lives here, with the doctor checks it guards, rather than travelling to a
      later part.
- [x] Effort: 2

### Task E.4 — Commit

- [x] `uv run pytest tests/cli tests/codehost -q`; ruff; pyright.
- [x] Commit: `feat(doctor): add gh CLI and hosts-file presence checks`
- [x] Effort: 1

---

## Task Review Disposition

Task review (`381-review.tasks.code-host-adapter-and-pr-target-resolution.part-1.md`,
z-ai/glm-5.3-flash, CONCERNS, 20260913, sha `cb2ce122`, 22 tool calls). Five
concerns and two notes actioned; one finding corrected in both directions.

- **F004 (concern) — accepted, and the reviewer's own count corrected.** B.2 said
  "All sixteen" over a list of **nineteen** class names. The reviewer caught the
  discrepancy but proposed "nineteen classes across fourteen rows"; the design's
  table has **fifteen** data rows, since three rows group two or three classes
  each. So both the file and the review were wrong, in different places. The bullet
  now reads nineteen classes across fifteen rows and says the count is the check.
  The knock-on reference in the CLI error test ("B.2's table" — B.2 is a list, not
  a table) now points at the design's error table with the count restated.
- **F005 (concern) — accepted, a real ordering defect.** The write-operations test
  task asserted `write_calls()` stays empty "across a full `sq pr show` run", one
  task before `pr.py` is created. Verified: the bullet sits in the write test, and
  the command is created in the next task. Split in two — the write test now
  scripts a full adapter pipeline (parse, select, resolve, fetch), and the
  CLI-level assertion moves to the `sq pr show` test where the command exists. The
  review was right that dropping the bullet during execution would have cost the
  slice its only in-suite read-only proof, which 384 is documented to reuse.
- **F006 (concern) — accepted.** The CLI test task carried four unrelated
  deliverables across two test files, including the densest test in the slice.
  Split into a behavior task (six-form parity, `--json`, the CLI-level
  `write_calls()` half) and an observability task (the nineteen-class error table,
  the import-graph walk). The deviation from the design's separate
  `test_errors_observable.py` is now stated rather than silent: exit codes are only
  observable through the CLI, so the error table lives with the CLI test.
- **F007 (concern) — accepted.** The cwd-helper extraction was documented in this
  file but contradicted by the design, whose Excluded and Coordination sections
  still said nothing under `review/` changes. Verified both lines still read that
  way. The design now carries a fourth scope-corrections row, an amended Excluded
  bullet, and a Coordination section naming both `sq-base` notifications. The
  reviewer's minor point is also taken: the extraction's open
  re-export-or-import choice is now decided — accept the `cli → review` import,
  since `review.py` already has it and moving a function with seven other callers
  would turn a behavior-preserving extraction into a refactor.
- **F008 (concern) — accepted, the most consequential.** The design specifies that
  `__init__.py` re-exports the package's public surface, and its Provides list is
  the contract 382/384/385 import. The models task said only "create it" — every
  checkbox satisfiable with an empty file, with the divergence surfacing only at
  382 integration as deep-path imports. A re-export bullet naming the full Provides
  list is added, verified once in the closeout sweep.
- **F009 (note) — accepted.** The doctor-subprocess invariant test was assigned two
  parts after the doctor checks it guards. Moved to the doctor test task, which
  already extends `tests/cli/test_doctor_checks.py`. The reviewer flagged it could
  not verify the "no such test exists" claim from its workspace; that claim was
  verified here before the correction was written, and again now.
- **F010 (note) — acknowledged, no change.** Per-part commit tasks are uniformly
  effort-1 by design; they are the distributed checkpoints the process asks for.
- **F001–F003 (pass)** — no action.

Note on scope: the review's `sourceDocument` names file 1 and its filename says
`part-1`, but its findings cover both files. A part-2 review has since arrived
(sha `ea0fca58`, reviewing the post-disposition state); it is dispositioned in the
**Task Review Disposition (part 2)** section at the end of
[file 2](project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md),
whose `sourceDocument` it names. Its F008 synced two superseded statements back into
the design; nothing in this file's dispositions was reversed.

---

**Parts F–I continue in
[381-tasks.code-host-adapter-and-pr-target-resolution-2.md](project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md)**
— GitHub reads, fetch and range, writes and CLI, live evidence and closeout. The
Context Summary, code anchors, corrections, coordination, and standing
constraints above govern both files.
