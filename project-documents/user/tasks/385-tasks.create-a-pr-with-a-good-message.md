---
docType: tasks
slice: create-a-pr-with-a-good-message
project: squadron
lld: user/slices/385-slice.create-a-pr-with-a-good-message.md
dependencies: [381]
projectState: "384 merged to `squadron-pr`; `sq review pr --post` writes findings to a PR. 381's authoring operations (`open_pull_request`, `default_branch`, `branch_exists`, `identify_operator`) are implemented over `gh` and fake-runner tested, with no production caller — this slice is their first. Design committed at 2c138d42; the plan entry's `sdk`-through-one-shot risk was resolved during design (D3) and the entry amended. Design reviewed (CONCERNS, all three findings addressed) — see the LLD's Design Review Response."
dateCreated: 20260917
dateUpdated: 20260917
status: not_started
---

## Context Summary

- Working on the **create-a-pr-with-a-good-message** slice (385), fifth of six in the 380 pull-request-workflow initiative.
- **Current state:** 381–384 all read from a pull request or write findings to one. This slice points the other way: `sq pr create` opens the PR and writes a description built from the branch's own artifacts. 381 built the four authoring operations over `gh` with no caller; this slice is that caller.
- **What this slice delivers:** `sq pr create` with base selection that refuses rather than falls through, a two-part pushed-branch precondition, input gathering from commits + slice artifacts + the latest in-range review, deterministic assembly, a five-section body contract with a presence check, `--dry-run`, and creation through the adapter.
- **Dependencies are 381 alone.** 383 is not a prerequisite — without it the review-provenance section carries its no-input line, which the architecture names as a supported degraded path. 383 is merged, so that path is exercised by unplanned repositories rather than by this one, and it is still built and tested.
- **Two parsers do not exist anywhere in the tree and are new here.** There is no `{index}-slice.{name}` branch-name parser (only the reverse lookup `_find_slice_branch` in `git_utils`), and nothing reads task-file checkbox state — `_tasks_input` passes task files to the review template as *paths* for injection. Tasks 1 and 2 write them, first, alone, because everything downstream depends on both.
- **The design resolved the plan entry's named risk (D3).** `summary_oneshot` does not refuse the `sdk` profile; its pipeline caller gates on SDK-session reuse, which a CLI command does not have. The composer performs the one-shot sequence directly rather than calling `summary_oneshot` or `run_review_with_profile`. The correction owed is to `summary_oneshot`'s docstring (Task 15), not its routing.
- **Every refusal that can be decided without a model call happens before it** — a missing push or an absent integration branch costs no tokens. Task order follows that sequencing.
- **The model is faked in every test.** It is exercised once, live, in Task 16.
- **The design was reviewed at CONCERNS and all three findings are folded into the tasks below.** F007 corrected the `ls-remote` timeout constant to `GIT_QUERY_TIMEOUT_SECONDS` (Tasks 6, 14); F008 added the model call's own failure mode, which is not a `CodeHostError` (Task 10); F009 filled a real gap — the title mechanism was named in the flag list and specified nowhere — now **D4a** and Task 10a.
- **Next planned slice:** 386 (Slash-Command Parity, Documentation, and Live Evidence), which consumes this slice's CLI surface.
- Work commits directly to `squadron-pr` (integration branch) through Phase 5; Phase 6 implementation uses branch `385-slice.create-a-pr-with-a-good-message`.

### Reference

Design decisions are cited as **D1**–**D8**, including **D4a** (the title, added in response to the design review); see the LLD rather than duplicating them here. Tasks follow the design's implementation order (LLD, "Implementation Notes → Order"). The base-selection table in **D1** is the specification for Task 5; the section table in **D4** is the specification for Task 11; the title table in **D4a** is the specification for Task 10a; the failure matrix in **D8** is the specification for Task 14.

Test tasks follow their implementation task directly. No test in this slice calls a model.

---

