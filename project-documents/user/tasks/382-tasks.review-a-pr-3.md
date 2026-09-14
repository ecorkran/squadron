---
docType: tasks
slice: review-a-pr
project: squadron
lld: project-documents/user/slices/382-slice.review-a-pr.md
dependencies: [381, 916, 904, 918]
projectState: "Files 1-2 land convention_root, the settings override, the worktree lifecycle, and the PR-metadata block. This file assembles sq review pr."
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Tasks: Review a PR (3 of 3)

Continues
[382-tasks.review-a-pr-1.md](project-documents/user/tasks/382-tasks.review-a-pr-1.md)
and
[382-tasks.review-a-pr-2.md](project-documents/user/tasks/382-tasks.review-a-pr-2.md),
which hold the Context Summary, verified code anchors, corrections against
the design, and the standing constraints. All of those govern the parts
below; read those files first.

Files 1–2 built every piece in isolation: `convention_root` and the settings
override (security-critical, landed first), the scratch-worktree lifecycle,
the PR-metadata block, and the `--files` intersection helper. This file wires
them into `sq review pr <target>` and closes the slice.

## Part F — `_warn_not_persistable`'s Reason Parameter (D6)

A small, isolated change ahead of the subcommand that needs it.

### Task F.1 — Add a `reason` parameter

