---
docType: tasks
slice: fix-pipeline
project: squadron
lld: user/slices/423-slice.fix-pipeline.md
dependencies:
- 422
projectState: v0.24.23 released, main is the target (git.integration_branch unset).
  Slices 421 and 422 have tasks written, not implemented. Slice 423 design written.
dateCreated: 20261106
dateUpdated: 20261106
status: not_started
turns: 49
promptTokens: 3373497
cachedTokens: 3232154
cacheWriteTokens: 141277
completionTokens: 38088
durationSeconds: 291.1
costUsd: 1.269654
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 1.2696539
    completionTokens: 38088
---

## Context Summary
- Working on slice 423: the built-in `fix` pipeline (`sq run fix <issue>`), the producer that 424 replays. Design: `user/slices/423-slice.fix-pipeline.md`; its D-numbers (D1–D9) are cited below instead of repeating them.
- Delivers: a `fix` step expanding to `fix-context → dispatch → commit`; `fix.yaml`; the fix prompt as a data file; the fix report and its checks; two issue sources (fetched, frozen file); two commit destinations (`target`, `current`); prompt-only parity through `sq _fix-prompt` and `sq _commit --subject fix`; docs and CHANGELOG.
- Order follows the design's Development Approach: pure modules first (Tasks 3–4), the commit (Tasks 5–6), the prompt and context action, step and pipeline with the executor test (Tasks 7–11), prompt-only (Tasks 12–13), docs for file mode (Task 14), the fetched source (Task 15), live walkthrough (Task 16).
- **Precondition for Task 15 (and so for Task 16):** 422's `CodeHost.get_issue` and `render_issue` (422 Tasks 5–6) are implemented and committed. At the time of writing neither exists (422 is not implemented), so Task 15 stops with `BLOCKED:` unless 422 Tasks 5–6 land first; Tasks 1–14 are complete and committed by then. Until Task 15, the fetch path fails explicitly (Task 3), so Tasks 1–14 ship nothing undefined; they use file mode and need nothing from 422.
- Design corrections found while reading the code (the design is not edited; these tasks follow the corrections):
  - **Dispatch fallback.** D2 says `fix-context` outputs `operation: build_context` and `context`, and that `DispatchAction` does not change. It does not work: the fallback in `actions/dispatch.py` (`_resolve_prompt`) accepts only a result whose `action_type` is `cf-op` and reads the prompt from `outputs["stdout"]`. Task 7 widens that one condition to any prior result with `operation: build_context` and a `stdout`, and `fix-context` outputs `stdout`. No other dispatch behavior changes.
  - **No attribution lines.** D6 refers to attribution lines the commit action adds. It adds none. The message is `fix: {summary}`, a blank line, `Fixes #{n}`, and nothing else.
  - **Name clash.** The design names both a StrEnum (file/github) and the fetch-or-read class `IssueSource`. The enum keeps the name `IssueSource` (Patterns and Conventions); the class is `IssueTextLoader`.
  - **Prompt loading.** D8 says `importlib.resources`; the code has no direct use of it. Packaged data goes through `squadron.data.data_dir()` (which wraps it); the prompt does too.
  - **`--io-dir` in prompt-only.** `sq run --prompt-only` refuses `--io-dir`, so `sq _fix-prompt --io-dir` is not reachable from `/sq:run`. The flag is built as the design's contract says and tested directly (Task 12); the renderer never passes it.
  - **One commit path.** D9's `sq _commit` and the SDK commit action share one function. The action reads the issue number, destination, start HEAD, start branch and reply text from this step's prior outputs; `sq _commit` builds those same prior outputs from its flags and report file.
  - **Start branch (D5, D9).** D5 checks HEAD only. `fix-context` also records `start_branch`, and the commit refuses when the branch differs, so under `commit-to: current` an agent that switches to another branch at the same commit is caught. `sq _commit` gets a `--start-branch` flag, read at render time like `--start-head`.