## Task 1 — The slice-branch name parser (D7)

Pure function, no dependencies, first consumed by Task 7.1. Landing alone makes a regression here unambiguous.

- [x] **1.1 Write `parse_slice_branch`**
  - [x] Create `src/squadron/pr/__init__.py` and `src/squadron/pr/branch.py`
  - [x] `parse_slice_branch(branch: str) -> int | None` — returns the index when the branch matches the `{index}-slice.{name}` convention, `None` otherwise
  - [x] Match the convention as the project's git rules define it: leading digits, `-slice.`, then a non-empty name
  - [x] A branch that does not match returns `None`. It is not an error — the architecture says a non-matching branch "gets a commits-only description, not a guessed slice"
  - [x] Effort: 1

- [x] **1.2 Test `parse_slice_branch`**
  - [x] `tests/pr/test_branch.py`. Cases: `385-slice.create-a-pr-with-a-good-message` → `385`; `384-slice.post-findings-to-the-pr` → `384`; `squadron-pr` → `None`; `main` → `None`; `feature/add-thing` → `None`; a branch with digits but no `-slice.` → `None`; a name containing further dots (`910-slice.foo.bar`) → `910`
  - [x] Success: every case passes; no case raises
  - [x] Effort: 1

---

## Task 2 — The task-file checkbox parser (D4)

The first checkbox reader in the codebase. Needed by Tasks 9 and 10.

- [x] **2.1 Write `parse_task_items`**
  - [x] Create `src/squadron/pr/tasks.py` with `parse_task_items(text: str) -> TaskItems`, where `TaskItems` is a frozen dataclass carrying `checked: tuple[str, ...]` and `unchecked: tuple[str, ...]`
  - [x] Parse leniently per the project's parsing rules: a list item counts when its marker is `[x]`, `[X]`, or `[ ]`, at **any indent depth**, with any leading list bullet (`-`, `*`, `+`) and any surrounding whitespace
  - [x] **Sub-items are attributed to their own state, not their parent's** — a checked parent with an unchecked child yields one of each
  - [x] The item's text is what follows the checkbox, stripped; markdown emphasis is left as written
  - [x] Items are returned in document order within each group
  - [x] Effort: 2

- [x] **2.2 Test `parse_task_items` against a real task file**
  - [x] `tests/pr/test_tasks.py`. Unit cases: `[x]`, `[X]`, `[ ]`, nested items at two and three indent levels, mixed parent/child states, trailing whitespace after the text, a line that is not a list item, an empty document
  - [x] **Fixture from real input.** Per the project's parsing rules ("the test fixture must include the actual format that parser will consume in production"), include a test reading an actual task file from `project-documents/user/tasks/` — this file once it exists, or `384-tasks.post-findings-to-the-pr.md` until then — and asserting both groups are non-empty and their counts sum to the file's checkbox count
  - [x] Success: the real-file test would fail if the parser required one exact indent level or a specific bullet character
  - [x] Effort: 2

---

## Task 3 — Git helpers for branch and range

Two helpers `git_utils.py` lacks. Both go beside the existing ones and use the module's `run_git` and its timeout.

- [x] **3.1 Write the helpers**
  - [x] In `src/squadron/review/git_utils.py`, add `current_branch(cwd: str) -> str` — `git rev-parse --abbrev-ref HEAD`
  - [x] A detached HEAD (git returns `HEAD`) raises, naming the condition: there is no branch to open a PR from. Match `github_cli._branch_for`'s existing behavior for the same situation (D2)
  - [x] Add `commits_in_range(base: str, head: str, *, cwd: str) -> list[CommitRecord]` — `git log` over `base..head` returning sha and subject per commit, newest first
  - [x] `CommitRecord` is a frozen dataclass with `sha: str` and `subject: str`
  - [x] Both go through the module's existing `run_git`, so both are bounded by `GIT_COMMAND_TIMEOUT_SECONDS`. Neither swallows a git failure: `run_git` returning `None` (git could not answer) and a non-zero return code (git ran and refused) are distinguished, per the module's own contract
  - [x] Effort: 2

