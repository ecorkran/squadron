---
docType: tasks
slice: slash-command-parity-documentation-and-live-evidence
project: squadron
lld: user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md
dependencies: [381, 382, 383, 384, 385]
projectState: "381-385 all merged into `squadron-pr`; the three PR capabilities (`sq pr show`, `sq review pr` with `--post`, `sq pr create`) are built, tested against the fake runner, and each has had one live run. None is reachable from a slash command and none appears in README, QUICKSTART, or COMMANDS. Design committed at 13bd1269, reviewed PASS (two notes, both answered — see the LLD's Response section). `squadron-pr` is ahead of `origin/squadron-pr` and has not been pushed; that push is a PM-authorized precondition of the live run, not a task here."
dateCreated: 20260920
dateUpdated: 20260920
status: not_started
---

## Context Summary

- Working on the **slash-command-parity-documentation-and-live-evidence** slice (386), sixth and
  last of the 380 pull-request-workflow initiative. It is the integration slice.
- **This slice adds no capability.** It closes three gaps: the PR commands have no slash-command
  transport, they are undocumented, and no single run has exercised all three together on one
  pull request.
- **No file under `src/squadron/` changes.** Deliverables are two command files, two new test
  modules, one edited test module, four documents, and a recorded live run. If the live run or
  the documentation pass turns up a CLI defect, it is fixed as a defect in its own commit and
  named in the DEVLOG — the slice does not plan for one (LLD, Technical Scope → Excluded).
- **Parity is structural, not tested by execution.** A slash command is a markdown file telling a
  session which `sq` command to run; pytest cannot execute it. D1 makes the transport add nothing
  to the argument string, and D2 tests the one thing that can drift — the command file's
  description of the CLI surface.
- **The three surfaces the drift test must equal** are registered today as: `review pr` with
  `--cwd --rules --rules-dir --no-rules --model --no-tools --profile --verbose --output
  --output-path --reviews-dir --json --no-save --post --dry-run`; `pr show` with `--cwd --json`;
  `pr create` with `--base --dry-run --model --profile --cwd --title`. Tasks 1 and 2 write the
  command files against this surface; Task 3's test is what keeps them equal. Do not copy this
  list into the test — the test introspects the live command objects.
- **The live run (Task 9) has a precondition outside this slice**: `squadron-pr` pushed to
  `origin`. It is PM-authorized and awaited. Tasks 1-8 need no host access and no PM action.
- **D4 is an observation task, not a decision.** Whether the default `sdk` profile works inside a
  Claude Code session is a fact about the runtime; Task 5 observes it and Tasks 6-7 document what
  was observed. Task order puts the observation before the documentation for that reason.
- **Next planned slice:** none. 386 closes initiative 380; Task 11 records that.
- Planning work (this file) commits directly to `squadron-pr`. Phase 6 implementation uses branch
  `386-slice.slash-command-parity-documentation-and-live-evidence`, forked from `squadron-pr`.

### Reference

Design decisions are cited as **D1**-**D6**; see the LLD rather than duplicating them here. The
documentation table in **D5** is the specification for Tasks 6 and 7; the sequence in **D6** is
the specification for Task 9; the four rules in **D3** are the specification for Tasks 1 and 2.
Task order follows the LLD's Implementation Notes → Order.

Test tasks follow their implementation task directly. No test in this slice calls a model, makes
a network call, or writes to a pull request.

**Commits.** Each numbered task ends in one semantic commit from the project root, typed per the
project's git rules — `docs:` for the command files and the four documents (Tasks 1, 2, 6, 7, 10),
`test:` for the test modules (Tasks 3, 4, 8), `chore:` for the close-out (Task 11). Task 5 records
an observation and commits nothing on its own; its result lands with Task 6. Task 9 is a live run
against the host and commits only its captured artifacts. A defect found along the way is its own
commit, separate from the task's.

---

## Task 1 — `commands/sq/pr.md`, the `/sq:pr` transport (D1, D3)

New file. Written first because Task 3's test is written against it.

- [x] **1.1 Create the file with the input-parsing preamble**
  - [x] Create `commands/sq/pr.md`, following the shape of `commands/sq/review.md`: a one-line
        purpose, an `## Input parsing` section, a valid-subcommand list, and a usage block
  - [x] First word of `$ARGUMENTS` is the subcommand; valid subcommands are `show` and `create`
  - [x] A missing or unrecognized subcommand shows the usage block and stops
  - [x] State the delegation rule plainly: the remainder is passed to the CLI **unchanged**, with
        nothing appended, substituted, or removed (D1)
  - [x] Effort: 1