- Shared names (defined once, Task 2): leaf module `pipeline/fix_keys.py` holds the param keys, output keys, `CommitTo`, `IssueSource`. The design's component list lacks it; the design's Patterns section requires it.
- Git state: an unreadable or unknown git state (`GitEnvironmentError` from `current_branch` or `read_integration_target`) is never turned into a failed action: it propagates and ends the run, as in `CommitAction` and `DispatchAction`; the hidden commands catch it at the process boundary, as `commit_run.py` does. A git command that merely reports an error (`changed_paths` returns text, `read_head` returns `None`) is a refusal.
- Nothing here pushes, posts to an issue, opens a PR or closes an issue. Tests live in `tests/pipeline/`, `tests/cli/` and `tests/load/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests.
- Load test: `FixContextAction` runs its git, file and loader work in `asyncio.to_thread`. Task 9 adds a load test with a fake loader that a blocking load does not starve the event loop, and verifies CI runs it; Task 15 adds the real-loader case. A bounded call also has a timeout test.
- Effort 3/5. Next planned slice: 424.

## Tasks

### Task 1: Create the slice branch
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file as modified or untracked, commit it there by path (`git add <task file>`, then `git commit -- <task file>` as `docs: revise slice 423 tasks`); planning work commits to the target, not a slice branch. Commit `DEVLOG.md` the same way only if `git diff DEVLOG.md` shows nothing but the slice 423 entry; otherwise leave it unstaged and stage every later commit by path, so unrelated DEVLOG changes never ride along
  - [ ] Success: `git status --short` does not list the task file
- [ ] `git checkout -b 423-slice.fix-pipeline <target>` (or switch to it if it exists)
  - [ ] Success: `git branch --show-current` prints the slice branch and `git log -1 --format=%s -- project-documents/user/tasks/423-tasks.fix-pipeline.md` shows the task file already in its history

### Task 2: Shared names and enum entries
- [ ] Create `src/squadron/pipeline/fix_keys.py`, a leaf module (imports nothing from `squadron.pipeline` except stdlib): the step/pipeline param keys `issue`, `issue-file`, `commit-to`; the `fix-context` output keys (`issue_number`, `issue_source`, `issue_text_sha256`, `start_head`, `start_branch`, `commit_to`); `CommitTo` StrEnum (`target`, `current`); `IssueSource` StrEnum (`file`, `github`)
- [ ] In `pipeline/git_ops.py` rename the private `_DETACHED_HEAD` (the value `current_branch` returns for a detached HEAD) to a public `DETACHED_HEAD` and update its three uses in that file; every later task compares against this constant, never the literal
- [ ] Add `StepTypeName.FIX = "fix"` (`pipeline/steps/__init__.py`), `ActionType.FIX_CONTEXT = "fix-context"` (`pipeline/actions/__init__.py`), `CommitSubject.FIX = "fix"` (`pipeline/commit_plan.py`), `FailureKind.FIX_REPORT = "fix_report"` (`pipeline/failure_kind.py`, with a comment like its neighbors)
- [ ] Find every exhaustive use of these four enums and keep it working: `grep -rn "CommitSubject\|FailureKind\|ActionType\.\|StepTypeName\." src tests` for `match` statements, dicts keyed by every member, and tests that count members (for example the commit-subject table in `_check_placement`, `template_for_subject`, the run-outcome reader)
  - [ ] A member with no meaning for `fix` in an existing table gets an explicit entry or an explicit refusal, not a silent default
  - [ ] Success: `uv run pytest tests/pipeline tests/cli -q -x` passes with the four members added and the rename done, and nothing else wired

### Task 3: Issue reference and frozen-file source (D2)
- [ ] `src/squadron/pipeline/fix_issue.py`: `parse_issue_ref(value) -> int` accepting a positive integer with an optional leading `#`, surrounding whitespace ignored; anything else (empty, zero, negative, `abc`, `1.5`, `#`, `12x`) raises `ValueError` naming the value
- [ ] In the same module, `IssueTextLoader` with a file path: resolves `issue-file` against the io-dir when one is given, else against the working directory; refuses a `..` path using `dispatch_keys.path_error`; reads UTF-8 verbatim. Result carries the text, `IssueSource.FILE`, and `sha256` of the UTF-8 bytes. Failures raise `IssueTextError` naming the path and cause:
  - [ ] Checked refusals (`..` path, missing file, not a regular file, empty or whitespace-only text) are logged at WARNING before raising
  - [ ] A caught `OSError` or `UnicodeDecodeError` from reading is logged with `logger.exception` (ERROR) and re-raised as `IssueTextError ... from exc`
- [ ] Define a small `IssueLoader` Protocol in `fix_issue.py`: `load(issue_number, issue_file, io_dir) -> IssueText` (text, `IssueSource`, sha256); `IssueTextLoader` implements it. `IssueTextLoader` takes a `CodeHost` factory in its constructor. Until Task 15, the non-file branch raises `IssueTextError` saying issue fetching is not built yet and to pass `issue-file`, without calling the factory (so the default `fix` pipeline fails explicitly, not undefined). In file mode the factory is never called
- [ ] Tests `tests/pipeline/test_fix_issue.py`: parametrized valid refs (`301`, `#301`, ` #7 `) and invalid refs; a file read verbatim (trailing newline and non-ASCII kept) with its sha256; relative path under io-dir and under cwd; `..` refused; missing, empty, directory each raise with a WARNING record; non-UTF-8 raises with an ERROR record (`caplog`); file mode with a factory that raises if called; the non-file branch raises the not-built-yet error and never calls the factory
  - [ ] Success: tests pass

**Commit**: `feat: add fix issue reference parsing and frozen file source`