- [ ] In [review.py](src/squadron/cli/commands/review.py), give
      `_warn_not_persistable` ([review.py:286](src/squadron/cli/commands/review.py#L286))
      a `reason: str` parameter, replacing the hardcoded "no slice
      identifier" text in its message with the passed-in reason.
- [ ] Update its one existing call site
      ([review.py:327](src/squadron/cli/commands/review.py#L327), inside
      `_resolve_save_outcome`) to pass `"no slice identifier"` — the
      existing wording, unchanged output for every current caller.
- [ ] `_resolve_save_outcome` itself gains a `not_persistable_reason: str`
      parameter (default matching today's wording) so callers can override
      it without duplicating the outcome-resolution logic.
- [ ] Effort: 1

### Task F.2 — Test: existing wording unchanged, new wording reachable

- [ ] Existing tests exercising `_warn_not_persistable`/
      `_resolve_save_outcome` (e.g. within `tests/cli/test_cli_review.py` or
      wherever slice-less `sq review code` is tested) pass unchanged.
- [ ] Add a case passing a custom reason string and asserting it appears in
      the warning.
- [ ] Effort: 1

### Task F.3 — Commit

- [ ] `uv run pytest tests/cli -q`; ruff; pyright.
- [ ] Commit: `refactor(cli): parameterize the not-persistable warning's reason`
- [ ] Effort: 1

---

## Part G — `sq review pr <target>`

Ties together 381's boundary, file 1's worktree and convention-root split,
and file 2's PR block. D2 (no range split needed) and D5 (tools decide which
tree) are implemented here, not as separate library code — they are choices
inside this command.

### Task G.1 — Resolve target, fetch range, assemble the PR-metadata string

- [ ] `review.py` is already at 1263 lines (well past the project's
      ~300-line source guideline), and this task adds a full subcommand plus
      its helpers. Add `review_pr` and its supporting functions to a new
      sibling module (e.g. `review_pr.py`) rather than growing `review.py`
      further; register its Typer command on the existing `review_app` from
      there. A full extraction of `review.py`'s other commands is out of
      scope for this slice — only the new code goes in the new module.
- [ ] Resolve `target` via `parse_target` → `list_remotes` → `select_remote`
      → `host.resolve_pull_request` → `host.fetch_pull_request_refs`,
      reusing the exact sequence `pr.py`'s `show` command already
      establishes ([pr.py:34-56](src/squadron/cli/commands/pr.py#L34-L56)).
      Do not duplicate this sequence as a second implementation — factor it
      into a shared helper both `pr show` and `review pr` call, so 381's
      command and this one stay provably identical up to the point their
      behavior diverges.
- [ ] Assemble the PR-metadata string from `ResolvedPullRequest` (title,
      body, `linked_issue_numbers`) and `list_unresolved_discussions` (path,
      line, author, body) — the CLI assembles raw content; `_pr_block`
      (file 2, Task D.3) does the fencing. Do not pre-render or pre-fence
      here.
- [ ] Effort: 3

### Task G.2 — Tools-decide-the-tree branch (D5)

- [ ] When tools are enabled (`not no_tools`, mirroring `review_code`'s own
      `no_tools` flag): call `sweep_orphans` then enter a `ScratchWorktree`
      context manager (file 1, Part C) keyed by the resolved
      `PullRequestRecord` and a fresh `run_id` (e.g. `uuid4().hex[:8]`).
      Inside the `with` block:
      - [ ] `inputs["cwd"] = <worktree path>` (the jail root and diff root —
            D2 established either root resolves the range correctly, so no
            special-casing is needed here).
      - [ ] Pass `convention_root=<checkout path>` and
            `setting_sources_override=[]` to `run_review_with_profile` (via
            whatever call path `_execute_review`/`_run_review_command` uses —
            these two functions need the same two new parameters threaded
            through them, mirroring how `no_tools` already threads through
            today).
- [ ] When tools are disabled (`--no-tools`): no worktree is created.
      `inputs["cwd"]` is the checkout; `convention_root` is omitted (`None`,
      same value, no split needed since there is only one root);
      `setting_sources_override` is still `[]` — D8's isolation applies
      regardless of whether tools are enabled, since the SDK's own project
      settings resolution is not gated by the tool flag.
- [ ] Both roots (checkout, and worktree path if one was created) are
      reported alongside the result — extend `ReviewResult` or the terminal
      display (whichever the design's "both roots are reported with the
      result" criterion is best satisfied by — check `ReviewResult`'s
      current fields before adding new ones, and prefer a display-layer
      addition over a model change if the model would otherwise need a
      speculative field 383 doesn't yet define).
- [ ] Effort: 4

### Task G.3 — Diff range, scope assertion, and `--files` intersection

- [ ] `inputs["diff"] = fetched.diff_range` (the three-dot merge-base range
      from 381). No normalization call — 381's fetch already produced the
      correct form; do not run `normalize_diff_spec` a second time.
- [ ] `assert_reviewable_scope(diff, checkout_cwd, exclude_patterns)` — D2:
      always against the checkout, regardless of whether a worktree exists,
      since the ref store is shared across worktrees.
- [ ] When `--files` is supplied, call `intersect_files_with_range` (file 2,
      Task E.1) with `fetched.changed_paths`, and set
      `inputs["files"]` to the intersected result (or however
      `code_review_prompt` expects the `files` input shaped — check whether
      it wants a glob string or a resolved list, and adapt the intersection
      helper's return or this call site so the existing builder code path
      is not forked).
- [ ] Effort: 2

### Task G.4 — Flag parity and command registration

- [ ] `sq review pr <target> [--cwd] [--model] [--profile] [--no-tools]
      [--rules] [--rules-dir] [--no-rules] [--files] [-v] [--output]
      [--output-path] [--json] [--no-save]` — same flags, same help text
      style as `review_code`
      ([review.py:985-1015](src/squadron/cli/commands/review.py#L985-L1015)).
      Omit `--fan` (reserved, not part of this slice's scope) and the
      positional `slice_number` (a PR target replaces it).
- [ ] `--cwd` resolves the **checkout** via `resolve_repo_cwd` (the shared
      helper 381 built,
      [cwd_resolution.py](src/squadron/cli/commands/cwd_resolution.py)) — the
      worktree path is never operator-supplied.
- [ ] Register under the existing `pr_app`
      ([pr.py](src/squadron/cli/commands/pr.py)) as `sq pr review`, **or**
      under `review_app` as `sq review pr` — the design names it
      `sq review pr <target>` throughout; register it there, on
      `review_app`, not on `pr_app`. Do not register it twice.
- [ ] On completion, call `_resolve_save_outcome` with
      `not_persistable_reason="PR review persistence is not yet
      available (383)"` (Part F) — `target` is always `None` on this path
      until 383 lands, so every `sq review pr` run reports this warning by
      design; that is correct, not a bug to fix here.
- [ ] Every `CodeHostError` from resolution/fetch is caught the same way
      `pr show` catches it — message and fix hint to stderr, exit 1.
- [ ] Effort: 3

### Task G.5 — Test: flag parity table

- [ ] Create `tests/cli/test_review_pr.py`, monkeypatching
      `build_github_host` the same way `tests/cli/test_pr_show.py` does
      (381's established seam — do not invent a second one).
- [ ] Table-driven: each of `--model`, `--profile`, `--no-tools`, `--rules`,
      `--rules-dir`, `--no-rules`, `--files`, `-v`/`-vv`, `--output`,
      `--json`, `--no-save` behaves on `sq review pr` as the equivalent
      existing test asserts for `sq review code` — reuse or mirror those
      existing cases rather than inventing new assertions.
- [ ] Not-persistable warning names PR persistence specifically (not the
      generic "no slice identifier" text).
- [ ] `--files` intersection: a glob matching some of the range's changed
      paths narrows to the intersection; a glob matching none raises naming
      both.
- [ ] Effort: 3

### Task G.6 — Test: worktree integration through the command

- [ ] With tools enabled: the review's prompt (captured at `-vvv`, or via
      whatever seam `test_pr_settings_isolation.py` established in file 1)
      shows `cwd` pointing at a worktree path distinct from the checkout,
      and the injected `CLAUDE.md` content matching the **checkout's**
      version even when a differing one is planted in the worktree — the
      design's "PR that edits the rules directory or CLAUDE.md is reviewed
      against the checkout's versions" criterion.
- [ ] With `--no-tools`: no `ScratchWorktree` is entered (assert via a spy or
      by confirming no `git worktree add` call appears in the fake runner's
      recorded calls) and the review still completes using the checkout
      alone.
- [ ] Two concurrent `sq review pr` invocations against the same target (run
      sequentially in the test but with distinct `run_id`s forced, or
      genuinely concurrently if the test harness supports it) produce
      distinct worktree paths and both complete.
- [ ] The operator's checkout is confirmed unchanged
      (`git status --porcelain`, `git for-each-ref refs/heads`) before and
      after a run that raises mid-review (force a failure via the fake
      runner) — the design's forced-failure criterion.
- [ ] Effort: 3

### Task G.7 — Commit Part G

- [ ] Run `uv run pytest -q`. **Full suite** — this registers a new command
      path and touches shared functions (`_warn_not_persistable`,
      `run_review_with_profile`) that other tests exercise.
- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(cli): add sq review pr over the code-host adapter and scratch worktree`
- [ ] Effort: 1

---

## Part H — Live Evidence and Closeout

### Task H.1 — Live verification walkthrough

- [ ] Run in a clone of `ecorkran/squadron` with `gh` authenticated, against
      an open PR (check `gh pr list --state open --limit 5` first — 381's
      live run found none open on 20260913; re-derive at execution time,
      per the design's Verification Walkthrough).
- [ ] Follow the design's six numbered steps exactly
      ([382-slice.review-a-pr.md, Verification Walkthrough](project-documents/user/slices/382-slice.review-a-pr.md)):
      before/after checkout state, `sq review pr <n> -v` then
      `--no-tools`, confirm nothing moved and no worktree leaked, orphan
      sweep (kill mid-run, confirm sweep on next invocation), containment
      (a PR body with a fence and the block's own label), and D8's settings
      isolation (plant a `PreToolUse` hook via a scratch PR, confirm no
      sentinel, confirm `sq review code` still loads project settings).
- [ ] Record each step's actual output, not a paraphrase — the design
      requires steps 3, 4, and 6 recorded in the DEVLOG entry that closes
      this slice.
- [ ] Effort: 3

### Task H.2 — Success criteria sweep

- [ ] Walk the design's Functional and Technical criteria
      (`382-slice.review-a-pr.md`, Success Criteria section) one by one,
      confirming each is demonstrated by a specific test (name it) or by
      H.1's recorded live run. Do not mark a criterion satisfied without
      naming its evidence.
- [ ] Confirm `ruff format`, `ruff check`, and `pyright` are clean across the
      whole slice's changes, not only the most recent commit.
- [ ] Confirm no module under `review/` imports `squadron.codehost` — the
      existing import-graph test, still passing with `worktree.py` added.
- [ ] Effort: 2

### Task H.3 — Documentation and closeout

- [ ] DEVLOG entry per `prompt.ai-project.system.md`, "Session State
      Summary", including H.1's recorded steps 3, 4, and 6.
- [ ] CHANGELOG: one short user-facing line for `sq review pr`. Technical
      detail (the two-root split, the settings override, the worktree
      lifecycle) belongs in the DEVLOG, not here.
- [ ] Mark this task file (and files 1–2) `status: complete`, set
      `dateUpdated`, and mark the slice complete in
      [382-slice.review-a-pr.md](project-documents/user/slices/382-slice.review-a-pr.md)
      and in the slice plan
      [380-slices.pull-request-workflow.md](project-documents/user/architecture/380-slices.pull-request-workflow.md).
- [ ] Merge the slice branch (`382-slice.review-a-pr`) into `squadron-pr`
      (the configured `git.integration_branch`). **Never to `main`.**
- [ ] Effort: 2

---

## Coverage Check

Every design decision maps to a task above: D1 → Part A (file 1); D2 → Task
G.1/G.3 (no separate library code, a command-level choice); D3 → Part C
(file 1); D4 → Part D (file 2); D5 → Task G.2; D6 → Part F; D7 → Part E
(file 2); D8 → Part A (file 1), Task A.4–A.5. Excluded per the design's scope
(persistence, posting, PR creation, slash-command parity, pipeline PR
targets) has no task here by design.