- [x] **1.2 Write the `## Subcommand: show` section**
  - [x] Delegation line: `sq pr show {remainder}`
  - [x] Document every option `sq pr show` registers, and no option it does not register. Read
        them from `sq pr show --help` at authoring time rather than from this task file
  - [x] Describe the four target forms the positional accepts (number, `owner/repo#number` and
        `repo#number`, URL, branch) and that omitting it uses the current branch
  - [x] Note that an absent remainder is valid and passes through as absent (D1)
  - [x] Effort: 1

- [x] **1.3 Write the `## Subcommand: create` section, including the D3 rules**
  - [x] Delegation line: `sq pr create {remainder}`
  - [x] Document every option `sq pr create` registers, read from `--help`, and no other
  - [x] State the four D3 instructions as instructions to the session, not as prose about them:
    - [x] `--dry-run` is offered but never substituted for a real create, nor a create for a dry run
    - [x] The command runs **once**; on a non-zero exit, show the output and stop — no retry
          (a create that failed after landing opens a second PR when retried, 385 D8)
    - [x] Printed remediation — the `git push` line from an unpushed-branch refusal — is **shown,
          not executed**: squadron does not push, and a session that pushes has made it push by proxy
    - [x] A refused base is not worked around by passing `--base` on the operator's behalf
  - [x] Note that `sq pr create` writes to the host, and that the CLI is the only thing that writes
  - [x] Effort: 2

- [x] **1.4 Verify the file parses as a command and installs**
  - [x] `sq install-commands` reports ten files and `~/.claude/commands/sq/pr.md` exists
  - [x] `sq uninstall-commands` (or the documented uninstall path) removes it
  - [x] No change to `src/squadron/cli/commands/install.py` is needed or made — it copies every
        `*.md` under the bundle subdirectory
  - [x] Effort: 1

---

## Task 2 — The `pr` section of `commands/sq/review.md` (D1, D3)

- [x] **2.1 Add `pr` to the preamble**
  - [x] Add `pr` to the valid-subcommand list in `## Input parsing`
  - [x] Add a usage line for it to the usage block, matching the existing lines' shape
  - [x] Effort: 1

- [x] **2.2 Write the `## Subcommand: pr` section**
  - [x] Delegation line: `sq review pr {remainder}` — **no number shorthand and no appended `-v`**,
        unlike the `code`/`slice`/`tasks`/`arch` sections. D1 gives both reasons: a bare number is
        already a complete PR target, and an injected flag is a difference between transports
  - [x] Document every option `sq review pr` registers, read from `sq review pr --help`, and no
        option it does not register
  - [x] Describe the four target forms and the omit-for-current-branch behavior
  - [x] Name where the artifact is written, including the unplanned-repository path: `--reviews-dir`,
        `review.external_reviews_dir`, and that the CLI prints the chosen location and its source
  - [x] State the D3 rules that apply to a review: `--post` is passed **only** when the operator
        typed it; the section never suggests adding it after a review and never re-runs a finished
        review with it; on a non-zero exit from `--post`, show the output and stop
  - [x] Keep the closing convention of the other sections: show the results, and on FAIL or
        CONCERNS highlight the key findings
  - [x] Effort: 2

---

## Task 3 — The command-surface drift test (D2)

Written after Tasks 1 and 2 so its first run either proves the files agree with the CLI or names
exactly what is missing.

- [x] **3.1 Write `tests/cli/test_command_surface.py`**
  - [x] Locate the bundled files through `_get_commands_source()` from
        `squadron.cli.commands.install` — the real bundled file is the fixture, not a synthetic one
  - [x] Define the commands under test as **one module-level list** of (command path, command
        file, section heading) entries, so adding a subcommand later is an added entry, not a new
        test: `review pr` / `review.md` / `## Subcommand: pr`; `pr show` and `pr create` /
        `pr.md` / their headings
  - [x] Extract a section by heading: from the heading line to the next `## ` at the same level or
        end of file
  - [x] Extract flags with a lenient token scan — `--[a-z][a-z-]*` anywhere in the section, inside
        or outside backticks (project parsing rules: parse the semantic content, not the formatting)
  - [x] Introspect the real Typer/Click command from the `sq` app for its registered long options
  - [x] Define the excluded-flag set (`--help`) **once**, as a module constant
  - [x] Effort: 3