### Task 4: Fix report (D4)
- [ ] `src/squadron/pipeline/fix_report.py`: Pydantic `FixReport` (`summary`, `failing_tests`, `failed_before_change`, `gates` as a list of `{command, exit_code}`) and `FixReportError(ValueError)`. `parse_fix_report(reply: str) -> FixReport` uses `extract_json_object` (`pipeline/actions/dispatch_io.py`); extra fields are ignored (lenient parsing)
- [ ] Each defect raises `FixReportError` with a message naming the field: no JSON object in the reply; `summary` empty, multi-line, or starting with `fix:`; `failing_tests` empty; `failed_before_change` not the boolean `true` (strict: the string `"true"` fails); `gates` empty; any `exit_code` not integer 0
- [ ] A `blocked` key present but null, empty, whitespace-only or not a string raises `FixReportError` naming `blocked`; it is neither ignored nor treated as a block
- [ ] A `blocked` key with a non-empty string reason raises `FixReportError` whose message starts with `fix blocked:` and carries the reason, whatever the other fields hold or lack. Check `blocked` before the field checks
  - [ ] Success: the model never accepts a report with a missing required field; one error message names one field
- [ ] Tests `tests/pipeline/test_fix_report.py`: a valid report inside prose and inside a code fence; every defect above (parametrized, asserting the field name is in the message); a `blocked` report with only `blocked`; a `blocked` report with all other fields too; `blocked` as `null`, `""`, `"  "` and `3`; a reply with leading unrelated prose and a trailing report
  - [ ] Success: tests pass

**Commit**: `feat: add fix report parsing and checks`

### Task 5: Fix commit plan (D5, D6)
- [ ] `src/squadron/pipeline/fix_commit.py`: frozen `FixCommitRequest` (`issue_number`, `commit_to: CommitTo`, `start_head`, `start_branch`, `reply_text`), frozen `FixCommitRefusal` (`message`, `failure_kind: FailureKind | None`), frozen `FixCommitPlan` (`plan: CommitPlan`, `report: FixReport`), and `fix_commit_plan(request, cwd, cf_client) -> FixCommitPlan | FixCommitRefusal`
- [ ] Order of checks, each refusal returned (logged at WARNING), nothing staged by this function:
  1. `parse_fix_report`; a `FixReportError` becomes a refusal with kind `FIX_REPORT`
  2. branch: `current_branch(cwd)` must equal `start_branch` and must not be `DETACHED_HEAD`; under `target` it must also equal `read_integration_target(cf_client)`. `cf_client` is not touched under `current`. A `GitEnvironmentError` from either call propagates (Context Summary, Git state)
  3. HEAD: `read_head(cwd)` must equal `start_head`, else a refusal naming both shas (first 12 characters, `unknown` when unreadable) and saying the agent must not commit
  4. `changed_paths(cwd)`: a git error string becomes a refusal; an empty list becomes a refusal with kind `FIX_REPORT` and the text "report claims a fix but the tree has no changes"
- [ ] The plan: `CommitPlan` with the changed paths, `stage_all` false, message `fix: {summary}`, a blank line, `Fixes #{issue_number}`. A summary over 72 characters is kept and logged at WARNING; the message never contains anything else
- [ ] Tests `tests/pipeline/test_fix_commit.py` against a real temporary git repo (use `run_test_git` from `tests/conftest.py`; cf is a `MagicMock` whose `get_config` returns the integration branch): valid report on each destination gives the exact message; wrong branch under `target`; branch differs from `start_branch` under `current` (switch to a new branch at the same commit); detached HEAD under `current`; `current` with a cf mock that raises if called; `current_branch` raising `GitEnvironmentError` propagates; HEAD moved; HEAD unreadable (`read_head` patched to `None`) refuses naming `unknown`; untracked file, modified file, deleted file and a rename all appear in the plan paths; a report defect refuses before any branch or HEAD check runs; a 100-character summary is kept and logs a WARNING (`caplog`)
  - [ ] Success: tests pass
- [ ] Its own test for nothing staged (design D5: a report with no changes fails): a valid report on a clean tree, and again on a tree where only an ignored file changed, each return a refusal with kind `FIX_REPORT` and the exact text "report claims a fix but the tree has no changes", and `git log` is unchanged
  - [ ] Success: the test passes

### Task 6: `CommitAction` handles `CommitSubject.FIX`
- [ ] In `fix_commit.py` add `fix_plan_from_context(context) -> FixCommitPlan | FixCommitRefusal`: it builds the `FixCommitRequest` from this step's prior outputs (`results_for_step(context.prior_outputs, context.step_name)`, `pipeline/models.py`; the `fix-context` result gives issue number, destination, start HEAD and start branch; the `dispatch` result's `response` is the reply text; a missing result is a refusal naming it) and calls `fix_commit_plan` with `context.cwd` and `context.cf_client`
- [ ] In `pipeline/actions/commit.py` `_commit`, before the guarded and `target is None` branches, delegate when `target.subject is CommitSubject.FIX` to that helper: a refusal becomes `ActionResult(success=False)` with its message and, when it has a kind, `metadata[FAILURE_KIND_KEY]` (give `_failure` an optional metadata argument); a plan goes to the existing `_stage_and_commit`, and the result's `metadata["fix_report"]` is the report's `model_dump()`. The existing `_check_placement` and `build_commit_plan` paths are not used for `FIX`
  - [ ] Success: `commit.py` stays at or under 300 lines (`wc -l`; it is 286 now), so the branch is one delegation, not an inlined copy of the checks
