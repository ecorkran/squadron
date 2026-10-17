---
docType: review
layer: project
reviewType: code
slice: producer-replay-and-pairwise-judging
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: fdc21e1dbb800395ce682527b4bc8d5769e99824
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: true
turns: 3
promptTokens: 355832
cachedTokens: 174465
cacheWriteTokens: 181363
completionTokens: 5498
durationSeconds: 60.4
costUsd: 1.654
costBasis: provider
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "build_context now fails, or crashes, when it cannot read provenance metadata"
    location: "src/squadron/pipeline/actions/cf_op.py:146-149"
  - id: F002
    severity: concern
    category: error-handling
    summary: "An invalid `metrology.judge_timeout_s` produces a traceback in `sq replay judge`"
    location: "src/squadron/cli/commands/replay_judge.py:63-74"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Filesystem errors while building a sandbox or reading drafts escape the runner and abort the whole set"
    location: "src/squadron/replay/sandbox.py:135-140"
  - id: F004
    severity: concern
    category: style
    summary: "`_sq_executable` uses `os.path.abspath` instead of pathlib"
    location: "src/squadron/cli/commands/replay.py:51-57"
  - id: F005
    severity: note
    category: dry
    summary: "The LLM-call-bound formula is written in two places"
    location: "src/squadron/cli/replay_views.py:24-27"
  - id: F006
    severity: note
    category: structure
    summary: "`report.py` and `runner.py` are over the ~300-line guideline; `_config_row` and `_original_row` repeat the judged fields"
    location: "src/squadron/replay/report.py"
  - id: F007
    severity: note
    category: concurrency
    summary: "`init_run`'s check that a run id is not already taken is check-then-write"
    location: "src/squadron/pipeline/state.py:359-360"
  - id: F008
    severity: note
    category: design
    summary: "`build_jobs` calls a CLI-level function that can raise `typer.Exit`"
    location: "src/squadron/cli/commands/replay_judge.py:44-51"
  - id: F009
    severity: pass
    category: dry
    summary: "The process lock was extracted without changing behaviour"
    location: "src/squadron/core/process_lock.py"
  - id: F010
    severity: pass
    category: design
    summary: "Failure classification uses values, not error text"
    location: "src/squadron/pipeline/failure_kind.py"
  - id: F011
    severity: pass
    category: failure-modes
    summary: "Judge calls have a timeout and their failures are logged"
    location: "src/squadron/replay/judging.py:163-174"
  - id: F012
    severity: pass
    category: parsing
    summary: "The verdict parser is lenient and tested against captured real replies"
    location: "src/squadron/replay/judge.py:20-41"
---

# Review: code — slice 177

**Verdict:** CONCERNS
**Model:** claude-opus-5-5
**Diff:** truncated: 256000 of 329274 characters reached the model

## Findings

### [CONCERN] build_context now fails, or crashes, when it cannot read provenance metadata

`build_context` used to need only `cf build --json`. It now also calls `cf_client.cf_version()` and `_read_guide_version()` inside the same `try`. This affects every P4/P5 run, not only replays.
- **`cf --version`:** if it fails or prints nothing, it raises `ContextForgeError`, and the whole build_context step fails. A fact that only feeds metadata now blocks production prompt building.
- **The guide version file (`cf_op.py:167-172`):** `read_text` can raise `OSError` or `UnicodeDecodeError`. The `except ContextForgeError` does not catch either, so they escape `execute()` as an uncaught exception instead of a failed `ActionResult`.
- **An empty marker file** returns `""` rather than `None`. That empty string then lands in the prompt identity and is treated as a missing version only by accident (`producer_report._guide_version` filters it out because it is falsy).

There are two reasonable fixes: decide that provenance is best-effort, log a WARNING and record `None`; or keep the hard failure but catch the file errors explicitly. Either way, add a test for the read-failure path.

### [CONCERN] An invalid `metrology.judge_timeout_s` produces a traceback in `sq replay judge`

`get_typed_config("metrology.judge_timeout_s", int, ...)` is evaluated inside the `try`, but the `except` only catches `JudgeInputError`, `JudgeCallError` and `ModelResolutionError`. A non-integer value raises `ValueError`, which surfaces as an uncaught traceback.

`replay_report.py:21-25` already handles the same case properly with `_min_evidence_n`, which prints a message telling the user how to fix the key. Read the timeout before the `try` using the same pattern, which also gets rid of a duplicate pattern. Add a test like `test_a_non_integer_evidence_floor_exits_1_naming_the_key`.

### [CONCERN] Filesystem errors while building a sandbox or reading drafts escape the runner and abort the whole set

The runner's docstring says "A failed config is data and does not stop the set", but only `SandboxError` is caught per config (`runner.py`, `run_replay_set`). Several file operations can raise other errors:
- `_write_lock` calls `write_text` (OSError).
- `_declares_submodules` calls `read_text` (`sandbox.py:152-155`; OSError or UnicodeDecodeError).
- `drafts._final_text` calls `path.read_text` (`drafts.py:43-47`).