- [x] **3.2 Test the helpers**
  - [x] Add to `tests/review/test_git_utils.py` (or a new file if that one is near its size limit). Cases: current branch on a normal checkout; detached HEAD raises; commits in a range with several commits; an empty range returns `[]`; git unavailable and git-refuses are distinguished
  - [x] Success: the empty-range case returns a list, not `None`, and does not raise
  - [x] Effort: 1

---

## Task 4 — Extract `resolve_locator` from `resolve_and_fetch_pull_request` (D6)

`create` needs host + remotes + locator, which are that helper's first three steps. `show` must be unchanged.

- [x] **4.1 Extract the shared prefix**
  - [x] In `src/squadron/cli/commands/pr.py`, extract the first three steps of `resolve_and_fetch_pull_request` into `resolve_locator(target: str | None, repo_cwd: str) -> tuple[CodeHost, RepositoryLocator]`
  - [x] `resolve_and_fetch_pull_request` calls it and keeps its own signature and behavior exactly
  - [x] Success: `sq pr show` behaves identically — its existing tests pass unchanged, with no edits to them
  - [x] Effort: 1

- [x] **4.2 Test the extraction**
  - [x] Assert `resolve_locator` returns the locator for each target form that `show` supports, against the fake runner
  - [x] Assert the existing `sq pr show` tests still pass without modification — this is the real criterion
  - [x] Effort: 1

---

## Task 5 — Base selection (D1)

The design's table is the specification. Three outcomes for the integration-branch term, not two.

- [x] **5.1 Write `select_base`**
  - [x] Create `src/squadron/pr/base.py` with `select_base(host, locator, *, base_flag: str | None, cwd: str) -> BaseSelection`
  - [x] `BaseSelection` is a frozen dataclass with `base: str` and `source: BaseSource`, where `BaseSource` is a `StrEnum` with members for the flag, the integration branch, and the host default — **not** free-text strings, per the project's rule against scattering comparison values
  - [x] Implement D1's table exactly:
    - `--base` given → use it, `source=flag`, **no host confirmation** (the design says why: a bad `--base` is loud, because `open_pull_request` rejects it with a 422 that names it)
    - integration branch set and `branch_exists` true → use it, `source=integration-branch`
    - integration branch set and `branch_exists` false → **raise**, naming the branch
    - integration branch unset or empty → `default_branch(locator)`, `source=host-default`
  - [x] Read `git.integration_branch` through `ContextForgeClient.get_config`, the same subprocess path `resolve_diff_base` uses. Accept an injectable client for tests, as `resolve_diff_base` does
  - [x] **Do not degrade an unreachable `cf` to a default base.** When `cf` is unavailable the key is treated as unset and the chain proceeds to the host default; when `cf` answers with a branch name, that name is authoritative and the confirmation applies (D1)
  - [x] Effort: 3

- [x] **5.2 Test base selection**
  - [x] `tests/pr/test_base.py`, against the fake runner and a fake cf client. One case per table row, plus: `cf` unavailable → host default, no raise; `cf` returns empty string → host default; the refusal case asserts the branch name appears in the message and that `default_branch` was **never called**
  - [x] Assert `--base` makes no `branch_exists` call
  - [x] Success: the refusal case would fail if the implementation fell through to the host default
  - [x] Effort: 2

---

## Task 6 — The pushed-branch precondition (D2)

Two checks, two different fixes. Both before any model call and any write.

