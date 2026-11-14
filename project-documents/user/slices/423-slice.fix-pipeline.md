---
docType: slice-design
slice: fix-pipeline
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [422]
interfaces: [424]
dateCreated: 20261104
dateUpdated: 20261113
status: complete
---

# Slice Design: Fix Pipeline

## Overview

`sq run fix <issue>` is a built-in pipeline that makes a fix the way the guide's fix rule says: a test that fails for the reported reason, the change that makes it pass, the project's gates, and one `fix:` commit on the target with `Fixes #n`. It has no branch, task file or review.

The same pipeline runs inside a benchmark sandbox. There the issue text comes from a file instead of GitHub, the commit goes on the current branch, and nothing calls GitHub or Context Forge.

## Value

- **User:** fixes are interactive today. A fix can now run unattended under the cost cap, from the CLI or `/sq:run`, and land as one commit that follows the fix rule.
- **Initiative:** fix cases (422) replay this pipeline (424). Fix-case results measure this pipeline's prompt. The architecture rules out using the `implement` step for this, because a fix has no design or task file.

## Technical Scope

Included:
- A `fix` step type. It expands to three actions: `fix-context` (issue text, preconditions, the assembled prompt), `dispatch` (the existing action), and `commit` (a new `fix` commit subject).
- The built-in pipeline `src/squadron/data/pipelines/fix.yaml`.
- The fix prompt, as a data file.
- The fix report: a JSON object the agent ends its reply with. The pipeline parses and checks it before committing.
- Two issue sources: fetched through `CodeHost.get_issue`, or read from a frozen file (`issue-file`).
- Two commit destinations: the integration target, or the current branch (`commit-to`).
- Prompt-only rendering, so `/sq:run fix <n>` stages, refuses and commits the same way `sq run fix <n>` does.
- Docs: the step in `docs/PIPELINES.md` (step catalog, built-in pipelines table), and a CHANGELOG bullet.

Excluded:
- Producer-only mode and anything else to do with replay (424).
- Running the gate commands from squadron. The agent runs them and reports them (D4).
- Posting to the issue, pushing, opening a PR, or closing the issue. `Fixes #n` closes it when the commit reaches the host's default branch.
- Choosing between fix and feat. The pipeline always commits `fix:`.
- A squadron MCP tool for `sq run`. Squadron has no MCP server for any pipeline; it uses MCP only as a client (`tools/mcp_bridge.py`). The parity criterion therefore covers the CLI and `/sq:run` (D9).

## Dependencies

### Prerequisites

- 422, for fetched issue text only: `CodeHost.get_issue` and the issue-text renderer (`issue_freeze`). This slice calls the renderer without a cutoff (D3), so 422 owns a renderer whose cutoff is optional. File mode needs nothing from 422.
- Bare-`#n` repository resolution already exists (`select_remote`, `codehost/remotes.py`).

### Interfaces Required

- `PipelineExecutor`, step type registry, `ActionResult`, and failure kinds.
- `DispatchAction`'s prompt fallback. It reads the prompt from the most recent prior output that carries assembled context. `fix-context` provides that output (D2).
- `extract_json_object` (`pipeline/actions/dispatch_io.py`) for the fix report.
- `CommitAction`, `CommitPlan`, `CommitSubject` (`pipeline/commit_plan.py`), `read_integration_target` and `current_branch` (`pipeline/git_ops.py`), `read_head` (`pipeline/head_stamp.py`), `changed_paths` (`pipeline/guarded_commit.py`).
- The cost cap (`pipeline.max_cost_usd`, the pipeline-file `max_cost_usd`, `--max-cost`) and `--io-dir`, both unchanged.
- The prompt renderer and the hidden `sq _commit` command, for prompt-only mode.

## Architecture

### Component Structure

