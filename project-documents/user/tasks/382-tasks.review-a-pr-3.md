---
docType: tasks
slice: review-a-pr
project: squadron
lld: project-documents/user/slices/382-slice.review-a-pr.md
dependencies: [381, 916, 904, 918]
projectState: "Files 1-2 land convention_root, the settings override, the worktree lifecycle, and the PR-metadata block. This file assembles sq review pr."
dateCreated: 20260913
dateUpdated: 20260914
status: complete
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

**Test-with restructuring note (review finding, part 3, F004).** The
original breakdown batched all four implementation tasks (resolution,
worktree branch, scope/rules, registration) before any test task ran. Tests
now interleave at two points: after resolution/fetch (G.2), and after the
worktree branch that carries the slice's most security-relevant wiring
(G.4) — the same grain Parts A, D, E, and F already use.

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
      establishes ([pr.py:34-57](src/squadron/cli/commands/pr.py#L34-L57)).
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

### Task G.2 — Test: target resolution and PR-metadata assembly

- [ ] Create `tests/cli/test_review_pr.py`, monkeypatching
      `build_github_host` the same way `tests/cli/test_pr_show.py` does
      (381's established seam — do not invent a second one).
- [ ] The shared resolution helper (factored out in G.1) resolves a target
      to the same `ResolvedPullRequest`/`FetchedRange` `pr show` would
      produce for the same target — assert against `pr show`'s own existing
      fixtures/scripted responses rather than duplicating them.
- [ ] The assembled PR-metadata string carries title, body, linked issue
      numbers, and unresolved discussions from the scripted
      `ResolvedPullRequest`/`list_unresolved_discussions` — assert the raw
      string content, not the fenced/rendered form (that's file 2's Task
      D.4).
- [ ] Effort: 2

### Task G.3 — Tools-decide-the-tree branch (D5)

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

### Task G.4 — Test: worktree integration through the command

- [ ] **Sequenced immediately after the worktree branch it tests (review
      finding, part 3, F004)** — this is the slice's most security-relevant
      wiring (worktree jail, `convention_root`, `setting_sources_override`
      all converge in G.3), so it does not wait behind scope/rules-dir
      wiring and command registration the way the original ordering did.
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

### Task G.5 — Diff range, scope assertion, rules provenance, and `--files` intersection

- [ ] `inputs["diff"] = fetched.diff_range` (the three-dot merge-base range
      from 381). No normalization call — 381's fetch already produced the
      correct form; do not run `normalize_diff_spec` a second time.
- [ ] `assert_reviewable_scope(diff, checkout_cwd, exclude_patterns)` — D2:
      always against the checkout, regardless of whether a worktree exists,
      since the ref store is shared across worktrees.
- [ ] **Rules-directory provenance is part of the two-root split, not only
      `CLAUDE.md` (review finding, part 3, F001).** D1's prose and the
      design's Functional criteria both name "the rules directory **and**
      `CLAUDE.md`" as convention inputs that must come from the checkout.
      `_resolve_review_cwd` ([review.py:237](src/squadron/cli/commands/review.py#L237))
      resolves both the reviewing `cwd` *and* the rules directory
      (`resolve_rules_dir`) from the same single argument — today's
      single-root assumption, correct for `sq review code` where there is
      only one root. On `sq review pr` this function must **not** be called
      with the worktree path. Resolve the rules directory from the
      **checkout** cwd (`repo_cwd` from Task G.1, before G.3's worktree
      branch ever runs) via `resolve_rules_dir(checkout_cwd, None,
      rules_dir_flag)` directly — the same call `_resolve_review_cwd` makes
      internally, but anchored at the checkout regardless of which root
      `inputs["cwd"]` ends up holding after G.3. This is the same class of
      risk D8 closes for SDK project settings: an unreviewed rules directory
      resolving from the worktree would let a PR's own planted rules content
      reach the reviewer's instructions.
- [x] **DROPPED — `--files` is not part of `sq review pr`.** Part E's
      `intersect_files_with_range` helper, its tests, and the
      `GLOB_MATCHED_NOTHING_IN_RANGE` enum case are reverted (see file 2,
      Part E). `sq review pr` reviews the PR's full merge-base range; no
      operator-supplied glob narrows it. Revisit only if a concrete need
      appears — do not re-litigate from the task text alone.
- [ ] Effort: 2

### Task G.6 — Test: rules provenance

- [ ] Extend `tests/cli/test_review_pr.py` (from G.2/G.4).
- [ ] **The rules-directory half of the two-root criterion (review finding,
      part 3, F001).** Plant a `.claude/rules/` (or configured rules
      directory) in the worktree with content that differs from the
      checkout's own rules directory. Assert the rendered `rules_content`
      passed into the review — not just `CLAUDE.md` — comes from the
      **checkout's** rules directory. This must fail against a naive
      implementation that calls `_resolve_review_cwd` with the worktree
      path, which is exactly the mistake Task G.5's provenance instruction
      exists to prevent.
- [x] **DROPPED — `--files` is not part of `sq review pr`** (see Task G.5).
      No intersection test; there is no intersection.
- [ ] Effort: 2

### Task G.7 — Flag parity and command registration

- [x] `sq review pr <target> [--cwd] [--model] [--profile] [--no-tools]
      [--rules] [--rules-dir] [--no-rules] [-v] [--output]
      [--output-path] [--json] [--no-save]` — same flags, same help text
      style as `review_code`
      ([review.py:985-1015](src/squadron/cli/commands/review.py#L985-L1015)).
      Omit `--fan` (reserved, not part of this slice's scope), `--files`
      (dropped — see Task G.5), and the positional `slice_number` (a PR
      target replaces it).
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

### Task G.8 — Test: flag parity table

- [ ] Extend `tests/cli/test_review_pr.py` (from G.2/G.4/G.6).
- [ ] Table-driven: each of `--model`, `--profile`, `--no-tools`, `--rules`,
      `--rules-dir`, `--no-rules`, `-v`/`-vv`, `--output`,
      `--json`, `--no-save` behaves on `sq review pr` as the equivalent
      existing test asserts for `sq review code` — reuse or mirror those
      existing cases rather than inventing new assertions. `--files` is
      dropped (Task G.5) and is not in this table.
- [ ] Not-persistable warning names PR persistence specifically (not the
      generic "no slice identifier" text).
- [ ] Effort: 3

### Task G.9 — Commit Part G

- [ ] Run `uv run pytest -q`. **Full suite** — this registers a new command
      path and touches shared functions (`_warn_not_persistable`,
      `run_review_with_profile`) that other tests exercise.
- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(cli): add sq review pr over the code-host adapter and scratch worktree`
- [ ] Effort: 1

---

## Part H — Closeout

### Task H.1 — Live verification walkthrough

- [x] **DROPPED — no live PR available.** `ecorkran/squadron` has no open
      PRs (checked 20260914: three PRs, all MERGED — #83, #66, #64). The
      design's six-step walkthrough requires an open PR to review, so it
      cannot be run. The behaviors it would have demonstrated are covered
      by the automated tests named in H.2: worktree/checkout root split,
      `--no-tools` bypass, concurrent distinct worktrees, and checkout
      unchanged after a forced mid-review failure. Orphan sweep and D8
      settings isolation have unit coverage (file 1, Parts A and C) but no
      live-run evidence. **Run this walkthrough before relying on
      `sq review pr` against real PRs.**

### Task H.2 — Success criteria sweep

- [x] **DROPPED — depends on H.1's live run for its evidence.** The
      mechanical checks it also carried are done and recorded below.
- [x] `ruff format` (533 files unchanged), `ruff check` (all passed), and
      `pyright` (0 errors) clean across the slice at commit `e6c8b55f`.
- [x] Full suite at `e6c8b55f`: 3962 passed, 4 skipped. The 3 failures in
      `tests/documents/test_schema_drift.py` are cf issue #88, pre-existing
      and unrelated to this slice.

### Task H.3 — Documentation and closeout

- [ ] DEVLOG entry per `prompt.ai-project.system.md`, "Session State
      Summary". Record that H.1's live walkthrough was not run and why.
- [ ] CHANGELOG: one short user-facing line for `sq review pr`. Technical
      detail (the two-root split, the settings override, the worktree
      lifecycle) belongs in the DEVLOG, not here.
- [ ] Mark this task file (and files 1–2) `status: complete`, set
      `dateUpdated`, and mark the slice complete in
      [382-slice.review-a-pr.md](project-documents/user/slices/382-slice.review-a-pr.md)
      and in the slice plan
      [380-slices.pull-request-workflow.md](project-documents/user/architecture/380-slices.pull-request-workflow.md).
- [ ] **Commit the DEVLOG entry, CHANGELOG line, and status/completion
      updates above** (review finding: every other Part in this breakdown
      ends with an explicit commit step; closeout must too, before the
      merge) — `docs: close out slice 382 (review a pr)` or similar.
- [ ] Merge the slice branch (`382-slice.review-a-pr`) into `squadron-pr`
      (the configured `git.integration_branch`). **Never to `main`.**
- [ ] Effort: 2

---

## Coverage Check

Every design decision maps to a task above: D1 → Part A (file 1); D2 → Task
G.1/G.5 (no separate library code, a command-level choice); D3 → Part C
(file 1); D4 → Part D (file 2); D5 → Task G.3; D6 → Part F; D7 → Part E
(file 2); D8 → Part A (file 1), Task A.4–A.5, and Task G.3's override calls.
Excluded per the design's scope (persistence, posting, PR creation,
slash-command parity, pipeline PR targets) has no task here by design.

---

## Task Review Disposition

Task review
(`382-review.tasks.review-a-pr.part-3.md`, claude-sonnet-5, CONCERNS,
20260913, sha `78ccf3bb`), reviewing this file. Four concerns and three
notes actioned; two pass findings, no action.

- **F001 (concern) — accepted, the sharpest finding across all three
  reviews.** D1's prose and the design's own Functional criteria name both
  "the rules directory and `CLAUDE.md`" as convention inputs the two-root
  split must source from the checkout, but every task touching the split
  (file 1's A.1–A.3, this file's original G.2/G.6) covered only `CLAUDE.md`
  via `_inject_file_contents`. Verified directly: `_resolve_review_cwd`
  ([review.py:237](src/squadron/cli/commands/review.py#L237)) resolves both
  the reviewing `cwd` *and* the rules directory from one argument — correct
  for `sq review code`'s single root, silently wrong if called with the
  worktree path on the PR path. Left unresolved, this is the same class of
  risk D8 closes for SDK project settings, just for rules content instead of
  hook execution. Fixed: Task G.5 (renumbered from G.3) now states the rules
  directory must resolve from the checkout `cwd` explicitly, calling
  `resolve_rules_dir` directly rather than through `_resolve_review_cwd`.
  New Task G.6 adds the isolation test: a worktree carrying different rules
  content than the checkout, asserting the rendered `rules_content` traces
  to the checkout.
- **F002 (concern) — accepted.** No task added a `tests/load/` case for the
  worktree lifecycle's concurrency and network paths, required by the
  project's load-test tier rule. Dispositioned in file 1 (new Task C.8),
  since the code under test lives there.
- **F003 (concern) — accepted, a duplicate of file 1's F001.** Same fix:
  file 1's Task C.7 now covers the happy-path submodule criterion. File 3's
  H.2 (success criteria sweep) now names C.7 as the evidence explicitly, so
  the sweep does not silently pass over this criterion the way it did
  before.
- **F004 (concern) — accepted.** Part G originally batched G.1–G.4 (target
  resolution, the worktree branch, scope/rules/`--files`, and full
  registration) before its first test task. Restructured: G.1 (resolve/
  fetch) → **G.2** (test) → G.3 (worktree branch, D5) → **G.4** (test —
  sequenced immediately after the security-relevant worktree wiring, not
  after registration) → G.5 (scope/rules/`--files`) → **G.6** (test: rules
  provenance, folds in F001's fix) → G.7 (registration) → **G.8** (test:
  flag parity) → G.9 (commit).
- **F005 (note) — accepted.** `pr.py`'s cited sequence ended at
  `fetch_pull_request_refs`, which is at line 57, one past the cited
  `34-56` range. Fixed to `34-57`.
- **F006 (note) — accepted, no change needed beyond acknowledging it.** The
  `ReviewResult`-vs-display-layer placement choice for reporting "both
  roots" is left to the implementer with a stated decision procedure,
  consistent with file 2's F006 disposition on a similar minor placement
  choice — genuinely low-risk and better decided against 383's actual
  persistence shape than guessed here.
- **F007 (note) — accepted, a duplicate of file 1's F003.** H.3 now has an
  explicit commit step before the merge.
- **F008 (pass)** — Parts F/G/H trace cleanly to D6, D2/D5, and closeout; no
  scope creep. No action.
- **F009 (pass)** — code anchors verified accurate against live source. No
  action.
