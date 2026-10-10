---
docType: review
layer: project
reviewType: code
slice: everyday-cli-fixes
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/940-slice.everyday-cli-fixes.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261009
dateUpdated: 20261009
reviewedSha: d7dc17c77610eca4f8751039ad81d595c5f9d8ea
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 37
diffTruncated: false
turns: 20
promptTokens: 2193261
cachedTokens: 1856896
completionTokens: 119625
reasoningTokens: 115408
durationSeconds: 614.6
runId: run-20261010-p6-71f18cf9
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Resume executes under a different pipeline than it plans with"
    location: "src/squadron/cli/commands/run.py:1230-1245"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Escaping a string that is deliberately Rich markup prints the tags literally"
    location: "src/squadron/cli/commands/config.py:121-122"
  - id: F003
    severity: concern
    category: error-handling
    summary: "The sweep leaves pipeline-derived text unescaped, and the guard cannot see it"
    location: "src/squadron/cli/commands/run_dry_run.py:76"
  - id: F004
    severity: note
    category: consistency
    summary: "Adjacent config lines treat the same value differently"
    location: "src/squadron/cli/commands/config.py:86"
  - id: F005
    severity: note
    category: error-handling
    summary: "Resume reports loader failures on stdout while every other run entry point uses stderr"
    location: "src/squadron/cli/commands/run.py:1214"
  - id: F006
    severity: note
    category: test-quality
    summary: "The guard's detection of `print` and `escape` is name-based"
    location: "tests/cli/test_rich_escape_guard.py:22-41"
  - id: F007
    severity: pass
    category: testing
    summary: "The new state field is backward compatible and tested at the boundary"
    location: "src/squadron/pipeline/state.py:212"
  - id: F008
    severity: pass
    category: testing
    summary: "The escaping change ships with its own regression test"
    location: "tests/cli/test_run.py:334-340"
---

# Review: code — slice 940

**Verdict:** FAIL
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [FAIL] Resume executes under a different pipeline than it plans with

`_load_run_definition` (run.py:183-199) correctly loads `state.load_target`, i.e. `pipeline_path` when present. But the resume branch then calls `_run_pipeline_sdk(state.pipeline, ...)` (run.py:1231) / `_run_pipeline(state.pipeline, ...)` (run.py:1244), and both of those call `load_pipeline(pipeline_name)` again internally (run.py:257 and run.py:389). For a path run, `state.pipeline` is the lowercased file *stem* (`_run_record_identity`, run.py:169-178), so:

- If no pipeline of that name exists in the project/user/built-in search dirs, `resolve_pipeline` raises `FileNotFoundError` (loader.py:118-121). The resume block only guards `KeyboardInterrupt` (run.py:1250), so it escapes as a traceback instead of the "Pipeline '…' not found" message the new helper prints.
- If a same-named pipeline *does* exist, the run is planned from the recorded path and then executed from a different file — the silent fallback the slice's own D4 rules forbid.

The same hole exists in item resume: `src/squadron/pipeline/item_resume.py:194` uses `load_pipeline(state.pipeline)`, and `run_item.handle_item_resume` passes the name into `run_body` (`run_items`→`_run_pipeline_sdk`). The slice design states resume, `--status` and item resume should all use `state.pipeline_path or state.pipeline`; only `--status` and the two prompt-only loaders actually do. The tests cannot catch this: `test_run_resume_path.py` stubs `_load_run_definition` with `side_effect=typer.Exit(1)` and asserts only that it was *called* with the right target.

### [CONCERN] Escaping a string that is deliberately Rich markup prints the tags literally

`user_status` / `proj_status` are Rich markup by construction (`"[green]exists[/green]"`, `"[dim]not found[/dim]"`, config.py:117-118). Wrapping them in `escape(...)` turns them into `\[green]exists\[/green]`, which Rich renders as the literal text `[green]exists[/green]`. The escape sweep should cover interpolated *values*, not the format strings the command owns. `tests/config/test_cli_config.py` still passes because `"exists"`/`"not found"` are substrings of the literal output, so this degradation is invisible to the suite.

### [CONCERN] The sweep leaves pipeline-derived text unescaped, and the guard cannot see it

`f"{pad}source: {escape(source)}, as: {config.get('as')}, on_item_failure: {config.get('on_item_failure')}"` escapes only the source; the other two values come from pipeline YAML and go into Rich markup raw, so a `[bracketed]` value vanishes — the same symptom as #177. `_render_explain` (run.py:527) has the same shape for `step.step_name`, `step.action_type`, `step.rationale` etc. in `table.add_row`. These are outside the shown hunks, so this is a gap in the sweep rather than a regression. The guard test documents this limit (D5), which is honest — but it means the "every CLI print site" claim is not mechanically supported.

### [NOTE] Adjacent config lines treat the same value differently

`config get` prints `_display_value(val)` unescaped, while `config list` escapes the identical value two commands later (config.py:103). A config value containing brackets renders differently depending on which subcommand is used.

### [NOTE] Resume reports loader failures on stdout while every other run entry point uses stderr

`_load_run_definition(state, file=sys.stdout)` is the only caller that does not pass `sys.stderr` (compare run.py:758 and run.py:898). The `file` parameter exists precisely to make this a deliberate choice; the docstring does not say why resume differs, and it makes `sq run --resume x > out` put the error in `out`.

### [NOTE] The guard's detection of `print` and `escape` is name-based

`_is_escape_call` accepts any `*.escape(...)` attribute, so an unrelated object's `escape` would satisfy the check (false negative), and `_is_print_call` accepts any `*.print(...)`, so a non-Rich logger method named `print` would be scanned (false positive). An aliased import (`from rich.markup import escape as esc`) would also evade both. The parametrized cases cover the intended shapes; these are limits, not defects, and are worth stating next to the "user text that never passed through an exception" limit the design already records.

### [PASS] The new state field is backward compatible and tested at the boundary

`pipeline_path: str | None = None` keeps schema 5, and `tests/pipeline/test_state.py:230-278` covers the round-trip, the not-lowercased path, a literal pre-slice v5 file loading with `None`, and an unknown future field still loading. `load_target` (state.py:215-220) is a single accessor rather than the `or` expression repeated at each call site.

### [PASS] The escaping change ships with its own regression test

`test_cf_error_keeps_bracketed_text` asserts the observable signal (`[codex]` survives to stdout) rather than merely that `escape` was called, and the new AST guard is a mechanical ratchet for the whole sweep rather than a one-off assertion — the right shape for a class of bug that will recur.

### Run Digest

- Response length: 6176 chars
- Response is newline-free: no
- Tool calls made: 37
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 444241
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2193261 / 1856896 / 119625 / 115408
- Duration: 614.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