```
src/squadron/
  data/pipelines/fix.yaml          built-in pipeline: one fix step
  data/prompts/fix.md              the fix prompt
  pipeline/steps/fix.py            FixStepType: validate, expand, needs_context_forge
  pipeline/actions/fix_context.py  FixContextAction: issue text, preconditions, prompt
  pipeline/fix_issue.py            IssueSource: parse the issue ref, fetch or read the text
  pipeline/fix_report.py           FixReport model and parse_fix_report
  pipeline/fix_commit.py           fix_commit_plan: target check, HEAD check, message
  cli/commands/fix_prompt_run.py   hidden `sq _fix-prompt` (prompt-only counterpart of fix-context)
```

Existing modules gain one entry each: `StepTypeName.FIX`, `ActionType.FIX_CONTEXT`, `CommitSubject.FIX`, `FailureKind.FIX_REPORT`, and the renderer table entries for the two actions. Each new module stays well under 300 lines.

### Data Flow

```
sq run fix 301 [-p issue-file=PATH] [-p commit-to=current] [--max-cost N] [--io-dir DIR]
  │
  ├─ fix-context
  │    parse issue ref ("301" or "#301") → 301
  │    preconditions: clean tree; destination branch check (D5)
  │    issue text: file (verbatim) | CodeHost.get_issue → render, no cutoff
  │    prompt = data/prompts/fix.md with the issue number and text substituted
  │    outputs: assembled prompt, issue number, source, text sha256, start HEAD, commit-to
  │
  ├─ dispatch (existing action, step model)
  │    agent: failing test → run it, see it fail → change → gates → report JSON
  │    agent does not commit
  │
  └─ commit (subject: fix)
       parse_fix_report(reply) → FixReport | refusal | blocked
       blocked → step fails with the reason, no commit
       fix_commit_plan: branch check, HEAD == start HEAD, stage all changes
       message: "fix: {summary}\n\nFixes #301"
```

### State Management

- The `fix-context` outputs and the commit action's metadata (the parsed report, commit sha) are saved in the run state file like any action's. Nothing new is persisted elsewhere.
- Start HEAD is the HEAD when `fix-context` runs. In prompt-only mode it is read when the step's instructions are rendered (D9).

## Technical Decisions

### D1 — A `fix` step type, not a pipeline of generic steps
Status: decided
- The step expands to `fix-context → dispatch → commit`, the same way `implement` expands to `cf-op → dispatch → review → commit`. `fix.yaml` is that one step:

```yaml
name: fix
description: Fix an issue - failing test, change, gates, one fix commit
params:
  issue: required
  model: sonnet
  issue-file: ""
  commit-to: target
steps:
  - fix:
      issue: "{issue}"
      model: "{model}"
      issue-file: "{issue-file}"
      commit-to: "{commit-to}"
```

- `sq run fix 301` binds `301` to `issue`, the first required param, through the existing `_resolve_target`.
- One step gives 424 a single producer step to run. It has no embedded review to strip, which matches the fix rule's "no review unless the Project Manager asks".
- Rejected: `dispatch` + guarded `commit` steps in YAML. The guarded commit needs `paths` globs and a fixed message. A fix touches any file, and its message comes from the agent. Prompt-only mode also refuses both `prompt_files` and the guarded commit, so `/sq:run fix` would not work.

