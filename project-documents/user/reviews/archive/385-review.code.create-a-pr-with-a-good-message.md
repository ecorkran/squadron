---
docType: review
layer: project
reviewType: code
slice: create-a-pr-with-a-good-message
targetKind: slice
rulesSource: project
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260918
dateUpdated: 20260919
responseStatus: addressed
reviewedSha: c7a403c97874842f5fffb06a5131e07af6180119
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "`compose_one_shot` does not filter the SDK's duplicate result/tool messages, corrupting the body on the default profile"
    location: "src/squadron/pr/body.py#compose_one_shot"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`GitRangeUnavailableError` from input gathering is unhandled in `create` — a bad base produces a traceback, contradicting the design's own \"loud 422\" claim"
    location: "src/squadron/cli/commands/pr.py#create"
  - id: F003
    severity: concern
    category: validation
    summary: "No guard against an empty commit range: the task file's \"impossible\" claim is unenforced, and the title silently degrades to empty"
    location: "src/squadron/pr/inputs.py#gather_commits_and_slice"
  - id: F004
    severity: concern
    category: robustness
    summary: "`_strip_model_headings` deletes every `#`-prefixed line, not just markdown headings — fenced code blocks in model prose are silently corrupted"
    location: "src/squadron/pr/body.py#_strip_model_headings"
  - id: F005
    severity: concern
    category: test-quality
    summary: "Two spec'd test properties are asserted only by their names: dry-run/real body equality and \"exactly one write\""
    location: "tests/cli/test_pr_create.py#test_dry_run_body_equals_the_next_real_runs_body"
  - id: F006
    severity: concern
    category: dead-code
    summary: "`git_utils.current_branch` is added and tested but has no production caller — duplicated detached-HEAD logic"
    location: "src/squadron/review/git_utils.py#current_branch"
  - id: F007
    severity: concern
    category: duplication
    summary: "~120 lines of fixtures duplicated verbatim across the two new CLI test files instead of a shared conftest"
    location: "tests/cli/test_pr_create.py"
  - id: F008
    severity: note
    category: observability
    summary: "`_read_design_h1` swallows an unreadable design file silently while `_read_design_excerpt` logs a WARNING for the same failure"
    location: "src/squadron/pr/body.py#_read_design_h1"
  - id: F009
    severity: note
    category: consistency
    summary: "Verdict rendering in the provenance block is untested and may render as `Verdict.PASS` if `Verdict` is not str-backed"
    location: "src/squadron/pr/body.py#_provenance_block"
  - id: F010
    severity: note
    category: consistency
    summary: "The `\"sdk\"` default and profile literals are scattered rather than referencing `ProfileName.SDK`"
    location: "src/squadron/cli/commands/pr.py#create"
  - id: F011
    severity: note
    category: design
    summary: "The `resolve_locator` extraction leaves `parse_target` running twice on the `show` path"
    location: "src/squadron/cli/commands/pr.py#resolve_and_fetch_pull_request"
---

# Review: code — slice 0

**Verdict:** FAIL
**Model:** z-ai/glm-5.3

## Findings

### [FAIL] `compose_one_shot` does not filter the SDK's duplicate result/tool messages, corrupting the body on the default profile