- [x] **3.2 Assert surface agreement**
  - [x] For each entry: assert set equality between the CLI's registered long options and the
        flags found in the file's section
  - [x] The failure message must distinguish the two directions — a flag in the CLI but not the
        file is an undocumented capability; a flag in the file but not the CLI is an instruction to
        pass something the CLI will reject
  - [x] Effort: 2

- [x] **3.3 Assert the delegation line**
  - [x] For each entry, assert the section contains its delegation command with the remainder
        placeholder and nothing appended (D1) — in particular that the `pr` section of `review.md`
        does not append `-v`
  - [x] Effort: 1

- [x] **3.4 Prove the test can fail**
  - [x] Add a test that runs the comparison logic against a deliberately incomplete section string
        and asserts it fails — this is the Success Criteria "Technical" item, and without it the
        drift test's value is unproven
  - [x] Refactor the comparison into a function the real test and this test both call, so the
        proof exercises the production path rather than a copy
  - [x] Effort: 2

- [x] **3.5 Run it**
  - [x] `pytest tests/cli/test_command_surface.py -q` passes
  - [x] If it fails, the fix is in the command file (Tasks 1-2), not in the test's expectations
  - [x] Effort: 1

---

## Task 4 — Update the install-commands test for the tenth file

- [x] **4.1 Update counts and the expected map**
  - [x] `tests/cli/test_install_commands.py`: the bundled-file count `9` appears in three
        assertions (the deep-target install, the custom-target install, and
        `test_get_commands_source_returns_valid_dir`) — update each to `10`
  - [x] Add `pr.md` to `EXPECTED_COMMANDS` with its expected delegation command, matching how the
        other entries express theirs
  - [x] Effort: 1

- [x] **4.2 Run it**
  - [x] `pytest tests/cli/test_install_commands.py -q` passes, including the receipt-driven
        uninstall test — `pr.md` is recorded in the receipt and removed on uninstall
  - [x] Effort: 1

---

## Task 5 — Observe the default profile inside a session (D4)

The result is input to Tasks 6 and 7, so it happens before them. This task **records a fact**; it
does not change behavior.

- [x] **5.1 Run `sq review pr` with the default profile from inside a Claude Code session**
  - [x] This task runs before Task 9.1 creates this slice's own PR, so it needs an existing
        target. Use PR **#116** (slice 385), open on `ecorkran/squadron` at the time of writing.
        Confirm it resolves first with `sq pr show 116`; if it has been merged or closed, use any
        open PR on the repository — the observation is about the profile, not about the PR
  - [x] Pass no `--profile` flag, so the `sdk` default applies
  - [x] Record the outcome verbatim: success, or the exact error text and exit code
  - [x] Do the same for `sq pr create --dry-run` (dry run only — no host write in this task)
  - [x] Effort: 1