### D2 — Issue text and the assembled prompt (`fix-context`)
Status: decided
- **Issue ref:** `issue` must be a positive integer, with an optional leading `#`. Anything else fails at validation, naming the value.
- **Frozen file** (`issue-file` non-empty): the path resolves against `--io-dir` when one is set, otherwise against the working directory. Paths with `..` are refused, using the same check as `prompt_files` (`dispatch_keys.path_error`). The file is read as UTF-8 and used verbatim. A missing, empty, unreadable or non-UTF-8 file fails the action before any model call. No `CodeHost` is constructed.
- **Fetched** (`issue-file` empty): the repository comes from the checkout's remotes through the existing bare-`#n` resolution. Then `CodeHost.get_issue(locator, number)` is called. It inherits `GitHubCli`'s existing 30-second command timeout (`HOST_COMMAND_TIMEOUT_SECONDS`), which raises `HostCommandTimeoutError`. A not-found, auth, transport or timeout `CodeHostError` fails the action before any dispatch, with the host's message. There is no retry and no fallback to a file.
- An empty `issue-file` is a documented mode ("fetch"). It is not a placeholder for a missing value.
- **Prompt:** `data/prompts/fix.md` gets two substitutions, `{issue_number}` and `{issue_text}`. The result goes in the action's outputs under the same keys `cf-op(build_context)` uses (`operation: build_context`, `context`). The dispatch picks it up through its existing fallback, so `DispatchAction` does not change.
- **Recorded:** `issue_number`, `issue_source` (`file` or `github`), `issue_text_sha256`, `start_head`, `commit_to`. 424 can check from the run state that a replay used the frozen text it was given.

### D3 — Fetched issue text has no cutoff
Status: decided
- A production fix works from the issue as it stands: title, body and every comment, rendered by 422's renderer with no cutoff. The cutoff and the edited-after-fix rejection exist only to keep a benchmark case from seeing its answer. A live fix has no answer yet.

### D4 — The agent runs the gates and reports them; the pipeline checks the report
Status: decided
- Squadron does not know a project's gate commands. They come from the project's conventions and rules, which SDK dispatches load natively and other dispatches get injected. The prompt tells the agent to run the format, lint, typecheck and touched-area test commands its project rules name.
- The agent ends its reply with one JSON object and writes no other. `parse_fix_report` reads the first JSON object it finds (`extract_json_object`, the helper every JSON reply uses), so a second object earlier in the reply would be read instead; the prompt forbids it. Fields:
  - `summary`: imperative one-line commit summary, without the `fix:` prefix.
  - `failing_tests`: test ids added or changed to reproduce the issue.
  - `failed_before_change`: whether those tests were run and failed before the change.
  - `gates`: list of `{command, exit_code}`, one per gate command run after the change.
  - `blocked`: present only when the fix cannot proceed without the Project Manager. It holds the reason, and the other fields are then not required.
- `parse_fix_report` uses `extract_json_object` and a Pydantic model. Each of these fails the step with `failure_kind: fix_report` and a message naming the field: no JSON object; `summary` empty or multi-line, or starting with `fix:`; `failing_tests` empty; `failed_before_change` not `true`; `gates` empty; any non-zero `exit_code`. The report is checked before anything is staged, so a refused fix leaves the agent's changes in the tree for inspection and commits nothing.
- `blocked` fails the step with `failure_kind: fix_report` and the reason, commits nothing, and leaves the tree as the agent left it. It does not pause the run. `sq run --resume` would re-run `fix-context`, which refuses the dirty tree, so there is no resume path. The user resolves the block, commits or discards the changes by hand, and runs `sq run fix` again.
- The prompt describes the fields by name and meaning only. It gives no example values, so a model that has nothing to report cannot copy an example (hallucination trap).
- Rejected: squadron re-running the gates. That would need a per-project gate config that does not exist, or re-running commands the model chose. 425 grades replays objectively. In production this is the same trust an interactive fix gets, but it is now recorded and checked for shape.

### D5 — Commit destination and preconditions
Status: decided
- `commit-to: target` (default). The destination is `read_integration_target` (`git.integration_branch`, else `main`). `fix-context` refuses unless the current branch is that target. It never switches branches, because the fix rule commits straight to the target.
- `commit-to: current`. The destination is the branch checked out when `fix-context` runs. A detached HEAD is refused. Context Forge is not read. 424 uses this in a sandbox, where cf is neither registered nor on `PATH`.
- Any other `commit-to` value fails validation.
- **Clean tree:** `fix-context` refuses a dirty working tree (`changed_paths` non-empty) and lists the paths. The fix commit stages everything, so a pre-existing change would end up in it.
- **HEAD unchanged:** the commit refuses if HEAD is not `start_head`. The prompt tells the agent not to commit, and an agent commit would mean the run cannot vouch for a single commit.
- **Staging:** every changed and untracked path, ignored files excluded (`changed_paths`). A report with no staged changes fails with `fix_report`: "report claims a fix but the tree has no changes".