The collection loop appends *every* response's content: `async for response in agent.handle_message(message): output_parts.append(response.content)`. Every other consumer of `handle_message` filters SDK-tagged messages first: `run_review_with_profile` (src/squadron/review/review_client.py:248-277, with the comment "SDK providers emit both an AssistantMessage and a ResultMessage with identical content (skip the duplicate), plus separate tool_use/tool_result messages... that are not part of the review's actual prose") and `capture_summary_via_profile_with_telemetry` (src/squadron/pipeline/summary_oneshot.py) both `continue` on `sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result")`, and `src/squadron/core/models.py` documents `SDK_RESULT_TYPE` with "Consumers should skip messages where metadata['sdk_type'] == SDK_RESULT_TYPE." The CLI default is `--profile sdk` (pr.py), and D3 deliberately routes `sdk` through this composer. Consequences on the default profile: (1) each body section's prose arrives twice (assistant text + identical result text), and `check_body_complete` cannot catch it — duplicated prose passes the structural "filled" test — so the PR body ships corrupted; (2) `_compose_title`'s candidate becomes `"title\ntitle"`, which contains a newline, so the model-composed title *always* falls back to the first commit's subject, silently disabling the D4a third term. Every test fakes the agent with a single message (`_make_fake_agent` yields one `Message` with no `sdk_type`), so the suite cannot see this. Fix: apply the same `sdk_type` filter the two existing consumers use, and add a test whose fake agent yields `assistant_text` + `result` messages (the shape `tests/pipeline/test_summary_oneshot.py:141-168` already models).

### [CONCERN] `GitRangeUnavailableError` from input gathering is unhandled in `create` — a bad base produces a traceback, contradicting the design's own "loud 422" claim

`inputs = gather_commits_and_slice(...)` sits outside every `try` in `create`, and `commits_in_range` (src/squadron/review/git_utils.py) raises `GitRangeUnavailableError` — not a `CodeHostError` — when git cannot answer or the range's refs don't resolve locally. That is a reachable, ordinary case: `select_base` verifies the base against the *host* (`branch_exists`/`default_branch` via `gh`) but never verifies the ref exists in the *local* clone, and `--base` is used verbatim with no confirmation at all. So `sq pr create --base typo` (or a host default branch name never fetched locally) fails with an unhandled traceback instead of the rendered refusal every other path produces. The design comment in `select_base` says "a bad value gets a loud 422 from `open_pull_request`" — but input gathering runs before the write and preempts that 422 with an exception the command doesn't render (and with `--dry-run` there is no 422 at all). The D8 failure matrix covers the five host call sites but misses this seventh I/O path. Relatedly, `_shas_in_range` (src/squadron/pr/inputs.py) silently returns `[]` on the same git failure, which would make the provenance section's "No squadron review covers this branch's commits" a false claim if reached by a direct caller.

### [CONCERN] No guard against an empty commit range: the task file's "impossible" claim is unenforced, and the title silently degrades to empty

Task 7.1 asserts "Always present — an empty range is impossible here, since a PR with no commits cannot be opened," but nothing enforces it. `check_head_pushed` only verifies the head branch exists remotely and matches local HEAD — a branch pushed at the same commit as the base (zero commits) passes every precondition, and `commits_in_range` legitimately returns `[]`. Downstream: `_compose_title`'s fallback is `commits[0].subject if commits else ""` (src/squadron/pr/body.py), so the resolved title is the empty string; the "What changed" section has `has_input=True` but an empty deterministic block and a prompt summarizing nothing; the model is called; and only then does `open_pull_request` fail (or `--dry-run` prints an empty title line). This violates both D8's principle (a refusal decidable without a model call should happen before it) and the project's no-silent-fallback rule. A guard refusing when `commits` is empty — before composition — closes it.

### [CONCERN] `_strip_model_headings` deletes every `#`-prefixed line, not just markdown headings — fenced code blocks in model prose are silently corrupted

The implementation drops any line whose `lstrip()` starts with `#`, but the docstring (and D4) promise only "any markdown heading line." A model response containing a fenced code block (a shell or Python snippet quoting a commit, for instance) loses its comment lines, producing a broken block in the posted PR body with no warning — silent content loss, which is exactly the failure mode this project's rules target. The check `line.lstrip().startswith("#")` should at minimum match actual heading syntax (`^#{1,6}\s`) and ideally ignore fenced regions. Note the prompts request "a short paragraph," so likelihood is moderate, but the function's contract and behavior disagree.

### [CONCERN] Two spec'd test properties are asserted only by their names: dry-run/real body equality and "exactly one write"

`test_dry_run_body_equals_the_next_real_runs_body` runs the dry run, runs the real create, and then asserts only `dry_result.exit_code == 0`, `real_result.exit_code == 0`, and `dry_body.strip()` — it never compares the dry-run body to the body the real run sends. The comparison is cheap to make: `RecordedCall` (tests/codehost/fake_runner.py) captures `stdin`, so the POST call's JSON payload's `body` field can be extracted and compared, which is what Task 13.2 ("dry-run output equals the body the next real run sends") asks for. As written, the D8 "one title and one body shared by both paths" claim is untested. Similarly, `test_happy_path_makes_exactly_one_write` asserts only exit code and the URL — this file's `patched_host` fixture never captures the runner (unlike `test_pr_create_failures.py`'s), so the write count is never checked despite the test's name.

### [CONCERN] `git_utils.current_branch` is added and tested but has no production caller — duplicated detached-HEAD logic

The diff adds `current_branch(cwd)` with its own `DetachedHeadError`, plus a dedicated test file (tests/review/test_git_utils_pr.py), but the CLI uses its own `_current_branch(host, ...)` (src/squadron/cli/commands/pr.py) instead, raising `TargetUnresolvableError` for the same condition. A repo-wide grep confirms no production caller of `git_utils.current_branch`. The seam rationale in `_current_branch` (reading through `host.runner` so a test can fake every process call through one factory) is sound, but then the `git_utils` version is dead code, and the codebase now carries two implementations of "current branch with a detached-HEAD refusal" in two exception types with near-identical messages — a DRY violation against CLAUDE.md ("Do not duplicate logic") and "resist adding complexity." Either the CLI should consume the helper (accepting a runner-injected variant), or the unused one should not ship.

