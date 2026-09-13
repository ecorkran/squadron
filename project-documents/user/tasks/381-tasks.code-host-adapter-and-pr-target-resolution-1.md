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

# Tasks: Code-Host Adapter and PR Target Resolution (1 of 2)

## Context Summary

The boundary the whole 380 initiative stands on: a code-host adapter protocol, a
GitHub implementation over the operator's `gh`, a typed PR record, the target
grammar, base-and-head fetch into namespaced refs, the enumerated failure modes,
and two `sq doctor` presence checks. Read-only against the host. Proving consumer
is `sq pr show <target>`.

Sequenced **A → I** per the design's Implementation Notes. The order is
load-bearing: every later part is tested *through* the process-runner seam built
in Part A, so A cannot slip.

Nothing under `src/squadron/review/` changes except the mechanical helper
extraction in Part A.5 (see Coordination below).

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
| "`run_all_checks` still makes no subprocess call (**existing test extended**)" | No such test exists — `grep subprocess tests/cli/test_doctor_checks.py` returns nothing. The invariant is also narrower than stated: `run_all_checks` calls `shutil.which` freely, and its docstring records that `git_hooks_path` is resolved *by the caller* precisely because a subprocess would violate the module's contract. | G.3 **writes** the test rather than extending one, and states the invariant as "no `subprocess.run`/`Popen` from the doctor-checks module", which is the property that actually holds. |
| "`--cwd` resolves as `sq review code` does" | That logic is `_resolve_review_cwd`, private to `review.py`, and it also resolves a rules directory `pr show` has no use for. The design does not say how `pr.py` obtains it. | PM decision (20260913): **extract the cwd half** into a shared CLI helper; `_resolve_review_cwd` becomes a thin wrapper. Task A.5. Widens the `sq-base` promise — see Coordination. |

### Coordination

Session `sq-base` (slice 917) asked to be told before the CLI command registry or
anything under `src/squadron/review/` is touched. This slice now makes **two**
such edits, not one:

1. `cli/app.py` — import and `add_typer(pr_app, name="pr")` (Task H.3).
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

- [ ] Create `src/squadron/core/process_runner.py` beside
      [subprocess_text.py](src/squadron/core/subprocess_text.py).
- [ ] `ProcessResult`: frozen dataclass, fields `argv: tuple[str, ...]`,
      `returncode: int`, `stdout: str`, `stderr: str`.
- [ ] `ProcessRunner` protocol, exactly this signature — `stdin` is how write
      operations pass a body, and it is load-bearing for Part G:

  ```python
  def run(self, argv: Sequence[str], *, cwd: str | None, timeout: float,
          env: Mapping[str, str] | None = None, stdin: str | None = None) -> ProcessResult: ...
  ```