### D6 — Commit message
Status: decided
- Subject: `fix: {summary}`. Body: `Fixes #{issue_number}`. Then any attribution lines the commit action already adds for pipeline commits, unchanged.
- The issue line is written in both destinations. In a sandbox it is inert, because the sandbox has no remote.
- A summary longer than 72 characters is kept as written and logged at WARNING. Trimming it would change what the agent wrote.

### D7 — The fix step does not declare a Context Forge need
Status: decided
- `FixStepType.needs_context_forge` returns false. The shared `sq run` gate does not change.
- Under `commit-to: target`, `fix-context` reads the target through `read_integration_target`, which already raises with a clear message when cf is unavailable. That fails the action before any dispatch.
- With `commit-to: current` and `issue-file` set, the fix pipeline makes no cf call and no `gh` call. It runs in any git repository, as #288 already allows for cf-free pipelines.
- Rejected: resolving placeholders before the `sq run` cf gate so the step could answer per mode. It changes the gate for every pipeline to serve one param.

### D8 — Fix prompt as a data file
Status: decided
- `data/prompts/fix.md` is loaded through `importlib.resources`, like the other packaged data. It is the one source of the prompt for both modes.
- Contents, in order:
  - The task: fix issue #N following the project's fix rule.
  - Steps: write a test that fails for the reported reason, run it and confirm it fails, make the change, run the gates.
  - Constraints: do not commit, push, switch branches, or fetch the issue, because its text is given below.
  - The report fields (D4), and the `blocked` exit.
  - The issue text, between explicit begin and end markers.
- The prompt's text is part of the dispatch's prompt identity, which `prompt_identity.py` already records. 424 and 425 can therefore tell results from different prompt versions apart.

### D9 — Prompt-only parity (`/sq:run fix`)
Status: decided
- `fix-context` renders as `sq _fix-prompt --issue N [--issue-file PATH] [--io-dir DIR] --commit-to MODE`. This hidden command runs the same `FixContextAction` code and prints the assembled prompt. The session runs it as it runs `cf build` for a phase step.
- `dispatch` renders as it does today ("Execute the work using the assembled context").
- `commit` renders as `sq _commit --subject fix --issue N --commit-to MODE --start-head SHA --report-file {tmp_path}`. The session writes its final JSON report to the temp file. `SHA` is read once by `render_step_instructions`, which builds all three actions' instructions together before the session runs `fix-context`. An agent commit during the dispatch therefore moves HEAD away from it. `sq _commit` calls the same `parse_fix_report` and `fix_commit_plan` the SDK path does, so it accepts, refuses and phrases the message identically.
- Rejected: an MCP `run` tool. No pipeline has one. Adding the first one for `fix` would be a separate feature.

### Patterns and Conventions

- Every comparison value is defined once: `StepTypeName.FIX`, `CommitSubject.FIX`, `FailureKind.FIX_REPORT`, a `CommitTo` StrEnum (`target`, `current`), an `IssueSource` StrEnum (`file`, `github`), and param-key constants shared by the step, the action, the renderer and the hidden commands.
- Each refusal is an `ActionResult(success=False)` with a message that names the cause, logged at WARNING. Code-host and git errors are logged with `logger.exception` at ERROR and fail the action.

## Implementation Details

### API Contracts

**CLI**

```
sq run fix <issue> [--model ALIAS] [-p issue-file=PATH] [-p commit-to=target|current]
                   [--max-cost USD] [--io-dir DIR] [--prompt-only]
```

| Param | Default | Meaning |
|---|---|---|
| `issue` | required | Issue number, `301` or `#301` |
| `model` | `sonnet` | Model alias for the dispatch |
| `issue-file` | `""` (fetch) | Frozen issue text; relative to `--io-dir` or the working directory |
| `commit-to` | `target` | `target`: integration target, must be checked out. `current`: the checked-out branch, no cf |