- [x] **5.2 Decide what the record obliges**
  - [x] If the default works inside a session: Tasks 6-7 say so, and no fallback is documented
  - [x] If it fails: Tasks 6-7 state the observed behavior and the working invocation
        (385's walkthrough used `--profile openrouter`), and the failure is logged as a **GitHub
        issue** against the CLI and linked from the DEVLOG entry (Task 10). It is **not** patched
        over by having the command file inject a profile — that would violate D1
  - [x] Effort: 1

---

## Task 6 — `README.md`: the "Pull requests" section (D5)

- [x] **6.1 Write the section**
  - [x] Place it after `## Reviews in depth`
  - [x] Cover, per the D5 table: reviewing a PR and its target forms; `--post` with `--dry-run`;
        `sq pr create` with `--dry-run`; base selection in one sentence; the five body sections
        named; and the unplanned-repository path — where the artifact goes, `--reviews-dir`,
        `review.external_reviews_dir`, and that the chosen location and its source are printed
  - [x] State the two host writes (`--post` and `sq pr create`) and that squadron never pushes
  - [x] Mention the `/sq:review pr` and `/sq:pr` transports and that they pass arguments through
        unchanged
  - [x] State D4's observed profile behavior (from Task 5)
  - [x] Effort: 3

- [x] **6.2 Constrain the examples**
  - [x] Every example in this section must be one of the invocations Task 9's live run executes —
        the examples and the evidence are then the same commands (D5, "Live")
  - [x] Use a placeholder target only where the grammar requires showing a form (`owner/repo#n`);
        hardcode no value the reader is meant to look up
  - [x] Effort: 1

---

## Task 7 — `docs/COMMANDS.md` and `docs/QUICKSTART.md` (D5)

- [x] **7.1 `docs/COMMANDS.md` — `### review pr`**
  - [x] Add under the existing `## review` section, following the shape of `### review code`
  - [x] Full option table, read from `sq review pr --help`; positional target and its four forms
  - [x] Effort: 2

- [x] **7.2 `docs/COMMANDS.md` — a new `## pr` section**
  - [x] `### pr show` and `### pr create`, each with its full option table read from `--help`
  - [x] Place it consistently with the file's existing top-level ordering
  - [x] Effort: 2

- [x] **7.3 `docs/COMMANDS.md` — `review.external_reviews_dir`**
  - [x] Document it under `## config` alongside the other keys, with its default tree
  - [x] Effort: 1

- [x] **7.4 `docs/QUICKSTART.md` — the `gh` doctor rows**
  - [x] Explain the `gh CLI` and `gh hosts file` rows: what each checks, and that doctor makes no
        subprocess or network call — so an OK row means the CLI is **present**, not that it is
        **authenticated**. Verify this claim against `src/squadron/cli/commands/doctor_checks.py`
        before writing it
  - [x] Include each row's fix hint as doctor prints it
  - [x] Effort: 2

- [x] **7.5 `docs/QUICKSTART.md` — correct the command count**
  - [x] The sample output reads `9 command(s)`; with `pr.md` it is ten
  - [x] Paste the doctor sample from a real `sq doctor -v` run rather than editing the number by
        hand, so the rest of the block is true too (D5)
  - [x] Effort: 1

---

## Task 8 — The documentation-example parse test (D5)

- [x] **8.1 Create `tests/docs/` and write `test_pr_doc_examples.py`**
  - [x] Create the package (`tests/docs/__init__.py`) — it does not exist yet
  - [x] Collect every line beginning `sq review pr` or `sq pr` from fenced code blocks in
        `README.md`, `docs/COMMANDS.md`, and `docs/QUICKSTART.md`, reading the repository files
  - [x] Extraction is lenient: tolerate a leading `$ ` prompt, trailing comments, and a trailing
        line-continuation backslash joining a wrapped example
  - [x] Split with `shlex`
  - [x] Effort: 2

- [x] **8.2 Parse each example against the real command without invoking it**
  - [x] Resolve the Click command from the `sq` app and parse the argument list against it, so an
        unknown flag or a flag missing its required value fails the test
  - [x] Nothing is executed: no model call, no subprocess, no network, no host write
  - [x] Assert at least one example was collected — an extractor that silently finds nothing must
        fail rather than pass vacuously (project parsing rules)
  - [x] Effort: 2

- [x] **8.3 Run both new test modules**
  - [x] `pytest tests/docs/test_pr_doc_examples.py tests/cli/test_command_surface.py -q` passes
  - [x] Effort: 1

---

## Task 9 — The live end-to-end run (D6)

**Precondition, not a task step:** `squadron-pr` is pushed to `origin` at its current head. That
push is PM-authorized and outside this slice. Do not perform it as part of this task; if it has
not happened, stop and report. `gh` must be authenticated for `github.com`.

Every step below is run by the operator's explicit command, and each write is preceded by its
`--dry-run`. Record each step's command, exit code, and identifying output (PR URL, comment URL,
artifact paths, shas) as you go — Task 10 writes them up.

- [x] **9.1 Push this slice's branch and create the PR**
  - [x] Push `386-slice.slash-command-parity-documentation-and-live-evidence`
  - [x] `sq pr create --dry-run`, inspect the title and body, then `sq pr create`
  - [x] Confirm stderr names the base as `squadron-pr` with source `integration-branch`
  - [x] Record the PR number and URL; `<n>` below is that number
  - [x] Effort: 1

- [x] **9.2 Deterministic parity: `sq pr show --json` across both transports (D2 tier one)**
  - [x] `sq pr show <n> --json` from a terminal, saved to a file
  - [x] `/sq:pr show <n> --json` in a Claude Code session, output saved to a second file
  - [x] `diff` prints nothing — byte-identical. If it does not, the difference is the finding:
        record it and stop rather than editing either output
  - [x] Effort: 1

- [x] **9.3 Review and post from the CLI**
  - [x] `sq review pr <n> --reviews-dir <cli-dir> --post --dry-run` — confirm it prints the comment
        and writes nothing to the host
  - [x] Then the same command without `--dry-run` — one comment posted
  - [x] Record the comment URL and the artifact path
  - [x] Effort: 1