- [ ] `SubprocessRunner.run` wraps `subprocess.run` with
      `capture_output=True, text=True, check=False, timeout=timeout` and
      `**TEXT_DECODING` ([subprocess_text.py:25](src/squadron/core/subprocess_text.py#L25)).
      Every text-mode subprocess call in this repo passes it; do not omit it.
- [ ] `env` is merged **over** `os.environ`, not substituted for it. A `gh` call
      with a replaced environment loses `PATH` and `HOME`.
- [ ] Effort: 2

### Task A.2 — The two runner errors

- [ ] `ProcessNotFoundError(executable)` from `FileNotFoundError`;
      `ProcessTimedOutError(argv, timeout)` from `subprocess.TimeoutExpired`.
- [ ] Both are **distinct types**, not a shared `None` return. `run_git`
      ([git_utils.py:27](src/squadron/review/git_utils.py#L27)) returns `None` for
      both; the architecture names "host call exceeded its timeout" as its own
      failure mode, so 381 cannot collapse them.
- [ ] The runner logs both at WARNING with the argv, and for the timeout the
      bound, before raising.
- [ ] Effort: 1

### Task A.3 — `FakeProcessRunner`

- [ ] Create `tests/codehost/` (with `__init__.py` — every tests subdirectory here
      is a package) and `tests/codehost/fake_runner.py`.
- [ ] Scripted as an ordered list of `(argv_prefix, ProcessResult | Exception)`.
      A scripted `Exception` is **raised**, which is how a wedged `gh` is produced.
- [ ] Records every call including `cwd`, `env`, and `stdin`, so a test can assert
      the exact body sent over stdin.
- [ ] An **unscripted argv raises immediately**. A fake that returns a benign
      default lets a test pass on a process the implementation should never have
      run — that is the whole reason this is not a `MagicMock`.
- [ ] `write_calls()` returns the recorded argv subset that would mutate the host:
      contains `-X POST`, `-X PATCH`, or `pr create`. 384's "zero writes without
      `--post`" assertion must be one call against this.
- [ ] There is no existing `class Fake` in `tests/` to copy — this establishes the
      convention. Keep it a plain class, not a fixture, so `tests/core` can use it
      too.
- [ ] Effort: 3

### Task A.4 — Test: the real runner

- [ ] Create `tests/core/test_process_runner.py` (`tests/core/` exists and holds
      `test_agent_registry.py`).
- [ ] Cover, against `python -c` so no external binary is required:
  - [ ] success — stdout, stderr, and returncode land on `ProcessResult`
  - [ ] non-zero exit is **returned**, not raised (`check=False`)
  - [ ] missing executable → `ProcessNotFoundError` naming the executable
  - [ ] a sleep exceeding a short timeout → `ProcessTimedOutError` naming the bound
  - [ ] `env` merges over `os.environ` rather than replacing it — assert a
        pre-existing variable survives alongside the injected one
  - [ ] non-UTF-8 bytes on stdout do not raise (the `TEXT_DECODING` pin)
- [ ] Assert a WARNING record for both error paths (`caplog`).
- [ ] Effort: 2

### Task A.5 — Extract the shared cwd helper (touches `review.py`)

- [ ] **Notify `sq-base` before making this edit.**
- [ ] PM decision 20260913: `pr show --cwd` must anchor at the git root exactly as
      `sq review code` does, but `_resolve_review_cwd`
      ([review.py:244](src/squadron/cli/commands/review.py#L244)) is private and
      also resolves a rules directory `pr show` does not need.
- [ ] Create a shared CLI helper module holding the cwd half: the config-vs-flag
      resolution now at [review.py:234-242](src/squadron/cli/commands/review.py#L234-L242)
      and the `find_git_root(...) or resolved_cwd` anchoring at
      [review.py:257](src/squadron/cli/commands/review.py#L257).
- [ ] `_resolve_review_cwd` becomes a thin wrapper: call the shared helper, then
      `resolve_rules_dir(review_cwd, None, rules_dir_flag)`
      ([rules.py:18](src/squadron/review/rules.py#L18)). Its signature and return
      tuple **do not change** — all five call sites
      ([:707](src/squadron/cli/commands/review.py#L707),
      [:771](src/squadron/cli/commands/review.py#L771),
      [:877](src/squadron/cli/commands/review.py#L877),
      [:981](src/squadron/cli/commands/review.py#L981),
      [:1192](src/squadron/cli/commands/review.py#L1192)) stay untouched.
- [ ] **Behavior-preserving.** If this edit changes any review behavior, it is
      wrong. The existing review test suite is the check.
- [ ] The helper must not import from `squadron.review` for the cwd half —
      `find_git_root` currently lives in `review/git_utils.py`. Either re-export it
      or accept the `cli → review` import here and record which; do **not** let
      `codehost/` acquire it either way.
- [ ] Effort: 2

### Task A.6 — Test and commit Part A

- [ ] Run `uv run pytest tests/core tests/review tests/cli -q`. All green — the
      review suite is what proves A.5 preserved behavior.
- [ ] Add a test that the shared cwd helper anchors at the git root, and falls back
      to the resolved cwd outside a work tree.
- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(core): add injected process-runner seam with bounded timeouts`
- [ ] Effort: 1

---

## Part B — Models, Errors, Protocol

Pure declarations. No behavior, so no test task of their own — Parts C onward
exercise every field and every error class.

### Task B.1 — `codehost/models.py`

- [ ] Create `src/squadron/codehost/` with `__init__.py`.
- [ ] All frozen dataclasses. Field names are the architecture's — do not rename.
- [ ] `PullRequestRecord(host, owner, repository, number, base_ref, head_ref,
      head_sha, url)` with a `key` property returning
      `f"{host}/{owner}/{repository}#{number}"`. 383 uses `key` as a filename
      prefix, so it must be stable and filesystem-safe.
- [ ] `ResolvedPullRequest(record, title, body, state, author_login, base_sha,
      is_cross_repository, head_repository, linked_issue_numbers)`.
- [ ] `PullRequestState` enum `{OPEN, CLOSED, MERGED}`. GraphQL returns these
      uppercase; map explicitly rather than relying on case coincidence.
- [ ] `RepositoryLocator(host, owner, repository, remote_name)`,
      `LocalRemote(name, host, owner, repository, url)` where `host` is
      `str | None` for an unparseable URL.
- [ ] `FetchedRange(base_ref, head_ref, base_sha, head_sha, merge_base,
      diff_range, changed_paths)`.
- [ ] `ReviewDiscussion(path, line, author_login, body, url)`,
      `HostComment(id, author_login, body, url)`, `OperatorIdentity(host, login)`.
- [ ] `RefRole` enum `{BASE, HEAD}`.
- [ ] Effort: 2

### Task B.2 — `codehost/errors.py`

- [ ] `CodeHostError(Exception)` carrying `fix_hint: str | None`.
- [ ] One subclass per row of the design's error table. All sixteen:
      `GitHubCliMissingError`, `HostUnauthenticatedError`, `HostUnreachableError`,
      `HostCommandTimeoutError`, `PullRequestNotFoundError`,
      `NoOpenPullRequestForBranchError`, `AmbiguousBranchPullRequestsError`,
      `ForeignRepositoryError`, `NoHostRemoteError`, `AmbiguousHostRemoteError`,
      `TargetSyntaxError`, `TargetUnresolvableError`, `RefNotFetchableError`,
      `RefMovedSinceResolutionError`, `NoMergeBaseError`,
      `HostRequestRejectedError`, `PullRequestCreationRejectedError`,
      `HostResponseMalformedError`, `OperatorUnidentifiedError`.
- [ ] Each carries its structured fields as attributes, not only in the message:
      `RefMovedSinceResolutionError(role, expected, actual)`,
      `HostRequestRejectedError(status, message)`,
      `HostCommandTimeoutError(argv, seconds)`,
      `RefNotFetchableError(role)`, `HostResponseMalformedError(argv, detail)`.
- [ ] Effort: 2

### Task B.3 — `codehost/protocol.py`

- [ ] `CodeHost` protocol with the eleven operations exactly as the design's
      listing gives them, including `serves_host(hostname) -> bool`.
- [ ] `branch_exists` returns `bool` — a missing branch is an answer, not a raise.
      Only transport and auth failures raise.
- [ ] `fetch_pull_request_refs` is on the protocol because the refspec is the
      host's convention; the implementation supplies refspecs and delegates the
      git work to `refs.fetch_and_range`.
- [ ] Effort: 1

### Task B.4 — Commit Part B

- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(codehost): add typed records, error hierarchy, and host protocol`
- [ ] Effort: 1

---

## Part C — Target Grammar

### Task C.1 — `parse_target`

- [ ] Create `src/squadron/codehost/targets.py`. `parse_target(text: str | None)
      -> PullRequestTarget` with `form: TargetForm`.
- [ ] Six forms, classified in this order, **each rule exclusive of the ones after
      it**. The order is the specification, not an optimization:

  | Order | Form | Rule | Carries |
  |---|---|---|---|
  | 1 | `CURRENT_BRANCH` | `text` is `None` or empty | nothing |
  | 2 | `URL` | has a scheme and a path matching `/{owner}/{repo}/pull/{n}` | host, owner, repository, number |
  | 3 | `OWNER_REPO_NUMBER` | exactly one `/` before a `#`, digits after, no whitespace | owner, repository, number |
  | 4 | `REPO_NUMBER` | no `/`, a `#`, digits after, non-empty name before | repository, number |
  | 5 | `NUMBER` | all digits, or `#` followed by digits | number |
  | 6 | `BRANCH` | anything else `git check-ref-format --branch` accepts | branch |

- [ ] Tolerate a trailing `.git`, a trailing slash, and a `?`/`#` fragment on a URL.
- [ ] A string failing rule 6 is `TargetSyntaxError`.
- [ ] The grammar lives **here and nowhere else**. `pr.py` passes the raw string
      through; no pre-parsing at the CLI edge.
- [ ] Do not implement the two-token form `squadron 7` — deferred as
      [issue #95](https://github.com/ecorkran/squadron/issues/95) because a second
      positional makes "branch name followed by a number" ambiguous.
- [ ] Effort: 3

### Task C.2 — Test: the grammar

- [ ] `tests/codehost/test_targets.py`, table-driven over all six forms.
- [ ] Pin the **exclusivity** of the ordering explicitly — these are the cases a
      reordering would silently break:
  - [ ] `owner/repo#7` is form 3, never form 4 or 6
  - [ ] `repo#7` is form 4, never form 6
  - [ ] `#7` and `7` are form 5, never form 6
  - [ ] a branch literally named `7` is unreachable by design; assert form 5 wins
        and record that as intended
- [ ] Cover the tolerated suffixes: `.git`, trailing slash, URL fragment/query.
- [ ] Cover `None` and `""` → form 1.
- [ ] Assert `TargetSyntaxError` for a string valid under no rule (e.g. one
      containing a space or a control character).
- [ ] Effort: 2

### Task C.3 — Commit

- [ ] `uv run pytest tests/codehost -q`; ruff; pyright.
- [ ] Commit: `feat(codehost): add PR target grammar`
- [ ] Effort: 1

---

## Part D — Remote Enumeration and Selection

### Task D.1 — `list_remotes` and `parse_remote_url`

- [ ] Create `src/squadron/codehost/remotes.py`.
- [ ] `list_remotes(runner, cwd)` runs `git remote`, then `git remote get-url
      <name>` per remote, both bounded by `GIT_QUERY_TIMEOUT_SECONDS`.
- [ ] `parse_remote_url` handles three shapes: `https://host/owner/repo(.git)`,
      `ssh://git@host/owner/repo`, and the scp-like `git@host:owner/repo(.git)`.
- [ ] A URL matching none yields `LocalRemote(host=None, ...)`. It is **never a
      candidate**, but it is retained and listed by name in ambiguity messages so
      the operator sees why it was skipped. Dropping it silently is the failure
      mode this guards.
- [ ] Effort: 3

### Task D.2 — `select_remote`

- [ ] `select_remote(target, remotes, serves_host) -> RepositoryLocator`. Three
      branches by target form:
  - [ ] **Explicit** (URL, `owner/repo#n`): candidates match owner **and**
        repository case-insensitively, and host when the form names one. Zero
        candidates → `ForeignRepositoryError` naming the target's repository and
        every remote's repository. Several → take the first in `git remote` order
        and **log the choice at INFO**.
  - [ ] **Repository-name** (`repo#n`): candidates are remotes where
        `serves_host(host)` and the repository name matches case-insensitively,
        owner ignored. Zero → `ForeignRepositoryError`. More than one owner →
        `AmbiguousHostRemoteError` listing `owner/repo` for each, with the
        `owner/repo#n` form as the remedy.
  - [ ] **Bare** (number, branch, current branch): candidates are remotes where
        `serves_host(host)`. Exactly one required. Zero → `NoHostRemoteError`.
        More than one → `AmbiguousHostRemoteError` listing the remote names.
- [ ] `serves_host` is passed in as a callable, not imported from `github_cli` —
      selection must stay host-agnostic.
- [ ] Effort: 3

### Task D.3 — Test: enumeration and selection

- [ ] `tests/codehost/test_remotes.py`, against the fake runner.
- [ ] URL parsing: all three shapes, with and without `.git`, over **both**
      `github.com` and `ghe.corp.example`.
- [ ] An unparseable remote URL yields `host=None` and is skipped as a candidate
      **and** appears by name in the ambiguity message.
- [ ] Fork layout (`origin` fork + `upstream` canonical, both GitHub): explicit
      forms resolve; bare forms raise `AmbiguousHostRemoteError` whose message
      contains **both remote names** (the design names the message content as the
      deliverable here).
- [ ] One GitHub remote + one non-GitHub mirror: bare forms **resolve**. This is
      why `serves_host` exists; it is the case a naive "exactly one remote" rule
      gets wrong.
- [ ] `repo#n` with the same repository name under two owners →
      `AmbiguousHostRemoteError`.
- [ ] A target naming a repository no remote points at → `ForeignRepositoryError`
      naming both sides.
- [ ] Two remotes for one repository → first in `git remote` order, INFO logged.
- [ ] Effort: 3

### Task D.4 — Commit

- [ ] `uv run pytest tests/codehost -q`; ruff; pyright.
- [ ] Commit: `feat(codehost): add remote enumeration and target-to-remote selection`
- [ ] Effort: 1

---

## Part E — `gh` Config Reading and Doctor Checks

### Task E.1 — `github_config.py`

- [ ] Create `src/squadron/codehost/github_config.py`. **No subprocess** in this
      module.
- [ ] `gh_hosts_file_path()`: `$GH_CONFIG_DIR/hosts.yml` when `GH_CONFIG_DIR` is
      set, else `~/.config/gh/hosts.yml`.
- [ ] `read_gh_hosts()`: top-level keys of that YAML file via `pyyaml`
      (`pyyaml>=6.0`, already a dependency — [pyproject.toml:34](pyproject.toml#L34)).
      Missing file, unreadable file, or malformed YAML yields an empty set, not a
      raise — absence of `gh` config is a normal state, and the adapter reports
      auth failures at invocation instead.
- [ ] Use `yaml.safe_load`, never `yaml.load`.
- [ ] Effort: 2

### Task E.2 — The two doctor checks

- [ ] Add to [doctor_checks.py](src/squadron/cli/commands/doctor_checks.py),
      following `check_codex_cli`
      ([:266-285](src/squadron/cli/commands/doctor_checks.py#L266-L285)) exactly —
      same `CheckResult` shape, `section=SECTION_INTEGRATIONS`, `required=False`.
      A squadron install without PR workflows is complete.
- [ ] `check_github_cli()`: `shutil.which("gh")`. OK with the path; WARN "not on
      PATH" with a module-level install-hint constant (`brew install gh`, or
      `https://cli.github.com`). Define the hint **once** as a constant, matching
      how the neighbours inline theirs only because they are single-use — this one
      is named in the design, so name it.
- [ ] `check_github_cli_hosts_file()`: OK when the path from `gh_hosts_file_path()`
      exists and `os.access(path, os.R_OK)`; WARN "missing" with hint
      `gh auth login`; WARN "not readable" with the path. **The file is not parsed
      by doctor.**
- [ ] Register both in `run_all_checks` via `_run`, **after** the existing CLI
      presence checks at
      [:508-509](src/squadron/cli/commands/doctor_checks.py#L508-L509).
- [ ] Effort: 2

### Task E.3 — Test: doctor rows

- [ ] Extend [tests/cli/test_doctor_checks.py](tests/cli/test_doctor_checks.py).
- [ ] `gh` present → OK row carrying the path; absent → WARN with the install hint;
      `sq doctor` still **exits 0** because the check is not required.
- [ ] Hosts file present and readable → OK; missing → WARN with the `gh auth login`
      hint; present but unreadable → WARN naming the path. Use `tmp_path` plus
      `GH_CONFIG_DIR` rather than touching the real `~/.config/gh`.
- [ ] `read_gh_hosts` on a malformed YAML file returns an empty set and does not
      raise.
- [ ] Effort: 2

### Task E.4 — Commit

- [ ] `uv run pytest tests/cli tests/codehost -q`; ruff; pyright.
- [ ] Commit: `feat(doctor): add gh CLI and hosts-file presence checks`
- [ ] Effort: 1

---

**Parts F–I continue in
[381-tasks.code-host-adapter-and-pr-target-resolution-2.md](project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md)**
— GitHub reads, fetch and range, writes and CLI, live evidence and closeout. The
Context Summary, code anchors, corrections, coordination, and standing
constraints above govern both files.