**Step config** (`fix:`), with keys `issue`, `model`, `issue-file` and `commit-to`. Any other key is rejected under `--strict`, like any step.

**Hidden commands**

- `sq _fix-prompt --issue N [--issue-file PATH] [--io-dir DIR] --commit-to MODE` prints the assembled prompt, or exits 1 with the refusal.
- `sq _commit --subject fix --issue N --commit-to MODE --start-head SHA --report-file PATH` commits or exits 1 with the refusal. A `blocked` report is a refusal and prints the reason.

## Integration Points

### Provides to Other Slices

- **424:** the `fix` pipeline and its single producer step. 424 runs it in a sandbox as `sq run fix <n> -p issue-file=<io-dir file> -p commit-to=current --io-dir <dir>`. The run state's `fix-context` outputs confirm the source and text hash, and the commit is on the sandbox branch.
- **425:** the fix commit as the producer's tree, with the fix report in the run state. 425 grades on its own and does not trust the report.

### Consumes from Other Slices

- **422:** `CodeHost.get_issue` and the issue-text renderer with an optional cutoff (see Prerequisites).
- **947 / #241:** the cost cap, unchanged.
- **#288:** cf-free pipeline runs, unchanged (D7).

## Success Criteria

### Functional Requirements

- `sq run fix <n>` on a real open squadron issue produces one new commit on the target. The commit adds a test that fails at the parent for the issue's reason and passes at the commit. Its subject is `fix: …` and its body has `Fixes #n`. The gates the report lists pass when re-run by hand.
- With `-p issue-file=… -p commit-to=current`, the pipeline runs in a git repository that is not cf-registered, with `cf` and `gh` absent from `PATH`. It commits to the checked-out branch.
- `fix-context` refuses a dirty tree (it lists the paths), a branch that is not the target under `commit-to: target`, a detached HEAD under `commit-to: current`, an invalid issue ref, and a missing or empty issue file. Each refusal happens before any dispatch.
- Each report defect listed in D4 fails with `failure_kind: fix_report`, commits nothing, and leaves the tree as the agent left it. So does a `blocked` report, which fails with its reason.
- An agent that commits during the dispatch makes the commit action refuse with the HEAD-moved message.
- `--max-cost` and `pipeline.max_cost_usd` stop a fix run whose dispatch crosses the cap, with `failure_kind: cost_cap`.
- `/sq:run fix <n>` and `sq run fix <n>` produce the same prompt and the same commit message for the same report. They refuse the same report defects with the same text.

### Technical Requirements

- Unit tests:
  - issue ref parsing
  - both issue sources (a fake `CodeHost`, including one that raises `HostCommandTimeoutError`; in file mode, a `CodeHost` factory that raises if called)
  - each precondition
  - `parse_fix_report`: every rejection, a valid report, a `blocked` report
  - `fix_commit_plan`: both destinations, HEAD moved, nothing staged
  - the message format
- An executor-level test runs `fix.yaml` with a fake dispatch that edits a file and returns a report. It asserts one commit with the expected message and run-state outputs.
- A parity test renders the step in prompt-only mode and runs `sq _fix-prompt` and `sq _commit` against the same fixture. It asserts the same prompt text and the same commit, and that `sq _commit` refuses when the fixture commits between rendering and the commit.
- `ruff format`, `ruff check`, `pyright` with zero errors.

### Integration Requirements

- 424 can run the pipeline in a 421 sandbox under the scrubbed environment with no extra flags or code paths beyond `issue-file`, `commit-to` and `--io-dir`.
- `sq pipelines list` shows `fix`. `sq run fix --validate` and `sq run fix 1 --dry-run` work.

### Verification Walkthrough