- [x] **9.4 Review and post from the slash command**
  - [x] `/sq:review pr <n> --reviews-dir <slash-dir> --post` in a session, same model and profile
        as 9.3
  - [x] Confirm the session ran that exact `sq` command, once
  - [x] `gh pr view <n> --json comments` shows **one** squadron comment, updated rather than
        duplicated (384's idempotency, now across transports)
  - [x] Effort: 1

- [x] **9.5 Compare the two review artifacts (D2 tier two)**
  - [x] Same filename in both directories
  - [x] Same frontmatter keys, and equal values for every deterministic field: the `pr` record,
        `reviewedSha`, `sourceDocument`, `reviewType`, `aiModel`, rules source
  - [x] Verdict and findings are model output: **record them, do not compare them**
  - [x] Keep both artifacts under `project-documents/user/reviews/` as 385's was
  - [x] Effort: 1

- [x] **9.6 The four target forms through `sq pr show`**
  - [x] Number, URL, `owner/repo#n`, and branch — all four against the now-open PR, closing the
        success-path gap 381's tasks deferred to this slice for want of an open PR
  - [x] Effort: 1

- [x] **9.7 Refusal is shown, not worked around (D3)**
  - [x] On a scratch branch with an unpushed commit, run `/sq:pr create --dry-run` in a session
  - [x] The session shows the refusal and the printed `git push` line and runs nothing further
  - [x] `git ls-remote` confirms the branch is still absent from the host
  - [x] Delete the scratch branch afterward
  - [x] Effort: 1

- [x] **9.8 Record the final host state**
  - [x] `gh pr view <n> --json body,comments` — the body has all five sections; exactly one
        squadron comment
  - [x] Effort: 1

---

## Task 10 — CHANGELOG and DEVLOG

- [x] **10.1 `CHANGELOG.md`**
  - [x] One user-facing bullet under `### Added` for the slash-command transports: `/sq:review pr`
        and `/sq:pr` with `show` and `create`. 381-385 already wrote the bullets for the
        capabilities themselves — do not restate them
  - [x] Keep it short and user-facing; technical detail belongs in the DEVLOG
  - [x] Effort: 1

- [x] **10.2 `DEVLOG.md`**
  - [x] An entry recording the live run step by step: each command, its exit code, and its
        identifying output (PR URL, comment URL, artifact paths, shas)
  - [x] Record D4's observation (Task 5) and link any GitHub issue it produced
  - [x] Record any CLI defect found during the run or the documentation pass, with its commit
  - [x] Note that after the merge is pushed the host marks the PR merged, which is its correct
        final state (D6, "Landing")
  - [x] Effort: 2

---

## Task 11 — Close the slice and the initiative

- [ ] **11.1 Refine the verification walkthrough**
  - [ ] Replace the LLD's draft walkthrough with the real commands and real output from Task 9,
        including the actual PR number
  - [ ] Effort: 1

- [x] **11.2 Log the deferred work as issues**
  - [x] Open a GitHub issue for retrofitting the drift test to the pre-existing subcommands
        (`code`, `slice`, `tasks`, `arch`, `resolve`) — the test's command list is the extension
        point, but their sections were not authored against it (LLD, Excluded)
  - [x] Link the issue number from this task file and from the DEVLOG entry — issue
        [#120](https://github.com/ecorkran/squadron/issues/120)
  - [x] Effort: 1

- [ ] **11.3 Gate**
  - [ ] `ruff format`, `ruff check`, `pyright` — zero errors
  - [ ] Full suite: no new failures. The three `tests/documents/test_schema_drift.py` failures are
        pre-existing (context-forge issue #88) and are not this slice's
  - [ ] Confirm no file under `src/squadron/` changed, except any defect fix committed separately
        and named in the DEVLOG
  - [ ] Effort: 1

- [ ] **11.4 Mark everything complete**
  - [ ] `status: complete` in this task file and in the slice design
  - [ ] Check slice plan entry 6 in `user/architecture/380-slices.pull-request-workflow.md`
  - [ ] Update the slice plan's and architecture document's `status` — 386 is the last slice, so
        this closes initiative 380
  - [ ] Every item in this file is checked, including any deliberately dropped, before the merge
  - [ ] Effort: 1

- [ ] **11.5 Land it**
  - [ ] Local `--no-ff` merge into `squadron-pr`, as every slice of this initiative landed. The
        live PR is evidence, not the merge route (D6, "Landing")
  - [ ] **Never merge to `main`** — `git.integration_branch` is set. Syncing or merging
        `squadron-pr` into `main` is PM-only and comes after this slice plus further testing
  - [ ] Effort: 1
