---
docType: tasks
slice: review-a-pr
project: squadron
lld: project-documents/user/slices/382-slice.review-a-pr.md
dependencies: [381, 916, 904, 918]
projectState: "381 (code-host adapter) and 918 (jail exclusions, telemetry) are merged. This slice spends 381's boundary on sq review pr."
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Tasks: Review a PR (1 of 3)

## Context Summary

381 built a code-host adapter: a target resolves to a `ResolvedPullRequest` and a
`FetchedRange` whose `diff_range` is a merge-base range over two namespaced refs
squadron just fetched. This slice spends that boundary on the initiative's
headline capability — `sq review pr <target>` — by handing the range and PR
record to the existing code review rather than building a second reviewer.

Three things make it more than wiring, and this file (1 of 3) covers the two
that are security- and correctness-critical:

- **D8 first, before anything else exists.** The PR path's tool jail is a
  scratch worktree containing a stranger's code. The Agent SDK resolves
  project settings — including `PreToolUse` shell hooks, which neither
  `permission_mode` nor `allowed_tools` constrains — from that worktree unless
  told not to. This file adds the override and its isolation test **before**
  the worktree exists, so no window opens where the two could combine.
- **D1, the two-root split.** `AgentConfig.cwd` today answers three questions
  at once (jail root, `tools.materialize` root, `_inject_file_contents`'s
  `CLAUDE.md` source). A second field, `convention_root`, lets code come from
  the worktree while conventions keep coming from the trusted checkout.
- **D3, the scratch-worktree lifecycle** — create, lock, sweep orphans, remove
  on every exit path, with submodule init bounded and a malformed lock treated
  as an orphan rather than an exception.

Files 2 and 3 continue with the PR-metadata block (D4), the `pr` subcommand
(D2, D5–D7), flag parity, and closeout. Read this file first — its anchors,
corrections, and standing constraints govern all three.

Nothing in this slice touches `sq review code`'s behavior; its existing tests
must pass unchanged throughout.

### Verified code anchors (traced on `a43d6ec8`, 20260913)