- [x] **6.1 Write the precondition checks**
  - [x] Create `src/squadron/pr/preconditions.py` with `check_head_pushed(host, locator, *, head: str, local_sha: str, cwd: str) -> None`, raising on refusal
  - [x] **Missing:** `branch_exists(locator, head)` false → raise naming the branch and the `git push -u <remote> <head>` command
  - [x] **Behind:** the host's sha for the branch differs from `local_sha` → raise naming both shas and the `git push <remote> <head>` command
  - [x] Read the remote sha with `git ls-remote <remote> refs/heads/<head>` through the adapter's process-runner seam, bounded by **`GIT_QUERY_TIMEOUT_SECONDS`** — the constant `codehost/refs.py` and `codehost/remotes.py` use for git queries, *not* `HOST_COMMAND_TIMEOUT_SECONDS`, which is for `gh` invocations (D2). Both are 30s today; the distinction is which constant a future change moves
  - [x] **Do not add a protocol operation** — the architecture fixes the operation list, and this is answerable with git against a remote the locator already names, as 381 fetches refs with git (D2)
  - [x] The remote name comes from the locator
  - [x] Effort: 3

- [x] **6.2 Test the preconditions**
  - [x] `tests/pr/test_preconditions.py`. Cases: branch absent → refusal naming `git push -u`; branch present and shas equal → passes; branch present and shas differ → refusal naming `git push` and both shas; `ls-remote` returning no matching ref; `ls-remote` timing out → refusal, not a silent pass
  - [x] Assert the `ls-remote` call carries `GIT_QUERY_TIMEOUT_SECONDS`, not the `gh` constant
  - [x] Success: the two refusals name different commands
  - [x] Effort: 2

---

## Task 7 — Input gathering: commits and slice artifacts (D7)

- [x] **7.1 Gather commits and the slice**
  - [x] Create `src/squadron/pr/inputs.py` with the commit and slice halves of `gather_inputs`
  - [x] Commits: `commits_in_range(base, head)` from Task 3. Always present — an empty range is impossible here, since a PR with no commits cannot be opened
  - [x] Slice: `parse_slice_branch(head)` from Task 1; on a match, `resolve_slice_info(cf_client, index)` for the design file and task files; read the first task file and `parse_task_items` it (Task 2)
  - [x] A branch that names a slice `cf` cannot resolve degrades to no-slice with a WARNING naming the index — not fatal, because a PR should still open
  - [x] A missing or unreadable task file degrades to no task items with a WARNING, leaving the design file usable for "why"
  - [x] Effort: 3