- [ ] Tests (`tests/pipeline/actions/test_commit.py`, or a new `test_commit_fix.py` beside it): a fix commit on a real repo lands one commit with the expected message, the `committed`/`sha` outputs and `metadata["fix_report"]`; a report defect fails with `failure_kind` `fix_report` and `git status` still shows the agent's changes and `git log` shows no new commit; HEAD moved fails without that kind; missing `fix-context` result fails by name
  - [ ] Success: tests pass; `uv run pytest tests/pipeline/actions/test_commit.py tests/pipeline/test_guarded_commit.py -q` still passes

**Commit**: `feat: commit fixes from a checked fix report`

### Task 7: Dispatch prompt fallback accepts any `build_context` result (design correction)
- [ ] In `actions/dispatch.py` `_resolve_prompt`, drop the `result.action_type == ActionType.CF_OP` test from the fallback loop so a prior result carrying `operation: build_context` and a non-`None` `stdout` supplies the prompt. Keep the reverse scan (most recent wins), the `PromptSource.BUILD_CONTEXT` source and the `cf_version`/`guide_version` copying unchanged. Update the docstring of `_resolve_prompt` and the comment in the loop to say any action may supply it
  - [ ] Success: no other branch of `_resolve_prompt` changes
- [ ] Tests (extend `tests/pipeline/actions/test_dispatch.py` or `test_dispatch_prompt_identity.py`): a prior `fix-context`-typed result with `operation: build_context` and `stdout` becomes the delivered prompt with source `build_context`; a prior result with `stdout` but no `operation` is ignored; the existing cf-op case still passes
  - [ ] Success: `uv run pytest tests/pipeline/actions -q` passes

**Commit**: `feat: let any action supply a dispatch's build_context prompt`