| Anchor | Location |
|---|---|
| `AgentConfig` — `cwd`, `setting_sources`, `tool_exclude_patterns` already exist; `convention_root` does not | [models.py:40-79](src/squadron/core/models.py#L40-L79) |
| `ClaudeSDKProvider.create_agent` — builds `ClaudeAgentOptions`, reads `config.cwd`/`config.setting_sources` | [sdk/provider.py:39-90](src/squadron/providers/sdk/provider.py#L39-L90) |
| `OpenAICompatibleProvider.create_agent` — passes `config.cwd` to the agent for `tools.materialize` | [openai/provider.py:37-81](src/squadron/providers/openai/provider.py#L37-L81) |
| `run_review_with_profile` — builds `AgentConfig` internally from `inputs` dict; no `convention_root`/override params yet | [review_client.py:60-201](src/squadron/review/review_client.py#L60-L201) |
| `_inject_file_contents` — reads `CLAUDE.md` from `inputs["cwd"]`, not a separate root | [review_client.py:343-451](src/squadron/review/review_client.py#L343-L451) |
| `_SKIP_KEYS` | [review_client.py:312](src/squadron/review/review_client.py#L312) |
| `code.yaml` — `setting_sources: [project]`, no `tool_exclude_patterns` (918, deliberate) | [code.yaml](src/squadron/data/templates/code.yaml) |
| `codehost/refs.py` — `GIT_FETCH_TIMEOUT_SECONDS = 300`, `GIT_QUERY_TIMEOUT_SECONDS = 30` (reuse, do not redefine) | [refs.py:28-31](src/squadron/codehost/refs.py#L28-L31) |
| `_config_dir()` — `~/.config/squadron/`, migrates from `~/.config/orchestration/` | [config/manager.py:18-27](src/squadron/config/manager.py#L18-L27) |
| `ProcessRunner` protocol, `ProcessTimedOutError`, `ProcessNotFoundError` | [core/process_runner.py](src/squadron/core/process_runner.py) |
| `FakeProcessRunner` — scripted `(argv_prefix, ProcessResult \| Exception)`, unscripted argv raises | [tests/codehost/fake_runner.py](tests/codehost/fake_runner.py) |
| `codehost/__init__.py` — package re-export contract this slice must extend | [codehost/__init__.py](src/squadron/codehost/__init__.py) |
| `pr_app` registration, `pr.py` command pattern (381 precedent for D2's CLI shape) | [pr.py](src/squadron/cli/commands/pr.py) |
| `resolve_repo_cwd`, `resolve_cwd` — shared cwd helper (Part A.5 of 381) | [cwd_resolution.py](src/squadron/cli/commands/cwd_resolution.py) |
| `resolve_effective_tools` | [tools/effective.py:38](src/squadron/tools/effective.py#L38) |
| `_warn_not_persistable(review_type)` — takes only a type string today; D6 needs a reason | [review.py:286-303](src/squadron/cli/commands/review.py#L286-L303) |
| `_run_review_command` / `_execute_review` — the call path `pr.py` will reuse | [review.py:538-684](src/squadron/cli/commands/review.py#L538-L684) |
| Existing `tests/codehost/` and `tests/review/` package layout | see directory listings below |

Confirmed absent at task-writing time (genuinely new, create them):
`src/squadron/codehost/worktree.py`, `tests/codehost/test_worktree.py`,
`tests/review/test_pr_settings_isolation.py`,
`tests/review/test_convention_root.py`,
`tests/review/test_code_builder_pr_block.py`, `tests/cli/test_review_pr.py`.

### Corrections against the design

One design statement needs a sharper implementation note than the design
gives it — recorded here rather than as a design amendment because it
narrows an implementation choice, not a decision.

| Design text | Finding | Disposition |
|---|---|---|
| D1/D8: "`convention_root`... threaded `inputs` → `AgentConfig`" and "the PR path overrides [`setting_sources`] per invocation" | `run_review_with_profile` takes an `inputs: dict[str, str]` and builds `AgentConfig` internally ([review_client.py:60](src/squadron/review/review_client.py#L60)); there is no existing parameter for a caller to hand it a convention root or a settings override directly. The design's data-flow diagram shows `AgentConfig(cwd=review_root, convention_root=checkout)` as if the caller constructs it, which it does not. | `run_review_with_profile` gains two new keyword-only parameters, `convention_root: str \| None = None` and `setting_sources_override: list[str] \| None = None`, both defaulting to preserve today's behavior exactly. It threads them into the `AgentConfig` it already builds and passes `convention_root` to `_inject_file_contents`. This is the mechanism the design's diagram assumed; Task 1.1 below states it explicitly so no implementer has to invent it. |

### Standing constraints (govern all three files)

- Every failure path raises a typed error, logs once at WARNING or ERROR with
  structured fields before raising, and exits 1 through the CLI. No silent
  path (Failure-Mode Enumeration rule).
- No test asserts on user-facing message *text* as logical structure except
  where the design or a task names message content as the deliverable (e.g.
  the settings-isolation test's sentinel-file assertion).
- Timeouts are module constants, never inlined literals. Reuse
  `GIT_FETCH_TIMEOUT_SECONDS` and `GIT_QUERY_TIMEOUT_SECONDS` from
  `codehost/refs.py` — do not redefine them in `worktree.py`.
- No module under `codehost/` imports `squadron.review`, `squadron.cli`,
  `squadron.pipeline`, or `squadron.providers`. No module under `review/`
  imports `squadron.codehost` (existing import-graph test, extended here).
- `ruff format`, `ruff check`, `pyright` clean before every commit; zero
  pyright errors is a merge blocker.
- `sq review code`'s existing tests pass unchanged after every task in this
  slice. Several tasks below say so explicitly at the points of highest risk;
  the constraint holds throughout.

---

## Part A — The Two-Root Split and the Settings Override

Sequenced first per the design's Implementation Notes: "before the worktree
exists, so no branch can ever reach the SDK with the worktree as `cwd` and the
template's `[project]` still in force." The isolation test is written before
its own fix, so it fails against the un-overridden path first.

### Task A.1 — `AgentConfig.convention_root`

- [ ] In [models.py](src/squadron/core/models.py), add
      `convention_root: str | None = None` beside `cwd`
      ([models.py:64](src/squadron/core/models.py#L64)), with a comment: `None`
      means "same as `cwd`" — today's behavior for every existing caller.
- [ ] Do not thread it into `OpenAICompatibleAgent` or `tools.materialize` —
      D1 states only `_inject_file_contents` consumes it. The non-SDK path's
      jail root stays `cwd` alone.
- [ ] Effort: 1

### Task A.2 — Thread `convention_root` through `run_review_with_profile`

- [ ] In [review_client.py](src/squadron/review/review_client.py), add a
      keyword-only parameter `convention_root: str | None = None` to
      `run_review_with_profile` ([review_client.py:60](src/squadron/review/review_client.py#L60)).
      See Corrections table above — this is the mechanism the design's data
      flow diagram assumed but did not name.
- [ ] Pass it to the `AgentConfig(...)` construction
      ([review_client.py:180](src/squadron/review/review_client.py#L180)) as
      `convention_root=convention_root`.
- [ ] Pass it to `_inject_file_contents` as a new keyword-only parameter
      `convention_root: str | None = None`
      ([review_client.py:343](src/squadron/review/review_client.py#L343)); inside,
      use `convention_root if convention_root is not None else inputs.get("cwd", ".")`
      as the directory the `CLAUDE.md` candidates are resolved against
      ([review_client.py:438](src/squadron/review/review_client.py#L438)), replacing
      today's `cwd_for_claude = inputs.get("cwd", ".")`.
- [ ] No other call site changes. `sq review code` and every other existing
      caller of `run_review_with_profile` omits the new parameter and gets
      `None`, which resolves to exactly today's `cwd`-sourced behavior.
- [ ] Effort: 2

### Task A.3 — Test: convention root is honored, and existing behavior is byte-identical

- [ ] Create `tests/review/test_convention_root.py`.
- [ ] A run with `convention_root` set to a directory whose `CLAUDE.md`
      differs from the one at `inputs["cwd"]` injects the **convention root's**
      content into the prompt, not the cwd's.
- [ ] A run that omits `convention_root` entirely produces a byte-identical
      prompt to the same run before this task's changes existed — pin this
      against a fixture captured from the current `test_content_injection.py`
      or `test_review_client.py` cases, whichever already covers
      `CLAUDE.md` injection.
- [ ] Run `uv run pytest tests/review -q` — full existing suite green,
      confirming A.1–A.2 changed no observable behavior for any caller that
      does not pass the new parameter.
- [ ] Effort: 2

### Task A.4 — `setting_sources_override` on `run_review_with_profile`

- [ ] Add a second keyword-only parameter,
      `setting_sources_override: list[str] | None = None`.
- [ ] When not `None`, it replaces `template.setting_sources` in the
      `AgentConfig` construction
      ([review_client.py:186](src/squadron/review/review_client.py#L186)) —
      i.e. `setting_sources=(setting_sources_override if setting_sources_override is not None else template.setting_sources)`.
      `None` (the default) preserves today's template-only behavior exactly,
      including for `sq review code`, whose `code.yaml` sets `[project]`.
- [ ] Do **not** edit `code.yaml`. Design D8: the safe value depends on what
      is being reviewed, not on the template, so the template's `[project]`
      must survive for the code path.
- [ ] Add the environment variable
      `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` to the agent's environment whenever
      `setting_sources_override == []`. `ClaudeAgentOptions` has a direct
      `env: dict[str, str]` field (confirmed in the installed
      `claude_agent_sdk` package) — set `kwargs["env"] = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}`
      in `ClaudeSDKProvider.create_agent`
      ([sdk/provider.py:39](src/squadron/providers/sdk/provider.py#L39)),
      merged with any existing `env` entries rather than overwriting them if
      `create_agent` ever gains another `env` source later.
- [ ] Effort: 3

### Task A.5 — Test: the isolation test, written to fail first

- [ ] Create `tests/review/test_pr_settings_isolation.py`.
- [ ] **Write this test before Task A.4's production code**, or if A.4 is
      already merged when this task starts, temporarily revert it, run the
      test, confirm it fails, then restore A.4. The design requires the test
      prove it would have caught the un-overridden path — recording that it
      failed first is the evidence.
- [ ] Plant a `.claude/settings.json` in a temp directory declaring a
      `PreToolUse` hook whose command writes a sentinel file (e.g.
      `touch sentinel.txt`) into a second temp location.
- [ ] Call `run_review_with_profile` with `cwd` set to the directory carrying
      the settings file and `setting_sources_override=[]`. Assert:
      - [ ] the constructed `AgentConfig` (or the `ClaudeAgentOptions` built
            from it) carries `setting_sources=[]`.
      - [ ] the environment passed to the agent carries
            `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
      - [ ] the sentinel file does not exist after the run.
- [ ] A second case in the same file: the same setup **without** the
      override (`setting_sources_override=None`, template default in force)
      still passes `[project]` through — this is `sq review code`'s existing
      path and must be pinned so the fix does not silently spread to it.
- [ ] Stub the SDK boundary the way
      `tests/review/test_template_sdk_regression.py` does: patch
      `"squadron.providers.sdk.agent.ClaudeSDKAgent"` (that file's
      `_AGENT_PATCH` constant) with `create=True`, and assert against the
      `ClaudeAgentOptions`/`AgentConfig` the mock was constructed or called
      with — do not invent a second stubbing seam.
- [ ] Effort: 3

### Task A.6 — Commit Part A

- [ ] Run `uv run pytest tests/review tests/core -q`. All green.
- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(review): add convention_root and per-invocation settings override`
- [ ] Effort: 1

---

## Part B — `_SKIP_KEYS` Extended for the PR Input

The `pr` input key does not exist yet (that lands in file 2's Part C), but
`_SKIP_KEYS` is a one-line, low-risk change with no dependency on the rest of
this slice, and D4 depends on it being in place before the PR block ever
reaches `_inject_file_contents`. Doing it here keeps Part A's file focused on
the security-critical work while not blocking file 2 on this file's review.

### Task B.1 — Add `pr` to `_SKIP_KEYS`

- [ ] In [review_client.py:312](src/squadron/review/review_client.py#L312),
      add `"pr"` to `_SKIP_KEYS`. Comment: a `pr` input value is rendered
      text from the builder (D4), never a file path; without this,
      `_inject_file_contents`'s "is this a real path" check could read a
      real file named inside a PR body off disk and inject it (Scope
      corrections table, design row 3).
- [ ] Effort: 1

### Task B.2 — Test: `pr` key is never treated as a path

- [ ] In `tests/review/test_content_injection.py` (or wherever `_SKIP_KEYS`
      is currently tested — check first), add a case: an `inputs["pr"]`
      value that happens to be a real, readable file path on disk is **not**
      injected as a file body.
- [ ] Effort: 1

### Task B.3 — Commit

- [ ] `uv run pytest tests/review -q`; ruff; pyright.
- [ ] Commit: `feat(review): exclude pr input key from file-path injection`
- [ ] Effort: 1

---

## Part C — Scratch Worktree Lifecycle

Design D3. Built and tested standalone against the fake runner — nothing here
depends on the CLI command that will use it (file 2, Part D).

### Task C.1 — `WorktreeError` hierarchy and `lock.json` shape

- [ ] Create `src/squadron/codehost/worktree.py`.
- [ ] `WorktreeError(CodeHostError)` base (reuse `codehost.errors.CodeHostError`
      — do not create a parallel hierarchy). Subclasses:
      `WorktreeCreationError`, `SubmoduleUnfetchableError(submodule_path)`,
      `SubmoduleTimeoutError(submodule_path, seconds)`.
- [ ] `WorktreeLock` frozen dataclass: `pid: int`, `started_at: float` (process
      start time, not lock-write time — a recycled pid must not read as
      alive).
- [ ] Effort: 2

### Task C.2 — `sweep_orphans`

- [ ] `sweep_orphans(runner, root)` where `root` is
      `~/.config/squadron/worktrees/` (via `_config_dir()`-equivalent — reuse
      the pattern at
      [config/manager.py:18-27](src/squadron/config/manager.py#L18-L27); do
      not hardcode `~/.config/squadron` a second time).
- [ ] For each subdirectory: read `lock.json`. Missing, truncated, unparsable
      JSON, or missing `pid`/`started_at` → log **one WARNING** naming the
      path and the reason, treat as orphan, remove via
      `git worktree remove --force` then the directory if anything remains.
      **Never raise** — a parse error escaping this function fails every
      subsequent `sq review pr` (design D3, the rationale for this rule).
- [ ] A present, parseable lock whose `pid` is not alive, or is alive but with
      a different process-start-time than recorded, is also an orphan by the
      same path.
- [ ] A present, parseable lock whose `pid` is alive with a matching start
      time is left alone.
- [ ] After sweeping dead entries, run `git worktree prune` once via the
      runner, bounded by `GIT_QUERY_TIMEOUT_SECONDS` (imported from
      `codehost.refs`, not redefined).
- [ ] Effort: 3

### Task C.3 — `ScratchWorktree` context manager: create

- [ ] `ScratchWorktree(runner, record: PullRequestRecord, run_id: str, root)`
      as a context manager. `__enter__`:
  - [ ] Calls `sweep_orphans` first.
  - [ ] Computes the path:
        `<root>/<host>-<owner>-<repo>-<number>-<run_id>` (record's `key` with
        `/` and `#` flattened to `-`, plus `run_id`).
  - [ ] `git worktree add --detach <path> <head_ref>`, bounded by
        `GIT_QUERY_TIMEOUT_SECONDS` (this is a local ref checkout, not a
        network fetch — 381 already fetched the ref).
  - [ ] Writes `lock.json` with the current pid and its start time
        immediately after the worktree directory exists, before any
        submodule work — the lock must cover the window the sweep is
        protecting against.
  - [ ] A non-zero exit on `worktree add` → `WorktreeCreationError` naming
        the path and the git stderr, logged at ERROR.
- [ ] Effort: 3

### Task C.4 — Submodule init, bounded, two distinct failure modes

- [ ] Inside `__enter__`, after the lock is written: run
      `git submodule update --init --recursive` in the new worktree, bounded
      by `GIT_FETCH_TIMEOUT_SECONDS` (imported from `codehost.refs` — this
      call reaches third-party remotes, the fetch bound applies, not the
      query bound).
- [ ] A non-zero exit (auth failure, submodule gone, unreachable) →
      `SubmoduleUnfetchableError` naming the submodule path, logged at ERROR.
      Determine the specific submodule path from git's own output rather than
      reporting the whole command failed generically.
- [ ] A `ProcessTimedOutError` from the runner →
      `SubmoduleTimeoutError(submodule_path, seconds)`, logged at ERROR
      naming both the submodule and the bound.
- [ ] Either failure removes the worktree (via `__exit__`'s cleanup path,
      Task C.5) before re-raising — no path leaves a half-initialized
      worktree behind.
- [ ] Effort: 3

### Task C.5 — Removal on every exit path

- [ ] `__exit__` removes the worktree unconditionally — success, exception,
      or (via the caller's own timeout handling) a review that ran past a
      bound. `git worktree remove --force <path>`, bounded by
      `GIT_QUERY_TIMEOUT_SECONDS`.
- [ ] A worktree that cannot be removed logs at WARNING naming the path and
      does **not** raise from `__exit__` — swallowing a cleanup failure
      inside a context manager's `__exit__` must not mask the original
      exception, but per design D3 the review's own result still stands, so
      this is the documented exception to "every try/except re-raises":
      comment why.
- [ ] Effort: 2

### Task C.6 — Test: worktree lifecycle

- [ ] Create `tests/codehost/test_worktree.py` against `FakeProcessRunner`
      (imported from `tests/codehost/fake_runner.py`, the existing
      convention — do not create a second fake).
- [ ] Create: happy path produces the expected path, argv, and a written
      `lock.json` with correct `pid`/`started_at` shape.
- [ ] Sweep: a live-owner lock (matching pid + start time, using the current
      test process) is left; a dead-owner lock (pid not alive, or alive with
      a mismatched start time) is swept with one WARNING.
- [ ] Malformed-lock table, one case each: truncated JSON, non-JSON content,
      missing `pid`, missing `started_at`, lock file absent entirely. Each
      asserts one WARNING, treat-as-orphan, and `sweep_orphans` raises
      nothing.
- [ ] Submodule init: a scripted non-zero exit → `SubmoduleUnfetchableError`
      naming the submodule; a scripted `ProcessTimedOutError` →
      `SubmoduleTimeoutError` naming the submodule and the bound; both assert
      the worktree directory is absent afterward.
- [ ] Removal: success, an exception raised inside the `with` block, and a
      scripted `git worktree remove` failure (asserts WARNING, no raise from
      `__exit__`) — all three confirmed via the fake runner's recorded calls
      plus directory-absence checks where a real temp directory is used.
- [ ] Two concurrent `ScratchWorktree` instances for the same PR record (same
      `record`, different `run_id`) produce non-colliding paths.
- [ ] Effort: 4

### Task C.7 — Commit Part C

- [ ] Run `uv run pytest tests/codehost -q`. All green — including 381's
      existing `test_import_boundaries.py`, confirming `worktree.py` adds no
      forbidden import.
- [ ] Add `ScratchWorktree`, `sweep_orphans`, and the new error classes to
      `codehost/__init__.py`'s re-export list (the package contract 382's own
      design names as `Provides`).
- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(codehost): add scratch-worktree lifecycle with orphan sweep`
- [ ] Effort: 1

---

**Continues in
[382-tasks.review-a-pr-2.md](project-documents/user/tasks/382-tasks.review-a-pr-2.md)**
— the PR-metadata block (D4), `code.yaml`'s new input, and the range/scope
decisions (D2, D5, D7) feeding into the `pr` subcommand built in file 3. The
Context Summary, verified anchors, corrections, and standing constraints above
govern all three files.