Any of these raises a raw exception that leaves `run_replay_set` part-way through a set. Records already written stay in the store, but the CLI prints no summary and exits with a traceback. Either wrap these operations as `SandboxError` (and make draft reads return `None` with a WARNING), or document that they are meant to be fatal.

### [CONCERN] `_sq_executable` uses `os.path.abspath` instead of pathlib

The Python rules require `pathlib` for path operations. Use `str(Path(found).resolve())` or `Path(found).absolute()`. The test at `tests/cli/test_replay_run.py` already compares against `script.resolve()`, so `resolve()` is the natural match.

### [NOTE] The LLM-call-bound formula is written in two places

`build_plan` computes `len(configs) * 2 * (1 + max_revisions)`, and `render_plan` restates the same formula as display text: `"({n} configs x 2 x (1 + {max}))"`. If the bound changes (for example, if a judge call is added per round), the explanation shown to the user will silently go stale. Consider defining the per-round factor once, as a constant in `runner.py`.

### [NOTE] `report.py` and `runner.py` are over the ~300-line guideline; `_config_row` and `_original_row` repeat the judged fields

`report.py` (311 lines) and `runner.py` (315 lines) are slightly over the guideline. `_config_row` and `_original_row` each copy the nine `_Judged` fields into `ConfigRow` by hand. A small helper that returns those fields as keyword arguments, or having `_Judged` carry them directly, would shorten both functions and bring `report.py` under the limit.

### [NOTE] `init_run`'s check that a run id is not already taken is check-then-write

`self._state_path(run_id).exists()` followed by a later write is a TOCTOU race. Replay ids carry a uuid suffix, so in practice this is safe. If the guarantee needs to hold under real concurrency, open the file exclusively (`open(path, "x")`).

### [NOTE] `build_jobs` calls a CLI-level function that can raise `typer.Exit`

The `original` callable is `common.start_point`, which raises `typer.Exit` on a `StartPointError`. `judge_jobs.build_jobs` is otherwise free of the CLI, but this way an unresolvable original exits the whole judge command, even though a set could still be judged without the original. Injecting the dependency keeps the core testable, but consider letting the core receive `None` (or the error) so it can drop the original and log a WARNING, which it already does when the sha does not match.

### [PASS] The process lock was extracted without changing behaviour

The worktree's ps/lock helpers moved into a shared module and are reused by the replay sandbox. The worktree keeps its own error type through `_current_process_lock`. Tests cover every malformed-lock case, a recycled pid and a live owner.

### [PASS] Failure classification uses values, not error text

`FailureKind` is stamped where each failure is decided (in dispatch and dispatch_artifact), carried through by the executor, and mapped in `outcome._CLASS_OF_KIND`. An unknown kind becomes `other`, keeping its error text, instead of raising.

### [PASS] Judge calls have a timeout and their failures are logged

Each judge call is wrapped in `asyncio.wait_for` with a timeout taken from config. A timeout or a `JudgeCallError` is logged at ERROR. If the second call of a pair fails, the pair is left unjudged and the first call's spend is logged at WARNING. The broad `except Exception` in `judge_dispatch.py` sits at the model-call boundary, re-raises as a single typed error, and has a comment saying why.

### [PASS] The verdict parser is lenient and tested against captured real replies

The parser accepts variations in case, spacing, emphasis, `=` instead of `:`, quote and heading marks, and CRLF line endings, while still requiring the whole line to be the verdict. Its tests include replies captured from the production judge, as the parsing rules require.

## Response (20261016)

All four concerns fixed, each in its own commit, with a test for each new failure path.

- **F001 fixed** (7791d2e8): provenance is best-effort. An unreadable `cf --version` or guide version file records `None` and logs at ERROR; an empty marker file counts as absent. The prompt build no longer depends on either.
- **F002 fixed** (618c7ab1): one `int_config` reader in `replay_common`, used by both `replay judge` and `replay report`. A bad `metrology.judge_timeout_s` now exits 1 naming the key.
- **F003 fixed** (f4b637ab): lock-write and `.gitmodules`-read failures raise `SandboxError`, which the runner already treats as data. An unreadable final text is recorded as `None` with a WARNING.
- **F004 fixed** (67054354): `Path(found).resolve()`.
- **F005 not changed.** The formula appears once in code and once in help text; a constant for a factor of 2 adds indirection without a second consumer.
- **F006 not changed.** Both files are within ~5% of the guideline and splitting them would separate cohesive code. The duplicated field copy is small and stays readable.
- **F007 not changed.** Replay ids carry a uuid suffix and `init_run --run-id` is hidden and used only by the replay runner, so there is no concurrent writer to the same id.
- **F008 not changed.** An unresolvable original start point means the sandbox could not have been built for the same slice; failing the judge command is the right outcome.

### Run Digest

- Response length: 7713 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 355832 / 174465 / 181363 / 5498 / not computed
- Duration: 60.4 s
- Cost: $1.65 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