Verified 20261113 on the slice branch. `SQ` is the build of this branch: `$PWD/.venv/bin/sq` from the repository root (an installed `sq` older than the branch has no `fix` pipeline; `sq run fix --validate` must print `Pipeline 'fix' is valid.`). Steps 3 to 5 call a real model (a run costs well under $1 on `sonnet`); scratch work goes in new `/tmp` directories.

1. **The pipeline is listed and valid.**
   ```bash
   $SQ pipelines list -v | grep -E '^ *fix\b'
   $SQ run fix --validate
   $SQ run fix 301 --dry-run
   ```
   Expect a `fix` row ending `issue=required model=sonnet issue-file= +1` (the list shows three params and counts the rest; `commit-to` is the one counted), then `Pipeline 'fix' is valid.`, then a dry run listing the one step as `fix-0 (fix)`. `--dry-run` prints steps, not actions, for every non-container step type; the three actions show under `--prompt-only` (step 6). All three commands also work with `cf` off `PATH`.

2. **Preconditions refuse before spending.** On the slice branch, which is not the target:
   ```bash
   touch scratch.txt && $SQ run fix 301; rm scratch.txt
   $SQ run fix 301
   ```
   Expect first `fix-context refused: the working tree has uncommitted changes: scratch.txt`, then (tree clean) `commit-to target requires branch 'main', but '<current branch>' is checked out`. Both end `Pipeline 'fix' — failed` with `fix-0: failed`. Neither dispatches: `$SQ runs list` shows both runs `failed` at `fix-0`, and the run's state file (`~/.config/squadron/runs/<run-id>.json`) lists only a failed `fix-context` action. (There is no `sq runs show`.)

3. **A real fix, fetched issue, target mode.** A walkthrough must not commit to squadron's own `main`, so use a cf-registered scratch clone whose current branch is its integration target:
   ```bash
   URL=$(git remote get-url origin)                    # the real URL, so a bare #n resolves
   git clone --no-hardlinks . /tmp/fixtarget && cd /tmp/fixtarget
   git remote set-url origin "$URL"
   git switch -c fix-target-check
   cf init --lite --no-ide --name fixtarget-check
   cf config set git.integration_branch fix-target-check
   uv sync -q
   $SQ run fix <n> --max-cost 3        # <n>: a small open issue from `gh issue list`
   git log -1 --format='%s%n%n%b'; git show --stat HEAD
   ```
   Expect `Pipeline 'fix' — completed` and one commit on `fix-target-check` with subject `fix: …` and body `Fixes #<n>`, a test file and the change in the stat. The run state shows `issue_source: github`, the parsed report under the commit action's `fix_report`, and the issue text's sha256. Then confirm the test is real and the reported gates pass:
   ```bash
   git worktree add /tmp/fixparent HEAD~1
   cp tests/<test file from the commit> /tmp/fixparent/tests/<same path>
   (cd /tmp/fixparent && uv sync -q && uv run pytest "<failing test id>")   # fails
   uv run pytest "<failing test id>"                                         # passes
   git worktree remove --force /tmp/fixparent
   uv run ruff format --check src tests && uv run ruff check src tests && uv run pyright
   ```
   Afterwards: `cf project rm fixtarget-check --yes` and remove `/tmp/fixtarget`. Caveat: a test written to the agent's new signature fails at the parent with a `TypeError`, which proves it fails there but not that it shows the reported symptom; read the test.