### [CONCERN] ~120 lines of fixtures duplicated verbatim across the two new CLI test files instead of a shared conftest

`_isolated_cf`, the `repo` fixture, `_local_head_sha`, `patched_host`, `_make_fake_message`, `_make_fake_agent`, and the `_fake_composer` registration block are copy-pasted between tests/cli/test_pr_create.py and tests/cli/test_pr_create_failures.py (with a third, differently-shaped `patched_host` variant in tests/cli/test_pr_resolve_locator.py). The project's testing rules explicitly say "Use `conftest.py` for shared fixtures; keep individual test files clean," and drift between the copies is already visible (the failures file's `patched_host` captures the runner; the other's does not). Related hygiene: the autouse fixtures write directly into `registry_mod._REGISTRY` without restoration (only `test_summary_oneshot.py`'s new test and `test_body.py`'s sdk test use try/finally), so fake providers persist for the whole session.

### [NOTE] `_read_design_h1` swallows an unreadable design file silently while `_read_design_excerpt` logs a WARNING for the same failure

Both functions read the same file and catch `OSError`; `_read_design_excerpt` logs a WARNING ("could not read slice design ... for composition") while `_read_design_h1` returns `None` with no log. The slice's own convention elsewhere (src/squadron/pr/inputs.py) is that every degradation emits a WARNING naming the condition. The title falling through to the model because the design file vanished is a degradation an operator should be able to see.

### [NOTE] Verdict rendering in the provenance block is untested and may render as `Verdict.PASS` if `Verdict` is not str-backed

The block interpolates `facts.review_verdict` directly (`f"... (verdict: {facts.review_verdict}, sha: ...)"`). Whether that renders as `PASS` depends on `Verdict` subclassing `str`/`StrEnum`, which I could not verify within this review; existing code elsewhere deliberately uses `Verdict.X.value` (src/squadron/review/persistence.py), which suggests not relying on interpolation. No test asserts how the verdict appears in the body (`test_deterministic_facts_appear_verbatim` checks the sha and design path but not the verdict). If `Verdict` is a plain `Enum`, the posted body reads "verdict: Verdict.CONCERNS". Worth one assertion in `tests/pr/test_body.py` to pin the behavior.

### [NOTE] The `"sdk"` default and profile literals are scattered rather than referencing `ProfileName.SDK`

`profile: str = typer.Option("sdk", ...)` hardcodes the profile name as a literal, while `src/squadron/providers/profiles.py` defines `ProfileName.SDK` for exactly this value (CLAUDE.md: define a value once, reference it everywhere). The test files repeat the literal (`_FAKE_PROFILE = "sdk"` in two files). Referencing the constant would make a future rename a one-place edit.

### [NOTE] The `resolve_locator` extraction leaves `parse_target` running twice on the `show` path

`resolve_locator` computes `parsed = parse_target(target)` internally, discards it, and `resolve_and_fetch_pull_request` immediately re-parses with `parse_target(target)` to feed `resolve_pull_request`. It's pure and harmless, but returning `parsed` alongside the locator (or accepting it) would remove the redundant parse and keep the extraction clean for future callers.

## Response

All eleven findings accepted and fixed. Verified after the changes: `ruff format`
clean, `ruff check` clean, `pyright` 0 errors, full suite **3 failed / 4205 passed /
6 skipped**. The three failures are `tests/documents/test_schema_drift.py`, the known
context-forge #88 out-of-root symptom this worktree already carried — an untouched
file, failing identically before these changes.

### [FAIL] F001 — `compose_one_shot` kept the SDK's duplicate result and tool messages

Confirmed and fixed. The loop appended every response; both sibling consumers skip
`sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result")`. `compose_one_shot` now
applies the same filter through a module constant, `_NON_PROSE_SDK_TYPES`
(`src/squadron/pr/body.py`). Added
`test_sdk_duplicate_result_and_tool_messages_are_skipped`, whose fake agent yields
`assistant_text` + `tool_use` + `tool_result` + a duplicate `result` and asserts the
output is the single line — the shape that, unfiltered, produced `"title\ntitle"` and
disabled D4a's third term. The consequences were not reproduced live: the `sdk`
profile cannot run inside a Claude Code session (`CLAUDECODE` nested-session
protection), which is also why 16.2 never saw this. PR #116 was composed with
`openai/gpt-4o-mini` and is unaffected.