### Task 8: The fix prompt (D8)
- [ ] Create `src/squadron/data/prompts/fix.md` (new directory; `pyproject.toml` builds `packages = ["src/squadron"]`, so add an `__init__.py` only if `data/templates` has one). Contents in the order D8 lists: the task (fix issue #N following the project's fix rule); the steps (write a test that fails for the reported reason, run it and confirm it fails, make the change, run the project's format, lint, typecheck and touched-area test commands as its rules name them); the constraints (do not commit, push, switch branches, or fetch the issue); the report fields by name and meaning (D4) and the `blocked` exit; the issue text between explicit begin and end markers. Exactly two placeholders: `{issue_number}` and `{issue_text}`
  - [ ] No example values, no sample JSON object, no braces other than the two placeholders (hallucination trap, D4/D8)
- [ ] Prompt loading: a function in `fix_issue.py` (or `fix_context.py`) that reads the file through `data_dir() / "prompts" / "fix.md"` and substitutes with two `str.replace` calls, number first and text last, so braces inside the issue text are never substituted or treated as format fields
- [ ] Tests `tests/pipeline/test_fix_prompt.py`: the prompt file contains only the two placeholders and no `{"`; both substitutions land; issue text with braces and a literal `{issue_number}` stays verbatim and is not substituted
  - [ ] Success: tests pass

**Commit**: `feat: add the fix prompt`

### Task 9: The `FixContextAction` (D2, D5)
- [ ] `src/squadron/pipeline/actions/fix_context.py`: `FixContextAction` (`action_type` `FIX_CONTEXT`; constructor takes an `IssueLoader` (Task 3), default `IssueTextLoader(lambda: build_github_host(SubprocessRunner()))`, whose factory is only called in fetch mode; `validate` returns no errors, as `CommitAction` does). `execute` runs the git, file and loader work in `asyncio.to_thread`. Refusals are `ActionResult(success=False)` logged at WARNING, each before anything else runs, in this order:
  1. issue ref invalid (`parse_issue_ref`)
  2. `commit-to` not a `CommitTo` value
  3. dirty tree: `changed_paths` non-empty → message lists the paths; a git error string → refusal with it
  4. branch: `current_branch(cwd)`; `DETACHED_HEAD` is refused under both destinations; under `target` the branch must equal `read_integration_target(context.cf_client)`. A `GitEnvironmentError` from either call propagates (Context Summary, Git state); no `try` around them
  5. `read_head(cwd)` is `None` → refusal "cannot read HEAD" (no start point to record)
  6. issue text through `IssueTextLoader`; a caught `IssueTextError` becomes the refusal (comment: it was logged where it was raised and carries the cause, so the action only reports it)
- [ ] Success outputs: `operation: build_context`, `stdout` (the assembled prompt), and the `fix_keys.py` output keys (`issue_number`, `issue_source`, `issue_text_sha256`, `start_head`, `start_branch`, `commit_to`). No `CodeHost` is built in file mode
- [ ] Register in `src/squadron/pipeline/executor.py` beside the other action imports (the `# Import modules to trigger registration` block at about line 529, and its `_ = (...)` tuple)
- [ ] Tests `tests/pipeline/actions/test_fix_context.py` on a real temp git repo, file mode: success outputs and prompt contents (issue number and text present, no unsubstituted placeholder left); one test per refusal (untracked file listed, branch is not the target, detached HEAD under each destination, invalid ref, invalid `commit-to`, missing and empty file, `read_head` patched to `None`); `target` with a cf mock whose `get_config` raises `ContextForgeError` raises `GitEnvironmentError` naming the key; `current_branch` patched to raise `GitEnvironmentError` propagates; `current` with `issue-file` never touches cf or a host.
  - [ ] Success: tests pass
- [ ] Load test `tests/load/test_fix_context_blocking.py` (module docstring in the style of `tests/load/test_grep_timeout.py`): a fake `IssueLoader` whose `load` blocks for a fixed time; run `FixContextAction.execute` concurrently with a ticker coroutine and assert the ticker's longest gap stays well under the block time, so the work runs off the event loop; a second case runs several `execute` calls concurrently and asserts they finish in about one block time, not the sum. Task 15 adds the real-loader case to this file
  - [ ] Success: the test passes under `uv run pytest tests/load/test_fix_context_blocking.py -q`; it has no `network` marker
- [ ] Confirm CI gates it: read `.github/workflows/ci.yml` and `pyproject.toml` `[tool.pytest.ini_options]`; the `uv run pytest` step passes no `-m`, `--ignore` or path that excludes `tests/load`, and `tests/load` is inside `testpaths`. The workflow runs only on pushes and pull requests to `main`, so slices merged into an integration branch are gated when that branch reaches `main`
  - [ ] Success: no exclusion found, or the exclusion is recorded in the DEVLOG entry

**Commit**: `feat: add the fix-context action`

### Task 10: `FixStepType` and `fix.yaml` (D1, D7)
- [ ] `src/squadron/pipeline/steps/fix.py`: `FixStepType` (`step_type` `FIX`; `known_keys` = `issue`, `model`, `issue-file`, `commit-to`). `validate`: `issue` must parse with `parse_issue_ref`; `commit-to` a `CommitTo` value; a value that is exactly one `{name}` token (letters, digits, `_`, `.`, `-` between the braces; `fix.yaml` writes `"{issue}"`, and the loader validates before params are bound) is an unresolved param placeholder and is accepted by `validate`, because `FixContextAction` checks the resolved value (Task 9); any other value, including a malformed one such as `"{301"`, is checked now. Same rule for `issue-file` (a string, `..` refused by `path_error`) and `model` (a string). Each error names the field and value
- [ ] `needs_context_forge` returns false (D7, with the reason in its docstring). `expand` returns `fix-context` (issue, issue-file, commit-to), `dispatch` (model), `commit` (`SUBJECT_PARAM: CommitSubject.FIX`)
- [ ] Register in `steps/__init__.py` `bootstrap_step_types` (alphabetical import, with the other pyright-ignore lines)
- [ ] `src/squadron/data/pipelines/fix.yaml` exactly as D1 gives it (params `issue: required`, `model: sonnet`, `issue-file: ""`, `commit-to: target`; one `fix:` step)
- [ ] Tests `tests/pipeline/steps/test_fix_step.py`: validate (each error; `#301`, `301`; a `{issue}` placeholder accepted; `{301` rejected), `expand` order and configs, `known_keys`, `needs_context_forge` false, `any_step_needs_context_forge` false for the loaded `fix` pipeline. Extend `tests/pipeline/test_builtin_pipelines.py` expectations if they list names; `fix` passes strict validation
  - [ ] Success: `uv run pytest tests/pipeline/steps tests/pipeline/test_builtin_pipelines.py tests/pipeline/test_known_keys.py -q` passes
- [ ] `sq pipelines list` shows `fix`; `sq run fix --validate` passes; `sq run fix 301 --dry-run` prints `fix-context`, `dispatch`, `commit` (add summary lines in `executor._summarize_action_config` or `cli/commands/run_dry_run.py` only if the output is blank or wrong for the new action types)
  - [ ] Success: the three commands run on a machine with `cf` off `PATH` for `--validate` and `--dry-run` where the existing cf-free path allows it (#288); record any command that needs cf and why

### Task 11: Executor-level test of `fix.yaml` (Technical Requirements)
- [ ] `tests/pipeline/test_fix_pipeline.py`: load `fix.yaml`, run `execute_pipeline` against a real temp git repo (file mode, `commit-to=current`, no cf, no host) with a fake dispatch action replacing the registered one: it edits a file and returns a valid report in `response`. Follow `tests/pipeline/test_executor_failure_kind.py` and `test_guarded_commit.py` for how actions are faked and the state read
  - [ ] Exactly one new commit; subject `fix: <summary>`, body `Fixes #<n>`; the run state holds the `fix-context` outputs (`issue_source: file`, the sha256, `start_head`, `start_branch`, `commit_to`) and the commit action's outputs
  - [ ] The fake dispatch's received prompt equals the `fix-context` `stdout`
- [ ] Failure cases in the same file: a fake dispatch that commits (HEAD moved) → run fails, one extra commit only (the agent's), none from the pipeline; a fake that switches to a new branch at the same commit → run fails naming the branch; a report defect → run state shows `failure_kind: fix_report` and the tree keeps the edits; a valid report with no edit → `failure_kind: fix_report`, no commit; a `blocked` report → failure with the reason; a dirty tree → fails at `fix-context` and the fake dispatch is never called; `commit-to=target` with a cf mock that cannot read the config → `execute_pipeline` raises `GitEnvironmentError` and the fake dispatch is never called
- [ ] Environment tripwire: in the success case, put `gh` and `cf` scripts that append their arguments to a log file and exit 127 first on `PATH` (real `git` still reachable) and set `GH_TOKEN` empty; the log stays empty. This proves the pipeline invokes neither command; running it under 421's `ScrubbedEnvironment` needs slice 421, which this slice does not depend on, and is deferred to issue #296
- [ ] Cost cap: with `--max-cost` / `pipeline.max_cost_usd` set below the fake dispatch's recorded spend (follow `tests/pipeline/test_executor_cost_cap.py`), the run stops with `failure_kind: cost_cap` and commits nothing
  - [ ] Success: tests pass; `uv run pytest tests/pipeline -q` passes

**Commit**: `feat: add the built-in fix pipeline`

### Task 12: Hidden commands `sq _fix-prompt` and `sq _commit --subject fix` (D9)
- [ ] `src/squadron/cli/commands/fix_prompt_run.py`: hidden `sq _fix-prompt --issue N [--issue-file PATH] [--io-dir DIR] --commit-to MODE`. It runs `FixContextAction.execute` with an `ActionContext` like `commit_run.py` builds (cwd `os.getcwd()`, `RUN_IO_DIR` param when `--io-dir` is given), prints the `stdout` output, and on a refusal prints `Error: {message}` to stderr and exits 1. At the process boundary it catches `GitEnvironmentError` and `ContextForgeError`, logs with `logger.exception`, prints `Error: …` and exits 1, as `commit_run.py` does. Register it in `cli/app.py` as `app.command("_fix-prompt", hidden=True)`
- [ ] `cli/commands/commit_run.py`: add `--issue`, `--commit-to`, `--start-head`, `--start-branch`, `--report-file`. For `--subject fix` all five are required (a missing one exits 1 naming it); read the report file as UTF-8 (a caught `OSError` or `UnicodeDecodeError` is logged with `logger.exception`, then exit 1 with the cause); build the prior outputs the commit action reads (a `fix-context`-typed result with issue number, destination, start HEAD and start branch; a `dispatch`-typed result with `response` = the file's text) and run `CommitAction`. A refusal prints its message (a `blocked` report prints its reason) and exits 1. The five flags are rejected for any other subject. Move the fix wiring into a helper module so `commit_run.py` stays under ~150 lines
- [ ] Tests (`tests/cli/test_commit_run.py`, new `tests/cli/test_fix_prompt_run.py`), on a real temp repo in file mode: `_fix-prompt` prints the prompt, refuses a dirty tree with exit 1, exits 1 on `GitEnvironmentError`; `_commit` commits with a valid report file, refuses each missing flag by name, refuses a defective and a `blocked` report with the same text as `parse_fix_report`, exits 1 on an unreadable report file, rejects the five flags for another subject
  - [ ] Success: tests pass; `tests/cli/test_command_surface.py` and `tests/cli/test_help.py` pass (hidden commands stay hidden)

**Commit**: `feat: add hidden commands for prompt-only fix runs`

### Task 13: Prompt-only rendering and parity (D9)
- [ ] `pipeline/prompt_renderer.py`: add `ActionType.FIX_CONTEXT` to `_BUILDERS`, rendering `sq _fix-prompt --issue N [--issue-file P] --commit-to MODE` (no `--io-dir`: `sq run --prompt-only` refuses it), `shlex.join`ed like `_render_commit`. The fix `commit` action renders `sq _commit --subject fix --issue N --commit-to MODE --start-head SHA --start-branch BRANCH --report-file {tmp_path}`. `SHA` and `BRANCH` are read once (`read_head`, `current_branch`) when `render_step_instructions` builds the step's instructions, before the session runs anything; add a `cwd` keyword (optional, `None` for existing callers) and pass the run's working directory from the call in `cli/commands/run.py` (use the cwd that function's neighbors already use). `cwd` missing, HEAD unreadable or a detached HEAD for a fix commit raises `PromptOnlyUnsupportedError` naming the cause. `dispatch` renders unchanged
- [ ] `commands/sq/run.md`: add `fix-context` to the `action_type` list and a `### fix-context` section (run `command` via Bash; keep its stdout as the assembled context for the next dispatch, as for `cf build`; on exit 1 show the error and stop). In `### commit`, add: when the command contains `{tmp_path}`, write the final JSON report of the dispatch to a temp file, substitute the path, run it, remove the file; on exit 1 show the refusal and stop
- [ ] Check of the `run.md` instructions, `tests/cli/test_run_md_actions.py` (new file): render the `fix` step in prompt-only mode and assert that every `action_type` it emits has a `### {action_type}` section in `commands/sq/run.md`, that the `action_type` list in its JSON example names `fix-context`, and that its `### commit` section mentions `{tmp_path}`
  - [ ] Success: removing the `### fix-context` heading from a copy of `run.md` makes the check fail (assert this once with a temporary copy), and the test passes on the real file
- [ ] Renderer tests (`tests/pipeline/test_prompt_renderer.py`): the fix actions render the exact commands; the HEAD and branch are the repo's at render time; missing `cwd` and detached HEAD raise `PromptOnlyUnsupportedError`
  - [ ] Success: tests pass
- [ ] Parity test `tests/pipeline/test_fix_prompt_parity.py` with two identical temp repos (file mode, `commit-to=current`): (a) the prompt printed by `sq _fix-prompt` (Typer `CliRunner`, `monkeypatch.chdir`) equals the SDK `FixContextAction` `stdout`; (b) the same report through `sq _commit` and through the SDK commit action gives the same commit message; (c) each report defect from Task 4 and a `blocked` report give the same refusal text from both paths; (d) a commit made between rendering and `sq _commit` is refused with the HEAD-moved text by both paths
  - [ ] Success: tests pass; `uv run pytest tests/pipeline tests/cli -q` passes

**Commit**: `feat: run the fix pipeline in prompt-only mode`

### Task 14: Docs and CHANGELOG
- [ ] `docs/PIPELINES.md`: a `### fix` section in the Step Type Catalog (after `branch`, before `### Commits`) covering the step keys, the three actions, the frozen-file issue source (`issue-file`; the fetched source is added in Task 15), the two destinations, the report fields, the refusals (dirty tree, wrong or switched branch, detached HEAD, bad report, `blocked`, HEAD moved) and that `blocked` has no resume path (D4); a `fix` row in the Built-in Pipelines table (`issue`, `model`, `issue-file`, `commit-to`); `fix-context` in the Action Type Catalog; `fix` in the commit-subject table in Commits (subject `fix: {summary}`, body `Fixes #n`, stages every changed path); a line in Prompt-Only Mode naming `sq _fix-prompt` and `sq _commit --subject fix`
  - [ ] The docs state that the pipeline never pushes, posts or closes an issue, and that gates are run and reported by the agent, not by squadron
- [ ] `CHANGELOG.md` under `[Unreleased]`, `### Added`: one or two short user-facing bullets (`sq run fix <issue> -p issue-file=PATH` makes a fix with a failing test, the change, the project's gates and one `fix:` commit with `Fixes #n`; `commit-to=current` for runs outside the target). Say nothing about fetching the issue; Task 15 adds it
  - [ ] Success: `uv run pytest tests/docs tests/cli -q` passes; the docs describe only behavior that exists

**Commit**: `docs: document the fix pipeline`

### Task 15: Fetched issue source (D2, D3)
- [ ] Check the 422 precondition; if any check fails, write `BLOCKED:` and what failed under this task, leave it unchecked and stop (Task 16 waits for it; Task 14 does not):
  - [ ] `grep -n "def get_issue" src/squadron/codehost/protocol.py src/squadron/codehost/github_cli.py` finds both
  - [ ] `grep -n "def render_issue" -A3 src/squadron/benchmark/issue_freeze.py` shows a `cutoff` parameter that accepts `None`
  - [ ] `uv run pytest tests/codehost tests/benchmark/test_issue_freeze.py -q` passes
- [ ] In `IssueTextLoader` replace the Task 3 not-built-yet branch: list remotes (`list_remotes`, `codehost/remotes.py`), select the repository with `select_remote(PullRequestTarget(form=TargetForm.NUMBER, number=n), remotes, host.serves_host)` (bare `#n`), call `host.get_issue(locator, n)`, and render with `render_issue(snapshot, None)` (no cutoff, D3). Result: text, `IssueSource.GITHUB`, sha256
  - [ ] Any `CodeHostError` (not found, pull request, auth, unreachable, `HostCommandTimeoutError`, no or ambiguous remote) is logged with `logger.exception` at ERROR and re-raised as `IssueTextError` carrying the host's message; no retry, no file fallback. `FixContextAction` returns it as a refusal before any dispatch
- [ ] Tests (extend `tests/pipeline/test_fix_issue.py`, `tests/pipeline/actions/test_fix_context.py`, replace the Task 3 not-built-yet case, and add a fetch-refusal case to `tests/pipeline/test_fix_pipeline.py`): a fake `CodeHost` returns a snapshot (use 422's test snapshot builder if it exists) and the prompt contains the rendered text with every comment and no cutoff; a fake that raises `HostCommandTimeoutError`, one raising the 422 not-found error, and one with no remote on a served host each fail the action with the host's message and `caplog` shows an ERROR record; the dispatch fake in the pipeline-level test is never called
  - [ ] Success: tests pass
- [ ] Add one case to `tests/load/test_fix_context_blocking.py` (Task 9): the real `IssueTextLoader` with a fake `CodeHost` whose `get_issue` blocks for a fixed time; the ticker's longest gap stays well under the block time
  - [ ] Success: the case passes under `uv run pytest tests/load/test_fix_context_blocking.py -q`
- [ ] Docs: in `docs/PIPELINES.md` `### fix`, add the fetched source (an empty `issue-file` fetches the issue and every comment through the code host, no cutoff; a host error fails before any dispatch) and, in the CHANGELOG bullet, say `sq run fix <issue>` reads the issue from GitHub
  - [ ] Success: `uv run pytest tests/docs tests/cli -q` passes

**Commit**: `feat: fetch fix issue text through the code host`

### Task 16: Verification walkthrough (design Verification Walkthrough)
Scratch work goes in new directories under `/tmp`; nothing is pushed. `SQ` below is `command -v sq`; confirm it is the build of this branch with `sq run fix --validate` (the `fix` pipeline exists only here).
- [ ] Gates on the whole branch: `ruff format --check`, `ruff check`, `pyright` (zero errors), `uv run pytest -q`
  - [ ] Success: all clean; failures fixed, or recorded as already failing on the target with the test names
- [ ] Walkthrough step 1 (listed and valid): `sq pipelines list -v`, `sq run fix --validate`, `sq run fix 301 --dry-run`
  - [ ] Success: `fix` listed with params `issue`, `model`, `issue-file`, `commit-to`; the dry run shows `fix-context → dispatch → commit`
- [ ] Walkthrough step 2 (refusals before spending), on the slice branch: with an untracked `scratch.txt`, `sq run fix 301` refuses and lists it; with the tree clean, it refuses because the slice branch is not the target; delete the file afterwards
  - [ ] Success: both refusals as described; `sq runs` shows no dispatch for either
- [ ] Walkthrough step 4 (frozen text, no `gh`, no `cf`) in a scratch clone (`git clone --no-hardlinks . /tmp/fixcheck`, then `git checkout -b sandbox`), the issue text from a real issue (`gh issue view <n> --json title,body --jq '.title + "\n\n" + .body' > /tmp/issue.md`); if the repository has no open issue, a hand-written text file for a known small defect. Make `/tmp/fixbin/gh` and `/tmp/fixbin/cf`, each a script that appends its arguments to `/tmp/fixbin/calls.log` and exits 127. Run as the design's step 4 gives, with `env PATH="/tmp/fixbin:$(dirname "$SQ"):/usr/bin:/bin" GH_TOKEN=`, so any call to either command is recorded whether or not a real one exists on the machine
  - [ ] Success: one commit on `sandbox`; run state shows `issue_source: file` and the file's sha256; `/tmp/fixbin/calls.log` is absent or empty (if it has lines, they name the caller's arguments: a call from squadron is a defect to fix, a call from the agent's own tool use is recorded in the DEVLOG)
- [ ] Walkthrough step 5 (cost cap) in the same clone, tree clean after step 4: `sq run fix <n> -p issue-file=issue.md -p commit-to=current --io-dir /tmp --max-cost 0.01`
  - [ ] Success: `sq runs show <run-id>` shows `failure_kind: cost_cap`; `git log` shows no new commit
- [ ] Walkthrough step 3 (fetched source, target mode, real fix) in a cf-registered scratch clone, the setup `ReplaySandbox._register_with_cf` uses: `git clone --no-hardlinks . /tmp/fixtarget`; set its `origin` to this repository's real URL (`git remote get-url origin` from here, then `git remote set-url origin <url>` there); `git switch -c fix-target-check`; `cf init --lite --no-ide --name fixtarget-check`; `cf config set git.integration_branch fix-target-check`; pick a small open issue with `gh issue list --state open`; run `sq run fix <n> --max-cost 3` with the default `commit-to: target`. Confirm the new test fails at `HEAD~1` and passes at `HEAD`, and the gates the report lists pass, as the design's step 3 lists. This is a scratch clone, so it shows target mode against a cf-registered checkout and not a commit on squadron's own `main`, which a walkthrough must not make. Afterwards `cf project rm fixtarget-check --yes` and remove the clone
  - [ ] Success: one `fix:` commit with `Fixes #<n>` on `fix-target-check`; run state shows `issue_source: github`; the new test fails at the parent and passes at the commit
- [ ] Walkthrough step 6 (`/sq:run fix <n>`) needs an interactive Claude Code session a task cannot drive. Its automated coverage is the Task 13 parity and `run.md` tests, plus: `sq run fix <n> --prompt-only` prints three actions whose commands match the Task 13 forms. In the slice's DEVLOG entry list `/sq:run fix <n>` as a manual check for the Project Manager; no task waits on it
  - [ ] Success: the rendered JSON matches; the DEVLOG entry carries the manual-check line

Any file the walkthrough made you change (a defect it found in this slice's code) is committed here; with no change there is nothing to commit.

**Commit**: `fix: correct fix pipeline defects found in verification`