4. **Frozen text, no GitHub, no cf.** In a scratch clone, with stand-in `gh` and `cf` first on `PATH` that record their arguments and exit 127 (so any call is logged whether or not a real one exists):
   ```bash
   git clone --no-hardlinks . /tmp/fixcheck && cd /tmp/fixcheck && git checkout -b sandbox && uv sync -q
   mkdir /tmp/fixbin /tmp/fixsq && ln -s "$SQ" /tmp/fixsq/sq
   for n in gh cf; do printf '#!/bin/sh\necho "%s $@" >> /tmp/fixbin/calls.log\nexit 127\n' $n > /tmp/fixbin/$n; chmod +x /tmp/fixbin/$n; done
   gh issue view <n> --json title,body --jq '.title + "\n\n" + .body' > /tmp/issue.md
   env PATH="/tmp/fixbin:/tmp/fixsq:$(dirname "$(command -v uv)"):/usr/bin:/bin" GH_TOKEN= \
     sq run fix <n> -p issue-file=issue.md -p commit-to=current --io-dir /tmp --max-cost 3
   git log -1 --format='%D %s'; cat /tmp/fixbin/calls.log
   ```
   Expect `Pipeline 'fix' — completed`, the commit on `sandbox`, the run state's `issue_source: file` and `issue_text_sha256` equal to `shasum -a 256 /tmp/issue.md`, and no `calls.log`. The first run of this step logged `cf get --json`: `execute_pipeline` read the project name from cf at start even when no step needs cf. It now does that only for a pipeline with a cf-using step (`any_step_needs_context_forge`), and `test_the_pipeline_invokes_neither_gh_nor_cf` covers it. (`uv` stays on `PATH` so the agent can run the clone's gates; `$SQ` is a symlink so the clone's own venv, not the repository's, is what its tests import.)

5. **Cost cap.** In the same clone, tree clean:
   ```bash
   env PATH=… GH_TOKEN= sq run fix <n> -p issue-file=issue.md -p commit-to=current --io-dir /tmp --max-cost 0.01
   ```
   Expect `Error: run spent $… this invocation, over --max-cost $0.01; raise the cap and resume to continue`, `git log` unchanged, and `failure_kind: cost_cap` on the dispatch action in the run's state file.

6. **Slash-command parity.** Automated: `$SQ run fix <n> --prompt-only 2>/dev/null` prints one step with three actions: `fix-context` (`sq _fix-prompt --issue <n> --commit-to target`), `dispatch` (no command: in-session work) and `commit` (`sq _commit --subject fix --issue <n> --commit-to target --start-head <sha> --start-branch <branch> --report-file '{tmp_path}'`). `tests/pipeline/test_fix_prompt_parity.py` shows the hidden commands give the same prompt, message and refusals as the SDK actions. Manual (needs an interactive Claude Code session): `/sq:run fix <n>` on a clean target, expecting the step 2 refusals under the same conditions and, on success, a commit through `sq _commit --subject fix`.

## Risk Assessment

### Technical Risks

- **Report honesty.** An agent can report gates it did not run. Production accepts the same trust an interactive fix does. The benchmark does not depend on it, because 425 re-grades objectively.
- **Untrusted issue text steers what is committed.** The fetched text includes every comment, so anyone who can comment influences the agent, and the commit stages every changed path (D5). The prompt marks the text as data and the clean-tree check bounds the starting state, but nothing limits or reports the paths. Deferred to #328.

### Mitigation Strategies

- Report: the shape checks in D4, and walkthrough step 3 re-runs the reported gates by hand.

## Implementation Notes

### Development Approach

1. `fix_issue.py` (ref parsing, file source) and `fix_report.py`, with tests. These are pure, with no executor.
2. `fix_commit.py` and `CommitSubject.FIX` in `CommitAction`, with tests.
3. `FixContextAction`, `FixStepType`, `fix.yaml`, the prompt file, and the executor-level test.
4. The fetched source through 422's `CodeHost.get_issue` and renderer.
5. Prompt-only: renderer entries, `sq _fix-prompt`, `sq _commit --subject fix`, the parity test.
6. Docs and CHANGELOG. Run walkthrough steps 1–5 on squadron.

Effort: 3/5. The slice plan said 2/5. Prompt-only parity and the report contract add a step.

### Special Considerations

- The fix commit stages every change. The clean-tree precondition is what makes that safe, so it must run before the dispatch, never only at commit time.
- `--io-dir` already exists for file-in steps. Reusing it for `issue-file` means 424 needs no new flag.
- The pipeline never pushes. A production fix lands on the local target, and the user pushes.