- [x] **7.2 Test commit and slice gathering**
  - [x] `tests/pr/test_inputs.py`. Cases: slice branch with design and tasks; slice branch whose index `cf` does not know → WARNING, no slice, no raise; non-slice branch → no slice, no `cf` call; task file absent → design present, items empty; `cf` unavailable entirely
  - [x] Assert the WARNING is emitted (per the design principles' failure-mode-observability rule) in each degraded case
  - [x] Effort: 2

---

## Task 8 — Input gathering: the latest in-range review (D7)

The rule that keeps a neighboring slice's review off this PR.

- [x] **8.1 Write the review scan**
  - [x] Add `find_latest_in_range_review(...)` to `src/squadron/pr/inputs.py`
  - [x] Enumerate `*-review.*.md` in the reviews directory — both the project's and, for an unplanned repository, the configured external directory 383 established. Reuse 383's `resolve_reviews_dir` rather than re-deriving the location
  - [x] Read each file's frontmatter for `reviewedSha` via the existing `read_frontmatter`
  - [x] **Keep those whose sha is in `git rev-list <base>..<head>` — membership in the range, not ancestry of head.** This is what excludes a merged ancestor's review (D7)
  - [x] Of the survivors, take the one whose reviewed sha is newest in the range
  - [x] An artifact with no `reviewedSha`, an unparseable sha, or a sha git does not recognize is **skipped with a WARNING naming the file** — not fatal, and not silent: silently dropping a review that should have been cited is the failure the provenance section exists to prevent
  - [x] Do not reuse `locate_review` — it is index-keyed and raises on ambiguity rather than ordering, both correct for its own callers
  - [x] Effort: 3

- [x] **8.2 Test the review scan**
  - [x] Add to `tests/pr/test_inputs.py`. **The load-bearing case:** a review whose reviewed sha is an ancestor of head but outside `base..head` is **not** selected, while an in-range review is. Build both in a fixture repository
  - [x] Further cases: no reviews at all → `None`; two in-range reviews → the newer sha wins; a review with no `reviewedSha` → skipped with a WARNING, scan continues; a malformed frontmatter file → skipped with a WARNING, scan continues; the external reviews directory is used when the repository has no `project-documents/`
  - [x] Success: the ancestor case would fail if the implementation used ancestry or file mtime
  - [x] Effort: 3

---

## Task 9 — Deterministic assembly

The exact parts, built without a model. Every fact copied, none inferred.

- [ ] **9.1 Write `assemble_facts`**
  - [ ] Create `src/squadron/pr/assembly.py` with `assemble_facts(inputs: PrInputs) -> PrFacts`
  - [ ] `PrFacts` is a frozen dataclass carrying the commit list, the slice design path, the checked and unchecked task items, the review artifact path, its verdict, and its reviewed sha — each either present or explicitly absent
  - [ ] **Every field is copied from an input. Nothing is derived, inferred, or defaulted.** Initiative 360's traceability rule is the constraint: assert nothing an input does not support
  - [ ] Absent inputs are represented as `None` or empty tuples, never as placeholder text — the no-input lines are the body layer's job (Task 11), not assembly's
  - [ ] Effort: 2

- [ ] **9.2 Test assembly**
  - [ ] `tests/pr/test_assembly.py`. Cases: full inputs → every field populated; no slice → slice fields absent, commits present; no review → review fields absent; no task items → both item tuples empty
  - [ ] Assert no field is ever a placeholder string
  - [ ] Effort: 1

---

## Task 10 — The one-shot composer (D3)

Prompt in, text out, through a profile. Small because it does one thing.

- [ ] **10.1 Write the composer**
  - [ ] Create `src/squadron/pr/body.py` with the one-shot call: `get_profile` → `ensure_provider_loaded` → `get_provider` → build an `AgentConfig` → `create_agent` → `handle_message`, the same sequence `run_review_with_profile` uses (D3)
  - [ ] Takes `model: str | None` and `profile: str` exactly as the CLI flags supply them
  - [ ] **Give the model no tools.** A description-writer with tools can assert things no input supports, which is what the traceability rule forbids (D3)
  - [ ] Do **not** call `summary_oneshot` or `run_review_with_profile` — the design states why for each (pipeline-shaped parameters; review-shaped template and result parsing)
  - [ ] The composer is injectable so every other test can fake it
  - [ ] **Enumerate the model call's failure mode (D8).** A provider that is unreachable, unauthenticated, or times out mid-stream, and any exception from `handle_message`, are caught at the composer's boundary, logged at ERROR with `logger.exception`, and become a non-zero exit that creates nothing. This is a process-boundary handler in the project's exception rules' sense, which is what permits catching broadly *here*; every narrower handler in the slice names its exception type
  - [ ] Effort: 3

- [ ] **10.2 Test the composer's wiring**
  - [ ] `tests/pr/test_body.py`, against a fake provider. Assert: the profile is resolved through the registry; `model=None` is passed through rather than defaulted locally; no tools are requested; the response text is returned unmodified
  - [ ] Assert the `sdk` profile resolves and dispatches without requiring a session — the design's D3 claim, checked rather than asserted
  - [ ] Assert a provider raising during `handle_message` exits non-zero, logs at ERROR, and creates nothing
  - [ ] No test here calls a real model
  - [ ] Effort: 2

---

## Task 10a — The title (D4a)

Three terms, only the third of which reaches the model. The slice's one degradation rather than refusal.

- [ ] **10a.1 Write `resolve_title`**
  - [ ] In `src/squadron/pr/body.py`, implement D4a's three-term table: `--title` verbatim → else the slice's human name → else a model-composed line
  - [ ] The human name comes from the design's H1 (`# Slice Design: {name}`, prefix stripped), **not** the frontmatter `slice` field, which is the kebab-case slug. A design whose H1 does not match that shape falls through to the third term rather than emitting a malformed title
  - [ ] The second term is deterministic and **makes no model call** — the slice is already named, and spending tokens to reinvent it loses information
  - [ ] The third term asks for one line under 72 characters, given the commit subjects and nothing else. 72 is the project's commit-summary convention applied to the same kind of object
  - [ ] **A response that is empty, multi-line, or over the bound falls back to the first commit's subject** — always present, always truthful. This is the slice's one place where a model failure degrades instead of refusing; D4a states the proportionality argument
  - [ ] The title is resolved once and bound to one variable shared by the dry-run and real paths, as the body is (D8)
  - [ ] Effort: 2

- [ ] **10a.2 Test the title**
  - [ ] Add to `tests/pr/test_body.py` with a fake composer. Cases: `--title` wins over both other terms; a resolved slice branch uses the H1 name and the composer is **never called**; a design with a non-matching H1 falls through to the model; a non-slice branch composes; an empty model response falls back to the first commit subject; a multi-line response falls back; a 100-character response falls back; a valid 60-character response is used
  - [ ] Success: the slice-branch case would fail if the implementation always called the model
  - [ ] Effort: 2

---

## Task 11 — The section contract (D4)

Five headings, squadron's. The model writes only prose.

- [ ] **11.1 Write the body assembly**
  - [ ] In `src/squadron/pr/body.py`, add `compose_body(facts: PrFacts, *, composer) -> str`
  - [ ] Define the five sections once, in order, as a module-level structure — heading text, which fact feeds it, and its no-input line. **One definition, referenced everywhere**, per the project's rule against scattering comparison values across code
  - [ ] Implement D4's table: what changed (commits, + design when present); why (design, else commits); how it was verified (checked items); known gaps (unchecked items); review provenance (the in-range review)
  - [ ] **Squadron emits the headings and writes the deterministic facts directly beneath the prose they support** — the commit list under "what changed", the design path under "why", the artifact path, verdict, and reviewed sha under "review provenance". The model's own headings, if it emits any, are discarded
  - [ ] A section with no input carries its no-input line **verbatim** and the model is not asked for prose there (D4)
  - [ ] "How it was verified" and "known gaps" share a no-input line because both derive from the task file
  - [ ] Effort: 3

- [ ] **11.2 Test the section contract**
  - [ ] Add to `tests/pr/test_body.py` with a fake composer. Cases: full inputs → five sections, no no-input lines; no slice → the two task sections carry their line; no review → provenance carries its line; unplanned repository (no slice, no review) → five sections with three no-input lines
  - [ ] Assert the deterministic facts appear verbatim — a commit sha from the input appears in the output
  - [ ] Assert a model response containing its own `##` headings does not produce duplicate or reordered sections
  - [ ] Effort: 3

---

## Task 12 — The presence-and-filled check (D5)

A body that fails this is an error, not a degraded PR.

- [ ] **12.1 Write the check**
  - [ ] In `src/squadron/pr/body.py`, add the check: all five headings present, **in order**, each section either containing prose or containing exactly its no-input line
  - [ ] **"Filled" is structural:** content non-empty after stripping whitespace and the squadron-written deterministic block, and not solely a restatement of the heading. It does not judge prose quality, which is not checkable and would be a false promise (D5)
  - [ ] The check runs on the **assembled** body, after squadron's headings and facts are inserted — so it validates what would be posted, not the model's raw response
  - [ ] Failure raises. **No retry** — a retry loop makes the command's token cost unbounded, and the operator can rerun having seen the reason (D5)
  - [ ] Effort: 2

- [ ] **12.2 Test the check**
  - [ ] Add to `tests/pr/test_body.py`. Cases: a complete body passes; a body missing one section fails naming it; a section containing only its heading fails; a section containing only whitespace fails; a section containing exactly its no-input line **passes**; sections present but out of order fails
  - [ ] Assert the failure path creates nothing — no host call is made
  - [ ] Effort: 2

---

## Task 13 — The `create` command (D6, D8)

Thin by construction: orchestration, printing, exit codes.

- [ ] **13.1 Wire the command**
  - [ ] In `src/squadron/cli/commands/pr.py`, add `@pr_app.command("create")` with `--base`, `--dry-run`, `--model`, `--profile`, `--cwd`, and `--title`
  - [ ] Order exactly as the design's data flow: resolve locator → preconditions (identity, then pushed) → base selection → input gathering → assembly → compose → check → dry-run return or create
  - [ ] **Every refusal decidable without a model happens before the model call** (D8)
  - [ ] `--title` is the first term of D4a's three-term title resolution (Task 10a), not a simple override of a model-composed title
  - [ ] Print the chosen base and its source before any write (D1)
  - [ ] `--dry-run` prints title and body to **stdout**, base and source to **stderr**, and returns before the write — the same split 384 chose, so the body can be piped
  - [ ] **`--dry-run` needs no accompanying flag.** Unlike `sq review pr --dry-run`, which required `--post` because posting was the opt-in, `sq pr create` *is* the write, so `--dry-run` is simply its preview (D8)
  - [ ] Bind the body **once** to one variable shared by the dry-run and real paths, so their equality is structural (D8)
  - [ ] On success print the created PR's URL
  - [ ] Effort: 3

- [ ] **13.2 Test the command**
  - [ ] `tests/cli/test_pr_create.py`, against the fake runner with a faked composer. Cases: the full happy path makes exactly one write; `--dry-run` makes **zero** writes and prints the body to stdout; dry-run output equals the body the next real run sends; `--base` is honored; `--title` overrides; identity refusal exits 1 with no write; a failed presence check exits 1 with no write
  - [ ] Assert the ordering: a precondition failure means the composer was **never called**
  - [ ] Effort: 3

---

## Task 14 — Transport failure and timeout across all five host calls (D8)

Mirrors 384's Task 7 matrix. The five call sites are `identify_operator`, `branch_exists`, `default_branch`, the `ls-remote` sha read, and `open_pull_request`.

- [ ] **14.1 Cover the failure matrix**
  - [ ] `tests/cli/test_pr_create_failures.py`, parametrized over all five call sites for both a classified transport failure and a scripted `ProcessTimedOutError`
  - [ ] Each asserts exit 1 and **no effective write** — distinguishing "zero attempts" at the four read sites from "exactly one failed, non-duplicating attempt" at the write site itself, as 384's helper does
  - [ ] Assert the four `gh` calls carry `HOST_COMMAND_TIMEOUT_SECONDS` and the `ls-remote` call carries `GIT_QUERY_TIMEOUT_SECONDS` (D2, F007)
  - [ ] Assert `PullRequestCreationRejectedError` (HTTP 422 from `open_pull_request`) is reported with the host's reason and its fix hint, and is **not retried** — a retried create after a network error that actually landed would open two PRs (D8)
  - [ ] Every one of the five uses the `except CodeHostError` → `render_code_host_error` → `typer.Exit(code=1)` pattern `review_pr.py` set
  - [ ] Effort: 3

---

## Task 15 — Import-graph guard and the `summary_oneshot` docstring

Two small corrections the design owes.

- [ ] **15.1 Extend the import-boundary test**
  - [ ] In `tests/codehost/test_import_boundaries.py`, add a case asserting `review/` does not import `pr/` (D6)
  - [ ] Confirm the existing review-package import ban and 384's single carve-out for `pr_comment.py` are unchanged
  - [ ] Effort: 1

- [ ] **15.2 Correct the `summary_oneshot` docstring (D3)**
  - [ ] In `src/squadron/pipeline/summary_oneshot.py`, correct the module docstring: it currently says "One-shot summary execution for non-SDK provider profiles", which describes its *caller's* policy rather than the module's behavior. State that the module routes any registered profile, and that the pipeline's SDK-session reuse is the caller's rule
  - [ ] **Do not change the routing.** It is correct, and the pipeline gate in `pipeline/actions/summary.py` stays where it belongs
  - [ ] Add a test asserting the module routes a registered profile without reference to SDK-ness
  - [ ] Success: `pipeline/actions/summary.py` is unmodified by this task
  - [ ] Effort: 1

---

## Task 16 — Verification, evidence, and close

- [ ] **16.1 Run the full gate**
  - [ ] `ruff format`, `ruff check`, `pyright` — zero errors is the merge blocker
  - [ ] Full test suite. The 3 pre-existing schema-drift failures (context-forge issue #88) are expected and must be unchanged by this slice
  - [ ] Effort: 1

- [ ] **16.2 Walk the design's verification steps live**
  - [ ] Execute the LLD's Verification Walkthrough, all six steps: dry run on a slice branch; the base refusal with a nonexistent integration branch; both push preconditions; the unplanned-repository path; dry-run/real equality followed by a live creation; and `sq review pr --dry-run --post` reading the created body back
  - [ ] **Step 6 is the two-readers claim checked rather than asserted** — the reviewer parses the sections squadron wrote
  - [ ] Restore `git.integration_branch` to `squadron-pr` after step 2
  - [ ] Record the created PR's URL as evidence
  - [ ] Effort: 3

- [ ] **16.3 Rewrite the Verification Walkthrough with observed output**
  - [ ] Replace the LLD's draft walkthrough in place with the actual commands and their observed output, as 384 did
  - [ ] Note explicitly any step that could not be exercised live and what covers it instead
  - [ ] Effort: 2

- [ ] **16.4 Close the slice**
  - [ ] CHANGELOG: one concise user-facing bullet
  - [ ] DEVLOG: a full dated entry covering the code tasks and the live verification
  - [ ] Set `status: complete` in both this file's and the LLD's frontmatter
  - [ ] Check entry 5 in `380-slices.pull-request-workflow.md`
  - [ ] **Mark any dropped or skipped item above `[x]` before closing** — the visualizer reads checkbox state
  - [ ] Code review is required before the slice closes. **Ask the Project Manager how they want it run** (pipeline and which model, direct `sq review code`, or the `/code-review` skill) rather than choosing a command
  - [ ] Merge `385-slice.create-a-pr-with-a-good-message` into `squadron-pr`. **Never into `main`** — the integration branch is set for this initiative
  - [ ] Effort: 2

---

## Task Review Response

Tasks review at `385-review.tasks.create-a-pr-with-a-good-message.md` (`moonshotai/kimi-k3`, reviewed sha `da018715`): **PASS**, four PASS and two notes.

**F004 — Task 1's header cited the wrong downstream consumer.** Correct. `parse_slice_branch`'s only consumer is Task 7.1 (slice input gathering); the header said Task 9. Fixed. Sequencing was unaffected either way — Task 1 lands first regardless — but a header that misstates its own dependency is exactly what a later reader would trust.

**F005 — commit checkpoints are implicit rather than explicit.** No change. The reviewer correctly identified that this file relies on CLAUDE.md's global rule ("git add and commit from project root at least once per task") rather than embedding per-task commit items, and left open whether the project expects them embedded. It does not: `384-tasks.post-findings-to-the-pr.md` carries no commit checkpoints either and closed successfully. Embedding them here would add ~17 checkbox items restating a rule that already applies, against the project's own instruction to resist unnecessary additions.

The four PASS findings covered functional and technical success-criteria coverage (including all three design-review findings), dependency sequencing with the test-with pattern, and the absence of scope creep or an NFR/load-test obligation.