### [CONCERN] F002 — `GitRangeUnavailableError` was unhandled in `create`

Confirmed and fixed. `create` now wraps input gathering and the review scan, rendering
`GitRangeUnavailableError` as a red refusal plus a hint to fetch the base or pass
`--base`, exit 1. `_shas_in_range` no longer returns `[]` on a git failure — it raises
the same error, so the provenance section can never claim "no review covers these
commits" because git could not answer. Tests:
`test_base_absent_from_the_local_clone_is_a_rendered_refusal` (CLI: exit 1, a
`SystemExit` rather than a traceback, no composer call, no write) and
`test_review_scan_raises_when_the_range_does_not_resolve`.

### [CONCERN] F003 — no guard against an empty commit range

Confirmed and fixed. `gather_commits_and_slice` raises the new `EmptyCommitRangeError`
when `base..head` is empty — before any cf or model call, per D8 — and `create`
renders it. `_compose_title`'s silent `""` fallback is gone; the fallback is
`commits[0].subject`, with the non-empty guarantee now enforced upstream rather than
asserted in a task note. Tests: `test_empty_commit_range_is_refused` and the CLI-level
`test_empty_commit_range_is_refused_before_composition` (a base at head's own commit).

### [CONCERN] F004 — `_strip_model_headings` dropped every `#`-prefixed line

Confirmed and fixed. It now drops only ATX heading syntax (`^ {0,3}#{1,6}(\s|$)`) and
never inside a fenced block (backtick or tilde fences tracked by opening marker).
`test_only_heading_syntax_outside_fences_is_stripped` covers a fenced `# comment`, a
fenced `## line`, and a `#123` issue reference, alongside real model headings that
are still removed.

### [CONCERN] F005 — two tests asserted only their names

Confirmed and fixed. The dry-run test is now
`test_dry_run_title_and_body_equal_what_the_next_real_run_sends`: it parses the real
run's POST payload from `RecordedCall.stdin` and compares both title and body to the
dry-run's stdout. `test_happy_path_makes_exactly_one_write` asserts
`len(write_calls()) == 1`. The neighbouring tests picked up the same rigor now that
the runner is reachable: dry-run asserts zero writes, `--base` asserts the payload's
`base`, and the identity and presence-check refusals assert no write.

### [CONCERN] F006 — `git_utils.current_branch` had no production caller

Confirmed; the unused one does not ship. `current_branch`, `DetachedHeadError`, and
`TestCurrentBranch` are deleted. The CLI's `_current_branch` — the one that reads
through `host.runner` — had no test of its own, so
`test_detached_head_is_refused_with_no_host_call` was added for it.

### [CONCERN] F007 — fixtures duplicated across the two CLI test files

Confirmed and fixed. Helpers and the scripted-call builders moved to
`tests/cli/pr_create_support.py`; the fixtures (`isolated_cf`, `pr_create_repo`,
`pr_create_host`, `fake_composer`) moved to `tests/cli/conftest.py` as opt-in fixtures
(`pytestmark = usefixtures(...)`), not autouse, so they do not touch the rest of
`tests/cli`. The drift is gone with the copies: one `HostHarness` carries both the
script and the captured runner. The per-site prefix ladder is now one ordered
`CALL_SITES` table with `script_through` / `script_before`. The fake provider is
registered with `monkeypatch.setitem`, so `_REGISTRY` is restored after each test.
`test_pr_resolve_locator.py`'s differently-shaped `patched_host` was left alone: it
serves a different function under test.

### [NOTE] F008 — `_read_design_h1` swallowed an unreadable design silently

Fixed. It logs a WARNING naming the file and the fall-through to a model-composed
title. `test_unreadable_design_warns_before_falling_through_to_the_model` asserts it.

### [NOTE] F009 — verdict rendering in the provenance block was untested

`Verdict` is a `StrEnum` (`src/squadron/review/models.py`), so the block already
rendered `PASS`. Pinned by `test_the_provenance_block_renders_the_verdicts_value`.

### [NOTE] F010 — scattered `"sdk"` literal

Fixed. `create`'s default is `ProfileName.SDK`; the tests' `FAKE_PROFILE` references
the same member, in one place.

### [NOTE] F011 — `parse_target` ran twice on the `show` path

Fixed. `resolve_locator` returns the parsed target alongside the host and locator, and
`resolve_and_fetch_pull_request` consumes it. The locator test asserts the returned
value.

### Run Digest

- Response length: 12209 chars
- Response is newline-free: no
- Tool calls made: 34
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 88204
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
